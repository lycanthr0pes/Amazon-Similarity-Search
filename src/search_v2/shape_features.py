"""Bounded image-plane measurements selected by an approved visual condition."""

import hashlib
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
from scipy.ndimage import gaussian_filter1d

from src.search_v2.shape_similarity import ShapeMargin, silhouette, unavailable_shape


ShapeMeasure = Literal["side_bulge", "side_smoothness", "aspect_ratio", "unobservable"]
FEATURE_PROFILE = (
    "shape-features-v1:upright:rows64:trim0.15:gaussian2:reference-gap0.02:explicit-direction"
)
FEATURE_SHA256 = hashlib.sha256(FEATURE_PROFILE.encode()).hexdigest()
MIN_FEATURE_SEPARATION = 0.02


def measure_shape(mask, measure):
    if measure not in {"side_bulge", "side_smoothness", "aspect_ratio", "unobservable"}:
        raise ValueError("Unsupported shape measurement")
    if measure == "unobservable" or silhouette(mask) is None:
        return None
    ys, xs = np.nonzero(mask)
    cropped = mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    height, width = cropped.shape
    if min(height, width) < 8 or not cropped.any(axis=1).all():
        return None
    if measure == "aspect_ratio":
        return float(width / (height + width))
    left = cropped.argmax(axis=1).astype(float)
    right = width - 1 - cropped[:, ::-1].argmax(axis=1).astype(float)
    locations = np.linspace(0.15, 0.85, 64) * (height - 1)
    sides = np.stack([np.interp(locations, np.arange(height), s) for s in (left, right)])
    sides = gaussian_filter1d(sides / width, 2.0, axis=1, mode="nearest")
    if measure == "side_bulge":
        widths = sides[1] - sides[0]
        chord = np.linspace(widths[0], widths[-1], len(widths))
        return float(np.clip(np.maximum(widths - chord, 0.0).mean(), 0.0, 1.0))
    # Smooth bends distribute turning; polygon vertices concentrate it.
    curvature = np.abs(np.diff(sides, n=2, axis=1)[:, 4:-4])
    rms = float(np.sqrt(np.mean(curvature**2)))
    return 1.0 if rms < 1e-6 else float(np.clip(curvature.mean() / rms, 0.0, 1.0))


class FeatureComparison(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", allow_inf_nan=False, revalidate_instances="always"
    )
    measure: ShapeMeasure
    direction: Literal["higher", "lower"] | None
    status: Literal[
        "scored",
        "region_unavailable",
        "feature_reference_too_close",
        "reference_direction_mismatch",
        "unobservable",
    ]
    candidate_value: float | None = Field(ge=0.0, le=1.0)
    positive_values: tuple[float | None, ...] = Field(min_length=1, max_length=3)
    negative_value: float | None = Field(ge=0.0, le=1.0)
    margin: ShapeMargin

    @model_validator(mode="after")
    def validate_measurements(self):
        for value in self.positive_values:
            if value is not None and (not np.isfinite(value) or not 0 <= value <= 1):
                raise ValueError("Invalid positive feature value")
        status, margin = _comparison(
            self.measure,
            self.candidate_value,
            self.positive_values,
            self.negative_value,
            self.direction,
        )
        if self.status != status or self.margin != margin:
            raise ValueError("Feature score differs from its measurements")
        return self


def _comparison(measure, current, positives, negative, direction):
    if measure == "unobservable":
        if direction is not None:
            raise ValueError("Unobservable features have no direction")
        if any(v is not None for v in (current, *positives, negative)):
            raise ValueError("Unobservable features cannot have measurements")
        return "unobservable", unavailable_shape()
    if direction not in {"higher", "lower"}:
        raise ValueError("Explicit feature direction required")
    if any(v is None for v in (current, *positives, negative)):
        return "region_unavailable", unavailable_shape()
    gaps = [abs(p - negative) for p in positives]
    # Every positive must distinguish this feature, in a consistent direction.
    if min(gaps) < MIN_FEATURE_SEPARATION or min(positives) < negative < max(positives):
        return "feature_reference_too_close", unavailable_shape()
    sign = 1 if direction == "higher" else -1
    if any(sign * (p - negative) <= 0 for p in positives):
        return "reference_direction_mismatch", unavailable_shape()
    distance = float(np.mean(gaps))
    raw = float(min(abs(current - negative) - abs(current - p) for p in positives))
    return "scored", ShapeMargin(
        status="scored",
        raw_margin=raw,
        reference_distance=distance,
        normalized_margin=max(-1.0, min(1.0, raw / distance)),
    )


def compare_features(candidate, positives, negative, measure, *, direction="higher"):
    if type(positives) is not tuple or not 1 <= len(positives) <= 3:
        raise ValueError("Shape references must be bounded")
    values = [
        None if m is None else measure_shape(m, measure) for m in (candidate, *positives, negative)
    ]
    current, *desired, other = values
    if measure == "unobservable":
        direction = None
    status, margin = _comparison(measure, current, tuple(desired), other, direction)
    return FeatureComparison(
        measure=measure,
        direction=direction,
        status=status,
        candidate_value=current,
        positive_values=tuple(desired),
        negative_value=other,
        margin=margin,
    )
