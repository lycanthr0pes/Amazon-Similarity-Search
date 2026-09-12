"""Image-free commands retain scoring/history without touching image services."""

from types import SimpleNamespace
import pytest
import test_candidate_connected_flow as connected
import test_candidate_search as candidate
from src.search_v2.browser_candidate import BrowserCandidateRun, candidate_browser_steps
from src.search_v2.condition_terms import LocalConditionExpander


@pytest.mark.parametrize("skip_stage", ["query", "reference", "comparison", "final"])
def test_image_free_browser_to_history(tmp_path, skip_stage):
    flow, images, _, history, clock = connected.start(
        tmp_path, plan_lifetime=None, condition_expander=LocalConditionExpander()
    )
    transport = candidate.ProductTransport(candidate.scanner_products(), tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("Image evaluation must not run")

    run = BrowserCandidateRun(
        candidate_browser_steps(
            flow,
            owner=connected.OWNER,
            images=SimpleNamespace(previews=lambda: ["fixture"] * len(images.calls)),
            products=lambda _: transport,
            history=history,
            now=lambda: clock[0],
            proxy=SimpleNamespace(fetch_image=forbidden),
            assets=None,
            encoder=SimpleNamespace(encode_images=forbidden),
        )
    )
    view = run.execute("start", {})
    for stage, action, values in [
        ("query", "reference", {"index": 0}),
        ("reference", "comparison", {}),
        ("comparison", "final", {}),
    ]:
        if skip_stage == stage:
            break
        view = run.execute(action, values)
    calls = len(images.calls)
    view = run.execute("without_images", {"index": 0})
    assert view["stage"] == "final" and view["imageMode"] == "off"
    assert view["images"] == [] and not transport.calls
    result = run.execute("search", {})
    assert result["stage"] == "complete" and result["saved"]
    assert result["imageMode"] == "off"
    assert len(images.calls) == calls and len(transport.calls) == 1
    if skip_stage == "query":
        assert calls == 0
    saved = history.list(owner_id=connected.OWNER, now=clock[0])
    assert len(saved) == 1
    detail = history.get(owner_id=connected.OWNER, locator=saved[0].locator, now=clock[0])
    assert detail.image_mode == "off" and detail.reference_images == ()
    assert detail.runtime_sha256 is None and detail.reference_set_sha256 is None
    for product in detail.products:
        assert product.image_component_status == "not_used" and product.image_score is None
        assert product.title_scores.score == max(
            product.title_scores.score_ja, product.title_scores.score_en or 0
        )
        for condition in product.condition_scores:
            assert condition.score == max(condition.score_ja, condition.score_en or 0)
    with pytest.raises((ValueError, StopIteration)):
        run.execute("search", {})
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    "source", ["マグカップ。3000円以下。", "マグカップ。取っ手がなくてもよい。", "マグカップ"]
)
def test_no_visual_conditions_need_no_visual_model(tmp_path, source):
    from src.search_v2.candidate_flow import CandidateSearchFlow
    from src.search_v2.provisional_history_repository import SqliteProvisionalHistoryRepository

    def forbidden(*args, **kwargs):
        pytest.fail("Image boundary was invoked")

    history = SqliteProvisionalHistoryRepository(tmp_path / "history.sqlite3")
    flow = CandidateSearchFlow(
        source,
        owner_id="local-user",
        session_id="fixture",
        postal_code="100-0001",
        policy=candidate.flow.backend_policy(),
        usage_ledger=candidate.flow.usage_ledger(),
        approval_repository=None,
        history_repository=history,
        image_transport=None,
        account_id=None,
        api_token=None,
        image_settings=forbidden,
        now=lambda: candidate.flow.NOW,
        visual_extractor=SimpleNamespace(evaluate=forbidden),
        allow_image_free=True,
        condition_expander=LocalConditionExpander(),
        plan_lifetime=None,
    )
    assert flow.plan.visual_conditions is None
    products = candidate.ProductTransport([{"name": "マグカップ", "price": 2000}], tmp_path)
    run = BrowserCandidateRun(
        candidate_browser_steps(
            flow,
            owner="local-user",
            images=None,
            products=lambda _: products,
            history=history,
            now=lambda: candidate.flow.NOW,
            proxy=None,
            assets=None,
            encoder=None,
            image_evaluator=forbidden,
        )
    )
    first = run.execute("start", {})
    assert first["canGenerateImages"] is False
    assert all("なくても" not in q for q in first["queries"])
    with pytest.raises(ValueError):
        flow.skip_images(owner_id="other", plan_sha256=flow.plan_sha256, human_confirmed=True)
    final = run.execute("without_images", {"index": 0})
    assert final["imageMode"] == "off"
    assert run.execute("search", {})["saved"]
    from src.search_v2.browser_history import BrowserHistory

    browser_history = BrowserHistory([tmp_path / "history.sqlite3"], now=lambda: candidate.flow.NOW)
    assert browser_history.list()["items"][0]["productName"] == "マグカップ"
    saved = browser_history.get(browser_history.list()["items"][0]["id"])["view"]
    assert saved["imageMode"] == "off" and saved["images"] == []
    assert len(products.calls) == 1


