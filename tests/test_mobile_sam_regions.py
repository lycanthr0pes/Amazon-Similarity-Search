"""Separate instances using semantic evidence, never desired-shape scores."""

import importlib
import numpy as np
import pytest


def module():
    return importlib.import_module("src.search_v2.region_refinement")


def objects():
    left = np.zeros((64, 96), bool)
    left[12:52, 8:38] = True
    right = np.zeros_like(left)
    right[12:52, 58:88] = True
    return left, right


def test_two_objects_are_not_combined_into_one_shape():
    left, right = objects()
    heat = np.where(left | right, 0.95, 0.05)
    selected = module().choose_regions((left | right, left, right), heat)
    assert len(selected) == 2
    assert np.array_equal(selected[0], left)
    assert np.array_equal(selected[1], right)


def test_semantic_target_beats_large_background_and_does_not_fill_real_hole():
    left, _ = objects()
    ring = left.copy()
    ring[20:44, 16:30] = False
    heat = np.where(ring, 0.95, 0.05)
    selected = module().choose_regions((np.ones_like(left), left, ring), heat)
    assert len(selected) == 1
    assert np.array_equal(selected[0], ring)


def test_no_target_does_not_silently_select_sam_object():
    left, right = objects()
    assert module().choose_regions((left, right), np.full(left.shape, 0.1)) == ()


def test_nested_duplicates_do_not_become_extra_instances():
    left, _ = objects()
    small = left.copy()
    small[12:17] = False
    selected = module().choose_regions((small, left), np.where(left, 0.95, 0.05))
    assert len(selected) == 1 and np.array_equal(selected[0], left)


@pytest.mark.parametrize("invalid", ["nan", "shape", "count"])
def test_refinement_rejects_invalid_model_evidence(invalid):
    left, right = objects()
    heat = np.where(left | right, 0.95, 0.05)
    candidates = (left, right)
    if invalid == "nan":
        heat[0, 0] = float("nan")
    elif invalid == "shape":
        heat = heat[:10]
    else:
        candidates = candidates * 257
    with pytest.raises(ValueError):
        module().choose_regions(candidates, heat)


def test_mobile_sam_mode_preserves_region_interface_and_records_diagnostics(tmp_path, monkeypatch):
    from pathlib import Path
    import json
    from types import SimpleNamespace
    import src.search_v2.clipseg_regions as adapter
    import test_search_v2_counterfactual_product_evaluator as fixture

    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"files": {}}))
    monkeypatch.setattr(adapter, "_MANIFEST", manifest)
    monkeypatch.setattr(adapter, "_MOBILE_MANIFEST", manifest, raising=False)
    python = tmp_path / "python"
    python.touch()
    service = adapter.LocalClipSegRegions(
        python=python, assets=tmp_path, mobile_sam_assets=tmp_path
    )
    image = fixture.proxy_image("mobile-region-fixture")

    def run(argv, **kwargs):
        assert argv[2].endswith("mobile_sam_worker.py")
        assert kwargs["timeout"] == 600
        assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
        root = Path(argv[-1])
        task = json.loads((root / "task.json").read_text())
        assert task["mobile_sam_assets"] == str(tmp_path)
        assert np.load(root / "images.npy").shape == (1, 512, 512, 3)
        masks = np.zeros((1, 1, 512, 512), np.uint8)
        masks[0, 0, 100:300, 100:300] = 1
        np.save(root / "masks.npy", masks)
        (root / "diagnostics.json").write_text(
            json.dumps(
                {
                    "seconds": 1.0,
                    "rows": [
                        {
                            "image_index": 0,
                            "target_index": 0,
                            "proposal_count": 2,
                            "instance_count": 1,
                            "refined_count": 1,
                            "status": "available",
                        }
                    ],
                }
            )
        )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(adapter.subprocess, "run", run)
    result = service.extract((image,), ("object body",))
    assert result[(image.pixel_sha256, "object body")].array().sum() == 40000
    assert service.last_diagnostics["rows"][0]["instance_count"] == 1


def test_refinement_prompts_do_not_treat_internal_holes_as_background():
    left, _ = objects()
    heat = np.where(left, 0.9, 0.0)
    heat[20:30, 20:30] = 0.0
    points, labels = module().region_points(heat)
    for (x, y), label in zip(points.astype(int), labels):
        if label == 0:
            assert not (8 <= x < 38 and 12 <= y < 52)


