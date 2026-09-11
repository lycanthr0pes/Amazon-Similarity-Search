from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from datetime import timezone
from pathlib import Path

import pytest

import src.search_v2.counterfactual_product_evaluator as evaluator
import src.search_v2.provisional_search_pipeline as provisional_pipeline
from src.search_v2.counterfactual_product_evaluator import CounterfactualProductEvaluationError
from src.search_v2.counterfactual_image import VisualConditionDraft
from src.search_v2.counterfactual_image import build_counterfactual_reference_set
from src.search_v2.counterfactual_image import build_visual_condition_set
from src.search_v2.image_proxy import ProxyImage
from src.search_v2.image_proxy import proxy_image_pixel_sha256
from src.search_v2.image_similarity import CLIP_EMBEDDING_DIMENSION
from src.search_v2.image_similarity import ClipEmbedding
from src.search_v2.image_similarity import ImagePerceptualHash
from src.search_v2.image_similarity import clip_runtime_profile_sha256
from src.search_v2.outscraper_request import build_outscraper_request
from src.search_v2.outscraper_http import OutscraperProductExecution
from src.search_v2.product_normalization import ProductNormalizationProfile
from src.search_v2.product_normalization import ProductNormalizationError
from src.search_v2.product_normalization import normalize_outscraper_products
from src.search_v2.counterfactual_reference_approval import ApprovedCounterfactualReferences
from src.search_v2.provisional_backend import complete_provisional_product_ranking
from src.search_v2.provisional_backend import ProvisionalBackendError
from src.search_v2.provisional_search_pipeline import ProvisionalSearchPipelineError
from src.search_v2.provisional_search_pipeline import run_provisional_search
from src.search_v2.provisional_history_repository import SqliteProvisionalHistoryRepository
from src.search_v2.provisional_history_snapshot import build_provisional_history_snapshot
from src.search_v2.query_planner import build_search_query_plan
from src.search_v2.query_planner import SearchQueryPlan
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_ranking import rank_typed_product_batch
from src.search_v2.typed_ranking import TypedRankingError
from src.search_v2.usage_ledger import UsageAmount
from src.search_v2.usage_ledger import UsageReservation
from src.search_v2.usage_ledger import UsageReservationRequest


def proxy_image(tag: str) -> ProxyImage:
    rgb = hashlib.sha256(tag.encode()).digest()[:3] * 4
    return ProxyImage(
        schema_version="2.0",
        source_url_sha256=hashlib.sha256(f"url-{tag}".encode()).hexdigest(),
        source_bytes_sha256=hashlib.sha256(f"bytes-{tag}".encode()).hexdigest(),
        pixel_sha256=proxy_image_pixel_sha256(2, 2, rgb),
        content_type="image/png",
        image_format="PNG",
        width=2,
        height=2,
        rgb_bytes=rgb,
    )


def unit_vector(x: float, y: float, z: float = 0.0) -> tuple[float, ...]:
    norm = math.sqrt(x * x + y * y + z * z)
    values = [x / norm, y / norm, z / norm]
    values.extend([0.0] * (CLIP_EMBEDDING_DIMENSION - len(values)))
    return tuple(values)


def mouse_intent():
    source = "黒いマウスを探す"
    draft = SearchIntentDraft.model_validate(
        {
            "product_name_ja": "マウス",
            "product_name_en": "mouse",
            "category_ja": None,
            "category_en": None,
            "required_terms_ja": [],
            "required_terms_en": [],
            "preferred_terms_ja": [],
            "preferred_terms_en": [],
            "negative_terms_ja": [],
            "negative_terms_en": [],
            "color_ja": "黒",
            "color_en": "black",
            "features_ja": [],
            "features_en": [],
            "brand": None,
            "model_number": None,
            "price": {
                "currency": "JPY",
                "mode": "none",
                "target_jpy": None,
                "min_jpy": None,
                "max_jpy": None,
                "source": "none",
                "confidence": None,
            },
            "typed_conditions": [],
            "ambiguities": [],
        }
    )
    provenance = build_intent_provenance(
        source_input=source,
        prompt=b"prompt",
        schema=b"schema",
        response=b"response",
    )
    return normalize_search_intent(source, draft, provenance=provenance)


