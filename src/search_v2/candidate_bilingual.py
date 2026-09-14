"""Independent language scores, followed by a maximum for each matching condition."""

from decimal import Decimal
import hashlib
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.search_v2.candidate_text import (
    CandidateTextScore,
    ConditionTextScore,
    _clauses,
    _coverage,
    _identity,
    _NEGATIVE,
    _UNCERTAIN,
    _numeric_score,
    _structured_present,
    score_conditions,
)
from src.search_v2.candidate_title import score_title
from src.search_v2.condition_weighting import condition_weights


PROFILE_ID = "candidate-text-bilingual-v2"
PROFILE_SHA256 = hashlib.sha256(
    b"candidate-bilingual-v2:per-condition-max:per-title-max:observed-first:"
    b"local-condition-terms-v1:visual-text:negative-guard:numeric-label-unit:missing-null"
).hexdigest()
_NEGATION = re.compile(_NEGATIVE.pattern + r"|\b(?:isn't|doesn't|non)\b|[- ]free\b", re.I)
_NUMERIC_QUALIFIER = re.compile(
    r"\b(?:approximately|approx|about|around|maximum|minimum|up to|at least|at most)\b", re.I
)
_UNIT_WORDS = {
    "milliliters": "ml",
    "millilitres": "ml",
    "milliliter": "ml",
    "millilitre": "ml",
    "liters": "l",
    "litres": "l",
    "liter": "l",
    "litre": "l",
    "grams": "g",
    "gram": "g",
    "kilograms": "kg",
    "kilogram": "kg",
    "millimeters": "mm",
    "centimeters": "cm",
    "meters": "m",
}


