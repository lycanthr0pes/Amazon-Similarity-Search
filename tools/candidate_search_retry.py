"""Resume the fixed synthetic live experiment with freshly authorized retrieval."""

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import time

from src.search_v2.candidate_search import CandidatePlan, CandidateSearch, _digest
from src.search_v2.candidate_completion import (
    CandidateCompletion,
    candidate_history_snapshot,
    complete_candidate_ranking,
)
from src.search_v2.counterfactual_cloudflare_http import (
    CounterfactualCloudflareImageArtifact,
    counterfactual_cloudflare_reference_set_sha256,
)
from src.search_v2.counterfactual_image import (
    build_counterfactual_reference_set,
    visual_condition_set_sha256,
)
from src.search_v2.counterfactual_reference_approval import (
    ApprovedCounterfactualReferences,
    _proxy_image,
)
from src.search_v2.image_similarity import compute_phash
from src.search_v2.provisional_approval_repository import (
    CounterfactualReferenceApprovalReceipt,
    CounterfactualReferenceApprovalReview,
    counterfactual_approval_receipt_sha256,
    counterfactual_approval_review_sha256,
)
from src.search_v2.provisional_history_repository import SqliteProvisionalHistoryRepository
from tools import backend_search_live_e2e as shared
from tools import candidate_search_live_e2e as live


_FILES = (
    "plan.json",
    "approvals.sqlite3",
    "image-1.png",
    "image-2.png",
    "image-response-1.json",
    "image-response-2.json",
)


def _read_private(path):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
            or info.st_size > 8 * 1024 * 1024
        ):
            raise ValueError("Saved run file is not private and bounded")
        body = stream.read(8 * 1024 * 1024 + 1)
        if len(body) > 8 * 1024 * 1024:
            raise ValueError("Saved run file exceeds limit")
        return body


@dataclass(frozen=True, repr=False)
class SavedRun:
    root: Path
    sha256: str
    plan: CandidatePlan
    approved: ApprovedCounterfactualReferences


