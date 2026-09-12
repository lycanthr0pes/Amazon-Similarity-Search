"""Explicit live composition for one fixed browser canary; no payload logging."""

from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from pathlib import Path
import base64
import hashlib
from io import BytesIO
import os
import threading

from src.search_v2.browser_candidate import (
    BrowserImages,
    candidate_browser_steps,
    MAX_BROWSER_IMAGE_SETS,
)


CANARY_INPUT = "マグカップ。丸みのある形。3000円以下。"
OWNER = "local-user"
ASSETS = Path("/home/products/models/siglip2-base-patch16-224-75de2d55")
IMAGE_PYTHON = Path("/home/products/model-envs/mobile-sam-eval-01/bin/python")
MODEL = Path("/home/products/models/Bonsai-8B.gguf")
SERVER = Path("/home/llama.cpp/build/bin/llama-server")
LEXICAL_ASSETS = Path("/home/products/models/search-lexical-context-v2")
WORDNET_DB = Path("/home/products/models/search-lexical-v1/wnjpn.db")
WORDNET_ADJECTIVES = Path("/home/products/models/wordnet-3.0-visual/data.adj")
WORDNET_SHA256 = "afde5f551efce321702022822f3b165630ed12b5ea79fffa44fb2f85aaa5b06d"
TRANSLATION_PYTHON = Path("/home/products/model-envs/opus-mt-eval-02/bin/python")
TRANSLATION_ASSETS = Path("/home/products/models/opus-mt-ja-en-ct2-v1")


class BrowserBonsai:
    def __init__(self, transport, *, stop):
        self._transport = transport
        self._stop = stop
        self.calls = 0

    def evaluate(self, request):
        from src.search_v2.bonsai_request import (
            BONSAI_REQUEST_HEADERS,
            BONSAI_MAX_RESPONSE_BYTES,
            _response_body,
        )

        if self.calls >= 2:
            raise ValueError("Bonsai execution limit reached")
        self.calls += 1
        expired = threading.Event()

        def expire():
            expired.set()
            try:
                self._stop()
            except OSError:
                pass  # The owning context verifies process cleanup.

        timer = threading.Timer(900, expire)
        timer.daemon = True
        timer.start()
        try:
            response = self._transport.post_json(
                url="http://127.0.0.1:18080/v1/chat/completions",
                headers=BONSAI_REQUEST_HEADERS,
                body=request,
                allow_redirects=False,
                accept_encoding="identity",
                maximum_response_bytes=BONSAI_MAX_RESPONSE_BYTES,
            )
        finally:
            timer.cancel()
            timer.join()
        if expired.is_set():
            raise ValueError("Bonsai request timed out")
        return _response_body(response)


@contextmanager
def browser_bonsai(config):
    """Own the model during preparation; each inference has a separate timeout."""
    from tools import bonsai_live_e2e as runtime

    process = runtime._launch_server(config)
    try:
        runtime._wait_until_ready(process, config.port)
        yield BrowserBonsai(runtime.RequestsBonsaiTransport(), stop=process.kill)
    finally:
        runtime._stop_server(process, config.port)


