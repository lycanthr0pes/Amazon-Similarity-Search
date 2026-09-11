"""Search-local attributes use synthetic source and product evidence only."""

from copy import deepcopy
import json

from jsonschema import Draft202012Validator
import pytest

from src.search_v2.bonsai_adapter import parse_bonsai_intent_response
from src.search_v2.bonsai_adapter import search_intent_generation_schema_bytes
from src.search_v2.history_snapshot import _condition_snapshot
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_requirements import DEFAULT_ATTRIBUTE_REGISTRY
from src.search_v2.typed_requirements import attribute_registry_sha256
from src.search_v2.typed_ranking import rank_typed_product_batch
from test_search_v2_bonsai_compact import response_bytes
from test_search_v2_typed_ranking import ranking_inputs


def capacity_condition():
    return {
        "attribute_key": "custom",
        "attribute_definition": {
            "label": "容量",
            "meaning": "容器に入る内容量",
            "source_quote": "容量350ml以上",
        },
        "operator": "at_least",
        "expected_value": {"value_type": "decimal", "minimum": "350", "unit": "ml"},
        "strength": "required",
    }


def dishwasher_condition():
    return {
        "attribute_key": "custom",
        "attribute_definition": {
            "label": "食洗機対応",
            "meaning": "食洗機で洗えること",
            "source_quote": "食洗機対応",
        },
        "operator": "equals",
        "expected_value": {"value_type": "boolean", "value": True},
        "strength": "required",
    }


def parse_conditions(conditions, source="容量350ml以上で食洗機対応のマグカップ"):
    return parse_bonsai_intent_response(
        source_input=source,
        prompt=b"synthetic-dynamic-attributes",
        response=response_bytes({"product_name_ja": "マグカップ", "typed_conditions": conditions}),
    )


def test_custom_wire_schema_accepts_bounded_definition():
    Draft202012Validator(json.loads(search_intent_generation_schema_bytes())).validate(
        {"product_name_ja": "マグカップ", "typed_conditions": [capacity_condition()]}
    )


def test_missing_attributes_are_local_and_reproducible():
    before = attribute_registry_sha256(DEFAULT_ATTRIBUTE_REGISTRY)
    intent = parse_conditions([capacity_condition(), dishwasher_condition()])
    proposal = build_typed_requirement_proposal(intent)
    assert proposal.status == "ready"
    assert len(proposal.requirements) == 2
    assert all(x.attribute_key.startswith("search.") for x in proposal.requirements)
    assert proposal == build_typed_requirement_proposal(intent)
    assert proposal.registry_sha256 != before
    assert attribute_registry_sha256(DEFAULT_ATTRIBUTE_REGISTRY) == before
    plain = build_typed_requirement_proposal(parse_conditions([], source="マグカップ"))
    assert plain.registry_sha256 == before


@pytest.mark.parametrize("mutation", ["quote", "label", "number", "unit", "operator", "strength"])
def test_unsupported_source_relation_blocks_confirmation(mutation):
    condition = capacity_condition()
    if mutation == "quote":
        condition["attribute_definition"]["source_quote"] = "容量500ml以上"
    elif mutation == "label":
        condition["attribute_definition"]["label"] = "重量"
    elif mutation == "number":
        condition["expected_value"]["minimum"] = "500"
    elif mutation == "unit":
        condition["expected_value"]["unit"] = "g"
    elif mutation == "operator":
        condition["operator"] = "at_most"
        condition["expected_value"] = {"value_type": "decimal", "maximum": "350", "unit": "ml"}
    else:
        condition["strength"] = "excluded"
    assert build_typed_requirement_proposal(parse_conditions([condition])).status == "blocking"


def test_unknown_false_boolean_is_not_silently_turned_into_true():
    condition = dishwasher_condition()
    condition["expected_value"]["value"] = False
    assert build_typed_requirement_proposal(parse_conditions([condition])).status == "blocking"


