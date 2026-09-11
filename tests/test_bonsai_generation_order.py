"""The llama.cpp grammar uses property order, unlike JSON Schema validation."""

import json

from jsonschema import Draft202012Validator
import pytest

from src.search_v2.bonsai_adapter import search_intent_generation_schema_bytes
from src.search_v2.bonsai_request import build_bonsai_intent_request
from src.search_v2.bonsai_request import load_bonsai_intent_prompt
from test_bonsai_attribute_inference import candidate_payload


def strength_first_payload():
    payload = candidate_payload()
    for index, candidate in enumerate(payload["typed_conditions"]):
        if candidate["attribute_key"] == "custom":
            payload["typed_conditions"][index] = {
                key: candidate[key]
                for key in (
                    "attribute_key",
                    "attribute_definition",
                    "strength",
                    "operator",
                    "expected_value",
                )
            }
    return payload


def ordered_fields(value, schema, definitions):
    """Check required-then-optional order used by llama.cpp's object grammar."""
    if "$ref" in schema:
        schema = definitions[schema["$ref"].rsplit("/", 1)[-1]]
    for keyword in ("oneOf", "anyOf"):
        if keyword in schema:
            variants = [
                branch
                for branch in schema[keyword]
                if Draft202012Validator({**branch, "$defs": definitions}).is_valid(value)
            ]
            assert variants
            return any(ordered_fields(value, branch, definitions) for branch in variants)
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        order = [key for key in properties if key in required]
        order += [key for key in properties if key not in required and key in value]
        return list(value) == order and all(
            ordered_fields(item, properties[key], definitions) for key, item in value.items()
        )
    if isinstance(value, list):
        return all(ordered_fields(item, schema["items"], definitions) for item in value)
    return True


@pytest.mark.parametrize("sent", [False, True])
def test_attribute_key_can_select_custom_before_its_definition(sent):
    schema = json.loads(search_intent_generation_schema_bytes())
    if sent:
        prepared = build_bonsai_intent_request(
            "青いライト。点灯時間8時間以上。",
            base_url="http://127.0.0.1:18080/v1",
            model_id="Bonsai-8B.gguf",
            temperature=0.0,
        )
        schema = json.loads(prepared.body)["response_format"]["schema"]
    variants = (
        [value for key, value in schema["$defs"].items() if key.startswith("SourceFact")]
        if sent
        else schema["$defs"]["BonsaiCompactTypedConditionCandidate"]["oneOf"]
    )
    assert variants
    assert all(next(iter(branch["properties"])) == "attribute_key" for branch in variants)


@pytest.mark.parametrize("case", ["prompt_example", "numeric_and_boolean"])
def test_documented_outputs_follow_the_sent_grammar_order(case):
    if case == "prompt_example":
        prompt = load_bonsai_intent_prompt().decode()
        value = json.loads(
            next(line[4:] for line in prompt.splitlines() if line.startswith("出力: "))
        )
    else:
        value = strength_first_payload()
    request = build_bonsai_intent_request(
        "fixture",
        base_url="http://127.0.0.1:18080/v1",
        model_id="Bonsai-8B.gguf",
        temperature=0.0,
    )
    schema = json.loads(request.body)["response_format"]["schema"]
    Draft202012Validator(schema).validate(value)
    assert ordered_fields(value, schema, schema["$defs"])


@pytest.mark.parametrize(
    ("operator", "target"),
    [
        ("equals", {"value_type": "boolean", "value": True}),
        ("one_of", {"value_type": "enum", "values": ["fixture_a", "fixture_b"]}),
        ("at_most", {"value_type": "integer", "maximum": 8, "unit": "時間"}),
        ("between", {"value_type": "decimal", "minimum": "1.5", "maximum": "2", "unit": "kg"}),
        ("contains_all", {"value_type": "text_set", "values": ["fixture"]}),
    ],
)
def test_custom_target_types_keep_discriminator_first(operator, target):
    request = build_bonsai_intent_request(
        "fixture",
        base_url="http://127.0.0.1:18080/v1",
        model_id="Bonsai-8B.gguf",
        temperature=0.0,
    )
    schema = json.loads(request.body)["response_format"]["schema"]
    value = strength_first_payload()
    value["typed_conditions"] = [value["typed_conditions"][1]]
    candidate = value["typed_conditions"][0]
    candidate["operator"] = operator
    candidate["expected_value"] = target
    Draft202012Validator(schema).validate(value)
    assert ordered_fields(value, schema, schema["$defs"])
    sorted_value = json.loads(json.dumps(value, sort_keys=True))
    assert not ordered_fields(sorted_value, schema, schema["$defs"])
