from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

import src.search_v2.holdout_evaluation as holdout_evaluation
from src.search_v2.holdout_evaluation import HOLDOUT_EVALUATION_PROFILE_V1
from src.search_v2.holdout_evaluation import HoldoutCasePrediction
from src.search_v2.holdout_evaluation import HoldoutEvaluationError
from src.search_v2.holdout_evaluation import HoldoutExpectedCondition
from src.search_v2.holdout_evaluation import HoldoutExpectedDecision
from src.search_v2.holdout_evaluation import HoldoutExpectedProduct
from src.search_v2.holdout_evaluation import HoldoutGroundTruthCase
from src.search_v2.holdout_evaluation import HoldoutGroundTruthDataset
from src.search_v2.holdout_evaluation import HoldoutPredictionSet
from src.search_v2.holdout_evaluation import build_holdout_case_prediction
from src.search_v2.holdout_evaluation import evaluate_holdout_predictions
from src.search_v2.holdout_evaluation import holdout_condition_identity_sha256
from src.search_v2.holdout_evaluation import holdout_evaluation_profile_sha256
from src.search_v2.holdout_evaluation import holdout_evaluation_report_sha256
from src.search_v2.holdout_evaluation import holdout_ground_truth_dataset_sha256
from src.search_v2.holdout_evaluation import holdout_prediction_set_sha256
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent
from src.search_v2.outscraper_request import build_outscraper_request
from src.search_v2.product_evidence import normalized_product_candidate_sha256
from src.search_v2.product_normalization import ProductNormalizationProfile
from src.search_v2.product_normalization import normalize_outscraper_products
from src.search_v2.query_planner import build_search_query_plan
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_ranking import rank_typed_product_batch
from src.search_v2.typed_ranking import typed_ranking_profile_sha256
from src.search_v2.typed_requirements import EnumTarget
from src.search_v2.typed_requirements import TypedRequirement
from src.search_v2.typed_requirements import TypedRequirementDraft
from src.search_v2.typed_requirements import normalize_typed_requirements


SOURCE_INPUT = "黒い丸形マウスを探す"


def enum_condition(
    attribute_key: str,
    value: str,
    *,
    strength: str = "required",
) -> dict[str, object]:
    return {
        "attribute_key": attribute_key,
        "operator": "equals",
        "expected_value": {"value_type": "enum", "values": [value]},
        "strength": strength,
    }


def normalized_intent(
    typed_conditions: list[dict[str, object]],
    *,
    source_input: str = SOURCE_INPUT,
    ambiguities: list[dict[str, object]] | None = None,
):
    payload: dict[str, object] = {
        "product_name_ja": "マウス",
        "product_name_en": "mouse",
        "category_ja": None,
        "category_en": None,
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
        "typed_conditions": typed_conditions,
        "ambiguities": ambiguities or [],
    }
    provenance = build_intent_provenance(
        source_input=source_input,
        prompt=b"holdout-synthetic-prompt-v1",
        schema=b'{"type":"object"}',
        response=b'{"synthetic":true}',
    )
    return normalize_search_intent(
        source_input,
        SearchIntentDraft.model_validate(payload),
        provenance=provenance,
    )


PRODUCTS = (
    {
        "name": "黒い丸形マウス",
        "asin": "B000HE0001",
        "features": ["Black", "Round"],
        "rating": 4.6,
        "reviews": 100,
    },
    {
        "name": "マウス",
        "asin": "B000HE0002",
        "rating": 4.8,
        "reviews": 1_000,
    },
    {
        "name": "白い長方形マウス",
        "asin": "B000HE0003",
        "features": ["White", "Rectangular"],
        "rating": 5.0,
        "reviews": 10_000,
    },
)


def ranking_run(
    *,
    conditions: list[dict[str, object]] | None = None,
    products: tuple[dict[str, object], ...] = PRODUCTS,
    source_input: str = SOURCE_INPUT,
):
    intent = normalized_intent(
        conditions or [enum_condition("form.shape", "round")],
        source_input=source_input,
    )
    query_plan = build_search_query_plan(intent)
    request = build_outscraper_request(query_plan, postal_code="100-0001")
    response_data: object = list(products)
    if len(query_plan.queries) > 1:
        response_data = [list(products), []]
    product_batch = normalize_outscraper_products(
        {"data": response_data},
        request=request,
        provider_request_id="task_holdout_synthetic",
        profile=ProductNormalizationProfile(
            schema_version="2.0",
            profile_id="observed-only-v2",
            usd_to_jpy_rate=160,
        ),
    )
    proposal = build_typed_requirement_proposal(intent)
    ranked_batch = rank_typed_product_batch(intent, query_plan, product_batch, proposal)
    return intent, query_plan, proposal, ranked_batch


