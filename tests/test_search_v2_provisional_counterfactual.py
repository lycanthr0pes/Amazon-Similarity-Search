from __future__ import annotations

import hashlib

import pytest

from src.search_v2.counterfactual_image import ConditionMargin
from src.search_v2.counterfactual_image import CounterfactualImageScore
from src.search_v2.counterfactual_v4 import minimum_positive_profile_sha256
from src.search_v2.image_similarity import clip_runtime_profile_sha256
from src.search_v2.provisional_counterfactual import PROVISIONAL_COUNTERFACTUAL_PROFILE
from src.search_v2.provisional_counterfactual import ProvisionalCounterfactualError
from src.search_v2.provisional_counterfactual import ProvisionalImageCandidateInput
from src.search_v2.provisional_counterfactual import build_provisional_counterfactual_batch
from src.search_v2.provisional_counterfactual import provisional_counterfactual_profile_sha256


def digest(tag: str) -> str:
    return hashlib.sha256(tag.encode()).hexdigest()


def score(tag: str, *margins: float) -> CounterfactualImageScore:
    return CounterfactualImageScore(
        schema_version="1.0",
        status="scored",
        condition_set_sha256=digest("conditions"),
        reference_set_sha256=digest("references"),
        score_profile_sha256=minimum_positive_profile_sha256(),
        runtime_sha256=clip_runtime_profile_sha256(),
        candidate_image_pixel_sha256=digest(f"image-{tag}"),
        condition_margins=tuple(
            ConditionMargin(
                condition_id=f"visual-condition-{index:03d}",
                status="scored",
                raw_margin=value / 10.0,
                reference_distance=0.1,
                normalized_margin=value,
            )
            for index, value in enumerate(margins, start=1)
        ),
        qualified_for_ranking=False,
    )


def candidate(tag: str, *margins: float) -> ProvisionalImageCandidateInput:
    image_score = score(tag, *margins)
    return ProvisionalImageCandidateInput(
        normalized_product_sha256=digest(f"product-{tag}"),
        candidate_image_pixel_sha256=image_score.candidate_image_pixel_sha256,
        score=image_score,
    )


def test_profile_records_the_human_provisional_decision_without_requalifying_v4() -> None:
    profile = PROVISIONAL_COUNTERFACTUAL_PROFILE

    assert profile.profile_id == "counterfactual-v4-provisional-production-v1"
    assert profile.source_score_profile_sha256 == minimum_positive_profile_sha256()
    assert profile.common_decision_threshold == 0.0
    assert profile.condition_aggregation == "minimum_calibrated_margin"
    assert profile.score_transform == "signed_margin_to_unit_interval"
    assert profile.known_holdout_accuracy == 0.875
    assert profile.known_holdout_auc == 1.0
    assert profile.adoption_basis == "human_authorized_provisional"
    assert profile.ranking_enabled is True
    assert provisional_counterfactual_profile_sha256() == (
        provisional_counterfactual_profile_sha256()
    )


def test_batch_uses_label_free_calibration_and_the_worst_condition() -> None:
    inputs = (
        candidate("one", -1.0, -1.0),
        candidate("two", -0.5, 0.5),
        candidate("three", 0.5, -0.5),
        candidate("four", 1.0, 1.0),
    )

    result = build_provisional_counterfactual_batch(inputs)

    assert result.status == "ready"
    assert result.ranking_enabled is True
    assert result.common_decision_threshold == 0.0
    assert tuple(item.status for item in result.candidates) == ("available",) * 4
    assert tuple(item.minimum_calibrated_margin for item in result.candidates) == pytest.approx(
        (-1.0, -0.5, -0.5, 1.0)
    )
    assert tuple(item.image_score for item in result.candidates) == pytest.approx(
        (0.0, 0.25, 0.25, 1.0)
    )
    assert tuple(item.matched_condition_count for item in result.candidates) == (0, 1, 1, 2)
    assert all(item.condition_count == 2 for item in result.candidates)


def test_zero_calibrated_margin_maps_to_half_score_and_counts_as_a_match() -> None:
    inputs = (
        candidate("one", -1.0),
        candidate("two", 0.0),
        candidate("three", 0.5),
        candidate("four", 1.0),
    )

    result = build_provisional_counterfactual_batch(inputs)

    second = result.candidates[1]
    assert second.minimum_calibrated_margin == pytest.approx(0.0)
    assert second.image_score == pytest.approx(0.5)
    assert second.matched_condition_count == 1


def test_missing_images_remain_missing_and_are_not_turned_into_zero_scores() -> None:
    missing_score = score("missing", -0.25).model_copy(
        update={
            "status": "missing",
            "candidate_image_pixel_sha256": None,
            "condition_margins": (
                ConditionMargin(
                    condition_id="visual-condition-001",
                    status="missing",
                    raw_margin=None,
                    reference_distance=None,
                    normalized_margin=None,
                ),
            ),
        }
    )
    inputs = (
        candidate("one", -1.0),
        candidate("two", -0.5),
        candidate("three", 0.5),
        candidate("four", 1.0),
        ProvisionalImageCandidateInput(
            normalized_product_sha256=digest("product-missing"),
            candidate_image_pixel_sha256=None,
            score=missing_score,
        ),
    )

    result = build_provisional_counterfactual_batch(inputs)

    missing = result.candidates[-1]
    assert result.status == "ready"
    assert missing.status == "missing"
    assert missing.candidate_image_pixel_sha256 is None
    assert missing.minimum_calibrated_margin is None
    assert missing.image_score is None
    assert missing.matched_condition_count is None


def test_uncalibrated_batch_fails_closed() -> None:
    inputs = tuple(candidate(str(index), 0.25) for index in range(1, 5))

    result = build_provisional_counterfactual_batch(inputs)

    assert result.status == "unknown"
    assert result.ranking_enabled is False
    assert {item.status for item in result.candidates} == {"unknown"}
    assert all(item.image_score is None for item in result.candidates)


def test_batch_rejects_duplicate_products_and_tampered_image_bindings() -> None:
    duplicate_product = (
        candidate("one", -1.0),
        candidate("one", -0.5),
        candidate("three", 0.5),
        candidate("four", 1.0),
    )
    tampered = candidate("one", -1.0).model_copy(
        update={"candidate_image_pixel_sha256": digest("different-image")}
    )

    with pytest.raises(ProvisionalCounterfactualError, match="provisional contract"):
        build_provisional_counterfactual_batch(duplicate_product)
    with pytest.raises(ProvisionalCounterfactualError, match="provisional contract"):
        build_provisional_counterfactual_batch(
            (
                tampered,
                candidate("two", -0.5),
                candidate("three", 0.5),
                candidate("four", 1.0),
            )
        )
