"""Backend composition for approved provisional counterfactual product ranking."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from src.search_v2.counterfactual_image import VisualConditionSet
from src.search_v2.counterfactual_image import visual_condition_set_sha256
from src.search_v2.counterfactual_product_evaluator import ProductImageProxy
from src.search_v2.counterfactual_product_evaluator import CounterfactualProductEvaluationError
from src.search_v2.counterfactual_product_evaluator import (
    evaluate_counterfactual_product_images,
)
from src.search_v2.counterfactual_reference_approval import ApprovedCounterfactualReferences
from src.search_v2.image_similarity import LocalClipImageEncoder
from src.search_v2.product_normalization import NormalizedProductBatch
from src.search_v2.product_normalization import normalized_product_batch_sha256
from src.search_v2.provisional_typed_ranking import ProvisionalTypedRankedProductBatch
from src.search_v2.provisional_typed_ranking import rank_provisional_typed_product_batch
from src.search_v2.typed_ranking import TypedRankedProductBatch


_INVALID_BACKEND_MESSAGE = "Inputs did not match the provisional backend contract"


class ProvisionalBackendError(ValueError):
    """A fixed-message rejection at the composed provisional backend boundary."""

    def __init__(
        self,
        message: str,
        *,
        failure_substage: Literal[
            "backend_validation",
            "image_validation",
            "reference_clip",
            "candidate_preparation",
            "candidate_clip",
            "candidate_scoring",
            "calibration",
            "ranking_v5",
        ],
        image_request_count: int | None = None,
        image_fetch_success_count: int | None = None,
        reference_clip_batch_count: int | None = None,
        candidate_clip_batch_count: int | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_substage = failure_substage
        self.image_request_count = image_request_count
        self.image_fetch_success_count = image_fetch_success_count
        self.reference_clip_batch_count = reference_clip_batch_count
        self.candidate_clip_batch_count = candidate_clip_batch_count

    def safe_metadata(self) -> dict[str, int | str | None]:
        return {
            "candidate_clip_batch_count": self.candidate_clip_batch_count,
            "failure_substage": self.failure_substage,
            "image_fetch_success_count": self.image_fetch_success_count,
            "image_request_count": self.image_request_count,
            "reference_clip_batch_count": self.reference_clip_batch_count,
        }


def complete_provisional_product_ranking(
    *,
    source_typed_ranking: TypedRankedProductBatch,
    product_batch: NormalizedProductBatch,
    condition_set: VisualConditionSet,
    approved_references: ApprovedCounterfactualReferences,
    proxy_service: ProductImageProxy,
    asset_root: Path,
    encoder: LocalClipImageEncoder,
) -> ProvisionalTypedRankedProductBatch:
    """Fetch product images, run fixed local CLIP, calibrate, and produce ranking v5."""
    try:
        source = TypedRankedProductBatch.model_validate(source_typed_ranking)
        products = NormalizedProductBatch.model_validate(product_batch)
        conditions = VisualConditionSet.model_validate(condition_set)
        approved = ApprovedCounterfactualReferences.model_validate(approved_references)
        if (
            source.normalized_product_batch_sha256 != normalized_product_batch_sha256(products)
            or approved.condition_set_sha256 != visual_condition_set_sha256(conditions)
            or approved.reference_set.condition_set_sha256 != approved.condition_set_sha256
        ):
            raise ValueError("provisional backend bindings do not match")
    except (TypeError, ValueError, ValidationError):
        raise ProvisionalBackendError(
            _INVALID_BACKEND_MESSAGE,
            failure_substage="backend_validation",
        ) from None

    try:
        image_batch = evaluate_counterfactual_product_images(
            product_batch=products,
            condition_set=conditions,
            reference_set=approved.reference_set,
            reference_images=approved.reference_images,
            proxy_service=proxy_service,
            asset_root=asset_root,
            encoder=encoder,
        )
    except CounterfactualProductEvaluationError as exc:
        diagnostic = exc.safe_metadata()
        raise ProvisionalBackendError(
            _INVALID_BACKEND_MESSAGE,
            failure_substage=exc.failure_substage,
            image_request_count=diagnostic["image_request_count"],
            image_fetch_success_count=diagnostic["image_fetch_success_count"],
            reference_clip_batch_count=diagnostic["reference_clip_batch_count"],
            candidate_clip_batch_count=diagnostic["candidate_clip_batch_count"],
        ) from None

    try:
        return rank_provisional_typed_product_batch(source, image_batch)
    except (TypeError, ValueError, ValidationError):
        candidate_image_count = sum(
            item.candidate_image_pixel_sha256 is not None for item in image_batch.candidates
        )
        raise ProvisionalBackendError(
            _INVALID_BACKEND_MESSAGE,
            failure_substage="ranking_v5",
            image_request_count=sum(bool(item.image_urls) for item in products.products),
            image_fetch_success_count=None,
            reference_clip_batch_count=1,
            candidate_clip_batch_count=(candidate_image_count + 3) // 4,
        ) from None
