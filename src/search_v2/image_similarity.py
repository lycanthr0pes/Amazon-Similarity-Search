from __future__ import annotations

import hashlib
import json
import math
import os
import stat
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Annotated
from typing import Literal
from typing import Protocol

from PIL import Image
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import field_validator
from pydantic import model_validator

from src.search_v2.image_proxy import ProxyImage


PHASH_IMAGE_SIZE = 32
PHASH_LOW_FREQUENCY_SIZE = 8
PHASH_BIT_COUNT = 64
PHASH_DUPLICATE_MAX_DISTANCE = 5
MAX_DEDUPE_IMAGES = 192

CLIP_MODEL_ID = "openai/clip-vit-base-patch32"
CLIP_REVISION = "12b36594d53414ecfba93c7200dbb7c7db3c900a"
CLIP_EMBEDDING_DIMENSION = 512
CLIP_MAX_IMAGES_PER_SET = 4
CLIP_IMAGE_RANKING_ENABLED = False
CLIP_PREPROCESSING_PROFILE_ID = "clip-rgb-bicubic-contain-mean-pad-224-v1"
CLIP_RUNTIME_PROFILE_DOMAIN = b"amazon-explorer-clip-runtime-profile-v2\x00"

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_ASSET_PATH_PATTERN = r"^[a-z0-9][a-z0-9_.-]{0,127}$"
_DCT_COSINES = tuple(
    tuple(
        math.cos(math.pi * (2 * coordinate + 1) * frequency / (2 * PHASH_IMAGE_SIZE))
        for coordinate in range(PHASH_IMAGE_SIZE)
    )
    for frequency in range(PHASH_LOW_FREQUENCY_SIZE)
)


class ClipRuntimeError(RuntimeError):
    """Fixed, non-sensitive failure for the pinned CLIP boundary."""


class _StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


class ClipAssetFile(_StrictFrozenContract):
    relative_path: Annotated[str, StringConstraints(pattern=_ASSET_PATH_PATTERN)]
    byte_length: Annotated[int, Field(ge=1, le=2_147_483_647)]
    sha256: Annotated[str, StringConstraints(pattern=_SHA256_PATTERN)]


class ClipAssetManifest(_StrictFrozenContract):
    schema_version: Literal["1.0"]
    model_id: Literal["openai/clip-vit-base-patch32"]
    revision: Literal["12b36594d53414ecfba93c7200dbb7c7db3c900a"]
    embedding_dimension: Literal[512]
    files: Annotated[tuple[ClipAssetFile, ...], Field(min_length=1, max_length=16)]

    @model_validator(mode="after")
    def validate_files(self) -> ClipAssetManifest:
        paths = tuple(asset.relative_path for asset in self.files)
        if len(paths) != len(set(paths)) or paths != tuple(sorted(paths)):
            raise ValueError("CLIP asset paths must be unique and sorted")
        return self


