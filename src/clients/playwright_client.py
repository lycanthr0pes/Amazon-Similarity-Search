"""CLI compatibility adapter backed only by the local Playwright worker."""

from src.config import settings
from src.search_v2.playwright_products import fetch_product_data
from src.utilities.json_editor import write_json


def call_playwright(query, cache_key):
    if not cache_key or any(c not in "0123456789abcdef" for c in cache_key):
        raise ValueError("Invalid product cache key")
    result = fetch_product_data([query], limit=settings.playwright_limit)
    path = settings.cache_dir / "playwright-v3" / "raw" / f"{cache_key}.json"
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    write_json(path, {"provider": "playwright", "data": result["data"]})
    return path
