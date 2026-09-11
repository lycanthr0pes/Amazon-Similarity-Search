from __future__ import annotations

import ast
import base64
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import importlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path

from PIL import Image
import pytest
from pydantic import ValidationError

from src.search_v2.cloudflare_http import CloudflareHttpResponse
from src.search_v2.counterfactual_image import VisualConditionDraft
from src.search_v2.counterfactual_image import build_visual_condition_set
from src.search_v2.outscraper_http import OutscraperHttpResponse
from src.search_v2.product_normalization import ProductNormalizationProfile
from src.search_v2.provisional_approval_repository import (
    CounterfactualApprovalConflictError,
)
from src.search_v2.provisional_approval_repository import (
    SqliteCounterfactualApprovalRepository,
)
from src.search_v2.provisional_orchestrator import (
    approve_provisional_reference_review,
)
from src.search_v2.provisional_orchestrator import (
    generate_provisional_reference_review,
)
from src.search_v2.provisional_orchestrator import generate_provisional_images
from src.search_v2.state_machine import InMemoryApprovalLedger
from src.search_v2.typed_intent_adapter import typed_requirement_proposal_sha256
from src.search_v2.typed_ranking import TYPED_RANKING_PROFILE_V4
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import ProviderUsageLimits
from src.search_v2.usage_ledger import UsageAmount


MODULE_NAME = "src.search_v2.orchestrator"
ORCHESTRATOR = (
    importlib.import_module(MODULE_NAME) if importlib.util.find_spec(MODULE_NAME) else None
)

NOW = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
SOURCE_INPUT = (
    "Sony WH-1000XM5の黒い軽量ノイズキャンセリング対応ワイヤレスヘッドホン"
    " (black lightweight wireless noise cancelling headphones)を5万円以内で。"
    "中古 used は避けたい。"
)
ACCOUNT_ID = "0123456789abcdef0123456789abcdef"
CLOUDFLARE_TOKEN = "fixture-cloudflare-token"
OUTSCRAPER_KEY = "fixture-outscraper-key"


@pytest.fixture(autouse=True)
def require_orchestration_boundary() -> None:
    assert ORCHESTRATOR is not None, "the offline search orchestration boundary is required"


def module():
    assert ORCHESTRATOR is not None
    return ORCHESTRATOR


class SequenceClock:
    def __init__(self, start: datetime = NOW) -> None:
        self.start = start
        self.offset = 0

    def __call__(self) -> datetime:
        result = self.start + timedelta(seconds=self.offset)
        self.offset += 1
        return result


class BonsaiTransport:
    def __init__(self, response: object | None = None) -> None:
        self.response = response if response is not None else bonsai_response()
        self.calls: list[dict[str, object]] = []

    def post_json(self, **kwargs: object):
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class CloudflareTransport:
    def __init__(self, responses: list[object] | None = None) -> None:
        self.responses = responses if responses is not None else cloudflare_responses()
        self.calls: list[dict[str, object]] = []

    def post_multipart(self, **kwargs: object):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("unexpected Cloudflare transport call")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class OutscraperTransport:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def get(self, **kwargs: object):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("unexpected Outscraper transport call")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def intent_payload(
    *,
    typed_conditions: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "product_name_ja": "ヘッドホン",
        "product_name_en": "headphones",
        "typed_conditions": [
            {
                "attribute_key": "appearance.color",
                "strength": "required",
                "operator": "equals",
                "expected_value": {"value_type": "enum", "values": ["black"]},
            }
        ],
        "required_terms_ja": ["ワイヤレス", "黒"],
        "required_terms_en": ["wireless", "black"],
        "preferred_terms_ja": ["軽量", "ノイズキャンセリング"],
        "preferred_terms_en": ["lightweight", "noise cancelling"],
        "negative_terms_ja": ["中古"],
        "negative_terms_en": ["used"],
        "brand": "Sony",
        "model_number": "WH-1000XM5",
        "price": {
            "mode": "max",
            "max_jpy": 50_000,
            "source": "explicit",
        },
    }
    if typed_conditions is not None:
        payload["typed_conditions"] = typed_conditions
    return payload


def queryless_blocking_payload() -> dict[str, object]:
    return {
        "ambiguities": [
            {
                "code": "product_type_unknown",
                "message": "商品種別を確認してください",
                "blocking": True,
            }
        ]
    }


