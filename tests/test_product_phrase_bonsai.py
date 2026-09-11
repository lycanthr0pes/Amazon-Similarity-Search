"""Unknown names are reviewable proposals, not invented dictionary entries."""

import json
from types import SimpleNamespace

import pytest

from src.search_v2.lexical_context import BonsaiProductSelector
from src.search_v2.lexical_expansion import ContextualQueryExpander
from test_product_phrase import Scorer, HUB, WHEEL
from test_lexical_context_selection import envelope
from test_lexical_structure import structure


class Evaluator:
    def __init__(self, payload):
        self.payload, self.requests = payload, []

    def evaluate(self, request):
        self.requests.append(json.loads(request))
        return envelope(self.payload)


def payload(name=None, english=None, sense_id=None):
    return {
        "sense_id": sense_id,
        "product_name_ja": name,
        "english": english,
        "evidence_index": 0 if name or sense_id else None,
    }


def test_generated_compound_is_requeried_in_dictionary_before_translation():
    evaluator = Evaluator(payload("USBハブ", "invented translation"))
    calls = []

    class Lexicon:
        sha256 = "d" * 64

        def lookup_products(self, product, context):
            return (WHEEL,)

        def lookup_contextual(self, product):
            calls.append(product)
            return (HUB,) if product == "usbハブ" else ()

    source = "usb端子を増やすハブ。"
    review = ContextualQueryExpander(
        Lexicon(), Scorer(), resolver=BonsaiProductSelector(evaluator, "a" * 64)
    ).prepare(source, structure(source, "ハブ", ("usb端子を増やす",)))
    assert calls == ["usbハブ"]
    assert review.expansion.selected_sense_id == HUB.sense_id
    assert review.expansion.terms.original_en == "usb hub"
    assert review.expansion.resolution_method == "bonsai"
    assert len(evaluator.requests) == 1


def test_unlisted_proposal_has_no_dictionary_id_and_one_translation():
    evaluator = Evaluator(
        {
            "product_name_ja": "磁気固定ケース",
            "english": "magnetic mounting case",
            "evidence_index": 0,
        }
    )
    lexicon = SimpleNamespace(
        sha256="d" * 64, lookup_products=lambda *_: (), lookup_contextual=lambda _: ()
    )
    source = "磁石で固定するケース。"
    review = ContextualQueryExpander(
        lexicon, Scorer(), resolver=BonsaiProductSelector(evaluator, "a" * 64)
    ).prepare(source, structure(source, "ケース", ("磁石で固定する",)))
    assert review.product_name == "磁気固定ケース"
    assert review.expansion.selected_sense_id is None
    assert review.expansion.resolution_method == "bonsai_inference"
    assert review.expansion.terms.synonyms[0].en == "magnetic mounting case"
    assert review.context_quotes == ("磁石で固定する",)


@pytest.mark.parametrize(
    "reply",
    [
        payload("USBハブ", "usb hub"),
        payload(sense_id="not-in-candidates"),
        {**payload("磁気固定ケース"), "extra": "ignored"},
        {**payload("磁気固定ケース"), "evidence_index": True},
    ],
)
def test_generated_names_cannot_replace_container_target_or_invent_ids(reply):
    evaluator = Evaluator(reply)
    resolver = BonsaiProductSelector(evaluator, "a" * 64)
    result = resolver.suggest("USBハブを入れるケース。", "ケース", ())
    assert result.sense is None and result.product_name is None


def test_no_context_is_not_sent_to_generative_model():
    evaluator = Evaluator(payload("ゴルフクラブ", "golf club"))
    result = BonsaiProductSelector(evaluator, "a" * 64).suggest(
        "クラブが欲しいです。", "クラブ", ()
    )
    assert result.product_name is None
    assert not evaluator.requests


def test_generation_schema_prevents_mixing_dictionary_and_generated_fields():
    from jsonschema import Draft202012Validator

    evaluator = Evaluator(payload(sense_id=WHEEL.sense_id))
    BonsaiProductSelector(evaluator, "a" * 64).suggest("自転車に使うハブ。", "ハブ", (WHEEL,))
    schema = evaluator.requests[0]["response_format"]["schema"]
    validator = Draft202012Validator(schema)
    assert validator.is_valid(payload(sense_id=WHEEL.sense_id))
    assert validator.is_valid(payload("自転車ハブ", "bicycle hub"))
    assert validator.is_valid(payload())
    assert not validator.is_valid(payload("ハブ", "hub", sense_id=WHEEL.sense_id))
