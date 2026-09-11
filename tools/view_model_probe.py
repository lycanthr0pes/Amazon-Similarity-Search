from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import requests

from src.config import CloudflareLiveSettings
from src.search_v2 import cloudflare_http as image_http
from src.search_v2.cloudflare_request import CloudflareImageRequest
from src.search_v2.cloudflare_request import build_cloudflare_request_set
from src.search_v2.cloudflare_request import cloudflare_image_request_sha256
from tools import provisional_search_live_e2e as saved_files
from tools import view_regeneration_live as view_diagnostic


MODEL_ID = "@cf/black-forest-labs/flux-2-klein-9b"
_TURNTABLE_ROTATIONS = {
    "front_three_quarter": (0, "Keep the product at zero rotation"),
    "left_side": (90, "Rotate the product 90 degrees counterclockwise as seen from above"),
    "right_side": (270, "Rotate the product 90 degrees clockwise as seen from above"),
    "rear_three_quarter": (180, "Rotate the product 180 degrees as seen from above"),
}


def _turntable_templates(templates):
    result = []
    for template in templates:
        _, rotation = _TURNTABLE_ROTATIONS[template.angle]
        prompt = (
            f"{rotation} relative to its original pose in image 0. "
            "The camera stays fixed at the exact position, height, distance and focal length "
            "used in image 0. Only the product turns around its vertical axis through its center. "
            "Use image 0 as the identity and starting-pose reference for this single rotation. "
            "Render exactly one photograph of the same product after this rotation. "
            "Keep its shape, dimensions, parts, attachments, material and color unchanged. "
            "Attached parts rotate rigidly with the product and become hidden when behind it. "
            "Keep the lighting, background, framing and image dimensions consistent with image 0. "
            "Do not mirror the image, rotate the image plane, add parts, labels or extra views."
        )
        result.append(
            CloudflareImageRequest.model_validate(template.model_copy(update={"prompt": prompt}))
        )
    return tuple(result)


class ViewModelProbeError(RuntimeError):
    pass


def run_model_probe(
    *, reference_path, reference_sha256, output_dir, settings, transport=None, mode="landmark-right"
):
    try:
        if mode not in {"landmark-right", "generic-four", "turntable-four"}:
            raise ValueError("probe mode is invalid")
        if type(settings) is not CloudflareLiveSettings:
            raise ValueError("settings are invalid")
        saved_files._validate_new_review_path(output_dir)
        reference = view_diagnostic._read_reference(reference_path, reference_sha256)
        template_set = build_cloudflare_request_set(
            intent=saved_files._fixed_context()[0],
            preimage_plan_sha256=hashlib.sha256(b"mug-view-regeneration-diagnostic-v1").hexdigest(),
            attempt=2,
            front_reference_png=reference,
            derive_front=True,
        )
        if mode == "landmark-right":
            templates = (view_diagnostic._select_requests(template_set.requests, "landmark-v1")[2],)
            contract = {
                "generation_model_id": MODEL_ID,
                "control_template_sha256": cloudflare_image_request_sha256(templates[0]),
            }
        else:
            templates = template_set.requests
            if mode == "turntable-four":
                templates = _turntable_templates(templates)
            contract = {
                "generation_model_id": MODEL_ID,
                "mode": mode,
                "control_template_sha256s": [
                    cloudflare_image_request_sha256(template) for template in templates
                ],
            }
            if mode == "turntable-four":
                contract["counterclockwise_degrees"] = [
                    _TURNTABLE_ROTATIONS[template.angle][0] for template in templates
                ]
        selected = transport if transport is not None else Klein9BTransport()
        output_dir.mkdir(mode=0o700)
    except Exception:
        raise ViewModelProbeError("model probe preparation failed") from None
    calls = 0
    images = []
    try:
        for template in templates:
            calls += 1
            body = selected.generate(template=template, settings=settings)
            normalized = image_http._normalized_png(body)
            name = f"{template.angle}.png"
            saved_files._write_file(output_dir / name, normalized)
            images.append(
                {
                    "angle": template.angle,
                    "file": name,
                    "sha256": hashlib.sha256(normalized).hexdigest(),
                }
            )
        summary = {
            **contract,
            "diagnostic_contract_sha256": hashlib.sha256(
                json.dumps(contract, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "reference_sha256": reference_sha256,
            "request_count": calls,
            "retry_count": 0,
            "quality_status": "human_review_pending",
        }
        if mode == "landmark-right":
            summary.update(output_sha256=images[0]["sha256"], angle="right_side")
        else:
            summary["images"] = images
        saved_files._write_file(
            output_dir / "summary.json", json.dumps(summary, indent=2).encode("utf-8")
        )
        return summary
    except Exception:
        raise ViewModelProbeError(
            f"model probe generation failed after {calls} request(s)"
        ) from None


class Klein9BTransport:
    def generate(self, *, template, settings):
        """Send the control's multipart fields to the fixed diagnostic model only."""
        try:
            if type(settings) is not CloudflareLiveSettings:
                raise ValueError("settings are invalid")
            template = CloudflareImageRequest.model_validate(template)
            if template.schema_version != "3.0":
                raise ValueError("probe view is invalid")
            endpoint = (
                "https://api.cloudflare.com/client/v4/accounts/"
                f"{settings.cloudflare_account_id}/ai/run/{MODEL_ID}"
            )
            headers = dict(image_http.CLOUDFLARE_REQUEST_HEADERS)
            headers["Authorization"] = f"Bearer {settings.cloudflare_api_token.get_secret_value()}"
            session = requests.Session()
            response = None
            try:
                image_http._configure_session(session)
                response = session.request(
                    method="POST",
                    url=endpoint,
                    headers=headers,
                    files=image_http._multipart_files(template),
                    timeout=(120, 120),
                    allow_redirects=False,
                    stream=True,
                    verify=True,
                    proxies={},
                )
                if not isinstance(response, requests.Response):
                    raise ValueError("invalid response")
                envelope = image_http._project_response(
                    response, maximum_response_bytes=image_http.CLOUDFLARE_MAX_RESPONSE_BYTES
                )
                # Decode bytes without attaching the 4B control template's artifact identity.
                return image_http._decoded_image(image_http._response_image_text(envelope))
            finally:
                try:
                    if response is not None:
                        image_http._close_response(response)
                finally:
                    session.close()
        except Exception:
            raise ViewModelProbeError("model probe transport failed") from None


def _main():
    parser = argparse.ArgumentParser(description="9B model probe; approval required")
    parser.add_argument("--reference-path", type=Path, required=True)
    parser.add_argument("--reference-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-live-api", action="store_true", required=True)
    parser.add_argument(
        "--mode",
        choices=("landmark-right", "generic-four", "turntable-four"),
        default="landmark-right",
    )
    args = parser.parse_args()
    try:
        settings = CloudflareLiveSettings()
    except Exception:
        raise SystemExit("model probe configuration failed") from None
    try:
        result = run_model_probe(
            reference_path=args.reference_path,
            reference_sha256=args.reference_sha256,
            output_dir=args.output_dir,
            settings=settings,
            mode=args.mode,
        )
    except ViewModelProbeError as exc:
        raise SystemExit(str(exc)) from None
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    _main()
