"""Whole-image similarity supports arbitrary targets without claiming part geometry."""

import json
import pytest

import test_candidate_search_live_e2e as live
import test_candidate_visual_conditions as visual
import test_search_v2_provisional_counterfactual as scores


@pytest.mark.parametrize("target", ["body of the mug", "back of the chair", "sleeve of the jacket"])
def test_shape_uses_whole_image_without_mandatory_regions(tmp_path, monkeypatch, target):
    old = visual.draft

    def draft(*args, **kwargs):
        return {
            **old(*args, **kwargs),
            "focus": {
                "kind": "shape",
                "scope": "part",
                "target": target,
                "measure": "side_bulge",
                "direction": "higher",
            },
        }

    class ForbiddenRegions:
        def extract(self, *args):
            pytest.fail("Default appearance scoring must not require segmentation")

    monkeypatch.setattr(visual, "draft", draft)
    module, config, services, _, _ = live.setup_run(tmp_path, monkeypatch)
    captured = []
    original_output = module._history_output

    def capture(config, result, flow, now):
        captured.append(result.ranking)
        return original_output(config, result, flow, now)

    monkeypatch.setattr(module, "_history_output", capture)
    result = module.run_candidate_e2e(
        config, services, region_extractor=ForbiddenRegions(), image_score_mode="appearance"
    )
    assert result["status"] == "succeeded"
    assert result["ranking_profile_id"] == "candidate-appearance-v1"
    assert result["image_evaluated"] == 4
    history = json.loads((config.output_dir / "history.json").read_text())
    assert history["provisional_profile_id"] == "counterfactual-appearance-v1"
    assert history["known_holdout_accuracy"] is None
    from src.search_v2.candidate_completion import CandidateVisualRanking

    ranking = CandidateVisualRanking.model_validate_json(captured[0].model_dump_json())
    assert ranking.image_batch.evidence_scope == "whole_image_similarity"
    assert ranking.image_batch.profile_id == "appearance-image-v1"
    assert all(not hasattr(row.image, "shapes") for row in ranking.products)
    with pytest.raises(ValueError):
        CandidateVisualRanking.model_validate(
            ranking.model_copy(update={"profile_id": "candidate-lexical-clip-v3"})
        )


def test_appearance_batch_binds_scope_and_retains_relative_evidence():
    from src.search_v2.relative_image_ranking import build_appearance_image_batch

    row = scores.candidate("one", 0.4)
    batch = build_appearance_image_batch((row,))
    assert batch.candidates[0].image_score == pytest.approx(0.7)
    assert type(batch).model_validate_json(batch.model_dump_json()) == batch
    with pytest.raises(ValueError):
        type(batch).model_validate(batch.model_copy(update={"evidence_scope": "part_verified"}))
    with pytest.raises(ValueError):
        type(batch).model_validate(batch.model_copy(update={"profile_sha256": "0" * 64}))


def test_generic_visual_request_does_not_require_geometry_selection():
    from src.search_v2.bonsai_visual_conditions import build_visual_request

    request = json.loads(build_visual_request("上着。袖が丸い形。"))
    variants = request["response_format"]["schema"]["properties"]["conditions"]["items"]["anyOf"]
    for variant in variants:
        focus = variant["properties"]["focus"]["anyOf"][0]
        assert focus["properties"]["measure"]["type"] == "null"
        assert focus["properties"]["direction"]["type"] == "null"


@pytest.mark.parametrize("failure", ["missing_image", "indistinguishable_references"])
def test_unusable_appearance_evidence_remains_unknown_without_dropping_products(
    monkeypatch, failure
):
    from pathlib import Path
    import test_search_v2_counterfactual_product_evaluator as fixture

    products, conditions, references, images, _ = fixture.inputs(product_count=1)
    product = fixture.proxy_image("appearance-candidate")
    mapping = {} if failure == "missing_image" else {products.products[0].image_urls[0]: product}
    fixture.fake_clip(
        monkeypatch,
        {
            images[0].pixel_sha256: fixture.unit_vector(1, 0),
            images[1].pixel_sha256: fixture.unit_vector(1, 0),
            product.pixel_sha256: fixture.unit_vector(0, 1),
        },
    )
    result = fixture.evaluator.evaluate_counterfactual_product_images(
        product_batch=products,
        condition_set=conditions,
        reference_set=references,
        reference_images=images,
        proxy_service=fixture.FakeProxyService(mapping),
        asset_root=Path("unused"),
        encoder=object(),
        score_mode="appearance",
    )
    assert len(result.candidates) == 1
    assert result.candidates[0].image_score is None
    assert result.candidates[0].reason == failure
    assert result.evidence_scope == "whole_image_similarity"
