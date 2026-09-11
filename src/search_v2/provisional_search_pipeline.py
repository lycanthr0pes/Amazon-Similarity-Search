"""Outscraper completion to provisional image-ranked product results."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from typing import Literal
from typing import Protocol

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationError
from pydantic import model_validator

from src.search_v2.counterfactual_image import VisualConditionSet
from src.search_v2.counterfactual_product_evaluator import ProductImageProxy
from src.search_v2.counterfactual_reference_approval import ApprovedCounterfactualReferences
from src.search_v2.image_proxy import ProxyImage
from src.search_v2.image_similarity import LocalClipImageEncoder
from src.search_v2.intent import NormalizedSearchIntent
from src.search_v2.outscraper_http import OUTSCRAPER_MAX_POLLS
from src.search_v2.outscraper_http import OutscraperProductExecution
from src.search_v2.outscraper_request import OutscraperAmazonProductsRequest
from src.search_v2.product_normalization import ProductNormalizationProfile
from src.search_v2.product_normalization import ProductNormalizationError
from src.search_v2.product_normalization import normalize_outscraper_products
from src.search_v2.provisional_backend import ProvisionalBackendError
from src.search_v2.provisional_backend import complete_provisional_product_ranking
from src.search_v2.provisional_typed_ranking import ProvisionalTypedRankedProductBatch
from src.search_v2.query_planner import SearchQueryPlan
from src.search_v2.typed_intent_adapter import TypedRequirementProposal
from src.search_v2.typed_ranking import TypedRankingError
from src.search_v2.typed_ranking import rank_typed_product_batch
from src.search_v2.usage_ledger import UsageReservation


PROVISIONAL_SEARCH_TASK_COUNT = 1
PROVISIONAL_SEARCH_RETRY_COUNT = 0
PROVISIONAL_SEARCH_MAXIMUM_CANDIDATES = 24

_INVALID_PIPELINE_MESSAGE = "Provisional search pipeline inputs are invalid"


class ProvisionalSearchPipelineError(ValueError):
    """A fixed-message failure at the provisional search composition boundary."""

    def __init__(
        self,
        message: str,
        *,
        failure_substage: Literal[
            "execution_validation",
            "product_normalization",
            "typed_ranking",
            "backend_validation",
            "image_validation",
            "reference_clip",
            "candidate_preparation",
            "candidate_clip",
            "candidate_scoring",
            "calibration",
            "ranking_v5",
            "result_validation",
        ],
        received_candidate_count: int | None = None,
        normalized_product_count: int | None = None,
        rejected_candidate_count: int | None = None,
        products_with_image_url: int | None = None,
        image_request_count: int | None = None,
        image_fetch_success_count: int | None = None,
        reference_clip_batch_count: int | None = None,
        candidate_clip_batch_count: int | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_substage = failure_substage
        self.received_candidate_count = received_candidate_count
        self.normalized_product_count = normalized_product_count
        self.rejected_candidate_count = rejected_candidate_count
        self.products_with_image_url = products_with_image_url
        self.image_request_count = image_request_count
        self.image_fetch_success_count = image_fetch_success_count
        self.reference_clip_batch_count = reference_clip_batch_count
        self.candidate_clip_batch_count = candidate_clip_batch_count

    def safe_metadata(self) -> dict[str, int | str | None]:
        return {
            "candidate_clip_batch_count": self.candidate_clip_batch_count,
            "failure_substage": self.failure_substage,
            "image_fetch_success_count": self.image_fetch_success_count,
            "image_request_count": self.image_request_count,
            "normalized_product_count": self.normalized_product_count,
            "products_with_image_url": self.products_with_image_url,
            "received_candidate_count": self.received_candidate_count,
            "reference_clip_batch_count": self.reference_clip_batch_count,
            "rejected_candidate_count": self.rejected_candidate_count,
        }


class _StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


class ProvisionalSearchResult(_StrictFrozenContract):
    schema_version: Literal["1.0"]
    outcome: Literal["image_ready", "image_unknown", "image_unavailable"]
    task_count: Literal[1]
    retry_count: Literal[0]
    polls_performed: Annotated[int, Field(ge=0, le=OUTSCRAPER_MAX_POLLS)]
    received_candidate_count: Annotated[int, Field(ge=4, le=24)]
    normalized_product_count: Annotated[int, Field(ge=4, le=24)]
    rejected_candidate_count: Annotated[int, Field(ge=0, le=24)]
    products_with_image_url: Annotated[int, Field(ge=0, le=24)]
    image_request_count: Annotated[int, Field(ge=0, le=24)]
    image_available_count: Annotated[int, Field(ge=0, le=24)]
    image_missing_count: Annotated[int, Field(ge=0, le=24)]
    image_unknown_count: Annotated[int, Field(ge=0, le=24)]
    ranked_batch: ProvisionalTypedRankedProductBatch = Field(repr=False)

    @model_validator(mode="after")
    def validate_counts(self) -> ProvisionalSearchResult:
        if (
            self.received_candidate_count
            != self.normalized_product_count + self.rejected_candidate_count
            or self.normalized_product_count != len(self.ranked_batch.products)
            or self.products_with_image_url > self.normalized_product_count
            or self.image_request_count > self.products_with_image_url
            or self.image_available_count + self.image_missing_count + self.image_unknown_count
            != self.normalized_product_count
        ):
            raise ValueError("provisional search result counts do not match")
        if self.outcome == "image_ready":
            if self.image_unknown_count != 0 or self.image_available_count < 4:
                raise ValueError("ready image result is inconsistent")
        elif self.outcome == "image_unknown":
            if self.image_unknown_count == 0 or self.image_available_count != 0:
                raise ValueError("unknown image result is inconsistent")
        elif (
            self.image_available_count != 0
            or self.image_unknown_count != 0
            or self.image_missing_count == 0
        ):
            raise ValueError("unavailable image result is inconsistent")
        return self

    def safe_metadata(self) -> dict[str, int | str]:
        return {
            "image_available_count": self.image_available_count,
            "image_missing_count": self.image_missing_count,
            "image_request_count": self.image_request_count,
            "image_unknown_count": self.image_unknown_count,
            "normalized_product_count": self.normalized_product_count,
            "outcome": self.outcome,
            "polls_performed": self.polls_performed,
            "products_with_image_url": self.products_with_image_url,
            "received_candidate_count": self.received_candidate_count,
            "rejected_candidate_count": self.rejected_candidate_count,
            "retry_count": self.retry_count,
            "task_count": self.task_count,
        }


class _ProxyService(Protocol):
    def fetch_image(self, url: str) -> ProxyImage: ...


class _CountingProxyService:
    def __init__(self, inner: _ProxyService) -> None:
        self.inner = inner
        self.request_count = 0

    def fetch_image(self, url: str) -> ProxyImage:
        self.request_count += 1
        return self.inner.fetch_image(url)


def _validated_execution(
    execution: object,
) -> tuple[OutscraperProductExecution, OutscraperAmazonProductsRequest]:
    if type(execution) is not OutscraperProductExecution:
        raise ProvisionalSearchPipelineError(
            _INVALID_PIPELINE_MESSAGE,
            failure_substage="execution_validation",
        ) from None
    try:
        request = OutscraperAmazonProductsRequest.model_validate(execution.request)
        reservation = UsageReservation.model_validate(execution.usage_reservation)
        if (
            len(request.queries) != 1
            or request.maximum_candidates != PROVISIONAL_SEARCH_MAXIMUM_CANDIDATES
            or type(execution.polls_performed) is not int
            or not 0 <= execution.polls_performed <= OUTSCRAPER_MAX_POLLS
            or reservation.status != "succeeded"
            or reservation.provider != "outscraper"
            or reservation.operation != "product_search"
            or reservation.amount.calls != PROVISIONAL_SEARCH_TASK_COUNT
            or reservation.amount.tokens != 0
        ):
            raise ValueError("Outscraper execution is not eligible")
        return execution, request
    except (AttributeError, TypeError, ValidationError, ValueError) as exc:
        raise ProvisionalSearchPipelineError(
            _INVALID_PIPELINE_MESSAGE,
            failure_substage="execution_validation",
        ) from exc


def run_provisional_search(
    *,
    execution: OutscraperProductExecution,
    intent: NormalizedSearchIntent,
    query_plan: SearchQueryPlan,
    typed_proposal: TypedRequirementProposal,
    normalization_profile: ProductNormalizationProfile,
    condition_set: VisualConditionSet,
    approved_references: ApprovedCounterfactualReferences,
    proxy_service: ProductImageProxy,
    asset_root: Path,
    encoder: LocalClipImageEncoder,
) -> ProvisionalSearchResult:
    """Normalize one completed Outscraper task and produce provisional ranking v5."""
    validated_execution, request = _validated_execution(execution)
    try:
        normalized = normalize_outscraper_products(
            validated_execution.response,
            request=request,
            provider_request_id=validated_execution.provider_request_id,
            profile=normalization_profile,
        )
    except ProductNormalizationError:
        raise ProvisionalSearchPipelineError(
            _INVALID_PIPELINE_MESSAGE,
            failure_substage="product_normalization",
        ) from None

    received_candidate_count = len(normalized.products) + len(normalized.rejections)
    normalized_product_count = len(normalized.products)
    rejected_candidate_count = len(normalized.rejections)
    products_with_image_url = sum(bool(item.image_urls) for item in normalized.products)
    try:
        source_ranking = rank_typed_product_batch(
            intent,
            query_plan,
            normalized,
            typed_proposal,
        )
    except TypedRankingError:
        raise ProvisionalSearchPipelineError(
            _INVALID_PIPELINE_MESSAGE,
            failure_substage="typed_ranking",
            received_candidate_count=received_candidate_count,
            normalized_product_count=normalized_product_count,
            rejected_candidate_count=rejected_candidate_count,
            products_with_image_url=products_with_image_url,
        ) from None

    counting_proxy = _CountingProxyService(proxy_service)
    try:
        ranked = complete_provisional_product_ranking(
            source_typed_ranking=source_ranking,
            product_batch=normalized,
            condition_set=condition_set,
            approved_references=approved_references,
            proxy_service=counting_proxy,
            asset_root=asset_root,
            encoder=encoder,
        )
    except ProvisionalBackendError as exc:
        diagnostic = exc.safe_metadata()
        raise ProvisionalSearchPipelineError(
            _INVALID_PIPELINE_MESSAGE,
            failure_substage=exc.failure_substage,
            received_candidate_count=received_candidate_count,
            normalized_product_count=normalized_product_count,
            rejected_candidate_count=rejected_candidate_count,
            products_with_image_url=products_with_image_url,
            image_request_count=diagnostic["image_request_count"],
            image_fetch_success_count=diagnostic["image_fetch_success_count"],
            reference_clip_batch_count=diagnostic["reference_clip_batch_count"],
            candidate_clip_batch_count=diagnostic["candidate_clip_batch_count"],
        ) from None

    statuses = tuple(item.image_component.status for item in ranked.products)
    available_count = statuses.count("available")
    unknown_count = statuses.count("unknown")
    if available_count >= 4:
        outcome = "image_ready"
    elif unknown_count > 0:
        outcome = "image_unknown"
    else:
        outcome = "image_unavailable"
    try:
        result = ProvisionalSearchResult(
            schema_version="1.0",
            outcome=outcome,
            task_count=PROVISIONAL_SEARCH_TASK_COUNT,
            retry_count=PROVISIONAL_SEARCH_RETRY_COUNT,
            polls_performed=validated_execution.polls_performed,
            received_candidate_count=received_candidate_count,
            normalized_product_count=normalized_product_count,
            rejected_candidate_count=rejected_candidate_count,
            products_with_image_url=products_with_image_url,
            image_request_count=counting_proxy.request_count,
            image_available_count=available_count,
            image_missing_count=statuses.count("missing"),
            image_unknown_count=unknown_count,
            ranked_batch=ranked,
        )
        return result
    except ValidationError:
        raise ProvisionalSearchPipelineError(
            _INVALID_PIPELINE_MESSAGE,
            failure_substage="result_validation",
            received_candidate_count=received_candidate_count,
            normalized_product_count=normalized_product_count,
            rejected_candidate_count=rejected_candidate_count,
            products_with_image_url=products_with_image_url,
            image_request_count=counting_proxy.request_count,
        ) from None
