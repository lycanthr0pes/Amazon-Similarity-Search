"""Candidate retrieval is distinct from intent confirmation and product ranking."""

from datetime import timedelta
import hashlib
import importlib
import json

import pytest

import test_search_v2_orchestrator as flow
from tools.bonsai_response_log import write_private


def module():
    return importlib.import_module("src.search_v2.candidate_search")


class ProductTransport:
    def __init__(self, products, root):
        self.products, self.root, self.calls = products, root, []

    def fetch(self, request):
        from src.search_v2.outscraper_contract import outscraper_request_sha256

        self.calls.append(request)
        response = {"data": [{**p, "query": request.queries[0].value} for p in self.products]}
        write_private(self.root / f"products-{len(self.calls)}.json", json.dumps(response).encode())
        return module().FetchedCandidates(
            outscraper_request_sha256(request), "fixture-task", response
        )


def start(tmp_path, source="スキャナー。600dpi以上。", name="スキャナー", inferred="印刷解像度"):
    class LoggedBonsai(flow.BonsaiTransport):
        def post_json(self, **kwargs):
            write_private(tmp_path / "bonsai-request.json", kwargs["body"])
            # Full fixture response is retained without printing source or product bodies.
            write_private(tmp_path / "bonsai-response.json", b"".join(self.response.body_chunks))
            return super().post_json(**kwargs)

    payload = {"product_name_ja": name, "attribute_names_ja": [inferred]}
    transport = LoggedBonsai(flow.bonsai_response(payload))
    clock, ledger = flow.SequenceClock(), flow.usage_ledger()
    stage = flow.module().start_intent_review(
        source,
        owner_id="owner-1",
        session_id="candidate-1",
        bonsai_config=flow.bonsai_config(),
        policy=flow.backend_policy(),
        usage_ledger=ledger,
        transport=transport,
        now=clock,
    )
    service = module().prepare_candidate_search(
        source,
        stage,
        postal_code="100-0001",
        normalization_profile=flow.backend_policy().normalization_profile,
        now=flow.NOW,
    )
    return service


def scanner_products():
    return [
        {
            "asin": "B000CA0001",
            "name": "スキャナーA",
            "features": ["光学解像度: 300dpi", "読取解像度: 1200dpi"],
        },
        {
            "asin": "B000CA0002",
            "name": "スキャナーB",
            "features": ["光学解像度: 600dpi", "読取解像度: 1200dpi"],
        },
        {"asin": "B000CA0003", "name": "スキャナーC", "features": ["読取解像度: 1200dpi"]},
    ]


def retrieve(service, tmp_path, products=None):
    transport = ProductTransport(scanner_products() if products is None else products, tmp_path)
    review = service.approve_and_fetch(
        owner_id="owner-1",
        plan_sha256=service.plan_sha256,
        transport=transport,
        now=flow.NOW + timedelta(seconds=1),
    )
    return review, transport


def test_natural_input_to_candidates_confirmation_and_evaluation(tmp_path):
    service = start(tmp_path)
    assert service.plan.request.queries[0].value == "スキャナー"
    assert service.plan.pending_quotes == ("600dpi以上",)
    assert "印刷解像度" not in service.plan.model_dump_json()
    with pytest.raises(ValueError):
        service.rank(owner_id="owner-1", now=flow.NOW)
    review, transport = retrieve(service, tmp_path)
    assert len(transport.calls) == 1
    assert review.unresolved == ("condition-001",)
    assert {o.label for o in review.options} == {"光学解像度", "読取解像度"}
    option = next(o for o in review.options if o.label == "光学解像度")
    service.confirm(
        owner_id="owner-1",
        review_sha256=review.sha256,
        selections={"condition-001": option.option_id},
        now=flow.NOW + timedelta(seconds=2),
    )
    ranked = service.rank(owner_id="owner-1", now=flow.NOW + timedelta(seconds=3))
    assert [p.product.asin for p in ranked.products] == ["B000CA0002", "B000CA0003", "B000CA0001"]
    assert [p.evaluation.required_status for p in ranked.products] == [
        "confirmed",
        "uncertain",
        "contradicted",
    ]
    write_private(tmp_path / "ranking.json", ranked.model_dump_json().encode())
    assert ranked.retrieval_plan_sha256 == service.plan_sha256
    assert ranked.review_sha256 == review.sha256
    assert all(
        p.product.provenance.query_plan_sha256 == ranked.product_batch.query_plan_sha256
        for p in ranked.products
    )


