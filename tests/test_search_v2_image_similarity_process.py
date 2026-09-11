from __future__ import annotations

import ast
import hashlib
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

import src.search_v2.image_similarity_process as image_similarity_process
from src.search_v2.image_proxy import ProxyImage
from src.search_v2.image_proxy import proxy_image_pixel_sha256
from src.search_v2.image_similarity import CLIP_EMBEDDING_DIMENSION
from src.search_v2.image_similarity import ClipRuntimeError
from src.search_v2.image_similarity import VerifiedClipAssets
from src.search_v2.image_similarity import run_pinned_clip_image_encoder
from src.search_v2.image_similarity import score_clip_image_similarity
from src.search_v2.image_similarity_onnx import CLIP_IMAGE_SIZE
from src.search_v2.image_similarity_onnx import CLIP_PIXEL_VALUES_BYTES_PER_IMAGE
from src.search_v2.image_similarity_process import CLIP_PROCESS_MAX_MESSAGE_BYTES
from src.search_v2.image_similarity_process import CLIP_PROCESS_TIMEOUT_SECONDS
from src.search_v2.image_similarity_process import ProcessIsolatedClipImageEncoder


MODULE_PATH = Path("src/search_v2/image_similarity_process.py")
REPOSITORY_MODEL_ROOT = (
    Path(__file__).resolve().parents[1] / "models" / "clip-vit-base-patch32-12b36594"
)
QUALITY_IMAGE_ROOT = Path(__file__).resolve().parent / "img" / "case1"
QUALITY_POSITIVE_IMAGE = QUALITY_IMAGE_ROOT / "near" / "n1.png"
QUALITY_NEGATIVE_IMAGE = QUALITY_IMAGE_ROOT / "far" / "f1.png"
QUALITY_POSITIVE_SHA256 = "ceb34d094f67747668ae3a07080550262ebf86612cf736b794db2849d6c2e080"
QUALITY_NEGATIVE_SHA256 = "ee58436ca6ee05a006768ab809b34e314a03d0cf0184df813d74ff5426ee3733"
_UNSET = object()


def proxy_image(*, source_tag: str = "image") -> ProxyImage:
    width = 8
    height = 8
    rgb_bytes = b"".join(
        bytes((x * 31, y * 31, (x + y) * 15)) for y in range(height) for x in range(width)
    )
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


def quality_proxy_image(
    *,
    path: Path,
    source_tag: str,
    expected_sha256: str,
) -> ProxyImage:
    assert path.is_file() and not path.is_symlink()
    source_bytes = path.read_bytes()
    assert hashlib.sha256(source_bytes).hexdigest() == expected_sha256
    with Image.open(BytesIO(source_bytes)) as decoded:
        assert decoded.format == "PNG"
        assert getattr(decoded, "n_frames", 1) == 1
        width, height = decoded.size
        rgb_bytes = decoded.convert("RGB").tobytes()
    return ProxyImage(
        schema_version="2.0",
        source_url_sha256=hashlib.sha256(f"quality:{source_tag}".encode()).hexdigest(),
        source_bytes_sha256=expected_sha256,
        pixel_sha256=proxy_image_pixel_sha256(width, height, rgb_bytes),
        content_type="image/png",
        image_format="PNG",
        width=width,
        height=height,
        rgb_bytes=rgb_bytes,
    )


def embedding_rows(count: int) -> tuple[tuple[float, ...], ...]:
    rows: list[tuple[float, ...]] = []
    for index in range(count):
        row = [0.0] * CLIP_EMBEDDING_DIMENSION
        row[index] = float(index + 1)
        rows.append(tuple(row))
    return tuple(rows)


class BytesSubclass(bytes):
    pass


