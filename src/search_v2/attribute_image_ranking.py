"""Attribute-specific evidence with independent shape and RGB comparison paths."""

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator, model_serializer

from src.search_v2.counterfactual_image import VisualConditionSet, visual_condition_set_sha256
from src.search_v2.relative_image_ranking import RelativeImageBatch
from src.search_v2.provisional_counterfactual import ProvisionalImageCandidateInput
from src.search_v2.shape_features import (
    FEATURE_SHA256,
    FeatureComparison,
    ShapeMeasure,
    compare_features,
)
from src.search_v2.shape_similarity import (
    SHAPE_PROFILE_SHA256,
    RegionMask,
    ShapeMargin,
    compare_silhouettes,
    unavailable_shape,
)


PROFILE_ID = "attribute-image-v1"
PROFILE_SHA256 = hashlib.sha256(
    f"{PROFILE_ID}:{SHAPE_PROFILE_SHA256}:shape-only-no-rgb-fallback:min-available".encode()
).hexdigest()
FEATURE_PROFILE_ID = "attribute-image-v2"
FEATURE_PROFILE_SHA256 = hashlib.sha256(
    f"{FEATURE_PROFILE_ID}:{PROFILE_SHA256}:{FEATURE_SHA256}".encode()
).hexdigest()
DIGEST = r"^[0-9a-f]{64}$"


class _Frozen(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", allow_inf_nan=False, revalidate_instances="always"
    )


class ShapeEvidence(_Frozen):
    condition_id: str = Field(pattern=r"^visual-condition-00[123]$")
    target_sha256: str = Field(pattern=DIGEST)
    candidate_mask_sha256: str | None = Field(pattern=DIGEST)
    reference_mask_sha256: tuple[str | None, ...] = Field(min_length=2, max_length=4)
    margin: ShapeMargin
    feature: FeatureComparison | None = None
    reason: Literal[
        "scored",
        "region_unavailable",
        "reference_too_close",
        "extractor_unconfigured",
        "extraction_failed",
        "feature_reference_too_close",
        "reference_direction_mismatch",
        "unobservable",
    ]

    @model_validator(mode="after")
    def validate_evidence(self):
        if self.feature is None and self.reason in {
            "feature_reference_too_close",
            "reference_direction_mismatch",
            "unobservable",
        }:
            raise ValueError("Feature failure requires measurement evidence")
        if self.feature is not None and self.margin != self.feature.margin:
            raise ValueError("Feature measurements differ from shape margin")
        if self.feature is not None and self.reason not in {
            self.feature.status,
            "extraction_failed",
            "extractor_unconfigured",
        }:
            raise ValueError("Feature status differs from shape reason")
        for digest in self.reference_mask_sha256:
            if digest is not None and (
                len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest)
            ):
                raise ValueError("Invalid reference mask digest")
        if self.margin.status != "region_unavailable":
            if (
                self.candidate_mask_sha256 is None
                or None in self.reference_mask_sha256
                or self.reason != self.margin.status
            ):
                raise ValueError("Shape masks do not support the score")
        elif self.reason not in {
            "region_unavailable",
            "extractor_unconfigured",
            "extraction_failed",
            "feature_reference_too_close",
            "reference_direction_mismatch",
            "unobservable",
        }:
            raise ValueError("Invalid shape failure reason")
        return self

    @model_serializer(mode="wrap")
    def serialize_feature(self, handler):
        result = handler(self)
        if self.feature is None:
            result.pop("feature", None)
        return result


def _values(source, shapes):
    by_condition = {s.condition_id: s.margin.normalized_margin for s in shapes}
    margins = [
        by_condition[m.condition_id] if m.condition_id in by_condition else m.normalized_margin
        for m in source.score.condition_margins
    ]
    available = [m for m in margins if m is not None]
    if available:
        score = (min(available) + 1.0) / 2.0
        return (
            "available",
            "scored" if len(available) == len(margins) else "partial_conditions",
            score,
            len(available),
        )
    return (
        ("missing" if source.candidate_image_pixel_sha256 is None else "unknown"),
        "no_computable_conditions",
        None,
        0,
    )


