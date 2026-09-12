"""Opt-in actual local dictionary/translation timings, never a mock speed claim."""

import hashlib
import json
import os
from pathlib import Path
from statistics import median
import subprocess
from time import perf_counter

import pytest

from src.search_v2.lexical_dictionary import SqliteLexicon
from src.search_v2.opus_mt import OpusMtTranslator


pytestmark = pytest.mark.skipif(
    os.environ.get("AMAZON_EXPLORER_LOCAL_TERMS_BENCHMARK") != "1",
    reason="Explicit local model benchmark only",
)
ROOT = Path(__file__).resolve().parents[1]
LEXICON = Path("/home/products/models/search-lexical-context-v2/lexicon.sqlite3")
MODEL = Path("/home/products/models/opus-mt-ja-en-ct2-v1")
PYTHON = Path("/home/products/model-envs/opus-mt-eval-02/bin/python")
PHRASES = (
    "軽量",
    "丸い",
    "取っ手",
    "陶器",
    "保温",
    "丈夫",
    "滑り止め",
    "電子レンジ対応",
    "食洗機対応",
    "3000円以下",
)


def timing(values):
    return {"samples": values, "median": median(values), "min": min(values), "max": max(values)}


def save(name, value):
    output = Path(os.environ["AMAZON_EXPLORER_TERMS_OUTPUT"]).absolute()
    assert not output.is_relative_to(ROOT)
    assert output.is_dir() and output.stat().st_mode & 0o077 == 0
    path = output / name
    with path.open("x", encoding="utf-8") as stream:
        os.chmod(path, 0o600)
        json.dump(value, stream, indent=2)
        stream.write("\n")


def test_local_dictionary_candidate_latency():
    assert LEXICON.is_file()
    started = perf_counter()
    lexicon = SqliteLexicon(LEXICON)
    init_seconds = perf_counter() - started
    rows = []
    try:
        for count in (1, 5, 10):
            samples, counts = [], []
            for _ in range(20):
                started = perf_counter()
                candidates = [lexicon.lookup_contextual(phrase) for phrase in PHRASES[:count]]
                # Retrieve all candidate forms/glosses without choosing a meaning.
                pairs = [
                    [(sense.forms, sense.glosses) for sense in senses] for senses in candidates
                ]
                samples.append(perf_counter() - started)
                counts.append([len(values) for values in pairs])
            assert all(value == counts[0] for value in counts)
            rows.append(
                {
                    "conditions": count,
                    "seconds": timing(samples),
                    "sense_counts": counts[0],
                    "hits": sum(bool(v) for v in counts[0]),
                }
            )
        assert any(row["hits"] for row in rows)
        save(
            "dictionary.json",
            {
                "initialization_seconds": init_seconds,
                "lexicon_sha256": lexicon.sha256,
                "rows": rows,
                "sense_selection_included": False,
            },
        )
    finally:
        lexicon.close()


def test_actual_translation_and_retained_model_latency():
    assert MODEL.is_dir() and PYTHON.is_file()
    started = perf_counter()
    translator = OpusMtTranslator(PYTHON, MODEL)
    init_seconds = perf_counter() - started
    rows, expected = [], {}
    for count in (1, 5, 10):
        samples, all_outputs = [], []
        for _ in range(3):
            started = perf_counter()
            values = []
            for offset in range(0, count, 2):
                values.extend(translator.translate(PHRASES[offset : min(offset + 2, count)]))
            samples.append(perf_counter() - started)
            assert len(values) == count
            all_outputs.append(values)
        assert all(value == all_outputs[0] for value in all_outputs)
        expected[count] = all_outputs[0]
        rows.append(
            {
                "conditions": count,
                "seconds": timing(samples),
                "worker_calls_per_sample": (count + 1) // 2,
                "nonempty_translations": sum(bool(v) for v in all_outputs[0]),
            }
        )
        print(f"local translation timing completed: conditions={count}", flush=True)
    save(
        "current-adapter.json",
        {
            "adapter_initialization_seconds": init_seconds,
            "runtime_sha256": translator.sha256,
            "model_reloaded_each_call": True,
            "rows": rows,
        },
    )

    started = perf_counter()
    result = subprocess.run(
        [
            str(PYTHON),
            "-I",
            str(ROOT / "tools/condition_mt_benchmark.py"),
            str(MODEL),
            str(ROOT / "src/search_v2/opus_mt_worker.py"),
        ],
        input=json.dumps(PHRASES, ensure_ascii=False).encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=120,
        env={"PATH": os.defpath, "OMP_NUM_THREADS": "2", "HF_HUB_OFFLINE": "1"},
        check=False,
    )
    wall_seconds = perf_counter() - started
    assert result.returncode == 0
    assert len(result.stdout) < 65536
    observed = json.loads(result.stdout)
    assert len(observed["model_load_seconds"]) == 1
    assert observed["first_output"] == expected[1]
    retained = []
    for row in observed["rows"]:
        assert all(value == expected[row["count"]] for value in row["outputs"])
        retained.append({"conditions": row["count"], "seconds": timing(row["seconds"])})
    save(
        "retained-model.json",
        {
            "subprocess_wall_seconds": wall_seconds,
            "native_import_seconds": observed["import_seconds"],
            "first_call_seconds": observed["first_call_seconds"],
            "model_load_seconds": observed["model_load_seconds"][0],
            "rows": retained,
            "outputs_match_current_adapter": True,
            "benchmark_sha256": hashlib.sha256(
                (ROOT / "tools/condition_mt_benchmark.py").read_bytes()
            ).hexdigest(),
            "production_implementation": False,
        },
    )