PINNED_CLIP_ASSET_MANIFEST = ClipAssetManifest(
    schema_version="1.0",
    model_id=CLIP_MODEL_ID,
    revision=CLIP_REVISION,
    embedding_dimension=CLIP_EMBEDDING_DIMENSION,
    files=(
        ClipAssetFile(
            relative_path="config.json",
            byte_length=456,
            sha256="20a24818e6ce94b8393759112206420496d48c6dcadacd657db33839bdaf823f",
        ),
        ClipAssetFile(
            relative_path="model.onnx",
            byte_length=605_804_513,
            sha256="57879bb1c23cdeb350d23569dd251ed4b740a96d747c529e94a2bb8040ac5d00",
        ),
        ClipAssetFile(
            relative_path="preprocessor_config.json",
            byte_length=468,
            sha256="5df7e578c37e907a431daf47fd592fc49fa50d23ed4c41285a0a34a58a9d2e06",
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class VerifiedClipAssets:
    root: Path = field(repr=False)
    manifest_sha256: str
    asset_bundle_sha256: str
    file_identities: tuple[tuple[int, ...], ...] = field(repr=False)


class LocalClipImageEncoder(Protocol):
    def encode_images(
        self,
        *,
        images: tuple[ProxyImage, ...],
        asset_root: Path,
        local_files_only: Literal[True],
    ) -> tuple[tuple[float, ...], ...]: ...


class ImagePerceptualHash(_StrictFrozenContract):
    schema_version: Literal["2.0"]
    image_pixel_sha256: Annotated[str, StringConstraints(pattern=_SHA256_PATTERN)]
    value: Annotated[int, Field(ge=0, le=(2**PHASH_BIT_COUNT) - 1)]

    @property
    def hex_value(self) -> str:
        return f"{self.value:016x}"


class ImageDuplicate(_StrictFrozenContract):
    schema_version: Literal["2.0"]
    dropped_index: Annotated[int, Field(ge=0, lt=MAX_DEDUPE_IMAGES)]
    kept_index: Annotated[int, Field(ge=0, lt=MAX_DEDUPE_IMAGES)]
    hamming_distance: Annotated[int, Field(ge=0, le=PHASH_DUPLICATE_MAX_DISTANCE)]


class ImageDedupeResult(_StrictFrozenContract):
    schema_version: Literal["2.0"]
    kept_indices: Annotated[tuple[int, ...], Field(max_length=MAX_DEDUPE_IMAGES)]
    duplicates: Annotated[tuple[ImageDuplicate, ...], Field(max_length=MAX_DEDUPE_IMAGES)]


class ClipEmbedding(_StrictFrozenContract):
    schema_version: Literal["2.0"]
    image_pixel_sha256: Annotated[str, StringConstraints(pattern=_SHA256_PATTERN)]
    runtime_sha256: Annotated[str, StringConstraints(pattern=_SHA256_PATTERN)]
    values: Annotated[
        tuple[float, ...],
        Field(
            min_length=CLIP_EMBEDDING_DIMENSION,
            max_length=CLIP_EMBEDDING_DIMENSION,
            exclude=True,
            repr=False,
        ),
    ]

    @field_validator("values", mode="before")
    @classmethod
    def validate_value_types(cls, value: object) -> object:
        if type(value) is not tuple or any(type(component) is not float for component in value):
            raise ValueError("CLIP embedding components must be floats")
        return value

    @model_validator(mode="after")
    def validate_unit_vector(self) -> ClipEmbedding:
        if not all(math.isfinite(component) for component in self.values):
            raise ValueError("CLIP embedding must be finite")
        norm = math.sqrt(math.fsum(component * component for component in self.values))
        if not math.isclose(norm, 1.0, rel_tol=0.0, abs_tol=1e-6):
            raise ValueError("CLIP embedding must be L2 normalized")
        return self


class ClipImageScore(_StrictFrozenContract):
    schema_version: Literal["2.0"]
    runtime_sha256: Annotated[str, StringConstraints(pattern=_SHA256_PATTERN)]
    angle_max_cosines: Annotated[tuple[float, ...], Field(min_length=4, max_length=4)]
    mean_cosine: Annotated[float, Field(ge=-1.0, le=1.0)]
    image_score: Annotated[float, Field(ge=0.0, le=1.0)]


def clip_runtime_profile_sha256(
    manifest: ClipAssetManifest = PINNED_CLIP_ASSET_MANIFEST,
) -> str:
    validated = ClipAssetManifest.model_validate(manifest)
    payload = json.dumps(
        {
            "asset_manifest": validated.model_dump(mode="json"),
            "preprocessing_profile_id": CLIP_PREPROCESSING_PROFILE_ID,
        },
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(CLIP_RUNTIME_PROFILE_DOMAIN + payload).hexdigest()


def verify_clip_asset_directory(
    root: Path,
    *,
    manifest: ClipAssetManifest = PINNED_CLIP_ASSET_MANIFEST,
) -> VerifiedClipAssets:
    validated = ClipAssetManifest.model_validate(manifest)
    try:
        supplied_root = Path(root)
        if supplied_root.is_symlink() or not supplied_root.is_dir():
            raise ClipRuntimeError("CLIP asset bundle is invalid")
        resolved_root = supplied_root.resolve(strict=True)
        expected_names = tuple(asset.relative_path for asset in validated.files)
        entries = tuple(supplied_root.iterdir())
        if tuple(sorted(entry.name for entry in entries)) != expected_names:
            raise ClipRuntimeError("CLIP asset bundle is invalid")
        file_identities: list[tuple[int, ...]] = []
        for asset in validated.files:
            path = supplied_root / asset.relative_path
            if path.is_symlink() or not path.is_file():
                raise ClipRuntimeError("CLIP asset bundle is invalid")
            stat_before = path.lstat()
            if (
                not stat.S_ISREG(stat_before.st_mode)
                or stat_before.st_nlink != 1
                or stat_before.st_size != asset.byte_length
            ):
                raise ClipRuntimeError("CLIP asset bundle is invalid")
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            stat_after = path.lstat()
            if digest.hexdigest() != asset.sha256 or _stable_stat(stat_after) != _stable_stat(
                stat_before
            ):
                raise ClipRuntimeError("CLIP asset bundle is invalid")
            file_identities.append(_stable_stat(stat_after))
    except ClipRuntimeError:
        raise
    except (OSError, RuntimeError, ValueError, TypeError):
        raise ClipRuntimeError("CLIP asset bundle is invalid") from None

    profile_sha256 = clip_runtime_profile_sha256(validated)
    return VerifiedClipAssets(
        root=resolved_root,
        manifest_sha256=profile_sha256,
        asset_bundle_sha256=profile_sha256,
        file_identities=tuple(file_identities),
    )


def _stable_stat(result: os.stat_result) -> tuple[int, ...]:
    return (
        result.st_mode,
        result.st_ino,
        result.st_dev,
        result.st_nlink,
        result.st_uid,
        result.st_gid,
        result.st_size,
        result.st_mtime_ns,
        result.st_ctime_ns,
    )


def compute_phash(image: ProxyImage) -> ImagePerceptualHash:
    validated = ProxyImage.model_validate(image)
    source = Image.frombytes(
        "RGB",
        (validated.width, validated.height),
        validated.rgb_bytes,
    )
    grayscale = source.convert("L").resize(
        (PHASH_IMAGE_SIZE, PHASH_IMAGE_SIZE),
        resample=Image.Resampling.LANCZOS,
    )
    pixels = tuple(float(value) for value in grayscale.get_flattened_data())
    rows = tuple(
        tuple(pixels[row * PHASH_IMAGE_SIZE : (row + 1) * PHASH_IMAGE_SIZE])
        for row in range(PHASH_IMAGE_SIZE)
    )
    horizontal = tuple(
        tuple(
            math.fsum(rows[y][x] * _DCT_COSINES[u][x] for x in range(PHASH_IMAGE_SIZE))
            for u in range(PHASH_LOW_FREQUENCY_SIZE)
        )
        for y in range(PHASH_IMAGE_SIZE)
    )
    raw_coefficients = tuple(
        math.fsum(horizontal[y][u] * _DCT_COSINES[v][y] for y in range(PHASH_IMAGE_SIZE))
        for v in range(PHASH_LOW_FREQUENCY_SIZE)
        for u in range(PHASH_LOW_FREQUENCY_SIZE)
    )
    maximum_magnitude = max(abs(coefficient) for coefficient in raw_coefficients)
    zero_tolerance = maximum_magnitude * 1e-12
    coefficients = tuple(
        0.0 if abs(coefficient) <= zero_tolerance else coefficient
        for coefficient in raw_coefficients
    )
    ordered = sorted(coefficients)
    median = (ordered[31] + ordered[32]) / 2.0
    value = 0
    for coefficient in coefficients:
        value = (value << 1) | int(coefficient > median)
    return ImagePerceptualHash(
        schema_version="2.0",
        image_pixel_sha256=validated.pixel_sha256,
        value=value,
    )


def phash_hamming_distance(
    first: ImagePerceptualHash,
    second: ImagePerceptualHash,
) -> int:
    validated_first = ImagePerceptualHash.model_validate(first)
    validated_second = ImagePerceptualHash.model_validate(second)
    return (validated_first.value ^ validated_second.value).bit_count()


def deduplicate_image_hashes(
    hashes: tuple[ImagePerceptualHash, ...],
) -> ImageDedupeResult:
    if type(hashes) is not tuple or len(hashes) > MAX_DEDUPE_IMAGES:
        raise ValueError("image hash set is invalid")
    validated = tuple(ImagePerceptualHash.model_validate(item) for item in hashes)
    kept_indices: list[int] = []
    duplicates: list[ImageDuplicate] = []
    for index, current in enumerate(validated):
        nearest: tuple[int, int] | None = None
        for kept_index in kept_indices:
            distance = phash_hamming_distance(current, validated[kept_index])
            candidate = (distance, kept_index)
            if nearest is None or candidate < nearest:
                nearest = candidate
        if nearest is not None and nearest[0] <= PHASH_DUPLICATE_MAX_DISTANCE:
            duplicates.append(
                ImageDuplicate(
                    schema_version="2.0",
                    dropped_index=index,
                    kept_index=nearest[1],
                    hamming_distance=nearest[0],
                )
            )
        else:
            kept_indices.append(index)
    return ImageDedupeResult(
        schema_version="2.0",
        kept_indices=tuple(kept_indices),
        duplicates=tuple(duplicates),
    )


def run_pinned_clip_image_encoder(
    images: tuple[ProxyImage, ...],
    *,
    asset_root: Path,
    encoder: LocalClipImageEncoder,
    manifest: ClipAssetManifest = PINNED_CLIP_ASSET_MANIFEST,
) -> tuple[ClipEmbedding, ...]:
    if type(images) is not tuple or not 1 <= len(images) <= CLIP_MAX_IMAGES_PER_SET:
        raise ClipRuntimeError("CLIP image set is invalid")
    try:
        validated_images = tuple(ProxyImage.model_validate(image) for image in images)
    except Exception:
        raise ClipRuntimeError("CLIP image set is invalid") from None
    verified = verify_clip_asset_directory(asset_root, manifest=manifest)
    try:
        raw_embeddings = encoder.encode_images(
            images=validated_images,
            asset_root=verified.root,
            local_files_only=True,
        )
    except Exception:
        raise ClipRuntimeError("CLIP encoder failed") from None
    if type(raw_embeddings) is not tuple or len(raw_embeddings) != len(validated_images):
        raise ClipRuntimeError("CLIP encoder output is invalid")

    embeddings: list[ClipEmbedding] = []
    for image, raw_embedding in zip(validated_images, raw_embeddings, strict=True):
        if (
            type(raw_embedding) is not tuple
            or len(raw_embedding) != CLIP_EMBEDDING_DIMENSION
            or any(type(component) is not float for component in raw_embedding)
            or not all(math.isfinite(component) for component in raw_embedding)
        ):
            raise ClipRuntimeError("CLIP encoder output is invalid")
        norm = math.sqrt(math.fsum(component * component for component in raw_embedding))
        if not math.isfinite(norm) or norm <= 0.0:
            raise ClipRuntimeError("CLIP encoder output is invalid")
        normalized = tuple(component / norm for component in raw_embedding)
        try:
            embeddings.append(
                ClipEmbedding(
                    schema_version="2.0",
                    image_pixel_sha256=image.pixel_sha256,
                    runtime_sha256=verified.manifest_sha256,
                    values=normalized,
                )
            )
        except Exception:
            raise ClipRuntimeError("CLIP encoder output is invalid") from None
    return tuple(embeddings)


def score_clip_image_similarity(
    reference_embeddings: tuple[ClipEmbedding, ...],
    candidate_embeddings: tuple[ClipEmbedding, ...],
) -> ClipImageScore:
    if (
        type(reference_embeddings) is not tuple
        or len(reference_embeddings) != 4
        or type(candidate_embeddings) is not tuple
        or not 1 <= len(candidate_embeddings) <= CLIP_MAX_IMAGES_PER_SET
    ):
        raise ClipRuntimeError("CLIP embedding set is invalid")
    try:
        references = tuple(ClipEmbedding.model_validate(item) for item in reference_embeddings)
        candidates = tuple(ClipEmbedding.model_validate(item) for item in candidate_embeddings)
    except Exception:
        raise ClipRuntimeError("CLIP embedding set is invalid") from None
    runtime_digests = {item.runtime_sha256 for item in (*references, *candidates)}
    approved_runtime_sha256 = clip_runtime_profile_sha256()
    if runtime_digests != {approved_runtime_sha256}:
        raise ClipRuntimeError("CLIP embedding set is invalid")

    angle_maxima = tuple(
        max(_bounded_cosine(reference.values, candidate.values) for candidate in candidates)
        for reference in references
    )
    mean_cosine = math.fsum(angle_maxima) / 4.0
    image_score = min(1.0, max(0.0, (mean_cosine + 1.0) / 2.0))
    return ClipImageScore(
        schema_version="2.0",
        runtime_sha256=approved_runtime_sha256,
        angle_max_cosines=angle_maxima,
        mean_cosine=mean_cosine,
        image_score=image_score,
    )


def _bounded_cosine(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    value = math.fsum(left * right for left, right in zip(first, second, strict=True))
    return min(1.0, max(-1.0, value))
