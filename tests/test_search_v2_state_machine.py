from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest
from pydantic import ValidationError

from src.search_v2.approval import ApprovedUsage
from src.search_v2.approval import SearchRuntimeBindings
from src.search_v2.approval import build_search_approval_plan
from src.search_v2.approval import search_approval_plan_sha256
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent
from src.search_v2.intent import search_intent_sha256
from src.search_v2.product_evidence import product_evidence_profile_sha256
from src.search_v2.query_planner import build_search_query_plan
from src.search_v2.query_planner import search_query_plan_sha256
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_intent_adapter import typed_requirement_proposal_sha256
from src.search_v2.typed_ranking import typed_ranking_profile_sha256
from src.search_v2.state_machine import SearchApprovalGrant
from src.search_v2.state_machine import InMemoryApprovalLedger
from src.search_v2.state_machine import SearchSessionSnapshot
from src.search_v2.state_machine import SearchStateError
from src.search_v2.state_machine import approve_image_review
from src.search_v2.state_machine import approve_intent_review
from src.search_v2.state_machine import consume_search_approval
from src.search_v2.state_machine import create_search_session
from src.search_v2.state_machine import issue_search_approval
from src.search_v2.state_machine import record_image_set
from src.search_v2.state_machine import record_intent_plan
from src.search_v2.state_machine import replace_intent_plan
from src.search_v2.state_machine import request_image_regeneration
from src.search_v2.state_machine import start_intent_processing
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import ProviderUsageLimits
from src.search_v2.usage_ledger import UsageAmount
from src.search_v2.usage_ledger import UsageReservation
from src.search_v2.usage_ledger import UsageReservationRequest
from src.search_v2.usage_ledger import usage_policy_sha256


NOW = datetime(2026, 9, 2, 5, 0, tzinfo=timezone.utc)


def normalized_intent(
    *,
    preferred_term: str = "軽量",
    typed_conditions: list[dict[str, object]] | None = None,
    blocking: bool = False,
):
    payload = {
        "product_name_ja": "ヘッドホン",
        "product_name_en": "headphones",
        "category_ja": "オーディオ",
        "category_en": "audio",
        "required_terms_ja": ["ワイヤレス"],
        "required_terms_en": ["wireless"],
        "preferred_terms_ja": [preferred_term],
        "preferred_terms_en": ["lightweight"],
        "negative_terms_ja": ["中古"],
        "negative_terms_en": ["used"],
        "color_ja": "黒",
        "color_en": "black",
        "features_ja": ["ノイズキャンセリング"],
        "features_en": ["noise cancelling"],
        "brand": "Sony",
        "model_number": "WH-1000XM5",
        "price": {
            "currency": "JPY",
            "mode": "max",
            "target_jpy": None,
            "min_jpy": None,
            "max_jpy": 50_000,
            "source": "explicit",
            "confidence": None,
        },
        "typed_conditions": [] if typed_conditions is None else typed_conditions,
        "ambiguities": [],
    }
    if blocking:
        payload.update(
            {
                "product_name_ja": None,
                "product_name_en": None,
                "category_ja": None,
                "category_en": None,
                "required_terms_ja": [],
                "required_terms_en": [],
                "preferred_terms_ja": [],
                "preferred_terms_en": [],
                "brand": None,
                "model_number": None,
                "ambiguities": [
                    {
                        "code": "product_type_unknown",
                        "message": "商品種別を確認してください",
                        "blocking": True,
                    }
                ],
            }
        )
    source_input = "Sony WH-1000XM5を5万円以内で"
    provenance = build_intent_provenance(
        source_input=source_input,
        prompt=b"prompt",
        schema=b"schema",
        response=b"response",
    )
    return normalize_search_intent(
        source_input,
        SearchIntentDraft.model_validate(payload),
        provenance=provenance,
    )


def usage_policies() -> list[ProviderUsageLimits]:
    def limits(provider: str, *, calls: int, tokens: int, cost: int):
        digest = {"bonsai": "a" * 64, "cloudflare": "b" * 64, "outscraper": "c" * 64}
        amount = UsageAmount(calls=calls, tokens=tokens, cost_microusd=cost)
        return ProviderUsageLimits(
            provider=provider,
            pricing_policy_sha256=digest[provider],
            per_user_day=amount,
            per_session=amount,
            global_day=amount,
        )

    return [
        limits("bonsai", calls=2, tokens=20_000, cost=20_000),
        limits("cloudflare", calls=8, tokens=0, cost=40_000),
        limits("outscraper", calls=1, tokens=0, cost=20_000),
    ]


