import json
from unittest.mock import patch

import pytest

from src.search_v2.cloudflare_request import CLOUDFLARE_IMAGE_MODEL_ID
from test_cloudflare_live_e2e import png_bytes
from test_cloudflare_live_e2e import response_for
from test_search_v2_cloudflare_http import CapturingSession
from test_search_v2_cloudflare_http import requests_response
from test_view_regeneration_live import arguments
from tools.view_model_probe import Klein9BTransport
from tools.view_model_probe import ViewModelProbeError
from tools.view_model_probe import run_model_probe


class RecordingTransport:
    def __init__(self, *, fail=False):
        self.templates = []
        self.fail = fail

    def generate(self, *, template, settings):
        self.templates.append(template)
        if self.fail:
            raise RuntimeError(settings.cloudflare_api_token.get_secret_value())
        return png_bytes()


def test_probe_sends_only_failed_view_and_records_actual_model(tmp_path):
    kwargs = arguments(tmp_path)
    transport = RecordingTransport()
    result = run_model_probe(**kwargs, transport=transport)
    assert len(transport.templates) == 1
    request = transport.templates[0]
    assert request.angle == "right_side"
    assert "toward the viewer" in request.prompt
    assert request.reference_image.width == request.reference_image.height == 511
    assert result["generation_model_id"] == "@cf/black-forest-labs/flux-2-klein-9b"
    assert result["request_count"] == 1 and result["retry_count"] == 0
    assert result["quality_status"] == "human_review_pending"
    assert len(result["diagnostic_contract_sha256"]) == 64
    root = kwargs["output_dir"]
    assert {p.name for p in root.iterdir()} == {"right_side.png", "summary.json"}
    assert root.stat().st_mode & 0o777 == 0o700
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in root.iterdir())
    assert json.loads((root / "summary.json").read_text()) == result
    assert CLOUDFLARE_IMAGE_MODEL_ID.endswith("klein-9b")


def test_probe_failure_has_one_call_without_retry_or_secret(tmp_path):
    transport = RecordingTransport(fail=True)
    with pytest.raises(ViewModelProbeError, match="generation failed after 1 request") as failure:
        run_model_probe(**arguments(tmp_path), transport=transport)
    assert len(transport.templates) == 1
    assert "fixture-cloudflare-api-token" not in str(failure.value)


def test_changed_reference_stops_before_generation(tmp_path):
    kwargs = arguments(tmp_path)
    kwargs["reference_sha256"] = "0" * 64
    transport = RecordingTransport()
    with pytest.raises(ViewModelProbeError, match="preparation failed"):
        run_model_probe(**kwargs, transport=transport)
    assert not transport.templates


def test_real_http_adapter_uses_fixed_9b_and_preserves_safety_limits(tmp_path):
    body = b"".join(response_for(png_bytes()).body_chunks)
    response, _ = requests_response((body,), content_length=str(len(body)))
    session = CapturingSession(response)
    with patch("tools.view_model_probe.requests.Session", return_value=session):
        run_model_probe(**arguments(tmp_path), transport=Klein9BTransport())
    prepared = session.prepared_request
    assert prepared.url.endswith("/ai/run/@cf/black-forest-labs/flux-2-klein-9b")
    assert prepared.headers["Content-Type"].startswith("multipart/form-data; boundary=")
    assert b"toward the viewer" in prepared.body
    assert b'name="input_image_0"' in prepared.body
    assert session.trust_env is False
    assert session.get_adapter("https://").max_retries.total == 0
    assert session.send_options["timeout"] == (120, 120)
    assert session.send_options["allow_redirects"] is False
    assert session.send_options["verify"] is True
    assert session.close_calls == 1