def one_query_plan(intent):
    full_plan = build_search_query_plan(intent)
    return SearchQueryPlan(
        schema_version="2.0",
        intent_sha256=full_plan.intent_sha256,
        queries=full_plan.queries[:1],
    )


def inputs(product_count: int = 5):
    source = "黒いマウスを探す"
    intent = mouse_intent()
    plan = one_query_plan(intent)
    request = build_outscraper_request(plan, postal_code="100-0001")
    products = [
        {
            "name": f"マウス{index}",
            "asin": f"B000EV{index:04d}",
            "image_1": f"https://images.example.test/product-{index}.png",
            "image_2": f"https://images.example.test/ignored-{index}.png",
        }
        for index in range(1, product_count + 1)
    ]
    batch = normalize_outscraper_products(
        {"data": products if len(plan.queries) == 1 else [products, []]},
        request=request,
        provider_request_id="task_counterfactual_evaluator",
        profile=ProductNormalizationProfile(
            schema_version="2.0",
            profile_id="observed-only-v2",
            usd_to_jpy_rate=160,
        ),
    )
    conditions = build_visual_condition_set(
        source_input=source,
        drafts=(
            VisualConditionDraft(
                source_phrase="黒い",
                strength="required",
                attribute_key="色",
            ),
        ),
    )
    references = (proxy_image("desired"), proxy_image("negative"))
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
    source_ranking = rank_typed_product_batch(
        intent,
        plan,
        batch,
        build_typed_requirement_proposal(intent),
    )
    return batch, conditions, reference_set, references, source_ranking


class FakeProxyService:
    def __init__(self, images: dict[str, ProxyImage], *, fail_suffix: str | None = None) -> None:
        self.images = images
        self.fail_suffix = fail_suffix
        self.urls: list[str] = []

    def fetch_image(self, url: str) -> ProxyImage:
        self.urls.append(url)
        if self.fail_suffix is not None and url.endswith(self.fail_suffix):
            raise RuntimeError("sensitive upstream detail")
        return self.images[url]


def fake_clip(monkeypatch, vectors: dict[str, tuple[float, ...]]):
    batch_sizes: list[int] = []

    def run(images, *, asset_root, encoder):
        del asset_root, encoder
        batch_sizes.append(len(images))
        return tuple(
            ClipEmbedding(
                schema_version="2.0",
                image_pixel_sha256=image.pixel_sha256,
                runtime_sha256=clip_runtime_profile_sha256(),
                values=vectors[image.pixel_sha256],
            )
            for image in images
        )

    monkeypatch.setattr(evaluator, "run_pinned_clip_image_encoder", run)
    return batch_sizes


def pipeline_arguments(product_count: int = 4) -> dict[str, object]:
    batch, conditions, reference_set, references, _source_ranking = inputs(
        product_count=product_count
    )
    intent = mouse_intent()
    plan = one_query_plan(intent)
    request = build_outscraper_request(plan, postal_code="100-0001")
    raw_products = [
        {
            "name": product.title,
            "asin": product.asin,
            "image_1": product.image_urls[0],
        }
        for product in sorted(batch.products, key=lambda item: item.provenance.response_index)
    ]
    finished_at = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    usage_request = UsageReservationRequest(
        provider="outscraper",
        operation="product_search",
        owner_id="owner-1",
        session_id="session-1",
        binding_sha256="d" * 64,
        amount=UsageAmount(calls=1, tokens=0, cost_microusd=0),
        pricing_policy_sha256="e" * 64,
    )
    execution = OutscraperProductExecution(
        request=request,
        provider_request_id="safe-task-id",
        response={"data": raw_products},
        polls_performed=3,
        usage_reservation=UsageReservation(
            reservation_id="r" * 32,
            request=usage_request,
            usage_policy_sha256="f" * 64,
            status="succeeded",
            reserved_at=finished_at,
            started_at=finished_at,
            finished_at=finished_at,
        ),
    )
    candidates = [proxy_image(f"pipeline-argument-{index}") for index in range(product_count)]
    service = FakeProxyService(
        {
            product.image_urls[0]: image
            for product, image in zip(batch.products, candidates, strict=True)
        }
    )
    approved = ApprovedCounterfactualReferences(
        schema_version="5.0",
        owner_id="owner-1",
        session_id="session-1",
        approval_basis="explicit_human_confirmation",
        human_confirmed=True,
        condition_set_sha256=reference_set.condition_set_sha256,
        cloudflare_reference_set_sha256="a" * 64,
        cloudflare_request_metadata_sha256="b" * 64,
        approval_receipt_sha256="c" * 64,
        reference_set=reference_set,
        reference_images=references,
    )
    return {
        "execution": execution,
        "intent": intent,
        "query_plan": plan,
        "typed_proposal": build_typed_requirement_proposal(intent),
        "normalization_profile": ProductNormalizationProfile(
            schema_version="2.0",
            profile_id="observed-only-v2",
            usd_to_jpy_rate=160,
        ),
        "condition_set": conditions,
        "approved_references": approved,
        "proxy_service": service,
        "asset_root": Path("unused-in-fake"),
        "encoder": object(),
    }


