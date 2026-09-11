"""Definition selection needs independently observable, unique source binding."""

from copy import deepcopy
import json

import pytest

from tools.bonsai_definition_cases import NEGATIVE_CASES
from tools.bonsai_definition_probe import build_request
from test_bonsai_definition_probe import envelope


def resolve(context, body):
    from src.search_v2.attribute_resolution import resolve_definition_response

    return resolve_definition_response(context, body)


def context():
    return {
        "source_input": "測定器。実効容量12qz以上。",
        "target_quote": "実効容量12qz以上",
        "documents": [
            {"id": "d1", "name": "実効容量", "unit": "qz", "definition": "実効値としての容量。"},
            {"id": "d2", "name": "公称容量", "unit": "qz", "definition": "公称値としての容量。"},
        ],
    }


@pytest.mark.parametrize("case", NEGATIVE_CASES, ids=lambda c: c.case_id)
@pytest.mark.parametrize("mode", ["definitions", "blind"])
def test_any_model_choice_is_held_without_unique_source_evidence(case, mode):
    body, mapping = build_request(case, mode)
    data = json.loads(json.loads(body)["messages"][1]["content"])
    for selected in (*mapping, "unresolved"):
        decision = resolve(data, envelope({"attribute_id": selected}))
        assert decision.status == "unresolved"
        assert decision.resolved_attribute_id is None


def test_unique_explicit_binding_progresses_and_preserves_candidate_id():
    decision = resolve(context(), envelope({"attribute_id": "d1"}))
    assert decision.status == "resolved"
    assert decision.resolved_attribute_id == decision.proposed_attribute_id == "d1"


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_choice",
        "missing",
        "duplicate",
        "wrong_unit",
        "no_definition",
        "no_name",
        "no_quote",
        "unclear",
        "unresolved",
    ],
)
def test_incomplete_or_conflicting_evidence_does_not_resolve(mutation):
    data, selected = context(), "d1"
    if mutation == "wrong_choice":
        selected = "d2"
    elif mutation == "missing":
        data["documents"] = data["documents"][1:]
        selected = "d2"
    elif mutation == "duplicate":
        data["documents"].append(
            {**data["documents"][0], "id": "d3", "definition": "別の条件下での容量。"}
        )
    elif mutation == "wrong_unit":
        data["documents"][0]["unit"] = "kg"
    elif mutation == "no_definition":
        data["documents"][0].pop("definition")
    elif mutation == "no_name":
        data["documents"][0].pop("name")
    elif mutation == "no_quote":
        data["source_input"] = "別の測定器"
    elif mutation == "unclear":
        data["source_input"] = "測定器。12qz以上。"
        data["target_quote"] = "12qz以上"
    else:
        selected = "unresolved"
    decision = resolve(data, envelope({"attribute_id": selected}))
    assert decision.status == "unresolved"
    assert decision.resolved_attribute_id is None


def test_order_and_opaque_id_change_do_not_change_evidence_decision():
    data = context()
    data["documents"].reverse()
    data["documents"][1]["id"] = "renamed"
    assert resolve(data, envelope({"attribute_id": "renamed"})).resolved_attribute_id == "renamed"


@pytest.mark.parametrize(
    "body",
    [
        b"bad",
        envelope({"attribute_id": "absent"}),
        envelope({"attribute_id": "d1", "confidence": 1}),
        b'{"choices":[]}',
    ],
)
def test_invalid_responses_are_errors_not_successful_abstentions(body):
    decision = resolve(context(), body)
    assert decision.status == "invalid"
    assert decision.resolved_attribute_id is None


def test_duplicate_ids_or_unbound_extra_context_are_invalid():
    data = context()
    duplicate = deepcopy(data["documents"][0])
    data["documents"].append(duplicate)
    assert resolve(data, envelope({"attribute_id": "d1"})).status == "invalid"
    data = context()
    data["expected"] = "d1"
    assert resolve(data, envelope({"attribute_id": "d1"})).status == "invalid"


@pytest.mark.parametrize(
    "label,unit", [("起動遅延", "ms"), ("曲げ剛性", "qz"), ("公称電圧", "V"), ("測定範囲", "Pa")]
)
def test_other_explicit_attributes_do_not_need_predefined_categories(label, unit):
    quote = f"{label}12{unit}以上"
    data = {
        "source_input": f"品物。{quote}。",
        "target_quote": quote,
        "documents": [{"id": "x", "name": label, "unit": unit, "definition": label + "の仕様定義"}],
    }
    assert resolve(data, envelope({"attribute_id": "x"})).resolved_attribute_id == "x"
    data["source_input"] = f"品物。12{unit}以上。"
    data["target_quote"] = f"12{unit}以上"
    assert resolve(data, envelope({"attribute_id": "x"})).status == "unresolved"


@pytest.mark.parametrize(
    "content",
    ['{"attribute_id":"d1","attribute_id":"d2"}', '{"attribute_id":NaN}', '{"attribute_id":null}'],
)
def test_non_strict_json_never_resolves(content):
    body = json.loads(envelope({"attribute_id": "d1"}))
    body["choices"][0]["message"]["content"] = content
    assert resolve(context(), json.dumps(body).encode()).status == "invalid"


def test_truncated_generation_never_resolves():
    body = json.loads(envelope({"attribute_id": "d1"}))
    body["choices"][0]["finish_reason"] = "length"
    assert resolve(context(), json.dumps(body).encode()).status == "invalid"
