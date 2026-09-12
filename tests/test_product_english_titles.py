"""Bilingual observations survive normalization, storage and browser projection."""

import json
from types import SimpleNamespace

import pytest
import test_search_v2_product_normalization as normalization
import test_candidate_connected_flow as connected
import test_candidate_search as candidate
from src.search_v2.browser_candidate import BrowserCandidateRun, candidate_browser_steps
from src.search_v2.product_request import (
    PlaywrightSearchRequest,
    product_request_sha256,
    rebuild_product_request,
)


def test_new_request_opts_in_and_old_request_roundtrips(tmp_path):
    flow = candidate.start(tmp_path)
    request = flow.plan.request
    assert request.english_titles is True
    old_json = request.model_dump(mode="json")
    old_json.pop("english_titles")
    old_json.pop("english_details")
    old = PlaywrightSearchRequest.model_validate_json(json.dumps(old_json))
    assert old.model_dump(mode="json") == old_json
    assert rebuild_product_request(old, flow.plan.query_plan) == old
    assert product_request_sha256(old) != product_request_sha256(request)


def test_bilingual_observations_reach_history_and_browser(tmp_path, monkeypatch):
    flow, images, _, history, clock = connected.start(tmp_path)
    ranking, _ = connected.clip(monkeypatch, tmp_path)
    products = candidate.scanner_products()
    products[0].update(name_en="Synthetic Scanner A", title_en_status="available")
    products[1].update(name_en=None, title_en_status="unavailable")
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
            assets=ranking["asset_root"],
            encoder=ranking["encoder"],
        )
    )
    run.execute("start", {})
    run.execute("reference", {"index": 0})
    run.execute("comparison", {})
    run.execute("final", {})
    result = run.execute("search", {})
    assert result["stage"] == "complete"
    rows = {row["title"]: row for row in result["products"]}
    assert rows["スキャナーA"]["titleEn"] == "Synthetic Scanner A"
    assert rows["スキャナーA"]["titleEnStatus"] == "available"
    assert rows["スキャナーB"]["titleEn"] is None
    assert rows["スキャナーB"]["titleEnStatus"] == "unavailable"
    assert "titleEn" not in rows["スキャナーC"]
    saved = history.list(owner_id=connected.OWNER, now=clock[0])[0]
    detail = history.get(owner_id=connected.OWNER, locator=saved.locator, now=clock[0])
    stored = {row.title: row for row in detail.products}
    assert stored["スキャナーA"].title_en == "Synthetic Scanner A"
    old = stored["スキャナーC"].model_dump(mode="json")
    assert "title_en" not in old and "title_en_status" not in old
    assert (
        type(stored["スキャナーC"]).model_validate_json(json.dumps(old)).model_dump(mode="json")
        == old
    )
    run.close()


@pytest.mark.parametrize("value", [None, "", [], " " * 100])
def test_missing_english_text_preserves_primary_product(value):
    batch = normalization.normalize(
        {
            "data": [
                [
                    {
                        "name": "合成商品",
                        "name_en": value,
                        "title_en_status": "available",
                    }
                ],
                [],
            ]
        }
    )
    product = batch.products[0]
    assert product.title == "合成商品"
    assert product.title_en_status == "unavailable"
    assert product.title_en is None
    with pytest.raises(ValueError, match="English title"):
        type(product).model_validate(product.model_copy(update={"title_en_status": "available"}))


def test_english_observation_is_bounded_and_legacy_serialization_is_unchanged():
    original = {"name": "合成商品"}
    old = normalization.normalize({"data": [[original], []]}).products[0]
    serialized = old.model_dump(mode="json")
    assert "title_en" not in serialized
    assert (
        type(old).model_validate_json(json.dumps(serialized)).model_dump(mode="json") == serialized
    )
    product = normalization.normalize(
        {
            "data": [
                [
                    {
                        **original,
                        "name_en": "A" * 600,
                        "title_en_status": "available",
                    }
                ],
                [],
            ]
        }
    ).products[0]
    assert len(product.title_en) == 500
    assert "title_en" in product.truncated_fields
