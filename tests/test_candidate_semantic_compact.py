"""Compact wire preserves every product, score and source-bound citation."""

import json
from types import SimpleNamespace

from jsonschema import Draft202012Validator
import pytest

import test_candidate_semantic_schema as previous
from src.search_v2.candidate_semantics import build_semantic_request, parse_semantic_response
from tools import candidate_search_live_e2e as live
from src.search_v2.bonsai_request import BonsaiHttpResponse


def schema():
    return json.loads(build_semantic_request("丸み", previous.FIELDS, (), {}, (), (3, 9)))[
        "response_format"
    ]["schema"]


def test_compact_generation_and_restore_match_old_result():
    value = {"evaluations": [[0.8, [[0, 0, 2]]], [None, []]]}
    validator = Draft202012Validator(schema())
    assert validator.is_valid(value)
    restored = parse_semantic_response(previous.FIELDS, previous.envelope(value), (3, 9))
    old = parse_semantic_response(previous.FIELDS, previous.envelope(previous.payload()), (3, 9))
    assert restored == old
    assert len(json.dumps(value)) < len(json.dumps(previous.payload())) / 2


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [[0.8, [[2, 0, 2]]], [None, []]],
        [[0.8, [[True, 0, 2]]], [None, []]],
        [[0.8, [[99, 0, 2]]], [None, []]],
        [[0.8, [[0, 0, 9]]], [None, []]],
        [[None, [[0, 0, 2]]], [None, []]],
        [[0.8, []], [None, []]],
        [[0.8, [[0, 0, 2]], "extra"], [None, []]],
        [[0.8, [[0, 0, 2]]]],
        [[0.8, [[0, 0, 2]]], previous.payload()["assessments"][1]],
    ],
)
def test_compact_invalid_rows_rejected_by_schema_and_receiver(rows):
    value = {"evaluations": rows}
    assert not Draft202012Validator(schema()).is_valid(value)
    with pytest.raises(ValueError):
        parse_semantic_response(previous.FIELDS, previous.envelope(value), (3, 9))


def test_compact_input_keeps_all_text_and_order():
    request = json.loads(build_semantic_request("丸み", previous.FIELDS, (), {}, (), (3, 9)))
    body = json.loads(request["messages"][1]["content"])
    assert body["fields"] == [
        [i, f.product_index, f.kind, f.text] for i, f in enumerate(previous.FIELDS)
    ]
    assert body["product_indices"] == [3, 9]


@pytest.mark.parametrize("success", [True, False])
def test_bonsai_wall_time_is_saved_without_body(tmp_path, success):
    def post_json(**kwargs):
        if not success:
            raise RuntimeError("private-sentinel")
        body = previous.envelope(previous.payload())
        return BonsaiHttpResponse(200, "application/json", len(body), None, (body,))

    bonsai = live._Bonsai(SimpleNamespace(post_json=post_json), 18080, tmp_path)
    if success:
        bonsai.evaluate(b"{}")
    else:
        with pytest.raises(ValueError):
            bonsai.evaluate(b"{}")
    path = tmp_path / "bonsai-timing-1.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["wall_milliseconds"] >= 0
    assert data["response_received"] is success
    assert data["model_metrics"] is None
    assert "private-sentinel" not in path.read_text()


def test_bonsai_model_timings_project_only_validated_metadata(tmp_path):
    body = json.dumps(
        {
            "choices": [{"finish_reason": "stop", "message": {"content": "private-sentinel"}}],
            "usage": {
                "prompt_tokens": 10,
                "prompt_tokens_details": {"cached_tokens": 2},
                "completion_tokens": 3,
                "total_tokens": 13,
            },
            "timings": {
                "prompt_n": 8,
                "cache_n": 2,
                "predicted_n": 3,
                "prompt_ms": 100.0,
                "predicted_ms": 200.0,
            },
        }
    ).encode()
    transport = SimpleNamespace(
        post_json=lambda **_: BonsaiHttpResponse(200, "application/json", len(body), None, (body,))
    )
    live._Bonsai(transport, 18080, tmp_path).evaluate(b"{}")
    path = tmp_path / "bonsai-timing-1.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["model_metrics"]["prompt_milliseconds"] == 100.0
    assert data["model_metrics"]["completion_tokens"] == 3
    assert "private-sentinel" not in path.read_text()
