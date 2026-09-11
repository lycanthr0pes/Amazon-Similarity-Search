from __future__ import annotations

import base64
from dataclasses import replace
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import hashlib
from io import BytesIO
import importlib
import importlib.util
import json
from unittest.mock import patch

from PIL import Image
from PIL.PngImagePlugin import PngInfo
import pytest
import requests
from requests.adapters import HTTPAdapter
from requests.cookies import RequestsCookieJar
from requests.structures import CaseInsensitiveDict

from src.search_v2.cloudflare_request import IMAGE_ANGLES
from src.search_v2.cloudflare_request import build_cloudflare_front_request
from src.search_v2.cloudflare_request import build_cloudflare_request_set
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent
from src.search_v2.query_planner import build_search_query_plan
from src.search_v2.query_planner import search_query_plan_sha256
from src.search_v2.state_machine import approve_intent_review
from src.search_v2.state_machine import create_search_session
from src.search_v2.state_machine import record_intent_plan
from src.search_v2.state_machine import start_intent_processing
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import ProviderUsageLimits
from src.search_v2.usage_ledger import UsageAmount
from src.search_v2.usage_ledger import UsageReservationRequest


MODULE_NAME = "src.search_v2.cloudflare_http"
CLOUDFLARE_HTTP = (
    importlib.import_module(MODULE_NAME) if importlib.util.find_spec(MODULE_NAME) else None
)

ACCOUNT_ID = "0123456789abcdef0123456789abcdef"
API_TOKEN = "fixture-cloudflare-api-token"
NOW = datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def require_cloudflare_http_boundary() -> None:
    assert CLOUDFLARE_HTTP is not None, (
        "the Cloudflare HTTP response and image normalization boundary is required"
    )


def module():
    assert CLOUDFLARE_HTTP is not None
    return CLOUDFLARE_HTTP


def normalized_intent():
    payload = {
        "product_name_ja": "ヘッドホン",
        "product_name_en": "headphones",
        "category_ja": "オーディオ",
        "category_en": "audio equipment",
        "required_terms_ja": ["ワイヤレス"],
        "required_terms_en": ["wireless"],
        "preferred_terms_ja": ["軽量"],
        "preferred_terms_en": ["lightweight"],
        "negative_terms_ja": ["中古"],
        "negative_terms_en": ["used"],
        "color_ja": "黒",
        "color_en": "black",
        "features_ja": ["ノイズキャンセリング"],
        "features_en": ["noise cancelling"],
        "brand": "Sony",
        "model_number": "WH-1000XM5",
        "price": {
            "currency": "JPY",
            "mode": "max",
            "target_jpy": None,
            "min_jpy": None,
            "max_jpy": 50_000,
            "source": "explicit",
            "confidence": None,
        },
        "typed_conditions": [],
        "ambiguities": [],
    }
    source_input = "Sony WH-1000XM5を5万円以内で"
    provenance = build_intent_provenance(
        source_input=source_input,
        prompt=b"prompt",
        schema=b"schema",
        response=b"response",
    )
    return normalize_search_intent(
        source_input,
        SearchIntentDraft.model_validate(payload),
        provenance=provenance,
    )


def image_context():
    intent = normalized_intent()
    query_plan = build_search_query_plan(intent)
    session = create_search_session(
        owner_id="owner-1",
        session_id="session-1",
        now=NOW,
    )
    session = start_intent_processing(
        session,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=1),
    )
    session = record_intent_plan(
        session,
        intent=intent,
        query_plan=query_plan,
        typed_proposal=build_typed_requirement_proposal(intent),
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=2),
    )

    limit = UsageAmount(calls=8, tokens=0, cost_microusd=40_000)
    ledger = InMemoryUsageLedger(
        [
            ProviderUsageLimits(
                provider="cloudflare",
                pricing_policy_sha256="b" * 64,
                per_user_day=limit,
                per_session=limit,
                global_day=limit,
            )
        ]
    )
    reserved = ledger.reserve(
        UsageReservationRequest(
            provider="cloudflare",
            operation="image_set",
            owner_id=session.owner_id,
            session_id=session.session_id,
            binding_sha256=search_query_plan_sha256(query_plan),
            amount=UsageAmount(calls=4, tokens=0, cost_microusd=4_000),
            pricing_policy_sha256="b" * 64,
        ),
        now=NOW + timedelta(seconds=3),
    )
    started = ledger.start(
        reserved.reservation_id,
        owner_id=session.owner_id,
        session_id=session.session_id,
        now=NOW + timedelta(seconds=4),
    )
    session = approve_intent_review(
        session,
        use_images=True,
        image_reservation=started,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=5),
    )
    return session, intent, ledger, started


