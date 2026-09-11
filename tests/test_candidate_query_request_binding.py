"""A saved plan cannot claim one selection while sending another query."""

import json

import pytest

import test_bonsai_query_terms as terms
from src.search_v2.candidate_search import CandidatePlan


@pytest.mark.parametrize("field,value", [("value", "別の商品"), ("language", "en")])
def test_request_must_equal_selected_query(tmp_path, field, value):
    service, _, _ = terms.start(tmp_path)
    payload = json.loads(service.plan.model_dump_json())
    payload["request"]["queries"][0][field] = value
    with pytest.raises(ValueError):
        CandidatePlan.model_validate_json(json.dumps(payload))
