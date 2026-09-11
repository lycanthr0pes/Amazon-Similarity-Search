"""Short generation wire with deterministic product and citation restoration."""

from src.search_v2.candidate_diagnostics import CandidateEvaluationError


def _tuple_schema(items):
    return (
        {
            "type": "array",
            "prefixItems": items,
            "minItems": len(items),
            "maxItems": len(items),
        }
        if items
        else {"type": "array", "maxItems": 0, "items": {"type": "array"}}
    )


def compact_schema(fields, indices):
    rows = []
    for index in indices:
        citations = [
            _tuple_schema(
                [
                    {"type": "integer", "const": ordinal},
                    {"type": "integer", "minimum": 0, "maximum": len(field.text) - 1},
                    {"type": "integer", "minimum": 1, "maximum": len(field.text)},
                ]
            )
            for ordinal, field in enumerate(fields)
            if field.product_index == index and field.text.strip()
        ]
        unknown = _tuple_schema([{"type": "null"}, _tuple_schema([])])
        if citations:
            known = _tuple_schema(
                [
                    {"type": "number", "minimum": 0, "maximum": 1},
                    {"type": "array", "minItems": 1, "maxItems": 4, "items": {"anyOf": citations}},
                ]
            )
            rows.append({"anyOf": [known, unknown]})
        else:
            rows.append(unknown)
    return {
        "type": "object",
        "properties": {"evaluations": _tuple_schema(rows)},
        "required": ["evaluations"],
        "additionalProperties": False,
    }


def expand_compact(value, fields, indices):
    rows = value["evaluations"]
    if type(rows) is not list or len(rows) != len(indices):
        raise CandidateEvaluationError("semantic_product_count", boundary="semantic_response")
    restored = []
    for index, row in zip(indices, rows, strict=True):
        if type(row) is not list or len(row) != 2:
            raise CandidateEvaluationError(
                "semantic_assessment_shape", boundary="semantic_response"
            )
        score, spans = row
        if type(spans) is not list or len(spans) > 4:
            raise CandidateEvaluationError("semantic_evidence_shape", boundary="semantic_response")
        evidence = []
        for span in spans:
            if type(span) is not list or len(span) != 3:
                raise CandidateEvaluationError("semantic_span_shape", boundary="semantic_response")
            ordinal, start, end = span
            if type(ordinal) is not int or not 0 <= ordinal < len(fields):
                raise CandidateEvaluationError(
                    "semantic_field_binding", boundary="semantic_response"
                )
            evidence.append({"field_id": fields[ordinal].field_id, "start": start, "end": end})
        restored.append({"product_index": index, "score": score, "evidence": evidence})
    return {"assessments": restored}
