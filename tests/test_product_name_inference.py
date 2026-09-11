"""A dictionary miss generates a reviewable name without dictionary selection."""

import json
from types import SimpleNamespace

import pytest

from src.search_v2.lexical_context import BonsaiProductSelector
from src.search_v2.lexical_expansion import ContextualQueryExpander
from src.search_v2.product_phrase import ProductPhraseReview
from test_product_phrase import HUB, Scorer
from test_product_phrase_bonsai import Evaluator
from test_lexical_structure import structure


def generated(name="縦置きノートパソコンスタンド", english="vertical laptop stand"):
    return {"product_name_ja": name, "english": english, "evidence_index": 0 if name else None}


class EmptyLexicon:
    sha256 = "d" * 64

    def lookup_products(self, product, context):
        return ()

    def lookup_contextual(self, product):
        pytest.fail("Direct inference must not re-query the dictionary")


def prepare(source, target, reply, fragments=(), ignored=(), lexicon=None):
    evaluator = Evaluator(reply)
    expander = ContextualQueryExpander(
        lexicon or EmptyLexicon(),
        Scorer(),
        resolver=BonsaiProductSelector(evaluator, "a" * 64),
    )
    review = expander.prepare(source, structure(source, target, fragments, ignored))
    return review, evaluator


def test_unknown_explicit_name_is_inferred_without_extra_context_or_dictionary():
    source = "縦置きノートパソコンスタンドが欲しいです。"
    review, evaluator = prepare(
        source, "縦置きノートパソコンスタンド", generated(), ignored=("欲しいです",)
    )
    assert review.product_name == "縦置きノートパソコンスタンド"
    assert review.expansion.resolution_method == "bonsai_inference"
    assert review.expansion.selected_sense_id is None
    assert review.expansion.terms.original_en == "vertical laptop stand"
    assert len(evaluator.requests) == 1
    user = json.loads(evaluator.requests[0]["messages"][1]["content"])
    assert user == {
        "evidence_sources": [{"index": 0, "text": source}],
        "target": "縦置きノートパソコンスタンド",
    }
    schema = evaluator.requests[0]["response_format"]["schema"]
    assert "sense_id" not in json.dumps(schema)
    assert ProductPhraseReview.model_validate_json(review.model_dump_json()) == review


def test_inference_can_rephrase_target_while_preserving_original_conditions():
    source = "縦に立てるノートパソコンホルダー。3000円以下。"
    review, evaluator = prepare(
        source, "ノートパソコンホルダー", generated(), ("縦に立てる", "3000円以下")
    )
    assert review.product_name == "縦置きノートパソコンスタンド"
    assert review.context_quotes == ("縦に立てる", "3000円以下")
    assert review.structure.original_source == source
    assert review.expansion.terms.original_en is None
    assert review.expansion.terms.synonyms[0].en == "vertical laptop stand"
    assert review.expansion.resolver_request_sha256 and review.expansion.resolver_response_sha256
    assert len(evaluator.requests) == 1


@pytest.mark.parametrize(
    "reply",
    [
        generated(None, None),
        {**generated(), "sense_id": "invented"},
        {**generated(), "evidence_index": True},
        {**generated(), "evidence_index": 1},
        generated("ノートパソコンスタンド", "stand for 3 laptops"),
        generated(None, "stand"),
    ],
)
def test_invalid_or_abstained_inference_keeps_original_input(reply):
    source = "縦置きノートパソコンスタンド。"
    review, evaluator = prepare(source, "縦置きノートパソコンスタンド", reply)
    assert len(evaluator.requests) == 1
    assert review.product_name is None
    assert review.expansion.status == "unavailable"
    assert review.expansion.resolver_response_sha256
    assert review.structure.original_source == source


def test_nonempty_dictionary_does_not_use_direct_generation():
    lexicon = SimpleNamespace(sha256="d" * 64, lookup_products=lambda *_: (HUB,))
    review, evaluator = prepare("usbハブ。", "usbハブ", generated(), lexicon=lexicon)
    assert review.expansion.resolution_method == "dictionary"
    assert review.product_name == "usbハブ"
    assert not evaluator.requests


def test_dictionary_error_is_not_a_miss():
    class Broken(EmptyLexicon):
        def lookup_products(self, product, context):
            raise ValueError("Dictionary unavailable")

    review, evaluator = prepare("未知ホルダー。", "未知ホルダー", generated(), lexicon=Broken())
    assert review.expansion.status == "unavailable"
    assert not evaluator.requests


def test_generated_provenance_cannot_claim_dictionary_sense():
    review, _ = prepare(
        "縦置きノートパソコンスタンド。", "縦置きノートパソコンスタンド", generated()
    )
    raw = json.loads(review.model_dump_json())
    raw["expansion"]["selected_sense_id"] = HUB.sense_id
    with pytest.raises(ValueError):
        ProductPhraseReview.model_validate_json(json.dumps(raw))


def test_direct_generation_schema_matches_abstention_contract():
    from jsonschema import Draft202012Validator

    _, evaluator = prepare(
        "縦置きノートパソコンスタンド。", "縦置きノートパソコンスタンド", generated()
    )
    validator = Draft202012Validator(evaluator.requests[0]["response_format"]["schema"])
    assert validator.is_valid(generated())
    assert validator.is_valid(generated(english=None))
    assert validator.is_valid(generated(None, None))
    assert not validator.is_valid(generated(None, "stand"))
    assert not validator.is_valid({**generated(), "sense_id": "invented"})


def test_failed_generation_does_not_retry_or_erase_source():
    class BrokenEvaluator:
        calls = 0

        def evaluate(self, request):
            self.calls += 1
            raise ValueError("Transport failed")

    evaluator = BrokenEvaluator()
    expander = ContextualQueryExpander(
        EmptyLexicon(), Scorer(), resolver=BonsaiProductSelector(evaluator, "a" * 64)
    )
    source = "未知ホルダー。"
    review = expander.prepare(source, structure(source, "未知ホルダー", ()))
    assert evaluator.calls == 1
    assert review.expansion.status == "unavailable"
    assert review.expansion.resolver_request_sha256
    assert review.expansion.resolver_response_sha256 is None
    assert review.structure.original_source == source
