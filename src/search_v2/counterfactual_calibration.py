"""Label-free batch calibration for counterfactual condition margins."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationError
from pydantic import model_validator

from src.search_v2.counterfactual_image import ConditionId
from src.search_v2.counterfactual_image import CounterfactualImageScore
from src.search_v2.counterfactual_image import Digest
from src.search_v2.counterfactual_v4 import minimum_positive_profile_sha256


CALIBRATED_RANKING_ENABLED = False
COMMON_DECISION_THRESHOLD = 0.0
MINIMUM_CALIBRATION_CANDIDATES = 4
MAXIMUM_CALIBRATION_CANDIDATES = 32
MINIMUM_OBSERVED_SPAN = 1e-6
MINIMUM_SATURATED_BOUNDARY_COUNT = 2
CALIBRATION_PROFILE_DOMAIN = b"amazon-explorer-counterfactual-batch-calibration-v1\x00"
_INVALID_CONTRACT_MESSAGE = "Inputs did not match the counterfactual calibration contract"

BoundedMargin = Annotated[float, Field(ge=-1.0, le=1.0)]


class CounterfactualCalibrationError(ValueError):
    """A fixed-message rejection for invalid calibration inputs."""


class _StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


class ObservedRangeCalibrationProfile(_StrictFrozenContract):
    schema_version: Literal["1.0"]
    profile_id: Literal["counterfactual-observed-range-unqualified-v1"]
    location: Literal["observed_midrange"]
    scale: Literal["observed_half_range"]
    minimum_candidate_count: Literal[4]
    maximum_candidate_count: Literal[32]
    minimum_observed_span: Annotated[float, Field(gt=0.0, le=1.0)]
    minimum_saturated_boundary_count: Literal[2]
    common_decision_threshold: Literal[0.0]
    labels_used: Literal[False]
    ranking_enabled: Literal[False]


OBSERVED_RANGE_CALIBRATION_PROFILE = ObservedRangeCalibrationProfile(
    schema_version="1.0",
    profile_id="counterfactual-observed-range-unqualified-v1",
    location="observed_midrange",
    scale="observed_half_range",
    minimum_candidate_count=MINIMUM_CALIBRATION_CANDIDATES,
    maximum_candidate_count=MAXIMUM_CALIBRATION_CANDIDATES,
    minimum_observed_span=MINIMUM_OBSERVED_SPAN,
    minimum_saturated_boundary_count=MINIMUM_SATURATED_BOUNDARY_COUNT,
    common_decision_threshold=COMMON_DECISION_THRESHOLD,
    labels_used=False,
    ranking_enabled=False,
)


class ConditionCalibration(_StrictFrozenContract):
    condition_id: ConditionId
    status: Literal["calibrated", "insufficient_span", "insufficient_diversity"]
    observed_count: Annotated[
        int,
        Field(
            ge=MINIMUM_CALIBRATION_CANDIDATES,
            le=MAXIMUM_CALIBRATION_CANDIDATES,
        ),
    ]
    observed_minimum: BoundedMargin
    observed_maximum: BoundedMargin
    center: BoundedMargin | None
    half_span: Annotated[float, Field(gt=0.0, le=1.0)] | None
    calibrated_margins: tuple[BoundedMargin, ...] | None = Field(repr=False)

    @model_validator(mode="after")
    def validate_status(self) -> ConditionCalibration:
        if self.observed_minimum > self.observed_maximum:
            raise ValueError("observed calibration range is reversed")
        if self.status != "calibrated":
            if any(
                value is not None
                for value in (self.center, self.half_span, self.calibrated_margins)
            ):
                raise ValueError("uncalibrated condition must not produce values")
            return self
        if self.center is None or self.half_span is None or self.calibrated_margins is None:
            raise ValueError("calibrated condition is incomplete")
        if len(self.calibrated_margins) != self.observed_count:
            raise ValueError("calibrated condition count is inconsistent")
        return self


class CounterfactualBatchCalibration(_StrictFrozenContract):
    schema_version: Literal["1.0"]
    status: Literal["calibrated", "unknown"]
    condition_set_sha256: Digest
    reference_set_sha256: Digest
    score_profile_sha256: Digest
    calibration_profile_sha256: Digest
    runtime_sha256: Digest
    candidate_image_pixel_sha256s: Annotated[
        tuple[Digest, ...],
        Field(
            min_length=MINIMUM_CALIBRATION_CANDIDATES,
            max_length=MAXIMUM_CALIBRATION_CANDIDATES,
            repr=False,
        ),
    ]
    conditions: Annotated[tuple[ConditionCalibration, ...], Field(min_length=1, max_length=3)]
    common_decision_threshold: Literal[0.0]
    qualified_for_ranking: Literal[False]

    @model_validator(mode="after")
    def validate_status(self) -> CounterfactualBatchCalibration:
        condition_statuses = {item.status for item in self.conditions}
        if self.status == "calibrated" and condition_statuses != {"calibrated"}:
            raise ValueError("calibrated batch contains an uncalibrated condition")
        if self.status == "unknown" and condition_statuses == {"calibrated"}:
            raise ValueError("unknown batch has no failed calibration")
        if any(
            item.observed_count != len(self.candidate_image_pixel_sha256s)
            for item in self.conditions
        ):
            raise ValueError("calibration candidate counts are inconsistent")
        return self


def calibration_profile_sha256(
    profile: ObservedRangeCalibrationProfile = OBSERVED_RANGE_CALIBRATION_PROFILE,
) -> str:
    """Return the stable identity of the strict calibration profile."""
    try:
        validated = ObservedRangeCalibrationProfile.model_validate(profile)
        payload = json.dumps(
            validated.model_dump(mode="json"),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(CALIBRATION_PROFILE_DOMAIN + payload).hexdigest()
    except (TypeError, ValueError, ValidationError) as exc:
        raise CounterfactualCalibrationError(_INVALID_CONTRACT_MESSAGE) from exc


def _calibrate_condition(
    condition_id: str,
    margins: tuple[float, ...],
    profile: ObservedRangeCalibrationProfile,
) -> ConditionCalibration:
    observed_minimum = min(margins)
    observed_maximum = max(margins)
    observed_span = observed_maximum - observed_minimum
    if observed_span < profile.minimum_observed_span:
        return ConditionCalibration(
            condition_id=condition_id,
            status="insufficient_span",
            observed_count=len(margins),
            observed_minimum=observed_minimum,
            observed_maximum=observed_maximum,
            center=None,
            half_span=None,
            calibrated_margins=None,
        )

    crosses_zero = observed_minimum < 0.0 < observed_maximum
    saturated_boundary_count = max(margins.count(-1.0), margins.count(1.0))
    if not crosses_zero and saturated_boundary_count < profile.minimum_saturated_boundary_count:
        return ConditionCalibration(
            condition_id=condition_id,
            status="insufficient_diversity",
            observed_count=len(margins),
            observed_minimum=observed_minimum,
            observed_maximum=observed_maximum,
            center=None,
            half_span=None,
            calibrated_margins=None,
        )

    center = (observed_minimum + observed_maximum) / 2.0
    half_span = observed_span / 2.0
    calibrated_margins = tuple(
        min(1.0, max(-1.0, (margin - center) / half_span)) for margin in margins
    )
    return ConditionCalibration(
        condition_id=condition_id,
        status="calibrated",
        observed_count=len(margins),
        observed_minimum=observed_minimum,
        observed_maximum=observed_maximum,
        center=center,
        half_span=half_span,
        calibrated_margins=calibrated_margins,
    )


def calibrate_minimum_positive_batch(
    scores: tuple[CounterfactualImageScore, ...],
    profile: ObservedRangeCalibrationProfile = OBSERVED_RANGE_CALIBRATION_PROFILE,
) -> CounterfactualBatchCalibration:
    """Center each unlabeled condition range on the shared zero threshold."""
    try:
        calibration_profile = ObservedRangeCalibrationProfile.model_validate(profile)
        if type(scores) is not tuple or not (
            calibration_profile.minimum_candidate_count
            <= len(scores)
            <= calibration_profile.maximum_candidate_count
        ):
            raise TypeError("calibration batch size is invalid")
        validated = tuple(CounterfactualImageScore.model_validate(item) for item in scores)
        if any(item.status != "scored" for item in validated):
            raise ValueError("calibration requires complete scored candidates")
        if {item.score_profile_sha256 for item in validated} != {minimum_positive_profile_sha256()}:
            raise ValueError("calibration requires the minimum-positive v4 score profile")

        first = validated[0]
        bindings = {
            (
                item.condition_set_sha256,
                item.reference_set_sha256,
                item.runtime_sha256,
            )
            for item in validated
        }
        if bindings != {
            (
                first.condition_set_sha256,
                first.reference_set_sha256,
                first.runtime_sha256,
            )
        }:
            raise ValueError("calibration batch bindings do not match")
        condition_ids = tuple(item.condition_id for item in first.condition_margins)
        if any(
            tuple(margin.condition_id for margin in item.condition_margins) != condition_ids
            for item in validated
        ):
            raise ValueError("calibration condition layouts do not match")
        candidate_digests = tuple(item.candidate_image_pixel_sha256 for item in validated)
        if any(item is None for item in candidate_digests):
            raise ValueError("calibration candidate digest is missing")
        if len(candidate_digests) != len(set(candidate_digests)):
            raise ValueError("calibration candidates must be unique")

        conditions = tuple(
            _calibrate_condition(
                condition_id,
                tuple(float(item.condition_margins[index].normalized_margin) for item in validated),
                calibration_profile,
            )
            for index, condition_id in enumerate(condition_ids)
        )
        status = (
            "calibrated" if all(item.status == "calibrated" for item in conditions) else "unknown"
        )
        return CounterfactualBatchCalibration(
            schema_version="1.0",
            status=status,
            condition_set_sha256=first.condition_set_sha256,
            reference_set_sha256=first.reference_set_sha256,
            score_profile_sha256=first.score_profile_sha256,
            calibration_profile_sha256=calibration_profile_sha256(calibration_profile),
            runtime_sha256=first.runtime_sha256,
            candidate_image_pixel_sha256s=candidate_digests,
            conditions=conditions,
            common_decision_threshold=COMMON_DECISION_THRESHOLD,
            qualified_for_ranking=False,
        )
    except CounterfactualCalibrationError:
        raise
    except (TypeError, ValueError, ValidationError) as exc:
        raise CounterfactualCalibrationError(_INVALID_CONTRACT_MESSAGE) from exc
