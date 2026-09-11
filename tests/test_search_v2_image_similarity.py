import ast
import hashlib
import inspect
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

import src.search_v2.image_similarity as image_similarity
from src.search_v2.image_proxy import ProxyImage
from src.search_v2.image_proxy import proxy_image_pixel_sha256
from src.search_v2.image_similarity import CLIP_EMBEDDING_DIMENSION
from src.search_v2.image_similarity import CLIP_IMAGE_RANKING_ENABLED
from src.search_v2.image_similarity import CLIP_MODEL_ID
from src.search_v2.image_similarity import CLIP_REVISION
from src.search_v2.image_similarity import PHASH_DUPLICATE_MAX_DISTANCE
from src.search_v2.image_similarity import PINNED_CLIP_ASSET_MANIFEST
from src.search_v2.image_similarity import ClipAssetFile
from src.search_v2.image_similarity import ClipAssetManifest
from src.search_v2.image_similarity import ClipEmbedding
from src.search_v2.image_similarity import ClipRuntimeError
from src.search_v2.image_similarity import ImagePerceptualHash
from src.search_v2.image_similarity import clip_runtime_profile_sha256
from src.search_v2.image_similarity import compute_phash
from src.search_v2.image_similarity import deduplicate_image_hashes
from src.search_v2.image_similarity import phash_hamming_distance
from src.search_v2.image_similarity import run_pinned_clip_image_encoder
from src.search_v2.image_similarity import score_clip_image_similarity
from src.search_v2.image_similarity import verify_clip_asset_directory


def proxy_image(
    *,
    width: int = 32,
    height: int = 32,
    pixel_at=None,
    source_tag: str = "image",
) -> ProxyImage:
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            color = pixel_at(x, y) if pixel_at is not None else (64, 64, 64)
            pixels.extend(color)
    rgb_bytes = bytes(pixels)
    return ProxyImage(
        schema_version="2.0",
        source_url_sha256=hashlib.sha256(f"url:{source_tag}".encode()).hexdigest(),
        source_bytes_sha256=hashlib.sha256(f"body:{source_tag}".encode()).hexdigest(),
        pixel_sha256=proxy_image_pixel_sha256(width, height, rgb_bytes),
        content_type="image/png",
        image_format="PNG",
        width=width,
        height=height,
        rgb_bytes=rgb_bytes,
    )


def vector(index: int, *, sign: float = 1.0, scale: float = 1.0) -> tuple[float, ...]:
    values = [0.0] * CLIP_EMBEDDING_DIMENSION
    values[index] = sign * scale
    return tuple(values)


def embedding(
    index: int,
    *,
    tag: str,
    sign: float = 1.0,
    runtime_sha256: str | None = None,
):
    return ClipEmbedding(
        schema_version="2.0",
        image_pixel_sha256=hashlib.sha256(tag.encode()).hexdigest(),
        runtime_sha256=runtime_sha256 or clip_runtime_profile_sha256(),
        values=vector(index, sign=sign),
    )


def fixture_manifest(files: dict[str, bytes]) -> ClipAssetManifest:
    return ClipAssetManifest(
        schema_version="1.0",
        model_id=CLIP_MODEL_ID,
        revision=CLIP_REVISION,
        embedding_dimension=CLIP_EMBEDDING_DIMENSION,
        files=tuple(
            ClipAssetFile(
                relative_path=name,
                byte_length=len(body),
                sha256=hashlib.sha256(body).hexdigest(),
            )
            for name, body in files.items()
        ),
    )


def materialize_assets(root: Path, files: dict[str, bytes]) -> None:
    root.mkdir()
    for name, body in files.items():
        (root / name).write_bytes(body)


