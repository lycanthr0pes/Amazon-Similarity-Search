from __future__ import annotations

import base64
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from io import BytesIO
import json

from PIL import Image
import pytest
import requests

import src.search_v2.counterfactual_cloudflare_http as counterfactual_http
from src.search_v2.counterfactual_cloudflare_http import (
    CLOUDFLARE_MAX_RESPONSE_BYTES,
)
from src.search_v2.counterfactual_cloudflare_http import (
    CounterfactualCloudflareExecutionError,
)
from src.search_v2.counterfactual_cloudflare_http import CloudflareHttpResponse
from src.search_v2.counterfactual_cloudflare_http import (
    execute_counterfactual_cloudflare_reference_set,
)
from src.search_v2.counterfactual_cloudflare_http import (
    counterfactual_cloudflare_reference_set_sha256,
)
from src.search_v2.counterfactual_cloudflare_request import (
    build_counterfactual_cloudflare_desired_request,
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


NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
ACCOUNT_ID = "0123456789abcdef0123456789abcdef"
API_TOKEN = "fixture-cloudflare-api-token"
PLAN_SHA256 = "a" * 64


def intent_and_conditions(count: int = 2):
    source = "黒いメッシュ背もたれでヘッドレスト付きのオフィスチェア"
    draft = SearchIntentDraft.model_validate(
        {
            "product_name_ja": "オフィスチェア",
            "product_name_en": "office chair",
            "category_ja": "椅子",
            "category_en": "chair",
            "required_terms_ja": [],
            "required_terms_en": [],
            "preferred_terms_ja": [],
            "preferred_terms_en": [],
            "negative_terms_ja": [],
            "negative_terms_en": [],
            "color_ja": "黒",
            "color_en": "black",
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
    )
    provenance = build_intent_provenance(
        source_input=source,
        prompt=b"prompt",
        schema=b"schema",
        response=b"response",
    )
    intent = normalize_search_intent(source, draft, provenance=provenance)
    drafts = (
        VisualConditionDraft(
            source_phrase="黒い",
            strength="required",
            attribute_key="色",
        ),
        VisualConditionDraft(
            source_phrase="ヘッドレスト付き",
            strength="required",
            attribute_key=None,
        ),
        VisualConditionDraft(
            source_phrase="メッシュ背もたれ",
            strength="preferred",
            attribute_key=None,
        ),
    )
    conditions = build_visual_condition_set(source_input=source, drafts=drafts[:count])
    return intent, conditions


def png_bytes(index: int) -> bytes:
    output = BytesIO()
    Image.new("RGB", (512, 512), (index, index + 1, index + 2)).save(output, format="PNG")
    return output.getvalue()


def response(index: int) -> CloudflareHttpResponse:
    body = json.dumps(
        {
            "result": {"image": base64.b64encode(png_bytes(index)).decode("ascii")},
            "success": True,
            "errors": [],
            "messages": [],
        },
        separators=(",", ":"),
    ).encode()
    return CloudflareHttpResponse(
        status_code=200,
        content_type="application/json; charset=utf-8",
        content_length=len(body),
        content_encoding="identity",
        body_chunks=(body,),
    )


class ScriptedTransport:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def post_multipart(self, **kwargs: object):
        self.calls.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def context(count: int = 2, *, reserved_calls: int | None = None):
    intent, conditions = intent_and_conditions(count)
    calls = 1 + count if reserved_calls is None else reserved_calls
    limit = UsageAmount(calls=8, tokens=0, cost_microusd=100_000)
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
            operation="counterfactual_reference_set",
            owner_id="owner-1",
            session_id="session-1",
            binding_sha256=PLAN_SHA256,
            amount=UsageAmount(calls=calls, tokens=0, cost_microusd=calls * 1_000),
            pricing_policy_sha256="b" * 64,
        ),
        now=NOW,
    )
    started = ledger.start(
        reserved.reservation_id,
        owner_id="owner-1",
        session_id="session-1",
        now=NOW + timedelta(seconds=1),
    )
    return intent, conditions, ledger, started


