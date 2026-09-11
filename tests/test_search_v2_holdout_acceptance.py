from __future__ import annotations

import inspect
from typing import Any

import pytest
from pydantic import ValidationError

import src.search_v2.holdout_acceptance as acceptance_module
from src.search_v2.holdout_acceptance import HOLDOUT_ACCEPTANCE_POLICY_V1
from src.search_v2.holdout_acceptance import HoldoutAcceptanceAssessment
from src.search_v2.holdout_acceptance import HoldoutAcceptanceCheck
from src.search_v2.holdout_acceptance import HoldoutAcceptanceError
from src.search_v2.holdout_acceptance import HoldoutAcceptancePolicy
from src.search_v2.holdout_acceptance import assess_holdout_quality
from src.search_v2.holdout_acceptance import holdout_acceptance_assessment_sha256
from src.search_v2.holdout_acceptance import holdout_acceptance_policy_sha256
from src.search_v2.holdout_evaluation import HoldoutCaseMetrics
from src.search_v2.holdout_evaluation import HoldoutCategoryMetrics
from src.search_v2.holdout_evaluation import HoldoutEvaluationReport
from src.search_v2.holdout_evaluation import _overall_metrics
from src.search_v2.holdout_evaluation import _summarize_cases
from src.search_v2.holdout_evaluation import holdout_evaluation_profile_sha256
from src.search_v2.holdout_evaluation import holdout_evaluation_report_sha256
from src.search_v2.typed_ranking import typed_ranking_profile_sha256


INVALID_MESSAGE = "Holdout acceptance inputs did not match the acceptance contract"


def ratio(numerator: int, denominator: int, *, empty: float = 0.0) -> float:
    if denominator == 0:
        return empty
    return float(round(numerator / denominator, 6))


def f1(precision: float, recall: float) -> float:
    if precision + recall == 0.0:
        return 0.0
    return float(round(2.0 * precision * recall / (precision + recall), 6))


def case_metrics(
    case_id: str,
    category: str,
    *,
    status: str = "ranked",
    expected_conditions: int = 20,
    predicted_conditions: int = 20,
    condition_matches: int = 20,
    expected_products: int = 20,
    ranked_products: int = 20,
    matched_products: int = 20,
    decision_labels: int = 20,
    decision_correct: int = 20,
    hard_labels: int = 1,
    hard_detected: int = 1,
    uncertainty_labels: int = 1,
    uncertainty_preserved: int = 1,
    required_labels: int = 20,
    required_correct: int = 20,
    pairwise_count: int = 20,
    pairwise_correct: int = 20,
    ndcg: float = 1.0,
) -> HoldoutCaseMetrics:
    if status != "ranked":
        ranked_products = 0
        matched_products = 0
        decision_correct = 0
        hard_detected = 0
        uncertainty_preserved = 0
        required_correct = 0
        pairwise_correct = 0
        ndcg = 0.0
    condition_precision = ratio(
        condition_matches,
        predicted_conditions,
        empty=1.0 if expected_conditions == 0 else 0.0,
    )
    condition_recall = ratio(condition_matches, expected_conditions, empty=1.0)
    return HoldoutCaseMetrics(
        schema_version="1.0",
        case_id=case_id,
        category=category,
        status=status,
        expected_condition_count=expected_conditions,
        predicted_condition_count=predicted_conditions,
        condition_true_positive_count=condition_matches,
        condition_precision=condition_precision,
        condition_recall=condition_recall,
        condition_f1=f1(condition_precision, condition_recall),
        expected_product_count=expected_products,
        ranked_product_count=ranked_products,
        matched_product_count=matched_products,
        candidate_precision=ratio(matched_products, ranked_products),
        candidate_recall=ratio(matched_products, expected_products),
        decision_label_count=decision_labels,
        decision_correct_count=decision_correct,
        decision_accuracy=ratio(decision_correct, decision_labels),
        hard_contradiction_label_count=hard_labels,
        hard_contradiction_detected_count=hard_detected,
        hard_contradiction_recall=(None if hard_labels == 0 else ratio(hard_detected, hard_labels)),
        uncertainty_label_count=uncertainty_labels,
        uncertainty_preserved_count=uncertainty_preserved,
        uncertainty_preservation=(
            None if uncertainty_labels == 0 else ratio(uncertainty_preserved, uncertainty_labels)
        ),
        required_status_label_count=required_labels,
        required_status_correct_count=required_correct,
        required_status_accuracy=ratio(required_correct, required_labels),
        pairwise_count=pairwise_count,
        pairwise_correct_count=pairwise_correct,
        pairwise_accuracy=ratio(pairwise_correct, pairwise_count),
        ndcg=ndcg,
    )


