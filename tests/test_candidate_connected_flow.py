"""Candidate-owned approval, image evaluation and real temporary history storage."""

from datetime import timedelta
import importlib
import json
from io import BytesIO
import sqlite3

from PIL import Image
import pytest

import test_candidate_search as candidate
import test_candidate_visual_conditions as visual
import test_search_v2_production_search as production
from src.search_v2.provisional_approval_repository import SqliteCounterfactualApprovalRepository
from src.search_v2.provisional_history_repository import SqliteProvisionalHistoryRepository
from tools.bonsai_response_log import write_private


OWNER = "candidate-owner"


def start(root, named=True, condition_count=1, image_score_mode="appearance", **flow_options):
    module = importlib.import_module("src.search_v2.candidate_flow")
    phrases = ["丸みのある形", "高級感のある見た目", "なめらかな質感"][:condition_count]
    source = (
        "スキャナー。"
        + "。".join(phrases)
        + "。"
        + ("光学解像度" if named else "")
        + "600dpi以上。10000円以下。"
    )
    clock = [candidate.flow.NOW]

    class Images(candidate.flow.CloudflareTransport):
        def post_multipart(self, **kwargs):
            index = len(self.calls) + 1
            write_private(
                root / f"image-request-{index}.json", kwargs["request"].model_dump_json().encode()
            )
            response = super().post_multipart(**kwargs)
            write_private(root / f"image-response-{index}.json", b"".join(response.body_chunks))
            return response

    images = Images(candidate.flow.cloudflare_responses() * 4)
    ledger = candidate.flow.usage_ledger()
    approvals = SqliteCounterfactualApprovalRepository(root / "approvals.sqlite3")
    history = SqliteProvisionalHistoryRepository(root / "history.sqlite3")
    flow = module.CandidateSearchFlow(
        source,
        owner_id=OWNER,
        session_id="connected-candidate",
        postal_code="100-0001",
        policy=candidate.flow.backend_policy(),
        usage_ledger=ledger,
        approval_repository=approvals,
        history_repository=history,
        image_transport=images,
        account_id=candidate.flow.ACCOUNT_ID,
        api_token=candidate.flow.CLOUDFLARE_TOKEN,
        now=lambda: clock[0],
        image_score_mode=image_score_mode,
        visual_extractor=visual.VisualBonsai(root, [visual.draft(phrase) for phrase in phrases]),
        **flow_options,
    )
    return flow, images, ledger, history, clock


def reference(flow):
    return flow.generate_reference(
        owner_id=OWNER, plan_sha256=flow.plan_sha256, human_confirmed=True
    )


def approve(flow):
    review = reference(flow)
    issued = flow.approve_reference(
        owner_id=OWNER, reference_sha256=review.sha256, human_confirmed=True
    )
    flow.approve_images(
        owner_id=OWNER,
        approval_id=issued.review.approval_id,
        token=issued.token,
        human_confirmed=True,
    )
    return issued


def fetch(flow, root, named=True):
    products = candidate.scanner_products() + [
        {"asin": "B000CA0004", "name": "スキャナーD", "features": ["光学解像度: 1200dpi"]}
    ]
    for index, product in enumerate(products, 1):
        product.update(
            price=8000, currency="JPY", image_1=f"https://m.media-amazon.com/images/{index}.png"
        )
    transport = candidate.ProductTransport(products, root)
    review = flow.approve_and_fetch(
        owner_id=OWNER, plan_sha256=flow.plan_sha256, transport=transport
    )
    selections = (
        {}
        if named
        else {"condition-001": next(o.option_id for o in review.options if o.label == "光学解像度")}
    )
    flow.confirm(owner_id=OWNER, review_sha256=review.sha256, selections=selections)
    return transport


def clip(monkeypatch, root, uniform=False, failure=False):
    candidates = [production.proxy_image(f"connected-{i}") for i in range(4)]
    proxy = production.ProxyService(
        {
            f"https://m.media-amazon.com/images/{i + 1}.png": image
            for i, image in enumerate(candidates)
        }
    )
    vectors = [(1.0, 0.0)] * 4 if uniform else [(1.0, 0.0), (0.0, 1.0), (0.8, 0.6), (0.6, 0.8)]
    mapping = {
        p.pixel_sha256: production.vector(*v) for p, v in zip(candidates, vectors, strict=True)
    }
    calls = []

    def encode(images, *, asset_root, encoder):
        calls.append(len(images))
        if failure:
            raise RuntimeError("fixture-clip-failure")
        values = tuple(
            production.ClipEmbedding(
                schema_version="2.0",
                image_pixel_sha256=image.pixel_sha256,
                runtime_sha256=production.clip_runtime_profile_sha256(),
                values=mapping.get(
                    image.pixel_sha256,
                    production.vector(1.0, 0.0) if index == 0 else production.vector(0.0, 1.0),
                ),
            )
            for index, image in enumerate(images)
        )
        write_private(
            root / f"clip-response-{len(calls)}.json",
            json.dumps([v.model_dump(mode="json") for v in values]).encode(),
        )
        return values

    monkeypatch.setattr(
        "src.search_v2.counterfactual_product_evaluator.run_pinned_clip_image_encoder", encode
    )
    return dict(proxy_service=proxy, asset_root=root, encoder=production.ClipEncoder()), calls


