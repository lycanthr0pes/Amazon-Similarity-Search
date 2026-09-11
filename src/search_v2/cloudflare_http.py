from __future__ import annotations

import base64
import binascii
from collections.abc import Callable
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import hashlib
import hmac
from io import BytesIO
import json
import re
from typing import Annotated
from typing import Any
from typing import Literal
from typing import NoReturn
from typing import Protocol
import warnings

from PIL import Image
from PIL import UnidentifiedImageError
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import ValidationError
from pydantic import model_validator
import requests
from requests.adapters import HTTPAdapter

from src.search_v2.cloudflare_request import CLOUDFLARE_IMAGE_MODEL_ID
from src.search_v2.cloudflare_request import CLOUDFLARE_OUTPUT_DIMENSION
from src.search_v2.cloudflare_request import IMAGE_ANGLES
from src.search_v2.cloudflare_request import MAX_REFERENCE_IMAGE_DIMENSION
from src.search_v2.cloudflare_request import CloudflareImageRequest
from src.search_v2.cloudflare_request import CloudflareRequestError
from src.search_v2.cloudflare_request import CloudflareRequestSet
from src.search_v2.cloudflare_request import ImageAngle
from src.search_v2.cloudflare_request import _png_dimensions
from src.search_v2.cloudflare_request import build_cloudflare_front_request
from src.search_v2.cloudflare_request import build_cloudflare_request_set
from src.search_v2.cloudflare_request import cloudflare_image_request_sha256
from src.search_v2.cloudflare_request import cloudflare_request_set_sha256
from src.search_v2.intent import NormalizedSearchIntent
from src.search_v2.intent import search_intent_sha256
from src.search_v2.state_machine import SearchSessionSnapshot
from src.search_v2.state_machine import SearchStateError
from src.search_v2.state_machine import record_image_set
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import UsageReservation


CLOUDFLARE_REQUEST_TIMEOUT_SECONDS = 120
CLOUDFLARE_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
CLOUDFLARE_MAX_IMAGE_BYTES = 2 * 1024 * 1024
CLOUDFLARE_REQUEST_HEADERS: tuple[tuple[str, str], ...] = (
    ("Accept", "application/json"),
    ("Accept-Encoding", "identity"),
)

_CLOUDFLARE_ORIGIN = "https://api.cloudflare.com"
_CLOUDFLARE_RUN_PREFIX = f"{_CLOUDFLARE_ORIGIN}/client/v4/accounts/"
_CLOUDFLARE_RUN_SUFFIX = f"/ai/run/{CLOUDFLARE_IMAGE_MODEL_ID}"
_ACCOUNT_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_ENDPOINT_PATTERN = re.compile(
    r"^https://api\.cloudflare\.com/client/v4/accounts/"
    r"[0-9a-f]{32}/ai/run/@cf/black-forest-labs/flux-2-klein-4b$"
)
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_STREAM_CHUNK_BYTES = 65_536
_MAX_TOKEN_CHARACTERS = 4_096
_MAX_HEADER_VALUE_CODEPOINTS = 200
_MAX_CONTENT_LENGTH_DIGITS = 20
_MAX_BASE64_CHARACTERS = ((CLOUDFLARE_MAX_IMAGE_BYTES + 2) // 3) * 4
_PROVIDER_IMAGE_FORMATS = ("PNG", "JPEG", "WEBP")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"
_WEBP_RIFF_SIGNATURE = b"RIFF"
_WEBP_FORMAT_SIGNATURE = b"WEBP"

_INVALID_EXECUTION_MESSAGE = "Cloudflare image execution request is invalid"
_TRANSPORT_FAILED_MESSAGE = "Cloudflare HTTP transport failed"
_INVALID_RESPONSE_MESSAGE = "Cloudflare response did not match the image contract"
_INVALID_IMAGE_MESSAGE = "Cloudflare image content is invalid"
_INVALID_ARTIFACT_MESSAGE = "Cloudflare image artifact is invalid"

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
PositiveImageBytes = Annotated[int, Field(gt=0, le=CLOUDFLARE_MAX_IMAGE_BYTES)]


class CloudflareExecutionError(RuntimeError):
    """Base class for fixed-message image execution failures."""


class CloudflareTransportError(CloudflareExecutionError):
    """The bounded HTTP attempt could not complete."""


class CloudflareResponseContractError(CloudflareExecutionError):
    """The provider response did not satisfy the accepted envelope."""


class CloudflareImageError(CloudflareExecutionError):
    """The decoded or normalized image was not acceptable."""


def _raise_invalid_execution() -> None:
    raise CloudflareExecutionError(_INVALID_EXECUTION_MESSAGE) from None


def _raise_transport_failed() -> None:
    raise CloudflareTransportError(_TRANSPORT_FAILED_MESSAGE) from None


def _raise_invalid_response() -> None:
    raise CloudflareResponseContractError(_INVALID_RESPONSE_MESSAGE) from None


def _raise_invalid_image() -> NoReturn:
    raise CloudflareImageError(_INVALID_IMAGE_MESSAGE) from None


def _raise_invalid_artifact() -> None:
    raise CloudflareImageError(_INVALID_ARTIFACT_MESSAGE) from None


class StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        revalidate_instances="always",
        frozen=True,
    )


