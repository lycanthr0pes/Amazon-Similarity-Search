"""Separate first-exposure measurements; do not mix them with development scores."""

import json
from pathlib import Path

import pytest

from tools.bonsai_name_holdout import CASES
from tools.bonsai_unseen_categories import judge, run_case
from test_bonsai_unseen_categories import parse, assert_reference_held


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_reference_and_wrong_property(case):
    assert_reference_held(case)
    wrong = case.payload()
    wrong["typed_conditions"][0]["attribute_definition"]["label"] = "価格"
    wrong["typed_conditions"][0]["attribute_definition"]["meaning"] = "商品の価格"
    assert not all(judge(parse(case, wrong), case).values())


@pytest.mark.live_api
@pytest.mark.bonsai_e2e
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_local_bonsai_name_holdout(pytestconfig, case):
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
        pytest.fail("Name-only holdout probe failed; inspect private logs", pytrace=False)
    print(json.dumps({"case_id": case.case_id, **result}, sort_keys=True), flush=True)
    if not all(result["checks"].values()):
        pytest.fail("Name-only holdout failed frozen criteria", pytrace=False)
