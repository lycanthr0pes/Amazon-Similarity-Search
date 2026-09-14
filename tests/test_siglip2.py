"""SigLIP model binding, numerical boundaries and candidate integration."""

import inspect
import json
import math
from pathlib import Path

import pytest

from src.search_v2 import siglip2
from src.search_v2.candidate_flow import CandidateSearchFlow
from src.search_v2.counterfactual_v4 import score_minimum_positive_conditions
from src.search_v2.image_similarity import clip_runtime_profile_sha256
from src.search_v2.relative_image_ranking import build_siglip2_appearance_batch
from src.search_v2.provisional_counterfactual import ProvisionalImageCandidateInput


def vector(x, y):
    norm = math.hypot(x, y)
    return (x / norm, y / norm) + (0.0,) * 766


def embedding(pixel, x, y):
    return siglip2.Siglip2Embedding(
        schema_version="2.0",
        image_pixel_sha256=pixel,
        runtime_sha256=siglip2.runtime_sha256(),
        values=vector(x, y),
    )


def test_candidate_default_and_runtime_are_siglip2():
    assert (
        inspect.signature(CandidateSearchFlow).parameters["image_score_mode"].default
        == "siglip2_text_image"
    )
    assert siglip2.runtime_sha256() != clip_runtime_profile_sha256()


def test_reference_margin_matches_trial_and_rejects_clip_runtime():
    import test_search_v2_counterfactual_product_evaluator as fixture

    _, conditions, references, images, _ = fixture.inputs(product_count=1)
    refs = (embedding(images[0].pixel_sha256, 1, 0), embedding(images[1].pixel_sha256, 0, 1))
    candidate = embedding("a" * 64, 4, 3)
    kwargs = dict(
        condition_set=conditions,
        reference_set=references,
        reference_embeddings=refs,
        candidate_embedding=candidate,
    )
    result = siglip2.score_conditions(**kwargs)
    batch = build_siglip2_appearance_batch(
        (
            ProvisionalImageCandidateInput(
                normalized_product_sha256="b" * 64,
                candidate_image_pixel_sha256="a" * 64,
                score=result,
            ),
        )
    )
    assert batch.candidates[0].image_score == pytest.approx(0.6)
    assert batch.profile_id == "siglip2-appearance-image-v1"
    assert type(batch).model_validate_json(batch.model_dump_json()) == batch
    with pytest.raises(ValueError):
        score_minimum_positive_conditions(**kwargs)
    with pytest.raises(ValueError):
        type(batch).model_validate(
            batch.model_copy(update={"runtime_sha256": clip_runtime_profile_sha256()})
        )


def test_invalid_embeddings_and_assets_are_rejected(tmp_path):
    with pytest.raises(ValueError):
        siglip2.Siglip2Embedding.model_validate(
            embedding("a" * 64, 1, 0).model_copy(update={"values": (0.0,) * 768})
        )
    with pytest.raises(ValueError, match="SigLIP"):
        siglip2.verify_assets(tmp_path)


@pytest.mark.parametrize("failure", ["missing", "close"])
def test_missing_and_indistinguishable_references_are_not_forced_to_zero(failure):
    import test_search_v2_counterfactual_product_evaluator as fixture

    _, conditions, references, images, _ = fixture.inputs(product_count=1)
    refs = tuple(embedding(image.pixel_sha256, 1, 0) for image in images)
    result = siglip2.score_conditions(
        condition_set=conditions,
        reference_set=references,
        reference_embeddings=refs,
        candidate_embedding=None if failure == "missing" else embedding("a" * 64, 0, 1),
    )
    assert result.status == ("missing" if failure == "missing" else "unknown")
    assert all(m.normalized_margin is None for m in result.condition_margins)


def test_legacy_approval_ranking_and_history_with_siglip2(tmp_path, monkeypatch):
    import test_candidate_search_live_e2e as live
    from src.search_v2 import counterfactual_product_evaluator as evaluator

    module, config, services, events, _ = live.setup_run(tmp_path, monkeypatch)
    calls = []

    def encode(images, **kwargs):
        calls.append(len(images))
        return tuple(
            embedding(im.pixel_sha256, 1 if i == 0 else 0, 0 if i == 0 else 1)
            for i, im in enumerate(images)
        )

    monkeypatch.setattr(evaluator, "run_pinned_siglip2_image_encoder", encode)
    result = module.run_candidate_e2e(config, services, image_score_mode="siglip2_appearance")
    assert result["status"] == "succeeded"
    assert len(events) == 2 and result["cloudflare_calls"] == 2
    assert result["ranking_profile_id"] == "candidate-siglip2-appearance-v1"
    history = json.loads((config.output_dir / "history.json").read_text())
    assert history["provisional_profile_id"] == "counterfactual-siglip2-appearance-v1"
    assert history["runtime_sha256"] == siglip2.runtime_sha256()
    assert history["known_holdout_accuracy"] is None
    assert calls == [2, 4]


