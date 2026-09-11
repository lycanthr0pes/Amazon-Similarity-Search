from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import json
from unittest.mock import patch

import pytest
import requests
from requests.adapters import HTTPAdapter
from requests.cookies import RequestsCookieJar
from requests.structures import CaseInsensitiveDict

from src.search_v2.outscraper_http import OUTSCRAPER_MAX_POLLS
from src.search_v2.outscraper_http import OUTSCRAPER_MAX_RESPONSE_BYTES
from src.search_v2.outscraper_http import OUTSCRAPER_POLL_INTERVAL_SECONDS
from src.search_v2.outscraper_http import OUTSCRAPER_REQUEST_HEADERS
from src.search_v2.outscraper_http import OUTSCRAPER_REQUEST_TIMEOUT_SECONDS
from src.search_v2.outscraper_http import OutscraperExecutionError
from src.search_v2.outscraper_http import OutscraperHttpResponse
from src.search_v2.outscraper_http import OutscraperPollingTimeout
from src.search_v2.outscraper_http import OutscraperProductExecution
from src.search_v2.outscraper_http import OutscraperResponseContractError
from src.search_v2.outscraper_http import OutscraperResultLocationError
from src.search_v2.outscraper_http import OutscraperTaskFailed
from src.search_v2.outscraper_http import OutscraperTransportError
from src.search_v2.outscraper_http import RequestsOutscraperTransport
from src.search_v2.outscraper_http import execute_outscraper_request
from src.search_v2.outscraper_request import AuthorizedOutscraperRequest
from src.search_v2.outscraper_request import build_outscraper_request
from src.search_v2.product_normalization import ProductNormalizationProfile
from src.search_v2.product_normalization import normalize_outscraper_products
from src.search_v2.query_planner import SearchQuery
from src.search_v2.query_planner import SearchQueryPlan
from src.search_v2.query_planner import search_query_plan_sha256
from src.search_v2.state_machine import SearchApprovalGrant
from src.search_v2.state_machine import SearchSessionSnapshot
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import ProviderUsageLimits
from src.search_v2.usage_ledger import UsageAmount
from src.search_v2.usage_ledger import UsageReservation
from src.search_v2.usage_ledger import UsageReservationRequest


ENDPOINT = "https://api.outscraper.cloud/amazon-products"
RESULTS_LOCATION = "https://api.outscraper.cloud/requests/request-1"
FIXTURE_API_KEY = "fixture-api-key"
NOW = datetime(2026, 9, 3, 8, 0, tzinfo=timezone.utc)


class RecordingRaw:
    def __init__(
        self,
        chunks: tuple[object, ...],
        *,
        error: Exception | None = None,
    ) -> None:
        self.chunks = chunks
        self.error = error
        self.stream_calls: list[tuple[int, bool]] = []
        self.yielded_chunks = 0
        self.close_calls = 0
        self.release_calls = 0

    def stream(self, chunk_size: int, *, decode_content: bool):
        self.stream_calls.append((chunk_size, decode_content))
        for chunk in self.chunks:
            self.yielded_chunks += 1
            yield chunk
        if self.error is not None:
            raise self.error

    def close(self) -> None:
        self.close_calls += 1

    def release_conn(self) -> None:
        self.release_calls += 1


def requests_response(
    chunks: tuple[object, ...],
    *,
    status_code: int = 200,
    content_type: str | None = "application/json; charset=utf-8",
    content_encoding: str | None = "identity",
    content_length: str | None = None,
    stream_error: Exception | None = None,
) -> tuple[requests.Response, RecordingRaw]:
    response = requests.Response()
    response.status_code = status_code
    headers: dict[str, str] = {}
    if content_type is not None:
        headers["Content-Type"] = content_type
    if content_encoding is not None:
        headers["Content-Encoding"] = content_encoding
    if content_length is not None:
        headers["Content-Length"] = content_length
    response.headers = CaseInsensitiveDict(headers)
    raw = RecordingRaw(chunks, error=stream_error)
    response.raw = raw
    response._content = False
    response._content_consumed = False
    return response, raw