def test_pinned_clip_manifest_has_exact_model_revision_and_assets() -> None:
    assert PINNED_CLIP_ASSET_MANIFEST.model_id == "openai/clip-vit-base-patch32"
    assert PINNED_CLIP_ASSET_MANIFEST.revision == ("12b36594d53414ecfba93c7200dbb7c7db3c900a")
    assert PINNED_CLIP_ASSET_MANIFEST.embedding_dimension == 512
    assert [asset.model_dump() for asset in PINNED_CLIP_ASSET_MANIFEST.files] == [
        {
            "relative_path": "config.json",
            "byte_length": 456,
            "sha256": "20a24818e6ce94b8393759112206420496d48c6dcadacd657db33839bdaf823f",
        },
        {
            "relative_path": "model.onnx",
            "byte_length": 605804513,
            "sha256": "57879bb1c23cdeb350d23569dd251ed4b740a96d747c529e94a2bb8040ac5d00",
        },
        {
            "relative_path": "preprocessor_config.json",
            "byte_length": 468,
            "sha256": "5df7e578c37e907a431daf47fd592fc49fa50d23ed4c41285a0a34a58a9d2e06",
        },
    ]
    assert CLIP_IMAGE_RANKING_ENABLED is False
    assert image_similarity.CLIP_PREPROCESSING_PROFILE_ID == (
        "clip-rgb-bicubic-contain-mean-pad-224-v1"
    )
    assert image_similarity.CLIP_RUNTIME_PROFILE_DOMAIN == (
        b"amazon-explorer-clip-runtime-profile-v2\x00"
    )
    assert len(clip_runtime_profile_sha256()) == 64
    assert clip_runtime_profile_sha256() == clip_runtime_profile_sha256()


def test_runtime_profile_digest_binds_preprocessing_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = clip_runtime_profile_sha256()

    monkeypatch.setattr(
        image_similarity,
        "CLIP_PREPROCESSING_PROFILE_ID",
        "clip-rgb-bicubic-contain-mean-pad-224-v2",
    )

    assert clip_runtime_profile_sha256() != original


@pytest.mark.parametrize(
    "relative_path",
    ["../model.bin", "/model.bin", "subdir/model.bin", "MODEL.BIN", "model bin"],
)
def test_manifest_rejects_unsafe_asset_paths(relative_path: str) -> None:
    with pytest.raises(ValidationError):
        ClipAssetFile(relative_path=relative_path, byte_length=1, sha256="a" * 64)


def test_asset_verifier_accepts_only_exact_regular_file_set(tmp_path: Path) -> None:
    files = {
        "config.json": b"config",
        "model.onnx": b"weights",
        "preprocessor_config.json": b"processor",
    }
    manifest = fixture_manifest(files)
    root = tmp_path / "clip"
    materialize_assets(root, files)

    verified = verify_clip_asset_directory(root, manifest=manifest)

    assert verified.root == root.resolve()
    assert verified.manifest_sha256 == clip_runtime_profile_sha256(manifest)
    assert verified.asset_bundle_sha256 == clip_runtime_profile_sha256(manifest)
    assert len(verified.file_identities) == 3
    assert "weights" not in repr(verified)
    assert "file_identities" not in repr(verified)


@pytest.mark.parametrize("mutation", ["missing", "extra", "length", "digest", "directory"])
def test_asset_verifier_fails_closed_for_file_set_or_digest_changes(
    tmp_path: Path,
    mutation: str,
) -> None:
    files = {
        "config.json": b"config",
        "model.onnx": b"weights",
        "preprocessor_config.json": b"processor",
    }
    manifest = fixture_manifest(files)
    root = tmp_path / "clip"
    materialize_assets(root, files)
    if mutation == "missing":
        (root / "config.json").unlink()
    elif mutation == "extra":
        (root / "README.md").write_text("extra", encoding="utf-8")
    elif mutation == "length":
        (root / "config.json").write_bytes(b"longer-config")
    elif mutation == "digest":
        (root / "config.json").write_bytes(b"confiG")
    else:
        (root / "model.onnx").unlink()
        (root / "model.onnx").mkdir()

    with pytest.raises(ClipRuntimeError, match="^CLIP asset bundle is invalid$"):
        verify_clip_asset_directory(root, manifest=manifest)


