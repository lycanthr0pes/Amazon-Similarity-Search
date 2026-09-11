import ast
import http.client
import inspect
import io
import socket
import ssl
from pathlib import Path

import pytest
from PIL import Image

import src.search_v2.image_proxy_http as image_proxy_http
from src.search_v2.image_proxy import IMAGE_PROXY_MAX_BYTES
from src.search_v2.image_proxy import IMAGE_PROXY_TIMEOUT_SECONDS
from src.search_v2.image_proxy import ImageProxyError
from src.search_v2.image_proxy import ImageProxyPolicy
from src.search_v2.image_proxy import fetch_proxy_image
from src.search_v2.image_proxy_http import ImageProxyTransportError
from src.search_v2.image_proxy_http import PinnedHttpsImageTransport


ALLOWED_HOST = "images.example.test"
PUBLIC_IPV4 = "93.184.216.34"
SECOND_PUBLIC_IPV4 = "8.8.8.8"
PUBLIC_IPV6 = "2001:4860:4860::8888"
SOURCE_URL = f"https://{ALLOWED_HOST}/catalog/item.png?size=large"


def png_bytes(color: tuple[int, int, int] = (12, 34, 56)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (2, 2), color).save(output, format="PNG")
    return output.getvalue()


class FakeRawSocket:
    def __init__(self, *, connect_error: Exception | None = None) -> None:
        self.connect_error = connect_error
        self.timeouts: list[int] = []
        self.connections: list[tuple[object, ...]] = []
        self.close_calls = 0

    def settimeout(self, timeout: int) -> None:
        self.timeouts.append(timeout)

    def connect(self, address: tuple[object, ...]) -> None:
        self.connections.append(address)
        if self.connect_error is not None:
            raise self.connect_error

    def close(self) -> None:
        self.close_calls += 1


class RecordingSocketFactory:
    def __init__(self, raw_socket: FakeRawSocket) -> None:
        self.raw_socket = raw_socket
        self.calls: list[tuple[int, int, int]] = []

    def __call__(self, family: int, kind: int, protocol: int) -> FakeRawSocket:
        self.calls.append((family, kind, protocol))
        return self.raw_socket


class FakeTlsSocket:
    def __init__(
        self,
        raw_socket: FakeRawSocket,
        *,
        peer_ip: str = PUBLIC_IPV4,
        send_error: Exception | None = None,
    ) -> None:
        self.raw_socket = raw_socket
        self.peer_ip = peer_ip
        self.send_error = send_error
        self.timeouts: list[int] = []
        self.sent: list[bytes] = []
        self.close_calls = 0

    def settimeout(self, timeout: int) -> None:
        self.timeouts.append(timeout)

    def getpeername(self) -> tuple[object, ...]:
        if ":" in self.peer_ip:
            return (self.peer_ip, 443, 0, 0)
        return (self.peer_ip, 443)

    def sendall(self, request: bytes) -> None:
        self.sent.append(request)
        if self.send_error is not None:
            raise self.send_error

    def close(self) -> None:
        self.close_calls += 1


class FakeTlsContext:
    def __init__(
        self,
        tls_socket: FakeTlsSocket,
        *,
        check_hostname: bool = True,
        verify_mode: ssl.VerifyMode = ssl.CERT_REQUIRED,
        wrap_error: Exception | None = None,
    ) -> None:
        self.tls_socket = tls_socket
        self.check_hostname = check_hostname
        self.verify_mode = verify_mode
        self.wrap_error = wrap_error
        self.minimum_version = ssl.TLSVersion.MINIMUM_SUPPORTED
        self.options = 0
        self.alpn_calls: list[list[str]] = []
        self.wrap_calls: list[dict[str, object]] = []

    def set_alpn_protocols(self, protocols: list[str]) -> None:
        self.alpn_calls.append(protocols)

    def wrap_socket(self, raw_socket, **kwargs) -> FakeTlsSocket:
        self.wrap_calls.append({"raw_socket": raw_socket, **kwargs})
        if self.wrap_error is not None:
            raise self.wrap_error
        return self.tls_socket


