"""Deterministic condition/title rankings plus approved visual evidence and history."""

from dataclasses import dataclass
import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator, model_serializer

from src.search_v2.attribute_image_ranking import (
    AttributeImageBatch,
    AttributeImageComponent,
    PROFILE_SHA256 as ATTRIBUTE_IMAGE_SHA256,
    FEATURE_PROFILE_SHA256 as FEATURE_IMAGE_SHA256,
)
from src.search_v2.candidate_search import CandidateRanking, CandidateRankedProduct, _digest
from src.search_v2.candidate_image_free import ImageFreeRanking
from src.search_v2.counterfactual_image import (
    counterfactual_reference_set_sha256,
    visual_condition_set_sha256,
)
from src.search_v2.counterfactual_product_evaluator import evaluate_counterfactual_product_images
from src.search_v2.counterfactual_reference_approval import ApprovedCounterfactualReferences
from src.search_v2.product_evidence import normalized_product_candidate_sha256
from src.search_v2.provisional_counterfactual import (
    ProvisionalCounterfactualBatch,
    ProvisionalImageComponent,
)
from src.search_v2.provisional_history_repository import (
    ProvisionalHistoryDetail,
    ProvisionalHistoryProductView,
    ProvisionalHistoryReferenceImageWrite,
    ProvisionalHistoryWrite,
)
from src.search_v2.provisional_history_snapshot import _clean_source_text, _png, _safe_product_url
from src.search_v2.candidate_text import TEXT_PROFILE_ID, TEXT_PROFILE_SHA256, candidate_sort_key
from src.search_v2.candidate_bilingual import (
    PROFILE_ID as BILINGUAL_PROFILE_ID,
    PROFILE_SHA256 as BILINGUAL_PROFILE_SHA256,
)
from src.search_v2.relative_image_ranking import (
    AppearanceImageBatch,
    Siglip2AppearanceImageBatch,
    SIGLIP2_APPEARANCE_SHA256,
    APPEARANCE_PROFILE_SHA256,
    RelativeImageBatch,
    RelativeImageComponent,
)


from src.search_v2.visual_text_scoring import (
    Siglip2DualImageBatch,
    VisualTextComponent,
    condition_texts,
    SORT_PROFILE as TEXT_IMAGE_SORT_PROFILE,
    RANKING_PROFILE as DUAL_PROFILE,
)


PROFILE_ID = "candidate-lexical-clip-v3"
IMAGE_WEIGHT = 0.5
LEGACY_IMAGE_WEIGHT = 0.2
SORT_PROFILE_ID = "excluded-title-conditions-image-review-v1"
PROFILE_SHA256 = _digest(
    {
        "profile": PROFILE_ID,
        "image_weight": LEGACY_IMAGE_WEIGHT,
        "missing_image": "lexical_only",
        "lexical": "sudachi-original-bilingual-title-v2",
        "image": "relative-image-v1",
        "required_conditions": "first",
    }
)


ATTRIBUTE_PROFILE_ID = "candidate-attribute-image-v1"
ATTRIBUTE_PROFILE_SHA256 = _digest(
    {
        "profile": ATTRIBUTE_PROFILE_ID,
        "image_weight": LEGACY_IMAGE_WEIGHT,
        "image": ATTRIBUTE_IMAGE_SHA256,
        "visual_availability": "observed-first-within-qualification",
        "required_conditions": "first",
        "missing_image": "lexical_only",
        "lexical": "sudachi-original-bilingual-title-v2",
    }
)


FEATURE_PROFILE_ID = "candidate-attribute-image-v2"
FEATURE_PROFILE_SHA256 = _digest(
    {"profile": FEATURE_PROFILE_ID, "base": ATTRIBUTE_PROFILE_SHA256, "image": FEATURE_IMAGE_SHA256}
)


APPEARANCE_PROFILE_ID = "candidate-appearance-v1"
APPEARANCE_RANKING_SHA256 = _digest(
    {
        "profile": APPEARANCE_PROFILE_ID,
        "base": PROFILE_SHA256,
        "image": APPEARANCE_PROFILE_SHA256,
        "evidence_scope": "whole_image_similarity",
    }
)


