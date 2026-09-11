"""Fixed quality acceptance policy for deterministic holdout reports."""

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

from src.search_v2.holdout_evaluation import HOLDOUT_EVALUATION_PROFILE_V1
from src.search_v2.holdout_evaluation import METRIC_DECIMALS
from src.search_v2.holdout_evaluation import HoldoutCategoryMetrics
from src.search_v2.holdout_evaluation import HoldoutEvaluationError
from src.search_v2.holdout_evaluation import HoldoutEvaluationReport
from src.search_v2.holdout_evaluation import HoldoutMetricSummary
from src.search_v2.holdout_evaluation import holdout_evaluation_profile_sha256
from src.search_v2.holdout_evaluation import holdout_evaluation_report_sha256
from src.search_v2.typed_ranking import TYPED_RANKING_PROFILE_V4
from src.search_v2.typed_ranking import typed_ranking_profile_sha256
from src.search_v2.typed_requirements import Identifier


HOLDOUT_ACCEPTANCE_POLICY_DOMAIN = b"amazon-explorer-holdout-acceptance-policy-v1\x00"
HOLDOUT_ACCEPTANCE_ASSESSMENT_DOMAIN = b"amazon-explorer-holdout-acceptance-assessment-v1\x00"

_INVALID_ACCEPTANCE_MESSAGE = "Holdout acceptance inputs did not match the acceptance contract"

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Count = Annotated[int, Field(ge=0, le=1_000_000)]
Ratio = Annotated[float, Field(ge=0.0, le=1.0)]
CheckValue = bool | Count | Ratio
ObservedValue = CheckValue | None
AcceptanceDecision = Literal["pass", "fail", "ineligible"]
AcceptanceScope = Literal["overall", "category"]
AcceptanceOperator = Literal["eq", "gte"]
AcceptanceMetric = Literal[
    "coverage_eligible",
    "hard_contradiction_label_count",
    "uncertainty_label_count",
    "blocking_case_count",
    "failed_case_count",
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
]

_CATEGORY_ELIGIBILITY_METRICS = (
    "hard_contradiction_label_count",
    "uncertainty_label_count",
)
_ELIGIBILITY_METRICS = frozenset(("coverage_eligible", *_CATEGORY_ELIGIBILITY_METRICS))
_COUNT_METRICS = frozenset(
    (
        "hard_contradiction_label_count",
        "uncertainty_label_count",
        "blocking_case_count",
        "failed_case_count",
    )
)
_OPTIONAL_RATIO_METRICS = frozenset(("hard_contradiction_recall", "uncertainty_preservation"))
_QUALITY_CHECK_SPECS = (
    ("blocking_case_count", "maximum_blocking_case_count", "eq"),
    ("failed_case_count", "maximum_failed_case_count", "eq"),
    ("condition_f1", "minimum_condition_f1", "gte"),
    ("condition_macro_f1", "minimum_condition_macro_f1", "gte"),
    ("candidate_precision", "minimum_candidate_precision", "gte"),
    ("candidate_recall", "minimum_candidate_recall", "gte"),
    ("candidate_macro_recall", "minimum_candidate_macro_recall", "gte"),
    ("decision_accuracy", "minimum_decision_accuracy", "gte"),
    ("decision_macro_accuracy", "minimum_decision_macro_accuracy", "gte"),
    (
        "hard_contradiction_recall",
        "minimum_hard_contradiction_recall",
        "gte",
    ),
    ("uncertainty_preservation", "minimum_uncertainty_preservation", "gte"),
    ("required_status_accuracy", "minimum_required_status_accuracy", "gte"),
    (
        "required_status_macro_accuracy",
        "minimum_required_status_macro_accuracy",
        "gte",
    ),
    ("pairwise_accuracy", "minimum_pairwise_accuracy", "gte"),
    ("pairwise_macro_accuracy", "minimum_pairwise_macro_accuracy", "gte"),
    ("mean_ndcg", "minimum_mean_ndcg", "gte"),
)
_QUALITY_METRICS = tuple(item[0] for item in _QUALITY_CHECK_SPECS)


class HoldoutAcceptanceError(ValueError):
    """A fixed-message rejection for invalid holdout acceptance inputs."""


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


def _raise_invalid_acceptance() -> None:
    raise HoldoutAcceptanceError(_INVALID_ACCEPTANCE_MESSAGE) from None


def _is_finite_ratio(value: object) -> bool:
    return type(value) is float and math.isfinite(value) and 0.0 <= value <= 1.0


