"""Offline dictionary import and read-only, bounded lookup."""

import hashlib
import json
from pathlib import Path
import sqlite3
import xml.etree.ElementTree as ET

from src.search_v2.lexical_selection import LexicalSense, MAX_SENSES, lexical_key


MAX_DICTIONARY_BYTES = 500_000_000


def _digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def jmdict_senses(path):
    path = Path(path)
    if not 0 < path.stat().st_size <= MAX_DICTIONARY_BYTES:
        raise ValueError("Invalid dictionary size")
    for _, entry in ET.iterparse(path, events=("end",)):
        if entry.tag != "entry":
            continue
        sequence = entry.findtext("ent_seq")
        words = [k.findtext("keb") for k in entry.findall("k_ele") if not k.findall("ke_inf")]
        readings = entry.findall("r_ele")
        pos = []
        for index, sense in enumerate(entry.findall("sense")):
            pos = [p.text for p in sense.findall("pos")] or pos
            if not any(p == "n" or p.startswith("noun (common)") for p in pos):
                continue
            # Reading-restricted senses need a fuller mapping; do not broaden them.
            if sense.findall("stagr") or sense.findall("misc"):
                continue
            allowed = [s.text for s in sense.findall("stagk")]
            forms = [w for w in words if not allowed or w in allowed]
            lookup_forms = list(forms)
            for reading in readings:
                restrictions = [r.text for r in reading.findall("re_restr")]
                if reading.findall("re_inf"):
                    continue
                if restrictions and not set(restrictions) & set(forms):
                    continue
                lookup_forms.append(reading.findtext("reb"))
            if not words:
                forms = list(lookup_forms)
            glosses = tuple(
                g.text
                for g in sense.findall("gloss")
                if g.text
                and g.get("{http://www.w3.org/XML/1998/namespace}lang", "eng") == "eng"
                and g.get("g_type") is None
            )
            if forms and glosses:
                yield LexicalSense(
                    f"jmdict:{sequence}:{index + 1}",
                    "jmdict",
                    tuple(dict.fromkeys(forms)),
                    glosses,
                    "; ".join(glosses)[:4000],
                    tuple(dict.fromkeys(lookup_forms)),
                )
        entry.clear()


def wordnet_senses(path, *, include_context=False):
    connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA trusted_schema=OFF")
        # Only manually checked Japanese links; never traverse hypernyms as synonyms.
        query = """SELECT s.synset, w.lemma, w.lang FROM sense s JOIN word w USING(wordid)
                   WHERE w.pos='n' AND ((w.lang='jpn' AND s.src='hand') OR w.lang='eng')
                   ORDER BY s.synset, w.wordid"""
        grouped = {}
        for key, lemma, language in connection.execute(query):
            grouped.setdefault(key, {"jpn": [], "eng": []})[language].append(
                lemma.replace("_", " ")
            )
        definitions, japanese, examples = {}, {}, {}
        for key, language, text in connection.execute(
            "SELECT synset,lang,def FROM synset_def ORDER BY synset,lang,sid"
        ):
            target = definitions if language == "eng" else japanese if language == "jpn" else None
            if target is not None and text:
                target.setdefault(key, []).append(text)
        if include_context:
            for key, text in connection.execute(
                "SELECT synset,def FROM synset_ex WHERE lang='jpn' ORDER BY synset,sid"
            ):
                if text:
                    examples.setdefault(key, []).append(text)
        for key, languages in grouped.items():
            if languages["jpn"] and languages["eng"]:
                yield LexicalSense(
                    "wordnet:" + key,
                    "wordnet",
                    tuple(dict.fromkeys(languages["jpn"])),
                    tuple(dict.fromkeys(languages["eng"])),
                    "; ".join(definitions.get(key, ()))[:4000],
                    definitions_ja=tuple(japanese.get(key, ())) if include_context else (),
                    examples_ja=tuple(examples.get(key, ())) if include_context else (),
                )
    finally:
        connection.close()


def build_lexicon(path, senses, metadata):
    path = Path(path)
    # Refuse to overwrite an existing dictionary or another process's staging file.
    with path.open("xb"):
        pass
    connection = sqlite3.connect(path)
    try:
        connection.executescript("""
            CREATE TABLE sense (id TEXT PRIMARY KEY, source TEXT NOT NULL, forms TEXT NOT NULL,
                                glosses TEXT NOT NULL, definition TEXT NOT NULL, context TEXT NOT NULL);
            CREATE TABLE form (key TEXT NOT NULL, sense_id TEXT NOT NULL,
                               PRIMARY KEY(key, sense_id));
            CREATE TABLE metadata (value TEXT NOT NULL);
            PRAGMA user_version=2;
        """)
        with connection:
            connection.execute("INSERT INTO metadata VALUES (?)", (json.dumps(metadata),))
            for sense in senses:
                connection.execute(
                    "INSERT INTO sense VALUES (?,?,?,?,?,?)",
                    (
                        sense.sense_id,
                        sense.source,
                        json.dumps(sense.forms, ensure_ascii=False),
                        json.dumps(sense.glosses),
                        sense.definition,
                        json.dumps(
                            {
                                "definitions_ja": sense.definitions_ja,
                                "examples_ja": sense.examples_ja,
                            },
                            ensure_ascii=False,
                        ),
                    ),
                )
                connection.executemany(
                    "INSERT OR IGNORE INTO form VALUES (?,?)",
                    (
                        (lexical_key(form), sense.sense_id)
                        for form in (sense.lookup_forms or sense.forms)
                    ),
                )
    except Exception:
        connection.close()
        path.unlink()
        raise
    finally:
        connection.close()


