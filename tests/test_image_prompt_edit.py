"""Prompt edits stay bound to the generated images, without preparing conditions again."""

import pytest
import test_candidate_connected_flow as connected
from src.search_v2.counterfactual_cloudflare_request import (
    build_counterfactual_cloudflare_desired_request,
    build_counterfactual_cloudflare_request_set,
    CounterfactualCloudflareRequest,
)
from test_search_v2_counterfactual_cloudflare_request import (
    normalized_intent,
    conditions,
    png_bytes,
)


def test_new_requests_use_9b_and_old_4b_metadata_remains_readable():
    request = build_counterfactual_cloudflare_desired_request(
        intent=normalized_intent(),
        condition_set=conditions(),
        preimage_plan_sha256="a" * 64,
    )
    assert request.model_id.endswith("klein-9b")
    old = request.model_dump(mode="json")
    old["model_id"] = "@cf/black-forest-labs/flux-2-klein-4b"
    assert CounterfactualCloudflareRequest.model_validate(old).model_dump(mode="json") == old


def test_override_prompts_and_comparison_nonce_are_bound_to_requests():
    kwargs = dict(
        intent=normalized_intent(),
        condition_set=conditions(),
        preimage_plan_sha256="a" * 64,
        desired_reference_png=png_bytes(),
    )
    original = build_counterfactual_cloudflare_request_set(**kwargs)
    edited = build_counterfactual_cloudflare_request_set(
        **kwargs,
        reference_prompt="A reference edited by the user.",
        comparison_prompts={"visual-condition-001": "An edited comparison."},
        comparison_nonce="b" * 64,
    )
    assert edited.requests[0].prompt == "A reference edited by the user."
    assert edited.requests[1].prompt == "An edited comparison."
    assert edited.requests[2].prompt == original.requests[2].prompt
    assert edited.requests[1].seed != original.requests[1].seed
    assert edited.requests[0].seed == original.requests[0].seed
    assert "generation_nonce" not in original.requests[0].model_dump(mode="json")


@pytest.mark.parametrize(
    "value",
    ["", " " * 4, "x" * 12001, "bad\x00prompt", "https://example.com"],
    ids=["empty", "blank", "too-long", "control", "url"],
)
def test_invalid_edits_do_not_start_generation(tmp_path, value):
    flow, transport, ledger, _, _ = connected.start(tmp_path, plan_lifetime=None)
    with pytest.raises(ValueError):
        flow.generate_reference(
            owner_id=connected.OWNER,
            plan_sha256=flow.plan_sha256,
            human_confirmed=True,
            prompt=value,
        )
    assert flow._state == "planned" and flow._attempt == 0
    assert not transport.calls and not ledger.snapshot().reservations


def test_comparison_edit_reuses_reference_and_invalidates_previous_approval(tmp_path):
    flow, transport, _, _, _ = connected.start(tmp_path, plan_lifetime=None)
    plan = flow.plan_sha256
    reference = flow.generate_reference(
        owner_id=connected.OWNER,
        plan_sha256=plan,
        human_confirmed=True,
        prompt="A custom reference.",
    )
    first = flow.approve_reference(
        owner_id=connected.OWNER,
        reference_sha256=reference.sha256,
        human_confirmed=True,
        prompts={"visual-condition-001": "First comparison."},
    )
    old_request = transport.calls[-1]["request"]
    second = flow.regenerate_comparisons(
        owner_id=connected.OWNER,
        plan_sha256=plan,
        human_confirmed=True,
        prompts={"visual-condition-001": "Second comparison."},
    )
    assert len(transport.calls) == 3
    assert transport.calls[-1]["request"].target == "counterfactual"
    assert transport.calls[-1]["request"].reference_image == old_request.reference_image
    assert transport.calls[-1]["request"].seed != old_request.seed
    assert flow.plan_sha256 == plan
    assert flow.image_prompts["reference"] == "A custom reference."
    assert flow.image_prompts["comparison"]["visual-condition-001"] == "Second comparison."
    with pytest.raises(ValueError):
        flow.approve_images(
            owner_id=connected.OWNER,
            approval_id=first.review.approval_id,
            token=first.token,
            human_confirmed=True,
        )
    flow.approve_images(
        owner_id=connected.OWNER,
        approval_id=second.review.approval_id,
        token=second.token,
        human_confirmed=True,
    )


def test_request_set_cannot_mix_old_and_new_image_models():
    from src.search_v2.counterfactual_cloudflare_request import CounterfactualCloudflareRequestSet

    requests = build_counterfactual_cloudflare_request_set(
        intent=normalized_intent(),
        condition_set=conditions(),
        preimage_plan_sha256="a" * 64,
        desired_reference_png=png_bytes(),
    )
    CounterfactualCloudflareRequestSet.model_validate(requests)
    mixed = requests.model_copy(
        update={
            "requests": (
                requests.requests[0],
                requests.requests[1].model_copy(
                    update={"model_id": "@cf/black-forest-labs/flux-2-klein-4b"}
                ),
                *requests.requests[2:],
            )
        }
    )
    with pytest.raises(ValueError):
        CounterfactualCloudflareRequestSet.model_validate(mixed)
