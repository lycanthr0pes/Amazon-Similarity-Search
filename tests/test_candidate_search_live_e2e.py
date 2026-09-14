"""Offline checks of the bounded candidate live entry; no provider is contacted."""

from contextlib import nullcontext
from dataclasses import replace
import importlib
import json
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

import test_candidate_connected_flow as connected
import test_candidate_search as candidate
import test_candidate_visual_conditions as visual
from src.search_v2.bonsai_request import BonsaiHttpResponse
from src.search_v2.candidate_queries import build_candidate_queries
from src.search_v2.outscraper_contract import build_outscraper_request
from tools.backend_search_live_e2e import BackendE2EConfig, BackendE2EServices
from tools.bonsai_response_log import write_private


def module():
    return importlib.import_module("tools.candidate_search_live_e2e")


def setup_run(tmp_path, monkeypatch, approvals=(True, True)):
    m = module()
    flow = candidate.flow
    clip, calls = connected.clip(monkeypatch, tmp_path)
    events = []

    class Bonsai:
        def __init__(self):
            self.calls = 0

        def post_json(self, **kwargs):
            self.calls += 1
            assert self.calls == 1, "Bonsai only extracts CLIP visual conditions"
            delegate = visual.VisualBonsai(tmp_path, [visual.draft("丸みのある形")])
            body = delegate.evaluate(kwargs["body"])
            return BonsaiHttpResponse(200, "application/json", len(body), None, (body,))

    bonsai = Bonsai()
    images = flow.CloudflareTransport(flow.cloudflare_responses())

    class Products:
        def get(self, **kwargs):
            from src.search_v2.outscraper_http import OutscraperHttpResponse

            products = [
                {
                    "asin": f"B000CA000{i}",
                    "name": f"マグカップ{i}",
                    "price": 1000 * i,
                    "currency": "JPY",
                    "image_1": f"https://m.media-amazon.com/images/{i}.png",
                    "query": next(value for key, value in kwargs["params"] if key == "query"),
                }
                for i in range(1, 5)
            ]
            body = json.dumps(
                {"id": "candidate-live-fixture", "status": "Success", "data": products}
            ).encode()
            write_private(tmp_path / "outscraper-response.json", body)
            return OutscraperHttpResponse(200, "application/json", len(body), None, (body,))

    def confirm(stage, review):
        events.append((stage, len(images.calls), bonsai.calls))
        assert all(__import__("pathlib").Path(p).is_file() for p in review["images"])
        return approvals[len(events) - 1]

    config = BackendE2EConfig(tmp_path / "live-output", tmp_path)
    services = BackendE2EServices(
        bonsai_session=lambda: nullcontext(bonsai),
        load_cloudflare=lambda: SimpleNamespace(
            cloudflare_account_id=flow.ACCOUNT_ID,
            cloudflare_api_token=SecretStr(flow.CLOUDFLARE_TOKEN),
        ),
        cloudflare_transport=images,
        load_outscraper_api_key=lambda: SecretStr("fixture-key"),
        outscraper_transport=Products(),
        proxy_service=clip["proxy_service"],
        encoder=clip["encoder"],
        now=lambda: flow.NOW,
        sleep=lambda _: None,
        confirm=confirm,
    )
    return m, config, services, events, calls


@pytest.mark.parametrize(
    "approvals,expected_images", [((False, True), 1), ((True, False), 2), ((True, True), 2)]
)
def test_candidate_entry_obeys_image_stops_and_reopens_history(
    tmp_path, monkeypatch, approvals, expected_images
):
    m, config, services, events, _ = setup_run(tmp_path, monkeypatch, approvals)
    result = m.run_candidate_e2e(config, services, image_score_mode="appearance")
    assert result["cloudflare_calls"] == expected_images
    assert events[0] == ("reference", 1, 1)
    if all(approvals):
        assert events[1] == ("search", 2, 1)
        assert result["status"] == "succeeded"
        assert result["bonsai_calls"] == 1 and result["outscraper_tasks"] == 1
        assert result["history_images_verified"] == 2 and result["product_count"] == 4
        assert result["ranking_profile_id"] == "candidate-appearance-v1"
        response = json.loads((config.output_dir / "outscraper-response-1.json").read_text())
        assert response["status_code"] == 200 and response["response_bytes"] > 0
        assert len(response["response_sha256"]) == 64
        assert "fixture-key" not in (config.output_dir / "outscraper-response-1.json").read_text()
        assert (
            json.loads((config.output_dir / "history.json").read_text())["known_holdout_accuracy"]
            is None
        )
    else:
        assert result["status"] == "cancelled"
        assert result["outscraper_tasks"] == 0 and result["bonsai_calls"] == 1


def test_entry_sanitizes_failure_without_repeating_requests(tmp_path, monkeypatch):
    m, config, services, _, _ = setup_run(tmp_path, monkeypatch)

    def fail():
        raise RuntimeError("sensitive-fixture-error")

    result = m.run_candidate_e2e(
        config, replace(services, load_outscraper_api_key=fail), image_score_mode="appearance"
    )
    assert result["status"] == "failed" and result["failure_stage"] == "candidates"
    assert result["outscraper_tasks"] == 0
    assert "sensitive-fixture-error" not in (config.output_dir / "summary.json").read_text()


