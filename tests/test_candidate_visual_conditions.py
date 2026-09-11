"""Existing source-grounded CLIP contracts receive Bonsai visual proposals."""

import hashlib
import importlib
import json

import pytest

from src.search_v2.candidate_queries import build_candidate_queries
from src.search_v2.candidate_search import prepare_candidate_search
from src.search_v2.counterfactual_image import VisualConditionSet
from tools.bonsai_response_log import write_private
import test_candidate_search as candidate


SOURCE = "椅子。丸みのある形。高級感のある見た目を希望。耐荷重100kg以上。"


class VisualBonsai:
    def __init__(self, root, conditions, status="ready"):
        self.root, self.conditions, self.status, self.calls = root, conditions, status, []

    def evaluate(self, request):
        self.calls.append(request)
        response = json.dumps(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {"status": self.status, "conditions": self.conditions}
                            )
                        },
                    }
                ]
            }
        ).encode()
        write_private(self.root / "visual-request.json", request)
        write_private(self.root / "visual-response.json", response)
        return response


def draft(phrase, strength="required", key=None):
    return {"source_phrase": phrase, "strength": strength, "attribute_key": key}


def prepare(tmp_path, source=SOURCE, conditions=None, status="ready"):
    bonsai = VisualBonsai(
        tmp_path,
        [draft("丸みのある形"), draft("高級感のある見た目を希望", "preferred")]
        if conditions is None
        else conditions,
        status,
    )
    service = prepare_candidate_search(
        source,
        owner_id="owner-1",
        session_id="visual-1",
        postal_code="100-0001",
        normalization_profile=candidate.flow.backend_policy().normalization_profile,
        now=candidate.flow.NOW,
        visual_extractor=bonsai,
    )
    return service, bonsai


def test_bonsai_visual_conditions_feed_existing_clip_contract_and_sudachi(tmp_path):
    service, bonsai = prepare(tmp_path)
    plan = service.plan
    assert isinstance(plan.visual_conditions, VisualConditionSet)
    assert len(bonsai.calls) == 1
    assert [c.source_phrase for c in plan.visual_conditions.conditions] == [
        "丸みのある形",
        "高級感のある見た目を希望",
    ]
    assert [c.strength for c in plan.visual_conditions.conditions] == ["required", "preferred"]
    assert "丸みのある形" in plan.image_prompt
    assert "高級感のある見た目" in plan.image_prompt
    assert "100kg" not in plan.image_prompt
    assert "耐荷重" in plan.request.queries[0].value
    assert plan.visual_request_sha256 == hashlib.sha256(bonsai.calls[0]).hexdigest()
    queries = build_candidate_queries(SOURCE, visual_conditions=plan.visual_conditions)
    assert queries.query_plan == plan.query_plan
    from src.search_v2.counterfactual_cloudflare_request import (
        build_counterfactual_cloudflare_desired_request,
        build_counterfactual_cloudflare_request_set,
    )
    from test_search_v2_counterfactual_cloudflare_request import png_bytes

    reference = build_counterfactual_cloudflare_desired_request(
        intent=queries.retrieval_intent,
        condition_set=plan.visual_conditions,
        preimage_plan_sha256=service.plan_sha256,
    )
    assert reference.condition_set_sha256
    requests = build_counterfactual_cloudflare_request_set(
        intent=queries.retrieval_intent,
        condition_set=plan.visual_conditions,
        preimage_plan_sha256=service.plan_sha256,
        desired_reference_png=png_bytes(),
    )
    assert requests.call_count == 3
    write_private(tmp_path / "plan.json", plan.model_dump_json().encode())
    with pytest.raises(ValueError):
        service.rank(owner_id="owner-1", now=candidate.flow.NOW)
    review, _ = candidate.retrieve(
        service, tmp_path, [{"name": "椅子", "features": ["耐荷重: 120kg"]}]
    )
    service.confirm(
        owner_id="owner-1", review_sha256=review.sha256, selections={}, now=candidate.flow.NOW
    )
    result = service.rank(owner_id="owner-1", now=candidate.flow.NOW)
    assert result.visual_evaluation_status == "pending"
    assert result.retrieval_plan.visual_conditions == plan.visual_conditions
    assert result.products[0].evaluation.required_status == "confirmed"


