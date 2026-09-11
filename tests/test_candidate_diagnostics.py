"""Synthetic diagnostics retain rejection boundaries without retaining provider text."""

from contextlib import nullcontext
from dataclasses import replace
import json

import pytest

from src.search_v2.bonsai_visual_conditions import parse_visual_response
from src.search_v2.bonsai_request import BonsaiHttpResponse
import test_candidate_search_live_e2e as live


SOURCE = "マグカップ。丸みのある形。高級感を希望。3000円以下。"
ROW = {"source_phrase": "丸みのある形", "strength": "required", "attribute_key": None}


def response(payload=None, **choice):
    data = {"status": "ready", "conditions": [ROW]} if payload is None else payload
    return json.dumps(
        {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(data)}, **choice}]}
    ).encode()


CASES = [
    (b"", "response_size"),
    (b"\xff", "envelope_json"),
    (b"not-json", "envelope_json"),
    (b'{"choices":[],"choices":[]}', "envelope_json"),
    (b"{}", "envelope_shape"),
    (b'{"choices":[null]}', "envelope_shape"),
    (response(finish_reason="length"), "finish_reason"),
    (response(message={"content": None}), "content_type"),
    (response(message={"content": "private-provider-sentinel"}), "content_json"),
    (
        response({"status": "ready", "conditions": [], "extra": "private-provider-sentinel"}),
        "payload_shape",
    ),
    (response({"status": "needs_clarification", "conditions": []}), "needs_clarification"),
    (response({"status": "private-provider-sentinel", "conditions": []}), "status_value"),
    (response({"status": "ready", "conditions": None}), "conditions_shape"),
    (response({"status": "ready", "conditions": [ROW] * 4}), "condition_count"),
    (
        response({"status": "ready", "conditions": [{"extra": "private-provider-sentinel"}]}),
        "draft_shape",
    ),
    (
        response(
            {"status": "ready", "conditions": [{**ROW, "strength": "private-provider-sentinel"}]}
        ),
        "draft_validation",
    ),
    (
        response({"status": "ready", "conditions": [{**ROW, "source_phrase": "木目調"}]}),
        "condition_binding",
    ),
    (
        response({"status": "ready", "conditions": [{**ROW, "attribute_key": "dimensions.width"}]}),
        "condition_binding",
    ),
    (response({"status": "ready", "conditions": [ROW, ROW]}), "condition_binding"),
    (
        response({"status": "ready", "conditions": [{**ROW, "source_phrase": "3000円以下"}]}),
        "clause_scope",
    ),
    (
        response({"status": "ready", "conditions": [{**ROW, "source_phrase": "丸み"}]}),
        "clause_scope",
    ),
    (
        response({"status": "ready", "conditions": [{**ROW, "source_phrase": "高級感を希望"}]}),
        "condition_strength",
    ),
]


@pytest.mark.parametrize("raw,code", CASES)
def test_parser_reports_a_fixed_rejection_code(raw, code):
    with pytest.raises(ValueError) as caught:
        parse_visual_response(SOURCE, raw)
    diagnostic = getattr(caught.value, "diagnostic", None)
    assert diagnostic is not None
    assert diagnostic.model_dump() == {"schema_version": "1.0", "code": code}
    assert "private-provider-sentinel" not in str(caught.value)


def test_empty_response_remains_valid_for_candidate_only():
    assert parse_visual_response(SOURCE, response({"status": "ready", "conditions": []})) is None
    assert len(parse_visual_response(SOURCE, response()).conditions) == 1


@pytest.mark.parametrize(
    "raw,code", CASES + [(response({"status": "ready", "conditions": []}), "empty_conditions")]
)
def test_diagnostic_survives_candidate_and_reaches_safe_summary(tmp_path, monkeypatch, raw, code):
    m, config, services, _, _ = live.setup_run(tmp_path, monkeypatch)
    # An empty result may reach the image-only guard only if retrieval itself is valid.
    monkeypatch.setattr(
        m, "SYNTHETIC_INPUT", "マグカップ。" if code == "empty_conditions" else SOURCE
    )

    class Transport:
        def post_json(self, **kwargs):
            return BonsaiHttpResponse(200, "application/json", len(raw), None, (raw,))

    result = m.run_candidate_e2e(
        config,
        replace(services, bonsai_session=lambda: nullcontext(Transport())),
        image_score_mode="appearance",
    )
    assert result["status"] == "failed"
    assert result["failure_diagnostic"] == {"schema_version": "1.0", "code": code}
    assert result["cloudflare_calls"] == 0 and result["outscraper_tasks"] == 0
    saved = (config.output_dir / "summary.json").read_text()
    assert json.loads(saved) == result
    assert "private-provider-sentinel" not in saved and SOURCE not in saved


