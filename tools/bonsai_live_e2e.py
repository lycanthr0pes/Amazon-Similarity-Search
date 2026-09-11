from __future__ import annotations

import http.client
import json
import math
import os
import socket
import stat
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

from src.search_v2.bonsai_http import RequestsBonsaiTransport
from src.search_v2.bonsai_request import BONSAI_MAX_RESPONSE_BYTES
from src.search_v2.bonsai_request import BonsaiHttpResponse
from src.search_v2.bonsai_request import BonsaiIntentExecution
from src.search_v2.bonsai_request import BonsaiRequestTransport
from src.search_v2.bonsai_request import PreparedBonsaiIntentRequest
from src.search_v2.bonsai_request import bonsai_intent_request_sha256
from src.search_v2.bonsai_request import build_bonsai_intent_request
from src.search_v2.bonsai_request import execute_bonsai_intent_request
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import ProviderUsageLimits
from src.search_v2.usage_ledger import UsageAmount
from src.search_v2.usage_ledger import UsageReservationRequest


BONSAI_E2E_HOST = "127.0.0.1"
BONSAI_E2E_CONTEXT_SIZE = 8192
BONSAI_E2E_PARALLEL_SLOTS = 1
BONSAI_E2E_REQUEST_COUNT = 2
BONSAI_E2E_STARTUP_DEADLINE_SECONDS = 180
BONSAI_E2E_RUN_DEADLINE_SECONDS = 900
BONSAI_E2E_STOP_DEADLINE_SECONDS = 5
BONSAI_E2E_HEALTH_POLL_SECONDS = 0.25
BONSAI_E2E_HEALTH_TIMEOUT_SECONDS = 1
BONSAI_E2E_MIN_PORT = 1024
BONSAI_E2E_MAX_PORT = 65535
BONSAI_E2E_PRICING_POLICY_SHA256 = "0" * 64
SYNTHETIC_INPUTS = (
    "黒いワイヤレスヘッドホンを5万円以内で。中古品は避けたい。",
    "白い軽量ワイヤレスマウスを1万円以内で。中古品は避けたい。",
)
BONSAI_DIAGNOSTIC_INPUT = SYNTHETIC_INPUTS[0]
BONSAI_E2E_MAX_METRIC_MILLISECONDS = BONSAI_E2E_RUN_DEADLINE_SECONDS * 1000
BONSAI_E2E_FINISH_REASONS = frozenset({"length", "stop"})

_CONFIGURATION_ERROR = "Bonsai E2E configuration is invalid"
_RESPONSE_METADATA_ERROR = "Bonsai E2E response metadata is invalid"
_PORT_IN_USE_ERROR = "Bonsai E2E loopback port is already in use"
_STARTUP_ERROR = "Bonsai E2E server did not become ready"
_REQUEST_ERROR = "Bonsai E2E request failed"
_CACHE_ERROR = "Bonsai E2E prompt cache was not reused"
_DEADLINE_ERROR = "Bonsai E2E run deadline was reached"
_CLEANUP_ERROR = "Bonsai E2E server cleanup failed"


class BonsaiLiveE2EError(RuntimeError):
    pass


def _raise_configuration_error() -> None:
    raise BonsaiLiveE2EError(_CONFIGURATION_ERROR)


def _validated_regular_file(path: object, *, executable: bool) -> Path:
    if not isinstance(path, Path) or not path.is_absolute():
        _raise_configuration_error()
    try:
        details = path.lstat()
    except OSError:
        _raise_configuration_error()
    if not stat.S_ISREG(details.st_mode) or details.st_size <= 0:
        _raise_configuration_error()
    if executable and not os.access(path, os.X_OK):
        _raise_configuration_error()
    return path


