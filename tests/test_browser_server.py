"""Loopback browser API origin, body, and static-file boundaries."""

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
from types import SimpleNamespace

import pytest

from src.search_v2.browser_search import BrowserSearch
from tools.browser_search_server import make_server


@pytest.fixture
def server(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<html>local</html>")
    with ThreadPoolExecutor(max_workers=1) as worker:
        controller = BrowserSearch(lambda *_: {"stage": "query"}, worker)
        monkeypatch.setattr(
            "tools.browser_search_server.HTTPServer",
            lambda address, handler: SimpleNamespace(server_port=8765, handler=handler),
        )
        yield make_server(controller, tmp_path)


def request(server, method, path, body=None, **headers):
    body = (body or "").encode()
    headers = {
        "Host": f"127.0.0.1:{server.server_port}",
        "Content-Length": str(len(body)),
        **headers,
    }
    raw = f"{method} {path} HTTP/1.0\r\n" + "".join(
        f"{key}: {value}\r\n" for key, value in headers.items()
    )
    output = bytearray()
    sock = SimpleNamespace(
        makefile=lambda *_: BytesIO(raw.encode() + b"\r\n" + body),
        sendall=output.extend,
        settimeout=lambda _: None,
    )
    server.handler(sock, ("127.0.0.1", 50000), server)
    head, payload = bytes(output).split(b"\r\n\r\n", 1)
    lines = head.decode().split("\r\n")
    return int(lines[0].split()[1]), dict(line.split(": ", 1) for line in lines[1:]), payload


def test_only_same_origin_json_commands(server):
    body = json.dumps({"action": "start", "revision": 0, "operation": "operation-0001"})
    headers = {"Content-Type": "application/json", "X-Amazon-Explorer-Browser": "1"}
    assert request(server, "POST", "/api/command", body, **headers)[0] == 403
    headers["Origin"] = "https://example.com"
    assert request(server, "POST", "/api/command", body, **headers)[0] == 403
    headers["Origin"] = f"http://127.0.0.1:{server.server_port}"
    assert request(server, "POST", "/api/command", body, **headers)[0] == 202
    assert request(server, "POST", "/api/command", body, **headers)[0] == 202


def test_host_static_and_read_boundaries(server):
    assert request(server, "GET", "/api/state", Host="example.com")[0] == 403
    assert request(server, "GET", "/api/state", **{"Sec-Fetch-Site": "cross-site"})[0] == 403
    assert request(server, "GET", "/../.env")[0] == 404
    status, headers, body = request(server, "GET", "/api/state")
    assert status == 200
    assert headers["Cache-Control"] == "no-store"
    assert "Access-Control-Allow-Origin" not in headers
    assert json.loads(body)["stage"] == "idle"


def test_restart_can_seed_input_without_starting_preparation(monkeypatch):
    import tools.browser_search_server as module

    seed = "マグカップ。できれば3000円以下。"

    def make(controller, *_args, **_kwargs):
        state = controller.snapshot()
        assert state["stage"] == "idle" and state["revision"] == 0
        assert state["input"] == seed
        return SimpleNamespace(
            server_port=8772, serve_forever=lambda: None, server_close=lambda: None
        )

    monkeypatch.setattr(module, "make_server", make)
    monkeypatch.setattr("sys.argv", ["server", "--offline-fixture"])
    module.main(initial_source=seed)
