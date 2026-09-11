"""Bonsai does not score products in the candidate flow."""

import inspect
import json

import pytest

import test_candidate_search as candidate
import test_candidate_search_live_e2e as live
from src.search_v2.candidate_flow import CandidateSearchFlow
from src.search_v2.candidate_search import CandidateRanking, CandidateSearch
from src.search_v2.provisional_history_repository import ProvisionalHistoryWrite


def ranked(root, source="スキャナー", products=None):
    service = candidate.direct_start(source)
    review, _ = candidate.retrieve(service, root, products)
    service.confirm(
        owner_id="owner-1", review_sha256=review.sha256, selections={}, now=candidate.flow.NOW
    )
    return service.rank(owner_id="owner-1", now=candidate.flow.NOW)


@pytest.mark.parametrize(
    "method,argument",
    [
        (CandidateSearch.rank, "bonsai"),
        (CandidateSearchFlow.complete, "bonsai"),
        (CandidateSearch.approve_and_fetch, "extractor"),
        (CandidateSearchFlow.approve_and_fetch, "extractor"),
    ],
)
def test_nonvisual_stages_have_no_llm_injection(method, argument):
    assert argument not in inspect.signature(method).parameters


def test_title_match_orders_equal_conditions_without_inference(tmp_path):
    result = ranked(tmp_path, products=[{"name": "収納ケース"}, {"name": "スキャナー"}])
    assert [p.product.title for p in result.products] == ["スキャナー", "収納ケース"]
    assert [p.lexical_score for p in result.products] == [1.0, 0.0]
    assert result.profile_id == "candidate-confirmed-lexical-v3"
    assert "semantic_score" not in result.model_dump_json()
    assert "bonsai_request_sha256" not in result.model_dump_json()
    assert CandidateRanking.model_validate_json(result.model_dump_json()) == result


def test_title_match_cannot_override_budget_or_unknown_price(tmp_path):
    result = ranked(
        tmp_path,
        "スキャナー。1000円以下。",
        [
            {"name": "スキャナー", "price": 2000, "currency": "JPY"},
            {"name": "商品", "price": 900, "currency": "JPY"},
            {"name": "スキャナー"},
        ],
    )
    assert [p.product.provenance.response_index for p in result.products] == [1, 2, 0]
    assert [p.evaluation.required_status for p in result.products] == [
        "confirmed",
        "uncertain",
        "contradicted",
    ]
    assert [p.lexical_score for p in result.products] == [0.0, 1.0, 1.0]


def test_connected_entry_uses_bonsai_only_before_images(tmp_path, monkeypatch):
    module, config, services, events, _ = live.setup_run(tmp_path, monkeypatch)
    result = module.run_candidate_e2e(config, services, image_score_mode="appearance")
    assert result["status"] == "succeeded"
    assert result["bonsai_calls"] == 1
    assert events == [("reference", 1, 1), ("search", 2, 1)]
    assert result["ranking_profile_id"] == "candidate-appearance-v1"
    assert result["lexical_scored_products"] == 4
    assert result["history_images_verified"] == 2
    assert not (config.output_dir / "bonsai-response-2.json").exists()


@pytest.mark.parametrize(
    "profile",
    ["candidate-semantic-clip-v1", "candidate-lexical-clip-v2", "candidate-lexical-clip-v3"],
)
def test_history_accepts_old_and_new_profiles_without_quality_claim(tmp_path, profile):
    from test_search_v2_provisional_history_repository import NOW, pending
    from src.search_v2.provisional_history_repository import SqliteProvisionalHistoryRepository

    value = pending().model_copy(
        update={
            "ranking_profile_id": profile,
            "known_holdout_accuracy": None,
            "provisional_profile_id": "counterfactual-relative-v1"
            if profile == "candidate-lexical-clip-v3"
            else "counterfactual-v4-provisional-production-v1",
        }
    )
    value = ProvisionalHistoryWrite.model_validate(value)
    path = tmp_path / "history.sqlite3"
    saved = SqliteProvisionalHistoryRepository(path).save(value, now=NOW)
    restored = SqliteProvisionalHistoryRepository(path).get(
        owner_id="owner-1", locator=saved.locator, now=NOW
    )
    assert restored.ranking_profile_id == profile
    assert restored.known_holdout_accuracy is None
    assert restored.products == value.products


@pytest.mark.parametrize("mutation", ["legacy_profile", "legacy_score", "score_range"])
def test_new_result_rejects_legacy_or_invalid_scoring(tmp_path, mutation):
    result = ranked(tmp_path)
    payload = json.loads(result.model_dump_json())
    if mutation == "legacy_profile":
        payload["profile_id"] = "candidate-confirmed-observations-v1"
    elif mutation == "legacy_score":
        payload["products"][0]["semantic_score"] = 1.0
    else:
        payload["products"][0]["lexical_score"] = 1.1
    with pytest.raises(ValueError):
        CandidateRanking.model_validate_json(json.dumps(payload))
