from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest
from pydantic import ValidationError

from src.search_v2.approval import ApprovedUsage
from src.search_v2.approval import SearchRuntimeBindings
from src.search_v2.approval import build_search_approval_plan
from src.search_v2.approval import search_approval_plan_sha256
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent
from src.search_v2.outscraper_request import OUTSCRAPER_AMAZON_PRODUCTS_ENDPOINT
from src.search_v2.outscraper_request import OUTSCRAPER_DOMAIN
from src.search_v2.outscraper_request import OUTSCRAPER_LANGUAGE
from src.search_v2.outscraper_request import OUTSCRAPER_LIMIT_PER_QUERY
from src.search_v2.outscraper_request import AuthorizedOutscraperRequest
from src.search_v2.outscraper_request import OutscraperAmazonProductsRequest
from src.search_v2.outscraper_request import OutscraperAuthorizationError
from src.search_v2.outscraper_request import authorize_outscraper_request
from src.search_v2.outscraper_request import build_outscraper_request
from src.search_v2.outscraper_request import outscraper_request_sha256
from src.search_v2.product_evidence import product_evidence_profile_sha256
from src.search_v2.query_planner import SearchQueryPlan
from src.search_v2.query_planner import build_search_query_plan
from src.search_v2.state_machine import InMemoryApprovalLedger
from src.search_v2.state_machine import SearchStateError
from src.search_v2.state_machine import approve_intent_review
from src.search_v2.state_machine import create_search_session
from src.search_v2.state_machine import issue_search_approval
from src.search_v2.state_machine import record_intent_plan
from src.search_v2.state_machine import start_intent_processing
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_ranking import typed_ranking_profile_sha256
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import ProviderUsageLimits
from src.search_v2.usage_ledger import UsageAmount
from src.search_v2.usage_ledger import UsageReservationRequest
from src.search_v2.usage_ledger import usage_policy_sha256


NOW = datetime(2026, 9, 2, 8, 0, tzinfo=timezone.utc)


def normalized_intent():
    payload = {
        "product_name_ja": "ヘッドホン",
        "product_name_en": "headphones",
        "category_ja": "オーディオ",
        "category_en": "audio",
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


def query_plan(*, one_query: bool = False) -> SearchQueryPlan:
    plan = build_search_query_plan(normalized_intent())
    if not one_query:
        return plan
    return SearchQueryPlan(
        schema_version="2.0",
        intent_sha256=plan.intent_sha256,
        queries=[plan.queries[0]],
    )


def usage_policies() -> list[ProviderUsageLimits]:
    def limits(provider: str, *, calls: int, tokens: int, cost: int):
        digests = {"bonsai": "a" * 64, "cloudflare": "b" * 64, "outscraper": "c" * 64}
        amount = UsageAmount(calls=calls, tokens=tokens, cost_microusd=cost)
        return ProviderUsageLimits(
            provider=provider,
            pricing_policy_sha256=digests[provider],
            per_user_day=amount,
            per_session=amount,
            global_day=amount,
        )

    return [
        limits("bonsai", calls=2, tokens=20_000, cost=20_000),
        limits("cloudflare", calls=8, tokens=0, cost=40_000),
        limits("outscraper", calls=1, tokens=0, cost=20_000),
    ]


def approval_context(*, request=None, request_digest: str | None = None):
    intent = normalized_intent()
    plan = build_search_query_plan(intent)
    request = request or build_outscraper_request(plan, postal_code="100-0001")

    session = create_search_session(owner_id="owner-1", session_id="session-1", now=NOW)
    session = start_intent_processing(
        session,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=1),
    )
    session = record_intent_plan(
        session,
        intent=intent,
        query_plan=plan,
        typed_proposal=build_typed_requirement_proposal(intent),
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=2),
    )
    session = approve_intent_review(
        session,
        use_images=False,
        image_reservation=None,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=3),
    )

    policies = usage_policies()
    approval = build_search_approval_plan(
        owner_id=session.owner_id,
        session_id=session.session_id,
        intent=intent,
        query_plan=plan,
        outscraper_request_sha256=(
            request_digest if request_digest is not None else outscraper_request_sha256(request)
        ),
        image_set_sha256=None,
        image_request_metadata_sha256=None,
        usage_allowances=[
            ApprovedUsage(
                provider="bonsai",
                calls=1,
                tokens=4_096,
                cost_microusd=5_000,
                pricing_policy_sha256="a" * 64,
            ),
            ApprovedUsage(
                provider="cloudflare",
                calls=0,
                tokens=0,
                cost_microusd=0,
                pricing_policy_sha256="b" * 64,
            ),
            ApprovedUsage(
                provider="outscraper",
                calls=1,
                tokens=0,
                cost_microusd=10_000,
                pricing_policy_sha256="c" * 64,
            ),
        ],
        runtime_bindings=SearchRuntimeBindings(
            bonsai_model_id="local-bonsai-model",
            bonsai_prompt_sha256=intent.provenance.prompt_sha256,
            bonsai_schema_sha256=intent.provenance.schema_sha256,
            cloudflare_model_id=None,
            image_prompt_sha256=None,
            ranking_profile_id="typed-ranking-v4",
            ranking_profile_sha256=typed_ranking_profile_sha256(),
            product_evidence_profile_sha256=product_evidence_profile_sha256(),
            implementation_sha256="e" * 64,
            usage_policy_sha256=usage_policy_sha256(policies),
        ),
        created_at=NOW + timedelta(seconds=4),
    )
    issued = issue_search_approval(
        session,
        plan=approval,
        expected_revision=session.revision,
        now=NOW + timedelta(seconds=4),
    )

    usage_ledger = InMemoryUsageLedger(policies)
    reserved = usage_ledger.reserve(
        UsageReservationRequest(
            provider="outscraper",
            operation="product_search",
            owner_id="owner-1",
            session_id="session-1",
            binding_sha256=search_approval_plan_sha256(approval),
            amount=UsageAmount(calls=1, tokens=0, cost_microusd=10_000),
            pricing_policy_sha256="c" * 64,
        ),
        now=NOW + timedelta(seconds=5),
    )
    reservation = usage_ledger.start(
        reserved.reservation_id,
        owner_id="owner-1",
        session_id="session-1",
        now=NOW + timedelta(seconds=5, milliseconds=1),
    )
    return request, approval, issued, reservation


