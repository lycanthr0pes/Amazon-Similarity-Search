from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import hashlib
import hmac
import json
import unicodedata

from pydantic import ValidationError

from src.search_v2.approval import search_approval_plan_sha256
from src.search_v2.history_repository import HistoryConditionSnapshot
from src.search_v2.history_repository import HistoryDetail
from src.search_v2.history_repository import HistoryProductView
from src.search_v2.history_repository import HistoryReferenceImageWrite
from src.search_v2.history_repository import SearchHistoryWrite
from src.search_v2.history_repository import SqliteSearchHistoryRepository
from src.search_v2.intent import MAX_SOURCE_INPUT_CODEPOINTS
from src.search_v2.intent import NormalizedSearchIntent
from src.search_v2.intent import PriceCondition
from src.search_v2.orchestrator import SearchReview
from src.search_v2.outscraper_request import outscraper_request_sha256
from src.search_v2.product_pipeline import ProductSearchPipelineResult
from src.search_v2.typed_intent_adapter import TypedRequirementProposal
from src.search_v2.typed_intent_adapter import typed_requirement_proposal_sha256
from src.search_v2.typed_ranking import TypedRankedProduct
from src.search_v2.typed_ranking import typed_ranking_profile_sha256
from src.search_v2.typed_requirements import DEFAULT_ATTRIBUTE_REGISTRY
from src.search_v2.typed_requirements import AttributeRegistry
from src.search_v2.typed_requirements import AttributeDefinition
from src.search_v2.typed_requirements import BooleanTarget
from src.search_v2.typed_requirements import DecimalTarget
from src.search_v2.typed_requirements import EnumTarget
from src.search_v2.typed_requirements import IntegerTarget
from src.search_v2.typed_requirements import SemanticTarget
from src.search_v2.typed_requirements import TextSetTarget
from src.search_v2.typed_requirements import TypedRequirement
from src.search_v2.typed_requirements import attribute_definition


_INVALID_INPUT_MESSAGE = "Completed search history inputs are invalid"
_COMPLETION_KEY_DOMAIN = b"amazon-explorer-search-history-completion-v2\x00"
_MAX_DISPLAY_SOURCE_CODEPOINTS = 2_000
_MAX_SUMMARY_CODEPOINTS = 200


class HistorySnapshotError(ValueError):
    """A fixed-message rejection before completed search history is saved."""


def _raise_invalid_input() -> None:
    raise HistorySnapshotError(_INVALID_INPUT_MESSAGE) from None


def _same_digest(left: object, right: object) -> bool:
    return type(left) is str and type(right) is str and hmac.compare_digest(left, right)


def _source_binding(source_text: object) -> tuple[str, str]:
    if (
        type(source_text) is not str
        or not source_text
        or len(source_text) > MAX_SOURCE_INPUT_CODEPOINTS
    ):
        _raise_invalid_input()
    normalized = unicodedata.normalize("NFKC", source_text)
    if any(
        unicodedata.category(character).startswith("C") and not character.isspace()
        for character in normalized
    ):
        _raise_invalid_input()
    display_text = " ".join(normalized.split())
    if not display_text or len(display_text) > _MAX_DISPLAY_SOURCE_CODEPOINTS:
        _raise_invalid_input()
    return hashlib.sha256(source_text.encode("utf-8")).hexdigest(), display_text


