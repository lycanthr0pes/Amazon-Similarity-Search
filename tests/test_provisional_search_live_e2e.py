from __future__ import annotations

import base64
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from io import BytesIO
import json
from pathlib import Path
import time

from PIL import Image
from PIL import ImageDraw
from pydantic import SecretStr
import pytest

import conftest as pytest_policy
from src.search_v2.counterfactual_cloudflare_http import CloudflareHttpResponse
from src.search_v2.outscraper_http import OutscraperHttpResponse
from src.search_v2.provisional_search_pipeline import ProvisionalSearchPipelineError
import tools.provisional_search_live_e2e as live_runner
from tools.provisional_search_live_e2e import ProductSearchLiveE2EConfig
from tools.provisional_search_live_e2e import ReferencePreparationLiveE2EConfig
from tools.provisional_search_live_e2e import ProvisionalSearchLiveE2EError
from tools.provisional_search_live_e2e import approve_reference_and_run
from tools.provisional_search_live_e2e import prepare_reference_review


NOW = datetime(2026, 9, 8, 8, 0, tzinfo=timezone.utc)
ACCOUNT_ID = "0123456789abcdef0123456789abcdef"
CLOUDFLARE_TOKEN = "fixture-cloudflare-token"
OUTSCRAPER_KEY = "fixture-outscraper-key"
CONFIRMATION_TEXT = "参照画像を確認し商品検索を承認する"


def image_response(*, kind: str) -> CloudflareHttpResponse:
    image = Image.new("RGB", (512, 512), "white")
    draw = ImageDraw.Draw(image)
    if kind == "desired":
        draw.rectangle((128, 96, 384, 416), fill="black")
        draw.rectangle((176, 144, 336, 368), fill="white")
    else:
        draw.ellipse((64, 64, 448, 448), fill="navy")
        draw.line((64, 448, 448, 64), fill="yellow", width=40)
    output = BytesIO()
    image.save(output, format="PNG")
    image.close()
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    body = json.dumps(
        {
            "result": {"image": encoded},
            "success": True,
            "errors": [],
            "messages": [],
        },
        separators=(",", ":"),
    ).encode()
    return CloudflareHttpResponse(
        status_code=200,
        content_type="application/json",
        content_length=len(body),
        content_encoding=None,
        body_chunks=(body,),
    )


class CloudflareTransport:
    def __init__(self) -> None:
        self.responses = [image_response(kind="desired"), image_response(kind="counterfactual")]
        self.calls: list[dict[str, object]] = []

    def post_multipart(self, **kwargs: object) -> CloudflareHttpResponse:
        self.calls.append(kwargs)
        return self.responses.pop(0)


def outscraper_response(payload: object) -> OutscraperHttpResponse:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    return OutscraperHttpResponse(
        status_code=200,
        content_type="application/json; charset=utf-8",
        content_length=len(body),
        content_encoding="identity",
        body_chunks=(body,),
    )


class OutscraperTransport:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get(self, **kwargs: object) -> OutscraperHttpResponse:
        self.calls.append(kwargs)
        return outscraper_response(
            {
                "id": "fixture-task-1",
                "status": "Success",
                "data": [
                    {
                        "query": "白い 陶器製 マグカップ",
                        "name": f"白い陶器製マグカップ {index}",
                        "asin": f"B000MUG{index:03d}",
                        "image_1": f"https://m.media-amazon.com/images/I/fixture-{index}.jpg",
                    }
                    for index in range(1, 5)
                ],
            }
        )


class PipelineResult:
    def safe_metadata(self) -> dict[str, int | str]:
        return {
            "image_request_count": 4,
            "normalized_product_count": 4,
            "outcome": "image_ready",
            "polls_performed": 0,
            "retry_count": 0,
            "task_count": 1,
        }


def preparation_config(tmp_path: Path) -> ReferencePreparationLiveE2EConfig:
    return ReferencePreparationLiveE2EConfig(
        account_id=ACCOUNT_ID,
        api_token=SecretStr(CLOUDFLARE_TOKEN),
        review_dir=tmp_path / "review",
        approval_db_path=tmp_path / "approval.sqlite3",
    )


def test_prepare_stops_after_two_cloudflare_calls_with_pending_private_review(
    tmp_path: Path,
) -> None:
    transport = CloudflareTransport()

    prepared = prepare_reference_review(
        preparation_config(tmp_path),
        transport=transport,
        now=lambda: NOW,
    )

    assert len(transport.calls) == 2
    assert prepared.safe_metadata()["stage"] == "reference_review_pending"
    assert prepared.safe_metadata()["cloudflare_request_count"] == 2
    assert prepared.safe_metadata()["retry_count"] == 0
    assert prepared.review.expires_at == NOW + timedelta(minutes=15)
    assert prepared.review_dir.stat().st_mode & 0o777 == 0o700
    assert tuple(path.name for path in prepared.output_files) == (
        "desired.png",
        "counterfactual-visual-condition-001.png",
    )
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in prepared.output_files)
    serialized = json.dumps(prepared.safe_metadata(), ensure_ascii=False, sort_keys=True)
    assert CLOUDFLARE_TOKEN not in serialized
    assert OUTSCRAPER_KEY not in serialized
    assert "白い陶器製マグカップ" not in serialized
    assert prepared._approval_token not in repr(prepared)
    assert prepared._approval_token.encode() not in (tmp_path / "approval.sqlite3").read_bytes()


