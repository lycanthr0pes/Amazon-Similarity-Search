"""Single-worker browser commands over a server-owned staged search."""

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
import re
from uuid import uuid4

from src.search_v2.product_links import japanese_product_url


class BrowserCancelled(Exception):
    """A cooperative stop before the next search phase."""


class BrowserModelBusy(Exception):
    """Preparation could not acquire its local model runtime."""


class BrowserCommandError(ValueError):
    def __init__(self):
        super().__init__("Search command is invalid or no longer available")


def validate_browser_source(source):
    if (
        type(source) is not str
        or not 0 < len(source) <= 2000
        or not source.strip()
        or any(ord(char) < 32 and char not in "\n\r\t" for char in source)
    ):
        raise BrowserCommandError()
    try:
        source.encode("utf-8")
    except UnicodeError:
        raise BrowserCommandError() from None
    return source


_ACTIONS = {
    "idle": "start",
    "query": "reference",
    "reference": "comparison",
    "comparison": "final",
    "final": "search",
    "attributes": "rank",
}


class BrowserSearch:
    """Keep requests in memory; duplicate commands never repeat provider calls."""

    def __init__(self, execute, worker, *, initial=None):
        self._execute = execute
        self._worker = worker
        self._lock = RLock()
        self._instance_id = uuid4().hex
        self._view = {"stage": "idle", "revision": 0, **(initial or {})}
        self._commands = {}
        self._deadline = None
        self._editable = self._view.get("editable") is True
        self._preparations = 0
        self._cancel_requested = False

    def _expire(self):
        if (
            self._deadline is not None
            and datetime.now(timezone.utc) >= self._deadline
            and self._view["stage"] in _ACTIONS
            and self._view["stage"] != "idle"
        ):
            self._view.update(
                stage="expired",
                revision=self._view["revision"] + 1,
                message="確認の期限が切れました。今回の実行は終了しています。",
            )

    def snapshot(self):
        with self._lock:
            self._expire()
            view = deepcopy(self._view)
            view["instanceId"] = self._instance_id
            if self._editable:
                view["canRevise"] = (
                    view["stage"]
                    in {
                        "query",
                        "clarification",
                        "reference",
                        "comparison",
                        "final",
                        "failed",
                        "expired",
                        "cancelled",
                    }
                    and self._preparations < 3
                )
            view["canReset"] = self._editable and view["stage"] != "working"
            for product in view.get("products", []):
                product["url"] = japanese_product_url(product.get("url"))
            return view

    def progress(self, step, *, during_fetch=False):
        with self._lock:
            if self._cancel_requested and not during_fetch:
                raise BrowserCancelled()
            self._view.update(
                researchStep=step,
                canCancel=(step == 0 or during_fetch) and not self._cancel_requested,
                revision=self._view["revision"] + 1,
            )

    def submit(self, command):
        if type(command) is not dict:
            raise BrowserCommandError()
        action = command.get("action")
        envelope = {"action", "revision", "operation"}
        if "instanceId" in command:
            if command["instanceId"] != self._instance_id:
                raise BrowserCommandError()
            envelope.add("instanceId")
        extra = (
            {"source"}
            if self._editable and action in {"start", "revise"}
            else {"index"}
            if action in {"reference", "without_images"}
            else {"selections"}
            if action == "rank"
            else set()
        )
        prompt_field = (
            "prompt"
            if action in {"reference", "regenerate"}
            else "prompts"
            if action in {"comparison", "regenerate_comparisons"}
            else None
        )
        if prompt_field and prompt_field in command:
            from src.search_v2.counterfactual_cloudflare_request import validate_image_prompt

            value = command[prompt_field]
            try:
                if prompt_field == "prompt":
                    validate_image_prompt(value)
                else:
                    if (
                        type(value) is not dict
                        or len(value) > 3
                        or any(type(k) is not str for k in value)
                    ):
                        raise ValueError()
                    for prompt in value.values():
                        validate_image_prompt(prompt)
            except (ValueError, TypeError):
                raise BrowserCommandError() from None
            extra = extra | {prompt_field}
        if "source" in extra and "imageMode" in command:
            if type(command["imageMode"]) is not str or command["imageMode"] not in {"on", "off"}:
                raise BrowserCommandError()
            extra = extra | {"imageMode"}
        if (
            set(command) != envelope | extra
            or type(command.get("revision")) is not int
            or type(command.get("operation")) is not str
            or not re.fullmatch(r"[A-Za-z0-9_-]{12,80}", command["operation"])
            or type(action) is not str
            or (
                action in {"reference", "without_images"}
                and (type(command["index"]) is not int or not 0 <= command["index"] < 8)
            )
            or (
                action == "rank"
                and (
                    type(command["selections"]) is not dict
                    or len(command["selections"]) > 16
                    or any(
                        type(k) is not str or type(v) is not str or len(k) > 100 or len(v) > 100
                        for k, v in command["selections"].items()
                    )
                )
            )
        ):
            raise BrowserCommandError()
        if "source" in extra:
            validate_browser_source(command["source"])
        with self._lock:
            self._expire()
            previous = self._commands.get(command["operation"])
            if previous is not None:
                if previous != command:
                    raise BrowserCommandError()
                return self.snapshot()
            if "prompts" in extra and not set(command["prompts"]) <= set(
                self._view.get("imagePrompts", {}).get("comparison", {})
            ):
                raise BrowserCommandError()
            if action == "cancel":
                if (
                    command["revision"] != self._view["revision"]
                    or self._view.get("canCancel") is not True
                    or self._view["stage"] != "working"
                ):
                    raise BrowserCommandError()
                self._commands[command["operation"]] = deepcopy(command)
                self._cancel_requested = True
                self._view.update(cancelRequested=True, canCancel=False)
                return self.snapshot()
            if (
                command["revision"] != self._view["revision"]
                or not (
                    (
                        _ACTIONS.get(self._view["stage"]) == action
                        and not (
                            action == "reference" and self._view.get("canGenerateImages") is False
                        )
                    )
                    or (
                        action == "without_images"
                        and self._view.get("canSkipImages") is True
                        and self._view["stage"]
                        in {"query", "reference", "comparison", "final", "expired", "failed"}
                    )
                    or (
                        self._editable
                        and action == "revise"
                        and self.snapshot().get("canRevise") is True
                    )
                    or (action == "reset" and self._editable and self._view["stage"] != "working")
                    or (
                        action == "regenerate"
                        and self._view.get("canRegenerate") is True
                        and self._view["stage"]
                        in {"reference", "comparison", "final", "failed", "expired"}
                    )
                    or (
                        action == "regenerate_comparisons"
                        and self._view.get("canRegenerateComparisons") is True
                        and self._view["stage"] in {"comparison", "final", "failed"}
                    )
                    or (
                        action == "retry_save"
                        and self._view.get("canRetrySave") is True
                        and self._view["stage"] == "complete"
                    )
                )
                or (action in {"start", "revise"} and self._preparations >= 3)
                or (action != "reset" and len(self._commands) >= 32)
            ):
                raise BrowserCommandError()
            if action == "reset":
                self._commands.clear()
                self._preparations = 0
                self._deadline = None
            self._commands[command["operation"]] = deepcopy(command)
            if "source" in extra:
                self._preparations += 1
                self._view = {
                    key: value
                    for key, value in self._view.items()
                    if key in {"mode", "editable", "revision", "historyAvailable"}
                }
                self._view["input"] = command["source"]
            self._cancel_requested = False
            self._view.update(
                stage="working",
                revision=self._view["revision"] + 1,
                workingAction=action,
                canCancel=False,
                cancelRequested=False,
            )
            if action == "retry_save":
                self._view["researchStep"] = 4
            if action in {"search", "rank"}:
                self._view["researchStep"] = 0 if action == "search" else 2
            self._worker.submit(self._run, action, {key: command[key] for key in extra})
            return self.snapshot()

    def _run(self, action, values):
        deadline = None
        try:
            view = self._execute(action, values)
            if "expiresAt" in view:
                deadline = datetime.fromisoformat(view["expiresAt"])
                if deadline.tzinfo is None:
                    raise ValueError("Confirmation expiry must have a timezone")
        except BrowserCancelled:
            view = {
                "stage": "cancelled",
                "canSkipImages": False,
                "message": "検索を中止しました。取得後の比較と保存は行っていません。",
            }
        except BrowserModelBusy:
            view = {
                "stage": "failed",
                "canSkipImages": False,
                "message": "Bonsaiが別の処理で使用中のため、条件を整理できませんでした。"
                "その処理の終了後に、もう一度条件を整理してください。",
            }
        except Exception:
            deadline = None
            view = {
                "stage": "failed",
                "canSkipImages": False,
                "message": "処理を完了できませんでした。実行を停止しました。",
            }
        with self._lock:
            self._deadline = deadline
            if action == "reset":
                self._view = {
                    key: value
                    for key, value in self._view.items()
                    if key in {"revision", "mode", "editable", "historyAvailable"}
                }
                view = {"stage": "idle", "input": ""}
            self._view.update(view)
            self._view["canCancel"] = False
            self._view.pop("workingAction", None)
            self._view.pop("cancelRequested", None)
            if deadline is not None:
                self._view["expiresAt"] = deadline.isoformat()
            else:
                self._view.pop("expiresAt", None)
            self._expire()
