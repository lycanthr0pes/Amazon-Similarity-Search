from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import hashlib
import hmac
import json
import re
import threading
import weakref
from typing import Annotated
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import ValidationError
from pydantic import model_validator

from src.search_v2.approval import ApprovedUsage
from src.search_v2.approval import SearchApprovalPlan
from src.search_v2.approval import SearchRuntimeBindings
from src.search_v2.approval import build_search_approval_plan
from src.search_v2.approval import search_approval_plan_sha256
from src.search_v2.bonsai_request import BonsaiIntentRequest
from src.search_v2.bonsai_request import BonsaiRequestTransport
from src.search_v2.bonsai_request import bonsai_intent_request_sha256
from src.search_v2.bonsai_request import build_bonsai_intent_request
from src.search_v2.bonsai_request import execute_bonsai_intent_request
from src.search_v2.cloudflare_http import CloudflareImageSetExecution
from src.search_v2.cloudflare_http import CloudflareExecutionError
from src.search_v2.cloudflare_http import CloudflareRequestTransport
from src.search_v2.cloudflare_http import execute_cloudflare_image_set
from src.search_v2.cloudflare_request import CLOUDFLARE_IMAGE_MODEL_ID
from src.search_v2.cloudflare_request import image_prompt_contract_sha256
from src.search_v2.counterfactual_cloudflare_http import (
    CounterfactualCloudflareImageArtifact,
    CounterfactualCloudflareDerivedExecution,
    _desired_reference_png,
    execute_counterfactual_desired_image,
    execute_counterfactual_derived_images,
)
from src.search_v2.counterfactual_cloudflare_request import (
    CounterfactualCloudflareRequest,
    build_counterfactual_cloudflare_desired_request,
    counterfactual_cloudflare_request_sha256,
)
from src.search_v2.counterfactual_image import VisualConditionSet
from src.search_v2.counterfactual_cloudflare_http import CloudflareFailureDiagnostic
from src.search_v2.counterfactual_cloudflare_http import CounterfactualCloudflareExecutionError
from src.search_v2.counterfactual_image import VisualConditionDraft
from src.search_v2.counterfactual_image import build_visual_condition_set
from src.search_v2.counterfactual_image import visual_condition_set_sha256
from src.search_v2.intent import NormalizedSearchIntent
from src.search_v2.intent import search_intent_sha256
from src.search_v2.outscraper_http import OutscraperExecutionError
from src.search_v2.outscraper_http import OutscraperProductExecution
from src.search_v2.outscraper_http import OutscraperRequestTransport
from src.search_v2.outscraper_http import execute_outscraper_request
from src.search_v2.outscraper_request import AuthorizedOutscraperRequest
from src.search_v2.outscraper_request import OutscraperAmazonProductsRequest
from src.search_v2.outscraper_request import authorize_outscraper_request
from src.search_v2.outscraper_request import build_outscraper_request
from src.search_v2.outscraper_request import outscraper_request_sha256
from src.search_v2.product_normalization import ProductNormalizationProfile
from src.search_v2.product_normalization import product_normalization_profile_sha256
from src.search_v2.product_evidence import product_evidence_profile_sha256
from src.search_v2.product_pipeline import ProductSearchPipelineResult
from src.search_v2.product_pipeline import complete_product_search
from src.search_v2.product_pipeline import fail_product_search
from src.search_v2.query_planner import SearchQueryPlan
from src.search_v2.query_planner import build_search_query_plan
from src.search_v2.query_planner import search_query_plan_sha256
from src.search_v2.state_machine import InMemoryApprovalLedger
from src.search_v2.state_machine import MAX_IMAGE_SET_ATTEMPTS
from src.search_v2.state_machine import SearchSessionSnapshot
from src.search_v2.state_machine import approve_image_review
from src.search_v2.state_machine import approve_intent_review
from src.search_v2.state_machine import create_search_session
from src.search_v2.state_machine import discard_failed_image_attempt
from src.search_v2.state_machine import discard_image_set
from src.search_v2.state_machine import issue_search_approval
from src.search_v2.state_machine import record_counterfactual_images
from src.search_v2.state_machine import record_intent_plan
from src.search_v2.state_machine import record_image_generation_failure
from src.search_v2.state_machine import start_intent_processing
from src.search_v2.typed_intent_adapter import TypedRequirementProposal
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_intent_adapter import typed_requirement_proposal_sha256
from src.search_v2.typed_ranking import TypedRankingProfile
from src.search_v2.typed_ranking import typed_ranking_profile_sha256
from src.search_v2.usage_ledger import Digest
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import UsageAmount
from src.search_v2.usage_ledger import UsageReservation
from src.search_v2.usage_ledger import UsageReservationRequest
from src.search_v2.usage_ledger import usage_policy_sha256


_INVALID_INPUT_MESSAGE = "Search orchestration inputs are invalid"
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43,128}$")

BoundedUrl = Annotated[str, StringConstraints(min_length=1, max_length=2_048)]
BoundedIdentifier = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class SearchOrchestrationError(ValueError):
    """A fixed-message rejection before an unapproved provider call."""


class StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


class ProviderAttemptBudget(StrictFrozenContract):
    amount: UsageAmount
    pricing_policy_sha256: Digest


class BonsaiIntentConfig(StrictFrozenContract):
    base_url: BoundedUrl
    model_id: BoundedIdentifier
    temperature: Annotated[float, Field(ge=0.0, le=2.0)]


class SearchBackendPolicy(StrictFrozenContract):
    schema_version: Literal["3.0"]
    bonsai_intent: ProviderAttemptBudget
    cloudflare_image_set: ProviderAttemptBudget
    outscraper_search: ProviderAttemptBudget
    normalization_profile: ProductNormalizationProfile
    ranking_profile: TypedRankingProfile
    implementation_sha256: Digest

    @model_validator(mode="after")
    def validate_attempt_shapes(self) -> SearchBackendPolicy:
        if (
            self.bonsai_intent.amount.calls != 1
            or self.bonsai_intent.amount.tokens < 1
            or self.cloudflare_image_set.amount.calls != 4
            or self.cloudflare_image_set.amount.tokens != 0
            or self.outscraper_search.amount.calls != 1
            or self.outscraper_search.amount.tokens != 0
        ):
            raise ValueError("provider attempt budget does not match the operation")
        return self


def _same_digest(left: str | None, right: str | None) -> bool:
    return type(left) is str and type(right) is str and hmac.compare_digest(left, right)


def _validate_intent_binding(
    *,
    session: SearchSessionSnapshot,
    intent: NormalizedSearchIntent,
    query_plan: SearchQueryPlan | None,
    typed_proposal: TypedRequirementProposal,
    request: BonsaiIntentRequest,
    reservation: UsageReservation,
) -> None:
    intent_digest = search_intent_sha256(intent)
    proposal_digest = typed_requirement_proposal_sha256(typed_proposal)
    expected_proposal = build_typed_requirement_proposal(intent)
    if (
        not _same_digest(session.intent_sha256, intent_digest)
        or typed_proposal != expected_proposal
        or not _same_digest(session.typed_requirement_proposal_sha256, proposal_digest)
        or session.typed_requirement_status != typed_proposal.status
        or not _same_digest(request.source_input_sha256, intent.provenance.source_input_sha256)
        or not _same_digest(request.prompt_sha256, intent.provenance.prompt_sha256)
        or not _same_digest(request.schema_sha256, intent.provenance.schema_sha256)
        or reservation.status != "succeeded"
        or reservation.provider != "bonsai"
        or reservation.operation != "intent"
        or reservation.owner_id != session.owner_id
        or reservation.session_id != session.session_id
        or reservation.amount.calls != 1
        or reservation.amount.tokens < request.maximum_usage_tokens
        or not _same_digest(
            reservation.binding_sha256,
            bonsai_intent_request_sha256(request),
        )
        or reservation.finished_at is None
        or reservation.finished_at > session.updated_at
    ):
        raise ValueError("intent review binding is invalid")
    if typed_proposal.status == "blocking":
        if query_plan is not None or session.query_plan_sha256 is not None:
            raise ValueError("intent review binding is invalid")
        return
    if query_plan is None:
        raise ValueError("intent review binding is invalid")
    query_digest = search_query_plan_sha256(query_plan)
    if not _same_digest(session.query_plan_sha256, query_digest) or not _same_digest(
        query_plan.intent_sha256,
        intent_digest,
    ):
        raise ValueError("intent review binding is invalid")


