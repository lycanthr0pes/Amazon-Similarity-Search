"""Candidate text scoring uses descriptions and keeps original title evidence first."""

import json

import pytest

import test_candidate_search as candidate
import test_bonsai_query_terms as query_terms
from src.search_v2.candidate_search import CandidateRanking, CandidateSearch


def search(source, *, expander=None):
    return CandidateSearch(
        source,
        owner_id="owner-1",
        session_id="text-test",
        postal_code="100-0001",
        normalization_profile=candidate.flow.backend_policy().normalization_profile,
        now=candidate.flow.NOW,
        query_expander=expander,
    )


def rank(service, root, products):
    review, _ = candidate.retrieve(service, root, products)
    service.confirm(
        owner_id="owner-1", review_sha256=review.sha256, selections={}, now=candidate.flow.NOW
    )
    return service.rank(owner_id="owner-1", now=candidate.flow.NOW)


def test_description_mentions_improve_condition_score(tmp_path):
    result = rank(
        search("マグカップ。電子レンジ対応。"),
        tmp_path,
        [
            {"name": "マグカップ", "description": "毎日の食卓に使える商品です。"},
            {"name": "マグカップ", "description": "電子レンジで温め直すことができます。"},
        ],
    )
    assert [p.product.provenance.response_index for p in result.products] == [1, 0]
    assert result.products[0].text_score.required_ratio > 0.0
    assert result.products[1].text_score.required_ratio == 0.0
    assert result.products[0].text_score.conditions[0].source == "description"
    assert CandidateRanking.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize("description", ["電子レンジは使用できません。", "電子レンジ非対応です。"])
def test_description_negation_never_earns_positive_score(tmp_path, description):
    result = rank(
        search("マグカップ。電子レンジ対応。"),
        tmp_path,
        [
            {"name": "マグカップ", "description": description},
        ],
    )
    assert result.products[0].text_score.required_ratio == 0.0


def test_structured_disagreement_wins_over_description(tmp_path):
    result = rank(
        search("マグカップ。電子レンジ対応。"),
        tmp_path,
        [
            {
                "name": "マグカップ",
                "features": ["電子レンジ対応: 非対応"],
                "description": "電子レンジで使用できます。",
            },
        ],
    )
    assert result.products[0].text_score.required_ratio == 0.0
    assert result.products[0].evaluation.required_status == "contradicted"


def test_numeric_structured_value_wins_over_description(tmp_path):
    result = rank(
        search("マグカップ。容量400ml以上。"),
        tmp_path,
        [
            {"name": "マグカップ", "features": ["容量: 300ml"], "description": "容量: 500ml"},
        ],
    )
    assert result.products[0].evaluation.required_status == "contradicted"
    assert result.products[0].text_score.required_ratio == 0.0


def test_numeric_prose_compares_value_and_unit(tmp_path):
    result = rank(
        search("マグカップ。容量400ml以上。"),
        tmp_path,
        [
            {"name": "マグカップ", "description": "容量は0.3Lです。"},
            {"name": "マグカップ", "description": "容量は0.5Lです。"},
        ],
    )
    assert [p.product.provenance.response_index for p in result.products] == [1, 0]
    assert [p.text_score.required_ratio for p in result.products] == [1.0, 0.0]


def test_original_title_beats_synonym_but_synonym_beats_unrelated(tmp_path):
    result = rank(
        search("スキャナー", expander=query_terms.QueryBonsai(tmp_path)),
        tmp_path,
        [
            {"name": "収納箱"},
            {"name": "読取装置"},
            {"name": "スキャナー"},
        ],
    )
    assert [p.product.provenance.response_index for p in result.products] == [2, 1, 0]
    assert 1.0 == result.products[0].lexical_score > result.products[1].lexical_score > 0.0
    assert result.retrieval_plan.title_comparison.category_ja == "スキャナー"
    assert result.retrieval_plan.title_comparison.category_en == "scanner"


def test_title_brand_and_model_are_source_owned_fields(tmp_path):
    service = search("マグカップ。ブランド: ACME。型番: AB-123。")
    fields = service.plan.title_comparison
    assert fields.brand == "ACME"
    assert fields.model_number == "AB-123"
    assert fields.category_ja == "マグカップ"
    result = rank(
        service,
        tmp_path,
        [
            {"name": "マグカップ ACME AB-124"},
            {"name": "マグカップ ACME AB-123"},
        ],
    )
    assert [p.product.provenance.response_index for p in result.products] == [1, 0]
    plain = search("マグカップ").plan.title_comparison
    assert plain.brand is None and plain.model_number is None


def test_description_score_tampering_is_rejected(tmp_path):
    result = rank(search("マグカップ。電子レンジ対応。"), tmp_path, [{"name": "マグカップ"}])
    payload = json.loads(result.model_dump_json())
    payload["products"][0]["text_score"]["required_ratio"] = 1.0
    with pytest.raises(ValueError):
        CandidateRanking.model_validate_json(json.dumps(payload))
