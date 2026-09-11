from __future__ import annotations

import hashlib
import struct
import zlib

import pytest

from src.search_v2.counterfactual_cloudflare_request import (
    CounterfactualCloudflareRequestError,
)
from src.search_v2.counterfactual_cloudflare_request import (
    build_counterfactual_cloudflare_desired_request,
)
from src.search_v2.counterfactual_cloudflare_request import (
    build_counterfactual_cloudflare_request_set,
)
from src.search_v2.counterfactual_cloudflare_request import (
    counterfactual_cloudflare_request_set_sha256,
)
from src.search_v2.counterfactual_image import VisualConditionDraft
from src.search_v2.counterfactual_image import build_visual_condition_set
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent


PLAN_SHA256 = "a" * 64


def normalized_intent():
    source = "Sonyの黒いヘッドレスト付きオフィスチェアを5万円以内で。中古は除外"
    payload = {
        "product_name_ja": "オフィスチェア",
        "product_name_en": "office chair",
        "category_ja": "椅子",
        "category_en": "chair",
        "required_terms_ja": ["ヘッドレスト付き"],
        "required_terms_en": ["with headrest"],
        "preferred_terms_ja": [],
        "preferred_terms_en": [],
        "negative_terms_ja": ["中古"],
        "negative_terms_en": ["used"],
        "color_ja": "黒",
        "color_en": "black",
        "features_ja": ["メッシュ背もたれ"],
        "features_en": ["mesh back"],
        "brand": "Sony",
        "model_number": None,
        "price": {
            "currency": "JPY",
            "mode": "max",
            "target_jpy": None,
            "min_jpy": None,
            "max_jpy": 50_000,
            "source": "explicit",
            "confidence": None,
        },
        "typed_conditions": [],
        "ambiguities": [],
    }
    provenance = build_intent_provenance(
        source_input=source,
        prompt=b"prompt",
        schema=b"schema",
        response=b"response",
    )
    return normalize_search_intent(
        source,
        SearchIntentDraft.model_validate(payload),
        provenance=provenance,
    )


def conditions(count: int = 2):
    source = "黒いメッシュ背もたれでヘッドレスト付きのオフィスチェア"
    drafts = (
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
        VisualConditionDraft(
            source_phrase="メッシュ背もたれ",
            strength="preferred",
            attribute_key=None,
        ),
    )
    return build_visual_condition_set(source_input=source, drafts=drafts[:count])


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def png_bytes() -> bytes:
    ihdr = struct.pack(">IIBBBBB", 10, 10, 8, 2, 0, 0, 0)
    rows = (b"\x00" + b"\x01\x02\x03" * 10) * 10
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            _png_chunk(b"IHDR", ihdr),
            _png_chunk(b"IDAT", zlib.compress(rows)),
            _png_chunk(b"IEND", b""),
        )
    )


def test_desired_request_uses_only_bounded_subject_and_confirmed_visual_phrases() -> None:
    request = build_counterfactual_cloudflare_desired_request(
        intent=normalized_intent(),
        condition_set=conditions(),
        preimage_plan_sha256=PLAN_SHA256,
    )

    assert request.schema_version == "1.0"
    assert request.target == "desired"
    assert request.condition_id is None
    assert request.attempt == 1
    assert request.reference_image is None
    assert "office chair" in request.prompt
    assert "黒い" in request.prompt
    assert "ヘッドレスト付き" in request.prompt
    assert "Sony" not in request.prompt
    assert "50000" not in request.prompt
    assert "used" not in request.prompt
    assert "中古" not in request.prompt
    assert normalized_intent().provenance.source_input_sha256 not in request.prompt


@pytest.mark.parametrize("count", [1, 2, 3])
def test_request_set_has_exact_one_plus_condition_count_without_retry(count: int) -> None:
    condition_set = conditions(count)
    request_set = build_counterfactual_cloudflare_request_set(
        intent=normalized_intent(),
        condition_set=condition_set,
        preimage_plan_sha256=PLAN_SHA256,
        desired_reference_png=png_bytes(),
    )

    assert request_set.call_count == 1 + count
    assert len(request_set.requests) == 1 + count
    assert request_set.requests[0].target == "desired"
    assert request_set.requests[0].reference_image is None
    assert tuple(item.condition_id for item in request_set.requests[1:]) == tuple(
        item.condition_id for item in condition_set.conditions
    )
    assert all(item.target == "counterfactual" for item in request_set.requests[1:])
    assert all(item.attempt == 1 for item in request_set.requests)
    assert all(item.reference_image is not None for item in request_set.requests[1:])
    assert len({item.reference_image.sha256 for item in request_set.requests[1:]}) == 1


def test_each_counterfactual_negates_one_condition_and_preserves_the_rest() -> None:
    request_set = build_counterfactual_cloudflare_request_set(
        intent=normalized_intent(),
        condition_set=conditions(3),
        preimage_plan_sha256=PLAN_SHA256,
        desired_reference_png=png_bytes(),
    )

    for request, condition in zip(
        request_set.requests[1:],
        conditions(3).conditions,
        strict=True,
    ):
        assert condition.source_phrase in request.prompt
        assert "change only the target condition" in request.prompt
        assert "preserve every other desired condition" in request.prompt


def test_digest_is_deterministic_and_separate_from_the_legacy_four_angle_schema() -> None:
    request_set = build_counterfactual_cloudflare_request_set(
        intent=normalized_intent(),
        condition_set=conditions(),
        preimage_plan_sha256=PLAN_SHA256,
        desired_reference_png=png_bytes(),
    )

    assert counterfactual_cloudflare_request_set_sha256(request_set) == (
        counterfactual_cloudflare_request_set_sha256(request_set)
    )
    assert request_set.schema_version == "1.0"
    assert "angle" not in request_set.model_dump(mode="json")


def test_request_rejects_more_than_three_conditions_and_tampered_reference() -> None:
    desired = build_counterfactual_cloudflare_desired_request(
        intent=normalized_intent(),
        condition_set=conditions(),
        preimage_plan_sha256=PLAN_SHA256,
    )
    assert hashlib.sha256(desired.prompt.encode()).hexdigest()

    with pytest.raises(CounterfactualCloudflareRequestError, match="request contract"):
        build_counterfactual_cloudflare_request_set(
            intent=normalized_intent(),
            condition_set=conditions(),
            preimage_plan_sha256=PLAN_SHA256,
            desired_reference_png=png_bytes() + b"tampered",
        )
