from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.search_v2.requirement_evaluation import EvidenceObservation
from src.search_v2.requirement_evaluation import RequirementEvaluationError
from src.search_v2.requirement_evaluation import adjudicate_requirement
from src.search_v2.requirement_evaluation import build_evidence_observation
from src.search_v2.requirement_evaluation import evaluate_typed_product
from src.search_v2.requirement_evaluation import evidence_observation_sha256
from src.search_v2.requirement_evaluation import typed_product_sort_key
from src.search_v2.typed_requirements import BooleanObservedValue
from src.search_v2.typed_requirements import DecimalObservedValue
from src.search_v2.typed_requirements import EnumObservedValue
from src.search_v2.typed_requirements import IntegerObservedValue
from src.search_v2.typed_requirements import TextSetObservedValue
from src.search_v2.typed_requirements import TypedRequirement
from src.search_v2.typed_requirements import TypedRequirementDraft
from src.search_v2.typed_requirements import normalize_typed_requirements


PRODUCT_SHA256 = "a" * 64
OTHER_PRODUCT_SHA256 = "b" * 64
PROFILE_SHA256 = "c" * 64
ARTIFACT_SHA256 = "d" * 64


def requirement(**overrides: object) -> TypedRequirement:
    payload: dict[str, object] = {
        "requirement_id": "requirement-1",
        "attribute_key": "form.shape",
        "operator": "equals",
        "expected_value": {"value_type": "enum", "values": ("round",)},
        "strength": "required",
    }
    payload.update(overrides)
    draft = TypedRequirementDraft.model_validate(payload)
    return normalize_typed_requirements((draft,))[0]


def observation(
    selected_requirement: TypedRequirement,
    *,
    source: str = "structured",
    observed_value: object | None = None,
    unknown_reason: str | None = None,
    product_sha256: str = PRODUCT_SHA256,
    input_artifact_sha256: str = ARTIFACT_SHA256,
):
    return build_evidence_observation(
        selected_requirement,
        product_sha256=product_sha256,
        source=source,
        observed_value=observed_value,
        unknown_reason=unknown_reason,
        evaluator_profile_sha256=PROFILE_SHA256,
        input_artifact_sha256=input_artifact_sha256,
    )


def decision_for(
    selected_requirement: TypedRequirement,
    observed_value: object | None,
    *,
    source: str = "structured",
    unknown_reason: str | None = None,
    product_sha256: str = PRODUCT_SHA256,
):
    evidence = observation(
        selected_requirement,
        source=source,
        observed_value=observed_value,
        unknown_reason=unknown_reason,
        product_sha256=product_sha256,
    )
    return adjudicate_requirement(
        selected_requirement,
        product_sha256=product_sha256,
        observations=(evidence,),
    )


def test_evidence_uses_registry_metadata_and_normalizes_observed_alias() -> None:
    selected = requirement()

    evidence = observation(
        selected,
        observed_value=EnumObservedValue(value_type="enum", value="丸形"),
    )

    assert evidence.source == "structured"
    assert evidence.source_priority == 10
    assert evidence.evaluator_id == "observed-structured-value"
    assert evidence.evaluator_version == "1"
    assert evidence.observed_value.value == "round"
    assert len(evidence_observation_sha256(evidence)) == 64


def test_registry_rejects_visual_evidence_for_connection_type() -> None:
    with pytest.raises(RequirementEvaluationError, match="evidence contract"):
        observation(
            requirement(),
            source="visual_feature",
            observed_value=EnumObservedValue(value_type="enum", value="round"),
        )


def test_unknown_observation_carries_no_value_and_is_not_a_mismatch() -> None:
    selected = requirement()
    missing = observation(
        selected,
        source="title_exact",
        unknown_reason="not_observed",
    )

    assert missing.status == "unknown"
    assert missing.observed_value is None
    assert (
        adjudicate_requirement(
            selected,
            product_sha256=PRODUCT_SHA256,
            observations=(missing,),
        ).state
        == "unknown"
    )


def test_no_evidence_is_unknown_instead_of_mismatch() -> None:
    result = adjudicate_requirement(
        requirement(),
        product_sha256=PRODUCT_SHA256,
        observations=(),
    )

    assert result.state == "unknown"
    assert result.reason == "no_observed_evidence"


