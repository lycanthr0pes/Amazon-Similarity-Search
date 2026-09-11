from __future__ import annotations

import hashlib
import ipaddress
import re
import warnings
from collections.abc import Callable
from collections.abc import Iterable
from dataclasses import dataclass
from io import BytesIO
from typing import Annotated
from typing import Literal
from typing import Protocol
from urllib.parse import urlsplit

from PIL import Image
from PIL import UnidentifiedImageError
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import model_validator


IMAGE_PROXY_MAX_BYTES = 8 * 1024 * 1024
IMAGE_PROXY_MAX_DIMENSION = 4096
IMAGE_PROXY_MAX_PIXELS = IMAGE_PROXY_MAX_DIMENSION**2
IMAGE_PROXY_TIMEOUT_SECONDS = 10
IMAGE_PROXY_MAX_DNS_ADDRESSES = 8
IMAGE_PROXY_MAX_URL_CHARACTERS = 2048
IMAGE_PROXY_MAX_ALLOWED_HOSTS = 32
IMAGE_PROXY_ALLOWED_CONTENT_TYPES = (
    "image/jpeg",
    "image/png",
    "image/webp",
)
IMAGE_PROXY_ALLOWED_FORMATS = ("JPEG", "PNG", "WEBP")

_CONTENT_TYPE_BY_FORMAT = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_DNS_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_PIXEL_DIGEST_DOMAIN = b"amazon-explorer-proxy-rgb-v1\x00"


class ImageProxyError(RuntimeError):
    """Fixed, non-sensitive failure for the server-side image boundary."""


class _StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


class ImageProxyPolicy(_StrictFrozenContract):
    schema_version: Literal["2.0"]
    allowed_hosts: Annotated[
        tuple[str, ...],
        Field(min_length=1, max_length=IMAGE_PROXY_MAX_ALLOWED_HOSTS),
    ]

    @model_validator(mode="after")
    def validate_allowed_hosts(self) -> ImageProxyPolicy:
        if len(self.allowed_hosts) != len(set(self.allowed_hosts)):
            raise ValueError("allowed hosts must be unique")
        for host in self.allowed_hosts:
            if not _is_canonical_dns_host(host):
                raise ValueError("allowed hosts must be canonical DNS names")
        return self


class ProxyImage(_StrictFrozenContract):
    schema_version: Literal["2.0"]
    source_url_sha256: Annotated[str, StringConstraints(pattern=_SHA256_PATTERN)]
    source_bytes_sha256: Annotated[str, StringConstraints(pattern=_SHA256_PATTERN)]
    pixel_sha256: Annotated[str, StringConstraints(pattern=_SHA256_PATTERN)]
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    image_format: Literal["JPEG", "PNG", "WEBP"]
    width: Annotated[int, Field(ge=1, le=IMAGE_PROXY_MAX_DIMENSION)]
    height: Annotated[int, Field(ge=1, le=IMAGE_PROXY_MAX_DIMENSION)]
    rgb_bytes: bytes = Field(exclude=True, repr=False)

    @model_validator(mode="after")
    def validate_pixels(self) -> ProxyImage:
        if self.width * self.height > IMAGE_PROXY_MAX_PIXELS:
            raise ValueError("image pixel count is invalid")
        if len(self.rgb_bytes) != self.width * self.height * 3:
            raise ValueError("RGB byte length is invalid")
        if proxy_image_pixel_sha256(self.width, self.height, self.rgb_bytes) != self.pixel_sha256:
            raise ValueError("RGB digest is invalid")
        if _CONTENT_TYPE_BY_FORMAT[self.image_format] != self.content_type:
            raise ValueError("image format does not match content type")
        return self


@dataclass(frozen=True, slots=True)
class ImageProxyHttpResponse:
    status_code: int
    peer_ip: str
    content_type: str | None
    content_length: int | None
    content_encoding: str | None
    body_chunks: Iterable[bytes]