def _validated_context(
    source_text: object,
    review: object,
    result: object,
) -> tuple[str, str, SearchReview, ProductSearchPipelineResult]:
    try:
        if type(review) is not SearchReview or type(result) is not ProductSearchPipelineResult:
            _raise_invalid_input()
        validated_review = SearchReview.model_validate(review)
        validated_result = ProductSearchPipelineResult.model_validate(result)
        source_digest, display_source = _source_binding(source_text)
        session = validated_result.session
        approval = session.approval
        normalized = validated_result.normalized_batch
        ranked = validated_result.ranked_batch
        if (
            validated_result.outcome not in {"results", "empty"}
            or normalized is None
            or ranked is None
            or approval is None
            or approval.consumed_at is None
            or session.owner_id != validated_review.session.owner_id
            or session.session_id != validated_review.session.session_id
            or session.created_at != validated_review.session.created_at
            or session.updated_at < validated_review.session.updated_at
            or approval.issued_at < validated_review.session.updated_at
            or approval.consumed_at > session.updated_at
            or approval.expires_at != validated_review.plan.expires_at
            or session.image_mode != validated_review.session.image_mode
            or session.image_set_sha256 != validated_review.session.image_set_sha256
            or session.image_request_metadata_sha256
            != validated_review.session.image_request_metadata_sha256
            or session.usage_policy_sha256 != validated_review.session.usage_policy_sha256
            or not _same_digest(session.intent_sha256, validated_review.session.intent_sha256)
            or not _same_digest(
                session.query_plan_sha256,
                validated_review.session.query_plan_sha256,
            )
            or not _same_digest(
                approval.plan_sha256,
                search_approval_plan_sha256(validated_review.plan),
            )
            or not _same_digest(
                source_digest,
                validated_review.bonsai_request.source_input_sha256,
            )
            or not _same_digest(
                source_digest,
                validated_review.intent.provenance.source_input_sha256,
            )
            or not _same_digest(
                normalized.outscraper_request_sha256,
                outscraper_request_sha256(validated_review.request),
            )
            or normalized.maximum_candidates != validated_review.request.maximum_candidates
            or not _same_digest(
                normalized.query_plan_sha256,
                validated_review.session.query_plan_sha256,
            )
            or not _same_digest(ranked.intent_sha256, validated_review.session.intent_sha256)
            or not _same_digest(
                ranked.query_plan_sha256,
                validated_review.session.query_plan_sha256,
            )
            or ranked.proposal != validated_review.typed_proposal
            or not _same_digest(
                ranked.typed_requirement_proposal_sha256,
                typed_requirement_proposal_sha256(validated_review.typed_proposal),
            )
            or ranked.ranking_profile_id != validated_review.ranking_profile.profile_id
            or not _same_digest(
                ranked.ranking_profile_sha256,
                typed_ranking_profile_sha256(validated_review.ranking_profile),
            )
        ):
            _raise_invalid_input()

        normalized_by_index = {
            product.provenance.response_index: product for product in normalized.products
        }
        if len(normalized_by_index) != len(normalized.products) or any(
            normalized_by_index.get(item.product.provenance.response_index) != item.product
            for item in ranked.products
        ):
            _raise_invalid_input()
        return source_digest, display_source, validated_review, validated_result
    except HistorySnapshotError:
        raise
    except (TypeError, UnicodeError, ValidationError, ValueError):
        _raise_invalid_input()


def _shortest_display(values: tuple[str, ...], *, fallback: str) -> str:
    candidates = (*values, fallback)
    return min(
        enumerate(candidates),
        key=lambda item: (len(item[1]), item[0]),
    )[1]


def _registry_value(value: str, definition: AttributeDefinition) -> str:
    aliases = tuple(item.alias for item in definition.value_aliases if item.canonical == value)
    return _shortest_display(aliases, fallback=value)


def _unit(value: str, definition: AttributeDefinition) -> str:
    aliases = tuple(item.alias for item in definition.unit_aliases if item.canonical == value)
    return _shortest_display(aliases, fallback=value)


def _number(value: int | Decimal) -> str:
    if type(value) is int:
        return f"{value:,}"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _target_text(requirement: TypedRequirement, definition: AttributeDefinition) -> str:
    target = requirement.expected_value
    if type(target) is BooleanTarget:
        return "はい" if target.value else "いいえ"
    if type(target) is EnumTarget:
        values = " / ".join(_registry_value(value, definition) for value in target.values)
        return f"{values}のいずれか" if requirement.operator == "one_of" else values
    if type(target) in {IntegerTarget, DecimalTarget}:
        unit = _unit(target.unit, definition)
        if requirement.operator == "equals":
            assert target.minimum is not None
            return f"{_number(target.minimum)}{unit}"
        if requirement.operator == "at_least":
            assert target.minimum is not None
            return f"{_number(target.minimum)}{unit}以上"
        if requirement.operator == "at_most":
            assert target.maximum is not None
            return f"{_number(target.maximum)}{unit}以下"
        assert target.minimum is not None and target.maximum is not None
        return f"{_number(target.minimum)}{unit}〜{_number(target.maximum)}{unit}"
    if type(target) is TextSetTarget:
        values = " / ".join(target.values)
        if requirement.operator == "contains_all":
            return f"すべて含む: {values}"
        if requirement.operator == "one_of":
            return f"{values}のいずれか"
        if requirement.operator == "compatible_with":
            return f"互換: {values}"
        return values
    if type(target) is SemanticTarget:
        return _registry_value(target.label, definition)
    raise TypeError("unsupported typed history target")


