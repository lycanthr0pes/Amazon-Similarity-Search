"""Turn bounded, observed product fields into registry-bound typed evidence."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from decimal import InvalidOperation
import hashlib
import json
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

from src.search_v2.dynamic_product_evidence import read_labelled_specification
from src.search_v2.product_normalization import NormalizedProductCandidate
from src.search_v2.requirement_evaluation import EvidenceObservation
from src.search_v2.requirement_evaluation import RequirementEvaluationError
from src.search_v2.requirement_evaluation import build_evidence_observation
from src.search_v2.requirement_evaluation import evidence_observation_sha256
from src.search_v2.typed_requirements import DEFAULT_ATTRIBUTE_REGISTRY
from src.search_v2.typed_requirements import AttributeDefinition
from src.search_v2.typed_requirements import AttributeRegistry
from src.search_v2.typed_requirements import DecimalObservedValue
from src.search_v2.typed_requirements import EnumObservedValue
from src.search_v2.typed_requirements import Identifier
from src.search_v2.typed_requirements import ObservedValue
from src.search_v2.typed_requirements import TypedRequirement
from src.search_v2.typed_requirements import TypedRequirementError
from src.search_v2.typed_requirements import attribute_definition
from src.search_v2.typed_requirements import attribute_registry_sha256
from src.search_v2.typed_requirements import normalize_observed_value
from src.search_v2.typed_requirements import typed_requirement_set_sha256


PRODUCT_EVIDENCE_PROFILE_DOMAIN = b"amazon-explorer-product-evidence-profile-v1\x00"
NORMALIZED_PRODUCT_CANDIDATE_DOMAIN = b"amazon-explorer-normalized-product-candidate-v1\x00"
PRODUCT_EVIDENCE_SET_DOMAIN = b"amazon-explorer-product-evidence-set-v1\x00"
STRUCTURED_ARTIFACT_DOMAIN = b"amazon-explorer-structured-product-artifact-v1\x00"
TITLE_ARTIFACT_DOMAIN = b"amazon-explorer-title-product-artifact-v1\x00"
UNAVAILABLE_ARTIFACT_DOMAIN = b"amazon-explorer-unavailable-product-artifact-v1\x00"

MAX_MATCHES_PER_SOURCE = 8
MAX_TOTAL_OBSERVATIONS = 2_048
_INVALID_EVIDENCE_MESSAGE = "Product inputs did not match the product evidence contract"

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
UnknownReason = Literal[
    "not_observed",
    "source_missing",
    "below_confidence",
    "evaluator_unavailable",
    "invalid_observation",
]

_FEATURE_ENUM_ATTRIBUTES = frozenset(
    {
        "form.shape",
        "form.orientation",
    }
)
_TITLE_ENUM_ATTRIBUTES = frozenset(
    {
        "appearance.color",
        "material.type",
        "form.shape",
        "form.orientation",
    }
)
_CLAY_COLOR_SUFFIX = re.compile(r"[\s-]+(?:soil|clay)\b")
_ATTRIBUTE_NEGATION_PREFIX = re.compile(r"(?:\bnon[\s-]+|\bnot\s+|非)$")
_ATTRIBUTE_IMITATION_SUFFIX = re.compile(
    r"(?:[\s-]+(?:like|look|style)\b|ではない|でない|以外|不使用|風|調)"
)
_DECIMAL_TEXT = r"(?<![0-9.])[0-9]{1,12}(?:\.[0-9]{1,12})?(?![0-9.])"
_WIDTH_PATTERNS = (
    re.compile(
        rf"(?:width|幅)\s*[:：=]?\s*(?P<value>{_DECIMAL_TEXT})\s*"
        r"(?P<unit>mm|millimeters?|ミリメートル)"
    ),
    re.compile(
        rf"(?P<value>{_DECIMAL_TEXT})\s*(?P<unit>mm|millimeters?|ミリメートル)"
        r"\s*(?:wide|幅)"
    ),
)


class ProductEvidenceError(ValueError):
    """A fixed-message rejection for invalid product evidence inputs."""


class StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


class ProductEvidenceAdapterProfile(StrictFrozenContract):
    schema_version: Literal["1.0"]
    profile_id: Literal["bounded-product-evidence-v4"]
    structured_parser_version: Literal["observed-structured-value-v4"]
    title_parser_version: Literal["bounded-title-exact-v3"]
    maximum_matches_per_source: Literal[8]


PRODUCT_EVIDENCE_PROFILE_V4 = ProductEvidenceAdapterProfile(
    schema_version="1.0",
    profile_id="bounded-product-evidence-v4",
    structured_parser_version="observed-structured-value-v4",
    title_parser_version="bounded-title-exact-v3",
    maximum_matches_per_source=MAX_MATCHES_PER_SOURCE,
)


class ProductEvidenceSet(StrictFrozenContract):
    schema_version: Literal["1.0"]
    product_sha256: Digest
    registry_sha256: Digest
    requirement_set_sha256: Digest
    evaluator_profile_sha256: Digest
    requirement_ids: Annotated[tuple[Identifier, ...], Field(max_length=64)]
    observations: Annotated[
        tuple[EvidenceObservation, ...],
        Field(max_length=MAX_TOTAL_OBSERVATIONS, repr=False),
    ]

    @model_validator(mode="after")
    def validate_bindings(self) -> ProductEvidenceSet:
        if len(self.requirement_ids) != len(set(self.requirement_ids)):
            raise ValueError("evidence set requirement ids must be unique")
        if any(item.requirement_id not in self.requirement_ids for item in self.observations):
            raise ValueError("evidence references an unknown requirement")
        if any(item.product_sha256 != self.product_sha256 for item in self.observations):
            raise ValueError("evidence product binding does not match the set")
        if any(item.registry_sha256 != self.registry_sha256 for item in self.observations):
            raise ValueError("evidence registry binding does not match the set")
        if any(
            item.evaluator_profile_sha256 != self.evaluator_profile_sha256
            for item in self.observations
        ):
            raise ValueError("evidence profile binding does not match the set")
        digests = tuple(evidence_observation_sha256(item) for item in self.observations)
        if len(digests) != len(set(digests)):
            raise ValueError("evidence observations must be unique")
        return self


@dataclass(frozen=True, slots=True)
class _Extraction:
    values: tuple[ObservedValue, ...]
    unknown_reason: UnknownReason | None


@dataclass(frozen=True, slots=True)
class _PhraseMatch:
    start: int
    end: int
    value: str | bool


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


def _validated_profile(profile: ProductEvidenceAdapterProfile) -> ProductEvidenceAdapterProfile:
    if type(profile) is not ProductEvidenceAdapterProfile:
        raise TypeError("profile must be an exact ProductEvidenceAdapterProfile")
    return ProductEvidenceAdapterProfile.model_validate(profile)


def _validated_product(product: NormalizedProductCandidate) -> NormalizedProductCandidate:
    if type(product) is not NormalizedProductCandidate:
        raise TypeError("product must be an exact NormalizedProductCandidate")
    return NormalizedProductCandidate.model_validate(product)


def product_evidence_profile_sha256(
    profile: ProductEvidenceAdapterProfile = PRODUCT_EVIDENCE_PROFILE_V4,
) -> str:
    try:
        return _canonical_sha256(PRODUCT_EVIDENCE_PROFILE_DOMAIN, _validated_profile(profile))
    except (TypeError, ValueError, ValidationError) as exc:
        raise ProductEvidenceError(_INVALID_EVIDENCE_MESSAGE) from exc


def normalized_product_candidate_sha256(product: NormalizedProductCandidate) -> str:
    try:
        return _canonical_sha256(NORMALIZED_PRODUCT_CANDIDATE_DOMAIN, _validated_product(product))
    except (TypeError, ValueError, ValidationError) as exc:
        raise ProductEvidenceError(_INVALID_EVIDENCE_MESSAGE) from exc


def _normalized_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        raise ValueError("product evidence text contains a control character")
    return " ".join(normalized.split())


def _observed_identity(value: ObservedValue) -> str:
    return json.dumps(
        value.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _canonical_values(values: list[ObservedValue]) -> tuple[ObservedValue, ...]:
    unique = {_observed_identity(value): value for value in values}
    return tuple(unique[key] for key in sorted(unique))


def _enum_phrase_map(definition: AttributeDefinition) -> dict[str, str]:
    phrases = {_normalized_text(value): value for value in definition.allowed_values}
    for alias in definition.value_aliases:
        phrases[_normalized_text(alias.alias)] = alias.canonical
    return phrases


def _is_ascii_word_character(value: str) -> bool:
    return value.isascii() and (value.isalnum() or value == "_")


def _is_cjk_character(value: str) -> bool:
    return (
        "\u3040" <= value <= "\u30ff"
        or "\u3400" <= value <= "\u4dbf"
        or "\u4e00" <= value <= "\u9fff"
    )


def _is_unicode_word_character(value: str) -> bool:
    return value.isalnum() or value == "_"


def _phrase_is_bounded(text: str, start: int, end: int, phrase: str) -> bool:
    before = text[start - 1] if start else ""
    after = text[end] if end < len(text) else ""
    if _is_ascii_word_character(phrase[0]) and before and _is_ascii_word_character(before):
        return False
    if _is_ascii_word_character(phrase[-1]) and after and _is_ascii_word_character(after):
        return False
    if len(phrase) == 1 and _is_cjk_character(phrase):
        if before and _is_unicode_word_character(before):
            return False
        if after and _is_unicode_word_character(after):
            return False
    return True


def _phrase_matches(
    text: str,
    phrases: tuple[tuple[str, str | bool], ...],
) -> tuple[_PhraseMatch, ...]:
    candidates: list[_PhraseMatch] = []
    for raw_phrase, value in phrases:
        phrase = _normalized_text(raw_phrase)
        start = text.find(phrase)
        while start >= 0:
            end = start + len(phrase)
            if _phrase_is_bounded(text, start, end, phrase):
                candidates.append(_PhraseMatch(start=start, end=end, value=value))
            start = text.find(phrase, start + 1)

    selected: list[_PhraseMatch] = []
    for candidate in sorted(
        candidates,
        key=lambda item: (-(item.end - item.start), item.start, item.end, str(item.value)),
    ):
        if any(
            candidate.start < existing.end and existing.start < candidate.end
            for existing in selected
        ):
            continue
        selected.append(candidate)
    return tuple(sorted(selected, key=lambda item: (item.start, item.end, str(item.value))))


def _enum_values_from_exact_features(
    definition: AttributeDefinition,
    features: tuple[str, ...],
) -> _Extraction:
    if not features:
        return _Extraction((), "source_missing")
    phrases = _enum_phrase_map(definition)
    values: list[ObservedValue] = []
    for feature in features:
        canonical = phrases.get(_normalized_text(feature))
        if canonical is None:
            continue
        values.append(EnumObservedValue(value_type="enum", value=canonical))
    if not values:
        return _Extraction((), "not_observed")
    return _Extraction(_canonical_values(values), None)


def _enum_values_from_title(
    definition: AttributeDefinition,
    title: str,
) -> _Extraction:
    phrases = tuple(_enum_phrase_map(definition).items())
    text = _normalized_text(title)
    matches = _phrase_matches(text, phrases)
    if definition.attribute_key == "appearance.color":
        matches = tuple(item for item in matches if not _CLAY_COLOR_SUFFIX.match(text[item.end :]))
    elif definition.attribute_key in {"material.type", "form.shape"}:
        matches = tuple(
            item
            for item in matches
            if not _ATTRIBUTE_NEGATION_PREFIX.search(text[: item.start])
            and not _ATTRIBUTE_IMITATION_SUFFIX.match(text[item.end :])
        )
    values = [EnumObservedValue(value_type="enum", value=str(item.value)) for item in matches]
    if not values:
        return _Extraction((), "not_observed")
    return _Extraction(_canonical_values(values), None)


def _pattern_matches(
    text: str,
    patterns: tuple[re.Pattern[str], ...],
    *,
    full: bool,
) -> tuple[re.Match[str], ...]:
    matches: list[re.Match[str]] = []
    for pattern in patterns:
        if full:
            match = pattern.fullmatch(text)
            if match is not None:
                matches.append(match)
        else:
            matches.extend(pattern.finditer(text))
    return tuple(matches)


def _width_values(texts: tuple[str, ...], *, full: bool) -> _Extraction:
    if full and not texts:
        return _Extraction((), "source_missing")
    values: list[ObservedValue] = []
    invalid = False
    for raw_text in texts:
        text = _normalized_text(raw_text)
        for match in _pattern_matches(text, _WIDTH_PATTERNS, full=full):
            try:
                unit = "mm" if match.group("unit") else ""
                values.append(
                    DecimalObservedValue(
                        value_type="decimal",
                        value=Decimal(match.group("value")),
                        unit=unit,
                    )
                )
            except (InvalidOperation, TypeError, ValueError, ValidationError):
                invalid = True
    if invalid:
        return _Extraction((), "invalid_observation")
    if not values:
        return _Extraction((), "not_observed")
    return _Extraction(_canonical_values(values), None)


def _structured_values(
    definition: AttributeDefinition,
    product: NormalizedProductCandidate,
) -> _Extraction:
    key = definition.attribute_key
    if key.startswith("search."):
        values: list[ObservedValue] = []
        try:
            for feature in product.attributes.features:
                value = read_labelled_specification(feature, definition)
                if value is not None and value not in values:
                    values.append(value)
        except (ValueError, TypedRequirementError):
            return _Extraction((), "invalid_observation")
        return _Extraction(tuple(values), None if values else "source_missing")
    if key == "appearance.color":
        if product.attributes.color is None:
            return _Extraction((), "source_missing")
        try:
            value = normalize_observed_value(
                EnumObservedValue(value_type="enum", value=product.attributes.color),
                definition,
            )
        except TypedRequirementError:
            return _Extraction((), "invalid_observation")
        return _Extraction((value,), None)
    if key == "material.type":
        if product.attributes.material is None:
            return _Extraction((), "source_missing")
        try:
            value = normalize_observed_value(
                EnumObservedValue(value_type="enum", value=product.attributes.material), definition
            )
        except TypedRequirementError:
            return _Extraction((), "invalid_observation")
        return _Extraction((value,), None)
    if key in _FEATURE_ENUM_ATTRIBUTES:
        return _enum_values_from_exact_features(definition, product.attributes.features)
    if key == "dimensions.width":
        return _width_values(product.attributes.features, full=True)
    return _Extraction((), "evaluator_unavailable")


def _title_values(
    definition: AttributeDefinition,
    product: NormalizedProductCandidate,
) -> _Extraction:
    key = definition.attribute_key
    if key in _TITLE_ENUM_ATTRIBUTES:
        return _enum_values_from_title(definition, product.title)
    if key == "dimensions.width":
        return _width_values((product.title,), full=False)
    return _Extraction((), "evaluator_unavailable")


def _extract(
    definition: AttributeDefinition,
    product: NormalizedProductCandidate,
    source: str,
) -> _Extraction:
    if source == "structured":
        return _structured_values(definition, product)
    if source == "title_exact":
        return _title_values(definition, product)
    return _Extraction((), "evaluator_unavailable")


def _artifact_sha256(product: NormalizedProductCandidate, source: str) -> str:
    if source == "structured":
        return _canonical_sha256(STRUCTURED_ARTIFACT_DOMAIN, product.attributes)
    if source == "title_exact":
        return _canonical_sha256(TITLE_ARTIFACT_DOMAIN, {"title": product.title})
    return _canonical_sha256(
        UNAVAILABLE_ARTIFACT_DOMAIN,
        {"product_sha256": normalized_product_candidate_sha256(product), "source": source},
    )


def _observation_sort_key(
    observation: EvidenceObservation,
    requirement_indexes: dict[str, int],
) -> tuple[int, int, str, int, str]:
    value_identity = (
        "" if observation.observed_value is None else _observed_identity(observation.observed_value)
    )
    return (
        requirement_indexes[observation.requirement_id],
        observation.source_priority,
        observation.source,
        0 if observation.status == "observed" else 1,
        value_identity,
    )


def build_product_evidence(
    product: NormalizedProductCandidate,
    requirements: tuple[TypedRequirement, ...],
    *,
    registry: AttributeRegistry = DEFAULT_ATTRIBUTE_REGISTRY,
    profile: ProductEvidenceAdapterProfile = PRODUCT_EVIDENCE_PROFILE_V4,
) -> ProductEvidenceSet:
    try:
        validated_product = _validated_product(product)
        validated_profile = _validated_profile(profile)
        if type(registry) is not AttributeRegistry:
            raise TypeError("registry must be an exact AttributeRegistry")
        validated_registry = AttributeRegistry.model_validate(registry)
        if type(requirements) is not tuple or any(
            type(item) is not TypedRequirement for item in requirements
        ):
            raise TypeError("requirements must contain exact TypedRequirement values")
        requirement_set_digest = typed_requirement_set_sha256(
            requirements,
            registry=validated_registry,
        )
        registry_digest = attribute_registry_sha256(validated_registry)
        product_digest = normalized_product_candidate_sha256(validated_product)
        profile_digest = product_evidence_profile_sha256(validated_profile)

        observations: list[EvidenceObservation] = []
        for requirement in requirements:
            definition = attribute_definition(
                requirement.attribute_key,
                registry=validated_registry,
            )
            for rule in sorted(
                definition.evidence_rules,
                key=lambda item: (item.priority, item.source),
            ):
                extraction = _extract(definition, validated_product, rule.source)
                if len(extraction.values) > validated_profile.maximum_matches_per_source:
                    raise ValueError("product evidence exceeds the match limit")
                artifact_digest = _artifact_sha256(validated_product, rule.source)
                if extraction.values:
                    observations.extend(
                        build_evidence_observation(
                            requirement,
                            product_sha256=product_digest,
                            source=rule.source,
                            observed_value=value,
                            unknown_reason=None,
                            evaluator_profile_sha256=profile_digest,
                            input_artifact_sha256=artifact_digest,
                            registry=validated_registry,
                        )
                        for value in extraction.values
                    )
                else:
                    observations.append(
                        build_evidence_observation(
                            requirement,
                            product_sha256=product_digest,
                            source=rule.source,
                            observed_value=None,
                            unknown_reason=extraction.unknown_reason,
                            evaluator_profile_sha256=profile_digest,
                            input_artifact_sha256=artifact_digest,
                            registry=validated_registry,
                        )
                    )

        requirement_ids = tuple(item.requirement_id for item in requirements)
        requirement_indexes = {
            requirement_id: index for index, requirement_id in enumerate(requirement_ids)
        }
        ordered_observations = tuple(
            sorted(
                observations,
                key=lambda item: _observation_sort_key(item, requirement_indexes),
            )
        )
        return ProductEvidenceSet(
            schema_version="1.0",
            product_sha256=product_digest,
            registry_sha256=registry_digest,
            requirement_set_sha256=requirement_set_digest,
            evaluator_profile_sha256=profile_digest,
            requirement_ids=requirement_ids,
            observations=ordered_observations,
        )
    except ProductEvidenceError:
        raise
    except (
        InvalidOperation,
        RequirementEvaluationError,
        TypeError,
        TypedRequirementError,
        ValidationError,
        ValueError,
    ) as exc:
        raise ProductEvidenceError(_INVALID_EVIDENCE_MESSAGE) from exc


def product_evidence_set_sha256(evidence_set: ProductEvidenceSet) -> str:
    try:
        if type(evidence_set) is not ProductEvidenceSet:
            raise TypeError("evidence set must be an exact ProductEvidenceSet")
        validated = ProductEvidenceSet.model_validate(evidence_set)
        indexes = {
            requirement_id: index for index, requirement_id in enumerate(validated.requirement_ids)
        }
        canonical_observations = tuple(
            sorted(
                validated.observations,
                key=lambda item: _observation_sort_key(item, indexes),
            )
        )
        if canonical_observations != validated.observations:
            raise ValueError("evidence observations are not in canonical order")
        return _canonical_sha256(PRODUCT_EVIDENCE_SET_DOMAIN, validated)
    except ProductEvidenceError:
        raise
    except (RequirementEvaluationError, TypeError, ValueError, ValidationError) as exc:
        raise ProductEvidenceError(_INVALID_EVIDENCE_MESSAGE) from exc
