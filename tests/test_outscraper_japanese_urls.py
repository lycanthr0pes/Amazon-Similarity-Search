"""Japanese page requests retain approval, response binding and legacy identity."""

from urllib.parse import parse_qsl, urlsplit

import pytest

from src.search_v2.outscraper_contract import (
    OutscraperAmazonProductsRequest,
    build_outscraper_request,
    japanese_search_url,
    outscraper_request_sha256,
)
from src.search_v2.outscraper_http import _validated_params
from src.search_v2.query_planner import SearchQuery, SearchQueryPlan
from test_search_v2_product_normalization import normalize


def request(*, japanese=True, query="丸い & 青い マグカップ"):
    return build_outscraper_request(
        SearchQueryPlan(
            schema_version="2.0",
            intent_sha256="a" * 64,
            queries=[SearchQuery(language="ja", value=query)],
        ),
        postal_code="100-0001",
        japanese_search_urls=japanese,
    )


def test_japanese_search_url_preserves_terms_and_separates_request_identity():
    current, legacy = request(), request(japanese=False)
    assert current.queries == legacy.queries
    assert current.maximum_candidates == legacy.maximum_candidates == 24
    assert current.endpoint == legacy.endpoint
    url = urlsplit(current.provider_queries()[0])
    assert url.scheme == "https" and url.netloc == "www.amazon.co.jp" and url.path == "/s"
    assert parse_qsl(url.query) == [("k", current.queries[0].value), ("language", "ja_JP")]
    assert legacy.provider_queries() == (legacy.queries[0].value,)
    assert current.query_parameters()[1:] == legacy.query_parameters()[1:]
    assert outscraper_request_sha256(current) != outscraper_request_sha256(legacy)
    restored = OutscraperAmazonProductsRequest.model_validate_json(legacy.model_dump_json())
    assert restored == legacy
    assert outscraper_request_sha256(restored) == outscraper_request_sha256(legacy)
    assert _validated_params(current.endpoint, current.query_parameters()) == (
        current.query_parameters()
    )


@pytest.mark.parametrize("query", ["語" * 200, "a+b & language=en_US # % / 日本語"])
def test_transport_accepts_encoded_search_terms_without_parameter_injection(query):
    current = request(query=query)
    params = _validated_params(current.endpoint, current.query_parameters())
    assert parse_qsl(urlsplit(params[0][1]).query) == [("k", query), ("language", "ja_JP")]


@pytest.mark.parametrize(
    "url",
    [
        "https://www.amazon.co.jp/s?k=fixture&language=en_US",
        "https://www.amazon.co.jp/s?k=fixture&language=ja_JP&language=en_US",
        "https://www.amazon.co.jp/s?k=fixture&language=ja_JP#extra",
        "https://www.amazon.co.jp/s?k=&language=ja_JP",
        japanese_search_url("語" * 201),
        japanese_search_url("fixture\nquery"),
    ],
)
def test_transport_rejects_noncanonical_or_unbounded_search_urls(url):
    current = request()
    with pytest.raises(ValueError):
        _validated_params(current.endpoint, (("query", url), *current.query_parameters()[1:]))


def test_response_query_must_match_wire_url_and_title_remains_observed():
    current = request()
    response = {"name": "日本語の商品名", "query": current.provider_queries()[0]}
    batch = normalize({"data": [response]}, request=current)
    assert len(batch.products) == 1 and batch.products[0].title == "日本語の商品名"
    assert batch.products[0].provenance.query_index == 0
    assert batch.products[0].provenance.query_language == "ja"
    for unapproved in (current.queries[0].value, current.provider_queries()[0] + "&x=1"):
        rejected = normalize({"data": [{**response, "query": unapproved}]}, request=current)
        assert not rejected.products and rejected.rejections[0].reason == "unapproved_query"
    english = normalize({"data": [{**response, "name": "Original English title"}]}, request=current)
    assert english.products[0].title == "Original English title"
