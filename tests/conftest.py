from __future__ import annotations

import _socket
import shutil
import sys
import sysconfig
from pathlib import Path
import socket
from collections.abc import Generator
from typing import Any

import pytest


_ORIGINAL_SOCKET = socket.socket
_ORIGINAL_LOW_LEVEL_SOCKET = _socket.socket
_ORIGINAL_SOCKET_TYPE = socket.SocketType
_ORIGINAL_RESOLVERS = {
    name: getattr(socket, name)
    for name in (
        "getaddrinfo",
        "gethostbyaddr",
        "gethostbyname",
        "gethostbyname_ex",
        "getnameinfo",
    )
}
_NETWORK_FAMILIES = frozenset({socket.AF_INET, socket.AF_INET6})
_BLOCKED_MESSAGE = (
    "Network access is disabled during tests. "
    "Mark an intentional live-service test with @pytest.mark.live_api "
    "and run it with --run-live-api."
)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--lexical-assets",
        default=None,
        help="prepared local lexical assets for optional CPU integration tests",
    )
    parser.addoption(
        "--bonsai-response-log-dir",
        default=None,
        help="absolute new private directory for all attribute-test response bodies",
    )
    parser.addoption(
        "--run-bonsai-attribute-inference",
        action="store_true",
        default=False,
        help="run the separately approved single-call Bonsai attribute inference probe",
    )
    parser.addoption(
        "--run-clip-runtime",
        action="store_true",
        default=False,
        help="run tests that load the pinned repository-local CLIP model",
    )
    parser.addoption(
        "--run-live-api",
        action="store_true",
        default=False,
        help="run tests that may contact explicitly approved live services",
    )
    parser.addoption(
        "--run-bonsai-e2e",
        action="store_true",
        default=False,
        help="run the explicitly approved localhost Bonsai v6 prompt-cache test",
    )
    parser.addoption(
        "--run-cloudflare-e2e",
        action="store_true",
        default=False,
        help="run the separately approved single-image Cloudflare Workers AI test",
    )
    parser.addoption(
        "--cloudflare-output-path",
        default=None,
        help="absolute new PNG path for the approved Cloudflare image test",
    )
    parser.addoption(
        "--run-counterfactual-cloudflare-e2e",
        action="store_true",
        default=False,
        help="run the separately approved minimum counterfactual Cloudflare test",
    )
    parser.addoption(
        "--counterfactual-cloudflare-output-dir",
        default=None,
        help="absolute new directory for the approved counterfactual Cloudflare test",
    )
    parser.addoption(
        "--run-product-image-proxy-e2e",
        action="store_true",
        default=False,
        help="run the separately approved one-image product proxy and CLIP test",
    )
    parser.addoption(
        "--product-image-reference-dir",
        default=None,
        help="absolute directory containing the approved two-image reference set",
    )
    parser.addoption(
        "--product-image-output-path",
        default=None,
        help="absolute new PNG path for the approved product image proxy test",
    )
    parser.addoption(
        "--run-backend-search-e2e",
        action="store_true",
        default=False,
        help="run the separately approved natural-language-to-history backend E2E",
    )
    parser.addoption(
        "--backend-search-output-dir",
        default=None,
        help="absolute new private directory for the approved backend E2E",
    )
    parser.addoption(
        "--backend-search-clip-asset-root",
        default=None,
        help="absolute pinned CLIP asset directory for the backend E2E",
    )
    parser.addoption(
        "--run-provisional-search-e2e",
        action="store_true",
        default=False,
        help="run the separately approved interactive provisional product-search test",
    )
    parser.addoption(
        "--provisional-search-review-dir",
        default=None,
        help="absolute new directory for the provisional search reference review",
    )
    parser.addoption(
        "--provisional-search-approval-db",
        default=None,
        help="absolute SQLite path for the provisional reference approval",
    )
    parser.addoption(
        "--provisional-search-clip-asset-root",
        default=None,
        help="absolute pinned CLIP asset root for the provisional search test",
    )
    parser.addoption(
        "--run-bonsai-latency-diagnostic",
        action="store_true",
        default=False,
        help="select the separately approved same-input Bonsai timing diagnostic",
    )
    parser.addoption(
        "--bonsai-server-bin",
        default=None,
        help="absolute path to the llama-server executable for the localhost Bonsai test",
    )
    parser.addoption(
        "--bonsai-model-path",
        default=None,
        help="absolute path to the GGUF model for the localhost Bonsai test",
    )
    parser.addoption(
        "--bonsai-e2e-port",
        type=int,
        default=18080,
        help="unused loopback port for the localhost Bonsai test (default: 18080)",
    )


