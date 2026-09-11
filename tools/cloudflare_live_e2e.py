from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
import time
from typing import Literal

from pydantic import SecretStr

from src.search_v2.cloudflare_http import CLOUDFLARE_MAX_RESPONSE_BYTES
from src.search_v2.cloudflare_http import CLOUDFLARE_REQUEST_TIMEOUT_SECONDS
from src.search_v2.cloudflare_http import CloudflareExecutionError
from src.search_v2.cloudflare_http import CloudflareHttpResponse
from src.search_v2.cloudflare_http import CloudflareImageError
from src.search_v2.cloudflare_http import CloudflareRequestTransport
from src.search_v2.cloudflare_http import CloudflareResponseContractError
from src.search_v2.cloudflare_http import CloudflareTransportError
from src.search_v2.cloudflare_http import RequestsCloudflareTransport
from src.search_v2.cloudflare_http import cloudflare_endpoint
from src.search_v2.cloudflare_http import parse_cloudflare_image_response
from src.search_v2.cloudflare_request import CLOUDFLARE_IMAGE_MODEL_ID
from src.search_v2.cloudflare_request import build_cloudflare_front_request
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent


CLOUDFLARE_E2E_REQUEST_COUNT = 1
CLOUDFLARE_E2E_RETRY_COUNT = 0
SYNTHETIC_INPUT = "白い無地の陶器製マグカップ"
_PLAN_SHA256 = hashlib.sha256(b"amazon-explorer-cloudflare-single-image-live-e2e-v1").hexdigest()

_CONFIGURATION_ERROR = "Cloudflare E2E configuration is invalid"
_OUTPUT_ERROR = "Cloudflare E2E output is invalid"
_REQUEST_ERROR = "Cloudflare E2E request failed"

CloudflareLiveFailureStage = Literal[
    "configuration",
    "output",
    "transport",
    "http_status",
    "response_contract",
    "image_content",
    "unexpected",
]


class CloudflareLiveE2EError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        failure_stage: CloudflareLiveFailureStage,
        http_status_code: int | None = None,
        request_count: int = 0,
        wall_milliseconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_stage = failure_stage
        self.http_status_code = http_status_code
        self.request_count = request_count
        self.retry_count = CLOUDFLARE_E2E_RETRY_COUNT
        self.wall_milliseconds = wall_milliseconds

    def safe_metadata(self) -> dict[str, int | str | None]:
        return {
            "failure_stage": self.failure_stage,
            "http_status_code": self.http_status_code,
            "outcome": "failed",
            "request_count": self.request_count,
            "retry_count": self.retry_count,
            "wall_milliseconds": self.wall_milliseconds,
        }


def _raise_configuration_error() -> None:
    raise CloudflareLiveE2EError(
        _CONFIGURATION_ERROR,
        failure_stage="configuration",
    ) from None


def _raise_output_error(
    *,
    request_count: int = 0,
    wall_milliseconds: int | None = None,
) -> None:
    raise CloudflareLiveE2EError(
        _OUTPUT_ERROR,
        failure_stage="output",
        request_count=request_count,
        wall_milliseconds=wall_milliseconds,
    ) from None


