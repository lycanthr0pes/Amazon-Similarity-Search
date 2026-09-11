"""Candidate-owned staged image approval, evaluation and history orchestration.

The flow owns its candidate service and execution state. Serialized results are
data, not permissions to resume generation, fetch products or consume approvals.
"""

from dataclasses import dataclass
from threading import RLock
import secrets

from src.search_v2.candidate_search import prepare_candidate_search, _digest, _time
from src.search_v2.candidate_queries import build_candidate_queries
from src.search_v2.candidate_diagnostics import CandidateEvaluationError, CandidatePreparationError
from src.search_v2.candidate_completion import (
    CandidateCompletion,
    candidate_history_snapshot,
    complete_candidate_ranking,
)
from src.search_v2.counterfactual_cloudflare_request import (
    build_counterfactual_cloudflare_desired_request,
)
from src.search_v2.counterfactual_cloudflare_http import (
    CounterfactualCloudflareImageArtifact,
    execute_counterfactual_desired_image,
    execute_counterfactual_derived_images,
)
from src.search_v2.counterfactual_image import visual_condition_set_sha256
from src.search_v2.counterfactual_reference_approval import (
    approve_counterfactual_reference_artifacts,
)
from src.search_v2.orchestrator import _policy_and_ledger, _single_image_budget
from src.search_v2.usage_ledger import UsageReservationRequest
from src.search_v2.bulge_reference_quality import (
    assess_bulge_references,
    BulgeReferenceError,
    REFERENCE_QUALITY_SHA256,
)


MAX_REFERENCE_ATTEMPTS = 3


@dataclass(frozen=True, repr=False)
class CandidateReferenceReview:
    sha256: str
    image: CounterfactualCloudflareImageArtifact