def test_single_or_frequent_attribute_is_not_proof_of_user_intent(tmp_path):
    service = start(tmp_path)
    review, _ = retrieve(
        service, tmp_path, [{"name": "スキャナー", "features": ["光学解像度: 1200dpi"]}]
    )
    assert len(review.options) == 1
    assert review.unresolved == ("condition-001",)
    with pytest.raises(ValueError):
        service.rank(owner_id="owner-1", now=flow.NOW)


@pytest.mark.parametrize("mutation", ["owner", "digest", "expired"])
def test_retrieval_checks_before_calling_provider(tmp_path, mutation):
    service = start(tmp_path)
    transport = ProductTransport(scanner_products(), tmp_path)
    with pytest.raises(ValueError):
        service.approve_and_fetch(
            owner_id="someone-else" if mutation == "owner" else "owner-1",
            plan_sha256="0" * 64 if mutation == "digest" else service.plan_sha256,
            transport=transport,
            now=flow.NOW + timedelta(minutes=16) if mutation == "expired" else flow.NOW,
        )
    assert not transport.calls


@pytest.mark.parametrize(
    "mutation", ["owner", "digest", "unknown_option", "missing", "extra", "expired"]
)
def test_confirmation_cannot_be_forged_or_partial(tmp_path, mutation):
    service = start(tmp_path)
    review, _ = retrieve(service, tmp_path)
    selections = {"condition-001": review.options[0].option_id}
    if mutation == "unknown_option":
        selections["condition-001"] = "unknown"
    if mutation == "missing":
        selections = {}
    if mutation == "extra":
        selections["condition-002"] = review.options[0].option_id
    with pytest.raises(ValueError):
        service.confirm(
            owner_id="elsewhere" if mutation == "owner" else "owner-1",
            review_sha256="0" * 64 if mutation == "digest" else review.sha256,
            selections=selections,
            now=flow.NOW + timedelta(minutes=16)
            if mutation == "expired"
            else flow.NOW + timedelta(seconds=2),
        )
    with pytest.raises(ValueError):
        service.rank(owner_id="owner-1", now=flow.NOW)


def test_retrieval_is_single_use_and_returned_plan_is_not_mutable_state(tmp_path):
    service = start(tmp_path)
    original = service.plan_sha256
    service.plan.query_plan.queries.clear()
    assert service.plan_sha256 == original
    _, transport = retrieve(service, tmp_path)
    with pytest.raises(ValueError):
        service.approve_and_fetch(
            owner_id="owner-1", plan_sha256=original, transport=transport, now=flow.NOW
        )
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    "features",
    [[], ["600dpi"], ["光学解像度: 不明"], ["光学解像度: 600〜1200dpi"], ["消費電力: 600W"]],
)
def test_missing_unlabelled_ranges_or_wrong_units_cannot_force_a_choice(tmp_path, features):
    service = start(tmp_path)
    review, _ = retrieve(service, tmp_path, [{"name": "スキャナー", "features": features}])
    assert not review.options
    with pytest.raises(ValueError):
        service.confirm(
            owner_id="owner-1", review_sha256=review.sha256, selections={}, now=flow.NOW
        )


def test_original_source_is_bound_to_the_review(tmp_path):
    service = start(tmp_path)
    assert (
        service.plan.source_sha256
        == hashlib.sha256("スキャナー。600dpi以上。".encode()).hexdigest()
    )