class RecordingContextFactory:
    def __init__(self, context: FakeTlsContext) -> None:
        self.context = context
        self.calls: list[ssl.Purpose] = []

    def __call__(self, *, purpose: ssl.Purpose) -> FakeTlsContext:
        self.calls.append(purpose)
        return self.context


class FakeHttpResponse:
    def __init__(
        self,
        *,
        body: bytes = b"",
        status: int = 200,
        version: int = 11,
        headers: list[tuple[str, str]] | None = None,
        begin_error: Exception | None = None,
        read_error: Exception | None = None,
        chunks: list[bytes] | None = None,
    ) -> None:
        self.status = status
        self.version = version
        self.headers = headers or [
            ("Content-Type", "image/png"),
            ("Content-Length", str(len(body))),
            ("Content-Encoding", "identity"),
        ]
        self.begin_error = begin_error
        self.read_error = read_error
        self.chunks = list(chunks) if chunks is not None else [body]
        self.begin_calls = 0
        self.read_sizes: list[int] = []
        self.close_calls = 0

    def begin(self) -> None:
        self.begin_calls += 1
        if self.begin_error is not None:
            raise self.begin_error

    def getheaders(self) -> list[tuple[str, str]]:
        return list(self.headers)

    def read(self, amount: int) -> bytes:
        self.read_sizes.append(amount)
        if self.read_error is not None:
            raise self.read_error
        if not self.chunks:
            return b""
        return self.chunks.pop(0)

    def close(self) -> None:
        self.close_calls += 1


class RecordingResponseFactory:
    def __init__(self, response: FakeHttpResponse) -> None:
        self.response = response
        self.calls: list[FakeTlsSocket] = []

    def __call__(self, tls_socket: FakeTlsSocket) -> FakeHttpResponse:
        self.calls.append(tls_socket)
        return self.response


def install_fixtures(
    monkeypatch: pytest.MonkeyPatch,
    *,
    body: bytes | None = None,
    peer_ip: str = PUBLIC_IPV4,
    connect_error: Exception | None = None,
    send_error: Exception | None = None,
    wrap_error: Exception | None = None,
    check_hostname: bool = True,
    verify_mode: ssl.VerifyMode = ssl.CERT_REQUIRED,
    response: FakeHttpResponse | None = None,
):
    raw_socket = FakeRawSocket(connect_error=connect_error)
    tls_socket = FakeTlsSocket(raw_socket, peer_ip=peer_ip, send_error=send_error)
    context = FakeTlsContext(
        tls_socket,
        check_hostname=check_hostname,
        verify_mode=verify_mode,
        wrap_error=wrap_error,
    )
    socket_factory = RecordingSocketFactory(raw_socket)
    context_factory = RecordingContextFactory(context)
    http_response = response or FakeHttpResponse(body=body if body is not None else png_bytes())
    response_factory = RecordingResponseFactory(http_response)
    monkeypatch.setattr(image_proxy_http.socket, "socket", socket_factory)
    monkeypatch.setattr(image_proxy_http.ssl, "create_default_context", context_factory)
    monkeypatch.setattr(image_proxy_http.http.client, "HTTPResponse", response_factory)
    return raw_socket, tls_socket, context, socket_factory, context_factory, http_response


def transport_fetch(
    *,
    resolved_addresses: tuple[str, ...] = (PUBLIC_IPV4,),
    url: str = SOURCE_URL,
    timeout_seconds: int = IMAGE_PROXY_TIMEOUT_SECONDS,
    allow_redirects: bool = False,
    accept_encoding: str = "identity",
    maximum_response_bytes: int = IMAGE_PROXY_MAX_BYTES,
):
    return PinnedHttpsImageTransport().fetch_https(
        url=url,
        resolved_addresses=resolved_addresses,
        timeout_seconds=timeout_seconds,
        allow_redirects=allow_redirects,
        accept_encoding=accept_encoding,
        maximum_response_bytes=maximum_response_bytes,
    )


