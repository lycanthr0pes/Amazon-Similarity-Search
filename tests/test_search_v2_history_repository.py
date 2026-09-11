from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
import hashlib
from io import BytesIO
import json
import os
import sqlite3
import stat

from PIL import Image
import pytest
from pydantic import ValidationError

import src.search_v2.history_repository as history_repository
from src.search_v2.history_repository import HistoryConflictError
from src.search_v2.history_repository import HistoryNotFoundError
from src.search_v2.history_repository import HistoryProductView
from src.search_v2.history_repository import HistoryReferenceImageWrite
from src.search_v2.history_repository import HistoryStorageError
from src.search_v2.history_repository import SearchHistoryWrite
from src.search_v2.history_repository import SqliteSearchHistoryRepository


NOW = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
ANGLES = (
    "front_three_quarter",
    "left_side",
    "right_side",
    "rear_three_quarter",
)


def png_bytes(color: tuple[int, int, int]) -> bytes:
    output = BytesIO()
    Image.new("RGB", (512, 512), color).save(output, format="PNG", optimize=False)
    return output.getvalue()


def reference_images() -> tuple[HistoryReferenceImageWrite, ...]:
    images: list[HistoryReferenceImageWrite] = []
    for index, angle in enumerate(ANGLES):
        body = png_bytes((30 + index, 60 + index, 90 + index))
        images.append(
            HistoryReferenceImageWrite(
                schema_version="2.0",
                angle=angle,
                content_type="image/png",
                sha256=hashlib.sha256(body).hexdigest(),
                byte_length=len(body),
                width=512,
                height=512,
                body=body,
            )
        )
    return tuple(images)


def product(*, rank: int = 1, title: str = "合成テスト商品") -> HistoryProductView:
    return HistoryProductView(
        schema_version="2.0",
        rank=rank,
        title=title,
        image_url="https://images.example.test/product.png",
        price_jpy=12_800,
        description="保存時点の商品説明",
        product_url="https://www.amazon.co.jp/dp/B000000001",
        required_status="confirmed",
        match_summary="条件によく合います",
        matching_points=("軽量", "黒"),
        unverified_points=("電池持続時間",),
        caution_points=(),
        image_comparison_note=None,
    )


def history_write(
    *,
    owner_id: str = "owner-a",
    completion_key: str = "a" * 64,
    completed_at: datetime = NOW,
    outcome: str = "results",
    title: str = "合成テスト商品",
    with_images: bool = False,
) -> SearchHistoryWrite:
    products = () if outcome == "empty" else (product(title=title),)
    images = reference_images() if with_images else ()
    return SearchHistoryWrite.model_validate(
        {
            "schema_version": "2.0",
            "owner_id": owner_id,
            "completion_key": completion_key,
            "completed_at": completed_at,
            "summary": "軽量ヘッドホン",
            "source_text": "5万円以内の軽量なヘッドホン",
            "condition_snapshot": {
                "schema_version": "2.0",
                "product_type": "ヘッドホン",
                "conditions": ("軽量", "黒"),
                "price_summary": "5万円以内",
            },
            "reference_image_mode": "on" if with_images else "off",
            "reference_images": images,
            "ranking_profile_id": "typed-ranking-v4",
            "candidate_limit": 24,
            "outcome": outcome,
            "result_snapshot": products,
        }
    )


def test_results_and_empty_history_persist_in_newest_first_order(tmp_path) -> None:
    path = tmp_path / "history.sqlite3"
    repository = SqliteSearchHistoryRepository(path)
    older = repository.save(
        history_write(completed_at=NOW - timedelta(hours=1)),
        now=NOW,
    )
    newer = repository.save(
        history_write(
            completion_key="b" * 64,
            completed_at=NOW,
            outcome="empty",
        ),
        now=NOW,
    )

    reopened = SqliteSearchHistoryRepository(path)
    entries = reopened.list(owner_id="owner-a", now=NOW)

    assert [entry.locator for entry in entries] == [newer.locator, older.locator]
    assert [entry.outcome for entry in entries] == ["empty", "results"]
    assert [entry.compared_count for entry in entries] == [0, 1]
    assert newer.expires_at == NOW + timedelta(days=30)
    detail = reopened.get(owner_id="owner-a", locator=newer.locator, now=NOW)
    assert detail.result_snapshot == ()
    assert detail.outcome == "empty"


def test_exact_replay_returns_same_entry_without_duplicate_images(tmp_path) -> None:
    path = tmp_path / "history.sqlite3"
    repository = SqliteSearchHistoryRepository(path)
    pending = history_write(with_images=True)

    first = repository.save(pending, now=NOW)
    second = SqliteSearchHistoryRepository(path).save(
        pending,
        now=NOW + timedelta(minutes=1),
    )

    assert second == first
    assert len(repository.list(owner_id="owner-a", now=NOW)) == 1
    assert len(second.reference_images) == 4
    assert second.reference_images == first.reference_images


