from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import os
from pathlib import Path
import sqlite3
import threading

from pydantic import ValidationError
import pytest

from src.search_v2.search_job import JOB_QUEUE_START_WINDOW
from src.search_v2.search_job import JOB_RETENTION
from src.search_v2.search_job import LOCAL_SEARCH_OWNER_ID
from src.search_v2.search_job import LocalSearchJobExecutor
from src.search_v2.search_job import SearchJobControl
from src.search_v2.search_job import SearchJobNotFoundError
from src.search_v2.search_job import SearchJobResult
from src.search_v2.search_job import SearchJobStorageError
from src.search_v2.search_job import SearchJobSubmission
from src.search_v2.search_job import SqliteSearchJobRepository


NOW = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
RESULT_LOCATOR = "r" * 43


def submission(
    *,
    owner_id: str = LOCAL_SEARCH_OWNER_ID,
    binding_sha256: str = "a" * 64,
) -> SearchJobSubmission:
    return SearchJobSubmission(
        schema_version="1.0",
        owner_id=owner_id,
        binding_sha256=binding_sha256,
    )


def result(locator: str = RESULT_LOCATOR) -> SearchJobResult:
    return SearchJobResult(schema_version="1.0", result_locator=locator)


def repository(tmp_path: Path) -> SqliteSearchJobRepository:
    return SqliteSearchJobRepository(tmp_path / "jobs.sqlite3")


def test_job_contracts_are_strict_frozen_and_do_not_accept_payload_fields(tmp_path) -> None:
    pending = submission()
    saved = repository(tmp_path).enqueue(pending, now=NOW).job

    assert saved.schema_version == "1.0"
    assert saved.status == "queued"
    assert saved.start_before == NOW + JOB_QUEUE_START_WINDOW
    assert saved.started_at is None
    assert saved.finished_at is None
    assert saved.purge_after is None
    assert set(saved.model_dump(mode="json")) == {
        "schema_version",
        "locator",
        "owner_id",
        "binding_sha256",
        "status",
        "revision",
        "created_at",
        "updated_at",
        "start_before",
        "started_at",
        "cancel_requested_at",
        "finished_at",
        "purge_after",
        "result_locator",
        "failure_code",
    }
    assert "owner_id" not in repr(saved)
    assert "binding_sha256" not in repr(saved)

    with pytest.raises(ValidationError, match="extra_forbidden"):
        SearchJobSubmission.model_validate(
            {
                **pending.model_dump(mode="python"),
                "source_text": "永続化してはならない検索文",
            }
        )
    with pytest.raises(ValidationError, match="frozen_instance"):
        pending.binding_sha256 = "b" * 64


def test_concurrent_duplicate_enqueue_creates_one_job(tmp_path) -> None:
    jobs = repository(tmp_path)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda _: jobs.enqueue(submission(), now=NOW),
                range(16),
            )
        )

    assert len({item.job.locator for item in results}) == 1
    assert sum(item.created for item in results) == 1
    assert jobs.count(owner_id=LOCAL_SEARCH_OWNER_ID) == 1


def test_owner_scope_hides_existing_job_like_unknown_locator(tmp_path) -> None:
    jobs = repository(tmp_path)
    saved = jobs.enqueue(submission(owner_id="owner-a"), now=NOW).job

    failures: list[str] = []
    for owner_id, locator in (
        ("owner-b", saved.locator),
        ("owner-a", "x" * 43),
    ):
        with pytest.raises(SearchJobNotFoundError) as raised:
            jobs.get(owner_id=owner_id, locator=locator, now=NOW)
        failures.append(str(raised.value))

    assert failures == ["Search job was not found"] * 2


def test_executor_runs_callbacks_in_background_one_at_a_time(tmp_path) -> None:
    jobs = repository(tmp_path)
    first_started = threading.Event()
    release_first = threading.Event()
    active = 0
    maximum_active = 0
    lock = threading.Lock()

    def runner(control: SearchJobControl) -> SearchJobResult:
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
            call_number = len(calls)
            calls.append(control.locator)
        if call_number == 0:
            first_started.set()
            assert release_first.wait(timeout=2)
        with lock:
            active -= 1
        return result("r" * 42 + str(call_number))

    calls: list[str] = []
    with LocalSearchJobExecutor(jobs, clock=lambda: NOW) as executor:
        first = executor.submit(binding_sha256="a" * 64, runner=runner)
        assert first_started.wait(timeout=2)
        second = executor.submit(binding_sha256="b" * 64, runner=runner)

        assert executor.get(first.locator).status == "running"
        assert executor.get(second.locator).status == "queued"
        release_first.set()
        executor.wait_until_idle()

        assert executor.get(first.locator).status == "succeeded"
        assert executor.get(second.locator).status == "succeeded"

    assert len(calls) == 2
    assert maximum_active == 1