SIGLIP2_PROFILE_ID = "candidate-siglip2-appearance-v1"
SIGLIP2_RANKING_SHA256 = _digest(
    {
        "profile": SIGLIP2_PROFILE_ID,
        "base": PROFILE_SHA256,
        "image": SIGLIP2_APPEARANCE_SHA256,
        "evidence_scope": "whole_image_similarity",
    }
)


LEGACY_PROFILE_SHA256 = _digest(
    {
        "profile": "candidate-lexical-clip-v2",
        "image_weight": LEGACY_IMAGE_WEIGHT,
        "missing_image": "lexical_only",
        "lexical": "sudachi-title-token-coverage-v1",
        "required_conditions": "first",
    }
)


def _total(candidate, image, image_weight=None):
    lexical = candidate.lexical_score
    weight = LEGACY_IMAGE_WEIGHT if image_weight is None else image_weight
    return (
        lexical
        if image.image_score is None
        else (1 - weight) * lexical + weight * image.image_score
    )


class CandidateVisualProduct(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", revalidate_instances="always"
    )
    candidate: CandidateRankedProduct = Field(repr=False)
    image: ProvisionalImageComponent | RelativeImageComponent | AttributeImageComponent
    visual_text: VisualTextComponent | None = None

    @property
    def visual_text_score(self):
        return self.visual_text.score if self.visual_text is not None else None

    total_score: float = Field(ge=0.0, le=1.0)
    image_weight: Literal[0.5] | None = None

    @model_serializer(mode="wrap")
    def serialize_compatible(self, handler):
        data = handler(self)
        if self.visual_text is None:
            data.pop("visual_text", None)
        if self.image_weight is None:
            data.pop("image_weight", None)
        return data

    @model_validator(mode="after")
    def validate_score(self):
        if self.image.normalized_product_sha256 != normalized_product_candidate_sha256(
            self.candidate.product
        ) or self.total_score != _total(self.candidate, self.image, self.image_weight):
            raise ValueError("Candidate visual score does not match its product")
        return self


def _sort_key(row):
    key = candidate_sort_key(row.candidate, row.total_score)

    if isinstance(row.image, AttributeImageComponent):
        return (*key[:3], row.image.image_score is None, *key[3:])
    return key


def _observed_excluded_ratio(candidate, source):
    excluded = [r for r in source.requirements if r.strength == "excluded"]
    weights = {d.attribute_key: d.default_weight for d in source.registry.definitions}
    decisions = {d.requirement_id: d.state for d in candidate.evaluation.decisions}
    total = sum(weights[r.attribute_key] for r in excluded)
    return (
        round(
            sum(
                weights[r.attribute_key] for r in excluded if decisions[r.requirement_id] == "match"
            )
            / total,
            6,
        )
        if total
        else 0.0
    )


def _title_image_sort_key(row, source):
    candidate = row.candidate
    text = candidate.text_score
    image = row.image.image_score
    return (
        -candidate.lexical_score,
        -(image if image is not None else -1.0),
        text.excluded_ratio if text else _observed_excluded_ratio(candidate, source),
        -(text.required_ratio if text else candidate.evaluation.required_match_ratio),
        -(text.preferred_ratio if text else candidate.evaluation.preferred_match_ratio),
        candidate.product.provenance.response_index,
    )


def _priority_sort_key(row, source):
    candidate = row.candidate
    text = candidate.text_score
    image = row.image.image_score
    rating = candidate.product.rating
    visual_text = getattr(row, "visual_text_score", None)
    return (
        text.excluded_ratio if text else _observed_excluded_ratio(candidate, source),
        -candidate.lexical_score,
        -(text.required_ratio if text else candidate.evaluation.required_match_ratio),
        -(text.preferred_ratio if text else candidate.evaluation.preferred_match_ratio),
        -(visual_text if visual_text is not None else -1.0),
        -(image if image is not None else -1.0),
        -(rating if rating is not None else -1.0),
        candidate.product.provenance.response_index,
    )


