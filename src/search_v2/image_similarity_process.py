from __future__ import annotations

import multiprocessing
import struct
from pathlib import Path
from time import monotonic as _monotonic
from typing import Literal
from typing import Protocol

import numpy as np

from src.search_v2.image_proxy import ProxyImage
from src.search_v2.image_similarity import CLIP_EMBEDDING_DIMENSION
from src.search_v2.image_similarity import CLIP_MAX_IMAGES_PER_SET
from src.search_v2.image_similarity import ClipRuntimeError
from src.search_v2.image_similarity import verify_clip_asset_directory
from src.search_v2.image_similarity_onnx import CLIP_IMAGE_SIZE
from src.search_v2.image_similarity_onnx import CLIP_PIXEL_VALUES_BYTES_PER_IMAGE
from src.search_v2.image_similarity_onnx import encode_preprocessed_clip_images
from src.search_v2.image_similarity_onnx import preprocess_clip_images
from src.search_v2.image_similarity_onnx import validate_embedding_rows


CLIP_PROCESS_TIMEOUT_SECONDS = 30.0
CLIP_PROCESS_MAX_INPUT_BYTES = CLIP_MAX_IMAGES_PER_SET * CLIP_PIXEL_VALUES_BYTES_PER_IMAGE

_SUCCESS_MAGIC = b"CLIPV1\x00\x00"
_SUCCESS_HEADER = struct.Struct("<8sB")
CLIP_PROCESS_MAX_MESSAGE_BYTES = (
    _SUCCESS_HEADER.size + CLIP_MAX_IMAGES_PER_SET * CLIP_EMBEDDING_DIMENSION * 4
)
_FAILURE_MESSAGE = b"error"
_PROCESS_CLEANUP_RESERVE_SECONDS = 2.0
_PROCESS_CLEANUP_STEP_SECONDS = 0.5
_MAX_ASSET_ROOT_CHARACTERS = 4096


class _Connection(Protocol):
    def poll(self, timeout: float) -> bool: ...

    def recv_bytes(self, maxlength: int) -> bytes: ...

    def send_bytes(self, message: bytes) -> None: ...

    def close(self) -> None: ...


class _Process(Protocol):
    @property
    def exitcode(self) -> int | None: ...

    def start(self) -> None: ...

    def join(self, timeout: float) -> None: ...

    def is_alive(self) -> bool: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...

    def close(self) -> None: ...


def _raise_process_failed() -> None:
    raise ClipRuntimeError("CLIP process encoder failed") from None


def _close_connection(connection: _Connection | None) -> bool:
    if connection is None:
        return True
    try:
        connection.close()
    except BaseException:
        return False
    return True


def _remaining_seconds(deadline: float) -> float:
    return max(0.0, deadline - _monotonic())


def _join_with_deadline(process: _Process, deadline: float) -> bool:
    try:
        process.join(
            min(
                _remaining_seconds(deadline),
                _PROCESS_CLEANUP_STEP_SECONDS,
            )
        )
    except BaseException:
        return False
    return True


def _is_alive(process: _Process) -> bool | None:
    try:
        return process.is_alive()
    except BaseException:
        return None


def _cleanup_process(
    process: _Process | None,
    *,
    started: bool,
    finished: bool,
    deadline: float,
) -> bool:
    if process is None:
        return True

    cleanup_succeeded = True
    alive = False if not started or finished else _is_alive(process)
    if alive is not False:
        try:
            process.terminate()
        except BaseException:
            cleanup_succeeded = False
        cleanup_succeeded = _join_with_deadline(process, deadline) and cleanup_succeeded
        alive = _is_alive(process)
    if alive is not False:
        try:
            process.kill()
        except BaseException:
            cleanup_succeeded = False
        cleanup_succeeded = _join_with_deadline(process, deadline) and cleanup_succeeded
        alive = _is_alive(process)
    if alive is not False:
        return False

    try:
        process.close()
    except BaseException:
        return False
    return cleanup_succeeded


def _success_message(rows: tuple[tuple[float, ...], ...]) -> bytes:
    validate_embedding_rows(rows)
    try:
        values = np.ascontiguousarray(np.asarray(rows, dtype="<f4"))
        message = _SUCCESS_HEADER.pack(_SUCCESS_MAGIC, len(rows)) + values.tobytes(order="C")
    except Exception:
        _raise_process_failed()
    if len(message) > CLIP_PROCESS_MAX_MESSAGE_BYTES:
        _raise_process_failed()
    return message


def _validated_message(
    message: object,
    *,
    expected_count: int,
) -> tuple[tuple[float, ...], ...]:
    if (
        type(message) is not bytes
        or len(message) < _SUCCESS_HEADER.size
        or len(message) > CLIP_PROCESS_MAX_MESSAGE_BYTES
    ):
        _raise_process_failed()
    try:
        magic, count = _SUCCESS_HEADER.unpack_from(message)
    except struct.error:
        _raise_process_failed()
    expected_length = _SUCCESS_HEADER.size + expected_count * CLIP_EMBEDDING_DIMENSION * 4
    if magic != _SUCCESS_MAGIC or count != expected_count or len(message) != expected_length:
        _raise_process_failed()
    try:
        values = np.frombuffer(message, dtype="<f4", offset=_SUCCESS_HEADER.size).reshape(
            expected_count,
            CLIP_EMBEDDING_DIMENSION,
        )
    except (TypeError, ValueError):
        _raise_process_failed()
    if not bool(np.isfinite(values).all()):
        _raise_process_failed()
    rows = tuple(tuple(float(component) for component in row) for row in values)
    try:
        validate_embedding_rows(rows)
    except Exception:
        _raise_process_failed()
    return rows


