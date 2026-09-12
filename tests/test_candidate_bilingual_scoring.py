"""Per-condition bilingual maxima, negative evidence and immutable old profiles."""

import json

import pytest

import test_candidate_search as candidate
import test_candidate_text_scoring as scoring
from src.search_v2.candidate_search import CandidateSearch, CandidateRanking


class Dictionary:
    sha256 = "a" * 64

    def lookup_contextual(self, phrase):
        from src.search_v2.lexical_selection import LexicalSense

        return (
            (
                LexicalSense(
                    "fixture:heat",
                    "fixture",
                    ("保温", "保温性"),
                    ("heat retention",),
                    "thermal insulation",
                ),
            )
            if phrase == "保温"
            else ()
        )


class Translator:
    sha256 = "b" * 64

    def __init__(self):
        self.calls = []

    def translate(self, phrases):
        self.calls.extend(phrases)
        mapping = {
            "電子レンジ": "microwave",
            "電子レンジ対応": "microwave safe",
            "容量": "capacity",
            "容量400ml以上": "capacity at least 400 ml",
            "保温": "heat retention",
            "保温性": "heat retention",
        }
        return tuple(mapping.get(p) for p in phrases)


def search(source):
    from src.search_v2.condition_terms import LocalConditionExpander

    translator = Translator()
    return CandidateSearch(
        source,
        owner_id="owner-1",
        session_id="bilingual-test",
        postal_code="100-0001",
        normalization_profile=candidate.flow.backend_policy().normalization_profile,
        now=candidate.flow.NOW,
        condition_expander=LocalConditionExpander(Dictionary(), translator=translator),
    ), translator


def test_each_condition_uses_maximum_and_records_both_languages(tmp_path):
    service, _ = search("マグカップ。電子レンジ対応。容量400ml以上。")
    result = scoring.rank(
        service,
        tmp_path,
        [
            {
                "name": "マグカップ",
                "name_en": "Mug",
                "title_en_status": "available",
                "description": "電子レンジで使えます。容量は300mlです。",
                "description_en": "Not microwave safe. Capacity: 500 ml.",
                "details_en_status": "available",
            }
        ],
    )
    rows = result.products[0].text_score.conditions
    assert [(r.score_ja, r.score_en, r.score) for r in rows] == [(1.0, 0.0, 1.0), (0.0, 1.0, 1.0)]
    assert result.products[0].text_score.required_ratio == 1.0
    assert result.products[0].text_score.profile_id == "candidate-text-bilingual-v2"
    assert CandidateRanking.model_validate_json(result.model_dump_json()) == result
    wire = json.loads(result.model_dump_json())
    wire["products"][0]["text_score"]["conditions"][0]["score_en"] = 1.0
    with pytest.raises(ValueError):
        CandidateRanking.model_validate_json(json.dumps(wire))


@pytest.mark.parametrize("english,expected", [("microwave safe", 1.0), ("not microwave safe", 0.0)])
def test_english_title_and_details_are_evaluated_without_overriding_negation(
    tmp_path, english, expected
):
    service, _ = search("マグカップ。電子レンジ対応。")
    result = scoring.rank(
        service,
        tmp_path,
        [
            {
                "name": "マグカップ",
                "name_en": english,
                "title_en_status": "available",
                "description_en": english,
                "details_en_status": "available",
            }
        ],
    )
    assert result.products[0].text_score.conditions[0].score_en == expected


def test_english_missing_preserves_japanese_score_and_old_profile(tmp_path):
    service, _ = search("マグカップ。電子レンジ対応。")
    result = scoring.rank(
        service, tmp_path, [{"name": "マグカップ", "description": "電子レンジ対応"}]
    )
    row = result.products[0].text_score.conditions[0]
    assert row.score_ja == row.score == 1.0
    assert row.score_en is None
    old_root = tmp_path / "old"
    old_root.mkdir()
    old = scoring.rank(
        scoring.search("マグカップ。電子レンジ対応。"),
        old_root,
        [{"name": "マグカップ", "description": "電子レンジ対応"}],
    )
    assert old.products[0].text_score.profile_id == "candidate-text-v1"
    assert "score_ja" not in old.products[0].text_score.conditions[0].model_dump()
    assert CandidateRanking.model_validate_json(old.model_dump_json()) == old


def test_condition_dictionary_synonyms_and_translation_requests_are_deduplicated():
    from src.search_v2.condition_terms import LocalConditionExpander

    translator = Translator()
    expander = LocalConditionExpander(Dictionary(), translator=translator)
    conditions = tuple(
        {
            "condition_id": f"condition-{i:03}",
            "label": "保温対応",
            "source_quote": "保温対応",
            "target": {"value_type": "boolean", "value": True},
            "strength": "required",
            "attribute_key": "custom",
        }
        for i in (1, 2)
    )
    bundle = expander.prepare("保温対応", conditions, None)
    assert "保温性" in bundle.conditions[0].terms_ja
    assert "heat retention" in bundle.conditions[0].terms_en
    assert len(translator.calls) == len(set(translator.calls))


