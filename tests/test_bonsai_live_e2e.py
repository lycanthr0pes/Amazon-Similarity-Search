from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import conftest as pytest_policy
import tools.bonsai_live_e2e as live_e2e
from tools.bonsai_live_e2e import BONSAI_E2E_CONTEXT_SIZE
from tools.bonsai_live_e2e import BONSAI_E2E_PARALLEL_SLOTS
from tools.bonsai_live_e2e import BONSAI_E2E_REQUEST_COUNT
from tools.bonsai_live_e2e import SYNTHETIC_INPUTS
from tools.bonsai_live_e2e import BonsaiLiveE2EConfig
from tools.bonsai_live_e2e import BonsaiLiveE2EError
from tools.bonsai_live_e2e import build_llama_server_command
from tools.bonsai_live_e2e import project_prompt_usage
from tools.bonsai_live_e2e import run_bonsai_live_e2e


def local_files(tmp_path: Path) -> tuple[Path, Path]:
    server_binary = tmp_path / "llama-server"
    server_binary.write_bytes(b"fixture executable")
    server_binary.chmod(0o700)
    model_path = tmp_path / "Bonsai-8B.gguf"
    model_path.write_bytes(b"fixture model")
    return server_binary, model_path


def valid_response_metrics_bytes(*, cached_tokens: int = 891) -> bytes:
    return json.dumps(
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": "private fixture"},
                }
            ],
            "timings": {
                "cache_n": cached_tokens,
                "predicted_ms": 4567.75,
                "predicted_n": 321,
                "prompt_ms": 123.5,
                "prompt_n": 925 - cached_tokens,
            },
            "usage": {
                "completion_tokens": 321,
                "prompt_tokens": 925,
                "prompt_tokens_details": {"cached_tokens": cached_tokens},
                "total_tokens": 1246,
            },
        },
        separators=(",", ":"),
    ).encode()


def fake_response_metrics(*, cached_tokens: int) -> SimpleNamespace:
    return SimpleNamespace(
        prompt_usage=live_e2e.BonsaiPromptUsage(
            prompt_tokens=925,
            cached_tokens=cached_tokens,
        ),
        completion_tokens=321,
        finish_reason="stop",
        predicted_milliseconds=4567.75,
        predicted_tokens=321,
        prompt_milliseconds=123.5,
        prompt_tokens_processed=925 - cached_tokens,
        response_bytes=4096,
    )


def test_server_command_fixes_production_cache_context_and_loopback(tmp_path: Path) -> None:
    server_binary, model_path = local_files(tmp_path)
    config = BonsaiLiveE2EConfig(
        server_binary=server_binary,
        model_path=model_path,
        port=18080,
    )

    command = build_llama_server_command(config)

    assert command == (
        str(server_binary),
        "-m",
        str(model_path),
        "-c",
        str(BONSAI_E2E_CONTEXT_SIZE),
        "-np",
        str(BONSAI_E2E_PARALLEL_SLOTS),
        "--cache-prompt",
        "--host",
        "127.0.0.1",
        "--port",
        "18080",
        "--log-disable",
    )
    assert "--slot-save-path" not in command


@pytest.mark.parametrize("port", [0, 80, 65536, True])
def test_config_rejects_unsafe_port(tmp_path: Path, port: object) -> None:
    server_binary, model_path = local_files(tmp_path)

    with pytest.raises(BonsaiLiveE2EError, match="^Bonsai E2E configuration is invalid$"):
        BonsaiLiveE2EConfig(
            server_binary=server_binary,
            model_path=model_path,
            port=port,  # type: ignore[arg-type]
        )


def test_config_requires_absolute_regular_executable_and_model(tmp_path: Path) -> None:
    server_binary, model_path = local_files(tmp_path)
    relative_server = Path(server_binary.name)

    with pytest.raises(BonsaiLiveE2EError, match="^Bonsai E2E configuration is invalid$"):
        BonsaiLiveE2EConfig(
            server_binary=relative_server,
            model_path=model_path,
            port=18080,
        )

    model_link = tmp_path / "linked.gguf"
    model_link.symlink_to(model_path)
    with pytest.raises(BonsaiLiveE2EError, match="^Bonsai E2E configuration is invalid$"):
        BonsaiLiveE2EConfig(
            server_binary=server_binary,
            model_path=model_link,
            port=18080,
        )


