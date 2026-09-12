"""Connected UI actions retain single-worker authority and provider limits."""

from concurrent.futures import ThreadPoolExecutor
from src.search_v2.browser_search import BrowserSearch
from src.search_v2.browser_candidate import BrowserCandidateRun
from tests.test_browser_search import command


def test_new_search_returns_to_input_without_reusing_old_steps():
    attempts = []

    def factory(source, attempt):
        attempts.append(attempt)
        yield {"stage": "query", "queries": [source]}

    run = BrowserCandidateRun(factory=factory)
    with ThreadPoolExecutor(max_workers=1) as worker:
        controller = BrowserSearch(run.execute, worker, initial={"editable": True, "input": "合成"})
        controller.submit(command(source="合成"))
        worker.submit(lambda: None).result()
        view = controller.snapshot()
        assert view.get("canReset") is True
        controller.submit(command("reset", revision=view["revision"], operation="reset-operation"))
        worker.submit(lambda: None).result()
        view = controller.snapshot()
        assert view["stage"] == "idle" and view["input"] == ""
        controller.submit(
            command(revision=view["revision"], operation="second-operation", source="次の合成")
        )
        worker.submit(lambda: None).result()
    assert attempts == [0, 1]


def test_actual_working_operation_is_exposed_without_fake_progress():
    from threading import Event

    entered, release = Event(), Event()

    def execute(*args):
        entered.set()
        release.wait(2)
        return {"stage": "query"}

    with ThreadPoolExecutor(max_workers=1) as worker:
        controller = BrowserSearch(execute, worker)
        try:
            view = controller.submit(command())
            assert entered.wait(2)
            assert view.get("workingAction") == "start"
        finally:
            release.set()


def test_regeneration_and_save_retry_never_repeat_product_fetch(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import test_candidate_connected_flow as connected
    import test_candidate_search as candidate
    from src.search_v2.browser_candidate import candidate_browser_steps

    flow, images, _, history, clock = connected.start(tmp_path, plan_lifetime=None)
    ranking, calls = connected.clip(monkeypatch, tmp_path)
    transport = candidate.ProductTransport(candidate.scanner_products(), tmp_path)
    saved = history.save
    saves = []
    progress = []

    def fail_once(*args, **kwargs):
        assert progress[-1] == 4
        saves.append(True)
        if len(saves) == 1:
            raise OSError("fixture")
        return saved(*args, **kwargs)

    monkeypatch.setattr(history, "save", fail_once)
    run = BrowserCandidateRun(
        candidate_browser_steps(
            flow,
            progress=progress.append,
            owner=connected.OWNER,
            images=SimpleNamespace(previews=lambda: ["fixture"] * len(images.calls)),
            products=lambda _: transport,
            history=history,
            now=lambda: clock[0],
            proxy=ranking["proxy_service"],
            assets=ranking["asset_root"],
            encoder=ranking["encoder"],
        )
    )
    assert run.execute("start", {})["referenceRemaining"] == 2
    assert run.execute("reference", {"index": 0})["referenceRemaining"] == 1
    run.execute("comparison", {})
    reference = run.execute("regenerate", {})
    assert reference["stage"] == "reference" and reference["referenceRemaining"] == 0
    assert reference["images"] == ["fixture"] and not reference["canRegenerate"]
    run.execute("comparison", {})
    run.execute("final", {})
    result = run.execute("search", {})
    assert result["stage"] == "complete" and result["canRetrySave"] and not result["saved"]
    assert result["products"] and len(transport.calls) == 1
    before = (len(images.calls), len(calls), len(transport.calls))
    result = run.execute("retry_save", {})
    assert result["saved"] and not result["canRetrySave"]
    assert before == (len(images.calls), len(calls), len(transport.calls))
    assert len(history.list(owner_id=connected.OWNER, now=clock[0])) == 1


def test_cancel_during_fetch_stops_before_ranking_or_save_and_cannot_overlap():
    from threading import Event
    import pytest
    from src.search_v2.browser_search import BrowserCommandError

    entered, release = Event(), Event()
    completed = []

    def execute(*args):
        controller.progress(0)
        entered.set()
        assert release.wait(2)
        controller.progress(1)
        completed.append(True)
        return {"stage": "complete"}

    with ThreadPoolExecutor(max_workers=1) as worker:
        controller = BrowserSearch(execute, worker, initial={"editable": True})
        controller.submit(command(source="合成"))
        assert entered.wait(2)
        try:
            view = controller.snapshot()
            stop = command("cancel", revision=view["revision"], operation="stop-operation")
            assert controller.submit(stop)["cancelRequested"]
            assert controller.submit(stop)["cancelRequested"]
            with pytest.raises(BrowserCommandError):
                controller.submit(
                    command("reset", revision=view["revision"], operation="reset-operation")
                )
        finally:
            release.set()
    assert not completed
    assert controller.snapshot()["stage"] == "cancelled"


def test_progress_after_fetch_disables_late_cancel():
    from threading import Event
    import pytest
    from src.search_v2.browser_search import BrowserCommandError

    entered, release = Event(), Event()

    def execute(*args):
        controller.progress(1)
        entered.set()
        release.wait(2)
        return {"stage": "complete"}

    with ThreadPoolExecutor(max_workers=1) as worker:
        controller = BrowserSearch(execute, worker)
        controller.submit(command())
        assert entered.wait(2)
        try:
            with pytest.raises(BrowserCommandError):
                controller.submit(command("cancel", revision=1, operation="late-cancel-operation"))
        finally:
            release.set()
    assert controller.snapshot()["stage"] == "complete"


def test_preparation_failure_can_be_retried_within_existing_budget():
    from tests.test_browser_editing import InlineWorker

    attempts = []

    def factory(source, attempt):
        attempts.append(attempt)
        if attempt == 0:
            raise ValueError("fixture failure")
        yield {"stage": "query", "queries": [source]}

    run = BrowserCandidateRun(factory=factory)
    controller = BrowserSearch(run.execute, InlineWorker(), initial={"editable": True})
    assert controller.submit(command(source="合成"))["stage"] == "failed"
    view = controller.snapshot()
    assert view["canRevise"]
    assert (
        controller.submit(
            command("revise", revision=view["revision"], operation="retry-operation", source="合成")
        )["stage"]
        == "query"
    )
    assert attempts == [0, 1]


def test_detail_progress_keeps_cancel_pending_until_fetch_finishes():
    from src.search_v2.browser_search import BrowserCancelled
    import pytest

    with ThreadPoolExecutor(max_workers=1) as worker:
        controller = BrowserSearch(
            lambda *_: None, worker, initial={"stage": "working", "workingAction": "search"}
        )
        controller.progress(1, during_fetch=True)
        view = controller.snapshot()
        assert view["researchStep"] == 1 and view["canCancel"]
        controller.submit(command("cancel", revision=view["revision"]))
        controller.progress(1, during_fetch=True)
        assert controller.snapshot()["cancelRequested"] and not controller.snapshot()["canCancel"]
        with pytest.raises(BrowserCancelled):
            controller.progress(2)
