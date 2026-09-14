"""Server-side product-image evaluation for the provisional counterfactual profile."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from typing import Protocol

from pydantic import ValidationError

from src.search_v2.attribute_image_ranking import AttributeImageBatch, build_attribute_image_batch
from src.search_v2.counterfactual_image import CounterfactualReferenceSet
from src.search_v2.counterfactual_image import VisualConditionSet
from src.search_v2.counterfactual_image import counterfactual_reference_set_sha256
from src.search_v2.counterfactual_image import visual_condition_set_sha256
from src.search_v2.counterfactual_v4 import score_minimum_positive_conditions
from src.search_v2.image_proxy import ProxyImage
from src.search_v2.image_similarity import ClipEmbedding
from src.search_v2.image_similarity import LocalClipImageEncoder
from src.search_v2.image_similarity import run_pinned_clip_image_encoder
from src.search_v2.siglip2 import (
    run_pinned_siglip2_image_encoder,
    score_conditions as score_siglip2_conditions,
)
from src.search_v2.product_evidence import normalized_product_candidate_sha256
from src.search_v2.product_normalization import NormalizedProductBatch
from src.search_v2.provisional_counterfactual import ProvisionalCounterfactualBatch
from src.search_v2.provisional_counterfactual import ProvisionalImageCandidateInput
from src.search_v2.provisional_counterfactual import build_provisional_counterfactual_batch
from src.search_v2.relative_image_ranking import (
    RelativeImageBatch,
    build_relative_image_batch,
    build_appearance_image_batch,
    build_siglip2_appearance_batch,
)


from src.search_v2.visual_text_scoring import Siglip2DualImageBatch, score_visual_text


MINIMUM_EVALUATION_PRODUCTS = 4
MAXIMUM_EVALUATION_PRODUCTS = 32
CLIP_EVALUATION_BATCH_SIZE = 4
_INVALID_EVALUATION_MESSAGE = "Product images did not match the counterfactual evaluation contract"


class CounterfactualProductEvaluationError(ValueError):
    """A fixed-message rejection at the server-side product-image boundary."""

    def __init__(
        self,
        message: str,
        *,
        failure_substage: Literal[
            "image_validation",
            "reference_clip",
            "candidate_preparation",
            "candidate_clip",
            "candidate_scoring",
            "calibration",
        ],
        image_request_count: int = 0,
        image_fetch_success_count: int = 0,
        reference_clip_batch_count: int = 0,
        candidate_clip_batch_count: int = 0,
    ) -> None:
        super().__init__(message)
        self.failure_substage = failure_substage
        self.image_request_count = image_request_count
        self.image_fetch_success_count = image_fetch_success_count
        self.reference_clip_batch_count = reference_clip_batch_count
        self.candidate_clip_batch_count = candidate_clip_batch_count

    def safe_metadata(self) -> dict[str, int | str]:
        return {
            "candidate_clip_batch_count": self.candidate_clip_batch_count,
            "failure_substage": self.failure_substage,
            "image_fetch_success_count": self.image_fetch_success_count,
            "image_request_count": self.image_request_count,
            "reference_clip_batch_count": self.reference_clip_batch_count,
        }


class _ClipBatchFailure(RuntimeError):
    def __init__(self, batch_count: int) -> None:
        super().__init__("CLIP batch failed")
        self.batch_count = batch_count


class ProductImageProxy(Protocol):
    def fetch_image(self, url: str) -> ProxyImage: ...


def _encode_batches(
    images: tuple[ProxyImage, ...],
    *,
    asset_root: Path,
    encoder: LocalClipImageEncoder,
    siglip2: bool = False,
) -> tuple[tuple[ClipEmbedding, ...], int]:
    encoded: list[ClipEmbedding] = []
    batch_count = 0
    batch_size = 36 if siglip2 else CLIP_EVALUATION_BATCH_SIZE
    encode = run_pinned_siglip2_image_encoder if siglip2 else run_pinned_clip_image_encoder
    for start in range(0, len(images), batch_size):
        batch_count += 1
        try:
            encoded.extend(
                encode(
                    images[start : start + batch_size],
                    asset_root=asset_root,
                    encoder=encoder,
                )
            )
        except Exception:
            raise _ClipBatchFailure(batch_count) from None
    return tuple(encoded), batch_count


def _missing_input(
    *,
    product_sha256: str,
    condition_set: VisualConditionSet,
    reference_set: CounterfactualReferenceSet,
    reference_embeddings: tuple[ClipEmbedding, ...],
    score_conditions=score_minimum_positive_conditions,
) -> ProvisionalImageCandidateInput:
    score = score_conditions(
        condition_set=condition_set,
        reference_set=reference_set,
        reference_embeddings=reference_embeddings,
        candidate_embedding=None,
    )
    return ProvisionalImageCandidateInput(
        normalized_product_sha256=product_sha256,
        candidate_image_pixel_sha256=None,
        score=score,
    )


def evaluate_counterfactual_product_images(
    *,
    product_batch: NormalizedProductBatch,
    condition_set: VisualConditionSet,
    reference_set: CounterfactualReferenceSet,
    reference_images: tuple[ProxyImage, ...],
    proxy_service: ProductImageProxy,
    asset_root: Path,
    encoder: LocalClipImageEncoder,
    score_mode: Literal[
        "calibrated", "relative", "appearance", "siglip2_appearance", "siglip2_text_image"
    ] = "calibrated",
    region_extractor=None,
) -> ProvisionalCounterfactualBatch | RelativeImageBatch | AttributeImageBatch:
    """Fetch only the first product image, score locally, and calibrate without labels."""
    try:
        products = NormalizedProductBatch.model_validate(product_batch)
        conditions = VisualConditionSet.model_validate(condition_set)
        references = CounterfactualReferenceSet.model_validate(reference_set)
        if score_mode not in {
            "calibrated",
            "relative",
            "appearance",
            "siglip2_appearance",
            "siglip2_text_image",
        }:
            raise ValueError("Invalid visual score mode")
        minimum = 1 if score_mode != "calibrated" else MINIMUM_EVALUATION_PRODUCTS
        if not (minimum <= len(products.products) <= MAXIMUM_EVALUATION_PRODUCTS):
            raise ValueError("counterfactual evaluation product count is invalid")
        if type(reference_images) is not tuple or len(reference_images) != 1 + len(
            conditions.conditions
        ):
            raise TypeError("counterfactual reference image count is invalid")
        validated_reference_images = tuple(
            ProxyImage.model_validate(image) for image in reference_images
        )
        expected_reference_digests = (
            references.desired_image_hash.image_pixel_sha256,
            *(item.image_hash.image_pixel_sha256 for item in references.counterfactuals),
        )
        if (
            references.condition_set_sha256 != visual_condition_set_sha256(conditions)
            or tuple(item.pixel_sha256 for item in validated_reference_images)
            != expected_reference_digests
            or counterfactual_reference_set_sha256(references) == ""
            or not callable(getattr(proxy_service, "fetch_image", None))
            or not isinstance(asset_root, Path)
        ):
            raise ValueError("counterfactual evaluator bindings do not match")
    except (TypeError, ValueError, ValidationError):
        raise CounterfactualProductEvaluationError(
            _INVALID_EVALUATION_MESSAGE,
            failure_substage="image_validation",
        ) from None

    siglip2 = score_mode in {"siglip2_appearance", "siglip2_text_image"}
    score_conditions = score_siglip2_conditions if siglip2 else score_minimum_positive_conditions
    try:
        reference_embeddings, reference_clip_batch_count = _encode_batches(
            validated_reference_images,
            asset_root=asset_root,
            encoder=encoder,
            siglip2=siglip2,
        )
    except _ClipBatchFailure as exc:
        raise CounterfactualProductEvaluationError(
            _INVALID_EVALUATION_MESSAGE,
            failure_substage="reference_clip",
            reference_clip_batch_count=exc.batch_count,
        ) from None

    fetched_by_product: list[tuple[str, ProxyImage | None]] = []
    seen_pixels: set[str] = set()
    image_request_count = 0
    image_fetch_success_count = 0
    try:
        for product in products.products:
            product_sha256 = normalized_product_candidate_sha256(product)
            image: ProxyImage | None = None
            if product.image_urls:
                image_request_count += 1
                try:
                    fetched = ProxyImage.model_validate(
                        proxy_service.fetch_image(product.image_urls[0])
                    )
                    image_fetch_success_count += 1
                    if score_mode != "calibrated" or fetched.pixel_sha256 not in seen_pixels:
                        image = fetched
                        seen_pixels.add(fetched.pixel_sha256)
                except Exception:
                    image = None
            fetched_by_product.append((product_sha256, image))
    except (TypeError, ValueError, ValidationError):
        raise CounterfactualProductEvaluationError(
            _INVALID_EVALUATION_MESSAGE,
            failure_substage="candidate_preparation",
            image_request_count=image_request_count,
            image_fetch_success_count=image_fetch_success_count,
            reference_clip_batch_count=reference_clip_batch_count,
        ) from None

    candidate_images = tuple(
        {
            image.pixel_sha256: image
            for _product_sha256, image in fetched_by_product
            if image is not None
        }.values()
    )
    try:
        candidate_embeddings, candidate_clip_batch_count = _encode_batches(
            candidate_images,
            asset_root=asset_root,
            encoder=encoder,
            siglip2=siglip2,
        )
    except _ClipBatchFailure as exc:
        raise CounterfactualProductEvaluationError(
            _INVALID_EVALUATION_MESSAGE,
            failure_substage="candidate_clip",
            image_request_count=image_request_count,
            image_fetch_success_count=image_fetch_success_count,
            reference_clip_batch_count=reference_clip_batch_count,
            candidate_clip_batch_count=exc.batch_count,
        ) from None

    embedding_by_pixel = {item.image_pixel_sha256: item for item in candidate_embeddings}

    candidate_inputs: list[ProvisionalImageCandidateInput] = []
    try:
        for product_sha256, image in fetched_by_product:
            if image is None:
                candidate_inputs.append(
                    _missing_input(
                        product_sha256=product_sha256,
                        condition_set=conditions,
                        reference_set=references,
                        reference_embeddings=reference_embeddings,
                        score_conditions=score_conditions,
                    )
                )
                continue
            score = score_conditions(
                condition_set=conditions,
                reference_set=references,
                reference_embeddings=reference_embeddings,
                candidate_embedding=embedding_by_pixel[image.pixel_sha256],
            )
            candidate_inputs.append(
                ProvisionalImageCandidateInput(
                    normalized_product_sha256=product_sha256,
                    candidate_image_pixel_sha256=image.pixel_sha256,
                    score=score,
                )
            )
    except (KeyError, TypeError, ValueError, ValidationError):
        raise CounterfactualProductEvaluationError(
            _INVALID_EVALUATION_MESSAGE,
            failure_substage="candidate_scoring",
            image_request_count=image_request_count,
            image_fetch_success_count=image_fetch_success_count,
            reference_clip_batch_count=reference_clip_batch_count,
            candidate_clip_batch_count=candidate_clip_batch_count,
        ) from None

    try:
        if score_mode == "siglip2_text_image":
            image_batch = build_siglip2_appearance_batch(tuple(candidate_inputs))
            text_batch = score_visual_text(
                conditions,
                fetched_by_product,
                candidate_embeddings,
                asset_root=asset_root,
                encoder=encoder,
            )
            return Siglip2DualImageBatch(
                **{name: getattr(image_batch, name) for name in type(image_batch).model_fields},
                text_batch=text_batch,
            )
        if score_mode == "siglip2_appearance":
            return build_siglip2_appearance_batch(tuple(candidate_inputs))
        if score_mode == "appearance":
            return build_appearance_image_batch(tuple(candidate_inputs))
        if score_mode == "relative":
            relative = build_relative_image_batch(tuple(candidate_inputs))
            if any(c.focus is not None and c.focus.kind == "shape" for c in conditions.conditions):
                return build_attribute_image_batch(
                    relative,
                    conditions,
                    validated_reference_images,
                    fetched_by_product,
                    region_extractor,
                )
            return relative
        return build_provisional_counterfactual_batch(tuple(candidate_inputs))
    except (TypeError, ValueError, ValidationError):
        raise CounterfactualProductEvaluationError(
            _INVALID_EVALUATION_MESSAGE,
            failure_substage="calibration",
            image_request_count=image_request_count,
            image_fetch_success_count=image_fetch_success_count,
            reference_clip_batch_count=reference_clip_batch_count,
            candidate_clip_batch_count=candidate_clip_batch_count,
        ) from None
