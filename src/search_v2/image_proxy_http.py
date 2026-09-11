from __future__ import annotations

import http.client
import ipaddress
import re
import socket
import ssl
from typing import Literal
from urllib.parse import urlsplit

from src.search_v2.image_proxy import IMAGE_PROXY_ALLOWED_CONTENT_TYPES
from src.search_v2.image_proxy import IMAGE_PROXY_MAX_BYTES
from src.search_v2.image_proxy import IMAGE_PROXY_MAX_DNS_ADDRESSES
from src.search_v2.image_proxy import IMAGE_PROXY_MAX_URL_CHARACTERS
from src.search_v2.image_proxy import IMAGE_PROXY_TIMEOUT_SECONDS
from src.search_v2.image_proxy import ImageProxyHttpResponse


_HTTPS_PORT = 443
_STREAM_CHUNK_BYTES = 65_536
_MAX_RESPONSE_HEADERS = 64
_MAX_RESPONSE_HEADER_BYTES = 65_536
_MAX_HEADER_NAME_CHARACTERS = 128
_MAX_HEADER_VALUE_CHARACTERS = 8_192
_MAX_CONTENT_LENGTH_DIGITS = 20
_HEADER_NAME_PATTERN = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
_CONTENT_CODING_PATTERN = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
_DNS_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")

_INVALID_REQUEST_MESSAGE = "image HTTPS transport request is invalid"
_TRANSPORT_FAILED_MESSAGE = "image HTTPS transport failed"


class ImageProxyTransportError(RuntimeError):
    """Fixed, non-sensitive error from the pinned image HTTPS adapter."""


def _raise_invalid_request() -> None:
    raise ImageProxyTransportError(_INVALID_REQUEST_MESSAGE) from None


def _raise_transport_failed() -> None:
    raise ImageProxyTransportError(_TRANSPORT_FAILED_MESSAGE) from None


def _is_canonical_host(host: object) -> bool:
    if type(host) is not str or not host or len(host) > 253 or host != host.lower():
        return False
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return False
    labels = host.split(".")
    return len(labels) >= 2 and all(_DNS_LABEL_PATTERN.fullmatch(label) for label in labels)


def _validated_url(value: object) -> tuple[str, str]:
    if (
        type(value) is not str
        or not value
        or len(value) > IMAGE_PROXY_MAX_URL_CHARACTERS
        or any(ord(character) <= 0x20 or ord(character) == 0x7F for character in value)
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
        or port not in (None, _HTTPS_PORT)
        or parsed.fragment
        or not _is_canonical_host(host)
        or parsed.netloc not in {host, f"{host}:{_HTTPS_PORT}"}
        or (parsed.path and not parsed.path.startswith("/"))
    ):
        raise ValueError("URL is invalid")

    target = parsed.path or "/"
    if parsed.query:
        target = f"{target}?{parsed.query}"
    return host, target


def _validated_addresses(
    value: object,
) -> tuple[ipaddress.IPv4Address | ipaddress.IPv6Address, ...]:
    if type(value) is not tuple or not 1 <= len(value) <= IMAGE_PROXY_MAX_DNS_ADDRESSES:
        raise ValueError("addresses are invalid")

    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    seen: set[str] = set()
    for raw_address in value:
        if type(raw_address) is not str:
            raise ValueError("address is invalid")
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError as exc:
            raise ValueError("address is invalid") from exc
        if not address.is_global or raw_address != address.compressed or raw_address in seen:
            raise ValueError("address is invalid")
        seen.add(raw_address)
        addresses.append(address)
    return tuple(addresses)


def _validate_transport_contract(
    *,
    url: object,
    resolved_addresses: object,
    timeout_seconds: object,
    allow_redirects: object,
    accept_encoding: object,
    maximum_response_bytes: object,
) -> tuple[str, str, tuple[ipaddress.IPv4Address | ipaddress.IPv6Address, ...]]:
    try:
        host, target = _validated_url(url)
        addresses = _validated_addresses(resolved_addresses)
        if type(timeout_seconds) is not int or timeout_seconds != IMAGE_PROXY_TIMEOUT_SECONDS:
            raise ValueError("timeout is invalid")
        if allow_redirects is not False or accept_encoding != "identity":
            raise ValueError("HTTP behavior is invalid")
        if (
            type(maximum_response_bytes) is not int
            or maximum_response_bytes != IMAGE_PROXY_MAX_BYTES
        ):
            raise ValueError("response limit is invalid")
        return host, target, addresses
    except (AttributeError, TypeError, UnicodeError, ValueError):
        _raise_invalid_request()