def test_evaluator_fetches_only_the_first_product_image_and_batches_clip(monkeypatch) -> None:
    batch, conditions, reference_set, references, _source_ranking = inputs()
    candidates = [proxy_image(f"candidate-{index}") for index in range(1, 6)]
    urls = {
        product.image_urls[0]: image
        for product, image in zip(batch.products, candidates, strict=True)
    }
    service = FakeProxyService(urls)
    vectors = {
        references[0].pixel_sha256: unit_vector(1.0, 0.0),
        references[1].pixel_sha256: unit_vector(0.0, 1.0),
        candidates[0].pixel_sha256: unit_vector(0.0, 1.0),
        candidates[1].pixel_sha256: unit_vector(0.0, 0.5, math.sqrt(0.75)),
        candidates[2].pixel_sha256: unit_vector(0.5, 0.0, math.sqrt(0.75)),
        candidates[3].pixel_sha256: unit_vector(1.0, 0.0),
        candidates[4].pixel_sha256: unit_vector(0.8, 0.0, 0.6),
    }
    batch_sizes = fake_clip(monkeypatch, vectors)

    result = evaluator.evaluate_counterfactual_product_images(
        product_batch=batch,
        condition_set=conditions,
        reference_set=reference_set,
        reference_images=references,
        proxy_service=service,
        asset_root=Path("unused-in-fake"),
        encoder=object(),
    )

    assert result.status == "ready"
    assert batch_sizes == [2, 4, 1]
    assert service.urls == [product.image_urls[0] for product in batch.products]
    assert all("ignored" not in url for url in service.urls)
    assert tuple(item.image_score for item in result.candidates[:4]) == pytest.approx(
        (0.0, 0.25, 0.75, 1.0)
    )


def test_proxy_failure_stays_missing_without_leaking_url_or_error(monkeypatch) -> None:
    batch, conditions, reference_set, references, _source_ranking = inputs()
    candidates = [proxy_image(f"candidate-{index}") for index in range(1, 6)]
    service = FakeProxyService(
        {
            product.image_urls[0]: image
            for product, image in zip(batch.products, candidates, strict=True)
        },
        fail_suffix="product-5.png",
    )
    vectors = {
        references[0].pixel_sha256: unit_vector(1.0, 0.0),
        references[1].pixel_sha256: unit_vector(0.0, 1.0),
        candidates[0].pixel_sha256: unit_vector(0.0, 1.0),
        candidates[1].pixel_sha256: unit_vector(0.0, 0.5, math.sqrt(0.75)),
        candidates[2].pixel_sha256: unit_vector(0.5, 0.0, math.sqrt(0.75)),
        candidates[3].pixel_sha256: unit_vector(1.0, 0.0),
    }
    fake_clip(monkeypatch, vectors)

    result = evaluator.evaluate_counterfactual_product_images(
        product_batch=batch,
        condition_set=conditions,
        reference_set=reference_set,
        reference_images=references,
        proxy_service=service,
        asset_root=Path("unused-in-fake"),
        encoder=object(),
    )

    assert result.status == "ready"
    assert result.candidates[-1].status == "missing"
    serialized = result.model_dump_json()
    assert "images.example.test" not in serialized
    assert "sensitive upstream detail" not in serialized


