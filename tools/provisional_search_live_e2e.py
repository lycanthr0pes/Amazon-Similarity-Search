"""Legacy two-image live diagnostic, separate from the preview-first product flow."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
import hashlib
import hmac
import os
from pathlib import Path
import stat
from typing import Literal
from typing import Protocol

from pydantic import SecretStr

from src.search_v2.approval import ApprovedUsage
from src.search_v2.approval import SearchRuntimeBindings
from src.search_v2.approval import build_search_approval_plan
from src.search_v2.approval import search_approval_plan_sha256
from src.search_v2.counterfactual_cloudflare_http import CounterfactualCloudflareTransport
from src.search_v2.counterfactual_cloudflare_http import (
    CounterfactualCloudflareReferenceExecution,
)
from src.search_v2.counterfactual_cloudflare_http import (
    RequestsCounterfactualCloudflareTransport,
)
from src.search_v2.counterfactual_cloudflare_http import (
    execute_counterfactual_cloudflare_reference_set,
)
from src.search_v2.counterfactual_image import VisualConditionDraft
from src.search_v2.counterfactual_image import VisualConditionSet
from src.search_v2.counterfactual_image import build_visual_condition_set
from src.search_v2.counterfactual_image import visual_condition_set_sha256
from src.search_v2.counterfactual_reference_approval import (
    approve_counterfactual_reference_artifacts,
)
from src.search_v2.image_proxy_service import ImageProxyService
from src.search_v2.image_similarity_process import ProcessIsolatedClipImageEncoder
from src.search_v2.intent import NormalizedSearchIntent
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent
from src.search_v2.outscraper_http import OutscraperRequestTransport
from src.search_v2.playwright_compat import PlaywrightTaskTransport
from src.search_v2.outscraper_http import execute_outscraper_request
from src.search_v2.outscraper_request import authorize_outscraper_request
from src.search_v2.outscraper_request import build_outscraper_request
from src.search_v2.outscraper_request import outscraper_request_sha256
from src.search_v2.product_evidence import product_evidence_profile_sha256
from src.search_v2.product_normalization import ProductNormalizationProfile
from src.search_v2.provisional_approval_repository import (
    CounterfactualReferenceApprovalReview,
)
from src.search_v2.provisional_approval_repository import (
    SqliteCounterfactualApprovalRepository,
)
from src.search_v2.provisional_search_pipeline import ProvisionalSearchResult
from src.search_v2.provisional_search_pipeline import ProvisionalSearchPipelineError
from src.search_v2.provisional_search_pipeline import run_provisional_search
from src.search_v2.query_planner import SearchQuery
from src.search_v2.query_planner import SearchQueryPlan
from src.search_v2.state_machine import InMemoryApprovalLedger
from src.search_v2.state_machine import approve_intent_review
from src.search_v2.state_machine import create_search_session
from src.search_v2.state_machine import issue_search_approval
from src.search_v2.state_machine import record_intent_plan
from src.search_v2.state_machine import start_intent_processing
from src.search_v2.typed_intent_adapter import TypedRequirementProposal
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_ranking import typed_ranking_profile_sha256
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import ProviderUsageLimits
from src.search_v2.usage_ledger import UsageAmount
from src.search_v2.usage_ledger import UsageReservationRequest
from src.search_v2.usage_ledger import usage_policy_sha256


PROVISIONAL_SEARCH_E2E_CLOUDFLARE_CALLS = 2
PROVISIONAL_SEARCH_E2E_TASK_COUNT = 1
PROVISIONAL_SEARCH_E2E_RETRY_COUNT = 0
PROVISIONAL_SEARCH_E2E_MAXIMUM_CANDIDATES = 24
PROVISIONAL_SEARCH_E2E_MAXIMUM_CLIP_BATCHES = 7
SYNTHETIC_INPUT = "白い陶器製マグカップ"
SYNTHETIC_QUERY = "白い 陶器製 マグカップ"

_OWNER_ID = "provisional-search-live-e2e"
_SESSION_ID = "white-ceramic-mug"
_PREIMAGE_PLAN_SHA256 = hashlib.sha256(
    b"amazon-explorer-provisional-search-live-e2e-v1"
).hexdigest()
_CLOUDFLARE_POLICY_SHA256 = hashlib.sha256(
    b"cloudflare-manual-live-e2e-call-only-no-monetary-cap-v1"
).hexdigest()
_OUTSCRAPER_POLICY_SHA256 = hashlib.sha256(
    b"outscraper-manual-live-e2e-task-only-no-monetary-cap-v1"
).hexdigest()
_BONSAI_POLICY_SHA256 = hashlib.sha256(b"bonsai-not-used-live-e2e-v1").hexdigest()
_IMPLEMENTATION_SHA256 = hashlib.sha256(
    b"amazon-explorer-provisional-search-live-e2e-implementation-v1"
).hexdigest()
_OUTPUT_NAMES = ("desired.png", "counterfactual-visual-condition-001.png")

_CONFIGURATION_ERROR = "Provisional search E2E configuration is invalid"
_PREPARATION_ERROR = "Provisional reference preparation failed"
_REFERENCE_ERROR = "Provisional reference review is invalid"
_SEARCH_ERROR = "Provisional product search failed"

FailureStage = Literal[
    "configuration",
    "reference_preparation",
    "reference_validation",
    "approval",
    "product_search",
    "ranking",
]


class ProvisionalSearchLiveE2EError(RuntimeError):
    """Fixed-message failure with non-sensitive stage metadata."""

    def __init__(
        self,
        message: str,
        *,
        failure_stage: FailureStage,
        cloudflare_request_count: int = 0,
        task_count: int = 0,
        failure_substage: str | None = None,
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
        self.failure_stage = failure_stage
        self.cloudflare_request_count = cloudflare_request_count
        self.task_count = task_count
        self.failure_substage = failure_substage
        self.received_candidate_count = received_candidate_count
        self.normalized_product_count = normalized_product_count
        self.rejected_candidate_count = rejected_candidate_count
        self.products_with_image_url = products_with_image_url
        self.image_request_count = image_request_count
        self.image_fetch_success_count = image_fetch_success_count
        self.reference_clip_batch_count = reference_clip_batch_count
        self.candidate_clip_batch_count = candidate_clip_batch_count

    def safe_metadata(self) -> dict[str, object]:
        return {
            "candidate_clip_batch_count": self.candidate_clip_batch_count,
            "cloudflare_request_count": self.cloudflare_request_count,
            "failure_stage": self.failure_stage,
            "failure_substage": self.failure_substage,
            "image_fetch_success_count": self.image_fetch_success_count,
            "image_request_count": self.image_request_count,
            "normalized_product_count": self.normalized_product_count,
            "outcome": "failed",
            "products_with_image_url": self.products_with_image_url,
            "received_candidate_count": self.received_candidate_count,
            "reference_clip_batch_count": self.reference_clip_batch_count,
            "rejected_candidate_count": self.rejected_candidate_count,
            "retry_count": PROVISIONAL_SEARCH_E2E_RETRY_COUNT,
            "task_count": self.task_count,
        }


def _valid_secret(value: object) -> bool:
    if not isinstance(value, SecretStr):
        return False
    secret = value.get_secret_value()
    return bool(
        secret
        and len(secret) <= 4_096
        and secret.isascii()
        and all(0x21 <= ord(character) <= 0x7E for character in secret)
    )


@dataclass(frozen=True, slots=True, repr=False)
class ReferencePreparationLiveE2EConfig:
    account_id: str
    api_token: SecretStr
    review_dir: Path
    approval_db_path: Path

    def __post_init__(self) -> None:
        valid_account = (
            type(self.account_id) is str
            and len(self.account_id) == 32
            and all(character in "0123456789abcdef" for character in self.account_id)
        )
        valid_paths = (
            isinstance(self.review_dir, Path)
            and self.review_dir.is_absolute()
            and isinstance(self.approval_db_path, Path)
            and self.approval_db_path.is_absolute()
            and self.review_dir != self.approval_db_path
        )
        if not valid_account or not _valid_secret(self.api_token) or not valid_paths:
            raise ProvisionalSearchLiveE2EError(
                _CONFIGURATION_ERROR,
                failure_stage="configuration",
            ) from None


@dataclass(frozen=True, slots=True, repr=False)
class ProductSearchLiveE2EConfig:
    asset_root: Path
    api_key: SecretStr | None = None

    def __post_init__(self) -> None:
        if (
            (self.api_key is not None and not _valid_secret(self.api_key))
            or not isinstance(self.asset_root, Path)
            or not self.asset_root.is_absolute()
            or not self.asset_root.is_dir()
        ):
            raise ProvisionalSearchLiveE2EError(
                _CONFIGURATION_ERROR,
                failure_stage="configuration",
            ) from None


@dataclass(frozen=True, slots=True)
class _SavedReference:
    path: Path
    device: int
    inode: int
    byte_length: int
    sha256: str


@dataclass(frozen=True, slots=True, repr=False)
class PreparedReferenceReview:
    review: CounterfactualReferenceApprovalReview
    review_dir: Path
    output_files: tuple[Path, Path]
    _review_device: int
    _review_inode: int
    _intent: NormalizedSearchIntent
    _conditions: VisualConditionSet
    _execution: CounterfactualCloudflareReferenceExecution
    _repository: SqliteCounterfactualApprovalRepository
    _approval_token: str
    _saved_references: tuple[_SavedReference, _SavedReference]

    def safe_metadata(self) -> dict[str, object]:
        return {
            "cloudflare_request_count": PROVISIONAL_SEARCH_E2E_CLOUDFLARE_CALLS,
            "expires_at": self.review.expires_at.isoformat(),
            "image_bytes": tuple(item.byte_length for item in self._execution.images),
            "image_sha256": tuple(item.sha256 for item in self._execution.images),
            "output_files": tuple(str(path) for path in self.output_files),
            "reference_set_sha256": self._execution.reference_set_sha256,
            "retry_count": PROVISIONAL_SEARCH_E2E_RETRY_COUNT,
            "stage": "reference_review_pending",
        }


@dataclass(frozen=True, slots=True, repr=False)
class ProvisionalSearchLiveE2EResult:
    pipeline_result: ProvisionalSearchResult | object
    cloudflare_request_count: Literal[2]
    clip_batch_count: int

    def safe_metadata(self) -> dict[str, int | str]:
        safe = self.pipeline_result.safe_metadata()
        if type(safe) is not dict:
            raise ProvisionalSearchLiveE2EError(
                _SEARCH_ERROR,
                failure_stage="ranking",
                cloudflare_request_count=PROVISIONAL_SEARCH_E2E_CLOUDFLARE_CALLS,
                task_count=PROVISIONAL_SEARCH_E2E_TASK_COUNT,
            ) from None
        return {
            **safe,
            "clip_batch_count": self.clip_batch_count,
            "cloudflare_request_count": self.cloudflare_request_count,
            "stage": "completed",
        }


class _LooseCloudflareTransport(Protocol):
    def post_multipart(self, **kwargs: object): ...


class _CountingCloudflareTransport:
    def __init__(
        self, inner: CounterfactualCloudflareTransport | _LooseCloudflareTransport
    ) -> None:
        self.inner = inner
        self.request_count = 0

    def post_multipart(self, **kwargs: object):
        if self.request_count >= PROVISIONAL_SEARCH_E2E_CLOUDFLARE_CALLS:
            raise ProvisionalSearchLiveE2EError(
                _PREPARATION_ERROR,
                failure_stage="reference_preparation",
                cloudflare_request_count=self.request_count,
            )
        self.request_count += 1
        return self.inner.post_multipart(**kwargs)


class _CountingOutscraperTransport:
    def __init__(self, inner: OutscraperRequestTransport) -> None:
        self.inner = inner
        self.request_count = 0
        self.task_count = 0

    def get(self, **kwargs: object):
        if kwargs.get("params"):
            if self.task_count >= PROVISIONAL_SEARCH_E2E_TASK_COUNT:
                raise ProvisionalSearchLiveE2EError(
                    _SEARCH_ERROR,
                    failure_stage="product_search",
                    cloudflare_request_count=PROVISIONAL_SEARCH_E2E_CLOUDFLARE_CALLS,
                    task_count=self.task_count,
                )
            self.task_count += 1
        self.request_count += 1
        return self.inner.get(**kwargs)


class _CountingEncoder:
    def __init__(self, inner: object) -> None:
        self.inner = inner
        self.batch_count = 0

    def encode_images(self, **kwargs: object):
        if self.batch_count >= PROVISIONAL_SEARCH_E2E_MAXIMUM_CLIP_BATCHES:
            raise ProvisionalSearchLiveE2EError(
                _SEARCH_ERROR,
                failure_stage="ranking",
                cloudflare_request_count=PROVISIONAL_SEARCH_E2E_CLOUDFLARE_CALLS,
                task_count=PROVISIONAL_SEARCH_E2E_TASK_COUNT,
            )
        self.batch_count += 1
        return self.inner.encode_images(**kwargs)


def _fixed_context() -> tuple[NormalizedSearchIntent, VisualConditionSet, TypedRequirementProposal]:
    payload = {
        "product_name_ja": "マグカップ",
        "product_name_en": "ceramic mug",
        "category_ja": "食器",
        "category_en": "tableware",
        "required_terms_ja": ["陶器製"],
        "required_terms_en": ["ceramic"],
        "preferred_terms_ja": [],
        "preferred_terms_en": [],
        "negative_terms_ja": [],
        "negative_terms_en": [],
        "color_ja": "白",
        "color_en": "white",
        "features_ja": [],
        "features_en": [],
        "brand": None,
        "model_number": None,
        "price": {
            "currency": "JPY",
            "mode": "none",
            "target_jpy": None,
            "min_jpy": None,
            "max_jpy": None,
            "source": "none",
            "confidence": None,
        },
        "typed_conditions": [
            {
                "attribute_key": "appearance.color",
                "operator": "equals",
                "expected_value": {"value_type": "enum", "values": ["white"]},
                "strength": "required",
            }
        ],
        "ambiguities": [],
    }
    provenance = build_intent_provenance(
        source_input=SYNTHETIC_INPUT,
        prompt=b"fixed provisional search live E2E prompt provenance",
        schema=b"fixed provisional search live E2E schema provenance",
        response=b"fixed provisional search live E2E response provenance",
    )
    intent = normalize_search_intent(
        SYNTHETIC_INPUT,
        SearchIntentDraft.model_validate(payload),
        provenance=provenance,
    )
    conditions = build_visual_condition_set(
        source_input=SYNTHETIC_INPUT,
        drafts=(
            VisualConditionDraft(
                source_phrase="白い",
                strength="required",
                attribute_key="色",
            ),
        ),
    )
    proposal = build_typed_requirement_proposal(intent)
    if proposal.status != "ready":
        raise ProvisionalSearchLiveE2EError(
            _PREPARATION_ERROR,
            failure_stage="reference_preparation",
        ) from None
    return intent, conditions, proposal


def _cloudflare_usage(now: datetime):
    amount = UsageAmount(
        calls=PROVISIONAL_SEARCH_E2E_CLOUDFLARE_CALLS,
        tokens=0,
        cost_microusd=0,
    )
    policy = ProviderUsageLimits(
        provider="cloudflare",
        pricing_policy_sha256=_CLOUDFLARE_POLICY_SHA256,
        per_user_day=amount,
        per_session=amount,
        global_day=amount,
    )
    ledger = InMemoryUsageLedger([policy])
    reservation = ledger.reserve(
        UsageReservationRequest(
            provider="cloudflare",
            operation="counterfactual_reference_set",
            owner_id=_OWNER_ID,
            session_id=_SESSION_ID,
            binding_sha256=_PREIMAGE_PLAN_SHA256,
            amount=amount,
            pricing_policy_sha256=_CLOUDFLARE_POLICY_SHA256,
        ),
        now=now,
    )
    started = ledger.start(
        reservation.reservation_id,
        owner_id=_OWNER_ID,
        session_id=_SESSION_ID,
        now=now,
    )
    return ledger, started


def _validate_new_review_path(path: Path) -> None:
    try:
        parent = path.parent.lstat()
        if (
            not path.is_absolute()
            or path.name in {"", ".", ".."}
            or not stat.S_ISDIR(parent.st_mode)
            or path.exists()
            or path.is_symlink()
        ):
            raise OSError("review path is unavailable")
    except OSError:
        raise ProvisionalSearchLiveE2EError(
            _CONFIGURATION_ERROR,
            failure_stage="configuration",
        ) from None


def _write_file(path: Path, body: bytes) -> _SavedReference:
    descriptor = -1
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags, 0o600)
        view = memoryview(body)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short write")
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o600)
        details = os.fstat(descriptor)
        return _SavedReference(
            path=path,
            device=details.st_dev,
            inode=details.st_ino,
            byte_length=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
        )
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _save_references(
    review_dir: Path,
    execution: CounterfactualCloudflareReferenceExecution,
) -> tuple[_SavedReference, _SavedReference]:
    created: list[Path] = []
    created_dir = False
    try:
        os.mkdir(review_dir, 0o700)
        created_dir = True
        os.chmod(review_dir, 0o700)
        saved = []
        for name, image in zip(_OUTPUT_NAMES, execution.images, strict=True):
            item = _write_file(review_dir / name, image.body)
            saved.append(item)
            created.append(item.path)
        if len(saved) != PROVISIONAL_SEARCH_E2E_CLOUDFLARE_CALLS:
            raise ValueError("reference count is invalid")
        return saved[0], saved[1]
    except Exception:
        for path in reversed(created):
            try:
                path.unlink()
            except OSError:
                pass
        if created_dir:
            try:
                review_dir.rmdir()
            except OSError:
                pass
        raise ProvisionalSearchLiveE2EError(
            _PREPARATION_ERROR,
            failure_stage="reference_preparation",
            cloudflare_request_count=PROVISIONAL_SEARCH_E2E_CLOUDFLARE_CALLS,
        ) from None


def prepare_reference_review(
    config: ReferencePreparationLiveE2EConfig,
    *,
    transport: CounterfactualCloudflareTransport | _LooseCloudflareTransport | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> PreparedReferenceReview:
    """Generate and persist two review images, then return without product access."""
    if type(config) is not ReferencePreparationLiveE2EConfig or not callable(now):
        raise ProvisionalSearchLiveE2EError(
            _CONFIGURATION_ERROR,
            failure_stage="configuration",
        ) from None
    _validate_new_review_path(config.review_dir)
    try:
        approval_parent = config.approval_db_path.parent.lstat()
        if not stat.S_ISDIR(approval_parent.st_mode) or config.approval_db_path.is_symlink():
            raise OSError("approval path is unavailable")
        repository = SqliteCounterfactualApprovalRepository(config.approval_db_path)
        current_time = now()
        intent, conditions, _proposal = _fixed_context()
        usage_ledger, reservation = _cloudflare_usage(current_time)
        counting = _CountingCloudflareTransport(
            transport or RequestsCounterfactualCloudflareTransport()
        )
        execution = execute_counterfactual_cloudflare_reference_set(
            intent=intent,
            condition_set=conditions,
            preimage_plan_sha256=_PREIMAGE_PLAN_SHA256,
            usage_ledger=usage_ledger,
            usage_reservation=reservation,
            account_id=config.account_id,
            api_token=config.api_token.get_secret_value(),
            transport=counting,
            now=now,
        )
        if counting.request_count != PROVISIONAL_SEARCH_E2E_CLOUDFLARE_CALLS:
            raise ValueError("Cloudflare request count is invalid")
    except ProvisionalSearchLiveE2EError:
        raise
    except Exception:
        request_count = counting.request_count if "counting" in locals() else 0
        raise ProvisionalSearchLiveE2EError(
            _PREPARATION_ERROR,
            failure_stage="reference_preparation",
            cloudflare_request_count=request_count,
        ) from None

    saved = _save_references(config.review_dir, execution)
    try:
        issued = repository.issue(
            owner_id=_OWNER_ID,
            session_id=_SESSION_ID,
            condition_set_sha256=visual_condition_set_sha256(conditions),
            reference_set_sha256=execution.reference_set_sha256,
            request_metadata_sha256=execution.request_metadata_sha256,
            usage_reservation=execution.usage_reservation,
            now=now(),
        )
    except Exception:
        for item in reversed(saved):
            try:
                item.path.unlink()
            except OSError:
                pass
        try:
            config.review_dir.rmdir()
        except OSError:
            pass
        raise ProvisionalSearchLiveE2EError(
            _PREPARATION_ERROR,
            failure_stage="reference_preparation",
            cloudflare_request_count=PROVISIONAL_SEARCH_E2E_CLOUDFLARE_CALLS,
        ) from None

    review_details = config.review_dir.stat(follow_symlinks=False)
    return PreparedReferenceReview(
        review=issued.review,
        review_dir=config.review_dir,
        output_files=(saved[0].path, saved[1].path),
        _review_device=review_details.st_dev,
        _review_inode=review_details.st_ino,
        _intent=intent,
        _conditions=conditions,
        _execution=execution,
        _repository=repository,
        _approval_token=issued.token,
        _saved_references=saved,
    )


def _read_saved_reference(saved: _SavedReference) -> bytes:
    descriptor = -1
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(saved.path, flags)
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_dev != saved.device
            or before.st_ino != saved.inode
            or before.st_nlink != 1
            or before.st_size != saved.byte_length
            or (os.name == "posix" and stat.S_IMODE(before.st_mode) != 0o600)
        ):
            raise ValueError("saved reference identity changed")
        body = bytearray()
        while len(body) <= saved.byte_length:
            chunk = os.read(descriptor, min(65_536, saved.byte_length + 1 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
        after = os.fstat(descriptor)
        stable_before = (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_uid,
            before.st_gid,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        stable_after = (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_uid,
            after.st_gid,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if stable_before != stable_after or len(body) != saved.byte_length:
            raise ValueError("saved reference changed during validation")
        return bytes(body)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _verify_saved_references(prepared: PreparedReferenceReview) -> None:
    try:
        if tuple(item.path for item in prepared._saved_references) != prepared.output_files:
            raise ValueError("saved paths changed")
        directory = prepared.review_dir.lstat()
        if (
            not stat.S_ISDIR(directory.st_mode)
            or directory.st_dev != prepared._review_device
            or directory.st_ino != prepared._review_inode
        ):
            raise ValueError("review directory changed")
        if os.name == "posix" and stat.S_IMODE(directory.st_mode) != 0o700:
            raise ValueError("review directory mode changed")
        for saved, artifact in zip(
            prepared._saved_references,
            prepared._execution.images,
            strict=True,
        ):
            body = _read_saved_reference(saved)
            if (
                len(body) != saved.byte_length
                or not hmac.compare_digest(hashlib.sha256(body).hexdigest(), saved.sha256)
                or not hmac.compare_digest(body, artifact.body)
            ):
                raise ValueError("saved reference content changed")
    except Exception:
        raise ProvisionalSearchLiveE2EError(
            _REFERENCE_ERROR,
            failure_stage="reference_validation",
            cloudflare_request_count=PROVISIONAL_SEARCH_E2E_CLOUDFLARE_CALLS,
        ) from None


def _search_policies() -> list[ProviderUsageLimits]:
    zero = UsageAmount(calls=0, tokens=0, cost_microusd=0)
    one_task = UsageAmount(calls=1, tokens=0, cost_microusd=0)
    return [
        ProviderUsageLimits(
            provider="bonsai",
            pricing_policy_sha256=_BONSAI_POLICY_SHA256,
            per_user_day=zero,
            per_session=zero,
            global_day=zero,
        ),
        ProviderUsageLimits(
            provider="cloudflare",
            pricing_policy_sha256=_CLOUDFLARE_POLICY_SHA256,
            per_user_day=zero,
            per_session=zero,
            global_day=zero,
        ),
        ProviderUsageLimits(
            provider="outscraper",
            pricing_policy_sha256=_OUTSCRAPER_POLICY_SHA256,
            per_user_day=one_task,
            per_session=one_task,
            global_day=one_task,
        ),
    ]


def _authorize_product_search(
    *,
    intent: NormalizedSearchIntent,
    proposal: TypedRequirementProposal,
    now: datetime,
):
    query_plan = SearchQueryPlan(
        schema_version="2.0",
        intent_sha256=proposal.intent_sha256,
        queries=[SearchQuery(language="ja", value=SYNTHETIC_QUERY)],
    )
    request = build_outscraper_request(query_plan, postal_code="100-0001")
    session = create_search_session(owner_id=_OWNER_ID, session_id=_SESSION_ID, now=now)
    session = start_intent_processing(
        session,
        expected_revision=session.revision,
        now=now,
    )
    session = record_intent_plan(
        session,
        intent=intent,
        query_plan=query_plan,
        typed_proposal=proposal,
        expected_revision=session.revision,
        now=now,
    )
    session = approve_intent_review(
        session,
        use_images=False,
        image_reservation=None,
        expected_revision=session.revision,
        now=now,
    )
    policies = _search_policies()
    policy_digest = usage_policy_sha256(policies)
    plan = build_search_approval_plan(
        owner_id=_OWNER_ID,
        session_id=_SESSION_ID,
        intent=intent,
        query_plan=query_plan,
        outscraper_request_sha256=outscraper_request_sha256(request),
        image_set_sha256=None,
        image_request_metadata_sha256=None,
        usage_allowances=[
            ApprovedUsage(
                provider="bonsai",
                calls=0,
                tokens=0,
                cost_microusd=0,
                pricing_policy_sha256=_BONSAI_POLICY_SHA256,
            ),
            ApprovedUsage(
                provider="cloudflare",
                calls=0,
                tokens=0,
                cost_microusd=0,
                pricing_policy_sha256=_CLOUDFLARE_POLICY_SHA256,
            ),
            ApprovedUsage(
                provider="outscraper",
                calls=1,
                tokens=0,
                cost_microusd=0,
                pricing_policy_sha256=_OUTSCRAPER_POLICY_SHA256,
            ),
        ],
        runtime_bindings=SearchRuntimeBindings(
            bonsai_model_id="fixed-live-e2e-intent",
            bonsai_prompt_sha256=intent.provenance.prompt_sha256,
            bonsai_schema_sha256=intent.provenance.schema_sha256,
            cloudflare_model_id=None,
            image_prompt_sha256=None,
            ranking_profile_id="typed-ranking-v4",
            ranking_profile_sha256=typed_ranking_profile_sha256(),
            product_evidence_profile_sha256=product_evidence_profile_sha256(),
            implementation_sha256=_IMPLEMENTATION_SHA256,
            usage_policy_sha256=policy_digest,
        ),
        created_at=now,
    )
    issued = issue_search_approval(
        session,
        plan=plan,
        expected_revision=session.revision,
        now=now,
    )
    usage_ledger = InMemoryUsageLedger(policies)
    amount = UsageAmount(calls=1, tokens=0, cost_microusd=0)
    reserved = usage_ledger.reserve(
        UsageReservationRequest(
            provider="outscraper",
            operation="product_search",
            owner_id=_OWNER_ID,
            session_id=_SESSION_ID,
            binding_sha256=search_approval_plan_sha256(plan),
            amount=amount,
            pricing_policy_sha256=_OUTSCRAPER_POLICY_SHA256,
        ),
        now=now,
    )
    started = usage_ledger.start(
        reserved.reservation_id,
        owner_id=_OWNER_ID,
        session_id=_SESSION_ID,
        now=now,
    )
    permit = authorize_outscraper_request(
        request,
        session=issued.session,
        approval_ledger=InMemoryApprovalLedger(),
        token=issued.token,
        plan=plan,
        outscraper_reservation=started,
        owner_id=_OWNER_ID,
        session_id=_SESSION_ID,
        expected_revision=issued.session.revision,
        now=now,
    )
    return query_plan, request, permit, usage_ledger, started


def approve_reference_and_run(
    prepared: PreparedReferenceReview,
    *,
    human_confirmed: Literal[True],
    load_product_config: Callable[[], ProductSearchLiveE2EConfig],
    outscraper_transport: OutscraperRequestTransport | None = None,
    proxy_service: object | None = None,
    encoder: object | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    sleep: Callable[[int], None],
) -> ProvisionalSearchLiveE2EResult:
    """Consume the reviewed references, then execute one product-search task."""
    if (
        type(prepared) is not PreparedReferenceReview
        or human_confirmed is not True
        or not callable(load_product_config)
        or not callable(now)
        or not callable(sleep)
    ):
        raise ProvisionalSearchLiveE2EError(
            _CONFIGURATION_ERROR,
            failure_stage="configuration",
            cloudflare_request_count=PROVISIONAL_SEARCH_E2E_CLOUDFLARE_CALLS,
        ) from None
    _verify_saved_references(prepared)
    current_time = now()
    try:
        receipt = prepared._repository.consume(
            review=prepared.review,
            token=prepared._approval_token,
            human_confirmed=True,
            now=current_time,
        )
        approved = approve_counterfactual_reference_artifacts(
            condition_set=prepared._conditions,
            request_set=prepared._execution.request_set,
            images=prepared._execution.images,
            reference_set_sha256=prepared._execution.reference_set_sha256,
            request_metadata_sha256=prepared._execution.request_metadata_sha256,
            approval_receipt=receipt,
        )
    except Exception:
        raise ProvisionalSearchLiveE2EError(
            _REFERENCE_ERROR,
            failure_stage="approval",
            cloudflare_request_count=PROVISIONAL_SEARCH_E2E_CLOUDFLARE_CALLS,
        ) from None

    try:
        config = load_product_config()
        if type(config) is not ProductSearchLiveE2EConfig:
            raise TypeError("product configuration is invalid")
        proposal = build_typed_requirement_proposal(prepared._intent)
        query_plan, _request, permit, usage_ledger, reservation = _authorize_product_search(
            intent=prepared._intent,
            proposal=proposal,
            now=current_time,
        )
        counting_transport = _CountingOutscraperTransport(
            outscraper_transport or PlaywrightTaskTransport()
        )
        execution = execute_outscraper_request(
            permit,
            usage_ledger=usage_ledger,
            usage_reservation=reservation,
            api_key=config.api_key.get_secret_value() if config.api_key is not None else "",
            transport=counting_transport,
            now=now,
            sleep=sleep,
        )
        if counting_transport.task_count != PROVISIONAL_SEARCH_E2E_TASK_COUNT:
            raise ValueError("Outscraper task count is invalid")
    except Exception:
        task_count = counting_transport.task_count if "counting_transport" in locals() else 0
        raise ProvisionalSearchLiveE2EError(
            _SEARCH_ERROR,
            failure_stage="product_search",
            cloudflare_request_count=PROVISIONAL_SEARCH_E2E_CLOUDFLARE_CALLS,
            task_count=task_count,
        ) from None

    try:
        selected_proxy = proxy_service or ImageProxyService(allowed_hosts=("m.media-amazon.com",))
        selected_encoder = encoder or ProcessIsolatedClipImageEncoder()
        counting_encoder = _CountingEncoder(selected_encoder)
        pipeline_result = run_provisional_search(
            execution=execution,
            intent=prepared._intent,
            query_plan=query_plan,
            typed_proposal=proposal,
            normalization_profile=ProductNormalizationProfile(
                schema_version="2.0",
                profile_id="observed-only-v2",
                usd_to_jpy_rate=160,
            ),
            condition_set=prepared._conditions,
            approved_references=approved,
            proxy_service=selected_proxy,
            asset_root=config.asset_root,
            encoder=counting_encoder,
        )
        if counting_encoder.batch_count > PROVISIONAL_SEARCH_E2E_MAXIMUM_CLIP_BATCHES:
            raise ValueError("CLIP batch count is invalid")
        result = ProvisionalSearchLiveE2EResult(
            pipeline_result=pipeline_result,
            cloudflare_request_count=PROVISIONAL_SEARCH_E2E_CLOUDFLARE_CALLS,
            clip_batch_count=counting_encoder.batch_count,
        )
        result.safe_metadata()
        return result
    except ProvisionalSearchPipelineError as error:
        diagnostic = error.safe_metadata()
        raise ProvisionalSearchLiveE2EError(
            _SEARCH_ERROR,
            failure_stage="ranking",
            failure_substage=error.failure_substage,
            cloudflare_request_count=PROVISIONAL_SEARCH_E2E_CLOUDFLARE_CALLS,
            task_count=PROVISIONAL_SEARCH_E2E_TASK_COUNT,
            received_candidate_count=diagnostic["received_candidate_count"],
            normalized_product_count=diagnostic["normalized_product_count"],
            rejected_candidate_count=diagnostic["rejected_candidate_count"],
            products_with_image_url=diagnostic["products_with_image_url"],
            image_request_count=diagnostic["image_request_count"],
            image_fetch_success_count=diagnostic["image_fetch_success_count"],
            reference_clip_batch_count=diagnostic["reference_clip_batch_count"],
            candidate_clip_batch_count=diagnostic["candidate_clip_batch_count"],
        ) from None
    except ProvisionalSearchLiveE2EError:
        raise
    except Exception:
        raise ProvisionalSearchLiveE2EError(
            _SEARCH_ERROR,
            failure_stage="ranking",
            cloudflare_request_count=PROVISIONAL_SEARCH_E2E_CLOUDFLARE_CALLS,
            task_count=PROVISIONAL_SEARCH_E2E_TASK_COUNT,
        ) from None


__all__ = [
    "PROVISIONAL_SEARCH_E2E_CLOUDFLARE_CALLS",
    "PROVISIONAL_SEARCH_E2E_MAXIMUM_CANDIDATES",
    "PROVISIONAL_SEARCH_E2E_MAXIMUM_CLIP_BATCHES",
    "PROVISIONAL_SEARCH_E2E_RETRY_COUNT",
    "PROVISIONAL_SEARCH_E2E_TASK_COUNT",
    "ProductSearchLiveE2EConfig",
    "ProvisionalSearchLiveE2EError",
    "ProvisionalSearchLiveE2EResult",
    "ReferencePreparationLiveE2EConfig",
    "SYNTHETIC_INPUT",
    "SYNTHETIC_QUERY",
    "approve_reference_and_run",
    "prepare_reference_review",
]
