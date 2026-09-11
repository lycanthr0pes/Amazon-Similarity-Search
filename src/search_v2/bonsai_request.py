from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import re
import unicodedata
from collections.abc import Callable
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated
from typing import Literal
from typing import Protocol
from urllib.parse import urlsplit

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import ValidationError
from pydantic import field_validator
from pydantic import model_validator

from src.exceptions import BonsaiRequestError
from src.exceptions import BonsaiResponseError
from src.search_v2.bonsai_adapter import BonsaiResponseContractError
from src.search_v2.bonsai_adapter import BonsaiResponseDiagnostic
from src.search_v2.bonsai_adapter import parse_bonsai_intent_response
from src.search_v2.bonsai_adapter import search_intent_generation_schema_bytes
from src.search_v2.bonsai_adapter import search_intent_schema_bytes
from src.search_v2.intent import MAX_BOUND_ARTIFACT_BYTES
from src.search_v2.intent import MAX_SOURCE_INPUT_CODEPOINTS
from src.search_v2.intent import NormalizedSearchIntent
from src.search_v2.source_constraints import bind_generation_schema
from src.search_v2.source_constraints import needs_attribute_name_inference
from src.search_v2.source_constraints import source_name_task_input
from src.search_v2.source_constraints import validate_source_response
from src.search_v2.usage_ledger import MAX_USAGE_TOKENS
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import UsageReservation


BONSAI_MAX_RESPONSE_BYTES = MAX_BOUND_ARTIFACT_BYTES
BONSAI_MAX_PROMPT_BYTES = 65_536
BONSAI_INTENT_PROMPT_PATH = Path(__file__).with_name("bonsai_intent_prompt.txt")
BONSAI_ATTRIBUTE_NAME_PROMPT_PATH = Path(__file__).with_name("bonsai_attribute_name_prompt.txt")
BONSAI_REQUEST_HEADERS: tuple[tuple[str, str], ...] = (
    ("Accept", "application/json"),
    ("Accept-Encoding", "identity"),
    ("Content-Type", "application/json"),
)

_CHAT_COMPLETIONS_SUFFIX = "/chat/completions"
_INVALID_REQUEST_MESSAGE = "Bonsai intent request is invalid"
_REQUEST_FAILED_MESSAGE = "Bonsai intent request failed"
_INVALID_RESPONSE_MESSAGE = "Bonsai response did not match the search intent contract"
_DNS_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Endpoint = Annotated[str, StringConstraints(min_length=1, max_length=2_048)]
ModelId = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class _StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


def _raise_invalid_request() -> None:
    raise BonsaiRequestError(_INVALID_REQUEST_MESSAGE) from None


def _raise_request_failed() -> None:
    raise BonsaiRequestError(_REQUEST_FAILED_MESSAGE) from None


def _raise_invalid_response(*, response_bytes: int = 0) -> None:
    raise BonsaiResponseContractError(
        BonsaiResponseDiagnostic(
            stage="response_metadata_invalid",
            draft_failure_group="not_applicable",
            searchability_failure_group="not_applicable",
            finish_reason="missing",
            completion_tokens=None,
            response_bytes=response_bytes,
        )
    ) from None


def _is_canonical_dns_host(host: str) -> bool:
    if not host or len(host) > 253 or host != host.casefold() or host.endswith("."):
        return False
    labels = host.split(".")
    return len(labels) >= 2 and all(_DNS_LABEL_PATTERN.fullmatch(label) for label in labels)