def test_attribute_definition_is_bound_to_confirmation_digest():
    intent = parse_conditions([capacity_condition()])
    first = build_typed_requirement_proposal(intent)
    changed = capacity_condition()
    changed["attribute_definition"]["meaning"] = "容器の公称内容量"
    second = build_typed_requirement_proposal(parse_conditions([changed]))
    assert first.registry_sha256 != second.registry_sha256
    assert first.intent_sha256 != second.intent_sha256


def test_new_attributes_drive_ranking_and_history_with_missing_values_unknown():
    intent = parse_conditions([capacity_condition(), dishwasher_condition()])
    products = [
        {
            "asin": "B000DY0001",
            "name": "マグカップ",
            "features": ["容量: 400ml", "食洗機対応: はい"],
        },
        {
            "asin": "B000DY0002",
            "name": "マグカップ",
            "features": ["容量: 200ml", "食洗機対応: はい"],
        },
        {
            "asin": "B000DY0003",
            "name": "マグカップ",
            "features": ["重量: 400g", "食洗機対応: はい"],
        },
        {
            "asin": "B000DY0004",
            "name": "マグカップ",
            "features": ["容量: 400ml", "食洗機対応: いいえ"],
        },
    ]
    ranked = rank_typed_product_batch(*ranking_inputs(products, intent=intent))
    assert [p.product.asin for p in ranked.products] == [
        "B000DY0001",
        "B000DY0003",
        "B000DY0002",
        "B000DY0004",
    ]
    assert [p.evaluation.required_status for p in ranked.products] == [
        "confirmed",
        "uncertain",
        "contradicted",
        "contradicted",
    ]
    snapshot = _condition_snapshot(intent, proposal=ranked.proposal, display_source="マグカップ")
    assert any("容量" in text and "350ml以上" in text for text in snapshot.conditions)
    assert any("食洗機対応" in text for text in snapshot.conditions)


def test_custom_category_keeps_or_and_does_not_claim_unknown_matches():
    condition = {
        **dishwasher_condition(),
        "attribute_definition": {
            "label": "表面仕上げ",
            "meaning": "表面の仕上げ方法",
            "source_quote": "表面仕上げは艶消しまたは鏡面",
        },
        "operator": "one_of",
        "expected_value": {"value_type": "enum", "values": ["艶消し", "鏡面"]},
    }
    intent = parse_conditions([condition], "表面仕上げは艶消しまたは鏡面のマグカップ")
    products = [
        {"asin": "B000DY0001", "name": "マグカップ", "features": ["表面仕上げ: 鏡面"]},
        {"asin": "B000DY0002", "name": "マグカップ", "features": ["表面仕上げ: 粗面"]},
    ]
    ranked = rank_typed_product_batch(*ranking_inputs(products, intent=intent))
    assert [p.evaluation.required_status for p in ranked.products] == ["confirmed", "contradicted"]


def test_unrelated_attribute_cannot_replace_registered_color():
    condition = deepcopy(dishwasher_condition())
    condition["attribute_definition"] = {
        "label": "色",
        "meaning": "商品全体の色",
        "source_quote": "色は白",
    }
    condition["expected_value"] = {"value_type": "boolean", "value": True}
    assert (
        build_typed_requirement_proposal(parse_conditions([condition], "色は白のマグカップ")).status
        == "blocking"
    )


@pytest.mark.parametrize(
    "source",
    [
        "食洗機対応ではないマグカップ",
        "食洗機対応は不要なマグカップ",
        "食洗機対応なら望ましいマグカップ",
        "容量350ml以上または食洗機対応のマグカップ",
    ],
)
def test_quote_cannot_cut_off_negation_preference_or_cross_attribute_or(source):
    assert (
        build_typed_requirement_proposal(parse_conditions([dishwasher_condition()], source)).status
        == "blocking"
    )


def test_duplicate_custom_attribute_blocks_instead_of_throwing():
    assert (
        build_typed_requirement_proposal(
            parse_conditions([capacity_condition(), capacity_condition()])
        ).status
        == "blocking"
    )


