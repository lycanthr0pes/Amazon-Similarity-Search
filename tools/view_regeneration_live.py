from __future__ import annotations

import argparse
import hashlib
import hmac
from io import BytesIO
from itertools import combinations
import json
from pathlib import Path

from PIL import Image

from src.config import CloudflareLiveSettings
from src.search_v2.cloudflare_http import CLOUDFLARE_MAX_RESPONSE_BYTES
from src.search_v2.cloudflare_http import CLOUDFLARE_REQUEST_TIMEOUT_SECONDS
from src.search_v2.cloudflare_http import RequestsCloudflareTransport
from src.search_v2.cloudflare_http import cloudflare_endpoint
from src.search_v2.cloudflare_http import parse_cloudflare_image_response
from src.search_v2.cloudflare_request import build_cloudflare_request_set
from src.search_v2.cloudflare_request import CloudflareImageRequest
from src.search_v2.cloudflare_request import cloudflare_image_request_sha256
from src.search_v2.image_proxy import ProxyImage
from src.search_v2.image_proxy import proxy_image_pixel_sha256
from src.search_v2.image_similarity import PHASH_DUPLICATE_MAX_DISTANCE
from src.search_v2.image_similarity import compute_phash
from src.search_v2.image_similarity import phash_hamming_distance
from tools import provisional_search_live_e2e as saved_files


_LANDMARK_VIEWS = {
    "front_three_quarter": (
        "Photograph the same white ceramic mug from image 0 in a front three-quarter view. "
        "The handle is at the right rear of the mug, with its oval opening visibly "
        "foreshortened and partly overlapped by the cylindrical cup. "
        "The camera looks down slightly, showing the inside of the circular rim. "
    ),
    "left_side": (
        "Photograph the same white ceramic mug from image 0 from its left side. "
        "The handle is on the far side, completely hidden behind the cylindrical cup. "
        "Its two attachment points stay on that far surface. The camera is level "
        "with the middle of the cup, so the rim appears as a narrow ellipse. "
    ),
    "right_side": (
        "Photograph the same white ceramic mug from image 0 from its right side, "
        "looking directly along the handle toward the cup. The handle points toward the viewer "
        "in the center foreground: its loop is seen edge-on as a narrow vertical curved strip, "
        "with the cylindrical cup behind it. The camera is level with the middle of the cup. "
    ),
    "rear_three_quarter": (
        "Photograph the same white ceramic mug from image 0 from behind in a rear three-quarter "
        "view. The handle is at the left rear of the mug, with its oval opening visibly "
        "foreshortened and partly overlapped by the cylindrical cup. "
        "The camera looks down slightly, showing the inside of the circular rim. "
    ),
}
_LANDMARK_FINISH = (
    "Keep the same straight cylindrical shape, height-to-width ratio, thick rounded rim, "
    "single curved handle with two attachments, and plain white ceramic material. "
    "One intact mug, centered on the same neutral gray studio background, soft lighting."
)


class ViewRegenerationError(RuntimeError):
    pass


def _read_reference(path, expected_sha256):
    details = path.lstat()
    if details.st_size > 2 * 1024 * 1024:
        raise ValueError("reference is too large")
    saved = saved_files._SavedReference(
        path, details.st_dev, details.st_ino, details.st_size, expected_sha256
    )
    body = saved_files._read_saved_reference(saved)
    if not hmac.compare_digest(hashlib.sha256(body).hexdigest(), expected_sha256):
        raise ValueError("reference changed")
    with Image.open(BytesIO(body), formats=("PNG",)) as source:
        if source.size != (512, 512) or source.mode != "RGB":
            raise ValueError("reference dimensions are invalid")
        source.load()
        with source.resize((511, 511), resample=Image.Resampling.LANCZOS) as resized:
            output = BytesIO()
            resized.save(output, format="PNG")
            return output.getvalue()


def _select_requests(requests, profile):
    if profile == "camera-v2":
        return requests
    if profile != "landmark-v1":
        raise ValueError("unknown prompt profile")
    return tuple(
        CloudflareImageRequest.model_validate(
            request.model_copy(update={"prompt": _LANDMARK_VIEWS[request.angle] + _LANDMARK_FINISH})
        )
        for request in requests
    )


def _image_hash(artifact):
    with Image.open(BytesIO(artifact.body), formats=("PNG",)) as source:
        source.load()
        pixels = source.tobytes()
    # The shared pHash implementation uses a pixel contract; no URL is fetched here.
    return compute_phash(
        ProxyImage(
            schema_version="2.0",
            source_url_sha256=hashlib.sha256(b"local-generated-view").hexdigest(),
            source_bytes_sha256=artifact.sha256,
            pixel_sha256=proxy_image_pixel_sha256(artifact.width, artifact.height, pixels),
            content_type="image/png",
            image_format="PNG",
            width=artifact.width,
            height=artifact.height,
            rgb_bytes=pixels,
        )
    )


