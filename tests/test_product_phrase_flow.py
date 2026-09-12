"""Product review reaches query confirmation and the existing fixture search flow."""

import json
from types import SimpleNamespace

import pytest

from src.search_v2.lexical_context import BonsaiProductSelector
from src.search_v2.lexical_expansion import ContextualQueryExpander
from src.search_v2.lexical_selection import LexicalSense
from test_lexical_structure import structure
from test_product_phrase_bonsai import Evaluator
import test_candidate_search_live_e2e as live


@pytest.mark.parametrize("dictionary_hit", [True, False])
@pytest.mark.parametrize("with_translation", [True, False])
def test_product_preparation_precedes_visuals_and_reaches_confirmation_and_history(
    tmp_path, monkeypatch, dictionary_hit, with_translation
):
    module, config, services, events, clips = live.setup_run(tmp_path, monkeypatch)
    visual = services.bonsai_session().__enter__()
    source = module.SYNTHETIC_INPUT
    parsed = structure(source, "マグカップ", ("丸みのある形", "3000円以下"))
    mug = LexicalSense("jmdict:mug", "jmdict", ("マグカップ",), ("mug",), "mug")

    class Lexicon:
        sha256 = "d" * 64

        def lookup_products(self, product, context):
            assert visual.calls == 0
            return (mug,) if dictionary_hit else ()

        def lookup_contextual(self, product):
            assert product != "マグカップ", "Product inference must not re-query the dictionary"
            return ()  # Independent condition preparation follows product inference.

    scorer = SimpleNamespace(sha256="c" * 64, scores=lambda source, senses: [0.95])
    evaluator = Evaluator(
        {
            "product_name_ja": "マグカップ",
            "english": None if with_translation else "mug",
            "evidence_index": 0,
        }
    )
    from test_product_translation import Translator

    translator = Translator(("coffee mug",)) if with_translation else None
    expander = ContextualQueryExpander(
        Lexicon(),
        scorer,
        resolver=BonsaiProductSelector(evaluator, "a" * 64),
        translator=translator,
    )
    expected_query = "coffee mug" if with_translation and not dictionary_hit else "mug"

    def select(review):
        assert review["product_review"]["product_name"] == "マグカップ"
        return next(i for i, q in enumerate(review["queries"]) if q["value"] == expected_query)

    result = module.run_candidate_e2e(
        config,
        services,
        select_query=select,
        lexical_expander=expander,
        source_parser=SimpleNamespace(analyze=lambda _: parsed),
        image_score_mode="appearance",
    )
    assert result["status"] == "succeeded"
    assert result["bonsai_calls"] == 1
    assert result["outscraper_tasks"] == 1
    assert result["history_images_verified"] == 2
    assert clips == [2, 4]
    saved = json.loads((config.output_dir / "plan.json").read_bytes())
    assert saved["query_expansion"]["profile_id"] == "product-query-terms-v1"
    assert saved["product_review"]["structure"]["original_source"] == source
    assert saved["request"]["queries"][0]["value"] == expected_query
    if translator:
        product_calls = [batch for batch in translator.calls if "マグカップ" in batch]
        assert product_calls == ([] if dictionary_hit else [("マグカップ",)])
        assert any("丸みのある形" in batch for batch in translator.calls)
    assert saved["condition_terms"]["profile_id"] == "condition-terms-v1"
    assert len(evaluator.requests) == (0 if dictionary_hit else 1)
    assert saved["query_expansion"]["resolution_method"] == (
        "cross_encoder" if dictionary_hit else "bonsai_inference"
    )