@pytest.mark.parametrize(
    "feature, status",
    [
        ("容量: 0.4l", "confirmed"),
        ("容量: 400g", "uncertain"),
        ("容量: 約400ml", "uncertain"),
        ("本体容量: 400ml", "uncertain"),
        ("容量: 200ml以上", "uncertain"),
    ],
)
def test_only_exact_label_and_compatible_observed_unit_are_evidence(feature, status):
    intent = parse_conditions([capacity_condition()])
    ranked = rank_typed_product_batch(
        *ranking_inputs(
            [
                {"asin": "B000DY0001", "name": "マグカップ", "features": [feature]},
            ],
            intent=intent,
        )
    )
    assert ranked.products[0].evaluation.required_status == status


def test_generated_registry_tampering_is_rejected():
    from pydantic import ValidationError
    from src.search_v2.typed_intent_adapter import TypedRequirementProposal

    proposal = build_typed_requirement_proposal(parse_conditions([capacity_condition()]))
    changed = proposal.registry.model_copy(update={"registry_id": "other-search"})
    with pytest.raises(ValidationError):
        TypedRequirementProposal.model_validate(proposal.model_copy(update={"registry": changed}))


def test_original_source_confirmation_search_and_sqlite_history(tmp_path):
    from src.search_v2.history_repository import SqliteSearchHistoryRepository
    from src.search_v2.history_snapshot import build_history_snapshot
    from src.search_v2.orchestrator import (
        start_intent_review,
        skip_images,
        approve_search,
        run_search,
    )
    from src.search_v2.outscraper_http import OutscraperHttpResponse
    from src.search_v2.state_machine import InMemoryApprovalLedger
    from test_search_v2_orchestrator import BonsaiTransport, OutscraperTransport, SequenceClock
    from test_search_v2_orchestrator import (
        backend_policy,
        bonsai_config,
        bonsai_response,
        usage_ledger,
    )

    source = "容量350ml以上で食洗機対応のマグカップ"
    capacity = capacity_condition()
    capacity["expected_value"] = {"value_type": "integer", "minimum": 350, "unit": "ml"}
    capacity["attribute_definition"]["meaning"] = "容量を表す数量（単位ml）"
    dishwasher = dishwasher_condition()
    dishwasher["attribute_definition"]["meaning"] = "食洗機対応の可否"
    transport = BonsaiTransport(
        bonsai_response(
            {
                "product_name_ja": "マグカップ",
                "typed_conditions": [capacity, dishwasher],
            }
        )
    )
    ledger, clock, policy = usage_ledger(), SequenceClock(), backend_policy()
    stage = start_intent_review(
        source,
        owner_id="owner-dynamic",
        session_id="session-dynamic",
        bonsai_config=bonsai_config(),
        policy=policy,
        usage_ledger=ledger,
        transport=transport,
        now=clock,
    )
    assert stage.typed_proposal.status == "ready"
    request_body = json.loads(transport.calls[0]["body"])
    assert request_body["messages"][-1]["content"] == source
    assert len(ledger.snapshot().reservations) == 1
    review = skip_images(
        stage, postal_code="100-0001", policy=policy, usage_ledger=ledger, now=clock
    )
    approved = approve_search(review, now=clock)
    body = json.dumps(
        {
            "id": "task-dynamic",
            "status": "Success",
            "data": [
                [
                    {
                        "name": "マグカップ",
                        "asin": "B000DY0001",
                        "features": ["容量: 400ml", "食洗機対応: はい"],
                    }
                ]
            ],
        }
    ).encode()
    product_transport = OutscraperTransport(
        [
            OutscraperHttpResponse(
                status_code=200,
                content_type="application/json",
                content_length=len(body),
                content_encoding="identity",
                body_chunks=(body,),
            )
        ]
    )
    result = run_search(
        approved,
        usage_ledger=ledger,
        approval_ledger=InMemoryApprovalLedger(),
        api_key="synthetic-key",
        transport=product_transport,
        now=clock,
        sleep=lambda _: None,
    )
    assert result.outcome == "results"
    assert result.ranked_batch.products[0].evaluation.required_status == "confirmed"
    pending = build_history_snapshot(source, review=review, result=result)
    repository = SqliteSearchHistoryRepository(tmp_path / "history.sqlite3")
    saved = repository.save(pending, now=clock())
    reopened = SqliteSearchHistoryRepository(tmp_path / "history.sqlite3").get(
        owner_id="owner-dynamic", locator=saved.locator, now=clock()
    )
    assert reopened == saved
    assert len(transport.calls) == len(product_transport.calls) == 1


