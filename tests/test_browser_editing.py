"""Editable input remains bound to a single, explicitly advanced browser run."""

from io import BytesIO
from types import SimpleNamespace
import base64

from PIL import Image
import pytest

from src.search_v2.browser_candidate import BrowserCandidateRun
from src.search_v2.browser_search import BrowserSearch, BrowserCommandError


class InlineWorker:
    def submit(self, fn, *args):
        fn(*args)


def command(action, revision, **values):
    return dict(action=action, revision=revision, operation=f"operation-{revision:04d}", **values)


def test_input_revision_rebuild_invalidates_previous_images():
    opened, closed = [], []

    def factory(source, attempt):
        opened.append((source, attempt))
        try:
            selection = yield {"stage": "query", "queries": [source], "conditions": []}
            assert selection == {"index": 0}
            yield {"stage": "reference", "images": ["fixture"]}
        finally:
            closed.append(attempt)

    run = BrowserCandidateRun(factory=factory)
    controller = BrowserSearch(run.execute, InlineWorker(), initial={"editable": True})
    first = command("start", 0, source="合成の丸いケース。")
    assert controller.submit(first)["input"] == "合成の丸いケース。"
    assert controller.submit(first)["stage"] == "query"
    revised = command("revise", 1, source="合成の青いケース。")
    state = controller.submit(revised)
    assert state["queries"] == ["合成の青いケース。"]
    assert state["input"] == "合成の青いケース。"
    assert closed == [0]
    assert opened == [("合成の丸いケース。", 0), ("合成の青いケース。", 1)]
    with pytest.raises(BrowserCommandError):
        controller.submit(command("reference", 1, index=0))
    controller.submit(command("reference", 2, index=0))
    state = controller.submit(command("revise", 3, source="合成の白いケース。"))
    assert state["stage"] == "query" and "images" not in state
    assert state["canRevise"] is False
    with pytest.raises(BrowserCommandError):
        controller.submit(command("comparison", 3))
    run.close()
    assert closed == [0, 1, 2]


def test_repreparation_is_bounded_without_resetting_duplicate_protection():
    calls = []
    controller = BrowserSearch(
        lambda action, values: calls.append(action) or {"stage": "query"},
        InlineWorker(),
        initial={"editable": True},
    )
    for revision in range(3):
        controller.submit(command("start" if revision == 0 else "revise", revision, source="合成"))
    assert controller.snapshot()["canRevise"] is False
    with pytest.raises(BrowserCommandError):
        controller.submit(command("revise", 3, source="合成"))
    assert calls == ["start", "revise", "revise"]


@pytest.mark.parametrize("source", ["", " ", "あ" * 2001, None, 3, "合成\x00入力", "\ud800"])
def test_invalid_input_never_enters_worker(source):
    controller = BrowserSearch(
        lambda *_: pytest.fail("provider called"), InlineWorker(), initial={"editable": True}
    )
    with pytest.raises(BrowserCommandError):
        controller.submit(command("start", 0, source=source))


def test_thumbnails_reuse_only_validated_pixels_without_second_fetch():
    from src.search_v2.browser_candidate import BrowserProductImages

    calls = []
    raw = SimpleNamespace(width=400, height=200, rgb_bytes=b"\xff\x00\x00" * 80000)
    proxy = BrowserProductImages(SimpleNamespace(fetch_image=lambda url: calls.append(url) or raw))
    assert proxy.fetch_image("https://m.media-amazon.com/image.png") is raw
    preview = proxy.preview(("https://m.media-amazon.com/image.png",))
    assert calls == ["https://m.media-amazon.com/image.png"]
    with Image.open(BytesIO(base64.b64decode(preview.split(",", 1)[1]))) as image:
        assert image.size == (192, 96)
    assert proxy.preview(("https://example.com/missing",)) is None
    assert proxy.preview(()) is None


def test_ambiguous_condition_can_be_corrected_before_any_preparation():
    calls = []

    def factory(source, attempt):
        calls.append(attempt)
        yield {"stage": "query", "queries": ["ケース"], "conditions": ["できれば赤"]}

    run = BrowserCandidateRun(factory=factory)
    controller = BrowserSearch(run.execute, InlineWorker(), initial={"editable": True})
    state = controller.submit(command("start", 0, source="ケース。赤が不要ではない。"))
    assert state["stage"] == "clarification" and state["canRevise"]
    assert state["conditionIssues"][0]["quote"] == "赤が不要ではない"
    assert calls == []
    state = controller.submit(
        command("revise", 1, source="ケース。できれば赤。取っ手がなくてもよい。")
    )
    assert state["stage"] == "query" and calls == [1]
    assert [r["strength"] for r in state["conditionReview"]] == ["preferred", "neutral"]
    assert "conditionIssues" not in state
    run.close()


def test_neutral_only_visual_stops_with_reason_without_model_call(tmp_path):
    import test_candidate_visual_conditions as visual

    model = visual.VisualBonsai(tmp_path, [])
    import test_candidate_search as candidate
    from src.search_v2.candidate_search import CandidateSearch

    def factory(source, attempt):
        CandidateSearch(
            source,
            owner_id="owner-1",
            session_id="neutral",
            postal_code="100-0001",
            normalization_profile=candidate.flow.backend_policy().normalization_profile,
            now=candidate.flow.NOW,
            visual_extractor=model,
        )
        pytest.fail("neutral input reached image path")
        yield

    run = BrowserCandidateRun(factory=factory)
    result = run.execute("start", {"source": "マグカップ。色にはこだわらない。"})
    assert result["stage"] == "clarification"
    assert "画像なし" in result["message"]
    assert result["conditionReview"][0]["strength"] == "neutral"
    assert model.calls == []
    run.close()


