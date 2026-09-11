from __future__ import annotations

import ast
import inspect
import io
import socket
from pathlib import Path

import pytest
from PIL import Image

import src.search_v2.image_proxy_dns as image_proxy_dns
from src.search_v2.image_proxy import IMAGE_PROXY_MAX_BYTES
from src.search_v2.image_proxy import IMAGE_PROXY_TIMEOUT_SECONDS
from src.search_v2.image_proxy import ImageProxyError
from src.search_v2.image_proxy import ImageProxyHttpResponse
from src.search_v2.image_proxy import ImageProxyPolicy
from src.search_v2.image_proxy import fetch_proxy_image
from src.search_v2.image_proxy_dns import BoundedImageDnsResolver
from src.search_v2.image_proxy_dns import ImageProxyDnsError


ALLOWED_HOST = "images.example.test"
SOURCE_URL = f"https://{ALLOWED_HOST}/catalog/item.png"
PUBLIC_IPV4 = "93.184.216.34"
PUBLIC_IPV6 = "2606:2800:220:1:248:1893:25c8:1946"
PRIVATE_IPV4 = "10.0.0.1"


def address_info(
    address: object = PUBLIC_IPV4,
    *,
    family: object = socket.AF_INET,
    socket_type: object = socket.SOCK_STREAM,
    protocol: object = socket.IPPROTO_TCP,
    canonical_name: object = "",
    port: object = 443,
    flowinfo: object = 0,
    scope_id: object = 0,
) -> tuple[object, ...]:
    if family == socket.AF_INET6:
        socket_address: object = (address, port, flowinfo, scope_id)
    else:
        socket_address = (address, port)
    return family, socket_type, protocol, canonical_name, socket_address


class RecordingGetAddrInfo:
    def __init__(self, results: object, *, error: Exception | None = None) -> None:
        self.results = results
        self.error = error
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def __call__(self, *args: object, **kwargs: object) -> object:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.results


class RecordingTransport:
    def __init__(self, *, peer_ip: str) -> None:
        self.peer_ip = peer_ip
        self.calls: list[dict[str, object]] = []

    def fetch_https(self, **kwargs: object) -> ImageProxyHttpResponse:
        self.calls.append(kwargs)
        body = png_bytes()
        return ImageProxyHttpResponse(
            status_code=200,
            peer_ip=self.peer_ip,
            content_type="image/png",
            content_length=len(body),
            content_encoding="identity",
            body_chunks=(body,),
        )


def png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (1, 1), (12, 34, 56)).save(output, format="PNG")
    return output.getvalue()


def policy() -> ImageProxyPolicy:
    return ImageProxyPolicy(schema_version="2.0", allowed_hosts=(ALLOWED_HOST,))


def test_resolves_ipv4_and_ipv6_once_with_exact_tcp_contract() -> None:
    getaddrinfo = RecordingGetAddrInfo(
        [
            address_info(),
            address_info(PUBLIC_IPV6, family=socket.AF_INET6),
        ]
    )
    resolver = BoundedImageDnsResolver(getaddrinfo=getaddrinfo)

    addresses = resolver(ALLOWED_HOST)

    assert addresses == (PUBLIC_IPV4, PUBLIC_IPV6)
    assert getaddrinfo.calls == [
        (
            (ALLOWED_HOST, 443),
            {
                "family": socket.AF_UNSPEC,
                "type": socket.SOCK_STREAM,
                "proto": socket.IPPROTO_TCP,
                "flags": socket.AI_NUMERICSERV,
            },
        )
    ]


def test_deduplicates_results_before_applying_transport_limit() -> None:
    getaddrinfo = RecordingGetAddrInfo(
        [
            address_info(PUBLIC_IPV6, family=socket.AF_INET6),
            address_info(),
            address_info(),
        ]
    )

    addresses = BoundedImageDnsResolver(getaddrinfo=getaddrinfo)(ALLOWED_HOST)

    assert addresses == (PUBLIC_IPV6, PUBLIC_IPV4)


def test_accepts_nine_unique_results_and_caps_transport_candidates() -> None:
    expected = (PUBLIC_IPV4,) + tuple(f"2001:4860:4860::{index}" for index in range(1, 9))
    getaddrinfo = RecordingGetAddrInfo(
        [address_info(expected[0])]
        + [address_info(value, family=socket.AF_INET6) for value in expected[1:]]
    )

    addresses = BoundedImageDnsResolver(getaddrinfo=getaddrinfo)(ALLOWED_HOST)

    assert addresses == expected[:8]