class RecordingSession:
    def __init__(
        self,
        response: object | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.trust_env = True
        self.headers = {"User-Agent": "unapproved-default"}
        self.cookies = RequestsCookieJar()
        self.cookies.set("unapproved-cookie", "value")
        self.proxies = {"https": "http://proxy.invalid"}
        self.auth: object = object()
        self.mounts: list[tuple[str, HTTPAdapter]] = []
        self.request_calls: list[dict[str, object]] = []
        self.close_calls = 0

    def mount(self, prefix: str, adapter: HTTPAdapter) -> None:
        self.mounts.append((prefix, adapter))

    def request(self, **kwargs: object) -> object:
        self.request_calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response

    def close(self) -> None:
        self.close_calls += 1


class CapturingSession(requests.Session):
    def __init__(self, response: requests.Response) -> None:
        super().__init__()
        self.response = response
        self.prepared_request: requests.PreparedRequest | None = None
        self.send_options: dict[str, object] | None = None
        self.close_calls = 0

    def send(self, request: requests.PreparedRequest, **kwargs: object) -> requests.Response:
        self.prepared_request = request
        self.send_options = kwargs
        return self.response

    def close(self) -> None:
        self.close_calls += 1
        super().close()


class ScriptedTransport:
    def __init__(self, responses: list[OutscraperHttpResponse | Exception]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def get(self, **kwargs: object) -> OutscraperHttpResponse:
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("unexpected Outscraper transport call")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def query_plan() -> SearchQueryPlan:
    return SearchQueryPlan(
        schema_version="2.0",
        intent_sha256="a" * 64,
        queries=[
            SearchQuery(language="ja", value="静音 ヘッドホン"),
            SearchQuery(language="en", value="quiet headphones"),
        ],
    )


def execution_context() -> tuple[
    AuthorizedOutscraperRequest,
    InMemoryUsageLedger,
    UsageReservation,
]:
    request = build_outscraper_request(query_plan(), postal_code="100-0001")
    plan_sha256 = "b" * 64
    consumed_at = NOW + timedelta(seconds=4)
    approval = SearchApprovalGrant(
        plan_sha256=plan_sha256,
        token_sha256="c" * 64,
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=15),
        consumed_at=consumed_at,
    )
    session = SearchSessionSnapshot(
        schema_version="3.0",
        owner_id="owner-1",
        session_id="session-1",
        revision=5,
        state="scrape_submitted",
        intent_sha256=query_plan().intent_sha256,
        query_plan_sha256=search_query_plan_sha256(query_plan()),
        typed_requirement_proposal_sha256="e" * 64,
        typed_requirement_status="ready",
        image_mode="off",
        image_attempts_started=0,
        active_image_reservation_id=None,
        image_set_sha256=None,
        image_request_metadata_sha256=None,
        usage_policy_sha256=None,
        approval=approval,
        created_at=NOW - timedelta(seconds=1),
        updated_at=consumed_at,
    )
    limit = UsageAmount(calls=10, tokens=0, cost_microusd=100_000)
    ledger = InMemoryUsageLedger(
        [
            ProviderUsageLimits(
                provider="outscraper",
                pricing_policy_sha256="d" * 64,
                per_user_day=limit,
                per_session=limit,
                global_day=limit,
            )
        ]
    )
    reserved = ledger.reserve(
        UsageReservationRequest(
            provider="outscraper",
            operation="product_search",
            owner_id=session.owner_id,
            session_id=session.session_id,
            binding_sha256=plan_sha256,
            amount=UsageAmount(calls=1, tokens=0, cost_microusd=10_000),
            pricing_policy_sha256="d" * 64,
        ),
        now=NOW + timedelta(seconds=1),
    )
    started = ledger.start(
        reserved.reservation_id,
        owner_id=session.owner_id,
        session_id=session.session_id,
        now=NOW + timedelta(seconds=2),
    )
    permit = AuthorizedOutscraperRequest(
        request=request,
        session=session,
        approval_plan_sha256=plan_sha256,
        reservation_id=started.reservation_id,
        authorized_at=consumed_at,
    )
    return permit, ledger, started


def transport_arguments(**overrides: object) -> dict[str, object]:
    request = build_outscraper_request(query_plan(), postal_code="100-0001")
    arguments: dict[str, object] = {
        "url": request.endpoint,
        "params": request.query_parameters(),
        "api_key": FIXTURE_API_KEY,
        "timeout_seconds": OUTSCRAPER_REQUEST_TIMEOUT_SECONDS,
        "allow_redirects": False,
        "accept_encoding": "identity",
        "maximum_response_bytes": OUTSCRAPER_MAX_RESPONSE_BYTES,
    }
    arguments.update(overrides)
    return arguments


def http_response(
    payload: object,
    *,
    status_code: int = 200,
) -> OutscraperHttpResponse:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    return OutscraperHttpResponse(
        status_code=status_code,
        content_type="application/json; charset=utf-8",
        content_length=len(body),
        content_encoding="identity",
        body_chunks=(body,),
    )


def run_execution(
    transport: ScriptedTransport,
    *,
    permit: AuthorizedOutscraperRequest | None = None,
    ledger: InMemoryUsageLedger | None = None,
    reservation: UsageReservation | None = None,
    api_key: str = FIXTURE_API_KEY,
    sleep=None,
) -> OutscraperProductExecution:
    if permit is None or ledger is None or reservation is None:
        permit, ledger, reservation = execution_context()
    return execute_outscraper_request(
        permit,
        usage_ledger=ledger,
        usage_reservation=reservation,
        api_key=api_key,
        transport=transport,
        now=lambda: NOW + timedelta(seconds=10),
        sleep=(lambda _seconds: None) if sleep is None else sleep,
    )


def completed_payload(*, request_id: str = "request-1") -> dict[str, object]:
    return {
        "id": request_id,
        "status": "Success",
        "data": [
            [
                {
                    "query": "静音 ヘッドホン",
                    "name": "Observed headphones",
                    "asin": "B012345678",
                    "price": "12,000",
                    "currency": "JPY",
                }
            ],
            [],
        ],
    }


def reservation_status(ledger: InMemoryUsageLedger, reservation_id: str) -> str:
    return next(
        item.status
        for item in ledger.snapshot().reservations
        if item.reservation_id == reservation_id
    )


def test_runtime_policy_is_fixed_and_bounded() -> None:
    assert OUTSCRAPER_REQUEST_TIMEOUT_SECONDS == 30
    assert OUTSCRAPER_POLL_INTERVAL_SECONDS == 30
    assert OUTSCRAPER_MAX_POLLS == 50
    assert OUTSCRAPER_MAX_RESPONSE_BYTES == 8 * 1024 * 1024
    assert OUTSCRAPER_REQUEST_HEADERS == (
        ("Accept", "application/json"),
        ("Accept-Encoding", "identity"),
    )


def test_transport_sends_exact_get_and_removes_session_ambient_state() -> None:
    body = b'{"id":"request-1","status":"Pending"}'
    response, raw = requests_response(
        (body,),
        status_code=202,
        content_length=str(len(body)),
    )
    session = RecordingSession(response)

    with patch("src.search_v2.outscraper_http.requests.Session", return_value=session) as factory:
        result = RequestsOutscraperTransport().get(**transport_arguments())

    factory.assert_called_once_with()
    assert session.trust_env is False
    assert session.headers == {}
    assert len(session.cookies) == 0
    assert session.proxies == {}
    assert session.auth is None
    assert [prefix for prefix, _adapter in session.mounts] == ["http://", "https://"]
    assert all(adapter.max_retries.total == 0 for _prefix, adapter in session.mounts)
    assert session.request_calls == [
        {
            "method": "GET",
            "url": ENDPOINT,
            "params": build_outscraper_request(
                query_plan(), postal_code="100-0001"
            ).query_parameters(),
            "headers": {
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "X-API-KEY": FIXTURE_API_KEY,
            },
            "timeout": (30, 30),
            "allow_redirects": False,
            "stream": True,
            "verify": True,
            "proxies": {},
        }
    ]
    assert result.body_chunks == (body,)
    assert raw.stream_calls == [(65_536, True)]
    assert session.close_calls == 1
    assert raw.close_calls == 1
    assert raw.release_calls == 1


def test_real_requests_prepared_request_has_only_fixed_headers_and_exact_parameters() -> None:
    body = b'{"id":"request-1","status":"Pending"}'
    response, _raw = requests_response(
        (body,),
        status_code=202,
        content_length=str(len(body)),
    )
    session = CapturingSession(response)

    with patch("src.search_v2.outscraper_http.requests.Session", return_value=session):
        RequestsOutscraperTransport().get(**transport_arguments())

    prepared = session.prepared_request
    assert prepared is not None
    assert prepared.method == "GET"
    assert prepared.body is None
    assert prepared.url is not None
    assert prepared.url.startswith(f"{ENDPOINT}?")
    assert prepared.url.count("query=") == 2
    assert "postal_code=100-0001" in prepared.url
    assert dict(prepared.headers) == {
        "Accept": "application/json",
        "Accept-Encoding": "identity",
        "X-API-KEY": FIXTURE_API_KEY,
    }
    assert "User-Agent" not in prepared.headers
    assert "Cookie" not in prepared.headers
    assert "Authorization" not in prepared.headers
    assert session.send_options is not None
    assert session.send_options["allow_redirects"] is False
    assert session.send_options["stream"] is True
    assert session.send_options["verify"] is True
    assert session.close_calls == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"url": "http://api.outscraper.cloud/amazon-products"},
        {"url": "https://user@example.test/amazon-products"},
        {"url": "https://api.outscraper.cloud/amazon-products?query=injected"},
        {"params": []},
        {"params": (("query", "safe"), ("webhook", "https://example.test"))},
        {"api_key": ""},
        {"api_key": "key\nvalue"},
        {"timeout_seconds": True},
        {"timeout_seconds": 301},
        {"allow_redirects": True},
        {"accept_encoding": "gzip"},
        {"maximum_response_bytes": OUTSCRAPER_MAX_RESPONSE_BYTES - 1},
    ],
)
def test_invalid_transport_contract_is_rejected_before_session_creation(
    overrides: dict[str, object],
) -> None:
    with (
        patch("src.search_v2.outscraper_http.requests.Session") as factory,
        pytest.raises(OutscraperExecutionError, match="execution request is invalid"),
    ):
        RequestsOutscraperTransport().get(**transport_arguments(**overrides))

    factory.assert_not_called()


