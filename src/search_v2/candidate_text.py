"""Description coverage assists condition ranking without claiming typed evidence."""

from decimal import Decimal
import hashlib
import re
from typing import Literal
import unicodedata

from pydantic import BaseModel, ConfigDict, Field

from src.search_v2.dynamic_attributes import _unit_spellings
from src.search_v2.dynamic_product_evidence import _UNITS
from src.search_v2.tokenizer import tokenize_search_text


TEXT_PROFILE_ID = "candidate-text-v1"
RATIO_DECIMALS = 6
EXCLUDED_PRIORITY_WEIGHT = 0.5
TEXT_PROFILE_SHA256 = hashlib.sha256(
    b"candidate-text-v1:structured-first:description-clause-coverage:negation-v2:"
    b"numeric-boundaries:original-plus-unmatched-synonym-0.25:equal-title-fields:ratio6:excluded-risk0.5"
).hexdigest()
_NEGATIVE = re.compile(
    r"非対応|不対応|不可|使え(?:ない|ません)|使わない|使用でき(?:ない|ません)|対応(?:して)?い(?:ない|ません)|非推奨|"
    r"でき(?:ない|ません)|では(?:あり)?ません|ではない|禁止|未対応|\b(?:not|no|cannot|can't|without)\b",
    re.I,
)
_UNCERTAIN = re.compile(
    r"場合|による|によって|一部|未確認|不明|要確認|\b(?:may|might|depending)\b", re.I
)
_NUMERIC = re.compile(
    r"(?P<number>-?[0-9]+(?:\.[0-9]+)?)\s*(?P<unit>[a-zA-Z]+|ミリリットル|リットル|グラム|ミリメートル|センチメートル)"
)


class ConditionTextScore(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", revalidate_instances="always"
    )
    requirement_id: str
    strength: Literal["required", "preferred", "excluded"]
    source: Literal["evidence", "description", "missing"]
    score: float = Field(ge=0.0, le=1.0)


class CandidateTextScore(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", revalidate_instances="always"
    )
    profile_id: Literal["candidate-text-v1"] = TEXT_PROFILE_ID
    profile_sha256: Literal[TEXT_PROFILE_SHA256] = TEXT_PROFILE_SHA256
    required_ratio: float = Field(ge=0.0, le=1.0)
    preferred_ratio: float = Field(ge=0.0, le=1.0)
    excluded_ratio: float = Field(ge=0.0, le=1.0)
    conditions: tuple[ConditionTextScore, ...]


def _identity(text):
    return unicodedata.normalize("NFKC", text).casefold()


def _clauses(text):
    return tuple(
        p.strip()
        for p in re.split(r"[。、；;\n!?！？]|ですが|だが|\bbut\b", _identity(text))
        if p.strip()
    )


def _coverage(phrase, clause):
    tokens = set(tokenize_search_text(phrase, language="ja"))
    if not tokens:
        return 0.0
    hits = 0
    for token in tokens:
        pattern = re.escape(token)
        if re.fullmatch(r"[a-z0-9_-]+", token):
            pattern = r"(?<![a-z0-9])" + pattern + r"(?![a-z0-9])"
        hits += bool(re.search(pattern, clause))
    return hits / len(tokens)


def _numeric_score(requirement, labels, clause):
    target = requirement.expected_value
    if not any(_identity(label) in clause for label in labels):
        return None
    if (
        _NEGATIVE.search(clause)
        or _UNCERTAIN.search(clause)
        or re.search(r"約|程度|前後|最大|最小", clause)
    ):
        return 0.0
    scores = []
    labelled_number = re.compile(
        "(?:"
        + "|".join(re.escape(_identity(label)) for label in labels)
        + r")[\s:はがの値=]*"
        + _NUMERIC.pattern
    )
    for match in labelled_number.finditer(clause):
        unit = _unit_spellings(match["unit"])[0]
        target_unit = _unit_spellings(target.unit)[0]
        if unit == target_unit:
            factor = Decimal(1)
        elif unit in _UNITS and target_unit in _UNITS and _UNITS[unit][0] == _UNITS[target_unit][0]:
            factor = _UNITS[unit][1] / _UNITS[target_unit][1]
        else:
            continue
        value = Decimal(match["number"]) * factor
        if requirement.operator == "equals":
            matched = value == target.minimum
        else:
            matched = (target.minimum is None or value >= target.minimum) and (
                target.maximum is None or value <= target.maximum
            )
        scores.append(float(matched))
    return min(scores) if scores else None


