"""Serve a built React UI and one explicitly enabled local search canary."""

from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
import argparse
import json
import mimetypes
import time
from pathlib import Path
from urllib.parse import urlsplit, unquote

from src.search_v2.browser_search import BrowserCommandError, BrowserSearch


MAX_COMMAND_BYTES = 160 * 1024


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate command field")
        value[key] = item
    return value


def make_server(controller, static_root, *, port=8765, history=None):
    from src.search_v2.browser_history import BrowserHistory
    from src.search_v2.provisional_history_repository import ProvisionalHistoryError

    history = history or BrowserHistory()
    root = Path(static_root).resolve(strict=True)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *_):
            pass  # Request paths and provider data do not belong in diagnostic logs.

        def _reply(self, status, body, content_type="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
            )
            self.end_headers()
            self.wfile.write(body)

        def _local(self):
            host = f"127.0.0.1:{self.server.server_port}"
            return (
                self.client_address[0] == "127.0.0.1"
                and self.headers.get_all("Host") == [host]
                and self.headers.get("Sec-Fetch-Site", "same-origin") in {"same-origin", "none"}
            )

        def do_GET(self):
            if not self._local():
                return self._reply(403, b"{}")
            path = unquote(urlsplit(self.path).path)
            if path == "/api/history" or path.startswith("/api/history/"):
                try:
                    view = (
                        history.list()
                        if path == "/api/history"
                        else history.get(path.removeprefix("/api/history/"))
                    )
                    return self._reply(200, json.dumps(view, ensure_ascii=False).encode())
                except LookupError:
                    return self._reply(404, b"{}")
                except (ProvisionalHistoryError, OSError, ValueError):
                    return self._reply(503, b"{}")
            if path == "/api/state":
                return self._reply(
                    200, json.dumps(controller.snapshot(), ensure_ascii=False).encode()
                )
            try:
                target = (root / ("index.html" if path == "/" else path.lstrip("/"))).resolve(
                    strict=True
                )
                if (
                    not target.is_relative_to(root)
                    or not target.is_file()
                    or any(part.startswith(".") for part in target.relative_to(root).parts)
                ):
                    return self._reply(404, b"{}")
                body = target.read_bytes()
                mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                return self._reply(200, body, mime)
            except (OSError, ValueError):
                return self._reply(404, b"{}")

        def do_POST(self):
            if (
                not self._local()
                or self.headers.get_all("Origin") != [f"http://127.0.0.1:{self.server.server_port}"]
                or self.headers.get("X-Amazon-Explorer-Browser") != "1"
            ):
                return self._reply(403, b"{}")
            if self.path not in {"/api/command", "/api/history/command"}:
                return self._reply(404, b"{}")
            try:
                lengths = self.headers.get_all("Content-Length", [])
                if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdecimal():
                    raise ValueError()
                size = int(lengths[0])
                if (
                    not 0 < size <= MAX_COMMAND_BYTES
                    or "Transfer-Encoding" in self.headers
                    or self.headers.get("Content-Type") != "application/json"
                ):
                    raise ValueError()
                command = json.loads(self.rfile.read(size), object_pairs_hook=_unique_object)
                if self.path == "/api/history/command":
                    if type(command) is not dict:
                        raise ValueError("Invalid history command")
                    if (
                        set(command) == {"action", "id", "confirmed"}
                        and command["action"] == "delete"
                        and command["confirmed"] is True
                    ):
                        history.delete(command["id"])
                        view = {"deleted": True}
                    elif command == {"action": "purge_expired"}:
                        view = {"deletedCount": history.purge_expired()}
                    else:
                        raise ValueError("Invalid history command")
                else:
                    view = controller.submit(command)
            except ProvisionalHistoryError:
                return self._reply(503, b"{}")
            except BrowserCommandError:
                return self._reply(409, b"{}")
            except (ValueError, OSError):
                return self._reply(400, b"{}")
            return self._reply(
                200 if self.path == "/api/history/command" else 202,
                json.dumps(view, ensure_ascii=False).encode(),
            )

    server = HTTPServer(("127.0.0.1", port), Handler)
    next_cleanup = 0.0

    def maintenance():
        nonlocal next_cleanup
        current = time.monotonic()
        if current < next_cleanup:
            return
        next_cleanup = current + 60.0
        try:
            history.purge_expired()
        except (ProvisionalHistoryError, OSError, ValueError):
            pass  # GET still hides expired rows; the next sweep retries without raw logs.

    server.service_actions = maintenance
    return server


def main(*, initial_source=None):
    if initial_source is not None:
        from src.search_v2.browser_search import validate_browser_source

        initial_source = validate_browser_source(initial_source)
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline-fixture", action="store_true")
    mode.add_argument("--run-live-api", action="store_true")
    mode.add_argument("--history-only", action="store_true")
    parser.add_argument("--history-db", type=Path, action="append", default=[])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--static-root", type=Path, default=Path("frontend/dist"))
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use an unprivileged local port")
    if args.run_live_api and args.output_dir is None:
        parser.error("Live mode requires a new private --output-dir and prior human authorization")
    if len(args.history_db) > 29 or any(not p.is_file() or p.is_symlink() for p in args.history_db):
        parser.error("Use up to 29 existing history database files")
    from src.search_v2.browser_history import BrowserHistory

    if args.history_only:

        class HistoryOnly:
            def snapshot(self):
                return {
                    "stage": "idle",
                    "revision": 0,
                    "historyAvailable": True,
                    "historyOnly": True,
                }

            def submit(self, command):
                raise BrowserCommandError()

        server = make_server(
            HistoryOnly(), args.static_root, port=args.port, history=BrowserHistory(args.history_db)
        )
        try:
            print(f"http://127.0.0.1:{server.server_port}/?mode=connected", flush=True)
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return
    from src.search_v2.browser_candidate import BrowserCandidateRun
    from tools.browser_search_runtime import live_steps, fixture_steps, CANARY_INPUT

    def steps(source, attempt, *, image_mode="on"):
        if args.offline_fixture:
            return fixture_steps(source=source, image_mode=image_mode)
        return live_steps(
            args.output_dir,
            source=source,
            attempt=attempt % 3,
            image_mode=image_mode,
            batch=attempt // 3,
            progress=run.progress,
        )

    run = BrowserCandidateRun(factory=steps)
    with ThreadPoolExecutor(max_workers=1) as worker:
        controller = BrowserSearch(
            run.execute,
            worker,
            initial={
                "mode": "fixture" if args.offline_fixture else "live",
                "input": CANARY_INPUT if initial_source is None else initial_source,
                "editable": True,
                "historyAvailable": True,
            },
        )
        run.progress = controller.progress
        paths = list(args.history_db)
        if args.run_live_api:
            paths += [args.output_dir / "history.sqlite3"] + [
                args.output_dir / f"revision-{i}" / "history.sqlite3" for i in (1, 2)
            ]
        server = make_server(
            controller, args.static_root, port=args.port, history=BrowserHistory(paths)
        )
        try:
            print(f"http://127.0.0.1:{server.server_port}/?mode=connected", flush=True)
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            worker.submit(run.close).result()


if __name__ == "__main__":
    main()