class AttributeImageComponent(_Frozen):
    source: ProvisionalImageCandidateInput = Field(repr=False)
    shapes: tuple[ShapeEvidence, ...] = Field(min_length=1, max_length=3)
    status: Literal["available", "missing", "unknown"]
    reason: Literal["scored", "partial_conditions", "no_computable_conditions"]
    image_score: float | None = Field(ge=0.0, le=1.0)
    usable_condition_count: int = Field(ge=0, le=3)

    @property
    def normalized_product_sha256(self):
        return self.source.normalized_product_sha256

    @model_validator(mode="after")
    def validate_score(self):
        ids = [s.condition_id for s in self.shapes]
        if len(ids) != len(set(ids)) or not set(ids).issubset(
            m.condition_id for m in self.source.score.condition_margins
        ):
            raise ValueError("Shape conditions do not match CLIP evidence")
        if (self.status, self.reason, self.image_score, self.usable_condition_count) != _values(
            self.source, self.shapes
        ):
            raise ValueError("Attribute score does not match its evidence")
        return self


class ShapeTarget(_Frozen):
    condition_id: str = Field(pattern=r"^visual-condition-00[123]$")
    target_sha256: str = Field(pattern=DIGEST)
    measure: ShapeMeasure | None = None
    direction: Literal["higher", "lower"] | None = None

    @model_serializer(mode="wrap")
    def serialize_measure(self, handler):
        result = handler(self)
        if self.measure is None:
            result.pop("measure", None)
        if self.direction is None:
            result.pop("direction", None)
        return result


class AttributeImageBatch(_Frozen):
    profile_id: Literal["attribute-image-v1", "attribute-image-v2"] = PROFILE_ID
    profile_sha256: str = Field(pattern=DIGEST)
    clip_batch: RelativeImageBatch = Field(repr=False)
    shape_targets: tuple[ShapeTarget, ...] = Field(min_length=1, max_length=3)
    region_runtime_sha256: str = Field(pattern=DIGEST)
    candidates: tuple[AttributeImageComponent, ...] = Field(min_length=1, max_length=32)

    @property
    def condition_set_sha256(self):
        return self.clip_batch.condition_set_sha256

    @property
    def reference_set_sha256(self):
        return self.clip_batch.reference_set_sha256

    @property
    def runtime_sha256(self):
        return hashlib.sha256(
            f"{self.clip_batch.runtime_sha256}:{self.region_runtime_sha256}:{FEATURE_SHA256 if self.profile_id == FEATURE_PROFILE_ID else SHAPE_PROFILE_SHA256}".encode()
        ).hexdigest()

    @model_validator(mode="after")
    def validate_bindings(self):
        feature = any(t.measure is not None for t in self.shape_targets)
        if self.profile_id != (
            FEATURE_PROFILE_ID if feature else PROFILE_ID
        ) or self.profile_sha256 != (FEATURE_PROFILE_SHA256 if feature else PROFILE_SHA256):
            raise ValueError("Attribute profile changed")
        expected = self.shape_targets
        ids = tuple(c.condition_id for c in expected)
        if len(set(ids)) != len(ids) or len(self.candidates) != len(self.clip_batch.candidates):
            raise ValueError("Attribute evidence is incomplete")
        for row, original in zip(self.candidates, self.clip_batch.candidates, strict=True):
            if row.source != original.source or tuple(s.condition_id for s in row.shapes) != ids:
                raise ValueError("Attribute source binding changed")
            for shape, target in zip(row.shapes, expected, strict=True):
                if (shape.feature.measure if shape.feature is not None else None) != target.measure:
                    raise ValueError("Attribute measurement binding changed")
                if (
                    shape.feature.direction if shape.feature is not None else None
                ) != target.direction:
                    raise ValueError("Attribute direction binding changed")
                if shape.target_sha256 != target.target_sha256 or len(
                    shape.reference_mask_sha256
                ) != 1 + len(original.source.score.condition_margins):
                    raise ValueError("Attribute target binding changed")
        return self


