"""Predeclared cross-category expectations and opt-in, single-call live tests."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from src.search_v2.bonsai_adapter import parse_bonsai_intent_response
from src.search_v2.bonsai_request import load_bonsai_intent_prompt
from tools.bonsai_inference_examples import EXAMPLES, judge_example, project_example, run_example
from test_search_v2_bonsai_compact import response_bytes


def judge_payload(example, payload):
    intent = parse_bonsai_intent_response(
        source_input=example.source,
        prompt=load_bonsai_intent_prompt(),
        response=response_bytes(payload),
    )
    return judge_example(intent, example)


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda e: e.case_id)
def test_declared_expectations_are_supported_by_the_adapter(example):
    payload = example.payload()
    assert all(judge_payload(example, payload).values())
    projection = project_example(response_bytes(payload), example)
    assert projection["stage"] == "draft_valid"
    assert all(projection["checks"].values())


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda e: e.case_id)
def test_omitted_condition_is_not_a_pass(example):
    payload = deepcopy(example.payload())
    payload["typed_conditions"].pop()
    assert not all(judge_payload(example, payload).values())


@pytest.mark.parametrize("mutation", ["strength", "value", "meaning", "unit"])
def test_corrupted_condition_is_not_a_pass(mutation):
    example = EXAMPLES[1]
    payload = example.payload()
    capacity = payload["typed_conditions"][1]
    if mutation == "strength":
        capacity["strength"] = "preferred"
    elif mutation == "value":
        capacity["expected_value"]["minimum"] = 999
    elif mutation == "unit":
        capacity["expected_value"]["unit"] = "mm"
    else:
        capacity["attribute_definition"]["meaning"] = "商品の重量"
    assert not all(judge_payload(example, payload).values())


@pytest.mark.live_api
@pytest.mark.bonsai_e2e
@pytest.mark.parametrize("example", EXAMPLES, ids=lambda e: e.case_id)
def test_local_bonsai_on_new_examples(pytestconfig, example):
    if not pytestconfig.getoption("--run-bonsai-attribute-inference"):
        pytest.skip("requires attribute inference live opt-in")
    from tools.bonsai_live_e2e import BonsaiLiveE2EConfig

    config = BonsaiLiveE2EConfig(
        server_binary=Path(pytestconfig.getoption("--bonsai-server-bin")),
        model_path=Path(pytestconfig.getoption("--bonsai-model-path")),
        port=pytestconfig.getoption("--bonsai-e2e-port"),
    )
    root = Path(pytestconfig.getoption("--bonsai-response-log-dir"))
    try:
        result = run_example(config, log_dir=root / example.case_id, example=example)
    except Exception:
        pytest.fail("Bonsai examples probe failed; inspect private logs", pytrace=False)
    print(json.dumps({"case_id": example.case_id, **result}, sort_keys=True), flush=True)
    if not all(result["checks"].values()):
        pytest.fail("Bonsai example did not meet the predeclared criteria", pytrace=False)


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda e: e.case_id)
def test_oracle_accepts_complete_model_proposals_before_grounding(example):
    projection = project_example(response_bytes(example.payload()), example)
    assert all(projection["checks"].values())


def test_equivalent_inch_unit_survives_grounding_and_evaluation():
    example = EXAMPLES[3]
    payload = example.payload()
    size = payload["typed_conditions"][1]
    size["attribute_definition"]["source_quote"] = "27インチ以上"
    size["expected_value"] = {"value_type": "decimal", "minimum": "27.000000", "unit": "inch"}
    checks = judge_payload(example, payload)
    assert {key for key, passed in checks.items() if not passed} == {
        "proposal_ready",
        "exact_requirement_count",
        "custom_attributes",
    }
    assert all(project_example(response_bytes(payload), example)["checks"].values())


def test_wrong_unit_scale_does_not_pass_as_inches():
    example = EXAMPLES[3]
    payload = example.payload()
    payload["typed_conditions"][1]["expected_value"]["unit"] = "cm"
    assert not all(judge_payload(example, payload).values())


def test_external_sound_cancellation_is_a_valid_meaning():
    example = EXAMPLES[2]
    payload = example.payload()
    payload["typed_conditions"][-1]["attribute_definition"]["meaning"] = (
        "外部の音をキャンセリングする機能があるか"
    )
    assert all(judge_payload(example, payload).values())


def test_negated_cancellation_meaning_does_not_pass():
    example = EXAMPLES[2]
    payload = example.payload()
    payload["typed_conditions"][-1]["attribute_definition"]["meaning"] = (
        "ノイズキャンセリングしない機能"
    )
    assert not all(judge_payload(example, payload).values())


def test_equivalent_hours_unit_survives_grounding():
    example = EXAMPLES[2]
    payload = example.payload()
    payload["typed_conditions"][1]["expected_value"]["unit"] = "hours"
    assert all(judge_payload(example, payload).values())


def test_repellent_definition_can_describe_preventing_surface_wetting():
    example = EXAMPLES[1]
    payload = example.payload()
    payload["typed_conditions"][-1]["attribute_definition"]["meaning"] = (
        "商品が水に濡れることを防ぐ機能"
    )
    assert all(judge_payload(example, payload).values())


def test_repellent_definition_cannot_promise_underwater_protection():
    example = EXAMPLES[1]
    payload = example.payload()
    payload["typed_conditions"][-1]["attribute_definition"]["meaning"] = (
        "撥水により水中での浸水を防ぐ機能"
    )
    assert not all(judge_payload(example, payload).values())