def test_history_rejects_mixing_image_modes_and_changed_ranking(tmp_path):
    from pydantic import ValidationError
    from test_candidate_text_scoring import search, rank
    from src.search_v2.candidate_image_free import (
        complete_image_free,
        image_free_history,
        ImageFreeRanking,
    )
    from src.search_v2.provisional_history_repository import ProvisionalHistoryWrite

    source = "マグカップ。電子レンジ対応。"
    ranking = complete_image_free(
        rank(search(source), tmp_path, [{"name": "マグカップ"}, {"name": "収納箱"}])
    )
    pending = image_free_history(ranking, source_text=source, completed_at=candidate.flow.NOW)
    for updates in [
        {"image_mode": None},
        {"runtime_sha256": "a" * 64},
        {"image_weight": 0.5},
        {"ranking_profile_id": "candidate-siglip2-appearance-v1"},
    ]:
        with pytest.raises(ValidationError):
            ProvisionalHistoryWrite.model_validate(pending.model_copy(update=updates))
    with pytest.raises(ValidationError):
        ImageFreeRanking.model_validate(
            ranking.model_copy(update={"products": ranking.products[::-1]})
        )


def test_browser_image_free_duplicate_and_revision_guards(tmp_path):
    from src.search_v2.browser_search import BrowserSearch, BrowserCommandError
    from tools.browser_search_runtime import fixture_steps

    run = BrowserCandidateRun(fixture_steps())
    worker = SimpleNamespace(submit=lambda fn, *args: fn(*args))
    controller = BrowserSearch(run.execute, worker)

    def command(action, **kwargs):
        return {
            "action": action,
            "revision": controller.snapshot()["revision"],
            "operation": f"operation-{action}",
            **kwargs,
        }

    controller.submit(command("start"))
    skip = command("without_images", index=0)
    state = controller.submit(skip)
    assert state["stage"] == "final" and state["imageMode"] == "off"
    assert controller.submit(skip) == state
    with pytest.raises(BrowserCommandError):
        controller.submit({**skip, "operation": "another-operation"})
    result = controller.submit(command("search"))
    assert result["stage"] == "complete"
    with pytest.raises(BrowserCommandError):
        controller.submit(command("without_images", index=0))


