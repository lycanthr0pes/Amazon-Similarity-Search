import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

import src.search_v2.typed_ranking as typed_ranking
from src.search_v2.intent import SearchIntentDraft
from src.search_v2.intent import build_intent_provenance
from src.search_v2.intent import normalize_search_intent
from src.search_v2.outscraper_request import build_outscraper_request
from src.search_v2.product_normalization import ProductNormalizationProfile
from src.search_v2.product_normalization import normalize_outscraper_products
from src.search_v2.query_planner import build_search_query_plan
from src.search_v2.ranking import rank_product_batch
from src.search_v2.ranking import ranked_product_batch_sha256
from src.search_v2.ranking import ranking_profile_sha256
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_ranking import TYPED_RANKING_PROFILE_V4
from src.search_v2.typed_ranking import TypedRankedProductBatch
from src.search_v2.typed_ranking import TypedRankingError
from src.search_v2.typed_ranking import TypedScoreBreakdown
from src.search_v2.typed_ranking import rank_typed_product_batch
from src.search_v2.typed_ranking import typed_ranked_product_batch_sha256
from src.search_v2.typed_ranking import typed_ranking_profile_sha256


def enum_condition(
    attribute_key: str,
    value: str,
    *,
    strength: str = "required",
) -> dict[str, object]:
    return {
        "attribute_key": attribute_key,
        "operator": "equals",
        "expected_value": {"value_type": "enum", "values": [value]},
        "strength": strength,
    }


def normalized_intent(
    typed_conditions: list[dict[str, object]] | None = None,
    **overrides: object,
):
    source_input = str(overrides.pop("source_input", "条件に合うマウスを探す"))
    payload: dict[str, object] = {
        "product_name_ja": "マウス",
        "product_name_en": "mouse",
        "category_ja": None,
        "category_en": None,
        "required_terms_ja": [],
        "required_terms_en": [],
        "preferred_terms_ja": [],
        "preferred_terms_en": [],
        "negative_terms_ja": [],
        "negative_terms_en": [],
        "color_ja": None,
        "color_en": None,
        "features_ja": [],
        "features_en": [],
        "brand": None,
        "model_number": None,
        "price": {
            "currency": "JPY",
            "mode": "none",
            "target_jpy": None,
            "min_jpy": None,
            "max_jpy": None,
            "source": "none",
            "confidence": None,
        },
        "typed_conditions": typed_conditions if typed_conditions is not None else [],
        "ambiguities": [],
    }
    payload.update(overrides)
    provenance = build_intent_provenance(
        source_input=source_input,
        prompt=b"typed-ranking-prompt-v1",
        schema=b'{"type":"object"}',
        response=b'{"typed_conditions":[]}',
    )
    return normalize_search_intent(
        source_input,
        SearchIntentDraft.model_validate(payload),
        provenance=provenance,
    )


def ranking_inputs(
    products: list[dict[str, object]],
    *,
    intent=None,
):
    selected_intent = intent or normalized_intent()
    query_plan = build_search_query_plan(selected_intent)
    request = build_outscraper_request(query_plan, postal_code="100-0001")
    response_data = products if len(query_plan.queries) == 1 else [products, []]
    product_batch = normalize_outscraper_products(
        {"data": response_data},
        request=request,
        provider_request_id="task_typed_ranking_v4",
        profile=ProductNormalizationProfile(
            schema_version="2.0",
            profile_id="observed-only-v2",
            usd_to_jpy_rate=160,
        ),
    )
    proposal = build_typed_requirement_proposal(selected_intent)
    return selected_intent, query_plan, product_batch, proposal


def ranked(products: list[dict[str, object]], *, intent=None):
    inputs = ranking_inputs(products, intent=intent)
    return rank_typed_product_batch(*inputs), inputs


def test_profile_is_v4_domain_separated_and_keeps_reviews_uniquely_lowest() -> None:
    profile = TYPED_RANKING_PROFILE_V4

    assert profile.schema_version == "4.0"
    assert profile.profile_id == "typed-ranking-v4"
    assert profile.source_ranking_profile_id == "ranking-v3"
    assert profile.title_weight == 0.35
    assert profile.typed_attributes_weight == 0.30
    assert profile.price_weight == 0.20
    assert profile.image_weight == 0.10
    assert profile.review_quality_weight == 0.05
    assert profile.review_quality_weight < min(
        profile.title_weight,
        profile.typed_attributes_weight,
        profile.price_weight,
        profile.image_weight,
    )
    assert profile.image_scoring_enabled is False
    assert typed_ranking_profile_sha256() == typed_ranking_profile_sha256(profile)
    assert len(typed_ranking_profile_sha256()) == 64
    assert typed_ranking_profile_sha256() != ranking_profile_sha256()


