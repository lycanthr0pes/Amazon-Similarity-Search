from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from datetime import timezone
from pathlib import Path

from pydantic import SecretStr
import pytest

from src.search_v2.counterfactual_image import VisualConditionDraft
from src.search_v2.counterfactual_image import build_counterfactual_reference_set
from src.search_v2.counterfactual_image import build_visual_condition_set
from src.search_v2.counterfactual_reference_approval import ApprovedCounterfactualReferences
from src.search_v2.image_proxy import ProxyImage
from src.search_v2.image_proxy import proxy_image_pixel_sha256
from src.search_v2.image_similarity import CLIP_EMBEDDING_DIMENSION
from src.search_v2.image_similarity import ClipEmbedding
from src.search_v2.image_similarity import ImagePerceptualHash
from src.search_v2.image_similarity import clip_runtime_profile_sha256
from src.search_v2.orchestrator import ApprovedSearch
from src.search_v2.orchestrator import BonsaiIntentConfig
from src.search_v2.orchestrator import ProviderAttemptBudget
from src.search_v2.orchestrator import SearchBackendPolicy
from src.search_v2.orchestrator import approve_search
from src.search_v2.orchestrator import skip_images
from src.search_v2.orchestrator import start_intent_review
from src.search_v2.bonsai_request import BonsaiHttpResponse
from src.search_v2.outscraper_http import OutscraperHttpResponse
from src.search_v2.product_normalization import ProductNormalizationProfile
from src.search_v2.production_search import ProductionSearchCommand
from src.search_v2.production_search import ProductionSearchError
from src.search_v2.production_search import ProvisionalProductionSearchService
from src.search_v2.production_search import production_search_job_binding_sha256
from src.search_v2.provisional_history_repository import SqliteProvisionalHistoryRepository
from src.search_v2.search_job import LOCAL_SEARCH_OWNER_ID
from src.search_v2.search_job import LocalSearchJobExecutor
from src.search_v2.search_job import SqliteSearchJobRepository
from src.search_v2.state_machine import InMemoryApprovalLedger
from src.search_v2.typed_ranking import TYPED_RANKING_PROFILE_V4
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import ProviderUsageLimits
from src.search_v2.usage_ledger import UsageAmount
from src.search_v2.usage_ledger import build_no_quota_usage_policies


NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
SOURCE = "黒いマウスを探す"
SESSION_ID = "production-fixture-session"


def digest(tag: str) -> str:
    return hashlib.sha256(tag.encode()).hexdigest()


def proxy_image(tag: str) -> ProxyImage:
    rgb = hashlib.sha256(tag.encode()).digest()[:3] * 4
    return ProxyImage(
        schema_version="2.0",
        source_url_sha256=digest(f"url-{tag}"),
        source_bytes_sha256=digest(f"bytes-{tag}"),
        pixel_sha256=proxy_image_pixel_sha256(2, 2, rgb),
        content_type="image/png",
        image_format="PNG",
        width=2,
        height=2,
        rgb_bytes=rgb,
    )