def test_higher_priority_structured_value_wins_over_title_value() -> None:
    selected = requirement()
    structured = observation(
        selected,
        observed_value=EnumObservedValue(value_type="enum", value="round"),
    )
    title = observation(
        selected,
        source="title_exact",
        observed_value=EnumObservedValue(value_type="enum", value="rectangular"),
    )

    result = adjudicate_requirement(
        selected,
        product_sha256=PRODUCT_SHA256,
        observations=(title, structured),
    )

    assert result.state == "match"
    assert result.accepted_evidence_sha256 == (evidence_observation_sha256(structured),)
    assert result.rejected_evidence_sha256 == (evidence_observation_sha256(title),)


def test_same_priority_conflicting_values_fail_closed() -> None:
    selected = requirement()
    round = observation(
        selected,
        observed_value=EnumObservedValue(value_type="enum", value="round"),
        input_artifact_sha256="1" * 64,
    )
    rectangular = build_evidence_observation(
        selected,
        product_sha256=PRODUCT_SHA256,
        source="structured",
        observed_value=EnumObservedValue(value_type="enum", value="rectangular"),
        unknown_reason=None,
        evaluator_profile_sha256=PROFILE_SHA256,
        input_artifact_sha256="2" * 64,
    )

    result = adjudicate_requirement(
        selected,
        product_sha256=PRODUCT_SHA256,
        observations=(rectangular, round),
    )

    assert result.state == "conflict"
    assert result.reason == "highest_priority_conflict"
    assert len(result.accepted_evidence_sha256) == 2


@pytest.mark.parametrize(
    ("requirement_overrides", "observed_payload", "expected_state"),
    [
        (
            {
                "attribute_key": "storage.compartment_count",
                "operator": "at_least",
                "expected_value": {
                    "value_type": "integer",
                    "minimum": 2,
                    "maximum": None,
                    "unit": "count",
                },
            },
            {"value_type": "integer", "value": 3, "unit": "count"},
            "match",
        ),
        (
            {
                "attribute_key": "storage.compartment_count",
                "operator": "between",
                "expected_value": {
                    "value_type": "integer",
                    "minimum": 2,
                    "maximum": 4,
                    "unit": "count",
                },
            },
            {"value_type": "integer", "value": 5, "unit": "count"},
            "mismatch",
        ),
        (
            {
                "attribute_key": "dimensions.width",
                "operator": "at_most",
                "expected_value": {
                    "value_type": "decimal",
                    "minimum": None,
                    "maximum": Decimal("120.0"),
                    "unit": "mm",
                },
            },
            {
                "value_type": "decimal",
                "value": Decimal("119.5"),
                "unit": "mm",
            },
            "match",
        ),
        (
            {
                "attribute_key": "compatibility.models",
                "operator": "contains_all",
                "expected_value": {
                    "value_type": "text_set",
                    "values": ("Model A", "Model B"),
                },
            },
            {
                "value_type": "text_set",
                "values": ("model b", "Model A", "Model C"),
            },
            "match",
        ),
        (
            {
                "attribute_key": "power.rechargeable",
                "expected_value": {"value_type": "boolean", "value": True},
            },
            {"value_type": "boolean", "value": False},
            "mismatch",
        ),
    ],
)
def test_adjudicates_type_specific_operators(
    requirement_overrides: dict[str, object],
    observed_payload: dict[str, object],
    expected_state: str,
) -> None:
    observed_types = {
        "boolean": BooleanObservedValue,
        "decimal": DecimalObservedValue,
        "integer": IntegerObservedValue,
        "text_set": TextSetObservedValue,
    }
    from custom_attribute_fixture import custom_requirement
    from src.search_v2.typed_requirements import DEFAULT_ATTRIBUTE_REGISTRY

    if requirement_overrides["attribute_key"] == "dimensions.width":
        selected, registry = requirement(**requirement_overrides), DEFAULT_ATTRIBUTE_REGISTRY
    else:
        payload = dict(requirement_overrides["expected_value"])
        if "values" in payload:
            payload["values"] = list(payload["values"])
        selected, registry = custom_requirement(
            "比較仕様", payload, requirement_overrides.get("operator", "equals")
        )
    observed_type = observed_types[str(observed_payload["value_type"])]
    observed = observed_type.model_validate(observed_payload)

    evidence = build_evidence_observation(
        selected,
        product_sha256=PRODUCT_SHA256,
        source="structured",
        observed_value=observed,
        unknown_reason=None,
        evaluator_profile_sha256=PROFILE_SHA256,
        input_artifact_sha256=ARTIFACT_SHA256,
        registry=registry,
    )
    assert (
        adjudicate_requirement(
            selected, product_sha256=PRODUCT_SHA256, observations=(evidence,), registry=registry
        ).state
        == expected_state
    )


