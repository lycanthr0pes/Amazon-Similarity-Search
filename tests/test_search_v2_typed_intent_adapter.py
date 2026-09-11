import ast
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import src.search_v2.typed_intent_adapter as typed_intent_adapter
from src.search_v2.bonsai_adapter import parse_bonsai_intent_response
from src.search_v2.bonsai_adapter import search_intent_schema_bytes
from src.search_v2.bonsai_request import load_bonsai_intent_prompt
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent
from src.search_v2.intent import search_intent_sha256
from src.search_v2.typed_intent_adapter import TypedIntentAdapterError
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_intent_adapter import typed_intent_adapter_profile_sha256
from src.search_v2.typed_intent_adapter import typed_requirement_proposal_sha256
from src.search_v2.typed_requirements import DEFAULT_ATTRIBUTE_REGISTRY
from src.search_v2.typed_requirements import attribute_registry_sha256
from src.search_v2.typed_requirements import typed_requirement_set_sha256


SOURCE_INPUT = "黒い丸形マウス。幅120mm以下、収納口は2つ"


def enum_candidate(
    attribute_key: str,
    value: str,
    *,
    strength: str = "required",
    operator: str = "equals",
) -> dict[str, object]:
    return {
        "attribute_key": attribute_key,
        "operator": operator,
        "expected_value": {"value_type": "enum", "values": [value]},
        "strength": strength,
    }


def intent_payload(
    typed_conditions: list[dict[str, object]] | None = None,
    *,
    ambiguities: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "product_name_ja": "マウス",
        "product_name_en": "mouse",
        "category_ja": "マウス",
        "category_en": "mouse",
        "required_terms_ja": ["マウス"],
        "required_terms_en": ["mouse"],
        "preferred_terms_ja": [],
        "preferred_terms_en": [],
        "negative_terms_ja": [],
        "negative_terms_en": [],
        "color_ja": "黒",
        "color_en": "black",
        "features_ja": ["丸形", "幅120mm", "収納口2つ"],
        "features_en": ["round", "width 120mm", "2 compartments"],
        "brand": None,
        "model_number": None,
        "price": {
            "currency": "JPY",
            "mode": "none",
            "target_jpy": None,
            "min_jpy": None,
            "max_jpy": None,
            "source": "none",
            "confidence": None,
        },
        "typed_conditions": typed_conditions if typed_conditions is not None else [],
        "ambiguities": ambiguities if ambiguities is not None else [],
    }


def compact_response_payload(
    typed_conditions: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "product_name_ja": "マウス",
        "product_name_en": "mouse",
        "required_terms_ja": ["黒", "丸形"],
        "required_terms_en": ["black", "round"],
        "preferred_terms_ja": ["幅120mm", "収納口2つ"],
        "preferred_terms_en": ["width 120mm", "2 compartments"],
        "typed_conditions": typed_conditions if typed_conditions is not None else [],
    }


def normalized_intent(
    typed_conditions: list[dict[str, object]] | None = None,
    *,
    ambiguities: list[dict[str, object]] | None = None,
):
    draft = SearchIntentDraft.model_validate(
        intent_payload(typed_conditions, ambiguities=ambiguities)
    )
    provenance = build_intent_provenance(
        source_input=SOURCE_INPUT,
        prompt=b"typed-intent-prompt-v1",
        schema=b'{"type":"object"}',
        response=b'{"typed_conditions":[]}',
    )
    return normalize_search_intent(SOURCE_INPUT, draft, provenance=provenance)


def response_bytes(payload: dict[str, object]) -> bytes:
    content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    envelope = {
        "id": "typed-intent-fixture",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }
    return json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode()