@pytest.mark.parametrize("kind", ["wrong_dimension", "nan", "zero", "wrong_count", "transport"])
def test_encoder_rejects_invalid_output_without_fallback(tmp_path, monkeypatch, kind):
    import test_search_v2_counterfactual_product_evaluator as fixture

    monkeypatch.setattr(siglip2, "verify_assets", lambda _: None)

    class Encoder:
        def encode_images(self, **kwargs):
            if kind == "transport":
                raise RuntimeError("private-output-must-not-escape")
            return {
                "wrong_dimension": ((1.0,) * 512,),
                "nan": ((float("nan"),) * 768,),
                "zero": ((0.0,) * 768,),
                "wrong_count": (),
            }[kind]

    with pytest.raises(ValueError, match="^SigLIP 2 image encoding failed$"):
        siglip2.run_pinned_siglip2_image_encoder(
            (fixture.proxy_image("sample"),), asset_root=tmp_path, encoder=Encoder()
        )


def test_local_worker_timeout_is_bounded_and_does_not_inherit_credentials(tmp_path, monkeypatch):
    import subprocess
    import test_search_v2_counterfactual_product_evaluator as fixture
    import sys

    monkeypatch.setattr(siglip2, "verify_assets", lambda _: None)
    monkeypatch.setenv("OUTSCRAPER_API_KEY", "synthetic-private-key")
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        assert "OUTSCRAPER_API_KEY" not in kwargs["env"]
        assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
        assert kwargs["timeout"] == 600
        assert kwargs["stderr"] == subprocess.DEVNULL
        raise subprocess.TimeoutExpired(argv, 600)

    monkeypatch.setattr(siglip2.subprocess, "run", run)
    with pytest.raises(ValueError, match="^SigLIP 2 local worker failed$"):
        siglip2.LocalSiglip2ImageEncoder(Path(sys.executable)).encode_images(
            images=(fixture.proxy_image("sample"),), asset_root=tmp_path
        )
    assert len(calls) == 1


def test_runtime_change_during_encoding_is_rejected(tmp_path, monkeypatch):
    import test_search_v2_counterfactual_product_evaluator as fixture

    monkeypatch.setattr(siglip2, "verify_assets", lambda _: None)

    class Encoder:
        def encode_images(self, **kwargs):
            monkeypatch.setattr(siglip2, "runtime_sha256", lambda: "f" * 64)
            return (vector(1, 0),)

    with pytest.raises(ValueError, match="SigLIP"):
        siglip2.run_pinned_siglip2_image_encoder(
            (fixture.proxy_image("sample"),), asset_root=tmp_path, encoder=Encoder()
        )


def test_multiple_conditions_keep_the_worst_compatible_positive():
    import test_search_v2_counterfactual_v4 as fixture

    conditions, references = fixture.two_conditions()
    pixel_ids = (
        references.desired_image_hash.image_pixel_sha256,
        *(r.image_hash.image_pixel_sha256 for r in references.counterfactuals),
    )
    refs = tuple(
        embedding(pixel, x, y)
        for pixel, (x, y) in zip(pixel_ids, [(1, 0), (0, 1), (1, 1)], strict=True)
    )
    result = siglip2.score_conditions(
        condition_set=conditions,
        reference_set=references,
        reference_embeddings=refs,
        candidate_embedding=embedding("a" * 64, 1, 0),
    )
    expected_raw = 1 / math.sqrt(2)
    expected_distance = (1 + 1 - 1 / math.sqrt(2)) / 2
    assert result.condition_margins[0].raw_margin == pytest.approx(expected_raw)
    assert result.condition_margins[0].reference_distance == pytest.approx(expected_distance)
    assert result.condition_margins[1].raw_margin == pytest.approx(-1 / math.sqrt(2))


def test_asset_read_access_time_is_not_treated_as_model_modification(tmp_path, monkeypatch):
    import hashlib
    import os

    payload = b"fixed-model-fixture"
    asset = tmp_path / "model.bin"
    asset.write_bytes(payload)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"files": {"model.bin": hashlib.sha256(payload).hexdigest()}}))
    monkeypatch.setattr(siglip2, "_MANIFEST", manifest)
    original = Path.stat
    reads = []

    def stat(path, *args, **kwargs):
        value = original(path, *args, **kwargs)
        if path == asset:
            reads.append(1)
            fields = list(value)
            fields[7] += len(reads)
            return os.stat_result(fields)
        return value

    monkeypatch.setattr(Path, "stat", stat)
    siglip2.verify_assets(tmp_path)
    assert len(reads) == 2
