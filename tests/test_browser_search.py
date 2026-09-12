"""Browser commands must not duplicate or bypass staged provider work."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from datetime import datetime, timedelta, timezone

import pytest

from src.search_v2.browser_search import BrowserSearch, BrowserCommandError


def command(action="start", revision=0, operation="operation-0001", **values):
    return {"action": action, "revision": revision, "operation": operation, **values}


def test_duplicate_command_and_reload_execute_once():
    calls = []
    entered, release = Event(), Event()

    def execute(action, values):
        calls.append(action)
        entered.set()
        assert release.wait(2)
        return {"stage": "query", "queries": ["マグカップ"]}

    with ThreadPoolExecutor(max_workers=1) as worker:
        controller = BrowserSearch(execute, worker)
        first = controller.submit(command())
        assert entered.wait(2)
        assert controller.submit(command()) == first
        assert controller.snapshot()["stage"] == "working"
        with pytest.raises(BrowserCommandError):
            controller.submit(command(operation="operation-0002"))
        release.set()
    assert calls == ["start"]
    assert controller.snapshot()["stage"] == "query"
    assert controller.submit(command())["stage"] == "query"


def test_confirmations_cannot_be_skipped_or_replayed():
    with ThreadPoolExecutor(max_workers=1) as worker:
        controller = BrowserSearch(lambda *_: {"stage": "query"}, worker)
        with pytest.raises(BrowserCommandError):
            controller.submit(command("search"))
        controller.submit(command())
    with pytest.raises(BrowserCommandError):
        controller.submit(command("reference", revision=0, operation="operation-0002", index=0))
    with pytest.raises(BrowserCommandError):
        controller.submit(command("search", revision=1, operation="operation-0003"))
    with pytest.raises(BrowserCommandError):
        controller.submit(command(index=0))


def test_provider_failure_is_terminal_and_redacted():
    def execute(*_):
        raise ValueError("private provider body")

    with ThreadPoolExecutor(max_workers=1) as worker:
        controller = BrowserSearch(execute, worker)
        controller.submit(command())
    result = controller.snapshot()
    assert result["stage"] == "failed"
    assert "private" not in str(result)
    with pytest.raises(BrowserCommandError):
        controller.submit(command(revision=1, operation="operation-0002"))


def test_expired_confirmation_is_visible_and_never_calls_provider():
    calls = []

    def execute(action, values):
        calls.append(action)
        return {"stage": "reference", "expiresAt": "2000-01-01T00:00:00+00:00"}

    with ThreadPoolExecutor(max_workers=1) as worker:
        controller = BrowserSearch(execute, worker)
        controller.submit(command())
    state = controller.snapshot()
    assert state["stage"] == "expired"
    assert state["message"] == "確認の期限が切れました。今回の実行は終了しています。"
    with pytest.raises(BrowserCommandError):
        controller.submit(
            command("comparison", revision=state["revision"], operation="operation-0002")
        )
    assert controller.submit(command())["stage"] == "expired"
    assert calls == ["start"]


def test_no_global_deadline_after_an_hour(monkeypatch):
    clock = [datetime(2026, 9, 12, tzinfo=timezone.utc)]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0]

    monkeypatch.setattr("src.search_v2.browser_search.datetime", Clock)
    with ThreadPoolExecutor(max_workers=1) as worker:
        controller = BrowserSearch(lambda *_: {"stage": "query"}, worker)
        controller.submit(command())
    clock[0] += timedelta(hours=1)
    view = controller.snapshot()
    assert view["stage"] == "query"
    assert "expiresAt" not in view


@pytest.mark.parametrize(
    "values",
    [
        {"revision": True},
        {"operation": "x"},
        {"action": "unknown"},
        {"source": "not authorized"},
        {"index": 0},
    ],
)
def test_invalid_commands_do_not_call_provider(values):
    with ThreadPoolExecutor(max_workers=1) as worker:
        controller = BrowserSearch(lambda *_: pytest.fail("provider called"), worker)
        with pytest.raises(BrowserCommandError):
            controller.submit({**command(), **values})


def test_consumed_image_expiry_does_not_limit_later_stages(monkeypatch):
    clock = [datetime(2026, 9, 12, tzinfo=timezone.utc)]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0]

    class Worker:
        def submit(self, fn, *args):
            fn(*args)

    def execute(action, _):
        if action == "start":
            return {
                "stage": "final",
                "expiresAt": (clock[0] + timedelta(minutes=15)).isoformat(),
            }
        clock[0] += timedelta(hours=1)
        return {"stage": "attributes"}

    monkeypatch.setattr("src.search_v2.browser_search.datetime", Clock)
    controller = BrowserSearch(execute, Worker())
    controller.submit(command())
    controller.submit(command("search", revision=1, operation="operation-0002"))
    view = controller.snapshot()
    assert view["stage"] == "attributes"
    assert "expiresAt" not in view


def test_snapshot_returns_japanese_product_links_without_mutating_saved_data():
    original = "https://www.amazon.co.jp/-/en/Synthetic/dp/B000000001?language=en_US&th=1"
    initial = {"stage": "complete", "products": [{"url": original}, {"url": None}]}
    controller = BrowserSearch(None, None, initial=initial)
    view = controller.snapshot()
    assert view["products"][0]["url"] == (
        "https://www.amazon.co.jp/dp/B000000001?th=1&language=ja_JP"
    )
    assert view["products"][1]["url"] is None
    assert initial["products"][0]["url"] == original
    assert controller.snapshot() == view


@pytest.mark.parametrize(
    "value",
    [
        None,
        123,
        "not a URL",
        "javascript:alert(1)",
        "https://amazon.co.jp.example.com/dp/B000000001",
        "https://user:password@amazon.co.jp/dp/B000000001",
    ],
)
def test_product_links_reject_unsafe_targets(value):
    from src.search_v2.product_links import japanese_product_url

    assert japanese_product_url(value) is None


@pytest.mark.parametrize(
    "values",
    [
        {"prompt": ""},
        {"prompt": "www.example.com"},
        {"prompts": {"unknown": "Edit."}},
        {"prompts": {"visual-condition-001": ""}},
    ],
)
def test_invalid_image_prompts_rejected_before_worker(values):
    action = "regenerate" if "prompt" in values else "regenerate_comparisons"
    with ThreadPoolExecutor(max_workers=1) as worker:
        controller = BrowserSearch(
            lambda *_: pytest.fail("worker called"),
            worker,
            initial={
                "stage": "comparison",
                "canRegenerate": True,
                "canRegenerateComparisons": True,
                "imagePrompts": {
                    "reference": "Reference.",
                    "comparison": {"visual-condition-001": "Comparison."},
                },
            },
        )
        with pytest.raises(BrowserCommandError):
            controller.submit(command(action, **values))
        assert controller.snapshot()["stage"] == "comparison"


def test_duplicate_prompt_edit_runs_once():
    calls = []
    with ThreadPoolExecutor(max_workers=1) as worker:
        controller = BrowserSearch(
            lambda action, values: calls.append((action, values)) or {"stage": "comparison"},
            worker,
            initial={
                "stage": "comparison",
                "canRegenerateComparisons": True,
                "imagePrompts": {
                    "reference": "Reference.",
                    "comparison": {"visual-condition-001": "Comparison."},
                },
            },
        )
        request = command(
            "regenerate_comparisons", prompts={"visual-condition-001": "Edited comparison."}
        )
        controller.submit(request)
        controller.submit(request)
    assert calls == [("regenerate_comparisons", {"prompts": request["prompts"]})]
