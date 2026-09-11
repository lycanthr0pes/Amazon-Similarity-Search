"""Generation selects citations from the assessed product's supplied fields."""

import json

from jsonschema import Draft202012Validator
import pytest

from src.search_v2.candidate_diagnostics import candidate_failure_diagnostic
from src.search_v2.candidate_semantics import build_semantic_request, parse_semantic_response
from src.search_v2.observed_attributes import ProductField
from tools.bonsai_response_log import write_private


FIELDS = (
    ProductField(field_id="p3-title", product_index=3, kind="title", text="角😀"),
    ProductField(field_id="p3-features-0", product_index=3, kind="features", text="丸みのある形"),
    ProductField(field_id="p9-title", product_index=9, kind="title", text="別の商品"),
)


def request_schema(fields=FIELDS, indices=(3, 9)):
    request = json.loads(
        build_semantic_request("丸みのある商品", fields, (), {}, (), indices, compact=False)
    )
    schema = request["response_format"]["schema"]
    Draft202012Validator.check_schema(schema)
    return request, Draft202012Validator(schema)


def payload():
    return {
        "assessments": [
            {
                "product_index": 3,
                "score": 0.8,
                "evidence": [{"field_id": "p3-title", "start": 0, "end": 2}],
            },
            {"product_index": 9, "score": None, "evidence": []},
        ]
    }


def envelope(value):
    return json.dumps(
        {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(value)}}]}
    ).encode()


@pytest.mark.parametrize(
    "mutation",
    [
        "invented_id",
        "foreign_product",
        "renamed_id",
        "null_id",
        "long_end",
        "long_start",
        "utf8_offset",
        "unknown_with_quote",
        "score_without_quote",
    ],
)
def test_schema_rejects_unbound_citations(tmp_path, mutation):
    value = payload()
    row = value["assessments"][0]
    span = row["evidence"][0]
    if mutation == "invented_id":
        span["field_id"] = "invented-field"
    if mutation == "foreign_product":
        span["field_id"] = "p9-title"
    if mutation == "renamed_id":
        span["field_id"] = "p3-name"
    if mutation == "null_id":
        span["field_id"] = None
    if mutation == "long_end":
        span["end"] = 3
    if mutation == "long_start":
        span["start"] = 2
    if mutation == "utf8_offset":
        span["end"] = len(FIELDS[0].text.encode())
    if mutation == "unknown_with_quote":
        row["score"] = None
    if mutation == "score_without_quote":
        row["evidence"] = []
    request, validator = request_schema()
    write_private(tmp_path / "request.json", json.dumps(request).encode())
    write_private(tmp_path / "response.json", envelope(value))
    assert not validator.is_valid(value)
    with pytest.raises(ValueError):
        parse_semantic_response(FIELDS, envelope(value), (3, 9))


@pytest.mark.parametrize("field", FIELDS[:2])
def test_actual_fields_and_unicode_offsets_remain_usable(tmp_path, field):
    value = payload()
    value["assessments"][0]["evidence"] = [
        {"field_id": field.field_id, "start": 0, "end": len(field.text)}
    ]
    _, validator = request_schema()
    write_private(tmp_path / "response.json", envelope(value))
    assert validator.is_valid(value)
    result = parse_semantic_response(FIELDS, envelope(value), (3, 9))
    assert result[3].evidence[0].quote == field.text
    assert result[9].score is None


@pytest.mark.parametrize("text", [None, "", " \n\t"])
def test_product_without_quotable_text_can_only_abstain(text):
    fields = (
        ()
        if text is None
        else (ProductField(field_id="p7-title", product_index=7, kind="title", text=text),)
    )
    _, validator = request_schema(fields, (7,))
    value = {"assessments": [{"product_index": 7, "score": None, "evidence": []}]}
    assert validator.is_valid(value)
    value["assessments"][0]["score"] = 0.8
    assert not validator.is_valid(value)


def test_empty_product_batch_has_valid_empty_schema():
    _, validator = request_schema((), ())
    assert validator.is_valid({"assessments": []})
    assert not validator.is_valid(payload())


def test_schema_preserves_arbitrary_ids_without_inferring_names():
    fields = tuple(
        ProductField(field_id=f'opaque-{i}-"\\', product_index=i, kind="title", text="未知商品")
        for i in range(24)
    )
    indices = tuple(f.product_index for f in fields)
    request, validator = request_schema(fields, indices)
    value = {
        "assessments": [
            {
                "product_index": f.product_index,
                "score": 0.5,
                "evidence": [{"field_id": f.field_id, "start": 0, "end": len(f.text)}],
            }
            for f in fields
        ]
    }
    assert validator.is_valid(value)
    assert len(parse_semantic_response(fields, envelope(value), indices)) == 24
    value["assessments"][0]["evidence"][0]["field_id"] = fields[1].field_id
    assert not validator.is_valid(value)
    assert request["model"] == "Bonsai-8B.gguf" and request["temperature"] == 0.0


@pytest.mark.parametrize(
    "violation,code", [("reverse", "semantic_span_range"), ("duplicate", "semantic_span_duplicate")]
)
def test_parser_keeps_relational_checks(violation, code):
    value = payload()
    evidence = value["assessments"][0]["evidence"]
    if violation == "reverse":
        evidence[0].update(start=1, end=1)
    else:
        evidence *= 2
    with pytest.raises(ValueError) as caught:
        parse_semantic_response(FIELDS, envelope(value), (3, 9))
    assert candidate_failure_diagnostic(caught.value).code == code
