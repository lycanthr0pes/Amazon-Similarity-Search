from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
import statistics

import pytest
from PIL import Image

from src.search_v2.counterfactual_calibration import COMMON_DECISION_THRESHOLD
from src.search_v2.counterfactual_calibration import calibrate_minimum_positive_batch
from src.search_v2.counterfactual_calibration import calibration_profile_sha256
from src.search_v2.counterfactual_image import COUNTERFACTUAL_RANKING_ENABLED
from src.search_v2.counterfactual_image import VisualConditionDraft
from src.search_v2.counterfactual_image import build_counterfactual_reference_set
from src.search_v2.counterfactual_image import build_visual_condition_set
from src.search_v2.counterfactual_image import score_counterfactual_conditions
from src.search_v2.counterfactual_redesign import MULTI_REFERENCE_RANKING_ENABLED
from src.search_v2.counterfactual_redesign import multi_reference_score_profile_sha256
from src.search_v2.counterfactual_redesign import score_multi_reference_counterfactual_conditions
from src.search_v2.counterfactual_selection import CounterfactualDevelopmentMetrics
from src.search_v2.counterfactual_selection import select_relative_development_winner
from src.search_v2.counterfactual_v4 import MINIMUM_POSITIVE_RANKING_ENABLED
from src.search_v2.counterfactual_v4 import minimum_positive_profile_sha256
from src.search_v2.counterfactual_v4 import score_minimum_positive_conditions
from src.search_v2.image_proxy import ProxyImage
from src.search_v2.image_proxy import proxy_image_pixel_sha256
from src.search_v2.image_similarity import PHASH_DUPLICATE_MAX_DISTANCE
from src.search_v2.image_similarity import ClipEmbedding
from src.search_v2.image_similarity import compute_phash
from src.search_v2.image_similarity import phash_hamming_distance
from src.search_v2.image_similarity import run_pinned_clip_image_encoder
from src.search_v2.image_similarity_process import ProcessIsolatedClipImageEncoder


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = REPOSITORY_ROOT / "models" / "clip-vit-base-patch32-12b36594"
IMAGE_ROOT = Path(__file__).resolve().parent / "img"
CASE_SOURCES = {
    "counterfactual-development-001": "黒い本体の電気ケトル",
    "counterfactual-development-002": "黒いメッシュ背もたれ・ヘッドレスト付きのオフィスチェア",
}
MINIMUM_CLASS_COUNT = 3
AUC_THRESHOLD = 0.80
ABSOLUTE_ACCURACY_THRESHOLD = 0.90
EVALUATION_CONTRACT = {
    "absolute_accuracy_threshold": ABSOLUTE_ACCURACY_THRESHOLD,
    "auc_threshold": AUC_THRESHOLD,
    "minimum_class_count": MINIMUM_CLASS_COUNT,
    "selection_policy_id": "counterfactual-development-relative-accuracy-v1",
}


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_proxy_image(path: Path, expected_sha256: str, tag: str) -> ProxyImage:
    assert path.is_file() and not path.is_symlink()
    assert path.stat().st_nlink == 1
    source_bytes = path.read_bytes()
    assert hashlib.sha256(source_bytes).hexdigest() == expected_sha256
    with Image.open(BytesIO(source_bytes)) as decoded:
        assert decoded.format == "PNG"
        assert getattr(decoded, "n_frames", 1) == 1
        width, height = decoded.size
        assert 1 <= width <= 4096
        assert 1 <= height <= 4096
        rgb_bytes = decoded.convert("RGB").tobytes()
    return ProxyImage(
        schema_version="2.0",
        source_url_sha256=hashlib.sha256(f"counterfactual:{tag}".encode()).hexdigest(),
        source_bytes_sha256=expected_sha256,
        pixel_sha256=proxy_image_pixel_sha256(width, height, rgb_bytes),
        content_type="image/png",
        image_format="PNG",
        width=width,
        height=height,
        rgb_bytes=rgb_bytes,
    )


def load_case_inputs(case_id: str):
    case_root = IMAGE_ROOT / case_id
    manifest = load_json(case_root / "manifest.json")
    source_case_root = IMAGE_ROOT / manifest["source_case_id"]
    source_manifest_path = source_case_root / "manifest.json"
    assert (
        hashlib.sha256(source_manifest_path.read_bytes()).hexdigest()
        == manifest["source_manifest_sha256"]
    )
    source_manifest = load_json(source_manifest_path)

    conditions = build_visual_condition_set(
        source_input=CASE_SOURCES[case_id],
        drafts=tuple(
            VisualConditionDraft(
                source_phrase=item["source_phrase"],
                strength="required",
                attribute_key=item["attribute_key"],
            )
            for item in manifest["conditions"]
        ),
    )
    references = tuple(
        load_proxy_image(case_root / item["path"], item["sha256"], item["path"])
        for item in manifest["references"]
    )
    reference_set = build_counterfactual_reference_set(
        condition_set=conditions,
        desired_image_hash=compute_phash(references[0]),
        counterfactual_image_hashes=tuple(compute_phash(image) for image in references[1:]),
    )
    source_candidates = {item["candidate_id"]: item for item in source_manifest["candidates"]}
    labels = manifest["candidate_labels"]
    candidates = tuple(
        load_proxy_image(
            source_case_root / source_candidates[item["candidate_id"]]["path"],
            source_candidates[item["candidate_id"]]["sha256"],
            item["candidate_id"],
        )
        for item in labels
    )
    return manifest, conditions, reference_set, references, labels, candidates