def expected_condition(
    requirement: TypedRequirement,
    *,
    condition_id: str,
) -> HoldoutExpectedCondition:
    truth_requirement = TypedRequirement.model_validate(
        {
            **requirement.model_dump(mode="python"),
            "requirement_id": condition_id,
        }
    )
    return HoldoutExpectedCondition(
        schema_version="1.0",
        condition_id=condition_id,
        evaluation_scope="typed_exact",
        requirement=truth_requirement,
        condition_identity_sha256=holdout_condition_identity_sha256(truth_requirement),
    )


def extra_color_condition() -> HoldoutExpectedCondition:
    requirement = normalize_typed_requirements(
        (
            TypedRequirementDraft(
                requirement_id="truth-002",
                attribute_key="appearance.color",
                operator="equals",
                expected_value=EnumTarget(value_type="enum", values=("black",)),
                strength="required",
            ),
        )
    )[0]
    return HoldoutExpectedCondition(
        schema_version="1.0",
        condition_id="truth-002",
        evaluation_scope="typed_exact",
        requirement=requirement,
        condition_identity_sha256=holdout_condition_identity_sha256(requirement),
    )


def ground_truth_case(
    *,
    case_id: str = "holdout-mouse-001",
    category: str = "mouse",
    include_color: bool = False,
) -> tuple[HoldoutGroundTruthCase, tuple[object, ...]]:
    intent, query_plan, proposal, ranked_batch = ranking_run()
    conditions = [expected_condition(proposal.requirements[0], condition_id="truth-001")]
    if include_color:
        conditions.append(extra_color_condition())

    products: list[HoldoutExpectedProduct] = []
    for item in ranked_batch.products:
        actual_decision = item.evaluation.decisions[0]
        decisions = [
            HoldoutExpectedDecision(
                condition_id="truth-001",
                expected_state=actual_decision.state,
            )
        ]
        if include_color:
            decisions.append(
                HoldoutExpectedDecision(
                    condition_id="truth-002",
                    expected_state="unknown",
                )
            )
        products.append(
            HoldoutExpectedProduct(
                product_sha256=normalized_product_candidate_sha256(item.product),
                relevance_grade=len(ranked_batch.products) - item.rank,
                decisions=tuple(decisions),
            )
        )

    case = HoldoutGroundTruthCase(
        schema_version="1.0",
        case_id=case_id,
        category=category,
        query_language="ja",
        source_input_sha256=intent.provenance.source_input_sha256,
        expected_conditions=tuple(conditions),
        expected_products=tuple(sorted(products, key=lambda item: item.product_sha256)),
    )
    return case, (intent, query_plan, proposal, ranked_batch)


def ranked_prediction(
    case_id: str,
    run: tuple[object, ...],
) -> HoldoutCasePrediction:
    intent, query_plan, proposal, ranked_batch = run
    return build_holdout_case_prediction(
        case_id=case_id,
        source_input_sha256=intent.provenance.source_input_sha256,
        status="ranked",
        intent=intent,
        query_plan=query_plan,
        proposal=proposal,
        ranked_batch=ranked_batch,
        failure_code=None,
    )


def dataset(
    cases: tuple[HoldoutGroundTruthCase, ...],
    *,
    dataset_id: str = "synthetic-holdout-v1",
) -> HoldoutGroundTruthDataset:
    return HoldoutGroundTruthDataset(
        schema_version="1.0",
        dataset_id=dataset_id,
        dataset_role="holdout",
        provenance_reference_id="synthetic-fixture-v1",
        content_policy="identifiers-digests-labels-only-v1",
        cases=tuple(sorted(cases, key=lambda item: item.case_id)),
    )


def predictions(
    cases: tuple[HoldoutCasePrediction, ...],
    *,
    dataset_id: str = "synthetic-holdout-v1",
) -> HoldoutPredictionSet:
    return HoldoutPredictionSet(
        schema_version="1.0",
        dataset_id=dataset_id,
        content_policy="digests-states-ranks-only-v1",
        evaluation_profile_sha256=holdout_evaluation_profile_sha256(),
        ranking_profile_id="typed-ranking-v4",
        ranking_profile_sha256=typed_ranking_profile_sha256(),
        cases=tuple(sorted(cases, key=lambda item: item.case_id)),
    )