@pytest.mark.parametrize("count", [1, 2, 3])
def test_execution_makes_exact_one_plus_n_calls_and_finishes_usage(count: int) -> None:
    intent, conditions, ledger, reservation = context(count)
    transport = ScriptedTransport([response(index) for index in range(10, 11 + count)])

    result = execute_counterfactual_cloudflare_reference_set(
        intent=intent,
        condition_set=conditions,
        preimage_plan_sha256=PLAN_SHA256,
        usage_ledger=ledger,
        usage_reservation=reservation,
        account_id=ACCOUNT_ID,
        api_token=API_TOKEN,
        transport=transport,
        now=lambda: NOW + timedelta(seconds=2),
    )

    assert len(transport.calls) == 1 + count
    assert result.request_set.call_count == 1 + count
    assert tuple(item.target for item in result.images) == (
        "desired",
        *("counterfactual" for _ in range(count)),
    )
    assert result.usage_reservation.status == "succeeded"
    assert ledger.snapshot().reservations[0] == result.usage_reservation
    assert all(call["allow_redirects"] is False for call in transport.calls)
    assert all(
        call["maximum_response_bytes"] == CLOUDFLARE_MAX_RESPONSE_BYTES for call in transport.calls
    )


def test_execution_never_serializes_image_bodies_or_credentials() -> None:
    intent, conditions, ledger, reservation = context(1)
    transport = ScriptedTransport([response(10), response(20)])

    result = execute_counterfactual_cloudflare_reference_set(
        intent=intent,
        condition_set=conditions,
        preimage_plan_sha256=PLAN_SHA256,
        usage_ledger=ledger,
        usage_reservation=reservation,
        account_id=ACCOUNT_ID,
        api_token=API_TOKEN,
        transport=transport,
        now=lambda: NOW + timedelta(seconds=2),
    )

    serialized = result.model_dump_json()
    assert API_TOKEN not in serialized
    assert base64.b64encode(result.images[0].body).decode() not in serialized
    assert result.reference_set_sha256 == counterfactual_cloudflare_reference_set_sha256(
        result.images
    )


def test_partial_failure_is_not_retried_and_marks_the_whole_reservation_failed() -> None:
    intent, conditions, ledger, reservation = context(2)
    transport = ScriptedTransport([response(10), RuntimeError("provider failed")])

    with pytest.raises(CounterfactualCloudflareExecutionError):
        execute_counterfactual_cloudflare_reference_set(
            intent=intent,
            condition_set=conditions,
            preimage_plan_sha256=PLAN_SHA256,
            usage_ledger=ledger,
            usage_reservation=reservation,
            account_id=ACCOUNT_ID,
            api_token=API_TOKEN,
            transport=transport,
            now=lambda: NOW + timedelta(seconds=2),
        )

    assert len(transport.calls) == 2
    assert ledger.snapshot().reservations[0].status == "failed"


def test_execution_rejects_over_reserved_call_count_before_transport() -> None:
    intent, conditions, ledger, reservation = context(1, reserved_calls=4)
    transport = ScriptedTransport([response(10), response(20)])

    with pytest.raises(CounterfactualCloudflareExecutionError, match="invalid"):
        execute_counterfactual_cloudflare_reference_set(
            intent=intent,
            condition_set=conditions,
            preimage_plan_sha256=PLAN_SHA256,
            usage_ledger=ledger,
            usage_reservation=reservation,
            account_id=ACCOUNT_ID,
            api_token=API_TOKEN,
            transport=transport,
            now=lambda: NOW + timedelta(seconds=2),
        )

    assert transport.calls == []


def test_production_transport_accepts_only_the_exact_cloudflare_endpoint(monkeypatch) -> None:
    intent, conditions = intent_and_conditions(1)
    request = build_counterfactual_cloudflare_desired_request(
        intent=intent,
        condition_set=conditions,
        preimage_plan_sha256=PLAN_SHA256,
    )
    projected = response(10)

    def request_without_network(self, **kwargs):
        del self
        assert kwargs["url"].endswith("/@cf/black-forest-labs/flux-2-klein-4b")
        return requests.Response()

    monkeypatch.setattr(requests.Session, "request", request_without_network)
    monkeypatch.setattr(
        counterfactual_http, "_project_response", lambda *_args, **_kwargs: projected
    )
    monkeypatch.setattr(counterfactual_http, "_close_response", lambda _response: None)

    actual = counterfactual_http.RequestsCounterfactualCloudflareTransport().post_multipart(
        request=request,
        url=(
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-2-klein-4b"
        ),
        api_token=API_TOKEN,
        timeout_seconds=120,
        allow_redirects=False,
        accept_encoding="identity",
        maximum_response_bytes=CLOUDFLARE_MAX_RESPONSE_BYTES,
    )

    assert actual is projected