def direct_start(source="スキャナー。600dpi以上。"):
    return module().prepare_candidate_search(
        source,
        owner_id="owner-1",
        session_id="direct-1",
        postal_code="100-0001",
        normalization_profile=flow.backend_policy().normalization_profile,
        now=flow.NOW,
    )


def test_sudachi_queries_without_presearch_bonsai():
    service = direct_start("スキャナー。白。600dpi以上。")
    assert "スキャナー" in service.plan.request.queries[0].value
    assert "600" not in service.plan.image_prompt
    assert "白" in service.plan.image_prompt
    assert service.plan.pending_quotes == ("600dpi以上",)


def test_lexical_ranking_preserves_numeric_requirements(tmp_path):
    service = direct_start()
    review, _ = retrieve(service, tmp_path)
    option = next(o for o in review.options if o.label == "光学解像度")
    service.confirm(
        owner_id="owner-1",
        review_sha256=review.sha256,
        selections={"condition-001": option.option_id},
        now=flow.NOW,
    )
    result = service.rank(owner_id="owner-1", now=flow.NOW)
    assert [p.product.asin for p in result.products] == ["B000CA0002", "B000CA0003", "B000CA0001"]
    assert [p.lexical_score for p in result.products] == [1.0, 1.0, 1.0]
    write_private(tmp_path / "lexical-ranking.json", result.model_dump_json().encode())


def test_equal_lexical_matches_preserve_response_order(tmp_path):
    service = direct_start("スキャナー")
    review, _ = retrieve(service, tmp_path)
    service.confirm(owner_id="owner-1", review_sha256=review.sha256, selections={}, now=flow.NOW)
    result = service.rank(owner_id="owner-1", now=flow.NOW)
    assert [p.product.asin for p in result.products] == ["B000CA0001", "B000CA0002", "B000CA0003"]
    assert all(p.lexical_score == 1.0 for p in result.products)


@pytest.mark.parametrize(
    "source,features,expected",
    [
        ("測定器。12qz以上。", ["有効量: 15qz"], "confirmed"),
        ("測定器。有効量12qz以上。", ["有効量: 10qz"], "contradicted"),
        ("測定器。有効量12qz以下。", ["有効量: 10qz"], "confirmed"),
        ("測定器。有効量1.5qz以上。", ["有効量: 1.6qz"], "confirmed"),
        ("測定器。有効量12qz以上。", ["有効量: 15qz", "有効量: 8qz"], "uncertain"),
        ("測定器。有効量12qz以上。", ["別量: 15qz"], "uncertain"),
        ("ケース。奥行1cm以上。", ["奥行: 15mm"], "confirmed"),
    ],
)
def test_observed_attributes_without_category_dictionary(tmp_path, source, features, expected):
    service = direct_start(source)
    review, _ = retrieve(service, tmp_path, [{"name": "評価用商品", "features": features}])
    selections = {
        cid: next(o.option_id for o in review.options if cid in o.condition_ids)
        for cid in review.unresolved
    }
    service.confirm(
        owner_id="owner-1", review_sha256=review.sha256, selections=selections, now=flow.NOW
    )
    result = service.rank(owner_id="owner-1", now=flow.NOW)
    assert result.products[0].evaluation.required_status == expected


@pytest.mark.parametrize(
    "source",
    [
        "スキャナー。600dpi以上または1200dpi以下。",
        "スキャナー。軽くて速い。600dpi以上。",
        "スキャナー。白色。600dpi以上。",
    ],
)
def test_unsupported_source_relations_are_not_silently_dropped(source):
    with pytest.raises(ValueError):
        direct_start(source)