class HoldoutAcceptancePolicy(StrictFrozenContract):
    schema_version: Literal["1.0"]
    policy_id: Literal["typed-ranking-holdout-acceptance-v1"]
    evaluation_profile_id: Literal["typed-ranking-holdout-v1"]
    evaluation_profile_sha256: Digest
    ranking_profile_id: Literal["typed-ranking-v4"]
    ranking_profile_sha256: Digest
    metric_decimals: Literal[6]
    require_all_categories: Literal[True]
    minimum_hard_contradiction_labels_per_category: Literal[1]
    minimum_uncertainty_labels_per_category: Literal[1]
    maximum_blocking_case_count: Literal[0]
    maximum_failed_case_count: Literal[0]
    minimum_condition_f1: Ratio
    minimum_condition_macro_f1: Ratio
    minimum_candidate_precision: Ratio
    minimum_candidate_recall: Ratio
    minimum_candidate_macro_recall: Ratio
    minimum_decision_accuracy: Ratio
    minimum_decision_macro_accuracy: Ratio
    minimum_hard_contradiction_recall: Ratio
    minimum_uncertainty_preservation: Ratio
    minimum_required_status_accuracy: Ratio
    minimum_required_status_macro_accuracy: Ratio
    minimum_pairwise_accuracy: Ratio
    minimum_pairwise_macro_accuracy: Ratio
    minimum_mean_ndcg: Ratio

    @field_validator(
        "minimum_condition_f1",
        "minimum_condition_macro_f1",
        "minimum_candidate_precision",
        "minimum_candidate_recall",
        "minimum_candidate_macro_recall",
        "minimum_decision_accuracy",
        "minimum_decision_macro_accuracy",
        "minimum_hard_contradiction_recall",
        "minimum_uncertainty_preservation",
        "minimum_required_status_accuracy",
        "minimum_required_status_macro_accuracy",
        "minimum_pairwise_accuracy",
        "minimum_pairwise_macro_accuracy",
        "minimum_mean_ndcg",
        mode="before",
    )
    @classmethod
    def validate_ratio_types(cls, value: object) -> object:
        if not _is_finite_ratio(value):
            raise ValueError("acceptance thresholds must be finite float ratios")
        return value

    @model_validator(mode="after")
    def validate_profile_bindings(self) -> HoldoutAcceptancePolicy:
        if (
            self.evaluation_profile_id != HOLDOUT_EVALUATION_PROFILE_V1.profile_id
            or self.evaluation_profile_sha256 != holdout_evaluation_profile_sha256()
            or self.ranking_profile_id != TYPED_RANKING_PROFILE_V4.profile_id
            or self.ranking_profile_sha256 != typed_ranking_profile_sha256()
            or self.metric_decimals != METRIC_DECIMALS
        ):
            raise ValueError("acceptance policy profile binding is unsupported")
        return self


HOLDOUT_ACCEPTANCE_POLICY_V1 = HoldoutAcceptancePolicy(
    schema_version="1.0",
    policy_id="typed-ranking-holdout-acceptance-v1",
    evaluation_profile_id="typed-ranking-holdout-v1",
    evaluation_profile_sha256=holdout_evaluation_profile_sha256(),
    ranking_profile_id="typed-ranking-v4",
    ranking_profile_sha256=typed_ranking_profile_sha256(),
    metric_decimals=METRIC_DECIMALS,
    require_all_categories=True,
    minimum_hard_contradiction_labels_per_category=1,
    minimum_uncertainty_labels_per_category=1,
    maximum_blocking_case_count=0,
    maximum_failed_case_count=0,
    minimum_condition_f1=0.90,
    minimum_condition_macro_f1=0.90,
    minimum_candidate_precision=0.85,
    minimum_candidate_recall=0.90,
    minimum_candidate_macro_recall=0.90,
    minimum_decision_accuracy=0.90,
    minimum_decision_macro_accuracy=0.90,
    minimum_hard_contradiction_recall=1.0,
    minimum_uncertainty_preservation=1.0,
    minimum_required_status_accuracy=1.0,
    minimum_required_status_macro_accuracy=1.0,
    minimum_pairwise_accuracy=0.85,
    minimum_pairwise_macro_accuracy=0.85,
    minimum_mean_ndcg=0.90,
)


def holdout_acceptance_policy_sha256(
    policy: HoldoutAcceptancePolicy = HOLDOUT_ACCEPTANCE_POLICY_V1,
) -> str:
    """Return the domain-separated digest of one strict acceptance policy."""

    try:
        if type(policy) is not HoldoutAcceptancePolicy:
            raise TypeError("policy must be an exact HoldoutAcceptancePolicy")
        validated = HoldoutAcceptancePolicy.model_validate(policy)
        return _canonical_model_sha256(HOLDOUT_ACCEPTANCE_POLICY_DOMAIN, validated)
    except HoldoutAcceptanceError:
        raise
    except (TypeError, ValueError, ValidationError, HoldoutEvaluationError):
        _raise_invalid_acceptance()


