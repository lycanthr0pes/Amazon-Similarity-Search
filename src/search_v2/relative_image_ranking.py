"""Relative visual ordering independent of the retrieved batch distribution."""

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.search_v2.counterfactual_v4 import minimum_positive_profile_sha256
from src.search_v2.image_similarity import clip_runtime_profile_sha256
from src.search_v2.siglip2 import (
    runtime_sha256 as siglip2_runtime_sha256,
    SCORE_PROFILE_SHA256 as SIGLIP2_SCORE_SHA256,
)
from src.search_v2.provisional_counterfactual import ProvisionalImageCandidateInput


PROFILE_ID = "relative-image-v1"
PROFILE_SHA256 = hashlib.sha256(
    b"relative-image-v1:minimum-computable-margin:signed-to-unit:no-calibration"
).hexdigest()


APPEARANCE_PROFILE_SHA256 = hashlib.sha256(
    b"appearance-image-v1:whole-image-similarity:relative-image-v1:no-geometry"
).hexdigest()


SIGLIP2_APPEARANCE_SHA256 = hashlib.sha256(
    b"siglip2-appearance-image-v1:whole-image-similarity:minimum-computable-margin:no-calibration"
).hexdigest()


class _Frozen(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", revalidate_instances="always", allow_inf_nan=False
    )


def _values(source):
    margins = [m.normalized_margin for m in source.score.condition_margins if m.status == "scored"]
    if margins:
        minimum = min(margins)
        reason = (
            "scored"
            if len(margins) == len(source.score.condition_margins)
            else "partial_conditions"
        )
        return "available", reason, minimum, (minimum + 1.0) / 2.0, len(margins)
    missing = source.score.status == "missing"
    return (
        "missing" if missing else "unknown",
        "missing_image" if missing else "indistinguishable_references",
        None,
        None,
        0,
    )


class RelativeImageComponent(_Frozen):
    source: ProvisionalImageCandidateInput = Field(repr=False)
    status: Literal["available", "missing", "unknown"]
    reason: Literal["scored", "partial_conditions", "missing_image", "indistinguishable_references"]
    minimum_margin: float | None = Field(ge=-1.0, le=1.0)
    image_score: float | None = Field(ge=0.0, le=1.0)
    usable_condition_count: int = Field(ge=0, le=3)

    @property
    def normalized_product_sha256(self):
        return self.source.normalized_product_sha256

    @model_validator(mode="after")
    def validate_values(self):
        if (
            self.status,
            self.reason,
            self.minimum_margin,
            self.image_score,
            self.usable_condition_count,
        ) != _values(self.source):
            raise ValueError("Relative image score does not match its evidence")
        return self


class RelativeImageBatch(_Frozen):
    profile_id: Literal["relative-image-v1"] = PROFILE_ID
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    condition_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reference_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["ready", "unknown"]
    candidates: tuple[RelativeImageComponent, ...] = Field(min_length=1, max_length=32)
    ranking_enabled: bool

    @model_validator(mode="after")
    def validate_bindings(self):
        ready = any(c.status == "available" for c in self.candidates)
        if (
            self.profile_sha256
            != (
                SIGLIP2_APPEARANCE_SHA256
                if self.profile_id == "siglip2-appearance-image-v1"
                else APPEARANCE_PROFILE_SHA256
                if self.profile_id == "appearance-image-v1"
                else PROFILE_SHA256
            )
            or self.ranking_enabled != ready
            or (self.status != ("ready" if ready else "unknown"))
        ):
            raise ValueError("Relative image profile or availability is invalid")
        products = [c.normalized_product_sha256 for c in self.candidates]
        if len(products) != len(set(products)):
            raise ValueError("Relative image products must be unique")
        first_ids = tuple(m.condition_id for m in self.candidates[0].source.score.condition_margins)
        for candidate in self.candidates:
            score = candidate.source.score
            if (
                score.condition_set_sha256 != self.condition_set_sha256
                or score.reference_set_sha256 != self.reference_set_sha256
                or score.runtime_sha256 != self.runtime_sha256
                or self.runtime_sha256
                != (
                    siglip2_runtime_sha256()
                    if self.profile_id == "siglip2-appearance-image-v1"
                    else clip_runtime_profile_sha256()
                )
                or score.score_profile_sha256
                != (
                    SIGLIP2_SCORE_SHA256
                    if self.profile_id == "siglip2-appearance-image-v1"
                    else minimum_positive_profile_sha256()
                )
                or tuple(m.condition_id for m in score.condition_margins) != first_ids
            ):
                raise ValueError("Relative image evidence binding is invalid")
        return self


def _build_image_batch(candidates, batch_type, profile_sha256):
    if type(candidates) is not tuple or not 1 <= len(candidates) <= 32:
        raise ValueError("Relative image candidate count is invalid")
    rows = []
    for candidate in candidates:
        source = ProvisionalImageCandidateInput.model_validate(candidate)
        status, reason, margin, score, count = _values(source)
        rows.append(
            RelativeImageComponent(
                source=source,
                status=status,
                reason=reason,
                minimum_margin=margin,
                image_score=score,
                usable_condition_count=count,
            )
        )
    first = rows[0].source.score
    ready = any(row.status == "available" for row in rows)
    return batch_type(
        profile_sha256=profile_sha256,
        condition_set_sha256=first.condition_set_sha256,
        reference_set_sha256=first.reference_set_sha256,
        runtime_sha256=first.runtime_sha256,
        status="ready" if ready else "unknown",
        ranking_enabled=ready,
        candidates=tuple(rows),
    )


class AppearanceImageBatch(RelativeImageBatch):
    """Global visual similarity, without verified part or attribute evidence."""

    profile_id: Literal["appearance-image-v1"] = "appearance-image-v1"
    evidence_scope: Literal["whole_image_similarity"] = "whole_image_similarity"


def build_relative_image_batch(candidates):
    return _build_image_batch(candidates, RelativeImageBatch, PROFILE_SHA256)


def build_appearance_image_batch(candidates):
    return _build_image_batch(candidates, AppearanceImageBatch, APPEARANCE_PROFILE_SHA256)


class Siglip2AppearanceImageBatch(RelativeImageBatch):
    """Whole-image SigLIP 2 evidence, separate from old CLIP history and scores."""

    profile_id: Literal["siglip2-appearance-image-v1"] = "siglip2-appearance-image-v1"
    evidence_scope: Literal["whole_image_similarity"] = "whole_image_similarity"


def build_siglip2_appearance_batch(candidates):
    return _build_image_batch(candidates, Siglip2AppearanceImageBatch, SIGLIP2_APPEARANCE_SHA256)
