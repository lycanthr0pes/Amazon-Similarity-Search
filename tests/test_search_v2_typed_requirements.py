from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.search_v2.typed_requirements import DEFAULT_ATTRIBUTE_REGISTRY
from src.search_v2.typed_requirements import AttributeRegistry
from src.search_v2.typed_requirements import DecimalTarget
from src.search_v2.typed_requirements import EnumTarget
from src.search_v2.typed_requirements import TypedRequirementDraft
from src.search_v2.typed_requirements import TypedRequirementError
from src.search_v2.typed_requirements import ValueAlias
from src.search_v2.typed_requirements import attribute_registry_sha256
from src.search_v2.typed_requirements import normalize_typed_requirements
from src.search_v2.typed_requirements import typed_requirement_set_sha256


def requirement_draft(**overrides: object) -> TypedRequirementDraft:
    payload: dict[str, object] = {
        "requirement_id": "requirement-1",
        "attribute_key": "form.shape",
        "operator": "equals",
        "expected_value": {
            "value_type": "enum",
            "values": ("round",),
        },
        "strength": "required",
    }
    payload.update(overrides)
    return TypedRequirementDraft.model_validate(payload)


def test_default_registry_is_canonical_and_digest_is_deterministic() -> None:
    keys = tuple(definition.attribute_key for definition in DEFAULT_ATTRIBUTE_REGISTRY.definitions)

    assert keys == tuple(sorted(keys))
    assert {
        "appearance.color",
        "appearance.style",
        "dimensions.width",
        "form.orientation",
        "form.shape",
        "material.type",
    } == set(keys)
    assert attribute_registry_sha256() == attribute_registry_sha256(DEFAULT_ATTRIBUTE_REGISTRY)
    assert len(attribute_registry_sha256()) == 64


def test_normalizes_registry_aliases_and_binds_the_registry_digest() -> None:
    connection = requirement_draft(
        attribute_key="形状",
        expected_value={"value_type": "enum", "values": ("丸形",)},
    )
    from custom_attribute_fixture import custom_requirement

    selected, registry = custom_requirement(
        "収納数", {"value_type": "integer", "minimum": 2, "maximum": 2, "unit": "個"}
    )
    compartments = requirement_draft(
        requirement_id="requirement-2",
        attribute_key="収納数",
        expected_value={"value_type": "integer", "minimum": 2, "maximum": 2, "unit": "個"},
    )
    normalized = normalize_typed_requirements((connection, compartments), registry=registry)
    assert normalized[0].attribute_key == "form.shape"
    assert normalized[0].expected_value.values == ("round",)
    assert normalized[1].attribute_key == selected.attribute_key
    assert normalized[1].expected_value.minimum == 2
    assert normalized[1].expected_value.unit == selected.expected_value.unit
    assert all(item.registry_sha256 == attribute_registry_sha256(registry) for item in normalized)


@pytest.mark.parametrize("forbidden_field", ["evaluator_id", "module_path", "weight"])
def test_untrusted_draft_cannot_select_execution_or_weight(
    forbidden_field: str,
) -> None:
    payload = {
        "requirement_id": "requirement-1",
        "attribute_key": "form.shape",
        "operator": "equals",
        "expected_value": {"value_type": "enum", "values": ("round",)},
        "strength": "required",
        forbidden_field: "untrusted",
    }

    with pytest.raises(ValidationError):
        TypedRequirementDraft.model_validate(payload)


@pytest.mark.parametrize(
    "overrides",
    [
        {"attribute_key": "unknown.attribute"},
        {"expected_value": {"value_type": "boolean", "value": True}},
        {"operator": "similar_to"},
        {
            "attribute_key": "収納口数",
            "expected_value": {
                "value_type": "integer",
                "minimum": 2,
                "maximum": 2,
                "unit": "kg",
            },
        },
        {"expected_value": {"value_type": "enum", "values": ("satellite",)}},
    ],
)
def test_rejects_unknown_or_incompatible_requirement(overrides: dict[str, object]) -> None:
    with pytest.raises(TypedRequirementError, match="typed requirement contract"):
        normalize_typed_requirements((requirement_draft(**overrides),))


