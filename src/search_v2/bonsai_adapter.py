from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from decimal import InvalidOperation
import re
from typing import Annotated
from typing import Literal
from typing import NoReturn
from typing import get_args
import unicodedata

from pydantic import Field
from pydantic import StringConstraints
from pydantic import ValidationError
from pydantic import model_validator

from src.exceptions import BonsaiResponseError
from src.search_v2.intent import BonsaiTypedConditionCandidate
from src.search_v2.dynamic_attributes import custom_condition_grounded
from src.search_v2.intent import BonsaiAttributeDefinition
from src.search_v2.intent import BonsaiBooleanTarget
from src.search_v2.intent import BonsaiDecimalTarget
from src.search_v2.intent import BonsaiEnumTarget
from src.search_v2.intent import BonsaiIntegerTarget
from src.search_v2.intent import BonsaiSemanticTarget
from src.search_v2.intent import BonsaiTextSetTarget
from src.search_v2.intent import CandidateDecimal
from src.search_v2.intent import Confidence
from src.search_v2.intent import IntentAmbiguity
from src.search_v2.intent import MAX_BOUND_ARTIFACT_BYTES
from src.search_v2.intent import MAX_PRICE_JPY
from src.search_v2.intent import NormalizedSearchIntent
from src.search_v2.intent import PriceCondition
from src.search_v2.intent import PriceValue
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import StrictContract
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent
from src.search_v2.query_planner import build_search_query_plan
from src.search_v2.tokenizer import _AnalyzedSource
from src.search_v2.tokenizer import _MorphemeSpan
from src.search_v2.tokenizer import _analyze_japanese_source
from src.search_v2.typed_requirements import _OPERATORS_BY_TYPE
from src.search_v2.typed_requirements import RequirementOperator
from src.search_v2.typed_requirements import RequirementStrength
from src.search_v2.typed_requirements import DEFAULT_ATTRIBUTE_REGISTRY
from src.search_v2.typed_requirements import TypedRequirementError
from src.search_v2.typed_requirements import attribute_definition
from src.search_v2.usage_ledger import MAX_USAGE_TOKENS


_INVALID_RESPONSE_MESSAGE = "Bonsai response did not match the search intent contract"
_FAILURE_STAGES = frozenset(
    {
        "response_metadata_invalid",
        "envelope_invalid",
        "content_not_json",
        "draft_schema_invalid",
        "intent_normalization_invalid",
        "intent_searchability_invalid",
        "output_truncated",
    }
)
_FINISH_REASONS = frozenset({"stop", "length", "other", "missing"})
_DRAFT_FAILURE_GROUPS = frozenset(
    {
        "not_applicable",
        "document",
        "fields",
        "price",
        "typed_conditions",
        "ambiguities",
        "multiple",
    }
)
_SEARCHABILITY_FAILURE_GROUPS = frozenset(
    {
        "not_applicable",
        "missing_terms",
        "invalid_terms",
    }
)
_APPLICATION_DECIMAL_PATTERN = r"^-?(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{1,6})?$"
_GENERATION_DECIMAL_PATTERN = r"^-?(0|[1-9][0-9]{0,12})(\.[0-9]{1,6})?$"
_AMBIGUITY_CODE_PATTERN = r"^[a-z][a-z0-9_]{0,49}$"
_COMPACT_PRICE_DEFINITION = "BonsaiCompactPriceCondition"
_COMPACT_AMBIGUITY_DEFINITION = "BonsaiCompactIntentAmbiguity"
_COMPACT_INTEGER_DEFINITION = "BonsaiCompactIntegerTarget"
_COMPACT_DECIMAL_DEFINITION = "BonsaiCompactDecimalTarget"
_COMPACT_TYPED_CONDITION_DEFINITION = "BonsaiCompactTypedConditionCandidate"
_MAX_WIRE_NAME_CHARACTERS = 48
_MAX_WIRE_TERM_CHARACTERS = 32
_MAX_WIRE_AMBIGUITY_CHARACTERS = 96
_MAX_WIRE_TERM_ITEMS = 4
_MAX_WIRE_TYPED_CONDITIONS = 4
_MAX_WIRE_SET_ITEMS = 4
_MAX_WIRE_AMBIGUITIES = 2
_SEARCHABLE_WIRE_FIELDS = (
    "product_name_ja",
    "product_name_en",
    "required_terms_ja",
    "required_terms_en",
    "preferred_terms_ja",
    "preferred_terms_en",
    "negative_terms_ja",
    "negative_terms_en",
    "brand",
    "model_number",
    "price",
    "typed_conditions",
)
_BLOCKING_WIRE_FIELDS = ("ambiguities",)
_PRICE_FIELDS = (
    "currency",
    "mode",
    "target_jpy",
    "min_jpy",
    "max_jpy",
    "source",
    "confidence",
)
_JPY_AMOUNT_PATTERN = re.compile(
    r"(?<![0-9,.])"
    r"(?P<number>"
    r"(?:[1-9][0-9]{0,2}(?:,[0-9]{3}){1,3})"
    r"|(?:(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,4})?)"
    r")"
    r"(?![0-9,.])\s*(?P<scale>[万千])?\s*円"
)
_ENGLISH_WITHOUT_PATTERN = re.compile(
    r"(?i)\bwithout\s+(?:a\s+|an\s+|the\s+)?(?P<term>[^,.;!?]{1,32})"
)
_JAPANESE_CHARACTER_PATTERN = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
_URL_PATTERN = re.compile(r"(?i)(?:[a-z][a-z0-9+.-]*://|www\.)")
_NEGATIVE_MARKERS = frozenset({"なし", "不要", "無し", "無い", "除外", "避ける"})
_NEGATIVE_PARTICLES = frozenset({"は", "を"})
_TARGET_BOUNDARY_PARTICLES = frozenset({"が", "けど", "で", "では", "なら", "ならば"})
_CLAUSE_BOUNDARIES = frozenset({",", ".", "!", "?", "、", "。", "！", "？", ";", "；"})
_NEGATIVE_SUFFIXES = frozenset({"為る", "する", "たい", "です", "だ", "ます", "と"})
_SOURCE_PRODUCT_UNGROUNDED_CODE = "source_product_ungrounded"
_SOURCE_PRODUCT_UNGROUNDED_MESSAGE = (
    "生成された商品種別を入力本文へ根拠付けできませんでした。商品種別を確認してください。"
)

BonsaiResponseFailureStage = Literal[
    "response_metadata_invalid",
    "envelope_invalid",
    "content_not_json",
    "draft_schema_invalid",
    "intent_normalization_invalid",
    "intent_searchability_invalid",
    "output_truncated",
]
BonsaiFinishReason = Literal["stop", "length", "other", "missing"]
BonsaiDraftFailureGroup = Literal[
    "not_applicable",
    "document",
    "fields",
    "price",
    "typed_conditions",
    "ambiguities",
    "multiple",
]
BonsaiSearchabilityFailureGroup = Literal[
    "not_applicable",
    "missing_terms",
    "invalid_terms",
]

WireNameText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=_MAX_WIRE_NAME_CHARACTERS),
]
WireTermText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=_MAX_WIRE_TERM_CHARACTERS),
]
WireAmbiguityMessage = Annotated[
    str,
    StringConstraints(min_length=1, max_length=_MAX_WIRE_AMBIGUITY_CHARACTERS),
]
WireTermList = Annotated[list[WireTermText], Field(max_length=_MAX_WIRE_TERM_ITEMS)]
WireSetValues = Annotated[
    list[WireTermText],
    Field(min_length=1, max_length=_MAX_WIRE_SET_ITEMS),
]
WireIntegerValue = Annotated[
    int,
    Field(ge=-1_000_000_000_000, le=1_000_000_000_000),
]
WireAttributeKey = Literal[
    "custom",
    "appearance.color",
    "appearance.style",
    "dimensions.width",
    "form.shape",
    "form.orientation",
    "material.type",
]
WireEnumValue = Literal[
    "cylindrical",
    "oval",
    "rectangular",
    "round",
    "spherical",
    "square",
    "bone_china",
    "earthenware",
    "glass",
    "plastic",
    "porcelain",
    "stainless_steel",
    "stoneware",
    "wood",
    "black",
    "blue",
    "brown",
    "gray",
    "green",
    "red",
    "silver",
    "white",
    "horizontal",
    "vertical",
]

