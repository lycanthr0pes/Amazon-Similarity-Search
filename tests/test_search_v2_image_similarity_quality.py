from __future__ import annotations

import hashlib
import statistics
from dataclasses import dataclass
from io import BytesIO
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
from src.search_v2.image_similarity import score_clip_image_similarity
from src.search_v2.image_similarity_process import ProcessIsolatedClipImageEncoder


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_MODEL_ROOT = REPOSITORY_ROOT / "models" / "clip-vit-base-patch32-12b36594"
QUALITY_IMAGE_ROOT = Path(__file__).resolve().parent / "img" / "case1"
QUALITY_DATASET = (
    (
        "far/f1.png",
        "ee58436ca6ee05a006768ab809b34e314a03d0cf0184df813d74ff5426ee3733",
    ),
    (
        "far/f2.png",
        "8ffe27d37e82cfd1b01a20b23cd24d5062a35157270c87e22c6c795c158d5aa3",
    ),
    (
        "far/f3.png",
        "6fec5ccd8bda41f7c4ed6f0f2a63a07dda85999ec9644a7c0920e37794d26619",
    ),
    (
        "far/f4.png",
        "cb5406f82f588f478aa2c376933240caed7f6617b761e98943ec96738ec7ac4c",
    ),
    (
        "far/f5.png",
        "4a4db427fa44ee5a00e0026dc3d900c257d932531023657574424a2800e67fcb",
    ),
    (
        "far/f6.png",
        "c8cd7954af85f2bfc96eb5b4b72cf4e8fb2e56330470281bdc03fe2a8e275d4f",
    ),
    (
        "far/f7.png",
        "9165c676a5589eb7faf46f2cff331797d0069cd2e8c12077f29fe4ff472da204",
    ),
    (
        "far/f8.png",
        "e0d3bdfee78fce5d9b1dd418317212e91ea2171a5ce4251a2c1488c1dbe1914d",
    ),
    (
        "far/f9.png",
        "795b875268aeba80ed1f1762f6577ca3cccfdf274369b6bda9a5cc52c6c444d9",
    ),
    (
        "far/f10.png",
        "5b12163aa5980af28fd7a915dbd6bef24365a7e60d402b487c8247df4bd17a43",
    ),
    (
        "far/f11.png",
        "f9d9879afcecdbf3ed019b9e72d2acddd359c837339408009361aa84e2e06580",
    ),
    (
        "far/f12.png",
        "bafdf449deca77b736248dc3e476c5f2c8b5830cd5d5651e009b76b451da3868",
    ),
    (
        "far/f13.png",
        "88d8144c1262465fbf7d3ba8bb470de631dce0e5c6969d4643c27ec24d8e4901",
    ),
    (
        "far/f14.png",
        "4943ddb855f584d8c196bc5306148ee109e784f55ccba739f6f0c812eecf3223",
    ),
    (
        "far/f15.png",
        "ac65b18535fc953fa3fbf939a2d9b36d83b22a087328b3f1af3d56f2e1e5575c",
    ),
    (
        "far/f16.png",
        "61a98a8715c65ce4fa050ea8910635ba7530e3cb63fbad6a17f6fbef831d738e",
    ),
    (
        "far/f17.png",
        "6a3d9d5b78dc725abba79e4c8abfb9cd26a735754a055827a9cc32a8435c0806",
    ),
    (
        "far/f18.png",
        "320ba1bbc667d3250a009f0b26e70bea63e7e26bd717d2cb76cbe47b00b4d7b6",
    ),
    (
        "near/n1.png",
        "ceb34d094f67747668ae3a07080550262ebf86612cf736b794db2849d6c2e080",
    ),
    (
        "near/n2.png",
        "4c375e24c72d01bf5127d2d19fdb54b6b99601244a76342e11439afeeb6d653d",
    ),
    (
        "near/n3.png",
        "98ef8b1a8d321c8501b88e832fbfa4e46c4d28e6fe9caf828be187f5116700ba",
    ),
    (
        "near/n4.png",
        "08b7f4c7b9eb7eeb73e12e6896a5509098a37929a9632b46d031c61320945710",
    ),
    (
        "near/n5.png",
        "4056a450c67a98d32662d32c832d78ae048cd17d1dd6f8e4222b3801df87ecad",
    ),
    (
        "near/n6.png",
        "d7b5636e95d96de6df5c52a8a77f2d94cd711c5d5b848e262b6594598d5c0c25",
    ),
    (
        "near/n7.png",
        "8396a8d3fab2dedb391985e455ab380e214968309d7c7fdc84f96a93aaaeb72b",
    ),
    (
        "near/n8.png",
        "e7e4b577bcc2d88ab35fce8e0c29197aec1b6c0e9c5813bd749e33743277bae0",
    ),
    (
        "near/n9.png",
        "4fba5a31e6a3d3087817be64573cf6c4c3e07e980bd297f068719b4e5dbb29db",
    ),
    (
        "near/n10.png",
        "55885380454376eb0ac9d8345ee721883bb4e8117f499d29060f422f38caf852",
    ),
    (
        "near/n11.png",
        "a6b0e9d8caced0000e8884f5e6b8daec7cebe86b339e05eef0830582d18b44c8",
    ),
    (
        "near/n12.png",
        "a85f3bd565e35dd3d772d61130ebb102c987d0a0c3c0e8bd62b4a2d198eaea77",
    ),
    (
        "near/n13.png",
        "cd4d3f9dff72f6637dd223b3bdddc9ddb72d54a0bcc0fe84ba82664250dfc3c8",
    ),
)
QUALITY_REFERENCE_PATHS = (
    "near/n1.png",
    "near/n2.png",
    "near/n3.png",
    "near/n4.png",
)
QUALITY_MINIMUM_PAIRWISE_AUC = 0.80
RECORDED_NEAR_SCORES = (
    0.941577334,
    0.939536876,
    0.944146656,
    0.947831493,
    0.891125104,
    0.931441005,
    0.949760071,
    0.899660880,
    0.928696958,
)
RECORDED_FAR_SCORES = (
    0.928791317,
    0.934345042,
    0.918605976,
    0.956535633,
    0.923406968,
    0.849827980,
    0.948368015,
    0.833424674,
    0.818147319,
    0.941192911,
    0.934072352,
    0.849155019,
    0.826285005,
    0.881924209,
    0.920476008,
    0.880311011,
    0.849108477,
    0.869078758,
)


