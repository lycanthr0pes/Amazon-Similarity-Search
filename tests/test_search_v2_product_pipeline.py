from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest
from pydantic import ValidationError

import src.search_v2.product_pipeline as product_pipeline
from src.search_v2.approval import ApprovedUsage
from src.search_v2.approval import SearchApprovalPlan
from src.search_v2.approval import SearchRuntimeBindings
from src.search_v2.approval import build_search_approval_plan
from src.search_v2.approval import search_approval_plan_sha256
from src.search_v2.intent import NormalizedSearchIntent
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent
from src.search_v2.outscraper_http import OutscraperProductExecution
from src.search_v2.outscraper_request import build_outscraper_request
from src.search_v2.outscraper_request import outscraper_request_sha256
from src.search_v2.product_evidence import product_evidence_profile_sha256
from src.search_v2.product_normalization import ProductNormalizationProfile
from src.search_v2.product_normalization import normalized_product_batch_sha256
from src.search_v2.query_planner import SearchQueryPlan
from src.search_v2.query_planner import build_search_query_plan
from src.search_v2.query_planner import search_query_plan_sha256
from src.search_v2.state_machine import SearchApprovalGrant
from src.search_v2.state_machine import SearchSessionSnapshot
from src.search_v2.typed_intent_adapter import TypedRequirementProposal
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_intent_adapter import typed_requirement_proposal_sha256
from src.search_v2.typed_ranking import TypedRankingError
from src.search_v2.typed_ranking import TypedRankedProductBatch
from src.search_v2.typed_ranking import typed_ranked_product_batch_sha256
from src.search_v2.typed_ranking import typed_ranking_profile_sha256
from src.search_v2.usage_ledger import UsageAmount
from src.search_v2.usage_ledger import UsageReservation
from src.search_v2.usage_ledger import UsageReservationRequest


NOW = datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc)


@dataclass(frozen=True, slots=True)
class PipelineContext:
    intent: NormalizedSearchIntent
    query_plan: SearchQueryPlan
    typed_proposal: TypedRequirementProposal
    approval_plan: SearchApprovalPlan
    session: SearchSessionSnapshot
    execution: OutscraperProductExecution
    normalization_profile: ProductNormalizationProfile


def normalized_intent() -> NormalizedSearchIntent:
    source_input = "5万円以内の黒い軽量ワイヤレスヘッドホン。中古は避けたい。"
    draft = SearchIntentDraft.model_validate(
        {
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
            "brand": None,
            "model_number": None,
            "price": {
                "currency": "JPY",
                "mode": "max",
                "target_jpy": None,
                "min_jpy": None,
                "max_jpy": 50_000,
                "source": "explicit",
                "confidence": None,
            },
            "typed_conditions": [
                {
                    "attribute_key": "色",
                    "operator": "equals",
                    "expected_value": {"value_type": "enum", "values": ["黒"]},
                    "strength": "required",
                }
            ],
            "ambiguities": [],
        }
    )
    provenance = build_intent_provenance(
        source_input=source_input,
        prompt=b"prompt",
        schema=b"schema",
        response=b"response",
    )
    return normalize_search_intent(source_input, draft, provenance=provenance)


def usage_allowances() -> list[ApprovedUsage]:
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


