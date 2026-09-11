from __future__ import annotations

from collections.abc import Callable
import ipaddress
import re
import socket

from src.search_v2.image_proxy import IMAGE_PROXY_MAX_DNS_ADDRESSES


GetAddrInfo = Callable[..., object]

_HTTPS_PORT = 443
_MAX_RAW_DNS_RESULTS = 64
_DNS_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_INVALID_REQUEST_MESSAGE = "image DNS request is invalid"
_RESOLUTION_FAILED_MESSAGE = "image DNS resolution failed"


class ImageProxyDnsError(RuntimeError):
    """Fixed, non-sensitive error from the image DNS adapter."""


def _raise_invalid_request() -> None:
    raise ImageProxyDnsError(_INVALID_REQUEST_MESSAGE) from None


def _raise_resolution_failed() -> None:
    raise ImageProxyDnsError(_RESOLUTION_FAILED_MESSAGE) from None


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


def _validated_address_info(item: object) -> str:
    if type(item) is not tuple or len(item) != 5:
        _raise_resolution_failed()
    family, socket_type, protocol, canonical_name, socket_address = item
    if (
        type(family) not in {int, socket.AddressFamily}
        or family not in {socket.AF_INET, socket.AF_INET6}
        or type(socket_type) not in {int, socket.SocketKind}
        or socket_type != socket.SOCK_STREAM
        or type(protocol) is not int
        or protocol != socket.IPPROTO_TCP
        or type(canonical_name) is not str
        or canonical_name != ""
        or type(socket_address) is not tuple
    ):
        _raise_resolution_failed()

    expected_length = 4 if family == socket.AF_INET6 else 2
    if len(socket_address) != expected_length:
        _raise_resolution_failed()
    raw_address, port = socket_address[:2]
    if type(raw_address) is not str or "%" in raw_address:
        _raise_resolution_failed()
    if type(port) is not int or port != _HTTPS_PORT:
        _raise_resolution_failed()
    if family == socket.AF_INET6:
        flowinfo, scope_id = socket_address[2:]
        if type(flowinfo) is not int or flowinfo != 0:
            _raise_resolution_failed()
        if type(scope_id) is not int or scope_id != 0:
            _raise_resolution_failed()

    try:
        address = ipaddress.ip_address(raw_address)
    except ValueError:
        _raise_resolution_failed()
    if raw_address != address.compressed:
        _raise_resolution_failed()
    if family == socket.AF_INET and not isinstance(address, ipaddress.IPv4Address):
        _raise_resolution_failed()
    if family == socket.AF_INET6 and not isinstance(address, ipaddress.IPv6Address):
        _raise_resolution_failed()
    return raw_address


def _validated_results(raw_results: object) -> tuple[str, ...]:
    if type(raw_results) is not list or not raw_results or len(raw_results) > _MAX_RAW_DNS_RESULTS:
        _raise_resolution_failed()
    addresses: list[str] = []
    seen: set[str] = set()
    for item in raw_results:
        address = _validated_address_info(item)
        if address in seen:
            continue
        seen.add(address)
        if len(addresses) < IMAGE_PROXY_MAX_DNS_ADDRESSES:
            addresses.append(address)
    return tuple(addresses)


class BoundedImageDnsResolver:
    """Resolve an image host through one bounded getaddrinfo call."""

    __slots__ = ("_getaddrinfo",)

    def __init__(self, *, getaddrinfo: GetAddrInfo | None = None) -> None:
        self._getaddrinfo = getaddrinfo

    def __call__(self, host: str) -> tuple[str, ...]:
        if not _is_canonical_host(host):
            _raise_invalid_request()
        getaddrinfo = self._getaddrinfo
        if getaddrinfo is None:
            getaddrinfo = socket.getaddrinfo
        try:
            raw_results = getaddrinfo(
                host,
                _HTTPS_PORT,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
                flags=socket.AI_NUMERICSERV,
            )
        except Exception:
            _raise_resolution_failed()
        return _validated_results(raw_results)