def reviewed_session():
    intent = normalized_intent()
    query_plan = build_search_query_plan(intent)
    session = create_search_session(
        owner_id="owner-1",
        session_id="session-1",
        now=NOW,
    )
    session = start_intent_processing(
        session,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=1),
    )
    session = record_intent_plan(
        session,
        intent=intent,
        query_plan=query_plan,
        typed_proposal=build_typed_requirement_proposal(intent),
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=2),
    )
    return session, intent, query_plan


def test_intent_plan_v3_binds_typed_proposal() -> None:
    intent = normalized_intent()
    query_plan = build_search_query_plan(intent)
    proposal = build_typed_requirement_proposal(intent)
    session = create_search_session(owner_id="owner-1", session_id="session-1", now=NOW)
    session = start_intent_processing(
        session,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=1),
    )
    session = record_intent_plan(
        session,
        intent=intent,
        query_plan=query_plan,
        typed_proposal=proposal,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=2),
    )

    assert session.schema_version == "3.0"
    assert session.typed_requirement_status == "ready"
    assert session.typed_requirement_proposal_sha256 == typed_requirement_proposal_sha256(proposal)
    old_payload = session.model_dump(mode="python")
    old_payload["schema_version"] = "2.0"
    with pytest.raises(ValidationError):
        SearchSessionSnapshot.model_validate(old_payload)


def test_queryless_blocking_plan_has_no_query_digest_or_executable_variant() -> None:
    intent = normalized_intent(blocking=True)
    proposal = build_typed_requirement_proposal(intent)
    session = create_search_session(owner_id="owner-1", session_id="session-blocked", now=NOW)
    processing = start_intent_processing(
        session,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=1),
    )

    blocked = record_intent_plan(
        processing,
        intent=intent,
        query_plan=None,
        typed_proposal=proposal,
        expected_revision=processing.revision,
        now=NOW + timedelta(seconds=2),
    )

    assert blocked.state == "intent_review"
    assert blocked.intent_sha256 == search_intent_sha256(intent)
    assert blocked.query_plan_sha256 is None
    assert blocked.typed_requirement_status == "blocking"

    tampered = blocked.model_dump(mode="python")
    tampered["query_plan_sha256"] = "d" * 64
    with pytest.raises(ValidationError):
        SearchSessionSnapshot.model_validate(tampered)

    artificial_query = build_search_query_plan(normalized_intent()).model_copy(
        update={"intent_sha256": search_intent_sha256(intent)}
    )
    with pytest.raises(SearchStateError):
        record_intent_plan(
            processing,
            intent=intent,
            query_plan=artificial_query,
            typed_proposal=proposal,
            expected_revision=processing.revision,
            now=NOW + timedelta(seconds=2),
        )


def test_ready_intent_plan_still_requires_a_query() -> None:
    intent = normalized_intent()
    session = create_search_session(owner_id="owner-1", session_id="session-ready", now=NOW)
    processing = start_intent_processing(
        session,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=1),
    )

    with pytest.raises(SearchStateError):
        record_intent_plan(
            processing,
            intent=intent,
            query_plan=None,
            typed_proposal=build_typed_requirement_proposal(intent),
            expected_revision=processing.revision,
            now=NOW + timedelta(seconds=2),
        )


def started_reservation(
    ledger: InMemoryUsageLedger,
    *,
    provider: str,
    operation: str,
    binding_sha256: str,
    calls: int,
    requested_at: datetime,
) -> UsageReservation:
    pricing_digest = {
        "bonsai": "a" * 64,
        "cloudflare": "b" * 64,
        "outscraper": "c" * 64,
    }[provider]
    reserved = ledger.reserve(
        UsageReservationRequest(
            provider=provider,
            operation=operation,
            owner_id="owner-1",
            session_id="session-1",
            binding_sha256=binding_sha256,
            amount=UsageAmount(
                calls=calls,
                tokens=0,
                cost_microusd=calls * 1_000,
            ),
            pricing_policy_sha256=pricing_digest,
        ),
        now=requested_at,
    )
    return ledger.start(
        reserved.reservation_id,
        owner_id="owner-1",
        session_id="session-1",
        now=requested_at + timedelta(milliseconds=1),
    )


