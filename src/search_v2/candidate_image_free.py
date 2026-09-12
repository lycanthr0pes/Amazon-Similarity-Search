"""Image-free ranking and history, with no fabricated image evidence."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, model_validator
from src.search_v2.candidate_search import CandidateRanking, CandidateRankedProduct, _digest
from src.search_v2.provisional_history_repository import (
    ProvisionalHistoryWrite,
    ProvisionalHistoryProductView,
)
from src.search_v2.provisional_history_snapshot import _clean_source_text, _safe_product_url

PROFILE = "candidate-image-free-v1"
SORT = "excluded-title-conditions-image-review-v1"
PROFILE_HASH = _digest(
    {
        "profile": PROFILE,
        "sort": "excluded,title,required,preferred,review,response_index",
        "image": "not_used",
        "text": "ja-en-max-v2",
    }
)


def sort_key(candidate, source):
    from src.search_v2.candidate_completion import _observed_excluded_ratio

    text = candidate.text_score
    return (
        text.excluded_ratio if text else _observed_excluded_ratio(candidate, source),
        -candidate.lexical_score,
        -(text.required_ratio if text else candidate.evaluation.required_match_ratio),
        -(text.preferred_ratio if text else candidate.evaluation.preferred_match_ratio),
        -(candidate.product.rating if candidate.product.rating is not None else -1.0),
        candidate.product.provenance.response_index,
    )


class ImageFreeRanking(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", revalidate_instances="always"
    )
    profile_id: Literal["candidate-image-free-v1"] = PROFILE
    image_mode: Literal["off"] = "off"
    source: CandidateRanking
    products: tuple[CandidateRankedProduct, ...]

    @model_validator(mode="after")
    def validate_products(self):
        if self.products != tuple(
            sorted(self.source.products, key=lambda row: sort_key(row, self.source))
        ):
            raise ValueError("Image-free ranking does not match its source")
        return self


def complete_image_free(source):
    source = CandidateRanking.model_validate(source)
    return ImageFreeRanking(
        source=source,
        products=tuple(sorted(source.products, key=lambda row: sort_key(row, source))),
    )


def image_free_history(ranking, *, source_text, completed_at):
    ranking = ImageFreeRanking.model_validate(ranking)
    source = ranking.source
    plan = source.retrieval_plan
    source_hash, summary = _clean_source_text(source_text)
    if source_hash != plan.source_sha256:
        raise ValueError("Image-free history source changed")
    return ProvisionalHistoryWrite(
        schema_version="5.0",
        image_mode="off",
        owner_id=plan.owner_id,
        completion_key=_digest(
            {
                "profile": PROFILE_HASH,
                "ranking": _digest(ranking),
                **(
                    {"history_product_name": plan.title_comparison.product_name_ja}
                    if plan.title_comparison
                    else {}
                ),
            }
        ),
        completed_at=completed_at,
        summary=summary,
        product_name=plan.title_comparison.product_name_ja if plan.title_comparison else None,
        provisional_profile_id="image-free-v1",
        ranking_profile_id=PROFILE,
        known_holdout_accuracy=None,
        ranking_profile_sha256=PROFILE_HASH,
        sort_profile_id=SORT,
        text_profile_id="candidate-text-bilingual-v2"
        if plan.condition_terms
        else "candidate-text-v1"
        if source.profile_id == "candidate-confirmed-lexical-v4"
        else None,
        retrieval_provider="playwright" if source.product_batch.provider == "playwright" else None,
        source_typed_ranked_product_batch_sha256=_digest(source),
        condition_set_sha256=None,
        reference_set_sha256=None,
        runtime_sha256=None,
        reference_images=(),
        products=tuple(
            ProvisionalHistoryProductView(
                schema_version="5.0",
                rank=i,
                title=row.product.title,
                title_en=row.product.title_en,
                title_en_status=row.product.title_en_status,
                review_rating=row.product.rating,
                title_scores=row.title_scores,
                condition_scores=row.text_score.conditions
                if row.title_scores is not None
                else None,
                price_jpy=row.product.price_jpy,
                product_url=_safe_product_url(row.product.product_url),
                required_status=row.evaluation.required_status,
                image_component_status="not_used",
                image_score=None,
                total_score=row.lexical_score,
            )
            for i, row in enumerate(ranking.products, 1)
        ),
    )