def pipeline_context(*, data: list[object] | None = None) -> PipelineContext:
    intent = normalized_intent()
    query_plan = build_search_query_plan(intent)
    typed_proposal = build_typed_requirement_proposal(intent)
    request = build_outscraper_request(query_plan, postal_code="100-0001")
    usage_policy_digest = "d" * 64
    runtime = SearchRuntimeBindings(
        bonsai_model_id="local-bonsai-model",
        bonsai_prompt_sha256=intent.provenance.prompt_sha256,
        bonsai_schema_sha256=intent.provenance.schema_sha256,
        cloudflare_model_id=None,
        image_prompt_sha256=None,
        ranking_profile_id="typed-ranking-v4",
        ranking_profile_sha256=typed_ranking_profile_sha256(),
        product_evidence_profile_sha256=product_evidence_profile_sha256(),
        implementation_sha256="e" * 64,
        usage_policy_sha256=usage_policy_digest,
    )
    approval_plan = build_search_approval_plan(
        owner_id="owner-1",
        session_id="session-1",
        intent=intent,
        query_plan=query_plan,
        outscraper_request_sha256=outscraper_request_sha256(request),
        image_set_sha256=None,
        image_request_metadata_sha256=None,
        usage_allowances=usage_allowances(),
        runtime_bindings=runtime,
        created_at=NOW,
    )
    plan_digest = search_approval_plan_sha256(approval_plan)
    consumed_at = NOW + timedelta(seconds=4)
    session = SearchSessionSnapshot(
        schema_version="3.0",
        owner_id="owner-1",
        session_id="session-1",
        revision=7,
        state="scrape_submitted",
        intent_sha256=approval_plan.intent_sha256,
        query_plan_sha256=search_query_plan_sha256(query_plan),
        typed_requirement_proposal_sha256=typed_requirement_proposal_sha256(typed_proposal),
        typed_requirement_status="ready",
        image_mode="off",
        image_attempts_started=0,
        active_image_reservation_id=None,
        image_set_sha256=None,
        image_request_metadata_sha256=None,
        usage_policy_sha256=None,
        approval=SearchApprovalGrant(
            plan_sha256=plan_digest,
            token_sha256="f" * 64,
            issued_at=NOW + timedelta(seconds=1),
            expires_at=approval_plan.expires_at,
            consumed_at=consumed_at,
        ),
        created_at=NOW,
        updated_at=consumed_at,
    )
    reservation = UsageReservation(
        reservation_id="r" * 32,
        request=UsageReservationRequest(
            provider="outscraper",
            operation="product_search",
            owner_id=session.owner_id,
            session_id=session.session_id,
            binding_sha256=plan_digest,
            amount=UsageAmount(calls=1, tokens=0, cost_microusd=10_000),
            pricing_policy_sha256="c" * 64,
        ),
        usage_policy_sha256=usage_policy_digest,
        status="succeeded",
        reserved_at=NOW + timedelta(seconds=2),
        started_at=NOW + timedelta(seconds=5),
        finished_at=NOW + timedelta(seconds=6),
    )
    if data is None:
        ja_query = query_plan.queries[0].value
        data = [
            [
                {
                    "query": ja_query,
                    "name": "中古 ワイヤレスヘッドホン",
                    "price": 48_000,
                    "currency": "JPY",
                },
                {
                    "query": ja_query,
                    "name": "黒 軽量 ワイヤレスヘッドホン",
                    "categories": ["オーディオ"],
                    "color": "黒",
                    "features": ["軽量", "ノイズキャンセリング"],
                    "price": 40_000,
                    "currency": "JPY",
                },
            ],
            [],
        ]
    execution = OutscraperProductExecution(
        request=request,
        provider_request_id="request-1",
        response={"data": data},
        polls_performed=2,
        usage_reservation=reservation,
    )
    normalization_profile = ProductNormalizationProfile(
        schema_version="2.0",
        profile_id="observed-only-v2",
        usd_to_jpy_rate=160,
    )
    return PipelineContext(
        intent=intent,
        query_plan=query_plan,
        typed_proposal=typed_proposal,
        approval_plan=approval_plan,
        session=session,
        execution=execution,
        normalization_profile=normalization_profile,
    )


def complete(context: PipelineContext):
    return product_pipeline.complete_product_search(
        context.session,
        execution=context.execution,
        approval_plan=context.approval_plan,
        intent=context.intent,
        query_plan=context.query_plan,
        typed_proposal=context.typed_proposal,
        normalization_profile=context.normalization_profile,
        expected_revision=context.session.revision,
        now=NOW + timedelta(seconds=7),
    )


