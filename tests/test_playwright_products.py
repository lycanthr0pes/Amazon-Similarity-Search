"""Provider migration, request binding and credential-free process boundaries."""

import json

import pytest

import test_candidate_search as candidate


def test_new_candidate_uses_playwright_and_preserves_old_plan(tmp_path):
    service = candidate.start(tmp_path)
    assert service.plan.request.provider == "playwright"
    assert service.plan.request.endpoint == "https://www.amazon.co.jp/s"
    from src.search_v2.product_request import rebuild_product_request, product_request_sha256
    from src.search_v2.outscraper_contract import build_outscraper_request

    old = build_outscraper_request(service.plan.query_plan, postal_code="100-0001")
    assert product_request_sha256(old) != product_request_sha256(service.plan.request)
    assert rebuild_product_request(old, service.plan.query_plan) == old
    plan = service.plan.model_copy(update={"request": old})
    restored = type(plan).model_validate_json(plan.model_dump_json())
    assert restored.request.provider == "outscraper"


def test_playwright_normalization_and_history_provenance(tmp_path):
    service = candidate.start(tmp_path)
    review, _ = candidate.retrieve(service, tmp_path)
    option = next(o for o in review.options if o.label == "光学解像度")
    service.confirm(
        owner_id="owner-1",
        review_sha256=review.sha256,
        selections={"condition-001": option.option_id},
        now=candidate.flow.NOW,
    )
    result = service.rank(owner_id="owner-1", now=candidate.flow.NOW)
    assert result.products[0].product.provenance.provider == "playwright"


def test_browser_transport_binds_request_once_without_api_key(tmp_path):
    from src.search_v2.playwright_products import PlaywrightProducts
    from src.search_v2.product_request import product_request_sha256

    request = candidate.start(tmp_path).plan.request
    calls = []

    def worker(payload):
        calls.append(payload)
        return {"data": [[{"asin": "B000CA0001", "name": "合成スキャナー"}]], "metrics": {}}

    transport = PlaywrightProducts(request, worker=worker)
    fetched = transport.fetch(request)
    assert fetched.request_sha256 == product_request_sha256(request)
    assert fetched.provider_request_id.startswith("playwright-")
    assert calls[0]["queries"] == [request.queries[0].value]
    assert not any("key" in k or "token" in k for k in calls[0])
    with pytest.raises(ValueError):
        transport.fetch(request)


def test_worker_failure_does_not_expose_query_or_exception(tmp_path):
    from src.search_v2.playwright_products import PlaywrightProducts, ProductFetchError

    request = candidate.start(tmp_path).plan.request

    def broken(payload):
        raise RuntimeError("private-provider-content")

    with pytest.raises(ProductFetchError) as failure:
        PlaywrightProducts(request, worker=broken).fetch(request)
    assert "private-provider-content" not in str(failure.value)


def test_worker_environment_drops_credentials(monkeypatch):
    from src.search_v2.playwright_products import worker_environment

    monkeypatch.setenv("OUTSCRAPER_API_KEY", "private-fixture")
    monkeypatch.setenv("DEBUG", "pw:*")
    monkeypatch.setenv("HTTPS_PROXY", "https://example.invalid")
    environment = worker_environment()
    assert not {"OUTSCRAPER_API_KEY", "DEBUG", "HTTPS_PROXY"} & environment.keys()
    assert "private-fixture" not in json.dumps(environment)


def test_legacy_adapter_does_not_send_credentials_or_poll(monkeypatch):
    from src.search_v2.playwright_compat import PlaywrightTaskTransport

    calls = []
    monkeypatch.setattr(
        "src.search_v2.playwright_compat.fetch_product_data",
        lambda queries: calls.append(queries) or {"data": [[]], "metrics": {}},
    )
    args = dict(
        url="https://api.outscraper.cloud/amazon-products",
        params=(
            ("query", "合成カップ"),
            ("domain", "amazon.co.jp"),
            ("language", "ja"),
            ("postal_code", "100-0001"),
            ("limit", "24"),
            ("async", "true"),
        ),
        api_key="must-not-be-used",
        timeout_seconds=30,
        allow_redirects=False,
        accept_encoding="identity",
        maximum_response_bytes=8 * 1024 * 1024,
    )
    result = PlaywrightTaskTransport().get(**args)
    assert result.status_code == 200 and calls == [["合成カップ"]]
    assert b"must-not-be-used" not in b"".join(result.body_chunks)
    with pytest.raises(ValueError):
        PlaywrightTaskTransport().get(
            **{**args, "url": "https://api.outscraper.cloud/requests/task", "params": ()}
        )


