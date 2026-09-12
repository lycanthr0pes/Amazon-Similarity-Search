"""History mutations stay owner-scoped, idempotent, and separate from search."""

import json
import sqlite3
from datetime import timedelta
from types import SimpleNamespace
import pytest
from tests.test_browser_history import saved
from tests.test_browser_server import request
from tests.test_search_v2_provisional_history_repository import NOW
from src.search_v2.browser_history import BrowserHistory
from tools.browser_search_server import make_server


def counts(path):
    with sqlite3.connect(path) as db:
        return tuple(
            db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("provisional_history", "provisional_history_images")
        )


def api(tmp_path, monkeypatch, history):
    (tmp_path / "index.html").write_text("fixture")
    monkeypatch.setattr(
        "tools.browser_search_server.HTTPServer",
        lambda a, h: SimpleNamespace(server_port=8765, handler=h),
    )
    return make_server(
        SimpleNamespace(snapshot=lambda: {"stage": "working", "revision": 3}),
        tmp_path,
        history=history,
    )


def post(server, command, **headers):
    return request(
        server,
        "POST",
        "/api/history/command",
        json.dumps(command),
        **{
            "Origin": "http://127.0.0.1:8765",
            "Content-Type": "application/json",
            "X-Amazon-Explorer-Browser": "1",
            **headers,
        },
    )


def test_delete_confirmation_cascade_and_retry(tmp_path, monkeypatch):
    path = tmp_path / "history.sqlite3"
    detail = saved(path)
    server = api(tmp_path, monkeypatch, BrowserHistory([path], now=lambda: NOW))
    command = {"action": "delete", "id": detail.locator, "confirmed": True}
    assert post(server, {**command, "confirmed": False})[0] == 400
    assert counts(path) == (1, 2)
    assert post(server, command, Origin="https://example.com")[0] == 403
    assert post(server, command)[0] == 200
    assert counts(path) == (0, 0)
    assert post(server, command)[0] == 200
    assert request(server, "GET", "/api/history/" + detail.locator)[0] == 404
    assert json.loads(request(server, "GET", "/api/state")[2]) == {
        "stage": "working",
        "revision": 3,
    }


def test_expiry_cleanup_preserves_other_owners_and_future_files(tmp_path):
    path = tmp_path / "expired.sqlite3"
    saved(path)
    other = tmp_path / "other.sqlite3"
    saved(other, owner="someone-else")
    live = tmp_path / "live.sqlite3"
    saved(live, completed=NOW + timedelta(seconds=1))
    missing = tmp_path / "missing.sqlite3"
    history = BrowserHistory([path, other, live, missing], now=lambda: NOW + timedelta(days=30))
    assert history.purge_expired() == 1
    assert counts(path) == (0, 0) and counts(other) == (1, 2) and counts(live) == (1, 2)
    assert history.purge_expired() == 0 and not missing.exists()


def test_foreign_owner_and_unknown_locator_are_not_deleted(tmp_path):
    path = tmp_path / "other.sqlite3"
    detail = saved(path, owner="someone-else")
    history = BrowserHistory([path], now=lambda: NOW)
    history.delete(detail.locator)
    history.delete("x" * 43)
    assert counts(path) == (1, 2)
    with pytest.raises(ValueError):
        history.delete("../other.sqlite3")


def test_cascade_failure_rolls_back_and_retry_uses_same_locator(tmp_path):
    from src.search_v2.provisional_history_repository import ProvisionalHistoryStorageError

    path = tmp_path / "history.sqlite3"
    detail = saved(path)
    history = BrowserHistory([path], now=lambda: NOW)
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TRIGGER fail_image_delete BEFORE DELETE ON provisional_history_images BEGIN SELECT RAISE(ABORT, 'fixture'); END"
        )
    with pytest.raises(ProvisionalHistoryStorageError):
        history.delete(detail.locator)
    assert counts(path) == (1, 2)
    with sqlite3.connect(path) as db:
        db.execute("DROP TRIGGER fail_image_delete")
    history.delete(detail.locator)
    assert counts(path) == (0, 0)


