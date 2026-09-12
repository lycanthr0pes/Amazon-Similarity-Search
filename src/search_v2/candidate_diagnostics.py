"""Allowlisted failure codes; no source, provider body or exception text."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class CandidateFailureDiagnostic(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", revalidate_instances="always"
    )
    schema_version: Literal["1.0"] = "1.0"
    code: Literal[
        "request_build",
        "transport",
        "http_status",
        "http_response",
        "response_size",
        "envelope_json",
        "envelope_shape",
        "finish_reason",
        "content_type",
        "content_json",
        "payload_shape",
        "needs_clarification",
        "status_value",
        "conditions_shape",
        "condition_count",
        "draft_shape",
        "draft_validation",
        "condition_binding",
        "contrast_proposal",
        "clause_scope",
        "condition_strength",
        "product_scope",
        "empty_conditions",
        "query_build",
        "plan_limits",
        "semantic_response_size",
        "semantic_envelope_json",
        "semantic_envelope_shape",
        "semantic_finish_reason",
        "semantic_content_type",
        "semantic_content_json",
        "semantic_payload_shape",
        "semantic_product_count",
        "semantic_assessment_shape",
        "semantic_product_index",
        "semantic_score",
        "semantic_evidence_shape",
        "semantic_span_shape",
        "semantic_field_binding",
        "semantic_field_owner",
        "semantic_span_range",
        "semantic_span_duplicate",
        "semantic_empty_quote",
        "ranking_requirements",
        "semantic_request",
        "semantic_transport",
        "ranking_product_evaluation",
        "ranking_contract",
        "candidate_ranking",
        "visual_evaluation",
        "reference_quality",
        "history_snapshot",
        "history_save",
        "unexpected",
    ]


class CandidatePreparationError(ValueError):
    def __init__(self, code, *, visual_extraction=False, product_review=None):
        super().__init__(
            "Candidate visual extraction failed"
            if visual_extraction
            else "Candidate preparation failed; see the fixed diagnostic code"
        )
        self.diagnostic = CandidateFailureDiagnostic(code=code)
        # Explicit caller review only; safe diagnostics never serialize source text.
        self.product_review = product_review


class CandidateEvaluationError(ValueError):
    def __init__(self, code, *, boundary="evaluation"):
        messages = {
            "evaluation": "Candidate evaluation failed",
            "semantic_response": "Invalid Bonsai semantic response",
            "completion": "Candidate completion failed",
            "history": "Candidate history save failed",
        }
        super().__init__(messages[boundary])
        self.diagnostic = CandidateFailureDiagnostic(code=code)


def candidate_failure_diagnostic(error):
    """Revalidate even typed exceptions before crossing the log boundary."""
    from src.search_v2.bulge_reference_quality import BulgeReferenceError

    if type(error) is BulgeReferenceError:
        return CandidateFailureDiagnostic(code="reference_quality")
    if type(error) in (CandidatePreparationError, CandidateEvaluationError):
        try:
            return CandidateFailureDiagnostic.model_validate(error.diagnostic)
        except (AttributeError, TypeError, ValueError):
            pass  # Invalid injected metadata must never reach an artifact.
    return CandidateFailureDiagnostic(code="unexpected")
