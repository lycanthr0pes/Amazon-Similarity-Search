from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
import hashlib
import os
from pathlib import Path
import stat
import time
from typing import Literal
from typing import Protocol

from pydantic import SecretStr

from src.search_v2.counterfactual_cloudflare_http import (
    CounterfactualCloudflareTransport,
)
from src.search_v2.counterfactual_cloudflare_http import (
    RequestsCounterfactualCloudflareTransport,
)
from src.search_v2.counterfactual_cloudflare_http import (
    execute_counterfactual_cloudflare_reference_set,
)
from src.search_v2.counterfactual_cloudflare_request import (
    COUNTERFACTUAL_PROMPT_CONTRACT_VERSION,
)
from src.search_v2.counterfactual_cloudflare_request import (
    counterfactual_prompt_contract_sha256,
)
from src.search_v2.counterfactual_image import VisualConditionDraft
from src.search_v2.counterfactual_image import build_visual_condition_set
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import ProviderUsageLimits
from src.search_v2.usage_ledger import UsageAmount
from src.search_v2.usage_ledger import UsageReservationRequest


COUNTERFACTUAL_CLOUDFLARE_E2E_REQUEST_COUNT = 2
COUNTERFACTUAL_CLOUDFLARE_E2E_RETRY_COUNT = 0
COUNTERFACTUAL_CLOUDFLARE_E2E_COST_MICROUSD = 633
SYNTHETIC_INPUT = "白い陶器製マグカップ"
VISUAL_CONDITION = "白い"

_PLAN_SHA256 = hashlib.sha256(
    b"amazon-explorer-counterfactual-cloudflare-minimum-live-e2e-v1"
).hexdigest()
_PRICING_POLICY_SHA256 = hashlib.sha256(
    b"flux-2-klein-4b:two-output-tiles:one-input-tile:633-microusd"
).hexdigest()
_OWNER_ID = "counterfactual-cloudflare-live-e2e"
_SESSION_ID = "minimum-reference-set"
_OUTPUT_NAMES = ("desired.png", "counterfactual-visual-condition-001.png")

_CONFIGURATION_ERROR = "Counterfactual Cloudflare E2E configuration is invalid"
_OUTPUT_ERROR = "Counterfactual Cloudflare E2E output is invalid"
_EXECUTION_ERROR = "Counterfactual Cloudflare E2E request failed"

FailureStage = Literal["configuration", "output", "execution"]


class CounterfactualCloudflareLiveE2EError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        failure_stage: FailureStage,
        request_count: int = 0,
        wall_milliseconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_stage = failure_stage
        self.request_count = request_count
        self.retry_count = COUNTERFACTUAL_CLOUDFLARE_E2E_RETRY_COUNT
        self.wall_milliseconds = wall_milliseconds

    def safe_metadata(self) -> dict[str, int | str | None]:
        return {
            "failure_stage": self.failure_stage,
            "outcome": "failed",
            "request_count": self.request_count,
            "retry_count": self.retry_count,
            "wall_milliseconds": self.wall_milliseconds,
        }


class _Transport(Protocol):
    def post_multipart(self, **kwargs: object): ...


class _CountingTransport:
    def __init__(self, inner: CounterfactualCloudflareTransport | _Transport) -> None:
        self.inner = inner
        self.request_count = 0

    def post_multipart(self, **kwargs: object):
        self.request_count += 1
        return self.inner.post_multipart(**kwargs)


@dataclass(frozen=True, slots=True, repr=False)
class CounterfactualCloudflareLiveE2EConfig:
    account_id: str
    api_token: SecretStr
    output_dir: Path

    def __post_init__(self) -> None:
        if (
            type(self.account_id) is not str
            or len(self.account_id) != 32
            or any(character not in "0123456789abcdef" for character in self.account_id)
            or not isinstance(self.api_token, SecretStr)
            or not self.api_token.get_secret_value()
        ):
            raise CounterfactualCloudflareLiveE2EError(
                _CONFIGURATION_ERROR,
                failure_stage="configuration",
            ) from None
        if not isinstance(self.output_dir, Path):
            raise CounterfactualCloudflareLiveE2EError(
                _OUTPUT_ERROR,
                failure_stage="output",
            ) from None


