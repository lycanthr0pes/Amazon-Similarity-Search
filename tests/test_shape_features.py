"""Measure the requested geometry, separately from the overall silhouette."""

import importlib
import json

import numpy as np
from PIL import Image, ImageDraw
import pytest


def api():
    return importlib.import_module("src.search_v2.shape_features")


def body(bulge, width=80, height=160, offset=(40, 30), canvas=(240, 240)):
    x0, y0 = offset
    image = Image.new("L", canvas)
    y = np.linspace(0, 1, height)
    widths = width * (1 + bulge * 4 * y * (1 - y))
    points = [(x0 - w / 2, y0 + i) for i, w in enumerate(widths)]
    points += [(x0 + w / 2, y0 + i) for i, w in reversed(list(enumerate(widths)))]
    ImageDraw.Draw(image).polygon(points, fill=1)
    return np.asarray(image, dtype=bool)


def test_bulge_beats_aspect_similarity():
    positive = body(0.65, width=60, offset=(100, 30))
    negative = body(0, width=60, offset=(100, 30))
    good = body(0.65, width=95, height=130, offset=(110, 30))
    bad = body(0, width=65, offset=(100, 30))
    a = api().compare_features(good, (positive,), negative, "side_bulge")
    b = api().compare_features(bad, (positive,), negative, "side_bulge")
    assert a.status == b.status == "scored"
    assert a.margin.normalized_margin > b.margin.normalized_margin


def test_geometry_values_ignore_position_and_uniform_scale():
    first = body(0.65, width=50, height=100, offset=(90, 30))
    second = np.zeros((480, 480), bool)
    second[8:468, 12:472] = np.repeat(np.repeat(first[:230, :230], 2, 0), 2, 1)
    for measure in ("side_bulge", "aspect_ratio", "side_smoothness"):
        assert api().measure_shape(first, measure) == pytest.approx(
            api().measure_shape(second, measure), abs=0.04
        )


def test_reference_difference_in_other_feature_cannot_enable_requested_feature():
    narrow = body(0, width=40, offset=(100, 30))
    wide = body(0, width=110, offset=(100, 30))
    result = api().compare_features(narrow, (narrow,), wide, "side_bulge")
    assert result.status == "feature_reference_too_close"
    assert result.margin.normalized_margin is None
    assert (
        api().compare_features(narrow, (narrow,), wide, "aspect_ratio", direction="lower").status
        == "scored"
    )


def test_unobservable_surface_does_not_fall_back_to_outline():
    m = body(0.6, offset=(100, 30))
    assert api().compare_features(m, (m,), m, "unobservable").status == "unobservable"


def test_empty_and_clipped_masks_do_not_become_geometry_scores():
    good = body(0.5, offset=(100, 30))
    for invalid in (np.zeros((10, 10), bool), np.ones((10, 10), bool)):
        assert (
            api().compare_features(invalid, (good,), good, "side_bulge").status
            == "region_unavailable"
        )


def test_focus_preserves_legacy_bytes_and_restricts_measure_to_shape():
    from src.search_v2.counterfactual_image import VisualFocus

    old = {"kind": "shape", "target": "object body", "scope": "part"}
    assert VisualFocus(**old).model_dump(mode="json") == old
    value = VisualFocus(**old, measure="side_bulge", direction="higher")
    assert value.measure == "side_bulge"
    with pytest.raises(ValueError):
        VisualFocus(kind="color", target="object body", scope="part", measure="side_bulge")