def test_tampered_evaluator_binding_is_rejected() -> None:
    selected = requirement()
    valid = observation(
        selected,
        observed_value=EnumObservedValue(value_type="enum", value="round"),
    )
    tampered = valid.model_copy(update={"evaluator_id": "untrusted-evaluator"})

    with pytest.raises(RequirementEvaluationError, match="evidence contract"):
        adjudicate_requirement(
            selected,
            product_sha256=PRODUCT_SHA256,
            observations=(tampered,),
        )


def test_evidence_model_rejects_non_namespaced_attribute_key() -> None:
    selected = requirement()
    valid = observation(
        selected,
        observed_value=EnumObservedValue(value_type="enum", value="round"),
    )
    tampered = valid.model_copy(update={"attribute_key": "not-namespaced"})

    with pytest.raises(ValidationError):
        EvidenceObservation.model_validate(tampered)


def test_required_state_distinguishes_confirmed_uncertain_and_contradicted() -> None:
    required = requirement()
    excluded = requirement(
        requirement_id="requirement-2",
        attribute_key="appearance.color",
        expected_value={"value_type": "enum", "values": ("red",)},
        strength="excluded",
    )
    requirements = (required, excluded)

    confirmed = evaluate_typed_product(
        requirements,
        (
            decision_for(
                required,
                EnumObservedValue(value_type="enum", value="round"),
            ),
            decision_for(
                excluded,
                EnumObservedValue(value_type="enum", value="black"),
            ),
        ),
        product_sha256=PRODUCT_SHA256,
    )
    uncertain = evaluate_typed_product(
        requirements,
        (
            decision_for(required, None, unknown_reason="not_observed"),
            decision_for(
                excluded,
                EnumObservedValue(value_type="enum", value="black"),
            ),
        ),
        product_sha256=PRODUCT_SHA256,
    )
    contradicted = evaluate_typed_product(
        requirements,
        (
            decision_for(
                required,
                EnumObservedValue(value_type="enum", value="rectangular"),
            ),
            decision_for(
                excluded,
                EnumObservedValue(value_type="enum", value="black"),
            ),
        ),
        product_sha256=PRODUCT_SHA256,
    )

    assert confirmed.required_status == "confirmed"
    assert uncertain.required_status == "uncertain"
    assert contradicted.required_status == "contradicted"


def test_unknown_remains_in_the_fixed_preferred_denominator() -> None:
    first = requirement(
        strength="preferred",
    )
    second = requirement(
        requirement_id="requirement-2",
        attribute_key="appearance.color",
        expected_value={"value_type": "enum", "values": ("black",)},
        strength="preferred",
    )

    evaluated = evaluate_typed_product(
        (first, second),
        (
            decision_for(
                first,
                EnumObservedValue(value_type="enum", value="round"),
            ),
            decision_for(second, None, unknown_reason="not_observed"),
        ),
        product_sha256=PRODUCT_SHA256,
    )

    assert evaluated.preferred_match_ratio == 0.5
    assert evaluated.evidence_coverage == 0.5


def test_required_status_precedes_overall_score_in_stable_sort_key() -> None:
    selected = requirement()
    confirmed = evaluate_typed_product(
        (selected,),
        (
            decision_for(
                selected,
                EnumObservedValue(value_type="enum", value="round"),
            ),
        ),
        product_sha256=PRODUCT_SHA256,
    )
    contradicted_decision = decision_for(
        selected,
        EnumObservedValue(value_type="enum", value="rectangular"),
        product_sha256=OTHER_PRODUCT_SHA256,
    )
    contradicted = evaluate_typed_product(
        (selected,),
        (contradicted_decision,),
        product_sha256=OTHER_PRODUCT_SHA256,
    )

    confirmed_key = typed_product_sort_key(
        confirmed,
        overall_score=0.01,
        response_index=10,
    )
    contradicted_key = typed_product_sort_key(
        contradicted,
        overall_score=1.0,
        response_index=0,
    )

    assert confirmed_key < contradicted_key
    assert typed_product_sort_key(
        confirmed,
        overall_score=0.01,
        response_index=10,
    ) == typed_product_sort_key(
        confirmed,
        overall_score=0.01,
        response_index=10,
    )