def _secure_tls_context() -> ssl.SSLContext:
    try:
        context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.options |= ssl.OP_NO_COMPRESSION
        context.set_alpn_protocols(["http/1.1"])
        if context.check_hostname is not True or context.verify_mode != ssl.CERT_REQUIRED:
            _raise_transport_failed()
        return context
    except ImageProxyTransportError:
        raise
    except Exception:
        _raise_transport_failed()


def _connection_address(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> tuple[object, ...]:
    if isinstance(address, ipaddress.IPv6Address):
        return (address.compressed, _HTTPS_PORT, 0, 0)
    return (address.compressed, _HTTPS_PORT)


def _request_bytes(*, host: str, target: str) -> bytes:
    accept = ", ".join(IMAGE_PROXY_ALLOWED_CONTENT_TYPES)
    return (
        f"GET {target} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Accept: {accept}\r\n"
        "Accept-Encoding: identity\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("ascii")


def _validated_peer_ip(peer: object, expected: str) -> str:
    if type(peer) is not tuple or len(peer) < 2:
        _raise_transport_failed()
    raw_address, port = peer[0], peer[1]
    if type(raw_address) is not str or type(port) is not int or port != _HTTPS_PORT:
        _raise_transport_failed()
    try:
        address = ipaddress.ip_address(raw_address)
    except ValueError:
        _raise_transport_failed()
    if not address.is_global or address.compressed != expected:
        _raise_transport_failed()
    return address.compressed


def _validated_headers(response: http.client.HTTPResponse) -> dict[str, list[str]]:
    try:
        raw_headers = response.getheaders()
    except Exception:
        _raise_transport_failed()
    if type(raw_headers) is not list or len(raw_headers) > _MAX_RESPONSE_HEADERS:
        _raise_transport_failed()

    headers: dict[str, list[str]] = {}
    total_bytes = 0
    for item in raw_headers:
        if type(item) is not tuple or len(item) != 2:
            _raise_transport_failed()
        name, value = item
        if (
            type(name) is not str
            or type(value) is not str
            or not name
            or len(name) > _MAX_HEADER_NAME_CHARACTERS
            or len(value) > _MAX_HEADER_VALUE_CHARACTERS
            or _HEADER_NAME_PATTERN.fullmatch(name) is None
            or any(ord(character) < 0x20 or ord(character) > 0x7E for character in value)
        ):
            _raise_transport_failed()
        total_bytes += len(name) + len(value) + 4
        if total_bytes > _MAX_RESPONSE_HEADER_BYTES:
            _raise_transport_failed()
        headers.setdefault(name.casefold(), []).append(value)
    return headers


def _single_header(headers: dict[str, list[str]], name: str) -> str | None:
    values = headers.get(name.casefold(), [])
    if len(values) > 1:
        _raise_transport_failed()
    return values[0] if values else None


def _content_length(headers: dict[str, list[str]]) -> int | None:
    value = _single_header(headers, "Content-Length")
    if value is None:
        return None
    if len(value) > _MAX_CONTENT_LENGTH_DIGITS or not value.isascii() or not value.isdecimal():
        _raise_transport_failed()
    return int(value)


def _response_metadata(
    response: http.client.HTTPResponse,
) -> tuple[int, str | None, int | None, str | None]:
    status_code = response.status
    version = response.version
    if (
        type(status_code) is not int
        or not 100 <= status_code <= 599
        or type(version) is not int
        or version not in {10, 11}
    ):
        _raise_transport_failed()

    headers = _validated_headers(response)
    content_type = _single_header(headers, "Content-Type")
    content_encoding = _single_header(headers, "Content-Encoding")
    content_length = _content_length(headers)
    transfer_encoding = _single_header(headers, "Transfer-Encoding")
    if content_encoding is not None and (
        not content_encoding.strip()
        or _CONTENT_CODING_PATTERN.fullmatch(content_encoding.strip()) is None
    ):
        _raise_transport_failed()
    if transfer_encoding is not None:
        if transfer_encoding.strip().casefold() != "chunked" or content_length is not None:
            _raise_transport_failed()
    return status_code, content_type, content_length, content_encoding


def _is_allowed_content_type(value: str | None) -> bool:
    if value is None:
        return False
    return value.split(";", maxsplit=1)[0].strip().casefold() in IMAGE_PROXY_ALLOWED_CONTENT_TYPES


def _should_read_body(
    *,
    status_code: int,
    content_type: str | None,
    content_length: int | None,
    content_encoding: str | None,
    maximum_response_bytes: int,
) -> bool:
    if status_code != 200 or not _is_allowed_content_type(content_type):
        return False
    if content_encoding is not None and content_encoding.strip().casefold() not in {"", "identity"}:
        return False
    return content_length is None or content_length <= maximum_response_bytes


def _read_body(
    response: http.client.HTTPResponse,
    *,
    maximum_response_bytes: int,
) -> tuple[bytes, ...]:
    body = bytearray()
    while True:
        read_size = min(_STREAM_CHUNK_BYTES, maximum_response_bytes - len(body) + 1)
        chunk = response.read(read_size)
        if type(chunk) is not bytes:
            _raise_transport_failed()
        if not chunk:
            break
        if len(body) + len(chunk) > maximum_response_bytes:
            _raise_transport_failed()
        body.extend(chunk)
    return (bytes(body),) if body else ()


def _project_response(
    response: http.client.HTTPResponse,
    *,
    peer_ip: str,
    maximum_response_bytes: int,
) -> ImageProxyHttpResponse:
    status_code, content_type, content_length, content_encoding = _response_metadata(response)
    body_chunks: tuple[bytes, ...] = ()
    if _should_read_body(
        status_code=status_code,
        content_type=content_type,
        content_length=content_length,
        content_encoding=content_encoding,
        maximum_response_bytes=maximum_response_bytes,
    ):
        body_chunks = _read_body(response, maximum_response_bytes=maximum_response_bytes)
    return ImageProxyHttpResponse(
        status_code=status_code,
        peer_ip=peer_ip,
        content_type=content_type,
        content_length=content_length,
        content_encoding=content_encoding,
        body_chunks=body_chunks,
    )


def _close(resource: object | None) -> bool:
    if resource is None:
        return False
    try:
        resource.close()  # type: ignore[attr-defined]
    except Exception:
        return True
    return False


class PinnedHttpsImageTransport:
    """Fetch one image through a single pinned-IP TLS connection."""

    def fetch_https(
        self,
        *,
        url: str,
        resolved_addresses: tuple[str, ...],
        timeout_seconds: int,
        allow_redirects: Literal[False],
        accept_encoding: Literal["identity"],
        maximum_response_bytes: int,
    ) -> ImageProxyHttpResponse:
        host, target, addresses = _validate_transport_contract(
            url=url,
            resolved_addresses=resolved_addresses,
            timeout_seconds=timeout_seconds,
            allow_redirects=allow_redirects,
            accept_encoding=accept_encoding,
            maximum_response_bytes=maximum_response_bytes,
        )
        context = _secure_tls_context()
        selected_address = addresses[0]

        raw_socket: object | None = None
        tls_socket: object | None = None
        response: object | None = None
        projected: ImageProxyHttpResponse | None = None
        failed = False
        try:
            family = (
                socket.AF_INET6
                if isinstance(selected_address, ipaddress.IPv6Address)
                else socket.AF_INET
            )
            raw_socket = socket.socket(family, socket.SOCK_STREAM, socket.IPPROTO_TCP)
            raw_socket.settimeout(timeout_seconds)  # type: ignore[attr-defined]
            raw_socket.connect(_connection_address(selected_address))  # type: ignore[attr-defined]
            tls_socket = context.wrap_socket(
                raw_socket,
                server_hostname=host,
                do_handshake_on_connect=True,
            )
            tls_socket.settimeout(timeout_seconds)  # type: ignore[attr-defined]
            peer_ip = _validated_peer_ip(tls_socket.getpeername(), selected_address.compressed)  # type: ignore[attr-defined]
            tls_socket.sendall(_request_bytes(host=host, target=target))  # type: ignore[attr-defined]

            response = http.client.HTTPResponse(tls_socket)  # type: ignore[arg-type]
            response.begin()  # type: ignore[attr-defined]
            projected = _project_response(
                response,  # type: ignore[arg-type]
                peer_ip=peer_ip,
                maximum_response_bytes=maximum_response_bytes,
            )
        except Exception:
            failed = True
        finally:
            close_failed = _close(response)
            close_failed = _close(tls_socket) or close_failed
            close_failed = _close(raw_socket) or close_failed
            failed = failed or close_failed

        if failed or projected is None:
            _raise_transport_failed()
        return projected