class BonsaiTransport:
    def post_json(self, **_kwargs: object) -> BonsaiHttpResponse:
        content = json.dumps(
            {
                "product_name_ja": "マウス",
                "typed_conditions": [
                    {
                        "attribute_key": "appearance.color",
                        "strength": "required",
                        "operator": "equals",
                        "expected_value": {"value_type": "enum", "values": ["black"]},
                    }
                ],
                "required_terms_ja": ["黒"],
                "required_terms_en": [],
                "preferred_terms_ja": [],
                "preferred_terms_en": [],
                "negative_terms_ja": [],
                "negative_terms_en": [],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        body = json.dumps(
            {
                "id": "fixture-response",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        return BonsaiHttpResponse(
            status_code=200,
            content_type="application/json; charset=utf-8",
            content_length=len(body),
            content_encoding="identity",
            body_chunks=(body,),
        )


def usage_ledger() -> InMemoryUsageLedger:
    return InMemoryUsageLedger(
        build_no_quota_usage_policies(
            bonsai_pricing_policy_sha256="a" * 64,
            cloudflare_pricing_policy_sha256="b" * 64,
            outscraper_pricing_policy_sha256="c" * 64,
        )
    )


def enforced_usage_ledger() -> InMemoryUsageLedger:
    limit = UsageAmount(calls=1_000, tokens=1_000_000, cost_microusd=1_000_000)
    return InMemoryUsageLedger(
        [
            ProviderUsageLimits(
                provider=provider,
                pricing_policy_sha256=pricing_digest,
                per_user_day=limit,
                per_session=limit,
                global_day=limit,
            )
            for provider, pricing_digest in (
                ("bonsai", "a" * 64),
                ("cloudflare", "b" * 64),
                ("outscraper", "c" * 64),
            )
        ]
    )


def backend_policy() -> SearchBackendPolicy:
    return SearchBackendPolicy(
        schema_version="3.0",
        bonsai_intent=ProviderAttemptBudget(
            amount=UsageAmount(calls=1, tokens=2_000_000, cost_microusd=0),
            pricing_policy_sha256="a" * 64,
        ),
        cloudflare_image_set=ProviderAttemptBudget(
            amount=UsageAmount(calls=4, tokens=0, cost_microusd=0),
            pricing_policy_sha256="b" * 64,
        ),
        outscraper_search=ProviderAttemptBudget(
            amount=UsageAmount(calls=1, tokens=0, cost_microusd=0),
            pricing_policy_sha256="c" * 64,
        ),
        normalization_profile=ProductNormalizationProfile(
            schema_version="2.0",
            profile_id="observed-only-v2",
            usd_to_jpy_rate=160,
        ),
        ranking_profile=TYPED_RANKING_PROFILE_V4,
        implementation_sha256="d" * 64,
    )


def approved_search(ledger: InMemoryUsageLedger) -> ApprovedSearch:
    stage = start_intent_review(
        SOURCE,
        owner_id=LOCAL_SEARCH_OWNER_ID,
        session_id=SESSION_ID,
        bonsai_config=BonsaiIntentConfig(
            base_url="http://127.0.0.1:8080/v1",
            model_id="Bonsai-8B.gguf",
            temperature=0.1,
        ),
        policy=backend_policy(),
        usage_ledger=ledger,
        transport=BonsaiTransport(),
        now=lambda: NOW,
    )
    review = skip_images(
        stage,
        postal_code="100-0001",
        policy=backend_policy(),
        usage_ledger=ledger,
        now=lambda: NOW,
    )
    return approve_search(review, now=lambda: NOW)


def approved_references():
    conditions = build_visual_condition_set(
        source_input=SOURCE,
        drafts=(
            VisualConditionDraft(
                source_phrase="黒い",
                strength="required",
                attribute_key="色",
            ),
        ),
    )
    references = (proxy_image("desired"), proxy_image("counterfactual"))
    reference_set = build_counterfactual_reference_set(
        condition_set=conditions,
        desired_image_hash=ImagePerceptualHash(
            schema_version="2.0",
            image_pixel_sha256=references[0].pixel_sha256,
            value=0,
        ),
        counterfactual_image_hashes=(
            ImagePerceptualHash(
                schema_version="2.0",
                image_pixel_sha256=references[1].pixel_sha256,
                value=0xFF,
            ),
        ),
    )
    approved = ApprovedCounterfactualReferences(
        schema_version="5.0",
        owner_id=LOCAL_SEARCH_OWNER_ID,
        session_id=SESSION_ID,
        approval_basis="explicit_human_confirmation",
        human_confirmed=True,
        condition_set_sha256=reference_set.condition_set_sha256,
        cloudflare_reference_set_sha256="e" * 64,
        cloudflare_request_metadata_sha256="f" * 64,
        approval_receipt_sha256="1" * 64,
        reference_set=reference_set,
        reference_images=references,
    )
    return conditions, approved


class OutscraperTransport:
    def __init__(self) -> None:
        self.calls = 0

    def get(self, **_kwargs: object) -> OutscraperHttpResponse:
        self.calls += 1
        products = [
            {
                "name": f"黒いマウス {index}",
                "asin": f"B000PS{index:04d}",
                "image_1": f"https://m.media-amazon.com/images/product-{index}.png",
            }
            for index in range(1, 5)
        ]
        body = json.dumps(
            {"id": "fixture-task", "status": "Success", "data": products},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        return OutscraperHttpResponse(
            status_code=200,
            content_type="application/json; charset=utf-8",
            content_length=len(body),
            content_encoding="identity",
            body_chunks=(body,),
        )


class FailingOutscraperTransport:
    def __init__(self) -> None:
        self.calls = 0

    def get(self, **_kwargs: object):
        self.calls += 1
        raise RuntimeError("sensitive fixture provider detail")


class ProxyService:
    def __init__(self, images: dict[str, ProxyImage]) -> None:
        self.images = images
        self.calls = 0

    def fetch_image(self, url: str) -> ProxyImage:
        self.calls += 1
        return self.images[url]


class ClipEncoder:
    def encode_images(self, **_kwargs: object):
        raise AssertionError("the pinned CLIP adapter is replaced by the offline fixture")


def test_production_service_rejects_a_quota_enforced_usage_ledger(tmp_path: Path) -> None:
    asset_root = tmp_path / "clip-assets"
    asset_root.mkdir()
    jobs = SqliteSearchJobRepository(tmp_path / "jobs.sqlite3")

    with LocalSearchJobExecutor(jobs, clock=lambda: NOW) as executor:
        with pytest.raises(ProductionSearchError, match="inputs are invalid"):
            ProvisionalProductionSearchService(
                executor=executor,
                history_repository=SqliteProvisionalHistoryRepository(tmp_path / "history.sqlite3"),
                usage_ledger=enforced_usage_ledger(),
                approval_ledger=InMemoryApprovalLedger(),
                load_outscraper_api_key=lambda: SecretStr("fixture-key"),
                outscraper_transport=OutscraperTransport(),
                proxy_service=ProxyService({}),
                clip_asset_root=asset_root,
                clip_encoder=ClipEncoder(),
                now=lambda: NOW,
                sleep=lambda _seconds: None,
            )


def vector(first: float, second: float) -> tuple[float, ...]:
    magnitude = math.sqrt(first * first + second * second)
    values = [first / magnitude, second / magnitude]
    values.extend([0.0] * (CLIP_EMBEDDING_DIMENSION - len(values)))
    return tuple(values)


def test_job_binding_rejects_reference_approval_from_another_session() -> None:
    ledger = usage_ledger()
    approved = approved_search(ledger)
    conditions, references = approved_references()
    command = ProductionSearchCommand(
        source_text=SOURCE,
        approved_search=approved,
        condition_set=conditions,
        approved_references=references.model_copy(update={"session_id": "other-session"}),
    )

    with pytest.raises(ProductionSearchError, match="inputs are invalid"):
        production_search_job_binding_sha256(command)


def test_offline_approved_search_job_runs_once_and_saves_reopenable_history(
    monkeypatch,
    tmp_path: Path,
) -> None:
    ledger = usage_ledger()
    approved = approved_search(ledger)
    conditions, references = approved_references()
    candidates = [proxy_image(f"candidate-{index}") for index in range(1, 5)]
    urls = [f"https://m.media-amazon.com/images/product-{index}.png" for index in range(1, 5)]
    proxy = ProxyService(dict(zip(urls, candidates, strict=True)))
    vectors = {
        references.reference_images[0].pixel_sha256: vector(1.0, 0.0),
        references.reference_images[1].pixel_sha256: vector(0.0, 1.0),
        candidates[0].pixel_sha256: vector(0.0, 1.0),
        candidates[1].pixel_sha256: vector(0.2, 0.98),
        candidates[2].pixel_sha256: vector(0.98, 0.2),
        candidates[3].pixel_sha256: vector(1.0, 0.0),
    }

    import src.search_v2.counterfactual_product_evaluator as evaluator

    def run_clip(images, *, asset_root, encoder):
        del asset_root, encoder
        return tuple(
            ClipEmbedding(
                schema_version="2.0",
                image_pixel_sha256=image.pixel_sha256,
                runtime_sha256=clip_runtime_profile_sha256(),
                values=vectors[image.pixel_sha256],
            )
            for image in images
        )

    monkeypatch.setattr(evaluator, "run_pinned_clip_image_encoder", run_clip)
    transport = OutscraperTransport()
    history = SqliteProvisionalHistoryRepository(tmp_path / "history.sqlite3")
    jobs = SqliteSearchJobRepository(tmp_path / "jobs.sqlite3")
    command = ProductionSearchCommand(
        source_text=SOURCE,
        approved_search=approved,
        condition_set=conditions,
        approved_references=references,
    )
    asset_root = tmp_path / "clip-assets"
    asset_root.mkdir()

    with LocalSearchJobExecutor(jobs, clock=lambda: NOW) as executor:
        service = ProvisionalProductionSearchService(
            executor=executor,
            history_repository=history,
            usage_ledger=ledger,
            approval_ledger=InMemoryApprovalLedger(),
            load_outscraper_api_key=lambda: SecretStr("fixture-key"),
            outscraper_transport=transport,
            proxy_service=proxy,
            clip_asset_root=asset_root,
            clip_encoder=ClipEncoder(),
            now=lambda: NOW,
            sleep=lambda _seconds: None,
        )
        first = service.submit(command)
        duplicate = service.submit(command)
        executor.wait_until_idle()
        completed = service.get(first.locator)

    assert duplicate.locator == first.locator
    assert transport.calls == 1
    assert proxy.calls == 4
    assert completed.status == "succeeded"
    assert completed.result_locator is not None

    reopened = SqliteProvisionalHistoryRepository(tmp_path / "history.sqlite3")
    detail = reopened.get(
        owner_id=LOCAL_SEARCH_OWNER_ID,
        locator=completed.result_locator,
        now=NOW,
    )
    assert detail.summary == SOURCE
    assert len(detail.products) == 4
    assert all(item.image_component_status == "available" for item in detail.products)
    assert SOURCE not in jobs.path.read_bytes().decode("utf-8", errors="ignore")


def test_failed_product_task_is_not_saved_or_automatically_reexecuted(tmp_path: Path) -> None:
    ledger = usage_ledger()
    approved = approved_search(ledger)
    conditions, references = approved_references()
    command = ProductionSearchCommand(
        source_text=SOURCE,
        approved_search=approved,
        condition_set=conditions,
        approved_references=references,
    )
    asset_root = tmp_path / "clip-assets"
    asset_root.mkdir()
    transport = FailingOutscraperTransport()
    history = SqliteProvisionalHistoryRepository(tmp_path / "history.sqlite3")
    jobs = SqliteSearchJobRepository(tmp_path / "jobs.sqlite3")

    with LocalSearchJobExecutor(jobs, clock=lambda: NOW) as executor:
        service = ProvisionalProductionSearchService(
            executor=executor,
            history_repository=history,
            usage_ledger=ledger,
            approval_ledger=InMemoryApprovalLedger(),
            load_outscraper_api_key=lambda: SecretStr("fixture-key"),
            outscraper_transport=transport,
            proxy_service=ProxyService({}),
            clip_asset_root=asset_root,
            clip_encoder=ClipEncoder(),
            now=lambda: NOW,
            sleep=lambda _seconds: None,
        )
        first = service.submit(command)
        executor.wait_until_idle()
        failed = service.get(first.locator)
        duplicate = service.submit(command)
        executor.wait_until_idle()

    assert failed.status == "failed"
    assert failed.failure_code == "execution_failed"
    assert duplicate.locator == first.locator
    assert transport.calls == 1
    assert history.list(owner_id=LOCAL_SEARCH_OWNER_ID, now=NOW) == ()
