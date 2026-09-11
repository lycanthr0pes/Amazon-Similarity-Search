"""Interactive, separately approved real-provider run of CandidateSearchFlow."""

from contextlib import ExitStack
from dataclasses import asdict, replace
from datetime import datetime, timezone
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import signal
import sys
import time

from PIL import Image

from src.search_v2.bonsai_request import (
    BONSAI_MAX_RESPONSE_BYTES,
    BONSAI_REQUEST_HEADERS,
    _response_body,
)
from src.search_v2.candidate_flow import CandidateSearchFlow
from src.search_v2.candidate_diagnostics import (
    CandidatePreparationError,
    candidate_failure_diagnostic,
)
from src.search_v2.candidate_search import FetchedCandidates
from src.search_v2.counterfactual_cloudflare_http import (
    CounterfactualCloudflareExecutionError,
    _artifact,
)
from src.search_v2.outscraper_contract import outscraper_request_sha256
from src.search_v2.outscraper_http import _execute_task, _validated_api_key
from src.search_v2.provisional_approval_repository import SqliteCounterfactualApprovalRepository
from src.search_v2.provisional_history_repository import SqliteProvisionalHistoryRepository
from tools import backend_search_live_e2e as shared


SYNTHETIC_INPUT = "マグカップ。丸みのある形。3000円以下。"
OWNER = "local-user"


def _log_response(output, name, response):
    # Concrete transports have already bounded the body. Preserve one-shot iterables for parsing.
    response = replace(response, body_chunks=tuple(response.body_chunks))
    body = b"".join(response.body_chunks)
    shared._json_file(
        output,
        name,
        {
            "status_code": response.status_code,
            "response_sha256": hashlib.sha256(body).hexdigest(),
            "response_bytes": len(body),
        },
    )
    return response


def _save_bonsai_timing(output, call, started, response):
    metrics = None
    if response is not None:
        try:
            metrics = asdict(
                shared.bonsai_runtime.project_response_metrics(_response_body(response))
            )
        except Exception:
            pass  # Optional, validated numerical metadata only; never save the raw failure.
    shared._json_file(
        output,
        f"bonsai-timing-{call}.json",
        {
            "wall_milliseconds": round((time.monotonic() - started) * 1000, 3),
            "response_received": response is not None,
            "model_metrics": metrics,
        },
    )


class _Bonsai:
    def __init__(self, transport, port, output, *, maximum_calls=1):
        self.transport, self.port, self.output = transport, port, output
        self.calls = 0
        self.maximum_calls = maximum_calls

    def evaluate(self, request):
        if self.calls >= self.maximum_calls:
            raise ValueError("Candidate live Bonsai limit exceeded")
        self.calls += 1
        started, response = time.monotonic(), None
        try:
            try:
                response = self.transport.post_json(
                    url=f"http://127.0.0.1:{self.port}/v1/chat/completions",
                    headers=BONSAI_REQUEST_HEADERS,
                    body=request,
                    allow_redirects=False,
                    accept_encoding="identity",
                    maximum_response_bytes=BONSAI_MAX_RESPONSE_BYTES,
                )
            except Exception:
                raise CandidatePreparationError("transport") from None
            response = _log_response(self.output, f"bonsai-response-{self.calls}.json", response)
            try:
                return _response_body(response)
            except Exception:
                raise CandidatePreparationError(
                    "http_status" if response.status_code != 200 else "http_response"
                ) from None
        finally:
            _save_bonsai_timing(self.output, self.calls, started, response)


class _Images(shared._CountedImages):
    def __init__(self, inner, output):
        super().__init__(inner)
        self.output, self.files = output, []

    def post_multipart(self, **kwargs):
        try:
            response = super().post_multipart(**kwargs)
            response = _log_response(self.output, f"image-http-{self.calls}.json", response)
            image = _artifact(kwargs["request"], response)
        except CounterfactualCloudflareExecutionError as error:
            shared._json_file(
                self.output,
                f"image-failure-{self.calls}.json",
                error.diagnostic.model_dump(mode="json"),
            )
            raise
        self.files.append(
            shared.saved_files._write_file(self.output / f"image-{self.calls}.png", image.body)
        )
        shared._json_file(
            self.output, f"image-response-{self.calls}.json", image.model_dump(mode="json")
        )
        return response