def test_transport_failure_has_fixed_message_and_closes_session() -> None:
    session = RecordingSession(error=requests.Timeout(f"leaked {FIXTURE_API_KEY}"))

    with (
        patch("src.search_v2.outscraper_http.requests.Session", return_value=session),
        pytest.raises(OutscraperTransportError) as exc_info,
    ):
        RequestsOutscraperTransport().get(**transport_arguments())

    assert str(exc_info.value) == "Outscraper HTTP transport failed"
    assert exc_info.value.__cause__ is None
    assert FIXTURE_API_KEY not in repr(exc_info.value)
    assert session.close_calls == 1


@pytest.mark.parametrize(
    ("response_kwargs", "expected_status"),
    [
        ({"status_code": 302}, 302),
        ({"content_type": "text/plain"}, 200),
        ({"content_encoding": "gzip"}, 200),
        ({"content_length": str(OUTSCRAPER_MAX_RESPONSE_BYTES + 1)}, 200),
    ],
)
def test_transport_does_not_read_unusable_response_bodies(
    response_kwargs: dict[str, object],
    expected_status: int,
) -> None:
    response, raw = requests_response((b"must-not-be-read",), **response_kwargs)
    session = RecordingSession(response)

    with patch("src.search_v2.outscraper_http.requests.Session", return_value=session):
        result = RequestsOutscraperTransport().get(**transport_arguments())

    assert result.status_code == expected_status
    assert result.body_chunks == ()
    assert raw.yielded_chunks == 0
    assert session.close_calls == 1


