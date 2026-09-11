from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import src.search_v2.image_similarity_onnx as image_similarity_onnx
from src.search_v2.image_proxy import ProxyImage
from src.search_v2.image_proxy import proxy_image_pixel_sha256
from src.search_v2.image_similarity import CLIP_EMBEDDING_DIMENSION
from src.search_v2.image_similarity import ClipRuntimeError
from src.search_v2.image_similarity import VerifiedClipAssets
from src.search_v2.image_similarity_onnx import CLIP_IMAGE_SIZE
from src.search_v2.image_similarity_onnx import CLIP_ONNX_MODEL_FILENAME
from src.search_v2.image_similarity_onnx import OnnxClipImageEncoder
from src.search_v2.image_similarity_onnx import preprocess_clip_images


MODULE_PATH = Path("src/search_v2/image_similarity_onnx.py")


def proxy_image(
    *,
    width: int = 4,
    height: int = 2,
    color: tuple[int, int, int] = (255, 0, 0),
    source_tag: str = "image",
) -> ProxyImage:
    rgb_bytes = bytes(color) * (width * height)
    return ProxyImage(
        schema_version="2.0",
        source_url_sha256=hashlib.sha256(f"url:{source_tag}".encode()).hexdigest(),
        source_bytes_sha256=hashlib.sha256(f"body:{source_tag}".encode()).hexdigest(),
        pixel_sha256=proxy_image_pixel_sha256(width, height, rgb_bytes),
        content_type="image/png",
        image_format="PNG",
        width=width,
        height=height,
        rgb_bytes=rgb_bytes,
    )


def metadata(
    name: str,
    shape: list[str | int],
    value_type: str,
) -> SimpleNamespace:
    return SimpleNamespace(name=name, shape=shape, type=value_type)


def expected_inputs() -> list[SimpleNamespace]:
    return [
        metadata("input_ids", ["text_batch_size", "sequence_length"], "tensor(int64)"),
        metadata(
            "pixel_values",
            ["image_batch_size", "num_channels", "height", "width"],
            "tensor(float)",
        ),
        metadata("attention_mask", ["text_batch_size", "sequence_length"], "tensor(int64)"),
    ]


def expected_outputs() -> list[SimpleNamespace]:
    return [
        metadata(
            "logits_per_image",
            ["image_batch_size", "text_batch_size"],
            "tensor(float)",
        ),
        metadata(
            "logits_per_text",
            ["text_batch_size", "image_batch_size"],
            "tensor(float)",
        ),
        metadata("text_embeds", ["text_batch_size", 512], "tensor(float)"),
        metadata("image_embeds", ["image_batch_size", 512], "tensor(float)"),
    ]


class RecordingSession:
    def __init__(
        self,
        outputs: np.ndarray,
        *,
        providers: list[str] | None = None,
        inputs: list[SimpleNamespace] | None = None,
        output_metadata: list[SimpleNamespace] | None = None,
        run_error: BaseException | None = None,
    ) -> None:
        self.outputs = outputs
        self.providers = providers or ["CPUExecutionProvider"]
        self.inputs = inputs or expected_inputs()
        self.output_metadata = output_metadata or expected_outputs()
        self.run_error = run_error
        self.run_calls: list[tuple[list[str], dict[str, np.ndarray]]] = []

    def get_providers(self) -> list[str]:
        return self.providers

    def get_inputs(self) -> list[SimpleNamespace]:
        return self.inputs

    def get_outputs(self) -> list[SimpleNamespace]:
        return self.output_metadata

    def run(
        self,
        output_names: list[str],
        feeds: dict[str, np.ndarray],
    ) -> list[np.ndarray]:
        self.run_calls.append((output_names, feeds))
        if self.run_error is not None:
            raise self.run_error
        return [self.outputs]


def install_runtime(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
    session: RecordingSession,
) -> tuple[list[Path], list[tuple[tuple[object, ...], dict[str, object]]]]:
    verification_calls: list[Path] = []
    session_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def verify_assets(asset_root: Path) -> VerifiedClipAssets:
        verification_calls.append(asset_root)
        return VerifiedClipAssets(
            root=asset_root.resolve(),
            manifest_sha256="a" * 64,
            asset_bundle_sha256="a" * 64,
            file_identities=((1, 2, 3),),
        )

    def make_session(*args: object, **kwargs: object) -> RecordingSession:
        session_calls.append((args, kwargs))
        return session

    monkeypatch.setattr(image_similarity_onnx, "verify_clip_asset_directory", verify_assets)
    monkeypatch.setattr(image_similarity_onnx.ort, "InferenceSession", make_session)
    return verification_calls, session_calls


