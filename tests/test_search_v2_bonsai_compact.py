import json

from jsonschema import Draft202012Validator
import pytest

from src.search_v2.bonsai_adapter import BonsaiResponseContractError
from src.search_v2.bonsai_adapter import parse_bonsai_intent_response
from src.search_v2.bonsai_adapter import search_intent_generation_schema_bytes
from src.search_v2.bonsai_request import build_bonsai_intent_request
from src.search_v2.bonsai_request import load_bonsai_intent_prompt
from src.search_v2.query_planner import build_search_query_plan
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal


SOURCE_INPUT = "5万円以内で黒色のワイヤレスヘッドホン。中古は除外。"
PROMPT_BYTES = b"bonsai-compact-wire-fixture"
LATENCY_REGRESSION_INPUT = "1万円以内の白い静音ワイヤレス日本語配列キーボード。テンキーは不要。"


def typed_color_condition() -> dict[str, object]:
    return {
        "attribute_key": "appearance.color",
        "operator": "equals",
        "expected_value": {
            "value_type": "enum",
            "values": ["black"],
        },
        "strength": "required",
    }


def compact_intent_payload() -> dict[str, object]:
    return {
        "product_name_ja": "ヘッドホン",
        "product_name_en": "headphones",
        "required_terms_ja": ["ワイヤレス", "黒"],
        "required_terms_en": ["wireless", "black"],
        "negative_terms_ja": ["中古"],
        "negative_terms_en": ["used"],
        "price": {
            "mode": "max",
            "max_jpy": 50000,
            "source": "explicit",
        },
        "typed_conditions": [typed_color_condition()],
    }


def complete_intent_payload() -> dict[str, object]:
    return {
        "product_name_ja": "ヘッドホン",
        "product_name_en": "headphones",
        "category_ja": None,
        "category_en": None,
        "required_terms_ja": ["ワイヤレス", "黒"],
        "required_terms_en": ["wireless", "black"],
        "preferred_terms_ja": [],
        "preferred_terms_en": [],
        "negative_terms_ja": ["中古"],
        "negative_terms_en": ["used"],
        "color_ja": None,
        "color_en": None,
        "features_ja": [],
        "features_en": [],
        "brand": None,
        "model_number": None,
        "price": {
            "currency": "JPY",
            "mode": "max",
            "target_jpy": None,
            "min_jpy": None,
            "max_jpy": 50000,
            "source": "explicit",
            "confidence": None,
        },
        "typed_conditions": [typed_color_condition()],
        "ambiguities": [],
    }


def response_bytes(payload: dict[str, object]) -> bytes:
    content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    envelope = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": content},
            }
        ],
        "usage": {"completion_tokens": 196},
    }
    return json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode()


def semantic_intent(intent) -> dict[str, object]:
    return intent.model_dump(mode="json", exclude={"provenance"})


def semantic_proposal(proposal) -> dict[str, object]:
    return proposal.model_dump(
        mode="json",
        exclude={
            "intent_sha256",
            "candidate_set_sha256",
            "registry_sha256",
            "adapter_profile_sha256",
            "requirement_set_sha256",
        },
    )


def test_compact_wire_restores_only_source_grounded_semantics() -> None:
    compact = parse_bonsai_intent_response(
        source_input=SOURCE_INPUT,
        prompt=PROMPT_BYTES,
        response=response_bytes(compact_intent_payload()),
    )
    expected_payload = complete_intent_payload()
    expected_payload.update(
        product_name_en=None,
        required_terms_en=[],
        negative_terms_en=[],
    )
    expected = type(compact).model_validate(
        {
            "schema_version": "2.0",
            **expected_payload,
            "provenance": compact.provenance,
        }
    )

    assert semantic_intent(compact) == semantic_intent(expected)
    assert [item.model_dump(mode="json") for item in build_search_query_plan(compact).queries] == [
        item.model_dump(mode="json") for item in build_search_query_plan(expected).queries
    ]
    assert semantic_proposal(build_typed_requirement_proposal(compact)) == semantic_proposal(
        build_typed_requirement_proposal(expected)
    )
    assert compact.price.currency == "JPY"
    assert compact.price.target_jpy is None
    assert compact.price.min_jpy is None
    assert compact.price.max_jpy == 50000
    assert compact.price.confidence is None
    assert compact.preferred_terms_ja == []
    assert compact.features_en == []
    assert compact.brand is None
    assert compact.ambiguities == []


