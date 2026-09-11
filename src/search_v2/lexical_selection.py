"""Select a dictionary sense; never synthesize a translation or a synonym."""

from dataclasses import dataclass
import math
import re
import unicodedata

from src.search_v2.bonsai_query_terms import QueryTerms, TranslatedTerm, _clean_term


MAX_SENSES = 16
MINIMUM_SCORE = 0.75
MINIMUM_MARGIN = 0.04


def lexical_key(text):
    value = unicodedata.normalize("NFKC", text).casefold()
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in value if not c.isspace())


@dataclass(frozen=True, repr=False)
class LexicalSense:
    sense_id: str
    source: str
    forms: tuple[str, ...]
    glosses: tuple[str, ...]
    definition: str
    lookup_forms: tuple[str, ...] = ()
    definitions_ja: tuple[str, ...] = ()
    examples_ja: tuple[str, ...] = ()

    def __post_init__(self):
        if (
            not self.sense_id
            or not self.source
            or not self.forms
            or not self.glosses
            or len(self.definition) > 4000
            or any(type(v) is not str or not v for v in (*self.forms, *self.glosses))
        ):
            raise ValueError("Invalid dictionary sense")


@dataclass(frozen=True, repr=False)
class SenseSelection:
    status: str
    sense: LexicalSense | None
    score: float | None = None
    margin: float | None = None


def select_sense(senses, scores, *, minimum=MINIMUM_SCORE, margin=MINIMUM_MARGIN):
    if not 0 <= minimum <= 1 or not 0 <= margin <= 2:
        raise ValueError("Invalid sense selection threshold")
    if len(senses) != len(scores) or len(senses) > MAX_SENSES:
        raise ValueError("Invalid sense candidate count")
    if len({s.sense_id for s in senses}) != len(senses):
        raise ValueError("Duplicate sense identities")
    if any(type(s) not in (int, float) or not math.isfinite(s) or not -1 <= s <= 1 for s in scores):
        raise ValueError("Invalid sense scores")
    if not senses:
        return SenseSelection("not_found", None)
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    best = order[0]
    difference = scores[best] - scores[order[1]] if len(order) > 1 else 2.0
    if scores[best] < minimum or difference < margin:
        return SenseSelection("ambiguous", None, scores[best], difference)
    return SenseSelection("selected", senses[best], scores[best], difference)


def _translation(glosses):
    for gloss in glosses:
        # JMdict uses a leading parenthesis for an optional lexical qualifier.
        gloss = re.sub(r"^\(([A-Za-z]+(?: [A-Za-z]+)*)\) (?=[A-Za-z])", r"\1 ", gloss)
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*(?:[- '][A-Za-z0-9]+){0,7}", gloss):
            continue
        if re.match(r"(?:a|an|the) ", gloss, re.I):
            continue
        try:
            return _clean_term(gloss, "en")
        except ValueError:
            continue
    return None


def terms_from_sense(product, sense):
    translation = _translation(sense.glosses)
    numbers = set(re.findall(r"\d+", product))
    if not set(re.findall(r"\d+", translation or "")).issubset(numbers):
        translation = None
    variants, seen = [], {lexical_key(product)}
    for form in sense.forms:
        key = lexical_key(form)
        if key in seen or not set(re.findall(r"\d+", form)).issubset(numbers):
            continue
        seen.add(key)
        try:
            variants.append(TranslatedTerm(ja=_clean_term(form, "ja"), en=translation))
        except ValueError:
            continue
        if len(variants) == 3:
            break
    return QueryTerms(original_en=translation, synonyms=tuple(variants))