def bonsai_live_test_enabled(
    *,
    is_latency_diagnostic: bool,
    run_live_api: bool,
    run_bonsai_e2e: bool,
    run_latency_diagnostic: bool,
) -> bool:
    if not run_live_api or not run_bonsai_e2e:
        return False
    if is_latency_diagnostic:
        return run_latency_diagnostic
    return not run_latency_diagnostic


def cloudflare_live_test_enabled(
    *,
    run_live_api: bool,
    run_cloudflare_e2e: bool,
) -> bool:
    return run_live_api and run_cloudflare_e2e


def counterfactual_cloudflare_live_test_enabled(
    *,
    run_live_api: bool,
    run_counterfactual_cloudflare_e2e: bool,
) -> bool:
    return run_live_api and run_counterfactual_cloudflare_e2e


def product_image_proxy_live_test_enabled(
    *,
    run_live_api: bool,
    run_product_image_proxy_e2e: bool,
) -> bool:
    return run_live_api and run_product_image_proxy_e2e


def provisional_search_live_test_enabled(
    *,
    run_live_api: bool,
    run_clip_runtime: bool,
    run_provisional_search_e2e: bool,
) -> bool:
    return run_live_api and run_clip_runtime and run_provisional_search_e2e


def backend_search_live_test_enabled(
    *, run_live_api: bool, run_clip_runtime: bool, run_backend_search_e2e: bool
) -> bool:
    return run_live_api and run_clip_runtime and run_backend_search_e2e


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    run_clip_runtime = config.getoption("--run-clip-runtime")
    run_live_api = config.getoption("--run-live-api")
    run_bonsai_e2e = config.getoption("--run-bonsai-e2e")
    run_cloudflare_e2e = config.getoption("--run-cloudflare-e2e")
    run_counterfactual_cloudflare_e2e = config.getoption("--run-counterfactual-cloudflare-e2e")
    run_product_image_proxy_e2e = config.getoption("--run-product-image-proxy-e2e")
    run_provisional_search_e2e = config.getoption("--run-provisional-search-e2e")
    run_backend_search_e2e = config.getoption("--run-backend-search-e2e")
    run_latency_diagnostic = config.getoption("--run-bonsai-latency-diagnostic")
    skip_clip_runtime = pytest.mark.skip(reason="requires explicit --run-clip-runtime opt-in")
    skip_live_api = pytest.mark.skip(reason="requires explicit --run-live-api opt-in")
    skip_bonsai_e2e = pytest.mark.skip(
        reason="requires explicit --run-live-api and --run-bonsai-e2e opt-ins"
    )
    skip_bonsai_latency = pytest.mark.skip(
        reason="requires the separately approved --run-bonsai-latency-diagnostic mode"
    )
    skip_cloudflare_e2e = pytest.mark.skip(
        reason="requires explicit --run-live-api and --run-cloudflare-e2e opt-ins"
    )
    skip_counterfactual_cloudflare_e2e = pytest.mark.skip(
        reason=("requires explicit --run-live-api and --run-counterfactual-cloudflare-e2e opt-ins")
    )
    skip_product_image_proxy_e2e = pytest.mark.skip(
        reason="requires explicit --run-live-api and --run-product-image-proxy-e2e opt-ins"
    )
    skip_provisional_search_e2e = pytest.mark.skip(
        reason=(
            "requires explicit --run-live-api, --run-clip-runtime, and "
            "--run-provisional-search-e2e opt-ins"
        )
    )
    for item in items:
        if item.get_closest_marker("backend_search_e2e") is not None and not (
            backend_search_live_test_enabled(
                run_live_api=run_live_api,
                run_clip_runtime=run_clip_runtime,
                run_backend_search_e2e=run_backend_search_e2e,
            )
        ):
            item.add_marker(pytest.mark.skip(reason="requires all backend E2E opt-ins"))
        if item.get_closest_marker("clip_runtime") is not None and not run_clip_runtime:
            item.add_marker(skip_clip_runtime)
        if item.get_closest_marker("live_api") is not None and not run_live_api:
            item.add_marker(skip_live_api)
        if item.get_closest_marker("bonsai_e2e") is not None:
            is_latency_diagnostic = item.get_closest_marker("bonsai_latency_diagnostic") is not None
            if not bonsai_live_test_enabled(
                is_latency_diagnostic=is_latency_diagnostic,
                run_live_api=run_live_api,
                run_bonsai_e2e=run_bonsai_e2e,
                run_latency_diagnostic=run_latency_diagnostic,
            ):
                item.add_marker(skip_bonsai_latency if is_latency_diagnostic else skip_bonsai_e2e)
        if item.get_closest_marker("cloudflare_e2e") is not None and not (
            cloudflare_live_test_enabled(
                run_live_api=run_live_api,
                run_cloudflare_e2e=run_cloudflare_e2e,
            )
        ):
            item.add_marker(skip_cloudflare_e2e)
        if item.get_closest_marker("counterfactual_cloudflare_e2e") is not None and not (
            counterfactual_cloudflare_live_test_enabled(
                run_live_api=run_live_api,
                run_counterfactual_cloudflare_e2e=run_counterfactual_cloudflare_e2e,
            )
        ):
            item.add_marker(skip_counterfactual_cloudflare_e2e)
        if item.get_closest_marker("product_image_proxy_e2e") is not None and not (
            product_image_proxy_live_test_enabled(
                run_live_api=run_live_api,
                run_product_image_proxy_e2e=run_product_image_proxy_e2e,
            )
        ):
            item.add_marker(skip_product_image_proxy_e2e)
        if item.get_closest_marker("provisional_search_e2e") is not None and not (
            provisional_search_live_test_enabled(
                run_live_api=run_live_api,
                run_clip_runtime=run_clip_runtime,
                run_provisional_search_e2e=run_provisional_search_e2e,
            )
        ):
            item.add_marker(skip_provisional_search_e2e)


