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
CASE3_IMAGE_ROOT = Path(__file__).resolve().parent / "img" / "case3"
CASE3_DATASET = (
    (
        "near/n1.png",
        "73bb267502b7f93ca8d3c71aebe2b372d3f0d85dba9131589f4fc30a730c98ba",
    ),
    (
        "near/n2.png",
        "ea0f901d42017e0d84a4ae42c0cc5d61d87b14f36c970846ee47260bd3ae5cb1",
    ),
    (
        "near/n3.png",
        "dcb7494cc4b6d7d00f8738a9b4e649f21dee270f54757e872e150a67fe74826a",
    ),
    (
        "near/n4.png",
        "3ab2afd6ecf285c3e76c42712058615c5ea9c8827c11f207b9251a7f7dd8ee6f",
    ),
    (
        "near/n5.png",
        "8f94790605166f08477aa36a08d73caef09be5b4e0ca1127393443b29e7dde79",
    ),
    (
        "near/n6.png",
        "3096e1fe67098f6e00ec1fc6a4cddd82cf3931588461e95f23deb2e7578f5aa2",
    ),
    (
        "near/n7.png",
        "f7f631abff42579cc5963540fedcea5ddf039cd46cb4cfc1837f45dc04c88a75",
    ),
    (
        "near/n8.png",
        "784a7386afc833c4121f16cafd3fed1d809e4f4cd623a74c46757ddbc21685f9",
    ),
    (
        "far/f1.png",
        "ce9ab4fb51c53165c758973addb40c18462eab76471d670a4985d9a5c000eb8c",
    ),
    (
        "far/f2.png",
        "71eb1b794a09a66c283697cce324e23d4191cd5378d2451e3774292f5e3cdb8c",
    ),
    (
        "far/f3.png",
        "e2ee61cd4c80ebe18b47efd1f74d5277eccc823dd2350a5f44062ab6955ac8c9",
    ),
    (
        "far/f4.png",
        "3a0d9ada565f165bff92ec9c0d8b5a7abcb995deca28b934d36ea5575aae708c",
    ),
    (
        "far/f5.png",
        "d5fbd65a201dc2873f9f62eab815dbdc92f91220274f942e7717741284cdee88",
    ),
    (
        "far/f6.png",
        "24f788e965aff66bfd7cc186de24831a5cf2257702b9d2a48f14b861785f32fd",
    ),
    (
        "far/f7.png",
        "280ffc5ca180a963f3fd80c941b1ad900dc13da684a0cb8888e68a38ae0751cc",
    ),
    (
        "far/f8.png",
        "9b3c1d0205fb6f683f4f7fbaafd747c6e7f96e031b3356bc0574c7acc34abe91",
    ),
    (
        "far/f9.png",
        "9cd5d50073cb153ee97dad358992fe646ca799dc5a1a4d3a719a1b5bdff8ea7e",
    ),
    (
        "far/f10.png",
        "a43f76406dfb072695ad15f08f8aad7ef09af1fbc6ac5b528dfd7f1d4eb2110a",
    ),
    (
        "far/f11.png",
        "50ba61c31811c01b79a5311da6a9fe1cb0759c9cbd270faf611b14346a9425e3",
    ),
    (
        "far/f12.png",
        "2a603b3058228587bf97e84a8af0dcdae297292f9024b544f3bc2cb17e5d4242",
    ),
)
CASE3_NEAR_PATHS = tuple(f"near/n{index}.png" for index in range(1, 9))
CASE3_FAR_PATHS = tuple(f"far/f{index}.png" for index in range(1, 13))
CASE3_INDEPENDENT_REFERENCE_PATHS: tuple[str, ...] = ()
CASE3_REQUIRED_TERMS = ("収納口2つ", "小型(卓上)", "縦", "収納")
CASE3_VISUAL_TERMS = ("収納口2つ", "縦", "収納")
CASE3_STRUCTURED_TERMS = ("小型(卓上)",)
CASE3_DIAGNOSTIC_TARGET_AUC = 0.80
CASE3_RECORDED_NEAR_SCORES = (
    0.861845264,
    0.876815378,
    0.861028791,
    0.855608228,
    0.861584181,
    0.836333164,
    0.871133567,
    0.846947121,
)
CASE3_RECORDED_FAR_SCORES = (
    0.882387325,
    0.879022222,
    0.835020564,
    0.863055455,
    0.863020730,
    0.845245016,
    0.831669874,
    0.866760791,
    0.876172105,
    0.837777276,
    0.853958982,
    0.867801849,
)


@dataclass(frozen=True, slots=True)
class Case3Candidate:
    path: str
    proximity: str
    visual_features: tuple[str, ...]
    structured_features: tuple[str, ...]
    expected_rank: int
    rating: float
    review_count: int


