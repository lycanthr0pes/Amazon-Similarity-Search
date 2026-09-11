from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.search_v2.approval import SearchApprovalPlan
from src.search_v2.approval import search_approval_plan_sha256
from src.search_v2.intent import NormalizedSearchIntent
from src.search_v2.intent import search_intent_sha256
from src.search_v2.query_planner import SearchQueryPlan
from src.search_v2.query_planner import search_query_plan_sha256
from src.search_v2.typed_intent_adapter import TypedRequirementProposal
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_intent_adapter import typed_requirement_proposal_sha256
from src.search_v2.usage_ledger import Digest
from src.search_v2.usage_ledger import ReservationId
from src.search_v2.usage_ledger import SubjectId
from src.search_v2.usage_ledger import UsageReservation


MAX_IMAGE_SET_ATTEMPTS = 2
MAX_APPROVAL_CONSUMPTIONS = 10_000
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43,128}$")

SearchState = Literal[
    "draft",
    "intent_processing",
    "intent_review",
    "image_generating",
    "image_generation_failed",
    "image_review",
    "search_approval",
    "scrape_submitted",
    "products_received",
    "products_normalized",
    "search_completed",
    "search_failed",
]
SearchResultOutcome = Literal["results", "empty"]
SearchFailureStage = Literal["product_search", "product_normalization", "ranking"]
SearchFailureCode = Literal[
    "product_search_failed",
    "product_normalization_failed",
    "ranking_failed",
]


class SearchStateError(ValueError):
    pass


class StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        revalidate_instances="always",
        frozen=True,
    )


def _utc_datetime(value: datetime, *, field_name: str) -> datetime:
    if type(value) is not datetime:
        raise TypeError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must use UTC")
    return value.astimezone(timezone.utc)


