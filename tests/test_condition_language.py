"""Natural preference/exclusion scope is shared by query and visual preparation."""

import json
import pytest

from src.search_v2.candidate_queries import build_candidate_queries
from src.search_v2.bonsai_visual_conditions import build_visual_request


@pytest.mark.parametrize(
    "phrase,strength",
    [
        ("できれば幅100mm以下", "preferred"),
        ("幅100mm以下が望ましいです", "preferred"),
        ("USB対応があるとよい", "preferred"),
        ("USB対応は不要", "excluded"),
        ("できればUSB対応は避けたい", "excluded"),
        ("必ず幅100mm以下", "required"),
    ],
)
def test_general_specifications(phrase, strength):
    queries = build_candidate_queries("スキャナー。" + phrase + "。")
    assert len(queries.facts) == 1
    assert queries.facts[0].strength == strength
    assert queries.facts[0].quote == phrase.casefold()


def test_neutral_is_not_a_query_or_visual_condition():
    source = "マグカップ。色にはこだわらない。赤でも構わない。取っ手がなくてもよい。3000円以下。"
    queries = build_candidate_queries(source)
    assert queries.retrieval_intent.product_name_ja == "マグカップ"
    assert queries.facts == ()
    request = json.loads(build_visual_request(source))
    assert json.loads(request["messages"][1]["content"])["clauses"] == []


def test_color_scope_and_boolean_value_are_preserved():
    queries = build_candidate_queries("スキャナー。できれば赤、容量300ml以上。USB非対応。")
    facts = queries.facts
    assert next(f for f in facts if f.key == "appearance.color").strength == "preferred"
    assert next(f for f in facts if f.label == "容量").strength == "required"
    usb = next(f for f in facts if f.label == "usb対応")
    assert usb.strength == "required" and usb.target["value"] is False


@pytest.mark.parametrize(
    "phrase,target,strength",
    [
        ("できれば赤", "赤", "preferred"),
        ("なるべく軽い", "軽い", "preferred"),
        ("丸い形だとうれしい", "丸い形", "preferred"),
        ("白を希望します", "白", "preferred"),
        ("赤は避けたい", "赤", "excluded"),
        ("取っ手はいらない", "取っ手", "excluded"),
        ("光沢は不要", "光沢", "excluded"),
        ("赤以外", "赤", "excluded"),
        ("取っ手なし", "取っ手", "excluded"),
        ("取っ手がなくてもよい", "取っ手", "neutral"),
        ("色にはこだわらない", "色", "neutral"),
        ("赤でも構わない", "赤", "neutral"),
        ("できれば赤は避けたい", "赤", "excluded"),
        ("ノンフライヤー", "ノンフライヤー", "required"),
    ],
)
def test_expression_families(phrase, target, strength):
    from src.search_v2.condition_language import interpret_clause

    value = interpret_clause(phrase, start=7)
    assert (value.quote, value.target, value.strength) == (phrase, target, strength)
    assert value.start == 7 and value.end == 7 + len(phrase)
    assert value.reason


@pytest.mark.parametrize(
    "source", ["赤を避けたくない", "赤が不要ではない", "できれば必ず赤", "赤は必須。赤は除外。"]
)
def test_ambiguous_language_requires_source_correction(source):
    from src.search_v2.condition_language import analyze_conditions, ConditionLanguageError

    with pytest.raises(ConditionLanguageError) as caught:
        analyze_conditions(source)
    assert caught.value.issues
    assert source not in str(caught.value)


@pytest.mark.parametrize(
    "phrase,strength,value",
    [
        ("取っ手不要", "excluded", True),
        ("USB非対応", "required", False),
        ("USB対応は不要", "excluded", True),
    ],
)
def test_exclusion_targets_presence_and_preserves_negative_attribute(phrase, strength, value):
    fact = build_candidate_queries("ケース。" + phrase + "。").facts[0]
    assert fact.strength == strength and fact.target["value"] is value