@dataclass(frozen=True, slots=True)
class QualityImageAttributes:
    path: str
    color: str | None
    connection: str | None
    is_gaming: bool | None
    object_type: str


# The user supplied these labels. None means the mouse-specific field is not applicable.
QUALITY_FAR_ATTRIBUTES = (
    QualityImageAttributes("far/f1.png", "white", "wired", True, "mouse"),
    QualityImageAttributes("far/f2.png", "black", "wired", True, "mouse"),
    QualityImageAttributes("far/f3.png", "white", "wireless", True, "mouse"),
    QualityImageAttributes("far/f4.png", "black", "wired", True, "mouse"),
    QualityImageAttributes("far/f5.png", "white", "wireless", True, "mouse"),
    QualityImageAttributes("far/f6.png", None, None, None, "mouse_feet"),
    QualityImageAttributes("far/f7.png", "black", "wired", True, "mouse"),
    QualityImageAttributes("far/f8.png", None, None, None, "mouse_feet"),
    QualityImageAttributes("far/f9.png", None, None, None, "mouse_feet"),
    QualityImageAttributes("far/f10.png", "black", "wired", True, "mouse"),
    QualityImageAttributes("far/f11.png", "black", "wireless", False, "mouse"),
    QualityImageAttributes("far/f12.png", "white", "wireless", True, "mouse"),
    QualityImageAttributes("far/f13.png", None, None, None, "mouse_feet"),
    QualityImageAttributes("far/f14.png", "white", "wireless", True, "mouse"),
    QualityImageAttributes("far/f15.png", "white", "wireless", True, "mouse"),
    QualityImageAttributes("far/f16.png", "red", "wireless", True, "mouse"),
    QualityImageAttributes("far/f17.png", None, None, None, "mouse_feet"),
    QualityImageAttributes("far/f18.png", None, None, None, "mouse_bungee"),
)
# These labels come from local image inspection only. Connection remains unknown because a
# disconnected cable, receiver, or dock in a still image does not establish wired/wireless
# product specifications. None for is_gaming means the use is not visible enough to confirm.
QUALITY_NEAR_VISUAL_ATTRIBUTES = (
    QualityImageAttributes("near/n1.png", "black", None, True, "mouse"),
    QualityImageAttributes("near/n2.png", "black", None, True, "mouse"),
    QualityImageAttributes("near/n3.png", "black", None, True, "mouse"),
    QualityImageAttributes("near/n4.png", "black", None, True, "mouse"),
    QualityImageAttributes("near/n5.png", "black", None, None, "mouse"),
    QualityImageAttributes("near/n6.png", "black", None, None, "mouse"),
    QualityImageAttributes("near/n7.png", "black", None, True, "mouse"),
    QualityImageAttributes("near/n8.png", "black", None, True, "mouse"),
    QualityImageAttributes("near/n9.png", "black", None, True, "mouse"),
    QualityImageAttributes("near/n10.png", "black", None, True, "mouse"),
    QualityImageAttributes("near/n11.png", "black", None, True, "mouse"),
    QualityImageAttributes("near/n12.png", "black", None, True, "mouse"),
    QualityImageAttributes("near/n13.png", "black", None, True, "mouse"),
)


