from __future__ import annotations

from dataclasses import dataclass
import hashlib
from io import BytesIO
import math
from pathlib import Path

import pytest
from PIL import Image

from src.search_v2.image_proxy import ProxyImage
from src.search_v2.image_proxy import proxy_image_pixel_sha256
from src.search_v2.image_similarity import CLIP_IMAGE_RANKING_ENABLED
from src.search_v2.image_similarity import ClipEmbedding
from src.search_v2.image_similarity import compute_phash
from src.search_v2.image_similarity import deduplicate_image_hashes
from src.search_v2.image_similarity import run_pinned_clip_image_encoder
from src.search_v2.image_similarity_process import ProcessIsolatedClipImageEncoder


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_MODEL_ROOT = REPOSITORY_ROOT / "models" / "clip-vit-base-patch32-12b36594"
CASE2_IMAGE_ROOT = Path(__file__).resolve().parent / "img" / "case2"
CASE2_DATASET = (
    (
        "near/n1.png",
        "1cf895ee0197a51394f95722db74d1b3fe33f2f9fb0cda70ea46a362768f1894",
    ),
    (
        "near/n2.png",
        "5643ccc36566d14805ce3680776a0f4a1ca3621705b489474f970e82c0d03178",
    ),
    (
        "near/n3.png",
        "cee8981d6082b1a47c98b597db9f98257a7eefd101575d8277aeafe193650253",
    ),
    (
        "near/n4.png",
        "bd1473fd043eee51ed50bf1f24b0ae201a3cecbf1bfe0000175fc6bdff561aaf",
    ),
    (
        "far/f1.png",
        "8722324267583541fa1f9051be4f87f9b4061574f6bd9ce35f8308e12dc178e2",
    ),
    (
        "far/f2.png",
        "20f628a33a0d7a36981a318e5d3a241bd0b1fbabac747719764c21b7285e5b24",
    ),
    (
        "far/f3.png",
        "a426e080732d6a8b0d523ff5f570017bd0579e5f11d18b4bca8b4503c40b1f3d",
    ),
    (
        "far/f4.png",
        "d5b63168ab7b281a2b2df52bc39b4b4e93529a8bc156262f8f2c35951f2e4b0f",
    ),
    (
        "far/f5.png",
        "ecedc524046e11badc0a3bc7f219fcaa08d186a7891082659111e2202fdf932e",
    ),
    (
        "far/f6.png",
        "ac3e1d671b8322433991b10c2dec1a47f9b29f17c9526bda824f7caeb8a31ab5",
    ),
    (
        "far/f7.png",
        "b1bcd2bc0e0ddd53c3e2ce525c9b2b203cc58b28700f40a398c7ac47ed6d3c9e",
    ),
)
CASE2_NEAR_PATHS = tuple(f"near/n{index}.png" for index in range(1, 5))
CASE2_FAR_PATHS = tuple(f"far/f{index}.png" for index in range(1, 8))
CASE2_INDEPENDENT_REFERENCE_PATHS: tuple[str, ...] = ()
CASE2_REQUIRED_TERMS = ("筒状", "長い", "縦", "金属製", "収納")
CASE2_ADDITIONAL_TERMS = ("四角い", "黒い")
CASE2_VISUAL_TERMS = ("筒状", "長い", "縦", "収納", "四角い", "黒い")
CASE2_STRUCTURED_TERMS = ("金属製",)
CASE2_DIAGNOSTIC_TARGET_AUC = 0.80
CASE2_RECORDED_NEAR_SCORES = (
    0.888890913,
    0.891890487,
    0.823862919,
    0.895726854,
)
CASE2_RECORDED_FAR_SCORES = (
    0.867201862,
    0.878533911,
    0.882351665,
    0.874803784,
    0.867728421,
    0.888073814,
    0.920737904,
)


@dataclass(frozen=True, slots=True)
class Case2Candidate:
    path: str
    proximity: str
    visual_features: tuple[str, ...]
    structured_features: tuple[str, ...]
    expected_rank: int
    rating: float
    review_count: int