class ImageProxyTransport(Protocol):
    def fetch_https(
        self,
        *,
        url: str,
        resolved_addresses: tuple[str, ...],
        timeout_seconds: int,
        allow_redirects: Literal[False],
        accept_encoding: Literal["identity"],
        maximum_response_bytes: int,
    ) -> ImageProxyHttpResponse: ...


ResolveImageHost = Callable[[str], Iterable[str]]


def fetch_proxy_image(
    *,
    url: str,
    policy: ImageProxyPolicy,
    resolve_host: ResolveImageHost,
    transport: ImageProxyTransport,
) -> ProxyImage:
    validated_policy = ImageProxyPolicy.model_validate(policy)
    host = _validate_image_url(url, validated_policy)
    resolved_addresses = _resolve_public_addresses(host, resolve_host)
    try:
        response = transport.fetch_https(
            url=url,
            resolved_addresses=resolved_addresses,
            timeout_seconds=IMAGE_PROXY_TIMEOUT_SECONDS,
            allow_redirects=False,
            accept_encoding="identity",
            maximum_response_bytes=IMAGE_PROXY_MAX_BYTES,
        )
    except Exception:
        raise ImageProxyError("image fetch failed") from None
    if not isinstance(response, ImageProxyHttpResponse):
        raise ImageProxyError("image response was rejected")

    _validate_peer_address(response.peer_ip, resolved_addresses)
    if type(response.status_code) is not int:
        raise ImageProxyError("image response was rejected")
    if 300 <= response.status_code <= 399:
        raise ImageProxyError("image redirect is not allowed")
    if response.status_code != 200:
        raise ImageProxyError("image response was rejected")

    content_type = _validate_response_metadata(response)
    body = _read_bounded_body(response)
    image_format, width, height, rgb_bytes = _decode_image(body, content_type)
    return ProxyImage(
        schema_version="2.0",
        source_url_sha256=hashlib.sha256(url.encode("utf-8")).hexdigest(),
        source_bytes_sha256=hashlib.sha256(body).hexdigest(),
        pixel_sha256=proxy_image_pixel_sha256(width, height, rgb_bytes),
        content_type=content_type,
        image_format=image_format,
        width=width,
        height=height,
        rgb_bytes=rgb_bytes,
    )


def proxy_image_pixel_sha256(width: int, height: int, rgb_bytes: bytes) -> str:
    _validate_dimensions(width, height)
    if type(rgb_bytes) is not bytes or len(rgb_bytes) != width * height * 3:
        raise ValueError("RGB byte length is invalid")
    digest = hashlib.sha256()
    digest.update(_PIXEL_DIGEST_DOMAIN)
    digest.update(width.to_bytes(4, "big"))
    digest.update(height.to_bytes(4, "big"))
    digest.update(rgb_bytes)
    return digest.hexdigest()


def _validate_image_url(url: object, policy: ImageProxyPolicy) -> str:
    if type(url) is not str or not url or len(url) > IMAGE_PROXY_MAX_URL_CHARACTERS:
        raise ImageProxyError("image URL is not allowed")
    if any(ord(character) <= 0x20 or ord(character) == 0x7F for character in url):
        raise ImageProxyError("image URL is not allowed")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise ImageProxyError("image URL is not allowed") from None
    host = parsed.hostname
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or host is None
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or parsed.fragment
        or "%" in parsed.netloc
        or "\\" in parsed.netloc
        or not _is_canonical_dns_host(host)
        or host not in policy.allowed_hosts
    ):
        raise ImageProxyError("image URL is not allowed")
    return host


def _is_canonical_dns_host(host: object) -> bool:
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