def _requirement_text(
    requirement: TypedRequirement, registry: AttributeRegistry = DEFAULT_ATTRIBUTE_REGISTRY
) -> str:
    definition = attribute_definition(requirement.attribute_key, registry=registry)
    label = _shortest_display(definition.aliases, fallback=definition.attribute_key)
    strength = {
        "required": "必須",
        "preferred": "希望",
        "excluded": "避けたい",
    }[requirement.strength]
    return f"{strength}: {label}: {_target_text(requirement, definition)}"


def _condition_snapshot(
    intent: NormalizedSearchIntent,
    *,
    proposal: TypedRequirementProposal,
    display_source: str,
) -> HistoryConditionSnapshot:
    product_type = next(
        (
            value
            for value in (
                intent.product_name_ja,
                intent.product_name_en,
                intent.category_ja,
                intent.category_en,
            )
            if value is not None
        ),
        display_source,
    )
    product_type = product_type[:_MAX_SUMMARY_CODEPOINTS]
    return HistoryConditionSnapshot(
        schema_version="2.0",
        product_type=product_type,
        conditions=tuple(
            _requirement_text(item, proposal.registry) for item in proposal.requirements
        ),
        price_summary=_price_summary(intent.price),
    )


def _price_summary(price: PriceCondition) -> str | None:
    if price.mode == "none":
        return None
    if price.mode == "exact":
        assert price.target_jpy is not None
        text = f"{price.target_jpy:,}円前後"
    elif price.mode == "range":
        assert price.min_jpy is not None and price.max_jpy is not None
        text = f"{price.min_jpy:,}円〜{price.max_jpy:,}円"
    elif price.mode == "min":
        assert price.min_jpy is not None
        text = f"{price.min_jpy:,}円以上"
    else:
        assert price.max_jpy is not None
        text = f"{price.max_jpy:,}円以内"
    if price.source == "inferred":
        return f"AIが提案した目安: {text}"
    return text


def _match_summary(item: TypedRankedProduct, proposal: TypedRequirementProposal) -> str:
    if item.evaluation.required_status == "contradicted":
        return "必須条件に合わない点があります"
    if item.evaluation.required_status == "uncertain":
        return "必須条件の一部を確認できません"
    if any(requirement.strength == "required" for requirement in proposal.requirements):
        return "必須条件を確認できました"
    if any(decision.state == "match" for decision in item.evaluation.decisions):
        return "確認できた商品情報には、希望に合う点があります"
    return "取得できた商品情報で条件との近さを比較しました"


