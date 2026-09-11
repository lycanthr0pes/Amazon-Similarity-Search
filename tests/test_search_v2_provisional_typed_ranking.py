from __future__ import annotations

import hashlib

import pytest

from src.search_v2.counterfactual_image import ConditionMargin
from src.search_v2.counterfactual_image import CounterfactualImageScore
from src.search_v2.counterfactual_v4 import minimum_positive_profile_sha256
from src.search_v2.image_similarity import clip_runtime_profile_sha256
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent
from src.search_v2.outscraper_request import build_outscraper_request
from src.search_v2.product_evidence import normalized_product_candidate_sha256
from src.search_v2.product_normalization import ProductNormalizationProfile
from src.search_v2.product_normalization import normalize_outscraper_products
from src.search_v2.provisional_counterfactual import ProvisionalImageCandidateInput
from src.search_v2.provisional_counterfactual import build_provisional_counterfactual_batch
from src.search_v2.provisional_typed_ranking import PROVISIONAL_TYPED_RANKING_PROFILE
from src.search_v2.provisional_typed_ranking import ProvisionalTypedRankingError
from src.search_v2.provisional_typed_ranking import rank_provisional_typed_product_batch
from src.search_v2.provisional_typed_ranking import provisional_typed_ranking_profile_sha256
from src.search_v2.query_planner import build_search_query_plan
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_ranking import rank_typed_product_batch
from src.search_v2.typed_ranking import typed_ranked_product_batch_sha256


def digest(tag: str) -> str:
    return hashlib.sha256(tag.encode()).hexdigest()


def source_ranking():
    source = "丸形マウスを探す"
    draft = SearchIntentDraft.model_validate(
        {
            "product_name_ja": "マウス",
            "product_name_en": "mouse",
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
            "typed_conditions": [
                {
                    "attribute_key": "form.shape",
                    "operator": "equals",
                    "expected_value": {"value_type": "enum", "values": ["round"]},
                    "strength": "required",
                }
            ],
            "ambiguities": [],
        }
    )
    provenance = build_intent_provenance(
        source_input=source,
        prompt=b"prompt",
        schema=b"schema",
        response=b"response",
    )
    intent = normalize_search_intent(source, draft, provenance=provenance)
    plan = build_search_query_plan(intent)
    request = build_outscraper_request(plan, postal_code="100-0001")
    products = [
        {"name": "丸形マウス", "asin": "B000PV5001", "features": ["Round"]},
        {"name": "丸形マウス", "asin": "B000PV5002", "features": ["Round"]},
        {"name": "マウス", "asin": "B000PV5003", "features": ["Rectangular"]},
        {"name": "マウス", "asin": "B000PV5004", "features": ["Rectangular"]},
    ]
    batch = normalize_outscraper_products(
        {"data": products if len(plan.queries) == 1 else [products, []]},
        request=request,
        provider_request_id="task_provisional_ranking",
        profile=ProductNormalizationProfile(
            schema_version="2.0",
            profile_id="observed-only-v2",
            usd_to_jpy_rate=160,
        ),
    )
    proposal = build_typed_requirement_proposal(intent)
    return rank_typed_product_batch(intent, plan, batch, proposal)


def image_score(product_sha256: str, tag: str, margin: float) -> ProvisionalImageCandidateInput:
    score = CounterfactualImageScore(
        schema_version="1.0",
        status="scored",
        condition_set_sha256=digest("conditions"),
        reference_set_sha256=digest("references"),
        score_profile_sha256=minimum_positive_profile_sha256(),
        runtime_sha256=clip_runtime_profile_sha256(),
        candidate_image_pixel_sha256=digest(f"image-{tag}"),
        condition_margins=(
            ConditionMargin(
                condition_id="visual-condition-001",
                status="scored",
                raw_margin=margin / 10.0,
                reference_distance=0.1,
                normalized_margin=margin,
            ),
        ),
        qualified_for_ranking=False,
    )
    return ProvisionalImageCandidateInput(
        normalized_product_sha256=product_sha256,
        candidate_image_pixel_sha256=score.candidate_image_pixel_sha256,
        score=score,
    )


def image_batch(source):
    by_response = sorted(source.products, key=lambda item: item.product.provenance.response_index)
    margins = (-1.0, -0.5, 0.5, 1.0)
    return build_provisional_counterfactual_batch(
        tuple(
            image_score(
                normalized_product_candidate_sha256(item.product),
                str(index),
                margin,
            )
            for index, (item, margin) in enumerate(zip(by_response, margins, strict=True), start=1)
        )
    )


def test_profile_is_new_and_keeps_image_as_the_second_lowest_base_weight() -> None:
    profile = PROVISIONAL_TYPED_RANKING_PROFILE

    assert profile.schema_version == "5.0"
    assert profile.profile_id == "typed-ranking-v5-counterfactual-provisional"
    assert profile.source_ranking_profile_id == "typed-ranking-v4"
    assert profile.image_weight == 0.1
    assert profile.review_quality_weight == 0.05
    assert profile.image_scoring_enabled is True
    assert provisional_typed_ranking_profile_sha256() == provisional_typed_ranking_profile_sha256()


def test_image_component_is_recomputed_without_mutating_the_v4_source() -> None:
    source = source_ranking()
    images = image_batch(source)

    result = rank_provisional_typed_product_batch(source, images)

    assert result.source_typed_ranked_product_batch_sha256 == typed_ranked_product_batch_sha256(
        source
    )
    assert all(item.breakdown.image.status == "available" for item in result.products)
    assert {item.breakdown.image.base_weight for item in result.products} == {0.1}
    score_by_product = {
        normalized_product_candidate_sha256(item.product): item.breakdown.image.score
        for item in result.products
    }
    assert score_by_product == {
        component.normalized_product_sha256: component.image_score
        for component in images.candidates
    }
    assert all(item.breakdown.image.status == "disabled" for item in source.products)


def test_required_status_still_precedes_total_score() -> None:
    source = source_ranking()
    result = rank_provisional_typed_product_batch(source, image_batch(source))

    required_statuses = [item.evaluation.required_status for item in result.products]
    assert required_statuses[:2] == ["confirmed", "confirmed"]
    assert required_statuses[2:] == ["contradicted", "contradicted"]


def test_product_binding_tamper_is_rejected() -> None:
    source = source_ranking()
    images = image_batch(source)
    tampered = images.model_copy(
        update={
            "candidates": (
                images.candidates[0].model_copy(
                    update={"normalized_product_sha256": digest("other-product")}
                ),
                *images.candidates[1:],
            )
        }
    )

    with pytest.raises(ProvisionalTypedRankingError, match="ranking contract"):
        rank_provisional_typed_product_batch(source, tampered)
