import ast
import hashlib
import inspect
import io
import struct
import zlib
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

import src.search_v2.image_proxy as image_proxy
from src.search_v2.image_proxy import IMAGE_PROXY_MAX_BYTES
from src.search_v2.image_proxy import IMAGE_PROXY_MAX_DIMENSION
from src.search_v2.image_proxy import IMAGE_PROXY_TIMEOUT_SECONDS
from src.search_v2.image_proxy import ImageProxyError
from src.search_v2.image_proxy import ImageProxyHttpResponse
from src.search_v2.image_proxy import ImageProxyPolicy
from src.search_v2.image_proxy import fetch_proxy_image


ALLOWED_HOST = "images.example.test"
PUBLIC_IP = "93.184.216.34"
SOURCE_URL = f"https://{ALLOWED_HOST}/catalog/item.png?size=large"


def png_bytes(
    width: int = 2,
    height: int = 2,
    *,
    color: tuple[int, int, int] = (12, 34, 56),
) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (width, height), color).save(output, format="PNG")
    return output.getvalue()


def png_header_only(width: int, height: int) -> bytes:
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"".join((b"\x89PNG\r\n\x1a\n", chunk(b"IHDR", ihdr), chunk(b"IEND", b"")))


class RecordingResolver:
    def __init__(self, addresses=(PUBLIC_IP,)) -> None:
        self.addresses = addresses
        self.hosts: list[str] = []

    def __call__(self, host: str):
        self.hosts.append(host)
        return self.addresses


