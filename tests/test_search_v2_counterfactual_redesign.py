from __future__ import annotations

import hashlib
import math

import pytest

from src.search_v2.counterfactual_image import VisualConditionDraft
from src.search_v2.counterfactual_image import build_counterfactual_reference_set
from src.search_v2.counterfactual_image import build_visual_condition_set
from src.search_v2.counterfactual_image import counterfactual_score_profile_sha256
from src.search_v2.counterfactual_image import score_counterfactual_conditions
from src.search_v2.counterfactual_redesign import MULTI_REFERENCE_RANKING_ENABLED
from src.search_v2.counterfactual_redesign import CounterfactualRedesignError
from src.search_v2.counterfactual_redesign import multi_reference_score_profile_sha256
from src.search_v2.counterfactual_redesign import score_multi_reference_counterfactual_conditions
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


def test_other_condition_counterfactuals_are_positive_references() -> None:
    conditions = build_visual_condition_set(
        source_input="黒いメッシュ背もたれでヘッドレスト付きの椅子",
        drafts=(
            VisualConditionDraft(
                source_phrase="黒い",
                strength="required",
                attribute_key="appearance.color",
            ),
            VisualConditionDraft(
                source_phrase="メッシュ背もたれ",
                strength="required",
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
            image_hash("not-mesh", 0xFF00),
            image_hash("no-headrest", 0xFF0000),
        ),
    )
    reference_embeddings = (
        embedding("anchor", 1.0, 0.0, 0.0, 0.0),
        embedding("not-black", 0.0, 1.0, 0.0, 0.0),
        embedding("not-mesh", 0.0, 0.0, 1.0, 0.0),
        embedding("no-headrest", 0.0, 0.0, 0.0, 1.0),
    )

    score = score_multi_reference_counterfactual_conditions(
        condition_set=conditions,
        reference_set=references,
        reference_embeddings=reference_embeddings,
        candidate_embedding=embedding("candidate", 0.0, 0.0, 1.0, 0.0),
    )

    assert score.status == "scored"
    assert score.condition_margins[0].normalized_margin == pytest.approx(1 / 3)
    assert score.condition_margins[1].normalized_margin == pytest.approx(-1.0)
    assert score.condition_margins[2].normalized_margin == pytest.approx(1 / 3)
    assert score.qualified_for_ranking is False


def test_single_condition_is_identical_to_the_current_margin() -> None:
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
    reference_embeddings = (
        embedding("anchor", 1.0, 0.0),
        embedding("not-black", 0.0, 1.0),
    )
    candidate = embedding("candidate", 1.0, 1.0)

    current = score_counterfactual_conditions(
        condition_set=conditions,
        reference_set=references,
        reference_embeddings=reference_embeddings,
        candidate_embedding=candidate,
    )
    redesigned = score_multi_reference_counterfactual_conditions(
        condition_set=conditions,
        reference_set=references,
        reference_embeddings=reference_embeddings,
        candidate_embedding=candidate,
    )

    assert redesigned.condition_margins[0].raw_margin == pytest.approx(
        current.condition_margins[0].raw_margin
    )
    assert redesigned.condition_margins[0].reference_distance == pytest.approx(
        current.condition_margins[0].reference_distance
    )
    assert redesigned.condition_margins[0].normalized_margin == pytest.approx(
        current.condition_margins[0].normalized_margin
    )


def test_multi_reference_profile_is_distinct_deterministic_and_unqualified() -> None:
    digest = multi_reference_score_profile_sha256()

    assert digest == multi_reference_score_profile_sha256()
    assert len(digest) == 64
    assert digest != counterfactual_score_profile_sha256()
    assert MULTI_REFERENCE_RANKING_ENABLED is False


def test_missing_candidate_and_unseparated_references_do_not_produce_ranking_scores() -> None:
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
    anchor = embedding("anchor", 1.0, 0.0)
    unseparated = ClipEmbedding(
        schema_version="2.0",
        image_pixel_sha256=hashlib.sha256(b"not-black").hexdigest(),
        runtime_sha256=clip_runtime_profile_sha256(),
        values=anchor.values,
    )

    missing = score_multi_reference_counterfactual_conditions(
        condition_set=conditions,
        reference_set=references,
        reference_embeddings=(anchor, unseparated),
        candidate_embedding=None,
    )
    unknown = score_multi_reference_counterfactual_conditions(
        condition_set=conditions,
        reference_set=references,
        reference_embeddings=(anchor, unseparated),
        candidate_embedding=embedding("candidate", 1.0, 0.0),
    )

    assert missing.status == "missing"
    assert missing.condition_margins[0].status == "missing"
    assert unknown.status == "unknown"
    assert unknown.condition_margins[0].status == "reference_too_close"
    assert unknown.condition_margins[0].normalized_margin is None


def test_rejects_incomplete_references_wrong_runtime_and_candidate_reuse() -> None:
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
    embeddings = (embedding("anchor", 1.0, 0.0), embedding("not-black", 0.0, 1.0))

    with pytest.raises(CounterfactualRedesignError, match="redesign contract"):
        score_multi_reference_counterfactual_conditions(
            condition_set=conditions,
            reference_set=references,
            reference_embeddings=embeddings[:-1],
            candidate_embedding=embedding("candidate", 1.0, 0.0),
        )

    wrong_runtime = embeddings[0].model_copy(update={"runtime_sha256": "b" * 64})
    with pytest.raises(CounterfactualRedesignError, match="redesign contract"):
        score_multi_reference_counterfactual_conditions(
            condition_set=conditions,
            reference_set=references,
            reference_embeddings=(wrong_runtime, embeddings[1]),
            candidate_embedding=embedding("candidate", 1.0, 0.0),
        )

    with pytest.raises(CounterfactualRedesignError, match="redesign contract"):
        score_multi_reference_counterfactual_conditions(
            condition_set=conditions,
            reference_set=references,
            reference_embeddings=embeddings,
            candidate_embedding=embeddings[0],
        )
