import pytest

from src.search_v2.tokenizer import _analyze_japanese_source
from src.search_v2.tokenizer import tokenize_search_text


def test_japanese_tokenizer_preserves_surface_order_and_filters_particles() -> None:
    value = "軽量で防水のUSB-Cケース"

    first = tokenize_search_text(value, language="ja")
    second = tokenize_search_text(value, language="ja")

    assert first == ["軽量", "防水", "usb", "c", "ケース"]
    assert second == first


def test_japanese_tokenizer_does_not_add_sudachi_transliteration_for_latin_surface() -> None:
    assert tokenize_search_text("Sony製のケース", language="ja") == ["sony製", "ケース"]


def test_japanese_tokenizer_keeps_consecutive_prefixes_with_their_content_word() -> None:
    assert tokenize_search_text("超低背キーボード", language="ja") == [
        "超低背",
        "キーボード",
    ]


def test_english_tokenizer_nfkc_casefolds_and_deduplicates_in_order() -> None:
    assert tokenize_search_text(
        "Noise-Cancelling HEADPHONES, ＩＰＸ７ headphones",
        language="en",
    ) == ["noise", "cancelling", "headphones", "ipx7"]


def test_japanese_tokenizer_returns_no_tokens_for_particles_and_punctuation() -> None:
    assert tokenize_search_text("の、を。", language="ja") == []


def test_source_analysis_preserves_morpheme_boundaries_and_exact_spans() -> None:
    analyzed = _analyze_japanese_source("白い製品と白鳥観察。藍鼠色")

    assert [item.surface for item in analyzed.morphemes] == [
        "白い",
        "製品",
        "と",
        "白鳥",
        "観察",
        "。",
        "藍鼠",
        "色",
    ]
    assert all(analyzed.text[item.begin : item.end] == item.surface for item in analyzed.morphemes)
    assert analyzed.morphemes[0].part_of_speech == "形容詞"
    assert analyzed.morphemes[3].normalized == "白鳥"


def test_source_analysis_keeps_particles_and_negative_markers() -> None:
    analyzed = _analyze_japanese_source("静音キーボードでテンキーは不要")

    assert [item.normalized for item in analyzed.morphemes] == [
        "静音",
        "キーボード",
        "で",
        "テンキー",
        "は",
        "不要",
    ]


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com/item",
        "ftp://example.com/item",
        "ｗｗｗ．example.com/item",
        "商品\n追加条件",
        "商品\x00追加条件",
    ],
)
def test_tokenizer_rejects_url_newline_and_control_characters(value: str) -> None:
    with pytest.raises(ValueError):
        tokenize_search_text(value, language="ja")


def test_tokenizer_rejects_an_unsupported_language() -> None:
    with pytest.raises(ValueError, match="unsupported tokenizer language"):
        tokenize_search_text("headphones", language="fr")