def _load_quality_dataset() -> dict[str, ProxyImage]:
    assert QUALITY_IMAGE_ROOT.is_dir() and not QUALITY_IMAGE_ROOT.is_symlink()
    entries = tuple(QUALITY_IMAGE_ROOT.rglob("*"))
    assert not any(path.is_symlink() for path in entries)
    assert tuple(
        sorted(path.relative_to(QUALITY_IMAGE_ROOT).as_posix() for path in entries if path.is_dir())
    ) == ("far", "near")
    expected_paths = tuple(relative_path for relative_path, _ in QUALITY_DATASET)
    actual_paths = tuple(
        sorted(
            path.relative_to(QUALITY_IMAGE_ROOT).as_posix() for path in entries if path.is_file()
        )
    )
    assert actual_paths == tuple(sorted(expected_paths))

    images: dict[str, ProxyImage] = {}
    source_digests: set[str] = set()
    pixel_digests: set[str] = set()
    for relative_path, expected_sha256 in QUALITY_DATASET:
        path = QUALITY_IMAGE_ROOT / relative_path
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
            source_url_sha256=hashlib.sha256(f"quality:{relative_path}".encode()).hexdigest(),
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


def _pairwise_auc(near_scores: tuple[float, ...], far_scores: tuple[float, ...]) -> float:
    wins = sum(near > far for near in near_scores for far in far_scores)
    ties = sum(near == far for near in near_scores for far in far_scores)
    return (wins + ties * 0.5) / (len(near_scores) * len(far_scores))


