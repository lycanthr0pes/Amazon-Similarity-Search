"""Characterize complete supported paths without inventing a candidate-to-history bridge."""

from datetime import timedelta
import json

import pytest

import test_candidate_search as candidate
import test_candidate_visual_conditions as visual
import test_search_v2_provisional_production_flow as existing
from test_search_v2_counterfactual_cloudflare_request import png_bytes
from src.search_v2.candidate_queries import build_candidate_queries
from src.search_v2.candidate_search import CandidateRanking, prepare_candidate_search
from src.search_v2.counterfactual_cloudflare_request import (
    build_counterfactual_cloudflare_desired_request,
    build_counterfactual_cloudflare_request_set,
)
from tools.bonsai_response_log import write_private


def save(root, name, value):
    if hasattr(value, "model_dump_json"):
        body = value.model_dump_json().encode()
    else:
        body = json.dumps(value, ensure_ascii=False, indent=2).encode()
    write_private(root / name, body)


def run_candidate_flow(tmp_path, named):
    source = (
        "スキャナー。丸みのある形。高級感のある見た目を希望。"
        + ("光学解像度" if named else "")
        + "600dpi以上。10000円以下。"
    )
    trace = []
    visual_bonsai = visual.VisualBonsai(
        tmp_path,
        [visual.draft("丸みのある形"), visual.draft("高級感のある見た目を希望", "preferred")],
    )
    service = prepare_candidate_search(
        source,
        owner_id="owner-1",
        session_id="offline-flow-1",
        postal_code="100-0001",
        normalization_profile=candidate.flow.backend_policy().normalization_profile,
        now=candidate.flow.NOW,
        visual_extractor=visual_bonsai,
    )
    trace.append("visual_bonsai_fixture")
    plan = service.plan
    save(tmp_path, "source.json", {"source": source, "synthetic": True})
    save(tmp_path, "retrieval-plan.json", plan)
    assert len(visual_bonsai.calls) == 1
    assert len(plan.visual_conditions.conditions) == 2
    assert plan.pending_quotes == (() if named else ("600dpi以上",))
    assert "600dpi" not in plan.image_prompt
    assert "10000" not in plan.image_prompt
    query = build_candidate_queries(source, visual_conditions=plan.visual_conditions)
    assert query.query_plan == plan.query_plan
    trace.append("sudachi_query_and_prompt")

    desired = build_counterfactual_cloudflare_desired_request(
        intent=query.retrieval_intent,
        condition_set=plan.visual_conditions,
        preimage_plan_sha256=service.plan_sha256,
    )
    save(tmp_path, "reference-request.json", desired)
    assert desired.target == "desired" and desired.reference_image is None
    # This PNG is a test input to a pure builder, not a generated/approved image.
    supplied_png = png_bytes()
    write_private(tmp_path / "synthetic-reference.png", supplied_png)
    requests = build_counterfactual_cloudflare_request_set(
        intent=query.retrieval_intent,
        condition_set=plan.visual_conditions,
        preimage_plan_sha256=service.plan_sha256,
        desired_reference_png=supplied_png,
    )
    save(tmp_path, "image-request-set.json", requests)
    assert requests.call_count == 3
    assert [r.target for r in requests.requests] == ["desired", "counterfactual", "counterfactual"]
    assert [r.condition_id for r in requests.requests[1:]] == [
        c.condition_id for c in plan.visual_conditions.conditions
    ]
    trace.append("image_descriptors_only")

    products = candidate.scanner_products() + [
        {
            "asin": "B000CA0004",
            "name": "スキャナーD",
            "features": ["光学解像度: 1200dpi"],
        }
    ]
    for product, price in zip(products, [8000, 9000, 7000, 9500], strict=True):
        product.update(price=price, currency="JPY")
    product_transport = candidate.ProductTransport(products, tmp_path)
    with pytest.raises(ValueError):
        service.approve_and_fetch(
            owner_id="owner-1",
            plan_sha256="0" * 64,
            transport=product_transport,
            now=candidate.flow.NOW,
        )
    assert not product_transport.calls
    trace.append("unconfirmed_plan_rejected")
    review = service.approve_and_fetch(
        owner_id="owner-1",
        plan_sha256=service.plan_sha256,
        transport=product_transport,
        now=candidate.flow.NOW + timedelta(seconds=1),
    )
    trace.append("approved_candidate_fetch_fixture")
    save(tmp_path, "attribute-review.json", review)
    with pytest.raises(ValueError):
        service.rank(owner_id="owner-1", now=candidate.flow.NOW)
    if not named:
        with pytest.raises(ValueError):
            service.confirm(
                owner_id="owner-1",
                review_sha256=review.sha256,
                selections={},
                now=candidate.flow.NOW,
            )
    selected = (
        {}
        if named
        else {"condition-001": next(o.option_id for o in review.options if o.label == "光学解像度")}
    )
    receipt = service.confirm(
        owner_id="owner-1",
        review_sha256=review.sha256,
        selections=selected,
        now=candidate.flow.NOW + timedelta(seconds=2),
    )
    save(
        tmp_path,
        "attribute-selection.json",
        {"selections": selected, "confirmation_sha256": receipt},
    )
    trace.append("attribute_confirmation")
    ranked = service.rank(owner_id="owner-1", now=candidate.flow.NOW + timedelta(seconds=3))
    trace.append("lexical_and_numeric_ranking")
    save(tmp_path, "ranking.json", ranked)
    assert [p.product.asin for p in ranked.products] == [
        "B000CA0002",
        "B000CA0004",
        "B000CA0003",
        "B000CA0001",
    ]
    assert [p.evaluation.required_status for p in ranked.products] == [
        "confirmed",
        "confirmed",
        "uncertain",
        "contradicted",
    ]
    assert [p.lexical_score for p in ranked.products] == [1.0, 1.0, 1.0, 1.0]
    assert len(product_transport.calls) == 1
    assert ranked.visual_evaluation_status == "pending"
    exported = json.loads((tmp_path / "ranking.json").read_bytes())
    assert exported == ranked.model_dump(mode="json")
    assert exported["confirmation_sha256"] == receipt
    trace.append("json_export_readback_not_history_db")
    for action in (
        lambda: service.rank(owner_id="owner-1", now=candidate.flow.NOW),
        lambda: service.approve_and_fetch(
            owner_id="owner-1",
            plan_sha256=service.plan_sha256,
            transport=product_transport,
            now=candidate.flow.NOW,
        ),
    ):
        with pytest.raises(ValueError):
            action()
    assert len(product_transport.calls) == 1
    save(
        tmp_path,
        "flow-verdict.json",
        {
            "trace": trace,
            "supported_candidate_path": "passed",
            "complete_image_clip_history_path": "not_connected",
            "domain_json_restore": "checked_by_separate_roundtrip_test",
            "visual_evaluation_status": ranked.visual_evaluation_status,
            "actual_provider_calls": 0,
            "actual_clip_calls": 0,
        },
    )

    return ranked


