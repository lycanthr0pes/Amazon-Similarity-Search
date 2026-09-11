import hashlib
import json
import stat

import pytest

from src.config import CloudflareLiveSettings
from src.search_v2.cloudflare_request import IMAGE_ANGLES
from test_cloudflare_live_e2e import FakeTransport
from test_cloudflare_live_e2e import FailingTransport
from test_cloudflare_live_e2e import png_bytes
from tools.view_regeneration_live import ViewRegenerationError
from tools.view_regeneration_live import regenerate_views


def arguments(tmp_path):
    reference = tmp_path / "preview.png"
    reference.write_bytes(png_bytes())
    reference.chmod(0o600)
    return {
        "reference_path": reference,
        "reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "output_dir": tmp_path / "regenerated",
        "settings": CloudflareLiveSettings(
            _env_file=None,
            cloudflare_account_id="a" * 32,
            cloudflare_api_token="fixture-cloudflare-api-token",
        ),
    }


def test_four_calls_share_reference_and_save_private_separate_outputs(tmp_path):
    kwargs = arguments(tmp_path)
    original = kwargs["reference_path"].read_bytes()
    transport = FakeTransport()
    summary = regenerate_views(**kwargs, transport=transport)
    assert len(transport.calls) == 4
    assert tuple(call["request"].angle for call in transport.calls) == IMAGE_ANGLES
    references = [call["request"].reference_image for call in transport.calls]
    assert all(ref == references[0] and ref.width == 511 for ref in references)
    assert all(call["request"].attempt == 2 for call in transport.calls)
    assert summary["request_count"] == 4 and summary["retry_count"] == 0
    assert summary["quality_status"] == "human_review_pending"
    root = kwargs["output_dir"]
    assert {p.name for p in root.iterdir()} == {f"{angle}.png" for angle in IMAGE_ANGLES} | {
        "summary.json"
    }
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in root.iterdir())
    assert json.loads((root / "summary.json").read_text()) == summary
    assert kwargs["reference_path"].read_bytes() == original


def test_provider_failure_stops_without_retry_or_secret_output(tmp_path):
    kwargs = arguments(tmp_path)
    transport = FailingTransport()
    with pytest.raises(ViewRegenerationError, match="generation failed after 1 request") as failure:
        regenerate_views(**kwargs, transport=transport)
    assert len(transport.calls) == 1
    assert "fixture-cloudflare-api-token" not in str(failure.value)
    assert not (kwargs["output_dir"] / "summary.json").exists()


@pytest.mark.parametrize("invalid", ["digest", "symlink", "existing_output"])
def test_invalid_files_stop_before_transport(tmp_path, invalid):
    kwargs = arguments(tmp_path)
    if invalid == "digest":
        kwargs["reference_sha256"] = "0" * 64
    elif invalid == "symlink":
        alias = tmp_path / "alias.png"
        alias.symlink_to(kwargs["reference_path"])
        kwargs["reference_path"] = alias
    else:
        kwargs["output_dir"].mkdir()
    transport = FakeTransport()
    with pytest.raises(ViewRegenerationError, match="preparation failed"):
        regenerate_views(**kwargs, transport=transport)
    assert transport.calls == []


def test_landmark_profile_changes_only_prompt_with_same_reference_and_seeds(tmp_path):
    kwargs = arguments(tmp_path)
    baseline = FakeTransport()
    regenerate_views(**kwargs, transport=baseline)
    kwargs["output_dir"] = tmp_path / "landmark"
    candidate = FakeTransport()
    result = regenerate_views(**kwargs, transport=candidate, prompt_profile="landmark-v1")
    assert result["prompt_profile"] == "landmark-v1"
    assert len(result["diagnostic_contract_sha256"]) == 64
    assert len(candidate.calls) == 4
    for original, changed in zip(baseline.calls, candidate.calls, strict=True):
        a, b = original["request"], changed["request"]
        assert a.seed == b.seed and a.angle == b.angle
        assert a.reference_image == b.reference_image
        assert a.width == b.width and a.height == b.height
        assert a.prompt != b.prompt
        assert "same white ceramic mug" in b.prompt
        assert "Visual attribute data" not in b.prompt
    assert "right rear" in candidate.calls[0]["request"].prompt
    assert "hidden behind" in candidate.calls[1]["request"].prompt
    assert "toward the viewer" in candidate.calls[2]["request"].prompt
    assert "left rear" in candidate.calls[3]["request"].prompt


def test_identical_outputs_are_flagged_and_never_accepted_as_four_views(tmp_path):
    result = regenerate_views(**arguments(tmp_path), transport=FakeTransport())
    assert result["view_comparison"]["status"] == "similar_views_detected"
    pairs = result["view_comparison"]["pairs"]
    assert len(pairs) == 6
    assert all(pair["hamming_distance"] == 0 and pair["suspected_duplicate"] for pair in pairs)
    assert result["quality_status"] == "human_review_pending"


def test_unknown_prompt_profile_fails_before_transport(tmp_path):
    transport = FakeTransport()
    with pytest.raises(ViewRegenerationError, match="preparation failed"):
        regenerate_views(**arguments(tmp_path), transport=transport, prompt_profile="unknown")
    assert transport.calls == []


def test_landmark_transport_serializes_four_distinct_prompts_with_the_same_image(tmp_path):
    from email import policy
    from email.parser import BytesParser
    from unittest.mock import patch

    from src.search_v2.cloudflare_http import RequestsCloudflareTransport
    from test_search_v2_cloudflare_http import CapturingSession
    from test_search_v2_cloudflare_http import requests_response
    from test_cloudflare_live_e2e import response_for

    body = b"".join(response_for(png_bytes()).body_chunks)
    sessions = [
        CapturingSession(requests_response((body,), content_length=str(len(body)))[0])
        for _ in range(4)
    ]
    with patch("src.search_v2.cloudflare_http.requests.Session", side_effect=sessions):
        regenerate_views(
            **arguments(tmp_path),
            transport=RequestsCloudflareTransport(),
            prompt_profile="landmark-v1",
        )
    sent = []
    for session in sessions:
        request = session.prepared_request
        message = BytesParser(policy=policy.default).parsebytes(
            f"Content-Type: {request.headers['Content-Type']}\r\n\r\n".encode() + request.body
        )
        fields = {
            part.get_param("name", header="content-disposition"): part.get_payload(decode=True)
            for part in message.iter_parts()
        }
        assert set(fields) == {"prompt", "seed", "width", "height", "input_image_0"}
        assert fields["width"] == fields["height"] == b"512"
        sent.append(fields)
    assert len({item["prompt"] for item in sent}) == 4
    assert len({item["seed"] for item in sent}) == 4
    assert len({item["input_image_0"] for item in sent}) == 1