def _compare_views(hashes):
    pairs = []
    for (first, first_hash), (second, second_hash) in combinations(hashes, 2):
        distance = phash_hamming_distance(first_hash, second_hash)
        pairs.append(
            {
                "first": first,
                "second": second,
                "hamming_distance": distance,
                "suspected_duplicate": distance <= PHASH_DUPLICATE_MAX_DISTANCE,
            }
        )
    return {
        "status": (
            "similar_views_detected"
            if any(pair["suspected_duplicate"] for pair in pairs)
            else "pose_review_required"
        ),
        "duplicate_distance_threshold": PHASH_DUPLICATE_MAX_DISTANCE,
        "pairs": pairs,
    }


def regenerate_views(
    *,
    reference_path,
    reference_sha256,
    output_dir,
    settings,
    transport=None,
    prompt_profile="camera-v2",
):
    """Run four diagnostic views of the fixed synthetic mug from a reviewed saved PNG."""
    try:
        if type(settings) is not CloudflareLiveSettings:
            raise ValueError("settings are invalid")
        saved_files._validate_new_review_path(output_dir)
        reference = _read_reference(reference_path, reference_sha256)
        intent, _, _ = saved_files._fixed_context()
        requests = build_cloudflare_request_set(
            intent=intent,
            preimage_plan_sha256=hashlib.sha256(b"mug-view-regeneration-diagnostic-v1").hexdigest(),
            attempt=2,
            front_reference_png=reference,
            derive_front=True,
        )
        selected_requests = _select_requests(requests.requests, prompt_profile)
        diagnostic_contract = {
            "profile": prompt_profile,
            "requests": [cloudflare_image_request_sha256(item) for item in selected_requests],
        }
        endpoint = cloudflare_endpoint(settings.cloudflare_account_id)
        selected = transport if transport is not None else RequestsCloudflareTransport()
        output_dir.mkdir(mode=0o700)
    except Exception:
        raise ViewRegenerationError("view preparation failed") from None

    calls = 0
    images = []
    hashes = []
    try:
        for request in selected_requests:
            calls += 1
            response = selected.post_multipart(
                request=request,
                url=endpoint,
                api_token=settings.cloudflare_api_token.get_secret_value(),
                timeout_seconds=CLOUDFLARE_REQUEST_TIMEOUT_SECONDS,
                allow_redirects=False,
                accept_encoding="identity",
                maximum_response_bytes=CLOUDFLARE_MAX_RESPONSE_BYTES,
            )
            artifact = parse_cloudflare_image_response(request=request, response=response)
            name = f"{request.angle}.png"
            saved_files._write_file(output_dir / name, artifact.body)
            images.append({"file": name, "sha256": artifact.sha256})
            hashes.append((request.angle, _image_hash(artifact)))
        summary = {
            "request_count": calls,
            "retry_count": 0,
            "quality_status": "human_review_pending",
            "context": "fixed_synthetic_mug_diagnostic",
            "reference_sha256": reference_sha256,
            "prompt_contract_sha256": requests.prompt_contract_sha256,
            "prompt_profile": prompt_profile,
            "diagnostic_contract_sha256": hashlib.sha256(
                json.dumps(diagnostic_contract, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "view_comparison": _compare_views(hashes),
            "images": images,
        }
        saved_files._write_file(
            output_dir / "summary.json", json.dumps(summary, indent=2).encode("utf-8")
        )
        return summary
    except Exception:
        raise ViewRegenerationError(f"view generation failed after {calls} request(s)") from None


def _main():
    parser = argparse.ArgumentParser(description="Four-view live diagnostic; approval required")
    parser.add_argument("--reference-path", type=Path, required=True)
    parser.add_argument("--reference-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-live-api", action="store_true", required=True)
    parser.add_argument(
        "--prompt-profile", choices=("camera-v2", "landmark-v1"), default="camera-v2"
    )
    args = parser.parse_args()
    try:
        settings = CloudflareLiveSettings()
    except Exception:
        raise SystemExit("view configuration failed") from None
    try:
        result = regenerate_views(
            reference_path=args.reference_path,
            reference_sha256=args.reference_sha256,
            output_dir=args.output_dir,
            settings=settings,
            prompt_profile=args.prompt_profile,
        )
    except ViewRegenerationError as exc:
        raise SystemExit(str(exc)) from None
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    _main()