def _validated_base_url(value: object) -> str:
    if type(value) is not str or not value or len(value) > 2_048:
        raise ValueError("base URL is invalid")
    if value != value.strip() or any(ord(character) <= 0x20 for character in value):
        raise ValueError("base URL contains unsupported whitespace")
    try:
        value.encode("ascii")
        parsed = urlsplit(value)
        port = parsed.port
    except (UnicodeEncodeError, ValueError) as exc:
        raise ValueError("base URL is invalid") from exc

    host = parsed.hostname
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or host is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != "/v1"
        or parsed.query
        or parsed.fragment
        or "%" in parsed.netloc
        or "\\" in parsed.netloc
    ):
        raise ValueError("base URL is not an approved operation URL")

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
        if not _is_canonical_dns_host(host):
            raise ValueError("base URL host is invalid") from None

    if parsed.scheme == "http" and (address is None or not address.is_loopback):
        raise ValueError("plain HTTP is limited to loopback addresses")

    if address is None:
        canonical_host = host
    elif address.version == 6:
        canonical_host = f"[{address.compressed}]"
    else:
        canonical_host = address.compressed
    expected_netloc = canonical_host if port is None else f"{canonical_host}:{port}"
    canonical = f"{parsed.scheme}://{expected_netloc}/v1"
    if value != canonical:
        raise ValueError("base URL is not canonical")
    return canonical


def _validated_endpoint(value: str) -> str:
    if not value.endswith(_CHAT_COMPLETIONS_SUFFIX):
        raise ValueError("Bonsai endpoint path is invalid")
    base_url = value[: -len(_CHAT_COMPLETIONS_SUFFIX)]
    if f"{_validated_base_url(base_url)}{_CHAT_COMPLETIONS_SUFFIX}" != value:
        raise ValueError("Bonsai endpoint is invalid")
    return value


def _validated_model_id(value: object) -> str:
    if type(value) is not str or not value or len(value) > 200 or value != value.strip():
        raise ValueError("model ID is invalid")
    if any(unicodedata.category(character).startswith("C") for character in value):
        raise ValueError("model ID contains control data")
    return value


def _source_input_sha256(value: object) -> str:
    if type(value) is not str or not value or len(value) > MAX_SOURCE_INPUT_CODEPOINTS:
        raise ValueError("source input is invalid")
    normalized = unicodedata.normalize("NFKC", value)
    if any(
        unicodedata.category(character).startswith("C") and not character.isspace()
        for character in normalized
    ):
        raise ValueError("source input contains control data")
    if not " ".join(normalized.split()):
        raise ValueError("source input is empty")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validated_prompt(value: object) -> tuple[bytes, str]:
    if type(value) is not bytes or not value or len(value) > BONSAI_MAX_PROMPT_BYTES:
        raise ValueError("prompt bytes are invalid")
    text = value.decode("utf-8")
    if not text.strip() or "\x00" in text:
        raise ValueError("prompt text is invalid")
    return value, text


def _validated_temperature(value: object) -> float:
    if type(value) not in {int, float} or type(value) is bool:
        raise ValueError("temperature is invalid")
    normalized = float(value)
    if not 0.0 <= normalized <= 2.0:
        raise ValueError("temperature is invalid")
    return normalized


class BonsaiIntentRequest(_StrictFrozenContract):
    schema_version: Literal["9.0"]
    provider: Literal["bonsai"]
    method: Literal["POST"]
    endpoint: Endpoint
    model_id: ModelId
    temperature: Annotated[float, Field(ge=0.0, le=2.0)]
    response_format: Literal["json_object"]
    allow_redirects: Literal[False]
    accept: Literal["application/json"]
    accept_encoding: Literal["identity"]
    content_type: Literal["application/json"]
    maximum_response_bytes: Literal[1_048_576]
    maximum_usage_tokens: Annotated[int, Field(ge=1, le=MAX_USAGE_TOKENS)]
    source_input_sha256: Digest
    prompt_sha256: Digest
    schema_sha256: Digest
    generation_schema_sha256: Digest
    body_sha256: Digest

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        return _validated_endpoint(value)

    @field_validator("model_id")
    @classmethod
    def validate_model_id(cls, value: str) -> str:
        return _validated_model_id(value)

    @model_validator(mode="after")
    def validate_usage_ceiling(self) -> BonsaiIntentRequest:
        if self.maximum_usage_tokens <= self.maximum_response_bytes:
            raise ValueError("usage token ceiling must include the request and response")
        return self


@dataclass(frozen=True, slots=True, repr=False)
class PreparedBonsaiIntentRequest:
    request: BonsaiIntentRequest
    source_input: str
    prompt: bytes
    body: bytes


