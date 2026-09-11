"""Compile explicit source facts into decoder constraints, without category dictionaries."""

from dataclasses import dataclass
import json
import re
import unicodedata

from src.search_v2.bonsai_adapter import _numeric_attribute_meaning, _source_phrase
from src.search_v2.tokenizer import _analyze_japanese_source
from src.search_v2.typed_requirements import DEFAULT_ATTRIBUTE_REGISTRY


_NUMBER = r"-?(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{1,6})?"
_QUANTITY = re.compile(
    rf"(?P<label>[^0-9]*?)(?P<number>{_NUMBER})\s*"
    r"(?P<unit>[^\s0-9、。,.]{1,32}?)(?P<relation>以上|以下|以内)(?:で)?$"
)
_STRENGTH = re.compile(r"(?:を|は)?(?P<value>希望|望ましい|除外|避けたい)$")
_ALTERNATIVE = re.compile(r"または|あるいは|もしくは|又は|\bor\b")
_CAPABILITY = re.compile(r"(?P<name>.+?)(?P<negative>非)?対応$")
_MAX_CONDITIONS = 4
_MAX_INTEGER_MAGNITUDE = 1_000_000_000_000
_JAPANESE_NAME_CHARACTER = re.compile(r"[\u3041-\u3096\u30a1-\u30fa\u3400-\u4dbf\u4e00-\u9fff]")


def _clauses(text):
    start = 0
    for separator in re.finditer(r"[。\n、]|(?<=(?:以上|以下|以内))で|(?<=対応)の", text):
        if separator.start() > start:
            yield start, text[start : separator.start()]
        start = separator.end()
    if start < len(text):
        yield start, text[start:]


@dataclass(frozen=True)
class _Fact:
    quote: str
    label: str | None
    target: dict
    operator: str
    strength: str
    key: str = "custom"

    def definition(self):
        if self.label is None:
            return None
        meaning = (
            _numeric_attribute_meaning(self.label, self.target["unit"])
            if "unit" in self.target
            else f"{self.label}の可否"
        )
        return {"label": self.label, "meaning": meaning, "source_quote": self.quote}


def _name_is_explicit(label):
    if not label or len(label) > 100:
        return False
    # Compound property nouns can include adjectival nouns. Sentence particles
    # and predicates still require scope resolution instead of name extraction.
    analyzed = _analyze_japanese_source(label)
    return any(m.part_of_speech == "名詞" for m in analyzed.morphemes) and all(
        m.part_of_speech in {"名詞", "形状詞", "接頭辞", "接尾辞", "補助記号", "記号"}
        for m in analyzed.morphemes
    )


