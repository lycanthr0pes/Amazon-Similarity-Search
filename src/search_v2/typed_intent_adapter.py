"""Convert Bonsai typed-condition candidates into trusted requirements."""

from __future__ import annotations

from decimal import Decimal
from decimal import InvalidOperation
import hashlib
import json
import re
from typing import Annotated
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import ValidationError
from pydantic import model_validator

from src.search_v2.dynamic_attributes import compile_search_registry
from src.search_v2.dynamic_attributes import numeric_identity_requires_review
from src.search_v2.dynamic_attributes import search_attribute_key
from src.search_v2.intent import BonsaiBooleanTarget
from src.search_v2.intent import BonsaiDecimalTarget
from src.search_v2.intent import BonsaiEnumTarget
from src.search_v2.intent import BonsaiIntegerTarget
from src.search_v2.intent import BonsaiSemanticTarget
from src.search_v2.intent import BonsaiTextSetTarget
from src.search_v2.intent import BonsaiTypedConditionCandidate
from src.search_v2.intent import MAX_TYPED_CONDITIONS
from src.search_v2.intent import NormalizedSearchIntent
from src.search_v2.intent import search_intent_sha256
from src.search_v2.typed_requirements import DEFAULT_ATTRIBUTE_REGISTRY
from src.search_v2.typed_requirements import AttributeRegistry
from src.search_v2.typed_requirements import BooleanTarget
from src.search_v2.typed_requirements import DecimalTarget
from src.search_v2.typed_requirements import EnumTarget
from src.search_v2.typed_requirements import IntegerTarget
from src.search_v2.typed_requirements import SemanticTarget
from src.search_v2.typed_requirements import TextSetTarget
from src.search_v2.typed_requirements import TypedRequirement
from src.search_v2.typed_requirements import TypedRequirementDraft
from src.search_v2.typed_requirements import TypedRequirementError
from src.search_v2.typed_requirements import attribute_definition
from src.search_v2.typed_requirements import attribute_registry_sha256
from src.search_v2.typed_requirements import normalize_typed_requirements
from src.search_v2.typed_requirements import typed_requirement_set_sha256


TYPED_INTENT_ADAPTER_PROFILE_DOMAIN = b"amazon-explorer-typed-intent-adapter-profile-v1\x00"
TYPED_CONDITION_CANDIDATE_SET_DOMAIN = b"amazon-explorer-typed-condition-candidate-set-v1\x00"
TYPED_REQUIREMENT_PROPOSAL_DOMAIN = b"amazon-explorer-typed-requirement-proposal-v1\x00"
MAX_TYPED_ISSUES = MAX_TYPED_CONDITIONS + 1
_INVALID_ADAPTER_MESSAGE = "Typed intent inputs did not match the adapter contract"
_REQUIREMENT_ID_PATTERN = re.compile(r"^condition-(?P<position>[0-9]{3})$")

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
IssueCode = Literal[
    "upstream_ambiguity",
    "attribute_identity_unresolved",
    "unknown_attribute",
    "invalid_condition",
    "semantic_requires_preferred",
    "duplicate_condition",
]


class TypedIntentAdapterError(ValueError):
    """A fixed-message rejection for invalid typed-intent inputs."""


class StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


class TypedIntentAdapterProfile(StrictFrozenContract):
    schema_version: Literal["1.0"]
    profile_id: Literal["bonsai-candidate-evidence-gated-v2"]
    decimal_parser_version: Literal["ascii-fixed-decimal-v1"]
    requirement_id_version: Literal["candidate-position-v1"]
    maximum_candidates: Literal[64]


TYPED_INTENT_ADAPTER_PROFILE_V1 = TypedIntentAdapterProfile(
    schema_version="1.0",
    profile_id="bonsai-candidate-evidence-gated-v2",
    decimal_parser_version="ascii-fixed-decimal-v1",
    requirement_id_version="candidate-position-v1",
    maximum_candidates=MAX_TYPED_CONDITIONS,
)


class TypedConditionIssue(StrictFrozenContract):
    code: IssueCode
    candidate_index: Annotated[int, Field(ge=0, lt=MAX_TYPED_CONDITIONS)] | None
    blocking: Literal[True]

    @model_validator(mode="after")
    def validate_source(self) -> TypedConditionIssue:
        if (self.code == "upstream_ambiguity") != (self.candidate_index is None):
            raise ValueError("issue source is inconsistent")
        return self


