from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest
from pydantic import ValidationError

from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import ProviderUsageLimits
from src.search_v2.usage_ledger import UsageAmount
from src.search_v2.usage_ledger import UsageLedgerError
from src.search_v2.usage_ledger import UsageLedgerSnapshot
from src.search_v2.usage_ledger import UsageLimitExceeded
from src.search_v2.usage_ledger import UsageReservationRequest
from src.search_v2.usage_ledger import build_no_quota_usage_policies
from src.search_v2.usage_ledger import usage_policy_sha256


NOW = datetime(2026, 9, 2, 3, 0, tzinfo=timezone.utc)


def amount(*, calls: int, tokens: int = 0, cost_microusd: int = 0) -> UsageAmount:
    return UsageAmount(calls=calls, tokens=tokens, cost_microusd=cost_microusd)


def policy(
    *,
    provider: str = "cloudflare",
    per_user_day_calls: int = 8,
    per_session_calls: int = 8,
    global_day_calls: int = 8,
) -> ProviderUsageLimits:
    return ProviderUsageLimits(
        provider=provider,
        pricing_policy_sha256={
            "bonsai": "a" * 64,
            "cloudflare": "b" * 64,
            "outscraper": "c" * 64,
        }[provider],
        per_user_day=amount(
            calls=per_user_day_calls,
            tokens=100_000,
            cost_microusd=1_000_000,
        ),
        per_session=amount(
            calls=per_session_calls,
            tokens=100_000,
            cost_microusd=1_000_000,
        ),
        global_day=amount(
            calls=global_day_calls,
            tokens=1_000_000,
            cost_microusd=10_000_000,
        ),
    )


def request(
    *,
    owner_id: str = "owner-1",
    session_id: str = "session-1",
    calls: int = 1,
    tokens: int = 0,
    cost_microusd: int = 1_000,
) -> UsageReservationRequest:
    return UsageReservationRequest(
        provider="cloudflare",
        operation="image_set",
        owner_id=owner_id,
        session_id=session_id,
        binding_sha256="d" * 64,
        amount=amount(calls=calls, tokens=tokens, cost_microusd=cost_microusd),
        pricing_policy_sha256="b" * 64,
    )


def test_usage_models_are_strict_and_policy_digest_is_deterministic() -> None:
    limits = policy()

    assert usage_policy_sha256([limits]) == usage_policy_sha256([limits])
    assert "requested_at" not in UsageReservationRequest.model_json_schema()["properties"]

    with pytest.raises(ValidationError, match="int_type"):
        UsageAmount(calls=True, tokens=0, cost_microusd=0)

    payload = limits.model_dump(mode="python")
    payload["unexpected"] = True
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ProviderUsageLimits.model_validate(payload)


def test_usage_policy_rejects_duplicate_provider_entries() -> None:
    with pytest.raises(UsageLedgerError, match="one policy per provider"):
        InMemoryUsageLedger([policy(), policy()])


def test_reservation_can_be_released_only_before_an_attempt_starts() -> None:
    ledger = InMemoryUsageLedger([policy(per_session_calls=4)])
    reserved = ledger.reserve(request(calls=4, cost_microusd=4_000), now=NOW)

    assert reserved.status == "reserved"
    assert reserved.reserved_at == NOW

    released = ledger.release(
        reserved.reservation_id,
        owner_id="owner-1",
        session_id="session-1",
        now=NOW + timedelta(seconds=1),
    )
    assert released.status == "released"

    replacement = ledger.reserve(
        request(calls=4, cost_microusd=4_000),
        now=NOW + timedelta(seconds=2),
    )
    started = ledger.start(
        replacement.reservation_id,
        owner_id="owner-1",
        session_id="session-1",
        now=NOW + timedelta(seconds=3),
    )
    assert started.status == "started"

    with pytest.raises(UsageLedgerError, match="started reservation cannot be released"):
        ledger.release(
            replacement.reservation_id,
            owner_id="owner-1",
            session_id="session-1",
            now=NOW + timedelta(seconds=4),
        )


def test_failed_attempt_remains_charged_and_survives_snapshot_restore() -> None:
    limits = policy(per_session_calls=1, per_user_day_calls=1, global_day_calls=1)
    ledger = InMemoryUsageLedger([limits])
    reserved = ledger.reserve(request(), now=NOW)
    ledger.start(
        reserved.reservation_id,
        owner_id="owner-1",
        session_id="session-1",
        now=NOW + timedelta(seconds=1),
    )
    failed = ledger.finish(
        reserved.reservation_id,
        owner_id="owner-1",
        session_id="session-1",
        success=False,
        now=NOW + timedelta(seconds=2),
    )

    assert failed.status == "failed"

    restored = InMemoryUsageLedger.from_snapshot(ledger.snapshot())
    with pytest.raises(UsageLimitExceeded):
        restored.reserve(request(), now=NOW + timedelta(seconds=3))