def test_same_completion_key_with_different_payload_is_not_overwritten(tmp_path) -> None:
    repository = SqliteSearchHistoryRepository(tmp_path / "history.sqlite3")
    original = repository.save(history_write(title="最初の商品"), now=NOW)

    with pytest.raises(HistoryConflictError, match="^Search history completion conflicts$"):
        repository.save(history_write(title="異なる商品"), now=NOW)

    stored = repository.get(owner_id="owner-a", locator=original.locator, now=NOW)
    assert stored.result_snapshot[0].title == "最初の商品"


def test_same_completion_key_is_independent_between_owners(tmp_path) -> None:
    repository = SqliteSearchHistoryRepository(tmp_path / "history.sqlite3")

    owner_a = repository.save(history_write(owner_id="owner-a"), now=NOW)
    owner_b = repository.save(history_write(owner_id="owner-b"), now=NOW)

    assert owner_a.locator != owner_b.locator
    assert [entry.locator for entry in repository.list(owner_id="owner-a", now=NOW)] == [
        owner_a.locator
    ]
    assert [entry.locator for entry in repository.list(owner_id="owner-b", now=NOW)] == [
        owner_b.locator
    ]


def test_wrong_owner_and_unknown_locator_have_same_fixed_failure(tmp_path) -> None:
    repository = SqliteSearchHistoryRepository(tmp_path / "history.sqlite3")
    saved = repository.save(history_write(), now=NOW)

    failures: list[str] = []
    for owner_id, locator in (
        ("owner-b", saved.locator),
        ("owner-a", "x" * 43),
    ):
        with pytest.raises(HistoryNotFoundError) as raised:
            repository.get(owner_id=owner_id, locator=locator, now=NOW)
        failures.append(str(raised.value))

    assert failures == ["Search history was not found"] * 2


def test_detail_and_image_are_public_allowlist_models(tmp_path) -> None:
    repository = SqliteSearchHistoryRepository(tmp_path / "history.sqlite3")
    saved = repository.save(history_write(with_images=True), now=NOW)
    public_detail = saved.model_dump(mode="json")

    assert set(public_detail) == {
        "schema_version",
        "locator",
        "completed_at",
        "expires_at",
        "summary",
        "source_text",
        "condition_snapshot",
        "reference_image_mode",
        "reference_images",
        "ranking_profile_id",
        "candidate_limit",
        "compared_count",
        "outcome",
        "result_snapshot",
    }
    assert "owner_id" not in repr(saved)
    assert "completion_key" not in repr(saved)
    assert "history_id" not in repr(saved)
    assert all("sha256" not in item for item in public_detail["reference_images"])

    image_ref = saved.reference_images[0]
    loaded = repository.get_image(
        owner_id="owner-a",
        image_locator=image_ref.locator,
        now=NOW,
    )
    assert loaded.body == reference_images()[0].body
    assert "body" not in loaded.model_dump(mode="json")
    assert "sha256" not in loaded.model_dump(mode="json")


def test_individual_delete_checks_owner_and_removes_owned_images(tmp_path) -> None:
    repository = SqliteSearchHistoryRepository(tmp_path / "history.sqlite3")
    saved = repository.save(history_write(with_images=True), now=NOW)
    image_locator = saved.reference_images[0].locator

    with pytest.raises(HistoryNotFoundError, match="^Search history was not found$"):
        repository.delete(owner_id="owner-b", locator=saved.locator)
    assert repository.get(owner_id="owner-a", locator=saved.locator, now=NOW) == saved

    repository.delete(owner_id="owner-a", locator=saved.locator)

    assert repository.list(owner_id="owner-a", now=NOW) == ()
    with pytest.raises(HistoryNotFoundError, match="^Search history was not found$"):
        repository.get_image(
            owner_id="owner-a",
            image_locator=image_locator,
            now=NOW,
        )


