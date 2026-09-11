"""Context is retained per synset, without inventing cross-dictionary links."""

import sqlite3

from src.search_v2.lexical_dictionary import wordnet_senses, build_lexicon, SqliteLexicon
from src.search_v2.lexical_selection import LexicalSense


def database(tmp_path):
    path = tmp_path / "wordnet.db"
    with sqlite3.connect(path) as c:
        c.executescript("""CREATE TABLE word(wordid,lemma,lang,pos);
        CREATE TABLE sense(synset,wordid,src);
        CREATE TABLE synset_def(synset,lang,def,sid);
        CREATE TABLE synset_ex(synset,lang,def,sid);
        INSERT INTO word VALUES(1,'マウス','jpn','n'),(2,'mouse','eng','n');
        INSERT INTO sense VALUES('1-n',1,'hand'),('1-n',2,'eng-30');
        INSERT INTO synset_def VALUES('1-n','eng','a pointing device',0),('1-n','eng','moves a cursor',1),('1-n','jpn','コンピュータの入力機器',0),('1-n','jpn','カーソルを操作する',1);
        INSERT INTO synset_ex VALUES('1-n','jpn','マウスで画面を操作する',0);""")
    return path


def test_wordnet_retains_all_definition_rows_and_japanese_examples(tmp_path):
    values = tuple(wordnet_senses(database(tmp_path), include_context=True))
    assert len(values) == 1
    assert values[0].definition == "a pointing device; moves a cursor"
    assert values[0].definitions_ja == ("コンピュータの入力機器", "カーソルを操作する")
    assert values[0].examples_ja == ("マウスで画面を操作する",)


def test_context_lookup_uses_complete_wordnet_senses_without_merging_jmdict(tmp_path):
    db = tmp_path / "lexicon.db"
    senses = [LexicalSense("jmdict:1:1", "jmdict", ("マウス",), ("mouth",), "mouth")]
    senses.extend(wordnet_senses(database(tmp_path), include_context=True))
    build_lexicon(db, senses, {})
    with SqliteLexicon(db) as lexicon:
        assert lexicon.lookup("マウス")[0].sense_id == "jmdict:1:1"
        values = lexicon.lookup_contextual("マウス")
        assert values[0].sense_id == "wordnet:1-n"
        assert values[0].definitions_ja == ("コンピュータの入力機器", "カーソルを操作する")
        assert values[0].glosses == ("mouse",)


def test_context_asset_preparation_binds_config_and_profile(tmp_path):
    from tools.prepare_lexical_assets import prepare
    from test_lexical_dictionary import XML

    wordnet = database(tmp_path)
    source = tmp_path / "JMdict.xml"
    source.write_bytes(XML)
    for name in ("encoder.onnx", "tokenizer.json", "config.json"):
        (tmp_path / name).write_bytes(b"fixture")
    manifest = prepare(tmp_path, source, wordnet, contextual=True)
    assert manifest["schema_version"] == 2
    assert manifest["scorer"] == "japanese-sense-pairs-v1"
    assert "config.json" in manifest["files"]