@pytest.mark.parametrize("named", [False, True])
@pytest.mark.parametrize("uniform", [False, True])
def test_candidate_input_to_images_ranking_and_history(tmp_path, monkeypatch, named, uniform):
    flow, images, ledger, history, _ = start(tmp_path, named)
    approve(flow)
    products = fetch(flow, tmp_path, named)
    kwargs, calls = clip(monkeypatch, tmp_path, uniform)
    result = flow.complete(owner_id=OWNER, **kwargs)
    assert len(images.calls) == 2 and len(products.calls) == 1
    assert calls == [2, 4]
    assert sorted(
        (r.operation, r.amount.calls, r.status) for r in ledger.snapshot().reservations
    ) == [
        ("counterfactual_images", 1, "succeeded"),
        ("reference_image", 1, "succeeded"),
    ]
    reopened = SqliteProvisionalHistoryRepository(history.path)
    detail = reopened.get(owner_id=OWNER, locator=result.history.locator, now=candidate.flow.NOW)
    assert detail == result.history
    assert detail.product_name == "スキャナー"
    listed = reopened.list(owner_id=OWNER, now=candidate.flow.NOW)
    assert len(listed) == 1 and listed[0].locator == detail.locator
    assert listed[0].known_holdout_accuracy is None
    assert listed[0].product_name == "スキャナー"
    assert detail.known_holdout_accuracy is None
    assert detail.ranking_profile_id == "candidate-appearance-v1"
    assert detail.sort_profile_id == "excluded-title-conditions-image-review-v1"
    if uniform:
        assert [p.required_status for p in detail.products] == [
            "confirmed",
            "confirmed",
            "contradicted",
            "uncertain",
        ]
        assert [p.title for p in detail.products] == [
            "スキャナーB",
            "スキャナーD",
            "スキャナーA",
            "スキャナーC",
        ]
        assert all(
            p.image_score == 1.0 and p.image_component_status == "available"
            for p in detail.products
        )
        assert [p.total_score for p in detail.products] == [1.0, 1.0, 1.0, 1.0]
    else:
        assert [p.required_status for p in detail.products] == [
            "confirmed",
            "confirmed",
            "contradicted",
            "uncertain",
        ]
        assert [p.title for p in detail.products] == [
            "スキャナーD",
            "スキャナーB",
            "スキャナーA",
            "スキャナーC",
        ]
        assert [p.image_score for p in detail.products] == pytest.approx([0.4, 0.0, 1.0, 0.6])
        assert [p.total_score for p in detail.products] == pytest.approx([0.7, 0.5, 1.0, 0.8])
    assert result.ranking.source.visual_evaluation_status == "pending"
    assert result.ranking.visual_evaluation_status == "evaluated"
    assert (
        type(result.ranking).model_validate_json(result.ranking.model_dump_json()) == result.ranking
    )
    for saved, artifact in zip(detail.reference_images, flow.reference_images, strict=True):
        stored = reopened.get_image(
            owner_id=OWNER, image_locator=saved.locator, now=candidate.flow.NOW
        )
        with Image.open(BytesIO(stored.body)) as image:
            assert image.convert("RGB").tobytes() == artifact.rgb_bytes
        write_private(tmp_path / f"history-{saved.target}.png", stored.body)
    write_private(tmp_path / "history.json", detail.model_dump_json().encode())
    write_private(tmp_path / "ranking.json", result.ranking.model_dump_json().encode())
    with pytest.raises(ValueError):
        flow.complete(owner_id=OWNER, **kwargs)
    assert calls == [2, 4]


