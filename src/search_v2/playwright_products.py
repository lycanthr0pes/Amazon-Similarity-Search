"""Anonymous local browser retrieval, bounded IPC and one-shot candidate binding."""

import json
import os
from pathlib import Path
from queue import Empty, Queue
import secrets
import shutil
import signal
import subprocess
from threading import Lock, Thread

from src.search_v2.product_request import PlaywrightSearchRequest, product_request_sha256


MAX_RESPONSE_BYTES = 8 * 1024 * 1024
WORKER_STEP_TIMEOUT = 50
_BROWSER_LOCK = Lock()


class ProductFetchError(RuntimeError):
    """Fixed failure codes; page bodies and browser exceptions never reach logs."""


def worker_environment():
    names = ("PATH", "HOME", "USERPROFILE", "LOCALAPPDATA", "SYSTEMROOT", "TEMP", "TMPDIR")
    return {name: os.environ[name] for name in names if name in os.environ}


def _read_events(stream, events):
    while True:
        line = stream.readline(MAX_RESPONSE_BYTES + 1)
        if not line:
            events.put(None)
            return
        if len(line) > MAX_RESPONSE_BYTES:
            events.put(False)
            return
        events.put(line)


def _stop_worker(process):
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # The browser and its owner already exited normally.
    elif process.poll() is None:
        process.kill()
    process.wait(timeout=10)


def run_product_worker(payload, *, progress=None):
    node = shutil.which("node")
    if node is None:
        raise ProductFetchError("Playwright Node runtime is unavailable")
    script = Path(__file__).resolve().parents[2] / "tools" / "playwright_products_worker.mjs"
    # One browser job per host process. No query or credential appears in argv.
    with _BROWSER_LOCK:
        process = subprocess.Popen(
            [node, str(script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=worker_environment(),
            start_new_session=os.name == "posix",
        )
        events = Queue()
        reader = Thread(target=_read_events, args=(process.stdout, events), daemon=True)
        reader.start()
        try:
            process.stdin.write(json.dumps(payload, ensure_ascii=False).encode())
            process.stdin.close()
            detail_steps = 2 if payload.get("englishTitles") else 1
            maximum_events = (payload["limit"] * detail_steps + 3) * len(payload["queries"]) + 3
            for _ in range(maximum_events):
                try:
                    line = events.get(timeout=WORKER_STEP_TIMEOUT)
                except Empty:
                    raise ProductFetchError("Playwright page step timed out") from None
                if not line:
                    raise ProductFetchError("Playwright worker did not complete")
                event = json.loads(line)
                if event == {"event": "progress", "phase": "details"}:
                    if progress is not None:
                        progress(1)
                    continue
                if event == {"event": "progress"}:
                    continue
                if event.get("event") == "result" and set(event) == {"event", "result"}:
                    process.wait(timeout=10)
                    if process.returncode != 0:
                        raise ProductFetchError("Playwright worker failed")
                    return event["result"]
                if event.get("event") == "error" and event.get("code") in {
                    "input_limit",
                    "input_contract",
                    "response_limit",
                    "page_unavailable",
                    "challenge",
                    "search_contract",
                    "product_contract",
                    "browser_failure",
                }:
                    raise ProductFetchError("Playwright retrieval failed: " + event["code"])
                raise ProductFetchError("Playwright page could not be retrieved")
            raise ProductFetchError("Playwright worker exceeded its page limit")
        except ProductFetchError:
            raise
        except Exception:
            raise ProductFetchError("Playwright worker failed") from None
        finally:
            _stop_worker(process)
            reader.join(timeout=2)
            process.stdout.close()


def fetch_product_data(
    queries, *, limit=24, worker=None, english_titles=True, english_details=True, progress=None
):
    if (
        type(queries) is not list
        or not 1 <= len(queries) <= 2
        or any(
            type(q) is not str or not q.strip() or q != q.strip() or len(q) > 200 for q in queries
        )
        or type(limit) is not int
        or not 1 <= limit <= 100
        or type(english_details) is not bool
        or type(english_titles) is not bool
    ):
        raise ValueError("Invalid Playwright product request")
    try:
        payload = {"queries": queries, "limit": limit}
        if english_titles:
            payload["englishTitles"] = True
            if english_details:
                payload["englishDetails"] = True
        result = (worker or run_product_worker)(
            payload, **({"progress": progress} if progress is not None else {})
        )
        if type(result) is not dict or set(result) != {"data", "metrics"}:
            raise ValueError
        metrics = result["metrics"]
        if type(metrics) is not dict or any(
            key
            not in {
                "search_pages",
                "detail_pages",
                "english_detail_pages",
                "requests_allowed",
                "requests_blocked",
            }
            or type(value) is not int
            or value < 0
            for key, value in metrics.items()
        ):
            raise ValueError
        groups = result["data"]
        if type(groups) is not list or len(groups) != len(queries):
            raise ValueError
        for index, group in enumerate(groups):
            if type(group) is not list or len(group) > limit:
                raise ValueError
            for product in group:
                if (
                    type(product) is not dict
                    or product.get("query", queries[index]) != queries[index]
                ):
                    raise ValueError
        if len(json.dumps(result).encode()) > MAX_RESPONSE_BYTES:
            raise ValueError
        return result
    except ProductFetchError:
        raise
    except Exception:
        raise ProductFetchError("Playwright product response is invalid") from None


class PlaywrightProducts:
    def __init__(self, request, *, worker=None, progress=None):
        self.request = PlaywrightSearchRequest.model_validate(request)
        self._worker = worker
        self._progress = progress
        self._lock = Lock()
        self._used = False
        self.metrics = {}

    def fetch(self, request):
        from src.search_v2.candidate_search import FetchedCandidates

        validated = PlaywrightSearchRequest.model_validate(request)
        with self._lock:
            if self._used or validated != self.request:
                raise ValueError("Playwright request is already used or does not match")
            self._used = True
        result = fetch_product_data(
            list(validated.provider_queries()),
            limit=validated.limit_per_query,
            worker=self._worker,
            english_titles=validated.english_titles is True,
            english_details=validated.english_details is True,
            progress=self._progress,
        )
        self.metrics = result["metrics"]
        return FetchedCandidates(
            product_request_sha256(validated),
            "playwright-" + secrets.token_hex(16),
            {"data": result["data"]},
        )
