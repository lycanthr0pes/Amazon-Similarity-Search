"""Model-inferred labels are evaluated separately from source-preserved facts."""

import json
from pathlib import Path

import pytest

from tools.bonsai_source_holdout import CASES
from tools.bonsai_unseen_categories import judge, run_case
from test_bonsai_unseen_categories import parse, assert_reference_held


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_holdout_reference_requires_identity_review(case):
    assert_reference_held(case)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_wrong_inferred_property_is_not_accepted(case):
    payload = case.payload()
    payload["typed_conditions"][0]["attribute_definition"]["label"] = "価格"
    payload["typed_conditions"][0]["attribute_definition"]["meaning"] = "商品の価格"
    assert not all(judge(parse(case, payload), case).values())


@pytest.mark.live_api
@pytest.mark.bonsai_e2e
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_local_bonsai_omitted_names(pytestconfig, case):
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
        pytest.fail("Omitted-name probe failed; inspect private logs", pytrace=False)
    print(json.dumps({"case_id": case.case_id, **result}, sort_keys=True), flush=True)
    if not all(result["checks"].values()):
        pytest.fail("Omitted-name inference failed frozen criteria", pytrace=False)
