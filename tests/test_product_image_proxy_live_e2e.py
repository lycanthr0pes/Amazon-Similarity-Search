from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path

from PIL import Image
from pydantic import SecretStr
import pytest

import conftest as pytest_policy
from src.config import ProductImageProxyLiveSettings
from src.search_v2.image_proxy import ProxyImage
from src.search_v2.image_proxy import proxy_image_pixel_sha256
from src.search_v2.image_similarity import ClipEmbedding
from src.search_v2.image_similarity import clip_runtime_profile_sha256
import tools.product_image_proxy_live_e2e as live_runner
from tools.product_image_proxy_live_e2e import PRODUCT_IMAGE_PROXY_E2E_REQUEST_COUNT
from tools.product_image_proxy_live_e2e import PRODUCT_IMAGE_PROXY_E2E_RETRY_COUNT
from tools.product_image_proxy_live_e2e import ProductImageProxyLiveE2EConfig
from tools.product_image_proxy_live_e2e import ProductImageProxyLiveE2EError
from tools.product_image_proxy_live_e2e import run_product_image_proxy_live_e2e


SOURCE_URL = "https://m.media-amazon.com/images/I/fixture-product.jpg"


def png_bytes(*, offset: int) -> bytes:
    image = Image.new("RGB", (512, 512), (240, 240, 240))
    for coordinate in range(64, 448):
        image.putpixel(
            (coordinate, (coordinate + offset) % 384 + 64),
            (offset % 256, (offset * 3) % 256, (offset * 7) % 256),
        )
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def proxy_image(*, offset: int, source_url: str = SOURCE_URL) -> ProxyImage:
    body = png_bytes(offset=offset)
    with Image.open(BytesIO(body), formats=("PNG",)) as image:
        image.load()
        rgb = image.convert("RGB")
        pixels = rgb.tobytes()
        width, height = rgb.size
    return ProxyImage(
        schema_version="2.0",
        source_url_sha256=hashlib.sha256(source_url.encode()).hexdigest(),
        source_bytes_sha256=hashlib.sha256(body).hexdigest(),
        pixel_sha256=proxy_image_pixel_sha256(width, height, pixels),
        content_type="image/png",
        image_format="PNG",
        width=width,
        height=height,
        rgb_bytes=pixels,
    )


def reference_dir(root: Path) -> Path:
    root.mkdir(mode=0o700)
    for name, offset in (
        ("desired.png", 31),
        ("counterfactual-visual-condition-001.png", 197),
    ):
        path = root / name
        path.write_bytes(png_bytes(offset=offset))
        path.chmod(0o600)
    return root


class RecordingProxy:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[str] = []

    def fetch_image(self, url: str) -> ProxyImage:
        self.calls.append(url)
        if isinstance(self.result, Exception):
            raise self.result
        assert isinstance(self.result, ProxyImage)
        return self.result


def config(tmp_path: Path, *, source_url: str = SOURCE_URL) -> ProductImageProxyLiveE2EConfig:
    return ProductImageProxyLiveE2EConfig(
        source_url=SecretStr(source_url),
        reference_dir=reference_dir(tmp_path / "references"),
        output_path=tmp_path / "candidate.png",
        asset_root=tmp_path / "clip-assets",
    )


def install_embedding_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    def encode(images, *, asset_root, encoder):
        del asset_root, encoder
        runtime = clip_runtime_profile_sha256()
        rows: list[ClipEmbedding] = []
        for index, image in enumerate(images):
            values = [0.0] * 512
            values[0 if index in {0, 2} else 1] = 1.0
            rows.append(
                ClipEmbedding(
                    schema_version="2.0",
                    image_pixel_sha256=image.pixel_sha256,
                    runtime_sha256=runtime,
                    values=tuple(values),
                )
            )
        return tuple(rows)

    monkeypatch.setattr(live_runner, "run_pinned_clip_image_encoder", encode)


