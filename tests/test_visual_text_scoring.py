"""Independent visual routes, polarity, missing evidence and durable history."""

from types import SimpleNamespace
from pathlib import Path
import hashlib
import subprocess
import sys

import pytest

from src.search_v2 import visual_text_scoring as text
from src.search_v2 import siglip2
from src.search_v2.candidate_completion import CandidateVisualRanking
from src.search_v2.browser_history import history_product
from src.search_v2.visual_contrast import VisualContrast
import test_candidate_connected_flow as connected
import test_search_v2_counterfactual_product_evaluator as fixture
from test_siglip2 import embedding, vector


def conditions():
    _, cs, _, _, _ = fixture.inputs(product_count=1)
    c = cs.conditions[0].model_copy(
        update={
            "contrast": VisualContrast(
                origin="local", matching="A red product", opposite="A blue product"
            )
        }
    )
    return cs.model_copy(update={"conditions": (c,)})


def score(monkeypatch, tmp_path, cs=None, rows=None, missing=False):
    monkeypatch.setattr(siglip2, "verify_assets", lambda _: None)
    im = fixture.proxy_image("text-target")
    encoder = SimpleNamespace(encode_texts=lambda **_: rows or (vector(1, 0),))
    return text.score_visual_text(
        cs or conditions(),
        [("a" * 64, None if missing else im)],
        () if missing else (embedding(im.pixel_sha256, 0.6, 0.8),),
        asset_root=tmp_path,
        encoder=encoder,
    )


def test_text_score_uses_condition_and_product_only(monkeypatch, tmp_path):
    result = score(monkeypatch, tmp_path)
    assert result.candidates[0].score == pytest.approx(0.8)
    assert (
        result.candidates[0].conditions[0].text_sha256
        == hashlib.sha256(b"this is a photo of a red product.").hexdigest()
    )
    assert result.condition_set_sha256 == text.visual_condition_set_sha256(conditions())
    # No generated reference-image argument exists in this path.
    assert text.VisualTextBatch.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValueError):
        text.VisualTextComponent.model_validate(
            result.candidates[0].model_copy(update={"score": 0.9})
        )


def test_excluded_direction_is_applied_exactly_once():
    cs = conditions()
    excluded = cs.model_copy(
        update={"conditions": (cs.conditions[0].model_copy(update={"strength": "excluded"}),)}
    )
    assert text.condition_texts(cs) == ("this is a photo of a red product.",)
    assert text.condition_texts(excluded) == ("this is a photo of a blue product.",)
    with pytest.raises(ValueError):
        text.condition_texts(
            cs.model_copy(
                update={"conditions": (cs.conditions[0].model_copy(update={"contrast": None}),)}
            )
        )


def test_missing_image_is_unscored_without_calling_text_encoder(monkeypatch, tmp_path):
    result = score(monkeypatch, tmp_path, missing=True)
    assert result.candidates[0].score is None
    assert result.candidates[0].conditions == ()


@pytest.mark.parametrize(
    "row", [(0.0,) * 768, (float("nan"),) * 768, (float("inf"),) * 768, (1.0,) * 512]
)
def test_invalid_text_embeddings_are_rejected(monkeypatch, tmp_path, row):
    with pytest.raises(ValueError, match="^SigLIP 2 visual text scoring failed$"):
        score(monkeypatch, tmp_path, rows=(row,))


