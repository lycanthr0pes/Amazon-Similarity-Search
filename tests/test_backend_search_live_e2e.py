from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import stat

import pytest

from src.config import CloudflareLiveSettings
from src.search_v2.bonsai_request import BonsaiHttpResponse
from tools.backend_search_live_e2e import BackendE2EConfig
from tools.backend_search_live_e2e import BackendE2EServices
from tools.backend_search_live_e2e import BackendSearchE2EError
from tools.backend_search_live_e2e import run_backend_search_e2e
from test_search_v2_orchestrator import ACCOUNT_ID
from test_search_v2_orchestrator import CLOUDFLARE_TOKEN
from test_search_v2_orchestrator import CloudflareTransport
from test_search_v2_orchestrator import cloudflare_responses
import test_search_v2_production_search as production


class BonsaiTransport:
    def __init__(self):
        self.calls = 0

    def post_json(self, **_kwargs):
        self.calls += 1
        content = json.dumps(
            {
                "product_name_ja": "マグカップ",
                "required_terms_ja": ["白い", "陶器製"],
                "typed_conditions": [
                    {
                        "attribute_key": "appearance.color",
                        "strength": "required",
                        "operator": "equals",
                        "expected_value": {"value_type": "enum", "values": ["white"]},
                    },
                    {
                        "attribute_key": "material.type",
                        "strength": "required",
                        "operator": "equals",
                        "expected_value": {"value_type": "enum", "values": ["earthenware"]},
                    },
                ],
            },
            ensure_ascii=False,
        )
        body = json.dumps(
            {
                "id": "private-provider-response",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": content},
                        "index": 0,
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
            ensure_ascii=False,
        ).encode()
        return BonsaiHttpResponse(
            status_code=200,
            content_type="application/json",
            content_length=len(body),
            content_encoding="identity",
            body_chunks=(body,),
        )


@pytest.fixture
def environment(tmp_path, monkeypatch):
    import src.search_v2.counterfactual_product_evaluator as evaluator

    candidates = [production.proxy_image(f"candidate-{index}") for index in range(1, 5)]
    proxy = production.ProxyService(
        {
            f"https://m.media-amazon.com/images/product-{index}.png": candidate
            for index, candidate in enumerate(candidates, 1)
        }
    )

    def run_clip(images, *, asset_root, encoder):
        del asset_root, encoder
        return tuple(
            production.ClipEmbedding(
                schema_version="2.0",
                image_pixel_sha256=image.pixel_sha256,
                runtime_sha256=production.clip_runtime_profile_sha256(),
                values=production.vector(0.0, 1.0)
                if len(images) == 2 and index == 1
                else production.vector(1.0, 0.0),
            )
            for index, image in enumerate(images)
        )

    monkeypatch.setattr(evaluator, "run_pinned_clip_image_encoder", run_clip)
    bonsai = BonsaiTransport()
    images = CloudflareTransport(cloudflare_responses() * 2)
    products = production.OutscraperTransport()
    loads = []
    time = [production.NOW]
    assets = tmp_path / "assets"
    assets.mkdir()
    config = BackendE2EConfig(tmp_path / "run", assets)

    def load_cloudflare():
        loads.append("cloudflare")
        return CloudflareLiveSettings(
            _env_file=None,
            cloudflare_account_id=ACCOUNT_ID,
            cloudflare_api_token=CLOUDFLARE_TOKEN,
        )

    def load_outscraper():
        loads.append("outscraper")
        return production.SecretStr("fixture-product-key")

    services = BackendE2EServices(
        bonsai_session=lambda: nullcontext(bonsai),
        load_cloudflare=load_cloudflare,
        cloudflare_transport=images,
        load_outscraper_api_key=load_outscraper,
        outscraper_transport=products,
        proxy_service=proxy,
        encoder=production.ClipEncoder(),
        now=lambda: time[0],
        sleep=lambda _seconds: None,
        confirm=lambda *_args: False,
    )
    return config, services, bonsai, images, products, loads, time


def test_first_image_waits_for_human_and_rejection_sends_nothing_more(environment):
    config, services, bonsai, images, products, loads, _ = environment

    def reject(stage, review):
        assert stage == "reference"
        assert len(images.calls) == 1 and products.calls == 0
        assert len(review["images"]) == 1
        assert Path(review["images"][0]).read_bytes().startswith(b"\x89PNG")
        return False

    result = run_backend_search_e2e(config, replace(services, confirm=reject))

    assert result["status"] == "reference_declined"
    assert bonsai.calls == 1 and len(images.calls) == 1 and products.calls == 0
    assert loads == ["cloudflare"]
    assert not (config.output_dir / "history.sqlite3").exists()


def test_full_backend_flow_saves_ranking_and_reopens_the_same_history(environment):
    config, services, bonsai, images, products, loads, _ = environment
    stages = []

    def approve(stage, review):
        stages.append(stage)
        assert products.calls == 0
        assert len(images.calls) == (1 if stage == "reference" else 2)
        assert len(review["images"]) == (1 if stage == "reference" else 2)
        return True

    result = run_backend_search_e2e(config, replace(services, confirm=approve))

    assert result["status"] == "succeeded"
    assert stages == ["reference", "search"]
    assert bonsai.calls == 1 and len(images.calls) == 2 and products.calls == 1
    assert loads == ["cloudflare", "outscraper"]
    assert result["history_reopened"] is True
    assert result["history_reference_images_verified"] == 2
    ranking = json.loads((config.output_dir / "ranking.json").read_text())
    history = json.loads((config.output_dir / "history.json").read_text())
    assert ranking["products"] == history["products"]
    assert len(ranking["products"]) == 4
    assert [item["rank"] for item in ranking["products"]] == [1, 2, 3, 4]
    query = json.loads((config.output_dir / "query.json").read_text())
    assert len(query["queries"]) == 1
    assert "マグカップ" in query["queries"][0]
    assert len(list(config.output_dir.glob("*.png"))) == 2
    assert stat.S_IMODE(config.output_dir.stat().st_mode) == 0o700
    for path in config.output_dir.iterdir():
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        body = path.read_bytes()
        for secret in (
            CLOUDFLARE_TOKEN,
            "fixture-product-key",
            "private-provider-response",
            "fixture-task",
        ):
            assert secret.encode() not in body


def test_rejected_final_images_do_not_load_product_credentials(environment):
    config, services, _, images, products, loads, _ = environment
    result = run_backend_search_e2e(
        config,
        replace(services, confirm=lambda stage, _review: stage == "reference"),
    )
    assert result["status"] == "search_declined"
    assert len(images.calls) == 2 and products.calls == 0
    assert loads == ["cloudflare"]


@pytest.mark.parametrize("change", ["preview", "expired", "truthy"])
def test_unapproved_or_changed_reference_cannot_start_derived_images(environment, change):
    config, services, _, images, products, loads, time = environment

    def change_review(_stage, review):
        if change == "preview":
            Path(review["images"][0]).write_bytes(b"changed")
        if change == "expired":
            time[0] += timedelta(minutes=16)
        return 1 if change == "truthy" else True

    with pytest.raises(BackendSearchE2EError):
        run_backend_search_e2e(config, replace(services, confirm=change_review))
    assert len(images.calls) == 1 and products.calls == 0
    assert loads == ["cloudflare"]


def test_existing_output_cannot_be_reused_to_repeat_a_search(environment):
    config, services, bonsai, images, products, _, _ = environment
    config.output_dir.mkdir()
    with pytest.raises(BackendSearchE2EError):
        run_backend_search_e2e(config, services)
    assert bonsai.calls == 0 and len(images.calls) == 0 and products.calls == 0


def test_live_image_transport_routes_each_request_to_its_production_adapter(
    environment, monkeypatch
):
    from src.search_v2.cloudflare_http import RequestsCloudflareTransport
    from src.search_v2.counterfactual_cloudflare_http import (
        RequestsCounterfactualCloudflareTransport,
    )
    from tools.backend_search_live_e2e import RequestsBackendImageTransport

    config, services, _, images, products, _, _ = environment
    routed = []

    def counterfactual(_self, **kwargs):
        routed.append(kwargs["request"].target)
        return images.post_multipart(**kwargs)

    def angle(_self, **kwargs):
        routed.append(kwargs["request"].angle)
        return images.post_multipart(**kwargs)

    monkeypatch.setattr(RequestsCounterfactualCloudflareTransport, "post_multipart", counterfactual)
    monkeypatch.setattr(RequestsCloudflareTransport, "post_multipart", angle)
    result = run_backend_search_e2e(
        config,
        replace(
            services,
            cloudflare_transport=RequestsBackendImageTransport(),
            confirm=lambda stage, _review: stage == "reference",
        ),
    )
    assert result["status"] == "search_declined"
    assert routed == ["desired", "counterfactual"]
    assert products.calls == 0


def test_failed_product_job_keeps_actual_counts_without_raw_exception(environment):
    config, services, _, _, _, _, _ = environment
    with pytest.raises(BackendSearchE2EError) as caught:
        run_backend_search_e2e(
            config,
            replace(
                services,
                confirm=lambda *_args: True,
                outscraper_transport=production.FailingOutscraperTransport(),
            ),
        )
    metadata = caught.value.safe_metadata()
    assert metadata["failure_stage"] == "product_job"
    assert metadata["bonsai_calls"] == 1
    assert metadata["cloudflare_calls"] == 2
    assert metadata["outscraper_tasks"] == 1
    assert metadata["product_image_requests"] == 0
    assert metadata["retry_count"] == 0
    assert "sensitive fixture provider detail" not in json.dumps(metadata)
    assert not (config.output_dir / "ranking.json").exists()


@pytest.mark.parametrize("kind", ["derived_file", "expired"])
def test_final_review_change_stops_before_product_secret(environment, kind):
    config, services, _, images, products, loads, time = environment

    def confirm(stage, review):
        if stage == "search":
            if kind == "derived_file":
                Path(review["images"][-1]).write_bytes(b"changed")
            else:
                time[0] += timedelta(minutes=16)
        return True

    with pytest.raises(BackendSearchE2EError):
        run_backend_search_e2e(config, replace(services, confirm=confirm))
    assert len(images.calls) == 2 and products.calls == 0
    assert loads == ["cloudflare"]


@pytest.mark.parametrize(
    "failure,expected_stage,expected_status",
    [
        ("transport", "transport", None),
        ("http", "http_status", 503),
        ("json", "response_contract", None),
        ("base64", "image_encoding", None),
        ("image", "image_content", None),
    ],
)
def test_reference_failure_reports_safe_substage_without_retry(
    environment, failure, expected_stage, expected_status
):
    import base64
    from src.search_v2.cloudflare_http import CloudflareHttpResponse

    config, services, _, images, products, loads, _ = environment
    private = "private-response-with-api-key-and-prompt"
    body = json.dumps(
        {"result": {"image": "!invalid-base64!"}, "success": True, "errors": [], "messages": []}
    ).encode()
    if failure == "json":
        body = private.encode()
    elif failure == "image":
        body = json.dumps(
            {
                "result": {"image": base64.b64encode(private.encode()).decode()},
                "success": True,
                "errors": [],
                "messages": [],
            }
        ).encode()
    response = CloudflareHttpResponse(
        status_code=503 if failure == "http" else 200,
        content_type="application/json",
        content_length=len(body),
        content_encoding="identity",
        body_chunks=(body,),
    )
    images.responses = [RuntimeError(private) if failure == "transport" else response]
    with pytest.raises(BackendSearchE2EError) as caught:
        run_backend_search_e2e(config, services)
    result = caught.value.safe_metadata()
    assert result["cloudflare_failure"] == {
        "stage": expected_stage,
        "http_status_code": expected_status,
        "provider_error_code": None,
    }
    assert result["failure_stage"] == "reference_generation"
    assert len(images.calls) == 1 and products.calls == 0
    assert loads == ["cloudflare"]
    assert private not in json.dumps(result)
    assert not (config.output_dir / "preview.png").exists()


@pytest.mark.parametrize("code", [3036, 3040])
def test_reference_failure_propagates_provider_code(environment, code):
    from src.search_v2.counterfactual_cloudflare_http import CloudflareFailureDiagnostic
    from src.search_v2.counterfactual_cloudflare_http import CounterfactualCloudflareExecutionError

    config, services, _, images, products, _, _ = environment
    images.responses = [
        CounterfactualCloudflareExecutionError(
            "fixed failure",
            diagnostic=CloudflareFailureDiagnostic(
                stage="http_status", http_status_code=429, provider_error_code=code
            ),
        )
    ]
    with pytest.raises(BackendSearchE2EError) as caught:
        run_backend_search_e2e(config, services)
    assert caught.value.safe_metadata()["cloudflare_failure"] == {
        "stage": "http_status",
        "http_status_code": 429,
        "provider_error_code": code,
    }
    assert len(images.calls) == 1 and products.calls == 0
