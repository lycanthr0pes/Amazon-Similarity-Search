from __future__ import annotations

import base64
from io import BytesIO
import json
from pathlib import Path

from PIL import Image
from pydantic import SecretStr
import pytest

import conftest as pytest_policy
from src.config import CloudflareLiveSettings
from src.search_v2.counterfactual_cloudflare_http import CloudflareHttpResponse
import tools.counterfactual_cloudflare_live_e2e as live_runner
from tools.counterfactual_cloudflare_live_e2e import (
    COUNTERFACTUAL_CLOUDFLARE_E2E_REQUEST_COUNT,
)
from tools.counterfactual_cloudflare_live_e2e import (
    COUNTERFACTUAL_CLOUDFLARE_E2E_RETRY_COUNT,
)
from tools.counterfactual_cloudflare_live_e2e import SYNTHETIC_INPUT
from tools.counterfactual_cloudflare_live_e2e import (
    CounterfactualCloudflareLiveE2EConfig,
)
from tools.counterfactual_cloudflare_live_e2e import (
    CounterfactualCloudflareLiveE2EError,
)
from tools.counterfactual_cloudflare_live_e2e import (
    run_counterfactual_cloudflare_live_e2e,
)


ACCOUNT_ID = "0123456789abcdef0123456789abcdef"
API_TOKEN = "fixture-cloudflare-api-token"


def image_bytes(*, image_format: str, color: tuple[int, int, int]) -> bytes:
    output = BytesIO()
    Image.new("RGB", (512, 512), color).save(output, format=image_format)
    return output.getvalue()


def response(*, image_format: str, color: tuple[int, int, int]) -> CloudflareHttpResponse:
    image = image_bytes(image_format=image_format, color=color)
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


class ScriptedTransport:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def post_multipart(self, **kwargs: object) -> CloudflareHttpResponse:
        self.calls.append(kwargs)
        current = self.responses.pop(0)
        if isinstance(current, Exception):
            raise current
        assert isinstance(current, CloudflareHttpResponse)
        return current


def test_runner_sends_exact_two_calls_and_saves_only_normalized_pngs(tmp_path: Path) -> None:
    output_dir = tmp_path / "counterfactual-live"
    transport = ScriptedTransport(
        [
            response(image_format="JPEG", color=(245, 245, 240)),
            response(image_format="WEBP", color=(40, 80, 160)),
        ]
    )

    result = run_counterfactual_cloudflare_live_e2e(
        CounterfactualCloudflareLiveE2EConfig(
            account_id=ACCOUNT_ID,
            api_token=SecretStr(API_TOKEN),
            output_dir=output_dir,
        ),
        transport=transport,
    )

    assert result.request_count == COUNTERFACTUAL_CLOUDFLARE_E2E_REQUEST_COUNT == 2
    assert result.retry_count == COUNTERFACTUAL_CLOUDFLARE_E2E_RETRY_COUNT == 0
    assert len(transport.calls) == 2
    assert tuple(path.name for path in result.output_files) == (
        "desired.png",
        "counterfactual-visual-condition-001.png",
    )
    assert output_dir.stat().st_mode & 0o777 == 0o700
    for path in result.output_files:
        assert path.parent == output_dir
        assert path.stat().st_mode & 0o777 == 0o600
        with Image.open(path, formats=("PNG",)) as image:
            image.load()
            assert image.format == "PNG"
            assert image.mode == "RGB"
            assert image.size == (512, 512)
            assert getattr(image, "n_frames", 1) == 1
            assert image.info == {}
    assert API_TOKEN not in repr(result)
    assert SYNTHETIC_INPUT not in repr(result)


def test_runner_rejects_existing_output_before_transport(tmp_path: Path) -> None:
    output_dir = tmp_path / "counterfactual-live"
    output_dir.mkdir()
    transport = ScriptedTransport([])

    with pytest.raises(CounterfactualCloudflareLiveE2EError) as captured:
        run_counterfactual_cloudflare_live_e2e(
            CounterfactualCloudflareLiveE2EConfig(
                account_id=ACCOUNT_ID,
                api_token=SecretStr(API_TOKEN),
                output_dir=output_dir,
            ),
            transport=transport,
        )

    assert captured.value.safe_metadata() == {
        "failure_stage": "output",
        "outcome": "failed",
        "request_count": 0,
        "retry_count": 0,
        "wall_milliseconds": None,
    }
    assert transport.calls == []


