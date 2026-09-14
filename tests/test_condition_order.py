"""Earlier source conditions carry more weight within their own strength."""

import pytest

from test_candidate_text_scoring import search, rank
from test_candidate_bilingual_scoring import search as bilingual_search
from src.search_v2.candidate_image_free import complete_image_free


def test_saved_plan_rejects_changed_source_positions():
    import test_candidate_search as candidate
    from src.search_v2.candidate_search import CandidateSearch, _digest
    from src.search_v2.condition_weighting import ConditionWeighting

    source = "マグカップ。電子レンジ対応。食洗機対応。"
    service = search(source)
    positions = service.plan.condition_weighting.positions
    changed = ConditionWeighting(positions=tuple((cid, 0) for cid, _ in positions))
    plan = service.plan.model_copy(update={"condition_weighting": changed})
    with pytest.raises(ValueError, match="positions changed"):
        CandidateSearch.from_approved_plan(
            plan,
            source=source,
            owner_id="owner-1",
            plan_sha256=_digest(plan),
            human_confirmed=True,
            normalization_profile=candidate.flow.backend_policy().normalization_profile,
            now=candidate.flow.NOW,
        )


def test_price_uses_source_position_even_though_it_is_appended_last(tmp_path):
    result = rank(
        search("マグカップ。3000円以下。電子レンジ対応。"),
        tmp_path,
        [
            {"name": "マグカップ", "price": 2000, "currency": "JPY"},
        ],
    )
    score = result.products[0].text_score
    assert score.required_ratio == pytest.approx(2 / 3, abs=1e-6)
    assert {r.requirement_id: r.weight for r in score.conditions}["condition-price"] == 2


def test_bilingual_visual_conditions_share_source_order_with_typed_conditions(tmp_path):
    from src.search_v2.candidate_search import CandidateSearch
    from src.search_v2.condition_terms import LocalConditionExpander
    import test_candidate_search as candidate

    service = CandidateSearch(
        "マグカップ。丸い形。電子レンジ対応。",
        owner_id="owner-1",
        session_id="mixed",
        postal_code="100-0001",
        normalization_profile=candidate.flow.backend_policy().normalization_profile,
        now=candidate.flow.NOW,
        image_mode="off",
        condition_expander=LocalConditionExpander(),
    )
    result = rank(service, tmp_path, [{"name": "マグカップ", "description": "丸い形。"}])
    rows = result.products[0].text_score.conditions
    assert [r.weight for r in rows] == [1, 2, 2]
    assert result.products[0].text_score.required_ratio == 0.8


def test_english_maximum_is_selected_before_weighting(tmp_path):
    service = bilingual_search("マグカップ。電子レンジ対応。容量400ml以上。")[0]
    result = rank(
        service,
        tmp_path,
        [
            {
                "name": "マグカップ",
                "description_en": "Microwave safe. Capacity: 200 ml.",
                "details_en_status": "available",
            }
        ],
    )
    score = result.products[0].text_score
    assert score.conditions[0].score_ja == 0.0
    assert score.conditions[0].score_en == score.conditions[0].score == 1.0
    assert score.required_ratio == pytest.approx(2 / 3, abs=1e-6)


def test_each_strength_has_its_own_weights_and_missing_scores_stay_in_denominator(tmp_path):
    result = rank(
        search("マグカップ。容量400ml以上が希望。電子レンジ対応。食洗機対応。"),
        tmp_path,
        [
            {"name": "マグカップ", "description": "電子レンジで温められます。"},
        ],
    )
    score = result.products[0].text_score
    assert [r.weight for r in score.conditions] == [1, 2, 1]
    assert score.required_ratio == pytest.approx(2 / 3, abs=1e-6)
    assert score.preferred_ratio == 0.0


