"""Validate input-grounded proposals and compile search-local attribute definitions."""

from decimal import Decimal
import hashlib
import json
import re
import unicodedata

from src.search_v2.intent import BonsaiTypedConditionCandidate
from src.search_v2.tokenizer import _AnalyzedSource
from src.search_v2.typed_requirements import AttributeDefinition
from src.search_v2.typed_requirements import AttributeRegistry
from src.search_v2.typed_requirements import EvidenceRule
from src.search_v2.typed_requirements import ValueAlias


_NUMBER = r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?"
_UNIT = re.compile(r"[a-z][a-z0-9_-]{0,31}")
_PREFERRED = re.compile(r"望ましい|希望|できれば|好ましい|prefer", re.I)
_EXCLUDED = re.compile(r"除外|避け|不要|以外|exclude|avoid", re.I)
_NEGATIVE = re.compile(r"非対応|対応不可|不対応|使えない|いいえ|false|不可|ではない", re.I)
_OR = re.compile(r"または|あるいは|もしくは|又は|\bor\b", re.I)
_OTHER_VALUE = "other_observed_value"
# Equivalent spellings only: these aliases never change a numeric magnitude.
_UNIT_SPELLINGS = {"inch": ("inch", "inches", "インチ"), "hour": ("hour", "hours", "時間")}


def _unit_spellings(value: str) -> tuple[str, ...]:
    normalized = _identity(value)
    for spellings in _UNIT_SPELLINGS.values():
        if normalized in spellings:
            return spellings
    return (normalized,)