def test_runner_fetches_once_scores_with_two_references_and_saves_png(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_embedding_fixture(monkeypatch)
    selected = config(tmp_path)
    service = RecordingProxy(proxy_image(offset=89))

    result = run_product_image_proxy_live_e2e(selected, proxy_service=service)

    assert result.request_count == PRODUCT_IMAGE_PROXY_E2E_REQUEST_COUNT == 1
    assert result.retry_count == PRODUCT_IMAGE_PROXY_E2E_RETRY_COUNT == 0
    assert result.clip_image_count == 3
    assert result.score_status == "scored"
    assert result.normalized_margin == pytest.approx(1.0)
    assert service.calls == [SOURCE_URL]
    assert result.output_path == selected.output_path
    assert selected.output_path.stat().st_mode & 0o777 == 0o600
    with Image.open(selected.output_path, formats=("PNG",)) as image:
        image.load()
        assert image.format == "PNG"
        assert image.mode == "RGB"
        assert image.size == (512, 512)
        assert getattr(image, "n_frames", 1) == 1
        assert image.info == {}
    serialized = json.dumps(result.safe_metadata(), sort_keys=True)
    assert SOURCE_URL not in serialized
    assert SOURCE_URL not in repr(result)
    assert SOURCE_URL not in repr(selected)


def test_runner_rejects_existing_output_before_fetch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_embedding_fixture(monkeypatch)
    selected = config(tmp_path)
    selected.output_path.write_bytes(b"existing")
    service = RecordingProxy(proxy_image(offset=89))

    with pytest.raises(ProductImageProxyLiveE2EError) as captured:
        run_product_image_proxy_live_e2e(selected, proxy_service=service)

    assert captured.value.safe_metadata() == {
        "failure_stage": "output",
        "outcome": "failed",
        "request_count": 0,
        "retry_count": 0,
        "wall_milliseconds": None,
    }
    assert service.calls == []


def test_runner_rejects_non_amazon_media_host_before_fetch(tmp_path: Path) -> None:
    selected = config(tmp_path, source_url="https://images.example.test/product.png")
    service = RecordingProxy(proxy_image(offset=89))

    with pytest.raises(ProductImageProxyLiveE2EError) as captured:
        run_product_image_proxy_live_e2e(selected, proxy_service=service)

    assert captured.value.failure_stage == "configuration"
    assert captured.value.request_count == 0
    assert service.calls == []


def test_runner_rejects_unsafe_reference_before_fetch(tmp_path: Path) -> None:
    selected = config(tmp_path)
    (selected.reference_dir / "desired.png").chmod(0o644)
    service = RecordingProxy(proxy_image(offset=89))

    with pytest.raises(ProductImageProxyLiveE2EError) as captured:
        run_product_image_proxy_live_e2e(selected, proxy_service=service)

    assert captured.value.failure_stage == "reference"
    assert captured.value.request_count == 0
    assert service.calls == []


def test_runner_reduces_fetch_failure_to_fixed_metadata(tmp_path: Path) -> None:
    selected = config(tmp_path)
    sensitive = RuntimeError(f"failed to fetch {SOURCE_URL}")
    service = RecordingProxy(sensitive)

    with pytest.raises(ProductImageProxyLiveE2EError) as captured:
        run_product_image_proxy_live_e2e(selected, proxy_service=service)

    serialized = json.dumps(captured.value.safe_metadata(), sort_keys=True)
    assert captured.value.failure_stage == "fetch"
    assert captured.value.request_count == 1
    assert captured.value.retry_count == 0
    assert isinstance(captured.value.wall_milliseconds, int)
    assert SOURCE_URL not in serialized
    assert str(sensitive) not in serialized
    assert not selected.output_path.exists()


def test_runner_reduces_clip_failure_without_saving(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = config(tmp_path)
    service = RecordingProxy(proxy_image(offset=89))

    def fail(*_args, **_kwargs):
        raise RuntimeError(f"clip failed for {SOURCE_URL}")

    monkeypatch.setattr(live_runner, "run_pinned_clip_image_encoder", fail)
    with pytest.raises(ProductImageProxyLiveE2EError) as captured:
        run_product_image_proxy_live_e2e(selected, proxy_service=service)

    assert captured.value.failure_stage == "clip"
    assert captured.value.request_count == 1
    assert not selected.output_path.exists()
    assert SOURCE_URL not in json.dumps(captured.value.safe_metadata(), sort_keys=True)


@pytest.mark.parametrize(
    ("run_live_api", "run_product_image_proxy_e2e", "expected"),
    [
        (False, False, False),
        (True, False, False),
        (False, True, False),
        (True, True, True),
    ],
)
def test_product_image_proxy_selector_requires_both_opt_ins(
    run_live_api: bool,
    run_product_image_proxy_e2e: bool,
    expected: bool,
) -> None:
    assert (
        pytest_policy.product_image_proxy_live_test_enabled(
            run_live_api=run_live_api,
            run_product_image_proxy_e2e=run_product_image_proxy_e2e,
        )
        is expected
    )


@pytest.mark.live_api
@pytest.mark.clip_runtime
@pytest.mark.product_image_proxy_e2e
def test_single_product_image_proxy_and_clip(pytestconfig: pytest.Config) -> None:
    reference_dir_value = pytestconfig.getoption("--product-image-reference-dir")
    output_path_value = pytestconfig.getoption("--product-image-output-path")
    if not isinstance(reference_dir_value, str) or not isinstance(output_path_value, str):
        pytest.fail("Product image proxy E2E paths are required", pytrace=False)
    try:
        configured = ProductImageProxyLiveSettings()
        result = run_product_image_proxy_live_e2e(
            ProductImageProxyLiveE2EConfig(
                source_url=configured.amazon_product_image_e2e_url,
                reference_dir=Path(reference_dir_value),
                output_path=Path(output_path_value),
                asset_root=Path("models/clip-vit-base-patch32-12b36594").resolve(),
            )
        )
    except ProductImageProxyLiveE2EError as error:
        print(json.dumps(error.safe_metadata(), sort_keys=True, separators=(",", ":")))
        pytest.fail(str(error), pytrace=False)
    except Exception:
        pytest.fail("Product image proxy E2E configuration is invalid", pytrace=False)

    assert result.request_count == PRODUCT_IMAGE_PROXY_E2E_REQUEST_COUNT == 1
    assert result.retry_count == PRODUCT_IMAGE_PROXY_E2E_RETRY_COUNT == 0
    print(json.dumps(result.safe_metadata(), sort_keys=True, separators=(",", ":")))


def test_live_test_has_dedicated_markers() -> None:
    marker_names = {
        marker.name
        for marker in getattr(test_single_product_image_proxy_and_clip, "pytestmark", ())
    }
    assert {"live_api", "clip_runtime", "product_image_proxy_e2e"} <= marker_names


def test_live_settings_masks_source_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AMAZON_PRODUCT_IMAGE_E2E_URL", SOURCE_URL)
    configured = ProductImageProxyLiveSettings(_env_file=None)

    assert configured.amazon_product_image_e2e_url.get_secret_value() == SOURCE_URL
    assert SOURCE_URL not in repr(configured)