def test_accepts_bounded_raw_duplicates_before_deduplication() -> None:
    getaddrinfo = RecordingGetAddrInfo([address_info()] * 64)

    addresses = BoundedImageDnsResolver(getaddrinfo=getaddrinfo)(ALLOWED_HOST)

    assert addresses == (PUBLIC_IPV4,)


def test_validates_results_beyond_transport_candidate_limit() -> None:
    results = [
        address_info(f"2001:4860:4860::{index}", family=socket.AF_INET6) for index in range(1, 9)
    ]
    results.append(address_info(canonical_name=ALLOWED_HOST))
    getaddrinfo = RecordingGetAddrInfo(results)

    with pytest.raises(ImageProxyDnsError, match="^image DNS resolution failed$"):
        BoundedImageDnsResolver(getaddrinfo=getaddrinfo)(ALLOWED_HOST)


@pytest.mark.parametrize(
    "host",
    [
        None,
        False,
        "",
        "images",
        "Images.example.test",
        "images.example.test.",
        "images..example.test",
        "-images.example.test",
        "images-.example.test",
        "127.0.0.1",
        "::1",
        "images.example.test:443",
        "images example.test",
        "images.example.test/path",
        "images.exämple.test",
        f"{'a' * 250}.test",
    ],
)
def test_rejects_noncanonical_host_before_resolution(host: object) -> None:
    getaddrinfo = RecordingGetAddrInfo([address_info()])
    resolver = BoundedImageDnsResolver(getaddrinfo=getaddrinfo)

    with pytest.raises(ImageProxyDnsError, match="^image DNS request is invalid$") as error:
        resolver(host)  # type: ignore[arg-type]

    assert getaddrinfo.calls == []
    if isinstance(host, str) and host:
        assert host not in str(error.value)


def test_converts_resolver_exception_without_retry_or_sensitive_data() -> None:
    sensitive_message = f"temporary failure for {ALLOWED_HOST}"
    getaddrinfo = RecordingGetAddrInfo([], error=OSError(sensitive_message))
    resolver = BoundedImageDnsResolver(getaddrinfo=getaddrinfo)

    with pytest.raises(ImageProxyDnsError, match="^image DNS resolution failed$") as error:
        resolver(ALLOWED_HOST)

    assert len(getaddrinfo.calls) == 1
    assert ALLOWED_HOST not in str(error.value)
    assert sensitive_message not in str(error.value)


def test_does_not_trust_an_injected_dns_error_message() -> None:
    sensitive_message = f"forged adapter error for {ALLOWED_HOST}"
    getaddrinfo = RecordingGetAddrInfo([], error=ImageProxyDnsError(sensitive_message))

    with pytest.raises(ImageProxyDnsError, match="^image DNS resolution failed$") as error:
        BoundedImageDnsResolver(getaddrinfo=getaddrinfo)(ALLOWED_HOST)

    assert len(getaddrinfo.calls) == 1
    assert ALLOWED_HOST not in str(error.value)
    assert sensitive_message not in str(error.value)


def test_default_resolver_remains_blocked_by_normal_pytest_network_guard() -> None:
    with pytest.raises(ImageProxyDnsError, match="^image DNS resolution failed$"):
        BoundedImageDnsResolver()(ALLOWED_HOST)


@pytest.mark.parametrize(
    "results",
    [
        None,
        (),
        [],
        tuple([address_info()]),
        [address_info()] * 65,
    ],
)
def test_rejects_non_list_empty_or_oversized_results(results: object) -> None:
    getaddrinfo = RecordingGetAddrInfo(results)

    with pytest.raises(ImageProxyDnsError, match="^image DNS resolution failed$"):
        BoundedImageDnsResolver(getaddrinfo=getaddrinfo)(ALLOWED_HOST)

    assert len(getaddrinfo.calls) == 1


