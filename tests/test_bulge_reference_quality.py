import json

import numpy as np
import pytest

import test_search_v2_counterfactual_cloudflare_request as requests
from src.search_v2.counterfactual_cloudflare_request import (
    build_counterfactual_cloudflare_request_set,
)
from src.search_v2.counterfactual_image import (
    VisualConditionDraft,
    VisualFocus,
    build_visual_condition_set,
)


def conditions(direction="higher"):
    return build_visual_condition_set(
        source_input="本体が膨らんだ白い商品",
        drafts=(
            VisualConditionDraft(
                source_phrase="本体が膨らんだ",
                strength="required",
                attribute_key=None,
                focus=VisualFocus(
                    kind="shape",
                    target="object body",
                    scope="part",
                    measure="side_bulge",
                    direction=direction,
                ),
            ),
            VisualConditionDraft(source_phrase="白い", strength="required", attribute_key="色"),
        ),
    )


@pytest.mark.parametrize("direction", ["higher", "lower"])
def test_only_negated_bulge_gets_opposite_silhouette(direction):
    bundle = build_counterfactual_cloudflare_request_set(
        intent=requests.normalized_intent(),
        condition_set=conditions(direction),
        preimage_plan_sha256=requests.PLAN_SHA256,
        desired_reference_png=requests.png_bytes(),
    )
    desired = "outward_bulge" if direction == "higher" else "straight_sides"
    negative = "straight_sides" if direction == "higher" else "outward_bulge"
    assert f'"silhouette":"{desired}"' in bundle.requests[0].prompt
    assert f'"silhouette":"{negative}"' in bundle.requests[1].prompt
    assert f'"silhouette":"{desired}"' in bundle.requests[2].prompt
    assert "Facets or texture alone" in bundle.requests[1].prompt
    assert bundle.requests[1].reference_image == bundle.requests[2].reference_image
    assert bundle.call_count == 3


def mask(amount=0):
    y, x = np.indices((256, 256))
    t = (y - 30) / 196
    width = 48 + amount * 4 * t * (1 - t)
    return (t >= 0) & (t <= 1) & (np.abs(x - 128) <= width)


def test_nominal_difference_is_not_enough_for_reference_adoption():
    from src.search_v2.bulge_reference_quality import assess_bulge_pair

    good = assess_bulge_pair(mask(32), mask(), direction="higher")
    same = assess_bulge_pair(mask(32), mask(32), direction="higher")
    wrong = assess_bulge_pair(mask(), mask(32), direction="higher")
    reverse = assess_bulge_pair(mask(), mask(32), direction="lower")
    assert good.status == reverse.status == "passed"
    assert good.minimum_gap >= 0.02
    assert same.status == "reference_too_close"
    assert wrong.status == "reference_direction_mismatch"
    with pytest.raises(ValueError):
        assess_bulge_pair(mask(), mask(32), direction="sideways")


def test_invalid_or_multiple_regions_cannot_pass():
    from src.search_v2.bulge_reference_quality import assess_bulge_pair

    empty = np.zeros((256, 256), dtype=bool)
    assert assess_bulge_pair(mask(32), empty, direction="higher").status == "region_unavailable"
    assert assess_bulge_pair(mask(32), None, direction="higher").status == "region_unavailable"
    two = empty.copy()
    two[20:220, 20:80] = two[20:220, 150:210] = True
    assert assess_bulge_pair(mask(32), two, direction="higher").status == "region_unavailable"


def test_report_is_numeric_and_immutable():
    from src.search_v2.bulge_reference_quality import assess_bulge_pair

    report = assess_bulge_pair(mask(32), mask(), direction="higher")
    data = json.loads(report.model_dump_json())
    assert "mask" not in data and "image" not in data
    with pytest.raises(ValueError):
        report.status = "region_unavailable"


def test_nominal_gap_above_threshold_with_unstable_variants_is_rejected():
    from src.search_v2.bulge_reference_quality import BulgeReferenceQuality

    report = BulgeReferenceQuality(
        direction="higher",
        positive_values=(0.04,) * 20 + (0.028,),
        negative_values=(0.01,) * 21,
    )
    assert report.positive_values[0] - report.negative_values[0] > report.threshold
    assert report.status == "reference_too_close"
    assert report.minimum_gap == pytest.approx(0.018)


@pytest.mark.parametrize("mode", ["valid", "wrong_binding", "raises"])
def test_reference_extractor_binding_and_failure_are_checked(monkeypatch, mode):
    import src.search_v2.bulge_reference_quality as quality
    import test_search_v2_production_search as production
    from src.search_v2.shape_similarity import RegionMask

    images = tuple(production.proxy_image(f"bulge-reference-{i}") for i in range(3))
    monkeypatch.setattr(quality, "_proxy_image", lambda artifact: artifact)

    class Regions:
        def extract(self, inputs, targets):
            if mode == "raises":
                raise RuntimeError("untrusted-extractor-error")
            return {
                (image.pixel_sha256, target): RegionMask.from_array(
                    "f" * 64 if mode == "wrong_binding" else image.pixel_sha256,
                    target,
                    mask(32 if i != 1 else 0),
                )
                for i, image in enumerate(inputs)
                for target in targets
            }

    reports = quality.assess_bulge_references(conditions(), images, Regions())
    assert len(reports) == 1
    assert reports[0][1].status == ("passed" if mode == "valid" else "extraction_failed")
    assert "untrusted" not in reports[0][1].model_dump_json()


def test_bulge_reference_without_measurement_cannot_issue_final_approval(tmp_path, monkeypatch):
    import test_candidate_connected_flow as connected
    import test_candidate_visual_conditions as visual

    original = visual.draft

    def draft(*args, **kwargs):
        return {
            **original(*args, **kwargs),
            "focus": {
                "kind": "shape",
                "target": "object body",
                "scope": "part",
                "measure": "side_bulge",
                "direction": "higher",
            },
        }

    monkeypatch.setattr(visual, "draft", draft)
    flow, images, ledger, _, _ = connected.start(tmp_path, image_score_mode="relative")
    reference = connected.reference(flow)
    with pytest.raises(ValueError, match="reference quality"):
        flow.approve_reference(
            owner_id=connected.OWNER, reference_sha256=reference.sha256, human_confirmed=True
        )
    assert len(images.calls) == 2
    assert all(r.status == "succeeded" for r in ledger.snapshot().reservations)
    assert flow.reference_quality[0][1].status == "extractor_unconfigured"
    assert flow._approval_review is None