@pytest.mark.parametrize("content_length", ["-1", "+1", "1.0", "1 0", "9" * 21])
def test_invalid_content_length_is_a_fixed_response_error(content_length: str) -> None:
    response, raw = requests_response((b"{}",), content_length=content_length)
    session = RecordingSession(response)

    with (
        patch("src.search_v2.outscraper_http.requests.Session", return_value=session),
        pytest.raises(OutscraperResponseContractError) as exc_info,
    ):
        RequestsOutscraperTransport().get(**transport_arguments())

    assert str(exc_info.value) == "Outscraper response did not match the task contract"
    assert exc_info.value.__cause__ is None
    assert raw.yielded_chunks == 0
    assert session.close_calls == 1


def test_streaming_body_is_stopped_at_the_exact_byte_limit() -> None:
    first = b"x" * OUTSCRAPER_MAX_RESPONSE_BYTES
    response, raw = requests_response((first, b"y"), content_length=None)
    session = RecordingSession(response)

    with (
        patch("src.search_v2.outscraper_http.requests.Session", return_value=session),
        pytest.raises(OutscraperResponseContractError),
    ):
        RequestsOutscraperTransport().get(**transport_arguments())

    assert raw.yielded_chunks == 2
    assert session.close_calls == 1


def test_immediate_success_returns_sanitized_result_and_finishes_usage() -> None:
    permit, ledger, reservation = execution_context()
    transport = ScriptedTransport([http_response(completed_payload())])

    execution = run_execution(
        transport,
        permit=permit,
        ledger=ledger,
        reservation=reservation,
    )

    assert isinstance(execution, OutscraperProductExecution)
    assert execution.request == permit.request
    assert execution.provider_request_id == "request-1"
    assert execution.response == {"data": completed_payload()["data"]}
    assert execution.polls_performed == 0
    assert execution.usage_reservation.status == "succeeded"
    assert reservation_status(ledger, reservation.reservation_id) == "succeeded"
    assert FIXTURE_API_KEY not in repr(execution)
    assert RESULTS_LOCATION not in repr(execution)