@dataclass(frozen=True, slots=True, repr=False)
class BonsaiHttpResponse:
    status_code: int
    content_type: str | None
    content_length: int | None
    content_encoding: str | None
    body_chunks: Iterable[bytes]


class BonsaiRequestTransport(Protocol):
    def post_json(
        self,
        *,
        url: str,
        headers: tuple[tuple[str, str], ...],
        body: bytes,
        allow_redirects: Literal[False],
        accept_encoding: Literal["identity"],
        maximum_response_bytes: int,
    ) -> BonsaiHttpResponse: ...


@dataclass(frozen=True, slots=True, repr=False)
class BonsaiIntentExecution:
    request: BonsaiIntentRequest
    intent: NormalizedSearchIntent
    usage_reservation: UsageReservation


def load_bonsai_intent_prompt() -> bytes:
    """Read the repository-fixed v2 prompt as exact UTF-8 bytes."""
    return _load_fixed_prompt(BONSAI_INTENT_PROMPT_PATH)


def _load_runtime_prompt(source_input: str) -> bytes:
    if needs_attribute_name_inference(source_input):
        return _load_fixed_prompt(BONSAI_ATTRIBUTE_NAME_PROMPT_PATH)
    return load_bonsai_intent_prompt()


def _load_fixed_prompt(path: Path) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            _raise_invalid_request()
        prompt = path.read_bytes()
        return _validated_prompt(prompt)[0]
    except BonsaiRequestError:
        raise
    except (OSError, UnicodeError, ValueError):
        _raise_invalid_request()


def _canonical_body(
    *,
    source_input: str,
    prompt_text: str,
    generation_schema_text: str,
    model_id: str,
    temperature: float,
) -> bytes:
    payload = {
        "messages": [
            {
                "content": prompt_text,
                "role": "system",
            },
            {"content": source_name_task_input(source_input), "role": "user"},
        ],
        "model": model_id,
        "response_format": {
            "schema": json.loads(generation_schema_text),
            "type": "json_object",
        },
        "stream": False,
        "temperature": temperature,
    }
    # Preserve the schema's generation order through the final HTTP body.
    # The fixed construction order remains deterministic and digest-bound.
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
    ).encode("utf-8")


def build_bonsai_intent_request(
    source_input: str,
    *,
    base_url: str,
    model_id: str,
    temperature: float,
) -> PreparedBonsaiIntentRequest:
    """Build one canonical credential-free v9 request bound to explicit source facts."""
    try:
        validated_base_url = _validated_base_url(base_url)
        validated_model_id = _validated_model_id(model_id)
        source_digest = _source_input_sha256(source_input)
        validated_temperature = _validated_temperature(temperature)
        prompt, prompt_text = _validated_prompt(_load_runtime_prompt(source_input))
        schema = search_intent_schema_bytes()
        generation_schema = bind_generation_schema(
            source_input, search_intent_generation_schema_bytes()
        )
        body = _canonical_body(
            source_input=source_input,
            prompt_text=prompt_text,
            generation_schema_text=generation_schema.decode("utf-8"),
            model_id=validated_model_id,
            temperature=validated_temperature,
        )
        if not body or len(body) > MAX_BOUND_ARTIFACT_BYTES:
            raise ValueError("request body is invalid")
        maximum_usage_tokens = len(body) + BONSAI_MAX_RESPONSE_BYTES
        request = BonsaiIntentRequest(
            schema_version="9.0",
            provider="bonsai",
            method="POST",
            endpoint=f"{validated_base_url}{_CHAT_COMPLETIONS_SUFFIX}",
            model_id=validated_model_id,
            temperature=validated_temperature,
            response_format="json_object",
            allow_redirects=False,
            accept="application/json",
            accept_encoding="identity",
            content_type="application/json",
            maximum_response_bytes=BONSAI_MAX_RESPONSE_BYTES,
            maximum_usage_tokens=maximum_usage_tokens,
            source_input_sha256=source_digest,
            prompt_sha256=hashlib.sha256(prompt).hexdigest(),
            schema_sha256=hashlib.sha256(schema).hexdigest(),
            generation_schema_sha256=hashlib.sha256(generation_schema).hexdigest(),
            body_sha256=hashlib.sha256(body).hexdigest(),
        )
        return PreparedBonsaiIntentRequest(
            request=request,
            source_input=source_input,
            prompt=prompt,
            body=body,
        )
    except BonsaiRequestError:
        raise
    except (TypeError, UnicodeError, ValidationError, ValueError):
        _raise_invalid_request()


