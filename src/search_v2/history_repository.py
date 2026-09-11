from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import hashlib
import hmac
from io import BytesIO
import json
import os
from pathlib import Path
import secrets
import sqlite3
import stat
from typing import Annotated
from typing import Iterator
from typing import Literal
from urllib.parse import urlsplit
import unicodedata

from PIL import Image
from PIL import UnidentifiedImageError
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import TypeAdapter
from pydantic import ValidationError
from pydantic import field_validator
from pydantic import model_validator

from src.search_v2.cloudflare_request import IMAGE_ANGLES
from src.search_v2.cloudflare_request import ImageAngle
from src.search_v2.usage_ledger import Digest
from src.search_v2.usage_ledger import SubjectId


HISTORY_RETENTION_DAYS = 30
MAX_HISTORY_PRODUCTS = 48
MAX_HISTORY_IMAGE_BYTES = 2 * 1024 * 1024

_SCHEMA_VERSION = 2
_INVALID_INPUT_MESSAGE = "Search history input is invalid"
_CONFLICT_MESSAGE = "Search history completion conflicts"
_NOT_FOUND_MESSAGE = "Search history was not found"
_STORAGE_ERROR_MESSAGE = "Search history storage operation failed"
_PAYLOAD_DOMAIN = b"amazon-explorer-search-history-v2\x00"

HistoryLocator = Annotated[
    str,
    StringConstraints(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
]
DisplayText = Annotated[str, StringConstraints(min_length=1, max_length=500)]
DisplayTextItems = Annotated[tuple[DisplayText, ...], Field(max_length=128)]
HttpsUrl = Annotated[str, StringConstraints(min_length=1, max_length=2_048)]

_OWNER_ADAPTER = TypeAdapter(SubjectId)
_LOCATOR_ADAPTER = TypeAdapter(HistoryLocator)


class SearchHistoryError(RuntimeError):
    """Base class for fixed-message history failures."""


class HistoryInputError(SearchHistoryError):
    """A write or operation argument is outside the history contract."""


class HistoryConflictError(SearchHistoryError):
    """A completion key already exists with different immutable content."""


class HistoryNotFoundError(SearchHistoryError):
    """A history record is absent, expired, or owned by another subject."""


class HistoryStorageError(SearchHistoryError):
    """The local history store could not complete an atomic operation."""


class StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        revalidate_instances="always",
        frozen=True,
    )


def _raise_input_error() -> None:
    raise HistoryInputError(_INVALID_INPUT_MESSAGE) from None


def _raise_storage_error() -> None:
    raise HistoryStorageError(_STORAGE_ERROR_MESSAGE) from None


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


def _contains_forbidden_control(value: str) -> bool:
    return any(
        unicodedata.category(character).startswith("C") and not character.isspace()
        for character in value
    )


def _validate_display_text(value: str) -> str:
    if value != value.strip() or _contains_forbidden_control(value):
        raise ValueError("history display text is invalid")
    return value


def _validate_https_url(value: str | None, *, amazon_product: bool) -> str | None:
    if value is None:
        return None
    try:
        value.encode("ascii")
        parsed = urlsplit(value)
        port = parsed.port
    except (UnicodeEncodeError, ValueError):
        raise ValueError("history URL is invalid") from None
    hostname = parsed.hostname
    if (
        parsed.scheme != "https"
        or hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.fragment
    ):
        raise ValueError("history URL is invalid")
    normalized_hostname = hostname.casefold()
    if normalized_hostname.endswith(".") or any(
        not label for label in normalized_hostname.split(".")
    ):
        raise ValueError("history URL is invalid")
    if amazon_product and not (
        normalized_hostname == "amazon.co.jp" or normalized_hostname.endswith(".amazon.co.jp")
    ):
        raise ValueError("history product URL is invalid")
    return value