def test_changed_review_file_is_rejected_before_product_secret_is_loaded(tmp_path: Path) -> None:
    prepared = prepare_reference_review(
        preparation_config(tmp_path),
        transport=CloudflareTransport(),
        now=lambda: NOW,
    )
    prepared.output_files[0].write_bytes(b"changed")
    loads = 0

    def load_product_config() -> ProductSearchLiveE2EConfig:
        nonlocal loads
        loads += 1
        return ProductSearchLiveE2EConfig(
            api_key=SecretStr(OUTSCRAPER_KEY),
            asset_root=tmp_path,
        )

    with pytest.raises(ProvisionalSearchLiveE2EError) as captured:
        approve_reference_and_run(
            prepared,
            human_confirmed=True,
            load_product_config=load_product_config,
            outscraper_transport=OutscraperTransport(),
            now=lambda: NOW + timedelta(seconds=1),
            sleep=lambda _seconds: None,
        )

    assert captured.value.safe_metadata()["failure_stage"] == "reference_validation"
    assert loads == 0


def test_expired_review_is_rejected_before_product_secret_is_loaded(tmp_path: Path) -> None:
    prepared = prepare_reference_review(
        preparation_config(tmp_path),
        transport=CloudflareTransport(),
        now=lambda: NOW,
    )
    loads = 0

    def load_product_config() -> ProductSearchLiveE2EConfig:
        nonlocal loads
        loads += 1
        return ProductSearchLiveE2EConfig(
            api_key=SecretStr(OUTSCRAPER_KEY),
            asset_root=tmp_path,
        )

    with pytest.raises(ProvisionalSearchLiveE2EError) as captured:
        approve_reference_and_run(
            prepared,
            human_confirmed=True,
            load_product_config=load_product_config,
            outscraper_transport=OutscraperTransport(),
            now=lambda: NOW + timedelta(minutes=15),
            sleep=lambda _seconds: None,
        )

    assert captured.value.safe_metadata()["failure_stage"] == "approval"
    assert loads == 0


def test_approved_review_loads_product_secret_once_and_runs_one_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = prepare_reference_review(
        preparation_config(tmp_path),
        transport=CloudflareTransport(),
        now=lambda: NOW,
    )
    transport = OutscraperTransport()
    loads = 0
    pipeline_calls: list[dict[str, object]] = []

    def load_product_config() -> ProductSearchLiveE2EConfig:
        nonlocal loads
        loads += 1
        return ProductSearchLiveE2EConfig(
            api_key=SecretStr(OUTSCRAPER_KEY),
            asset_root=tmp_path,
        )

    def run_pipeline(**kwargs: object) -> PipelineResult:
        pipeline_calls.append(kwargs)
        return PipelineResult()

    monkeypatch.setattr(live_runner, "run_provisional_search", run_pipeline)

    result = approve_reference_and_run(
        prepared,
        human_confirmed=True,
        load_product_config=load_product_config,
        outscraper_transport=transport,
        proxy_service=object(),
        encoder=object(),
        now=lambda: NOW + timedelta(seconds=1),
        sleep=lambda _seconds: None,
    )

    assert loads == 1
    assert len(transport.calls) == 1
    assert transport.calls[0]["params"]
    assert len(pipeline_calls) == 1
    assert pipeline_calls[0]["execution"].usage_reservation.status == "succeeded"
    assert pipeline_calls[0]["approved_references"].human_confirmed is True
    assert result.safe_metadata()["stage"] == "completed"
    assert result.safe_metadata()["cloudflare_request_count"] == 2
    assert result.safe_metadata()["task_count"] == 1
    serialized = json.dumps(result.safe_metadata(), ensure_ascii=False, sort_keys=True)
    assert CLOUDFLARE_TOKEN not in serialized
    assert OUTSCRAPER_KEY not in serialized
    assert "m.media-amazon.com" not in serialized


