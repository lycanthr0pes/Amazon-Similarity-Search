"""Version-separated counterfactual branch from the current intent review."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import hashlib
import hmac
import json
import secrets
from typing import Callable
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationError
from pydantic import model_validator

from src.search_v2.counterfactual_cloudflare_http import (
    CounterfactualCloudflareDerivedExecution,
)
from src.search_v2.counterfactual_cloudflare_http import (
    CounterfactualCloudflareReferenceExecution,
)
from src.search_v2.counterfactual_cloudflare_http import CounterfactualCloudflareTransport
from src.search_v2.counterfactual_image import VisualConditionSet
from src.search_v2.counterfactual_image import visual_condition_set_sha256
from src.search_v2.counterfactual_reference_approval import ApprovedCounterfactualReferences
from src.search_v2.counterfactual_reference_approval import (
    approve_counterfactual_reference_artifacts,
)
from src.search_v2.intent import search_intent_sha256
from src.search_v2.orchestrator import IntentReview
from src.search_v2.orchestrator import ImageReview
from src.search_v2.orchestrator import ProviderAttemptBudget
from src.search_v2.orchestrator import ReferenceReview
from src.search_v2.orchestrator import SearchBackendPolicy
from src.search_v2.orchestrator import _validate_current_images
from src.search_v2.orchestrator import approve_reference_image
from src.search_v2.orchestrator import generate_images
from src.search_v2.provisional_approval_repository import (
    CounterfactualReferenceApprovalReview,
)
from src.search_v2.provisional_approval_repository import (
    IssuedCounterfactualReferenceApproval,
)
from src.search_v2.provisional_approval_repository import (
    SqliteCounterfactualApprovalRepository,
)
from src.search_v2.provisional_counterfactual import (
    provisional_counterfactual_profile_sha256,
)
from src.search_v2.query_planner import search_query_plan_sha256
from src.search_v2.typed_intent_adapter import typed_requirement_proposal_sha256
from src.search_v2.usage_ledger import Digest
from src.search_v2.usage_ledger import InMemoryUsageLedger


_PLAN_DOMAIN = b"amazon-explorer-provisional-orchestrator-plan-v5\x00"
_INVALID_INPUT_MESSAGE = "Provisional search orchestration inputs are invalid"


class ProvisionalOrchestrationError(ValueError):
    """A fixed-message rejection before the provisional branch performs a call."""


class _StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


def _same_digest(left: object, right: object) -> bool:
    return type(left) is str and type(right) is str and hmac.compare_digest(left, right)


def _utc_now(now: Callable[[], datetime]) -> datetime:
    try:
        value = now()
        if type(value) is not datetime or value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("provisional orchestration time must use UTC")
        return value.astimezone(timezone.utc)
    except Exception as exc:
        raise ProvisionalOrchestrationError(_INVALID_INPUT_MESSAGE) from exc


def provisional_preimage_plan_sha256(
    stage: IntentReview,
    condition_set: VisualConditionSet,
    cloudflare_budget: ProviderAttemptBudget,
) -> str:
    try:
        review = IntentReview.model_validate(stage)
        conditions = VisualConditionSet.model_validate(condition_set)
        budget = ProviderAttemptBudget.model_validate(cloudflare_budget)
        payload = json.dumps(
            {
                "schema_version": "5.0",
                "owner_id": review.session.owner_id,
                "session_id": review.session.session_id,
                "intent_sha256": search_intent_sha256(review.intent),
                "query_plan_sha256": search_query_plan_sha256(review.query_plan),
                "typed_requirement_proposal_sha256": typed_requirement_proposal_sha256(
                    review.typed_proposal
                ),
                "condition_set_sha256": visual_condition_set_sha256(conditions),
                "provisional_profile_sha256": provisional_counterfactual_profile_sha256(),
                "cloudflare_budget": budget.model_dump(mode="json"),
            },
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(_PLAN_DOMAIN + payload).hexdigest()
    except (TypeError, ValueError, ValidationError) as exc:
        raise ProvisionalOrchestrationError(_INVALID_INPUT_MESSAGE) from exc


class ProvisionalReferenceReview(_StrictFrozenContract):
    schema_version: Literal["5.0"]
    source_intent_review: IntentReview = Field(repr=False)
    condition_set: VisualConditionSet = Field(repr=False)
    preimage_plan_sha256: Digest
    execution: (
        CounterfactualCloudflareReferenceExecution | CounterfactualCloudflareDerivedExecution
    ) = Field(repr=False)
    approval_review: CounterfactualReferenceApprovalReview = Field(repr=False)
    image_review: ImageReview | None = Field(default=None, repr=False)

    @model_validator(mode="after")
    def validate_bindings(self) -> ProvisionalReferenceReview:
        source = self.source_intent_review
        conditions = self.condition_set
        execution = self.execution
        approval = self.approval_review
        reservation = execution.usage_reservation
        if (
            source.session.state != "intent_review"
            or source.typed_proposal.status != "ready"
            or not _same_digest(
                execution.request_set.intent_sha256,
                search_intent_sha256(source.intent),
            )
            or not _same_digest(
                execution.request_set.condition_set_sha256,
                visual_condition_set_sha256(conditions),
            )
            or not _same_digest(
                execution.request_set.preimage_plan_sha256, self.preimage_plan_sha256
            )
            or approval.owner_id != source.session.owner_id
            or approval.session_id != source.session.session_id
            or not _same_digest(
                approval.condition_set_sha256,
                execution.request_set.condition_set_sha256,
            )
            or not _same_digest(approval.reference_set_sha256, execution.reference_set_sha256)
            or not _same_digest(
                approval.request_metadata_sha256,
                execution.request_metadata_sha256,
            )
            or approval.usage_reservation_id != reservation.reservation_id
            or not _same_digest(approval.usage_policy_sha256, reservation.usage_policy_sha256)
            or not _same_digest(approval.usage_binding_sha256, reservation.binding_sha256)
            or approval.call_count != execution.request_set.call_count
        ):
            raise ValueError("provisional reference review binding is invalid")
        if isinstance(execution, CounterfactualCloudflareDerivedExecution):
            if (
                self.image_review is None
                or self.image_review.counterfactual_execution != execution
                or self.image_review.reference_review is None
                or self.image_review.reference_review.source_intent_review != source
            ):
                raise ValueError("provisional derived image review is incomplete")
        elif self.image_review is not None:
            raise ValueError("legacy provisional review contains unrelated image evidence")
        return self


@dataclass(frozen=True, slots=True, repr=False)
class IssuedProvisionalReferenceReview:
    review: ProvisionalReferenceReview
    approval_token: str


def generate_provisional_reference_review(
    stage: IntentReview,
    *,
    source_input: str,
    condition_set: VisualConditionSet,
    policy: SearchBackendPolicy,
    usage_ledger: InMemoryUsageLedger,
    account_id: str,
    api_token: str,
    transport: CounterfactualCloudflareTransport,
    now: Callable[[], datetime],
) -> ReferenceReview:
    """Generate one reference and stop before issuing any final artifact approval."""
    return generate_images(
        stage,
        source_input=source_input,
        condition_set=condition_set,
        policy=policy,
        usage_ledger=usage_ledger,
        account_id=account_id,
        api_token=api_token,
        transport=transport,
        now=now,
    )


def generate_provisional_images(
    stage: ReferenceReview,
    *,
    human_confirmed: Literal[True],
    policy: SearchBackendPolicy,
    usage_ledger: InMemoryUsageLedger,
    approval_repository: SqliteCounterfactualApprovalRepository,
    account_id: str,
    api_token: str,
    transport: CounterfactualCloudflareTransport,
    now: Callable[[], datetime],
    token_factory: Callable[[], str] = lambda: secrets.token_urlsafe(32),
) -> IssuedProvisionalReferenceReview:
    """Generate the approved views and comparisons, then await final artifact review."""
    if not isinstance(approval_repository, SqliteCounterfactualApprovalRepository):
        raise ProvisionalOrchestrationError(_INVALID_INPUT_MESSAGE)
    images = approve_reference_image(
        stage,
        human_confirmed=human_confirmed,
        policy=policy,
        usage_ledger=usage_ledger,
        account_id=account_id,
        api_token=api_token,
        transport=transport,
        now=now,
    )
    if not isinstance(images, ImageReview):
        raise ProvisionalOrchestrationError("Provisional image generation did not complete")
    reference = images.reference_review
    execution = images.counterfactual_execution
    if reference is None or execution is None:
        raise ProvisionalOrchestrationError(_INVALID_INPUT_MESSAGE)
    source = reference.source_intent_review
    issued: IssuedCounterfactualReferenceApproval = approval_repository.issue(
        owner_id=source.session.owner_id,
        session_id=source.session.session_id,
        condition_set_sha256=visual_condition_set_sha256(reference.condition_set),
        reference_set_sha256=execution.reference_set_sha256,
        request_metadata_sha256=execution.request_metadata_sha256,
        usage_reservation=execution.usage_reservation,
        reference_image_reservation=reference.usage_reservations[-1],
        now=_utc_now(now),
        token_factory=token_factory,
    )
    review = ProvisionalReferenceReview(
        schema_version="5.0",
        source_intent_review=source,
        condition_set=reference.condition_set,
        preimage_plan_sha256=reference.request.preimage_plan_sha256,
        execution=execution,
        approval_review=issued.review,
        image_review=images,
    )
    return IssuedProvisionalReferenceReview(review=review, approval_token=issued.token)


def approve_provisional_reference_review(
    stage: ProvisionalReferenceReview,
    *,
    approval_token: str,
    human_confirmed: Literal[True],
    approval_repository: SqliteCounterfactualApprovalRepository,
    now: Callable[[], datetime],
) -> ApprovedCounterfactualReferences:
    """Atomically consume the human approval and materialize local references."""
    try:
        review = ProvisionalReferenceReview.model_validate(stage)
    except (TypeError, ValueError, ValidationError) as exc:
        raise ProvisionalOrchestrationError(_INVALID_INPUT_MESSAGE) from exc
    if review.image_review is not None:
        _validate_current_images(review.image_review, None)
    receipt = approval_repository.consume(
        review=review.approval_review,
        token=approval_token,
        human_confirmed=human_confirmed,
        now=_utc_now(now),
    )
    execution = review.execution
    return approve_counterfactual_reference_artifacts(
        condition_set=review.condition_set,
        request_set=execution.request_set,
        images=execution.images,
        reference_set_sha256=execution.reference_set_sha256,
        request_metadata_sha256=execution.request_metadata_sha256,
        approval_receipt=receipt,
    )