def test_cleanup_tick_retries_failed_store_and_keeps_get_read_only(tmp_path, monkeypatch):
    from src.search_v2.provisional_history_repository import ProvisionalHistoryStorageError

    path = tmp_path / "history.sqlite3"
    saved(path)
    history = BrowserHistory([path], now=lambda: NOW + timedelta(days=30))
    server = api(tmp_path, monkeypatch, history)
    tick = [0.0]
    monkeypatch.setattr("tools.browser_search_server.time.monotonic", lambda: tick[0])
    cleanup = history.purge_expired
    calls = []

    def attempt():
        calls.append(True)
        if len(calls) == 1:
            history._cleanup_failed = True
            raise ProvisionalHistoryStorageError("fixture")
        return cleanup()

    monkeypatch.setattr(history, "purge_expired", attempt)
    assert json.loads(request(server, "GET", "/api/history")[2]) == {"items": []}
    assert counts(path) == (1, 2)
    server.service_actions()
    assert counts(path) == (1, 2)
    assert json.loads(request(server, "GET", "/api/history")[2])["cleanupPending"] is True
    tick[0] = 59.9
    server.service_actions()
    assert len(calls) == 1
    tick[0] = 60.0
    server.service_actions()
    assert len(calls) == 2 and counts(path) == (0, 0)
    assert json.loads(request(server, "GET", "/api/history")[2]) == {"items": []}


def test_existing_writer_refuses_creation_and_legacy_schema(tmp_path):
    from src.search_v2.provisional_history_repository import (
        SqliteProvisionalHistoryRepository,
        ProvisionalHistoryStorageError,
    )

    path = tmp_path / "missing" / "history.sqlite3"
    with pytest.raises(ProvisionalHistoryStorageError):
        SqliteProvisionalHistoryRepository(path, existing_only=True)
    assert not path.parent.exists()
    old = tmp_path / "old.sqlite3"
    with sqlite3.connect(old):
        pass
    old.chmod(0o600)
    before = old.read_bytes()
    with pytest.raises(ProvisionalHistoryStorageError):
        SqliteProvisionalHistoryRepository(old, existing_only=True)
    assert old.read_bytes() == before


def test_cleanup_rejects_symlink_and_continues_other_databases(tmp_path):
    from src.search_v2.provisional_history_repository import ProvisionalHistoryStorageError

    target = tmp_path / "target.sqlite3"
    saved(target)
    link = tmp_path / "link.sqlite3"
    link.symlink_to(target)
    valid = tmp_path / "valid.sqlite3"
    saved(valid)
    history = BrowserHistory([link, valid], now=lambda: NOW + timedelta(days=31))
    with pytest.raises(ProvisionalHistoryStorageError):
        history.purge_expired()
    assert counts(target) == (1, 2) and counts(valid) == (0, 0)


def test_cleanup_api_does_not_accept_client_cutoff_or_owner(tmp_path, monkeypatch):
    path = tmp_path / "history.sqlite3"
    saved(path)
    server = api(
        tmp_path, monkeypatch, BrowserHistory([path], now=lambda: NOW + timedelta(days=30))
    )
    for extra in ({"owner_id": "someone-else"}, {"now": "2099-01-01"}, {"path": str(path)}):
        assert post(server, {"action": "purge_expired", **extra})[0] == 400
    assert counts(path) == (1, 2)
    assert json.loads(post(server, {"action": "purge_expired"})[2]) == {"deletedCount": 1}
    assert json.loads(post(server, {"action": "purge_expired"})[2]) == {"deletedCount": 0}


def test_deleting_one_item_preserves_another_in_the_same_store(tmp_path):
    from tests.test_search_v2_provisional_history_repository import pending
    from src.search_v2.provisional_history_repository import SqliteProvisionalHistoryRepository

    path = tmp_path / "history.sqlite3"
    first = saved(path)
    repo = SqliteProvisionalHistoryRepository(path)
    second = repo.save(
        pending().model_copy(update={"owner_id": "local-user", "completion_key": "f" * 64}), now=NOW
    )
    BrowserHistory([path], now=lambda: NOW).delete(first.locator)
    assert counts(path) == (1, 2)
    assert repo.get(owner_id="local-user", locator=second.locator, now=NOW) == second


def test_cleanup_without_expired_rows_preserves_database_bytes(tmp_path):
    path = tmp_path / "history.sqlite3"
    saved(path)
    before = path.read_bytes()
    assert BrowserHistory([path], now=lambda: NOW).purge_expired() == 0
    assert path.read_bytes() == before
