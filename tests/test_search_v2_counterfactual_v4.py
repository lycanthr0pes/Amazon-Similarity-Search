from __future__ import annotations

import hashlib
import math

import pytest

from src.search_v2.counterfactual_image import VisualConditionDraft
from src.search_v2.counterfactual_image import build_counterfactual_reference_set
from src.search_v2.counterfactual_image import build_visual_condition_set
from src.search_v2.counterfactual_image import score_counterfactual_conditions
from src.search_v2.counterfactual_v4 import MINIMUM_POSITIVE_RANKING_ENABLED
from src.search_v2.counterfactual_v4 import CounterfactualV4Error
from src.search_v2.counterfactual_v4 import minimum_positive_profile_sha256
from src.search_v2.counterfactual_v4 import score_minimum_positive_conditions
from src.search_v2.image_similarity import CLIP_EMBEDDING_DIMENSION
from src.search_v2.image_similarity import ClipEmbedding
from src.search_v2.image_similarity import ImagePerceptualHash
from src.search_v2.image_similarity import clip_runtime_profile_sha256


def unit_vector(*components: float) -> tuple[float, ...]:
    norm = math.sqrt(math.fsum(value * value for value in components))
    values = [value / norm for value in components]
    values.extend([0.0] * (CLIP_EMBEDDING_DIMENSION - len(values)))
    return tuple(values)


def embedding(tag: str, *components: float) -> ClipEmbedding:
    return ClipEmbedding(
        schema_version="2.0",
        image_pixel_sha256=hashlib.sha256(tag.encode()).hexdigest(),
        runtime_sha256=clip_runtime_profile_sha256(),
        values=unit_vector(*components),
    )


def image_hash(tag: str, value: int) -> ImagePerceptualHash:
    return ImagePerceptualHash(
        schema_version="2.0",
        image_pixel_sha256=hashlib.sha256(tag.encode()).hexdigest(),
        value=value,
    )


def one_condition():
    conditions = build_visual_condition_set(
        source_input="黒いケトル",
        drafts=(
            VisualConditionDraft(
                source_phrase="黒い",
                strength="required",
                attribute_key="appearance.color",
            ),
        ),
    )
    references = build_counterfactual_reference_set(
        condition_set=conditions,
        desired_image_hash=image_hash("anchor", 0),
        counterfactual_image_hashes=(image_hash("not-black", 0xFF),),
    )
    return conditions, references


def two_conditions():
    conditions = build_visual_condition_set(
        source_input="黒いヘッドレスト付き椅子",
        drafts=(
            VisualConditionDraft(
                source_phrase="黒い",
                strength="required",
                attribute_key="appearance.color",
            ),
            VisualConditionDraft(
                source_phrase="ヘッドレスト付き",
                strength="required",
            ),
        ),
    )
    references = build_counterfactual_reference_set(
        condition_set=conditions,
        desired_image_hash=image_hash("anchor", 0),
        counterfactual_image_hashes=(
            image_hash("not-black", 0xFF),
            image_hash("no-headrest", 0xFF00),
        ),
    )
    return conditions, references


def test_single_condition_is_identical_to_the_original_normalized_margin() -> None:
    conditions, references = one_condition()
    reference_embeddings = (
        embedding("anchor", 1.0, 0.0),
        embedding("not-black", 0.0, 1.0),
    )
    candidate = embedding("candidate", 1.0, 1.0)

    original = score_counterfactual_conditions(
        condition_set=conditions,
        reference_set=references,
        reference_embeddings=reference_embeddings,
        candidate_embedding=candidate,
    )
    v4 = score_minimum_positive_conditions(
        condition_set=conditions,
        reference_set=references,
        reference_embeddings=reference_embeddings,
        candidate_embedding=candidate,
    )

    margin = v4.condition_margins[0]
    assert margin.raw_margin == pytest.approx(original.condition_margins[0].raw_margin)
    assert margin.reference_distance == pytest.approx(
        original.condition_margins[0].reference_distance
    )
    assert margin.normalized_margin == pytest.approx(
        original.condition_margins[0].normalized_margin
    )


def test_multiple_conditions_use_the_worst_compatible_positive_reference() -> None:
    conditions, references = two_conditions()
    root_three_over_two = math.sqrt(3.0) / 2.0
    reference_embeddings = (
        embedding("anchor", 1.0, 0.0),
        embedding("not-black", -0.5, root_three_over_two),
        embedding("no-headrest", -0.5, -root_three_over_two),
    )

    anchor_like = score_minimum_positive_conditions(
        condition_set=conditions,
        reference_set=references,
        reference_embeddings=reference_embeddings,
        candidate_embedding=embedding("candidate-anchor", 1.0, 0.0),
    )
    first_negative_like = score_minimum_positive_conditions(
        condition_set=conditions,
        reference_set=references,
        reference_embeddings=reference_embeddings,
        candidate_embedding=embedding("candidate-not-black", -0.5, root_three_over_two),
    )

    assert anchor_like.status == "scored"
    assert [margin.normalized_margin for margin in anchor_like.condition_margins] == pytest.approx(
        [0.0, 0.0]
    )
    assert first_negative_like.condition_margins[0].normalized_margin == pytest.approx(-1.0)
    assert first_negative_like.condition_margins[1].normalized_margin == pytest.approx(0.0)


def test_missing_candidate_and_unseparated_references_fail_closed() -> None:
    conditions, references = one_condition()
    anchor = embedding("anchor", 1.0, 0.0)
    indistinguishable = ClipEmbedding(
        schema_version="2.0",
        image_pixel_sha256=hashlib.sha256(b"not-black").hexdigest(),
        runtime_sha256=clip_runtime_profile_sha256(),
        values=anchor.values,
    )

    missing = score_minimum_positive_conditions(
        condition_set=conditions,
        reference_set=references,
        reference_embeddings=(anchor, indistinguishable),
        candidate_embedding=None,
    )
    unknown = score_minimum_positive_conditions(
        condition_set=conditions,
        reference_set=references,
        reference_embeddings=(anchor, indistinguishable),
        candidate_embedding=embedding("candidate", 1.0, 0.0),
    )

    assert missing.status == "missing"
    assert missing.condition_margins[0].status == "missing"
    assert unknown.status == "unknown"
    assert unknown.condition_margins[0].status == "reference_too_close"
    assert unknown.condition_margins[0].normalized_margin is None


def test_v4_rejects_wrong_runtime_and_candidate_reference_reuse() -> None:
    conditions, references = one_condition()
    reference_embeddings = (
        embedding("anchor", 1.0, 0.0),
        embedding("not-black", 0.0, 1.0),
    )
    wrong_runtime = reference_embeddings[0].model_copy(update={"runtime_sha256": "b" * 64})

    with pytest.raises(CounterfactualV4Error, match="counterfactual v4 contract"):
        score_minimum_positive_conditions(
            condition_set=conditions,
            reference_set=references,
            reference_embeddings=(wrong_runtime, reference_embeddings[1]),
            candidate_embedding=embedding("candidate", 1.0, 0.0),
        )
    with pytest.raises(CounterfactualV4Error, match="counterfactual v4 contract"):
        score_minimum_positive_conditions(
            condition_set=conditions,
            reference_set=references,
            reference_embeddings=reference_embeddings,
            candidate_embedding=reference_embeddings[0],
        )


def test_v4_profile_is_deterministic_and_never_enables_ranking() -> None:
    digest = minimum_positive_profile_sha256()

    assert digest == minimum_positive_profile_sha256()
    assert len(digest) == 64
    assert MINIMUM_POSITIVE_RANKING_ENABLED is False