def live_steps(output, *, source=CANARY_INPUT, attempt=0, progress=None, batch=0, image_mode="on"):
    from src.search_v2.browser_search import validate_browser_source
    from src.config import CloudflareLiveSettings
    from src.search_v2.candidate_flow import CandidateSearchFlow
    from src.search_v2.image_proxy_service import ImageProxyService
    from src.search_v2.wordnet_contrast import WordNetContrastDictionary
    from src.search_v2.lexical_assets import load_lexical_services
    from src.search_v2.lexical_context import BonsaiProductSelector
    from src.search_v2.lexical_expansion import ContextualQueryExpander
    from src.search_v2.opus_mt import OpusMtTranslator
    from src.search_v2.playwright_products import PlaywrightProducts
    from src.search_v2.provisional_approval_repository import SqliteCounterfactualApprovalRepository
    from src.search_v2.provisional_history_repository import SqliteProvisionalHistoryRepository
    from src.search_v2.siglip2 import LocalSiglip2ImageEncoder, verify_assets
    from tools import backend_search_live_e2e as shared

    source = validate_browser_source(source)
    if image_mode not in {"on", "off"}:
        raise ValueError("Invalid preparation image mode")
    from src.search_v2.condition_language import analyze_conditions

    analyze_conditions(source)
    if type(attempt) is not int or not 0 <= attempt <= 2:
        raise ValueError("Invalid preparation attempt")
    output = Path(output).absolute()
    history_root = output
    repository = Path(__file__).resolve().parents[1]
    if output.is_relative_to(repository) or output.resolve() != output:
        raise ValueError("Use a new private directory outside the repository")
    if type(batch) is not int or not 0 <= batch <= 1000000:
        raise ValueError("Invalid search batch")
    if batch:
        output.mkdir(mode=0o700, parents=False, exist_ok=True)
        if output.stat().st_mode & 0o777 != 0o700:
            raise ValueError("Use a private run directory")
        output = output / f"search-{batch}"
        if output.resolve() != output:
            raise ValueError("Use a private run directory")
    if attempt:
        # Local clarification can return before the first run creates its directory.
        output.mkdir(mode=0o700, parents=False, exist_ok=True)
        if output.stat().st_mode & 0o777 != 0o700:
            raise ValueError("Use a private run directory")
        output = output / f"revision-{attempt}"
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.chmod(output, 0o700)
    with MODEL.open("rb") as stream:
        model_hash = hashlib.file_digest(stream, "sha256").hexdigest()

    def now():
        return datetime.now(timezone.utc)

    def image_settings():
        verify_assets(ASSETS)
        settings = CloudflareLiveSettings()
        return settings.cloudflare_account_id, settings.cloudflare_api_token.get_secret_value()

    runtime = shared.bonsai_runtime.BonsaiLiveE2EConfig(SERVER, MODEL, 18080)
    policy, ledger = shared._policy_and_ledger()
    images = BrowserImages(shared.RequestsBackendImageTransport())

    def thumbnail_factory():
        return shared._CountedProxy(ImageProxyService(allowed_hosts=("m.media-amazon.com",)))

    def image_evaluator():
        return (
            thumbnail_factory(),
            ASSETS,
            shared._CountedEncoder(LocalSiglip2ImageEncoder(IMAGE_PYTHON)),
        )

    history = SqliteProvisionalHistoryRepository(history_root / "history.sqlite3")
    with (
        load_lexical_services(LEXICAL_ASSETS) as (expander, syntax),
        (
            WordNetContrastDictionary(
                WORDNET_DB, WORDNET_ADJECTIVES, expected_sha256=WORDNET_SHA256
            )
            if image_mode == "on"
            else nullcontext(None)
        ) as contrast_dictionary,
        browser_bonsai(runtime) as bonsai,
    ):
        if not isinstance(expander, ContextualQueryExpander):
            raise ValueError("Contextual dictionary required")
        expander = expander.with_translator(
            OpusMtTranslator(TRANSLATION_PYTHON, TRANSLATION_ASSETS)
        )
        expander = expander.with_resolver(BonsaiProductSelector(bonsai, model_hash))
        flow = CandidateSearchFlow(
            source,
            owner_id=OWNER,
            session_id="browser-canary",
            postal_code="100-0001",
            policy=policy,
            usage_ledger=ledger,
            approval_repository=SqliteCounterfactualApprovalRepository(
                output / "approvals.sqlite3"
            ),
            history_repository=history,
            image_transport=images,
            account_id=None,
            api_token=None,
            image_settings=image_settings,
            allow_image_free=True,
            image_mode=image_mode,
            now=now,
            visual_extractor=bonsai if image_mode == "on" else None,
            lexical_expander=expander,
            contrast_resolver=expander.visual_contrasts(contrast_dictionary)
            if image_mode == "on"
            else None,
            source_parser=syntax,
            image_score_mode="siglip2_appearance",
            plan_lifetime=None,
        )
    yield from candidate_browser_steps(
        flow,
        owner=OWNER,
        images=images,
        products=lambda request: PlaywrightProducts(
            request,
            progress=(lambda step: progress(step, during_fetch=True))
            if progress is not None
            else None,
        ),
        history=history,
        now=now,
        proxy=None,
        assets=None,
        encoder=None,
        image_evaluator=image_evaluator,
        thumbnail_factory=thumbnail_factory,
        progress=progress,
    )