class _Products(shared._CountedProducts):
    def __init__(self, inner, output):
        super().__init__(inner)
        self.output = output

    def get(self, **kwargs):
        response = super().get(**kwargs)
        return _log_response(
            self.output, f"outscraper-response-{self.tasks + self.polls}.json", response
        )


class CandidateProducts:
    """One bound candidate request using the existing bounded task/poll transport."""

    def __init__(self, request, load_key, transport, sleep):
        self.request, self.load_key, self.transport, self.sleep = (
            request,
            load_key,
            transport,
            sleep,
        )
        self.used = False

    def fetch(self, request):
        if (
            self.used
            or request != self.request
            or len(request.queries) != 1
            or request.maximum_candidates != 24
        ):
            raise ValueError("Candidate live product request is not approved")
        self.used = True
        key = _validated_api_key(self.load_key().get_secret_value())
        request_id, data, _ = _execute_task(
            request, api_key=key, transport=self.transport, sleep=self.sleep
        )
        return FetchedCandidates(outscraper_request_sha256(request), request_id, {"data": data})


def _history_output(config, result, flow, now):
    repository = SqliteProvisionalHistoryRepository(config.output_dir / "history.sqlite3")
    detail = repository.get(owner_id=OWNER, locator=result.history.locator, now=now)
    listed = repository.list(owner_id=OWNER, now=now)
    if detail != result.history or len(listed) != 1 or listed[0].locator != detail.locator:
        raise ValueError("Candidate live history roundtrip failed")
    restored = type(result.ranking).model_validate_json(result.ranking.model_dump_json())
    if restored != result.ranking:
        raise ValueError("Candidate live ranking roundtrip failed")
    for stored, expected in zip(detail.reference_images, flow.reference_images, strict=True):
        image = repository.get_image(owner_id=OWNER, image_locator=stored.locator, now=now)
        with Image.open(BytesIO(image.body)) as decoded:
            if decoded.convert("RGB").tobytes() != expected.rgb_bytes:
                raise ValueError("Candidate live history image differs")
    shared._json_file(config.output_dir, "history.json", detail.model_dump(mode="json"))
    shared._json_file(
        config.output_dir, "image-scores.json", result.ranking.image_batch.model_dump(mode="json")
    )
    shared._json_file(
        config.output_dir,
        "ranking.json",
        {
            "profile_id": detail.ranking_profile_id,
            "products": [p.model_dump(mode="json") for p in detail.products],
        },
    )
    return {
        "product_count": len(detail.products),
        "history_images_verified": len(detail.reference_images),
        "ranking_profile_id": detail.ranking_profile_id,
        "lexical_scored_products": len(result.ranking.products),
        "image_evaluated": sum(p.image_score is not None for p in detail.products),
    }


def _confirm_images(services, stage, queries, files, conditions):
    review = {
        "queries": queries,
        "images": [str(item.path) for item in files],
        "maximum_candidates": 24,
        "visual_conditions": [c.model_dump(mode="json") for c in conditions.conditions],
    }
    confirmed = services.confirm(stage, review)
    if type(confirmed) is not bool:
        raise ValueError("Invalid image confirmation")
    return confirmed


