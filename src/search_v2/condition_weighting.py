"""Versioned source positions for condition aggregation; no inferred priorities."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.search_v2.tokenizer import _analyze_japanese_source


PROFILE = "source-order-linear-v1"
WeightingProfile = Literal["source-order-linear-v1"]


class ConditionWeighting(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    profile_id: WeightingProfile = PROFILE
    positions: tuple[tuple[str, Annotated[int, Field(ge=0, le=2000)]], ...] = Field(max_length=64)

    @model_validator(mode="after")
    def unique_positions(self):
        if len(dict(self.positions)) != len(self.positions):
            raise ValueError("Duplicate condition position")
        return self


def build_condition_weighting(source, conditions, visual_conditions):
    normalized = _analyze_japanese_source(source).text
    positions = []
    for condition in conditions:
        quote = _analyze_japanese_source(condition["source_quote"]).text
        start = normalized.find(quote)
        if start < 0:
            raise ValueError("Condition position is not in its source")
        positions.append((condition["condition_id"], start))
    if visual_conditions:
        positions.extend((c.condition_id, c.source_start) for c in visual_conditions.conditions)
    return ConditionWeighting(positions=tuple(sorted(positions)))


def condition_weights(rows, defaults, weighting):
    if weighting is None:
        return defaults
    positions = dict(weighting.positions)
    if any(r.requirement_id not in positions for r in rows):
        raise ValueError("Scored condition has no source position")
    weights = {}
    for strength in ("required", "preferred", "excluded"):
        selected = [r for r in rows if r.strength == strength]
        starts = sorted({positions[r.requirement_id] for r in selected})
        by_start = {start: len(starts) - index for index, start in enumerate(starts)}
        weights.update({r.requirement_id: by_start[positions[r.requirement_id]] for r in selected})
    return weights
