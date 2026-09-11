from __future__ import annotations

from dataclasses import replace
from io import BytesIO

from PIL import Image
import pytest

from src.search_v2.provisional_approval_repository import SqliteCounterfactualApprovalRepository
from src.search_v2.provisional_orchestrator import approve_provisional_reference_review
from src.search_v2.provisional_orchestrator import generate_provisional_images
from src.search_v2.provisional_orchestrator import generate_provisional_reference_review
from src.search_v2.orchestrator import accept_images
from test_search_v2_orchestrator import ACCOUNT_ID
from test_search_v2_orchestrator import CLOUDFLARE_TOKEN
from test_search_v2_orchestrator import CloudflareTransport
from test_search_v2_orchestrator import cloudflare_responses
import test_search_v2_production_search as production


SOURCE = production.SOURCE + " ＵＳＢ"


def generated_command(tmp_path):
    ledger = production.usage_ledger()
    policy = production.backend_policy()

    def clock():
        return production.NOW

    stage = production.start_intent_review(
        SOURCE,
        owner_id=production.LOCAL_SEARCH_OWNER_ID,
        session_id=production.SESSION_ID,
        bonsai_config=production.BonsaiIntentConfig(
            base_url="http://127.0.0.1:8080/v1",
            model_id="Bonsai-8B.gguf",
            temperature=0.1,
        ),
        policy=policy,
        usage_ledger=ledger,
        transport=production.BonsaiTransport(),
        now=clock,
    )
    conditions = production.build_visual_condition_set(
        source_input=SOURCE,
        drafts=(production.VisualConditionDraft(source_phrase="黒い", strength="required"),),
    )
    images = CloudflareTransport(cloudflare_responses() * 2)
    reference = generate_provisional_reference_review(
        stage,
        source_input=SOURCE,
        condition_set=conditions,
        policy=policy,
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=images,
        now=clock,
    )
    approvals = SqliteCounterfactualApprovalRepository(tmp_path / "references.sqlite3")
    issued = generate_provisional_images(
        reference,
        human_confirmed=True,
        policy=policy,
        usage_ledger=ledger,
        approval_repository=approvals,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=images,
        now=clock,
    )
    approved_references = approve_provisional_reference_review(
        issued.review,
        approval_token=issued.approval_token,
        human_confirmed=True,
        approval_repository=approvals,
        now=clock,
    )
    review = accept_images(
        issued.review.image_review,
        postal_code="100-0001",
        policy=policy,
        usage_ledger=ledger,
        now=clock,
    )
    command = production.ProductionSearchCommand(
        source_text=SOURCE,
        approved_search=production.approve_search(review, now=clock),
        condition_set=conditions,
        approved_references=approved_references,
    )
    return command, ledger, images