def png_bytes(
    *,
    width: int = 512,
    height: int = 512,
    color: tuple[int, int, int, int] = (10, 20, 30, 255),
    metadata: str | None = None,
) -> bytes:
    output = BytesIO()
    information = None
    if metadata is not None:
        information = PngInfo()
        information.add_text("private-note", metadata)
    Image.new("RGBA", (width, height), color).save(
        output,
        format="PNG",
        pnginfo=information,
    )
    return output.getvalue()


def raster_bytes(image_format: str, *, width: int = 512, height: int = 512) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), (10, 20, 30)).save(output, format=image_format)
    return output.getvalue()


def animated_png_bytes() -> bytes:
    output = BytesIO()
    first = Image.new("RGB", (512, 512), (1, 2, 3))
    second = Image.new("RGB", (512, 512), (4, 5, 6))
    first.save(
        output,
        format="PNG",
        save_all=True,
        append_images=[second],
        duration=100,
        loop=0,
    )
    return output.getvalue()


def response_json(image: bytes, **overrides: object) -> bytes:
    payload: dict[str, object] = {
        "result": {"image": base64.b64encode(image).decode("ascii")},
        "success": True,
        "errors": [],
        "messages": [],
    }
    payload.update(overrides)
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def http_response(
    body: bytes,
    *,
    status_code: int = 200,
    content_type: str | None = "application/json; charset=utf-8",
    content_encoding: str | None = "identity",
    content_length: int | None | object = ...,
    chunks: tuple[object, ...] | None = None,
):
    m = module()
    if content_length is ...:
        content_length = len(body)
    return m.CloudflareHttpResponse(
        status_code=status_code,
        content_type=content_type,
        content_length=content_length,
        content_encoding=content_encoding,
        body_chunks=(body,) if chunks is None else chunks,
    )


class ScriptedTransport:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def post_multipart(self, **kwargs: object):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("unexpected Cloudflare transport call")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def successful_transport() -> ScriptedTransport:
    responses = [
        http_response(response_json(png_bytes(color=(index, index + 1, index + 2, 255))))
        for index in (10, 20, 30, 40)
    ]
    return ScriptedTransport(responses)


def execute(transport: ScriptedTransport, **overrides: object):
    m = module()
    session, intent, ledger, reservation = image_context()
    arguments: dict[str, object] = {
        "session": session,
        "intent": intent,
        "usage_ledger": ledger,
        "usage_reservation": reservation,
        "account_id": ACCOUNT_ID,
        "api_token": API_TOKEN,
        "transport": transport,
        "now": lambda: NOW + timedelta(seconds=6),
    }
    arguments.update(overrides)
    return m.execute_cloudflare_image_set(**arguments), ledger, session


def test_execution_posts_exact_four_request_sequence_and_records_image_review() -> None:
    m = module()
    transport = successful_transport()
    result, ledger, original_session = execute(transport)

    assert [call["request"].angle for call in transport.calls] == list(IMAGE_ANGLES)
    assert len(transport.calls) == 4
    assert all(
        call["url"]
        == (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-2-klein-4b"
        )
        for call in transport.calls
    )
    assert all(call["api_token"] == API_TOKEN for call in transport.calls)
    assert all(call["allow_redirects"] is False for call in transport.calls)
    assert all(call["accept_encoding"] == "identity" for call in transport.calls)
    assert all(
        call["maximum_response_bytes"] == m.CLOUDFLARE_MAX_RESPONSE_BYTES
        for call in transport.calls
    )

    assert result.session.state == "image_review"
    assert result.session.revision == original_session.revision + 1
    assert result.session.active_image_reservation_id is None
    assert result.session.image_set_sha256 == result.image_set_sha256
    assert result.session.image_request_metadata_sha256 == result.request_metadata_sha256
    assert result.usage_reservation.status == "succeeded"
    assert ledger.snapshot().reservations[0] == result.usage_reservation
    assert tuple(image.angle for image in result.images) == IMAGE_ANGLES
    assert all(image.width == 512 and image.height == 512 for image in result.images)


