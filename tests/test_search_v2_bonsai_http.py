from __future__ import annotations

import json
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import inspect
from typing import Any
from unittest.mock import patch

import pytest
import requests
from requests.adapters import HTTPAdapter
from requests.cookies import RequestsCookieJar
from requests.structures import CaseInsensitiveDict

from src.exceptions import BonsaiRequestError
from src.search_v2.bonsai_http import RequestsBonsaiTransport
from src.search_v2.bonsai_request import BONSAI_MAX_RESPONSE_BYTES
from src.search_v2.bonsai_request import BONSAI_REQUEST_HEADERS
from src.search_v2.bonsai_request import bonsai_intent_request_sha256
from src.search_v2.bonsai_request import build_bonsai_intent_request
from src.search_v2.bonsai_request import execute_bonsai_intent_request
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import ProviderUsageLimits
from src.search_v2.usage_ledger import UsageAmount
from src.search_v2.usage_ledger import UsageReservationRequest


VALID_URL = "https://bonsai.example.test/v1/chat/completions"
REQUEST_BODY = b'{"fixed":"body"}'
NOW = datetime(2026, 9, 3, 6, 0, tzinfo=timezone.utc)


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


def make_response(
    chunks: tuple[object, ...] = (b"{}",),
    *,
    status_code: int = 200,
    content_type: str | None = "application/json; charset=utf-8",
    content_encoding: str | None = "identity",
    content_length: str | None = "2",
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


def transport_arguments(**overrides: object) -> dict[str, object]:
    arguments: dict[str, object] = {
        "url": VALID_URL,
        "headers": BONSAI_REQUEST_HEADERS,
        "body": REQUEST_BODY,
        "allow_redirects": False,
        "accept_encoding": "identity",
        "maximum_response_bytes": BONSAI_MAX_RESPONSE_BYTES,
    }
    arguments.update(overrides)
    return arguments


def call_transport(
    session: RecordingSession,
    **overrides: object,
):
    with patch("src.search_v2.bonsai_http.requests.Session", return_value=session) as factory:
        result = RequestsBonsaiTransport().post_json(**transport_arguments(**overrides))
    return result, factory


def intent_payload() -> dict[str, object]:
    return {
        "product_name_ja": "ヘッドホン",
        "product_name_en": "headphones",
        "typed_conditions": [
            {
                "attribute_key": "appearance.color",
                "strength": "required",
                "operator": "equals",
                "expected_value": {"value_type": "enum", "values": ["black"]},
            }
        ],
        "required_terms_ja": ["ワイヤレス", "黒"],
        "required_terms_en": ["wireless", "black"],
        "preferred_terms_ja": ["ノイズキャンセリング"],
        "preferred_terms_en": ["noise cancelling"],
        "brand": "Sony",
        "price": {
            "mode": "max",
            "max_jpy": 50000,
            "source": "explicit",
        },
    }


def valid_response_bytes() -> bytes:
    content = json.dumps(intent_payload(), ensure_ascii=False, separators=(",", ":"))
    envelope = {
        "id": "fixture-response-id",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }
    return json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode()


def reserve_usage(prepared):
    limit = UsageAmount(calls=100, tokens=10_000_000, cost_microusd=10_000_000)
    ledger = InMemoryUsageLedger(
        [
            ProviderUsageLimits(
                provider="bonsai",
                pricing_policy_sha256="a" * 64,
                per_user_day=limit,
                per_session=limit,
                global_day=limit,
            )
        ]
    )
    reservation = ledger.reserve(
        UsageReservationRequest(
            provider="bonsai",
            operation="intent",
            owner_id="owner-1",
            session_id="session-1",
            binding_sha256=bonsai_intent_request_sha256(prepared.request),
            amount=UsageAmount(
                calls=1,
                tokens=prepared.request.maximum_usage_tokens,
                cost_microusd=0,
            ),
            pricing_policy_sha256="a" * 64,
        ),
        now=NOW,
    )
    return ledger, reservation


class SequenceClock:
    def __init__(self, *values: datetime) -> None:
        self.values = iter(values)

    def __call__(self) -> datetime:
        return next(self.values)


def test_posts_exact_body_with_isolated_session_and_bounded_stream() -> None:
    response, raw = make_response((b"{", b'"ok":true}'), content_length="11")
    session = RecordingSession(response)

    result, factory = call_transport(session)

    factory.assert_called_once_with()
    assert session.trust_env is False
    assert session.headers == {}
    assert len(session.cookies) == 0
    assert session.proxies == {}
    assert session.auth is None
    assert [prefix for prefix, _ in session.mounts] == ["http://", "https://"]
    assert all(adapter.max_retries.total == 0 for _, adapter in session.mounts)
    assert all(adapter.max_retries.read is False for _, adapter in session.mounts)
    assert session.request_calls == [
        {
            "method": "POST",
            "url": VALID_URL,
            "headers": dict(BONSAI_REQUEST_HEADERS),
            "data": REQUEST_BODY,
            "allow_redirects": False,
            "stream": True,
            "verify": True,
            "proxies": {},
        }
    ]
    assert result.status_code == 200
    assert result.content_type == "application/json; charset=utf-8"
    assert result.content_encoding == "identity"
    assert result.content_length == 11
    assert result.body_chunks == (b'{"ok":true}',)
    assert raw.stream_calls == [(65_536, True)]
    assert session.close_calls == 1


def test_real_requests_preparation_has_no_unapproved_metadata() -> None:
    response, _ = make_response()
    session = CapturingSession(response)

    with patch("src.search_v2.bonsai_http.requests.Session", return_value=session):
        RequestsBonsaiTransport().post_json(**transport_arguments())

    prepared = session.prepared_request
    assert prepared is not None
    assert prepared.method == "POST"
    assert prepared.url == VALID_URL
    assert prepared.body == REQUEST_BODY
    assert dict(prepared.headers) == {
        "Accept": "application/json",
        "Accept-Encoding": "identity",
        "Content-Type": "application/json",
        "Content-Length": str(len(REQUEST_BODY)),
    }
    assert session.send_options == {
        "timeout": None,
        "allow_redirects": False,
        "stream": True,
        "verify": True,
        "cert": None,
        "proxies": {},
    }
    assert session.close_calls == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"url": "http://bonsai.example.test/v1/chat/completions"},
        {"url": "https://bonsai.example.test/v1/chat/completions?copy=1"},
        {"url": "https://bonsai.example.test/v1/models"},
        {"headers": BONSAI_REQUEST_HEADERS + (("X-Unapproved", "value"),)},
        {"body": "not-bytes"},
        {"body": b""},
        {"allow_redirects": True},
        {"accept_encoding": "gzip"},
        {"maximum_response_bytes": BONSAI_MAX_RESPONSE_BYTES - 1},
    ],
)
def test_invalid_transport_contract_stops_before_session(overrides: dict[str, Any]) -> None:
    with (
        patch("src.search_v2.bonsai_http.requests.Session") as factory,
        pytest.raises(
            BonsaiRequestError,
            match="^Bonsai HTTP transport request is invalid$",
        ),
    ):
        RequestsBonsaiTransport().post_json(**transport_arguments(**overrides))

    factory.assert_not_called()


