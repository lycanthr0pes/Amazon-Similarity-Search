"""Read existing Japanese WordNet and Princeton 3.0 lexical antonym pointers."""

import hashlib
from pathlib import Path
import re
import sqlite3


def _adjectives(path):
    text = path.read_text(encoding="ascii")
    if "WordNet 3.0" not in text[:4096]:
        raise ValueError("WordNet contrast requires the 3.0 offset namespace")
    records = {}
    for line in text.splitlines():
        if not line or line.startswith("  "):
            continue
        fields = line.split("|", 1)[0].split()
        offset, _, pos, count = fields[:4]
        if not re.fullmatch(r"[0-9]{8}", offset) or pos not in {"a", "s"}:
            raise ValueError("Invalid WordNet adjective record")
        end = 4 + 2 * int(count, 16)
        words = tuple(re.sub(r"\((?:a|p|ip)\)$", "", w).replace("_", " ") for w in fields[4:end:2])
        pointer_end = end + 1 + 4 * int(fields[end])
        if pointer_end != len(fields) or offset in records or not words:
            raise ValueError("Invalid WordNet adjective pointers")
        pointers = []
        for i in range(end + 1, pointer_end, 4):
            relation, target, target_pos, indices = fields[i : i + 4]
            if relation != "!" or target_pos not in {"a", "s"}:
                continue
            if not re.fullmatch(r"[0-9a-fA-F]{4}", indices):
                raise ValueError("Invalid WordNet lexical indices")
            source_index, target_index = int(indices[:2], 16), int(indices[2:], 16)
            if not 1 <= source_index <= len(words) or target_index < 1:
                raise ValueError("Invalid WordNet antonym indices")
            pointers.append((target, source_index, target_index))
        records[offset] = (words, tuple(pointers), line.partition("|")[2].strip()[:240])
    for _, pointers, _ in records.values():
        for target, _, index in pointers:
            if target not in records or index > len(records[target][0]):
                raise ValueError("Unbound WordNet antonym")
    return records


class WordNetContrastDictionary:
    """No downloads, writes, synonym traversal, or implicit choice between senses."""

    def __init__(self, japanese_db, adjective_data, *, expected_sha256=None):
        paths = (Path(japanese_db), Path(adjective_data))
        if any(not p.is_file() for p in paths) or paths[1].stat().st_size > 8 * 1024 * 1024:
            raise ValueError("Prepared WordNet contrast assets are missing or invalid")
        digests = []
        for path in paths:
            with path.open("rb") as stream:
                digests.append(hashlib.file_digest(stream, "sha256").hexdigest())
        self.sha256 = hashlib.sha256(
            ("wordnet-3.0-contrast-v1:" + ":".join(digests)).encode()
        ).hexdigest()
        if expected_sha256 is not None and self.sha256 != expected_sha256:
            raise ValueError("WordNet contrast assets differ from the pinned version")
        self._adjectives = _adjectives(paths[1])
        self._db = sqlite3.connect(paths[0].resolve().as_uri() + "?mode=ro", uri=True)
        self._db.execute("PRAGMA trusted_schema=OFF")
        self._db.execute("PRAGMA query_only=ON")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self._db.close()

    def _senses(self, forms, pos):
        if not 0 < len(forms) <= 3 or any(not 0 < len(f) <= 100 for f in forms):
            return ()
        slots = ",".join("?" for _ in forms)
        rows = self._db.execute(
            f"SELECT DISTINCT s.synset FROM word w JOIN sense s USING(wordid) "
            f"WHERE w.lemma IN ({slots}) AND w.lang='jpn' AND w.pos=? "
            "AND s.src='hand' ORDER BY s.synset LIMIT 17",
            (*forms, pos),
        ).fetchall()
        return tuple(row[0] for row in rows)

    def antonym(self, forms):
        senses = self._senses(forms, "a")
        if len(senses) != 1:
            return None
        pairs = self.antonyms(forms)
        return pairs[0] if len(pairs) == 1 else None

    def antonyms(self, forms):
        senses = self._senses(forms, "a")
        if len(senses) > 16:
            return ()
        pairs = set()
        for source in senses:
            record = self._adjectives.get(source.split("-")[0])
            if record is None:
                continue
            words, pointers, _ = record
            pairs.update(
                (words[start - 1], self._adjectives[target][0][end - 1], source, target + "-a")
                for target, start, end in pointers
            )
        return tuple(sorted(pairs)) if len(pairs) <= 4 else ()

    def definition(self, sense_id):
        return self._adjectives[sense_id.split("-")[0]][2]

    def noun(self, forms):
        senses = self._senses(forms, "n")
        if len(senses) != 1:
            return None
        rows = self._db.execute(
            "SELECT DISTINCT w.lemma FROM word w JOIN sense s USING(wordid) "
            "WHERE s.synset=? AND w.lang='eng' AND w.pos='n' ORDER BY w.wordid LIMIT 17",
            senses,
        ).fetchall()
        # Synonyms within a single confirmed sense can share one literal noun phrase.
        for (word,) in rows:
            word = word.replace("_", " ")
            if re.fullmatch(r"[A-Za-z][A-Za-z -]{0,79}", word):
                return word, senses[0]
        return None
