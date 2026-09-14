"""Blank syntax fragments cannot become conditions or point at a product name."""

from types import SimpleNamespace

import pytest

from src.search_v2.bonsai_visual_conditions import _visual_clauses
from src.search_v2.condition_language import ConditionLanguageError, display_issues
from src.search_v2.lexical_runtime import GinzaProductParser
from src.search_v2.lexical_structure import ProductStructure, TextSpan


class Token(SimpleNamespace):
    def __len__(self):
        return len(self.text)


@pytest.mark.parametrize("blank", ["\n\n", "\r\n", "  ", "\t"])
def test_parser_does_not_emit_blank_only_fragments(blank):
    source = "花瓶。" + blank
    doc = [
        Token(text="花瓶", idx=0, pos_="NOUN", dep_="ROOT", lemma_="花瓶"),
        Token(text="。", idx=2, pos_="PUNCT", dep_="punct", lemma_="。"),
        Token(text=blank, idx=3, pos_="SPACE", dep_="dep", lemma_=blank),
    ]
    parser = GinzaProductParser.__new__(GinzaProductParser)
    parser.parser_id = "fixture"
    parser._nlp = lambda _: doc
    parsed = parser.analyze(source)
    assert parsed.product.text(parsed.source) == "花瓶"
    assert parsed.fragments == ()


@pytest.mark.parametrize("blank", ["\n\n", "\r\n", "  ", "\t"])
def test_visual_candidates_ignore_blank_fragments_and_preserve_conditions(blank):
    phrase = "丸みのある形"
    source = "花瓶。" + blank + phrase + "。" + blank
    start = source.index(phrase)
    parsed = ProductStructure(
        source,
        TextSpan(0, 2),
        (
            TextSpan(3, start),
            TextSpan(start, start + len(phrase)),
            TextSpan(len(source) - len(blank), len(source)),
        ),
        (),
        "fixture",
    )
    assert _visual_clauses(source, parsed) == (phrase,)


def test_incomplete_modifier_reports_its_source_position_not_the_product():
    source = "花瓶。青を希望。"
    start = source.index("希望")
    parsed = ProductStructure(source, TextSpan(0, 2), (TextSpan(start, start + 2),), (), "fixture")
    with pytest.raises(ConditionLanguageError) as caught:
        _visual_clauses(source, parsed)
    assert display_issues(source, caught.value.issues) == [
        {"start": start, "end": start + 2, "quote": "希望", "code": "modifier_scope"}
    ]


def test_prepared_local_parser_accepts_blank_lines_around_a_visual_condition():
    pytest.importorskip("spacy")
    pytest.importorskip("ja_ginza")
    source = "花瓶。\n\n丸みのある形。\n\n"
    parsed = GinzaProductParser().analyze(source)
    assert _visual_clauses(source, parsed) == ("丸みのある形",)
    assert all(span.text(parsed.source).strip() for span in parsed.fragments)
