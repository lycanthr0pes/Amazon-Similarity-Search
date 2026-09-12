"""Attribute isolation uses target masks, never RGB as a shape substitute."""

import hashlib
import json

import numpy as np
from PIL import Image, ImageDraw
import pytest

import test_candidate_visual_conditions as visual


def test_bonsai_focus_survives_grounding_and_changes_binding(tmp_path):
    row = visual.draft("丸みのある形")
    row["focus"] = {"kind": "shape", "target": "body of the chair", "scope": "part"}
    service, bonsai = visual.prepare(tmp_path, source="椅子。丸みのある形。", conditions=[row])
    condition = service.plan.visual_conditions.conditions[0]
    assert condition.focus.target == "body of the chair"
    assert json.loads(bonsai.calls[0])["response_format"]["schema"]["properties"]["conditions"][
        "items"
    ]["anyOf"][0]["properties"]["focus"]
    assert type(service.plan).model_validate_json(service.plan.model_dump_json()) == service.plan


def mask(shape="ellipse", size=(160, 160), box=(40, 30, 120, 130)):
    image = Image.new("L", size)
    getattr(ImageDraw.Draw(image), shape)(box, fill=255)
    return np.asarray(image) > 0


def test_shape_score_prefers_contour_independent_of_rgb():
    from src.search_v2.shape_similarity import compare_silhouettes

    desired, negative = mask(), mask("rectangle")
    good = compare_silhouettes(desired, (desired,), negative)
    bad = compare_silhouettes(negative, (desired,), negative)
    assert good.normalized_margin == pytest.approx(1.0)
    assert bad.normalized_margin == pytest.approx(-1.0)


def test_shape_normalization_preserves_aspect_but_removes_position_and_scale():
    from src.search_v2.shape_similarity import silhouette

    first = silhouette(mask("rectangle", box=(40, 30, 119, 129)))
    moved = silhouette(mask("rectangle", size=(240, 240), box=(20, 10, 179, 209)))
    square = silhouette(mask("rectangle", box=(40, 30, 119, 109)))
    assert np.array_equal(first, moved)
    assert not np.array_equal(first, square)


@pytest.mark.parametrize("invalid", [np.zeros((10, 10), bool), np.ones((10, 10), bool)])
def test_absent_or_unbounded_target_is_not_a_shape_match(invalid):
    from src.search_v2.shape_similarity import silhouette

    assert silhouette(invalid) is None


def test_same_reference_shape_is_unusable_even_if_rgb_would_differ():
    from src.search_v2.shape_similarity import compare_silhouettes

    assert compare_silhouettes(mask(), (mask(),), mask()).normalized_margin is None


def test_target_region_binds_pixels_and_target():
    from src.search_v2.shape_similarity import RegionMask

    value = mask()
    region = RegionMask.from_array("a" * 64, "body", value)
    assert region.image_pixel_sha256 == "a" * 64
    assert region.target_sha256 == hashlib.sha256(b"body").hexdigest()
    assert np.array_equal(region.array(), value)
    with pytest.raises(ValueError):
        RegionMask.from_array("invalid", "body", value)


def test_legacy_condition_json_and_digest_do_not_gain_null_focus():
    from src.search_v2.counterfactual_image import (
        VisualConditionDraft,
        build_visual_condition_set,
        visual_condition_set_sha256,
        VISUAL_CONDITION_SET_DOMAIN,
    )

    conditions = build_visual_condition_set(
        source_input="丸い形",
        drafts=(VisualConditionDraft(source_phrase="丸い形", strength="required"),),
    )
    data = conditions.model_dump(mode="json")
    assert "focus" not in data["conditions"][0]
    canonical = json.dumps(
        data, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert (
        visual_condition_set_sha256(conditions)
        == hashlib.sha256(VISUAL_CONDITION_SET_DOMAIN + canonical).hexdigest()
    )


@pytest.mark.parametrize("failure", [None, "missing", "wrong_binding", "exception"])
def test_attribute_flow_reopens_history_and_preserves_failure_reasons(
    tmp_path, monkeypatch, failure
):
    import test_candidate_search_live_e2e as live
    from src.search_v2.shape_similarity import RegionMask

    original = visual.draft

    def focused(*args, **kwargs):
        row = original(*args, **kwargs)
        row["focus"] = {"kind": "shape", "target": "body of the mug", "scope": "part"}
        return row

    monkeypatch.setattr(visual, "draft", focused)
    module, config, services, _, _ = live.setup_run(tmp_path, monkeypatch)

    class Regions:
        runtime_sha256 = "e" * 64

        def extract(self, images, targets):
            assert targets == ("body of the mug",)
            if failure == "exception":
                raise RuntimeError("sensitive-region-failure")
            return {
                (image.pixel_sha256, target): None
                if failure == "missing"
                else RegionMask.from_array(
                    "f" * 64 if failure == "wrong_binding" else image.pixel_sha256,
                    target,
                    mask("rectangle" if index == 1 else "ellipse"),
                )
                for index, image in enumerate(images)
                for target in targets
            }

    result = module.run_candidate_e2e(
        config, services, region_extractor=Regions(), image_score_mode="relative"
    )
    assert result["status"] == "succeeded"
    assert result["ranking_profile_id"] == "candidate-attribute-image-v1"
    assert result["image_evaluated"] == (4 if failure is None else 0)
    scores = json.loads((config.output_dir / "image-scores.json").read_text())
    history = json.loads((config.output_dir / "history.json").read_text())
    assert history["known_holdout_accuracy"] is None
    assert history["provisional_profile_id"] == "counterfactual-attribute-v1"
    assert [p["required_status"] for p in history["products"]] == ["confirmed"] * 3 + [
        "contradicted"
    ]
    expected = (
        "scored"
        if failure is None
        else "region_unavailable"
        if failure == "missing"
        else "extraction_failed"
    )
    assert {p["shapes"][0]["reason"] for p in scores["candidates"]} == {expected}
    assert "sensitive-region-failure" not in (config.output_dir / "image-scores.json").read_text()
    from src.search_v2.attribute_image_ranking import AttributeImageBatch

    parsed = AttributeImageBatch.model_validate_json(json.dumps(scores))
    altered = parsed.candidates[0].shapes[0].model_copy(update={"target_sha256": "0" * 64})
    row = parsed.candidates[0].model_copy(update={"shapes": (altered,)})
    with pytest.raises(ValueError):
        AttributeImageBatch.model_validate(
            parsed.model_copy(update={"candidates": (row, *parsed.candidates[1:])})
        )


def test_unobserved_shape_does_not_outrank_observed_shape(monkeypatch):
    from types import SimpleNamespace
    import src.search_v2.candidate_completion as completion
    from src.search_v2.attribute_image_ranking import AttributeImageComponent

    monkeypatch.setattr(
        completion,
        "candidate_sort_key",
        lambda row, overall_score: (
            0,
            -1.0,
            0.0,
            -overall_score,
            row.product.provenance.response_index,
        ),
    )
    candidate = SimpleNamespace(
        evaluation=None, product=SimpleNamespace(provenance=SimpleNamespace(response_index=0))
    )
    unknown = SimpleNamespace(
        candidate=candidate,
        image=AttributeImageComponent.model_construct(image_score=None),
        total_score=1.0,
    )
    known = SimpleNamespace(
        candidate=candidate,
        image=AttributeImageComponent.model_construct(image_score=0.8),
        total_score=0.96,
    )
    assert completion._sort_key(known) < completion._sort_key(unknown)
