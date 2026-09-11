from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from pydantic import model_validator


MAX_LEDGER_RESERVATIONS = 10_000
MAX_USAGE_CALLS = 1_000_000
MAX_USAGE_TOKENS = 1_000_000_000_000
MAX_USAGE_COST_MICROUSD = 1_000_000_000_000_000

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
SubjectId = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"),
]
ReservationId = Annotated[
    str,
    StringConstraints(min_length=32, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
]
Provider = Literal["bonsai", "cloudflare", "outscraper"]
UsageOperation = Literal[
    "intent",
    "image_set",
    "reference_image",
    "counterfactual_images",
    "counterfactual_reference_set",
    "product_search",
]
ReservationStatus = Literal["reserved", "started", "succeeded", "failed", "released"]


class UsageLedgerError(ValueError):
    pass


class UsageLimitExceeded(UsageLedgerError):
    pass


class StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        revalidate_instances="always",
        frozen=True,
    )


def _utc_datetime(value: datetime, *, field_name: str) -> datetime:
    if type(value) is not datetime:
        raise TypeError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must use UTC")
    return value.astimezone(timezone.utc)


class UsageAmount(StrictFrozenContract):
    calls: Annotated[int, Field(ge=0, le=MAX_USAGE_CALLS)]
    tokens: Annotated[int, Field(ge=0, le=MAX_USAGE_TOKENS)]
    cost_microusd: Annotated[int, Field(ge=0, le=MAX_USAGE_COST_MICROUSD)]

    @property
    def is_zero(self) -> bool:
        return self.calls == 0 and self.tokens == 0 and self.cost_microusd == 0


class ProviderUsageLimits(StrictFrozenContract):
    provider: Provider
    pricing_policy_sha256: Digest
    quota_enforcement: Literal["enforced", "disabled"] = "enforced"
    per_user_day: UsageAmount
    per_session: UsageAmount
    global_day: UsageAmount

    @model_validator(mode="after")
    def validate_disabled_quota(self) -> ProviderUsageLimits:
        if self.quota_enforcement == "disabled" and not all(
            amount.is_zero for amount in (self.per_user_day, self.per_session, self.global_day)
        ):
            raise ValueError("disabled quota must not contain limit values")
        return self


def build_no_quota_usage_policies(
    *,
    bonsai_pricing_policy_sha256: str,
    cloudflare_pricing_policy_sha256: str,
    outscraper_pricing_policy_sha256: str,
) -> list[ProviderUsageLimits]:
    """Build production policies that record attempts without usage quotas."""
    zero = UsageAmount(calls=0, tokens=0, cost_microusd=0)
    return [
        ProviderUsageLimits(
            provider=provider,
            pricing_policy_sha256=pricing_digest,
            quota_enforcement="disabled",
            per_user_day=zero,
            per_session=zero,
            global_day=zero,
        )
        for provider, pricing_digest in (
            ("bonsai", bonsai_pricing_policy_sha256),
            ("cloudflare", cloudflare_pricing_policy_sha256),
            ("outscraper", outscraper_pricing_policy_sha256),
        )
    ]


