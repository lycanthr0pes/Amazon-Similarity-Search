"""Offline multi-reference scores for condition-specific counterfactual images."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Annotated
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationError

from src.search_v2.counterfactual_image import ConditionMargin
from src.search_v2.counterfactual_image import CounterfactualImageScore
from src.search_v2.counterfactual_image import CounterfactualReferenceSet
from src.search_v2.counterfactual_image import VisualConditionSet
from src.search_v2.counterfactual_image import counterfactual_reference_set_sha256
from src.search_v2.counterfactual_image import visual_condition_set_sha256
from src.search_v2.image_similarity import ClipEmbedding
from src.search_v2.image_similarity import clip_runtime_profile_sha256


MULTI_REFERENCE_RANKING_ENABLED = False
MULTI_REFERENCE_SCORE_PROFILE_DOMAIN = (
    b"amazon-explorer-counterfactual-multi-reference-score-profile-v1\x00"
)
MINIMUM_REFERENCE_DISTANCE = 1e-6
_INVALID_CONTRACT_MESSAGE = "Inputs did not match the counterfactual redesign contract"


class CounterfactualRedesignError(ValueError):
    """A fixed-message rejection for invalid redesigned scoring inputs."""


class _StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


class MultiReferenceScoreProfile(_StrictFrozenContract):
    schema_version: Literal["1.0"]
    profile_id: Literal["clip-counterfactual-mean-positive-margin-unqualified-v2"]
    positive_reference_mode: Literal["anchor_and_other_counterfactuals"]
    minimum_reference_distance: Annotated[float, Field(gt=0.0, le=1.0)]
    normalized_margin_minimum: Literal[-1.0]
    normalized_margin_maximum: Literal[1.0]
    decision_thresholds_calibrated: Literal[False]
    ranking_enabled: Literal[False]


MULTI_REFERENCE_SCORE_PROFILE_V2 = MultiReferenceScoreProfile(
    schema_version="1.0",
    profile_id="clip-counterfactual-mean-positive-margin-unqualified-v2",
    positive_reference_mode="anchor_and_other_counterfactuals",
    minimum_reference_distance=MINIMUM_REFERENCE_DISTANCE,
    normalized_margin_minimum=-1.0,
    normalized_margin_maximum=1.0,
    decision_thresholds_calibrated=False,
    ranking_enabled=False,
)


def multi_reference_score_profile_sha256(
    profile: MultiReferenceScoreProfile = MULTI_REFERENCE_SCORE_PROFILE_V2,
) -> str:
    """Return the stable identity of the strict redesigned score profile."""
    try:
        validated = MultiReferenceScoreProfile.model_validate(profile)
        payload = json.dumps(
            validated.model_dump(mode="json"),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(MULTI_REFERENCE_SCORE_PROFILE_DOMAIN + payload).hexdigest()
    except (TypeError, ValueError, ValidationError) as exc:
        raise CounterfactualRedesignError(_INVALID_CONTRACT_MESSAGE) from exc


def _bounded_cosine(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    value = math.fsum(left * right for left, right in zip(first, second, strict=True))
    return min(1.0, max(-1.0, value))


def _missing_margins(conditions: VisualConditionSet) -> tuple[ConditionMargin, ...]:
    return tuple(
        ConditionMargin(
            condition_id=condition.condition_id,
            status="missing",
            raw_margin=None,
            reference_distance=None,
            normalized_margin=None,
        )
        for condition in conditions.conditions
    )


def score_multi_reference_counterfactual_conditions(
    *,
    condition_set: VisualConditionSet,
    reference_set: CounterfactualReferenceSet,
    reference_embeddings: tuple[ClipEmbedding, ...],
    candidate_embedding: ClipEmbedding | None,
    profile: MultiReferenceScoreProfile = MULTI_REFERENCE_SCORE_PROFILE_V2,
) -> CounterfactualImageScore:
    """Score each condition against its negative and all compatible positives."""
    try:
        conditions = VisualConditionSet.model_validate(condition_set)
        references = CounterfactualReferenceSet.model_validate(reference_set)
        score_profile = MultiReferenceScoreProfile.model_validate(profile)
        condition_digest = visual_condition_set_sha256(conditions)
        if references.condition_set_sha256 != condition_digest:
            raise ValueError("reference set does not match the condition set")
        if type(reference_embeddings) is not tuple or len(reference_embeddings) != 1 + len(
            conditions.conditions
        ):
            raise TypeError("reference embeddings do not match the condition set")
        embeddings = tuple(ClipEmbedding.model_validate(item) for item in reference_embeddings)
        expected_pixel_digests = (
            references.desired_image_hash.image_pixel_sha256,
            *(item.image_hash.image_pixel_sha256 for item in references.counterfactuals),
        )
        if tuple(item.image_pixel_sha256 for item in embeddings) != expected_pixel_digests:
            raise ValueError("reference embedding images do not match the reference set")
        approved_runtime = clip_runtime_profile_sha256()
        if {item.runtime_sha256 for item in embeddings} != {approved_runtime}:
            raise ValueError("reference embedding runtime is not approved")

        reference_digest = counterfactual_reference_set_sha256(references)
        profile_digest = multi_reference_score_profile_sha256(score_profile)
        if candidate_embedding is None:
            return CounterfactualImageScore(
                schema_version="1.0",
                status="missing",
                condition_set_sha256=condition_digest,
                reference_set_sha256=reference_digest,
                score_profile_sha256=profile_digest,
                runtime_sha256=approved_runtime,
                candidate_image_pixel_sha256=None,
                condition_margins=_missing_margins(conditions),
                qualified_for_ranking=False,
            )

        candidate = ClipEmbedding.model_validate(candidate_embedding)
        if candidate.runtime_sha256 != approved_runtime:
            raise ValueError("candidate embedding runtime is not approved")
        if candidate.image_pixel_sha256 in expected_pixel_digests:
            raise ValueError("candidate image must be independent from the references")

        margins: list[ConditionMargin] = []
        for condition_index, condition in enumerate(conditions.conditions):
            negative_index = condition_index + 1
            negative = embeddings[negative_index]
            positives = tuple(
                embedding
                for reference_index, embedding in enumerate(embeddings)
                if reference_index != negative_index
            )
            positive_cosine = math.fsum(
                _bounded_cosine(candidate.values, positive.values) for positive in positives
            ) / len(positives)
            negative_cosine = _bounded_cosine(candidate.values, negative.values)
            raw_margin = positive_cosine - negative_cosine
            reference_distance = math.fsum(
                1.0 - _bounded_cosine(positive.values, negative.values) for positive in positives
            ) / len(positives)
            if reference_distance < score_profile.minimum_reference_distance:
                margins.append(
                    ConditionMargin(
                        condition_id=condition.condition_id,
                        status="reference_too_close",
                        raw_margin=raw_margin,
                        reference_distance=reference_distance,
                        normalized_margin=None,
                    )
                )
                continue
            margins.append(
                ConditionMargin(
                    condition_id=condition.condition_id,
                    status="scored",
                    raw_margin=raw_margin,
                    reference_distance=reference_distance,
                    normalized_margin=min(1.0, max(-1.0, raw_margin / reference_distance)),
                )
            )

        status = "scored" if all(item.status == "scored" for item in margins) else "unknown"
        return CounterfactualImageScore(
            schema_version="1.0",
            status=status,
            condition_set_sha256=condition_digest,
            reference_set_sha256=reference_digest,
            score_profile_sha256=profile_digest,
            runtime_sha256=approved_runtime,
            candidate_image_pixel_sha256=candidate.image_pixel_sha256,
            condition_margins=tuple(margins),
            qualified_for_ranking=False,
        )
    except CounterfactualRedesignError:
        raise
    except (TypeError, ValueError, ValidationError) as exc:
        raise CounterfactualRedesignError(_INVALID_CONTRACT_MESSAGE) from exc