def build_attribute_image_batch(
    clip_batch, conditions, reference_images, fetched_by_product, extractor
):
    """Fetch no images here; reuse pixels from the validated image evaluator."""
    clip_batch = RelativeImageBatch.model_validate(clip_batch)
    conditions = VisualConditionSet.model_validate(conditions)
    if visual_condition_set_sha256(conditions) != clip_batch.condition_set_sha256:
        raise ValueError("Attribute conditions changed")
    images = {
        i.pixel_sha256: i
        for i in (*reference_images, *(i for _, i in fetched_by_product if i is not None))
    }
    by_pixel, reasons = {}, {}
    targets = tuple(
        dict.fromkeys(
            c.focus.target
            for c in conditions.conditions
            if c.focus is not None and c.focus.kind == "shape" and c.focus.measure != "unobservable"
        )
    )
    runtime = hashlib.sha256(b"region-extractor-unconfigured").hexdigest()
    if extractor is not None and targets:
        runtime = extractor.runtime_sha256
        try:
            result = extractor.extract(tuple(images.values()), targets)
            if type(result) is not dict or set(result) != {(i, t) for i in images for t in targets}:
                raise ValueError("Region extractor returned a different image set")
            for (pixel, target), region in result.items():
                if region is not None and (
                    not isinstance(region, RegionMask)
                    or region.image_pixel_sha256 != pixel
                    or region.target_sha256 != hashlib.sha256(target.encode()).hexdigest()
                ):
                    raise ValueError("Region extractor binding changed")
            by_pixel = result
        except Exception:
            reasons = dict.fromkeys(targets, "extraction_failed")
    else:
        reasons = dict.fromkeys(targets, "extractor_unconfigured")
    rows = []
    for original in clip_batch.candidates:
        shapes = []
        for index, condition in enumerate(conditions.conditions):
            if condition.focus is None or condition.focus.kind != "shape":
                continue
            target = condition.focus.target
            candidate = by_pixel.get((original.source.candidate_image_pixel_sha256, target))
            references = tuple(by_pixel.get((i.pixel_sha256, target)) for i in reference_images)
            positive = tuple(r for i, r in enumerate(references) if i != index + 1)
            negative = references[index + 1]
            margin = (
                compare_silhouettes(
                    candidate.array(), tuple(r.array() for r in positive), negative.array()
                )
                if candidate is not None and all(r is not None for r in references)
                else unavailable_shape()
            )
            feature = None
            if condition.focus.measure is not None:
                feature = compare_features(
                    None if candidate is None else candidate.array(),
                    tuple(None if r is None else r.array() for r in positive),
                    None if negative is None else negative.array(),
                    condition.focus.measure,
                    direction=condition.focus.direction,
                )
                margin = feature.margin
            shapes.append(
                ShapeEvidence(
                    condition_id=condition.condition_id,
                    target_sha256=hashlib.sha256(target.encode()).hexdigest(),
                    candidate_mask_sha256=None if candidate is None else candidate.sha256,
                    reference_mask_sha256=tuple(
                        None if r is None else r.sha256 for r in references
                    ),
                    margin=margin,
                    feature=feature,
                    reason=reasons.get(
                        target, margin.status if feature is None else feature.status
                    ),
                )
            )
        status, reason, score, count = _values(original.source, shapes)
        rows.append(
            AttributeImageComponent(
                source=original.source,
                shapes=tuple(shapes),
                status=status,
                reason=reason,
                image_score=score,
                usable_condition_count=count,
            )
        )
    uses_features = any(
        c.focus is not None and c.focus.measure is not None for c in conditions.conditions
    )
    return AttributeImageBatch(
        profile_id=FEATURE_PROFILE_ID if uses_features else PROFILE_ID,
        profile_sha256=FEATURE_PROFILE_SHA256 if uses_features else PROFILE_SHA256,
        clip_batch=clip_batch,
        shape_targets=tuple(
            ShapeTarget(
                condition_id=c.condition_id,
                target_sha256=hashlib.sha256(c.focus.target.encode()).hexdigest(),
                measure=c.focus.measure,
                direction=c.focus.direction,
            )
            for c in conditions.conditions
            if c.focus is not None and c.focus.kind == "shape"
        ),
        region_runtime_sha256=runtime,
        candidates=tuple(rows),
    )
