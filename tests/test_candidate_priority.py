"""Final ordering follows user priorities rather than a weighted total."""

from types import SimpleNamespace
import json

import pytest

from src.search_v2 import candidate_completion as completion
import test_candidate_connected_flow as connected


def row(title=0.5, image=0.5, excluded=0.0, required=0.5, preferred=0.5, index=0):
    return SimpleNamespace(
        candidate=SimpleNamespace(
            lexical_score=title,
            text_score=SimpleNamespace(
                excluded_ratio=excluded, required_ratio=required, preferred_ratio=preferred
            ),
            evaluation=SimpleNamespace(required_status="contradicted"),
            product=SimpleNamespace(provenance=SimpleNamespace(response_index=index)),
        ),
        image=SimpleNamespace(image_score=image),
        total_score=0.5 * title + 0.5 * (image or 0.0),
    )


@pytest.mark.parametrize(
    "first,second",
    [
        (row(title=0.6, image=0.0, excluded=1.0), row(title=0.5, image=1.0)),
        (row(image=0.6, excluded=1.0, required=0.0), row(image=0.5, required=1.0)),
        (row(excluded=0.0, required=0.0), row(excluded=0.5, required=1.0)),
        (row(required=0.6, preferred=0.0), row(required=0.5, preferred=1.0)),
        (row(preferred=0.6, index=1), row(preferred=0.5, index=0)),
        (row(index=1), row(index=2)),
        (row(image=0.0, required=0.0), row(image=None, required=1.0)),
        (row(image=None, excluded=0.0), row(image=None, excluded=1.0)),
    ],
)
def test_each_priority_precedes_all_later_criteria(first, second):
    source = SimpleNamespace()
    assert completion._title_image_sort_key(first, source) < completion._title_image_sort_key(
        second, source
    )


def test_observed_exclusions_remain_available_for_legacy_source():
    source = SimpleNamespace(
        requirements=[
            SimpleNamespace(
                requirement_id="exclude-1", attribute_key="feature", strength="excluded"
            )
        ],
        registry=SimpleNamespace(
            definitions=[SimpleNamespace(attribute_key="feature", default_weight=1)]
        ),
    )
    first, second = row(), row()
    for product, state in ((first, "mismatch"), (second, "match")):
        product.candidate.text_score = None
        product.candidate.evaluation = SimpleNamespace(
            required_match_ratio=0.5,
            preferred_match_ratio=0.5,
            decisions=[SimpleNamespace(requirement_id="exclude-1", state=state)],
        )
    assert completion._title_image_sort_key(first, source) < completion._title_image_sort_key(
        second, source
    )


def test_priority_reaches_history_and_preserves_previous_equal_weight_order(tmp_path, monkeypatch):
    flow, _, _, history, _ = connected.start(tmp_path)
    connected.approve(flow)
    connected.fetch(flow, tmp_path)
    kwargs, _ = connected.clip(monkeypatch, tmp_path)
    result = flow.complete(owner_id=connected.OWNER, **kwargs)
    assert result.ranking.sort_profile_id == completion.SORT_PROFILE_ID
    assert result.history.sort_profile_id == completion.SORT_PROFILE_ID
    assert result.history.products[0].required_status == "confirmed"
    assert (
        completion.CandidateVisualRanking.model_validate_json(result.ranking.model_dump_json())
        == result.ranking
    )
    with pytest.raises(ValueError, match="ordering"):
        completion.CandidateVisualRanking.model_validate(
            result.ranking.model_copy(update={"sort_profile_id": None})
        )
    legacy = completion.CandidateVisualRanking.model_validate(
        result.ranking.model_copy(
            update={
                "sort_profile_id": None,
                "products": tuple(sorted(result.ranking.products, key=completion._sort_key)),
            }
        )
    )
    assert "sort_profile_id" not in json.loads(legacy.model_dump_json())
    assert legacy.image_weight == 0.5
    assert completion._history_profile_digest(legacy) != completion._history_profile_digest(
        result.ranking
    )
    pending = completion.candidate_history_snapshot(
        legacy, flow._approved, source_text=flow._source, completed_at=connected.candidate.flow.NOW
    )
    old = history.save(pending, now=connected.candidate.flow.NOW)
    assert old.locator != result.history.locator
    assert old.sort_profile_id is None
    assert [p.required_status for p in old.products] == [
        "confirmed",
        "confirmed",
        "uncertain",
        "contradicted",
    ]
    assert (
        history.get(owner_id=connected.OWNER, locator=old.locator, now=connected.candidate.flow.NOW)
        == old
    )
    assert (
        history.get(
            owner_id=connected.OWNER,
            locator=result.history.locator,
            now=connected.candidate.flow.NOW,
        )
        == result.history
    )
