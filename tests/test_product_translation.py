"""Dictionary misses use reviewable MT translations without changing product facts."""

import json
from types import SimpleNamespace

import pytest

from src.search_v2.lexical_context import BonsaiProductSelector
from src.search_v2.lexical_expansion import ContextualQueryExpander
from src.search_v2.product_phrase import ProductPhraseReview
from test_lexical_structure import structure
from test_product_name_inference import EmptyLexicon, generated
from test_product_phrase import HUB, Scorer
from test_product_phrase_bonsai import Evaluator


class Translator:
    sha256 = "f" * 64

    def __init__(self, outputs=("laptop holder", "vertical laptop stand")):
        self.calls = []
        self.outputs = outputs

    def translate(self, phrases):
        self.calls.append(phrases)
        if isinstance(self.outputs, Exception):
            raise self.outputs
        return self.outputs


def prepare(translator, *, target="ノートパソコンホルダー", lexicon=None):
    evaluator = Evaluator(generated(english=None))
    expander = ContextualQueryExpander(
        lexicon or EmptyLexicon(), Scorer(), translator=translator
    ).with_resolver(BonsaiProductSelector(evaluator, "a" * 64))
    source = target + "。"
    review = expander.prepare(source, structure(source, target, ()))
    return review, evaluator


def test_missing_phrase_gets_one_translation_per_original_and_proposal():
    translator = Translator()
    review, evaluator = prepare(translator)
    terms = review.expansion.terms
    assert translator.calls == [("ノートパソコンホルダー", "縦置きノートパソコンスタンド")]
    assert terms.original_en == "laptop holder"
    assert [(t.ja, t.en) for t in terms.synonyms] == [
        ("縦置きノートパソコンスタンド", "vertical laptop stand")
    ]
    assert review.expansion.translation.status == "ready"
    assert review.expansion.translation.model_sha256 == translator.sha256
    assert review.expansion.translation.request_sha256
    assert review.expansion.translation.response_sha256
    schema = evaluator.requests[0]["response_format"]["schema"]
    assert all(branch["properties"]["english"] == {"type": "null"} for branch in schema["oneOf"])
    assert ProductPhraseReview.model_validate_json(review.model_dump_json()) == review


def test_identical_original_and_proposal_translate_once():
    translator = Translator(("vertical laptop stand",))
    review, _ = prepare(translator, target="縦置きノートパソコンスタンド")
    assert translator.calls == [("縦置きノートパソコンスタンド",)]
    assert review.expansion.terms.original_en == review.expansion.terms.synonyms[0].en


@pytest.mark.parametrize(
    "failure",
    [
        RuntimeError("private failure"),
        ("wrong count",),
        (None, None),
        ("日本語", "stand"),
        ("holder 999", "stand"),
    ],
)
def test_translation_failure_keeps_japanese_without_bonsai_english_fallback(failure):
    translator = Translator(failure)
    review, _ = prepare(translator)
    assert review.product_name == "縦置きノートパソコンスタンド"
    assert review.expansion.status == "ready"
    assert review.expansion.terms.original_en is None
    assert review.expansion.terms.synonyms[0].en is None
    assert review.expansion.translation.status == "unavailable"
    assert len(translator.calls) == 1
    assert "private failure" not in review.model_dump_json()


@pytest.mark.parametrize("broken", [False, True])
def test_dictionary_hit_or_error_never_calls_mt(broken):
    def lookup(*_):
        if broken:
            raise ValueError("dictionary failure")
        return (HUB,)

    translator = Translator()
    review, evaluator = prepare(
        translator,
        target="usbハブ",
        lexicon=SimpleNamespace(sha256="d" * 64, lookup_products=lookup),
    )
    assert not translator.calls and not evaluator.requests
    assert review.expansion.translation is None
    assert review.expansion.status == ("unavailable" if broken else "ready")


def test_translation_identity_separates_cache_and_old_json_still_loads():
    first, _ = prepare(Translator())
    different = Translator()
    different.sha256 = "e" * 64
    second, _ = prepare(different)
    assert first.expansion.request_sha256 != second.expansion.request_sha256
    from test_product_name_inference import prepare as old_prepare

    old, _ = old_prepare(
        "縦置きノートパソコンスタンド。", "縦置きノートパソコンスタンド", generated()
    )
    raw = json.loads(old.model_dump_json())
    raw["expansion"].pop("translation", None)
    assert ProductPhraseReview.model_validate_json(json.dumps(raw)) == old


def test_bonsai_abstention_does_not_trigger_translation():
    translator = Translator()
    expander = ContextualQueryExpander(
        EmptyLexicon(),
        Scorer(),
        translator=translator,
        resolver=BonsaiProductSelector(Evaluator(generated(None, None)), "a" * 64),
    )
    source = "未知ホルダー。"
    review = expander.prepare(source, structure(source, "未知ホルダー", ()))
    assert review.product_name is None and not translator.calls
    assert review.expansion.translation is None


def test_unavailable_translation_cannot_restore_bonsai_english():
    review, _ = prepare(Translator(RuntimeError()))
    raw = json.loads(review.model_dump_json())
    raw["expansion"]["terms"]["original_en"] = "invented fallback"
    with pytest.raises(ValueError):
        ProductPhraseReview.model_validate_json(json.dumps(raw))