def four_cases(**overrides: Any) -> tuple[HoldoutCaseMetrics, ...]:
    return tuple(
        case_metrics(case_id, category, **overrides)
        for case_id, category in (
            ("holdout-alpha-001", "alpha"),
            ("holdout-alpha-002", "alpha"),
            ("holdout-beta-001", "beta"),
            ("holdout-beta-002", "beta"),
        )
    )


def evaluation_report(
    cases: tuple[HoldoutCaseMetrics, ...] | None = None,
) -> HoldoutEvaluationReport:
    selected = (
        four_cases() if cases is None else tuple(sorted(cases, key=lambda item: item.case_id))
    )
    categories = tuple(
        HoldoutCategoryMetrics(
            category=category,
            summary=_summarize_cases(tuple(item for item in selected if item.category == category)),
        )
        for category in sorted({item.category for item in selected})
    )
    return HoldoutEvaluationReport(
        schema_version="1.0",
        profile_id="typed-ranking-holdout-v1",
        profile_sha256=holdout_evaluation_profile_sha256(),
        dataset_id="unseen-synthetic-holdout-v1",
        dataset_sha256="a" * 64,
        prediction_set_sha256="b" * 64,
        ranking_profile_id="typed-ranking-v4",
        ranking_profile_sha256=typed_ranking_profile_sha256(),
        quality_decision="not_assessed",
        cases=selected,
        categories=categories,
        overall=_overall_metrics(selected, categories),
    )


def find_check(
    assessment: HoldoutAcceptanceAssessment,
    metric: str,
    *,
    scope: str,
    category: str | None = None,
) -> HoldoutAcceptanceCheck:
    matches = [
        item
        for item in assessment.checks
        if item.metric == metric and item.scope == scope and item.category == category
    ]
    assert len(matches) == 1
    return matches[0]


def test_policy_fixes_profiles_thresholds_and_category_safety_coverage() -> None:
    policy = HOLDOUT_ACCEPTANCE_POLICY_V1

    assert policy.schema_version == "1.0"
    assert policy.policy_id == "typed-ranking-holdout-acceptance-v1"
    assert policy.evaluation_profile_id == "typed-ranking-holdout-v1"
    assert policy.evaluation_profile_sha256 == holdout_evaluation_profile_sha256()
    assert policy.ranking_profile_id == "typed-ranking-v4"
    assert policy.ranking_profile_sha256 == typed_ranking_profile_sha256()
    assert policy.metric_decimals == 6
    assert policy.require_all_categories is True
    assert policy.minimum_hard_contradiction_labels_per_category == 1
    assert policy.minimum_uncertainty_labels_per_category == 1
    assert policy.maximum_blocking_case_count == 0
    assert policy.maximum_failed_case_count == 0
    assert policy.minimum_condition_f1 == 0.90
    assert policy.minimum_condition_macro_f1 == 0.90
    assert policy.minimum_candidate_precision == 0.85
    assert policy.minimum_candidate_recall == 0.90
    assert policy.minimum_candidate_macro_recall == 0.90
    assert policy.minimum_decision_accuracy == 0.90
    assert policy.minimum_decision_macro_accuracy == 0.90
    assert policy.minimum_hard_contradiction_recall == 1.0
    assert policy.minimum_uncertainty_preservation == 1.0
    assert policy.minimum_required_status_accuracy == 1.0
    assert policy.minimum_required_status_macro_accuracy == 1.0
    assert policy.minimum_pairwise_accuracy == 0.85
    assert policy.minimum_pairwise_macro_accuracy == 0.85
    assert policy.minimum_mean_ndcg == 0.90
    assert len(holdout_acceptance_policy_sha256()) == 64
    assert holdout_acceptance_policy_sha256() == holdout_acceptance_policy_sha256(policy)