class CandidateVisualRanking(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", revalidate_instances="always"
    )
    profile_id: Literal[
        "candidate-lexical-clip-v2",
        "candidate-lexical-clip-v3",
        "candidate-attribute-image-v1",
        "candidate-attribute-image-v2",
        "candidate-appearance-v1",
        "candidate-siglip2-appearance-v1",
        "candidate-siglip2-dual-v2",
    ] = PROFILE_ID
    source: CandidateRanking = Field(repr=False)
    image_batch: (
        Siglip2DualImageBatch
        | Siglip2AppearanceImageBatch
        | AppearanceImageBatch
        | ProvisionalCounterfactualBatch
        | RelativeImageBatch
        | AttributeImageBatch
    ) = Field(repr=False)
    products: tuple[CandidateVisualProduct, ...] = Field(repr=False)
    approval_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    visual_evaluation_status: Literal["evaluated"] = "evaluated"
    text_profile_id: Literal["candidate-text-v1", "candidate-text-bilingual-v2"] | None = None
    image_weight: Literal[0.5] | None = None
    sort_profile_id: (
        Literal[
            "title-image-conditions-v1",
            "excluded-title-conditions-image-review-v1",
            "excluded-title-conditions-text-image-review-v2",
        ]
        | None
    ) = None

    @model_serializer(mode="wrap")
    def serialize_compatible(self, handler):
        data = handler(self)
        if self.text_profile_id is None:
            data.pop("text_profile_id", None)
        if self.image_weight is None:
            data.pop("image_weight", None)
        if self.sort_profile_id is None:
            data.pop("sort_profile_id", None)
        return data

    @model_validator(mode="after")
    def validate_bindings(self):
        source = self.source
        dual = self.profile_id == DUAL_PROFILE
        if dual != isinstance(self.image_batch, Siglip2DualImageBatch) or dual != (
            self.sort_profile_id == TEXT_IMAGE_SORT_PROFILE
        ):
            raise ValueError("Candidate visual text profile mismatch")
        if any((p.visual_text is not None) != dual for p in self.products):
            raise ValueError("Candidate visual text evidence is missing or unexpected")
        if dual:
            text_rows = {
                c.normalized_product_sha256: c for c in self.image_batch.text_batch.candidates
            }
            conditions = source.retrieval_plan.visual_conditions
            expected = tuple(
                (c.condition_id, hashlib.sha256(t.encode()).hexdigest())
                for c, t in zip(conditions.conditions, condition_texts(conditions), strict=True)
            )
            for row in self.products:
                if row.visual_text != text_rows.get(row.image.normalized_product_sha256):
                    raise ValueError("Candidate visual text evidence changed")
                if (
                    row.visual_text.candidate_image_pixel_sha256 is not None
                    and tuple((c.condition_id, c.text_sha256) for c in row.visual_text.conditions)
                    != expected
                ):
                    raise ValueError("Candidate visual descriptions changed")
        if self.sort_profile_id is not None and self.image_weight != IMAGE_WEIGHT:
            raise ValueError("Candidate sort profile requires current score weighting")
        if any(row.image_weight != self.image_weight for row in self.products):
            raise ValueError("Candidate image weight is inconsistent")
        if (self.text_profile_id is not None) != (
            source.profile_id
            in {"candidate-confirmed-lexical-v4", "candidate-confirmed-lexical-v5"}
        ):
            raise ValueError("Candidate visual text profile is inconsistent")
        if self.text_profile_id and self.text_profile_id != (
            BILINGUAL_PROFILE_ID if source.retrieval_plan.condition_terms else TEXT_PROFILE_ID
        ):
            raise ValueError("Candidate visual language profile is inconsistent")
        if (self.profile_id in {SIGLIP2_PROFILE_ID, DUAL_PROFILE}) != isinstance(
            self.image_batch, Siglip2AppearanceImageBatch
        ):
            raise ValueError("Candidate SigLIP profile does not match its image model")
        if (self.profile_id == APPEARANCE_PROFILE_ID) != isinstance(
            self.image_batch, AppearanceImageBatch
        ):
            raise ValueError("Candidate appearance scope does not match its ranking method")
        relative = self.profile_id != "candidate-lexical-clip-v2"
        attribute = self.profile_id in {ATTRIBUTE_PROFILE_ID, FEATURE_PROFILE_ID}
        if relative != (
            source.profile_id
            in {
                "candidate-confirmed-lexical-v3",
                "candidate-confirmed-lexical-v4",
                "candidate-confirmed-lexical-v5",
            }
        ):
            raise ValueError("Candidate text profile does not match its ranking method")
        batch_type = (
            AttributeImageBatch
            if attribute
            else RelativeImageBatch
            if relative
            else ProvisionalCounterfactualBatch
        )
        component_type = (
            AttributeImageComponent
            if attribute
            else RelativeImageComponent
            if relative
            else ProvisionalImageComponent
        )
        if not isinstance(self.image_batch, batch_type) or any(
            not isinstance(p.image, component_type) for p in self.products
        ):
            raise ValueError("Candidate image profile does not match the scoring method")
        if source.retrieval_plan_sha256 != _digest(source.retrieval_plan):
            raise ValueError("Candidate result plan binding is invalid")
        conditions = source.retrieval_plan.visual_conditions
        if (
            conditions is None
            or self.image_batch.condition_set_sha256 != visual_condition_set_sha256(conditions)
        ):
            raise ValueError("Candidate visual conditions changed")
        if attribute:
            if (self.profile_id == FEATURE_PROFILE_ID) != (
                self.image_batch.profile_id == "attribute-image-v2"
            ):
                raise ValueError("Candidate geometry profile changed")
            targets = tuple(
                (
                    c.condition_id,
                    hashlib.sha256(c.focus.target.encode()).hexdigest(),
                    c.focus.measure,
                    c.focus.direction,
                )
                for c in conditions.conditions
                if c.focus is not None and c.focus.kind == "shape"
            )
            if targets != tuple(
                (c.condition_id, c.target_sha256, c.measure, c.direction)
                for c in self.image_batch.shape_targets
            ):
                raise ValueError("Candidate shape targets changed")
        if (
            len(self.products) != len(source.products)
            or len(self.image_batch.candidates) != len(source.products)
            or sorted(
                self.products,
                key=lambda row: (
                    _priority_sort_key(row, source)
                    if self.sort_profile_id in {SORT_PROFILE_ID, TEXT_IMAGE_SORT_PROFILE}
                    else _title_image_sort_key(row, source)
                    if self.sort_profile_id == "title-image-conditions-v1"
                    else _sort_key(row)
                ),
            )
            != list(self.products)
        ):
            raise ValueError("Candidate visual ordering or count is invalid")
        original = {normalized_product_candidate_sha256(p.product): p for p in source.products}
        images = {p.normalized_product_sha256: p for p in self.image_batch.candidates}
        if (
            len(original) != len(self.products)
            or len(images) != len(self.products)
            or {p.image.normalized_product_sha256 for p in self.products} != set(original)
        ):
            raise ValueError("Candidate visual products are not a complete set")
        for row in self.products:
            key = row.image.normalized_product_sha256
            if row.candidate != original[key] or row.image != images.get(key):
                raise ValueError("Candidate visual evidence changed")
        return self