@dataclass(frozen=True, slots=True)
class CounterfactualCloudflareLiveE2EResult:
    request_count: int
    retry_count: int
    model_id: str
    seeds: tuple[int, int]
    image_sha256: tuple[str, str]
    image_bytes: tuple[int, int]
    reference_set_sha256: str
    wall_milliseconds: int
    output_files: tuple[Path, Path]

    def safe_metadata(self) -> dict[str, object]:
        return {
            "image_bytes": self.image_bytes,
            "image_sha256": self.image_sha256,
            "model_id": self.model_id,
            "outcome": "succeeded",
            "output_files": tuple(str(path) for path in self.output_files),
            "reference_set_sha256": self.reference_set_sha256,
            "request_count": self.request_count,
            "retry_count": self.retry_count,
            "seeds": self.seeds,
            "wall_milliseconds": self.wall_milliseconds,
        }


def _elapsed_milliseconds(started: int) -> int:
    return max(1, (time.monotonic_ns() - started + 999_999) // 1_000_000)


def _fixed_context():
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
        "typed_conditions": [],
        "ambiguities": [],
    }
    provenance = build_intent_provenance(
        source_input=SYNTHETIC_INPUT,
        prompt=b"fixed counterfactual Cloudflare live E2E prompt provenance",
        schema=b"fixed counterfactual Cloudflare live E2E schema provenance",
        response=b"fixed counterfactual Cloudflare live E2E response provenance",
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
                source_phrase=VISUAL_CONDITION,
                strength="required",
                attribute_key="色",
            ),
        ),
    )
    return intent, conditions


def _validated_output_dir(path: Path) -> Path:
    if not path.is_absolute() or path.name in {"", ".", ".."}:
        raise CounterfactualCloudflareLiveE2EError(
            _OUTPUT_ERROR,
            failure_stage="output",
        ) from None
    try:
        parent = path.parent.lstat()
        if not stat.S_ISDIR(parent.st_mode) or path.exists() or path.is_symlink():
            raise OSError("output path is unavailable")
    except CounterfactualCloudflareLiveE2EError:
        raise
    except OSError:
        raise CounterfactualCloudflareLiveE2EError(
            _OUTPUT_ERROR,
            failure_stage="output",
        ) from None
    return path


def _write_file(path: Path, body: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        view = memoryview(body)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short write")
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o600)
    finally:
        os.close(descriptor)


def _write_output_set(output_dir: Path, images: tuple[object, ...]) -> tuple[Path, Path]:
    created_paths: list[Path] = []
    created_dir = False
    try:
        os.mkdir(output_dir, 0o700)
        created_dir = True
        os.chmod(output_dir, 0o700)
        for name, image in zip(_OUTPUT_NAMES, images, strict=True):
            body = getattr(image, "body")
            if type(body) is not bytes:
                raise TypeError("image body is invalid")
            path = output_dir / name
            _write_file(path, body)
            created_paths.append(path)
        if len(created_paths) != COUNTERFACTUAL_CLOUDFLARE_E2E_REQUEST_COUNT:
            raise ValueError("output count is invalid")
        return created_paths[0], created_paths[1]
    except Exception:
        for path in reversed(created_paths):
            try:
                path.unlink()
            except OSError:
                pass
        if created_dir:
            try:
                output_dir.rmdir()
            except OSError:
                pass
        raise CounterfactualCloudflareLiveE2EError(
            _OUTPUT_ERROR,
            failure_stage="output",
            request_count=COUNTERFACTUAL_CLOUDFLARE_E2E_REQUEST_COUNT,
        ) from None


def _usage_context(now: datetime):
    amount = UsageAmount(
        calls=COUNTERFACTUAL_CLOUDFLARE_E2E_REQUEST_COUNT,
        tokens=0,
        cost_microusd=COUNTERFACTUAL_CLOUDFLARE_E2E_COST_MICROUSD,
    )
    policy = ProviderUsageLimits(
        provider="cloudflare",
        pricing_policy_sha256=_PRICING_POLICY_SHA256,
        per_user_day=amount,
        per_session=amount,
        global_day=amount,
    )
    ledger = InMemoryUsageLedger([policy])
    reserved = ledger.reserve(
        UsageReservationRequest(
            provider="cloudflare",
            operation="counterfactual_reference_set",
            owner_id=_OWNER_ID,
            session_id=_SESSION_ID,
            binding_sha256=_PLAN_SHA256,
            amount=amount,
            pricing_policy_sha256=_PRICING_POLICY_SHA256,
        ),
        now=now,
    )
    started = ledger.start(
        reserved.reservation_id,
        owner_id=_OWNER_ID,
        session_id=_SESSION_ID,
        now=now,
    )
    return ledger, started