def test_prompt_usage_projection_keeps_only_bounded_counts() -> None:
    response = json.dumps(
        {
            "choices": [{"message": {"content": "private fixture"}}],
            "usage": {
                "prompt_tokens": 913,
                "prompt_tokens_details": {"cached_tokens": 895},
            },
        },
        separators=(",", ":"),
    ).encode()

    usage = project_prompt_usage(response)

    assert usage.prompt_tokens == 913
    assert usage.cached_tokens == 895
    assert "private fixture" not in repr(usage)


@pytest.mark.parametrize(
    "response",
    [
        b"{}",
        b'{"usage":{"prompt_tokens":1}}',
        b'{"usage":{"prompt_tokens":1,"prompt_tokens_details":{"cached_tokens":-1}}}',
        b'{"usage":{"prompt_tokens":1,"prompt_tokens_details":{"cached_tokens":2}}}',
        b'{"usage":{"prompt_tokens":true,"prompt_tokens_details":{"cached_tokens":0}}}',
    ],
)
def test_prompt_usage_projection_rejects_invalid_metadata(response: bytes) -> None:
    with pytest.raises(BonsaiLiveE2EError, match="^Bonsai E2E response metadata is invalid$"):
        project_prompt_usage(response)


def test_response_metrics_projection_keeps_only_bounded_timing_data() -> None:
    projector = getattr(live_e2e, "project_response_metrics", None)
    assert callable(projector), "response timing projector is required"

    metrics = projector(valid_response_metrics_bytes())

    assert metrics.prompt_usage.prompt_tokens == 925
    assert metrics.prompt_usage.cached_tokens == 891
    assert metrics.prompt_tokens_processed == 34
    assert metrics.prompt_milliseconds == 123.5
    assert metrics.completion_tokens == 321
    assert metrics.predicted_tokens == 321
    assert metrics.predicted_milliseconds == 4567.75
    assert metrics.finish_reason == "stop"
    assert metrics.response_bytes == len(valid_response_metrics_bytes())
    assert "private fixture" not in repr(metrics)


@pytest.mark.parametrize(
    "response",
    [
        b"{}",
        b'{"choices":[{"finish_reason":"unknown"}],"timings":{},"usage":{}}',
        b'{"choices":[{"finish_reason":"stop"}],"timings":{"cache_n":0,"prompt_n":1,"prompt_ms":1,"predicted_n":1,"predicted_ms":1},"usage":{"completion_tokens":true,"prompt_tokens":1,"total_tokens":2,"prompt_tokens_details":{"cached_tokens":0}}}',
        b'{"choices":[{"finish_reason":"stop"}],"timings":{"cache_n":1,"prompt_n":1,"prompt_ms":1,"predicted_n":1,"predicted_ms":1},"usage":{"completion_tokens":1,"prompt_tokens":1,"total_tokens":2,"prompt_tokens_details":{"cached_tokens":1}}}',
        b'{"choices":[{"finish_reason":"stop"}],"timings":{"cache_n":0,"prompt_n":1,"prompt_ms":1,"predicted_n":2,"predicted_ms":1},"usage":{"completion_tokens":1,"prompt_tokens":1,"total_tokens":2,"prompt_tokens_details":{"cached_tokens":0}}}',
        b'{"choices":[{"finish_reason":"stop"}],"timings":{"cache_n":0,"prompt_n":1,"prompt_ms":1,"predicted_n":1,"predicted_ms":NaN},"usage":{"completion_tokens":1,"prompt_tokens":1,"total_tokens":2,"prompt_tokens_details":{"cached_tokens":0}}}',
        b'{"choices":[{"finish_reason":"stop"},{"finish_reason":"stop"}],"timings":{"cache_n":0,"prompt_n":1,"prompt_ms":1,"predicted_n":1,"predicted_ms":1},"usage":{"completion_tokens":1,"prompt_tokens":1,"total_tokens":2,"prompt_tokens_details":{"cached_tokens":0}}}',
        b'{"choices":[{"finish_reason":"stop"}],"timings":{"cache_n":0,"prompt_n":1,"prompt_ms":1,"predicted_n":1,"predicted_ms":1},"usage":{"completion_tokens":1,"completion_tokens":1,"prompt_tokens":1,"total_tokens":2,"prompt_tokens_details":{"cached_tokens":0}}}',
    ],
)
def test_response_metrics_projection_rejects_invalid_metadata(response: bytes) -> None:
    projector = getattr(live_e2e, "project_response_metrics", None)
    assert callable(projector), "response timing projector is required"

    with pytest.raises(BonsaiLiveE2EError, match="^Bonsai E2E response metadata is invalid$"):
        projector(response)


