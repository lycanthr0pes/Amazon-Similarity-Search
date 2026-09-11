import hashlib
import json
import struct
import zlib

import pytest
from pydantic import ValidationError

from src.search_v2.cloudflare_request import CLOUDFLARE_IMAGE_MODEL_ID
from src.search_v2.cloudflare_request import IMAGE_ANGLES
from src.search_v2.cloudflare_request import MAX_REFERENCE_IMAGE_BYTES
from src.search_v2.cloudflare_request import CloudflareImageRequest
from src.search_v2.cloudflare_request import CloudflareRequestError
from src.search_v2.cloudflare_request import build_cloudflare_front_request
from src.search_v2.cloudflare_request import build_cloudflare_request_set
from src.search_v2.cloudflare_request import cloudflare_image_request_sha256
from src.search_v2.cloudflare_request import cloudflare_request_set_sha256
from src.search_v2.cloudflare_request import image_prompt_contract_sha256
from src.search_v2.cloudflare_request import prepare_reference_png
from src.search_v2.intent import IntentAmbiguity
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent


PLAN_SHA256 = "a" * 64


def normalized_intent():
    payload = {
        "product_name_ja": "ヘッドホン",
        "product_name_en": "headphones",
        "category_ja": "オーディオ",
        "category_en": "audio equipment",
        "required_terms_ja": ["ワイヤレス"],
        "required_terms_en": ["wireless"],
        "preferred_terms_ja": ["軽量"],
        "preferred_terms_en": ["lightweight"],
        "negative_terms_ja": ["中古"],
        "negative_terms_en": ["used"],
        "color_ja": "黒",
        "color_en": "black",
        "features_ja": ["ノイズキャンセリング", "オーバーイヤー"],
        "features_en": ["noise cancelling", "over-ear"],
        "brand": "Sony",
        "model_number": "WH-1000XM5",
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
    source_input = "Sony WH-1000XM5を5万円以内で"
    provenance = build_intent_provenance(
        source_input=source_input,
        prompt=b"prompt",
        schema=b"schema",
        response=b"response",
    )
    return normalize_search_intent(
        source_input,
        SearchIntentDraft.model_validate(payload),
        provenance=provenance,
    )


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum)


def png_bytes(width: int = 2, height: int = 2, *, pixel: bytes = b"\x00\x00\x00") -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw_rows = (b"\x00" + pixel * width) * height
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            _png_chunk(b"IHDR", ihdr),
            _png_chunk(b"IDAT", zlib.compress(raw_rows)),
            _png_chunk(b"IEND", b""),
        )
    )


def expected_seed(angle: str, attempt: int) -> int:
    preimage = (f"amazon-explorer-image-seed-v1\n{PLAN_SHA256}\n{angle}\n{attempt}").encode()
    return int.from_bytes(hashlib.sha256(preimage).digest()[:4], "big")


def test_front_request_uses_exact_model_fixed_fields_and_no_reference() -> None:
    request = build_cloudflare_front_request(
        intent=normalized_intent(),
        preimage_plan_sha256=PLAN_SHA256,
        attempt=1,
    )

    assert request.method == "POST"
    assert request.model_id == CLOUDFLARE_IMAGE_MODEL_ID
    assert request.angle == "front_three_quarter"
    assert request.width == 512
    assert request.height == 512
    assert request.seed == expected_seed("front_three_quarter", 1)
    assert request.reference_image is None

    form = request.multipart_form()
    assert [(field.name, field.value) for field in form.text_fields] == [
        ("prompt", request.prompt),
        ("width", "512"),
        ("height", "512"),
        ("seed", str(request.seed)),
    ]
    assert form.file_fields == ()
    assert "steps" not in form.model_dump_json()
    assert "guidance" not in form.model_dump_json()


