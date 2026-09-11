"""Dictionary candidates are bounded evidence, never model-generated strings."""

import math

import pytest

from src.search_v2.lexical_selection import LexicalSense, select_sense, terms_from_sense


def sense(key, gloss, forms=("マウス",)):
    return LexicalSense(key, "fixture", forms, (gloss,), gloss)


def test_context_selects_only_an_existing_sense():
    values = (sense("animal", "mouse"), sense("device", "computer mouse"))
    result = select_sense(values, [0.78, 0.91], minimum=0.75, margin=0.04)
    assert result.sense == values[1]
    assert result.status == "selected"


@pytest.mark.parametrize("scores", [[0.86, 0.85], [0.70, 0.60]])
def test_weak_or_tied_evidence_abstains(scores):
    result = select_sense((sense("a", "mouse"), sense("b", "computer mouse")), scores)
    assert result.sense is None
    assert result.status == "ambiguous"


@pytest.mark.parametrize("scores", [[math.nan, 0.9], [math.inf, 0.9], [0.9], [1.1, 0.9]])
def test_invalid_scores_are_not_confidence(scores):
    with pytest.raises(ValueError):
        select_sense((sense("a", "mouse"), sense("b", "computer mouse")), scores)


def test_no_dictionary_entry_means_no_generated_translation():
    assert select_sense((), []).status == "not_found"


def test_translation_and_variants_come_from_one_sense():
    value = sense("case", "business card case", ("名刺入れ", "名刺ケース"))
    terms = terms_from_sense("名刺入れ", value)
    assert terms.original_en == "business card case"
    assert [(s.ja, s.en) for s in terms.synonyms] == [("名刺ケース", "business card case")]


def test_dictionary_explanation_is_not_a_search_term():
    value = sense("unsafe", "a case used for cards (usually business cards)")
    assert terms_from_sense("マウス", value).original_en is None


def test_multiword_product_keeps_full_phrase():
    value = sense("case", "business card case", ("名刺入れ",))
    assert terms_from_sense("名刺 入れ", value).synonyms == ()


def test_leading_dictionary_qualifier_is_part_of_the_translation():
    value = sense("case", "(business) card case", ("名刺入れ",))
    assert terms_from_sense("名刺入れ", value).original_en == "business card case"
