"""Relative ordering retains computable evidence without requiring a mixed batch."""

import json
import pytest
import test_search_v2_provisional_counterfactual as fixture
import test_candidate_search as candidate
import test_candidate_search_live_e2e as live


def build(items):
    from src.search_v2.relative_image_ranking import build_relative_image_batch

    return build_relative_image_batch(items)


@pytest.mark.parametrize(
    "values", [(0.3,), (0.3, 0.6, 0.8), (-0.8, -0.6, -0.3), (0.3,) * 4, (0.0,) * 4]
)
def test_computable_margins_do_not_require_count_spread_or_signs(values):
    batch = build(tuple(fixture.candidate(str(i), v) for i, v in enumerate(values)))
    assert batch.status == "ready"
    assert [c.image_score for c in batch.candidates] == pytest.approx([(v + 1) / 2 for v in values])
    assert all(c.reason == "scored" for c in batch.candidates)
    assert type(batch).model_validate_json(batch.model_dump_json()) == batch


def test_candidate_insertion_does_not_change_existing_scores():
    first = fixture.candidate("a", 0.4)
    assert (
        build((first,)).candidates[0] == build((first, fixture.candidate("b", -0.8))).candidates[0]
    )


def test_partial_reference_failure_preserves_other_condition():
    item = fixture.candidate("a", 0.4, 0.7)
    margins = item.score.condition_margins
    broken = margins[1].model_copy(
        update={
            "status": "reference_too_close",
            "reference_distance": 0.0,
            "normalized_margin": None,
        }
    )
    item = item.model_copy(
        update={
            "score": item.score.model_copy(
                update={"status": "unknown", "condition_margins": (margins[0], broken)}
            )
        }
    )
    row = build((item,)).candidates[0]
    assert row.image_score == pytest.approx(0.7)
    assert row.reason == "partial_conditions" and row.usable_condition_count == 1


def test_all_indistinguishable_references_remain_unknown():
    item = fixture.candidate("a", 0.4)
    margin = item.score.condition_margins[0].model_copy(
        update={
            "status": "reference_too_close",
            "reference_distance": 0.0,
            "normalized_margin": None,
        }
    )
    item = item.model_copy(
        update={
            "score": item.score.model_copy(
                update={"status": "unknown", "condition_margins": (margin,)}
            )
        }
    )
    row = build((item,)).candidates[0]
    assert row.status == "unknown" and row.image_score is None
    assert row.reason == "indistinguishable_references"


@pytest.mark.parametrize("change", ["duplicate", "binding", "nan", "profile"])
def test_invalid_evidence_is_still_rejected(change):
    a, b = fixture.candidate("a", 0.3), fixture.candidate("b", 0.4)
    if change == "duplicate":
        b = a
    elif change == "binding":
        b = b.model_copy(
            update={"score": b.score.model_copy(update={"reference_set_sha256": "0" * 64})}
        )
    elif change == "profile":
        b = b.model_copy(
            update={"score": b.score.model_copy(update={"score_profile_sha256": "0" * 64})}
        )
    else:
        m = b.score.condition_margins[0].model_copy(update={"normalized_margin": float("nan")})
        b = b.model_copy(update={"score": b.score.model_copy(update={"condition_margins": (m,)})})
    with pytest.raises(ValueError):
        build((a, b))


def test_original_translation_scores_english_without_expanding_request(tmp_path):
    s = candidate.module().prepare_candidate_search(
        "マグカップ",
        owner_id="owner-1",
        session_id="translation",
        postal_code="100-0001",
        normalization_profile=candidate.flow.backend_policy().normalization_profile,
        now=candidate.flow.NOW,
        lexical_expander=live.lexical_expander(),
    )
    before = s.plan.request
    review, _ = candidate.retrieve(
        s, tmp_path, [{"name": "Thermal mug"}, {"name": "マグカップ"}, {"name": "Storage box"}]
    )
    s.confirm(
        owner_id="owner-1", review_sha256=review.sha256, selections={}, now=candidate.flow.NOW
    )
    ranked = s.rank(owner_id="owner-1", now=candidate.flow.NOW)
    assert {p.product.title: p.lexical_score for p in ranked.products} == {
        "Thermal mug": 1.0,
        "マグカップ": 1.0,
        "Storage box": 0.0,
    }
    assert ranked.retrieval_plan.request == before
    assert [q.value for q in before.queries] == ["マグカップ"]


def test_candidate_completion_uses_relative_profile(tmp_path, monkeypatch):
    module, config, services, _, _ = live.setup_run(tmp_path, monkeypatch)
    result = module.run_candidate_e2e(config, services, image_score_mode="appearance")
    assert result["status"] == "succeeded"
    assert result["ranking_profile_id"] == "candidate-appearance-v1"
    assert result["image_evaluated"] == 4
    history = json.loads((config.output_dir / "history.json").read_text())
    assert history["known_holdout_accuracy"] is None


@pytest.mark.parametrize("count", [1, 2])
def test_relative_evaluator_reuses_equal_pixels_without_dropping_products(monkeypatch, count):
    from pathlib import Path
    import test_search_v2_counterfactual_product_evaluator as e

    batch, conditions, refs, images, _ = e.inputs(product_count=count)
    product_image = e.proxy_image("shared-product-image")
    proxy = e.FakeProxyService({p.image_urls[0]: product_image for p in batch.products})
    calls = e.fake_clip(
        monkeypatch,
        {
            images[0].pixel_sha256: e.unit_vector(1.0, 0.0),
            images[1].pixel_sha256: e.unit_vector(0.0, 1.0),
            product_image.pixel_sha256: e.unit_vector(0.8, 0.6),
        },
    )
    result = e.evaluator.evaluate_counterfactual_product_images(
        product_batch=batch,
        condition_set=conditions,
        reference_set=refs,
        reference_images=images,
        proxy_service=proxy,
        asset_root=Path("unused"),
        encoder=object(),
        score_mode="relative",
    )
    assert [c.image_score for c in result.candidates] == pytest.approx([0.6] * count)
    assert calls == [2, 1]
