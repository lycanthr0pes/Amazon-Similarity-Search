from __future__ import annotations

import ipaddress
import multiprocessing
from time import monotonic as _monotonic
from typing import Protocol

from src.search_v2.image_proxy import IMAGE_PROXY_MAX_DNS_ADDRESSES
from src.search_v2.image_proxy_dns import BoundedImageDnsResolver


IMAGE_PROXY_DNS_PROCESS_TIMEOUT_SECONDS = 5.0
IMAGE_PROXY_DNS_PROCESS_MAX_MESSAGE_BYTES = 512

_PROCESS_FAILED_MESSAGE = "image DNS process failed"
_SUCCESS_PREFIX = b"ok\n"
_FAILURE_MESSAGE = b"error"
_PROCESS_CLEANUP_RESERVE_SECONDS = 0.5
_PROCESS_CLEANUP_STEP_SECONDS = 0.25


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


class ImageProxyDnsProcessError(RuntimeError):
    """Fixed, non-sensitive error from the DNS process boundary."""


def _raise_process_failed() -> None:
    raise ImageProxyDnsProcessError(_PROCESS_FAILED_MESSAGE) from None


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
        timeout = min(
            _remaining_seconds(deadline),
            _PROCESS_CLEANUP_STEP_SECONDS,
        )
        process.join(timeout)
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


def _validated_numeric_address(raw_address: object) -> str:
    if type(raw_address) is not str:
        _raise_process_failed()
    try:
        address = ipaddress.ip_address(raw_address)
    except ValueError:
        _raise_process_failed()
    if raw_address != address.compressed:
        _raise_process_failed()
    return raw_address


def _validated_message(message: object) -> tuple[str, ...]:
    if (
        type(message) is not bytes
        or not message.startswith(_SUCCESS_PREFIX)
        or len(message) > IMAGE_PROXY_DNS_PROCESS_MAX_MESSAGE_BYTES
    ):
        _raise_process_failed()
    raw_addresses = message.split(b"\n")[1:]
    if not raw_addresses or len(raw_addresses) > IMAGE_PROXY_MAX_DNS_ADDRESSES:
        _raise_process_failed()
    try:
        addresses = tuple(item.decode("ascii") for item in raw_addresses)
    except UnicodeDecodeError:
        _raise_process_failed()
    return tuple(_validated_numeric_address(item) for item in addresses)


def _success_message(addresses: tuple[str, ...]) -> bytes:
    validated = tuple(_validated_numeric_address(item) for item in addresses)
    message = _SUCCESS_PREFIX + b"\n".join(item.encode("ascii") for item in validated)
    if len(message) > IMAGE_PROXY_DNS_PROCESS_MAX_MESSAGE_BYTES:
        _raise_process_failed()
    return message


def _resolve_image_host_in_child(sender: _Connection, host: str) -> None:
    message = _FAILURE_MESSAGE
    try:
        message = _success_message(BoundedImageDnsResolver()(host))
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


class ProcessIsolatedImageDnsResolver:
    """Resolve an image host in a bounded child process."""

    __slots__ = ()

    def __call__(self, host: str) -> tuple[str, ...]:
        if type(host) is not str or not host or len(host) > 253:
            _raise_process_failed()

        receiver: _Connection | None = None
        sender: _Connection | None = None
        process: _Process | None = None
        deadline = 0.0
        started = False
        finished = False
        succeeded = False
        interruption: BaseException | None = None
        result: tuple[str, ...] = ()

        try:
            deadline = _monotonic() + IMAGE_PROXY_DNS_PROCESS_TIMEOUT_SECONDS
            context = multiprocessing.get_context("spawn")
            receiver, sender = context.Pipe(duplex=False)
            process = context.Process(
                target=_resolve_image_host_in_child,
                args=(sender, host),
                daemon=True,
            )
            process.start()
            started = True

            if not _close_connection(sender):
                _raise_process_failed()
            sender = None

            resolution_deadline = deadline - _PROCESS_CLEANUP_RESERVE_SECONDS
            remaining = _remaining_seconds(resolution_deadline)
            if remaining <= 0 or not receiver.poll(remaining):
                _raise_process_failed()
            message = receiver.recv_bytes(IMAGE_PROXY_DNS_PROCESS_MAX_MESSAGE_BYTES)

            remaining = _remaining_seconds(resolution_deadline)
            if remaining <= 0:
                _raise_process_failed()
            process.join(remaining)
            alive = process.is_alive()
            finished = not alive
            exitcode = process.exitcode
            if alive or type(exitcode) is not int or exitcode != 0:
                _raise_process_failed()

            result = _validated_message(message)
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
