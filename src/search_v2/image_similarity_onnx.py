from __future__ import annotations

import math
from pathlib import Path
from typing import Literal

import numpy as np
import onnxruntime as ort
from PIL import Image

from src.search_v2.image_proxy import ProxyImage
from src.search_v2.image_similarity import CLIP_EMBEDDING_DIMENSION
from src.search_v2.image_similarity import CLIP_MAX_IMAGES_PER_SET
from src.search_v2.image_similarity import ClipRuntimeError
from src.search_v2.image_similarity import verify_clip_asset_directory


CLIP_IMAGE_SIZE = 224
CLIP_RESAMPLE_NAME = "BICUBIC"
CLIP_ONNX_MODEL_FILENAME = "model.onnx"
CLIP_PIXEL_VALUES_BYTES_PER_IMAGE = 3 * CLIP_IMAGE_SIZE * CLIP_IMAGE_SIZE * 4

_IMAGE_MEAN = np.asarray((0.48145466, 0.4578275, 0.40821073), dtype=np.float32)
_IMAGE_STANDARD_DEVIATION = np.asarray(
    (0.26862954, 0.26130258, 0.27577711),
    dtype=np.float32,
)
_EXPECTED_INPUTS = (
    (
        "input_ids",
        ("text_batch_size", "sequence_length"),
        "tensor(int64)",
    ),
    (
        "pixel_values",
        ("image_batch_size", "num_channels", "height", "width"),
        "tensor(float)",
    ),
    (
        "attention_mask",
        ("text_batch_size", "sequence_length"),
        "tensor(int64)",
    ),
)
_EXPECTED_OUTPUTS = (
    (
        "logits_per_image",
        ("image_batch_size", "text_batch_size"),
        "tensor(float)",
    ),
    (
        "logits_per_text",
        ("text_batch_size", "image_batch_size"),
        "tensor(float)",
    ),
    (
        "text_embeds",
        ("text_batch_size", CLIP_EMBEDDING_DIMENSION),
        "tensor(float)",
    ),
    (
        "image_embeds",
        ("image_batch_size", CLIP_EMBEDDING_DIMENSION),
        "tensor(float)",
    ),
)


def _raise_preprocessing_failed() -> None:
    raise ClipRuntimeError("CLIP image preprocessing failed") from None


def _raise_onnx_failed() -> None:
    raise ClipRuntimeError("CLIP ONNX encoder failed") from None


def _contained_image_size(width: int, height: int) -> tuple[int, int]:
    if type(width) is not int or type(height) is not int or width < 1 or height < 1:
        _raise_preprocessing_failed()
    scale = CLIP_IMAGE_SIZE / max(width, height)
    return (
        max(1, round(width * scale)),
        max(1, round(height * scale)),
    )


def preprocess_clip_images(images: tuple[ProxyImage, ...]) -> np.ndarray:
    """Build the fixed CLIP NCHW float32 image tensor without I/O."""

    if type(images) is not tuple or not 1 <= len(images) <= CLIP_MAX_IMAGES_PER_SET:
        _raise_preprocessing_failed()
    prepared: list[np.ndarray] = []
    try:
        for supplied_image in images:
            image = ProxyImage.model_validate(supplied_image)
            source = Image.frombytes(
                "RGB",
                (image.width, image.height),
                image.rgb_bytes,
            )
            resized = source.resize(
                _contained_image_size(image.width, image.height),
                resample=Image.Resampling.BICUBIC,
            )
            resized_pixels = np.asarray(resized, dtype=np.float32)
            resized_pixels = resized_pixels * np.float32(1.0 / 255.0)
            pixels = np.empty((CLIP_IMAGE_SIZE, CLIP_IMAGE_SIZE, 3), dtype=np.float32)
            pixels[:] = _IMAGE_MEAN
            left = (CLIP_IMAGE_SIZE - resized.width) // 2
            top = (CLIP_IMAGE_SIZE - resized.height) // 2
            pixels[top : top + resized.height, left : left + resized.width] = resized_pixels
            pixels = (pixels - _IMAGE_MEAN) / _IMAGE_STANDARD_DEVIATION
            prepared.append(np.ascontiguousarray(pixels.transpose(2, 0, 1)))
    except ClipRuntimeError:
        raise
    except Exception:
        _raise_preprocessing_failed()
    try:
        batch = np.ascontiguousarray(np.stack(prepared), dtype=np.float32)
    except Exception:
        _raise_preprocessing_failed()
    expected_shape = (len(images), 3, CLIP_IMAGE_SIZE, CLIP_IMAGE_SIZE)
    if (
        type(batch) is not np.ndarray
        or batch.shape != expected_shape
        or batch.dtype != np.dtype(np.float32)
        or not batch.flags.c_contiguous
        or batch.nbytes != len(images) * CLIP_PIXEL_VALUES_BYTES_PER_IMAGE
        or not bool(np.isfinite(batch).all())
    ):
        _raise_preprocessing_failed()
    return batch


