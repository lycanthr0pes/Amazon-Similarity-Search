from __future__ import annotations

from dataclasses import dataclass

from src.search_v2.image_proxy import ImageProxyPolicy
from src.search_v2.image_proxy import ImageProxyTransport
from src.search_v2.image_proxy import ProxyImage
from src.search_v2.image_proxy import ResolveImageHost
from src.search_v2.image_proxy import fetch_proxy_image
from src.search_v2.image_proxy_dns_process import ProcessIsolatedImageDnsResolver
from src.search_v2.image_proxy_http import PinnedHttpsImageTransport


_INVALID_CONFIGURATION_MESSAGE = "image proxy configuration is invalid"
_REQUEST_FAILED_MESSAGE = "image proxy request failed"


class ImageProxyServiceError(RuntimeError):
    """Fixed, non-sensitive failure from the image proxy service."""


@dataclass(frozen=True, slots=True, repr=False, init=False)
class ImageProxyService:
    """Own the server-side image policy and its production dependencies."""

    _policy: ImageProxyPolicy
    _resolve_host: ResolveImageHost
    _transport: ImageProxyTransport

    def __init__(
        self,
        *,
        allowed_hosts: tuple[str, ...],
        resolve_host: ResolveImageHost | None = None,
        transport: ImageProxyTransport | None = None,
    ) -> None:
        try:
            if type(allowed_hosts) is not tuple:
                raise TypeError("allowed_hosts must be a tuple")
            policy = ImageProxyPolicy(
                schema_version="2.0",
                allowed_hosts=allowed_hosts,
            )
            configured_resolver = (
                ProcessIsolatedImageDnsResolver() if resolve_host is None else resolve_host
            )
            configured_transport = PinnedHttpsImageTransport() if transport is None else transport
            if not callable(configured_resolver):
                raise TypeError("resolve_host must be callable")
            if not callable(getattr(configured_transport, "fetch_https")):
                raise TypeError("transport.fetch_https must be callable")
        except Exception:
            raise ImageProxyServiceError(_INVALID_CONFIGURATION_MESSAGE) from None

        object.__setattr__(self, "_policy", policy)
        object.__setattr__(self, "_resolve_host", configured_resolver)
        object.__setattr__(self, "_transport", configured_transport)

    def fetch_image(self, url: str) -> ProxyImage:
        try:
            return fetch_proxy_image(
                url=url,
                policy=self._policy,
                resolve_host=self._resolve_host,
                transport=self._transport,
            )
        except Exception:
            raise ImageProxyServiceError(_REQUEST_FAILED_MESSAGE) from None