def approval_plan(session, intent, query_plan, *, with_images: bool, created_at: datetime):
    policies = usage_policies()
    usages = [
        ApprovedUsage(
            provider="bonsai",
            calls=1,
            tokens=4_096,
            cost_microusd=5_000,
            pricing_policy_sha256="a" * 64,
        ),
        ApprovedUsage(
            provider="cloudflare",
            calls=(8 if with_images else 0),
            tokens=0,
            cost_microusd=(20_000 if with_images else 0),
            pricing_policy_sha256="b" * 64,
        ),
        ApprovedUsage(
            provider="outscraper",
            calls=1,
            tokens=0,
            cost_microusd=10_000,
            pricing_policy_sha256="c" * 64,
        ),
    ]
    runtime = SearchRuntimeBindings(
        bonsai_model_id="local-bonsai-model",
        bonsai_prompt_sha256=intent.provenance.prompt_sha256,
        bonsai_schema_sha256=intent.provenance.schema_sha256,
        cloudflare_model_id=("@cf/black-forest-labs/flux-2-klein-4b" if with_images else None),
        image_prompt_sha256=("d" * 64 if with_images else None),
        ranking_profile_id="typed-ranking-v4",
        ranking_profile_sha256=typed_ranking_profile_sha256(),
        product_evidence_profile_sha256=product_evidence_profile_sha256(),
        implementation_sha256="f" * 64,
        usage_policy_sha256=usage_policy_sha256(policies),
    )
    return build_search_approval_plan(
        owner_id=session.owner_id,
        session_id=session.session_id,
        intent=intent,
        query_plan=query_plan,
        outscraper_request_sha256="2" * 64,
        image_set_sha256=session.image_set_sha256,
        image_request_metadata_sha256=session.image_request_metadata_sha256,
        usage_allowances=usages,
        runtime_bindings=runtime,
        created_at=created_at,
    )


def test_image_off_path_requires_two_approvals_and_consumes_token_once(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.search_v2.state_machine.secrets.token_urlsafe",
        lambda _size: "A" * 43,
    )
    session, intent, query_plan = reviewed_session()
    session = approve_intent_review(
        session,
        use_images=False,
        image_reservation=None,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=3),
    )
    assert session.state == "search_approval"

    plan = approval_plan(
        session,
        intent,
        query_plan,
        with_images=False,
        created_at=NOW + timedelta(seconds=4),
    )
    issued = issue_search_approval(
        session,
        plan=plan,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=4),
    )
    assert issued.token == "A" * 43
    assert issued.token not in issued.session.model_dump_json()
    assert issued.session.approval is not None
    assert issued.session.approval.token_sha256 != issued.token

    ledger = InMemoryUsageLedger(usage_policies())
    reservation = started_reservation(
        ledger,
        provider="outscraper",
        operation="product_search",
        binding_sha256=search_approval_plan_sha256(plan),
        calls=1,
        requested_at=NOW + timedelta(seconds=5),
    )
    approval_ledger = InMemoryApprovalLedger()
    submitted = consume_search_approval(
        issued.session,
        approval_ledger=approval_ledger,
        token=issued.token,
        plan=plan,
        outscraper_reservation=reservation,
        owner_id="owner-1",
        session_id="session-1",
        expected_revision=issued.session.revision,
        now=NOW + timedelta(seconds=6),
    )
    assert submitted.state == "scrape_submitted"
    assert submitted.approval is not None
    assert submitted.approval.consumed_at == NOW + timedelta(seconds=6)

    with pytest.raises(SearchStateError):
        consume_search_approval(
            submitted,
            approval_ledger=approval_ledger,
            token=issued.token,
            plan=plan,
            outscraper_reservation=reservation,
            owner_id="owner-1",
            session_id="session-1",
            expected_revision=submitted.revision,
            now=NOW + timedelta(seconds=7),
        )


