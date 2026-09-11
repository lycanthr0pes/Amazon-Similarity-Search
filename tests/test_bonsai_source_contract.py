"""Facts stated by the user must be immutable before and after model generation."""

from copy import deepcopy
import json

from jsonschema import Draft202012Validator
import pytest

from src.search_v2.bonsai_request import build_bonsai_intent_request


SOURCE = "品物。重量2kg以下。USB接続対応を希望。無線LAN対応は除外。"


def schema_for(source):
    request = build_bonsai_intent_request(
        source, base_url="http://127.0.0.1:18080/v1", model_id="Bonsai-8B.gguf", temperature=0.0
    )
    return json.loads(request.body)["response_format"]["schema"]


def condition(label, quote, value, strength="required", operator="equals"):
    meaning = f"{label}を表す数量（単位{value['unit']}）" if "unit" in value else f"{label}の可否"
    return {
        "attribute_key": "custom",
        "attribute_definition": {"label": label, "meaning": meaning, "source_quote": quote},
        "strength": strength,
        "operator": operator,
        "expected_value": value,
    }


def payload():
    return {
        "product_name_ja": "品物",
        "typed_conditions": [
            condition(
                "重量",
                "重量2kg以下",
                {"value_type": "integer", "maximum": 2, "unit": "kg"},
                operator="at_most",
            ),
            condition(
                "usb接続対応",
                "usb接続対応を希望",
                {"value_type": "boolean", "value": True},
                "preferred",
            ),
            condition(
                "無線lan対応",
                "無線lan対応は除外",
                {"value_type": "boolean", "value": True},
                "excluded",
            ),
        ],
    }


@pytest.mark.parametrize(
    "mutation", ["number", "unit", "strength", "polarity", "missing", "meaning", "key"]
)
def test_decoder_cannot_change_explicit_facts(mutation):
    validator = Draft202012Validator(schema_for(SOURCE))
    expected = payload()
    assert validator.is_valid(expected)
    wrong = deepcopy(expected)
    conditions = wrong["typed_conditions"]
    if mutation == "number":
        conditions[0]["expected_value"]["maximum"] = 2000
    elif mutation == "unit":
        conditions[0]["expected_value"]["unit"] = "g"
    elif mutation == "strength":
        conditions[1]["strength"] = "required"
    elif mutation == "polarity":
        conditions[2]["expected_value"]["value"] = False
    elif mutation == "missing":
        conditions.pop()
    elif mutation == "meaning":
        conditions[0]["attribute_definition"]["meaning"] = "商品の価格"
    else:
        conditions[0] = {
            "attribute_key": "dimensions.width",
            "operator": "at_most",
            "strength": "required",
            "expected_value": {"value_type": "decimal", "maximum": "2", "unit": "mm"},
        }
    assert not validator.is_valid(wrong)


def test_request_schema_is_bound_to_its_source_values():
    assert not Draft202012Validator(schema_for(SOURCE.replace("2kg", "7kg"))).is_valid(payload())


def name_response(label="倍率"):
    return {"product_name_ja": "品物", "attribute_names_ja": [label]}


def test_model_only_supplies_names_and_cannot_return_quantity_fields():
    validator = Draft202012Validator(schema_for("品物。40倍以上。"))
    value = name_response()
    assert validator.is_valid(value)
    value["expected_value"] = {"minimum": 400, "unit": "mm"}
    assert not validator.is_valid(value)


def test_inferred_names_are_joined_with_source_facts_and_deterministic_definitions():
    from src.search_v2.source_constraints import expand_source_names

    value = expand_source_names("品物。40倍以上。接続対応を希望。", name_response())
    conditions = value["typed_conditions"]
    assert conditions[0]["expected_value"] == {"value_type": "integer", "minimum": 40, "unit": "倍"}
    assert conditions[0]["attribute_definition"] == {
        "label": "倍率",
        "meaning": "倍率を表す数量（単位倍）",
        "source_quote": "40倍以上",
    }
    assert conditions[1]["strength"] == "preferred"
    assert conditions[1]["expected_value"] == {"value_type": "boolean", "value": True}


@pytest.mark.parametrize(
    "name", ["倍", "40倍", "40倍以上", "倍以上", "倍上限", "品物", "倍率\n", 4, None]
)
def test_invalid_names_do_not_turn_into_ready_conditions(name):
    from src.search_v2.source_constraints import expand_source_names

    with pytest.raises(ValueError):
        expand_source_names("品物。40倍以上。", name_response(name))