@pytest.mark.parametrize(
    "conditions",
    [
        [draft("木目調")],
        [draft("100kg以上")],
        [draft("耐荷重100kg以上")],
        [draft("高級感のある見た目", "preferred")],
        [draft("高級感のある見た目を希望", "required")],
        [draft("丸みのある形", key="dimensions.width")],
        [draft("丸みのある形"), draft("丸みのある形")],
        [draft("丸みのある形")] * 4,
    ],
)
def test_fabricated_partial_nonvisual_or_wrong_strength_proposals_fail(tmp_path, conditions):
    with pytest.raises(ValueError):
        prepare(tmp_path, conditions=conditions)


def test_abstention_does_not_become_an_empty_success(tmp_path):
    with pytest.raises(ValueError):
        prepare(tmp_path, conditions=[], status="needs_clarification")


def test_no_visual_conditions_preserves_existing_path(tmp_path):
    service, _ = prepare(tmp_path, source="スキャナー。600dpi以上。", conditions=[])
    assert service.plan.visual_conditions is None
    assert service.plan.pending_quotes == ("600dpi以上",)


def test_visual_conditions_cannot_move_to_another_source(tmp_path):
    service, _ = prepare(tmp_path)
    with pytest.raises(ValueError):
        build_candidate_queries(
            "机。丸みのある形。", visual_conditions=service.plan.visual_conditions
        )


def test_excluded_visual_phrase_is_preserved_in_prompt(tmp_path):
    service, _ = prepare(
        tmp_path, source="机。木目調を除外。", conditions=[draft("木目調を除外", "excluded")]
    )
    assert "木目調を除外" in service.plan.image_prompt
    assert service.plan.visual_conditions.conditions[0].strength == "excluded"


def test_parser_rejects_unknown_fields_and_bad_envelopes(tmp_path):
    m = importlib.import_module("src.search_v2.bonsai_visual_conditions")
    for i, response in enumerate(
        [b"{}", b"not-json", b'{"choices":[]}', b'{"choices":[],"choices":[]}']
    ):
        write_private(tmp_path / f"malformed-{i}.json", response)
        with pytest.raises(ValueError):
            m.parse_visual_response(SOURCE, response)


def test_common_visual_fact_remains_a_typed_condition(tmp_path):
    service, _ = prepare(
        tmp_path,
        source="椅子。白。耐荷重100kg以上。",
        conditions=[draft("白", key="appearance.color")],
    )
    queries = build_candidate_queries(
        "椅子。白。耐荷重100kg以上。", visual_conditions=service.plan.visual_conditions
    )
    assert {f.key for f in queries.facts} == {"custom", "appearance.color"}
    assert "白" in service.plan.request.queries[0].value


def test_visual_review_is_bound_to_retrieval_approval(tmp_path):
    service, _ = prepare(tmp_path)
    old_hash = service.plan_sha256
    # Mutating a detached projection cannot change the server-owned proposal.
    service.plan.query_plan.queries.clear()
    assert service.plan_sha256 == old_hash
    transport = candidate.ProductTransport([{"name": "椅子"}], tmp_path)
    with pytest.raises(ValueError):
        service.approve_and_fetch(
            owner_id="owner-1", plan_sha256="0" * 64, transport=transport, now=candidate.flow.NOW
        )
    assert not transport.calls


@pytest.mark.parametrize(
    "source,phrase",
    [
        ("マグ。食洗機対応。", "食洗機対応"),
        ("机。幅100mm以下。", "幅100mm以下"),
        ("椅子。丸みのある形ではない。", "丸みのある形"),
    ],
)
def test_performance_and_cropped_negation_never_move_to_clip(tmp_path, source, phrase):
    with pytest.raises(ValueError):
        prepare(tmp_path, source=source, conditions=[draft(phrase)])


def test_provider_failure_does_not_fall_back_to_no_visual_conditions():
    class Failing:
        def evaluate(self, request):
            raise RuntimeError("private provider diagnostic")

    with pytest.raises(ValueError, match="^Candidate visual extraction failed$"):
        prepare_candidate_search(
            "椅子",
            owner_id="owner-1",
            session_id="visual-1",
            postal_code="100-0001",
            normalization_profile=candidate.flow.backend_policy().normalization_profile,
            now=candidate.flow.NOW,
            visual_extractor=Failing(),
        )


def test_visual_extraction_cannot_erase_alternative_relationship(tmp_path):
    with pytest.raises(ValueError):
        prepare(
            tmp_path,
            source="椅子。高級感または素朴な印象。",
            conditions=[draft("高級感または素朴な印象")],
        )