def test_front_output_is_resized_only_for_three_shared_reference_inputs() -> None:
    transport = successful_transport()
    result, _ledger, _session = execute(transport)

    assert result.request_set.requests[0].reference_image is None
    references = [request.reference_image for request in result.request_set.requests[1:]]
    assert all(reference is not None for reference in references)
    assert references[0] == references[1] == references[2]
    assert references[0].width == 511
    assert references[0].height == 511
    with Image.open(BytesIO(references[0].body), formats=("PNG",)) as image:
        assert image.size == (511, 511)
        assert image.mode == "RGB"

    assert result.images[0].width == 512
    assert result.images[0].height == 512
    assert result.images[0].body != references[0].body
    assert transport.calls[0]["request"] == result.request_set.requests[0]
    assert [call["request"] for call in transport.calls[1:]] == list(
        result.request_set.requests[1:]
    )


def test_artifacts_are_deterministic_metadata_free_rgb_pngs() -> None:
    m = module()
    request = build_cloudflare_front_request(
        intent=normalized_intent(),
        preimage_plan_sha256="a" * 64,
        attempt=1,
    )
    raw = png_bytes(metadata="must-not-survive")
    response = http_response(response_json(raw))

    first = m.parse_cloudflare_image_response(request=request, response=response)
    second = m.parse_cloudflare_image_response(request=request, response=response)

    assert first == second
    assert first.body == second.body
    assert first.body != raw
    assert b"must-not-survive" not in first.body
    assert first.sha256 == hashlib.sha256(first.body).hexdigest()
    with Image.open(BytesIO(first.body), formats=("PNG",)) as image:
        assert image.mode == "RGB"
        assert image.size == (512, 512)
        assert image.info == {}


@pytest.mark.parametrize("image_format", ["JPEG", "WEBP"])
def test_supported_provider_images_are_normalized_to_rgb_png(image_format: str) -> None:
    m = module()
    request = build_cloudflare_front_request(
        intent=normalized_intent(),
        preimage_plan_sha256="a" * 64,
        attempt=1,
    )
    raw = raster_bytes(image_format)

    artifact = m.parse_cloudflare_image_response(
        request=request,
        response=http_response(response_json(raw)),
    )

    assert artifact.content_type == "image/png"
    assert artifact.body != raw
    assert artifact.sha256 == hashlib.sha256(artifact.body).hexdigest()
    with Image.open(BytesIO(artifact.body), formats=("PNG",)) as image:
        assert image.format == "PNG"
        assert image.mode == "RGB"
        assert image.size == (512, 512)
        assert image.info == {}


def test_execution_result_never_serializes_image_bytes_or_credentials() -> None:
    transport = successful_transport()
    result, _ledger, _session = execute(transport)

    serialized = result.model_dump_json()
    rendered = repr(result)
    assert API_TOKEN not in serialized
    assert API_TOKEN not in rendered
    assert ACCOUNT_ID not in serialized
    assert ACCOUNT_ID not in rendered
    for image in result.images:
        assert base64.b64encode(image.body).decode("ascii") not in serialized
        assert image.sha256 in serialized
    assert "body" not in serialized


def test_image_set_digest_binds_ordered_artifact_metadata() -> None:
    m = module()
    result, _ledger, _session = execute(successful_transport())
    assert m.cloudflare_image_set_sha256(result.images) == result.image_set_sha256

    changed = list(result.images)
    changed[0] = changed[0].model_copy(update={"sha256": "f" * 64})
    with pytest.raises(m.CloudflareImageError, match="Cloudflare image artifact is invalid"):
        m.cloudflare_image_set_sha256(tuple(changed))


