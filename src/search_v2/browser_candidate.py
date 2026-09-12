"""Display projections and explicit browser stops for candidate image search."""

import base64
from dataclasses import replace
from io import BytesIO

from PIL import Image

from src.search_v2.counterfactual_cloudflare_http import _artifact
from src.search_v2.browser_search import validate_browser_source
from src.search_v2.browser_history import history_product
from src.search_v2.history_content import HistoryContent
from src.search_v2.condition_language import ConditionExpression
from src.search_v2.candidate_title import title_metadata
from src.search_v2.tokenizer import _analyze_japanese_source
from src.search_v2.candidate_diagnostics import CandidatePreparationError
from src.search_v2.condition_language import (
    analyze_conditions,
    display_conditions,
    display_issues,
    original_range,
    ConditionLanguageError,
)


MAX_BROWSER_IMAGE_SETS = 2
MAX_BROWSER_IMAGE_CALLS = MAX_BROWSER_IMAGE_SETS * 4


class BrowserImages:
    """Retain validated preview images in memory without recording HTTP bodies."""

    def __init__(self, transport):
        self._transport = transport
        self._calls = 0
        self.images = []

    def post_multipart(self, **kwargs):
        if self._calls >= MAX_BROWSER_IMAGE_CALLS:
            raise ValueError("Browser image execution limit reached")
        self._calls += 1
        response = self._transport.post_multipart(**kwargs)
        response = replace(response, body_chunks=tuple(response.body_chunks))
        image = _artifact(kwargs["request"], response)
        self.images.append(image.body)
        return response

    def previews(self):
        return [
            "data:image/png;base64," + base64.b64encode(body).decode("ascii")
            for body in self.images
        ]


class BrowserProductImages:
    """Reuse bounded, proxy-decoded images for display without another request."""

    def __init__(self, inner):
        self.inner = inner
        self._previews = {}
        self._display_attempts = set()

    def fetch_image(self, url):
        result = self.inner.fetch_image(url)
        if len(self._previews) < 24:
            try:
                image = Image.frombytes("RGB", (result.width, result.height), result.rgb_bytes)
                image.thumbnail((192, 192))
                buffer = BytesIO()
                image.save(buffer, format="PNG")
                self._previews[url] = (
                    "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
                )
            except (OSError, ValueError):
                pass  # Thumbnail failure does not discard a usable evaluation image.
        return result

    def load_previews(self, url_groups):
        attempted = self._display_attempts
        for urls in url_groups:
            if not urls or urls[0] in attempted:
                continue
            if len(attempted) >= 24:
                break
            url = urls[0]
            attempted.add(url)
            if url in self._previews:
                continue
            try:
                self.fetch_image(url)
            except Exception:
                pass  # Display-only failures must not discard text ranking or history.

    def preview(self, urls):
        return self._previews.get(urls[0]) if urls else None