@pytest.mark.parametrize("diverse", [False, True], ids=["uniform", "diverse"])
def test_staged_generation_reaches_product_job_and_reopenable_history(
    monkeypatch, tmp_path, diverse
):
    command, ledger, images = generated_command(tmp_path)
    references = command.approved_references
    candidates = [production.proxy_image(f"candidate-{index}") for index in range(1, 5)]
    urls = [f"https://m.media-amazon.com/images/product-{index}.png" for index in range(1, 5)]
    proxy = production.ProxyService(dict(zip(urls, candidates, strict=True)))
    vectors = {
        references.reference_images[0].pixel_sha256: production.vector(1.0, 0.0),
        references.reference_images[1].pixel_sha256: production.vector(0.0, 1.0),
        **{candidate.pixel_sha256: production.vector(1.0, 0.0) for candidate in candidates},
    }
    if diverse:
        for candidate, coordinates in zip(
            candidates, [(0.0, 1.0), (0.6, 0.8), (0.8, 0.6), (1.0, 0.0)], strict=True
        ):
            vectors[candidate.pixel_sha256] = production.vector(*coordinates)
    import src.search_v2.counterfactual_product_evaluator as evaluator

    def run_clip(source_images, *, asset_root, encoder):
        del asset_root, encoder
        return tuple(
            production.ClipEmbedding(
                schema_version="2.0",
                image_pixel_sha256=image.pixel_sha256,
                runtime_sha256=production.clip_runtime_profile_sha256(),
                values=vectors[image.pixel_sha256],
            )
            for image in source_images
        )

    monkeypatch.setattr(evaluator, "run_pinned_clip_image_encoder", run_clip)
    products = production.OutscraperTransport()
    history = production.SqliteProvisionalHistoryRepository(tmp_path / "history.sqlite3")
    jobs = production.SqliteSearchJobRepository(tmp_path / "jobs.sqlite3")
    assets = tmp_path / "clip-assets"
    assets.mkdir()
    with production.LocalSearchJobExecutor(jobs, clock=lambda: production.NOW) as executor:
        service = production.ProvisionalProductionSearchService(
            executor=executor,
            history_repository=history,
            usage_ledger=ledger,
            approval_ledger=production.InMemoryApprovalLedger(),
            load_outscraper_api_key=lambda: production.SecretStr("fixture-key"),
            outscraper_transport=products,
            proxy_service=proxy,
            clip_asset_root=assets,
            clip_encoder=production.ClipEncoder(),
            now=lambda: production.NOW,
            sleep=lambda _seconds: None,
        )
        job = service.submit(command)
        duplicate = service.submit(command)
        executor.wait_until_idle()
        completed = service.get(job.locator)

    assert duplicate.locator == job.locator
    assert len(images.calls) == 2
    assert products.calls == 1
    assert completed.status == "succeeded"
    reopened = production.SqliteProvisionalHistoryRepository(history.path)
    detail = reopened.get(
        owner_id=production.LOCAL_SEARCH_OWNER_ID,
        locator=completed.result_locator,
        now=production.NOW,
    )
    assert len(detail.products) == 4
    if diverse:
        assert all(product.image_component_status == "available" for product in detail.products)
        scores_by_title = {product.title: product.image_score for product in detail.products}
        assert scores_by_title == pytest.approx(
            {f"黒いマウス {index}": score for index, score in enumerate([0.0, 0.4, 0.6, 1.0], 1)}
        )
        assert [product.image_score for product in detail.products] == pytest.approx(
            [1.0, 0.6, 0.4, 0.0]
        )
    else:
        assert all(product.image_component_status == "unknown" for product in detail.products)
        assert all(product.image_score is None for product in detail.products)
    assert tuple(image.target for image in detail.reference_images) == ("desired", "counterfactual")
    assert detail.condition_set_sha256 == references.condition_set_sha256
    assert len(detail.reference_images) == 2
    for stored, expected in zip(detail.reference_images, references.reference_images, strict=True):
        saved = reopened.get_image(
            owner_id=production.LOCAL_SEARCH_OWNER_ID,
            image_locator=stored.locator,
            now=production.NOW,
        )
        with Image.open(BytesIO(saved.body)) as decoded:
            assert decoded.convert("RGB").tobytes() == expected.rgb_bytes
    assert len(images.calls) == 2
    assert products.calls == 1


@pytest.mark.parametrize("change", ["artifact_digest", "request_digest", "equivalent_source"])
def test_new_product_job_rejects_unbound_reference_or_changed_raw_input(tmp_path, change):
    command, _, _ = generated_command(tmp_path)
    if change == "equivalent_source":
        command = replace(command, source_text=production.SOURCE + " USB")
    else:
        field = (
            "cloudflare_reference_set_sha256"
            if change == "artifact_digest"
            else "cloudflare_request_metadata_sha256"
        )
        command = replace(
            command,
            approved_references=command.approved_references.model_copy(update={field: "f" * 64}),
        )

    with pytest.raises(production.ProductionSearchError):
        production.production_search_job_binding_sha256(command)
