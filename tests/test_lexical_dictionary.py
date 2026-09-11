"""Dictionary imports retain sense and orthography restrictions."""

from src.search_v2.lexical_dictionary import SqliteLexicon, build_lexicon, jmdict_senses


XML = b"""<?xml version="1.0"?><JMdict><entry><ent_seq>1</ent_seq>
<k_ele><keb>\xe6\xa9\x8b</keb></k_ele><k_ele><keb>\xe7\xae\xb8</keb></k_ele>
<r_ele><reb>\xe3\x81\xaf\xe3\x81\x97</reb></r_ele>
<sense><stagk>\xe6\xa9\x8b</stagk><pos>noun (common) (futsuumeishi)</pos><gloss>bridge</gloss></sense>
<sense><stagk>\xe7\xae\xb8</stagk><gloss>chopsticks</gloss></sense>
</entry></JMdict>"""


def test_import_does_not_mix_different_headword_senses(tmp_path):
    path = tmp_path / "dictionary.xml"
    path.write_bytes(XML)
    senses = list(jmdict_senses(path))
    assert len(senses) == 2
    assert "橋" in senses[0].forms and "箸" not in senses[0].forms
    assert "箸" in senses[1].forms and "橋" not in senses[1].forms


def test_lookup_retains_all_ambiguous_reading_senses(tmp_path):
    source = tmp_path / "dictionary.xml"
    source.write_bytes(XML)
    db = tmp_path / "lexicon.db"
    build_lexicon(db, jmdict_senses(source), {"source": "synthetic"})
    with SqliteLexicon(db) as lexicon:
        assert len(lexicon.lookup("ハシ")) == 2
        assert lexicon.lookup("箸")[0].glosses == ("chopsticks",)
        assert lexicon.lookup("未収録商品") == ()
        assert len(lexicon.sha256) == 64


def test_reading_is_lookup_evidence_not_a_synonym(tmp_path):
    from src.search_v2.lexical_selection import terms_from_sense

    source = tmp_path / "dictionary.xml"
    source.write_bytes(XML)
    db = tmp_path / "lexicon.db"
    build_lexicon(db, jmdict_senses(source), {"source": "synthetic"})
    with SqliteLexicon(db) as lexicon:
        sense = lexicon.lookup("橋")[0]
        assert terms_from_sense("橋", sense).synonyms == ()
        assert len(lexicon.lookup("はし")) == 2