def _elapsed_milliseconds(started: int) -> int:
    return max(1, (time.monotonic_ns() - started + 999_999) // 1_000_000)


def _raise_request_error(
    *,
    failure_stage: CloudflareLiveFailureStage,
    started: int,
    http_status_code: int | None = None,
) -> None:
    raise CloudflareLiveE2EError(
        _REQUEST_ERROR,
        failure_stage=failure_stage,
        http_status_code=http_status_code,
        request_count=CLOUDFLARE_E2E_REQUEST_COUNT,
        wall_milliseconds=_elapsed_milliseconds(started),
    ) from None


@dataclass(frozen=True, slots=True, repr=False)
class CloudflareLiveE2EConfig:
    account_id: str
    api_token: SecretStr
    output_path: Path

    def __post_init__(self) -> None:
        try:
            cloudflare_endpoint(self.account_id)
        except (CloudflareExecutionError, TypeError, ValueError):
            _raise_configuration_error()
        if not isinstance(self.api_token, SecretStr) or not self.api_token.get_secret_value():
            _raise_configuration_error()
        if not isinstance(self.output_path, Path):
            _raise_output_error()


@dataclass(frozen=True, slots=True)
class CloudflareLiveE2EResult:
    request_count: int
    retry_count: int
    model_id: str
    seed: int
    image_sha256: str
    image_bytes: int
    width: int
    height: int
    wall_milliseconds: int
    output_path: Path


def _fixed_intent():
    payload = {
        "product_name_ja": "マグカップ",
        "product_name_en": "ceramic mug",
        "category_ja": "食器",
        "category_en": "tableware",
        "required_terms_ja": ["無地", "陶器製"],
        "required_terms_en": ["plain", "ceramic"],
        "preferred_terms_ja": [],
        "preferred_terms_en": [],
        "negative_terms_ja": [],
        "negative_terms_en": [],
        "color_ja": "白",
        "color_en": "white",
        "features_ja": ["持ち手付き"],
        "features_en": ["single handle"],
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
        prompt=b"fixed Cloudflare live E2E prompt provenance",
        schema=b"fixed Cloudflare live E2E schema provenance",
        response=b"fixed Cloudflare live E2E response provenance",
    )
    return normalize_search_intent(
        SYNTHETIC_INPUT,
        SearchIntentDraft.model_validate(payload),
        provenance=provenance,
    )


def _validated_output_path(path: Path) -> Path:
    if not path.is_absolute() or path.suffix.casefold() != ".png":
        _raise_output_error()
    try:
        parent_details = path.parent.lstat()
        if not stat.S_ISDIR(parent_details.st_mode) or path.exists() or path.is_symlink():
            _raise_output_error()
    except CloudflareLiveE2EError:
        raise
    except OSError:
        _raise_output_error()
    return path


def _write_exclusive_png(path: Path, body: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    created = False
    try:
        descriptor = os.open(path, flags, 0o600)
        created = True
        view = memoryview(body)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short write")
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o600)
    except OSError:
        if created:
            try:
                path.unlink()
            except OSError:
                pass
        _raise_output_error()
    finally:
        if descriptor is not None:
            os.close(descriptor)


def run_cloudflare_live_e2e(
    config: CloudflareLiveE2EConfig,
    *,
    transport: CloudflareRequestTransport | None = None,
) -> CloudflareLiveE2EResult:
    if type(config) is not CloudflareLiveE2EConfig:
        _raise_configuration_error()
    output_path = _validated_output_path(config.output_path)
    selected_transport = transport if transport is not None else RequestsCloudflareTransport()
    if not callable(getattr(selected_transport, "post_multipart", None)):
        _raise_configuration_error()

    request = build_cloudflare_front_request(
        intent=_fixed_intent(),
        preimage_plan_sha256=_PLAN_SHA256,
        attempt=1,
    )
    started = time.monotonic_ns()
    try:
        response = selected_transport.post_multipart(
            request=request,
            url=cloudflare_endpoint(config.account_id),
            api_token=config.api_token.get_secret_value(),
            timeout_seconds=CLOUDFLARE_REQUEST_TIMEOUT_SECONDS,
            allow_redirects=False,
            accept_encoding="identity",
            maximum_response_bytes=CLOUDFLARE_MAX_RESPONSE_BYTES,
        )
    except CloudflareTransportError:
        _raise_request_error(failure_stage="transport", started=started)
    except CloudflareResponseContractError:
        _raise_request_error(failure_stage="response_contract", started=started)
    except CloudflareImageError:
        _raise_request_error(failure_stage="image_content", started=started)
    except Exception:
        _raise_request_error(failure_stage="unexpected", started=started)

    if (
        type(response) is CloudflareHttpResponse
        and type(response.status_code) is int
        and 100 <= response.status_code <= 599
        and response.status_code != 200
    ):
        _raise_request_error(
            failure_stage="http_status",
            started=started,
            http_status_code=response.status_code,
        )

    try:
        artifact = parse_cloudflare_image_response(
            request=request,
            response=response,
        )
    except CloudflareTransportError:
        _raise_request_error(failure_stage="transport", started=started)
    except CloudflareResponseContractError:
        _raise_request_error(failure_stage="response_contract", started=started)
    except CloudflareImageError:
        _raise_request_error(failure_stage="image_content", started=started)
    except Exception:
        _raise_request_error(failure_stage="unexpected", started=started)
    wall_milliseconds = _elapsed_milliseconds(started)

    try:
        _write_exclusive_png(output_path, artifact.body)
    except CloudflareLiveE2EError:
        _raise_output_error(
            request_count=CLOUDFLARE_E2E_REQUEST_COUNT,
            wall_milliseconds=wall_milliseconds,
        )
    return CloudflareLiveE2EResult(
        request_count=CLOUDFLARE_E2E_REQUEST_COUNT,
        retry_count=CLOUDFLARE_E2E_RETRY_COUNT,
        model_id=CLOUDFLARE_IMAGE_MODEL_ID,
        seed=request.seed,
        image_sha256=artifact.sha256,
        image_bytes=artifact.byte_length,
        width=artifact.width,
        height=artifact.height,
        wall_milliseconds=wall_milliseconds,
        output_path=output_path,
    )