def _source_facts(source):
    analyzed = _analyze_japanese_source(source)
    facts = []
    unparsed = []
    uncertain = False
    starts = {m.begin for m in analyzed.morphemes}
    ends = {m.end for m in analyzed.morphemes}
    # Decimal points stay inside clauses. Quoted or coordinated conditions are not split heuristically.
    for clause_start, clause in _clauses(analyzed.text):
        quote = clause.strip()
        if not quote:
            continue
        start = clause_start + len(clause) - len(clause.lstrip())
        if start not in starts or start + len(quote) not in ends:
            continue
        if _ALTERNATIVE.search(quote):
            uncertain = True
            continue
        strength = "required"
        relation = _STRENGTH.search(quote)
        value_phrase = quote
        if relation:
            strength = "preferred" if relation["value"] in {"希望", "望ましい"} else "excluded"
            value_phrase = quote[: relation.start()].strip()
        numeric = _QUANTITY.fullmatch(value_phrase)
        if numeric:
            label = numeric["label"].strip()
            unit = numeric["unit"]
            if unit.endswith("円"):
                continue  # The existing price contract owns currency, not custom attributes.
            if label and not _name_is_explicit(label):
                uncertain = True
                continue
            operator = "at_least" if numeric["relation"] == "以上" else "at_most"
            bound = "minimum" if operator == "at_least" else "maximum"
            number = numeric["number"]
            decimal = "." in number or abs(int(number)) > _MAX_INTEGER_MAGNITUDE
            target = {
                "value_type": "decimal" if decimal else "integer",
                bound: number if decimal else int(number),
                "unit": unit,
            }
            key = "custom"
            for definition in DEFAULT_ATTRIBUTE_REGISTRY.definitions:
                if label in definition.aliases:
                    if definition.attribute_key != "dimensions.width" or unit != "mm":
                        uncertain = True
                    else:
                        key = definition.attribute_key
                        target = {"value_type": "decimal", bound: number, "unit": unit}
            facts.append(_Fact(quote, label or None, target, operator, strength, key))
            continue
        capability = _CAPABILITY.fullmatch(value_phrase)
        if capability and _name_is_explicit(value_phrase):
            label = capability["name"] + "対応"
            facts.append(
                _Fact(
                    quote,
                    label,
                    {"value_type": "boolean", "value": not bool(capability["negative"])},
                    "equals",
                    strength,
                )
            )
        elif re.search(r"[0-9].*(以上|以下|以内)", value_phrase) and not re.search(
            r"[0-9].*円", value_phrase
        ):
            uncertain = True
        elif clause_start and not analyzed.text[:clause_start].endswith("対応の"):
            unparsed.append(value_phrase)
    common, ambiguous_common = _common_facts(analyzed, facts)
    facts.extend(common)
    if any(fact.key == "custom" for fact in facts):
        for clause in unparsed:
            remaining = clause
            for fact in common:
                remaining = remaining.replace(fact.quote, "")
            if not re.fullmatch(r"(?:い|の|で|な|は|が|と|を|\s)*", remaining):
                uncertain = True
    uncertain |= ambiguous_common
    if len(facts) > _MAX_CONDITIONS or len({f.quote for f in facts}) != len(facts):
        uncertain = True
    return tuple(facts), uncertain


def _common_facts(source, custom):
    facts = []
    uncertain = False
    for definition in DEFAULT_ATTRIBUTE_REGISTRY.definitions:
        if definition.value_type != "enum":
            continue
        values = []
        for value in definition.allowed_values:
            aliases = tuple(a.alias for a in definition.value_aliases if a.canonical == value)
            phrase = _source_phrase(source, (value, *aliases))
            if phrase is None or any(phrase in f.quote for f in custom):
                continue
            position = source.text.find(phrase.casefold())
            clause = next(
                (
                    m.group().strip()
                    for m in re.finditer(r"[^。\n、]+", source.text)
                    if m.start() <= position < m.end()
                ),
                "",
            )
            qualifier = _STRENGTH.search(clause)
            strength = "required"
            if qualifier:
                strength = "preferred" if qualifier["value"] in {"希望", "望ましい"} else "excluded"
            if re.search(r"ではない|ない|以外|不要", clause):
                uncertain = True
            values.append(
                _Fact(
                    phrase,
                    None,
                    {"value_type": "enum", "values": [value]},
                    "equals",
                    strength,
                    definition.attribute_key,
                )
            )
        if len(values) > 1:
            uncertain = True  # Multiple values need an explicit AND/OR/part relation.
        facts.extend(values)
    return facts, uncertain


