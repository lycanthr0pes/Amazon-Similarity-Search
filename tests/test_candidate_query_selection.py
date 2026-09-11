"""Review selects one query before any image/search approval."""

import json

import pytest

import test_bonsai_query_terms as terms
import test_candidate_search_live_e2e as live
import test_candidate_connected_flow as connected
from src.search_v2.candidate_search import CandidatePlan


@pytest.mark.parametrize("index", [0, 1, 2])
def test_reviewed_query_reaches_search_and_history(tmp_path, monkeypatch, index):
    module, config, services, events, clips = live.setup_run(tmp_path, monkeypatch)

    def select(review):
        assert events == []
        assert [q["value"] for q in review["queries"]] == ["マグカップ", "マグ", "mug"]
        assert review["maximum_candidates"] == 24
        return index

    result = module.run_candidate_e2e(
        config,
        services,
        select_query=select,
        lexical_expander=live.lexical_expander(),
        image_score_mode="appearance",
    )
    assert result["status"] == "succeeded"
    assert result["bonsai_calls"] == 1 and result["outscraper_tasks"] == 1
    assert events == [("reference", 1, 1), ("search", 2, 1)]
    assert clips == [2, 4]
    saved = json.loads((config.output_dir / "plan.json").read_bytes())
    assert saved["selected_query_index"] == index
    assert len(saved["request"]["queries"]) == 1
    assert saved["request"]["maximum_candidates"] == 24
    assert result["history_images_verified"] == 2
    assert saved["query_expansion"]["profile_id"] == "dictionary-query-terms-v1"
    assert saved["query_expansion"]["selected_sense_id"] == "fixture:mug"
    assert not (tmp_path / "query-request.json").exists()


@pytest.mark.parametrize("index", [True, -1, 7, "1"])
def test_bad_query_selection_never_reaches_images_or_search(tmp_path, monkeypatch, index):
    module, config, services, events, _ = live.setup_run(tmp_path, monkeypatch)
    result = module.run_candidate_e2e(
        config, services, select_query=lambda _: index, image_score_mode="appearance"
    )
    assert result["status"] == "failed"
    assert result["failure_stage"] == "query_selection"
    assert result["cloudflare_calls"] == result["outscraper_tasks"] == 0
    assert events == []


@pytest.mark.parametrize("change", ["status", "source", "selected", "options", "noncanonical"])
def test_saved_plan_rejects_inconsistent_query_suggestions(tmp_path, change):
    service, _, _ = terms.start(tmp_path)
    payload = json.loads(service.plan.model_dump_json())
    if change == "status":
        payload["query_expansion"]["status"] = "unavailable"
    elif change == "source":
        payload["query_expansion"]["source_sha256"] = "0" * 64
    elif change == "selected":
        payload["selected_query_index"] = 2
    elif change == "options":
        payload["query_options"][1]["value"] = "その他の商品"
    else:
        payload["query_expansion"]["terms"]["original_en"] = "SCANNER"
    with pytest.raises(ValueError):
        CandidatePlan.model_validate_json(json.dumps(payload))


def test_query_cannot_change_after_reference_generation(tmp_path):
    flow, *_ = connected.start(tmp_path)
    connected.reference(flow)
    old = flow.plan_sha256
    with pytest.raises(ValueError):
        flow.select_search_query(owner_id=connected.OWNER, plan_sha256=old, index=0)
    assert flow.plan_sha256 == old
