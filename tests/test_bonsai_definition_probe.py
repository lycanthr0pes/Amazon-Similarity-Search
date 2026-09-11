"""Evaluation contracts for the isolated oracle-context Bonsai experiment."""

from dataclasses import replace
import json

import pytest

from tools.bonsai_definition_cases import DEFINITIONS, NEGATIVE_CASES, POSITIVE_CASES
from tools.bonsai_definition_probe import build_request, judge, summarize, trials


def envelope(value):
    return json.dumps(
        {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(value)}}]}
    ).encode()


def test_definition_ablation_only_removes_meanings():
    case = POSITIVE_CASES[1]
    names, mapping = build_request(case, "names")
    full, full_mapping = build_request(case, "definitions")
    assert mapping == full_mapping
    names, full = json.loads(names), json.loads(full)
    data = json.loads(full["messages"][1]["content"])
    for document in data["documents"]:
        document.pop("definition")
    full["messages"][1]["content"] = json.dumps(data, ensure_ascii=False)
    assert full == names


def test_blind_arm_removes_names_units_and_changes_ids_and_order():
    case = POSITIVE_CASES[0]
    full, full_mapping = build_request(case, "definitions")
    masked, mapping = build_request(case, "blind")
    documents = json.loads(json.loads(masked)["messages"][1]["content"])["documents"]
    assert all(set(d) == {"id", "definition"} for d in documents)
    assert not set(mapping) & set(full_mapping)
    full_docs = json.loads(json.loads(full)["messages"][1]["content"])["documents"]
    assert [mapping[d["id"]] for d in documents] != [full_mapping[d["id"]] for d in full_docs]


@pytest.mark.parametrize("case", (*POSITIVE_CASES, *NEGATIVE_CASES), ids=lambda c: c.case_id)
def test_expected_answer_does_not_change_request(case):
    request, mapping = build_request(case, "definitions")
    changed, changed_mapping = build_request(replace(case, expected="SECRET_ORACLE"), "definitions")
    assert request == changed and mapping == changed_mapping
    data = json.loads(request)
    assert "SECRET_ORACLE" not in request.decode()
    allowed = data["response_format"]["schema"]["properties"]["attribute_id"]["enum"]
    assert set(allowed) == {*mapping, "unresolved"}
    assert all(
        DEFINITIONS[key].key not in data["messages"][1]["content"] for key in case.candidates
    )


@pytest.mark.parametrize("mode", ("names", "definitions", "blind"))
def test_judge_uses_mapping_and_never_accepts_another_candidate(mode):
    case = POSITIVE_CASES[1]
    _, mapping = build_request(case, mode)
    for identifier, key in mapping.items():
        result = judge(envelope({"attribute_id": identifier}), case, mapping)
        assert result["format_valid"]
        assert result["passed"] == (key == case.expected)
    assert not judge(envelope({"attribute_id": "unresolved"}), case, mapping)["passed"]


@pytest.mark.parametrize("case", NEGATIVE_CASES, ids=lambda c: c.case_id)
def test_missing_and_ambiguous_require_abstention(case):
    _, mapping = build_request(case, "definitions")
    assert judge(envelope({"attribute_id": "unresolved"}), case, mapping)["passed"]
    assert all(
        not judge(envelope({"attribute_id": key}), case, mapping)["passed"] for key in mapping
    )


@pytest.mark.parametrize(
    "content",
    [
        '{"attribute_id":"unresolved","attribute_id":"unresolved"}',
        '{"attribute_id":"unresolved","extra":1}',
        '{"attribute_id":null}',
        '{"attribute_id":"not-a-document"}',
        '```json\n{"attribute_id":"unresolved"}\n```',
    ],
)
def test_malformed_answers_do_not_pass_even_for_negative_cases(content):
    case = NEGATIVE_CASES[0]
    _, mapping = build_request(case, "definitions")
    raw = json.dumps(
        {"choices": [{"finish_reason": "stop", "message": {"content": content}}]}
    ).encode()
    result = judge(raw, case, mapping)
    assert not result["format_valid"] and not result["passed"]


def test_incomplete_generation_is_failure():
    case = NEGATIVE_CASES[0]
    _, mapping = build_request(case, "definitions")
    raw = json.loads(envelope({"attribute_id": "unresolved"}))
    raw["choices"][0]["finish_reason"] = "length"
    assert not judge(json.dumps(raw).encode(), case, mapping)["passed"]


def test_trial_matrix_is_fixed_and_every_target_quote_is_in_source():
    matrix = trials()
    assert len(matrix) == 52
    assert len({(case.case_id, mode) for case, mode in matrix}) == 52
    for case, _ in matrix:
        assert case.target_quote in case.source
        assert len(case.candidates) == len(set(case.candidates)) == 3
        assert case.expected is None or case.expected in case.candidates


def test_unknown_mode_cannot_silently_change_experiment():
    with pytest.raises(ValueError):
        build_request(POSITIVE_CASES[0], "typo")


@pytest.mark.parametrize("failure", ["none", "wrong_selection", "missing_result"])
def test_quality_gate_counts_negative_failures_and_incomplete_runs(failure):
    results = [
        {
            "group": case.group,
            "mode": mode,
            "passed": True,
            "format_valid": True,
            "calls": 1,
            "seconds": 1,
        }
        for case, mode in trials()
    ]
    if failure == "wrong_selection":
        results[-1]["passed"] = False
    if failure == "missing_result":
        results.pop()
    summary = summarize(results)
    assert summary["gate_passed"] == (failure == "none")
    assert summary["calls"] == len(results)