def _validate_image_usage_history(
    *,
    session: SearchSessionSnapshot,
    query_plan: SearchQueryPlan,
    bonsai_reservation: UsageReservation,
    reservations: tuple[UsageReservation, ...],
    final_status: Literal["succeeded", "failed"],
    reference_review: ReferenceReview | None = None,
) -> None:
    query_digest = search_query_plan_sha256(query_plan)
    operation = "image_set"
    calls = 4
    if reference_review is not None:
        query_digest = reference_review.request.preimage_plan_sha256
        operation = "counterfactual_images"
        calls = len(reference_review.condition_set.conditions)
    seen_ids: set[str] = set()
    prior_finished_at: datetime | None = None
    for index, reservation in enumerate(reservations):
        expected_status = final_status if index == len(reservations) - 1 else None
        if (
            reservation.reservation_id in seen_ids
            or reservation.status not in {"succeeded", "failed"}
            or (expected_status is not None and reservation.status != expected_status)
            or reservation.provider != "cloudflare"
            or reservation.operation != operation
            or reservation.owner_id != session.owner_id
            or reservation.session_id != session.session_id
            or reservation.amount.calls != calls
            or reservation.amount.tokens != 0
            or not _same_digest(reservation.binding_sha256, query_digest)
            or not _same_digest(
                reservation.usage_policy_sha256,
                bonsai_reservation.usage_policy_sha256,
            )
            or reservation.started_at is None
            or reservation.finished_at is None
            or reservation.finished_at > session.updated_at
            or (prior_finished_at is not None and reservation.started_at < prior_finished_at)
        ):
            raise ValueError("image usage binding is invalid")
        seen_ids.add(reservation.reservation_id)
        prior_finished_at = reservation.finished_at
    if not reservations:
        raise ValueError("image usage history is empty")


class IntentReview(StrictFrozenContract):
    schema_version: Literal["3.0"]
    session: SearchSessionSnapshot = Field(repr=False)
    intent: NormalizedSearchIntent = Field(repr=False)
    query_plan: SearchQueryPlan = Field(repr=False)
    typed_proposal: TypedRequirementProposal = Field(repr=False)
    bonsai_request: BonsaiIntentRequest = Field(repr=False)
    bonsai_usage_reservation: UsageReservation = Field(repr=False)

    @model_validator(mode="after")
    def validate_stage(self) -> IntentReview:
        if (
            self.session.state != "intent_review"
            or self.session.image_mode != "off"
            or self.session.approval is not None
        ):
            raise ValueError("intent review state is invalid")
        _validate_intent_binding(
            session=self.session,
            intent=self.intent,
            query_plan=self.query_plan,
            typed_proposal=self.typed_proposal,
            request=self.bonsai_request,
            reservation=self.bonsai_usage_reservation,
        )
        return self


class BlockingIntentReview(StrictFrozenContract):
    schema_version: Literal["3.0"]
    session: SearchSessionSnapshot = Field(repr=False)
    intent: NormalizedSearchIntent = Field(repr=False)
    typed_proposal: TypedRequirementProposal = Field(repr=False)
    bonsai_request: BonsaiIntentRequest = Field(repr=False)
    bonsai_usage_reservation: UsageReservation = Field(repr=False)

    @model_validator(mode="after")
    def validate_stage(self) -> BlockingIntentReview:
        if (
            self.session.state != "intent_review"
            or self.session.image_mode != "off"
            or self.session.approval is not None
            or self.typed_proposal.status != "blocking"
        ):
            raise ValueError("blocking intent review state is invalid")
        _validate_intent_binding(
            session=self.session,
            intent=self.intent,
            query_plan=None,
            typed_proposal=self.typed_proposal,
            request=self.bonsai_request,
            reservation=self.bonsai_usage_reservation,
        )
        return self


class ReferenceReview(StrictFrozenContract):
    """One generated image awaiting an explicit decision in this process."""

    schema_version: Literal["1.0"]
    status: Literal["reference_review", "reference_generation_failed"]
    source_intent_review: IntentReview = Field(repr=False)
    condition_set: VisualConditionSet = Field(repr=False)
    request: CounterfactualCloudflareRequest = Field(repr=False)
    image: CounterfactualCloudflareImageArtifact | None = Field(repr=False)
    usage_reservations: Annotated[
        tuple[UsageReservation, ...], Field(min_length=1, max_length=2, repr=False)
    ]
    prior_derived_usage: Annotated[
        tuple[UsageReservation, ...], Field(max_length=2, repr=False)
    ] = ()
    policy_sha256: Digest
    expires_at: datetime

    failure_diagnostic: CloudflareFailureDiagnostic | None = Field(default=None, repr=False)

    @model_validator(mode="after")
    def validate_reference(self) -> ReferenceReview:
        source = self.source_intent_review
        last = self.usage_reservations[-1]
        if (
            self.request.target != "desired"
            or self.request.intent_sha256 != search_intent_sha256(source.intent)
            or self.request.condition_set_sha256 != visual_condition_set_sha256(self.condition_set)
            or last.binding_sha256 != self.request.preimage_plan_sha256
            or any(
                item.operation != "reference_image"
                or item.provider != "cloudflare"
                or item.amount.calls != 1
                or item.amount.tokens != 0
                or item.owner_id != source.session.owner_id
                or item.session_id != source.session.session_id
                or item.status not in {"succeeded", "failed"}
                for item in self.usage_reservations
            )
            or last.finished_at is None
            or self.expires_at != last.finished_at + timedelta(minutes=15)
        ):
            raise ValueError("reference review binding is invalid")
        if self.status == "reference_review":
            if (
                self.image is None
                or self.failure_diagnostic is not None
                or last.status != "succeeded"
                or self.image.request_sha256
                != counterfactual_cloudflare_request_sha256(self.request)
            ):
                raise ValueError("reference review requires its generated image")
        elif self.image is not None or last.status != "failed":
            raise ValueError("failed reference review must not contain an image")
        for usage in self.prior_derived_usage:
            expected_binding = (
                source.session.query_plan_sha256
                if usage.operation == "image_set"
                else self.usage_reservations[0].binding_sha256
            )
            if (
                len(self.usage_reservations) != 2
                or usage.operation not in {"image_set", "counterfactual_images"}
                or usage.provider != "cloudflare"
                or usage.owner_id != source.session.owner_id
                or usage.session_id != source.session.session_id
                or usage.binding_sha256 != expected_binding
                or usage.status not in {"succeeded", "failed"}
                or usage.finished_at is None
                or usage.finished_at > last.reserved_at
            ):
                raise ValueError("prior derived usage is invalid")
        return self


_REFERENCE_LOCK = threading.Lock()
_REFERENCE_REVIEWS: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