def _policy_digest_from_validated(policies: list[ProviderUsageLimits]) -> str:
    canonical = json.dumps(
        [
            policy.model_dump(mode="json")
            for policy in sorted(policies, key=lambda item: item.provider)
        ],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(b"amazon-explorer-usage-policy-v2\n" + canonical).hexdigest()


class UsageReservationRequest(StrictFrozenContract):
    provider: Provider
    operation: UsageOperation
    owner_id: SubjectId
    session_id: SubjectId
    binding_sha256: Digest
    amount: UsageAmount
    pricing_policy_sha256: Digest

    @model_validator(mode="after")
    def validate_operation(self) -> UsageReservationRequest:
        expected_provider = {
            "intent": "bonsai",
            "image_set": "cloudflare",
            "reference_image": "cloudflare",
            "counterfactual_images": "cloudflare",
            "counterfactual_reference_set": "cloudflare",
            "product_search": "outscraper",
        }[self.operation]
        if self.provider != expected_provider:
            raise ValueError("usage operation does not match provider")
        if self.amount.is_zero:
            raise ValueError("usage reservation must reserve at least one dimension")
        return self


class UsageReservation(StrictFrozenContract):
    reservation_id: ReservationId
    request: UsageReservationRequest
    usage_policy_sha256: Digest
    status: ReservationStatus
    reserved_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @field_validator("reserved_at", "started_at", "finished_at")
    @classmethod
    def validate_optional_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _utc_datetime(value, field_name="reservation timestamp")

    @model_validator(mode="after")
    def validate_lifecycle(self) -> UsageReservation:
        if self.status == "reserved":
            if self.started_at is not None or self.finished_at is not None:
                raise ValueError("reserved usage must not have lifecycle timestamps")
        elif self.status == "started":
            if self.started_at is None or self.finished_at is not None:
                raise ValueError("started usage requires only started_at")
        elif self.status in {"succeeded", "failed"}:
            if self.started_at is None or self.finished_at is None:
                raise ValueError("finished attempt requires start and finish timestamps")
        elif self.status == "released":
            if self.started_at is not None or self.finished_at is None:
                raise ValueError("released usage requires finish without start")

        if self.started_at is not None and self.started_at < self.reserved_at:
            raise ValueError("usage start precedes reservation")
        if self.finished_at is not None:
            lower_bound = self.started_at or self.reserved_at
            if self.finished_at < lower_bound:
                raise ValueError("usage finish precedes its prior lifecycle event")
        return self

    @property
    def provider(self) -> Provider:
        return self.request.provider

    @property
    def operation(self) -> UsageOperation:
        return self.request.operation

    @property
    def owner_id(self) -> str:
        return self.request.owner_id

    @property
    def session_id(self) -> str:
        return self.request.session_id

    @property
    def binding_sha256(self) -> str:
        return self.request.binding_sha256

    @property
    def amount(self) -> UsageAmount:
        return self.request.amount


class UsageLedgerSnapshot(StrictFrozenContract):
    schema_version: Literal["2.0"]
    policies: Annotated[list[ProviderUsageLimits], Field(min_length=1, max_length=3)]
    reservations: Annotated[list[UsageReservation], Field(max_length=MAX_LEDGER_RESERVATIONS)]

    @model_validator(mode="after")
    def validate_unique_entries(self) -> UsageLedgerSnapshot:
        providers = [policy.provider for policy in self.policies]
        if len(providers) != len(set(providers)):
            raise ValueError("usage ledger requires one policy per provider")
        policy_by_provider = {policy.provider: policy for policy in self.policies}
        expected_usage_policy_sha256 = _policy_digest_from_validated(self.policies)

        reservation_ids = [reservation.reservation_id for reservation in self.reservations]
        if len(reservation_ids) != len(set(reservation_ids)):
            raise ValueError("usage ledger contains duplicate reservation IDs")
        for reservation in self.reservations:
            policy = policy_by_provider.get(reservation.provider)
            if policy is None:
                raise ValueError("usage reservation has no provider policy")
            if not hmac.compare_digest(
                reservation.request.pricing_policy_sha256,
                policy.pricing_policy_sha256,
            ):
                raise ValueError("usage reservation pricing policy does not match")
            if not hmac.compare_digest(
                reservation.usage_policy_sha256,
                expected_usage_policy_sha256,
            ):
                raise ValueError("usage reservation does not match the ledger policy")
        return self


def _validated_policies(
    policies: list[ProviderUsageLimits],
) -> list[ProviderUsageLimits]:
    if type(policies) is not list:
        raise TypeError("usage policies must be a list")
    try:
        snapshot = UsageLedgerSnapshot(
            schema_version="2.0",
            policies=policies,
            reservations=[],
        )
    except ValueError as exc:
        message = str(exc)
        if "one policy per provider" in message:
            raise UsageLedgerError("usage ledger requires one policy per provider") from None
        raise UsageLedgerError("usage policies are invalid") from exc
    return sorted(snapshot.policies, key=lambda item: item.provider)


def usage_policy_sha256(policies: list[ProviderUsageLimits]) -> str:
    validated = _validated_policies(policies)
    return _policy_digest_from_validated(validated)


UsageTotal = tuple[int, int, int]


def _add_amount(total: UsageTotal, amount: UsageAmount) -> UsageTotal:
    return (
        total[0] + amount.calls,
        total[1] + amount.tokens,
        total[2] + amount.cost_microusd,
    )


def _within_limit(total: UsageTotal, limit: UsageAmount) -> bool:
    return total[0] <= limit.calls and total[1] <= limit.tokens and total[2] <= limit.cost_microusd


class InMemoryUsageLedger:
    """Atomic only inside one process; snapshots are suitable for a later repository boundary."""

    _CHARGED_STATUSES = frozenset({"reserved", "started", "succeeded", "failed"})

    def __init__(self, policies: list[ProviderUsageLimits]) -> None:
        validated = _validated_policies(policies)
        self._policies = {policy.provider: policy for policy in validated}
        self._reservations: dict[str, UsageReservation] = {}
        self._lock = threading.Lock()

    @classmethod
    def from_snapshot(cls, snapshot: UsageLedgerSnapshot) -> InMemoryUsageLedger:
        try:
            validated = UsageLedgerSnapshot.model_validate(snapshot)
        except ValueError as exc:
            raise UsageLedgerError("usage ledger snapshot is invalid") from exc
        ledger = cls(validated.policies)
        ledger._reservations = {
            reservation.reservation_id: reservation for reservation in validated.reservations
        }
        ledger._validate_current_limits()
        return ledger

    def snapshot(self) -> UsageLedgerSnapshot:
        with self._lock:
            return UsageLedgerSnapshot(
                schema_version="2.0",
                policies=sorted(self._policies.values(), key=lambda item: item.provider),
                reservations=sorted(
                    self._reservations.values(),
                    key=lambda item: (item.reserved_at, item.reservation_id),
                ),
            )

    def reserve(
        self,
        request: UsageReservationRequest,
        *,
        now: datetime,
    ) -> UsageReservation:
        try:
            validated = UsageReservationRequest.model_validate(request)
        except ValueError as exc:
            raise UsageLedgerError("usage reservation request is invalid") from exc
        validated_now = _utc_datetime(now, field_name="now")

        with self._lock:
            policy = self._policies.get(validated.provider)
            if policy is None:
                raise UsageLedgerError("usage provider has no approved policy")
            if not hmac.compare_digest(
                validated.pricing_policy_sha256,
                policy.pricing_policy_sha256,
            ):
                raise UsageLedgerError("usage reservation pricing policy does not match")
            if self._would_exceed(validated, policy, reserved_at=validated_now):
                raise UsageLimitExceeded("usage reservation exceeds an approved limit")
            if len(self._reservations) >= MAX_LEDGER_RESERVATIONS:
                raise UsageLimitExceeded("usage ledger reservation capacity is exhausted")

            reservation_id = self._new_reservation_id()
            reservation = UsageReservation(
                reservation_id=reservation_id,
                request=validated,
                usage_policy_sha256=usage_policy_sha256(list(self._policies.values())),
                status="reserved",
                reserved_at=validated_now,
                started_at=None,
                finished_at=None,
            )
            self._reservations[reservation_id] = reservation
            return reservation

    def start(
        self,
        reservation_id: str,
        *,
        owner_id: str,
        session_id: str,
        now: datetime,
    ) -> UsageReservation:
        validated_now = _utc_datetime(now, field_name="now")
        with self._lock:
            reservation = self._owned_reservation(reservation_id, owner_id, session_id)
            if reservation.status != "reserved":
                raise UsageLedgerError("only a reserved usage attempt can start")
            updated = self._updated_reservation(
                reservation,
                status="started",
                started_at=validated_now,
                finished_at=None,
            )
            self._reservations[reservation_id] = updated
            return updated

    def finish(
        self,
        reservation_id: str,
        *,
        owner_id: str,
        session_id: str,
        success: bool,
        now: datetime,
    ) -> UsageReservation:
        if type(success) is not bool:
            raise TypeError("success must be a bool")
        validated_now = _utc_datetime(now, field_name="now")
        with self._lock:
            reservation = self._owned_reservation(reservation_id, owner_id, session_id)
            if reservation.status != "started":
                raise UsageLedgerError("only a started usage attempt can finish")
            updated = self._updated_reservation(
                reservation,
                status="succeeded" if success else "failed",
                started_at=reservation.started_at,
                finished_at=validated_now,
            )
            self._reservations[reservation_id] = updated
            return updated

    def release(
        self,
        reservation_id: str,
        *,
        owner_id: str,
        session_id: str,
        now: datetime,
    ) -> UsageReservation:
        validated_now = _utc_datetime(now, field_name="now")
        with self._lock:
            reservation = self._owned_reservation(reservation_id, owner_id, session_id)
            if reservation.status == "started":
                raise UsageLedgerError("started reservation cannot be released")
            if reservation.status != "reserved":
                raise UsageLedgerError("only an unstarted reservation can be released")
            updated = self._updated_reservation(
                reservation,
                status="released",
                started_at=None,
                finished_at=validated_now,
            )
            self._reservations[reservation_id] = updated
            return updated

    def _new_reservation_id(self) -> str:
        for _ in range(10):
            candidate = secrets.token_urlsafe(24)
            if candidate not in self._reservations:
                return candidate
        raise UsageLedgerError("could not allocate a unique usage reservation ID")

    def _owned_reservation(
        self,
        reservation_id: str,
        owner_id: str,
        session_id: str,
    ) -> UsageReservation:
        reservation = self._reservations.get(reservation_id)
        if reservation is None:
            raise UsageLedgerError("usage reservation does not exist")
        if reservation.owner_id != owner_id or reservation.session_id != session_id:
            raise UsageLedgerError("usage reservation owner or session does not match")
        return reservation

    def _updated_reservation(
        self,
        reservation: UsageReservation,
        *,
        status: ReservationStatus,
        started_at: datetime | None,
        finished_at: datetime | None,
    ) -> UsageReservation:
        payload = reservation.model_dump(mode="python")
        payload.update(
            status=status,
            started_at=started_at,
            finished_at=finished_at,
        )
        try:
            return UsageReservation.model_validate(payload)
        except ValueError as exc:
            raise UsageLedgerError("usage reservation lifecycle is invalid") from exc

    def _charged_reservations(self, provider: Provider) -> list[UsageReservation]:
        return [
            reservation
            for reservation in self._reservations.values()
            if reservation.provider == provider and reservation.status in self._CHARGED_STATUSES
        ]

    def _scope_total(
        self,
        reservations: list[UsageReservation],
        predicate,
    ) -> UsageTotal:
        total: UsageTotal = (0, 0, 0)
        for reservation in reservations:
            if predicate(reservation):
                total = _add_amount(total, reservation.amount)
        return total

    def _would_exceed(
        self,
        request: UsageReservationRequest,
        policy: ProviderUsageLimits,
        *,
        reserved_at: datetime,
    ) -> bool:
        if policy.quota_enforcement == "disabled":
            return False
        reservations = self._charged_reservations(request.provider)
        usage_day = reserved_at.date()
        scope_limits = (
            (
                self._scope_total(
                    reservations,
                    lambda item: (
                        item.owner_id == request.owner_id and item.reserved_at.date() == usage_day
                    ),
                ),
                policy.per_user_day,
            ),
            (
                self._scope_total(
                    reservations,
                    lambda item: (
                        item.owner_id == request.owner_id and item.session_id == request.session_id
                    ),
                ),
                policy.per_session,
            ),
            (
                self._scope_total(
                    reservations,
                    lambda item: item.reserved_at.date() == usage_day,
                ),
                policy.global_day,
            ),
        )
        return any(
            not _within_limit(_add_amount(total, request.amount), limit)
            for total, limit in scope_limits
        )

    def _validate_current_limits(self) -> None:
        for provider, policy in self._policies.items():
            if policy.quota_enforcement == "disabled":
                continue
            per_user_day: dict[tuple[str, date], UsageTotal] = {}
            per_session: dict[tuple[str, str], UsageTotal] = {}
            global_day: dict[date, UsageTotal] = {}
            for reservation in self._charged_reservations(provider):
                usage_day = reservation.reserved_at.date()
                user_day_key = (reservation.owner_id, usage_day)
                session_key = (reservation.owner_id, reservation.session_id)
                per_user_day[user_day_key] = _add_amount(
                    per_user_day.get(user_day_key, (0, 0, 0)),
                    reservation.amount,
                )
                per_session[session_key] = _add_amount(
                    per_session.get(session_key, (0, 0, 0)),
                    reservation.amount,
                )
                global_day[usage_day] = _add_amount(
                    global_day.get(usage_day, (0, 0, 0)),
                    reservation.amount,
                )
            if (
                any(
                    not _within_limit(total, policy.per_user_day) for total in per_user_day.values()
                )
                or any(
                    not _within_limit(total, policy.per_session) for total in per_session.values()
                )
                or any(not _within_limit(total, policy.global_day) for total in global_day.values())
            ):
                raise UsageLedgerError("usage ledger snapshot exceeds an approved limit")
