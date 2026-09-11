"""Read only explicitly labelled specifications for search-local attributes."""

from decimal import Decimal
import re
import unicodedata

from src.search_v2.typed_requirements import AttributeDefinition
from src.search_v2.typed_requirements import BooleanObservedValue
from src.search_v2.typed_requirements import DecimalObservedValue
from src.search_v2.typed_requirements import EnumObservedValue
from src.search_v2.typed_requirements import IntegerObservedValue
from src.search_v2.typed_requirements import ObservedValue
from src.search_v2.typed_requirements import TextSetObservedValue
from src.search_v2.typed_requirements import normalize_observed_value


_NUMBER_UNIT = re.compile(r"(-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?)\s*([^\s:;,]{1,32})")
_UNITS = {
    "ml": ("volume", Decimal(1)),
    "l": ("volume", Decimal(1000)),
    "mm": ("length", Decimal(1)),
    "cm": ("length", Decimal(10)),
    "m": ("length", Decimal(1000)),
    "g": ("mass", Decimal(1)),
    "kg": ("mass", Decimal(1000)),
}
_BOOLEAN = {
    "はい": True,
    "対応": True,
    "可能": True,
    "あり": True,
    "true": True,
    "yes": True,
    "いいえ": False,
    "非対応": False,
    "不可": False,
    "なし": False,
    "false": False,
    "no": False,
}


def _identity(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


def _numeric_value(text: str, definition: AttributeDefinition) -> ObservedValue:
    match = _NUMBER_UNIT.fullmatch(text)
    if match is None:
        raise ValueError("specification has no exact number and unit")
    value, unit = Decimal(match[1]), match[2]
    target_unit = definition.allowed_units[0]
    unit = next(
        (alias.canonical for alias in definition.unit_aliases if _identity(alias.alias) == unit),
        unit,
    )
    if unit != target_unit:
        if (
            unit not in _UNITS
            or target_unit not in _UNITS
            or _UNITS[unit][0] != _UNITS[target_unit][0]
        ):
            raise ValueError("specification unit is incompatible")
        value = value * _UNITS[unit][1] / _UNITS[target_unit][1]
    if definition.value_type == "integer":
        if value != value.to_integral_value():
            raise ValueError("integer specification has a fractional value")
        return IntegerObservedValue(value_type="integer", value=int(value), unit=target_unit)
    return DecimalObservedValue(value_type="decimal", value=value, unit=target_unit)


def read_labelled_specification(text: str, definition: AttributeDefinition) -> ObservedValue | None:
    label, separator, raw_value = _identity(text).partition(":")
    if not separator or label.strip() not in {_identity(alias) for alias in definition.aliases}:
        return None
    value = raw_value.strip()
    if not value:
        raise ValueError("empty specification value")
    if definition.value_type in {"integer", "decimal"}:
        observed = _numeric_value(value, definition)
    elif definition.value_type == "boolean":
        if value not in _BOOLEAN:
            raise ValueError("ambiguous boolean specification")
        observed = BooleanObservedValue(value_type="boolean", value=_BOOLEAN[value])
    elif definition.value_type == "enum":
        matched = next(
            (item.canonical for item in definition.value_aliases if _identity(item.alias) == value),
            None,
        )
        # Absence and uncertain/multi-valued text are not categorical contradictions.
        if matched is None and (
            re.search(
                r"不明|未記載|不詳|unknown|n/?a|[,;/、]|または|又は|\bor\b|ではない|以外", value
            )
            or len(value) > 32
        ):
            raise ValueError("ambiguous category specification")
        observed = EnumObservedValue(value_type="enum", value=matched or "other_observed_value")
    elif definition.value_type == "text_set":
        values = tuple(part.strip() for part in re.split(r"[,、]", value))
        observed = TextSetObservedValue(value_type="text_set", values=values)
    else:
        raise ValueError("unsupported specification type")
    return normalize_observed_value(observed, definition)