def test_live_inputs_are_two_distinct_non_secret_fixtures() -> None:
    assert BONSAI_E2E_REQUEST_COUNT == 2
    assert len(SYNTHETIC_INPUTS) == BONSAI_E2E_REQUEST_COUNT
    assert len(set(SYNTHETIC_INPUTS)) == BONSAI_E2E_REQUEST_COUNT
    assert all(0 < len(value) <= 2000 for value in SYNTHETIC_INPUTS)


def test_runner_executes_two_v9_requests_and_cleans_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server_binary, model_path = local_files(tmp_path)
    config = BonsaiLiveE2EConfig(
        server_binary=server_binary,
        model_path=model_path,
        port=18080,
    )
    process = SimpleNamespace()
    executed: list[str] = []
    stopped: list[tuple[object, int]] = []

    monkeypatch.setattr(live_e2e, "_launch_server", lambda selected: process)
    monkeypatch.setattr(live_e2e, "_wait_until_ready", lambda selected, port: None)
    monkeypatch.setattr(
        live_e2e,
        "_stop_server",
        lambda selected, port: stopped.append((selected, port)),
    )

    def execute(prepared, *, ledger):
        del ledger
        executed.append(prepared.request.schema_version)
        cached_tokens = 0 if len(executed) == 1 else 895
        return (
            SimpleNamespace(request=prepared.request),
            fake_response_metrics(cached_tokens=cached_tokens),
            10,
        )

    monkeypatch.setattr(live_e2e, "_execute_request", execute)

    result = run_bonsai_live_e2e(config)

    assert executed == ["9.0", "9.0"]
    assert result.request_count == BONSAI_E2E_REQUEST_COUNT
    assert result.server_stopped is True
    assert stopped == [(process, 18080)]


def test_latency_diagnostic_repeats_one_v9_request_and_cleans_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = getattr(live_e2e, "run_bonsai_latency_diagnostic", None)
    diagnostic_input = getattr(live_e2e, "BONSAI_DIAGNOSTIC_INPUT", None)
    assert callable(runner), "latency diagnostic runner is required"
    assert type(diagnostic_input) is str and diagnostic_input
    server_binary, model_path = local_files(tmp_path)
    config = BonsaiLiveE2EConfig(
        server_binary=server_binary,
        model_path=model_path,
        port=18080,
    )
    process = SimpleNamespace()
    executed: list[tuple[str, str, str]] = []
    stopped: list[tuple[object, int]] = []

    monkeypatch.setattr(live_e2e, "_launch_server", lambda selected: process)
    monkeypatch.setattr(live_e2e, "_wait_until_ready", lambda selected, port: None)
    monkeypatch.setattr(
        live_e2e,
        "_stop_server",
        lambda selected, port: stopped.append((selected, port)),
    )

    def execute(prepared, *, ledger):
        del ledger
        executed.append(
            (
                prepared.request.schema_version,
                prepared.request.source_input_sha256,
                prepared.request.body_sha256,
            )
        )
        cached_tokens = 0 if len(executed) == 1 else 924
        return (
            SimpleNamespace(request=prepared.request),
            fake_response_metrics(cached_tokens=cached_tokens),
            10,
        )

    monkeypatch.setattr(live_e2e, "_execute_request", execute)

    result = runner(config)

    assert len(executed) == BONSAI_E2E_REQUEST_COUNT
    assert executed[0] == executed[1]
    assert result.schema_versions == ("9.0", "9.0")
    assert result.prompt_usages[0].cached_tokens == 0
    assert result.prompt_usages[1].cached_tokens == 924
    assert result.server_stopped is True
    assert diagnostic_input not in repr(result)
    assert stopped == [(process, 18080)]


