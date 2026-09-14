"""Visual text agreement precedes reference-image agreement, without averaging."""

from types import SimpleNamespace
import pytest
from src.search_v2 import candidate_completion as completion
from test_candidate_exclusion_priority import rated


@pytest.mark.parametrize(
    "text_a,text_b,image_a,image_b",
    [
        (0.8, 0.7, 0.0, 1.0),
        (0.0, None, 0.0, 1.0),
    ],
)
def test_visual_text_precedes_image_similarity(text_a, text_b, image_a, image_b):
    first, second = rated(image=image_a), rated(image=image_b)
    first.visual_text_score = text_a
    second.visual_text_score = text_b
    assert completion._priority_sort_key(first, SimpleNamespace()) < completion._priority_sort_key(
        second, SimpleNamespace()
    )