def test_snapshot_restore_rejects_policy_tampering_and_aggregate_overage() -> None:
    limits = policy(per_session_calls=1, per_user_day_calls=1, global_day_calls=1)
    ledger = InMemoryUsageLedger([limits])
    reservation = ledger.reserve(request(), now=NOW)
    snapshot = ledger.snapshot()

    tampered_policy = reservation.model_copy(update={"usage_policy_sha256": "f" * 64})
    tampered_snapshot = snapshot.model_copy(update={"reservations": [tampered_policy]})
    with pytest.raises(UsageLedgerError, match="snapshot is invalid"):
        InMemoryUsageLedger.from_snapshot(tampered_snapshot)

    duplicate_charge = reservation.model_copy(
        update={
            "reservation_id": "Z" * 32,
            "reserved_at": NOW + timedelta(seconds=1),
        }
    )
    over_limit_snapshot = UsageLedgerSnapshot(
        schema_version="2.0",
        policies=[limits],
        reservations=[reservation, duplicate_charge],
    )
    with pytest.raises(UsageLedgerError, match="exceeds an approved limit"):
        InMemoryUsageLedger.from_snapshot(over_limit_snapshot)


def test_ledger_enforces_session_user_day_and_global_day_limits() -> None:
    limits = policy(
        per_session_calls=2,
        per_user_day_calls=3,
        global_day_calls=4,
    )
    ledger = InMemoryUsageLedger([limits])

    ledger.reserve(request(calls=2), now=NOW)
    with pytest.raises(UsageLimitExceeded):
        ledger.reserve(request(calls=1), now=NOW + timedelta(seconds=1))

    ledger.reserve(
        request(session_id="session-2", calls=1),
        now=NOW + timedelta(seconds=2),
    )
    with pytest.raises(UsageLimitExceeded):
        ledger.reserve(
            request(session_id="session-3", calls=1),
            now=NOW + timedelta(seconds=3),
        )

    ledger.reserve(
        request(owner_id="owner-2", session_id="session-4", calls=1),
        now=NOW + timedelta(seconds=4),
    )
    with pytest.raises(UsageLimitExceeded):
        ledger.reserve(
            request(owner_id="owner-3", session_id="session-5", calls=1),
            now=NOW + timedelta(seconds=5),
        )


def test_new_utc_day_resets_day_scopes_but_not_session_scope() -> None:
    limits = policy(
        per_session_calls=2,
        per_user_day_calls=1,
        global_day_calls=1,
    )
    ledger = InMemoryUsageLedger([limits])
    ledger.reserve(request(), now=NOW)

    next_day = NOW + timedelta(days=1)
    ledger.reserve(request(session_id="session-2"), now=next_day)

    with pytest.raises(UsageLimitExceeded):
        ledger.reserve(
            request(session_id="session-2"),
            now=next_day + timedelta(seconds=1),
        )


def test_reservation_requires_matching_policy_digest_and_utc_timestamp() -> None:
    ledger = InMemoryUsageLedger([policy()])
    mismatched = request().model_copy(update={"pricing_policy_sha256": "e" * 64})

    with pytest.raises(UsageLedgerError, match="pricing policy"):
        ledger.reserve(mismatched, now=NOW)

    with pytest.raises(ValueError, match="UTC"):
        ledger.reserve(request(), now=NOW.replace(tzinfo=None))


def test_reservation_owner_and_session_are_checked_for_lifecycle_updates() -> None:
    ledger = InMemoryUsageLedger([policy()])
    reserved = ledger.reserve(request(), now=NOW)

    with pytest.raises(UsageLedgerError, match="reservation owner or session"):
        ledger.start(
            reserved.reservation_id,
            owner_id="owner-2",
            session_id="session-1",
            now=NOW + timedelta(seconds=1),
        )


def test_concurrent_reservations_cannot_bypass_the_limit() -> None:
    limits = policy(per_session_calls=1, per_user_day_calls=1, global_day_calls=1)
    ledger = InMemoryUsageLedger([limits])

    def reserve_once(offset: int) -> str:
        try:
            reservation = ledger.reserve(
                request(),
                now=NOW + timedelta(microseconds=offset),
            )
        except UsageLimitExceeded:
            return "rejected"
        return reservation.status

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve_once, (1, 2)))

    assert sorted(results) == ["rejected", "reserved"]
    assert len(ledger.snapshot().reservations) == 1


def test_no_quota_policy_records_attempts_without_user_session_day_or_cost_rejection() -> None:
    policies = build_no_quota_usage_policies(
        bonsai_pricing_policy_sha256="a" * 64,
        cloudflare_pricing_policy_sha256="b" * 64,
        outscraper_pricing_policy_sha256="c" * 64,
    )
    cloudflare = next(item for item in policies if item.provider == "cloudflare")
    ledger = InMemoryUsageLedger(policies)

    assert cloudflare.quota_enforcement == "disabled"
    assert cloudflare.per_user_day.is_zero
    assert cloudflare.per_session.is_zero
    assert cloudflare.global_day.is_zero

    first = ledger.reserve(
        request(calls=8, tokens=100_000, cost_microusd=1_000_000),
        now=NOW,
    )
    second = ledger.reserve(
        request(calls=8, tokens=100_000, cost_microusd=1_000_000),
        now=NOW + timedelta(seconds=1),
    )

    assert first.status == "reserved"
    assert second.status == "reserved"
    assert len(ledger.snapshot().reservations) == 2
