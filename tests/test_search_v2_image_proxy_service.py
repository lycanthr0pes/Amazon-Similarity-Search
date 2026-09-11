from __future__ import annotations

import ast
import hashlib
import inspect
import io
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from PIL import Image

import src.search_v2.image_proxy_service as image_proxy_service
from src.search_v2.image_proxy import IMAGE_PROXY_MAX_BYTES
from src.search_v2.image_proxy import IMAGE_PROXY_TIMEOUT_SECONDS
from src.search_v2.image_proxy import ImageProxyHttpResponse
from src.search_v2.image_proxy import ImageProxyPolicy
from src.search_v2.image_proxy import ProxyImage
from src.search_v2.image_proxy import proxy_image_pixel_sha256
from src.search_v2.image_proxy_service import ImageProxyService
from src.search_v2.image_proxy_service import ImageProxyServiceError


ALLOWED_HOST = "images.example.test"
OTHER_HOST = "other-images.example.test"
PUBLIC_IPV4 = "93.184.216.34"
PUBLIC_IPV6 = "2001:4860:4860::8888"
SOURCE_URL = f"https://{ALLOWED_HOST}/catalog/item.png?size=large"
MODULE_PATH = Path("src/search_v2/image_proxy_service.py")


def png_bytes(color: tuple[int, int, int] = (12, 34, 56)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (2, 2), color).save(output, format="PNG")
    return output.getvalue()


def image_response(
    *,
    body: bytes | None = None,
    peer_ip: str = PUBLIC_IPV4,
) -> ImageProxyHttpResponse:
    payload = body if body is not None else png_bytes()
    return ImageProxyHttpResponse(
        status_code=200,
        peer_ip=peer_ip,
        content_type="image/png",
        content_length=len(payload),
        content_encoding="identity",
        body_chunks=(payload[:7], payload[7:]),
    )


def proxy_image_fixture() -> ProxyImage:
    rgb_bytes = bytes((1, 2, 3))
    return ProxyImage(
        schema_version="2.0",
        source_url_sha256="0" * 64,
        source_bytes_sha256="1" * 64,
        pixel_sha256=proxy_image_pixel_sha256(1, 1, rgb_bytes),
        content_type="image/png",
        image_format="PNG",
        width=1,
        height=1,
        rgb_bytes=rgb_bytes,
    )


class RecordingResolver:
    def __init__(
        self,
        addresses: tuple[str, ...] = (PUBLIC_IPV4,),
        *,
        error: Exception | None = None,
    ) -> None:
        self.addresses = addresses
        self.error = error
        self.calls: list[str] = []

    def __call__(self, host: str) -> tuple[str, ...]:
        self.calls.append(host)
        if self.error is not None:
            raise self.error
        return self.addresses


