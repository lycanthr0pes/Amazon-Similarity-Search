"""Suffixes survive product extraction and repeated query tokenization."""

import json

import pytest

from src.search_v2.candidate_queries import build_candidate_queries
from src.search_v2.outscraper_request import build_outscraper_request
from src.search_v2.tokenizer import tokenize_search_text
import test_bonsai_query_terms as terms


@pytest.mark.parametrize(
    "source,expected",
    [
        ("名刺入れ", ["名刺入れ"]),
        ("子供用", ["子供用"]),
        ("山田さん", ["山田さん"]),
        ("Sony製のケース", ["sony製", "ケース"]),
        ("個人向け用", ["個人向け用"]),
        ("名刺 名刺入れ", ["名刺", "名刺入れ"]),
        ("名刺入れ 名刺入れ", ["名刺入れ"]),
    ],
)
def test_suffixes_survive_without_collapsing_distinct_words(source, expected):
    assert tokenize_search_text(source, language="ja") == expected
    assert tokenize_search_text(" ".join(expected), language="ja") == expected


def test_final_search_request_keeps_card_case_product():
    queries = build_candidate_queries("名刺入れ。3000円以下。")
    request = build_outscraper_request(queries.query_plan, postal_code="100-0001")
    assert queries.retrieval_intent.product_name_ja == "名刺入れ"
    assert [query.value for query in request.queries] == ["名刺入れ"]
    assert "商品: 名刺入れ" in queries.image_prompt


def test_bonsai_receives_complete_product_name(tmp_path):
    from test_candidate_search import module, flow

    bonsai = terms.QueryBonsai(
        tmp_path, terms.response({"original_en": "business card case", "synonyms": []})
    )
    service = module().prepare_candidate_search(
        "名刺入れ。3000円以下。",
        owner_id="owner-1",
        session_id="suffix-test",
        postal_code="100-0001",
        normalization_profile=flow.backend_policy().normalization_profile,
        now=flow.NOW,
        query_expander=bonsai,
    )
    body = json.loads(bonsai.calls[0])
    assert json.loads(body["messages"][1]["content"])["product_phrase"] == "名刺入れ"
    assert service.plan.query_options[0].value == "名刺入れ"
    assert service.plan.query_options[1].value == "business card case"
