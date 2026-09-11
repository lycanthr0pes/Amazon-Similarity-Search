"""Frozen unseen-category oracle checks and separately opted-in live evaluation."""

from pathlib import Path
import json

import pytest

from src.search_v2.bonsai_adapter import parse_bonsai_intent_response
from src.search_v2.bonsai_request import load_bonsai_intent_prompt
from tools.bonsai_unseen_categories import CASES, judge, project, run_case
from test_search_v2_bonsai_compact import response_bytes


def parse(case, payload):
    return parse_bonsai_intent_response(
        source_input=case.source,
        prompt=load_bonsai_intent_prompt(),
        response=response_bytes(payload),
    )


def assert_reference_held(case):
    payload = case.payload()
    assert all(project(response_bytes(payload), case)["checks"].values())
    checks = judge(parse(case, payload), case)
    assert {key for key, passed in checks.items() if not passed} == {
        "proposal_ready",
        "exact_requirement_count",
        "custom_attributes",
    }


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_correct_fixture_has_full_coverage(case):
    payload = case.payload()
    assert all(project(response_bytes(payload), case)["checks"].values())
    if case.case_id == "microscope_1":
        assert_reference_held(case)
    else:
        assert all(judge(parse(case, payload), case).values())


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
@pytest.mark.parametrize("mutation", ["missing", "strength", "value", "meaning"])
def test_wrong_condition_is_not_success(case, mutation):
    payload = case.payload()
    condition = payload["typed_conditions"][-1]
    if mutation == "missing":
        payload["typed_conditions"].pop()
    elif mutation == "strength":
        condition["strength"] = "excluded" if condition["strength"] != "excluded" else "required"
    elif mutation == "value":
        condition["expected_value"]["value"] = False
    else:
        condition["attribute_definition"]["meaning"] = "商品の価格"
    assert not all(project(response_bytes(payload), case)["checks"].values())
    assert not all(judge(parse(case, payload), case).values())


@pytest.mark.parametrize("mutation", ["unit", "bound", "operator"])
def test_wrong_numeric_semantics_fail(mutation):
    case = CASES[-1]
    payload = case.payload()
    condition = payload["typed_conditions"][0]
    if mutation == "unit":
        condition["expected_value"]["unit"] = "g"
    elif mutation == "bound":
        condition["expected_value"]["maximum"] = 200
    else:
        condition["operator"] = "at_least"
        condition["expected_value"] = {"value_type": "integer", "minimum": 2, "unit": "kg"}
    assert not all(judge(parse(case, payload), case).values())


def test_unrequested_attribute_is_not_success():
    case = CASES[0]
    payload = case.payload()
    intent = parse(case, payload).model_copy(update={"required_terms_ja": ["高級"]})
    assert not judge(intent, case)["no_unrequested_fields"]


@pytest.mark.live_api
@pytest.mark.bonsai_e2e
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_local_bonsai_unseen_categories(pytestconfig, case):
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
        result = run_case(config, log_dir=root / case.case_id, case=case)
    except Exception:
        pytest.fail("Unseen-category probe failed; inspect private logs", pytrace=False)
    print(json.dumps({"case_id": case.case_id, **result}, sort_keys=True), flush=True)
    if not all(result["checks"].values()):
        pytest.fail("Unseen-category inference failed frozen criteria", pytrace=False)