def run_counterfactual_cloudflare_live_e2e(
    config: CounterfactualCloudflareLiveE2EConfig,
    *,
    transport: CounterfactualCloudflareTransport | _Transport | None = None,
) -> CounterfactualCloudflareLiveE2EResult:
    if type(config) is not CounterfactualCloudflareLiveE2EConfig:
        raise CounterfactualCloudflareLiveE2EError(
            _CONFIGURATION_ERROR,
            failure_stage="configuration",
        ) from None
    output_dir = _validated_output_dir(config.output_dir)
    selected_transport = transport or RequestsCounterfactualCloudflareTransport()
    if not callable(getattr(selected_transport, "post_multipart", None)):
        raise CounterfactualCloudflareLiveE2EError(
            _CONFIGURATION_ERROR,
            failure_stage="configuration",
        ) from None

    counting_transport = _CountingTransport(selected_transport)
    started_at = time.monotonic_ns()
    now = datetime.now(timezone.utc)
    try:
        intent, conditions = _fixed_context()
        ledger, reservation = _usage_context(now)
        execution = execute_counterfactual_cloudflare_reference_set(
            intent=intent,
            condition_set=conditions,
            preimage_plan_sha256=_PLAN_SHA256,
            usage_ledger=ledger,
            usage_reservation=reservation,
            account_id=config.account_id,
            api_token=config.api_token.get_secret_value(),
            transport=counting_transport,
            now=lambda: datetime.now(timezone.utc),
        )
    except Exception:
        raise CounterfactualCloudflareLiveE2EError(
            _EXECUTION_ERROR,
            failure_stage="execution",
            request_count=counting_transport.request_count,
            wall_milliseconds=_elapsed_milliseconds(started_at),
        ) from None

    if (
        counting_transport.request_count != COUNTERFACTUAL_CLOUDFLARE_E2E_REQUEST_COUNT
        or execution.request_set.call_count != COUNTERFACTUAL_CLOUDFLARE_E2E_REQUEST_COUNT
        or len(execution.images) != COUNTERFACTUAL_CLOUDFLARE_E2E_REQUEST_COUNT
        or execution.usage_reservation.status != "succeeded"
        or COUNTERFACTUAL_PROMPT_CONTRACT_VERSION != "amazon-explorer-counterfactual-prompt-v2"
        or execution.request_set.prompt_contract_sha256 != counterfactual_prompt_contract_sha256()
    ):
        raise CounterfactualCloudflareLiveE2EError(
            _EXECUTION_ERROR,
            failure_stage="execution",
            request_count=counting_transport.request_count,
            wall_milliseconds=_elapsed_milliseconds(started_at),
        ) from None
    try:
        output_files = _write_output_set(output_dir, execution.images)
    except CounterfactualCloudflareLiveE2EError as error:
        raise CounterfactualCloudflareLiveE2EError(
            _OUTPUT_ERROR,
            failure_stage="output",
            request_count=error.request_count,
            wall_milliseconds=_elapsed_milliseconds(started_at),
        ) from None
    wall_milliseconds = _elapsed_milliseconds(started_at)
    return CounterfactualCloudflareLiveE2EResult(
        request_count=counting_transport.request_count,
        retry_count=COUNTERFACTUAL_CLOUDFLARE_E2E_RETRY_COUNT,
        model_id=execution.request_set.requests[0].model_id,
        seeds=tuple(request.seed for request in execution.request_set.requests),
        image_sha256=tuple(image.sha256 for image in execution.images),
        image_bytes=tuple(image.byte_length for image in execution.images),
        reference_set_sha256=execution.reference_set_sha256,
        wall_milliseconds=wall_milliseconds,
        output_files=output_files,
    )