def test_new_default_roundtrips_both_routes_and_rejects_old_profile(tmp_path, monkeypatch):
    from src.search_v2 import counterfactual_product_evaluator as evaluator

    from src.search_v2.condition_terms import LocalConditionExpander
    from test_candidate_bilingual_scoring import Dictionary, Translator

    flow, _, _, repository, _ = connected.start(
        tmp_path,
        image_score_mode="siglip2_text_image",
        condition_expander=LocalConditionExpander(Dictionary(), translator=Translator()),
    )
    connected.approve(flow)
    connected.fetch(flow, tmp_path)
    kwargs, _ = connected.clip(monkeypatch, tmp_path)
    calls = []

    def encode(images, **_):
        calls.append(len(images))
        return tuple(
            embedding(im.pixel_sha256, 1 if i == 0 else 0, 0 if i == 0 else 1)
            for i, im in enumerate(images)
        )

    monkeypatch.setattr(evaluator, "run_pinned_siglip2_image_encoder", encode)
    monkeypatch.setattr(siglip2, "verify_assets", lambda _: None)
    kwargs["encoder"] = SimpleNamespace(encode_texts=lambda **_: (vector(0, 1),))
    result = flow.complete(owner_id=connected.OWNER, **kwargs)
    assert result.ranking.profile_id == text.RANKING_PROFILE
    assert result.ranking.sort_profile_id == text.SORT_PROFILE
    assert calls == [2, 4]
    assert (
        CandidateVisualRanking.model_validate_json(result.ranking.model_dump_json())
        == result.ranking
    )
    assert (
        repository.get(
            owner_id=connected.OWNER,
            locator=result.history.locator,
            now=connected.candidate.flow.NOW,
        )
        == result.history
    )
    assert all(p.visual_text is not None for p in result.history.products)
    for p in result.history.products:
        browser = history_product(p)
        assert browser["scores"]["textImage"] == p.visual_text.score
        assert browser["scores"]["image"] == p.image_score
    with pytest.raises(ValueError):
        CandidateVisualRanking.model_validate(
            result.ranking.model_copy(
                update={"sort_profile_id": "excluded-title-conditions-image-review-v1"}
            )
        )
    products = result.ranking.products
    with pytest.raises(ValueError):
        CandidateVisualRanking.model_validate(
            result.ranking.model_copy(
                update={
                    "products": (
                        products[0].model_copy(update={"visual_text": None}),
                        *products[1:],
                    )
                }
            )
        )


def test_text_worker_is_bounded_and_does_not_inherit_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr(siglip2, "verify_assets", lambda _: None)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "private-fixture")

    def run(argv, **kw):
        assert kw["timeout"] == 600
        assert "CLOUDFLARE_API_TOKEN" not in kw["env"]
        assert kw["env"]["HF_HUB_OFFLINE"] == "1"
        assert kw["stderr"] == subprocess.DEVNULL
        assert "this is a photo" not in " ".join(argv)
        raise subprocess.TimeoutExpired(argv, 600)

    monkeypatch.setattr(text.subprocess, "run", run)
    with pytest.raises(ValueError, match="^SigLIP 2 text worker failed$"):
        text.LocalSiglip2MultimodalEncoder(Path(sys.executable)).encode_texts(
            texts=text.condition_texts(conditions()), asset_root=tmp_path
        )


def test_minimum_of_all_conditions_is_independent_of_candidate_batch(monkeypatch, tmp_path):
    import test_search_v2_counterfactual_v4 as multi

    cs, _ = multi.two_conditions()
    cs = cs.model_copy(
        update={
            "conditions": tuple(
                c.model_copy(
                    update={
                        "contrast": VisualContrast(
                            origin="local", matching="A red product", opposite="A blue product"
                        )
                    }
                )
                for c in cs.conditions
            )
        }
    )
    result = score(monkeypatch, tmp_path, cs=cs, rows=(vector(1, 0), vector(0, 1)))
    row = result.candidates[0]
    assert [c.score for c in row.conditions] == pytest.approx([0.8, 0.9])
    assert row.score == pytest.approx(0.8)


def test_indistinguishable_generated_images_do_not_disable_text_scoring(tmp_path, monkeypatch):
    from src.search_v2 import counterfactual_product_evaluator as evaluator

    products, _, _, _, _ = fixture.inputs(product_count=1)
    cs = conditions()
    # Build references for exactly these conditions using the existing fixture hashes.
    _, _, references, images, _ = fixture.inputs(product_count=1)
    proxy = fixture.FakeProxyService(
        {products.products[0].image_urls[0]: fixture.proxy_image("candidate")}
    )
    references = references.model_copy(
        update={"condition_set_sha256": text.visual_condition_set_sha256(cs)}
    )

    def encode(pictures, **_):
        return tuple(embedding(im.pixel_sha256, 1, 0) for im in pictures)

    monkeypatch.setattr(evaluator, "run_pinned_siglip2_image_encoder", encode)
    monkeypatch.setattr(siglip2, "verify_assets", lambda _: None)
    batch = evaluator.evaluate_counterfactual_product_images(
        product_batch=products,
        condition_set=cs,
        reference_set=references,
        reference_images=images,
        proxy_service=proxy,
        asset_root=tmp_path,
        encoder=SimpleNamespace(encode_texts=lambda **_: (vector(1, 0),)),
        score_mode="siglip2_text_image",
    )
    assert batch.candidates[0].image_score is None
    assert batch.text_batch.candidates[0].score == pytest.approx(1.0)