def test_compact_wire_restores_omitted_price_and_collection_defaults() -> None:
    intent = parse_bonsai_intent_response(
        source_input="ヘッドホン",
        prompt=PROMPT_BYTES,
        response=response_bytes({"product_name_ja": "ヘッドホン"}),
    )

    assert intent.price.model_dump(mode="json") == {
        "currency": "JPY",
        "mode": "none",
        "target_jpy": None,
        "min_jpy": None,
        "max_jpy": None,
        "source": "none",
        "confidence": None,
    }
    assert intent.required_terms_ja == []
    assert intent.typed_conditions == []
    assert intent.ambiguities == []
    assert [query.language for query in build_search_query_plan(intent).queries] == ["ja"]


def test_latency_regression_input_has_a_short_ready_compact_representation() -> None:
    payload = {
        "product_name_ja": "日本語配列キーボード",
        "required_terms_ja": ["白", "静音", "ワイヤレス"],
        "negative_terms_ja": ["テンキー"],
        "price": {"mode": "max", "max_jpy": 10000, "source": "explicit"},
    }
    compact = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    intent = parse_bonsai_intent_response(
        source_input=LATENCY_REGRESSION_INPUT,
        prompt=PROMPT_BYTES,
        response=response_bytes(payload),
    )
    proposal = build_typed_requirement_proposal(intent)
    query_plan = build_search_query_plan(intent)

    assert len(compact) <= 203
    assert intent.product_name_en is None
    assert intent.price.max_jpy == 10000
    assert intent.required_terms_ja == ["白", "静音", "ワイヤレス"]
    assert intent.negative_terms_ja == ["テンキー"]
    assert proposal.status == "ready"
    assert [query.language for query in query_plan.queries] == ["ja"]


def test_live_regression_is_grounded_and_recovers_explicit_source_conditions() -> None:
    payload = {
        "product_name_ja": "静音ワイヤレス日本語配列キーボード",
        "required_terms_ja": ["1万円"],
        "typed_conditions": [
            {
                "attribute_key": "appearance.color",
                "operator": "equals",
                "expected_value": {"value_type": "enum", "values": ["white"]},
                "strength": "required",
            },
            {
                "attribute_key": "appearance.style",
                "operator": "similar_to",
                "expected_value": {"value_type": "semantic", "label": "minimal"},
                "strength": "preferred",
            },
            {
                "attribute_key": "form.factor",
                "operator": "equals",
                "expected_value": {
                    "value_type": "enum",
                    "values": ["wireless", "wireless"],
                },
                "strength": "required",
            },
            {
                "attribute_key": "form.orientation",
                "operator": "equals",
                "expected_value": {
                    "value_type": "enum",
                    "values": ["horizontal", "vertical"],
                },
                "strength": "required",
            },
        ],
    }

    # The historical response refers to a removed preset; it must be regenerated.
    with pytest.raises(BonsaiResponseContractError):
        parse_bonsai_intent_response(
            source_input=LATENCY_REGRESSION_INPUT,
            prompt=PROMPT_BYTES,
            response=response_bytes(payload),
        )

    # Preserve the source-grounding regression with the current geometric preset.
    payload["typed_conditions"][2]["attribute_key"] = "form.shape"
    payload["typed_conditions"][2]["expected_value"]["values"] = ["round", "round"]
    intent = parse_bonsai_intent_response(
        source_input=LATENCY_REGRESSION_INPUT,
        prompt=PROMPT_BYTES,
        response=response_bytes(payload),
    )
    proposal = build_typed_requirement_proposal(intent)
    query_plan = build_search_query_plan(intent)

    assert intent.price.max_jpy == 10000
    assert intent.negative_terms_ja == ["テンキー"]
    assert intent.required_terms_ja == ["白"]
    assert [item.attribute_key for item in intent.typed_conditions] == ["appearance.color"]
    assert proposal.status == "ready"
    assert "白" in query_plan.queries[0].value


