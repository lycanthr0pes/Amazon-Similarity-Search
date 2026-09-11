"""Source-bound syntax proposals. Unconsumed content must never disappear."""

from dataclasses import dataclass, replace
import re

from src.search_v2.tokenizer import _analyze_japanese_source


_REQUEST_WORDS = re.compile(r"(?:探す|探し(?:て(?:い(?:る|ます)?)?)?|欲しい|ほしい|買う|購入する)")


def is_request_phrase(text):
    morphemes = _analyze_japanese_source(text).morphemes
    if not morphemes:
        return False
    words = [m.dictionary_form for m in morphemes]
    start = 2 if words[:2] == ["購入", "する"] else 1
    if start == 1 and words[0] not in {"探す", "欲しい", "ほしい", "買う"}:
        return False
    return all(
        m.part_of_speech in {"助動詞", "助詞", "補助記号", "空白"}
        or m.dictionary_form in {"いる", "居る"}
        for m in morphemes[start:]
    ) and not any(w in {"ない", "ぬ", "ず"} for w in words[start:])


@dataclass(frozen=True)
class TextSpan:
    start: int
    end: int

    def text(self, source):
        return source[self.start : self.end]


@dataclass(frozen=True, repr=False)
class ProductStructure:
    source: str
    product: TextSpan
    fragments: tuple[TextSpan, ...]
    ignored: tuple[TextSpan, ...]
    parser_id: str
    original_source: str | None = None


def validate_structure(source, structure):
    normalized = _analyze_japanese_source(source).text
    if type(structure) is not ProductStructure:
        raise ValueError("Invalid source structure")
    if structure.original_source is not None and structure.original_source != source:
        raise ValueError("Structure belongs to another original source")
    if type(structure) is not ProductStructure or structure.source != normalized:
        raise ValueError("Structure belongs to another source")
    if not structure.parser_id or len(structure.fragments) > 16 or len(structure.ignored) > 4:
        raise ValueError("Invalid structure bounds")
    spans = (structure.product, *structure.fragments, *structure.ignored)
    occupied = set()
    for span in spans:
        if (
            type(span) is not TextSpan
            or type(span.start) is not int
            or type(span.end) is not int
            or not 0 <= span.start < span.end <= len(normalized)
        ):
            raise ValueError("Invalid source span")
        positions = set(range(span.start, span.end))
        if occupied & positions:
            raise ValueError("Overlapping source spans")
        occupied.update(positions)
    for span in structure.ignored:
        if not is_request_phrase(span.text(normalized)):
            raise ValueError("A condition cannot be ignored as request wording")
    return replace(structure, original_source=source)


def syntax_remainder(source, structure, consumed):
    validate_structure(source, structure)
    remaining = list(structure.source)
    for span in (structure.product, *structure.ignored):
        remaining[span.start : span.end] = " " * (span.end - span.start)
    text = "".join(remaining)
    for phrase in consumed:
        text = text.replace(phrase, " ")
    text = re.sub(r"[0-9]+(?:\.[0-9]+)?\s*(?:万|千)?円(?:以上|以下|以内)?", " ", text)
    # Only grammatical connectors may remain after every substantive condition.
    if re.sub(r"[\s。、、のをがはでにへとも]+", "", text):
        raise ValueError("Unresolved source conditions")
    return structure.product.text(structure.source)