@dataclass(frozen=True, slots=True, repr=False)
class CloudflareHttpResponse:
    status_code: int
    content_type: str | None
    content_length: int | None
    content_encoding: str | None
    body_chunks: Iterable[bytes]


class CloudflareRequestTransport(Protocol):
    def post_multipart(
        self,
        *,
        request: CloudflareImageRequest,
        url: str,
        api_token: str,
        timeout_seconds: int,
        allow_redirects: Literal[False],
        accept_encoding: Literal["identity"],
        maximum_response_bytes: int,
    ) -> CloudflareHttpResponse: ...


class CloudflareImageArtifact(StrictFrozenContract):
    schema_version: Literal["2.0"]
    angle: ImageAngle
    attempt: Annotated[int, Field(ge=1, le=2)]
    request_sha256: Digest
    content_type: Literal["image/png"]
    sha256: Digest
    byte_length: PositiveImageBytes
    width: Literal[512]
    height: Literal[512]
    body: bytes = Field(exclude=True, repr=False)

    @model_validator(mode="after")
    def validate_body_metadata(self) -> CloudflareImageArtifact:
        if type(self.body) is not bytes or len(self.body) != self.byte_length:
            raise ValueError("image artifact byte length does not match")
        if not hmac.compare_digest(hashlib.sha256(self.body).hexdigest(), self.sha256):
            raise ValueError("image artifact digest does not match")
        try:
            dimensions = _png_dimensions(self.body)
        except (TypeError, ValueError):
            raise ValueError("image artifact PNG is invalid") from None
        if dimensions != (self.width, self.height):
            raise ValueError("image artifact dimensions do not match")
        try:
            canonical = _normalized_png(self.body)
        except CloudflareExecutionError:
            raise ValueError("image artifact is not canonical") from None
        if canonical != self.body:
            raise ValueError("image artifact is not canonical")
        return self