def test_pending_task_polls_same_id_until_success_without_extra_sleep() -> None:
    pending = {
        "id": "request-1",
        "status": "Pending",
        "results_location": RESULTS_LOCATION,
    }
    transport = ScriptedTransport(
        [
            http_response(pending, status_code=202),
            http_response({"id": "request-1", "status": "Pending"}),
            http_response(completed_payload()),
        ]
    )
    sleeps: list[int] = []

    execution = run_execution(transport, sleep=sleeps.append)

    assert execution.polls_performed == 2
    assert sleeps == [OUTSCRAPER_POLL_INTERVAL_SECONDS]
    assert len(transport.calls) == 3
    assert transport.calls[0]["url"] == ENDPOINT
    assert (
        transport.calls[0]["params"]
        == build_outscraper_request(query_plan(), postal_code="100-0001").query_parameters()
    )
    assert transport.calls[1]["url"] == RESULTS_LOCATION
    assert transport.calls[1]["params"] == ()
    assert transport.calls[2]["url"] == RESULTS_LOCATION
    assert all(call["api_key"] == FIXTURE_API_KEY for call in transport.calls)
    assert all(call["allow_redirects"] is False for call in transport.calls)


@pytest.mark.parametrize(
    "results_location",
    [
        "http://api.outscraper.cloud/requests/request-1",
        "https://evil.example/requests/request-1",
        "https://api.outscraper.cloud.evil.example/requests/request-1",
        "https://api.outscraper.cloud:444/requests/request-1",
        "https://api.outscraper.cloud/other/request-1",
        "https://api.outscraper.cloud/requests/request-2",
        "https://api.outscraper.cloud/requests/request-1?flat=true",
        "https://user@api.outscraper.cloud/requests/request-1",
    ],
)
def test_unapproved_result_location_fails_before_api_key_is_sent_again(
    results_location: str,
) -> None:
    permit, ledger, reservation = execution_context()
    transport = ScriptedTransport(
        [
            http_response(
                {
                    "id": "request-1",
                    "status": "Pending",
                    "results_location": results_location,
                },
                status_code=202,
            )
        ]
    )

    with pytest.raises(OutscraperResultLocationError) as exc_info:
        run_execution(
            transport,
            permit=permit,
            ledger=ledger,
            reservation=reservation,
        )

    assert str(exc_info.value) == "Outscraper result location is not approved"
    assert exc_info.value.__cause__ is None
    assert results_location not in str(exc_info.value)
    assert len(transport.calls) == 1
    assert reservation_status(ledger, reservation.reservation_id) == "failed"