@pytest.mark.parametrize(
    "status,length", [(302, "12"), (500, "12"), (200, str(4 * 1024 * 1024 + 1))]
)
def test_http_rejection_does_not_read_body_or_retry(tmp_path, status, length):
    response, raw = requests_response((b"private-body",), status_code=status, content_length=length)
    session = CapturingSession(response)
    with patch("tools.view_model_probe.requests.Session", return_value=session) as factory:
        with pytest.raises(ViewModelProbeError, match="generation failed after 1 request"):
            run_model_probe(**arguments(tmp_path), transport=Klein9BTransport())
    factory.assert_called_once()
    assert session.close_calls == 1
    assert not (tmp_path / "regenerated" / "summary.json").exists()
    assert raw.stream_calls == []


def test_generic_four_uses_unmodified_production_prompts_and_exact_four_calls(tmp_path):
    from hashlib import sha256

    from src.search_v2.cloudflare_request import IMAGE_ANGLES
    from src.search_v2.cloudflare_request import build_cloudflare_request_set
    from tools.provisional_search_live_e2e import _fixed_context
    from tools.view_regeneration_live import _read_reference

    kwargs = arguments(tmp_path)
    expected = build_cloudflare_request_set(
        intent=_fixed_context()[0],
        preimage_plan_sha256=sha256(b"mug-view-regeneration-diagnostic-v1").hexdigest(),
        attempt=2,
        front_reference_png=_read_reference(kwargs["reference_path"], kwargs["reference_sha256"]),
        derive_front=True,
    )
    transport = RecordingTransport()
    result = run_model_probe(**kwargs, transport=transport, mode="generic-four")
    assert tuple(transport.templates) == expected.requests
    assert result["request_count"] == 4 and result["retry_count"] == 0
    assert result["mode"] == "generic-four"
    assert [item["angle"] for item in result["images"]] == list(IMAGE_ANGLES)
    assert result["quality_status"] == "human_review_pending"
    assert {p.name for p in kwargs["output_dir"].iterdir()} == {
        f"{angle}.png" for angle in IMAGE_ANGLES
    } | {"summary.json"}


def test_generic_four_stops_after_first_failure(tmp_path):
    transport = RecordingTransport(fail=True)
    with pytest.raises(ViewModelProbeError, match="generation failed after 1 request"):
        run_model_probe(**arguments(tmp_path), transport=transport, mode="generic-four")
    assert len(transport.templates) == 1


def test_unknown_probe_mode_never_calls_transport(tmp_path):
    transport = RecordingTransport()
    with pytest.raises(ViewModelProbeError, match="preparation failed"):
        run_model_probe(**arguments(tmp_path), transport=transport, mode="unknown")
    assert not transport.templates


def test_generic_four_real_adapter_sends_every_angle_to_9b(tmp_path):
    body = b"".join(response_for(png_bytes()).body_chunks)
    sessions = [
        CapturingSession(requests_response((body,), content_length=str(len(body)))[0])
        for _ in range(4)
    ]
    with patch("tools.view_model_probe.requests.Session", side_effect=sessions) as factory:
        result = run_model_probe(
            **arguments(tmp_path), transport=Klein9BTransport(), mode="generic-four"
        )
    assert result["request_count"] == factory.call_count == 4
    assert all(s.prepared_request.url.endswith("/flux-2-klein-9b") for s in sessions)
    assert all(s.close_calls == 1 for s in sessions)


def test_turntable_four_uses_reference_relative_rotation_without_absolute_view_names(tmp_path):
    transport = RecordingTransport()
    result = run_model_probe(**arguments(tmp_path), transport=transport, mode="turntable-four")
    assert result["mode"] == "turntable-four" and result["request_count"] == 4
    assert result["counterclockwise_degrees"] == [0, 90, 270, 180]
    assert set(result["counterclockwise_degrees"]) == {0, 90, 180, 270}
    for template in transport.templates:
        assert "camera stays fixed" in template.prompt
        assert "image 0" in template.prompt
        assert all(
            view not in template.prompt
            for view in ("left side", "right side", "rear three-quarter", "front three-quarter")
        )
    assert "zero rotation" in transport.templates[0].prompt
    assert "90 degrees counterclockwise" in transport.templates[1].prompt
    assert "90 degrees clockwise" in transport.templates[2].prompt
    assert "180 degrees" in transport.templates[3].prompt
