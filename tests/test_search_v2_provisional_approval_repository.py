from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import threading

import pytest

from src.search_v2.provisional_approval_repository import (
    CounterfactualApprovalConflictError,
)
from src.search_v2.provisional_approval_repository import (
    SqliteCounterfactualApprovalRepository,
)
from src.search_v2.usage_ledger import UsageAmount
from src.search_v2.usage_ledger import UsageReservation
from src.search_v2.usage_ledger import UsageReservationRequest


NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
TOKEN = "A" * 43


def succeeded_reservation() -> UsageReservation:
    return UsageReservation(
        reservation_id="reference-reservation-000000000001",
        request=UsageReservationRequest(
            provider="cloudflare",
            operation="counterfactual_reference_set",
            owner_id="owner-1",
            session_id="session-1",
            binding_sha256="a" * 64,
            amount=UsageAmount(calls=3, tokens=0, cost_microusd=3_000),
            pricing_policy_sha256="b" * 64,
        ),
        usage_policy_sha256="c" * 64,
        status="succeeded",
        reserved_at=NOW,
        started_at=NOW + timedelta(seconds=1),
        finished_at=NOW + timedelta(seconds=2),
    )


def test_approval_is_persistent_single_use_and_does_not_store_the_raw_token(tmp_path) -> None:
    path = tmp_path / "counterfactual-approval.sqlite3"
    repository = SqliteCounterfactualApprovalRepository(path)
    issued = repository.issue(
        owner_id="owner-1",
        session_id="session-1",
        condition_set_sha256="d" * 64,
        reference_set_sha256="e" * 64,
        request_metadata_sha256="f" * 64,
        usage_reservation=succeeded_reservation(),
        now=NOW + timedelta(seconds=3),
        token_factory=lambda: TOKEN,
    )

    assert issued.token == TOKEN
    assert TOKEN.encode() not in path.read_bytes()

    reopened = SqliteCounterfactualApprovalRepository(path)
    receipt = reopened.consume(
        review=issued.review,
        token=TOKEN,
        human_confirmed=True,
        now=NOW + timedelta(seconds=4),
    )

    assert receipt.consumed_at == NOW + timedelta(seconds=4)
    assert receipt.reference_set_sha256 == "e" * 64
    with pytest.raises(CounterfactualApprovalConflictError, match="already been consumed"):
        reopened.consume(
            review=issued.review,
            token=TOKEN,
            human_confirmed=True,
            now=NOW + timedelta(seconds=5),
        )


def test_approval_rejects_owner_binding_changes_and_unknown_schema(tmp_path) -> None:
    path = tmp_path / "counterfactual-approval.sqlite3"
    repository = SqliteCounterfactualApprovalRepository(path)
    issued = repository.issue(
        owner_id="owner-1",
        session_id="session-1",
        condition_set_sha256="d" * 64,
        reference_set_sha256="e" * 64,
        request_metadata_sha256="f" * 64,
        usage_reservation=succeeded_reservation(),
        now=NOW + timedelta(seconds=3),
        token_factory=lambda: TOKEN,
    )

    changed = issued.review.model_copy(update={"owner_id": "owner-2"})
    with pytest.raises(CounterfactualApprovalConflictError):
        repository.consume(
            review=changed,
            token=TOKEN,
            human_confirmed=True,
            now=NOW + timedelta(seconds=4),
        )

    other = tmp_path / "unknown.sqlite3"
    connection = sqlite3.connect(other)
    connection.execute("PRAGMA user_version = 2")
    connection.close()
    with pytest.raises(Exception, match="storage"):
        SqliteCounterfactualApprovalRepository(other)


def test_parallel_approval_consumers_allow_exactly_one_claim(tmp_path) -> None:
    repository = SqliteCounterfactualApprovalRepository(
        tmp_path / "counterfactual-approval.sqlite3"
    )
    issued = repository.issue(
        owner_id="owner-1",
        session_id="session-1",
        condition_set_sha256="d" * 64,
        reference_set_sha256="e" * 64,
        request_metadata_sha256="f" * 64,
        usage_reservation=succeeded_reservation(),
        now=NOW + timedelta(seconds=3),
        token_factory=lambda: TOKEN,
    )
    barrier = threading.Barrier(2)

    def consume() -> str:
        barrier.wait()
        try:
            repository.consume(
                review=issued.review,
                token=TOKEN,
                human_confirmed=True,
                now=NOW + timedelta(seconds=4),
            )
            return "consumed"
        except CounterfactualApprovalConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(lambda _index: consume(), range(2)))

    assert sorted(outcomes) == ["conflict", "consumed"]
