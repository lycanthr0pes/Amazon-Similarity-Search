"""Versioned typed ranking with the provisional counterfactual image component."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Annotated
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import ValidationError
from pydantic import model_validator

from src.search_v2.product_evidence import ProductEvidenceSet
from src.search_v2.product_evidence import normalized_product_candidate_sha256
from src.search_v2.product_normalization import NormalizedProductCandidate
from src.search_v2.provisional_counterfactual import ProvisionalCounterfactualBatch
from src.search_v2.provisional_counterfactual import ProvisionalImageComponent
from src.search_v2.provisional_counterfactual import provisional_counterfactual_batch_sha256
from src.search_v2.provisional_counterfactual import provisional_counterfactual_profile_sha256
from src.search_v2.ranking import EFFECTIVE_WEIGHT_DECIMALS
from src.search_v2.ranking import MAX_RANKED_PRODUCTS
from src.search_v2.ranking import SCORE_DECIMALS
from src.search_v2.ranking import ComponentReason
from src.search_v2.ranking import ComponentStatus
from src.search_v2.ranking import ScoreComponent
from src.search_v2.ranking import ScoreTerm
from src.search_v2.requirement_evaluation import TypedProductEvaluation
from src.search_v2.requirement_evaluation import typed_product_sort_key
from src.search_v2.typed_ranking import MAX_TYPED_WEIGHT
from src.search_v2.typed_ranking import TYPED_RANKING_PROFILE_V4
from src.search_v2.typed_ranking import TypedRankedProduct
from src.search_v2.typed_ranking import TypedRankedProductBatch
from src.search_v2.typed_ranking import typed_ranked_product_batch_sha256
from src.search_v2.typed_ranking import typed_ranking_profile_sha256


PROVISIONAL_TYPED_RANKING_PROFILE_DOMAIN = (
    b"amazon-explorer-typed-ranking-v5-counterfactual-provisional-profile\x00"
)
PROVISIONAL_TYPED_RANKED_BATCH_DOMAIN = (
    b"amazon-explorer-typed-ranking-v5-counterfactual-provisional-batch\x00"
)
_INVALID_RANKING_MESSAGE = "Inputs did not match the provisional typed ranking contract"

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
ScoreValue = Annotated[float, Field(ge=0.0, le=1.0)]


class ProvisionalTypedRankingError(ValueError):
    """A fixed-message rejection at the provisional ranking boundary."""


class _StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


class ProvisionalTypedRankingProfile(_StrictFrozenContract):
    schema_version: Literal["5.0"]
    profile_id: Literal["typed-ranking-v5-counterfactual-provisional"]
    source_ranking_profile_id: Literal["typed-ranking-v4"]
    source_ranking_profile_sha256: Digest
    counterfactual_profile_sha256: Digest
    sort_key_version: Literal["required-preferred-total-response-v1"]
    title_weight: Literal[0.35]
    typed_attributes_weight: Literal[0.3]
    price_weight: Literal[0.2]
    image_weight: Literal[0.1]
    review_quality_weight: Literal[0.05]
    negative_match_penalty: Literal[0.2]
    max_negative_penalty: Literal[0.5]
    image_scoring_enabled: Literal[True]
    adoption_basis: Literal["human_authorized_provisional"]
    score_decimals: Literal[4]

    @model_validator(mode="after")
    def validate_weights(self) -> ProvisionalTypedRankingProfile:
        weights = (
            self.title_weight,
            self.typed_attributes_weight,
            self.price_weight,
            self.image_weight,
            self.review_quality_weight,
        )
        if not math.isclose(math.fsum(weights), 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("provisional ranking weights must total one")
        if self.review_quality_weight >= min(weights[:-1]):
            raise ValueError("review quality must remain the unique lowest weight")
        if self.source_ranking_profile_sha256 != typed_ranking_profile_sha256(
            TYPED_RANKING_PROFILE_V4
        ):
            raise ValueError("provisional source ranking profile is unsupported")
        return self


PROVISIONAL_TYPED_RANKING_PROFILE = ProvisionalTypedRankingProfile(
    schema_version="5.0",
    profile_id="typed-ranking-v5-counterfactual-provisional",
    source_ranking_profile_id="typed-ranking-v4",
    source_ranking_profile_sha256=typed_ranking_profile_sha256(TYPED_RANKING_PROFILE_V4),
    counterfactual_profile_sha256=provisional_counterfactual_profile_sha256(),
    sort_key_version="required-preferred-total-response-v1",
    title_weight=0.35,
    typed_attributes_weight=0.3,
    price_weight=0.2,
    image_weight=0.1,
    review_quality_weight=0.05,
    negative_match_penalty=0.2,
    max_negative_penalty=0.5,
    image_scoring_enabled=True,
    adoption_basis="human_authorized_provisional",
    score_decimals=4,
)


class ProvisionalTypedScoreBreakdown(_StrictFrozenContract):
    title: ScoreComponent
    typed_attributes: ScoreComponent
    price: ScoreComponent
    image: ScoreComponent
    review_quality: ScoreComponent
    typed_requirement_count: Annotated[int, Field(ge=0, le=64)]
    typed_satisfied_weight: Annotated[int, Field(ge=0, le=MAX_TYPED_WEIGHT)]
    typed_total_weight: Annotated[int, Field(ge=0, le=MAX_TYPED_WEIGHT)]
    available_base_weight: ScoreValue
    pre_penalty_score: ScoreValue
    negative_penalty: ScoreValue
    total_score: ScoreValue
    title_language: Literal["ja", "en"] | None
    negative_matches: Annotated[tuple[ScoreTerm, ...], Field(max_length=64)]

    @model_validator(mode="after")
    def validate_breakdown(self) -> ProvisionalTypedScoreBreakdown:
        profile = PROVISIONAL_TYPED_RANKING_PROFILE
        components = (
            self.title,
            self.typed_attributes,
            self.price,
            self.image,
            self.review_quality,
        )
        weights = (
            profile.title_weight,
            profile.typed_attributes_weight,
            profile.price_weight,
            profile.image_weight,
            profile.review_quality_weight,
        )
        if tuple(item.base_weight for item in components) != weights:
            raise ValueError("provisional component weights do not match")
        if self.image.status == "disabled":
            raise ValueError("provisional image component must not be disabled")
        expected_available = round(
            math.fsum(
                weight
                for component, weight in zip(components, weights, strict=True)
                if component.status == "available"
            ),
            SCORE_DECIMALS,
        )
        if self.available_base_weight != expected_available:
            raise ValueError("provisional available weight does not match")
        expected_pre_penalty = round(
            math.fsum(item.contribution for item in components),
            SCORE_DECIMALS,
        )
        if self.pre_penalty_score != expected_pre_penalty:
            raise ValueError("provisional pre-penalty score does not match")
        expected_total = round(
            max(0.0, min(1.0, self.pre_penalty_score - self.negative_penalty)),
            SCORE_DECIMALS,
        )
        if self.total_score != expected_total:
            raise ValueError("provisional total score does not match")
        return self


class ProvisionalTypedRankedProduct(_StrictFrozenContract):
    schema_version: Literal["5.0"]
    rank: Annotated[int, Field(ge=1, le=MAX_RANKED_PRODUCTS)]
    product: NormalizedProductCandidate = Field(repr=False)
    evidence: ProductEvidenceSet = Field(repr=False)
    evaluation: TypedProductEvaluation
    image_component: ProvisionalImageComponent
    breakdown: ProvisionalTypedScoreBreakdown

    @model_validator(mode="after")
    def validate_bindings(self) -> ProvisionalTypedRankedProduct:
        product_sha256 = normalized_product_candidate_sha256(self.product)
        if (
            self.evidence.product_sha256 != product_sha256
            or self.evaluation.product_sha256 != product_sha256
            or self.image_component.normalized_product_sha256 != product_sha256
        ):
            raise ValueError("provisional ranked product binding does not match")
        return self


class ProvisionalTypedRankedProductBatch(_StrictFrozenContract):
    schema_version: Literal["5.0"]
    ranking_profile_id: Literal["typed-ranking-v5-counterfactual-provisional"]
    ranking_profile_sha256: Digest
    source_typed_ranked_product_batch_sha256: Digest
    counterfactual_batch_sha256: Digest
    condition_set_sha256: Digest
    reference_set_sha256: Digest
    runtime_sha256: Digest
    products: Annotated[
        tuple[ProvisionalTypedRankedProduct, ...],
        Field(max_length=MAX_RANKED_PRODUCTS),
    ]

    @model_validator(mode="after")
    def validate_products(self) -> ProvisionalTypedRankedProductBatch:
        if self.ranking_profile_sha256 != provisional_typed_ranking_profile_sha256():
            raise ValueError("provisional ranking profile binding is unsupported")
        if tuple(item.rank for item in self.products) != tuple(range(1, len(self.products) + 1)):
            raise ValueError("provisional product ranks are not contiguous")
        sort_keys = tuple(
            typed_product_sort_key(
                item.evaluation,
                overall_score=item.breakdown.total_score,
                response_index=item.product.provenance.response_index,
            )
            for item in self.products
        )
        if sort_keys != tuple(sorted(sort_keys)):
            raise ValueError("provisional products are not in canonical order")
        return self


def _canonical_sha256(domain: bytes, value: BaseModel) -> str:
    payload = json.dumps(
        value.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(domain + payload).hexdigest()


def provisional_typed_ranking_profile_sha256(
    profile: ProvisionalTypedRankingProfile = PROVISIONAL_TYPED_RANKING_PROFILE,
) -> str:
    try:
        validated = ProvisionalTypedRankingProfile.model_validate(profile)
        return _canonical_sha256(PROVISIONAL_TYPED_RANKING_PROFILE_DOMAIN, validated)
    except (TypeError, ValueError, ValidationError) as exc:
        raise ProvisionalTypedRankingError(_INVALID_RANKING_MESSAGE) from exc


def _component(
    *,
    status: ComponentStatus,
    reason: ComponentReason,
    score: float | None,
    base_weight: float,
    available_base_weight: float,
) -> ScoreComponent:
    if status != "available":
        return ScoreComponent(
            status=status,
            reason=reason,
            score=None,
            base_weight=float(base_weight),
            effective_weight=0.0,
            contribution=0.0,
        )
    if score is None or available_base_weight <= 0.0:
        raise ValueError("available provisional component has no score")
    bounded = float(round(max(0.0, min(1.0, score)), SCORE_DECIMALS))
    effective = float(round(base_weight / available_base_weight, EFFECTIVE_WEIGHT_DECIMALS))
    return ScoreComponent(
        status="available",
        reason="scored",
        score=bounded,
        base_weight=float(base_weight),
        effective_weight=effective,
        contribution=float(round(bounded * effective, SCORE_DECIMALS)),
    )


def _breakdown(
    source: TypedRankedProduct,
    image: ProvisionalImageComponent,
) -> ProvisionalTypedScoreBreakdown:
    source_breakdown = source.breakdown
    image_status: ComponentStatus = "available" if image.status == "available" else "missing"
    image_reason: ComponentReason = (
        "scored" if image.status == "available" else "product_data_missing"
    )
    raw = (
        (
            source_breakdown.title.status,
            source_breakdown.title.reason,
            source_breakdown.title.score,
        ),
        (
            source_breakdown.typed_attributes.status,
            source_breakdown.typed_attributes.reason,
            source_breakdown.typed_attributes.score,
        ),
        (
            source_breakdown.price.status,
            source_breakdown.price.reason,
            source_breakdown.price.score,
        ),
        (image_status, image_reason, image.image_score),
        (
            source_breakdown.review_quality.status,
            source_breakdown.review_quality.reason,
            source_breakdown.review_quality.score,
        ),
    )
    profile = PROVISIONAL_TYPED_RANKING_PROFILE
    weights = (
        profile.title_weight,
        profile.typed_attributes_weight,
        profile.price_weight,
        profile.image_weight,
        profile.review_quality_weight,
    )
    available_weight = math.fsum(
        weight
        for (status, _reason, _score), weight in zip(raw, weights, strict=True)
        if status == "available"
    )
    components = tuple(
        _component(
            status=status,
            reason=reason,
            score=score,
            base_weight=weight,
            available_base_weight=available_weight,
        )
        for (status, reason, score), weight in zip(raw, weights, strict=True)
    )
    negative_penalty = float(
        round(
            min(
                profile.max_negative_penalty,
                len(source_breakdown.negative_matches) * profile.negative_match_penalty,
            ),
            SCORE_DECIMALS,
        )
    )
    pre_penalty = float(round(math.fsum(item.contribution for item in components), SCORE_DECIMALS))
    total = float(round(max(0.0, min(1.0, pre_penalty - negative_penalty)), SCORE_DECIMALS))
    return ProvisionalTypedScoreBreakdown(
        title=components[0],
        typed_attributes=components[1],
        price=components[2],
        image=components[3],
        review_quality=components[4],
        typed_requirement_count=source_breakdown.typed_requirement_count,
        typed_satisfied_weight=source_breakdown.typed_satisfied_weight,
        typed_total_weight=source_breakdown.typed_total_weight,
        available_base_weight=float(round(available_weight, SCORE_DECIMALS)),
        pre_penalty_score=pre_penalty,
        negative_penalty=negative_penalty,
        total_score=total,
        title_language=source_breakdown.title_language,
        negative_matches=source_breakdown.negative_matches,
    )


def rank_provisional_typed_product_batch(
    source_batch: TypedRankedProductBatch,
    counterfactual_batch: ProvisionalCounterfactualBatch,
    *,
    profile: ProvisionalTypedRankingProfile = PROVISIONAL_TYPED_RANKING_PROFILE,
) -> ProvisionalTypedRankedProductBatch:
    """Add the provisional image component while retaining the typed required-status sort."""
    try:
        if type(source_batch) is not TypedRankedProductBatch:
            raise TypeError("source typed batch type is invalid")
        if type(counterfactual_batch) is not ProvisionalCounterfactualBatch:
            raise TypeError("counterfactual batch type is invalid")
        validated_source = TypedRankedProductBatch.model_validate(source_batch)
        images = ProvisionalCounterfactualBatch.model_validate(counterfactual_batch)
        validated_profile = ProvisionalTypedRankingProfile.model_validate(profile)
        if validated_profile != PROVISIONAL_TYPED_RANKING_PROFILE:
            raise ValueError("provisional ranking profile is not approved")

        source_by_digest = {
            normalized_product_candidate_sha256(item.product): item
            for item in validated_source.products
        }
        image_by_digest = {item.normalized_product_sha256: item for item in images.candidates}
        if source_by_digest.keys() != image_by_digest.keys():
            raise ValueError("provisional image products do not match the ranking products")

        scored = tuple(
            (
                item,
                image_by_digest[product_sha256],
                _breakdown(item, image_by_digest[product_sha256]),
            )
            for product_sha256, item in source_by_digest.items()
        )
        ordered = sorted(
            scored,
            key=lambda value: typed_product_sort_key(
                value[0].evaluation,
                overall_score=value[2].total_score,
                response_index=value[0].product.provenance.response_index,
            ),
        )
        products = tuple(
            ProvisionalTypedRankedProduct(
                schema_version="5.0",
                rank=rank,
                product=source.product,
                evidence=source.evidence,
                evaluation=source.evaluation,
                image_component=image,
                breakdown=breakdown,
            )
            for rank, (source, image, breakdown) in enumerate(ordered, start=1)
        )
        return ProvisionalTypedRankedProductBatch(
            schema_version="5.0",
            ranking_profile_id=validated_profile.profile_id,
            ranking_profile_sha256=provisional_typed_ranking_profile_sha256(validated_profile),
            source_typed_ranked_product_batch_sha256=typed_ranked_product_batch_sha256(
                validated_source
            ),
            counterfactual_batch_sha256=provisional_counterfactual_batch_sha256(images),
            condition_set_sha256=images.condition_set_sha256,
            reference_set_sha256=images.reference_set_sha256,
            runtime_sha256=images.runtime_sha256,
            products=products,
        )
    except ProvisionalTypedRankingError:
        raise
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise ProvisionalTypedRankingError(_INVALID_RANKING_MESSAGE) from exc


def provisional_typed_ranked_product_batch_sha256(
    batch: ProvisionalTypedRankedProductBatch,
) -> str:
    try:
        validated = ProvisionalTypedRankedProductBatch.model_validate(batch)
        return _canonical_sha256(PROVISIONAL_TYPED_RANKED_BATCH_DOMAIN, validated)
    except (TypeError, ValueError, ValidationError) as exc:
        raise ProvisionalTypedRankingError(_INVALID_RANKING_MESSAGE) from exc