def run_candidate_e2e(
    config,
    services,
    *,
    select_query=None,
    lexical_expander=None,
    source_parser=None,
    sense_resolver_factory=None,
    region_extractor=None,
    image_score_mode="siglip2_appearance",
):
    """Call only after the human has approved the displayed execution scope."""
    identity = shared._new_output(config)
    images = _Images(services.cloudflare_transport, config.output_dir)
    products = _Products(services.outscraper_transport, config.output_dir)
    proxy = shared._CountedProxy(services.proxy_service)
    encoder = shared._CountedEncoder(services.encoder)
    bonsai = None
    flow = None
    stage = "configuration"
    result = {"status": "failed"}
    try:
        settings = services.load_cloudflare()
        policy, ledger = shared._policy_and_ledger()
        approvals = SqliteCounterfactualApprovalRepository(config.output_dir / "approvals.sqlite3")
        history = SqliteProvisionalHistoryRepository(config.output_dir / "history.sqlite3")
        with services.bonsai_session() as transport:
            bonsai = _Bonsai(
                transport,
                config.bonsai_port,
                config.output_dir,
                maximum_calls=2 if sense_resolver_factory else 1,
            )
            expander = lexical_expander
            if sense_resolver_factory is not None:
                from src.search_v2.lexical_expansion import ContextualQueryExpander

                if not isinstance(expander, ContextualQueryExpander):
                    raise ValueError("Sense selection requires a contextual dictionary")
                expander = expander.with_resolver(sense_resolver_factory(bonsai))
            stage = "visual_conditions"
            flow = CandidateSearchFlow(
                SYNTHETIC_INPUT,
                owner_id=OWNER,
                session_id="candidate-live-e2e",
                postal_code="100-0001",
                policy=policy,
                usage_ledger=ledger,
                approval_repository=approvals,
                history_repository=history,
                image_transport=images,
                account_id=settings.cloudflare_account_id,
                api_token=settings.cloudflare_api_token.get_secret_value(),
                now=services.now,
                visual_extractor=bonsai,
                lexical_expander=expander,
                source_parser=source_parser,
                reference_region_extractor=region_extractor,
                image_score_mode=image_score_mode,
            )
            if (
                len(flow.plan.visual_conditions.conditions) != 1
                or len(flow.plan.request.queries) != 1
                or flow.plan.request.maximum_candidates != 24
            ):
                raise CandidatePreparationError("plan_limits")
            stage = "query_selection"
            if select_query is not None:
                index = select_query(
                    {
                        "queries": [q.model_dump(mode="json") for q in flow.plan.query_options],
                        "maximum_candidates": 24,
                        "visual_conditions": [
                            c.model_dump(mode="json")
                            for c in flow.plan.visual_conditions.conditions
                        ],
                        "expansion_status": flow.plan.query_expansion.status
                        if flow.plan.query_expansion
                        else "unavailable",
                        "query_terms": (
                            None
                            if flow.plan.query_expansion is None
                            or flow.plan.query_expansion.terms is None
                            else flow.plan.query_expansion.terms.model_dump(mode="json")
                        ),
                        "product_review": flow.plan.product_review.model_dump(mode="json")
                        if flow.plan.product_review is not None
                        else None,
                    }
                )
                flow.select_search_query(owner_id=OWNER, plan_sha256=flow.plan_sha256, index=index)
            shared._json_file(config.output_dir, "plan.json", flow.plan.model_dump(mode="json"))
            stage = "reference_image"
            reference = flow.generate_reference(
                owner_id=OWNER, plan_sha256=flow.plan_sha256, human_confirmed=True
            )
            queries = [q.value for q in flow.plan.request.queries]
            stage = "reference_confirmation"
            if not _confirm_images(
                services, "reference", queries, images.files, flow.plan.visual_conditions
            ):
                result = {"status": "cancelled", "stopped_at": stage}
            else:
                shared._verify_images(config.output_dir, identity, images.files)
                stage = "counterfactual_image"
                issued = flow.approve_reference(
                    owner_id=OWNER, reference_sha256=reference.sha256, human_confirmed=True
                )
                stage = "image_confirmation"
                if not _confirm_images(
                    services, "search", queries, images.files, flow.plan.visual_conditions
                ):
                    result = {"status": "cancelled", "stopped_at": stage}
                else:
                    shared._verify_images(config.output_dir, identity, images.files)
                    flow.approve_images(
                        owner_id=OWNER,
                        approval_id=issued.review.approval_id,
                        token=issued.token,
                        human_confirmed=True,
                    )
                    stage = "candidates"
                    review = flow.approve_and_fetch(
                        owner_id=OWNER,
                        plan_sha256=flow.plan_sha256,
                        transport=CandidateProducts(
                            flow.plan.request,
                            services.load_outscraper_api_key,
                            products,
                            services.sleep,
                        ),
                    )
                    # The fixed example names every condition. Never choose an inferred attribute silently.
                    if review.unresolved:
                        raise ValueError("Candidate live input needs attribute confirmation")
                    stage = "condition_confirmation"
                    flow.confirm(owner_id=OWNER, review_sha256=review.sha256, selections={})
                    stage = "ranking_clip_history"
                    completed = flow.complete(
                        owner_id=OWNER,
                        proxy_service=proxy,
                        asset_root=config.asset_root,
                        encoder=encoder,
                        region_extractor=region_extractor,
                    )
                    stage = "history_reopen"
                    result = {
                        "status": "succeeded",
                        **_history_output(config, completed, flow, services.now()),
                    }
    except Exception as error:
        # Do not print provider payloads, credential values, or exception text.
        if type(error) is CandidatePreparationError and error.product_review is not None:
            from src.search_v2.product_phrase import ProductPhraseReview

            review = ProductPhraseReview.model_validate(error.product_review)
            # This diagnostic runner has a fixed synthetic input and private output.
            shared._json_file(
                config.output_dir, "product-review.json", review.model_dump(mode="json")
            )
        result = {
            "status": "failed",
            "failure_stage": stage,
            "failure_diagnostic": candidate_failure_diagnostic(error).model_dump(mode="json"),
        }
        if result["failure_diagnostic"]["code"] == "reference_quality":
            result["failure_stage"] = "reference_quality"
    result.update(
        {
            "bonsai_calls": bonsai.calls if bonsai else 0,
            "cloudflare_calls": images.calls,
            "outscraper_tasks": products.tasks,
            "outscraper_polls": products.polls,
            "product_image_attempts": proxy.calls,
            "product_images_received": proxy.succeeded,
            "clip_batches": encoder.calls,
            "retry_count": 0,
        }
    )
    quality_reports = getattr(flow, "reference_quality", ())
    if quality_reports:
        shared._json_file(
            config.output_dir,
            "reference-quality.json",
            [
                {"condition_id": key, **report.model_dump(mode="json")}
                for key, report in quality_reports
            ],
        )
    shared._json_file(config.output_dir, "summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-live-api", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--asset-root", type=Path, required=True)
    parser.add_argument("--image-model", choices=("siglip2", "clip"), default="siglip2")
    parser.add_argument("--image-python", type=Path, help="Prepared Python for SigLIP 2")
    parser.add_argument("--server-bin", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument(
        "--lexical-assets", type=Path, help="Prepared local dictionary/encoder bundle"
    )
    parser.add_argument(
        "--translation-python", type=Path, help="Prepared OPUS-MT Python executable"
    )
    parser.add_argument("--opus-mt-assets", type=Path, help="Evaluated local OPUS-MT INT8 bundle")
    parser.add_argument(
        "--region-python", type=Path, help="Prepared local CLIPSeg Python executable"
    )
    parser.add_argument("--region-assets", type=Path, help="Pinned local CLIPSeg asset directory")
    parser.add_argument(
        "--mobile-sam-assets",
        type=Path,
        help="Pinned MobileSAM source and weights for instance refinement",
    )
    args = parser.parse_args()
    if args.image_model == "siglip2" and args.image_python is None:
        parser.error("SigLIP 2 requires --image-python; use --image-model clip for legacy CLIP")
    if args.image_model == "clip" and args.image_python is not None:
        parser.error("--image-python belongs to SigLIP 2")
    if args.mobile_sam_assets is not None and (
        args.region_python is None or args.region_assets is None
    ):
        parser.error("MobileSAM requires the region runtime and CLIPSeg assets")
    if bool(args.region_python) != bool(args.region_assets):
        parser.error("Region extraction requires both local runtime paths")
    if bool(args.translation_python) != bool(args.opus_mt_assets) or (
        args.opus_mt_assets is not None and args.lexical_assets is None
    ):
        parser.error("OPUS-MT requires both runtime paths and contextual lexical assets")
    if not args.run_live_api or not sys.stdin.isatty():
        parser.error(
            "Live execution requires separate human authorization, opt-in and an interactive terminal"
        )

    from src.config import CloudflareLiveSettings, OutscraperLiveSettings
    from src.search_v2.image_proxy_service import ImageProxyService
    from src.search_v2.image_similarity import verify_clip_asset_directory
    from src.search_v2.image_similarity_process import ProcessIsolatedClipImageEncoder
    from src.search_v2.outscraper_http import RequestsOutscraperTransport

    def confirm(stage, review):
        print(json.dumps({"stage": stage, **review}, ensure_ascii=False), flush=True)
        phrase = (
            shared.REFERENCE_CONFIRMATION if stage == "reference" else shared.SEARCH_CONFIRMATION
        )
        return input(f"続ける場合は「{phrase}」と入力: ") == phrase

    def select_query(review):
        print(json.dumps({"stage": "query_selection", **review}, ensure_ascii=False), flush=True)
        chosen = input("検索語の番号を0から選択（空欄は元の検索語0）: ").strip()
        if not chosen:
            return 0
        if len(chosen) != 1 or chosen not in "01234567":
            raise ValueError("Invalid query selection")
        return int(chosen)

    def expired(_signum, _frame):
        raise TimeoutError("Candidate live deadline exceeded")

    try:
        config = shared.BackendE2EConfig(args.output_dir, args.asset_root)
        runtime = shared.bonsai_runtime.BonsaiLiveE2EConfig(
            args.server_bin, args.model_path, config.bonsai_port
        )
        if args.image_model == "siglip2":
            from src.search_v2.siglip2 import LocalSiglip2ImageEncoder, verify_assets

            verify_assets(config.asset_root)
            image_encoder = LocalSiglip2ImageEncoder(args.image_python)
        else:
            verify_clip_asset_directory(config.asset_root)
            image_encoder = ProcessIsolatedClipImageEncoder()
        region_options = {}
        if args.region_assets is not None:
            from src.search_v2.clipseg_regions import LocalClipSegRegions

            region_options["region_extractor"] = LocalClipSegRegions(
                python=args.region_python,
                assets=args.region_assets,
                **(
                    {"mobile_sam_assets": args.mobile_sam_assets}
                    if args.mobile_sam_assets is not None
                    else {}
                ),
            )
        signal.signal(signal.SIGALRM, expired)
        signal.alarm(900)
        from src.search_v2.lexical_assets import load_lexical_services

        with ExitStack() as stack:
            lexical_options = {}
            if args.lexical_assets is not None:
                expander, syntax = stack.enter_context(load_lexical_services(args.lexical_assets))
                lexical_options = {"lexical_expander": expander, "source_parser": syntax}
                from src.search_v2.lexical_expansion import ContextualQueryExpander
                from src.search_v2.lexical_context import BonsaiProductSelector

                if args.opus_mt_assets is not None:
                    from src.search_v2.opus_mt import OpusMtTranslator

                    if not isinstance(expander, ContextualQueryExpander):
                        raise ValueError("OPUS-MT requires contextual product preparation")
                    expander = expander.with_translator(
                        OpusMtTranslator(args.translation_python, args.opus_mt_assets)
                    )
                    lexical_options["lexical_expander"] = expander
                if isinstance(expander, ContextualQueryExpander):
                    with args.model_path.open("rb") as model_file:
                        model_hash = hashlib.file_digest(model_file, "sha256").hexdigest()
                    lexical_options["sense_resolver_factory"] = lambda evaluator: (
                        BonsaiProductSelector(evaluator, model_hash)
                    )

            result = run_candidate_e2e(
                config,
                shared.BackendE2EServices(
                    bonsai_session=lambda: shared.owned_bonsai(runtime),
                    load_cloudflare=CloudflareLiveSettings,
                    cloudflare_transport=shared.RequestsBackendImageTransport(),
                    load_outscraper_api_key=lambda: OutscraperLiveSettings().outscraper_api_key,
                    outscraper_transport=RequestsOutscraperTransport(),
                    proxy_service=ImageProxyService(allowed_hosts=("m.media-amazon.com",)),
                    encoder=image_encoder,
                    now=lambda: datetime.now(timezone.utc),
                    sleep=time.sleep,
                    confirm=confirm,
                ),
                image_score_mode="siglip2_appearance"
                if args.image_model == "siglip2"
                else "appearance",
                select_query=select_query,
                **lexical_options,
                **region_options,
            )
        print(json.dumps(result, ensure_ascii=True), flush=True)
        return 0 if result["status"] == "succeeded" else 1
    except Exception:
        print('{"status":"failed","failure_stage":"entry_or_cleanup"}', flush=True)
        return 1
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    raise SystemExit(main())
