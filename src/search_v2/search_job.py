from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import queue
import secrets
import sqlite3
import stat
import threading
from typing import Annotated
from typing import Callable
from typing import Iterator
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import TypeAdapter
from pydantic import ValidationError
from pydantic import field_validator
from pydantic import model_validator

from src.search_v2.usage_ledger import Digest
from src.search_v2.usage_ledger import SubjectId


LOCAL_SEARCH_OWNER_ID = "local-user"
JOB_QUEUE_START_WINDOW = timedelta(hours=24)
JOB_RETENTION = timedelta(days=30)

_SCHEMA_VERSION = 1
_INPUT_ERROR_MESSAGE = "Search job input is invalid"
_NOT_FOUND_MESSAGE = "Search job was not found"
_STATE_ERROR_MESSAGE = "Search job state transition is invalid"
_STORAGE_ERROR_MESSAGE = "Search job storage operation failed"
_EXECUTOR_CLOSED_MESSAGE = "Search job executor is closed"
_RECORD_DOMAIN = b"amazon-explorer-local-search-job-v1\x00"

JobLocator = Annotated[
    str,
    StringConstraints(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
]
SearchJobStatus = Literal[
    "queued",
    "running",
    "cancel_requested",
    "succeeded",
    "failed",
    "cancelled",
    "timed_out",
]
SearchJobFailureCode = Literal[
    "execution_failed",
    "queue_start_expired",
    "worker_restarted",
]
_TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "timed_out"}

_OWNER_ADAPTER = TypeAdapter(SubjectId)
_LOCATOR_ADAPTER = TypeAdapter(JobLocator)


class SearchJobError(RuntimeError):
    """Base class for fixed-message local job failures."""


class SearchJobInputError(SearchJobError):
    """A job input is outside the local job contract."""


class SearchJobNotFoundError(SearchJobError):
    """A job is absent or does not belong to the requested owner."""


class SearchJobStateError(SearchJobError):
    """A requested job transition is not valid."""


class SearchJobStorageError(SearchJobError):
    """The local job store could not complete an atomic operation."""


class _SearchJobCancelled(SearchJobError):
    pass


class StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        revalidate_instances="always",
        frozen=True,
    )