# The user supplied these labels and expected ranks in the local case3 workbook.
# The test intentionally does not load that workbook or copy its personal metadata.
CASE3_CANDIDATES = (
    Case3Candidate(
        "near/n1.png",
        "near",
        ("収納口2つ", "縦", "収納"),
        ("小型(卓上)",),
        1,
        4.2,
        6,
    ),
    Case3Candidate(
        "near/n2.png",
        "near",
        ("収納口2つ", "縦", "収納"),
        ("小型(卓上)",),
        2,
        4.5,
        2,
    ),
    Case3Candidate(
        "near/n3.png",
        "near",
        ("収納口2つ", "縦", "収納"),
        ("小型(卓上)",),
        1,
        5.0,
        2,
    ),
    Case3Candidate(
        "near/n4.png",
        "near",
        ("収納口2つ", "縦", "収納"),
        ("小型(卓上)",),
        3,
        4.4,
        12,
    ),
    Case3Candidate(
        "near/n5.png",
        "near",
        ("収納口2つ", "縦", "収納"),
        ("小型(卓上)",),
        4,
        0.0,
        0,
    ),
    Case3Candidate(
        "near/n6.png",
        "near",
        ("収納口2つ", "縦", "収納"),
        ("小型(卓上)",),
        3,
        0.0,
        0,
    ),
    Case3Candidate(
        "near/n7.png",
        "near",
        ("収納口2つ", "縦", "収納"),
        ("小型(卓上)",),
        1,
        4.2,
        19,
    ),
    Case3Candidate(
        "near/n8.png",
        "near",
        ("収納口2つ", "縦", "収納"),
        ("小型(卓上)",),
        1,
        0.0,
        0,
    ),
    Case3Candidate(
        "far/f1.png",
        "far",
        ("収納口2つ", "収納"),
        ("小型(卓上)",),
        9,
        3.9,
        28,
    ),
    Case3Candidate(
        "far/f2.png",
        "far",
        ("収納口2つ", "収納"),
        ("小型(卓上)",),
        9,
        5.0,
        1,
    ),
    Case3Candidate(
        "far/f3.png",
        "far",
        ("縦", "収納"),
        ("小型(卓上)",),
        5,
        4.2,
        137,
    ),
    Case3Candidate(
        "far/f4.png",
        "far",
        ("収納口2つ", "収納"),
        ("小型(卓上)",),
        10,
        3.0,
        9,
    ),
    Case3Candidate(
        "far/f5.png",
        "far",
        ("縦", "収納"),
        ("小型(卓上)",),
        5,
        4.4,
        60,
    ),
    Case3Candidate(
        "far/f6.png",
        "far",
        ("縦", "収納"),
        ("小型(卓上)",),
        6,
        3.0,
        1,
    ),
    Case3Candidate(
        "far/f7.png",
        "far",
        ("収納口2つ", "収納"),
        ("小型(卓上)",),
        9,
        4.5,
        2,
    ),
    Case3Candidate(
        "far/f8.png",
        "far",
        ("収納口2つ", "収納"),
        ("小型(卓上)",),
        9,
        4.3,
        39,
    ),
    Case3Candidate(
        "far/f9.png",
        "far",
        ("縦", "収納"),
        ("小型(卓上)",),
        6,
        4.3,
        6,
    ),
    Case3Candidate(
        "far/f10.png",
        "far",
        ("縦", "収納"),
        ("小型(卓上)",),
        7,
        4.3,
        666,
    ),
    Case3Candidate(
        "far/f11.png",
        "far",
        ("収納口2つ", "収納"),
        ("小型(卓上)",),
        8,
        4.4,
        167,
    ),
    Case3Candidate(
        "far/f12.png",
        "far",
        ("縦", "収納"),
        ("小型(卓上)",),
        5,
        5.0,
        1,
    ),
)


def _load_case3_images() -> dict[str, ProxyImage]:
    assert CASE3_IMAGE_ROOT.is_dir() and not CASE3_IMAGE_ROOT.is_symlink()
    image_directories = tuple(CASE3_IMAGE_ROOT / name for name in ("far", "near"))
    entries = tuple(path for directory in image_directories for path in directory.rglob("*"))
    assert all(directory.is_dir() and not directory.is_symlink() for directory in image_directories)
    assert not any(path.is_symlink() for path in entries)
    expected_paths = tuple(path for path, _ in CASE3_DATASET)
    actual_paths = tuple(
        sorted(path.relative_to(CASE3_IMAGE_ROOT).as_posix() for path in entries if path.is_file())
    )
    assert actual_paths == tuple(sorted(expected_paths))

    images: dict[str, ProxyImage] = {}
    source_digests: set[str] = set()
    pixel_digests: set[str] = set()
    for relative_path, expected_sha256 in CASE3_DATASET:
        path = CASE3_IMAGE_ROOT / relative_path
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
            source_url_sha256=hashlib.sha256(f"quality-case3:{relative_path}".encode()).hexdigest(),
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


