"""One explicitly paired translation per original or synonymous product term."""

import json

import pytest

import test_bonsai_query_terms as terms
import test_candidate_search_live_e2e as live


def payload():
    return {
        "original_en": "scanner",
        "synonyms": [{"ja": "読取装置", "en": "reading device"}],
    }


def test_schema_binds_one_translation_to_each_term():
    request = json.loads(terms.module().build_query_terms_request(terms.SOURCE, "スキャナー"))
    schema = request["response_format"]["schema"]
    assert set(schema["properties"]) == {"original_en", "synonyms"}
    original = schema["properties"]["original_en"]
    assert original == {
        "anyOf": [{"type": "string", "minLength": 1, "maxLength": 64}, {"type": "null"}]
    }
    synonyms = schema["properties"]["synonyms"]
    assert synonyms["maxItems"] == 3
    assert synonyms["items"]["required"] == ["ja", "en"]
    assert synonyms["items"]["properties"]["en"] == original


def test_parser_preserves_correspondence_and_explicit_abstention():
    value = payload()
    value["synonyms"].append({"ja": "スキャン装置", "en": None})
    result = terms.module().parse_query_terms_response("スキャナー", terms.response(value))
    assert result.original_en == "scanner"
    assert [(row.ja, row.en) for row in result.synonyms] == [
        ("読取装置", "reading device"),
        ("スキャン装置", None),
    ]


@pytest.mark.parametrize(
    "mutation",
    ["original_list", "synonym_list", "missing_translation", "conflict", "extra", "old_list"],
)
def test_unpaired_or_multiple_translations_are_rejected(mutation):
    value = payload()
    if mutation == "original_list":
        value["original_en"] = ["scanner", "reader"]
    elif mutation == "synonym_list":
        value["synonyms"][0]["en"] = ["reading device", "reader"]
    elif mutation == "missing_translation":
        del value["synonyms"][0]["en"]
    elif mutation == "conflict":
        value["synonyms"].append({"ja": "読取装置", "en": "reader"})
    elif mutation == "extra":
        value["synonyms"][0]["other_en"] = "reader"
    else:
        value = {"synonyms_ja": ["読取装置"], "translations_en": ["scanner"]}
    with pytest.raises(ValueError):
        terms.module().parse_query_terms_response("スキャナー", terms.response(value))


def test_all_eight_choices_are_reviewable_and_last_is_selectable(tmp_path):
    value = payload()
    value["synonyms"] += [
        {"ja": "スキャン装置", "en": "scanning device"},
        {"ja": "画像読取機", "en": "image reader"},
    ]
    service, _, query = terms.start(tmp_path, terms.response(value))
    assert service.plan.query_expansion.profile_id == "bonsai-query-terms-v2"
    assert len(service.plan.query_options) == 8
    assert service.plan.query_options[-1].value == "image reader"
    service.select_search_query(
        owner_id="owner-1", plan_sha256=service.plan_sha256, index=7, now=terms.candidate.flow.NOW
    )
    assert service.plan.request.queries[0].value == "image reader"
    assert service.plan.request.maximum_candidates == 24
    assert len(query.calls) == 1


def test_review_contains_the_translation_pairs(tmp_path, monkeypatch):
    module, config, services, _, _ = live.setup_run(tmp_path, monkeypatch)
    captured = []

    def select(review):
        captured.append(review)
        return 2

    result = module.run_candidate_e2e(
        config,
        services,
        select_query=select,
        lexical_expander=live.lexical_expander(),
        image_score_mode="appearance",
    )
    assert result["status"] == "succeeded"
    assert captured[0]["query_terms"] == {
        "original_en": "mug",
        "synonyms": [{"ja": "マグ", "en": "mug"}],
    }
