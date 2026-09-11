from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
import hashlib
from io import BytesIO

from PIL import Image
import pytest

from src.search_v2.history_repository import SqliteSearchHistoryRepository
from src.search_v2.provisional_history_repository import (
    ProvisionalHistoryProductView,
)
from src.search_v2.provisional_history_repository import ProvisionalHistoryNotFoundError
from src.search_v2.provisional_history_repository import (
    ProvisionalHistoryReferenceImageWrite,
)
from src.search_v2.provisional_history_repository import (
    ProvisionalHistoryWrite,
)
from src.search_v2.provisional_history_repository import (
    SqliteProvisionalHistoryRepository,
)


NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)


def png(color: tuple[int, int, int]) -> bytes:
    output = BytesIO()
    Image.new("RGB", (512, 512), color).save(output, format="PNG")
    return output.getvalue()


def reference(
    target: str,
    condition_id: str | None,
    color: tuple[int, int, int],
) -> ProvisionalHistoryReferenceImageWrite:
    body = png(color)
    return ProvisionalHistoryReferenceImageWrite(
        schema_version="5.0",
        target=target,
        condition_id=condition_id,
        content_type="image/png",
        sha256=hashlib.sha256(body).hexdigest(),
        byte_length=len(body),
        width=512,
        height=512,
        body=body,
    )


def pending() -> ProvisionalHistoryWrite:
    return ProvisionalHistoryWrite(
        schema_version="5.0",
        owner_id="owner-1",
        completion_key="a" * 64,
        completed_at=NOW,
        summary="黒いヘッドレスト付きオフィスチェア",
        provisional_profile_id="counterfactual-v4-provisional-production-v1",
        known_holdout_accuracy=0.875,
        ranking_profile_id="typed-ranking-v5-counterfactual-provisional",
        ranking_profile_sha256="b" * 64,
        source_typed_ranked_product_batch_sha256="c" * 64,
        condition_set_sha256="d" * 64,
        reference_set_sha256="e" * 64,
        runtime_sha256="f" * 64,
        reference_images=(
            reference("desired", None, (10, 20, 30)),
            reference("counterfactual", "visual-condition-001", (40, 50, 60)),
        ),
        products=(
            ProvisionalHistoryProductView(
                schema_version="5.0",
                rank=1,
                title="商品1",
                price_jpy=12_000,
                product_url="https://www.amazon.co.jp/dp/B000000001",
                required_status="confirmed",
                image_component_status="available",
                image_score=0.75,
                total_score=0.8,
            ),
        ),
    )


def test_v5_history_reopens_with_profile_accuracy_and_image_state(tmp_path) -> None:
    path = tmp_path / "provisional-history.sqlite3"
    repository = SqliteProvisionalHistoryRepository(path)
    detail = repository.save(pending(), now=NOW + timedelta(seconds=1))

    reopened = SqliteProvisionalHistoryRepository(path)
    loaded = reopened.get(owner_id="owner-1", locator=detail.locator, now=NOW)

    assert loaded.schema_version == "5.0"
    assert loaded.known_holdout_accuracy == 0.875
    assert loaded.source_typed_ranked_product_batch_sha256 == "c" * 64
    assert loaded.products[0].image_component_status == "available"
    assert tuple(item.target for item in loaded.reference_images) == (
        "desired",
        "counterfactual",
    )
    assert (
        reopened.get_image(
            owner_id="owner-1",
            image_locator=loaded.reference_images[0].locator,
            now=NOW,
        ).body
        == pending().reference_images[0].body
    )


def test_v5_history_is_owner_scoped_and_not_readable_as_legacy_v2(tmp_path) -> None:
    path = tmp_path / "provisional-history.sqlite3"
    repository = SqliteProvisionalHistoryRepository(path)
    detail = repository.save(pending(), now=NOW)

    with pytest.raises(Exception, match="not found"):
        repository.get(owner_id="owner-2", locator=detail.locator, now=NOW)
    with pytest.raises(Exception, match="storage"):
        SqliteSearchHistoryRepository(path)

    image_locator = detail.reference_images[0].locator
    repository.delete(owner_id="owner-1", locator=detail.locator)
    with pytest.raises(ProvisionalHistoryNotFoundError):
        repository.get_image(
            owner_id="owner-1",
            image_locator=image_locator,
            now=NOW,
        )


def test_v5_history_requires_desired_then_condition_counterfactuals() -> None:
    original = pending()
    value = {name: getattr(original, name) for name in type(original).model_fields}
    value["reference_images"] = tuple(reversed(value["reference_images"]))

    with pytest.raises(ValueError, match="ordering"):
        ProvisionalHistoryWrite.model_validate(value)