@dataclass(frozen=True, repr=False)
class CandidateCompletion:
    ranking: CandidateVisualRanking | ImageFreeRanking
    history: ProvisionalHistoryDetail


def complete_candidate_ranking(
    source,
    approved,
    *,
    proxy_service,
    asset_root,
    encoder,
    region_extractor=None,
    image_score_mode="siglip2_text_image",
):
    if image_score_mode not in {
        "siglip2_text_image",
        "siglip2_appearance",
        "appearance",
        "relative",
    }:
        raise ValueError("Invalid candidate image score mode")
    source = CandidateRanking.model_validate(source)
    approved = ApprovedCounterfactualReferences.model_validate(approved)
    plan = source.retrieval_plan
    if (
        plan.visual_conditions is None
        or plan.image_preparation == "text-only-v1"
        or approved.owner_id != plan.owner_id
        or approved.session_id != plan.session_id
        or approved.condition_set_sha256 != visual_condition_set_sha256(plan.visual_conditions)
    ):
        raise ValueError("Candidate reference binding is invalid")
    images = evaluate_counterfactual_product_images(
        product_batch=source.product_batch,
        condition_set=plan.visual_conditions,
        reference_set=approved.reference_set,
        reference_images=approved.reference_images,
        proxy_service=proxy_service,
        asset_root=asset_root,
        encoder=encoder,
        score_mode=image_score_mode,
        region_extractor=region_extractor,
    )
    by_product = {image.normalized_product_sha256: image for image in images.candidates}
    texts = (
        {c.normalized_product_sha256: c for c in images.text_batch.candidates}
        if isinstance(images, Siglip2DualImageBatch)
        else {}
    )
    rows = []
    for candidate in source.products:
        image = by_product[normalized_product_candidate_sha256(candidate.product)]
        rows.append(
            CandidateVisualProduct(
                candidate=candidate,
                image=image,
                visual_text=texts.get(image.normalized_product_sha256),
                image_weight=IMAGE_WEIGHT,
                total_score=_total(candidate, image, IMAGE_WEIGHT),
            )
        )
    return CandidateVisualRanking(
        image_weight=IMAGE_WEIGHT,
        sort_profile_id=TEXT_IMAGE_SORT_PROFILE if texts else SORT_PROFILE_ID,
        text_profile_id=BILINGUAL_PROFILE_ID
        if source.retrieval_plan.condition_terms
        else TEXT_PROFILE_ID
        if source.profile_id == "candidate-confirmed-lexical-v4"
        else None,
        profile_id=(
            DUAL_PROFILE
            if isinstance(images, Siglip2DualImageBatch)
            else SIGLIP2_PROFILE_ID
            if isinstance(images, Siglip2AppearanceImageBatch)
            else APPEARANCE_PROFILE_ID
            if isinstance(images, AppearanceImageBatch)
            else FEATURE_PROFILE_ID
            if isinstance(images, AttributeImageBatch) and images.profile_id == "attribute-image-v2"
            else ATTRIBUTE_PROFILE_ID
            if isinstance(images, AttributeImageBatch)
            else PROFILE_ID
        ),
        source=source,
        image_batch=images,
        products=tuple(sorted(rows, key=lambda row: _priority_sort_key(row, source))),
        approval_receipt_sha256=approved.approval_receipt_sha256,
    )


