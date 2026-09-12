"""Local browser fixture with real candidate scoring and temporary SQLite history."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import test_search_v2_orchestrator as fixtures
from src.search_v2.browser_candidate import BrowserCandidateRun, candidate_browser_steps
from src.search_v2.browser_history import BrowserHistory
from src.search_v2.browser_search import BrowserSearch
from src.search_v2.candidate_flow import CandidateSearchFlow
from src.search_v2.candidate_search import FetchedCandidates
from src.search_v2.condition_terms import LocalConditionExpander
from src.search_v2.outscraper_contract import outscraper_request_sha256
from src.search_v2.provisional_history_repository import SqliteProvisionalHistoryRepository
from tools.browser_search_server import make_server


def main():
    def forbidden(*args, **kwargs):
        raise AssertionError("Image services must stay uncalled")

    def now():
        return datetime.now(timezone.utc)

    def fetch(request):
        return FetchedCandidates(
            outscraper_request_sha256(request),
            "fixture-task",
            {
                "data": [
                    {
                        "name": "合成マグカップ",
                        "price": 2000,
                        "rating": 4.0,
                        "image_1": "https://m.media-amazon.com/images/fixture.png",
                        "query": request.provider_queries()[0],
                    }
                ]
            },
        )

    with (
        TemporaryDirectory(prefix="ae-image-free-fixture-") as directory,
        ThreadPoolExecutor(max_workers=1) as worker,
    ):
        history = SqliteProvisionalHistoryRepository(Path(directory) / "history.sqlite3")

        def steps(source, attempt, *, image_mode="on"):
            flow = CandidateSearchFlow(
                source,
                owner_id="local-user",
                session_id=f"fixture-{attempt}",
                postal_code="100-0001",
                policy=fixtures.backend_policy(),
                usage_ledger=fixtures.usage_ledger(),
                approval_repository=None,
                history_repository=history,
                image_transport=None,
                account_id=None,
                api_token=None,
                image_settings=forbidden,
                now=now,
                visual_extractor=None,
                allow_image_free=True,
                image_mode=image_mode,
                plan_lifetime=None,
                condition_expander=LocalConditionExpander(),
            )
            yield from candidate_browser_steps(
                flow,
                owner="local-user",
                images=None,
                products=lambda _: SimpleNamespace(fetch=fetch),
                history=history,
                now=now,
                proxy=None,
                assets=None,
                encoder=None,
                image_evaluator=forbidden,
                thumbnail_factory=lambda: SimpleNamespace(
                    fetch_image=lambda _: SimpleNamespace(
                        width=1, height=1, rgb_bytes=b"\xff\xff\xff"
                    )
                ),
                progress=run.progress,
            )

        run = BrowserCandidateRun(factory=steps)
        controller = BrowserSearch(
            run.execute,
            worker,
            initial={
                "mode": "fixture",
                "editable": True,
                "historyAvailable": True,
                "input": "マグカップ。3000円以下。取っ手がなくてもよい。",
            },
        )
        run.progress = controller.progress
        server = make_server(
            controller,
            Path("frontend/dist"),
            port=8764,
            history=BrowserHistory([Path(directory) / "history.sqlite3"]),
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            worker.submit(run.close).result()


if __name__ == "__main__":
    main()