def test_duplicate_executor_submit_never_runs_replacement_callback(tmp_path) -> None:
    jobs = repository(tmp_path)
    started = threading.Event()
    release = threading.Event()
    replacement_called = threading.Event()

    def original(control: SearchJobControl) -> SearchJobResult:
        started.set()
        assert release.wait(timeout=2)
        return result()

    def replacement(control: SearchJobControl) -> SearchJobResult:
        replacement_called.set()
        return result("z" * 43)

    with LocalSearchJobExecutor(jobs, clock=lambda: NOW) as executor:
        first = executor.submit(binding_sha256="a" * 64, runner=original)
        assert started.wait(timeout=2)
        duplicate = executor.submit(binding_sha256="a" * 64, runner=replacement)
        release.set()
        executor.wait_until_idle()

        assert duplicate.locator == first.locator
        assert executor.get(first.locator).result_locator == RESULT_LOCATOR

    assert not replacement_called.is_set()


def test_queued_cancel_prevents_callback_from_starting(tmp_path) -> None:
    jobs = repository(tmp_path)
    first_started = threading.Event()
    release_first = threading.Event()
    queued_called = threading.Event()

    def first_runner(control: SearchJobControl) -> SearchJobResult:
        first_started.set()
        assert release_first.wait(timeout=2)
        return result()

    def queued_runner(control: SearchJobControl) -> SearchJobResult:
        queued_called.set()
        return result("q" * 43)

    with LocalSearchJobExecutor(jobs, clock=lambda: NOW) as executor:
        executor.submit(binding_sha256="a" * 64, runner=first_runner)
        assert first_started.wait(timeout=2)
        queued = executor.submit(binding_sha256="b" * 64, runner=queued_runner)

        cancelled = executor.cancel(queued.locator)
        assert cancelled.status == "cancelled"
        release_first.set()
        executor.wait_until_idle()

        assert executor.get(queued.locator).status == "cancelled"

    assert not queued_called.is_set()


def test_running_cancel_is_cooperative_and_discards_returned_result(tmp_path) -> None:
    jobs = repository(tmp_path)
    started = threading.Event()
    release = threading.Event()

    def runner(control: SearchJobControl) -> SearchJobResult:
        started.set()
        assert release.wait(timeout=2)
        assert control.cancel_requested
        return result()

    with LocalSearchJobExecutor(jobs, clock=lambda: NOW) as executor:
        submitted = executor.submit(binding_sha256="a" * 64, runner=runner)
        assert started.wait(timeout=2)

        requested = executor.cancel(submitted.locator)
        assert requested.status == "cancel_requested"
        release.set()
        executor.wait_until_idle()

        cancelled = executor.get(submitted.locator)
        assert cancelled.status == "cancelled"
        assert cancelled.result_locator is None


def test_callback_error_is_reduced_to_fixed_code_without_body_storage(tmp_path) -> None:
    path = tmp_path / "jobs.sqlite3"
    secret_message = "sensitive-query-and-provider-response"

    def runner(control: SearchJobControl) -> SearchJobResult:
        raise RuntimeError(secret_message)

    jobs = SqliteSearchJobRepository(path)
    with LocalSearchJobExecutor(jobs, clock=lambda: NOW) as executor:
        submitted = executor.submit(binding_sha256="a" * 64, runner=runner)
        executor.wait_until_idle()
        failed = executor.get(submitted.locator)

    assert failed.status == "failed"
    assert failed.failure_code == "execution_failed"
    assert secret_message.encode() not in path.read_bytes()


def test_queue_start_deadline_times_out_without_running_work(tmp_path) -> None:
    jobs = repository(tmp_path)
    queued = jobs.enqueue(submission(), now=NOW).job

    timed_out = jobs.claim_for_execution(
        owner_id=LOCAL_SEARCH_OWNER_ID,
        locator=queued.locator,
        now=NOW + JOB_QUEUE_START_WINDOW,
    )

    assert timed_out.status == "timed_out"
    assert timed_out.started_at is None
    assert timed_out.failure_code == "queue_start_expired"
    assert timed_out.purge_after == timed_out.finished_at + JOB_RETENTION