def test_bonsai_candidate_schema_is_required_strict_and_cannot_select_execution() -> None:
    schema = SearchIntentDraft.model_json_schema()
    assert "typed_conditions" in schema["required"]
    candidate_reference = schema["properties"]["typed_conditions"]["items"]["$ref"]
    candidate_schema = schema["$defs"][candidate_reference.rsplit("/", 1)[1]]

    assert candidate_schema["additionalProperties"] is False
    assert set(candidate_schema["required"]) == set(candidate_schema["properties"]) - {
        "attribute_definition"
    }
    assert set(candidate_schema["properties"]) == {
        "attribute_definition",
        "attribute_key",
        "operator",
        "expected_value",
        "strength",
    }
    forbidden = {
        "command",
        "evaluator_id",
        "model_path",
        "module",
        "priority",
        "registry_sha256",
        "url",
        "weight",
    }
    assert set(candidate_schema["properties"]).isdisjoint(forbidden)

    missing = intent_payload()
    del missing["typed_conditions"]
    with pytest.raises(ValidationError, match="Field required"):
        SearchIntentDraft.model_validate(missing)

    injected = enum_candidate("appearance.color", "black")
    injected["evaluator_id"] = "run-user-code"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        SearchIntentDraft.model_validate(intent_payload([injected]))


def test_bonsai_candidate_json_types_are_strict() -> None:
    wrong_integer = {
        "attribute_key": "storage.compartment_count",
        "operator": "equals",
        "expected_value": {
            "value_type": "integer",
            "minimum": "2",
            "maximum": "2",
            "unit": "count",
        },
        "strength": "required",
    }
    wrong_decimal = {
        "attribute_key": "dimensions.width",
        "operator": "at_most",
        "expected_value": {
            "value_type": "decimal",
            "minimum": None,
            "maximum": 120,
            "unit": "mm",
        },
        "strength": "required",
    }

    with pytest.raises(ValidationError, match="int_type"):
        SearchIntentDraft.model_validate(intent_payload([wrong_integer]))
    with pytest.raises(ValidationError, match="string_type"):
        SearchIntentDraft.model_validate(intent_payload([wrong_decimal]))


def test_partial_candidates_bind_but_missing_numeric_specs_block() -> None:
    payload = compact_response_payload([enum_candidate("form.shape", "round")])
    response = response_bytes(payload)

    intent = parse_bonsai_intent_response(
        source_input=SOURCE_INPUT,
        prompt=b"typed-intent-prompt-v1",
        response=response,
    )

    assert intent.typed_conditions[0].attribute_key == "form.shape"
    assert (
        intent.provenance.schema_sha256 == hashlib.sha256(search_intent_schema_bytes()).hexdigest()
    )
    proposal = build_typed_requirement_proposal(intent)
    assert proposal.status == "blocking"
    assert proposal.requirements[0].attribute_key == "form.shape"
    assert proposal.requirements[0].expected_value.values == ("round",)

    missing = dict(payload)
    del missing["typed_conditions"]
    without_candidates = parse_bonsai_intent_response(
        source_input=SOURCE_INPUT,
        prompt=b"typed-intent-prompt-v1",
        response=response_bytes(missing),
    )

    assert without_candidates.typed_conditions == []
    assert build_typed_requirement_proposal(without_candidates).status == "blocking"


def test_prompt_limits_bonsai_to_candidates_not_trusted_execution_metadata() -> None:
    prompt = load_bonsai_intent_prompt().decode("utf-8")

    assert "typed_conditions" in prompt
    assert "共有辞書は変更しない" in prompt
    assert "既存属性はvalue_typeを守り" in prompt
    assert "allowed valueへ一意" in prompt
    assert "外観styleが" not in prompt
    assert "evaluator" in prompt
    assert "weight" in prompt
    assert all(
        definition.attribute_key in prompt for definition in DEFAULT_ATTRIBUTE_REGISTRY.definitions
    )


