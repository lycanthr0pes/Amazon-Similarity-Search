"""移行中に保持する現行backendの観察可能な挙動を固定する。"""

import json

import pytest

from src.config import settings
from src.main.run import run_product_search
from src.schemas import NormalizedAmazonProduct
from src.schemas import ProductAttributes
from src.services.outscraper_search_select import select_outscraper_query
from src.services.product_scoring import calculate_price_score
from src.services.product_scoring import score_products
from src.utilities.json_editor import write_json


def test_legacy_query_selection_does_not_skip_an_invalid_first_japanese_query() -> None:
    """現行処理は配列を探索せず、先頭の日本語queryだけを検証する。"""

    attrs = ProductAttributes(
        estimated_product_name_ja="キーボード",
        search_queries_ja=["", "静音 キーボード"],
        search_queries_en=["quiet keyboard"],
    )

    with pytest.raises(ValueError, match="must not be empty"):
        select_outscraper_query(attrs)


def test_legacy_attributes_coerce_price_and_ignore_unknown_fields() -> None:
    """現行cache/Bonsai互換modelのpermissiveな入力境界を記録する。"""

    attrs = ProductAttributes.model_validate(
        {
            "estimated_product_name_ja": "マウス",
            "max_price_jpy": "5000",
            "future_field": "ignored",
        }
    )

    assert attrs.max_price_jpy == 5000
    assert "future_field" not in attrs.model_dump()


def test_legacy_price_score_distinguishes_missing_price_from_no_price_condition() -> None:
    """商品価格欠損は0.0、価格条件なしの既知価格は中立値0.5である。"""

    attrs = ProductAttributes(estimated_product_name_ja="マウス")

    assert calculate_price_score(attrs, NormalizedAmazonProduct(title="欠損")) == 0.0
    assert (
        calculate_price_score(
            attrs,
            NormalizedAmazonProduct(title="価格あり", price_jpy=5000),
        )
        == 0.5
    )


def test_legacy_equal_scores_preserve_input_order() -> None:
    """同点時の追加tie-breakがなく、Pythonのstable sortで入力順を保つ。"""

    attrs = ProductAttributes(estimated_product_name_ja="マウス")
    products = [
        NormalizedAmazonProduct(asin="FIRST", title="同一商品"),
        NormalizedAmazonProduct(asin="SECOND", title="同一商品"),
    ]

    scored = score_products(attrs, products)

    assert scored[0].total_score == scored[1].total_score
    assert [product.asin for product in scored] == ["FIRST", "SECOND"]


def test_legacy_tfidf_score_depends_on_the_other_candidates() -> None:
    """現行TF-IDFは検索結果集合全体でIDFをfitするため、候補追加で既存scoreも変わる。"""

    attrs = ProductAttributes(
        estimated_product_name_ja="無関係",
        estimated_product_name_en="alpha beta",
    )
    target = NormalizedAmazonProduct(asin="TARGET", title="alpha")
    duplicate = NormalizedAmazonProduct(asin="DUPLICATE", title="alpha")

    isolated = score_products(attrs, [target])
    with_duplicate = score_products(attrs, [target, duplicate])
    isolated_target = next(product for product in isolated if product.asin == "TARGET")
    duplicate_target = next(product for product in with_duplicate if product.asin == "TARGET")

    assert isolated_target.title_similarity == 0.7093
    assert duplicate_target.title_similarity == 0.6411


def test_legacy_use_cache_false_recomputes_even_when_files_exist(monkeypatch, tmp_path) -> None:
    """use_cache=Falseは既存fileを読まず、外部adapterを毎回呼ぶ。"""

    import src.clients.bonsai_client as bonsai_client
    import src.clients.playwright_client as playwright_client

    calls = {"bonsai": 0, "outscraper": 0}

    def fake_call_bonsai(user_input: str) -> str:
        calls["bonsai"] += 1
        return json.dumps(
            {
                "estimated_product_name_ja": user_input,
                "search_queries_ja": [user_input],
            },
            ensure_ascii=False,
        )

    def fake_call_outscraper(query: str, cache_key: str):
        calls["outscraper"] += 1
        path = tmp_path / "playwright-v3" / "raw" / f"{cache_key}.json"
        write_json(
            path,
            {
                "status": "success",
                "data": [[{"name": query, "asin": "B000BASELINE", "price_parsed": 5000}]],
            },
        )
        return path

    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    monkeypatch.setattr(settings, "enable_cache", True)
    monkeypatch.setattr(bonsai_client, "call_bonsai", fake_call_bonsai)
    monkeypatch.setattr(playwright_client, "call_playwright", fake_call_outscraper)

    first = run_product_search("静音マウス", use_cache=False)
    second = run_product_search("静音マウス", use_cache=False)

    assert first == second
    assert calls == {"bonsai": 2, "outscraper": 2}
