from __future__ import annotations

from dataclasses import dataclass
import hashlib
from io import BytesIO
import os
from pathlib import Path
import stat
import time
from typing import Literal
from typing import Protocol
from urllib.parse import urlsplit

from PIL import Image
from pydantic import SecretStr

from src.search_v2.counterfactual_image import VisualConditionDraft
from src.search_v2.counterfactual_image import build_counterfactual_reference_set
from src.search_v2.counterfactual_image import build_visual_condition_set
from src.search_v2.counterfactual_v4 import score_minimum_positive_conditions
from src.search_v2.image_proxy import ProxyImage
from src.search_v2.image_proxy import proxy_image_pixel_sha256
from src.search_v2.image_proxy_service import ImageProxyService
from src.search_v2.image_similarity import compute_phash
from src.search_v2.image_similarity import run_pinned_clip_image_encoder
from src.search_v2.image_similarity_process import ProcessIsolatedClipImageEncoder


PRODUCT_IMAGE_PROXY_E2E_REQUEST_COUNT = 1
PRODUCT_IMAGE_PROXY_E2E_RETRY_COUNT = 0
PRODUCT_IMAGE_PROXY_E2E_CLIP_IMAGE_COUNT = 3

_ALLOWED_HOST = "m.media-amazon.com"
_REFERENCE_NAMES = (
    "desired.png",
    "counterfactual-visual-condition-001.png",
)
_REFERENCE_MAX_BYTES = 2 * 1024 * 1024
_REFERENCE_SIZE = (512, 512)
_SOURCE_INPUT = "白い陶器製マグカップ"
_VISUAL_CONDITION = "白い"

_CONFIGURATION_ERROR = "Product image proxy E2E configuration is invalid"
_REFERENCE_ERROR = "Product image proxy E2E reference set is invalid"
_OUTPUT_ERROR = "Product image proxy E2E output is invalid"
_FETCH_ERROR = "Product image proxy E2E fetch failed"
_CLIP_ERROR = "Product image proxy E2E CLIP evaluation failed"

FailureStage = Literal["configuration", "reference", "output", "fetch", "clip"]


class ProductImageProxyLiveE2EError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        failure_stage: FailureStage,
        request_count: int = 0,
        wall_milliseconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_stage = failure_stage
        self.request_count = request_count
        self.retry_count = PRODUCT_IMAGE_PROXY_E2E_RETRY_COUNT
        self.wall_milliseconds = wall_milliseconds

    def safe_metadata(self) -> dict[str, int | str | None]:
        return {
            "failure_stage": self.failure_stage,
            "outcome": "failed",
            "request_count": self.request_count,
            "retry_count": self.retry_count,
            "wall_milliseconds": self.wall_milliseconds,
        }


class _ProxyService(Protocol):
    def fetch_image(self, url: str) -> ProxyImage: ...


class _CountingProxyService:
    def __init__(self, inner: _ProxyService) -> None:
        self.inner = inner
        self.request_count = 0

    def fetch_image(self, url: str) -> ProxyImage:
        self.request_count += 1
        return self.inner.fetch_image(url)


@dataclass(frozen=True, slots=True, repr=False)
class ProductImageProxyLiveE2EConfig:
    source_url: SecretStr
    reference_dir: Path
    output_path: Path
    asset_root: Path

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_url, SecretStr)
            or not isinstance(self.reference_dir, Path)
            or not isinstance(self.output_path, Path)
            or not isinstance(self.asset_root, Path)
        ):
            raise ProductImageProxyLiveE2EError(
                _CONFIGURATION_ERROR,
                failure_stage="configuration",
            ) from None


@dataclass(frozen=True, slots=True)
class ProductImageProxyLiveE2EResult:
    request_count: int
    retry_count: int
    clip_image_count: int
    score_status: str
    normalized_margin: float
    candidate_pixel_sha256: str
    reference_set_sha256: str
    wall_milliseconds: int
    output_path: Path

    def safe_metadata(self) -> dict[str, object]:
        return {
            "candidate_pixel_sha256": self.candidate_pixel_sha256,
            "clip_image_count": self.clip_image_count,
            "normalized_margin": self.normalized_margin,
            "outcome": "succeeded",
            "output_path": str(self.output_path),
            "reference_set_sha256": self.reference_set_sha256,
            "request_count": self.request_count,
            "retry_count": self.retry_count,
            "score_status": self.score_status,
            "wall_milliseconds": self.wall_milliseconds,
        }


