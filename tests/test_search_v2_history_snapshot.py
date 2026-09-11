from __future__ import annotations

import ast
import base64
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from io import BytesIO
import inspect
import json
from pathlib import Path
import sqlite3

from PIL import Image
import pytest

import src.search_v2.history_snapshot as history_snapshot
import src.search_v2.orchestrator as orchestrator
from src.search_v2.cloudflare_http import CloudflareHttpResponse
from src.search_v2.counterfactual_image import VisualConditionDraft
from src.search_v2.counterfactual_image import build_visual_condition_set
from src.search_v2.history_repository import HistoryStorageError
from src.search_v2.history_repository import SqliteSearchHistoryRepository
from src.search_v2.outscraper_http import OutscraperHttpResponse
from src.search_v2.product_normalization import ProductNormalizationProfile
from src.search_v2.product_pipeline import ProductSearchPipelineResult
from src.search_v2.state_machine import InMemoryApprovalLedger
from src.search_v2.typed_ranking import TYPED_RANKING_PROFILE_V4
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import ProviderUsageLimits
from src.search_v2.usage_ledger import UsageAmount


NOW = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
SOURCE_TEXT = "Sony WH-1000XM5の黒い軽量ワイヤレスヘッドホンを5万円以内で。中古は避けたい。"
ACCOUNT_ID = "0123456789abcdef0123456789abcdef"


class SequenceClock:
    def __init__(self) -> None:
        self.offset = 0

    def __call__(self) -> datetime:
        value = NOW + timedelta(seconds=self.offset)
        self.offset += 1
        return value