class ImageReview(StrictFrozenContract):
    schema_version: Literal["3.0", "4.0"]
    session: SearchSessionSnapshot = Field(repr=False)
    intent: NormalizedSearchIntent = Field(repr=False)
    query_plan: SearchQueryPlan = Field(repr=False)
    typed_proposal: TypedRequirementProposal = Field(repr=False)
    bonsai_request: BonsaiIntentRequest = Field(repr=False)
    bonsai_usage_reservation: UsageReservation = Field(repr=False)
    execution: CloudflareImageSetExecution | None = Field(repr=False)
    image_usage_reservations: Annotated[
        tuple[UsageReservation, ...],
        Field(min_length=1, max_length=2, repr=False),
    ]
    reference_review: ReferenceReview | None = Field(default=None, repr=False)
    counterfactual_execution: CounterfactualCloudflareDerivedExecution | None = Field(
        default=None, repr=False
    )

    @model_validator(mode="after")
    def validate_stage(self) -> ImageReview:
        if (
            self.session.state != "image_review"
            or self.session.image_mode != "on"
            or self.session.approval is not None
            or self.session.image_attempts_started != len(self.image_usage_reservations)
        ):
            raise ValueError("image review state is invalid")
        if self.schema_version == "3.0":
            if (
                self.execution is None
                or self.execution.session != self.session
                or self.execution.usage_reservation != self.image_usage_reservations[-1]
                or self.execution.request_set.attempt != len(self.image_usage_reservations)
            ):
                raise ValueError("legacy image review requires its four-view execution")
        elif (
            self.execution is not None
            or self.reference_review is None
            or self.counterfactual_execution is None
            or self.image_usage_reservations != (self.counterfactual_execution.usage_reservation,)
            or self.session.image_set_sha256 != self.counterfactual_execution.reference_set_sha256
            or self.session.image_request_metadata_sha256
            != self.counterfactual_execution.request_metadata_sha256
        ):
            raise ValueError("reference image review requires only its comparisons")
        _validate_intent_binding(
            session=self.session,
            intent=self.intent,
            query_plan=self.query_plan,
            typed_proposal=self.typed_proposal,
            request=self.bonsai_request,
            reservation=self.bonsai_usage_reservation,
        )
        _validate_image_usage_history(
            session=self.session,
            query_plan=self.query_plan,
            bonsai_reservation=self.bonsai_usage_reservation,
            reservations=self.image_usage_reservations,
            final_status="succeeded",
            reference_review=self.reference_review if self.schema_version == "4.0" else None,
        )
        if (self.reference_review is None) != (self.counterfactual_execution is None):
            raise ValueError("reference approval and counterfactual result are required together")
        if self.reference_review is not None:
            reference = self.reference_review
            counterfactual = self.counterfactual_execution
            if (
                reference.image is None
                or reference.source_intent_review.intent != self.intent
                or reference.source_intent_review.query_plan != self.query_plan
                or reference.source_intent_review.session.owner_id != self.session.owner_id
                or reference.source_intent_review.session.session_id != self.session.session_id
                or counterfactual.images[0] != reference.image
                or counterfactual.request_set.requests[0] != reference.request
                or counterfactual.usage_reservation.owner_id != self.session.owner_id
                or counterfactual.usage_reservation.session_id != self.session.session_id
                or (
                    self.execution is not None
                    and any(
                        request.reference_image is None
                        or request.reference_image.body != _desired_reference_png(reference.image)
                        for request in self.execution.request_set.requests
                    )
                )
            ):
                raise ValueError("derived images do not match the approved reference")
        return self

    @property
    def all_image_usage(self) -> tuple[UsageReservation, ...]:
        if self.reference_review is None or self.counterfactual_execution is None:
            return self.image_usage_reservations
        derived_usage = self.image_usage_reservations
        if self.schema_version == "3.0":
            derived_usage = (*derived_usage, self.counterfactual_execution.usage_reservation)
        return (
            *self.reference_review.usage_reservations,
            *self.reference_review.prior_derived_usage,
            *derived_usage,
        )

    @property
    def reference_generation_sha256(self) -> str | None:
        if self.reference_review is None or self.counterfactual_execution is None:
            return None
        payload = (
            self.reference_review.model_dump_json()
            + self.counterfactual_execution.reference_set_sha256
            + self.counterfactual_execution.request_metadata_sha256
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ImageFailureReview(StrictFrozenContract):
    schema_version: Literal["3.0"]
    failure_code: Literal["image_generation_failed"]
    session: SearchSessionSnapshot = Field(repr=False)
    intent: NormalizedSearchIntent = Field(repr=False)
    query_plan: SearchQueryPlan = Field(repr=False)
    typed_proposal: TypedRequirementProposal = Field(repr=False)
    bonsai_request: BonsaiIntentRequest = Field(repr=False)
    bonsai_usage_reservation: UsageReservation = Field(repr=False)
    image_usage_reservations: Annotated[
        tuple[UsageReservation, ...],
        Field(min_length=1, max_length=2, repr=False),
    ]
    reference_review: ReferenceReview | None = Field(default=None, repr=False)

    @model_validator(mode="after")
    def validate_stage(self) -> ImageFailureReview:
        if (
            self.session.state != "image_generation_failed"
            or self.session.image_mode != "on"
            or self.session.approval is not None
            or self.session.image_attempts_started != len(self.image_usage_reservations)
            or self.session.failed_image_reservation_id
            != self.image_usage_reservations[-1].reservation_id
        ):
            raise ValueError("image failure review state is invalid")
        _validate_intent_binding(
            session=self.session,
            intent=self.intent,
            query_plan=self.query_plan,
            typed_proposal=self.typed_proposal,
            request=self.bonsai_request,
            reservation=self.bonsai_usage_reservation,
        )
        _validate_image_usage_history(
            session=self.session,
            query_plan=self.query_plan,
            bonsai_reservation=self.bonsai_usage_reservation,
            reservations=self.image_usage_reservations,
            final_status="failed",
        )
        if self.reference_review is not None and (
            self.reference_review.source_intent_review.intent != self.intent
            or self.reference_review.source_intent_review.query_plan != self.query_plan
            or self.reference_review.source_intent_review.session.owner_id != self.session.owner_id
            or self.reference_review.source_intent_review.session.session_id
            != self.session.session_id
        ):
            raise ValueError("failed derived images do not match their reference")
        return self


class SearchReview(StrictFrozenContract):
    schema_version: Literal["3.0"]
    session: SearchSessionSnapshot = Field(repr=False)
    intent: NormalizedSearchIntent = Field(repr=False)
    query_plan: SearchQueryPlan = Field(repr=False)
    typed_proposal: TypedRequirementProposal = Field(repr=False)
    request: OutscraperAmazonProductsRequest = Field(repr=False)
    plan: SearchApprovalPlan = Field(repr=False)
    bonsai_request: BonsaiIntentRequest = Field(repr=False)
    bonsai_usage_reservation: UsageReservation = Field(repr=False)
    image_review: ImageReview | None = Field(repr=False)
    normalization_profile: ProductNormalizationProfile
    ranking_profile: TypedRankingProfile
    implementation_sha256: Digest

    @model_validator(mode="after")
    def validate_stage(self) -> SearchReview:
        intent_digest = search_intent_sha256(self.intent)
        query_digest = search_query_plan_sha256(self.query_plan)
        request_queries = tuple((item.language, item.value) for item in self.request.queries)
        planned_queries = tuple((item.language, item.value) for item in self.query_plan.queries)
        allowances = {item.provider: item for item in self.plan.usage_allowances}
        if (
            self.session.state != "search_approval"
            or self.session.approval is not None
            or self.plan.owner_id != self.session.owner_id
            or self.plan.session_id != self.session.session_id
            or self.plan.intent != self.intent
            or self.plan.query_plan != self.query_plan
            or self.typed_proposal != build_typed_requirement_proposal(self.intent)
            or self.typed_proposal.status != "ready"
            or not _same_digest(self.session.intent_sha256, intent_digest)
            or not _same_digest(self.session.query_plan_sha256, query_digest)
            or not _same_digest(
                self.session.typed_requirement_proposal_sha256,
                typed_requirement_proposal_sha256(self.typed_proposal),
            )
            or self.session.typed_requirement_status != "ready"
            or not _same_digest(
                self.plan.typed_requirement_proposal_sha256,
                typed_requirement_proposal_sha256(self.typed_proposal),
            )
            or not _same_digest(self.request.query_plan_sha256, query_digest)
            or request_queries != planned_queries
            or not _same_digest(
                self.plan.outscraper_request_sha256,
                outscraper_request_sha256(self.request),
            )
            or self.plan.created_at != self.session.updated_at
            or self.plan.runtime_bindings.bonsai_model_id != self.bonsai_request.model_id
            or not _same_digest(
                self.plan.runtime_bindings.usage_policy_sha256,
                self.bonsai_usage_reservation.usage_policy_sha256,
            )
            or self.plan.runtime_bindings.ranking_profile_id != self.ranking_profile.profile_id
            or not _same_digest(
                self.plan.runtime_bindings.ranking_profile_sha256,
                typed_ranking_profile_sha256(self.ranking_profile),
            )
            or not _same_digest(
                self.plan.runtime_bindings.product_evidence_profile_sha256,
                product_evidence_profile_sha256(),
            )
            or not _same_digest(
                self.plan.runtime_bindings.implementation_sha256,
                _runtime_sha256(
                    implementation_sha256=self.implementation_sha256,
                    normalization_profile=self.normalization_profile,
                    ranking_profile=self.ranking_profile,
                ),
            )
        ):
            raise ValueError("search review binding is invalid")
        _validate_intent_binding(
            session=self.session,
            intent=self.intent,
            query_plan=self.query_plan,
            typed_proposal=self.typed_proposal,
            request=self.bonsai_request,
            reservation=self.bonsai_usage_reservation,
        )
        bonsai_allowance = allowances["bonsai"]
        if (
            bonsai_allowance.calls != self.bonsai_usage_reservation.amount.calls
            or bonsai_allowance.tokens != self.bonsai_usage_reservation.amount.tokens
            or bonsai_allowance.cost_microusd != self.bonsai_usage_reservation.amount.cost_microusd
            or not _same_digest(
                bonsai_allowance.pricing_policy_sha256,
                self.bonsai_usage_reservation.request.pricing_policy_sha256,
            )
        ):
            raise ValueError("search review Bonsai usage is invalid")
        if self.session.image_mode == "off":
            if self.plan.image_mode != "off" or self.image_review is not None:
                raise ValueError("search review image mode is invalid")
            return self
        if self.image_review is None:
            raise ValueError("search review image evidence is missing")
        cloudflare_allowance = allowances["cloudflare"]
        image_calls = sum(item.amount.calls for item in self.image_review.all_image_usage)
        image_tokens = sum(item.amount.tokens for item in self.image_review.all_image_usage)
        image_cost = sum(item.amount.cost_microusd for item in self.image_review.all_image_usage)
        if self.session.image_mode == "on" and (
            self.plan.image_mode != "approved"
            or self.image_review.intent != self.intent
            or self.image_review.query_plan != self.query_plan
            or self.image_review.typed_proposal != self.typed_proposal
            or self.plan.reference_generation_sha256
            != self.image_review.reference_generation_sha256
            or self.plan.image_generation_profile
            != (
                "reference_counterfactual"
                if self.image_review.schema_version == "4.0"
                else "legacy_four_views"
            )
            or not _same_digest(self.plan.image_set_sha256, self.session.image_set_sha256)
            or not _same_digest(
                self.plan.image_request_metadata_sha256,
                self.session.image_request_metadata_sha256,
            )
            or cloudflare_allowance.calls != image_calls
            or cloudflare_allowance.tokens != image_tokens
            or cloudflare_allowance.cost_microusd != image_cost
            or not _same_digest(
                cloudflare_allowance.pricing_policy_sha256,
                self.image_review.image_usage_reservations[-1].request.pricing_policy_sha256,
            )
        ):
            raise ValueError("search review image binding is invalid")
        return self


@dataclass(frozen=True, slots=True, repr=False)
class ApprovedSearch:
    review: SearchReview
    session: SearchSessionSnapshot
    token: str


def _raise_invalid_input() -> None:
    raise SearchOrchestrationError(_INVALID_INPUT_MESSAGE) from None


def _utc_now(now: Callable[[], datetime]) -> datetime:
    try:
        if not callable(now):
            _raise_invalid_input()
        value = now()
        if type(value) is not datetime or value.tzinfo is None or value.utcoffset() != timedelta(0):
            _raise_invalid_input()
        return value.astimezone(timezone.utc)
    except SearchOrchestrationError:
        raise
    except Exception:
        _raise_invalid_input()


def _policy_and_ledger(
    policy: SearchBackendPolicy,
    ledger: InMemoryUsageLedger,
) -> tuple[SearchBackendPolicy, str]:
    try:
        validated = SearchBackendPolicy.model_validate(policy)
        if not isinstance(ledger, InMemoryUsageLedger):
            _raise_invalid_input()
        snapshot = ledger.snapshot()
        policies = {item.provider: item for item in snapshot.policies}
        budgets = {
            "bonsai": validated.bonsai_intent,
            "cloudflare": validated.cloudflare_image_set,
            "outscraper": validated.outscraper_search,
        }
        if set(policies) != set(budgets) or any(
            not _same_digest(policies[name].pricing_policy_sha256, budget.pricing_policy_sha256)
            for name, budget in budgets.items()
        ):
            _raise_invalid_input()
        return validated, usage_policy_sha256(snapshot.policies)
    except SearchOrchestrationError:
        raise
    except (AttributeError, TypeError, ValidationError, ValueError):
        _raise_invalid_input()


def _current_reservation(
    ledger: InMemoryUsageLedger,
    reservation: UsageReservation,
) -> None:
    current = next(
        (
            item
            for item in ledger.snapshot().reservations
            if item.reservation_id == reservation.reservation_id
        ),
        None,
    )
    if current != reservation:
        _raise_invalid_input()


def _matching_budget(reservation: UsageReservation, budget: ProviderAttemptBudget) -> None:
    if reservation.amount != budget.amount or not _same_digest(
        reservation.request.pricing_policy_sha256,
        budget.pricing_policy_sha256,
    ):
        _raise_invalid_input()


def _runtime_sha256(
    *,
    implementation_sha256: str,
    normalization_profile: ProductNormalizationProfile,
    ranking_profile: TypedRankingProfile,
) -> str:
    payload = {
        "implementation_sha256": implementation_sha256,
        "normalization_profile_sha256": product_normalization_profile_sha256(normalization_profile),
        "product_evidence_profile_sha256": product_evidence_profile_sha256(),
        "ranking_profile_sha256": typed_ranking_profile_sha256(ranking_profile),
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(b"amazon-explorer-search-runtime-v3\n" + canonical).hexdigest()


def _reserve_usage(
    ledger: InMemoryUsageLedger,
    *,
    provider: Literal["bonsai", "cloudflare", "outscraper"],
    operation: Literal[
        "intent", "image_set", "reference_image", "counterfactual_images", "product_search"
    ],
    owner_id: str,
    session_id: str,
    binding_sha256: str,
    budget: ProviderAttemptBudget,
    now: datetime,
) -> UsageReservation:
    return ledger.reserve(
        UsageReservationRequest(
            provider=provider,
            operation=operation,
            owner_id=owner_id,
            session_id=session_id,
            binding_sha256=binding_sha256,
            amount=budget.amount,
            pricing_policy_sha256=budget.pricing_policy_sha256,
        ),
        now=now,
    )


def _start_usage(
    ledger: InMemoryUsageLedger,
    reservation: UsageReservation,
    *,
    now: Callable[[], datetime],
) -> UsageReservation:
    return ledger.start(
        reservation.reservation_id,
        owner_id=reservation.owner_id,
        session_id=reservation.session_id,
        now=_utc_now(now),
    )


def _validate_intent_review(
    stage: IntentReview,
    *,
    policy: SearchBackendPolicy,
    usage_ledger: InMemoryUsageLedger,
) -> IntentReview:
    try:
        validated = IntentReview.model_validate(stage)
    except (TypeError, ValidationError, ValueError):
        _raise_invalid_input()
    if validated.typed_proposal.status != "ready":
        _raise_invalid_input()
    validated_policy, _policy_digest = _policy_and_ledger(policy, usage_ledger)
    _current_reservation(usage_ledger, validated.bonsai_usage_reservation)
    _matching_budget(validated.bonsai_usage_reservation, validated_policy.bonsai_intent)
    return validated


def _validate_blocking_intent_review(
    stage: BlockingIntentReview,
    *,
    policy: SearchBackendPolicy,
    usage_ledger: InMemoryUsageLedger,
) -> BlockingIntentReview:
    try:
        validated = BlockingIntentReview.model_validate(stage)
    except (TypeError, ValidationError, ValueError):
        _raise_invalid_input()
    validated_policy, _policy_digest = _policy_and_ledger(policy, usage_ledger)
    _current_reservation(usage_ledger, validated.bonsai_usage_reservation)
    _matching_budget(validated.bonsai_usage_reservation, validated_policy.bonsai_intent)
    return validated


def _validate_image_review(
    stage: ImageReview,
    *,
    policy: SearchBackendPolicy,
    usage_ledger: InMemoryUsageLedger,
) -> ImageReview:
    try:
        validated = ImageReview.model_validate(stage)
    except (TypeError, ValidationError, ValueError):
        _raise_invalid_input()
    validated_policy, _policy_digest = _policy_and_ledger(policy, usage_ledger)
    _current_reservation(usage_ledger, validated.bonsai_usage_reservation)
    _matching_budget(validated.bonsai_usage_reservation, validated_policy.bonsai_intent)
    for reservation in validated.all_image_usage:
        _current_reservation(usage_ledger, reservation)
        if reservation.operation == "image_set":
            _matching_budget(reservation, validated_policy.cloudflare_image_set)
    _validate_current_images(validated, usage_ledger)
    return validated


def _validate_current_images(
    stage: ImageReview | ImageFailureReview, ledger: InMemoryUsageLedger | None
) -> None:
    if stage.reference_review is None:
        return
    reference = stage.reference_review
    with _REFERENCE_LOCK:
        repositories = (
            (_REFERENCE_REVIEWS.get(ledger, {}),)
            if ledger is not None
            else tuple(_REFERENCE_REVIEWS.values())
        )
        if not any(
            records.get(_reference_key(reference.source_intent_review)) == (reference, "consumed")
            for records in repositories
        ):
            _raise_invalid_input()


def _validate_image_failure_review(
    stage: ImageFailureReview,
    *,
    policy: SearchBackendPolicy,
    usage_ledger: InMemoryUsageLedger,
) -> ImageFailureReview:
    try:
        validated = ImageFailureReview.model_validate(stage)
    except (TypeError, ValidationError, ValueError):
        _raise_invalid_input()
    validated_policy, _policy_digest = _policy_and_ledger(policy, usage_ledger)
    _current_reservation(usage_ledger, validated.bonsai_usage_reservation)
    _matching_budget(validated.bonsai_usage_reservation, validated_policy.bonsai_intent)
    for reservation in validated.image_usage_reservations:
        _current_reservation(usage_ledger, reservation)
        _matching_budget(reservation, validated_policy.cloudflare_image_set)
    _validate_current_images(validated, usage_ledger)
    return validated


def start_intent_review(
    source_input: str,
    *,
    owner_id: str,
    session_id: str,
    bonsai_config: BonsaiIntentConfig,
    policy: SearchBackendPolicy,
    usage_ledger: InMemoryUsageLedger,
    transport: BonsaiRequestTransport,
    now: Callable[[], datetime],
) -> IntentReview | BlockingIntentReview:
    """Run one Bonsai attempt and stop with a deterministic intent review."""
    validated_policy, _policy_digest = _policy_and_ledger(policy, usage_ledger)
    try:
        config = BonsaiIntentConfig.model_validate(bonsai_config)
    except (TypeError, ValidationError, ValueError):
        _raise_invalid_input()
    prepared = build_bonsai_intent_request(
        source_input,
        base_url=config.base_url,
        model_id=config.model_id,
        temperature=config.temperature,
    )
    if validated_policy.bonsai_intent.amount.tokens < prepared.request.maximum_usage_tokens:
        _raise_invalid_input()

    session = create_search_session(
        owner_id=owner_id,
        session_id=session_id,
        now=_utc_now(now),
    )
    session = start_intent_processing(
        session,
        expected_revision=session.revision,
        now=_utc_now(now),
    )
    reserved = _reserve_usage(
        usage_ledger,
        provider="bonsai",
        operation="intent",
        owner_id=session.owner_id,
        session_id=session.session_id,
        binding_sha256=bonsai_intent_request_sha256(prepared.request),
        budget=validated_policy.bonsai_intent,
        now=_utc_now(now),
    )
    execution = execute_bonsai_intent_request(
        prepared,
        usage_ledger=usage_ledger,
        usage_reservation=reserved,
        transport=transport,
        now=now,
    )
    typed_proposal = build_typed_requirement_proposal(execution.intent)
    query_plan = (
        None if typed_proposal.status == "blocking" else build_search_query_plan(execution.intent)
    )
    session = record_intent_plan(
        session,
        intent=execution.intent,
        query_plan=query_plan,
        typed_proposal=typed_proposal,
        expected_revision=session.revision,
        now=_utc_now(now),
    )
    try:
        if typed_proposal.status == "blocking":
            return BlockingIntentReview(
                schema_version="3.0",
                session=session,
                intent=execution.intent,
                typed_proposal=typed_proposal,
                bonsai_request=execution.request,
                bonsai_usage_reservation=execution.usage_reservation,
            )
        if query_plan is None:
            _raise_invalid_input()
        return IntentReview(
            schema_version="3.0",
            session=session,
            intent=execution.intent,
            query_plan=query_plan,
            typed_proposal=typed_proposal,
            bonsai_request=execution.request,
            bonsai_usage_reservation=execution.usage_reservation,
        )
    except (TypeError, ValidationError, ValueError):
        _raise_invalid_input()


def _new_image_reservation(
    session: SearchSessionSnapshot,
    query_plan: SearchQueryPlan,
    *,
    policy: SearchBackendPolicy,
    usage_ledger: InMemoryUsageLedger,
    now: Callable[[], datetime],
) -> UsageReservation:
    reserved = _reserve_usage(
        usage_ledger,
        provider="cloudflare",
        operation="image_set",
        owner_id=session.owner_id,
        session_id=session.session_id,
        binding_sha256=search_query_plan_sha256(query_plan),
        budget=policy.cloudflare_image_set,
        now=_utc_now(now),
    )
    return _start_usage(usage_ledger, reserved, now=now)


def _failed_image_reservation(
    usage_ledger: InMemoryUsageLedger,
    started: UsageReservation,
) -> UsageReservation:
    current = next(
        (
            item
            for item in usage_ledger.snapshot().reservations
            if item.reservation_id == started.reservation_id
        ),
        None,
    )
    if current is None or current.status != "failed" or current.request != started.request:
        _raise_invalid_input()
    return current


def _build_image_failure_review(
    *,
    generating: SearchSessionSnapshot,
    intent: NormalizedSearchIntent,
    query_plan: SearchQueryPlan,
    typed_proposal: TypedRequirementProposal,
    bonsai_request: BonsaiIntentRequest,
    bonsai_usage_reservation: UsageReservation,
    previous_image_usage: tuple[UsageReservation, ...],
    started: UsageReservation,
    usage_ledger: InMemoryUsageLedger,
) -> ImageFailureReview:
    failed = _failed_image_reservation(usage_ledger, started)
    if failed.finished_at is None:
        _raise_invalid_input()
    try:
        failed_session = record_image_generation_failure(
            generating,
            image_reservation=failed,
            expected_revision=generating.revision,
            now=failed.finished_at,
        )
        return ImageFailureReview(
            schema_version="3.0",
            failure_code="image_generation_failed",
            session=failed_session,
            intent=intent,
            query_plan=query_plan,
            typed_proposal=typed_proposal,
            bonsai_request=bonsai_request,
            bonsai_usage_reservation=bonsai_usage_reservation,
            image_usage_reservations=(*previous_image_usage, failed),
        )
    except (TypeError, ValidationError, ValueError):
        _raise_invalid_input()


def _generate_approved_images(
    stage: IntentReview | BlockingIntentReview,
    *,
    policy: SearchBackendPolicy,
    usage_ledger: InMemoryUsageLedger,
    account_id: str,
    api_token: str,
    transport: CloudflareRequestTransport,
    now: Callable[[], datetime],
    approved_reference_png: bytes,
) -> ImageReview | ImageFailureReview:
    """Execute the first approved four-image attempt and stop for image review."""
    if isinstance(stage, BlockingIntentReview):
        _validate_blocking_intent_review(
            stage,
            policy=policy,
            usage_ledger=usage_ledger,
        )
        _raise_invalid_input()
    validated = _validate_intent_review(
        stage,
        policy=policy,
        usage_ledger=usage_ledger,
    )
    validated_policy, _policy_digest = _policy_and_ledger(policy, usage_ledger)
    started = _new_image_reservation(
        validated.session,
        validated.query_plan,
        policy=validated_policy,
        usage_ledger=usage_ledger,
        now=now,
    )
    try:
        generating = approve_intent_review(
            validated.session,
            use_images=True,
            image_reservation=started,
            expected_revision=validated.session.revision,
            now=_utc_now(now),
        )
    except Exception:
        _finish_failed_usage(usage_ledger, started, now=now)
        raise
    try:
        execution = execute_cloudflare_image_set(
            generating,
            intent=validated.intent,
            usage_ledger=usage_ledger,
            usage_reservation=started,
            account_id=account_id,
            api_token=api_token,
            transport=transport,
            now=now,
            approved_reference_png=approved_reference_png,
        )
    except CloudflareExecutionError:
        return _build_image_failure_review(
            generating=generating,
            intent=validated.intent,
            query_plan=validated.query_plan,
            typed_proposal=validated.typed_proposal,
            bonsai_request=validated.bonsai_request,
            bonsai_usage_reservation=validated.bonsai_usage_reservation,
            previous_image_usage=(),
            started=started,
            usage_ledger=usage_ledger,
        )
    try:
        return ImageReview(
            schema_version="3.0",
            session=execution.session,
            intent=validated.intent,
            query_plan=validated.query_plan,
            typed_proposal=validated.typed_proposal,
            bonsai_request=validated.bonsai_request,
            bonsai_usage_reservation=validated.bonsai_usage_reservation,
            execution=execution,
            image_usage_reservations=(execution.usage_reservation,),
        )
    except (TypeError, ValidationError, ValueError):
        _raise_invalid_input()


def _reference_key(stage: IntentReview) -> tuple[str, str]:
    return stage.session.owner_id, stage.session.session_id


def _reference_policy_digest(policy: SearchBackendPolicy) -> str:
    return hashlib.sha256(policy.model_dump_json().encode("utf-8")).hexdigest()


def _single_image_budget(policy: SearchBackendPolicy, calls: int) -> ProviderAttemptBudget:
    budget = policy.cloudflare_image_set
    return ProviderAttemptBudget(
        amount=UsageAmount(
            calls=calls,
            tokens=0,
            cost_microusd=((budget.amount.cost_microusd + 3) // 4) * calls,
        ),
        pricing_policy_sha256=budget.pricing_policy_sha256,
    )


def _generate_reference(
    source: IntentReview,
    *,
    condition_set: VisualConditionSet,
    previous: ReferenceReview | None,
    policy: SearchBackendPolicy,
    usage_ledger: InMemoryUsageLedger,
    account_id: str,
    api_token: str,
    transport: CloudflareRequestTransport,
    now: Callable[[], datetime],
) -> ReferenceReview:
    conditions = VisualConditionSet.model_validate(condition_set)
    prior = () if previous is None else previous.usage_reservations
    prior_derived = ()
    if previous is not None:
        prior_derived = tuple(
            item
            for item in usage_ledger.snapshot().reservations
            if item.owner_id == source.session.owner_id
            and item.session_id == source.session.session_id
            and item.reserved_at >= previous.usage_reservations[0].reserved_at
            and (
                (
                    item.operation == "image_set"
                    and item.binding_sha256 == source.session.query_plan_sha256
                )
                or (
                    item.operation == "counterfactual_images"
                    and item.binding_sha256 == previous.request.preimage_plan_sha256
                )
            )
        )
    plan_digest = hashlib.sha256(
        json.dumps(
            {
                "flow": "reference-and-counterfactual-only-v1",
                "query": search_query_plan_sha256(source.query_plan),
                "conditions": visual_condition_set_sha256(conditions),
                "attempt": len(prior) + 1,
                "policy": _reference_policy_digest(policy),
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    request = build_counterfactual_cloudflare_desired_request(
        intent=source.intent, condition_set=conditions, preimage_plan_sha256=plan_digest
    )
    key = _reference_key(source)
    with _REFERENCE_LOCK:
        records = _REFERENCE_REVIEWS.setdefault(usage_ledger, {})
        current = records.get(key)
        if previous is None:
            if current is not None:
                old_review, _status = current
                if (
                    _status in {"generating", "deriving"}
                    or (old_review is None and _status != "retry_ready")
                    or (
                        old_review is not None
                        and source.session.revision
                        <= old_review.source_intent_review.session.revision
                    )
                ):
                    _raise_invalid_input()
        elif len(prior) >= MAX_IMAGE_SET_ATTEMPTS:
            raise SearchOrchestrationError("image set limit has been reached")
        elif current not in (
            (previous, "pending"),
            (previous, "consumed"),
            (previous, "retry_ready"),
        ):
            _raise_invalid_input()
        # Invalidate the old image before any new reservation or provider call.
        records[key] = (previous, "generating")
    try:
        reserved = _reserve_usage(
            usage_ledger,
            provider="cloudflare",
            operation="reference_image",
            owner_id=source.session.owner_id,
            session_id=source.session.session_id,
            binding_sha256=plan_digest,
            budget=_single_image_budget(policy, 1),
            now=_utc_now(now),
        )
        started = _start_usage(usage_ledger, reserved, now=now)
    except Exception:
        with _REFERENCE_LOCK:
            _REFERENCE_REVIEWS[usage_ledger][key] = (previous, "retry_ready")
        raise
    image = None
    failure_diagnostic = None
    try:
        image = execute_counterfactual_desired_image(
            request=request,
            account_id=account_id,
            api_token=api_token,
            transport=transport,
        )
    except CounterfactualCloudflareExecutionError as error:
        failure_diagnostic = error.diagnostic
    except CloudflareExecutionError:
        failure_diagnostic = CloudflareFailureDiagnostic(stage="unexpected")
    except Exception:
        # Provider exceptions can contain prompts or credentials; expose only the fixed stage.
        failure_diagnostic = CloudflareFailureDiagnostic(stage="unexpected")
    finished = usage_ledger.finish(
        started.reservation_id,
        owner_id=started.owner_id,
        session_id=started.session_id,
        success=image is not None,
        now=_utc_now(now),
    )
    result = ReferenceReview(
        schema_version="1.0",
        status="reference_review" if image is not None else "reference_generation_failed",
        failure_diagnostic=failure_diagnostic,
        source_intent_review=source,
        condition_set=conditions,
        request=request,
        image=image,
        usage_reservations=(*prior, finished),
        prior_derived_usage=prior_derived,
        policy_sha256=_reference_policy_digest(policy),
        expires_at=finished.finished_at + timedelta(minutes=15),
    )
    with _REFERENCE_LOCK:
        _REFERENCE_REVIEWS[usage_ledger][key] = (result, "pending")
    return result


def generate_images(
    stage: IntentReview | BlockingIntentReview,
    *,
    source_input: str,
    condition_set: VisualConditionSet,
    policy: SearchBackendPolicy,
    usage_ledger: InMemoryUsageLedger,
    account_id: str,
    api_token: str,
    transport: CloudflareRequestTransport,
    now: Callable[[], datetime],
) -> ReferenceReview:
    """Generate one reference image and stop before every derived image request."""
    source = _validate_intent_review(stage, policy=policy, usage_ledger=usage_ledger)
    if (
        type(source_input) is not str
        or hashlib.sha256(source_input.encode("utf-8")).hexdigest()
        != source.intent.provenance.source_input_sha256
    ):
        _raise_invalid_input()
    conditions = VisualConditionSet.model_validate(condition_set)
    grounded_conditions = build_visual_condition_set(
        source_input=source_input,
        drafts=tuple(
            VisualConditionDraft(
                source_phrase=item.source_phrase,
                strength=item.strength,
                attribute_key=item.attribute_key,
                focus=item.focus,
            )
            for item in conditions.conditions
        ),
    )
    if conditions != grounded_conditions:
        _raise_invalid_input()
    return _generate_reference(
        source,
        condition_set=condition_set,
        previous=None,
        policy=policy,
        usage_ledger=usage_ledger,
        account_id=account_id,
        api_token=api_token,
        transport=transport,
        now=now,
    )


def _validate_reference_review(
    stage: ReferenceReview,
    *,
    policy: SearchBackendPolicy,
    usage_ledger: InMemoryUsageLedger,
) -> ReferenceReview:
    try:
        reference = ReferenceReview.model_validate(stage)
        _validate_intent_review(
            reference.source_intent_review, policy=policy, usage_ledger=usage_ledger
        )
        if reference.policy_sha256 != _reference_policy_digest(policy):
            _raise_invalid_input()
        for reservation in reference.usage_reservations:
            _current_reservation(usage_ledger, reservation)
        return reference
    except (TypeError, ValueError, ValidationError):
        _raise_invalid_input()


def regenerate_images(
    stage: ReferenceReview,
    *,
    policy: SearchBackendPolicy,
    usage_ledger: InMemoryUsageLedger,
    account_id: str,
    api_token: str,
    transport: CloudflareRequestTransport,
    now: Callable[[], datetime],
) -> ReferenceReview:
    """Replace the reference once and require a new explicit image approval."""
    reference = _validate_reference_review(stage, policy=policy, usage_ledger=usage_ledger)
    return _generate_reference(
        reference.source_intent_review,
        condition_set=reference.condition_set,
        previous=reference,
        policy=policy,
        usage_ledger=usage_ledger,
        account_id=account_id,
        api_token=api_token,
        transport=transport,
        now=now,
    )


def retry_failed_images(
    stage: ReferenceReview,
    *,
    policy: SearchBackendPolicy,
    usage_ledger: InMemoryUsageLedger,
    account_id: str,
    api_token: str,
    transport: CloudflareRequestTransport,
    now: Callable[[], datetime],
) -> ReferenceReview:
    """Retry only a failed reference, within the same two-attempt limit."""
    if not isinstance(stage, ReferenceReview) or stage.status != "reference_generation_failed":
        _raise_invalid_input()
    return regenerate_images(
        stage,
        policy=policy,
        usage_ledger=usage_ledger,
        account_id=account_id,
        api_token=api_token,
        transport=transport,
        now=now,
    )


def approve_reference_image(
    stage: ReferenceReview,
    *,
    human_confirmed: Literal[True],
    policy: SearchBackendPolicy,
    usage_ledger: InMemoryUsageLedger,
    account_id: str,
    api_token: str,
    transport: CloudflareRequestTransport,
    now: Callable[[], datetime],
) -> ImageReview | ImageFailureReview:
    """Consume one reference approval and generate only its N counterfactuals."""
    reference = _validate_reference_review(stage, policy=policy, usage_ledger=usage_ledger)
    if (
        human_confirmed is not True
        or reference.image is None
        or _utc_now(now) >= reference.expires_at
    ):
        _raise_invalid_input()
    source = reference.source_intent_review
    key = _reference_key(source)
    with _REFERENCE_LOCK:
        records = _REFERENCE_REVIEWS.get(usage_ledger, {})
        if records.get(key) != (reference, "pending"):
            _raise_invalid_input()
        records[key] = (reference, "deriving")
    try:
        reserved = _reserve_usage(
            usage_ledger,
            provider="cloudflare",
            operation="counterfactual_images",
            owner_id=source.session.owner_id,
            session_id=source.session.session_id,
            binding_sha256=reference.request.preimage_plan_sha256,
            budget=_single_image_budget(policy, len(reference.condition_set.conditions)),
            now=_utc_now(now),
        )
        started = _start_usage(usage_ledger, reserved, now=now)
        try:
            counterfactual = execute_counterfactual_derived_images(
                intent=source.intent,
                condition_set=reference.condition_set,
                desired_request=reference.request,
                desired=reference.image,
                preimage_plan_sha256=reference.request.preimage_plan_sha256,
                usage_ledger=usage_ledger,
                usage_reservation=started,
                account_id=account_id,
                api_token=api_token,
                transport=transport,
                now=now,
            )
        except Exception:
            raise SearchOrchestrationError("derived image generation failed") from None
        session = record_counterfactual_images(
            source.session,
            image_reservation=counterfactual.usage_reservation,
            preimage_plan_sha256=reference.request.preimage_plan_sha256,
            condition_count=len(reference.condition_set.conditions),
            image_set_sha256=counterfactual.reference_set_sha256,
            image_request_metadata_sha256=counterfactual.request_metadata_sha256,
            expected_revision=source.session.revision,
            now=_utc_now(now),
        )
        return ImageReview(
            schema_version="4.0",
            session=session,
            intent=source.intent,
            query_plan=source.query_plan,
            typed_proposal=source.typed_proposal,
            bonsai_request=source.bonsai_request,
            bonsai_usage_reservation=source.bonsai_usage_reservation,
            image_usage_reservations=(counterfactual.usage_reservation,),
            execution=None,
            reference_review=reference,
            counterfactual_execution=counterfactual,
        )
    finally:
        with _REFERENCE_LOCK:
            _REFERENCE_REVIEWS[usage_ledger][key] = (reference, "consumed")


def _approved_usage(
    *,
    provider: Literal["bonsai", "cloudflare", "outscraper"],
    amount: UsageAmount,
    pricing_policy_sha256: str,
) -> ApprovedUsage:
    return ApprovedUsage(
        provider=provider,
        calls=amount.calls,
        tokens=amount.tokens,
        cost_microusd=amount.cost_microusd,
        pricing_policy_sha256=pricing_policy_sha256,
    )


def _image_usage(
    stage: ImageReview,
    *,
    policy: SearchBackendPolicy,
) -> ApprovedUsage:
    calls = sum(item.amount.calls for item in stage.all_image_usage)
    tokens = sum(item.amount.tokens for item in stage.all_image_usage)
    cost = sum(item.amount.cost_microusd for item in stage.all_image_usage)
    return ApprovedUsage(
        provider="cloudflare",
        calls=calls,
        tokens=tokens,
        cost_microusd=cost,
        pricing_policy_sha256=policy.cloudflare_image_set.pricing_policy_sha256,
    )


def _build_search_review(
    *,
    session: SearchSessionSnapshot,
    intent: NormalizedSearchIntent,
    query_plan: SearchQueryPlan,
    typed_proposal: TypedRequirementProposal,
    bonsai_request: BonsaiIntentRequest,
    bonsai_reservation: UsageReservation,
    image_stage: ImageReview | None,
    postal_code: str,
    policy: SearchBackendPolicy,
    usage_policy_digest: str,
    created_at: datetime,
) -> SearchReview:
    request = build_outscraper_request(query_plan, postal_code=postal_code)
    if image_stage is None:
        image_usage = ApprovedUsage(
            provider="cloudflare",
            calls=0,
            tokens=0,
            cost_microusd=0,
            pricing_policy_sha256=policy.cloudflare_image_set.pricing_policy_sha256,
        )
        cloudflare_model_id = None
        image_prompt_sha256 = None
        image_set_sha256 = None
        image_request_metadata_sha256 = None
    else:
        image_usage = _image_usage(image_stage, policy=policy)
        cloudflare_model_id = CLOUDFLARE_IMAGE_MODEL_ID
        image_prompt_sha256 = (
            image_stage.reference_review.request.prompt_contract_sha256
            if image_stage.schema_version == "4.0"
            else image_prompt_contract_sha256()
        )
        image_set_sha256 = image_stage.session.image_set_sha256
        image_request_metadata_sha256 = image_stage.session.image_request_metadata_sha256

    plan = build_search_approval_plan(
        owner_id=session.owner_id,
        session_id=session.session_id,
        intent=intent,
        query_plan=query_plan,
        outscraper_request_sha256=outscraper_request_sha256(request),
        image_set_sha256=image_set_sha256,
        image_request_metadata_sha256=image_request_metadata_sha256,
        reference_generation_sha256=(
            image_stage.reference_generation_sha256 if image_stage is not None else None
        ),
        image_generation_profile=(
            "reference_counterfactual"
            if image_stage is not None and image_stage.schema_version == "4.0"
            else "legacy_four_views"
        ),
        usage_allowances=[
            _approved_usage(
                provider="bonsai",
                amount=bonsai_reservation.amount,
                pricing_policy_sha256=policy.bonsai_intent.pricing_policy_sha256,
            ),
            image_usage,
            _approved_usage(
                provider="outscraper",
                amount=policy.outscraper_search.amount,
                pricing_policy_sha256=policy.outscraper_search.pricing_policy_sha256,
            ),
        ],
        runtime_bindings=SearchRuntimeBindings(
            bonsai_model_id=bonsai_request.model_id,
            bonsai_prompt_sha256=bonsai_request.prompt_sha256,
            bonsai_schema_sha256=bonsai_request.schema_sha256,
            cloudflare_model_id=cloudflare_model_id,
            image_prompt_sha256=image_prompt_sha256,
            ranking_profile_id=policy.ranking_profile.profile_id,
            ranking_profile_sha256=typed_ranking_profile_sha256(policy.ranking_profile),
            product_evidence_profile_sha256=product_evidence_profile_sha256(),
            implementation_sha256=_runtime_sha256(
                implementation_sha256=policy.implementation_sha256,
                normalization_profile=policy.normalization_profile,
                ranking_profile=policy.ranking_profile,
            ),
            usage_policy_sha256=usage_policy_digest,
        ),
        created_at=created_at,
    )
    try:
        return SearchReview(
            schema_version="3.0",
            session=session,
            intent=intent,
            query_plan=query_plan,
            typed_proposal=typed_proposal,
            request=request,
            plan=plan,
            bonsai_request=bonsai_request,
            bonsai_usage_reservation=bonsai_reservation,
            image_review=image_stage,
            normalization_profile=policy.normalization_profile,
            ranking_profile=policy.ranking_profile,
            implementation_sha256=policy.implementation_sha256,
        )
    except (TypeError, ValidationError, ValueError):
        _raise_invalid_input()


def skip_images(
    stage: IntentReview | BlockingIntentReview | ReferenceReview | ImageReview | ImageFailureReview,
    *,
    postal_code: str,
    policy: SearchBackendPolicy,
    usage_ledger: InMemoryUsageLedger,
    now: Callable[[], datetime],
) -> SearchReview:
    """Approve the intent without images and stop before final search approval."""
    transition_time = _utc_now(now)
    validated_policy, policy_digest = _policy_and_ledger(policy, usage_ledger)
    if isinstance(stage, ReferenceReview):
        reference = _validate_reference_review(stage, policy=policy, usage_ledger=usage_ledger)
        with _REFERENCE_LOCK:
            records = _REFERENCE_REVIEWS.get(usage_ledger, {})
            key = _reference_key(reference.source_intent_review)
            if records.get(key) not in (
                (reference, "pending"),
                (reference, "consumed"),
                (reference, "retry_ready"),
            ):
                _raise_invalid_input()
            records[key] = (reference, "discarded")
        stage = reference.source_intent_review
    elif isinstance(stage, IntentReview):
        with _REFERENCE_LOCK:
            records = _REFERENCE_REVIEWS.get(usage_ledger, {})
            key = _reference_key(stage)
            if key in records:
                _raise_invalid_input()
    if isinstance(stage, BlockingIntentReview):
        _validate_blocking_intent_review(
            stage,
            policy=validated_policy,
            usage_ledger=usage_ledger,
        )
        _raise_invalid_input()
    if isinstance(stage, IntentReview):
        validated = _validate_intent_review(
            stage,
            policy=validated_policy,
            usage_ledger=usage_ledger,
        )
        session = approve_intent_review(
            validated.session,
            use_images=False,
            image_reservation=None,
            expected_revision=validated.session.revision,
            now=transition_time,
        )
        intent = validated.intent
        query_plan = validated.query_plan
        typed_proposal = validated.typed_proposal
        bonsai_request = validated.bonsai_request
        bonsai_reservation = validated.bonsai_usage_reservation
    elif isinstance(stage, ImageReview):
        validated_image = _validate_image_review(
            stage,
            policy=validated_policy,
            usage_ledger=usage_ledger,
        )
        if validated_image.reference_review is not None:
            reference = validated_image.reference_review
            with _REFERENCE_LOCK:
                _REFERENCE_REVIEWS[usage_ledger][_reference_key(reference.source_intent_review)] = (
                    reference,
                    "discarded",
                )
        session = discard_image_set(
            validated_image.session,
            expected_revision=validated_image.session.revision,
            now=transition_time,
        )
        intent = validated_image.intent
        query_plan = validated_image.query_plan
        typed_proposal = validated_image.typed_proposal
        bonsai_request = validated_image.bonsai_request
        bonsai_reservation = validated_image.bonsai_usage_reservation
    elif isinstance(stage, ImageFailureReview):
        validated_failure = _validate_image_failure_review(
            stage,
            policy=validated_policy,
            usage_ledger=usage_ledger,
        )
        if validated_failure.reference_review is not None:
            reference = validated_failure.reference_review
            with _REFERENCE_LOCK:
                _REFERENCE_REVIEWS[usage_ledger][_reference_key(reference.source_intent_review)] = (
                    reference,
                    "discarded",
                )
        session = discard_failed_image_attempt(
            validated_failure.session,
            expected_revision=validated_failure.session.revision,
            now=transition_time,
        )
        intent = validated_failure.intent
        query_plan = validated_failure.query_plan
        typed_proposal = validated_failure.typed_proposal
        bonsai_request = validated_failure.bonsai_request
        bonsai_reservation = validated_failure.bonsai_usage_reservation
    else:
        _raise_invalid_input()
    return _build_search_review(
        session=session,
        intent=intent,
        query_plan=query_plan,
        typed_proposal=typed_proposal,
        bonsai_request=bonsai_request,
        bonsai_reservation=bonsai_reservation,
        image_stage=None,
        postal_code=postal_code,
        policy=validated_policy,
        usage_policy_digest=policy_digest,
        created_at=transition_time,
    )


def accept_images(
    stage: ImageReview,
    *,
    postal_code: str,
    policy: SearchBackendPolicy,
    usage_ledger: InMemoryUsageLedger,
    now: Callable[[], datetime],
) -> SearchReview:
    """Accept the complete image set and stop before final search approval."""
    validated_policy, policy_digest = _policy_and_ledger(policy, usage_ledger)
    validated = _validate_image_review(
        stage,
        policy=validated_policy,
        usage_ledger=usage_ledger,
    )
    transition_time = _utc_now(now)
    session = approve_image_review(
        validated.session,
        expected_revision=validated.session.revision,
        now=transition_time,
    )
    return _build_search_review(
        session=session,
        intent=validated.intent,
        query_plan=validated.query_plan,
        typed_proposal=validated.typed_proposal,
        bonsai_request=validated.bonsai_request,
        bonsai_reservation=validated.bonsai_usage_reservation,
        image_stage=validated,
        postal_code=postal_code,
        policy=validated_policy,
        usage_policy_digest=policy_digest,
        created_at=transition_time,
    )


def approve_search(
    review: SearchReview,
    *,
    now: Callable[[], datetime],
) -> ApprovedSearch:
    """Issue the single-use token without starting an Outscraper request."""
    try:
        validated = SearchReview.model_validate(review)
    except (TypeError, ValidationError, ValueError):
        _raise_invalid_input()
    if validated.image_review is not None:
        _validate_current_images(validated.image_review, None)
    issued = issue_search_approval(
        validated.session,
        plan=validated.plan,
        expected_revision=validated.session.revision,
        now=_utc_now(now),
    )
    return ApprovedSearch(
        review=validated,
        session=issued.session,
        token=issued.token,
    )


def _token_sha256(token: str) -> str:
    try:
        if type(token) is not str or _TOKEN_PATTERN.fullmatch(token) is None:
            _raise_invalid_input()
        return hashlib.sha256(
            b"amazon-explorer-search-approval-token-v2\n" + token.encode("ascii")
        ).hexdigest()
    except SearchOrchestrationError:
        raise
    except (TypeError, UnicodeError, ValueError):
        _raise_invalid_input()


def approved_search_sha256(approved: ApprovedSearch) -> str:
    """Return a non-secret digest for one validated, unconsumed search approval."""
    validated = _validate_approved(approved)
    grant = validated.session.approval
    if grant is None:
        _raise_invalid_input()
    payload = json.dumps(
        {
            "owner_id": validated.session.owner_id,
            "session_id": validated.session.session_id,
            "plan_sha256": search_approval_plan_sha256(validated.review.plan),
            "token_sha256": grant.token_sha256,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(b"amazon-explorer-approved-search-v3\n" + payload).hexdigest()


def _validate_approved(approved: ApprovedSearch) -> ApprovedSearch:
    if type(approved) is not ApprovedSearch:
        _raise_invalid_input()
    try:
        review = SearchReview.model_validate(approved.review)
        session = SearchSessionSnapshot.model_validate(approved.session)
    except (TypeError, ValidationError, ValueError):
        _raise_invalid_input()
    grant = session.approval
    token_digest = _token_sha256(approved.token)
    if (
        grant is None
        or session.state != "search_approval"
        or session.revision != review.session.revision + 1
        or session.owner_id != review.session.owner_id
        or session.session_id != review.session.session_id
        or session.created_at != review.session.created_at
        or session.updated_at != grant.issued_at
        or grant.issued_at < review.session.updated_at
        or session.intent_sha256 != review.session.intent_sha256
        or session.query_plan_sha256 != review.session.query_plan_sha256
        or session.typed_requirement_proposal_sha256
        != review.session.typed_requirement_proposal_sha256
        or session.typed_requirement_status != review.session.typed_requirement_status
        or session.image_mode != review.session.image_mode
        or session.image_attempts_started != review.session.image_attempts_started
        or session.active_image_reservation_id != review.session.active_image_reservation_id
        or session.image_set_sha256 != review.session.image_set_sha256
        or session.image_request_metadata_sha256 != review.session.image_request_metadata_sha256
        or session.usage_policy_sha256 != review.session.usage_policy_sha256
        or not _same_digest(grant.plan_sha256, search_approval_plan_sha256(review.plan))
        or not _same_digest(grant.token_sha256, token_digest)
        or grant.expires_at != review.plan.expires_at
        or grant.consumed_at is not None
    ):
        _raise_invalid_input()
    return ApprovedSearch(review=review, session=session, token=approved.token)


def _validate_plan_ledger(
    review: SearchReview,
    usage_ledger: InMemoryUsageLedger,
) -> ApprovedUsage:
    if not isinstance(usage_ledger, InMemoryUsageLedger):
        _raise_invalid_input()
    snapshot = usage_ledger.snapshot()
    policies = {item.provider: item for item in snapshot.policies}
    allowances = {item.provider: item for item in review.plan.usage_allowances}
    if (
        set(policies) != {"bonsai", "cloudflare", "outscraper"}
        or not _same_digest(
            review.plan.runtime_bindings.usage_policy_sha256,
            usage_policy_sha256(snapshot.policies),
        )
        or any(
            not _same_digest(
                allowances[provider].pricing_policy_sha256,
                provider_policy.pricing_policy_sha256,
            )
            for provider, provider_policy in policies.items()
        )
    ):
        _raise_invalid_input()
    _current_reservation(usage_ledger, review.bonsai_usage_reservation)
    if review.image_review is not None:
        _validate_current_images(review.image_review, usage_ledger)
        for reservation in review.image_review.all_image_usage:
            _current_reservation(usage_ledger, reservation)
    allowance = next(item for item in review.plan.usage_allowances if item.provider == "outscraper")
    return allowance


def _finish_failed_usage(
    ledger: InMemoryUsageLedger,
    reservation: UsageReservation,
    *,
    now: Callable[[], datetime],
) -> None:
    ledger.finish(
        reservation.reservation_id,
        owner_id=reservation.owner_id,
        session_id=reservation.session_id,
        success=False,
        now=_utc_now(now),
    )


def _authorize_approved_search(
    approved: ApprovedSearch,
    *,
    usage_ledger: InMemoryUsageLedger,
    approval_ledger: InMemoryApprovalLedger,
    now: Callable[[], datetime],
) -> tuple[ApprovedSearch, AuthorizedOutscraperRequest, UsageReservation]:
    validated = _validate_approved(approved)
    if not isinstance(approval_ledger, InMemoryApprovalLedger):
        _raise_invalid_input()
    token_digest = validated.session.approval.token_sha256
    if any(
        _same_digest(item.token_sha256, token_digest)
        for item in approval_ledger.snapshot().consumptions
    ):
        raise SearchOrchestrationError("Search approval has already been consumed") from None

    allowance = _validate_plan_ledger(validated.review, usage_ledger)
    reserve_time = _utc_now(now)
    if reserve_time >= validated.review.plan.expires_at:
        raise SearchOrchestrationError("Search approval has expired") from None
    reserved = _reserve_usage(
        usage_ledger,
        provider="outscraper",
        operation="product_search",
        owner_id=validated.session.owner_id,
        session_id=validated.session.session_id,
        binding_sha256=search_approval_plan_sha256(validated.review.plan),
        budget=ProviderAttemptBudget(
            amount=UsageAmount(
                calls=allowance.calls,
                tokens=allowance.tokens,
                cost_microusd=allowance.cost_microusd,
            ),
            pricing_policy_sha256=allowance.pricing_policy_sha256,
        ),
        now=reserve_time,
    )
    started = _start_usage(usage_ledger, reserved, now=now)
    try:
        permit = authorize_outscraper_request(
            validated.review.request,
            session=validated.session,
            approval_ledger=approval_ledger,
            token=validated.token,
            plan=validated.review.plan,
            outscraper_reservation=started,
            owner_id=validated.session.owner_id,
            session_id=validated.session.session_id,
            expected_revision=validated.session.revision,
            now=_utc_now(now),
        )
    except Exception:
        _finish_failed_usage(usage_ledger, started, now=now)
        raise
    return validated, permit, started


def execute_approved_outscraper_request(
    approved: ApprovedSearch,
    *,
    usage_ledger: InMemoryUsageLedger,
    approval_ledger: InMemoryApprovalLedger,
    api_key: str,
    transport: OutscraperRequestTransport,
    now: Callable[[], datetime],
    sleep: Callable[[int], None],
) -> OutscraperProductExecution:
    """Consume one final approval and execute its exact Outscraper request once."""
    _validated, permit, started = _authorize_approved_search(
        approved,
        usage_ledger=usage_ledger,
        approval_ledger=approval_ledger,
        now=now,
    )
    return execute_outscraper_request(
        permit,
        usage_ledger=usage_ledger,
        usage_reservation=started,
        api_key=api_key,
        transport=transport,
        now=now,
        sleep=sleep,
    )


def run_search(
    approved: ApprovedSearch,
    *,
    usage_ledger: InMemoryUsageLedger,
    approval_ledger: InMemoryApprovalLedger,
    api_key: str,
    transport: OutscraperRequestTransport,
    now: Callable[[], datetime],
    sleep: Callable[[int], None],
) -> ProductSearchPipelineResult:
    """Consume final approval, run one Outscraper attempt, then normalize and rank."""
    validated, permit, started = _authorize_approved_search(
        approved,
        usage_ledger=usage_ledger,
        approval_ledger=approval_ledger,
        now=now,
    )

    try:
        execution = execute_outscraper_request(
            permit,
            usage_ledger=usage_ledger,
            usage_reservation=started,
            api_key=api_key,
            transport=transport,
            now=now,
            sleep=sleep,
        )
    except OutscraperExecutionError:
        return fail_product_search(
            permit.session,
            approval_plan=validated.review.plan,
            expected_revision=permit.session.revision,
            now=_utc_now(now),
        )

    return complete_product_search(
        permit.session,
        execution=execution,
        approval_plan=validated.review.plan,
        intent=validated.review.intent,
        query_plan=validated.review.query_plan,
        typed_proposal=validated.review.typed_proposal,
        normalization_profile=validated.review.normalization_profile,
        ranking_profile=validated.review.ranking_profile,
        expected_revision=permit.session.revision,
        now=_utc_now(now),
    )