def test_missing_property_uses_a_distinct_digest_bound_inference_task():
    import hashlib

    from src.search_v2.bonsai_request import load_bonsai_intent_prompt

    request = build_bonsai_intent_request(
        "品物。40倍以上。",
        base_url="http://127.0.0.1:18080/v1",
        model_id="Bonsai-8B.gguf",
        temperature=0.0,
    )
    assert request.prompt != load_bonsai_intent_prompt()
    assert "attribute_names_ja" in request.prompt.decode()
    assert request.request.prompt_sha256 == hashlib.sha256(request.prompt).hexdigest()
    assert json.loads(request.body)["messages"][0]["content"] == request.prompt.decode()
    task = json.loads(json.loads(request.body)["messages"][1]["content"])
    assert task == {
        "source_input": "品物。40倍以上。",
        "unnamed_quantities": [{"source_quote": "40倍以上", "unit": "倍"}],
    }


def test_name_only_wire_passes_the_application_boundary_and_binds_runtime_prompt():
    from dataclasses import replace
    from src.exceptions import BonsaiRequestError
    from src.search_v2.bonsai_request import load_bonsai_intent_prompt
    from test_search_v2_bonsai_request import RecordingTransport, execute, http_response

    prepared = build_bonsai_intent_request(
        "品物。40倍以上。",
        base_url="http://127.0.0.1:18080/v1",
        model_id="Bonsai-8B.gguf",
        temperature=0.0,
    )
    body = json.dumps({"choices": [{"message": {"content": json.dumps(name_response())}}]}).encode()
    transport = RecordingTransport(http_response(body))
    result, _ = execute(prepared, transport)
    assert (
        result.intent.typed_conditions[0].attribute_definition.meaning == "倍率を表す数量（単位倍）"
    )
    assert len(transport.calls) == 1
    wrong = replace(prepared, prompt=load_bonsai_intent_prompt())
    unused = RecordingTransport(http_response(body))
    with pytest.raises(BonsaiRequestError):
        execute(wrong, unused)
    assert not unused.calls


@pytest.mark.parametrize("unit,label", [("倍", "倍"), ("v", "V"), ("lm", "LM")])
def test_unit_names_and_case_variants_are_not_property_names(unit, label):
    validator = Draft202012Validator(schema_for(f"品物。12{unit}以上。"))
    assert not validator.is_valid(name_response(label))


@pytest.mark.parametrize("label", ['倍"', "倍\\", "倍\n", '"', "\x00"])
def test_inferred_names_cannot_escape_decoder_json_strings(label):
    assert not Draft202012Validator(schema_for("品物。40倍以上。")).is_valid(name_response(label))


def test_large_source_integer_uses_lossless_decimal_wire():
    validator = Draft202012Validator(schema_for("品物。測定値2000000000000qz以下。"))
    value = {
        "product_name_ja": "品物",
        "typed_conditions": [
            condition(
                "測定値",
                "測定値2000000000000qz以下",
                {"value_type": "decimal", "maximum": "2000000000000", "unit": "qz"},
                operator="at_most",
            )
        ],
    }
    assert validator.is_valid(value)


def test_unresolved_alternative_cannot_become_a_conjunction():
    source = "品物。重量2kg以下または容量3L以上。"
    assert not Draft202012Validator(schema_for(source)).is_valid({"product_name_ja": "品物"})


def test_common_attributes_cannot_be_fabricated_or_omitted():
    validator = Draft202012Validator(schema_for("青い品物。重量2kg以下。"))
    value = {
        "product_name_ja": "品物",
        "typed_conditions": [
            payload()["typed_conditions"][0],
            {
                "attribute_key": "appearance.color",
                "strength": "required",
                "operator": "equals",
                "expected_value": {"value_type": "enum", "values": ["blue"]},
            },
        ],
    }
    assert validator.is_valid(value)
    value["typed_conditions"][-1]["expected_value"]["values"] = ["black"]
    assert not validator.is_valid(value)
    value["typed_conditions"].pop()
    assert not validator.is_valid(value)