def test_pipeline_failure_exposes_only_safe_substage_counts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = prepare_reference_review(
        preparation_config(tmp_path),
        transport=CloudflareTransport(),
        now=lambda: NOW,
    )

    def load_product_config() -> ProductSearchLiveE2EConfig:
        return ProductSearchLiveE2EConfig(
            api_key=SecretStr(OUTSCRAPER_KEY),
            asset_root=tmp_path,
        )

    def fail_pipeline(**_kwargs: object) -> PipelineResult:
        raise ProvisionalSearchPipelineError(
            "Provisional search pipeline inputs are invalid",
            failure_substage="candidate_clip",
            received_candidate_count=24,
            normalized_product_count=23,
            rejected_candidate_count=1,
            products_with_image_url=20,
            image_request_count=20,
            image_fetch_success_count=16,
            reference_clip_batch_count=1,
            candidate_clip_batch_count=2,
        )

    monkeypatch.setattr(live_runner, "run_provisional_search", fail_pipeline)

    with pytest.raises(ProvisionalSearchLiveE2EError) as captured:
        approve_reference_and_run(
            prepared,
            human_confirmed=True,
            load_product_config=load_product_config,
            outscraper_transport=OutscraperTransport(),
            proxy_service=object(),
            encoder=object(),
            now=lambda: NOW + timedelta(seconds=1),
            sleep=lambda _seconds: None,
        )

    assert captured.value.safe_metadata() == {
        "candidate_clip_batch_count": 2,
        "cloudflare_request_count": 2,
        "failure_stage": "ranking",
        "failure_substage": "candidate_clip",
        "image_fetch_success_count": 16,
        "image_request_count": 20,
        "normalized_product_count": 23,
        "outcome": "failed",
        "products_with_image_url": 20,
        "received_candidate_count": 24,
        "reference_clip_batch_count": 1,
        "rejected_candidate_count": 1,
        "retry_count": 0,
        "task_count": 1,
    }
    serialized = json.dumps(captured.value.safe_metadata(), ensure_ascii=False, sort_keys=True)
    assert OUTSCRAPER_KEY not in serialized
    assert "fixture-task-1" not in serialized
    assert "白い 陶器製 マグカップ" not in serialized


@pytest.mark.parametrize(
    ("run_live_api", "run_clip_runtime", "run_provisional_search_e2e", "expected"),
    [
        (False, False, False, False),
        (True, False, True, False),
        (True, True, False, False),
        (True, True, True, True),
    ],
)
def test_provisional_search_selector_requires_all_opt_ins(
    run_live_api: bool,
    run_clip_runtime: bool,
    run_provisional_search_e2e: bool,
    expected: bool,
) -> None:
    assert (
        pytest_policy.provisional_search_live_test_enabled(
            run_live_api=run_live_api,
            run_clip_runtime=run_clip_runtime,
            run_provisional_search_e2e=run_provisional_search_e2e,
        )
        is expected
    )


def test_outscraper_live_settings_masks_the_api_key() -> None:
    from src.config import OutscraperLiveSettings

    configured = OutscraperLiveSettings(
        outscraper_api_key=OUTSCRAPER_KEY,
        _env_file=None,
    )

    assert isinstance(configured.outscraper_api_key, SecretStr)
    assert configured.outscraper_api_key.get_secret_value() == OUTSCRAPER_KEY
    assert OUTSCRAPER_KEY not in repr(configured)


@pytest.mark.live_api
@pytest.mark.clip_runtime
@pytest.mark.provisional_search_e2e
def test_interactive_provisional_product_image_ranking(pytestconfig: pytest.Config) -> None:
    review_dir = pytestconfig.getoption("--provisional-search-review-dir")
    approval_db = pytestconfig.getoption("--provisional-search-approval-db")
    asset_root = pytestconfig.getoption("--provisional-search-clip-asset-root")
    if not all(isinstance(value, str) for value in (review_dir, approval_db, asset_root)):
        pytest.fail("Provisional search E2E requires three absolute output paths", pytrace=False)

    from src.config import CloudflareLiveSettings
    from src.config import OutscraperLiveSettings

    try:
        cloudflare = CloudflareLiveSettings()
        prepared = prepare_reference_review(
            ReferencePreparationLiveE2EConfig(
                account_id=cloudflare.cloudflare_account_id,
                api_token=cloudflare.cloudflare_api_token,
                review_dir=Path(review_dir),
                approval_db_path=Path(approval_db),
            )
        )
        del cloudflare
        print(json.dumps(prepared.safe_metadata(), ensure_ascii=True, sort_keys=True))
        confirmation = input(f"Type exactly '{CONFIRMATION_TEXT}' to continue: ")
        if confirmation != CONFIRMATION_TEXT:
            pytest.fail("Provisional search E2E was not confirmed", pytrace=False)

        def load_product_config() -> ProductSearchLiveE2EConfig:
            configured = OutscraperLiveSettings()
            return ProductSearchLiveE2EConfig(
                api_key=configured.outscraper_api_key,
                asset_root=Path(asset_root),
            )

        result = approve_reference_and_run(
            prepared,
            human_confirmed=True,
            load_product_config=load_product_config,
            sleep=time.sleep,
        )
    except ProvisionalSearchLiveE2EError as error:
        print(json.dumps(error.safe_metadata(), ensure_ascii=True, sort_keys=True))
        pytest.fail(str(error), pytrace=False)

    print(json.dumps(result.safe_metadata(), ensure_ascii=True, sort_keys=True))


def test_interactive_live_test_has_dedicated_markers() -> None:
    marker_names = {
        marker.name
        for marker in getattr(
            test_interactive_provisional_product_image_ranking,
            "pytestmark",
            (),
        )
    }

    assert {"clip_runtime", "live_api", "provisional_search_e2e"} <= marker_names
