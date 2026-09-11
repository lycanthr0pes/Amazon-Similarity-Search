from __future__ import annotations

import asyncio
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import json
from typing import Any

from src.search_v2.production_api import InMemoryProductionSubmissionStore
from src.search_v2.production_api import create_local_production_api
from src.search_v2.production_search import ProductionSearchCommand
from src.search_v2.provisional_history_repository import ProvisionalHistoryDetail
from src.search_v2.provisional_history_repository import ProvisionalHistoryProductView
from src.search_v2.provisional_history_repository import ProvisionalHistoryReferenceImageRef
from src.search_v2.search_job import JOB_QUEUE_START_WINDOW
from src.search_v2.search_job import JOB_RETENTION
from src.search_v2.search_job import SearchJobNotFoundError
from src.search_v2.search_job import SearchJobSnapshot


NOW = datetime(2026, 9, 8, 15, 0, tzinfo=timezone.utc)
JOB_LOCATOR = "j" * 43
HISTORY_LOCATOR = "h" * 43


def command() -> ProductionSearchCommand:
    return ProductionSearchCommand(
        source_text="fixture source",
        approved_search=None,
        condition_set=None,
        approved_references=None,
    )


def job(
    status: str = "queued",
    *,
    locator: str = JOB_LOCATOR,
    result_locator: str | None = None,
) -> SearchJobSnapshot:
    started_at = NOW + timedelta(seconds=1) if status != "queued" else None
    cancel_requested_at = None
    finished_at = None
    failure_code = None
    updated_at = started_at or NOW
    purge_after = None
    if status == "cancel_requested":
        cancel_requested_at = NOW + timedelta(seconds=2)
        updated_at = cancel_requested_at
    elif status in {"succeeded", "failed", "cancelled", "timed_out"}:
        finished_at = NOW + timedelta(seconds=3)
        updated_at = finished_at
        purge_after = finished_at + JOB_RETENTION
        if status == "succeeded":
            result_locator = result_locator or HISTORY_LOCATOR
        elif status == "failed":
            failure_code = "execution_failed"
        elif status == "cancelled":
            cancel_requested_at = NOW + timedelta(seconds=2)
        elif status == "timed_out":
            started_at = None
            failure_code = "queue_start_expired"
    return SearchJobSnapshot(
        schema_version="1.0",
        locator=locator,
        owner_id="local-user",
        binding_sha256="b" * 64,
        status=status,
        revision=1 if status != "queued" else 0,
        created_at=NOW,
        updated_at=updated_at,
        start_before=NOW + JOB_QUEUE_START_WINDOW,
        started_at=started_at,
        cancel_requested_at=cancel_requested_at,
        finished_at=finished_at,
        purge_after=purge_after,
        result_locator=result_locator,
        failure_code=failure_code,
    )


class FakeProductionService:
    def __init__(self) -> None:
        self.current = job()
        self.submit_calls = 0
        self.get_calls = 0
        self.cancel_calls = 0

    def submit(self, _command: ProductionSearchCommand) -> SearchJobSnapshot:
        self.submit_calls += 1
        return self.current

    def get(self, locator: str) -> SearchJobSnapshot:
        self.get_calls += 1
        if locator != self.current.locator:
            raise SearchJobNotFoundError("sensitive internal detail")
        return self.current

    def cancel(self, locator: str) -> SearchJobSnapshot:
        self.cancel_calls += 1
        if locator != self.current.locator:
            raise SearchJobNotFoundError("sensitive internal detail")
        if self.current.status == "queued":
            self.current = job("cancelled")
        elif self.current.status == "running":
            self.current = job("cancel_requested")
        return self.current


class FakeHistoryRepository:
    def __init__(self, detail: ProvisionalHistoryDetail) -> None:
        self.detail = detail
        self.calls: list[tuple[str, str, datetime]] = []

    def get(self, *, owner_id: str, locator: str, now: datetime) -> ProvisionalHistoryDetail:
        self.calls.append((owner_id, locator, now))
        return self.detail


def history_detail() -> ProvisionalHistoryDetail:
    references = (
        ProvisionalHistoryReferenceImageRef(
            schema_version="5.0",
            locator="d" * 43,
            target="desired",
            condition_id=None,
            content_type="image/png",
            width=512,
            height=512,
        ),
        ProvisionalHistoryReferenceImageRef(
            schema_version="5.0",
            locator="c" * 43,
            target="counterfactual",
            condition_id="visual-condition-001",
            content_type="image/png",
            width=512,
            height=512,
        ),
    )
    products = (
        ProvisionalHistoryProductView(
            schema_version="5.0",
            rank=1,
            title="黒いマウス",
            price_jpy=2980,
            product_url="https://www.amazon.co.jp/dp/B000000001",
            required_status="confirmed",
            image_component_status="available",
            image_score=0.82,
            total_score=0.91,
        ),
    )
    return ProvisionalHistoryDetail(
        schema_version="5.0",
        locator=HISTORY_LOCATOR,
        completed_at=NOW,
        expires_at=NOW + timedelta(days=30),
        summary="黒いマウスを探す",
        provisional_profile_id="counterfactual-v4-provisional-production-v1",
        known_holdout_accuracy=0.875,
        ranking_profile_id="typed-ranking-v5-counterfactual-provisional",
        ranking_profile_sha256="1" * 64,
        source_typed_ranked_product_batch_sha256="2" * 64,
        condition_set_sha256="3" * 64,
        reference_set_sha256="4" * 64,
        runtime_sha256="5" * 64,
        reference_images=references,
        products=products,
    )


