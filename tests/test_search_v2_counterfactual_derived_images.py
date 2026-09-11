from __future__ import annotations

from datetime import timedelta

from pydantic import ValidationError
import pytest

import src.search_v2.counterfactual_cloudflare_http as image_http
from src.search_v2.counterfactual_cloudflare_request import (
    build_counterfactual_cloudflare_desired_request,
)
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import ProviderUsageLimits
from src.search_v2.usage_ledger import UsageAmount
from src.search_v2.usage_ledger import UsageReservationRequest
from test_search_v2_counterfactual_cloudflare_http import ACCOUNT_ID
from test_search_v2_counterfactual_cloudflare_http import API_TOKEN
from test_search_v2_counterfactual_cloudflare_http import NOW
from test_search_v2_counterfactual_cloudflare_http import PLAN_SHA256
from test_search_v2_counterfactual_cloudflare_http import ScriptedTransport
from test_search_v2_counterfactual_cloudflare_http import intent_and_conditions
from test_search_v2_counterfactual_cloudflare_http import response


def derived_context(count: int = 2, *, reserved_calls: int | None = None):
    intent, conditions = intent_and_conditions(count)
    request = build_counterfactual_cloudflare_desired_request(
        intent=intent,
        condition_set=conditions,
        preimage_plan_sha256=PLAN_SHA256,
    )
    desired = image_http._artifact(request, response(10))
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
    calls = count if reserved_calls is None else reserved_calls
    reserved = ledger.reserve(
        UsageReservationRequest(
            provider="cloudflare",
            operation="counterfactual_images",
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
    return {
        "desired_request": request,
        "desired": desired,
        "intent": intent,
        "condition_set": conditions,
        "preimage_plan_sha256": PLAN_SHA256,
        "usage_ledger": ledger,
        "usage_reservation": started,
        "account_id": ACCOUNT_ID,
        "api_token": API_TOKEN,
        "now": lambda: NOW + timedelta(seconds=2),
    }


def test_desired_image_executes_only_the_initial_request() -> None:
    execute = getattr(image_http, "execute_counterfactual_desired_image", None)
    assert callable(execute), "single reference image execution is required"
    context = derived_context(1)
    transport = ScriptedTransport([response(10)])

    actual = execute(
        request=context["desired_request"],
        account_id=ACCOUNT_ID,
        api_token=API_TOKEN,
        transport=transport,
    )

    assert actual == context["desired"]
    assert len(transport.calls) == 1
    assert transport.calls[0]["request"].target == "desired"


@pytest.mark.parametrize("count", [1, 2, 3])
def test_derived_images_reuse_desired_and_charge_only_n_calls(count: int) -> None:
    execute = getattr(image_http, "execute_counterfactual_derived_images", None)
    assert callable(execute), "derived images must reuse the approved reference"
    context = derived_context(count)
    transport = ScriptedTransport([response(index) for index in range(20, 20 + count)])

    actual = execute(**context, transport=transport)

    assert len(transport.calls) == count
    assert all(call["request"].target == "counterfactual" for call in transport.calls)
    assert all(call["request"].reference_image is not None for call in transport.calls)
    assert actual.images[0] == context["desired"]
    assert len(actual.images) == 1 + count
    assert actual.request_set.requests[0] == context["desired_request"]
    assert actual.usage_reservation.amount.calls == count
    assert actual.usage_reservation.status == "succeeded"
    assert context["usage_ledger"].snapshot().reservations[0] == actual.usage_reservation
    assert API_TOKEN not in actual.model_dump_json()


@pytest.mark.parametrize("tamper", ["desired_request", "desired", "call_count"])
def test_derived_images_reject_mismatched_approval_before_transport(tamper: str) -> None:
    execute = getattr(image_http, "execute_counterfactual_derived_images", None)
    assert callable(execute), "derived images must validate the approved reference"
    context = derived_context(1, reserved_calls=2 if tamper == "call_count" else None)
    if tamper == "desired_request":
        context["desired_request"] = context["desired_request"].model_copy(
            update={"prompt": "a different approved product"}
        )
    if tamper == "desired":
        context["desired"] = context["desired"].model_copy(update={"request_sha256": "f" * 64})
    transport = ScriptedTransport([response(20)])

    with pytest.raises(image_http.CounterfactualCloudflareExecutionError):
        execute(**context, transport=transport)

    assert transport.calls == []


def test_derived_partial_failure_retains_desired_and_does_not_retry() -> None:
    execute = getattr(image_http, "execute_counterfactual_derived_images", None)
    assert callable(execute), "derived images require a separate failure boundary"
    context = derived_context(2)
    desired = context["desired"]
    transport = ScriptedTransport([response(20), RuntimeError("provider failed")])

    with pytest.raises(image_http.CounterfactualCloudflareExecutionError):
        execute(**context, transport=transport)

    assert len(transport.calls) == 2
    assert context["desired"] == desired
    assert context["usage_ledger"].snapshot().reservations[0].status == "failed"


def test_completed_derived_reservation_cannot_be_replayed() -> None:
    context = derived_context(1)
    transport = ScriptedTransport([response(20)])
    image_http.execute_counterfactual_derived_images(**context, transport=transport)

    with pytest.raises(image_http.CounterfactualCloudflareExecutionError):
        image_http.execute_counterfactual_derived_images(**context, transport=transport)

    assert len(transport.calls) == 1


def test_initial_generator_rejects_counterfactual_requests_without_posting() -> None:
    context = derived_context(1)
    generated = image_http.execute_counterfactual_derived_images(
        **context,
        transport=ScriptedTransport([response(20)]),
    )
    transport = ScriptedTransport([])

    with pytest.raises(image_http.CounterfactualCloudflareExecutionError):
        image_http.execute_counterfactual_desired_image(
            request=generated.request_set.requests[1],
            account_id=ACCOUNT_ID,
            api_token=API_TOKEN,
            transport=transport,
        )

    assert transport.calls == []


def test_derived_result_rejects_an_image_from_a_different_initial_reference() -> None:
    context = derived_context(1)
    result = image_http.execute_counterfactual_derived_images(
        **context,
        transport=ScriptedTransport([response(20)]),
    )
    changed_image = image_http._artifact(context["desired_request"], response(30))
    forged = result.model_copy(update={"images": (changed_image, result.images[1])})

    with pytest.raises(ValidationError):
        type(result).model_validate(forged)