def test_asset_verifier_rejects_symlink(tmp_path: Path) -> None:
    files = {
        "config.json": b"config",
        "model.onnx": b"weights",
        "preprocessor_config.json": b"processor",
    }
    manifest = fixture_manifest(files)
    root = tmp_path / "clip"
    materialize_assets(root, files)
    target = tmp_path / "outside.bin"
    target.write_bytes(files["model.onnx"])
    (root / "model.onnx").unlink()
    (root / "model.onnx").symlink_to(target)

    with pytest.raises(ClipRuntimeError, match="^CLIP asset bundle is invalid$"):
        verify_clip_asset_directory(root, manifest=manifest)


def test_asset_verifier_rejects_hardlink(tmp_path: Path) -> None:
    files = {
        "config.json": b"config",
        "model.onnx": b"weights",
        "preprocessor_config.json": b"processor",
    }
    manifest = fixture_manifest(files)
    root = tmp_path / "clip"
    materialize_assets(root, files)
    outside = tmp_path / "outside.onnx"
    (root / "model.onnx").rename(outside)
    (root / "model.onnx").hardlink_to(outside)

    with pytest.raises(ClipRuntimeError, match="^CLIP asset bundle is invalid$"):
        verify_clip_asset_directory(root, manifest=manifest)


def test_phash_is_deterministic_64_bit_and_brightness_duplicates_are_near() -> None:
    black = proxy_image(pixel_at=lambda _x, _y: (0, 0, 0), source_tag="black")
    white = proxy_image(pixel_at=lambda _x, _y: (255, 255, 255), source_tag="white")
    quadrants = proxy_image(
        pixel_at=lambda x, y: (255, 255, 255) if (x < 16) == (y < 16) else (0, 0, 0),
        source_tag="quadrants",
    )

    black_hash = compute_phash(black)
    white_hash = compute_phash(white)
    quadrants_hash = compute_phash(quadrants)

    assert black_hash == compute_phash(black)
    assert 0 <= black_hash.value <= (2**64 - 1)
    assert len(black_hash.hex_value) == 16
    assert black_hash.image_pixel_sha256 == black.pixel_sha256
    assert phash_hamming_distance(black_hash, white_hash) <= PHASH_DUPLICATE_MAX_DISTANCE
    assert phash_hamming_distance(black_hash, quadrants_hash) > PHASH_DUPLICATE_MAX_DISTANCE


def test_hamming_threshold_deduplicates_stably_without_becoming_a_score() -> None:
    hashes = (
        ImagePerceptualHash(schema_version="2.0", image_pixel_sha256="a" * 64, value=0),
        ImagePerceptualHash(schema_version="2.0", image_pixel_sha256="b" * 64, value=0b1_1111),
        ImagePerceptualHash(schema_version="2.0", image_pixel_sha256="c" * 64, value=0b11_1111),
    )

    result = deduplicate_image_hashes(hashes)

    assert PHASH_DUPLICATE_MAX_DISTANCE == 5
    assert result.kept_indices == (0, 2)
    assert result.duplicates[0].dropped_index == 1
    assert result.duplicates[0].kept_index == 0
    assert result.duplicates[0].hamming_distance == 5
    assert "phash" not in inspect.signature(score_clip_image_similarity).parameters
    assert "hamming" not in inspect.signature(score_clip_image_similarity).parameters


class RecordingEncoder:
    def __init__(self, outputs) -> None:
        self.outputs = outputs
        self.calls: list[dict[str, object]] = []

    def encode_images(self, **kwargs):
        self.calls.append(kwargs)
        return self.outputs


def test_pinned_runtime_verifies_assets_forces_local_only_and_normalizes(tmp_path: Path) -> None:
    files = {
        "config.json": b"config",
        "model.onnx": b"weights",
        "preprocessor_config.json": b"processor",
    }
    manifest = fixture_manifest(files)
    root = tmp_path / "clip"
    materialize_assets(root, files)
    image = proxy_image(source_tag="runtime")
    encoder = RecordingEncoder((vector(7, scale=3.0),))

    result = run_pinned_clip_image_encoder(
        (image,),
        asset_root=root,
        encoder=encoder,
        manifest=manifest,
    )

    assert len(result) == 1
    assert result[0].image_pixel_sha256 == image.pixel_sha256
    assert result[0].runtime_sha256 == clip_runtime_profile_sha256(manifest)
    assert result[0].values == vector(7)
    assert encoder.calls == [
        {
            "images": (image,),
            "asset_root": root.resolve(),
            "local_files_only": True,
        }
    ]


