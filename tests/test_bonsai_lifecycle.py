"""Credential-free subprocess checks against synthetic loopback listeners only."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from tools import bonsai_live_e2e as runtime


@pytest.mark.skipif(sys.platform != "linux", reason="Linux process ownership")
@pytest.mark.parametrize(
    "case",
    [
        "terminate",
        "kill",
        "exit",
        "concurrent",
        "foreign",
        "cleanup",
        "exec_failure",
        "spawn_failure",
    ],
)
def test_owned_model_lifecycle(case):
    result = subprocess.run(
        [sys.executable, "-I", str(Path(__file__).with_name("bonsai_lifecycle_fixture.py")), case],
        env={"LC_ALL": "C"},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=35,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode()


def test_browser_reports_conflict_without_private_error_text(monkeypatch):
    from src.search_v2.browser_search import BrowserSearch
    from tools.browser_search_runtime import browser_bonsai

    def conflict(_):
        # The adapter must map the type, never display raw exception text.
        raise runtime.BonsaiPortBusyError("private fixture")

    monkeypatch.setattr(runtime, "_launch_server", conflict)

    def execute(*_):
        with browser_bonsai(None):
            pytest.fail("provider was reached")

    with ThreadPoolExecutor(max_workers=1) as worker:
        controller = BrowserSearch(execute, worker, initial={"editable": True})
        controller.submit(
            {"action": "start", "revision": 0, "operation": "conflict-test-01", "source": "合成"}
        )
    view = controller.snapshot()
    assert view["stage"] == "failed"
    assert "Bonsai" in view["message"] and "使用中" in view["message"]
    assert "private" not in json.dumps(view)
    assert view["canRevise"] is True


@pytest.mark.parametrize("parents", [(1,), (123, 1)])
def test_parent_exit_during_guard_setup_never_execs(monkeypatch, parents):
    from tools import bonsai_child

    observed = iter(parents)
    calls = []

    class Prctl:
        def __call__(self, *args):
            calls.append(args)
            return 0

    monkeypatch.setattr(bonsai_child.os, "getppid", lambda: next(observed))
    monkeypatch.setattr(
        bonsai_child.ctypes, "CDLL", lambda *_, **__: SimpleNamespace(prctl=Prctl())
    )
    monkeypatch.setattr(bonsai_child.os, "execv", lambda *_: pytest.fail("orphan was executed"))
    with pytest.raises(ValueError, match="owner"):
        bonsai_child._exec_owned(123, -1, ["/synthetic/model"])
    assert len(calls) == len(parents) - 1


def test_guard_setup_failure_never_execs(monkeypatch):
    from tools import bonsai_child

    class Prctl:
        def __call__(self, *_):
            return -1

    monkeypatch.setattr(bonsai_child.os, "getppid", lambda: 123)
    monkeypatch.setattr(
        bonsai_child.ctypes, "CDLL", lambda *_, **__: SimpleNamespace(prctl=Prctl())
    )
    monkeypatch.setattr(
        bonsai_child.os, "execv", lambda *_: pytest.fail("unguarded model executed")
    )
    with pytest.raises(OSError, match="Cannot bind"):
        bonsai_child._exec_owned(123, -1, ["/synthetic/model"])