@pytest.mark.parametrize("unit", ["個", "℃", "mah"])
def test_source_grounded_unit_labels_are_not_limited_to_width_or_volume(unit):
    condition = capacity_condition()
    condition["attribute_definition"] = {
        "label": "定格",
        "meaning": "商品の定格値",
        "source_quote": f"定格350{unit}以上",
    }
    condition["expected_value"]["unit"] = unit
    intent = parse_conditions([condition], f"定格350{unit}以上のマグカップ")
    ranked = rank_typed_product_batch(
        *ranking_inputs(
            [
                {"asin": "B000DY0001", "name": "マグカップ", "features": [f"定格: 400{unit}"]},
            ],
            intent=intent,
        )
    )
    assert ranked.products[0].evaluation.required_status == "confirmed"


def test_same_attribute_or_can_be_combined_with_another_required_attribute():
    choice = {
        **dishwasher_condition(),
        "attribute_definition": {
            "label": "表面仕上げ",
            "meaning": "表面の仕上げ方法",
            "source_quote": "表面仕上げは艶消しまたは鏡面",
        },
        "operator": "one_of",
        "expected_value": {"value_type": "enum", "values": ["艶消し", "鏡面"]},
    }
    intent = parse_conditions(
        [choice, dishwasher_condition()], "表面仕上げは艶消しまたは鏡面で食洗機対応のマグカップ"
    )
    assert build_typed_requirement_proposal(intent).status == "ready"


def test_category_negation_cannot_become_a_positive_requirement():
    condition = {
        **dishwasher_condition(),
        "attribute_definition": {
            "label": "表面仕上げ",
            "meaning": "表面の仕上げ方法",
            "source_quote": "表面仕上げは鏡面ではない",
        },
        "expected_value": {"value_type": "enum", "values": ["鏡面"]},
    }
    intent = parse_conditions([condition], "表面仕上げは鏡面ではないマグカップ")
    assert build_typed_requirement_proposal(intent).status == "blocking"


def test_alternatives_cannot_become_contains_all():
    condition = {
        **dishwasher_condition(),
        "attribute_definition": {
            "label": "互換規格",
            "meaning": "対応する規格",
            "source_quote": "互換規格はA規格またはB規格",
        },
        "operator": "contains_all",
        "expected_value": {"value_type": "text_set", "values": ["A規格", "B規格"]},
    }
    intent = parse_conditions([condition], "互換規格はA規格またはB規格のマグカップ")
    assert build_typed_requirement_proposal(intent).status == "blocking"


def test_old_evidence_profile_cannot_describe_new_attribute_extraction():
    from pydantic import ValidationError
    from src.search_v2.product_evidence import ProductEvidenceAdapterProfile

    with pytest.raises(ValidationError):
        ProductEvidenceAdapterProfile(
            schema_version="1.0",
            profile_id="bounded-product-evidence-v2",
            structured_parser_version="observed-structured-value-v2",
            title_parser_version="bounded-title-exact-v2",
            maximum_matches_per_source=8,
        )


@pytest.mark.parametrize("unit", ["inch", "インチ"])
def test_equivalent_inch_spelling_reaches_product_evidence(unit):
    condition = capacity_condition()
    condition["attribute_definition"] = {
        "label": "定格",
        "meaning": "商品の定格寸法",
        "source_quote": "定格27インチ以上",
    }
    condition["expected_value"].update(minimum="27", unit=unit)
    intent = parse_conditions([condition], "定格27インチ以上のマグカップ")
    ranked = rank_typed_product_batch(
        *ranking_inputs(
            [{"asin": "B000DY0001", "name": "マグカップ", "features": ["定格: 28インチ"]}],
            intent=intent,
        )
    )
    assert ranked.products[0].evaluation.required_status == "confirmed"
