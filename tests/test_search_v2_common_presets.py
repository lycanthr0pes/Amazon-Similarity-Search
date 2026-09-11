"""Category specifications are proposed per search, never preset by the backend."""

import json

from jsonschema import Draft202012Validator
import pytest

from src.search_v2.bonsai_adapter import BonsaiResponseContractError
from src.search_v2.bonsai_adapter import parse_bonsai_intent_response
from src.search_v2.bonsai_adapter import search_intent_generation_schema_bytes
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_ranking import rank_typed_product_batch
from src.search_v2.typed_requirements import DEFAULT_ATTRIBUTE_REGISTRY
from test_search_v2_bonsai_compact import response_bytes
from test_search_v2_dynamic_attributes import parse_conditions
from test_search_v2_typed_ranking import ranking_inputs


def test_presets_only_describe_common_physical_and_appearance_attributes():
    assert {d.attribute_key for d in DEFAULT_ATTRIBUTE_REGISTRY.definitions} == {
        "appearance.color",
        "appearance.style",
        "dimensions.width",
        "form.shape",
        "form.orientation",
        "material.type",
    }


@pytest.mark.parametrize(
    "key, value",
    [
        ("mouse.connection", {"value_type": "enum", "values": ["wireless"]}),
        ("power.rechargeable", {"value_type": "boolean", "value": True}),
        (
            "storage.compartment_count",
            {"value_type": "integer", "minimum": 2, "maximum": 2, "unit": "count"},
        ),
        ("compatibility.models", {"value_type": "text_set", "values": ["Model-A"]}),
        ("form.factor", {"value_type": "enum", "values": ["desktop"]}),
    ],
)
def test_removed_presets_are_rejected_by_wire_schema_and_adapter(key, value):
    payload = {
        "product_name_ja": "マウス",
        "typed_conditions": [
            {
                "attribute_key": key,
                "operator": "equals",
                "expected_value": value,
                "strength": "required",
            }
        ],
    }
    assert not Draft202012Validator(json.loads(search_intent_generation_schema_bytes())).is_valid(
        payload
    )
    with pytest.raises(BonsaiResponseContractError):
        parse_bonsai_intent_response(
            source_input="無線で充電式、収納口数2個、Model-A対応の卓上マウス",
            prompt=b"synthetic-common-presets",
            response=response_bytes(payload),
        )


@pytest.mark.parametrize(
    "label, quote, value, yes, no, operator",
    [
        (
            "マウス接続方式",
            "マウス接続方式は無線",
            {"value_type": "enum", "values": ["無線"]},
            "無線",
            "有線",
            "equals",
        ),
        ("充電式", "充電式", {"value_type": "boolean", "value": True}, "はい", "いいえ", "equals"),
        (
            "収納口数",
            "収納口数2個以上",
            {"value_type": "integer", "minimum": 2, "unit": "個"},
            "3個",
            "1個",
            "at_least",
        ),
        (
            "対応モデル",
            "対応モデルはModel-A",
            {"value_type": "text_set", "values": ["Model-A"]},
            "Model-A",
            "Model-B",
            "compatible_with",
        ),
        (
            "設置方法",
            "設置方法は卓上",
            {"value_type": "enum", "values": ["卓上"]},
            "卓上",
            "壁掛け",
            "equals",
        ),
    ],
)
def test_category_specification_is_inferred_and_used_in_ranking(
    label, quote, value, yes, no, operator
):
    candidate = {
        "attribute_key": "custom",
        "attribute_definition": {
            "label": label,
            "meaning": label + "の仕様",
            "source_quote": quote,
        },
        "operator": operator,
        "expected_value": value,
        "strength": "required",
    }
    intent = parse_conditions([candidate], source=quote + "のマグカップ")
    proposal = build_typed_requirement_proposal(intent)
    assert proposal.status == "ready"
    assert proposal.requirements[0].attribute_key.startswith("search.")
    rows = [
        {"name": "マグカップ", "asin": "B000CP0001", "features": [label + ": " + yes]},
        {"name": "マグカップ", "asin": "B000CP0002", "features": [label + ": " + no]},
        {"name": "マグカップ", "asin": "B000CP0003"},
    ]
    ranked = rank_typed_product_batch(*ranking_inputs(rows, intent=intent))
    assert [p.evaluation.required_status for p in ranked.products] == [
        "confirmed",
        "uncertain",
        "contradicted",
    ]


def test_shape_preset_is_geometric_instead_of_a_device_form_factor():
    intent = parse_conditions(
        [
            {
                "attribute_key": "form.shape",
                "operator": "equals",
                "expected_value": {"value_type": "enum", "values": ["cylindrical"]},
                "strength": "required",
            }
        ],
        source="円筒形のマグカップ",
    )
    ranked = rank_typed_product_batch(
        *ranking_inputs(
            [
                {"name": "円筒形 マグカップ", "asin": "B000CP0001", "features": ["円筒形"]},
                {"name": "長方形 マグカップ", "asin": "B000CP0002", "features": ["長方形"]},
            ],
            intent=intent,
        )
    )
    assert [p.evaluation.required_status for p in ranked.products] == ["confirmed", "contradicted"]


@pytest.mark.parametrize(
    "label, quote, value, operator",
    [
        ("接続方式", "無線", {"value_type": "enum", "values": ["無線"]}, "equals"),
        (
            "内容量",
            "350ml以上",
            {"value_type": "decimal", "minimum": "350", "unit": "ml"},
            "at_least",
        ),
        ("充電対応", "充電できる", {"value_type": "boolean", "value": True}, "equals"),
    ],
)
def test_inferred_numeric_name_is_a_review_candidate(label, quote, value, operator):
    intent = parse_conditions(
        [
            {
                "attribute_key": "custom",
                "attribute_definition": {
                    "label": label,
                    "meaning": label + "の仕様",
                    "source_quote": quote,
                },
                "operator": operator,
                "expected_value": value,
                "strength": "required",
            }
        ],
        source=quote + "のマグカップ",
    )
    proposal = build_typed_requirement_proposal(intent)
    numeric = value["value_type"] in {"integer", "decimal"}
    assert proposal.status == ("blocking" if numeric else "ready")
    assert len(proposal.requirements) == (0 if numeric else 1)
    assert intent.typed_conditions[0].attribute_definition.label == label


def test_negated_geometric_shape_is_not_positive_evidence():
    intent = parse_conditions(
        [
            {
                "attribute_key": "form.shape",
                "operator": "equals",
                "expected_value": {"value_type": "enum", "values": ["round"]},
                "strength": "required",
            }
        ],
        source="丸形のマグカップ",
    )
    ranked = rank_typed_product_batch(
        *ranking_inputs([{"name": "丸形ではないマグカップ", "asin": "B000CP0001"}], intent=intent)
    )
    assert ranked.products[0].evaluation.required_status == "uncertain"