def test_profile_fixes_metric_versions_coverage_and_disabled_image_boundary() -> None:
    profile = HOLDOUT_EVALUATION_PROFILE_V1

    assert profile.profile_id == "typed-ranking-holdout-v1"
    assert profile.ranking_profile_id == "typed-ranking-v4"
    assert profile.ranking_profile_sha256 == typed_ranking_profile_sha256()
    assert profile.minimum_categories == 2
    assert profile.minimum_cases_per_category == 2
    assert profile.minimum_products_per_case == 3
    assert profile.minimum_conditions_per_case == 1
    assert profile.minimum_hard_contradiction_labels == 1
    assert profile.minimum_uncertainty_labels == 1
    assert profile.image_scoring_enabled is False
    assert profile.prediction_projection_version == "digests-states-ranks-only-v1"
    assert len(holdout_evaluation_profile_sha256()) == 64


def test_perfect_ranked_case_reports_separate_exact_and_ranking_metrics() -> None:
    truth_case, run = ground_truth_case()
    truth = dataset((truth_case,))
    prediction = predictions((ranked_prediction(truth_case.case_id, run),))

    report = evaluate_holdout_predictions(truth, prediction)
    case = report.cases[0]

    assert report.quality_decision == "not_assessed"
    assert report.overall.coverage_eligible is False
    assert set(report.overall.coverage_issues) == {
        "too_few_categories",
        "too_few_cases_per_category",
    }
    assert case.status == "ranked"
    assert case.condition_precision == 1.0
    assert case.condition_recall == 1.0
    assert case.condition_f1 == 1.0
    assert case.candidate_precision == 1.0
    assert case.candidate_recall == 1.0
    assert case.decision_accuracy == 1.0
    assert case.hard_contradiction_recall == 1.0
    assert case.uncertainty_preservation == 1.0
    assert case.required_status_accuracy == 1.0
    assert case.pairwise_accuracy == 1.0
    assert case.ndcg == 1.0
    assert report.overall.summary.condition_macro_f1 == 1.0
    assert report.overall.summary.mean_ndcg == 1.0


def test_multiple_categories_become_coverage_eligible_without_a_quality_pass() -> None:
    cases: list[HoldoutGroundTruthCase] = []
    predicted: list[HoldoutCasePrediction] = []
    for case_id, category in (
        ("holdout-mouse-001", "mouse"),
        ("holdout-mouse-002", "mouse"),
        ("holdout-storage-001", "storage"),
        ("holdout-storage-002", "storage"),
    ):
        truth_case, run = ground_truth_case(case_id=case_id, category=category)
        cases.append(truth_case)
        predicted.append(ranked_prediction(case_id, run))

    report = evaluate_holdout_predictions(dataset(tuple(cases)), predictions(tuple(predicted)))

    assert report.overall.coverage_eligible is True
    assert report.overall.coverage_issues == ()
    assert [item.category for item in report.categories] == ["mouse", "storage"]
    assert report.overall.category_macro_condition_f1 == 1.0
    assert report.overall.category_macro_decision_accuracy == 1.0
    assert report.overall.category_macro_pairwise_accuracy == 1.0
    assert report.overall.category_macro_ndcg == 1.0
    assert report.quality_decision == "not_assessed"


def test_missing_condition_stays_in_recall_decision_and_uncertainty_denominators() -> None:
    truth_case, run = ground_truth_case(include_color=True)

    report = evaluate_holdout_predictions(
        dataset((truth_case,)),
        predictions((ranked_prediction(truth_case.case_id, run),)),
    )
    case = report.cases[0]

    assert case.expected_condition_count == 2
    assert case.predicted_condition_count == 1
    assert case.condition_precision == 1.0
    assert case.condition_recall == 0.5
    assert case.condition_f1 == pytest.approx(0.666667)
    assert case.decision_label_count == 6
    assert case.decision_correct_count == 3
    assert case.decision_accuracy == 0.5
    assert case.uncertainty_label_count == 4
    assert case.uncertainty_preserved_count == 1
    assert case.uncertainty_preservation == 0.25