@pytest.mark.parametrize(
    ("source_input", "expected_mode", "expected_min", "expected_max"),
    [
        ("5000円以上の保存容器", "min", 5000, None),
        ("1.5万円以下の保存容器", "max", None, 15000),
        ("5000円から1万円の保存容器", "range", 5000, 10000),
    ],
)
def test_explicit_jpy_bounds_are_recovered_without_product_vocabulary(
    source_input: str,
    expected_mode: str,
    expected_min: int | None,
    expected_max: int | None,
) -> None:
    intent = parse_bonsai_intent_response(
        source_input=source_input,
        prompt=PROMPT_BYTES,
        response=response_bytes({"product_name_ja": "保存容器"}),
    )

    assert intent.price.mode == expected_mode
    assert intent.price.min_jpy == expected_min
    assert intent.price.max_jpy == expected_max
    assert intent.price.source == "explicit"


def test_malformed_grouped_jpy_is_not_partially_recovered() -> None:
    intent = parse_bonsai_intent_response(
        source_input="5,00円以上の保存容器",
        prompt=PROMPT_BYTES,
        response=response_bytes({"product_name_ja": "保存容器"}),
    )

    assert intent.price.mode == "none"


def test_single_character_typed_alias_does_not_match_inside_an_unknown_word() -> None:
    payload = {
        "product_name_ja": "双眼鏡",
        "typed_conditions": [
            {
                "attribute_key": "appearance.color",
                "operator": "equals",
                "expected_value": {"value_type": "enum", "values": ["white"]},
                "strength": "required",
            }
        ],
    }

    intent = parse_bonsai_intent_response(
        source_input="白鳥観察用の双眼鏡",
        prompt=PROMPT_BYTES,
        response=response_bytes(payload),
    )

    assert intent.typed_conditions == []
    assert intent.required_terms_ja == []


def test_single_character_alias_does_not_match_unknown_compound_suffix() -> None:
    payload = {
        "product_name_ja": "洗濯機",
        "typed_conditions": [
            {
                "attribute_key": "appearance.color",
                "operator": "equals",
                "expected_value": {"value_type": "enum", "values": ["white"]},
                "strength": "required",
            }
        ],
    }

    intent = parse_bonsai_intent_response(
        source_input="漂白機能付き洗濯機",
        prompt=PROMPT_BYTES,
        response=response_bytes(payload),
    )

    assert intent.typed_conditions == []
    assert intent.required_terms_ja == []


def test_japanese_negative_target_starts_after_the_previous_case_particle() -> None:
    intent = parse_bonsai_intent_response(
        source_input="静音キーボードでテンキーは不要",
        prompt=PROMPT_BYTES,
        response=response_bytes({"product_name_ja": "キーボード"}),
    )

    assert intent.negative_terms_ja == ["テンキー"]


def test_japanese_double_negative_is_not_recovered_as_an_exclusion() -> None:
    intent = parse_bonsai_intent_response(
        source_input="テンキーは不要ではない",
        prompt=PROMPT_BYTES,
        response=response_bytes({"product_name_ja": "キーボード"}),
    )

    assert intent.negative_terms_ja == []


def test_ungrounded_product_name_uses_grounded_positive_terms_from_observed_live_intent() -> None:
    source_input = (
        "5,000円以上10,000円以下の藍鼠色で超低背のワイヤレスキーボード。"
        "発光機能は除外。テンキーは不要ではない。"
    )
    intent = parse_bonsai_intent_response(
        source_input=source_input,
        prompt=PROMPT_BYTES,
        response=response_bytes(
            {
                "product_name_ja": "青いマウス",
                "required_terms_ja": ["超低背", "ワイヤレスキーボード", "ワイヤレス"],
                "negative_terms_ja": ["発光機能"],
            }
        ),
    )
    proposal = build_typed_requirement_proposal(intent)
    query_plan = build_search_query_plan(intent)

    assert intent.product_name_ja is None
    assert intent.required_terms_ja == ["超低背", "ワイヤレスキーボード", "ワイヤレス"]
    assert intent.negative_terms_ja == ["発光機能"]
    assert intent.price.mode == "range"
    assert intent.price.min_jpy == 5000
    assert intent.price.max_jpy == 10000
    assert intent.ambiguities == []
    assert proposal.status == "ready"
    assert [item.language for item in query_plan.queries] == ["ja"]
    assert query_plan.queries[0].value == "超低背 ワイヤレス キーボード"


