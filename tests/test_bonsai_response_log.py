"""Test-only loopback logging retains both rejected and accepted response bodies."""

import importlib.util
import json
import stat

import pytest

from src.exceptions import BonsaiRequestError
from src.search_v2.bonsai_request import BONSAI_MAX_RESPONSE_BYTES, BONSAI_REQUEST_HEADERS
from test_search_v2_bonsai_http import RecordingSession, make_response


def log_transport(root):
    assert importlib.util.find_spec("tools.bonsai_response_log") is not None, (
        "response logging is required"
    )
    from tools.bonsai_response_log import LoggedBonsaiTransport

    return LoggedBonsaiTransport(root)


def request(transport, **overrides):
    args = dict(
        url="http://127.0.0.1:18080/v1/chat/completions",
        headers=BONSAI_REQUEST_HEADERS,
        body=b"{}",
        allow_redirects=False,
        accept_encoding="identity",
        maximum_response_bytes=BONSAI_MAX_RESPONSE_BYTES,
    )
    args.update(overrides)
    return transport.post_json(**args)


@pytest.mark.parametrize(
    "status,body,content_type",
    [
        (200, b'{"private":"model output"}', "application/json"),
        (500, b"private model failure", "text/plain"),
        (200, b"invalid JSON", "application/json"),
    ],
)
def test_all_statuses_and_invalid_content_are_saved_exactly(
    tmp_path, monkeypatch, status, body, content_type
):
    import requests

    response, raw = make_response(
        (body,), status_code=status, content_type=content_type, content_length=str(len(body))
    )
    session = RecordingSession(response)
    monkeypatch.setattr(requests, "Session", lambda: session)
    root = tmp_path / "run"
    transport = log_transport(root)
    result = request(transport)
    assert (root / "response-001.body").read_bytes() == body
    metadata = json.loads((root / "response-001.json").read_text())
    assert metadata["status_code"] == status and metadata["body_complete"] is True
    assert result.status_code == status
    assert session.close_calls == 1 and raw.close_calls == 1
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in root.iterdir())
    assert "private" not in repr(transport)
    with pytest.raises(BonsaiRequestError):
        request(transport)
    assert len(session.request_calls) == 1


@pytest.mark.parametrize("failure", ["limit", "stream", "connect"])
def test_incomplete_response_has_prefix_and_fixed_reason(tmp_path, monkeypatch, failure):
    import requests

    body = b"x" * (BONSAI_MAX_RESPONSE_BYTES + 1) if failure == "limit" else b"partial"
    response, _ = make_response(
        (body,),
        content_length=None,
        stream_error=RuntimeError("private failure") if failure == "stream" else None,
    )
    session = RecordingSession(
        response, error=RuntimeError("private failure") if failure == "connect" else None
    )
    monkeypatch.setattr(requests, "Session", lambda: session)
    root = tmp_path / "run"
    transport = log_transport(root)
    with pytest.raises(BonsaiRequestError):
        request(transport)
    metadata = json.loads((root / "response-001.json").read_text())
    assert metadata["body_complete"] is False
    assert (
        metadata["failure_stage"]
        == {"limit": "response_limit", "stream": "body_read", "connect": "connect"}[failure]
    )
    assert "private failure" not in json.dumps(metadata)
    assert (root / "response-001.body").read_bytes() == (
        b"" if failure == "connect" else body[:BONSAI_MAX_RESPONSE_BYTES]
    )
    assert session.close_calls == 1


def test_existing_log_directory_is_never_overwritten(tmp_path):
    with pytest.raises((ValueError, FileExistsError)):
        log_transport(tmp_path)


def test_external_endpoint_is_rejected_before_network(tmp_path, monkeypatch):
    import requests

    monkeypatch.setattr(requests, "Session", lambda: pytest.fail("unexpected network"))
    transport = log_transport(tmp_path / "run")
    with pytest.raises(BonsaiRequestError):
        request(transport, url="https://bonsai.example.test/v1/chat/completions")


def test_repository_directory_cannot_receive_raw_logs(tmp_path, monkeypatch):
    transport = log_transport(tmp_path / "first")
    import tools.bonsai_response_log as module

    monkeypatch.setattr(module, "REPOSITORY_ROOT", tmp_path, raising=False)
    with pytest.raises(ValueError):
        type(transport)(tmp_path / "second")