def _resolve_public_addresses(host: str, resolve_host: ResolveImageHost) -> tuple[str, ...]:
    try:
        raw_addresses = tuple(resolve_host(host))
    except Exception:
        raise ImageProxyError("image address is not allowed") from None
    if not raw_addresses or len(raw_addresses) > IMAGE_PROXY_MAX_DNS_ADDRESSES:
        raise ImageProxyError("image address is not allowed")

    normalized: list[str] = []
    for raw_address in raw_addresses:
        if type(raw_address) is not str:
            raise ImageProxyError("image address is not allowed")
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError:
            raise ImageProxyError("image address is not allowed") from None
        if not address.is_global:
            raise ImageProxyError("image address is not allowed")
        canonical = address.compressed
        if canonical not in normalized:
            normalized.append(canonical)
    if not normalized:
        raise ImageProxyError("image address is not allowed")
    return tuple(normalized)


def _validate_peer_address(peer_ip: object, resolved_addresses: tuple[str, ...]) -> None:
    if type(peer_ip) is not str:
        raise ImageProxyError("image peer address is not allowed")
    try:
        address = ipaddress.ip_address(peer_ip)
    except ValueError:
        raise ImageProxyError("image peer address is not allowed") from None
    if not address.is_global or address.compressed not in resolved_addresses:
        raise ImageProxyError("image peer address is not allowed")


def _validate_response_metadata(response: ImageProxyHttpResponse) -> str:
    encoding = response.content_encoding
    if encoding is not None and (
        type(encoding) is not str or encoding.strip().lower() not in ("", "identity")
    ):
        raise ImageProxyError("image response was rejected")
    if type(response.content_type) is not str:
        raise ImageProxyError("image response was rejected")
    content_type = response.content_type.split(";", maxsplit=1)[0].strip().lower()
    if content_type not in IMAGE_PROXY_ALLOWED_CONTENT_TYPES:
        raise ImageProxyError("image response was rejected")
    content_length = response.content_length
    if content_length is not None and (
        type(content_length) is not int
        or content_length < 0
        or content_length > IMAGE_PROXY_MAX_BYTES
    ):
        raise ImageProxyError("image response is too large")
    return content_type


def _read_bounded_body(response: ImageProxyHttpResponse) -> bytes:
    chunks: list[bytes] = []
    total = 0
    try:
        for chunk in response.body_chunks:
            if type(chunk) is not bytes:
                raise ImageProxyError("image response was rejected")
            total += len(chunk)
            if total > IMAGE_PROXY_MAX_BYTES:
                raise ImageProxyError("image response is too large")
            if chunk:
                chunks.append(chunk)
    except ImageProxyError:
        raise
    except Exception:
        raise ImageProxyError("image response was rejected") from None
    if total == 0:
        raise ImageProxyError("image response was rejected")
    if response.content_length is not None and total != response.content_length:
        raise ImageProxyError("image response was rejected")
    return b"".join(chunks)


def _decode_image(body: bytes, content_type: str) -> tuple[str, int, int, bytes]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(body), formats=IMAGE_PROXY_ALLOWED_FORMATS) as source:
                image_format = source.format
                if image_format not in IMAGE_PROXY_ALLOWED_FORMATS:
                    raise ImageProxyError("image content is invalid")
                if _CONTENT_TYPE_BY_FORMAT[image_format] != content_type:
                    raise ImageProxyError("image content is invalid")
                width, height = source.size
                _validate_dimensions(width, height)
                if getattr(source, "is_animated", False) or getattr(source, "n_frames", 1) != 1:
                    raise ImageProxyError("image content is invalid")
                source.load()
                _validate_dimensions(*source.size)
                rgb_bytes = source.convert("RGB").tobytes()
    except ImageProxyError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError):
        raise ImageProxyError("image content is invalid") from None
    except (OSError, SyntaxError, ValueError):
        raise ImageProxyError("image content is invalid") from None
    return image_format, width, height, rgb_bytes


def _validate_dimensions(width: object, height: object) -> None:
    if (
        type(width) is not int
        or type(height) is not int
        or width < 1
        or height < 1
        or width > IMAGE_PROXY_MAX_DIMENSION
        or height > IMAGE_PROXY_MAX_DIMENSION
        or width * height > IMAGE_PROXY_MAX_PIXELS
    ):
        raise ImageProxyError("image dimensions are not allowed")
