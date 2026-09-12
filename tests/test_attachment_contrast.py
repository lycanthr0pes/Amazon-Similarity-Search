"""Synthetic attachment conditions use existing dictionary names and presence grammar."""

import json

import pytest

from src.search_v2.bonsai_visual_conditions import build_visual_request, parse_visual_response
from src.search_v2.visual_contrast import ContrastResolver, grammatical_negation
from src.search_v2.lexical_selection import LexicalSense
from src.search_v2.lexical_structure import ProductStructure, TextSpan
from test_visual_contrast import response


class Lexicon:
    sha256 = "b" * 64

    def lookup(self, phrase):
        if phrase != "ストラップ":
            return ()
        return tuple(
            LexicalSense(f"jmdict:1234:{i}", "jmdict", (phrase,), (english,), english)
            for i, english in enumerate(("carrying strap", "wrist strap"), 1)
        )


@pytest.mark.parametrize(
    "phrase", ["ストラップ付き", "ストラップつき", "ストラップが付属", "ストラップが付いている"]
)
def test_attachment_grammar_is_not_a_handwritten_part_dictionary(phrase):
    assert grammatical_negation(phrase) == "ストラップがない"


def test_existing_dictionary_candidates_need_only_the_selected_id():
    resolver = ContrastResolver(lexicon=Lexicon())
    source = "ストラップ付きのケース"
    structure = ProductStructure(source, TextSpan(8, 11), (TextSpan(0, 7),), (), "fixture")
    body = json.loads(
        json.loads(build_visual_request(source, structure=structure, contrast_resolver=resolver))[
            "messages"
        ][1]["content"]
    )
    assert body["presence_conditions"]["ストラップ付き"]["part"] == "ストラップ"
    assert len(body["dictionary_contrast_candidates"]["ストラップ付き"]) == 2
    conditions = parse_visual_response(
        source,
        response("ストラップ付き", contrast={"sense_id": "jmdict:1234:2"}),
        structure=structure,
        contrast_resolver=resolver,
        require_contrast=True,
    )
    pair = conditions.conditions[0].contrast
    assert pair.matching == "A product with a visible wrist strap"
    assert pair.opposite == "A product without any wrist strap"
    assert pair.origin == "grammar"
    assert pair.evidence.dictionary_sha256 == Lexicon.sha256


@pytest.mark.parametrize(
    "phrase,strength",
    [("羽根付き", "required"), ("羽根がない", "required"), ("羽根付きは避けたい", "excluded")],
)
def test_unknown_component_uses_one_model_noun_and_code_builds_both_sides(phrase, strength):
    conditions = parse_visual_response(
        f"飾り。{phrase}。",
        response(phrase, strength, {"part_en": "feather"}),
        require_contrast=True,
    )
    pair = conditions.conditions[0].contrast
    assert pair.origin == "bonsai"
    assert ("without" in pair.matching) == (phrase == "羽根がない")
    assert ("without" in pair.opposite) != (phrase == "羽根がない")


@pytest.mark.parametrize(
    "phrase,proposal",
    [
        ("丸い", {"part_en": "strap"}),
        ("羽根付き", {"part_en": "without feathers"}),
        ("羽根付き", {"part_en": "羽根"}),
        ("羽根付き", {"sense_id": "jmdict:9999:1"}),
        ("赤い羽根付き", {"part_en": "feather"}),
    ],
)
def test_wrong_scope_or_unbound_dictionary_or_negative_noun_is_rejected(phrase, proposal):
    with pytest.raises(ValueError):
        parse_visual_response(
            f"飾り。{phrase}。", response(phrase, contrast=proposal), require_contrast=True
        )


def test_neutral_attachments_are_not_image_conditions():
    assert grammatical_negation("ストラップがなくてもよい") is None


def test_attachment_candidate_reaches_review_and_image_prompts_with_one_inference():
    from src.search_v2.candidate_search import prepare_candidate_search
    from src.search_v2.counterfactual_cloudflare_request import (
        build_counterfactual_cloudflare_request_set,
    )
    from test_search_v2_counterfactual_cloudflare_request import png_bytes
    import test_candidate_search as fixture

    source = "ストラップ付きのケース"

    class Parser:
        def analyze(self, text):
            return ProductStructure(text, TextSpan(8, 11), (TextSpan(0, 7),), (), "fixture")

    class Bonsai:
        calls = 0

        def evaluate(self, request):
            self.calls += 1
            return response("ストラップ付き", contrast={"sense_id": "jmdict:1234:1"})

    bonsai = Bonsai()
    candidate = prepare_candidate_search(
        source,
        owner_id="owner-1",
        session_id="attachment",
        postal_code="100-0001",
        normalization_profile=fixture.flow.backend_policy().normalization_profile,
        now=fixture.flow.NOW,
        source_parser=Parser(),
        visual_extractor=bonsai,
        contrast_resolver=ContrastResolver(lexicon=Lexicon()),
    )
    assert bonsai.calls == 1
    assert candidate.plan.title_comparison.product_name_ja == "ケース"
    assert candidate.plan.request.queries[0].value == "ケース"
    conditions = candidate.plan.visual_conditions
    assert conditions.conditions[0].source_phrase == "ストラップ付き"
    requests = build_counterfactual_cloudflare_request_set(
        intent=candidate._queries.retrieval_intent,
        condition_set=conditions,
        preimage_plan_sha256="a" * 64,
        desired_reference_png=png_bytes(),
    )
    assert "with a visible carrying strap" in requests.requests[0].prompt
    assert "without any carrying strap" in requests.requests[1].prompt


def test_old_v2_plan_is_read_without_changing_profile_or_evidence():
    from src.search_v2.visual_contrast import VisualContrast

    data = {
        "profile": "visual-contrast-v2",
        "origin": "grammar",
        "matching": "A product with a visible lid",
        "opposite": "A product without any lid",
        "evidence": {
            "target": "蓋がある",
            "dictionary_sha256": "a" * 64,
            "sense_ids": ["00000001-n"],
        },
    }
    assert VisualContrast.model_validate_json(json.dumps(data)).model_dump(mode="json") == data


def test_nonvisual_product_modifier_is_not_added_to_attachment_conditions():
    source = "ストラップ付きのワイヤレスケース"
    structure = ProductStructure(source, TextSpan(8, len(source)), (TextSpan(0, 7),), (), "fixture")
    body = json.loads(
        json.loads(build_visual_request(source, structure=structure))["messages"][1]["content"]
    )
    assert body["clauses"] == ["ストラップ付き"]
    assert set(body["presence_conditions"]) == {"ストラップ付き"}


def test_dictionary_presence_generation_requires_a_listed_id():
    from jsonschema import Draft202012Validator

    resolver = ContrastResolver(lexicon=Lexicon())
    request = json.loads(
        build_visual_request("ケース。ストラップ付き。", contrast_resolver=resolver)
    )
    schema = request["response_format"]["schema"]
    row = {
        "source_phrase": "ストラップ付き",
        "strength": "required",
        "attribute_key": None,
        "focus": None,
    }
    for contrast, allowed in [
        ({"sense_id": "jmdict:1234:1"}, True),
        ({"sense_id": "jmdict:1234:2"}, True),
        ({"sense_id": "jmdict:9999:1"}, False),
        ({"part_en": "wrist strap"}, False),
        ({"part_en": "case with a wrist strap"}, False),
        (None, False),
    ]:
        assert (
            Draft202012Validator(schema).is_valid(
                {"status": "ready", "conditions": [{**row, "contrast": contrast}]}
            )
            is allowed
        )
