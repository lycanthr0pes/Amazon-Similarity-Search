"""Editing prepares new lexical evidence and source-bound browser fields."""

from types import SimpleNamespace
import unicodedata

import pytest
import test_candidate_search as fixtures
from test_browser_editing import InlineWorker, command
from src.search_v2.browser_candidate import BrowserCandidateRun, candidate_browser_steps
from src.search_v2.browser_search import BrowserSearch
from src.search_v2.candidate_flow import CandidateSearchFlow
from src.search_v2.condition_terms import LocalConditionExpander
from src.search_v2.bonsai_query_terms import QueryExpansion, QueryTerms, TranslatedTerm
from src.search_v2.candidate_search import candidate_source_sha256


def test_product_and_conditions_are_reexpanded_after_each_edit():
    product_calls, condition_calls, translations, plans = [], [], [], []

    class Translator:
        sha256 = "e" * 64

        def translate(self, phrases):
            translations.append(phrases)
            return tuple("dishwasher safe" if "食洗機" in p else "microwave safe" for p in phrases)

    class Lexical:
        def propose(self, source, product):
            product_calls.append((source, product))
            english = {"マグカップ": "mug", "タンブラー": "tumbler"}[product]
            return QueryExpansion(
                profile_id="dictionary-query-terms-v1",
                status="ready",
                source_sha256=candidate_source_sha256(source),
                request_sha256="a" * 64,
                response_sha256="b" * 64,
                dictionary_sha256="c" * 64,
                sense_model_sha256="d" * 64,
                selected_sense_id="fixture:product",
                terms=QueryTerms(
                    original_en=english, synonyms=(TranslatedTerm(ja=product, en=english),)
                ),
            )

    class Conditions(LocalConditionExpander):
        def prepare(self, source, conditions, visual):
            condition_calls.append(source)
            return super().prepare(source, conditions, visual)

    def factory(source, attempt):
        flow = CandidateSearchFlow(
            source,
            owner_id="owner-1",
            session_id=f"edit-{attempt}",
            postal_code="100-0001",
            policy=fixtures.flow.backend_policy(),
            usage_ledger=fixtures.flow.usage_ledger(),
            approval_repository=None,
            history_repository=None,
            image_transport=None,
            account_id=None,
            api_token=None,
            now=lambda: fixtures.flow.NOW,
            allow_image_free=True,
            visual_extractor=None,
            plan_lifetime=None,
            lexical_expander=Lexical(),
            condition_expander=Conditions(translator=Translator()),
        )
        plans.append(flow.plan)
        yield from candidate_browser_steps(
            flow,
            owner="owner-1",
            images=None,
            products=None,
            history=None,
            now=lambda: fixtures.flow.NOW,
            proxy=None,
            assets=None,
            encoder=None,
        )

    run = BrowserCandidateRun(factory=factory)
    controller = BrowserSearch(run.execute, InlineWorker(), initial={"editable": True})
    sources = [
        "マグカップ。電子レンジ対応。取っ手がなくてもよい。",
        "タンブラー。電子レンジ対応。取っ手がなくてもよい。",
        "タンブラー。食洗機対応。取っ手がなくてもよい。",
    ]
    for i, source in enumerate(sources):
        state = controller.submit(command("start" if i == 0 else "revise", i, source=source))
        assert state["stage"] == "query"
        assert state["productName"] == source.split("。")[0]
        assert state["conditionText"] == "。".join(source.split("。")[1:])
    assert [call[0] for call in product_calls] == condition_calls == sources
    assert plans[0].title_comparison.product_name_en == "mug"
    assert plans[1].title_comparison.product_name_en == "tumbler"
    assert len({p.source_sha256 for p in plans}) == 3
    assert plans[0].condition_terms != plans[2].condition_terms
    assert "電子レンジ" not in str([c.source_ja for c in plans[2].condition_terms.conditions])
    assert state["canRevise"] is False
    assert translations
    assert any("microwave safe" in c.terms_en for c in plans[0].condition_terms.conditions)
    assert any("dishwasher safe" in c.terms_en for c in plans[2].condition_terms.conditions)
    assert not any("microwave safe" in c.terms_en for c in plans[2].condition_terms.conditions)
    run.close()


@pytest.mark.parametrize(
    "source,product,clauses",
    [
        (
            "３０００円以下のマグカップを探しています。取っ手がなくてもよい。",
            "マグカップ",
            ("3000円以下", "取っ手がなくてもよい"),
        ),
        ("ＵＳＢハブ。ＵＳＢ非対応。", "usbハブ", ("usb非対応",)),
    ],
)
def test_editor_keeps_original_condition_quotes_with_inline_product(source, product, clauses):
    from test_lexical_structure import structure

    normalized = unicodedata.normalize("NFKC", source).casefold()
    ignored = ("探しています",) if "探しています" in normalized else ()
    parsed = structure(normalized, product, clauses, ignored)
    flow = CandidateSearchFlow(
        source,
        owner_id="owner-1",
        session_id="inline-edit",
        postal_code="100-0001",
        policy=fixtures.flow.backend_policy(),
        usage_ledger=fixtures.flow.usage_ledger(),
        approval_repository=None,
        history_repository=None,
        image_transport=None,
        account_id=None,
        api_token=None,
        now=lambda: fixtures.flow.NOW,
        allow_image_free=True,
        visual_extractor=None,
        plan_lifetime=None,
        source_parser=SimpleNamespace(analyze=lambda _: parsed),
    )
    steps = candidate_browser_steps(
        flow,
        owner="owner-1",
        images=None,
        products=None,
        history=None,
        now=lambda: fixtures.flow.NOW,
        proxy=None,
        assets=None,
        encoder=None,
    )
    state = next(steps)
    assert unicodedata.normalize("NFKC", state["productName"]).casefold() == product
    assert (
        unicodedata.normalize("NFKC", state["conditionText"]).casefold()
        == "。".join(clauses) + "。"
    )
    assert "探しています" not in state["conditionText"]
    steps.close()


def test_edit_projection_retains_explicit_brand_and_model():
    flow = CandidateSearchFlow(
        "マグカップ。ブランド:合成。型番:ABC-123。3000円以下。",
        owner_id="owner-1",
        session_id="metadata-edit",
        postal_code="100-0001",
        policy=fixtures.flow.backend_policy(),
        usage_ledger=fixtures.flow.usage_ledger(),
        approval_repository=None,
        history_repository=None,
        image_transport=None,
        account_id=None,
        api_token=None,
        now=lambda: fixtures.flow.NOW,
        allow_image_free=True,
        visual_extractor=None,
        plan_lifetime=None,
    )
    steps = candidate_browser_steps(
        flow,
        owner="owner-1",
        images=None,
        products=None,
        history=None,
        now=lambda: fixtures.flow.NOW,
        proxy=None,
        assets=None,
        encoder=None,
    )
    state = next(steps)
    assert state["productName"] == "マグカップ"
    assert "ブランド:合成" in state["conditionText"]
    assert "型番:ABC-123" in state["conditionText"]
    assert "3000円以下" in state["conditionText"]
    steps.close()