def test_missing_top_product_is_not_dropped_from_candidate_or_ranking_metrics() -> None:
    truth_case, _ = ground_truth_case()
    run_without_top = ranking_run(
        products=(
            {"name": "", "asin": PRODUCTS[0]["asin"]},
            PRODUCTS[1],
            PRODUCTS[2],
        )
    )

    report = evaluate_holdout_predictions(
        dataset((truth_case,)),
        predictions((ranked_prediction(truth_case.case_id, run_without_top),)),
    )
    case = report.cases[0]

    assert case.expected_product_count == 3
    assert case.ranked_product_count == 2
    assert case.matched_product_count == 2
    assert case.candidate_precision == 1.0
    assert case.candidate_recall == pytest.approx(0.666667)
    assert case.pairwise_correct_count < case.pairwise_count
    assert case.pairwise_accuracy < 1.0
    assert case.ndcg < 1.0


def test_unexpected_condition_and_product_reduce_precision() -> None:
    truth_case, _ = ground_truth_case()
    run_with_condition = ranking_run(
        conditions=[
            enum_condition("form.shape", "round"),
            enum_condition("appearance.color", "black"),
        ]
    )
    condition_report = evaluate_holdout_predictions(
        dataset((truth_case,)),
        predictions((ranked_prediction(truth_case.case_id, run_with_condition),)),
    )

    assert condition_report.cases[0].predicted_condition_count == 2
    assert condition_report.cases[0].condition_true_positive_count == 1
    assert condition_report.cases[0].condition_precision == 0.5
    assert condition_report.cases[0].condition_recall == 1.0

    run_with_product = ranking_run(
        products=(
            *PRODUCTS,
            {
                "name": "追加の丸形マウス",
                "asin": "B000HE0004",
                "features": ["Round"],
            },
        )
    )
    product_report = evaluate_holdout_predictions(
        dataset((truth_case,)),
        predictions((ranked_prediction(truth_case.case_id, run_with_product),)),
    )

    assert product_report.cases[0].expected_product_count == 3
    assert product_report.cases[0].ranked_product_count == 4
    assert product_report.cases[0].matched_product_count == 3
    assert product_report.cases[0].candidate_precision == 0.75
    assert product_report.cases[0].candidate_recall == 1.0


def test_equal_relevance_grades_are_excluded_from_strict_pairwise_denominator() -> None:
    truth_case, run = ground_truth_case()
    ranked_batch = run[3]
    top_digests = {
        normalized_product_candidate_sha256(item.product) for item in ranked_batch.products[:2]
    }
    products = tuple(
        HoldoutExpectedProduct(
            product_sha256=item.product_sha256,
            relevance_grade=2 if item.product_sha256 in top_digests else 0,
            decisions=item.decisions,
        )
        for item in truth_case.expected_products
    )
    tied_truth = HoldoutGroundTruthCase.model_validate(
        {
            **truth_case.model_dump(mode="python"),
            "expected_products": products,
        }
    )

    report = evaluate_holdout_predictions(
        dataset((tied_truth,)),
        predictions((ranked_prediction(tied_truth.case_id, run),)),
    )

    assert report.cases[0].pairwise_count == 2
    assert report.cases[0].pairwise_correct_count == 2
    assert report.cases[0].pairwise_accuracy == 1.0
    assert report.cases[0].ndcg == 1.0


def test_blocking_and_failed_cases_remain_in_the_aggregate() -> None:
    first_truth, _ = ground_truth_case(case_id="holdout-mouse-001")
    second_truth, _ = ground_truth_case(case_id="holdout-mouse-002")
    blocking_intent = normalized_intent(
        [
            enum_condition("form.shape", "round"),
            enum_condition("unknown.private_attribute", "private-value"),
        ],
    )
    blocking_query = build_search_query_plan(blocking_intent)
    blocking_proposal = build_typed_requirement_proposal(blocking_intent)
    blocking = build_holdout_case_prediction(
        case_id=first_truth.case_id,
        source_input_sha256=blocking_intent.provenance.source_input_sha256,
        status="blocking",
        intent=blocking_intent,
        query_plan=blocking_query,
        proposal=blocking_proposal,
        ranked_batch=None,
        failure_code=None,
    )
    failed = build_holdout_case_prediction(
        case_id=second_truth.case_id,
        source_input_sha256=second_truth.source_input_sha256,
        status="failed",
        intent=None,
        query_plan=None,
        proposal=None,
        ranked_batch=None,
        failure_code="bonsai-failed",
    )

    report = evaluate_holdout_predictions(
        dataset((first_truth, second_truth)),
        predictions((blocking, failed)),
    )

    assert report.overall.summary.case_count == 2
    assert report.overall.summary.ranked_case_count == 0
    assert report.overall.summary.blocking_case_count == 1
    assert report.overall.summary.failed_case_count == 1
    assert [item.status for item in report.cases] == ["blocking", "failed"]
    assert all(item.pairwise_accuracy == 0.0 for item in report.cases)
    assert all(item.ndcg == 0.0 for item in report.cases)
    assert report.overall.summary.pairwise_accuracy == 0.0
    assert report.overall.summary.mean_ndcg == 0.0