_TYPED_CONDITION_VALUE_PROFILES = (
    (
        (
            "appearance.color",
            "form.shape",
            "form.orientation",
            "material.type",
        ),
        ("equals", "one_of"),
        "enum",
        "BonsaiCompactEnumTarget",
        ("required", "preferred", "excluded"),
    ),
    (
        ("dimensions.width",),
        ("equals", "at_least", "at_most", "between"),
        "decimal",
        "BonsaiCompactDecimalTarget",
        ("required", "preferred", "excluded"),
    ),
    (
        ("appearance.style",),
        ("similar_to",),
        "semantic",
        "BonsaiCompactSemanticTarget",
        ("preferred",),
    ),
)
_TYPED_CONDITION_PROFILE_BY_KEY = {
    attribute_key: (value_type, frozenset(operators), frozenset(strengths))
    for attribute_keys, operators, value_type, _target_definition, strengths in (
        _TYPED_CONDITION_VALUE_PROFILES
    )
    for attribute_key in attribute_keys
}


class BonsaiCompactBooleanTarget(StrictContract):
    value_type: Literal["boolean"]
    value: bool


class BonsaiCompactEnumTarget(StrictContract):
    value_type: Literal["enum"]
    values: Annotated[
        list[Annotated[str, StringConstraints(min_length=1, max_length=32)]],
        Field(min_length=1, max_length=_MAX_WIRE_SET_ITEMS),
    ]


class BonsaiCompactIntegerTarget(StrictContract):
    value_type: Literal["integer"]
    minimum: WireIntegerValue | None = None
    maximum: WireIntegerValue | None = None
    unit: Annotated[str, StringConstraints(min_length=1, max_length=32)]

    @model_validator(mode="after")
    def validate_bound(self) -> BonsaiCompactIntegerTarget:
        if self.minimum is None and self.maximum is None:
            raise ValueError("compact integer target requires a bound")
        return self


class BonsaiCompactDecimalTarget(StrictContract):
    value_type: Literal["decimal"]
    minimum: CandidateDecimal | None = None
    maximum: CandidateDecimal | None = None
    unit: Annotated[str, StringConstraints(min_length=1, max_length=32)]

    @model_validator(mode="after")
    def validate_bound(self) -> BonsaiCompactDecimalTarget:
        if self.minimum is None and self.maximum is None:
            raise ValueError("compact decimal target requires a bound")
        return self


class BonsaiCompactTextSetTarget(StrictContract):
    value_type: Literal["text_set"]
    values: WireSetValues


class BonsaiCompactSemanticTarget(StrictContract):
    value_type: Literal["semantic"]
    label: Literal["gaming", "industrial", "minimal"]


BonsaiCompactRequirementTarget = Annotated[
    BonsaiCompactBooleanTarget
    | BonsaiCompactEnumTarget
    | BonsaiCompactIntegerTarget
    | BonsaiCompactDecimalTarget
    | BonsaiCompactTextSetTarget
    | BonsaiCompactSemanticTarget,
    Field(discriminator="value_type"),
]


def _numeric_attribute_meaning(label: str, unit: str) -> str:
    return f"{label}を表す数量（単位{unit}）"


class BonsaiCompactTypedConditionCandidate(StrictContract):
    attribute_definition: BonsaiAttributeDefinition | None = None
    attribute_key: WireAttributeKey
    operator: RequirementOperator
    expected_value: BonsaiCompactRequirementTarget
    strength: RequirementStrength

    @model_validator(mode="after")
    def validate_registry_shape(self) -> BonsaiCompactTypedConditionCandidate:
        if self.attribute_key == "custom":
            if self.attribute_definition is None:
                raise ValueError("custom conditions require an attribute definition")
            return self
        if self.attribute_definition is not None:
            raise ValueError("registered attributes cannot be redefined")
        expected_type, operators, strengths = _TYPED_CONDITION_PROFILE_BY_KEY[self.attribute_key]
        if (
            self.expected_value.value_type != expected_type
            or self.operator not in operators
            or self.strength not in strengths
        ):
            raise ValueError("compact typed condition does not match the registry shape")
        value = self.expected_value
        if value.value_type == "enum" and not set(value.values).issubset(get_args(WireEnumValue)):
            raise ValueError("registered enum value is invalid")
        if value.value_type == "integer" and value.unit != "count":
            raise ValueError("registered integer unit is invalid")
        if value.value_type == "decimal" and value.unit != "mm":
            raise ValueError("registered decimal unit is invalid")
        return self

    def to_candidate(self) -> BonsaiTypedConditionCandidate:
        return BonsaiTypedConditionCandidate.model_validate(self.model_dump(mode="json"))


class BonsaiCompactIntentAmbiguity(StrictContract):
    code: Annotated[str, StringConstraints(pattern=_AMBIGUITY_CODE_PATTERN)]
    message: WireAmbiguityMessage
    blocking: Literal[True]

    def to_ambiguity(self) -> IntentAmbiguity:
        return IntentAmbiguity.model_validate(self.model_dump(mode="json"))


class BonsaiCompactPriceCondition(StrictContract):
    """Sparse provider wire price expanded into the complete application contract."""

    currency: Literal["JPY"] = "JPY"
    mode: Literal["exact", "range", "min", "max", "none"]
    target_jpy: PriceValue | None = None
    min_jpy: PriceValue | None = None
    max_jpy: PriceValue | None = None
    source: Literal["explicit", "inferred", "none"]
    confidence: Confidence | None = None

    @model_validator(mode="after")
    def validate_complete_price_contract(self) -> BonsaiCompactPriceCondition:
        if self.source == "explicit" and "confidence" in self.model_fields_set:
            raise ValueError("explicit compact price must omit confidence")
        self.to_price_condition()
        return self

    def to_price_condition(self) -> PriceCondition:
        return PriceCondition(
            currency=self.currency,
            mode=self.mode,
            target_jpy=self.target_jpy,
            min_jpy=self.min_jpy,
            max_jpy=self.max_jpy,
            source=self.source,
            confidence=self.confidence,
        )


def _no_price() -> BonsaiCompactPriceCondition:
    return BonsaiCompactPriceCondition(mode="none", source="none")


def _normalized_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _japanese_span_phrase(source: _AnalyzedSource, candidate: str) -> str | None:
    identity = _normalized_text(candidate)
    for start_index, start in enumerate(source.morphemes):
        for end in source.morphemes[start_index:]:
            phrase = source.text[start.begin : end.end]
            phrase_identity = _normalized_text(phrase)
            if phrase_identity == identity:
                return unicodedata.normalize("NFKC", candidate)
            if (
                start is end
                and len(identity) == 1
                and phrase_identity in {f"{identity}い", f"{identity}色"}
            ):
                return unicodedata.normalize("NFKC", candidate)
            if len(phrase_identity) > len(identity) + 1:
                break
    return None


def _ascii_source_phrase(source: str, candidate: str) -> str | None:
    identity = _normalized_text(candidate)
    pattern = re.compile(rf"(?<![a-z0-9_]){re.escape(identity)}(?![a-z0-9_])")
    if pattern.search(source) is None:
        return None
    return unicodedata.normalize("NFKC", candidate)


