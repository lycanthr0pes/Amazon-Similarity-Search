"""Real local processes, with a synthetic listener and no model or provider data."""

from pathlib import Path
import os
import select
import signal
import socket
import subprocess
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import bonsai_live_e2e as runtime


pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux process ownership")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def listener(tmp_path):
    binary = tmp_path / "listener"
    binary.write_text(
        f"#!{sys.executable}\n"
        "import http.server, signal, sys\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "class Handler(http.server.BaseHTTPRequestHandler):\n"
        " def do_GET(self):\n"
        "  self.send_response(200); self.end_headers()\n"
        " def log_message(self, *args): pass\n"
        "port = int(sys.argv[sys.argv.index('--port') + 1])\n"
        "http.server.HTTPServer(('127.0.0.1', port), Handler).serve_forever()\n"
    )
    binary.chmod(0o700)
    model = tmp_path / "fixture.gguf"
    model.write_bytes(b"not a model")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    return runtime.BonsaiLiveE2EConfig(binary, model, port)


def process_state(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return ("dead" if fields[0] == "Z" else "alive", fields[19])
    except FileNotFoundError:
        return ("dead", None)


def owner_process(config):
    source = (
        "import os, sys, time\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "from pathlib import Path\n"
        "from concurrent.futures import ThreadPoolExecutor\n"
        "from tools import bonsai_live_e2e as r\n"
        f"c = r.BonsaiLiveE2EConfig(Path({str(config.server_binary)!r}), "
        f"Path({str(config.model_path)!r}), {config.port})\n"
        "def own():\n"
        " p = r._launch_server(c)\n"
        " r._wait_until_ready(p, c.port)\n"
        " print(p.pid, flush=True)\n"
        " time.sleep(60)\n"
        "with ThreadPoolExecutor(max_workers=1) as worker:\n"
        " worker.submit(own)\n"
        " if sys.stdin.readline().strip() == 'exit': os._exit(0)\n"
        " time.sleep(60)\n"
    )
    owner = subprocess.Popen(
        [sys.executable, "-I", "-c", source],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env={"LC_ALL": "C"},
    )
    assert select.select([owner.stdout], [], [], 10)[0], "fixture owner not ready"
    child_pid = int(owner.stdout.readline())
    return owner, child_pid


@pytest.mark.parametrize("exit_mode", ["terminate", "kill", "exit"])
def test_parent_exit_releases_model_and_allows_restart(listener, monkeypatch, exit_mode):
    monkeypatch.setattr(runtime, "BONSAI_E2E_STOP_DEADLINE_SECONDS", 0.1)
    owner, child_pid = owner_process(listener)
    identity = process_state(child_pid)[1]
    try:
        if exit_mode == "exit":
            owner.stdin.write(b"exit\n")
            owner.stdin.flush()
        else:
            getattr(owner, exit_mode)()
        owner.wait(timeout=5)
        deadline = time.monotonic() + 5
        while process_state(child_pid) == ("alive", identity) and time.monotonic() < deadline:
            time.sleep(0.02)
        assert process_state(child_pid) != ("alive", identity), "Bonsai survived its owner"
        assert not runtime._port_is_listening(listener.port)
        child = runtime._launch_server(listener)
        try:
            runtime._wait_until_ready(child, listener.port)
        finally:
            runtime._stop_server(child, listener.port)
        assert not runtime._port_is_listening(listener.port)
    finally:
        if owner.poll() is None:
            owner.kill()
            owner.wait(timeout=5)
        if process_state(child_pid) == ("alive", identity):
            os.kill(child_pid, signal.SIGKILL)
        owner.stdin.close()
        owner.stdout.close()


def test_second_launch_is_rejected_even_before_first_listener_is_ready(listener, monkeypatch):
    monkeypatch.setattr(runtime, "BONSAI_E2E_STOP_DEADLINE_SECONDS", 0.1)
    first = runtime._launch_server(listener)
    second = None
    try:
        with monkeypatch.context() as patch:
            patch.setattr(runtime, "_port_is_listening", lambda _: False)
            try:
                second = runtime._launch_server(listener)
            except runtime.BonsaiLiveE2EError as error:
                assert type(error).__name__ == "BonsaiPortBusyError"
            else:
                pytest.fail("second model was started while first owned the port")
        runtime._wait_until_ready(first, listener.port)
    finally:
        if second is not None:
            second.kill()
            second.wait(timeout=5)
        runtime._stop_server(first, listener.port)


def test_foreign_listener_is_left_alive(listener):
    with socket.socket() as foreign:
        foreign.bind(("127.0.0.1", listener.port))
        foreign.listen()
        with pytest.raises(runtime.BonsaiLiveE2EError) as failure:
            runtime._launch_server(listener)
        assert type(failure.value).__name__ == "BonsaiPortBusyError"
        assert runtime._port_is_listening(listener.port)


def test_normal_cleanup_escalates_and_releases_lease(listener, monkeypatch):
    monkeypatch.setattr(runtime, "BONSAI_E2E_STOP_DEADLINE_SECONDS", 0.1)
    for _ in range(2):
        child = runtime._launch_server(listener)
        try:
            runtime._wait_until_ready(child, listener.port)
        finally:
            runtime._stop_server(child, listener.port)
        assert child.poll() == -signal.SIGKILL
        assert not runtime._port_is_listening(listener.port)


def test_failed_exec_releases_lease(listener, monkeypatch):
    monkeypatch.setattr(runtime, "BONSAI_E2E_STOP_DEADLINE_SECONDS", 0.1)
    original = listener.server_binary.read_bytes()
    listener.server_binary.write_bytes(b"not an executable")
    child = runtime._launch_server(listener)
    try:
        with pytest.raises(runtime.BonsaiLiveE2EError, match="did not become ready"):
            runtime._wait_until_ready(child, listener.port)
    finally:
        runtime._stop_server(child, listener.port)
    listener.server_binary.write_bytes(original)
    test_normal_cleanup_escalates_and_releases_lease(listener, monkeypatch)


def test_failed_spawn_releases_lease(listener, monkeypatch):
    with monkeypatch.context() as patch:

        def fail(*_, **__):
            raise OSError("synthetic spawn error")

        patch.setattr(runtime.subprocess, "Popen", fail)
        with pytest.raises(runtime.BonsaiLiveE2EError, match="did not become ready"):
            runtime._launch_server(listener)
    test_normal_cleanup_escalates_and_releases_lease(listener, monkeypatch)


if __name__ == "__main__":
    from tempfile import TemporaryDirectory

    with TemporaryDirectory(prefix="bonsai-lifecycle-") as temporary:
        config = listener.__wrapped__(Path(temporary))
        with pytest.MonkeyPatch.context() as patch:
            case = sys.argv[1]
            if case in {"terminate", "kill", "exit"}:
                test_parent_exit_releases_model_and_allows_restart(config, patch, case)
            elif case == "concurrent":
                test_second_launch_is_rejected_even_before_first_listener_is_ready(config, patch)
            elif case == "foreign":
                test_foreign_listener_is_left_alive(config)
            elif case == "cleanup":
                test_normal_cleanup_escalates_and_releases_lease(config, patch)
            elif case == "exec_failure":
                test_failed_exec_releases_lease(config, patch)
            elif case == "spawn_failure":
                test_failed_spawn_releases_lease(config, patch)
            else:
                raise AssertionError("unknown synthetic case")
