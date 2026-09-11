from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

import pytest

import src.search_v2.image_proxy_dns_process as image_proxy_dns_process
from src.search_v2.image_proxy_dns_process import IMAGE_PROXY_DNS_PROCESS_TIMEOUT_SECONDS
from src.search_v2.image_proxy_dns_process import ImageProxyDnsProcessError
from src.search_v2.image_proxy_dns_process import ProcessIsolatedImageDnsResolver


ALLOWED_HOST = "images.example.test"
PUBLIC_IPV4 = "93.184.216.34"
PUBLIC_IPV6 = "2001:4860:4860::8888"
SENSITIVE_MESSAGE = f"resolver exposed {ALLOWED_HOST}"
MODULE_PATH = Path("src/search_v2/image_proxy_dns_process.py")
_UNSET = object()


class StringSubclass(str):
    pass


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
        self.sent: list[object] = []
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


class RecordingResolver:
    def __init__(
        self,
        addresses: tuple[str, ...] = (PUBLIC_IPV4,),
        *,
        error: BaseException | None = None,
    ) -> None:
        self.addresses = addresses
        self.error = error
        self.calls: list[str] = []

    def __call__(self, host: str) -> tuple[str, ...]:
        self.calls.append(host)
        if self.error is not None:
            raise self.error
        return self.addresses


class RecordingFactory:
    def __init__(self, value: object) -> None:
        self.value = value
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def __call__(self, *args: object, **kwargs: object) -> object:
        self.calls.append((args, kwargs))
        return self.value


def install_context(
    monkeypatch: pytest.MonkeyPatch,
    *,
    message: object = f"ok\n{PUBLIC_IPV4}\n{PUBLIC_IPV6}".encode("ascii"),
    poll_result: bool = True,
    poll_error: BaseException | None = None,
    recv_error: BaseException | None = None,
    receiver_close_error: BaseException | None = None,
    sender_close_error: BaseException | None = None,
    process: RecordingProcess | None = None,
    clock_values: tuple[float, ...] = (100.0, 100.25, 100.5, 100.75),
) -> tuple[
    RecordingContext,
    RecordingEndpoint,
    RecordingEndpoint,
    RecordingProcess,
    list[str],
]:
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

    monkeypatch.setattr(image_proxy_dns_process.multiprocessing, "get_context", get_context)
    monkeypatch.setattr(
        image_proxy_dns_process,
        "_monotonic",
        RecordingClock(clock_values),
    )
    return context, receiver, sender, configured_process, context_names


