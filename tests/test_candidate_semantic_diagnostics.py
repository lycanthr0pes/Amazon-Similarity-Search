"""Rejection reasons survive ranking boundaries without exposing provider text."""

import json
import sqlite3

import pytest

import test_candidate_connected_flow as connected
import test_candidate_search_live_e2e as live
import test_candidate_semantics as semantic
from src.search_v2.candidate_diagnostics import candidate_failure_diagnostic
from src.search_v2.candidate_semantics import parse_semantic_response
from tools.bonsai_response_log import write_private


def invalid_response(case):
    row = semantic.assessment()
    if case == "size":
        return b""
    if case == "json":
        return b"\xff"
    if case == "envelope":
        return b'{"choices":[null]}'
    if case == "finish":
        return b'{"choices":[{"finish_reason":"length"}]}'
    if case == "content_type":
        return b'{"choices":[{"finish_reason":"stop","message":{"content":null}}]}'
    if case == "content_json":
        return b'{"choices":[{"finish_reason":"stop","message":{"content":"private-sentinel"}}]}'
    if case == "payload":
        return semantic.envelope({"private-sentinel": []})
    if case == "count":
        return semantic.envelope({"assessments": []})
    if case == "row":
        row["private-sentinel"] = True
    if case == "index":
        row["product_index"] = 99
    if case == "score":
        row["score"] = True
    if case == "evidence":
        row["evidence"] = []
    span = row["evidence"][0] if row["evidence"] else {}
    if case == "span":
        span["private-sentinel"] = True
    if case == "field":
        span["field_id"] = "private-sentinel"
    if case == "owner":
        span["field_id"] = "p1-title"
    if case == "range":
        span["end"] = 99
    if case == "duplicate":
        row["evidence"] *= 2
    if case == "empty_quote":
        span.update(field_id="p0-blank", start=0, end=1)
    return semantic.envelope({"assessments": [row]})


CASES = [
    ("size", "semantic_response_size"),
    ("json", "semantic_envelope_json"),
    ("envelope", "semantic_envelope_shape"),
    ("finish", "semantic_finish_reason"),
    ("content_type", "semantic_content_type"),
    ("content_json", "semantic_content_json"),
    ("payload", "semantic_payload_shape"),
    ("count", "semantic_product_count"),
    ("row", "semantic_assessment_shape"),
    ("index", "semantic_product_index"),
    ("score", "semantic_score"),
    ("evidence", "semantic_evidence_shape"),
    ("span", "semantic_span_shape"),
    ("field", "semantic_field_binding"),
    ("owner", "semantic_field_owner"),
    ("range", "semantic_span_range"),
    ("duplicate", "semantic_span_duplicate"),
    ("empty_quote", "semantic_empty_quote"),
]


@pytest.mark.parametrize("case,code", CASES)
def test_semantic_rejection_has_fixed_reason(tmp_path, case, code):
    response = invalid_response(case)
    write_private(tmp_path / "response.json", response)
    fields = semantic.FIELDS + (
        semantic.ProductField(field_id="p0-blank", product_index=0, kind="title", text=" "),
    )
    with pytest.raises(ValueError, match="Invalid Bonsai semantic response") as caught:
        parse_semantic_response(fields, response, (0,))
    diagnostic = candidate_failure_diagnostic(caught.value)
    assert diagnostic.code == code
    assert "private-sentinel" not in diagnostic.model_dump_json()


def test_legacy_semantic_path_is_not_called_by_runner(tmp_path, monkeypatch):
    module, config, services, _, clips = live.setup_run(tmp_path, monkeypatch)

    def fail(*args, **kwargs):
        raise AssertionError("Legacy product inference must not run")

    monkeypatch.setattr("src.search_v2.candidate_semantics.build_semantic_request", fail)
    monkeypatch.setattr("src.search_v2.candidate_semantics.parse_semantic_response", fail)
    monkeypatch.setattr("src.search_v2.observed_attributes.build_extraction_request", fail)
    result = module.run_candidate_e2e(config, services, image_score_mode="appearance")
    assert result["status"] == "succeeded"
    assert result["bonsai_calls"] == 1 and result["outscraper_tasks"] == 1
    assert result["retry_count"] == 0
    # This fixture replaces the encoder runner, so observe its own calls.
    assert clips == [2, 4]
    assert "semantic_known" not in result
    with sqlite3.connect(config.output_dir / "history.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM provisional_history").fetchone()[0] == 1


@pytest.mark.parametrize(
    "target,code",
    [
        ("_requirements", "ranking_requirements"),
        ("_evaluate", "ranking_product_evaluation"),
        ("complete_candidate_ranking", "visual_evaluation"),
        ("candidate_history_snapshot", "history_snapshot"),
    ],
)
def test_completion_boundaries_are_distinguishable(tmp_path, monkeypatch, target, code):
    import src.search_v2.candidate_flow as flow_module
    from src.search_v2.candidate_search import CandidateSearch

    module, config, services, _, _ = live.setup_run(tmp_path, monkeypatch)

    def fail(*args, **kwargs):
        raise RuntimeError("private-sentinel")

    owner = CandidateSearch if target.startswith("_") else flow_module
    monkeypatch.setattr(owner, target, fail)
    result = module.run_candidate_e2e(config, services, image_score_mode="appearance")
    assert result["failure_diagnostic"]["code"] == code
    assert "private-sentinel" not in json.dumps(result)


def test_history_failure_keeps_retry_state_and_reason(tmp_path, monkeypatch):
    flow, images, _, history, _ = connected.start(tmp_path)
    connected.approve(flow)
    connected.fetch(flow, tmp_path)
    kwargs, calls = connected.clip(monkeypatch, tmp_path)
    save = history.save

    def fail(*args, **kwargs):
        raise RuntimeError("private-sentinel")

    monkeypatch.setattr(history, "save", fail)
    with pytest.raises(ValueError, match="Candidate history save failed") as caught:
        flow.complete(owner_id=connected.OWNER, **kwargs)
    assert candidate_failure_diagnostic(caught.value).code == "history_save"
    monkeypatch.setattr(history, "save", save)
    result = flow.retry_history(owner_id=connected.OWNER)
    assert result.history.products
    assert len(images.calls) == 2 and calls == [2, 4]


def test_invalid_diagnostic_metadata_is_not_exposed():
    from src.search_v2.candidate_diagnostics import CandidateEvaluationError

    error = CandidateEvaluationError("semantic_score")
    error.diagnostic = {"code": "semantic_score", "body": "private-sentinel"}
    assert candidate_failure_diagnostic(error).code == "unexpected"


def test_null_and_zero_scores_remain_distinct():
    zero = semantic.assessment()
    zero["score"] = 0.0
    unknown = {"product_index": 1, "score": None, "evidence": []}
    result = parse_semantic_response(
        semantic.FIELDS, semantic.envelope({"assessments": [zero, unknown]}), (0, 1)
    )
    assert result[0].score == 0.0 and result[1].score is None