def encode_images(images: tuple[ProxyImage, ...]) -> tuple[ClipEmbedding, ...]:
    encoder = ProcessIsolatedClipImageEncoder()
    encoded: list[ClipEmbedding] = []
    for start in range(0, len(images), 4):
        encoded.extend(
            run_pinned_clip_image_encoder(
                images[start : start + 4],
                asset_root=MODEL_ROOT,
                encoder=encoder,
            )
        )
    return tuple(encoded)


def pairwise_auc(positive: tuple[float, ...], negative: tuple[float, ...]) -> float:
    wins = sum(left > right for left in positive for right in negative)
    ties = sum(left == right for left in positive for right in negative)
    return (wins + ties * 0.5) / (len(positive) * len(negative))


def canonical_sha256(domain: bytes, value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(domain + payload).hexdigest()


def best_threshold(match: tuple[float, ...], mismatch: tuple[float, ...]) -> dict[str, float]:
    values = sorted(set((*match, *mismatch)))
    thresholds = [values[0] - 1.0]
    thresholds.extend((left + right) / 2 for left, right in zip(values, values[1:], strict=False))
    thresholds.append(values[-1] + 1.0)
    best: tuple[tuple[float, float, float, float], float, float, float] | None = None
    for threshold in thresholds:
        sensitivity = sum(value >= threshold for value in match) / len(match)
        specificity = sum(value < threshold for value in mismatch) / len(mismatch)
        balanced_accuracy = (sensitivity + specificity) / 2
        candidate = (balanced_accuracy, sensitivity + specificity, -abs(threshold), threshold)
        if best is None or candidate > best[0]:
            best = (candidate, threshold, sensitivity, specificity)
    assert best is not None
    return {
        "threshold": best[1],
        "balanced_accuracy": best[0][0],
        "sensitivity": best[2],
        "specificity": best[3],
    }


def development_bindings() -> tuple[str, str, str]:
    manifests = tuple(load_json(IMAGE_ROOT / case_id / "manifest.json") for case_id in CASE_SOURCES)
    dataset = {
        "case_manifests": [
            {
                "case_id": case_id,
                "manifest_sha256": hashlib.sha256(
                    (IMAGE_ROOT / case_id / "manifest.json").read_bytes()
                ).hexdigest(),
                "source_manifest_sha256": manifest["source_manifest_sha256"],
            }
            for case_id, manifest in zip(CASE_SOURCES, manifests, strict=True)
        ]
    }
    labels = {
        case_id: manifest["candidate_labels"]
        for case_id, manifest in zip(CASE_SOURCES, manifests, strict=True)
    }
    return (
        canonical_sha256(b"amazon-explorer-counterfactual-development-dataset-v1\x00", dataset),
        canonical_sha256(b"amazon-explorer-counterfactual-development-labels-v1\x00", labels),
        canonical_sha256(
            b"amazon-explorer-counterfactual-evaluation-contract-v1\x00",
            EVALUATION_CONTRACT,
        ),
    )


def test_calibration_manifests_freeze_labels_before_clip_and_reject_duplicate_references() -> None:
    for case_id, expected_calls in (
        ("counterfactual-development-001", 2),
        ("counterfactual-development-002", 4),
    ):
        manifest, conditions, _, references, labels, _ = load_case_inputs(case_id)
        generation = manifest["generation"]
        assert manifest["label_frozen_before_clip"] is True
        assert generation == {
            "provider": "gpt-image",
            "scope": "test_only",
            "call_limit": expected_calls,
            "call_count": expected_calls,
            "retry_count": 0,
            "candidate_images_sent": False,
            "human_reference_confirmation": True,
        }
        assert len(references) == 1 + len(conditions.conditions)
        assert len(labels) in {10, 12}
        hashes = tuple(compute_phash(image) for image in references)
        assert (
            min(
                phash_hamming_distance(left, right)
                for index, left in enumerate(hashes)
                for right in hashes[index + 1 :]
            )
            > PHASH_DUPLICATE_MAX_DISTANCE
        )


def test_recorded_calibration_result_preserves_ineligible_and_failed_conditions() -> None:
    result = load_json(IMAGE_ROOT / "counterfactual-calibration-result.json")

    assert result["assessment"] == "fail"
    assert result["qualified_for_ranking"] is False
    assert result["auc_threshold"] == AUC_THRESHOLD
    assert result["minimum_class_count"] == MINIMUM_CLASS_COUNT
    assert result["pooled_eligible_conditions"]["pairwise_auc"] == pytest.approx(0.78)
    assert result["pooled_eligible_conditions"]["assessment"] == "fail"
    cases = {item["case_id"]: item for item in result["cases"]}
    kettle = cases["counterfactual-development-001"]["conditions"][0]
    chair = cases["counterfactual-development-002"]["conditions"]
    assert kettle["pairwise_auc"] == pytest.approx(1.0)
    assert kettle["assessment"] == "pass"
    assert chair[0]["assessment"] == "ineligible"
    assert chair[1]["assessment"] == "ineligible"
    assert chair[2]["pairwise_auc"] == pytest.approx(0.75)
    assert chair[2]["assessment"] == "fail"
    assert cases["counterfactual-development-002"]["aggregate_min"][
        "pairwise_auc"
    ] == pytest.approx(0.5833333333333334)
    assert cases["counterfactual-development-002"]["aggregate_mean"][
        "pairwise_auc"
    ] == pytest.approx(0.7083333333333334)


def test_recorded_redesign_result_selects_the_better_comparable_specification() -> None:
    result = load_json(IMAGE_ROOT / "counterfactual-redesign-result.json")
    baseline = load_json(IMAGE_ROOT / "counterfactual-calibration-result.json")
    dataset_sha256, labels_sha256, evaluation_contract_sha256 = development_bindings()

    assert result["external_call_count"] == 0
    assert result["reused_fixed_references_and_candidates"] is True
    assert result["development_dataset_sha256"] == dataset_sha256
    assert result["labels_sha256"] == labels_sha256
    assert result["evaluation_contract_sha256"] == evaluation_contract_sha256
    assert result["redesigned"]["score_profile_sha256"] == (multi_reference_score_profile_sha256())
    baseline_pool = baseline["pooled_eligible_conditions"]
    baseline_correct_count = sum(
        value >= baseline_pool["diagnostic_threshold"] for value in baseline_pool["match_scores"]
    ) + sum(
        value < baseline_pool["diagnostic_threshold"] for value in baseline_pool["mismatch_scores"]
    )
    assert result["current"]["correct_count"] == baseline_correct_count == 16
    assert result["current"]["pairwise_auc"] == baseline_pool["pairwise_auc"]
    baseline_cases = {item["case_id"]: item for item in baseline["cases"]}
    assert (
        result["current"]["worst_condition_auc"]
        == baseline_cases["counterfactual-development-002"]["conditions"][2]["pairwise_auc"]
    )
    for specification in (result["current"], result["redesigned"]):
        assert specification["accuracy"] == pytest.approx(
            specification["correct_count"] / specification["evaluation_count"]
        )
    eligible_redesigned = tuple(
        condition["pairwise_auc"]
        for condition in result["redesigned"]["conditions"].values()
        if condition["assessment"] == "pass"
    )
    assert result["redesigned"]["worst_condition_auc"] == pytest.approx(min(eligible_redesigned))
    current = CounterfactualDevelopmentMetrics(
        schema_version="1.0",
        specification_id=result["current"]["specification_id"],
        absolute_assessment=result["current"]["absolute_assessment"],
        development_dataset_sha256=dataset_sha256,
        labels_sha256=labels_sha256,
        evaluation_contract_sha256=evaluation_contract_sha256,
        correct_count=result["current"]["correct_count"],
        evaluation_count=result["current"]["evaluation_count"],
        pairwise_auc=result["current"]["pairwise_auc"],
        worst_condition_auc=result["current"]["worst_condition_auc"],
    )
    redesigned = CounterfactualDevelopmentMetrics(
        schema_version="1.0",
        specification_id=result["redesigned"]["specification_id"],
        absolute_assessment=result["redesigned"]["absolute_assessment"],
        development_dataset_sha256=dataset_sha256,
        labels_sha256=labels_sha256,
        evaluation_contract_sha256=evaluation_contract_sha256,
        correct_count=result["redesigned"]["correct_count"],
        evaluation_count=result["redesigned"]["evaluation_count"],
        pairwise_auc=result["redesigned"]["pairwise_auc"],
        worst_condition_auc=result["redesigned"]["worst_condition_auc"],
    )
    selection = select_relative_development_winner(current=current, redesigned=redesigned)

    assert selection.model_dump(mode="json") == result["selection"]
    assert selection.winner_specification_id == "counterfactual-mean-positive-v2"
    assert selection.tie_breaker == "pairwise_auc"
    assert result["qualified_for_ranking"] is False


def test_recorded_v4_result_uses_the_same_development_binding() -> None:
    result = load_json(IMAGE_ROOT / "counterfactual-v4-result.json")
    previous = load_json(IMAGE_ROOT / "counterfactual-redesign-result.json")
    dataset_sha256, labels_sha256, evaluation_contract_sha256 = development_bindings()

    assert result["external_call_count"] == 0
    assert result["reused_fixed_references_and_candidates"] is True
    assert result["development_dataset_sha256"] == dataset_sha256
    assert result["labels_sha256"] == labels_sha256
    assert result["evaluation_contract_sha256"] == evaluation_contract_sha256
    assert result["v4"]["score_profile_sha256"] == minimum_positive_profile_sha256()
    for metric_name in (
        "specification_id",
        "absolute_assessment",
        "correct_count",
        "evaluation_count",
        "accuracy",
        "pairwise_auc",
        "worst_condition_auc",
    ):
        assert result["current"][metric_name] == previous["redesigned"][metric_name]
    for specification in (result["current"], result["v4"]):
        assert specification["accuracy"] == pytest.approx(
            specification["correct_count"] / specification["evaluation_count"]
        )
    eligible_v4 = tuple(
        condition["pairwise_auc"]
        for condition in result["v4"]["conditions"].values()
        if condition["assessment"] == "pass"
    )
    assert result["v4"]["worst_condition_auc"] == pytest.approx(min(eligible_v4))
    rejected = result["rejected_reference_self_calibration"]
    assert rejected["assessment"] == "rejected_no_improvement"
    assert rejected["hard_clamp"]["pairwise_auc"] == pytest.approx(0.72)
    assert rejected["monotonic_without_hard_clamp"]["pairwise_auc"] == pytest.approx(0.84)
    current = CounterfactualDevelopmentMetrics(
        schema_version="1.0",
        specification_id=result["current"]["specification_id"],
        absolute_assessment=result["current"]["absolute_assessment"],
        development_dataset_sha256=dataset_sha256,
        labels_sha256=labels_sha256,
        evaluation_contract_sha256=evaluation_contract_sha256,
        correct_count=result["current"]["correct_count"],
        evaluation_count=result["current"]["evaluation_count"],
        pairwise_auc=result["current"]["pairwise_auc"],
        worst_condition_auc=result["current"]["worst_condition_auc"],
    )
    v4 = CounterfactualDevelopmentMetrics(
        schema_version="1.0",
        specification_id=result["v4"]["specification_id"],
        absolute_assessment=result["v4"]["absolute_assessment"],
        development_dataset_sha256=dataset_sha256,
        labels_sha256=labels_sha256,
        evaluation_contract_sha256=evaluation_contract_sha256,
        correct_count=result["v4"]["correct_count"],
        evaluation_count=result["v4"]["evaluation_count"],
        pairwise_auc=result["v4"]["pairwise_auc"],
        worst_condition_auc=result["v4"]["worst_condition_auc"],
    )
    selection = select_relative_development_winner(current=current, redesigned=v4)

    assert selection.model_dump(mode="json") == result["selection"]
    assert result["qualified_for_ranking"] is False


def test_recorded_v4_calibration_uses_labels_only_for_evaluation() -> None:
    result = load_json(IMAGE_ROOT / "counterfactual-v4-calibration-result.json")
    previous = load_json(IMAGE_ROOT / "counterfactual-v4-result.json")
    dataset_sha256, labels_sha256, evaluation_contract_sha256 = development_bindings()

    assert result["external_call_count"] == 0
    assert result["reused_fixed_references_and_candidates"] is True
    assert result["development_dataset_sha256"] == dataset_sha256
    assert result["labels_sha256"] == labels_sha256
    assert result["evaluation_contract_sha256"] == evaluation_contract_sha256
    assert result["score_profile_sha256"] == minimum_positive_profile_sha256()
    assert result["calibration_profile_sha256"] == calibration_profile_sha256()
    assert result["labels_used_for_calibration"] is False
    assert result["common_decision_threshold"] == COMMON_DECISION_THRESHOLD == 0.0
    assert result["calibrated"]["correct_count"] == 20
    assert result["calibrated"]["evaluation_count"] == 20
    assert result["calibrated"]["accuracy"] == pytest.approx(1.0)
    assert result["calibrated"]["pairwise_auc"] == pytest.approx(1.0)
    assert (
        result["calibrated"]["conditions"]["counterfactual-development-002:visual-condition-002"][
            "calibration_status"
        ]
        == "insufficient_diversity"
    )
    current = CounterfactualDevelopmentMetrics(
        schema_version="1.0",
        specification_id=previous["v4"]["specification_id"],
        absolute_assessment=previous["v4"]["absolute_assessment"],
        development_dataset_sha256=dataset_sha256,
        labels_sha256=labels_sha256,
        evaluation_contract_sha256=evaluation_contract_sha256,
        correct_count=previous["v4"]["correct_count"],
        evaluation_count=previous["v4"]["evaluation_count"],
        pairwise_auc=previous["v4"]["pairwise_auc"],
        worst_condition_auc=previous["v4"]["worst_condition_auc"],
    )
    calibrated = CounterfactualDevelopmentMetrics(
        schema_version="1.0",
        specification_id=result["calibrated"]["specification_id"],
        absolute_assessment=result["calibrated"]["absolute_assessment"],
        development_dataset_sha256=dataset_sha256,
        labels_sha256=labels_sha256,
        evaluation_contract_sha256=evaluation_contract_sha256,
        correct_count=result["calibrated"]["correct_count"],
        evaluation_count=result["calibrated"]["evaluation_count"],
        pairwise_auc=result["calibrated"]["pairwise_auc"],
        worst_condition_auc=result["calibrated"]["worst_condition_auc"],
    )

    assert (
        select_relative_development_winner(current=current, redesigned=calibrated).model_dump(
            mode="json"
        )
        == result["selection"]
    )
    assert result["qualified_for_ranking"] is False


@pytest.mark.clip_runtime
def test_recorded_counterfactual_margins_match_fixed_clip_runtime() -> None:
    result = load_json(IMAGE_ROOT / "counterfactual-calibration-result.json")
    recorded_cases = {item["case_id"]: item for item in result["cases"]}

    for case_id in CASE_SOURCES:
        _, conditions, reference_set, references, labels, candidates = load_case_inputs(case_id)
        embeddings = encode_images((*references, *candidates))
        reference_embeddings = embeddings[: len(references)]
        candidate_embeddings = embeddings[len(references) :]
        recorded_scores = {
            item["candidate_id"]: item["margins"]
            for item in recorded_cases[case_id]["candidate_scores"]
        }
        for label, embedding in zip(labels, candidate_embeddings, strict=True):
            score = score_counterfactual_conditions(
                condition_set=conditions,
                reference_set=reference_set,
                reference_embeddings=reference_embeddings,
                candidate_embedding=embedding,
            )
            expected = recorded_scores[label["candidate_id"]]
            for margin in score.condition_margins:
                values = expected[margin.condition_id]
                assert margin.raw_margin == pytest.approx(values["raw_margin"], abs=1e-8)
                assert margin.reference_distance == pytest.approx(
                    values["reference_distance"], abs=1e-8
                )
                assert margin.normalized_margin == pytest.approx(
                    values["normalized_margin"], abs=1e-8
                )

    pooled = result["pooled_eligible_conditions"]
    assert pairwise_auc(
        tuple(pooled["match_scores"]), tuple(pooled["mismatch_scores"])
    ) == pytest.approx(0.78)
    assert statistics.median(pooled["match_scores"]) > statistics.median(pooled["mismatch_scores"])
    assert COUNTERFACTUAL_RANKING_ENABLED is False


@pytest.mark.clip_runtime
def test_redesigned_metrics_match_fixed_clip_runtime() -> None:
    result = load_json(IMAGE_ROOT / "counterfactual-redesign-result.json")
    condition_metrics: dict[str, dict[str, object]] = {}
    pooled_match: list[float] = []
    pooled_mismatch: list[float] = []

    for case_id in CASE_SOURCES:
        _, conditions, reference_set, references, labels, candidates = load_case_inputs(case_id)
        embeddings = encode_images((*references, *candidates))
        reference_embeddings = embeddings[: len(references)]
        for condition_index, condition in enumerate(conditions.conditions):
            scores = tuple(
                score_multi_reference_counterfactual_conditions(
                    condition_set=conditions,
                    reference_set=reference_set,
                    reference_embeddings=reference_embeddings,
                    candidate_embedding=embedding,
                )
                .condition_margins[condition_index]
                .normalized_margin
                for embedding in embeddings[len(references) :]
            )
            assert all(value is not None for value in scores)
            numeric_scores = tuple(float(value) for value in scores if value is not None)
            match = tuple(
                value
                for value, label in zip(numeric_scores, labels, strict=True)
                if label[condition.condition_id] == "match"
            )
            mismatch = tuple(
                value
                for value, label in zip(numeric_scores, labels, strict=True)
                if label[condition.condition_id] == "mismatch"
            )
            key = f"{case_id}:{condition.condition_id}"
            if len(match) < MINIMUM_CLASS_COUNT or len(mismatch) < MINIMUM_CLASS_COUNT:
                condition_metrics[key] = {
                    "assessment": "ineligible",
                    "match_count": len(match),
                    "mismatch_count": len(mismatch),
                }
                continue
            pooled_match.extend(match)
            pooled_mismatch.extend(mismatch)
            condition_metrics[key] = {
                "assessment": "pass" if pairwise_auc(match, mismatch) >= AUC_THRESHOLD else "fail",
                "pairwise_auc": pairwise_auc(match, mismatch),
                **best_threshold(match, mismatch),
            }

    match_scores = tuple(pooled_match)
    mismatch_scores = tuple(pooled_mismatch)
    pooled_threshold = best_threshold(match_scores, mismatch_scores)
    correct_count = sum(value >= pooled_threshold["threshold"] for value in match_scores) + sum(
        value < pooled_threshold["threshold"] for value in mismatch_scores
    )

    recorded_conditions = result["redesigned"]["conditions"]
    assert condition_metrics.keys() == recorded_conditions.keys()
    for key, metrics in condition_metrics.items():
        recorded = recorded_conditions[key]
        assert metrics.keys() == recorded.keys()
        assert metrics["assessment"] == recorded["assessment"]
        for metric_name in metrics.keys() - {"assessment"}:
            assert metrics[metric_name] == pytest.approx(recorded[metric_name])
    assert pairwise_auc(match_scores, mismatch_scores) == pytest.approx(
        result["redesigned"]["pairwise_auc"]
    )
    assert pooled_threshold == pytest.approx(result["redesigned"]["pooled_diagnostic"])
    assert correct_count == result["redesigned"]["correct_count"] == 16
    assert len(match_scores) + len(mismatch_scores) == 20
    assert MULTI_REFERENCE_RANKING_ENABLED is False


@pytest.mark.clip_runtime
def test_v4_metrics_match_fixed_clip_runtime() -> None:
    result = load_json(IMAGE_ROOT / "counterfactual-v4-result.json")
    calibration_result = load_json(IMAGE_ROOT / "counterfactual-v4-calibration-result.json")
    condition_metrics: dict[str, dict[str, object]] = {}
    pooled_match: list[float] = []
    pooled_mismatch: list[float] = []
    calibration_metrics: dict[str, dict[str, object]] = {}
    calibrated_match: list[float] = []
    calibrated_mismatch: list[float] = []

    for case_id in CASE_SOURCES:
        _, conditions, reference_set, references, labels, candidates = load_case_inputs(case_id)
        embeddings = encode_images((*references, *candidates))
        reference_embeddings = embeddings[: len(references)]
        candidate_scores = tuple(
            score_minimum_positive_conditions(
                condition_set=conditions,
                reference_set=reference_set,
                reference_embeddings=reference_embeddings,
                candidate_embedding=embedding,
            )
            for embedding in embeddings[len(references) :]
        )
        assert all(score.status == "scored" for score in candidate_scores)
        batch_calibration = calibrate_minimum_positive_batch(candidate_scores)
        for condition_index, condition in enumerate(conditions.conditions):
            margins = tuple(score.condition_margins[condition_index] for score in candidate_scores)
            scores = tuple(margin.normalized_margin for margin in margins)
            assert all(value is not None for value in scores)
            numeric_scores = tuple(float(value) for value in scores if value is not None)
            match = tuple(
                value
                for value, label in zip(numeric_scores, labels, strict=True)
                if label[condition.condition_id] == "match"
            )
            mismatch = tuple(
                value
                for value, label in zip(numeric_scores, labels, strict=True)
                if label[condition.condition_id] == "mismatch"
            )
            key = f"{case_id}:{condition.condition_id}"
            if len(match) < MINIMUM_CLASS_COUNT or len(mismatch) < MINIMUM_CLASS_COUNT:
                condition_metrics[key] = {
                    "assessment": "ineligible",
                    "match_count": len(match),
                    "mismatch_count": len(mismatch),
                }
                continue
            pooled_match.extend(match)
            pooled_mismatch.extend(mismatch)
            condition_metrics[key] = {
                "assessment": "pass" if pairwise_auc(match, mismatch) >= AUC_THRESHOLD else "fail",
                "pairwise_auc": pairwise_auc(match, mismatch),
                **best_threshold(match, mismatch),
            }

        for condition in batch_calibration.conditions:
            labels_for_condition = tuple(item[condition.condition_id] for item in labels)
            match_count = labels_for_condition.count("match")
            mismatch_count = labels_for_condition.count("mismatch")
            metrics: dict[str, object] = {
                "calibration_status": condition.status,
                "observed_count": condition.observed_count,
                "observed_minimum": condition.observed_minimum,
                "observed_maximum": condition.observed_maximum,
                "center": condition.center,
                "half_span": condition.half_span,
            }
            if match_count < MINIMUM_CLASS_COUNT or mismatch_count < MINIMUM_CLASS_COUNT:
                metrics.update(
                    assessment="ineligible",
                    match_count=match_count,
                    mismatch_count=mismatch_count,
                )
            elif condition.calibrated_margins is None:
                metrics.update(
                    assessment="uncalibrated",
                    match_count=match_count,
                    mismatch_count=mismatch_count,
                )
            else:
                match = tuple(
                    value
                    for value, label in zip(
                        condition.calibrated_margins, labels_for_condition, strict=True
                    )
                    if label == "match"
                )
                mismatch = tuple(
                    value
                    for value, label in zip(
                        condition.calibrated_margins, labels_for_condition, strict=True
                    )
                    if label == "mismatch"
                )
                condition_correct = sum(
                    value >= COMMON_DECISION_THRESHOLD for value in match
                ) + sum(value < COMMON_DECISION_THRESHOLD for value in mismatch)
                metrics.update(
                    assessment="pass",
                    match_count=len(match),
                    mismatch_count=len(mismatch),
                    correct_count=condition_correct,
                    evaluation_count=len(match) + len(mismatch),
                    accuracy=condition_correct / (len(match) + len(mismatch)),
                    pairwise_auc=pairwise_auc(match, mismatch),
                )
                calibrated_match.extend(match)
                calibrated_mismatch.extend(mismatch)
            calibration_metrics[f"{case_id}:{condition.condition_id}"] = metrics

    match_scores = tuple(pooled_match)
    mismatch_scores = tuple(pooled_mismatch)
    pooled_threshold = best_threshold(match_scores, mismatch_scores)
    correct_count = sum(value >= pooled_threshold["threshold"] for value in match_scores) + sum(
        value < pooled_threshold["threshold"] for value in mismatch_scores
    )

    recorded_conditions = result["v4"]["conditions"]
    assert condition_metrics.keys() == recorded_conditions.keys()
    for key, metrics in condition_metrics.items():
        recorded = recorded_conditions[key]
        assert metrics.keys() == recorded.keys()
        assert metrics["assessment"] == recorded["assessment"]
        for metric_name in metrics.keys() - {"assessment"}:
            assert metrics[metric_name] == pytest.approx(recorded[metric_name])
    assert pairwise_auc(match_scores, mismatch_scores) == pytest.approx(
        result["v4"]["pairwise_auc"]
    )
    assert pooled_threshold == pytest.approx(result["v4"]["pooled_diagnostic"])
    assert correct_count == result["v4"]["correct_count"]
    assert len(match_scores) + len(mismatch_scores) == result["v4"]["evaluation_count"]

    recorded_calibration = calibration_result["calibrated"]["conditions"]
    assert calibration_metrics.keys() == recorded_calibration.keys()
    for key, metrics in calibration_metrics.items():
        recorded = recorded_calibration[key]
        assert metrics.keys() == recorded.keys()
        for metric_name, value in metrics.items():
            if isinstance(value, float):
                assert value == pytest.approx(recorded[metric_name])
            else:
                assert value == recorded[metric_name]
    calibrated_correct = sum(
        value >= COMMON_DECISION_THRESHOLD for value in calibrated_match
    ) + sum(value < COMMON_DECISION_THRESHOLD for value in calibrated_mismatch)
    assert calibrated_correct == calibration_result["calibrated"]["correct_count"] == 20
    assert len(calibrated_match) + len(calibrated_mismatch) == 20
    assert pairwise_auc(tuple(calibrated_match), tuple(calibrated_mismatch)) == pytest.approx(
        calibration_result["calibrated"]["pairwise_auc"]
    )
    assert MINIMUM_POSITIVE_RANKING_ENABLED is False


def test_unknown_condition_holdout_freezes_inputs_and_failed_aggregate() -> None:
    case_root = IMAGE_ROOT / "image-holdout-006"
    collection = load_json(case_root / "collection.json")
    labels = load_json(case_root / "labels.json")
    references = load_json(case_root / "references.json")
    result = load_json(case_root / "result.json")

    assert collection["top_level_navigation_count"] == 1
    assert collection["retry_count"] == 0
    assert collection["external_requests_sent"] == collection["external_request_limit"] == 100
    assert collection["external_requests_blocked_before_send"] == 40
    assert collection["candidate_count"] == len(collection["candidates"]) == 12
    assert labels["labels_fixed_before_clip"] is True
    assert labels["class_counts"] == {"match": 3, "mismatch": 5, "ambiguous": 4}
    assert references["generation_calls_used"] == references["generation_call_limit"] == 2
    assert references["retry_count"] == 0
    assert references["candidate_images_sent_to_generator"] is False
    assert references["human_pair_confirmation"] == "confirmed"
    assert references["clip_execution"] == "completed"
    assert result["external_call_count_during_clip"] == 0
    assert result["labels_used_for_calibration"] is False
    assert result["calibration_candidate_count"] == 12
    assert result["common_decision_threshold"] == COMMON_DECISION_THRESHOLD == 0.0
    assert result["calibration"]["status"] == "calibrated"
    assert result["evaluation"]["true_positive"] == 3
    assert result["evaluation"]["false_negative"] == 0
    assert result["evaluation"]["true_negative"] == 4
    assert result["evaluation"]["false_positive"] == 1
    assert result["evaluation"]["accuracy"] == pytest.approx(0.875)
    assert result["evaluation"]["pairwise_auc"] == pytest.approx(1.0)
    assert result["assessment"] == "fail"
    assert result["qualified_for_ranking"] is False


@pytest.mark.clip_runtime
def test_unknown_condition_holdout_matches_fixed_clip_runtime() -> None:
    case_root = IMAGE_ROOT / "image-holdout-006"
    collection = load_json(case_root / "collection.json")
    labels = load_json(case_root / "labels.json")
    references = load_json(case_root / "references.json")
    result = load_json(case_root / "result.json")

    conditions = build_visual_condition_set(
        source_input="机の端を挟むクランプ式のデスクライト",
        drafts=(
            VisualConditionDraft(
                source_phrase="机の端を挟むクランプ式",
                strength="required",
            ),
        ),
    )
    reference_images = tuple(
        load_proxy_image(case_root / item["path"], item["sha256"], item["role"])
        for item in references["references"]
    )
    reference_hashes = tuple(compute_phash(image) for image in reference_images)
    reference_set = build_counterfactual_reference_set(
        condition_set=conditions,
        desired_image_hash=reference_hashes[0],
        counterfactual_image_hashes=(reference_hashes[1],),
    )
    candidates = tuple(
        load_proxy_image(
            case_root / item["path"],
            item["sha256"],
            item["candidate_id"],
        )
        for item in collection["candidates"]
    )
    embeddings = encode_images((*reference_images, *candidates))
    candidate_scores = tuple(
        score_minimum_positive_conditions(
            condition_set=conditions,
            reference_set=reference_set,
            reference_embeddings=embeddings[:2],
            candidate_embedding=embedding,
        )
        for embedding in embeddings[2:]
    )
    calibration = calibrate_minimum_positive_batch(candidate_scores)
    condition = calibration.conditions[0]
    assert condition.calibrated_margins is not None

    label_by_id = {item["candidate_id"]: item["label"] for item in labels["labels"]}
    values_by_label = {
        label: tuple(
            value
            for candidate, value in zip(
                collection["candidates"], condition.calibrated_margins, strict=True
            )
            if label_by_id[candidate["candidate_id"]] == label
        )
        for label in ("match", "mismatch", "ambiguous")
    }

    recorded_calibration = result["calibration"]
    assert condition.status == recorded_calibration["status"]
    for field in ("observed_minimum", "observed_maximum", "center", "half_span"):
        assert getattr(condition, field) == pytest.approx(recorded_calibration[field])

    for label, values in values_by_label.items():
        recorded = result["evaluation"][label]
        assert len(values) == recorded["count"]
        assert min(values) == pytest.approx(recorded["minimum"])
        assert statistics.median(values) == pytest.approx(recorded["median"])
        assert max(values) == pytest.approx(recorded["maximum"])

    match = values_by_label["match"]
    mismatch = values_by_label["mismatch"]
    true_positive = sum(value >= COMMON_DECISION_THRESHOLD for value in match)
    true_negative = sum(value < COMMON_DECISION_THRESHOLD for value in mismatch)
    evaluation_count = len(match) + len(mismatch)
    assert true_positive == result["evaluation"]["true_positive"]
    assert len(match) - true_positive == result["evaluation"]["false_negative"]
    assert true_negative == result["evaluation"]["true_negative"]
    assert len(mismatch) - true_negative == result["evaluation"]["false_positive"]
    assert (true_positive + true_negative) / evaluation_count == pytest.approx(
        result["evaluation"]["accuracy"]
    )
    assert pairwise_auc(match, mismatch) == pytest.approx(result["evaluation"]["pairwise_auc"])
    assert phash_hamming_distance(*reference_hashes) == result["reference_phash_distance"]
    assert result["runtime_sha256"] == embeddings[0].runtime_sha256
    assert result["score_profile_sha256"] == minimum_positive_profile_sha256()
    assert result["calibration_profile_sha256"] == calibration_profile_sha256()
    assert MINIMUM_POSITIVE_RANKING_ENABLED is False