@pytest.mark.parametrize(
    (
        "is_latency_diagnostic",
        "run_live_api",
        "run_bonsai_e2e",
        "run_latency_diagnostic",
        "expected",
    ),
    [
        (False, True, True, False, True),
        (True, True, True, False, False),
        (False, True, True, True, False),
        (True, True, True, True, True),
        (True, True, False, True, False),
        (True, False, True, True, False),
    ],
)
def test_bonsai_live_selector_runs_exactly_one_approved_mode(
    is_latency_diagnostic: bool,
    run_live_api: bool,
    run_bonsai_e2e: bool,
    run_latency_diagnostic: bool,
    expected: bool,
) -> None:
    selector = getattr(pytest_policy, "bonsai_live_test_enabled", None)
    assert callable(selector), "Bonsai live test selector is required"

    assert (
        selector(
            is_latency_diagnostic=is_latency_diagnostic,
            run_live_api=run_live_api,
            run_bonsai_e2e=run_bonsai_e2e,
            run_latency_diagnostic=run_latency_diagnostic,
        )
        is expected
    )


def test_runner_cleans_up_after_request_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server_binary, model_path = local_files(tmp_path)
    config = BonsaiLiveE2EConfig(
        server_binary=server_binary,
        model_path=model_path,
        port=18080,
    )
    process = SimpleNamespace()
    stopped: list[tuple[object, int]] = []

    monkeypatch.setattr(live_e2e, "_launch_server", lambda selected: process)
    monkeypatch.setattr(live_e2e, "_wait_until_ready", lambda selected, port: None)
    monkeypatch.setattr(
        live_e2e,
        "_stop_server",
        lambda selected, port: stopped.append((selected, port)),
    )
    monkeypatch.setattr(
        live_e2e,
        "_execute_request",
        lambda prepared, *, ledger: (_ for _ in ()).throw(BonsaiLiveE2EError("failure")),
    )

    with pytest.raises(BonsaiLiveE2EError, match="^failure$"):
        run_bonsai_live_e2e(config)

    assert stopped == [(process, 18080)]


def test_runner_stops_before_request_after_run_deadline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server_binary, model_path = local_files(tmp_path)
    config = BonsaiLiveE2EConfig(
        server_binary=server_binary,
        model_path=model_path,
        port=18080,
    )
    terminations: list[bool] = []
    process = SimpleNamespace(
        poll=lambda: None,
        terminate=lambda: terminations.append(True),
    )
    stopped: list[tuple[object, int]] = []
    executions: list[bool] = []

    class ImmediateTimer:
        def __init__(self, interval: int, function) -> None:
            assert interval == live_e2e.BONSAI_E2E_RUN_DEADLINE_SECONDS
            self.function = function

        def start(self) -> None:
            self.function()

        def cancel(self) -> None:
            return None

    monkeypatch.setattr(live_e2e, "_launch_server", lambda selected: process)
    monkeypatch.setattr(live_e2e, "_wait_until_ready", lambda selected, port: None)
    monkeypatch.setattr(
        live_e2e,
        "_stop_server",
        lambda selected, port: stopped.append((selected, port)),
    )
    monkeypatch.setattr(live_e2e.threading, "Timer", ImmediateTimer)
    monkeypatch.setattr(
        live_e2e,
        "_execute_request",
        lambda prepared, *, ledger: executions.append(True),
    )

    with pytest.raises(BonsaiLiveE2EError, match="^Bonsai E2E run deadline was reached$"):
        run_bonsai_live_e2e(config)

    assert executions == []
    assert terminations == [True]
    assert stopped == [(process, 18080)]


