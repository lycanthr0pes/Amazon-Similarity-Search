import pytest
from pydantic import ValidationError

from src.search_v2.intent import IntentProvenance
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent
from src.search_v2.query_planner import SearchQuery
from src.search_v2.query_planner import SearchQueryPlan
from src.search_v2.query_planner import build_search_query_plan
from src.search_v2.query_planner import search_query_plan_sha256


def normalized_intent(**overrides):
    payload = {
        "product_name_ja": "ヘッドホン",
        "product_name_en": "headphones",
        "category_ja": "オーディオ",
        "category_en": "audio",
        "required_terms_ja": ["ワイヤレス", "ノイズキャンセリング"],
        "required_terms_en": ["wireless", "noise cancelling"],
        "preferred_terms_ja": ["軽量"],
        "preferred_terms_en": ["lightweight"],
        "negative_terms_ja": ["中古"],
        "negative_terms_en": ["used"],
        "color_ja": "黒",
        "color_en": "black",
        "features_ja": [],
        "features_en": [],
        "brand": "Sony",
        "model_number": "WH-1000XM5",
        "price": {
            "currency": "JPY",
            "mode": "none",
            "target_jpy": None,
            "min_jpy": None,
            "max_jpy": None,
            "source": "none",
            "confidence": None,
        },
        "typed_conditions": [],
        "ambiguities": [],
    }
    payload.update(overrides)
    source_input = "Sony WH-1000XM5のワイヤレスヘッドホン"
    draft = SearchIntentDraft.model_validate(payload)
    provenance = build_intent_provenance(
        source_input=source_input,
        prompt=b"prompt",
        schema=b"schema",
        response=b"response",
    )
    return normalize_search_intent(source_input, draft, provenance=provenance)


def test_query_plan_is_deterministic_bilingual_and_excludes_negative_terms() -> None:
    intent = normalized_intent()

    first = build_search_query_plan(intent)
    second = build_search_query_plan(intent)

    assert first == second
    assert [query.language for query in first.queries] == ["ja", "en"]
    assert first.queries[0].value == (
        "ヘッドホン オーディオ Sony WH-1000XM5 ワイヤレス ノイズキャンセリング 軽量"
    )
    assert first.queries[1].value == (
        "headphones audio Sony WH-1000XM5 wireless noise cancelling lightweight"
    )
    assert "中古" not in first.queries[0].value
    assert "used" not in first.queries[1].value
    assert search_query_plan_sha256(first) == search_query_plan_sha256(second)


def test_query_plan_drops_whole_low_priority_terms_at_200_character_limit() -> None:
    long_name = "A" * 190
    intent = normalized_intent(
        product_name_ja=None,
        product_name_en=long_name,
        category_ja=None,
        category_en=None,
        required_terms_ja=[],
        required_terms_en=["additional required condition"],
        preferred_terms_ja=[],
        preferred_terms_en=[],
        brand=None,
        model_number=None,
    )

    plan = build_search_query_plan(intent)

    assert len(plan.queries) == 1
    assert plan.queries[0].value == long_name.casefold()
    assert len(plan.queries[0].value) <= 200


def test_query_plan_collapses_equivalent_japanese_and_english_queries() -> None:
    intent = normalized_intent(
        product_name_ja="USB C Cable",
        product_name_en="ＵＳＢ　Ｃ　Ｃａｂｌｅ",
        category_ja=None,
        category_en=None,
        required_terms_ja=[],
        required_terms_en=[],
        preferred_terms_ja=[],
        preferred_terms_en=[],
        brand=None,
        model_number=None,
    )

    plan = build_search_query_plan(intent)

    assert [(query.language, query.value) for query in plan.queries] == [("ja", "usb c cable")]


def test_query_plan_tokenizes_semantic_terms_but_preserves_identifier_spelling() -> None:
    intent = normalized_intent(
        product_name_ja="軽量で防水のUSB-Cケース",
        product_name_en="Noise-Cancelling HEADPHONES",
        category_ja=None,
        category_en=None,
        required_terms_ja=[],
        required_terms_en=[],
        preferred_terms_ja=[],
        preferred_terms_en=[],
    )

    plan = build_search_query_plan(intent)

    assert [(query.language, query.value) for query in plan.queries] == [
        ("ja", "軽量 防水 usb c ケース Sony WH-1000XM5"),
        ("en", "noise cancelling headphones Sony WH-1000XM5"),
    ]


def test_query_plan_rejects_a_url_before_token_punctuation_is_removed() -> None:
    intent = normalized_intent(
        product_name_ja="ｈｔｔｐ：／／example.com/item",
        product_name_en=None,
        category_ja=None,
        category_en=None,
        required_terms_ja=[],
        required_terms_en=[],
        preferred_terms_ja=[],
        preferred_terms_en=[],
        brand=None,
        model_number=None,
    )

    with pytest.raises(ValueError, match="URL"):
        build_search_query_plan(intent)


def test_query_plan_stops_on_a_blocking_ambiguity() -> None:
    intent = normalized_intent(
        ambiguities=[
            {
                "code": "product_type_unknown",
                "message": "商品種別を確認してください",
                "blocking": True,
            }
        ]
    )

    with pytest.raises(ValueError, match="blocking ambiguity"):
        build_search_query_plan(intent)


@pytest.mark.parametrize(
    "value",
    ["https://example.com/item", "ftp://example.com/item", "商品\n追加条件", "   "],
)
def test_search_query_rejects_url_newline_and_empty_value(value: str) -> None:
    with pytest.raises(ValidationError):
        SearchQuery(language="ja", value=value)


def test_search_query_plan_rejects_duplicate_language() -> None:
    with pytest.raises(ValidationError, match="one query per language"):
        SearchQueryPlan(
            schema_version="2.0",
            intent_sha256="a" * 64,
            queries=[
                SearchQuery(language="ja", value="商品"),
                SearchQuery(language="ja", value="別の商品"),
            ],
        )


def test_search_query_plan_revalidates_preconstructed_queries() -> None:
    forged_query = SearchQuery.model_construct(
        language="ja",
        value="https://example.com/item",
    )

    with pytest.raises(ValidationError):
        SearchQueryPlan(
            schema_version="2.0",
            intent_sha256="a" * 64,
            queries=[forged_query],
        )


def test_query_planner_revalidates_a_preconstructed_top_level_intent() -> None:
    intent = normalized_intent()
    forged_provenance = IntentProvenance.model_construct(
        source_input_sha256="not-a-digest",
        prompt_sha256="b" * 64,
        schema_sha256="c" * 64,
        response_sha256="d" * 64,
    )
    forged_intent = intent.model_copy(update={"provenance": forged_provenance})

    with pytest.raises(ValidationError):
        build_search_query_plan(forged_intent)