def test_request_failure_is_fixed_and_session_is_closed() -> None:
    marker = "request-private-marker"
    session = RecordingSession(error=requests.Timeout(marker))

    with (
        patch("src.search_v2.bonsai_http.requests.Session", return_value=session),
        pytest.raises(BonsaiRequestError, match="^Bonsai HTTP transport failed$") as error,
    ):
        RequestsBonsaiTransport().post_json(**transport_arguments())

    assert marker not in str(error.value)
    assert error.value.__cause__ is None
    assert len(session.request_calls) == 1
    assert session.close_calls == 1


def test_transport_signature_and_send_options_have_no_application_timeout() -> None:
    assert "timeout_seconds" not in inspect.signature(RequestsBonsaiTransport.post_json).parameters

    response, _ = make_response()
    session = RecordingSession(response)
    call_transport(session)

    assert session.request_calls
    assert "timeout" not in session.request_calls[0]


def test_non_response_result_is_fixed_and_session_is_closed() -> None:
    session = RecordingSession(object())

    with (
        patch("src.search_v2.bonsai_http.requests.Session", return_value=session),
        pytest.raises(BonsaiRequestError, match="^Bonsai HTTP transport failed$"),
    ):
        RequestsBonsaiTransport().post_json(**transport_arguments())

    assert session.close_calls == 1


@pytest.mark.parametrize("content_length", ["-1", "+1", "1, 1", " 1", "one", "9" * 40])
def test_invalid_content_length_is_fixed_and_resources_are_closed(
    content_length: str,
) -> None:
    response, raw = make_response(content_length=content_length)
    session = RecordingSession(response)

    with (
        patch("src.search_v2.bonsai_http.requests.Session", return_value=session),
        pytest.raises(BonsaiRequestError, match="^Bonsai HTTP transport failed$"),
    ):
        RequestsBonsaiTransport().post_json(**transport_arguments())

    assert raw.stream_calls == []
    assert raw.close_calls == 1
    assert session.close_calls == 1