def test_received_far_attributes_cover_fixed_manifest() -> None:
    far_paths = tuple(path for path, _ in QUALITY_DATASET if path.startswith("far/"))
    attributes = QUALITY_FAR_ATTRIBUTES

    assert tuple(item.path for item in attributes) == far_paths
    assert far_paths == tuple(f"far/f{index}.png" for index in range(1, 19))
    assert len(set(far_paths)) == 18
    assert {item.color for item in attributes} == {None, "black", "red", "white"}
    assert {item.connection for item in attributes} == {None, "wired", "wireless"}
    assert {item.is_gaming for item in attributes} == {None, False, True}
    assert {item.object_type for item in attributes} == {
        "mouse",
        "mouse_bungee",
        "mouse_feet",
    }
    assert sum(item.object_type == "mouse" for item in attributes) == 12
    assert sum(item.object_type == "mouse_feet" for item in attributes) == 5
    assert sum(item.object_type == "mouse_bungee" for item in attributes) == 1
    assert sum(item.color == "white" for item in attributes) == 6
    assert sum(item.color == "black" for item in attributes) == 5
    assert sum(item.color == "red" for item in attributes) == 1
    assert sum(item.connection == "wired" for item in attributes) == 5
    assert sum(item.connection == "wireless" for item in attributes) == 7
    assert sum(item.is_gaming is True for item in attributes) == 11
    assert sum(item.is_gaming is False for item in attributes) == 1


def test_near_visual_attributes_cover_fixed_manifest_without_filling_unknowns() -> None:
    near_paths = tuple(path for path, _ in QUALITY_DATASET if path.startswith("near/"))
    attributes = QUALITY_NEAR_VISUAL_ATTRIBUTES

    assert tuple(item.path for item in attributes) == near_paths
    assert near_paths == tuple(f"near/n{index}.png" for index in range(1, 14))
    assert len(set(near_paths)) == 13
    assert {item.color for item in attributes} == {"black"}
    assert {item.connection for item in attributes} == {None}
    assert {item.object_type for item in attributes} == {"mouse"}
    assert {item.is_gaming for item in attributes} == {None, True}
    assert sum(item.is_gaming is True for item in attributes) == 11
    assert tuple(item.path for item in attributes if item.is_gaming is None) == (
        "near/n5.png",
        "near/n6.png",
    )


def test_recorded_near_scores_do_not_fill_unknown_visual_gaming_use() -> None:
    candidate_attributes = tuple(
        item for item in QUALITY_NEAR_VISUAL_ATTRIBUTES if item.path not in QUALITY_REFERENCE_PATHS
    )
    scores_by_path = dict(
        zip(
            (item.path for item in candidate_attributes),
            RECORDED_NEAR_SCORES,
            strict=True,
        )
    )
    unknown_gaming = tuple(item for item in candidate_attributes if item.is_gaming is None)
    visible_gaming = tuple(item for item in candidate_attributes if item.is_gaming is True)

    assert tuple(item.path for item in unknown_gaming) == ("near/n5.png", "near/n6.png")
    assert tuple(item.path for item in visible_gaming) == tuple(
        f"near/n{index}.png" for index in range(7, 14)
    )

    unknown_gaming_mean = statistics.fmean(scores_by_path[item.path] for item in unknown_gaming)
    visible_gaming_mean = statistics.fmean(scores_by_path[item.path] for item in visible_gaming)
    print(
        "recorded near visual subgroups: "
        f"unknown_gaming_mean={unknown_gaming_mean:.9f} "
        f"visible_gaming_mean={visible_gaming_mean:.9f}"
    )

    assert unknown_gaming_mean > visible_gaming_mean


