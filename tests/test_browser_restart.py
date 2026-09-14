"""Restart recovery uses synthetic preparation boundaries, never a provider."""

from types import SimpleNamespace

import pytest

from src.search_v2.browser_search import BrowserCommandError, BrowserSearch


class ImmediateWorker:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def submit(self, fn, *args):
        result = fn(*args)
        return SimpleNamespace(result=lambda: result)


def test_restart_with_same_output_reaches_preparation(tmp_path, monkeypatch):
    from tools import browser_search_server as server

    root = tmp_path / "run"
    root.mkdir(mode=0o700)
    marker = root / "history-marker"
    marker.write_bytes(b"existing history")
    boundaries, paths = [], []

    def model_boundary(*_):
        directories = {p for p in root.rglob("*") if p.is_dir()}
        boundaries.append(directories)
        raise RuntimeError("synthetic preparation boundary")

    def make_server(controller, *_, history, **__):
        paths.append(history.paths)

        def serve():
            controller.submit(
                {
                    "action": "start",
                    "revision": 0,
                    "operation": "restart-fixture-001",
                    "source": "マグカップ。丸みのある形。",
                }
            )
            raise KeyboardInterrupt

        return SimpleNamespace(server_port=8772, serve_forever=serve, server_close=lambda: None)

    monkeypatch.setattr(server, "ThreadPoolExecutor", lambda **_: ImmediateWorker())
    monkeypatch.setattr(server, "make_server", make_server)
    monkeypatch.setattr("tools.browser_search_runtime.MODEL", SimpleNamespace(open=model_boundary))
    monkeypatch.setattr(
        "sys.argv", ["browser_search_server", "--run-live-api", "--output-dir", str(root)]
    )
    for _ in range(2):
        server.main()
    assert len(boundaries) == 2
    assert boundaries[1] - boundaries[0]
    assert all(p.stat().st_mode & 0o777 == 0o700 for p in boundaries[1])
    assert paths[0] == paths[1]
    assert root / "history.sqlite3" in paths[0]
    assert marker.read_bytes() == b"existing history"


def test_instance_identity_survives_actions_but_changes_on_restart():
    first = BrowserSearch(lambda *_: {"stage": "query"}, ImmediateWorker())
    second = BrowserSearch(lambda *_: {"stage": "query"}, ImmediateWorker())
    identity = first.snapshot().get("instanceId")
    assert identity is not None
    assert second.snapshot()["instanceId"] != identity
    first.submit({"action": "start", "revision": 0, "operation": "instance-fixture-001"})
    assert first.snapshot()["instanceId"] == identity


def test_old_instance_command_is_rejected_even_at_same_revision():
    calls = []
    current = BrowserSearch(lambda *_: calls.append(True) or {"stage": "query"}, ImmediateWorker())
    identity = current.snapshot().get("instanceId")
    assert identity is not None
    command = {
        "action": "start",
        "revision": 0,
        "operation": "instance-fixture-001",
        "instanceId": "0" * 32,
    }
    with pytest.raises(BrowserCommandError):
        current.submit(command)
    assert not calls
    current.submit({**command, "instanceId": identity})
    assert calls == [True]


@pytest.mark.parametrize("case", ["invalid_id", "public_root", "symlink", "existing"])
def test_restart_namespace_preserves_private_boundaries(tmp_path, monkeypatch, case):
    from tools import browser_search_runtime as runtime

    root = tmp_path / "run"
    run_id = "c" * 32
    root.mkdir(mode=0o755 if case == "public_root" else 0o700)
    session = root / f"session-{run_id}"
    if case == "invalid_id":
        run_id = "../outside"
    elif case == "symlink":
        outside = tmp_path / "outside"
        outside.mkdir(mode=0o700)
        session.symlink_to(outside, target_is_directory=True)
    elif case == "existing":
        session.mkdir(mode=0o700)
        (session / "marker").write_bytes(b"preserve")
    monkeypatch.setattr(
        runtime, "MODEL", SimpleNamespace(open=lambda *_: pytest.fail("model accessed"))
    )
    with pytest.raises((ValueError, FileExistsError)):
        next(runtime.live_steps(root, run_id=run_id))
    if case == "existing":
        assert (session / "marker").read_bytes() == b"preserve"
    elif case == "symlink":
        assert list(outside.iterdir()) == []
    else:
        assert list(root.iterdir()) == []