def test_polled_response_id_must_match_initial_task() -> None:
    permit, ledger, reservation = execution_context()
    transport = ScriptedTransport(
        [
            http_response(
                {
                    "id": "request-1",
                    "status": "Pending",
                    "results_location": RESULTS_LOCATION,
                },
                status_code=202,
            ),
            http_response(completed_payload(request_id="request-2")),
        ]
    )

    with pytest.raises(OutscraperResponseContractError):
        run_execution(
            transport,
            permit=permit,
            ledger=ledger,
            reservation=reservation,
        )

    assert reservation_status(ledger, reservation.reservation_id) == "failed"


@pytest.mark.parametrize(
    "response",
    [
        OutscraperHttpResponse(
            status_code=200,
            content_type="application/json",
            content_length=2,
            content_encoding="identity",
            body_chunks=(b"[]",),
        ),
        OutscraperHttpResponse(
            status_code=200,
            content_type="application/json",
            content_length=None,
            content_encoding="identity",
            body_chunks=(b'{"id":"a","id":"b","status":1}',),
        ),
        OutscraperHttpResponse(
            status_code=200,
            content_type="application/json",
            content_length=None,
            content_encoding="identity",
            body_chunks=(b'{"id":"request-1","status":NaN,"data":[]}',),
        ),
        OutscraperHttpResponse(
            status_code=200,
            content_type="application/json",
            content_length=1,
            content_encoding="identity",
            body_chunks=(b"\xff",),
        ),
    ],
)
def test_invalid_json_and_envelopes_fail_closed_and_finish_usage(
    response: OutscraperHttpResponse,
) -> None:
    permit, ledger, reservation = execution_context()

    with pytest.raises(OutscraperResponseContractError) as exc_info:
        run_execution(
            ScriptedTransport([response]),
            permit=permit,
            ledger=ledger,
            reservation=reservation,
        )

    assert str(exc_info.value) == "Outscraper response did not match the task contract"
    assert exc_info.value.__cause__ is None
    assert reservation_status(ledger, reservation.reservation_id) == "failed"


def test_task_failure_is_fixed_and_finishes_usage_without_exposing_provider_text() -> None:
    permit, ledger, reservation = execution_context()
    provider_text = f"do not expose {FIXTURE_API_KEY}"
    transport = ScriptedTransport(
        [
            http_response(
                {
                    "id": "request-1",
                    "status": "Failure",
                    "errorMessage": provider_text,
                },
                status_code=204,
            )
        ]
    )

    with pytest.raises(OutscraperTaskFailed) as exc_info:
        run_execution(
            transport,
            permit=permit,
            ledger=ledger,
            reservation=reservation,
        )

    assert str(exc_info.value) == "Outscraper product search task failed"
    assert provider_text not in repr(exc_info.value)
    assert reservation_status(ledger, reservation.reservation_id) == "failed"