def test_recorded_far_scores_characterize_attribute_subgroups() -> None:
    scores_by_path = dict(
        zip(
            (item.path for item in QUALITY_FAR_ATTRIBUTES),
            RECORDED_FAR_SCORES,
            strict=True,
        )
    )
    connection_only = tuple(
        item
        for item in QUALITY_FAR_ATTRIBUTES
        if item.color == "black"
        and item.connection == "wired"
        and item.is_gaming is True
        and item.object_type == "mouse"
    )
    gaming_only = tuple(
        item
        for item in QUALITY_FAR_ATTRIBUTES
        if item.color == "black"
        and item.connection == "wireless"
        and item.is_gaming is False
        and item.object_type == "mouse"
    )
    color_only = tuple(
        item
        for item in QUALITY_FAR_ATTRIBUTES
        if item.color in {"red", "white"}
        and item.connection == "wireless"
        and item.is_gaming is True
        and item.object_type == "mouse"
    )
    non_mouse = tuple(item for item in QUALITY_FAR_ATTRIBUTES if item.object_type != "mouse")

    assert tuple(item.path for item in connection_only) == (
        "far/f2.png",
        "far/f4.png",
        "far/f7.png",
        "far/f10.png",
    )
    assert tuple(item.path for item in gaming_only) == ("far/f11.png",)
    assert tuple(item.path for item in color_only) == (
        "far/f3.png",
        "far/f5.png",
        "far/f12.png",
        "far/f14.png",
        "far/f15.png",
        "far/f16.png",
    )
    assert tuple(item.path for item in non_mouse) == (
        "far/f6.png",
        "far/f8.png",
        "far/f9.png",
        "far/f13.png",
        "far/f17.png",
        "far/f18.png",
    )

    connection_only_mean = statistics.fmean(scores_by_path[item.path] for item in connection_only)
    gaming_only_mean = statistics.fmean(scores_by_path[item.path] for item in gaming_only)
    color_only_mean = statistics.fmean(scores_by_path[item.path] for item in color_only)
    non_mouse_mean = statistics.fmean(scores_by_path[item.path] for item in non_mouse)
    print(
        "recorded far attribute subgroups: "
        f"connection_only_mean={connection_only_mean:.9f} "
        f"gaming_only_mean={gaming_only_mean:.9f} "
        f"color_only_mean={color_only_mean:.9f} "
        f"non_mouse_mean={non_mouse_mean:.9f}"
    )

    assert connection_only_mean > gaming_only_mean > color_only_mean > non_mouse_mean
    assert min(scores_by_path[item.path] for item in connection_only) > statistics.median(
        RECORDED_FAR_SCORES
    )


def test_recorded_scores_meet_connection_neutral_visual_scope() -> None:
    scores_by_path = dict(
        zip(
            (item.path for item in QUALITY_FAR_ATTRIBUTES),
            RECORDED_FAR_SCORES,
            strict=True,
        )
    )
    connection_only_paths = tuple(
        item.path
        for item in QUALITY_FAR_ATTRIBUTES
        if item.color == "black"
        and item.connection == "wired"
        and item.is_gaming is True
        and item.object_type == "mouse"
    )
    connection_only_path_set = frozenset(connection_only_paths)
    visual_positive_scores = RECORDED_NEAR_SCORES + tuple(
        scores_by_path[path] for path in connection_only_paths
    )
    visual_negative_scores = tuple(
        scores_by_path[item.path]
        for item in QUALITY_FAR_ATTRIBUTES
        if item.path not in connection_only_path_set
    )
    pairwise_wins = sum(
        near > far for near in visual_positive_scores for far in visual_negative_scores
    )
    pairwise_ties = sum(
        near == far for near in visual_positive_scores for far in visual_negative_scores
    )
    auc = _pairwise_auc(visual_positive_scores, visual_negative_scores)
    positive_median = statistics.median(visual_positive_scores)
    negative_median = statistics.median(visual_negative_scores)
    print(
        "recorded connection-neutral visual scope: "
        f"positive_count={len(visual_positive_scores)} "
        f"negative_count={len(visual_negative_scores)} "
        f"pairwise_wins={pairwise_wins} pairwise_ties={pairwise_ties} "
        f"pairwise_auc={auc:.9f} "
        f"positive_median={positive_median:.9f} "
        f"negative_median={negative_median:.9f}"
    )

    assert connection_only_paths == (
        "far/f2.png",
        "far/f4.png",
        "far/f7.png",
        "far/f10.png",
    )
    assert len(visual_positive_scores) == 13
    assert len(visual_negative_scores) == 14
    assert pairwise_wins == 169
    assert pairwise_ties == 0
    assert auc == pytest.approx(0.9285714285714286)
    assert auc >= QUALITY_MINIMUM_PAIRWISE_AUC
    assert positive_median == pytest.approx(0.941192911)
    assert negative_median == pytest.approx(0.874694884)
    assert _pairwise_auc(RECORDED_NEAR_SCORES, RECORDED_FAR_SCORES) == pytest.approx(
        0.7592592592592593
    )