@dataclass(frozen=True, slots=True)
class BonsaiLiveE2EConfig:
    server_binary: Path
    model_path: Path
    port: int

    def __post_init__(self) -> None:
        _validated_regular_file(self.server_binary, executable=True)
        _validated_regular_file(self.model_path, executable=False)
        if (
            type(self.port) is not int
            or self.port < BONSAI_E2E_MIN_PORT
            or self.port > BONSAI_E2E_MAX_PORT
        ):
            _raise_configuration_error()


@dataclass(frozen=True, slots=True)
class BonsaiPromptUsage:
    prompt_tokens: int
    cached_tokens: int


@dataclass(frozen=True, slots=True)
class BonsaiResponseMetrics:
    prompt_usage: BonsaiPromptUsage
    completion_tokens: int
    prompt_tokens_processed: int
    prompt_milliseconds: float
    predicted_tokens: int
    predicted_milliseconds: float
    finish_reason: str
    response_bytes: int


@dataclass(frozen=True, slots=True)
class BonsaiLiveE2EResult:
    request_count: int
    schema_versions: tuple[str, ...]
    response_metrics: tuple[BonsaiResponseMetrics, ...]
    wall_milliseconds: tuple[int, ...]
    server_stopped: bool

    @property
    def prompt_usages(self) -> tuple[BonsaiPromptUsage, ...]:
        return tuple(item.prompt_usage for item in self.response_metrics)


def build_llama_server_command(config: BonsaiLiveE2EConfig) -> tuple[str, ...]:
    if type(config) is not BonsaiLiveE2EConfig:
        _raise_configuration_error()
    return (
        str(config.server_binary),
        "-m",
        str(config.model_path),
        "-c",
        str(BONSAI_E2E_CONTEXT_SIZE),
        "-np",
        str(BONSAI_E2E_PARALLEL_SLOTS),
        "--cache-prompt",
        "--host",
        BONSAI_E2E_HOST,
        "--port",
        str(config.port),
        "--log-disable",
    )


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    del value
    raise ValueError("non-finite JSON number")


def _response_envelope(response: bytes) -> dict[str, Any]:
    if type(response) is not bytes or not response or len(response) > BONSAI_MAX_RESPONSE_BYTES:
        raise ValueError("response bytes are invalid")
    envelope = json.loads(
        response.decode("utf-8"),
        object_pairs_hook=_strict_object,
        parse_constant=_reject_json_constant,
    )
    if type(envelope) is not dict:
        raise ValueError("response envelope is invalid")
    return envelope


def _prompt_usage_from_envelope(envelope: dict[str, Any]) -> BonsaiPromptUsage:
    usage = envelope.get("usage")
    if type(usage) is not dict:
        raise ValueError("response usage is invalid")
    prompt_tokens = usage.get("prompt_tokens")
    prompt_details = usage.get("prompt_tokens_details")
    if type(prompt_details) is not dict:
        raise ValueError("prompt token details are invalid")
    cached_tokens = prompt_details.get("cached_tokens")
    if (
        type(prompt_tokens) is not int
        or prompt_tokens <= 0
        or prompt_tokens > BONSAI_E2E_CONTEXT_SIZE
        or type(cached_tokens) is not int
        or cached_tokens < 0
        or cached_tokens > prompt_tokens
    ):
        raise ValueError("prompt token counts are invalid")
    return BonsaiPromptUsage(
        prompt_tokens=prompt_tokens,
        cached_tokens=cached_tokens,
    )


def project_prompt_usage(response: bytes) -> BonsaiPromptUsage:
    try:
        return _prompt_usage_from_envelope(_response_envelope(response))
    except (LookupError, TypeError, UnicodeError, ValueError):
        raise BonsaiLiveE2EError(_RESPONSE_METADATA_ERROR) from None


def _bounded_milliseconds(value: object) -> float:
    if type(value) not in {int, float}:
        raise ValueError("timing value is invalid")
    normalized = float(value)
    if (
        not math.isfinite(normalized)
        or normalized < 0
        or normalized > BONSAI_E2E_MAX_METRIC_MILLISECONDS
    ):
        raise ValueError("timing value is out of range")
    return normalized