def test_connects_to_first_pinned_ip_with_original_host_tls_and_exact_get(monkeypatch) -> None:
    body = png_bytes(color=(10, 20, 30))
    raw, tls, context, sockets, contexts, response = install_fixtures(
        monkeypatch,
        body=body,
    )

    projected = transport_fetch(resolved_addresses=(PUBLIC_IPV4, SECOND_PUBLIC_IPV4))

    assert sockets.calls == [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)]
    assert raw.timeouts == [IMAGE_PROXY_TIMEOUT_SECONDS]
    assert raw.connections == [(PUBLIC_IPV4, 443)]
    assert contexts.calls == [ssl.Purpose.SERVER_AUTH]
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.minimum_version == ssl.TLSVersion.TLSv1_2
    assert context.options & ssl.OP_NO_COMPRESSION
    assert context.alpn_calls == [["http/1.1"]]
    assert context.wrap_calls == [
        {
            "raw_socket": raw,
            "server_hostname": ALLOWED_HOST,
            "do_handshake_on_connect": True,
        }
    ]
    assert tls.timeouts == [IMAGE_PROXY_TIMEOUT_SECONDS]
    assert tls.sent == [
        b"GET /catalog/item.png?size=large HTTP/1.1\r\n"
        b"Host: images.example.test\r\n"
        b"Accept: image/jpeg, image/png, image/webp\r\n"
        b"Accept-Encoding: identity\r\n"
        b"Connection: close\r\n\r\n"
    ]
    assert projected.status_code == 200
    assert projected.peer_ip == PUBLIC_IPV4
    assert projected.content_type == "image/png"
    assert projected.content_length == len(body)
    assert projected.content_encoding == "identity"
    assert projected.body_chunks == (body,)
    assert response.close_calls == 1
    assert tls.close_calls == 1
    assert raw.close_calls == 1


def test_fixture_transport_integrates_with_image_proxy_core_without_network(monkeypatch) -> None:
    body = png_bytes(color=(40, 50, 60))
    raw, tls, _context, _sockets, _contexts, response = install_fixtures(
        monkeypatch,
        body=body,
    )

    image = fetch_proxy_image(
        url=SOURCE_URL,
        policy=ImageProxyPolicy(schema_version="2.0", allowed_hosts=(ALLOWED_HOST,)),
        resolve_host=lambda host: (PUBLIC_IPV4,) if host == ALLOWED_HOST else (),
        transport=PinnedHttpsImageTransport(),
    )

    assert image.width == 2
    assert image.height == 2
    assert image.rgb_bytes == bytes((40, 50, 60)) * 4
    assert response.close_calls == 1
    assert tls.close_calls == 1
    assert raw.close_calls == 1


def test_uses_ipv6_socket_and_numeric_four_tuple(monkeypatch) -> None:
    raw, _tls, context, sockets, _contexts, _response = install_fixtures(
        monkeypatch,
        peer_ip=PUBLIC_IPV6,
    )

    projected = transport_fetch(resolved_addresses=(PUBLIC_IPV6,))

    assert sockets.calls == [(socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP)]
    assert raw.connections == [(PUBLIC_IPV6, 443, 0, 0)]
    assert context.wrap_calls[0]["server_hostname"] == ALLOWED_HOST
    assert projected.peer_ip == PUBLIC_IPV6


@pytest.mark.parametrize(
    "overrides",
    [
        {"url": f"http://{ALLOWED_HOST}/item.png"},
        {"url": f"https://user:password@{ALLOWED_HOST}/item.png"},
        {"url": f"https://{ALLOWED_HOST}:444/item.png"},
        {"url": f"https://{ALLOWED_HOST}/café.png"},
        {"resolved_addresses": ()},
        {"resolved_addresses": ("127.0.0.1",)},
        {"resolved_addresses": (PUBLIC_IPV4, PUBLIC_IPV4)},
        {"resolved_addresses": tuple(f"8.8.8.{index}" for index in range(1, 10))},
        {"timeout_seconds": IMAGE_PROXY_TIMEOUT_SECONDS - 1},
        {"allow_redirects": True},
        {"accept_encoding": "gzip"},
        {"maximum_response_bytes": IMAGE_PROXY_MAX_BYTES - 1},
    ],
)
def test_rejects_invalid_transport_contract_before_socket(monkeypatch, overrides) -> None:
    _raw, _tls, _context, sockets, contexts, response = install_fixtures(monkeypatch)

    with pytest.raises(
        ImageProxyTransportError,
        match="^image HTTPS transport request is invalid$",
    ) as error:
        transport_fetch(**overrides)

    assert SOURCE_URL not in str(error.value)
    assert sockets.calls == []
    assert contexts.calls == []
    assert response.begin_calls == 0


