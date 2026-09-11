"""Source-owned retrieval and reference-image prompts; no LLM or inferred names."""

from dataclasses import dataclass
import hashlib
import json
import re

from src.search_v2.bonsai_adapter import BonsaiCompactSearchIntentDraft, _explicit_source_price
from src.search_v2.bonsai_visual_conditions import validate_visual_conditions
from src.search_v2.counterfactual_image import VisualConditionSet
from src.search_v2.lexical_structure import syntax_remainder, validate_structure
from src.search_v2.intent import (
    NormalizedSearchIntent,
    build_intent_provenance,
    normalize_search_intent,
)
from src.search_v2.query_planner import SearchQueryPlan, build_search_query_plan
from src.search_v2.source_constraints import _Fact, _common_facts, _source_facts
from src.search_v2.tokenizer import _analyze_japanese_source, tokenize_search_text
from src.search_v2.typed_requirements import DEFAULT_ATTRIBUTE_REGISTRY


@dataclass(frozen=True, repr=False)
class CandidateQueries:
    retrieval_intent: NormalizedSearchIntent
    query_plan: SearchQueryPlan
    facts: tuple[_Fact, ...]
    image_prompt: str


def build_candidate_queries(
    source: str, *, visual_conditions: VisualConditionSet | None = None, structure=None
) -> CandidateQueries:
    if type(source) is not str or not 0 < len(source) <= 2000:
        raise ValueError("Invalid candidate source")
    analyzed = _analyze_japanese_source(source)
    remaining_source = analyzed.text
    if visual_conditions is not None:
        visual_conditions = validate_visual_conditions(
            source, visual_conditions, structure=structure
        )
        for condition in reversed(
            sorted(visual_conditions.conditions, key=lambda c: c.source_start)
        ):
            remaining_source = (
                remaining_source[: condition.source_start]
                + " " * (condition.source_end - condition.source_start)
                + remaining_source[condition.source_end :]
            )
    if structure is not None:
        validate_structure(source, structure)
        fact_source = "。".join(span.text(remaining_source).strip() for span in structure.fragments)
    else:
        fact_source = remaining_source
    facts, uncertain = _source_facts(fact_source)
    if visual_conditions is not None:
        # Common color/material facts retain their deterministic typed evidence;
        # the LLM proposal only owns the additional visual interpretation.
        common, ambiguous = _common_facts(analyzed, facts)
        facts = (*facts, *(f for f in common if f not in facts))
        uncertain |= ambiguous
    if uncertain:
        raise ValueError("Source relations require clarification before candidate retrieval")
    remainder = remaining_source
    for fact in facts:
        remainder = remainder.replace(fact.quote, " ")
    remainder = re.sub(r"[0-9]+(?:\.[0-9]+)?\s*(?:万|千)?円(?:以上|以下|以内)?", " ", remainder)
    segments = [s.strip() for s in re.split(r"[。\n、]", remainder) if s.strip()]
    # Do not absorb unparsed second conditions into a product name.
    if structure is None and len(segments) != 1:
        raise ValueError("A product phrase and supported conditions are required")
    if structure is not None:
        phrase = syntax_remainder(
            source,
            structure,
            [f.quote for f in facts]
            + (
                [c.source_phrase for c in visual_conditions.conditions] if visual_conditions else []
            ),
        )
    else:
        phrase = segments[0]
    tokens = tokenize_search_text(phrase, language="ja")
    if not tokens:
        raise ValueError("Candidate retrieval needs product terms")
    product = " ".join(tokens)
    if len(product) > 100:
        raise ValueError("Candidate product phrase exceeds the query limit")
    conditions, terms, visuals = [], [], []
    for fact in facts:
        if fact.key == "custom" and fact.label is None:
            continue
        condition = {
            "attribute_key": fact.key,
            "operator": fact.operator,
            "strength": fact.strength,
            "expected_value": fact.target,
        }
        if fact.key == "custom":
            condition["attribute_definition"] = fact.definition()
        conditions.append(condition)
        if fact.strength == "required":
            terms.append(fact.quote)
        if fact.strength != "excluded" and any(
            d.attribute_key == fact.key and d.visual_prompt_allowed
            for d in DEFAULT_ATTRIBUTE_REGISTRY.definitions
        ):
            visuals.append(fact.quote)
    draft = BonsaiCompactSearchIntentDraft.model_validate(
        {"product_name_ja": product, "required_terms_ja": terms, "typed_conditions": conditions}
    ).to_search_intent_draft()
    price = _explicit_source_price(analyzed)
    if price is not None:
        draft.price = price
    response = json.dumps(draft.model_dump(mode="json"), ensure_ascii=False).encode()
    provenance = build_intent_provenance(
        source_input=source,
        prompt=b"sudachi-candidate-projection-v1",
        schema=b"source-facts-v1",
        response=response,
    )
    intent = normalize_search_intent(source, draft, provenance=provenance)
    image = "白い背景に置かれた商品の参考写真。商品: " + product
    if visuals:
        image += "。外観条件: " + "、".join(visuals)
    if visual_conditions is not None:
        image += "。確認対象の視覚条件: " + "、".join(
            c.source_phrase for c in visual_conditions.conditions
        )
    image += "。文字や性能値を描かない。"
    return CandidateQueries(intent, build_search_query_plan(intent), facts, image)


def candidate_source_sha256(source: str) -> str:
    return hashlib.sha256(source.encode()).hexdigest()
