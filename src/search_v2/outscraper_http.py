from __future__ import annotations

from collections.abc import Callable
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
import hmac
import json
import re
import unicodedata
from typing import Any
from typing import Literal
from typing import Protocol
from urllib.parse import urlsplit

from pydantic import ValidationError
import requests
from requests.adapters import HTTPAdapter

from src.search_v2.outscraper_request import OUTSCRAPER_DOMAIN
from src.search_v2.outscraper_request import OUTSCRAPER_LANGUAGE
from src.search_v2.outscraper_request import OUTSCRAPER_LIMIT_PER_QUERY
from src.search_v2.outscraper_request import AuthorizedOutscraperRequest
from src.search_v2.outscraper_request import OutscraperAmazonProductsRequest
from src.search_v2.outscraper_request import _validated_endpoint
from src.search_v2.state_machine import SearchSessionSnapshot
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import UsageReservation


OUTSCRAPER_REQUEST_TIMEOUT_SECONDS = 30
OUTSCRAPER_POLL_INTERVAL_SECONDS = 30
OUTSCRAPER_MAX_POLLS = 50
OUTSCRAPER_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
OUTSCRAPER_REQUEST_HEADERS: tuple[tuple[str, str], ...] = (
    ("Accept", "application/json"),
    ("Accept-Encoding", "identity"),
)

_STREAM_CHUNK_BYTES = 65_536
_MAX_API_KEY_CHARACTERS = 4_096
_MAX_URL_CHARACTERS = 2_048
_MAX_HEADER_VALUE_CODEPOINTS = 200
_MAX_CONTENT_LENGTH_DIGITS = 20
_MAX_PROVIDER_REQUEST_ID_CHARACTERS = 256
_POSTAL_CODE_PATTERN = re.compile(r"^[0-9]{3}-?[0-9]{4}$")
_DNS_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_RESULT_PATH_PATTERN = re.compile(
    rf"^/requests/([A-Za-z0-9][A-Za-z0-9._-]{{0,{_MAX_PROVIDER_REQUEST_ID_CHARACTERS - 1}}})$"
)
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")

_INVALID_EXECUTION_MESSAGE = "Outscraper execution request is invalid"
_TRANSPORT_FAILED_MESSAGE = "Outscraper HTTP transport failed"
_INVALID_RESPONSE_MESSAGE = "Outscraper response did not match the task contract"
_INVALID_LOCATION_MESSAGE = "Outscraper result location is not approved"
_TASK_FAILED_MESSAGE = "Outscraper product search task failed"
_POLLING_TIMEOUT_MESSAGE = "Outscraper product search task timed out"


class OutscraperExecutionError(RuntimeError):
    """Base class for fixed-message v2 execution failures."""


class OutscraperTransportError(OutscraperExecutionError):
    """The bounded HTTP request could not complete."""


class OutscraperResponseContractError(OutscraperExecutionError):
    """The provider response did not satisfy the v2 task contract."""


class OutscraperResultLocationError(OutscraperExecutionError):
    """A provider-supplied polling location was not approved."""


class OutscraperTaskFailed(OutscraperExecutionError):
    """The provider reported a terminal task failure."""


class OutscraperPollingTimeout(OutscraperExecutionError):
    """The provider remained pending through the fixed polling ceiling."""


def _raise_invalid_execution() -> None:
    raise OutscraperExecutionError(_INVALID_EXECUTION_MESSAGE) from None


def _raise_transport_failed() -> None:
    raise OutscraperTransportError(_TRANSPORT_FAILED_MESSAGE) from None


def _raise_invalid_response() -> None:
    raise OutscraperResponseContractError(_INVALID_RESPONSE_MESSAGE) from None


def _raise_invalid_location() -> None:
    raise OutscraperResultLocationError(_INVALID_LOCATION_MESSAGE) from None


def _raise_task_failed() -> None:
    raise OutscraperTaskFailed(_TASK_FAILED_MESSAGE) from None


def _raise_polling_timeout() -> None:
    raise OutscraperPollingTimeout(_POLLING_TIMEOUT_MESSAGE) from None


@dataclass(frozen=True, slots=True, repr=False)
class OutscraperHttpResponse:
    status_code: int
    content_type: str | None
    content_length: int | None
    content_encoding: str | None
    body_chunks: Iterable[bytes]


