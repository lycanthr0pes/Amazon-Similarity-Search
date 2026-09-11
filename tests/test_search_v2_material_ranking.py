"""Synthetic regression for material requirements and clay color ambiguity."""

import json

import pytest

from src.search_v2.bonsai_adapter import parse_bonsai_intent_response
from src.search_v2.bonsai_adapter import search_intent_generation_schema_bytes
from src.search_v2.product_evidence import ProductEvidenceAdapterProfile
from src.search_v2.product_evidence import build_product_evidence
from src.search_v2.provisional_counterfactual import build_provisional_counterfactual_batch
from src.search_v2.provisional_typed_ranking import rank_provisional_typed_product_batch
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_ranking import rank_typed_product_batch
from test_search_v2_bonsai_compact import response_bytes
from test_search_v2_product_evidence import decide, observed, product, requirement
from test_search_v2_provisional_typed_ranking import image_score
from test_search_v2_typed_ranking import ranking_inputs


def material_condition(value="earthenware", strength="required"):
    return {
        "attribute_key": "material.type",
        "operator": "equals",
        "expected_value": {"value_type": "enum", "values": [value]},
        "strength": strength,
    }


def mug_intent(**overrides):
    payload = {
        "product_name_ja": "マグカップ",
        "typed_conditions": [
            material_condition(),
            {**material_condition("white"), "attribute_key": "appearance.color"},
        ],
    }
    payload.update(overrides)
    return parse_bonsai_intent_response(
        source_input="白い陶器製マグカップ",
        prompt=b"synthetic-material-regression",
        response=response_bytes(payload),
    )


@pytest.mark.parametrize(
    "title, colors",
    [
        ("Red Soil Mug White", ("white",)),
        ("red-clay Mug White", ("white",)),
        ("White Clay Mug Blue", ("blue",)),
        ("Black Clay Mug White", ("white",)),
        ("赤土 マグカップ ホワイト", ("white",)),
        ("Red Soil Mug", ()),
        ("Red Mug White", ("red", "white")),
        ("Red Mug", ("red",)),
        ("Red Clay Mug Red", ("red",)),
    ],
)
def test_clay_descriptor_is_not_a_product_color(title, colors):
    selected = requirement(
        attribute_key="appearance.color",
        expected_value={"value_type": "enum", "values": ("white",)},
    )
    evidence = build_product_evidence(product(title=title), (selected,))
    assert (
        tuple(x.observed_value.value for x in observed(evidence, selected, "title_exact")) == colors
    )


@pytest.mark.parametrize(
    "material, title, state",
    [
        ("陶器", "Plain Mug", "match"),
        ("Pottery", "Plain Mug", "unknown"),
        ("Porcelain", "Earthenware Mug", "mismatch"),
        ("磁器", "Plain Mug", "mismatch"),
        ("Bone China", "Plain Mug", "mismatch"),
        ("Stoneware", "Plain Mug", "mismatch"),
        ("Glass", "Plain Mug", "mismatch"),
        (None, "Earthenware Mug", "match"),
        (None, "陶器製 マグカップ", "match"),
        (None, "Porcelain Mug", "mismatch"),
        (None, "Ceramic Mug", "unknown"),
        ("Ceramic", "Plain Mug", "unknown"),
        (None, "Mino Ware Mug", "unknown"),
        (None, "Earthenware Porcelain Mug", "conflict"),
        (None, "Non-earthenware Mug", "unknown"),
        (None, "陶器ではない マグカップ", "unknown"),
        (None, "陶器製ではない ガラス製 マグカップ", "mismatch"),
        (None, "Porcelain-like Plastic Mug", "mismatch"),
    ],
)
def test_material_evidence_requires_an_observed_material(material, title, state):
    selected = requirement(
        attribute_key="material.type",
        expected_value={"value_type": "enum", "values": ("earthenware",)},
    )
    candidate = product(
        title=title, material=material, description="Earthenware", features=("陶器",)
    )
    evidence = build_product_evidence(candidate, (selected,))
    assert decide(evidence, selected).state == state
    if material is None:
        structured = [x for x in evidence.observations if x.source == "structured"]
        assert structured[0].unknown_reason == "source_missing"


