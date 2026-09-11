"""Detect explicit specifications lost before a supposedly ready proposal."""

from copy import deepcopy

import pytest

from src.search_v2.bonsai_adapter import parse_bonsai_intent_response
from src.search_v2.bonsai_request import load_bonsai_intent_prompt
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from test_bonsai_attribute_inference import SOURCE, candidate_payload
from test_search_v2_bonsai_compact import response_bytes


def proposal(payload, source=SOURCE):
    intent = parse_bonsai_intent_response(
        source_input=source, prompt=load_bonsai_intent_prompt(), response=response_bytes(payload)
    )
    return build_typed_requirement_proposal(intent)


@pytest.mark.parametrize(
    "payload",
    [
        {"product_name_ja": "マグカップ"},
        {"product_name_ja": "白いマグカップ", "required_terms_ja": ["350ml以上", "食洗機対応"]},
        {"product_name_ja": "白いマグカップ。350ml以上で、食洗機対応。"},
    ],
)
def test_missing_numeric_specification_never_becomes_ready(payload):
    assert proposal(payload).status == "blocking"


def test_plausible_inferred_specs_still_require_identity_review():
    assert proposal(candidate_payload()).status == "blocking"


def test_product_name_cannot_absorb_a_second_condition_sentence():
    assert (
        proposal({"product_name_ja": "マグカップ。食洗機対応"}, "マグカップ。食洗機対応").status
        == "blocking"
    )


def test_unit_bound_guard_is_not_a_capacity_preset():
    source = "点灯時間8時間以上のライト"
    assert (
        proposal(
            {"product_name_ja": "ライト", "required_terms_ja": ["点灯時間8時間以上"]}, source
        ).status
        == "blocking"
    )


def test_price_comparison_without_product_specs_is_still_searchable():
    assert proposal({"product_name_ja": "マグカップ"}, "5000円以下のマグカップ").status == "ready"


def test_other_quantity_does_not_cover_the_missing_capacity():
    payload = deepcopy(candidate_payload())
    payload["typed_conditions"][1]["attribute_definition"].update(
        label="重量", meaning="商品の重量", source_quote="重量350g以上"
    )
    payload["typed_conditions"][1]["expected_value"]["unit"] = "g"
    assert proposal(payload, SOURCE + "重量350g以上。").status == "blocking"


def test_numeric_specification_cannot_be_hidden_in_a_custom_enum():
    payload = deepcopy(candidate_payload())
    capacity = payload["typed_conditions"][1]
    capacity["operator"] = "equals"
    capacity["expected_value"] = {"value_type": "enum", "values": ["350ml以上"]}
    assert proposal(payload).status == "blocking"


def test_common_width_range_remains_ready():
    payload = {
        "product_name_ja": "ケース",
        "typed_conditions": [
            {
                "attribute_key": "dimensions.width",
                "operator": "between",
                "expected_value": {
                    "value_type": "decimal",
                    "minimum": "100",
                    "maximum": "120",
                    "unit": "mm",
                },
                "strength": "required",
            }
        ],
    }
    assert proposal(payload, "幅100 mm以上120 mm以下のケース").status == "ready"
