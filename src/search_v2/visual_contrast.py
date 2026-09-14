"""Bounded visual descriptions for generated references and visual text/image comparison."""

from typing import Annotated, Literal
import re

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator, model_serializer

from src.search_v2.condition_language import interpret_clause

PROFILE = "visual-contrast-v1"
CURRENT_PROFILE = "visual-contrast-v3"
SENSE_PATTERN = r"^(?:[0-9]{8}-[ans]|jmdict:[0-9]+:[0-9]+)$"
Appearance = Annotated[
    str, StringConstraints(min_length=1, max_length=240, pattern=r"^[A-Za-z][A-Za-z0-9 ,.'()/-]*$")
]


class ContrastEvidence(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, revalidate_instances="always"
    )
    target: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    dictionary_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")] | None = None
    sense_ids: tuple[Annotated[str, StringConstraints(pattern=SENSE_PATTERN)], ...] = ()


class VisualContrast(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, revalidate_instances="always"
    )
    profile: Literal["visual-contrast-v1", "visual-contrast-v2", "visual-contrast-v3"] = PROFILE
    origin: Literal["local", "bonsai", "wordnet", "grammar"]
    matching: Appearance
    opposite: Appearance
    evidence: ContrastEvidence | None = None

    @model_serializer(mode="wrap")
    def legacy_fields(self, handler):
        data = handler(self)
        if self.evidence is None:
            data.pop("evidence", None)
        return data

    @model_validator(mode="after")
    def distinct_appearances(self):
        if self.profile == PROFILE:
            if self.evidence is not None or self.origin not in {"local", "bonsai"}:
                raise ValueError("Invalid legacy contrast provenance")
        elif self.evidence is None or self.origin == "local":
            raise ValueError("Current contrasts require provenance")
        elif self.origin in {"wordnet", "grammar"}:
            count = 2 if self.origin == "wordnet" else 1
            if self.evidence.dictionary_sha256 is None or len(self.evidence.sense_ids) != count:
                raise ValueError("Dictionary contrasts require sense provenance")
        elif self.evidence.dictionary_sha256 is not None or self.evidence.sense_ids:
            raise ValueError("Bonsai cannot claim dictionary provenance")
        if self.profile == "visual-contrast-v2" and any(
            not re.fullmatch(r"[0-9]{8}-[ans]", key) for key in self.evidence.sense_ids
        ):
            raise ValueError("Legacy v2 contrast only supports WordNet provenance")
        if any(text != text.strip() for text in (self.matching, self.opposite)):
            raise ValueError("Visual contrast contains surrounding whitespace")
        if self.matching.casefold() == self.opposite.casefold():
            raise ValueError("Visual contrast must describe different appearances")
        if any("www." in text.casefold() for text in (self.matching, self.opposite)):
            raise ValueError("Visual contrast contains a URL")
        return self


def local_contrast(phrase):
    """Frozen v1 read compatibility only; new preparation uses ContrastResolver."""
    expression = interpret_clause(phrase)
    if expression.strength == "neutral":
        return None
    target = expression.target
    rounded = (
        "A rounded outline with visibly curved sides",
        "An angular outline with straight sides and visible corners",
    )
    gloss = (
        "A glossy surface with visible specular reflections",
        "A matte surface without glossy reflections",
    )
    handle = ("A product with a clearly visible handle", "A product without any handle")
    pair = None
    if re.fullmatch(r"丸い(?:形)?|丸み(?:のある形|がある)|丸みを帯びた形", target):
        pair = rounded
    elif re.fullmatch(r"角ばった(?:形)?|角張った(?:形)?|四角い(?:形)?", target):
        pair = rounded[::-1]
    elif re.fullmatch(
        r"(?:胴体|本体)(?:が|に|は)?(?:丸い|丸みがある|膨らんでいる)|丸みのある(?:胴体|本体)",
        target,
    ):
        pair = (
            "A body with outward-bulging side outlines",
            "A body with straight side outlines and no outward bulge",
        )
    elif re.fullmatch(r"光沢(?:がある|あり)?|つやがある|艶がある", target):
        pair = gloss
    elif re.fullmatch(
        r"マット(?:な質感|仕上げ)?|つや消し|艶消し|(?:つや|艶|光沢)(?:のない|がない)", target
    ):
        pair = gloss[::-1]
    elif re.fullmatch(r"取っ手(?:がある|あり|付き)?", target):
        pair = handle
    if pair is None:
        colors = {
            "赤": ("red", "blue"),
            "青": ("blue", "red"),
            "白": ("white", "black"),
            "黒": ("black", "white"),
        }
        match = re.fullmatch(r"(赤|青|白|黒)(?:色|い)?", target)
        if match:
            color, other = colors[match[1]]
            pair = (f"A {color} product surface", f"A {other} product surface")
    return (
        None if pair is None else VisualContrast(origin="local", matching=pair[0], opposite=pair[1])
    )


