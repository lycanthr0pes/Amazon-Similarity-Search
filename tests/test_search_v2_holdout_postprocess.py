from dataclasses import FrozenInstanceError
from dataclasses import fields
import inspect

import pytest

import src.search_v2.holdout_postprocess as holdout_postprocess
from src.search_v2.holdout_evaluation import HoldoutEvaluationError
from src.search_v2.holdout_evaluation import build_holdout_case_prediction
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent
from src.search_v2.outscraper_request import build_outscraper_request
from src.search_v2.product_normalization import ProductNormalizationProfile
from src.search_v2.product_normalization import normalize_outscraper_products
from src.search_v2.typed_intent_adapter import TypedIntentAdapterError
from src.search_v2.typed_ranking import TypedRankingError


def enum_condition(attribute_key: str, value: str) -> dict[str, object]:
    return {
        "attribute_key": attribute_key,
        "operator": "equals",
        "expected_value": {"value_type": "enum", "values": [value]},
        "strength": "required",
    }


def normalized_intent(*, blocking: bool = False):
    source_input = "synthetic holdout input"
    payload = {
        "product_name_ja": None,
        "product_name_en": "mouse",
        "category_ja": None,
        "category_en": "computer accessories",
        "required_terms_ja": [],
        "required_terms_en": [],
        "preferred_terms_ja": [],
        "preferred_terms_en": [],
        "negative_terms_ja": [],
        "negative_terms_en": [],
        "color_ja": None,
        "color_en": None,
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
        "typed_conditions": [enum_condition("form.shape", "round")],
        "ambiguities": (
            [
                {
                    "code": "needs_confirmation",
                    "message": "private-marker-that-must-not-be-retained",
                    "blocking": True,
                }
            ]
            if blocking
            else []
        ),
    }
    provenance = build_intent_provenance(
        source_input=source_input,
        prompt=b"synthetic-prompt",
        schema=b"synthetic-schema",
        response=b"synthetic-response",
    )
    return normalize_search_intent(
        source_input,
        SearchIntentDraft.model_validate(payload),
        provenance=provenance,
    )


def product_batch(intent, query_plan):
    request = build_outscraper_request(query_plan, postal_code="100-0001")
    products = [
        {
            "name": "synthetic product",
            "features": ["Round"],
        }
    ]
    response_data = products if len(query_plan.queries) == 1 else [products, []]
    return normalize_outscraper_products(
        {"data": response_data},
        request=request,
        provider_request_id="synthetic-postprocess",
        profile=ProductNormalizationProfile(
            schema_version="2.0",
            profile_id="observed-only-v2",
            usd_to_jpy_rate=160,
        ),
    )


def ready_artifacts():
    intent = normalized_intent()
    proposal = holdout_postprocess.build_postprocess_proposal(intent)
    query_plan = holdout_postprocess.build_postprocess_query(intent, proposal)
    assert query_plan is not None
    batch = product_batch(intent, query_plan)
    ranked = holdout_postprocess.rank_postprocess_batch(
        intent,
        query_plan,
        batch,
        proposal,
    )
    return intent, proposal, query_plan, batch, ranked


def test_diagnostic_is_frozen_strict_and_contains_only_a_fixed_stage() -> None:
    diagnostic_type = holdout_postprocess.HoldoutPostprocessDiagnostic
    diagnostic = diagnostic_type(stage="typed_proposal_invalid")

    assert tuple(field.name for field in fields(diagnostic_type)) == ("stage",)
    with pytest.raises(FrozenInstanceError):
        diagnostic.stage = "query_plan_invalid"
    with pytest.raises((TypeError, ValueError)):
        diagnostic_type(stage="private-provider-error")


def test_ready_path_reaches_ranked_prediction_without_network_or_callbacks() -> None:
    intent, proposal, query_plan, _batch, ranked = ready_artifacts()

    prediction = holdout_postprocess.project_postprocess_case(
        case_id="holdout-synthetic-001",
        source_input_sha256=intent.provenance.source_input_sha256,
        status="ranked",
        intent=intent,
        query_plan=query_plan,
        proposal=proposal,
        ranked_batch=ranked,
        failure_code=None,
    )

    assert prediction.status == "ranked"
    assert prediction.query_plan_sha256 is not None
    assert len(prediction.ranked_products) == 1
    assert prediction == build_holdout_case_prediction(
        case_id="holdout-synthetic-001",
        source_input_sha256=intent.provenance.source_input_sha256,
        status="ranked",
        intent=intent,
        query_plan=query_plan,
        proposal=proposal,
        ranked_batch=ranked,
        failure_code=None,
    )

    signatures = {
        name: tuple(inspect.signature(getattr(holdout_postprocess, name)).parameters)
        for name in (
            "build_postprocess_proposal",
            "build_postprocess_query",
            "rank_postprocess_batch",
            "project_postprocess_case",
        )
    }
    assert signatures == {
        "build_postprocess_proposal": ("intent",),
        "build_postprocess_query": ("intent", "proposal"),
        "rank_postprocess_batch": (
            "intent",
            "query_plan",
            "product_batch",
            "proposal",
        ),
        "project_postprocess_case": (
            "case_id",
            "source_input_sha256",
            "status",
            "intent",
            "query_plan",
            "proposal",
            "ranked_batch",
            "failure_code",
        ),
    }