class _NetworkBlockedSocket(_ORIGINAL_SOCKET):
    """Socket that permits local IPC but rejects IPv4 and IPv6 communication."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        _ORIGINAL_LOW_LEVEL_SOCKET.__init__(self, *args, **kwargs)
        self._io_refs = 0
        self._closed = False

    def _fail_if_network(self) -> None:
        if self.family in _NETWORK_FAMILIES:
            raise AssertionError(_BLOCKED_MESSAGE)

    def connect(self, address: Any) -> None:
        self._fail_if_network()
        return super().connect(address)

    def connect_ex(self, address: Any) -> int:
        self._fail_if_network()
        return super().connect_ex(address)

    def bind(self, address: Any) -> None:
        self._fail_if_network()
        return super().bind(address)

    def accept(self) -> Any:
        self._fail_if_network()
        return super().accept()

    def listen(self, backlog: int = 0) -> None:
        self._fail_if_network()
        return super().listen(backlog)

    def recv(self, bufsize: int, flags: int = 0) -> bytes:
        self._fail_if_network()
        return super().recv(bufsize, flags)

    def recv_into(self, buffer: Any, nbytes: int = 0, flags: int = 0) -> int:
        self._fail_if_network()
        return super().recv_into(buffer, nbytes, flags)

    def recvfrom(self, bufsize: int, flags: int = 0) -> Any:
        self._fail_if_network()
        return super().recvfrom(bufsize, flags)

    def recvfrom_into(
        self,
        buffer: Any,
        nbytes: int = 0,
        flags: int = 0,
    ) -> Any:
        self._fail_if_network()
        return super().recvfrom_into(buffer, nbytes, flags)

    def recvmsg(self, *args: Any) -> Any:
        self._fail_if_network()
        return super().recvmsg(*args)

    def recvmsg_into(self, *args: Any) -> Any:
        self._fail_if_network()
        return super().recvmsg_into(*args)

    def send(self, data: Any, flags: int = 0) -> int:
        self._fail_if_network()
        return super().send(data, flags)

    def sendall(self, data: Any, flags: int = 0) -> None:
        self._fail_if_network()
        return super().sendall(data, flags)

    def sendto(self, *args: Any) -> int:
        self._fail_if_network()
        return super().sendto(*args)

    def sendmsg(self, *args: Any) -> int:
        self._fail_if_network()
        return super().sendmsg(*args)

    def sendfile(self, file: Any, offset: int = 0, count: int | None = None) -> int:
        self._fail_if_network()
        return super().sendfile(file, offset, count)

    def shutdown(self, how: int) -> None:
        self._fail_if_network()
        return super().shutdown(how)


def _block_name_resolution(*args: Any, **kwargs: Any) -> None:
    del args, kwargs
    raise AssertionError(_BLOCKED_MESSAGE)


def _install_network_guard() -> None:
    socket.socket = _NetworkBlockedSocket
    socket.SocketType = _NetworkBlockedSocket
    _socket.socket = _NetworkBlockedSocket
    for name in _ORIGINAL_RESOLVERS:
        setattr(socket, name, _block_name_resolution)


def _restore_network_functions() -> None:
    socket.socket = _ORIGINAL_SOCKET
    socket.SocketType = _ORIGINAL_SOCKET_TYPE
    _socket.socket = _ORIGINAL_LOW_LEVEL_SOCKET
    for name, original in _ORIGINAL_RESOLVERS.items():
        setattr(socket, name, original)


def pytest_configure(config: pytest.Config) -> None:
    del config
    _install_network_guard()


def pytest_unconfigure(config: pytest.Config) -> None:
    del config
    _restore_network_functions()


@pytest.fixture
def original_socket_type(request: pytest.FixtureRequest) -> type[socket.socket]:
    """Expose the unpatched type only for the network policy's self-test."""

    if request.node.get_closest_marker("live_api") is None or not request.config.getoption(
        "--run-live-api"
    ):
        raise RuntimeError("the original socket is available only to an opted-in live_api test")
    return _ORIGINAL_SOCKET


