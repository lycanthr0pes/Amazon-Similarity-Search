"""Playwright retrieval contract; legacy requests remain readable without migration."""

import hashlib
import json
from typing import Literal

from pydantic import Field, model_serializer, model_validator

from src.search_v2.outscraper_contract import (
    Digest,
    OutscraperAmazonProductsRequest,
    OutscraperQuery,
    PostalCode,
    StrictFrozenContract,
    build_outscraper_request,
)
from src.search_v2.query_planner import SearchQueryPlan, search_query_plan_sha256


class PlaywrightSearchRequest(StrictFrozenContract):
    schema_version: Literal["1.0"] = "1.0"
    provider: Literal["playwright"] = "playwright"
    endpoint: Literal["https://www.amazon.co.jp/s"] = "https://www.amazon.co.jp/s"
    query_plan_sha256: Digest
    queries: tuple[OutscraperQuery, ...] = Field(min_length=1, max_length=2, repr=False)
    domain: Literal["amazon.co.jp"] = "amazon.co.jp"
    language: Literal["ja"] = "ja"
    # Kept as input provenance only; anonymous pages use Amazon's default delivery location.
    postal_code: PostalCode = Field(repr=False)
    delivery_location: Literal["amazon_default"] = "amazon_default"
    limit_per_query: Literal[24] = 24
    maximum_candidates: Literal[24, 48]
    maximum_search_pages: Literal[3] = 3
    page_timeout_seconds: Literal[30] = 30
    retries: Literal[0] = 0
    details: Literal[True] = True
    english_titles: Literal[True] | None = None
    english_details: Literal[True] | None = None

    @model_serializer(mode="wrap")
    def serialize_compatible(self, handler):
        data = handler(self)
        if self.english_titles is None:
            data.pop("english_titles", None)
        if self.english_details is None:
            data.pop("english_details", None)
        return data

    @model_validator(mode="after")
    def validate_batch(self):
        if self.english_details and not self.english_titles:
            raise ValueError("English details require English retrieval")
        languages = [q.language for q in self.queries]
        if len(set(languages)) != len(languages):
            raise ValueError("Duplicate product query language")
        if self.maximum_candidates != len(self.queries) * self.limit_per_query:
            raise ValueError("Product candidate limit does not match queries")
        return self

    def provider_queries(self):
        return tuple(q.value for q in self.queries)

    def compatibility_request(self):
        """Only for explicitly injected legacy task-protocol adapters."""
        return OutscraperAmazonProductsRequest(
            schema_version="2.0",
            provider="outscraper",
            method="GET",
            endpoint="https://api.outscraper.cloud/amazon-products",
            query_plan_sha256=self.query_plan_sha256,
            queries=self.queries,
            domain=self.domain,
            language=self.language,
            postal_code=self.postal_code,
            limit_per_query=24,
            async_request=True,
            maximum_candidates=self.maximum_candidates,
        )


ProductSearchRequest = PlaywrightSearchRequest | OutscraperAmazonProductsRequest


def build_product_request(query_plan, *, postal_code, english_titles=True, english_details=True):
    plan = SearchQueryPlan.model_validate(query_plan)
    return PlaywrightSearchRequest(
        query_plan_sha256=search_query_plan_sha256(plan),
        queries=tuple(OutscraperQuery(language=q.language, value=q.value) for q in plan.queries),
        postal_code=postal_code,
        maximum_candidates=24 * len(plan.queries),
        english_titles=True if english_titles else None,
        english_details=True if english_titles and english_details else None,
    )


def rebuild_product_request(request, query_plan):
    if isinstance(request, PlaywrightSearchRequest):
        return build_product_request(
            query_plan,
            postal_code=request.postal_code,
            english_titles=request.english_titles,
            english_details=request.english_details,
        )
    return build_outscraper_request(
        query_plan,
        postal_code=request.postal_code,
        japanese_search_urls=request.schema_version == "2.1",
    )


def product_request_sha256(request):
    if not isinstance(request, PlaywrightSearchRequest):
        from src.search_v2.outscraper_contract import outscraper_request_sha256

        return outscraper_request_sha256(request)
    validated = PlaywrightSearchRequest.model_validate(request)
    body = json.dumps(
        validated.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode()
    return hashlib.sha256(b"amazon-explorer-playwright-request-v1\n" + body).hexdigest()
