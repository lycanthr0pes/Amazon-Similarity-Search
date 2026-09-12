"""Canary limits are enforced before contacting the injected provider."""

from types import SimpleNamespace

import pytest

from tools.browser_search_runtime import BrowserBonsai, fixture_steps


@pytest.mark.parametrize("failure", [False, True])
def test_browser_images_allow_two_full_sets_and_count_failed_calls(monkeypatch, failure):
    from src.search_v2.browser_candidate import BrowserImages

    calls = []

    def post(**kwargs):
        calls.append(kwargs)
        if failure:
            raise OSError("fixture")
        from src.search_v2.cloudflare_http import CloudflareHttpResponse

        return CloudflareHttpResponse(200, "image/png", None, None, ())

    monkeypatch.setattr(
        "src.search_v2.browser_candidate._artifact", lambda *_: SimpleNamespace(body=b"fixture")
    )
    images = BrowserImages(SimpleNamespace(post_multipart=post))
    for _ in range(8):
        if failure:
            with pytest.raises(OSError):
                images.post_multipart(request=None)
        else:
            images.post_multipart(request=None)
    with pytest.raises(ValueError, match="image execution limit"):
        images.post_multipart(request=None)
    assert len(calls) == 8


@pytest.mark.parametrize("condition_count", [1, 3])
def test_live_composition_does_not_reuse_the_two_image_canary_limit(
    tmp_path, monkeypatch, condition_count
):
    from contextlib import nullcontext
    from io import BytesIO
    import test_candidate_connected_flow as connected
    from tools import browser_search_runtime as runtime

    flow, transport, _, _, _ = connected.start(
        tmp_path, plan_lifetime=None, condition_count=condition_count
    )

    class Expander:
        def with_translator(self, *_):
            return self

        def with_resolver(self, *_):
            return self

        def visual_contrasts(self, *_):
            return None

    def prepared_flow(*_, **kwargs):
        flow._transport = kwargs["image_transport"]
        return flow

    monkeypatch.setattr(runtime, "MODEL", SimpleNamespace(open=lambda *_: BytesIO(b"fixture")))
    monkeypatch.setattr(runtime, "browser_bonsai", lambda *_: nullcontext(None))
    monkeypatch.setattr("tools.bonsai_live_e2e.BonsaiLiveE2EConfig", lambda *_: None)
    monkeypatch.setattr(runtime, "OWNER", connected.OWNER)
    monkeypatch.setattr("src.search_v2.lexical_expansion.ContextualQueryExpander", Expander)
    monkeypatch.setattr(
        "src.search_v2.lexical_assets.load_lexical_services",
        lambda *_: nullcontext((Expander(), None)),
    )
    monkeypatch.setattr("src.search_v2.lexical_context.BonsaiProductSelector", lambda *_: None)
    monkeypatch.setattr("src.search_v2.opus_mt.OpusMtTranslator", lambda *_: None)
    monkeypatch.setattr(
        "src.search_v2.wordnet_contrast.WordNetContrastDictionary",
        lambda *_, **__: nullcontext(None),
    )
    monkeypatch.setattr("src.search_v2.candidate_flow.CandidateSearchFlow", prepared_flow)
    monkeypatch.setattr(
        "tools.backend_search_live_e2e.RequestsBackendImageTransport", lambda: transport
    )
    monkeypatch.setattr(
        "src.config.CloudflareLiveSettings", lambda: pytest.fail("credentials loaded")
    )
    steps = runtime.live_steps(tmp_path / "run", source="マグカップ。丸みのある形。")
    assert next(steps)["stage"] == "query"
    assert steps.send({"index": 0})["stage"] == "reference"
    assert steps.send({})["stage"] == "comparison"
    assert steps.send({"regenerate": True})["stage"] == "reference"
    assert steps.send({})["stage"] == "comparison"
    assert len(transport.calls) == 2 * (1 + condition_count)
    steps.close()