def test_required_state_precedes_v4_total_and_retains_every_candidate() -> None:
    intent = normalized_intent([enum_condition("form.shape", "round")])
    result, inputs = ranked(
        [
            {
                "name": "マウス",
                "asin": "B000TV4001",
                "features": ["Rectangular"],
                "rating": 5.0,
                "reviews": 1_000,
            },
            {"name": "マウス", "asin": "B000TV4002"},
            {
                "name": "マウス",
                "asin": "B000TV4003",
                "features": ["Round"],
                "rating": 3.0,
                "reviews": 1_000,
            },
        ],
        intent=intent,
    )
    old = rank_product_batch(*inputs[:3])

    assert [item.product.asin for item in old.products][0] == "B000TV4001"
    assert [item.product.asin for item in result.products] == [
        "B000TV4003",
        "B000TV4002",
        "B000TV4001",
    ]
    assert [item.evaluation.required_status for item in result.products] == [
        "confirmed",
        "uncertain",
        "contradicted",
    ]
    assert len(result.products) == 3


def test_unknown_typed_evidence_stays_in_the_fixed_denominator() -> None:
    intent = normalized_intent(
        [
            enum_condition("form.shape", "round"),
            enum_condition("appearance.color", "black", strength="preferred"),
        ]
    )
    result, _ = ranked(
        [
            {
                "name": "マウス",
                "asin": "B000TV4004",
                "features": ["Round"],
            }
        ],
        intent=intent,
    )
    breakdown = result.products[0].breakdown

    assert breakdown.typed_attributes.status == "available"
    assert breakdown.typed_attributes.reason == "scored"
    assert breakdown.typed_total_weight == 2
    assert breakdown.typed_satisfied_weight == 1
    assert breakdown.typed_attributes.score == 0.5
    assert breakdown.typed_attributes.effective_weight > 0.0


def test_excluded_mismatch_is_satisfied_but_excluded_match_is_contradicted() -> None:
    intent = normalized_intent([enum_condition("form.shape", "rectangular", strength="excluded")])
    result, _ = ranked(
        [
            {
                "name": "マウス",
                "asin": "B000TV4005",
                "features": ["Rectangular"],
            },
            {
                "name": "マウス",
                "asin": "B000TV4006",
                "features": ["Round"],
            },
        ],
        intent=intent,
    )

    accepted, rejected = result.products
    assert accepted.product.asin == "B000TV4006"
    assert accepted.evaluation.required_status == "confirmed"
    assert accepted.breakdown.typed_attributes.score == 1.0
    assert rejected.evaluation.required_status == "contradicted"
    assert rejected.breakdown.typed_attributes.score == 0.0


def test_preferred_ratio_precedes_review_driven_total() -> None:
    intent = normalized_intent([enum_condition("appearance.color", "black", strength="preferred")])
    result, _ = ranked(
        [
            {
                "name": "マウス",
                "asin": "B000TV4007",
                "color": "White",
                "rating": 5.0,
                "reviews": 1_000,
            },
            {
                "name": "マウス",
                "asin": "B000TV4008",
                "color": "Black",
                "rating": 3.0,
                "reviews": 1_000,
            },
        ],
        intent=intent,
    )

    assert [item.product.asin for item in result.products] == ["B000TV4008", "B000TV4007"]
    assert [item.evaluation.preferred_match_ratio for item in result.products] == [1.0, 0.0]


