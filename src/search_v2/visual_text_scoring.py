"""Independent SigLIP text/image evidence; generated images never enter this score."""

import hashlib
import json
import math
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from typing import Annotated, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.search_v2 import siglip2
from src.search_v2.counterfactual_image import VisualConditionSet, visual_condition_set_sha256
from src.search_v2.relative_image_ranking import Siglip2AppearanceImageBatch

PROFILE = "siglip2-visual-text-v1"
SORT_PROFILE = "excluded-title-conditions-text-image-review-v2"
RANKING_PROFILE = "candidate-siglip2-dual-v2"
_WORKER = Path(__file__).with_name("siglip2_text_worker.py")
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Unit = Annotated[float, Field(ge=0.0, le=1.0)]


def runtime_sha256():
    return hashlib.sha256(
        b"siglip2-text-v1:lowercase:pad64:reject-truncation:fp32:cpu2\x00"
        + _WORKER.read_bytes()
        + Path(__file__).read_bytes()
        + siglip2.runtime_sha256().encode()
    ).hexdigest()


def condition_texts(conditions):
    conditions = VisualConditionSet.model_validate(conditions)
    result = []
    for condition in conditions.conditions:
        if condition.contrast is None:
            raise ValueError("Visual text scoring requires confirmed descriptions")
        text = (
            condition.contrast.opposite
            if condition.strength == "excluded"
            else condition.contrast.matching
        )
        result.append(f"this is a photo of {text.rstrip('.').lower()}.")
    return tuple(result)


class _Frozen(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", revalidate_instances="always", allow_inf_nan=False
    )


class VisualTextConditionScore(_Frozen):
    condition_id: str = Field(pattern=r"^visual-condition-[0-9]{3}$")
    text_sha256: Digest
    score: Unit


class VisualTextComponent(_Frozen):
    normalized_product_sha256: Digest
    candidate_image_pixel_sha256: Digest | None
    conditions: tuple[VisualTextConditionScore, ...] = Field(max_length=3)
    score: Unit | None

    @model_validator(mode="after")
    def validate_score(self):
        if self.candidate_image_pixel_sha256 is None:
            if self.conditions or self.score is not None:
                raise ValueError("Missing image cannot have visual text evidence")
        elif not self.conditions or self.score != min(c.score for c in self.conditions):
            raise ValueError("Visual text score does not match condition evidence")
        return self


class VisualTextBatch(_Frozen):
    profile_id: Literal["siglip2-visual-text-v1"] = PROFILE
    condition_set_sha256: Digest
    runtime_sha256: Digest
    candidates: tuple[VisualTextComponent, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_products(self):
        keys = [c.normalized_product_sha256 for c in self.candidates]
        if len(keys) != len(set(keys)) or self.runtime_sha256 != runtime_sha256():
            raise ValueError("Visual text batch binding is invalid")
        return self


class Siglip2DualImageBatch(Siglip2AppearanceImageBatch):
    text_batch: VisualTextBatch

    @model_validator(mode="after")
    def validate_text_binding(self):
        if self.text_batch.condition_set_sha256 != self.condition_set_sha256:
            raise ValueError("Visual text conditions changed")
        texts = {c.normalized_product_sha256: c for c in self.text_batch.candidates}
        if set(texts) != {c.normalized_product_sha256 for c in self.candidates}:
            raise ValueError("Visual text products changed")
        for image in self.candidates:
            text = texts[image.normalized_product_sha256]
            if text.candidate_image_pixel_sha256 != image.source.candidate_image_pixel_sha256:
                raise ValueError("Visual text image changed")
        return self


def score_visual_text(conditions, fetched, embeddings, *, asset_root, encoder):
    texts = condition_texts(conditions)
    try:
        siglip2.verify_assets(asset_root)
        runtime = runtime_sha256()
        available = {
            e.image_pixel_sha256: siglip2.Siglip2Embedding.model_validate(e) for e in embeddings
        }
        rows = encoder.encode_texts(texts=texts, asset_root=asset_root) if available else ()
        if available and (type(rows) is not tuple or len(rows) != len(texts)):
            raise ValueError("Invalid text embedding count")
        vectors = []
        for row in rows:
            if (
                type(row) is not tuple
                or len(row) != 768
                or any(type(x) is not float or not math.isfinite(x) for x in row)
            ):
                raise ValueError("Invalid text embedding")
            norm = math.sqrt(math.fsum(x * x for x in row))
            if not math.isfinite(norm) or norm <= 0:
                raise ValueError("Zero text embedding")
            vectors.append(tuple(x / norm for x in row))
        result = []
        for key, image in fetched:
            scores = []
            if image is not None:
                embedding = available[image.pixel_sha256]
                if embedding.runtime_sha256 != siglip2.runtime_sha256():
                    raise ValueError("Image runtime mismatch")
                for condition, text, vector in zip(
                    conditions.conditions, texts, vectors, strict=True
                ):
                    cosine = math.fsum(a * b for a, b in zip(vector, embedding.values, strict=True))
                    scores.append(
                        VisualTextConditionScore(
                            condition_id=condition.condition_id,
                            text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                            score=max(0.0, min(1.0, (cosine + 1.0) / 2.0)),
                        )
                    )
            result.append(
                VisualTextComponent(
                    normalized_product_sha256=key,
                    candidate_image_pixel_sha256=image.pixel_sha256 if image else None,
                    conditions=tuple(scores),
                    score=min(s.score for s in scores) if scores else None,
                )
            )
        siglip2.verify_assets(asset_root)
        if runtime != runtime_sha256():
            raise ValueError("Text runtime changed")
        return VisualTextBatch(
            condition_set_sha256=visual_condition_set_sha256(conditions),
            runtime_sha256=runtime,
            candidates=tuple(result),
        )
    except Exception:
        raise ValueError("SigLIP 2 visual text scoring failed") from None


class LocalSiglip2MultimodalEncoder(siglip2.LocalSiglip2ImageEncoder):
    def encode_texts(self, *, texts, asset_root):
        try:
            if (
                type(texts) is not tuple
                or not 1 <= len(texts) <= 3
                or any(type(t) is not str or not 1 <= len(t) <= 300 for t in texts)
            ):
                raise ValueError("Invalid text count or size")
            siglip2.verify_assets(asset_root)
            with TemporaryDirectory(prefix="amazon-siglip2-text-") as directory:
                root = Path(directory)
                (root / "task.json").write_text(
                    json.dumps({"assets": str(asset_root), "texts": texts})
                )
                env = {
                    "HF_HUB_OFFLINE": "1",
                    "TRANSFORMERS_OFFLINE": "1",
                    "HF_HUB_DISABLE_TELEMETRY": "1",
                    "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
                    "TOKENIZERS_PARALLELISM": "false",
                    "OMP_NUM_THREADS": "2",
                    "MKL_NUM_THREADS": "2",
                }
                result = subprocess.run(
                    [str(self._python), "-I", str(_WORKER), str(root)],
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=600,
                    check=False,
                )
                path = root / "text.npy"
                if result.returncode != 0 or not path.is_file() or path.stat().st_size > 10000:
                    raise ValueError("Worker failed")
                values = np.load(path, allow_pickle=False)
                if (
                    values.dtype != np.float32
                    or values.shape != (len(texts), 768)
                    or not np.isfinite(values).all()
                ):
                    raise ValueError("Invalid worker output")
                siglip2.verify_assets(asset_root)
                return tuple(tuple(float(v) for v in row) for row in values)
        except Exception:
            raise ValueError("SigLIP 2 text worker failed") from None
