"""Offline contracts and scores for condition-specific counterfactual images."""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Annotated
from typing import Literal
import unicodedata

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import ValidationError
from pydantic import model_validator
from pydantic import model_serializer

from src.search_v2.visual_contrast import VisualContrast
from src.search_v2.image_similarity import PHASH_DUPLICATE_MAX_DISTANCE
from src.search_v2.image_similarity import ClipEmbedding
from src.search_v2.image_similarity import ImagePerceptualHash
from src.search_v2.image_similarity import clip_runtime_profile_sha256
from src.search_v2.tokenizer import _analyze_japanese_source
from src.search_v2.typed_requirements import DEFAULT_ATTRIBUTE_REGISTRY
from src.search_v2.typed_requirements import AttributeRegistry
from src.search_v2.typed_requirements import RequirementStrength
from src.search_v2.typed_requirements import TypedRequirementError
from src.search_v2.typed_requirements import attribute_definition
from src.search_v2.typed_requirements import attribute_registry_sha256


MAX_VISUAL_CONDITIONS = 3
MAX_VISUAL_PHRASE_CHARACTERS = 32
MAX_SOURCE_CHARACTERS = 2_000
COUNTERFACTUAL_RANKING_ENABLED = False
COUNTERFACTUAL_SCORE_PROFILE_DOMAIN = b"amazon-explorer-counterfactual-score-profile-v1\x00"
VISUAL_CONDITION_SET_DOMAIN = b"amazon-explorer-visual-condition-set-v1\x00"
COUNTERFACTUAL_REFERENCE_SET_DOMAIN = b"amazon-explorer-counterfactual-reference-set-v1\x00"
MIN_REFERENCE_DISTANCE = 1e-6

_INVALID_CONTRACT_MESSAGE = "Inputs did not match the counterfactual image contract"
_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
_CONDITION_ID_PATTERN = r"^visual-condition-(?:001|002|003)$"
_ATTRIBUTE_KEY_PATTERN = r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$"
_JAPANESE_CHARACTER_PATTERN = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
_URL_PATTERN = re.compile(r"(?i)(?:[a-z][a-z0-9+.-]*://|www\.)")

Digest = Annotated[str, StringConstraints(pattern=_DIGEST_PATTERN)]
ConditionId = Annotated[str, StringConstraints(pattern=_CONDITION_ID_PATTERN)]
AttributeKey = Annotated[str, StringConstraints(pattern=_ATTRIBUTE_KEY_PATTERN)]
VisualPhrase = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_VISUAL_PHRASE_CHARACTERS),
]
AttributeName = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class CounterfactualImageError(ValueError):
    """A fixed-message rejection for invalid counterfactual image inputs."""


class _StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


class VisualFocus(_StrictFrozenContract):
    kind: Literal["shape", "color", "material", "appearance"]
    target: Annotated[
        str, StringConstraints(min_length=1, max_length=120, pattern=r"^[A-Za-z][A-Za-z0-9 ,'-]*$")
    ]
    scope: Literal["whole", "part"]
    measure: Literal["side_bulge", "side_smoothness", "aspect_ratio", "unobservable"] | None = None

    direction: Literal["higher", "lower"] | None = None

    @model_validator(mode="after")
    def validate_measure(self):
        measurable = self.measure is not None and self.measure != "unobservable"
        if measurable != (self.direction is not None):
            raise ValueError("Measurable shape conditions require an explicit direction")
        if self.measure is not None and self.kind != "shape":
            raise ValueError("Only shape conditions have geometry measurements")
        return self

    @model_serializer(mode="wrap")
    def serialize_measure(self, handler):
        result = handler(self)
        if self.measure is None:
            result.pop("measure", None)
        if self.direction is None:
            result.pop("direction", None)
        return result


class VisualConditionDraft(_StrictFrozenContract):
    source_phrase: VisualPhrase
    strength: RequirementStrength
    attribute_key: AttributeName | None = None
    focus: VisualFocus | None = None
    contrast: VisualContrast | None = None

    @model_serializer(mode="wrap")
    def serialize_focus(self, handler):
        result = handler(self)
        if self.focus is None:
            result.pop("focus", None)
        if self.contrast is None:
            result.pop("contrast", None)
        return result


