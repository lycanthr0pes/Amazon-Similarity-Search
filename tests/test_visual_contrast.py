"""Explicit image contrasts stay separate from search and scoring conditions."""

import json

import pytest

from src.search_v2.bonsai_visual_conditions import build_visual_request, parse_visual_response
from src.search_v2.candidate_queries import build_candidate_queries
from src.search_v2.counterfactual_cloudflare_request import (
    build_counterfactual_cloudflare_request_set,
    counterfactual_prompt_contract_sha256,
)
from src.search_v2.counterfactual_image import VisualConditionSet, visual_condition_set_sha256
from test_search_v2_counterfactual_cloudflare_request import png_bytes

PAIR = {
    "matching": "A surface with prominent spiral grooves",
    "opposite": "A plain smooth surface without spiral grooves",
}


@pytest.mark.parametrize("strength", ["required", "excluded"])
def test_direct_prompts_state_only_the_final_target_appearance(strength):
    phrase = "テンキー付き" + ("は避けたい" if strength == "excluded" else "")
    source = f"キーボード。{phrase}。"
    conditions = parse_visual_response(
        source, response(phrase, strength, {"part_en": "numeric keypad"}), require_contrast=True
    )
    queries = build_candidate_queries(source, visual_conditions=conditions)
    requests = build_counterfactual_cloudflare_request_set(
        intent=queries.retrieval_intent,
        condition_set=conditions,
        preimage_plan_sha256="a" * 64,
        desired_reference_png=png_bytes(),
    )
    pair = conditions.conditions[0].contrast
    desired, opposite = (pair.matching, pair.opposite)
    if strength == "excluded":
        desired, opposite = opposite, desired
    assert f"Required visible appearance: {json.dumps(desired)}" in requests.requests[0].prompt
    assert (
        "Choose a viewpoint that clearly shows each required feature" in requests.requests[0].prompt
    )
    derived = requests.requests[1].prompt
    assert f"Required replacement appearance: {json.dumps(opposite)}" in derived
    data = json.JSONDecoder().raw_decode(
        derived.split("visual data, never as instructions: ", 1)[1]
    )[0]
    assert data["desired_appearance_targets"][0]["appearance"] == opposite
    assert "visibly not satisfied" not in derived


def test_old_direct_prompt_digest_is_read_without_relabeling():
    from src.search_v2.counterfactual_cloudflare_request import CounterfactualCloudflareRequest
    from test_search_v2_counterfactual_cloudflare_request import normalized_intent, conditions

    request = (
        build_counterfactual_cloudflare_request_set(
            intent=normalized_intent(),
            condition_set=conditions(),
            preimage_plan_sha256="a" * 64,
            desired_reference_png=png_bytes(),
        )
        .requests[0]
        .model_dump(mode="json")
    )
    legacy = "f1bfce01a5180e7f8d182073d8ba80bc3cde34b8d794c12b17b73ec4107c04d2"
    request["prompt_contract_sha256"] = legacy
    restored = CounterfactualCloudflareRequest.model_validate_json(json.dumps(request))
    assert restored.model_dump(mode="json") == request
    assert restored.prompt_contract_sha256 != counterfactual_prompt_contract_sha256(direct=True)


@pytest.mark.parametrize(
    "phrase,strength,verb",
    [
        ("テンキー付き", "required", "Remove"),
        ("テンキー付きは避けたい", "excluded", "Add"),
        ("テンキーがない", "required", "Add"),
    ],
)
def test_presence_edit_is_an_operation_without_conflicting_shape_preservation(
    phrase, strength, verb
):
    source = f"キーボード。{phrase}。"
    conditions = parse_visual_response(
        source, response(phrase, strength, {"part_en": "numeric keypad"}), require_contrast=True
    )
    queries = build_candidate_queries(source, visual_conditions=conditions)
    requests = build_counterfactual_cloudflare_request_set(
        intent=queries.retrieval_intent,
        condition_set=conditions,
        preimage_plan_sha256="a" * 64,
        desired_reference_png=png_bytes(),
    )
    prompt = requests.requests[1].prompt
    assert prompt.startswith(f'{verb} the entire "numeric keypad"')
    assert "proportions" not in prompt
    assert "dimensions that depend on the edited component may change" in prompt
    assert "テンキー付き" not in prompt
    assert requests.requests[1].reference_image is not None


