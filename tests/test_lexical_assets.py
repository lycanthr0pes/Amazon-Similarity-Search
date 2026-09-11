"""Model and dictionary identities are checked before loading any runtime."""

import hashlib
import json

import pytest


def test_changed_asset_is_rejected_before_loading_models(tmp_path, monkeypatch):
    from src.search_v2 import lexical_assets as assets

    names = ("lexicon.sqlite3", "encoder.onnx", "tokenizer.json")
    hashes = {}
    for name in names:
        path = tmp_path / name
        path.write_bytes(b"fixture")
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (tmp_path / "runtime-manifest.json").write_text(
        json.dumps({"schema_version": 1, "files": hashes})
    )
    (tmp_path / "encoder.onnx").write_bytes(b"changed")
    monkeypatch.setattr(assets, "OnnxGlossScorer", lambda *_: pytest.fail("No model should load"))
    with pytest.raises(ValueError):
        with assets.load_lexical_services(tmp_path):
            pytest.fail("Invalid assets were accepted")


def test_prepare_builds_reproducible_local_bundle_without_overwrite(tmp_path):
    import sqlite3
    from tools.prepare_lexical_assets import prepare
    from test_lexical_dictionary import XML
    from src.search_v2.lexical_dictionary import SqliteLexicon

    (tmp_path / "encoder.onnx").write_bytes(b"fixture-model")
    (tmp_path / "tokenizer.json").write_bytes(b"fixture-tokenizer")
    source = tmp_path / "JMdict.xml"
    source.write_bytes(XML)
    wordnet = tmp_path / "wordnet.db"
    with sqlite3.connect(wordnet) as connection:
        connection.executescript(
            "CREATE TABLE word(wordid, lemma, lang, pos); CREATE TABLE sense(synset, wordid, src); CREATE TABLE synset_def(synset, def, lang, sid);"
        )
    manifest = prepare(tmp_path, source, wordnet)
    assert manifest["schema_version"] == 1
    with SqliteLexicon(tmp_path / "lexicon.sqlite3") as lexicon:
        assert lexicon.sha256 == manifest["files"]["lexicon.sqlite3"]
        assert lexicon.lookup("橋")[0].glosses == ("bridge",)
    with pytest.raises(ValueError):
        prepare(tmp_path, source, wordnet)