def test_adapter_normalizes_aliases_json_values_and_assigns_local_ids() -> None:
    candidates = [
        enum_candidate("色", "黒"),
        enum_candidate("形状", "丸形"),
        {
            "attribute_key": "custom",
            "attribute_definition": {
                "label": "収納数",
                "meaning": "収納できる個数",
                "source_quote": "収納数2個",
            },
            "operator": "equals",
            "expected_value": {
                "value_type": "integer",
                "minimum": 2,
                "maximum": 2,
                "unit": "個",
            },
            "strength": "required",
        },
        {
            "attribute_key": "幅",
            "operator": "at_most",
            "expected_value": {
                "value_type": "decimal",
                "minimum": None,
                "maximum": "120.0",
                "unit": "ミリメートル",
            },
            "strength": "required",
        },
    ]
    intent = normalized_intent(candidates)

    first = build_typed_requirement_proposal(intent)
    second = build_typed_requirement_proposal(intent)

    assert first == second
    assert first.status == "ready"
    assert first.issues == ()
    assert first.intent_sha256 == search_intent_sha256(intent)
    assert first.registry_sha256 == attribute_registry_sha256(first.registry)
    assert first.adapter_profile_sha256 == typed_intent_adapter_profile_sha256()
    assert tuple(item.requirement_id for item in first.requirements) == (
        "condition-001",
        "condition-002",
        "condition-003",
        "condition-004",
    )
    assert tuple(item.attribute_key for item in first.requirements) == (
        "appearance.color",
        "form.shape",
        first.requirements[2].attribute_key,
        "dimensions.width",
    )
    assert first.requirements[2].attribute_key.startswith("search.")
    assert first.requirements[0].expected_value.values == ("black",)
    assert first.requirements[1].expected_value.values == ("round",)
    assert (
        first.requirements[2].expected_value.minimum,
        first.requirements[2].expected_value.unit,
    ) == (
        2,
        first.requirements[2].expected_value.unit,
    )
    assert (
        first.requirements[3].expected_value.maximum,
        first.requirements[3].expected_value.unit,
    ) == (Decimal("120"), "mm")
    assert first.requirement_set_sha256 == typed_requirement_set_sha256(
        first.requirements, registry=first.registry
    )
    assert typed_requirement_proposal_sha256(first) == typed_requirement_proposal_sha256(second)


def test_unknown_attribute_is_blocking_and_valid_partial_is_preserved() -> None:
    secret_key = "private-unknown-attribute"
    intent = normalized_intent(
        [
            enum_candidate("appearance.color", "black"),
            enum_candidate(secret_key, "secret-value"),
        ]
    )

    proposal = build_typed_requirement_proposal(intent)

    assert proposal.status == "blocking"
    assert tuple(item.attribute_key for item in proposal.requirements) == ("appearance.color",)
    assert tuple((item.candidate_index, item.code) for item in proposal.issues) == (
        (1, "unknown_attribute"),
    )
    assert secret_key not in repr(proposal)


@pytest.mark.parametrize(
    "candidate",
    [
        {
            "attribute_key": "appearance.color",
            "operator": "equals",
            "expected_value": {"value_type": "boolean", "value": True},
            "strength": "required",
        },
        {
            "attribute_key": "dimensions.width",
            "operator": "at_most",
            "expected_value": {
                "value_type": "decimal",
                "minimum": None,
                "maximum": "120",
                "unit": "cm",
            },
            "strength": "required",
        },
        enum_candidate("form.orientation", "vertical", operator="contains_all"),
        enum_candidate("appearance.color", "purple"),
        {
            "attribute_key": "dimensions.width",
            "operator": "at_most",
            "expected_value": {
                "value_type": "decimal",
                "minimum": None,
                "maximum": "9999999999999",
                "unit": "mm",
            },
            "strength": "required",
        },
    ],
)
def test_known_attribute_contract_mismatch_is_blocking(candidate: dict[str, object]) -> None:
    proposal = build_typed_requirement_proposal(normalized_intent([candidate]))

    assert proposal.status == "blocking"
    assert proposal.requirements == ()
    assert tuple((item.candidate_index, item.code) for item in proposal.issues) == (
        (0, "invalid_condition"),
    )


