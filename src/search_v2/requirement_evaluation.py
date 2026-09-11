"""Evidence construction, adjudication, and typed product ordering."""

from __future__ import annotations

from decimal import Decimal
import hashlib
import json
import math
from typing import Annotated
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import ValidationError
from pydantic import field_validator
from pydantic import model_validator

from src.search_v2.typed_requirements import DEFAULT_ATTRIBUTE_REGISTRY
from src.search_v2.typed_requirements import AttributeDefinition
from src.search_v2.typed_requirements import AttributeKey
from src.search_v2.typed_requirements import AttributeRegistry
from src.search_v2.typed_requirements import BooleanObservedValue
from src.search_v2.typed_requirements import BooleanTarget
from src.search_v2.typed_requirements import DecimalObservedValue
from src.search_v2.typed_requirements import DecimalTarget
from src.search_v2.typed_requirements import EnumObservedValue
from src.search_v2.typed_requirements import EnumTarget
from src.search_v2.typed_requirements import EvidenceSource
from src.search_v2.typed_requirements import Identifier
from src.search_v2.typed_requirements import IntegerObservedValue
from src.search_v2.typed_requirements import IntegerTarget
from src.search_v2.typed_requirements import ObservedValue
from src.search_v2.typed_requirements import SemanticObservedValue
from src.search_v2.typed_requirements import SemanticTarget
from src.search_v2.typed_requirements import TextSetObservedValue
from src.search_v2.typed_requirements import TextSetTarget
from src.search_v2.typed_requirements import TypedRequirement
from src.search_v2.typed_requirements import TypedRequirementDraft
from src.search_v2.typed_requirements import TypedRequirementError
from src.search_v2.typed_requirements import VersionText
from src.search_v2.typed_requirements import attribute_definition
from src.search_v2.typed_requirements import attribute_registry_sha256
from src.search_v2.typed_requirements import normalize_observed_value
from src.search_v2.typed_requirements import normalize_typed_requirements
from src.search_v2.typed_requirements import typed_requirement_set_sha256


EVIDENCE_OBSERVATION_DOMAIN = b"amazon-explorer-evidence-observation-v1\x00"
MAX_EVIDENCE_PER_REQUIREMENT = 32
RATIO_DECIMALS = 6

_INVALID_EVIDENCE_MESSAGE = "Evidence inputs did not match the evidence contract"

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
EvidenceStatus = Literal["observed", "unknown"]
UnknownReason = Literal[
    "not_observed",
    "source_missing",
    "below_confidence",
    "evaluator_unavailable",
    "invalid_observation",
]
DecisionState = Literal["match", "mismatch", "unknown", "conflict"]
DecisionReason = Literal[
    "matched",
    "did_not_match",
    "no_observed_evidence",
    "highest_priority_conflict",
]
RequiredStatus = Literal["confirmed", "uncertain", "contradicted"]
ScoreValue = Annotated[float, Field(ge=0.0, le=1.0)]

_OBSERVED_VALUE_TYPES = (
    BooleanObservedValue,
    EnumObservedValue,
    IntegerObservedValue,
    DecimalObservedValue,
    TextSetObservedValue,
    SemanticObservedValue,
)


class RequirementEvaluationError(ValueError):
    """A fixed-message rejection for invalid evidence inputs."""


class StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


class EvidenceObservation(StrictFrozenContract):
    schema_version: Literal["1.0"]
    requirement_id: Identifier
    attribute_key: AttributeKey
    product_sha256: Digest
    source: EvidenceSource
    source_priority: Annotated[int, Field(ge=1, le=100)]
    status: EvidenceStatus
    observed_value: ObservedValue | None
    unknown_reason: UnknownReason | None
    registry_sha256: Digest
    evaluator_id: Identifier
    evaluator_version: VersionText
    evaluator_profile_sha256: Digest
    input_artifact_sha256: Digest

    @model_validator(mode="after")
    def validate_status(self) -> EvidenceObservation:
        if self.status == "observed" and (
            self.observed_value is None or self.unknown_reason is not None
        ):
            raise ValueError("observed evidence requires only an observed value")
        if self.status == "unknown" and (
            self.observed_value is not None or self.unknown_reason is None
        ):
            raise ValueError("unknown evidence requires only an unknown reason")
        return self