def test_completed_execution_is_normalized_ranked_and_bound_to_final_state() -> None:
    context = pipeline_context()

    result = complete(context)

    assert result.outcome == "results"
    assert result.schema_version == "3.0"
    assert result.normalized_batch is not None
    assert result.ranked_batch is not None
    assert isinstance(result.ranked_batch, TypedRankedProductBatch)
    assert result.ranked_batch.ranking_profile_id == "typed-ranking-v4"
    assert [item.product.title for item in result.ranked_batch.products] == [
        "黒 軽量 ワイヤレスヘッドホン",
        "中古 ワイヤレスヘッドホン",
    ]
    session = result.session
    assert session.state == "search_completed"
    assert session.revision == context.session.revision + 3
    assert session.received_candidate_count == 2
    assert session.normalized_product_count == 2
    assert session.rejected_candidate_count == 0
    assert session.ranked_product_count == 2
    assert session.result_outcome == "results"
    assert session.normalized_product_batch_sha256 == normalized_product_batch_sha256(
        result.normalized_batch
    )
    assert session.ranked_product_batch_sha256 == typed_ranked_product_batch_sha256(
        result.ranked_batch
    )
    assert session.failure_stage is None
    assert session.failure_code is None

    state_json = session.model_dump_json()
    assert context.execution.provider_request_id not in state_json
    assert context.execution.request.postal_code not in state_json
    assert context.query_plan.queries[0].value not in state_json
    assert result.ranked_batch.products[0].product.title not in state_json
    assert result.ranked_batch.products[0].product.title not in repr(result)


def test_empty_provider_result_is_a_successful_empty_completion() -> None:
    context = pipeline_context(data=[])

    result = complete(context)

    assert result.outcome == "empty"
    assert result.session.state == "search_completed"
    assert result.session.received_candidate_count == 0
    assert result.session.normalized_product_count == 0
    assert result.session.rejected_candidate_count == 0
    assert result.session.ranked_product_count == 0
    assert result.session.result_outcome == "empty"
    assert result.normalized_batch is not None
    assert result.normalized_batch.products == ()
    assert result.ranked_batch is not None
    assert result.ranked_batch.products == ()


def test_all_rejected_candidates_are_a_successful_empty_completion() -> None:
    context = pipeline_context(data=[[{"name": ""}], []])

    result = complete(context)

    assert result.outcome == "empty"
    assert result.session.received_candidate_count == 1
    assert result.session.normalized_product_count == 0
    assert result.session.rejected_candidate_count == 1
    assert result.session.ranked_product_count == 0
    assert result.normalized_batch is not None
    assert result.normalized_batch.rejections[0].reason == "missing_title"


def test_provider_execution_failure_has_a_separate_fixed_failure_state() -> None:
    context = pipeline_context()

    result = product_pipeline.fail_product_search(
        context.session,
        approval_plan=context.approval_plan,
        expected_revision=context.session.revision,
        now=NOW + timedelta(seconds=7),
    )

    assert result.outcome == "failed"
    assert result.normalized_batch is None
    assert result.ranked_batch is None
    assert result.session.state == "search_failed"
    assert result.session.failure_stage == "product_search"
    assert result.session.failure_code == "product_search_failed"
    assert result.session.result_outcome is None
    assert result.session.received_candidate_count is None


def test_normalization_contract_failure_returns_only_a_fixed_failure_state() -> None:
    leaked_provider_text = "provider-secret-must-not-appear"
    data: list[object] = [[] for _index in range(49)]
    data[0] = [{"name": leaked_provider_text}]
    context = pipeline_context(data=data)

    result = complete(context)

    assert result.outcome == "failed"
    assert result.normalized_batch is None
    assert result.ranked_batch is None
    assert result.session.state == "search_failed"
    assert result.session.failure_stage == "product_normalization"
    assert result.session.failure_code == "product_normalization_failed"
    assert result.session.received_candidate_count == 1
    assert leaked_provider_text not in result.session.model_dump_json()
    assert leaked_provider_text not in repr(result)