def test_product_adapter_binds_approved_request_and_refuses_repeat(tmp_path):
    m = module()
    first = build_outscraper_request(
        build_candidate_queries("マグカップ").query_plan, postal_code="100-0001"
    )
    second = build_outscraper_request(
        build_candidate_queries("椅子").query_plan, postal_code="100-0001"
    )
    calls = []

    class Transport:
        def get(self, **kwargs):
            calls.append(kwargs)
            raise RuntimeError("synthetic transport failure")

    transport = m.CandidateProducts(
        first, lambda: SecretStr("fixture-key"), Transport(), lambda _: None
    )
    with pytest.raises(ValueError):
        transport.fetch(second)
    assert not calls
    with pytest.raises(Exception):
        transport.fetch(first)
    with pytest.raises(ValueError):
        transport.fetch(first)
    assert len(calls) == 1


@pytest.mark.parametrize("changed_stage", ["reference", "search"])
def test_changed_preview_stops_before_the_next_provider(tmp_path, monkeypatch, changed_stage):
    m, config, services, _, _ = setup_run(tmp_path, monkeypatch)

    def confirm(stage, review):
        if stage == changed_stage:
            from pathlib import Path

            Path(review["images"][-1]).write_bytes(b"replaced-preview")
        return True

    result = m.run_candidate_e2e(
        config, replace(services, confirm=confirm), image_score_mode="appearance"
    )
    assert result["status"] == "failed"
    assert result["cloudflare_calls"] == (1 if changed_stage == "reference" else 2)
    assert result["outscraper_tasks"] == 0


@pytest.mark.parametrize("translate", [False, True])
@pytest.mark.parametrize("image_model", ["clip", "siglip2"])
def test_cli_passes_runtime_configuration_before_any_live_call(
    tmp_path, monkeypatch, translate, image_model
):
    from pathlib import Path
    import sys
    import src.search_v2.image_similarity as similarity

    m = module()
    binary, model = tmp_path / "llama-server", tmp_path / "Bonsai.gguf"
    binary.write_bytes(b"fixture-executable")
    binary.chmod(0o700)
    model.write_bytes(b"fixture-model")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "candidate-search",
            "--run-live-api",
            "--image-model",
            "clip",
            "--output-dir",
            str(tmp_path / "run"),
            "--asset-root",
            str(tmp_path),
            "--server-bin",
            str(binary),
            "--model-path",
            str(model),
        ],
    )
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(similarity, "verify_clip_asset_directory", lambda _: None)
    if image_model == "siglip2":
        from src.search_v2 import siglip2

        monkeypatch.setattr(siglip2, "verify_assets", lambda _: None)
        index = sys.argv.index("--image-model")
        del sys.argv[index : index + 2]
        sys.argv.extend(["--image-python", str(binary)])
    if translate:
        from contextlib import contextmanager
        from src.search_v2.lexical_expansion import ContextualQueryExpander
        import src.search_v2.lexical_assets as assets
        import src.search_v2.opus_mt as mt

        translator = SimpleNamespace(sha256="f" * 64)
        monkeypatch.setattr(mt, "OpusMtTranslator", lambda python, root: translator)

        @contextmanager
        def lexical(root):
            yield ContextualQueryExpander(None, None), SimpleNamespace()

        monkeypatch.setattr(assets, "load_lexical_services", lexical)
        sys.argv.extend(
            [
                "--lexical-assets",
                str(tmp_path),
                "--translation-python",
                str(binary),
                "--opus-mt-assets",
                str(tmp_path),
            ]
        )
    calls = []

    def run(config, services, *, select_query, **options):
        calls.append(config)
        assert callable(select_query)
        assert config.bonsai_port == 18080
        assert config.asset_root == Path(tmp_path)
        assert options["image_score_mode"] == (
            "siglip2_text_image" if image_model == "siglip2" else "appearance"
        )
        assert type(services.encoder).__name__ == (
            "LocalSiglip2MultimodalEncoder"
            if image_model == "siglip2"
            else "ProcessIsolatedClipImageEncoder"
        )
        if translate:
            assert options["lexical_expander"]._translator is translator
            assert options["sense_resolver_factory"]
        return {"status": "succeeded"}

    monkeypatch.setattr(m, "run_candidate_e2e", run)
    assert m.main() == 0
    assert len(calls) == 1


def lexical_expander():
    from src.search_v2.lexical_expansion import DictionaryQueryExpander
    from src.search_v2.lexical_selection import LexicalSense
    from test_lexical_connection import Scorer

    class Lexicon:
        sha256 = "a" * 64

        def lookup(self, phrase):
            assert phrase == "マグカップ"
            return (
                LexicalSense("fixture:mug", "fixture", ("マグカップ", "マグ"), ("mug",), "mug"),
            )

    return DictionaryQueryExpander(Lexicon(), Scorer())