def bonsai_intent_request_sha256(request: BonsaiIntentRequest) -> str:
    try:
        validated = BonsaiIntentRequest.model_validate(request)
    except (TypeError, ValidationError, ValueError):
        _raise_invalid_request()
    canonical = json.dumps(
        validated.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(b"amazon-explorer-bonsai-intent-request-v9\n" + canonical).hexdigest()


def _validated_prepared_request(
    prepared: PreparedBonsaiIntentRequest,
) -> BonsaiIntentRequest:
    if type(prepared) is not PreparedBonsaiIntentRequest:
        _raise_invalid_request()
    try:
        request = BonsaiIntentRequest.model_validate(prepared.request)
        if type(prepared.source_input) is not str or type(prepared.body) is not bytes:
            raise ValueError("prepared request field type is invalid")
        source_digest = _source_input_sha256(prepared.source_input)
        expected_prompt = _load_runtime_prompt(prepared.source_input)
        if type(prepared.prompt) is not bytes or not hmac.compare_digest(
            prepared.prompt,
            expected_prompt,
        ):
            raise ValueError("prepared prompt is not the fixed runtime prompt")
        prompt, prompt_text = _validated_prompt(prepared.prompt)
        schema = search_intent_schema_bytes()
        generation_schema = bind_generation_schema(
            prepared.source_input, search_intent_generation_schema_bytes()
        )
        body = _canonical_body(
            source_input=prepared.source_input,
            prompt_text=prompt_text,
            generation_schema_text=generation_schema.decode("utf-8"),
            model_id=request.model_id,
            temperature=request.temperature,
        )
        expected_digests = (
            (source_digest, request.source_input_sha256),
            (hashlib.sha256(prompt).hexdigest(), request.prompt_sha256),
            (hashlib.sha256(schema).hexdigest(), request.schema_sha256),
            (
                hashlib.sha256(generation_schema).hexdigest(),
                request.generation_schema_sha256,
            ),
            (hashlib.sha256(body).hexdigest(), request.body_sha256),
        )
        if not hmac.compare_digest(body, prepared.body) or any(
            not hmac.compare_digest(expected, actual) for expected, actual in expected_digests
        ):
            raise ValueError("prepared request binding is invalid")
        if request.maximum_usage_tokens != len(body) + request.maximum_response_bytes:
            raise ValueError("prepared usage token ceiling is invalid")
        return request
    except BonsaiRequestError:
        raise
    except (TypeError, UnicodeError, ValidationError, ValueError):
        _raise_invalid_request()


def _validated_reserved_usage(
    reservation: UsageReservation,
    *,
    request: BonsaiIntentRequest,
) -> UsageReservation:
    try:
        validated = UsageReservation.model_validate(reservation)
        if (
            validated.status != "reserved"
            or validated.provider != "bonsai"
            or validated.operation != "intent"
            or validated.amount.calls != 1
            or validated.amount.tokens < request.maximum_usage_tokens
            or not hmac.compare_digest(
                validated.binding_sha256,
                bonsai_intent_request_sha256(request),
            )
        ):
            raise ValueError("usage reservation does not match the request")
        return validated
    except BonsaiRequestError:
        raise
    except (TypeError, ValidationError, ValueError):
        _raise_invalid_request()


def _start_usage(
    ledger: InMemoryUsageLedger,
    reservation: UsageReservation,
    *,
    now: Callable[[], datetime],
) -> UsageReservation:
    try:
        started = ledger.start(
            reservation.reservation_id,
            owner_id=reservation.owner_id,
            session_id=reservation.session_id,
            now=now(),
        )
        if (
            started.status != "started"
            or started.request != reservation.request
            or started.usage_policy_sha256 != reservation.usage_policy_sha256
        ):
            raise ValueError("started reservation changed its binding")
        return started
    except Exception:
        _raise_invalid_request()


def _finish_usage(
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
            now=now(),
        )
    except Exception:
        _raise_request_failed()


def _validated_content_type(value: object) -> None:
    if type(value) is not str or not value or len(value) > 200:
        _raise_invalid_response()
    parts = [part.strip().casefold() for part in value.split(";")]
    if parts[0] != "application/json" or any(not part for part in parts):
        _raise_invalid_response()
    parameters: dict[str, str] = {}
    for part in parts[1:]:
        name, separator, parameter_value = part.partition("=")
        if separator != "=" or name in parameters:
            _raise_invalid_response()
        parameters[name] = parameter_value.strip('"')
    if parameters and parameters != {"charset": "utf-8"}:
        _raise_invalid_response()


def _response_body(response: object) -> bytes:
    if not isinstance(response, BonsaiHttpResponse):
        _raise_invalid_response()
    if type(response.status_code) is not int:
        _raise_invalid_response()
    if response.status_code != 200:
        _raise_request_failed()

    _validated_content_type(response.content_type)
    if response.content_encoding is not None and (
        type(response.content_encoding) is not str
        or response.content_encoding.casefold() != "identity"
    ):
        _raise_invalid_response()
    if response.content_length is not None and (
        type(response.content_length) is not int
        or response.content_length < 0
        or response.content_length > BONSAI_MAX_RESPONSE_BYTES
    ):
        _raise_invalid_response()

    chunks: list[bytes] = []
    total = 0
    invalid_chunks = False
    try:
        for chunk in response.body_chunks:
            if type(chunk) is not bytes:
                invalid_chunks = True
                break
            total += len(chunk)
            if total > BONSAI_MAX_RESPONSE_BYTES:
                invalid_chunks = True
                break
            chunks.append(chunk)
    except Exception:
        invalid_chunks = True
    if invalid_chunks:
        _raise_invalid_response(response_bytes=min(total, BONSAI_MAX_RESPONSE_BYTES + 1))

    if response.content_length is not None and response.content_length != total:
        _raise_invalid_response(response_bytes=total)
    return b"".join(chunks)


def execute_bonsai_intent_request(
    prepared: PreparedBonsaiIntentRequest,
    *,
    usage_ledger: InMemoryUsageLedger,
    usage_reservation: UsageReservation,
    transport: BonsaiRequestTransport,
    now: Callable[[], datetime],
) -> BonsaiIntentExecution:
    """Execute exactly one injected transport attempt and close its usage lifecycle."""
    if not isinstance(usage_ledger, InMemoryUsageLedger):
        _raise_invalid_request()
    if not callable(now) or not callable(getattr(transport, "post_json", None)):
        _raise_invalid_request()

    request = _validated_prepared_request(prepared)
    reservation = _validated_reserved_usage(usage_reservation, request=request)
    started = _start_usage(usage_ledger, reservation, now=now)

    try:
        response = transport.post_json(
            url=request.endpoint,
            headers=BONSAI_REQUEST_HEADERS,
            body=prepared.body,
            allow_redirects=False,
            accept_encoding="identity",
            maximum_response_bytes=request.maximum_response_bytes,
        )
    except Exception:
        _finish_usage(usage_ledger, started, success=False, now=now)
        _raise_request_failed()

    try:
        response_body = _response_body(response)
        intent = parse_bonsai_intent_response(
            source_input=prepared.source_input,
            prompt=prepared.prompt,
            response=response_body,
        )
        try:
            validate_source_response(prepared.source_input, response_body)
        except (TypeError, ValueError, KeyError):
            raise BonsaiResponseError("Bonsai response violated source constraints") from None
    except (BonsaiRequestError, BonsaiResponseError):
        _finish_usage(usage_ledger, started, success=False, now=now)
        raise
    except Exception:
        _finish_usage(usage_ledger, started, success=False, now=now)
        _raise_invalid_response()

    finished = _finish_usage(usage_ledger, started, success=True, now=now)
    return BonsaiIntentExecution(
        request=request,
        intent=intent,
        usage_reservation=finished,
    )