@pytest.fixture(autouse=True)
def block_network_access(
    request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    """Keep collection and normal tests guarded; opt-in live tests restore temporarily."""

    live_opted_in = request.node.get_closest_marker(
        "live_api"
    ) is not None and request.config.getoption("--run-live-api")
    if live_opted_in:
        _restore_network_functions()
    else:
        _install_network_guard()
    from src.search_v2 import playwright_products

    original_worker = playwright_products.run_product_worker
    if not live_opted_in:

        def blocked_browser_worker(*_args, **_kwargs):
            raise RuntimeError("Live Playwright retrieval is disabled in offline tests")

        playwright_products.run_product_worker = blocked_browser_worker
    try:
        yield
    finally:
        playwright_products.run_product_worker = original_worker
        _install_network_guard()


@pytest.fixture(scope="session")
def trusted_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Stage a real test interpreter without inheriting host executable ACLs."""
    directory = tmp_path_factory.mktemp("trusted-python")
    source = Path(sys.executable).resolve(strict=True)
    (directory / "bin").mkdir()
    executable = directory / "bin" / "python"
    shutil.copyfile(source, executable)
    executable.chmod(0o555)
    # execve via /proc/self/fd cannot rely on a nearby pyvenv.cfg.
    stdlib = Path(sysconfig.get_path("stdlib"))
    shutil.copytree(
        stdlib,
        directory / "lib" / stdlib.name,
        copy_function=shutil.copyfile,
        ignore=shutil.ignore_patterns("site-packages", "__pycache__"),
    )
    for library in (Path(sys.base_prefix) / "lib").glob("libpython*so*"):
        shutil.copyfile(library, directory / "lib" / library.name)
    return executable