def test_english_title_can_win_independently_of_condition_score(tmp_path):
    import test_bonsai_query_terms as query
    from src.search_v2.condition_terms import LocalConditionExpander

    service = CandidateSearch(
        "スキャナー。電子レンジ対応。",
        owner_id="owner-1",
        session_id="title-test",
        postal_code="100-0001",
        normalization_profile=candidate.flow.backend_policy().normalization_profile,
        now=candidate.flow.NOW,
        query_expander=query.QueryBonsai(tmp_path),
        condition_expander=LocalConditionExpander(Dictionary(), translator=Translator()),
    )
    result = scoring.rank(
        service,
        tmp_path,
        [
            {
                "name": "合成商品",
                "name_en": "scanner",
                "title_en_status": "available",
                "details_en_status": "available",
                "description_en": "Not microwave safe.",
            }
        ],
    )
    row = result.products[0]
    assert row.title_scores.score_ja == 0.0
    assert row.title_scores.score_en == row.lexical_score == 1.0
    assert row.text_score.required_ratio == 0.0


@pytest.mark.parametrize(
    "feature,description,expected",
    [
        ("Capacity: 0.5 liters", "Capacity: 200 ml", 1.0),
        ("Capacity: 300 ml", "Capacity: 500 ml", 0.0),
        ("Capacity: unknown", "Capacity: 500 ml", 0.0),
        ("Weight: 500 grams", "Capacity: 300 ml", 0.0),
        ("Capacity: 500 grams", "Capacity: 500 ml", 0.0),
        ("Capacity: 500 ml approximately", "Capacity: 500 ml", 0.0),
    ],
)
def test_english_numeric_units_and_structured_priority(tmp_path, feature, description, expected):
    service, _ = search("マグカップ。容量400ml以上。")
    result = scoring.rank(
        service,
        tmp_path,
        [
            {
                "name": "マグカップ",
                "features_en": [feature],
                "description_en": description,
                "details_en_status": "available",
            }
        ],
    )
    assert result.products[0].text_score.conditions[0].score_en == expected


def test_excluded_condition_uses_higher_match_as_exclusion(tmp_path):
    service, _ = search("マグカップ。電子レンジ対応を除外。")
    result = scoring.rank(
        service,
        tmp_path,
        [
            {
                "name": "マグカップ",
                "description_en": "Microwave safe.",
                "details_en_status": "available",
            }
        ],
    )
    row = result.products[0].text_score
    assert row.excluded_ratio == 1.0
    assert row.conditions[0].strength == "excluded"
    assert row.conditions[0].score_ja == 0.0 and row.conditions[0].score_en == 1.0


def test_truncated_english_description_is_not_used_as_complete_evidence(tmp_path):
    service, _ = search("マグカップ。電子レンジ対応。")
    result = scoring.rank(
        service,
        tmp_path,
        [
            {
                "name": "マグカップ",
                "description_en": "Microwave safe. " + "x" * 4001,
                "details_en_status": "available",
            }
        ],
    )
    product = result.products[0]
    assert "description_en" in product.product.truncated_fields
    assert product.text_score.conditions[0].score_en is None


def test_bilingual_image_completion_and_history_keep_scores(tmp_path, monkeypatch):
    import test_candidate_connected_flow as connected
    from src.search_v2.condition_terms import LocalConditionExpander

    flow, _, _, history, clock = connected.start(
        tmp_path, condition_expander=LocalConditionExpander(Dictionary(), translator=Translator())
    )
    connected.approve(flow)
    connected.fetch(flow, tmp_path)
    kwargs, _ = connected.clip(monkeypatch, tmp_path)
    completed = flow.complete(owner_id=connected.OWNER, **kwargs)
    assert completed.ranking.text_profile_id == "candidate-text-bilingual-v2"
    assert completed.ranking.sort_profile_id == "excluded-title-conditions-image-review-v1"
    assert all(
        row.total_score == 0.5 * row.candidate.lexical_score + 0.5 * row.image.image_score
        for row in completed.ranking.products
    )
    restored = history.get(
        owner_id=connected.OWNER, locator=completed.history.locator, now=clock[0]
    )
    assert restored == completed.history
    for saved, row in zip(restored.products, completed.ranking.products, strict=True):
        assert saved.title_scores == row.candidate.title_scores
        assert saved.condition_scores == row.candidate.text_score.conditions


def test_ambiguous_dictionary_and_failed_translation_keep_japanese():
    from src.search_v2.condition_terms import LocalConditionExpander

    class Ambiguous(Dictionary):
        def lookup_contextual(self, phrase):
            sense = super().lookup_contextual("保温")[0]
            from dataclasses import replace

            return (sense, replace(sense, sense_id="other", forms=("別の語義",)))

    class Failed(Translator):
        def translate(self, phrases):
            raise ValueError("fixture failure")

    result = LocalConditionExpander(Ambiguous(), translator=Failed()).prepare(
        "保温対応",
        (
            {
                "condition_id": "condition-001",
                "strength": "required",
                "source_quote": "保温対応",
                "label": "保温対応",
                "target": {"value_type": "boolean", "value": True},
                "attribute_key": "custom",
            },
        ),
        None,
    )
    assert result.conditions[0].terms_ja == ("保温",)
    assert result.conditions[0].terms_en == ()
    assert result.conditions[0].sense_ids == ()


def test_composed_condition_synonyms_preserve_qualifiers_and_translate_whole_phrase():
    from types import SimpleNamespace
    from src.search_v2.condition_terms import LocalConditionExpander

    translator = Translator()
    phrase = "保温に優れた"
    bundle = LocalConditionExpander(Dictionary(), translator=translator).prepare(
        phrase,
        (),
        SimpleNamespace(
            conditions=(
                SimpleNamespace(
                    condition_id="visual-001", strength="required", source_phrase=phrase
                ),
            )
        ),
    )
    row = bundle.conditions[0]
    assert row.terms_ja == (phrase, "保温性に優れた")
    assert set(translator.calls) == set(row.terms_ja)
    assert "heat retention" not in row.terms_en