def test_bonsai_rejects_third_request(monkeypatch):
    calls = []
    monkeypatch.setattr("src.search_v2.bonsai_request._response_body", lambda _: b"{}")
    transport = SimpleNamespace(post_json=lambda **kwargs: calls.append(kwargs))
    bonsai = BrowserBonsai(transport, stop=lambda: pytest.fail("unexpected timeout"))
    assert bonsai.evaluate(b"{}") == b"{}"
    assert bonsai.evaluate(b"{}") == b"{}"
    with pytest.raises(ValueError):
        bonsai.evaluate(b"{}")
    assert len(calls) == 2
    assert all(call["url"] == "http://127.0.0.1:18080/v1/chat/completions" for call in calls)


def test_each_bonsai_request_has_its_own_timeout(monkeypatch):
    timers, stops = [], []

    class Timer:
        def __init__(self, seconds, callback):
            self.seconds, self.callback = seconds, callback
            self.cancelled = self.joined = False
            timers.append(self)

        def start(self):
            pass

        def cancel(self):
            self.cancelled = True

        def join(self):
            self.joined = True

    monkeypatch.setattr("tools.browser_search_runtime.threading.Timer", Timer)
    monkeypatch.setattr("src.search_v2.bonsai_request._response_body", lambda _: b"{}")
    bonsai = BrowserBonsai(
        SimpleNamespace(post_json=lambda **_: None), stop=lambda: stops.append(True)
    )
    assert bonsai.evaluate(b"{}") == b"{}"
    assert bonsai.evaluate(b"{}") == b"{}"
    assert len(timers) == 2
    assert all(timer.seconds == 900 and timer.cancelled and timer.joined for timer in timers)
    assert not stops

    def timeout(**_):
        timers[-1].callback()
        return None

    expired = BrowserBonsai(SimpleNamespace(post_json=timeout), stop=lambda: stops.append(True))
    with pytest.raises(ValueError, match="Bonsai request timed out"):
        expired.evaluate(b"{}")
    assert stops == [True]
    assert timers[-1].cancelled and timers[-1].joined


def test_fixture_does_not_load_credentials(monkeypatch):
    def forbidden(*_, **__):
        pytest.fail("Fixture loaded live credentials")

    monkeypatch.setattr("src.config.CloudflareLiveSettings", forbidden)
    monkeypatch.setattr("src.config.OutscraperLiveSettings", forbidden)
    steps = fixture_steps()
    assert next(steps)["stage"] == "query"
    assert steps.send({"index": 0})["stage"] == "reference"
    assert next(steps)["stage"] == "comparison"
    assert next(steps)["stage"] == "final"
    assert next(steps)["stage"] == "complete"
    steps.close()


@pytest.mark.parametrize("fail", [False, True])
def test_model_is_cleaned_up_after_preparation(monkeypatch, fail):
    from tools.browser_search_runtime import browser_bonsai
    from tools import bonsai_live_e2e as runtime

    events = []
    process = SimpleNamespace(kill=lambda: events.append("kill"))
    monkeypatch.setattr(runtime, "_launch_server", lambda _: process)
    monkeypatch.setattr(runtime, "_wait_until_ready", lambda *_: events.append("ready"))
    monkeypatch.setattr(runtime, "_stop_server", lambda *_: events.append("stop"))
    try:
        with browser_bonsai(SimpleNamespace(port=18080)) as bonsai:
            assert isinstance(bonsai, BrowserBonsai)
            events.append("prepare")
            if fail:
                raise ValueError("fixture failure")
    except ValueError:
        assert fail
    assert events == ["ready", "prepare", "stop"]


