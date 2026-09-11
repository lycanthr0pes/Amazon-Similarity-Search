"""Select individual semantic regions without consulting desired shape references."""

import numpy as np
from scipy import ndimage


MAX_REGION_PROPOSALS = 256
MAX_SELECTED_REGIONS = 4


def region_score(mask, heat):
    mass = float(heat[mask].sum())
    area = int(mask.sum())
    if not area or mass <= area * 0.5:
        return 0.0
    # Soft Dice retains semantic coverage: a tiny confident fragment cannot
    # win merely because the rest of the target is less certain.
    return 2.0 * mass / (area + float(heat.sum()))


def _valid_masks(proposals, heat):
    if (
        type(proposals) is not tuple
        or len(proposals) > MAX_REGION_PROPOSALS
        or not isinstance(heat, np.ndarray)
        or heat.ndim != 2
        or not all(1 <= n <= 512 for n in heat.shape)
        or not np.isfinite(heat).all()
        or heat.min() < 0.0
        or heat.max() > 1.0
    ):
        raise ValueError("Invalid semantic region input")
    valid = []
    for mask in proposals:
        if not isinstance(mask, np.ndarray) or mask.dtype != np.bool_ or mask.shape != heat.shape:
            raise ValueError("Invalid region proposal")
        area = int(mask.sum())
        if not area or area == mask.size:
            continue
        labels, count = ndimage.label(mask)
        sizes = np.bincount(labels.ravel())[1:]
        # Disconnected substantial objects must not be treated as one silhouette.
        if count > 1 and sizes.max() < area * 0.95:
            continue
        valid.append(mask)
    return tuple(valid)


def choose_regions(proposals, heat):
    ranked = []
    for mask in _valid_masks(proposals, heat):
        score = region_score(mask, heat)
        if score > 0.0:
            ys, xs = np.nonzero(mask)
            ranked.append((score, int(mask.sum()), int(ys.min()), int(xs.min()), mask))
    return _select(ranked)


def choose_parts(proposals, heat):
    ranked = []
    for mask in _valid_masks(proposals, heat):
        # Within one object, penalize extensions not supported as the part.
        # Cross-object selection uses coverage (region_score) separately.
        score = float((heat[mask] * 2.0 - 1.0).sum() / np.sqrt(mask.sum()))
        if score > 0:
            ys, xs = np.nonzero(mask)
            ranked.append((score, int(mask.sum()), int(ys.min()), int(xs.min()), mask))
    return _select(ranked)


def choose_instances(proposals, heat):
    candidates = tuple(m for m in _valid_masks(proposals, heat) if region_score(m, heat) > 0)
    ranked = []
    for mask in candidates:
        area = int(mask.sum())
        if any(
            other.sum() > area * 1.2 and np.logical_and(mask, other).sum() / area >= 0.95
            for other in candidates
        ):
            continue
        # An object can contain a small target part. Resolve nested proposals
        # before ranking parts so a highly confident lid cannot replace a mug.
        score = float(np.maximum(heat[mask] * 2.0 - 1.0, 0.0).sum() / np.sqrt(area))
        ys, xs = np.nonzero(mask)
        ranked.append((score, area, int(ys.min()), int(xs.min()), mask))
    return _select(ranked)


def constrain_region(region, instance):
    return np.logical_and(region, instance)


def _select(ranked):
    ranked.sort(key=lambda row: (-row[0], -row[1], row[2], row[3]))
    selected = []
    for _, area, _, _, mask in ranked:
        if any(
            np.logical_and(mask, other).sum() / min(area, other.sum()) > 0.5 for other in selected
        ):
            continue
        selected.append(mask)
        if len(selected) == MAX_SELECTED_REGIONS:
            break
    return tuple(selected)


def region_box(mask, padding=0.08):
    ys, xs = np.nonzero(mask)
    if not len(xs):
        raise ValueError("Empty target region")
    pad = max(2, round(max(xs.max() - xs.min(), ys.max() - ys.min()) * padding))
    return (
        max(0, int(xs.min()) - pad),
        max(0, int(ys.min()) - pad),
        min(mask.shape[1], int(xs.max()) + pad + 1),
        min(mask.shape[0], int(ys.max()) + pad + 1),
    )


def region_points(heat):
    positive = heat >= 0.5
    if not positive.any():
        return None
    distance = ndimage.distance_transform_edt(positive)
    y, x = np.unravel_index(np.argmax(distance * heat), heat.shape)
    x0, y0, x1, y1 = region_box(positive, padding=0.0)
    points, labels = [[x, y]], [1]
    # Exclude exterior distractors, not low-confidence holes inside the target.
    outside = np.ones_like(positive)
    outside[y0:y1, x0:x1] = False
    for px, py in (
        (max(0, x0 - 1), y),
        (min(heat.shape[1] - 1, x1), y),
        (x, max(0, y0 - 1)),
        (x, min(heat.shape[0] - 1, y1)),
    ):
        if heat[py, px] < 0.25 and outside[py, px]:
            points.append([px, py])
            labels.append(0)
    return np.asarray(points, dtype=np.float32), np.asarray(labels, dtype=np.int32)
