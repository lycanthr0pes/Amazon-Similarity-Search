"""Separate schema-5 display history for provisional counterfactual ranking."""

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
from pydantic import model_serializer

from src.search_v2.candidate_bilingual import BilingualTitleScore, BilingualConditionScore
from src.search_v2.history_content import HistoryContent, validate_thumbnail
from src.search_v2.usage_ledger import Digest
from src.search_v2.usage_ledger import SubjectId


PROVISIONAL_HISTORY_RETENTION_DAYS = 30
MAX_PROVISIONAL_HISTORY_PRODUCTS = 48
MAX_PROVISIONAL_HISTORY_IMAGE_BYTES = 2 * 1024 * 1024
_SCHEMA_VERSION = 5
_PAYLOAD_DOMAIN = b"amazon-explorer-provisional-history-v5\x00"
_INVALID_INPUT_MESSAGE = "Provisional search history input is invalid"
_CONFLICT_MESSAGE = "Provisional search history completion conflicts"
_NOT_FOUND_MESSAGE = "Provisional search history was not found"
_STORAGE_MESSAGE = "Provisional search history storage operation failed"

HistoryLocator = Annotated[
    str,
    StringConstraints(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
]
DisplayText = Annotated[str, StringConstraints(min_length=1, max_length=500)]
HttpsUrl = Annotated[str, StringConstraints(min_length=1, max_length=2_048)]
ImageTarget = Literal["desired", "counterfactual"]
ImageComponentStatus = Literal["available", "missing", "unknown", "not_used"]

_OWNER_ADAPTER = TypeAdapter(SubjectId)
_LOCATOR_ADAPTER = TypeAdapter(HistoryLocator)


class ProvisionalHistoryError(RuntimeError):
    """Base class for fixed-message provisional history failures."""


class ProvisionalHistoryInputError(ProvisionalHistoryError):
    pass


class ProvisionalHistoryConflictError(ProvisionalHistoryError):
    pass


class ProvisionalHistoryNotFoundError(ProvisionalHistoryError):
    pass


class ProvisionalHistoryStorageError(ProvisionalHistoryError):
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


def _validate_display_text(value: str) -> str:
    if value != value.strip() or any(
        unicodedata.category(character).startswith("C") and not character.isspace()
        for character in value
    ):
        raise ValueError("provisional history display text is invalid")
    return value


def _validate_product_url(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        value.encode("ascii")
        parsed = urlsplit(value)
        port = parsed.port
    except (UnicodeEncodeError, ValueError):
        raise ValueError("provisional history product URL is invalid") from None
    hostname = parsed.hostname
    if (
        parsed.scheme != "https"
        or hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.fragment
        or not (
            hostname.casefold() == "amazon.co.jp" or hostname.casefold().endswith(".amazon.co.jp")
        )
    ):
        raise ValueError("provisional history product URL is invalid")
    return value


class ProvisionalHistoryProductView(_StrictFrozenContract):
    schema_version: Literal["5.0"]
    rank: Annotated[int, Field(ge=1, le=MAX_PROVISIONAL_HISTORY_PRODUCTS)]
    thumbnail_png: str | None = Field(default=None, max_length=180000, repr=False)
    title: DisplayText = Field(repr=False)
    title_en: DisplayText | None = Field(default=None, repr=False)
    title_en_status: Literal["available", "unavailable"] | None = None
    review_rating: Annotated[float, Field(ge=0.0, le=5.0)] | None = None
    title_scores: BilingualTitleScore | None = None
    condition_scores: tuple[BilingualConditionScore, ...] | None = Field(
        default=None, max_length=64
    )
    price_jpy: Annotated[int, Field(gt=0, le=1_000_000_000)] | None
    product_url: HttpsUrl | None = Field(repr=False)
    required_status: Literal["confirmed", "uncertain", "contradicted"]
    image_component_status: ImageComponentStatus
    image_score: Annotated[float, Field(ge=0.0, le=1.0)] | None
    total_score: Annotated[float, Field(ge=0.0, le=1.0)]

    @model_serializer(mode="wrap")
    def serialize_compatible(self, handler):
        data = handler(self)
        for field in ("title_scores", "condition_scores", "review_rating", "thumbnail_png"):
            if getattr(self, field) is None:
                data.pop(field, None)
        if self.title_en_status is None:
            data.pop("title_en", None)
            data.pop("title_en_status", None)
        return data

    @field_validator("thumbnail_png")
    @classmethod
    def validate_thumbnail(cls, value):
        return validate_thumbnail(value)

    @field_validator("title", "title_en")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        return _validate_display_text(value) if value is not None else None

    @field_validator("product_url")
    @classmethod
    def validate_product_url(cls, value: str | None) -> str | None:
        return _validate_product_url(value)

    @model_validator(mode="after")
    def validate_image_component(self) -> ProvisionalHistoryProductView:
        if (self.title_en_status == "available") != (self.title_en is not None):
            raise ValueError("English title status is inconsistent")
        if (self.image_component_status == "available") != (self.image_score is not None):
            raise ValueError("provisional history image score is inconsistent")
        return self


class ProvisionalHistoryReferenceImageWrite(_StrictFrozenContract):
    schema_version: Literal["5.0"]
    target: ImageTarget
    condition_id: (
        Annotated[
            str,
            StringConstraints(pattern=r"^visual-condition-[0-9]{3}$"),
        ]
        | None
    )
    content_type: Literal["image/png"]
    sha256: Digest
    byte_length: Annotated[int, Field(gt=0, le=MAX_PROVISIONAL_HISTORY_IMAGE_BYTES)]
    width: Annotated[int, Field(ge=1, le=4_096)]
    height: Annotated[int, Field(ge=1, le=4_096)]
    body: bytes = Field(exclude=True, repr=False)

    @model_validator(mode="after")
    def validate_image(self) -> ProvisionalHistoryReferenceImageWrite:
        if (self.target == "desired") != (self.condition_id is None):
            raise ValueError("provisional history reference target is inconsistent")
        if type(self.body) is not bytes or len(self.body) != self.byte_length:
            raise ValueError("provisional history image byte length does not match")
        if not hmac.compare_digest(hashlib.sha256(self.body).hexdigest(), self.sha256):
            raise ValueError("provisional history image digest does not match")
        try:
            with Image.open(BytesIO(self.body), formats=("PNG",)) as image:
                if (
                    image.format != "PNG"
                    or image.size != (self.width, self.height)
                    or getattr(image, "n_frames", 1) != 1
                ):
                    raise ValueError("provisional history image metadata does not match")
                image.load()
        except (OSError, UnidentifiedImageError):
            raise ValueError("provisional history image body is invalid") from None
        return self


class ProvisionalHistoryReferenceImageRef(_StrictFrozenContract):
    schema_version: Literal["5.0"]
    locator: HistoryLocator
    target: ImageTarget
    condition_id: (
        Annotated[
            str,
            StringConstraints(pattern=r"^visual-condition-[0-9]{3}$"),
        ]
        | None
    )
    content_type: Literal["image/png"]
    width: Annotated[int, Field(ge=1, le=4_096)]
    height: Annotated[int, Field(ge=1, le=4_096)]

    @model_validator(mode="after")
    def validate_target(self) -> ProvisionalHistoryReferenceImageRef:
        if (self.target == "desired") != (self.condition_id is None):
            raise ValueError("provisional history reference target is inconsistent")
        return self


class _HistoryRankingMetadata(_StrictFrozenContract):
    product_name: Annotated[str, StringConstraints(min_length=1, max_length=100)] | None = None

    @field_validator("product_name")
    @classmethod
    def validate_product_name(cls, value):
        return _validate_display_text(value) if value is not None else None

    history_content: HistoryContent | None = Field(default=None, repr=False)
    image_mode: Literal["off"] | None = None
    image_weight: Literal[0.5] | None = None
    sort_profile_id: (
        Literal["title-image-conditions-v1", "excluded-title-conditions-image-review-v1"] | None
    ) = None
    text_profile_id: Literal["candidate-text-v1", "candidate-text-bilingual-v2"] | None = None
    retrieval_provider: Literal["playwright"] | None = None

    @model_serializer(mode="wrap")
    def serialize_compatible(self, handler):
        data = handler(self)
        if self.product_name is None:
            data.pop("product_name", None)
        if self.history_content is None:
            data.pop("history_content", None)
        if self.image_mode is None:
            data.pop("image_mode", None)
        if self.image_weight is None:
            data.pop("image_weight", None)
        if self.sort_profile_id is None:
            data.pop("sort_profile_id", None)
        if self.text_profile_id is None:
            data.pop("text_profile_id", None)
        if self.retrieval_provider is None:
            data.pop("retrieval_provider", None)
        return data

    provisional_profile_id: Literal[
        "counterfactual-v4-provisional-production-v1",
        "counterfactual-relative-v1",
        "counterfactual-appearance-v1",
        "counterfactual-siglip2-appearance-v1",
        "counterfactual-attribute-v1",
        "counterfactual-attribute-v2",
        "image-free-v1",
    ]
    known_holdout_accuracy: Literal[0.875] | None
    ranking_profile_id: Literal[
        "typed-ranking-v5-counterfactual-provisional",
        "candidate-semantic-clip-v1",
        "candidate-lexical-clip-v2",
        "candidate-lexical-clip-v3",
        "candidate-appearance-v1",
        "candidate-siglip2-appearance-v1",
        "candidate-attribute-image-v1",
        "candidate-attribute-image-v2",
        "candidate-image-free-v1",
    ]

    @model_validator(mode="after")
    def validate_ranking_metadata(self):
        image_free = self.image_mode == "off"
        if image_free != (self.ranking_profile_id == "candidate-image-free-v1") or image_free != (
            self.provisional_profile_id == "image-free-v1"
        ):
            raise ValueError("History image mode and profile disagree")
        if image_free and (
            self.image_weight is not None
            or self.sort_profile_id != "excluded-title-conditions-image-review-v1"
        ):
            raise ValueError("Image-free history cannot use image weighting")
        if not image_free and self.sort_profile_id is not None and self.image_weight != 0.5:
            raise ValueError("History sort profile requires current score weighting")
        if self.image_weight is not None and self.ranking_profile_id in {
            "typed-ranking-v5-counterfactual-provisional",
            "candidate-semantic-clip-v1",
        }:
            raise ValueError("Legacy history cannot use equal image weighting")
        if self.text_profile_id is not None and self.ranking_profile_id in {
            "typed-ranking-v5-counterfactual-provisional",
            "candidate-semantic-clip-v1",
            "candidate-lexical-clip-v2",
        }:
            raise ValueError("Legacy history cannot use the new text profile")
        if (self.ranking_profile_id == "candidate-siglip2-appearance-v1") != (
            self.provisional_profile_id == "counterfactual-siglip2-appearance-v1"
        ):
            raise ValueError("History SigLIP model profile does not match")
        if (self.ranking_profile_id == "candidate-appearance-v1") != (
            self.provisional_profile_id == "counterfactual-appearance-v1"
        ):
            raise ValueError("History appearance scope does not match its ranking method")
        if (self.ranking_profile_id == "candidate-attribute-image-v2") != (
            self.provisional_profile_id == "counterfactual-attribute-v2"
        ):
            raise ValueError("History geometry profile does not match its ranking method")
        if (self.ranking_profile_id == "candidate-attribute-image-v1") != (
            self.provisional_profile_id == "counterfactual-attribute-v1"
        ):
            raise ValueError("History attribute profile does not match its ranking method")
        if (self.ranking_profile_id == "candidate-lexical-clip-v3") != (
            self.provisional_profile_id == "counterfactual-relative-v1"
        ):
            raise ValueError("History visual profile does not match its ranking method")
        expected = (
            0.875
            if self.ranking_profile_id == "typed-ranking-v5-counterfactual-provisional"
            else None
        )
        if self.known_holdout_accuracy != expected:
            raise ValueError("History accuracy does not belong to its ranking profile")
        return self

    @model_validator(mode="after")
    def validate_image_evidence(self):
        if not hasattr(self, "reference_images"):
            return self
        if any(p.thumbnail_png is not None for p in self.products) and (
            self.history_content is None
        ):
            raise ValueError("History thumbnails require an image content snapshot")
        if self.history_content is not None and any(
            score.requirement_id not in self.history_content.condition_labels
            for product in self.products
            for score in (product.condition_scores or ())
        ):
            raise ValueError("History condition labels are incomplete")
        hashes = (self.condition_set_sha256, self.reference_set_sha256, self.runtime_sha256)
        if self.image_mode == "off":
            if (
                self.reference_images
                or any(h is not None for h in hashes)
                or any(
                    p.image_component_status != "not_used" or p.image_score is not None
                    for p in self.products
                )
            ):
                raise ValueError("Image-free history contains image evidence")
        elif (
            not self.products
            or len(self.reference_images) < 2
            or any(h is None for h in hashes)
            or any(p.image_component_status == "not_used" for p in self.products)
        ):
            raise ValueError("Image history requires its image evidence")
        return self


class ProvisionalHistoryWrite(_HistoryRankingMetadata):
    schema_version: Literal["5.0"]
    owner_id: SubjectId = Field(repr=False)
    completion_key: Digest = Field(repr=False)
    completed_at: datetime
    summary: DisplayText
    ranking_profile_sha256: Digest
    source_typed_ranked_product_batch_sha256: Digest
    condition_set_sha256: Digest | None
    reference_set_sha256: Digest | None
    runtime_sha256: Digest | None
    reference_images: Annotated[
        tuple[ProvisionalHistoryReferenceImageWrite, ...],
        Field(min_length=0, max_length=4, exclude=True, repr=False),
    ]
    products: Annotated[
        tuple[ProvisionalHistoryProductView, ...],
        Field(min_length=0, max_length=MAX_PROVISIONAL_HISTORY_PRODUCTS, repr=False),
    ]

    @field_validator("completed_at")
    @classmethod
    def validate_completed_at(cls, value: datetime) -> datetime:
        return _utc_datetime(value, field_name="completed_at")

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        return _validate_display_text(value)

    @model_validator(mode="after")
    def validate_order(self) -> ProvisionalHistoryWrite:
        references = self.reference_images
        if self.image_mode == "off":
            if tuple(item.rank for item in self.products) != tuple(
                range(1, len(self.products) + 1)
            ):
                raise ValueError("Invalid image-free product order")
            return self
        expected_ids = tuple(f"visual-condition-{index:03d}" for index in range(1, len(references)))
        if (
            references[0].target != "desired"
            or references[0].condition_id is not None
            or tuple(item.target for item in references[1:])
            != ("counterfactual",) * (len(references) - 1)
            or tuple(item.condition_id for item in references[1:]) != expected_ids
            or tuple(item.rank for item in self.products) != tuple(range(1, len(self.products) + 1))
        ):
            raise ValueError("provisional history ordering is invalid")
        return self


class ProvisionalHistoryDetail(_HistoryRankingMetadata):
    schema_version: Literal["5.0"]
    locator: HistoryLocator
    completed_at: datetime
    expires_at: datetime
    summary: DisplayText
    ranking_profile_sha256: Digest
    source_typed_ranked_product_batch_sha256: Digest
    condition_set_sha256: Digest | None
    reference_set_sha256: Digest | None
    runtime_sha256: Digest | None
    reference_images: Annotated[
        tuple[ProvisionalHistoryReferenceImageRef, ...], Field(min_length=0, max_length=4)
    ]
    products: Annotated[
        tuple[ProvisionalHistoryProductView, ...],
        Field(min_length=0, max_length=MAX_PROVISIONAL_HISTORY_PRODUCTS, repr=False),
    ]

    @field_validator("completed_at", "expires_at")
    @classmethod
    def validate_timestamp(cls, value: datetime, info) -> datetime:
        return _utc_datetime(value, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_expiry(self) -> ProvisionalHistoryDetail:
        if self.expires_at != self.completed_at + timedelta(
            days=PROVISIONAL_HISTORY_RETENTION_DAYS
        ):
            raise ValueError("provisional history expiry is invalid")
        return self


class ProvisionalHistoryListItem(_StrictFrozenContract):
    product_name: Annotated[str, StringConstraints(min_length=1, max_length=100)] | None = None
    schema_version: Literal["5.0"]
    locator: HistoryLocator
    completed_at: datetime
    expires_at: datetime
    summary: DisplayText
    known_holdout_accuracy: Literal[0.875] | None
    compared_count: Annotated[int, Field(ge=0, le=MAX_PROVISIONAL_HISTORY_PRODUCTS)]

    @field_validator("completed_at", "expires_at")
    @classmethod
    def validate_timestamp(cls, value: datetime, info) -> datetime:
        return _utc_datetime(value, field_name=info.field_name)


class ProvisionalHistoryImage(_StrictFrozenContract):
    schema_version: Literal["5.0"]
    locator: HistoryLocator
    target: ImageTarget
    condition_id: (
        Annotated[
            str,
            StringConstraints(pattern=r"^visual-condition-[0-9]{3}$"),
        ]
        | None
    )
    content_type: Literal["image/png"]
    width: Annotated[int, Field(ge=1, le=4_096)]
    height: Annotated[int, Field(ge=1, le=4_096)]
    body: bytes = Field(exclude=True, repr=False)


def _payload_sha256(pending: ProvisionalHistoryWrite) -> str:
    payload = pending.model_dump(mode="json")
    payload["reference_images"] = [
        image.model_dump(mode="json", exclude={"body"}) for image in pending.reference_images
    ]
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(_PAYLOAD_DOMAIN + canonical).hexdigest()


def _detail_json(detail: ProvisionalHistoryDetail) -> str:
    return json.dumps(
        detail.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _detail_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class SqliteProvisionalHistoryRepository:
    """Owner-scoped schema-5 history; never migrates legacy schema-2 rows."""

    def __init__(self, path: Path, *, read_only: bool = False, existing_only: bool = False) -> None:
        self._existing_only = existing_only
        self._read_only = read_only
        try:
            requested = Path(path)
            if requested.is_symlink():
                raise ProvisionalHistoryStorageError(_STORAGE_MESSAGE)
            if not read_only and not existing_only:
                requested.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            resolved = requested.resolve()
            if resolved.exists():
                mode = resolved.stat(follow_symlinks=False).st_mode
                if not stat.S_ISREG(mode) or (os.name == "posix" and stat.S_IMODE(mode) & 0o077):
                    raise ProvisionalHistoryStorageError(_STORAGE_MESSAGE)
            elif read_only or existing_only:
                raise ProvisionalHistoryStorageError(_STORAGE_MESSAGE)
            else:
                flags = os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(resolved, flags, 0o600)
                os.close(descriptor)
            self.path = resolved
            self._initialize()
        except ProvisionalHistoryError:
            raise
        except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
            raise ProvisionalHistoryStorageError(_STORAGE_MESSAGE) from exc

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(
                self.path.as_uri() + ("?mode=ro" if self._read_only else "?mode=rw")
                if self._read_only or self._existing_only
                else self.path,
                uri=self._read_only or self._existing_only,
                timeout=0.25 if self._existing_only else 5.0,
                isolation_level=None,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
        finally:
            if connection is not None:
                connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in {0, _SCHEMA_VERSION} or (
                (self._read_only or self._existing_only) and version != _SCHEMA_VERSION
            ):
                raise ProvisionalHistoryStorageError(_STORAGE_MESSAGE)
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
                raise ProvisionalHistoryStorageError(_STORAGE_MESSAGE)
            connection.execute("PRAGMA journal_mode = DELETE")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """
                    CREATE TABLE provisional_history (
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
                        CHECK (length(completion_key) = 64),
                        CHECK (length(payload_sha256) = 64),
                        CHECK (length(detail_sha256) = 64),
                        CHECK (expires_at > completed_at)
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX provisional_history_owner_completed
                    ON provisional_history (owner_id, completed_at DESC, history_id DESC)
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX provisional_history_expiry
                    ON provisional_history (expires_at)
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE provisional_history_images (
                        history_id TEXT NOT NULL,
                        position INTEGER NOT NULL,
                        locator TEXT NOT NULL UNIQUE,
                        target TEXT NOT NULL,
                        condition_id TEXT,
                        content_type TEXT NOT NULL,
                        sha256 TEXT NOT NULL,
                        byte_length INTEGER NOT NULL,
                        width INTEGER NOT NULL,
                        height INTEGER NOT NULL,
                        body BLOB NOT NULL,
                        PRIMARY KEY (history_id, position),
                        FOREIGN KEY (history_id) REFERENCES provisional_history(history_id)
                            ON DELETE CASCADE,
                        CHECK (position BETWEEN 0 AND 3),
                        CHECK (target IN ('desired', 'counterfactual')),
                        CHECK ((target = 'desired' AND condition_id IS NULL)
                            OR (target = 'counterfactual' AND condition_id IS NOT NULL)),
                        CHECK (content_type = 'image/png'),
                        CHECK (length(sha256) = 64),
                        CHECK (byte_length BETWEEN 1 AND 2097152),
                        CHECK (width BETWEEN 1 AND 4096),
                        CHECK (height BETWEEN 1 AND 4096),
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
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ProvisionalHistoryStorageError(_STORAGE_MESSAGE)
        connection.execute(
            """
            SELECT history_id, locator, owner_id, completion_key, completed_at,
                   expires_at, payload_sha256, detail_json, detail_sha256
            FROM provisional_history LIMIT 0
            """
        )
        connection.execute(
            """
            SELECT history_id, position, locator, target, condition_id,
                   content_type, sha256, byte_length, width, height, body
            FROM provisional_history_images LIMIT 0
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
    ) -> ProvisionalHistoryDetail:
        try:
            if not hmac.compare_digest(_detail_sha256(row["detail_json"]), row["detail_sha256"]):
                raise ProvisionalHistoryStorageError(_STORAGE_MESSAGE)
            detail = ProvisionalHistoryDetail.model_validate_json(row["detail_json"], strict=True)
            if (
                detail.locator != row["locator"]
                or _time_text(detail.completed_at) != row["completed_at"]
                or _time_text(detail.expires_at) != row["expires_at"]
            ):
                raise ProvisionalHistoryStorageError(_STORAGE_MESSAGE)
            image_rows = connection.execute(
                """
                SELECT locator, target, condition_id, content_type, width, height
                FROM provisional_history_images
                WHERE history_id = ? ORDER BY position
                """,
                (row["history_id"],),
            ).fetchall()
            refs = tuple(
                ProvisionalHistoryReferenceImageRef(
                    schema_version="5.0",
                    locator=item["locator"],
                    target=item["target"],
                    condition_id=item["condition_id"],
                    content_type=item["content_type"],
                    width=item["width"],
                    height=item["height"],
                )
                for item in image_rows
            )
            if refs != detail.reference_images:
                raise ProvisionalHistoryStorageError(_STORAGE_MESSAGE)
            return detail
        except ProvisionalHistoryError:
            raise
        except (TypeError, ValueError, ValidationError) as exc:
            raise ProvisionalHistoryStorageError(_STORAGE_MESSAGE) from exc

    def save(self, pending: ProvisionalHistoryWrite, *, now: datetime) -> ProvisionalHistoryDetail:
        try:
            validated = ProvisionalHistoryWrite.model_validate(pending)
            current = _utc_datetime(now, field_name="now")
            expires = validated.completed_at + timedelta(days=PROVISIONAL_HISTORY_RETENTION_DAYS)
            if not validated.completed_at <= current < expires:
                raise ValueError("provisional history completion is outside retention")
            payload_digest = _payload_sha256(validated)
        except (TypeError, ValueError, ValidationError) as exc:
            raise ProvisionalHistoryInputError(_INVALID_INPUT_MESSAGE) from exc

        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    """
                    SELECT history_id, locator, completed_at, expires_at,
                           payload_sha256, detail_json, detail_sha256
                    FROM provisional_history
                    WHERE owner_id = ? AND completion_key = ?
                    """,
                    (validated.owner_id, validated.completion_key),
                ).fetchone()
                if existing is not None:
                    if not hmac.compare_digest(existing["payload_sha256"], payload_digest):
                        self._rollback(connection)
                        raise ProvisionalHistoryConflictError(_CONFLICT_MESSAGE)
                    detail = self._load_detail(connection, existing)
                    connection.execute("COMMIT")
                    return detail

                history_id = hashlib.sha256(
                    f"{validated.owner_id}\x00{validated.completion_key}".encode("utf-8")
                ).hexdigest()
                locator = secrets.token_urlsafe(32)
                image_refs = tuple(
                    ProvisionalHistoryReferenceImageRef(
                        schema_version="5.0",
                        locator=secrets.token_urlsafe(32),
                        target=image.target,
                        condition_id=image.condition_id,
                        content_type=image.content_type,
                        width=image.width,
                        height=image.height,
                    )
                    for image in validated.reference_images
                )
                detail = ProvisionalHistoryDetail(
                    schema_version="5.0",
                    locator=locator,
                    completed_at=validated.completed_at,
                    expires_at=expires,
                    summary=validated.summary,
                    product_name=validated.product_name,
                    history_content=validated.history_content,
                    provisional_profile_id=validated.provisional_profile_id,
                    known_holdout_accuracy=validated.known_holdout_accuracy,
                    ranking_profile_id=validated.ranking_profile_id,
                    text_profile_id=validated.text_profile_id,
                    image_mode=validated.image_mode,
                    image_weight=validated.image_weight,
                    sort_profile_id=validated.sort_profile_id,
                    retrieval_provider=validated.retrieval_provider,
                    ranking_profile_sha256=validated.ranking_profile_sha256,
                    source_typed_ranked_product_batch_sha256=(
                        validated.source_typed_ranked_product_batch_sha256
                    ),
                    condition_set_sha256=validated.condition_set_sha256,
                    reference_set_sha256=validated.reference_set_sha256,
                    runtime_sha256=validated.runtime_sha256,
                    reference_images=image_refs,
                    products=validated.products,
                )
                serialized = _detail_json(detail)
                connection.execute(
                    """
                    INSERT INTO provisional_history (
                        history_id, locator, owner_id, completion_key, completed_at,
                        expires_at, payload_sha256, detail_json, detail_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        history_id,
                        locator,
                        validated.owner_id,
                        validated.completion_key,
                        _time_text(validated.completed_at),
                        _time_text(expires),
                        payload_digest,
                        serialized,
                        _detail_sha256(serialized),
                    ),
                )
                for position, (image, ref) in enumerate(
                    zip(validated.reference_images, image_refs, strict=True)
                ):
                    connection.execute(
                        """
                        INSERT INTO provisional_history_images (
                            history_id, position, locator, target, condition_id,
                            content_type, sha256, byte_length, width, height, body
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            history_id,
                            position,
                            ref.locator,
                            image.target,
                            image.condition_id,
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
        except ProvisionalHistoryError:
            raise
        except (OSError, sqlite3.Error, TypeError, ValueError, ValidationError) as exc:
            raise ProvisionalHistoryStorageError(_STORAGE_MESSAGE) from exc

    def get(
        self,
        *,
        owner_id: str,
        locator: str,
        now: datetime,
    ) -> ProvisionalHistoryDetail:
        try:
            owner = _OWNER_ADAPTER.validate_python(owner_id, strict=True)
            validated_locator = _LOCATOR_ADAPTER.validate_python(locator, strict=True)
            current = _utc_datetime(now, field_name="now")
        except (TypeError, ValueError, ValidationError) as exc:
            raise ProvisionalHistoryInputError(_INVALID_INPUT_MESSAGE) from exc
        try:
            with self._connection() as connection:
                row = connection.execute(
                    """
                    SELECT history_id, locator, completed_at, expires_at,
                           payload_sha256, detail_json, detail_sha256
                    FROM provisional_history
                    WHERE owner_id = ? AND locator = ? AND expires_at > ?
                    """,
                    (owner, validated_locator, _time_text(current)),
                ).fetchone()
                if row is None:
                    raise ProvisionalHistoryNotFoundError(_NOT_FOUND_MESSAGE)
                return self._load_detail(connection, row)
        except ProvisionalHistoryError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise ProvisionalHistoryStorageError(_STORAGE_MESSAGE) from exc

    def list(
        self,
        *,
        owner_id: str,
        now: datetime,
    ) -> tuple[ProvisionalHistoryListItem, ...]:
        try:
            owner = _OWNER_ADAPTER.validate_python(owner_id, strict=True)
            current = _utc_datetime(now, field_name="now")
        except (TypeError, ValueError, ValidationError) as exc:
            raise ProvisionalHistoryInputError(_INVALID_INPUT_MESSAGE) from exc
        try:
            with self._connection() as connection:
                rows = connection.execute(
                    """
                    SELECT history_id, locator, completed_at, expires_at,
                           payload_sha256, detail_json, detail_sha256
                    FROM provisional_history
                    WHERE owner_id = ? AND expires_at > ?
                    ORDER BY completed_at DESC, history_id DESC
                    """,
                    (owner, _time_text(current)),
                ).fetchall()
                details = (self._load_detail(connection, row) for row in rows)
                return tuple(
                    ProvisionalHistoryListItem(
                        schema_version="5.0",
                        locator=detail.locator,
                        completed_at=detail.completed_at,
                        expires_at=detail.expires_at,
                        summary=detail.summary,
                        product_name=detail.product_name,
                        known_holdout_accuracy=detail.known_holdout_accuracy,
                        compared_count=len(detail.products),
                    )
                    for detail in details
                )
        except ProvisionalHistoryError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise ProvisionalHistoryStorageError(_STORAGE_MESSAGE) from exc

    def get_image(
        self,
        *,
        owner_id: str,
        image_locator: str,
        now: datetime,
    ) -> ProvisionalHistoryImage:
        try:
            owner = _OWNER_ADAPTER.validate_python(owner_id, strict=True)
            locator = _LOCATOR_ADAPTER.validate_python(image_locator, strict=True)
            current = _utc_datetime(now, field_name="now")
        except (TypeError, ValueError, ValidationError) as exc:
            raise ProvisionalHistoryInputError(_INVALID_INPUT_MESSAGE) from exc
        try:
            with self._connection() as connection:
                row = connection.execute(
                    """
                    SELECT image.locator, image.target, image.condition_id,
                           image.content_type, image.sha256, image.byte_length,
                           image.width, image.height, image.body
                    FROM provisional_history_images AS image
                    JOIN provisional_history AS history
                      ON history.history_id = image.history_id
                    WHERE history.owner_id = ? AND image.locator = ?
                      AND history.expires_at > ?
                    """,
                    (owner, locator, _time_text(current)),
                ).fetchone()
                if row is None:
                    raise ProvisionalHistoryNotFoundError(_NOT_FOUND_MESSAGE)
                artifact = ProvisionalHistoryReferenceImageWrite(
                    schema_version="5.0",
                    target=row["target"],
                    condition_id=row["condition_id"],
                    content_type=row["content_type"],
                    sha256=row["sha256"],
                    byte_length=row["byte_length"],
                    width=row["width"],
                    height=row["height"],
                    body=row["body"],
                )
                return ProvisionalHistoryImage(
                    schema_version="5.0",
                    locator=row["locator"],
                    target=artifact.target,
                    condition_id=artifact.condition_id,
                    content_type=artifact.content_type,
                    width=artifact.width,
                    height=artifact.height,
                    body=artifact.body,
                )
        except ProvisionalHistoryError:
            raise
        except (OSError, sqlite3.Error, TypeError, ValueError, ValidationError) as exc:
            raise ProvisionalHistoryStorageError(_STORAGE_MESSAGE) from exc

    def delete(self, *, owner_id: str, locator: str) -> None:
        try:
            owner = _OWNER_ADAPTER.validate_python(owner_id, strict=True)
            validated_locator = _LOCATOR_ADAPTER.validate_python(locator, strict=True)
        except (TypeError, ValueError, ValidationError) as exc:
            raise ProvisionalHistoryInputError(_INVALID_INPUT_MESSAGE) from exc
        try:
            with self._connection() as connection:
                connection.execute("PRAGMA secure_delete = ON")
                connection.execute("BEGIN IMMEDIATE")
                deleted = connection.execute(
                    "DELETE FROM provisional_history WHERE owner_id = ? AND locator = ?",
                    (owner, validated_locator),
                ).rowcount
                if deleted != 1:
                    self._rollback(connection)
                    raise ProvisionalHistoryNotFoundError(_NOT_FOUND_MESSAGE)
                connection.execute("COMMIT")
        except ProvisionalHistoryError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise ProvisionalHistoryStorageError(_STORAGE_MESSAGE) from exc

    def purge_expired(self, *, now: datetime, owner_id: str | None = None) -> int:
        try:
            current = _utc_datetime(now, field_name="now")
            owner = (
                None if owner_id is None else _OWNER_ADAPTER.validate_python(owner_id, strict=True)
            )
        except (TypeError, ValueError) as exc:
            raise ProvisionalHistoryInputError(_INVALID_INPUT_MESSAGE) from exc
        try:
            with self._connection() as connection:
                connection.execute("PRAGMA secure_delete = ON")
                connection.execute("BEGIN IMMEDIATE")
                deleted = connection.execute(
                    "DELETE FROM provisional_history WHERE expires_at <= ?"
                    + (" AND owner_id = ?" if owner is not None else ""),
                    (_time_text(current), owner) if owner is not None else (_time_text(current),),
                ).rowcount
                connection.execute("COMMIT")
                return deleted
        except (OSError, sqlite3.Error) as exc:
            raise ProvisionalHistoryStorageError(_STORAGE_MESSAGE) from exc