def _description_score(requirement, definition, clauses, label):
    target = requirement.expected_value
    labels = (label,) if label else definition.aliases
    if target.value_type in {"integer", "decimal"}:
        values = [_numeric_score(requirement, labels, clause) for clause in clauses]
        scores = [value for value in values if value is not None]
        return min(scores) if scores else 0.0
    if target.value_type == "boolean":
        terms = tuple(re.sub(r"(?:非)?対応$", "", value) for value in labels)
    elif target.value_type in {"enum", "text_set"}:
        terms = (
            *target.values,
            *(a.alias for a in definition.value_aliases if a.canonical in target.values),
        )
    else:
        terms = labels
    scores = []
    denied = False
    for clause in clauses:
        coverage = max((_coverage(term, clause) for term in terms), default=0.0)
        if not coverage or _UNCERTAIN.search(clause):
            continue
        negative = bool(_NEGATIVE.search(clause))
        expected_negative = target.value_type == "boolean" and not target.value
        if negative != expected_negative:
            denied = True
            continue
        scores.append(coverage)
    # Conflicting prose does not earn a positive score; absence never proves exclusion.
    return 0.0 if denied else max(scores, default=0.0)


def _structured_present(product, definition, label):
    fields = {
        "appearance.color": product.attributes.color,
        "material.type": product.attributes.material,
    }
    if fields.get(definition.attribute_key) is not None:
        return True
    labels = (label,) if label else definition.aliases
    return any(
        _identity(feature).partition(":")[0].strip() == _identity(name)
        for feature in product.attributes.features
        for name in labels
    )


def score_conditions(product, requirements, registry, evaluation, labels):
    definitions = {d.attribute_key: d for d in registry.definitions}
    decisions = {d.requirement_id: d for d in evaluation.decisions}
    description = product.description if "description" not in product.truncated_fields else None
    clauses = _clauses(description or "")
    rows = []
    for requirement in requirements:
        decision = decisions[requirement.requirement_id]
        if decision.state != "unknown":
            source, score = "evidence", float(decision.state == "match")
        elif requirement.requirement_id == "condition-price" or _structured_present(
            product, definitions[requirement.attribute_key], labels.get(requirement.requirement_id)
        ):
            source, score = "evidence", 0.0
        else:
            source = "description" if clauses else "missing"
            score = _description_score(
                requirement,
                definitions[requirement.attribute_key],
                clauses,
                labels.get(requirement.requirement_id),
            )
        rows.append(
            ConditionTextScore(
                requirement_id=requirement.requirement_id,
                strength=requirement.strength,
                source=source,
                score=score,
            )
        )

    def ratio(strength):
        selected = [
            (r, row) for r, row in zip(requirements, rows, strict=True) if r.strength == strength
        ]
        denominator = sum(definitions[r.attribute_key].default_weight for r, _ in selected)
        return (
            round(
                sum(definitions[r.attribute_key].default_weight * row.score for r, row in selected)
                / denominator,
                RATIO_DECIMALS,
            )
            if denominator
            else 1.0
        )

    return CandidateTextScore(
        required_ratio=ratio("required"),
        preferred_ratio=ratio("preferred"),
        excluded_ratio=ratio("excluded")
        if any(r.strength == "excluded" for r in requirements)
        else 0.0,
        conditions=tuple(rows),
    )


def candidate_sort_key(row, overall_score):
    status = {"confirmed": 0, "uncertain": 1, "contradicted": 2}[row.evaluation.required_status]
    score = row.text_score
    return (
        status + (EXCLUDED_PRIORITY_WEIGHT * score.excluded_ratio if score else 0.0),
        -(score.required_ratio if score else row.evaluation.required_match_ratio),
        -(score.preferred_ratio if score else row.evaluation.preferred_match_ratio),
        -overall_score,
        row.product.provenance.response_index,
    )
