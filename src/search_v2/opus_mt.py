"""Bounded local OPUS-MT adapter using the separately prepared CPU environment."""

import hashlib
import json
import os
from pathlib import Path
import subprocess


ASSET_HASHES = {
    "int8_float32/model.bin": "e96d00966af7ae59150ac8b84b83d68331860f4d02bdc290bac37ac3bb278c6b",
    "int8_float32/config.json": "152eb448f1020eb55f90971d7b95f61896abee8415d555ca51ae7897ac0a0e68",
    "int8_float32/shared_vocabulary.json": "c6e7f9988e5fe15c59ed331ce2d7c3dd551e70add8efc09f839f5a48168da4d6",
    "original/source.spm": "d0b5c3b10b5959f056ff2c86e2f2356129242ff1fc72d3a4a34d6a8c0eee4e57",
    "original/target.spm": "35d89c704e270d441fade716a3931d49c43179400682edcca7f180694982a2f6",
}


def _digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_assets(root):
    hashes = {name: _digest(root / name) for name in ASSET_HASHES}
    if hashes != ASSET_HASHES:
        raise ValueError("OPUS-MT assets differ from the evaluated model")
    return hashes


class OpusMtTranslator:
    def __init__(self, python, asset_root):
        # Preserve the venv executable path; resolving its symlink loses its packages.
        self._python = Path(python).absolute()
        self._root = Path(asset_root).resolve()
        self._worker = Path(__file__).with_name("opus_mt_worker.py")
        if not self._python.is_file() or not os.access(self._python, os.X_OK):
            raise ValueError("Local translation runtime is unavailable")
        self._hashes = verify_assets(self._root)
        self._worker_hash = _digest(self._worker)
        self.sha256 = hashlib.sha256(
            json.dumps(
                {
                    "assets": self._hashes,
                    "worker": self._worker_hash,
                    "profile": "opus-mt-ja-en-int8-v1",
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()

    def translate(self, phrases):
        try:
            if (
                type(phrases) is not tuple
                or not 1 <= len(phrases) <= 2
                or any(type(p) is not str or not 0 < len(p) <= 100 for p in phrases)
                or verify_assets(self._root) != self._hashes
                or _digest(self._worker) != self._worker_hash
            ):
                raise ValueError("Invalid local translation request")
            environment = {
                k: os.environ[k] for k in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP") if k in os.environ
            }
            environment.update({"PATH": os.defpath, "OMP_NUM_THREADS": "2", "HF_HUB_OFFLINE": "1"})
            result = subprocess.run(
                [str(self._python), "-I", str(self._worker), str(self._root)],
                input=json.dumps(phrases, ensure_ascii=False).encode(),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
                env=environment,
            )
            if result.returncode != 0 or len(result.stdout) > 16384:
                raise ValueError("Invalid local translation response")
            values = json.loads(result.stdout)
            if (
                type(values) is not list
                or len(values) != len(phrases)
                or any(
                    v is not None and (type(v) is not str or not 0 < len(v) <= 256) for v in values
                )
            ):
                raise ValueError("Invalid local translation response")
            return tuple(values)
        except Exception:
            raise ValueError("Local translation failed") from None