def _elapsed_milliseconds(started: int) -> int:
    return max(1, (time.monotonic_ns() - started + 999_999) // 1_000_000)


def _validate_source_url(source_url: SecretStr) -> str:
    try:
        value = source_url.get_secret_value()
        parsed = urlsplit(value)
        port = parsed.port
    except Exception:
        raise ProductImageProxyLiveE2EError(
            _CONFIGURATION_ERROR,
            failure_stage="configuration",
        ) from None
    if (
        not value
        or len(value) > 2_048
        or not value.isascii()
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
        or parsed.scheme != "https"
        or parsed.hostname != _ALLOWED_HOST
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or parsed.fragment
        or "%" in parsed.netloc
        or "\\" in parsed.netloc
    ):
        raise ProductImageProxyLiveE2EError(
            _CONFIGURATION_ERROR,
            failure_stage="configuration",
        ) from None
    return value


def _validate_output_path(path: Path) -> Path:
    if not path.is_absolute() or path.suffix.lower() != ".png" or path.name in {"", ".", ".."}:
        raise ProductImageProxyLiveE2EError(
            _OUTPUT_ERROR,
            failure_stage="output",
        ) from None
    try:
        parent = path.parent.lstat()
        if not stat.S_ISDIR(parent.st_mode) or path.exists() or path.is_symlink():
            raise OSError("output path is unavailable")
    except OSError:
        raise ProductImageProxyLiveE2EError(
            _OUTPUT_ERROR,
            failure_stage="output",
        ) from None
    return path


def _stable_stat(result: os.stat_result) -> tuple[int, ...]:
    return (
        result.st_mode,
        result.st_ino,
        result.st_dev,
        result.st_nlink,
        result.st_uid,
        result.st_gid,
        result.st_size,
        result.st_mtime_ns,
        result.st_ctime_ns,
    )


def _read_reference_file(path: Path) -> bytes:
    descriptor = -1
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_uid != os.getuid()
            or before.st_nlink != 1
            or not 1 <= before.st_size <= _REFERENCE_MAX_BYTES
        ):
            raise OSError("reference file is unsafe")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(64 * 1024, _REFERENCE_MAX_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > _REFERENCE_MAX_BYTES:
                raise OSError("reference file is too large")
        after = os.fstat(descriptor)
        if _stable_stat(before) != _stable_stat(after) or total != before.st_size:
            raise OSError("reference file changed")
        return b"".join(chunks)
    except OSError:
        raise ProductImageProxyLiveE2EError(
            _REFERENCE_ERROR,
            failure_stage="reference",
        ) from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _reference_proxy_image(name: str, body: bytes) -> ProxyImage:
    try:
        with Image.open(BytesIO(body), formats=("PNG",)) as image:
            image.load()
            if (
                image.format != "PNG"
                or image.mode != "RGB"
                or image.size != _REFERENCE_SIZE
                or getattr(image, "n_frames", 1) != 1
                or image.info != {}
            ):
                raise ValueError("reference image contract mismatch")
            pixels = image.tobytes()
        width, height = _REFERENCE_SIZE
        return ProxyImage(
            schema_version="2.0",
            source_url_sha256=hashlib.sha256(
                f"approved-reference:{name}".encode("ascii")
            ).hexdigest(),
            source_bytes_sha256=hashlib.sha256(body).hexdigest(),
            pixel_sha256=proxy_image_pixel_sha256(width, height, pixels),
            content_type="image/png",
            image_format="PNG",
            width=width,
            height=height,
            rgb_bytes=pixels,
        )
    except ProductImageProxyLiveE2EError:
        raise
    except Exception:
        raise ProductImageProxyLiveE2EError(
            _REFERENCE_ERROR,
            failure_stage="reference",
        ) from None


def _load_references(reference_dir: Path) -> tuple[ProxyImage, ProxyImage]:
    if not reference_dir.is_absolute() or reference_dir.name in {"", ".", ".."}:
        raise ProductImageProxyLiveE2EError(
            _REFERENCE_ERROR,
            failure_stage="reference",
        ) from None
    try:
        directory = reference_dir.lstat()
        names = tuple(sorted(os.listdir(reference_dir)))
        if (
            not stat.S_ISDIR(directory.st_mode)
            or stat.S_IMODE(directory.st_mode) != 0o700
            or directory.st_uid != os.getuid()
            or names != tuple(sorted(_REFERENCE_NAMES))
        ):
            raise OSError("reference directory is unsafe")
    except OSError:
        raise ProductImageProxyLiveE2EError(
            _REFERENCE_ERROR,
            failure_stage="reference",
        ) from None
    return tuple(
        _reference_proxy_image(name, _read_reference_file(reference_dir / name))
        for name in _REFERENCE_NAMES
    )


def _build_reference_contract(
    references: tuple[ProxyImage, ProxyImage],
):
    conditions = build_visual_condition_set(
        source_input=_SOURCE_INPUT,
        drafts=(
            VisualConditionDraft(
                source_phrase=_VISUAL_CONDITION,
                strength="required",
                attribute_key="色",
            ),
        ),
    )
    reference_set = build_counterfactual_reference_set(
        condition_set=conditions,
        desired_image_hash=compute_phash(references[0]),
        counterfactual_image_hashes=(compute_phash(references[1]),),
    )
    return conditions, reference_set


def _write_output(path: Path, candidate: ProxyImage) -> None:
    descriptor = -1
    try:
        image = Image.frombytes("RGB", (candidate.width, candidate.height), candidate.rgb_bytes)
        encoded = BytesIO()
        image.save(encoded, format="PNG")
        body = encoded.getvalue()
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags, 0o600)
        view = memoryview(body)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short write")
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o600)
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
            descriptor = -1
        try:
            path.unlink()
        except OSError:
            pass
        raise ProductImageProxyLiveE2EError(
            _OUTPUT_ERROR,
            failure_stage="output",
            request_count=PRODUCT_IMAGE_PROXY_E2E_REQUEST_COUNT,
        ) from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def run_product_image_proxy_live_e2e(
    config: ProductImageProxyLiveE2EConfig,
    *,
    proxy_service: _ProxyService | None = None,
) -> ProductImageProxyLiveE2EResult:
    try:
        if not isinstance(config, ProductImageProxyLiveE2EConfig):
            raise TypeError("config is invalid")
        source_url = _validate_source_url(config.source_url)
    except ProductImageProxyLiveE2EError:
        raise
    except Exception:
        raise ProductImageProxyLiveE2EError(
            _CONFIGURATION_ERROR,
            failure_stage="configuration",
        ) from None

    output_path = _validate_output_path(config.output_path)
    references = _load_references(config.reference_dir)
    try:
        conditions, reference_set = _build_reference_contract(references)
    except Exception:
        raise ProductImageProxyLiveE2EError(
            _REFERENCE_ERROR,
            failure_stage="reference",
        ) from None

    try:
        service = proxy_service or ImageProxyService(allowed_hosts=(_ALLOWED_HOST,))
        counting_service = _CountingProxyService(service)
    except Exception:
        raise ProductImageProxyLiveE2EError(
            _CONFIGURATION_ERROR,
            failure_stage="configuration",
        ) from None

    started = time.monotonic_ns()
    try:
        candidate = ProxyImage.model_validate(counting_service.fetch_image(source_url))
        if counting_service.request_count != PRODUCT_IMAGE_PROXY_E2E_REQUEST_COUNT:
            raise RuntimeError("request count is invalid")
    except Exception:
        raise ProductImageProxyLiveE2EError(
            _FETCH_ERROR,
            failure_stage="fetch",
            request_count=counting_service.request_count,
            wall_milliseconds=_elapsed_milliseconds(started),
        ) from None

    try:
        embeddings = run_pinned_clip_image_encoder(
            (*references, candidate),
            asset_root=config.asset_root,
            encoder=ProcessIsolatedClipImageEncoder(),
        )
        if len(embeddings) != PRODUCT_IMAGE_PROXY_E2E_CLIP_IMAGE_COUNT:
            raise ValueError("CLIP embedding count is invalid")
        score = score_minimum_positive_conditions(
            condition_set=conditions,
            reference_set=reference_set,
            reference_embeddings=embeddings[:2],
            candidate_embedding=embeddings[2],
        )
        if len(score.condition_margins) != 1:
            raise ValueError("score condition count is invalid")
        margin = score.condition_margins[0]
        if (
            score.status != "scored"
            or margin.status != "scored"
            or margin.normalized_margin is None
        ):
            raise ValueError("score is unavailable")
    except Exception:
        raise ProductImageProxyLiveE2EError(
            _CLIP_ERROR,
            failure_stage="clip",
            request_count=counting_service.request_count,
            wall_milliseconds=_elapsed_milliseconds(started),
        ) from None

    try:
        _write_output(output_path, candidate)
    except ProductImageProxyLiveE2EError as error:
        raise ProductImageProxyLiveE2EError(
            str(error),
            failure_stage="output",
            request_count=counting_service.request_count,
            wall_milliseconds=_elapsed_milliseconds(started),
        ) from None

    return ProductImageProxyLiveE2EResult(
        request_count=counting_service.request_count,
        retry_count=PRODUCT_IMAGE_PROXY_E2E_RETRY_COUNT,
        clip_image_count=PRODUCT_IMAGE_PROXY_E2E_CLIP_IMAGE_COUNT,
        score_status=score.status,
        normalized_margin=margin.normalized_margin,
        candidate_pixel_sha256=candidate.pixel_sha256,
        reference_set_sha256=score.reference_set_sha256,
        wall_milliseconds=_elapsed_milliseconds(started),
        output_path=output_path,
    )


def main() -> int:
    raise SystemExit(
        "Run the dedicated pytest node so all live-service opt-ins and safe reporting apply."
    )


if __name__ == "__main__":
    raise SystemExit(main())