def test_expired_entry_is_hidden_before_idempotent_physical_purge(tmp_path) -> None:
    repository = SqliteSearchHistoryRepository(tmp_path / "history.sqlite3")
    saved = repository.save(history_write(with_images=True), now=NOW)
    expires_at = NOW + timedelta(days=30)

    assert repository.list(owner_id="owner-a", now=expires_at) == ()
    with pytest.raises(HistoryNotFoundError, match="^Search history was not found$"):
        repository.get(owner_id="owner-a", locator=saved.locator, now=expires_at)
    with pytest.raises(HistoryNotFoundError, match="^Search history was not found$"):
        repository.get_image(
            owner_id="owner-a",
            image_locator=saved.reference_images[0].locator,
            now=expires_at,
        )

    assert repository.purge_expired(now=expires_at) == 1
    assert repository.purge_expired(now=expires_at) == 0
    with sqlite3.connect(repository.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM search_history").fetchone()[0] == 0
        assert (
            connection.execute("SELECT COUNT(*) FROM history_reference_images").fetchone()[0] == 0
        )


def test_already_expired_snapshot_is_rejected_without_write(tmp_path) -> None:
    repository = SqliteSearchHistoryRepository(tmp_path / "history.sqlite3")

    with pytest.raises(
        history_repository.HistoryInputError, match="^Search history input is invalid$"
    ):
        repository.save(history_write(), now=NOW + timedelta(days=30))

    assert repository.list(owner_id="owner-a", now=NOW) == ()


def test_image_insert_failure_rolls_back_entry_and_assets(tmp_path, monkeypatch) -> None:
    repository = SqliteSearchHistoryRepository(tmp_path / "history.sqlite3")
    monkeypatch.setattr(history_repository.secrets, "token_urlsafe", lambda _size: "z" * 43)

    with pytest.raises(HistoryStorageError, match="^Search history storage operation failed$"):
        repository.save(history_write(with_images=True), now=NOW)

    with sqlite3.connect(repository.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM search_history").fetchone()[0] == 0
        assert (
            connection.execute("SELECT COUNT(*) FROM history_reference_images").fetchone()[0] == 0
        )


def test_delete_failure_rolls_back_entry_and_assets(tmp_path) -> None:
    repository = SqliteSearchHistoryRepository(tmp_path / "history.sqlite3")
    saved = repository.save(history_write(with_images=True), now=NOW)
    image_locator = saved.reference_images[0].locator
    with sqlite3.connect(repository.path) as connection:
        connection.execute(
            """
            CREATE TRIGGER block_history_delete
            BEFORE DELETE ON search_history
            BEGIN
                SELECT RAISE(ABORT, 'blocked');
            END
            """
        )

    with pytest.raises(HistoryStorageError, match="^Search history storage operation failed$"):
        repository.delete(owner_id="owner-a", locator=saved.locator)

    assert repository.get(owner_id="owner-a", locator=saved.locator, now=NOW) == saved
    loaded = repository.get_image(
        owner_id="owner-a",
        image_locator=image_locator,
        now=NOW,
    )
    assert loaded.body == reference_images()[0].body


def test_valid_but_modified_detail_json_is_rejected(tmp_path) -> None:
    repository = SqliteSearchHistoryRepository(tmp_path / "history.sqlite3")
    saved = repository.save(history_write(), now=NOW)
    with sqlite3.connect(repository.path) as connection:
        stored = connection.execute(
            "SELECT detail_json FROM search_history WHERE locator = ?",
            (saved.locator,),
        ).fetchone()[0]
        modified = json.loads(stored)
        modified["summary"] = "書き換えられた要約"
        connection.execute(
            "UPDATE search_history SET detail_json = ? WHERE locator = ?",
            (
                json.dumps(
                    modified,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                saved.locator,
            ),
        )

    with pytest.raises(HistoryStorageError, match="^Search history storage operation failed$"):
        repository.get(owner_id="owner-a", locator=saved.locator, now=NOW)


def test_strict_snapshot_rejects_invalid_result_and_image_shapes() -> None:
    valid = history_write().model_dump()

    with pytest.raises(ValidationError):
        SearchHistoryWrite.model_validate({**valid, "unexpected": "value"})
    with pytest.raises(ValidationError):
        SearchHistoryWrite.model_validate(
            {
                **valid,
                "completed_at": NOW.replace(tzinfo=None),
            }
        )
    with pytest.raises(ValidationError):
        SearchHistoryWrite.model_validate(
            {
                **valid,
                "outcome": "empty",
            }
        )
    with pytest.raises(ValidationError):
        SearchHistoryWrite.model_validate(
            {
                **valid,
                "reference_image_mode": "on",
                "reference_images": reference_images()[:3],
            }
        )


def test_unknown_schema_version_is_rejected_without_modification(tmp_path) -> None:
    path = tmp_path / "history.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 99")
    path.chmod(0o600)

    with pytest.raises(HistoryStorageError, match="^Search history storage operation failed$"):
        SqliteSearchHistoryRepository(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 99


def test_legacy_v1_database_is_rejected_without_modification(tmp_path) -> None:
    path = tmp_path / "history.sqlite3"
    SqliteSearchHistoryRepository(path)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 1")
    before = path.read_bytes()

    with pytest.raises(HistoryStorageError, match="^Search history storage operation failed$"):
        SqliteSearchHistoryRepository(path)

    assert path.read_bytes() == before


@pytest.mark.skipif(os.name != "posix", reason="POSIX file mode contract")
def test_existing_insecure_database_is_rejected_without_chmod(tmp_path) -> None:
    path = tmp_path / "history.sqlite3"
    path.touch(mode=0o644)
    path.chmod(0o644)

    with pytest.raises(HistoryStorageError, match="^Search history storage operation failed$"):
        SqliteSearchHistoryRepository(path)

    assert stat.S_IMODE(path.stat().st_mode) == 0o644
