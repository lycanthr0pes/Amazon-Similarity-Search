"""Conservative definition selection: a model ID is a proposal, never evidence.

Only a unique, explicitly named quantity can currently be resolved automatically.
Semantic paraphrases remain unresolved until an independent binding is available.
This module does not retrieve documents or certify their authority or accuracy.
"""

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from src.search_v2.bonsai_adapter import _load_strict_json, MAX_BOUND_ARTIFACT_BYTES
from src.search_v2.dynamic_attributes import _identity
from src.search_v2.source_constraints import _source_facts


ShortText = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class _StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _Definition(_StrictInput):
    id: ShortText
    name: ShortText | None = None
    unit: ShortText | None = None
    definition: Annotated[str, StringConstraints(min_length=1, max_length=8000)] | None = None


class _Context(_StrictInput):
    source_input: Annotated[str, StringConstraints(min_length=1, max_length=8000)]
    target_quote: Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    documents: Annotated[list[_Definition], Field(max_length=64)]


@dataclass(frozen=True)
class AttributeResolution:
    status: Literal["resolved", "unresolved", "invalid"]
    proposed_attribute_id: str | None
    resolved_attribute_id: str | None
    reason: Literal[
        "explicit_unique_binding",
        "evidence_required",
        "model_abstained",
        "invalid_response_or_context",
    ]


def _selection(response: bytes, identifiers: set[str]) -> str:
    if type(response) is not bytes or not response or len(response) > MAX_BOUND_ARTIFACT_BYTES:
        raise ValueError("Invalid definition selection")
    valid, envelope = _load_strict_json(response.decode("utf-8"))
    if not valid or type(envelope) is not dict:
        raise ValueError("Invalid definition selection")
    choices = envelope.get("choices")
    if type(choices) is not list or len(choices) != 1 or type(choices[0]) is not dict:
        raise ValueError("Invalid definition selection")
    choice = choices[0]
    message = choice.get("message")
    if choice.get("finish_reason") != "stop" or type(message) is not dict:
        raise ValueError("Invalid definition selection")
    content = message.get("content")
    if type(content) is not str:
        raise ValueError("Invalid definition selection")
    valid, value = _load_strict_json(content)
    if not valid or type(value) is not dict or set(value) != {"attribute_id"}:
        raise ValueError("Invalid definition selection")
    selected = value["attribute_id"]
    if type(selected) is not str or selected not in identifiers | {"unresolved"}:
        raise ValueError("Invalid definition selection")
    return selected


def resolve_definition_response(context: dict, response: bytes) -> AttributeResolution:
    """Validate raw selection, then require source evidence independent of that choice.

    No expected label, confidence, model-authored proof, or prevalidated boolean is
    accepted. Missing evidence and conflicting definitions cannot produce an ID
    for execution; malformed responses are errors rather than successful abstention.
    """
    try:
        data = _Context.model_validate(context)
        identifiers = {document.id for document in data.documents}
        if len(identifiers) != len(data.documents) or "unresolved" in identifiers:
            raise ValueError("Invalid definition identifiers")
        selected = _selection(response, identifiers)
        if selected == "unresolved":
            return AttributeResolution("unresolved", None, None, "model_abstained")
        pending = AttributeResolution("unresolved", selected, None, "evidence_required")
        facts, uncertain = _source_facts(data.source_input)
        quote = _identity(data.target_quote)
        matching = [fact for fact in facts if fact.quote == quote]
        if uncertain or len(matching) != 1 or _identity(data.source_input).count(quote) != 1:
            return pending
        fact = matching[0]
        if fact.label is None or "unit" not in fact.target:
            return pending
        # A hidden name/unit or absent definition is incomplete context. A second
        # document with the same name/unit is a conflict even if its prose differs.
        if any(not d.name or not d.unit or not d.definition for d in data.documents):
            return pending
        compatible = [
            d.id
            for d in data.documents
            if _identity(d.name) == _identity(fact.label)
            and _identity(d.unit) == _identity(fact.target["unit"])
        ]
        if compatible != [selected]:
            return pending
        return AttributeResolution("resolved", selected, selected, "explicit_unique_binding")
    except (TypeError, ValueError, UnicodeError, ValidationError, RecursionError):
        return AttributeResolution("invalid", None, None, "invalid_response_or_context")