def authorize(request, approval, issued, reservation, *, ledger=None, token=None):
    return authorize_outscraper_request(
        request,
        session=issued.session,
        approval_ledger=ledger or InMemoryApprovalLedger(),
        token=issued.token if token is None else token,
        plan=approval,
        outscraper_reservation=reservation,
        owner_id="owner-1",
        session_id="session-1",
        expected_revision=issued.session.revision,
        now=NOW + timedelta(seconds=6),
    )


def test_builds_one_async_get_with_repeated_queries_and_only_approved_parameters() -> None:
    plan = query_plan()
    request = build_outscraper_request(plan, postal_code="100-0001")

    assert request.endpoint == OUTSCRAPER_AMAZON_PRODUCTS_ENDPOINT
    assert request.method == "GET"
    assert request.domain == OUTSCRAPER_DOMAIN == "amazon.co.jp"
    assert request.language == OUTSCRAPER_LANGUAGE == "ja"
    assert request.limit_per_query == OUTSCRAPER_LIMIT_PER_QUERY == 24
    assert request.async_request is True
    assert request.maximum_candidates == 48
    assert tuple((query.language, query.value) for query in request.queries) == tuple(
        (query.language, query.value) for query in plan.queries
    )
    assert request.query_parameters() == (
        ("query", plan.queries[0].value),
        ("query", plan.queries[1].value),
        ("domain", "amazon.co.jp"),
        ("language", "ja"),
        ("postal_code", "100-0001"),
        ("limit", "24"),
        ("async", "true"),
    )
    assert {name for name, _value in request.query_parameters()} == {
        "query",
        "domain",
        "language",
        "postal_code",
        "limit",
        "async",
    }
    assert "100-0001" not in repr(request)
    assert all(query.value not in repr(request) for query in plan.queries)


def test_one_query_plan_has_a_24_candidate_ceiling() -> None:
    plan = query_plan(one_query=True)
    request = build_outscraper_request(plan, postal_code="1000001")

    assert request.maximum_candidates == 24
    assert [item for item in request.query_parameters() if item[0] == "query"] == [
        ("query", plan.queries[0].value)
    ]


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://api.outscraper.cloud/amazon-products",
        "https://user@example.test/amazon-products",
        "https://api.outscraper.cloud/other",
        "https://api.outscraper.cloud/amazon-products?async=true",
        "https://api.outscraper.cloud/amazon-products#fragment",
    ],
)
def test_endpoint_is_https_credential_free_and_has_the_exact_operation_path(
    endpoint: str,
) -> None:
    with pytest.raises(ValidationError):
        build_outscraper_request(query_plan(), endpoint=endpoint, postal_code="100-0001")


@pytest.mark.parametrize("postal_code", ["", " 100-0001", "100-0001\n", "ABC-0001"])
def test_postal_code_is_a_bounded_japanese_server_setting(postal_code: str) -> None:
    with pytest.raises(ValidationError):
        build_outscraper_request(query_plan(), postal_code=postal_code)


def test_request_contract_rejects_credentials_and_unknown_provider_parameters() -> None:
    request = build_outscraper_request(query_plan(), postal_code="100-0001")
    payload = request.model_dump(mode="python")

    for field_name in ("api_key", "apiKey", "authorization", "fields", "ui", "webhook"):
        with pytest.raises(ValidationError):
            OutscraperAmazonProductsRequest.model_validate(
                {**payload, field_name: "must-not-be-accepted"}
            )


