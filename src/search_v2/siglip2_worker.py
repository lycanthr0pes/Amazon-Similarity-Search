"""Credential-free SigLIP 2 image worker. No runtime downloads or text inference."""

from importlib.metadata import version
import json
from pathlib import Path
import socket
import sys


def _no_network(*args, **kwargs):
    raise RuntimeError("Network disabled in image worker")


def main():
    socket.socket.connect = _no_network
    socket.socket.connect_ex = _no_network
    socket.create_connection = _no_network
    manifest = json.loads(Path(__file__).with_name("siglip2_assets.json").read_text())
    if any(version(name) != expected for name, expected in manifest["versions"].items()):
        raise ValueError("SigLIP 2 runtime version mismatch")
    import numpy as np
    from PIL import Image
    import torch
    from transformers import AutoImageProcessor, AutoModel

    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    root = Path(sys.argv[1])
    if (root / "task.json").stat().st_size > 32768 or (
        root / "images.npy"
    ).stat().st_size > 5500000:
        raise ValueError("Worker input exceeds limit")
    task = json.loads((root / "task.json").read_text())
    pixels = np.load(root / "images.npy", allow_pickle=False)
    if (
        pixels.dtype != np.uint8
        or pixels.ndim != 4
        or pixels.shape[1:] != (224, 224, 3)
        or not 1 <= len(pixels) <= 36
    ):
        raise ValueError("Invalid worker images")
    model = AutoModel.from_pretrained(
        task["assets"],
        local_files_only=True,
        trust_remote_code=False,
        token=False,
        use_safetensors=True,
        dtype=torch.float32,
        attn_implementation="eager",
    ).eval()
    processor = AutoImageProcessor.from_pretrained(
        task["assets"], local_files_only=True, trust_remote_code=False, token=False, use_fast=False
    )
    output = []
    with torch.inference_mode():
        for start in range(0, len(pixels), 4):
            images = [Image.fromarray(row) for row in pixels[start : start + 4]]
            output.append(
                model.get_image_features(**processor(images=images, return_tensors="pt"))
                .cpu()
                .numpy()
            )
    np.save(root / "embeddings.npy", np.concatenate(output), allow_pickle=False)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(1) from None