def test_ungrounded_product_without_positive_terms_still_blocks() -> None:
    intent = parse_bonsai_intent_response(
        source_input="5,000円以内。発光機能は除外。",
        prompt=PROMPT_BYTES,
        response=response_bytes(
            {
                "product_name_ja": "青いマウス",
                "negative_terms_ja": ["発光機能"],
            }
        ),
    )

    assert intent.product_name_ja is None
    assert intent.required_terms_ja == []
    assert intent.preferred_terms_ja == []
    assert intent.negative_terms_ja == ["発光機能"]
    assert [item.code for item in intent.ambiguities] == ["source_product_ungrounded"]
    with pytest.raises(ValueError, match="blocking ambiguity"):
        build_search_query_plan(intent)


def test_free_terms_and_scalar_values_require_exact_source_grounding() -> None:
    intent = parse_bonsai_intent_response(
        source_input="白いキーボード",
        prompt=PROMPT_BYTES,
        response=response_bytes(
            {
                "product_name_ja": "キーボード",
                "required_terms_ja": ["白", "青い"],
                "brand": "Invented Brand",
                "model_number": "MODEL-404",
            }
        ),
    )

    assert intent.product_name_ja == "キーボード"
    assert intent.required_terms_ja == ["白"]
    assert intent.brand is None
    assert intent.model_number is None
    assert intent.ambiguities == []


def test_grounded_english_product_keeps_an_english_only_query() -> None:
    intent = parse_bonsai_intent_response(
        source_input="A hyperspectral portable spectrometer.",
        prompt=PROMPT_BYTES,
        response=response_bytes(
            {
                "product_name_ja": "携帯用分光計",
                "product_name_en": "portable spectrometer",
                "required_terms_en": ["hyperspectral"],
            }
        ),
    )
    query_plan = build_search_query_plan(intent)

    assert intent.product_name_ja is None
    assert intent.product_name_en == "portable spectrometer"
    assert intent.required_terms_en == ["hyperspectral"]
    assert intent.ambiguities == []
    assert [query.language for query in query_plan.queries] == ["en"]


def test_unknown_english_exclusion_is_recovered_only_in_english_terms() -> None:
    intent = parse_bonsai_intent_response(
        source_input="A portable spectrometer without a field subscription.",
        prompt=PROMPT_BYTES,
        response=response_bytes({"product_name_ja": "携帯用分光計"}),
    )

    assert intent.negative_terms_en == ["field subscription"]
    assert intent.negative_terms_ja == []


@pytest.mark.parametrize(
    ("source_input", "payload", "expected_languages"),
    [
        (
            "藍鼠色で超低背のキーボード。発光機能は除外。",
            {
                "product_name_ja": "キーボード",
                "required_terms_ja": ["藍鼠色", "超低背"],
                "negative_terms_ja": ["発光機能"],
            },
            ["ja"],
        ),
        (
            "雲母調で真空対応の保存容器。積み重ね可能が希望。使い捨ては避ける。",
            {
                "product_name_ja": "保存容器",
                "required_terms_ja": ["雲母調", "真空対応"],
                "preferred_terms_ja": ["積み重ね可能"],
                "negative_terms_ja": ["使い捨て"],
            },
            ["ja"],
        ),
        (
            "A hyperspectral, field-calibrated portable spectrometer without a subscription.",
            {
                "product_name_ja": "携帯用分光計",
                "product_name_en": "portable spectrometer",
                "required_terms_en": ["hyperspectral", "field-calibrated"],
                "negative_terms_en": ["subscription"],
            },
            ["en"],
        ),
    ],
)
def test_unregistered_search_vocabulary_is_preserved_without_a_term_whitelist(
    source_input: str,
    payload: dict[str, object],
    expected_languages: list[str],
) -> None:
    intent = parse_bonsai_intent_response(
        source_input=source_input,
        prompt=PROMPT_BYTES,
        response=response_bytes(payload),
    )
    query_plan = build_search_query_plan(intent)
    prompt = load_bonsai_intent_prompt().decode("utf-8")

    assert [query.language for query in query_plan.queries] == expected_languages
    for field_name in (
        "required_terms_ja",
        "required_terms_en",
        "preferred_terms_ja",
        "preferred_terms_en",
        "negative_terms_ja",
        "negative_terms_en",
    ):
        for term in payload.get(field_name, []):
            assert term in getattr(intent, field_name)
            assert term not in prompt


