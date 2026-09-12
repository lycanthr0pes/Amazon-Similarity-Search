"""Persistent display history must not execute searches or mutate stored results."""

from datetime import timedelta
import hashlib
import json
import sqlite3
from types import SimpleNamespace

import pytest

from tests.test_browser_server import request, server  # noqa: F401
from tests.test_search_v2_provisional_history_repository import NOW, pending
from src.search_v2.provisional_history_repository import (
    SqliteProvisionalHistoryRepository,
    ProvisionalHistoryStorageError,
)


def test_history_route_is_read_only_and_empty_by_default(server):  # noqa: F811
    status, headers, body = request(server, "GET", "/api/history")
    assert status == 200
    assert json.loads(body) == {"items": []}
    assert headers["Cache-Control"] == "no-store"
    assert request(server, "GET", "/api/history", Host="example.com")[0] == 403
    assert request(server, "GET", "/api/history", **{"Sec-Fetch-Site": "cross-site"})[0] == 403


def saved(path, *, owner="local-user", completed=NOW):
    write = pending().model_copy(update={"owner_id": owner, "completed_at": completed})
    return SqliteProvisionalHistoryRepository(path).save(write, now=completed)


def test_read_only_repository_refuses_writes_and_creation(tmp_path):
    path = tmp_path / "saved.sqlite3"
    detail = saved(path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    repo = SqliteProvisionalHistoryRepository(path, read_only=True)
    assert repo.get(owner_id="local-user", locator=detail.locator, now=NOW) == detail
    with repo._connection() as db, pytest.raises(sqlite3.OperationalError):
        db.execute("DELETE FROM provisional_history")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    missing = tmp_path / "absent.sqlite3"
    with pytest.raises(ProvisionalHistoryStorageError):
        SqliteProvisionalHistoryRepository(missing, read_only=True)
    assert not missing.exists()


def test_history_reopens_only_configured_owner_and_keeps_database(tmp_path):
    from src.search_v2.browser_history import BrowserHistory

    paths = [tmp_path / f"history-{i}.sqlite3" for i in range(3)]
    old = saved(paths[0])
    new = saved(paths[1], completed=NOW + timedelta(seconds=2))
    saved(paths[2], owner="someone-else")
    before = [p.read_bytes() for p in paths]
    history = BrowserHistory(paths, now=lambda: NOW + timedelta(seconds=3))
    items = history.list()["items"]
    assert [i["id"] for i in items] == [new.locator, old.locator]
    assert set(items[0]) == {"id", "summary", "completedAt", "expiresAt", "count"}
    reopened = BrowserHistory(paths, now=lambda: NOW + timedelta(seconds=3))
    detail = reopened.get(new.locator)
    assert detail["view"]["products"][0]["title"] == new.products[0].title
    assert detail["view"]["products"][0]["url"].endswith("language=ja_JP")
    assert len(detail["view"]["images"]) == 2
    assert [p.read_bytes() for p in paths] == before
    with pytest.raises(LookupError):
        reopened.get("../history-0.sqlite3")
    expired = BrowserHistory(paths, now=lambda: NOW + timedelta(days=31))
    assert expired.list() == {"items": []}
    with pytest.raises(LookupError):
        expired.get(new.locator)


def test_history_missing_future_database_and_corrupt_database(tmp_path):
    from src.search_v2.browser_history import BrowserHistory

    path = tmp_path / "future.sqlite3"
    history = BrowserHistory([path], now=lambda: NOW)
    assert history.list() == {"items": []}
    assert not path.exists()
    detail = saved(path)
    assert history.get(detail.locator)["view"]["saved"] is True
    with sqlite3.connect(path) as db:
        db.execute("UPDATE provisional_history SET detail_sha256 = ?", ("0" * 64,))
    with pytest.raises(ProvisionalHistoryStorageError):
        history.list()


def test_history_api_projects_errors_without_paths(tmp_path, monkeypatch):
    from tools.browser_search_server import make_server
    from src.search_v2.browser_history import BrowserHistory

    path = tmp_path / "private.sqlite3"
    detail = saved(path)
    (tmp_path / "index.html").write_text("local")
    monkeypatch.setattr(
        "tools.browser_search_server.HTTPServer",
        lambda a, h: SimpleNamespace(server_port=8765, handler=h),
    )
    controller = SimpleNamespace(snapshot=lambda: {"stage": "working", "revision": 1})
    api = make_server(controller, tmp_path, history=BrowserHistory([path], now=lambda: NOW))
    assert request(api, "GET", "/api/history/" + detail.locator)[0] == 200
    assert request(api, "GET", "/api/history/../../private.sqlite3")[0] == 404
    assert json.loads(request(api, "GET", "/api/state")[2])["stage"] == "working"
    with sqlite3.connect(path) as db:
        db.execute("UPDATE provisional_history SET detail_sha256 = ?", ("0" * 64,))
    status, _, body = request(api, "GET", "/api/history")
    assert status == 503 and body == b"{}"


def test_product_name_is_saved_separately_from_input_and_reopened(tmp_path):
    from src.search_v2.browser_history import BrowserHistory
    from src.search_v2.provisional_history_repository import ProvisionalHistoryWrite

    path = tmp_path / "named.sqlite3"
    write = ProvisionalHistoryWrite.model_validate(
        pending().model_dump()
        | {
            "owner_id": "local-user",
            "summary": "3000円以下のマグカップを探しています。",
            "product_name": "マグカップ",
            "reference_images": pending().reference_images,
        }
    )
    detail = SqliteProvisionalHistoryRepository(path).save(write, now=NOW)
    before = path.read_bytes()
    browser = BrowserHistory([path], now=lambda: NOW)
    assert browser.list()["items"][0]["productName"] == "マグカップ"
    restored = browser.get(detail.locator)
    assert restored["productName"] == "マグカップ"
    assert restored["view"]["input"] == "3000円以下のマグカップを探しています。"
    assert path.read_bytes() == before
    assert "product_name" not in pending().model_dump()
