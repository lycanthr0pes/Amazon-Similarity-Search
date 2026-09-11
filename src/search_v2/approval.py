from __future__ import annotations

import hashlib
import hmac
import json
import unicodedata
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from pydantic import model_validator

from src.search_v2.intent import NormalizedSearchIntent
from src.search_v2.intent import search_intent_sha256
from src.search_v2.product_evidence import product_evidence_profile_sha256
from src.search_v2.query_planner import SearchQueryPlan
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_intent_adapter import typed_requirement_proposal_sha256
from src.search_v2.typed_ranking import TYPED_RANKING_PROFILE_V4
from src.search_v2.typed_ranking import typed_ranking_profile_sha256
from src.search_v2.usage_ledger import MAX_USAGE_CALLS
from src.search_v2.usage_ledger import MAX_USAGE_COST_MICROUSD
from src.search_v2.usage_ledger import MAX_USAGE_TOKENS
from src.search_v2.usage_ledger import Digest
from src.search_v2.usage_ledger import Provider
from src.search_v2.usage_ledger import SubjectId


APPROVAL_TTL = timedelta(minutes=15)

BoundedIdentifier = Annotated[str, StringConstraints(min_length=1, max_length=200)]


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


def _bounded_identifier(value: str, *, field_name: str) -> str:
    if value != value.strip() or any(
        unicodedata.category(character).startswith("C") for character in value
    ):
        raise ValueError(f"{field_name} contains unsupported whitespace or control characters")
    return value


class ApprovedUsage(StrictFrozenContract):
    provider: Provider
    calls: Annotated[int, Field(ge=0, le=MAX_USAGE_CALLS)]
    tokens: Annotated[int, Field(ge=0, le=MAX_USAGE_TOKENS)]
    cost_microusd: Annotated[int, Field(ge=0, le=MAX_USAGE_COST_MICROUSD)]
    pricing_policy_sha256: Digest


