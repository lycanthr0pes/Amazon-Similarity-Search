"""Offline selection policy for counterfactual development specifications."""

from __future__ import annotations

from typing import Annotated
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import ValidationError
from pydantic import model_validator


_INVALID_COMPARISON_MESSAGE = "Inputs did not match the counterfactual comparison contract"
_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
_SPECIFICATION_ID_PATTERN = r"^[a-z0-9][a-z0-9._-]{0,63}$"

Digest = Annotated[str, StringConstraints(pattern=_DIGEST_PATTERN)]
SpecificationId = Annotated[str, StringConstraints(pattern=_SPECIFICATION_ID_PATTERN)]
UnitMetric = Annotated[float, Field(ge=0.0, le=1.0)]


class CounterfactualSelectionError(ValueError):
    """A fixed-message rejection for incomparable development results."""


class _StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


class CounterfactualDevelopmentMetrics(_StrictFrozenContract):
    schema_version: Literal["1.0"]
    specification_id: SpecificationId
    absolute_assessment: Literal["fail"]
    development_dataset_sha256: Digest
    labels_sha256: Digest
    evaluation_contract_sha256: Digest
    correct_count: Annotated[int, Field(ge=0)]
    evaluation_count: Annotated[int, Field(ge=1)]
    pairwise_auc: UnitMetric
    worst_condition_auc: UnitMetric

    @model_validator(mode="after")
    def validate_counts(self) -> CounterfactualDevelopmentMetrics:
        if self.correct_count > self.evaluation_count:
            raise ValueError("correct count exceeds the evaluation count")
        return self


class CounterfactualDevelopmentSelection(_StrictFrozenContract):
    schema_version: Literal["1.0"]
    policy_id: Literal["counterfactual-development-relative-accuracy-v1"]
    decision: Literal["pass"]
    selection_basis: Literal["relative_development_accuracy"]
    tie_breaker: Literal[
        "accuracy",
        "pairwise_auc",
        "worst_condition_auc",
        "current_on_exact_tie",
    ]
    winner_specification_id: SpecificationId
    loser_specification_id: SpecificationId
    winner_accuracy: UnitMetric
    eligible_for_independent_holdout: Literal[True]
    qualified_for_ranking: Literal[False]


def _selection_key(metrics: CounterfactualDevelopmentMetrics) -> tuple[int, float, float]:
    return (
        metrics.correct_count,
        metrics.pairwise_auc,
        metrics.worst_condition_auc,
    )


def _tie_breaker(
    current: CounterfactualDevelopmentMetrics,
    redesigned: CounterfactualDevelopmentMetrics,
) -> str:
    if current.correct_count != redesigned.correct_count:
        return "accuracy"
    if current.pairwise_auc != redesigned.pairwise_auc:
        return "pairwise_auc"
    if current.worst_condition_auc != redesigned.worst_condition_auc:
        return "worst_condition_auc"
    return "current_on_exact_tie"


def select_relative_development_winner(
    *,
    current: CounterfactualDevelopmentMetrics,
    redesigned: CounterfactualDevelopmentMetrics,
) -> CounterfactualDevelopmentSelection:
    """Select one development-pass winner without qualifying it for ranking."""

    try:
        if type(current) is not CounterfactualDevelopmentMetrics:
            raise TypeError("current metrics must use the exact contract type")
        if type(redesigned) is not CounterfactualDevelopmentMetrics:
            raise TypeError("redesigned metrics must use the exact contract type")
        current_metrics = CounterfactualDevelopmentMetrics.model_validate(current)
        redesigned_metrics = CounterfactualDevelopmentMetrics.model_validate(redesigned)
        if current_metrics.specification_id == redesigned_metrics.specification_id:
            raise ValueError("development specifications must be distinct")
        current_binding = (
            current_metrics.development_dataset_sha256,
            current_metrics.labels_sha256,
            current_metrics.evaluation_contract_sha256,
            current_metrics.evaluation_count,
        )
        redesigned_binding = (
            redesigned_metrics.development_dataset_sha256,
            redesigned_metrics.labels_sha256,
            redesigned_metrics.evaluation_contract_sha256,
            redesigned_metrics.evaluation_count,
        )
        if current_binding != redesigned_binding:
            raise ValueError("development evaluations are not comparable")

        if _selection_key(redesigned_metrics) > _selection_key(current_metrics):
            winner = redesigned_metrics
            loser = current_metrics
        else:
            winner = current_metrics
            loser = redesigned_metrics
        return CounterfactualDevelopmentSelection(
            schema_version="1.0",
            policy_id="counterfactual-development-relative-accuracy-v1",
            decision="pass",
            selection_basis="relative_development_accuracy",
            tie_breaker=_tie_breaker(current_metrics, redesigned_metrics),
            winner_specification_id=winner.specification_id,
            loser_specification_id=loser.specification_id,
            winner_accuracy=winner.correct_count / winner.evaluation_count,
            eligible_for_independent_holdout=True,
            qualified_for_ranking=False,
        )
    except CounterfactualSelectionError:
        raise
    except (TypeError, ValueError, ValidationError) as exc:
        raise CounterfactualSelectionError(_INVALID_COMPARISON_MESSAGE) from exc