class OutscraperRequestTransport(Protocol):
    def get(
        self,
        *,
        url: str,
        params: tuple[tuple[str, str], ...],
        api_key: str,
        timeout_seconds: int,
        allow_redirects: Literal[False],
        accept_encoding: Literal["identity"],
        maximum_response_bytes: int,
    ) -> OutscraperHttpResponse: ...


@dataclass(frozen=True, slots=True, repr=False)
class OutscraperProductExecution:
    request: OutscraperAmazonProductsRequest
    provider_request_id: str
    response: dict[str, object]
    polls_performed: int
    usage_reservation: UsageReservation


def _canonical_https_url(value: object) -> tuple[str, str, int, str]:
    if (
        type(value) is not str
        or not value
        or len(value) > _MAX_URL_CHARACTERS
        or value != value.strip()
        or any(unicodedata.category(character).startswith("C") for character in value)
    ):
        raise ValueError("URL is invalid")
    try:
        value.encode("ascii")
        parsed = urlsplit(value)
        port = parsed.port
    except (UnicodeEncodeError, ValueError) as exc:
        raise ValueError("URL is invalid") from exc

    host = parsed.hostname
    if (
        parsed.scheme != "https"
        or host is None
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.path.startswith("/")
        or parsed.query
        or parsed.fragment
        or "%" in parsed.netloc
        or "\\" in value
        or host != host.casefold()
        or host.endswith(".")
        or len(host) > 253
        or len(host.split(".")) < 2
        or any(_DNS_LABEL_PATTERN.fullmatch(label) is None for label in host.split("."))
    ):
        raise ValueError("URL is not a canonical HTTPS operation URL")

    expected_netloc = host if port is None else f"{host}:{port}"
    if parsed.netloc != expected_netloc:
        raise ValueError("URL authority is not canonical")
    return value, host, port or 443, parsed.path


def _validated_transport_url(value: object) -> str:
    url, _host, _port, path = _canonical_https_url(value)
    if path == "/amazon-products":
        return _validated_endpoint(url)
    if _RESULT_PATH_PATTERN.fullmatch(path) is None:
        raise ValueError("URL path is not approved")
    return url


def _validated_query_value(value: str) -> None:
    if (
        not value
        or len(value) > 200
        or value != value.strip()
        or any(unicodedata.category(character).startswith("C") for character in value)
    ):
        raise ValueError("query value is invalid")


def _validated_params(
    url: str,
    params: object,
) -> tuple[tuple[str, str], ...]:
    if type(params) is not tuple:
        raise TypeError("request parameters must be a tuple")

    validated: list[tuple[str, str]] = []
    for item in params:
        if type(item) is not tuple or len(item) != 2:
            raise TypeError("request parameter is invalid")
        name, value = item
        if type(name) is not str or type(value) is not str:
            raise TypeError("request parameter field is invalid")
        validated.append((name, value))

    path = urlsplit(url).path
    if path != "/amazon-products":
        if validated:
            raise ValueError("polling request must not contain query parameters")
        return ()

    if len(validated) not in {6, 7}:
        raise ValueError("task request parameter count is invalid")
    query_count = len(validated) - 5
    query_parameters = validated[:query_count]
    tail = validated[query_count:]
    if any(name != "query" for name, _value in query_parameters):
        raise ValueError("task query parameters are invalid")
    for _name, value in query_parameters:
        _validated_query_value(value)
    if tail != [
        ("domain", OUTSCRAPER_DOMAIN),
        ("language", OUTSCRAPER_LANGUAGE),
        ("postal_code", tail[2][1]),
        ("limit", str(OUTSCRAPER_LIMIT_PER_QUERY)),
        ("async", "true"),
    ]:
        raise ValueError("task request parameters are invalid")
    if _POSTAL_CODE_PATTERN.fullmatch(tail[2][1]) is None:
        raise ValueError("task postal code is invalid")
    return tuple(validated)