class RecordingEndpoint:
    def __init__(
        self,
        *,
        message: object = _UNSET,
        poll_result: bool = True,
        poll_error: BaseException | None = None,
        recv_error: BaseException | None = None,
        send_error: BaseException | None = None,
        close_error: BaseException | None = None,
    ) -> None:
        self.message = message
        self.poll_result = poll_result
        self.poll_error = poll_error
        self.recv_error = recv_error
        self.send_error = send_error
        self.close_error = close_error
        self.poll_calls: list[float] = []
        self.recv_calls: list[int] = []
        self.sent: list[bytes] = []
        self.close_calls = 0

    def poll(self, timeout: float) -> bool:
        self.poll_calls.append(timeout)
        if self.poll_error is not None:
            raise self.poll_error
        return self.poll_result

    def recv_bytes(self, maxlength: int) -> object:
        self.recv_calls.append(maxlength)
        if self.recv_error is not None:
            raise self.recv_error
        if self.message is _UNSET:
            raise EOFError
        return self.message

    def send_bytes(self, message: bytes) -> None:
        if self.send_error is not None:
            raise self.send_error
        self.sent.append(message)

    def close(self) -> None:
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error


class RecordingProcess:
    def __init__(
        self,
        *,
        alive_after_start: bool = False,
        exitcode: object = 0,
        start_error: BaseException | None = None,
        terminate_stops: bool = True,
        kill_stops: bool = True,
        close_error: BaseException | None = None,
    ) -> None:
        self.alive_after_start = alive_after_start
        self._alive = False
        self._exitcode = exitcode
        self.start_error = start_error
        self.terminate_stops = terminate_stops
        self.kill_stops = kill_stops
        self.close_error = close_error
        self.start_calls = 0
        self.join_calls: list[float] = []
        self.is_alive_calls = 0
        self.terminate_calls = 0
        self.kill_calls = 0
        self.close_calls = 0

    def start(self) -> None:
        self.start_calls += 1
        if self.start_error is not None:
            raise self.start_error
        self._alive = self.alive_after_start

    def join(self, timeout: float) -> None:
        self.join_calls.append(timeout)

    def is_alive(self) -> bool:
        self.is_alive_calls += 1
        return self._alive

    def terminate(self) -> None:
        self.terminate_calls += 1
        if self.terminate_stops:
            self._alive = False

    def kill(self) -> None:
        self.kill_calls += 1
        if self.kill_stops:
            self._alive = False

    def close(self) -> None:
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error

    @property
    def exitcode(self) -> object:
        return self._exitcode


class RecordingContext:
    def __init__(
        self,
        receiver: RecordingEndpoint,
        sender: RecordingEndpoint,
        process: RecordingProcess,
    ) -> None:
        self.receiver = receiver
        self.sender = sender
        self.process = process
        self.pipe_calls: list[bool] = []
        self.process_calls: list[dict[str, object]] = []

    def Pipe(self, *, duplex: bool) -> tuple[RecordingEndpoint, RecordingEndpoint]:
        self.pipe_calls.append(duplex)
        return self.receiver, self.sender

    def Process(self, **kwargs: object) -> RecordingProcess:
        self.process_calls.append(kwargs)
        return self.process


class RecordingClock:
    def __init__(self, values: tuple[float, ...]) -> None:
        self.values = values
        self.calls = 0

    def __call__(self) -> float:
        index = min(self.calls, len(self.values) - 1)
        self.calls += 1
        return self.values[index]


def install_context(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
    *,
    message: object = _UNSET,
    poll_result: bool = True,
    poll_error: BaseException | None = None,
    recv_error: BaseException | None = None,
    receiver_close_error: BaseException | None = None,
    sender_close_error: BaseException | None = None,
    process: RecordingProcess | None = None,
    clock_values: tuple[float, ...] = (100.0, 100.25, 100.5, 100.75),
    image_count: int = 1,
) -> tuple[RecordingContext, RecordingEndpoint, RecordingEndpoint, RecordingProcess, list[str]]:
    if message is _UNSET:
        message = image_similarity_process._success_message(embedding_rows(image_count))
    receiver = RecordingEndpoint(
        message=message,
        poll_result=poll_result,
        poll_error=poll_error,
        recv_error=recv_error,
        close_error=receiver_close_error,
    )
    sender = RecordingEndpoint(close_error=sender_close_error)
    configured_process = process if process is not None else RecordingProcess()
    context = RecordingContext(receiver, sender, configured_process)
    context_names: list[str] = []

    def get_context(name: str) -> RecordingContext:
        context_names.append(name)
        return context

    def verify_assets(asset_root: Path) -> VerifiedClipAssets:
        return VerifiedClipAssets(
            root=asset_root.resolve(),
            manifest_sha256="a" * 64,
            asset_bundle_sha256="a" * 64,
            file_identities=((1, 2, 3),),
        )

    pixel_values = np.zeros(
        (image_count, 3, CLIP_IMAGE_SIZE, CLIP_IMAGE_SIZE),
        dtype=np.float32,
    )
    monkeypatch.setattr(image_similarity_process.multiprocessing, "get_context", get_context)
    monkeypatch.setattr(image_similarity_process, "verify_clip_asset_directory", verify_assets)
    monkeypatch.setattr(
        image_similarity_process,
        "preprocess_clip_images",
        lambda images: pixel_values,
    )
    monkeypatch.setattr(
        image_similarity_process,
        "_monotonic",
        RecordingClock(clock_values),
    )
    return context, receiver, sender, configured_process, context_names