def test_second_provider_failure_returns_no_partial_set_and_charges_attempt() -> None:
    m = module()
    marker = "provider-secret-detail"
    transport = ScriptedTransport(
        [
            http_response(response_json(png_bytes())),
            RuntimeError(marker),
            http_response(response_json(png_bytes())),
        ]
    )
    session, intent, ledger, reservation = image_context()

    with pytest.raises(m.CloudflareTransportError) as raised:
        m.execute_cloudflare_image_set(
            session=session,
            intent=intent,
            usage_ledger=ledger,
            usage_reservation=reservation,
            account_id=ACCOUNT_ID,
            api_token=API_TOKEN,
            transport=transport,
            now=lambda: NOW + timedelta(seconds=6),
        )

    assert str(raised.value) == "Cloudflare HTTP transport failed"
    assert marker not in str(raised.value)
    assert API_TOKEN not in str(raised.value)
    assert len(transport.calls) == 2
    assert ledger.snapshot().reservations[0].status == "failed"
    assert session.state == "image_generating"
    assert session.active_image_reservation_id == reservation.reservation_id


def test_invalid_response_charges_started_attempt_with_fixed_error() -> None:
    m = module()
    transport = ScriptedTransport([http_response(b'{"provider":"raw detail"}')])
    session, intent, ledger, reservation = image_context()

    with pytest.raises(m.CloudflareResponseContractError) as raised:
        m.execute_cloudflare_image_set(
            session=session,
            intent=intent,
            usage_ledger=ledger,
            usage_reservation=reservation,
            account_id=ACCOUNT_ID,
            api_token=API_TOKEN,
            transport=transport,
            now=lambda: NOW + timedelta(seconds=6),
        )

    assert str(raised.value) == "Cloudflare response did not match the image contract"
    assert "raw detail" not in str(raised.value)
    assert ledger.snapshot().reservations[0].status == "failed"


def test_invalid_execution_binding_does_not_mutate_the_ledger() -> None:
    m = module()
    session, intent, ledger, reservation = image_context()
    tampered = session.model_copy(update={"active_image_reservation_id": "Z" * 32})

    with pytest.raises(
        m.CloudflareExecutionError,
        match="Cloudflare image execution request is invalid",
    ):
        m.execute_cloudflare_image_set(
            session=tampered,
            intent=intent,
            usage_ledger=ledger,
            usage_reservation=reservation,
            account_id=ACCOUNT_ID,
            api_token=API_TOKEN,
            transport=successful_transport(),
            now=lambda: NOW + timedelta(seconds=6),
        )

    assert ledger.snapshot().reservations[0].status == "started"


@pytest.mark.parametrize(
    "field,value",
    [
        ("account_id", "not-an-account"),
        ("account_id", "A" * 32),
        ("account_id", "0" * 31),
        ("api_token", ""),
        ("api_token", "contains space"),
        ("api_token", "line\nbreak"),
    ],
)
def test_invalid_server_credentials_fail_closed_and_finish_attempt(field: str, value: str) -> None:
    m = module()
    session, intent, ledger, reservation = image_context()
    arguments = {"account_id": ACCOUNT_ID, "api_token": API_TOKEN}
    arguments[field] = value

    with pytest.raises(
        m.CloudflareExecutionError,
        match="Cloudflare image execution request is invalid",
    ):
        m.execute_cloudflare_image_set(
            session=session,
            intent=intent,
            usage_ledger=ledger,
            usage_reservation=reservation,
            transport=successful_transport(),
            now=lambda: NOW + timedelta(seconds=6),
            **arguments,
        )

    assert ledger.snapshot().reservations[0].status == "failed"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"result": {"image": "AA=="}, "success": False, "errors": [], "messages": []},
        {
            "result": {"image": "AA=="},
            "success": True,
            "errors": [{"message": "raw"}],
            "messages": [],
        },
        {
            "result": {"image": "AA=="},
            "success": True,
            "errors": [],
            "messages": ["raw"],
        },
        {"result": "AA==", "success": True, "errors": [], "messages": []},
        {
            "result": {"image": "AA==", "extra": 1},
            "success": True,
            "errors": [],
            "messages": [],
        },
        {
            "result": {"image": "AA=="},
            "success": True,
            "errors": [],
            "messages": [],
            "extra": 1,
        },
    ],
)
def test_response_requires_exact_success_envelope(payload: dict[str, object]) -> None:
    m = module()
    request = build_cloudflare_front_request(
        intent=normalized_intent(),
        preimage_plan_sha256="a" * 64,
        attempt=1,
    )
    body = json.dumps(payload, separators=(",", ":")).encode()

    with pytest.raises(
        m.CloudflareResponseContractError,
        match="Cloudflare response did not match the image contract",
    ):
        m.parse_cloudflare_image_response(
            request=request,
            response=http_response(body),
        )


