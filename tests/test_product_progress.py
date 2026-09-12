"""Worker progress reaches the browser before retrieval returns; no provider traffic."""

import io
import json
from types import SimpleNamespace

import test_candidate_search as candidate
from src.search_v2.playwright_products import PlaywrightProducts, run_product_worker


def test_detail_event_crosses_worker_adapter_before_completion(tmp_path, monkeypatch):
    request = candidate.start(tmp_path).plan.request
    events = [
        {"event": "progress"},
        {"event": "progress", "phase": "details"},
        {"event": "progress"},
        {"event": "result", "result": {"data": [[] for _ in request.queries], "metrics": {}}},
    ]
    process = SimpleNamespace(
        stdin=io.BytesIO(),
        stdout=io.BytesIO(b"".join(json.dumps(event).encode() + b"\n" for event in events)),
        returncode=0,
        wait=lambda **_: None,
    )
    monkeypatch.setattr("src.search_v2.playwright_products.shutil.which", lambda _: "node")
    monkeypatch.setattr(
        "src.search_v2.playwright_products.subprocess.Popen", lambda *_, **__: process
    )
    monkeypatch.setattr("src.search_v2.playwright_products._stop_worker", lambda _: None)
    progress = []
    transport = PlaywrightProducts(request, worker=run_product_worker, progress=progress.append)
    transport.fetch(request)
    progress.append("returned")
    assert progress == [1, "returned"]