def _utc_datetime(value: object, *, field_name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None:
        raise ValueError(f"{field_name} must use UTC")
    try:
        if value.utcoffset() != timedelta(0):
            raise ValueError(f"{field_name} must use UTC")
    except (OverflowError, ValueError):
        raise ValueError(f"{field_name} must use UTC") from None
    return value.astimezone(timezone.utc)


def _time_text(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


class SearchJobSubmission(StrictFrozenContract):
    schema_version: Literal["1.0"]
    owner_id: SubjectId = Field(repr=False)
    binding_sha256: Digest = Field(repr=False)


class SearchJobResult(StrictFrozenContract):
    schema_version: Literal["1.0"]
    result_locator: JobLocator


class SearchJobSnapshot(StrictFrozenContract):
    schema_version: Literal["1.0"]
    locator: JobLocator
    owner_id: SubjectId = Field(repr=False)
    binding_sha256: Digest = Field(repr=False)
    status: SearchJobStatus
    revision: Annotated[int, Field(ge=0)]
    created_at: datetime
    updated_at: datetime
    start_before: datetime
    started_at: datetime | None
    cancel_requested_at: datetime | None
    finished_at: datetime | None
    purge_after: datetime | None
    result_locator: JobLocator | None
    failure_code: SearchJobFailureCode | None

    @field_validator(
        "created_at",
        "updated_at",
        "start_before",
        "started_at",
        "cancel_requested_at",
        "finished_at",
        "purge_after",
    )
    @classmethod
    def validate_timestamp(cls, value: datetime | None, info) -> datetime | None:
        if value is None:
            return None
        return _utc_datetime(value, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_state(self) -> SearchJobSnapshot:
        if self.start_before != self.created_at + JOB_QUEUE_START_WINDOW:
            raise ValueError("job queue start deadline is inconsistent")
        if self.updated_at < self.created_at:
            raise ValueError("job update precedes creation")
        if self.started_at is not None and not (
            self.created_at <= self.started_at < self.start_before
        ):
            raise ValueError("job start time is inconsistent")
        if self.cancel_requested_at is not None:
            earliest = self.started_at if self.started_at is not None else self.created_at
            if self.cancel_requested_at < earliest:
                raise ValueError("job cancellation time is inconsistent")
        if self.finished_at is not None:
            earliest = self.cancel_requested_at or self.started_at or self.created_at
            if self.finished_at < earliest:
                raise ValueError("job finish time is inconsistent")

        if self.status == "queued":
            self._validate_queued()
        elif self.status == "running":
            self._validate_running()
        elif self.status == "cancel_requested":
            self._validate_cancel_requested()
        else:
            self._validate_terminal()
        return self

    def _validate_queued(self) -> None:
        if (
            self.updated_at != self.created_at
            or self.started_at is not None
            or self.cancel_requested_at is not None
            or self.finished_at is not None
            or self.purge_after is not None
            or self.result_locator is not None
            or self.failure_code is not None
        ):
            raise ValueError("queued job contains later state")

    def _validate_running(self) -> None:
        if (
            self.started_at is None
            or self.updated_at != self.started_at
            or self.cancel_requested_at is not None
            or self.finished_at is not None
            or self.purge_after is not None
            or self.result_locator is not None
            or self.failure_code is not None
        ):
            raise ValueError("running job state is inconsistent")

    def _validate_cancel_requested(self) -> None:
        if (
            self.started_at is None
            or self.cancel_requested_at is None
            or self.updated_at != self.cancel_requested_at
            or self.finished_at is not None
            or self.purge_after is not None
            or self.result_locator is not None
            or self.failure_code is not None
        ):
            raise ValueError("cancel-requested job state is inconsistent")

    def _validate_terminal(self) -> None:
        if (
            self.finished_at is None
            or self.updated_at != self.finished_at
            or self.purge_after != self.finished_at + JOB_RETENTION
        ):
            raise ValueError("terminal job timestamps are inconsistent")
        if self.status == "succeeded":
            if (
                self.started_at is None
                or self.cancel_requested_at is not None
                or self.result_locator is None
                or self.failure_code is not None
            ):
                raise ValueError("succeeded job state is inconsistent")
            return
        if self.status == "failed":
            if (
                self.cancel_requested_at is not None
                or self.result_locator is not None
                or self.failure_code not in {"execution_failed", "worker_restarted"}
                or (self.failure_code == "execution_failed" and self.started_at is None)
            ):
                raise ValueError("failed job state is inconsistent")
            return
        if self.status == "cancelled":
            if (
                self.cancel_requested_at is None
                or self.result_locator is not None
                or self.failure_code is not None
            ):
                raise ValueError("cancelled job state is inconsistent")
            return
        if (
            self.status != "timed_out"
            or self.started_at is not None
            or self.cancel_requested_at is not None
            or self.result_locator is not None
            or self.failure_code != "queue_start_expired"
        ):
            raise ValueError("timed-out job state is inconsistent")


class SearchJobEnqueueResult(StrictFrozenContract):
    job: SearchJobSnapshot
    created: bool


def _raise_input_error() -> None:
    raise SearchJobInputError(_INPUT_ERROR_MESSAGE) from None


def _raise_storage_error() -> None:
    raise SearchJobStorageError(_STORAGE_ERROR_MESSAGE) from None


def _validated_submission(pending: object) -> SearchJobSubmission:
    try:
        if type(pending) is not SearchJobSubmission:
            _raise_input_error()
        return SearchJobSubmission.model_validate(pending)
    except SearchJobInputError:
        raise
    except (TypeError, ValidationError, ValueError):
        _raise_input_error()


def _validated_result(result: object) -> SearchJobResult:
    try:
        if type(result) is not SearchJobResult:
            _raise_input_error()
        return SearchJobResult.model_validate(result)
    except SearchJobInputError:
        raise
    except (TypeError, ValidationError, ValueError):
        _raise_input_error()


def _validated_owner(owner_id: object) -> str:
    try:
        return _OWNER_ADAPTER.validate_python(owner_id, strict=True)
    except (TypeError, ValidationError, ValueError):
        _raise_input_error()


def _validated_locator(locator: object) -> str:
    try:
        return _LOCATOR_ADAPTER.validate_python(locator, strict=True)
    except (TypeError, ValidationError, ValueError):
        _raise_input_error()


def _validated_now(now: object) -> datetime:
    try:
        return _utc_datetime(now, field_name="now")
    except (TypeError, ValueError):
        _raise_input_error()


def _new_queued_job(
    pending: SearchJobSubmission,
    *,
    locator: str,
    now: datetime,
) -> SearchJobSnapshot:
    return SearchJobSnapshot(
        schema_version="1.0",
        locator=locator,
        owner_id=pending.owner_id,
        binding_sha256=pending.binding_sha256,
        status="queued",
        revision=0,
        created_at=now,
        updated_at=now,
        start_before=now + JOB_QUEUE_START_WINDOW,
        started_at=None,
        cancel_requested_at=None,
        finished_at=None,
        purge_after=None,
        result_locator=None,
        failure_code=None,
    )


def _updated_job(job: SearchJobSnapshot, **updates: object) -> SearchJobSnapshot:
    payload = job.model_dump(mode="python")
    payload.update(updates)
    payload["revision"] = job.revision + 1
    return SearchJobSnapshot.model_validate(payload)


def _record_sha256(job: SearchJobSnapshot) -> str:
    canonical = json.dumps(
        job.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(_RECORD_DOMAIN + canonical).hexdigest()


def _parse_time(value: object, *, field_name: str) -> datetime | None:
    if value is None:
        return None
    if type(value) is not str:
        _raise_storage_error()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        parsed = _utc_datetime(parsed, field_name=field_name)
    except (TypeError, ValueError):
        _raise_storage_error()
    if _time_text(parsed) != value:
        _raise_storage_error()
    return parsed


_SELECT_COLUMNS = """
    job_id, locator, owner_id, binding_sha256, status, revision,
    created_at, updated_at, start_before, started_at,
    cancel_requested_at, finished_at, purge_after, result_locator,
    failure_code, record_sha256
"""


class SqliteSearchJobRepository:
    """Owner-scoped local job metadata without search or provider payloads."""

    def __init__(self, path: Path) -> None:
        try:
            requested = Path(path)
            if requested.is_symlink():
                _raise_storage_error()
            requested.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            resolved = requested.resolve()
            if resolved.exists():
                mode = resolved.stat(follow_symlinks=False).st_mode
                if not stat.S_ISREG(mode):
                    _raise_storage_error()
                if os.name == "posix" and stat.S_IMODE(mode) & 0o077:
                    _raise_storage_error()
            else:
                flags = os.O_CREAT | os.O_EXCL | os.O_RDWR
                flags |= getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(resolved, flags, 0o600)
                os.close(descriptor)
            self.path = resolved
            self._initialize()
        except SearchJobStorageError:
            raise
        except (OSError, sqlite3.Error, TypeError, ValueError):
            _raise_storage_error()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(
                self.path,
                timeout=5.0,
                isolation_level=None,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout = 5000")
            yield connection
        finally:
            if connection is not None:
                connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in {0, _SCHEMA_VERSION}:
                _raise_storage_error()
            if version == _SCHEMA_VERSION:
                self._validate_schema(connection)
                return

            existing = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type IN ('table', 'index', 'trigger', 'view')
                  AND name NOT LIKE 'sqlite_%'
                LIMIT 1
                """
            ).fetchone()
            if existing is not None:
                _raise_storage_error()

            connection.execute("PRAGMA journal_mode = DELETE")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """
                    CREATE TABLE search_jobs (
                        job_id TEXT PRIMARY KEY NOT NULL,
                        locator TEXT NOT NULL UNIQUE,
                        owner_id TEXT NOT NULL,
                        binding_sha256 TEXT NOT NULL,
                        status TEXT NOT NULL,
                        revision INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        start_before TEXT NOT NULL,
                        started_at TEXT,
                        cancel_requested_at TEXT,
                        finished_at TEXT,
                        purge_after TEXT,
                        result_locator TEXT,
                        failure_code TEXT,
                        record_sha256 TEXT NOT NULL,
                        UNIQUE (owner_id, binding_sha256),
                        CHECK (length(job_id) = 64),
                        CHECK (length(locator) BETWEEN 43 AND 128),
                        CHECK (length(owner_id) BETWEEN 1 AND 128),
                        CHECK (length(binding_sha256) = 64),
                        CHECK (status IN (
                            'queued', 'running', 'cancel_requested',
                            'succeeded', 'failed', 'cancelled', 'timed_out'
                        )),
                        CHECK (revision >= 0),
                        CHECK (result_locator IS NULL OR length(result_locator) BETWEEN 43 AND 128),
                        CHECK (failure_code IS NULL OR failure_code IN (
                            'execution_failed', 'queue_start_expired', 'worker_restarted'
                        )),
                        CHECK (length(record_sha256) = 64)
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX search_jobs_purge
                    ON search_jobs (purge_after)
                    """
                )
                connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
                connection.execute("COMMIT")
            except sqlite3.Error:
                connection.execute("ROLLBACK")
                raise

    def _validate_schema(self, connection: sqlite3.Connection) -> None:
        result = connection.execute("PRAGMA quick_check").fetchone()
        if result is None or result[0] != "ok":
            _raise_storage_error()
        connection.execute(f"SELECT {_SELECT_COLUMNS} FROM search_jobs LIMIT 0")

    @staticmethod
    def _rollback(connection: sqlite3.Connection) -> None:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    def _snapshot_from_row(self, row: sqlite3.Row) -> SearchJobSnapshot:
        try:
            job = SearchJobSnapshot(
                schema_version="1.0",
                locator=row["locator"],
                owner_id=row["owner_id"],
                binding_sha256=row["binding_sha256"],
                status=row["status"],
                revision=row["revision"],
                created_at=_parse_time(row["created_at"], field_name="created_at"),
                updated_at=_parse_time(row["updated_at"], field_name="updated_at"),
                start_before=_parse_time(row["start_before"], field_name="start_before"),
                started_at=_parse_time(row["started_at"], field_name="started_at"),
                cancel_requested_at=_parse_time(
                    row["cancel_requested_at"],
                    field_name="cancel_requested_at",
                ),
                finished_at=_parse_time(row["finished_at"], field_name="finished_at"),
                purge_after=_parse_time(row["purge_after"], field_name="purge_after"),
                result_locator=row["result_locator"],
                failure_code=row["failure_code"],
            )
            if not hmac.compare_digest(_record_sha256(job), row["record_sha256"]):
                _raise_storage_error()
            return job
        except SearchJobStorageError:
            raise
        except (TypeError, ValidationError, ValueError):
            _raise_storage_error()

    def _owned_row(
        self,
        connection: sqlite3.Connection,
        *,
        owner_id: str,
        locator: str,
    ) -> tuple[str, SearchJobSnapshot]:
        row = connection.execute(
            f"SELECT {_SELECT_COLUMNS} FROM search_jobs WHERE owner_id = ? AND locator = ?",
            (owner_id, locator),
        ).fetchone()
        if row is None:
            raise SearchJobNotFoundError(_NOT_FOUND_MESSAGE) from None
        return row["job_id"], self._snapshot_from_row(row)

    def _write_snapshot(
        self,
        connection: sqlite3.Connection,
        *,
        job_id: str,
        previous_revision: int,
        job: SearchJobSnapshot,
    ) -> None:
        cursor = connection.execute(
            """
            UPDATE search_jobs
            SET status = ?, revision = ?, updated_at = ?, started_at = ?,
                cancel_requested_at = ?, finished_at = ?, purge_after = ?,
                result_locator = ?, failure_code = ?, record_sha256 = ?
            WHERE job_id = ? AND revision = ?
            """,
            (
                job.status,
                job.revision,
                _time_text(job.updated_at),
                _time_text(job.started_at) if job.started_at is not None else None,
                (
                    _time_text(job.cancel_requested_at)
                    if job.cancel_requested_at is not None
                    else None
                ),
                _time_text(job.finished_at) if job.finished_at is not None else None,
                _time_text(job.purge_after) if job.purge_after is not None else None,
                job.result_locator,
                job.failure_code,
                _record_sha256(job),
                job_id,
                previous_revision,
            ),
        )
        if cursor.rowcount != 1:
            raise SearchJobStateError(_STATE_ERROR_MESSAGE) from None

    @staticmethod
    def _ensure_time_order(job: SearchJobSnapshot, now: datetime) -> None:
        if now < job.updated_at:
            raise SearchJobStateError(_STATE_ERROR_MESSAGE) from None

    @staticmethod
    def _terminal_job(
        job: SearchJobSnapshot,
        *,
        status: Literal["succeeded", "failed", "cancelled", "timed_out"],
        now: datetime,
        result_locator: str | None = None,
        failure_code: SearchJobFailureCode | None = None,
        cancel_requested_at: datetime | None = None,
    ) -> SearchJobSnapshot:
        return _updated_job(
            job,
            status=status,
            updated_at=now,
            cancel_requested_at=cancel_requested_at,
            finished_at=now,
            purge_after=now + JOB_RETENTION,
            result_locator=result_locator,
            failure_code=failure_code,
        )

    def enqueue(
        self,
        pending: SearchJobSubmission,
        *,
        now: datetime,
    ) -> SearchJobEnqueueResult:
        validated = _validated_submission(pending)
        current_time = _validated_now(now)
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    existing = connection.execute(
                        f"SELECT {_SELECT_COLUMNS} FROM search_jobs "
                        "WHERE owner_id = ? AND binding_sha256 = ?",
                        (validated.owner_id, validated.binding_sha256),
                    ).fetchone()
                    if existing is not None:
                        job = self._snapshot_from_row(existing)
                        connection.execute("COMMIT")
                        return SearchJobEnqueueResult(job=job, created=False)

                    job_id = secrets.token_hex(32)
                    job = _new_queued_job(
                        validated,
                        locator=secrets.token_urlsafe(32),
                        now=current_time,
                    )
                    connection.execute(
                        """
                        INSERT INTO search_jobs (
                            job_id, locator, owner_id, binding_sha256, status,
                            revision, created_at, updated_at, start_before,
                            started_at, cancel_requested_at, finished_at,
                            purge_after, result_locator, failure_code,
                            record_sha256
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL,
                                  NULL, NULL, NULL, ?)
                        """,
                        (
                            job_id,
                            job.locator,
                            job.owner_id,
                            job.binding_sha256,
                            job.status,
                            job.revision,
                            _time_text(job.created_at),
                            _time_text(job.updated_at),
                            _time_text(job.start_before),
                            _record_sha256(job),
                        ),
                    )
                    connection.execute("COMMIT")
                    return SearchJobEnqueueResult(job=job, created=True)
                except (SearchJobError, sqlite3.Error):
                    self._rollback(connection)
                    raise
        except SearchJobError:
            raise
        except (OSError, sqlite3.Error, TypeError, ValidationError, ValueError):
            _raise_storage_error()

    def count(self, *, owner_id: str) -> int:
        validated_owner = _validated_owner(owner_id)
        try:
            with self._connection() as connection:
                return int(
                    connection.execute(
                        "SELECT COUNT(*) FROM search_jobs WHERE owner_id = ?",
                        (validated_owner,),
                    ).fetchone()[0]
                )
        except (OSError, sqlite3.Error, TypeError, ValueError):
            _raise_storage_error()

    def get(
        self,
        *,
        owner_id: str,
        locator: str,
        now: datetime,
    ) -> SearchJobSnapshot:
        validated_owner = _validated_owner(owner_id)
        validated_locator = _validated_locator(locator)
        current_time = _validated_now(now)
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    job_id, job = self._owned_row(
                        connection,
                        owner_id=validated_owner,
                        locator=validated_locator,
                    )
                    self._ensure_time_order(job, current_time)
                    if job.purge_after is not None and current_time >= job.purge_after:
                        raise SearchJobNotFoundError(_NOT_FOUND_MESSAGE) from None
                    if job.status == "queued" and current_time >= job.start_before:
                        expired = self._terminal_job(
                            job,
                            status="timed_out",
                            now=current_time,
                            failure_code="queue_start_expired",
                        )
                        self._write_snapshot(
                            connection,
                            job_id=job_id,
                            previous_revision=job.revision,
                            job=expired,
                        )
                        job = expired
                    connection.execute("COMMIT")
                    return job
                except SearchJobError:
                    self._rollback(connection)
                    raise
        except SearchJobError:
            raise
        except (OSError, sqlite3.Error, TypeError, ValidationError, ValueError):
            _raise_storage_error()

    def claim_for_execution(
        self,
        *,
        owner_id: str,
        locator: str,
        now: datetime,
    ) -> SearchJobSnapshot:
        validated_owner = _validated_owner(owner_id)
        validated_locator = _validated_locator(locator)
        current_time = _validated_now(now)
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    job_id, job = self._owned_row(
                        connection,
                        owner_id=validated_owner,
                        locator=validated_locator,
                    )
                    self._ensure_time_order(job, current_time)
                    if job.status != "queued":
                        connection.execute("COMMIT")
                        return job
                    if current_time >= job.start_before:
                        claimed = self._terminal_job(
                            job,
                            status="timed_out",
                            now=current_time,
                            failure_code="queue_start_expired",
                        )
                    else:
                        claimed = _updated_job(
                            job,
                            status="running",
                            updated_at=current_time,
                            started_at=current_time,
                        )
                    self._write_snapshot(
                        connection,
                        job_id=job_id,
                        previous_revision=job.revision,
                        job=claimed,
                    )
                    connection.execute("COMMIT")
                    return claimed
                except SearchJobError:
                    self._rollback(connection)
                    raise
        except SearchJobError:
            raise
        except (OSError, sqlite3.Error, TypeError, ValidationError, ValueError):
            _raise_storage_error()

    def request_cancel(
        self,
        *,
        owner_id: str,
        locator: str,
        now: datetime,
    ) -> SearchJobSnapshot:
        validated_owner = _validated_owner(owner_id)
        validated_locator = _validated_locator(locator)
        current_time = _validated_now(now)
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    job_id, job = self._owned_row(
                        connection,
                        owner_id=validated_owner,
                        locator=validated_locator,
                    )
                    self._ensure_time_order(job, current_time)
                    if job.status == "queued":
                        changed = self._terminal_job(
                            job,
                            status="cancelled",
                            now=current_time,
                            cancel_requested_at=current_time,
                        )
                    elif job.status == "running":
                        changed = _updated_job(
                            job,
                            status="cancel_requested",
                            updated_at=current_time,
                            cancel_requested_at=current_time,
                        )
                    else:
                        connection.execute("COMMIT")
                        return job
                    self._write_snapshot(
                        connection,
                        job_id=job_id,
                        previous_revision=job.revision,
                        job=changed,
                    )
                    connection.execute("COMMIT")
                    return changed
                except SearchJobError:
                    self._rollback(connection)
                    raise
        except SearchJobError:
            raise
        except (OSError, sqlite3.Error, TypeError, ValidationError, ValueError):
            _raise_storage_error()

    def finish_success(
        self,
        *,
        owner_id: str,
        locator: str,
        result: SearchJobResult,
        now: datetime,
    ) -> SearchJobSnapshot:
        validated_result = _validated_result(result)
        return self._finish(
            owner_id=owner_id,
            locator=locator,
            now=now,
            result=validated_result,
            failure_code=None,
            cancelled=False,
        )

    def finish_failure(
        self,
        *,
        owner_id: str,
        locator: str,
        now: datetime,
    ) -> SearchJobSnapshot:
        return self._finish(
            owner_id=owner_id,
            locator=locator,
            now=now,
            result=None,
            failure_code="execution_failed",
            cancelled=False,
        )

    def finish_cancelled(
        self,
        *,
        owner_id: str,
        locator: str,
        now: datetime,
    ) -> SearchJobSnapshot:
        return self._finish(
            owner_id=owner_id,
            locator=locator,
            now=now,
            result=None,
            failure_code=None,
            cancelled=True,
        )

    def _finish(
        self,
        *,
        owner_id: str,
        locator: str,
        now: datetime,
        result: SearchJobResult | None,
        failure_code: Literal["execution_failed"] | None,
        cancelled: bool,
    ) -> SearchJobSnapshot:
        validated_owner = _validated_owner(owner_id)
        validated_locator = _validated_locator(locator)
        current_time = _validated_now(now)
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    job_id, job = self._owned_row(
                        connection,
                        owner_id=validated_owner,
                        locator=validated_locator,
                    )
                    self._ensure_time_order(job, current_time)
                    if job.status not in {"running", "cancel_requested"}:
                        raise SearchJobStateError(_STATE_ERROR_MESSAGE) from None

                    cancellation_wins = cancelled or job.status == "cancel_requested"
                    if cancellation_wins:
                        cancellation_time = job.cancel_requested_at or current_time
                        finished = self._terminal_job(
                            job,
                            status="cancelled",
                            now=current_time,
                            cancel_requested_at=cancellation_time,
                        )
                    elif result is not None:
                        finished = self._terminal_job(
                            job,
                            status="succeeded",
                            now=current_time,
                            result_locator=result.result_locator,
                        )
                    elif failure_code is not None:
                        finished = self._terminal_job(
                            job,
                            status="failed",
                            now=current_time,
                            failure_code=failure_code,
                        )
                    else:
                        raise SearchJobStateError(_STATE_ERROR_MESSAGE) from None

                    self._write_snapshot(
                        connection,
                        job_id=job_id,
                        previous_revision=job.revision,
                        job=finished,
                    )
                    connection.execute("COMMIT")
                    return finished
                except SearchJobError:
                    self._rollback(connection)
                    raise
        except SearchJobError:
            raise
        except (OSError, sqlite3.Error, TypeError, ValidationError, ValueError):
            _raise_storage_error()

    def recover_interrupted(self, *, now: datetime) -> int:
        current_time = _validated_now(now)
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    rows = connection.execute(
                        f"SELECT {_SELECT_COLUMNS} FROM search_jobs "
                        "WHERE status IN ('queued', 'running', 'cancel_requested') "
                        "ORDER BY created_at, job_id"
                    ).fetchall()
                    for row in rows:
                        job = self._snapshot_from_row(row)
                        self._ensure_time_order(job, current_time)
                        if job.status == "cancel_requested":
                            recovered = self._terminal_job(
                                job,
                                status="cancelled",
                                now=current_time,
                                cancel_requested_at=job.cancel_requested_at,
                            )
                        else:
                            recovered = self._terminal_job(
                                job,
                                status="failed",
                                now=current_time,
                                failure_code="worker_restarted",
                            )
                        self._write_snapshot(
                            connection,
                            job_id=row["job_id"],
                            previous_revision=job.revision,
                            job=recovered,
                        )
                    connection.execute("COMMIT")
                    return len(rows)
                except SearchJobError:
                    self._rollback(connection)
                    raise
        except SearchJobError:
            raise
        except (OSError, sqlite3.Error, TypeError, ValidationError, ValueError):
            _raise_storage_error()

    def purge_expired(self, *, now: datetime) -> int:
        current_time = _validated_now(now)
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    rows = connection.execute(
                        f"SELECT {_SELECT_COLUMNS} FROM search_jobs "
                        "WHERE purge_after IS NOT NULL AND purge_after <= ? "
                        "ORDER BY purge_after, job_id",
                        (_time_text(current_time),),
                    ).fetchall()
                    for row in rows:
                        job = self._snapshot_from_row(row)
                        if job.status not in _TERMINAL_STATUSES:
                            _raise_storage_error()
                    if rows:
                        connection.executemany(
                            "DELETE FROM search_jobs WHERE job_id = ?",
                            ((row["job_id"],) for row in rows),
                        )
                    connection.execute("COMMIT")
                    return len(rows)
                except SearchJobError:
                    self._rollback(connection)
                    raise
        except SearchJobError:
            raise
        except (OSError, sqlite3.Error, TypeError, ValidationError, ValueError):
            _raise_storage_error()


class SearchJobControl:
    """Cooperative cancellation signal for one in-process search callback."""

    __slots__ = ("_cancel_event", "_locator")

    def __init__(self, *, locator: str, cancel_event: threading.Event) -> None:
        self._locator = _validated_locator(locator)
        self._cancel_event = cancel_event

    @property
    def locator(self) -> str:
        return self._locator

    @property
    def cancel_requested(self) -> bool:
        return self._cancel_event.is_set()

    def checkpoint(self) -> None:
        if self.cancel_requested:
            raise _SearchJobCancelled("Search job cancellation requested") from None


SearchJobRunner = Callable[[SearchJobControl], SearchJobResult]
SearchJobClock = Callable[[], datetime]
_STOP = object()


class LocalSearchJobExecutor:
    """One background worker for the fixed local owner."""

    def __init__(
        self,
        repository: SqliteSearchJobRepository,
        *,
        clock: SearchJobClock,
    ) -> None:
        if type(repository) is not SqliteSearchJobRepository or not callable(clock):
            _raise_input_error()
        self._repository = repository
        self._clock = clock
        self._queue: queue.Queue[object] = queue.Queue()
        self._cancel_events: dict[str, threading.Event] = {}
        self._state_lock = threading.Lock()
        self._accepting = True
        self._repository.recover_interrupted(now=self._now())
        self._worker = threading.Thread(
            target=self._run,
            name="local-search-job-worker",
            daemon=True,
        )
        self._worker.start()

    def __enter__(self) -> LocalSearchJobExecutor:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.shutdown()

    def _now(self) -> datetime:
        try:
            return _validated_now(self._clock())
        except SearchJobInputError:
            raise
        except Exception:
            _raise_input_error()

    def submit(
        self,
        *,
        binding_sha256: str,
        runner: SearchJobRunner,
    ) -> SearchJobSnapshot:
        if not callable(runner):
            _raise_input_error()
        try:
            pending = SearchJobSubmission(
                schema_version="1.0",
                owner_id=LOCAL_SEARCH_OWNER_ID,
                binding_sha256=binding_sha256,
            )
        except (TypeError, ValidationError, ValueError):
            _raise_input_error()

        with self._state_lock:
            if not self._accepting:
                raise SearchJobStateError(_EXECUTOR_CLOSED_MESSAGE) from None
            enqueued = self._repository.enqueue(pending, now=self._now())
            if enqueued.created:
                cancel_event = threading.Event()
                self._cancel_events[enqueued.job.locator] = cancel_event
                self._queue.put((enqueued.job.locator, runner, cancel_event))
            return enqueued.job

    def get(self, locator: str) -> SearchJobSnapshot:
        return self._repository.get(
            owner_id=LOCAL_SEARCH_OWNER_ID,
            locator=locator,
            now=self._now(),
        )

    def cancel(self, locator: str) -> SearchJobSnapshot:
        cancelled = self._repository.request_cancel(
            owner_id=LOCAL_SEARCH_OWNER_ID,
            locator=locator,
            now=self._now(),
        )
        with self._state_lock:
            cancel_event = self._cancel_events.get(cancelled.locator)
            if cancel_event is not None:
                cancel_event.set()
        return cancelled

    def wait_until_idle(self) -> None:
        self._queue.join()

    def shutdown(self) -> None:
        with self._state_lock:
            if not self._accepting:
                return
            self._accepting = False
            self._queue.put(_STOP)
        self._worker.join()

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is _STOP:
                    return
                locator, runner, cancel_event = item
                self._run_one(locator, runner, cancel_event)
            finally:
                self._queue.task_done()

    def _run_one(
        self,
        locator: str,
        runner: SearchJobRunner,
        cancel_event: threading.Event,
    ) -> None:
        try:
            claimed = self._repository.claim_for_execution(
                owner_id=LOCAL_SEARCH_OWNER_ID,
                locator=locator,
                now=self._now(),
            )
            if claimed.status != "running":
                return

            control = SearchJobControl(locator=locator, cancel_event=cancel_event)
            try:
                control.checkpoint()
                result = runner(control)
                validated_result = _validated_result(result)
            except _SearchJobCancelled:
                self._repository.finish_cancelled(
                    owner_id=LOCAL_SEARCH_OWNER_ID,
                    locator=locator,
                    now=self._now(),
                )
            except Exception:
                self._repository.finish_failure(
                    owner_id=LOCAL_SEARCH_OWNER_ID,
                    locator=locator,
                    now=self._now(),
                )
            else:
                self._repository.finish_success(
                    owner_id=LOCAL_SEARCH_OWNER_ID,
                    locator=locator,
                    result=validated_result,
                    now=self._now(),
                )
        except SearchJobError:
            pass
        finally:
            with self._state_lock:
                self._cancel_events.pop(locator, None)