@pytest.mark.live_api
@pytest.mark.bonsai_e2e
def test_request_v8_reuses_prompt_cache_with_local_bonsai(pytestconfig: pytest.Config) -> None:
    server_binary = pytestconfig.getoption("--bonsai-server-bin")
    model_path = pytestconfig.getoption("--bonsai-model-path")
    if not isinstance(server_binary, str) or not isinstance(model_path, str):
        pytest.fail("Bonsai E2E requires explicit server and model paths", pytrace=False)

    result = run_bonsai_live_e2e(
        BonsaiLiveE2EConfig(
            server_binary=Path(server_binary),
            model_path=Path(model_path),
            port=pytestconfig.getoption("--bonsai-e2e-port"),
        )
    )

    assert result.request_count == BONSAI_E2E_REQUEST_COUNT
    assert result.schema_versions == ("9.0", "9.0")
    assert result.prompt_usages[0].cached_tokens == 0
    assert result.prompt_usages[1].cached_tokens > 0
    assert all(item.completion_tokens > 0 for item in result.response_metrics)
    assert all(item.predicted_milliseconds > 0 for item in result.response_metrics)
    assert all(item.prompt_milliseconds > 0 for item in result.response_metrics)
    assert result.server_stopped is True
    assert all(duration > 0 for duration in result.wall_milliseconds)
    assert all(source not in repr(result) for source in SYNTHETIC_INPUTS)
    print(
        json.dumps(
            {
                "cached_tokens": [item.cached_tokens for item in result.prompt_usages],
                "prompt_tokens": [item.prompt_tokens for item in result.prompt_usages],
                "request_count": result.request_count,
                "schema_versions": result.schema_versions,
                "server_stopped": result.server_stopped,
                "wall_milliseconds": result.wall_milliseconds,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


@pytest.mark.live_api
@pytest.mark.bonsai_e2e
@pytest.mark.bonsai_latency_diagnostic
def test_same_request_separates_prompt_and_generation_time(
    pytestconfig: pytest.Config,
) -> None:
    server_binary = pytestconfig.getoption("--bonsai-server-bin")
    model_path = pytestconfig.getoption("--bonsai-model-path")
    if not isinstance(server_binary, str) or not isinstance(model_path, str):
        pytest.fail("Bonsai E2E requires explicit server and model paths", pytrace=False)
    runner = getattr(live_e2e, "run_bonsai_latency_diagnostic", None)
    assert callable(runner), "latency diagnostic runner is required"

    result = runner(
        BonsaiLiveE2EConfig(
            server_binary=Path(server_binary),
            model_path=Path(model_path),
            port=pytestconfig.getoption("--bonsai-e2e-port"),
        )
    )

    assert result.request_count == BONSAI_E2E_REQUEST_COUNT
    assert result.schema_versions == ("9.0", "9.0")
    assert result.prompt_usages[0].cached_tokens == 0
    assert result.prompt_usages[1].cached_tokens > 0
    assert result.prompt_usages[0].prompt_tokens == result.prompt_usages[1].prompt_tokens
    assert all(item.completion_tokens > 0 for item in result.response_metrics)
    assert all(item.predicted_milliseconds > 0 for item in result.response_metrics)
    assert all(item.prompt_milliseconds > 0 for item in result.response_metrics)
    assert result.server_stopped is True
    assert all(duration > 0 for duration in result.wall_milliseconds)
    assert live_e2e.BONSAI_DIAGNOSTIC_INPUT not in repr(result)
    print(
        json.dumps(
            {
                "cached_tokens": [item.cached_tokens for item in result.prompt_usages],
                "completion_tokens": [item.completion_tokens for item in result.response_metrics],
                "finish_reasons": [item.finish_reason for item in result.response_metrics],
                "predicted_milliseconds": [
                    item.predicted_milliseconds for item in result.response_metrics
                ],
                "predicted_tokens": [item.predicted_tokens for item in result.response_metrics],
                "prompt_milliseconds": [
                    item.prompt_milliseconds for item in result.response_metrics
                ],
                "prompt_tokens": [item.prompt_tokens for item in result.prompt_usages],
                "prompt_tokens_processed": [
                    item.prompt_tokens_processed for item in result.response_metrics
                ],
                "request_count": result.request_count,
                "response_bytes": [item.response_bytes for item in result.response_metrics],
                "schema_versions": result.schema_versions,
                "server_stopped": result.server_stopped,
                "wall_milliseconds": result.wall_milliseconds,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def test_latency_diagnostic_has_dedicated_marker() -> None:
    marker_names = {
        marker.name
        for marker in getattr(
            test_same_request_separates_prompt_and_generation_time,
            "pytestmark",
            (),
        )
    }

    assert {"live_api", "bonsai_e2e", "bonsai_latency_diagnostic"} <= marker_names
