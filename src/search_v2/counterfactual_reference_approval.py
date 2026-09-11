"""Human approval boundary for generated counterfactual reference artifacts."""

from __future__ import annotations

import hashlib
import hmac
from io import BytesIO
import json
from typing import Annotated
from typing import Literal

from PIL import Image
from PIL import UnidentifiedImageError
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import ValidationError
from pydantic import model_validator

from src.search_v2.counterfactual_cloudflare_http import (
    CounterfactualCloudflareImageArtifact,
)
from src.search_v2.counterfactual_cloudflare_http import (
    counterfactual_cloudflare_reference_set_sha256,
)
from src.search_v2.counterfactual_cloudflare_request import (
    CounterfactualCloudflareRequestSet,
)
from src.search_v2.counterfactual_cloudflare_request import (
    counterfactual_cloudflare_request_set_sha256,
)
from src.search_v2.counterfactual_image import CounterfactualReferenceSet
from src.search_v2.counterfactual_image import VisualConditionSet
from src.search_v2.counterfactual_image import build_counterfactual_reference_set
from src.search_v2.counterfactual_image import visual_condition_set_sha256
from src.search_v2.image_proxy import ProxyImage
from src.search_v2.image_proxy import proxy_image_pixel_sha256
from src.search_v2.image_similarity import compute_phash
from src.search_v2.provisional_approval_repository import (
    CounterfactualReferenceApprovalReceipt,
)
from src.search_v2.provisional_approval_repository import (
    counterfactual_approval_receipt_sha256,
)
from src.search_v2.usage_ledger import SubjectId


APPROVED_COUNTERFACTUAL_REFERENCES_DOMAIN = (
    b"amazon-explorer-approved-counterfactual-references-v5\x00"
)
_INVALID_APPROVAL_MESSAGE = "Inputs did not match the counterfactual reference approval contract"

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class CounterfactualReferenceApprovalError(ValueError):
    """A fixed-message rejection at the human confirmation boundary."""


class _StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


class ApprovedCounterfactualReferences(_StrictFrozenContract):
    schema_version: Literal["5.0"]
    owner_id: SubjectId = Field(repr=False)
    session_id: SubjectId = Field(repr=False)
    approval_basis: Literal["explicit_human_confirmation"]
    human_confirmed: Literal[True]
    condition_set_sha256: Digest
    cloudflare_reference_set_sha256: Digest
    cloudflare_request_metadata_sha256: Digest
    approval_receipt_sha256: Digest
    reference_set: CounterfactualReferenceSet
    reference_images: Annotated[
        tuple[ProxyImage, ...],
        Field(min_length=2, max_length=4, repr=False),
    ]

    @model_validator(mode="after")
    def validate_bindings(self) -> ApprovedCounterfactualReferences:
        if self.reference_set.condition_set_sha256 != self.condition_set_sha256:
            raise ValueError("approved condition set binding does not match")
        expected_pixels = (
            self.reference_set.desired_image_hash.image_pixel_sha256,
            *(item.image_hash.image_pixel_sha256 for item in self.reference_set.counterfactuals),
        )
        if tuple(item.pixel_sha256 for item in self.reference_images) != expected_pixels:
            raise ValueError("approved reference image binding does not match")
        return self


def _proxy_image(artifact: CounterfactualCloudflareImageArtifact) -> ProxyImage:
    try:
        with Image.open(BytesIO(artifact.body), formats=("PNG",)) as source:
            source.load()
            converted = source.convert("RGB")
            try:
                width, height = converted.size
                rgb = converted.tobytes()
            finally:
                converted.close()
        return ProxyImage(
            schema_version="2.0",
            source_url_sha256=hashlib.sha256(
                b"cloudflare-counterfactual-request-v1\x00"
                + artifact.request_sha256.encode("ascii")
            ).hexdigest(),
            source_bytes_sha256=artifact.sha256,
            pixel_sha256=proxy_image_pixel_sha256(width, height, rgb),
            content_type="image/png",
            image_format="PNG",
            width=width,
            height=height,
            rgb_bytes=rgb,
        )
    except (OSError, TypeError, UnidentifiedImageError, ValueError) as exc:
        raise CounterfactualReferenceApprovalError(_INVALID_APPROVAL_MESSAGE) from exc


def approve_counterfactual_reference_artifacts(
    *,
    condition_set: VisualConditionSet,
    request_set: CounterfactualCloudflareRequestSet,
    images: tuple[CounterfactualCloudflareImageArtifact, ...],
    reference_set_sha256: str,
    request_metadata_sha256: str,
    approval_receipt: CounterfactualReferenceApprovalReceipt,
) -> ApprovedCounterfactualReferences:
    """Convert a persistently consumed reference review into local CLIP material."""
    try:
        conditions = VisualConditionSet.model_validate(condition_set)
        requests = CounterfactualCloudflareRequestSet.model_validate(request_set)
        receipt = CounterfactualReferenceApprovalReceipt.model_validate(approval_receipt)
        if type(images) is not tuple:
            raise ValueError("counterfactual references require a consumed approval")
        artifacts = tuple(
            CounterfactualCloudflareImageArtifact.model_validate(item) for item in images
        )
        condition_digest = visual_condition_set_sha256(conditions)
        if (
            requests.condition_set_sha256 != condition_digest
            or receipt.condition_set_sha256 != condition_digest
            or receipt.reference_set_sha256 != reference_set_sha256
            or receipt.request_metadata_sha256 != request_metadata_sha256
            or receipt.call_count != len(artifacts)
            or len(artifacts) != requests.call_count
            or tuple(item.condition_id for item in artifacts)
            != tuple(item.condition_id for item in requests.requests)
            or not hmac.compare_digest(
                reference_set_sha256,
                counterfactual_cloudflare_reference_set_sha256(artifacts),
            )
            or not hmac.compare_digest(
                request_metadata_sha256,
                counterfactual_cloudflare_request_set_sha256(requests),
            )
        ):
            raise ValueError("counterfactual approval binding does not match")

        proxy_images = tuple(_proxy_image(item) for item in artifacts)
        hashes = tuple(compute_phash(item) for item in proxy_images)
        references = build_counterfactual_reference_set(
            condition_set=conditions,
            desired_image_hash=hashes[0],
            counterfactual_image_hashes=hashes[1:],
        )
        return ApprovedCounterfactualReferences(
            schema_version="5.0",
            owner_id=receipt.owner_id,
            session_id=receipt.session_id,
            approval_basis="explicit_human_confirmation",
            human_confirmed=True,
            condition_set_sha256=condition_digest,
            cloudflare_reference_set_sha256=reference_set_sha256,
            cloudflare_request_metadata_sha256=request_metadata_sha256,
            approval_receipt_sha256=counterfactual_approval_receipt_sha256(receipt),
            reference_set=references,
            reference_images=proxy_images,
        )
    except CounterfactualReferenceApprovalError:
        raise
    except (TypeError, ValueError, ValidationError) as exc:
        raise CounterfactualReferenceApprovalError(_INVALID_APPROVAL_MESSAGE) from exc


def approved_counterfactual_references_sha256(
    approved: ApprovedCounterfactualReferences,
) -> str:
    try:
        validated = ApprovedCounterfactualReferences.model_validate(approved)
        payload = json.dumps(
            validated.model_dump(mode="json"),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(APPROVED_COUNTERFACTUAL_REFERENCES_DOMAIN + payload).hexdigest()
    except (TypeError, ValueError, ValidationError) as exc:
        raise CounterfactualReferenceApprovalError(_INVALID_APPROVAL_MESSAGE) from exc