def candidate_history_snapshot(ranking, approved, *, source_text, completed_at):
    ranking = CandidateVisualRanking.model_validate(ranking)
    approved = ApprovedCounterfactualReferences.model_validate(approved)
    plan = ranking.source.retrieval_plan
    source_hash, summary = _clean_source_text(source_text)
    reference_hash = counterfactual_reference_set_sha256(approved.reference_set)
    if (
        source_hash != plan.source_sha256
        or approved.owner_id != plan.owner_id
        or approved.session_id != plan.session_id
        or ranking.approval_receipt_sha256 != approved.approval_receipt_sha256
        or ranking.image_batch.reference_set_sha256 != reference_hash
        or ranking.image_batch.condition_set_sha256 != approved.condition_set_sha256
    ):
        raise ValueError("Candidate history binding is invalid")
    references = []
    for index, image in enumerate(approved.reference_images):
        body = _png(image)
        references.append(
            ProvisionalHistoryReferenceImageWrite(
                schema_version="5.0",
                target="desired" if index == 0 else "counterfactual",
                condition_id=None if index == 0 else f"visual-condition-{index:03d}",
                content_type="image/png",
                sha256=hashlib.sha256(body).hexdigest(),
                byte_length=len(body),
                width=image.width,
                height=image.height,
                body=body,
            )
        )
    products = tuple(
        ProvisionalHistoryProductView(
            schema_version="5.0",
            rank=index,
            title=row.candidate.product.title,
            review_rating=row.candidate.product.rating
            if ranking.sort_profile_id in {SORT_PROFILE_ID, TEXT_IMAGE_SORT_PROFILE}
            else None,
            title_en=row.candidate.product.title_en,
            title_en_status=row.candidate.product.title_en_status,
            title_scores=row.candidate.title_scores,
            condition_scores=row.candidate.text_score.conditions
            if row.candidate.title_scores is not None
            else None,
            price_jpy=row.candidate.product.price_jpy,
            product_url=_safe_product_url(row.candidate.product.product_url),
            required_status=row.candidate.evaluation.required_status,
            image_component_status=row.image.status,
            image_score=row.image.image_score,
            visual_text=row.visual_text,
            total_score=row.total_score,
        )
        for index, row in enumerate(ranking.products, 1)
    )
    return ProvisionalHistoryWrite(
        condition_weighting=plan.condition_weighting,
        image_weight=ranking.image_weight,
        sort_profile_id=ranking.sort_profile_id,
        text_profile_id=ranking.text_profile_id,
        retrieval_provider="playwright"
        if ranking.source.product_batch.provider == "playwright"
        else None,
        schema_version="5.0",
        owner_id=plan.owner_id,
        completion_key=_digest(
            {
                "profile": ranking.profile_id,
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
        provisional_profile_id=(
            "counterfactual-siglip2-dual-v2"
            if ranking.profile_id == DUAL_PROFILE
            else "counterfactual-siglip2-appearance-v1"
            if ranking.profile_id == SIGLIP2_PROFILE_ID
            else "counterfactual-appearance-v1"
            if ranking.profile_id == APPEARANCE_PROFILE_ID
            else "counterfactual-attribute-v2"
            if ranking.profile_id == FEATURE_PROFILE_ID
            else "counterfactual-attribute-v1"
            if ranking.profile_id == ATTRIBUTE_PROFILE_ID
            else "counterfactual-relative-v1"
            if ranking.profile_id == PROFILE_ID
            else "counterfactual-v4-provisional-production-v1"
        ),
        known_holdout_accuracy=None,
        ranking_profile_id=ranking.profile_id,
        ranking_profile_sha256=_history_profile_digest(ranking),
        source_typed_ranked_product_batch_sha256=_digest(ranking.source),
        condition_set_sha256=approved.condition_set_sha256,
        reference_set_sha256=reference_hash,
        runtime_sha256=ranking.image_batch.runtime_sha256,
        reference_images=tuple(references),
        products=products,
    )


def _history_profile_digest(ranking):
    base = (
        _digest(
            {
                "base": SIGLIP2_RANKING_SHA256,
                "text_image": ranking.image_batch.text_batch.runtime_sha256,
                "score": "minimum-condition-unit-cosine-v1",
                "profile": DUAL_PROFILE,
            }
        )
        if ranking.profile_id == DUAL_PROFILE
        else SIGLIP2_RANKING_SHA256
        if ranking.profile_id == SIGLIP2_PROFILE_ID
        else APPEARANCE_RANKING_SHA256
        if ranking.profile_id == APPEARANCE_PROFILE_ID
        else FEATURE_PROFILE_SHA256
        if ranking.profile_id == FEATURE_PROFILE_ID
        else ATTRIBUTE_PROFILE_SHA256
        if ranking.profile_id == ATTRIBUTE_PROFILE_ID
        else PROFILE_SHA256
        if ranking.profile_id == PROFILE_ID
        else LEGACY_PROFILE_SHA256
    )
    digest = (
        _digest(
            {
                "image_ranking": base,
                "text": BILINGUAL_PROFILE_SHA256
                if ranking.text_profile_id == BILINGUAL_PROFILE_ID
                else TEXT_PROFILE_SHA256,
            }
        )
        if ranking.text_profile_id
        else base
    )
    digest = (
        _digest({"base": digest, "image_weight": ranking.image_weight})
        if ranking.image_weight is not None
        else digest
    )
    digest = (
        _digest({"base": digest, "sort_profile_id": ranking.sort_profile_id})
        if ranking.sort_profile_id is not None
        else digest
    )
    weighting = ranking.source.retrieval_plan.condition_weighting
    return (
        _digest({"base": digest, "condition_weighting": weighting.model_dump(mode="json")})
        if weighting is not None
        else digest
    )