def test_upstream_blocking_ambiguity_can_be_projected_without_a_query_plan() -> None:
    intent = normalized_intent(
        [enum_condition("form.shape", "round")],
        ambiguities=[
            {
                "code": "needs_confirmation",
                "message": "synthetic blocking ambiguity",
                "blocking": True,
            }
        ],
    )
    proposal = build_typed_requirement_proposal(intent)

    prediction = build_holdout_case_prediction(
        case_id="holdout-mouse-003",
        source_input_sha256=intent.provenance.source_input_sha256,
        status="blocking",
        intent=intent,
        query_plan=None,
        proposal=proposal,
        ranked_batch=None,
        failure_code=None,
    )

    assert proposal.status == "blocking"
    assert prediction.status == "blocking"
    assert prediction.intent_sha256 is not None
    assert prediction.query_plan_sha256 is None
    assert prediction.proposal_sha256 is not None
    assert prediction.ranked_batch_sha256 is None
    assert prediction.ranked_products == ()
    assert holdout_prediction_set_sha256(predictions((prediction,))) == (
        holdout_prediction_set_sha256(predictions((prediction,)))
    )


def test_ground_truth_rejects_development_ids_semantic_conditions_and_bad_matrix() -> None:
    truth_case, _ = ground_truth_case()
    payload = truth_case.model_dump(mode="python")
    payload["case_id"] = "case1"
    with pytest.raises(ValidationError):
        HoldoutGroundTruthCase.model_validate(payload)

    semantic = normalize_typed_requirements(
        (
            TypedRequirementDraft(
                requirement_id="truth-003",
                attribute_key="appearance.style",
                operator="similar_to",
                expected_value={"value_type": "semantic", "label": "gaming"},
                strength="preferred",
            ),
        )
    )[0]
    semantic_payload = truth_case.expected_conditions[0].model_dump(mode="python")
    semantic_payload.update(
        {
            "condition_id": "truth-003",
            "requirement": semantic,
            "condition_identity_sha256": holdout_condition_identity_sha256(semantic),
        }
    )
    with pytest.raises(ValidationError):
        HoldoutExpectedCondition.model_validate(semantic_payload)

    product_payload = truth_case.expected_products[0].model_dump(mode="python")
    product_payload["decisions"] = ()
    case_payload = truth_case.model_dump(mode="python")
    case_payload["expected_products"] = tuple(
        [HoldoutExpectedProduct.model_validate(product_payload), *truth_case.expected_products[1:]]
    )
    with pytest.raises(ValidationError):
        HoldoutGroundTruthCase.model_validate(case_payload)


def test_prediction_contract_rejects_inconsistent_status_and_batch() -> None:
    truth_case, run = ground_truth_case()
    valid = ranked_prediction(truth_case.case_id, run)
    payload = valid.model_dump(mode="python")
    payload["status"] = "blocking"

    with pytest.raises(ValidationError):
        HoldoutCasePrediction.model_validate(payload)

    payload = valid.model_dump(mode="python")
    payload["failure_code"] = "private raw exception text is forbidden"
    with pytest.raises(ValidationError):
        HoldoutCasePrediction.model_validate(payload)

    intent, _query_plan, proposal, ranked_batch = run
    with pytest.raises(HoldoutEvaluationError, match="Holdout evaluation inputs"):
        build_holdout_case_prediction(
            case_id=truth_case.case_id,
            source_input_sha256=intent.provenance.source_input_sha256,
            status="ranked",
            intent=intent,
            query_plan=None,
            proposal=proposal,
            ranked_batch=ranked_batch,
            failure_code=None,
        )