@pytest.mark.parametrize(
    "body",
    [
        b"not-json",
        b"\xff",
        b'{"result":{"image":"AA=="},"result":{"image":"AA=="},'
        b'"success":true,"errors":[],"messages":[]}',
        b'{"result":{"image":NaN},"success":true,"errors":[],"messages":[]}',
    ],
)
def test_response_rejects_invalid_utf8_json_duplicate_keys_and_nonfinite(body: bytes) -> None:
    m = module()
    request = build_cloudflare_front_request(
        intent=normalized_intent(),
        preimage_plan_sha256="a" * 64,
        attempt=1,
    )

    with pytest.raises(m.CloudflareResponseContractError):
        m.parse_cloudflare_image_response(
            request=request,
            response=http_response(body),
        )


@pytest.mark.parametrize(
    "encoded",
    [
        "data:image/png;base64,AA==",
        "AA==\n",
        "AA=A",
        "A===",
        "あ",
    ],
)
def test_response_rejects_noncanonical_base64(encoded: str) -> None:
    m = module()
    request = build_cloudflare_front_request(
        intent=normalized_intent(),
        preimage_plan_sha256="a" * 64,
        attempt=1,
    )
    body = json.dumps(
        {"result": {"image": encoded}, "success": True, "errors": [], "messages": []},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()

    with pytest.raises(m.CloudflareResponseContractError):
        m.parse_cloudflare_image_response(
            request=request,
            response=http_response(body),
        )


@pytest.mark.parametrize(
    "body",
    [
        b"not-an-image",
        raster_bytes("BMP"),
        png_bytes(width=511),
        raster_bytes("JPEG", width=511),
        raster_bytes("WEBP", height=511),
        raster_bytes("JPEG")[: len(raster_bytes("JPEG")) // 2],
        raster_bytes("WEBP")[: len(raster_bytes("WEBP")) // 2],
        animated_png_bytes(),
        b"x" * (2 * 1024 * 1024 + 1),
    ],
)
def test_response_rejects_unsupported_wrong_size_animation_and_oversize(body: bytes) -> None:
    m = module()
    request = build_cloudflare_front_request(
        intent=normalized_intent(),
        preimage_plan_sha256="a" * 64,
        attempt=1,
    )

    with pytest.raises(m.CloudflareImageError, match="Cloudflare image content is invalid"):
        m.parse_cloudflare_image_response(
            request=request,
            response=http_response(response_json(body)),
        )


def test_response_rejects_decompression_bomb_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    m = module()
    request = build_cloudflare_front_request(
        intent=normalized_intent(),
        preimage_plan_sha256="a" * 64,
        attempt=1,
    )
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1)

    with pytest.raises(m.CloudflareImageError, match="Cloudflare image content is invalid"):
        m.parse_cloudflare_image_response(
            request=request,
            response=http_response(response_json(raster_bytes("JPEG"))),
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"status_code": 302},
        {"status_code": 500},
        {"content_type": None},
        {"content_type": "text/plain"},
        {"content_type": "application/json; charset=shift_jis"},
        {"content_encoding": "gzip"},
        {"content_length": -1},
        {"content_length": 4 * 1024 * 1024 + 1},
    ],
)
def test_http_response_contract_rejects_status_headers_and_declared_size(
    overrides: dict[str, object],
) -> None:
    m = module()
    request = build_cloudflare_front_request(
        intent=normalized_intent(),
        preimage_plan_sha256="a" * 64,
        attempt=1,
    )
    body = response_json(png_bytes())

    with pytest.raises(m.CloudflareExecutionError):
        m.parse_cloudflare_image_response(
            request=request,
            response=http_response(body, **overrides),
        )


