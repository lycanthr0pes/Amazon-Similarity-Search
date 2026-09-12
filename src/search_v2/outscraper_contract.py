"""Pure Outscraper request contracts shared by authorization and normalization."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Annotated
from typing import Literal
import unicodedata
from urllib.parse import urlencode, urlsplit

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import field_validator
from pydantic import model_validator

from src.search_v2.query_planner import SearchQuery
from src.search_v2.query_planner import SearchQueryPlan
from src.search_v2.query_planner import search_query_plan_sha256


OUTSCRAPER_AMAZON_PRODUCTS_ENDPOINT = "https://api.outscraper.cloud/amazon-products"
OUTSCRAPER_DOMAIN = "amazon.co.jp"
OUTSCRAPER_LANGUAGE = "ja"
OUTSCRAPER_LIMIT_PER_QUERY = 24
OUTSCRAPER_MAXIMUM_CANDIDATES = 48

_ENDPOINT_PATH = "/amazon-products"
_POSTAL_CODE_PATTERN = re.compile(r"^[0-9]{3}-?[0-9]{4}$")
_DNS_HOST_PATTERN = re.compile(r"^[a-z0-9.-]+$")

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Endpoint = Annotated[str, StringConstraints(min_length=1, max_length=2048)]
QueryText = Annotated[str, StringConstraints(min_length=1, max_length=200)]
PostalCode = Annotated[str, StringConstraints(min_length=7, max_length=8)]


class StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        revalidate_instances="always",
        frozen=True,
    )


def _validated_endpoint(value: str) -> str:
    if value != value.strip() or any(
        unicodedata.category(character).startswith("C") for character in value
    ):
        raise ValueError("Outscraper endpoint contains unsupported whitespace or control data")
    try:
        value.encode("ascii")
        parsed = urlsplit(value)
        port = parsed.port
    except (UnicodeEncodeError, ValueError) as exc:
        raise ValueError("Outscraper endpoint is invalid") from exc

    hostname = parsed.hostname
    if (
        parsed.scheme != "https"
        or hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != _ENDPOINT_PATH
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Outscraper endpoint must be a credential-free HTTPS operation URL")
    if (
        hostname != hostname.casefold()
        or hostname.endswith(".")
        or _DNS_HOST_PATTERN.fullmatch(hostname) is None
        or any(
            not label or label.startswith("-") or label.endswith("-")
            for label in hostname.split(".")
        )
    ):
        raise ValueError("Outscraper endpoint host is invalid")

    expected_netloc = hostname if port is None else f"{hostname}:{port}"
    if parsed.netloc != expected_netloc:
        raise ValueError("Outscraper endpoint is not canonical")
    return value


class OutscraperQuery(StrictFrozenContract):
    language: Literal["ja", "en"]
    value: QueryText

    @model_validator(mode="after")
    def validate_canonical_query(self) -> OutscraperQuery:
        validated = SearchQuery.model_validate({"language": self.language, "value": self.value})
        if validated.value != self.value:
            raise ValueError("Outscraper query is not canonical")
        return self


class OutscraperAmazonProductsRequest(StrictFrozenContract):
    schema_version: Literal["2.0", "2.1"]
    provider: Literal["outscraper"]
    method: Literal["GET"]
    endpoint: Endpoint
    query_plan_sha256: Digest
    queries: Annotated[
        tuple[OutscraperQuery, ...],
        Field(min_length=1, max_length=2, repr=False),
    ]
    domain: Literal["amazon.co.jp"]
    language: Literal["ja"]
    postal_code: PostalCode = Field(repr=False)
    limit_per_query: Literal[24]
    async_request: Literal[True]
    maximum_candidates: Literal[24, 48]

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        return _validated_endpoint(value)

    @field_validator("postal_code")
    @classmethod
    def validate_postal_code(cls, value: str) -> str:
        if _POSTAL_CODE_PATTERN.fullmatch(value) is None:
            raise ValueError("Outscraper postal code is invalid")
        return value

    @model_validator(mode="after")
    def validate_query_batch(self) -> OutscraperAmazonProductsRequest:
        languages = tuple(query.language for query in self.queries)
        if len(languages) != len(set(languages)):
            raise ValueError("Outscraper request permits one query per language")
        if self.maximum_candidates != len(self.queries) * self.limit_per_query:
            raise ValueError("Outscraper candidate ceiling does not match the query batch")
        return self

    def provider_queries(self) -> tuple[str, ...]:
        if self.schema_version == "2.0":
            return tuple(query.value for query in self.queries)
        return tuple(japanese_search_url(query.value) for query in self.queries)

    def query_parameters(self) -> tuple[tuple[str, str], ...]:
        return (
            *(("query", value) for value in self.provider_queries()),
            ("domain", self.domain),
            ("language", self.language),
            ("postal_code", self.postal_code),
            ("limit", str(self.limit_per_query)),
            ("async", "true"),
        )


def japanese_search_url(query: str) -> str:
    return "https://www.amazon.co.jp/s?" + urlencode({"k": query, "language": "ja_JP"})


def build_outscraper_request(
    query_plan: SearchQueryPlan,
    *,
    endpoint: str = OUTSCRAPER_AMAZON_PRODUCTS_ENDPOINT,
    postal_code: str,
    japanese_search_urls: bool = False,
) -> OutscraperAmazonProductsRequest:
    if type(japanese_search_urls) is not bool:
        raise ValueError("Invalid Japanese search URL option")
    validated_plan = SearchQueryPlan.model_validate(query_plan)
    queries = tuple(
        OutscraperQuery(language=query.language, value=query.value)
        for query in validated_plan.queries
    )
    return OutscraperAmazonProductsRequest(
        schema_version="2.1" if japanese_search_urls else "2.0",
        provider="outscraper",
        method="GET",
        endpoint=endpoint,
        query_plan_sha256=search_query_plan_sha256(validated_plan),
        queries=queries,
        domain=OUTSCRAPER_DOMAIN,
        language=OUTSCRAPER_LANGUAGE,
        postal_code=postal_code,
        limit_per_query=OUTSCRAPER_LIMIT_PER_QUERY,
        async_request=True,
        maximum_candidates=len(queries) * OUTSCRAPER_LIMIT_PER_QUERY,
    )


def outscraper_request_sha256(request: OutscraperAmazonProductsRequest) -> str:
    # Compatibility for existing callers; new digests include a distinct provider domain.
    from src.search_v2.product_request import PlaywrightSearchRequest, product_request_sha256

    if isinstance(request, PlaywrightSearchRequest):
        return product_request_sha256(request)
    validated = OutscraperAmazonProductsRequest.model_validate(request)
    canonical = json.dumps(
        validated.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(b"amazon-explorer-outscraper-request-v2\n" + canonical).hexdigest()