class VisualCondition(_StrictFrozenContract):
    schema_version: Literal["1.0"]
    condition_id: ConditionId
    source_sha256: Digest
    source_start: Annotated[int, Field(ge=0, lt=MAX_SOURCE_CHARACTERS)]
    source_end: Annotated[int, Field(gt=0, le=MAX_SOURCE_CHARACTERS)]
    source_phrase: VisualPhrase = Field(repr=False)
    strength: RequirementStrength
    attribute_key: AttributeKey | None
    registry_sha256: Digest
    focus: VisualFocus | None = None
    contrast: VisualContrast | None = None

    @model_validator(mode="after")
    def validate_span(self) -> VisualCondition:
        if self.source_start >= self.source_end:
            raise ValueError("visual condition source span is invalid")
        if self.source_end - self.source_start != len(self.source_phrase):
            raise ValueError("visual condition source phrase does not match its span")
        return self

    @model_serializer(mode="wrap")
    def serialize_focus(self, handler):
        result = handler(self)
        if self.focus is None:
            result.pop("focus", None)
        if self.contrast is None:
            result.pop("contrast", None)
        return result


class VisualConditionSet(_StrictFrozenContract):
    schema_version: Literal["1.0"]
    source_sha256: Digest
    registry_sha256: Digest
    conditions: Annotated[
        tuple[VisualCondition, ...],
        Field(min_length=1, max_length=MAX_VISUAL_CONDITIONS, repr=False),
    ]

    @model_validator(mode="after")
    def validate_conditions(self) -> VisualConditionSet:
        expected_ids = tuple(
            f"visual-condition-{index:03d}" for index in range(1, len(self.conditions) + 1)
        )
        if tuple(item.condition_id for item in self.conditions) != expected_ids:
            raise ValueError("visual condition IDs are not canonical")
        if any(item.source_sha256 != self.source_sha256 for item in self.conditions):
            raise ValueError("visual conditions do not share one source binding")
        if any(item.registry_sha256 != self.registry_sha256 for item in self.conditions):
            raise ValueError("visual conditions do not share one registry binding")
        identities = tuple(_text_identity(item.source_phrase) for item in self.conditions)
        spans = tuple((item.source_start, item.source_end) for item in self.conditions)
        if len(identities) != len(set(identities)) or len(spans) != len(set(spans)):
            raise ValueError("visual conditions must be unique")
        return self


class CounterfactualReference(_StrictFrozenContract):
    condition_id: ConditionId
    image_hash: ImagePerceptualHash


class CounterfactualReferenceSet(_StrictFrozenContract):
    schema_version: Literal["1.0"]
    condition_set_sha256: Digest
    desired_image_hash: ImagePerceptualHash
    counterfactuals: Annotated[
        tuple[CounterfactualReference, ...],
        Field(min_length=1, max_length=MAX_VISUAL_CONDITIONS, repr=False),
    ]

    @model_validator(mode="after")
    def validate_references(self) -> CounterfactualReferenceSet:
        expected_ids = tuple(
            f"visual-condition-{index:03d}" for index in range(1, len(self.counterfactuals) + 1)
        )
        if tuple(item.condition_id for item in self.counterfactuals) != expected_ids:
            raise ValueError("counterfactual condition IDs are not canonical")
        hashes = (self.desired_image_hash, *(item.image_hash for item in self.counterfactuals))
        pixel_digests = tuple(item.image_pixel_sha256 for item in hashes)
        if len(pixel_digests) != len(set(pixel_digests)):
            raise ValueError("counterfactual images must be distinct")
        for index, current in enumerate(hashes):
            for previous in hashes[:index]:
                distance = (current.value ^ previous.value).bit_count()
                if distance <= PHASH_DUPLICATE_MAX_DISTANCE:
                    raise ValueError("counterfactual images must not be perceptual duplicates")
        return self