def test_http_response_contract_checks_measured_and_declared_lengths() -> None:
    m = module()
    request = build_cloudflare_front_request(
        intent=normalized_intent(),
        preimage_plan_sha256="a" * 64,
        attempt=1,
    )
    body = response_json(png_bytes())

    for response in (
        http_response(body, content_length=len(body) + 1),
        http_response(
            b"",
            content_length=None,
            chunks=(b"x" * m.CLOUDFLARE_MAX_RESPONSE_BYTES, b"x"),
        ),
        http_response(body, chunks=(body, "not-bytes")),
    ):
        with pytest.raises(m.CloudflareResponseContractError):
            m.parse_cloudflare_image_response(request=request, response=response)


class RecordingRaw:
    def __init__(
        self,
        chunks: tuple[object, ...],
        *,
        error: Exception | None = None,
    ) -> None:
        self.chunks = chunks
        self.error = error
        self.stream_calls: list[tuple[int, bool]] = []
        self.yielded_chunks = 0
        self.close_calls = 0
        self.release_calls = 0

    def stream(self, chunk_size: int, *, decode_content: bool):
        self.stream_calls.append((chunk_size, decode_content))
        for chunk in self.chunks:
            self.yielded_chunks += 1
            yield chunk
        if self.error is not None:
            raise self.error

    def close(self) -> None:
        self.close_calls += 1

    def release_conn(self) -> None:
        self.release_calls += 1


def requests_response(
    chunks: tuple[object, ...],
    *,
    status_code: int = 200,
    content_type: str | None = "application/json; charset=utf-8",
    content_encoding: str | None = "identity",
    content_length: str | None = None,
    stream_error: Exception | None = None,
) -> tuple[requests.Response, RecordingRaw]:
    response = requests.Response()
    response.status_code = status_code
    headers: dict[str, str] = {}
    if content_type is not None:
        headers["Content-Type"] = content_type
    if content_encoding is not None:
        headers["Content-Encoding"] = content_encoding
    if content_length is not None:
        headers["Content-Length"] = content_length
    response.headers = CaseInsensitiveDict(headers)
    raw = RecordingRaw(chunks, error=stream_error)
    response.raw = raw
    response._content = False
    response._content_consumed = False
    return response, raw