def _typed_points(
    item: TypedRankedProduct,
    proposal: TypedRequirementProposal,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    requirements = {item.requirement_id: item for item in proposal.requirements}
    matching: list[str] = []
    unverified: list[str] = []
    caution: list[str] = []

    for decision in item.evaluation.decisions:
        requirement = requirements[decision.requirement_id]
        text = _requirement_text(requirement, proposal.registry)
        if decision.state == "unknown":
            unverified.append(f"未確認: {text}")
        elif decision.state == "conflict":
            unverified.append(f"情報が矛盾: {text}")
        elif requirement.strength == "excluded":
            if decision.state == "match":
                caution.append(f"該当: {text}")
            else:
                matching.append(f"非該当: {text}")
        elif decision.state == "match":
            matching.append(f"一致: {text}")
        else:
            caution.append(f"不一致: {text}")

    caution.extend(f"避けたい語句に該当: {value}" for value in item.breakdown.negative_matches)
    return (
        tuple(dict.fromkeys(matching)),
        tuple(dict.fromkeys(unverified)),
        tuple(dict.fromkeys(caution)),
    )


def _product_snapshot(
    item: TypedRankedProduct,
    *,
    proposal: TypedRequirementProposal,
    image_mode: str,
) -> HistoryProductView:
    product = item.product
    matching, unverified, caution = _typed_points(item, proposal)
    image_note = (
        "参考画像は保存されていますが、商品の順位付けには使っていません"
        if image_mode == "on"
        else "画像を使わずに比較しました"
    )
    return HistoryProductView(
        schema_version="2.0",
        rank=item.rank,
        title=product.title,
        image_url=product.image_urls[0] if product.image_urls else None,
        price_jpy=product.price_jpy,
        description=product.description,
        product_url=product.product_url,
        required_status=item.evaluation.required_status,
        match_summary=_match_summary(item, proposal),
        matching_points=matching,
        unverified_points=unverified,
        caution_points=caution,
        image_comparison_note=image_note,
    )


def _reference_images(review: SearchReview) -> tuple[HistoryReferenceImageWrite, ...]:
    if review.image_review is None:
        return ()
    if review.image_review.schema_version == "4.0":
        image = review.image_review.reference_review.image
        return (
            HistoryReferenceImageWrite(
                schema_version="2.0",
                angle="front_three_quarter",
                content_type=image.content_type,
                sha256=image.sha256,
                byte_length=image.byte_length,
                width=image.width,
                height=image.height,
                body=image.body,
            ),
        )
    return tuple(
        HistoryReferenceImageWrite(
            schema_version="2.0",
            angle=image.angle,
            content_type=image.content_type,
            sha256=image.sha256,
            byte_length=image.byte_length,
            width=image.width,
            height=image.height,
            body=image.body,
        )
        for image in review.image_review.execution.images
    )


def _completion_key(
    *,
    source_digest: str,
    review: SearchReview,
    result: ProductSearchPipelineResult,
) -> str:
    payload = {
        "approval_plan_sha256": search_approval_plan_sha256(review.plan),
        "completed_at": result.session.updated_at.isoformat(timespec="microseconds"),
        "normalized_product_batch_sha256": result.session.normalized_product_batch_sha256,
        "outcome": result.outcome,
        "owner_id": result.session.owner_id,
        "ranked_product_batch_sha256": result.session.ranked_product_batch_sha256,
        "ranking_profile_id": result.ranked_batch.ranking_profile_id
        if result.ranked_batch is not None
        else None,
        "session_id": result.session.session_id,
        "source_input_sha256": source_digest,
        "typed_requirement_proposal_sha256": review.plan.typed_requirement_proposal_sha256,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(_COMPLETION_KEY_DOMAIN + canonical).hexdigest()


def build_history_snapshot(
    source_text: str,
    *,
    review: SearchReview,
    result: ProductSearchPipelineResult,
) -> SearchHistoryWrite:
    source_digest, display_source, validated_review, validated_result = _validated_context(
        source_text,
        review,
        result,
    )
    ranked = validated_result.ranked_batch
    if ranked is None:
        _raise_invalid_input()
    try:
        conditions = _condition_snapshot(
            validated_review.intent,
            proposal=validated_review.typed_proposal,
            display_source=display_source,
        )
        reference_images = _reference_images(validated_review)
        image_mode = "on" if reference_images else "off"
        return SearchHistoryWrite(
            schema_version=(
                "3.0"
                if validated_review.image_review is not None
                and validated_review.image_review.schema_version == "4.0"
                else "2.0"
            ),
            owner_id=validated_result.session.owner_id,
            completion_key=_completion_key(
                source_digest=source_digest,
                review=validated_review,
                result=validated_result,
            ),
            completed_at=validated_result.session.updated_at,
            summary=conditions.product_type[:_MAX_SUMMARY_CODEPOINTS],
            source_text=display_source,
            condition_snapshot=conditions,
            reference_image_mode=image_mode,
            reference_images=reference_images,
            ranking_profile_id=ranked.ranking_profile_id,
            candidate_limit=validated_review.request.maximum_candidates,
            outcome=validated_result.outcome,
            result_snapshot=tuple(
                _product_snapshot(
                    item,
                    proposal=validated_review.typed_proposal,
                    image_mode=image_mode,
                )
                for item in ranked.products
            ),
        )
    except HistorySnapshotError:
        raise
    except (TypeError, UnicodeError, ValidationError, ValueError):
        _raise_invalid_input()


def save_completed_history(
    source_text: str,
    *,
    review: SearchReview,
    result: ProductSearchPipelineResult,
    repository: SqliteSearchHistoryRepository,
    now: datetime,
) -> HistoryDetail:
    if type(repository) is not SqliteSearchHistoryRepository:
        _raise_invalid_input()
    pending = build_history_snapshot(source_text, review=review, result=result)
    return repository.save(pending, now=now)