@pytest.mark.parametrize("strength", ["希望", "除外"])
def test_condition_strength_is_preserved(tmp_path, strength):
    service = direct_start("測定器。有効量12qz以上" + strength + "。")
    review, _ = retrieve(service, tmp_path, [{"name": "商品", "features": ["有効量: 15qz"]}])
    service.confirm(owner_id="owner-1", review_sha256=review.sha256, selections={}, now=flow.NOW)
    result = service.rank(owner_id="owner-1", now=flow.NOW)
    assert review.conditions[0]["strength"] == ("preferred" if strength == "希望" else "excluded")
    assert result.products[0].evaluation.required_status == (
        "confirmed" if strength == "希望" else "contradicted"
    )


def test_multiple_quantities_cannot_share_incompatible_attribute(tmp_path):
    service = direct_start("測定器。12qz以上。5w以下。")
    review, _ = retrieve(
        service, tmp_path, [{"name": "商品", "features": ["有効量: 15qz", "消費電力: 3w"]}]
    )
    selections = {
        cid: next(o.option_id for o in review.options if cid in o.condition_ids)
        for cid in review.unresolved
    }
    with pytest.raises(ValueError):
        service.confirm(
            owner_id="owner-1",
            review_sha256=review.sha256,
            selections={cid: selections["condition-001"] for cid in review.unresolved},
            now=flow.NOW,
        )
    service.confirm(
        owner_id="owner-1", review_sha256=review.sha256, selections=selections, now=flow.NOW
    )
    assert (
        service.rank(owner_id="owner-1", now=flow.NOW).products[0].evaluation.required_status
        == "confirmed"
    )


def test_explicit_budget_remains_a_required_condition(tmp_path):
    service = direct_start("スキャナー。1000円以下。")
    review, _ = retrieve(
        service,
        tmp_path,
        [
            {"name": "高額商品", "price": 2000, "currency": "JPY"},
            {"name": "予算内商品", "price": 900, "currency": "JPY"},
            {"name": "価格欠落商品"},
        ],
    )
    service.confirm(owner_id="owner-1", review_sha256=review.sha256, selections={}, now=flow.NOW)
    result = service.rank(owner_id="owner-1", now=flow.NOW)
    assert [p.product.provenance.response_index for p in result.products] == [1, 2, 0]
    assert [p.evaluation.required_status for p in result.products] == [
        "confirmed",
        "uncertain",
        "contradicted",
    ]


def test_truncated_product_fields_cannot_establish_an_attribute(tmp_path):
    service = direct_start()
    review, _ = retrieve(
        service,
        tmp_path,
        [{"name": "商品", "description": "解像度: 1200dpi。" + "長い説明" * 4000}],
    )
    assert not review.options


def test_invalid_provider_binding_is_not_retried(tmp_path):
    class WrongBinding(ProductTransport):
        def fetch(self, request):
            result = super().fetch(request)
            return module().FetchedCandidates("0" * 64, result.provider_request_id, result.response)

    service = direct_start()
    transport = WrongBinding(scanner_products(), tmp_path)
    for _ in range(2):
        with pytest.raises(ValueError):
            service.approve_and_fetch(
                owner_id="owner-1",
                plan_sha256=service.plan_sha256,
                transport=transport,
                now=flow.NOW,
            )
    assert len(transport.calls) == 1


def test_removed_bonsai_argument_rejects_before_call_or_state_change(tmp_path):
    class InvalidBonsai:
        calls = 0

        def evaluate(self, request):
            self.calls += 1
            response = b"{}"
            write_private(tmp_path / "invalid-response.json", response)
            return response

    service = direct_start("商品")
    review, _ = retrieve(service, tmp_path)
    service.confirm(owner_id="owner-1", review_sha256=review.sha256, selections={}, now=flow.NOW)
    bonsai = InvalidBonsai()
    with pytest.raises(TypeError):
        service.rank(owner_id="owner-1", now=flow.NOW, bonsai=bonsai)
    assert bonsai.calls == 0
    assert service.rank(owner_id="owner-1", now=flow.NOW).products
