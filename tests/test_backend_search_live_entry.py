from __future__ import annotations

from itertools import product
from datetime import datetime
from datetime import timezone
import json
from pathlib import Path
import sys
import time

import pytest

from conftest import backend_search_live_test_enabled
from tools import bonsai_live_e2e as bonsai
from tools.backend_search_live_e2e import owned_bonsai


@pytest.mark.parametrize("live,clip,backend", product((False, True), repeat=3))
def test_live_entry_requires_every_opt_in(live, clip, backend):
    assert backend_search_live_test_enabled(
        run_live_api=live,
        run_clip_runtime=clip,
        run_backend_search_e2e=backend,
    ) is (live and clip and backend)


@pytest.mark.parametrize("failure", ["body", "startup"])
def test_owned_bonsai_is_stopped_when_startup_or_call_fails(tmp_path, monkeypatch, failure):
    server = tmp_path / "server"
    server.write_bytes(b"fixture")
    server.chmod(0o700)
    model = tmp_path / "model.gguf"
    model.write_bytes(b"fixture")
    config = bonsai.BonsaiLiveE2EConfig(server, model, 18080)
    calls = []
    process = object()

    def launch(received):
        assert received == config
        calls.append("launch")
        return process

    def ready(received, port):
        assert received is process and port == 18080
        calls.append("ready")
        if failure == "startup":
            raise RuntimeError("fixture startup failure")

    def stop(received, port):
        assert received is process and port == 18080
        calls.append("stop")

    monkeypatch.setattr(bonsai, "_launch_server", launch)
    monkeypatch.setattr(bonsai, "_wait_until_ready", ready)
    monkeypatch.setattr(bonsai, "_stop_server", stop)
    with pytest.raises(RuntimeError):
        with owned_bonsai(config) as transport:
            assert isinstance(transport, bonsai.RequestsBonsaiTransport)
            calls.append("body")
            raise RuntimeError("fixture body failure")
    assert calls == (
        ["launch", "ready", "body", "stop"] if failure == "body" else ["launch", "ready", "stop"]
    )


@pytest.mark.live_api
@pytest.mark.clip_runtime
@pytest.mark.backend_search_e2e
def test_natural_language_images_ranking_history(pytestconfig):
    from src.config import CloudflareLiveSettings
    from src.config import OutscraperLiveSettings
    from src.search_v2.image_proxy_service import ImageProxyService
    from src.search_v2.image_similarity import verify_clip_asset_directory
    from src.search_v2.image_similarity_process import ProcessIsolatedClipImageEncoder
    from src.search_v2.outscraper_http import RequestsOutscraperTransport
    from tools.backend_search_live_e2e import BackendE2EConfig
    from tools.backend_search_live_e2e import BackendE2EServices
    from tools.backend_search_live_e2e import BackendSearchE2EError
    from tools.backend_search_live_e2e import REFERENCE_CONFIRMATION
    from tools.backend_search_live_e2e import SEARCH_CONFIRMATION
    from tools.backend_search_live_e2e import RequestsBackendImageTransport
    from tools.backend_search_live_e2e import run_backend_search_e2e

    if not sys.stdin.isatty():
        pytest.fail("Backend E2E requires interactive image confirmation", pytrace=False)

    def confirm(stage, review):
        print(
            json.dumps({"stage": stage, **review}, ensure_ascii=False, sort_keys=True), flush=True
        )
        phrase = REFERENCE_CONFIRMATION if stage == "reference" else SEARCH_CONFIRMATION
        return input(f"続ける場合は「{phrase}」と入力: ") == phrase

    try:
        config = BackendE2EConfig(
            output_dir=Path(pytestconfig.getoption("--backend-search-output-dir")),
            asset_root=Path(pytestconfig.getoption("--backend-search-clip-asset-root")),
            bonsai_port=pytestconfig.getoption("--bonsai-e2e-port"),
        )
        bonsai_config = bonsai.BonsaiLiveE2EConfig(
            server_binary=Path(pytestconfig.getoption("--bonsai-server-bin")),
            model_path=Path(pytestconfig.getoption("--bonsai-model-path")),
            port=config.bonsai_port,
        )
        verify_clip_asset_directory(config.asset_root)
        result = run_backend_search_e2e(
            config,
            BackendE2EServices(
                bonsai_session=lambda: owned_bonsai(bonsai_config),
                load_cloudflare=CloudflareLiveSettings,
                cloudflare_transport=RequestsBackendImageTransport(),
                load_outscraper_api_key=lambda: OutscraperLiveSettings().outscraper_api_key,
                outscraper_transport=RequestsOutscraperTransport(),
                proxy_service=ImageProxyService(allowed_hosts=("m.media-amazon.com",)),
                encoder=ProcessIsolatedClipImageEncoder(),
                now=lambda: datetime.now(timezone.utc),
                sleep=time.sleep,
                confirm=confirm,
            ),
        )
    except BackendSearchE2EError as error:
        print(json.dumps(error.safe_metadata(), ensure_ascii=True, sort_keys=True), flush=True)
        pytest.fail("Backend search E2E failed; see safe stage metadata", pytrace=False)
    except Exception:
        pytest.fail("Backend search E2E configuration failed", pytrace=False)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True), flush=True)
    if result["status"] != "succeeded":
        pytest.fail("Backend search E2E was not approved to completion", pytrace=False)