def project_response_metrics(response: bytes) -> BonsaiResponseMetrics:
    try:
        envelope = _response_envelope(response)
        prompt_usage = _prompt_usage_from_envelope(envelope)
        usage = envelope.get("usage")
        timings = envelope.get("timings")
        choices = envelope.get("choices")
        if type(usage) is not dict or type(timings) is not dict:
            raise ValueError("response metrics are missing")
        if type(choices) is not list or len(choices) != 1 or type(choices[0]) is not dict:
            raise ValueError("response choice metadata is invalid")

        completion_tokens = usage.get("completion_tokens")
        total_tokens = usage.get("total_tokens")
        prompt_tokens_processed = timings.get("prompt_n")
        cache_tokens = timings.get("cache_n")
        predicted_tokens = timings.get("predicted_n")
        finish_reason = choices[0].get("finish_reason")
        if (
            type(completion_tokens) is not int
            or completion_tokens <= 0
            or completion_tokens > BONSAI_MAX_RESPONSE_BYTES
            or type(total_tokens) is not int
            or total_tokens != prompt_usage.prompt_tokens + completion_tokens
            or type(prompt_tokens_processed) is not int
            or prompt_tokens_processed < 0
            or prompt_tokens_processed > prompt_usage.prompt_tokens
            or type(cache_tokens) is not int
            or cache_tokens != prompt_usage.cached_tokens
            or prompt_tokens_processed + cache_tokens != prompt_usage.prompt_tokens
            or type(predicted_tokens) is not int
            or predicted_tokens != completion_tokens
            or finish_reason not in BONSAI_E2E_FINISH_REASONS
        ):
            raise ValueError("response metric values are invalid")

        prompt_milliseconds = _bounded_milliseconds(timings.get("prompt_ms"))
        predicted_milliseconds = _bounded_milliseconds(timings.get("predicted_ms"))
        if completion_tokens > 0 and predicted_milliseconds <= 0:
            raise ValueError("generation timing is invalid")
        if prompt_tokens_processed > 0 and prompt_milliseconds <= 0:
            raise ValueError("prompt timing is invalid")

        return BonsaiResponseMetrics(
            prompt_usage=prompt_usage,
            completion_tokens=completion_tokens,
            prompt_tokens_processed=prompt_tokens_processed,
            prompt_milliseconds=prompt_milliseconds,
            predicted_tokens=predicted_tokens,
            predicted_milliseconds=predicted_milliseconds,
            finish_reason=finish_reason,
            response_bytes=len(response),
        )
    except (LookupError, TypeError, UnicodeError, ValueError):
        raise BonsaiLiveE2EError(_RESPONSE_METADATA_ERROR) from None


class _CapturingTransport(BonsaiRequestTransport):
    def __init__(self) -> None:
        self._delegate = RequestsBonsaiTransport()
        self._response_body: bytes | None = None

    def post_json(
        self,
        *,
        url: str,
        headers: tuple[tuple[str, str], ...],
        body: bytes,
        allow_redirects: bool,
        accept_encoding: str,
        maximum_response_bytes: int,
    ) -> BonsaiHttpResponse:
        response = self._delegate.post_json(
            url=url,
            headers=headers,
            body=body,
            allow_redirects=allow_redirects,
            accept_encoding=accept_encoding,
            maximum_response_bytes=maximum_response_bytes,
        )
        chunks = tuple(response.body_chunks)
        response_body = b"".join(chunks)
        self._response_body = response_body
        return BonsaiHttpResponse(
            status_code=response.status_code,
            content_type=response.content_type,
            content_length=response.content_length,
            content_encoding=response.content_encoding,
            body_chunks=(response_body,),
        )

    def take_response_body(self) -> bytes:
        if self._response_body is None:
            raise BonsaiLiveE2EError(_RESPONSE_METADATA_ERROR)
        response_body = self._response_body
        self._response_body = None
        return response_body

    def clear(self) -> None:
        self._response_body = None