def test_semantic_hard_condition_is_blocking_and_is_not_softened() -> None:
    candidate = {
        "attribute_key": "appearance.style",
        "operator": "similar_to",
        "expected_value": {"value_type": "semantic", "label": "gaming"},
        "strength": "required",
    }

    proposal = build_typed_requirement_proposal(normalized_intent([candidate]))

    assert proposal.status == "blocking"
    assert proposal.requirements == ()
    assert proposal.issues[0].code == "semantic_requires_preferred"


def test_duplicate_after_registry_normalization_is_blocking_not_double_weighted() -> None:
    intent = normalized_intent(
        [
            enum_candidate("appearance.color", "black"),
            enum_candidate("色", "ブラック"),
        ]
    )

    proposal = build_typed_requirement_proposal(intent)

    assert proposal.status == "blocking"
    assert len(proposal.requirements) == 1
    assert proposal.requirements[0].requirement_id == "condition-001"
    assert tuple((item.candidate_index, item.code) for item in proposal.issues) == (
        (1, "duplicate_condition"),
    )


def test_upstream_blocking_ambiguity_keeps_valid_partial_but_blocks_ready_status() -> None:
    secret_message = "PRIVATE-UPSTREAM-AMBIGUITY"
    intent = normalized_intent(
        [enum_candidate("appearance.color", "black")],
        ambiguities=[
            {
                "code": "unclear_product",
                "message": secret_message,
                "blocking": True,
            }
        ],
    )

    proposal = build_typed_requirement_proposal(intent)

    assert proposal.status == "blocking"
    assert len(proposal.requirements) == 1
    assert tuple((item.candidate_index, item.code) for item in proposal.issues) == (
        (None, "upstream_ambiguity"),
    )
    assert secret_message not in repr(proposal)


def test_empty_candidates_are_ready_when_upstream_intent_is_not_blocked() -> None:
    proposal = build_typed_requirement_proposal(normalized_intent())

    assert proposal.status == "ready"
    assert proposal.requirements == ()
    assert proposal.issues == ()
    assert proposal.requirement_set_sha256 == typed_requirement_set_sha256(())


def test_proposal_digest_rejects_noncanonical_requirement_order() -> None:
    proposal = build_typed_requirement_proposal(
        normalized_intent(
            [
                enum_candidate("appearance.color", "black"),
                enum_candidate("form.shape", "round"),
            ]
        )
    )
    forged = proposal.model_copy(update={"requirements": proposal.requirements[::-1]})

    with pytest.raises(TypedIntentAdapterError, match="adapter contract"):
        typed_requirement_proposal_sha256(forged)


def test_tampered_intent_is_rejected_without_leaking_input_text() -> None:
    secret_text = "PRIVATE-TYPED-INTENT-TEXT"
    tampered = normalized_intent().model_copy(update={"product_name_ja": secret_text * 20})

    with pytest.raises(TypedIntentAdapterError, match="adapter contract") as captured:
        build_typed_requirement_proposal(tampered)

    assert secret_text not in str(captured.value)
    assert captured.value.__cause__ is None


def test_candidate_count_is_bounded_by_the_strict_intent_schema() -> None:
    candidates = [enum_candidate("appearance.color", "black") for _ in range(65)]

    with pytest.raises(ValidationError, match="too_long"):
        SearchIntentDraft.model_validate(intent_payload(candidates))


def test_adapter_has_no_provider_llm_network_dynamic_import_or_callback_boundary() -> None:
    module_path = Path(typed_intent_adapter.__file__)
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.add(node.func.id)

    assert not any(
        name in {"openai", "requests", "httpx", "socket", "importlib"}
        or name.startswith("openai.")
        or name.startswith("requests.")
        or name.startswith("httpx.")
        or name.startswith("socket.")
        or name.startswith("importlib.")
        or name == "src.clients"
        or name.startswith("src.clients.")
        or name == "src.search_v2.bonsai_request"
        for name in imports
    )
    assert "__import__" not in calls