def _validated_child_input(
    asset_root_text: object,
    image_count: object,
    pixel_bytes: object,
) -> tuple[Path, np.ndarray]:
    if (
        type(asset_root_text) is not str
        or not asset_root_text
        or len(asset_root_text) > _MAX_ASSET_ROOT_CHARACTERS
        or "\x00" in asset_root_text
        or type(image_count) is not int
        or not 1 <= image_count <= CLIP_MAX_IMAGES_PER_SET
        or type(pixel_bytes) is not bytes
        or len(pixel_bytes) != image_count * CLIP_PIXEL_VALUES_BYTES_PER_IMAGE
        or len(pixel_bytes) > CLIP_PROCESS_MAX_INPUT_BYTES
    ):
        _raise_process_failed()
    root = Path(asset_root_text)
    if not root.is_absolute():
        _raise_process_failed()
    try:
        pixel_values = np.frombuffer(pixel_bytes, dtype="<f4").reshape(
            image_count,
            3,
            CLIP_IMAGE_SIZE,
            CLIP_IMAGE_SIZE,
        )
    except (TypeError, ValueError):
        _raise_process_failed()
    if not bool(np.isfinite(pixel_values).all()):
        _raise_process_failed()
    return root, pixel_values


def _encode_clip_images_in_child(
    sender: _Connection,
    asset_root_text: str,
    image_count: int,
    pixel_bytes: bytes,
) -> None:
    message = _FAILURE_MESSAGE
    try:
        asset_root, pixel_values = _validated_child_input(
            asset_root_text,
            image_count,
            pixel_bytes,
        )
        rows = encode_preprocessed_clip_images(
            pixel_values=pixel_values,
            asset_root=asset_root,
        )
        if len(rows) != image_count:
            _raise_process_failed()
        message = _success_message(rows)
    except BaseException:
        # Child failures are intentionally reduced to one fixed tag.
        pass

    try:
        sender.send_bytes(message)
    except BaseException:
        # The parent converts missing or broken IPC to its fixed error.
        pass
    try:
        sender.close()
    except BaseException:
        # There is no safe recovery or reporting channel left in the child.
        pass


class ProcessIsolatedClipImageEncoder:
    """Run one bounded CLIP batch in a Windows/WSL-compatible child process."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "<src.search_v2.image_similarity_process.ProcessIsolatedClipImageEncoder object>"

    def encode_images(
        self,
        *,
        images: tuple[ProxyImage, ...],
        asset_root: Path,
        local_files_only: Literal[True],
    ) -> tuple[tuple[float, ...], ...]:
        if local_files_only is not True:
            _raise_process_failed()

        receiver: _Connection | None = None
        sender: _Connection | None = None
        process: _Process | None = None
        deadline = 0.0
        started = False
        finished = False
        succeeded = False
        interruption: BaseException | None = None
        result: tuple[tuple[float, ...], ...] = ()

        try:
            pixel_values = preprocess_clip_images(images)
            image_count = pixel_values.shape[0]
            pixel_bytes = pixel_values.astype("<f4", copy=False).tobytes(order="C")
            if (
                type(pixel_bytes) is not bytes
                or len(pixel_bytes) != image_count * CLIP_PIXEL_VALUES_BYTES_PER_IMAGE
                or len(pixel_bytes) > CLIP_PROCESS_MAX_INPUT_BYTES
            ):
                _raise_process_failed()
            verified_before = verify_clip_asset_directory(Path(asset_root))

            deadline = _monotonic() + CLIP_PROCESS_TIMEOUT_SECONDS
            context = multiprocessing.get_context("spawn")
            receiver, sender = context.Pipe(duplex=False)
            process = context.Process(
                target=_encode_clip_images_in_child,
                args=(
                    sender,
                    str(verified_before.root),
                    image_count,
                    pixel_bytes,
                ),
                daemon=True,
            )
            process.start()
            started = True

            if not _close_connection(sender):
                _raise_process_failed()
            sender = None

            work_deadline = deadline - _PROCESS_CLEANUP_RESERVE_SECONDS
            remaining = _remaining_seconds(work_deadline)
            if remaining <= 0 or not receiver.poll(remaining):
                _raise_process_failed()
            message = receiver.recv_bytes(CLIP_PROCESS_MAX_MESSAGE_BYTES)

            remaining = _remaining_seconds(work_deadline)
            if remaining <= 0:
                _raise_process_failed()
            process.join(remaining)
            alive = process.is_alive()
            finished = not alive
            exitcode = process.exitcode
            if alive or type(exitcode) is not int or exitcode != 0:
                _raise_process_failed()

            result = _validated_message(message, expected_count=image_count)
            verified_after = verify_clip_asset_directory(Path(asset_root))
            if verified_after != verified_before:
                _raise_process_failed()
            succeeded = True
        except Exception:
            succeeded = False
        except BaseException as error:
            interruption = error
            succeeded = False

        process_clean = _cleanup_process(
            process,
            started=started,
            finished=finished,
            deadline=deadline,
        )
        receiver_clean = _close_connection(receiver)
        sender_clean = _close_connection(sender)
        if interruption is not None:
            raise interruption
        if not succeeded or not process_clean or not receiver_clean or not sender_clean:
            _raise_process_failed()
        return result
