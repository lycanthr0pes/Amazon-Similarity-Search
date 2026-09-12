"""Measure actual OPUS-MT with one retained model, isolated from production."""

import json
from pathlib import Path
import runpy
import sys
from time import perf_counter


def measure(root, worker, phrases):
    started = perf_counter()
    import ctranslate2

    import_seconds = perf_counter() - started
    translate = runpy.run_path(str(worker))["translate"]
    constructor = ctranslate2.Translator
    models = []
    load_times = []

    def retained_model(*args, **kwargs):
        if not models:
            started = perf_counter()
            models.append(constructor(*args, **kwargs))
            load_times.append(perf_counter() - started)
        return models[0]

    ctranslate2.Translator = retained_model
    try:
        started = perf_counter()
        first = translate(root, phrases[:1])
        cold_seconds = perf_counter() - started
        rows = []
        for count in (1, 5, 10):
            runs, outputs = [], []
            for _ in range(3):
                started = perf_counter()
                values = []
                for offset in range(0, count, 2):
                    values.extend(translate(root, phrases[offset : min(offset + 2, count)]))
                runs.append(perf_counter() - started)
                outputs.append(values)
            rows.append({"count": count, "seconds": runs, "outputs": outputs})
        return {
            "import_seconds": import_seconds,
            "first_call_seconds": cold_seconds,
            "model_load_seconds": load_times,
            "first_output": first,
            "rows": rows,
        }
    finally:
        ctranslate2.Translator = constructor


if __name__ == "__main__":
    try:
        phrases = json.loads(sys.stdin.buffer.read(4096))
        if not isinstance(phrases, list) or len(phrases) != 10:
            raise ValueError("Invalid benchmark input")
        result = measure(Path(sys.argv[1]), Path(sys.argv[2]), phrases)
        # Actual translations are IPC only; the parent writes numeric summaries.
        print(json.dumps(result, ensure_ascii=False))
    except Exception:
        raise SystemExit(1) from None
