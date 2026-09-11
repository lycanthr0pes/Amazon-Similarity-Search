"""Offline replay of a frozen definition experiment through the evidence gate."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from src.search_v2.attribute_resolution import resolve_definition_response
from tools.bonsai_response_log import REPOSITORY_ROOT, write_json, write_private


def replay(source: Path, destination: Path):
    if (
        not destination.is_absolute()
        or destination.resolve() != destination
        or destination.is_relative_to(REPOSITORY_ROOT)
    ):
        raise ValueError("A new repository-external absolute log directory is required")
    manifest = json.loads((source / "manifest.json").read_bytes())
    requests = manifest["requests"]
    if len(requests) != 52:
        raise ValueError("Expected the complete frozen 52-request experiment")
    destination.mkdir(mode=0o700)
    cases = {case["case_id"]: case for case in manifest["cases"]}
    files = [*sorted((REPOSITORY_ROOT / "src/search_v2").glob("*.py")), Path(__file__).resolve()]
    write_json(
        destination / "manifest.json",
        {
            "kind": "offline_replay",
            "new_model_calls": 0,
            "source_manifest_sha256": hashlib.sha256(
                (source / "manifest.json").read_bytes()
            ).hexdigest(),
            "source_sha256": {
                str(p.relative_to(REPOSITORY_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in files
            },
            "criteria": {
                "negative_held": 16,
                "invalid": 0,
                "report_positive_coverage_separately": True,
            },
        },
    )
    results = []
    for index, request in enumerate(requests, 1):
        body = (source / f"request-{index:03}.json").read_bytes()
        if hashlib.sha256(body).hexdigest() != request["sha256"]:
            raise ValueError("Frozen request changed")
        trial = source / f"trial-{index:03}"
        raw = (trial / "response-001.body").read_bytes()
        metadata = json.loads((trial / "response-001.json").read_bytes())
        if (
            not metadata["body_complete"]
            or metadata["status_code"] != 200
            or metadata["received_bytes"] != len(raw)
        ):
            raise ValueError("Incomplete recorded response")
        write_private(destination / f"request-{index:03}.json", body)
        write_private(destination / f"response-{index:03}.body", raw)
        context = json.loads(json.loads(body)["messages"][1]["content"])
        # Evaluation labels never enter resolve_definition_response.
        decision = resolve_definition_response(context, raw)
        case = cases[request["case_id"]]
        result = {
            "index": index,
            "case_id": case["case_id"],
            "group": case["group"],
            "mode": request["mode"],
            "negative": case["expected"] is None,
            "response_sha256": hashlib.sha256(raw).hexdigest(),
            **asdict(decision),
        }
        write_json(destination / f"assessment-{index:03}.json", result)
        results.append(result)
    negative = [r for r in results if r["negative"]]
    positive = [r for r in results if not r["negative"]]
    summary = {
        "kind": "offline_replay",
        "new_model_calls": 0,
        "total": len(results),
        "negative_count": len(negative),
        "negative_held": sum(r["status"] == "unresolved" for r in negative),
        "positive_count": len(positive),
        "positive_resolved": sum(r["status"] == "resolved" for r in positive),
        "positive_held": sum(r["status"] == "unresolved" for r in positive),
        "invalid": sum(r["status"] == "invalid" for r in results),
    }
    write_json(destination / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-log-dir", type=Path, required=True)
    parser.add_argument("--log-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(replay(args.source_log_dir, args.log_dir), sort_keys=True))


if __name__ == "__main__":
    main()