def test_restart_recovery_never_replays_unrestorable_callbacks(tmp_path) -> None:
    jobs = repository(tmp_path)
    running = jobs.enqueue(submission(binding_sha256="a" * 64), now=NOW).job
    cancel_requested = jobs.enqueue(submission(binding_sha256="b" * 64), now=NOW).job
    queued = jobs.enqueue(submission(binding_sha256="c" * 64), now=NOW).job
    jobs.claim_for_execution(
        owner_id=LOCAL_SEARCH_OWNER_ID,
        locator=running.locator,
        now=NOW,
    )
    jobs.claim_for_execution(
        owner_id=LOCAL_SEARCH_OWNER_ID,
        locator=cancel_requested.locator,
        now=NOW,
    )
    jobs.request_cancel(
        owner_id=LOCAL_SEARCH_OWNER_ID,
        locator=cancel_requested.locator,
        now=NOW,
    )

    recovered = jobs.recover_interrupted(now=NOW + timedelta(seconds=1))

    assert recovered == 3
    assert (
        jobs.get(
            owner_id=LOCAL_SEARCH_OWNER_ID,
            locator=running.locator,
            now=NOW + timedelta(seconds=1),
        ).failure_code
        == "worker_restarted"
    )
    assert (
        jobs.get(
            owner_id=LOCAL_SEARCH_OWNER_ID,
            locator=cancel_requested.locator,
            now=NOW + timedelta(seconds=1),
        ).status
        == "cancelled"
    )
    assert (
        jobs.get(
            owner_id=LOCAL_SEARCH_OWNER_ID,
            locator=queued.locator,
            now=NOW + timedelta(seconds=1),
        ).failure_code
        == "worker_restarted"
    )


def test_terminal_metadata_is_purged_at_thirty_days_but_active_job_remains(tmp_path) -> None:
    jobs = repository(tmp_path)
    completed = jobs.enqueue(submission(binding_sha256="a" * 64), now=NOW).job
    active = jobs.enqueue(submission(binding_sha256="b" * 64), now=NOW).job
    jobs.claim_for_execution(
        owner_id=LOCAL_SEARCH_OWNER_ID,
        locator=completed.locator,
        now=NOW,
    )
    jobs.claim_for_execution(
        owner_id=LOCAL_SEARCH_OWNER_ID,
        locator=active.locator,
        now=NOW,
    )
    jobs.finish_success(
        owner_id=LOCAL_SEARCH_OWNER_ID,
        locator=completed.locator,
        result=result(),
        now=NOW,
    )

    assert jobs.purge_expired(now=NOW + JOB_RETENTION - timedelta(microseconds=1)) == 0
    assert jobs.purge_expired(now=NOW + JOB_RETENTION) == 1
    assert jobs.count(owner_id=LOCAL_SEARCH_OWNER_ID) == 1
    assert (
        jobs.get(
            owner_id=LOCAL_SEARCH_OWNER_ID,
            locator=active.locator,
            now=NOW + JOB_RETENTION,
        ).status
        == "running"
    )
    with pytest.raises(SearchJobNotFoundError):
        jobs.get(
            owner_id=LOCAL_SEARCH_OWNER_ID,
            locator=completed.locator,
            now=NOW + JOB_RETENTION,
        )


def test_repository_rejects_unsafe_mode_unknown_schema_and_row_tampering(tmp_path) -> None:
    path = tmp_path / "jobs.sqlite3"
    jobs = SqliteSearchJobRepository(path)
    saved = jobs.enqueue(submission(), now=NOW).job

    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE search_jobs SET status = 'succeeded' WHERE locator = ?",
            (saved.locator,),
        )
    with pytest.raises(SearchJobStorageError, match="^Search job storage operation failed$"):
        jobs.get(owner_id=LOCAL_SEARCH_OWNER_ID, locator=saved.locator, now=NOW)

    schema_path = tmp_path / "unknown.sqlite3"
    SqliteSearchJobRepository(schema_path)
    with sqlite3.connect(schema_path) as connection:
        connection.execute("PRAGMA user_version = 2")
    with pytest.raises(SearchJobStorageError, match="^Search job storage operation failed$"):
        SqliteSearchJobRepository(schema_path)

    if os.name == "posix":
        os.chmod(path, 0o644)
        with pytest.raises(SearchJobStorageError, match="^Search job storage operation failed$"):
            SqliteSearchJobRepository(path)


def test_executor_startup_recovers_existing_active_jobs(tmp_path) -> None:
    jobs = repository(tmp_path)
    queued = jobs.enqueue(submission(), now=NOW).job

    with LocalSearchJobExecutor(jobs, clock=lambda: NOW + timedelta(seconds=1)) as executor:
        recovered = executor.get(queued.locator)

    assert recovered.status == "failed"
    assert recovered.failure_code == "worker_restarted"