def test_prediction_projection_does_not_serialize_query_or_product_text() -> None:
    truth_case, run = ground_truth_case()
    prediction = ranked_prediction(truth_case.case_id, run)

    serialized = prediction.model_dump_json()

    assert prediction.intent_sha256 is not None
    assert prediction.query_plan_sha256 is not None
    assert prediction.proposal_sha256 is not None
    assert prediction.ranked_batch_sha256 is not None
    assert SOURCE_INPUT not in serialized
    assert "黒い丸形マウス" not in serialized
    assert "B000HE0001" not in serialized


def test_evaluator_rejects_dataset_prediction_binding_without_echoing_input() -> None:
    truth_case, run = ground_truth_case()
    truth = dataset((truth_case,))
    prediction = predictions(
        (ranked_prediction(truth_case.case_id, run),),
        dataset_id="different-holdout-v1",
    )

    with pytest.raises(HoldoutEvaluationError, match="Holdout evaluation inputs") as exc_info:
        evaluate_holdout_predictions(truth, prediction)

    assert truth.dataset_id not in str(exc_info.value)
    assert prediction.dataset_id not in str(exc_info.value)


def test_digests_are_deterministic_and_change_with_ground_truth_or_predictions() -> None:
    truth_case, run = ground_truth_case()
    truth = dataset((truth_case,))
    prediction = predictions((ranked_prediction(truth_case.case_id, run),))
    report = evaluate_holdout_predictions(truth, prediction)

    assert holdout_ground_truth_dataset_sha256(truth) == holdout_ground_truth_dataset_sha256(truth)
    assert holdout_prediction_set_sha256(prediction) == holdout_prediction_set_sha256(prediction)
    assert holdout_evaluation_report_sha256(report) == holdout_evaluation_report_sha256(report)

    changed_product = truth_case.expected_products[0].model_copy(
        update={"relevance_grade": truth_case.expected_products[0].relevance_grade + 1}
    )
    changed_case = HoldoutGroundTruthCase.model_validate(
        {
            **truth_case.model_dump(mode="python"),
            "expected_products": tuple(
                sorted(
                    (changed_product, *truth_case.expected_products[1:]),
                    key=lambda item: item.product_sha256,
                )
            ),
        }
    )
    changed_truth = dataset((changed_case,))
    assert holdout_ground_truth_dataset_sha256(changed_truth) != (
        holdout_ground_truth_dataset_sha256(truth)
    )

    tampered_prediction = prediction.model_copy(update={"ranking_profile_sha256": "0" * 64})
    with pytest.raises(HoldoutEvaluationError, match="Holdout evaluation inputs"):
        holdout_prediction_set_sha256(tampered_prediction)

    tampered_case = report.cases[0].model_copy(update={"decision_correct_count": 0})
    tampered_report = report.model_copy(update={"cases": (tampered_case,)})
    with pytest.raises(HoldoutEvaluationError, match="Holdout evaluation inputs"):
        holdout_evaluation_report_sha256(tampered_report)


def test_case_and_dataset_order_must_be_canonical() -> None:
    first, _ = ground_truth_case(case_id="holdout-mouse-001")
    second, _ = ground_truth_case(case_id="holdout-mouse-002")

    with pytest.raises(ValidationError):
        HoldoutGroundTruthDataset(
            schema_version="1.0",
            dataset_id="synthetic-holdout-v1",
            dataset_role="holdout",
            provenance_reference_id="synthetic-fixture-v1",
            content_policy="identifiers-digests-labels-only-v1",
            cases=(second, first),
        )

    payload = first.model_dump(mode="python")
    payload["expected_products"] = tuple(reversed(first.expected_products))
    with pytest.raises(ValidationError):
        HoldoutGroundTruthCase.model_validate(payload)


def test_module_has_no_network_file_reader_dynamic_import_or_callback_boundary() -> None:
    module_path = Path(holdout_evaluation.__file__)
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(module_path))
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert imported_roots.isdisjoint(
        {"aiohttp", "httpx", "requests", "socket", "subprocess", "urllib"}
    )
    assert "importlib" not in imported_roots
    assert "__import__" not in called_names
    assert "open" not in called_names
    assert "Path" not in called_names
    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(argument.arg in {"callback", "client", "transport"} for argument in node.args.args)
        for node in ast.walk(tree)
    )