@pytest.mark.parametrize(
    ("payload", "expected_group"),
    [
        (
            {
                "product_name_ja": "ヘッドホン",
                "price": {"mode": "max", "max_jpy": 50000},
            },
            "price",
        ),
        (
            {
                "product_name_ja": "ヘッドホン",
                "unexpected": "provider-value-must-not-leak",
            },
            "fields",
        ),
    ],
)
def test_compact_wire_rejects_malformed_sparse_fields_without_value_leakage(
    payload: dict[str, object],
    expected_group: str,
) -> None:
    with pytest.raises(BonsaiResponseContractError) as error:
        parse_bonsai_intent_response(
            source_input="ヘッドホン",
            prompt=PROMPT_BYTES,
            response=response_bytes(payload),
        )

    assert error.value.diagnostic.stage == "draft_schema_invalid"
    assert error.value.diagnostic.draft_failure_group == expected_group
    assert "provider-value-must-not-leak" not in str(error.value)
    assert "provider-value-must-not-leak" not in repr(error.value.diagnostic)
    assert error.value.__cause__ is None
    assert error.value.__context__ is None


def test_generation_schema_accepts_only_meaningful_present_values_in_compact_fixture() -> None:
    schema = json.loads(search_intent_generation_schema_bytes())
    validator = Draft202012Validator(schema)

    assert list(validator.iter_errors(compact_intent_payload())) == []
    assert list(validator.iter_errors(complete_intent_payload()))

    explicit_max = next(
        variant
        for variant in schema["$defs"]["BonsaiCompactPriceCondition"]["oneOf"]
        if variant["properties"]["mode"].get("const") == "max"
        and variant["properties"]["source"].get("const") == "explicit"
    )
    assert set(explicit_max["properties"]) == {"mode", "max_jpy", "source"}
    assert explicit_max["required"] == ["mode", "max_jpy", "source"]
    assert explicit_max["additionalProperties"] is False
    assert all(
        variant["properties"]["mode"].get("const") != "none"
        for variant in schema["$defs"]["BonsaiCompactPriceCondition"]["oneOf"]
    )

    searchable, blocking = schema["anyOf"]
    assert "product_name_ja" in searchable["required"]
    assert searchable["properties"]["product_name_ja"]["type"] == "string"
    assert "ambiguities" in blocking["required"]
    assert blocking["properties"]["ambiguities"]["minItems"] == 1