class BrowserCandidateRun:
    def __init__(self, steps=None, *, factory=None):
        if (steps is None) == (factory is None):
            raise ValueError("Provide steps or an editable factory")
        self._steps = steps
        self._factory = factory
        self._attempt = 0
        self._preparations = 0
        self.progress = None
        self._stage = "idle"
        self._started = False

    def execute(self, action, values):
        if action == "reset" and self._factory is not None:
            self.close()
            self._steps = None
            self._started = False
            self._stage = "idle"
            self._preparations = 0
            return {"stage": "idle", "input": ""}
        if self._factory is not None and action in {"start", "revise"}:
            source = validate_browser_source(values.get("source"))
            if (
                self._preparations >= 3
                or (
                    action == "revise"
                    and self._stage
                    not in {
                        "query",
                        "clarification",
                        "reference",
                        "comparison",
                        "final",
                        "failed",
                        "expired",
                        "cancelled",
                    }
                )
                or (action == "start" and self._started)
            ):
                raise ValueError("Input editing is not available")
            self.close()
            attempt = self._attempt
            self._attempt += 1
            self._preparations += 1
            self._started = True
            try:
                analyze_conditions(source)
                self._steps = self._factory(
                    source,
                    attempt,
                    **({"image_mode": values["imageMode"]} if "imageMode" in values else {}),
                )
                view = next(self._steps)
            except ConditionLanguageError as error:
                view = {
                    "stage": "clarification",
                    "message": "条件の句が多すぎます。文章を短くしてください。"
                    if any(issue["code"] == "condition_count" for issue in error.issues)
                    else "希望・否定の意味を確定できません。該当箇所を書き直してください。",
                    "conditionIssues": display_issues(source, error.issues),
                }
            except CandidatePreparationError as error:
                if error.diagnostic.code not in {
                    "empty_conditions",
                    "query_build",
                    "product_scope",
                    "contrast_proposal",
                    "needs_clarification",
                }:
                    self._stage = "failed"
                    raise
                message = (
                    "比較する見た目の条件がありません。画像なし対応の接続経路を使用するか、文章を修正してください。"
                    if error.diagnostic.code == "empty_conditions"
                    else "比較画像で変える見た目を確定できません。形・色・表面などを具体的に書き直してください。"
                    if error.diagnostic.code in {"contrast_proposal", "needs_clarification"}
                    else "商品の種類と条件の範囲を確定できません。文章を区切り、数値条件には項目名を添えてください。"
                )
                view = {
                    "stage": "clarification",
                    "message": message,
                    "conditionReview": display_conditions(source),
                }
                if error.diagnostic.code not in {
                    "empty_conditions",
                    "contrast_proposal",
                    "needs_clarification",
                }:
                    view["conditionIssues"] = [
                        {"start": 0, "end": len(source), "quote": source, "code": "modifier_scope"}
                    ]
            except Exception:
                self._stage = "failed"
                raise
            if view["stage"] == "query" and "conditionReview" not in view:
                view["conditionReview"] = display_conditions(source, view.get("conditions", ()))
            self._stage = view["stage"]
            return view
        if not self._started:
            if action != "start":
                raise ValueError("Search has not started")
            self._started = True
            view = next(self._steps)
            self._stage = view["stage"]
            return view
        view = self._steps.send(
            {
                **values,
                **(
                    {"without_images": True}
                    if action == "without_images"
                    else {"regenerate": True}
                    if action == "regenerate"
                    else {"regenerate_comparisons": True}
                    if action == "regenerate_comparisons"
                    else {"retry_save": True}
                    if action == "retry_save"
                    else {}
                ),
            }
        )
        self._stage = view["stage"]
        if view["stage"] == "complete" and not view.get("canRetrySave"):
            self._steps.close()
        return view

    def close(self):
        if self._steps is not None:
            self._steps.close()