def test_prompt_uses_only_approved_visual_attributes_as_data() -> None:
    request = build_cloudflare_front_request(
        intent=normalized_intent(),
        preimage_plan_sha256=PLAN_SHA256,
        attempt=1,
    )

    assert "headphones" in request.prompt
    assert "audio equipment" in request.prompt
    assert "black" in request.prompt
    assert "wireless" in request.prompt
    assert "noise cancelling" in request.prompt
    assert "front three-quarter" in request.prompt
    assert "Sony" not in request.prompt
    assert "WH-1000XM5" not in request.prompt
    assert "5万円" not in request.prompt
    assert "used" not in request.prompt
    assert "軽量" not in request.prompt

    marker = "Visual attribute data: "
    encoded = request.prompt.split(marker, maxsplit=1)[1].split(". Show", maxsplit=1)[0]
    assert json.loads(encoded) == {
        "category": "audio equipment",
        "color": "black",
        "required_characteristics": ["wireless", "ワイヤレス"],
        "subject": "headphones",
        "visible_features": [
            "noise cancelling",
            "over-ear",
            "ノイズキャンセリング",
            "オーバーイヤー",
        ],
    }


def test_request_set_has_fixed_order_and_one_shared_front_reference() -> None:
    reference = png_bytes(width=511, height=510)
    request_set = build_cloudflare_request_set(
        intent=normalized_intent(),
        preimage_plan_sha256=PLAN_SHA256,
        attempt=1,
        front_reference_png=reference,
    )

    assert tuple(request.angle for request in request_set.requests) == IMAGE_ANGLES
    assert request_set.requests[0] == build_cloudflare_front_request(
        intent=normalized_intent(),
        preimage_plan_sha256=PLAN_SHA256,
        attempt=1,
    )
    assert request_set.requests[0].multipart_form().file_fields == ()

    expected_sha256 = hashlib.sha256(reference).hexdigest()
    for request in request_set.requests[1:]:
        assert request.reference_image is not None
        assert request.reference_image.sha256 == expected_sha256
        assert request.reference_image.width == 511
        assert request.reference_image.height == 510
        form = request.multipart_form()
        assert len(form.file_fields) == 1
        assert form.file_fields[0].name == "input_image_0"
        assert form.file_fields[0].filename == "front-reference.png"
        assert form.file_fields[0].content_type == "image/png"
        assert form.file_fields[0].body == reference

    assert "input_image_1" not in request_set.model_dump_json()
    assert "input_image_2" not in request_set.model_dump_json()
    assert "input_image_3" not in request_set.model_dump_json()


def test_derived_views_require_camera_motion_and_correct_occlusion() -> None:
    requests = build_cloudflare_request_set(
        intent=normalized_intent(),
        preimage_plan_sha256=PLAN_SHA256,
        attempt=2,
        front_reference_png=png_bytes(),
        derive_front=True,
    ).requests
    directions = (
        "45 degrees toward the product's left",
        "90 degrees toward the product's left",
        "90 degrees toward the product's right",
        "135 degrees toward the product's right",
    )
    for request, direction in zip(requests, directions, strict=True):
        assert direction in request.prompt
        assert request.prompt.index(direction) < request.prompt.index("Visual attribute data:")
        assert "input camera position as 0 degrees" in request.prompt
        assert "occluded" in request.prompt
        assert "Do not copy the input camera angle" in request.prompt
        assert request.reference_image is not None


def test_attempt_changes_seeds_and_request_metadata_digest() -> None:
    intent = normalized_intent()
    reference = png_bytes()
    first = build_cloudflare_request_set(
        intent=intent,
        preimage_plan_sha256=PLAN_SHA256,
        attempt=1,
        front_reference_png=reference,
    )
    second = build_cloudflare_request_set(
        intent=intent,
        preimage_plan_sha256=PLAN_SHA256,
        attempt=2,
        front_reference_png=reference,
    )

    assert [request.prompt for request in first.requests] == [
        request.prompt for request in second.requests
    ]
    assert [request.seed for request in first.requests] == [
        expected_seed(angle, 1) for angle in IMAGE_ANGLES
    ]
    assert [request.seed for request in second.requests] == [
        expected_seed(angle, 2) for angle in IMAGE_ANGLES
    ]
    assert cloudflare_request_set_sha256(first) != cloudflare_request_set_sha256(second)


def test_request_and_prompt_contract_digests_are_deterministic() -> None:
    intent = normalized_intent()
    first = build_cloudflare_front_request(
        intent=intent,
        preimage_plan_sha256=PLAN_SHA256,
        attempt=1,
    )
    second = build_cloudflare_front_request(
        intent=intent,
        preimage_plan_sha256=PLAN_SHA256,
        attempt=1,
    )

    assert cloudflare_image_request_sha256(first) == cloudflare_image_request_sha256(second)
    assert first.prompt_contract_sha256 == image_prompt_contract_sha256()
    assert len(image_prompt_contract_sha256()) == 64


