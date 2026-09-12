"""Source-bound condition terms from local dictionaries and local translation only."""

import hashlib
import re
from typing import Annotated, Literal
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from src.search_v2.lexical_selection import select_sense, terms_from_sense


Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Term = Annotated[str, StringConstraints(min_length=1, max_length=256)]
MAX_TRANSLATION_PHRASES = 192


class ConditionTerms(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    condition_id: str
    strength: Literal["required", "preferred", "excluded"]
    source_ja: str = Field(repr=False, min_length=1, max_length=2000)
    source_en: Term | None = Field(default=None, repr=False)
    terms_ja: tuple[Term, ...] = Field(default=(), max_length=32, repr=False)
    terms_en: tuple[Term, ...] = Field(default=(), max_length=32, repr=False)
    sense_ids: tuple[str, ...] = ()
    visual: bool = False


class ConditionTermBundle(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    profile_id: Literal["condition-terms-v1"] = "condition-terms-v1"
    source_sha256: Digest
    dictionary_sha256: Digest | None = None
    translator_sha256: Digest | None = None
    sense_model_sha256: Digest | None = None
    conditions: tuple[ConditionTerms, ...] = Field(max_length=64, repr=False)

    @model_validator(mode="after")
    def unique_conditions(self):
        ids = [row.condition_id for row in self.conditions]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate condition terms")
        return self


def _unique(values):
    return tuple(dict.fromkeys(v for v in values if v))


def _english(value):
    return (
        isinstance(value, str)
        and 0 < len(value) <= 256
        and re.search(r"[a-z]", value, re.I) is not None
        and re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", value) is None
        and not any(unicodedata.category(c).startswith("C") for c in value)
    )


class LocalConditionExpander:
    def __init__(self, lexicon=None, *, scorer=None, translator=None):
        self.lexicon, self.scorer, self.translator = lexicon, scorer, translator

    def _select(self, source, term):
        senses = self.lexicon.lookup_contextual(term)
        if len(senses) == 1:
            return senses[0], True
        if len(senses) > 1 and self.scorer:
            return select_sense(
                senses, self.scorer.scores(source, senses), minimum=0.80, margin=0.20
            ).sense, True
        return None, bool(senses)

    def _dictionary_terms(self, source, term):
        selected, found = self._select(source, term)
        if selected:
            terms = terms_from_sense(term, selected)
            return (
                _unique((term, *(s.ja for s in terms.synonyms))),
                _unique((terms.original_en, *(s.en for s in terms.synonyms))),
                (selected.sense_id,),
            )
        if found:
            return (term,), (), ()
        from src.search_v2.tokenizer import _analyze_japanese_source

        # Replace a noun inside the complete phrase; retain qualifiers and negation.
        variants, ids = [term], []
        for morpheme in _analyze_japanese_source(term).morphemes:
            noun = morpheme.surface
            if morpheme.part_of_speech != "名詞" or len(noun) < 2 or noun == term:
                continue
            selected, _ = self._select(source, noun)
            if not selected:
                continue
            terms = terms_from_sense(noun, selected)
            for synonym in terms.synonyms:
                variant = term.replace(noun, synonym.ja, 1)
                if variant not in variants and len(variant) <= 100:
                    variants.append(variant)
                    ids.append(selected.sense_id)
                if len(variants) == 4:
                    break
            if len(variants) == 4:
                break
        # A constituent's dictionary gloss is not a translation of the whole phrase.
        return tuple(variants), (), _unique(ids)

    def prepare(self, source, conditions, visual_conditions):
        from src.search_v2.condition_language import interpret_clause
        from src.search_v2.typed_requirements import DEFAULT_ATTRIBUTE_REGISTRY

        definitions = {d.attribute_key: d for d in DEFAULT_ATTRIBUTE_REGISTRY.definitions}
        requests = []
        for condition in conditions:
            if condition["condition_id"] == "condition-price":
                # Price is a shared observed JPY value, not translated product prose.
                requests.append((condition, (), False))
                continue
            target = condition["target"]
            label = condition["label"]
            if target["value_type"] in {"enum", "text_set"}:
                terms = list(target["values"])
                definition = definitions.get(condition["attribute_key"])
                if definition:
                    terms.extend(a.alias for a in definition.value_aliases if a.canonical in terms)
            else:
                terms = [re.sub(r"(?:非)?対応$", "", label)] if label else []
            requests.append((condition, _unique(terms), False))
        if visual_conditions:
            for visual in visual_conditions.conditions:
                requests.append(
                    (
                        {
                            "condition_id": visual.condition_id,
                            "strength": visual.strength,
                            "source_quote": visual.source_phrase,
                        },
                        (interpret_clause(visual.source_phrase).target,),
                        True,
                    )
                )
        expanded, translations, queued = {}, {}, []
        for condition, terms, _ in requests:
            if condition["condition_id"] == "condition-price":
                continue
            for term in (*terms, interpret_clause(condition["source_quote"]).target):
                if term in expanded:
                    continue
                variants, english, sense_ids = (term,), (), ()
                if _english(term):
                    english = (term,)
                elif self.lexicon and len(term) <= 100:
                    try:
                        variants, english, sense_ids = self._dictionary_terms(source, term)
                    except Exception:
                        pass  # Unavailable or ambiguous dictionaries do not invent aliases.
                expanded[term] = (variants, english, sense_ids)
                for phrase in variants:
                    if english:
                        translations[phrase] = english
                    elif 0 < len(phrase) <= 100 and phrase not in queued:
                        queued.append(phrase)
        queued = [q for q in queued if q not in translations][:MAX_TRANSLATION_PHRASES]
        if self.translator:
            for index in range(0, len(queued), 2):
                batch = tuple(queued[index : index + 2])
                try:
                    values = self.translator.translate(batch)
                    if len(values) != len(batch):
                        continue
                    for phrase, value in zip(batch, values, strict=True):
                        if _english(value) and set(re.findall(r"\d+", value)) == set(
                            re.findall(r"\d+", phrase)
                        ):
                            translations[phrase] = (value.strip(),)
                except Exception:
                    continue  # Preserve Japanese terms after a bounded local failure.
        rows = []
        for condition, terms, visual in requests:
            japanese = _unique(v for term in terms for v in expanded[term][0])
            english = _unique(v for term in japanese for v in translations.get(term, ()))
            source_ja = condition["source_quote"]
            source_en = translations.get(interpret_clause(source_ja).target, ())
            rows.append(
                ConditionTerms(
                    condition_id=condition["condition_id"],
                    strength=condition["strength"],
                    source_ja=source_ja,
                    source_en=source_en[0] if source_en else None,
                    terms_ja=japanese[:32],
                    terms_en=english[:32],
                    visual=visual,
                    sense_ids=_unique(sid for term in terms for sid in expanded[term][2]),
                )
            )
        return ConditionTermBundle(
            source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            dictionary_sha256=getattr(self.lexicon, "sha256", None),
            translator_sha256=getattr(self.translator, "sha256", None),
            sense_model_sha256=getattr(self.scorer, "sha256", None),
            conditions=tuple(rows),
        )