def _validated_api_key(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > _MAX_API_KEY_CHARACTERS
        or not value.isascii()
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise ValueError("API key is invalid")
    return value


def _validate_transport_contract(
    *,
    url: object,
    params: object,
    api_key: object,
    timeout_seconds: object,
    allow_redirects: object,
    accept_encoding: object,
    maximum_response_bytes: object,
) -> tuple[str, tuple[tuple[str, str], ...], str]:
    try:
        validated_url = _validated_transport_url(url)
        validated_params = _validated_params(validated_url, params)
        validated_key = _validated_api_key(api_key)
        if type(timeout_seconds) is not int or (
            timeout_seconds != OUTSCRAPER_REQUEST_TIMEOUT_SECONDS
        ):
            raise ValueError("request timeout is invalid")
        if allow_redirects is not False or accept_encoding != "identity":
            raise ValueError("redirect or encoding contract is invalid")
        if type(maximum_response_bytes) is not int or (
            maximum_response_bytes != OUTSCRAPER_MAX_RESPONSE_BYTES
        ):
            raise ValueError("response limit is invalid")
        return validated_url, validated_params, validated_key
    except (AttributeError, TypeError, UnicodeError, ValueError):
        _raise_invalid_execution()


def _response_header(response: requests.Response, name: str) -> str | None:
    value = response.headers.get(name)
    if value is None:
        return None
    if (
        type(value) is not str
        or not value
        or len(value) > _MAX_HEADER_VALUE_CODEPOINTS
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    ):
        _raise_invalid_response()
    return value


def _content_length(response: requests.Response) -> int | None:
    value = _response_header(response, "Content-Length")
    if value is None:
        return None
    if len(value) > _MAX_CONTENT_LENGTH_DIGITS or not value.isascii() or not value.isdecimal():
        _raise_invalid_response()
    return int(value)


def _is_json_content_type(value: str | None) -> bool:
    if value is None or len(value) > _MAX_HEADER_VALUE_CODEPOINTS:
        return False
    parts = [part.strip().casefold() for part in value.split(";")]
    if parts[0] != "application/json" or any(not part for part in parts):
        return False
    parameters: dict[str, str] = {}
    for part in parts[1:]:
        name, separator, parameter_value = part.partition("=")
        if separator != "=" or name in parameters:
            return False
        parameters[name] = parameter_value.strip('"')
    return not parameters or parameters == {"charset": "utf-8"}


def _should_read_body(
    *,
    status_code: int,
    content_type: str | None,
    content_encoding: str | None,
    content_length: int | None,
    maximum_response_bytes: int,
) -> bool:
    if status_code not in {200, 202} or not _is_json_content_type(content_type):
        return False
    if content_encoding is not None and content_encoding.casefold() != "identity":
        return False
    return content_length is None or content_length <= maximum_response_bytes


def _read_body(
    response: requests.Response,
    *,
    maximum_response_bytes: int,
) -> tuple[bytes, ...]:
    body = bytearray()
    try:
        for chunk in response.iter_content(
            chunk_size=_STREAM_CHUNK_BYTES,
            decode_unicode=False,
        ):
            if not chunk:
                continue
            if type(chunk) is not bytes:
                _raise_invalid_response()
            if len(body) + len(chunk) > maximum_response_bytes:
                _raise_invalid_response()
            body.extend(chunk)
    except OutscraperExecutionError:
        raise
    except Exception:
        _raise_transport_failed()
    return (bytes(body),) if body else ()


def _project_response(
    response: requests.Response,
    *,
    maximum_response_bytes: int,
) -> OutscraperHttpResponse:
    status_code = response.status_code
    if type(status_code) is not int or not 100 <= status_code <= 599:
        _raise_invalid_response()

    content_type = _response_header(response, "Content-Type")
    content_encoding = _response_header(response, "Content-Encoding")
    content_length = _content_length(response)
    body_chunks: tuple[bytes, ...] = ()
    if _should_read_body(
        status_code=status_code,
        content_type=content_type,
        content_encoding=content_encoding,
        content_length=content_length,
        maximum_response_bytes=maximum_response_bytes,
    ):
        body_chunks = _read_body(
            response,
            maximum_response_bytes=maximum_response_bytes,
        )
    return OutscraperHttpResponse(
        status_code=status_code,
        content_type=content_type,
        content_length=content_length,
        content_encoding=content_encoding,
        body_chunks=body_chunks,
    )


def _configure_session(session: requests.Session) -> None:
    session.trust_env = False
    session.headers.clear()
    session.cookies.clear()
    session.proxies.clear()
    session.auth = None
    session.mount("http://", HTTPAdapter(max_retries=0))
    session.mount("https://", HTTPAdapter(max_retries=0))


def _close_response(response: requests.Response) -> None:
    if response._content_consumed:
        response.raw.close()
    response.close()


class RequestsOutscraperTransport:
    """Send one isolated Outscraper GET without retaining credential or session state."""

    def get(
        self,
        *,
        url: str,
        params: tuple[tuple[str, str], ...],
        api_key: str,
        timeout_seconds: int,
        allow_redirects: Literal[False],
        accept_encoding: Literal["identity"],
        maximum_response_bytes: int,
    ) -> OutscraperHttpResponse:
        validated_url, validated_params, validated_key = _validate_transport_contract(
            url=url,
            params=params,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            allow_redirects=allow_redirects,
            accept_encoding=accept_encoding,
            maximum_response_bytes=maximum_response_bytes,
        )
        headers = dict(OUTSCRAPER_REQUEST_HEADERS)
        headers["X-API-KEY"] = validated_key

        try:
            session = requests.Session()
            response: requests.Response | None = None
            try:
                _configure_session(session)
                response = session.request(
                    method="GET",
                    url=validated_url,
                    params=validated_params,
                    headers=headers,
                    timeout=(timeout_seconds, timeout_seconds),
                    allow_redirects=False,
                    stream=True,
                    verify=True,
                    proxies={},
                )
                if not isinstance(response, requests.Response):
                    _raise_transport_failed()
                return _project_response(
                    response,
                    maximum_response_bytes=maximum_response_bytes,
                )
            finally:
                if response is not None:
                    try:
                        _close_response(response)
                    finally:
                        session.close()
                else:
                    session.close()
        except OutscraperExecutionError:
            raise
        except Exception:
            _raise_transport_failed()


def _validated_execution_context(
    permit: object,
    *,
    usage_ledger: object,
    usage_reservation: object,
) -> tuple[OutscraperAmazonProductsRequest, SearchSessionSnapshot, UsageReservation]:
    try:
        if type(permit) is not AuthorizedOutscraperRequest:
            raise TypeError("execution permit type is invalid")
        request = OutscraperAmazonProductsRequest.model_validate(permit.request)
        session = SearchSessionSnapshot.model_validate(permit.session)
        reservation = UsageReservation.model_validate(usage_reservation)
        if not isinstance(usage_ledger, InMemoryUsageLedger):
            raise TypeError("usage ledger type is invalid")
        if (
            type(permit.approval_plan_sha256) is not str
            or _DIGEST_PATTERN.fullmatch(permit.approval_plan_sha256) is None
            or type(permit.reservation_id) is not str
            or type(permit.authorized_at) is not datetime
            or permit.authorized_at.tzinfo is None
            or permit.authorized_at.utcoffset() != timedelta(0)
            or session.state != "scrape_submitted"
            or session.approval is None
            or session.approval.consumed_at is None
            or session.approval.consumed_at != permit.authorized_at
            or not hmac.compare_digest(
                session.approval.plan_sha256,
                permit.approval_plan_sha256,
            )
            or not hmac.compare_digest(
                request.query_plan_sha256,
                session.query_plan_sha256 or "",
            )
            or reservation.status != "started"
            or reservation.provider != "outscraper"
            or reservation.operation != "product_search"
            or reservation.amount.calls != 1
            or reservation.amount.tokens != 0
            or reservation.owner_id != session.owner_id
            or reservation.session_id != session.session_id
            or reservation.reservation_id != permit.reservation_id
            or not hmac.compare_digest(
                reservation.binding_sha256,
                permit.approval_plan_sha256,
            )
        ):
            raise ValueError("execution binding is invalid")
        current = next(
            (
                item
                for item in usage_ledger.snapshot().reservations
                if item.reservation_id == reservation.reservation_id
            ),
            None,
        )
        if current != reservation:
            raise ValueError("usage reservation is not current")
        return request, session, reservation
    except (AttributeError, TypeError, ValidationError, ValueError):
        _raise_invalid_execution()


def _finish_usage(
    usage_ledger: InMemoryUsageLedger,
    reservation: UsageReservation,
    *,
    success: bool,
    now: Callable[[], datetime],
) -> UsageReservation:
    try:
        finished = usage_ledger.finish(
            reservation.reservation_id,
            owner_id=reservation.owner_id,
            session_id=reservation.session_id,
            success=success,
            now=now(),
        )
        if (
            finished.status != ("succeeded" if success else "failed")
            or finished.request != reservation.request
            or finished.usage_policy_sha256 != reservation.usage_policy_sha256
        ):
            raise ValueError("finished reservation changed its binding")
        return finished
    except Exception:
        _raise_transport_failed()


def _transport_get(
    transport: OutscraperRequestTransport,
    *,
    url: str,
    params: tuple[tuple[str, str], ...],
    api_key: str,
) -> OutscraperHttpResponse:
    try:
        return transport.get(
            url=url,
            params=params,
            api_key=api_key,
            timeout_seconds=OUTSCRAPER_REQUEST_TIMEOUT_SECONDS,
            allow_redirects=False,
            accept_encoding="identity",
            maximum_response_bytes=OUTSCRAPER_MAX_RESPONSE_BYTES,
        )
    except OutscraperExecutionError:
        raise
    except Exception:
        _raise_transport_failed()


def _validated_content_type(value: object) -> None:
    if type(value) is not str or not _is_json_content_type(value):
        _raise_invalid_response()


def _response_body(response: object) -> bytes:
    if not isinstance(response, OutscraperHttpResponse):
        _raise_invalid_response()
    if type(response.status_code) is not int:
        _raise_invalid_response()
    if 300 <= response.status_code < 400:
        _raise_invalid_location()
    if response.status_code == 204:
        _raise_task_failed()
    if response.status_code not in {200, 202}:
        _raise_transport_failed()

    _validated_content_type(response.content_type)
    if response.content_encoding is not None and (
        type(response.content_encoding) is not str
        or response.content_encoding.casefold() != "identity"
    ):
        _raise_invalid_response()
    if response.content_length is not None and (
        type(response.content_length) is not int
        or response.content_length < 0
        or response.content_length > OUTSCRAPER_MAX_RESPONSE_BYTES
    ):
        _raise_invalid_response()

    chunks: list[bytes] = []
    total = 0
    try:
        for chunk in response.body_chunks:
            if type(chunk) is not bytes:
                _raise_invalid_response()
            total += len(chunk)
            if total > OUTSCRAPER_MAX_RESPONSE_BYTES:
                _raise_invalid_response()
            chunks.append(chunk)
    except OutscraperExecutionError:
        raise
    except Exception:
        _raise_invalid_response()
    if response.content_length is not None and response.content_length != total:
        _raise_invalid_response()
    if total == 0:
        _raise_invalid_response()
    return b"".join(chunks)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("duplicate JSON key")
        result[name] = value
    return result


def _reject_non_finite_constant(_value: str) -> None:
    raise ValueError("non-finite JSON number")


def _response_payload(response: object) -> dict[str, Any]:
    body = _response_body(response)
    try:
        payload = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite_constant,
        )
    except (UnicodeError, ValueError):
        _raise_invalid_response()
    if type(payload) is not dict:
        _raise_invalid_response()
    return payload


