import ast
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

import src.search_v2.ranking as ranking
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent
from src.search_v2.outscraper_request import build_outscraper_request
from src.search_v2.product_normalization import ProductNormalizationProfile
from src.search_v2.product_normalization import normalize_outscraper_products
from src.search_v2.query_planner import build_search_query_plan
from src.search_v2.ranking import RANKING_PROFILE_V3
from src.search_v2.ranking import RankedProductBatch
from src.search_v2.ranking import RankingError
from src.search_v2.ranking import rank_product_batch
from src.search_v2.ranking import ranked_product_batch_sha256
from src.search_v2.ranking import ranking_profile_sha256


def normalized_intent(**overrides):
    source_input = overrides.pop(
        "source_input",
        "5万円以内の黒い軽量ワイヤレスノイズキャンセリングヘッドホン。中古は避けたい。",
    )
    payload = {
        "product_name_ja": "ヘッドホン",
        "product_name_en": "headphones",
        "category_ja": "オーディオ",
        "category_en": "audio",
        "required_terms_ja": ["ワイヤレス"],
        "required_terms_en": ["wireless"],
        "preferred_terms_ja": ["軽量"],
        "preferred_terms_en": ["lightweight"],
        "negative_terms_ja": ["中古"],
        "negative_terms_en": ["used"],
        "color_ja": "黒",
        "color_en": "black",
        "features_ja": ["ノイズキャンセリング"],
        "features_en": ["noise cancelling"],
        "brand": None,
        "model_number": None,
        "price": {
            "currency": "JPY",
            "mode": "max",
            "target_jpy": None,
            "min_jpy": None,
            "max_jpy": 50_000,
            "source": "explicit",
            "confidence": None,
        },
        "typed_conditions": [],
        "ambiguities": [],
    }
    payload.update(overrides)
    provenance = build_intent_provenance(
        source_input=source_input,
        prompt=b"prompt",
        schema=b"schema",
        response=b"response",
    )
    return normalize_search_intent(
        source_input,
        SearchIntentDraft.model_validate(payload),
        provenance=provenance,
    )


def ranking_inputs(products, *, intent=None):
    selected_intent = intent or normalized_intent()
    query_plan = build_search_query_plan(selected_intent)
    request = build_outscraper_request(query_plan, postal_code="100-0001")
    response_data = products if len(query_plan.queries) == 1 else [products, []]
    batch = normalize_outscraper_products(
        {"data": response_data},
        request=request,
        provider_request_id="task_0123456789",
        profile=ProductNormalizationProfile(
            schema_version="2.0",
            profile_id="observed-only-v2",
            usd_to_jpy_rate=160,
        ),
    )
    return selected_intent, query_plan, batch


def title_only_intent(**overrides):
    payload = {
        "source_input": "ヘッドホンを探す",
        "product_name_ja": "ヘッドホン",
        "product_name_en": None,
        "category_ja": None,
        "category_en": None,
        "required_terms_ja": [],
        "required_terms_en": [],
        "preferred_terms_ja": [],
        "preferred_terms_en": [],
        "negative_terms_ja": [],
        "negative_terms_en": [],
        "color_ja": None,
        "color_en": None,
        "features_ja": [],
        "features_en": [],
        "brand": None,
        "model_number": None,
        "price": {
            "currency": "JPY",
            "mode": "none",
            "target_jpy": None,
            "min_jpy": None,
            "max_jpy": None,
            "source": "none",
            "confidence": None,
        },
        "typed_conditions": [],
        "ambiguities": [],
    }
    payload.update(overrides)
    return normalized_intent(**payload)


