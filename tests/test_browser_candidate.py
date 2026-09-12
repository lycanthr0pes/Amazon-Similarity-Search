"""The browser stops drive the real candidate state machine with offline providers."""

from types import SimpleNamespace
from datetime import timedelta

import pytest

import test_candidate_connected_flow as connected
import test_candidate_search as candidate

from src.search_v2.browser_candidate import BrowserCandidateRun, candidate_browser_steps


@pytest.mark.parametrize("condition_count", [1, 3])
@pytest.mark.parametrize("retry_at", ["reference", "comparison"])
def test_bounded_browser_transport_can_regenerate_a_complete_set(
    tmp_path, condition_count, retry_at
):
    from src.search_v2.browser_candidate import BrowserImages

    flow, transport, _, history, clock = connected.start(
        tmp_path, plan_lifetime=None, condition_count=condition_count
    )
    images = BrowserImages(transport)
    flow._transport = images
    run = BrowserCandidateRun(
        candidate_browser_steps(
            flow,
            owner=connected.OWNER,
            images=images,
            products=None,
            history=history,
            now=lambda: clock[0],
            proxy=None,
            assets=None,
            encoder=None,
        )
    )
    assert run.execute("start", {})["stage"] == "query"
    assert run.execute("reference", {"index": 0})["stage"] == "reference"
    first_seed = transport.calls[0]["request"].seed
    if retry_at == "comparison":
        assert run.execute("comparison", {})["stage"] == "comparison"
    reference = run.execute("regenerate", {})
    assert reference["stage"] == "reference" and len(reference["images"]) == 1
    assert transport.calls[-1]["request"].seed != first_seed
    comparison = run.execute("comparison", {})
    assert comparison["stage"] == "comparison"
    assert len(comparison["images"]) == 1 + condition_count
    assert not comparison["canRegenerate"]
    count = len(transport.calls)
    assert count == (2 + condition_count if retry_at == "reference" else 2 * (1 + condition_count))
    with pytest.raises(ValueError, match="image set limit"):
        run.execute("regenerate", {})
    assert len(transport.calls) == count
    run.close()


@pytest.mark.parametrize("japanese_search_urls", [False, True])
@pytest.mark.parametrize("bilingual", [False, True])
@pytest.mark.parametrize("condition_count", [1, 3])
def test_browser_confirmations_to_sqlite_history(
    tmp_path, monkeypatch, japanese_search_urls, bilingual, condition_count
):
    from src.search_v2.condition_terms import LocalConditionExpander

    flow, images, _, history, clock = connected.start(
        tmp_path,
        plan_lifetime=None,
        japanese_search_urls=japanese_search_urls,
        condition_expander=LocalConditionExpander() if bilingual else None,
        condition_count=condition_count,
    )
    ranking, calls = connected.clip(monkeypatch, tmp_path)
    products = candidate.scanner_products()
    for index, product in enumerate(products, 1):
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
            assets=ranking["asset_root"],
            encoder=ranking["encoder"],
        )
    )
    first = run.execute("start", {})
    assert first["stage"] == "query"
    assert "expiresAt" not in first
    assert flow.plan.expires_at is None
    clock[0] += timedelta(hours=1)
    assert not images.calls and not transport.calls
    assert run.execute("reference", {"index": 0})["stage"] == "reference"
    assert len(images.calls) == 1 and not transport.calls
    clock[0] += timedelta(hours=1)
    assert run.execute("comparison", {})["stage"] == "comparison"
    assert len(images.calls) == condition_count + 1 and not transport.calls
    assert run.execute("final", {})["stage"] == "final"
    assert not transport.calls
    fetch = transport.fetch

    def slow_fetch(request):
        clock[0] += timedelta(hours=1)
        return fetch(request)

    monkeypatch.setattr(transport, "fetch", slow_fetch)
    result = run.execute("search", {})
    assert result["stage"] == "complete" and result["saved"]
    assert len(transport.calls) == 1 and calls
    request = transport.calls[0]
    assert request.schema_version == ("2.1" if japanese_search_urls else "1.0")
    assert request.provider == ("outscraper" if japanese_search_urls else "playwright")
    assert all("language=ja_JP" in value for value in request.provider_queries()) == (
        japanese_search_urls
    )
    assert len(history.list(owner_id=connected.OWNER, now=clock[0])) == 1
    assert all(
        set(item)
        == {"title", "price", "url", "required", "appearance", "thumbnail", "reviewRating"}
        | ({"scores"} if bilingual else set())
        for item in result["products"]
    )
    if bilingual:
        for item in result["products"]:
            title = item["scores"]["title"]
            assert title["score"] == max(title["score_ja"], title["score_en"] or 0)
            for condition in item["scores"]["conditions"]:
                assert condition["score"] == max(condition["score_ja"], condition["score_en"] or 0)
            assert "image" in item["scores"] and "total" in item["scores"]
    assert all(
        item["thumbnail"].startswith("data:image/png;base64,") for item in result["products"]
    )
    assert ranking["proxy_service"].calls == len(products)
    assert "token" not in str(result) and "sha256" not in str(result)
    run.close()