def test_image_path_requires_started_reservations_and_limits_sets_to_two() -> None:
    session, intent, query_plan = reviewed_session()
    ledger = InMemoryUsageLedger(usage_policies())

    reserved_only = ledger.reserve(
        UsageReservationRequest(
            provider="cloudflare",
            operation="image_set",
            owner_id="owner-1",
            session_id="session-1",
            binding_sha256=search_query_plan_sha256(query_plan),
            amount=UsageAmount(calls=4, tokens=0, cost_microusd=4_000),
            pricing_policy_sha256="b" * 64,
        ),
        now=NOW + timedelta(seconds=3),
    )
    with pytest.raises(SearchStateError, match="started image reservation"):
        approve_intent_review(
            session,
            use_images=True,
            image_reservation=reserved_only,
            expected_revision=session.revision,
            now=NOW + timedelta(seconds=4),
        )

    first = ledger.start(
        reserved_only.reservation_id,
        owner_id="owner-1",
        session_id="session-1",
        now=NOW + timedelta(seconds=4),
    )
    session = approve_intent_review(
        session,
        use_images=True,
        image_reservation=first,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=5),
    )
    assert session.state == "image_generating"
    assert session.image_attempts_started == 1

    with pytest.raises(SearchStateError, match="succeeded image reservation"):
        record_image_set(
            session,
            image_reservation=first,
            image_set_sha256="3" * 64,
            image_request_metadata_sha256="4" * 64,
            expected_revision=session.revision,
            now=NOW + timedelta(milliseconds=5_250),
        )

    first_finished = ledger.finish(
        first.reservation_id,
        owner_id="owner-1",
        session_id="session-1",
        success=True,
        now=NOW + timedelta(milliseconds=5_500),
    )
    session = record_image_set(
        session,
        image_reservation=first_finished,
        image_set_sha256="3" * 64,
        image_request_metadata_sha256="4" * 64,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=6),
    )
    assert session.state == "image_review"

    second = started_reservation(
        ledger,
        provider="cloudflare",
        operation="image_set",
        binding_sha256=search_query_plan_sha256(query_plan),
        calls=4,
        requested_at=NOW + timedelta(seconds=7),
    )
    session = request_image_regeneration(
        session,
        image_reservation=second,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=8),
    )
    assert session.state == "image_generating"
    assert session.image_attempts_started == 2
    assert session.image_set_sha256 is None

    second_finished = ledger.finish(
        second.reservation_id,
        owner_id="owner-1",
        session_id="session-1",
        success=True,
        now=NOW + timedelta(milliseconds=8_500),
    )
    session = record_image_set(
        session,
        image_reservation=second_finished,
        image_set_sha256="5" * 64,
        image_request_metadata_sha256="6" * 64,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=9),
    )
    with pytest.raises(SearchStateError, match="image set limit"):
        request_image_regeneration(
            session,
            image_reservation=second,
            expected_revision=session.revision,
            now=NOW + timedelta(seconds=10),
        )

    session = approve_image_review(
        session,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=11),
    )
    assert session.state == "search_approval"
    plan = approval_plan(
        session,
        intent,
        query_plan,
        with_images=True,
        created_at=NOW + timedelta(seconds=12),
    )
    assert plan.image_set_sha256 == "5" * 64


def test_plan_change_invalidates_image_and_existing_search_approval() -> None:
    session, intent, query_plan = reviewed_session()
    session = approve_intent_review(
        session,
        use_images=False,
        image_reservation=None,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=3),
    )
    old_plan = approval_plan(
        session,
        intent,
        query_plan,
        with_images=False,
        created_at=NOW + timedelta(seconds=4),
    )
    issued = issue_search_approval(
        session,
        plan=old_plan,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=4),
    )

    new_intent = normalized_intent(preferred_term="長時間")
    new_query_plan = build_search_query_plan(new_intent)
    revised = replace_intent_plan(
        issued.session,
        intent=new_intent,
        query_plan=new_query_plan,
        typed_proposal=build_typed_requirement_proposal(new_intent),
        expected_revision=issued.session.revision,
        now=NOW + timedelta(seconds=5),
    )

    assert revised.state == "intent_review"
    assert revised.approval is None
    assert revised.image_set_sha256 is None
    assert revised.query_plan_sha256 == search_query_plan_sha256(new_query_plan)


