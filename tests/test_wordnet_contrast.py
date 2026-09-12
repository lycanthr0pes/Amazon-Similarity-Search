"""Existing dictionary relationships, grammar, and the image-only fallback boundary."""

import json
import sqlite3

import pytest

from src.search_v2.visual_contrast import ContrastResolver, grammatical_negation
from src.search_v2.wordnet_contrast import WordNetContrastDictionary
from src.search_v2.bonsai_visual_conditions import build_visual_request, parse_visual_response
from test_visual_contrast import response, PAIR


@pytest.fixture
def dictionary(tmp_path):
    path = tmp_path / "wnjpn.db"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE word(wordid INTEGER PRIMARY KEY, lemma TEXT, lang TEXT, pos TEXT);
            CREATE TABLE sense(synset TEXT, wordid INTEGER, lang TEXT, src TEXT);
        """)
        words = [
            (1, "透明", "jpn", "a", "00000001-a"),
            (2, "透明", "jpn", "a", "00000001-a"),
            (3, "不透明", "jpn", "a", "00000002-a"),
            (4, "明るい", "jpn", "a", "00000003-a"),
            (5, "明るい", "jpn", "a", "00000004-a"),
            (6, "蓋", "jpn", "n", "00000005-n"),
            (7, "lid", "eng", "n", "00000005-n"),
            (8, "丸い", "jpn", "a", "00000006-a"),
        ]
        for key, lemma, lang, pos, synset in words:
            db.execute("INSERT INTO word VALUES (?,?,?,?)", (key, lemma, lang, pos))
            db.execute("INSERT INTO sense VALUES (?,?,?,?)", (synset, key, lang, "hand"))
    adj = tmp_path / "data.adj"
    adj.write_text(
        "  WordNet 3.0 synthetic fixture\n"
        "00000001 00 a 02 clear 0 transparent 0 001 ! 00000002 a 0201 | see through\n"
        "00000002 00 a 01 opaque 0 001 ! 00000001 a 0102 | not see through\n"
        "00000003 00 a 01 bright 0 001 ! 00000004 a 0101 | light\n"
        "00000004 00 a 01 dark 0 001 ! 00000003 a 0101 | dark\n"
        "00000006 00 s 01 round 0 001 & 00000001 a 0000 | round\n"
    )
    with WordNetContrastDictionary(path, adj) as dictionary:
        yield dictionary


def test_dictionary_follows_word_indices_not_arbitrary_synonyms(dictionary):
    pair = ContrastResolver(dictionary).resolve("透明")
    assert pair.origin == "wordnet"
    assert pair.matching == "A product that is transparent"
    assert pair.opposite == "A product that is opaque"
    assert pair.evidence.dictionary_sha256 == dictionary.sha256
    assert pair.evidence.sense_ids == ("00000001-a", "00000002-a")


def test_polysemy_and_non_antonym_relations_are_not_guessed(dictionary):
    resolver = ContrastResolver(dictionary)
    assert resolver.resolve("明るい") is None
    assert resolver.resolve("丸い") is None
    assert resolver.resolve("蓋が透明") is None
    assert resolver.resolve("赤と青の模様") is None
    assert resolver.resolve("できれば透明でも構わない") is None


@pytest.mark.parametrize("phrase", ["赤", "丸みのある形", "つやのない"])
def test_new_path_never_uses_handwritten_opposites(phrase):
    assert ContrastResolver().resolve(phrase) is None


@pytest.mark.parametrize(
    "phrase,negative",
    [
        ("丸い", "丸くない"),
        ("蓋が丸い", "蓋が丸くない"),
        ("透明", "透明ではない"),
        ("蓋がある", "蓋がない"),
        ("蓋がない", "蓋がある"),
        ("赤と青の模様", None),
        ("取っ手がなくてもよい", None),
    ],
)
def test_grammar_produces_hints_without_changing_scope(phrase, negative):
    assert grammatical_negation(phrase) == negative


def test_presence_is_concrete_and_exclusion_is_not_applied_twice(dictionary):
    resolver = ContrastResolver(dictionary)
    pair = resolver.resolve("蓋は不要")
    assert pair.origin == "grammar"
    assert pair.matching == "A product with a visible lid"
    assert pair.opposite == "A product without any lid"
    absent = resolver.resolve("蓋がない")
    assert absent.matching == pair.opposite
    assert absent.opposite == pair.matching


def test_dictionary_request_and_response_use_same_resolution(dictionary):
    resolver = ContrastResolver(dictionary)
    source = "マグカップ。透明。丸い。"
    request = json.loads(build_visual_request(source, contrast_resolver=resolver))
    body = json.loads(request["messages"][1]["content"])
    assert body["contrast_policy"] == "visual-contrast-v3"
    assert body["local_contrasts"]["透明"]["origin"] == "wordnet"
    assert body["contrast_inference_clauses"] == ["丸い"]
    assert body["contrast_negation_hints"]["丸い"] == "丸くない"
    conditions = parse_visual_response(
        source, response("透明"), require_contrast=True, contrast_resolver=resolver
    )
    assert conditions.conditions[0].contrast == resolver.resolve("透明")
    with pytest.raises(ValueError):
        parse_visual_response(
            source,
            response("透明", contrast=PAIR),
            require_contrast=True,
            contrast_resolver=resolver,
        )


def test_unconfigured_dictionary_still_uses_bonsai_without_extra_requests():
    conditions = parse_visual_response(
        "マグカップ。丸い。", response("丸い", contrast=PAIR), require_contrast=True
    )
    pair = conditions.conditions[0].contrast
    assert pair.profile == "visual-contrast-v3"
    assert pair.origin == "bonsai"


def test_dictionary_missing_file_is_not_created(tmp_path):
    path = tmp_path / "missing.db"
    with pytest.raises(ValueError):
        WordNetContrastDictionary(path, tmp_path / "missing.adj")
    assert not path.exists()


def test_bonsai_selects_a_dictionary_sense_without_rewriting_the_pair(dictionary):
    resolver = ContrastResolver(dictionary)
    source = "マグカップ。明るい。"
    candidates = resolver.candidates("明るい")
    assert len(candidates) == 2
    selected = candidates[0]
    proposal = {
        "matching": selected.matching,
        "opposite": selected.opposite,
        "sense_id": selected.evidence.sense_ids[0],
    }
    conditions = parse_visual_response(
        source,
        response("明るい", contrast=proposal),
        require_contrast=True,
        contrast_resolver=resolver,
    )
    assert conditions.conditions[0].contrast == selected
    proposal["sense_id"] = "99999999-a"
    with pytest.raises(ValueError):
        parse_visual_response(
            source,
            response("明るい", contrast=proposal),
            require_contrast=True,
            contrast_resolver=resolver,
        )


def test_dictionary_and_presence_reach_candidate_and_excluded_image_prompts(dictionary):
    from src.search_v2.candidate_search import prepare_candidate_search
    from src.search_v2.counterfactual_cloudflare_request import (
        build_counterfactual_cloudflare_request_set,
    )
    from test_search_v2_counterfactual_cloudflare_request import png_bytes
    import test_candidate_search as fixture

    class Bonsai:
        calls = 0

        def evaluate(self, request):
            self.calls += 1
            body = json.loads(json.loads(request)["messages"][1]["content"])
            assert body["local_contrasts"]["透明は避けたい"]["origin"] == "wordnet"
            return response("透明は避けたい", "excluded")

    bonsai = Bonsai()
    candidate = prepare_candidate_search(
        "マグカップ。透明は避けたい。3000円以下。",
        owner_id="owner-1",
        session_id="dictionary",
        postal_code="100-0001",
        normalization_profile=fixture.flow.backend_policy().normalization_profile,
        now=fixture.flow.NOW,
        visual_extractor=bonsai,
        contrast_resolver=ContrastResolver(dictionary),
    )
    assert bonsai.calls == 1
    assert candidate.plan.request.queries[0].value == "マグカップ"
    conditions = candidate.plan.visual_conditions
    pair = conditions.conditions[0].contrast
    requests = build_counterfactual_cloudflare_request_set(
        intent=candidate._queries.retrieval_intent,
        condition_set=conditions,
        preimage_plan_sha256="a" * 64,
        desired_reference_png=png_bytes(),
    )
    assert pair.opposite in requests.requests[0].prompt
    assert pair.matching in requests.requests[1].prompt
    assert (
        type(candidate.plan).model_validate_json(candidate.plan.model_dump_json()) == candidate.plan
    )


def test_dictionary_provenance_cannot_be_rebound_to_another_phrase(dictionary):
    from src.search_v2.bonsai_visual_conditions import validate_visual_conditions

    conditions = parse_visual_response(
        "マグカップ。透明。",
        response("透明"),
        require_contrast=True,
        contrast_resolver=ContrastResolver(dictionary),
    )
    c = conditions.conditions[0]
    forged = c.contrast.model_copy(
        update={"evidence": c.contrast.evidence.model_copy(update={"target": "別の条件"})}
    )
    with pytest.raises(ValueError):
        validate_visual_conditions(
            "マグカップ。透明。",
            conditions.model_copy(
                update={"conditions": (c.model_copy(update={"contrast": forged}),)}
            ),
        )


def test_dictionary_digest_pin_rejects_changed_asset(dictionary, tmp_path):
    path = tmp_path / "data.adj"
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="pinned version"):
        WordNetContrastDictionary(tmp_path / "wnjpn.db", path, expected_sha256=dictionary.sha256)


@pytest.mark.parametrize(
    "replacement", ["! 00000002 a 0001", "! 99999999 a 0201", "! 00000002 a 0202"]
)
def test_invalid_lexical_pointers_are_rejected(dictionary, tmp_path, replacement):
    path = tmp_path / "data.adj"
    path.write_text(path.read_text().replace("! 00000002 a 0201", replacement))
    with pytest.raises(ValueError):
        WordNetContrastDictionary(tmp_path / "wnjpn.db", path)


def test_other_wordnet_version_is_not_interpreted_as_30(dictionary, tmp_path):
    path = tmp_path / "data.adj"
    path.write_text(path.read_text().replace("WordNet 3.0", "WordNet 3.1"))
    with pytest.raises(ValueError, match="3.0 offset"):
        WordNetContrastDictionary(tmp_path / "wnjpn.db", path)


def test_browser_composition_passes_pinned_dictionary_to_preparation(tmp_path, monkeypatch):
    from contextlib import nullcontext
    from tools import browser_search_runtime as runtime

    model = tmp_path / "model"
    model.write_bytes(b"synthetic model identity only")
    monkeypatch.setattr(runtime, "MODEL", model)

    class Expander:
        def visual_contrasts(self, dictionary=None):
            return ContrastResolver(dictionary)

        def with_translator(self, translator):
            return self

        def with_resolver(self, resolver):
            return self

    monkeypatch.setattr("src.search_v2.lexical_expansion.ContextualQueryExpander", Expander)
    monkeypatch.setattr(
        "src.search_v2.lexical_assets.load_lexical_services",
        lambda _: nullcontext((Expander(), object())),
    )
    monkeypatch.setattr("src.search_v2.opus_mt.OpusMtTranslator", lambda *_: object())
    dictionary = object()

    def load_dictionary(db, adj, *, expected_sha256):
        assert db == runtime.WORDNET_DB
        assert adj == runtime.WORDNET_ADJECTIVES
        assert expected_sha256 == runtime.WORDNET_SHA256
        return nullcontext(dictionary)

    monkeypatch.setattr("src.search_v2.wordnet_contrast.WordNetContrastDictionary", load_dictionary)
    monkeypatch.setattr(runtime, "browser_bonsai", lambda _: nullcontext(object()))
    seen = []

    def flow(source, **kwargs):
        seen.append(kwargs["contrast_resolver"])
        return object()

    monkeypatch.setattr("src.search_v2.candidate_flow.CandidateSearchFlow", flow)
    monkeypatch.setattr(runtime, "candidate_browser_steps", lambda *_, **__: iter(["prepared"]))
    assert list(runtime.live_steps(tmp_path / "run")) == ["prepared"]
    assert len(seen) == 1 and seen[0]._dictionary is dictionary


def test_missing_dictionary_contrasts_are_explicit_inference_tasks(dictionary):
    resolver = ContrastResolver(dictionary)
    source = "ケース。透明。明るい。らせん状の模様。"
    request = json.loads(build_visual_request(source, contrast_resolver=resolver))
    body = json.loads(request["messages"][1]["content"])
    assert body["contrast_inference_tasks"] == {
        "らせん状の模様": {
            "target": "らせん状の模様",
            "reason": "no_contrast_candidate",
            "output": "matching_opposite",
        }
    }
    assert "透明" in body["local_contrasts"]
    assert "明るい" in body["dictionary_contrast_candidates"]


def test_missing_component_requests_a_bonsai_name_for_presence_pair(dictionary):
    request = json.loads(
        build_visual_request("ケース。羽根付き。", contrast_resolver=ContrastResolver(dictionary))
    )
    body = json.loads(request["messages"][1]["content"])
    assert body["contrast_inference_tasks"] == {
        "羽根付き": {"target": "羽根付き", "reason": "no_contrast_candidate", "output": "part_en"}
    }


@pytest.mark.parametrize(
    "strength,phrase", [("required", "らせん状の模様"), ("excluded", "らせん状の模様は避けたい")]
)
def test_missing_contrast_reaches_images_with_one_bonsai_call(dictionary, strength, phrase):
    import test_candidate_search as fixture
    from src.search_v2.candidate_search import prepare_candidate_search
    from src.search_v2.counterfactual_cloudflare_request import (
        build_counterfactual_cloudflare_request_set,
    )
    from test_search_v2_counterfactual_cloudflare_request import png_bytes

    class Bonsai:
        calls = 0

        def evaluate(self, request):
            self.calls += 1
            task = json.loads(json.loads(request)["messages"][1]["content"])[
                "contrast_inference_tasks"
            ][phrase]
            assert task["output"] == "matching_opposite"
            return response(phrase, strength, PAIR)

    bonsai = Bonsai()
    source = f"ケース。{phrase}。2000円以下。"
    candidate = prepare_candidate_search(
        source,
        owner_id="owner-1",
        session_id="missing-contrast",
        postal_code="100-0001",
        normalization_profile=fixture.flow.backend_policy().normalization_profile,
        now=fixture.flow.NOW,
        visual_extractor=bonsai,
        contrast_resolver=ContrastResolver(dictionary),
    )
    assert bonsai.calls == 1
    condition = candidate.plan.visual_conditions.conditions[0]
    assert condition.contrast.origin == "bonsai"
    assert condition.contrast.evidence.dictionary_sha256 is None
    assert condition.contrast.evidence.sense_ids == ()
    assert candidate.plan.request.queries[0].value == "ケース"
    requests = build_counterfactual_cloudflare_request_set(
        intent=candidate._queries.retrieval_intent,
        condition_set=candidate.plan.visual_conditions,
        preimage_plan_sha256="a" * 64,
        desired_reference_png=png_bytes(),
    )
    matching, opposite = (
        (PAIR["opposite"], PAIR["matching"])
        if strength == "excluded"
        else (PAIR["matching"], PAIR["opposite"])
    )
    assert matching in requests.requests[0].prompt
    assert opposite in requests.requests[1].prompt


@pytest.mark.parametrize(
    "phrase,strength,contrast,allowed",
    [
        ("透明", "required", None, True),
        ("明るい", "required", None, False),
        ("らせん状の模様", "required", None, False),
        ("明るい", "required", {"sense_id": "00000003-a"}, True),
        ("らせん状の模様", "required", {"sense_id": "00000003-a"}, False),
        ("明るい", "excluded", {"sense_id": "00000003-a"}, False),
        ("らせん状の模様", "required", PAIR, True),
        ("透明", "required", PAIR, False),
    ],
)
def test_generation_requires_the_clause_specific_contrast(
    dictionary, phrase, strength, contrast, allowed
):
    from jsonschema import Draft202012Validator

    request = json.loads(
        build_visual_request(
            "ケース。透明。明るい。らせん状の模様。", contrast_resolver=ContrastResolver(dictionary)
        )
    )
    schema = request["response_format"]["schema"]
    value = {
        "status": "ready",
        "conditions": [
            {
                "source_phrase": phrase,
                "strength": strength,
                "attribute_key": None,
                "focus": None,
                "contrast": contrast,
            }
        ],
    }
    assert Draft202012Validator(schema).is_valid(value) is allowed


def test_unknown_presence_requires_a_component_name_not_null(dictionary):
    from jsonschema import Draft202012Validator

    request = json.loads(
        build_visual_request("ケース。羽根付き。", contrast_resolver=ContrastResolver(dictionary))
    )
    schema = request["response_format"]["schema"]
    row = {
        "source_phrase": "羽根付き",
        "strength": "required",
        "attribute_key": None,
        "focus": None,
    }
    for contrast, allowed in [(None, False), ({"part_en": "feather"}, True), (PAIR, False)]:
        assert (
            Draft202012Validator(schema).is_valid(
                {"status": "ready", "conditions": [{**row, "contrast": contrast}]}
            )
            is allowed
        )
