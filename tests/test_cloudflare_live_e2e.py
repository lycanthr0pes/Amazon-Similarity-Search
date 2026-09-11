from __future__ import annotations

import base64
from io import BytesIO
import json
from pathlib import Path

from PIL import Image
from pydantic import SecretStr
from pydantic import ValidationError
import pytest

import conftest as pytest_policy
from src.config import CloudflareLiveSettings
from src.config import Settings
from src.search_v2.cloudflare_http import CloudflareHttpResponse
from src.search_v2.cloudflare_http import CloudflareImageError
from src.search_v2.cloudflare_http import CloudflareResponseContractError
from src.search_v2.cloudflare_http import CloudflareTransportError
from tools.cloudflare_live_e2e import CLOUDFLARE_E2E_REQUEST_COUNT
from tools.cloudflare_live_e2e import SYNTHETIC_INPUT
from tools.cloudflare_live_e2e import CloudflareLiveE2EConfig
from tools.cloudflare_live_e2e import CloudflareLiveE2EError
from tools.cloudflare_live_e2e import run_cloudflare_live_e2e


ACCOUNT_ID = "0123456789abcdef0123456789abcdef"
API_TOKEN = "fixture-cloudflare-api-token"


def png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (512, 512), (245, 245, 240)).save(output, format="PNG")
    return output.getvalue()


def jpeg_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (512, 512), (245, 245, 240)).save(output, format="JPEG")
    return output.getvalue()