class SearchApprovalGrant(StrictFrozenContract):
    plan_sha256: Digest
    token_sha256: Digest
    issued_at: datetime
    expires_at: datetime
    consumed_at: datetime | None

    @field_validator("issued_at", "expires_at", "consumed_at")
    @classmethod
    def validate_timestamp(cls, value: datetime | None, info) -> datetime | None:
        if value is None:
            return None
        return _utc_datetime(value, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_lifetime(self) -> SearchApprovalGrant:
        if self.expires_at <= self.issued_at:
            raise ValueError("approval expiry must follow issuance")
        if self.consumed_at is not None and not (
            self.issued_at <= self.consumed_at < self.expires_at
        ):
            raise ValueError("approval consumption is outside its lifetime")
        return self


class ApprovalConsumption(StrictFrozenContract):
    owner_id: SubjectId
    session_id: SubjectId
    plan_sha256: Digest
    token_sha256: Digest
    consumed_at: datetime

    @field_validator("consumed_at")
    @classmethod
    def validate_consumed_at(cls, value: datetime) -> datetime:
        return _utc_datetime(value, field_name="consumed_at")


class ApprovalConsumptionSnapshot(StrictFrozenContract):
    schema_version: Literal["2.0"]
    consumptions: Annotated[
        list[ApprovalConsumption],
        Field(max_length=MAX_APPROVAL_CONSUMPTIONS),
    ]

    @model_validator(mode="after")
    def validate_unique_tokens(self) -> ApprovalConsumptionSnapshot:
        token_digests = [consumption.token_sha256 for consumption in self.consumptions]
        if len(token_digests) != len(set(token_digests)):
            raise ValueError("approval consumption ledger contains duplicate tokens")
        return self


class InMemoryApprovalLedger:
    """Atomic single-use claims inside one process without retaining raw tokens."""

    def __init__(self) -> None:
        self._consumptions: dict[str, ApprovalConsumption] = {}
        self._lock = threading.Lock()

    @classmethod
    def from_snapshot(
        cls,
        snapshot: ApprovalConsumptionSnapshot,
    ) -> InMemoryApprovalLedger:
        try:
            validated = ApprovalConsumptionSnapshot.model_validate(snapshot)
        except ValueError as exc:
            raise SearchStateError("approval consumption snapshot is invalid") from exc
        ledger = cls()
        ledger._consumptions = {
            consumption.token_sha256: consumption for consumption in validated.consumptions
        }
        return ledger

    def snapshot(self) -> ApprovalConsumptionSnapshot:
        with self._lock:
            return ApprovalConsumptionSnapshot(
                schema_version="2.0",
                consumptions=sorted(
                    self._consumptions.values(),
                    key=lambda item: (item.consumed_at, item.token_sha256),
                ),
            )

    def claim(
        self,
        grant: SearchApprovalGrant,
        *,
        owner_id: str,
        session_id: str,
        now: datetime,
    ) -> ApprovalConsumption:
        try:
            validated_grant = SearchApprovalGrant.model_validate(grant)
        except ValueError as exc:
            raise SearchStateError("search approval grant is invalid") from exc
        validated_now = _utc_datetime(now, field_name="now")
        if validated_grant.consumed_at is not None:
            raise SearchStateError("search approval has already been consumed")
        if not validated_grant.issued_at <= validated_now < validated_grant.expires_at:
            raise SearchStateError("search approval has expired")

        consumption = ApprovalConsumption(
            owner_id=owner_id,
            session_id=session_id,
            plan_sha256=validated_grant.plan_sha256,
            token_sha256=validated_grant.token_sha256,
            consumed_at=validated_now,
        )
        with self._lock:
            if validated_grant.token_sha256 in self._consumptions:
                raise SearchStateError("search approval has already been consumed")
            if len(self._consumptions) >= MAX_APPROVAL_CONSUMPTIONS:
                raise SearchStateError("approval consumption ledger capacity is exhausted")
            self._consumptions[validated_grant.token_sha256] = consumption
        return consumption


class SearchSessionSnapshot(StrictFrozenContract):
    schema_version: Literal["3.0"]
    owner_id: SubjectId
    session_id: SubjectId
    revision: Annotated[int, Field(ge=0)]
    state: SearchState
    intent_sha256: Digest | None
    query_plan_sha256: Digest | None
    typed_requirement_proposal_sha256: Digest | None
    typed_requirement_status: Literal["ready", "blocking"] | None
    image_mode: Literal["off", "on"]
    image_attempts_started: Annotated[int, Field(ge=0, le=MAX_IMAGE_SET_ATTEMPTS)]
    active_image_reservation_id: ReservationId | None
    failed_image_reservation_id: ReservationId | None = None
    image_set_sha256: Digest | None
    image_request_metadata_sha256: Digest | None
    usage_policy_sha256: Digest | None
    approval: SearchApprovalGrant | None
    created_at: datetime
    updated_at: datetime
    received_candidate_count: Annotated[int, Field(ge=0, le=48)] | None = None
    normalized_product_count: Annotated[int, Field(ge=0, le=48)] | None = None
    rejected_candidate_count: Annotated[int, Field(ge=0, le=48)] | None = None
    ranked_product_count: Annotated[int, Field(ge=0, le=48)] | None = None
    normalized_product_batch_sha256: Digest | None = None
    ranked_product_batch_sha256: Digest | None = None
    result_outcome: SearchResultOutcome | None = None
    failure_stage: SearchFailureStage | None = None
    failure_code: SearchFailureCode | None = None

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_timestamp(cls, value: datetime, info) -> datetime:
        return _utc_datetime(value, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_state_contract(self) -> SearchSessionSnapshot:
        if self.updated_at < self.created_at:
            raise ValueError("session update precedes creation")

        review_values = (
            self.intent_sha256,
            self.typed_requirement_proposal_sha256,
            self.typed_requirement_status,
        )
        has_review = all(value is not None for value in review_values)
        if any(value is not None for value in review_values) != has_review:
            raise ValueError("intent and typed proposal bindings must be present together")
        if self.state in {"draft", "intent_processing"} and (
            has_review or self.query_plan_sha256 is not None
        ):
            raise ValueError("pre-review state must not contain a reviewed plan")
        if self.state not in {"draft", "intent_processing"} and not has_review:
            raise ValueError("review and execution states require a reviewed plan")
        if self.typed_requirement_status == "blocking":
            if self.state != "intent_review" or self.query_plan_sha256 is not None:
                raise ValueError("blocking typed conditions require a query-less intent review")
        elif has_review and self.query_plan_sha256 is None:
            raise ValueError("ready typed conditions require a query plan")

        image_bindings_present = (
            self.image_set_sha256 is not None and self.image_request_metadata_sha256 is not None
        )
        if (self.image_set_sha256 is None) != (self.image_request_metadata_sha256 is None):
            raise ValueError("image result bindings must be present together")

        if self.image_mode == "off":
            if (
                self.image_attempts_started != 0
                or self.active_image_reservation_id is not None
                or self.failed_image_reservation_id is not None
                or image_bindings_present
                or self.usage_policy_sha256 is not None
            ):
                raise ValueError("image-off session must not contain image execution state")
            if self.state in {"image_generating", "image_generation_failed", "image_review"}:
                raise ValueError("image state requires image mode on")
        else:
            if self.image_attempts_started < 1 or self.usage_policy_sha256 is None:
                raise ValueError("image-on session requires a started set and usage policy")
            if self.state == "image_generating":
                if (
                    self.active_image_reservation_id is None
                    or self.failed_image_reservation_id is not None
                    or image_bindings_present
                ):
                    raise ValueError("image generation requires an active reservation only")
            elif self.state == "image_generation_failed":
                if (
                    self.active_image_reservation_id is not None
                    or self.failed_image_reservation_id is None
                    or image_bindings_present
                ):
                    raise ValueError("failed image generation requires a failed reservation only")
            elif self.state in {
                "image_review",
                "search_approval",
                "scrape_submitted",
                "products_received",
                "products_normalized",
                "search_completed",
                "search_failed",
            }:
                if (
                    self.active_image_reservation_id is not None
                    or self.failed_image_reservation_id is not None
                    or not image_bindings_present
                ):
                    raise ValueError("post-generation state requires completed image bindings")
            else:
                raise ValueError("image mode on is invalid in the current state")

        execution_states = {
            "scrape_submitted",
            "products_received",
            "products_normalized",
            "search_completed",
            "search_failed",
        }
        if self.approval is None:
            if self.state in execution_states:
                raise ValueError("submitted search requires a consumed approval")
        elif self.state == "search_approval":
            if self.approval.consumed_at is not None:
                raise ValueError("search approval state cannot contain a consumed approval")
        elif self.state in execution_states:
            if self.approval.consumed_at is None:
                raise ValueError("submitted search requires consumed approval")
        else:
            raise ValueError("approval grant is invalid in the current state")

        progress_values = (
            self.received_candidate_count,
            self.normalized_product_count,
            self.rejected_candidate_count,
            self.ranked_product_count,
            self.normalized_product_batch_sha256,
            self.ranked_product_batch_sha256,
            self.result_outcome,
            self.failure_stage,
            self.failure_code,
        )
        if self.state not in {
            "products_received",
            "products_normalized",
            "search_completed",
            "search_failed",
        }:
            if any(value is not None for value in progress_values):
                raise ValueError("pre-result state must not contain product progress")
            return self

        has_normalized_progress = (
            self.normalized_product_count is not None
            and self.rejected_candidate_count is not None
            and self.normalized_product_batch_sha256 is not None
        )
        if (
            any(
                value is not None
                for value in (
                    self.normalized_product_count,
                    self.rejected_candidate_count,
                    self.normalized_product_batch_sha256,
                )
            )
            != has_normalized_progress
        ):
            raise ValueError("normalized product progress must be present together")
        if has_normalized_progress and (
            self.received_candidate_count is None
            or self.normalized_product_count + self.rejected_candidate_count
            != self.received_candidate_count
        ):
            raise ValueError("normalized product counts do not match received candidates")

        if self.state == "products_received":
            if self.received_candidate_count is None or any(
                value is not None
                for value in (
                    self.normalized_product_count,
                    self.rejected_candidate_count,
                    self.ranked_product_count,
                    self.normalized_product_batch_sha256,
                    self.ranked_product_batch_sha256,
                    self.result_outcome,
                    self.failure_stage,
                    self.failure_code,
                )
            ):
                raise ValueError("received product state is inconsistent")
            return self

        if self.state == "products_normalized":
            if not has_normalized_progress or any(
                value is not None
                for value in (
                    self.ranked_product_count,
                    self.ranked_product_batch_sha256,
                    self.result_outcome,
                    self.failure_stage,
                    self.failure_code,
                )
            ):
                raise ValueError("normalized product state is inconsistent")
            return self

        if self.state == "search_completed":
            if (
                not has_normalized_progress
                or self.ranked_product_count is None
                or self.ranked_product_batch_sha256 is None
                or self.result_outcome is None
                or self.failure_stage is not None
                or self.failure_code is not None
                or self.ranked_product_count != self.normalized_product_count
                or (self.result_outcome == "results") != (self.ranked_product_count > 0)
            ):
                raise ValueError("completed search state is inconsistent")
            return self

        if self.result_outcome is not None or any(
            value is not None
            for value in (self.ranked_product_count, self.ranked_product_batch_sha256)
        ):
            raise ValueError("failed search must not contain a completed result")
        expected_failures = {
            "product_search": ("product_search_failed", False, False),
            "product_normalization": ("product_normalization_failed", True, False),
            "ranking": ("ranking_failed", True, True),
        }
        if self.failure_stage not in expected_failures:
            raise ValueError("failed search requires a failure stage")
        expected_code, requires_received, requires_normalized = expected_failures[
            self.failure_stage
        ]
        if self.failure_code != expected_code:
            raise ValueError("failed search code does not match its stage")
        if (self.received_candidate_count is not None) != requires_received:
            raise ValueError("failed search received progress is inconsistent")
        if has_normalized_progress != requires_normalized:
            raise ValueError("failed search normalized progress is inconsistent")
        return self


@dataclass(frozen=True, slots=True)
class IssuedSearchApproval:
    session: SearchSessionSnapshot
    token: str


def create_search_session(
    *,
    owner_id: str,
    session_id: str,
    now: datetime,
) -> SearchSessionSnapshot:
    validated_now = _utc_datetime(now, field_name="now")
    return SearchSessionSnapshot(
        schema_version="3.0",
        owner_id=owner_id,
        session_id=session_id,
        revision=0,
        state="draft",
        intent_sha256=None,
        query_plan_sha256=None,
        typed_requirement_proposal_sha256=None,
        typed_requirement_status=None,
        image_mode="off",
        image_attempts_started=0,
        active_image_reservation_id=None,
        failed_image_reservation_id=None,
        image_set_sha256=None,
        image_request_metadata_sha256=None,
        usage_policy_sha256=None,
        approval=None,
        created_at=validated_now,
        updated_at=validated_now,
    )


def start_intent_processing(
    session: SearchSessionSnapshot,
    *,
    expected_revision: int,
    now: datetime,
) -> SearchSessionSnapshot:
    validated = _prepare_transition(
        session,
        expected_revision=expected_revision,
        allowed_states={"draft"},
        now=now,
    )
    return _advance(validated, now=now, state="intent_processing")


def record_intent_plan(
    session: SearchSessionSnapshot,
    *,
    intent: NormalizedSearchIntent,
    query_plan: SearchQueryPlan | None,
    typed_proposal: TypedRequirementProposal,
    expected_revision: int,
    now: datetime,
) -> SearchSessionSnapshot:
    validated = _prepare_transition(
        session,
        expected_revision=expected_revision,
        allowed_states={"intent_processing"},
        now=now,
    )
    intent, query_plan, typed_proposal = _validated_intent_plan(
        intent,
        query_plan,
        typed_proposal,
    )
    return _advance(
        validated,
        now=now,
        state="intent_review",
        intent_sha256=search_intent_sha256(intent),
        query_plan_sha256=(
            search_query_plan_sha256(query_plan) if query_plan is not None else None
        ),
        typed_requirement_proposal_sha256=typed_requirement_proposal_sha256(typed_proposal),
        typed_requirement_status=typed_proposal.status,
    )


def replace_intent_plan(
    session: SearchSessionSnapshot,
    *,
    intent: NormalizedSearchIntent,
    query_plan: SearchQueryPlan | None,
    typed_proposal: TypedRequirementProposal,
    expected_revision: int,
    now: datetime,
) -> SearchSessionSnapshot:
    validated = _prepare_transition(
        session,
        expected_revision=expected_revision,
        allowed_states={"intent_review", "image_review", "search_approval"},
        now=now,
    )
    intent, query_plan, typed_proposal = _validated_intent_plan(
        intent,
        query_plan,
        typed_proposal,
    )
    return _advance(
        validated,
        now=now,
        state="intent_review",
        intent_sha256=search_intent_sha256(intent),
        query_plan_sha256=(
            search_query_plan_sha256(query_plan) if query_plan is not None else None
        ),
        typed_requirement_proposal_sha256=typed_requirement_proposal_sha256(typed_proposal),
        typed_requirement_status=typed_proposal.status,
        image_mode="off",
        image_attempts_started=0,
        active_image_reservation_id=None,
        failed_image_reservation_id=None,
        image_set_sha256=None,
        image_request_metadata_sha256=None,
        usage_policy_sha256=None,
        approval=None,
    )


def approve_intent_review(
    session: SearchSessionSnapshot,
    *,
    use_images: bool,
    image_reservation: UsageReservation | None,
    expected_revision: int,
    now: datetime,
) -> SearchSessionSnapshot:
    if type(use_images) is not bool:
        raise TypeError("use_images must be a bool")
    validated = _prepare_transition(
        session,
        expected_revision=expected_revision,
        allowed_states={"intent_review"},
        now=now,
    )
    if validated.typed_requirement_status != "ready":
        raise SearchStateError("blocking typed conditions require review")
    if not use_images:
        if image_reservation is not None:
            raise SearchStateError("image-off approval must not include a reservation")
        return _advance(validated, now=now, state="search_approval")

    reservation = _validated_image_reservation(validated, image_reservation, now=now)
    return _advance(
        validated,
        now=now,
        state="image_generating",
        image_mode="on",
        image_attempts_started=1,
        active_image_reservation_id=reservation.reservation_id,
        failed_image_reservation_id=None,
        usage_policy_sha256=reservation.usage_policy_sha256,
    )


def record_image_set(
    session: SearchSessionSnapshot,
    *,
    image_reservation: UsageReservation,
    image_set_sha256: str,
    image_request_metadata_sha256: str,
    expected_revision: int,
    now: datetime,
) -> SearchSessionSnapshot:
    validated = _prepare_transition(
        session,
        expected_revision=expected_revision,
        allowed_states={"image_generating"},
        now=now,
    )
    _validated_completed_image_reservation(
        validated,
        image_reservation,
        now=now,
    )
    return _advance(
        validated,
        now=now,
        state="image_review",
        active_image_reservation_id=None,
        failed_image_reservation_id=None,
        image_set_sha256=_validated_digest(image_set_sha256, field_name="image_set_sha256"),
        image_request_metadata_sha256=_validated_digest(
            image_request_metadata_sha256,
            field_name="image_request_metadata_sha256",
        ),
    )


def record_counterfactual_images(
    session: SearchSessionSnapshot,
    *,
    image_reservation: UsageReservation,
    preimage_plan_sha256: str,
    condition_count: int,
    image_set_sha256: str,
    image_request_metadata_sha256: str,
    expected_revision: int,
    now: datetime,
) -> SearchSessionSnapshot:
    """Record the approved reference's completed comparisons without a four-view job."""
    validated = _prepare_transition(
        session, expected_revision=expected_revision, allowed_states={"intent_review"}, now=now
    )
    reservation = UsageReservation.model_validate(image_reservation)
    if (
        validated.typed_requirement_status != "ready"
        or type(condition_count) is not int
        or not 1 <= condition_count <= 3
        or reservation.status != "succeeded"
        or reservation.provider != "cloudflare"
        or reservation.operation != "counterfactual_images"
        or reservation.owner_id != validated.owner_id
        or reservation.session_id != validated.session_id
        or reservation.amount.calls != condition_count
        or reservation.amount.tokens != 0
        or reservation.binding_sha256
        != _validated_digest(preimage_plan_sha256, field_name="preimage_plan_sha256")
        or reservation.started_at is None
        or reservation.started_at < validated.updated_at
        or reservation.finished_at is None
        or reservation.finished_at > _utc_datetime(now, field_name="now")
    ):
        raise SearchStateError("counterfactual images do not match the session")
    return _advance(
        validated,
        now=now,
        state="image_review",
        image_mode="on",
        image_attempts_started=1,
        usage_policy_sha256=reservation.usage_policy_sha256,
        image_set_sha256=_validated_digest(image_set_sha256, field_name="image_set_sha256"),
        image_request_metadata_sha256=_validated_digest(
            image_request_metadata_sha256, field_name="image_request_metadata_sha256"
        ),
    )


def record_image_generation_failure(
    session: SearchSessionSnapshot,
    *,
    image_reservation: UsageReservation,
    expected_revision: int,
    now: datetime,
) -> SearchSessionSnapshot:
    """Bind a finished failed attempt before offering any recovery action."""
    validated = _prepare_transition(
        session,
        expected_revision=expected_revision,
        allowed_states={"image_generating"},
        now=now,
    )
    reservation = _validated_failed_image_reservation(
        validated,
        image_reservation,
        now=now,
    )
    return _advance(
        validated,
        now=now,
        state="image_generation_failed",
        active_image_reservation_id=None,
        failed_image_reservation_id=reservation.reservation_id,
        image_set_sha256=None,
        image_request_metadata_sha256=None,
    )


def request_image_regeneration(
    session: SearchSessionSnapshot,
    *,
    image_reservation: UsageReservation,
    expected_revision: int,
    now: datetime,
) -> SearchSessionSnapshot:
    validated = _prepare_transition(
        session,
        expected_revision=expected_revision,
        allowed_states={"image_review"},
        now=now,
    )
    if validated.image_attempts_started >= MAX_IMAGE_SET_ATTEMPTS:
        raise SearchStateError("image set limit has been reached")
    reservation = _validated_image_reservation(validated, image_reservation, now=now)
    if not hmac.compare_digest(
        reservation.usage_policy_sha256,
        validated.usage_policy_sha256 or "",
    ):
        raise SearchStateError("image reservation usage policy does not match")
    return _advance(
        validated,
        now=now,
        state="image_generating",
        image_attempts_started=validated.image_attempts_started + 1,
        active_image_reservation_id=reservation.reservation_id,
        failed_image_reservation_id=None,
        image_set_sha256=None,
        image_request_metadata_sha256=None,
    )


def retry_failed_image_set(
    session: SearchSessionSnapshot,
    *,
    image_reservation: UsageReservation,
    expected_revision: int,
    now: datetime,
) -> SearchSessionSnapshot:
    """Start a new all-four attempt after an explicitly recorded failure."""
    validated = _prepare_transition(
        session,
        expected_revision=expected_revision,
        allowed_states={"image_generation_failed"},
        now=now,
    )
    if validated.image_attempts_started >= MAX_IMAGE_SET_ATTEMPTS:
        raise SearchStateError("image set limit has been reached")
    reservation = _validated_image_reservation(validated, image_reservation, now=now)
    if reservation.reservation_id == validated.failed_image_reservation_id:
        raise SearchStateError("a new image reservation is required")
    if not hmac.compare_digest(
        reservation.usage_policy_sha256,
        validated.usage_policy_sha256 or "",
    ):
        raise SearchStateError("image reservation usage policy does not match")
    return _advance(
        validated,
        now=now,
        state="image_generating",
        image_attempts_started=validated.image_attempts_started + 1,
        active_image_reservation_id=reservation.reservation_id,
        failed_image_reservation_id=None,
        image_set_sha256=None,
        image_request_metadata_sha256=None,
    )


def approve_image_review(
    session: SearchSessionSnapshot,
    *,
    expected_revision: int,
    now: datetime,
) -> SearchSessionSnapshot:
    validated = _prepare_transition(
        session,
        expected_revision=expected_revision,
        allowed_states={"image_review"},
        now=now,
    )
    return _advance(validated, now=now, state="search_approval")


def discard_image_set(
    session: SearchSessionSnapshot,
    *,
    expected_revision: int,
    now: datetime,
) -> SearchSessionSnapshot:
    """Continue without generated images while usage remains in the separate ledger."""
    validated = _prepare_transition(
        session,
        expected_revision=expected_revision,
        allowed_states={"image_review"},
        now=now,
    )
    return _advance(
        validated,
        now=now,
        state="search_approval",
        image_mode="off",
        image_attempts_started=0,
        active_image_reservation_id=None,
        failed_image_reservation_id=None,
        image_set_sha256=None,
        image_request_metadata_sha256=None,
        usage_policy_sha256=None,
    )


def discard_failed_image_attempt(
    session: SearchSessionSnapshot,
    *,
    expected_revision: int,
    now: datetime,
) -> SearchSessionSnapshot:
    """Continue without images while the failed attempt remains in its ledger."""
    validated = _prepare_transition(
        session,
        expected_revision=expected_revision,
        allowed_states={"image_generation_failed"},
        now=now,
    )
    return _advance(
        validated,
        now=now,
        state="search_approval",
        image_mode="off",
        image_attempts_started=0,
        active_image_reservation_id=None,
        failed_image_reservation_id=None,
        image_set_sha256=None,
        image_request_metadata_sha256=None,
        usage_policy_sha256=None,
    )


def issue_search_approval(
    session: SearchSessionSnapshot,
    *,
    plan: SearchApprovalPlan,
    expected_revision: int,
    now: datetime,
) -> IssuedSearchApproval:
    validated = _prepare_transition(
        session,
        expected_revision=expected_revision,
        allowed_states={"search_approval"},
        now=now,
    )
    if validated.approval is not None:
        raise SearchStateError("search approval has already been issued")
    validated_plan = _validated_plan_for_session(validated, plan)
    validated_now = _utc_datetime(now, field_name="now")
    if validated_now < validated_plan.created_at:
        raise SearchStateError("search approval plan is not active yet")
    if validated_now >= validated_plan.expires_at:
        raise SearchStateError("search approval plan has expired")

    token = secrets.token_urlsafe(32)
    if not _TOKEN_PATTERN.fullmatch(token):
        raise SearchStateError("could not issue a valid search approval token")
    grant = SearchApprovalGrant(
        plan_sha256=search_approval_plan_sha256(validated_plan),
        token_sha256=_approval_token_sha256(token),
        issued_at=validated_now,
        expires_at=validated_plan.expires_at,
        consumed_at=None,
    )
    return IssuedSearchApproval(
        session=_advance(validated, now=validated_now, approval=grant),
        token=token,
    )


def consume_search_approval(
    session: SearchSessionSnapshot,
    *,
    approval_ledger: InMemoryApprovalLedger,
    token: str,
    plan: SearchApprovalPlan,
    outscraper_reservation: UsageReservation,
    owner_id: str,
    session_id: str,
    expected_revision: int,
    now: datetime,
) -> SearchSessionSnapshot:
    validated = _prepare_transition(
        session,
        expected_revision=expected_revision,
        allowed_states={"search_approval"},
        now=now,
    )
    if owner_id != validated.owner_id or session_id != validated.session_id:
        raise SearchStateError("approval owner or session does not match")
    if validated.approval is None:
        raise SearchStateError("search approval has not been issued")

    validated_plan = _validated_plan_for_session(validated, plan)
    plan_sha256 = search_approval_plan_sha256(validated_plan)
    if not hmac.compare_digest(validated.approval.plan_sha256, plan_sha256):
        raise SearchStateError("approved plan does not match")
    if validated.approval.expires_at != validated_plan.expires_at:
        raise SearchStateError("approved plan expiry does not match")

    validated_now = _utc_datetime(now, field_name="now")
    if validated_now >= validated.approval.expires_at:
        raise SearchStateError("search approval has expired")
    if type(token) is not str or not _TOKEN_PATTERN.fullmatch(token):
        raise SearchStateError("approval token does not match")
    if not hmac.compare_digest(
        validated.approval.token_sha256,
        _approval_token_sha256(token),
    ):
        raise SearchStateError("approval token does not match")

    _validated_outscraper_reservation(
        validated,
        validated_plan,
        outscraper_reservation,
        plan_sha256=plan_sha256,
        now=validated_now,
    )
    if not isinstance(approval_ledger, InMemoryApprovalLedger):
        raise TypeError("approval_ledger must be an InMemoryApprovalLedger")
    approval_ledger.claim(
        validated.approval,
        owner_id=validated.owner_id,
        session_id=validated.session_id,
        now=validated_now,
    )

    consumed_grant = SearchApprovalGrant(
        plan_sha256=validated.approval.plan_sha256,
        token_sha256=validated.approval.token_sha256,
        issued_at=validated.approval.issued_at,
        expires_at=validated.approval.expires_at,
        consumed_at=validated_now,
    )
    return _advance(
        validated,
        now=validated_now,
        state="scrape_submitted",
        approval=consumed_grant,
    )


def record_products_received(
    session: SearchSessionSnapshot,
    *,
    received_candidate_count: int,
    expected_revision: int,
    now: datetime,
) -> SearchSessionSnapshot:
    validated = _prepare_transition(
        session,
        expected_revision=expected_revision,
        allowed_states={"scrape_submitted"},
        now=now,
    )
    return _advance(
        validated,
        now=now,
        state="products_received",
        received_candidate_count=received_candidate_count,
    )


def record_products_normalized(
    session: SearchSessionSnapshot,
    *,
    normalized_product_count: int,
    rejected_candidate_count: int,
    normalized_product_batch_sha256: str,
    expected_revision: int,
    now: datetime,
) -> SearchSessionSnapshot:
    validated = _prepare_transition(
        session,
        expected_revision=expected_revision,
        allowed_states={"products_received"},
        now=now,
    )
    return _advance(
        validated,
        now=now,
        state="products_normalized",
        normalized_product_count=normalized_product_count,
        rejected_candidate_count=rejected_candidate_count,
        normalized_product_batch_sha256=_validated_digest(
            normalized_product_batch_sha256,
            field_name="normalized_product_batch_sha256",
        ),
    )


def record_search_completed(
    session: SearchSessionSnapshot,
    *,
    ranked_product_count: int,
    ranked_product_batch_sha256: str,
    expected_revision: int,
    now: datetime,
) -> SearchSessionSnapshot:
    if type(ranked_product_count) is not int or not 0 <= ranked_product_count <= 48:
        raise SearchStateError("ranked product count is invalid")
    validated = _prepare_transition(
        session,
        expected_revision=expected_revision,
        allowed_states={"products_normalized"},
        now=now,
    )
    return _advance(
        validated,
        now=now,
        state="search_completed",
        ranked_product_count=ranked_product_count,
        ranked_product_batch_sha256=_validated_digest(
            ranked_product_batch_sha256,
            field_name="ranked_product_batch_sha256",
        ),
        result_outcome="results" if ranked_product_count > 0 else "empty",
    )


def record_search_failed(
    session: SearchSessionSnapshot,
    *,
    failure_stage: SearchFailureStage,
    expected_revision: int,
    now: datetime,
) -> SearchSessionSnapshot:
    allowed_state = {
        "product_search": "scrape_submitted",
        "product_normalization": "products_received",
        "ranking": "products_normalized",
    }.get(failure_stage)
    if allowed_state is None:
        raise SearchStateError("search failure stage is invalid")
    validated = _prepare_transition(
        session,
        expected_revision=expected_revision,
        allowed_states={allowed_state},
        now=now,
    )
    failure_code: SearchFailureCode = {
        "product_search": "product_search_failed",
        "product_normalization": "product_normalization_failed",
        "ranking": "ranking_failed",
    }[failure_stage]
    return _advance(
        validated,
        now=now,
        state="search_failed",
        failure_stage=failure_stage,
        failure_code=failure_code,
    )


def _prepare_transition(
    session: SearchSessionSnapshot,
    *,
    expected_revision: int,
    allowed_states: set[str],
    now: datetime,
) -> SearchSessionSnapshot:
    try:
        validated = SearchSessionSnapshot.model_validate(session)
    except ValueError as exc:
        raise SearchStateError("search session snapshot is invalid") from exc
    if type(expected_revision) is not int or expected_revision != validated.revision:
        raise SearchStateError("stale session revision")
    if validated.state not in allowed_states:
        raise SearchStateError("state transition is not allowed")
    validated_now = _utc_datetime(now, field_name="now")
    if validated_now < validated.updated_at:
        raise SearchStateError("state transition time precedes the current snapshot")
    return validated


def _advance(
    session: SearchSessionSnapshot,
    *,
    now: datetime,
    **updates,
) -> SearchSessionSnapshot:
    payload = session.model_dump(mode="python")
    payload.update(updates)
    payload["revision"] = session.revision + 1
    payload["updated_at"] = _utc_datetime(now, field_name="now")
    try:
        return SearchSessionSnapshot.model_validate(payload)
    except ValueError as exc:
        raise SearchStateError("state transition produced an invalid snapshot") from exc


def _validated_intent_plan(
    intent: NormalizedSearchIntent,
    query_plan: SearchQueryPlan | None,
    typed_proposal: TypedRequirementProposal,
) -> tuple[NormalizedSearchIntent, SearchQueryPlan | None, TypedRequirementProposal]:
    try:
        if type(typed_proposal) is not TypedRequirementProposal:
            raise TypeError("typed proposal must be exact")
        validated_intent = NormalizedSearchIntent.model_validate(intent)
        validated_proposal = TypedRequirementProposal.model_validate(typed_proposal)
        expected_proposal = build_typed_requirement_proposal(validated_intent)
    except (TypeError, ValueError) as exc:
        raise SearchStateError("intent, query plan, or typed proposal is invalid") from exc
    if validated_proposal != expected_proposal:
        raise SearchStateError("typed proposal does not match intent")
    if validated_proposal.status == "blocking":
        if query_plan is not None:
            raise SearchStateError("blocking typed proposal must not include a query plan")
        return validated_intent, None, validated_proposal
    if query_plan is None:
        raise SearchStateError("ready typed proposal requires a query plan")
    try:
        validated_query_plan = SearchQueryPlan.model_validate(query_plan)
    except ValueError as exc:
        raise SearchStateError("intent, query plan, or typed proposal is invalid") from exc
    if not hmac.compare_digest(
        validated_query_plan.intent_sha256,
        search_intent_sha256(validated_intent),
    ):
        raise SearchStateError("query plan does not match intent")
    return validated_intent, validated_query_plan, validated_proposal


def _validated_image_reservation(
    session: SearchSessionSnapshot,
    reservation: UsageReservation | None,
    *,
    now: datetime,
) -> UsageReservation:
    if reservation is None:
        raise SearchStateError("started image reservation is required")
    try:
        validated = UsageReservation.model_validate(reservation)
    except ValueError as exc:
        raise SearchStateError("started image reservation is invalid") from exc
    if (
        validated.status != "started"
        or validated.provider != "cloudflare"
        or validated.operation != "image_set"
        or validated.owner_id != session.owner_id
        or validated.session_id != session.session_id
        or validated.amount.calls != 4
        or validated.amount.tokens != 0
        or not hmac.compare_digest(
            validated.binding_sha256,
            session.query_plan_sha256 or "",
        )
    ):
        raise SearchStateError("started image reservation does not match the session")
    validated_now = _utc_datetime(now, field_name="now")
    if validated.started_at is None or validated.started_at > validated_now:
        raise SearchStateError("started image reservation time is invalid")
    return validated


def _validated_plan_for_session(
    session: SearchSessionSnapshot,
    plan: SearchApprovalPlan,
) -> SearchApprovalPlan:
    try:
        validated = SearchApprovalPlan.model_validate(plan)
    except ValueError as exc:
        raise SearchStateError("approved plan is invalid") from exc
    if validated.owner_id != session.owner_id or validated.session_id != session.session_id:
        raise SearchStateError("approved plan owner or session does not match")
    if not hmac.compare_digest(validated.intent_sha256, session.intent_sha256 or ""):
        raise SearchStateError("approved plan intent does not match")
    if not hmac.compare_digest(
        search_query_plan_sha256(validated.query_plan),
        session.query_plan_sha256 or "",
    ):
        raise SearchStateError("approved plan query does not match")
    if not hmac.compare_digest(
        validated.typed_requirement_proposal_sha256,
        session.typed_requirement_proposal_sha256 or "",
    ):
        raise SearchStateError("approved plan typed proposal does not match")
    if session.image_mode == "off":
        if validated.image_mode != "off":
            raise SearchStateError("approved plan image mode does not match")
    else:
        if (
            validated.image_mode != "approved"
            or not hmac.compare_digest(
                validated.image_set_sha256 or "",
                session.image_set_sha256 or "",
            )
            or not hmac.compare_digest(
                validated.image_request_metadata_sha256 or "",
                session.image_request_metadata_sha256 or "",
            )
        ):
            raise SearchStateError("approved plan image bindings do not match")
        if not hmac.compare_digest(
            validated.runtime_bindings.usage_policy_sha256,
            session.usage_policy_sha256 or "",
        ):
            raise SearchStateError("approved plan usage policy does not match")
    return validated


def _validated_completed_image_reservation(
    session: SearchSessionSnapshot,
    reservation: UsageReservation,
    *,
    now: datetime,
) -> UsageReservation:
    try:
        validated = UsageReservation.model_validate(reservation)
    except ValueError as exc:
        raise SearchStateError("succeeded image reservation is invalid") from exc
    if (
        validated.status != "succeeded"
        or validated.provider != "cloudflare"
        or validated.operation != "image_set"
        or validated.owner_id != session.owner_id
        or validated.session_id != session.session_id
        or validated.reservation_id != session.active_image_reservation_id
        or validated.amount.calls != 4
        or validated.amount.tokens != 0
        or not hmac.compare_digest(
            validated.binding_sha256,
            session.query_plan_sha256 or "",
        )
        or not hmac.compare_digest(
            validated.usage_policy_sha256,
            session.usage_policy_sha256 or "",
        )
    ):
        raise SearchStateError("succeeded image reservation does not match the session")
    validated_now = _utc_datetime(now, field_name="now")
    if validated.finished_at is None or validated.finished_at > validated_now:
        raise SearchStateError("succeeded image reservation time is invalid")
    return validated


def _validated_failed_image_reservation(
    session: SearchSessionSnapshot,
    reservation: UsageReservation,
    *,
    now: datetime,
) -> UsageReservation:
    try:
        validated = UsageReservation.model_validate(reservation)
    except ValueError as exc:
        raise SearchStateError("failed image reservation is invalid") from exc
    if (
        validated.status != "failed"
        or validated.provider != "cloudflare"
        or validated.operation != "image_set"
        or validated.owner_id != session.owner_id
        or validated.session_id != session.session_id
        or validated.reservation_id != session.active_image_reservation_id
        or validated.amount.calls != 4
        or validated.amount.tokens != 0
        or not hmac.compare_digest(
            validated.binding_sha256,
            session.query_plan_sha256 or "",
        )
        or not hmac.compare_digest(
            validated.usage_policy_sha256,
            session.usage_policy_sha256 or "",
        )
    ):
        raise SearchStateError("failed image reservation does not match the session")
    validated_now = _utc_datetime(now, field_name="now")
    if validated.finished_at is None or validated.finished_at > validated_now:
        raise SearchStateError("failed image reservation time is invalid")
    return validated


def _validated_outscraper_reservation(
    session: SearchSessionSnapshot,
    plan: SearchApprovalPlan,
    reservation: UsageReservation,
    *,
    plan_sha256: str,
    now: datetime,
) -> UsageReservation:
    try:
        validated = UsageReservation.model_validate(reservation)
    except ValueError as exc:
        raise SearchStateError("started Outscraper reservation is invalid") from exc
    allowance = next(item for item in plan.usage_allowances if item.provider == "outscraper")
    if (
        validated.status != "started"
        or validated.provider != "outscraper"
        or validated.operation != "product_search"
        or validated.owner_id != session.owner_id
        or validated.session_id != session.session_id
        or validated.amount.calls != 1
        or validated.amount.tokens > allowance.tokens
        or validated.amount.cost_microusd > allowance.cost_microusd
        or not hmac.compare_digest(validated.binding_sha256, plan_sha256)
        or not hmac.compare_digest(
            validated.request.pricing_policy_sha256,
            allowance.pricing_policy_sha256,
        )
        or not hmac.compare_digest(
            validated.usage_policy_sha256,
            plan.runtime_bindings.usage_policy_sha256,
        )
    ):
        raise SearchStateError("started Outscraper reservation does not match approval")
    if validated.started_at is None or validated.started_at > now:
        raise SearchStateError("started Outscraper reservation time is invalid")
    if session.approval is None or validated.started_at < session.approval.issued_at:
        raise SearchStateError("Outscraper reservation started before search approval")
    return validated


def _validated_digest(value: str, *, field_name: str) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise SearchStateError(f"{field_name} is not a SHA-256 digest")
    return value


def _approval_token_sha256(token: str) -> str:
    return hashlib.sha256(
        b"amazon-explorer-search-approval-token-v2\n" + token.encode("ascii")
    ).hexdigest()
