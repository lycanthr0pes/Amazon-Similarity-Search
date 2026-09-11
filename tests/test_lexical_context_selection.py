"""Pair comparison and Bonsai fallback select IDs, never invent query terms."""

import json
from types import SimpleNamespace

import numpy as np
import pytest

from src.search_v2.lexical_selection import LexicalSense


def senses():
    return (
        LexicalSense(
            "wn:tool",
            "wordnet",
            ("ドライバー",),
            ("screwdriver",),
            "tool",
            definitions_ja=("ねじを回す手工具",),
        ),
        LexicalSense(
            "wn:club",
            "wordnet",
            ("ドライバー",),
            ("driver",),
            "club",
            definitions_ja=("ゴルフクラブ",),
        ),
    )


def envelope(value):
    return json.dumps(
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": json.dumps(value, ensure_ascii=False)},
                }
            ]
        }
    ).encode()


class Bonsai:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def evaluate(self, body):
        self.calls.append(body)
        return envelope(self.value)


def test_pair_scorer_reads_source_and_japanese_definition_together():
    from src.search_v2.lexical_context import OnnxSenseScorer

    class Tokenizer:
        def encode_batch(self, values):
            assert len(values) == 2
            assert all(v[0] == "ネジを締めるドライバー" for v in values)
            assert "ねじを回す手工具" in values[0][1]
            return [
                SimpleNamespace(ids=[1, 2], attention_mask=[1, 1], type_ids=[0, 1]) for _ in values
            ]

    class Session:
        def get_inputs(self):
            return [SimpleNamespace(name=n) for n in ("input_ids", "attention_mask")]

        def run(self, _, inputs):
            return [np.array([[4.0], [-4.0]])]

    scorer = OnnxSenseScorer.__new__(OnnxSenseScorer)
    scorer._tokenizer = Tokenizer()
    scorer._session = Session()
    values = scorer.scores("ネジを締めるドライバー", senses())
    assert values[0] > 0.98 and values[1] < 0.02


def test_bonsai_selects_existing_id_with_grounded_context_only():
    from src.search_v2.lexical_context import BonsaiSenseSelector

    model = Bonsai({"sense_id": "wn:tool", "evidence_index": 0})
    selector = BonsaiSenseSelector(model, "a" * 64)
    result = selector.select("ネジを締めるドライバーが欲しい。", "ドライバー", senses())
    assert result.sense == senses()[0]
    assert len(model.calls) == 1
    request = json.loads(model.calls[0])
    schema = request["response_format"]["schema"]
    assert schema["properties"]["sense_id"]["enum"] == [None, "wn:tool", "wn:club"]
    assert len(result.request_sha256) == len(result.response_sha256) == 64


@pytest.mark.parametrize(
    "payload",
    [
        {"sense_id": "new:invented", "evidence": "ネジを締める"},
        {"sense_id": "wn:tool", "evidence": "ゴルフで使う"},
        {"sense_id": "wn:tool", "evidence": "ドライバー"},
        {"sense_id": "wn:tool", "evidence": "ネジを締める", "translation": "drill"},
        {"sense_id": None, "evidence": "ネジを締める"},
    ],
)
def test_invalid_bonsai_selection_abstains_without_retry(payload):
    from src.search_v2.lexical_context import BonsaiSenseSelector

    model = Bonsai(payload)
    result = BonsaiSenseSelector(model, "a" * 64).select(
        "ネジを締めるドライバーが欲しい。", "ドライバー", senses()
    )
    assert result.sense is None
    assert len(model.calls) == 1


def test_no_context_means_no_bonsai_call():
    from src.search_v2.lexical_context import BonsaiSenseSelector

    model = Bonsai({"sense_id": "wn:tool", "evidence": "ドライバー"})
    assert (
        BonsaiSenseSelector(model, "a" * 64)
        .select("ドライバーを探しています。", "ドライバー", senses())
        .sense
        is None
    )
    assert model.calls == []