class TypedRequirementProposal(StrictFrozenContract):
    schema_version: Literal["1.0"]
    status: Literal["ready", "blocking"]
    intent_sha256: Digest
    candidate_set_sha256: Digest
    registry_sha256: Digest
    registry: AttributeRegistry = DEFAULT_ATTRIBUTE_REGISTRY
    adapter_profile_sha256: Digest
    requirement_set_sha256: Digest
    requirements: Annotated[
        tuple[TypedRequirement, ...],
        Field(max_length=MAX_TYPED_CONDITIONS, repr=False),
    ]
    issues: Annotated[tuple[TypedConditionIssue, ...], Field(max_length=MAX_TYPED_ISSUES)]

    @model_validator(mode="after")
    def validate_bindings(self) -> TypedRequirementProposal:
        if self.registry_sha256 != attribute_registry_sha256(self.registry):
            raise ValueError("proposal registry binding does not match its definitions")
        positions: list[int] = []
        for requirement in self.requirements:
            match = _REQUIREMENT_ID_PATTERN.fullmatch(requirement.requirement_id)
            if match is None:
                raise ValueError("requirement id is not adapter-owned")
            position = int(match.group("position"))
            if not 1 <= position <= MAX_TYPED_CONDITIONS:
                raise ValueError("requirement position is outside the candidate set")
            positions.append(position)
            if requirement.registry_sha256 != self.registry_sha256:
                raise ValueError("requirement registry binding does not match the proposal")
        if positions != sorted(positions) or len(positions) != len(set(positions)):
            raise ValueError("requirements are not in canonical candidate order")

        issue_indexes = tuple(
            -1 if item.candidate_index is None else item.candidate_index for item in self.issues
        )
        if issue_indexes != tuple(sorted(issue_indexes)) or len(issue_indexes) != len(
            set(issue_indexes)
        ):
            raise ValueError("issues are not in canonical candidate order")
        if (self.status == "blocking") != bool(self.issues):
            raise ValueError("proposal status does not match its issues")
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


def _validated_profile(profile: TypedIntentAdapterProfile) -> TypedIntentAdapterProfile:
    if type(profile) is not TypedIntentAdapterProfile:
        raise TypeError("profile must be an exact TypedIntentAdapterProfile")
    return TypedIntentAdapterProfile.model_validate(profile)


def _validated_intent(intent: NormalizedSearchIntent) -> NormalizedSearchIntent:
    if type(intent) is not NormalizedSearchIntent:
        raise TypeError("intent must be an exact NormalizedSearchIntent")
    return NormalizedSearchIntent.model_validate(intent)


def _validated_registry(registry: AttributeRegistry) -> AttributeRegistry:
    if type(registry) is not AttributeRegistry:
        raise TypeError("registry must be an exact AttributeRegistry")
    return AttributeRegistry.model_validate(registry)


def typed_intent_adapter_profile_sha256(
    profile: TypedIntentAdapterProfile = TYPED_INTENT_ADAPTER_PROFILE_V1,
) -> str:
    try:
        return _canonical_sha256(
            TYPED_INTENT_ADAPTER_PROFILE_DOMAIN,
            _validated_profile(profile),
        )
    except (TypeError, ValueError, ValidationError):
        raise TypedIntentAdapterError(_INVALID_ADAPTER_MESSAGE) from None


def _candidate_set_sha256(intent: NormalizedSearchIntent) -> str:
    return _canonical_sha256(
        TYPED_CONDITION_CANDIDATE_SET_DOMAIN,
        [item.model_dump(mode="json") for item in intent.typed_conditions],
    )


def _candidate_target(candidate: BonsaiTypedConditionCandidate):
    value = candidate.expected_value
    if type(value) is BonsaiBooleanTarget:
        return BooleanTarget(value_type="boolean", value=value.value)
    if type(value) is BonsaiEnumTarget:
        return EnumTarget(value_type="enum", values=tuple(value.values))
    if type(value) is BonsaiIntegerTarget:
        return IntegerTarget(
            value_type="integer",
            minimum=value.minimum,
            maximum=value.maximum,
            unit=value.unit,
        )
    if type(value) is BonsaiDecimalTarget:
        return DecimalTarget(
            value_type="decimal",
            minimum=None if value.minimum is None else Decimal(value.minimum),
            maximum=None if value.maximum is None else Decimal(value.maximum),
            unit=value.unit,
        )
    if type(value) is BonsaiTextSetTarget:
        return TextSetTarget(value_type="text_set", values=tuple(value.values))
    if type(value) is BonsaiSemanticTarget:
        return SemanticTarget(value_type="semantic", label=value.label)
    raise TypeError("candidate target is unsupported")