def _provider_request_id(payload: dict[str, Any], *, expected: str | None = None) -> str:
    value = payload.get("id")
    if (
        type(value) is not str
        or len(value) > _MAX_PROVIDER_REQUEST_ID_CHARACTERS
        or _RESULT_PATH_PATTERN.fullmatch(f"/requests/{value}") is None
    ):
        _raise_invalid_response()
    if expected is not None and not hmac.compare_digest(value, expected):
        _raise_invalid_response()
    return value


def _task_status(payload: dict[str, Any]) -> Literal["pending", "success"]:
    value = payload.get("status")
    if type(value) is not str or value != value.strip() or len(value) > 32:
        _raise_invalid_response()
    status = value.casefold()
    if status == "failure":
        _raise_task_failed()
    if status == "pending":
        if "data" in payload:
            _raise_invalid_response()
        return "pending"
    if status == "success":
        return "success"
    _raise_invalid_response()


def _completed_data(
    payload: dict[str, Any],
    *,
    maximum_candidates: int,
) -> list[object]:
    data = payload.get("data")
    if type(data) is not list:
        _raise_invalid_response()
    candidate_count = 0
    for group in data:
        candidate_count += len(group) if type(group) is list else 1
        if candidate_count > maximum_candidates:
            _raise_invalid_response()
    return data


