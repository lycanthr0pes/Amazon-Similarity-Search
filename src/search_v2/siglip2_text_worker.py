"""Bounded offline text encoder using the same pinned SigLIP 2 weights as images."""

from importlib.metadata import version
import json
from pathlib import Path
import socket
import sys


def _no_network(*args, **kwargs):
    raise RuntimeError("Network disabled in text worker")


def main():
    socket.socket.connect = _no_network
    socket.socket.connect_ex = _no_network
    socket.create_connection = _no_network
    manifest = json.loads(Path(__file__).with_name("siglip2_assets.json").read_text())
    if any(version(name) != expected for name, expected in manifest["versions"].items()):
        raise ValueError("SigLIP 2 runtime version mismatch")
    import numpy as np
    import torch
    from transformers import AutoModel, AutoTokenizer

    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    root = Path(sys.argv[1])
    if (root / "task.json").stat().st_size > 32768:
        raise ValueError("Worker input exceeds limit")
    task = json.loads((root / "task.json").read_text())
    texts = task["texts"]
    if (
        type(texts) is not list
        or not 1 <= len(texts) <= 3
        or any(type(t) is not str or not 1 <= len(t) <= 300 for t in texts)
    ):
        raise ValueError("Invalid texts")
    tokenizer = AutoTokenizer.from_pretrained(
        task["assets"], local_files_only=True, trust_remote_code=False, token=False
    )
    texts = [t.lower() for t in texts]
    encoded = tokenizer(
        texts, padding="max_length", max_length=64, truncation=False, return_tensors="pt"
    )
    if encoded["input_ids"].shape != (len(texts), 64):
        raise ValueError("Visual text exceeds model context")
    model = AutoModel.from_pretrained(
        task["assets"],
        local_files_only=True,
        trust_remote_code=False,
        token=False,
        use_safetensors=True,
        dtype=torch.float32,
        attn_implementation="eager",
    ).eval()
    with torch.inference_mode():
        output = model.get_text_features(**encoded).cpu().numpy()
    np.save(root / "text.npy", output, allow_pickle=False)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(1) from None
