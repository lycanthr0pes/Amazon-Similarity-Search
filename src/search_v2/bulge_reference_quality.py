"""Check reference separation before image approval, without scoring products."""

from typing import Literal
import hashlib

import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, computed_field
from scipy.ndimage import distance_transform_edt, gaussian_filter, rotate

from src.search_v2.bulge_measurement import measure
from src.search_v2.counterfactual_reference_approval import _proxy_image


REFERENCE_QUALITY_PROFILE = (
    "bulge-reference-quality-v1:bilateral:min-component0.995:tilt20:trim0.15:rows64:"
    "gaussian2:endpoint-band5:rotation3:scale0.9-1.1:boundary2:noise12-sigma6:"
    "seeds11001-11002:valid19of20:minimum-gap0.02"
)
REFERENCE_QUALITY_SHA256 = hashlib.sha256(REFERENCE_QUALITY_PROFILE.encode()).hexdigest()


class BulgeReferenceError(ValueError):
    def __init__(self):
        super().__init__("Candidate reference quality check failed")


class BulgeReferenceQuality(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", allow_inf_nan=False)
    direction: Literal["higher", "lower"]
    profile_id: Literal["bulge-reference-quality-v1"] = "bulge-reference-quality-v1"
    positive_values: tuple[float | None, ...] = Field(min_length=21, max_length=21)
    negative_values: tuple[float | None, ...] = Field(min_length=21, max_length=21)
    threshold: Literal[0.02] = 0.02
    failure: Literal["extractor_unconfigured", "extraction_failed"] | None = None

    @computed_field
    @property
    def minimum_gap(self) -> float | None:
        positive = [v for v in self.positive_values if v is not None]
        negative = [v for v in self.negative_values if v is not None]
        if not positive or not negative:
            return None
        if self.direction == "higher":
            return min(positive) - max(negative)
        return min(negative) - max(positive)

    @computed_field
    @property
    def status(self) -> str:
        if self.failure:
            return self.failure
        p, n = self.positive_values[0], self.negative_values[0]
        if (
            p is None
            or n is None
            or any(
                sum(v is not None for v in values[1:]) < 19
                for values in (self.positive_values, self.negative_values)
            )
        ):
            return "region_unavailable"
        sign = 1 if self.direction == "higher" else -1
        if sign * (p - n) < 0:
            return "reference_direction_mismatch"
        if self.minimum_gap < self.threshold:
            return "reference_too_close"
        return "passed"


def _variants(mask, seed):
    for angle in (-3, 3):
        yield rotate(mask, angle, reshape=False, order=0, prefilter=False)
    for scale in (0.9, 1.1):
        source = Image.fromarray(mask)
        resized = source.resize(
            tuple(round(n * scale) for n in source.size), Image.Resampling.NEAREST
        )
        canvas = Image.new("1", source.size)
        canvas.paste(resized, tuple((a - b) // 2 for a, b in zip(source.size, resized.size)))
        yield np.asarray(canvas).astype(bool)
    signed = distance_transform_edt(mask) - distance_transform_edt(~mask)
    signed -= 0.5 * np.sign(signed)
    for offset in (-2, -1, 1, 2):
        yield signed + offset > 0
    rng = np.random.default_rng(seed)
    for _ in range(12):
        noise = gaussian_filter(rng.normal(size=mask.shape), sigma=6)
        noise *= 2 / np.max(np.abs(noise))
        yield signed + noise > 0


def _measurements(mask, seed):
    if mask is None:
        return (None,) * 21
    original = measure(mask)
    if original is None:
        return (None,) * 21
    values = [original["mean"]]
    for variant in _variants(mask, seed):
        result = measure(variant)
        values.append(None if result is None else result["mean"])
    return tuple(values)


def assess_bulge_pair(positive, negative, *, direction):
    if direction not in ("higher", "lower"):
        raise ValueError("Explicit bulge direction required")
    return BulgeReferenceQuality(
        direction=direction,
        positive_values=_measurements(positive, 11001),
        negative_values=_measurements(negative, 11002),
    )


def assess_bulge_references(conditions, artifacts, extractor):
    targets = [c for c in conditions.conditions if c.focus and c.focus.measure == "side_bulge"]
    if not targets:
        return ()
    if extractor is None:
        return tuple((c.condition_id, _failure(c, "extractor_unconfigured")) for c in targets)
    try:
        images = tuple(_proxy_image(a) for a in artifacts)
        if len(images) != 1 + len(conditions.conditions):
            raise ValueError("Reference images do not match conditions")
        regions = extractor.extract(images, tuple(dict.fromkeys(c.focus.target for c in targets)))
        reports = []
        for condition in targets:
            index = next(i for i, c in enumerate(conditions.conditions, 1) if c == condition)
            masks = []
            for image in (images[0], images[index]):
                region = regions.get((image.pixel_sha256, condition.focus.target))
                if region is not None and (
                    region.image_pixel_sha256 != image.pixel_sha256
                    or region.target_sha256
                    != hashlib.sha256(condition.focus.target.encode()).hexdigest()
                ):
                    raise ValueError("Region binding differs from reference")
                masks.append(None if region is None else region.array())
            reports.append(
                (
                    condition.condition_id,
                    assess_bulge_pair(*masks, direction=condition.focus.direction),
                )
            )
        return tuple(reports)
    except Exception:
        return tuple((c.condition_id, _failure(c, "extraction_failed")) for c in targets)


def _failure(condition, reason):
    return BulgeReferenceQuality(
        direction=condition.focus.direction,
        positive_values=(None,) * 21,
        negative_values=(None,) * 21,
        failure=reason,
    )
