"""Compile already acquired dictionaries; no network or model inference."""

import argparse
import hashlib
import itertools
import json
from pathlib import Path

from src.search_v2.lexical_assets import asset_hashes
from src.search_v2.lexical_dictionary import build_lexicon, jmdict_senses, wordnet_senses


def prepare(root, jmdict, wordnet, *, contextual=False):
    root = Path(root)
    # Input files, notices and model files are prepared separately by the operator.
    for name in (
        ("encoder.onnx", "tokenizer.json", "config.json")
        if contextual
        else ("encoder.onnx", "tokenizer.json")
    ):
        if not (root / name).is_file():
            raise ValueError("Prepare local model files before compiling dictionaries")
    metadata = {"schema_version": 1, "sources": {}}
    for name, path in (("jmdict", jmdict), ("wordnet", wordnet)):
        with Path(path).open("rb") as stream:
            metadata["sources"][name] = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest_path = root / "runtime-manifest.json"
    if manifest_path.exists():
        raise ValueError("An existing bundle must not be overwritten")
    build_lexicon(
        root / "lexicon.sqlite3",
        itertools.chain(jmdict_senses(jmdict), wordnet_senses(wordnet, include_context=contextual)),
        metadata,
    )
    manifest = {
        "schema_version": 2 if contextual else 1,
        "files": asset_hashes(root, contextual=contextual),
    }
    if contextual:
        manifest["scorer"] = "japanese-sense-pairs-v1"
    with manifest_path.open("x") as stream:
        json.dump(manifest, stream, sort_keys=True, indent=2)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-root", type=Path, required=True)
    parser.add_argument("--jmdict-xml", type=Path, required=True)
    parser.add_argument("--wordnet-db", type=Path, required=True)
    parser.add_argument(
        "--contextual", action="store_true", help="prepare Japanese definitions and the pair scorer"
    )
    args = parser.parse_args()
    try:
        prepare(args.asset_root, args.jmdict_xml, args.wordnet_db, contextual=args.contextual)
    except Exception:
        print('{"status":"failed","stage":"local_asset_preparation"}')
        return 1
    print('{"status":"prepared","network_used":false}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
