"""Fixed, single-call Bonsai attribute inference diagnostic."""

from decimal import Decimal

from src.search_v2.bonsai_adapter import BonsaiCompactSearchIntentDraft
from src.search_v2.bonsai_adapter import _extract_content, _load_strict_json
from tools.bonsai_response_log import LoggedBonsaiTransport, write_json
import re
import unicodedata

from src.search_v2.bonsai_request import build_bonsai_intent_request
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_requirements import attribute_registry_sha256
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import ProviderUsageLimits
from src.search_v2.usage_ledger import UsageAmount
from tools import bonsai_live_e2e as runtime
from tools.backend_search_live_e2e import owned_bonsai


SYNTHETIC_INPUT = "白いマグカップ。350ml以上で、食洗機対応。"


def _text(value):
    return unicodedata.normalize("NFKC", value).casefold().strip()


def _capacity(candidate):
    definition = candidate.attribute_definition
    value = candidate.expected_value
    return (
        definition is not None
        and candidate.attribute_key == "custom"
        and _text(definition.label) in {"容量", "内容量", "容積"}
        and bool(re.search("容量|内容量|液体.*量", definition.meaning))
        and not re.search("重量|重さ|ではない|でない|非対応", definition.meaning)
        and candidate.operator == "at_least"
        and candidate.strength == "required"
        and value.value_type in {"integer", "decimal"}
        and value.minimum is not None
        and Decimal(str(value.minimum)) == 350
        and value.maximum is None
        and _text(value.unit) == "ml"
    )


def _dishwasher(candidate):
    definition = candidate.attribute_definition
    value = candidate.expected_value
    return (
        definition is not None
        and candidate.attribute_key == "custom"
        and bool(re.search("食洗機|食器洗い機|食器洗浄機", definition.label))
        and bool(re.search("食洗機|食器洗い機|食器洗浄機", definition.meaning))
        and not re.search("不可|できない|非対応|不対応|ではない", definition.meaning)
        and candidate.operator == "equals"
        and candidate.strength == "required"
        and value.value_type == "boolean"
        and value.value is True
    )


def judge_inference(intent):
    """Use fixed-case lexical criteria; this is not a general semantic evaluator."""
    proposal = build_typed_requirement_proposal(intent)
    candidates = intent.typed_conditions
    return {
        "proposal_ready": proposal.status == "ready",
        "product_type": intent.product_name_ja == "マグカップ",
        "exactly_three_conditions": len(candidates) == len(proposal.requirements) == 3,
        "white_required": sum(
            c.attribute_key == "appearance.color"
            and c.operator == "equals"
            and c.strength == "required"
            and c.expected_value.value_type == "enum"
            and tuple(c.expected_value.values) == ("white",)
            for c in candidates
        )
        == 1,
        "capacity_minimum_350ml": sum(_capacity(c) for c in candidates) == 1,
        "dishwasher_required": sum(_dishwasher(c) for c in candidates) == 1,
        "two_search_local_attributes": sum(
            r.attribute_key.startswith("search.") for r in proposal.requirements
        )
        == 2,
        "no_extra_preferences": not (
            intent.preferred_terms_ja
            or intent.preferred_terms_en
            or intent.negative_terms_ja
            or intent.negative_terms_en
            or intent.price.mode != "none"
            or intent.brand
            or intent.model_number
        ),
    }


def project_model_response(body):
    result = {"stage": "envelope_invalid", "typed_count": None, "custom_count": None}
    try:
        envelope = runtime._response_envelope(body)
        extracted = _extract_content(envelope)
        if extracted is None:
            return result
        result["stage"] = "content_not_json"
        valid, payload = _load_strict_json(extracted[0])
        if not valid or type(payload) is not dict:
            return result
        result["stage"] = "draft_schema_invalid"
        from src.search_v2.source_constraints import expand_source_names

        payload = expand_source_names(SYNTHETIC_INPUT, payload)
        draft = BonsaiCompactSearchIntentDraft.model_validate(payload).to_search_intent_draft()
        result.update(
            stage="draft_valid",
            typed_count=len(draft.typed_conditions),
            custom_count=sum(c.attribute_key == "custom" for c in draft.typed_conditions),
            product_type=draft.product_name_ja == "マグカップ",
            capacity_minimum_350ml=any(_capacity(c) for c in draft.typed_conditions),
            dishwasher_required=any(_dishwasher(c) for c in draft.typed_conditions),
        )
    except Exception:
        pass  # Raw bytes remain in the private log; stdout contains fixed diagnostics only.
    return result


def run_inference_probe(
    config,
    *,
    log_dir,
    source_input=SYNTHETIC_INPUT,
    judge=judge_inference,
    project=project_model_response,
):
    transport = LoggedBonsaiTransport(log_dir)
    before = attribute_registry_sha256()
    prepared = build_bonsai_intent_request(
        source_input,
        base_url=f"http://127.0.0.1:{config.port}/v1",
        model_id=config.model_path.name,
        temperature=0.0,
    )
    limit = UsageAmount(calls=1, tokens=prepared.request.maximum_usage_tokens, cost_microusd=0)
    ledger = InMemoryUsageLedger(
        [
            ProviderUsageLimits(
                provider="bonsai",
                pricing_policy_sha256=runtime.BONSAI_E2E_PRICING_POLICY_SHA256,
                per_user_day=limit,
                per_session=limit,
                global_day=limit,
            )
        ]
    )
    try:
        with owned_bonsai(config):
            execution, metrics, milliseconds = runtime._execute_request(
                prepared, ledger=ledger, transport=transport
            )
            checks = judge(execution.intent)
            write_json(log_dir / "normalized-intent.json", execution.intent.model_dump(mode="json"))
    except Exception:
        write_json(
            log_dir / "probe-result.json",
            {
                "status": "failed",
                "stage": "execution_or_cleanup",
                "request_count": transport.calls,
            },
        )
        raise
    finally:
        response_path = log_dir / "response-001.body"
        if response_path.is_file():
            write_json(
                log_dir / "model-projection.json",
                project(response_path.read_bytes()),
            )
    checks["shared_registry_unchanged"] = before == attribute_registry_sha256()
    result = {
        "checks": checks,
        "normalized_typed_count": len(execution.intent.typed_conditions),
        "normalized_custom_count": sum(
            c.attribute_key == "custom" for c in execution.intent.typed_conditions
        ),
        "request_count": 1,
        "retry_count": 0,
        "wall_milliseconds": milliseconds,
        "prompt_tokens": metrics.prompt_usage.prompt_tokens,
        "completion_tokens": metrics.completion_tokens,
        "response_bytes": metrics.response_bytes,
        "server_stopped": True,
    }
    write_json(log_dir / "probe-result.json", result)
    return result