def test_perfect_eligible_report_passes_without_mutating_raw_quality_decision() -> None:
    report = evaluation_report()

    assessment = assess_holdout_quality(report)

    assert report.quality_decision == "not_assessed"
    assert assessment.decision == "pass"
    assert assessment.policy_sha256 == holdout_acceptance_policy_sha256()
    assert assessment.evaluation_report_sha256 == holdout_evaluation_report_sha256(report)
    assert assessment.dataset_sha256 == report.dataset_sha256
    assert assessment.prediction_set_sha256 == report.prediction_set_sha256
    assert assessment.evaluation_profile_sha256 == report.profile_sha256
    assert assessment.ranking_profile_sha256 == report.ranking_profile_sha256
    assert all(item.passed for item in assessment.checks)
    assert len(holdout_acceptance_assessment_sha256(assessment)) == 64

    serialized = assessment.model_dump_json()
    for forbidden in (
        "query",
        "product_name",
        "title",
        "asin",
        "provider_response",
        "raw_error",
    ):
        assert forbidden not in serialized.casefold()


@pytest.mark.parametrize(
    ("overrides", "metric", "observed"),
    (
        ({"condition_matches": 18}, "condition_f1", 0.90),
        (
            {"expected_products": 18, "ranked_products": 20, "matched_products": 17},
            "candidate_precision",
            0.85,
        ),
        (
            {"expected_products": 20, "ranked_products": 20, "matched_products": 18},
            "candidate_recall",
            0.90,
        ),
        ({"decision_correct": 18}, "decision_accuracy", 0.90),
        ({"pairwise_correct": 17}, "pairwise_accuracy", 0.85),
        ({"ndcg": 0.90}, "mean_ndcg", 0.90),
    ),
)
def test_threshold_boundary_is_inclusive(
    overrides: dict[str, object],
    metric: str,
    observed: float,
) -> None:
    assessment = assess_holdout_quality(evaluation_report(four_cases(**overrides)))

    assert assessment.decision == "pass"
    check = find_check(assessment, metric, scope="overall")
    assert check.observed == observed
    assert check.passed is True


@pytest.mark.parametrize(
    ("overrides", "metric"),
    (
        ({"condition_matches": 17}, "condition_f1"),
        (
            {"expected_products": 16, "ranked_products": 19, "matched_products": 16},
            "candidate_precision",
        ),
        (
            {"expected_products": 20, "ranked_products": 17, "matched_products": 17},
            "candidate_recall",
        ),
        ({"decision_correct": 17}, "decision_accuracy"),
        ({"hard_detected": 0}, "hard_contradiction_recall"),
        ({"uncertainty_preserved": 0}, "uncertainty_preservation"),
        ({"required_correct": 19}, "required_status_accuracy"),
        ({"pairwise_correct": 16}, "pairwise_accuracy"),
        ({"ndcg": 0.899999}, "mean_ndcg"),
    ),
)
def test_one_unmet_quality_rule_fails_without_weighted_compensation(
    overrides: dict[str, object],
    metric: str,
) -> None:
    assessment = assess_holdout_quality(evaluation_report(four_cases(**overrides)))

    assert assessment.decision == "fail"
    assert find_check(assessment, metric, scope="overall").passed is False