def test_fixed_ranking_profile_is_deterministic_and_keeps_reviews_lowest_weight() -> None:
    assert RANKING_PROFILE_V3.schema_version == "3.0"
    assert RANKING_PROFILE_V3.profile_id == "ranking-v3"
    assert RANKING_PROFILE_V3.title_weight == 0.35
    assert RANKING_PROFILE_V3.attributes_weight == 0.30
    assert RANKING_PROFILE_V3.price_weight == 0.20
    assert RANKING_PROFILE_V3.image_weight == 0.10
    assert RANKING_PROFILE_V3.review_quality_weight == 0.05
    assert RANKING_PROFILE_V3.high_rating_threshold == 4.0
    assert RANKING_PROFILE_V3.maximum_rating == 5.0
    assert RANKING_PROFILE_V3.review_count_saturation == 1_000
    assert RANKING_PROFILE_V3.review_quality_weight < min(
        RANKING_PROFILE_V3.title_weight,
        RANKING_PROFILE_V3.attributes_weight,
        RANKING_PROFILE_V3.price_weight,
        RANKING_PROFILE_V3.image_weight,
    )
    assert RANKING_PROFILE_V3.negative_match_penalty == 0.20
    assert RANKING_PROFILE_V3.max_negative_penalty == 0.50
    assert RANKING_PROFILE_V3.image_scoring_enabled is False
    assert ranking_profile_sha256() == ranking_profile_sha256(RANKING_PROFILE_V3)
    assert len(ranking_profile_sha256()) == 64


@pytest.mark.parametrize(
    ("rating", "reviews", "expected"),
    [
        (3.9, 1_000, 0.0),
        (4.0, 0, 0.0),
        (4.0, 1, 0.0803),
        (4.5, 100, 0.6012),
        (5.0, 1_000, 1.0),
        (5.0, 10_000, 1.0),
    ],
)
def test_review_quality_uses_high_rating_and_log_scaled_review_volume(
    rating: float,
    reviews: int,
    expected: float,
) -> None:
    intent = title_only_intent()
    intent, query_plan, batch = ranking_inputs(
        [{"name": "ヘッドホン", "rating": rating, "reviews": reviews}],
        intent=intent,
    )

    component = rank_product_batch(intent, query_plan, batch).products[0].breakdown.review_quality

    assert component.status == "available"
    assert component.reason == "scored"
    assert component.score == expected


@pytest.mark.parametrize(
    "product",
    [
        {"name": "ヘッドホン", "rating": 4.8},
        {"name": "ヘッドホン", "reviews": 500},
    ],
)
def test_review_quality_is_missing_when_either_observation_is_missing(product) -> None:
    intent = title_only_intent()
    intent, query_plan, batch = ranking_inputs([product], intent=intent)

    breakdown = rank_product_batch(intent, query_plan, batch).products[0].breakdown

    assert breakdown.review_quality.status == "missing"
    assert breakdown.review_quality.reason == "product_data_missing"
    assert breakdown.review_quality.score is None
    assert breakdown.review_quality.effective_weight == 0.0
    assert breakdown.title.effective_weight == 1.0


def test_review_quality_breaks_a_normal_score_tie_without_overriding_other_weights() -> None:
    intent = title_only_intent()
    intent, query_plan, batch = ranking_inputs(
        [
            {
                "name": "ヘッドホン",
                "asin": "B000TEST01",
                "rating": 4.0,
                "reviews": 1,
            },
            {
                "name": "ヘッドホン",
                "asin": "B000TEST02",
                "rating": 5.0,
                "reviews": 1_000,
            },
        ],
        intent=intent,
    )

    result = rank_product_batch(intent, query_plan, batch)

    assert [item.product.asin for item in result.products] == ["B000TEST02", "B000TEST01"]
    higher, lower = (item.breakdown for item in result.products)
    assert higher.review_quality.score == 1.0
    assert lower.review_quality.score == 0.0803
    assert higher.review_quality.effective_weight == pytest.approx(0.125)
    assert math.isclose(higher.title.effective_weight, 0.875)
    assert higher.total_score == 1.0
    assert lower.total_score == 0.885


@pytest.mark.parametrize(
    ("higher_rating", "higher_reviews", "lower_rating", "lower_reviews"),
    [
        (4.3, 317, 4.6, 145),
        (4.2, 1432, 4.1, 8),
    ],
)
def test_case2_review_quality_supports_user_expected_tie_breaks(
    higher_rating: float,
    higher_reviews: int,
    lower_rating: float,
    lower_reviews: int,
) -> None:
    intent = title_only_intent()
    intent, query_plan, batch = ranking_inputs(
        [
            {
                "name": "同一特徴の収納用品",
                "asin": "B000CASE2H",
                "rating": higher_rating,
                "reviews": higher_reviews,
            },
            {
                "name": "同一特徴の収納用品",
                "asin": "B000CASE2L",
                "rating": lower_rating,
                "reviews": lower_reviews,
            },
        ],
        intent=intent,
    )

    result = rank_product_batch(intent, query_plan, batch)

    assert [item.product.asin for item in result.products] == ["B000CASE2H", "B000CASE2L"]
    assert (
        result.products[0].breakdown.review_quality.score
        > result.products[1].breakdown.review_quality.score
    )