def _requirement_identity(requirement: TypedRequirement) -> str:
    payload = requirement.model_dump(mode="json", exclude={"requirement_id"})
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _issue_for_invalid_candidate(
    candidate: BonsaiTypedConditionCandidate,
    *,
    candidate_index: int,
    registry: AttributeRegistry,
) -> TypedConditionIssue:
    try:
        definition = attribute_definition(candidate.attribute_key, registry=registry)
    except TypedRequirementError:
        return TypedConditionIssue(
            code="unknown_attribute",
            candidate_index=candidate_index,
            blocking=True,
        )
    if definition.value_type == "semantic" and candidate.strength != "preferred":
        code: IssueCode = "semantic_requires_preferred"
    else:
        code = "invalid_condition"
    return TypedConditionIssue(
        code=code,
        candidate_index=candidate_index,
        blocking=True,
    )


def build_typed_requirement_proposal(
    intent: NormalizedSearchIntent,
    *,
    registry: AttributeRegistry = DEFAULT_ATTRIBUTE_REGISTRY,
    profile: TypedIntentAdapterProfile = TYPED_INTENT_ADAPTER_PROFILE_V1,
) -> TypedRequirementProposal:
    try:
        validated_intent = _validated_intent(intent)
        validated_registry = _validated_registry(registry)
        try:
            validated_registry = compile_search_registry(
                [
                    c
                    for c in validated_intent.typed_conditions
                    if not numeric_identity_requires_review(c)
                ],
                validated_registry,
            )
        except (ValueError, ValidationError):
            # Each custom candidate becomes an unknown-attribute issue below; never approve a partial schema.
            pass
        validated_profile = _validated_profile(profile)
        if len(validated_intent.typed_conditions) > validated_profile.maximum_candidates:
            raise ValueError("candidate set exceeds the adapter profile")

        issues: list[TypedConditionIssue] = []
        if validated_intent.has_blocking_ambiguity:
            issues.append(
                TypedConditionIssue(
                    code="upstream_ambiguity",
                    candidate_index=None,
                    blocking=True,
                )
            )

        requirements: list[TypedRequirement] = []
        identities: set[str] = set()
        for index, candidate in enumerate(validated_intent.typed_conditions):
            if numeric_identity_requires_review(candidate):
                issues.append(
                    TypedConditionIssue(
                        code="attribute_identity_unresolved", candidate_index=index, blocking=True
                    )
                )
                continue
            try:
                draft = TypedRequirementDraft(
                    requirement_id=f"condition-{index + 1:03d}",
                    attribute_key=search_attribute_key(candidate),
                    operator=candidate.operator,
                    expected_value=_candidate_target(candidate),
                    strength=candidate.strength,
                )
                normalized = normalize_typed_requirements(
                    (draft,),
                    registry=validated_registry,
                )[0]
            except (
                InvalidOperation,
                TypeError,
                TypedRequirementError,
                ValidationError,
                ValueError,
            ):
                issues.append(
                    _issue_for_invalid_candidate(
                        candidate,
                        candidate_index=index,
                        registry=validated_registry,
                    )
                )
                continue

            identity = _requirement_identity(normalized)
            if identity in identities:
                issues.append(
                    TypedConditionIssue(
                        code="duplicate_condition",
                        candidate_index=index,
                        blocking=True,
                    )
                )
                continue
            identities.add(identity)
            requirements.append(normalized)

        requirement_tuple = tuple(requirements)
        registry_digest = attribute_registry_sha256(validated_registry)
        return TypedRequirementProposal(
            schema_version="1.0",
            status="blocking" if issues else "ready",
            intent_sha256=search_intent_sha256(validated_intent),
            candidate_set_sha256=_candidate_set_sha256(validated_intent),
            registry_sha256=registry_digest,
            registry=validated_registry,
            adapter_profile_sha256=typed_intent_adapter_profile_sha256(validated_profile),
            requirement_set_sha256=typed_requirement_set_sha256(
                requirement_tuple,
                registry=validated_registry,
            ),
            requirements=requirement_tuple,
            issues=tuple(issues),
        )
    except TypedIntentAdapterError:
        raise
    except (
        InvalidOperation,
        TypeError,
        TypedRequirementError,
        ValidationError,
        ValueError,
    ):
        raise TypedIntentAdapterError(_INVALID_ADAPTER_MESSAGE) from None


def typed_requirement_proposal_sha256(proposal: TypedRequirementProposal) -> str:
    try:
        if type(proposal) is not TypedRequirementProposal:
            raise TypeError("proposal must be an exact TypedRequirementProposal")
        validated = TypedRequirementProposal.model_validate(proposal)
        return _canonical_sha256(TYPED_REQUIREMENT_PROPOSAL_DOMAIN, validated)
    except (TypeError, ValueError, ValidationError):
        raise TypedIntentAdapterError(_INVALID_ADAPTER_MESSAGE) from None
