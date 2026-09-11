from __future__ import annotations

import hashlib

import pytest

from src.search_v2.counterfactual_selection import CounterfactualDevelopmentMetrics
from src.search_v2.counterfactual_selection import CounterfactualSelectionError
from src.search_v2.counterfactual_selection import select_relative_development_winner


def digest(tag: str) -> str:
    return hashlib.sha256(tag.encode()).hexdigest()


def metrics(
    specification_id: str,
    *,
    correct_count: int,
    pairwise_auc: float,
    worst_condition_auc: float,
    dataset_sha256: str | None = None,
) -> CounterfactualDevelopmentMetrics:
    return CounterfactualDevelopmentMetrics(
        schema_version="1.0",
        specification_id=specification_id,
        absolute_assessment="fail",
        development_dataset_sha256=dataset_sha256 or digest("development-dataset"),
        labels_sha256=digest("frozen-labels"),
        evaluation_contract_sha256=digest("evaluation-contract"),
        correct_count=correct_count,
        evaluation_count=20,
        pairwise_auc=pairwise_auc,
        worst_condition_auc=worst_condition_auc,
    )


def test_redesigned_specification_passes_when_its_accuracy_is_higher() -> None:
    selection = select_relative_development_winner(
        current=metrics(
            "counterfactual-current-v1",
            correct_count=16,
            pairwise_auc=0.78,
            worst_condition_auc=0.75,
        ),
        redesigned=metrics(
            "counterfactual-redesigned-v1",
            correct_count=17,
            pairwise_auc=0.76,
            worst_condition_auc=0.70,
        ),
    )

    assert selection.decision == "pass"
    assert selection.selection_basis == "relative_development_accuracy"
    assert selection.winner_specification_id == "counterfactual-redesigned-v1"
    assert selection.winner_accuracy == pytest.approx(0.85)
    assert selection.eligible_for_independent_holdout is True
    assert selection.qualified_for_ranking is False


def test_current_specification_passes_when_redesign_does_not_improve_accuracy() -> None:
    selection = select_relative_development_winner(
        current=metrics(
            "counterfactual-current-v1",
            correct_count=16,
            pairwise_auc=0.78,
            worst_condition_auc=0.75,
        ),
        redesigned=metrics(
            "counterfactual-redesigned-v1",
            correct_count=15,
            pairwise_auc=0.90,
            worst_condition_auc=0.90,
        ),
    )

    assert selection.winner_specification_id == "counterfactual-current-v1"
    assert selection.winner_accuracy == pytest.approx(0.80)


def test_equal_accuracy_uses_auc_then_worst_condition_and_finally_current() -> None:
    current = metrics(
        "counterfactual-current-v1",
        correct_count=16,
        pairwise_auc=0.78,
        worst_condition_auc=0.75,
    )

    auc_winner = select_relative_development_winner(
        current=current,
        redesigned=metrics(
            "counterfactual-redesigned-v1",
            correct_count=16,
            pairwise_auc=0.79,
            worst_condition_auc=0.70,
        ),
    )
    worst_condition_winner = select_relative_development_winner(
        current=current,
        redesigned=metrics(
            "counterfactual-redesigned-v1",
            correct_count=16,
            pairwise_auc=0.78,
            worst_condition_auc=0.76,
        ),
    )
    exact_tie = select_relative_development_winner(
        current=current,
        redesigned=metrics(
            "counterfactual-redesigned-v1",
            correct_count=16,
            pairwise_auc=0.78,
            worst_condition_auc=0.75,
        ),
    )

    assert auc_winner.winner_specification_id == "counterfactual-redesigned-v1"
    assert worst_condition_winner.winner_specification_id == "counterfactual-redesigned-v1"
    assert exact_tie.winner_specification_id == "counterfactual-current-v1"


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("development_dataset_sha256", digest("other-dataset")),
        ("labels_sha256", digest("other-labels")),
        ("evaluation_contract_sha256", digest("other-contract")),
        ("evaluation_count", 19),
    ],
)
def test_comparison_rejects_nonidentical_evaluation_bindings(
    field: str, replacement: object
) -> None:
    current = metrics(
        "counterfactual-current-v1",
        correct_count=16,
        pairwise_auc=0.78,
        worst_condition_auc=0.75,
    )
    redesigned = metrics(
        "counterfactual-redesigned-v1",
        correct_count=16,
        pairwise_auc=0.78,
        worst_condition_auc=0.75,
    ).model_copy(update={field: replacement})

    with pytest.raises(CounterfactualSelectionError, match="comparison contract"):
        select_relative_development_winner(current=current, redesigned=redesigned)


def test_comparison_rejects_reusing_the_same_specification_id() -> None:
    current = metrics(
        "counterfactual-current-v1",
        correct_count=16,
        pairwise_auc=0.78,
        worst_condition_auc=0.75,
    )

    with pytest.raises(CounterfactualSelectionError, match="comparison contract"):
        select_relative_development_winner(current=current, redesigned=current)