@pytest.mark.clip_runtime
def test_received_quality_dataset_is_fixed_unique_and_has_disjoint_references() -> None:
    images = _load_quality_dataset()
    near_paths = tuple(path for path in images if path.startswith("near/"))
    far_paths = tuple(path for path in images if path.startswith("far/"))

    assert len(near_paths) == 13
    assert len(far_paths) == 18
    assert QUALITY_REFERENCE_PATHS == near_paths[:4]
    assert not set(QUALITY_REFERENCE_PATHS).intersection(far_paths)
    assert (
        deduplicate_image_hashes(
            tuple(compute_phash(image) for image in images.values())
        ).duplicates
        == ()
    )


@pytest.mark.clip_runtime
def test_received_quality_dataset_characterization_matches_recorded_baseline() -> None:
    images = _load_quality_dataset()
    near_paths = tuple(
        path for path in images if path.startswith("near/") and path not in QUALITY_REFERENCE_PATHS
    )
    far_paths = tuple(path for path in images if path.startswith("far/"))
    all_paths = (*QUALITY_REFERENCE_PATHS, *near_paths, *far_paths)
    embeddings = _encode_in_fixed_batches(all_paths, images)
    references = tuple(embeddings[path] for path in QUALITY_REFERENCE_PATHS)
    near_scores = tuple(
        score_clip_image_similarity(references, (embeddings[path],)).image_score
        for path in near_paths
    )
    far_scores = tuple(
        score_clip_image_similarity(references, (embeddings[path],)).image_score
        for path in far_paths
    )
    near_mean = statistics.fmean(near_scores)
    far_mean = statistics.fmean(far_scores)
    near_median = statistics.median(near_scores)
    far_median = statistics.median(far_scores)
    auc = _pairwise_auc(near_scores, far_scores)

    print(
        "received CLIP dataset: "
        f"references={len(references)} near={len(near_scores)} far={len(far_scores)} "
        f"near_mean={near_mean:.9f} far_mean={far_mean:.9f} "
        f"near_median={near_median:.9f} far_median={far_median:.9f} "
        f"near_min={min(near_scores):.9f} near_max={max(near_scores):.9f} "
        f"far_min={min(far_scores):.9f} far_max={max(far_scores):.9f} "
        f"pairwise_auc={auc:.9f}"
    )
    print("near_scores=" + ",".join(f"{score:.9f}" for score in near_scores))
    print("far_scores=" + ",".join(f"{score:.9f}" for score in far_scores))

    assert CLIP_IMAGE_RANKING_ENABLED is False
    assert near_scores == pytest.approx(RECORDED_NEAR_SCORES, abs=1e-8)
    assert far_scores == pytest.approx(RECORDED_FAR_SCORES, abs=1e-8)
    assert auc == pytest.approx(0.7592592592592593)


@pytest.mark.clip_runtime
@pytest.mark.xfail(
    reason="single-query dataset misses the predeclared pairwise AUC baseline",
    strict=True,
)
def test_recorded_quality_dataset_meets_predeclared_single_query_baseline() -> None:
    auc = _pairwise_auc(RECORDED_NEAR_SCORES, RECORDED_FAR_SCORES)

    assert auc >= QUALITY_MINIMUM_PAIRWISE_AUC
    assert statistics.median(RECORDED_NEAR_SCORES) > statistics.median(RECORDED_FAR_SCORES)