def candidate_browser_steps(
    flow,
    *,
    owner,
    images,
    products,
    history,
    now,
    proxy,
    assets,
    encoder,
    image_evaluator=None,
    thumbnail_factory=None,
    progress=None,
):
    plan = flow.plan

    def expiry(approval_expires=None):
        deadlines = [value for value in (plan.expires_at, approval_expires) if value is not None]
        return {"expiresAt": min(deadlines).isoformat()} if deadlines else {}

    visual = plan.visual_conditions.conditions if plan.visual_conditions else ()
    if len(visual) > 3 or plan.request.maximum_candidates != 24:
        raise CandidatePreparationError("empty_conditions")
    review = (
        display_conditions(
            flow._source,
            [c["source_quote"] for c in flow._candidate._conditions]
            + [c.source_phrase for c in visual],
            structure=plan.source_structure,
        )
        if plan.condition_language_profile
        else []
    )
    labels = {
        c["condition_id"]: c["label"] or c["source_quote"] for c in flow._candidate._conditions
    }
    labels.update({c.condition_id: c.source_phrase for c in visual})
    if plan.condition_terms is not None:
        labels.update({c.condition_id: c.source_ja for c in plan.condition_terms.conditions})
    content = HistoryContent(
        source_text=flow._source,
        condition_labels=labels,
        condition_review=tuple(ConditionExpression.model_validate(row) for row in review),
    )
    structure = plan.source_structure
    product_name = plan.title_comparison.product_name_ja
    spans = [(row["start"], row["end"]) for row in review]
    normalized = _analyze_japanese_source(flow._source).text
    _, metadata_quotes = title_metadata(normalized)
    for quote in metadata_quotes:
        left = normalized.index(quote)
        spans.append(original_range(flow._source, left, left + len(quote)))
    if structure is not None:
        left, right = original_range(flow._source, structure.product.start, structure.product.end)
        product_name = flow._source[left:right]
        spans.extend(
            original_range(flow._source, span.start, span.end) for span in structure.fragments
        )
    # Keep neutral clauses and explicit brand/model metadata when editing.
    merged = []
    for left, right in sorted(set(spans)):
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(right, merged[-1][1]))
        else:
            merged.append((left, right))
    clauses = [flow._source[left:right] for left, right in merged]
    condition_text = "。".join(clause.rstrip("。\n") for clause in clauses)
    if condition_text:
        condition_text += "。"
    selection = yield {
        "stage": "query",
        "productName": product_name,
        "conditionText": condition_text,
        "canSkipImages": True,
        "canGenerateImages": bool(visual) and plan.image_preparation != "text-only-v1",
        **({"imageMode": "off", "images": []} if plan.image_preparation == "text-only-v1" else {}),
        "referenceRemaining": MAX_BROWSER_IMAGE_SETS,
        "imagePrompts": flow.image_prompts,
        "queries": [query.value for query in plan.query_options],
        "conditionReview": review,
        "conditions": [condition.source_phrase for condition in visual],
        "conditionLabels": labels,
        **expiry(),
    }
    flow.select_search_query(owner_id=owner, plan_sha256=flow.plan_sha256, index=selection["index"])
    skip = selection.get("without_images") is True
    command = selection
    attempts = 0
    reference_preview = None
    while not skip:
        if attempts >= MAX_BROWSER_IMAGE_SETS:
            raise ValueError("Browser image set limit reached")
        attempts += 1
        remaining = MAX_BROWSER_IMAGE_SETS - attempts
        try:
            offset = len(images.previews())
            if command.get("regenerate_comparisons"):
                issued = flow.regenerate_comparisons(
                    owner_id=owner,
                    plan_sha256=flow.plan_sha256,
                    human_confirmed=True,
                    prompts=command.get("prompts"),
                )
                previews = [reference_preview] + images.previews()[offset:]
            else:
                reference = (
                    flow.regenerate_reference if attempts > 1 else flow.generate_reference
                )(
                    owner_id=owner,
                    plan_sha256=flow.plan_sha256,
                    human_confirmed=True,
                    prompt=command.get("prompt"),
                )
                reference_preview = images.previews()[offset]
                command = yield {
                    "stage": "reference",
                    "images": [reference_preview],
                    "selectedQuery": flow.plan.request.queries[0].value,
                    "canSkipImages": True,
                    "canRegenerate": remaining > 0,
                    "canRegenerateComparisons": False,
                    "referenceRemaining": remaining,
                    "imagePrompts": flow.image_prompts,
                    **expiry(),
                }
                if command.get("regenerate"):
                    continue
                skip = command.get("without_images") is True
                if skip:
                    break
                issued = flow.approve_reference(
                    owner_id=owner,
                    reference_sha256=reference.sha256,
                    human_confirmed=True,
                    prompts=command.get("prompts"),
                )
                previews = images.previews()[offset:]
            command = yield {
                "stage": "comparison",
                "images": previews,
                "canSkipImages": True,
                "canRegenerate": remaining > 0,
                "canRegenerateComparisons": remaining > 0,
                "referenceRemaining": remaining,
                "imagePrompts": flow.image_prompts,
                **expiry(issued.review.expires_at),
            }
            if command.get("regenerate") or command.get("regenerate_comparisons"):
                continue
            skip = command.get("without_images") is True
            if skip:
                break
            command = yield {
                "stage": "final",
                "canSkipImages": True,
                "canRegenerate": remaining > 0,
                "canRegenerateComparisons": remaining > 0,
                **expiry(issued.review.expires_at),
            }
            if command.get("regenerate") or command.get("regenerate_comparisons"):
                continue
            skip = command.get("without_images") is True
            if not skip:
                flow.approve_images(
                    owner_id=owner,
                    approval_id=issued.review.approval_id,
                    token=issued.token,
                    human_confirmed=True,
                )
            break
        except ValueError:
            if flow._state != "image_failed":
                raise
            command = yield {
                "stage": "failed",
                "canSkipImages": True,
                "canRegenerate": remaining > 0,
                "canRegenerateComparisons": remaining > 0 and flow._reference is not None,
                "referenceRemaining": remaining,
                "imagePrompts": flow.image_prompts,
                "images": [reference_preview] if flow._reference is not None else [],
                "message": (
                    "画像を準備できませんでした。作り直すか、画像なしで進めます。"
                    if remaining > 0
                    else "画像を準備できませんでした。作り直しの上限に達しました。条件へ戻るか、画像なしで進めます。"
                ),
                **expiry(),
            }
            if command.get("regenerate") or command.get("regenerate_comparisons"):
                continue
            if command.get("without_images") is not True:
                raise ValueError("Explicit image-free confirmation required")
            skip = True
    if skip:
        flow.skip_images(owner_id=owner, plan_sha256=flow.plan_sha256, human_confirmed=True)
        yield {
            "stage": "final",
            "imageMode": "off",
            "images": [],
            "canSkipImages": False,
            "canRegenerate": False,
            "canRegenerateComparisons": False,
            "imagePrompts": None,
            "selectedQuery": flow.plan.request.queries[0].value,
            **expiry(),
        }
    if progress is not None:
        progress(0)
    review = flow.approve_and_fetch(
        owner_id=owner, plan_sha256=flow.plan_sha256, transport=products(flow.plan.request)
    )
    if progress is not None:
        progress(1)
    selections = {}
    if review.unresolved:
        chosen = yield {
            "stage": "attributes",
            "unresolved": list(review.unresolved),
            "options": [
                {
                    "id": option.option_id,
                    "label": option.label,
                    "conditions": list(option.condition_ids),
                }
                for option in review.options
            ],
            **expiry(),
        }
        selections = chosen["selections"]
    if progress is not None:
        progress(2)
    flow.confirm(owner_id=owner, review_sha256=review.sha256, selections=selections)
    if not skip and image_evaluator is not None:
        proxy, assets, encoder = image_evaluator()
    display_proxy = thumbnail_factory() if skip and thumbnail_factory is not None else None
    thumbnails = BrowserProductImages(display_proxy) if display_proxy is not None else None
    if not skip:
        thumbnails = BrowserProductImages(proxy)
    if progress is not None:
        progress(3)
    try:
        completed = (
            flow.complete(
                owner_id=owner, proxy_service=thumbnails, history_content=content, progress=progress
            )
            if skip
            else flow.complete(
                owner_id=owner,
                proxy_service=thumbnails,
                asset_root=assets,
                encoder=encoder,
                history_content=content,
                progress=progress,
            )
        )
    except Exception:
        if flow._state != "history_pending":
            raise
        while True:
            command = yield {
                "stage": "complete",
                "saved": False,
                "canRetrySave": True,
                "canSkipImages": False,
                "canRegenerate": False,
                "canRegenerateComparisons": False,
                "imagePrompts": None,
                "message": "結果を履歴に保存できませんでした。結果はこの画面で確認できます。",
                **content.browser_fields(),
                **({"imageMode": "off", "images": []} if skip else {}),
                "sortProfile": flow._pending.sort_profile_id,
                "products": [history_product(p) for p in flow._pending.products],
            }
            if not command.get("retry_save"):
                raise ValueError("Explicit save retry required")
            try:
                completed = flow.retry_history(owner_id=owner)
                break
            except Exception:
                if flow._state != "history_pending":
                    raise
    if progress is not None:
        progress(4)
    detail = history.get(owner_id=owner, locator=completed.history.locator, now=now())
    if detail != completed.history:
        raise ValueError("History verification failed")
    yield {
        "stage": "complete",
        **detail.history_content.browser_fields(),
        "saved": True,
        "canRetrySave": False,
        "canRegenerate": False,
        "researchStep": 5,
        "canSkipImages": False,
        **({"imageMode": "off"} if skip else {}),
        "sortProfile": detail.sort_profile_id,
        "products": [
            {
                **history_product(product),
                "thumbnail": product.thumbnail_png,
            }
            for product in detail.products
        ],
    }