def test_free_text_attribute_score_is_not_carried_into_v4() -> None:
    intent = normalized_intent(
        required_terms_ja=["軽量"],
        required_terms_en=["lightweight"],
    )
    result, inputs = ranked(
        [
            {
                "name": "マウス",
                "asin": "B000TV4009",
                "features": ["重量級", "Heavy"],
            },
            {
                "name": "マウス",
                "asin": "B000TV4010",
                "features": ["軽量", "Lightweight"],
            },
        ],
        intent=intent,
    )
    old = rank_product_batch(*inputs[:3])

    assert [item.product.asin for item in old.products] == ["B000TV4010", "B000TV4009"]
    assert [item.product.asin for item in result.products] == ["B000TV4009", "B000TV4010"]
    assert all(item.breakdown.typed_attributes.status == "missing" for item in result.products)
    assert all(
        item.breakdown.typed_attributes.reason == "not_requested" for item in result.products
    )
    assert result.products[0].breakdown.total_score == result.products[1].breakdown.total_score


def test_v4_reuses_only_allowed_v3_components_and_negative_matches() -> None:
    intent = normalized_intent(
        [enum_condition("form.shape", "round")],
        negative_terms_ja=["中古"],
        negative_terms_en=["used"],
        price={
            "currency": "JPY",
            "mode": "max",
            "target_jpy": None,
            "min_jpy": None,
            "max_jpy": 50_000,
            "source": "explicit",
            "confidence": None,
        },
    )
    result, inputs = ranked(
        [
            {
                "name": "中古 マウス",
                "asin": "B000TV4020",
                "features": ["Round"],
                "price": 40_000,
                "currency": "JPY",
                "rating": 4.5,
                "reviews": 100,
            }
        ],
        intent=intent,
    )
    source = rank_product_batch(*inputs[:3]).products[0].breakdown
    breakdown = result.products[0].breakdown

    assert breakdown.title.score == source.title.score
    assert breakdown.price.score == source.price.score
    assert breakdown.review_quality.score == source.review_quality.score
    assert breakdown.image.status == source.image.status == "disabled"
    assert breakdown.negative_matches == source.negative_matches == ("中古",)
    assert breakdown.negative_penalty == source.negative_penalty == 0.2
    assert "attributes" not in TypedScoreBreakdown.model_fields
    assert "attribute_language" not in TypedScoreBreakdown.model_fields
    assert "matched_terms" not in TypedScoreBreakdown.model_fields
    assert "missing_terms" not in TypedScoreBreakdown.model_fields


def test_no_requirements_excludes_typed_component_and_preserves_stable_order() -> None:
    result, _ = ranked(
        [
            {"name": "マウス", "asin": "B000TV4011"},
            {"name": "マウス", "asin": "B000TV4012"},
        ]
    )

    assert [item.product.asin for item in result.products] == ["B000TV4011", "B000TV4012"]
    assert all(item.breakdown.typed_requirement_count == 0 for item in result.products)
    assert all(item.breakdown.typed_attributes.score is None for item in result.products)


def test_blocking_proposal_stops_before_source_ranking_or_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "SECRET-UNKNOWN-ATTRIBUTE"
    intent = normalized_intent([enum_condition(secret, "round")])
    inputs = ranking_inputs([{"name": "マウス", "asin": "B000TV4013"}], intent=intent)

    def must_not_run(*args, **kwargs):
        raise AssertionError("ranking work started")

    monkeypatch.setattr(typed_ranking, "rank_product_batch", must_not_run)
    monkeypatch.setattr(typed_ranking, "build_product_evidence", must_not_run)

    with pytest.raises(TypedRankingError, match="Typed ranking inputs") as captured:
        rank_typed_product_batch(*inputs)

    assert str(captured.value) == "Typed ranking inputs did not match the ranking contract"
    assert secret not in str(captured.value)


def test_result_binds_all_input_and_source_domains() -> None:
    result, inputs = ranked(
        [
            {
                "name": "Round Mouse",
                "asin": "B000TV4014",
                "features": ["Round"],
            }
        ],
        intent=normalized_intent([enum_condition("form.shape", "round")]),
    )
    source = rank_product_batch(*inputs[:3])

    assert result.schema_version == "4.0"
    assert result.ranking_profile_id == "typed-ranking-v4"
    assert result.source_ranking_profile_id == "ranking-v3"
    assert result.source_ranked_product_batch_sha256 == ranked_product_batch_sha256(source)
    assert result.typed_requirement_proposal_sha256
    assert result.registry_sha256 == result.proposal.registry_sha256
    assert result.requirement_set_sha256 == result.proposal.requirement_set_sha256
    assert len(typed_ranked_product_batch_sha256(result)) == 64