def test_generation_schema_structurally_bounds_strings_arrays_and_root_fields() -> None:
    schema = json.loads(search_intent_generation_schema_bytes())
    searchable, blocking = schema["anyOf"]
    searchable_fields = {
        "product_name_ja",
        "product_name_en",
        "required_terms_ja",
        "required_terms_en",
        "preferred_terms_ja",
        "preferred_terms_en",
        "negative_terms_ja",
        "negative_terms_en",
        "brand",
        "model_number",
        "price",
        "typed_conditions",
    }

    assert set(searchable["properties"]) == searchable_fields
    assert searchable["required"] == ["product_name_ja"]
    assert searchable["additionalProperties"] is False
    assert searchable["maxProperties"] == 12
    assert set(blocking["properties"]) == {"ambiguities"}
    assert blocking["required"] == ["ambiguities"]
    assert blocking["additionalProperties"] is False
    assert blocking["maxProperties"] == 1

    for field_name in ("product_name_ja", "product_name_en", "brand", "model_number"):
        assert searchable["properties"][field_name]["maxLength"] == 48
    for field_name in (
        "required_terms_ja",
        "required_terms_en",
        "preferred_terms_ja",
        "preferred_terms_en",
        "negative_terms_ja",
        "negative_terms_en",
    ):
        field = searchable["properties"][field_name]
        assert field["maxItems"] == 4
        assert field["items"]["maxLength"] == 32
    assert searchable["properties"]["typed_conditions"]["maxItems"] == 4
    assert blocking["properties"]["ambiguities"]["maxItems"] == 2

    ambiguity_ref = blocking["properties"]["ambiguities"]["items"]["$ref"]
    ambiguity = schema["$defs"][ambiguity_ref.rsplit("/", 1)[-1]]
    assert ambiguity["properties"]["message"]["maxLength"] == 96
    assert ambiguity["properties"]["blocking"] == {"const": True, "type": "boolean"}

    enum_values = schema["$defs"]["BonsaiCompactEnumTarget"]["properties"]["values"]
    text_values = schema["$defs"]["BonsaiCompactTextSetTarget"]["properties"]["values"]
    assert enum_values["maxItems"] == 4
    assert text_values["maxItems"] == 4
    assert text_values["items"]["maxLength"] == 32


def test_generation_schema_ties_typed_attribute_to_its_value_type() -> None:
    schema = json.loads(search_intent_generation_schema_bytes())
    validator = Draft202012Validator(schema)
    invalid = compact_intent_payload()
    invalid["typed_conditions"] = [
        {
            "attribute_key": "appearance.style",
            "operator": "similar_to",
            "expected_value": {"value_type": "text_set", "values": ["minimal"]},
            "strength": "preferred",
        }
    ]
    valid = compact_intent_payload()
    valid["typed_conditions"] = [
        {
            "attribute_key": "appearance.style",
            "operator": "similar_to",
            "expected_value": {"value_type": "semantic", "label": "minimal"},
            "strength": "preferred",
        }
    ]

    assert list(validator.iter_errors(invalid))
    assert list(validator.iter_errors(valid)) == []


def test_compact_adapter_rejects_typed_attribute_value_type_mismatch() -> None:
    payload = compact_intent_payload()
    payload["typed_conditions"] = [
        {
            "attribute_key": "appearance.style",
            "operator": "similar_to",
            "expected_value": {"value_type": "text_set", "values": ["minimal"]},
            "strength": "preferred",
        }
    ]

    with pytest.raises(BonsaiResponseContractError) as error:
        parse_bonsai_intent_response(
            source_input=SOURCE_INPUT,
            prompt=PROMPT_BYTES,
            response=response_bytes(payload),
        )

    assert error.value.diagnostic.stage == "draft_schema_invalid"
    assert error.value.diagnostic.draft_failure_group == "typed_conditions"


@pytest.mark.parametrize(
    ("mutation", "expected_group"),
    [
        ({"category_ja": "provider-value-must-not-leak"}, "fields"),
        ({"product_name_ja": "x" * 49}, "fields"),
        ({"required_terms_ja": ["a", "b", "c", "d", "e"]}, "fields"),
        (
            {
                "ambiguities": [
                    {
                        "code": "needs_confirmation",
                        "message": "provider-value-must-not-leak",
                        "blocking": True,
                    }
                ]
            },
            "document",
        ),
    ],
)
def test_compact_wire_rejects_out_of_profile_or_oversized_content(
    mutation: dict[str, object],
    expected_group: str,
) -> None:
    payload = {**compact_intent_payload(), **mutation}

    with pytest.raises(BonsaiResponseContractError) as error:
        parse_bonsai_intent_response(
            source_input=SOURCE_INPUT,
            prompt=PROMPT_BYTES,
            response=response_bytes(payload),
        )

    assert error.value.diagnostic.stage == "draft_schema_invalid"
    assert error.value.diagnostic.draft_failure_group == expected_group
    assert "provider-value-must-not-leak" not in str(error.value)
    assert "provider-value-must-not-leak" not in repr(error.value.diagnostic)


