"""Build display-only schema-5 history from a completed provisional ranking."""

from __future__ import annotations

from datetime import datetime
import hashlib
from io import BytesIO
import json
import unicodedata
from urllib.parse import urlsplit

from PIL import Image
from pydantic import ValidationError

from src.search_v2.counterfactual_image import VisualConditionSet
from src.search_v2.counterfactual_image import counterfactual_reference_set_sha256
from src.search_v2.counterfactual_image import visual_condition_set_sha256
from src.search_v2.counterfactual_reference_approval import ApprovedCounterfactualReferences
from src.search_v2.provisional_counterfactual import PROVISIONAL_COUNTERFACTUAL_PROFILE
from src.search_v2.provisional_history_repository import ProvisionalHistoryProductView
from src.search_v2.provisional_history_repository import (
    ProvisionalHistoryReferenceImageWrite,
)
from src.search_v2.provisional_history_repository import ProvisionalHistoryWrite
from src.search_v2.provisional_typed_ranking import ProvisionalTypedRankedProductBatch
from src.search_v2.provisional_typed_ranking import (
    provisional_typed_ranked_product_batch_sha256,
)


_COMPLETION_DOMAIN = b"amazon-explorer-provisional-history-completion-v5\x00"
_INVALID_INPUT_MESSAGE = "Completed provisional history inputs are invalid"


class ProvisionalHistorySnapshotError(ValueError):
    """A fixed-message rejection before provisional history persistence."""


def _clean_source_text(value: object) -> tuple[str, str]:
    if type(value) is not str or not value or len(value) > 2_000:
        raise ValueError("provisional history source text is invalid")
    normalized = unicodedata.normalize("NFKC", value)
    if any(
        unicodedata.category(character).startswith("C") and not character.isspace()
        for character in normalized
    ):
        raise ValueError("provisional history source text is invalid")
    display = " ".join(normalized.split())
    if not display:
        raise ValueError("provisional history source text is invalid")
    return hashlib.sha256(value.encode("utf-8")).hexdigest(), display[:200]


def _png(image) -> bytes:
    decoded = Image.frombytes("RGB", (image.width, image.height), image.rgb_bytes)
    try:
        output = BytesIO()
        decoded.save(output, format="PNG", optimize=False, compress_level=9)
        return output.getvalue()
    finally:
        decoded.close()


def _safe_product_url(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = urlsplit(value)
        host = parsed.hostname.casefold() if parsed.hostname is not None else ""
    except ValueError:
        return None
    if host == "amazon.co.jp" or host.endswith(".amazon.co.jp"):
        return value
    return None


def _completion_key(
    *,
    owner_id: str,
    source_sha256: str,
    ranked_batch_sha256: str,
    approval_receipt_sha256: str,
) -> str:
    payload = json.dumps(
        {
            "schema_version": "5.0",
            "owner_id": owner_id,
            "source_sha256": source_sha256,
            "ranked_batch_sha256": ranked_batch_sha256,
            "approval_receipt_sha256": approval_receipt_sha256,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(_COMPLETION_DOMAIN + payload).hexdigest()


def build_provisional_history_snapshot(
    *,
    owner_id: str,
    source_text: str,
    completed_at: datetime,
    condition_set: VisualConditionSet,
    approved_references: ApprovedCounterfactualReferences,
    ranked_batch: ProvisionalTypedRankedProductBatch,
) -> ProvisionalHistoryWrite:
    """Project v5 ranking into display fields without product image URLs or embeddings."""
    try:
        conditions = VisualConditionSet.model_validate(condition_set)
        approved = ApprovedCounterfactualReferences.model_validate(approved_references)
        ranked = ProvisionalTypedRankedProductBatch.model_validate(ranked_batch)
        source_sha256, summary = _clean_source_text(source_text)
        condition_digest = visual_condition_set_sha256(conditions)
        reference_digest = counterfactual_reference_set_sha256(approved.reference_set)
        if (
            approved.condition_set_sha256 != condition_digest
            or ranked.condition_set_sha256 != condition_digest
            or ranked.reference_set_sha256 != reference_digest
            or approved.reference_set.condition_set_sha256 != condition_digest
            or len(approved.reference_images) != 1 + len(conditions.conditions)
            or not ranked.products
        ):
            raise ValueError("provisional history bindings do not match")

        targets = (("desired", None),) + tuple(
            ("counterfactual", condition.condition_id) for condition in conditions.conditions
        )
        reference_images = []
        for (target, condition_id), image in zip(
            targets,
            approved.reference_images,
            strict=True,
        ):
            body = _png(image)
            reference_images.append(
                ProvisionalHistoryReferenceImageWrite(
                    schema_version="5.0",
                    target=target,
                    condition_id=condition_id,
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
                rank=item.rank,
                title=item.product.title,
                price_jpy=item.product.price_jpy,
                product_url=_safe_product_url(item.product.product_url),
                required_status=item.evaluation.required_status,
                image_component_status=item.image_component.status,
                image_score=item.image_component.image_score,
                total_score=item.breakdown.total_score,
            )
            for item in ranked.products
        )
        ranked_digest = provisional_typed_ranked_product_batch_sha256(ranked)
        return ProvisionalHistoryWrite(
            schema_version="5.0",
            owner_id=owner_id,
            completion_key=_completion_key(
                owner_id=owner_id,
                source_sha256=source_sha256,
                ranked_batch_sha256=ranked_digest,
                approval_receipt_sha256=approved.approval_receipt_sha256,
            ),
            completed_at=completed_at,
            summary=summary,
            provisional_profile_id=PROVISIONAL_COUNTERFACTUAL_PROFILE.profile_id,
            known_holdout_accuracy=PROVISIONAL_COUNTERFACTUAL_PROFILE.known_holdout_accuracy,
            ranking_profile_id=ranked.ranking_profile_id,
            ranking_profile_sha256=ranked.ranking_profile_sha256,
            source_typed_ranked_product_batch_sha256=(
                ranked.source_typed_ranked_product_batch_sha256
            ),
            condition_set_sha256=ranked.condition_set_sha256,
            reference_set_sha256=ranked.reference_set_sha256,
            runtime_sha256=ranked.runtime_sha256,
            reference_images=tuple(reference_images),
            products=products,
        )
    except ProvisionalHistorySnapshotError:
        raise
    except (TypeError, ValueError, ValidationError) as exc:
        raise ProvisionalHistorySnapshotError(_INVALID_INPUT_MESSAGE) from exc
