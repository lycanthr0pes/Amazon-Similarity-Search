"""A model suggestion is not proof of the quantity's attribute identity."""

import pytest

from src.search_v2.bonsai_adapter import parse_bonsai_intent_response
from src.search_v2.dynamic_attributes import compile_search_registry
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_requirements import DEFAULT_ATTRIBUTE_REGISTRY
from test_bonsai_source_contract import condition
from test_search_v2_bonsai_compact import response_bytes


def inferred_intent(label="実効容量", quote="12qz以上"):
    payload = {
        "product_name_ja": "測定器",
        "typed_conditions": [
            condition(
                label,
                quote,
                {"value_type": "integer", "minimum": 12, "unit": "qz"},
                operator="at_least",
            )
        ],
    }
    return parse_bonsai_intent_response(
        source_input=f"測定器。{quote}。",
        prompt=b"abstention-fixture",
        response=response_bytes(payload),
    )


@pytest.mark.parametrize("label", ["実効容量", "公称容量", "最大圧力", "架空特性"])
def test_unsupported_identity_is_kept_for_review_but_never_ready(label):
    intent = inferred_intent(label)
    assert intent.typed_conditions[0].attribute_definition.label == label
    assert intent.has_blocking_ambiguity
    proposal = build_typed_requirement_proposal(intent)
    assert proposal.status == "blocking"
    assert not proposal.requirements


def test_removing_model_ambiguity_cannot_promote_old_inferred_candidate():
    intent = inferred_intent()
    intent.ambiguities.clear()
    proposal = build_typed_requirement_proposal(intent)
    assert proposal.status == "blocking"
    assert not proposal.requirements
    with pytest.raises(ValueError):
        compile_search_registry(intent.typed_conditions, DEFAULT_ATTRIBUTE_REGISTRY)


def test_existing_registry_cannot_certify_an_unverified_proposal():
    explicit = inferred_intent(quote="実効容量12qz以上")
    registry = build_typed_requirement_proposal(explicit).registry
    inferred = inferred_intent()
    inferred.ambiguities.clear()
    assert build_typed_requirement_proposal(inferred, registry=registry).status == "blocking"


def test_removing_ambiguity_cannot_make_a_search_query():
    from src.search_v2.query_planner import build_search_query_plan

    intent = inferred_intent()
    intent.ambiguities.clear()
    with pytest.raises(ValueError):
        build_search_query_plan(intent)


@pytest.mark.parametrize("label", ["実効容量", "公称容量", "最大圧力", "架空特性"])
def test_explicit_identity_still_progresses_without_a_category_dictionary(label):
    intent = inferred_intent(label, f"{label}12qz以上")
    assert not intent.has_blocking_ambiguity
    proposal = build_typed_requirement_proposal(intent)
    assert proposal.status == "ready"
    assert len(proposal.requirements) == 1


def test_name_only_wire_cannot_bypass_review_or_start_downstream_providers():
    import test_search_v2_orchestrator as fixtures

    m = fixtures.module()
    ledger, clock = fixtures.usage_ledger(), fixtures.SequenceClock()
    source = "測定器。12qz以上。"
    transport = fixtures.BonsaiTransport(
        fixtures.bonsai_response({"product_name_ja": "測定器", "attribute_names_ja": ["実効容量"]})
    )
    stage = m.start_intent_review(
        source,
        owner_id="owner-1",
        session_id="abstention-test",
        bonsai_config=fixtures.bonsai_config(),
        policy=fixtures.backend_policy(),
        usage_ledger=ledger,
        transport=transport,
        now=clock,
    )
    assert isinstance(stage, m.BlockingIntentReview)
    assert stage.session.query_plan_sha256 is None
    cloudflare = fixtures.CloudflareTransport(responses=[])
    with pytest.raises(m.SearchOrchestrationError):
        m.generate_images(
            stage,
            source_input=source,
            condition_set=fixtures.reference_conditions(),
            policy=fixtures.backend_policy(),
            usage_ledger=ledger,
            account_id=fixtures.ACCOUNT_ID,
            api_token=fixtures.CLOUDFLARE_TOKEN,
            transport=cloudflare,
            now=clock,
        )
    with pytest.raises(m.SearchOrchestrationError):
        m.skip_images(
            stage,
            postal_code="100-0001",
            policy=fixtures.backend_policy(),
            usage_ledger=ledger,
            now=clock,
        )
    assert not cloudflare.calls
    assert len(transport.calls) == 1
    assert [(r.provider, r.status) for r in ledger.snapshot().reservations] == [
        ("bonsai", "succeeded")
    ]
