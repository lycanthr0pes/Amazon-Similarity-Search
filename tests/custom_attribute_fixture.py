"""Synthetic search-local requirements for generic engine/evidence tests."""

from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from test_search_v2_typed_ranking import normalized_intent


def custom_requirement(label, target, operator="equals"):
    quote = label
    if target["value_type"] in {"integer", "decimal"}:
        unit = target["unit"]
        lower, upper = target.get("minimum"), target.get("maximum")
        quantity = {
            "equals": f"{lower}{unit}",
            "at_least": f"{lower}{unit}以上",
            "at_most": f"{upper}{unit}以下",
            "between": f"{lower}{unit}以上{upper}{unit}以下",
        }[operator]
        quote += quantity
    proposal = build_typed_requirement_proposal(
        normalized_intent(
            [
                {
                    "attribute_key": "custom",
                    "attribute_definition": {
                        "label": label,
                        "meaning": label,
                        "source_quote": quote,
                    },
                    "operator": operator,
                    "expected_value": target,
                    "strength": "required",
                }
            ]
        )
    )
    assert proposal.status == "ready"
    return proposal.requirements[0], proposal.registry