def test_live_server_revision_after_local_clarification_creates_private_parent(
    tmp_path, monkeypatch
):
    import tools.browser_search_server as server
    from src.search_v2.candidate_diagnostics import CandidatePreparationError

    root = tmp_path / "new-run"
    checks, states = [], []

    def asset_boundary(*_):
        checks.append((root / "revision-1").is_dir())
        raise CandidatePreparationError("empty_conditions")

    monkeypatch.setattr("tools.browser_search_runtime.MODEL", SimpleNamespace(open=asset_boundary))
    monkeypatch.setattr(
        "src.config.CloudflareLiveSettings", lambda: pytest.fail("credentials loaded")
    )

    class Worker:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def submit(self, fn, *args):
            value = fn(*args)
            return SimpleNamespace(result=lambda: value)

    def fake_server(controller, *_args, **_kwargs):
        def serve():
            assert not root.exists()
            for revision, source in enumerate(
                ("マグカップ。赤が不要ではない。", "マグカップ。丸みのある形。")
            ):
                states.append(
                    controller.submit(
                        {
                            "action": "start" if revision == 0 else "revise",
                            "revision": revision,
                            "operation": f"revision-{revision:04}",
                            "source": source,
                        }
                    )
                )
                if revision == 0:
                    assert not root.exists()
            raise KeyboardInterrupt

        return SimpleNamespace(server_port=8772, serve_forever=serve, server_close=lambda: None)

    monkeypatch.setattr(server, "ThreadPoolExecutor", lambda **_: Worker())
    monkeypatch.setattr(server, "make_server", fake_server)
    monkeypatch.setattr(
        "sys.argv", ["browser_search_server", "--run-live-api", "--output-dir", str(root)]
    )
    server.main()
    assert [s["stage"] for s in states] == ["clarification", "clarification"]
    assert checks == [True]
    assert (root.stat().st_mode & 0o777) == 0o700
    assert ((root / "revision-1").stat().st_mode & 0o777) == 0o700


@pytest.mark.parametrize(
    "case", ["invalid_attempt", "symlink", "public_parent", "existing_revision"]
)
def test_revision_output_rejects_unsafe_or_existing_destinations(tmp_path, monkeypatch, case):
    from tools.browser_search_runtime import live_steps

    root = tmp_path / "run"
    attempt = 1
    if case == "invalid_attempt":
        attempt = 3
    elif case == "symlink":
        actual = tmp_path / "actual"
        actual.mkdir(mode=0o700)
        root.symlink_to(actual, target_is_directory=True)
    else:
        root.mkdir(mode=0o755 if case == "public_parent" else 0o700)
        if case == "existing_revision":
            (root / "revision-1").mkdir(mode=0o700)
            (root / "revision-1" / "marker").write_text("fixture")
    monkeypatch.setattr(
        "src.search_v2.siglip2.verify_assets", lambda _: pytest.fail("assets loaded")
    )
    with pytest.raises((ValueError, FileExistsError)):
        next(live_steps(root, source="マグカップ。丸みのある形。", attempt=attempt))
    if case == "existing_revision":
        assert (root / "revision-1" / "marker").read_text() == "fixture"
    elif case == "invalid_attempt":
        assert not root.exists()
    else:
        assert not (root / "revision-1").exists()


def test_new_search_batch_rejects_symlink_before_model_or_provider(tmp_path):
    from tools.browser_search_runtime import live_steps

    root = tmp_path / "run"
    root.mkdir(mode=0o700)
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    (root / "search-1").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="private run"):
        next(live_steps(root, source="マグカップ。丸みのある形。", attempt=1, batch=1))
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("attempt", [0, 1, 2])
def test_new_search_batch_uses_fresh_private_preparation_paths(tmp_path, monkeypatch, attempt):
    from tools.browser_search_runtime import live_steps

    root = tmp_path / "run"
    root.mkdir(mode=0o700)
    expected = root / "search-1"
    if attempt:
        expected = expected / f"revision-{attempt}"
    seen = []

    def stop_before_model(*args):
        seen.append(expected.is_dir())
        raise RuntimeError("fixture model boundary")

    monkeypatch.setattr(
        "tools.browser_search_runtime.MODEL", SimpleNamespace(open=stop_before_model)
    )
    with pytest.raises(RuntimeError, match="fixture model boundary"):
        next(live_steps(root, source="マグカップ。丸みのある形。", attempt=attempt, batch=1))
    assert seen == [True]
    assert expected.stat().st_mode & 0o777 == 0o700
    with pytest.raises(FileExistsError):
        next(live_steps(root, source="マグカップ。丸みのある形。", attempt=attempt, batch=1))
    assert seen == [True]