class CloudflareImageSetExecution(StrictFrozenContract):
    schema_version: Literal["2.0"]
    request_set: CloudflareRequestSet = Field(repr=False)
    images: Annotated[
        tuple[CloudflareImageArtifact, ...],
        Field(min_length=4, max_length=4, repr=False),
    ]
    image_set_sha256: Digest
    request_metadata_sha256: Digest
    usage_reservation: UsageReservation = Field(repr=False)
    session: SearchSessionSnapshot = Field(repr=False)

    @model_validator(mode="after")
    def validate_execution_bindings(self) -> CloudflareImageSetExecution:
        if tuple(image.angle for image in self.images) != IMAGE_ANGLES:
            raise ValueError("image artifact order does not match")
        if any(image.attempt != self.request_set.attempt for image in self.images):
            raise ValueError("image artifact attempt does not match")
        expected_request_digests = tuple(
            cloudflare_image_request_sha256(request) for request in self.request_set.requests
        )
        if tuple(image.request_sha256 for image in self.images) != expected_request_digests:
            raise ValueError("image artifact request does not match")
        if not hmac.compare_digest(
            self.request_metadata_sha256,
            cloudflare_request_set_sha256(self.request_set),
        ):
            raise ValueError("request metadata digest does not match")
        if not hmac.compare_digest(
            self.image_set_sha256,
            _image_set_digest(self.images),
        ):
            raise ValueError("image set digest does not match")
        if (
            self.usage_reservation.status != "succeeded"
            or self.usage_reservation.provider != "cloudflare"
            or self.usage_reservation.operation != "image_set"
            or self.usage_reservation.amount.calls != 4
            or self.usage_reservation.amount.tokens != 0
            or self.session.state != "image_review"
            or self.session.owner_id != self.usage_reservation.owner_id
            or self.session.session_id != self.usage_reservation.session_id
            or not hmac.compare_digest(
                self.session.query_plan_sha256 or "",
                self.usage_reservation.binding_sha256,
            )
            or not hmac.compare_digest(
                self.session.usage_policy_sha256 or "",
                self.usage_reservation.usage_policy_sha256,
            )
            or not hmac.compare_digest(
                self.session.image_set_sha256 or "",
                self.image_set_sha256,
            )
            or not hmac.compare_digest(
                self.session.image_request_metadata_sha256 or "",
                self.request_metadata_sha256,
            )
        ):
            raise ValueError("completed image execution does not match session")
        return self


def cloudflare_endpoint(account_id: object) -> str:
    if type(account_id) is not str or _ACCOUNT_ID_PATTERN.fullmatch(account_id) is None:
        _raise_invalid_execution()
    return f"{_CLOUDFLARE_RUN_PREFIX}{account_id}{_CLOUDFLARE_RUN_SUFFIX}"


def _validated_endpoint(value: object) -> str:
    if type(value) is not str or _ENDPOINT_PATTERN.fullmatch(value) is None:
        _raise_invalid_execution()
    return value


