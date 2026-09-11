"""Pinned image-only SigLIP 2 adapter with isolated, bounded offline inference."""

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image
from pydantic import Field

from src.search_v2.image_proxy import ProxyImage
from src.search_v2.image_similarity import ClipEmbedding, _stable_stat
from src.search_v2.counterfactual_v4 import _score_conditions


_MANIFEST = Path(__file__).with_name("siglip2_assets.json")
_WORKER = Path(__file__).with_name("siglip2_worker.py")
SCORE_PROFILE_SHA256 = hashlib.sha256(
    b"siglip2-minimum-positive-v1:minimum-cosine:mean-reference-distance:1e-6:clamp"
).hexdigest()
MAX_IMAGES = 36
TIMEOUT_SECONDS = 600


class Siglip2Embedding(ClipEmbedding):
    """Distinct dimension and runtime; never accepted as a CLIP embedding."""

    values: tuple[float, ...] = Field(min_length=768, max_length=768, exclude=True, repr=False)


def runtime_sha256():
    return hashlib.sha256(
        b"siglip2-image-runtime-v1:rgb-bilinear-resize224:mean-std0.5:fp32:cpu2:batch4\x00"
        + _MANIFEST.read_bytes()
        + _WORKER.read_bytes()
        + Path(__file__).read_bytes()
    ).hexdigest()


def verify_assets(root):
    try:
        if not isinstance(root, Path) or not root.is_absolute() or not root.is_dir():
            raise ValueError("Prepared assets required")
        for name, expected in json.loads(_MANIFEST.read_text())["files"].items():
            path = root / name
            before = path.stat()
            with path.open("rb") as stream:
                actual = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    actual.update(chunk)
            if actual.hexdigest() != expected or _stable_stat(before) != _stable_stat(path.stat()):
                raise ValueError("Changed assets")
    except (OSError, TypeError, ValueError):
        raise ValueError("SigLIP 2 assets are missing or changed") from None


def run_pinned_siglip2_image_encoder(images, *, asset_root, encoder):
    try:
        if type(images) is not tuple or not 1 <= len(images) <= MAX_IMAGES:
            raise ValueError("Invalid image count")
        images = tuple(ProxyImage.model_validate(image) for image in images)
        verify_assets(asset_root)
        runtime = runtime_sha256()
        rows = encoder.encode_images(images=images, asset_root=asset_root)
        if type(rows) is not tuple or len(rows) != len(images):
            raise ValueError("Invalid embedding count")
        embeddings = []
        for image, row in zip(images, rows, strict=True):
            if (
                type(row) is not tuple
                or len(row) != 768
                or any(type(x) is not float or not math.isfinite(x) for x in row)
            ):
                raise ValueError("Invalid embedding")
            norm = math.sqrt(math.fsum(x * x for x in row))
            if norm <= 0:
                raise ValueError("Zero embedding")
            embeddings.append(
                Siglip2Embedding(
                    schema_version="2.0",
                    image_pixel_sha256=image.pixel_sha256,
                    runtime_sha256=runtime,
                    values=tuple(x / norm for x in row),
                )
            )
        verify_assets(asset_root)
        if runtime != runtime_sha256():
            raise ValueError("Changed runtime")
        return tuple(embeddings)
    except Exception:
        raise ValueError("SigLIP 2 image encoding failed") from None


def score_conditions(*, condition_set, reference_set, reference_embeddings, candidate_embedding):
    return _score_conditions(
        condition_set=condition_set,
        reference_set=reference_set,
        reference_embeddings=reference_embeddings,
        candidate_embedding=candidate_embedding,
        embedding_type=Siglip2Embedding,
        approved_runtime=runtime_sha256(),
        profile_digest=SCORE_PROFILE_SHA256,
        reference_minimum=1e-6,
    )


class LocalSiglip2ImageEncoder:
    def __init__(self, python: Path):
        if not isinstance(python, Path) or not python.is_absolute() or not python.is_file():
            raise ValueError("Prepared SigLIP 2 Python executable is required")
        self._python = python

    def encode_images(self, *, images, asset_root):
        try:
            if type(images) is not tuple or not 1 <= len(images) <= MAX_IMAGES:
                raise ValueError("Invalid image count")
            verify_assets(asset_root)
            pixels = []
            for value in images:
                image = ProxyImage.model_validate(value)
                pil = Image.frombytes("RGB", (image.width, image.height), image.rgb_bytes)
                pixels.append(np.asarray(pil.resize((224, 224), Image.Resampling.BILINEAR)))
            with TemporaryDirectory(prefix="amazon-siglip2-") as directory:
                root = Path(directory)
                np.save(root / "images.npy", np.stack(pixels), allow_pickle=False)
                (root / "task.json").write_text(json.dumps({"assets": str(asset_root)}))
                env = {
                    k: v
                    for k, v in os.environ.items()
                    if k in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
                }
                env.update(
                    HF_HUB_OFFLINE="1",
                    TRANSFORMERS_OFFLINE="1",
                    HF_HUB_DISABLE_TELEMETRY="1",
                    HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
                    TOKENIZERS_PARALLELISM="false",
                    OMP_NUM_THREADS="2",
                    MKL_NUM_THREADS="2",
                )
                result = subprocess.run(
                    [str(self._python), "-I", str(_WORKER), str(root)],
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=TIMEOUT_SECONDS,
                    check=False,
                )
                path = root / "embeddings.npy"
                if result.returncode != 0 or not path.is_file() or path.stat().st_size > 128000:
                    raise ValueError("Worker failed")
                output = np.load(path, allow_pickle=False)
                if (
                    output.dtype != np.float32
                    or output.shape != (len(images), 768)
                    or not np.isfinite(output).all()
                ):
                    raise ValueError("Invalid worker output")
                verify_assets(asset_root)
                return tuple(tuple(float(v) for v in row) for row in output)
        except Exception:
            raise ValueError("SigLIP 2 local worker failed") from None