def _identity(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


def _value_key(value: str) -> str:
    return "value_" + hashlib.sha256(_identity(value).encode()).hexdigest()[:24]


def _unit_key(value: str) -> str:
    normalized = _unit_spellings(value)[0]
    if (
        not normalized
        or len(normalized) > 32
        or any(c.isspace() or unicodedata.category(c).startswith("C") for c in normalized)
    ):
        raise ValueError("invalid generated unit label")
    if _UNIT.fullmatch(normalized):
        return normalized
    return "unit_" + hashlib.sha256(normalized.encode()).hexdigest()[:24]


def search_attribute_key(candidate: BonsaiTypedConditionCandidate) -> str:
    definition = candidate.attribute_definition
    if definition is None:
        return candidate.attribute_key
    # Meaning and target are bound separately; the same label cannot split into competing attributes.
    return (
        "search."
        + "attribute_"
        + hashlib.sha256(_identity(definition.label).encode()).hexdigest()[:24]
    )


def _numeric_grounded(candidate: BonsaiTypedConditionCandidate, quote: str) -> bool:
    target = candidate.expected_value
    unit = _identity(target.unit)
    try:
        _unit_key(unit)
    except ValueError:
        return False
    spelling = "(?:" + "|".join(re.escape(v) for v in _unit_spellings(unit)) + ")"
    amounts = list(re.finditer(rf"(?<![\d.])(?P<number>{_NUMBER})\s*{spelling}(?![a-z])", quote))
    bounds = [
        Decimal(str(value)) for value in (target.minimum, target.maximum) if value is not None
    ]
    if not amounts or not bounds:
        return False
    prefix = quote[: amounts[0].start()].strip()
    label = _identity(candidate.attribute_definition.label)
    if prefix and not re.fullmatch(re.escape(label) + r"\s*(?:は|が|:|=)?\s*", prefix):
        return False
    observed = [Decimal(match.group("number")) for match in amounts]
    tail = quote[amounts[-1].end() :].strip()
    if candidate.operator == "at_least":
        return (
            target.minimum is not None
            and target.maximum is None
            and observed == bounds
            and tail.startswith("以上")
        )
    if candidate.operator == "at_most":
        return (
            target.maximum is not None
            and target.minimum is None
            and observed == bounds
            and tail.startswith(("以下", "以内"))
        )
    if candidate.operator == "equals":
        return (
            len(bounds) == 2
            and bounds[0] == bounds[1]
            and observed == bounds[:1]
            and not re.search("以上|以下|未満|超|から|まで", tail)
        )
    if candidate.operator == "between" and len(amounts) == 2 and len(bounds) == 2:
        between = quote[amounts[0].end() : amounts[1].start()].strip()
        return (
            observed == bounds
            and bounds[0] <= bounds[1]
            and (
                (between == "以上" and tail.startswith(("以下", "以内")))
                or (between in {"から", "〜", "~", "-"} and tail.startswith("まで"))
            )
        )
    return False


def numeric_identity_requires_review(candidate: BonsaiTypedConditionCandidate) -> bool:
    """Quantity evidence alone cannot certify a model-supplied attribute name.

    Keep this check independent of the model's ambiguity field and of registry
    membership: old proposals and caller-supplied registries must not bypass it.
    Non-numeric conditions retain their existing grounding contract.
    """
    if candidate.attribute_key != "custom" or candidate.expected_value.value_type not in {
        "integer",
        "decimal",
    }:
        return False
    definition = candidate.attribute_definition
    if definition is None:
        return True
    quote, label = _identity(definition.source_quote), _identity(definition.label)
    # Require the name immediately attached to the quantity, not merely elsewhere
    # in the source. This is an evidence requirement, not semantic name correction.
    attached_name = re.match(re.escape(label) + rf"\s*(?:は|が|:|=)?\s*(?={_NUMBER})", quote)
    return not label or attached_name is None or not _numeric_grounded(candidate, quote)


def custom_condition_grounded(
    candidate: BonsaiTypedConditionCandidate,
    source: _AnalyzedSource,
    registry: AttributeRegistry,
) -> bool:
    definition = candidate.attribute_definition
    if definition is None or candidate.attribute_key != "custom":
        return False
    quote, label = _identity(definition.source_quote), _identity(definition.label)
    if not label or any(unicodedata.category(c).startswith("C") for c in quote):
        return False
    start = source.text.find(quote)
    starts = {m.begin for m in source.morphemes}
    ends = {m.end for m in source.morphemes}
    if start not in starts or start + len(quote) not in ends:
        return False
    if source.text.count(quote) != 1:
        return False
    suffix = re.split(r"[、。,.\n]", source.text[start + len(quote) :], maxsplit=1)[0]
    if re.match(
        r"\s*(?:は|が|なら|で|を)?(?:ではない|ない|不要|除外|避け|望ましい|希望|好ましい|以上|以下|未満|超)",
        suffix,
    ):
        return False
    if re.search(r"(?:または|あるいは|もしくは|又は|\bor)\s*$", source.text[:start]) or _OR.match(
        suffix
    ):
        return False
    # Existing names cannot be repurposed by a generated definition, regardless of its proposed type.
    if any(
        label == _identity(name)
        for item in registry.definitions
        for name in (item.attribute_key, *item.aliases)
    ):
        return False
    expected_strength = (
        "excluded"
        if _EXCLUDED.search(quote)
        else "preferred"
        if _PREFERRED.search(quote)
        else "required"
    )
    if candidate.strength != expected_strength:
        return False
    value = candidate.expected_value
    if value.value_type != "boolean" and _NEGATIVE.search(quote):
        return False
    if value.value_type in {"integer", "decimal"}:
        return _numeric_grounded(candidate, quote)
    if value.value_type == "boolean":
        # The label itself may express a capability; a negative must be stated explicitly.
        negative = bool(_NEGATIVE.search(quote))
        return (
            candidate.operator == "equals"
            and value.value is not negative
            and (
                negative
                or quote == label
                or bool(re.search(r"対応|可能|できる|あり|true|はい", quote))
            )
        )
    if value.value_type in {"enum", "text_set"}:
        if candidate.operator not in {"equals", "one_of", "contains_all", "compatible_with"}:
            return False
        if candidate.operator == "equals" and len(value.values) != 1:
            return False
        if candidate.operator == "one_of" and len(value.values) > 1 and not _OR.search(quote):
            return False
        if _OR.search(quote) and (candidate.operator != "one_of" or len(value.values) < 2):
            return False
        return all(_identity(item) in quote for item in value.values) and len(
            {_identity(item) for item in value.values}
        ) == len(value.values)
    return False


def compile_search_registry(
    candidates: list[BonsaiTypedConditionCandidate],
    base: AttributeRegistry,
) -> AttributeRegistry:
    additions: dict[str, AttributeDefinition] = {}
    for candidate in candidates:
        proposed = candidate.attribute_definition
        if proposed is None:
            continue
        if candidate.attribute_key != "custom":
            raise ValueError("a registered attribute cannot carry a generated definition")
        if numeric_identity_requires_review(candidate):
            raise ValueError("numeric attribute identity requires review")
        value = candidate.expected_value
        kind = value.value_type
        if kind not in {"boolean", "integer", "decimal", "enum", "text_set"}:
            raise ValueError("unsupported generated attribute type")
        unit = _unit_key(value.unit) if kind in {"integer", "decimal"} else None
        enum_values = tuple(value.values) if kind == "enum" else ()
        key = search_attribute_key(candidate)
        definition = AttributeDefinition(
            category="search",
            attribute_key=key,
            aliases=(proposed.label,),
            value_type=kind,
            allowed_operators=(candidate.operator,),
            allowed_strengths=(candidate.strength,),
            allowed_units=() if unit is None else (unit,),
            unit_aliases=()
            if unit is None
            else tuple(
                ValueAlias(alias=alias, canonical=unit)
                for alias in dict.fromkeys(
                    _UNIT_SPELLINGS.get(unit, (unicodedata.normalize("NFKC", value.unit),))
                )
                if alias != unit
            ),
            allowed_values=tuple(sorted((_OTHER_VALUE, *(_value_key(v) for v in enum_values))))
            if enum_values
            else (),
            value_aliases=tuple(ValueAlias(alias=v, canonical=_value_key(v)) for v in enum_values),
            evidence_rules=(
                EvidenceRule(
                    source="structured",
                    priority=1,
                    evaluator_id="search-labelled-specification",
                    evaluator_version="1.0",
                ),
            ),
            default_weight=1,
            visual_prompt_allowed=False,
        )
        if key in additions:
            raise ValueError("duplicate generated attribute")
        additions[key] = definition
    if not additions:
        return base
    manifest = [
        c.attribute_definition.model_dump()
        for c in candidates
        if c.attribute_definition is not None
    ]
    definition_digest = hashlib.sha256(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()[:24]
    return AttributeRegistry(
        schema_version="1.0",
        registry_id="search-attributes-v1-" + definition_digest,
        definitions=tuple(
            sorted((*base.definitions, *additions.values()), key=lambda d: d.attribute_key)
        ),
    )