def _validated_api_token(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > _MAX_TOKEN_CHARACTERS
        or not value.isascii()
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        _raise_invalid_execution()
    return value


def _validated_request(value: object) -> CloudflareImageRequest:
    try:
        if type(value) is not CloudflareImageRequest:
            raise TypeError("request type is invalid")
        return CloudflareImageRequest.model_validate(value)
    except (CloudflareRequestError, TypeError, ValidationError, ValueError):
        _raise_invalid_execution()


def _validated_transport_contract(
    *,
    request: object,
    url: object,
    api_token: object,
    timeout_seconds: object,
    allow_redirects: object,
    accept_encoding: object,
    maximum_response_bytes: object,
) -> tuple[CloudflareImageRequest, str, str]:
    validated_request = _validated_request(request)
    validated_url = _validated_endpoint(url)
    validated_token = _validated_api_token(api_token)
    if (
        type(timeout_seconds) is not int
        or timeout_seconds != CLOUDFLARE_REQUEST_TIMEOUT_SECONDS
        or allow_redirects is not False
        or accept_encoding != "identity"
        or type(maximum_response_bytes) is not int
        or maximum_response_bytes != CLOUDFLARE_MAX_RESPONSE_BYTES
    ):
        _raise_invalid_execution()
    return validated_request, validated_url, validated_token


def _response_header(response: requests.Response, name: str) -> str | None:
    value = response.headers.get(name)
    if value is None:
        return None
    if (
        type(value) is not str
        or not value
        or len(value) > _MAX_HEADER_VALUE_CODEPOINTS
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    ):
        _raise_invalid_response()
    return value


def _content_length(response: requests.Response) -> int | None:
    value = _response_header(response, "Content-Length")
    if value is None:
        return None
    if len(value) > _MAX_CONTENT_LENGTH_DIGITS or not value.isascii() or not value.isdecimal():
        _raise_invalid_response()
    return int(value)


def _is_json_content_type(value: str | None) -> bool:
    if value is None or len(value) > _MAX_HEADER_VALUE_CODEPOINTS:
        return False
    parts = [part.strip().casefold() for part in value.split(";")]
    if parts[0] != "application/json" or any(not part for part in parts):
        return False
    parameters: dict[str, str] = {}
    for part in parts[1:]:
        name, separator, parameter_value = part.partition("=")
        if separator != "=" or name in parameters:
            return False
        parameters[name] = parameter_value.strip('"')
    return not parameters or parameters == {"charset": "utf-8"}


def _should_read_body(
    *,
    status_code: int,
    content_type: str | None,
    content_encoding: str | None,
    content_length: int | None,
    maximum_response_bytes: int,
) -> bool:
    if status_code != 200 or not _is_json_content_type(content_type):
        return False
    if content_encoding is not None and content_encoding.casefold() != "identity":
        return False
    return content_length is None or content_length <= maximum_response_bytes


def _read_body(
    response: requests.Response,
    *,
    maximum_response_bytes: int,
) -> tuple[bytes, ...]:
    body = bytearray()
    try:
        for chunk in response.iter_content(
            chunk_size=_STREAM_CHUNK_BYTES,
            decode_unicode=False,
        ):
            if not chunk:
                continue
            if type(chunk) is not bytes:
                _raise_invalid_response()
            if len(body) + len(chunk) > maximum_response_bytes:
                _raise_invalid_response()
            body.extend(chunk)
    except CloudflareExecutionError:
        raise
    except Exception:
        _raise_transport_failed()
    return (bytes(body),) if body else ()


def _project_response(
    response: requests.Response,
    *,
    maximum_response_bytes: int,
) -> CloudflareHttpResponse:
    status_code = response.status_code
    if type(status_code) is not int or not 100 <= status_code <= 599:
        _raise_invalid_response()
    content_type = _response_header(response, "Content-Type")
    content_encoding = _response_header(response, "Content-Encoding")
    content_length = _content_length(response)
    body_chunks: tuple[bytes, ...] = ()
    if _should_read_body(
        status_code=status_code,
        content_type=content_type,
        content_encoding=content_encoding,
        content_length=content_length,
        maximum_response_bytes=maximum_response_bytes,
    ):
        body_chunks = _read_body(
            response,
            maximum_response_bytes=maximum_response_bytes,
        )
    return CloudflareHttpResponse(
        status_code=status_code,
        content_type=content_type,
        content_length=content_length,
        content_encoding=content_encoding,
        body_chunks=body_chunks,
    )


def _configure_session(session: requests.Session) -> None:
    session.trust_env = False
    session.headers.clear()
    session.cookies.clear()
    session.proxies.clear()
    session.auth = None
    session.mount("http://", HTTPAdapter(max_retries=0))
    session.mount("https://", HTTPAdapter(max_retries=0))


def _close_response(response: requests.Response) -> None:
    if response._content_consumed:
        response.raw.close()
    response.close()


def _multipart_files(request: CloudflareImageRequest) -> list[tuple[str, tuple[object, ...]]]:
    form = request.multipart_form()
    fields: list[tuple[str, tuple[object, ...]]] = [
        (field.name, (None, field.value)) for field in form.text_fields
    ]
    fields.extend(
        (
            field.name,
            (field.filename, field.body, field.content_type),
        )
        for field in form.file_fields
    )
    return fields


class RequestsCloudflareTransport:
    """Send one isolated multipart request without retaining credential or session state."""

    def post_multipart(
        self,
        *,
        request: CloudflareImageRequest,
        url: str,
        api_token: str,
        timeout_seconds: int,
        allow_redirects: Literal[False],
        accept_encoding: Literal["identity"],
        maximum_response_bytes: int,
    ) -> CloudflareHttpResponse:
        validated_request, validated_url, validated_token = _validated_transport_contract(
            request=request,
            url=url,
            api_token=api_token,
            timeout_seconds=timeout_seconds,
            allow_redirects=allow_redirects,
            accept_encoding=accept_encoding,
            maximum_response_bytes=maximum_response_bytes,
        )
        headers = dict(CLOUDFLARE_REQUEST_HEADERS)
        headers["Authorization"] = f"Bearer {validated_token}"

        try:
            session = requests.Session()
            response: requests.Response | None = None
            try:
                _configure_session(session)
                response = session.request(
                    method="POST",
                    url=validated_url,
                    headers=headers,
                    files=_multipart_files(validated_request),
                    timeout=(timeout_seconds, timeout_seconds),
                    allow_redirects=False,
                    stream=True,
                    verify=True,
                    proxies={},
                )
                if not isinstance(response, requests.Response):
                    _raise_transport_failed()
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
        except CloudflareExecutionError:
            raise
        except Exception:
            _raise_transport_failed()


def _response_body(response: object) -> bytes:
    if type(response) is not CloudflareHttpResponse:
        _raise_invalid_response()
    if type(response.status_code) is not int:
        _raise_invalid_response()
    if response.status_code != 200:
        _raise_transport_failed()
    if not _is_json_content_type(response.content_type):
        _raise_invalid_response()
    if response.content_encoding is not None and (
        type(response.content_encoding) is not str
        or response.content_encoding.casefold() != "identity"
    ):
        _raise_invalid_response()
    if response.content_length is not None and (
        type(response.content_length) is not int
        or response.content_length < 0
        or response.content_length > CLOUDFLARE_MAX_RESPONSE_BYTES
    ):
        _raise_invalid_response()

    chunks: list[bytes] = []
    total = 0
    try:
        for chunk in response.body_chunks:
            if type(chunk) is not bytes:
                _raise_invalid_response()
            total += len(chunk)
            if total > CLOUDFLARE_MAX_RESPONSE_BYTES:
                _raise_invalid_response()
            if chunk:
                chunks.append(chunk)
    except CloudflareExecutionError:
        raise
    except Exception:
        _raise_invalid_response()
    if total == 0 or (response.content_length is not None and response.content_length != total):
        _raise_invalid_response()
    return b"".join(chunks)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("duplicate JSON key")
        result[name] = value
    return result


def _reject_non_finite_constant(_value: str) -> None:
    raise ValueError("non-finite JSON number")


def _response_image_text(response: object) -> str:
    body = _response_body(response)
    try:
        payload = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite_constant,
        )
    except (UnicodeError, ValueError, RecursionError):
        _raise_invalid_response()
    if type(payload) is not dict or set(payload) != {
        "result",
        "success",
        "errors",
        "messages",
    }:
        _raise_invalid_response()
    if (
        payload["success"] is not True
        or type(payload["errors"]) is not list
        or payload["errors"]
        or type(payload["messages"]) is not list
        or payload["messages"]
    ):
        _raise_invalid_response()
    result = payload["result"]
    if type(result) is not dict or set(result) != {"image"}:
        _raise_invalid_response()
    encoded = result["image"]
    if type(encoded) is not str or not encoded:
        _raise_invalid_response()
    return encoded