class CandidateSearchFlow:
    """One process, one owned candidate session, injected provider boundaries."""

    def __init__(
        self,
        source,
        *,
        owner_id,
        session_id,
        postal_code,
        policy,
        usage_ledger,
        approval_repository,
        history_repository,
        image_transport,
        account_id,
        api_token,
        now,
        visual_extractor,
        query_expander=None,
        lexical_expander=None,
        source_parser=None,
        reference_region_extractor=None,
        image_score_mode="siglip2_appearance",
    ):
        if image_score_mode not in {"siglip2_appearance", "appearance", "relative"}:
            raise ValueError("Invalid candidate image score mode")
        self._image_score_mode = image_score_mode
        self._policy, _ = _policy_and_ledger(policy, usage_ledger)
        self._now = now
        self._candidate = prepare_candidate_search(
            source,
            owner_id=owner_id,
            session_id=session_id,
            postal_code=postal_code,
            normalization_profile=self._policy.normalization_profile,
            now=self._now(),
            visual_extractor=visual_extractor,
            query_expander=query_expander,
            lexical_expander=lexical_expander,
            source_parser=source_parser,
        )
        self._plan = self._candidate.plan
        if self._plan.visual_conditions is None:
            raise CandidatePreparationError("empty_conditions")
        self._source = source
        self._intent = build_candidate_queries(
            source,
            visual_conditions=self._plan.visual_conditions,
            structure=self._plan.source_structure,
        ).retrieval_intent
        self._ledger = usage_ledger
        self._approvals = approval_repository
        self._history = history_repository
        self._transport = image_transport
        self._account = account_id
        self._token = api_token
        self._lock = RLock()
        self._state = "planned"
        self._nonce = secrets.token_hex(16)
        self._attempt = 0
        self._reference = self._approved = self._execution = self._approval_review = None
        self._pending = self._ranking = None
        self._reference_regions = reference_region_extractor
        self._reference_quality = ()

    @property
    def reference_quality(self):
        with self._lock:
            return tuple(
                (key, report.model_copy(deep=True)) for key, report in self._reference_quality
            )

    @property
    def plan(self):
        return self._candidate.plan

    @property
    def plan_sha256(self):
        return self._candidate.plan_sha256

    def select_search_query(self, *, owner_id, plan_sha256, index):
        with self._lock:
            now = self._check(owner_id, {"planned"})
            self._plan = self._candidate.select_search_query(
                owner_id=owner_id, plan_sha256=plan_sha256, index=index, now=now
            )
            return self.plan

    @property
    def reference_images(self):
        with self._lock:
            if self._approved is None:
                raise ValueError("Candidate images are not approved")
            return tuple(image.model_copy(deep=True) for image in self._approved.reference_images)

    def _check(self, owner_id, states):
        now = _time(self._now())
        if (
            owner_id != self._plan.owner_id
            or self._state not in states
            or not self._plan.created_at <= now < self._plan.expires_at
        ):
            raise ValueError("Candidate operation does not match owner, lifetime, or state")
        return now

    def _reserve(self, operation, calls):
        budget = _single_image_budget(self._policy, calls)
        reservation = self._ledger.reserve(
            UsageReservationRequest(
                provider="cloudflare",
                operation=operation,
                owner_id=self._plan.owner_id,
                session_id=self._plan.session_id,
                binding_sha256=self._image_binding,
                amount=budget.amount,
                pricing_policy_sha256=budget.pricing_policy_sha256,
            ),
            now=_time(self._now()),
        )
        return self._ledger.start(
            reservation.reservation_id,
            owner_id=self._plan.owner_id,
            session_id=self._plan.session_id,
            now=_time(self._now()),
        )

    def _finish(self, reservation, success):
        return self._ledger.finish(
            reservation.reservation_id,
            owner_id=self._plan.owner_id,
            session_id=self._plan.session_id,
            success=success,
            now=_time(self._now()),
        )

    def generate_reference(self, *, owner_id, plan_sha256, human_confirmed):
        return self._generate(owner_id, plan_sha256, human_confirmed, {"planned"})

    def regenerate_reference(self, *, owner_id, plan_sha256, human_confirmed):
        return self._generate(
            owner_id,
            plan_sha256,
            human_confirmed,
            {"reference_review", "images_review", "images_approved", "image_failed"},
        )

    def _generate(self, owner_id, plan_sha256, human_confirmed, states):
        with self._lock:
            self._check(owner_id, states)
            if (
                human_confirmed is not True
                or plan_sha256 != self.plan_sha256
                or self._attempt >= MAX_REFERENCE_ATTEMPTS
            ):
                raise ValueError("Candidate reference approval is invalid")
            self._state = "generating"
            self._attempt += 1
            self._reference = self._approved = self._execution = self._approval_review = None
            self._reference_quality = ()
            self._image_binding = _digest(
                {
                    "plan": self.plan_sha256,
                    "attempt": self._attempt,
                    "flow": self._nonce,
                    "policy": _digest(self._policy),
                    "reference_quality_policy": (
                        REFERENCE_QUALITY_SHA256 if self._image_score_mode == "relative" else None
                    ),
                    "image_score_mode": self._image_score_mode,
                }
            )
        reservation = None
        try:
            request = build_counterfactual_cloudflare_desired_request(
                intent=self._intent,
                condition_set=self._plan.visual_conditions,
                preimage_plan_sha256=self._image_binding,
            )
            reservation = self._reserve("reference_image", 1)
            image = execute_counterfactual_desired_image(
                request=request,
                account_id=self._account,
                api_token=self._token,
                transport=self._transport,
            )
            finished = self._finish(reservation, True)
            reservation = None
            review = CandidateReferenceReview(
                _digest({"binding": self._image_binding, "image": image.model_dump(mode="json")}),
                image,
            )
            with self._lock:
                self._desired_request, self._reference_usage = request, finished
                self._reference = review
                self._state = "reference_review"
            return CandidateReferenceReview(review.sha256, image.model_copy(deep=True))
        except Exception:
            if reservation is not None:
                self._finish(reservation, False)
            self._state = "image_failed"
            raise ValueError("Candidate reference generation failed") from None

    def approve_reference(self, *, owner_id, reference_sha256, human_confirmed):
        with self._lock:
            self._check(owner_id, {"reference_review"})
            if human_confirmed is not True or reference_sha256 != self._reference.sha256:
                raise ValueError("Candidate reference approval is invalid")
            self._state = "deriving"
        reservation = None
        try:
            reservation = self._reserve(
                "counterfactual_images", len(self._plan.visual_conditions.conditions)
            )
            execution = execute_counterfactual_derived_images(
                desired_request=self._desired_request,
                desired=self._reference.image,
                intent=self._intent,
                condition_set=self._plan.visual_conditions,
                preimage_plan_sha256=self._image_binding,
                usage_ledger=self._ledger,
                usage_reservation=reservation,
                account_id=self._account,
                api_token=self._token,
                transport=self._transport,
                now=self._now,
            )
            if self._image_score_mode == "relative":
                self._reference_quality = assess_bulge_references(
                    self._plan.visual_conditions, execution.images, self._reference_regions
                )
            if any(report.status != "passed" for _, report in self._reference_quality):
                raise BulgeReferenceError()
            issued = self._approvals.issue(
                owner_id=self._plan.owner_id,
                session_id=self._plan.session_id,
                condition_set_sha256=visual_condition_set_sha256(self._plan.visual_conditions),
                reference_set_sha256=execution.reference_set_sha256,
                request_metadata_sha256=execution.request_metadata_sha256,
                usage_reservation=execution.usage_reservation,
                reference_image_reservation=self._reference_usage,
                now=_time(self._now()),
            )
            with self._lock:
                self._execution, self._approval_review = (
                    execution,
                    issued.review.model_copy(deep=True),
                )
                self._state = "images_review"
            return issued
        except Exception as error:
            if reservation is not None:
                current = next(
                    r
                    for r in self._ledger.snapshot().reservations
                    if r.reservation_id == reservation.reservation_id
                )
                if current.status == "started":
                    self._finish(current, False)
            self._state = "image_failed"
            if isinstance(error, BulgeReferenceError):
                raise error from None
            raise ValueError("Candidate derived image generation failed") from None

    def approve_images(self, *, owner_id, approval_id, token, human_confirmed):
        with self._lock:
            now = self._check(owner_id, {"images_review"})
            if human_confirmed is not True or approval_id != self._approval_review.approval_id:
                raise ValueError("Candidate final image approval is invalid")
            try:
                receipt = self._approvals.consume(
                    review=self._approval_review, token=token, human_confirmed=True, now=now
                )
            except Exception:
                raise ValueError("Candidate final image approval failed") from None
            self._state = "approving"
            execution = self._execution
            try:
                self._approved = approve_counterfactual_reference_artifacts(
                    condition_set=self._plan.visual_conditions,
                    request_set=execution.request_set,
                    images=execution.images,
                    reference_set_sha256=execution.reference_set_sha256,
                    request_metadata_sha256=execution.request_metadata_sha256,
                    approval_receipt=receipt,
                )
                self._state = "images_approved"
            except Exception:
                self._state = "failed"
                raise ValueError("Candidate final image approval failed") from None

    def approve_and_fetch(self, *, owner_id, plan_sha256, transport):
        with self._lock:
            now = self._check(owner_id, {"images_approved"})
            if plan_sha256 != self.plan_sha256:
                raise ValueError("Candidate retrieval plan changed")
            self._state = "fetching"
        try:
            review = self._candidate.approve_and_fetch(
                owner_id=owner_id,
                plan_sha256=plan_sha256,
                transport=transport,
                now=now,
            )
            self._state = "attribute_review"
            return review
        except Exception:
            self._state = "failed"
            raise ValueError("Candidate retrieval failed") from None

    def confirm(self, *, owner_id, review_sha256, selections):
        with self._lock:
            now = self._check(owner_id, {"attribute_review"})
            receipt = self._candidate.confirm(
                owner_id=owner_id, review_sha256=review_sha256, selections=selections, now=now
            )
            self._state = "confirmed"
            return receipt

    def complete(self, *, owner_id, proxy_service, asset_root, encoder, region_extractor=None):
        with self._lock:
            now = self._check(owner_id, {"confirmed"})
            self._state = "evaluating"
        stage = "candidate_ranking"
        try:
            source = self._candidate.rank(owner_id=owner_id, now=now)
            stage = "visual_evaluation"
            ranking = complete_candidate_ranking(
                source,
                self._approved,
                proxy_service=proxy_service,
                asset_root=asset_root,
                encoder=encoder,
                region_extractor=region_extractor,
                image_score_mode=self._image_score_mode,
            )
            stage = "history_snapshot"
            pending = candidate_history_snapshot(
                ranking, self._approved, source_text=self._source, completed_at=_time(self._now())
            )
        except (CandidateEvaluationError, CandidatePreparationError):
            self._state = "failed"
            raise
        except Exception:
            self._state = "failed"
            raise CandidateEvaluationError(stage, boundary="completion") from None
        with self._lock:
            self._pending, self._ranking = pending, ranking
            self._state = "history_pending"
        return self.retry_history(owner_id=owner_id)

    def retry_history(self, *, owner_id):
        with self._lock:
            now = self._check(owner_id, {"history_pending"})
            self._state = "saving"
        try:
            detail = self._history.save(self._pending, now=now)
        except Exception:
            self._state = "history_pending"
            raise CandidateEvaluationError("history_save", boundary="history") from None
        self._state = "completed"
        return CandidateCompletion(self._ranking, detail)