def test_connection_failure_is_not_retried_with_second_address(monkeypatch) -> None:
    raw, _tls, _context, sockets, _contexts, response = install_fixtures(
        monkeypatch,
        connect_error=OSError("synthetic connect failure"),
    )

    with pytest.raises(ImageProxyTransportError, match="^image HTTPS transport failed$"):
        transport_fetch(resolved_addresses=(PUBLIC_IPV4, SECOND_PUBLIC_IPV4))

    assert sockets.calls == [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)]
    assert raw.connections == [(PUBLIC_IPV4, 443)]
    assert raw.close_calls == 1
    assert response.begin_calls == 0


@pytest.mark.parametrize(
    ("check_hostname", "verify_mode"),
    [(False, ssl.CERT_REQUIRED), (True, ssl.CERT_NONE)],
)
def test_rejects_insecure_tls_context_before_socket(
    monkeypatch,
    check_hostname: bool,
    verify_mode: ssl.VerifyMode,
) -> None:
    _raw, _tls, _context, sockets, contexts, response = install_fixtures(
        monkeypatch,
        check_hostname=check_hostname,
        verify_mode=verify_mode,
    )

    with pytest.raises(ImageProxyTransportError, match="^image HTTPS transport failed$"):
        transport_fetch()

    assert contexts.calls == [ssl.Purpose.SERVER_AUTH]
    assert sockets.calls == []
    assert response.begin_calls == 0


def test_rejects_unpinned_tls_peer_before_sending_request(monkeypatch) -> None:
    raw, tls, _context, _sockets, _contexts, response = install_fixtures(
        monkeypatch,
        peer_ip=SECOND_PUBLIC_IPV4,
    )

    with pytest.raises(ImageProxyTransportError, match="^image HTTPS transport failed$"):
        transport_fetch()

    assert tls.sent == []
    assert response.begin_calls == 0
    assert tls.close_calls == 1
    assert raw.close_calls == 1


@pytest.mark.parametrize(
    ("response", "expected_status"),
    [
        (FakeHttpResponse(status=302, body=b"redirect"), 302),
        (
            FakeHttpResponse(
                body=b"not an image",
                headers=[("Content-Type", "text/html"), ("Content-Length", "12")],
            ),
            200,
        ),
        (
            FakeHttpResponse(
                body=b"compressed",
                headers=[
                    ("Content-Type", "image/png"),
                    ("Content-Length", "10"),
                    ("Content-Encoding", "gzip"),
                ],
            ),
            200,
        ),
        (
            FakeHttpResponse(
                body=b"oversized",
                headers=[
                    ("Content-Type", "image/png"),
                    ("Content-Length", str(IMAGE_PROXY_MAX_BYTES + 1)),
                ],
            ),
            200,
        ),
    ],
)
def test_does_not_read_rejected_or_declared_oversized_body(
    monkeypatch,
    response: FakeHttpResponse,
    expected_status: int,
) -> None:
    raw, tls, _context, _sockets, _contexts, installed = install_fixtures(
        monkeypatch,
        response=response,
    )

    projected = transport_fetch()

    assert projected.status_code == expected_status
    assert projected.body_chunks == ()
    assert installed.read_sizes == []
    assert installed.close_calls == 1
    assert tls.close_calls == 1
    assert raw.close_calls == 1


def test_accepts_chunked_body_without_content_length(monkeypatch) -> None:
    body = png_bytes()
    response = FakeHttpResponse(
        chunks=[body[:5], body[5:], b""],
        headers=[
            ("Content-Type", "image/png"),
            ("Content-Encoding", "identity"),
            ("Transfer-Encoding", "chunked"),
        ],
    )
    install_fixtures(monkeypatch, response=response)

    projected = transport_fetch()

    assert projected.content_length is None
    assert projected.body_chunks == (body,)