def _decoded_image(encoded: str) -> bytes:
    if len(encoded) > _MAX_BASE64_CHARACTERS:
        _raise_invalid_image()
    try:
        encoded_bytes = encoded.encode("ascii")
        decoded = base64.b64decode(encoded_bytes, validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError):
        _raise_invalid_response()
    if not decoded:
        _raise_invalid_response()
    if base64.b64encode(decoded) != encoded_bytes:
        _raise_invalid_response()
    if len(decoded) > CLOUDFLARE_MAX_IMAGE_BYTES:
        _raise_invalid_image()
    return decoded


def _encode_clean_png(image: Image.Image) -> bytes:
    converted = image.convert("RGB")
    try:
        pixels = converted.tobytes()
    finally:
        converted.close()
    clean = Image.frombytes("RGB", image.size, pixels)
    output = BytesIO()
    try:
        clean.save(
            output,
            format="PNG",
            optimize=False,
            compress_level=9,
        )
    finally:
        clean.close()
    result = output.getvalue()
    if not result or len(result) > CLOUDFLARE_MAX_IMAGE_BYTES:
        _raise_invalid_image()
    return result


def _provider_image_format(body: bytes) -> str:
    if body.startswith(_PNG_SIGNATURE):
        return "PNG"
    if body.startswith(_JPEG_SIGNATURE):
        return "JPEG"
    if (
        len(body) >= 12
        and body.startswith(_WEBP_RIFF_SIGNATURE)
        and body[8:12] == _WEBP_FORMAT_SIGNATURE
    ):
        return "WEBP"
    _raise_invalid_image()


