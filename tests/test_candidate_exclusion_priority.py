"""Negative exclusions precede all positive criteria; reviews only break final ties."""

from types import SimpleNamespace

import pytest

from src.search_v2 import candidate_completion as completion
from src.search_v2.browser_history import history_product
import test_candidate_connected_flow as connected
from test_candidate_priority import row


def rated(*, rating=3.0, **kwargs):
    result = row(**kwargs)
    result.candidate.product.rating = rating
    return result


@pytest.mark.parametrize(
    "first,second",
    [
        (rated(excluded=0.0, title=0.0), rated(excluded=0.1, title=1.0)),
        (rated(title=0.6, required=0.0), rated(title=0.5, required=1.0)),
        (
            rated(required=0.6, preferred=0.0, image=0.0),
            rated(required=0.5, preferred=1.0, image=1.0),
        ),
        (rated(preferred=0.6, image=0.0), rated(preferred=0.5, image=1.0)),
        (rated(image=0.6, rating=0.0), rated(image=0.5, rating=5.0)),
        (rated(rating=4.5, index=1), rated(rating=4.0, index=0)),
        (rated(rating=0.0, index=1), rated(rating=None, index=0)),
        (rated(image=0.0, rating=None), rated(image=None, rating=5.0)),
        (rated(rating=None, index=0), rated(rating=None, index=1)),
    ],
)
def test_requested_priority(first, second):
    assert completion._priority_sort_key(first, SimpleNamespace()) < completion._priority_sort_key(
        second, SimpleNamespace()
    )


def test_profile_and_review_survive_completion_and_old_order(tmp_path, monkeypatch):
    flow, _, _, history, _ = connected.start(tmp_path)
    connected.approve(flow)
    products = connected.candidate.scanner_products()
    monkeypatch.setattr(
        connected.candidate,
        "scanner_products",
        lambda: [{**p, "rating": float(i + 3)} for i, p in enumerate(products)],
    )
    connected.fetch(flow, tmp_path)
    kwargs, _ = connected.clip(monkeypatch, tmp_path)
    result = flow.complete(owner_id=connected.OWNER, **kwargs)
    assert result.ranking.sort_profile_id == "excluded-title-conditions-image-review-v1"
    assert result.history.sort_profile_id == result.ranking.sort_profile_id
    assert (
        completion.CandidateVisualRanking.model_validate_json(result.ranking.model_dump_json())
        == result.ranking
    )
    assert any(p.review_rating is not None for p in result.history.products)
    with pytest.raises(ValueError, match="ordering"):
        completion.CandidateVisualRanking.model_validate(
            result.ranking.model_copy(update={"products": tuple(reversed(result.ranking.products))})
        )
    for product, ranked in zip(result.history.products, result.ranking.products, strict=True):
        assert product.review_rating == ranked.candidate.product.rating
        assert history_product(product)["reviewRating"] == ranked.candidate.product.rating
    previous = completion.CandidateVisualRanking.model_validate(
        result.ranking.model_copy(
            update={
                "sort_profile_id": "title-image-conditions-v1",
                "products": tuple(
                    sorted(
                        result.ranking.products,
                        key=lambda r: completion._title_image_sort_key(r, result.ranking.source),
                    )
                ),
            }
        )
    )
    assert (
        completion.CandidateVisualRanking.model_validate_json(previous.model_dump_json())
        == previous
    )
    assert completion._history_profile_digest(previous) != completion._history_profile_digest(
        result.ranking
    )
    saved = history.save(
        completion.candidate_history_snapshot(
            previous,
            flow._approved,
            source_text=flow._source,
            completed_at=connected.candidate.flow.NOW,
        ),
        now=connected.candidate.flow.NOW,
    )
    assert saved.sort_profile_id == "title-image-conditions-v1"
    assert (
        history.get(
            owner_id=connected.OWNER, locator=saved.locator, now=connected.candidate.flow.NOW
        )
        == saved
    )