def test_one_weak_category_fails_even_when_overall_pairwise_metrics_pass() -> None:
    cases = (
        case_metrics("holdout-alpha-001", "alpha", pairwise_correct=16),
        case_metrics("holdout-alpha-002", "alpha", pairwise_correct=16),
        case_metrics("holdout-beta-001", "beta"),
        case_metrics("holdout-beta-002", "beta"),
    )

    assessment = assess_holdout_quality(evaluation_report(cases))

    assert find_check(assessment, "pairwise_accuracy", scope="overall").passed is True
    assert (
        find_check(
            assessment,
            "pairwise_accuracy",
            scope="category",
            category="alpha",
        ).passed
        is False
    )
    assert assessment.decision == "fail"


def test_category_case_macro_failure_is_not_hidden_by_passing_micro_and_overall() -> None:
    cases = (
        case_metrics(
            "holdout-alpha-001",
            "alpha",
            expected_conditions=10,
            predicted_conditions=10,
            condition_matches=7,
        ),
        case_metrics(
            "holdout-alpha-002",
            "alpha",
            expected_conditions=100,
            predicted_conditions=100,
            condition_matches=100,
        ),
        case_metrics("holdout-beta-001", "beta"),
        case_metrics("holdout-beta-002", "beta"),
    )

    assessment = assess_holdout_quality(evaluation_report(cases))

    assert find_check(assessment, "condition_f1", scope="overall").passed is True
    assert find_check(assessment, "condition_macro_f1", scope="overall").passed is True
    assert (
        find_check(
            assessment,
            "condition_f1",
            scope="category",
            category="alpha",
        ).passed
        is True
    )
    assert (
        find_check(
            assessment,
            "condition_macro_f1",
            scope="category",
            category="alpha",
        ).passed
        is False
    )
    assert assessment.decision == "fail"


def test_evaluation_coverage_failure_is_ineligible() -> None:
    report = evaluation_report(
        (
            case_metrics("holdout-alpha-001", "alpha"),
            case_metrics("holdout-alpha-002", "alpha"),
        )
    )

    assessment = assess_holdout_quality(report)

    assert report.overall.coverage_eligible is False
    assert assessment.decision == "ineligible"
    assert find_check(assessment, "coverage_eligible", scope="overall").passed is False


@pytest.mark.parametrize(
    ("overrides", "metric"),
    (
        (
            {"hard_labels": 0, "hard_detected": 0},
            "hard_contradiction_label_count",
        ),
        (
            {"uncertainty_labels": 0, "uncertainty_preserved": 0},
            "uncertainty_label_count",
        ),
    ),
)
def test_missing_safety_labels_in_one_category_is_ineligible(
    overrides: dict[str, object],
    metric: str,
) -> None:
    cases = (
        case_metrics("holdout-alpha-001", "alpha", **overrides),
        case_metrics("holdout-alpha-002", "alpha", **overrides),
        case_metrics("holdout-beta-001", "beta"),
        case_metrics("holdout-beta-002", "beta"),
    )
    report = evaluation_report(cases)

    assessment = assess_holdout_quality(report)

    assert report.overall.coverage_eligible is True
    assert assessment.decision == "ineligible"
    assert find_check(assessment, metric, scope="category", category="alpha").passed is False


@pytest.mark.parametrize(
    ("status", "metric"), (("blocking", "blocking_case_count"), ("failed", "failed_case_count"))
)
def test_blocking_and_failed_cases_are_quality_failures(status: str, metric: str) -> None:
    cases = (
        case_metrics("holdout-alpha-001", "alpha", status=status),
        case_metrics("holdout-alpha-002", "alpha"),
        case_metrics("holdout-beta-001", "beta"),
        case_metrics("holdout-beta-002", "beta"),
    )

    assessment = assess_holdout_quality(evaluation_report(cases))

    assert assessment.decision == "fail"
    assert find_check(assessment, metric, scope="overall").passed is False


