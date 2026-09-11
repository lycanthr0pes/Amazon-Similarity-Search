from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
import hmac
import re
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationError
from pydantic import model_validator

from src.search_v2.approval import SearchApprovalPlan
from src.search_v2.approval import search_approval_plan_sha256
from src.search_v2.intent import NormalizedSearchIntent
from src.search_v2.intent import search_intent_sha256
from src.search_v2.outscraper_http import OUTSCRAPER_MAX_POLLS
from src.search_v2.outscraper_http import OutscraperProductExecution
from src.search_v2.outscraper_request import OutscraperAmazonProductsRequest
from src.search_v2.outscraper_request import outscraper_request_sha256
from src.search_v2.product_normalization import NormalizedProductBatch
from src.search_v2.product_normalization import ProductNormalizationError
from src.search_v2.product_normalization import ProductNormalizationProfile
from src.search_v2.product_normalization import normalize_outscraper_products
from src.search_v2.product_normalization import normalized_product_batch_sha256
from src.search_v2.product_evidence import product_evidence_profile_sha256
from src.search_v2.query_planner import SearchQueryPlan
from src.search_v2.query_planner import search_query_plan_sha256
from src.search_v2.state_machine import SearchSessionSnapshot
from src.search_v2.state_machine import SearchStateError
from src.search_v2.state_machine import record_products_normalized
from src.search_v2.state_machine import record_products_received
from src.search_v2.state_machine import record_search_completed
from src.search_v2.state_machine import record_search_failed
from src.search_v2.typed_intent_adapter import TypedRequirementProposal
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_intent_adapter import typed_requirement_proposal_sha256
from src.search_v2.typed_ranking import TYPED_RANKING_PROFILE_V4
from src.search_v2.typed_ranking import TypedRankedProductBatch
from src.search_v2.typed_ranking import TypedRankingError
from src.search_v2.typed_ranking import TypedRankingProfile
from src.search_v2.typed_ranking import rank_typed_product_batch
from src.search_v2.typed_ranking import typed_ranked_product_batch_sha256
from src.search_v2.typed_ranking import typed_ranking_profile_sha256
from src.search_v2.usage_ledger import UsageReservation


_INVALID_PIPELINE_MESSAGE = "Product search pipeline inputs are invalid"
_PROVIDER_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,255}$")


class ProductSearchPipelineError(ValueError):
    """A fixed-message rejection before product processing changes state."""


class StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        revalidate_instances="always",
        frozen=True,
    )


class ProductSearchPipelineResult(StrictFrozenContract):
    schema_version: Literal["3.0"]
    outcome: Literal["results", "empty", "failed"]
    session: SearchSessionSnapshot
    normalized_batch: NormalizedProductBatch | None = Field(repr=False)
    ranked_batch: TypedRankedProductBatch | None = Field(repr=False)

    @model_validator(mode="after")
    def validate_result_bindings(self) -> ProductSearchPipelineResult:
        if self.outcome == "failed":
            if self.session.state != "search_failed" or self.ranked_batch is not None:
                raise ValueError("failed pipeline result is inconsistent")
            if self.session.failure_stage == "ranking":
                if self.normalized_batch is None:
                    raise ValueError("ranking failure requires the normalized batch")
                if (
                    self.session.normalized_product_batch_sha256
                    != normalized_product_batch_sha256(self.normalized_batch)
                    or self.normalized_batch.query_plan_sha256 != self.session.query_plan_sha256
                ):
                    raise ValueError("ranking failure batch binding is inconsistent")
            elif self.normalized_batch is not None:
                raise ValueError("pre-ranking failure must not expose a normalized batch")
            return self

        if (
            self.session.state != "search_completed"
            or self.session.result_outcome != self.outcome
            or self.normalized_batch is None
            or self.ranked_batch is None
        ):
            raise ValueError("completed pipeline result is inconsistent")
        if (
            self.session.normalized_product_batch_sha256
            != normalized_product_batch_sha256(self.normalized_batch)
            or self.session.ranked_product_batch_sha256
            != typed_ranked_product_batch_sha256(self.ranked_batch)
            or self.ranked_batch.normalized_product_batch_sha256
            != normalized_product_batch_sha256(self.normalized_batch)
            or self.normalized_batch.query_plan_sha256 != self.session.query_plan_sha256
            or self.ranked_batch.query_plan_sha256 != self.session.query_plan_sha256
            or self.ranked_batch.intent_sha256 != self.session.intent_sha256
            or self.ranked_batch.typed_requirement_proposal_sha256
            != self.session.typed_requirement_proposal_sha256
            or self.session.normalized_product_count != len(self.normalized_batch.products)
            or self.session.rejected_candidate_count != len(self.normalized_batch.rejections)
            or self.session.ranked_product_count != len(self.ranked_batch.products)
            or (self.outcome == "results") != bool(self.ranked_batch.products)
        ):
            raise ValueError("completed pipeline batch binding is inconsistent")
        return self