class HoldoutAcceptanceCheck(StrictFrozenContract):
    scope: AcceptanceScope
    category: Identifier | None
    metric: AcceptanceMetric
    operator: AcceptanceOperator
    observed: ObservedValue
    required: CheckValue
    passed: bool

    @model_validator(mode="after")
    def validate_check(self) -> HoldoutAcceptanceCheck:
        if (self.scope == "overall") != (self.category is None):
            raise ValueError("acceptance check scope is inconsistent")
        if self.metric == "coverage_eligible":
            if (
                self.scope != "overall"
                or self.operator != "eq"
                or type(self.observed) is not bool
                or type(self.required) is not bool
            ):
                raise ValueError("coverage acceptance check is inconsistent")
        elif self.metric in _CATEGORY_ELIGIBILITY_METRICS:
            if (
                self.scope != "category"
                or self.operator != "gte"
                or type(self.observed) is not int
                or type(self.required) is not int
            ):
                raise ValueError("category eligibility check is inconsistent")
        elif self.metric in _COUNT_METRICS:
            if (
                self.operator != "eq"
                or type(self.observed) is not int
                or type(self.required) is not int
            ):
                raise ValueError("count acceptance check is inconsistent")
        else:
            if self.operator != "gte" or not _is_finite_ratio(self.required):
                raise ValueError("ratio acceptance check is inconsistent")
            if self.observed is None:
                if self.metric not in _OPTIONAL_RATIO_METRICS:
                    raise ValueError("acceptance check is missing a required ratio")
            elif not _is_finite_ratio(self.observed):
                raise ValueError("acceptance check has an invalid ratio")

        expected_passed = (
            self.observed == self.required
            if self.operator == "eq"
            else self.observed is not None and self.observed >= self.required
        )
        if self.passed is not expected_passed:
            raise ValueError("acceptance check result is inconsistent")
        return self


class HoldoutAcceptanceAssessment(StrictFrozenContract):
    schema_version: Literal["1.0"]
    policy_id: Literal["typed-ranking-holdout-acceptance-v1"]
    policy_sha256: Digest
    evaluation_profile_id: Literal["typed-ranking-holdout-v1"]
    evaluation_profile_sha256: Digest
    evaluation_report_sha256: Digest
    dataset_id: Identifier
    dataset_sha256: Digest
    prediction_set_sha256: Digest
    ranking_profile_id: Literal["typed-ranking-v4"]
    ranking_profile_sha256: Digest
    decision: AcceptanceDecision
    checks: Annotated[
        tuple[HoldoutAcceptanceCheck, ...],
        Field(min_length=35, max_length=1_200),
    ]

    @model_validator(mode="after")
    def validate_assessment(self) -> HoldoutAcceptanceAssessment:
        if (
            self.policy_sha256 != holdout_acceptance_policy_sha256()
            or self.evaluation_profile_sha256 != holdout_evaluation_profile_sha256()
            or self.ranking_profile_sha256 != typed_ranking_profile_sha256()
        ):
            raise ValueError("acceptance assessment profile binding is unsupported")

        categories = tuple(
            sorted(
                {
                    item.category
                    for item in self.checks
                    if item.scope == "category" and item.category is not None
                }
            )
        )
        expected_order = [("overall", None, "coverage_eligible")]
        expected_order.extend(
            ("category", category, metric)
            for category in categories
            for metric in _CATEGORY_ELIGIBILITY_METRICS
        )
        expected_order.extend(("overall", None, metric) for metric in _QUALITY_METRICS)
        expected_order.extend(
            ("category", category, metric) for category in categories for metric in _QUALITY_METRICS
        )
        actual_order = [(item.scope, item.category, item.metric) for item in self.checks]
        if not categories or actual_order != expected_order:
            raise ValueError("acceptance checks are not canonical")

        eligibility_failed = any(
            not item.passed and item.metric in _ELIGIBILITY_METRICS for item in self.checks
        )
        quality_failed = any(
            not item.passed and item.metric not in _ELIGIBILITY_METRICS for item in self.checks
        )
        expected_decision: AcceptanceDecision
        if eligibility_failed:
            expected_decision = "ineligible"
        elif quality_failed:
            expected_decision = "fail"
        else:
            expected_decision = "pass"
        if self.decision != expected_decision:
            raise ValueError("acceptance decision is inconsistent")
        return self


def _check(
    *,
    scope: AcceptanceScope,
    category: str | None,
    metric: AcceptanceMetric,
    operator: AcceptanceOperator,
    observed: ObservedValue,
    required: CheckValue,
) -> HoldoutAcceptanceCheck:
    passed = (
        observed == required if operator == "eq" else observed is not None and observed >= required
    )
    return HoldoutAcceptanceCheck(
        scope=scope,
        category=category,
        metric=metric,
        operator=operator,
        observed=observed,
        required=required,
        passed=passed,
    )


