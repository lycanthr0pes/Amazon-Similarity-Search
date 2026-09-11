from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError

from src.search_v2.approval import SearchApprovalPlan
from src.search_v2.approval import search_approval_plan_sha256
from src.search_v2.outscraper_contract import OUTSCRAPER_AMAZON_PRODUCTS_ENDPOINT
from src.search_v2.outscraper_contract import OUTSCRAPER_DOMAIN
from src.search_v2.outscraper_contract import OUTSCRAPER_LANGUAGE
from src.search_v2.outscraper_contract import OUTSCRAPER_LIMIT_PER_QUERY
from src.search_v2.outscraper_contract import OUTSCRAPER_MAXIMUM_CANDIDATES
from src.search_v2.outscraper_contract import OutscraperAmazonProductsRequest
from src.search_v2.outscraper_contract import OutscraperQuery
from src.search_v2.outscraper_contract import _validated_endpoint
from src.search_v2.outscraper_contract import build_outscraper_request
from src.search_v2.outscraper_contract import outscraper_request_sha256
from src.search_v2.query_planner import search_query_plan_sha256
from src.search_v2.state_machine import InMemoryApprovalLedger
from src.search_v2.state_machine import SearchSessionSnapshot
from src.search_v2.state_machine import consume_search_approval
from src.search_v2.usage_ledger import UsageReservation


__all__ = [
    "OUTSCRAPER_AMAZON_PRODUCTS_ENDPOINT",
    "OUTSCRAPER_DOMAIN",
    "OUTSCRAPER_LANGUAGE",
    "OUTSCRAPER_LIMIT_PER_QUERY",
    "OUTSCRAPER_MAXIMUM_CANDIDATES",
    "AuthorizedOutscraperRequest",
    "OutscraperAmazonProductsRequest",
    "OutscraperAuthorizationError",
    "OutscraperQuery",
    "_validated_endpoint",
    "authorize_outscraper_request",
    "build_outscraper_request",
    "outscraper_request_sha256",
]


class OutscraperAuthorizationError(ValueError):
    """A fixed-message rejection before an Outscraper execution permit is issued."""


@dataclass(frozen=True, slots=True, repr=False)
class AuthorizedOutscraperRequest:
    request: OutscraperAmazonProductsRequest
    session: SearchSessionSnapshot
    approval_plan_sha256: str
    reservation_id: str
    authorized_at: datetime


def authorize_outscraper_request(
    request: OutscraperAmazonProductsRequest,
    *,
    session: SearchSessionSnapshot,
    approval_ledger: InMemoryApprovalLedger,
    token: str,
    plan: SearchApprovalPlan,
    outscraper_reservation: UsageReservation,
    owner_id: str,
    session_id: str,
    expected_revision: int,
    now: datetime,
) -> AuthorizedOutscraperRequest:
    try:
        validated_request = OutscraperAmazonProductsRequest.model_validate(request)
    except (TypeError, ValidationError, ValueError) as exc:
        raise OutscraperAuthorizationError("Outscraper request is invalid") from exc

    try:
        validated_plan = SearchApprovalPlan.model_validate(plan)
    except (TypeError, ValidationError, ValueError) as exc:
        raise OutscraperAuthorizationError("Outscraper approval plan is invalid") from exc

    if not hmac.compare_digest(
        validated_request.query_plan_sha256,
        search_query_plan_sha256(validated_plan.query_plan),
    ):
        raise OutscraperAuthorizationError("Outscraper request query plan does not match approval")
    request_queries = tuple((query.language, query.value) for query in validated_request.queries)
    approved_queries = tuple(
        (query.language, query.value) for query in validated_plan.query_plan.queries
    )
    if request_queries != approved_queries:
        raise OutscraperAuthorizationError("Outscraper request query batch does not match approval")
    if not hmac.compare_digest(
        outscraper_request_sha256(validated_request),
        validated_plan.outscraper_request_sha256,
    ):
        raise OutscraperAuthorizationError("Outscraper request does not match approval")

    plan_sha256 = search_approval_plan_sha256(validated_plan)
    submitted = consume_search_approval(
        session,
        approval_ledger=approval_ledger,
        token=token,
        plan=validated_plan,
        outscraper_reservation=outscraper_reservation,
        owner_id=owner_id,
        session_id=session_id,
        expected_revision=expected_revision,
        now=now,
    )
    if submitted.approval is None or submitted.approval.consumed_at is None:
        raise AssertionError("approved Outscraper request did not consume its approval")
    return AuthorizedOutscraperRequest(
        request=validated_request,
        session=submitted,
        approval_plan_sha256=plan_sha256,
        reservation_id=outscraper_reservation.reservation_id,
        authorized_at=submitted.approval.consumed_at,
    )