@pytest.mark.parametrize("image_mode", [None, "off"])
def test_live_composition_image_free_never_loads_image_settings(tmp_path, monkeypatch, image_mode):
    from contextlib import contextmanager, nullcontext
    from io import BytesIO
    import tools.browser_search_runtime as runtime
    import src.search_v2.candidate_flow as flow_module
    from src.search_v2.browser_history import BrowserHistory

    root = tmp_path / "private-run"
    original_flow = flow_module.CandidateSearchFlow

    def forbidden(*args, **kwargs):
        pytest.fail("Image dependency loaded during image-free execution")

    class Expander:
        def visual_contrasts(self, dictionary=None):
            from src.search_v2.visual_contrast import ContrastResolver

            return ContrastResolver(dictionary)

        def with_translator(self, _):
            return self

        def with_resolver(self, _):
            return self

    @contextmanager
    def lexical(_):
        yield Expander(), None

    @contextmanager
    def model(_):
        yield SimpleNamespace(evaluate=forbidden)

    def fixture_flow(*args, **kwargs):
        kwargs["lexical_expander"] = None  # Dictionary is independently fixture-tested.
        kwargs["condition_expander"] = LocalConditionExpander()
        flow = original_flow(*args, **kwargs)
        if image_mode:
            assert flow.plan.visual_request_sha256 is None
            assert flow.plan.visual_response_sha256 is None
            assert all(
                c.contrast is None and c.focus is None
                for c in flow.plan.visual_conditions.conditions
            )
            with pytest.raises(ValueError):
                flow.generate_reference(
                    owner_id=runtime.OWNER, plan_sha256=flow.plan_sha256, human_confirmed=True
                )
        return flow

    monkeypatch.setattr(
        runtime, "MODEL", SimpleNamespace(open=lambda *_: BytesIO(b"synthetic model"))
    )
    monkeypatch.setattr(runtime, "browser_bonsai", model)
    monkeypatch.setattr("tools.bonsai_live_e2e.BonsaiLiveE2EConfig", lambda *_: None)
    monkeypatch.setattr("src.search_v2.lexical_assets.load_lexical_services", lexical)
    monkeypatch.setattr(
        "src.search_v2.wordnet_contrast.WordNetContrastDictionary",
        lambda *_, **__: nullcontext(None),
    )
    monkeypatch.setattr("src.search_v2.lexical_expansion.ContextualQueryExpander", Expander)
    monkeypatch.setattr("src.search_v2.opus_mt.OpusMtTranslator", lambda *_: None)
    monkeypatch.setattr("src.search_v2.lexical_context.BonsaiProductSelector", lambda *_: None)
    monkeypatch.setattr(flow_module, "CandidateSearchFlow", fixture_flow)
    for target in (
        "src.config.CloudflareLiveSettings",
        "src.search_v2.siglip2.verify_assets",
        "src.search_v2.siglip2.LocalSiglip2ImageEncoder",
    ):
        monkeypatch.setattr(target, forbidden)
    preview_calls = []

    def display_image(url):
        preview_calls.append(url)
        return SimpleNamespace(width=1, height=1, rgb_bytes=b"\xff\xff\xff")

    monkeypatch.setattr(
        "src.search_v2.image_proxy_service.ImageProxyService",
        lambda **_: SimpleNamespace(fetch_image=display_image),
    )
    transport = candidate.ProductTransport(
        [
            {
                "name": "マグカップ",
                "price": 2000,
                "image_1": "https://m.media-amazon.com/images/fixture.png",
            }
        ],
        tmp_path,
    )
    monkeypatch.setattr(
        "src.search_v2.playwright_products.PlaywrightProducts", lambda _, **kwargs: transport
    )
    source = "ケース。羽根付き。できれば2000円以下。" if image_mode else "マグカップ。3000円以下。"
    if image_mode:
        monkeypatch.setattr("src.search_v2.wordnet_contrast.WordNetContrastDictionary", forbidden)
        monkeypatch.setattr(Expander, "visual_contrasts", forbidden)
    run = BrowserCandidateRun(
        runtime.live_steps(
            root, source=source, **({"image_mode": image_mode} if image_mode else {})
        )
    )
    assert run.execute("start", {})["canGenerateImages"] is False
    assert run.execute("without_images", {"index": 0})["stage"] == "final"
    assert run.execute("search", {})["saved"]
    history = BrowserHistory([root / "history.sqlite3"])
    saved = history.list()
    assert len(saved["items"]) == 1 and len(transport.calls) == 1
    assert len(preview_calls) == 1
    assert history.get(saved["items"][0]["id"])["view"]["products"][0]["thumbnail"]
    if image_mode:
        detail = history.get(saved["items"][0]["id"])["view"]
        assert "羽根付き" in detail["conditionLabels"].values()
        assert {c["strength"] for c in detail["products"][0]["scores"]["conditions"]} == {
            "required",
            "preferred",
        }


def test_image_free_review_breaks_text_ties_without_overriding_title(tmp_path):
    from test_candidate_text_scoring import search, rank
    from src.search_v2.candidate_image_free import complete_image_free

    result = complete_image_free(
        rank(
            search("マグカップ"),
            tmp_path,
            [
                {"name": "マグカップ", "rating": 2.0},
                {"name": "収納箱", "rating": 5.0},
                {"name": "マグカップ", "rating": 4.0},
                {"name": "マグカップ"},
            ],
        )
    )
    assert [row.product.provenance.response_index for row in result.products] == [2, 0, 3, 1]