def _normalized_png(body: bytes) -> bytes:
    if type(body) is not bytes or not body or len(body) > CLOUDFLARE_MAX_IMAGE_BYTES:
        _raise_invalid_image()
    try:
        image_format = _provider_image_format(body)
        expected_size = (CLOUDFLARE_OUTPUT_DIMENSION, CLOUDFLARE_OUTPUT_DIMENSION)
        if image_format == "PNG" and _png_dimensions(body) != expected_size:
            _raise_invalid_image()
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(body), formats=_PROVIDER_IMAGE_FORMATS) as source:
                if (
                    source.format != image_format
                    or source.size != expected_size
                    or getattr(source, "is_animated", False)
                    or getattr(source, "n_frames", 1) != 1
                ):
                    _raise_invalid_image()
                source.load()
                if source.size != expected_size:
                    _raise_invalid_image()
                normalized = _encode_clean_png(source)
        if _png_dimensions(normalized) != expected_size:
            _raise_invalid_image()
        return normalized
    except CloudflareExecutionError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        TypeError,
        ValueError,
    ):
        _raise_invalid_image()


def _artifact(
    request: CloudflareImageRequest,
    *,
    body: bytes,
) -> CloudflareImageArtifact:
    normalized = _normalized_png(body)
    try:
        return CloudflareImageArtifact(
            schema_version="2.0",
            angle=request.angle,
            attempt=request.attempt,
            request_sha256=cloudflare_image_request_sha256(request),
            content_type="image/png",
            sha256=hashlib.sha256(normalized).hexdigest(),
            byte_length=len(normalized),
            width=CLOUDFLARE_OUTPUT_DIMENSION,
            height=CLOUDFLARE_OUTPUT_DIMENSION,
            body=normalized,
        )
    except (CloudflareRequestError, TypeError, ValidationError, ValueError):
        _raise_invalid_artifact()


def parse_cloudflare_image_response(
    *,
    request: CloudflareImageRequest,
    response: CloudflareHttpResponse,
) -> CloudflareImageArtifact:
    validated_request = _validated_request(request)
    encoded = _response_image_text(response)
    return _artifact(validated_request, body=_decoded_image(encoded))


def _reference_png(front: CloudflareImageArtifact) -> bytes:
    try:
        validated = CloudflareImageArtifact.model_validate(front)
        with Image.open(BytesIO(validated.body), formats=("PNG",)) as source:
            source.load()
            resized = source.convert("RGB").resize(
                (MAX_REFERENCE_IMAGE_DIMENSION, MAX_REFERENCE_IMAGE_DIMENSION),
                resample=Image.Resampling.LANCZOS,
            )
            try:
                reference = _encode_clean_png(resized)
            finally:
                resized.close()
        if _png_dimensions(reference) != (
            MAX_REFERENCE_IMAGE_DIMENSION,
            MAX_REFERENCE_IMAGE_DIMENSION,
        ):
            _raise_invalid_image()
        return reference
    except CloudflareExecutionError:
        raise
    except (TypeError, ValidationError, ValueError, OSError, UnidentifiedImageError):
        _raise_invalid_image()


