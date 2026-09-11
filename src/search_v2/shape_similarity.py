"""Two-dimensional shape comparison, independent of colour and CLIP embeddings."""

from dataclasses import dataclass
import hashlib
import re

import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, model_validator


SHAPE_PROFILE = "silhouette-iou-v1:96px:aspect-preserved:min-positive:reference-distance"
SHAPE_PROFILE_SHA256 = hashlib.sha256(SHAPE_PROFILE.encode()).hexdigest()
NORMALIZED_SIZE = 96
REGION_MAX_SIZE = 512


@dataclass(frozen=True, repr=False)
class RegionMask:
    image_pixel_sha256: str
    target_sha256: str
    width: int
    height: int
    data: bytes

    def __post_init__(self):
        if (
            type(self.data) is not bytes
            or type(self.width) is not int
            or type(self.height) is not int
            or not all(
                re.fullmatch(r"[0-9a-f]{64}", x)
                for x in (self.image_pixel_sha256, self.target_sha256)
            )
            or not 1 <= self.width <= REGION_MAX_SIZE
            or not 1 <= self.height <= REGION_MAX_SIZE
            or len(self.data) != self.width * self.height
            or set(self.data) - {0, 1}
        ):
            raise ValueError("Invalid target mask")

    @classmethod
    def from_array(cls, image_digest, target, array):
        if not isinstance(array, np.ndarray) or array.dtype != np.bool_ or array.ndim != 2:
            raise ValueError("Target mask must be a boolean plane")
        return cls(
            image_digest,
            hashlib.sha256(target.encode()).hexdigest(),
            array.shape[1],
            array.shape[0],
            array.tobytes(),
        )

    def array(self):
        return (
            np.frombuffer(self.data, dtype=np.uint8).reshape(self.height, self.width).astype(bool)
        )

    @property
    def sha256(self):
        header = (
            f"{self.image_pixel_sha256}:{self.target_sha256}:{self.width}:{self.height}:".encode()
        )
        return hashlib.sha256(header + self.data).hexdigest()


class ShapeMargin(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", allow_inf_nan=False, revalidate_instances="always"
    )
    status: str = Field(pattern=r"^(scored|region_unavailable|reference_too_close)$")
    raw_margin: float | None = Field(ge=-1.0, le=1.0)
    reference_distance: float | None = Field(ge=0.0, le=1.0)
    normalized_margin: float | None = Field(ge=-1.0, le=1.0)

    @model_validator(mode="after")
    def validate_score(self):
        if self.status == "region_unavailable":
            valid = self.raw_margin is self.reference_distance is self.normalized_margin is None
        elif self.raw_margin is None or self.reference_distance is None:
            valid = False
        elif self.status == "reference_too_close":
            valid = self.reference_distance < 1e-6 and self.normalized_margin is None
        else:
            valid = self.reference_distance >= 1e-6 and self.normalized_margin == max(
                -1.0, min(1.0, self.raw_margin / self.reference_distance)
            )
        if not valid:
            raise ValueError("Shape margin does not match its evidence")
        return self


def unavailable_shape():
    return ShapeMargin(
        status="region_unavailable",
        raw_margin=None,
        reference_distance=None,
        normalized_margin=None,
    )


def silhouette(mask):
    """Crop the target and fit it to a square without stretching either axis."""
    if not isinstance(mask, np.ndarray) or mask.ndim != 2 or mask.dtype != np.bool_:
        raise ValueError("Shape input must be a boolean plane")
    if not all(1 <= n <= REGION_MAX_SIZE for n in mask.shape):
        raise ValueError("Shape dimensions are invalid")
    if not mask.any() or mask.all():
        return None
    # A target crossing the image boundary has no complete observable outline.
    if mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any():
        return None
    ys, xs = np.nonzero(mask)
    crop = Image.fromarray(mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1])
    scale = (NORMALIZED_SIZE - 4) / max(crop.size)
    size = tuple(max(1, round(n * scale)) for n in crop.size)
    crop = crop.resize(size, Image.Resampling.NEAREST)
    canvas = Image.new("1", (NORMALIZED_SIZE, NORMALIZED_SIZE))
    canvas.paste(crop, tuple((NORMALIZED_SIZE - n) // 2 for n in size))
    return np.asarray(canvas, dtype=bool)


def _iou(first, second):
    return float(np.logical_and(first, second).sum() / np.logical_or(first, second).sum())


def compare_silhouettes(candidate, positives, negative):
    if type(positives) is not tuple or not 1 <= len(positives) <= 3:
        raise ValueError("Shape references must be bounded")
    values = tuple(None if m is None else silhouette(m) for m in (candidate, *positives, negative))
    if any(m is None for m in values):
        return unavailable_shape()
    current, *desired, other = values
    distance = float(np.mean([1.0 - _iou(p, other) for p in desired]))
    margin = min(_iou(current, p) for p in desired) - _iou(current, other)
    return ShapeMargin(
        status="scored" if distance >= 1e-6 else "reference_too_close",
        raw_margin=margin,
        reference_distance=distance,
        normalized_margin=max(-1.0, min(1.0, margin / distance)) if distance >= 1e-6 else None,
    )