class RequirementDecision(StrictFrozenContract):
    schema_version: Literal["1.0"]
    requirement_id: Identifier
    requirement_sha256: Digest
    product_sha256: Digest
    registry_sha256: Digest
    state: DecisionState
    reason: DecisionReason
    accepted_evidence_sha256: Annotated[tuple[Digest, ...], Field(max_length=32)]
    rejected_evidence_sha256: Annotated[tuple[Digest, ...], Field(max_length=32)]

    @model_validator(mode="after")
    def validate_decision(self) -> RequirementDecision:
        accepted = self.accepted_evidence_sha256
        rejected = self.rejected_evidence_sha256
        if len(accepted) != len(set(accepted)) or len(rejected) != len(set(rejected)):
            raise ValueError("decision evidence digests must be unique")
        if set(accepted).intersection(rejected):
            raise ValueError("accepted and rejected evidence must not overlap")
        if self.state == "match" and (self.reason != "matched" or not accepted):
            raise ValueError("match decision is inconsistent")
        if self.state == "mismatch" and (self.reason != "did_not_match" or not accepted):
            raise ValueError("mismatch decision is inconsistent")
        if self.state == "unknown" and (self.reason != "no_observed_evidence" or accepted):
            raise ValueError("unknown decision is inconsistent")
        if self.state == "conflict" and (
            self.reason != "highest_priority_conflict" or len(accepted) < 2
        ):
            raise ValueError("conflict decision is inconsistent")
        return self


class TypedProductEvaluation(StrictFrozenContract):
    schema_version: Literal["1.0"]
    product_sha256: Digest
    registry_sha256: Digest
    requirement_set_sha256: Digest
    required_status: RequiredStatus
    required_match_ratio: ScoreValue
    preferred_match_ratio: ScoreValue
    evidence_coverage: ScoreValue
    decisions: Annotated[tuple[RequirementDecision, ...], Field(max_length=64)]

    @field_validator(
        "required_match_ratio",
        "preferred_match_ratio",
        "evidence_coverage",
        mode="before",
    )
    @classmethod
    def validate_float(cls, value: object) -> object:
        if type(value) is not float or not math.isfinite(value):
            raise ValueError("evaluation ratios must be finite floats")
        return value

    @model_validator(mode="after")
    def validate_bindings(self) -> TypedProductEvaluation:
        identifiers = tuple(item.requirement_id for item in self.decisions)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("evaluation decisions must have unique requirement ids")
        if any(item.product_sha256 != self.product_sha256 for item in self.decisions):
            raise ValueError("decision product binding does not match the evaluation")
        if any(item.registry_sha256 != self.registry_sha256 for item in self.decisions):
            raise ValueError("decision registry binding does not match the evaluation")
        return self