def _image_set_digest(images: tuple[CloudflareImageArtifact, ...]) -> str:
    canonical = json.dumps(
        [image.model_dump(mode="json") for image in images],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(b"amazon-explorer-cloudflare-image-set-v2\n" + canonical).hexdigest()


def cloudflare_image_set_sha256(images: object) -> str:
    if type(images) is not tuple or len(images) != len(IMAGE_ANGLES):
        _raise_invalid_artifact()
    try:
        validated = tuple(CloudflareImageArtifact.model_validate(image) for image in images)
    except (TypeError, ValidationError, ValueError):
        _raise_invalid_artifact()
    if tuple(image.angle for image in validated) != IMAGE_ANGLES:
        _raise_invalid_artifact()
    if len({image.attempt for image in validated}) != 1:
        _raise_invalid_artifact()
    return _image_set_digest(validated)


def _validated_execution_context(
    session: object,
    *,
    intent: object,
    usage_ledger: object,
    usage_reservation: object,
) -> tuple[
    SearchSessionSnapshot,
    NormalizedSearchIntent,
    InMemoryUsageLedger,
    UsageReservation,
]:
    try:
        validated_session = SearchSessionSnapshot.model_validate(session)
        validated_intent = NormalizedSearchIntent.model_validate(intent)
        validated_reservation = UsageReservation.model_validate(usage_reservation)
        if not isinstance(usage_ledger, InMemoryUsageLedger):
            raise TypeError("usage ledger type is invalid")
        if (
            validated_session.state != "image_generating"
            or validated_session.image_mode != "on"
            or validated_session.image_attempts_started not in {1, 2}
            or validated_session.query_plan_sha256 is None
            or validated_session.active_image_reservation_id != validated_reservation.reservation_id
            or not hmac.compare_digest(
                validated_session.intent_sha256 or "",
                search_intent_sha256(validated_intent),
            )
            or validated_reservation.status != "started"
            or validated_reservation.provider != "cloudflare"
            or validated_reservation.operation != "image_set"
            or validated_reservation.owner_id != validated_session.owner_id
            or validated_reservation.session_id != validated_session.session_id
            or validated_reservation.amount.calls != 4
            or validated_reservation.amount.tokens != 0
            or not hmac.compare_digest(
                validated_reservation.binding_sha256,
                validated_session.query_plan_sha256,
            )
            or not hmac.compare_digest(
                validated_reservation.usage_policy_sha256,
                validated_session.usage_policy_sha256 or "",
            )
        ):
            raise ValueError("image execution binding is invalid")
        current = next(
            (
                reservation
                for reservation in usage_ledger.snapshot().reservations
                if reservation.reservation_id == validated_reservation.reservation_id
            ),
            None,
        )
        if current != validated_reservation:
            raise ValueError("usage reservation is not current")
        return (
            validated_session,
            validated_intent,
            usage_ledger,
            validated_reservation,
        )
    except Exception:
        _raise_invalid_execution()


def _transport_post(
    transport: CloudflareRequestTransport,
    *,
    request: CloudflareImageRequest,
    url: str,
    api_token: str,
) -> CloudflareHttpResponse:
    try:
        return transport.post_multipart(
            request=request,
            url=url,
            api_token=api_token,
            timeout_seconds=CLOUDFLARE_REQUEST_TIMEOUT_SECONDS,
            allow_redirects=False,
            accept_encoding="identity",
            maximum_response_bytes=CLOUDFLARE_MAX_RESPONSE_BYTES,
        )
    except CloudflareExecutionError:
        raise
    except Exception:
        _raise_transport_failed()


def _utc_datetime(value: object) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() != timedelta(0):
        _raise_transport_failed()
    return value.astimezone(timezone.utc)


def _finish_usage(
    usage_ledger: InMemoryUsageLedger,
    reservation: UsageReservation,
    *,
    success: bool,
    finished_at: datetime,
) -> UsageReservation:
    try:
        finished = usage_ledger.finish(
            reservation.reservation_id,
            owner_id=reservation.owner_id,
            session_id=reservation.session_id,
            success=success,
            now=finished_at,
        )
        if (
            finished.status != ("succeeded" if success else "failed")
            or finished.request != reservation.request
            or not hmac.compare_digest(
                finished.usage_policy_sha256,
                reservation.usage_policy_sha256,
            )
        ):
            raise ValueError("finished reservation changed its binding")
        return finished
    except Exception:
        _raise_transport_failed()


def _failure_time(now: Callable[[], datetime]) -> datetime:
    try:
        return _utc_datetime(now())
    except CloudflareExecutionError:
        raise
    except Exception:
        _raise_transport_failed()


def _project_succeeded(
    reservation: UsageReservation,
    *,
    finished_at: datetime,
) -> UsageReservation:
    payload = reservation.model_dump(mode="python")
    payload.update(status="succeeded", finished_at=finished_at)
    try:
        return UsageReservation.model_validate(payload)
    except (TypeError, ValidationError, ValueError):
        _raise_transport_failed()


def execute_cloudflare_image_set(
    session: SearchSessionSnapshot,
    *,
    intent: NormalizedSearchIntent,
    usage_ledger: InMemoryUsageLedger,
    usage_reservation: UsageReservation,
    account_id: str,
    api_token: str,
    transport: CloudflareRequestTransport,
    now: Callable[[], datetime],
    approved_reference_png: bytes | None = None,
) -> CloudflareImageSetExecution:
    """Execute one approved four-image attempt and record only an all-success set."""
    validated_session, validated_intent, ledger, reservation = _validated_execution_context(
        session,
        intent=intent,
        usage_ledger=usage_ledger,
        usage_reservation=usage_reservation,
    )

    try:
        if not callable(now) or not callable(getattr(transport, "post_multipart", None)):
            _raise_invalid_execution()
        endpoint = cloudflare_endpoint(account_id)
        validated_token = _validated_api_token(api_token)
        plan_sha256 = validated_session.query_plan_sha256
        if type(plan_sha256) is not str or _DIGEST_PATTERN.fullmatch(plan_sha256) is None:
            _raise_invalid_execution()
        if approved_reference_png is None:
            front_request = build_cloudflare_front_request(
                intent=validated_intent,
                preimage_plan_sha256=plan_sha256,
                attempt=validated_session.image_attempts_started,
            )
            front = parse_cloudflare_image_response(
                request=front_request,
                response=_transport_post(
                    transport,
                    request=front_request,
                    url=endpoint,
                    api_token=validated_token,
                ),
            )
            request_set = build_cloudflare_request_set(
                intent=validated_intent,
                preimage_plan_sha256=plan_sha256,
                attempt=validated_session.image_attempts_started,
                front_reference_png=_reference_png(front),
            )
            if request_set.requests[0] != front_request:
                _raise_invalid_execution()
            images = [front]
            pending_requests = request_set.requests[1:]
        else:
            request_set = build_cloudflare_request_set(
                intent=validated_intent,
                preimage_plan_sha256=plan_sha256,
                attempt=validated_session.image_attempts_started,
                front_reference_png=approved_reference_png,
                derive_front=True,
            )
            images = []
            pending_requests = request_set.requests
        for request in pending_requests:
            images.append(
                parse_cloudflare_image_response(
                    request=request,
                    response=_transport_post(
                        transport,
                        request=request,
                        url=endpoint,
                        api_token=validated_token,
                    ),
                )
            )
        image_tuple = tuple(images)
        image_set_sha256 = cloudflare_image_set_sha256(image_tuple)
        request_metadata_sha256 = cloudflare_request_set_sha256(request_set)
    except CloudflareExecutionError:
        _finish_usage(
            ledger,
            reservation,
            success=False,
            finished_at=_failure_time(now),
        )
        raise
    except Exception:
        _finish_usage(
            ledger,
            reservation,
            success=False,
            finished_at=_failure_time(now),
        )
        _raise_transport_failed()

    finished_at = _failure_time(now)
    projected_reservation = _project_succeeded(
        reservation,
        finished_at=finished_at,
    )
    try:
        completed_session = record_image_set(
            validated_session,
            image_reservation=projected_reservation,
            image_set_sha256=image_set_sha256,
            image_request_metadata_sha256=request_metadata_sha256,
            expected_revision=validated_session.revision,
            now=finished_at,
        )
    except (SearchStateError, TypeError, ValidationError, ValueError):
        _finish_usage(
            ledger,
            reservation,
            success=False,
            finished_at=finished_at,
        )
        _raise_invalid_execution()

    try:
        execution = CloudflareImageSetExecution(
            schema_version="2.0",
            request_set=request_set,
            images=image_tuple,
            image_set_sha256=image_set_sha256,
            request_metadata_sha256=request_metadata_sha256,
            usage_reservation=projected_reservation,
            session=completed_session,
        )
    except (CloudflareRequestError, TypeError, ValidationError, ValueError):
        _finish_usage(
            ledger,
            reservation,
            success=False,
            finished_at=finished_at,
        )
        _raise_invalid_artifact()
    finished_reservation = _finish_usage(
        ledger,
        reservation,
        success=True,
        finished_at=finished_at,
    )
    if finished_reservation != execution.usage_reservation:
        _raise_transport_failed()
    return execution