class SqliteLexicon:
    def __init__(self, path):
        path = Path(path).resolve()
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_DICTIONARY_BYTES:
            raise ValueError("Invalid lexical database")
        self.sha256 = _digest(path)
        self._connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        self._connection.execute("PRAGMA trusted_schema=OFF")
        self._connection.execute("PRAGMA query_only=ON")
        self._version = self._connection.execute("PRAGMA user_version").fetchone()[0]
        if self._version not in (1, 2):
            self.close()
            raise ValueError("Unsupported lexical database version")

    def lookup(self, phrase):
        return self._lookup(phrase, contextual=False)

    def lookup_contextual(self, phrase):
        if self._version != 2:
            raise ValueError("Contextual lookup requires a new lexical database")
        return self._lookup(phrase, contextual=True)

    def lookup_products(self, product, context):
        """Find compounds ending in the requested object, using source noun anchors."""
        from src.search_v2.tokenizer import _analyze_japanese_source

        if type(product) is not str or not 0 < len(product) <= 100:
            raise ValueError("Invalid product lookup")
        if type(context) is not str or len(context) > 2000:
            raise ValueError("Invalid product context")
        key = lexical_key(product)
        keys = {key}
        anchors = tuple(
            dict.fromkeys(
                lexical_key(m.surface)
                for m in _analyze_japanese_source(context).morphemes
                if m.part_of_speech == "名詞" and not m.surface.isdecimal()
            )
        )[:8]

        # Values are escaped LIKE literals. Never treat source text as a SQL pattern.
        def escape(value):
            return value.replace("!", "!!").replace("%", "!%").replace("_", "!_")

        for anchor in anchors:
            rows = self._connection.execute(
                "SELECT DISTINCT key FROM form WHERE key LIKE ? ESCAPE '!' "
                "AND key LIKE ? ESCAPE '!' ORDER BY key LIMIT ?",
                ("%" + escape(key), "%" + escape(anchor) + "%", MAX_SENSES + 1),
            ).fetchall()
            if len(rows) > MAX_SENSES:
                raise ValueError("Too many product compounds")
            keys.update(r[0] for r in rows)
        senses = {}
        for candidate in sorted(keys):
            for sense in self.lookup_contextual(candidate):
                senses[sense.sense_id] = sense
        if len(senses) > MAX_SENSES:
            raise ValueError("Too many product senses")
        return tuple(senses.values())

    def _lookup(self, phrase, *, contextual):
        if type(phrase) is not str or not 0 < len(phrase) <= 100:
            raise ValueError("Invalid dictionary lookup")
        context = "s.context" if self._version == 2 else "'{}'"
        # Prefer one dictionary inventory; never guess alignment between sense IDs.
        priority = (
            "CASE WHEN s.source='wordnet' AND json_array_length(json_extract(s.context,'$.definitions_ja'))>0 THEN 0 ELSE 1 END,"
            if contextual
            else ""
        )
        rows = self._connection.execute(
            f"SELECT s.id,s.source,s.forms,s.glosses,s.definition,{context} FROM form f "
            f"JOIN sense s ON f.sense_id=s.id WHERE f.key=? ORDER BY {priority}s.source,s.id LIMIT ?",
            (lexical_key(phrase), MAX_SENSES + 1),
        ).fetchall()
        preferred = (
            [r for r in rows if r[1] == "wordnet" and json.loads(r[5]).get("definitions_ja")]
            if contextual
            else []
        )
        rows = preferred or [r for r in rows if r[1] == "jmdict"] or rows
        if len(rows) > MAX_SENSES:
            raise ValueError("Too many dictionary senses")
        return tuple(
            LexicalSense(
                r[0],
                r[1],
                tuple(json.loads(r[2])),
                tuple(json.loads(r[3])),
                r[4],
                definitions_ja=tuple(json.loads(r[5]).get("definitions_ja", ())),
                examples_ja=tuple(json.loads(r[5]).get("examples_ja", ())),
            )
            for r in rows
        )

    def close(self):
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