@pytest.mark.parametrize(
    "result",
    [
        None,
        [],
        (),
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, ""),
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (), "extra"),
        address_info(family=[]),
        address_info(family=9_999),
        address_info(socket_type=[]),
        address_info(socket_type=socket.SOCK_DGRAM),
        address_info(protocol=[]),
        address_info(protocol=socket.IPPROTO_UDP),
        address_info(protocol=0),
        address_info(canonical_name=ALLOWED_HOST),
        address_info(canonical_name=None),
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", [PUBLIC_IPV4, 443]),
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (PUBLIC_IPV4,)),
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            (PUBLIC_IPV4, 443, 0),
        ),
        address_info(address=None),
        address_info(port="443"),
        address_info(port=80),
        address_info(address="not-an-ip"),
        address_info(address=PUBLIC_IPV6),
        address_info(
            "2606:2800:0220:0001:0248:1893:25C8:1946",
            family=socket.AF_INET6,
        ),
        address_info(f"{PUBLIC_IPV6}%eth0", family=socket.AF_INET6),
        address_info(PUBLIC_IPV6, family=socket.AF_INET6, flowinfo=1),
        address_info(PUBLIC_IPV6, family=socket.AF_INET6, scope_id=1),
        address_info(PUBLIC_IPV6, family=socket.AF_INET6, flowinfo=False),
        address_info(PUBLIC_IPV6, family=socket.AF_INET6, scope_id=False),
        (
            socket.AF_INET6,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            (PUBLIC_IPV6, 443, 0),
        ),
        (
            socket.AF_INET6,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            (PUBLIC_IPV6, 443, 0, 0, 0),
        ),
    ],
)
def test_rejects_malformed_or_noncanonical_address_info(result: object) -> None:
    getaddrinfo = RecordingGetAddrInfo([result])

    with pytest.raises(ImageProxyDnsError, match="^image DNS resolution failed$") as error:
        BoundedImageDnsResolver(getaddrinfo=getaddrinfo)(ALLOWED_HOST)

    assert len(getaddrinfo.calls) == 1
    assert ALLOWED_HOST not in str(error.value)
    assert "not-an-ip" not in str(error.value)


def test_core_deduplicates_global_results_before_transport() -> None:
    getaddrinfo = RecordingGetAddrInfo(
        [
            address_info(PUBLIC_IPV6, family=socket.AF_INET6),
            address_info(),
            address_info(),
        ]
    )
    transport = RecordingTransport(peer_ip=PUBLIC_IPV6)

    image = fetch_proxy_image(
        url=SOURCE_URL,
        policy=policy(),
        resolve_host=BoundedImageDnsResolver(getaddrinfo=getaddrinfo),
        transport=transport,
    )

    assert image.width == 1
    assert image.height == 1
    assert transport.calls == [
        {
            "url": SOURCE_URL,
            "resolved_addresses": (PUBLIC_IPV6, PUBLIC_IPV4),
            "timeout_seconds": IMAGE_PROXY_TIMEOUT_SECONDS,
            "allow_redirects": False,
            "accept_encoding": "identity",
            "maximum_response_bytes": IMAGE_PROXY_MAX_BYTES,
        }
    ]


def test_core_rejects_mixed_private_result_before_transport() -> None:
    getaddrinfo = RecordingGetAddrInfo(
        [
            address_info(),
            address_info(PRIVATE_IPV4),
        ]
    )
    transport = RecordingTransport(peer_ip=PUBLIC_IPV4)

    with pytest.raises(ImageProxyError, match="^image address is not allowed$"):
        fetch_proxy_image(
            url=SOURCE_URL,
            policy=policy(),
            resolve_host=BoundedImageDnsResolver(getaddrinfo=getaddrinfo),
            transport=transport,
        )

    assert len(getaddrinfo.calls) == 1
    assert transport.calls == []


def test_module_uses_only_getaddrinfo_for_name_resolution() -> None:
    source = inspect.getsource(image_proxy_dns)
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        node.module.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    attribute_calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert not imported_roots.intersection(
        {"asyncio", "dns", "httpx", "requests", "subprocess", "urllib"}
    )
    assert "getaddrinfo" in source
    assert not attribute_calls.intersection(
        {
            "create_connection",
            "gethostbyaddr",
            "gethostbyname",
            "gethostbyname_ex",
            "sleep",
        }
    )
    assert not any(isinstance(node, ast.While) for node in ast.walk(tree))


def test_test_file_does_not_disable_network_guard() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    attribute_names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    variable_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}

    assert "live_api" not in attribute_names
    assert "original_socket_type" not in variable_names
