"""Private history preserves display content without revisiting providers."""

from types import SimpleNamespace

import pytest
import test_candidate_connected_flow as connected
import test_candidate_search as candidate

from src.search_v2.browser_candidate import BrowserCandidateRun, candidate_browser_steps
from src.search_v2.browser_history import BrowserHistory
from src.search_v2.condition_terms import LocalConditionExpander
from src.search_v2.provisional_history_repository import SqliteProvisionalHistoryRepository


@pytest.mark.parametrize("image_free", [False, True])
def test_reopen_preserves_source_labels_and_product_images(tmp_path, monkeypatch, image_free):
    monkeypatch.setattr(connected, "OWNER", "local-user")
    flow, images, _, history, clock = connected.start(
        tmp_path, plan_lifetime=None, condition_expander=LocalConditionExpander()
    )
    ranking, calls = connected.clip(monkeypatch, tmp_path)
    products = candidate.scanner_products()
    for index, product in enumerate(products):
        product["image_1"] = f"https://m.media-amazon.com/images/{index}.png"
    transport = candidate.ProductTransport(products, tmp_path)
    run = BrowserCandidateRun(
        candidate_browser_steps(
            flow,
            owner=connected.OWNER,
            images=SimpleNamespace(previews=lambda: ["fixture"] * len(images.calls)),
            products=lambda _: transport,
            history=history,
            now=lambda: clock[0],
            proxy=ranking["proxy_service"],
            thumbnail_factory=lambda: ranking["proxy_service"],
            assets=ranking["asset_root"],
            encoder=ranking["encoder"],
        )
    )
    query = run.execute("start", {})
    if image_free:
        run.execute("without_images", {"index": 0})
    else:
        run.execute("reference", {"index": 0})
        run.execute("comparison", {})
        run.execute("final", {})
    result = run.execute("search", {})
    before = (len(transport.calls), ranking["proxy_service"].calls)
    browser = BrowserHistory([tmp_path / "history.sqlite3"], now=lambda: clock[0])
    item = browser.list()["items"][0]
    view = browser.get(item["id"])["view"]
    assert view.get("historyContentAvailable") is True
    assert view["input"] == flow._source
    assert view["conditionLabels"] == query["conditionLabels"]
    assert view["conditionReview"] == query["conditionReview"]
    assert [p.get("thumbnail") for p in view["products"]] == [
        p["thumbnail"] for p in result["products"]
    ]
    fresh = SqliteProvisionalHistoryRepository(tmp_path / "history.sqlite3", read_only=True)
    detail = fresh.get(owner_id=connected.OWNER, locator=item["id"], now=clock[0])
    assert detail.history_content.source_text == flow._source
    assert (len(transport.calls), ranking["proxy_service"].calls) == before
    assert before == (1, len(products))
    if image_free:
        assert not calls and not images.calls
        assert any(p.thumbnail_png for p in detail.products)
        assert all(
            p.image_score is None and p.image_component_status == "not_used"
            for p in detail.products
        )
        assert detail.reference_images == ()


def content_write():
    from tests.test_search_v2_provisional_history_repository import pending
    from src.search_v2.history_content import HistoryContent
    from src.search_v2.condition_language import ConditionExpression
    from io import BytesIO
    import base64
    from PIL import Image

    source = "合成入力。\n" + "あ" * 510 + "。取っ手がなくてもよい。"
    quote = "取っ手がなくてもよい"
    content = HistoryContent(
        source_text=source,
        condition_labels={"condition-001": "光学解像度"},
        condition_review=(
            ConditionExpression(
                start=source.index(quote),
                end=source.index(quote) + len(quote),
                quote=quote,
                target="取っ手",
                strength="neutral",
                reason="permission",
            ),
        ),
    )
    buffer = BytesIO()
    Image.new("RGB", (192, 128), "red").save(buffer, format="PNG")
    png = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    write = pending()
    return write.model_copy(
        update={
            "owner_id": "local-user",
            "history_content": content,
            "products": (write.products[0].model_copy(update={"thumbnail_png": png}),)
            + write.products[1:],
        }
    )


@pytest.mark.parametrize("deletion", ["delete", "expiry"])
def test_long_input_png_and_neutral_survive_restart_then_delete_together(tmp_path, deletion):
    import sqlite3
    from datetime import timedelta
    from tests.test_search_v2_provisional_history_repository import NOW

    path = tmp_path / "history.sqlite3"
    write = content_write()
    repo = SqliteProvisionalHistoryRepository(path)
    first = repo.save(write, now=NOW)
    assert repo.save(write, now=NOW) == first
    browser = BrowserHistory([path], now=lambda: NOW)
    view = browser.get(first.locator)["view"]
    assert len(view["input"]) > 500
    assert view["input"] == write.history_content.source_text
    assert view["conditionReview"][0]["strength"] == "neutral"
    assert view["products"][0]["thumbnail"] == write.products[0].thumbnail_png
    assert not any(p.get("thumbnail") for p in view["products"][1:])
    if deletion == "delete":
        browser.delete(first.locator)
    else:
        browser = BrowserHistory([path], now=lambda: NOW + timedelta(days=30))
        assert browser.list() == {"items": []}
        assert browser.purge_expired() == 1
    with pytest.raises(LookupError):
        browser.get(first.locator)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM provisional_history").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM provisional_history_images").fetchone()[0] == 0
    assert write.history_content.source_text.encode() not in path.read_bytes()
    assert write.products[0].thumbnail_png.encode() not in path.read_bytes()