def _source_phrase(source: _AnalyzedSource, candidates: tuple[str, ...]) -> str | None:
    matches: list[tuple[int, int, str]] = []
    for candidate in candidates:
        normalized_candidate = unicodedata.normalize("NFKC", candidate)
        if _JAPANESE_CHARACTER_PATTERN.search(normalized_candidate):
            phrase = _japanese_span_phrase(source, normalized_candidate)
        else:
            phrase = _ascii_source_phrase(source.text, normalized_candidate)
        if phrase is None:
            continue
        position = source.text.find(_normalized_text(phrase))
        matches.append((position, -len(phrase), phrase))
    if not matches:
        return None
    return min(matches)[2]


def _grounded_value(source: _AnalyzedSource, value: str | None) -> str | None:
    if value is None:
        return None
    if _URL_PATTERN.search(value):
        return value
    return _source_phrase(source, (value,))


def _grounded_terms(source: _AnalyzedSource, values: list[str]) -> list[str]:
    return [
        grounded for value in values if (grounded := _grounded_value(source, value)) is not None
    ]


def _value_source_phrases(
    source: _AnalyzedSource,
    candidate: BonsaiTypedConditionCandidate,
) -> list[str]:
    try:
        definition = attribute_definition(candidate.attribute_key)
    except TypedRequirementError:
        return []
    if (
        candidate.operator not in definition.allowed_operators
        or candidate.strength not in definition.allowed_strengths
        or candidate.expected_value.value_type != definition.value_type
    ):
        return []

    value = candidate.expected_value
    if type(value) is BonsaiEnumTarget:
        if len(value.values) != len(set(value.values)):
            return []
        if candidate.operator == "equals" and len(value.values) != 1:
            return []
        evidence: list[str] = []
        for expected in value.values:
            if expected not in definition.allowed_values:
                return []
            aliases = tuple(
                item.alias for item in definition.value_aliases if item.canonical == expected
            )
            phrase = _source_phrase(source, (expected, *aliases))
            if phrase is None:
                return []
            evidence.append(phrase)
        return evidence
    if type(value) is BonsaiSemanticTarget:
        if value.label not in definition.allowed_values:
            return []
        aliases = tuple(
            item.alias for item in definition.value_aliases if item.canonical == value.label
        )
        phrase = _source_phrase(source, (value.label, *aliases))
        return [] if phrase is None else [phrase]
    if type(value) is BonsaiTextSetTarget:
        if len(value.values) != len({_normalized_text(item) for item in value.values}):
            return []
        evidence = [_source_phrase(source, (item,)) for item in value.values]
        return [] if any(item is None for item in evidence) else [item for item in evidence if item]
    if type(value) is BonsaiBooleanTarget:
        if not value.value:
            return []
        phrase = _source_phrase(source, definition.aliases)
        return [] if phrase is None else [phrase]
    if type(value) in {BonsaiIntegerTarget, BonsaiDecimalTarget}:
        if candidate.operator == "equals" and not (
            value.minimum is not None
            and value.maximum is not None
            and value.minimum == value.maximum
        ):
            return []
        if candidate.operator == "at_least" and not (
            value.minimum is not None and value.maximum is None
        ):
            return []
        if candidate.operator == "at_most" and not (
            value.minimum is None and value.maximum is not None
        ):
            return []
        if candidate.operator == "between" and not (
            value.minimum is not None
            and value.maximum is not None
            and Decimal(value.minimum) <= Decimal(value.maximum)
        ):
            return []
        attribute_phrase = _source_phrase(source, definition.aliases)
        if attribute_phrase is None:
            return []
        bounds = tuple(str(item) for item in (value.minimum, value.maximum) if item is not None)
        if any(_source_phrase(source, (bound,)) is None for bound in bounds):
            return []
        units = (
            value.unit,
            *(item.alias for item in definition.unit_aliases if item.canonical == value.unit),
        )
        if _source_phrase(source, units) is None:
            return []
        return [attribute_phrase]
    return []


def _untyped_source_phrases(
    source: _AnalyzedSource,
    candidate: BonsaiTypedConditionCandidate,
) -> list[str]:
    value = candidate.expected_value
    if type(value) in {BonsaiEnumTarget, BonsaiTextSetTarget}:
        evidence: list[str] = []
        for expected in value.values:
            aliases = tuple(
                item.alias
                for definition in DEFAULT_ATTRIBUTE_REGISTRY.definitions
                for item in definition.value_aliases
                if item.canonical == expected
            )
            phrase = _source_phrase(source, (expected, *aliases))
            if phrase is not None:
                evidence.append(phrase)
        return evidence
    if type(value) is BonsaiSemanticTarget:
        aliases = tuple(
            item.alias
            for definition in DEFAULT_ATTRIBUTE_REGISTRY.definitions
            for item in definition.value_aliases
            if item.canonical == value.label
        )
        phrase = _source_phrase(source, (value.label, *aliases))
        return [] if phrase is None else [phrase]
    return []


def _jpy_amount(match: re.Match[str]) -> int | None:
    scale = {None: 1, "千": 1_000, "万": 10_000}[match.group("scale")]
    try:
        amount = Decimal(match.group("number").replace(",", "")) * scale
    except InvalidOperation:
        return None
    if amount != amount.to_integral_value():
        return None
    integer = int(amount)
    return integer if 0 < integer <= MAX_PRICE_JPY else None


def _normalized_between(source: _AnalyzedSource, start: int, end: int) -> list[str]:
    return [
        morpheme.normalized
        for morpheme in source.morphemes
        if morpheme.begin >= start
        and morpheme.end <= end
        and morpheme.surface not in _CLAUSE_BOUNDARIES
    ]


def _relation_after(source: _AnalyzedSource, position: int) -> str | None:
    for morpheme in source.morphemes:
        if morpheme.begin < position:
            continue
        if source.text[position : morpheme.begin].strip():
            return None
        return morpheme.normalized
    return None


def _explicit_source_price(source: _AnalyzedSource) -> PriceCondition | None:
    matches = list(_JPY_AMOUNT_PATTERN.finditer(source.text))
    if not 1 <= len(matches) <= 2:
        return None
    amounts = [_jpy_amount(match) for match in matches]
    if any(amount is None for amount in amounts):
        return None

    if len(matches) == 2:
        between = source.text[matches[0].end() : matches[1].start()]
        between_words = _normalized_between(
            source,
            matches[0].end(),
            matches[1].start(),
        )
        second_relation = _relation_after(source, matches[1].end())
        is_range = between_words == ["から"] or bool(
            re.fullmatch(r"\s*(?:~|〜|～|-|–|—)\s*", between)
        )
        is_bounded_range = between_words == ["以上"] and second_relation in {"以下", "以内"}
        if not (is_range or is_bounded_range):
            return None
        minimum, maximum = amounts
        if minimum is None or maximum is None or minimum > maximum:
            return None
        return PriceCondition(
            currency="JPY",
            mode="range",
            target_jpy=None,
            min_jpy=minimum,
            max_jpy=maximum,
            source="explicit",
            confidence=None,
        )

    amount = amounts[0]
    relation = _relation_after(source, matches[0].end())
    if relation in {"以内", "以下", "まで", "未満"}:
        mode = "max"
    elif relation == "以上":
        mode = "min"
    else:
        return None
    return PriceCondition(
        currency="JPY",
        mode=mode,
        target_jpy=None,
        min_jpy=amount if mode == "min" else None,
        max_jpy=amount if mode == "max" else None,
        source="explicit",
        confidence=None,
    )