def test_ranking_failure_retains_only_the_normalized_batch_and_fixed_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = pipeline_context()
    leaked_error = "ranking-internal-secret"

    def fail_ranking(*_args, **_kwargs):
        raise TypedRankingError(leaked_error)

    monkeypatch.setattr(product_pipeline, "rank_typed_product_batch", fail_ranking)

    result = complete(context)

    assert result.outcome == "failed"
    assert result.normalized_batch is not None
    assert result.ranked_batch is None
    assert result.session.state == "search_failed"
    assert result.session.failure_stage == "ranking"
    assert result.session.failure_code == "ranking_failed"
    assert result.session.normalized_product_batch_sha256 == normalized_product_batch_sha256(
        result.normalized_batch
    )
    assert result.session.ranked_product_batch_sha256 is None
    assert leaked_error not in result.session.model_dump_json()
    assert leaked_error not in repr(result)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda context: replace(
            context.execution,
            request=build_outscraper_request(context.query_plan, postal_code="999-9999"),
        ),
        lambda context: replace(
            context.execution,
            response={"data": [], "provider_debug": "must-not-leak"},
        ),
        lambda context: replace(
            context.execution,
            polls_performed=51,
        ),
        lambda context: replace(
            context.execution,
            usage_reservation=context.execution.usage_reservation.model_copy(
                update={"status": "failed"}
            ),
        ),
    ],
)
def test_tampered_execution_is_rejected_before_product_processing(mutate) -> None:
    context = pipeline_context()
    changed = replace(context, execution=mutate(context))

    with pytest.raises(product_pipeline.ProductSearchPipelineError) as exc_info:
        complete(changed)

    assert str(exc_info.value) == "Product search pipeline inputs are invalid"
    assert exc_info.value.__cause__ is None
    assert "must-not-leak" not in repr(exc_info.value)


def test_mismatched_approval_plan_and_stale_revision_are_rejected() -> None:
    context = pipeline_context()
    changed_plan = context.approval_plan.model_copy(update={"outscraper_request_sha256": "0" * 64})

    with pytest.raises(product_pipeline.ProductSearchPipelineError):
        product_pipeline.complete_product_search(
            context.session,
            execution=context.execution,
            approval_plan=changed_plan,
            intent=context.intent,
            query_plan=context.query_plan,
            typed_proposal=context.typed_proposal,
            normalization_profile=context.normalization_profile,
            expected_revision=context.session.revision,
            now=NOW + timedelta(seconds=7),
        )

    with pytest.raises(product_pipeline.ProductSearchPipelineError):
        product_pipeline.complete_product_search(
            context.session,
            execution=context.execution,
            approval_plan=context.approval_plan,
            intent=context.intent,
            query_plan=context.query_plan,
            typed_proposal=context.typed_proposal,
            normalization_profile=context.normalization_profile,
            expected_revision=context.session.revision - 1,
            now=NOW + timedelta(seconds=7),
        )


def test_completed_state_rejects_inconsistent_counts_outcome_and_digests() -> None:
    result = complete(pipeline_context())
    payload = result.session.model_dump(mode="python")

    for updates in (
        {"normalized_product_count": 1},
        {"ranked_product_count": 0},
        {"result_outcome": "empty"},
        {"ranked_product_batch_sha256": None},
        {"failure_code": "ranking_failed"},
    ):
        with pytest.raises(ValidationError):
            SearchSessionSnapshot.model_validate({**payload, **updates})


def test_pipeline_result_revalidates_nested_final_state() -> None:
    result = complete(pipeline_context())
    forged_session = result.session.model_construct(
        **{
            **result.session.model_dump(mode="python"),
            "result_outcome": "empty",
        }
    )
    payload = result.model_dump(mode="python")
    payload["session"] = forged_session

    with pytest.raises(ValidationError):
        product_pipeline.ProductSearchPipelineResult.model_validate(payload)
