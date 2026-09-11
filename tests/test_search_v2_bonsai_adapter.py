import hashlib
import json
from dataclasses import FrozenInstanceError

import pytest

import src.search_v2.bonsai_adapter as bonsai_adapter
from src.exceptions import BonsaiResponseError
from src.search_v2.bonsai_adapter import parse_bonsai_intent_response
from src.search_v2.bonsai_adapter import search_intent_schema_bytes
from src.search_v2.intent import MAX_BOUND_ARTIFACT_BYTES
from src.search_v2.intent import SearchIntentDraft


SOURCE_INPUT = "Sony WH-1000XM5の黒いワイヤレスヘッドホンを5万円以内で"
PROMPT_BYTES = b"bonsai-search-intent-prompt-v2"


def intent_payload() -> dict[str, object]:
    return {
        "product_name_ja": "ヘッドホン",
        "product_name_en": "headphones",
        "required_terms_ja": ["ワイヤレス", "黒"],
        "required_terms_en": ["wireless", "black"],
        "preferred_terms_ja": ["軽量", "ノイズキャンセリング"],
        "preferred_terms_en": ["lightweight", "noise cancelling"],
        "negative_terms_ja": ["中古"],
        "negative_terms_en": ["used"],
        "brand": "Sony",
        "model_number": "WH-1000XM5",
        "price": {
            "mode": "max",
            "max_jpy": 50000,
            "source": "explicit",
        },
        "typed_conditions": [],
    }


