"""Generation and reception share the source-owned visual candidate boundary."""

import json

import pytest

from src.search_v2.bonsai_visual_conditions import build_visual_request, parse_visual_response
from src.search_v2.candidate_queries import build_candidate_queries
from src.search_v2.counterfactual_image import VisualConditionDraft, build_visual_condition_set


@pytest.mark.parametrize(
    "source,expected",
    [
        ("マグカップ。丸みのある形。3000円以下。", ["丸みのある形"]),
        ("３０００円以下。丸みのある形。マグカップ。", ["丸みのある形"]),
        ("スキャナー。なめらかな質感。光学解像度600dpi以上。USB対応。", ["なめらかな質感"]),
        ("トルクレンチ。高級感のある見た目を希望。耐荷重50kg以上。", ["高級感のある見た目を希望"]),
        ("机。木目調を除外。幅100mm以下。", ["木目調を除外"]),
        ("椅子。白。耐荷重100kg以上。", ["白"]),
        ("白。マグカップ。容量350ml以上。", ["白"]),
        ("３Ｄプリンター。丸みのある形。10000円以下。", ["丸みのある形"]),
        ("椅子。丸みのある形ではない。高級感または素朴な印象。", ["丸みのある形ではない"]),
    ],
)
def test_only_visual_candidates_are_offered(source, expected):
    request = json.loads(build_visual_request(source))
    payload = json.loads(request["messages"][1]["content"])
    schema = request["response_format"]["schema"]["properties"]["conditions"]
    assert payload["clauses"] == expected
    assert schema["items"]["properties"]["source_phrase"]["enum"] == expected
    assert schema["maxItems"] == min(3, len(expected))
    assert payload["source"] == source


@pytest.mark.parametrize(
    "source", ["マグカップ。3000円以下。", "スキャナー。600dpi以上。USB対応。", "マグカップ"]
)
def test_no_visual_candidates_have_an_empty_array_contract(source):
    request = json.loads(build_visual_request(source))
    payload = json.loads(request["messages"][1]["content"])
    conditions = request["response_format"]["schema"]["properties"]["conditions"]
    assert payload["clauses"] == []
    assert conditions["maxItems"] == 0
    assert "enum" not in conditions["items"]["properties"]["source_phrase"]


@pytest.mark.parametrize("phrase", ["マグカップ", "3000円以下"])
def test_excluded_candidate_is_rejected_even_if_provider_ignores_schema(phrase):
    raw = json.dumps(
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": json.dumps(
                            {
                                "status": "ready",
                                "conditions": [
                                    {
                                        "source_phrase": phrase,
                                        "strength": "required",
                                        "attribute_key": None,
                                    }
                                ],
                            }
                        )
                    },
                }
            ]
        }
    ).encode()
    with pytest.raises(ValueError) as caught:
        parse_visual_response("マグカップ。丸みのある形。3000円以下。", raw)
    assert caught.value.diagnostic.code == "clause_scope"


def test_excluded_product_cannot_bypass_parser_via_direct_condition_set():
    source = "マグカップ。丸みのある形。3000円以下。"
    conditions = build_visual_condition_set(
        source_input=source,
        drafts=(
            VisualConditionDraft(
                source_phrase="マグカップ", strength="required", attribute_key=None
            ),
        ),
    )
    with pytest.raises(ValueError):
        build_candidate_queries(source, visual_conditions=conditions)


def test_visual_selection_preserves_product_and_price_constraints():
    source = "マグカップ。丸みのある形。3000円以下。"
    raw = json.dumps(
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": json.dumps(
                            {
                                "status": "ready",
                                "conditions": [
                                    {
                                        "source_phrase": "丸みのある形",
                                        "strength": "required",
                                        "attribute_key": None,
                                    }
                                ],
                            }
                        )
                    },
                }
            ]
        }
    ).encode()
    conditions = parse_visual_response(source, raw)
    queries = build_candidate_queries(source, visual_conditions=conditions)
    assert [q.value for q in queries.query_plan.queries] == ["マグカップ"]
    assert queries.retrieval_intent.price.max_jpy == 3000
    assert "3000" not in queries.image_prompt
    assert "丸みのある形" in queries.image_prompt


@pytest.mark.parametrize("source", ["机。木目調。", "高級感。マグカップ。3000円以下。"])
def test_ambiguous_nominal_clauses_are_held_without_guessing_product(source):
    with pytest.raises(ValueError) as caught:
        build_visual_request(source)
    assert caught.value.diagnostic.code == "product_scope"
