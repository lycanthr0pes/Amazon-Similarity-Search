"""Private response recording for the explicitly approved loopback inference test."""

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import requests

from src.exceptions import BonsaiRequestError
from src.search_v2.bonsai_http import _configure_session
from src.search_v2.bonsai_http import _project_response
from src.search_v2.bonsai_http import _validate_transport_contract


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def write_private(path, body):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(body)


def write_json(path, value):
    write_private(
        path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n"
    )


class LoggedBonsaiTransport:
    def __init__(self, root: Path):
        if (
            not isinstance(root, Path)
            or not root.is_absolute()
            or root.resolve() != root
            or root.is_relative_to(REPOSITORY_ROOT)
        ):
            raise ValueError("A new absolute private log directory is required")
        root.mkdir(mode=0o700)
        self.root = root
        self.calls = 0
        self._response_body = None

    def post_json(self, **kwargs):
        _validate_transport_contract(**kwargs)
        parsed = urlsplit(kwargs["url"])
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or self.calls:
            raise BonsaiRequestError("Diagnostic transport requires one loopback request")
        self.calls += 1
        stage = "connect"
        complete = False
        status = None
        body = bytearray()
        session = None
        response = None
        failure = None
        limit = kwargs["maximum_response_bytes"]
        fd = os.open(
            self.root / "response-001.body",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            with os.fdopen(fd, "wb") as file:
                session = requests.Session()
                _configure_session(session)
                response = session.request(
                    method="POST",
                    url=kwargs["url"],
                    headers=dict(kwargs["headers"]),
                    data=kwargs["body"],
                    allow_redirects=False,
                    stream=True,
                    verify=True,
                    proxies={},
                )
                if not isinstance(response, requests.Response):
                    raise ValueError("Invalid response type")
                if type(response.status_code) is int and 100 <= response.status_code <= 599:
                    status = response.status_code
                stage = "body_read"
                for chunk in response.raw.stream(65_536, decode_content=False):
                    if type(chunk) is not bytes:
                        raise ValueError("Invalid response chunk")
                    prefix = chunk[: limit - len(body)]
                    file.write(prefix)
                    body.extend(prefix)
                    if len(prefix) < len(chunk):
                        stage = "response_limit"
                        raise ValueError("Response too large")
                complete = True
                self._response_body = bytes(body)
                stage = "response_contract"
                # Reuse the production metadata/body projection on the bytes already recorded.
                buffered = requests.Response()
                buffered.status_code = response.status_code
                buffered.headers = response.headers.copy()
                buffered._content = bytes(body)
                buffered._content_consumed = True
                return _project_response(buffered, maximum_response_bytes=limit)
        except Exception:
            failure = stage
            self.clear()
            raise BonsaiRequestError(
                "Bonsai diagnostic request failed; see private response log"
            ) from None
        finally:
            try:
                if response is not None:
                    response.close()
            finally:
                try:
                    if session is not None:
                        session.close()
                finally:
                    write_json(
                        self.root / "response-001.json",
                        {
                            "status_code": status,
                            "body_complete": complete,
                            "received_bytes": len(body),
                            "failure_stage": failure,
                        },
                    )

    def take_response_body(self):
        if self._response_body is None:
            raise BonsaiRequestError("No complete diagnostic response")
        body = self._response_body
        self.clear()
        return body

    def clear(self):
        self._response_body = None
