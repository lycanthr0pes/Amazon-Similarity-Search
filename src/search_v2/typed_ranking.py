"""Rank products with registry-bound typed conditions without changing ranking v3."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Annotated
from typing import Literal
import unicodedata

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import ValidationError
from pydantic import field_validator
from pydantic import model_validator

from src.search_v2.intent import NormalizedSearchIntent
from src.search_v2.intent import search_intent_sha256
from src.search_v2.product_evidence import PRODUCT_EVIDENCE_PROFILE_V4
from src.search_v2.product_evidence import ProductEvidenceSet
from src.search_v2.product_evidence import build_product_evidence
from src.search_v2.product_evidence import normalized_product_candidate_sha256
from src.search_v2.product_evidence import product_evidence_profile_sha256
from src.search_v2.product_normalization import NormalizedProductBatch
from src.search_v2.product_normalization import NormalizedProductCandidate
from src.search_v2.product_normalization import normalized_product_batch_sha256
from src.search_v2.query_planner import SearchQueryPlan
from src.search_v2.query_planner import search_query_plan_sha256
from src.search_v2.ranking import EFFECTIVE_WEIGHT_DECIMALS
from src.search_v2.ranking import MAX_RANKED_PRODUCTS
from src.search_v2.ranking import MAX_SCORE_TERMS
from src.search_v2.ranking import RANKING_PROFILE_V3
from src.search_v2.ranking import SCORE_DECIMALS
from src.search_v2.ranking import ComponentReason
from src.search_v2.ranking import ComponentStatus
from src.search_v2.ranking import ScoreBreakdown
from src.search_v2.ranking import ScoreComponent
from src.search_v2.ranking import ScoreValue
from src.search_v2.ranking import rank_product_batch
from src.search_v2.ranking import ranked_product_batch_sha256
from src.search_v2.ranking import ranking_profile_sha256
from src.search_v2.requirement_evaluation import EvidenceObservation
from src.search_v2.requirement_evaluation import RequirementDecision
from src.search_v2.requirement_evaluation import TypedProductEvaluation
from src.search_v2.requirement_evaluation import adjudicate_requirement
from src.search_v2.requirement_evaluation import evaluate_typed_product
from src.search_v2.requirement_evaluation import typed_product_sort_key
from src.search_v2.typed_intent_adapter import TypedRequirementProposal
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_intent_adapter import typed_requirement_proposal_sha256
from src.search_v2.typed_requirements import DEFAULT_ATTRIBUTE_REGISTRY
from src.search_v2.typed_requirements import AttributeRegistry
from src.search_v2.typed_requirements import TypedRequirement
from src.search_v2.typed_requirements import attribute_definition
from src.search_v2.typed_requirements import attribute_registry_sha256
from src.search_v2.typed_requirements import typed_requirement_set_sha256


TYPED_RANKING_PROFILE_DOMAIN = b"amazon-explorer-typed-ranking-profile-v4\x00"
TYPED_RANKED_PRODUCT_BATCH_DOMAIN = b"amazon-explorer-typed-ranked-product-batch-v4\x00"
MAX_TYPED_WEIGHT = 6_400

_INVALID_RANKING_MESSAGE = "Typed ranking inputs did not match the ranking contract"

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
ScoreTerm = Annotated[str, StringConstraints(min_length=1, max_length=200)]
ScoreTerms = Annotated[
    tuple[ScoreTerm, ...],
    Field(max_length=MAX_SCORE_TERMS, repr=False),
]


class TypedRankingError(ValueError):
    """A fixed-message rejection for invalid typed-ranking boundary inputs."""


class StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


class TypedRankingProfile(StrictFrozenContract):
    schema_version: Literal["4.0"]
    profile_id: Literal["typed-ranking-v4"]
    source_ranking_profile_id: Literal["ranking-v3"]
    source_ranking_profile_sha256: Digest
    typed_score_version: Literal["registry-fixed-denominator-v1"]
    sort_key_version: Literal["required-preferred-total-response-v1"]
    title_weight: Literal[0.35]
    typed_attributes_weight: Literal[0.3]
    price_weight: Literal[0.2]
    image_weight: Literal[0.1]
    review_quality_weight: Literal[0.05]
    negative_match_penalty: Literal[0.2]
    max_negative_penalty: Literal[0.5]
    image_scoring_enabled: Literal[False]
    score_decimals: Literal[4]

    @model_validator(mode="after")
    def validate_profile(self) -> TypedRankingProfile:
        weights = (
            self.title_weight,
            self.typed_attributes_weight,
            self.price_weight,
            self.image_weight,
            self.review_quality_weight,
        )
        if not math.isclose(math.fsum(weights), 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("typed ranking base weights must total 1.0")
        if self.review_quality_weight >= min(weights[:-1]):
            raise ValueError("review quality weight must be the unique lowest weight")
        if self.source_ranking_profile_sha256 != ranking_profile_sha256(RANKING_PROFILE_V3):
            raise ValueError("source ranking profile binding is unsupported")
        return self


TYPED_RANKING_PROFILE_V4 = TypedRankingProfile(
    schema_version="4.0",
    profile_id="typed-ranking-v4",
    source_ranking_profile_id="ranking-v3",
    source_ranking_profile_sha256=ranking_profile_sha256(RANKING_PROFILE_V3),
    typed_score_version="registry-fixed-denominator-v1",
    sort_key_version="required-preferred-total-response-v1",
    title_weight=0.35,
    typed_attributes_weight=0.3,
    price_weight=0.2,
    image_weight=0.1,
    review_quality_weight=0.05,
    negative_match_penalty=0.2,
    max_negative_penalty=0.5,
    image_scoring_enabled=False,
    score_decimals=4,
)


def _text_identity(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _unique_terms(values: tuple[str, ...]) -> bool:
    identities = tuple(_text_identity(value) for value in values)
    return len(identities) == len(set(identities))


class TypedScoreBreakdown(StrictFrozenContract):
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
    negative_matches: ScoreTerms

    @field_validator(
        "available_base_weight",
        "pre_penalty_score",
        "negative_penalty",
        "total_score",
        mode="before",
    )
    @classmethod
    def validate_float_types(cls, value: object) -> object:
        if type(value) is not float or not math.isfinite(value):
            raise ValueError("typed score breakdown values must be finite floats")
        return value

    @model_validator(mode="after")
    def validate_breakdown(self) -> TypedScoreBreakdown:
        profile = TYPED_RANKING_PROFILE_V4
        components = (
            self.title,
            self.typed_attributes,
            self.price,
            self.image,
            self.review_quality,
        )
        expected_weights = (
            profile.title_weight,
            profile.typed_attributes_weight,
            profile.price_weight,
            profile.image_weight,
            profile.review_quality_weight,
        )
        if tuple(component.base_weight for component in components) != expected_weights:
            raise ValueError("typed score base weights do not match the profile")
        if self.image.status != "disabled":
            raise ValueError("image ranking must remain disabled")
        if self.review_quality.status == "disabled":
            raise ValueError("review quality ranking must not be disabled")

        if self.typed_requirement_count == 0:
            if (
                self.typed_total_weight != 0
                or self.typed_satisfied_weight != 0
                or self.typed_attributes.status != "missing"
                or self.typed_attributes.reason != "not_requested"
            ):
                raise ValueError("empty typed requirements must be not requested")
        elif (
            self.typed_total_weight <= 0
            or self.typed_satisfied_weight > self.typed_total_weight
            or self.typed_attributes.status != "available"
            or self.typed_attributes.reason != "scored"
            or self.typed_attributes.score
            != round(
                self.typed_satisfied_weight / self.typed_total_weight,
                SCORE_DECIMALS,
            )
        ):
            raise ValueError("typed attribute component is inconsistent")

        available = tuple(component for component in components if component.status == "available")
        expected_available_weight = round(
            math.fsum(component.base_weight for component in available),
            SCORE_DECIMALS,
        )
        if self.available_base_weight != expected_available_weight:
            raise ValueError("available typed score weight is inconsistent")
        effective_total = math.fsum(component.effective_weight for component in available)
        expected_effective_total = 1.0 if available else 0.0
        if not math.isclose(
            effective_total,
            expected_effective_total,
            rel_tol=0.0,
            abs_tol=3e-6,
        ):
            raise ValueError("effective typed score weights are not normalized")

        expected_pre_penalty = round(
            math.fsum(component.contribution for component in components),
            SCORE_DECIMALS,
        )
        if self.pre_penalty_score != expected_pre_penalty:
            raise ValueError("typed pre-penalty score is inconsistent")
        expected_penalty = round(
            min(
                profile.max_negative_penalty,
                len(self.negative_matches) * profile.negative_match_penalty,
            ),
            SCORE_DECIMALS,
        )
        if self.negative_penalty != expected_penalty:
            raise ValueError("typed negative penalty is inconsistent")
        expected_total = round(
            max(0.0, min(1.0, self.pre_penalty_score - self.negative_penalty)),
            SCORE_DECIMALS,
        )
        if self.total_score != expected_total:
            raise ValueError("typed total score is inconsistent")

        if self.title.status == "available" and self.title_language is None:
            raise ValueError("available title score requires a language")
        if self.title.status != "available" and self.title_language is not None:
            raise ValueError("unavailable title score must not select a language")
        if not _unique_terms(self.negative_matches):
            raise ValueError("negative matches must be unique")
        return self


class TypedRankedProduct(StrictFrozenContract):
    schema_version: Literal["4.0"]
    rank: Annotated[int, Field(ge=1, le=MAX_RANKED_PRODUCTS)]
    product: NormalizedProductCandidate = Field(repr=False)
    evidence: ProductEvidenceSet = Field(repr=False)
    evaluation: TypedProductEvaluation
    breakdown: TypedScoreBreakdown

    @model_validator(mode="after")
    def validate_product_bindings(self) -> TypedRankedProduct:
        product_digest = normalized_product_candidate_sha256(self.product)
        if (
            self.evidence.product_sha256 != product_digest
            or self.evaluation.product_sha256 != product_digest
        ):
            raise ValueError("typed ranked product binding is inconsistent")
        return self


class TypedRankedProductBatch(StrictFrozenContract):
    schema_version: Literal["4.0"]
    ranking_profile_id: Literal["typed-ranking-v4"]
    ranking_profile_sha256: Digest
    source_ranking_profile_id: Literal["ranking-v3"]
    source_ranking_profile_sha256: Digest
    source_ranked_product_batch_sha256: Digest
    intent_sha256: Digest
    query_plan_sha256: Digest
    normalized_product_batch_sha256: Digest
    typed_requirement_proposal_sha256: Digest
    registry_sha256: Digest
    requirement_set_sha256: Digest
    evidence_profile_sha256: Digest
    proposal: TypedRequirementProposal = Field(repr=False)
    products: Annotated[
        tuple[TypedRankedProduct, ...],
        Field(max_length=MAX_RANKED_PRODUCTS),
    ]

    @model_validator(mode="after")
    def validate_ranked_products(self) -> TypedRankedProductBatch:
        if (
            self.ranking_profile_sha256 != typed_ranking_profile_sha256()
            or self.source_ranking_profile_sha256 != ranking_profile_sha256()
        ):
            raise ValueError("typed ranking profile binding is unsupported")
        if self.proposal.status != "ready" or self.proposal.issues:
            raise ValueError("typed ranking requires a ready proposal")
        if (
            self.typed_requirement_proposal_sha256
            != typed_requirement_proposal_sha256(self.proposal)
            or self.intent_sha256 != self.proposal.intent_sha256
            or self.registry_sha256 != self.proposal.registry_sha256
            or self.requirement_set_sha256 != self.proposal.requirement_set_sha256
        ):
            raise ValueError("typed proposal binding is inconsistent")

        registry_digest = attribute_registry_sha256(self.proposal.registry)
        requirement_digest = typed_requirement_set_sha256(
            self.proposal.requirements,
            registry=self.proposal.registry,
        )
        if (
            self.registry_sha256 != registry_digest
            or self.requirement_set_sha256 != requirement_digest
            or self.evidence_profile_sha256
            != product_evidence_profile_sha256(PRODUCT_EVIDENCE_PROFILE_V4)
        ):
            raise ValueError("typed domain binding is unsupported")
        if tuple(item.rank for item in self.products) != tuple(range(1, len(self.products) + 1)):
            raise ValueError("typed ranked products must have contiguous ranks")

        response_indexes = tuple(item.product.provenance.response_index for item in self.products)
        if len(response_indexes) != len(set(response_indexes)):
            raise ValueError("typed ranked products must have unique response indexes")

        for item in self.products:
            if item.product.provenance.query_plan_sha256 != self.query_plan_sha256:
                raise ValueError("typed ranked product query binding is inconsistent")
            expected_evidence = build_product_evidence(
                item.product,
                self.proposal.requirements,
                registry=self.proposal.registry,
            )
            if item.evidence != expected_evidence:
                raise ValueError("typed ranked product evidence is not reproducible")
            expected_evaluation = _evaluate_product(
                self.proposal.requirements,
                expected_evidence,
                registry=self.proposal.registry,
            )
            if item.evaluation != expected_evaluation:
                raise ValueError("typed ranked product evaluation is not reproducible")
            count, satisfied_weight, total_weight, score = _typed_score(
                self.proposal.requirements,
                expected_evaluation,
                registry=self.proposal.registry,
            )
            component_score = item.breakdown.typed_attributes.score
            if (
                item.breakdown.typed_requirement_count != count
                or item.breakdown.typed_satisfied_weight != satisfied_weight
                or item.breakdown.typed_total_weight != total_weight
                or component_score != score
            ):
                raise ValueError("typed ranked product score is not reproducible")

        sort_keys = tuple(
            typed_product_sort_key(
                item.evaluation,
                overall_score=item.breakdown.total_score,
                response_index=item.product.provenance.response_index,
            )
            for item in self.products
        )
        if sort_keys != tuple(sorted(sort_keys)):
            raise ValueError("typed ranked products are not in canonical order")
        return self


@dataclass(frozen=True, slots=True)
class _RawComponent:
    status: ComponentStatus
    reason: ComponentReason
    score: float | None


def _canonical_model_sha256(domain: bytes, value: BaseModel) -> str:
    canonical = json.dumps(
        value.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(domain + canonical).hexdigest()


def typed_ranking_profile_sha256(
    profile: TypedRankingProfile = TYPED_RANKING_PROFILE_V4,
) -> str:
    try:
        if type(profile) is not TypedRankingProfile:
            raise TypeError("profile must be an exact TypedRankingProfile")
        validated = TypedRankingProfile.model_validate(profile)
        return _canonical_model_sha256(TYPED_RANKING_PROFILE_DOMAIN, validated)
    except (TypeError, ValueError, ValidationError):
        raise TypedRankingError(_INVALID_RANKING_MESSAGE) from None


def _observations_for(
    evidence: ProductEvidenceSet,
    requirement: TypedRequirement,
) -> tuple[EvidenceObservation, ...]:
    return tuple(
        item for item in evidence.observations if item.requirement_id == requirement.requirement_id
    )


def _evaluate_product(
    requirements: tuple[TypedRequirement, ...],
    evidence: ProductEvidenceSet,
    *,
    registry: AttributeRegistry = DEFAULT_ATTRIBUTE_REGISTRY,
) -> TypedProductEvaluation:
    decisions = tuple(
        adjudicate_requirement(
            requirement,
            product_sha256=evidence.product_sha256,
            observations=_observations_for(evidence, requirement),
            registry=registry,
        )
        for requirement in requirements
    )
    return evaluate_typed_product(
        requirements,
        decisions,
        product_sha256=evidence.product_sha256,
        registry=registry,
    )


def _typed_score(
    requirements: tuple[TypedRequirement, ...],
    evaluation: TypedProductEvaluation,
    *,
    registry: AttributeRegistry = DEFAULT_ATTRIBUTE_REGISTRY,
) -> tuple[int, int, int, float | None]:
    if not requirements:
        return 0, 0, 0, None

    decisions: dict[str, RequirementDecision] = {
        item.requirement_id: item for item in evaluation.decisions
    }
    total_weight = 0
    satisfied_weight = 0
    for requirement in requirements:
        weight = attribute_definition(requirement.attribute_key, registry=registry).default_weight
        total_weight += weight
        state = decisions[requirement.requirement_id].state
        satisfied = state == "mismatch" if requirement.strength == "excluded" else state == "match"
        if satisfied:
            satisfied_weight += weight
    score = round(satisfied_weight / total_weight, SCORE_DECIMALS)
    return len(requirements), satisfied_weight, total_weight, float(score)


def _component(
    raw: _RawComponent,
    *,
    base_weight: float,
    available_base_weight: float,
) -> ScoreComponent:
    if raw.status != "available":
        return ScoreComponent(
            status=raw.status,
            reason=raw.reason,
            score=None,
            base_weight=float(base_weight),
            effective_weight=0.0,
            contribution=0.0,
        )
    if raw.score is None or available_base_weight <= 0.0:
        raise ValueError("available score component is missing its score")
    score = round(max(0.0, min(1.0, raw.score)), SCORE_DECIMALS)
    effective_weight = round(
        base_weight / available_base_weight,
        EFFECTIVE_WEIGHT_DECIMALS,
    )
    return ScoreComponent(
        status="available",
        reason="scored",
        score=float(score),
        base_weight=float(base_weight),
        effective_weight=float(effective_weight),
        contribution=float(round(score * effective_weight, SCORE_DECIMALS)),
    )


def _raw_source_component(component: ScoreComponent) -> _RawComponent:
    return _RawComponent(
        status=component.status,
        reason=component.reason,
        score=component.score,
    )


def _score_product(
    requirements: tuple[TypedRequirement, ...],
    evaluation: TypedProductEvaluation,
    source_breakdown: ScoreBreakdown,
    *,
    registry: AttributeRegistry = DEFAULT_ATTRIBUTE_REGISTRY,
) -> TypedScoreBreakdown:
    count, satisfied_weight, total_weight, typed_score = _typed_score(
        requirements,
        evaluation,
        registry=registry,
    )
    raw_typed = _RawComponent(
        status="missing" if typed_score is None else "available",
        reason="not_requested" if typed_score is None else "scored",
        score=typed_score,
    )
    raw_components = (
        _raw_source_component(source_breakdown.title),
        raw_typed,
        _raw_source_component(source_breakdown.price),
        _raw_source_component(source_breakdown.image),
        _raw_source_component(source_breakdown.review_quality),
    )
    profile = TYPED_RANKING_PROFILE_V4
    base_weights = (
        profile.title_weight,
        profile.typed_attributes_weight,
        profile.price_weight,
        profile.image_weight,
        profile.review_quality_weight,
    )
    available_base_weight = math.fsum(
        weight
        for raw, weight in zip(raw_components, base_weights, strict=True)
        if raw.status == "available"
    )
    components = tuple(
        _component(
            raw,
            base_weight=weight,
            available_base_weight=available_base_weight,
        )
        for raw, weight in zip(raw_components, base_weights, strict=True)
    )
    negative_matches = tuple(source_breakdown.negative_matches)
    negative_penalty = round(
        min(
            profile.max_negative_penalty,
            len(negative_matches) * profile.negative_match_penalty,
        ),
        SCORE_DECIMALS,
    )
    pre_penalty_score = round(
        math.fsum(component.contribution for component in components),
        SCORE_DECIMALS,
    )
    total_score = round(
        max(0.0, min(1.0, pre_penalty_score - negative_penalty)),
        SCORE_DECIMALS,
    )
    return TypedScoreBreakdown(
        title=components[0],
        typed_attributes=components[1],
        price=components[2],
        image=components[3],
        review_quality=components[4],
        typed_requirement_count=count,
        typed_satisfied_weight=satisfied_weight,
        typed_total_weight=total_weight,
        available_base_weight=float(round(available_base_weight, SCORE_DECIMALS)),
        pre_penalty_score=float(pre_penalty_score),
        negative_penalty=float(negative_penalty),
        total_score=float(total_score),
        title_language=source_breakdown.title_language,
        negative_matches=negative_matches,
    )


def _raise_invalid_ranking() -> None:
    raise TypedRankingError(_INVALID_RANKING_MESSAGE) from None


def rank_typed_product_batch(
    intent: NormalizedSearchIntent,
    query_plan: SearchQueryPlan,
    product_batch: NormalizedProductBatch,
    proposal: TypedRequirementProposal,
    *,
    profile: TypedRankingProfile = TYPED_RANKING_PROFILE_V4,
) -> TypedRankedProductBatch:
    try:
        if type(intent) is not NormalizedSearchIntent:
            raise TypeError("intent must be an exact NormalizedSearchIntent")
        if type(query_plan) is not SearchQueryPlan:
            raise TypeError("query plan must be an exact SearchQueryPlan")
        if type(product_batch) is not NormalizedProductBatch:
            raise TypeError("product batch must be an exact NormalizedProductBatch")
        if type(proposal) is not TypedRequirementProposal:
            raise TypeError("proposal must be an exact TypedRequirementProposal")
        if type(profile) is not TypedRankingProfile:
            raise TypeError("profile must be an exact TypedRankingProfile")

        validated_intent = NormalizedSearchIntent.model_validate(intent)
        validated_query_plan = SearchQueryPlan.model_validate(query_plan)
        validated_product_batch = NormalizedProductBatch.model_validate(product_batch)
        validated_proposal = TypedRequirementProposal.model_validate(proposal)
        validated_profile = TypedRankingProfile.model_validate(profile)
        intent_digest = search_intent_sha256(validated_intent)
        query_plan_digest = search_query_plan_sha256(validated_query_plan)
        product_batch_digest = normalized_product_batch_sha256(validated_product_batch)
        expected_proposal = build_typed_requirement_proposal(validated_intent)
        if (
            validated_profile != TYPED_RANKING_PROFILE_V4
            or typed_ranking_profile_sha256(validated_profile) != typed_ranking_profile_sha256()
            or validated_query_plan.intent_sha256 != intent_digest
            or validated_product_batch.query_plan_sha256 != query_plan_digest
            or validated_proposal != expected_proposal
            or validated_proposal.status != "ready"
            or validated_proposal.issues
        ):
            _raise_invalid_ranking()

        source_ranking = rank_product_batch(
            validated_intent,
            validated_query_plan,
            validated_product_batch,
        )
        source_by_index = {
            item.product.provenance.response_index: item for item in source_ranking.products
        }

        scored: list[
            tuple[
                NormalizedProductCandidate,
                ProductEvidenceSet,
                TypedProductEvaluation,
                TypedScoreBreakdown,
            ]
        ] = []
        for product in validated_product_batch.products:
            evidence = build_product_evidence(
                product, validated_proposal.requirements, registry=validated_proposal.registry
            )
            evaluation = _evaluate_product(
                validated_proposal.requirements, evidence, registry=validated_proposal.registry
            )
            source = source_by_index[product.provenance.response_index]
            breakdown = _score_product(
                validated_proposal.requirements,
                evaluation,
                source.breakdown,
                registry=validated_proposal.registry,
            )
            scored.append((product, evidence, evaluation, breakdown))

        ordered = sorted(
            scored,
            key=lambda item: typed_product_sort_key(
                item[2],
                overall_score=item[3].total_score,
                response_index=item[0].provenance.response_index,
            ),
        )
        ranked_products = tuple(
            TypedRankedProduct(
                schema_version="4.0",
                rank=rank,
                product=product,
                evidence=evidence,
                evaluation=evaluation,
                breakdown=breakdown,
            )
            for rank, (product, evidence, evaluation, breakdown) in enumerate(
                ordered,
                start=1,
            )
        )
        return TypedRankedProductBatch(
            schema_version="4.0",
            ranking_profile_id=validated_profile.profile_id,
            ranking_profile_sha256=typed_ranking_profile_sha256(validated_profile),
            source_ranking_profile_id=validated_profile.source_ranking_profile_id,
            source_ranking_profile_sha256=validated_profile.source_ranking_profile_sha256,
            source_ranked_product_batch_sha256=ranked_product_batch_sha256(source_ranking),
            intent_sha256=intent_digest,
            query_plan_sha256=query_plan_digest,
            normalized_product_batch_sha256=product_batch_digest,
            typed_requirement_proposal_sha256=typed_requirement_proposal_sha256(validated_proposal),
            registry_sha256=validated_proposal.registry_sha256,
            requirement_set_sha256=validated_proposal.requirement_set_sha256,
            evidence_profile_sha256=product_evidence_profile_sha256(),
            proposal=validated_proposal,
            products=ranked_products,
        )
    except TypedRankingError:
        raise
    except (AssertionError, KeyError, TypeError, ValidationError, ValueError):
        _raise_invalid_ranking()


def typed_ranked_product_batch_sha256(batch: TypedRankedProductBatch) -> str:
    try:
        if type(batch) is not TypedRankedProductBatch:
            raise TypeError("batch must be an exact TypedRankedProductBatch")
        validated = TypedRankedProductBatch.model_validate(batch)
        return _canonical_model_sha256(TYPED_RANKED_PRODUCT_BATCH_DOMAIN, validated)
    except TypedRankingError:
        raise
    except (TypeError, ValidationError, ValueError):
        raise TypedRankingError(_INVALID_RANKING_MESSAGE) from None