@pytest.mark.parametrize(
    "measure",
    ["side_bulge", "unobservable", "feature_reference_too_close", "reference_direction_mismatch"],
)
def test_feature_flow_connects_to_new_ranking_and_history(tmp_path, monkeypatch, measure):
    import test_attribute_image_ranking as fixture
    import test_candidate_search_live_e2e as live
    import test_candidate_visual_conditions as visual
    from src.search_v2.shape_similarity import RegionMask

    old_draft = visual.draft

    def draft(*args, **kwargs):
        return {
            **old_draft(*args, **kwargs),
            "focus": {
                "kind": "shape",
                "target": "object body",
                "scope": "part",
                "measure": "unobservable" if measure == "unobservable" else "side_bulge",
                "direction": None
                if measure == "unobservable"
                else "lower"
                if measure == "reference_direction_mismatch"
                else "higher",
            },
        }

    monkeypatch.setattr(visual, "draft", draft)
    module, config, services, _, _ = live.setup_run(tmp_path, monkeypatch)

    class Regions:
        runtime_sha256 = "e" * 64

        def extract(self, images, targets):
            assert measure != "unobservable", "Unobservable shape must not invoke segmentation"
            return {
                (im.pixel_sha256, target): RegionMask.from_array(
                    im.pixel_sha256,
                    target,
                    fixture.mask(
                        "rectangle"
                        if i == 1 and measure != "feature_reference_too_close"
                        else "ellipse"
                    ),
                )
                for i, im in enumerate(images)
                for target in targets
            }

    result = module.run_candidate_e2e(
        config, services, region_extractor=Regions(), image_score_mode="relative"
    )
    if measure in {"feature_reference_too_close", "reference_direction_mismatch"}:
        assert result["status"] == "failed"
        assert result["failure_stage"] == "reference_quality"
        assert result["failure_diagnostic"]["code"] == "reference_quality"
        assert result["outscraper_tasks"] == result["clip_batches"] == 0
        assert not (config.output_dir / "history.json").exists()
        reports = json.loads((config.output_dir / "reference-quality.json").read_text())
        assert reports[0]["status"] == (
            "reference_too_close" if measure == "feature_reference_too_close" else measure
        )
        return
    assert result["status"] == "succeeded"
    assert result["ranking_profile_id"] == "candidate-attribute-image-v2"
    assert result["image_evaluated"] == (4 if measure == "side_bulge" else 0)
    history = json.loads((config.output_dir / "history.json").read_text())
    assert history["provisional_profile_id"] == "counterfactual-attribute-v2"
    assert history["known_holdout_accuracy"] is None
    scores = json.loads((config.output_dir / "image-scores.json").read_text())
    assert scores["candidates"][0]["shapes"][0]["feature"]["measure"] == (
        "unobservable" if measure == "unobservable" else "side_bulge"
    )
    if measure != "side_bulge":
        assert all(c["shapes"][0]["reason"] == measure for c in scores["candidates"])
    from src.search_v2.attribute_image_ranking import AttributeImageBatch

    restored = AttributeImageBatch.model_validate_json(json.dumps(scores))
    bad_target = restored.shape_targets[0].model_copy(
        update={"direction": "higher" if measure == "reference_direction_mismatch" else "lower"}
    )
    with pytest.raises(ValueError):
        AttributeImageBatch.model_validate(
            restored.model_copy(update={"shape_targets": (bad_target,)})
        )


def test_reference_must_express_the_approved_direction():
    rounded = body(0.65, width=60, offset=(100, 30))
    straight = body(0, width=60, offset=(100, 30))
    wrong = api().compare_features(rounded, (straight,), rounded, "side_bulge", direction="higher")
    assert wrong.status == "reference_direction_mismatch"
    assert wrong.margin.normalized_margin is None
    assert (
        api()
        .compare_features(straight, (straight,), rounded, "side_bulge", direction="lower")
        .status
        == "scored"
    )


def test_measurement_direction_must_be_explicit_in_new_focus():
    from src.search_v2.counterfactual_image import VisualFocus

    with pytest.raises(ValueError):
        VisualFocus(kind="shape", target="object body", scope="part", measure="side_bulge")


def test_shape_score_rejects_changed_feature_measurements():
    result = api().compare_features(
        body(0.65, offset=(100, 30)),
        (body(0.65, offset=(100, 30)),),
        body(0, offset=(100, 30)),
        "side_bulge",
    )
    with pytest.raises(ValueError):
        api().FeatureComparison.model_validate(result.model_copy(update={"candidate_value": 0.0}))


def test_legacy_shape_evidence_cannot_claim_feature_specific_failure():
    from src.search_v2.attribute_image_ranking import ShapeEvidence
    from src.search_v2.shape_similarity import unavailable_shape

    with pytest.raises(ValueError):
        ShapeEvidence(
            condition_id="visual-condition-001",
            target_sha256="a" * 64,
            candidate_mask_sha256=None,
            reference_mask_sha256=(None, None),
            margin=unavailable_shape(),
            reason="feature_reference_too_close",
        )