def test_http_failure_preserves_status_without_reading_provider_body(monkeypatch) -> None:
    intent, conditions = intent_and_conditions(1)
    request = build_counterfactual_cloudflare_desired_request(
        intent=intent, condition_set=conditions, preimage_plan_sha256=PLAN_SHA256
    )
    calls = []
    closed = []

    def request_without_network(self, **kwargs):
        del self, kwargs
        calls.append("request")
        result = requests.Response()
        result.status_code = 503
        return result

    def forbidden_projection(*_args, **_kwargs):
        pytest.fail("An HTTP error must not read the private provider body")

    monkeypatch.setattr(requests.Session, "request", request_without_network)
    monkeypatch.setattr(counterfactual_http, "_project_response", forbidden_projection)
    monkeypatch.setattr(
        counterfactual_http, "_close_response", lambda _response: closed.append(True)
    )
    with pytest.raises(CounterfactualCloudflareExecutionError) as caught:
        counterfactual_http.execute_counterfactual_desired_image(
            request=request,
            account_id=ACCOUNT_ID,
            api_token=API_TOKEN,
            transport=counterfactual_http.RequestsCounterfactualCloudflareTransport(),
        )
    assert caught.value.diagnostic.model_dump() == {
        "stage": "http_status",
        "http_status_code": 503,
        "provider_error_code": None,
    }
    assert calls == ["request"] and closed == [True]


@pytest.mark.parametrize(
    "payload",
    [
        {"stage": "private-provider-message"},
        {"stage": "http_status", "http_status_code": 200},
        {"stage": "http_status", "http_status_code": "503"},
        {"stage": "transport", "http_status_code": 503},
        {"stage": "transport", "body": "private-response"},
    ],
)
def test_failure_diagnostic_rejects_unbounded_provider_fields(payload) -> None:
    with pytest.raises(ValueError):
        counterfactual_http.CloudflareFailureDiagnostic.model_validate(payload)


@pytest.mark.parametrize(
    "body, expected_code",
    [
        (b'{"errors":[{"code":3036,"message":"private-provider-data"}]}', 3036),
        (b'{"errors":[{"code":3040,"message":"private-provider-data"}]}', 3040),
        (b'{"errors":[{"code":"3036"}]}', None),
        (b'{"errors":[{"code":9999}]}', None),
        (b'{"errors":[{"code":3036,"code":3040}]}', None),
        (b'{"errors":[{"code":3036},{"code":3040}]}', None),
        (b"private-provider-data", None),
        (b'{"errors":[{"code":3036}],"message":"' + b"x" * 8192 + b'"}', None),
    ],
)
def test_429_retains_only_known_error_code(monkeypatch, body, expected_code) -> None:
    intent, conditions = intent_and_conditions(1)
    request = build_counterfactual_cloudflare_desired_request(
        intent=intent, condition_set=conditions, preimage_plan_sha256=PLAN_SHA256
    )
    calls, closed, read_sizes = [], [], []

    def request_without_network(self, **kwargs):
        del self, kwargs
        calls.append(True)
        response = requests.Response()
        response.status_code = 429
        response.headers["Content-Type"] = "application/json"

        def chunks(chunk_size):
            for offset in range(0, len(body), chunk_size):
                chunk = body[offset : offset + chunk_size]
                read_sizes.append(len(chunk))
                yield chunk

        response.iter_content = chunks
        return response

    monkeypatch.setattr(requests.Session, "request", request_without_network)
    monkeypatch.setattr(counterfactual_http, "_close_response", lambda _: closed.append(True))
    with pytest.raises(CounterfactualCloudflareExecutionError) as caught:
        counterfactual_http.execute_counterfactual_desired_image(
            request=request,
            account_id=ACCOUNT_ID,
            api_token=API_TOKEN,
            transport=counterfactual_http.RequestsCounterfactualCloudflareTransport(),
        )
    diagnostic = caught.value.diagnostic.model_dump()
    assert "provider_error_code" in diagnostic
    assert diagnostic["provider_error_code"] == expected_code
    assert diagnostic["http_status_code"] == 429
    assert diagnostic["stage"] == "http_status"
    assert "private-provider-data" not in json.dumps(diagnostic)
    assert calls == [True] and closed == [True]
    assert sum(read_sizes) <= 8192 + 1024