def _case3_cluster_scores(
    embeddings: dict[str, ClipEmbedding],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    near_scores = tuple(
        _mapped_mean_cosine(
            tuple(reference for reference in CASE3_NEAR_PATHS if reference != candidate),
            candidate,
            embeddings,
        )
        for candidate in CASE3_NEAR_PATHS
    )
    far_scores = tuple(
        _mapped_mean_cosine(CASE3_NEAR_PATHS, candidate, embeddings)
        for candidate in CASE3_FAR_PATHS
    )
    return near_scores, far_scores


def _pairwise_auc(near_scores: tuple[float, ...], far_scores: tuple[float, ...]) -> float:
    wins = sum(near > far for near in near_scores for far in far_scores)
    ties = sum(near == far for near in near_scores for far in far_scores)
    return (wins + ties * 0.5) / (len(near_scores) * len(far_scores))


def _expected_order_concordance(scores_by_path: dict[str, float]) -> tuple[int, int]:
    comparable = 0
    concordant = 0
    for index, left in enumerate(CASE3_CANDIDATES):
        for right in CASE3_CANDIDATES[index + 1 :]:
            if left.expected_rank == right.expected_rank:
                continue
            comparable += 1
            expected_left_higher = left.expected_rank < right.expected_rank
            actual_left_higher = scores_by_path[left.path] > scores_by_path[right.path]
            concordant += expected_left_higher == actual_left_higher
    return concordant, comparable


def test_case3_user_labels_cover_fixed_third_condition() -> None:
    paths = tuple(candidate.path for candidate in CASE3_CANDIDATES)
    visual_terms = frozenset(CASE3_VISUAL_TERMS)
    structured_terms = frozenset(CASE3_STRUCTURED_TERMS)

    assert CASE3_REQUIRED_TERMS == ("収納口2つ", "小型(卓上)", "縦", "収納")
    assert paths == CASE3_NEAR_PATHS + CASE3_FAR_PATHS
    assert tuple(candidate.proximity for candidate in CASE3_CANDIDATES[:8]) == ("near",) * 8
    assert tuple(candidate.proximity for candidate in CASE3_CANDIDATES[8:]) == ("far",) * 12
    assert tuple(candidate.expected_rank for candidate in CASE3_CANDIDATES) == (
        1,
        2,
        1,
        3,
        4,
        3,
        1,
        1,
        9,
        9,
        5,
        10,
        5,
        6,
        9,
        9,
        6,
        7,
        8,
        5,
    )
    assert all(set(candidate.visual_features) <= visual_terms for candidate in CASE3_CANDIDATES)
    assert all(
        set(candidate.structured_features) <= structured_terms for candidate in CASE3_CANDIDATES
    )
    assert all(0.0 <= candidate.rating <= 5.0 for candidate in CASE3_CANDIDATES)
    assert all(candidate.review_count >= 0 for candidate in CASE3_CANDIDATES)
    assert CASE3_INDEPENDENT_REFERENCE_PATHS == ()


def test_case3_recorded_cluster_diagnostic_keeps_image_ranking_disabled() -> None:
    near_scores = CASE3_RECORDED_NEAR_SCORES
    far_scores = CASE3_RECORDED_FAR_SCORES
    paths = CASE3_NEAR_PATHS + CASE3_FAR_PATHS
    scores_by_path = dict(zip(paths, near_scores + far_scores, strict=True))
    auc = _pairwise_auc(near_scores, far_scores)
    concordant, comparable = _expected_order_concordance(scores_by_path)

    assert auc == pytest.approx(0.46875)
    assert (concordant, comparable) == (80, 173)
    assert concordant / comparable == pytest.approx(0.4624277456647399)
    assert auc < CASE3_DIAGNOSTIC_TARGET_AUC
    assert CLIP_IMAGE_RANKING_ENABLED is False


@pytest.mark.clip_runtime
def test_case3_images_are_fixed_unique_and_not_independent_references() -> None:
    images = _load_case3_images()

    assert tuple(images) == CASE3_NEAR_PATHS + CASE3_FAR_PATHS
    assert (
        deduplicate_image_hashes(
            tuple(compute_phash(image) for image in images.values())
        ).duplicates
        == ()
    )
    assert CASE3_INDEPENDENT_REFERENCE_PATHS == ()


@pytest.mark.clip_runtime
def test_case3_pinned_onnx_matches_recorded_cluster_diagnostic() -> None:
    images = _load_case3_images()
    paths = CASE3_NEAR_PATHS + CASE3_FAR_PATHS
    embeddings = _encode_in_fixed_batches(paths, images)
    near_scores, far_scores = _case3_cluster_scores(embeddings)
    scores_by_path = dict(zip(paths, near_scores + far_scores, strict=True))
    auc = _pairwise_auc(near_scores, far_scores)
    concordant, comparable = _expected_order_concordance(scores_by_path)

    print(
        "case3 self-excluded cluster diagnostic: "
        f"near={len(near_scores)} far={len(far_scores)} "
        f"pairwise_auc={auc:.9f} "
        f"expected_order_concordance={concordant}/{comparable}"
    )
    print("near_scores=" + ",".join(f"{score:.9f}" for score in near_scores))
    print("far_scores=" + ",".join(f"{score:.9f}" for score in far_scores))

    assert near_scores == pytest.approx(CASE3_RECORDED_NEAR_SCORES, abs=1e-8)
    assert far_scores == pytest.approx(CASE3_RECORDED_FAR_SCORES, abs=1e-8)
    assert auc == pytest.approx(0.46875)
    assert (concordant, comparable) == (80, 173)
    assert CLIP_IMAGE_RANKING_ENABLED is False