def test_history_retry_does_not_repeat_providers(tmp_path, monkeypatch):
    flow, images, _, history, _ = start(tmp_path)
    approve(flow)
    products = fetch(flow, tmp_path)
    kwargs, calls = clip(monkeypatch, tmp_path)
    save = history.save
    attempts = []

    def uncertain_save(*args, **kwargs):
        detail = save(*args, **kwargs)
        attempts.append(detail.locator)
        if len(attempts) == 1:
            raise RuntimeError("fixture acknowledgment lost after commit")
        return detail

    monkeypatch.setattr(history, "save", uncertain_save)
    with pytest.raises(ValueError, match="Candidate history save failed"):
        flow.complete(owner_id=OWNER, **kwargs)
    with pytest.raises(ValueError):
        flow.retry_history(owner_id="another")
    result = flow.retry_history(owner_id=OWNER)
    assert attempts == [result.history.locator, result.history.locator]
    assert len(images.calls) == 2 and len(products.calls) == 1 and calls == [2, 4]


@pytest.mark.parametrize("phase", ["reference", "derived"])
def test_generation_failure_preserves_failed_usage(tmp_path, monkeypatch, phase):
    flow, images, ledger, history, _ = start(tmp_path)
    if phase == "derived":
        review = reference(flow)

    def fail(**kwargs):
        raise RuntimeError("fixture-provider-failure")

    monkeypatch.setattr(images, "post_multipart", fail)
    with pytest.raises(ValueError):
        if phase == "reference":
            reference(flow)
        else:
            flow.approve_reference(
                owner_id=OWNER, reference_sha256=review.sha256, human_confirmed=True
            )
    failed = [r for r in ledger.snapshot().reservations if r.status == "failed"]
    assert len(failed) == 1 and failed[0].amount.calls == 1
    with pytest.raises(ValueError):
        flow.approve_and_fetch(owner_id=OWNER, plan_sha256=flow.plan_sha256, transport=object())
    with sqlite3.connect(history.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM provisional_history").fetchone()[0] == 0


def test_final_approval_is_single_use_and_checks_bindings(tmp_path):
    flow, images, _, _, _ = start(tmp_path)
    ref = reference(flow)
    issued = flow.approve_reference(
        owner_id=OWNER, reference_sha256=ref.sha256, human_confirmed=True
    )
    for owner, approval_id, token, confirmed in [
        ("another", issued.review.approval_id, issued.token, True),
        (OWNER, "wrong", issued.token, True),
        (OWNER, issued.review.approval_id, "wrong", True),
        (OWNER, issued.review.approval_id, issued.token, False),
    ]:
        with pytest.raises(ValueError):
            flow.approve_images(
                owner_id=owner, approval_id=approval_id, token=token, human_confirmed=confirmed
            )
    flow.approve_images(
        owner_id=OWNER,
        approval_id=issued.review.approval_id,
        token=issued.token,
        human_confirmed=True,
    )
    with pytest.raises(ValueError):
        flow.approve_images(
            owner_id=OWNER,
            approval_id=issued.review.approval_id,
            token=issued.token,
            human_confirmed=True,
        )
    assert len(images.calls) == 2


@pytest.mark.parametrize("action", ["fetch", "complete", "approve_images"])
def test_later_steps_require_own_image_approvals(tmp_path, action):
    flow, images, _, _, _ = start(tmp_path)
    with pytest.raises(ValueError):
        if action == "fetch":
            flow.approve_and_fetch(owner_id=OWNER, plan_sha256=flow.plan_sha256, transport=object())
        elif action == "complete":
            flow.complete(
                owner_id=OWNER, proxy_service=object(), asset_root=tmp_path, encoder=object()
            )
        else:
            flow.approve_images(
                owner_id=OWNER, approval_id="unknown", token="unknown", human_confirmed=True
            )
    assert not images.calls


@pytest.mark.parametrize("change", ["owner", "digest", "denied", "expired"])
def test_reference_approval_rejects_invalid_binding(tmp_path, change):
    flow, images, _, _, clock = start(tmp_path)
    review = reference(flow)
    if change == "expired":
        clock[0] += timedelta(minutes=16)
    with pytest.raises(ValueError):
        flow.approve_reference(
            owner_id="another" if change == "owner" else OWNER,
            reference_sha256="0" * 64 if change == "digest" else review.sha256,
            human_confirmed=change != "denied",
        )
    assert len(images.calls) == 1


def test_regeneration_invalidates_old_approval(tmp_path):
    flow, images, _, _, _ = start(tmp_path)
    old = reference(flow)
    issued = flow.approve_reference(
        owner_id=OWNER, reference_sha256=old.sha256, human_confirmed=True
    )
    new = flow.regenerate_reference(
        owner_id=OWNER, plan_sha256=flow.plan_sha256, human_confirmed=True
    )
    assert new.sha256 != old.sha256
    with pytest.raises(ValueError):
        flow.approve_reference(owner_id=OWNER, reference_sha256=old.sha256, human_confirmed=True)
    with pytest.raises(ValueError):
        flow.approve_images(
            owner_id=OWNER,
            approval_id=issued.review.approval_id,
            token=issued.token,
            human_confirmed=True,
        )
    assert len(images.calls) == 3


def test_unselected_quantity_and_clip_failure_do_not_save_history(tmp_path, monkeypatch):
    flow, _, _, history, _ = start(tmp_path, False)
    approve(flow)
    kwargs, calls = clip(monkeypatch, tmp_path, failure=True)
    with pytest.raises(ValueError):
        flow.complete(owner_id=OWNER, **kwargs)
    assert not calls
    fetch(flow, tmp_path, False)
    with pytest.raises(ValueError, match="Candidate completion failed"):
        flow.complete(owner_id=OWNER, **kwargs)
    assert calls == [2]
    with sqlite3.connect(history.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM provisional_history").fetchone()[0] == 0


@pytest.mark.parametrize("condition_count", [2, 3])
def test_reference_approval_generates_only_condition_count(tmp_path, condition_count):
    flow, images, ledger, _, _ = start(tmp_path, condition_count=condition_count)
    ref = reference(flow)
    assert len(images.calls) == 1
    issued = flow.approve_reference(
        owner_id=OWNER, reference_sha256=ref.sha256, human_confirmed=True
    )
    assert len(images.calls) == 1 + condition_count
    assert issued.review.call_count == 1 + condition_count
    flow.approve_images(
        owner_id=OWNER,
        approval_id=issued.review.approval_id,
        token=issued.token,
        human_confirmed=True,
    )
    assert len(flow.reference_images) == 1 + condition_count
    derived = next(
        r for r in ledger.snapshot().reservations if r.operation == "counterfactual_images"
    )
    assert derived.amount.calls == condition_count


def test_reference_is_single_use_under_concurrent_confirmation(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    flow, images, _, _, _ = start(tmp_path)
    ref = reference(flow)

    def attempt():
        try:
            flow.approve_reference(
                owner_id=OWNER, reference_sha256=ref.sha256, human_confirmed=True
            )
            return "accepted"
        except ValueError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(outcomes) == ["accepted", "rejected"]
    assert len(images.calls) == 2


def test_quantity_requires_selection_after_fetch(tmp_path, monkeypatch):
    flow, _, _, _, _ = start(tmp_path, False)
    approve(flow)
    transport = candidate.ProductTransport(candidate.scanner_products(), tmp_path)
    review = flow.approve_and_fetch(
        owner_id=OWNER, plan_sha256=flow.plan_sha256, transport=transport
    )
    with pytest.raises(ValueError):
        flow.confirm(owner_id=OWNER, review_sha256=review.sha256, selections={})
    kwargs, calls = clip(monkeypatch, tmp_path)
    with pytest.raises(ValueError):
        flow.complete(owner_id=OWNER, **kwargs)
    assert not calls
    with pytest.raises(ValueError):
        flow.regenerate_reference(
            owner_id=OWNER, plan_sha256=flow.plan_sha256, human_confirmed=True
        )


def test_regeneration_has_bounded_attempts(tmp_path):
    flow, images, _, _, _ = start(tmp_path)
    reference(flow)
    for _ in range(2):
        flow.regenerate_reference(
            owner_id=OWNER, plan_sha256=flow.plan_sha256, human_confirmed=True
        )
    with pytest.raises(ValueError):
        flow.regenerate_reference(
            owner_id=OWNER, plan_sha256=flow.plan_sha256, human_confirmed=True
        )
    assert len(images.calls) == 3


@pytest.mark.parametrize("change", ["owner", "digest", "denied"])
def test_initial_generation_requires_plan_confirmation(tmp_path, change):
    flow, images, ledger, _, _ = start(tmp_path)
    with pytest.raises(ValueError):
        flow.generate_reference(
            owner_id="another" if change == "owner" else OWNER,
            plan_sha256="0" * 64 if change == "digest" else flow.plan_sha256,
            human_confirmed=change != "denied",
        )
    assert not images.calls and not ledger.snapshot().reservations


@pytest.mark.parametrize(
    "profile,accuracy",
    [
        ("candidate-semantic-clip-v1", 0.875),
        ("candidate-lexical-clip-v2", 0.875),
        ("typed-ranking-v5-counterfactual-provisional", None),
        ("unknown-profile", None),
    ],
)
def test_history_rejects_quality_claim_from_other_profile(profile, accuracy):
    from test_search_v2_provisional_history_repository import pending
    from src.search_v2.provisional_history_repository import ProvisionalHistoryWrite

    value = pending().model_copy(
        update={"ranking_profile_id": profile, "known_holdout_accuracy": accuracy}
    )
    with pytest.raises(ValueError):
        ProvisionalHistoryWrite.model_validate(value)