@pytest.mark.parametrize(
    "phrase,strength",
    [
        ("できれば3000円以下", "preferred"),
        ("3000円以下", "required"),
    ],
)
def test_budget_strength_reaches_observed_scoring(tmp_path, phrase, strength):
    import test_candidate_text_scoring as scoring

    service = scoring.search("マグカップ。" + phrase + "。")
    assert service._conditions[0]["strength"] == strength
    result = scoring.rank(
        service, tmp_path, [{"name": "マグカップ", "price": 4000, "currency": "JPY"}]
    )
    row = result.products[0]
    assert (row.evaluation.required_status == "contradicted") == (strength == "required")
    assert row.text_score.conditions[0].strength == strength
    assert row.text_score.conditions[0].score == 0.0


def test_bonsai_cannot_change_local_classification(tmp_path):
    import test_candidate_visual_conditions as visual
    from src.search_v2.candidate_diagnostics import CandidatePreparationError

    source = "マグカップ。できれば赤は避けたい。"
    phrase = "できれば赤は避けたい"
    service, model = visual.prepare(
        tmp_path, source, [visual.draft(phrase, "excluded", "appearance.color")]
    )
    payload = json.loads(json.loads(model.calls[0])["messages"][1]["content"])
    assert payload["condition_classification"][0]["strength"] == "excluded"
    assert service.plan.visual_conditions.conditions[0].strength == "excluded"
    with pytest.raises(CandidatePreparationError):
        visual.prepare(tmp_path, source, [visual.draft(phrase, "preferred", "appearance.color")])


def test_exclusion_bilingual_matching_target_and_neutral_absence(tmp_path):
    import test_candidate_bilingual_scoring as bilingual
    import test_candidate_text_scoring as scoring

    service, translator = bilingual.search("マグカップ。電子レンジ対応は不要。色にはこだわらない。")
    assert all("こだわらない" not in p for p in translator.calls)
    result = scoring.rank(
        service,
        tmp_path,
        [
            {
                "name": "マグカップ",
                "name_en": "Mug",
                "title_en_status": "available",
                "description_en": "microwave safe",
                "details_en_status": "available",
            }
        ],
    )
    rows = result.products[0].text_score.conditions
    assert len(rows) == 1
    assert (rows[0].strength, rows[0].score_ja, rows[0].score_en, rows[0].score) == (
        "excluded",
        0.0,
        1.0,
        1.0,
    )


def test_visual_terms_expand_matching_target_only():
    from types import SimpleNamespace
    from src.search_v2.condition_terms import LocalConditionExpander

    calls = []

    def translate(phrases):
        calls.extend(phrases)
        return tuple("red" if p == "赤" else None for p in phrases)

    source = "赤は避けたい"
    visual = SimpleNamespace(
        conditions=[
            SimpleNamespace(condition_id="visual-001", source_phrase=source, strength="excluded")
        ]
    )
    row = (
        LocalConditionExpander(translator=SimpleNamespace(translate=translate))
        .prepare(source, (), visual)
        .conditions[0]
    )
    assert row.terms_ja == ("赤",) and row.terms_en == ("red",)
    assert row.source_ja == source and row.strength == "excluded"


def test_legacy_plan_serialization_and_preparation_keep_legacy_interpretation():
    import test_candidate_text_scoring as scoring
    import test_candidate_search as candidate
    from src.search_v2.candidate_search import CandidateSearch, CandidatePlan, _digest

    source = "マグカップ。電子レンジ対応を希望。"
    current = scoring.search(source)
    legacy_queries = build_candidate_queries(source, language_profile=None)
    from src.search_v2.product_request import rebuild_product_request

    old = CandidatePlan.model_validate(
        current.plan.model_copy(
            update={
                "condition_language_profile": None,
                "condition_language_sha256": None,
                "query_plan": legacy_queries.query_plan,
                "query_options": tuple(legacy_queries.query_plan.queries),
                "request": rebuild_product_request(current.plan.request, legacy_queries.query_plan),
            }
        )
    )
    assert "condition_language" not in old.model_dump_json()
    assert _digest(old) != current.plan_sha256
    restored = CandidateSearch.from_approved_plan(
        old,
        source=source,
        owner_id="owner-1",
        plan_sha256=_digest(old),
        human_confirmed=True,
        normalization_profile=candidate.flow.backend_policy().normalization_profile,
        now=candidate.flow.NOW,
    )
    assert restored._queries.query_plan == legacy_queries.query_plan
    assert restored._conditions[0]["strength"] == "preferred"
    assert CandidatePlan.model_validate_json(old.model_dump_json()) == old