def _port_is_listening(port: int) -> bool:
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.settimeout(0.2)
        return client.connect_ex((BONSAI_E2E_HOST, port)) == 0
    finally:
        client.close()


def _health_ready(port: int) -> bool:
    connection = http.client.HTTPConnection(
        BONSAI_E2E_HOST,
        port,
        timeout=BONSAI_E2E_HEALTH_TIMEOUT_SECONDS,
    )
    try:
        connection.request(
            "GET",
            "/health",
            headers={"Accept": "application/json", "Connection": "close"},
        )
        response = connection.getresponse()
        response.read(4096)
        return response.status == 200
    except (OSError, http.client.HTTPException):
        return False
    finally:
        connection.close()


def _wait_until_ready(process: subprocess.Popen[bytes], port: int) -> None:
    deadline = time.monotonic() + BONSAI_E2E_STARTUP_DEADLINE_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise BonsaiLiveE2EError(_STARTUP_ERROR)
        if _health_ready(port):
            return
        time.sleep(BONSAI_E2E_HEALTH_POLL_SECONDS)
    raise BonsaiLiveE2EError(_STARTUP_ERROR)


def _stop_server(process: subprocess.Popen[bytes], port: int) -> None:
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=BONSAI_E2E_STOP_DEADLINE_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()
                try:
                    process.wait(timeout=BONSAI_E2E_STOP_DEADLINE_SECONDS)
                except subprocess.TimeoutExpired:
                    raise BonsaiLiveE2EError(_CLEANUP_ERROR) from None
    except (OSError, subprocess.SubprocessError):
        raise BonsaiLiveE2EError(_CLEANUP_ERROR) from None

    deadline = time.monotonic() + BONSAI_E2E_STOP_DEADLINE_SECONDS
    while time.monotonic() < deadline:
        if not _port_is_listening(port):
            return
        time.sleep(BONSAI_E2E_HEALTH_POLL_SECONDS)
    raise BonsaiLiveE2EError(_CLEANUP_ERROR)


def _launch_server(config: BonsaiLiveE2EConfig) -> subprocess.Popen[bytes]:
    if _port_is_listening(config.port):
        raise BonsaiLiveE2EError(_PORT_IN_USE_ERROR)
    try:
        return subprocess.Popen(
            build_llama_server_command(config),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={"LC_ALL": "C"},
            close_fds=True,
            start_new_session=True,
        )
    except OSError:
        raise BonsaiLiveE2EError(_STARTUP_ERROR) from None


def _usage_ledger(
    prepared_requests: tuple[PreparedBonsaiIntentRequest, ...],
) -> InMemoryUsageLedger:
    maximum_tokens = sum(item.request.maximum_usage_tokens for item in prepared_requests)
    limit = UsageAmount(
        calls=BONSAI_E2E_REQUEST_COUNT,
        tokens=maximum_tokens,
        cost_microusd=0,
    )
    return InMemoryUsageLedger(
        [
            ProviderUsageLimits(
                provider="bonsai",
                pricing_policy_sha256=BONSAI_E2E_PRICING_POLICY_SHA256,
                per_user_day=limit,
                per_session=limit,
                global_day=limit,
            )
        ]
    )


def _reserve_request(
    ledger: InMemoryUsageLedger,
    prepared: PreparedBonsaiIntentRequest,
):
    return ledger.reserve(
        UsageReservationRequest(
            provider="bonsai",
            operation="intent",
            owner_id="bonsai-e2e-owner",
            session_id="bonsai-e2e-session",
            binding_sha256=bonsai_intent_request_sha256(prepared.request),
            amount=UsageAmount(
                calls=1,
                tokens=prepared.request.maximum_usage_tokens,
                cost_microusd=0,
            ),
            pricing_policy_sha256=BONSAI_E2E_PRICING_POLICY_SHA256,
        ),
        now=datetime.now(timezone.utc),
    )