class RecordingTransport:
    def __init__(self, response: ImageProxyHttpResponse) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def fetch_https(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def response_for(
    body: bytes,
    *,
    status_code: int = 200,
    peer_ip: str = PUBLIC_IP,
    content_type: str | None = "image/png",
    content_length: int | None = None,
    content_encoding: str | None = "identity",
    chunks=None,
) -> ImageProxyHttpResponse:
    return ImageProxyHttpResponse(
        status_code=status_code,
        peer_ip=peer_ip,
        content_type=content_type,
        content_length=len(body) if content_length is None else content_length,
        content_encoding=content_encoding,
        body_chunks=chunks if chunks is not None else (body[:5], body[5:]),
    )


def policy() -> ImageProxyPolicy:
    return ImageProxyPolicy(schema_version="2.0", allowed_hosts=(ALLOWED_HOST,))


def fetch(body: bytes, **response_overrides):
    resolver = RecordingResolver()
    transport = RecordingTransport(response_for(body, **response_overrides))
    image = fetch_proxy_image(
        url=SOURCE_URL,
        policy=policy(),
        resolve_host=resolver,
        transport=transport,
    )
    return image, resolver, transport


def test_fetches_with_pinned_addresses_and_returns_metadata_free_rgb() -> None:
    body = png_bytes(color=(10, 20, 30))

    image, resolver, transport = fetch(body)

    assert resolver.hosts == [ALLOWED_HOST]
    assert transport.calls == [
        {
            "url": SOURCE_URL,
            "resolved_addresses": (PUBLIC_IP,),
            "timeout_seconds": IMAGE_PROXY_TIMEOUT_SECONDS,
            "allow_redirects": False,
            "accept_encoding": "identity",
            "maximum_response_bytes": IMAGE_PROXY_MAX_BYTES,
        }
    ]
    assert image.schema_version == "2.0"
    assert image.source_url_sha256 == hashlib.sha256(SOURCE_URL.encode()).hexdigest()
    assert image.source_bytes_sha256 == hashlib.sha256(body).hexdigest()
    assert image.width == 2
    assert image.height == 2
    assert image.image_format == "PNG"
    assert image.content_type == "image/png"
    assert image.rgb_bytes == bytes((10, 20, 30)) * 4
    assert image.pixel_sha256 == image_proxy.proxy_image_pixel_sha256(2, 2, image.rgb_bytes)
    assert SOURCE_URL not in repr(image)
    assert SOURCE_URL not in image.model_dump_json()
    assert "rgb_bytes" not in image.model_dump()


def test_canonical_pixel_digest_binds_dimensions() -> None:
    rgb_bytes = bytes(range(12))

    one_by_four = image_proxy.proxy_image_pixel_sha256(1, 4, rgb_bytes)
    two_by_two = image_proxy.proxy_image_pixel_sha256(2, 2, rgb_bytes)

    assert one_by_four != two_by_two


@pytest.mark.parametrize(
    "url",
    [
        f"http://{ALLOWED_HOST}/item.png",
        f"https://user:password@{ALLOWED_HOST}/item.png",
        "https://93.184.216.34/item.png",
        f"https://{ALLOWED_HOST}:444/item.png",
        f"https://{ALLOWED_HOST}./item.png",
        f"https://{ALLOWED_HOST}/item.png#fragment",
        "https://other.example.test/item.png",
        "https:///item.png",
    ],
)
def test_rejects_ambiguous_or_unapproved_urls_before_dns(url: str) -> None:
    resolver = RecordingResolver()
    transport = RecordingTransport(response_for(png_bytes()))

    with pytest.raises(ImageProxyError, match="^image URL is not allowed$") as error:
        fetch_proxy_image(
            url=url,
            policy=policy(),
            resolve_host=resolver,
            transport=transport,
        )

    assert url not in str(error.value)
    assert resolver.hosts == []
    assert transport.calls == []


@pytest.mark.parametrize(
    "hosts",
    [
        (),
        ("*.example.test",),
        ("localhost",),
        ("127.0.0.1",),
        ("Images.Example.test",),
        (ALLOWED_HOST, ALLOWED_HOST),
    ],
)
def test_policy_requires_unique_lowercase_dns_host_allowlist(hosts) -> None:
    with pytest.raises(ValidationError):
        ImageProxyPolicy(schema_version="2.0", allowed_hosts=hosts)


@pytest.mark.parametrize(
    "addresses",
    [
        (),
        ("127.0.0.1",),
        ("10.0.0.1",),
        ("169.254.169.254",),
        ("::1",),
        (PUBLIC_IP, "10.0.0.1"),
        tuple(f"8.8.8.{index}" for index in range(1, 10)),
        ("not-an-ip",),
    ],
)
def test_rejects_empty_private_mixed_or_oversized_dns_results(addresses) -> None:
    resolver = RecordingResolver(addresses)
    transport = RecordingTransport(response_for(png_bytes()))

    with pytest.raises(ImageProxyError, match="^image address is not allowed$"):
        fetch_proxy_image(
            url=SOURCE_URL,
            policy=policy(),
            resolve_host=resolver,
            transport=transport,
        )

    assert transport.calls == []


@pytest.mark.parametrize("peer_ip", ["93.184.216.35", "127.0.0.1", "not-an-ip"])
def test_rejects_peer_ip_that_is_not_the_validated_dns_destination(peer_ip: str) -> None:
    with pytest.raises(ImageProxyError, match="^image peer address is not allowed$"):
        fetch(png_bytes(), peer_ip=peer_ip)


@pytest.mark.parametrize("status_code", [301, 302, 307, 308])
def test_rejects_redirect_without_consuming_body(status_code: int) -> None:
    def forbidden_chunks():
        raise AssertionError("redirect body must not be consumed")
        yield b""

    with pytest.raises(ImageProxyError, match="^image redirect is not allowed$"):
        fetch(png_bytes(), status_code=status_code, chunks=forbidden_chunks())


@pytest.mark.parametrize("status_code", [199, 204, 404, 500])
def test_requires_exact_success_status(status_code: int) -> None:
    with pytest.raises(ImageProxyError, match="^image response was rejected$"):
        fetch(png_bytes(), status_code=status_code)


@pytest.mark.parametrize(
    ("content_type", "content_encoding"),
    [
        (None, "identity"),
        ("text/html", "identity"),
        ("image/gif", "identity"),
        ("image/png", "gzip"),
    ],
)
def test_rejects_unapproved_content_type_and_transfer_encoding(
    content_type: str | None,
    content_encoding: str | None,
) -> None:
    with pytest.raises(ImageProxyError, match="^image response was rejected$"):
        fetch(
            png_bytes(),
            content_type=content_type,
            content_encoding=content_encoding,
        )


def test_enforces_declared_and_streamed_byte_limits() -> None:
    body = png_bytes()
    with pytest.raises(ImageProxyError, match="^image response is too large$"):
        fetch(body, content_length=IMAGE_PROXY_MAX_BYTES + 1)

    oversized_chunks = (b"x" * IMAGE_PROXY_MAX_BYTES, b"y")
    with pytest.raises(ImageProxyError, match="^image response is too large$"):
        fetch(body, content_length=1, chunks=oversized_chunks)


def test_content_type_must_match_decoder_format() -> None:
    output = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(output, format="JPEG")

    with pytest.raises(ImageProxyError, match="^image content is invalid$"):
        fetch(output.getvalue(), content_type="image/png")


@pytest.mark.parametrize(
    ("width", "height"),
    [
        (IMAGE_PROXY_MAX_DIMENSION + 1, 1),
        (IMAGE_PROXY_MAX_DIMENSION, IMAGE_PROXY_MAX_DIMENSION + 1),
    ],
)
def test_rejects_dimensions_before_full_decode(width: int, height: int) -> None:
    with pytest.raises(ImageProxyError, match="^image dimensions are not allowed$"):
        fetch(png_header_only(width, height))


def test_treats_pillow_decompression_warning_as_an_error(monkeypatch) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1)

    with pytest.raises(ImageProxyError, match="^image content is invalid$"):
        fetch(png_bytes(2, 2))


def test_image_proxy_core_has_no_built_in_network_client() -> None:
    module_path = Path(image_proxy.__file__)
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)

    forbidden = ("requests", "httpx", "urllib3", "socket", "aiohttp")
    assert not any(
        name == prefix or name.startswith(f"{prefix}.") for name in imports for prefix in forbidden
    )
    assert tuple(inspect.signature(fetch_proxy_image).parameters) == (
        "url",
        "policy",
        "resolve_host",
        "transport",
    )


def test_pillow_is_a_direct_project_dependency() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8").lower()

    assert '"pillow>=' in pyproject