@pytest.mark.parametrize("mutation", ["number", "missing", "definition"])
def test_application_rejects_a_provider_ignoring_the_source_schema(mutation):
    from src.search_v2.source_constraints import validate_source_response

    value = payload()
    if mutation == "number":
        value["typed_conditions"][0]["expected_value"]["maximum"] = 2000
    elif mutation == "missing":
        value["typed_conditions"].pop()
    else:
        value["typed_conditions"][0]["attribute_definition"]["meaning"] = "商品の価格"
    response = json.dumps({"choices": [{"message": {"content": json.dumps(value)}}]}).encode()
    with pytest.raises(ValueError):
        validate_source_response(SOURCE, response)


@pytest.mark.parametrize("amount,unit", [(7, "qz"), (-5, "°c"), (349, "枚")])
@pytest.mark.parametrize(
    "strength,suffix", [("required", ""), ("preferred", "を希望"), ("excluded", "は除外")]
)
def test_source_binding_does_not_depend_on_category_or_numeric_magnitude(
    amount, unit, strength, suffix
):
    source = f"未登録商品。測定値{amount}{unit}以下{suffix}。"
    value = {
        "product_name_ja": "未登録商品",
        "typed_conditions": [
            condition(
                "測定値",
                f"測定値{amount}{unit}以下{suffix}",
                {"value_type": "integer", "maximum": amount, "unit": unit},
                strength,
                "at_most",
            )
        ],
    }
    validator = Draft202012Validator(schema_for(source))
    assert validator.is_valid(value)
    value["typed_conditions"][0]["expected_value"]["maximum"] = amount + 1
    assert not validator.is_valid(value)


def test_shared_color_alias_does_not_match_inside_a_product_word():
    validator = Draft202012Validator(schema_for("白鳥観察用品。重量2kg以下。"))
    value = {"product_name_ja": "観察用品", "typed_conditions": [payload()["typed_conditions"][0]]}
    assert validator.is_valid(value)
    value["typed_conditions"].append(
        {
            "attribute_key": "appearance.color",
            "strength": "required",
            "operator": "equals",
            "expected_value": {"value_type": "enum", "values": ["white"]},
        }
    )
    assert not validator.is_valid(value)


def test_unresolved_scope_requires_blocking_instead_of_a_guessed_label():
    validator = Draft202012Validator(schema_for("品物。重量2kg以下か3kg以上。"))
    assert not validator.is_valid({"product_name_ja": "品物"})
    assert validator.is_valid(
        {
            "ambiguities": [
                {
                    "code": "scope_unknown",
                    "message": "条件の関係を確認してください",
                    "blocking": True,
                }
            ]
        }
    )


@pytest.mark.parametrize("tail", ["耐熱仕様", "取り外せる部品", "測定値2qz未満"])
def test_unparsed_specification_is_not_silently_removed(tail):
    validator = Draft202012Validator(schema_for(f"品物。重量2kg以下。{tail}。"))
    value = {"product_name_ja": "品物", "typed_conditions": [payload()["typed_conditions"][0]]}
    assert not validator.is_valid(value)


def test_product_noun_can_follow_bound_specifications():
    value = {
        "product_name_ja": "品物",
        "typed_conditions": [
            condition(
                "重量",
                "重量2kg以下",
                {
                    "value_type": "integer",
                    "maximum": 2,
                    "unit": "kg",
                },
                operator="at_most",
            ),
            condition("接続対応", "接続対応", {"value_type": "boolean", "value": True}),
        ],
    }
    assert Draft202012Validator(schema_for("重量2kg以下で接続対応の品物")).is_valid(value)


def test_received_fact_violation_marks_usage_failed_without_retry():
    from src.exceptions import BonsaiResponseError
    from test_search_v2_bonsai_request import (
        RecordingTransport,
        execute,
        http_response,
        prepared_request,
    )

    value = {
        "product_name_ja": "ヘッドホン",
        "typed_conditions": [
            {
                "attribute_key": "appearance.color",
                "operator": "equals",
                "strength": "required",
                "expected_value": {"value_type": "enum", "values": ["white"]},
            }
        ],
    }
    response = json.dumps({"choices": [{"message": {"content": json.dumps(value)}}]}).encode()
    transport = RecordingTransport(http_response(response))
    from test_search_v2_bonsai_request import reserved_usage

    request = prepared_request()
    ledger, reservation = reserved_usage(request)
    with pytest.raises(BonsaiResponseError, match="source constraints"):
        execute(request, transport, ledger=ledger, reservation=reservation)
    assert len(transport.calls) == 1
    assert ledger.snapshot().reservations[0].status == "failed"