@pytest.mark.parametrize("failure", ["reference", "comparison"])
def test_image_failure_can_continue_without_images(tmp_path, failure):
    flow, images, ledger, history, clock = connected.start(tmp_path, plan_lifetime=None)
    products = candidate.ProductTransport(candidate.scanner_products(), tmp_path)
    run = BrowserCandidateRun(
        candidate_browser_steps(
            flow,
            owner=connected.OWNER,
            images=SimpleNamespace(previews=lambda: ["fixture"] * len(images.calls)),
            products=lambda _: products,
            history=history,
            now=lambda: clock[0],
            proxy=None,
            assets=None,
            encoder=None,
        )
    )
    run.execute("start", {})
    if failure == "comparison":
        run.execute("reference", {"index": 0})

    def unavailable(**_):
        raise ValueError("Synthetic image service failure")

    images.post_multipart = unavailable
    result = run.execute(
        "reference" if failure == "reference" else "comparison",
        {"index": 0} if failure == "reference" else {},
    )
    assert result["stage"] == "failed" and result["canSkipImages"]
    usage = ledger.snapshot()
    assert run.execute("without_images", {"index": 0})["stage"] == "final"
    assert run.execute("search", {})["saved"]
    assert ledger.snapshot() == usage and len(products.calls) == 1


def test_empty_image_free_result_is_saved_without_fabricated_products(tmp_path):
    from test_candidate_text_scoring import search, rank
    from src.search_v2.candidate_image_free import complete_image_free, image_free_history
    from src.search_v2.provisional_history_repository import SqliteProvisionalHistoryRepository

    source = "マグカップ"
    ranking = complete_image_free(rank(search(source), tmp_path, []))
    pending = image_free_history(ranking, source_text=source, completed_at=candidate.flow.NOW)
    history = SqliteProvisionalHistoryRepository(tmp_path / "empty-history.sqlite3")
    detail = history.save(pending, now=candidate.flow.NOW)
    assert detail.products == () and detail.reference_images == ()
    assert history.list(owner_id="owner-1", now=candidate.flow.NOW)[0].compared_count == 0


@pytest.mark.parametrize(
    "strength,phrase",
    [
        ("required", "羽根付き"),
        ("preferred", "できれば羽根付き"),
        ("excluded", "羽根付きは避けたい"),
    ],
)
def test_text_only_preparation_keeps_bilingual_appearance_scores(tmp_path, strength, phrase):
    from src.search_v2.candidate_search import CandidateSearch, CandidatePlan
    from test_candidate_text_scoring import rank

    class Translator:
        sha256 = "f" * 64

        def translate(self, phrases):
            assert all("こだわらない" not in text for text in phrases)
            return tuple("with feathers" if text == "羽根付き" else None for text in phrases)

    def forbidden(*args, **kwargs):
        pytest.fail("Contrast inference must not run")

    service = CandidateSearch(
        f"ケース。{phrase}。色にはこだわらない。",
        owner_id="owner-1",
        session_id="image-free-text",
        postal_code="100-0001",
        normalization_profile=candidate.flow.backend_policy().normalization_profile,
        now=candidate.flow.NOW,
        image_mode="off",
        allow_empty_visual=True,
        visual_extractor=SimpleNamespace(evaluate=forbidden),
        condition_expander=LocalConditionExpander(translator=Translator()),
        contrast_resolver=SimpleNamespace(resolve=forbidden),
    )
    assert service.plan.image_preparation == "text-only-v1"
    assert service.plan.visual_request_sha256 is None
    assert service.plan.visual_response_sha256 is None
    assert CandidatePlan.model_validate_json(service.plan.model_dump_json()) == service.plan
    for field in ("visual_request_sha256", "visual_response_sha256"):
        with pytest.raises(ValueError):
            CandidatePlan.model_validate(service.plan.model_copy(update={field: "a" * 64}))
    legacy = service.plan.model_copy(update={"image_preparation": None})
    assert "image_preparation" not in legacy.model_dump(mode="json")
    assert legacy.model_dump_json() != service.plan.model_dump_json()
    result = rank(
        service,
        tmp_path,
        [{"name": "ケース", "name_en": "Case with feathers", "title_en_status": "available"}],
    )
    score = result.products[0].text_score
    assert len(score.conditions) == 1
    row = score.conditions[0]
    assert row.strength == strength
    assert (row.score_ja, row.score_en, row.score) == (0.0, 1.0, 1.0)
    assert score.excluded_ratio == (1.0 if strength == "excluded" else 0.0)
