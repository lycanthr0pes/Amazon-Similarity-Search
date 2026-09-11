"""Dictionary suggestions retain the existing query-confirmation boundary."""

import json

import pytest

from src.search_v2.lexical_expansion import DictionaryQueryExpander
from src.search_v2.lexical_selection import LexicalSense
from src.search_v2.candidate_search import prepare_candidate_search, CandidatePlan
import test_candidate_search as candidate

NOW = candidate.flow.NOW
PROFILE = candidate.flow.backend_policy().normalization_profile


class Lexicon:
    sha256 = "a" * 64

    def lookup(self, phrase):
        return (
            LexicalSense(
                "fixture:case",
                "fixture",
                ("名刺入れ", "名刺ケース"),
                ("business card case",),
                "a case for business cards",
            ),
        )


class Scorer:
    sha256 = "b" * 64

    def scores(self, *_):
        raise AssertionError("An exact unique sense does not need model inference")


def test_dictionary_candidates_are_reviewable_and_source_bound():
    source = "名刺入れ。3000円以下。"
    search = prepare_candidate_search(
        source,
        owner_id="owner",
        session_id="session",
        postal_code="100-0001",
        normalization_profile=PROFILE,
        now=NOW,
        lexical_expander=DictionaryQueryExpander(Lexicon(), Scorer()),
    )
    plan = search.plan
    assert plan.query_expansion.profile_id == "dictionary-query-terms-v1"
    assert plan.query_expansion.selected_sense_id == "fixture:case"
    assert plan.query_options[0].value == "名刺入れ"
    assert any(q.value == "business card case" for q in plan.query_options)
    assert plan.selected_query_index == 0
    assert CandidatePlan.model_validate_json(plan.model_dump_json()) == plan
    search.select_search_query(
        owner_id="owner", plan_sha256=search.plan_sha256, index=len(plan.query_options) - 1, now=NOW
    )
    assert search.plan.request.queries[0].value == "business card case"


def test_missing_dictionary_sense_keeps_original_query():
    class Empty(Lexicon):
        def lookup(self, phrase):
            return ()

    expansion = DictionaryQueryExpander(Empty(), Scorer()).propose("未収録商品", "未収録商品")
    assert expansion.status == "unavailable" and expansion.terms is None


def test_dictionary_profile_requires_dictionary_provenance():
    result = DictionaryQueryExpander(Lexicon(), Scorer()).propose("名刺入れ", "名刺入れ")
    raw = json.loads(result.model_dump_json())
    raw.pop("dictionary_sha256")
    with pytest.raises(ValueError):
        type(result).model_validate_json(json.dumps(raw))


def test_saved_syntax_structure_cannot_change_original_source():
    from types import SimpleNamespace
    from test_lexical_structure import structure

    source = "名刺入れを探しています。"
    parser = SimpleNamespace(analyze=lambda _: structure(source, "名刺入れ", (), ("探しています",)))
    search = prepare_candidate_search(
        source,
        owner_id="owner",
        session_id="session",
        postal_code="100-0001",
        normalization_profile=PROFILE,
        now=NOW,
        source_parser=parser,
    )
    payload = json.loads(search.plan.model_dump_json())
    payload["source_structure"]["source"] = "架空商品を探しています。"
    with pytest.raises(ValueError):
        CandidatePlan.model_validate_json(json.dumps(payload))


def test_bonsai_visual_selection_keeps_full_negative_modifier(tmp_path):
    from types import SimpleNamespace
    from test_lexical_structure import structure
    from test_candidate_visual_conditions import VisualBonsai, draft

    source = "つやのない名刺入れが欲しい。"
    parser = SimpleNamespace(
        analyze=lambda _: structure(source, "名刺入れ", ("つやのない",), ("欲しい",))
    )
    bonsai = VisualBonsai(tmp_path, [draft("つやのない")])
    search = prepare_candidate_search(
        source,
        owner_id="owner",
        session_id="session",
        postal_code="100-0001",
        normalization_profile=PROFILE,
        now=NOW,
        source_parser=parser,
        visual_extractor=bonsai,
        lexical_expander=DictionaryQueryExpander(Lexicon(), Scorer()),
    )
    assert search.plan.visual_conditions.conditions[0].source_phrase == "つやのない"
    assert search.plan.query_plan.queries[0].value == "名刺入れ"
    assert CandidatePlan.model_validate_json(search.plan.model_dump_json()) == search.plan


def test_optional_translation_failure_clears_selected_sense(monkeypatch):
    def fail(*_):
        raise ValueError("fixture translation failure")

    monkeypatch.setattr("src.search_v2.lexical_expansion.terms_from_sense", fail)
    result = DictionaryQueryExpander(Lexicon(), Scorer()).propose("名刺入れ", "名刺入れ")
    assert result.status == "unavailable"
    assert result.terms is None
    assert result.selected_sense_id is None