def test_preprocessor_is_fixed_bicubic_contain_mean_pad_nchw_float32() -> None:
    red = proxy_image(color=(255, 0, 0), source_tag="red")
    blue = proxy_image(width=2, height=4, color=(0, 0, 255), source_tag="blue")

    first = preprocess_clip_images((red, blue))
    second = preprocess_clip_images((red, blue))

    assert CLIP_IMAGE_SIZE == 224
    assert image_similarity_onnx.CLIP_RESAMPLE_NAME == "BICUBIC"
    assert image_similarity_onnx._contained_image_size(4, 2) == (224, 112)
    assert image_similarity_onnx._contained_image_size(2, 4) == (112, 224)
    assert first.shape == (2, 3, 224, 224)
    assert first.dtype == np.dtype(np.float32)
    assert first.flags.c_contiguous
    assert np.array_equal(first, second)
    assert first[0, :, 0, 112] == pytest.approx((0.0, 0.0, 0.0), abs=1e-7)
    assert first[0, :, 223, 112] == pytest.approx((0.0, 0.0, 0.0), abs=1e-7)
    assert first[0, :, 112, 112] == pytest.approx(
        (
            (1.0 - 0.48145466) / 0.26862954,
            (0.0 - 0.4578275) / 0.26130258,
            (0.0 - 0.40821073) / 0.27577711,
        )
    )
    assert first[1, :, 112, 0] == pytest.approx((0.0, 0.0, 0.0), abs=1e-7)
    assert first[1, :, 112, 223] == pytest.approx((0.0, 0.0, 0.0), abs=1e-7)
    assert first[1, :, 112, 112] == pytest.approx(
        (
            (0.0 - 0.48145466) / 0.26862954,
            (0.0 - 0.4578275) / 0.26130258,
            (1.0 - 0.40821073) / 0.27577711,
        )
    )


@pytest.mark.parametrize(
    "images",
    [
        None,
        [],
        (),
        tuple(proxy_image(source_tag=str(index)) for index in range(5)),
    ],
)
def test_preprocessor_rejects_invalid_image_sets(images: object) -> None:
    with pytest.raises(ClipRuntimeError, match="^CLIP image preprocessing failed$"):
        preprocess_clip_images(images)  # type: ignore[arg-type]


def test_preprocessor_contains_an_extreme_aspect_ratio_without_unbounded_intermediate() -> None:
    extreme = proxy_image(width=1, height=4096, source_tag="extreme")

    result = preprocess_clip_images((extreme,))

    assert image_similarity_onnx._contained_image_size(1, 4096) == (1, 224)
    assert result.shape == (1, 3, 224, 224)
    assert result[0, :, 112, 0] == pytest.approx((0.0, 0.0, 0.0), abs=1e-7)
    assert result[0, :, 112, 111] != pytest.approx((0.0, 0.0, 0.0), abs=1e-7)


def test_encoder_uses_only_fixed_cpu_session_and_exact_graph_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outputs = np.zeros((2, CLIP_EMBEDDING_DIMENSION), dtype=np.float32)
    outputs[0, 3] = 3.0
    outputs[1, 7] = 4.0
    session = RecordingSession(outputs)
    verification_calls, session_calls = install_runtime(monkeypatch, tmp_path, session)
    images = (
        proxy_image(color=(255, 0, 0), source_tag="first"),
        proxy_image(color=(0, 0, 255), source_tag="second"),
    )

    result = OnnxClipImageEncoder().encode_images(
        images=images,
        asset_root=tmp_path,
        local_files_only=True,
    )

    assert result[0][3] == 3.0
    assert result[1][7] == 4.0
    assert all(type(component) is float for row in result for component in row)
    assert verification_calls == [tmp_path, tmp_path]
    assert len(session_calls) == 1
    args, kwargs = session_calls[0]
    assert args == (str(tmp_path.resolve() / CLIP_ONNX_MODEL_FILENAME),)
    assert kwargs["providers"] == ["CPUExecutionProvider"]
    options = kwargs["sess_options"]
    assert options.intra_op_num_threads == 1
    assert options.inter_op_num_threads == 1
    assert options.execution_mode == image_similarity_onnx.ort.ExecutionMode.ORT_SEQUENTIAL
    assert (
        options.graph_optimization_level
        == image_similarity_onnx.ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    )
    assert session.run_calls[0][0] == ["image_embeds"]
    feeds = session.run_calls[0][1]
    assert set(feeds) == {"attention_mask", "input_ids", "pixel_values"}
    assert feeds["pixel_values"].shape == (2, 3, 224, 224)
    assert feeds["pixel_values"].dtype == np.dtype(np.float32)
    assert np.array_equal(feeds["input_ids"], np.array([[0]], dtype=np.int64))
    assert np.array_equal(feeds["attention_mask"], np.array([[1]], dtype=np.int64))