def test_wrong_token_owner_plan_and_expired_token_are_rejected() -> None:
    session, intent, query_plan = reviewed_session()
    session = approve_intent_review(
        session,
        use_images=False,
        image_reservation=None,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=3),
    )
    plan = approval_plan(
        session,
        intent,
        query_plan,
        with_images=False,
        created_at=NOW + timedelta(seconds=4),
    )
    issued = issue_search_approval(
        session,
        plan=plan,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=4),
    )
    ledger = InMemoryUsageLedger(usage_policies())
    reservation = started_reservation(
        ledger,
        provider="outscraper",
        operation="product_search",
        binding_sha256=search_approval_plan_sha256(plan),
        calls=1,
        requested_at=NOW + timedelta(seconds=5),
    )

    common = {
        "session": issued.session,
        "approval_ledger": InMemoryApprovalLedger(),
        "plan": plan,
        "outscraper_reservation": reservation,
        "session_id": "session-1",
        "expected_revision": issued.session.revision,
        "now": NOW + timedelta(seconds=6),
    }
    with pytest.raises(SearchStateError, match="approval token"):
        consume_search_approval(token="B" * 43, owner_id="owner-1", **common)
    with pytest.raises(SearchStateError, match="owner or session"):
        consume_search_approval(token=issued.token, owner_id="owner-2", **common)

    changed_plan = plan.model_copy(update={"outscraper_request_sha256": "9" * 64})
    with pytest.raises(SearchStateError, match="approved plan"):
        consume_search_approval(
            issued.session,
            approval_ledger=InMemoryApprovalLedger(),
            token=issued.token,
            plan=changed_plan,
            outscraper_reservation=reservation,
            owner_id="owner-1",
            session_id="session-1",
            expected_revision=issued.session.revision,
            now=NOW + timedelta(seconds=6),
        )

    oversized_request = reservation.request.model_copy(
        update={
            "amount": UsageAmount(calls=1, tokens=0, cost_microusd=10_001),
        }
    )
    oversized_reservation = reservation.model_copy(update={"request": oversized_request})
    with pytest.raises(SearchStateError, match="Outscraper reservation"):
        consume_search_approval(
            issued.session,
            approval_ledger=InMemoryApprovalLedger(),
            token=issued.token,
            plan=plan,
            outscraper_reservation=oversized_reservation,
            owner_id="owner-1",
            session_id="session-1",
            expected_revision=issued.session.revision,
            now=NOW + timedelta(seconds=6),
        )

    with pytest.raises(SearchStateError, match="expired"):
        consume_search_approval(
            issued.session,
            approval_ledger=InMemoryApprovalLedger(),
            token=issued.token,
            plan=plan,
            outscraper_reservation=reservation,
            owner_id="owner-1",
            session_id="session-1",
            expected_revision=issued.session.revision,
            now=plan.expires_at,
        )


def test_outscraper_reservation_cannot_start_before_search_approval() -> None:
    session, intent, query_plan = reviewed_session()
    session = approve_intent_review(
        session,
        use_images=False,
        image_reservation=None,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=3),
    )
    plan = approval_plan(
        session,
        intent,
        query_plan,
        with_images=False,
        created_at=NOW + timedelta(seconds=4),
    )
    usage_ledger = InMemoryUsageLedger(usage_policies())
    reservation = started_reservation(
        usage_ledger,
        provider="outscraper",
        operation="product_search",
        binding_sha256=search_approval_plan_sha256(plan),
        calls=1,
        requested_at=NOW + timedelta(milliseconds=3_500),
    )
    issued = issue_search_approval(
        session,
        plan=plan,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=4),
    )

    with pytest.raises(SearchStateError, match="started before search approval"):
        consume_search_approval(
            issued.session,
            approval_ledger=InMemoryApprovalLedger(),
            token=issued.token,
            plan=plan,
            outscraper_reservation=reservation,
            owner_id="owner-1",
            session_id="session-1",
            expected_revision=issued.session.revision,
            now=NOW + timedelta(seconds=5),
        )