def test_ranking_returns_explainable_components_and_applies_negative_penalty() -> None:
    intent, query_plan, batch = ranking_inputs(
        [
            {
                "name": "ヘッドホン",
                "categories": ["オーディオ"],
                "color": "黒",
                "features": ["ワイヤレス", "軽量", "ノイズキャンセリング"],
                "price": 40_000,
                "currency": "JPY",
            },
            {
                "name": "中古 ヘッドホン",
                "categories": ["オーディオ"],
                "color": "黒",
                "features": ["ワイヤレス", "軽量", "ノイズキャンセリング"],
                "price": 40_000,
                "currency": "JPY",
            },
        ]
    )

    result = rank_product_batch(intent, query_plan, batch)

    assert [item.product.provenance.response_index for item in result.products] == [0, 1]
    first = result.products[0]
    assert first.rank == 1
    assert first.breakdown.title.score == 0.5
    assert first.breakdown.attributes.score == 1.0
    assert first.breakdown.price.score == 1.0
    assert first.breakdown.image.status == "disabled"
    assert first.breakdown.review_quality.status == "missing"
    assert first.breakdown.available_base_weight == 0.85
    assert first.breakdown.title.effective_weight == pytest.approx(0.411765)
    assert first.breakdown.attributes.effective_weight == pytest.approx(0.352941)
    assert first.breakdown.price.effective_weight == pytest.approx(0.235294)
    assert first.breakdown.pre_penalty_score == 0.7941
    assert first.breakdown.negative_penalty == 0.0
    assert first.breakdown.total_score == 0.7941
    assert first.breakdown.attribute_language == "ja"
    assert first.breakdown.matched_terms == (
        "ワイヤレス",
        "軽量",
        "オーディオ",
        "黒",
        "ノイズキャンセリング",
    )
    assert first.breakdown.missing_terms == ()

    second = result.products[1]
    assert second.breakdown.negative_matches == ("中古",)
    assert second.breakdown.negative_penalty == 0.2
    assert second.breakdown.total_score == 0.5941


def test_missing_components_are_excluded_and_available_weight_is_renormalized() -> None:
    intent = title_only_intent()
    intent, query_plan, batch = ranking_inputs([{"name": "ヘッドホン"}], intent=intent)

    result = rank_product_batch(intent, query_plan, batch)
    breakdown = result.products[0].breakdown

    assert breakdown.title.status == "available"
    assert breakdown.title.score == 1.0
    assert breakdown.title.effective_weight == 1.0
    assert breakdown.attributes.status == "missing"
    assert breakdown.attributes.reason == "no_intent_terms"
    assert breakdown.price.status == "missing"
    assert breakdown.price.reason == "not_requested"
    assert breakdown.image.status == "disabled"
    assert breakdown.image.reason == "image_scoring_disabled"
    assert breakdown.review_quality.status == "missing"
    assert breakdown.review_quality.reason == "product_data_missing"
    assert breakdown.available_base_weight == 0.35
    assert breakdown.total_score == 1.0


def test_observed_mismatch_is_zero_not_missing_and_keeps_its_weight() -> None:
    intent = title_only_intent(required_terms_ja=["静音"])
    intent, query_plan, batch = ranking_inputs(
        [{"name": "ヘッドホン", "features": ["防水"]}],
        intent=intent,
    )

    breakdown = rank_product_batch(intent, query_plan, batch).products[0].breakdown

    assert breakdown.attributes.status == "available"
    assert breakdown.attributes.score == 0.0
    assert breakdown.attributes.effective_weight == pytest.approx(0.461538)
    assert breakdown.missing_terms == ("静音",)
    assert breakdown.available_base_weight == 0.65
    assert breakdown.total_score == 0.5385