def test_request_set_digest_binds_reference_image_bytes() -> None:
    first = build_cloudflare_request_set(
        intent=normalized_intent(),
        preimage_plan_sha256=PLAN_SHA256,
        attempt=1,
        front_reference_png=png_bytes(pixel=b"\x00\x00\x00"),
    )
    second = build_cloudflare_request_set(
        intent=normalized_intent(),
        preimage_plan_sha256=PLAN_SHA256,
        attempt=1,
        front_reference_png=png_bytes(pixel=b"\xff\xff\xff"),
    )

    assert cloudflare_request_set_sha256(first) != cloudflare_request_set_sha256(second)


@pytest.mark.parametrize("attempt", [0, 3, True, "1"])
def test_attempt_is_strict_and_limited_to_two_sets(attempt) -> None:
    with pytest.raises(CloudflareRequestError, match="image attempt is invalid"):
        build_cloudflare_front_request(
            intent=normalized_intent(),
            preimage_plan_sha256=PLAN_SHA256,
            attempt=attempt,
        )


def test_blocking_ambiguity_stops_request_construction() -> None:
    intent = normalized_intent().model_copy(
        update={
            "ambiguities": [
                IntentAmbiguity(
                    code="product_kind",
                    message="商品種別を確認してください",
                    blocking=True,
                )
            ]
        }
    )

    with pytest.raises(CloudflareRequestError, match="image intent is not ready"):
        build_cloudflare_front_request(
            intent=intent,
            preimage_plan_sha256=PLAN_SHA256,
            attempt=1,
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"not-a-png", "reference image is invalid"),
        (png_bytes(width=512, height=511), "reference image dimensions are invalid"),
        (png_bytes(width=511, height=512), "reference image dimensions are invalid"),
        (png_bytes() + b"trailing", "reference image is invalid"),
    ],
)
def test_reference_png_rejects_invalid_format_or_dimensions(payload: bytes, message: str) -> None:
    with pytest.raises(CloudflareRequestError, match=message):
        prepare_reference_png(payload)


def test_reference_png_rejects_corrupt_crc_and_oversized_body() -> None:
    corrupted = bytearray(png_bytes())
    corrupted[-5] ^= 0x01

    with pytest.raises(CloudflareRequestError, match="reference image is invalid"):
        prepare_reference_png(bytes(corrupted))
    with pytest.raises(CloudflareRequestError, match="reference image size is invalid"):
        prepare_reference_png(b"x" * (MAX_REFERENCE_IMAGE_BYTES + 1))


def test_reference_body_is_excluded_from_serializable_metadata() -> None:
    reference = png_bytes(pixel=b"secret-binary"[:3])
    request_set = build_cloudflare_request_set(
        intent=normalized_intent(),
        preimage_plan_sha256=PLAN_SHA256,
        attempt=1,
        front_reference_png=reference,
    )

    dumped = request_set.model_dump_json()
    assert reference.hex() not in dumped
    assert "body" not in dumped
    assert hashlib.sha256(reference).hexdigest() in dumped
    assert "authorization" not in dumped.casefold()
    assert "api_token" not in dumped.casefold()
    assert "account_id" not in dumped.casefold()


def test_strict_contract_rejects_unknown_transport_fields() -> None:
    request = build_cloudflare_front_request(
        intent=normalized_intent(),
        preimage_plan_sha256=PLAN_SHA256,
        attempt=1,
    )
    payload = request.model_dump(mode="python")
    payload["guidance"] = 3.5

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CloudflareImageRequest.model_validate(payload)


def test_request_digest_revalidates_tampered_seed() -> None:
    request = build_cloudflare_front_request(
        intent=normalized_intent(),
        preimage_plan_sha256=PLAN_SHA256,
        attempt=1,
    )
    tampered = request.model_copy(update={"seed": request.seed + 1})

    with pytest.raises(CloudflareRequestError, match="image request metadata is invalid"):
        cloudflare_image_request_sha256(tampered)