def response_bytes(content: object) -> bytes:
    envelope = {
        "id": "fixture-response-id",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }
    return json.dumps(
        envelope,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def valid_response_bytes() -> bytes:
    content = json.dumps(
        intent_payload(),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return response_bytes(f"\n  {content}\n")


def test_parse_bonsai_intent_response_normalizes_and_binds_exact_artifacts() -> None:
    response = valid_response_bytes()

    intent = parse_bonsai_intent_response(
        source_input=SOURCE_INPUT,
        prompt=PROMPT_BYTES,
        response=response,
    )

    assert intent.schema_version == "2.0"
    assert intent.brand == "Sony"
    assert intent.model_number == "WH-1000XM5"
    assert intent.price.max_jpy == 50000
    assert (
        intent.provenance.source_input_sha256
        == hashlib.sha256(SOURCE_INPUT.encode("utf-8")).hexdigest()
    )
    assert intent.provenance.prompt_sha256 == hashlib.sha256(PROMPT_BYTES).hexdigest()
    assert (
        intent.provenance.schema_sha256 == hashlib.sha256(search_intent_schema_bytes()).hexdigest()
    )
    assert intent.provenance.response_sha256 == hashlib.sha256(response).hexdigest()


def test_search_intent_schema_bytes_are_canonical_and_deterministic() -> None:
    expected = json.dumps(
        SearchIntentDraft.model_json_schema(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    assert search_intent_schema_bytes() == expected
    assert search_intent_schema_bytes() == search_intent_schema_bytes()


@pytest.mark.parametrize(
    "response",
    [
        b"[]",
        b"{}",
        b'{"choices":[]}',
        b'{"choices":{}}',
        b'{"choices":[null]}',
        b'{"choices":[{}]}',
        b'{"choices":[{"message":null}]}',
        b'{"choices":[{"message":{}}]}',
        b'{"choices":[{"message":{"content":""}}]}',
        b'{"choices":[{"message":{"content":42}}]}',
    ],
)
def test_parse_bonsai_intent_response_rejects_invalid_envelope(response: bytes) -> None:
    with pytest.raises(BonsaiResponseError, match="search intent contract"):
        parse_bonsai_intent_response(
            source_input=SOURCE_INPUT,
            prompt=PROMPT_BYTES,
            response=response,
        )


def invalid_content_cases() -> list[str]:
    payload = intent_payload()
    valid_content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    extra = dict(payload)
    extra["unexpected"] = True

    wrong_type = dict(payload)
    wrong_type["price"] = {**dict(payload["price"]), "max_jpy": "50000"}

    duplicate_key = '{"product_name_ja":"別名",' + valid_content[1:]
    non_finite = valid_content.replace('"max_jpy":50000', '"max_jpy":NaN')

    return [
        f"```json\n{valid_content}\n```",
        f"説明です。{valid_content}",
        f"{valid_content}以上です。",
        "[]",
        '"not an object"',
        json.dumps(extra, ensure_ascii=False, separators=(",", ":")),
        json.dumps(wrong_type, ensure_ascii=False, separators=(",", ":")),
        duplicate_key,
        non_finite,
    ]


@pytest.mark.parametrize("content", invalid_content_cases())
def test_parse_bonsai_intent_response_rejects_non_strict_content(content: str) -> None:
    with pytest.raises(BonsaiResponseError, match="search intent contract"):
        parse_bonsai_intent_response(
            source_input=SOURCE_INPUT,
            prompt=PROMPT_BYTES,
            response=response_bytes(content),
        )


@pytest.mark.parametrize(
    "response",
    [
        b"",
        b"\xff",
        b"{" + (b" " * MAX_BOUND_ARTIFACT_BYTES),
    ],
)
def test_parse_bonsai_intent_response_rejects_invalid_raw_body(response: bytes) -> None:
    with pytest.raises(BonsaiResponseError, match="search intent contract"):
        parse_bonsai_intent_response(
            source_input=SOURCE_INPUT,
            prompt=PROMPT_BYTES,
            response=response,
        )


def test_parse_bonsai_intent_response_does_not_expose_raw_content_in_error() -> None:
    marker = "raw-secret-marker-must-not-leak"

    with pytest.raises(BonsaiResponseError) as error:
        parse_bonsai_intent_response(
            source_input=SOURCE_INPUT,
            prompt=PROMPT_BYTES,
            response=response_bytes(f'{{"unexpected":"{marker}"}}'),
        )

    assert marker not in str(error.value)
    assert error.value.__cause__ is None


@pytest.mark.parametrize(
    (
        "response",
        "stage",
        "draft_failure_group",
        "searchability_failure_group",
        "finish_reason",
        "completion_tokens",
    ),
    [
        (
            b"",
            "response_metadata_invalid",
            "not_applicable",
            "not_applicable",
            "missing",
            None,
        ),
        (
            b"{}",
            "envelope_invalid",
            "not_applicable",
            "not_applicable",
            "missing",
            None,
        ),
        (
            response_bytes("not-json"),
            "content_not_json",
            "not_applicable",
            "not_applicable",
            "stop",
            20,
        ),
        (
            response_bytes("{}"),
            "draft_schema_invalid",
            "document",
            "not_applicable",
            "stop",
            20,
        ),
    ],
)
def test_parse_failure_has_only_safe_stage_metadata(
    response: bytes,
    stage: str,
    draft_failure_group: str,
    searchability_failure_group: str,
    finish_reason: str,
    completion_tokens: int | None,
) -> None:
    error_type = getattr(bonsai_adapter, "BonsaiResponseContractError", BonsaiResponseError)
    with pytest.raises(error_type) as error:
        parse_bonsai_intent_response(
            source_input=SOURCE_INPUT,
            prompt=PROMPT_BYTES,
            response=response,
        )

    assert str(error.value) == "Bonsai response did not match the search intent contract"
    diagnostic_type = getattr(bonsai_adapter, "BonsaiResponseDiagnostic", None)
    assert diagnostic_type is not None
    assert error.value.diagnostic == diagnostic_type(
        stage=stage,
        draft_failure_group=draft_failure_group,
        searchability_failure_group=searchability_failure_group,
        finish_reason=finish_reason,
        completion_tokens=completion_tokens,
        response_bytes=len(response),
    )
    assert error.value.__cause__ is None
    assert error.value.__context__ is None


def invalid_draft_group_cases() -> list[tuple[dict[str, object], str]]:
    marker = "raw-draft-marker-must-not-leak"
    price = intent_payload()
    price["price"] = {
        "mode": "max",
        "max_jpy": marker,
        "source": "explicit",
    }

    typed = intent_payload()
    typed["typed_conditions"] = [
        {
            "attribute_key": marker,
            "operator": "at_most",
            "expected_value": {
                "value_type": "decimal",
                "minimum": None,
                "maximum": "120",
                "unit": "mm",
            },
            "strength": "required",
        }
    ]

    ambiguity = {
        "ambiguities": [
            {
                "code": f"{marker}!",
                "message": "確認が必要です",
                "blocking": True,
            }
        ]
    }

    fields = intent_payload()
    fields["product_name_ja"] = marker * 2
    return [
        (price, "price"),
        (typed, "typed_conditions"),
        (ambiguity, "ambiguities"),
        (fields, "fields"),
    ]


@pytest.mark.parametrize(("payload", "expected_group"), invalid_draft_group_cases())
def test_draft_schema_failure_exposes_only_a_fixed_group(
    payload: dict[str, object],
    expected_group: str,
) -> None:
    marker = "raw-draft-marker-must-not-leak"
    content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    error_type = getattr(bonsai_adapter, "BonsaiResponseContractError", BonsaiResponseError)
    with pytest.raises(error_type) as error:
        parse_bonsai_intent_response(
            source_input=SOURCE_INPUT,
            prompt=PROMPT_BYTES,
            response=response_bytes(content),
        )

    assert error.value.diagnostic.stage == "draft_schema_invalid"
    assert error.value.diagnostic.draft_failure_group == expected_group
    assert marker not in str(error.value)
    assert marker not in repr(error.value)
    assert marker not in repr(error.value.diagnostic)
    assert error.value.__cause__ is None
    assert error.value.__context__ is None


def test_finish_reason_length_is_reported_as_truncation_before_content_parsing() -> None:
    envelope = {
        "choices": [
            {
                "message": {"content": "not-json"},
                "finish_reason": "length",
            }
        ],
        "usage": {"completion_tokens": 321},
    }
    response = json.dumps(envelope, separators=(",", ":")).encode()

    error_type = getattr(bonsai_adapter, "BonsaiResponseContractError", BonsaiResponseError)
    with pytest.raises(error_type) as error:
        parse_bonsai_intent_response(
            source_input=SOURCE_INPUT,
            prompt=PROMPT_BYTES,
            response=response,
        )

    diagnostic_type = getattr(bonsai_adapter, "BonsaiResponseDiagnostic", None)
    assert diagnostic_type is not None
    assert error.value.diagnostic == diagnostic_type(
        stage="output_truncated",
        draft_failure_group="not_applicable",
        searchability_failure_group="not_applicable",
        finish_reason="length",
        completion_tokens=321,
        response_bytes=len(response),
    )


def test_unknown_finish_reason_is_normalized_without_retaining_provider_value() -> None:
    marker = "provider-specific-secret-finish-reason"
    envelope = {
        "choices": [
            {
                "message": {"content": "not-json"},
                "finish_reason": marker,
            }
        ],
        "usage": {"completion_tokens": -1},
    }
    response = json.dumps(envelope, separators=(",", ":")).encode()

    error_type = getattr(bonsai_adapter, "BonsaiResponseContractError", BonsaiResponseError)
    with pytest.raises(error_type) as error:
        parse_bonsai_intent_response(
            source_input=SOURCE_INPUT,
            prompt=PROMPT_BYTES,
            response=response,
        )

    assert error.value.diagnostic.finish_reason == "other"
    assert error.value.diagnostic.completion_tokens is None
    assert marker not in repr(error.value)
    assert marker not in repr(error.value.diagnostic)


def test_normalization_failure_is_classified_without_validation_details() -> None:
    marker = "raw-secret-marker"
    payload = {
        "ambiguities": [
            {
                "code": "needs_confirmation",
                "message": f"unsafe\u0001{marker}",
                "blocking": True,
            }
        ]
    }
    content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    response = response_bytes(content)

    error_type = getattr(bonsai_adapter, "BonsaiResponseContractError", BonsaiResponseError)
    with pytest.raises(error_type) as error:
        parse_bonsai_intent_response(
            source_input=SOURCE_INPUT,
            prompt=PROMPT_BYTES,
            response=response,
        )

    assert error.value.diagnostic.stage == "intent_normalization_invalid"
    assert marker not in str(error.value)
    assert marker not in repr(error.value)
    assert marker not in repr(error.value.diagnostic)
    assert error.value.__cause__ is None
    assert error.value.__context__ is None


def test_searchable_profile_requires_product_name_before_postprocess() -> None:
    marker = "unsearchable-intent-marker"
    payload = {"product_name_en": marker}
    content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    response = response_bytes(content)

    error_type = getattr(bonsai_adapter, "BonsaiResponseContractError", BonsaiResponseError)
    with pytest.raises(error_type) as error:
        parse_bonsai_intent_response(
            source_input=SOURCE_INPUT,
            prompt=PROMPT_BYTES,
            response=response,
        )

    assert error.value.diagnostic.stage == "draft_schema_invalid"
    assert error.value.diagnostic.draft_failure_group == "document"
    assert error.value.diagnostic.searchability_failure_group == "not_applicable"
    assert marker not in str(error.value)
    assert marker not in repr(error.value)
    assert marker not in repr(error.value.diagnostic)
    assert error.value.__cause__ is None
    assert error.value.__context__ is None


def test_invalid_declared_search_term_has_only_a_fixed_searchability_group() -> None:
    marker = "invalid-search-term-marker"
    payload = {"product_name_ja": f"https://{marker}.test/item"}
    content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    error_type = getattr(bonsai_adapter, "BonsaiResponseContractError", BonsaiResponseError)
    with pytest.raises(error_type) as error:
        parse_bonsai_intent_response(
            source_input=SOURCE_INPUT,
            prompt=PROMPT_BYTES,
            response=response_bytes(content),
        )

    assert error.value.diagnostic.stage == "intent_searchability_invalid"
    assert error.value.diagnostic.searchability_failure_group == "invalid_terms"
    assert marker not in str(error.value)
    assert marker not in repr(error.value)
    assert marker not in repr(error.value.diagnostic)
    assert error.value.__cause__ is None
    assert error.value.__context__ is None


def test_blocking_intent_without_searchable_terms_remains_valid() -> None:
    payload = {
        "ambiguities": [
            {
                "code": "product_type_unknown",
                "message": "商品種別を確認してください",
                "blocking": True,
            }
        ]
    }
    content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    intent = parse_bonsai_intent_response(
        source_input=SOURCE_INPUT,
        prompt=PROMPT_BYTES,
        response=response_bytes(content),
    )

    assert intent.has_blocking_ambiguity


def test_response_diagnostic_is_frozen_and_rejects_unknown_codes() -> None:
    diagnostic_type = getattr(bonsai_adapter, "BonsaiResponseDiagnostic", None)
    assert diagnostic_type is not None
    diagnostic = diagnostic_type(
        stage="envelope_invalid",
        draft_failure_group="not_applicable",
        searchability_failure_group="not_applicable",
        finish_reason="missing",
        completion_tokens=None,
        response_bytes=2,
    )

    with pytest.raises(FrozenInstanceError):
        diagnostic.response_bytes = 3
    with pytest.raises((TypeError, ValueError)):
        diagnostic_type(
            stage="raw-provider-error",
            draft_failure_group="not_applicable",
            searchability_failure_group="not_applicable",
            finish_reason="missing",
            completion_tokens=None,
            response_bytes=2,
        )
    with pytest.raises((TypeError, ValueError)):
        diagnostic_type(
            stage="draft_schema_invalid",
            draft_failure_group="not_applicable",
            searchability_failure_group="not_applicable",
            finish_reason="stop",
            completion_tokens=1,
            response_bytes=2,
        )
    with pytest.raises((TypeError, ValueError)):
        diagnostic_type(
            stage="envelope_invalid",
            draft_failure_group="price",
            searchability_failure_group="not_applicable",
            finish_reason="missing",
            completion_tokens=None,
            response_bytes=2,
        )
    with pytest.raises((TypeError, ValueError)):
        diagnostic_type(
            stage="intent_searchability_invalid",
            draft_failure_group="not_applicable",
            searchability_failure_group="not_applicable",
            finish_reason="stop",
            completion_tokens=1,
            response_bytes=2,
        )
    with pytest.raises((TypeError, ValueError)):
        diagnostic_type(
            stage="envelope_invalid",
            draft_failure_group="not_applicable",
            searchability_failure_group="missing_terms",
            finish_reason="missing",
            completion_tokens=None,
            response_bytes=2,
        )
    with pytest.raises((TypeError, ValueError)):
        diagnostic_type(
            stage="intent_searchability_invalid",
            draft_failure_group="not_applicable",
            searchability_failure_group="provider-detail",
            finish_reason="stop",
            completion_tokens=1,
            response_bytes=2,
        )
