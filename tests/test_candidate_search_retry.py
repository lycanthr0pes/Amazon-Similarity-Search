"""A fresh search requires renewed authorization and preserves approved source data."""

from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest

from src.search_v2.candidate_search import CandidateSearch, prepare_candidate_search
from tools.backend_search_live_e2e import BackendE2EConfig
import test_candidate_search_live_e2e as live
import test_search_v2_orchestrator as fixtures


def original():
    return prepare_candidate_search(
        "マグカップ。3000円以下。",
        owner_id="local-user",
        session_id="retry-test",
        postal_code="100-0001",
        normalization_profile=fixtures.backend_policy().normalization_profile,
        now=fixtures.NOW,
    )


def renew(service, **overrides):
    options = dict(
        source="マグカップ。3000円以下。",
        owner_id="local-user",
        plan_sha256=service.plan_sha256,
        human_confirmed=True,
        normalization_profile=fixtures.backend_policy().normalization_profile,
        now=fixtures.NOW + timedelta(hours=1),
    )
    options.update(overrides)
    return CandidateSearch.from_approved_plan(service.plan, **options)


@pytest.mark.parametrize(
    "change",
    [
        {"human_confirmed": False},
        {"owner_id": "other"},
        {"plan_sha256": "0" * 64},
        {"source": "マグカップ。5000円以下。"},
    ],
)
def test_saved_plan_is_not_authorization(change):
    with pytest.raises(ValueError):
        renew(original(), **change)


def test_renewed_search_keeps_query_conditions_and_gets_fresh_lifetime():
    before = original()
    after = renew(before)
    assert after.plan.request == before.plan.request
    assert after.plan.visual_conditions == before.plan.visual_conditions
    assert after.plan.source_sha256 == before.plan.source_sha256
    assert after._conditions == before._conditions
    assert after.plan.created_at == fixtures.NOW + timedelta(hours=1)
    assert after.plan.expires_at - after.plan.created_at == timedelta(minutes=15)
    assert after.plan_sha256 != before.plan_sha256


def saved_run(tmp_path, monkeypatch):
    module, config, services, events, clips = live.setup_run(tmp_path, monkeypatch)

    def failed_key():
        raise ValueError("fixture pre-fetch failure")

    result = module.run_candidate_e2e(
        config, replace(services, load_outscraper_api_key=failed_key), image_score_mode="appearance"
    )
    assert result["failure_stage"] == "candidates"
    return config, services, clips


def test_saved_images_retry_reaches_clip_ranking_and_history(tmp_path, monkeypatch):
    from tools import candidate_search_retry as retry

    config, services, clips = saved_run(tmp_path, monkeypatch)
    bundle = retry.load_saved_run(config.output_dir)

    def forbidden(*args, **kwargs):
        pytest.fail("Search retry cannot run Bonsai or image generation")

    services = replace(
        services,
        bonsai_session=forbidden,
        load_cloudflare=forbidden,
        cloudflare_transport=SimpleNamespace(post_multipart=forbidden),
    )
    target = BackendE2EConfig(tmp_path / "retry-output", config.asset_root)
    result = retry.run_search_retry(target, services, bundle, human_confirmed=True)
    assert result["status"] == "succeeded"
    assert result["bonsai_calls"] == 0 and result["cloudflare_calls"] == 0
    assert result["outscraper_tasks"] == 1 and result["history_images_verified"] == 2
    assert clips == [2, 4]
    assert (target.output_dir / "ranking.json").is_file()


def test_saved_image_change_is_rejected_before_request(tmp_path, monkeypatch):
    from tools import candidate_search_retry as retry

    config, services, _ = saved_run(tmp_path, monkeypatch)
    bundle = retry.load_saved_run(config.output_dir)
    (config.output_dir / "image-1.png").write_bytes(b"changed")

    def forbidden():
        pytest.fail("Changed image must not load credentials")

    result = retry.run_search_retry(
        BackendE2EConfig(tmp_path / "retry-output", config.asset_root),
        replace(services, load_outscraper_api_key=forbidden),
        bundle,
        human_confirmed=True,
    )
    assert result["status"] == "failed" and result["outscraper_tasks"] == 0


def test_retry_denied_without_current_confirmation(tmp_path, monkeypatch):
    from tools import candidate_search_retry as retry

    config, services, _ = saved_run(tmp_path, monkeypatch)
    bundle = retry.load_saved_run(config.output_dir)

    def forbidden():
        pytest.fail("Unapproved retry must not load credentials")

    result = retry.run_search_retry(
        BackendE2EConfig(tmp_path / "retry", config.asset_root),
        replace(services, load_outscraper_api_key=forbidden),
        bundle,
        human_confirmed=False,
    )
    assert result["status"] == "failed" and result["outscraper_tasks"] == 0


@pytest.mark.parametrize("change", ["unconsumed", "digest", "owner"])
def test_saved_approval_tampering_is_rejected(tmp_path, monkeypatch, change):
    import sqlite3
    from tools import candidate_search_retry as retry

    config, _, _ = saved_run(tmp_path, monkeypatch)
    with sqlite3.connect(config.output_dir / "approvals.sqlite3") as connection:
        if change == "unconsumed":
            connection.execute("UPDATE counterfactual_approvals SET consumed_at=NULL")
        elif change == "digest":
            connection.execute("UPDATE counterfactual_approvals SET review_sha256=?", ("0" * 64,))
        else:
            import json
            from src.search_v2.provisional_approval_repository import (
                CounterfactualReferenceApprovalReview,
                counterfactual_approval_review_sha256,
            )

            body = json.loads(
                connection.execute("SELECT review_json FROM counterfactual_approvals").fetchone()[0]
            )
            body["owner_id"] = "other-owner"
            review = CounterfactualReferenceApprovalReview.model_validate_json(json.dumps(body))
            connection.execute(
                "UPDATE counterfactual_approvals SET review_json=?,review_sha256=?",
                (review.model_dump_json(), counterfactual_approval_review_sha256(review)),
            )
    with pytest.raises(ValueError):
        retry.load_saved_run(config.output_dir)


def test_provider_failure_keeps_task_identity_without_body(tmp_path, monkeypatch):
    import json
    from src.search_v2.outscraper_http import OutscraperHttpResponse
    from tools import candidate_search_retry as retry

    config, services, _ = saved_run(tmp_path, monkeypatch)
    bundle = retry.load_saved_run(config.output_dir)

    class Failure:
        def get(self, **kwargs):
            body = b'{"id":"fixture-task","status":"Failure","error":"private-fixture-detail"}'
            return OutscraperHttpResponse(200, "application/json", len(body), None, (body,))

    target = BackendE2EConfig(tmp_path / "retry", config.asset_root)
    result = retry.run_search_retry(
        target, replace(services, outscraper_transport=Failure()), bundle, human_confirmed=True
    )
    assert result["status"] == "failed" and result["outscraper_tasks"] == 1
    metadata = json.loads((target.output_dir / "task-status-1.json").read_text())
    assert metadata["provider_request_id"] == "fixture-task"
    assert metadata["provider_status"] == "Failure"
    failure = json.loads((target.output_dir / "retrieval-failure.json").read_text())
    assert failure["exception_type"] == "OutscraperTaskFailed"
    assert all(
        "private-fixture-detail" not in p.read_text() for p in target.output_dir.glob("*.json")
    )
