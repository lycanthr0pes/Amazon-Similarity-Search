"""Description and title fallbacks preserve authority, absence and history boundaries."""

import json

import pytest

import test_candidate_search as candidate
import test_candidate_search_live_e2e as live
from test_candidate_text_scoring import rank, search
from src.search_v2.candidate_search import CandidatePlan, CandidateRanking, CandidateSearch


def test_partial_description_coverage_is_fractional(tmp_path):
    result = rank(
        search("マグカップ。電子レンジ加熱対応。"),
        tmp_path,
        [
            {"name": "マグカップ", "description": "電子レンジで温め直せます。"},
        ],
    )
    assert 0.0 < result.products[0].text_score.required_ratio < 1.0
    assert result.products[0].evaluation.required_status == "uncertain"


def test_invalid_structured_value_does_not_fall_back(tmp_path):
    result = rank(
        search("マグカップ。電子レンジ対応。"),
        tmp_path,
        [
            {
                "name": "マグカップ",
                "features": ["電子レンジ対応: 不明"],
                "description": "電子レンジに対応しています。",
            },
        ],
    )
    assert result.products[0].text_score.required_ratio == 0.0


def test_structured_match_ignores_negative_prose(tmp_path):
    result = rank(
        search("マグカップ。電子レンジ対応。"),
        tmp_path,
        [
            {
                "name": "マグカップ",
                "features": ["電子レンジ対応: 対応"],
                "description": "電子レンジ非対応です。",
            },
        ],
    )
    assert result.products[0].text_score.required_ratio == 1.0
    assert result.products[0].evaluation.required_status == "confirmed"


def test_excluded_prose_match_lowers_rank_without_proving_absence(tmp_path):
    result = rank(
        search("マグカップ。電子レンジ対応を除外。"),
        tmp_path,
        [
            {"name": "マグカップ", "description": "電子レンジに対応しています。"},
            {"name": "マグカップ", "description": "毎日の食事に使えます。"},
        ],
    )
    assert [p.product.provenance.response_index for p in result.products] == [1, 0]
    assert all(p.evaluation.required_status == "uncertain" for p in result.products)


def test_missing_price_cannot_be_filled_from_description(tmp_path):
    result = rank(
        search("マグカップ。3000円以下。"),
        tmp_path,
        [
            {"name": "マグカップ", "description": "価格は1000JPYです。"},
        ],
    )
    assert result.products[0].text_score.required_ratio == 0.0


def test_explicit_categories_are_separate_bilingual_fields():
    service = search("携帯用マグカップ。カテゴリ: 食器。カテゴリ英語: tableware。")
    assert service.plan.title_comparison.category_ja == "食器"
    assert service.plan.title_comparison.category_en == "tableware"


def test_model_is_not_guessed_from_standard_name():
    assert search("USB-3 ケーブル").plan.title_comparison.model_number is None


def test_plan_binds_the_text_scoring_profile():
    plan = search("マグカップ").plan
    data = json.loads(plan.model_dump_json())
    assert data["title_comparison"]["profile_id"] == "candidate-text-v1"
    data["title_comparison"]["profile_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        CandidatePlan.model_validate_json(json.dumps(data))


def test_truncated_description_is_not_scored(tmp_path):
    from src.search_v2.product_normalization import MAX_PRODUCT_DESCRIPTION_CHARACTERS

    result = rank(
        search("マグカップ。電子レンジ対応。"),
        tmp_path,
        [
            {
                "name": "マグカップ",
                "description": "電子レンジ対応。" + "あ" * MAX_PRODUCT_DESCRIPTION_CHARACTERS,
            },
        ],
    )
    assert result.products[0].text_score.required_ratio == 0.0


def test_legacy_plan_and_result_keep_old_serialization(tmp_path):
    service = search("マグカップ")
    plan = service.plan.model_copy(update={"title_comparison": None})
    assert "title_comparison" not in plan.model_dump_json()
    from src.search_v2.candidate_search import _digest

    restored = CandidateSearch.from_approved_plan(
        CandidatePlan.model_validate_json(plan.model_dump_json()),
        source="マグカップ",
        owner_id="owner-1",
        plan_sha256=_digest(plan),
        human_confirmed=True,
        normalization_profile=candidate.flow.backend_policy().normalization_profile,
        now=candidate.flow.NOW,
    )
    result = rank(restored, tmp_path, [{"name": "マグカップ"}])
    assert result.profile_id == "candidate-confirmed-lexical-v3"
    assert "text_score" not in result.model_dump_json()
    assert CandidateRanking.model_validate_json(result.model_dump_json()) == result


def test_new_text_profile_reaches_visual_json_and_sqlite(tmp_path, monkeypatch):
    module, config, services, _, _ = live.setup_run(tmp_path, monkeypatch)
    result = module.run_candidate_e2e(config, services, image_score_mode="appearance")
    assert result["status"] == "succeeded"
    history = json.loads((config.output_dir / "history.json").read_bytes())
    assert history["text_profile_id"] == "candidate-text-v1"
    assert result["text_profile_id"] == "candidate-text-v1"


def test_new_result_rejects_downgraded_text_profile(tmp_path):
    result = rank(search("マグカップ"), tmp_path, [{"name": "マグカップ"}])
    data = json.loads(result.model_dump_json())
    data["profile_id"] = "candidate-confirmed-lexical-v3"
    with pytest.raises(ValueError):
        CandidateRanking.model_validate_json(json.dumps(data))


@pytest.mark.parametrize(
    "text", ["電子レンジには対応していない商品です。", "電子レンジは使わないでください。"]
)
def test_negative_instruction_in_description_is_not_a_match(tmp_path, text):
    result = rank(
        search("マグカップ。電子レンジ対応。"),
        tmp_path,
        [{"name": "マグカップ", "description": text}],
    )
    assert result.products[0].text_score.required_ratio == 0.0


def test_numeric_prose_uses_the_number_next_to_the_attribute(tmp_path):
    result = rank(
        search("マグカップ。容量400ml以上。"),
        tmp_path,
        [{"name": "マグカップ", "description": "容量は500mlで、計量の最小目盛りは20mlです。"}],
    )
    assert result.products[0].text_score.required_ratio == 1.0


def test_unknown_structured_number_blocks_exact_description_fallback(tmp_path):
    result = rank(
        search("マグカップ。容量400ml以上。"),
        tmp_path,
        [{"name": "マグカップ", "features": ["容量: 不明"], "description": "容量: 500ml"}],
    )
    assert result.products[0].evaluation.required_status == "uncertain"
    assert result.products[0].text_score.required_ratio == 0.0


def test_explicit_identity_fields_work_with_source_structure():
    from test_lexical_structure import structure
    from src.search_v2.candidate_queries import build_candidate_queries

    text = "マグカップを探しています。ブランド: ACME。型番: AB-123。"
    parsed = structure(
        text.casefold(), "マグカップ", ("ブランド: acme", "型番: ab-123"), ("探しています",)
    )
    assert (
        build_candidate_queries(text, structure=parsed).retrieval_intent.product_name_ja
        == "マグカップ"
    )