def load_saved_run(root):
    """Read an existing receipt, without consuming or reissuing its approval token."""
    root = Path(root)
    info = root.lstat()
    if (
        not root.is_absolute()
        or root.resolve() != root
        or not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise ValueError("Saved run directory is not private")
    bodies = {name: _read_private(root / name) for name in _FILES}
    hashes = {name: hashlib.sha256(body).hexdigest() for name, body in bodies.items()}
    digest = _digest(hashes)
    plan = CandidatePlan.model_validate_json(bodies["plan.json"])
    if (
        plan.owner_id != live.OWNER
        or plan.source_sha256 != hashlib.sha256(live.SYNTHETIC_INPUT.encode()).hexdigest()
        or plan.visual_conditions is None
        or len(plan.visual_conditions.conditions) != 1
    ):
        raise ValueError("Saved run does not match the fixed experiment")
    # immutable read avoids locks/WAL creation and never selects token columns.
    with sqlite3.connect(
        (root / "approvals.sqlite3").as_uri() + "?mode=ro&immutable=1", uri=True
    ) as connection:
        rows = connection.execute(
            "SELECT review_json, review_sha256, consumed_at FROM counterfactual_approvals"
        ).fetchmany(2)
    if len(rows) != 1 or rows[0][2] is None:
        raise ValueError("Saved images have no unique consumed approval")
    review = CounterfactualReferenceApprovalReview.model_validate_json(rows[0][0])
    consumed = datetime.fromisoformat(rows[0][2])
    if (
        counterfactual_approval_review_sha256(review) != rows[0][1]
        or review.owner_id != plan.owner_id
        or review.session_id != plan.session_id
        or review.condition_set_sha256 != visual_condition_set_sha256(plan.visual_conditions)
        or not review.issued_at <= consumed < review.expires_at
        or review.call_count != 2
    ):
        raise ValueError("Saved image approval does not match the plan")
    artifacts = tuple(
        CounterfactualCloudflareImageArtifact.model_validate(
            {
                **json.loads(bodies[f"image-response-{i}.json"]),
                "body": bodies[f"image-{i}.png"],
            }
        )
        for i in (1, 2)
    )
    if counterfactual_cloudflare_reference_set_sha256(artifacts) != review.reference_set_sha256:
        raise ValueError("Saved images do not match the consumed review")
    receipt = CounterfactualReferenceApprovalReceipt.model_validate(
        {
            **review.model_dump(exclude={"issued_at", "expires_at"}),
            "approval_basis": "explicit_human_confirmation",
            "consumed_at": consumed,
        }
    )
    images = tuple(_proxy_image(item) for item in artifacts)
    phashes = tuple(compute_phash(item) for item in images)
    approved = ApprovedCounterfactualReferences(
        schema_version="5.0",
        owner_id=plan.owner_id,
        session_id=plan.session_id,
        approval_basis="explicit_human_confirmation",
        human_confirmed=True,
        condition_set_sha256=review.condition_set_sha256,
        cloudflare_reference_set_sha256=review.reference_set_sha256,
        # Retain the recorded request provenance; do not invent missing request bodies.
        cloudflare_request_metadata_sha256=review.request_metadata_sha256,
        approval_receipt_sha256=counterfactual_approval_receipt_sha256(receipt),
        reference_set=build_counterfactual_reference_set(
            condition_set=plan.visual_conditions,
            desired_image_hash=phashes[0],
            counterfactual_image_hashes=phashes[1:],
        ),
        reference_images=images,
    )
    if any(hashlib.sha256(_read_private(root / n)).hexdigest() != hashes[n] for n in _FILES):
        raise ValueError("Saved run changed while loading")
    return SavedRun(root, digest, plan, approved)


class _TrackedProducts(live._Products):
    def get(self, **kwargs):
        response = super().get(**kwargs)
        try:
            payload = json.loads(b"".join(response.body_chunks))
            task = payload.get("id")
            status = payload.get("status")
            metadata = {"call": self.tasks + self.polls, "http_status": response.status_code}
            if isinstance(task, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,255}", task):
                metadata["provider_request_id"] = task
            if status in ("Pending", "Success", "Failure"):
                metadata["provider_status"] = status
            shared._json_file(self.output, f"task-status-{self.tasks + self.polls}.json", metadata)
        except (ValueError, TypeError, AttributeError):
            pass  # Invalid provider JSON is rejected by the existing task adapter.
        return response


class _DiagnosedProducts(live.CandidateProducts):
    def fetch(self, request):
        try:
            return super().fetch(request)
        except Exception as error:
            shared._json_file(
                self.transport.output,
                "retrieval-failure.json",
                {"exception_type": type(error).__name__},
            )
            raise


def run_search_retry(config, services, bundle, *, human_confirmed):
    shared._new_output(config)
    products = _TrackedProducts(services.outscraper_transport, config.output_dir)
    proxy = shared._CountedProxy(services.proxy_service)
    encoder = shared._CountedEncoder(services.encoder)
    stage = "saved_approval"
    started = time.monotonic()
    try:
        if human_confirmed is not True:
            raise ValueError("Search retry requires current human authorization")
        current = load_saved_run(bundle.root)
        if current.sha256 != bundle.sha256:
            raise ValueError("Saved run changed since authorization")
        policy, _ = shared._policy_and_ledger()
        candidate = CandidateSearch.from_approved_plan(
            current.plan,
            source=live.SYNTHETIC_INPUT,
            owner_id=live.OWNER,
            plan_sha256=_digest(current.plan),
            human_confirmed=True,
            normalization_profile=policy.normalization_profile,
            now=services.now(),
            use_playwright=services.product_transport_factory is not None,
        )
        shared._json_file(config.output_dir, "plan.json", candidate.plan.model_dump(mode="json"))
        shared._json_file(
            config.output_dir,
            "reused-approval.json",
            {
                "source_bundle_sha256": current.sha256,
                "original_plan_sha256": _digest(current.plan),
                "approval_receipt_sha256": current.approved.approval_receipt_sha256,
                "new_search_human_confirmed": True,
            },
        )
        stage = "candidates"
        review = candidate.approve_and_fetch(
            owner_id=live.OWNER,
            plan_sha256=candidate.plan_sha256,
            now=services.now(),
            transport=services.product_transport_factory(candidate.plan.request)
            if services.product_transport_factory
            else _DiagnosedProducts(
                candidate.plan.request, services.load_outscraper_api_key, products, services.sleep
            ),
        )
        if review.unresolved:
            raise ValueError("Fixed experiment requires additional condition confirmation")
        stage = "condition_confirmation"
        candidate.confirm(
            owner_id=live.OWNER, review_sha256=review.sha256, selections={}, now=services.now()
        )
        stage = "ranking"
        source = candidate.rank(owner_id=live.OWNER, now=services.now())
        stage = "clip"
        ranking = complete_candidate_ranking(
            source,
            current.approved,
            image_score_mode="appearance",
            proxy_service=proxy,
            asset_root=config.asset_root,
            encoder=encoder,
        )
        stage = "history"
        now = services.now()
        pending = candidate_history_snapshot(
            ranking, current.approved, source_text=live.SYNTHETIC_INPUT, completed_at=now
        )
        history = SqliteProvisionalHistoryRepository(config.output_dir / "history.sqlite3")
        completed = CandidateCompletion(ranking, history.save(pending, now=now))
        result = {
            "status": "succeeded",
            **live._history_output(config, completed, current.approved, now),
        }
    except Exception as error:
        result = {
            "status": "failed",
            "failure_stage": stage,
            "exception_type": type(error).__name__,
        }
    result.update(
        bonsai_calls=0,
        cloudflare_calls=0,
        reused_images=2,
        outscraper_tasks=products.tasks,
        outscraper_polls=products.polls,
        product_image_attempts=proxy.calls,
        product_images_received=proxy.succeeded,
        clip_batches=encoder.calls,
        retry_count=0,
        elapsed_seconds=round(time.monotonic() - started, 3),
    )
    shared._json_file(config.output_dir, "summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-live-api", action="store_true")
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--asset-root", type=Path, required=True)
    args = parser.parse_args()
    if not args.run_live_api:
        parser.error("Separate human authorization and live opt-in are required")
    from src.search_v2.image_proxy_service import ImageProxyService
    from src.search_v2.image_similarity import verify_clip_asset_directory
    from src.search_v2.image_similarity_process import ProcessIsolatedClipImageEncoder
    from src.search_v2.playwright_products import PlaywrightProducts

    try:
        bundle = load_saved_run(args.source_dir)
        if bundle.sha256 != args.source_sha256:
            raise ValueError("Authorized saved run changed")
        verify_clip_asset_directory(args.asset_root)
        services = shared.BackendE2EServices(
            bonsai_session=None,
            load_cloudflare=None,
            cloudflare_transport=None,
            load_outscraper_api_key=None,
            outscraper_transport=None,
            product_transport_factory=PlaywrightProducts,
            proxy_service=ImageProxyService(allowed_hosts=("m.media-amazon.com",)),
            encoder=ProcessIsolatedClipImageEncoder(),
            now=lambda: datetime.now(timezone.utc),
            sleep=time.sleep,
            confirm=None,
        )
        result = run_search_retry(
            shared.BackendE2EConfig(args.output_dir, args.asset_root),
            services,
            bundle,
            human_confirmed=True,
        )
        print(json.dumps(result), flush=True)
        return 0 if result["status"] == "succeeded" else 1
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "failure_stage": "entry",
                    "exception_type": type(error).__name__,
                }
            ),
            flush=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
