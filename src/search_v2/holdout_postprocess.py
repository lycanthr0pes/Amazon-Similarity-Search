"""Privacy-safe stages for projecting typed-ranking holdout attempts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from typing import NoReturn

from src.search_v2.holdout_evaluation import HoldoutCasePrediction
from src.search_v2.holdout_evaluation import build_holdout_case_prediction
from src.search_v2.intent import NormalizedSearchIntent
from src.search_v2.product_normalization import NormalizedProductBatch
from src.search_v2.query_planner import SearchQueryPlan
from src.search_v2.query_planner import build_search_query_plan
from src.search_v2.typed_intent_adapter import TypedRequirementProposal
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_ranking import TypedRankedProductBatch
from src.search_v2.typed_ranking import rank_typed_product_batch


_INVALID_POSTPROCESS_MESSAGE = "Holdout post-processing did not complete"
_FAILURE_STAGES = frozenset(
    {
        "typed_proposal_invalid",
        "query_plan_invalid",
        "typed_ranking_invalid",
        "prediction_projection_invalid",
    }
)
_FAILED = object()

HoldoutPostprocessFailureStage = Literal[
    "typed_proposal_invalid",
    "query_plan_invalid",
    "typed_ranking_invalid",
    "prediction_projection_invalid",
]


@dataclass(frozen=True, slots=True)
class HoldoutPostprocessDiagnostic:
    """A bounded failure stage that contains no runtime input or error text."""

    stage: HoldoutPostprocessFailureStage

    def __post_init__(self) -> None:
        if type(self.stage) is not str or self.stage not in _FAILURE_STAGES:
            raise ValueError("holdout post-processing stage is invalid")


class HoldoutPostprocessError(ValueError):
    """Fixed-message failure carrying only a safe post-processing stage."""

    def __init__(self, diagnostic: HoldoutPostprocessDiagnostic) -> None:
        if type(diagnostic) is not HoldoutPostprocessDiagnostic:
            raise TypeError("holdout post-processing diagnostic is invalid")
        self.diagnostic = diagnostic
        super().__init__(_INVALID_POSTPROCESS_MESSAGE)


def _raise_postprocess(stage: HoldoutPostprocessFailureStage) -> NoReturn:
    raise HoldoutPostprocessError(HoldoutPostprocessDiagnostic(stage=stage)) from None


def build_postprocess_proposal(
    intent: NormalizedSearchIntent,
) -> TypedRequirementProposal:
    """Build a trusted proposal or expose only the fixed proposal stage."""

    result: object = _FAILED
    try:
        result = build_typed_requirement_proposal(intent)
    except Exception:
        pass
    if type(result) is not TypedRequirementProposal:
        _raise_postprocess("typed_proposal_invalid")
    return result


def build_postprocess_query(
    intent: NormalizedSearchIntent,
    proposal: TypedRequirementProposal,
) -> SearchQueryPlan | None:
    """Skip query creation for a bound blocking proposal, otherwise build it."""

    result: object = _FAILED
    try:
        if type(proposal) is not TypedRequirementProposal:
            raise TypeError("proposal must be exact")
        validated = TypedRequirementProposal.model_validate(proposal)
        if validated != build_typed_requirement_proposal(intent):
            raise ValueError("proposal binding is invalid")
        if validated.status == "blocking":
            return None
        result = build_search_query_plan(intent)
    except Exception:
        pass
    if type(result) is not SearchQueryPlan:
        _raise_postprocess("query_plan_invalid")
    return result


def rank_postprocess_batch(
    intent: NormalizedSearchIntent,
    query_plan: SearchQueryPlan,
    product_batch: NormalizedProductBatch,
    proposal: TypedRequirementProposal,
) -> TypedRankedProductBatch:
    """Run typed ranking or expose only the fixed ranking stage."""

    result: object = _FAILED
    try:
        result = rank_typed_product_batch(
            intent,
            query_plan,
            product_batch,
            proposal,
        )
    except Exception:
        pass
    if type(result) is not TypedRankedProductBatch:
        _raise_postprocess("typed_ranking_invalid")
    return result


def project_postprocess_case(
    *,
    case_id: str,
    source_input_sha256: str,
    status: str,
    intent: NormalizedSearchIntent | None,
    query_plan: SearchQueryPlan | None,
    proposal: TypedRequirementProposal | None,
    ranked_batch: TypedRankedProductBatch | None,
    failure_code: str | None,
) -> HoldoutCasePrediction:
    """Project runtime artifacts or expose only the fixed projection stage."""

    result: object = _FAILED
    try:
        result = build_holdout_case_prediction(
            case_id=case_id,
            source_input_sha256=source_input_sha256,
            status=status,
            intent=intent,
            query_plan=query_plan,
            proposal=proposal,
            ranked_batch=ranked_batch,
            failure_code=failure_code,
        )
    except Exception:
        pass
    if type(result) is not HoldoutCasePrediction:
        _raise_postprocess("prediction_projection_invalid")
    return result