def test_upstream_blocking_ambiguity_skips_query_and_projects_as_blocking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    intent = normalized_intent(blocking=True)
    proposal = holdout_postprocess.build_postprocess_proposal(intent)

    def must_not_run(*_args, **_kwargs):
        raise AssertionError("query planning started")

    monkeypatch.setattr(holdout_postprocess, "build_search_query_plan", must_not_run)

    query_plan = holdout_postprocess.build_postprocess_query(intent, proposal)
    prediction = holdout_postprocess.project_postprocess_case(
        case_id="holdout-synthetic-002",
        source_input_sha256=intent.provenance.source_input_sha256,
        status="blocking",
        intent=intent,
        query_plan=query_plan,
        proposal=proposal,
        ranked_batch=None,
        failure_code=None,
    )

    assert proposal.status == "blocking"
    assert query_plan is None
    assert prediction.status == "blocking"
    assert prediction.intent_sha256 is not None
    assert prediction.query_plan_sha256 is None
    assert prediction.proposal_sha256 is not None
    assert prediction.ranked_batch_sha256 is None
    assert prediction.ranked_products == ()


@pytest.mark.parametrize(
    ("function_name", "expected_stage"),
    [
        ("build_typed_requirement_proposal", "typed_proposal_invalid"),
        ("build_search_query_plan", "query_plan_invalid"),
    ],
)
def test_preparation_failure_exposes_only_its_fixed_stage(
    monkeypatch: pytest.MonkeyPatch,
    function_name: str,
    expected_stage: str,
) -> None:
    intent = normalized_intent()
    proposal = None
    if function_name == "build_search_query_plan":
        proposal = holdout_postprocess.build_postprocess_proposal(intent)

    def fail(*_args, **_kwargs):
        if function_name == "build_typed_requirement_proposal":
            raise TypedIntentAdapterError("private-provider-error")
        raise ValueError("private-query-and-product-data")

    monkeypatch.setattr(holdout_postprocess, function_name, fail)
    error_type = holdout_postprocess.HoldoutPostprocessError
    with pytest.raises(error_type) as captured:
        if proposal is None:
            holdout_postprocess.build_postprocess_proposal(intent)
        else:
            holdout_postprocess.build_postprocess_query(intent, proposal)

    assert str(captured.value) == "Holdout post-processing did not complete"
    assert captured.value.diagnostic.stage == expected_stage
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert "private" not in repr(captured.value)
    assert "private" not in repr(captured.value.diagnostic)


def test_ranking_failure_exposes_only_fixed_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    intent, proposal, query_plan, batch, _ranked = ready_artifacts()

    def fail(*_args, **_kwargs):
        raise TypedRankingError("private-product-data")

    monkeypatch.setattr(holdout_postprocess, "rank_typed_product_batch", fail)
    with pytest.raises(holdout_postprocess.HoldoutPostprocessError) as captured:
        holdout_postprocess.rank_postprocess_batch(
            intent,
            query_plan,
            batch,
            proposal,
        )

    assert captured.value.diagnostic.stage == "typed_ranking_invalid"
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert "private" not in repr(captured.value)


def test_projection_failure_exposes_only_fixed_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    intent, proposal, query_plan, _batch, ranked = ready_artifacts()

    def fail(**_kwargs):
        raise HoldoutEvaluationError("private-evaluation-data")

    monkeypatch.setattr(holdout_postprocess, "build_holdout_case_prediction", fail)
    with pytest.raises(holdout_postprocess.HoldoutPostprocessError) as captured:
        holdout_postprocess.project_postprocess_case(
            case_id="holdout-synthetic-003",
            source_input_sha256=intent.provenance.source_input_sha256,
            status="ranked",
            intent=intent,
            query_plan=query_plan,
            proposal=proposal,
            ranked_batch=ranked,
            failure_code=None,
        )

    assert captured.value.diagnostic.stage == "prediction_projection_invalid"
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert "private" not in repr(captured.value)
