from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from pydantic import model_validator

from src.search_v2.dynamic_attributes import numeric_identity_requires_review
from src.search_v2.intent import NormalizedSearchIntent
from src.search_v2.intent import search_intent_sha256
from src.search_v2.tokenizer import tokenize_search_text


MAX_QUERY_CHARACTERS = 200
_URL_PATTERN = re.compile(r"(?i)(?:[a-z][a-z0-9+.-]*://|www\.)")

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class StrictContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        revalidate_instances="always",
    )


class SearchQuery(StrictContract):
    language: Literal["ja", "en"]
    value: Annotated[str, StringConstraints(min_length=1, max_length=MAX_QUERY_CHARACTERS)]

    @field_validator("value")
    @classmethod
    def normalize_and_validate_value(cls, value: str) -> str:
        if any(character in "\r\n" for character in value):
            raise ValueError("search query must not contain a newline")
        normalized = unicodedata.normalize("NFKC", value)
        if any(unicodedata.category(character).startswith("C") for character in normalized):
            raise ValueError("search query must not contain control characters")
        collapsed = " ".join(normalized.split())
        if not collapsed:
            raise ValueError("search query must not be empty")
        if len(collapsed) > MAX_QUERY_CHARACTERS:
            raise ValueError("search query exceeds 200 characters")
        if _URL_PATTERN.search(collapsed):
            raise ValueError("search query must not contain a URL")
        return collapsed


class SearchQueryPlan(StrictContract):
    schema_version: Literal["2.0"]
    intent_sha256: Digest
    queries: Annotated[list[SearchQuery], Field(min_length=1, max_length=2)]

    @model_validator(mode="after")
    def validate_query_set(self) -> SearchQueryPlan:
        languages = [query.language for query in self.queries]
        if len(languages) != len(set(languages)):
            raise ValueError("search plan permits one query per language")
        identities = [
            unicodedata.normalize("NFKC", query.value).casefold() for query in self.queries
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("search plan must not contain equivalent queries")
        return self


def _query_term_groups(
    intent: NormalizedSearchIntent,
    *,
    language: Literal["ja", "en"],
) -> list[list[str]]:
    if language == "ja":
        language_terms = [
            (intent.product_name_ja, True),
            (intent.category_ja, True),
            (intent.brand, False),
            (intent.model_number, False),
            *((term, True) for term in intent.required_terms_ja),
            *((term, True) for term in intent.preferred_terms_ja),
        ]
    else:
        language_terms = [
            (intent.product_name_en, True),
            (intent.category_en, True),
            (intent.brand, False),
            (intent.model_number, False),
            *((term, True) for term in intent.required_terms_en),
            *((term, True) for term in intent.preferred_terms_en),
        ]

    groups: list[list[str]] = []
    for term, should_tokenize in language_terms:
        if term is None:
            continue
        candidates = tokenize_search_text(term, language=language) if should_tokenize else [term]
        group: list[str] = []
        seen_in_group: set[str] = set()
        for candidate in candidates:
            identity = unicodedata.normalize("NFKC", candidate).casefold()
            if identity in seen_in_group:
                continue
            seen_in_group.add(identity)
            group.append(candidate)
        if group:
            groups.append(group)
    return groups


def _bounded_query(groups: list[list[str]]) -> str | None:
    accepted: list[str] = []
    seen: set[str] = set()
    for group in groups:
        unique_group = [
            term for term in group if unicodedata.normalize("NFKC", term).casefold() not in seen
        ]
        candidate = " ".join([*accepted, *unique_group])
        if len(candidate) <= MAX_QUERY_CHARACTERS:
            accepted.extend(unique_group)
            seen.update(unicodedata.normalize("NFKC", term).casefold() for term in unique_group)
    return " ".join(accepted) or None


def build_search_query_plan(intent: NormalizedSearchIntent) -> SearchQueryPlan:
    intent = NormalizedSearchIntent.model_validate(intent)
    if intent.has_blocking_ambiguity or any(
        numeric_identity_requires_review(candidate) for candidate in intent.typed_conditions
    ):
        raise ValueError("blocking ambiguity must be resolved before building a query plan")

    queries: list[SearchQuery] = []
    seen_queries: set[str] = set()
    for language in ("ja", "en"):
        value = _bounded_query(_query_term_groups(intent, language=language))
        if value is None:
            continue
        query = SearchQuery(language=language, value=value)
        identity = unicodedata.normalize("NFKC", query.value).casefold()
        if identity in seen_queries:
            continue
        seen_queries.add(identity)
        queries.append(query)

    if not queries:
        raise ValueError("normalized intent does not contain searchable terms")
    return SearchQueryPlan(
        schema_version="2.0",
        intent_sha256=search_intent_sha256(intent),
        queries=queries,
    )


def search_query_plan_sha256(plan: SearchQueryPlan) -> str:
    plan = SearchQueryPlan.model_validate(plan)
    canonical = json.dumps(
        plan.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(b"amazon-explorer-search-query-plan-v2\n" + canonical).hexdigest()
