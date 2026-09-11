"""Source structure must preserve the target, modifiers and uncertainty."""

import pytest

from src.search_v2.lexical_structure import ProductStructure, TextSpan, validate_structure
from src.search_v2.candidate_queries import build_candidate_queries


def structure(source, product, fragments, ignored=()):
    def span(text):
        start = source.index(text)
        return TextSpan(start, start + len(text))

    return ProductStructure(
        source,
        span(product),
        tuple(span(t) for t in fragments),
        tuple(span(t) for t in ignored),
        "fixture",
    )


def test_search_predicate_does_not_become_product():
    source = "名刺入れを探しています。"
    parsed = structure(source, "名刺入れ", (), ("探しています",))
    query = build_candidate_queries(source, structure=parsed)
    assert query.retrieval_intent.product_name_ja == "名刺入れ"


def test_inline_price_is_kept_out_of_product_but_retained_as_condition():
    source = "3000円以下の花瓶を探しています。"
    parsed = structure(source, "花瓶", ("3000円以下",), ("探しています",))
    query = build_candidate_queries(source, structure=parsed)
    assert query.retrieval_intent.product_name_ja == "花瓶"
    assert query.retrieval_intent.price.max_jpy == 3000


def test_unhandled_attachment_cannot_disappear():
    source = "机に固定するライトが欲しい。"
    parsed = structure(source, "ライト", ("机に固定する",), ("欲しい",))
    with pytest.raises(ValueError):
        build_candidate_queries(source, structure=parsed)


def test_structure_cannot_be_reused_with_another_source():
    source = "名刺入れを探しています。"
    parsed = structure(source, "名刺入れ", (), ("探しています",))
    with pytest.raises(ValueError):
        validate_structure("花瓶を探しています。", parsed)


def test_ignored_span_cannot_hide_a_condition():
    source = "名刺入れ。USB対応。"
    parsed = structure(source, "名刺入れ", (), ("USB対応",))
    with pytest.raises(ValueError):
        validate_structure(source, parsed)
