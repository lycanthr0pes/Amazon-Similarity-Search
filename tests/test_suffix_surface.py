"""Inflected stems keep their source spelling when suffixes are attached."""

import pytest

from src.search_v2.tokenizer import tokenize_search_text


@pytest.mark.parametrize(
    "source", ["軽さ", "使いやすさ", "美しさ", "柔らかさ", "涼しげ", "取り付け用", "子ども用"]
)
def test_suffix_keeps_source_stem_and_survives_retokenization(source):
    tokens = tokenize_search_text(source, language="ja")
    assert tokens == [source]
    assert tokenize_search_text(" ".join(tokens), language="ja") == tokens