def test_request_digest_is_deterministic_and_binds_every_outbound_value() -> None:
    plan = query_plan()
    first = build_outscraper_request(plan, postal_code="100-0001")
    same = build_outscraper_request(plan, postal_code="100-0001")
    other_endpoint = build_outscraper_request(
        plan,
        endpoint="https://api.outscraper.com/amazon-products",
        postal_code="100-0001",
    )
    other_postal_code = build_outscraper_request(plan, postal_code="1000002")
    one_query = build_outscraper_request(query_plan(one_query=True), postal_code="100-0001")

    assert outscraper_request_sha256(first) == outscraper_request_sha256(same)
    assert outscraper_request_sha256(first) != outscraper_request_sha256(other_endpoint)
    assert outscraper_request_sha256(first) != outscraper_request_sha256(other_postal_code)
    assert outscraper_request_sha256(first) != outscraper_request_sha256(one_query)


def test_digest_revalidates_forged_nested_query_data() -> None:
    request = build_outscraper_request(query_plan(), postal_code="100-0001")
    forged_query = request.queries[0].model_construct(
        language="ja",
        value="https://example.test/injected",
    )
    forged = request.model_copy(update={"queries": (forged_query, *request.queries[1:])})

    with pytest.raises(ValidationError):
        outscraper_request_sha256(forged)


def test_valid_explicit_approval_returns_one_token_free_execution_permit() -> None:
    request, approval, issued, reservation = approval_context()
    ledger = InMemoryApprovalLedger()

    permit = authorize(request, approval, issued, reservation, ledger=ledger)

    assert isinstance(permit, AuthorizedOutscraperRequest)
    assert permit.request == request
    assert permit.session.state == "scrape_submitted"
    assert permit.session.approval is not None
    assert permit.session.approval.consumed_at == NOW + timedelta(seconds=6)
    assert permit.approval_plan_sha256 == search_approval_plan_sha256(approval)
    assert permit.reservation_id == reservation.reservation_id
    assert permit.authorized_at == NOW + timedelta(seconds=6)
    assert issued.token not in repr(permit)
    assert all("token" not in name for name in permit.__dataclass_fields__)

    with pytest.raises(SearchStateError, match="already been consumed"):
        authorize(request, approval, issued, reservation, ledger=ledger)


def test_request_mismatch_is_rejected_before_the_single_use_token_is_consumed() -> None:
    request, approval, issued, reservation = approval_context()
    changed = build_outscraper_request(query_plan(), postal_code="1000002")
    ledger = InMemoryApprovalLedger()

    with pytest.raises(OutscraperAuthorizationError, match="request does not match approval"):
        authorize(changed, approval, issued, reservation, ledger=ledger)

    assert ledger.snapshot().consumptions == []
    permit = authorize(request, approval, issued, reservation, ledger=ledger)
    assert permit.session.state == "scrape_submitted"


def test_request_query_plan_must_match_the_plan_even_when_its_request_digest_is_approved() -> None:
    request = build_outscraper_request(query_plan(), postal_code="100-0001")
    forged = request.model_copy(update={"query_plan_sha256": "9" * 64})
    request, approval, issued, reservation = approval_context(
        request=forged,
        request_digest=outscraper_request_sha256(forged),
    )
    ledger = InMemoryApprovalLedger()

    with pytest.raises(OutscraperAuthorizationError, match="query plan does not match approval"):
        authorize(request, approval, issued, reservation, ledger=ledger)

    assert ledger.snapshot().consumptions == []


def test_request_query_values_must_match_the_approved_query_plan() -> None:
    request = build_outscraper_request(query_plan(), postal_code="100-0001")
    changed_query = request.queries[0].model_copy(update={"value": "別の商品"})
    forged = request.model_copy(update={"queries": (changed_query, *request.queries[1:])})
    request, approval, issued, reservation = approval_context(
        request=forged,
        request_digest=outscraper_request_sha256(forged),
    )
    ledger = InMemoryApprovalLedger()

    with pytest.raises(OutscraperAuthorizationError, match="query batch does not match approval"):
        authorize(request, approval, issued, reservation, ledger=ledger)

    assert ledger.snapshot().consumptions == []


def test_wrong_token_never_returns_a_permit_or_consumes_the_approval() -> None:
    request, approval, issued, reservation = approval_context()
    ledger = InMemoryApprovalLedger()

    with pytest.raises(SearchStateError, match="approval token does not match"):
        authorize(
            request,
            approval,
            issued,
            reservation,
            ledger=ledger,
            token="B" * 43,
        )

    assert ledger.snapshot().consumptions == []
    assert authorize(request, approval, issued, reservation, ledger=ledger).session.state == (
        "scrape_submitted"
    )


def test_guard_revalidates_a_forged_request_before_claiming_the_token() -> None:
    request, approval, issued, reservation = approval_context()
    forged = request.model_construct(**{**request.model_dump(mode="python"), "method": "POST"})
    ledger = InMemoryApprovalLedger()

    with pytest.raises(OutscraperAuthorizationError, match="Outscraper request is invalid"):
        authorize(forged, approval, issued, reservation, ledger=ledger)

    assert ledger.snapshot().consumptions == []