def grammatical_negation(phrase):
    """Generate bounded Japanese hints, never assert that a negation is drawable."""
    from src.search_v2.tokenizer import _analyze_japanese_source

    expression = interpret_clause(phrase)
    if expression.strength == "neutral":
        return None
    target = expression.target
    presence = presence_condition(phrase)
    if presence is not None:
        part, present = presence
        return part + ("がない" if present else "がある")
    tokens = _analyze_japanese_source(target).morphemes
    if not tokens:
        return None
    last = tokens[-1]
    # Only a single adjective or an explicit noun-subject/adjective clause.
    prefix = target[: last.begin]
    if prefix:
        subject = re.fullmatch(r"(.+?)[がは]", prefix)
        if subject is None or not all(
            m.part_of_speech == "名詞" for m in _analyze_japanese_source(subject[1]).morphemes
        ):
            return None
    if (
        last.part_of_speech == "形容詞"
        and last.surface == last.dictionary_form
        and last.surface.endswith("い")
        and last.surface != "ない"
    ):
        # Sudachi's normalized lemma handles irregular いい -> 良い -> 良くない.
        lemma = last.normalized if last.dictionary_form == "いい" else last.dictionary_form
        return prefix + lemma[:-1] + "くない"
    if last.part_of_speech == "形状詞":
        return target + "ではない"
    return None


def presence_condition(phrase):
    """Recognize a complete part-presence clause without a component-name table."""
    from src.search_v2.tokenizer import _analyze_japanese_source

    expression = interpret_clause(phrase)
    if expression.strength == "neutral":
        return None
    target = expression.target
    match = re.fullmatch(
        r"(.+?)(付き|つき|が付属(?:する|している)?|が付いている|が付いた|[がは]ある|[がは]ない)",
        target,
    )
    if match:
        part, present = match[1], not match[2].endswith("ない")
    elif expression.strength == "excluded":
        part, present = target, True
    else:
        return None
    tokens = _analyze_japanese_source(part).morphemes
    if not tokens or not all(t.part_of_speech in {"名詞", "接尾辞", "接頭辞"} for t in tokens):
        return None
    return part, present


