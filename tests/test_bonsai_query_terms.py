"""Query selection preserves conditions and original-first synonym scoring."""

from datetime import timedelta
import importlib
import json

import pytest

import test_candidate_search as candidate
import test_candidate_visual_conditions as visual
from tools.bonsai_response_log import write_private


SOURCE = "スキャナー。丸みのある形。光学解像度600dpi以上。10000円以下。"


def module():
    return importlib.import_module("src.search_v2.bonsai_query_terms")


def response(payload=None, finish="stop"):
    return json.dumps(
        {
            "choices": [
                {
                    "finish_reason": finish,
                    "message": {
                        "content": json.dumps(
                            payload
                            if payload is not None
                            else {
                                "original_en": "scanner",
                                "synonyms": [{"ja": "読取装置", "en": "scanner"}],
                            }
                        )
                    },
                }
            ]
        }
    ).encode()


class QueryBonsai:
    def __init__(self, root, raw=None):
        self.root, self.raw, self.calls = root, response() if raw is None else raw, []

    def evaluate(self, request):
        self.calls.append(request)
        write_private(self.root / "query-request.json", request)
        write_private(self.root / "query-response.json", self.raw)
        return self.raw


def start(root, raw=None):
    visual_bonsai = visual.VisualBonsai(root, [visual.draft("丸みのある形")])
    query_bonsai = QueryBonsai(root, raw)
    service = candidate.module().prepare_candidate_search(
        SOURCE,
        owner_id="owner-1",
        session_id="query-terms",
        postal_code="100-0001",
        normalization_profile=candidate.flow.backend_policy().normalization_profile,
        now=candidate.flow.NOW,
        visual_extractor=visual_bonsai,
        query_expander=query_bonsai,
    )
    return service, visual_bonsai, query_bonsai


def test_query_request_only_asks_for_bounded_term_lists():
    request = json.loads(module().build_query_terms_request(SOURCE, "スキャナー"))
    body = json.loads(request["messages"][1]["content"])
    assert body == {"source": SOURCE, "product_phrase": "スキャナー"}
    schema = request["response_format"]["schema"]
    assert set(schema["properties"]) == {"original_en", "synonyms"}
    assert schema["properties"]["synonyms"]["maxItems"] == 3
    assert schema["properties"]["original_en"]["anyOf"][0]["maxLength"] == 64
    assert request["temperature"] == 0.0 and request["stream"] is False
    assert "max_tokens" not in request


@pytest.mark.parametrize(
    "bad",
    [
        b"{}",
        b"not-json",
        response(finish="length"),
        response({"original_en": None, "synonyms": [], "score": 1}),
        response({"original_en": "scanner", "synonyms": [{"ja": "読取装置", "en": None}] * 4}),
        response({"original_en": "x" * 65, "synonyms": []}),
        response({"original_en": None, "synonyms": [{"ja": True, "en": None}]}),
        response({"original_en": "https://example.com", "synonyms": []}),
        response({"original_en": "scan\nitem", "synonyms": []}),
        response({"original_en": "スキャナー", "synonyms": []}),
        response({"original_en": None, "synonyms": [{"ja": "scanner", "en": None}]}),
        response({"original_en": "scanner 1200dpi", "synonyms": []}),
    ],
)
def test_invalid_suggestions_are_rejected(bad):
    with pytest.raises(ValueError):
        module().parse_query_terms_response("スキャナー", bad)


def test_normalization_deduplicates_without_changing_original_terms():
    value = module().parse_query_terms_response(
        "スキャナー",
        response(
            {
                "original_en": "Scanner",
                "synonyms": [
                    {"ja": "スキャナー", "en": "scanner"},
                    {"ja": "読取装置", "en": "Scanner"},
                    {"ja": "読取装置", "en": "scanner"},
                ],
            }
        ),
    )
    assert [(row.ja, row.en) for row in value.synonyms] == [("読取装置", "scanner")]
    assert value.original_en == "scanner"


