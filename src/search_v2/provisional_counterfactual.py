"""Human-authorized provisional production use of counterfactual v4 scores."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Annotated
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import ValidationError
from pydantic import model_validator

from src.search_v2.counterfactual_calibration import COMMON_DECISION_THRESHOLD
from src.search_v2.counterfactual_calibration import CounterfactualCalibrationError
from src.search_v2.counterfactual_calibration import calibrate_minimum_positive_batch
from src.search_v2.counterfactual_calibration import calibration_profile_sha256
from src.search_v2.counterfactual_image import CounterfactualImageScore
from src.search_v2.counterfactual_v4 import minimum_positive_profile_sha256


MINIMUM_PROVISIONAL_CANDIDATES = 4
MAXIMUM_PROVISIONAL_CANDIDATES = 32
PROVISIONAL_COUNTERFACTUAL_PROFILE_DOMAIN = (
    b"amazon-explorer-counterfactual-provisional-production-profile-v1\x00"
)
PROVISIONAL_COUNTERFACTUAL_BATCH_DOMAIN = (
    b"amazon-explorer-counterfactual-provisional-production-batch-v1\x00"
)
_INVALID_CONTRACT_MESSAGE = "Inputs did not match the provisional contract"

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
UnitScore = Annotated[float, Field(ge=0.0, le=1.0)]
BoundedMargin = Annotated[float, Field(ge=-1.0, le=1.0)]


class ProvisionalCounterfactualError(ValueError):
    """A fixed-message rejection for provisional production boundary inputs."""


class _StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


class ProvisionalCounterfactualProfile(_StrictFrozenContract):
    schema_version: Literal["1.0"]
    profile_id: Literal["counterfactual-v4-provisional-production-v1"]
    source_score_profile_sha256: Digest
    calibration_profile_sha256: Digest
    common_decision_threshold: Literal[0.0]
    condition_aggregation: Literal["minimum_calibrated_margin"]
    score_transform: Literal["signed_margin_to_unit_interval"]
    minimum_calibration_candidate_count: Literal[4]
    known_holdout_accuracy: Literal[0.875]
    known_holdout_auc: Literal[1.0]
    adoption_basis: Literal["human_authorized_provisional"]
    labels_used_for_runtime_calibration: Literal[False]
    ranking_enabled: Literal[True]


PROVISIONAL_COUNTERFACTUAL_PROFILE = ProvisionalCounterfactualProfile(
    schema_version="1.0",
    profile_id="counterfactual-v4-provisional-production-v1",
    source_score_profile_sha256=minimum_positive_profile_sha256(),
    calibration_profile_sha256=calibration_profile_sha256(),
    common_decision_threshold=COMMON_DECISION_THRESHOLD,
    condition_aggregation="minimum_calibrated_margin",
    score_transform="signed_margin_to_unit_interval",
    minimum_calibration_candidate_count=MINIMUM_PROVISIONAL_CANDIDATES,
    known_holdout_accuracy=0.875,
    known_holdout_auc=1.0,
    adoption_basis="human_authorized_provisional",
    labels_used_for_runtime_calibration=False,
    ranking_enabled=True,
)


class ProvisionalImageCandidateInput(_StrictFrozenContract):
    normalized_product_sha256: Digest
    candidate_image_pixel_sha256: Digest | None
    score: CounterfactualImageScore = Field(repr=False)

    @model_validator(mode="after")
    def validate_image_binding(self) -> ProvisionalImageCandidateInput:
        if self.candidate_image_pixel_sha256 != self.score.candidate_image_pixel_sha256:
            raise ValueError("candidate image binding does not match its score")
        return self


class ProvisionalImageComponent(_StrictFrozenContract):
    normalized_product_sha256: Digest
    candidate_image_pixel_sha256: Digest | None
    status: Literal["available", "missing", "unknown"]
    minimum_calibrated_margin: BoundedMargin | None
    image_score: UnitScore | None
    matched_condition_count: Annotated[int, Field(ge=0, le=3)] | None
    condition_count: Annotated[int, Field(ge=1, le=3)]

    @model_validator(mode="after")
    def validate_status_values(self) -> ProvisionalImageComponent:
        values = (
            self.minimum_calibrated_margin,
            self.image_score,
            self.matched_condition_count,
        )
        if self.status == "available":
            if self.candidate_image_pixel_sha256 is None or any(value is None for value in values):
                raise ValueError("available image component is incomplete")
            return self
        if any(value is not None for value in values):
            raise ValueError("unavailable image component contains a score")
        if self.status == "missing" and self.candidate_image_pixel_sha256 is not None:
            raise ValueError("missing image component contains an image digest")
        return self


class ProvisionalCounterfactualBatch(_StrictFrozenContract):
    schema_version: Literal["1.0"]
    status: Literal["ready", "unknown"]
    profile_sha256: Digest
    condition_set_sha256: Digest
    reference_set_sha256: Digest
    source_score_profile_sha256: Digest
    calibration_profile_sha256: Digest
    runtime_sha256: Digest
    common_decision_threshold: Literal[0.0]
    candidates: Annotated[
        tuple[ProvisionalImageComponent, ...],
        Field(
            min_length=MINIMUM_PROVISIONAL_CANDIDATES,
            max_length=MAXIMUM_PROVISIONAL_CANDIDATES,
            repr=False,
        ),
    ]
    ranking_enabled: bool

    @model_validator(mode="after")
    def validate_status(self) -> ProvisionalCounterfactualBatch:
        available = any(item.status == "available" for item in self.candidates)
        if self.status == "ready" and (not self.ranking_enabled or not available):
            raise ValueError("ready provisional batch is not ranking enabled")
        if self.status == "unknown" and (self.ranking_enabled or available):
            raise ValueError("unknown provisional batch contains available scores")
        return self


def provisional_counterfactual_profile_sha256(
    profile: ProvisionalCounterfactualProfile = PROVISIONAL_COUNTERFACTUAL_PROFILE,
) -> str:
    """Return the stable identity of the human-authorized provisional profile."""
    try:
        validated = ProvisionalCounterfactualProfile.model_validate(profile)
        payload = json.dumps(
            validated.model_dump(mode="json"),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(PROVISIONAL_COUNTERFACTUAL_PROFILE_DOMAIN + payload).hexdigest()
    except (TypeError, ValueError, ValidationError) as exc:
        raise ProvisionalCounterfactualError(_INVALID_CONTRACT_MESSAGE) from exc


def provisional_counterfactual_batch_sha256(
    batch: ProvisionalCounterfactualBatch,
) -> str:
    """Return the stable identity of a provisional image-component batch."""
    try:
        validated = ProvisionalCounterfactualBatch.model_validate(batch)
        payload = json.dumps(
            validated.model_dump(mode="json"),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(PROVISIONAL_COUNTERFACTUAL_BATCH_DOMAIN + payload).hexdigest()
    except (TypeError, ValueError, ValidationError) as exc:
        raise ProvisionalCounterfactualError(_INVALID_CONTRACT_MESSAGE) from exc


def _unavailable_component(
    candidate: ProvisionalImageCandidateInput,
    *,
    status: Literal["missing", "unknown"],
    condition_count: int,
) -> ProvisionalImageComponent:
    return ProvisionalImageComponent(
        normalized_product_sha256=candidate.normalized_product_sha256,
        candidate_image_pixel_sha256=candidate.candidate_image_pixel_sha256,
        status=status,
        minimum_calibrated_margin=None,
        image_score=None,
        matched_condition_count=None,
        condition_count=condition_count,
    )


def build_provisional_counterfactual_batch(
    candidates: tuple[ProvisionalImageCandidateInput, ...],
    profile: ProvisionalCounterfactualProfile = PROVISIONAL_COUNTERFACTUAL_PROFILE,
) -> ProvisionalCounterfactualBatch:
    """Calibrate v4 margins without labels and expose only fail-closed image components."""
    try:
        approved_profile = ProvisionalCounterfactualProfile.model_validate(profile)
        if type(candidates) is not tuple or not (
            MINIMUM_PROVISIONAL_CANDIDATES <= len(candidates) <= MAXIMUM_PROVISIONAL_CANDIDATES
        ):
            raise TypeError("provisional candidate count is invalid")
        validated = tuple(
            ProvisionalImageCandidateInput.model_validate(item) for item in candidates
        )
        product_digests = tuple(item.normalized_product_sha256 for item in validated)
        if len(product_digests) != len(set(product_digests)):
            raise ValueError("provisional products must be unique")

        scores = tuple(item.score for item in validated)
        first = scores[0]
        condition_ids = tuple(item.condition_id for item in first.condition_margins)
        if any(
            (
                item.condition_set_sha256,
                item.reference_set_sha256,
                item.score_profile_sha256,
                item.runtime_sha256,
                tuple(margin.condition_id for margin in item.condition_margins),
            )
            != (
                first.condition_set_sha256,
                first.reference_set_sha256,
                first.score_profile_sha256,
                first.runtime_sha256,
                condition_ids,
            )
            for item in scores
        ):
            raise ValueError("provisional score bindings do not match")
        if not hmac.compare_digest(
            first.score_profile_sha256,
            approved_profile.source_score_profile_sha256,
        ):
            raise ValueError("provisional score profile is not approved")

        scored_candidates = tuple(item for item in validated if item.score.status == "scored")
        if len(scored_candidates) < approved_profile.minimum_calibration_candidate_count:
            calibration = None
        else:
            calibration = calibrate_minimum_positive_batch(
                tuple(item.score for item in scored_candidates)
            )

        condition_count = len(condition_ids)
        ready = calibration is not None and calibration.status == "calibrated"
        calibrated_by_pixel: dict[str, tuple[float, ...]] = {}
        if ready and calibration is not None:
            for index, candidate in enumerate(scored_candidates):
                pixel_digest = candidate.candidate_image_pixel_sha256
                if pixel_digest is None:
                    raise ValueError("scored candidate has no image binding")
                calibrated_by_pixel[pixel_digest] = tuple(
                    float(condition.calibrated_margins[index])
                    for condition in calibration.conditions
                    if condition.calibrated_margins is not None
                )

        components: list[ProvisionalImageComponent] = []
        for candidate in validated:
            if candidate.score.status == "missing":
                components.append(
                    _unavailable_component(
                        candidate,
                        status="missing",
                        condition_count=condition_count,
                    )
                )
                continue
            margins = (
                calibrated_by_pixel.get(candidate.candidate_image_pixel_sha256 or "")
                if candidate.score.status == "scored"
                else None
            )
            if margins is None or len(margins) != condition_count:
                components.append(
                    _unavailable_component(
                        candidate,
                        status="unknown",
                        condition_count=condition_count,
                    )
                )
                continue
            minimum_margin = min(margins)
            components.append(
                ProvisionalImageComponent(
                    normalized_product_sha256=candidate.normalized_product_sha256,
                    candidate_image_pixel_sha256=candidate.candidate_image_pixel_sha256,
                    status="available",
                    minimum_calibrated_margin=minimum_margin,
                    image_score=(minimum_margin + 1.0) / 2.0,
                    matched_condition_count=sum(
                        margin >= approved_profile.common_decision_threshold for margin in margins
                    ),
                    condition_count=condition_count,
                )
            )

        return ProvisionalCounterfactualBatch(
            schema_version="1.0",
            status="ready" if ready else "unknown",
            profile_sha256=provisional_counterfactual_profile_sha256(approved_profile),
            condition_set_sha256=first.condition_set_sha256,
            reference_set_sha256=first.reference_set_sha256,
            source_score_profile_sha256=first.score_profile_sha256,
            calibration_profile_sha256=approved_profile.calibration_profile_sha256,
            runtime_sha256=first.runtime_sha256,
            common_decision_threshold=approved_profile.common_decision_threshold,
            candidates=tuple(components),
            ranking_enabled=ready,
        )
    except ProvisionalCounterfactualError:
        raise
    except (CounterfactualCalibrationError, TypeError, ValueError, ValidationError) as exc:
        raise ProvisionalCounterfactualError(_INVALID_CONTRACT_MESSAGE) from exc
