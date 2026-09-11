"""Specification labels must retain their language and source fact type."""

import pytest

from src.search_v2.source_constraints import expand_source_names


@pytest.mark.parametrize("modifier", ["急速", "簡易", "柔軟"])
def test_adjectival_noun_modifier_preserves_a_capability(modifier):
    from src.search_v2.source_constraints import needs_attribute_name_inference

    source = f"品物。3qz以上。{modifier}接続対応を希望。"
    assert needs_attribute_name_inference(source)
    value = expand_source_names(source, response("測定量"))
    capability = value["typed_conditions"][1]
    assert capability["attribute_definition"]["label"] == f"{modifier}接続対応"
    assert capability["expected_value"] == {"value_type": "boolean", "value": True}
    assert capability["strength"] == "preferred"


@pytest.mark.parametrize("clause", ["接続ができる", "接続しない", "急速か安全な接続対応"])
def test_sentence_or_unresolved_modifier_scope_is_not_an_explicit_name(clause):
    from src.search_v2.source_constraints import _name_is_explicit

    assert not _name_is_explicit(clause)


def response(name):
    return {"product_name_ja": "品物", "attribute_names_ja": [name]}


@pytest.mark.parametrize("unit", ["qz", "倍", "l/日", "単位", "Ω"])
@pytest.mark.parametrize("name", ["resolution", "dots_per_inch", "12345", "αβγ"])
def test_decoder_rejects_names_without_japanese_characters(unit, name):
    from jsonschema import Draft202012Validator
    from test_bonsai_source_contract import schema_for

    assert not Draft202012Validator(schema_for(f"品物。3{unit}以上。")).is_valid(response(name))


@pytest.mark.parametrize("position", [0, 1, 32, 99])
def test_decoder_and_application_preserve_the_full_name_length_boundary(position):
    from jsonschema import Draft202012Validator
    from test_bonsai_source_contract import schema_for

    validator = Draft202012Validator(schema_for("品物。3qz以上。"))
    name = "A" * position + "量" + "B" * (99 - position)
    assert validator.is_valid(response(name))
    assert expand_source_names("品物。3qz以上。", response(name))
    assert not validator.is_valid(response(name + "C"))


@pytest.mark.parametrize("unit", ["倍", "l/日", "単位", "qz", "Ω/日", "Д/日"])
def test_japanese_unit_and_its_case_variants_remain_excluded(unit):
    from jsonschema import Draft202012Validator
    from test_bonsai_source_contract import schema_for

    validator = Draft202012Validator(schema_for(f"品物。3{unit}以上。"))
    assert not validator.is_valid(response(unit))
    assert not validator.is_valid(response(unit.upper()))
    assert validator.is_valid(response(unit + "測定量"))


@pytest.mark.parametrize("name", ["接続対応", "接続", "CONNECT対応", "connect"])
def test_numeric_name_cannot_reuse_a_known_boolean_property(name):
    with pytest.raises(ValueError):
        expand_source_names("品物。3qz以上。接続対応。CONNECT対応を希望。", response(name))


@pytest.mark.parametrize("name", ["resolution", " dots_per_inch", "qz quantity"])
def test_inferred_japanese_name_cannot_be_an_english_unit_or_description(name):
    with pytest.raises(ValueError):
        expand_source_names("品物。3qz以上。", response(name))


@pytest.mark.parametrize("name", ["USB転送速度", "容量", "かたさ", "サイズ"])
def test_japanese_names_can_include_latin_abbreviations(name):
    result = expand_source_names("品物。3qz以上。", response(name))
    assert result["typed_conditions"][0]["attribute_definition"]["label"] == name


def test_numeric_name_can_reuse_an_explicit_numeric_property_for_another_bound():
    result = expand_source_names("品物。容量3L以上。5L以下。", response("容量"))
    assert [c["attribute_definition"]["label"] for c in result["typed_conditions"]] == [
        "容量",
        "容量",
    ]


@pytest.mark.parametrize("name", ["接続対応", "resolution"])
def test_invalid_names_fail_the_request_without_retry(name):
    import json

    from src.exceptions import BonsaiResponseError
    from src.search_v2.bonsai_request import build_bonsai_intent_request
    from test_search_v2_bonsai_request import (
        RecordingTransport,
        execute,
        http_response,
        reserved_usage,
    )

    prepared = build_bonsai_intent_request(
        "品物。3qz以上。接続対応。",
        base_url="http://127.0.0.1:18080/v1",
        model_id="Bonsai-8B.gguf",
        temperature=0.0,
    )
    body = json.dumps({"choices": [{"message": {"content": json.dumps(response(name))}}]}).encode()
    transport = RecordingTransport(http_response(body))
    ledger, reservation = reserved_usage(prepared)
    with pytest.raises(BonsaiResponseError):
        execute(prepared, transport, ledger=ledger, reservation=reservation)
    assert len(transport.calls) == 1
    assert ledger.snapshot().reservations[0].status == "failed"
