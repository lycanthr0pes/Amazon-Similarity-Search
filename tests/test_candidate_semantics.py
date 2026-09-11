"""Untrusted Bonsai rankings can only cite the supplied product's source fields."""

import json

import pytest

from src.search_v2.candidate_semantics import build_semantic_request, parse_semantic_response
from src.search_v2.observed_attributes import (
    ProductField,
    discover_specifications,
    parse_extraction_response,
)
from tools.bonsai_response_log import write_private


FIELDS = (
    ProductField(field_id="p0-title", product_index=0, kind="title", text="合成商品"),
    ProductField(field_id="p1-title", product_index=1, kind="title", text="別の商品"),
)


def envelope(value):
    return json.dumps(
        {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(value)}}]}
    ).encode()


def assessment():
    return {
        "product_index": 0,
        "score": 0.8,
        "evidence": [{"field_id": "p0-title", "start": 0, "end": 4}],
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "foreign_product",
        "bool_index",
        "high",
        "nan",
        "bool_score",
        "no_evidence",
        "foreign_field",
        "offset",
        "bool_offset",
        "duplicate_span",
        "invented_fact",
        "unknown_with_evidence",
    ],
)
def test_rejects_incomplete_or_fabricated_model_evaluations(tmp_path, mutation):
    row = assessment()
    rows = [row]
    if mutation == "missing":
        rows = []
    if mutation == "duplicate":
        rows = [row, row]
    if mutation == "foreign_product":
        row["product_index"] = 2
    if mutation == "bool_index":
        row["product_index"] = False
    if mutation == "high":
        row["score"] = 1.1
    if mutation == "nan":
        row["score"] = float("nan")
    if mutation == "bool_score":
        row["score"] = True
    if mutation == "no_evidence":
        row["evidence"] = []
    if mutation == "foreign_field":
        row["evidence"][0]["field_id"] = "p1-title"
    if mutation == "offset":
        row["evidence"][0]["end"] = 100
    if mutation == "bool_offset":
        row["evidence"][0]["start"] = False
    if mutation == "duplicate_span":
        row["evidence"] *= 2
    if mutation == "invented_fact":
        row["fact"] = "作り出した値"
    if mutation == "unknown_with_evidence":
        row["score"] = None
    response = envelope({"assessments": rows})
    write_private(tmp_path / "response.json", response)
    with pytest.raises(ValueError, match="Invalid Bonsai semantic response"):
        parse_semantic_response(FIELDS, response, (0,))


def test_unknown_is_distinct_from_zero_and_requests_are_bounded(tmp_path):
    response = envelope({"assessments": [{"product_index": 0, "score": None, "evidence": []}]})
    write_private(tmp_path / "response.json", response)
    assert parse_semantic_response(FIELDS, response, (0,))[0].score is None
    large = (ProductField(field_id="p0-title", product_index=0, kind="title", text="字" * 9000),)
    with pytest.raises(ValueError):
        build_semantic_request("商品", large, (), {}, (), (0,))


@pytest.mark.parametrize(
    "text",
    [
        "600dpi",
        "解像度600〜1200dpi",
        "解像度 600 - 1200dpi",
        "解像度: 最大600dpi",
        "解像度: 600dpiではない",
        "解像度: 600dpi以上",
        "解像度: 不明",
    ],
)
def test_qualifiers_ranges_and_unlabelled_values_are_not_exact_facts(text):
    fields = (ProductField(field_id="p0-feature", product_index=0, kind="features", text=text),)
    assert not discover_specifications(fields)


def test_extraction_cannot_crop_a_qualifier_or_generate_a_value(tmp_path):
    field = ProductField(
        field_id="p0-feature", product_index=0, kind="features", text="解像度: 600dpiではない"
    )
    response = envelope(
        {"spans": [{"field_id": field.field_id, "start": 0, "end": len("解像度: 600dpi")}]}
    )
    write_private(tmp_path / "response.json", response)
    with pytest.raises(ValueError):
        parse_extraction_response((field,), response)