def test_same_issued_snapshot_can_be_consumed_only_once_under_concurrency() -> None:
    session, intent, query_plan = reviewed_session()
    session = approve_intent_review(
        session,
        use_images=False,
        image_reservation=None,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=3),
    )
    plan = approval_plan(
        session,
        intent,
        query_plan,
        with_images=False,
        created_at=NOW + timedelta(seconds=4),
    )
    issued = issue_search_approval(
        session,
        plan=plan,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=4),
    )
    usage_ledger = InMemoryUsageLedger(usage_policies())
    reservation = started_reservation(
        usage_ledger,
        provider="outscraper",
        operation="product_search",
        binding_sha256=search_approval_plan_sha256(plan),
        calls=1,
        requested_at=NOW + timedelta(seconds=5),
    )
    approval_ledger = InMemoryApprovalLedger()

    def consume_once(_index: int) -> str:
        try:
            result = consume_search_approval(
                issued.session,
                approval_ledger=approval_ledger,
                token=issued.token,
                plan=plan,
                outscraper_reservation=reservation,
                owner_id="owner-1",
                session_id="session-1",
                expected_revision=issued.session.revision,
                now=NOW + timedelta(seconds=6),
            )
        except SearchStateError:
            return "rejected"
        return result.state

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(consume_once, (1, 2)))

    assert sorted(results) == ["rejected", "scrape_submitted"]
    restored = InMemoryApprovalLedger.from_snapshot(approval_ledger.snapshot())
    with pytest.raises(SearchStateError, match="already been consumed"):
        consume_search_approval(
            issued.session,
            approval_ledger=restored,
            token=issued.token,
            plan=plan,
            outscraper_reservation=reservation,
            owner_id="owner-1",
            session_id="session-1",
            expected_revision=issued.session.revision,
            now=NOW + timedelta(seconds=7),
        )


def image_recovery_api():
    from src.search_v2 import state_machine

    required = (
        "record_image_generation_failure",
        "retry_failed_image_set",
        "discard_failed_image_attempt",
    )
    assert all(hasattr(state_machine, name) for name in required), (
        "image failure recovery transitions are required"
    )
    return (
        state_machine.record_image_generation_failure,
        state_machine.retry_failed_image_set,
        state_machine.discard_failed_image_attempt,
    )


def failed_image_session():
    record_failure, _retry, _discard = image_recovery_api()
    session, intent, query_plan = reviewed_session()
    ledger = InMemoryUsageLedger(usage_policies())
    started = started_reservation(
        ledger,
        provider="cloudflare",
        operation="image_set",
        binding_sha256=search_query_plan_sha256(query_plan),
        calls=4,
        requested_at=NOW + timedelta(seconds=3),
    )
    generating = approve_intent_review(
        session,
        use_images=True,
        image_reservation=started,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=4),
    )
    failed = ledger.finish(
        started.reservation_id,
        owner_id="owner-1",
        session_id="session-1",
        success=False,
        now=NOW + timedelta(seconds=5),
    )
    recovery = record_failure(
        generating,
        image_reservation=failed,
        expected_revision=generating.revision,
        now=NOW + timedelta(seconds=6),
    )
    return recovery, intent, query_plan, ledger, failed


def test_failed_image_attempt_enters_strict_recovery_state() -> None:
    recovery, _intent, _query_plan, _ledger, failed = failed_image_session()

    assert recovery.state == "image_generation_failed"
    assert recovery.revision == 4
    assert recovery.image_mode == "on"
    assert recovery.image_attempts_started == 1
    assert recovery.active_image_reservation_id is None
    assert recovery.failed_image_reservation_id == failed.reservation_id
    assert recovery.image_set_sha256 is None
    assert recovery.image_request_metadata_sha256 is None

    payload = recovery.model_dump(mode="python")
    payload["failed_image_reservation_id"] = None
    with pytest.raises(ValidationError):
        SearchSessionSnapshot.model_validate(payload)

    payload = recovery.model_dump(mode="python")
    payload["active_image_reservation_id"] = "A" * 32
    with pytest.raises(ValidationError):
        SearchSessionSnapshot.model_validate(payload)


def test_image_failure_record_rejects_stale_or_mismatched_failed_reservation() -> None:
    record_failure, _retry, _discard = image_recovery_api()
    session, _intent, query_plan = reviewed_session()
    ledger = InMemoryUsageLedger(usage_policies())
    started = started_reservation(
        ledger,
        provider="cloudflare",
        operation="image_set",
        binding_sha256=search_query_plan_sha256(query_plan),
        calls=4,
        requested_at=NOW + timedelta(seconds=3),
    )
    generating = approve_intent_review(
        session,
        use_images=True,
        image_reservation=started,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=4),
    )
    failed = ledger.finish(
        started.reservation_id,
        owner_id="owner-1",
        session_id="session-1",
        success=False,
        now=NOW + timedelta(seconds=5),
    )

    with pytest.raises(SearchStateError, match="stale session revision"):
        record_failure(
            generating,
            image_reservation=failed,
            expected_revision=generating.revision - 1,
            now=NOW + timedelta(seconds=6),
        )

    tampered_request = failed.request.model_copy(update={"session_id": "session-2"})
    tampered = failed.model_copy(update={"request": tampered_request})
    with pytest.raises(SearchStateError, match="failed image reservation"):
        record_failure(
            generating,
            image_reservation=tampered,
            expected_revision=generating.revision,
            now=NOW + timedelta(seconds=6),
        )