def _raise_invalid_pipeline() -> None:
    raise ProductSearchPipelineError(_INVALID_PIPELINE_MESSAGE) from None


def _utc_datetime(value: object) -> datetime:
    if type(value) is not datetime or value.tzinfo is None:
        _raise_invalid_pipeline()
    try:
        if value.utcoffset() != timedelta(0):
            _raise_invalid_pipeline()
    except (OverflowError, ValueError):
        _raise_invalid_pipeline()
    return value.astimezone(timezone.utc)


def _plan_matches_session(
    plan: SearchApprovalPlan,
    session: SearchSessionSnapshot,
) -> bool:
    if session.approval is None or session.approval.consumed_at is None:
        return False
    plan_digest = search_approval_plan_sha256(plan)
    query_digest = search_query_plan_sha256(plan.query_plan)
    if (
        session.state != "scrape_submitted"
        or plan.owner_id != session.owner_id
        or plan.session_id != session.session_id
        or not hmac.compare_digest(plan_digest, session.approval.plan_sha256)
        or not hmac.compare_digest(plan.intent_sha256, session.intent_sha256 or "")
        or not hmac.compare_digest(query_digest, session.query_plan_sha256 or "")
        or not hmac.compare_digest(
            plan.typed_requirement_proposal_sha256,
            session.typed_requirement_proposal_sha256 or "",
        )
        or session.typed_requirement_status != "ready"
        or session.approval.expires_at != plan.expires_at
    ):
        return False
    if session.image_mode == "off":
        return plan.image_mode == "off"
    return (
        plan.image_mode == "approved"
        and hmac.compare_digest(plan.image_set_sha256 or "", session.image_set_sha256 or "")
        and hmac.compare_digest(
            plan.image_request_metadata_sha256 or "",
            session.image_request_metadata_sha256 or "",
        )
        and hmac.compare_digest(
            plan.runtime_bindings.usage_policy_sha256,
            session.usage_policy_sha256 or "",
        )
    )


def _candidate_count(data: list[object], *, maximum_candidates: int) -> int:
    count = 0
    for group in data:
        count += len(group) if type(group) is list else 1
        if count > maximum_candidates:
            _raise_invalid_pipeline()
    return count


def _validated_submitted_context(
    session: object,
    *,
    approval_plan: object,
    expected_revision: object,
    now: object,
) -> tuple[SearchSessionSnapshot, SearchApprovalPlan, datetime]:
    try:
        validated_session = SearchSessionSnapshot.model_validate(session)
        validated_plan = SearchApprovalPlan.model_validate(approval_plan)
        validated_now = _utc_datetime(now)
        if (
            type(expected_revision) is not int
            or expected_revision != validated_session.revision
            or validated_now < validated_session.updated_at
            or not _plan_matches_session(validated_plan, validated_session)
        ):
            _raise_invalid_pipeline()
        return validated_session, validated_plan, validated_now
    except ProductSearchPipelineError:
        raise
    except (AttributeError, TypeError, ValidationError, ValueError):
        _raise_invalid_pipeline()


