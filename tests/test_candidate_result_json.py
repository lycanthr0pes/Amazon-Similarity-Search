"""Result JSON decodes Decimal targets without relaxing Python domain inputs."""

from decimal import Decimal
import json

import pytest
from pydantic import ValidationError

from src.search_v2.candidate_search import CandidateRanking
from src.search_v2.typed_requirements import DecimalTarget
from tools.bonsai_response_log import write_private
import test_candidate_search as candidate
from test_candidate_offline_flow import run_candidate_flow


@pytest.fixture(scope="module")
def ranking(tmp_path_factory):
    return run_candidate_flow(tmp_path_factory.mktemp("candidate-result-json"), False)


@pytest.mark.parametrize("encoding", ["str", "bytes", "bytearray"])
def test_result_json_roundtrip_preserves_values_digests_and_pending(ranking, encoding):
    wire = ranking.model_dump_json()
    if encoding != "str":
        wire = wire.encode() if encoding == "bytes" else bytearray(wire.encode())
    restored = CandidateRanking.model_validate_json(wire)
    assert restored == ranking
    assert restored.model_dump_json() == ranking.model_dump_json()
    assert restored.requirements[0].expected_value.minimum == Decimal(600)
    assert restored.requirements[0].expected_value.maximum is None
    assert restored.requirements[1].expected_value.minimum is None
    assert restored.requirements[1].expected_value.maximum == Decimal(10000)
    assert restored.visual_evaluation_status == "pending"


@pytest.mark.parametrize(
    "bad",
    [
        True,
        600,
        600.0,
        [],
        {},
        "NaN",
        "sNaN",
        "Infinity",
        "-Infinity",
        " 600 ",
        "6_00",
        "0x258",
        "",
        "01",
        "1e9999",
        "9" * 65,
        "1.0000001",
        "1000000000001",
        "-1000000000001",
    ],
)
def test_invalid_decimal_json_targets_are_rejected(ranking, tmp_path, bad):
    payload = json.loads(ranking.model_dump_json())
    payload["requirements"][0]["expected_value"]["minimum"] = bad
    wire = json.dumps(payload).encode()
    write_private(tmp_path / "invalid-result.json", wire)
    with pytest.raises(ValidationError):
        CandidateRanking.model_validate_json(wire)


@pytest.mark.parametrize(
    "mutation",
    ["missing_bound", "extra_target_field", "extra_requirement_field", "wrong_nondecimal_type"],
)
def test_json_decoder_preserves_other_strict_contracts(ranking, tmp_path, mutation):
    payload = json.loads(ranking.model_dump_json())
    requirement = payload["requirements"][0]
    target = requirement["expected_value"]
    if mutation == "missing_bound":
        del target["maximum"]
    if mutation == "extra_target_field":
        target["invented"] = True
    if mutation == "extra_requirement_field":
        requirement["invented"] = True
    if mutation == "wrong_nondecimal_type":
        target["value_type"] = "integer"
    wire = json.dumps(payload).encode()
    write_private(tmp_path / "invalid-result.json", wire)
    with pytest.raises(ValidationError):
        CandidateRanking.model_validate_json(wire)


@pytest.mark.parametrize("bad", ["600", 600, 600.0, True])
def test_python_domain_still_requires_decimal_instances(ranking, bad):
    payload = ranking.model_dump(mode="python")
    payload["requirements"][0]["expected_value"]["minimum"] = bad
    with pytest.raises(
        ValidationError, match="decimal target values must be finite Decimal instances"
    ):
        CandidateRanking.model_validate(payload)
    assert payload["requirements"][0]["expected_value"]["minimum"] == bad
    with pytest.raises(ValidationError):
        DecimalTarget.model_validate_json(
            '{"value_type":"decimal","minimum":"600","maximum":null,"unit":"dpi"}'
        )


@pytest.mark.parametrize(
    "source,features",
    [
        ("商品", []),
        ("商品。白。", []),
        ("測定器。有効量1.25qz以上。", ["有効量: 1.50qz"]),
        ("測定器。有効量0.000001qz以下。", ["有効量: 0.000001qz"]),
        ("測定器。有効量-1.25qz以上。", ["有効量: -1qz"]),
        ("マグ。白。食洗機対応。容量1.5l以上。", ["食洗機対応: 対応", "容量: 2l"]),
    ],
)
def test_fractional_negative_and_mixed_targets_roundtrip(tmp_path, source, features):
    service = candidate.direct_start(source)
    review, _ = candidate.retrieve(
        service, tmp_path, [{"name": "商品", "color": "白", "features": features}]
    )
    service.confirm(
        owner_id="owner-1", review_sha256=review.sha256, selections={}, now=candidate.flow.NOW
    )
    ranked = service.rank(owner_id="owner-1", now=candidate.flow.NOW)
    wire = ranked.model_dump_json().encode()
    write_private(tmp_path / "result.json", wire)
    restored = CandidateRanking.model_validate_json(wire)
    assert restored == ranked
    assert restored.model_dump_json().encode() == wire