class ContrastResolver:
    """Prefer existing dictionary antonyms, then concrete presence grammar."""

    def __init__(self, dictionary=None, *, lexicon=None):
        self._dictionary = dictionary
        self._lexicon = lexicon

    def candidates(self, phrase):
        from src.search_v2.tokenizer import _analyze_japanese_source

        expression = interpret_clause(phrase)
        if presence_condition(phrase) is not None:
            return tuple(pair for pair, _ in self._part_candidates(phrase))
        if expression.strength == "neutral" or self._dictionary is None:
            return ()
        tokens = _analyze_japanese_source(expression.target).morphemes
        if len(tokens) != 1 or tokens[0].part_of_speech not in {"形容詞", "形状詞"}:
            return ()
        token = tokens[0]
        forms = tuple(dict.fromkeys((token.surface, token.dictionary_form, token.normalized)))
        return tuple(
            self._pair(
                expression.target,
                "wordnet",
                f"A product that is {matching}",
                f"A product that is {opposite}",
                (source, other),
            )
            for matching, opposite, source, other in self._dictionary.antonyms(forms)
        )

    def describe(self, pair):
        if pair.origin == "grammar":
            presence = presence_condition(pair.evidence.target)
            part = presence[0] if presence else pair.evidence.target
            if self._lexicon is not None and pair.evidence.sense_ids[0].startswith("jmdict:"):
                for sense in self._lexicon.lookup(part):
                    if sense.sense_id == pair.evidence.sense_ids[0]:
                        return sense.definition[:240]
            return pair.matching
        return self._dictionary.definition(pair.evidence.sense_ids[0])

    def resolve(self, phrase):
        from src.search_v2.tokenizer import _analyze_japanese_source

        expression = interpret_clause(phrase)
        if expression.strength == "neutral":
            return None
        target = expression.target
        tokens = _analyze_japanese_source(target).morphemes
        if (
            self._dictionary is not None
            and len(tokens) == 1
            and tokens[0].part_of_speech in {"形容詞", "形状詞"}
        ):
            token = tokens[0]
            forms = tuple(dict.fromkeys((token.surface, token.dictionary_form, token.normalized)))
            found = self._dictionary.antonym(forms)
            if found:
                matching, opposite, source, other = found
                return self._pair(
                    target,
                    "wordnet",
                    f"A product that is {matching}",
                    f"A product that is {opposite}",
                    (source, other),
                )
        candidates = self._part_candidates(phrase)
        return candidates[0][0] if len(candidates) == 1 else None

    def _part_candidates(self, phrase):
        presence = presence_condition(phrase)
        if presence is None:
            return ()
        part, _ = presence
        found = self._dictionary.noun((part,)) if self._dictionary else None
        if found:
            english, sense = found
            pair = self.presence_proposal(
                phrase, english, dictionary_sha256=self._dictionary.sha256, sense_id=sense
            )
            return ((pair, pair.matching),)
        if self._lexicon is None:
            return ()
        from src.search_v2.lexical_selection import terms_from_sense

        senses = self._lexicon.lookup(part)
        if not 0 < len(senses) <= 4:
            return ()
        candidates = []
        for sense in senses:
            if sense.source != "jmdict" or not re.fullmatch(SENSE_PATTERN, sense.sense_id):
                return ()
            english = terms_from_sense(part, sense).original_en
            if english is None:
                return ()
            try:
                pair = self.presence_proposal(
                    phrase, english, dictionary_sha256=self._lexicon.sha256, sense_id=sense.sense_id
                )
            except ValueError:
                return ()  # A dictionary gloss is not always a usable component noun.
            candidates.append((pair, sense.definition[:240]))
        return tuple(candidates)

    def presence_proposal(self, phrase, english, *, dictionary_sha256=None, sense_id=None):
        presence = presence_condition(phrase)
        if (
            presence is None
            or type(english) is not str
            or len(english) > 80
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*(?:[- '][A-Za-z0-9]+){0,7}", english)
        ):
            raise ValueError("Invalid component noun")
        if re.search(r"\b(?:with|without|not|no|and|or)\b", english, re.I):
            raise ValueError("Component noun includes a condition")
        matching, opposite = (
            f"A product with a visible {english}",
            f"A product without any {english}",
        )
        if not presence[1]:
            matching, opposite = opposite, matching
        return VisualContrast(
            profile=CURRENT_PROFILE,
            origin="grammar" if sense_id else "bonsai",
            matching=matching,
            opposite=opposite,
            evidence=ContrastEvidence(
                target=interpret_clause(phrase).target,
                dictionary_sha256=dictionary_sha256,
                sense_ids=(sense_id,) if sense_id else (),
            ),
        )

    def _pair(self, target, origin, matching, opposite, senses):
        return VisualContrast(
            profile=CURRENT_PROFILE,
            origin=origin,
            matching=matching,
            opposite=opposite,
            evidence=ContrastEvidence(
                target=target, dictionary_sha256=self._dictionary.sha256, sense_ids=senses
            ),
        )