def _validated_pipeline_context(
    session: object,
    *,
    execution: object,
    approval_plan: object,
    intent: object,
    query_plan: object,
    typed_proposal: object,
    normalization_profile: object,
    ranking_profile: object,
    expected_revision: object,
    now: object,
) -> tuple[
    SearchSessionSnapshot,
    OutscraperProductExecution,
    NormalizedSearchIntent,
    SearchQueryPlan,
    ProductNormalizationProfile,
    TypedRequirementProposal,
    TypedRankingProfile,
    int,
    datetime,
]:
    try:
        validated_session, validated_plan, validated_now = _validated_submitted_context(
            session,
            approval_plan=approval_plan,
            expected_revision=expected_revision,
            now=now,
        )
        if type(execution) is not OutscraperProductExecution:
            _raise_invalid_pipeline()
        validated_intent = NormalizedSearchIntent.model_validate(intent)
        validated_query_plan = SearchQueryPlan.model_validate(query_plan)
        if type(typed_proposal) is not TypedRequirementProposal:
            _raise_invalid_pipeline()
        validated_proposal = TypedRequirementProposal.model_validate(typed_proposal)
        validated_request = OutscraperAmazonProductsRequest.model_validate(execution.request)
        validated_reservation = UsageReservation.model_validate(execution.usage_reservation)
        validated_normalization_profile = ProductNormalizationProfile.model_validate(
            normalization_profile
        )
        validated_ranking_profile = TypedRankingProfile.model_validate(ranking_profile)

        intent_digest = search_intent_sha256(validated_intent)
        query_digest = search_query_plan_sha256(validated_query_plan)
        request_digest = outscraper_request_sha256(validated_request)
        plan_digest = search_approval_plan_sha256(validated_plan)
        proposal_digest = typed_requirement_proposal_sha256(validated_proposal)
        request_queries = tuple(
            (query.language, query.value) for query in validated_request.queries
        )
        planned_queries = tuple(
            (query.language, query.value) for query in validated_query_plan.queries
        )
        outscraper_allowance = next(
            item for item in validated_plan.usage_allowances if item.provider == "outscraper"
        )
        if (
            not hmac.compare_digest(validated_plan.intent_sha256, intent_digest)
            or validated_proposal != build_typed_requirement_proposal(validated_intent)
            or validated_proposal.status != "ready"
            or not hmac.compare_digest(
                validated_plan.typed_requirement_proposal_sha256,
                proposal_digest,
            )
            or not hmac.compare_digest(validated_query_plan.intent_sha256, intent_digest)
            or not hmac.compare_digest(
                search_query_plan_sha256(validated_plan.query_plan),
                query_digest,
            )
            or not hmac.compare_digest(
                validated_session.query_plan_sha256 or "",
                query_digest,
            )
            or not hmac.compare_digest(validated_request.query_plan_sha256, query_digest)
            or request_queries != planned_queries
            or not hmac.compare_digest(
                validated_plan.outscraper_request_sha256,
                request_digest,
            )
            or validated_plan.runtime_bindings.ranking_profile_id
            != validated_ranking_profile.profile_id
            or not hmac.compare_digest(
                validated_plan.runtime_bindings.ranking_profile_sha256,
                typed_ranking_profile_sha256(validated_ranking_profile),
            )
            or not hmac.compare_digest(
                validated_plan.runtime_bindings.product_evidence_profile_sha256,
                product_evidence_profile_sha256(),
            )
            or validated_reservation.status != "succeeded"
            or validated_reservation.provider != "outscraper"
            or validated_reservation.operation != "product_search"
            or validated_reservation.owner_id != validated_session.owner_id
            or validated_reservation.session_id != validated_session.session_id
            or validated_reservation.amount.calls != 1
            or validated_reservation.amount.tokens > outscraper_allowance.tokens
            or validated_reservation.amount.cost_microusd > outscraper_allowance.cost_microusd
            or not hmac.compare_digest(validated_reservation.binding_sha256, plan_digest)
            or not hmac.compare_digest(
                validated_reservation.request.pricing_policy_sha256,
                outscraper_allowance.pricing_policy_sha256,
            )
            or not hmac.compare_digest(
                validated_reservation.usage_policy_sha256,
                validated_plan.runtime_bindings.usage_policy_sha256,
            )
            or validated_reservation.started_at is None
            or validated_reservation.finished_at is None
            or validated_session.approval is None
            or validated_reservation.started_at < validated_session.approval.issued_at
            or validated_reservation.finished_at < validated_session.approval.consumed_at
            or validated_reservation.finished_at > validated_now
            or type(execution.provider_request_id) is not str
            or _PROVIDER_REQUEST_ID_PATTERN.fullmatch(execution.provider_request_id) is None
            or type(execution.polls_performed) is not int
            or not 0 <= execution.polls_performed <= OUTSCRAPER_MAX_POLLS
            or type(execution.response) is not dict
            or set(execution.response) != {"data"}
            or type(execution.response["data"]) is not list
        ):
            _raise_invalid_pipeline()
        received_count = _candidate_count(
            execution.response["data"],
            maximum_candidates=validated_request.maximum_candidates,
        )
        validated_execution = OutscraperProductExecution(
            request=validated_request,
            provider_request_id=execution.provider_request_id,
            response={"data": execution.response["data"]},
            polls_performed=execution.polls_performed,
            usage_reservation=validated_reservation,
        )
        return (
            validated_session,
            validated_execution,
            validated_intent,
            validated_query_plan,
            validated_normalization_profile,
            validated_proposal,
            validated_ranking_profile,
            received_count,
            validated_now,
        )
    except ProductSearchPipelineError:
        raise
    except (AttributeError, StopIteration, TypeError, ValidationError, ValueError):
        _raise_invalid_pipeline()