def test_failed_image_attempt_retries_once_with_a_new_reservation() -> None:
    _record_failure, retry, _discard = image_recovery_api()
    recovery, _intent, query_plan, ledger, failed = failed_image_session()
    second = started_reservation(
        ledger,
        provider="cloudflare",
        operation="image_set",
        binding_sha256=search_query_plan_sha256(query_plan),
        calls=4,
        requested_at=NOW + timedelta(seconds=7),
    )

    generating = retry(
        recovery,
        image_reservation=second,
        expected_revision=recovery.revision,
        now=NOW + timedelta(seconds=8),
    )

    assert generating.state == "image_generating"
    assert generating.image_attempts_started == 2
    assert generating.active_image_reservation_id == second.reservation_id
    assert generating.failed_image_reservation_id is None
    assert failed.status == "failed"

    forged_reuse = failed.model_copy(update={"status": "started", "finished_at": None})
    with pytest.raises(SearchStateError, match="new image reservation"):
        retry(
            recovery,
            image_reservation=forged_reuse,
            expected_revision=recovery.revision,
            now=NOW + timedelta(seconds=8),
        )


def test_second_failed_image_attempt_cannot_retry_but_can_continue_without_images() -> None:
    record_failure, retry, discard = image_recovery_api()
    recovery, _intent, query_plan, ledger, first_failed = failed_image_session()
    second = started_reservation(
        ledger,
        provider="cloudflare",
        operation="image_set",
        binding_sha256=search_query_plan_sha256(query_plan),
        calls=4,
        requested_at=NOW + timedelta(seconds=7),
    )
    generating = retry(
        recovery,
        image_reservation=second,
        expected_revision=recovery.revision,
        now=NOW + timedelta(seconds=8),
    )
    second_failed = ledger.finish(
        second.reservation_id,
        owner_id="owner-1",
        session_id="session-1",
        success=False,
        now=NOW + timedelta(seconds=9),
    )
    exhausted = record_failure(
        generating,
        image_reservation=second_failed,
        expected_revision=generating.revision,
        now=NOW + timedelta(seconds=10),
    )

    with pytest.raises(SearchStateError, match="image set limit"):
        retry(
            exhausted,
            image_reservation=second,
            expected_revision=exhausted.revision,
            now=NOW + timedelta(seconds=11),
        )

    continued = discard(
        exhausted,
        expected_revision=exhausted.revision,
        now=NOW + timedelta(seconds=11),
    )
    assert continued.state == "search_approval"
    assert continued.image_mode == "off"
    assert continued.image_attempts_started == 0
    assert continued.active_image_reservation_id is None
    assert continued.failed_image_reservation_id is None
    assert continued.usage_policy_sha256 is None
    assert [item.status for item in ledger.snapshot().reservations] == [
        first_failed.status,
        second_failed.status,
    ]


def test_stale_revision_and_invalid_transition_fail_closed() -> None:
    session = create_search_session(
        owner_id="owner-1",
        session_id="session-1",
        now=NOW,
    )

    with pytest.raises(SearchStateError, match="stale session revision"):
        start_intent_processing(
            session,
            expected_revision=1,
            now=NOW + timedelta(seconds=1),
        )

    with pytest.raises(SearchStateError, match="state transition"):
        approve_intent_review(
            session,
            use_images=False,
            image_reservation=None,
            expected_revision=0,
            now=NOW + timedelta(seconds=1),
        )


def test_session_revalidates_nested_approval_grant() -> None:
    session, intent, query_plan = reviewed_session()
    session = approve_intent_review(
        session,
        use_images=False,
        image_reservation=None,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=3),
    )
    forged = SearchApprovalGrant.model_construct(
        plan_sha256="invalid",
        token_sha256="invalid",
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=15),
        consumed_at=None,
    )
    payload = session.model_dump(mode="python")
    payload["approval"] = forged

    with pytest.raises(ValidationError):
        SearchSessionSnapshot.model_validate(payload)