def _canonical_sha256(domain: bytes, value: BaseModel) -> str:
    canonical = json.dumps(
        value.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(domain + canonical).hexdigest()


def _validated_requirement(
    requirement: TypedRequirement,
    registry: AttributeRegistry,
) -> tuple[TypedRequirement, AttributeDefinition]:
    validated = TypedRequirement.model_validate(requirement)
    registry_digest = attribute_registry_sha256(registry)
    if validated.registry_sha256 != registry_digest:
        raise ValueError("requirement registry binding is invalid")

    draft = TypedRequirementDraft(
        requirement_id=validated.requirement_id,
        attribute_key=validated.attribute_key,
        operator=validated.operator,
        expected_value=validated.expected_value,
        strength=validated.strength,
    )
    normalized = normalize_typed_requirements((draft,), registry=registry)[0]
    if normalized != validated:
        raise ValueError("requirement is not canonical for the registry")
    return validated, attribute_definition(validated.attribute_key, registry=registry)


def _evidence_rule(definition: AttributeDefinition, source: str):
    for rule in definition.evidence_rules:
        if rule.source == source:
            return rule
    raise ValueError("evidence source is not allowed for the attribute")


def build_evidence_observation(
    requirement: TypedRequirement,
    *,
    product_sha256: str,
    source: str,
    observed_value: object | None,
    unknown_reason: str | None,
    evaluator_profile_sha256: str,
    input_artifact_sha256: str,
    registry: AttributeRegistry = DEFAULT_ATTRIBUTE_REGISTRY,
) -> EvidenceObservation:
    try:
        validated_registry = AttributeRegistry.model_validate(registry)
        validated_requirement, definition = _validated_requirement(
            requirement,
            validated_registry,
        )
        rule = _evidence_rule(definition, source)
        if (observed_value is None) == (unknown_reason is None):
            raise ValueError("evidence must contain either a value or an unknown reason")

        normalized_value = None
        status: EvidenceStatus = "unknown"
        if observed_value is not None:
            if type(observed_value) not in _OBSERVED_VALUE_TYPES:
                raise TypeError("observed value must be an exact typed value")
            normalized_value = normalize_observed_value(observed_value, definition)
            status = "observed"

        return EvidenceObservation(
            schema_version="1.0",
            requirement_id=validated_requirement.requirement_id,
            attribute_key=validated_requirement.attribute_key,
            product_sha256=product_sha256,
            source=rule.source,
            source_priority=rule.priority,
            status=status,
            observed_value=normalized_value,
            unknown_reason=unknown_reason,
            registry_sha256=attribute_registry_sha256(validated_registry),
            evaluator_id=rule.evaluator_id,
            evaluator_version=rule.evaluator_version,
            evaluator_profile_sha256=evaluator_profile_sha256,
            input_artifact_sha256=input_artifact_sha256,
        )
    except (TypedRequirementError, TypeError, ValueError, ValidationError) as exc:
        raise RequirementEvaluationError(_INVALID_EVIDENCE_MESSAGE) from exc


def evidence_observation_sha256(observation: EvidenceObservation) -> str:
    try:
        validated = EvidenceObservation.model_validate(observation)
    except ValidationError as exc:
        raise RequirementEvaluationError(_INVALID_EVIDENCE_MESSAGE) from exc
    return _canonical_sha256(EVIDENCE_OBSERVATION_DOMAIN, validated)


def _validate_observation_binding(
    observation: EvidenceObservation,
    requirement: TypedRequirement,
    definition: AttributeDefinition,
    product_sha256: str,
    registry_sha256: str,
) -> EvidenceObservation:
    validated = EvidenceObservation.model_validate(observation)
    rule = _evidence_rule(definition, validated.source)
    if (
        validated.requirement_id != requirement.requirement_id
        or validated.attribute_key != requirement.attribute_key
        or validated.product_sha256 != product_sha256
        or validated.registry_sha256 != registry_sha256
        or validated.source_priority != rule.priority
        or validated.evaluator_id != rule.evaluator_id
        or validated.evaluator_version != rule.evaluator_version
    ):
        raise ValueError("evidence binding is invalid")
    if validated.observed_value is not None:
        normalized = normalize_observed_value(validated.observed_value, definition)
        if normalized != validated.observed_value:
            raise ValueError("observed value is not canonical")
    return validated


def _observed_identity(value: ObservedValue) -> bytes:
    return json.dumps(
        value.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _compare_numeric(
    operator: str,
    observed: int | Decimal,
    minimum: int | Decimal | None,
    maximum: int | Decimal | None,
) -> bool:
    if operator == "equals":
        return observed == minimum
    if operator == "at_least":
        return minimum is not None and observed >= minimum
    if operator == "at_most":
        return maximum is not None and observed <= maximum
    if operator == "between":
        return minimum is not None and maximum is not None and minimum <= observed <= maximum
    raise ValueError("numeric operator is unsupported")


def _matches(requirement: TypedRequirement, observed: ObservedValue) -> bool:
    target = requirement.expected_value
    operator = requirement.operator
    if isinstance(target, BooleanTarget) and isinstance(observed, BooleanObservedValue):
        return operator == "equals" and observed.value is target.value
    if isinstance(target, EnumTarget) and isinstance(observed, EnumObservedValue):
        if operator == "equals":
            return observed.value == target.values[0]
        if operator in {"one_of", "compatible_with"}:
            return observed.value in target.values
    if isinstance(target, IntegerTarget) and isinstance(observed, IntegerObservedValue):
        if observed.unit != target.unit:
            raise ValueError("integer units do not match")
        return _compare_numeric(operator, observed.value, target.minimum, target.maximum)
    if isinstance(target, DecimalTarget) and isinstance(observed, DecimalObservedValue):
        if observed.unit != target.unit:
            raise ValueError("decimal units do not match")
        return _compare_numeric(operator, observed.value, target.minimum, target.maximum)
    if isinstance(target, TextSetTarget) and isinstance(observed, TextSetObservedValue):
        expected_values = set(target.values)
        observed_values = set(observed.values)
        if operator == "equals":
            return observed_values == expected_values
        if operator == "contains_all":
            return expected_values.issubset(observed_values)
        if operator in {"one_of", "compatible_with"}:
            return bool(expected_values.intersection(observed_values))
    if isinstance(target, SemanticTarget) and isinstance(observed, SemanticObservedValue):
        return operator == "similar_to" and observed.label == target.label
    raise ValueError("observed value does not match the requirement type")


def adjudicate_requirement(
    requirement: TypedRequirement,
    *,
    product_sha256: str,
    observations: tuple[EvidenceObservation, ...],
    registry: AttributeRegistry = DEFAULT_ATTRIBUTE_REGISTRY,
) -> RequirementDecision:
    try:
        validated_registry = AttributeRegistry.model_validate(registry)
        validated_requirement, definition = _validated_requirement(
            requirement,
            validated_registry,
        )
        if type(observations) is not tuple or len(observations) > MAX_EVIDENCE_PER_REQUIREMENT:
            raise TypeError("observations must be a bounded tuple")

        registry_digest = attribute_registry_sha256(validated_registry)
        validated_observations = tuple(
            _validate_observation_binding(
                observation,
                validated_requirement,
                definition,
                product_sha256,
                registry_digest,
            )
            for observation in observations
        )
        evidence_pairs = tuple(
            (evidence_observation_sha256(item), item) for item in validated_observations
        )
        evidence_digests = tuple(item[0] for item in evidence_pairs)
        if len(evidence_digests) != len(set(evidence_digests)):
            raise ValueError("duplicate evidence observations are not allowed")

        observed_pairs = tuple(pair for pair in evidence_pairs if pair[1].status == "observed")
        requirement_digest = typed_requirement_set_sha256(
            (validated_requirement,),
            registry=validated_registry,
        )
        if not observed_pairs:
            return RequirementDecision(
                schema_version="1.0",
                requirement_id=validated_requirement.requirement_id,
                requirement_sha256=requirement_digest,
                product_sha256=product_sha256,
                registry_sha256=registry_digest,
                state="unknown",
                reason="no_observed_evidence",
                accepted_evidence_sha256=(),
                rejected_evidence_sha256=tuple(sorted(evidence_digests)),
            )

        highest_priority = min(pair[1].source_priority for pair in observed_pairs)
        accepted_pairs = tuple(
            pair for pair in observed_pairs if pair[1].source_priority == highest_priority
        )
        accepted_digests = tuple(sorted(pair[0] for pair in accepted_pairs))
        rejected_digests = tuple(
            sorted(pair[0] for pair in evidence_pairs if pair[0] not in accepted_digests)
        )
        distinct_values = {
            _observed_identity(pair[1].observed_value)
            for pair in accepted_pairs
            if pair[1].observed_value is not None
        }
        if len(distinct_values) != 1:
            return RequirementDecision(
                schema_version="1.0",
                requirement_id=validated_requirement.requirement_id,
                requirement_sha256=requirement_digest,
                product_sha256=product_sha256,
                registry_sha256=registry_digest,
                state="conflict",
                reason="highest_priority_conflict",
                accepted_evidence_sha256=accepted_digests,
                rejected_evidence_sha256=rejected_digests,
            )

        selected_value = accepted_pairs[0][1].observed_value
        if selected_value is None:
            raise ValueError("observed evidence is missing its value")
        matched = _matches(validated_requirement, selected_value)
        return RequirementDecision(
            schema_version="1.0",
            requirement_id=validated_requirement.requirement_id,
            requirement_sha256=requirement_digest,
            product_sha256=product_sha256,
            registry_sha256=registry_digest,
            state="match" if matched else "mismatch",
            reason="matched" if matched else "did_not_match",
            accepted_evidence_sha256=accepted_digests,
            rejected_evidence_sha256=rejected_digests,
        )
    except (TypedRequirementError, TypeError, ValueError, ValidationError) as exc:
        raise RequirementEvaluationError(_INVALID_EVIDENCE_MESSAGE) from exc


def _weighted_ratio(
    requirements: tuple[TypedRequirement, ...],
    decisions: dict[str, RequirementDecision],
    definitions: dict[str, AttributeDefinition],
    strength: str,
) -> float:
    selected = tuple(item for item in requirements if item.strength == strength)
    denominator = sum(definitions[item.attribute_key].default_weight for item in selected)
    if denominator == 0:
        return 1.0
    numerator = sum(
        definitions[item.attribute_key].default_weight
        for item in selected
        if decisions[item.requirement_id].state == "match"
    )
    return round(numerator / denominator, RATIO_DECIMALS)


def evaluate_typed_product(
    requirements: tuple[TypedRequirement, ...],
    decisions: tuple[RequirementDecision, ...],
    *,
    product_sha256: str,
    registry: AttributeRegistry = DEFAULT_ATTRIBUTE_REGISTRY,
) -> TypedProductEvaluation:
    try:
        validated_registry = AttributeRegistry.model_validate(registry)
        if type(requirements) is not tuple or type(decisions) is not tuple:
            raise TypeError("requirements and decisions must be tuples")
        validated_requirements = tuple(
            _validated_requirement(item, validated_registry)[0] for item in requirements
        )
        validated_decisions = tuple(RequirementDecision.model_validate(item) for item in decisions)
        requirement_ids = tuple(item.requirement_id for item in validated_requirements)
        decision_ids = tuple(item.requirement_id for item in validated_decisions)
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("requirement ids must be unique")
        if len(decision_ids) != len(set(decision_ids)):
            raise ValueError("decision requirement ids must be unique")
        if set(requirement_ids) != set(decision_ids):
            raise ValueError("decisions must cover every requirement exactly once")

        registry_digest = attribute_registry_sha256(validated_registry)
        requirement_map = {item.requirement_id: item for item in validated_requirements}
        decision_map = {item.requirement_id: item for item in validated_decisions}
        for requirement_id, decision in decision_map.items():
            selected = requirement_map[requirement_id]
            if (
                decision.product_sha256 != product_sha256
                or decision.registry_sha256 != registry_digest
                or decision.requirement_sha256
                != typed_requirement_set_sha256((selected,), registry=validated_registry)
            ):
                raise ValueError("decision binding is invalid")

        ordered_decisions = tuple(
            decision_map[item.requirement_id] for item in validated_requirements
        )
        hard_decisions = tuple(
            (item, decision_map[item.requirement_id])
            for item in validated_requirements
            if item.strength in {"required", "excluded"}
        )
        contradicted = any(
            (item.strength == "required" and decision.state == "mismatch")
            or (item.strength == "excluded" and decision.state == "match")
            for item, decision in hard_decisions
        )
        uncertain = any(decision.state in {"unknown", "conflict"} for _, decision in hard_decisions)
        required_status: RequiredStatus = "confirmed"
        if contradicted:
            required_status = "contradicted"
        elif uncertain:
            required_status = "uncertain"

        definitions = {
            item.attribute_key: attribute_definition(
                item.attribute_key, registry=validated_registry
            )
            for item in validated_requirements
        }
        total_weight = sum(
            definitions[item.attribute_key].default_weight for item in validated_requirements
        )
        observed_weight = sum(
            definitions[item.attribute_key].default_weight
            for item in validated_requirements
            if decision_map[item.requirement_id].state in {"match", "mismatch"}
        )
        coverage = (
            1.0
            if total_weight == 0
            else round(
                observed_weight / total_weight,
                RATIO_DECIMALS,
            )
        )
        return TypedProductEvaluation(
            schema_version="1.0",
            product_sha256=product_sha256,
            registry_sha256=registry_digest,
            requirement_set_sha256=typed_requirement_set_sha256(
                validated_requirements,
                registry=validated_registry,
            ),
            required_status=required_status,
            required_match_ratio=_weighted_ratio(
                validated_requirements,
                decision_map,
                definitions,
                "required",
            ),
            preferred_match_ratio=_weighted_ratio(
                validated_requirements,
                decision_map,
                definitions,
                "preferred",
            ),
            evidence_coverage=coverage,
            decisions=ordered_decisions,
        )
    except (TypedRequirementError, TypeError, ValueError, ValidationError) as exc:
        raise RequirementEvaluationError(_INVALID_EVIDENCE_MESSAGE) from exc


def typed_product_sort_key(
    evaluation: TypedProductEvaluation,
    *,
    overall_score: float,
    response_index: int,
) -> tuple[int, float, float, float, int]:
    try:
        validated = TypedProductEvaluation.model_validate(evaluation)
        if type(overall_score) is not float or not math.isfinite(overall_score):
            raise TypeError("overall score must be a finite float")
        if not 0.0 <= overall_score <= 1.0:
            raise ValueError("overall score is outside the allowed range")
        if type(response_index) is not int or not 0 <= response_index < 48:
            raise ValueError("response index is outside the allowed range")
        status_order = {"confirmed": 0, "uncertain": 1, "contradicted": 2}
        return (
            status_order[validated.required_status],
            -validated.required_match_ratio,
            -validated.preferred_match_ratio,
            -overall_score,
            response_index,
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise RequirementEvaluationError(_INVALID_EVIDENCE_MESSAGE) from exc