def test_semantic_requirement_must_remain_preferred() -> None:
    expected = {"value_type": "semantic", "label": "gaming"}
    required = requirement_draft(
        attribute_key="appearance.style",
        operator="similar_to",
        expected_value=expected,
        strength="required",
    )
    preferred = required.model_copy(update={"strength": "preferred"})

    with pytest.raises(TypedRequirementError, match="typed requirement contract"):
        normalize_typed_requirements((required,))

    assert normalize_typed_requirements((preferred,))[0].strength == "preferred"


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), 1.5])
def test_decimal_target_rejects_non_finite_or_non_decimal_values(value: object) -> None:
    with pytest.raises(ValidationError):
        DecimalTarget.model_validate(
            {
                "value_type": "decimal",
                "minimum": value,
                "maximum": Decimal("10.0"),
                "unit": "mm",
            }
        )


def test_equal_decimal_values_have_one_canonical_requirement_digest() -> None:
    def normalized(value: Decimal):
        return normalize_typed_requirements(
            (
                requirement_draft(
                    attribute_key="dimensions.width",
                    expected_value={
                        "value_type": "decimal",
                        "minimum": value,
                        "maximum": value,
                        "unit": "mm",
                    },
                ),
            )
        )

    first = normalized(Decimal("120.0"))
    second = normalized(Decimal("120.00"))

    assert first == second
    assert typed_requirement_set_sha256(first) == typed_requirement_set_sha256(second)


def test_decimal_target_rejects_excessive_precision() -> None:
    with pytest.raises(ValidationError):
        DecimalTarget.model_validate(
            {
                "value_type": "decimal",
                "minimum": Decimal("0.1234567"),
                "maximum": Decimal("1.0"),
                "unit": "mm",
            }
        )


def test_registry_rejects_attribute_alias_collisions() -> None:
    first = DEFAULT_ATTRIBUTE_REGISTRY.definitions[0].model_copy(
        update={"aliases": ("shared alias",)}
    )
    second = DEFAULT_ATTRIBUTE_REGISTRY.definitions[1].model_copy(
        update={"aliases": ("SHARED ALIAS",)}
    )

    with pytest.raises(ValidationError):
        AttributeRegistry(
            schema_version="1.0",
            registry_id="test-registry",
            definitions=tuple(sorted((first, second), key=lambda item: item.attribute_key)),
        )


def test_registry_alias_cannot_override_a_canonical_value() -> None:
    connection = next(
        definition
        for definition in DEFAULT_ATTRIBUTE_REGISTRY.definitions
        if definition.attribute_key == "form.shape"
    )
    tampered_connection = connection.model_copy(
        update={
            "value_aliases": connection.value_aliases
            + (ValueAlias(alias="round", canonical="rectangular"),)
        }
    )
    definitions = tuple(
        tampered_connection if item.attribute_key == "form.shape" else item
        for item in DEFAULT_ATTRIBUTE_REGISTRY.definitions
    )

    with pytest.raises(ValidationError):
        AttributeRegistry(
            schema_version="1.0",
            registry_id="test-registry",
            definitions=definitions,
        )


def test_requirement_set_digest_is_deterministic_and_order_bound() -> None:
    first = normalize_typed_requirements(
        (
            requirement_draft(),
            requirement_draft(
                requirement_id="requirement-2",
                attribute_key="appearance.color",
                expected_value={"value_type": "enum", "values": ("black",)},
                strength="preferred",
            ),
        )
    )
    second = (first[1], first[0])

    assert typed_requirement_set_sha256(first) == typed_requirement_set_sha256(first)
    assert typed_requirement_set_sha256(first) != typed_requirement_set_sha256(second)


def test_requirement_set_digest_rejects_noncanonical_requirement() -> None:
    normalized = normalize_typed_requirements((requirement_draft(),))[0]
    noncanonical = normalized.model_copy(
        update={
            "expected_value": EnumTarget(value_type="enum", values=("丸形",)),
        }
    )

    with pytest.raises(TypedRequirementError, match="typed requirement contract"):
        typed_requirement_set_sha256((noncanonical,))
