"""Local production application service for approved provisional searches."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import hashlib
import hmac
import json
from pathlib import Path
import unicodedata

from pydantic import SecretStr
from pydantic import ValidationError

from src.search_v2.counterfactual_image import VisualConditionSet
from src.search_v2.counterfactual_image import _normalize_source
from src.search_v2.counterfactual_image import visual_condition_set_sha256
from src.search_v2.counterfactual_reference_approval import ApprovedCounterfactualReferences
from src.search_v2.counterfactual_reference_approval import (
    approved_counterfactual_references_sha256,
)
from src.search_v2.orchestrator import ApprovedSearch
from src.search_v2.orchestrator import approved_search_sha256
from src.search_v2.orchestrator import execute_approved_outscraper_request
from src.search_v2.outscraper_http import OutscraperRequestTransport
from src.search_v2.provisional_history_repository import SqliteProvisionalHistoryRepository
from src.search_v2.provisional_history_snapshot import build_provisional_history_snapshot
from src.search_v2.provisional_search_pipeline import run_provisional_search
from src.search_v2.search_job import LOCAL_SEARCH_OWNER_ID
from src.search_v2.search_job import LocalSearchJobExecutor
from src.search_v2.search_job import SearchJobControl
from src.search_v2.search_job import SearchJobResult
from src.search_v2.search_job import SearchJobSnapshot
from src.search_v2.state_machine import InMemoryApprovalLedger
from src.search_v2.usage_ledger import InMemoryUsageLedger


_BINDING_DOMAIN = b"amazon-explorer-provisional-production-job-v1\x00"
_INVALID_INPUT_MESSAGE = "Production search inputs are invalid"


class ProductionSearchError(ValueError):
    """A fixed-message rejection before an approved search job is submitted."""


@dataclass(frozen=True, slots=True, repr=False)
class ProductionSearchCommand:
    source_text: str
    approved_search: ApprovedSearch
    condition_set: VisualConditionSet
    approved_references: ApprovedCounterfactualReferences


def _raise_invalid_input() -> None:
    raise ProductionSearchError(_INVALID_INPUT_MESSAGE) from None


def _utc_now(now: Callable[[], datetime]) -> datetime:
    try:
        value = now()
        if type(value) is not datetime or value.tzinfo is None:
            _raise_invalid_input()
        if value.utcoffset() != timedelta(0):
            _raise_invalid_input()
        return value.astimezone(timezone.utc)
    except ProductionSearchError:
        raise
    except Exception:
        _raise_invalid_input()


def _source_sha256(source_text: object) -> str:
    if type(source_text) is not str or not source_text or len(source_text) > 2_000:
        _raise_invalid_input()
    normalized = unicodedata.normalize("NFKC", source_text)
    if any(
        unicodedata.category(character).startswith("C") and not character.isspace()
        for character in normalized
    ):
        _raise_invalid_input()
    if not normalized.strip():
        _raise_invalid_input()
    return hashlib.sha256(source_text.encode("utf-8")).hexdigest()


def _validated_command(command: object) -> ProductionSearchCommand:
    try:
        if type(command) is not ProductionSearchCommand:
            _raise_invalid_input()
        approved = command.approved_search
        approved_digest = approved_search_sha256(approved)
        conditions = VisualConditionSet.model_validate(command.condition_set)
        references = ApprovedCounterfactualReferences.model_validate(command.approved_references)
        source_digest = _source_sha256(command.source_text)
        condition_source_digest = hashlib.sha256(
            _normalize_source(command.source_text).encode("utf-8")
        ).hexdigest()
        review = approved.review
        session = approved.session
        condition_digest = visual_condition_set_sha256(conditions)
        if (
            not approved_digest
            or session.owner_id != LOCAL_SEARCH_OWNER_ID
            or review.session.owner_id != LOCAL_SEARCH_OWNER_ID
            or references.owner_id != LOCAL_SEARCH_OWNER_ID
            or references.session_id != session.session_id
            or review.session.session_id != session.session_id
            or review.typed_proposal.status != "ready"
            or not hmac.compare_digest(
                review.intent.provenance.source_input_sha256,
                source_digest,
            )
            or not hmac.compare_digest(conditions.source_sha256, condition_source_digest)
            or not hmac.compare_digest(references.condition_set_sha256, condition_digest)
        ):
            _raise_invalid_input()
        if review.plan.image_mode == "approved":
            image_review = review.image_review
            if image_review is None or image_review.counterfactual_execution is None:
                _raise_invalid_input()
            generated = image_review.counterfactual_execution
            if (
                not hmac.compare_digest(
                    references.cloudflare_reference_set_sha256,
                    generated.reference_set_sha256,
                )
                or not hmac.compare_digest(
                    references.cloudflare_request_metadata_sha256,
                    generated.request_metadata_sha256,
                )
                or image_review.reference_review is None
                or image_review.reference_review.condition_set != conditions
            ):
                _raise_invalid_input()
        return ProductionSearchCommand(
            source_text=command.source_text,
            approved_search=approved,
            condition_set=conditions,
            approved_references=references,
        )
    except ProductionSearchError:
        raise
    except (AttributeError, TypeError, ValidationError, ValueError):
        _raise_invalid_input()


def production_search_job_binding_sha256(command: ProductionSearchCommand) -> str:
    """Bind job idempotency to the approval, source, conditions, and references."""
    validated = _validated_command(command)
    payload = json.dumps(
        {
            "schema_version": "1.0",
            "approved_search_sha256": approved_search_sha256(validated.approved_search),
            "approved_references_sha256": approved_counterfactual_references_sha256(
                validated.approved_references
            ),
            "condition_set_sha256": visual_condition_set_sha256(validated.condition_set),
            "source_sha256": _source_sha256(validated.source_text),
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(_BINDING_DOMAIN + payload).hexdigest()


def _validate_no_quota_ledger(usage_ledger: InMemoryUsageLedger) -> None:
    try:
        policies = usage_ledger.snapshot().policies
        if {policy.provider for policy in policies} != {
            "bonsai",
            "cloudflare",
            "outscraper",
        } or any(policy.quota_enforcement != "disabled" for policy in policies):
            _raise_invalid_input()
    except ProductionSearchError:
        raise
    except Exception:
        _raise_invalid_input()


class ProvisionalProductionSearchService:
    """Submit one approved v5 search to the fixed local job executor."""

    __slots__ = (
        "_approval_ledger",
        "_clip_asset_root",
        "_clip_encoder",
        "_executor",
        "_history_repository",
        "_load_outscraper_api_key",
        "_now",
        "_outscraper_transport",
        "_proxy_service",
        "_sleep",
        "_usage_ledger",
    )

    def __init__(
        self,
        *,
        executor: LocalSearchJobExecutor,
        history_repository: SqliteProvisionalHistoryRepository,
        usage_ledger: InMemoryUsageLedger,
        approval_ledger: InMemoryApprovalLedger,
        load_outscraper_api_key: Callable[[], SecretStr],
        outscraper_transport: OutscraperRequestTransport,
        proxy_service: object,
        clip_asset_root: Path,
        clip_encoder: object,
        now: Callable[[], datetime],
        sleep: Callable[[int], None],
    ) -> None:
        if (
            type(executor) is not LocalSearchJobExecutor
            or type(history_repository) is not SqliteProvisionalHistoryRepository
            or not isinstance(usage_ledger, InMemoryUsageLedger)
            or not isinstance(approval_ledger, InMemoryApprovalLedger)
            or not callable(load_outscraper_api_key)
            or not callable(getattr(outscraper_transport, "get", None))
            or not callable(getattr(proxy_service, "fetch_image", None))
            or not isinstance(clip_asset_root, Path)
            or not clip_asset_root.is_absolute()
            or not clip_asset_root.is_dir()
            or not callable(getattr(clip_encoder, "encode_images", None))
            or not callable(now)
            or not callable(sleep)
        ):
            _raise_invalid_input()
        _validate_no_quota_ledger(usage_ledger)
        _utc_now(now)
        self._executor = executor
        self._history_repository = history_repository
        self._usage_ledger = usage_ledger
        self._approval_ledger = approval_ledger
        self._load_outscraper_api_key = load_outscraper_api_key
        self._outscraper_transport = outscraper_transport
        self._proxy_service = proxy_service
        self._clip_asset_root = clip_asset_root
        self._clip_encoder = clip_encoder
        self._now = now
        self._sleep = sleep

    def submit(self, command: ProductionSearchCommand) -> SearchJobSnapshot:
        validated = _validated_command(command)
        submitted_at = _utc_now(self._now)
        if submitted_at >= validated.approved_search.review.plan.expires_at:
            raise ProductionSearchError("Production search approval has expired") from None
        binding = production_search_job_binding_sha256(validated)

        def run(control: SearchJobControl) -> SearchJobResult:
            control.checkpoint()
            key = self._load_outscraper_api_key()
            if not isinstance(key, SecretStr):
                _raise_invalid_input()
            execution = execute_approved_outscraper_request(
                validated.approved_search,
                usage_ledger=self._usage_ledger,
                approval_ledger=self._approval_ledger,
                api_key=key.get_secret_value(),
                transport=self._outscraper_transport,
                now=self._now,
                sleep=self._sleep,
            )
            control.checkpoint()
            result = run_provisional_search(
                execution=execution,
                intent=validated.approved_search.review.intent,
                query_plan=validated.approved_search.review.query_plan,
                typed_proposal=validated.approved_search.review.typed_proposal,
                normalization_profile=(validated.approved_search.review.normalization_profile),
                condition_set=validated.condition_set,
                approved_references=validated.approved_references,
                proxy_service=self._proxy_service,
                asset_root=self._clip_asset_root,
                encoder=self._clip_encoder,
            )
            control.checkpoint()
            completed_at = _utc_now(self._now)
            pending = build_provisional_history_snapshot(
                owner_id=LOCAL_SEARCH_OWNER_ID,
                source_text=validated.source_text,
                completed_at=completed_at,
                condition_set=validated.condition_set,
                approved_references=validated.approved_references,
                ranked_batch=result.ranked_batch,
            )
            detail = self._history_repository.save(pending, now=completed_at)
            return SearchJobResult(
                schema_version="1.0",
                result_locator=detail.locator,
            )

        return self._executor.submit(binding_sha256=binding, runner=run)

    def get(self, locator: str) -> SearchJobSnapshot:
        return self._executor.get(locator)

    def cancel(self, locator: str) -> SearchJobSnapshot:
        return self._executor.cancel(locator)