@pytest.mark.parametrize("bilingual", [False, True])
def test_legacy_plan_keeps_unweighted_scores_and_serialization(tmp_path, bilingual):
    import test_candidate_search as candidate
    from src.search_v2.candidate_search import CandidateSearch, CandidateRanking, _digest
    from src.search_v2.candidate_image_free import image_free_history, PROFILE_HASH

    source = "マグカップ。電子レンジ対応。食洗機対応。"
    service = bilingual_search(source)[0] if bilingual else search(source)
    plan = service.plan.model_copy(update={"condition_weighting": None})
    resumed = CandidateSearch.from_approved_plan(
        plan,
        source=source,
        owner_id="owner-1",
        plan_sha256=_digest(plan),
        human_confirmed=True,
        normalization_profile=candidate.flow.backend_policy().normalization_profile,
        now=candidate.flow.NOW,
    )
    result = rank(
        resumed, tmp_path, [{"name": "マグカップ", "description": "電子レンジで温められます。"}]
    )
    assert result.products[0].text_score.required_ratio == 0.5
    wire = result.model_dump_json()
    assert "condition_weighting" not in wire and '"weight"' not in wire
    assert CandidateRanking.model_validate_json(wire).model_dump_json() == wire
    saved = image_free_history(
        complete_image_free(result), source_text=source, completed_at=candidate.flow.NOW
    )
    assert "condition_weighting" not in saved.model_dump_json()
    assert saved.ranking_profile_sha256 == PROFILE_HASH


def test_weights_survive_sqlite_history_and_reject_tampering(tmp_path):
    import json
    import test_candidate_search as candidate
    from src.search_v2.candidate_search import CandidateRanking
    from src.search_v2.candidate_image_free import image_free_history, PROFILE_HASH
    from src.search_v2.provisional_history_repository import (
        SqliteProvisionalHistoryRepository,
        ProvisionalHistoryWrite,
    )

    source = "マグカップ。電子レンジ対応。食洗機対応。"
    result = rank(
        bilingual_search(source)[0],
        tmp_path,
        [{"name": "マグカップ", "description": "電子レンジで温められます。"}],
    )
    saved = image_free_history(
        complete_image_free(result), source_text=source, completed_at=candidate.flow.NOW
    )
    assert saved.ranking_profile_sha256 != PROFILE_HASH
    assert saved.condition_weighting == result.retrieval_plan.condition_weighting
    repository = SqliteProvisionalHistoryRepository(tmp_path / "weighted.sqlite3")
    detail = repository.save(saved, now=candidate.flow.NOW)
    assert (
        repository.get(owner_id="owner-1", locator=detail.locator, now=candidate.flow.NOW) == detail
    )
    assert [r.weight for r in detail.products[0].condition_scores] == [2, 1]
    for value, model, key in [
        (result, CandidateRanking, "text_score"),
        (saved, ProvisionalHistoryWrite, None),
    ]:
        wire = json.loads(value.model_dump_json())
        scores = (
            wire["products"][0][key]["conditions"]
            if key
            else wire["products"][0]["condition_scores"]
        )
        scores[0]["weight"] = 1
        with pytest.raises(ValueError):
            model.model_validate_json(json.dumps(wire))


@pytest.mark.parametrize("bilingual", [False, True])
@pytest.mark.parametrize(
    "suffix,ratio",
    [("", "required_ratio"), ("が希望", "preferred_ratio"), ("を除外", "excluded_ratio")],
)
@pytest.mark.parametrize("reverse", [False, True])
def test_earlier_condition_changes_score_and_final_order(
    tmp_path, bilingual, suffix, ratio, reverse
):
    clauses = ["電子レンジ対応", "食洗機対応"]
    if reverse:
        clauses.reverse()
    source = "マグカップ。" + "。".join(c + suffix for c in clauses) + "。"
    service = bilingual_search(source)[0] if bilingual else search(source)
    result = rank(
        service,
        tmp_path,
        [
            {"name": "マグカップ", "description": "電子レンジで温められます。"},
            {"name": "マグカップ", "description": "食洗機で洗えます。"},
        ],
    )
    by_index = {p.product.provenance.response_index: p.text_score for p in result.products}
    first = int(reverse)
    assert getattr(by_index[first], ratio) == pytest.approx(2 / 3, abs=1e-6)
    assert getattr(by_index[1 - first], ratio) == pytest.approx(1 / 3, abs=1e-6)
    final = complete_image_free(result)
    expected = 1 - first if ratio == "excluded_ratio" else first
    assert final.products[0].product.provenance.response_index == expected