def test_cache_keys_do_not_reuse_outscraper(tmp_path, monkeypatch):
    from src.main.run import build_outscraper_cache_key, build_playwright_cache_key
    from src.config import settings
    from src.clients.playwright_client import call_playwright

    assert build_outscraper_cache_key("合成") != build_playwright_cache_key("合成")
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    monkeypatch.setattr(settings, "outscraper_api_key", "")
    monkeypatch.setattr(
        "src.clients.playwright_client.fetch_product_data",
        lambda *a, **kw: {"data": [[]], "metrics": {}},
    )
    path = call_playwright("合成", "a" * 64)
    assert path.parent == tmp_path / "playwright-v3" / "raw"
    assert json.loads(path.read_text())["provider"] == "playwright"


@pytest.mark.parametrize(
    "response",
    [
        {"data": []},
        {"data": [[]], "metrics": {}, "raw": "private"},
        {"data": [[{"query": "other"}]], "metrics": {}},
    ],
)
def test_malformed_worker_response_is_rejected(response):
    from src.search_v2.playwright_products import fetch_product_data, ProductFetchError

    with pytest.raises(ProductFetchError):
        fetch_product_data(["合成"], worker=lambda _: response)


def test_browser_adapter_through_ranking_and_sqlite(tmp_path, monkeypatch):
    import test_candidate_connected_flow as connected
    from src.search_v2.playwright_products import PlaywrightProducts

    flow, _, _, history, clock = connected.start(tmp_path)
    connected.approve(flow)
    products = candidate.scanner_products()
    for index, product in enumerate(products, 1):
        product.update(
            price=8000, currency="JPY", image_1=f"https://m.media-amazon.com/images/{index}.png"
        )
    transport = PlaywrightProducts(
        flow.plan.request, worker=lambda _: {"data": [products], "metrics": {}}
    )
    review = flow.approve_and_fetch(
        owner_id=connected.OWNER, plan_sha256=flow.plan_sha256, transport=transport
    )
    flow.confirm(owner_id=connected.OWNER, review_sha256=review.sha256, selections={})
    kwargs, _ = connected.clip(monkeypatch, tmp_path)
    result = flow.complete(owner_id=connected.OWNER, **kwargs)
    assert len(result.history.products) == 3
    assert result.history.retrieval_provider == "playwright"
    assert result.ranking.source.product_batch.provider == "playwright"
    assert (
        history.get(owner_id=connected.OWNER, locator=result.history.locator, now=clock[0])
        == result.history
    )


def test_live_entry_factory_never_loads_outscraper_key(tmp_path, monkeypatch):
    from dataclasses import replace
    import test_candidate_search_live_e2e as entry
    from src.search_v2.playwright_products import PlaywrightProducts

    _, config, services, _, _ = entry.setup_run(tmp_path, monkeypatch)

    def forbidden():
        pytest.fail("Outscraper credential loader was called")

    products = [
        {
            "asin": "B000CA0001",
            "name": "合成マグカップ",
            "price": 2000,
            "currency": "JPY",
            "image_1": "https://m.media-amazon.com/images/1.png",
        }
    ]

    def factory(request):
        return PlaywrightProducts(request, worker=lambda _: {"data": [products], "metrics": {}})

    result = entry.module().run_candidate_e2e(
        config,
        replace(
            services,
            load_outscraper_api_key=forbidden,
            outscraper_transport=None,
            product_transport_factory=factory,
        ),
        image_score_mode="appearance",
    )
    assert result["status"] == "succeeded"
    assert result["outscraper_tasks"] == result["outscraper_polls"] == 0


def test_saved_outscraper_plan_is_migrated_only_for_new_retrieval():
    import test_candidate_search_retry as retry

    saved = retry.original()
    from src.search_v2.outscraper_contract import build_outscraper_request
    from src.search_v2.candidate_search import CandidatePlan, CandidateSearch, _digest

    old = CandidatePlan.model_validate(
        saved.plan.model_copy(
            update={
                "request": build_outscraper_request(saved.plan.query_plan, postal_code="100-0001")
            }
        )
    )
    renewed = CandidateSearch.from_approved_plan(
        old,
        source="マグカップ。3000円以下。",
        owner_id="local-user",
        plan_sha256=_digest(old),
        human_confirmed=True,
        normalization_profile=candidate.flow.backend_policy().normalization_profile,
        now=candidate.flow.NOW,
        use_playwright=True,
    )
    assert old.request.provider == "outscraper"
    assert renewed.plan.request.provider == "playwright"
    assert renewed.plan.expires_at is None
    assert renewed.plan.source_sha256 == old.source_sha256