@pytest.mark.parametrize(
    ("response_options", "expected_status", "expected_length"),
    [
        ({"status_code": 302}, 302, 2),
        ({"status_code": 503}, 503, 2),
        ({"content_type": "text/plain"}, 200, 2),
        ({"content_encoding": "gzip"}, 200, 2),
        (
            {"content_length": str(BONSAI_MAX_RESPONSE_BYTES + 1)},
            200,
            BONSAI_MAX_RESPONSE_BYTES + 1,
        ),
    ],
)
def test_rejected_response_metadata_does_not_consume_body(
    response_options: dict[str, object],
    expected_status: int,
    expected_length: int,
) -> None:
    response, raw = make_response(**response_options)
    session = RecordingSession(response)

    result, _ = call_transport(session)

    assert result.status_code == expected_status
    assert result.content_length == expected_length
    assert result.body_chunks == ()
    assert raw.stream_calls == []
    assert raw.close_calls == 1
    assert session.close_calls == 1


def test_streamed_body_limit_stops_without_consuming_later_chunks() -> None:
    chunk = b"x" * (BONSAI_MAX_RESPONSE_BYTES // 2 + 1)
    response, raw = make_response(
        (chunk, chunk, b"must-not-be-consumed"),
        content_length=None,
    )
    session = RecordingSession(response)

    with (
        patch("src.search_v2.bonsai_http.requests.Session", return_value=session),
        pytest.raises(BonsaiRequestError, match="^Bonsai HTTP transport failed$"),
    ):
        RequestsBonsaiTransport().post_json(**transport_arguments())

    assert raw.yielded_chunks == 2
    assert raw.close_calls == 1
    assert session.close_calls == 1


def test_stream_failure_does_not_expose_detail_and_closes_resources() -> None:
    marker = "stream-private-marker"
    response, raw = make_response(
        (b"{",),
        content_length=None,
        stream_error=requests.ConnectionError(marker),
    )
    session = RecordingSession(response)

    with (
        patch("src.search_v2.bonsai_http.requests.Session", return_value=session),
        pytest.raises(BonsaiRequestError, match="^Bonsai HTTP transport failed$") as error,
    ):
        RequestsBonsaiTransport().post_json(**transport_arguments())

    assert marker not in str(error.value)
    assert error.value.__cause__ is None
    assert raw.close_calls == 1
    assert session.close_calls == 1


def test_empty_stream_chunks_are_discarded() -> None:
    response, _ = make_response(
        (b"", b"abc", b"", b"def"),
        content_length="6",
    )
    session = RecordingSession(response)

    result, _ = call_transport(session)

    assert result.body_chunks == (b"abcdef",)


def test_executes_request_and_strict_response_with_requests_transport() -> None:
    prepared = build_bonsai_intent_request(
        "Sonyの黒いワイヤレスヘッドホンを5万円以内で",
        base_url="http://127.0.0.1:8080/v1",
        model_id="Bonsai-8B.gguf",
        temperature=0.1,
    )
    ledger, reservation = reserve_usage(prepared)
    body = valid_response_bytes()
    response, _ = make_response(
        (body[:17], body[17:]),
        content_length=str(len(body)),
    )
    session = RecordingSession(response)

    with patch("src.search_v2.bonsai_http.requests.Session", return_value=session):
        result = execute_bonsai_intent_request(
            prepared,
            usage_ledger=ledger,
            usage_reservation=reservation,
            transport=RequestsBonsaiTransport(),
            now=SequenceClock(
                NOW + timedelta(seconds=1),
                NOW + timedelta(seconds=2),
            ),
        )

    assert len(session.request_calls) == 1
    assert session.request_calls[0]["data"] == prepared.body
    assert result.intent.brand == "Sony"
    assert result.usage_reservation.status == "succeeded"
    assert ledger.snapshot().reservations[0].status == "succeeded"


def test_requests_transport_failure_closes_execution_usage() -> None:
    prepared = build_bonsai_intent_request(
        "ワイヤレスヘッドホンを5万円以内で",
        base_url="http://127.0.0.1:8080/v1",
        model_id="Bonsai-8B.gguf",
        temperature=0.1,
    )
    ledger, reservation = reserve_usage(prepared)
    marker = "transport-integration-private-marker"
    session = RecordingSession(error=requests.Timeout(marker))

    with (
        patch("src.search_v2.bonsai_http.requests.Session", return_value=session),
        pytest.raises(BonsaiRequestError, match="^Bonsai intent request failed$") as error,
    ):
        execute_bonsai_intent_request(
            prepared,
            usage_ledger=ledger,
            usage_reservation=reservation,
            transport=RequestsBonsaiTransport(),
            now=SequenceClock(
                NOW + timedelta(seconds=1),
                NOW + timedelta(seconds=2),
            ),
        )

    assert marker not in str(error.value)
    assert len(session.request_calls) == 1
    assert session.close_calls == 1
    assert ledger.snapshot().reservations[0].status == "failed"
