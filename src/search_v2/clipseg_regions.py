"""Bounded local CLIPSeg adapter; preparation never happens during inference."""

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image

from src.search_v2.counterfactual_image import VisualFocus
from src.search_v2.image_proxy import ProxyImage
from src.search_v2.shape_similarity import RegionMask


_MANIFEST = Path(__file__).with_name("clipseg_assets.json")
_WORKER = Path(__file__).with_name("clipseg_worker.py")
_MOBILE_MANIFEST = Path(__file__).with_name("mobile_sam_assets.json")
_MOBILE_WORKER = Path(__file__).with_name("mobile_sam_worker.py")
_REFINEMENT = Path(__file__).with_name("region_refinement.py")
REGION_TIMEOUT_SECONDS = 240
MOBILE_REGION_TIMEOUT_SECONDS = 600


def _verify_assets(root, manifest_path):
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("Prepared region model directory is required")
    manifest = json.loads(manifest_path.read_text())
    for name, digest in manifest["files"].items():
        with (root / name).open("rb") as file:
            actual = hashlib.sha256()
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                actual.update(chunk)
            if actual.hexdigest() != digest:
                raise ValueError("Region model assets changed")


def _diagnostics(root, masks):
    path = root / "diagnostics.json"
    if path.stat().st_size > 32768:
        raise ValueError("Region diagnostics exceed limit")
    data = json.loads(path.read_text())
    if (
        type(data) is not dict
        or set(data) != {"seconds", "rows"}
        or type(data["seconds"]) not in {int, float}
        or not math.isfinite(data["seconds"])
        or data["seconds"] < 0
        or type(data["rows"]) is not list
        or len(data["rows"]) != masks.shape[0] * masks.shape[1]
    ):
        raise ValueError("Invalid region diagnostics")
    for index, row in enumerate(data["rows"]):
        if type(row) is not dict or set(row) != {
            "image_index",
            "target_index",
            "proposal_count",
            "instance_count",
            "refined_count",
            "status",
        }:
            raise ValueError("Invalid region diagnostic row")
        i, j = divmod(index, masks.shape[1])
        for key, limit in (
            ("image_index", 35),
            ("target_index", 2),
            ("proposal_count", 256),
            ("instance_count", 4),
            ("refined_count", 4),
        ):
            if type(row[key]) is not int or not 0 <= row[key] <= limit:
                raise ValueError("Invalid region diagnostic counter")
        if (row["image_index"], row["target_index"]) != (i, j) or row["status"] != (
            "available" if masks[i, j].any() else "unavailable"
        ):
            raise ValueError("Region diagnostics do not match masks")
    return data


class LocalClipSegRegions:
    def __init__(self, *, python: Path, assets: Path, mobile_sam_assets: Path | None = None):
        if (
            not python.is_absolute()
            or not python.is_file()
            or not assets.is_absolute()
            or not assets.is_dir()
        ):
            raise ValueError("Prepared local region environment is required")
        _verify_assets(assets, _MANIFEST)
        self._mobile_sam_assets = mobile_sam_assets
        if mobile_sam_assets is not None:
            _verify_assets(mobile_sam_assets, _MOBILE_MANIFEST)
        self._python, self._assets = python, assets
        contract = (
            _MANIFEST.read_bytes()
            + _WORKER.read_bytes()
            + b"clipseg-cpu-2threads:letterbox352:threshold0.5:v1"
        )
        if mobile_sam_assets is not None:
            contract += (
                _MOBILE_MANIFEST.read_bytes()
                + _MOBILE_WORKER.read_bytes()
                + _REFINEMENT.read_bytes()
                + Path(__file__).read_bytes()
            )
        self.runtime_sha256 = hashlib.sha256(contract).hexdigest()
        self.last_diagnostics = None

    def extract(self, images, targets):
        if (
            type(images) is not tuple
            or not 1 <= len(images) <= 36
            or type(targets) is not tuple
            or not 1 <= len(targets) <= 3
            or len(set(targets)) != len(targets)
        ):
            raise ValueError("Region input count is invalid")
        for target in targets:
            VisualFocus(kind="shape", scope="part", target=target)
        images = tuple(ProxyImage.model_validate(i) for i in images)
        if len({i.pixel_sha256 for i in images}) != len(images):
            raise ValueError("Region image digests must be unique")
        mobile = getattr(self, "_mobile_sam_assets", None)
        size = 512 if mobile is not None else 352
        self.last_diagnostics = None
        pixels = []
        for source in images:
            image = Image.frombytes("RGB", (source.width, source.height), source.rgb_bytes)
            image.thumbnail((size - 8, size - 8), Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", (size, size), (255, 255, 255))
            canvas.paste(image, tuple((size - n) // 2 for n in image.size))
            pixels.append(np.asarray(canvas))
        with TemporaryDirectory(prefix="amazon-region-") as directory:
            root = Path(directory)
            task = {"assets": str(self._assets), "targets": targets}
            if mobile is not None:
                task["mobile_sam_assets"] = str(mobile)
            (root / "task.json").write_text(json.dumps(task))
            np.save(root / "images.npy", np.stack(pixels), allow_pickle=False)
            env = {
                name: value
                for name, value in os.environ.items()
                if name in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
            }
            env.update(
                HF_HUB_OFFLINE="1",
                TRANSFORMERS_OFFLINE="1",
                HF_HUB_DISABLE_TELEMETRY="1",
                TOKENIZERS_PARALLELISM="false",
                OMP_NUM_THREADS="2",
            )
            try:
                completed = subprocess.run(
                    [
                        str(self._python),
                        "-I",
                        str(_MOBILE_WORKER if mobile is not None else _WORKER),
                        str(root),
                    ],
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=MOBILE_REGION_TIMEOUT_SECONDS
                    if mobile is not None
                    else REGION_TIMEOUT_SECONDS,
                    check=False,
                )
                result = root / "masks.npy"
                if (
                    completed.returncode != 0
                    or not result.is_file()
                    or result.stat().st_size > (29_000_000 if mobile is not None else 14_000_000)
                ):
                    raise ValueError("Region worker failed")
                masks = np.load(result, allow_pickle=False)
                if (
                    masks.dtype != np.uint8
                    or masks.shape != (len(images), len(targets), size, size)
                    or not np.isin(masks, (0, 1)).all()
                ):
                    raise ValueError("Invalid region worker result")
                if mobile is not None:
                    self.last_diagnostics = _diagnostics(root, masks)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                raise ValueError("Local region extraction failed") from None
        return {
            (image.pixel_sha256, target): RegionMask.from_array(
                image.pixel_sha256, target, masks[i, j].astype(bool)
            )
            for i, image in enumerate(images)
            for j, target in enumerate(targets)
        }
