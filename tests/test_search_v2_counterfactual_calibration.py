from __future__ import annotations

import hashlib

import pytest

from src.search_v2.counterfactual_calibration import CALIBRATED_RANKING_ENABLED
from src.search_v2.counterfactual_calibration import COMMON_DECISION_THRESHOLD
from src.search_v2.counterfactual_calibration import CounterfactualCalibrationError
from src.search_v2.counterfactual_calibration import calibrate_minimum_positive_batch
from src.search_v2.counterfactual_calibration import calibration_profile_sha256
from src.search_v2.counterfactual_image import ConditionMargin
from src.search_v2.counterfactual_image import CounterfactualImageScore
from src.search_v2.counterfactual_v4 import minimum_positive_profile_sha256
from src.search_v2.image_similarity import clip_runtime_profile_sha256


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
        candidate_image_pixel_sha256=digest(tag),
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


def test_unknown_conditions_share_zero_after_observed_range_calibration() -> None:
    batch = (
        score("candidate-1", -1.0, -0.8),
        score("candidate-2", -0.5, -0.6),
        score("candidate-3", 0.5, 0.2),
        score("candidate-4", 1.0, 0.4),
    )

    calibrated = calibrate_minimum_positive_batch(batch)

    assert calibrated.status == "calibrated"
    assert calibrated.common_decision_threshold == COMMON_DECISION_THRESHOLD == 0.0
    assert calibrated.conditions[0].center == pytest.approx(0.0)
    assert calibrated.conditions[0].calibrated_margins == pytest.approx((-1.0, -0.5, 0.5, 1.0))
    assert calibrated.conditions[1].center == pytest.approx(-0.2)
    assert calibrated.conditions[1].calibrated_margins == pytest.approx(
        (-1.0, -2.0 / 3.0, 2.0 / 3.0, 1.0)
    )
    assert calibrated.qualified_for_ranking is False


def test_insufficient_observed_span_fails_closed_without_forcing_a_split() -> None:
    batch = tuple(score(f"candidate-{index}", 0.25) for index in range(1, 5))

    calibrated = calibrate_minimum_positive_batch(batch)

    assert calibrated.status == "unknown"
    assert calibrated.conditions[0].status == "insufficient_span"
    assert calibrated.conditions[0].center is None
    assert calibrated.conditions[0].half_span is None
    assert calibrated.conditions[0].calibrated_margins is None


def test_one_sided_range_without_boundary_support_fails_closed() -> None:
    batch = (
        score("candidate-1", -0.9),
        score("candidate-2", -0.7),
        score("candidate-3", -0.3),
        score("candidate-4", -0.1),
    )

    calibrated = calibrate_minimum_positive_batch(batch)

    assert calibrated.status == "unknown"
    assert calibrated.conditions[0].status == "insufficient_diversity"
    assert calibrated.conditions[0].calibrated_margins is None


def test_repeated_saturation_supports_one_sided_calibration() -> None:
    batch = (
        score("candidate-1", -1.0),
        score("candidate-2", -1.0),
        score("candidate-3", -0.5),
        score("candidate-4", -0.1),
    )

    calibrated = calibrate_minimum_positive_batch(batch)

    assert calibrated.status == "calibrated"
    assert calibrated.conditions[0].center == pytest.approx(-0.55)
    assert calibrated.conditions[0].calibrated_margins == pytest.approx(
        (-1.0, -1.0, 1.0 / 9.0, 1.0)
    )


def test_calibration_rejects_small_or_mixed_batches() -> None:
    too_small = tuple(score(f"candidate-{index}", float(index) / 10.0) for index in range(1, 4))
    mixed_binding = (
        score("candidate-1", -1.0),
        score("candidate-2", -0.5),
        score("candidate-3", 0.5),
        score("candidate-4", 1.0).model_copy(
            update={"reference_set_sha256": digest("other-references")}
        ),
    )
    duplicate_candidate = (
        score("candidate-1", -1.0),
        score("candidate-1", -0.5),
        score("candidate-3", 0.5),
        score("candidate-4", 1.0),
    )

    with pytest.raises(CounterfactualCalibrationError, match="calibration contract"):
        calibrate_minimum_positive_batch(too_small)
    with pytest.raises(CounterfactualCalibrationError, match="calibration contract"):
        calibrate_minimum_positive_batch(mixed_binding)
    with pytest.raises(CounterfactualCalibrationError, match="calibration contract"):
        calibrate_minimum_positive_batch(duplicate_candidate)


def test_calibration_profile_is_deterministic_and_never_enables_ranking() -> None:
    profile_digest = calibration_profile_sha256()

    assert profile_digest == calibration_profile_sha256()
    assert len(profile_digest) == 64
    assert CALIBRATED_RANKING_ENABLED is False