def oversized_nested_payload_cases() -> list[tuple[dict[str, object], str]]:
    compact = compact_intent_payload()
    typed = typed_color_condition()
    return [
        ({**compact, "required_terms_ja": ["x" * 33]}, "fields"),
        ({**compact, "typed_conditions": [typed] * 5}, "typed_conditions"),
        (
            {
                **compact,
                "typed_conditions": [
                    {
                        "attribute_key": "compatibility.models",
                        "operator": "contains_all",
                        "expected_value": {
                            "value_type": "text_set",
                            "values": ["a", "b", "c", "d", "e"],
                        },
                        "strength": "required",
                    }
                ],
            },
            "typed_conditions",
        ),
        (
            {
                "ambiguities": [
                    {
                        "code": f"needs_confirmation_{index}",
                        "message": "確認が必要です",
                        "blocking": True,
                    }
                    for index in range(3)
                ]
            },
            "ambiguities",
        ),
        (
            {
                "ambiguities": [
                    {
                        "code": "needs_confirmation",
                        "message": "x" * 97,
                        "blocking": True,
                    }
                ]
            },
            "ambiguities",
        ),
    ]


@pytest.mark.parametrize(("payload", "expected_group"), oversized_nested_payload_cases())
def test_compact_wire_rejects_each_nested_size_limit(
    payload: dict[str, object],
    expected_group: str,
) -> None:
    with pytest.raises(BonsaiResponseContractError) as error:
        parse_bonsai_intent_response(
            source_input=SOURCE_INPUT,
            prompt=PROMPT_BYTES,
            response=response_bytes(payload),
        )

    assert error.value.diagnostic.stage == "draft_schema_invalid"
    assert error.value.diagnostic.draft_failure_group == expected_group


def test_compact_fixture_is_minified_and_bounded_for_the_196_token_target() -> None:
    compact = json.dumps(
        compact_intent_payload(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    complete = json.dumps(
        complete_intent_payload(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    assert b"\n" not in compact
    assert b": " not in compact
    assert len(compact) <= 600
    assert len(compact) < len(complete)


def test_request_v9_binds_bounded_compact_schema_without_a_hard_generation_cap() -> None:
    prepared = build_bonsai_intent_request(
        SOURCE_INPUT,
        base_url="http://127.0.0.1:8080/v1",
        model_id="Bonsai-8B.gguf",
        temperature=0,
    )
    body = json.loads(prepared.body)
    prompt = load_bonsai_intent_prompt().decode()

    assert prepared.request.schema_version == "9.0"
    from src.search_v2.source_constraints import bind_generation_schema

    assert body["response_format"]["schema"] == json.loads(
        bind_generation_schema(SOURCE_INPUT, search_intent_generation_schema_bytes())
    )
    assert "max_tokens" not in body
    assert "省略" in prompt
    assert "minified" in prompt
    assert "196" not in prompt
    assert "product_name_jaを省略" in prompt
    assert "product_name_jaをnull" not in prompt
    assert "切断" in prompt
    assert "blocking" in prompt
    assert "翻訳のためだけ" in prompt
    assert "原子的な条件" in prompt
    assert "各条件を全て1回" in prompt
    assert "原文表記" in prompt
    assert "上下限関係" in prompt
    assert "否定・除外対象" in prompt
    assert "allowed valueへ一意" in prompt
    assert "白い" not in prompt
    assert "黒い" not in prompt
    assert "テンキー" not in prompt
    assert len(prompt.encode("utf-8")) <= 4_899


def test_dynamic_schema_keeps_the_fixed_request_body_below_17000_bytes() -> None:
    prepared = build_bonsai_intent_request(
        LATENCY_REGRESSION_INPUT,
        base_url="http://127.0.0.1:18080/v1",
        model_id="Bonsai-8B.gguf",
        temperature=0.0,
    )

    assert len(prepared.body) <= 17_000