def test_unobserved_product_attributes_are_missing_instead_of_zero() -> None:
    intent = title_only_intent(required_terms_ja=["静音"])
    intent, query_plan, batch = ranking_inputs([{"name": "ヘッドホン"}], intent=intent)

    breakdown = rank_product_batch(intent, query_plan, batch).products[0].breakdown

    assert breakdown.attributes.status == "missing"
    assert breakdown.attributes.reason == "product_data_missing"
    assert breakdown.missing_terms == ("静音",)
    assert breakdown.title.effective_weight == 1.0
    assert breakdown.total_score == 1.0


@pytest.mark.parametrize(
    ("price", "product_price", "expected"),
    [
        (
            {
                "currency": "JPY",
                "mode": "exact",
                "target_jpy": 10_000,
                "min_jpy": None,
                "max_jpy": None,
                "source": "explicit",
                "confidence": None,
            },
            8_000,
            0.8,
        ),
        (
            {
                "currency": "JPY",
                "mode": "range",
                "target_jpy": None,
                "min_jpy": 5_000,
                "max_jpy": 10_000,
                "source": "explicit",
                "confidence": None,
            },
            4_000,
            0.8,
        ),
        (
            {
                "currency": "JPY",
                "mode": "min",
                "target_jpy": None,
                "min_jpy": 10_000,
                "max_jpy": None,
                "source": "explicit",
                "confidence": None,
            },
            8_000,
            0.8,
        ),
        (
            {
                "currency": "JPY",
                "mode": "max",
                "target_jpy": None,
                "min_jpy": None,
                "max_jpy": 10_000,
                "source": "explicit",
                "confidence": None,
            },
            12_500,
            0.8,
        ),
    ],
)
def test_price_score_follows_strict_price_modes(price, product_price, expected) -> None:
    intent = title_only_intent(price=price)
    intent, query_plan, batch = ranking_inputs(
        [{"name": "ヘッドホン", "price": product_price, "currency": "JPY"}],
        intent=intent,
    )

    component = rank_product_batch(intent, query_plan, batch).products[0].breakdown.price

    assert component.status == "available"
    assert component.score == expected


def test_requested_price_without_observed_price_is_missing() -> None:
    intent = title_only_intent(
        price={
            "currency": "JPY",
            "mode": "max",
            "target_jpy": None,
            "min_jpy": None,
            "max_jpy": 10_000,
            "source": "explicit",
            "confidence": None,
        }
    )
    intent, query_plan, batch = ranking_inputs([{"name": "ヘッドホン"}], intent=intent)

    component = rank_product_batch(intent, query_plan, batch).products[0].breakdown.price

    assert component.status == "missing"
    assert component.reason == "product_data_missing"
    assert component.score is None


def test_negative_penalty_is_capped_and_does_not_remove_the_product() -> None:
    intent = title_only_intent(
        negative_terms_ja=["中古", "破損", "部品取り"],
        source_input="中古、破損、部品取りは避けてヘッドホンを探す",
    )
    intent, query_plan, batch = ranking_inputs(
        [{"name": "中古 破損 部品取り ヘッドホン"}],
        intent=intent,
    )

    result = rank_product_batch(intent, query_plan, batch)
    breakdown = result.products[0].breakdown

    assert len(result.products) == 1
    assert breakdown.negative_matches == ("中古", "破損", "部品取り")
    assert breakdown.negative_penalty == 0.5
    assert breakdown.pre_penalty_score == 1.0
    assert breakdown.total_score == 0.5


def test_ties_use_response_index_even_if_product_tuple_is_reordered() -> None:
    intent = title_only_intent()
    intent, query_plan, batch = ranking_inputs(
        [
            {"name": "ヘッドホン", "asin": "B000TEST01"},
            {"name": "ヘッドホン", "asin": "B000TEST02"},
        ],
        intent=intent,
    )
    reordered = batch.model_copy(update={"products": tuple(reversed(batch.products))})

    original_result = rank_product_batch(intent, query_plan, batch)
    reordered_result = rank_product_batch(intent, query_plan, reordered)

    assert [item.product.asin for item in original_result.products] == [
        "B000TEST01",
        "B000TEST02",
    ]
    assert [item.product.asin for item in reordered_result.products] == [
        "B000TEST01",
        "B000TEST02",
    ]
    assert [item.rank for item in reordered_result.products] == [1, 2]