def _validated_results_location(
    value: object,
    *,
    endpoint: str,
    provider_request_id: str,
) -> str:
    try:
        result_url, result_host, result_port, result_path = _canonical_https_url(value)
        endpoint_url, endpoint_host, endpoint_port, endpoint_path = _canonical_https_url(endpoint)
        if endpoint_path != "/amazon-products":
            raise ValueError("endpoint path is invalid")
        expected_path = f"/requests/{provider_request_id}"
        if (
            result_host != endpoint_host
            or result_port != endpoint_port
            or result_path != expected_path
            or result_url != (f"https://{urlsplit(endpoint_url).netloc}{expected_path}")
        ):
            raise ValueError("result location binding is invalid")
        return result_url
    except (AttributeError, TypeError, UnicodeError, ValueError):
        _raise_invalid_location()


def _execute_task(
    request: OutscraperAmazonProductsRequest,
    *,
    api_key: str,
    transport: OutscraperRequestTransport,
    sleep: Callable[[int], None],
) -> tuple[str, list[object], int]:
    initial = _response_payload(
        _transport_get(
            transport,
            url=request.endpoint,
            params=request.query_parameters(),
            api_key=api_key,
        )
    )
    request_id = _provider_request_id(initial)
    state = _task_status(initial)
    if state == "success":
        return (
            request_id,
            _completed_data(
                initial,
                maximum_candidates=request.maximum_candidates,
            ),
            0,
        )

    results_location = _validated_results_location(
        initial.get("results_location"),
        endpoint=request.endpoint,
        provider_request_id=request_id,
    )
    for poll_count in range(1, OUTSCRAPER_MAX_POLLS + 1):
        payload = _response_payload(
            _transport_get(
                transport,
                url=results_location,
                params=(),
                api_key=api_key,
            )
        )
        _provider_request_id(payload, expected=request_id)
        state = _task_status(payload)
        if state == "success":
            return (
                request_id,
                _completed_data(
                    payload,
                    maximum_candidates=request.maximum_candidates,
                ),
                poll_count,
            )
        if poll_count < OUTSCRAPER_MAX_POLLS:
            try:
                sleep(OUTSCRAPER_POLL_INTERVAL_SECONDS)
            except Exception:
                _raise_transport_failed()
    _raise_polling_timeout()


