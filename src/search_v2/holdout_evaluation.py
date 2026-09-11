"""Deterministic offline evaluation contracts for unseen typed-ranking data."""

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
from pydantic import field_validator
from pydantic import model_validator

from src.search_v2.intent import NormalizedSearchIntent
from src.search_v2.intent import search_intent_sha256
from src.search_v2.product_evidence import normalized_product_candidate_sha256
from src.search_v2.query_planner import SearchQueryPlan
from src.search_v2.query_planner import search_query_plan_sha256
from src.search_v2.requirement_evaluation import DecisionState
from src.search_v2.requirement_evaluation import RequiredStatus
from src.search_v2.typed_intent_adapter import TypedRequirementProposal
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_intent_adapter import typed_requirement_proposal_sha256
from src.search_v2.typed_ranking import TYPED_RANKING_PROFILE_V4
from src.search_v2.typed_ranking import TypedRankedProductBatch
from src.search_v2.typed_ranking import typed_ranked_product_batch_sha256
from src.search_v2.typed_ranking import typed_ranking_profile_sha256
from src.search_v2.typed_requirements import DEFAULT_ATTRIBUTE_REGISTRY
from src.search_v2.typed_requirements import Identifier
from src.search_v2.typed_requirements import TypedRequirement
from src.search_v2.typed_requirements import TypedRequirementDraft
from src.search_v2.typed_requirements import TypedRequirementError
from src.search_v2.typed_requirements import attribute_definition
from src.search_v2.typed_requirements import attribute_registry_sha256
from src.search_v2.typed_requirements import normalize_typed_requirements


HOLDOUT_EVALUATION_PROFILE_DOMAIN = b"amazon-explorer-holdout-evaluation-profile-v1\x00"
HOLDOUT_CONDITION_IDENTITY_DOMAIN = b"amazon-explorer-holdout-condition-identity-v1\x00"
HOLDOUT_GROUND_TRUTH_DATASET_DOMAIN = b"amazon-explorer-holdout-ground-truth-v1\x00"
HOLDOUT_PREDICTION_SET_DOMAIN = b"amazon-explorer-holdout-prediction-set-v1\x00"
HOLDOUT_EVALUATION_REPORT_DOMAIN = b"amazon-explorer-holdout-evaluation-report-v1\x00"

MAX_HOLDOUT_CASES = 128
MAX_EXPECTED_PRODUCTS = 48
MAX_CATEGORIES = 64
METRIC_DECIMALS = 6
KNOWN_DEVELOPMENT_CASE_IDS = frozenset(("case1", "case2", "case3"))

_INVALID_EVALUATION_MESSAGE = "Holdout evaluation inputs did not match the evaluation contract"

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Count = Annotated[int, Field(ge=0, le=1_000_000)]
Ratio = Annotated[float, Field(ge=0.0, le=1.0)]
RelevanceGrade = Annotated[int, Field(ge=0, le=3)]
Rank = Annotated[int, Field(ge=1, le=MAX_EXPECTED_PRODUCTS)]
QueryLanguage = Literal["ja", "en", "mixed"]
PredictionStatus = Literal["ranked", "blocking", "failed"]
CoverageIssue = Literal[
    "too_few_categories",
    "too_few_cases_per_category",
    "too_few_products_per_case",
    "too_few_conditions_per_case",
    "missing_hard_contradiction_labels",
    "missing_uncertainty_labels",
]


class HoldoutEvaluationError(ValueError):
    """A fixed-message rejection for invalid holdout evaluation inputs."""


class StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