async def call_asgi(
    app,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    client_host: str = "127.0.0.1",
) -> tuple[int, dict[str, str], bytes]:
    sent: list[dict[str, Any]] = []
    request_headers = [(b"host", b"localhost")]
    request_headers.extend(
        (name.lower().encode("ascii"), value.encode("ascii"))
        for name, value in (headers or {}).items()
    )
    received = False

    async def receive() -> dict[str, Any]:
        nonlocal received
        if not received:
            received = True
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "root_path": "",
        "headers": request_headers,
        "client": (client_host, 50000),
        "server": ("127.0.0.1", 8000),
    }
    await app(scope, receive, send)
    start = next(item for item in sent if item["type"] == "http.response.start")
    body = b"".join(item.get("body", b"") for item in sent if item["type"] == "http.response.body")
    response_headers = {
        name.decode("latin-1"): value.decode("latin-1") for name, value in start["headers"]
    }
    return start["status"], response_headers, body


def request(app, method: str, path: str, **kwargs):
    return asyncio.run(call_asgi(app, method, path, **kwargs))


def api_fixture():
    service = FakeProductionService()
    history = FakeHistoryRepository(history_detail())
    submissions = InMemoryProductionSubmissionStore()
    submission = submissions.register(
        command(),
        now=NOW,
        expires_at=NOW + timedelta(minutes=15),
    )
    app = create_local_production_api(
        service=service,
        history_repository=history,
        submission_store=submissions,
        now=lambda: NOW,
    )
    return app, service, history, submission


def test_submit_is_idempotent_and_returns_only_display_safe_job_state() -> None:
    app, service, _history, submission = api_fixture()
    headers = {"x-amazon-explorer-submission": submission.capability}

    first_status, first_headers, first_body = request(
        app,
        "POST",
        "/api/v1/search-jobs",
        headers=headers,
    )
    second_status, _second_headers, second_body = request(
        app,
        "POST",
        "/api/v1/search-jobs",
        headers=headers,
    )

    assert first_status == second_status == 202
    assert first_headers["cache-control"] == "no-store"
    assert first_body == second_body
    assert service.submit_calls == 1
    payload = json.loads(first_body)
    assert payload == {
        "schema_version": "1.0",
        "locator": JOB_LOCATOR,
        "status": "queued",
        "can_cancel": True,
        "created_at": "2026-09-08T15:00:00Z",
        "updated_at": "2026-09-08T15:00:00Z",
        "finished_at": None,
        "result_locator": None,
    }
    assert submission.capability.encode() not in first_body
    assert b"owner_id" not in first_body
    assert b"binding_sha256" not in first_body
    assert b"failure_code" not in first_body


def test_get_and_cancel_use_existing_job_without_restarting_work() -> None:
    app, service, _history, submission = api_fixture()
    headers = {"x-amazon-explorer-submission": submission.capability}
    request(app, "POST", "/api/v1/search-jobs", headers=headers)

    get_status, _get_headers, get_body = request(
        app,
        "GET",
        f"/api/v1/search-jobs/{JOB_LOCATOR}",
    )
    cancel_status, _cancel_headers, cancel_body = request(
        app,
        "POST",
        f"/api/v1/search-jobs/{JOB_LOCATOR}/cancel",
    )

    assert get_status == cancel_status == 200
    assert json.loads(get_body)["status"] == "queued"
    cancelled = json.loads(cancel_body)
    assert cancelled["status"] == "cancelled"
    assert cancelled["can_cancel"] is False
    assert service.submit_calls == 1
    assert service.cancel_calls == 1


def test_terminal_job_cannot_be_cancelled_again() -> None:
    app, service, _history, _submission = api_fixture()
    service.current = job("succeeded")

    status, _headers, body = request(
        app,
        "POST",
        f"/api/v1/search-jobs/{JOB_LOCATOR}/cancel",
    )

    assert status == 409
    assert json.loads(body) == {"schema_version": "1.0", "error": "state_conflict"}
    assert service.cancel_calls == 0


