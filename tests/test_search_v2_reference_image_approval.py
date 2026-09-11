from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from test_search_v2_orchestrator import (
    ACCOUNT_ID,
    CLOUDFLARE_TOKEN,
    SOURCE_INPUT,
    CloudflareTransport,
    approve_reference,
    backend_policy,
    cloudflare_responses,
    intent_review,
    module,
    reference_conditions,
)
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import UsageLedgerError


def reference_context():
    stage, ledger, clock, _ = intent_review()
    reference = module().generate_images(
        stage,
        source_input=SOURCE_INPUT,
        condition_set=reference_conditions(),
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=CloudflareTransport(),
        now=clock,
    )
    return reference, ledger, clock


def regenerate(reference, ledger, clock):
    return module().regenerate_images(
        reference,
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=CloudflareTransport(),
        now=clock,
    )


def test_regeneration_invalidates_previous_reference_and_approved_outputs() -> None:
    m = module()
    reference, ledger, clock = reference_context()
    first_images = approve_reference(reference, ledger, clock)
    stale_search_review = m.accept_images(
        first_images,
        postal_code="100-0001",
        policy=backend_policy(),
        usage_ledger=ledger,
        now=clock,
    )
    replacement = regenerate(reference, ledger, clock)
    transport = CloudflareTransport([])
    with pytest.raises(ValueError):
        approve_reference(reference, ledger, clock, transport)
    with pytest.raises(ValueError):
        m.accept_images(
            first_images,
            postal_code="100-0001",
            policy=backend_policy(),
            usage_ledger=ledger,
            now=clock,
        )
    with pytest.raises(ValueError):
        m.approve_search(stale_search_review, now=clock)
    assert transport.calls == []
    second_images = approve_reference(replacement, ledger, clock)
    search_review = m.accept_images(
        second_images,
        postal_code="100-0001",
        policy=backend_policy(),
        usage_ledger=ledger,
        now=clock,
    )
    assert (
        next(
            item.calls
            for item in search_review.plan.usage_allowances
            if item.provider == "cloudflare"
        )
        == 4
    )
    assert sum(item.amount.calls for item in second_images.all_image_usage) == 4


def test_discarded_reference_cannot_generate_derived_images() -> None:
    reference, ledger, clock = reference_context()
    module().skip_images(
        reference,
        postal_code="100-0001",
        policy=backend_policy(),
        usage_ledger=ledger,
        now=clock,
    )
    transport = CloudflareTransport([])
    with pytest.raises(ValueError):
        approve_reference(reference, ledger, clock, transport)
    assert transport.calls == []


def test_expired_reference_is_rejected_before_new_reservation() -> None:
    reference, ledger, _ = reference_context()
    before = ledger.snapshot()
    transport = CloudflareTransport([])
    with pytest.raises(ValueError):
        approve_reference(reference, ledger, lambda: reference.expires_at, transport)
    assert ledger.snapshot() == before
    assert transport.calls == []


def test_parallel_approvals_only_generate_one_derived_batch() -> None:
    reference, ledger, clock = reference_context()
    transport = CloudflareTransport(cloudflare_responses() * 2)
    fixed_time = clock()

    def approve():
        try:
            return approve_reference(reference, ledger, lambda: fixed_time, transport)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: approve(), range(2)))
    assert sum(item is not None for item in results) == 1
    assert len(transport.calls) == 1


def test_search_rejects_missing_reference_usage_before_outscraper() -> None:
    reference, ledger, clock = reference_context()
    images = approve_reference(reference, ledger, clock)
    review = module().accept_images(
        images,
        postal_code="100-0001",
        policy=backend_policy(),
        usage_ledger=ledger,
        now=clock,
    )
    snapshot = ledger.snapshot()
    stripped = InMemoryUsageLedger.from_snapshot(
        snapshot.model_copy(
            update={
                "reservations": [
                    item
                    for item in snapshot.reservations
                    if item.operation not in {"reference_image", "counterfactual_images"}
                ],
            }
        )
    )
    with pytest.raises(ValueError):
        module()._validate_plan_ledger(review, stripped)


def test_failed_counterfactual_cannot_replay_and_preserves_usage_after_regeneration() -> None:
    reference, ledger, clock = reference_context()
    transport = CloudflareTransport([RuntimeError("raw provider detail")])
    with pytest.raises(ValueError, match="derived image generation failed"):
        approve_reference(reference, ledger, clock, transport)
    assert len(transport.calls) == 1
    with pytest.raises(ValueError):
        approve_reference(reference, ledger, clock, transport)
    replacement = regenerate(reference, ledger, clock)
    assert [item.status for item in replacement.prior_derived_usage] == ["failed"]
    completed = approve_reference(replacement, ledger, clock)
    assert sum(item.amount.calls for item in completed.all_image_usage) == 4


def test_failed_counterfactual_can_continue_without_images() -> None:
    reference, ledger, clock = reference_context()
    transport = CloudflareTransport([RuntimeError("raw detail")])
    with pytest.raises(ValueError):
        approve_reference(reference, ledger, clock, transport)
    review = module().skip_images(
        reference,
        postal_code="100-0001",
        policy=backend_policy(),
        usage_ledger=ledger,
        now=clock,
    )
    assert review.plan.image_mode == "off"
    assert (
        sum(
            item.amount.calls
            for item in ledger.snapshot().reservations
            if item.provider == "cloudflare"
        )
        == 2
    )
    assert len(transport.calls) == 1


def test_reference_reservation_failure_can_retry_without_provider_call(monkeypatch) -> None:
    stage, ledger, clock, _ = intent_review()
    original_reserve = ledger.reserve
    transport = CloudflareTransport()

    def unavailable(*args, **kwargs):
        raise UsageLedgerError("reservation unavailable")

    monkeypatch.setattr(ledger, "reserve", unavailable)
    kwargs = dict(
        source_input=SOURCE_INPUT,
        condition_set=reference_conditions(),
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=transport,
        now=clock,
    )
    with pytest.raises(UsageLedgerError):
        module().generate_images(stage, **kwargs)
    assert transport.calls == []
    monkeypatch.setattr(ledger, "reserve", original_reserve)
    result = module().generate_images(stage, **kwargs)
    assert result.status == "reference_review"
    assert len(transport.calls) == 1