class HistoryConditionSnapshot(StrictFrozenContract):
    schema_version: Literal["2.0"]
    product_type: DisplayText
    conditions: DisplayTextItems
    price_summary: DisplayText | None

    @field_validator("product_type", "price_summary")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_display_text(value)

    @field_validator("conditions")
    @classmethod
    def validate_conditions(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("history conditions must be unique")
        return tuple(_validate_display_text(value) for value in values)


class HistoryProductView(StrictFrozenContract):
    schema_version: Literal["2.0"]
    rank: Annotated[int, Field(ge=1, le=MAX_HISTORY_PRODUCTS)]
    title: DisplayText = Field(repr=False)
    image_url: HttpsUrl | None = Field(repr=False)
    price_jpy: Annotated[int, Field(gt=0, le=1_000_000_000)] | None
    description: Annotated[str, StringConstraints(min_length=1, max_length=4_000)] | None = Field(
        repr=False
    )
    product_url: HttpsUrl | None = Field(repr=False)
    required_status: Literal["confirmed", "uncertain", "contradicted"]
    match_summary: DisplayText
    matching_points: DisplayTextItems
    unverified_points: DisplayTextItems
    caution_points: DisplayTextItems
    image_comparison_note: DisplayText | None

    @field_validator("title", "description", "match_summary", "image_comparison_note")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_display_text(value)

    @field_validator("matching_points", "unverified_points", "caution_points")
    @classmethod
    def validate_points(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("history product points must be unique")
        return tuple(_validate_display_text(value) for value in values)

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, value: str | None) -> str | None:
        return _validate_https_url(value, amazon_product=False)

    @field_validator("product_url")
    @classmethod
    def validate_product_url(cls, value: str | None) -> str | None:
        return _validate_https_url(value, amazon_product=True)


class HistoryReferenceImageWrite(StrictFrozenContract):
    schema_version: Literal["2.0"]
    angle: ImageAngle
    content_type: Literal["image/png"]
    sha256: Digest
    byte_length: Annotated[int, Field(gt=0, le=MAX_HISTORY_IMAGE_BYTES)]
    width: Literal[512]
    height: Literal[512]
    body: bytes = Field(exclude=True, repr=False)

    @model_validator(mode="after")
    def validate_body(self) -> HistoryReferenceImageWrite:
        if type(self.body) is not bytes or len(self.body) != self.byte_length:
            raise ValueError("history image byte length does not match")
        if not hmac.compare_digest(hashlib.sha256(self.body).hexdigest(), self.sha256):
            raise ValueError("history image digest does not match")
        try:
            with Image.open(BytesIO(self.body)) as image:
                if (
                    image.format != "PNG"
                    or image.size != (self.width, self.height)
                    or getattr(image, "n_frames", 1) != 1
                ):
                    raise ValueError("history image metadata does not match")
                image.load()
        except (OSError, UnidentifiedImageError):
            raise ValueError("history image body is invalid") from None
        return self


class SearchHistoryWrite(StrictFrozenContract):
    schema_version: Literal["2.0", "3.0"]
    owner_id: SubjectId = Field(repr=False)
    completion_key: Digest = Field(repr=False)
    completed_at: datetime
    summary: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    source_text: Annotated[str, StringConstraints(min_length=1, max_length=2_000)] = Field(
        repr=False
    )
    condition_snapshot: HistoryConditionSnapshot
    reference_image_mode: Literal["off", "on"]
    reference_images: Annotated[
        tuple[HistoryReferenceImageWrite, ...],
        Field(max_length=4, exclude=True, repr=False),
    ]
    ranking_profile_id: Literal["typed-ranking-v4"]
    candidate_limit: Literal[24, 48]
    outcome: Literal["results", "empty"]
    result_snapshot: Annotated[
        tuple[HistoryProductView, ...],
        Field(max_length=MAX_HISTORY_PRODUCTS, repr=False),
    ]

    @field_validator("completed_at")
    @classmethod
    def validate_completed_at(cls, value: datetime) -> datetime:
        return _utc_datetime(value, field_name="history completion time")

    @field_validator("summary", "source_text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _validate_display_text(value)

    @model_validator(mode="after")
    def validate_snapshot(self) -> SearchHistoryWrite:
        if self.reference_image_mode == "off" and self.reference_images:
            raise ValueError("image-off history must not contain reference images")
        if self.reference_image_mode == "on" and tuple(
            image.angle for image in self.reference_images
        ) != (("front_three_quarter",) if self.schema_version == "3.0" else IMAGE_ANGLES):
            raise ValueError("image-on history has invalid references for its schema")
        if self.outcome == "empty" and self.result_snapshot:
            raise ValueError("empty history must not contain products")
        if self.outcome == "results" and not self.result_snapshot:
            raise ValueError("results history requires products")
        if len(self.result_snapshot) > self.candidate_limit:
            raise ValueError("history results exceed the candidate limit")
        expected_ranks = tuple(range(1, len(self.result_snapshot) + 1))
        if tuple(product.rank for product in self.result_snapshot) != expected_ranks:
            raise ValueError("history product ranks must be contiguous")
        return self


class HistoryReferenceImageRef(StrictFrozenContract):
    schema_version: Literal["2.0"]
    locator: HistoryLocator
    angle: ImageAngle
    content_type: Literal["image/png"]
    width: Literal[512]
    height: Literal[512]


class HistoryListItem(StrictFrozenContract):
    schema_version: Literal["2.0"]
    locator: HistoryLocator
    completed_at: datetime
    expires_at: datetime
    summary: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    price_summary: DisplayText | None
    reference_image_mode: Literal["off", "on"]
    ranking_profile_id: Literal["typed-ranking-v4"]
    compared_count: Annotated[int, Field(ge=0, le=MAX_HISTORY_PRODUCTS)]
    outcome: Literal["results", "empty"]

    @field_validator("completed_at", "expires_at")
    @classmethod
    def validate_timestamp(cls, value: datetime, info) -> datetime:
        return _utc_datetime(value, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_summary(self) -> HistoryListItem:
        if self.expires_at != self.completed_at + timedelta(days=HISTORY_RETENTION_DAYS):
            raise ValueError("history expiry is inconsistent")
        if (self.outcome == "empty") != (self.compared_count == 0):
            raise ValueError("history outcome and product count are inconsistent")
        return self


class HistoryDetail(StrictFrozenContract):
    schema_version: Literal["2.0", "3.0"]
    locator: HistoryLocator
    completed_at: datetime
    expires_at: datetime
    summary: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    source_text: Annotated[str, StringConstraints(min_length=1, max_length=2_000)] = Field(
        repr=False
    )
    condition_snapshot: HistoryConditionSnapshot
    reference_image_mode: Literal["off", "on"]
    reference_images: Annotated[tuple[HistoryReferenceImageRef, ...], Field(max_length=4)]
    ranking_profile_id: Literal["typed-ranking-v4"]
    candidate_limit: Literal[24, 48]
    compared_count: Annotated[int, Field(ge=0, le=MAX_HISTORY_PRODUCTS)]
    outcome: Literal["results", "empty"]
    result_snapshot: Annotated[
        tuple[HistoryProductView, ...],
        Field(max_length=MAX_HISTORY_PRODUCTS, repr=False),
    ]

    @field_validator("completed_at", "expires_at")
    @classmethod
    def validate_timestamp(cls, value: datetime, info) -> datetime:
        return _utc_datetime(value, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_detail(self) -> HistoryDetail:
        if self.expires_at != self.completed_at + timedelta(days=HISTORY_RETENTION_DAYS):
            raise ValueError("history expiry is inconsistent")
        if self.compared_count != len(self.result_snapshot):
            raise ValueError("history product count is inconsistent")
        if (self.outcome == "empty") != (self.compared_count == 0):
            raise ValueError("history outcome and product count are inconsistent")
        if self.reference_image_mode == "off" and self.reference_images:
            raise ValueError("image-off history must not contain image references")
        if self.reference_image_mode == "on" and tuple(
            image.angle for image in self.reference_images
        ) != (("front_three_quarter",) if self.schema_version == "3.0" else IMAGE_ANGLES):
            raise ValueError("image-on history has invalid references for its schema")
        if tuple(product.rank for product in self.result_snapshot) != tuple(
            range(1, self.compared_count + 1)
        ):
            raise ValueError("history product ranks are inconsistent")
        return self


class HistoryImage(StrictFrozenContract):
    schema_version: Literal["2.0"]
    locator: HistoryLocator
    angle: ImageAngle
    content_type: Literal["image/png"]
    width: Literal[512]
    height: Literal[512]
    body: bytes = Field(exclude=True, repr=False)


def _validated_pending(pending: object) -> SearchHistoryWrite:
    try:
        return SearchHistoryWrite.model_validate(pending)
    except (TypeError, ValidationError, ValueError):
        _raise_input_error()


def _validated_now(now: object) -> datetime:
    try:
        return _utc_datetime(now, field_name="now")
    except (TypeError, ValueError):
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


def _payload_sha256(pending: SearchHistoryWrite) -> str:
    payload = pending.model_dump(mode="json")
    payload["reference_images"] = [
        {
            "schema_version": image.schema_version,
            "angle": image.angle,
            "content_type": image.content_type,
            "sha256": image.sha256,
            "byte_length": image.byte_length,
            "width": image.width,
            "height": image.height,
        }
        for image in pending.reference_images
    ]
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(_PAYLOAD_DOMAIN + canonical).hexdigest()


def _detail_json(detail: HistoryDetail) -> str:
    return json.dumps(
        detail.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _new_detail(
    pending: SearchHistoryWrite,
    *,
    locator: str,
    expires_at: datetime,
    image_refs: tuple[HistoryReferenceImageRef, ...],
) -> HistoryDetail:
    return HistoryDetail(
        schema_version=pending.schema_version,
        locator=locator,
        completed_at=pending.completed_at,
        expires_at=expires_at,
        summary=pending.summary,
        source_text=pending.source_text,
        condition_snapshot=pending.condition_snapshot,
        reference_image_mode=pending.reference_image_mode,
        reference_images=image_refs,
        ranking_profile_id=pending.ranking_profile_id,
        candidate_limit=pending.candidate_limit,
        compared_count=len(pending.result_snapshot),
        outcome=pending.outcome,
        result_snapshot=pending.result_snapshot,
    )


def _list_item(detail: HistoryDetail) -> HistoryListItem:
    return HistoryListItem(
        schema_version="2.0",
        locator=detail.locator,
        completed_at=detail.completed_at,
        expires_at=detail.expires_at,
        summary=detail.summary,
        price_summary=detail.condition_snapshot.price_summary,
        reference_image_mode=detail.reference_image_mode,
        ranking_profile_id=detail.ranking_profile_id,
        compared_count=detail.compared_count,
        outcome=detail.outcome,
    )


class SqliteSearchHistoryRepository:
    """Persistent, owner-scoped local search history without provider calls."""

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
        except HistoryStorageError:
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
            connection.execute("PRAGMA foreign_keys = ON")
            if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
                raise sqlite3.DatabaseError("foreign keys are unavailable")
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
                    CREATE TABLE search_history (
                        history_id TEXT PRIMARY KEY NOT NULL,
                        locator TEXT NOT NULL UNIQUE,
                        owner_id TEXT NOT NULL,
                        completion_key TEXT NOT NULL,
                        completed_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        payload_sha256 TEXT NOT NULL,
                        detail_json TEXT NOT NULL,
                        detail_sha256 TEXT NOT NULL,
                        UNIQUE (owner_id, completion_key),
                        CHECK (length(history_id) = 64),
                        CHECK (length(locator) >= 43),
                        CHECK (length(owner_id) BETWEEN 1 AND 128),
                        CHECK (length(completion_key) = 64),
                        CHECK (length(payload_sha256) = 64),
                        CHECK (length(detail_sha256) = 64),
                        CHECK (expires_at > completed_at)
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX search_history_owner_completed
                    ON search_history (owner_id, completed_at DESC, history_id DESC)
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX search_history_expiry
                    ON search_history (expires_at)
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE history_reference_images (
                        history_id TEXT NOT NULL,
                        position INTEGER NOT NULL,
                        locator TEXT NOT NULL UNIQUE,
                        angle TEXT NOT NULL,
                        content_type TEXT NOT NULL,
                        sha256 TEXT NOT NULL,
                        byte_length INTEGER NOT NULL,
                        width INTEGER NOT NULL,
                        height INTEGER NOT NULL,
                        body BLOB NOT NULL,
                        PRIMARY KEY (history_id, position),
                        UNIQUE (history_id, angle),
                        FOREIGN KEY (history_id)
                            REFERENCES search_history(history_id)
                            ON DELETE CASCADE,
                        CHECK (position BETWEEN 0 AND 3),
                        CHECK (angle IN (
                            'front_three_quarter',
                            'left_side',
                            'right_side',
                            'rear_three_quarter'
                        )),
                        CHECK (content_type = 'image/png'),
                        CHECK (length(sha256) = 64),
                        CHECK (byte_length BETWEEN 1 AND 2097152),
                        CHECK (width = 512),
                        CHECK (height = 512),
                        CHECK (length(body) = byte_length)
                    )
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
        connection.execute(
            """
            SELECT history_id, locator, owner_id, completion_key, completed_at,
                   expires_at, payload_sha256, detail_json, detail_sha256
            FROM search_history
            LIMIT 0
            """
        )
        connection.execute(
            """
            SELECT history_id, position, locator, angle, content_type, sha256,
                   byte_length, width, height, body
            FROM history_reference_images
            LIMIT 0
            """
        )

    @staticmethod
    def _rollback(connection: sqlite3.Connection) -> None:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    def _load_detail(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> HistoryDetail:
        try:
            if not hmac.compare_digest(
                _text_sha256(row["detail_json"]),
                row["detail_sha256"],
            ):
                _raise_storage_error()
            detail = HistoryDetail.model_validate_json(row["detail_json"], strict=True)
            if (
                detail.locator != row["locator"]
                or _time_text(detail.completed_at) != row["completed_at"]
                or _time_text(detail.expires_at) != row["expires_at"]
            ):
                _raise_storage_error()
            image_rows = connection.execute(
                """
                SELECT locator, angle, content_type, width, height
                FROM history_reference_images
                WHERE history_id = ?
                ORDER BY position
                """,
                (row["history_id"],),
            ).fetchall()
            image_refs = tuple(
                HistoryReferenceImageRef(
                    schema_version="2.0",
                    locator=image_row["locator"],
                    angle=image_row["angle"],
                    content_type=image_row["content_type"],
                    width=image_row["width"],
                    height=image_row["height"],
                )
                for image_row in image_rows
            )
            if image_refs != detail.reference_images:
                _raise_storage_error()
            return detail
        except HistoryStorageError:
            raise
        except (TypeError, ValidationError, ValueError):
            _raise_storage_error()

    def save(self, pending: SearchHistoryWrite, *, now: datetime) -> HistoryDetail:
        validated = _validated_pending(pending)
        current_time = _validated_now(now)
        try:
            expires_at = validated.completed_at + timedelta(days=HISTORY_RETENTION_DAYS)
        except OverflowError:
            _raise_input_error()
        if not validated.completed_at <= current_time < expires_at:
            _raise_input_error()

        payload_sha256 = _payload_sha256(validated)
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    existing = connection.execute(
                        """
                        SELECT history_id, locator, completed_at, expires_at,
                               payload_sha256, detail_json, detail_sha256
                        FROM search_history
                        WHERE owner_id = ? AND completion_key = ?
                        """,
                        (validated.owner_id, validated.completion_key),
                    ).fetchone()
                    if existing is not None:
                        if not hmac.compare_digest(existing["payload_sha256"], payload_sha256):
                            raise HistoryConflictError(_CONFLICT_MESSAGE) from None
                        detail = self._load_detail(connection, existing)
                        connection.execute("COMMIT")
                        return detail

                    history_id = secrets.token_hex(32)
                    locator = secrets.token_urlsafe(32)
                    image_refs = tuple(
                        HistoryReferenceImageRef(
                            schema_version="2.0",
                            locator=secrets.token_urlsafe(32),
                            angle=image.angle,
                            content_type="image/png",
                            width=512,
                            height=512,
                        )
                        for image in validated.reference_images
                    )
                    detail = _new_detail(
                        validated,
                        locator=locator,
                        expires_at=expires_at,
                        image_refs=image_refs,
                    )
                    serialized_detail = _detail_json(detail)
                    connection.execute(
                        """
                        INSERT INTO search_history (
                            history_id, locator, owner_id, completion_key,
                            completed_at, expires_at, payload_sha256, detail_json,
                            detail_sha256
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            history_id,
                            locator,
                            validated.owner_id,
                            validated.completion_key,
                            _time_text(validated.completed_at),
                            _time_text(expires_at),
                            payload_sha256,
                            serialized_detail,
                            _text_sha256(serialized_detail),
                        ),
                    )
                    for position, (image, image_ref) in enumerate(
                        zip(validated.reference_images, image_refs, strict=True)
                    ):
                        connection.execute(
                            """
                            INSERT INTO history_reference_images (
                                history_id, position, locator, angle, content_type,
                                sha256, byte_length, width, height, body
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                history_id,
                                position,
                                image_ref.locator,
                                image.angle,
                                image.content_type,
                                image.sha256,
                                image.byte_length,
                                image.width,
                                image.height,
                                image.body,
                            ),
                        )
                    connection.execute("COMMIT")
                    return detail
                except SearchHistoryError:
                    self._rollback(connection)
                    raise
                except (sqlite3.Error, TypeError, ValidationError, ValueError):
                    self._rollback(connection)
                    _raise_storage_error()
        except SearchHistoryError:
            raise
        except (OSError, sqlite3.Error):
            _raise_storage_error()

    def list(self, *, owner_id: str, now: datetime) -> tuple[HistoryListItem, ...]:
        validated_owner = _validated_owner(owner_id)
        current_time = _validated_now(now)
        try:
            with self._connection() as connection:
                rows = connection.execute(
                    """
                    SELECT history_id, locator, completed_at, expires_at,
                           payload_sha256, detail_json, detail_sha256
                    FROM search_history
                    WHERE owner_id = ? AND expires_at > ?
                    ORDER BY completed_at DESC, history_id DESC
                    """,
                    (validated_owner, _time_text(current_time)),
                ).fetchall()
                return tuple(_list_item(self._load_detail(connection, row)) for row in rows)
        except SearchHistoryError:
            raise
        except (OSError, sqlite3.Error, TypeError, ValidationError, ValueError):
            _raise_storage_error()

    def get(self, *, owner_id: str, locator: str, now: datetime) -> HistoryDetail:
        validated_owner = _validated_owner(owner_id)
        validated_locator = _validated_locator(locator)
        current_time = _validated_now(now)
        try:
            with self._connection() as connection:
                row = connection.execute(
                    """
                    SELECT history_id, locator, completed_at, expires_at,
                           payload_sha256, detail_json, detail_sha256
                    FROM search_history
                    WHERE owner_id = ? AND locator = ? AND expires_at > ?
                    """,
                    (validated_owner, validated_locator, _time_text(current_time)),
                ).fetchone()
                if row is None:
                    raise HistoryNotFoundError(_NOT_FOUND_MESSAGE) from None
                return self._load_detail(connection, row)
        except SearchHistoryError:
            raise
        except (OSError, sqlite3.Error, TypeError, ValidationError, ValueError):
            _raise_storage_error()

    def get_image(self, *, owner_id: str, image_locator: str, now: datetime) -> HistoryImage:
        validated_owner = _validated_owner(owner_id)
        validated_locator = _validated_locator(image_locator)
        current_time = _validated_now(now)
        try:
            with self._connection() as connection:
                row = connection.execute(
                    """
                    SELECT image.locator, image.angle, image.content_type,
                           image.sha256, image.byte_length, image.width,
                           image.height, image.body
                    FROM history_reference_images AS image
                    JOIN search_history AS history
                      ON history.history_id = image.history_id
                    WHERE history.owner_id = ?
                      AND image.locator = ?
                      AND history.expires_at > ?
                    """,
                    (validated_owner, validated_locator, _time_text(current_time)),
                ).fetchone()
                if row is None:
                    raise HistoryNotFoundError(_NOT_FOUND_MESSAGE) from None
                artifact = HistoryReferenceImageWrite(
                    schema_version="2.0",
                    angle=row["angle"],
                    content_type=row["content_type"],
                    sha256=row["sha256"],
                    byte_length=row["byte_length"],
                    width=row["width"],
                    height=row["height"],
                    body=row["body"],
                )
                return HistoryImage(
                    schema_version="2.0",
                    locator=row["locator"],
                    angle=artifact.angle,
                    content_type=artifact.content_type,
                    width=artifact.width,
                    height=artifact.height,
                    body=artifact.body,
                )
        except HistoryNotFoundError:
            raise
        except (OSError, sqlite3.Error, TypeError, ValidationError, ValueError):
            _raise_storage_error()

    def delete(self, *, owner_id: str, locator: str) -> None:
        validated_owner = _validated_owner(owner_id)
        validated_locator = _validated_locator(locator)
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    row = connection.execute(
                        """
                        SELECT history_id
                        FROM search_history
                        WHERE owner_id = ? AND locator = ?
                        """,
                        (validated_owner, validated_locator),
                    ).fetchone()
                    if row is None:
                        raise HistoryNotFoundError(_NOT_FOUND_MESSAGE) from None
                    deleted = connection.execute(
                        """
                        DELETE FROM search_history
                        WHERE history_id = ? AND owner_id = ?
                        """,
                        (row["history_id"], validated_owner),
                    ).rowcount
                    if deleted != 1:
                        _raise_storage_error()
                    connection.execute("COMMIT")
                except SearchHistoryError:
                    self._rollback(connection)
                    raise
                except sqlite3.Error:
                    self._rollback(connection)
                    _raise_storage_error()
        except SearchHistoryError:
            raise
        except (OSError, sqlite3.Error):
            _raise_storage_error()

    def purge_expired(self, *, now: datetime) -> int:
        current_time = _validated_now(now)
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    deleted = connection.execute(
                        """
                        DELETE FROM search_history
                        WHERE expires_at <= ?
                        """,
                        (_time_text(current_time),),
                    ).rowcount
                    connection.execute("COMMIT")
                    return deleted
                except sqlite3.Error:
                    self._rollback(connection)
                    _raise_storage_error()
        except SearchHistoryError:
            raise
        except (OSError, sqlite3.Error):
            _raise_storage_error()