class BilingualTitleScore(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    score_ja: float = Field(ge=0, le=1)
    score_en: float | None = Field(ge=0, le=1)
    score: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def maximum(self):
        if self.score != max(self.score_ja, self.score_en or 0.0):
            raise ValueError("Bilingual title maximum is inconsistent")
        return self


class BilingualConditionScore(ConditionTextScore):
    source: Literal["evidence", "description", "missing", "product_text"]
    score_ja: float = Field(ge=0, le=1)
    score_en: float | None = Field(ge=0, le=1)
    selected_language: Literal["ja", "en"]

    @model_validator(mode="after")
    def maximum(self):
        if self.score != max(self.score_ja, self.score_en or 0.0):
            raise ValueError("Bilingual condition maximum is inconsistent")
        if self.selected_language != ("en" if (self.score_en or 0) > self.score_ja else "ja"):
            raise ValueError("Bilingual condition language is inconsistent")
        return self


class BilingualTextScore(CandidateTextScore):
    profile_id: Literal["candidate-text-bilingual-v2"] = PROFILE_ID
    profile_sha256: Literal[PROFILE_SHA256] = PROFILE_SHA256
    conditions: tuple[BilingualConditionScore, ...]


def title_scores(comparison, product):
    ja = score_title(comparison, product.title)
    en = score_title(comparison, product.title_en) if product.title_en else None
    return BilingualTitleScore(score_ja=ja, score_en=en, score=max(ja, en or 0.0))


def _text_score(terms, clauses, *, expected_negative=False):
    scores, denied = [], False
    for clause in clauses:
        coverage = max((_coverage(term, clause) for term in terms), default=0.0)
        if not coverage or _UNCERTAIN.search(clause):
            continue
        if bool(_NEGATION.search(clause)) != expected_negative:
            denied = True
        else:
            scores.append(coverage)
    return 0.0 if denied else max(scores, default=0.0)


def _numeric_clauses(text):
    # Sentence splitting must preserve the decimal point in observed measurements.
    text = _identity(text)
    for word, unit in _UNIT_WORDS.items():
        text = re.sub(r"\b" + word + r"\b", unit, text)
    text = re.sub(r"\b(?:is|of)\s+(?=\d)", "", text)
    return tuple(
        p.strip() for p in re.split(r"[。、；;\n!?！？]|(?<!\d)\.|\.(?!\d)", text) if p.strip()
    )


def _language_score(product, requirement, definition, terms, label, language):
    english = language == "en"
    details = product.details_en if english else product
    attrs = details if english else product.attributes
    title = product.title_en if english else product.title
    description = details.description if details else None
    suffix = "_en" if english else ""
    if "description" + suffix in product.truncated_fields:
        description = None
    if "title" + suffix in product.truncated_fields:
        title = None
    features = (
        attrs.features if attrs and "features" + suffix not in product.truncated_fields else ()
    )
    target = requirement.expected_value if requirement else None
    if not terms:
        return None if english else 0.0
    if english and not (
        title or description or features or (attrs and (attrs.color or attrs.material))
    ):
        return None
    if definition and definition.attribute_key in {"appearance.color", "material.type"}:
        field = "color" if definition.attribute_key == "appearance.color" else "material"
        observed = getattr(attrs, field, None)
        if observed and field + suffix not in product.truncated_fields:
            return _text_score(terms, _clauses(observed))
    if target and target.value_type in {"integer", "decimal"}:
        for index, text in enumerate(("\n".join(features), title or "", description or "")):
            values = [
                (
                    0.0
                    if _NUMERIC_QUALIFIER.search(clause)
                    and any(_identity(term) in clause for term in terms)
                    else _numeric_score(requirement, terms, clause)
                )
                for clause in _numeric_clauses(text)
            ]
            scores = [v for v in values if v is not None]
            if scores:
                return min(scores)
            if index == 0 and any(_identity(term) in _identity(text) for term in terms):
                return 0.0
        return 0.0
    labelled = [
        f
        for f in features
        if ":" in f
        and any(
            _coverage(t, _identity(f).partition(":")[0]) == 1.0
            for t in (*terms, *((label,) if label else ()))
        )
    ]
    body = (
        "\n".join(labelled)
        if labelled
        else "\n".join(filter(None, (title, description, *features)))
    )
    clauses = _clauses(body)
    # ASCII periods separate English sentences but not decimal measurements.
    if english:
        clauses = _numeric_clauses(body)
    return _text_score(
        terms,
        clauses,
        expected_negative=bool(target and target.value_type == "boolean" and not target.value),
    )


def score_bilingual(product, requirements, registry, evaluation, labels, bundle, *, weighting=None):
    original = score_conditions(product, requirements, registry, evaluation, labels)
    originals = {r.requirement_id: r for r in original.conditions}
    definitions = {d.attribute_key: d for d in registry.definitions}
    decisions = {d.requirement_id: d for d in evaluation.decisions}
    expanded = {c.condition_id: c for c in bundle.conditions}
    rows, weights = [], {}
    for requirement in requirements:
        cid = requirement.requirement_id
        definition = definitions[requirement.attribute_key]
        weights[cid] = definition.default_weight
        base, terms = originals[cid], expanded.get(cid)
        ja, en = base.score, None
        if cid == "condition-price":
            # Both language views share the observed JPY price and numeric target.
            en = ja if product.details_en is not None else None
        elif terms:
            if decisions[cid].state == "unknown" and not _structured_present(
                product, definition, labels.get(cid)
            ):
                ja = max(
                    ja,
                    _language_score(
                        product, requirement, definition, terms.terms_ja, labels.get(cid), "ja"
                    ),
                )
            en = _language_score(product, requirement, definition, terms.terms_en, None, "en")
        selected_source = (
            "product_text" if (en or 0) > base.score or ja > base.score else base.source
        )
        rows.append(
            BilingualConditionScore(
                requirement_id=cid,
                strength=requirement.strength,
                source=selected_source,
                score_ja=ja,
                score_en=en,
                score=max(ja, en or 0.0),
                selected_language="en" if (en or 0) > ja else "ja",
            )
        )
    for terms in bundle.conditions:
        if not terms.visual:
            continue
        ja = _language_score(product, None, None, terms.terms_ja, None, "ja")
        en = _language_score(product, None, None, terms.terms_en, None, "en")
        weights[terms.condition_id] = 1
        rows.append(
            BilingualConditionScore(
                requirement_id=terms.condition_id,
                strength=terms.strength,
                source="description",
                score_ja=ja,
                score_en=en,
                score=max(ja, en or 0.0),
                selected_language="en" if (en or 0) > ja else "ja",
            )
        )

    weights = condition_weights(rows, weights, weighting)
    if weighting is not None:
        rows = [r.model_copy(update={"weight": weights[r.requirement_id]}) for r in rows]

    def ratio(strength):
        selected = [r for r in rows if r.strength == strength]
        total = sum(weights[r.requirement_id] for r in selected)
        return (
            round(
                float(
                    sum(Decimal(str(r.score)) * weights[r.requirement_id] for r in selected) / total
                ),
                6,
            )
            if total
            else (0.0 if strength == "excluded" else 1.0)
        )

    return BilingualTextScore(
        required_ratio=ratio("required"),
        preferred_ratio=ratio("preferred"),
        excluded_ratio=ratio("excluded"),
        conditions=tuple(rows),
    )
