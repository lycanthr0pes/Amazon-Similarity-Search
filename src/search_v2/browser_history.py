"""Read configured local history stores without launching any search providers."""

import base64
from datetime import datetime, timezone
from pathlib import Path
import re

from src.search_v2.product_links import japanese_product_url
from src.search_v2.provisional_history_repository import (
    SqliteProvisionalHistoryRepository,
    ProvisionalHistoryNotFoundError,
    ProvisionalHistoryStorageError,
    ProvisionalHistoryError,
)


class BrowserHistory:
    def __init__(self, paths=(), *, now=None):
        if len(paths) > 32:
            raise ValueError("Too many history stores")
        self.paths = tuple(dict.fromkeys(Path(p).absolute() for p in paths))
        self.now = now or (lambda: datetime.now(timezone.utc))
        self._cleanup_failed = False

    def _repository(self, path, *, writable=False):
        if path.resolve() != path or path.is_symlink():
            raise ProvisionalHistoryStorageError("History storage unavailable")
        return SqliteProvisionalHistoryRepository(
            path, read_only=not writable, existing_only=writable
        )

    def delete(self, locator):
        if type(locator) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", locator):
            raise ValueError("Invalid history locator")
        for path in self.paths:
            if not path.exists() and not path.is_symlink():
                continue
            try:
                self._repository(path, writable=True).delete(owner_id="local-user", locator=locator)
            except ProvisionalHistoryNotFoundError:
                pass  # Already absent, including a lost response or an expiry race.

    def purge_expired(self):
        now = self.now()
        deleted, failed = 0, False
        for path in self.paths:
            if not path.exists() and not path.is_symlink():
                continue
            try:
                deleted += self._repository(path, writable=True).purge_expired(
                    now=now, owner_id="local-user"
                )
            except (ProvisionalHistoryError, OSError, ValueError):
                failed = True  # Continue other stores; retry failures on the next sweep.
        self._cleanup_failed = failed
        if failed:
            raise ProvisionalHistoryStorageError("History cleanup incomplete")
        return deleted

    def _repositories(self):
        for path in self.paths:
            # Current runs create their database only after explicit execution.
            if path.exists() or path.is_symlink():
                yield self._repository(path)

    def list(self):
        now = self.now()
        items = [
            item
            for repo in self._repositories()
            for item in repo.list(owner_id="local-user", now=now)
        ]
        items.sort(key=lambda item: (item.completed_at, item.locator), reverse=True)
        unique = {item.locator: item for item in items}
        return {
            "items": [history_item(item) for item in list(unique.values())[:30]],
            **({"cleanupPending": True} if self._cleanup_failed else {}),
        }

    def get(self, locator):
        if type(locator) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", locator):
            raise LookupError("History unavailable")
        now = self.now()
        for repo in self._repositories():
            try:
                detail = repo.get(owner_id="local-user", locator=locator, now=now)
            except ProvisionalHistoryNotFoundError:
                continue
            images = [
                repo.get_image(owner_id="local-user", image_locator=ref.locator, now=now)
                for ref in detail.reference_images
            ]
            return {
                **history_item(detail),
                "view": {
                    "stage": "complete",
                    "revision": 0,
                    "saved": True,
                    **({"imageMode": "off"} if detail.image_mode == "off" else {}),
                    "sortProfile": detail.sort_profile_id,
                    "input": detail.summary,
                    **(detail.history_content.browser_fields() if detail.history_content else {}),
                    "images": [
                        "data:image/png;base64," + base64.b64encode(image.body).decode("ascii")
                        for image in images
                    ],
                    "products": [history_product(product) for product in detail.products],
                },
            }
        raise LookupError("History unavailable")


def history_item(item):
    return {
        "id": item.locator,
        "summary": item.summary,
        **({"productName": item.product_name} if item.product_name else {}),
        "completedAt": item.completed_at.isoformat(),
        "expiresAt": item.expires_at.isoformat(),
        "count": len(item.products) if hasattr(item, "products") else item.compared_count,
    }


def history_product(product):
    return {
        "title": product.title,
        **({"thumbnail": product.thumbnail_png} if product.thumbnail_png else {}),
        "reviewRating": product.review_rating,
        **(
            {"titleEn": product.title_en, "titleEnStatus": product.title_en_status}
            if product.title_en_status is not None
            else {}
        ),
        **(
            {
                "scores": {
                    "title": product.title_scores.model_dump(mode="json"),
                    "conditions": [s.model_dump(mode="json") for s in product.condition_scores],
                    "image": product.image_score,
                    **(
                        {"textImage": product.visual_text.score}
                        if product.visual_text is not None
                        else {}
                    ),
                    "total": product.total_score,
                }
            }
            if product.title_scores is not None
            else {}
        ),
        "price": product.price_jpy,
        "url": japanese_product_url(product.product_url),
        "required": {"confirmed": "一致", "uncertain": "未確認", "contradicted": "不一致"}[
            product.required_status
        ],
        "appearance": "視覚条件の文章・参考画像による外観補助"
        if product.visual_text is not None and product.visual_text.score is not None
        else "参考画像による外観補助"
        if product.image_component_status == "available"
        else "画像比較は使用していません"
        if product.image_component_status == "not_used"
        else "外観は未確認",
    }