def test_expired_reference_stops_before_second_image(tmp_path):
    flow, images, _, _, clock = connected.start(tmp_path)
    reference = connected.reference(flow)
    assert len(images.calls) == 1
    clock[0] = flow.plan.expires_at + timedelta(seconds=1)
    with pytest.raises(ValueError):
        flow.approve_reference(
            owner_id=connected.OWNER, reference_sha256=reference.sha256, human_confirmed=True
        )
    assert len(images.calls) == 1


@pytest.mark.parametrize("condition_count", [1, 3])
def test_browser_prompt_edits_reuse_reference_and_share_regeneration_budget(
    tmp_path, condition_count
):
    from src.search_v2.browser_candidate import BrowserImages

    flow, transport, _, history, clock = connected.start(
        tmp_path, plan_lifetime=None, condition_count=condition_count
    )
    images = BrowserImages(transport)
    flow._transport = images
    run = BrowserCandidateRun(
        candidate_browser_steps(
            flow,
            owner=connected.OWNER,
            images=images,
            products=None,
            history=history,
            now=lambda: clock[0],
            proxy=None,
            assets=None,
            encoder=None,
        )
    )
    initial = run.execute("start", {})
    plan = flow.plan_sha256
    prompts = {
        key: f"First edit {index}."
        for index, key in enumerate(initial["imagePrompts"]["comparison"])
    }
    reference = run.execute("reference", {"index": 0, "prompt": "A custom studio reference."})
    assert transport.calls[0]["request"].prompt == "A custom studio reference."
    first = run.execute("comparison", {"prompts": prompts})
    assert first["canRegenerateComparisons"]
    first_seeds = [call["request"].seed for call in transport.calls[1:]]
    second_prompts = {key: f"Second edit {index}." for index, key in enumerate(prompts)}
    second = run.execute("regenerate_comparisons", {"prompts": second_prompts})
    assert len(transport.calls) == 1 + condition_count * 2
    assert second["images"][0] == reference["images"][0]
    assert second["imagePrompts"]["comparison"] == second_prompts
    assert not second["canRegenerate"] and not second["canRegenerateComparisons"]
    assert second["referenceRemaining"] == 0 and flow.plan_sha256 == plan
    for index, call in enumerate(transport.calls[-condition_count:]):
        request = call["request"]
        assert request.model_id.endswith("klein-9b")
        assert request.prompt == second_prompts[request.condition_id]
        assert request.seed != first_seeds[index]
    assert run.execute("final", {})["stage"] == "final"
    with pytest.raises(ValueError, match="image set limit"):
        run.execute("regenerate_comparisons", {"prompts": second_prompts})
    assert len(transport.calls) == 1 + condition_count * 2
    run.close()
