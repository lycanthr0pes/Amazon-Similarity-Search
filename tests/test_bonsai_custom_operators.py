"""Custom conditions must pair their value type with a supported operator."""

import json

from jsonschema import Draft202012Validator
import pytest

from src.search_v2.bonsai_adapter import search_intent_generation_schema_bytes
from test_bonsai_attribute_inference import candidate_payload


@pytest.mark.parametrize(
    ("target", "operator"),
    [
        ({"value_type": "boolean", "value": True}, "contains_all"),
        ({"value_type": "boolean", "value": True}, "at_least"),
        ({"value_type": "enum", "values": ["fixture"]}, "contains_all"),
        ({"value_type": "integer", "minimum": 8, "unit": "時間"}, "one_of"),
        ({"value_type": "decimal", "minimum": "8", "unit": "時間"}, "compatible_with"),
        ({"value_type": "text_set", "values": ["fixture"]}, "between"),
        ({"value_type": "semantic", "label": "minimal"}, "similar_to"),
    ],
)
def test_generation_refuses_unsupported_custom_pair(target, operator):
    payload = candidate_payload()
    candidate = payload["typed_conditions"][-1]
    candidate["expected_value"] = target
    candidate["operator"] = operator
    validator = Draft202012Validator(json.loads(search_intent_generation_schema_bytes()))
    assert not validator.is_valid(payload)


@pytest.mark.parametrize("strength", ["required", "preferred", "excluded"])
def test_boolean_equality_keeps_all_source_dependent_strengths(strength):
    payload = candidate_payload()
    payload["typed_conditions"][-1]["strength"] = strength
    validator = Draft202012Validator(json.loads(search_intent_generation_schema_bytes()))
    validator.validate(payload)


def test_mixed_strength_prompt_example_survives_source_grounding():
    from src.search_v2.bonsai_adapter import parse_bonsai_intent_response
    from src.search_v2.bonsai_request import load_bonsai_intent_prompt
    from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
    from test_search_v2_bonsai_compact import response_bytes

    prompt = load_bonsai_intent_prompt()
    lines = prompt.decode().splitlines()
    source = next(line[4:] for line in lines if line.startswith("入力: "))
    payload = json.loads(next(line[4:] for line in lines if line.startswith("出力: ")))
    intent = parse_bonsai_intent_response(
        source_input=source, prompt=prompt, response=response_bytes(payload)
    )
    proposal = build_typed_requirement_proposal(intent)
    assert proposal.status == "ready"
    assert len(proposal.requirements) == 4
    custom = [c for c in intent.typed_conditions if c.attribute_key == "custom"]
    assert {c.expected_value.value_type for c in custom} == {"integer", "boolean"}
    assert {c.strength for c in custom} == {"required", "preferred", "excluded"}
