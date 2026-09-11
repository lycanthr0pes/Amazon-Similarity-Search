"""CLIPSeg semantics and MobileSAM instance/contour extraction on a local CPU."""

from importlib.metadata import version
import json
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image
import torch
from transformers import CLIPSegForImageSegmentation, CLIPSegProcessor

# This worker runs with -I; imports below are fixed local source, not the cwd.
sys.path.insert(0, str(Path(__file__).parent))
from region_refinement import (
    choose_instances,
    choose_parts,
    choose_regions,
    constrain_region,
    region_box,
    region_points,
)


def probability(processor, model, pixels, target):
    inputs = processor(
        text=[target], images=[Image.fromarray(pixels)], padding=True, return_tensors="pt"
    )
    heat = model(**inputs).logits[0].sigmoid().numpy()
    return np.asarray(
        Image.fromarray(heat).resize((pixels.shape[1], pixels.shape[0]), Image.Resampling.BILINEAR)
    )


def refine(predictor, heat):
    prompts = region_points(heat)
    if prompts is None:
        return None
    masks, _, _ = predictor.predict(
        point_coords=prompts[0], point_labels=prompts[1], multimask_output=True
    )
    candidates = choose_parts(tuple(masks), heat)
    return candidates[0] if candidates else None


def main():
    started = time.monotonic()
    root = Path(sys.argv[1])
    task = json.loads((root / "task.json").read_text())
    expected = {
        "torch": "2.6.0+cpu",
        "torchvision": "0.21.0+cpu",
        "transformers": "4.57.6",
        "numpy": "2.5.3",
        "pillow": "12.3.0",
        "tokenizers": "0.22.2",
        "timm": "1.0.15",
        "scipy": "1.18.1",
    }
    if any(version(name) != value for name, value in expected.items()):
        raise ValueError("Region environment changed")
    torch.set_num_threads(2)
    sys.path.insert(0, task["mobile_sam_assets"])
    from mobile_sam import sam_model_registry, SamAutomaticMaskGenerator, SamPredictor

    sam = sam_model_registry["vit_t"](
        checkpoint=str(Path(task["mobile_sam_assets"]) / "weights/mobile_sam.pt")
    ).eval()
    generator = SamAutomaticMaskGenerator(
        sam,
        points_per_side=8,
        points_per_batch=8,
        pred_iou_thresh=0.8,
        stability_score_thresh=0.9,
        crop_n_layers=0,
    )
    predictor = SamPredictor(sam)
    processor = CLIPSegProcessor.from_pretrained(task["assets"], local_files_only=True)
    clipseg = CLIPSegForImageSegmentation.from_pretrained(
        task["assets"], local_files_only=True, use_safetensors=True
    ).eval()
    images = np.load(root / "images.npy", allow_pickle=False)
    targets = task["targets"]
    if (
        images.dtype != np.uint8
        or images.ndim != 4
        or images.shape[1:] != (512, 512, 3)
        or not 1 <= len(images) <= 36
        or not 1 <= len(targets) <= 3
    ):
        raise ValueError("Invalid MobileSAM input")
    output = np.zeros((len(images), len(targets), 512, 512), dtype=np.uint8)
    diagnostics = []
    with torch.inference_mode():
        for i, pixels in enumerate(images):
            proposals = generator.generate(pixels)
            masks = tuple(p["segmentation"] for p in proposals)
            for j, target in enumerate(targets):
                heat = probability(processor, clipseg, pixels, target)
                instances = choose_instances(masks, heat)
                refined = []
                for instance in instances:
                    x0, y0, x1, y1 = region_box(instance)
                    crop = pixels[y0:y1, x0:x1]
                    local_heat = probability(processor, clipseg, crop, target)
                    predictor.set_image(crop)
                    result = refine(predictor, local_heat)
                    if result is None:
                        continue
                    expanded = np.zeros((512, 512), bool)
                    expanded[y0:y1, x0:x1] = result
                    expanded = constrain_region(expanded, instance)
                    if expanded.any():
                        refined.append(expanded)
                selected = choose_regions(tuple(refined), heat)
                if selected:
                    # Select one instance by semantic evidence, not shape similarity.
                    output[i, j] = selected[0]
                diagnostics.append(
                    {
                        "image_index": i,
                        "target_index": j,
                        "proposal_count": len(masks),
                        "instance_count": len(instances),
                        "refined_count": len(refined),
                        "status": "available" if selected else "unavailable",
                    }
                )
    np.save(root / "masks.npy", output, allow_pickle=False)
    (root / "diagnostics.json").write_text(
        json.dumps({"seconds": time.monotonic() - started, "rows": diagnostics})
    )


if __name__ == "__main__":
    main()