def _result(
    *,
    outcome: Literal["results", "empty", "failed"],
    session: SearchSessionSnapshot,
    normalized_batch: NormalizedProductBatch | None,
    ranked_batch: TypedRankedProductBatch | None,
) -> ProductSearchPipelineResult:
    try:
        return ProductSearchPipelineResult(
            schema_version="3.0",
            outcome=outcome,
            session=session,
            normalized_batch=normalized_batch,
            ranked_batch=ranked_batch,
        )
    except (TypeError, ValidationError, ValueError):
        _raise_invalid_pipeline()


def fail_product_search(
    session: SearchSessionSnapshot,
    *,
    approval_plan: SearchApprovalPlan,
    expected_revision: int,
    now: datetime,
) -> ProductSearchPipelineResult:
    """Record an already-classified provider execution failure without raw details."""
    validated_session, _validated_plan, validated_now = _validated_submitted_context(
        session,
        approval_plan=approval_plan,
        expected_revision=expected_revision,
        now=now,
    )
    try:
        failed = record_search_failed(
            validated_session,
            failure_stage="product_search",
            expected_revision=validated_session.revision,
            now=validated_now,
        )
    except SearchStateError:
        _raise_invalid_pipeline()
    return _result(
        outcome="failed",
        session=failed,
        normalized_batch=None,
        ranked_batch=None,
    )


def complete_product_search(
    session: SearchSessionSnapshot,
    *,
    execution: OutscraperProductExecution,
    approval_plan: SearchApprovalPlan,
    intent: NormalizedSearchIntent,
    query_plan: SearchQueryPlan,
    typed_proposal: TypedRequirementProposal,
    normalization_profile: ProductNormalizationProfile,
    expected_revision: int,
    now: datetime,
    ranking_profile: TypedRankingProfile = TYPED_RANKING_PROFILE_V4,
) -> ProductSearchPipelineResult:
    """Normalize and rank one validated, completed Outscraper execution offline."""
    (
        validated_session,
        validated_execution,
        validated_intent,
        validated_query_plan,
        validated_normalization_profile,
        validated_proposal,
        validated_ranking_profile,
        received_count,
        validated_now,
    ) = _validated_pipeline_context(
        session,
        execution=execution,
        approval_plan=approval_plan,
        intent=intent,
        query_plan=query_plan,
        typed_proposal=typed_proposal,
        normalization_profile=normalization_profile,
        ranking_profile=ranking_profile,
        expected_revision=expected_revision,
        now=now,
    )

    try:
        received = record_products_received(
            validated_session,
            received_candidate_count=received_count,
            expected_revision=validated_session.revision,
            now=validated_now,
        )
    except SearchStateError:
        _raise_invalid_pipeline()

    try:
        normalized = normalize_outscraper_products(
            validated_execution.response,
            request=validated_execution.request,
            provider_request_id=validated_execution.provider_request_id,
            profile=validated_normalization_profile,
        )
    except ProductNormalizationError:
        try:
            failed = record_search_failed(
                received,
                failure_stage="product_normalization",
                expected_revision=received.revision,
                now=validated_now,
            )
        except SearchStateError:
            _raise_invalid_pipeline()
        return _result(
            outcome="failed",
            session=failed,
            normalized_batch=None,
            ranked_batch=None,
        )

    try:
        normalized_state = record_products_normalized(
            received,
            normalized_product_count=len(normalized.products),
            rejected_candidate_count=len(normalized.rejections),
            normalized_product_batch_sha256=normalized_product_batch_sha256(normalized),
            expected_revision=received.revision,
            now=validated_now,
        )
    except SearchStateError:
        _raise_invalid_pipeline()

    try:
        ranked = rank_typed_product_batch(
            validated_intent,
            validated_query_plan,
            normalized,
            validated_proposal,
            profile=validated_ranking_profile,
        )
    except TypedRankingError:
        try:
            failed = record_search_failed(
                normalized_state,
                failure_stage="ranking",
                expected_revision=normalized_state.revision,
                now=validated_now,
            )
        except SearchStateError:
            _raise_invalid_pipeline()
        return _result(
            outcome="failed",
            session=failed,
            normalized_batch=normalized,
            ranked_batch=None,
        )

    try:
        completed = record_search_completed(
            normalized_state,
            ranked_product_count=len(ranked.products),
            ranked_product_batch_sha256=typed_ranked_product_batch_sha256(ranked),
            expected_revision=normalized_state.revision,
            now=validated_now,
        )
    except SearchStateError:
        _raise_invalid_pipeline()
    return _result(
        outcome="results" if ranked.products else "empty",
        session=completed,
        normalized_batch=normalized,
        ranked_batch=ranked,
    )
