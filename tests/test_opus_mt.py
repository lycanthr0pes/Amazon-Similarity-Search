"""Local MT uses fixed assets, bounded input and a separate credential-free runtime."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


def adapter(tmp_path, monkeypatch):
    import src.search_v2.opus_mt as mt

    monkeypatch.setattr(mt, "verify_assets", lambda _: {"model": "a" * 64})
    return mt, mt.OpusMtTranslator(Path(__import__("sys").executable), tmp_path)


def test_worker_receives_phrases_on_stdin_and_no_credentials(tmp_path, monkeypatch):
    mt, translator = adapter(tmp_path, monkeypatch)
    monkeypatch.setenv("OUTSCRAPER_API_KEY", "fixture-secret")
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        assert "縦置き" not in " ".join(argv)
        assert "OUTSCRAPER_API_KEY" not in kwargs["env"]
        assert kwargs["timeout"] == 30 and kwargs["stderr"] == subprocess.DEVNULL
        assert json.loads(kwargs["input"]) == ["縦置きノートパソコンスタンド"]
        return SimpleNamespace(returncode=0, stdout=b'["A vertical laptop stand."]')

    monkeypatch.setattr(mt.subprocess, "run", run)
    assert translator.translate(("縦置きノートパソコンスタンド",)) == ("A vertical laptop stand.",)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "result", [b"[]", b"{}", b"[3]", b'["x"]' * 20000], ids=["count", "object", "type", "size"]
)
def test_malformed_worker_output_is_rejected(tmp_path, monkeypatch, result):
    mt, translator = adapter(tmp_path, monkeypatch)
    monkeypatch.setattr(
        mt.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout=result)
    )
    with pytest.raises(ValueError, match="Local translation failed"):
        translator.translate(("スタンド",))


def test_timeout_has_no_retry_or_raw_exception(tmp_path, monkeypatch):
    mt, translator = adapter(tmp_path, monkeypatch)
    calls = []

    def run(*args, **kwargs):
        calls.append(1)
        raise subprocess.TimeoutExpired("private command", 30)

    monkeypatch.setattr(mt.subprocess, "run", run)
    with pytest.raises(ValueError, match="^Local translation failed$"):
        translator.translate(("スタンド",))
    assert calls == [1]


def test_asset_change_prevents_translation(tmp_path, monkeypatch):
    mt, translator = adapter(tmp_path, monkeypatch)
    monkeypatch.setattr(mt, "verify_assets", lambda _: {"model": "b" * 64})
    monkeypatch.setattr(
        mt.subprocess, "run", lambda *a, **kw: pytest.fail("Changed model executed")
    )
    with pytest.raises(ValueError):
        translator.translate(("スタンド",))