def encode_with_fake_context(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
    **kwargs: Any,
) -> tuple[tuple[float, ...], ...]:
    install_context(monkeypatch, root, **kwargs)
    return ProcessIsolatedClipImageEncoder().encode_images(
        images=(proxy_image(),),
        asset_root=root,
        local_files_only=True,
    )


def test_public_contract_is_fixed_and_constructor_is_lazy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_context(name: str) -> object:
        raise AssertionError(name)

    monkeypatch.setattr(image_similarity_process.multiprocessing, "get_context", unexpected_context)

    encoder = ProcessIsolatedClipImageEncoder()

    assert CLIP_PROCESS_TIMEOUT_SECONDS == 30.0
    assert CLIP_PROCESS_MAX_MESSAGE_BYTES == 8201
    assert repr(encoder) == (
        "<src.search_v2.image_similarity_process.ProcessIsolatedClipImageEncoder object>"
    )


def test_uses_one_spawn_process_with_bounded_parent_preprocessed_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context, receiver, sender, process, context_names = install_context(
        monkeypatch,
        tmp_path,
    )

    result = ProcessIsolatedClipImageEncoder().encode_images(
        images=(proxy_image(),),
        asset_root=tmp_path,
        local_files_only=True,
    )

    assert result == embedding_rows(1)
    assert context_names == ["spawn"]
    assert context.pipe_calls == [False]
    assert len(context.process_calls) == 1
    process_call = context.process_calls[0]
    assert process_call["target"] is image_similarity_process._encode_clip_images_in_child
    args = process_call["args"]
    assert args[0] is sender
    assert args[1] == str(tmp_path.resolve())
    assert args[2] == 1
    assert type(args[3]) is bytes
    assert len(args[3]) == CLIP_PIXEL_VALUES_BYTES_PER_IMAGE
    assert process_call["daemon"] is True
    assert process.start_calls == 1
    assert receiver.recv_calls == [CLIP_PROCESS_MAX_MESSAGE_BYTES]
    assert len(receiver.poll_calls) == 1
    assert 0 < receiver.poll_calls[0] < CLIP_PROCESS_TIMEOUT_SECONDS
    assert process.join_calls
    assert process.terminate_calls == 0
    assert process.kill_calls == 0
    assert process.close_calls == 1
    assert receiver.close_calls == 1
    assert sender.close_calls >= 1


def test_deadline_reserves_cleanup_time(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, receiver, _, process, _ = install_context(
        monkeypatch,
        tmp_path,
        clock_values=(10.0, 11.0, 12.0, 13.0),
    )

    ProcessIsolatedClipImageEncoder().encode_images(
        images=(proxy_image(),),
        asset_root=tmp_path,
        local_files_only=True,
    )

    assert receiver.poll_calls == [27.0]
    assert process.join_calls[0] == 26.0


@pytest.mark.parametrize("local_only", [False, 1, None])
def test_rejects_nonliteral_local_only_before_process_creation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    local_only: object,
) -> None:
    context_calls: list[str] = []

    def get_context(name: str) -> object:
        context_calls.append(name)
        raise AssertionError("must not create process")

    monkeypatch.setattr(image_similarity_process.multiprocessing, "get_context", get_context)

    with pytest.raises(ClipRuntimeError, match="^CLIP process encoder failed$"):
        ProcessIsolatedClipImageEncoder().encode_images(
            images=(proxy_image(),),
            asset_root=tmp_path,
            local_files_only=local_only,  # type: ignore[arg-type]
        )

    assert context_calls == []