def test_natural_conditions_revision_to_fixture_ranking_and_history(tmp_path, monkeypatch):
    import test_candidate_connected_flow as connected
    import test_candidate_search as candidate
    import test_candidate_visual_conditions as visual
    from src.search_v2.browser_candidate import candidate_browser_steps
    from src.search_v2.candidate_flow import CandidateSearchFlow
    from src.search_v2.condition_terms import LocalConditionExpander
    from src.search_v2.provisional_approval_repository import SqliteCounterfactualApprovalRepository
    from src.search_v2.provisional_history_repository import SqliteProvisionalHistoryRepository
    from datetime import datetime

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return candidate.flow.NOW

    monkeypatch.setattr("src.search_v2.browser_search.datetime", Clock)
    history = SqliteProvisionalHistoryRepository(tmp_path / "history.sqlite3")
    images = candidate.flow.CloudflareTransport(candidate.flow.cloudflare_responses() * 4)
    ranking, _ = connected.clip(monkeypatch, tmp_path)
    products = candidate.ProductTransport(
        [
            {
                "name": "マグカップ",
                "price": 4000,
                "currency": "JPY",
                "name_en": "Mug",
                "title_en_status": "available",
                "description_en": "microwave safe",
                "details_en_status": "available",
                "image_1": "https://m.media-amazon.com/images/1.png",
            }
        ],
        tmp_path,
    )
    translator = SimpleNamespace(
        translate=lambda phrases: tuple("microwave" if p == "電子レンジ" else None for p in phrases)
    )

    def factory(source, attempt):
        flow = CandidateSearchFlow(
            source,
            owner_id="owner-1",
            session_id="natural-fixture",
            postal_code="100-0001",
            policy=candidate.flow.backend_policy(),
            usage_ledger=candidate.flow.usage_ledger(),
            approval_repository=SqliteCounterfactualApprovalRepository(
                tmp_path / "approval.sqlite3"
            ),
            history_repository=history,
            image_transport=images,
            account_id=candidate.flow.ACCOUNT_ID,
            api_token=candidate.flow.CLOUDFLARE_TOKEN,
            now=lambda: candidate.flow.NOW,
            image_score_mode="appearance",
            plan_lifetime=None,
            visual_extractor=visual.VisualBonsai(
                tmp_path, [visual.draft("丸い形だとうれしい", "preferred")]
            ),
            condition_expander=LocalConditionExpander(translator=translator),
        )
        yield from candidate_browser_steps(
            flow,
            owner="owner-1",
            images=SimpleNamespace(previews=lambda: ["fixture"] * len(images.calls)),
            products=lambda _: products,
            history=history,
            now=lambda: candidate.flow.NOW,
            proxy=ranking["proxy_service"],
            assets=ranking["asset_root"],
            encoder=ranking["encoder"],
        )

    run = BrowserCandidateRun(factory=factory)
    controller = BrowserSearch(run.execute, InlineWorker(), initial={"editable": True})
    state = controller.submit(command("start", 0, source="マグカップ。赤が不要ではない。"))
    assert state["stage"] == "clarification" and not images.calls and not products.calls
    source = "マグカップ。丸い形だとうれしい。電子レンジ対応は不要。色にはこだわらない。できれば3000円以下。"
    state = controller.submit(command("revise", 1, source=source))
    assert state["stage"] == "query"
    assert [r["strength"] for r in state["conditionReview"]] == [
        "preferred",
        "excluded",
        "neutral",
        "preferred",
    ]
    assert not any("こだわらない" in q for q in state["queries"])
    for action, args in [
        ("reference", {"index": 0}),
        ("comparison", {}),
        ("final", {}),
        ("search", {}),
    ]:
        state = controller.submit(command(action, state["revision"], **args))
    assert state["stage"] == "complete" and state["saved"]
    rows = state["products"][0]["scores"]["conditions"]
    excluded = [r for r in rows if r["strength"] == "excluded"]
    assert len(excluded) == 1 and excluded[0]["score_en"] == excluded[0]["score"] == 1.0
    assert not any(r["strength"] == "required" for r in rows)
    assert len(history.list(owner_id="owner-1", now=candidate.flow.NOW)) == 1
    assert len(products.calls) == 1 and len(images.calls) == 2
    run.close()


def test_preparation_image_mode_reaches_factory_on_start_and_revision():
    modes = []

    def factory(source, attempt, *, image_mode="on"):
        modes.append(image_mode)
        yield {"stage": "query", "canSkipImages": True}

    run = BrowserCandidateRun(factory=factory)
    controller = BrowserSearch(run.execute, InlineWorker(), initial={"editable": True})
    first = command("start", 0, source="ケース。羽根付き。", imageMode="off")
    assert controller.submit(first)["stage"] == "query"
    assert controller.submit(first)["stage"] == "query"
    revision = controller.snapshot()["revision"]
    assert (
        controller.submit(command("revise", revision, source="ケース。羽根付き。", imageMode="on"))[
            "stage"
        ]
        == "query"
    )
    assert modes == ["off", "on"]


@pytest.mark.parametrize("mode", [None, True, False, 0, "", "auto", [], {}])
def test_invalid_preparation_image_mode_is_rejected(mode):
    controller = BrowserSearch(
        lambda *_: pytest.fail("Invalid mode reached worker"),
        InlineWorker(),
        initial={"editable": True},
    )
    with pytest.raises(BrowserCommandError):
        controller.submit(command("start", 0, source="ケース。", imageMode=mode))