@pytest.mark.parametrize(
    "headers",
    [
        [("Content-Type", "image/png"), ("Content-Length", "1"), ("Content-Length", "1")],
        [
            ("Content-Type", "image/png"),
            ("Content-Length", "1"),
            ("Transfer-Encoding", "chunked"),
        ],
        [("Content-Type", "image/png"), ("Transfer-Encoding", "gzip")],
        [("Content-Type", "image/png"), ("Content-Encoding", "identity, gzip")],
        [("Content-Type", "image/png\r\nX-Injected: yes")],
        [("X-Test", "ok")] * 65,
    ],
)
def test_rejects_ambiguous_or_unbounded_response_headers(monkeypatch, headers) -> None:
    response = FakeHttpResponse(body=b"x", headers=headers)
    raw, tls, _context, _sockets, _contexts, installed = install_fixtures(
        monkeypatch,
        response=response,
    )

    with pytest.raises(ImageProxyTransportError, match="^image HTTPS transport failed$"):
        transport_fetch()

    assert installed.read_sizes == []
    assert installed.close_calls == 1
    assert tls.close_calls == 1
    assert raw.close_calls == 1


def test_rejects_stream_that_exceeds_limit_and_closes_every_resource(monkeypatch) -> None:
    response = FakeHttpResponse(
        chunks=[b"x" * IMAGE_PROXY_MAX_BYTES, b"y"],
        headers=[("Content-Type", "image/png")],
    )
    raw, tls, _context, _sockets, _contexts, installed = install_fixtures(
        monkeypatch,
        response=response,
    )

    with pytest.raises(ImageProxyTransportError, match="^image HTTPS transport failed$"):
        transport_fetch()

    assert len(installed.read_sizes) == 2
    assert installed.close_calls == 1
    assert tls.close_calls == 1
    assert raw.close_calls == 1


@pytest.mark.parametrize("failure_stage", ["wrap", "send", "begin", "read"])
def test_closes_created_resources_for_each_failure_stage(monkeypatch, failure_stage: str) -> None:
    response = FakeHttpResponse(
        body=b"x",
        begin_error=OSError("synthetic begin failure") if failure_stage == "begin" else None,
        read_error=OSError("synthetic read failure") if failure_stage == "read" else None,
    )
    raw, tls, _context, _sockets, _contexts, installed = install_fixtures(
        monkeypatch,
        wrap_error=OSError("synthetic TLS failure") if failure_stage == "wrap" else None,
        send_error=OSError("synthetic send failure") if failure_stage == "send" else None,
        response=response,
    )

    with pytest.raises(ImageProxyTransportError, match="^image HTTPS transport failed$"):
        transport_fetch()

    assert raw.close_calls == 1
    assert tls.close_calls == (0 if failure_stage == "wrap" else 1)
    assert installed.close_calls == (1 if failure_stage in {"begin", "read"} else 0)


def test_core_maps_transport_failure_to_existing_non_sensitive_error(monkeypatch) -> None:
    install_fixtures(monkeypatch, connect_error=OSError(SOURCE_URL))

    with pytest.raises(ImageProxyError, match="^image fetch failed$") as error:
        fetch_proxy_image(
            url=SOURCE_URL,
            policy=ImageProxyPolicy(schema_version="2.0", allowed_hosts=(ALLOWED_HOST,)),
            resolve_host=lambda _host: (PUBLIC_IPV4,),
            transport=PinnedHttpsImageTransport(),
        )

    assert SOURCE_URL not in str(error.value)


def test_transport_uses_no_dns_client_proxy_retry_or_credential_api() -> None:
    module_path = Path(image_proxy_http.__file__)
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    called_attributes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            called_attributes.add(node.func.attr)

    forbidden_imports = ("requests", "httpx", "urllib3", "aiohttp")
    assert not any(
        name == prefix or name.startswith(f"{prefix}.")
        for name in imports
        for prefix in forbidden_imports
    )
    assert (
        not {
            "getaddrinfo",
            "gethostbyaddr",
            "gethostbyname",
            "gethostbyname_ex",
            "getnameinfo",
        }
        & called_attributes
    )
    signature = inspect.signature(PinnedHttpsImageTransport.fetch_https)
    assert tuple(signature.parameters) == (
        "self",
        "url",
        "resolved_addresses",
        "timeout_seconds",
        "allow_redirects",
        "accept_encoding",
        "maximum_response_bytes",
    )
    assert http.client.HTTPResponse is not None