@pytest.mark.parametrize(
    "message",
    [
        None,
        [],
        b"",
        b"error",
        b"unknown",
        BytesSubclass(b"error"),
        b"CLIPV1\x00\x00\x01",
        b"x" * (CLIP_PROCESS_MAX_MESSAGE_BYTES + 1),
    ],
)
def test_rejects_malformed_ipc_messages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    message: object,
) -> None:
    install_context(monkeypatch, tmp_path, message=message)

    with pytest.raises(ClipRuntimeError, match="^CLIP process encoder failed$"):
        ProcessIsolatedClipImageEncoder().encode_images(
            images=(proxy_image(),),
            asset_root=tmp_path,
            local_files_only=True,
        )


@pytest.mark.parametrize("component", [float("nan"), float("inf"), 0.0])
def test_rejects_nonfinite_or_zero_ipc_embedding(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    component: float,
) -> None:
    row = np.zeros((1, CLIP_EMBEDDING_DIMENSION), dtype="<f4")
    row[0, 0] = component
    message = (
        image_similarity_process._SUCCESS_HEADER.pack(
            image_similarity_process._SUCCESS_MAGIC,
            1,
        )
        + row.tobytes()
    )
    install_context(monkeypatch, tmp_path, message=message)

    with pytest.raises(ClipRuntimeError, match="^CLIP process encoder failed$"):
        ProcessIsolatedClipImageEncoder().encode_images(
            images=(proxy_image(),),
            asset_root=tmp_path,
            local_files_only=True,
        )


def test_timeout_terminates_child_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    process = RecordingProcess(alive_after_start=True)
    context, receiver, _, _, context_names = install_context(
        monkeypatch,
        tmp_path,
        poll_result=False,
        process=process,
    )

    with pytest.raises(ClipRuntimeError, match="^CLIP process encoder failed$"):
        ProcessIsolatedClipImageEncoder().encode_images(
            images=(proxy_image(),),
            asset_root=tmp_path,
            local_files_only=True,
        )

    assert context_names == ["spawn"]
    assert len(context.process_calls) == 1
    assert receiver.recv_calls == []
    assert process.terminate_calls == 1
    assert process.kill_calls == 0
    assert process.close_calls == 1


def test_kills_child_when_terminate_does_not_stop_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    process = RecordingProcess(
        alive_after_start=True,
        terminate_stops=False,
        kill_stops=True,
    )
    install_context(
        monkeypatch,
        tmp_path,
        poll_result=False,
        process=process,
    )

    with pytest.raises(ClipRuntimeError, match="^CLIP process encoder failed$"):
        ProcessIsolatedClipImageEncoder().encode_images(
            images=(proxy_image(),),
            asset_root=tmp_path,
            local_files_only=True,
        )

    assert process.terminate_calls == 1
    assert process.kill_calls == 1
    assert process.close_calls == 1


def test_keyboard_interrupt_is_reraised_after_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    process = RecordingProcess(alive_after_start=True)
    _, _, _, _, _ = install_context(
        monkeypatch,
        tmp_path,
        poll_error=KeyboardInterrupt(),
        process=process,
    )

    with pytest.raises(KeyboardInterrupt):
        ProcessIsolatedClipImageEncoder().encode_images(
            images=(proxy_image(),),
            asset_root=tmp_path,
            local_files_only=True,
        )

    assert process.terminate_calls == 1
    assert process.close_calls == 1