def test_fewer_than_four_scored_candidates_fails_closed(monkeypatch) -> None:
    batch, conditions, reference_set, references, source_ranking = inputs(product_count=4)
    candidates = [proxy_image(f"candidate-{index}") for index in range(1, 5)]
    service = FakeProxyService(
        {
            product.image_urls[0]: image
            for product, image in zip(batch.products, candidates, strict=True)
        },
        fail_suffix="product-4.png",
    )
    vectors = {
        references[0].pixel_sha256: unit_vector(1.0, 0.0),
        references[1].pixel_sha256: unit_vector(0.0, 1.0),
        candidates[0].pixel_sha256: unit_vector(0.0, 1.0),
        candidates[1].pixel_sha256: unit_vector(0.5, 0.0, math.sqrt(0.75)),
        candidates[2].pixel_sha256: unit_vector(1.0, 0.0),
    }
    fake_clip(monkeypatch, vectors)

    result = evaluator.evaluate_counterfactual_product_images(
        product_batch=batch,
        condition_set=conditions,
        reference_set=reference_set,
        reference_images=references,
        proxy_service=service,
        asset_root=Path("unused-in-fake"),
        encoder=object(),
    )

    assert result.status == "unknown"
    assert result.ranking_enabled is False
    assert all(item.image_score is None for item in result.candidates)


def test_reference_clip_failure_reports_only_safe_substage_counts(monkeypatch) -> None:
    batch, conditions, reference_set, references, _source_ranking = inputs(product_count=4)
    service = FakeProxyService({})

    def fail_reference_clip(*_args, **_kwargs):
        raise RuntimeError("sensitive reference runtime detail")

    monkeypatch.setattr(evaluator, "run_pinned_clip_image_encoder", fail_reference_clip)

    with pytest.raises(CounterfactualProductEvaluationError) as captured:
        evaluator.evaluate_counterfactual_product_images(
            product_batch=batch,
            condition_set=conditions,
            reference_set=reference_set,
            reference_images=references,
            proxy_service=service,
            asset_root=Path("unused-in-fake"),
            encoder=object(),
        )

    assert captured.value.safe_metadata() == {
        "candidate_clip_batch_count": 0,
        "failure_substage": "reference_clip",
        "image_fetch_success_count": 0,
        "image_request_count": 0,
        "reference_clip_batch_count": 1,
    }
    assert "sensitive" not in json.dumps(captured.value.safe_metadata(), sort_keys=True)


def test_candidate_clip_failure_reports_completed_proxy_counts(monkeypatch) -> None:
    batch, conditions, reference_set, references, _source_ranking = inputs(product_count=4)
    candidates = [proxy_image(f"diagnostic-{index}") for index in range(1, 5)]
    service = FakeProxyService(
        {
            product.image_urls[0]: image
            for product, image in zip(batch.products, candidates, strict=True)
        }
    )
    calls = 0

    def fail_candidate_clip(images, *, asset_root, encoder):
        nonlocal calls
        del asset_root, encoder
        calls += 1
        if calls == 1:
            return tuple(
                ClipEmbedding(
                    schema_version="2.0",
                    image_pixel_sha256=image.pixel_sha256,
                    runtime_sha256=clip_runtime_profile_sha256(),
                    values=unit_vector(1.0, 0.0),
                )
                for image in images
            )
        raise RuntimeError("sensitive candidate runtime detail")

    monkeypatch.setattr(evaluator, "run_pinned_clip_image_encoder", fail_candidate_clip)

    with pytest.raises(CounterfactualProductEvaluationError) as captured:
        evaluator.evaluate_counterfactual_product_images(
            product_batch=batch,
            condition_set=conditions,
            reference_set=reference_set,
            reference_images=references,
            proxy_service=service,
            asset_root=Path("unused-in-fake"),
            encoder=object(),
        )

    assert captured.value.safe_metadata() == {
        "candidate_clip_batch_count": 1,
        "failure_substage": "candidate_clip",
        "image_fetch_success_count": 4,
        "image_request_count": 4,
        "reference_clip_batch_count": 1,
    }
    serialized = json.dumps(captured.value.safe_metadata(), sort_keys=True)
    assert "sensitive" not in serialized
    assert "images.example.test" not in serialized


