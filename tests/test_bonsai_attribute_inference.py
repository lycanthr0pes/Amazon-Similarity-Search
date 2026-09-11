"""A fixed live inference probe has an independently tested semantic acceptance check."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from src.search_v2.bonsai_adapter import parse_bonsai_intent_response
from src.search_v2.bonsai_request import load_bonsai_intent_prompt
from test_search_v2_bonsai_compact import response_bytes


SOURCE = "白いマグカップ。350ml以上で、食洗機対応。"


def candidate_payload():
    return {
        "product_name_ja": "マグカップ",
        "typed_conditions": [
            {
                "attribute_key": "appearance.color",
                "operator": "equals",
                "expected_value": {"value_type": "enum", "values": ["white"]},
                "strength": "required",
            },
            {
                "attribute_key": "custom",
                "attribute_definition": {
                    "label": "容量",
                    "meaning": "容器に入る液体の容量",
                    "source_quote": "350ml以上",
                },
                "operator": "at_least",
                "expected_value": {"value_type": "decimal", "minimum": "350", "unit": "ml"},
                "strength": "required",
            },
            {
                "attribute_key": "custom",
                "attribute_definition": {
                    "label": "食洗機対応",
                    "meaning": "食洗機で洗えるかどうか",
                    "source_quote": "食洗機対応",
                },
                "operator": "equals",
                "expected_value": {"value_type": "boolean", "value": True},
                "strength": "required",
            },
        ],
    }


def probe_module():
    assert importlib.util.find_spec("tools.bonsai_attribute_inference") is not None, (
        "the single-call attribute inference probe is required"
    )
    from tools import bonsai_attribute_inference

    return bonsai_attribute_inference


def judge(payload):
    intent = parse_bonsai_intent_response(
        source_input=SOURCE,
        prompt=load_bonsai_intent_prompt(),
        response=response_bytes(payload),
    )
    return probe_module().judge_inference(intent)


def assert_unverified_identity_checks(checks):
    # Preserve the old quality oracle: withholding execution is not a semantic pass.
    failed = {key for key, passed in checks.items() if not passed}
    assert failed == {"proposal_ready", "exactly_three_conditions", "two_search_local_attributes"}


def test_plausible_inference_is_held_without_exporting_model_text():
    checks = judge(candidate_payload())
    assert_unverified_identity_checks(checks)
    assert all(type(value) is bool for value in checks.values())
    assert SOURCE not in json.dumps(checks, ensure_ascii=False)


@pytest.mark.parametrize(
    "mutation", ["missing", "label", "meaning", "unit", "bound", "operator", "strength", "boolean"]
)
def test_incorrect_inference_fails_semantic_acceptance(mutation):
    payload = deepcopy(candidate_payload())
    capacity = payload["typed_conditions"][1]
    if mutation == "missing":
        payload["typed_conditions"].pop()
    elif mutation == "label":
        capacity["attribute_definition"]["label"] = "重量"
    elif mutation == "meaning":
        capacity["attribute_definition"]["meaning"] = "商品の重量"
    elif mutation == "unit":
        capacity["expected_value"]["unit"] = "g"
    elif mutation == "bound":
        capacity["expected_value"]["minimum"] = "500"
    elif mutation == "operator":
        capacity["operator"] = "at_most"
        capacity["expected_value"] = {"value_type": "decimal", "maximum": "350", "unit": "ml"}
    elif mutation == "strength":
        capacity["strength"] = "preferred"
    else:
        payload["typed_conditions"][2]["expected_value"]["value"] = False
    assert not all(judge(payload).values())


@pytest.mark.live_api
@pytest.mark.bonsai_e2e
def test_local_bonsai_infers_search_attributes(pytestconfig):
    if not pytestconfig.getoption("--run-bonsai-attribute-inference"):
        pytest.skip("requires the separately approved attribute inference opt-in")
    from tools.bonsai_live_e2e import BonsaiLiveE2EConfig

    probe = probe_module()
    try:
        config = BonsaiLiveE2EConfig(
            server_binary=Path(pytestconfig.getoption("--bonsai-server-bin")),
            model_path=Path(pytestconfig.getoption("--bonsai-model-path")),
            port=pytestconfig.getoption("--bonsai-e2e-port"),
        )
        result = probe.run_inference_probe(
            config, log_dir=Path(pytestconfig.getoption("--bonsai-response-log-dir"))
        )
    except Exception:
        pytest.fail("Bonsai attribute inference probe failed before safe result", pytrace=False)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True), flush=True)
    if not all(result["checks"].values()):
        pytest.fail("Bonsai attribute inference did not meet the fixed criteria", pytrace=False)


@pytest.mark.parametrize("fails", [False, True])
def test_probe_calls_once_and_leaves_server_cleanup_to_owner(tmp_path, monkeypatch, fails):
    from contextlib import contextmanager
    from types import SimpleNamespace

    probe = probe_module()
    events = []

    @contextmanager
    def owned(_config):
        events.append("start")
        try:
            yield None
        finally:
            events.append("stop")

    intent = parse_bonsai_intent_response(
        source_input=SOURCE,
        prompt=load_bonsai_intent_prompt(),
        response=response_bytes(candidate_payload()),
    )

    def execute(prepared, *, ledger, transport):
        events.append("call")
        assert prepared.request.endpoint == "http://127.0.0.1:18080/v1/chat/completions"
        assert ledger is not None
        if fails:
            raise RuntimeError("private fixture error")
        return (
            SimpleNamespace(intent=intent),
            SimpleNamespace(
                prompt_usage=SimpleNamespace(prompt_tokens=10),
                completion_tokens=20,
                response_bytes=400,
            ),
            100,
        )

    monkeypatch.setattr(probe, "owned_bonsai", owned)
    monkeypatch.setattr(probe.runtime, "_execute_request", execute)
    config = SimpleNamespace(port=18080, model_path=Path("/synthetic/Bonsai-8B.gguf"))
    if fails:
        with pytest.raises(RuntimeError, match="private fixture error"):
            probe.run_inference_probe(config, log_dir=tmp_path / "responses")
    else:
        result = probe.run_inference_probe(config, log_dir=tmp_path / "responses")
        assert_unverified_identity_checks(result["checks"])
        assert result["request_count"] == 1
        assert result["retry_count"] == 0
        assert result["server_stopped"] is True
    assert events == ["start", "call", "stop"]


@pytest.mark.parametrize("invalid", [False, True])
def test_probe_records_response_before_parsing_and_keeps_replay_data(
    tmp_path, monkeypatch, invalid
):
    from contextlib import nullcontext
    from types import SimpleNamespace
    import requests
    from test_bonsai_live_e2e import valid_response_metrics_bytes
    from test_search_v2_bonsai_http import make_response, RecordingSession

    probe = probe_module()
    envelope = json.loads(valid_response_metrics_bytes())
    payload = candidate_payload()
    payload = {"product_name_ja": "マグカップ", "attribute_names_ja": ["容量"]}
    envelope["choices"][0]["message"]["content"] = (
        "private invalid JSON" if invalid else json.dumps(payload, ensure_ascii=False)
    )
    body = json.dumps(envelope, ensure_ascii=False).encode()
    response, _ = make_response((body,), content_length=str(len(body)))
    session = RecordingSession(response)
    monkeypatch.setattr(requests, "Session", lambda: session)
    monkeypatch.setattr(probe, "owned_bonsai", lambda _config: nullcontext())
    config = SimpleNamespace(port=18080, model_path=Path("/synthetic/Bonsai-8B.gguf"))
    root = tmp_path / "response-log"
    if invalid:
        with pytest.raises(Exception):
            probe.run_inference_probe(config, log_dir=root)
    else:
        result = probe.run_inference_probe(config, log_dir=root)
        assert_unverified_identity_checks(result["checks"])
        saved = json.loads((root / "normalized-intent.json").read_text())
        assert len(saved["typed_conditions"]) == 3
    assert (root / "response-001.body").read_bytes() == body
    projection = json.loads((root / "model-projection.json").read_text())
    assert projection["stage"] == ("content_not_json" if invalid else "draft_valid")
    assert projection["typed_count"] == (None if invalid else 3)
    assert projection["custom_count"] == (None if invalid else 2)
    assert "private invalid JSON" not in json.dumps(projection)
    assert (root / "probe-result.json").is_file()
    assert len(session.request_calls) == 1
