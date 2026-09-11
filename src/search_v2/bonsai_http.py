from __future__ import annotations

from typing import Literal

import requests
from requests.adapters import HTTPAdapter

from src.exceptions import BonsaiRequestError
from src.exceptions import BonsaiResponseError
from src.search_v2.bonsai_request import BONSAI_MAX_RESPONSE_BYTES
from src.search_v2.bonsai_request import BONSAI_REQUEST_HEADERS
from src.search_v2.bonsai_request import BonsaiHttpResponse
from src.search_v2.bonsai_request import _validated_content_type
from src.search_v2.bonsai_request import _validated_endpoint


_STREAM_CHUNK_BYTES = 65_536
_MAX_HEADER_VALUE_CODEPOINTS = 200
_MAX_CONTENT_LENGTH_DIGITS = 20
_INVALID_REQUEST_MESSAGE = "Bonsai HTTP transport request is invalid"
_TRANSPORT_FAILED_MESSAGE = "Bonsai HTTP transport failed"


def _raise_invalid_request() -> None:
    raise BonsaiRequestError(_INVALID_REQUEST_MESSAGE) from None


def _raise_transport_failed() -> None:
    raise BonsaiRequestError(_TRANSPORT_FAILED_MESSAGE) from None


def _validate_transport_contract(
    *,
    url: object,
    headers: object,
    body: object,
    allow_redirects: object,
    accept_encoding: object,
    maximum_response_bytes: object,
) -> None:
    try:
        if type(url) is not str or _validated_endpoint(url) != url:
            raise ValueError("transport URL is invalid")
        if type(headers) is not tuple or headers != BONSAI_REQUEST_HEADERS:
            raise ValueError("transport headers are invalid")
        if type(body) is not bytes or not body or len(body) > BONSAI_MAX_RESPONSE_BYTES:
            raise ValueError("transport body is invalid")
        if allow_redirects is not False or accept_encoding != "identity":
            raise ValueError("transport behavior is invalid")
        if (
            type(maximum_response_bytes) is not int
            or maximum_response_bytes != BONSAI_MAX_RESPONSE_BYTES
        ):
            raise ValueError("transport response limit is invalid")
    except (AttributeError, TypeError, ValueError):
        _raise_invalid_request()


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
        _raise_transport_failed()
    return value


def _content_length(response: requests.Response) -> int | None:
    value = _response_header(response, "Content-Length")
    if value is None:
        return None
    if len(value) > _MAX_CONTENT_LENGTH_DIGITS or not value.isascii() or not value.isdecimal():
        _raise_transport_failed()
    return int(value)


def _should_read_body(
    *,
    status_code: int,
    content_type: str | None,
    content_encoding: str | None,
    content_length: int | None,
    maximum_response_bytes: int,
) -> bool:
    if status_code != 200:
        return False
    try:
        _validated_content_type(content_type)
    except BonsaiResponseError:
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
    for chunk in response.iter_content(
        chunk_size=_STREAM_CHUNK_BYTES,
        decode_unicode=False,
    ):
        if not chunk:
            continue
        if type(chunk) is not bytes:
            _raise_transport_failed()
        if len(body) + len(chunk) > maximum_response_bytes:
            _raise_transport_failed()
        body.extend(chunk)
    return (bytes(body),) if body else ()


def _project_response(
    response: requests.Response,
    *,
    maximum_response_bytes: int,
) -> BonsaiHttpResponse:
    status_code = response.status_code
    if type(status_code) is not int or not 100 <= status_code <= 599:
        _raise_transport_failed()

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

    return BonsaiHttpResponse(
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


class RequestsBonsaiTransport:
    """Send one validated Bonsai request without retaining HTTP session state."""

    def post_json(
        self,
        *,
        url: str,
        headers: tuple[tuple[str, str], ...],
        body: bytes,
        allow_redirects: Literal[False],
        accept_encoding: Literal["identity"],
        maximum_response_bytes: int,
    ) -> BonsaiHttpResponse:
        _validate_transport_contract(
            url=url,
            headers=headers,
            body=body,
            allow_redirects=allow_redirects,
            accept_encoding=accept_encoding,
            maximum_response_bytes=maximum_response_bytes,
        )

        try:
            session = requests.Session()
            response: requests.Response | None = None
            try:
                _configure_session(session)
                response = session.request(
                    method="POST",
                    url=url,
                    headers=dict(headers),
                    data=body,
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
                        response.close()
                    finally:
                        session.close()
                else:
                    session.close()
        except BonsaiRequestError:
            raise
        except Exception:
            _raise_transport_failed()