def test_two_roles_do_not_rewrite_original_query_or_conditions(tmp_path):
    service, vision, query = start(tmp_path)
    plan = service.plan
    assert len(vision.calls) == len(query.calls) == 1
    assert plan.query_expansion.status == "ready"
    assert len(plan.query_options) == 3
    assert plan.request.queries[0].language == "ja"
    assert "スキャナー" in plan.request.queries[0].value
    assert plan.request.maximum_candidates == 24
    assert plan.selected_query_index == 0
    assert plan.query_expansion.terms.synonyms[0].ja == "読取装置"
    assert "scanner" not in plan.image_prompt
    assert plan.visual_conditions.conditions[0].source_phrase == "丸みのある形"


@pytest.mark.parametrize("index,language", [(1, "ja"), (2, "en")])
def test_selected_query_changes_retrieval_but_not_product_scoring(tmp_path, index, language):
    service, vision, query = start(tmp_path)
    old = service.plan_sha256
    service.select_search_query(
        owner_id="owner-1", plan_sha256=old, index=index, now=candidate.flow.NOW
    )
    assert service.plan_sha256 != old
    assert service.plan.selected_query_index == index
    assert len(service.plan.request.queries) == 1
    assert service.plan.request.queries[0].language == language
    assert service.plan.request.maximum_candidates == 24
    transport = candidate.ProductTransport(
        [
            {
                "name": "スキャナー",
                "features": ["光学解像度: 1200dpi"],
                "price": 9000,
                "currency": "JPY",
            },
            {
                "name": "読取装置",
                "features": ["光学解像度: 300dpi"],
                "price": 9000,
                "currency": "JPY",
            },
        ],
        tmp_path,
    )
    with pytest.raises(ValueError):
        service.approve_and_fetch(
            owner_id="owner-1", plan_sha256=old, transport=transport, now=candidate.flow.NOW
        )
    assert not transport.calls
    review = service.approve_and_fetch(
        owner_id="owner-1",
        plan_sha256=service.plan_sha256,
        transport=transport,
        now=candidate.flow.NOW,
    )
    service.confirm(
        owner_id="owner-1", review_sha256=review.sha256, selections={}, now=candidate.flow.NOW
    )
    result = service.rank(owner_id="owner-1", now=candidate.flow.NOW)
    assert [p.lexical_score for p in result.products] == [1.0, 0.25]
    assert [p.evaluation.required_status for p in result.products] == ["confirmed", "contradicted"]
    assert len(vision.calls) == len(query.calls) == 1
    with pytest.raises(ValueError):
        service.select_search_query(
            owner_id="owner-1", plan_sha256=service.plan_sha256, index=0, now=candidate.flow.NOW
        )


@pytest.mark.parametrize("change", ["owner", "digest", "expired", "bool", "negative", "outside"])
def test_selection_rejects_invalid_binding_without_changing_plan(tmp_path, change):
    service, _, query = start(tmp_path)
    old = service.plan_sha256
    with pytest.raises(ValueError):
        service.select_search_query(
            owner_id="other" if change == "owner" else "owner-1",
            plan_sha256="0" * 64 if change == "digest" else old,
            index={"bool": True, "negative": -1, "outside": 99}.get(change, 1),
            now=candidate.flow.NOW + timedelta(minutes=16)
            if change == "expired"
            else candidate.flow.NOW,
        )
    assert service.plan_sha256 == old and len(query.calls) == 1


def test_bad_expansion_keeps_original_query_without_retry(tmp_path):
    service, vision, query = start(tmp_path, b"private-invalid-response")
    assert service.plan.query_expansion.status == "unavailable"
    assert len(service.plan.query_options) == 1
    assert "スキャナー" in service.plan.request.queries[0].value
    assert "private-invalid-response" not in service.plan.model_dump_json()
    assert len(vision.calls) == len(query.calls) == 1