@pytest.mark.parametrize(
    "outputs",
    [
        (),
        (vector(0), vector(1)),
        ((0.0,) * (CLIP_EMBEDDING_DIMENSION - 1),),
        ((0.0,) * CLIP_EMBEDDING_DIMENSION,),
        (tuple(float("nan") if i == 0 else 0.0 for i in range(CLIP_EMBEDDING_DIMENSION)),),
        (tuple(True if i == 0 else 0.0 for i in range(CLIP_EMBEDDING_DIMENSION)),),
    ],
)
def test_pinned_runtime_rejects_invalid_encoder_outputs(tmp_path: Path, outputs) -> None:
    files = {
        "config.json": b"config",
        "model.onnx": b"weights",
        "preprocessor_config.json": b"processor",
    }
    manifest = fixture_manifest(files)
    root = tmp_path / "clip"
    materialize_assets(root, files)

    with pytest.raises(ClipRuntimeError, match="^CLIP encoder output is invalid$"):
        run_pinned_clip_image_encoder(
            (proxy_image(),),
            asset_root=root,
            encoder=RecordingEncoder(outputs),
            manifest=manifest,
        )


def test_clip_score_uses_four_angle_maxima_then_fixed_mapping() -> None:
    references = tuple(embedding(index, tag=f"reference-{index}") for index in range(4))
    candidates = (
        embedding(0, tag="candidate-0"),
        embedding(1, tag="candidate-1"),
    )

    result = score_clip_image_similarity(references, candidates)

    assert result.angle_max_cosines == pytest.approx((1.0, 1.0, 0.0, 0.0))
    assert result.mean_cosine == pytest.approx(0.5)
    assert result.image_score == pytest.approx(0.75)
    assert result.runtime_sha256 == clip_runtime_profile_sha256()


def test_clip_score_rejects_consistent_but_unapproved_runtime_digest() -> None:
    references = tuple(
        embedding(index, tag=f"reference-{index}", runtime_sha256="b" * 64) for index in range(4)
    )
    candidates = (embedding(0, tag="candidate", runtime_sha256="b" * 64),)

    with pytest.raises(ClipRuntimeError, match="^CLIP embedding set is invalid$"):
        score_clip_image_similarity(references, candidates)


@pytest.mark.parametrize(
    ("references", "candidates"),
    [
        (tuple(embedding(i, tag=f"r{i}") for i in range(3)), (embedding(0, tag="c"),)),
        (tuple(embedding(i, tag=f"r{i}") for i in range(4)), ()),
        (
            tuple(embedding(i, tag=f"r{i}") for i in range(4)),
            tuple(embedding(i, tag=f"c{i}") for i in range(5)),
        ),
        (
            tuple(embedding(i, tag=f"r{i}") for i in range(4)),
            (embedding(0, tag="c", runtime_sha256="b" * 64),),
        ),
    ],
)
def test_clip_score_rejects_wrong_counts_or_runtime(references, candidates) -> None:
    with pytest.raises(ClipRuntimeError, match="^CLIP embedding set is invalid$"):
        score_clip_image_similarity(references, candidates)


def test_clip_embedding_requires_finite_unit_vector() -> None:
    with pytest.raises(ValidationError):
        ClipEmbedding(
            schema_version="2.0",
            image_pixel_sha256="a" * 64,
            runtime_sha256="b" * 64,
            values=vector(0, scale=2.0),
        )

    invalid = list(vector(0))
    invalid[0] = math.inf
    with pytest.raises(ValidationError):
        ClipEmbedding(
            schema_version="2.0",
            image_pixel_sha256="a" * 64,
            runtime_sha256="b" * 64,
            values=tuple(invalid),
        )


def test_similarity_module_has_no_network_or_ml_runtime_import() -> None:
    module_path = Path(image_similarity.__file__)
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)

    forbidden = ("requests", "httpx", "socket", "torch", "transformers", "huggingface_hub")
    assert not any(
        name == prefix or name.startswith(f"{prefix}.") for name in imports for prefix in forbidden
    )