def response_for(image: bytes) -> CloudflareHttpResponse:
    body = json.dumps(
        {
            "result": {"image": base64.b64encode(image).decode("ascii")},
            "success": True,
            "errors": [],
            "messages": [],
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return CloudflareHttpResponse(
        status_code=200,
        content_type="application/json",
        content_length=len(body),
        content_encoding=None,
        body_chunks=(body,),
    )


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def post_multipart(self, **kwargs: object) -> CloudflareHttpResponse:
        self.calls.append(kwargs)
        return response_for(png_bytes())


class FailingTransport(FakeTransport):
    def post_multipart(self, **kwargs: object) -> CloudflareHttpResponse:
        self.calls.append(kwargs)
        raise RuntimeError(API_TOKEN)


class RaisingTransport(FakeTransport):
    def __init__(self, error: Exception) -> None:
        super().__init__()
        self.error = error

    def post_multipart(self, **kwargs: object) -> CloudflareHttpResponse:
        self.calls.append(kwargs)
        raise self.error


class StaticResponseTransport(FakeTransport):
    def __init__(self, response: CloudflareHttpResponse) -> None:
        super().__init__()
        self.response = response

    def post_multipart(self, **kwargs: object) -> CloudflareHttpResponse:
        self.calls.append(kwargs)
        return self.response


def test_settings_load_cloudflare_secret_without_repr_exposure() -> None:
    configured = CloudflareLiveSettings(
        _env_file=None,
        cloudflare_account_id=ACCOUNT_ID,
        cloudflare_api_token=API_TOKEN,
    )

    assert configured.cloudflare_account_id == ACCOUNT_ID
    assert isinstance(configured.cloudflare_api_token, SecretStr)
    assert configured.cloudflare_api_token.get_secret_value() == API_TOKEN
    assert API_TOKEN not in repr(configured)
    assert API_TOKEN not in configured.model_dump_json()
    assert "cloudflare_api_token" not in Settings.model_fields


def test_standard_settings_do_not_retain_cloudflare_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", ACCOUNT_ID)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", API_TOKEN)

    configured = Settings(_env_file=None)

    assert "cloudflare_account_id" not in configured.model_dump()
    assert "cloudflare_api_token" not in configured.model_dump()
    assert API_TOKEN not in repr(configured)


@pytest.mark.parametrize("api_token", ["", "contains space", "秘密", "x" * 4_097])
def test_live_settings_reject_invalid_cloudflare_api_token(api_token: str) -> None:
    with pytest.raises(ValidationError):
        CloudflareLiveSettings(
            _env_file=None,
            cloudflare_account_id=ACCOUNT_ID,
            cloudflare_api_token=api_token,
        )


@pytest.mark.parametrize("account_id", ["short", "G" * 32, "0" * 33])
def test_settings_reject_invalid_cloudflare_account_id(account_id: str) -> None:
    with pytest.raises(ValidationError):
        CloudflareLiveSettings(
            _env_file=None,
            cloudflare_account_id=account_id,
            cloudflare_api_token=API_TOKEN,
        )


@pytest.mark.parametrize(
    ("run_live_api", "run_cloudflare_e2e", "expected"),
    [
        (False, False, False),
        (True, False, False),
        (False, True, False),
        (True, True, True),
    ],
)
def test_cloudflare_live_selector_requires_both_opt_ins(
    run_live_api: bool,
    run_cloudflare_e2e: bool,
    expected: bool,
) -> None:
    assert (
        pytest_policy.cloudflare_live_test_enabled(
            run_live_api=run_live_api,
            run_cloudflare_e2e=run_cloudflare_e2e,
        )
        is expected
    )


def test_runner_sends_one_request_and_saves_only_normalized_png(tmp_path: Path) -> None:
    output_path = tmp_path / "cloudflare-reference.png"
    transport = FakeTransport()

    result = run_cloudflare_live_e2e(
        CloudflareLiveE2EConfig(
            account_id=ACCOUNT_ID,
            api_token=SecretStr(API_TOKEN),
            output_path=output_path,
        ),
        transport=transport,
    )

    assert result.request_count == CLOUDFLARE_E2E_REQUEST_COUNT == 1
    assert result.retry_count == 0
    assert len(transport.calls) == 1
    assert transport.calls[0]["api_token"] == API_TOKEN
    assert transport.calls[0]["allow_redirects"] is False
    assert output_path.is_file()
    assert output_path.stat().st_mode & 0o777 == 0o600
    assert len(output_path.read_bytes()) == result.image_bytes


def test_runner_normalizes_jpeg_response_before_exclusive_save(tmp_path: Path) -> None:
    output_path = tmp_path / "cloudflare-reference.png"
    transport = StaticResponseTransport(response_for(jpeg_bytes()))

    result = run_cloudflare_live_e2e(
        CloudflareLiveE2EConfig(
            account_id=ACCOUNT_ID,
            api_token=SecretStr(API_TOKEN),
            output_path=output_path,
        ),
        transport=transport,
    )

    assert result.request_count == 1
    with Image.open(output_path, formats=("PNG",)) as image:
        assert image.format == "PNG"
        assert image.mode == "RGB"
        assert image.size == (512, 512)
        assert image.info == {}
    assert result.width == result.height == 512
    assert API_TOKEN not in repr(result)
    assert SYNTHETIC_INPUT not in repr(result)


def test_runner_rejects_missing_secret_before_transport(tmp_path: Path) -> None:
    transport = FakeTransport()

    with pytest.raises(CloudflareLiveE2EError, match="^Cloudflare E2E configuration is invalid$"):
        run_cloudflare_live_e2e(
            CloudflareLiveE2EConfig(
                account_id=ACCOUNT_ID,
                api_token=SecretStr(""),
                output_path=tmp_path / "cloudflare-reference.png",
            ),
            transport=transport,
        )

    assert transport.calls == []


def test_runner_rejects_existing_output_before_transport(tmp_path: Path) -> None:
    output_path = tmp_path / "cloudflare-reference.png"
    output_path.write_bytes(b"existing")
    transport = FakeTransport()

    with pytest.raises(CloudflareLiveE2EError, match="^Cloudflare E2E output is invalid$"):
        run_cloudflare_live_e2e(
            CloudflareLiveE2EConfig(
                account_id=ACCOUNT_ID,
                api_token=SecretStr(API_TOKEN),
                output_path=output_path,
            ),
            transport=transport,
        )

    assert transport.calls == []
    assert output_path.read_bytes() == b"existing"


def test_runner_hides_provider_failure_and_does_not_create_output(tmp_path: Path) -> None:
    output_path = tmp_path / "cloudflare-reference.png"
    transport = FailingTransport()

    with pytest.raises(CloudflareLiveE2EError) as captured:
        run_cloudflare_live_e2e(
            CloudflareLiveE2EConfig(
                account_id=ACCOUNT_ID,
                api_token=SecretStr(API_TOKEN),
                output_path=output_path,
            ),
            transport=transport,
        )

    assert str(captured.value) == "Cloudflare E2E request failed"
    assert API_TOKEN not in str(captured.value)
    assert len(transport.calls) == 1
    assert not output_path.exists()


@pytest.mark.parametrize(
    ("error", "expected_stage"),
    [
        (CloudflareTransportError("provider transport detail"), "transport"),
        (
            CloudflareResponseContractError("provider response detail"),
            "response_contract",
        ),
        (CloudflareImageError("provider image detail"), "image_content"),
        (RuntimeError("unexpected provider detail"), "unexpected"),
    ],
)
def test_runner_classifies_failure_without_provider_detail(
    tmp_path: Path,
    error: Exception,
    expected_stage: str,
) -> None:
    output_path = tmp_path / "cloudflare-reference.png"
    transport = RaisingTransport(error)

    with pytest.raises(CloudflareLiveE2EError) as captured:
        run_cloudflare_live_e2e(
            CloudflareLiveE2EConfig(
                account_id=ACCOUNT_ID,
                api_token=SecretStr(API_TOKEN),
                output_path=output_path,
            ),
            transport=transport,
        )

    diagnostic = captured.value.safe_metadata()
    serialized = json.dumps(diagnostic, sort_keys=True)
    assert diagnostic == {
        "failure_stage": expected_stage,
        "http_status_code": None,
        "outcome": "failed",
        "request_count": 1,
        "retry_count": 0,
        "wall_milliseconds": captured.value.wall_milliseconds,
    }
    assert isinstance(captured.value.wall_milliseconds, int)
    assert captured.value.wall_milliseconds >= 1
    assert API_TOKEN not in serialized
    assert str(error) not in serialized
    assert len(transport.calls) == 1
    assert not output_path.exists()


@pytest.mark.parametrize("status_code", [400, 401, 403, 429, 500])
def test_runner_reports_only_validated_non_success_status(
    tmp_path: Path,
    status_code: int,
) -> None:
    marker = "provider response must not appear"
    transport = StaticResponseTransport(
        CloudflareHttpResponse(
            status_code=status_code,
            content_type="application/json",
            content_length=len(marker),
            content_encoding=None,
            body_chunks=(marker.encode(),),
        )
    )

    with pytest.raises(CloudflareLiveE2EError) as captured:
        run_cloudflare_live_e2e(
            CloudflareLiveE2EConfig(
                account_id=ACCOUNT_ID,
                api_token=SecretStr(API_TOKEN),
                output_path=tmp_path / "cloudflare-reference.png",
            ),
            transport=transport,
        )

    diagnostic = captured.value.safe_metadata()
    assert diagnostic["failure_stage"] == "http_status"
    assert diagnostic["http_status_code"] == status_code
    assert marker not in json.dumps(diagnostic, sort_keys=True)


def test_runner_classifies_actual_response_contract_failure(tmp_path: Path) -> None:
    transport = StaticResponseTransport(
        CloudflareHttpResponse(
            status_code=200,
            content_type="application/json",
            content_length=2,
            content_encoding=None,
            body_chunks=(b"{}",),
        )
    )

    with pytest.raises(CloudflareLiveE2EError) as captured:
        run_cloudflare_live_e2e(
            CloudflareLiveE2EConfig(
                account_id=ACCOUNT_ID,
                api_token=SecretStr(API_TOKEN),
                output_path=tmp_path / "cloudflare-reference.png",
            ),
            transport=transport,
        )

    assert captured.value.failure_stage == "response_contract"


def test_runner_classifies_actual_image_failure(tmp_path: Path) -> None:
    class InvalidImageTransport(FakeTransport):
        def post_multipart(self, **kwargs: object) -> CloudflareHttpResponse:
            self.calls.append(kwargs)
            return response_for(b"not-an-image")

    with pytest.raises(CloudflareLiveE2EError) as captured:
        run_cloudflare_live_e2e(
            CloudflareLiveE2EConfig(
                account_id=ACCOUNT_ID,
                api_token=SecretStr(API_TOKEN),
                output_path=tmp_path / "cloudflare-reference.png",
            ),
            transport=InvalidImageTransport(),
        )

    assert captured.value.failure_stage == "image_content"


def test_output_failure_after_response_reports_one_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = "local output detail"

    def fail_open(*_args: object, **_kwargs: object) -> int:
        raise OSError(marker)

    monkeypatch.setattr("tools.cloudflare_live_e2e.os.open", fail_open)

    with pytest.raises(CloudflareLiveE2EError) as captured:
        run_cloudflare_live_e2e(
            CloudflareLiveE2EConfig(
                account_id=ACCOUNT_ID,
                api_token=SecretStr(API_TOKEN),
                output_path=tmp_path / "cloudflare-reference.png",
            ),
            transport=FakeTransport(),
        )

    diagnostic = captured.value.safe_metadata()
    assert diagnostic["failure_stage"] == "output"
    assert diagnostic["request_count"] == 1
    assert isinstance(diagnostic["wall_milliseconds"], int)
    assert marker not in json.dumps(diagnostic, sort_keys=True)


def test_configuration_failure_reports_zero_requests(tmp_path: Path) -> None:
    with pytest.raises(CloudflareLiveE2EError) as captured:
        CloudflareLiveE2EConfig(
            account_id="invalid",
            api_token=SecretStr(API_TOKEN),
            output_path=tmp_path / "cloudflare-reference.png",
        )

    assert captured.value.safe_metadata() == {
        "failure_stage": "configuration",
        "http_status_code": None,
        "outcome": "failed",
        "request_count": 0,
        "retry_count": 0,
        "wall_milliseconds": None,
    }


@pytest.mark.live_api
@pytest.mark.cloudflare_e2e
def test_single_cloudflare_reference_image(pytestconfig: pytest.Config) -> None:
    output = pytestconfig.getoption("--cloudflare-output-path")
    if not isinstance(output, str):
        pytest.fail("Cloudflare E2E requires an explicit output path", pytrace=False)
    configured = CloudflareLiveSettings()

    try:
        result = run_cloudflare_live_e2e(
            CloudflareLiveE2EConfig(
                account_id=configured.cloudflare_account_id,
                api_token=configured.cloudflare_api_token,
                output_path=Path(output),
            )
        )
    except CloudflareLiveE2EError as error:
        print(
            json.dumps(
                error.safe_metadata(),
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        pytest.fail(str(error), pytrace=False)

    assert result.request_count == CLOUDFLARE_E2E_REQUEST_COUNT == 1
    assert result.retry_count == 0
    assert result.width == result.height == 512
    print(
        json.dumps(
            {
                "image_bytes": result.image_bytes,
                "image_sha256": result.image_sha256,
                "model_id": result.model_id,
                "output_path": str(result.output_path),
                "request_count": result.request_count,
                "retry_count": result.retry_count,
                "seed": result.seed,
                "wall_milliseconds": result.wall_milliseconds,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def test_cloudflare_live_test_has_dedicated_markers() -> None:
    marker_names = {
        marker.name
        for marker in getattr(
            test_single_cloudflare_reference_image,
            "pytestmark",
            (),
        )
    }

    assert {"live_api", "cloudflare_e2e"} <= marker_names
