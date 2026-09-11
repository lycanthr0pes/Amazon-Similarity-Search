"""Strict typed requirements and the repository-owned attribute registry."""

from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from typing import Annotated
from typing import Literal
import unicodedata

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import ValidationError
from pydantic import field_validator
from pydantic import model_validator


ATTRIBUTE_REGISTRY_DOMAIN = b"amazon-explorer-attribute-registry-v1\x00"
TYPED_REQUIREMENT_SET_DOMAIN = b"amazon-explorer-typed-requirement-set-v1\x00"
MAX_ATTRIBUTE_DEFINITIONS = 128
MAX_ATTRIBUTE_ALIASES = 16
MAX_ALLOWED_VALUES = 64
MAX_VALUE_ALIASES = 64
MAX_EVIDENCE_RULES = 3
MAX_REQUIREMENTS = 64
MAX_SET_VALUES = 32
MAX_TEXT_CHARACTERS = 200
MIN_NUMERIC_VALUE = -1_000_000_000_000
MAX_NUMERIC_VALUE = 1_000_000_000_000

_INVALID_REQUIREMENT_MESSAGE = "Typed inputs did not match the typed requirement contract"

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Identifier = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,63}$"),
]
AttributeKey = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$"),
]
BoundedText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_TEXT_CHARACTERS),
]
RegistryValue = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,63}$"),
]
VersionText = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$"),
]
IntegerValue = Annotated[int, Field(ge=MIN_NUMERIC_VALUE, le=MAX_NUMERIC_VALUE)]
DecimalValue = Annotated[
    Decimal,
    Field(
        ge=Decimal(MIN_NUMERIC_VALUE),
        le=Decimal(MAX_NUMERIC_VALUE),
        max_digits=24,
        decimal_places=6,
    ),
]
RequirementOperator = Literal[
    "equals",
    "one_of",
    "contains_all",
    "at_least",
    "at_most",
    "between",
    "compatible_with",
    "similar_to",
]
RequirementStrength = Literal["required", "preferred", "excluded"]
ValueType = Literal["boolean", "enum", "integer", "decimal", "text_set", "semantic"]
EvidenceSource = Literal["structured", "title_exact", "visual_feature"]

_OPERATORS_BY_TYPE: dict[str, frozenset[str]] = {
    "boolean": frozenset(("equals",)),
    "enum": frozenset(("equals", "one_of", "compatible_with")),
    "integer": frozenset(("equals", "at_least", "at_most", "between")),
    "decimal": frozenset(("equals", "at_least", "at_most", "between")),
    "text_set": frozenset(("equals", "one_of", "contains_all", "compatible_with")),
    "semantic": frozenset(("similar_to",)),
}


class TypedRequirementError(ValueError):
    """A fixed-message rejection for invalid typed requirement inputs."""


class StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