@pytest.mark.parametrize(
    ("providers", "inputs", "outputs"),
    [
        (["CPUExecutionProvider", "AzureExecutionProvider"], None, None),
        (["AzureExecutionProvider"], None, None),
        (None, [metadata("pixel_values", [1, 3, 224, 224], "tensor(float)")], None),
        (None, None, [metadata("image_embeds", ["image_batch_size", 256], "tensor(float)")]),
    ],
)
def test_encoder_rejects_provider_or_graph_contract_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    providers: list[str] | None,
    inputs: list[SimpleNamespace] | None,
    outputs: list[SimpleNamespace] | None,
) -> None:
    session = RecordingSession(
        np.ones((1, 512), dtype=np.float32),
        providers=providers,
        inputs=inputs,
        output_metadata=outputs,
    )
    install_runtime(monkeypatch, tmp_path, session)

    with pytest.raises(ClipRuntimeError, match="^CLIP ONNX encoder failed$"):
        OnnxClipImageEncoder().encode_images(
            images=(proxy_image(),),
            asset_root=tmp_path,
            local_files_only=True,
        )


@pytest.mark.parametrize(
    "output",
    [
        np.ones((1, 511), dtype=np.float32),
        np.ones((2, 512), dtype=np.float32),
        np.ones((1, 512), dtype=np.float64),
        np.full((1, 512), np.nan, dtype=np.float32),
        np.zeros((1, 512), dtype=np.float32),
    ],
)
def test_encoder_rejects_invalid_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    output: np.ndarray,
) -> None:
    install_runtime(monkeypatch, tmp_path, RecordingSession(output))

    with pytest.raises(ClipRuntimeError, match="^CLIP ONNX encoder failed$"):
        OnnxClipImageEncoder().encode_images(
            images=(proxy_image(),),
            asset_root=tmp_path,
            local_files_only=True,
        )


def test_encoder_fails_closed_without_leaking_runtime_details(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sensitive = f"failed to load {tmp_path}/secret-model.onnx"
    session = RecordingSession(
        np.ones((1, 512), dtype=np.float32),
        run_error=RuntimeError(sensitive),
    )
    verification_calls, _ = install_runtime(monkeypatch, tmp_path, session)

    with pytest.raises(ClipRuntimeError, match="^CLIP ONNX encoder failed$") as error:
        OnnxClipImageEncoder().encode_images(
            images=(proxy_image(),),
            asset_root=tmp_path,
            local_files_only=True,
        )

    assert sensitive not in str(error.value)
    assert str(tmp_path) not in str(error.value)
    assert verification_calls == [tmp_path]


def test_encoder_rejects_asset_identity_change_during_inference(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    session = RecordingSession(np.ones((1, 512), dtype=np.float32))
    verification_calls, _ = install_runtime(monkeypatch, tmp_path, session)

    def changed_verification(asset_root: Path) -> VerifiedClipAssets:
        verification_calls.append(asset_root)
        sequence = len(verification_calls)
        return VerifiedClipAssets(
            root=asset_root.resolve(),
            manifest_sha256="a" * 64,
            asset_bundle_sha256="a" * 64,
            file_identities=((sequence, 2, 3),),
        )

    monkeypatch.setattr(
        image_similarity_onnx,
        "verify_clip_asset_directory",
        changed_verification,
    )

    with pytest.raises(ClipRuntimeError, match="^CLIP ONNX encoder failed$"):
        OnnxClipImageEncoder().encode_images(
            images=(proxy_image(),),
            asset_root=tmp_path,
            local_files_only=True,
        )

    assert verification_calls == [tmp_path, tmp_path]


@pytest.mark.parametrize("local_only", [False, 1, None])
def test_encoder_rejects_nonliteral_local_only_before_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    local_only: object,
) -> None:
    calls: list[Path] = []

    def unexpected_verify(root: Path) -> object:
        calls.append(root)
        raise AssertionError("must not verify")

    monkeypatch.setattr(image_similarity_onnx, "verify_clip_asset_directory", unexpected_verify)

    with pytest.raises(ClipRuntimeError, match="^CLIP ONNX encoder failed$"):
        OnnxClipImageEncoder().encode_images(
            images=(proxy_image(),),
            asset_root=tmp_path,
            local_files_only=local_only,  # type: ignore[arg-type]
        )

    assert calls == []


def test_onnx_module_has_no_network_or_pickle_model_runtime_import() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)

    forbidden = (
        "huggingface_hub",
        "httpx",
        "pickle",
        "requests",
        "socket",
        "torch",
        "transformers",
    )
    assert not any(
        name == prefix or name.startswith(f"{prefix}.") for name in imports for prefix in forbidden
    )