def test_material_wire_contract_and_source_grounding():
    from jsonschema import Draft202012Validator

    schema = json.loads(search_intent_generation_schema_bytes())
    Draft202012Validator(schema).validate(
        {"product_name_ja": "マグカップ", "typed_conditions": [material_condition()]}
    )
    intent = mug_intent()
    proposal = build_typed_requirement_proposal(intent)
    assert proposal.status == "ready"
    assert {(x.attribute_key, x.strength) for x in proposal.requirements} == {
        ("material.type", "required"),
        ("appearance.color", "required"),
    }


@pytest.mark.parametrize(
    "strength, field",
    [
        ("required", "required_terms_ja"),
        ("preferred", "preferred_terms_ja"),
        ("excluded", "negative_terms_ja"),
    ],
)
def test_material_term_becomes_a_typed_condition(strength, field):
    intent = mug_intent(typed_conditions=[], **{field: ["陶器製"]})
    proposal = build_typed_requirement_proposal(intent)
    assert proposal.status == "ready"
    assert [
        (x.attribute_key, x.strength, x.expected_value.values) for x in proposal.requirements
    ] == [("material.type", strength, ("earthenware",))]


def test_omitted_material_cannot_silently_become_a_ready_intent():
    intent = mug_intent(typed_conditions=[])
    assert intent.has_blocking_ambiguity


@pytest.mark.parametrize("value", ["ceramic", "pottery", "陶磁器", "セラミック"])
def test_broad_material_cannot_be_asserted_as_earthenware(value):
    intent = parse_bonsai_intent_response(
        source_input=f"{value} マグカップ",
        prompt=b"synthetic-material-regression",
        response=response_bytes({"product_name_ja": "マグカップ", "required_terms_ja": [value]}),
    )
    assert intent.has_blocking_ambiguity


def test_existing_material_condition_is_not_duplicated_by_a_term():
    intent = mug_intent(required_terms_ja=["陶器製"])
    assert len(build_typed_requirement_proposal(intent).requirements) == 2


def test_evidence_profile_rejects_the_old_parser_version():
    with pytest.raises(ValueError):
        ProductEvidenceAdapterProfile.model_validate(
            {
                "schema_version": "1.0",
                "profile_id": "bounded-product-evidence-v1",
                "structured_parser_version": "observed-structured-value-v1",
                "title_parser_version": "bounded-title-exact-v1",
                "maximum_matches_per_source": 8,
            }
        )


def test_material_mismatch_cannot_outrank_a_match_with_image_score():
    intent = mug_intent()
    items = [
        {
            "name": "White Porcelain Mug",
            "asin": "B000MT0001",
            "material": "Porcelain",
            "color": "White",
        },
        {"name": "Red Soil Mug White", "asin": "B000MT0002", "material": "Earthenware"},
        {"name": "White Mug", "asin": "B000MT0003", "color": "White"},
        {"name": "White Glass Mug", "asin": "B000MT0004", "material": "Glass", "color": "White"},
    ]
    source = rank_typed_product_batch(*ranking_inputs(items, intent=intent))
    image_inputs = tuple(
        image_score(
            x.evaluation.product_sha256, str(i), -0.9 if x.product.asin == "B000MT0002" else 0.9
        )
        for i, x in enumerate(source.products)
    )
    result = rank_provisional_typed_product_batch(
        source, build_provisional_counterfactual_batch(image_inputs)
    )
    assert [(x.product.asin, x.evaluation.required_status) for x in result.products[:2]] == [
        ("B000MT0002", "confirmed"),
        ("B000MT0003", "uncertain"),
    ]
    assert all(x.evaluation.required_status == "contradicted" for x in result.products[2:])