def _text_identity(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _contains_forbidden_control(value: str) -> bool:
    return any(
        unicodedata.category(character).startswith("C") and not character.isspace()
        for character in value
    )


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    if _contains_forbidden_control(normalized):
        raise ValueError("text contains a forbidden control character")
    collapsed = " ".join(normalized.split())
    if not collapsed or len(collapsed) > MAX_TEXT_CHARACTERS:
        raise ValueError("text length is outside the allowed range")
    return collapsed


def _has_unique_text(values: tuple[str, ...]) -> bool:
    identities = tuple(_text_identity(value) for value in values)
    return len(identities) == len(set(identities))


def _canonical_decimal(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if value.is_zero():
        return Decimal(0)
    return value.normalize()


class ValueAlias(StrictFrozenContract):
    alias: BoundedText
    canonical: RegistryValue

    @field_validator("alias")
    @classmethod
    def validate_alias(cls, value: str) -> str:
        if _normalize_text(value) != value:
            raise ValueError("registry aliases must already be normalized")
        return value


class EvidenceRule(StrictFrozenContract):
    source: EvidenceSource
    priority: Annotated[int, Field(ge=1, le=100)]
    evaluator_id: Identifier
    evaluator_version: VersionText


class BooleanTarget(StrictFrozenContract):
    value_type: Literal["boolean"]
    value: bool


class EnumTarget(StrictFrozenContract):
    value_type: Literal["enum"]
    values: Annotated[tuple[BoundedText, ...], Field(min_length=1, max_length=MAX_SET_VALUES)]

    @model_validator(mode="after")
    def validate_values(self) -> EnumTarget:
        if not _has_unique_text(self.values):
            raise ValueError("enum target values must be unique")
        return self


class IntegerTarget(StrictFrozenContract):
    value_type: Literal["integer"]
    minimum: IntegerValue | None
    maximum: IntegerValue | None
    unit: BoundedText


class DecimalTarget(StrictFrozenContract):
    value_type: Literal["decimal"]
    minimum: DecimalValue | None
    maximum: DecimalValue | None
    unit: BoundedText

    @field_validator("minimum", "maximum", mode="before")
    @classmethod
    def validate_decimal(cls, value: object) -> object:
        if value is None:
            return value
        if type(value) is not Decimal or not value.is_finite():
            raise ValueError("decimal target values must be finite Decimal instances")
        return value


class TextSetTarget(StrictFrozenContract):
    value_type: Literal["text_set"]
    values: Annotated[tuple[BoundedText, ...], Field(min_length=1, max_length=MAX_SET_VALUES)]

    @model_validator(mode="after")
    def validate_values(self) -> TextSetTarget:
        if not _has_unique_text(self.values):
            raise ValueError("text set target values must be unique")
        return self


class SemanticTarget(StrictFrozenContract):
    value_type: Literal["semantic"]
    label: BoundedText


RequirementTarget = Annotated[
    BooleanTarget | EnumTarget | IntegerTarget | DecimalTarget | TextSetTarget | SemanticTarget,
    Field(discriminator="value_type"),
]


class BooleanObservedValue(StrictFrozenContract):
    value_type: Literal["boolean"]
    value: bool


class EnumObservedValue(StrictFrozenContract):
    value_type: Literal["enum"]
    value: BoundedText


class IntegerObservedValue(StrictFrozenContract):
    value_type: Literal["integer"]
    value: IntegerValue
    unit: BoundedText


class DecimalObservedValue(StrictFrozenContract):
    value_type: Literal["decimal"]
    value: DecimalValue
    unit: BoundedText

    @field_validator("value", mode="before")
    @classmethod
    def validate_decimal(cls, value: object) -> object:
        if type(value) is not Decimal or not value.is_finite():
            raise ValueError("observed decimal values must be finite Decimal instances")
        return value


class TextSetObservedValue(StrictFrozenContract):
    value_type: Literal["text_set"]
    values: Annotated[tuple[BoundedText, ...], Field(min_length=1, max_length=MAX_SET_VALUES)]

    @model_validator(mode="after")
    def validate_values(self) -> TextSetObservedValue:
        if not _has_unique_text(self.values):
            raise ValueError("observed text set values must be unique")
        return self


class SemanticObservedValue(StrictFrozenContract):
    value_type: Literal["semantic"]
    label: BoundedText


ObservedValue = Annotated[
    BooleanObservedValue
    | EnumObservedValue
    | IntegerObservedValue
    | DecimalObservedValue
    | TextSetObservedValue
    | SemanticObservedValue,
    Field(discriminator="value_type"),
]


class AttributeDefinition(StrictFrozenContract):
    category: Identifier
    attribute_key: AttributeKey
    aliases: Annotated[tuple[BoundedText, ...], Field(max_length=MAX_ATTRIBUTE_ALIASES)]
    value_type: ValueType
    allowed_operators: Annotated[
        tuple[RequirementOperator, ...],
        Field(min_length=1, max_length=8),
    ]
    allowed_strengths: Annotated[
        tuple[RequirementStrength, ...],
        Field(min_length=1, max_length=3),
    ]
    allowed_units: Annotated[tuple[RegistryValue, ...], Field(max_length=16)]
    unit_aliases: Annotated[tuple[ValueAlias, ...], Field(max_length=MAX_VALUE_ALIASES)]
    allowed_values: Annotated[tuple[RegistryValue, ...], Field(max_length=MAX_ALLOWED_VALUES)]
    value_aliases: Annotated[tuple[ValueAlias, ...], Field(max_length=MAX_VALUE_ALIASES)]
    evidence_rules: Annotated[tuple[EvidenceRule, ...], Field(max_length=MAX_EVIDENCE_RULES)]
    default_weight: Annotated[int, Field(ge=1, le=100)]
    visual_prompt_allowed: bool

    @model_validator(mode="after")
    def validate_definition(self) -> AttributeDefinition:
        if not _has_unique_text(self.aliases):
            raise ValueError("attribute aliases must be unique")
        if len(self.allowed_operators) != len(set(self.allowed_operators)):
            raise ValueError("allowed operators must be unique")
        if not set(self.allowed_operators).issubset(_OPERATORS_BY_TYPE[self.value_type]):
            raise ValueError("operator is incompatible with the attribute value type")
        if len(self.allowed_strengths) != len(set(self.allowed_strengths)):
            raise ValueError("allowed strengths must be unique")
        if self.value_type == "semantic" and self.allowed_strengths != ("preferred",):
            raise ValueError("semantic attributes must remain preferred")

        numeric = self.value_type in {"integer", "decimal"}
        if numeric != bool(self.allowed_units):
            raise ValueError("numeric attributes require units and other attributes forbid them")
        if len(self.allowed_units) != len(set(self.allowed_units)):
            raise ValueError("allowed units must be unique")
        if len(self.unit_aliases) != len(
            {_text_identity(item.alias) for item in self.unit_aliases}
        ):
            raise ValueError("unit aliases must be unique")
        if any(item.canonical not in self.allowed_units for item in self.unit_aliases):
            raise ValueError("unit alias must resolve to an allowed unit")
        unit_resolution = {_text_identity(unit): unit for unit in self.allowed_units}
        for item in self.unit_aliases:
            existing = unit_resolution.get(_text_identity(item.alias))
            if existing is not None and existing != item.canonical:
                raise ValueError("unit alias must not override a canonical unit")

        enumerated = self.value_type in {"enum", "semantic"}
        if enumerated != bool(self.allowed_values):
            raise ValueError("enum and semantic attributes require allowed values")
        if len(self.allowed_values) != len(set(self.allowed_values)):
            raise ValueError("allowed values must be unique")
        if len(self.value_aliases) != len(
            {_text_identity(item.alias) for item in self.value_aliases}
        ):
            raise ValueError("value aliases must be unique")
        if any(item.canonical not in self.allowed_values for item in self.value_aliases):
            raise ValueError("value alias must resolve to an allowed value")
        value_resolution = {_text_identity(value): value for value in self.allowed_values}
        for item in self.value_aliases:
            existing = value_resolution.get(_text_identity(item.alias))
            if existing is not None and existing != item.canonical:
                raise ValueError("value alias must not override a canonical value")

        sources = tuple(rule.source for rule in self.evidence_rules)
        if len(sources) != len(set(sources)):
            raise ValueError("evidence sources must be unique for an attribute")
        return self


class AttributeRegistry(StrictFrozenContract):
    schema_version: Literal["1.0"]
    registry_id: Identifier
    definitions: Annotated[
        tuple[AttributeDefinition, ...],
        Field(min_length=1, max_length=MAX_ATTRIBUTE_DEFINITIONS),
    ]

    @model_validator(mode="after")
    def validate_registry(self) -> AttributeRegistry:
        keys = tuple(definition.attribute_key for definition in self.definitions)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("attribute definitions must have unique sorted keys")

        identities: dict[str, str] = {}
        for definition in self.definitions:
            for name in (definition.attribute_key, *definition.aliases):
                identity = _text_identity(name)
                existing = identities.get(identity)
                if existing is not None and existing != definition.attribute_key:
                    raise ValueError("attribute key and alias identities must be unique")
                identities[identity] = definition.attribute_key
        return self


class TypedRequirementDraft(StrictFrozenContract):
    requirement_id: Identifier
    attribute_key: BoundedText
    operator: RequirementOperator
    expected_value: RequirementTarget
    strength: RequirementStrength


class TypedRequirement(StrictFrozenContract):
    schema_version: Literal["1.0"]
    requirement_id: Identifier
    attribute_key: AttributeKey
    operator: RequirementOperator
    expected_value: RequirementTarget
    strength: RequirementStrength
    registry_sha256: Digest


_STRUCTURED_EVIDENCE = EvidenceRule(
    source="structured",
    priority=10,
    evaluator_id="observed-structured-value",
    evaluator_version="1",
)
_TITLE_EVIDENCE = EvidenceRule(
    source="title_exact",
    priority=20,
    evaluator_id="bounded-title-exact",
    evaluator_version="1",
)


DEFAULT_ATTRIBUTE_REGISTRY = AttributeRegistry(
    schema_version="1.0",
    registry_id="common-attribute-registry-v4",
    definitions=(
        AttributeDefinition(
            category="appearance",
            attribute_key="appearance.color",
            aliases=("色", "カラー"),
            value_type="enum",
            allowed_operators=("equals", "one_of"),
            allowed_strengths=("required", "preferred", "excluded"),
            allowed_units=(),
            unit_aliases=(),
            allowed_values=("black", "blue", "brown", "gray", "green", "red", "silver", "white"),
            value_aliases=(
                ValueAlias(alias="ブラック", canonical="black"),
                ValueAlias(alias="ブルー", canonical="blue"),
                ValueAlias(alias="ブラウン", canonical="brown"),
                ValueAlias(alias="グレー", canonical="gray"),
                ValueAlias(alias="グリーン", canonical="green"),
                ValueAlias(alias="レッド", canonical="red"),
                ValueAlias(alias="シルバー", canonical="silver"),
                ValueAlias(alias="ホワイト", canonical="white"),
                ValueAlias(alias="黒", canonical="black"),
                ValueAlias(alias="青", canonical="blue"),
                ValueAlias(alias="茶", canonical="brown"),
                ValueAlias(alias="灰", canonical="gray"),
                ValueAlias(alias="緑", canonical="green"),
                ValueAlias(alias="赤", canonical="red"),
                ValueAlias(alias="銀", canonical="silver"),
                ValueAlias(alias="白", canonical="white"),
            ),
            evidence_rules=(_STRUCTURED_EVIDENCE, _TITLE_EVIDENCE),
            default_weight=1,
            visual_prompt_allowed=True,
        ),
        AttributeDefinition(
            category="appearance",
            attribute_key="appearance.style",
            aliases=("外観スタイル",),
            value_type="semantic",
            allowed_operators=("similar_to",),
            allowed_strengths=("preferred",),
            allowed_units=(),
            unit_aliases=(),
            allowed_values=("gaming", "industrial", "minimal"),
            value_aliases=(
                ValueAlias(alias="ゲーミング", canonical="gaming"),
                ValueAlias(alias="インダストリアル", canonical="industrial"),
                ValueAlias(alias="ミニマル", canonical="minimal"),
            ),
            evidence_rules=(),
            default_weight=1,
            visual_prompt_allowed=True,
        ),
        AttributeDefinition(
            category="dimensions",
            attribute_key="dimensions.width",
            aliases=("幅",),
            value_type="decimal",
            allowed_operators=("equals", "at_least", "at_most", "between"),
            allowed_strengths=("required", "preferred", "excluded"),
            allowed_units=("mm",),
            unit_aliases=(ValueAlias(alias="ミリメートル", canonical="mm"),),
            allowed_values=(),
            value_aliases=(),
            evidence_rules=(_STRUCTURED_EVIDENCE, _TITLE_EVIDENCE),
            default_weight=1,
            visual_prompt_allowed=False,
        ),
        AttributeDefinition(
            category="form",
            attribute_key="form.orientation",
            aliases=("向き",),
            value_type="enum",
            allowed_operators=("equals", "one_of"),
            allowed_strengths=("required", "preferred", "excluded"),
            allowed_units=(),
            unit_aliases=(),
            allowed_values=("horizontal", "vertical"),
            value_aliases=(
                ValueAlias(alias="横", canonical="horizontal"),
                ValueAlias(alias="横型", canonical="horizontal"),
                ValueAlias(alias="縦", canonical="vertical"),
                ValueAlias(alias="縦型", canonical="vertical"),
            ),
            evidence_rules=(_STRUCTURED_EVIDENCE, _TITLE_EVIDENCE),
            default_weight=1,
            visual_prompt_allowed=True,
        ),
        AttributeDefinition(
            category="form",
            attribute_key="form.shape",
            aliases=("形状", "形"),
            value_type="enum",
            allowed_operators=("equals", "one_of"),
            allowed_strengths=("required", "preferred", "excluded"),
            allowed_units=(),
            unit_aliases=(),
            allowed_values=("cylindrical", "oval", "rectangular", "round", "spherical", "square"),
            value_aliases=(
                ValueAlias(alias="円筒形", canonical="cylindrical"),
                ValueAlias(alias="楕円形", canonical="oval"),
                ValueAlias(alias="長方形", canonical="rectangular"),
                ValueAlias(alias="丸形", canonical="round"),
                ValueAlias(alias="丸い", canonical="round"),
                ValueAlias(alias="円形", canonical="round"),
                ValueAlias(alias="球形", canonical="spherical"),
                ValueAlias(alias="正方形", canonical="square"),
            ),
            evidence_rules=(_STRUCTURED_EVIDENCE, _TITLE_EVIDENCE),
            default_weight=1,
            visual_prompt_allowed=True,
        ),
        AttributeDefinition(
            category="material",
            attribute_key="material.type",
            aliases=("材質", "素材"),
            value_type="enum",
            allowed_operators=("equals", "one_of"),
            allowed_strengths=("required", "preferred", "excluded"),
            allowed_units=(),
            unit_aliases=(),
            allowed_values=(
                "bone_china",
                "earthenware",
                "glass",
                "plastic",
                "porcelain",
                "stainless_steel",
                "stoneware",
                "wood",
            ),
            value_aliases=(
                ValueAlias(alias="陶器", canonical="earthenware"),
                ValueAlias(alias="陶器製", canonical="earthenware"),
                ValueAlias(alias="磁器", canonical="porcelain"),
                ValueAlias(alias="磁器製", canonical="porcelain"),
                ValueAlias(alias="ボーンチャイナ", canonical="bone_china"),
                ValueAlias(alias="bone china", canonical="bone_china"),
                ValueAlias(alias="炻器", canonical="stoneware"),
                ValueAlias(alias="せっ器", canonical="stoneware"),
                ValueAlias(alias="ストーンウェア", canonical="stoneware"),
                ValueAlias(alias="ガラス", canonical="glass"),
                ValueAlias(alias="ガラス製", canonical="glass"),
                ValueAlias(alias="プラスチック", canonical="plastic"),
                ValueAlias(alias="樹脂", canonical="plastic"),
                ValueAlias(alias="ステンレス", canonical="stainless_steel"),
                ValueAlias(alias="stainless steel", canonical="stainless_steel"),
                ValueAlias(alias="木製", canonical="wood"),
                ValueAlias(alias="wooden", canonical="wood"),
            ),
            evidence_rules=(_STRUCTURED_EVIDENCE, _TITLE_EVIDENCE),
            default_weight=1,
            visual_prompt_allowed=False,
        ),
    ),
)


def _canonical_sha256(domain: bytes, value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(domain + canonical).hexdigest()


def attribute_registry_sha256(registry: AttributeRegistry = DEFAULT_ATTRIBUTE_REGISTRY) -> str:
    try:
        validated = AttributeRegistry.model_validate(registry)
    except ValidationError as exc:
        raise TypedRequirementError(_INVALID_REQUIREMENT_MESSAGE) from exc
    return _canonical_sha256(ATTRIBUTE_REGISTRY_DOMAIN, validated)


def _definition_lookup(registry: AttributeRegistry) -> dict[str, AttributeDefinition]:
    lookup: dict[str, AttributeDefinition] = {}
    for definition in registry.definitions:
        lookup[_text_identity(definition.attribute_key)] = definition
        for alias in definition.aliases:
            lookup[_text_identity(alias)] = definition
    return lookup


def _normalize_allowed_value(value: str, definition: AttributeDefinition) -> str:
    normalized = _normalize_text(value)
    aliases = {_text_identity(canonical): canonical for canonical in definition.allowed_values}
    aliases.update(
        {_text_identity(item.alias): item.canonical for item in definition.value_aliases}
    )
    try:
        return aliases[_text_identity(normalized)]
    except KeyError as exc:
        raise ValueError("value is not allowed for the attribute") from exc


def _normalize_unit(value: str, definition: AttributeDefinition) -> str:
    normalized = _normalize_text(value)
    aliases = {_text_identity(unit): unit for unit in definition.allowed_units}
    aliases.update({_text_identity(item.alias): item.canonical for item in definition.unit_aliases})
    try:
        return aliases[_text_identity(normalized)]
    except KeyError as exc:
        raise ValueError("unit is not allowed for the attribute") from exc


def _validate_numeric_bounds(
    operator: RequirementOperator,
    minimum: int | Decimal | None,
    maximum: int | Decimal | None,
) -> None:
    if operator == "equals" and not (
        minimum is not None and maximum is not None and minimum == maximum
    ):
        raise ValueError("equals requires identical minimum and maximum")
    if operator == "at_least" and not (minimum is not None and maximum is None):
        raise ValueError("at_least requires only minimum")
    if operator == "at_most" and not (minimum is None and maximum is not None):
        raise ValueError("at_most requires only maximum")
    if operator == "between" and not (
        minimum is not None and maximum is not None and minimum <= maximum
    ):
        raise ValueError("between requires ordered minimum and maximum")


def _normalize_target(
    target: RequirementTarget,
    definition: AttributeDefinition,
    operator: RequirementOperator,
) -> RequirementTarget:
    if target.value_type != definition.value_type:
        raise ValueError("target type does not match the attribute definition")

    if isinstance(target, BooleanTarget):
        return target
    if isinstance(target, EnumTarget):
        values = tuple(
            sorted(
                (_normalize_allowed_value(value, definition) for value in target.values),
                key=_text_identity,
            )
        )
        if len(values) != len(set(values)):
            raise ValueError("normalized enum values must be unique")
        if operator == "equals" and len(values) != 1:
            raise ValueError("enum equals requires exactly one expected value")
        return EnumTarget(value_type="enum", values=values)
    if isinstance(target, IntegerTarget):
        _validate_numeric_bounds(operator, target.minimum, target.maximum)
        return IntegerTarget(
            value_type="integer",
            minimum=target.minimum,
            maximum=target.maximum,
            unit=_normalize_unit(target.unit, definition),
        )
    if isinstance(target, DecimalTarget):
        _validate_numeric_bounds(operator, target.minimum, target.maximum)
        return DecimalTarget(
            value_type="decimal",
            minimum=_canonical_decimal(target.minimum),
            maximum=_canonical_decimal(target.maximum),
            unit=_normalize_unit(target.unit, definition),
        )
    if isinstance(target, TextSetTarget):
        values = tuple(sorted((_normalize_text(value).casefold() for value in target.values)))
        if len(values) != len(set(values)):
            raise ValueError("normalized text set values must be unique")
        return TextSetTarget(value_type="text_set", values=values)
    if isinstance(target, SemanticTarget):
        return SemanticTarget(
            value_type="semantic",
            label=_normalize_allowed_value(target.label, definition),
        )
    raise TypeError("unsupported requirement target")


def normalize_typed_requirements(
    drafts: tuple[TypedRequirementDraft, ...],
    *,
    registry: AttributeRegistry = DEFAULT_ATTRIBUTE_REGISTRY,
) -> tuple[TypedRequirement, ...]:
    try:
        validated_registry = AttributeRegistry.model_validate(registry)
        if type(drafts) is not tuple or len(drafts) > MAX_REQUIREMENTS:
            raise TypeError("drafts must be a bounded tuple")
        if any(type(draft) is not TypedRequirementDraft for draft in drafts):
            raise TypeError("drafts must contain exact TypedRequirementDraft values")

        requirement_ids = tuple(draft.requirement_id for draft in drafts)
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("requirement ids must be unique")

        lookup = _definition_lookup(validated_registry)
        registry_digest = attribute_registry_sha256(validated_registry)
        normalized: list[TypedRequirement] = []
        for draft in drafts:
            definition = lookup.get(_text_identity(_normalize_text(draft.attribute_key)))
            if definition is None:
                raise ValueError("attribute key is not registered")
            if draft.operator not in definition.allowed_operators:
                raise ValueError("operator is not allowed for the attribute")
            if draft.strength not in definition.allowed_strengths:
                raise ValueError("strength is not allowed for the attribute")
            normalized.append(
                TypedRequirement(
                    schema_version="1.0",
                    requirement_id=draft.requirement_id,
                    attribute_key=definition.attribute_key,
                    operator=draft.operator,
                    expected_value=_normalize_target(
                        draft.expected_value,
                        definition,
                        draft.operator,
                    ),
                    strength=draft.strength,
                    registry_sha256=registry_digest,
                )
            )
        return tuple(normalized)
    except TypedRequirementError:
        raise
    except (TypeError, ValueError, ValidationError) as exc:
        raise TypedRequirementError(_INVALID_REQUIREMENT_MESSAGE) from exc


def typed_requirement_set_sha256(
    requirements: tuple[TypedRequirement, ...],
    *,
    registry: AttributeRegistry = DEFAULT_ATTRIBUTE_REGISTRY,
) -> str:
    try:
        validated_registry = AttributeRegistry.model_validate(registry)
        if type(requirements) is not tuple or len(requirements) > MAX_REQUIREMENTS:
            raise TypeError("requirements must be a bounded tuple")
        validated = tuple(TypedRequirement.model_validate(item) for item in requirements)
        registry_digest = attribute_registry_sha256(validated_registry)
        if any(item.registry_sha256 != registry_digest for item in validated):
            raise ValueError("requirement registry binding is invalid")
        identifiers = tuple(item.requirement_id for item in validated)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("requirement ids must be unique")
        canonical = normalize_typed_requirements(
            tuple(
                TypedRequirementDraft(
                    requirement_id=item.requirement_id,
                    attribute_key=item.attribute_key,
                    operator=item.operator,
                    expected_value=item.expected_value,
                    strength=item.strength,
                )
                for item in validated
            ),
            registry=validated_registry,
        )
        if canonical != validated:
            raise ValueError("requirements must be canonical for the registry")
        payload = {
            "registry_sha256": registry_digest,
            "requirements": [item.model_dump(mode="json") for item in validated],
        }
        return _canonical_sha256(TYPED_REQUIREMENT_SET_DOMAIN, payload)
    except TypedRequirementError:
        raise
    except (TypeError, ValueError, ValidationError) as exc:
        raise TypedRequirementError(_INVALID_REQUIREMENT_MESSAGE) from exc


def attribute_definition(
    attribute_key: str,
    *,
    registry: AttributeRegistry = DEFAULT_ATTRIBUTE_REGISTRY,
) -> AttributeDefinition:
    """Return a registered definition for trusted internal adapters."""

    try:
        validated_registry = AttributeRegistry.model_validate(registry)
        definition = _definition_lookup(validated_registry).get(
            _text_identity(_normalize_text(attribute_key))
        )
        if definition is None:
            raise ValueError("attribute key is not registered")
        return definition
    except (TypeError, ValueError, ValidationError) as exc:
        raise TypedRequirementError(_INVALID_REQUIREMENT_MESSAGE) from exc


def normalize_observed_value(
    value: ObservedValue,
    definition: AttributeDefinition,
) -> ObservedValue:
    """Normalize an observation using only a trusted registry definition."""

    if value.value_type != definition.value_type:
        raise TypedRequirementError(_INVALID_REQUIREMENT_MESSAGE)
    try:
        if isinstance(value, BooleanObservedValue):
            return value
        if isinstance(value, EnumObservedValue):
            return EnumObservedValue(
                value_type="enum",
                value=_normalize_allowed_value(value.value, definition),
            )
        if isinstance(value, IntegerObservedValue):
            return IntegerObservedValue(
                value_type="integer",
                value=value.value,
                unit=_normalize_unit(value.unit, definition),
            )
        if isinstance(value, DecimalObservedValue):
            return DecimalObservedValue(
                value_type="decimal",
                value=_canonical_decimal(value.value),
                unit=_normalize_unit(value.unit, definition),
            )
        if isinstance(value, TextSetObservedValue):
            values = tuple(sorted((_normalize_text(item).casefold() for item in value.values)))
            if len(values) != len(set(values)):
                raise ValueError("normalized observed set values must be unique")
            return TextSetObservedValue(value_type="text_set", values=values)
        if isinstance(value, SemanticObservedValue):
            return SemanticObservedValue(
                value_type="semantic",
                label=_normalize_allowed_value(value.label, definition),
            )
        raise TypeError("unsupported observed value")
    except (TypeError, ValueError, ValidationError) as exc:
        raise TypedRequirementError(_INVALID_REQUIREMENT_MESSAGE) from exc