def test_calibration_failure_reports_prior_safe_counts(monkeypatch) -> None:
    batch, conditions, reference_set, references, _source_ranking = inputs(product_count=4)
    candidates = [proxy_image(f"calibration-{index}") for index in range(1, 5)]
    service = FakeProxyService(
        {
            product.image_urls[0]: image
            for product, image in zip(batch.products, candidates, strict=True)
        }
    )
    vectors = {
        image.pixel_sha256: unit_vector(1.0, index + 1.0)
        for index, image in enumerate((*references, *candidates))
    }
    fake_clip(monkeypatch, vectors)

    def fail_calibration(*_args, **_kwargs):
        raise ValueError("sensitive calibration detail")

    monkeypatch.setattr(
        evaluator,
        "build_provisional_counterfactual_batch",
        fail_calibration,
    )

    with pytest.raises(CounterfactualProductEvaluationError) as captured:
        evaluator.evaluate_counterfactual_product_images(
            product_batch=batch,
            condition_set=conditions,
            reference_set=reference_set,
            reference_images=references,
            proxy_service=service,
            asset_root=Path("unused-in-fake"),
            encoder=object(),
        )

    assert captured.value.safe_metadata() == {
        "candidate_clip_batch_count": 1,
        "failure_substage": "calibration",
        "image_fetch_success_count": 4,
        "image_request_count": 4,
        "reference_clip_batch_count": 1,
    }
    assert "sensitive" not in json.dumps(captured.value.safe_metadata(), sort_keys=True)


def test_pipeline_reports_product_normalization_substage(monkeypatch) -> None:
    arguments = pipeline_arguments()

    def fail_normalization(*_args, **_kwargs):
        raise ProductNormalizationError("sensitive product body")

    monkeypatch.setattr(
        provisional_pipeline,
        "normalize_outscraper_products",
        fail_normalization,
    )

    with pytest.raises(ProvisionalSearchPipelineError) as captured:
        run_provisional_search(**arguments)

    diagnostic = captured.value.safe_metadata()
    assert diagnostic["failure_substage"] == "product_normalization"
    assert diagnostic["received_candidate_count"] is None
    assert "sensitive" not in json.dumps(diagnostic, sort_keys=True)


def test_pipeline_reports_typed_ranking_substage_with_product_counts(monkeypatch) -> None:
    arguments = pipeline_arguments()

    def fail_typed_ranking(*_args, **_kwargs):
        raise TypedRankingError("sensitive title")

    monkeypatch.setattr(
        provisional_pipeline,
        "rank_typed_product_batch",
        fail_typed_ranking,
    )

    with pytest.raises(ProvisionalSearchPipelineError) as captured:
        run_provisional_search(**arguments)

    diagnostic = captured.value.safe_metadata()
    assert diagnostic["failure_substage"] == "typed_ranking"
    assert diagnostic["received_candidate_count"] == 4
    assert diagnostic["normalized_product_count"] == 4
    assert diagnostic["rejected_candidate_count"] == 0
    assert diagnostic["products_with_image_url"] == 4
    assert "sensitive" not in json.dumps(diagnostic, sort_keys=True)


def test_pipeline_preserves_backend_substage_and_safe_counts(monkeypatch) -> None:
    arguments = pipeline_arguments()

    def fail_backend(*_args, **_kwargs):
        raise ProvisionalBackendError(
            "Inputs did not match the provisional backend contract",
            failure_substage="candidate_clip",
            image_request_count=4,
            image_fetch_success_count=3,
            reference_clip_batch_count=1,
            candidate_clip_batch_count=1,
        )

    monkeypatch.setattr(
        provisional_pipeline,
        "complete_provisional_product_ranking",
        fail_backend,
    )

    with pytest.raises(ProvisionalSearchPipelineError) as captured:
        run_provisional_search(**arguments)

    assert captured.value.safe_metadata() == {
        "candidate_clip_batch_count": 1,
        "failure_substage": "candidate_clip",
        "image_fetch_success_count": 3,
        "image_request_count": 4,
        "normalized_product_count": 4,
        "products_with_image_url": 4,
        "received_candidate_count": 4,
        "reference_clip_batch_count": 1,
        "rejected_candidate_count": 0,
    }