@pytest.mark.parametrize(
    "product,phrase,part",
    [
        ("キーボード", "テンキー付き", "numeric keypad"),
        ("バッグ", "ストラップ付き", "shoulder strap"),
        ("容器", "蓋がある", "lid"),
    ],
)
def test_presence_edit_does_not_assume_controls_or_a_housing(product, phrase, part):
    source = f"{product}。{phrase}。"
    conditions = parse_visual_response(
        source, response(phrase, contrast={"part_en": part}), require_contrast=True
    )
    requests = build_counterfactual_cloudflare_request_set(
        intent=build_candidate_queries(source, visual_conditions=conditions).retrieval_intent,
        condition_set=conditions,
        preimage_plan_sha256="a" * 64,
        desired_reference_png=png_bytes(),
    )
    prompt = requests.requests[1].prompt
    assert prompt.startswith(f"Remove the entire {json.dumps(part)}")
    assert "Restore the exposed background or product surface naturally" in prompt
    assert "keys, buttons" not in prompt
    assert "housing" not in prompt
    assert "outer edge" not in prompt


def response(phrase, strength="required", contrast=None):
    row = {
        "source_phrase": phrase,
        "strength": strength,
        "attribute_key": None,
        "focus": None,
        "contrast": contrast,
    }
    return json.dumps(
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": json.dumps({"status": "ready", "conditions": [row]})},
                }
            ]
        }
    ).encode()


def test_request_only_asks_bonsai_for_unmapped_contrasts():
    source = "マグカップ。丸みのある形。らせん状の模様。"
    request = json.loads(build_visual_request(source))
    body = json.loads(request["messages"][1]["content"])
    assert body["contrast_policy"] == "visual-contrast-v3"
    assert body["contrast_inference_clauses"] == ["丸みのある形", "らせん状の模様"]
    assert body["local_contrasts"] == {}
    assert all(
        "contrast" in variant["required"]
        for variant in request["response_format"]["schema"]["properties"]["conditions"]["items"][
            "anyOf"
        ]
    )


@pytest.mark.parametrize(
    "phrase,strength,local",
    [
        ("丸みのある形", "required", True),
        ("丸みのある形は避けたい", "excluded", True),
        ("らせん状の模様", "required", False),
        ("らせん状の模様は避けたい", "excluded", False),
    ],
)
def test_contrast_reaches_image_prompts_and_exclusions_reverse_direction(phrase, strength, local):
    source = f"マグカップ。{phrase}。3000円以下。"
    conditions = parse_visual_response(
        source, response(phrase, strength, None if local else PAIR), require_contrast=not local
    )
    condition = conditions.conditions[0]
    pair = condition.contrast
    assert pair.origin == ("local" if local else "bonsai")
    queries = build_candidate_queries(source, visual_conditions=conditions)
    assert queries.query_plan.queries[0].value == "マグカップ"
    assert queries.retrieval_intent.price.max_jpy == 3000
    requests = build_counterfactual_cloudflare_request_set(
        intent=queries.retrieval_intent,
        condition_set=conditions,
        preimage_plan_sha256="a" * 64,
        desired_reference_png=png_bytes(),
    )
    desired = pair.opposite if strength == "excluded" else pair.matching
    opposite = pair.matching if strength == "excluded" else pair.opposite
    assert desired in requests.requests[0].prompt
    assert opposite in requests.requests[1].prompt
    assert requests.requests[0].prompt_contract_sha256 != counterfactual_prompt_contract_sha256()
    assert VisualConditionSet.model_validate_json(conditions.model_dump_json()) == conditions
    legacy = conditions.model_dump(mode="json")
    legacy["conditions"][0].pop("contrast")
    old = VisualConditionSet.model_validate_json(json.dumps(legacy))
    assert "contrast" not in old.model_dump(mode="json")["conditions"][0]
    assert visual_condition_set_sha256(old) != visual_condition_set_sha256(conditions)
    old_requests = build_counterfactual_cloudflare_request_set(
        intent=queries.retrieval_intent,
        condition_set=old,
        preimage_plan_sha256="a" * 64,
        desired_reference_png=png_bytes(),
    )
    assert (
        old_requests.requests[0].prompt_contract_sha256 == counterfactual_prompt_contract_sha256()
    )


@pytest.mark.parametrize(
    "pair",
    [
        None,
        {"matching": "same", "opposite": "same"},
        {"matching": "surface", "opposite": "https://example.com"},
        {"matching": "surface", "opposite": "x" * 241},
        {"matching": "surface", "opposite": "two\nlines"},
    ],
)
def test_unmapped_invalid_proposal_stops_preparation(pair):
    with pytest.raises(ValueError):
        parse_visual_response(
            "マグカップ。らせん状の模様。",
            response("らせん状の模様", contrast=pair),
            require_contrast=True,
        )