def bonsai_response(payload: dict[str, object] | None = None):
    content = json.dumps(
        intent_payload() if payload is None else payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    body = json.dumps(
        {
            "id": "fixture-response-1",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    from src.search_v2.bonsai_request import BonsaiHttpResponse

    return BonsaiHttpResponse(
        status_code=200,
        content_type="application/json; charset=utf-8",
        content_length=len(body),
        content_encoding="identity",
        body_chunks=(body,),
    )


def png_bytes(color: tuple[int, int, int]) -> bytes:
    output = BytesIO()
    image = Image.new("RGB", (512, 512), color)
    step = max(7, color[0] + 3)
    for x in range(color[0], 512, step):
        image.putpixel((x, (x * (color[0] + 1)) % 512), (255, 255 - color[0], 0))
    image.save(output, format="PNG")
    return output.getvalue()


def cloudflare_responses() -> list[CloudflareHttpResponse]:
    responses: list[CloudflareHttpResponse] = []
    for value in (10, 20, 30, 40):
        encoded = base64.b64encode(png_bytes((value, value + 1, value + 2))).decode("ascii")
        body = json.dumps(
            {"result": {"image": encoded}, "success": True, "errors": [], "messages": []},
            separators=(",", ":"),
        ).encode()
        responses.append(
            CloudflareHttpResponse(
                status_code=200,
                content_type="application/json; charset=utf-8",
                content_length=len(body),
                content_encoding="identity",
                body_chunks=(body,),
            )
        )
    return responses


def outscraper_response(query: str, *, empty: bool = False) -> OutscraperHttpResponse:
    products: list[dict[str, object]] = []
    if not empty:
        products.append(
            {
                "query": query,
                "name": "Sony 黒 軽量 ワイヤレスヘッドホン",
                "asin": "B012345678",
                "color": "黒",
                "features": ["軽量", "ノイズキャンセリング"],
                "price": 40_000,
                "currency": "JPY",
            }
        )
    body = json.dumps(
        {
            "id": "request-1",
            "status": "Success",
            "data": [products, []],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    return OutscraperHttpResponse(
        status_code=200,
        content_type="application/json; charset=utf-8",
        content_length=len(body),
        content_encoding="identity",
        body_chunks=(body,),
    )


def usage_ledger() -> InMemoryUsageLedger:
    maximum = UsageAmount(calls=100, tokens=100_000_000, cost_microusd=10_000_000)
    return InMemoryUsageLedger(
        [
            ProviderUsageLimits(
                provider="bonsai",
                pricing_policy_sha256="a" * 64,
                per_user_day=maximum,
                per_session=maximum,
                global_day=maximum,
            ),
            ProviderUsageLimits(
                provider="cloudflare",
                pricing_policy_sha256="b" * 64,
                per_user_day=maximum,
                per_session=maximum,
                global_day=maximum,
            ),
            ProviderUsageLimits(
                provider="outscraper",
                pricing_policy_sha256="c" * 64,
                per_user_day=maximum,
                per_session=maximum,
                global_day=maximum,
            ),
        ]
    )


def backend_policy():
    m = module()
    return m.SearchBackendPolicy(
        schema_version="3.0",
        bonsai_intent=m.ProviderAttemptBudget(
            amount=UsageAmount(calls=1, tokens=2_000_000, cost_microusd=5_000),
            pricing_policy_sha256="a" * 64,
        ),
        cloudflare_image_set=m.ProviderAttemptBudget(
            amount=UsageAmount(calls=4, tokens=0, cost_microusd=4_000),
            pricing_policy_sha256="b" * 64,
        ),
        outscraper_search=m.ProviderAttemptBudget(
            amount=UsageAmount(calls=1, tokens=0, cost_microusd=10_000),
            pricing_policy_sha256="c" * 64,
        ),
        normalization_profile=ProductNormalizationProfile(
            schema_version="2.0",
            profile_id="observed-only-v2",
            usd_to_jpy_rate=160,
        ),
        ranking_profile=TYPED_RANKING_PROFILE_V4,
        implementation_sha256="d" * 64,
    )


def bonsai_config():
    m = module()
    return m.BonsaiIntentConfig(
        base_url="http://127.0.0.1:8080/v1",
        model_id="Bonsai-8B.gguf",
        temperature=0.1,
    )


def test_bonsai_config_exposes_no_generation_token_or_timeout_control() -> None:
    m = module()
    fields = m.BonsaiIntentConfig.model_fields

    assert "max_output_tokens" not in fields
    assert "timeout_seconds" not in fields
    for legacy_field, value in (("max_output_tokens", None), ("timeout_seconds", 60)):
        with pytest.raises(ValidationError, match="extra_forbidden"):
            m.BonsaiIntentConfig.model_validate(
                {
                    **bonsai_config().model_dump(mode="python"),
                    legacy_field: value,
                }
            )


def intent_review(
    *,
    ledger: InMemoryUsageLedger | None = None,
    clock: SequenceClock | None = None,
    transport: BonsaiTransport | None = None,
):
    m = module()
    selected_ledger = ledger if ledger is not None else usage_ledger()
    selected_clock = clock if clock is not None else SequenceClock()
    selected_transport = transport if transport is not None else BonsaiTransport()
    stage = m.start_intent_review(
        SOURCE_INPUT,
        owner_id="owner-1",
        session_id="session-1",
        bonsai_config=bonsai_config(),
        policy=backend_policy(),
        usage_ledger=selected_ledger,
        transport=selected_transport,
        now=selected_clock,
    )
    return stage, selected_ledger, selected_clock, selected_transport


def reference_conditions():
    return build_visual_condition_set(
        source_input=SOURCE_INPUT,
        drafts=(VisualConditionDraft(source_phrase="黒", strength="required"),),
    )


def approve_reference(reference, ledger, clock, transport=None):
    return module().approve_reference_image(
        reference,
        human_confirmed=True,
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=transport or CloudflareTransport(cloudflare_responses() * 2),
        now=clock,
    )


def approved_without_images():
    m = module()
    stage, ledger, clock, bonsai = intent_review()
    review = m.skip_images(
        stage,
        postal_code="100-0001",
        policy=backend_policy(),
        usage_ledger=ledger,
        now=clock,
    )
    approved = m.approve_search(review, now=clock)
    return approved, ledger, clock, bonsai


def test_provisional_branch_starts_at_current_intent_review_and_persists_approval(
    tmp_path,
) -> None:
    stage, ledger, clock, _bonsai = intent_review()
    conditions = build_visual_condition_set(
        source_input=SOURCE_INPUT,
        drafts=(
            VisualConditionDraft(
                source_phrase="黒い",
                strength="required",
                attribute_key="色",
            ),
            VisualConditionDraft(
                source_phrase="軽量",
                strength="preferred",
                attribute_key=None,
            ),
            VisualConditionDraft(
                source_phrase="ノイズキャンセリング",
                strength="preferred",
                attribute_key=None,
            ),
        ),
    )
    repository = SqliteCounterfactualApprovalRepository(
        tmp_path / "counterfactual-approval.sqlite3"
    )
    transport = CloudflareTransport(cloudflare_responses() * 2)

    reference = generate_provisional_reference_review(
        stage,
        source_input=SOURCE_INPUT,
        condition_set=conditions,
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=transport,
        now=clock,
    )
    assert reference.status == "reference_review"
    assert len(transport.calls) == 1
    issued = generate_provisional_images(
        reference,
        human_confirmed=True,
        policy=backend_policy(),
        usage_ledger=ledger,
        approval_repository=repository,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=transport,
        now=clock,
        token_factory=lambda: "A" * 43,
    )

    assert issued.review.schema_version == "5.0"
    assert issued.review.execution.request_set.call_count == 4
    assert len(transport.calls) == 4
    reopened = SqliteCounterfactualApprovalRepository(repository.path)
    approved = approve_provisional_reference_review(
        issued.review,
        approval_token=issued.approval_token,
        human_confirmed=True,
        approval_repository=reopened,
        now=clock,
    )
    assert approved.approval_receipt_sha256
    with pytest.raises(CounterfactualApprovalConflictError, match="already been consumed"):
        approve_provisional_reference_review(
            issued.review,
            approval_token=issued.approval_token,
            human_confirmed=True,
            approval_repository=reopened,
            now=clock,
        )


def test_policy_rejects_provider_attempt_shapes_that_would_change_call_counts() -> None:
    m = module()
    policy = backend_policy().model_dump(mode="python")
    policy["cloudflare_image_set"]["amount"] = UsageAmount(
        calls=3,
        tokens=0,
        cost_microusd=4_000,
    )

    with pytest.raises(ValidationError):
        m.SearchBackendPolicy.model_validate(policy)


def test_intent_review_executes_only_bonsai_and_stops_before_first_confirmation() -> None:
    stage, ledger, _clock, transport = intent_review()

    assert stage.session.state == "intent_review"
    assert stage.session.approval is None
    assert len(stage.query_plan.queries) == 2
    assert len(transport.calls) == 1
    reservations = ledger.snapshot().reservations
    assert [(item.provider, item.status) for item in reservations] == [("bonsai", "succeeded")]
    dumped = stage.model_dump_json()
    assert SOURCE_INPUT not in dumped
    assert "fixture-response-1" not in dumped


def test_first_review_exposes_proposal_and_rejects_source_contradiction() -> None:
    stage, _ledger, _clock, _transport = intent_review()

    assert stage.schema_version == "3.0"
    assert stage.typed_proposal.status == "ready"
    assert stage.session.typed_requirement_proposal_sha256 == typed_requirement_proposal_sha256(
        stage.typed_proposal
    )

    payload = intent_payload(
        typed_conditions=[
            {
                "attribute_key": "appearance.color",
                "operator": "equals",
                "expected_value": {"value_type": "enum", "values": ["round"]},
                "strength": "required",
            }
        ]
    )
    ledger = usage_ledger()
    clock = SequenceClock()
    from src.exceptions import BonsaiResponseError

    with pytest.raises(BonsaiResponseError, match="source constraints"):
        module().start_intent_review(
            SOURCE_INPUT,
            owner_id="owner-1",
            session_id="session-blocked",
            bonsai_config=bonsai_config(),
            policy=backend_policy(),
            usage_ledger=ledger,
            transport=BonsaiTransport(bonsai_response(payload)),
            now=clock,
        )
    assert ledger.snapshot().reservations[0].status == "failed"


def test_queryless_blocking_response_returns_first_confirmation_without_query() -> None:
    m = module()
    ledger = usage_ledger()
    clock = SequenceClock()
    transport = BonsaiTransport(bonsai_response(queryless_blocking_payload()))

    stage = m.start_intent_review(
        SOURCE_INPUT,
        owner_id="owner-1",
        session_id="session-queryless-blocking",
        bonsai_config=bonsai_config(),
        policy=backend_policy(),
        usage_ledger=ledger,
        transport=transport,
        now=clock,
    )

    assert isinstance(stage, m.BlockingIntentReview)
    assert stage.session.state == "intent_review"
    assert stage.session.query_plan_sha256 is None
    assert stage.session.typed_requirement_status == "blocking"
    assert stage.typed_proposal.status == "blocking"
    assert not hasattr(stage, "query_plan")
    assert len(transport.calls) == 1
    assert [(item.provider, item.status) for item in ledger.snapshot().reservations] == [
        ("bonsai", "succeeded")
    ]


def test_ungrounded_live_product_uses_grounded_terms_for_review() -> None:
    m = module()
    ledger = usage_ledger()
    clock = SequenceClock()
    source_input = (
        "5,000円以上10,000円以下の藍鼠色で超低背のワイヤレスキーボード。"
        "発光機能は除外。テンキーは不要ではない。"
    )
    transport = BonsaiTransport(
        bonsai_response(
            {
                "product_name_ja": "青いマウス",
                "required_terms_ja": ["超低背", "ワイヤレスキーボード", "ワイヤレス"],
                "negative_terms_ja": ["発光機能"],
            }
        )
    )

    stage = m.start_intent_review(
        source_input,
        owner_id="owner-1",
        session_id="session-ungrounded-live-product",
        bonsai_config=bonsai_config(),
        policy=backend_policy(),
        usage_ledger=ledger,
        transport=transport,
        now=clock,
    )

    assert isinstance(stage, m.IntentReview)
    assert stage.session.query_plan_sha256 is not None
    assert stage.intent.price.mode == "range"
    assert stage.intent.price.min_jpy == 5000
    assert stage.intent.price.max_jpy == 10000
    assert stage.intent.ambiguities == []
    assert stage.intent.product_name_ja is None
    assert stage.typed_proposal.status == "ready"
    assert [item.language for item in stage.query_plan.queries] == ["ja"]
    assert stage.query_plan.queries[0].value == "超低背 ワイヤレス キーボード"
    assert len(transport.calls) == 1
    assert [(item.provider, item.status) for item in ledger.snapshot().reservations] == [
        ("bonsai", "succeeded")
    ]


def test_blocking_confirmation_cannot_start_later_providers() -> None:
    m = module()
    ledger = usage_ledger()
    clock = SequenceClock()
    stage = m.start_intent_review(
        SOURCE_INPUT,
        owner_id="owner-1",
        session_id="session-blocking-provider-guard",
        bonsai_config=bonsai_config(),
        policy=backend_policy(),
        usage_ledger=ledger,
        transport=BonsaiTransport(bonsai_response(queryless_blocking_payload())),
        now=clock,
    )
    cloudflare = CloudflareTransport(responses=[])

    with pytest.raises(m.SearchOrchestrationError):
        m.generate_images(
            stage,
            source_input=SOURCE_INPUT,
            condition_set=reference_conditions(),
            policy=backend_policy(),
            usage_ledger=ledger,
            account_id=ACCOUNT_ID,
            api_token=CLOUDFLARE_TOKEN,
            transport=cloudflare,
            now=clock,
        )
    with pytest.raises(m.SearchOrchestrationError):
        m.skip_images(
            stage,
            postal_code="100-0001",
            policy=backend_policy(),
            usage_ledger=ledger,
            now=clock,
        )

    assert cloudflare.calls == []
    assert [(item.provider, item.status) for item in ledger.snapshot().reservations] == [
        ("bonsai", "succeeded")
    ]


def test_image_off_path_waits_for_final_confirmation_then_completes_once() -> None:
    m = module()
    stage, ledger, clock, bonsai = intent_review()
    review = m.skip_images(
        stage,
        postal_code="100-0001",
        policy=backend_policy(),
        usage_ledger=ledger,
        now=clock,
    )

    assert review.session.state == "search_approval"
    assert review.session.approval is None
    assert review.plan.image_mode == "off"
    assert (
        next(item.calls for item in review.plan.usage_allowances if item.provider == "cloudflare")
        == 0
    )
    assert len(ledger.snapshot().reservations) == 1

    approved = m.approve_search(review, now=clock)
    assert approved.session.approval is not None
    assert approved.session.approval.consumed_at is None
    assert len(ledger.snapshot().reservations) == 1

    outscraper = OutscraperTransport([outscraper_response(review.query_plan.queries[0].value)])
    result = m.run_search(
        approved,
        usage_ledger=ledger,
        approval_ledger=InMemoryApprovalLedger(),
        api_key=OUTSCRAPER_KEY,
        transport=outscraper,
        now=clock,
        sleep=lambda _seconds: None,
    )

    assert result.outcome == "results"
    assert result.session.state == "search_completed"
    assert len(result.ranked_batch.products) == 1
    assert len(outscraper.calls) == 1
    assert len(bonsai.calls) == 1
    assert [(item.provider, item.status) for item in ledger.snapshot().reservations] == [
        ("bonsai", "succeeded"),
        ("outscraper", "succeeded"),
    ]


def test_image_path_stops_at_image_review_and_binds_all_image_calls_to_final_plan() -> None:
    m = module()
    stage, ledger, clock, _bonsai = intent_review()
    cloudflare = CloudflareTransport(cloudflare_responses() * 2)

    images = m.generate_images(
        stage,
        source_input=SOURCE_INPUT,
        condition_set=reference_conditions(),
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=cloudflare,
        now=clock,
    )

    images = approve_reference(images, ledger, clock, cloudflare)

    assert images.session.state == "image_review"
    assert len(cloudflare.calls) == 2
    assert len(ledger.snapshot().reservations) == 3
    assert all(item.status == "succeeded" for item in ledger.snapshot().reservations)

    review = m.accept_images(
        images,
        postal_code="100-0001",
        policy=backend_policy(),
        usage_ledger=ledger,
        now=clock,
    )

    assert review.session.state == "search_approval"
    assert review.plan.image_mode == "approved"
    assert review.plan.image_set_sha256 == images.counterfactual_execution.reference_set_sha256
    assert (
        next(item.calls for item in review.plan.usage_allowances if item.provider == "cloudflare")
        == 2
    )
    assert len(ledger.snapshot().reservations) == 3
    assert CLOUDFLARE_TOKEN not in images.model_dump_json()
    assert not any(
        isinstance(value, bytes) for value in _walk_values(images.model_dump(mode="python"))
    )

    approved = m.approve_search(review, now=clock)
    outscraper = OutscraperTransport([outscraper_response(review.query_plan.queries[0].value)])
    result = m.run_search(
        approved,
        usage_ledger=ledger,
        approval_ledger=InMemoryApprovalLedger(),
        api_key=OUTSCRAPER_KEY,
        transport=outscraper,
        now=clock,
        sleep=lambda _seconds: None,
    )

    assert result.outcome == "results"
    assert result.session.state == "search_completed"
    assert result.session.image_mode == "on"
    assert len(outscraper.calls) == 1


def test_image_regeneration_replaces_reference_and_records_three_approved_calls() -> None:
    m = module()
    stage, ledger, clock, _bonsai = intent_review()
    first_transport = CloudflareTransport()
    first = m.generate_images(
        stage,
        source_input=SOURCE_INPUT,
        condition_set=reference_conditions(),
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=first_transport,
        now=clock,
    )
    second_transport = CloudflareTransport()
    second = m.regenerate_images(
        first,
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=second_transport,
        now=clock,
    )
    images = approve_reference(second, ledger, clock)
    review = m.accept_images(
        images,
        postal_code="100-0001",
        policy=backend_policy(),
        usage_ledger=ledger,
        now=clock,
    )

    assert len(second.usage_reservations) == 2
    assert first.request.preimage_plan_sha256 != second.request.preimage_plan_sha256
    assert len(first_transport.calls) == len(second_transport.calls) == 1
    assert images.reference_review == second
    assert (
        next(item.calls for item in review.plan.usage_allowances if item.provider == "cloudflare")
        == 3
    )


def test_generated_images_can_be_discarded_without_refunding_usage() -> None:
    m = module()
    stage, ledger, clock, _bonsai = intent_review()
    images = m.generate_images(
        stage,
        source_input=SOURCE_INPUT,
        condition_set=reference_conditions(),
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=CloudflareTransport(),
        now=clock,
    )
    review = m.skip_images(
        images,
        postal_code="100-0001",
        policy=backend_policy(),
        usage_ledger=ledger,
        now=clock,
    )

    assert review.session.state == "search_approval"
    assert review.session.image_mode == "off"
    assert review.plan.image_mode == "off"
    assert review.plan.runtime_bindings.cloudflare_model_id is None
    assert (
        next(item.calls for item in review.plan.usage_allowances if item.provider == "cloudflare")
        == 0
    )
    assert [(item.provider, item.status) for item in ledger.snapshot().reservations] == [
        ("bonsai", "succeeded"),
        ("cloudflare", "succeeded"),
    ]


def test_search_failure_is_returned_as_fixed_product_search_state() -> None:
    m = module()
    approved, ledger, clock, _bonsai = approved_without_images()
    approval_ledger = InMemoryApprovalLedger()
    transport = OutscraperTransport([RuntimeError("raw provider detail")])

    result = m.run_search(
        approved,
        usage_ledger=ledger,
        approval_ledger=approval_ledger,
        api_key=OUTSCRAPER_KEY,
        transport=transport,
        now=clock,
        sleep=lambda _seconds: None,
    )

    assert result.outcome == "failed"
    assert result.session.state == "search_failed"
    assert result.session.failure_stage == "product_search"
    assert result.session.failure_code == "product_search_failed"
    assert "raw provider detail" not in result.model_dump_json()
    assert ledger.snapshot().reservations[-1].status == "failed"
    assert len(approval_ledger.snapshot().consumptions) == 1


def test_normal_empty_result_completes_without_becoming_a_failure() -> None:
    m = module()
    approved, ledger, clock, _bonsai = approved_without_images()
    transport = OutscraperTransport(
        [outscraper_response(approved.review.query_plan.queries[0].value, empty=True)]
    )

    result = m.run_search(
        approved,
        usage_ledger=ledger,
        approval_ledger=InMemoryApprovalLedger(),
        api_key=OUTSCRAPER_KEY,
        transport=transport,
        now=clock,
        sleep=lambda _seconds: None,
    )

    assert result.outcome == "empty"
    assert result.session.state == "search_completed"
    assert result.session.result_outcome == "empty"
    assert result.session.failure_code is None


def test_expired_approval_is_rejected_before_usage_or_provider_attempt() -> None:
    m = module()
    approved, ledger, _clock, _bonsai = approved_without_images()
    transport = OutscraperTransport([])
    reservation_count = len(ledger.snapshot().reservations)

    with pytest.raises(m.SearchOrchestrationError, match="expired"):
        m.run_search(
            approved,
            usage_ledger=ledger,
            approval_ledger=InMemoryApprovalLedger(),
            api_key=OUTSCRAPER_KEY,
            transport=transport,
            now=SequenceClock(NOW + timedelta(minutes=16)),
            sleep=lambda _seconds: None,
        )

    assert len(ledger.snapshot().reservations) == reservation_count
    assert transport.calls == []


def test_sequential_reuse_is_rejected_before_a_second_provider_attempt() -> None:
    m = module()
    approved, ledger, clock, _bonsai = approved_without_images()
    approval_ledger = InMemoryApprovalLedger()
    transport = OutscraperTransport(
        [outscraper_response(approved.review.query_plan.queries[0].value)]
    )
    m.run_search(
        approved,
        usage_ledger=ledger,
        approval_ledger=approval_ledger,
        api_key=OUTSCRAPER_KEY,
        transport=transport,
        now=clock,
        sleep=lambda _seconds: None,
    )
    reservation_count = len(ledger.snapshot().reservations)

    with pytest.raises(m.SearchOrchestrationError, match="already been consumed"):
        m.run_search(
            approved,
            usage_ledger=ledger,
            approval_ledger=approval_ledger,
            api_key=OUTSCRAPER_KEY,
            transport=transport,
            now=clock,
            sleep=lambda _seconds: None,
        )

    assert len(transport.calls) == 1
    assert len(ledger.snapshot().reservations) == reservation_count


def test_tampered_review_is_rejected_before_approval_or_provider_use() -> None:
    m = module()
    approved, ledger, clock, _bonsai = approved_without_images()
    payload = approved.review.model_dump(mode="python")
    request_payload = dict(payload["request"])
    request_payload["postal_code"] = "150-0001"
    payload["request"] = request_payload

    with pytest.raises(ValidationError):
        m.SearchReview.model_validate(payload)

    assert len(ledger.snapshot().reservations) == 1
    assert approved.session.approval is not None
    assert approved.session.approval.consumed_at is None
    assert clock.offset > 0


def test_provider_credentials_and_raw_approval_token_are_not_represented() -> None:
    m = module()
    approved, _ledger, _clock, _bonsai = approved_without_images()

    represented = repr(approved)
    serialized = approved.review.model_dump_json()
    assert approved.token not in represented
    assert CLOUDFLARE_TOKEN not in represented
    assert OUTSCRAPER_KEY not in represented
    assert approved.token not in serialized
    assert not hasattr(approved, "model_dump")
    assert approved.review.session.approval is None
    assert approved.session.approval is not None
    assert m.ApprovedSearch.__dataclass_params__.repr is False


def test_orchestrator_does_not_import_openai_or_send_products_to_bonsai() -> None:
    source_path = Path("src/search_v2/orchestrator.py")
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    imported = {
        name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for name in (
            [alias.name for alias in node.names]
            if isinstance(node, ast.Import)
            else [node.module or ""]
        )
    }
    assert not any(name == "openai" or name.startswith("openai.") for name in imported)

    approved, ledger, clock, bonsai = approved_without_images()
    transport = OutscraperTransport(
        [outscraper_response(approved.review.query_plan.queries[0].value)]
    )
    m = module()
    m.run_search(
        approved,
        usage_ledger=ledger,
        approval_ledger=InMemoryApprovalLedger(),
        api_key=OUTSCRAPER_KEY,
        transport=transport,
        now=clock,
        sleep=lambda _seconds: None,
    )

    assert len(bonsai.calls) == 1
    assert len(transport.calls) == 1


def test_cloudflare_failure_returns_strict_recovery_stage_and_keeps_failed_usage() -> None:
    m = module()
    assert hasattr(m, "ImageFailureReview"), "image failure recovery stage is required"
    stage, ledger, clock, _bonsai = intent_review()
    transport = CloudflareTransport([RuntimeError("raw image provider detail")])

    failed = m.generate_images(
        stage,
        source_input=SOURCE_INPUT,
        condition_set=reference_conditions(),
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=transport,
        now=clock,
    )

    assert isinstance(failed, m.ReferenceReview)
    assert failed.status == "reference_generation_failed"
    assert len(failed.usage_reservations) == 1
    assert len(transport.calls) == 1
    assert ledger.snapshot().reservations[-1].provider == "cloudflare"
    assert ledger.snapshot().reservations[-1].status == "failed"
    serialized = failed.model_dump_json()
    assert "raw image provider detail" not in serialized
    assert CLOUDFLARE_TOKEN not in serialized
    assert not any(isinstance(value, bytes) for value in _walk_values(failed.model_dump()))


def test_failed_image_attempt_retries_only_after_explicit_action_and_counts_both() -> None:
    m = module()
    assert hasattr(m, "retry_failed_images"), "explicit failed image retry is required"
    stage, ledger, clock, _bonsai = intent_review()
    failed_transport = CloudflareTransport([RuntimeError("raw image provider detail")])
    failed = m.generate_images(
        stage,
        source_input=SOURCE_INPUT,
        condition_set=reference_conditions(),
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=failed_transport,
        now=clock,
    )

    assert len(failed_transport.calls) == 1
    assert [item.status for item in failed.usage_reservations] == ["failed"]
    assert len(ledger.snapshot().reservations) == 2

    retry_transport = CloudflareTransport()
    images = m.retry_failed_images(
        failed,
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=retry_transport,
        now=clock,
    )

    assert images.status == "reference_review"
    assert len(images.usage_reservations) == 2
    assert [item.status for item in images.usage_reservations] == [
        "failed",
        "succeeded",
    ]
    assert len(retry_transport.calls) == 1

    completed = approve_reference(images, ledger, clock)
    review = m.accept_images(
        completed,
        postal_code="100-0001",
        policy=backend_policy(),
        usage_ledger=ledger,
        now=clock,
    )
    assert (
        next(item.calls for item in review.plan.usage_allowances if item.provider == "cloudflare")
        == 3
    )


def test_failed_image_attempt_can_continue_without_images_without_refund() -> None:
    m = module()
    stage, ledger, clock, _bonsai = intent_review()
    transport = CloudflareTransport([RuntimeError("raw image provider detail")])
    failed = m.generate_images(
        stage,
        source_input=SOURCE_INPUT,
        condition_set=reference_conditions(),
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=transport,
        now=clock,
    )
    reservation_count = len(ledger.snapshot().reservations)

    review = m.skip_images(
        failed,
        postal_code="100-0001",
        policy=backend_policy(),
        usage_ledger=ledger,
        now=clock,
    )

    assert len(transport.calls) == 1
    assert len(ledger.snapshot().reservations) == reservation_count
    assert ledger.snapshot().reservations[-1].status == "failed"
    assert review.session.state == "search_approval"
    assert review.session.image_mode == "off"
    assert review.plan.image_mode == "off"
    assert (
        next(item.calls for item in review.plan.usage_allowances if item.provider == "cloudflare")
        == 0
    )


def test_second_attempt_failure_blocks_third_attempt_before_reservation_or_transport() -> None:
    m = module()
    stage, ledger, clock, _bonsai = intent_review()
    first = m.generate_images(
        stage,
        source_input=SOURCE_INPUT,
        condition_set=reference_conditions(),
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=CloudflareTransport(),
        now=clock,
    )
    failed = m.regenerate_images(
        first,
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=CloudflareTransport([RuntimeError("raw second-attempt detail")]),
        now=clock,
    )
    assert failed.status == "reference_generation_failed"
    assert len(failed.usage_reservations) == 2
    assert [item.status for item in failed.usage_reservations] == [
        "succeeded",
        "failed",
    ]
    reservation_count = len(ledger.snapshot().reservations)
    third_transport = CloudflareTransport([])

    with pytest.raises(m.SearchOrchestrationError, match="image set limit"):
        m.retry_failed_images(
            failed,
            policy=backend_policy(),
            usage_ledger=ledger,
            account_id=ACCOUNT_ID,
            api_token=CLOUDFLARE_TOKEN,
            transport=third_transport,
            now=clock,
        )

    assert len(ledger.snapshot().reservations) == reservation_count
    assert third_transport.calls == []


def test_tampered_image_failure_stage_is_rejected_before_retry_reservation() -> None:
    m = module()
    stage, ledger, clock, _bonsai = intent_review()
    failed = m.generate_images(
        stage,
        source_input=SOURCE_INPUT,
        condition_set=reference_conditions(),
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=CloudflareTransport([RuntimeError("raw detail")]),
        now=clock,
    )
    tampered = failed.model_copy(update={"policy_sha256": "0" * 64})
    reservation_count = len(ledger.snapshot().reservations)
    transport = CloudflareTransport([])

    with pytest.raises(m.SearchOrchestrationError, match="invalid"):
        m.retry_failed_images(
            tampered,
            policy=backend_policy(),
            usage_ledger=ledger,
            account_id=ACCOUNT_ID,
            api_token=CLOUDFLARE_TOKEN,
            transport=transport,
            now=clock,
        )

    assert len(ledger.snapshot().reservations) == reservation_count
    assert transport.calls == []


def test_explicit_retry_failure_returns_exhausted_recovery_without_auto_retry() -> None:
    m = module()
    stage, ledger, clock, _bonsai = intent_review()
    failed = m.generate_images(
        stage,
        source_input=SOURCE_INPUT,
        condition_set=reference_conditions(),
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=CloudflareTransport([RuntimeError("raw first-attempt detail")]),
        now=clock,
    )
    retry_transport = CloudflareTransport([RuntimeError("raw retry detail")])

    exhausted = m.retry_failed_images(
        failed,
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=retry_transport,
        now=clock,
    )

    assert exhausted.status == "reference_generation_failed"
    assert len(exhausted.usage_reservations) == 2
    assert [item.status for item in exhausted.usage_reservations] == [
        "failed",
        "failed",
    ]
    assert len(retry_transport.calls) == 1
    assert "raw retry detail" not in exhausted.model_dump_json()


def test_completed_second_image_attempt_blocks_regeneration_before_reservation() -> None:
    m = module()
    stage, ledger, clock, _bonsai = intent_review()
    first = m.generate_images(
        stage,
        source_input=SOURCE_INPUT,
        condition_set=reference_conditions(),
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=CloudflareTransport(),
        now=clock,
    )
    second = m.regenerate_images(
        first,
        policy=backend_policy(),
        usage_ledger=ledger,
        account_id=ACCOUNT_ID,
        api_token=CLOUDFLARE_TOKEN,
        transport=CloudflareTransport(),
        now=clock,
    )
    reservation_count = len(ledger.snapshot().reservations)
    transport = CloudflareTransport([])

    with pytest.raises(m.SearchOrchestrationError, match="image set limit"):
        m.regenerate_images(
            second,
            policy=backend_policy(),
            usage_ledger=ledger,
            account_id=ACCOUNT_ID,
            api_token=CLOUDFLARE_TOKEN,
            transport=transport,
            now=clock,
        )

    assert len(ledger.snapshot().reservations) == reservation_count
    assert transport.calls == []


def _walk_values(value: object):
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk_values(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_values(item)
        return
    yield value