def test_provisional_backend_connects_approved_references_to_v5_ranking(
    monkeypatch,
    tmp_path,
) -> None:
    batch, conditions, reference_set, references, source_ranking = inputs(product_count=4)
    candidates = [proxy_image(f"candidate-{index}") for index in range(1, 5)]
    service = FakeProxyService(
        {
            product.image_urls[0]: image
            for product, image in zip(batch.products, candidates, strict=True)
        }
    )
    vectors = {
        references[0].pixel_sha256: unit_vector(1.0, 0.0),
        references[1].pixel_sha256: unit_vector(0.0, 1.0),
        candidates[0].pixel_sha256: unit_vector(0.0, 1.0),
        candidates[1].pixel_sha256: unit_vector(0.0, 0.5, math.sqrt(0.75)),
        candidates[2].pixel_sha256: unit_vector(0.5, 0.0, math.sqrt(0.75)),
        candidates[3].pixel_sha256: unit_vector(1.0, 0.0),
    }
    fake_clip(monkeypatch, vectors)
    approved = ApprovedCounterfactualReferences(
        schema_version="5.0",
        owner_id="owner-1",
        session_id="session-1",
        approval_basis="explicit_human_confirmation",
        human_confirmed=True,
        condition_set_sha256=reference_set.condition_set_sha256,
        cloudflare_reference_set_sha256="a" * 64,
        cloudflare_request_metadata_sha256="b" * 64,
        approval_receipt_sha256="c" * 64,
        reference_set=reference_set,
        reference_images=references,
    )

    result = complete_provisional_product_ranking(
        source_typed_ranking=source_ranking,
        product_batch=batch,
        condition_set=conditions,
        approved_references=approved,
        proxy_service=service,
        asset_root=Path("unused-in-fake"),
        encoder=object(),
    )

    assert result.schema_version == "5.0"
    assert result.ranking_profile_id == "typed-ranking-v5-counterfactual-provisional"
    assert all(item.breakdown.image.status == "available" for item in result.products)

    pending = build_provisional_history_snapshot(
        owner_id="owner-1",
        source_text="黒いマウスを探す",
        completed_at=datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc),
        condition_set=conditions,
        approved_references=approved,
        ranked_batch=result,
    )
    repository = SqliteProvisionalHistoryRepository(tmp_path / "history-v5.sqlite3")
    detail = repository.save(pending, now=pending.completed_at)

    assert detail.ranking_profile_id == "typed-ranking-v5-counterfactual-provisional"
    assert detail.known_holdout_accuracy == 0.875
    assert all(item.image_component_status == "available" for item in detail.products)
    assert "images.example.test" not in detail.model_dump_json()


