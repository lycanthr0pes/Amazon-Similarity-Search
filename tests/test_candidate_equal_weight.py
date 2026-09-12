"""Equal title/image contributions and immutable legacy ranking history."""

import json
from types import SimpleNamespace

import pytest

import test_candidate_connected_flow as connected
from src.search_v2.candidate_completion import (
    IMAGE_WEIGHT,
    CandidateVisualProduct,
    CandidateVisualRanking,
    _history_profile_digest,
    _sort_key,
    _total,
    candidate_history_snapshot,
)


def test_image_and_title_have_equal_influence_and_missing_image_keeps_title():
    title = SimpleNamespace(lexical_score=1.0)
    image = SimpleNamespace(lexical_score=0.25)
    high_image = _total(image, SimpleNamespace(image_score=1.0), IMAGE_WEIGHT)
    high_title = _total(title, SimpleNamespace(image_score=0.0), IMAGE_WEIGHT)
    assert high_image == 0.625
    assert high_title == 0.5
    assert high_image > high_title
    assert _total(image, SimpleNamespace(image_score=None), IMAGE_WEIGHT) == 0.25
    assert _total(title, SimpleNamespace(image_score=0.0)) == 0.8


def test_equal_weight_history_and_legacy_json_remain_separate(tmp_path, monkeypatch):
    flow, _, _, history, _ = connected.start(tmp_path)
    connected.approve(flow)
    connected.fetch(flow, tmp_path)
    kwargs, _ = connected.clip(monkeypatch, tmp_path)
    result = flow.complete(owner_id=connected.OWNER, **kwargs)
    assert result.history.image_weight == 0.5
    assert result.ranking.image_weight == 0.5
    assert all(row.image_weight == 0.5 for row in result.ranking.products)
    assert (
        history.get(
            owner_id=connected.OWNER,
            locator=result.history.locator,
            now=connected.candidate.flow.NOW,
        )
        == result.history
    )

    legacy_json = json.loads(result.ranking.model_dump_json())
    legacy_json.pop("image_weight")
    legacy_json.pop("sort_profile_id")
    for row in legacy_json["products"]:
        row.pop("image_weight")
        row["total_score"] = (
            0.8 * row["candidate"]["lexical_score"] + 0.2 * row["image"]["image_score"]
        )
    legacy_json["products"] = [
        row.model_dump(mode="json")
        for row in sorted(
            [
                CandidateVisualProduct.model_validate_json(json.dumps(row))
                for row in legacy_json["products"]
            ],
            key=_sort_key,
        )
    ]
    legacy = CandidateVisualRanking.model_validate_json(json.dumps(legacy_json))
    assert json.loads(legacy.model_dump_json()) == legacy_json
    assert _history_profile_digest(legacy) != _history_profile_digest(result.ranking)
    pending = candidate_history_snapshot(
        legacy,
        flow._approved,
        source_text=flow._source,
        completed_at=connected.candidate.flow.NOW,
    )
    old = history.save(pending, now=connected.candidate.flow.NOW)
    assert old.locator != result.history.locator
    assert "image_weight" not in json.loads(old.model_dump_json())
    assert [row.total_score for row in old.products] == pytest.approx([0.88, 0.8, 0.92, 1.0])
    assert (
        history.get(owner_id=connected.OWNER, locator=old.locator, now=connected.candidate.flow.NOW)
        == old
    )

    with pytest.raises(ValueError, match="weight"):
        CandidateVisualRanking.model_validate(
            result.ranking.model_copy(update={"image_weight": None})
        )
    altered = json.loads(result.ranking.model_dump_json())
    altered["products"][1].pop("image_weight")
    with pytest.raises(ValueError, match="score does not match"):
        CandidateVisualRanking.model_validate_json(json.dumps(altered))
