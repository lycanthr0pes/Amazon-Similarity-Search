"""Persistent single-use human approval for counterfactual reference sets."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
from typing import Annotated
from typing import Callable
from typing import Iterator
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import ValidationError
from pydantic import field_validator
from pydantic import model_validator

from src.search_v2.usage_ledger import Digest
from src.search_v2.usage_ledger import SubjectId
from src.search_v2.usage_ledger import UsageReservation


COUNTERFACTUAL_APPROVAL_TTL = timedelta(minutes=15)
_SCHEMA_VERSION = 1
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43,128}$")
_TOKEN_DOMAIN = b"amazon-explorer-counterfactual-approval-token-v1\x00"
_REVIEW_DOMAIN = b"amazon-explorer-counterfactual-approval-review-v1\x00"
_RECEIPT_DOMAIN = b"amazon-explorer-counterfactual-approval-receipt-v1\x00"
_INVALID_INPUT_MESSAGE = "Counterfactual approval input is invalid"
_CONFLICT_MESSAGE = "Counterfactual approval conflicts with persistent state"
_CONSUMED_MESSAGE = "Counterfactual approval has already been consumed"
_STORAGE_MESSAGE = "Counterfactual approval storage operation failed"

ApprovalId = Annotated[
    str,
    StringConstraints(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
]


class CounterfactualApprovalError(RuntimeError):
    """Base class for fixed-message counterfactual approval failures."""


class CounterfactualApprovalInputError(CounterfactualApprovalError):
    pass


class CounterfactualApprovalConflictError(CounterfactualApprovalError):
    pass


class CounterfactualApprovalStorageError(CounterfactualApprovalError):
    pass


class _StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


def _utc_datetime(value: datetime, *, field_name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must use UTC")
    return value.astimezone(timezone.utc)


def _time_text(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _token_sha256(token: object) -> str:
    if type(token) is not str or _TOKEN_PATTERN.fullmatch(token) is None:
        raise CounterfactualApprovalInputError(_INVALID_INPUT_MESSAGE) from None
    return hashlib.sha256(_TOKEN_DOMAIN + token.encode("ascii")).hexdigest()


class CounterfactualReferenceApprovalReview(_StrictFrozenContract):
    schema_version: Literal["5.0"]
    approval_id: ApprovalId
    owner_id: SubjectId = Field(repr=False)
    session_id: SubjectId = Field(repr=False)
    condition_set_sha256: Digest
    reference_set_sha256: Digest
    request_metadata_sha256: Digest
    usage_reservation_id: Annotated[
        str,
        StringConstraints(min_length=32, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
    ]
    usage_policy_sha256: Digest
    usage_binding_sha256: Digest
    call_count: Annotated[int, Field(ge=2, le=4)]
    issued_at: datetime
    expires_at: datetime

    @field_validator("issued_at", "expires_at")
    @classmethod
    def validate_timestamp(cls, value: datetime, info) -> datetime:
        return _utc_datetime(value, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_lifetime(self) -> CounterfactualReferenceApprovalReview:
        if self.expires_at != self.issued_at + COUNTERFACTUAL_APPROVAL_TTL:
            raise ValueError("counterfactual approval lifetime is invalid")
        return self


class CounterfactualReferenceApprovalReceipt(_StrictFrozenContract):
    schema_version: Literal["5.0"]
    approval_id: ApprovalId
    owner_id: SubjectId = Field(repr=False)
    session_id: SubjectId = Field(repr=False)
    condition_set_sha256: Digest
    reference_set_sha256: Digest
    request_metadata_sha256: Digest
    usage_reservation_id: Annotated[
        str,
        StringConstraints(min_length=32, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
    ]
    usage_policy_sha256: Digest
    usage_binding_sha256: Digest
    call_count: Annotated[int, Field(ge=2, le=4)]
    approval_basis: Literal["explicit_human_confirmation"]
    consumed_at: datetime

    @field_validator("consumed_at")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _utc_datetime(value, field_name="consumed_at")


@dataclass(frozen=True, slots=True, repr=False)
class IssuedCounterfactualReferenceApproval:
    review: CounterfactualReferenceApprovalReview
    token: str


def counterfactual_approval_review_sha256(
    review: CounterfactualReferenceApprovalReview,
) -> str:
    try:
        validated = CounterfactualReferenceApprovalReview.model_validate(review)
        payload = json.dumps(
            validated.model_dump(mode="json"),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(_REVIEW_DOMAIN + payload).hexdigest()
    except (TypeError, ValueError, ValidationError) as exc:
        raise CounterfactualApprovalInputError(_INVALID_INPUT_MESSAGE) from exc


def counterfactual_approval_receipt_sha256(
    receipt: CounterfactualReferenceApprovalReceipt,
) -> str:
    try:
        validated = CounterfactualReferenceApprovalReceipt.model_validate(receipt)
        payload = json.dumps(
            validated.model_dump(mode="json"),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(_RECEIPT_DOMAIN + payload).hexdigest()
    except (TypeError, ValueError, ValidationError) as exc:
        raise CounterfactualApprovalInputError(_INVALID_INPUT_MESSAGE) from exc


class SqliteCounterfactualApprovalRepository:
    """A separate, persistent schema that atomically consumes approval tokens."""

    def __init__(self, path: Path) -> None:
        try:
            requested = Path(path)
            if requested.is_symlink():
                raise CounterfactualApprovalStorageError(_STORAGE_MESSAGE)
            requested.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            resolved = requested.resolve()
            if resolved.exists():
                mode = resolved.stat(follow_symlinks=False).st_mode
                if not stat.S_ISREG(mode) or (os.name == "posix" and stat.S_IMODE(mode) & 0o077):
                    raise CounterfactualApprovalStorageError(_STORAGE_MESSAGE)
            else:
                flags = os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(resolved, flags, 0o600)
                os.close(descriptor)
            self.path = resolved
            self._initialize()
        except CounterfactualApprovalError:
            raise
        except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
            raise CounterfactualApprovalStorageError(_STORAGE_MESSAGE) from exc

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
            connection.row_factory = sqlite3.Row
            yield connection
        finally:
            if connection is not None:
                connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in {0, _SCHEMA_VERSION}:
                raise CounterfactualApprovalStorageError(_STORAGE_MESSAGE)
            if version == _SCHEMA_VERSION:
                self._validate_schema(connection)
                return
            existing = connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type IN ('table', 'index', 'trigger', 'view')
                  AND name NOT LIKE 'sqlite_%'
                LIMIT 1
                """
            ).fetchone()
            if existing is not None:
                raise CounterfactualApprovalStorageError(_STORAGE_MESSAGE)
            connection.execute("PRAGMA journal_mode = DELETE")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """
                    CREATE TABLE counterfactual_approvals (
                        approval_id TEXT PRIMARY KEY NOT NULL,
                        owner_id TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        review_json TEXT NOT NULL,
                        review_sha256 TEXT NOT NULL,
                        token_sha256 TEXT NOT NULL UNIQUE,
                        issued_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        consumed_at TEXT,
                        UNIQUE (owner_id, session_id, review_sha256),
                        CHECK (length(approval_id) >= 43),
                        CHECK (length(review_sha256) = 64),
                        CHECK (length(token_sha256) = 64),
                        CHECK (expires_at > issued_at)
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX counterfactual_approvals_expiry
                    ON counterfactual_approvals (expires_at)
                    """
                )
                connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
                connection.execute("COMMIT")
            except sqlite3.Error:
                connection.execute("ROLLBACK")
                raise

    def _validate_schema(self, connection: sqlite3.Connection) -> None:
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise CounterfactualApprovalStorageError(_STORAGE_MESSAGE)
        connection.execute(
            """
            SELECT approval_id, owner_id, session_id, review_json, review_sha256,
                   token_sha256, issued_at, expires_at, consumed_at
            FROM counterfactual_approvals LIMIT 0
            """
        )

    @staticmethod
    def _rollback(connection: sqlite3.Connection) -> None:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    def issue(
        self,
        *,
        owner_id: str,
        session_id: str,
        condition_set_sha256: str,
        reference_set_sha256: str,
        request_metadata_sha256: str,
        usage_reservation: UsageReservation,
        now: datetime,
        reference_image_reservation: UsageReservation | None = None,
        token_factory: Callable[[], str] = lambda: secrets.token_urlsafe(32),
    ) -> IssuedCounterfactualReferenceApproval:
        try:
            reservation = UsageReservation.model_validate(usage_reservation)
            issued_at = _utc_datetime(now, field_name="now")
            call_count = reservation.amount.calls
            if reference_image_reservation is None:
                if reservation.operation != "counterfactual_reference_set":
                    raise ValueError("counterfactual approval requires its initial reference usage")
            else:
                reference = UsageReservation.model_validate(reference_image_reservation)
                if (
                    reservation.operation != "counterfactual_images"
                    or not 1 <= reservation.amount.calls <= 3
                    or reference.status != "succeeded"
                    or reference.provider != "cloudflare"
                    or reference.operation != "reference_image"
                    or reference.amount.calls != 1
                    or reference.amount.tokens != 0
                    or reference.owner_id != owner_id
                    or reference.session_id != session_id
                    or reference.usage_policy_sha256 != reservation.usage_policy_sha256
                    or reference.binding_sha256 != reservation.binding_sha256
                    or reference.request.pricing_policy_sha256
                    != reservation.request.pricing_policy_sha256
                    or reference.reservation_id == reservation.reservation_id
                    or reference.finished_at is None
                    or reservation.started_at is None
                    or reference.finished_at > reservation.started_at
                ):
                    raise ValueError("counterfactual split usage binding is invalid")
                call_count += reference.amount.calls
            if (
                reservation.status != "succeeded"
                or reservation.provider != "cloudflare"
                or reservation.owner_id != owner_id
                or reservation.session_id != session_id
                or not 2 <= call_count <= 4
                or reservation.amount.tokens != 0
                or reservation.finished_at is None
                or reservation.finished_at > issued_at
                or not callable(token_factory)
            ):
                raise ValueError("counterfactual approval usage binding is invalid")
            token = token_factory()
            token_digest = _token_sha256(token)
            approval_id = secrets.token_urlsafe(32)
            review = CounterfactualReferenceApprovalReview(
                schema_version="5.0",
                approval_id=approval_id,
                owner_id=owner_id,
                session_id=session_id,
                condition_set_sha256=condition_set_sha256,
                reference_set_sha256=reference_set_sha256,
                request_metadata_sha256=request_metadata_sha256,
                usage_reservation_id=reservation.reservation_id,
                usage_policy_sha256=reservation.usage_policy_sha256,
                usage_binding_sha256=reservation.binding_sha256,
                call_count=call_count,
                issued_at=issued_at,
                expires_at=issued_at + COUNTERFACTUAL_APPROVAL_TTL,
            )
            review_json = review.model_dump_json()
            review_digest = counterfactual_approval_review_sha256(review)
        except CounterfactualApprovalError:
            raise
        except (TypeError, ValueError, ValidationError) as exc:
            raise CounterfactualApprovalInputError(_INVALID_INPUT_MESSAGE) from exc

        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    connection.execute(
                        """
                        INSERT INTO counterfactual_approvals (
                            approval_id, owner_id, session_id, review_json,
                            review_sha256, token_sha256, issued_at, expires_at,
                            consumed_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                        """,
                        (
                            review.approval_id,
                            review.owner_id,
                            review.session_id,
                            review_json,
                            review_digest,
                            token_digest,
                            _time_text(review.issued_at),
                            _time_text(review.expires_at),
                        ),
                    )
                    connection.execute("COMMIT")
                except sqlite3.IntegrityError as exc:
                    self._rollback(connection)
                    raise CounterfactualApprovalConflictError(_CONFLICT_MESSAGE) from exc
                except sqlite3.Error:
                    self._rollback(connection)
                    raise
            return IssuedCounterfactualReferenceApproval(review=review, token=token)
        except CounterfactualApprovalError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise CounterfactualApprovalStorageError(_STORAGE_MESSAGE) from exc

    def consume(
        self,
        *,
        review: CounterfactualReferenceApprovalReview,
        token: str,
        human_confirmed: Literal[True],
        now: datetime,
    ) -> CounterfactualReferenceApprovalReceipt:
        try:
            validated = CounterfactualReferenceApprovalReview.model_validate(review)
            consumed_at = _utc_datetime(now, field_name="now")
            token_digest = _token_sha256(token)
            review_digest = counterfactual_approval_review_sha256(validated)
            if (
                human_confirmed is not True
                or not validated.issued_at <= consumed_at < validated.expires_at
            ):
                raise CounterfactualApprovalConflictError(_CONFLICT_MESSAGE)
        except CounterfactualApprovalError:
            raise
        except (TypeError, ValueError, ValidationError) as exc:
            raise CounterfactualApprovalInputError(_INVALID_INPUT_MESSAGE) from exc

        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT owner_id, session_id, review_json, review_sha256,
                           token_sha256, consumed_at
                    FROM counterfactual_approvals
                    WHERE approval_id = ?
                    """,
                    (validated.approval_id,),
                ).fetchone()
                if row is None:
                    self._rollback(connection)
                    raise CounterfactualApprovalConflictError(_CONFLICT_MESSAGE)
                if row["consumed_at"] is not None:
                    self._rollback(connection)
                    raise CounterfactualApprovalConflictError(_CONSUMED_MESSAGE)
                persisted = CounterfactualReferenceApprovalReview.model_validate_json(
                    row["review_json"], strict=True
                )
                if (
                    persisted != validated
                    or row["owner_id"] != validated.owner_id
                    or row["session_id"] != validated.session_id
                    or not hmac.compare_digest(row["review_sha256"], review_digest)
                    or not hmac.compare_digest(row["token_sha256"], token_digest)
                ):
                    self._rollback(connection)
                    raise CounterfactualApprovalConflictError(_CONFLICT_MESSAGE)
                updated = connection.execute(
                    """
                    UPDATE counterfactual_approvals SET consumed_at = ?
                    WHERE approval_id = ? AND consumed_at IS NULL
                    """,
                    (_time_text(consumed_at), validated.approval_id),
                ).rowcount
                if updated != 1:
                    self._rollback(connection)
                    raise CounterfactualApprovalConflictError(_CONSUMED_MESSAGE)
                connection.execute("COMMIT")
            return CounterfactualReferenceApprovalReceipt(
                schema_version="5.0",
                approval_id=validated.approval_id,
                owner_id=validated.owner_id,
                session_id=validated.session_id,
                condition_set_sha256=validated.condition_set_sha256,
                reference_set_sha256=validated.reference_set_sha256,
                request_metadata_sha256=validated.request_metadata_sha256,
                usage_reservation_id=validated.usage_reservation_id,
                usage_policy_sha256=validated.usage_policy_sha256,
                usage_binding_sha256=validated.usage_binding_sha256,
                call_count=validated.call_count,
                approval_basis="explicit_human_confirmation",
                consumed_at=consumed_at,
            )
        except CounterfactualApprovalError:
            raise
        except (OSError, sqlite3.Error, TypeError, ValueError, ValidationError) as exc:
            raise CounterfactualApprovalStorageError(_STORAGE_MESSAGE) from exc