@pytest.mark.parametrize("target", ["intent", "query", "batch", "proposal", "profile"])
def test_public_boundary_rejects_tampered_inputs_with_one_fixed_error(target: str) -> None:
    inputs = list(
        ranking_inputs(
            [{"name": "マウス", "asin": "B000TV4015"}],
            intent=normalized_intent([enum_condition("form.shape", "round")]),
        )
    )
    if target == "intent":
        inputs[0] = inputs[0].model_copy(update={"product_name_ja": "改変"})
    elif target == "query":
        inputs[1] = inputs[1].model_copy(update={"intent_sha256": "f" * 64})
    elif target == "batch":
        inputs[2] = inputs[2].model_copy(update={"query_plan_sha256": "f" * 64})
    elif target == "proposal":
        inputs[3] = inputs[3].model_copy(update={"intent_sha256": "f" * 64})
    else:
        inputs.append(TYPED_RANKING_PROFILE_V4.model_copy(update={"title_weight": 0.34}))

    with pytest.raises(TypedRankingError) as captured:
        if target == "profile":
            rank_typed_product_batch(*inputs[:4], profile=inputs[4])
        else:
            rank_typed_product_batch(*inputs)

    assert str(captured.value) == "Typed ranking inputs did not match the ranking contract"


def test_batch_digest_rejects_tampered_product_evaluation_and_order() -> None:
    result, _ = ranked(
        [
            {
                "name": "Round Mouse",
                "asin": "B000TV4016",
                "features": ["Round"],
            },
            {
                "name": "Rectangular Mouse",
                "asin": "B000TV4017",
                "features": ["Rectangular"],
            },
        ],
        intent=normalized_intent([enum_condition("form.shape", "round")]),
    )
    first = result.products[0]
    changed_product = first.product.model_copy(update={"title": "Tampered Mouse"})
    tampered_product = first.model_copy(update={"product": changed_product})
    changed_evaluation = first.evaluation.model_copy(update={"required_status": "contradicted"})
    tampered_evaluation = first.model_copy(update={"evaluation": changed_evaluation})
    reversed_products = tuple(
        item.model_copy(update={"rank": rank})
        for rank, item in enumerate(reversed(result.products), start=1)
    )

    for products in (
        (tampered_product, *result.products[1:]),
        (tampered_evaluation, *result.products[1:]),
        reversed_products,
    ):
        with pytest.raises(TypedRankingError, match="Typed ranking inputs"):
            typed_ranked_product_batch_sha256(result.model_copy(update={"products": products}))


def test_v3_payload_cannot_be_read_as_typed_ranking_v4() -> None:
    inputs = ranking_inputs([{"name": "マウス", "asin": "B000TV4018"}])
    old = rank_product_batch(*inputs[:3])

    with pytest.raises(ValidationError):
        TypedRankedProductBatch.model_validate(old.model_dump(mode="python"))


def test_empty_batch_is_valid_and_deterministic() -> None:
    result, _ = ranked([])

    assert result.products == ()
    assert typed_ranked_product_batch_sha256(result) == typed_ranked_product_batch_sha256(result)


def test_repr_and_error_do_not_expose_product_text_candidate_text_or_url() -> None:
    secret = "SECRET-PRODUCT-TEXT"
    result, _ = ranked(
        [
            {
                "name": secret,
                "asin": "B000TV4019",
                "url": "https://www.amazon.co.jp/dp/B000TV4019?secret=do-not-show",
            }
        ]
    )

    rendered = repr(result)
    assert secret not in rendered
    assert "do-not-show" not in rendered


def test_module_has_no_provider_network_image_runtime_or_dynamic_import_boundary() -> None:
    module_path = Path(typed_ranking.__file__)
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.add(node.func.id)

    assert not any(
        name in {"openai", "requests", "httpx", "socket", "onnxruntime"}
        or name.startswith("openai.")
        or name.startswith("requests.")
        or name.startswith("httpx.")
        or name.startswith("socket.")
        or name.startswith("onnxruntime.")
        or name == "src.clients"
        or name.startswith("src.clients.")
        or name == "src.search_v2.image_similarity"
        or name.startswith("src.search_v2.image_similarity.")
        for name in imports
    )
    assert "__import__" not in calls
    assert "eval" not in calls
    assert "exec" not in calls
