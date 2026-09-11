"""Bounded Cloudflare execution for provisional counterfactual references."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import hashlib
import hmac
from io import BytesIO
import json
from typing import Annotated
from typing import Literal
from typing import Protocol

from PIL import Image
from PIL import UnidentifiedImageError
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import ValidationError
from pydantic import model_validator
import requests

from src.search_v2.cloudflare_http import CLOUDFLARE_MAX_IMAGE_BYTES
from src.search_v2.cloudflare_http import CLOUDFLARE_MAX_RESPONSE_BYTES
from src.search_v2.cloudflare_http import CLOUDFLARE_REQUEST_HEADERS
from src.search_v2.cloudflare_http import CLOUDFLARE_REQUEST_TIMEOUT_SECONDS
from src.search_v2.cloudflare_http import CloudflareExecutionError
from src.search_v2.cloudflare_http import CloudflareHttpResponse
from src.search_v2.cloudflare_http import CloudflareResponseContractError
from src.search_v2.cloudflare_http import _close_response
from src.search_v2.cloudflare_http import _configure_session
from src.search_v2.cloudflare_http import _decoded_image
from src.search_v2.cloudflare_http import _encode_clean_png
from src.search_v2.cloudflare_http import _normalized_png
from src.search_v2.cloudflare_http import _project_response
from src.search_v2.cloudflare_http import _reject_duplicate_keys
from src.search_v2.cloudflare_http import _reject_non_finite_constant
from src.search_v2.cloudflare_http import _response_image_text
from src.search_v2.cloudflare_http import _validated_api_token
from src.search_v2.cloudflare_http import cloudflare_endpoint
from src.search_v2.cloudflare_request import CLOUDFLARE_OUTPUT_DIMENSION
from src.search_v2.cloudflare_request import MAX_REFERENCE_IMAGE_DIMENSION
from src.search_v2.cloudflare_request import _png_dimensions
from src.search_v2.counterfactual_cloudflare_request import (
    CounterfactualCloudflareRequest,
)
from src.search_v2.counterfactual_cloudflare_request import (
    CounterfactualCloudflareRequestError,
)
from src.search_v2.counterfactual_cloudflare_request import (
    CounterfactualCloudflareRequestSet,
)
from src.search_v2.counterfactual_cloudflare_request import (
    build_counterfactual_cloudflare_desired_request,
)
from src.search_v2.counterfactual_cloudflare_request import (
    build_counterfactual_cloudflare_request_set,
)
from src.search_v2.counterfactual_cloudflare_request import (
    counterfactual_cloudflare_request_set_sha256,
)
from src.search_v2.counterfactual_cloudflare_request import (
    counterfactual_cloudflare_request_sha256,
)
from src.search_v2.counterfactual_image import ConditionId
from src.search_v2.counterfactual_image import VisualConditionSet
from src.search_v2.counterfactual_image import visual_condition_set_sha256
from src.search_v2.intent import NormalizedSearchIntent
from src.search_v2.intent import search_intent_sha256
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import UsageReservation


_INVALID_EXECUTION_MESSAGE = "Counterfactual Cloudflare execution is invalid"
_TRANSPORT_FAILED_MESSAGE = "Counterfactual Cloudflare transport failed"
_INVALID_ARTIFACT_MESSAGE = "Counterfactual Cloudflare artifact is invalid"
_MAX_ERROR_JSON_BYTES = 8192
_ERROR_CHUNK_BYTES = 1024
_KNOWN_429_CODES = (3036, 3040)
COUNTERFACTUAL_REFERENCE_SET_DOMAIN = (
    b"amazon-explorer-cloudflare-counterfactual-reference-artifacts-v1\x00"
)

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
PositiveImageBytes = Annotated[int, Field(gt=0, le=CLOUDFLARE_MAX_IMAGE_BYTES)]


class CloudflareFailureDiagnostic(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, revalidate_instances="always"
    )

    stage: Literal[
        "transport",
        "http_status",
        "response_contract",
        "image_encoding",
        "image_content",
        "artifact_contract",
        "unexpected",
    ]
    http_status_code: Annotated[int, Field(ge=100, le=599)] | None = None
    provider_error_code: Literal[3036, 3040] | None = None

    @model_validator(mode="after")
    def validate_status(self) -> CloudflareFailureDiagnostic:
        if (self.stage == "http_status") != (self.http_status_code is not None):
            raise ValueError("HTTP status is required only for an HTTP failure")
        if self.http_status_code == 200:
            raise ValueError("HTTP success is not a failure")
        if self.provider_error_code is not None and self.http_status_code != 429:
            raise ValueError("Provider code is supported only for HTTP 429")
        return self


class CounterfactualCloudflareExecutionError(RuntimeError):
    """A fixed-message failure at the provisional Cloudflare execution boundary."""

    def __init__(self, message: str, *, diagnostic: CloudflareFailureDiagnostic | None = None):
        super().__init__(message)
        self.diagnostic = (
            CloudflareFailureDiagnostic(stage="unexpected")
            if diagnostic is None
            else CloudflareFailureDiagnostic.model_validate(diagnostic)
        )


class CounterfactualCloudflareTransportError(CounterfactualCloudflareExecutionError):
    """A request failed without an automatic retry."""


class _StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


class CounterfactualCloudflareTransport(Protocol):
    def post_multipart(
        self,
        *,
        request: CounterfactualCloudflareRequest,
        url: str,
        api_token: str,
        timeout_seconds: int,
        allow_redirects: Literal[False],
        accept_encoding: Literal["identity"],
        maximum_response_bytes: int,
    ) -> CloudflareHttpResponse: ...


class CounterfactualCloudflareImageArtifact(_StrictFrozenContract):
    schema_version: Literal["1.0"]
    target: Literal["desired", "counterfactual"]
    condition_id: ConditionId | None
    attempt: Literal[1]
    request_sha256: Digest
    content_type: Literal["image/png"]
    sha256: Digest
    byte_length: PositiveImageBytes
    width: Literal[512]
    height: Literal[512]
    body: bytes = Field(exclude=True, repr=False)

    @model_validator(mode="after")
    def validate_artifact(self) -> CounterfactualCloudflareImageArtifact:
        if (self.target == "desired") != (self.condition_id is None):
            raise ValueError("counterfactual artifact target is inconsistent")
        if type(self.body) is not bytes or len(self.body) != self.byte_length:
            raise ValueError("counterfactual artifact length does not match")
        if not hmac.compare_digest(hashlib.sha256(self.body).hexdigest(), self.sha256):
            raise ValueError("counterfactual artifact digest does not match")
        if _png_dimensions(self.body) != (self.width, self.height):
            raise ValueError("counterfactual artifact dimensions do not match")
        if _normalized_png(self.body) != self.body:
            raise ValueError("counterfactual artifact is not canonical")
        return self


class _CounterfactualExecution(_StrictFrozenContract):
    schema_version: Literal["1.0"]
    request_set: CounterfactualCloudflareRequestSet = Field(repr=False)
    images: Annotated[
        tuple[CounterfactualCloudflareImageArtifact, ...],
        Field(min_length=2, max_length=4, repr=False),
    ]
    reference_set_sha256: Digest
    request_metadata_sha256: Digest
    usage_reservation: UsageReservation = Field(repr=False)

    @model_validator(mode="after")
    def validate_execution(self) -> _CounterfactualExecution:
        if len(self.images) != self.request_set.call_count:
            raise ValueError("counterfactual execution count does not match")
        if tuple(item.target for item in self.images) != tuple(
            item.target for item in self.request_set.requests
        ):
            raise ValueError("counterfactual execution targets do not match")
        if tuple(item.condition_id for item in self.images) != tuple(
            item.condition_id for item in self.request_set.requests
        ):
            raise ValueError("counterfactual execution conditions do not match")
        if tuple(item.request_sha256 for item in self.images) != tuple(
            counterfactual_cloudflare_request_sha256(item) for item in self.request_set.requests
        ):
            raise ValueError("counterfactual execution requests do not match")
        if not hmac.compare_digest(
            self.reference_set_sha256,
            counterfactual_cloudflare_reference_set_sha256(self.images),
        ):
            raise ValueError("counterfactual reference set digest does not match")
        if not hmac.compare_digest(
            self.request_metadata_sha256,
            counterfactual_cloudflare_request_set_sha256(self.request_set),
        ):
            raise ValueError("counterfactual request metadata digest does not match")
        return self


class CounterfactualCloudflareReferenceExecution(_CounterfactualExecution):
    @model_validator(mode="after")
    def validate_usage(self) -> CounterfactualCloudflareReferenceExecution:
        reservation = self.usage_reservation
        if (
            reservation.status != "succeeded"
            or reservation.provider != "cloudflare"
            or reservation.operation != "counterfactual_reference_set"
            or reservation.amount.calls != self.request_set.call_count
            or reservation.amount.tokens != 0
        ):
            raise ValueError("counterfactual usage result does not match")
        return self


class CounterfactualCloudflareDerivedExecution(_CounterfactualExecution):
    @model_validator(mode="after")
    def validate_usage(self) -> CounterfactualCloudflareDerivedExecution:
        reservation = self.usage_reservation
        if (
            reservation.status != "succeeded"
            or reservation.provider != "cloudflare"
            or reservation.operation != "counterfactual_images"
            or reservation.amount.calls != self.request_set.call_count - 1
            or reservation.amount.tokens != 0
            or reservation.binding_sha256 != self.request_set.preimage_plan_sha256
        ):
            raise ValueError("counterfactual derived usage result does not match")
        return self


def _multipart_files(
    request: CounterfactualCloudflareRequest,
) -> list[tuple[str, tuple[object, ...]]]:
    form = request.multipart_form()
    fields: list[tuple[str, tuple[object, ...]]] = [
        (field.name, (None, field.value)) for field in form.text_fields
    ]
    fields.extend(
        (
            field.name,
            (field.filename, field.image.body, field.image.content_type),
        )
        for field in form.file_fields
    )
    return fields


def _provider_error_code(response: requests.Response) -> int | None:
    # Error text can contain private data; retain only documented numeric codes.
    if response.status_code != 429:
        return None
    try:
        if (
            response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            != "application/json"
        ):
            return None
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            return None
        length = response.headers.get("Content-Length")
        if length is not None and not 0 <= int(length) <= _MAX_ERROR_JSON_BYTES:
            return None
        body = bytearray()
        for chunk in response.iter_content(chunk_size=_ERROR_CHUNK_BYTES):
            if len(body) + len(chunk) > _MAX_ERROR_JSON_BYTES:
                return None
            body.extend(chunk)
        payload = json.loads(
            body,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite_constant,
        )
        errors = payload.get("errors")
        if type(errors) is not list or len(errors) != 1 or type(errors[0]) is not dict:
            return None
        code = errors[0].get("code")
        return code if type(code) is int and code in _KNOWN_429_CODES else None
    except Exception:
        # Keep the observed HTTP failure when its optional body cannot be read.
        return None


class RequestsCounterfactualCloudflareTransport:
    """Send one isolated request using the shared strict Cloudflare response projection."""

    def post_multipart(
        self,
        *,
        request: CounterfactualCloudflareRequest,
        url: str,
        api_token: str,
        timeout_seconds: int,
        allow_redirects: Literal[False],
        accept_encoding: Literal["identity"],
        maximum_response_bytes: int,
    ) -> CloudflareHttpResponse:
        try:
            validated_request = CounterfactualCloudflareRequest.model_validate(request)
            prefix = "https://api.cloudflare.com/client/v4/accounts/"
            suffix = f"/ai/run/{validated_request.model_id}"
            if not url.startswith(prefix) or not url.endswith(suffix):
                raise ValueError("transport endpoint does not match")
            account_id = url[len(prefix) : -len(suffix)]
            expected_url = cloudflare_endpoint(account_id)
            validated_token = _validated_api_token(api_token)
            if (
                url != expected_url
                or timeout_seconds != CLOUDFLARE_REQUEST_TIMEOUT_SECONDS
                or allow_redirects is not False
                or accept_encoding != "identity"
                or maximum_response_bytes != CLOUDFLARE_MAX_RESPONSE_BYTES
            ):
                raise ValueError("transport arguments do not match")
        except (CloudflareExecutionError, TypeError, ValueError, ValidationError) as exc:
            raise CounterfactualCloudflareExecutionError(_INVALID_EXECUTION_MESSAGE) from exc

        headers = dict(CLOUDFLARE_REQUEST_HEADERS)
        headers["Authorization"] = f"Bearer {validated_token}"
        try:
            session = requests.Session()
            response: requests.Response | None = None
            try:
                _configure_session(session)
                response = session.request(
                    method="POST",
                    url=url,
                    headers=headers,
                    files=_multipart_files(validated_request),
                    timeout=(timeout_seconds, timeout_seconds),
                    allow_redirects=False,
                    stream=True,
                    verify=True,
                    proxies={},
                )
                if not isinstance(response, requests.Response):
                    raise TypeError("transport response is invalid")
                if (
                    type(response.status_code) is int
                    and 100 <= response.status_code <= 599
                    and response.status_code != 200
                ):
                    raise CounterfactualCloudflareExecutionError(
                        _TRANSPORT_FAILED_MESSAGE,
                        diagnostic=CloudflareFailureDiagnostic(
                            stage="http_status",
                            http_status_code=response.status_code,
                            provider_error_code=_provider_error_code(response),
                        ),
                    )
                return _project_response(
                    response,
                    maximum_response_bytes=maximum_response_bytes,
                )
            finally:
                if response is not None:
                    try:
                        _close_response(response)
                    finally:
                        session.close()
                else:
                    session.close()
        except CounterfactualCloudflareExecutionError:
            raise
        except CloudflareResponseContractError:
            raise CounterfactualCloudflareExecutionError(
                _TRANSPORT_FAILED_MESSAGE,
                diagnostic=CloudflareFailureDiagnostic(stage="response_contract"),
            ) from None
        except Exception as exc:
            raise CounterfactualCloudflareTransportError(
                _TRANSPORT_FAILED_MESSAGE,
                diagnostic=CloudflareFailureDiagnostic(stage="transport"),
            ) from exc


def _artifact(
    request: CounterfactualCloudflareRequest,
    response: CloudflareHttpResponse,
) -> CounterfactualCloudflareImageArtifact:
    stage = "artifact_contract"
    try:
        validated_request = CounterfactualCloudflareRequest.model_validate(request)
        if (
            type(response) is CloudflareHttpResponse
            and type(response.status_code) is int
            and 100 <= response.status_code <= 599
            and response.status_code != 200
        ):
            raise CounterfactualCloudflareExecutionError(
                _INVALID_ARTIFACT_MESSAGE,
                diagnostic=CloudflareFailureDiagnostic(
                    stage="http_status",
                    http_status_code=response.status_code,
                ),
            )
        stage = "response_contract"
        encoded = _response_image_text(response)
        stage = "image_encoding"
        decoded = _decoded_image(encoded)
        stage = "image_content"
        normalized = _normalized_png(decoded)
        stage = "artifact_contract"
        return CounterfactualCloudflareImageArtifact(
            schema_version="1.0",
            target=validated_request.target,
            condition_id=validated_request.condition_id,
            attempt=1,
            request_sha256=counterfactual_cloudflare_request_sha256(validated_request),
            content_type="image/png",
            sha256=hashlib.sha256(normalized).hexdigest(),
            byte_length=len(normalized),
            width=CLOUDFLARE_OUTPUT_DIMENSION,
            height=CLOUDFLARE_OUTPUT_DIMENSION,
            body=normalized,
        )
    except CounterfactualCloudflareExecutionError:
        raise
    except Exception as exc:
        raise CounterfactualCloudflareExecutionError(
            _INVALID_ARTIFACT_MESSAGE,
            diagnostic=CloudflareFailureDiagnostic(stage=stage),
        ) from exc


def _desired_reference_png(desired: CounterfactualCloudflareImageArtifact) -> bytes:
    try:
        with Image.open(BytesIO(desired.body), formats=("PNG",)) as source:
            source.load()
            resized = source.convert("RGB").resize(
                (MAX_REFERENCE_IMAGE_DIMENSION, MAX_REFERENCE_IMAGE_DIMENSION),
                resample=Image.Resampling.LANCZOS,
            )
            try:
                result = _encode_clean_png(resized)
            finally:
                resized.close()
        if _png_dimensions(result) != (
            MAX_REFERENCE_IMAGE_DIMENSION,
            MAX_REFERENCE_IMAGE_DIMENSION,
        ):
            raise ValueError("desired reference dimensions do not match")
        return result
    except (
        CloudflareExecutionError,
        OSError,
        TypeError,
        UnidentifiedImageError,
        ValueError,
    ) as exc:
        raise CounterfactualCloudflareExecutionError(_INVALID_ARTIFACT_MESSAGE) from exc


def counterfactual_cloudflare_reference_set_sha256(images: object) -> str:
    try:
        if type(images) is not tuple or not 2 <= len(images) <= 4:
            raise TypeError("counterfactual image count is invalid")
        validated = tuple(
            CounterfactualCloudflareImageArtifact.model_validate(item) for item in images
        )
        expected_ids = (None,) + tuple(
            f"visual-condition-{index:03d}" for index in range(1, len(validated))
        )
        if tuple(item.condition_id for item in validated) != expected_ids:
            raise ValueError("counterfactual image order is invalid")
        payload = json.dumps(
            [item.model_dump(mode="json") for item in validated],
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(COUNTERFACTUAL_REFERENCE_SET_DOMAIN + payload).hexdigest()
    except (CloudflareExecutionError, TypeError, ValueError, ValidationError) as exc:
        raise CounterfactualCloudflareExecutionError(_INVALID_ARTIFACT_MESSAGE) from exc


def _utc_now(now: Callable[[], datetime]) -> datetime:
    try:
        value = now()
        if type(value) is not datetime or value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise TypeError("completion time must use UTC")
        return value.astimezone(timezone.utc)
    except CounterfactualCloudflareExecutionError:
        raise
    except Exception as exc:
        raise CounterfactualCloudflareTransportError(_TRANSPORT_FAILED_MESSAGE) from exc


def _finish(
    ledger: InMemoryUsageLedger,
    reservation: UsageReservation,
    *,
    success: bool,
    now: Callable[[], datetime],
) -> UsageReservation:
    try:
        return ledger.finish(
            reservation.reservation_id,
            owner_id=reservation.owner_id,
            session_id=reservation.session_id,
            success=success,
            now=_utc_now(now),
        )
    except CounterfactualCloudflareExecutionError:
        raise
    except Exception as exc:
        raise CounterfactualCloudflareTransportError(_TRANSPORT_FAILED_MESSAGE) from exc


def _validate_context(
    *,
    intent: object,
    condition_set: object,
    preimage_plan_sha256: object,
    usage_ledger: object,
    usage_reservation: object,
    operation: Literal["counterfactual_reference_set", "counterfactual_images"] = (
        "counterfactual_reference_set"
    ),
) -> tuple[NormalizedSearchIntent, VisualConditionSet, InMemoryUsageLedger, UsageReservation]:
    try:
        validated_intent = NormalizedSearchIntent.model_validate(intent)
        conditions = VisualConditionSet.model_validate(condition_set)
        reservation = UsageReservation.model_validate(usage_reservation)
        if not isinstance(usage_ledger, InMemoryUsageLedger):
            raise TypeError("usage ledger is invalid")
        call_count = len(conditions.conditions)
        if operation == "counterfactual_reference_set":
            call_count += 1
        if (
            type(preimage_plan_sha256) is not str
            or reservation.status != "started"
            or reservation.provider != "cloudflare"
            or reservation.operation != operation
            or reservation.amount.calls != call_count
            or reservation.amount.tokens != 0
            or not hmac.compare_digest(reservation.binding_sha256, preimage_plan_sha256)
            or validated_intent.has_blocking_ambiguity
            or visual_condition_set_sha256(conditions) == ""
            or search_intent_sha256(validated_intent) == ""
        ):
            raise ValueError("counterfactual execution binding is invalid")
        current = next(
            (
                item
                for item in usage_ledger.snapshot().reservations
                if item.reservation_id == reservation.reservation_id
            ),
            None,
        )
        if current != reservation:
            raise ValueError("counterfactual reservation is not current")
        return validated_intent, conditions, usage_ledger, reservation
    except Exception as exc:
        raise CounterfactualCloudflareExecutionError(_INVALID_EXECUTION_MESSAGE) from exc


def _post(
    transport: CounterfactualCloudflareTransport,
    *,
    request: CounterfactualCloudflareRequest,
    endpoint: str,
    api_token: str,
) -> CloudflareHttpResponse:
    try:
        return transport.post_multipart(
            request=request,
            url=endpoint,
            api_token=api_token,
            timeout_seconds=CLOUDFLARE_REQUEST_TIMEOUT_SECONDS,
            allow_redirects=False,
            accept_encoding="identity",
            maximum_response_bytes=CLOUDFLARE_MAX_RESPONSE_BYTES,
        )
    except CounterfactualCloudflareExecutionError:
        raise
    except Exception as exc:
        raise CounterfactualCloudflareTransportError(
            _TRANSPORT_FAILED_MESSAGE,
            diagnostic=CloudflareFailureDiagnostic(stage="transport"),
        ) from exc


def execute_counterfactual_desired_image(
    *,
    request: CounterfactualCloudflareRequest,
    account_id: str,
    api_token: str,
    transport: CounterfactualCloudflareTransport,
) -> CounterfactualCloudflareImageArtifact:
    """Generate only the initial reference; its usage lifecycle belongs to the caller."""
    try:
        validated = CounterfactualCloudflareRequest.model_validate(request)
        if validated.target != "desired":
            raise ValueError("initial reference must use the desired request")
        endpoint = cloudflare_endpoint(account_id)
        token = _validated_api_token(api_token)
        if not callable(getattr(transport, "post_multipart", None)):
            raise TypeError("counterfactual transport is invalid")
    except Exception as exc:
        raise CounterfactualCloudflareExecutionError(_INVALID_EXECUTION_MESSAGE) from exc
    return _artifact(
        validated,
        _post(transport, request=validated, endpoint=endpoint, api_token=token),
    )


def execute_counterfactual_derived_images(
    *,
    desired_request: CounterfactualCloudflareRequest,
    desired: CounterfactualCloudflareImageArtifact,
    intent: NormalizedSearchIntent,
    condition_set: VisualConditionSet,
    preimage_plan_sha256: str,
    usage_ledger: InMemoryUsageLedger,
    usage_reservation: UsageReservation,
    account_id: str,
    api_token: str,
    transport: CounterfactualCloudflareTransport,
    now: Callable[[], datetime],
) -> CounterfactualCloudflareDerivedExecution:
    """Reuse the approved reference and generate only one image per visual condition."""
    validated_intent, conditions, ledger, reservation = _validate_context(
        intent=intent,
        condition_set=condition_set,
        preimage_plan_sha256=preimage_plan_sha256,
        usage_ledger=usage_ledger,
        usage_reservation=usage_reservation,
        operation="counterfactual_images",
    )
    if not callable(now) or not callable(getattr(transport, "post_multipart", None)):
        raise CounterfactualCloudflareExecutionError(_INVALID_EXECUTION_MESSAGE)
    try:
        validated_request = CounterfactualCloudflareRequest.model_validate(desired_request)
        validated_desired = CounterfactualCloudflareImageArtifact.model_validate(desired)
        expected_request = build_counterfactual_cloudflare_desired_request(
            intent=validated_intent,
            condition_set=conditions,
            preimage_plan_sha256=preimage_plan_sha256,
        )
        if (
            validated_request != expected_request
            or validated_desired.target != "desired"
            or validated_desired.request_sha256
            != counterfactual_cloudflare_request_sha256(validated_request)
        ):
            raise CounterfactualCloudflareExecutionError(_INVALID_EXECUTION_MESSAGE)
        endpoint = cloudflare_endpoint(account_id)
        token = _validated_api_token(api_token)
        request_set = build_counterfactual_cloudflare_request_set(
            intent=validated_intent,
            condition_set=conditions,
            preimage_plan_sha256=preimage_plan_sha256,
            desired_reference_png=_desired_reference_png(validated_desired),
        )
        if request_set.requests[0] != validated_request:
            raise CounterfactualCloudflareExecutionError(_INVALID_EXECUTION_MESSAGE)
        images = [validated_desired]
        for request in request_set.requests[1:]:
            images.append(
                _artifact(
                    request,
                    _post(transport, request=request, endpoint=endpoint, api_token=token),
                )
            )
        image_tuple = tuple(images)
        reference_digest = counterfactual_cloudflare_reference_set_sha256(image_tuple)
        request_digest = counterfactual_cloudflare_request_set_sha256(request_set)
    except Exception as exc:
        _finish(ledger, reservation, success=False, now=now)
        if isinstance(exc, CounterfactualCloudflareExecutionError):
            raise
        raise CounterfactualCloudflareExecutionError(_INVALID_EXECUTION_MESSAGE) from exc

    finished_at = _utc_now(now)
    try:
        projected_payload = reservation.model_dump(mode="python")
        projected_payload.update(status="succeeded", finished_at=finished_at)
        projected = UsageReservation.model_validate(projected_payload)
        execution = CounterfactualCloudflareDerivedExecution(
            schema_version="1.0",
            request_set=request_set,
            images=image_tuple,
            reference_set_sha256=reference_digest,
            request_metadata_sha256=request_digest,
            usage_reservation=projected,
        )
    except (CounterfactualCloudflareExecutionError, TypeError, ValueError, ValidationError) as exc:
        _finish(ledger, reservation, success=False, now=lambda: finished_at)
        raise CounterfactualCloudflareExecutionError(_INVALID_ARTIFACT_MESSAGE) from exc
    finished = _finish(ledger, reservation, success=True, now=lambda: finished_at)
    if finished != projected:
        raise CounterfactualCloudflareTransportError(_TRANSPORT_FAILED_MESSAGE)
    return execution


def execute_counterfactual_cloudflare_reference_set(
    *,
    intent: NormalizedSearchIntent,
    condition_set: VisualConditionSet,
    preimage_plan_sha256: str,
    usage_ledger: InMemoryUsageLedger,
    usage_reservation: UsageReservation,
    account_id: str,
    api_token: str,
    transport: CounterfactualCloudflareTransport,
    now: Callable[[], datetime],
) -> CounterfactualCloudflareReferenceExecution:
    """Execute exactly one desired request and one request per condition, without retries."""
    validated_intent, conditions, ledger, reservation = _validate_context(
        intent=intent,
        condition_set=condition_set,
        preimage_plan_sha256=preimage_plan_sha256,
        usage_ledger=usage_ledger,
        usage_reservation=usage_reservation,
    )
    if not callable(now) or not callable(getattr(transport, "post_multipart", None)):
        raise CounterfactualCloudflareExecutionError(_INVALID_EXECUTION_MESSAGE)

    try:
        endpoint = cloudflare_endpoint(account_id)
        token = _validated_api_token(api_token)
        desired_request = build_counterfactual_cloudflare_desired_request(
            intent=validated_intent,
            condition_set=conditions,
            preimage_plan_sha256=preimage_plan_sha256,
        )
        desired = _artifact(
            desired_request,
            _post(
                transport,
                request=desired_request,
                endpoint=endpoint,
                api_token=token,
            ),
        )
        request_set = build_counterfactual_cloudflare_request_set(
            intent=validated_intent,
            condition_set=conditions,
            preimage_plan_sha256=preimage_plan_sha256,
            desired_reference_png=_desired_reference_png(desired),
        )
        if request_set.requests[0] != desired_request:
            raise ValueError("desired request changed after provider execution")
        images = [desired]
        for request in request_set.requests[1:]:
            images.append(
                _artifact(
                    request,
                    _post(
                        transport,
                        request=request,
                        endpoint=endpoint,
                        api_token=token,
                    ),
                )
            )
        image_tuple = tuple(images)
        reference_set_sha256 = counterfactual_cloudflare_reference_set_sha256(image_tuple)
        request_metadata_sha256 = counterfactual_cloudflare_request_set_sha256(request_set)
    except Exception as exc:
        _finish(ledger, reservation, success=False, now=now)
        if isinstance(exc, CounterfactualCloudflareExecutionError):
            raise
        if isinstance(exc, CounterfactualCloudflareRequestError):
            raise CounterfactualCloudflareExecutionError(_INVALID_EXECUTION_MESSAGE) from exc
        raise CounterfactualCloudflareTransportError(_TRANSPORT_FAILED_MESSAGE) from exc

    finished_at = _utc_now(now)
    try:
        projected_payload = reservation.model_dump(mode="python")
        projected_payload.update(status="succeeded", finished_at=finished_at)
        projected = UsageReservation.model_validate(projected_payload)
        execution = CounterfactualCloudflareReferenceExecution(
            schema_version="1.0",
            request_set=request_set,
            images=image_tuple,
            reference_set_sha256=reference_set_sha256,
            request_metadata_sha256=request_metadata_sha256,
            usage_reservation=projected,
        )
    except (CounterfactualCloudflareExecutionError, TypeError, ValueError, ValidationError) as exc:
        try:
            ledger.finish(
                reservation.reservation_id,
                owner_id=reservation.owner_id,
                session_id=reservation.session_id,
                success=False,
                now=finished_at,
            )
        except Exception:
            raise CounterfactualCloudflareTransportError(_TRANSPORT_FAILED_MESSAGE) from exc
        raise CounterfactualCloudflareExecutionError(_INVALID_ARTIFACT_MESSAGE) from exc
    try:
        finished = ledger.finish(
            reservation.reservation_id,
            owner_id=reservation.owner_id,
            session_id=reservation.session_id,
            success=True,
            now=finished_at,
        )
    except Exception as exc:
        raise CounterfactualCloudflareTransportError(_TRANSPORT_FAILED_MESSAGE) from exc
    if finished != projected:
        raise CounterfactualCloudflareTransportError(_TRANSPORT_FAILED_MESSAGE)
    return execution


__all__ = [
    "CLOUDFLARE_MAX_RESPONSE_BYTES",
    "CloudflareHttpResponse",
    "CounterfactualCloudflareExecutionError",
    "CounterfactualCloudflareDerivedExecution",
    "CounterfactualCloudflareImageArtifact",
    "CounterfactualCloudflareReferenceExecution",
    "RequestsCounterfactualCloudflareTransport",
    "counterfactual_cloudflare_reference_set_sha256",
    "execute_counterfactual_cloudflare_reference_set",
    "execute_counterfactual_derived_images",
    "execute_counterfactual_desired_image",
]