class SearchRuntimeBindings(StrictFrozenContract):
    bonsai_model_id: BoundedIdentifier
    bonsai_prompt_sha256: Digest
    bonsai_schema_sha256: Digest
    cloudflare_model_id: BoundedIdentifier | None
    image_prompt_sha256: Digest | None
    ranking_profile_id: BoundedIdentifier
    ranking_profile_sha256: Digest
    product_evidence_profile_sha256: Digest
    implementation_sha256: Digest
    usage_policy_sha256: Digest

    @field_validator("bonsai_model_id", "cloudflare_model_id", "ranking_profile_id")
    @classmethod
    def validate_identifier(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        return _bounded_identifier(value, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_runtime(self) -> SearchRuntimeBindings:
        if (self.cloudflare_model_id is None) != (self.image_prompt_sha256 is None):
            raise ValueError("Cloudflare runtime bindings must be present together")
        if (
            self.ranking_profile_id != TYPED_RANKING_PROFILE_V4.profile_id
            or not hmac.compare_digest(
                self.ranking_profile_sha256,
                typed_ranking_profile_sha256(),
            )
            or not hmac.compare_digest(
                self.product_evidence_profile_sha256,
                product_evidence_profile_sha256(),
            )
        ):
            raise ValueError("typed ranking runtime bindings are unsupported")
        return self


class SearchApprovalPlan(StrictFrozenContract):
    schema_version: Literal["3.0"]
    owner_id: SubjectId
    session_id: SubjectId
    intent: NormalizedSearchIntent
    intent_sha256: Digest
    typed_requirement_proposal_sha256: Digest
    query_plan: SearchQueryPlan
    outscraper_request_sha256: Digest
    image_mode: Literal["off", "approved"]
    image_set_sha256: Digest | None
    image_request_metadata_sha256: Digest | None
    reference_generation_sha256: Digest | None = None
    image_generation_profile: Literal["legacy_four_views", "reference_counterfactual"] = (
        "legacy_four_views"
    )
    usage_allowances: Annotated[list[ApprovedUsage], Field(min_length=3, max_length=3)]
    runtime_bindings: SearchRuntimeBindings
    created_at: datetime
    expires_at: datetime

    @field_validator("created_at", "expires_at")
    @classmethod
    def validate_timestamp(cls, value: datetime, info) -> datetime:
        return _utc_datetime(value, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_bindings(self) -> SearchApprovalPlan:
        expected_intent_sha256 = search_intent_sha256(self.intent)
        proposal = build_typed_requirement_proposal(self.intent)
        if not hmac.compare_digest(self.intent_sha256, expected_intent_sha256):
            raise ValueError("approval intent digest does not match intent")
        if proposal.status != "ready" or not hmac.compare_digest(
            self.typed_requirement_proposal_sha256,
            typed_requirement_proposal_sha256(proposal),
        ):
            raise ValueError("approval typed proposal does not match intent")
        if not hmac.compare_digest(self.query_plan.intent_sha256, expected_intent_sha256):
            raise ValueError("query plan does not match intent")
        if not hmac.compare_digest(
            self.runtime_bindings.bonsai_prompt_sha256,
            self.intent.provenance.prompt_sha256,
        ) or not hmac.compare_digest(
            self.runtime_bindings.bonsai_schema_sha256,
            self.intent.provenance.schema_sha256,
        ):
            raise ValueError("runtime prompt or schema does not match intent provenance")
        if self.expires_at - self.created_at != APPROVAL_TTL:
            raise ValueError("search approval plan must expire after exactly 15 minutes")

        allowances = {allowance.provider: allowance for allowance in self.usage_allowances}
        if len(allowances) != 3 or set(allowances) != {
            "bonsai",
            "cloudflare",
            "outscraper",
        }:
            raise ValueError("approval plan requires one allowance per provider")
        if allowances["outscraper"].calls != 1:
            raise ValueError("approval plan must allow exactly one Outscraper search call")

        image_bindings_present = (
            self.image_set_sha256 is not None and self.image_request_metadata_sha256 is not None
        )
        if (self.image_set_sha256 is None) != (self.image_request_metadata_sha256 is None):
            raise ValueError("image bindings must be all present or all absent")

        cloudflare_runtime_present = self.runtime_bindings.cloudflare_model_id is not None
        cloudflare_allowance = allowances["cloudflare"]
        if self.image_mode == "off":
            if (
                image_bindings_present
                or self.reference_generation_sha256 is not None
                or self.image_generation_profile != "legacy_four_views"
            ):
                raise ValueError("image-off plan must not contain image bindings")
            if cloudflare_runtime_present:
                raise ValueError("image-off plan must not contain Cloudflare runtime")
            if (
                cloudflare_allowance.calls != 0
                or cloudflare_allowance.tokens != 0
                or cloudflare_allowance.cost_microusd != 0
            ):
                raise ValueError("image-off plan must have a zero Cloudflare allowance")
        else:
            if not image_bindings_present:
                raise ValueError("approved image plan requires image bindings")
            if not cloudflare_runtime_present:
                raise ValueError("approved image plan requires Cloudflare runtime")
            allowed_calls = (
                {4, 8} if self.reference_generation_sha256 is None else set(range(6, 17))
            )
            if self.image_generation_profile == "reference_counterfactual":
                if self.reference_generation_sha256 is None:
                    raise ValueError("reference-only flow requires its generation binding")
                allowed_calls = set(range(2, 9))
            if cloudflare_allowance.calls not in allowed_calls:
                raise ValueError("approved image plan has an invalid generation allowance")
        return self


def build_search_approval_plan(
    *,
    owner_id: str,
    session_id: str,
    intent: NormalizedSearchIntent,
    query_plan: SearchQueryPlan,
    outscraper_request_sha256: str,
    image_set_sha256: str | None,
    image_request_metadata_sha256: str | None,
    usage_allowances: list[ApprovedUsage],
    runtime_bindings: SearchRuntimeBindings,
    created_at: datetime,
    reference_generation_sha256: str | None = None,
    image_generation_profile: Literal["legacy_four_views", "reference_counterfactual"] = (
        "legacy_four_views"
    ),
) -> SearchApprovalPlan:
    image_mode = (
        "off" if image_set_sha256 is None and image_request_metadata_sha256 is None else "approved"
    )
    proposal = build_typed_requirement_proposal(intent)
    return SearchApprovalPlan(
        schema_version="3.0",
        owner_id=owner_id,
        session_id=session_id,
        intent=intent,
        intent_sha256=search_intent_sha256(intent),
        typed_requirement_proposal_sha256=typed_requirement_proposal_sha256(proposal),
        query_plan=query_plan,
        outscraper_request_sha256=outscraper_request_sha256,
        image_mode=image_mode,
        image_set_sha256=image_set_sha256,
        image_request_metadata_sha256=image_request_metadata_sha256,
        reference_generation_sha256=reference_generation_sha256,
        image_generation_profile=image_generation_profile,
        usage_allowances=usage_allowances,
        runtime_bindings=runtime_bindings,
        created_at=created_at,
        expires_at=created_at + APPROVAL_TTL,
    )


def search_approval_plan_sha256(plan: SearchApprovalPlan) -> str:
    plan = SearchApprovalPlan.model_validate(plan)
    payload = plan.model_dump(mode="json")
    payload["usage_allowances"] = sorted(
        payload["usage_allowances"],
        key=lambda item: item["provider"],
    )
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(b"amazon-explorer-approved-search-plan-v3\n" + canonical).hexdigest()