def _canonical_model_sha256(domain: bytes, value: BaseModel) -> str:
    canonical = json.dumps(
        value.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(domain + canonical).hexdigest()


def _raise_invalid_evaluation() -> None:
    raise HoldoutEvaluationError(_INVALID_EVALUATION_MESSAGE) from None


def _validated_requirement(requirement: TypedRequirement) -> TypedRequirement:
    if type(requirement) is not TypedRequirement:
        raise TypeError("requirement must be an exact TypedRequirement")
    validated = TypedRequirement.model_validate(requirement)
    if validated.registry_sha256 != attribute_registry_sha256(DEFAULT_ATTRIBUTE_REGISTRY):
        raise ValueError("requirement registry binding is unsupported")
    normalized = normalize_typed_requirements(
        (
            TypedRequirementDraft(
                requirement_id=validated.requirement_id,
                attribute_key=validated.attribute_key,
                operator=validated.operator,
                expected_value=validated.expected_value,
                strength=validated.strength,
            ),
        ),
        registry=DEFAULT_ATTRIBUTE_REGISTRY,
    )[0]
    if normalized != validated:
        raise ValueError("requirement is not canonical")
    return validated


def holdout_condition_identity_sha256(requirement: TypedRequirement) -> str:
    """Hash a canonical condition without its annotator-owned condition ID."""

    try:
        validated = _validated_requirement(requirement)
        payload = validated.model_dump(mode="json", exclude={"requirement_id"})
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(HOLDOUT_CONDITION_IDENTITY_DOMAIN + canonical).hexdigest()
    except (TypeError, ValueError, ValidationError, TypedRequirementError):
        _raise_invalid_evaluation()


class HoldoutEvaluationProfile(StrictFrozenContract):
    schema_version: Literal["1.0"]
    profile_id: Literal["typed-ranking-holdout-v1"]
    ranking_profile_id: Literal["typed-ranking-v4"]
    ranking_profile_sha256: Digest
    condition_identity_version: Literal["canonical-requirement-without-id-v1"]
    condition_metric_version: Literal["set-precision-recall-f1-v1"]
    decision_metric_version: Literal["expected-matrix-exact-state-v1"]
    safety_metric_version: Literal["hard-contradiction-and-uncertainty-v1"]
    ranking_metric_version: Literal["strict-pairwise-and-full-list-ndcg-v1"]
    aggregation_version: Literal["label-micro-case-and-category-macro-v1"]
    prediction_projection_version: Literal["digests-states-ranks-only-v1"]
    minimum_categories: Literal[2]
    minimum_cases_per_category: Literal[2]
    minimum_products_per_case: Literal[3]
    minimum_conditions_per_case: Literal[1]
    minimum_hard_contradiction_labels: Literal[1]
    minimum_uncertainty_labels: Literal[1]
    image_scoring_enabled: Literal[False]
    metric_decimals: Literal[6]

    @model_validator(mode="after")
    def validate_profile(self) -> HoldoutEvaluationProfile:
        if (
            self.ranking_profile_sha256 != typed_ranking_profile_sha256()
            or self.ranking_profile_id != TYPED_RANKING_PROFILE_V4.profile_id
        ):
            raise ValueError("holdout ranking profile binding is unsupported")
        return self


HOLDOUT_EVALUATION_PROFILE_V1 = HoldoutEvaluationProfile(
    schema_version="1.0",
    profile_id="typed-ranking-holdout-v1",
    ranking_profile_id="typed-ranking-v4",
    ranking_profile_sha256=typed_ranking_profile_sha256(),
    condition_identity_version="canonical-requirement-without-id-v1",
    condition_metric_version="set-precision-recall-f1-v1",
    decision_metric_version="expected-matrix-exact-state-v1",
    safety_metric_version="hard-contradiction-and-uncertainty-v1",
    ranking_metric_version="strict-pairwise-and-full-list-ndcg-v1",
    aggregation_version="label-micro-case-and-category-macro-v1",
    prediction_projection_version="digests-states-ranks-only-v1",
    minimum_categories=2,
    minimum_cases_per_category=2,
    minimum_products_per_case=3,
    minimum_conditions_per_case=1,
    minimum_hard_contradiction_labels=1,
    minimum_uncertainty_labels=1,
    image_scoring_enabled=False,
    metric_decimals=METRIC_DECIMALS,
)


def holdout_evaluation_profile_sha256(
    profile: HoldoutEvaluationProfile = HOLDOUT_EVALUATION_PROFILE_V1,
) -> str:
    try:
        if type(profile) is not HoldoutEvaluationProfile:
            raise TypeError("profile must be an exact HoldoutEvaluationProfile")
        validated = HoldoutEvaluationProfile.model_validate(profile)
        return _canonical_model_sha256(HOLDOUT_EVALUATION_PROFILE_DOMAIN, validated)
    except (TypeError, ValueError, ValidationError):
        _raise_invalid_evaluation()


class HoldoutExpectedCondition(StrictFrozenContract):
    schema_version: Literal["1.0"]
    condition_id: Identifier
    evaluation_scope: Literal["typed_exact"]
    requirement: TypedRequirement = Field(repr=False)
    condition_identity_sha256: Digest

    @model_validator(mode="after")
    def validate_condition(self) -> HoldoutExpectedCondition:
        validated = _validated_requirement(self.requirement)
        definition = attribute_definition(
            validated.attribute_key,
            registry=DEFAULT_ATTRIBUTE_REGISTRY,
        )
        if validated.requirement_id != self.condition_id:
            raise ValueError("ground-truth condition ID is inconsistent")
        if definition.value_type == "semantic":
            raise ValueError("semantic conditions require a separate evaluation profile")
        if self.condition_identity_sha256 != holdout_condition_identity_sha256(validated):
            raise ValueError("ground-truth condition identity is inconsistent")
        return self


class HoldoutExpectedDecision(StrictFrozenContract):
    condition_id: Identifier
    expected_state: DecisionState


class HoldoutExpectedProduct(StrictFrozenContract):
    product_sha256: Digest
    relevance_grade: RelevanceGrade
    decisions: Annotated[tuple[HoldoutExpectedDecision, ...], Field(max_length=64)]

    @model_validator(mode="after")
    def validate_decisions(self) -> HoldoutExpectedProduct:
        identifiers = tuple(item.condition_id for item in self.decisions)
        if identifiers != tuple(sorted(identifiers)) or len(identifiers) != len(set(identifiers)):
            raise ValueError("expected decisions must have unique canonical condition IDs")
        return self


class HoldoutGroundTruthCase(StrictFrozenContract):
    schema_version: Literal["1.0"]
    case_id: Identifier
    category: Identifier
    query_language: QueryLanguage
    source_input_sha256: Digest
    expected_conditions: Annotated[
        tuple[HoldoutExpectedCondition, ...],
        Field(max_length=64, repr=False),
    ]
    expected_products: Annotated[
        tuple[HoldoutExpectedProduct, ...],
        Field(min_length=2, max_length=MAX_EXPECTED_PRODUCTS, repr=False),
    ]

    @model_validator(mode="after")
    def validate_case(self) -> HoldoutGroundTruthCase:
        if self.case_id in KNOWN_DEVELOPMENT_CASE_IDS:
            raise ValueError("known development case ID is not a holdout ID")
        condition_ids = tuple(item.condition_id for item in self.expected_conditions)
        condition_digests = tuple(
            item.condition_identity_sha256 for item in self.expected_conditions
        )
        if condition_ids != tuple(sorted(condition_ids)) or len(condition_ids) != len(
            set(condition_ids)
        ):
            raise ValueError("expected conditions must have unique canonical IDs")
        if len(condition_digests) != len(set(condition_digests)):
            raise ValueError("expected conditions must have unique identities")

        product_digests = tuple(item.product_sha256 for item in self.expected_products)
        if product_digests != tuple(sorted(product_digests)) or len(product_digests) != len(
            set(product_digests)
        ):
            raise ValueError("expected products must have unique canonical digests")
        if len({item.relevance_grade for item in self.expected_products}) < 2:
            raise ValueError("expected products require at least two relevance grades")
        if max(item.relevance_grade for item in self.expected_products) <= 0:
            raise ValueError("expected products require a relevant candidate")
        for product in self.expected_products:
            if tuple(item.condition_id for item in product.decisions) != condition_ids:
                raise ValueError("expected decision matrix must cover every condition")
        return self


class HoldoutGroundTruthDataset(StrictFrozenContract):
    schema_version: Literal["1.0"]
    dataset_id: Identifier
    dataset_role: Literal["holdout"]
    provenance_reference_id: Identifier
    content_policy: Literal["identifiers-digests-labels-only-v1"]
    cases: Annotated[
        tuple[HoldoutGroundTruthCase, ...],
        Field(min_length=1, max_length=MAX_HOLDOUT_CASES, repr=False),
    ]

    @model_validator(mode="after")
    def validate_cases(self) -> HoldoutGroundTruthDataset:
        identifiers = tuple(item.case_id for item in self.cases)
        if identifiers != tuple(sorted(identifiers)) or len(identifiers) != len(set(identifiers)):
            raise ValueError("ground-truth cases must have unique canonical IDs")
        if len({item.category for item in self.cases}) > MAX_CATEGORIES:
            raise ValueError("ground-truth dataset contains too many categories")
        return self


def holdout_ground_truth_dataset_sha256(dataset: HoldoutGroundTruthDataset) -> str:
    try:
        if type(dataset) is not HoldoutGroundTruthDataset:
            raise TypeError("dataset must be an exact HoldoutGroundTruthDataset")
        validated = HoldoutGroundTruthDataset.model_validate(dataset)
        return _canonical_model_sha256(HOLDOUT_GROUND_TRUTH_DATASET_DOMAIN, validated)
    except (TypeError, ValueError, ValidationError, TypedRequirementError):
        _raise_invalid_evaluation()


class HoldoutPredictedCondition(StrictFrozenContract):
    condition_identity_sha256: Digest


class HoldoutPredictedDecision(StrictFrozenContract):
    condition_identity_sha256: Digest
    state: DecisionState


class HoldoutPredictedProduct(StrictFrozenContract):
    product_sha256: Digest
    rank: Rank
    required_status: RequiredStatus
    decisions: Annotated[tuple[HoldoutPredictedDecision, ...], Field(max_length=64)]

    @model_validator(mode="after")
    def validate_decisions(self) -> HoldoutPredictedProduct:
        identities = tuple(item.condition_identity_sha256 for item in self.decisions)
        if identities != tuple(sorted(identities)) or len(identities) != len(set(identities)):
            raise ValueError("predicted decisions must have unique canonical condition identities")
        return self


class HoldoutCasePrediction(StrictFrozenContract):
    schema_version: Literal["1.0"]
    case_id: Identifier
    source_input_sha256: Digest
    status: PredictionStatus
    intent_sha256: Digest | None
    query_plan_sha256: Digest | None
    proposal_sha256: Digest | None
    ranked_batch_sha256: Digest | None
    predicted_conditions: Annotated[
        tuple[HoldoutPredictedCondition, ...],
        Field(max_length=64),
    ]
    ranked_products: Annotated[
        tuple[HoldoutPredictedProduct, ...],
        Field(max_length=MAX_EXPECTED_PRODUCTS),
    ]
    failure_code: Identifier | None

    @model_validator(mode="after")
    def validate_artifacts(self) -> HoldoutCasePrediction:
        condition_identities = tuple(
            item.condition_identity_sha256 for item in self.predicted_conditions
        )
        if condition_identities != tuple(sorted(condition_identities)) or len(
            condition_identities
        ) != len(set(condition_identities)):
            raise ValueError("predicted conditions must have unique canonical identities")
        product_digests = tuple(item.product_sha256 for item in self.ranked_products)
        if product_digests != tuple(sorted(product_digests)) or len(product_digests) != len(
            set(product_digests)
        ):
            raise ValueError("predicted products must have unique canonical digests")
        if {item.rank for item in self.ranked_products} != set(
            range(1, len(self.ranked_products) + 1)
        ):
            raise ValueError("predicted products must have contiguous unique ranks")
        for product in self.ranked_products:
            if tuple(item.condition_identity_sha256 for item in product.decisions) != (
                condition_identities
            ):
                raise ValueError("predicted decision matrix must cover every condition")

        artifact_digests = (
            self.intent_sha256,
            self.query_plan_sha256,
            self.proposal_sha256,
        )
        if (
            self.status != "blocking"
            and any(item is None for item in artifact_digests)
            and any(item is not None for item in artifact_digests)
        ):
            raise ValueError("prediction artifact digests are all-or-none")
        if self.status == "blocking" and (
            self.intent_sha256 is None or self.proposal_sha256 is None
        ):
            raise ValueError("blocking prediction requires intent and proposal bindings")
        if self.status == "ranked":
            if (
                any(item is None for item in artifact_digests)
                or self.ranked_batch_sha256 is None
                or self.failure_code is not None
            ):
                raise ValueError("ranked prediction artifacts are inconsistent")
        elif self.status == "blocking":
            if (
                self.ranked_batch_sha256 is not None
                or self.ranked_products
                or self.failure_code is not None
            ):
                raise ValueError("blocking prediction artifacts are inconsistent")
        elif (
            self.ranked_batch_sha256 is not None
            or self.ranked_products
            or self.failure_code is None
        ):
            raise ValueError("failed prediction artifacts are inconsistent")
        if self.intent_sha256 is None and self.predicted_conditions:
            raise ValueError("prediction conditions require bound intent artifacts")
        return self


def build_holdout_case_prediction(
    *,
    case_id: str,
    source_input_sha256: str,
    status: str,
    intent: NormalizedSearchIntent | None,
    query_plan: SearchQueryPlan | None,
    proposal: TypedRequirementProposal | None,
    ranked_batch: TypedRankedProductBatch | None,
    failure_code: str | None,
) -> HoldoutCasePrediction:
    """Validate full runtime artifacts and project only bounded evaluation facts."""

    try:
        artifacts = (intent, query_plan, proposal)
        if status == "blocking":
            if intent is None or proposal is None:
                raise ValueError("blocking prediction requires intent and proposal artifacts")
        elif any(item is None for item in artifacts) and any(
            item is not None for item in artifacts
        ):
            raise ValueError("prediction runtime artifacts are all-or-none")
        if all(item is None for item in artifacts):
            if status != "failed" or ranked_batch is not None or failure_code is None:
                raise ValueError("artifact-free prediction must be failed")
            return HoldoutCasePrediction(
                schema_version="1.0",
                case_id=case_id,
                source_input_sha256=source_input_sha256,
                status="failed",
                intent_sha256=None,
                query_plan_sha256=None,
                proposal_sha256=None,
                ranked_batch_sha256=None,
                predicted_conditions=(),
                ranked_products=(),
                failure_code=failure_code,
            )

        if type(intent) is not NormalizedSearchIntent:
            raise TypeError("prediction intent must be exact")
        if type(proposal) is not TypedRequirementProposal:
            raise TypeError("prediction proposal must be exact")
        validated_intent = NormalizedSearchIntent.model_validate(intent)
        validated_proposal = TypedRequirementProposal.model_validate(proposal)
        intent_digest = search_intent_sha256(validated_intent)
        validated_query: SearchQueryPlan | None = None
        query_digest: str | None = None
        if query_plan is not None:
            if type(query_plan) is not SearchQueryPlan:
                raise TypeError("prediction query plan must be exact")
            validated_query = SearchQueryPlan.model_validate(query_plan)
            query_digest = search_query_plan_sha256(validated_query)
        if (
            validated_intent.provenance.source_input_sha256 != source_input_sha256
            or validated_proposal != build_typed_requirement_proposal(validated_intent)
            or (validated_query is not None and validated_query.intent_sha256 != intent_digest)
        ):
            raise ValueError("prediction runtime artifacts are inconsistent")

        requirement_identities = {
            item.requirement_id: holdout_condition_identity_sha256(item)
            for item in validated_proposal.requirements
        }
        predicted_conditions = tuple(
            HoldoutPredictedCondition(condition_identity_sha256=identity)
            for identity in sorted(requirement_identities.values())
        )
        ranked_products: tuple[HoldoutPredictedProduct, ...] = ()
        ranked_batch_digest: str | None = None
        if ranked_batch is not None:
            if validated_query is None or query_digest is None:
                raise ValueError("ranked prediction requires a query plan")
            if type(ranked_batch) is not TypedRankedProductBatch:
                raise TypeError("prediction ranked batch must be exact")
            validated_batch = TypedRankedProductBatch.model_validate(ranked_batch)
            if (
                validated_batch.intent_sha256 != intent_digest
                or validated_batch.query_plan_sha256 != query_digest
                or validated_batch.proposal != validated_proposal
                or validated_batch.ranking_profile_sha256 != typed_ranking_profile_sha256()
            ):
                raise ValueError("prediction ranked batch binding is inconsistent")
            projected_products = []
            for product in validated_batch.products:
                decision_by_identity = tuple(
                    sorted(
                        (
                            HoldoutPredictedDecision(
                                condition_identity_sha256=requirement_identities[
                                    decision.requirement_id
                                ],
                                state=decision.state,
                            )
                            for decision in product.evaluation.decisions
                        ),
                        key=lambda item: item.condition_identity_sha256,
                    )
                )
                projected_products.append(
                    HoldoutPredictedProduct(
                        product_sha256=normalized_product_candidate_sha256(product.product),
                        rank=product.rank,
                        required_status=product.evaluation.required_status,
                        decisions=decision_by_identity,
                    )
                )
            ranked_products = tuple(
                sorted(projected_products, key=lambda item: item.product_sha256)
            )
            ranked_batch_digest = typed_ranked_product_batch_sha256(validated_batch)

        if status == "ranked":
            if (
                validated_proposal.status != "ready"
                or validated_proposal.issues
                or validated_query is None
                or ranked_batch is None
                or failure_code is not None
            ):
                raise ValueError("ranked prediction runtime artifacts are inconsistent")
        elif status == "blocking":
            if (
                validated_proposal.status != "blocking"
                or not validated_proposal.issues
                or ranked_batch is not None
                or failure_code is not None
            ):
                raise ValueError("blocking prediction runtime artifacts are inconsistent")
        elif status == "failed":
            if (
                validated_proposal.status != "ready"
                or ranked_batch is not None
                or failure_code is None
            ):
                raise ValueError("failed prediction runtime artifacts are inconsistent")
        else:
            raise ValueError("prediction status is unsupported")

        return HoldoutCasePrediction(
            schema_version="1.0",
            case_id=case_id,
            source_input_sha256=source_input_sha256,
            status=status,
            intent_sha256=intent_digest,
            query_plan_sha256=query_digest,
            proposal_sha256=typed_requirement_proposal_sha256(validated_proposal),
            ranked_batch_sha256=ranked_batch_digest,
            predicted_conditions=predicted_conditions,
            ranked_products=ranked_products,
            failure_code=failure_code,
        )
    except HoldoutEvaluationError:
        raise
    except (KeyError, TypeError, ValueError, ValidationError, TypedRequirementError):
        _raise_invalid_evaluation()


class HoldoutPredictionSet(StrictFrozenContract):
    schema_version: Literal["1.0"]
    dataset_id: Identifier
    content_policy: Literal["digests-states-ranks-only-v1"]
    evaluation_profile_sha256: Digest
    ranking_profile_id: Literal["typed-ranking-v4"]
    ranking_profile_sha256: Digest
    cases: Annotated[
        tuple[HoldoutCasePrediction, ...],
        Field(min_length=1, max_length=MAX_HOLDOUT_CASES, repr=False),
    ]

    @model_validator(mode="after")
    def validate_predictions(self) -> HoldoutPredictionSet:
        identifiers = tuple(item.case_id for item in self.cases)
        if identifiers != tuple(sorted(identifiers)) or len(identifiers) != len(set(identifiers)):
            raise ValueError("prediction cases must have unique canonical IDs")
        if (
            self.evaluation_profile_sha256 != holdout_evaluation_profile_sha256()
            or self.ranking_profile_id != TYPED_RANKING_PROFILE_V4.profile_id
            or self.ranking_profile_sha256 != typed_ranking_profile_sha256()
        ):
            raise ValueError("prediction profile binding is unsupported")
        return self


def holdout_prediction_set_sha256(predictions: HoldoutPredictionSet) -> str:
    try:
        if type(predictions) is not HoldoutPredictionSet:
            raise TypeError("predictions must be an exact HoldoutPredictionSet")
        validated = HoldoutPredictionSet.model_validate(predictions)
        return _canonical_model_sha256(HOLDOUT_PREDICTION_SET_DOMAIN, validated)
    except (TypeError, ValueError, ValidationError):
        _raise_invalid_evaluation()


def _ratio(numerator: int, denominator: int, *, empty_value: float = 0.0) -> float:
    if denominator == 0:
        return float(empty_value)
    return float(round(numerator / denominator, METRIC_DECIMALS))


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0.0:
        return 0.0
    return float(round(2.0 * precision * recall / (precision + recall), METRIC_DECIMALS))


def _mean(values: tuple[float, ...]) -> float:
    if not values:
        raise ValueError("metric mean requires at least one value")
    return float(round(math.fsum(values) / len(values), METRIC_DECIMALS))


def _optional_ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return _ratio(numerator, denominator)


def _is_finite_ratio(value: object) -> bool:
    return type(value) is float and math.isfinite(value) and 0.0 <= value <= 1.0


class HoldoutCaseMetrics(StrictFrozenContract):
    schema_version: Literal["1.0"]
    case_id: Identifier
    category: Identifier
    status: PredictionStatus
    expected_condition_count: Count
    predicted_condition_count: Count
    condition_true_positive_count: Count
    condition_precision: Ratio
    condition_recall: Ratio
    condition_f1: Ratio
    expected_product_count: Count
    ranked_product_count: Count
    matched_product_count: Count
    candidate_precision: Ratio
    candidate_recall: Ratio
    decision_label_count: Count
    decision_correct_count: Count
    decision_accuracy: Ratio
    hard_contradiction_label_count: Count
    hard_contradiction_detected_count: Count
    hard_contradiction_recall: Ratio | None
    uncertainty_label_count: Count
    uncertainty_preserved_count: Count
    uncertainty_preservation: Ratio | None
    required_status_label_count: Count
    required_status_correct_count: Count
    required_status_accuracy: Ratio
    pairwise_count: Count
    pairwise_correct_count: Count
    pairwise_accuracy: Ratio
    ndcg: Ratio

    @field_validator(
        "condition_precision",
        "condition_recall",
        "condition_f1",
        "candidate_precision",
        "candidate_recall",
        "decision_accuracy",
        "hard_contradiction_recall",
        "uncertainty_preservation",
        "required_status_accuracy",
        "pairwise_accuracy",
        "ndcg",
        mode="before",
    )
    @classmethod
    def validate_ratio_types(cls, value: object) -> object:
        if value is not None and not _is_finite_ratio(value):
            raise ValueError("holdout metrics must be finite float ratios")
        return value

    @model_validator(mode="after")
    def validate_metrics(self) -> HoldoutCaseMetrics:
        if self.condition_true_positive_count > min(
            self.expected_condition_count,
            self.predicted_condition_count,
        ):
            raise ValueError("condition counts are inconsistent")
        expected_precision = _ratio(
            self.condition_true_positive_count,
            self.predicted_condition_count,
            empty_value=1.0 if self.expected_condition_count == 0 else 0.0,
        )
        expected_recall = _ratio(
            self.condition_true_positive_count,
            self.expected_condition_count,
            empty_value=1.0,
        )
        if (
            self.condition_precision != expected_precision
            or self.condition_recall != expected_recall
            or self.condition_f1 != _f1(expected_precision, expected_recall)
        ):
            raise ValueError("condition metrics are inconsistent")
        if self.matched_product_count > min(
            self.expected_product_count,
            self.ranked_product_count,
        ):
            raise ValueError("candidate counts are inconsistent")
        if self.candidate_precision != _ratio(
            self.matched_product_count, self.ranked_product_count
        ) or self.candidate_recall != _ratio(
            self.matched_product_count, self.expected_product_count
        ):
            raise ValueError("candidate metrics are inconsistent")
        count_groups = (
            (
                self.decision_correct_count,
                self.decision_label_count,
                self.decision_accuracy,
                False,
            ),
            (
                self.hard_contradiction_detected_count,
                self.hard_contradiction_label_count,
                self.hard_contradiction_recall,
                True,
            ),
            (
                self.uncertainty_preserved_count,
                self.uncertainty_label_count,
                self.uncertainty_preservation,
                True,
            ),
            (
                self.required_status_correct_count,
                self.required_status_label_count,
                self.required_status_accuracy,
                False,
            ),
            (
                self.pairwise_correct_count,
                self.pairwise_count,
                self.pairwise_accuracy,
                False,
            ),
        )
        for numerator, denominator, ratio, optional in count_groups:
            if numerator > denominator:
                raise ValueError("holdout metric counts are inconsistent")
            expected = (
                _optional_ratio(numerator, denominator)
                if optional
                else _ratio(numerator, denominator)
            )
            if ratio != expected:
                raise ValueError("holdout metric ratio is inconsistent")
        if self.status != "ranked" and (
            self.ranked_product_count != 0
            or self.matched_product_count != 0
            or self.candidate_precision != 0.0
            or self.candidate_recall != 0.0
            or self.decision_correct_count != 0
            or self.hard_contradiction_detected_count != 0
            or self.uncertainty_preserved_count != 0
            or self.required_status_correct_count != 0
            or self.pairwise_correct_count != 0
            or self.ndcg != 0.0
        ):
            raise ValueError("non-ranked case metrics must retain zero prediction quality")
        return self


class HoldoutMetricSummary(StrictFrozenContract):
    case_count: Count
    ranked_case_count: Count
    blocking_case_count: Count
    failed_case_count: Count
    expected_condition_count: Count
    predicted_condition_count: Count
    condition_true_positive_count: Count
    condition_precision: Ratio
    condition_recall: Ratio
    condition_f1: Ratio
    condition_macro_f1: Ratio
    expected_product_count: Count
    ranked_product_count: Count
    matched_product_count: Count
    candidate_precision: Ratio
    candidate_recall: Ratio
    candidate_macro_recall: Ratio
    decision_label_count: Count
    decision_correct_count: Count
    decision_accuracy: Ratio
    decision_macro_accuracy: Ratio
    hard_contradiction_label_count: Count
    hard_contradiction_detected_count: Count
    hard_contradiction_recall: Ratio | None
    uncertainty_label_count: Count
    uncertainty_preserved_count: Count
    uncertainty_preservation: Ratio | None
    required_status_label_count: Count
    required_status_correct_count: Count
    required_status_accuracy: Ratio
    required_status_macro_accuracy: Ratio
    pairwise_count: Count
    pairwise_correct_count: Count
    pairwise_accuracy: Ratio
    pairwise_macro_accuracy: Ratio
    mean_ndcg: Ratio

    @field_validator(
        "condition_precision",
        "condition_recall",
        "condition_f1",
        "condition_macro_f1",
        "candidate_precision",
        "candidate_recall",
        "candidate_macro_recall",
        "decision_accuracy",
        "decision_macro_accuracy",
        "hard_contradiction_recall",
        "uncertainty_preservation",
        "required_status_accuracy",
        "required_status_macro_accuracy",
        "pairwise_accuracy",
        "pairwise_macro_accuracy",
        "mean_ndcg",
        mode="before",
    )
    @classmethod
    def validate_ratio_types(cls, value: object) -> object:
        if value is not None and not _is_finite_ratio(value):
            raise ValueError("holdout summary values must be finite float ratios")
        return value

    @model_validator(mode="after")
    def validate_case_counts(self) -> HoldoutMetricSummary:
        if (
            self.ranked_case_count + self.blocking_case_count + self.failed_case_count
            != self.case_count
        ):
            raise ValueError("holdout summary case status counts are inconsistent")
        return self


class HoldoutCategoryMetrics(StrictFrozenContract):
    category: Identifier
    summary: HoldoutMetricSummary


class HoldoutOverallMetrics(StrictFrozenContract):
    coverage_eligible: bool
    coverage_issues: Annotated[tuple[CoverageIssue, ...], Field(max_length=6)]
    category_count: Annotated[int, Field(ge=1, le=MAX_CATEGORIES)]
    summary: HoldoutMetricSummary
    category_macro_condition_f1: Ratio
    category_macro_decision_accuracy: Ratio
    category_macro_pairwise_accuracy: Ratio
    category_macro_ndcg: Ratio

    @field_validator(
        "category_macro_condition_f1",
        "category_macro_decision_accuracy",
        "category_macro_pairwise_accuracy",
        "category_macro_ndcg",
        mode="before",
    )
    @classmethod
    def validate_ratio_types(cls, value: object) -> object:
        if not _is_finite_ratio(value):
            raise ValueError("category macro values must be finite float ratios")
        return value

    @model_validator(mode="after")
    def validate_coverage(self) -> HoldoutOverallMetrics:
        if self.coverage_issues != tuple(dict.fromkeys(self.coverage_issues)):
            raise ValueError("coverage issues must be unique and canonical")
        if self.coverage_eligible == bool(self.coverage_issues):
            raise ValueError("coverage eligibility is inconsistent")
        return self


class HoldoutEvaluationReport(StrictFrozenContract):
    schema_version: Literal["1.0"]
    profile_id: Literal["typed-ranking-holdout-v1"]
    profile_sha256: Digest
    dataset_id: Identifier
    dataset_sha256: Digest
    prediction_set_sha256: Digest
    ranking_profile_id: Literal["typed-ranking-v4"]
    ranking_profile_sha256: Digest
    quality_decision: Literal["not_assessed"]
    cases: Annotated[
        tuple[HoldoutCaseMetrics, ...],
        Field(min_length=1, max_length=MAX_HOLDOUT_CASES),
    ]
    categories: Annotated[
        tuple[HoldoutCategoryMetrics, ...],
        Field(min_length=1, max_length=MAX_CATEGORIES),
    ]
    overall: HoldoutOverallMetrics

    @model_validator(mode="after")
    def validate_report(self) -> HoldoutEvaluationReport:
        if (
            self.profile_sha256 != holdout_evaluation_profile_sha256()
            or self.ranking_profile_sha256 != typed_ranking_profile_sha256()
        ):
            raise ValueError("holdout report profile binding is unsupported")
        case_ids = tuple(item.case_id for item in self.cases)
        if case_ids != tuple(sorted(case_ids)) or len(case_ids) != len(set(case_ids)):
            raise ValueError("holdout report cases must be canonical")
        category_names = tuple(item.category for item in self.categories)
        if category_names != tuple(sorted(category_names)) or len(category_names) != len(
            set(category_names)
        ):
            raise ValueError("holdout report categories must be canonical")
        if category_names != tuple(sorted({item.category for item in self.cases})):
            raise ValueError("holdout report category coverage is inconsistent")
        for category in self.categories:
            selected = tuple(item for item in self.cases if item.category == category.category)
            if category.summary != _summarize_cases(selected):
                raise ValueError("holdout category summary is inconsistent")
        if self.overall != _overall_metrics(self.cases, self.categories):
            raise ValueError("holdout overall summary is inconsistent")
        return self


def holdout_evaluation_report_sha256(report: HoldoutEvaluationReport) -> str:
    try:
        if type(report) is not HoldoutEvaluationReport:
            raise TypeError("report must be an exact HoldoutEvaluationReport")
        validated = HoldoutEvaluationReport.model_validate(report)
        return _canonical_model_sha256(HOLDOUT_EVALUATION_REPORT_DOMAIN, validated)
    except (TypeError, ValueError, ValidationError):
        _raise_invalid_evaluation()


def _expected_required_status(
    conditions: tuple[HoldoutExpectedCondition, ...],
    decisions: tuple[HoldoutExpectedDecision, ...],
) -> str:
    requirements = {item.condition_id: item.requirement for item in conditions}
    contradicted = False
    uncertain = False
    for decision in decisions:
        requirement = requirements[decision.condition_id]
        if requirement.strength not in {"required", "excluded"}:
            continue
        if _is_hard_contradiction(requirement, decision.expected_state):
            contradicted = True
        elif decision.expected_state in {"unknown", "conflict"}:
            uncertain = True
    if contradicted:
        return "contradicted"
    if uncertain:
        return "uncertain"
    return "confirmed"


def _is_hard_contradiction(requirement: TypedRequirement, state: str) -> bool:
    return (requirement.strength == "required" and state == "mismatch") or (
        requirement.strength == "excluded" and state == "match"
    )


def _condition_counts(
    truth: HoldoutGroundTruthCase,
    prediction: HoldoutCasePrediction,
) -> tuple[int, int, int, dict[str, str]]:
    expected_by_identity = {
        item.condition_identity_sha256: item.condition_id for item in truth.expected_conditions
    }
    actual_by_identity = {
        item.condition_identity_sha256: item.condition_identity_sha256
        for item in prediction.predicted_conditions
    }
    matched = set(expected_by_identity).intersection(actual_by_identity)
    truth_to_actual = {
        expected_by_identity[identity]: actual_by_identity[identity] for identity in matched
    }
    return (
        len(expected_by_identity),
        len(actual_by_identity),
        len(matched),
        truth_to_actual,
    )


def _actual_products(
    prediction: HoldoutCasePrediction,
) -> dict[str, HoldoutPredictedProduct]:
    return {item.product_sha256: item for item in prediction.ranked_products}


def _decision_metrics(
    truth: HoldoutGroundTruthCase,
    actual_products: dict[str, HoldoutPredictedProduct],
    truth_to_actual_condition: dict[str, str],
) -> tuple[int, int, int, int, int, int, int, int]:
    truth_conditions = {item.condition_id: item.requirement for item in truth.expected_conditions}
    decision_labels = 0
    decision_correct = 0
    contradiction_labels = 0
    contradiction_detected = 0
    uncertainty_labels = 0
    uncertainty_preserved = 0
    required_status_labels = 0
    required_status_correct = 0
    for expected_product in truth.expected_products:
        actual_product = actual_products.get(expected_product.product_sha256)
        actual_decisions = (
            {}
            if actual_product is None
            else {item.condition_identity_sha256: item.state for item in actual_product.decisions}
        )
        for expected in expected_product.decisions:
            decision_labels += 1
            requirement = truth_conditions[expected.condition_id]
            actual_condition_id = truth_to_actual_condition.get(expected.condition_id)
            actual_state = (
                None if actual_condition_id is None else actual_decisions.get(actual_condition_id)
            )
            if actual_state == expected.expected_state:
                decision_correct += 1
            if _is_hard_contradiction(requirement, expected.expected_state):
                contradiction_labels += 1
                if actual_state is not None and _is_hard_contradiction(
                    requirement,
                    actual_state,
                ):
                    contradiction_detected += 1
            if requirement.strength in {"required", "excluded"} and expected.expected_state in {
                "unknown",
                "conflict",
            }:
                uncertainty_labels += 1
                if actual_state in {"unknown", "conflict"}:
                    uncertainty_preserved += 1

        required_status_labels += 1
        expected_status = _expected_required_status(
            truth.expected_conditions,
            expected_product.decisions,
        )
        if actual_product is not None and actual_product.required_status == expected_status:
            required_status_correct += 1
    return (
        decision_labels,
        decision_correct,
        contradiction_labels,
        contradiction_detected,
        uncertainty_labels,
        uncertainty_preserved,
        required_status_labels,
        required_status_correct,
    )


def _pairwise_metrics(
    truth: HoldoutGroundTruthCase,
    actual_products: dict[str, HoldoutPredictedProduct],
) -> tuple[int, int]:
    ranks = {digest: item.rank for digest, item in actual_products.items()}
    comparable = 0
    correct = 0
    for index, left in enumerate(truth.expected_products):
        for right in truth.expected_products[index + 1 :]:
            if left.relevance_grade == right.relevance_grade:
                continue
            comparable += 1
            preferred, other = (
                (left, right) if left.relevance_grade > right.relevance_grade else (right, left)
            )
            preferred_rank = ranks.get(preferred.product_sha256)
            other_rank = ranks.get(other.product_sha256)
            if (
                preferred_rank is not None
                and other_rank is not None
                and preferred_rank < other_rank
            ):
                correct += 1
    return comparable, correct


def _ndcg(
    truth: HoldoutGroundTruthCase,
    prediction: HoldoutCasePrediction,
) -> float:
    grade_by_product = {
        item.product_sha256: item.relevance_grade for item in truth.expected_products
    }
    actual_order = tuple(
        item.product_sha256
        for item in sorted(prediction.ranked_products, key=lambda item: item.rank)
    )
    evaluation_length = len(truth.expected_products)
    actual_grades = [grade_by_product.get(item, 0) for item in actual_order[:evaluation_length]]
    actual_grades.extend([0] * (evaluation_length - len(actual_grades)))
    ideal_grades = sorted(grade_by_product.values(), reverse=True)

    def dcg(grades: list[int]) -> float:
        return math.fsum(
            (2**grade - 1) / math.log2(position + 2) for position, grade in enumerate(grades)
        )

    ideal = dcg(ideal_grades)
    if ideal <= 0.0:
        raise ValueError("ground truth does not define a positive ideal ranking")
    return float(round(dcg(actual_grades) / ideal, METRIC_DECIMALS))


def _evaluate_case(
    truth: HoldoutGroundTruthCase,
    prediction: HoldoutCasePrediction,
) -> HoldoutCaseMetrics:
    expected_conditions, predicted_conditions, condition_matches, truth_to_actual = (
        _condition_counts(truth, prediction)
    )
    condition_precision = _ratio(
        condition_matches,
        predicted_conditions,
        empty_value=1.0 if expected_conditions == 0 else 0.0,
    )
    condition_recall = _ratio(
        condition_matches,
        expected_conditions,
        empty_value=1.0,
    )
    actual_products = _actual_products(prediction)
    expected_product_digests = {item.product_sha256 for item in truth.expected_products}
    matched_products = len(expected_product_digests.intersection(actual_products))
    (
        decision_labels,
        decision_correct,
        contradiction_labels,
        contradiction_detected,
        uncertainty_labels,
        uncertainty_preserved,
        required_status_labels,
        required_status_correct,
    ) = _decision_metrics(truth, actual_products, truth_to_actual)
    pairwise_count, pairwise_correct = _pairwise_metrics(truth, actual_products)
    return HoldoutCaseMetrics(
        schema_version="1.0",
        case_id=truth.case_id,
        category=truth.category,
        status=prediction.status,
        expected_condition_count=expected_conditions,
        predicted_condition_count=predicted_conditions,
        condition_true_positive_count=condition_matches,
        condition_precision=condition_precision,
        condition_recall=condition_recall,
        condition_f1=_f1(condition_precision, condition_recall),
        expected_product_count=len(truth.expected_products),
        ranked_product_count=len(actual_products),
        matched_product_count=matched_products,
        candidate_precision=_ratio(matched_products, len(actual_products)),
        candidate_recall=_ratio(matched_products, len(truth.expected_products)),
        decision_label_count=decision_labels,
        decision_correct_count=decision_correct,
        decision_accuracy=_ratio(decision_correct, decision_labels),
        hard_contradiction_label_count=contradiction_labels,
        hard_contradiction_detected_count=contradiction_detected,
        hard_contradiction_recall=_optional_ratio(
            contradiction_detected,
            contradiction_labels,
        ),
        uncertainty_label_count=uncertainty_labels,
        uncertainty_preserved_count=uncertainty_preserved,
        uncertainty_preservation=_optional_ratio(
            uncertainty_preserved,
            uncertainty_labels,
        ),
        required_status_label_count=required_status_labels,
        required_status_correct_count=required_status_correct,
        required_status_accuracy=_ratio(required_status_correct, required_status_labels),
        pairwise_count=pairwise_count,
        pairwise_correct_count=pairwise_correct,
        pairwise_accuracy=_ratio(pairwise_correct, pairwise_count),
        ndcg=_ndcg(truth, prediction),
    )


def _summarize_cases(cases: tuple[HoldoutCaseMetrics, ...]) -> HoldoutMetricSummary:
    if not cases:
        raise ValueError("holdout summary requires at least one case")
    expected_conditions = sum(item.expected_condition_count for item in cases)
    predicted_conditions = sum(item.predicted_condition_count for item in cases)
    condition_matches = sum(item.condition_true_positive_count for item in cases)
    condition_precision = _ratio(
        condition_matches,
        predicted_conditions,
        empty_value=1.0 if expected_conditions == 0 else 0.0,
    )
    condition_recall = _ratio(
        condition_matches,
        expected_conditions,
        empty_value=1.0,
    )
    expected_products = sum(item.expected_product_count for item in cases)
    ranked_products = sum(item.ranked_product_count for item in cases)
    matched_products = sum(item.matched_product_count for item in cases)
    decision_labels = sum(item.decision_label_count for item in cases)
    decision_correct = sum(item.decision_correct_count for item in cases)
    contradiction_labels = sum(item.hard_contradiction_label_count for item in cases)
    contradiction_detected = sum(item.hard_contradiction_detected_count for item in cases)
    uncertainty_labels = sum(item.uncertainty_label_count for item in cases)
    uncertainty_preserved = sum(item.uncertainty_preserved_count for item in cases)
    required_status_labels = sum(item.required_status_label_count for item in cases)
    required_status_correct = sum(item.required_status_correct_count for item in cases)
    pairwise_count = sum(item.pairwise_count for item in cases)
    pairwise_correct = sum(item.pairwise_correct_count for item in cases)
    return HoldoutMetricSummary(
        case_count=len(cases),
        ranked_case_count=sum(item.status == "ranked" for item in cases),
        blocking_case_count=sum(item.status == "blocking" for item in cases),
        failed_case_count=sum(item.status == "failed" for item in cases),
        expected_condition_count=expected_conditions,
        predicted_condition_count=predicted_conditions,
        condition_true_positive_count=condition_matches,
        condition_precision=condition_precision,
        condition_recall=condition_recall,
        condition_f1=_f1(condition_precision, condition_recall),
        condition_macro_f1=_mean(tuple(item.condition_f1 for item in cases)),
        expected_product_count=expected_products,
        ranked_product_count=ranked_products,
        matched_product_count=matched_products,
        candidate_precision=_ratio(matched_products, ranked_products),
        candidate_recall=_ratio(matched_products, expected_products),
        candidate_macro_recall=_mean(tuple(item.candidate_recall for item in cases)),
        decision_label_count=decision_labels,
        decision_correct_count=decision_correct,
        decision_accuracy=_ratio(decision_correct, decision_labels),
        decision_macro_accuracy=_mean(tuple(item.decision_accuracy for item in cases)),
        hard_contradiction_label_count=contradiction_labels,
        hard_contradiction_detected_count=contradiction_detected,
        hard_contradiction_recall=_optional_ratio(
            contradiction_detected,
            contradiction_labels,
        ),
        uncertainty_label_count=uncertainty_labels,
        uncertainty_preserved_count=uncertainty_preserved,
        uncertainty_preservation=_optional_ratio(
            uncertainty_preserved,
            uncertainty_labels,
        ),
        required_status_label_count=required_status_labels,
        required_status_correct_count=required_status_correct,
        required_status_accuracy=_ratio(required_status_correct, required_status_labels),
        required_status_macro_accuracy=_mean(
            tuple(item.required_status_accuracy for item in cases)
        ),
        pairwise_count=pairwise_count,
        pairwise_correct_count=pairwise_correct,
        pairwise_accuracy=_ratio(pairwise_correct, pairwise_count),
        pairwise_macro_accuracy=_mean(tuple(item.pairwise_accuracy for item in cases)),
        mean_ndcg=_mean(tuple(item.ndcg for item in cases)),
    )


def _coverage_issues(cases: tuple[HoldoutCaseMetrics, ...]) -> tuple[CoverageIssue, ...]:
    profile = HOLDOUT_EVALUATION_PROFILE_V1
    categories = tuple(sorted({item.category for item in cases}))
    issues: list[CoverageIssue] = []
    if len(categories) < profile.minimum_categories:
        issues.append("too_few_categories")
    if any(
        sum(item.category == category for item in cases) < profile.minimum_cases_per_category
        for category in categories
    ):
        issues.append("too_few_cases_per_category")
    if any(item.expected_product_count < profile.minimum_products_per_case for item in cases):
        issues.append("too_few_products_per_case")
    if any(item.expected_condition_count < profile.minimum_conditions_per_case for item in cases):
        issues.append("too_few_conditions_per_case")
    if (
        sum(item.hard_contradiction_label_count for item in cases)
        < profile.minimum_hard_contradiction_labels
    ):
        issues.append("missing_hard_contradiction_labels")
    if sum(item.uncertainty_label_count for item in cases) < profile.minimum_uncertainty_labels:
        issues.append("missing_uncertainty_labels")
    return tuple(issues)


def _overall_metrics(
    cases: tuple[HoldoutCaseMetrics, ...],
    categories: tuple[HoldoutCategoryMetrics, ...],
) -> HoldoutOverallMetrics:
    issues = _coverage_issues(cases)
    return HoldoutOverallMetrics(
        coverage_eligible=not issues,
        coverage_issues=issues,
        category_count=len(categories),
        summary=_summarize_cases(cases),
        category_macro_condition_f1=_mean(
            tuple(item.summary.condition_macro_f1 for item in categories)
        ),
        category_macro_decision_accuracy=_mean(
            tuple(item.summary.decision_macro_accuracy for item in categories)
        ),
        category_macro_pairwise_accuracy=_mean(
            tuple(item.summary.pairwise_macro_accuracy for item in categories)
        ),
        category_macro_ndcg=_mean(tuple(item.summary.mean_ndcg for item in categories)),
    )


def evaluate_holdout_predictions(
    dataset: HoldoutGroundTruthDataset,
    predictions: HoldoutPredictionSet,
    *,
    profile: HoldoutEvaluationProfile = HOLDOUT_EVALUATION_PROFILE_V1,
) -> HoldoutEvaluationReport:
    """Evaluate typed-ranking predictions without invoking providers or reading files."""

    try:
        if type(dataset) is not HoldoutGroundTruthDataset:
            raise TypeError("dataset must be an exact HoldoutGroundTruthDataset")
        if type(predictions) is not HoldoutPredictionSet:
            raise TypeError("predictions must be an exact HoldoutPredictionSet")
        if type(profile) is not HoldoutEvaluationProfile:
            raise TypeError("profile must be an exact HoldoutEvaluationProfile")
        validated_dataset = HoldoutGroundTruthDataset.model_validate(dataset)
        validated_predictions = HoldoutPredictionSet.model_validate(predictions)
        validated_profile = HoldoutEvaluationProfile.model_validate(profile)
        if (
            validated_profile != HOLDOUT_EVALUATION_PROFILE_V1
            or validated_predictions.evaluation_profile_sha256
            != holdout_evaluation_profile_sha256(validated_profile)
            or validated_dataset.dataset_id != validated_predictions.dataset_id
            or tuple(item.case_id for item in validated_dataset.cases)
            != tuple(item.case_id for item in validated_predictions.cases)
        ):
            raise ValueError("holdout dataset and predictions are inconsistent")

        case_metrics: list[HoldoutCaseMetrics] = []
        for truth, prediction in zip(
            validated_dataset.cases,
            validated_predictions.cases,
            strict=True,
        ):
            if truth.source_input_sha256 != prediction.source_input_sha256:
                raise ValueError("holdout source input binding is inconsistent")
            case_metrics.append(_evaluate_case(truth, prediction))
        cases = tuple(case_metrics)
        categories = tuple(
            HoldoutCategoryMetrics(
                category=category,
                summary=_summarize_cases(
                    tuple(item for item in cases if item.category == category)
                ),
            )
            for category in sorted({item.category for item in cases})
        )
        return HoldoutEvaluationReport(
            schema_version="1.0",
            profile_id=validated_profile.profile_id,
            profile_sha256=holdout_evaluation_profile_sha256(validated_profile),
            dataset_id=validated_dataset.dataset_id,
            dataset_sha256=holdout_ground_truth_dataset_sha256(validated_dataset),
            prediction_set_sha256=holdout_prediction_set_sha256(validated_predictions),
            ranking_profile_id=validated_predictions.ranking_profile_id,
            ranking_profile_sha256=validated_predictions.ranking_profile_sha256,
            quality_decision="not_assessed",
            cases=cases,
            categories=categories,
            overall=_overall_metrics(cases, categories),
        )
    except HoldoutEvaluationError:
        raise
    except (KeyError, TypeError, ValueError, ValidationError, TypedRequirementError):
        _raise_invalid_evaluation()