class CounterfactualScoreProfile(_StrictFrozenContract):
    schema_version: Literal["1.0"]
    profile_id: Literal["clip-counterfactual-margin-unqualified-v1"]
    minimum_reference_distance: Annotated[float, Field(gt=0.0, le=1.0)]
    normalized_margin_minimum: Literal[-1.0]
    normalized_margin_maximum: Literal[1.0]
    decision_thresholds_calibrated: Literal[False]
    ranking_enabled: Literal[False]


COUNTERFACTUAL_SCORE_PROFILE_V1 = CounterfactualScoreProfile(
    schema_version="1.0",
    profile_id="clip-counterfactual-margin-unqualified-v1",
    minimum_reference_distance=MIN_REFERENCE_DISTANCE,
    normalized_margin_minimum=-1.0,
    normalized_margin_maximum=1.0,
    decision_thresholds_calibrated=False,
    ranking_enabled=False,
)


class ConditionMargin(_StrictFrozenContract):
    condition_id: ConditionId
    status: Literal["scored", "missing", "reference_too_close"]
    raw_margin: Annotated[float, Field(ge=-2.0, le=2.0)] | None
    reference_distance: Annotated[float, Field(ge=0.0, le=2.0)] | None
    normalized_margin: Annotated[float, Field(ge=-1.0, le=1.0)] | None

    @model_validator(mode="after")
    def validate_status_values(self) -> ConditionMargin:
        if self.status == "missing":
            if any(
                value is not None
                for value in (self.raw_margin, self.reference_distance, self.normalized_margin)
            ):
                raise ValueError("missing condition margin must not contain scores")
            return self
        if self.raw_margin is None or self.reference_distance is None:
            raise ValueError("condition margin is incomplete")
        if (self.status == "scored") != (self.normalized_margin is not None):
            raise ValueError("condition margin status does not match its normalized score")
        return self


class CounterfactualImageScore(_StrictFrozenContract):
    schema_version: Literal["1.0"]
    status: Literal["scored", "missing", "unknown"]
    condition_set_sha256: Digest
    reference_set_sha256: Digest
    score_profile_sha256: Digest
    runtime_sha256: Digest
    candidate_image_pixel_sha256: Digest | None
    condition_margins: Annotated[
        tuple[ConditionMargin, ...],
        Field(min_length=1, max_length=MAX_VISUAL_CONDITIONS, repr=False),
    ]
    qualified_for_ranking: Literal[False]

    @model_validator(mode="after")
    def validate_status(self) -> CounterfactualImageScore:
        margin_statuses = {item.status for item in self.condition_margins}
        if self.status == "missing":
            if self.candidate_image_pixel_sha256 is not None or margin_statuses != {"missing"}:
                raise ValueError("missing counterfactual score is inconsistent")
        elif self.status == "scored":
            if self.candidate_image_pixel_sha256 is None or margin_statuses != {"scored"}:
                raise ValueError("scored counterfactual result is inconsistent")
        else:
            if (
                self.candidate_image_pixel_sha256 is None
                or "reference_too_close" not in margin_statuses
                or not margin_statuses.issubset({"scored", "reference_too_close"})
            ):
                raise ValueError("unknown counterfactual result is inconsistent")
        return self


