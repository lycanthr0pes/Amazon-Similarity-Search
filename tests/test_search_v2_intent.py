import hashlib

import pytest
from pydantic import ValidationError

from src.search_v2.intent import PriceCondition
from src.search_v2.intent import IntentAmbiguity
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent


def draft_payload() -> dict[str, object]:
    return {
        "product_name_ja": "ヘッドホン",
        "product_name_en": "headphones",
        "category_ja": "オーディオ",
        "category_en": "audio",
        "required_terms_ja": ["ワイヤレス"],
        "required_terms_en": ["wireless"],
        "preferred_terms_ja": ["軽量"],
        "preferred_terms_en": ["lightweight"],
        "negative_terms_ja": ["中古"],
        "negative_terms_en": ["used"],
        "color_ja": "黒",
        "color_en": "black",
        "features_ja": ["ノイズキャンセリング"],
        "features_en": ["noise cancelling"],
        "brand": "Sony",
        "model_number": "WH-1000XM5",
        "price": {
            "currency": "JPY",
            "mode": "max",
            "target_jpy": None,
            "min_jpy": None,
            "max_jpy": 50000,
            "source": "explicit",
            "confidence": None,
        },
        "typed_conditions": [],
        "ambiguities": [],
    }


def test_search_intent_schema_requires_every_declared_field_and_forbids_extra() -> None:
    schema = SearchIntentDraft.model_json_schema()
    price_schema = schema["$defs"]["PriceCondition"]

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert price_schema["additionalProperties"] is False
    assert set(price_schema["required"]) == set(price_schema["properties"])

    payload = draft_payload()
    payload["unexpected"] = True
    with pytest.raises(ValidationError, match="extra_forbidden"):
        SearchIntentDraft.model_validate(payload)


def test_price_condition_is_strict_and_enforces_mode_invariants() -> None:
    payload = draft_payload()
    price = dict(payload["price"])
    price["max_jpy"] = "50000"
    payload["price"] = price
    with pytest.raises(ValidationError, match="int_type"):
        SearchIntentDraft.model_validate(payload)

    with pytest.raises(ValidationError, match="exact price requires only target_jpy"):
        PriceCondition(
            currency="JPY",
            mode="exact",
            target_jpy=50000,
            min_jpy=10000,
            max_jpy=None,
            source="explicit",
            confidence=None,
        )

    with pytest.raises(ValidationError, match="min_jpy must not exceed max_jpy"):
        PriceCondition(
            currency="JPY",
            mode="range",
            target_jpy=None,
            min_jpy=50000,
            max_jpy=10000,
            source="explicit",
            confidence=None,
        )


def test_draft_revalidates_preconstructed_nested_models() -> None:
    payload = draft_payload()
    payload["ambiguities"] = [
        IntentAmbiguity.model_construct(
            code="INVALID CODE",
            message="",
            blocking="yes",
        )
    ]

    with pytest.raises(ValidationError):
        SearchIntentDraft.model_validate(payload)


def test_draft_rejects_an_oversized_total_json_payload() -> None:
    payload = draft_payload()
    oversized_terms = ["😀" * 100 for _ in range(20)]
    for field_name in (
        "required_terms_ja",
        "required_terms_en",
        "preferred_terms_ja",
        "preferred_terms_en",
        "negative_terms_ja",
        "negative_terms_en",
        "features_ja",
        "features_en",
    ):
        payload[field_name] = oversized_terms

    with pytest.raises(ValidationError, match="intent JSON exceeds"):
        SearchIntentDraft.model_validate(payload)


def test_normalize_search_intent_is_deterministic_and_binds_exact_artifacts() -> None:
    source_input = "  Ｓｏｎｙ　ヘッドホン WH-1000XM5を5万円以内で  "
    payload = draft_payload()
    payload["features_ja"] = [
        " ノイズ　キャンセリング ",
        "ノイズ キャンセリング",
        "   ",
    ]
    payload["brand"] = "Ｓｏｎｙ"
    draft = SearchIntentDraft.model_validate(payload)
    provenance = build_intent_provenance(
        source_input=source_input,
        prompt=b"intent-prompt-v1",
        schema=b'{"type":"object"}',
        response=b'{"product_name_ja":"headphones"}',
    )

    first = normalize_search_intent(source_input, draft, provenance=provenance)
    second = normalize_search_intent(source_input, draft, provenance=provenance)

    assert first == second
    assert first.brand == "Sony"
    assert first.model_number == "WH-1000XM5"
    assert first.features_ja == ["ノイズ キャンセリング"]
    assert (
        first.provenance.source_input_sha256
        == hashlib.sha256(source_input.encode("utf-8")).hexdigest()
    )
    assert first.provenance.prompt_sha256 == hashlib.sha256(b"intent-prompt-v1").hexdigest()


def test_normalizer_removes_brand_and_model_without_literal_input_evidence() -> None:
    draft = SearchIntentDraft.model_validate(draft_payload())
    source_input = "軽いワイヤレスヘッドホンが欲しい"
    provenance = build_intent_provenance(
        source_input=source_input,
        prompt=b"prompt",
        schema=b"schema",
        response=b"response",
    )

    normalized = normalize_search_intent(source_input, draft, provenance=provenance)

    assert normalized.brand is None
    assert normalized.model_number is None


def test_normalizer_rejects_provenance_from_a_different_source_input() -> None:
    source_input = "軽いワイヤレスヘッドホンが欲しい"
    draft = SearchIntentDraft.model_validate(draft_payload())
    provenance = build_intent_provenance(
        source_input="別の入力",
        prompt=b"prompt",
        schema=b"schema",
        response=b"response",
    )

    with pytest.raises(ValueError, match="provenance does not match source_input"):
        normalize_search_intent(source_input, draft, provenance=provenance)


@pytest.mark.parametrize(
    "source_input",
    ["", "x" * 2001, "ヘッドホン\x00"],
)
def test_intent_provenance_rejects_invalid_source_input(source_input: str) -> None:
    with pytest.raises(ValueError):
        build_intent_provenance(
            source_input=source_input,
            prompt=b"prompt",
            schema=b"schema",
            response=b"response",
        )