def _dedupe_terms(terms: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for term in terms:
        identity = _normalized_text(term)
        if not term or len(term) > 100 or identity in seen:
            continue
        seen.add(identity)
        result.append(term)
    return result


def _marker_ends_clause(morphemes: tuple[_MorphemeSpan, ...], marker_index: int) -> bool:
    for morpheme in morphemes[marker_index + 1 :]:
        if morpheme.surface in _CLAUSE_BOUNDARIES:
            return True
        if morpheme.normalized not in _NEGATIVE_SUFFIXES:
            return False
    return True


def _has_prior_negative_marker(
    morphemes: tuple[_MorphemeSpan, ...],
    marker_index: int,
) -> bool:
    for morpheme in reversed(morphemes[:marker_index]):
        if morpheme.surface in _CLAUSE_BOUNDARIES:
            return False
        if morpheme.normalized in _NEGATIVE_MARKERS:
            return True
    return False


def _negative_target(source: _AnalyzedSource, marker_index: int) -> str | None:
    morphemes = source.morphemes
    target_end = marker_index
    if target_end > 0 and morphemes[target_end - 1].normalized in _NEGATIVE_PARTICLES:
        target_end -= 1
    if target_end == 0:
        return None

    target_start = target_end - 1
    while target_start > 0:
        previous = morphemes[target_start - 1]
        if previous.surface in _CLAUSE_BOUNDARIES:
            break
        if previous.normalized in _TARGET_BOUNDARY_PARTICLES:
            break
        target_start -= 1

    value = source.text[morphemes[target_start].begin : morphemes[target_end - 1].end].strip()
    return value or None


def _explicit_negative_terms(source: _AnalyzedSource) -> tuple[list[str], list[str]]:
    japanese_terms: list[str] = []
    for index, morpheme in enumerate(source.morphemes):
        if morpheme.normalized not in _NEGATIVE_MARKERS:
            continue
        if morpheme.normalized in {"なし", "無し", "無い"} and _has_prior_negative_marker(
            source.morphemes,
            index,
        ):
            continue
        if not _marker_ends_clause(source.morphemes, index):
            continue
        target = _negative_target(source, index)
        if target is not None:
            japanese_terms.append(target)
    english_terms = [
        match.group("term").strip() for match in _ENGLISH_WITHOUT_PATTERN.finditer(source.text)
    ]
    return _dedupe_terms(japanese_terms), _dedupe_terms(english_terms)


def _is_price_term(value: str) -> bool:
    return _JPY_AMOUNT_PATTERN.fullmatch(unicodedata.normalize("NFKC", value).strip()) is not None


def _append_unique(values: list[str], additions: list[str]) -> list[str]:
    result = [item for item in values if not _is_price_term(item)]
    identities = {_normalized_text(item) for item in result}
    for item in additions:
        identity = _normalized_text(item)
        if identity in identities:
            continue
        identities.add(identity)
        result.append(item)
    return result


def _material_term_conditions(
    terms_by_strength: tuple[tuple[str, list[str]], ...],
    existing: list[BonsaiTypedConditionCandidate],
) -> list[BonsaiTypedConditionCandidate]:
    definition = attribute_definition("material.type")
    aliases = {_normalized_text(value): value for value in definition.allowed_values}
    aliases.update(
        {_normalized_text(item.alias): item.canonical for item in definition.value_aliases}
    )
    conditions = list(existing)
    for strength, terms in terms_by_strength:
        for term in terms:
            canonical = aliases.get(_normalized_text(term))
            if canonical is None:
                continue
            if any(
                item.attribute_key == definition.attribute_key
                and item.strength == strength
                and type(item.expected_value) is BonsaiEnumTarget
                and canonical in item.expected_value.values
                for item in conditions
            ):
                continue
            conditions.append(
                BonsaiTypedConditionCandidate.model_validate(
                    {
                        "attribute_key": definition.attribute_key,
                        "operator": "equals",
                        "expected_value": {"value_type": "enum", "values": [canonical]},
                        "strength": strength,
                    }
                )
            )
    return conditions


def _missing_material(
    source: _AnalyzedSource, candidates: list[BonsaiTypedConditionCandidate]
) -> bool:
    if _source_phrase(source, ("ceramic", "pottery", "陶磁器", "セラミック")) is not None:
        return True
    definition = attribute_definition("material.type")
    covered = {
        value
        for candidate in candidates
        if candidate.attribute_key == definition.attribute_key
        and type(candidate.expected_value) is BonsaiEnumTarget
        for value in candidate.expected_value.values
    }
    for value in definition.allowed_values:
        aliases = tuple(item.alias for item in definition.value_aliases if item.canonical == value)
        if value not in covered and _source_phrase(source, (value, *aliases)) is not None:
            return True
    return False


_BOUNDED_QUANTITY = re.compile(
    r"(?<![0-9.])(?P<number>[0-9]+(?:\.[0-9]+)?)\s*"
    r"(?P<unit>[a-zA-Z%℃°一-龥]{1,12}?)\s*(?P<relation>以上|以下|以内|未満|超)"
)


def _missing_quantity(source, candidates):
    covered = []
    for candidate in candidates:
        if candidate.attribute_definition is not None and candidate.expected_value.value_type in {
            "integer",
            "decimal",
        }:
            quote = _normalized_text(candidate.attribute_definition.source_quote)
            start = source.text.find(quote)
            if start >= 0:
                covered.append((start, start + len(quote)))
    for candidate in candidates:
        value = candidate.expected_value
        if (
            candidate.attribute_key == "dimensions.width"
            and candidate.operator == "between"
            and value.value_type == "decimal"
        ):
            pattern = (
                r"幅\s*(?:は|が|:|=)?\s*(?P<minimum>[0-9]+(?:\.[0-9]+)?)\s*"
                + re.escape(value.unit)
                + r"\s*以上[\s、,]*(?P<maximum>[0-9]+(?:\.[0-9]+)?)\s*"
                + re.escape(value.unit)
                + r"\s*(?:以下|以内)"
            )
            for interval in re.finditer(pattern, source.text):
                if (
                    value.minimum is not None
                    and value.maximum is not None
                    and Decimal(interval.group("minimum")) == Decimal(value.minimum)
                    and Decimal(interval.group("maximum")) == Decimal(value.maximum)
                ):
                    covered.append(interval.span())
    for match in _BOUNDED_QUANTITY.finditer(source.text):
        if match.group("unit") in {"円", "万円", "千円"}:
            continue
        if any(start <= match.start() and match.end() <= end for start, end in covered):
            continue
        # The common width preset has no quote; require its label beside this exact quantity.
        width_covered = False
        for candidate in candidates:
            if candidate.attribute_key != "dimensions.width":
                continue
            value = candidate.expected_value
            if value.value_type != "decimal":
                continue
            relation = {"以上": "at_least", "以下": "at_most", "以内": "at_most"}.get(
                match.group("relation")
            )
            amount = value.minimum if relation == "at_least" else value.maximum
            if (
                candidate.operator == relation
                and amount is not None
                and Decimal(amount) == Decimal(match.group("number"))
                and value.unit == match.group("unit")
                and re.search(r"幅\s*(?:は|が|:|=)?\s*$", source.text[: match.start()])
            ):
                width_covered = True
        if not width_covered:
            return True
    return False


def _ground_source_conditions(source: str, draft: SearchIntentDraft) -> SearchIntentDraft:
    from src.search_v2.dynamic_attributes import numeric_identity_requires_review

    if draft.ambiguities:
        return draft

    analyzed_source = _analyze_japanese_source(source)
    product_name_ja = _grounded_value(analyzed_source, draft.product_name_ja)
    product_name_en = _grounded_value(analyzed_source, draft.product_name_en)
    brand = _grounded_value(analyzed_source, draft.brand)
    model_number = _grounded_value(analyzed_source, draft.model_number)
    required_ja = _grounded_terms(analyzed_source, draft.required_terms_ja)
    required_en = _grounded_terms(analyzed_source, draft.required_terms_en)
    preferred_ja = _grounded_terms(analyzed_source, draft.preferred_terms_ja)
    preferred_en = _grounded_terms(analyzed_source, draft.preferred_terms_en)
    negative_ja = _grounded_terms(analyzed_source, draft.negative_terms_ja)
    negative_en = _grounded_terms(analyzed_source, draft.negative_terms_en)
    explicit_negative_ja, explicit_negative_en = _explicit_negative_terms(analyzed_source)
    typed_conditions: list[BonsaiTypedConditionCandidate] = []
    typed_required_ja: list[str] = []
    typed_required_en: list[str] = []
    typed_preferred_ja: list[str] = []
    typed_preferred_en: list[str] = []
    custom_invalid = False
    for candidate in draft.typed_conditions:
        if candidate.attribute_key == "custom":
            if custom_condition_grounded(candidate, analyzed_source, DEFAULT_ATTRIBUTE_REGISTRY):
                typed_conditions.append(candidate)
                # Keep the whole grounded phrase so units, scope and relations survive query planning.
                phrase = candidate.attribute_definition.source_quote
                target_terms = {
                    "required": typed_required_ja,
                    "preferred": typed_preferred_ja,
                    "excluded": negative_ja,
                }
                target_terms[candidate.strength].append(phrase)
            else:
                custom_invalid = True
            continue
        evidence = _value_source_phrases(analyzed_source, candidate)
        if evidence:
            typed_conditions.append(candidate)
        else:
            evidence = _untyped_source_phrases(analyzed_source, candidate)
        if not evidence:
            continue
        is_japanese = any(
            any(
                "HIRAGANA" in unicodedata.name(character, "")
                or "KATAKANA" in unicodedata.name(character, "")
                or "CJK" in unicodedata.name(character, "")
                for character in phrase
            )
            for phrase in evidence
        )
        if candidate.strength == "excluded":
            (negative_ja if is_japanese else negative_en).extend(evidence)
        elif candidate.strength == "preferred":
            (typed_preferred_ja if is_japanese else typed_preferred_en).extend(evidence)
        else:
            (typed_required_ja if is_japanese else typed_required_en).extend(evidence)

    price = _explicit_source_price(analyzed_source) or draft.price
    grounded_required_ja = _append_unique(required_ja, typed_required_ja)
    grounded_required_en = _append_unique(required_en, typed_required_en)
    grounded_preferred_ja = _append_unique(preferred_ja, typed_preferred_ja)
    grounded_preferred_en = _append_unique(preferred_en, typed_preferred_en)
    typed_conditions = _material_term_conditions(
        (
            ("required", grounded_required_ja + grounded_required_en),
            ("preferred", grounded_preferred_ja + grounded_preferred_en),
            ("excluded", negative_ja + negative_en + explicit_negative_ja + explicit_negative_en),
        ),
        typed_conditions,
    )
    ambiguities = list(draft.ambiguities)
    if any(numeric_identity_requires_review(candidate) for candidate in typed_conditions):
        ambiguities.append(
            IntentAmbiguity(
                code="attribute_identity_unresolved",
                message="数値が指す属性名は未確定です。対象の属性名と数値を明記して入力し直してください。",
                blocking=True,
            )
        )
    if _missing_quantity(analyzed_source, typed_conditions):
        ambiguities.append(
            IntentAmbiguity(
                code="numeric_condition_unresolved",
                message="数値・単位・比較条件を属性として確認してください。",
                blocking=True,
            )
        )
    if any(
        name and any(mark in name for mark in "。！？;；\n")
        for name in (product_name_ja, product_name_en)
    ):
        ambiguities.append(
            IntentAmbiguity(
                code="product_condition_mixed",
                message="商品種別と仕様条件を分けて確認してください。",
                blocking=True,
            )
        )
    if custom_invalid:
        ambiguities.append(
            IntentAmbiguity(
                code="custom_condition_unresolved",
                message="追加属性の根拠・単位・条件の関係を確認してください。",
                blocking=True,
            )
        )
    if (
        _missing_material(analyzed_source, typed_conditions)
        or len(typed_conditions) > _MAX_WIRE_TYPED_CONDITIONS
    ):
        ambiguities.append(
            IntentAmbiguity(
                code="material_condition_unresolved",
                message="材質条件を確認してください。",
                blocking=True,
            )
        )
    grounded_positive_scalars = (product_name_ja, product_name_en, brand, model_number)
    grounded_positive_terms = (
        grounded_required_ja,
        grounded_required_en,
        grounded_preferred_ja,
        grounded_preferred_en,
    )
    if not any(value is not None for value in grounded_positive_scalars) and not any(
        grounded_positive_terms
    ):
        ambiguities.append(
            IntentAmbiguity(
                code=_SOURCE_PRODUCT_UNGROUNDED_CODE,
                message=_SOURCE_PRODUCT_UNGROUNDED_MESSAGE,
                blocking=True,
            )
        )
    return SearchIntentDraft.model_validate(
        {
            **draft.model_dump(mode="json"),
            "product_name_ja": product_name_ja,
            "product_name_en": product_name_en,
            "required_terms_ja": grounded_required_ja,
            "required_terms_en": grounded_required_en,
            "preferred_terms_ja": grounded_preferred_ja,
            "preferred_terms_en": grounded_preferred_en,
            "negative_terms_ja": _append_unique(negative_ja, explicit_negative_ja),
            "negative_terms_en": _append_unique(negative_en, explicit_negative_en),
            "brand": brand,
            "model_number": model_number,
            "price": price.model_dump(mode="json"),
            "typed_conditions": [item.model_dump(mode="json") for item in typed_conditions],
            "ambiguities": [item.model_dump(mode="json") for item in ambiguities],
        }
    )


class BonsaiCompactSearchIntentDraft(StrictContract):
    """Bounded Bonsai wire response expanded into the complete application draft."""

    product_name_ja: WireNameText | None = None
    product_name_en: WireNameText | None = None
    required_terms_ja: WireTermList = Field(default_factory=list)
    required_terms_en: WireTermList = Field(default_factory=list)
    preferred_terms_ja: WireTermList = Field(default_factory=list)
    preferred_terms_en: WireTermList = Field(default_factory=list)
    negative_terms_ja: WireTermList = Field(default_factory=list)
    negative_terms_en: WireTermList = Field(default_factory=list)
    brand: WireNameText | None = None
    model_number: WireNameText | None = None
    price: BonsaiCompactPriceCondition = Field(default_factory=_no_price)
    typed_conditions: list[BonsaiCompactTypedConditionCandidate] = Field(
        default_factory=list,
        max_length=_MAX_WIRE_TYPED_CONDITIONS,
    )
    ambiguities: list[BonsaiCompactIntentAmbiguity] = Field(
        default_factory=list,
        max_length=_MAX_WIRE_AMBIGUITIES,
    )

    @model_validator(mode="after")
    def validate_wire_profile(self) -> BonsaiCompactSearchIntentDraft:
        present_fields = frozenset(self.model_fields_set)
        if "ambiguities" in present_fields:
            if present_fields != frozenset(_BLOCKING_WIRE_FIELDS) or not self.ambiguities:
                raise ValueError("blocking compact response must contain only ambiguities")
            return self
        if "product_name_ja" not in present_fields:
            raise ValueError("searchable compact response requires product_name_ja")
        if "price" in present_fields and self.price.mode == "none":
            raise ValueError("compact response must omit an empty price")
        return self

    def to_search_intent_draft(self) -> SearchIntentDraft:
        return SearchIntentDraft(
            product_name_ja=self.product_name_ja,
            product_name_en=self.product_name_en,
            category_ja=None,
            category_en=None,
            required_terms_ja=self.required_terms_ja,
            required_terms_en=self.required_terms_en,
            preferred_terms_ja=self.preferred_terms_ja,
            preferred_terms_en=self.preferred_terms_en,
            negative_terms_ja=self.negative_terms_ja,
            negative_terms_en=self.negative_terms_en,
            color_ja=None,
            color_en=None,
            features_ja=[],
            features_en=[],
            brand=self.brand,
            model_number=self.model_number,
            price=self.price.to_price_condition(),
            typed_conditions=[item.to_candidate() for item in self.typed_conditions],
            ambiguities=[item.to_ambiguity() for item in self.ambiguities],
        )


@dataclass(frozen=True, slots=True)
class BonsaiResponseDiagnostic:
    """Bounded response metadata that is safe to retain after a parse failure."""

    stage: BonsaiResponseFailureStage
    draft_failure_group: BonsaiDraftFailureGroup
    searchability_failure_group: BonsaiSearchabilityFailureGroup
    finish_reason: BonsaiFinishReason
    completion_tokens: int | None
    response_bytes: int

    def __post_init__(self) -> None:
        if type(self.stage) is not str or self.stage not in _FAILURE_STAGES:
            raise ValueError("response failure stage is invalid")
        if (
            type(self.draft_failure_group) is not str
            or self.draft_failure_group not in _DRAFT_FAILURE_GROUPS
        ):
            raise ValueError("draft failure group is invalid")
        if (self.stage == "draft_schema_invalid") != (self.draft_failure_group != "not_applicable"):
            raise ValueError("draft failure group does not match response stage")
        if (
            type(self.searchability_failure_group) is not str
            or self.searchability_failure_group not in _SEARCHABILITY_FAILURE_GROUPS
        ):
            raise ValueError("searchability failure group is invalid")
        if (self.stage == "intent_searchability_invalid") != (
            self.searchability_failure_group != "not_applicable"
        ):
            raise ValueError("searchability failure group does not match response stage")
        if type(self.finish_reason) is not str or self.finish_reason not in _FINISH_REASONS:
            raise ValueError("response finish reason is invalid")
        if self.completion_tokens is not None and (
            type(self.completion_tokens) is not int
            or not 0 <= self.completion_tokens <= MAX_USAGE_TOKENS
        ):
            raise ValueError("response completion token count is invalid")
        if type(self.response_bytes) is not int or not (
            0 <= self.response_bytes <= MAX_BOUND_ARTIFACT_BYTES + 1
        ):
            raise ValueError("response byte count is invalid")


class BonsaiResponseContractError(BonsaiResponseError):
    """Fixed-message response error with no provider body or validation detail."""

    def __init__(self, diagnostic: BonsaiResponseDiagnostic) -> None:
        if type(diagnostic) is not BonsaiResponseDiagnostic:
            raise TypeError("response diagnostic is invalid")
        self.diagnostic = diagnostic
        super().__init__(_INVALID_RESPONSE_MESSAGE)


class _InvalidBonsaiResponse(ValueError):
    pass


def _raise_invalid_response(
    stage: BonsaiResponseFailureStage,
    *,
    response_bytes: int,
    draft_failure_group: BonsaiDraftFailureGroup = "not_applicable",
    searchability_failure_group: BonsaiSearchabilityFailureGroup = "not_applicable",
    finish_reason: BonsaiFinishReason = "missing",
    completion_tokens: int | None = None,
) -> NoReturn:
    error = BonsaiResponseContractError(
        BonsaiResponseDiagnostic(
            stage=stage,
            draft_failure_group=draft_failure_group,
            searchability_failure_group=searchability_failure_group,
            finish_reason=finish_reason,
            completion_tokens=completion_tokens,
            response_bytes=response_bytes,
        )
    )
    raise error from None


def _reject_non_finite_number(value: str) -> NoReturn:
    raise _InvalidBonsaiResponse(f"non-finite JSON number: {value}")


def _object_from_unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _InvalidBonsaiResponse("duplicate JSON object key")
        result[key] = value
    return result


def _load_strict_json(value: str) -> tuple[bool, object | None]:
    try:
        parsed = json.loads(
            value,
            object_pairs_hook=_object_from_unique_pairs,
            parse_constant=_reject_non_finite_number,
        )
    except (RecursionError, TypeError, ValueError):
        return False, None
    return True, parsed


def _extract_content(envelope: object) -> tuple[str, dict[str, object]] | None:
    if type(envelope) is not dict:
        return None

    choices = envelope.get("choices")
    if type(choices) is not list or not choices:
        return None

    first_choice = choices[0]
    if type(first_choice) is not dict:
        return None

    message = first_choice.get("message")
    if type(message) is not dict:
        return None

    content = message.get("content")
    if type(content) is not str or not content.strip():
        return None
    return content, first_choice


def _finish_reason(choice: dict[str, object]) -> BonsaiFinishReason:
    value = choice.get("finish_reason")
    if value is None:
        return "missing"
    if value == "stop":
        return "stop"
    if value == "length":
        return "length"
    return "other"


def _completion_tokens(envelope: object) -> int | None:
    if type(envelope) is not dict:
        return None
    usage = envelope.get("usage")
    if type(usage) is not dict:
        return None
    value = usage.get("completion_tokens")
    if type(value) is not int or not 0 <= value <= MAX_USAGE_TOKENS:
        return None
    return value


def _response_size(response: object) -> int:
    if type(response) is not bytes:
        return 0
    return min(len(response), MAX_BOUND_ARTIFACT_BYTES + 1)


def search_intent_schema_bytes() -> bytes:
    """Return the canonical strict draft schema bound to response provenance."""
    return json.dumps(
        SearchIntentDraft.model_json_schema(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _generation_compatible_schema(value: object) -> object:
    if type(value) is dict:
        result: dict[str, object] = {}
        for key, item in value.items():
            if key == "pattern":
                if item == _APPLICATION_DECIMAL_PATTERN:
                    result[key] = _GENERATION_DECIMAL_PATTERN
                    continue
                if item != _AMBIGUITY_CODE_PATTERN:
                    raise ValueError("search intent schema has an unsupported pattern")
            result[key] = _generation_compatible_schema(item)
        return result
    if type(value) is list:
        return [_generation_compatible_schema(item) for item in value]
    return value


def _schema_choice(schema: object, expected_type: str) -> dict[str, object]:
    if type(schema) is not dict or type(schema.get("anyOf")) is not list:
        raise ValueError("nullable schema is invalid")
    choices = [
        choice
        for choice in schema["anyOf"]
        if type(choice) is dict and choice.get("type") == expected_type
    ]
    if len(choices) != 1:
        raise ValueError("nullable schema choice is invalid")
    return deepcopy(choices[0])


def _price_generation_schema(schema: object) -> dict[str, object]:
    if type(schema) is not dict or type(schema.get("properties")) is not dict:
        raise ValueError("price schema is invalid")
    properties = schema["properties"]
    required = schema.get("required")
    if set(properties) != set(_PRICE_FIELDS) or required != ["mode", "source"]:
        raise ValueError("price schema fields are invalid")

    integer_schemas = {
        field_name: _schema_choice(properties[field_name], "integer")
        for field_name in ("target_jpy", "min_jpy", "max_jpy")
    }
    number_confidence = _schema_choice(properties["confidence"], "number")
    active_by_mode = {
        "exact": ("target_jpy",),
        "range": ("min_jpy", "max_jpy"),
        "min": ("min_jpy",),
        "max": ("max_jpy",),
    }

    variants: list[dict[str, object]] = []
    for mode, active_fields in active_by_mode.items():
        for source in ("explicit", "inferred"):
            variant_properties: dict[str, object] = {
                "mode": {"const": mode, "type": "string"},
            }
            variant_properties.update(
                {field_name: deepcopy(integer_schemas[field_name]) for field_name in active_fields}
            )
            variant_properties["source"] = {"const": source, "type": "string"}
            required_fields = ["mode", *active_fields, "source"]
            if source == "inferred":
                variant_properties["confidence"] = deepcopy(number_confidence)
                required_fields.append("confidence")
            variants.append(
                {
                    "additionalProperties": False,
                    "properties": variant_properties,
                    "required": required_fields,
                    "type": "object",
                }
            )

    return {"oneOf": variants, "title": _COMPACT_PRICE_DEFINITION}


def _bounded_range_generation_schema(
    schema: object,
    *,
    value_type: str,
) -> dict[str, object]:
    if type(schema) is not dict or type(schema.get("properties")) is not dict:
        raise ValueError("compact range target schema is invalid")
    properties = schema["properties"]
    if set(properties) != {"value_type", "minimum", "maximum", "unit"}:
        raise ValueError("compact range target fields are invalid")
    minimum = _schema_choice(properties["minimum"], value_type)
    maximum = _schema_choice(properties["maximum"], value_type)
    common = {"value_type": deepcopy(properties["value_type"])}
    variants: list[dict[str, object]] = []
    for active_fields in (("minimum",), ("maximum",), ("minimum", "maximum")):
        variant_properties = deepcopy(common)
        if "minimum" in active_fields:
            variant_properties["minimum"] = deepcopy(minimum)
        if "maximum" in active_fields:
            variant_properties["maximum"] = deepcopy(maximum)
        variant_properties["unit"] = deepcopy(properties["unit"])
        variants.append(
            {
                "additionalProperties": False,
                "properties": variant_properties,
                "required": ["value_type", *active_fields, "unit"],
                "type": "object",
            }
        )
    return {"oneOf": variants, "title": schema.get("title")}


def _typed_condition_generation_schema(schema: object) -> dict[str, object]:
    if type(schema) is not dict or type(schema.get("properties")) is not dict:
        raise ValueError("compact typed condition schema is invalid")
    properties = schema["properties"]
    if set(properties) != {
        "attribute_key",
        "operator",
        "expected_value",
        "strength",
        "attribute_definition",
    }:
        raise ValueError("compact typed condition fields are invalid")

    variants: list[dict[str, object]] = []
    for (
        attribute_keys,
        operators,
        _value_type,
        target_definition,
        strengths,
    ) in _TYPED_CONDITION_VALUE_PROFILES:
        variants.append(
            {
                "additionalProperties": False,
                "properties": {
                    "attribute_key": {"enum": list(attribute_keys), "type": "string"},
                    "operator": {"enum": list(operators), "type": "string"},
                    "expected_value": {"$ref": f"#/$defs/{target_definition}"},
                    "strength": {"enum": list(strengths), "type": "string"},
                },
                "required": ["attribute_key", "operator", "expected_value", "strength"],
                "type": "object",
            }
        )
    # Bind each custom target type to domain-supported operators during decoding.
    for value_type, target_definitions in (
        ("boolean", ("BonsaiCompactBooleanTarget",)),
        ("enum", ("BonsaiCustomEnumTarget",)),
        ("integer", ("BonsaiCustomIntegerTarget", "BonsaiCustomDecimalTarget")),
        ("text_set", ("BonsaiCompactTextSetTarget",)),
    ):
        targets = [{"$ref": f"#/$defs/{name}"} for name in target_definitions]
        variants.append(
            {
                "additionalProperties": False,
                "properties": {
                    "attribute_key": {"const": "custom", "type": "string"},
                    "attribute_definition": {"$ref": "#/$defs/BonsaiAttributeDefinition"},
                    "strength": deepcopy(properties["strength"]),
                    "operator": {"enum": sorted(_OPERATORS_BY_TYPE[value_type]), "type": "string"},
                    "expected_value": targets[0] if len(targets) == 1 else {"oneOf": targets},
                },
                "required": [
                    "attribute_key",
                    "attribute_definition",
                    "strength",
                    "operator",
                    "expected_value",
                ],
                "type": "object",
            }
        )
    return {"oneOf": variants, "title": schema.get("title")}


def _compact_present_value_generation_schema(schema: object) -> dict[str, object]:
    if type(schema) is not dict or type(schema.get("properties")) is not dict:
        raise ValueError("search intent schema properties are invalid")
    properties = schema["properties"]
    optional_text_fields = (
        "product_name_ja",
        "product_name_en",
        "brand",
        "model_number",
    )
    list_fields = (
        "required_terms_ja",
        "required_terms_en",
        "preferred_terms_ja",
        "preferred_terms_en",
        "negative_terms_ja",
        "negative_terms_en",
        "typed_conditions",
        "ambiguities",
    )
    if not set((*optional_text_fields, *list_fields)).issubset(properties):
        raise ValueError("compact search intent fields are invalid")
    for field_name in optional_text_fields:
        properties[field_name] = _schema_choice(properties[field_name], "string")
    for field_name in list_fields:
        field_schema = properties[field_name]
        if type(field_schema) is not dict or field_schema.get("type") != "array":
            raise ValueError("compact list schema is invalid")
        field_schema["minItems"] = 1
    return schema


def _search_or_blocking_generation_schema(schema: object) -> dict[str, object]:
    if type(schema) is not dict or type(schema.get("$defs")) is not dict:
        raise ValueError("search intent schema definitions are invalid")
    if type(schema.get("properties")) is not dict:
        raise ValueError("search intent schema properties are invalid")
    definitions = schema["$defs"]
    properties = schema["properties"]
    if _COMPACT_AMBIGUITY_DEFINITION not in definitions:
        raise ValueError("ambiguity schema definition is missing")
    ambiguity_definition = definitions[_COMPACT_AMBIGUITY_DEFINITION]
    if (
        type(ambiguity_definition) is not dict
        or type(ambiguity_definition.get("properties")) is not dict
        or "blocking" not in ambiguity_definition["properties"]
    ):
        raise ValueError("ambiguity blocking field is invalid")
    ambiguity_definition["properties"]["blocking"] = {
        "const": True,
        "type": "boolean",
    }
    if set(properties) != set((*_SEARCHABLE_WIRE_FIELDS, *_BLOCKING_WIRE_FIELDS)):
        raise ValueError("searchability schema fields are missing")

    product_name_schema = properties["product_name_ja"]
    if type(product_name_schema) is not dict or product_name_schema.get("type") != "string":
        raise ValueError("compact product name schema is invalid")
    ambiguity_list = properties["ambiguities"]
    if (
        type(ambiguity_list) is not dict
        or ambiguity_list.get("type") != "array"
        or ambiguity_list.get("items") != {"$ref": f"#/$defs/{_COMPACT_AMBIGUITY_DEFINITION}"}
    ):
        raise ValueError("ambiguity list schema is invalid")

    searchable = {
        "additionalProperties": False,
        "maxProperties": len(_SEARCHABLE_WIRE_FIELDS),
        "properties": {
            field_name: deepcopy(properties[field_name]) for field_name in _SEARCHABLE_WIRE_FIELDS
        },
        "required": ["product_name_ja"],
        "type": "object",
    }
    blocking = {
        "additionalProperties": False,
        "maxProperties": len(_BLOCKING_WIRE_FIELDS),
        "properties": {
            field_name: deepcopy(properties[field_name]) for field_name in _BLOCKING_WIRE_FIELDS
        },
        "required": ["ambiguities"],
        "type": "object",
    }
    bounded_schema = {
        key: deepcopy(value)
        for key, value in schema.items()
        if key not in {"additionalProperties", "properties", "required"}
    }
    bounded_schema["anyOf"] = [searchable, blocking]
    return bounded_schema


def _strip_schema_annotations(value: object) -> object:
    if type(value) is dict:
        return {
            key: _strip_schema_annotations(item)
            for key, item in value.items()
            if key not in {"title", "description", "default"}
        }
    if type(value) is list:
        return [_strip_schema_annotations(item) for item in value]
    return value


def search_intent_generation_schema_bytes() -> bytes:
    """Return the compact llama.cpp wire schema with generation-safe constraints."""
    generation_schema = _generation_compatible_schema(
        BonsaiCompactSearchIntentDraft.model_json_schema()
    )
    if type(generation_schema) is not dict or type(generation_schema.get("$defs")) is not dict:
        raise ValueError("search intent schema definitions are invalid")
    definitions = generation_schema["$defs"]
    if _COMPACT_PRICE_DEFINITION not in definitions:
        raise ValueError("price schema definition is missing")
    definitions[_COMPACT_PRICE_DEFINITION] = _price_generation_schema(
        definitions[_COMPACT_PRICE_DEFINITION]
    )
    if _COMPACT_INTEGER_DEFINITION not in definitions:
        raise ValueError("compact integer target definition is missing")
    definitions[_COMPACT_INTEGER_DEFINITION] = _bounded_range_generation_schema(
        definitions[_COMPACT_INTEGER_DEFINITION],
        value_type="integer",
    )
    if _COMPACT_DECIMAL_DEFINITION not in definitions:
        raise ValueError("compact decimal target definition is missing")
    definitions[_COMPACT_DECIMAL_DEFINITION] = _bounded_range_generation_schema(
        definitions[_COMPACT_DECIMAL_DEFINITION],
        value_type="string",
    )
    if _COMPACT_TYPED_CONDITION_DEFINITION not in definitions:
        raise ValueError("compact typed condition definition is missing")
    definitions[_COMPACT_TYPED_CONDITION_DEFINITION] = _typed_condition_generation_schema(
        definitions[_COMPACT_TYPED_CONDITION_DEFINITION]
    )
    for kind, unit in (("Integer", "count"), ("Decimal", "mm")):
        name = f"BonsaiCompact{kind}Target"
        definitions[f"BonsaiCustom{kind}Target"] = deepcopy(definitions[name])
        for variant in definitions[name]["oneOf"]:
            variant["properties"]["unit"] = {"const": unit, "type": "string"}
    definitions["BonsaiCustomEnumTarget"] = deepcopy(definitions["BonsaiCompactEnumTarget"])
    definitions["BonsaiCompactEnumTarget"]["properties"]["values"]["items"] = {
        "enum": list(get_args(WireEnumValue)),
        "type": "string",
    }
    # Reuse scalar bounds across range variants instead of repeating their constraints.
    for kind in ("Integer", "Decimal"):
        name = f"BonsaiCompact{kind}Target"
        shared = f"{kind}Bound"
        definitions[shared] = deepcopy(definitions[name]["oneOf"][0]["properties"]["minimum"])
        for prefix in ("BonsaiCompact", "BonsaiCustom"):
            for variant in definitions[f"{prefix}{kind}Target"]["oneOf"]:
                for bound in ("minimum", "maximum"):
                    if bound in variant["properties"]:
                        variant["properties"][bound] = {"$ref": f"#/$defs/{shared}"}
    # The common registry has no integer preset; only the custom target is used.
    definitions.pop("BonsaiCompactIntegerTarget")
    generation_schema = _compact_present_value_generation_schema(generation_schema)
    generation_schema = _search_or_blocking_generation_schema(generation_schema)
    # llama.cpp makes object property order part of the generated grammar.
    # Sorting would put custom.attribute_definition before attribute_key and
    # make the prompt's key-first custom examples impossible to generate.
    return json.dumps(
        _strip_schema_annotations(generation_schema),
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _draft_failure_group(error: ValidationError) -> BonsaiDraftFailureGroup:
    groups: set[BonsaiDraftFailureGroup] = set()
    for item in error.errors(include_url=False, include_context=False, include_input=False):
        location = item.get("loc")
        if type(location) not in {tuple, list} or not location:
            groups.add("document")
            continue
        first = location[0]
        if first == "price":
            groups.add("price")
        elif first == "typed_conditions":
            groups.add("typed_conditions")
        elif first == "ambiguities":
            groups.add("ambiguities")
        else:
            groups.add("fields")
    if not groups:
        return "document"
    if len(groups) > 1:
        return "multiple"
    return groups.pop()


def _has_declared_search_terms(intent: NormalizedSearchIntent) -> bool:
    scalar_values = (
        intent.product_name_ja,
        intent.product_name_en,
        intent.category_ja,
        intent.category_en,
        intent.brand,
        intent.model_number,
    )
    term_lists = (
        intent.required_terms_ja,
        intent.required_terms_en,
        intent.preferred_terms_ja,
        intent.preferred_terms_en,
    )
    return any(value is not None for value in scalar_values) or any(term_lists)


def parse_bonsai_intent_response(
    *,
    source_input: str,
    prompt: bytes,
    response: bytes,
) -> NormalizedSearchIntent:
    """Parse and source-ground one exact Bonsai response body."""
    response_size = _response_size(response)
    if type(response) is not bytes or not response or len(response) > MAX_BOUND_ARTIFACT_BYTES:
        _raise_invalid_response("response_metadata_invalid", response_bytes=response_size)

    try:
        decoded_response = response.decode("utf-8")
    except UnicodeError:
        decoded_response = None
    if decoded_response is None:
        _raise_invalid_response("envelope_invalid", response_bytes=response_size)

    envelope_ok, envelope = _load_strict_json(decoded_response)
    if not envelope_ok:
        _raise_invalid_response("envelope_invalid", response_bytes=response_size)
    extracted = _extract_content(envelope)
    if extracted is None:
        _raise_invalid_response("envelope_invalid", response_bytes=response_size)
    content, choice = extracted
    finish_reason = _finish_reason(choice)
    completion_tokens = _completion_tokens(envelope)
    if finish_reason == "length":
        _raise_invalid_response(
            "output_truncated",
            response_bytes=response_size,
            finish_reason=finish_reason,
            completion_tokens=completion_tokens,
        )

    content_ok, draft_data = _load_strict_json(content)
    if not content_ok or type(draft_data) is not dict:
        _raise_invalid_response(
            "content_not_json",
            response_bytes=response_size,
            finish_reason=finish_reason,
            completion_tokens=completion_tokens,
        )
    draft_failure_group: BonsaiDraftFailureGroup = "document"
    try:
        from src.search_v2.source_constraints import expand_source_names

        draft_data = expand_source_names(source_input, draft_data)
        compact_draft = BonsaiCompactSearchIntentDraft.model_validate(draft_data)
        draft = _ground_source_conditions(
            source_input,
            compact_draft.to_search_intent_draft(),
        )
    except ValidationError as error:
        draft_failure_group = _draft_failure_group(error)
        draft = None
    except (RecursionError, TypeError, ValueError):
        draft = None
    if draft is None:
        _raise_invalid_response(
            "draft_schema_invalid",
            response_bytes=response_size,
            draft_failure_group=draft_failure_group,
            finish_reason=finish_reason,
            completion_tokens=completion_tokens,
        )

    schema = search_intent_schema_bytes()
    intent = None
    try:
        provenance = build_intent_provenance(
            source_input=source_input,
            prompt=prompt,
            schema=schema,
            response=response,
        )
        intent = normalize_search_intent(source_input, draft, provenance=provenance)
    except (RecursionError, TypeError, ValidationError, ValueError):
        pass
    if intent is None:
        _raise_invalid_response(
            "intent_normalization_invalid",
            response_bytes=response_size,
            finish_reason=finish_reason,
            completion_tokens=completion_tokens,
        )
    if not intent.has_blocking_ambiguity:
        searchability_invalid = False
        try:
            build_search_query_plan(intent)
        except (RecursionError, TypeError, ValidationError, ValueError):
            searchability_invalid = True
        if searchability_invalid:
            searchability_failure_group: BonsaiSearchabilityFailureGroup = (
                "invalid_terms" if _has_declared_search_terms(intent) else "missing_terms"
            )
            _raise_invalid_response(
                "intent_searchability_invalid",
                response_bytes=response_size,
                searchability_failure_group=searchability_failure_group,
                finish_reason=finish_reason,
                completion_tokens=completion_tokens,
            )
    return intent