def _canonical_sha256(domain: bytes, value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(domain + canonical).hexdigest()


def _text_identity(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _normalize_source(value: str) -> str:
    if type(value) is not str:
        raise TypeError("source must be a string")
    normalized = unicodedata.normalize("NFKC", value).casefold()
    if not normalized or len(normalized) > MAX_SOURCE_CHARACTERS:
        raise ValueError("source length is invalid")
    if any(
        unicodedata.category(character).startswith("C") and not character.isspace()
        for character in normalized
    ):
        raise ValueError("source contains a forbidden control character")
    return normalized


def _normalize_phrase(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    if not normalized or len(normalized) > MAX_VISUAL_PHRASE_CHARACTERS:
        raise ValueError("visual phrase length is invalid")
    if any(character in "\r\n" for character in normalized):
        raise ValueError("visual phrase contains a newline")
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        raise ValueError("visual phrase contains a forbidden control character")
    if _URL_PATTERN.search(normalized):
        raise ValueError("visual phrase contains a URL")
    return normalized


def _japanese_source_span(source_input: str, phrase: str) -> tuple[int, int, str] | None:
    source = _analyze_japanese_source(source_input)
    for start_index, start in enumerate(source.morphemes):
        for end in source.morphemes[start_index:]:
            surface = source.text[start.begin : end.end]
            identity = _text_identity(surface)
            if identity == phrase:
                return start.begin, end.end, surface
            if start is end and len(phrase) == 1 and identity in {f"{phrase}い", f"{phrase}色"}:
                return start.begin, end.end, surface
            if len(identity) > len(phrase) + 1:
                break
    return None


def _ascii_source_span(source: str, phrase: str) -> tuple[int, int, str] | None:
    pattern = re.compile(rf"(?<![a-z0-9_]){re.escape(phrase)}(?![a-z0-9_])")
    match = pattern.search(source)
    if match is None:
        return None
    return match.start(), match.end(), source[match.start() : match.end()]


def _source_span(source_input: str, normalized_source: str, phrase: str) -> tuple[int, int, str]:
    if _JAPANESE_CHARACTER_PATTERN.search(phrase):
        result = _japanese_source_span(source_input, phrase)
    else:
        result = _ascii_source_span(normalized_source, phrase)
    if result is None:
        raise ValueError("visual phrase is not source grounded")
    return result


def build_visual_condition_set(
    *,
    source_input: str,
    drafts: tuple[VisualConditionDraft, ...],
    registry: AttributeRegistry = DEFAULT_ATTRIBUTE_REGISTRY,
) -> VisualConditionSet:
    try:
        normalized_source = _normalize_source(source_input)
        validated_registry = AttributeRegistry.model_validate(registry)
        if type(drafts) is not tuple or not 1 <= len(drafts) <= MAX_VISUAL_CONDITIONS:
            raise TypeError("visual condition drafts must be a bounded tuple")
        if any(type(item) is not VisualConditionDraft for item in drafts):
            raise TypeError("visual condition drafts must use the exact draft type")

        source_digest = hashlib.sha256(normalized_source.encode("utf-8")).hexdigest()
        registry_digest = attribute_registry_sha256(validated_registry)
        conditions: list[VisualCondition] = []
        for index, draft_value in enumerate(drafts, start=1):
            current = VisualConditionDraft.model_validate(draft_value)
            phrase = _normalize_phrase(current.source_phrase)
            start, end, source_phrase = _source_span(source_input, normalized_source, phrase)
            attribute_key: str | None = None
            if current.attribute_key is not None:
                definition = attribute_definition(
                    current.attribute_key, registry=validated_registry
                )
                if not definition.visual_prompt_allowed:
                    raise ValueError("attribute does not allow visual prompts")
                attribute_key = definition.attribute_key
            conditions.append(
                VisualCondition(
                    schema_version="1.0",
                    condition_id=f"visual-condition-{index:03d}",
                    source_sha256=source_digest,
                    source_start=start,
                    source_end=end,
                    source_phrase=source_phrase,
                    strength=current.strength,
                    attribute_key=attribute_key,
                    registry_sha256=registry_digest,
                    focus=current.focus,
                    contrast=current.contrast,
                )
            )
        return VisualConditionSet(
            schema_version="1.0",
            source_sha256=source_digest,
            registry_sha256=registry_digest,
            conditions=tuple(conditions),
        )
    except CounterfactualImageError:
        raise
    except (TypeError, ValueError, ValidationError, TypedRequirementError) as exc:
        raise CounterfactualImageError(_INVALID_CONTRACT_MESSAGE) from exc


def visual_condition_set_sha256(condition_set: VisualConditionSet) -> str:
    try:
        validated = VisualConditionSet.model_validate(condition_set)
        return _canonical_sha256(VISUAL_CONDITION_SET_DOMAIN, validated)
    except (TypeError, ValueError, ValidationError) as exc:
        raise CounterfactualImageError(_INVALID_CONTRACT_MESSAGE) from exc


def build_counterfactual_reference_set(
    *,
    condition_set: VisualConditionSet,
    desired_image_hash: ImagePerceptualHash,
    counterfactual_image_hashes: tuple[ImagePerceptualHash, ...],
) -> CounterfactualReferenceSet:
    try:
        conditions = VisualConditionSet.model_validate(condition_set)
        desired = ImagePerceptualHash.model_validate(desired_image_hash)
        if (
            type(counterfactual_image_hashes) is not tuple
            or len(counterfactual_image_hashes) != len(conditions.conditions)
            or any(type(item) is not ImagePerceptualHash for item in counterfactual_image_hashes)
        ):
            raise TypeError("counterfactual image hashes do not match the conditions")
        counterfactuals = tuple(
            CounterfactualReference(
                condition_id=condition.condition_id,
                image_hash=ImagePerceptualHash.model_validate(image_hash),
            )
            for condition, image_hash in zip(
                conditions.conditions,
                counterfactual_image_hashes,
                strict=True,
            )
        )
        return CounterfactualReferenceSet(
            schema_version="1.0",
            condition_set_sha256=visual_condition_set_sha256(conditions),
            desired_image_hash=desired,
            counterfactuals=counterfactuals,
        )
    except CounterfactualImageError:
        raise
    except (TypeError, ValueError, ValidationError) as exc:
        raise CounterfactualImageError(_INVALID_CONTRACT_MESSAGE) from exc


def counterfactual_reference_set_sha256(reference_set: CounterfactualReferenceSet) -> str:
    try:
        validated = CounterfactualReferenceSet.model_validate(reference_set)
        return _canonical_sha256(COUNTERFACTUAL_REFERENCE_SET_DOMAIN, validated)
    except (TypeError, ValueError, ValidationError) as exc:
        raise CounterfactualImageError(_INVALID_CONTRACT_MESSAGE) from exc


def counterfactual_score_profile_sha256(
    profile: CounterfactualScoreProfile = COUNTERFACTUAL_SCORE_PROFILE_V1,
) -> str:
    try:
        validated = CounterfactualScoreProfile.model_validate(profile)
        return _canonical_sha256(COUNTERFACTUAL_SCORE_PROFILE_DOMAIN, validated)
    except (TypeError, ValueError, ValidationError) as exc:
        raise CounterfactualImageError(_INVALID_CONTRACT_MESSAGE) from exc


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


def score_counterfactual_conditions(
    *,
    condition_set: VisualConditionSet,
    reference_set: CounterfactualReferenceSet,
    reference_embeddings: tuple[ClipEmbedding, ...],
    candidate_embedding: ClipEmbedding | None,
    profile: CounterfactualScoreProfile = COUNTERFACTUAL_SCORE_PROFILE_V1,
) -> CounterfactualImageScore:
    try:
        conditions = VisualConditionSet.model_validate(condition_set)
        references = CounterfactualReferenceSet.model_validate(reference_set)
        score_profile = CounterfactualScoreProfile.model_validate(profile)
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
        profile_digest = counterfactual_score_profile_sha256(score_profile)
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

        anchor = embeddings[0]
        anchor_cosine = _bounded_cosine(candidate.values, anchor.values)
        margins: list[ConditionMargin] = []
        for condition, counterfactual in zip(
            conditions.conditions,
            embeddings[1:],
            strict=True,
        ):
            counterfactual_cosine = _bounded_cosine(candidate.values, counterfactual.values)
            raw_margin = anchor_cosine - counterfactual_cosine
            reference_distance = 1.0 - _bounded_cosine(
                anchor.values,
                counterfactual.values,
            )
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
            normalized_margin = min(1.0, max(-1.0, raw_margin / reference_distance))
            margins.append(
                ConditionMargin(
                    condition_id=condition.condition_id,
                    status="scored",
                    raw_margin=raw_margin,
                    reference_distance=reference_distance,
                    normalized_margin=normalized_margin,
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
    except CounterfactualImageError:
        raise
    except (TypeError, ValueError, ValidationError) as exc:
        raise CounterfactualImageError(_INVALID_CONTRACT_MESSAGE) from exc
