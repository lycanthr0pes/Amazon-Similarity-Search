from __future__ import annotations

import pytest

from test_search_v2_orchestrator import (
    ACCOUNT_ID,
    CLOUDFLARE_TOKEN,
    SOURCE_INPUT,
    CloudflareTransport,
    backend_policy,
    cloudflare_responses,
    intent_review,
    module,
)
from src.search_v2.counterfactual_image import VisualConditionDraft
from src.search_v2.counterfactual_image import build_visual_condition_set


def conditions():
    return build_visual_condition_set(
        source_input=SOURCE_INPUT,
        drafts=(VisualConditionDraft(source_phrase="黒", strength="required"),),
    )


def test_initial_generation_stops_after_one_reference_image() -> None:
    stage, ledger, clock, _ = intent_review()
    transport = CloudflareTransport()
    reference = module().generate_images(
        stage,
        source_input=SOURCE_INPUT,
        condition_set=conditions(),
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=transport,
        now=clock,
    )
    assert reference.status == "reference_review"
    assert len(transport.calls) == 1
    assert reference.image is not None
    assert reference.usage_reservations[-1].amount.calls == 1


def test_reference_approval_generates_only_one_fake_once() -> None:
    m = module()
    stage, ledger, clock, _ = intent_review()
    transport = CloudflareTransport(cloudflare_responses() * 2)
    reference = m.generate_images(
        stage,
        source_input=SOURCE_INPUT,
        condition_set=conditions(),
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=transport,
        now=clock,
    )
    with pytest.raises(ValueError):
        m.approve_reference_image(
            reference,
            human_confirmed=False,
            policy=backend_policy(),
            usage_ledger=ledger,
            account_id=ACCOUNT_ID,
            api_token=CLOUDFLARE_TOKEN,
            transport=transport,
            now=clock,
        )
    assert len(transport.calls) == 1
    images = m.approve_reference_image(
        reference,
        human_confirmed=True,
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=transport,
        now=clock,
    )
    assert images.session.state == "image_review"
    assert len(transport.calls) == 2
    assert images.execution is None
    assert images.schema_version == "4.0"
    assert all(item.operation != "image_set" for item in ledger.snapshot().reservations)
    assert len(images.counterfactual_execution.images) == 2
    references = [call["request"].reference_image for call in transport.calls[1:]]
    assert all(image is not None for image in references)
    assert len({image.sha256 for image in references}) == 1
    with pytest.raises(ValueError):
        m.approve_reference_image(
            reference,
            human_confirmed=True,
            policy=backend_policy(),
            usage_ledger=ledger,
            account_id=ACCOUNT_ID,
            api_token=CLOUDFLARE_TOKEN,
            transport=transport,
            now=clock,
        )
    assert len(transport.calls) == 2


@pytest.mark.parametrize("condition_count", [1, 2, 3])
def test_reference_and_fake_call_limit_includes_both_approved_attempts(condition_count) -> None:
    m = module()
    stage, ledger, clock, _ = intent_review()
    condition_set = build_visual_condition_set(
        source_input=SOURCE_INPUT,
        drafts=tuple(
            VisualConditionDraft(source_phrase=phrase, strength="preferred")
            for phrase in ("黒い", "軽量", "ノイズキャンセリング")[:condition_count]
        ),
    )
    transport = CloudflareTransport(cloudflare_responses() * 2)
    reference = m.generate_images(
        stage,
        source_input=SOURCE_INPUT,
        condition_set=condition_set,
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=transport,
        now=clock,
    )
    for attempt in (1, 2):
        images = m.approve_reference_image(
            reference,
            human_confirmed=True,
            policy=backend_policy(),
            usage_ledger=ledger,
            account_id=ACCOUNT_ID,
            api_token=CLOUDFLARE_TOKEN,
            transport=transport,
            now=clock,
        )
        review = m.accept_images(
            images,
            postal_code="100-0001",
            policy=backend_policy(),
            usage_ledger=ledger,
            now=clock,
        )
        expected_calls = attempt * (1 + condition_count)
        assert len(transport.calls) == expected_calls
        assert sum(item.amount.calls for item in images.all_image_usage) == expected_calls
        allowance = next(x for x in review.plan.usage_allowances if x.provider == "cloudflare")
        assert allowance.calls == expected_calls
        assert review.plan.image_generation_profile == "reference_counterfactual"
        assert all(x.operation != "image_set" for x in ledger.snapshot().reservations)
        if attempt == 1:
            reference = m.regenerate_images(
                reference,
                policy=backend_policy(),
                usage_ledger=ledger,
                account_id=ACCOUNT_ID,
                api_token=CLOUDFLARE_TOKEN,
                transport=transport,
                now=clock,
            )
    with pytest.raises(ValueError):
        m.regenerate_images(
            reference,
            policy=backend_policy(),
            usage_ledger=ledger,
            account_id=ACCOUNT_ID,
            api_token=CLOUDFLARE_TOKEN,
            transport=transport,
            now=clock,
        )
    assert len(transport.calls) == 2 * (1 + condition_count)
