"""Product naming uses context without changing the requested object or facts."""

import json
from dataclasses import replace

import pytest

from src.search_v2.lexical_dictionary import SqliteLexicon, build_lexicon
from src.search_v2.lexical_selection import LexicalSense
from src.search_v2.lexical_expansion import ContextualQueryExpander
from src.search_v2.lexical_context import has_context
from src.search_v2.candidate_search import prepare_candidate_search
from src.search_v2.candidate_diagnostics import CandidatePreparationError
from test_lexical_structure import structure
from test_lexical_connection import NOW, PROFILE


HUB = LexicalSense("jmdict:usb", "jmdict", ("USBハブ",), ("USB hub",), "USB hub")
WHEEL = LexicalSense("wordnet:wheel", "wordnet", ("ハブ",), ("hub",), "wheel centre")
CASE = LexicalSense("jmdict:case", "jmdict", ("ケース",), ("case",), "container")


class Scorer:
    sha256 = "c" * 64

    def scores(self, source, senses):
        return [0.95 if s.sense_id == HUB.sense_id else 0.01 for s in senses]


@pytest.fixture
def lexicon(tmp_path):
    path = tmp_path / "lexicon.sqlite3"
    build_lexicon(path, [HUB, WHEEL, CASE], {})
    with SqliteLexicon(path) as lexicon:
        yield lexicon


def test_context_retrieves_compound_without_substituting_the_target(lexicon):
    assert HUB in lexicon.lookup_products("ハブ", "USB端子を増やす")
    assert HUB not in lexicon.lookup_products("ケース", "USBハブを入れる")
    assert CASE in lexicon.lookup_products("ケース", "USBハブを入れる")


@pytest.mark.parametrize(
    "source", ["クラブが欲しいです。", "クラブを買いたいです。", "クラブを探していました。"]
)
def test_polite_request_inflections_are_not_meaningful_context(source):
    assert not has_context(source, "クラブ")


def test_compound_proposal_keeps_the_original_structure_and_price(lexicon):
    source = "usb端子を増やすハブ。3000円以下。"
    parsed = structure(source, "ハブ", ("usb端子を増やす", "3000円以下"))
    review = ContextualQueryExpander(lexicon, Scorer()).prepare(source, parsed)
    assert review.product_name == "usbハブ"
    assert review.structure == replace(parsed, original_source=source)
    assert review.expansion.profile_id == "product-query-terms-v1"
    assert review.expansion.selected_sense_id == HUB.sense_id
    assert review.expansion.terms.original_en == "usb hub"
    restored = type(review).model_validate_json(review.model_dump_json())
    assert restored == review
    raw = json.loads(review.model_dump_json())
    raw["source_sha256"] = "a" * 64
    with pytest.raises(ValueError):
        type(review).model_validate_json(json.dumps(raw))


def test_single_dictionary_sense_does_not_bypass_context_fit(lexicon):
    class Weak(Scorer):
        def scores(self, source, senses):
            return [0.01] * len(senses)

    source = "海底で育てるハブ。"
    parsed = structure(source, "ハブ", ("海底で育てる",))
    review = ContextualQueryExpander(lexicon, Weak()).prepare(source, parsed)
    assert review.product_name is None
    assert review.expansion.status == "unavailable"


def test_product_review_is_available_before_unresolved_conditions_stop_query(lexicon):
    source = "usb端子を増やすハブ。3000円以下。"
    parsed = structure(source, "ハブ", ("usb端子を増やす", "3000円以下"))

    class Parser:
        def analyze(self, _):
            return parsed

    with pytest.raises(CandidatePreparationError) as caught:
        prepare_candidate_search(
            source,
            owner_id="owner",
            session_id="session",
            postal_code="100-0001",
            normalization_profile=PROFILE,
            now=NOW,
            source_parser=Parser(),
            lexical_expander=ContextualQueryExpander(lexicon, Scorer()),
        )
    assert caught.value.product_review.product_name == "usbハブ"
    assert "3000円以下" in caught.value.product_review.context_quotes
    assert source not in str(caught.value)


def test_price_alone_does_not_trigger_semantic_inference(lexicon):
    class NoInference(Scorer):
        def scores(self, *_):
            pytest.fail("A price does not disambiguate the product name")

    source = "usbハブ。3000円以下。"
    parsed = structure(source, "usbハブ", ("3000円以下",))
    review = ContextualQueryExpander(lexicon, NoInference()).prepare(source, parsed)
    assert review.product_name == "usbハブ"
    assert review.expansion.resolution_method == "dictionary"


def test_ready_plan_keeps_product_review_and_price(lexicon):
    from types import SimpleNamespace
    from src.search_v2.candidate_search import CandidatePlan

    source = "usbハブ。3000円以下。"
    parsed = structure(source, "usbハブ", ("3000円以下",))
    service = prepare_candidate_search(
        source,
        owner_id="owner",
        session_id="session",
        postal_code="100-0001",
        normalization_profile=PROFILE,
        now=NOW,
        source_parser=SimpleNamespace(analyze=lambda _: parsed),
        lexical_expander=ContextualQueryExpander(lexicon, Scorer()),
    )
    assert service.plan.product_review.product_name == "usbハブ"
    assert service.plan.query_expansion.profile_id == "product-query-terms-v1"
    assert service._queries.retrieval_intent.price.max_jpy == 3000
    assert CandidatePlan.model_validate_json(service.plan.model_dump_json()) == service.plan
    raw = json.loads(service.plan.model_dump_json())
    raw["product_review"] = None
    with pytest.raises(ValueError):
        CandidatePlan.model_validate_json(json.dumps(raw))


def test_negated_product_cannot_be_selected_by_a_high_dictionary_score(lexicon):
    from src.search_v2.lexical_structure import ProductStructure, TextSpan

    source = "usbハブ以外のハブ。"
    start = source.rindex("ハブ")
    parsed = ProductStructure(
        source, TextSpan(start, start + 2), (TextSpan(0, start - 1),), (), "fixture"
    )
    review = ContextualQueryExpander(lexicon, Scorer()).prepare(source, parsed)
    assert review.product_name is None


def test_visual_failure_also_returns_the_earlier_product_review(lexicon):
    from types import SimpleNamespace

    source = "usb端子を増やすハブ。"
    parsed = structure(source, "ハブ", ("usb端子を増やす",))
    with pytest.raises(CandidatePreparationError) as caught:
        prepare_candidate_search(
            source,
            owner_id="owner",
            session_id="session",
            postal_code="100-0001",
            normalization_profile=PROFILE,
            now=NOW,
            source_parser=SimpleNamespace(analyze=lambda _: parsed),
            lexical_expander=ContextualQueryExpander(lexicon, Scorer()),
            visual_extractor=SimpleNamespace(evaluate=lambda _: b"{}"),
        )
    assert caught.value.product_review.product_name == "usbハブ"