# The user supplied these labels and expected ranks in the local case2 workbook.
CASE2_CANDIDATES = (
    Case2Candidate(
        "near/n1.png",
        "near",
        ("筒状", "長い", "縦", "収納", "四角い", "黒い"),
        ("金属製",),
        1,
        4.3,
        383,
    ),
    Case2Candidate(
        "near/n2.png",
        "near",
        ("筒状", "長い", "縦", "収納", "黒い"),
        ("金属製",),
        2,
        4.5,
        1486,
    ),
    Case2Candidate(
        "near/n3.png",
        "near",
        ("筒状", "長い", "縦", "収納", "四角い", "黒い"),
        ("金属製",),
        1,
        4.3,
        383,
    ),
    Case2Candidate(
        "near/n4.png",
        "near",
        ("縦", "長い", "収納", "四角い", "黒い"),
        ("金属製",),
        3,
        4.3,
        317,
    ),
    Case2Candidate(
        "far/f1.png",
        "far",
        ("縦", "収納", "四角い"),
        (),
        8,
        4.2,
        1432,
    ),
    Case2Candidate(
        "far/f2.png",
        "far",
        ("縦", "収納", "四角い"),
        (),
        9,
        4.1,
        8,
    ),
    Case2Candidate(
        "far/f3.png",
        "far",
        ("長い", "収納", "四角い"),
        (),
        9,
        3.8,
        9,
    ),
    Case2Candidate(
        "far/f4.png",
        "far",
        ("縦", "長い", "収納", "四角い", "黒い"),
        ("金属製",),
        4,
        4.6,
        145,
    ),
    Case2Candidate(
        "far/f5.png",
        "far",
        ("筒状", "縦", "収納", "黒い"),
        ("金属製",),
        5,
        4.5,
        154,
    ),
    Case2Candidate(
        "far/f6.png",
        "far",
        ("筒状", "縦", "収納", "黒い"),
        (),
        6,
        3.4,
        56,
    ),
    Case2Candidate(
        "far/f7.png",
        "far",
        ("縦", "収納", "四角い", "黒い"),
        (),
        7,
        4.6,
        5,
    ),
)


def _load_case2_images() -> dict[str, ProxyImage]:
    assert CASE2_IMAGE_ROOT.is_dir() and not CASE2_IMAGE_ROOT.is_symlink()
    image_directories = tuple(CASE2_IMAGE_ROOT / name for name in ("far", "near"))
    entries = tuple(path for directory in image_directories for path in directory.rglob("*"))
    assert all(directory.is_dir() and not directory.is_symlink() for directory in image_directories)
    assert not any(path.is_symlink() for path in entries)
    expected_paths = tuple(path for path, _ in CASE2_DATASET)
    actual_paths = tuple(
        sorted(path.relative_to(CASE2_IMAGE_ROOT).as_posix() for path in entries if path.is_file())
    )
    assert actual_paths == tuple(sorted(expected_paths))

    images: dict[str, ProxyImage] = {}
    source_digests: set[str] = set()
    pixel_digests: set[str] = set()
    for relative_path, expected_sha256 in CASE2_DATASET:
        path = CASE2_IMAGE_ROOT / relative_path
        assert path.stat().st_nlink == 1
        source_bytes = path.read_bytes()
        source_sha256 = hashlib.sha256(source_bytes).hexdigest()
        assert source_sha256 == expected_sha256
        assert source_sha256 not in source_digests
        source_digests.add(source_sha256)
        with Image.open(BytesIO(source_bytes)) as decoded:
            assert decoded.format == "PNG"
            assert getattr(decoded, "n_frames", 1) == 1
            width, height = decoded.size
            assert 1 <= width <= 4096
            assert 1 <= height <= 4096
            rgb_bytes = decoded.convert("RGB").tobytes()
        pixel_sha256 = proxy_image_pixel_sha256(width, height, rgb_bytes)
        assert pixel_sha256 not in pixel_digests
        pixel_digests.add(pixel_sha256)
        images[relative_path] = ProxyImage(
            schema_version="2.0",
            source_url_sha256=hashlib.sha256(f"quality-case2:{relative_path}".encode()).hexdigest(),
            source_bytes_sha256=source_sha256,
            pixel_sha256=pixel_sha256,
            content_type="image/png",
            image_format="PNG",
            width=width,
            height=height,
            rgb_bytes=rgb_bytes,
        )
    return images


def _encode_in_fixed_batches(
    paths: tuple[str, ...],
    images: dict[str, ProxyImage],
) -> dict[str, ClipEmbedding]:
    encoder = ProcessIsolatedClipImageEncoder()
    encoded: list[ClipEmbedding] = []
    for start in range(0, len(paths), 4):
        encoded.extend(
            run_pinned_clip_image_encoder(
                tuple(images[path] for path in paths[start : start + 4]),
                asset_root=REPOSITORY_MODEL_ROOT,
                encoder=encoder,
            )
        )
    return dict(zip(paths, encoded, strict=True))


def _mapped_mean_cosine(
    reference_paths: tuple[str, ...],
    candidate_path: str,
    embeddings: dict[str, ClipEmbedding],
) -> float:
    cosines = tuple(
        max(
            -1.0,
            min(
                1.0,
                math.fsum(
                    left * right
                    for left, right in zip(
                        embeddings[reference_path].values,
                        embeddings[candidate_path].values,
                        strict=True,
                    )
                ),
            ),
        )
        for reference_path in reference_paths
    )
    return (math.fsum(cosines) / len(cosines) + 1.0) / 2.0


