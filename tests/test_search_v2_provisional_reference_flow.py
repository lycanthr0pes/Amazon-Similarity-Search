from __future__ import annotations

from datetime import timedelta
import sqlite3

import pytest

import src.search_v2.provisional_orchestrator as provisional
from src.search_v2.provisional_approval_repository import CounterfactualApprovalConflictError
from src.search_v2.provisional_approval_repository import CounterfactualApprovalInputError
from src.search_v2.provisional_approval_repository import SqliteCounterfactualApprovalRepository
from test_search_v2_orchestrator import ACCOUNT_ID
from test_search_v2_orchestrator import CLOUDFLARE_TOKEN
from test_search_v2_orchestrator import SOURCE_INPUT
from test_search_v2_orchestrator import CloudflareTransport
from test_search_v2_orchestrator import backend_policy
from test_search_v2_orchestrator import cloudflare_responses
from test_search_v2_orchestrator import intent_review
from test_search_v2_orchestrator import module
from test_search_v2_orchestrator import reference_conditions


def initial_reference(transport=None):
    stage, ledger, clock, _ = intent_review()
    selected = (
        transport if transport is not None else CloudflareTransport(cloudflare_responses() * 2)
    )
    reference = provisional.generate_provisional_reference_review(
        stage,
        source_input=SOURCE_INPUT,
        condition_set=reference_conditions(),
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=selected,
        now=clock,
    )
    return reference, ledger, clock, selected


def completed_images(reference, ledger, clock, transport, repository, **overrides):
    execute = getattr(provisional, "generate_provisional_images", None)
    assert callable(execute), "provisional generation must wait for the initial image decision"
    arguments = {
        "human_confirmed": True,
        "policy": backend_policy(),
        "usage_ledger": ledger,
        "approval_repository": repository,
        "account_id": ACCOUNT_ID,
        "api_token": CLOUDFLARE_TOKEN,
        "transport": transport,
        "now": clock,
    }
    arguments.update(overrides)
    return execute(reference, **arguments)


def test_public_provisional_entry_stops_after_one_image() -> None:
    reference, _, _, transport = initial_reference()

    assert reference.status == "reference_review"
    assert len(transport.calls) == 1
    assert reference.image is not None
    assert not hasattr(reference, "approval_token")


@pytest.mark.parametrize("decision", ["denied", "expired", "replaced"])
def test_provisional_rejects_unapproved_reference_without_new_calls(tmp_path, decision) -> None:
    reference, ledger, clock, transport = initial_reference()
    repository = SqliteCounterfactualApprovalRepository(tmp_path / "review.sqlite3")
    overrides = {}
    if decision == "denied":
        overrides["human_confirmed"] = False
    elif decision == "expired":
        overrides["now"] = lambda: reference.expires_at + timedelta(seconds=1)
    else:
        module().regenerate_images(
            reference,
            policy=backend_policy(),
            usage_ledger=ledger,
            account_id=ACCOUNT_ID,
            api_token=CLOUDFLARE_TOKEN,
            transport=transport,
            now=clock,
        )
    calls_before = len(transport.calls)

    with pytest.raises(ValueError):
        completed_images(reference, ledger, clock, transport, repository, **overrides)

    assert len(transport.calls) == calls_before


def test_complete_provisional_images_reach_persistent_single_use_approval(tmp_path) -> None:
    reference, ledger, clock, transport = initial_reference()
    path = tmp_path / "review.sqlite3"
    repository = SqliteCounterfactualApprovalRepository(path)
    issued = completed_images(reference, ledger, clock, transport, repository)

    assert len(transport.calls) == 2
    assert issued.review.image_review.execution is None
    assert issued.review.execution.images[0] == reference.image
    assert issued.review.execution.usage_reservation.amount.calls == 1
    assert issued.review.approval_review.call_count == 2
    assert issued.approval_token.encode() not in path.read_bytes()
    reopened = SqliteCounterfactualApprovalRepository(path)
    approved = provisional.approve_provisional_reference_review(
        issued.review,
        approval_token=issued.approval_token,
        human_confirmed=True,
        approval_repository=reopened,
        now=clock,
    )

    assert len(approved.reference_images) == 2
    assert approved.cloudflare_reference_set_sha256 == issued.review.execution.reference_set_sha256
    assert len(transport.calls) == 2
    with pytest.raises(CounterfactualApprovalConflictError):
        provisional.approve_provisional_reference_review(
            issued.review,
            approval_token=issued.approval_token,
            human_confirmed=True,
            approval_repository=reopened,
            now=clock,
        )


def test_incomplete_provisional_generation_cannot_issue_final_approval(tmp_path) -> None:
    responses = cloudflare_responses()[:1] + [RuntimeError("failed")]
    reference, ledger, clock, transport = initial_reference(CloudflareTransport(responses))
    path = tmp_path / "review.sqlite3"
    repository = SqliteCounterfactualApprovalRepository(path)

    with pytest.raises(ValueError):
        completed_images(reference, ledger, clock, transport, repository)

    with sqlite3.connect(path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM counterfactual_approvals").fetchone()[0]
    assert count == 0
    assert len(transport.calls) == 2


def test_split_usage_approval_rejects_reference_from_another_plan(tmp_path) -> None:
    reference, ledger, clock, transport = initial_reference()
    repository = SqliteCounterfactualApprovalRepository(tmp_path / "review.sqlite3")
    issued = completed_images(reference, ledger, clock, transport, repository)
    reference_reservation = reference.usage_reservations[-1]
    request = reference_reservation.request.model_copy(update={"binding_sha256": "f" * 64})
    changed = reference_reservation.model_copy(update={"request": request})

    with pytest.raises(CounterfactualApprovalInputError):
        repository.issue(
            owner_id=reference.source_intent_review.session.owner_id,
            session_id=reference.source_intent_review.session.session_id,
            condition_set_sha256=issued.review.approval_review.condition_set_sha256,
            reference_set_sha256=issued.review.execution.reference_set_sha256,
            request_metadata_sha256=issued.review.execution.request_metadata_sha256,
            usage_reservation=issued.review.execution.usage_reservation,
            reference_image_reservation=changed,
            now=clock(),
        )


def test_provisional_final_approval_rejects_images_after_reference_replacement(tmp_path) -> None:
    reference, ledger, clock, transport = initial_reference()
    repository = SqliteCounterfactualApprovalRepository(tmp_path / "review.sqlite3")
    issued = completed_images(reference, ledger, clock, transport, repository)
    module().regenerate_images(
        reference,
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=transport,
        now=clock,
    )

    with pytest.raises(ValueError):
        provisional.approve_provisional_reference_review(
            issued.review,
            approval_token=issued.approval_token,
            human_confirmed=True,
            approval_repository=repository,
            now=clock,
        )

    assert len(transport.calls) == 3
