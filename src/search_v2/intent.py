from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from src.search_v2.typed_requirements import RequirementOperator
from src.search_v2.typed_requirements import RequirementStrength


MAX_SOURCE_INPUT_CODEPOINTS = 2_000
MAX_BOUND_ARTIFACT_BYTES = 1_048_576
MAX_INTENT_JSON_BYTES = 49_152
MAX_PRICE_JPY = 1_000_000_000
MAX_TYPED_CONDITIONS = 64
MAX_TYPED_SET_VALUES = 32

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
ShortText = Annotated[str, StringConstraints(min_length=1, max_length=100)]
NameText = Annotated[str, StringConstraints(min_length=1, max_length=200)]
AmbiguityMessage = Annotated[str, StringConstraints(min_length=1, max_length=300)]
AmbiguityCode = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,49}$"),
]
TermList = Annotated[list[ShortText], Field(max_length=20)]
PriceValue = Annotated[int, Field(gt=0, le=MAX_PRICE_JPY)]
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
CandidateDecimal = Annotated[
    str,
    StringConstraints(pattern=r"^-?(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{1,6})?$"),
]


class StrictContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        revalidate_instances="always",
    )


class PriceCondition(StrictContract):
    currency: Literal["JPY"]
    mode: Literal["exact", "range", "min", "max", "none"]
    target_jpy: PriceValue | None
    min_jpy: PriceValue | None
    max_jpy: PriceValue | None
    source: Literal["explicit", "inferred", "none"]
    confidence: Confidence | None

    @model_validator(mode="after")
    def validate_mode_contract(self) -> PriceCondition:
        values = (self.target_jpy, self.min_jpy, self.max_jpy)
        if self.mode == "none":
            if any(value is not None for value in values):
                raise ValueError("none price must not contain price values")
            if self.source != "none" or self.confidence is not None:
                raise ValueError("none price requires source=none and confidence=null")
            return self

        if self.source == "none":
            raise ValueError("priced condition requires explicit or inferred source")
        if self.source == "inferred" and self.confidence is None:
            raise ValueError("inferred price requires confidence")

        if self.mode == "exact" and not (
            self.target_jpy is not None and self.min_jpy is None and self.max_jpy is None
        ):
            raise ValueError("exact price requires only target_jpy")
        if self.mode == "range" and not (
            self.target_jpy is None and self.min_jpy is not None and self.max_jpy is not None
        ):
            raise ValueError("range price requires only min_jpy and max_jpy")
        if self.mode == "min" and not (
            self.target_jpy is None and self.min_jpy is not None and self.max_jpy is None
        ):
            raise ValueError("min price requires only min_jpy")
        if self.mode == "max" and not (
            self.target_jpy is None and self.min_jpy is None and self.max_jpy is not None
        ):
            raise ValueError("max price requires only max_jpy")
        if (
            self.mode == "range"
            and self.min_jpy is not None
            and self.max_jpy is not None
            and self.min_jpy > self.max_jpy
        ):
            raise ValueError("min_jpy must not exceed max_jpy")
        return self


class IntentAmbiguity(StrictContract):
    code: AmbiguityCode
    message: AmbiguityMessage
    blocking: bool


class IntentProvenance(StrictContract):
    source_input_sha256: Digest
    prompt_sha256: Digest
    schema_sha256: Digest
    response_sha256: Digest


class BonsaiBooleanTarget(StrictContract):
    value_type: Literal["boolean"]
    value: bool


class BonsaiEnumTarget(StrictContract):
    value_type: Literal["enum"]
    values: Annotated[list[ShortText], Field(min_length=1, max_length=MAX_TYPED_SET_VALUES)]


class BonsaiIntegerTarget(StrictContract):
    value_type: Literal["integer"]
    minimum: Annotated[int, Field(ge=-1_000_000_000_000, le=1_000_000_000_000)] | None
    maximum: Annotated[int, Field(ge=-1_000_000_000_000, le=1_000_000_000_000)] | None
    unit: ShortText