def test_policy_is_strict_frozen_and_only_fixed_policy_is_assessable() -> None:
    payload = HOLDOUT_ACCEPTANCE_POLICY_V1.model_dump()
    with pytest.raises(ValidationError):
        HoldoutAcceptancePolicy.model_validate({**payload, "unknown": True})
    with pytest.raises(ValidationError):
        HoldoutAcceptancePolicy.model_validate({**payload, "minimum_decision_accuracy": "0.90"})
    with pytest.raises(ValidationError):
        HOLDOUT_ACCEPTANCE_POLICY_V1.minimum_decision_accuracy = 0.8  # type: ignore[misc]

    changed = HoldoutAcceptancePolicy.model_validate({**payload, "minimum_decision_accuracy": 0.80})
    assert holdout_acceptance_policy_sha256(changed) != holdout_acceptance_policy_sha256()
    with pytest.raises(HoldoutAcceptanceError, match=f"^{INVALID_MESSAGE}$"):
        assess_holdout_quality(evaluation_report(), policy=changed)


def test_tampered_or_noncanonical_report_is_rejected_with_fixed_message() -> None:
    report = evaluation_report()
    tampered_profile = report.model_copy(update={"profile_sha256": "0" * 64})
    reversed_categories = report.model_copy(
        update={"categories": tuple(reversed(report.categories))}
    )

    for invalid in (tampered_profile, reversed_categories):
        with pytest.raises(HoldoutAcceptanceError, match=f"^{INVALID_MESSAGE}$"):
            assess_holdout_quality(invalid)


def test_assessment_digest_rejects_decision_and_check_order_tampering() -> None:
    assessment = assess_holdout_quality(evaluation_report())
    tampered_decision = assessment.model_copy(update={"decision": "fail"})
    reversed_checks = assessment.model_copy(update={"checks": tuple(reversed(assessment.checks))})

    assert holdout_acceptance_assessment_sha256(assessment) == (
        holdout_acceptance_assessment_sha256(assess_holdout_quality(evaluation_report()))
    )
    for invalid in (tampered_decision, reversed_checks):
        with pytest.raises(HoldoutAcceptanceError, match=f"^{INVALID_MESSAGE}$"):
            holdout_acceptance_assessment_sha256(invalid)


def test_assessment_digest_rejects_inconsistent_check_and_changes_on_valid_tamper() -> None:
    assessment = assess_holdout_quality(evaluation_report())
    first_quality_index = next(
        index
        for index, item in enumerate(assessment.checks)
        if item.metric == "condition_f1" and item.scope == "overall"
    )
    original = assessment.checks[first_quality_index]
    inconsistent = original.model_copy(update={"observed": 0.0})
    invalid_checks = list(assessment.checks)
    invalid_checks[first_quality_index] = inconsistent
    invalid = assessment.model_copy(update={"checks": tuple(invalid_checks)})

    with pytest.raises(HoldoutAcceptanceError, match=f"^{INVALID_MESSAGE}$"):
        holdout_acceptance_assessment_sha256(invalid)

    changed_check = original.model_copy(update={"observed": 0.90, "passed": True})
    changed_checks = list(assessment.checks)
    changed_checks[first_quality_index] = changed_check
    changed = assessment.model_copy(update={"checks": tuple(changed_checks)})
    assert holdout_acceptance_assessment_sha256(changed) != (
        holdout_acceptance_assessment_sha256(assessment)
    )


def test_public_assessment_boundary_has_no_io_or_injection_hooks() -> None:
    signature = inspect.signature(assess_holdout_quality)
    assert tuple(signature.parameters) == ("report", "policy")
    assert signature.parameters["policy"].kind is inspect.Parameter.KEYWORD_ONLY

    source = inspect.getsource(acceptance_module)
    for forbidden in (
        "requests",
        "urllib",
        "socket",
        "open(",
        "import_module",
        "callback",
    ):
        assert forbidden not in source