def test_history_projection_excludes_internal_ranking_metadata_and_scores() -> None:
    app, _service, history, _submission = api_fixture()

    status, headers, body = request(
        app,
        "GET",
        f"/api/v1/search-history/{HISTORY_LOCATOR}",
    )

    assert status == 200
    assert headers["cache-control"] == "no-store"
    payload = json.loads(body)
    assert payload["summary"] == "黒いマウスを探す"
    assert payload["reference_images"][0]["target"] == "desired"
    assert payload["products"] == [
        {
            "rank": 1,
            "title": "黒いマウス",
            "price_jpy": 2980,
            "product_url": "https://www.amazon.co.jp/dp/B000000001",
            "required_status": "confirmed",
            "image_component_status": "available",
        }
    ]
    serialized = body.decode("utf-8")
    for forbidden in (
        "known_holdout_accuracy",
        "ranking_profile",
        "runtime_sha256",
        "total_score",
        "image_score",
    ):
        assert forbidden not in serialized
    assert history.calls == [("local-user", HISTORY_LOCATOR, NOW)]


def test_missing_capability_and_unknown_resource_use_fixed_not_found() -> None:
    app, _service, _history, _submission = api_fixture()

    submit_status, _submit_headers, submit_body = request(
        app,
        "POST",
        "/api/v1/search-jobs",
    )
    get_status, _get_headers, get_body = request(
        app,
        "GET",
        f"/api/v1/search-jobs/{'x' * 43}",
    )

    expected = {"schema_version": "1.0", "error": "not_found"}
    assert submit_status == get_status == 404
    assert json.loads(submit_body) == expected
    assert json.loads(get_body) == expected
    assert b"sensitive" not in get_body


def test_non_loopback_client_is_rejected_before_service_access() -> None:
    app, service, _history, submission = api_fixture()

    status, _headers, body = request(
        app,
        "POST",
        "/api/v1/search-jobs",
        headers={"x-amazon-explorer-submission": submission.capability},
        client_host="192.0.2.10",
    )

    assert status == 403
    assert json.loads(body) == {"schema_version": "1.0", "error": "local_only"}
    assert service.submit_calls == 0


def test_expired_submission_is_removed_without_starting_search() -> None:
    service = FakeProductionService()
    history = FakeHistoryRepository(history_detail())
    submissions = InMemoryProductionSubmissionStore()
    submission = submissions.register(
        command(),
        now=NOW,
        expires_at=NOW + timedelta(minutes=1),
    )
    app = create_local_production_api(
        service=service,
        history_repository=history,
        submission_store=submissions,
        now=lambda: NOW + timedelta(minutes=1),
    )

    status, _headers, body = request(
        app,
        "POST",
        "/api/v1/search-jobs",
        headers={"x-amazon-explorer-submission": submission.capability},
    )

    assert status == 404
    assert json.loads(body) == {"schema_version": "1.0", "error": "not_found"}
    assert service.submit_calls == 0


def test_submission_lifetime_cannot_exceed_approval_window() -> None:
    submissions = InMemoryProductionSubmissionStore()

    try:
        submissions.register(
            command(),
            now=NOW,
            expires_at=NOW + timedelta(minutes=15, microseconds=1),
        )
    except ValueError as error:
        assert str(error) == "Production submission is invalid"
    else:
        raise AssertionError("overlong submission capability was accepted")


def test_unexpected_backend_error_is_not_disclosed() -> None:
    app, service, _history, _submission = api_fixture()

    def fail_with_sensitive_detail(_locator: str) -> SearchJobSnapshot:
        raise RuntimeError("sensitive backend detail")

    service.get = fail_with_sensitive_detail  # type: ignore[method-assign]
    status, _headers, body = request(
        app,
        "GET",
        f"/api/v1/search-jobs/{JOB_LOCATOR}",
    )

    assert status == 500
    assert json.loads(body) == {"schema_version": "1.0", "error": "internal_error"}
    assert b"sensitive" not in body


def test_method_not_allowed_uses_fixed_json_error() -> None:
    app, _service, _history, _submission = api_fixture()

    status, headers, body = request(app, "GET", "/api/v1/search-jobs")

    assert status == 405
    assert headers["cache-control"] == "no-store"
    assert json.loads(body) == {
        "schema_version": "1.0",
        "error": "method_not_allowed",
    }


def test_cancel_race_does_not_report_an_uncancelled_state_as_success() -> None:
    app, service, _history, _submission = api_fixture()

    def lose_cancel_race(_locator: str) -> SearchJobSnapshot:
        service.cancel_calls += 1
        return job("succeeded")

    service.cancel = lose_cancel_race  # type: ignore[method-assign]
    status, _headers, body = request(
        app,
        "POST",
        f"/api/v1/search-jobs/{JOB_LOCATOR}/cancel",
    )

    assert status == 409
    assert json.loads(body) == {"schema_version": "1.0", "error": "state_conflict"}
    assert service.cancel_calls == 1