def test_pending_task_stops_at_fixed_poll_limit_and_finishes_usage() -> None:
    permit, ledger, reservation = execution_context()
    initial = http_response(
        {
            "id": "request-1",
            "status": "Pending",
            "results_location": RESULTS_LOCATION,
        },
        status_code=202,
    )
    pending = http_response({"id": "request-1", "status": "Pending"})
    transport = ScriptedTransport([initial, *[pending] * OUTSCRAPER_MAX_POLLS])
    sleeps: list[int] = []

    with pytest.raises(OutscraperPollingTimeout) as exc_info:
        run_execution(
            transport,
            permit=permit,
            ledger=ledger,
            reservation=reservation,
            sleep=sleeps.append,
        )

    assert str(exc_info.value) == "Outscraper product search task timed out"
    assert len(transport.calls) == 1 + OUTSCRAPER_MAX_POLLS
    assert len(sleeps) == OUTSCRAPER_MAX_POLLS - 1
    assert reservation_status(ledger, reservation.reservation_id) == "failed"


def test_transport_failure_is_not_retried_and_finishes_usage() -> None:
    permit, ledger, reservation = execution_context()
    transport = ScriptedTransport([OutscraperTransportError("Outscraper HTTP transport failed")])

    with pytest.raises(OutscraperTransportError):
        run_execution(
            transport,
            permit=permit,
            ledger=ledger,
            reservation=reservation,
        )

    assert len(transport.calls) == 1
    assert reservation_status(ledger, reservation.reservation_id) == "failed"


def test_http_error_is_not_retried_or_read() -> None:
    permit, ledger, reservation = execution_context()
    response = OutscraperHttpResponse(
        status_code=500,
        content_type="application/json",
        content_length=1_000,
        content_encoding="identity",
        body_chunks=(),
    )
    transport = ScriptedTransport([response])

    with pytest.raises(OutscraperTransportError):
        run_execution(
            transport,
            permit=permit,
            ledger=ledger,
            reservation=reservation,
        )

    assert len(transport.calls) == 1
    assert reservation_status(ledger, reservation.reservation_id) == "failed"


def test_success_output_connects_to_existing_observed_only_normalizer() -> None:
    execution = run_execution(ScriptedTransport([http_response(completed_payload())]))

    batch = normalize_outscraper_products(
        execution.response,
        request=execution.request,
        provider_request_id=execution.provider_request_id,
        profile=ProductNormalizationProfile(
            schema_version="2.0",
            profile_id="observed-only-v2",
            usd_to_jpy_rate=150,
        ),
    )

    assert len(batch.products) == 1
    assert batch.products[0].title == "Observed headphones"
    assert batch.products[0].price_jpy == 12_000


@pytest.mark.parametrize(
    "mutate",
    [
        lambda permit, reservation: (
            replace(permit, reservation_id="x" * 32),
            reservation,
        ),
        lambda permit, reservation: (
            replace(permit, approval_plan_sha256="f" * 64),
            reservation,
        ),
        lambda permit, reservation: (
            permit,
            reservation.model_copy(update={"status": "succeeded"}),
        ),
    ],
)
def test_forged_permit_or_reservation_is_rejected_before_transport(
    mutate,
) -> None:
    permit, ledger, reservation = execution_context()
    changed_permit, changed_reservation = mutate(permit, reservation)
    transport = ScriptedTransport([])

    with pytest.raises(OutscraperExecutionError, match="execution request is invalid"):
        run_execution(
            transport,
            permit=changed_permit,
            ledger=ledger,
            reservation=changed_reservation,
        )

    assert transport.calls == []
    assert reservation_status(ledger, reservation.reservation_id) == "started"


def test_invalid_api_key_finishes_valid_started_usage_without_transport() -> None:
    permit, ledger, reservation = execution_context()
    transport = ScriptedTransport([])

    with pytest.raises(OutscraperExecutionError, match="execution request is invalid"):
        run_execution(
            transport,
            permit=permit,
            ledger=ledger,
            reservation=reservation,
            api_key="",
        )

    assert transport.calls == []
    assert reservation_status(ledger, reservation.reservation_id) == "failed"
