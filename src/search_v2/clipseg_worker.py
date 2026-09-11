"""Isolated CPU worker. Only explicit local assets and temporary files are read."""

from importlib.metadata import version
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image
import torch
from transformers import CLIPSegForImageSegmentation, CLIPSegProcessor


def main():
    root = Path(sys.argv[1])
    task = json.loads((root / "task.json").read_text())
    expected = {
        "torch": "2.6.0+cpu",
        "transformers": "4.57.6",
        "numpy": "2.5.3",
        "pillow": "12.3.0",
        "tokenizers": "0.22.2",
    }
    if any(version(name) != value for name, value in expected.items()):
        raise ValueError("Region worker environment changed")
    torch.set_num_threads(2)
    processor = CLIPSegProcessor.from_pretrained(task["assets"], local_files_only=True)
    model = CLIPSegForImageSegmentation.from_pretrained(
        task["assets"], local_files_only=True, use_safetensors=True
    ).eval()
    images = np.load(root / "images.npy", allow_pickle=False)
    if (
        images.dtype != np.uint8
        or images.ndim != 4
        or images.shape[1:] != (352, 352, 3)
        or not 1 <= len(images) <= 36
        or not 1 <= len(task["targets"]) <= 3
    ):
        raise ValueError("Invalid region worker input")
    masks = np.zeros((len(images), len(task["targets"]), 352, 352), dtype=np.uint8)
    with torch.inference_mode():
        for i, pixels in enumerate(images):
            for j, target in enumerate(task["targets"]):
                inputs = processor(
                    text=[target],
                    images=[Image.fromarray(pixels)],
                    padding=True,
                    return_tensors="pt",
                )
                logits = model(**inputs).logits
                masks[i, j] = (logits[0].sigmoid().numpy() >= 0.5).astype(np.uint8)
    np.save(root / "masks.npy", masks, allow_pickle=False)


if __name__ == "__main__":
    main()