def test_runner_reports_partial_failure_without_output_or_secret(tmp_path: Path) -> None:
    output_dir = tmp_path / "counterfactual-live"
    provider_detail = RuntimeError(f"provider rejected {API_TOKEN}")
    transport = ScriptedTransport(
        [
            response(image_format="PNG", color=(245, 245, 240)),
            provider_detail,
        ]
    )

    with pytest.raises(CounterfactualCloudflareLiveE2EError) as captured:
        run_counterfactual_cloudflare_live_e2e(
            CounterfactualCloudflareLiveE2EConfig(
                account_id=ACCOUNT_ID,
                api_token=SecretStr(API_TOKEN),
                output_dir=output_dir,
            ),
            transport=transport,
        )

    diagnostic = captured.value.safe_metadata()
    serialized = json.dumps(diagnostic, sort_keys=True)
    assert diagnostic == {
        "failure_stage": "execution",
        "outcome": "failed",
        "request_count": 2,
        "retry_count": 0,
        "wall_milliseconds": captured.value.wall_milliseconds,
    }
    assert isinstance(captured.value.wall_milliseconds, int)
    assert captured.value.wall_milliseconds >= 1
    assert API_TOKEN not in serialized
    assert str(provider_detail) not in serialized
    assert len(transport.calls) == 2
    assert not output_dir.exists()


def test_runner_reports_consumed_calls_and_time_when_output_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "counterfactual-live"
    transport = ScriptedTransport(
        [
            response(image_format="PNG", color=(245, 245, 240)),
            response(image_format="PNG", color=(40, 80, 160)),
        ]
    )

    def fail_write(_path: Path, _body: bytes) -> None:
        raise OSError("local output detail")

    monkeypatch.setattr(live_runner, "_write_file", fail_write)

    with pytest.raises(CounterfactualCloudflareLiveE2EError) as captured:
        run_counterfactual_cloudflare_live_e2e(
            CounterfactualCloudflareLiveE2EConfig(
                account_id=ACCOUNT_ID,
                api_token=SecretStr(API_TOKEN),
                output_dir=output_dir,
            ),
            transport=transport,
        )

    diagnostic = captured.value.safe_metadata()
    assert diagnostic["failure_stage"] == "output"
    assert diagnostic["request_count"] == 2
    assert diagnostic["retry_count"] == 0
    assert isinstance(diagnostic["wall_milliseconds"], int)
    assert diagnostic["wall_milliseconds"] >= 1
    assert len(transport.calls) == 2
    assert not output_dir.exists()


@pytest.mark.parametrize(
    ("run_live_api", "run_counterfactual_cloudflare_e2e", "expected"),
    [
        (False, False, False),
        (True, False, False),
        (False, True, False),
        (True, True, True),
    ],
)
def test_counterfactual_live_selector_requires_both_opt_ins(
    run_live_api: bool,
    run_counterfactual_cloudflare_e2e: bool,
    expected: bool,
) -> None:
    assert (
        pytest_policy.counterfactual_cloudflare_live_test_enabled(
            run_live_api=run_live_api,
            run_counterfactual_cloudflare_e2e=run_counterfactual_cloudflare_e2e,
        )
        is expected
    )


@pytest.mark.live_api
@pytest.mark.counterfactual_cloudflare_e2e
def test_minimum_counterfactual_cloudflare_reference_set(pytestconfig: pytest.Config) -> None:
    output = pytestconfig.getoption("--counterfactual-cloudflare-output-dir")
    if not isinstance(output, str):
        pytest.fail("Counterfactual Cloudflare E2E requires an output directory", pytrace=False)
    configured = CloudflareLiveSettings()

    try:
        result = run_counterfactual_cloudflare_live_e2e(
            CounterfactualCloudflareLiveE2EConfig(
                account_id=configured.cloudflare_account_id,
                api_token=configured.cloudflare_api_token,
                output_dir=Path(output),
            )
        )
    except CounterfactualCloudflareLiveE2EError as error:
        print(
            json.dumps(
                error.safe_metadata(),
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        pytest.fail(str(error), pytrace=False)

    assert result.request_count == COUNTERFACTUAL_CLOUDFLARE_E2E_REQUEST_COUNT == 2
    assert result.retry_count == COUNTERFACTUAL_CLOUDFLARE_E2E_RETRY_COUNT == 0
    print(
        json.dumps(
            result.safe_metadata(),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def test_counterfactual_live_test_has_dedicated_markers() -> None:
    marker_names = {
        marker.name
        for marker in getattr(
            test_minimum_counterfactual_cloudflare_reference_set,
            "pytestmark",
            (),
        )
    }

    assert {"live_api", "counterfactual_cloudflare_e2e"} <= marker_names