def _case2_cluster_scores(
    embeddings: dict[str, ClipEmbedding],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    near_scores = tuple(
        _mapped_mean_cosine(
            tuple(reference for reference in CASE2_NEAR_PATHS if reference != candidate),
            candidate,
            embeddings,
        )
        for candidate in CASE2_NEAR_PATHS
    )
    far_scores = tuple(
        _mapped_mean_cosine(CASE2_NEAR_PATHS, candidate, embeddings)
        for candidate in CASE2_FAR_PATHS
    )
    return near_scores, far_scores


def _pairwise_auc(near_scores: tuple[float, ...], far_scores: tuple[float, ...]) -> float:
    wins = sum(near > far for near in near_scores for far in far_scores)
    ties = sum(near == far for near in near_scores for far in far_scores)
    return (wins + ties * 0.5) / (len(near_scores) * len(far_scores))


def _expected_order_concordance(scores_by_path: dict[str, float]) -> tuple[int, int]:
    comparable = 0
    concordant = 0
    for index, left in enumerate(CASE2_CANDIDATES):
        for right in CASE2_CANDIDATES[index + 1 :]:
            if left.expected_rank == right.expected_rank:
                continue
            comparable += 1
            expected_left_higher = left.expected_rank < right.expected_rank
            actual_left_higher = scores_by_path[left.path] > scores_by_path[right.path]
            concordant += expected_left_higher == actual_left_higher
    return concordant, comparable


def test_case2_user_labels_cover_fixed_second_condition() -> None:
    paths = tuple(candidate.path for candidate in CASE2_CANDIDATES)
    visual_terms = frozenset(CASE2_VISUAL_TERMS)
    structured_terms = frozenset(CASE2_STRUCTURED_TERMS)

    assert CASE2_REQUIRED_TERMS == ("筒状", "長い", "縦", "金属製", "収納")
    assert CASE2_ADDITIONAL_TERMS == ("四角い", "黒い")
    assert paths == CASE2_NEAR_PATHS + CASE2_FAR_PATHS
    assert tuple(candidate.proximity for candidate in CASE2_CANDIDATES[:4]) == ("near",) * 4
    assert tuple(candidate.proximity for candidate in CASE2_CANDIDATES[4:]) == ("far",) * 7
    assert tuple(candidate.expected_rank for candidate in CASE2_CANDIDATES) == (
        1,
        2,
        1,
        3,
        8,
        9,
        9,
        4,
        5,
        6,
        7,
    )
    assert all(set(candidate.visual_features) <= visual_terms for candidate in CASE2_CANDIDATES)
    assert all(
        set(candidate.structured_features) <= structured_terms for candidate in CASE2_CANDIDATES
    )
    assert all(0.0 <= candidate.rating <= 5.0 for candidate in CASE2_CANDIDATES)
    assert all(candidate.review_count >= 0 for candidate in CASE2_CANDIDATES)
    assert CASE2_INDEPENDENT_REFERENCE_PATHS == ()


def test_case2_recorded_cluster_diagnostic_keeps_image_ranking_disabled() -> None:
    near_scores = CASE2_RECORDED_NEAR_SCORES
    far_scores = CASE2_RECORDED_FAR_SCORES
    paths = CASE2_NEAR_PATHS + CASE2_FAR_PATHS
    scores_by_path = dict(zip(paths, near_scores + far_scores, strict=True))
    auc = _pairwise_auc(near_scores, far_scores)
    concordant, comparable = _expected_order_concordance(scores_by_path)

    assert auc == pytest.approx(0.6428571428571429)
    assert (concordant, comparable) == (27, 53)
    assert concordant / comparable == pytest.approx(0.5094339622641509)
    assert auc < CASE2_DIAGNOSTIC_TARGET_AUC
    assert CLIP_IMAGE_RANKING_ENABLED is False


@pytest.mark.clip_runtime
def test_case2_images_are_fixed_unique_and_not_independent_references() -> None:
    images = _load_case2_images()

    assert tuple(images) == CASE2_NEAR_PATHS + CASE2_FAR_PATHS
    assert (
        deduplicate_image_hashes(
            tuple(compute_phash(image) for image in images.values())
        ).duplicates
        == ()
    )
    assert CASE2_INDEPENDENT_REFERENCE_PATHS == ()


@pytest.mark.clip_runtime
def test_case2_pinned_onnx_matches_recorded_cluster_diagnostic() -> None:
    images = _load_case2_images()
    paths = CASE2_NEAR_PATHS + CASE2_FAR_PATHS
    embeddings = _encode_in_fixed_batches(paths, images)
    near_scores, far_scores = _case2_cluster_scores(embeddings)
    scores_by_path = dict(zip(paths, near_scores + far_scores, strict=True))
    auc = _pairwise_auc(near_scores, far_scores)
    concordant, comparable = _expected_order_concordance(scores_by_path)

    print(
        "case2 self-excluded cluster diagnostic: "
        f"near={len(near_scores)} far={len(far_scores)} "
        f"pairwise_auc={auc:.9f} "
        f"expected_order_concordance={concordant}/{comparable}"
    )
    print("near_scores=" + ",".join(f"{score:.9f}" for score in near_scores))
    print("far_scores=" + ",".join(f"{score:.9f}" for score in far_scores))

    assert near_scores == pytest.approx(CASE2_RECORDED_NEAR_SCORES, abs=1e-8)
    assert far_scores == pytest.approx(CASE2_RECORDED_FAR_SCORES, abs=1e-8)
    assert auc == pytest.approx(0.6428571428571429)
    assert (concordant, comparable) == (27, 53)
    assert CLIP_IMAGE_RANKING_ENABLED is False