def test_mobile_cli_requires_clipseg_runtime_before_any_service(monkeypatch):
    import sys
    import tools.candidate_search_live_e2e as entry

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "candidate",
            "--mobile-sam-assets",
            "/prepared/sam",
            "--output-dir",
            "/unused/output",
            "--asset-root",
            "/unused/clip",
            "--server-bin",
            "/unused/server",
            "--model-path",
            "/unused/model",
        ],
    )
    with pytest.raises(SystemExit) as exc:
        entry.main()
    assert exc.value.code == 2


def test_mobile_extractor_connects_to_candidate_ranking_and_history(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from types import SimpleNamespace
    import src.search_v2.clipseg_regions as adapter
    import test_candidate_search_live_e2e as live
    import test_candidate_visual_conditions as visual

    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"files": {}}))
    monkeypatch.setattr(adapter, "_MANIFEST", manifest)
    monkeypatch.setattr(adapter, "_MOBILE_MANIFEST", manifest)
    python = tmp_path / "python"
    python.touch()
    extractor = adapter.LocalClipSegRegions(
        python=python, assets=tmp_path, mobile_sam_assets=tmp_path
    )
    old_draft = visual.draft

    def draft(*args, **kwargs):
        return {
            **old_draft(*args, **kwargs),
            "focus": {"kind": "shape", "target": "object body", "scope": "part"},
        }

    monkeypatch.setattr(visual, "draft", draft)

    def run(argv, **kwargs):
        from PIL import Image, ImageDraw

        root = Path(argv[-1])
        images = np.load(root / "images.npy")
        n = len(images)
        masks = np.zeros((n, 1, 512, 512), np.uint8)
        for i in range(n):
            image = Image.new("L", (512, 512))
            draw = ImageDraw.Draw(image)
            (draw.rectangle if i == 1 else draw.ellipse)((100, 100, 400, 400), fill=1)
            masks[i, 0] = np.asarray(image)
        np.save(root / "masks.npy", masks)
        (root / "diagnostics.json").write_text(
            json.dumps(
                {
                    "seconds": 1.0,
                    "rows": [
                        {
                            "image_index": i,
                            "target_index": 0,
                            "proposal_count": 2,
                            "instance_count": 1,
                            "refined_count": 1,
                            "status": "available",
                        }
                        for i in range(n)
                    ],
                }
            )
        )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(adapter.subprocess, "run", run)
    entry, config, services, _, _ = live.setup_run(tmp_path, monkeypatch)
    result = entry.run_candidate_e2e(
        config, services, region_extractor=extractor, image_score_mode="relative"
    )
    assert result["status"] == "succeeded"
    assert result["ranking_profile_id"] == "candidate-attribute-image-v1"
    assert result["history_images_verified"] == 2 and result["image_evaluated"] == 4
    scores = json.loads((config.output_dir / "image-scores.json").read_text())
    assert scores["region_runtime_sha256"] == extractor.runtime_sha256


def test_instance_selection_keeps_parent_object_before_selecting_part():
    body, _ = objects()
    lid = np.zeros_like(body)
    lid[12:18, 8:38] = True
    heat = np.where(body, 0.55, 0.05)
    heat[lid] = 0.99
    selected = module().choose_instances((lid, body), heat)
    assert len(selected) == 1 and np.array_equal(selected[0], body)


def test_instances_remain_separate_when_both_contain_target_parts():
    left, right = objects()
    selected = module().choose_instances(
        (left | right, left, right), np.where(left | right, 0.9, 0.1)
    )
    assert len(selected) == 2
    assert all(not np.array_equal(r, left | right) for r in selected)


def test_semantic_coverage_does_not_prefer_tiny_confident_fragment():
    body, _ = objects()
    fragment = np.zeros_like(body)
    fragment[12:18, 8:38] = True
    heat = np.where(body, 0.55, 0.01)
    heat[fragment] = 0.99
    selected = module().choose_regions((fragment, body), heat)
    assert len(selected) == 1 and np.array_equal(selected[0], body)


def test_instance_selection_rejects_background_with_small_semantic_noise():
    body, _ = objects()
    background = ~body
    heat = np.where(body, 0.9, 0.05)
    heat[0, 0] = 0.8
    selected = module().choose_instances((background, body), heat)
    assert len(selected) == 1 and np.array_equal(selected[0], body)


def test_refined_part_cannot_include_neighbor_outside_selected_instance():
    left, right = objects()
    refined = left | right
    result = module().constrain_region(refined, left)
    assert np.array_equal(result, left)


def test_part_selection_excludes_uncertain_extension_of_object():
    body, _ = objects()
    whole = body.copy()
    whole[20:44, 38:53] = True
    heat = np.where(body, 0.6, 0.01)
    heat[whole & ~body] = 0.49
    selected = module().choose_parts((whole, body), heat)
    assert len(selected) == 1 and np.array_equal(selected[0], body)