class RecordingTransport:
    def __init__(
        self,
        response: object | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.response = response if response is not None else image_response()
        self.error = error
        self.calls: list[dict[str, object]] = []

    def fetch_https(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class RecordingFactory:
    def __init__(self, value: object) -> None:
        self.value = value
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def __call__(self, *args: object, **kwargs: object) -> object:
        self.calls.append((args, kwargs))
        return self.value


def service_with(
    *,
    resolver: object | None = None,
    transport: object | None = None,
) -> ImageProxyService:
    return ImageProxyService(
        allowed_hosts=(ALLOWED_HOST,),
        resolve_host=resolver if resolver is not None else RecordingResolver(),
        transport=transport if transport is not None else RecordingTransport(),
    )


def test_composes_existing_core_and_returns_validated_image() -> None:
    body = png_bytes(color=(10, 20, 30))
    resolver = RecordingResolver((PUBLIC_IPV4, PUBLIC_IPV6))
    transport = RecordingTransport(image_response(body=body))

    result = service_with(resolver=resolver, transport=transport).fetch_image(SOURCE_URL)

    assert isinstance(result, ProxyImage)
    assert result.schema_version == "2.0"
    assert result.image_format == "PNG"
    assert (result.width, result.height) == (2, 2)
    assert result.source_url_sha256 == hashlib.sha256(SOURCE_URL.encode()).hexdigest()
    assert result.source_bytes_sha256 == hashlib.sha256(body).hexdigest()
    assert resolver.calls == [ALLOWED_HOST]
    assert transport.calls == [
        {
            "url": SOURCE_URL,
            "resolved_addresses": (PUBLIC_IPV4, PUBLIC_IPV6),
            "timeout_seconds": IMAGE_PROXY_TIMEOUT_SECONDS,
            "allow_redirects": False,
            "accept_encoding": "identity",
            "maximum_response_bytes": IMAGE_PROXY_MAX_BYTES,
        }
    ]


def test_delegates_once_with_constructor_owned_policy_and_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = RecordingResolver()
    transport = RecordingTransport()
    expected = proxy_image_fixture()
    calls: list[dict[str, object]] = []

    def recording_delegate(**kwargs: object) -> ProxyImage:
        calls.append(kwargs)
        return expected

    monkeypatch.setattr(image_proxy_service, "fetch_proxy_image", recording_delegate)
    service = service_with(resolver=resolver, transport=transport)

    result = service.fetch_image(SOURCE_URL)

    assert result is expected
    assert len(calls) == 1
    assert calls[0]["url"] == SOURCE_URL
    assert calls[0]["resolve_host"] is resolver
    assert calls[0]["transport"] is transport
    policy = calls[0]["policy"]
    assert isinstance(policy, ImageProxyPolicy)
    assert policy.schema_version == "2.0"
    assert policy.allowed_hosts == (ALLOWED_HOST,)
    assert resolver.calls == []
    assert transport.calls == []


def test_default_composition_builds_each_dependency_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = RecordingResolver()
    transport = RecordingTransport()
    resolver_factory = RecordingFactory(resolver)
    transport_factory = RecordingFactory(transport)
    delegate_calls: list[dict[str, object]] = []
    expected = proxy_image_fixture()

    def recording_delegate(**kwargs: object) -> ProxyImage:
        delegate_calls.append(kwargs)
        return expected

    monkeypatch.setattr(
        image_proxy_service,
        "ProcessIsolatedImageDnsResolver",
        resolver_factory,
    )
    monkeypatch.setattr(image_proxy_service, "PinnedHttpsImageTransport", transport_factory)
    monkeypatch.setattr(image_proxy_service, "fetch_proxy_image", recording_delegate)

    service = ImageProxyService(allowed_hosts=(ALLOWED_HOST,))

    assert resolver_factory.calls == [((), {})]
    assert transport_factory.calls == [((), {})]
    assert delegate_calls == []
    assert service.fetch_image(SOURCE_URL) is expected
    assert len(delegate_calls) == 1
    assert delegate_calls[0]["resolve_host"] is resolver
    assert delegate_calls[0]["transport"] is transport


def test_real_default_construction_does_not_start_network() -> None:
    service = ImageProxyService(allowed_hosts=(ALLOWED_HOST,))

    assert ALLOWED_HOST not in repr(service)


def test_public_fetch_signature_does_not_allow_request_policy_overrides() -> None:
    constructor = inspect.signature(ImageProxyService)
    fetch = inspect.signature(ImageProxyService.fetch_image)

    assert tuple(constructor.parameters) == ("allowed_hosts", "resolve_host", "transport")
    assert constructor.parameters["allowed_hosts"].kind is inspect.Parameter.KEYWORD_ONLY
    assert tuple(fetch.parameters) == ("self", "url")
    assert fetch.parameters["url"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD


def test_service_configuration_is_frozen_and_hidden_from_repr() -> None:
    service = service_with()

    assert ALLOWED_HOST not in repr(service)
    with pytest.raises(FrozenInstanceError):
        service._policy = ImageProxyPolicy(  # type: ignore[misc]
            schema_version="2.0",
            allowed_hosts=(OTHER_HOST,),
        )
    with pytest.raises((AttributeError, TypeError)):
        service.request_policy = object()  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "allowed_hosts",
    [
        None,
        False,
        [],
        (),
        (ALLOWED_HOST, ALLOWED_HOST),
        ("Images.example.test",),
        ("images",),
        ("127.0.0.1",),
        (ALLOWED_HOST, 1),
        tuple(f"images-{index}.example.test" for index in range(33)),
    ],
)
def test_rejects_invalid_allowlist_with_fixed_configuration_error(
    allowed_hosts: object,
) -> None:
    with pytest.raises(
        ImageProxyServiceError,
        match="^image proxy configuration is invalid$",
    ) as error:
        ImageProxyService(allowed_hosts=allowed_hosts)  # type: ignore[arg-type]

    assert ALLOWED_HOST not in str(error.value)
    assert ALLOWED_HOST not in repr(error.value)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"resolve_host": object()},
        {"transport": object()},
    ],
)
def test_rejects_non_callable_dependencies_as_configuration_error(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(
        ImageProxyServiceError,
        match="^image proxy configuration is invalid$",
    ):
        ImageProxyService(allowed_hosts=(ALLOWED_HOST,), **kwargs)  # type: ignore[arg-type]


def test_converts_dependency_attribute_failure_without_sensitive_data() -> None:
    sensitive_message = f"transport property exposed {ALLOWED_HOST}"

    class RaisingTransport:
        @property
        def fetch_https(self) -> object:
            raise RuntimeError(sensitive_message)

    with pytest.raises(
        ImageProxyServiceError,
        match="^image proxy configuration is invalid$",
    ) as error:
        ImageProxyService(
            allowed_hosts=(ALLOWED_HOST,),
            resolve_host=RecordingResolver(),
            transport=RaisingTransport(),
        )

    assert sensitive_message not in str(error.value)
    assert ALLOWED_HOST not in str(error.value)


def test_converts_default_factory_failure_without_sensitive_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sensitive_message = f"resolver factory exposed {ALLOWED_HOST}"

    def failing_factory() -> object:
        raise RuntimeError(sensitive_message)

    monkeypatch.setattr(
        image_proxy_service,
        "ProcessIsolatedImageDnsResolver",
        failing_factory,
    )

    with pytest.raises(
        ImageProxyServiceError,
        match="^image proxy configuration is invalid$",
    ) as error:
        ImageProxyService(allowed_hosts=(ALLOWED_HOST,))

    assert sensitive_message not in str(error.value)
    assert ALLOWED_HOST not in str(error.value)


@pytest.mark.parametrize(
    "url",
    [
        None,
        "",
        f"http://{ALLOWED_HOST}/item.png",
        f"https://{OTHER_HOST}/item.png",
        f"https://user:password@{ALLOWED_HOST}/item.png",
    ],
)
def test_rejects_invalid_or_disallowed_url_before_resolution(url: object) -> None:
    resolver = RecordingResolver()
    transport = RecordingTransport()
    service = service_with(resolver=resolver, transport=transport)

    with pytest.raises(
        ImageProxyServiceError,
        match="^image proxy request failed$",
    ) as error:
        service.fetch_image(url)  # type: ignore[arg-type]

    assert resolver.calls == []
    assert transport.calls == []
    if isinstance(url, str) and url:
        assert url not in str(error.value)


def test_converts_resolver_failure_without_retry_or_sensitive_data() -> None:
    sensitive_message = f"resolver exposed {ALLOWED_HOST}"
    resolver = RecordingResolver(error=RuntimeError(sensitive_message))
    transport = RecordingTransport()

    with pytest.raises(
        ImageProxyServiceError,
        match="^image proxy request failed$",
    ) as error:
        service_with(resolver=resolver, transport=transport).fetch_image(SOURCE_URL)

    assert resolver.calls == [ALLOWED_HOST]
    assert transport.calls == []
    assert sensitive_message not in str(error.value)
    assert SOURCE_URL not in str(error.value)


def test_rejects_mixed_public_and_private_dns_before_transport() -> None:
    resolver = RecordingResolver((PUBLIC_IPV4, "127.0.0.1"))
    transport = RecordingTransport()

    with pytest.raises(ImageProxyServiceError, match="^image proxy request failed$"):
        service_with(resolver=resolver, transport=transport).fetch_image(SOURCE_URL)

    assert resolver.calls == [ALLOWED_HOST]
    assert transport.calls == []


def test_converts_transport_failure_without_retry_or_sensitive_data() -> None:
    sensitive_message = f"transport exposed {SOURCE_URL}"
    resolver = RecordingResolver()
    transport = RecordingTransport(error=RuntimeError(sensitive_message))

    with pytest.raises(
        ImageProxyServiceError,
        match="^image proxy request failed$",
    ) as error:
        service_with(resolver=resolver, transport=transport).fetch_image(SOURCE_URL)

    assert resolver.calls == [ALLOWED_HOST]
    assert len(transport.calls) == 1
    assert sensitive_message not in str(error.value)
    assert SOURCE_URL not in str(error.value)


def test_converts_invalid_transport_response_without_retry() -> None:
    resolver = RecordingResolver()
    transport = RecordingTransport(response=object())

    with pytest.raises(ImageProxyServiceError, match="^image proxy request failed$"):
        service_with(resolver=resolver, transport=transport).fetch_image(SOURCE_URL)

    assert resolver.calls == [ALLOWED_HOST]
    assert len(transport.calls) == 1


def test_does_not_trust_a_forged_service_error_from_delegate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sensitive_message = f"forged service error for {SOURCE_URL}"
    calls = 0

    def failing_delegate(**kwargs: object) -> ProxyImage:
        nonlocal calls
        del kwargs
        calls += 1
        raise ImageProxyServiceError(sensitive_message)

    monkeypatch.setattr(image_proxy_service, "fetch_proxy_image", failing_delegate)

    with pytest.raises(
        ImageProxyServiceError,
        match="^image proxy request failed$",
    ) as error:
        service_with().fetch_image(SOURCE_URL)

    assert calls == 1
    assert sensitive_message not in str(error.value)
    assert SOURCE_URL not in str(error.value)


def test_service_module_only_composes_existing_proxy_layers() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    called_names: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_roots.add(node.module.split(".", maxsplit=1)[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.append(node.func.id)

    assert imported_roots.isdisjoint(
        {"_socket", "http", "logging", "os", "requests", "socket", "ssl", "urllib"}
    )
    assert not any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(tree))
    assert called_names.count("fetch_proxy_image") == 1
    assert "print" not in called_names