@pytest.mark.parametrize(
    "mode,code", [("transport", "transport"), ("http", "http_status"), ("body", "http_response")]
)
def test_http_failures_are_distinct_and_sanitized(tmp_path, monkeypatch, mode, code):
    m, config, services, _, _ = live.setup_run(tmp_path, monkeypatch)

    class Transport:
        def post_json(self, **kwargs):
            if mode == "transport":
                raise RuntimeError("private-provider-sentinel")
            raw = b"private-provider-sentinel"
            return BonsaiHttpResponse(
                503 if mode == "http" else 200, "text/plain", len(raw), None, (raw,)
            )

    result = m.run_candidate_e2e(
        config,
        replace(services, bonsai_session=lambda: nullcontext(Transport())),
        image_score_mode="appearance",
    )
    assert result["failure_diagnostic"]["code"] == code
    for path in config.output_dir.glob("*.json"):
        assert "private-provider-sentinel" not in path.read_text()


def test_unrelated_constructor_error_has_a_fixed_fallback(tmp_path, monkeypatch):
    m, config, services, _, _ = live.setup_run(tmp_path, monkeypatch)

    def fail(*args, **kwargs):
        raise RuntimeError("private-provider-sentinel")

    monkeypatch.setattr(m, "CandidateSearchFlow", fail)
    result = m.run_candidate_e2e(config, services, image_score_mode="appearance")
    assert result["failure_diagnostic"]["code"] == "unexpected"
    assert "private-provider-sentinel" not in json.dumps(result)


@pytest.mark.parametrize(
    "fault,code",
    [("request", "request_build"), ("query", "query_build"), ("limits", "plan_limits")],
)
def test_preparation_failures_after_or_before_parser_are_identified(
    tmp_path, monkeypatch, fault, code
):
    import src.search_v2.candidate_search as search

    m, config, services, _, _ = live.setup_run(tmp_path, monkeypatch)

    def fail(*args, **kwargs):
        raise ValueError("private-provider-sentinel")

    if fault in {"request", "query"}:
        monkeypatch.setattr(
            search,
            "build_visual_request" if fault == "request" else "build_candidate_queries",
            fail,
        )
    else:
        from types import SimpleNamespace

        monkeypatch.setattr(
            m,
            "CandidateSearchFlow",
            lambda *a, **kw: SimpleNamespace(
                plan=SimpleNamespace(visual_conditions=SimpleNamespace(conditions=(1, 2)))
            ),
        )
    result = m.run_candidate_e2e(config, services, image_score_mode="appearance")
    assert result["failure_diagnostic"]["code"] == code
    assert result["cloudflare_calls"] == 0 and result["outscraper_tasks"] == 0
    assert "private-provider-sentinel" not in json.dumps(result)


@pytest.mark.parametrize(
    "injected",
    [
        "private-provider-sentinel",
        {"schema_version": "1.0", "code": "private-provider-sentinel"},
        {"code": "transport", "source": "private-provider-sentinel"},
    ],
)
def test_forged_diagnostic_does_not_leak_to_summary(tmp_path, monkeypatch, injected):
    from src.search_v2.candidate_diagnostics import CandidatePreparationError

    m, config, services, _, _ = live.setup_run(tmp_path, monkeypatch)

    def fail(*args, **kwargs):
        error = CandidatePreparationError("transport")
        error.diagnostic = injected
        raise error

    monkeypatch.setattr(m, "CandidateSearchFlow", fail)
    result = m.run_candidate_e2e(config, services, image_score_mode="appearance")
    assert result["failure_diagnostic"]["code"] == "unexpected"
    assert "private-provider-sentinel" not in json.dumps(result)
