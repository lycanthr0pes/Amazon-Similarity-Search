"""Interactive backend E2E through the production orchestration and search job."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import hmac
from io import BytesIO
import json
import os
from pathlib import Path
import stat
import threading
from typing import Callable

from PIL import Image

from src.search_v2.counterfactual_cloudflare_http import RequestsCounterfactualCloudflareTransport
from src.search_v2.counterfactual_cloudflare_request import CounterfactualCloudflareRequest
from src.search_v2.counterfactual_image import VisualConditionDraft
from src.search_v2.counterfactual_image import build_visual_condition_set
from src.search_v2.orchestrator import BonsaiIntentConfig
from src.search_v2.orchestrator import IntentReview
from src.search_v2.orchestrator import ProviderAttemptBudget
from src.search_v2.orchestrator import SearchBackendPolicy
from src.search_v2.orchestrator import accept_images
from src.search_v2.orchestrator import approve_search
from src.search_v2.orchestrator import start_intent_review
from src.search_v2.product_normalization import ProductNormalizationProfile
from src.search_v2.production_search import ProductionSearchCommand
from src.search_v2.production_search import ProvisionalProductionSearchService
from src.search_v2.provisional_approval_repository import SqliteCounterfactualApprovalRepository
from src.search_v2.provisional_history_repository import SqliteProvisionalHistoryRepository
from src.search_v2.provisional_orchestrator import approve_provisional_reference_review
from src.search_v2.provisional_orchestrator import generate_provisional_images
from src.search_v2.provisional_orchestrator import generate_provisional_reference_review
from src.search_v2.search_job import LOCAL_SEARCH_OWNER_ID
from src.search_v2.search_job import LocalSearchJobExecutor
from src.search_v2.search_job import SqliteSearchJobRepository
from src.search_v2.state_machine import InMemoryApprovalLedger
from src.search_v2.typed_ranking import TYPED_RANKING_PROFILE_V4
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import UsageAmount
from src.search_v2.usage_ledger import build_no_quota_usage_policies
from tools import provisional_search_live_e2e as saved_files
from tools import bonsai_live_e2e as bonsai_runtime


SYNTHETIC_INPUT = "白い陶器製マグカップ"
REFERENCE_CONFIRMATION = "この参考画像を了承して偽画像を生成する"
SEARCH_CONFIRMATION = "生成画像と検索クエリを確認し商品検索を承認する"
_MAX_IMAGE_CALLS = 2
_MAX_PRODUCT_IMAGES = 24
_MAX_POLLS = 50
_MAX_CLIP_BATCHES = 7


class BackendSearchE2EError(RuntimeError):
    def __init__(self, stage: str) -> None:
        super().__init__("Backend search E2E failed")
        self.stage = stage
        self.counts = {}

    def safe_metadata(self):
        return {"status": "failed", "failure_stage": self.stage, "retry_count": 0, **self.counts}


class RequestsBackendImageTransport:
    def post_multipart(self, **kwargs):
        request = kwargs.get("request")
        if type(request) is CounterfactualCloudflareRequest:
            return RequestsCounterfactualCloudflareTransport().post_multipart(**kwargs)
        raise BackendSearchE2EError("image_request_type")


@contextmanager
def owned_bonsai(config):
    process = bonsai_runtime._launch_server(config)
    expired = threading.Event()

    def expire():
        expired.set()
        try:
            process.terminate()
        except OSError:
            pass  # The ordinary cleanup below verifies process and port termination.

    deadline = threading.Timer(900, expire)
    deadline.daemon = True
    deadline.start()
    try:
        bonsai_runtime._wait_until_ready(process, config.port)
        yield bonsai_runtime.RequestsBonsaiTransport()
        if expired.is_set():
            raise BackendSearchE2EError("bonsai_deadline")
    finally:
        deadline.cancel()
        deadline.join()
        bonsai_runtime._stop_server(process, config.port)


@dataclass(frozen=True, slots=True)
class BackendE2EConfig:
    output_dir: Path
    asset_root: Path
    bonsai_port: int = 18080


@dataclass(frozen=True, slots=True, repr=False)
class BackendE2EServices:
    bonsai_session: Callable
    load_cloudflare: Callable
    cloudflare_transport: object
    load_outscraper_api_key: Callable
    outscraper_transport: object
    proxy_service: object
    encoder: object
    now: Callable
    sleep: Callable
    confirm: Callable
    product_transport_factory: Callable | None = None


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _policy_and_ledger():
    digests = {
        name: _digest(f"backend-e2e-{name}-manual-no-money-cap-v1")
        for name in ("bonsai", "cloudflare", "outscraper")
    }
    ledger = InMemoryUsageLedger(
        build_no_quota_usage_policies(
            bonsai_pricing_policy_sha256=digests["bonsai"],
            cloudflare_pricing_policy_sha256=digests["cloudflare"],
            outscraper_pricing_policy_sha256=digests["outscraper"],
        )
    )
    policy = SearchBackendPolicy(
        schema_version="3.0",
        bonsai_intent=ProviderAttemptBudget(
            amount=UsageAmount(calls=1, tokens=2_000_000, cost_microusd=0),
            pricing_policy_sha256=digests["bonsai"],
        ),
        cloudflare_image_set=ProviderAttemptBudget(
            amount=UsageAmount(calls=4, tokens=0, cost_microusd=0),
            pricing_policy_sha256=digests["cloudflare"],
        ),
        outscraper_search=ProviderAttemptBudget(
            amount=UsageAmount(calls=1, tokens=0, cost_microusd=0),
            pricing_policy_sha256=digests["outscraper"],
        ),
        normalization_profile=ProductNormalizationProfile(
            schema_version="2.0",
            profile_id="observed-only-v2",
            usd_to_jpy_rate=160,
        ),
        ranking_profile=TYPED_RANKING_PROFILE_V4,
        implementation_sha256=_digest("backend-search-live-e2e-v1"),
    )
    return policy, ledger


class _CountedBonsai:
    def __init__(self):
        self.inner = None
        self.calls = 0

    def post_json(self, **kwargs):
        if self.calls >= 1 or self.inner is None:
            raise BackendSearchE2EError("bonsai_limit")
        self.calls += 1
        return self.inner.post_json(**kwargs)


class _CountedImages:
    def __init__(self, inner):
        self.inner = inner
        self.calls = 0

    def post_multipart(self, **kwargs):
        if self.calls >= _MAX_IMAGE_CALLS:
            raise BackendSearchE2EError("image_limit")
        self.calls += 1
        return self.inner.post_multipart(**kwargs)


class _CountedProducts:
    def __init__(self, inner):
        self.inner = inner
        self.tasks = 0
        self.polls = 0

    def get(self, **kwargs):
        if kwargs.get("params"):
            if self.tasks >= 1:
                raise BackendSearchE2EError("task_limit")
            self.tasks += 1
        else:
            if self.tasks != 1 or self.polls >= _MAX_POLLS:
                raise BackendSearchE2EError("poll_limit")
            self.polls += 1
        return self.inner.get(**kwargs)


class _CountedProxy:
    def __init__(self, inner):
        self.inner = inner
        self.calls = 0
        self.succeeded = 0

    def fetch_image(self, url):
        if self.calls >= _MAX_PRODUCT_IMAGES:
            raise BackendSearchE2EError("product_image_limit")
        self.calls += 1
        result = self.inner.fetch_image(url)
        self.succeeded += 1
        return result


class _CountedEncoder:
    def __init__(self, inner):
        self.inner = inner
        self.calls = 0
        self.text_calls = 0

    def encode_texts(self, **kwargs):
        if self.text_calls >= 1:
            raise BackendSearchE2EError("visual_text_limit")
        self.text_calls += 1
        return self.inner.encode_texts(**kwargs)

    def encode_images(self, **kwargs):
        if self.calls >= _MAX_CLIP_BATCHES:
            raise BackendSearchE2EError("clip_limit")
        self.calls += 1
        return self.inner.encode_images(**kwargs)


def _new_output(config):
    root = config.output_dir
    if (
        type(config) is not BackendE2EConfig
        or not root.is_absolute()
        or not config.asset_root.is_absolute()
        or not config.asset_root.is_dir()
        or not 1024 <= config.bonsai_port <= 65535
    ):
        raise BackendSearchE2EError("configuration")
    saved_files._validate_new_review_path(root)
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    return root.stat()


def _verify_images(root, identity, files):
    current = root.lstat()
    if (
        not stat.S_ISDIR(current.st_mode)
        or current.st_uid != os.getuid()
        or stat.S_IMODE(current.st_mode) != 0o700
        or (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino)
    ):
        raise BackendSearchE2EError("review_files")
    for item in files:
        body = saved_files._read_saved_reference(item)
        if not hmac.compare_digest(hashlib.sha256(body).hexdigest(), item.sha256):
            raise BackendSearchE2EError("review_files")


def _json_file(root, name, value):
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode()
    saved_files._write_file(root / name, body + b"\n")


def _confirmed(services, stage, queries, files):
    result = services.confirm(
        stage,
        {
            "queries": queries,
            "images": [str(item.path) for item in files],
            "maximum_candidates": _MAX_PRODUCT_IMAGES,
        },
    )
    if type(result) is not bool:
        raise BackendSearchE2EError("confirmation")
    return result


def _save_history_output(config, history, completed, references, now):
    before = history.get(owner_id=LOCAL_SEARCH_OWNER_ID, locator=completed.result_locator, now=now)
    reopened = SqliteProvisionalHistoryRepository(config.output_dir / "history.sqlite3")
    after = reopened.get(owner_id=LOCAL_SEARCH_OWNER_ID, locator=completed.result_locator, now=now)
    if before != after or not after.products:
        raise BackendSearchE2EError("history_reopen")
    for stored, expected in zip(after.reference_images, references.reference_images, strict=True):
        image = reopened.get_image(
            owner_id=LOCAL_SEARCH_OWNER_ID, image_locator=stored.locator, now=now
        )
        with Image.open(BytesIO(image.body)) as decoded:
            if decoded.convert("RGB").tobytes() != expected.rgb_bytes:
                raise BackendSearchE2EError("history_images")
    # The user's requested ranking output is the bounded display projection, not raw provider data.
    products = [
        product.model_dump(mode="json", exclude={"schema_version", "product_url"})
        for product in after.products
    ]
    _json_file(config.output_dir, "ranking.json", {"products": products})
    _json_file(
        config.output_dir,
        "history.json",
        {
            "schema_version": after.schema_version,
            "locator": after.locator,
            "completed_at": after.completed_at.isoformat(),
            "expires_at": after.expires_at.isoformat(),
            "products": products,
            "reference_images": [
                {
                    "target": image.target,
                    "condition_id": image.condition_id,
                    "width": image.width,
                    "height": image.height,
                }
                for image in after.reference_images
            ],
        },
    )
    return len(after.products), len(after.reference_images)


def run_backend_search_e2e(
    config: BackendE2EConfig, services: BackendE2EServices
) -> dict[str, object]:
    stage = "configuration"
    bonsai = _CountedBonsai()
    images = _CountedImages(services.cloudflare_transport)
    products = _CountedProducts(services.outscraper_transport)
    proxy = _CountedProxy(services.proxy_service)
    encoder = _CountedEncoder(services.encoder)
    cloudflare_failure = None

    def counts():
        return {
            "bonsai_calls": bonsai.calls,
            "cloudflare_calls": images.calls,
            "outscraper_tasks": products.tasks,
            "outscraper_polls": products.polls,
            "product_image_requests": proxy.calls,
            "product_image_successes": proxy.succeeded,
            "clip_batches": encoder.calls,
            **(
                {"cloudflare_failure": cloudflare_failure.model_dump()}
                if cloudflare_failure
                else {}
            ),
        }

    try:
        identity = _new_output(config)
        policy, ledger = _policy_and_ledger()
        stage = "bonsai"
        with services.bonsai_session() as transport:
            bonsai.inner = transport
            intent = start_intent_review(
                SYNTHETIC_INPUT,
                owner_id=LOCAL_SEARCH_OWNER_ID,
                session_id="backend-e2e-" + config.output_dir.name,
                bonsai_config=BonsaiIntentConfig(
                    base_url=f"http://127.0.0.1:{config.bonsai_port}/v1",
                    model_id="Bonsai-8B.gguf",
                    temperature=0.0,
                ),
                policy=policy,
                usage_ledger=ledger,
                transport=bonsai,
                now=services.now,
            )
        if not isinstance(intent, IntentReview) or len(intent.query_plan.queries) != 1:
            raise BackendSearchE2EError("intent_not_ready")
        queries = [query.value for query in intent.query_plan.queries]
        _json_file(config.output_dir, "query.json", {"queries": queries})
        conditions = build_visual_condition_set(
            source_input=SYNTHETIC_INPUT,
            drafts=(VisualConditionDraft(source_phrase="白い", strength="required"),),
        )
        stage = "reference_generation"
        cloudflare = services.load_cloudflare()
        reference = generate_provisional_reference_review(
            intent,
            source_input=SYNTHETIC_INPUT,
            condition_set=conditions,
            policy=policy,
            usage_ledger=ledger,
            account_id=cloudflare.cloudflare_account_id,
            api_token=cloudflare.cloudflare_api_token.get_secret_value(),
            transport=images,
            now=services.now,
        )
        if reference.status != "reference_review" or images.calls != 1:
            cloudflare_failure = reference.failure_diagnostic
            raise BackendSearchE2EError("reference_generation")
        preview = saved_files._write_file(config.output_dir / "preview.png", reference.image.body)
        stage = "reference_confirmation"
        if not _confirmed(services, "reference", queries, (preview,)):
            return {"status": "reference_declined", "cloudflare_calls": images.calls}
        _verify_images(config.output_dir, identity, (preview,))
        stage = "derived_generation"
        approvals = SqliteCounterfactualApprovalRepository(config.output_dir / "approvals.sqlite3")
        issued = generate_provisional_images(
            reference,
            human_confirmed=True,
            policy=policy,
            usage_ledger=ledger,
            approval_repository=approvals,
            account_id=cloudflare.cloudflare_account_id,
            api_token=cloudflare.cloudflare_api_token.get_secret_value(),
            transport=images,
            now=services.now,
        )
        del cloudflare
        if images.calls != _MAX_IMAGE_CALLS:
            raise BackendSearchE2EError("derived_generation")
        files = [preview]
        for image in issued.review.execution.images[1:]:
            files.append(
                saved_files._write_file(
                    config.output_dir / f"fake-{image.condition_id}.png", image.body
                )
            )
        stage = "search_confirmation"
        if not _confirmed(services, "search", queries, files):
            return {"status": "search_declined", "cloudflare_calls": images.calls}
        _verify_images(config.output_dir, identity, files)
        references = approve_provisional_reference_review(
            issued.review,
            approval_token=issued.approval_token,
            human_confirmed=True,
            approval_repository=approvals,
            now=services.now,
        )
        review = accept_images(
            issued.review.image_review,
            postal_code="100-0001",
            policy=policy,
            usage_ledger=ledger,
            now=services.now,
        )
        command = ProductionSearchCommand(
            source_text=SYNTHETIC_INPUT,
            approved_search=approve_search(review, now=services.now),
            condition_set=conditions,
            approved_references=references,
        )
        stage = "product_job"
        history = SqliteProvisionalHistoryRepository(config.output_dir / "history.sqlite3")
        jobs = SqliteSearchJobRepository(config.output_dir / "jobs.sqlite3")
        with LocalSearchJobExecutor(jobs, clock=services.now) as executor:
            service = ProvisionalProductionSearchService(
                executor=executor,
                history_repository=history,
                usage_ledger=ledger,
                approval_ledger=InMemoryApprovalLedger(),
                load_outscraper_api_key=services.load_outscraper_api_key,
                outscraper_transport=products,
                proxy_service=proxy,
                clip_asset_root=config.asset_root,
                clip_encoder=encoder,
                now=services.now,
                sleep=services.sleep,
            )
            job = service.submit(command)
            executor.wait_until_idle()
            completed = service.get(job.locator)
        if completed.status != "succeeded" or products.tasks != 1:
            raise BackendSearchE2EError("product_job")
        stage = "history_output"
        count, reference_count = _save_history_output(
            config, history, completed, references, services.now()
        )
        result = {
            "status": "succeeded",
            "bonsai_calls": 1,
            "cloudflare_calls": images.calls,
            "outscraper_tasks": products.tasks,
            "outscraper_polls": products.polls,
            "product_image_requests": proxy.calls,
            "product_image_successes": proxy.succeeded,
            "clip_batches": encoder.calls,
            "ranked_products": count,
            "history_reopened": True,
            "history_reference_images_verified": reference_count,
            "retry_count": 0,
        }
        _json_file(config.output_dir, "summary.json", result)
        return result
    except BackendSearchE2EError as error:
        error.counts = counts()
        raise error from None
    except Exception:
        error = BackendSearchE2EError(stage)
        error.counts = counts()
        raise error from None