class BonsaiTransport:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def post_json(self, **kwargs: object):
        self.calls.append(kwargs)
        content = json.dumps(intent_payload(), ensure_ascii=False, separators=(",", ":"))
        body = json.dumps(
            {
                "id": "fixture-bonsai-response",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        from src.search_v2.bonsai_request import BonsaiHttpResponse

        return BonsaiHttpResponse(
            status_code=200,
            content_type="application/json; charset=utf-8",
            content_length=len(body),
            content_encoding="identity",
            body_chunks=(body,),
        )


class CloudflareTransport:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.responses = cloudflare_responses()

    def post_multipart(self, **kwargs: object):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class OutscraperTransport:
    def __init__(self, response: OutscraperHttpResponse | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def get(self, **kwargs: object):
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@dataclass(frozen=True, slots=True)
class CompletedContext:
    source_text: str
    review: orchestrator.SearchReview
    result: ProductSearchPipelineResult
    bonsai: BonsaiTransport
    cloudflare: CloudflareTransport | None
    outscraper: OutscraperTransport

    @property
    def provider_call_counts(self) -> tuple[int, int, int]:
        return (
            len(self.bonsai.calls),
            0 if self.cloudflare is None else len(self.cloudflare.calls),
            len(self.outscraper.calls),
        )


def intent_payload() -> dict[str, object]:
    return {
        "product_name_ja": "ヘッドホン",
        "required_terms_ja": ["ワイヤレス", "黒"],
        "preferred_terms_ja": ["軽量", "ノイズキャンセリング"],
        "negative_terms_ja": ["中古"],
        "brand": "Sony",
        "model_number": "WH-1000XM5",
        "price": {
            "mode": "max",
            "max_jpy": 50_000,
            "source": "explicit",
        },
        "typed_conditions": [
            {
                "attribute_key": "appearance.color",
                "operator": "equals",
                "expected_value": {"value_type": "enum", "values": ["black"]},
                "strength": "required",
            }
        ],
    }


def png_bytes(color: tuple[int, int, int]) -> bytes:
    output = BytesIO()
    Image.new("RGB", (512, 512), color).save(output, format="PNG")
    return output.getvalue()


def cloudflare_responses() -> list[CloudflareHttpResponse]:
    responses: list[CloudflareHttpResponse] = []
    for value in (20, 40, 60, 80, 100, 120):
        encoded = base64.b64encode(png_bytes((value, value + 1, value + 2))).decode("ascii")
        body = json.dumps(
            {"result": {"image": encoded}, "success": True, "errors": [], "messages": []},
            separators=(",", ":"),
        ).encode()
        responses.append(
            CloudflareHttpResponse(
                status_code=200,
                content_type="application/json; charset=utf-8",
                content_length=len(body),
                content_encoding="identity",
                body_chunks=(body,),
            )
        )
    return responses


def outscraper_response(
    query: str,
    *,
    empty: bool,
    product_title: str,
    product_color: str | None,
) -> OutscraperHttpResponse:
    products: list[dict[str, object]] = []
    if not empty:
        product: dict[str, object] = {
            "query": query,
            "name": product_title,
            "asin": "B012345678",
            "brand": "Sony",
            "description": "軽量でノイズキャンセリングに対応したワイヤレスヘッドホンです。",
            "categories": ["オーディオ"],
            "features": ["軽量", "ノイズキャンセリング"],
            "price": 40_000,
            "currency": "JPY",
            "url": "https://www.amazon.co.jp/dp/B012345678?tag=fixture#details",
            "high_res_images": ["https://images.example.test/product.jpg"],
        }
        if product_color is not None:
            product["color"] = product_color
        products.append(product)
    body = json.dumps(
        {"id": "fixture-outscraper-request", "status": "Success", "data": [products]},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    return OutscraperHttpResponse(
        status_code=200,
        content_type="application/json; charset=utf-8",
        content_length=len(body),
        content_encoding="identity",
        body_chunks=(body,),
    )


def usage_ledger() -> InMemoryUsageLedger:
    maximum = UsageAmount(calls=100, tokens=100_000_000, cost_microusd=10_000_000)
    return InMemoryUsageLedger(
        [
            ProviderUsageLimits(
                provider="bonsai",
                pricing_policy_sha256="a" * 64,
                per_user_day=maximum,
                per_session=maximum,
                global_day=maximum,
            ),
            ProviderUsageLimits(
                provider="cloudflare",
                pricing_policy_sha256="b" * 64,
                per_user_day=maximum,
                per_session=maximum,
                global_day=maximum,
            ),
            ProviderUsageLimits(
                provider="outscraper",
                pricing_policy_sha256="c" * 64,
                per_user_day=maximum,
                per_session=maximum,
                global_day=maximum,
            ),
        ]
    )


def backend_policy() -> orchestrator.SearchBackendPolicy:
    return orchestrator.SearchBackendPolicy(
        schema_version="3.0",
        bonsai_intent=orchestrator.ProviderAttemptBudget(
            amount=UsageAmount(calls=1, tokens=2_000_000, cost_microusd=5_000),
            pricing_policy_sha256="a" * 64,
        ),
        cloudflare_image_set=orchestrator.ProviderAttemptBudget(
            amount=UsageAmount(calls=4, tokens=0, cost_microusd=4_000),
            pricing_policy_sha256="b" * 64,
        ),
        outscraper_search=orchestrator.ProviderAttemptBudget(
            amount=UsageAmount(calls=1, tokens=0, cost_microusd=10_000),
            pricing_policy_sha256="c" * 64,
        ),
        normalization_profile=ProductNormalizationProfile(
            schema_version="2.0",
            profile_id="observed-only-v2",
            usd_to_jpy_rate=160,
        ),
        ranking_profile=TYPED_RANKING_PROFILE_V4,
        implementation_sha256="d" * 64,
    )


def complete_context(
    *,
    source_text: str = SOURCE_TEXT,
    owner_id: str = "owner-1",
    session_id: str = "session-1",
    with_images: bool = False,
    empty: bool = False,
    failed: bool = False,
    product_title: str = "Sony 黒 軽量 ワイヤレスヘッドホン",
    product_color: str | None = "黒",
) -> CompletedContext:
    ledger = usage_ledger()
    clock = SequenceClock()
    bonsai = BonsaiTransport()
    stage = orchestrator.start_intent_review(
        source_text,
        owner_id=owner_id,
        session_id=session_id,
        bonsai_config=orchestrator.BonsaiIntentConfig(
            base_url="http://127.0.0.1:8080/v1",
            model_id="Bonsai-8B.gguf",
            temperature=0.1,
        ),
        policy=backend_policy(),
        usage_ledger=ledger,
        transport=bonsai,
        now=clock,
    )
    cloudflare: CloudflareTransport | None = None
    if with_images:
        cloudflare = CloudflareTransport()
        reference_review = orchestrator.generate_images(
            stage,
            source_input=source_text,
            condition_set=build_visual_condition_set(
                source_input=source_text,
                drafts=(VisualConditionDraft(source_phrase="黒い", strength="required"),),
            ),
            policy=backend_policy(),
            usage_ledger=ledger,
            account_id=ACCOUNT_ID,
            api_token="fixture-cloudflare-token",
            transport=cloudflare,
            now=clock,
        )
        assert reference_review.status == "reference_review"
        assert len(cloudflare.calls) == 1
        image_review = orchestrator.approve_reference_image(
            reference_review,
            human_confirmed=True,
            policy=backend_policy(),
            usage_ledger=ledger,
            account_id=ACCOUNT_ID,
            api_token="fixture-cloudflare-token",
            transport=cloudflare,
            now=clock,
        )
        assert isinstance(image_review, orchestrator.ImageReview)
        assert len(cloudflare.calls) == 2
        review = orchestrator.accept_images(
            image_review,
            postal_code="100-0001",
            policy=backend_policy(),
            usage_ledger=ledger,
            now=clock,
        )
    else:
        review = orchestrator.skip_images(
            stage,
            postal_code="100-0001",
            policy=backend_policy(),
            usage_ledger=ledger,
            now=clock,
        )
    approved = orchestrator.approve_search(review, now=clock)
    response: OutscraperHttpResponse | Exception
    if failed:
        response = RuntimeError("raw provider failure")
    else:
        response = outscraper_response(
            review.query_plan.queries[0].value,
            empty=empty,
            product_title=product_title,
            product_color=product_color,
        )
    outscraper = OutscraperTransport(response)
    result = orchestrator.run_search(
        approved,
        usage_ledger=ledger,
        approval_ledger=InMemoryApprovalLedger(),
        api_key="fixture-outscraper-key",
        transport=outscraper,
        now=clock,
        sleep=lambda _seconds: None,
    )
    return CompletedContext(
        source_text=source_text,
        review=review,
        result=result,
        bonsai=bonsai,
        cloudflare=cloudflare,
        outscraper=outscraper,
    )


def test_results_are_converted_to_public_snapshot_and_saved_idempotently(tmp_path) -> None:
    context = complete_context()
    before_calls = context.provider_call_counts

    pending = history_snapshot.build_history_snapshot(
        context.source_text,
        review=context.review,
        result=context.result,
    )

    assert pending.schema_version == "2.0"
    assert pending.ranking_profile_id == "typed-ranking-v4"
    assert pending.owner_id == "owner-1"
    assert pending.completed_at == context.result.session.updated_at
    assert pending.summary == "ヘッドホン"
    assert pending.source_text == SOURCE_TEXT
    assert pending.condition_snapshot.product_type == "ヘッドホン"
    assert pending.condition_snapshot.conditions == ("必須: 色: 黒",)
    assert pending.condition_snapshot.price_summary == "50,000円以内"
    assert pending.reference_image_mode == "off"
    assert pending.reference_images == ()
    assert pending.candidate_limit == 48
    assert pending.outcome == "results"
    assert len(pending.result_snapshot) == 1
    product = pending.result_snapshot[0]
    assert product.schema_version == "2.0"
    assert product.required_status == "confirmed"
    ranked = context.result.ranked_batch.products[0]
    assert product.rank == 1
    assert product.title == "Sony 黒 軽量 ワイヤレスヘッドホン"
    assert product.image_url == "https://images.example.test/product.jpg"
    assert product.price_jpy == 40_000
    assert product.description == "軽量でノイズキャンセリングに対応したワイヤレスヘッドホンです。"
    assert product.product_url == "https://www.amazon.co.jp/dp/B012345678"
    assert product.matching_points == ("一致: 必須: 色: 黒",)
    assert product.unverified_points == ()
    assert product.caution_points == ranked.breakdown.negative_matches
    assert product.match_summary == "必須条件を確認できました"
    assert product.image_comparison_note == "画像を使わずに比較しました"
    assert set(product.model_dump()) == {
        "schema_version",
        "rank",
        "title",
        "image_url",
        "price_jpy",
        "description",
        "product_url",
        "required_status",
        "match_summary",
        "matching_points",
        "unverified_points",
        "caution_points",
        "image_comparison_note",
    }

    repository = SqliteSearchHistoryRepository(tmp_path / "history.sqlite3")
    first = history_snapshot.save_completed_history(
        context.source_text,
        review=context.review,
        result=context.result,
        repository=repository,
        now=context.result.session.updated_at,
    )
    second = history_snapshot.save_completed_history(
        context.source_text,
        review=context.review,
        result=context.result,
        repository=repository,
        now=context.result.session.updated_at + timedelta(minutes=1),
    )

    assert second == first
    assert len(repository.list(owner_id="owner-1", now=context.result.session.updated_at)) == 1
    assert context.provider_call_counts == before_calls
    public = first.model_dump(mode="json")
    assert not {
        "owner_id",
        "completion_key",
        "provider",
        "model_id",
        "postal_code",
        "token",
        "raw_score",
    }.intersection(public)


def test_typed_decisions_drive_required_status_and_public_explanations() -> None:
    contradicted = complete_context(
        product_title="Sony 白 軽量 ワイヤレスヘッドホン",
        product_color="白",
    )
    contradicted_snapshot = history_snapshot.build_history_snapshot(
        contradicted.source_text,
        review=contradicted.review,
        result=contradicted.result,
    ).result_snapshot[0]

    assert contradicted_snapshot.required_status == "contradicted"
    assert contradicted_snapshot.matching_points == ()
    assert contradicted_snapshot.unverified_points == ()
    assert contradicted_snapshot.caution_points == ("不一致: 必須: 色: 黒",)
    assert contradicted_snapshot.match_summary == "必須条件に合わない点があります"

    uncertain = complete_context(
        session_id="session-unknown-color",
        product_title="Sony 軽量 ワイヤレスヘッドホン",
        product_color=None,
    )
    uncertain_snapshot = history_snapshot.build_history_snapshot(
        uncertain.source_text,
        review=uncertain.review,
        result=uncertain.result,
    ).result_snapshot[0]

    assert uncertain_snapshot.required_status == "uncertain"
    assert uncertain_snapshot.matching_points == ()
    assert uncertain_snapshot.unverified_points == ("未確認: 必須: 色: 黒",)
    assert uncertain_snapshot.caution_points == ()
    assert uncertain_snapshot.match_summary == "必須条件の一部を確認できません"


def test_normal_empty_result_is_saved_but_failed_result_is_rejected(tmp_path) -> None:
    empty = complete_context(empty=True)
    repository = SqliteSearchHistoryRepository(tmp_path / "history.sqlite3")

    saved = history_snapshot.save_completed_history(
        empty.source_text,
        review=empty.review,
        result=empty.result,
        repository=repository,
        now=empty.result.session.updated_at,
    )

    assert saved.outcome == "empty"
    assert saved.compared_count == 0
    assert saved.result_snapshot == ()

    failed = complete_context(failed=True, session_id="session-failed")
    with pytest.raises(
        history_snapshot.HistorySnapshotError,
        match="^Completed search history inputs are invalid$",
    ):
        history_snapshot.save_completed_history(
            failed.source_text,
            review=failed.review,
            result=failed.result,
            repository=repository,
            now=failed.result.session.updated_at,
        )

    assert len(repository.list(owner_id="owner-1", now=failed.result.session.updated_at)) == 1


def test_approved_reference_is_saved_without_four_generated_views(tmp_path) -> None:
    context = complete_context(with_images=True)
    assert context.review.image_review is not None

    pending = history_snapshot.build_history_snapshot(
        context.source_text,
        review=context.review,
        result=context.result,
    )

    source_image = context.review.image_review.reference_review.image
    assert pending.reference_image_mode == "on"
    assert pending.schema_version == "3.0"
    assert len(pending.reference_images) == 1
    assert pending.reference_images[0].body == source_image.body
    assert pending.result_snapshot[0].image_comparison_note == (
        "参考画像は保存されていますが、商品の順位付けには使っていません"
    )

    saved = history_snapshot.save_completed_history(
        context.source_text,
        review=context.review,
        result=context.result,
        repository=SqliteSearchHistoryRepository(tmp_path / "history.sqlite3"),
        now=context.result.session.updated_at,
    )
    assert len(saved.reference_images) == 1
    assert saved.schema_version == "3.0"


def test_source_text_is_exactly_bound_before_display_normalization() -> None:
    source_text = "  Sony　WH-1000XM5の黒いヘッドホンを\n5万円以内で  "
    context = complete_context(source_text=source_text)

    pending = history_snapshot.build_history_snapshot(
        source_text,
        review=context.review,
        result=context.result,
    )

    assert pending.source_text == "Sony WH-1000XM5の黒いヘッドホンを 5万円以内で"
    with pytest.raises(
        history_snapshot.HistorySnapshotError,
        match="^Completed search history inputs are invalid$",
    ):
        history_snapshot.build_history_snapshot(
            pending.source_text,
            review=context.review,
            result=context.result,
        )


def test_different_review_owner_or_session_is_rejected_before_save(tmp_path) -> None:
    context = complete_context()
    other = complete_context(owner_id="owner-2", session_id="session-2")
    repository = SqliteSearchHistoryRepository(tmp_path / "history.sqlite3")

    with pytest.raises(
        history_snapshot.HistorySnapshotError,
        match="^Completed search history inputs are invalid$",
    ):
        history_snapshot.save_completed_history(
            context.source_text,
            review=other.review,
            result=context.result,
            repository=repository,
            now=context.result.session.updated_at,
        )

    assert repository.list(owner_id="owner-1", now=context.result.session.updated_at) == ()
    assert repository.list(owner_id="owner-2", now=context.result.session.updated_at) == ()


def test_ranked_product_not_in_normalized_batch_is_rejected() -> None:
    context = complete_context()
    other = complete_context(product_title="Sony 別の商品")
    assert context.result.ranked_batch is not None
    assert other.result.ranked_batch is not None
    assert context.result.normalized_batch is not None

    first = context.result.ranked_batch.products[0].model_copy(
        update={"product": other.result.ranked_batch.products[0].product}
    )
    tampered_batch = context.result.ranked_batch.model_copy(update={"products": (first,)})
    tampered = ProductSearchPipelineResult.model_construct(
        schema_version="3.0",
        outcome="results",
        session=context.result.session,
        normalized_batch=context.result.normalized_batch,
        ranked_batch=tampered_batch,
    )

    with pytest.raises(
        history_snapshot.HistorySnapshotError,
        match="^Completed search history inputs are invalid$",
    ):
        history_snapshot.build_history_snapshot(
            context.source_text,
            review=context.review,
            result=tampered,
        )


def test_storage_failure_keeps_completed_result_retriable_without_provider_calls(tmp_path) -> None:
    context = complete_context()
    repository = SqliteSearchHistoryRepository(tmp_path / "history.sqlite3")
    before_result = context.result.model_dump(mode="json")
    before_calls = context.provider_call_counts
    with sqlite3.connect(repository.path) as connection:
        connection.execute(
            """
            CREATE TRIGGER block_history_snapshot_insert
            BEFORE INSERT ON search_history
            BEGIN
                SELECT RAISE(ABORT, 'blocked');
            END
            """
        )

    with pytest.raises(HistoryStorageError, match="^Search history storage operation failed$"):
        history_snapshot.save_completed_history(
            context.source_text,
            review=context.review,
            result=context.result,
            repository=repository,
            now=context.result.session.updated_at,
        )

    assert context.result.model_dump(mode="json") == before_result
    assert context.provider_call_counts == before_calls
    with sqlite3.connect(repository.path) as connection:
        connection.execute("DROP TRIGGER block_history_snapshot_insert")

    saved = history_snapshot.save_completed_history(
        context.source_text,
        review=context.review,
        result=context.result,
        repository=repository,
        now=context.result.session.updated_at + timedelta(minutes=1),
    )
    assert saved.compared_count == 1
    assert context.provider_call_counts == before_calls


def test_history_snapshot_boundary_has_no_credential_or_provider_execution_api() -> None:
    source = Path("src/search_v2/history_snapshot.py")
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    parameters = set(inspect.signature(history_snapshot.save_completed_history).parameters)

    assert "openai" not in imports
    assert "src.search_v2.bonsai_http" not in imports
    assert "src.search_v2.cloudflare_http" not in imports
    assert "src.search_v2.outscraper_http" not in imports
    assert not {"api_key", "api_token", "credential", "approval_token"}.intersection(parameters)