def execute_outscraper_request(
    permit: AuthorizedOutscraperRequest,
    *,
    usage_ledger: InMemoryUsageLedger,
    usage_reservation: UsageReservation,
    api_key: str,
    transport: OutscraperRequestTransport,
    now: Callable[[], datetime],
    sleep: Callable[[int], None],
) -> OutscraperProductExecution:
    """Execute one authorized task creation and its bounded result polling lifecycle."""
    request, _session, reservation = _validated_execution_context(
        permit,
        usage_ledger=usage_ledger,
        usage_reservation=usage_reservation,
    )
    if not callable(now) or not callable(sleep) or not callable(getattr(transport, "get", None)):
        _raise_invalid_execution()
    try:
        validated_key = _validated_api_key(api_key)
    except (AttributeError, TypeError, UnicodeError, ValueError):
        _finish_usage(
            usage_ledger,
            reservation,
            success=False,
            now=now,
        )
        _raise_invalid_execution()

    try:
        request_id, data, polls_performed = _execute_task(
            request,
            api_key=validated_key,
            transport=transport,
            sleep=sleep,
        )
    except OutscraperExecutionError:
        _finish_usage(
            usage_ledger,
            reservation,
            success=False,
            now=now,
        )
        raise
    except Exception:
        _finish_usage(
            usage_ledger,
            reservation,
            success=False,
            now=now,
        )
        _raise_transport_failed()

    finished = _finish_usage(
        usage_ledger,
        reservation,
        success=True,
        now=now,
    )
    return OutscraperProductExecution(
        request=request,
        provider_request_id=request_id,
        response={"data": data},
        polls_performed=polls_performed,
        usage_reservation=finished,
    )
