"""Bilateral outline measurements for reference quality checks, not product scores."""

import numpy as np
from scipy.ndimage import gaussian_filter1d, label, rotate


def clean_mask(mask):
    if mask.dtype != bool or mask.ndim != 2 or max(mask.shape) > 512:
        raise ValueError("Expected a bounded boolean mask")
    if not mask.any() or mask[0].any() or mask[-1].any():
        return None
    if mask[:, 0].any() or mask[:, -1].any():
        return None
    components, count = label(mask, structure=np.ones((3, 3)))
    areas = np.bincount(components.ravel())[1:]
    if not count or areas.max() / areas.sum() < 0.995:
        return None
    return components == areas.argmax() + 1


def crop_sides(mask):
    ys, xs = np.nonzero(mask)
    cropped = mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    h, w = cropped.shape
    if min(h, w) < 8 or not cropped.any(axis=1).all():
        return None
    left = cropped.argmax(axis=1).astype(float)
    right = w - 1 - cropped[:, ::-1].argmax(axis=1).astype(float)
    return left, right


def measure(mask):
    cleaned = clean_mask(mask)
    if cleaned is None:
        return None
    sides = crop_sides(cleaned)
    if sides is None:
        return None
    left, right = sides
    y = np.arange(len(left))
    middle = (y >= 0.15 * y[-1]) & (y <= 0.85 * y[-1])
    slope = np.polyfit(y[middle], ((left + right) / 2)[middle], 1)[0]
    angle = float(np.degrees(np.arctan(slope)))
    if abs(angle) > 20:
        return None
    upright = rotate(cleaned, -angle, reshape=True, order=0, prefilter=False)
    sides = crop_sides(upright)
    if sides is None:
        return None
    left, right = sides
    positions = np.linspace(0.15, 0.85, 64)
    sampled = np.stack(
        [np.interp(positions * (len(left) - 1), np.arange(len(left)), s) for s in sides]
    )
    sampled = gaussian_filter1d(sampled, 2, axis=1, mode="nearest")
    width = float(np.median(sampled[1] - sampled[0]))
    if width <= 0:
        return None
    endpoint_x = (positions[:5].mean(), positions[-5:].mean())
    chords = []
    for side in sampled:
        endpoints = (np.median(side[:5]), np.median(side[-5:]))
        gradient = (endpoints[1] - endpoints[0]) / (endpoint_x[1] - endpoint_x[0])
        chords.append(endpoints[0] + gradient * (positions - endpoint_x[0]))
    outward = np.stack((chords[0] - sampled[0], sampled[1] - chords[1])) / width
    # A one-sided protrusion alone is not evidence of a bilateral body bulge.
    profile = np.maximum(np.minimum(outward[0], outward[1]), 0)
    mass = float(profile.sum())
    return {
        "mean": float(profile.mean()),
        "peak90": float(np.quantile(profile, 0.9)),
        "position": None if mass < 1e-9 else float(profile @ positions / mass),
        "extent": float(np.mean(profile > 0.01)),
        "left_mean": float(np.maximum(outward[0], 0).mean()),
        "right_mean": float(np.maximum(outward[1], 0).mean()),
        "tilt_degrees": angle,
        "removed_pixels": int(mask.sum() - cleaned.sum()),
        "profile": profile.tolist(),
    }
