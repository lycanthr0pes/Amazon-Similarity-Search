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


def prepare_proposal(translator, *, name="usbハブ", english=None, found=()):
    from test_product_phrase import WHEEL
    from test_product_phrase_bonsai import payload

    evaluator = Evaluator(payload(name, english))
    lexicon = SimpleNamespace(
        sha256="d" * 64,
        lookup_products=lambda *_: (WHEEL,),
        lookup_contextual=lambda _: found,
    )
    source = "usb端子を増やすハブ。"
    review = ContextualQueryExpander(
        lexicon,
        Scorer(),
        translator=translator,
        resolver=BonsaiProductSelector(evaluator, "a" * 64),
    ).prepare(source, structure(source, "ハブ", ("usb端子を増やす",)))
    return review, evaluator


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


def test_unlisted_proposal_uses_local_translation_and_name_only_bonsai_schema():
    from jsonschema import Draft202012Validator
    from test_product_phrase_bonsai import payload

    translator = Translator(("hub", "usb hub"))
    review, evaluator = prepare_proposal(translator)
    assert translator.calls == [("ハブ", "usbハブ")]
    assert review.expansion.resolution_method == "bonsai_proposal"
    assert review.expansion.selected_sense_id is None
    assert review.expansion.terms.original_en == "hub"
    assert review.expansion.terms.synonyms[0].en == "usb hub"
    assert review.expansion.translation.status == "ready"
    schema = evaluator.requests[0]["response_format"]["schema"]
    assert all(b["properties"]["english"] == {"type": "null"} for b in schema["oneOf"])
    validator = Draft202012Validator(schema)
    assert validator.is_valid(payload("usbハブ"))
    assert not validator.is_valid(payload("usbハブ", "invented translation"))
    assert ProductPhraseReview.model_validate_json(review.model_dump_json()) == review


def test_unlisted_proposal_translation_failure_preserves_japanese_and_rejects_fallback():
    translator = Translator(RuntimeError("private fixture"))
    review, _ = prepare_proposal(translator)
    assert translator.calls == [("ハブ", "usbハブ")]
    assert review.product_name == "usbハブ"
    assert review.expansion.terms.original_en is None
    assert review.expansion.terms.synonyms[0].en is None
    assert review.expansion.translation.status == "unavailable"
    raw = json.loads(review.model_dump_json())
    raw["expansion"]["terms"]["synonyms"][0]["en"] = "invented fallback"
    with pytest.raises(ValueError):
        ProductPhraseReview.model_validate_json(json.dumps(raw))


def test_name_only_proposal_rejects_bonsai_english_before_translation():
    translator = Translator(("hub", "usb hub"))
    review, _ = prepare_proposal(translator, english="invented translation")
    assert review.product_name is None
    assert review.expansion.status == "unavailable"
    assert not translator.calls


def test_proposed_identical_name_is_translated_once():
    translator = Translator(("hub",))
    review, _ = prepare_proposal(translator, name="ハブ")
    assert translator.calls == [("ハブ",)]
    assert review.expansion.terms.original_en == review.expansion.terms.synonyms[0].en == "hub"


def test_proposed_name_found_in_dictionary_keeps_dictionary_english():
    translator = Translator()
    review, _ = prepare_proposal(translator, found=(HUB,))
    assert not translator.calls
    assert review.expansion.selected_sense_id == HUB.sense_id
    assert review.expansion.terms.original_en == "usb hub"
    assert review.expansion.translation is None


def test_local_proposal_translation_reaches_query_selection_and_history(tmp_path, monkeypatch):
    import test_candidate_search_live_e2e as live
    from test_product_phrase import WHEEL
    from test_product_phrase_bonsai import payload

    module, config, services, _, _ = live.setup_run(tmp_path, monkeypatch)
    source = module.SYNTHETIC_INPUT
    evaluator = Evaluator(payload("丸形マグカップ"))
    translator = Translator(("mug", "round mug"))
    expander = ContextualQueryExpander(
        SimpleNamespace(
            sha256="d" * 64, lookup_products=lambda *_: (WHEEL,), lookup_contextual=lambda _: ()
        ),
        Scorer(),
        translator=translator,
        resolver=BonsaiProductSelector(evaluator, "a" * 64),
    )

    def select(review):
        assert review["query_terms"]["synonyms"] == [{"ja": "丸形マグカップ", "en": "round mug"}]
        return next(i for i, q in enumerate(review["queries"]) if q["value"] == "round mug")

    result = module.run_candidate_e2e(
        config,
        services,
        select_query=select,
        lexical_expander=expander,
        source_parser=SimpleNamespace(
            analyze=lambda _: structure(source, "マグカップ", ("丸みのある形", "3000円以下"))
        ),
        image_score_mode="appearance",
    )
    assert result["status"] == "succeeded" and result["history_images_verified"] == 2
    assert len(evaluator.requests) == 1
    assert translator.calls[0] == ("マグカップ", "丸形マグカップ")
    saved = json.loads((config.output_dir / "plan.json").read_bytes())
    assert saved["request"]["queries"][0]["value"] == "round mug"
    assert saved["query_expansion"]["resolution_method"] == "bonsai_proposal"
    assert saved["query_expansion"]["translation"]["provider"] == "opus-mt-ja-en-int8-v1"


def test_proposal_without_local_translator_preserves_old_english_and_json():
    review, _ = prepare_proposal(None, english="usb hub")
    assert review.expansion.translation is None
    assert review.expansion.terms.synonyms[0].en == "usb hub"
    assert ProductPhraseReview.model_validate_json(review.model_dump_json()) == review