@pytest.mark.parametrize(
    (
        "duplicate_images",
        "reservation_status",
        "expected_outcome",
        "available_count",
        "missing_count",
        "unknown_count",
    ),
    (
        (False, "succeeded", "image_ready", 4, 0, 0),
        (True, "succeeded", "image_unknown", 0, 3, 1),
        (False, "failed", None, 0, 0, 0),
    ),
)
def test_provisional_search_connects_outscraper_products_and_fails_closed(
    monkeypatch,
    duplicate_images,
    reservation_status,
    expected_outcome,
    available_count,
    missing_count,
    unknown_count,
) -> None:
    batch, conditions, reference_set, references, _source_ranking = inputs(product_count=4)
    intent = mouse_intent()
    plan = one_query_plan(intent)
    request = build_outscraper_request(plan, postal_code="100-0001")
    raw_products = [
        {
            "name": product.title,
            "asin": product.asin,
            "image_1": product.image_urls[0],
            "image_2": product.image_urls[1],
        }
        for product in sorted(batch.products, key=lambda item: item.provenance.response_index)
    ]
    usage_request = UsageReservationRequest(
        provider="outscraper",
        operation="product_search",
        owner_id="owner-1",
        session_id="session-1",
        binding_sha256="d" * 64,
        amount=UsageAmount(calls=1, tokens=0, cost_microusd=10_000),
        pricing_policy_sha256="e" * 64,
    )
    finished_at = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    execution = OutscraperProductExecution(
        request=request,
        provider_request_id="task_counterfactual_evaluator",
        response={"data": raw_products if len(plan.queries) == 1 else [raw_products, []]},
        polls_performed=3,
        usage_reservation=UsageReservation(
            reservation_id="r" * 32,
            request=usage_request,
            usage_policy_sha256="f" * 64,
            status=reservation_status,
            reserved_at=finished_at,
            started_at=finished_at,
            finished_at=finished_at,
        ),
    )
    candidates = (
        [proxy_image("pipeline-duplicate")] * 4
        if duplicate_images
        else [proxy_image(f"pipeline-candidate-{index}") for index in range(1, 5)]
    )
    service = FakeProxyService(
        {
            product.image_urls[0]: image
            for product, image in zip(batch.products, candidates, strict=True)
        }
    )
    vectors = {
        references[0].pixel_sha256: unit_vector(1.0, 0.0),
        references[1].pixel_sha256: unit_vector(0.0, 1.0),
        candidates[0].pixel_sha256: unit_vector(0.0, 1.0),
        candidates[1].pixel_sha256: unit_vector(0.0, 0.5, math.sqrt(0.75)),
        candidates[2].pixel_sha256: unit_vector(0.5, 0.0, math.sqrt(0.75)),
        candidates[3].pixel_sha256: unit_vector(1.0, 0.0),
    }
    fake_clip(monkeypatch, vectors)
    approved = ApprovedCounterfactualReferences(
        schema_version="5.0",
        owner_id="owner-1",
        session_id="session-1",
        approval_basis="explicit_human_confirmation",
        human_confirmed=True,
        condition_set_sha256=reference_set.condition_set_sha256,
        cloudflare_reference_set_sha256="a" * 64,
        cloudflare_request_metadata_sha256="b" * 64,
        approval_receipt_sha256="c" * 64,
        reference_set=reference_set,
        reference_images=references,
    )

    arguments = {
        "execution": execution,
        "intent": intent,
        "query_plan": plan,
        "typed_proposal": build_typed_requirement_proposal(intent),
        "normalization_profile": ProductNormalizationProfile(
            schema_version="2.0",
            profile_id="observed-only-v2",
            usd_to_jpy_rate=160,
        ),
        "condition_set": conditions,
        "approved_references": approved,
        "proxy_service": service,
        "asset_root": Path("unused-in-fake"),
        "encoder": object(),
    }
    if reservation_status == "failed":
        with pytest.raises(
            ProvisionalSearchPipelineError,
            match="Provisional search pipeline inputs are invalid",
        ):
            run_provisional_search(**arguments)
        assert service.urls == []
        return

    result = run_provisional_search(**arguments)

    assert result.ranked_batch.schema_version == "5.0"
    assert result.safe_metadata() == {
        "image_available_count": available_count,
        "image_missing_count": missing_count,
        "image_request_count": 4,
        "image_unknown_count": unknown_count,
        "normalized_product_count": 4,
        "outcome": expected_outcome,
        "polls_performed": 3,
        "products_with_image_url": 4,
        "received_candidate_count": 4,
        "rejected_candidate_count": 0,
        "retry_count": 0,
        "task_count": 1,
    }
    serialized = json.dumps(result.safe_metadata(), sort_keys=True)
    assert "images.example.test" not in serialized
    assert "task_counterfactual_evaluator" not in serialized


def test_provisional_search_reports_all_missing_images_as_unavailable(monkeypatch) -> None:
    arguments = pipeline_arguments()
    arguments["proxy_service"] = FakeProxyService({}, fail_suffix=".png")
    desired = proxy_image("desired")
    negative = proxy_image("negative")
    fake_clip(
        monkeypatch,
        {
            desired.pixel_sha256: unit_vector(1.0, 0.0),
            negative.pixel_sha256: unit_vector(0.0, 1.0),
        },
    )

    result = run_provisional_search(**arguments)

    assert result.safe_metadata() == {
        "image_available_count": 0,
        "image_missing_count": 4,
        "image_request_count": 4,
        "image_unknown_count": 0,
        "normalized_product_count": 4,
        "outcome": "image_unavailable",
        "polls_performed": 3,
        "products_with_image_url": 4,
        "received_candidate_count": 4,
        "rejected_candidate_count": 0,
        "retry_count": 0,
        "task_count": 1,
    }
