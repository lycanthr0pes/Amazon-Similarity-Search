from datetime import datetime
from datetime import timezone

import pytest
from pydantic import ValidationError

from src.search_v2.approval import APPROVAL_TTL
from src.search_v2.approval import ApprovedUsage
from src.search_v2.approval import SearchRuntimeBindings
from src.search_v2.approval import build_search_approval_plan
from src.search_v2.approval import search_approval_plan_sha256
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent
from src.search_v2.query_planner import build_search_query_plan
from src.search_v2.product_evidence import product_evidence_profile_sha256
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_intent_adapter import typed_requirement_proposal_sha256
from src.search_v2.typed_ranking import typed_ranking_profile_sha256


NOW = datetime(2026, 9, 2, 4, 0, tzinfo=timezone.utc)


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


def approved_usage() -> list[ApprovedUsage]:
    return [
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
    ]


def runtime_bindings(*, with_images: bool = False) -> SearchRuntimeBindings:
    intent = normalized_intent()
    return SearchRuntimeBindings(
        bonsai_model_id="local-bonsai-model",
        bonsai_prompt_sha256=intent.provenance.prompt_sha256,
        bonsai_schema_sha256=intent.provenance.schema_sha256,
        cloudflare_model_id=("@cf/black-forest-labs/flux-2-klein-4b" if with_images else None),
        image_prompt_sha256=("d" * 64 if with_images else None),
        ranking_profile_id="typed-ranking-v4",
        ranking_profile_sha256=typed_ranking_profile_sha256(),
        product_evidence_profile_sha256=product_evidence_profile_sha256(),
        implementation_sha256="f" * 64,
        usage_policy_sha256="1" * 64,
    )


def approval_plan(*, with_images: bool = False, outscraper_digest: str = "2" * 64):
    intent = normalized_intent()
    query_plan = build_search_query_plan(intent)
    usages = approved_usage()
    if with_images:
        usages[1] = usages[1].model_copy(update={"calls": 8, "cost_microusd": 20_000})
    return build_search_approval_plan(
        owner_id="owner-1",
        session_id="session-1",
        intent=intent,
        query_plan=query_plan,
        outscraper_request_sha256=outscraper_digest,
        image_set_sha256=("3" * 64 if with_images else None),
        image_request_metadata_sha256=("4" * 64 if with_images else None),
        usage_allowances=usages,
        runtime_bindings=runtime_bindings(with_images=with_images),
        created_at=NOW,
    )


def test_approval_plan_is_canonical_deterministic_and_expires_in_15_minutes() -> None:
    first = approval_plan()
    second = approval_plan()

    assert first == second
    assert first.expires_at == NOW + APPROVAL_TTL
    assert search_approval_plan_sha256(first) == search_approval_plan_sha256(second)
    assert "Sony WH-1000XM5を5万円以内で" not in first.model_dump_json()
    assert "approval_token" not in first.model_dump_json()


def test_approval_plan_v3_binds_the_typed_proposal_and_v4_runtime() -> None:
    plan = approval_plan()
    proposal = build_typed_requirement_proposal(plan.intent)

    assert plan.schema_version == "3.0"
    assert plan.typed_requirement_proposal_sha256 == typed_requirement_proposal_sha256(proposal)
    assert (
        plan.runtime_bindings.product_evidence_profile_sha256 == product_evidence_profile_sha256()
    )
    assert plan.runtime_bindings.ranking_profile_id == "typed-ranking-v4"
    assert plan.runtime_bindings.ranking_profile_sha256 == typed_ranking_profile_sha256()

    payload = plan.model_dump(mode="python")
    payload["schema_version"] = "2.0"
    with pytest.raises(ValidationError):
        type(plan).model_validate(payload)


def test_approval_digest_changes_when_outscraper_request_changes() -> None:
    first = approval_plan(outscraper_digest="2" * 64)
    second = approval_plan(outscraper_digest="3" * 64)

    assert search_approval_plan_sha256(first) != search_approval_plan_sha256(second)


def test_approval_digest_canonicalizes_provider_allowance_order() -> None:
    plan = approval_plan()
    payload = plan.model_dump(mode="python")
    payload["usage_allowances"] = list(reversed(plan.usage_allowances))
    reordered = type(plan).model_validate(payload)

    assert search_approval_plan_sha256(reordered) == search_approval_plan_sha256(plan)


def test_approval_plan_binds_the_exact_intent_query_and_runtime_provenance() -> None:
    plan = approval_plan()

    assert plan.query_plan.intent_sha256 == plan.intent_sha256
    assert plan.runtime_bindings.bonsai_prompt_sha256 == plan.intent.provenance.prompt_sha256
    assert plan.runtime_bindings.bonsai_schema_sha256 == plan.intent.provenance.schema_sha256

    forged_query_plan = plan.query_plan.model_copy(update={"intent_sha256": "9" * 64})
    payload = plan.model_dump(mode="python")
    payload["query_plan"] = forged_query_plan
    with pytest.raises(ValidationError, match="query plan does not match intent"):
        type(plan).model_validate(payload)


def test_approval_plan_requires_exactly_one_allowance_per_provider() -> None:
    plan = approval_plan()
    payload = plan.model_dump(mode="python")
    payload["usage_allowances"] = [
        approved_usage()[0],
        approved_usage()[0],
        approved_usage()[2],
    ]

    with pytest.raises(ValidationError, match="one allowance per provider"):
        type(plan).model_validate(payload)


def test_image_bindings_are_all_present_or_all_absent() -> None:
    intent = normalized_intent()
    query_plan = build_search_query_plan(intent)

    with pytest.raises(ValidationError, match="image bindings"):
        build_search_approval_plan(
            owner_id="owner-1",
            session_id="session-1",
            intent=intent,
            query_plan=query_plan,
            outscraper_request_sha256="2" * 64,
            image_set_sha256="3" * 64,
            image_request_metadata_sha256=None,
            usage_allowances=approved_usage(),
            runtime_bindings=runtime_bindings(with_images=False),
            created_at=NOW,
        )


def test_image_plan_requires_cloudflare_runtime_and_nonzero_allowance() -> None:
    plan = approval_plan(with_images=True)
    payload = plan.model_dump(mode="python")
    payload["runtime_bindings"] = runtime_bindings(with_images=False)

    with pytest.raises(ValidationError, match="Cloudflare runtime"):
        type(plan).model_validate(payload)


def test_approval_plan_requires_utc_and_revalidates_nested_models() -> None:
    with pytest.raises(ValidationError, match="UTC"):
        build_search_approval_plan(
            owner_id="owner-1",
            session_id="session-1",
            intent=normalized_intent(),
            query_plan=build_search_query_plan(normalized_intent()),
            outscraper_request_sha256="2" * 64,
            image_set_sha256=None,
            image_request_metadata_sha256=None,
            usage_allowances=approved_usage(),
            runtime_bindings=runtime_bindings(),
            created_at=NOW.replace(tzinfo=None),
        )

    plan = approval_plan()
    forged_usage = ApprovedUsage.model_construct(
        provider="outscraper",
        calls=True,
        tokens=0,
        cost_microusd=1,
        pricing_policy_sha256="c" * 64,
    )
    payload = plan.model_dump(mode="python")
    payload["usage_allowances"] = [*approved_usage()[:2], forged_usage]
    with pytest.raises(ValidationError):
        type(plan).model_validate(payload)
