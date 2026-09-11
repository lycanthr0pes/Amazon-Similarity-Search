"""Load a prepared lexical bundle locally, checking all file identities first."""

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path

from src.search_v2.lexical_dictionary import SqliteLexicon
from src.search_v2.lexical_expansion import DictionaryQueryExpander, ContextualQueryExpander
from src.search_v2.lexical_context import OnnxSenseScorer
from src.search_v2.lexical_runtime import GinzaProductParser, OnnxGlossScorer


ASSET_NAMES = ("lexicon.sqlite3", "encoder.onnx", "tokenizer.json")


def asset_hashes(root, *, contextual=False):
    result = {}
    for name in (*ASSET_NAMES, *(("config.json",) if contextual else ())):
        with (Path(root) / name).open("rb") as stream:
            result[name] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


@contextmanager
def load_lexical_services(root):
    root = Path(root)
    manifest = json.loads((root / "runtime-manifest.json").read_bytes())
    contextual = manifest.get("schema_version") == 2
    expected = {
        "schema_version": 2 if contextual else 1,
        "files": asset_hashes(root, contextual=contextual),
    }
    if contextual:
        expected["scorer"] = "japanese-sense-pairs-v1"
    if manifest != expected:
        raise ValueError("Lexical assets differ from the prepared manifest")
    with SqliteLexicon(root / "lexicon.sqlite3") as lexicon:
        scorer = (
            OnnxSenseScorer(root / "encoder.onnx", root / "tokenizer.json", root / "config.json")
            if contextual
            else OnnxGlossScorer(root / "encoder.onnx", root / "tokenizer.json")
        )
        parser = GinzaProductParser()
        expander = (
            ContextualQueryExpander(lexicon, scorer)
            if contextual
            else DictionaryQueryExpander(lexicon, scorer)
        )
        yield expander, parser