def test_content_retry_conflict_rollback_and_legacy_omission(tmp_path):
    import sqlite3
    from tests.test_search_v2_provisional_history_repository import NOW, pending
    from src.search_v2.provisional_history_repository import (
        ProvisionalHistoryConflictError,
        ProvisionalHistoryStorageError,
    )

    path = tmp_path / "history.sqlite3"
    repo = SqliteProvisionalHistoryRepository(path)
    write = content_write()
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TRIGGER stop BEFORE INSERT ON provisional_history_images BEGIN SELECT RAISE(ABORT, 'fixture'); END"
        )
    with pytest.raises(ProvisionalHistoryStorageError):
        repo.save(write, now=NOW)
    assert repo.list(owner_id="local-user", now=NOW) == ()
    with sqlite3.connect(path) as db:
        db.execute("DROP TRIGGER stop")
    saved = repo.save(write, now=NOW)
    altered = write.model_copy(
        update={
            "history_content": write.history_content.model_copy(
                update={"condition_labels": {"condition-001": "変更した合成条件"}}
            )
        }
    )
    with pytest.raises(ProvisionalHistoryConflictError):
        repo.save(altered, now=NOW)
    assert repo.get(owner_id="local-user", locator=saved.locator, now=NOW) == saved
    legacy = pending()
    assert "history_content" not in legacy.model_dump()
    assert all("thumbnail_png" not in p for p in legacy.model_dump()["products"])


@pytest.mark.parametrize(
    "change", ["source_range", "source_length", "thumbnail", "oversize_png", "missing_content"]
)
def test_rejects_invalid_persisted_content(tmp_path, change):
    from tests.test_search_v2_provisional_history_repository import NOW
    from src.search_v2.provisional_history_repository import ProvisionalHistoryInputError
    import base64
    from io import BytesIO
    from PIL import Image

    write = content_write()
    if change == "source_range":
        content = write.history_content.model_copy(update={"source_text": "別の原文"})
        write = write.model_copy(update={"history_content": content})
    elif change == "source_length":
        write = write.model_copy(
            update={
                "history_content": write.history_content.model_copy(
                    update={"source_text": "あ" * 2001}
                )
            }
        )
    elif change == "missing_content":
        write = write.model_copy(update={"history_content": None})
    else:
        thumbnail = "data:image/png;base64,bm90LXBuZw=="
        if change == "oversize_png":
            buffer = BytesIO()
            Image.new("RGB", (193, 1)).save(buffer, format="PNG")
            thumbnail = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
        write = write.model_copy(
            update={
                "products": (write.products[0].model_copy(update={"thumbnail_png": thumbnail}),)
                + write.products[1:]
            }
        )
    repo = SqliteProvisionalHistoryRepository(tmp_path / "history.sqlite3")
    with pytest.raises(ProvisionalHistoryInputError):
        repo.save(write, now=NOW)
    assert repo.list(owner_id="local-user", now=NOW) == ()


def test_snapshot_must_describe_the_completed_flow_source(tmp_path, monkeypatch):
    from src.search_v2.history_content import HistoryContent
    from src.search_v2.candidate_diagnostics import CandidateEvaluationError

    flow, images, _, history, clock = connected.start(tmp_path, plan_lifetime=None)
    transport = candidate.ProductTransport(candidate.scanner_products(), tmp_path)
    complete = flow.complete

    def changed_content(**kwargs):
        kwargs["history_content"] = HistoryContent(
            source_text="別の合成入力", condition_labels={}, condition_review=()
        )
        return complete(**kwargs)

    monkeypatch.setattr(flow, "complete", changed_content)
    run = BrowserCandidateRun(
        candidate_browser_steps(
            flow,
            owner=connected.OWNER,
            images=None,
            products=lambda _: transport,
            history=history,
            now=lambda: clock[0],
            proxy=None,
            assets=None,
            encoder=None,
        )
    )
    run.execute("start", {})
    run.execute("without_images", {"index": 0})
    with pytest.raises(CandidateEvaluationError):
        run.execute("search", {})
    assert history.list(owner_id=connected.OWNER, now=clock[0]) == ()


def test_display_only_images_deduplicate_cap_and_tolerate_failures():
    from src.search_v2.browser_candidate import BrowserProductImages

    calls = []

    def fetch(url):
        calls.append(url)
        if url.endswith("/0.png"):
            raise ValueError("Unavailable synthetic image")
        return SimpleNamespace(width=400, height=200, rgb_bytes=b"\xff\xff\xff" * 400 * 200)

    images = BrowserProductImages(SimpleNamespace(fetch_image=fetch))
    groups = [(f"https://m.media-amazon.com/images/{i}.png",) for i in range(30)]
    images.load_previews([(), groups[0], *groups])
    images.load_previews(groups)
    assert len(calls) == 24 and len(set(calls)) == 24
    assert images.preview(groups[0]) is None and images.preview(groups[-1]) is None
    from src.search_v2.history_content import validate_thumbnail

    assert validate_thumbnail(images.preview(groups[1]))