class BonsaiDecimalTarget(StrictContract):
    value_type: Literal["decimal"]
    minimum: CandidateDecimal | None
    maximum: CandidateDecimal | None
    unit: ShortText


class BonsaiTextSetTarget(StrictContract):
    value_type: Literal["text_set"]
    values: Annotated[list[ShortText], Field(min_length=1, max_length=MAX_TYPED_SET_VALUES)]


class BonsaiSemanticTarget(StrictContract):
    value_type: Literal["semantic"]
    label: ShortText


BonsaiRequirementTarget = Annotated[
    BonsaiBooleanTarget
    | BonsaiEnumTarget
    | BonsaiIntegerTarget
    | BonsaiDecimalTarget
    | BonsaiTextSetTarget
    | BonsaiSemanticTarget,
    Field(discriminator="value_type"),
]


class BonsaiAttributeDefinition(StrictContract):
    label: ShortText
    meaning: NameText
    source_quote: NameText = Field(repr=False)


class BonsaiTypedConditionCandidate(StrictContract):
    attribute_key: NameText
    operator: RequirementOperator
    expected_value: BonsaiRequirementTarget
    strength: RequirementStrength
    attribute_definition: BonsaiAttributeDefinition | None = None


class SearchIntentDraft(StrictContract):
    product_name_ja: NameText | None
    product_name_en: NameText | None
    category_ja: ShortText | None
    category_en: ShortText | None
    required_terms_ja: TermList
    required_terms_en: TermList
    preferred_terms_ja: TermList
    preferred_terms_en: TermList
    negative_terms_ja: TermList
    negative_terms_en: TermList
    color_ja: ShortText | None
    color_en: ShortText | None
    features_ja: TermList
    features_en: TermList
    brand: ShortText | None
    model_number: ShortText | None
    price: PriceCondition
    typed_conditions: Annotated[
        list[BonsaiTypedConditionCandidate],
        Field(max_length=MAX_TYPED_CONDITIONS),
    ]
    ambiguities: Annotated[list[IntentAmbiguity], Field(max_length=20)]

    @model_validator(mode="after")
    def validate_total_json_size(self) -> SearchIntentDraft:
        canonical = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(canonical) > MAX_INTENT_JSON_BYTES:
            raise ValueError("intent JSON exceeds 49,152 UTF-8 bytes")
        return self


class NormalizedSearchIntent(SearchIntentDraft):
    schema_version: Literal["2.0"]
    provenance: IntentProvenance

    @property
    def has_blocking_ambiguity(self) -> bool:
        return any(ambiguity.blocking for ambiguity in self.ambiguities)


def _contains_forbidden_control(value: str) -> bool:
    return any(
        unicodedata.category(character).startswith("C") and not character.isspace()
        for character in value
    )