def _quality_checks(
    summary: HoldoutMetricSummary,
    *,
    scope: AcceptanceScope,
    category: str | None,
    policy: HoldoutAcceptancePolicy,
) -> tuple[HoldoutAcceptanceCheck, ...]:
    return tuple(
        _check(
            scope=scope,
            category=category,
            metric=metric,
            operator=operator,
            observed=getattr(summary, metric),
            required=getattr(policy, policy_field),
        )
        for metric, policy_field, operator in _QUALITY_CHECK_SPECS
    )


def _category_eligibility_checks(
    category: HoldoutCategoryMetrics,
    policy: HoldoutAcceptancePolicy,
) -> tuple[HoldoutAcceptanceCheck, ...]:
    return (
        _check(
            scope="category",
            category=category.category,
            metric="hard_contradiction_label_count",
            operator="gte",
            observed=category.summary.hard_contradiction_label_count,
            required=policy.minimum_hard_contradiction_labels_per_category,
        ),
        _check(
            scope="category",
            category=category.category,
            metric="uncertainty_label_count",
            operator="gte",
            observed=category.summary.uncertainty_label_count,
            required=policy.minimum_uncertainty_labels_per_category,
        ),
    )


def _decision(checks: tuple[HoldoutAcceptanceCheck, ...]) -> AcceptanceDecision:
    if any(not item.passed and item.metric in _ELIGIBILITY_METRICS for item in checks):
        return "ineligible"
    if any(not item.passed for item in checks):
        return "fail"
    return "pass"


def assess_holdout_quality(
    report: HoldoutEvaluationReport,
    *,
    policy: HoldoutAcceptancePolicy = HOLDOUT_ACCEPTANCE_POLICY_V1,
) -> HoldoutAcceptanceAssessment:
    """Apply the fixed offline policy without changing the evaluation report."""

    try:
        if type(report) is not HoldoutEvaluationReport:
            raise TypeError("report must be an exact HoldoutEvaluationReport")
        if type(policy) is not HoldoutAcceptancePolicy:
            raise TypeError("policy must be an exact HoldoutAcceptancePolicy")
        validated_report = HoldoutEvaluationReport.model_validate(report)
        validated_policy = HoldoutAcceptancePolicy.model_validate(policy)
        if validated_policy != HOLDOUT_ACCEPTANCE_POLICY_V1:
            raise ValueError("acceptance policy is unsupported")

        checks: list[HoldoutAcceptanceCheck] = [
            _check(
                scope="overall",
                category=None,
                metric="coverage_eligible",
                operator="eq",
                observed=validated_report.overall.coverage_eligible,
                required=True,
            )
        ]
        for category in validated_report.categories:
            checks.extend(_category_eligibility_checks(category, validated_policy))
        checks.extend(
            _quality_checks(
                validated_report.overall.summary,
                scope="overall",
                category=None,
                policy=validated_policy,
            )
        )
        for category in validated_report.categories:
            checks.extend(
                _quality_checks(
                    category.summary,
                    scope="category",
                    category=category.category,
                    policy=validated_policy,
                )
            )
        canonical_checks = tuple(checks)
        return HoldoutAcceptanceAssessment(
            schema_version="1.0",
            policy_id=validated_policy.policy_id,
            policy_sha256=holdout_acceptance_policy_sha256(validated_policy),
            evaluation_profile_id=validated_report.profile_id,
            evaluation_profile_sha256=validated_report.profile_sha256,
            evaluation_report_sha256=holdout_evaluation_report_sha256(validated_report),
            dataset_id=validated_report.dataset_id,
            dataset_sha256=validated_report.dataset_sha256,
            prediction_set_sha256=validated_report.prediction_set_sha256,
            ranking_profile_id=validated_report.ranking_profile_id,
            ranking_profile_sha256=validated_report.ranking_profile_sha256,
            decision=_decision(canonical_checks),
            checks=canonical_checks,
        )
    except HoldoutAcceptanceError:
        raise
    except (TypeError, ValueError, ValidationError, HoldoutEvaluationError):
        _raise_invalid_acceptance()


def holdout_acceptance_assessment_sha256(
    assessment: HoldoutAcceptanceAssessment,
) -> str:
    """Return the domain-separated digest of one canonical assessment."""

    try:
        if type(assessment) is not HoldoutAcceptanceAssessment:
            raise TypeError("assessment must be an exact HoldoutAcceptanceAssessment")
        validated = HoldoutAcceptanceAssessment.model_validate(assessment)
        return _canonical_model_sha256(
            HOLDOUT_ACCEPTANCE_ASSESSMENT_DOMAIN,
            validated,
        )
    except HoldoutAcceptanceError:
        raise
    except (TypeError, ValueError, ValidationError, HoldoutEvaluationError):
        _raise_invalid_acceptance()