def _execute_request(
    prepared: PreparedBonsaiIntentRequest,
    *,
    ledger: InMemoryUsageLedger,
    transport=None,
) -> tuple[BonsaiIntentExecution, BonsaiResponseMetrics, int]:
    reservation = _reserve_request(ledger, prepared)
    if transport is None:
        transport = _CapturingTransport()
    started = time.monotonic_ns()
    try:
        execution = execute_bonsai_intent_request(
            prepared,
            usage_ledger=ledger,
            usage_reservation=reservation,
            transport=transport,
            now=lambda: datetime.now(timezone.utc),
        )
        metrics = project_response_metrics(transport.take_response_body())
    except Exception:
        raise BonsaiLiveE2EError(_REQUEST_ERROR) from None
    finally:
        transport.clear()
    elapsed = max(1, (time.monotonic_ns() - started + 999_999) // 1_000_000)
    return execution, metrics, elapsed


def _run_bonsai_requests(
    config: BonsaiLiveE2EConfig,
    *,
    source_inputs: tuple[str, str],
) -> BonsaiLiveE2EResult:
    if type(config) is not BonsaiLiveE2EConfig:
        _raise_configuration_error()
    base_url = f"http://{BONSAI_E2E_HOST}:{config.port}/v1"
    prepared_requests = tuple(
        build_bonsai_intent_request(
            source_input,
            base_url=base_url,
            model_id=config.model_path.name,
            temperature=0.0,
        )
        for source_input in source_inputs
    )
    ledger = _usage_ledger(prepared_requests)
    process = _launch_server(config)
    deadline_reached = threading.Event()

    def stop_at_deadline() -> None:
        deadline_reached.set()
        try:
            if process.poll() is None:
                process.terminate()
        except OSError:
            return

    timer = threading.Timer(BONSAI_E2E_RUN_DEADLINE_SECONDS, stop_at_deadline)
    timer.daemon = True
    server_stopped = False
    executions: list[BonsaiIntentExecution] = []
    response_metrics: list[BonsaiResponseMetrics] = []
    wall_milliseconds: list[int] = []
    try:
        _wait_until_ready(process, config.port)
        timer.start()
        for prepared in prepared_requests:
            if deadline_reached.is_set():
                raise BonsaiLiveE2EError(_DEADLINE_ERROR)
            try:
                execution, metrics, elapsed = _execute_request(
                    prepared,
                    ledger=ledger,
                )
            except BonsaiLiveE2EError:
                if deadline_reached.is_set():
                    raise BonsaiLiveE2EError(_DEADLINE_ERROR) from None
                raise
            executions.append(execution)
            response_metrics.append(metrics)
            wall_milliseconds.append(elapsed)
        if deadline_reached.is_set():
            raise BonsaiLiveE2EError(_DEADLINE_ERROR)
        if (
            response_metrics[0].prompt_usage.cached_tokens != 0
            or response_metrics[1].prompt_usage.cached_tokens <= 0
        ):
            raise BonsaiLiveE2EError(_CACHE_ERROR)
    finally:
        timer.cancel()
        _stop_server(process, config.port)
        server_stopped = True

    return BonsaiLiveE2EResult(
        request_count=len(executions),
        schema_versions=tuple(item.request.schema_version for item in executions),
        response_metrics=tuple(response_metrics),
        wall_milliseconds=tuple(wall_milliseconds),
        server_stopped=server_stopped,
    )


def run_bonsai_live_e2e(config: BonsaiLiveE2EConfig) -> BonsaiLiveE2EResult:
    return _run_bonsai_requests(config, source_inputs=SYNTHETIC_INPUTS)


def run_bonsai_latency_diagnostic(config: BonsaiLiveE2EConfig) -> BonsaiLiveE2EResult:
    return _run_bonsai_requests(
        config,
        source_inputs=(BONSAI_DIAGNOSTIC_INPUT, BONSAI_DIAGNOSTIC_INPUT),
    )