def test_child_reconstructs_fixed_tensor_and_sends_only_embedding_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sender = RecordingEndpoint()
    pixel_values = np.arange(
        CLIP_PIXEL_VALUES_BYTES_PER_IMAGE // 4,
        dtype="<f4",
    ).reshape(1, 3, CLIP_IMAGE_SIZE, CLIP_IMAGE_SIZE)
    calls: list[tuple[np.ndarray, Path]] = []

    def encode(*, pixel_values: np.ndarray, asset_root: Path):
        calls.append((pixel_values, asset_root))
        return embedding_rows(1)

    monkeypatch.setattr(image_similarity_process, "encode_preprocessed_clip_images", encode)

    image_similarity_process._encode_clip_images_in_child(
        sender,
        str(tmp_path.resolve()),
        1,
        pixel_values.tobytes(),
    )

    assert len(calls) == 1
    child_values, child_root = calls[0]
    assert child_root == tmp_path.resolve()
    assert child_values.shape == (1, 3, 224, 224)
    assert child_values.dtype == np.dtype(np.float32)
    assert np.array_equal(child_values, pixel_values)
    assert sender.sent == [image_similarity_process._success_message(embedding_rows(1))]
    assert len(sender.sent[0]) <= CLIP_PROCESS_MAX_MESSAGE_BYTES
    assert sender.close_calls == 1


def test_child_reduces_sensitive_failure_to_fixed_tag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sender = RecordingEndpoint()
    sensitive = f"bad model at {tmp_path}/secret.onnx"

    def fail(**kwargs: object) -> object:
        del kwargs
        raise RuntimeError(sensitive)

    monkeypatch.setattr(image_similarity_process, "encode_preprocessed_clip_images", fail)
    payload = bytes(CLIP_PIXEL_VALUES_BYTES_PER_IMAGE)

    image_similarity_process._encode_clip_images_in_child(
        sender,
        str(tmp_path.resolve()),
        1,
        payload,
    )

    assert sender.sent == [b"error"]
    assert sensitive.encode() not in sender.sent[0]
    assert sender.close_calls == 1


def test_process_module_has_no_network_pickle_or_provider_fallback_import() -> None:
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


@pytest.mark.clip_runtime
def test_repository_local_model_runs_in_isolated_cpu_process() -> None:
    result = run_pinned_clip_image_encoder(
        (proxy_image(source_tag="real-model"),),
        asset_root=REPOSITORY_MODEL_ROOT,
        encoder=ProcessIsolatedClipImageEncoder(),
    )

    assert len(result) == 1
    assert len(result[0].values) == CLIP_EMBEDDING_DIMENSION
    assert all(np.isfinite(component) for component in result[0].values)
    assert np.linalg.vector_norm(np.asarray(result[0].values)) == pytest.approx(1.0)


@pytest.mark.clip_runtime
def test_received_pair_is_reproducible_and_distinguishable_from_positive_reference() -> None:
    images = (
        quality_proxy_image(
            path=QUALITY_POSITIVE_IMAGE,
            source_tag="positive",
            expected_sha256=QUALITY_POSITIVE_SHA256,
        ),
        quality_proxy_image(
            path=QUALITY_NEGATIVE_IMAGE,
            source_tag="negative",
            expected_sha256=QUALITY_NEGATIVE_SHA256,
        ),
    )

    runs = tuple(
        run_pinned_clip_image_encoder(
            images,
            asset_root=REPOSITORY_MODEL_ROOT,
            encoder=ProcessIsolatedClipImageEncoder(),
        )
        for _ in range(3)
    )

    # One supplied positive image stands in for all four reference angles here. This proves
    # deterministic image-to-image ordering only, not query semantics or production quality.
    assert runs[1:] == (runs[0], runs[0])
    scores = tuple(
        (
            score_clip_image_similarity((positive,) * 4, (positive,)).image_score,
            score_clip_image_similarity((positive,) * 4, (negative,)).image_score,
        )
        for positive, negative in runs
    )
    assert scores[1:] == (scores[0], scores[0])
    assert scores[0][0] == pytest.approx(1.0)
    assert scores[0][0] > scores[0][1]
    print(
        "received CLIP pair: "
        f"runs=3 positive={scores[0][0]:.9f} "
        f"negative={scores[0][1]:.9f} "
        f"margin={scores[0][0] - scores[0][1]:.9f}"
    )