@pytest.mark.parametrize(
    "source", ["ケース。できれば赤。", "ケース。ＵＳＢ対応は不要。", "ケース。カ\u3099ラスは不要。"]
)
def test_confirmation_offsets_retain_original_unicode(source):
    from src.search_v2.condition_language import display_conditions

    rows = display_conditions(source)
    assert len(rows) == 1
    assert rows[0]["quote"] == source.split("。")[1]
    assert source[rows[0]["start"] : rows[0]["end"]] == rows[0]["quote"]


def test_inline_modifier_uses_syntax_target_and_retains_price():
    from test_lexical_structure import structure
    from src.search_v2.condition_language import display_conditions

    source = "できれば3000円以下のマグカップを探しています。"
    parsed = structure(source, "マグカップ", ("できれば3000円以下",), ("探しています",))
    query = build_candidate_queries(source, structure=parsed)
    assert query.retrieval_intent.product_name_ja == "マグカップ"
    assert query.price_strength == "preferred" and query.retrieval_intent.price.max_jpy == 3000
    assert display_conditions(source, structure=parsed)[0]["quote"] == "できれば3000円以下"


def test_known_shape_keeps_preference_without_partial_consumption():
    query = build_candidate_queries("マグカップ。丸い形だとうれしい。")
    assert len(query.facts) == 1
    assert query.facts[0].key == "form.shape" and query.facts[0].strength == "preferred"


def test_prepared_local_ginza_uses_common_modifier_scope():
    pytest.importorskip("ja_ginza")
    from src.search_v2.lexical_runtime import GinzaProductParser
    from src.search_v2.condition_language import analyze_conditions

    parser = GinzaProductParser()
    for source, expected in [
        (
            "マグカップ。できれば赤、容量300ml以上。取っ手がなくてもよい。",
            ["preferred", "required", "neutral"],
        ),
        ("マグカップ。丸い形だとうれしい。", ["preferred"]),
        ("スキャナー。USB対応があるとよい。", ["preferred"]),
        ("できれば3000円以下のマグカップを探しています。", ["preferred"]),
    ]:
        parsed = parser.analyze(source)
        rows = analyze_conditions(source, structure=parsed)
        assert [r.strength for r in rows] == expected
        build_candidate_queries(source, structure=parsed)


@pytest.mark.parametrize(
    "phrase,strength,target",
    [
        ("色にはこだわりません", "neutral", "色"),
        ("取っ手がなくても構いません", "neutral", "取っ手"),
        ("白を希望しています", "preferred", "白"),
        ("取っ手はいりません", "excluded", "取っ手"),
        ("容量は必ず300ml以上", "required", "容量は300ml以上"),
    ],
)
def test_polite_forms_and_middle_requirement(phrase, strength, target):
    from src.search_v2.condition_language import interpret_clause

    row = interpret_clause(phrase)
    assert (row.strength, row.target) == (strength, target)


def test_opposite_boolean_requirements_request_correction():
    from src.search_v2.condition_language import ConditionLanguageError

    with pytest.raises(ConditionLanguageError):
        build_candidate_queries("スキャナー。USB対応は必須。USB非対応は必須。")


def test_neutral_clause_count_is_bounded_before_display_or_model():
    from src.search_v2.condition_language import analyze_conditions, ConditionLanguageError

    with pytest.raises(ConditionLanguageError) as error:
        analyze_conditions("マグカップ。" + "赤でも構わない。" * 24)
    assert error.value.issues[0]["code"] == "condition_count"


def test_conflict_offsets_survive_syntax_fragment_projection():
    from test_lexical_structure import structure
    from src.search_v2.condition_language import ConditionLanguageError

    source = "スキャナーを探しています。usb対応は必須。usb非対応は必須。"
    phrases = ("usb対応は必須", "usb非対応は必須")
    parsed = structure(source, "スキャナー", phrases, ("探しています",))
    with pytest.raises(ConditionLanguageError) as caught:
        build_candidate_queries(source, structure=parsed)
    assert [source[i["start"] : i["end"]] for i in caught.value.issues] == list(phrases)