def resolve_with_fake_context(monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> tuple[str, ...]:
    install_context(monkeypatch, **kwargs)
    return ProcessIsolatedImageDnsResolver()(ALLOWED_HOST)


def test_public_contract_is_fixed_and_construction_is_lazy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_get_context(name: str) -> object:
        raise AssertionError(name)

    monkeypatch.setattr(
        image_proxy_dns_process.multiprocessing,
        "get_context",
        unexpected_get_context,
    )

    resolver = ProcessIsolatedImageDnsResolver()

    assert IMAGE_PROXY_DNS_PROCESS_TIMEOUT_SECONDS == 5.0
    assert image_proxy_dns_process.IMAGE_PROXY_DNS_PROCESS_MAX_MESSAGE_BYTES == 512
    assert tuple(inspect.signature(ProcessIsolatedImageDnsResolver).parameters) == ()
    assert tuple(inspect.signature(resolver.__call__).parameters) == ("host",)
    assert ALLOWED_HOST not in repr(resolver)


def test_resolves_once_through_spawn_process_and_validates_ipc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, receiver, sender, process, context_names = install_context(monkeypatch)

    result = ProcessIsolatedImageDnsResolver()(ALLOWED_HOST)

    assert result == (PUBLIC_IPV4, PUBLIC_IPV6)
    assert context_names == ["spawn"]
    assert context.pipe_calls == [False]
    assert len(context.process_calls) == 1
    process_call = context.process_calls[0]
    assert process_call["target"] is image_proxy_dns_process._resolve_image_host_in_child
    assert process_call["args"] == (sender, ALLOWED_HOST)
    assert process_call["daemon"] is True
    assert process.start_calls == 1
    assert receiver.recv_calls == [512]
    assert len(receiver.poll_calls) == 1
    assert 0 < receiver.poll_calls[0] <= IMAGE_PROXY_DNS_PROCESS_TIMEOUT_SECONDS
    assert process.join_calls
    assert all(
        0 <= timeout <= IMAGE_PROXY_DNS_PROCESS_TIMEOUT_SECONDS for timeout in process.join_calls
    )
    assert process.terminate_calls == 0
    assert process.kill_calls == 0
    assert process.close_calls == 1
    assert receiver.close_calls == 1
    assert sender.close_calls >= 1


def test_deadline_reserves_cleanup_time_after_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, receiver, _, process, _ = install_context(
        monkeypatch,
        clock_values=(10.0, 11.0, 12.0, 13.0),
    )

    assert ProcessIsolatedImageDnsResolver()(ALLOWED_HOST) == (PUBLIC_IPV4, PUBLIC_IPV6)

    assert receiver.poll_calls == [3.5]
    assert process.join_calls[0] == 2.5
    assert len(context.process_calls) == 1


@pytest.mark.parametrize(
    "host",
    [None, False, "", "a" * 254, StringSubclass(ALLOWED_HOST)],
)
def test_rejects_unsafe_ipc_host_before_process_creation(
    monkeypatch: pytest.MonkeyPatch,
    host: object,
) -> None:
    context_calls: list[str] = []

    def get_context(name: str) -> object:
        context_calls.append(name)
        raise AssertionError("process context must not be created")

    monkeypatch.setattr(image_proxy_dns_process.multiprocessing, "get_context", get_context)

    with pytest.raises(
        ImageProxyDnsProcessError,
        match="^image DNS process failed$",
    ) as error:
        ProcessIsolatedImageDnsResolver()(host)  # type: ignore[arg-type]

    assert context_calls == []
    assert ALLOWED_HOST not in str(error.value)


def test_timeout_terminates_child_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    process = RecordingProcess(alive_after_start=True, terminate_stops=True)
    context, receiver, _, _, context_names = install_context(
        monkeypatch,
        poll_result=False,
        process=process,
    )

    with pytest.raises(ImageProxyDnsProcessError, match="^image DNS process failed$"):
        ProcessIsolatedImageDnsResolver()(ALLOWED_HOST)

    assert context_names == ["spawn"]
    assert len(context.process_calls) == 1
    assert receiver.recv_calls == []
    assert process.start_calls == 1
    assert process.terminate_calls == 1
    assert process.kill_calls == 0
    assert process.close_calls == 1
    assert process.join_calls == [0.25]


def test_kills_child_once_when_terminate_does_not_stop_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = RecordingProcess(
        alive_after_start=True,
        terminate_stops=False,
        kill_stops=True,
    )
    context, _, _, _, _ = install_context(
        monkeypatch,
        poll_result=False,
        process=process,
    )

    with pytest.raises(ImageProxyDnsProcessError, match="^image DNS process failed$"):
        ProcessIsolatedImageDnsResolver()(ALLOWED_HOST)

    assert len(context.process_calls) == 1
    assert process.terminate_calls == 1
    assert process.kill_calls == 1
    assert process.close_calls == 1
    assert len(process.join_calls) == 2
    assert all(0 <= timeout <= 0.25 for timeout in process.join_calls)


def test_rejects_result_if_child_does_not_exit_before_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = RecordingProcess(alive_after_start=True, terminate_stops=True)
    install_context(monkeypatch, process=process)

    with pytest.raises(ImageProxyDnsProcessError, match="^image DNS process failed$"):
        ProcessIsolatedImageDnsResolver()(ALLOWED_HOST)

    assert process.terminate_calls == 1
    assert process.kill_calls == 0


@pytest.mark.parametrize(
    "message",
    [
        None,
        [],
        b"",
        b"ok",
        b"ok\n",
        b"ok\nnot-an-ip",
        b"ok\n2001:4860:4860:0:0:0:0:8888",
        b"ok\n" + b"\n".join(PUBLIC_IPV4.encode("ascii") for _ in range(9)),
        BytesSubclass(f"ok\n{PUBLIC_IPV4}".encode("ascii")),
        f"error\n{SENSITIVE_MESSAGE}".encode("ascii"),
        f"unknown\n{PUBLIC_IPV4}".encode("ascii"),
        f"ok\n{PUBLIC_IPV4}\n".encode("ascii"),
        b"ok\n\xff",
    ],
)
def test_rejects_malformed_or_noncanonical_ipc_message(
    monkeypatch: pytest.MonkeyPatch,
    message: object,
) -> None:
    install_context(monkeypatch, message=message)

    with pytest.raises(
        ImageProxyDnsProcessError,
        match="^image DNS process failed$",
    ) as error:
        ProcessIsolatedImageDnsResolver()(ALLOWED_HOST)

    assert SENSITIVE_MESSAGE not in str(error.value)
    assert ALLOWED_HOST not in str(error.value)


@pytest.mark.parametrize(
    ("kwargs", "process"),
    [
        ({"poll_error": RuntimeError(SENSITIVE_MESSAGE)}, None),
        ({"recv_error": RuntimeError(SENSITIVE_MESSAGE)}, None),
        ({"receiver_close_error": RuntimeError(SENSITIVE_MESSAGE)}, None),
        ({"sender_close_error": RuntimeError(SENSITIVE_MESSAGE)}, None),
        ({}, RecordingProcess(exitcode=1)),
        ({}, RecordingProcess(start_error=RuntimeError(SENSITIVE_MESSAGE))),
        ({}, RecordingProcess(close_error=RuntimeError(SENSITIVE_MESSAGE))),
    ],
)
def test_converts_process_and_pipe_failures_to_fixed_error(
    monkeypatch: pytest.MonkeyPatch,
    kwargs: dict[str, object],
    process: RecordingProcess | None,
) -> None:
    if process is not None:
        kwargs["process"] = process
    install_context(monkeypatch, **kwargs)

    with pytest.raises(
        ImageProxyDnsProcessError,
        match="^image DNS process failed$",
    ) as error:
        ProcessIsolatedImageDnsResolver()(ALLOWED_HOST)

    assert SENSITIVE_MESSAGE not in str(error.value)
    assert ALLOWED_HOST not in str(error.value)


def test_parent_cleans_child_and_propagates_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = RecordingProcess(alive_after_start=True, terminate_stops=True)
    install_context(
        monkeypatch,
        poll_error=KeyboardInterrupt(),
        process=process,
    )

    with pytest.raises(KeyboardInterrupt):
        ProcessIsolatedImageDnsResolver()(ALLOWED_HOST)

    assert process.terminate_calls == 1
    assert process.kill_calls == 0
    assert process.close_calls == 1


def test_child_worker_sends_only_validated_addresses_and_closes_pipe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = RecordingResolver((PUBLIC_IPV6, PUBLIC_IPV4))
    factory = RecordingFactory(resolver)
    sender = RecordingEndpoint()
    monkeypatch.setattr(image_proxy_dns_process, "BoundedImageDnsResolver", factory)

    image_proxy_dns_process._resolve_image_host_in_child(sender, ALLOWED_HOST)

    assert factory.calls == [((), {})]
    assert resolver.calls == [ALLOWED_HOST]
    assert sender.sent == [f"ok\n{PUBLIC_IPV6}\n{PUBLIC_IPV4}".encode("ascii")]
    assert sender.close_calls == 1


@pytest.mark.parametrize(
    "error",
    [RuntimeError(SENSITIVE_MESSAGE), KeyboardInterrupt(), SystemExit(2)],
)
def test_child_worker_converts_all_resolver_failures_to_fixed_tag(
    monkeypatch: pytest.MonkeyPatch,
    error: BaseException,
) -> None:
    resolver = RecordingResolver(error=error)
    sender = RecordingEndpoint()
    monkeypatch.setattr(
        image_proxy_dns_process,
        "BoundedImageDnsResolver",
        RecordingFactory(resolver),
    )

    image_proxy_dns_process._resolve_image_host_in_child(sender, ALLOWED_HOST)

    assert resolver.calls == [ALLOWED_HOST]
    assert sender.sent == [b"error"]
    assert sender.close_calls == 1


def test_child_worker_swallows_pipe_failure_and_still_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sender = RecordingEndpoint(
        send_error=RuntimeError(SENSITIVE_MESSAGE),
        close_error=RuntimeError(SENSITIVE_MESSAGE),
    )
    monkeypatch.setattr(
        image_proxy_dns_process,
        "BoundedImageDnsResolver",
        RecordingFactory(RecordingResolver()),
    )

    image_proxy_dns_process._resolve_image_host_in_child(sender, ALLOWED_HOST)

    assert sender.sent == []
    assert sender.close_calls == 1


def test_module_uses_spawn_without_shell_network_or_retry_helpers() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        node.module.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    method_calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert imported_roots.isdisjoint(
        {"asyncio", "http", "logging", "os", "requests", "socket", "subprocess", "urllib"}
    )
    assert 'get_context("spawn")' in source
    assert "fork" not in source.lower()
    assert "forkserver" not in source.lower()
    assert "print" not in called_names
    assert "recv_bytes" in method_calls
    assert "send_bytes" in method_calls
    assert "recv" not in method_calls
    assert "send" not in method_calls
    assert not method_calls.intersection({"getaddrinfo", "sleep", "system"})
    assert not any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(tree))


def test_test_file_does_not_disable_network_guard() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    attribute_names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    variable_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}

    assert "live_api" not in attribute_names
    assert "original_socket_type" not in variable_names