def _normalize_required_text(value: str, *, field_name: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    if _contains_forbidden_control(normalized):
        raise ValueError(f"{field_name} contains a forbidden control character")
    collapsed = " ".join(normalized.split())
    if not collapsed:
        raise ValueError(f"{field_name} must not be empty")
    return collapsed


def _normalize_optional_text(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", value)
    if _contains_forbidden_control(normalized):
        raise ValueError(f"{field_name} contains a forbidden control character")
    collapsed = " ".join(normalized.split())
    return collapsed or None


def _normalize_terms(values: list[str], *, field_name: str) -> list[str]:
    normalized_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalize_optional_text(value, field_name=field_name)
        if normalized is None:
            continue
        identity = normalized.casefold()
        if identity in seen:
            continue
        seen.add(identity)
        normalized_values.append(normalized)
    return normalized_values


def _validated_source_input(source_input: str) -> str:
    if type(source_input) is not str:
        raise TypeError("source_input must be a string")
    if len(source_input) > MAX_SOURCE_INPUT_CODEPOINTS:
        raise ValueError("source_input exceeds 2,000 Unicode code points")
    return _normalize_required_text(source_input, field_name="source_input")


def _artifact_sha256(value: bytes, *, field_name: str) -> str:
    if type(value) is not bytes:
        raise TypeError(f"{field_name} must be exact bytes")
    if not value or len(value) > MAX_BOUND_ARTIFACT_BYTES:
        raise ValueError(f"{field_name} must contain between 1 and 1,048,576 bytes")
    return hashlib.sha256(value).hexdigest()


def build_intent_provenance(
    *,
    source_input: str,
    prompt: bytes,
    schema: bytes,
    response: bytes,
) -> IntentProvenance:
    _validated_source_input(source_input)
    return IntentProvenance(
        source_input_sha256=hashlib.sha256(source_input.encode("utf-8")).hexdigest(),
        prompt_sha256=_artifact_sha256(prompt, field_name="prompt"),
        schema_sha256=_artifact_sha256(schema, field_name="schema"),
        response_sha256=_artifact_sha256(response, field_name="response"),
    )


def normalize_search_intent(
    source_input: str,
    draft: SearchIntentDraft,
    *,
    provenance: IntentProvenance,
) -> NormalizedSearchIntent:
    draft = SearchIntentDraft.model_validate(draft)
    provenance = IntentProvenance.model_validate(provenance)
    normalized_source = _validated_source_input(source_input)
    expected_source_sha256 = hashlib.sha256(source_input.encode("utf-8")).hexdigest()
    if provenance.source_input_sha256 != expected_source_sha256:
        raise ValueError("provenance does not match source_input")

    normalized_ambiguities = [
        IntentAmbiguity(
            code=ambiguity.code,
            message=_normalize_required_text(ambiguity.message, field_name="ambiguity.message"),
            blocking=ambiguity.blocking,
        )
        for ambiguity in draft.ambiguities
    ]

    brand = _normalize_optional_text(draft.brand, field_name="brand")
    model_number = _normalize_optional_text(draft.model_number, field_name="model_number")
    source_identity = normalized_source.casefold()
    if brand is not None and brand.casefold() not in source_identity:
        brand = None
    if model_number is not None and model_number.casefold() not in source_identity:
        model_number = None

    return NormalizedSearchIntent(
        schema_version="2.0",
        product_name_ja=_normalize_optional_text(
            draft.product_name_ja,
            field_name="product_name_ja",
        ),
        product_name_en=_normalize_optional_text(
            draft.product_name_en,
            field_name="product_name_en",
        ),
        category_ja=_normalize_optional_text(draft.category_ja, field_name="category_ja"),
        category_en=_normalize_optional_text(draft.category_en, field_name="category_en"),
        required_terms_ja=_normalize_terms(
            draft.required_terms_ja,
            field_name="required_terms_ja",
        ),
        required_terms_en=_normalize_terms(
            draft.required_terms_en,
            field_name="required_terms_en",
        ),
        preferred_terms_ja=_normalize_terms(
            draft.preferred_terms_ja,
            field_name="preferred_terms_ja",
        ),
        preferred_terms_en=_normalize_terms(
            draft.preferred_terms_en,
            field_name="preferred_terms_en",
        ),
        negative_terms_ja=_normalize_terms(
            draft.negative_terms_ja,
            field_name="negative_terms_ja",
        ),
        negative_terms_en=_normalize_terms(
            draft.negative_terms_en,
            field_name="negative_terms_en",
        ),
        color_ja=_normalize_optional_text(draft.color_ja, field_name="color_ja"),
        color_en=_normalize_optional_text(draft.color_en, field_name="color_en"),
        features_ja=_normalize_terms(draft.features_ja, field_name="features_ja"),
        features_en=_normalize_terms(draft.features_en, field_name="features_en"),
        brand=brand,
        model_number=model_number,
        price=draft.price,
        typed_conditions=draft.typed_conditions,
        ambiguities=normalized_ambiguities,
        provenance=provenance,
    )


def search_intent_sha256(intent: NormalizedSearchIntent) -> str:
    intent = NormalizedSearchIntent.model_validate(intent)
    canonical = json.dumps(
        intent.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(b"amazon-explorer-search-intent-v2\n" + canonical).hexdigest()
