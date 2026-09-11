"""Only ambiguous contextual cases can ask Bonsai, once, for a dictionary ID."""

import pytest

from test_lexical_context_selection import senses, Bonsai
from src.search_v2.lexical_context import BonsaiSenseSelector


class Lexicon:
    sha256 = "a" * 64

    def lookup_contextual(self, phrase):
        return senses()


class Scorer:
    sha256 = "b" * 64

    def __init__(self, values):
        self.values = values
        self.calls = 0

    def scores(self, *_):
        self.calls += 1
        return self.values


def test_confident_pair_selection_never_calls_bonsai():
    from src.search_v2.lexical_expansion import ContextualQueryExpander

    bonsai = Bonsai({"sense_id": "wn:club", "evidence": "ネジを締める"})
    expander = ContextualQueryExpander(
        Lexicon(), Scorer([0.97, 0.20]), resolver=BonsaiSenseSelector(bonsai, "c" * 64)
    )
    result = expander.propose("ネジを締めるドライバーが欲しい。", "ドライバー")
    assert result.profile_id == "dictionary-query-terms-v2"
    assert result.resolution_method == "cross_encoder"
    assert result.terms.original_en == "screwdriver"
    assert bonsai.calls == []


def test_ambiguous_pair_selection_uses_one_bonsai_choice_and_retains_provenance():
    from src.search_v2.lexical_expansion import ContextualQueryExpander

    bonsai = Bonsai({"sense_id": "wn:tool", "evidence_index": 0})
    expander = ContextualQueryExpander(
        Lexicon(), Scorer([0.6, 0.5]), resolver=BonsaiSenseSelector(bonsai, "c" * 64)
    )
    result = expander.propose("ネジを締めるドライバーが欲しい。", "ドライバー")
    assert result.resolution_method == "bonsai"
    assert result.selected_sense_id == "wn:tool"
    assert len(result.resolver_request_sha256) == len(result.resolver_response_sha256) == 64
    assert result.terms.original_en == "screwdriver"
    assert len(bonsai.calls) == 1
    assert type(result).model_validate_json(result.model_dump_json()) == result


def test_unknown_and_context_free_queries_do_not_invoke_either_model():
    from src.search_v2.lexical_expansion import ContextualQueryExpander

    scorer = Scorer([0.99, 0.01])
    bonsai = Bonsai({"sense_id": "wn:tool", "evidence": "ドライバー"})
    result = ContextualQueryExpander(
        Lexicon(), scorer, resolver=BonsaiSenseSelector(bonsai, "c" * 64)
    ).propose("ドライバーを探しています。", "ドライバー")
    assert result.status == "unavailable" and result.resolution_method == "abstained"
    assert scorer.calls == 0 and bonsai.calls == []


@pytest.mark.parametrize("choice", [None, "missing"])
def test_ambiguous_or_invalid_bonsai_response_keeps_original_query(choice):
    from src.search_v2.lexical_expansion import ContextualQueryExpander

    bonsai = Bonsai({"sense_id": choice, "evidence": None})
    result = ContextualQueryExpander(
        Lexicon(), Scorer([0.6, 0.5]), resolver=BonsaiSenseSelector(bonsai, "c" * 64)
    ).propose("ネジを締めるドライバーが欲しい。", "ドライバー")
    assert result.status == "unavailable" and result.selected_sense_id is None
    assert result.terms is None and len(bonsai.calls) == 1


def test_dictionary_only_result_cannot_claim_a_bonsai_response():
    from src.search_v2.lexical_expansion import ContextualQueryExpander
    import json

    result = ContextualQueryExpander(Lexicon(), Scorer([0.97, 0.01])).propose(
        "ネジを締めるドライバーが欲しい。", "ドライバー"
    )
    payload = json.loads(result.model_dump_json())
    payload.update(
        resolver_sha256="a" * 64,
        resolver_request_sha256="b" * 64,
        resolver_response_sha256="c" * 64,
    )
    with pytest.raises(ValueError):
        type(result).model_validate_json(json.dumps(payload))