def _object(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _constant(value):
    if isinstance(value, dict):
        return _object({key: _constant(item) for key, item in value.items()})
    return {"const": value}


def _property_name_pattern(unit):
    # Enumerate the first Japanese character's position. Each branch owns its
    # length budget: llama.cpp ignores maxLength when it compiles a pattern.
    japanese = _name_characters("japanese")
    other = _name_characters("other")
    safe = _name_characters("any")
    branches = [
        _repeat_characters(other, index, index) + japanese + _repeat_characters(safe, 0, 99 - index)
        for index in range(100)
    ]
    first = _JAPANESE_NAME_CHARACTER.search(unit)
    if first and not any(ord(char) < 32 or char in '\\"' for char in unit):
        # Only this branch can equal the unit. Subtract that finite word,
        # including single-character case variants, without lookahead or not.
        position = first.start()
        prefixes = [""]
        alternatives = []
        for index, char in enumerate(unit):
            variants = (
                char.lower() + char.upper()
                if len(char.lower()) == len(char.upper()) == 1 and char.lower() != char.upper()
                else char
            )
            kind = "other" if index < position else "japanese" if index == position else "any"
            suffix = _repeat_characters(safe, 0, 99 - max(index, position))
            if index < position:
                suffix = (
                    _repeat_characters(other, position - index - 1, position - index - 1)
                    + japanese
                    + suffix
                )
            alternatives.append(prefixes[-1] + _name_characters(kind, variants) + suffix)
            prefixes.append(prefixes[-1] + "[" + re.escape(variants) + "]")
        alternatives.extend(prefixes[position + 1 : -1])
        alternatives.append(prefixes[-1] + _repeat_characters(safe, 1, 100 - len(unit)))
        branches[position] = "(" + "|".join(alternatives) + ")"
    return "^(" + "|".join(branches) + ")$"


def _repeat_characters(characters, minimum, maximum):
    return "" if maximum == 0 else characters + f"{{{minimum},{maximum}}}"


def _name_characters(kind, excluded=""):
    # The decoder matches raw JSON: no branch may consume a quote or escape.
    unsafe = r'\x00-\x1f"\\'
    japanese = _JAPANESE_NAME_CHARACTER.pattern[1:-1]
    if kind != "japanese":
        omitted = japanese if kind == "other" else ""
        return "[^" + unsafe + omitted + re.escape(excluded) + "]"
    ranges = []
    for lower, upper in ((0x3041, 0x3096), (0x30A1, 0x30FA), (0x3400, 0x4DBF), (0x4E00, 0x9FFF)):
        for point in sorted({ord(char) for char in excluded if lower <= ord(char) <= upper}):
            if lower < point:
                ranges.append(chr(lower) + "-" + chr(point - 1))
            lower = point + 1
        if lower <= upper:
            ranges.append(chr(lower) + "-" + chr(upper))
    return "[" + "".join(ranges) + "]"


def _fact_schema(fact):
    properties = {"attribute_key": _constant(fact.key)}
    if fact.key == "custom":
        properties["attribute_definition"] = _constant(fact.definition())
    properties.update(
        strength=_constant(fact.strength),
        operator=_constant(fact.operator),
        expected_value=_constant(fact.target),
    )
    return _object(properties)


def _prune_definitions(schema):
    definitions = schema["$defs"]
    used = set()

    def visit(value):
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            reference = value.get("$ref")
            if reference:
                name = reference.removeprefix("#/$defs/")
                if name not in used:
                    used.add(name)
                    visit(definitions[name])
            for key, item in value.items():
                if key != "$defs":
                    visit(item)

    visit(schema)
    schema["$defs"] = {key: value for key, value in definitions.items() if key in used}


def bind_generation_schema(source, base_schema):
    facts, uncertain = _source_facts(source)
    if not facts and not uncertain:
        return base_schema
    schema = json.loads(base_schema)
    searchable, blocking = schema["anyOf"]
    if uncertain:
        schema["anyOf"] = [blocking]
    elif any(f.key == "custom" and f.label is None for f in facts):
        missing = [f for f in facts if f.key == "custom" and f.label is None]
        schema["anyOf"] = [
            _object(
                {
                    "product_name_ja": {"type": "string", "minLength": 1, "maxLength": 100},
                    "attribute_names_ja": {
                        "type": "array",
                        "prefixItems": [
                            {"type": "string", "pattern": _property_name_pattern(f.target["unit"])}
                            for f in missing
                        ],
                        "minItems": len(missing),
                        "maxItems": len(missing),
                    },
                }
            ),
            blocking,
        ]
    else:
        definitions = schema["$defs"]
        for index, fact in enumerate(facts):
            definitions[f"SourceFact{index}"] = _fact_schema(fact)
        prefixes = [{"$ref": f"#/$defs/SourceFact{index}"} for index in range(len(facts))]
        searchable["properties"]["typed_conditions"] = {
            "type": "array",
            "prefixItems": prefixes,
            "minItems": len(facts),
            "maxItems": len(facts),
        }
        searchable["required"].append("typed_conditions")
    _prune_definitions(schema)
    return json.dumps(schema, ensure_ascii=False, separators=(",", ":")).encode()


def needs_attribute_name_inference(source):
    facts, uncertain = _source_facts(source)
    return not uncertain and any(f.key == "custom" and f.label is None for f in facts)


def source_name_task_input(source):
    facts, uncertain = _source_facts(source)
    missing = [f for f in facts if f.key == "custom" and f.label is None]
    if uncertain or not missing:
        return source
    return json.dumps(
        {
            "source_input": source,
            "unnamed_quantities": [
                {"source_quote": f.quote, "unit": f.target["unit"]} for f in missing
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def expand_source_names(source, payload):
    """Join model-owned missing names with source-owned facts, without correcting model values."""
    if "attribute_names_ja" not in payload:
        return payload
    facts, uncertain = _source_facts(source)
    missing = [f for f in facts if f.key == "custom" and f.label is None]
    names = payload.get("attribute_names_ja")
    if (
        uncertain
        or not missing
        or set(payload) != {"product_name_ja", "attribute_names_ja"}
        or type(names) is not list
        or len(names) != len(missing)
        or type(payload.get("product_name_ja")) is not str
    ):
        raise ValueError("Invalid source name response")
    boolean_names = {
        name
        for fact in facts
        if fact.target["value_type"] == "boolean" and fact.label is not None
        for name in (fact.label, fact.label.removesuffix("対応"))
    }
    for name, fact in zip(names, missing):
        if type(name) is not str:
            raise ValueError("Invalid inferred property name")
        normalized = unicodedata.normalize("NFKC", name).casefold().strip()
        product = unicodedata.normalize("NFKC", payload["product_name_ja"]).casefold().strip()
        if (
            not normalized
            or normalized == product
            or normalized in boolean_names
            or not _JAPANESE_NAME_CHARACTER.search(normalized)
            or not re.fullmatch(_property_name_pattern(fact.target["unit"]), name)
            or re.fullmatch(
                rf"(?:{_NUMBER}\s*)?{re.escape(fact.target['unit'])}"
                r"(?:以上|以下|以内|未満|超|上限|下限|最大|最小)?",
                normalized,
            )
            or re.search(r"[0-9].*(以上|以下|以内|未満|超)", normalized)
        ):
            raise ValueError("Invalid inferred property name")
    names = iter(names)
    conditions = []
    for fact in facts:
        condition = {
            "attribute_key": fact.key,
            "strength": fact.strength,
            "operator": fact.operator,
            "expected_value": fact.target.copy(),
        }
        if fact.key == "custom":
            definition = fact.definition()
            if definition is None:
                name = next(names)
                definition = {
                    "label": name,
                    "meaning": _numeric_attribute_meaning(name, fact.target["unit"]),
                    "source_quote": fact.quote,
                }
            condition["attribute_definition"] = definition
        conditions.append(condition)
    return {"product_name_ja": payload["product_name_ja"], "typed_conditions": conditions}


def validate_source_response(source, response):
    facts, uncertain = _source_facts(source)
    if not facts and not uncertain:
        return
    data = json.loads(json.loads(response)["choices"][0]["message"]["content"])
    if set(data) == {"ambiguities"}:
        return  # The strict response parser still checks every ambiguity's shape and blocking flag.
    if needs_attribute_name_inference(source):
        if "attribute_names_ja" not in data:
            raise ValueError("Expected missing specification names only")
        expand_source_names(source, data)
        return
    if uncertain:
        raise ValueError("Unresolved source scope")
    candidates = data.get("typed_conditions", [])
    if len(candidates) != len(facts):
        raise ValueError("Missing source condition")
    for candidate, fact in zip(candidates, facts):
        if any(
            candidate.get(key) != expected
            for key, expected in {
                "attribute_key": fact.key,
                "strength": fact.strength,
                "operator": fact.operator,
                "expected_value": fact.target,
            }.items()
        ):
            raise ValueError("Changed source fact")
        if fact.key == "custom":
            definition = candidate.get("attribute_definition", {})
            if definition.get("source_quote") != fact.quote or (
                fact.label is not None and definition != fact.definition()
            ):
                raise ValueError("Changed source definition")