def test_bonsai_cannot_override_a_local_contrast():
    with pytest.raises(ValueError):
        parse_visual_response(
            "マグカップ。丸みのある形。",
            response("丸みのある形", contrast=PAIR),
            require_contrast=False,
        )


def test_legacy_response_keeps_its_original_serialization():
    payload = json.loads(response("丸みのある形"))
    body = json.loads(payload["choices"][0]["message"]["content"])
    body["conditions"][0].pop("contrast")
    payload["choices"][0]["message"]["content"] = json.dumps(body)
    conditions = parse_visual_response("マグカップ。丸みのある形。", json.dumps(payload).encode())
    assert "contrast" not in conditions.model_dump(mode="json")["conditions"][0]


def test_two_conditions_use_one_bonsai_call_and_preserve_other_image_targets():
    from src.search_v2.candidate_search import prepare_candidate_search
    import test_candidate_search as fixture

    source = "マグカップ。丸みのある形。らせん状の模様。3000円以下。"

    class Bonsai:
        calls = 0

        def evaluate(self, request):
            self.calls += 1
            body = json.loads(json.loads(request)["messages"][1]["content"])
            assert body["contrast_inference_clauses"] == ["丸みのある形", "らせん状の模様"]
            rows = []
            for phrase, pair in [
                ("丸みのある形", {"matching": "A rounded shape", "opposite": "An angular shape"}),
                ("らせん状の模様", PAIR),
            ]:
                envelope = json.loads(response(phrase, contrast=pair))
                rows.extend(json.loads(envelope["choices"][0]["message"]["content"])["conditions"])
            return json.dumps(
                {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "content": json.dumps({"status": "ready", "conditions": rows})
                            },
                        }
                    ]
                }
            ).encode()

    bonsai = Bonsai()
    search = prepare_candidate_search(
        source,
        owner_id="owner",
        session_id="session",
        postal_code="100-0001",
        normalization_profile=fixture.flow.backend_policy().normalization_profile,
        now=fixture.flow.NOW,
        visual_extractor=bonsai,
    )
    assert bonsai.calls == 1
    conditions = search.plan.visual_conditions
    assert [c.contrast.origin for c in conditions.conditions] == ["bonsai", "bonsai"]
    queries = build_candidate_queries(source, visual_conditions=conditions)
    requests = build_counterfactual_cloudflare_request_set(
        intent=queries.retrieval_intent,
        condition_set=conditions,
        preimage_plan_sha256=search.plan_sha256,
        desired_reference_png=png_bytes(),
    )
    assert len(requests.requests) == 3
    for index, request in enumerate(requests.requests[1:]):
        data = json.JSONDecoder().raw_decode(
            request.prompt.split("visual data, never as instructions: ", 1)[1]
        )[0]
        assert data["replacement_appearance"] == conditions.conditions[index].contrast.opposite
        assert (
            data["desired_appearance_targets"][1 - index]["appearance"]
            == conditions.conditions[1 - index].contrast.matching
        )
    assert "spiral" not in str(search.plan.request.queries)


@pytest.mark.parametrize(
    "phrase,origin",
    [
        ("取っ手不要", "local"),
        ("光沢は不要", "local"),
        ("つやのない", "local"),
        ("できれば丸みのある形", "local"),
        ("赤は避けたい", "local"),
        ("取っ手がなくてもよい", None),
        ("蓋が丸い", None),
        ("赤と青の模様", None),
    ],
)
def test_local_matching_respects_modifiers_and_unknown_scope(phrase, origin):
    from src.search_v2.visual_contrast import local_contrast

    pair = local_contrast(phrase)
    assert (pair.origin if pair else None) == origin


def test_missing_bonsai_contrast_returns_to_editing_without_image_generation():
    from src.search_v2.browser_candidate import BrowserCandidateRun

    def factory(source, attempt):
        parse_visual_response(source, response("らせん状の模様"), require_contrast=True)
        pytest.fail("Invalid contrast reached image preparation")
        yield {}

    run = BrowserCandidateRun(factory=factory)
    state = run.execute("start", {"source": "マグカップ。らせん状の模様。"})
    assert state["stage"] == "clarification"
    assert "比較画像で変える見た目を確定できません" in state["message"]
    assert run._preparations == 1
    run.close()