@pytest.mark.parametrize(
    "named", [False, True], ids=["quantity-needs-selection", "explicit-attribute"]
)
def test_candidate_natural_input_to_ranked_output(tmp_path, named):
    run_candidate_flow(tmp_path, named)


@pytest.mark.parametrize(
    "named", [False, True], ids=["quantity-needs-selection", "explicit-attribute"]
)
def test_candidate_domain_result_can_be_restored(tmp_path, named):
    ranked = run_candidate_flow(tmp_path, named)
    restored = CandidateRanking.model_validate_json((tmp_path / "ranking.json").read_bytes())
    assert restored == ranked


@pytest.mark.parametrize("diverse", [False, True], ids=["uniform", "diverse"])
def test_existing_image_clip_and_history_path_separately(monkeypatch, tmp_path, diverse):
    """Reuse the shipped flow test; record only synthetic bodies, never headers/keys."""
    counts = {}

    def record(kind, body, suffix="json"):
        counts[kind] = counts.get(kind, 0) + 1
        write_private(tmp_path / f"{kind}-{counts[kind]:03}.{suffix}", body)

    bonsai_post = existing.production.BonsaiTransport.post_json
    image_post = existing.CloudflareTransport.post_multipart
    products_get = existing.production.OutscraperTransport.get
    history_get = existing.production.SqliteProvisionalHistoryRepository.get
    history_image = existing.production.SqliteProvisionalHistoryRepository.get_image

    def bonsai(self, **kwargs):
        record("bonsai-request", kwargs["body"])
        response = bonsai_post(self, **kwargs)
        record("bonsai-response", b"".join(response.body_chunks))
        return response

    def images(self, **kwargs):
        record("image-request", kwargs["request"].model_dump_json().encode())
        response = image_post(self, **kwargs)
        record("image-response", b"".join(response.body_chunks))
        return response

    def products(self, **kwargs):
        response = products_get(self, **kwargs)
        record("product-response", b"".join(response.body_chunks))
        return response

    def history(self, **kwargs):
        result = history_get(self, **kwargs)
        record("history-response", result.model_dump_json().encode())
        return result

    def history_png(self, **kwargs):
        result = history_image(self, **kwargs)
        record("history-image-response", result.body, "png")
        return result

    monkeypatch.setattr(existing.production.BonsaiTransport, "post_json", bonsai)
    monkeypatch.setattr(existing.CloudflareTransport, "post_multipart", images)
    monkeypatch.setattr(existing.production.OutscraperTransport, "get", products)
    monkeypatch.setattr(existing.production.SqliteProvisionalHistoryRepository, "get", history)
    monkeypatch.setattr(
        existing.production.SqliteProvisionalHistoryRepository, "get_image", history_png
    )

    class ClipRecordingPatch:
        def setattr(self, target, name, function):
            assert name == "run_pinned_clip_image_encoder"

            def encoded(*args, **kwargs):
                result = function(*args, **kwargs)
                record(
                    "clip-fixture-response",
                    json.dumps([v.model_dump(mode="json") for v in result]).encode(),
                )
                return result

            monkeypatch.setattr(target, name, encoded)

    existing.test_staged_generation_reaches_product_job_and_reopenable_history(
        ClipRecordingPatch(), tmp_path, diverse
    )
    assert counts["bonsai-response"] == 1
    assert counts["image-response"] == 2
    assert counts["product-response"] == 1
    assert counts["clip-fixture-response"] >= 1
    assert counts["history-response"] >= 1
    assert counts["history-image-response"] == 2
    save(
        tmp_path,
        "flow-verdict.json",
        {
            "existing_staged_image_clip_history_path": "passed",
            "candidate_path_connected": False,
            "clip_fixture": "diverse" if diverse else "uniform",
            "actual_provider_calls": 0,
            "actual_clip_calls": 0,
            "recorded_responses": counts,
        },
    )