def fixture_steps(*, source=CANARY_INPUT, image_mode="on"):
    """Synthetic responses only; provider and credential factories stay uncalled."""
    from PIL import Image, ImageDraw

    previews = []
    for color, shape in (("white", "ellipse"), ("gray", "rectangle")):
        image = Image.new("RGB", (512, 512), "#cccccc")
        draw = ImageDraw.Draw(image)
        getattr(draw, shape)((150, 140, 360, 370), fill=color, outline="black", width=5)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        previews.append("data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode())
    prompts = {
        "reference": "A studio photograph of the requested product.",
        "comparison": {"visual-condition-001": "Edit the specified shape in reference image 0."},
    }
    command = yield {
        "stage": "query",
        "canSkipImages": True,
        "canGenerateImages": image_mode == "on",
        "imagePrompts": prompts if image_mode == "on" else None,
        "referenceRemaining": MAX_BROWSER_IMAGE_SETS,
        **({"imageMode": "off", "images": []} if image_mode == "off" else {}),
        "productName": source.split("。", 1)[0],
        "conditionText": source.partition("。")[2],
        "queries": [source.split("。", 1)[0]],
        "conditions": ["丸みのある形"],
        "conditionLabels": {"condition-price": "価格", "visual-condition-001": "丸みのある形"},
    }
    skip = bool(command and (command or {}).get("without_images"))
    attempts = 0
    while not skip:
        attempts += 1
        remaining = MAX_BROWSER_IMAGE_SETS - attempts
        if attempts > MAX_BROWSER_IMAGE_SETS:
            raise ValueError("Image limit reached")
        if not (command or {}).get("regenerate_comparisons"):
            prompts["reference"] = (command or {}).get("prompt", prompts["reference"])
            command = yield {
                "stage": "reference",
                "images": previews[:1],
                "selectedQuery": source.split("。", 1)[0],
                "canSkipImages": True,
                "imagePrompts": prompts,
                "canRegenerate": remaining > 0,
                "canRegenerateComparisons": False,
                "referenceRemaining": remaining,
            }
            if (command or {}).get("regenerate"):
                continue
            skip = bool((command or {}).get("without_images"))
            if skip:
                break
        prompts["comparison"].update((command or {}).get("prompts", {}))
        command = yield {
            "stage": "comparison",
            "images": previews,
            "canSkipImages": True,
            "imagePrompts": prompts,
            "canRegenerate": remaining > 0,
            "canRegenerateComparisons": remaining > 0,
            "referenceRemaining": remaining,
        }
        if (command or {}).get("regenerate") or (command or {}).get("regenerate_comparisons"):
            continue
        skip = bool((command or {}).get("without_images"))
        if skip:
            break
        command = yield {"stage": "final", "canSkipImages": True}
        if (command or {}).get("regenerate") or (command or {}).get("regenerate_comparisons"):
            continue
        skip = bool((command or {}).get("without_images"))
        break
    if skip:
        yield {
            "stage": "final",
            "images": [],
            "imageMode": "off",
            "canSkipImages": False,
            "selectedQuery": "マグカップ",
        }
    yield {
        "stage": "complete",
        "saved": False,
        "canSkipImages": False,
        **(
            {"imageMode": "off", "sortProfile": "excluded-title-conditions-image-review-v1"}
            if skip
            else {}
        ),
        "products": [
            {
                "title": "合成マグカップ",
                "price": 2000,
                "url": None,
                "required": "一致",
                "appearance": "画像比較は使用していません" if skip else "参考画像による外観補助",
                "thumbnail": previews[0],
                "scores": {
                    "title": {"score_ja": 1.0, "score_en": 0.8, "score": 1.0},
                    "image": None if skip else 0.75,
                    "total": 1.0 if skip else 0.875,
                    "conditions": [
                        {
                            "requirement_id": "condition-price",
                            "strength": "required",
                            "score_ja": 1.0,
                            "score_en": None,
                            "score": 1.0,
                        }
                    ],
                },
            }
        ],
    }