class RecordingSession:
    def __init__(
        self,
        response: object | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.trust_env = True
        self.headers = {"User-Agent": "unapproved-default"}
        self.cookies = RequestsCookieJar()
        self.cookies.set("unapproved-cookie", "value")
        self.proxies = {"https": "http://proxy.invalid"}
        self.auth: object = object()
        self.mounts: list[tuple[str, HTTPAdapter]] = []
        self.request_calls: list[dict[str, object]] = []
        self.close_calls = 0

    def mount(self, prefix: str, adapter: HTTPAdapter) -> None:
        self.mounts.append((prefix, adapter))

    def request(self, **kwargs: object) -> object:
        self.request_calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response

    def close(self) -> None:
        self.close_calls += 1


class CapturingSession(requests.Session):
    def __init__(self, response: requests.Response) -> None:
        super().__init__()
        self.response = response
        self.prepared_request: requests.PreparedRequest | None = None
        self.send_options: dict[str, object] | None = None
        self.close_calls = 0

    def send(self, request: requests.PreparedRequest, **kwargs: object) -> requests.Response:
        self.prepared_request = request
        self.send_options = kwargs
        return self.response

    def close(self) -> None:
        self.close_calls += 1
        super().close()


def transport_arguments(request, **overrides: object) -> dict[str, object]:
    m = module()
    arguments: dict[str, object] = {
        "request": request,
        "url": m.cloudflare_endpoint(ACCOUNT_ID),
        "api_token": API_TOKEN,
        "timeout_seconds": m.CLOUDFLARE_REQUEST_TIMEOUT_SECONDS,
        "allow_redirects": False,
        "accept_encoding": "identity",
        "maximum_response_bytes": m.CLOUDFLARE_MAX_RESPONSE_BYTES,
    }
    arguments.update(overrides)
    return arguments


def call_requests_transport(session: RecordingSession, request, **overrides: object):
    m = module()
    with patch(f"{MODULE_NAME}.requests.Session", return_value=session) as factory:
        result = m.RequestsCloudflareTransport().post_multipart(
            **transport_arguments(request, **overrides)
        )
    return result, factory


def test_requests_transport_isolated_session_and_exact_prompt_only_multipart() -> None:
    m = module()
    body = b"{}"
    response, raw = requests_response((body,), content_length=str(len(body)))
    session = RecordingSession(response)
    request = build_cloudflare_front_request(
        intent=normalized_intent(),
        preimage_plan_sha256="a" * 64,
        attempt=1,
    )

    projected, factory = call_requests_transport(session, request)

    factory.assert_called_once_with()
    assert session.trust_env is False
    assert session.headers == {}
    assert len(session.cookies) == 0
    assert session.proxies == {}
    assert session.auth is None
    assert [prefix for prefix, _adapter in session.mounts] == ["http://", "https://"]
    assert all(adapter.max_retries.total == 0 for _prefix, adapter in session.mounts)
    assert session.close_calls == 1
    assert raw.close_calls >= 1
    assert projected.body_chunks == (body,)

    sent = session.request_calls[0]
    assert sent["method"] == "POST"
    assert sent["url"] == m.cloudflare_endpoint(ACCOUNT_ID)
    assert sent["headers"] == {
        "Accept": "application/json",
        "Accept-Encoding": "identity",
        "Authorization": f"Bearer {API_TOKEN}",
    }
    assert "Content-Type" not in sent["headers"]
    assert sent["timeout"] == (
        m.CLOUDFLARE_REQUEST_TIMEOUT_SECONDS,
        m.CLOUDFLARE_REQUEST_TIMEOUT_SECONDS,
    )
    assert sent["allow_redirects"] is False
    assert sent["stream"] is True
    assert sent["verify"] is True
    assert sent["proxies"] == {}
    assert "data" not in sent
    assert "json" not in sent
    assert sent["files"] == [
        (field.name, (None, field.value)) for field in request.multipart_form().text_fields
    ]


def test_requests_transport_builds_real_multipart_boundary_for_prompt_and_reference() -> None:
    m = module()
    reference = png_bytes(width=511, height=511)
    request_set = build_cloudflare_request_set(
        intent=normalized_intent(),
        preimage_plan_sha256="a" * 64,
        attempt=1,
        front_reference_png=reference,
    )

    for request in (request_set.requests[0], request_set.requests[1]):
        response, _raw = requests_response((b"{}",), content_length="2")
        session = CapturingSession(response)
        with patch(f"{MODULE_NAME}.requests.Session", return_value=session):
            m.RequestsCloudflareTransport().post_multipart(**transport_arguments(request))

        prepared = session.prepared_request
        assert prepared is not None
        content_type = prepared.headers["Content-Type"]
        assert content_type.startswith("multipart/form-data; boundary=")
        assert prepared.headers["Authorization"] == f"Bearer {API_TOKEN}"
        assert isinstance(prepared.body, bytes)
        assert b'name="prompt"' in prepared.body
        assert b'name="width"' in prepared.body
        assert b'name="height"' in prepared.body
        assert b'name="seed"' in prepared.body
        if request.reference_image is None:
            assert b'name="input_image_0"' not in prepared.body
        else:
            assert b'name="input_image_0"; filename="front-reference.png"' in prepared.body
            assert b"Content-Type: image/png" in prepared.body
            assert reference in prepared.body


def test_requests_transport_never_reads_rejected_response_body() -> None:
    response, raw = requests_response(
        (b"provider secret",),
        status_code=302,
        content_length=str(len(b"provider secret")),
    )
    session = RecordingSession(response)
    request = build_cloudflare_front_request(
        intent=normalized_intent(),
        preimage_plan_sha256="a" * 64,
        attempt=1,
    )

    projected, _factory = call_requests_transport(session, request)

    assert projected.status_code == 302
    assert projected.body_chunks == ()
    assert raw.yielded_chunks == 0


def test_requests_transport_closes_session_on_sanitized_timeout() -> None:
    m = module()
    marker = f"leaked {API_TOKEN}"
    session = RecordingSession(error=requests.Timeout(marker))
    request = build_cloudflare_front_request(
        intent=normalized_intent(),
        preimage_plan_sha256="a" * 64,
        attempt=1,
    )

    with pytest.raises(m.CloudflareTransportError) as raised:
        call_requests_transport(session, request)

    assert str(raised.value) == "Cloudflare HTTP transport failed"
    assert marker not in str(raised.value)
    assert session.close_calls == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"url": "https://example.test/client/v4/accounts/" + ACCOUNT_ID},
        {"url": "http://api.cloudflare.com/client/v4/accounts/" + ACCOUNT_ID},
        {"url": "https://api.cloudflare.com:444/client/v4/accounts/" + ACCOUNT_ID},
        {"url": "https://api.cloudflare.com/client/v4/accounts/" + ACCOUNT_ID + "/ai/run"},
        {"api_token": ""},
        {"api_token": "bad token"},
        {"timeout_seconds": 1},
        {"allow_redirects": True},
        {"accept_encoding": "gzip"},
        {"maximum_response_bytes": 1},
    ],
)
def test_requests_transport_rejects_contract_changes_before_session_creation(
    overrides: dict[str, object],
) -> None:
    m = module()
    request = build_cloudflare_front_request(
        intent=normalized_intent(),
        preimage_plan_sha256="a" * 64,
        attempt=1,
    )
    with patch(f"{MODULE_NAME}.requests.Session") as factory:
        with pytest.raises(
            m.CloudflareExecutionError,
            match="Cloudflare image execution request is invalid",
        ):
            m.RequestsCloudflareTransport().post_multipart(
                **transport_arguments(request, **overrides)
            )
    factory.assert_not_called()