def test_empty_batch_returns_a_bound_empty_ranking() -> None:
    intent, query_plan, batch = ranking_inputs([])

    first = rank_product_batch(intent, query_plan, batch)
    second = rank_product_batch(intent, query_plan, batch)

    assert first.products == ()
    assert first == second
    assert first.schema_version == "3.0"
    assert first.ranking_profile_id == "ranking-v3"
    assert first.ranking_profile_sha256 == ranking_profile_sha256()
    assert ranked_product_batch_sha256(first) == ranked_product_batch_sha256(second)


def test_ranking_rejects_mismatched_intent_query_batch_or_profile() -> None:
    intent, query_plan, batch = ranking_inputs([{"name": "ヘッドホン"}])
    wrong_query = query_plan.model_copy(update={"intent_sha256": "f" * 64})
    wrong_batch = batch.model_copy(update={"query_plan_sha256": "e" * 64})
    forged_profile = RANKING_PROFILE_V3.model_construct(
        **{
            **RANKING_PROFILE_V3.model_dump(mode="python"),
            "title_weight": 0.9,
        }
    )
    legacy_profile = RANKING_PROFILE_V3.model_construct(
        **{
            **RANKING_PROFILE_V3.model_dump(mode="python"),
            "schema_version": "2.0",
            "profile_id": "ranking-v2",
        }
    )

    with pytest.raises(RankingError, match="^Ranking inputs did not match the ranking contract$"):
        rank_product_batch(intent, wrong_query, batch)
    with pytest.raises(RankingError, match="^Ranking inputs did not match the ranking contract$"):
        rank_product_batch(intent, query_plan, wrong_batch)
    with pytest.raises(RankingError, match="^Ranking inputs did not match the ranking contract$"):
        rank_product_batch(intent, query_plan, batch, profile=forged_profile)
    with pytest.raises(RankingError, match="^Ranking inputs did not match the ranking contract$"):
        rank_product_batch(intent, query_plan, batch, profile=legacy_profile)


def test_ranked_models_are_strict_and_revalidate_nested_components() -> None:
    intent, query_plan, batch = ranking_inputs([{"name": "ヘッドホン"}])
    result = rank_product_batch(intent, query_plan, batch)
    payload = result.model_dump(mode="python")

    with pytest.raises(ValidationError):
        RankedProductBatch.model_validate({**payload, "unexpected": True})

    item = result.products[0]
    forged_title = item.breakdown.title.model_copy(update={"score": True})
    forged_breakdown = item.breakdown.model_copy(update={"title": forged_title})
    forged_item = item.model_copy(update={"breakdown": forged_breakdown})
    forged_result = result.model_copy(update={"products": (forged_item,)})
    with pytest.raises(ValidationError):
        ranked_product_batch_sha256(forged_result)


def test_ranked_batch_digest_binds_scores_and_products() -> None:
    intent = title_only_intent()
    intent, query_plan, first_batch = ranking_inputs(
        [{"name": "ヘッドホン", "price": 8_000, "currency": "JPY"}],
        intent=intent,
    )
    _, _, second_batch = ranking_inputs(
        [{"name": "ヘッドホン", "price": 9_000, "currency": "JPY"}],
        intent=intent,
    )

    first = rank_product_batch(intent, query_plan, first_batch)
    second = rank_product_batch(intent, query_plan, second_batch)

    assert ranked_product_batch_sha256(first) != ranked_product_batch_sha256(second)


def test_ranking_module_has_no_network_provider_or_ml_runtime_import() -> None:
    module_path = Path(ranking.__file__)
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)

    forbidden = (
        "requests",
        "httpx",
        "socket",
        "openai",
        "torch",
        "transformers",
        "src.clients",
    )
    assert not any(
        name == prefix or name.startswith(f"{prefix}.") for name in imports for prefix in forbidden
    )