def _session_metadata(items: object) -> tuple[tuple[str, tuple[object, ...], str], ...]:
    if type(items) is not list:
        _raise_onnx_failed()
    result: list[tuple[str, tuple[object, ...], str]] = []
    try:
        for item in items:
            name = item.name
            shape = tuple(item.shape)
            value_type = item.type
            if type(name) is not str or type(value_type) is not str:
                _raise_onnx_failed()
            result.append((name, shape, value_type))
    except ClipRuntimeError:
        raise
    except Exception:
        _raise_onnx_failed()
    return tuple(result)


def _new_session_options() -> ort.SessionOptions:
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return options


def _run_image_embeddings(
    *,
    pixel_values: np.ndarray,
    asset_root: Path,
) -> tuple[tuple[float, ...], ...]:
    if (
        type(pixel_values) is not np.ndarray
        or pixel_values.ndim != 4
        or not 1 <= pixel_values.shape[0] <= CLIP_MAX_IMAGES_PER_SET
        or pixel_values.shape[1:] != (3, CLIP_IMAGE_SIZE, CLIP_IMAGE_SIZE)
        or pixel_values.dtype != np.dtype(np.float32)
        or not pixel_values.flags.c_contiguous
        or not bool(np.isfinite(pixel_values).all())
    ):
        _raise_onnx_failed()
    verified_before = verify_clip_asset_directory(asset_root)
    session = ort.InferenceSession(
        str(verified_before.root / CLIP_ONNX_MODEL_FILENAME),
        sess_options=_new_session_options(),
        providers=["CPUExecutionProvider"],
    )
    if session.get_providers() != ["CPUExecutionProvider"]:
        _raise_onnx_failed()
    if _session_metadata(session.get_inputs()) != _EXPECTED_INPUTS:
        _raise_onnx_failed()
    if _session_metadata(session.get_outputs()) != _EXPECTED_OUTPUTS:
        _raise_onnx_failed()

    raw_outputs = session.run(
        ["image_embeds"],
        {
            "input_ids": np.zeros((1, 1), dtype=np.int64),
            "pixel_values": pixel_values,
            "attention_mask": np.ones((1, 1), dtype=np.int64),
        },
    )
    expected_shape = (pixel_values.shape[0], CLIP_EMBEDDING_DIMENSION)
    if type(raw_outputs) is not list or len(raw_outputs) != 1:
        _raise_onnx_failed()
    raw_embeddings = raw_outputs[0]
    if (
        type(raw_embeddings) is not np.ndarray
        or raw_embeddings.shape != expected_shape
        or raw_embeddings.dtype != np.dtype(np.float32)
        or not bool(np.isfinite(raw_embeddings).all())
    ):
        _raise_onnx_failed()
    norms = np.sqrt(np.sum(raw_embeddings * raw_embeddings, axis=1, dtype=np.float64))
    if not bool(np.isfinite(norms).all()) or bool(np.any(norms <= 0.0)):
        _raise_onnx_failed()
    verified_after = verify_clip_asset_directory(asset_root)
    if verified_after != verified_before:
        _raise_onnx_failed()
    return tuple(tuple(float(component) for component in row) for row in raw_embeddings)


class OnnxClipImageEncoder:
    """Run the exact pinned ONNX graph on its CPU execution provider."""

    __slots__ = ()

    def encode_images(
        self,
        *,
        images: tuple[ProxyImage, ...],
        asset_root: Path,
        local_files_only: Literal[True],
    ) -> tuple[tuple[float, ...], ...]:
        if local_files_only is not True:
            _raise_onnx_failed()
        try:
            pixel_values = preprocess_clip_images(images)
            return _run_image_embeddings(
                pixel_values=pixel_values,
                asset_root=Path(asset_root),
            )
        except Exception:
            _raise_onnx_failed()


def encode_preprocessed_clip_images(
    *,
    pixel_values: np.ndarray,
    asset_root: Path,
) -> tuple[tuple[float, ...], ...]:
    """Run a parent-preprocessed bounded tensor for the process adapter."""

    try:
        return _run_image_embeddings(
            pixel_values=pixel_values,
            asset_root=Path(asset_root),
        )
    except Exception:
        _raise_onnx_failed()


def validate_embedding_rows(rows: tuple[tuple[float, ...], ...]) -> None:
    """Validate rows before the process child serializes them."""

    if type(rows) is not tuple or not 1 <= len(rows) <= CLIP_MAX_IMAGES_PER_SET:
        _raise_onnx_failed()
    for row in rows:
        if (
            type(row) is not tuple
            or len(row) != CLIP_EMBEDDING_DIMENSION
            or any(type(component) is not float for component in row)
            or not all(math.isfinite(component) for component in row)
            or math.fsum(component * component for component in row) <= 0.0
        ):
            _raise_onnx_failed()
