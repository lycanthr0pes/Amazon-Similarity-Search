from __future__ import annotations

import hashlib
from datetime import datetime
from datetime import timezone
from io import BytesIO

from PIL import Image
import pytest

from src.search_v2.cloudflare_http import _normalized_png
from src.search_v2.counterfactual_cloudflare_http import (
    CounterfactualCloudflareImageArtifact,
)
from src.search_v2.counterfactual_cloudflare_http import (
    counterfactual_cloudflare_reference_set_sha256,
)
from src.search_v2.counterfactual_cloudflare_request import (
    build_counterfactual_cloudflare_request_set,
)
from src.search_v2.counterfactual_cloudflare_request import (
    counterfactual_cloudflare_request_set_sha256,
)
from src.search_v2.counterfactual_cloudflare_request import (
    counterfactual_cloudflare_request_sha256,
)
from src.search_v2.counterfactual_image import VisualConditionDraft
from src.search_v2.counterfactual_image import build_visual_condition_set
from src.search_v2.counterfactual_reference_approval import (
    CounterfactualReferenceApprovalError,
)
from src.search_v2.counterfactual_reference_approval import (
    approve_counterfactual_reference_artifacts,
)
from src.search_v2.counterfactual_reference_approval import (
    approved_counterfactual_references_sha256,
)
from src.search_v2.provisional_approval_repository import (
    CounterfactualReferenceApprovalReceipt,
)
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent


def intent_and_conditions():
    source = "黒いヘッドレスト付きのオフィスチェア"
    draft = SearchIntentDraft.model_validate(
        {
            "product_name_ja": "オフィスチェア",
            "product_name_en": "office chair",
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
    intent = normalize_search_intent(source, draft, provenance=provenance)
    conditions = build_visual_condition_set(
        source_input=source,
        drafts=(
            VisualConditionDraft(
                source_phrase="黒い",
                strength="required",
                attribute_key="色",
            ),
            VisualConditionDraft(
                source_phrase="ヘッドレスト付き",
                strength="required",
                attribute_key=None,
            ),
        ),
    )
    return intent, conditions


def png(index: int, *, size: int = 512) -> bytes:
    output = BytesIO()
    image = Image.new("RGB", (size, size), (index, index * 2, index * 3))
    for x in range(index, size, max(2, index + 3)):
        image.putpixel((x, (x * (index + 1)) % size), (255, 255 - index, index))
    image.save(output, format="PNG")
    return _normalized_png(output.getvalue()) if size == 512 else output.getvalue()


def request_set_and_images():
    intent, conditions = intent_and_conditions()
    requests = build_counterfactual_cloudflare_request_set(
        intent=intent,
        condition_set=conditions,
        preimage_plan_sha256="a" * 64,
        desired_reference_png=png(10, size=10),
    )
    bodies = (png(10), png(40), png(90))
    images = tuple(
        CounterfactualCloudflareImageArtifact(
            schema_version="1.0",
            target=request.target,
            condition_id=request.condition_id,
            attempt=1,
            request_sha256=counterfactual_cloudflare_request_sha256(request),
            content_type="image/png",
            sha256=hashlib.sha256(body).hexdigest(),
            byte_length=len(body),
            width=512,
            height=512,
            body=body,
        )
        for request, body in zip(requests.requests, bodies, strict=True)
    )
    return conditions, requests, images


def approval_receipt(conditions, requests, images):
    return CounterfactualReferenceApprovalReceipt(
        schema_version="5.0",
        approval_id="A" * 43,
        owner_id="owner-1",
        session_id="session-1",
        condition_set_sha256=requests.condition_set_sha256,
        reference_set_sha256=counterfactual_cloudflare_reference_set_sha256(images),
        request_metadata_sha256=counterfactual_cloudflare_request_set_sha256(requests),
        usage_reservation_id="reference-reservation-000000000001",
        usage_policy_sha256="a" * 64,
        usage_binding_sha256="b" * 64,
        call_count=len(images),
        approval_basis="explicit_human_confirmation",
        consumed_at=datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc),
    )


def test_human_confirmed_cloudflare_artifacts_become_local_reference_material() -> None:
    conditions, requests, images = request_set_and_images()

    approved = approve_counterfactual_reference_artifacts(
        condition_set=conditions,
        request_set=requests,
        images=images,
        reference_set_sha256=counterfactual_cloudflare_reference_set_sha256(images),
        request_metadata_sha256=counterfactual_cloudflare_request_set_sha256(requests),
        approval_receipt=approval_receipt(conditions, requests, images),
    )

    assert approved.schema_version == "5.0"
    assert approved.human_confirmed is True
    assert len(approved.reference_images) == 3
    assert approved.reference_set.condition_set_sha256 == requests.condition_set_sha256
    assert tuple(image.pixel_sha256 for image in approved.reference_images) == (
        approved.reference_set.desired_image_hash.image_pixel_sha256,
        *(item.image_hash.image_pixel_sha256 for item in approved.reference_set.counterfactuals),
    )
    assert approved_counterfactual_references_sha256(approved) == (
        approved_counterfactual_references_sha256(approved)
    )
    assert all(image.body not in approved.model_dump_json().encode() for image in images)
    with pytest.raises(ValueError):
        type(approved).model_validate(
            {**approved.model_dump(mode="python"), "schema_version": "1.0"}
        )


def test_absent_human_confirmation_and_tampered_binding_are_rejected() -> None:
    conditions, requests, images = request_set_and_images()

    with pytest.raises(CounterfactualReferenceApprovalError, match="approval contract"):
        approve_counterfactual_reference_artifacts(
            condition_set=conditions,
            request_set=requests,
            images=images,
            reference_set_sha256=counterfactual_cloudflare_reference_set_sha256(images),
            request_metadata_sha256=counterfactual_cloudflare_request_set_sha256(requests),
            approval_receipt=None,
        )
    with pytest.raises(CounterfactualReferenceApprovalError, match="approval contract"):
        approve_counterfactual_reference_artifacts(
            condition_set=conditions,
            request_set=requests,
            images=images,
            reference_set_sha256="f" * 64,
            request_metadata_sha256=counterfactual_cloudflare_request_set_sha256(requests),
            approval_receipt=approval_receipt(conditions, requests, images),
        )