def test_request_object_tampering_is_revalidated_before_transport() -> None:
    m = module()
    request = build_cloudflare_front_request(
        intent=normalized_intent(),
        preimage_plan_sha256="a" * 64,
        attempt=1,
    )
    tampered = request.model_copy(update={"width": 1024})
    with patch(f"{MODULE_NAME}.requests.Session") as factory:
        with pytest.raises(m.CloudflareExecutionError):
            m.RequestsCloudflareTransport().post_multipart(**transport_arguments(tampered))
    factory.assert_not_called()


def test_endpoint_accepts_only_lowercase_32_hex_account_id() -> None:
    m = module()
    assert m.cloudflare_endpoint(ACCOUNT_ID).endswith(
        f"/accounts/{ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-2-klein-4b"
    )
    for invalid in ("", "0" * 31, "0" * 33, "G" * 32, "A" * 32, 123):
        with pytest.raises(
            m.CloudflareExecutionError,
            match="Cloudflare image execution request is invalid",
        ):
            m.cloudflare_endpoint(invalid)


def test_dataclass_replace_cannot_turn_response_limit_into_a_valid_large_body() -> None:
    m = module()
    request = build_cloudflare_front_request(
        intent=normalized_intent(),
        preimage_plan_sha256="a" * 64,
        attempt=1,
    )
    valid = http_response(response_json(png_bytes()))
    changed = replace(
        valid,
        content_length=m.CLOUDFLARE_MAX_RESPONSE_BYTES + 1,
    )
    with pytest.raises(m.CloudflareResponseContractError):
        m.parse_cloudflare_image_response(request=request, response=changed)
