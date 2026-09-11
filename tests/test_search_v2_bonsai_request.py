import ast
import hashlib
import inspect
import json
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

import src.search_v2.bonsai_adapter as bonsai_adapter
import src.search_v2.bonsai_request as bonsai_request
from src.exceptions import BonsaiRequestError
from src.exceptions import BonsaiResponseError
from src.search_v2.bonsai_adapter import search_intent_schema_bytes
from src.search_v2.source_constraints import bind_generation_schema
from src.search_v2.bonsai_request import BONSAI_MAX_RESPONSE_BYTES
from src.search_v2.bonsai_request import BONSAI_REQUEST_HEADERS
from src.search_v2.bonsai_request import BonsaiHttpResponse
from src.search_v2.bonsai_request import BonsaiIntentRequest
from src.search_v2.bonsai_request import PreparedBonsaiIntentRequest
from src.search_v2.bonsai_request import bonsai_intent_request_sha256
from src.search_v2.bonsai_request import build_bonsai_intent_request
from src.search_v2.bonsai_request import execute_bonsai_intent_request
from src.search_v2.bonsai_request import load_bonsai_intent_prompt
from src.search_v2.usage_ledger import InMemoryUsageLedger
from src.search_v2.usage_ledger import ProviderUsageLimits
from src.search_v2.usage_ledger import UsageAmount
from src.search_v2.usage_ledger import UsageReservationRequest


SOURCE_INPUT = "Sony WH-1000XM5の黒いワイヤレスヘッドホンを5万円以内で"
BASE_URL = "http://127.0.0.1:8080/v1"
MODEL_ID = "Bonsai-8B.gguf"
NOW = datetime(2026, 9, 3, 3, 0, tzinfo=timezone.utc)
GENERATION_SCHEMA_SHA256 = "415728a8c74f59373994d18b8e16f65750c90d8a0c6f10c150630f77a89dc2e6"
COMPATIBLE_DECIMAL_PATTERN = r"^-?(0|[1-9][0-9]{0,12})(\.[0-9]{1,6})?$"


def intent_payload() -> dict[str, object]:
    return {
        "product_name_ja": "ヘッドホン",
        "product_name_en": "headphones",
        "typed_conditions": [
            {
                "attribute_key": "appearance.color",
                "strength": "required",
                "operator": "equals",
                "expected_value": {"value_type": "enum", "values": ["black"]},
            }
        ],
        "required_terms_ja": ["ワイヤレス", "黒"],
        "required_terms_en": ["wireless", "black"],
        "preferred_terms_ja": ["軽量", "ノイズキャンセリング"],
        "preferred_terms_en": ["lightweight", "noise cancelling"],
        "negative_terms_ja": ["中古"],
        "negative_terms_en": ["used"],
        "brand": "Sony",
        "model_number": "WH-1000XM5",
        "price": {
            "mode": "max",
            "max_jpy": 50000,
            "source": "explicit",
        },
    }


def compact_intent_payload() -> dict[str, object]:
    return intent_payload()


def valid_response_bytes(*, marker: str = "fixture-response-id") -> bytes:
    content = json.dumps(intent_payload(), ensure_ascii=False, separators=(",", ":"))
    envelope = {
        "id": marker,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }
    return json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode()


def prepared_request(**overrides) -> PreparedBonsaiIntentRequest:
    parameters = {
        "base_url": BASE_URL,
        "model_id": MODEL_ID,
        "temperature": 0.1,
    }
    parameters.update(overrides)
    return build_bonsai_intent_request(SOURCE_INPUT, **parameters)


def usage_limits(provider: str = "bonsai") -> ProviderUsageLimits:
    amount = UsageAmount(calls=100, tokens=10_000_000, cost_microusd=10_000_000)
    return ProviderUsageLimits(
        provider=provider,
        pricing_policy_sha256={
            "bonsai": "a" * 64,
            "cloudflare": "b" * 64,
        }[provider],
        per_user_day=amount,
        per_session=amount,
        global_day=amount,
    )


def reserved_usage(
    prepared: PreparedBonsaiIntentRequest,
    *,
    binding_sha256: str | None = None,
    calls: int = 1,
    tokens: int | None = None,
    provider: str = "bonsai",
):
    ledger = InMemoryUsageLedger([usage_limits(provider)])
    operation = "intent" if provider == "bonsai" else "image_set"
    reservation = ledger.reserve(
        UsageReservationRequest(
            provider=provider,
            operation=operation,
            owner_id="owner-1",
            session_id="session-1",
            binding_sha256=(
                bonsai_intent_request_sha256(prepared.request)
                if binding_sha256 is None
                else binding_sha256
            ),
            amount=UsageAmount(
                calls=calls,
                tokens=(prepared.request.maximum_usage_tokens if tokens is None else tokens),
                cost_microusd=0,
            ),
            pricing_policy_sha256={
                "bonsai": "a" * 64,
                "cloudflare": "b" * 64,
            }[provider],
        ),
        now=NOW,
    )
    return ledger, reservation


class RecordingTransport:
    def __init__(
        self,
        response: BonsaiHttpResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    def post_json(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class SequenceClock:
    def __init__(self, *values: datetime) -> None:
        self.values = iter(values)

    def __call__(self) -> datetime:
        return next(self.values)


def http_response(
    body: bytes,
    *,
    status_code: int = 200,
    content_type: str | None = "application/json; charset=utf-8",
    content_length: int | None = None,
    content_encoding: str | None = "identity",
    body_chunks=None,
) -> BonsaiHttpResponse:
    return BonsaiHttpResponse(
        status_code=status_code,
        content_type=content_type,
        content_length=len(body) if content_length is None else content_length,
        content_encoding=content_encoding,
        body_chunks=body_chunks if body_chunks is not None else (body[:7], body[7:]),
    )


def execute(
    prepared: PreparedBonsaiIntentRequest,
    transport: RecordingTransport,
    *,
    ledger: InMemoryUsageLedger | None = None,
    reservation=None,
):
    if ledger is None or reservation is None:
        ledger, reservation = reserved_usage(prepared)
    result = execute_bonsai_intent_request(
        prepared,
        usage_ledger=ledger,
        usage_reservation=reservation,
        transport=transport,
        now=SequenceClock(NOW + timedelta(seconds=1), NOW + timedelta(seconds=2)),
    )
    return result, ledger


def test_prompt_asset_load_is_exact_and_independent_of_current_directory(
    monkeypatch,
    tmp_path,
) -> None:
    first = load_bonsai_intent_prompt()
    monkeypatch.chdir(tmp_path)

    assert load_bonsai_intent_prompt() == first
    assert isinstance(first, bytes)
    assert first
    assert b"JSON" in first
    assert b"Markdown" in first


def test_prompt_requires_searchable_nonblocking_output_and_forbids_query_urls() -> None:
    prompt = load_bonsai_intent_prompt().decode("utf-8")

    assert "非blocking" in prompt
    assert "product_name_ja" in prompt
    assert "必ず" in prompt
    assert "URL" in prompt


def test_generation_schema_is_canonical_and_closes_known_strict_schema_gaps() -> None:
    generation_schema_reader = getattr(
        bonsai_adapter,
        "search_intent_generation_schema_bytes",
        None,
    )

    assert callable(generation_schema_reader)
    first = generation_schema_reader()
    second = generation_schema_reader()
    generation_schema = json.loads(first)
    complete_schema = json.loads(search_intent_schema_bytes())

    assert first == second
    assert (
        first
        == json.dumps(
            generation_schema,
            ensure_ascii=False,
            sort_keys=False,
            separators=(",", ":"),
        ).encode()
    )
    assert generation_schema != complete_schema
    assert generation_schema["type"] == "object"
    assert "properties" not in generation_schema
    assert hashlib.sha256(first).hexdigest() == GENERATION_SCHEMA_SHA256

    root_variants = generation_schema["anyOf"]
    assert len(root_variants) == 2
    searchable_variant, blocking_variant = root_variants
    assert searchable_variant["properties"]["product_name_ja"]["type"] == "string"
    assert blocking_variant["properties"]["ambiguities"]["minItems"] == 1
    assert blocking_variant["properties"]["ambiguities"]["items"] == {
        "$ref": "#/$defs/BonsaiCompactIntentAmbiguity"
    }
    assert generation_schema["$defs"]["BonsaiCompactIntentAmbiguity"]["properties"]["blocking"] == {
        "const": True,
        "type": "boolean",
    }

    definitions = generation_schema["$defs"]
    complete_definitions = complete_schema["$defs"]
    assert (
        definitions["BonsaiCompactIntentAmbiguity"]["properties"]["code"]["pattern"]
        == complete_definitions["IntentAmbiguity"]["properties"]["code"]["pattern"]
    )
    decimal_variants = definitions["BonsaiCompactDecimalTarget"]["oneOf"]
    for field_name in ("minimum", "maximum"):
        field_schemas = [
            variant["properties"][field_name]
            for variant in decimal_variants
            if field_name in variant["properties"]
        ]
        assert field_schemas
        resolved = [
            definitions[item["$ref"].rsplit("/", 1)[1]] if "$ref" in item else item
            for item in field_schemas
        ]
        assert all(item["pattern"] == COMPATIBLE_DECIMAL_PATTERN for item in resolved)

    price_schema = definitions["BonsaiCompactPriceCondition"]
    price_variants = price_schema["oneOf"]
    assert len(price_variants) == 8
    assert {
        (
            variant["properties"]["mode"]["const"],
            variant["properties"]["source"]["const"],
        )
        for variant in price_variants
    } == {
        ("exact", "explicit"),
        ("exact", "inferred"),
        ("range", "explicit"),
        ("range", "inferred"),
        ("min", "explicit"),
        ("min", "inferred"),
        ("max", "explicit"),
        ("max", "inferred"),
    }
    expected_active_fields = {
        "exact": {"target_jpy"},
        "range": {"min_jpy", "max_jpy"},
        "min": {"min_jpy"},
        "max": {"max_jpy"},
    }
    for variant in price_variants:
        properties = variant["properties"]
        mode = properties["mode"]["const"]
        source = properties["source"]["const"]
        assert variant["type"] == "object"
        assert variant["additionalProperties"] is False
        expected_properties = {
            "mode",
            "source",
            *expected_active_fields[mode],
        }
        expected_required = [
            "mode",
            *(
                field_name
                for field_name in ("target_jpy", "min_jpy", "max_jpy")
                if field_name in expected_active_fields[mode]
            ),
            "source",
        ]
        if source == "inferred":
            expected_properties.add("confidence")
            expected_required.append("confidence")
            assert properties["confidence"]["type"] == "number"
        assert set(properties) == expected_properties
        assert variant["required"] == expected_required

    assert complete_definitions["PriceCondition"]["required"] == [
        "currency",
        "mode",
        "target_jpy",
        "min_jpy",
        "max_jpy",
        "source",
        "confidence",
    ]


def test_generation_schema_requires_product_identity_or_blocking_ambiguity() -> None:
    generation_schema = json.loads(bonsai_adapter.search_intent_generation_schema_bytes())
    validator = Draft202012Validator(generation_schema)

    searchable = compact_intent_payload()
    assert list(validator.iter_errors(searchable)) == []

    missing_identity = compact_intent_payload()
    missing_identity.pop("product_name_ja")
    assert len(list(validator.iter_errors(missing_identity))) == 1

    blocking = {
        "ambiguities": [
            {
                "code": "product_type_unknown",
                "message": "商品種別を確認してください",
                "blocking": True,
            }
        ]
    }
    assert list(validator.iter_errors(blocking)) == []

    nonblocking_ambiguity = dict(blocking)
    nonblocking_ambiguity["ambiguities"] = [
        {
            "code": "minor_question",
            "message": "任意条件を確認してください",
            "blocking": False,
        }
    ]
    assert len(list(validator.iter_errors(nonblocking_ambiguity))) == 1


def test_builds_canonical_credential_free_request_and_safe_descriptor() -> None:
    prepared = prepared_request()
    prompt = load_bonsai_intent_prompt()
    schema = search_intent_schema_bytes()
    generation_schema_reader = getattr(
        bonsai_adapter,
        "search_intent_generation_schema_bytes",
        None,
    )
    assert callable(generation_schema_reader)
    generation_schema = bind_generation_schema(SOURCE_INPUT, generation_schema_reader())
    payload = json.loads(prepared.body.decode())

    assert payload == {
        "messages": [
            {
                "content": prompt.decode(),
                "role": "system",
            },
            {"content": SOURCE_INPUT, "role": "user"},
        ],
        "model": MODEL_ID,
        "response_format": {
            "schema": json.loads(generation_schema),
            "type": "json_object",
        },
        "stream": False,
        "temperature": 0.1,
    }
    assert prepared.request.schema_version == "9.0"
    assert prepared.request.response_format == "json_object"
    assert prepared.request.endpoint == f"{BASE_URL}/chat/completions"
    assert prepared.request.source_input_sha256 == hashlib.sha256(SOURCE_INPUT.encode()).hexdigest()
    assert prepared.request.prompt_sha256 == hashlib.sha256(prompt).hexdigest()
    assert prepared.request.schema_sha256 == hashlib.sha256(schema).hexdigest()
    assert (
        prepared.request.generation_schema_sha256 == hashlib.sha256(generation_schema).hexdigest()
    )
    assert prepared.request.body_sha256 == hashlib.sha256(prepared.body).hexdigest()
    assert prepared.request.maximum_usage_tokens == len(prepared.body) + BONSAI_MAX_RESPONSE_BYTES
    assert "max_tokens" not in payload
    assert "max_output_tokens" not in BonsaiIntentRequest.model_fields
    assert "timeout_seconds" not in BonsaiIntentRequest.model_fields
    assert payload["response_format"]["schema"]
    assert schema.decode() not in payload["messages"][0]["content"]
    assert "json_schema" not in payload["response_format"]
    assert "authorization" not in prepared.body.decode().casefold()

    serialized = prepared.request.model_dump_json()
    assert SOURCE_INPUT not in serialized
    assert prompt.decode() not in serialized
    assert "messages" not in serialized
    assert SOURCE_INPUT not in repr(prepared)
    assert set(BonsaiIntentRequest.model_json_schema()["properties"]).isdisjoint(
        {"source_input", "prompt", "body", "authorization"}
    )


def test_request_digest_is_deterministic_and_binds_execution_parameters() -> None:
    original = prepared_request()
    same = prepared_request()

    assert original.body == same.body
    assert bonsai_intent_request_sha256(original.request) == bonsai_intent_request_sha256(
        same.request
    )

    variants = (
        build_bonsai_intent_request(
            "別の商品",
            base_url=BASE_URL,
            model_id=MODEL_ID,
            temperature=0.1,
        ),
        prepared_request(model_id="other-model"),
        prepared_request(temperature=0.2),
        prepared_request(base_url="https://bonsai.example.test/v1"),
    )
    digest = bonsai_intent_request_sha256(original.request)
    assert all(bonsai_intent_request_sha256(item.request) != digest for item in variants)


@pytest.mark.parametrize(
    "base_url",
    [
        "http://bonsai.example.test/v1",
        "http://localhost:8080/v1",
        "https://User:password@bonsai.example.test/v1",
        "https://Bonsai.example.test/v1",
        "https://bonsai.example.test./v1",
        "https://bonsai.example.test/v1/",
        "https://bonsai.example.test/other",
        "https://bonsai.example.test/v1?mode=test",
        "https://bonsai.example.test/v1#fragment",
        "https:///v1",
    ],
)
def test_rejects_noncanonical_or_unsafe_base_url(base_url: str) -> None:
    with pytest.raises(BonsaiRequestError, match="^Bonsai intent request is invalid$") as error:
        prepared_request(base_url=base_url)

    assert base_url not in str(error.value)
    assert error.value.__cause__ is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"model_id": ""},
        {"model_id": " leading-space"},
        {"model_id": "bad\nmodel"},
        {"temperature": -0.1},
        {"temperature": 2.1},
    ],
)
def test_rejects_invalid_request_parameters(overrides: dict[str, object]) -> None:
    with pytest.raises(BonsaiRequestError, match="^Bonsai intent request is invalid$"):
        prepared_request(**overrides)


@pytest.mark.parametrize("source_input", ["", " \n\t ", "bad\x00input", "a" * 2_001])
def test_rejects_invalid_source_input_before_a_request_is_prepared(source_input: str) -> None:
    with pytest.raises(BonsaiRequestError, match="^Bonsai intent request is invalid$"):
        build_bonsai_intent_request(
            source_input,
            base_url=BASE_URL,
            model_id=MODEL_ID,
            temperature=0.1,
        )


def test_builder_signature_exposes_no_generation_token_or_timeout_control() -> None:
    parameters = inspect.signature(build_bonsai_intent_request).parameters

    assert "max_output_tokens" not in parameters
    assert "timeout_seconds" not in parameters
    assert "max_output_tokens" not in BonsaiIntentRequest.model_fields
    assert "timeout_seconds" not in BonsaiIntentRequest.model_fields


def test_request_model_is_strict_frozen_and_revalidates_instances() -> None:
    request = prepared_request().request
    payload = request.model_dump(mode="python")
    payload["unexpected"] = True

    with pytest.raises(ValidationError, match="extra_forbidden"):
        BonsaiIntentRequest.model_validate(payload)
    with pytest.raises(ValidationError, match="literal_error"):
        BonsaiIntentRequest.model_validate(
            {**request.model_dump(mode="python"), "schema_version": "6.0"}
        )
    without_generation_schema = request.model_dump(mode="python")
    without_generation_schema.pop("generation_schema_sha256", None)
    with pytest.raises(ValidationError, match="missing"):
        BonsaiIntentRequest.model_validate(without_generation_schema)


def test_generation_schema_does_not_replace_strict_application_validation() -> None:
    prepared = prepared_request()
    payload = intent_payload()
    payload["typed_conditions"] = [
        {
            "attribute_key": "dimensions.width",
            "operator": "at_most",
            "expected_value": {
                "value_type": "decimal",
                "minimum": None,
                "maximum": "01",
                "unit": "mm",
            },
            "strength": "required",
        }
    ]
    content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    response = {
        "choices": [
            {
                "message": {"content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"completion_tokens": 20},
    }
    body = json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode()
    transport = RecordingTransport(http_response(body))
    ledger, reservation = reserved_usage(prepared)

    error_type = getattr(bonsai_adapter, "BonsaiResponseContractError", BonsaiResponseError)
    with pytest.raises(error_type) as error:
        execute(prepared, transport, ledger=ledger, reservation=reservation)

    assert error.value.diagnostic.stage == "draft_schema_invalid"
    assert ledger.snapshot().reservations[0].status == "failed"


def test_execution_calls_exact_transport_once_and_finishes_usage() -> None:
    prepared = prepared_request()
    response = valid_response_bytes(marker="raw-response-marker")
    transport = RecordingTransport(http_response(response))

    result, ledger = execute(prepared, transport)

    assert transport.calls == [
        {
            "url": prepared.request.endpoint,
            "headers": BONSAI_REQUEST_HEADERS,
            "body": prepared.body,
            "allow_redirects": False,
            "accept_encoding": "identity",
            "maximum_response_bytes": BONSAI_MAX_RESPONSE_BYTES,
        }
    ]
    assert result.request == prepared.request
    assert result.intent.brand == "Sony"
    assert result.intent.provenance.response_sha256 == hashlib.sha256(response).hexdigest()
    assert result.usage_reservation.status == "succeeded"
    assert ledger.snapshot().reservations[0].status == "succeeded"
    assert SOURCE_INPUT not in repr(result)
    assert "raw-response-marker" not in repr(result)


def test_transport_failure_is_fixed_message_charged_and_not_retried() -> None:
    prepared = prepared_request()
    marker = "transport-secret-marker"
    transport = RecordingTransport(error=RuntimeError(marker))
    ledger, reservation = reserved_usage(prepared)

    with pytest.raises(BonsaiRequestError, match="^Bonsai intent request failed$") as error:
        execute(prepared, transport, ledger=ledger, reservation=reservation)

    assert marker not in str(error.value)
    assert error.value.__cause__ is None
    assert len(transport.calls) == 1
    assert ledger.snapshot().reservations[0].status == "failed"


def test_non_success_status_does_not_consume_or_expose_response_body() -> None:
    marker = "provider-error-body-marker"

    def forbidden_body():
        raise AssertionError(marker)
        yield b""

    prepared = prepared_request()
    transport = RecordingTransport(
        http_response(b"", status_code=503, body_chunks=forbidden_body())
    )
    ledger, reservation = reserved_usage(prepared)

    with pytest.raises(BonsaiRequestError, match="^Bonsai intent request failed$") as error:
        execute(prepared, transport, ledger=ledger, reservation=reservation)

    assert marker not in str(error.value)
    assert ledger.snapshot().reservations[0].status == "failed"


@pytest.mark.parametrize(
    "response",
    [
        http_response(b"{}", content_type=None),
        http_response(b"{}", content_type="text/html"),
        http_response(b"{}", content_encoding="gzip"),
        http_response(b"{}", content_length=3),
        http_response(b"{}", body_chunks=(b"{}", "not-bytes")),
        http_response(b"{}"),
    ],
)
def test_invalid_http_or_contract_response_is_fixed_and_charged(
    response: BonsaiHttpResponse,
) -> None:
    prepared = prepared_request()
    transport = RecordingTransport(response)
    ledger, reservation = reserved_usage(prepared)

    with pytest.raises(
        BonsaiResponseError, match="^Bonsai response did not match the search intent contract$"
    ) as error:
        execute(prepared, transport, ledger=ledger, reservation=reservation)

    assert error.value.__cause__ is None
    assert ledger.snapshot().reservations[0].status == "failed"


def test_invalid_http_metadata_has_safe_response_stage() -> None:
    marker = "unsafe-content-type-marker"
    prepared = prepared_request()
    transport = RecordingTransport(http_response(b"{}", content_type=f"text/{marker}"))
    ledger, reservation = reserved_usage(prepared)

    error_type = getattr(bonsai_adapter, "BonsaiResponseContractError", BonsaiResponseError)
    with pytest.raises(error_type) as error:
        execute(prepared, transport, ledger=ledger, reservation=reservation)

    assert str(error.value) == "Bonsai response did not match the search intent contract"
    assert error.value.diagnostic.stage == "response_metadata_invalid"
    assert error.value.diagnostic.finish_reason == "missing"
    assert error.value.diagnostic.completion_tokens is None
    assert error.value.diagnostic.response_bytes == 0
    assert marker not in repr(error.value)
    assert marker not in repr(error.value.diagnostic)
    assert error.value.__cause__ is None
    assert error.value.__context__ is None
    assert ledger.snapshot().reservations[0].status == "failed"


def test_declared_response_limit_is_enforced_without_consuming_body() -> None:
    def forbidden_body():
        raise AssertionError("oversized response body must not be consumed")
        yield b""

    prepared = prepared_request()
    response = BonsaiHttpResponse(
        status_code=200,
        content_type="application/json",
        content_length=BONSAI_MAX_RESPONSE_BYTES + 1,
        content_encoding="identity",
        body_chunks=forbidden_body(),
    )
    transport = RecordingTransport(response)
    ledger, reservation = reserved_usage(prepared)

    with pytest.raises(BonsaiResponseError, match="search intent contract"):
        execute(prepared, transport, ledger=ledger, reservation=reservation)

    assert ledger.snapshot().reservations[0].status == "failed"


@pytest.mark.parametrize(
    ("reservation_options", "start_first"),
    [
        ({"binding_sha256": "f" * 64}, False),
        ({"calls": 2}, False),
        ({"tokens": 999}, False),
        ({"provider": "cloudflare"}, False),
        ({}, True),
    ],
)
def test_invalid_usage_reservation_stops_before_transport(
    reservation_options: dict[str, object],
    start_first: bool,
) -> None:
    prepared = prepared_request()
    ledger, reservation = reserved_usage(prepared, **reservation_options)
    if start_first:
        reservation = ledger.start(
            reservation.reservation_id,
            owner_id=reservation.owner_id,
            session_id=reservation.session_id,
            now=NOW + timedelta(milliseconds=1),
        )
    transport = RecordingTransport(http_response(valid_response_bytes()))

    with pytest.raises(BonsaiRequestError, match="^Bonsai intent request is invalid$"):
        execute(prepared, transport, ledger=ledger, reservation=reservation)

    assert transport.calls == []


def test_tampered_prepared_body_stops_before_usage_or_transport() -> None:
    original = prepared_request()
    tampered = PreparedBonsaiIntentRequest(
        request=original.request,
        source_input=original.source_input,
        prompt=original.prompt,
        body=original.body + b" ",
    )
    ledger, reservation = reserved_usage(original)
    transport = RecordingTransport(http_response(valid_response_bytes()))

    with pytest.raises(BonsaiRequestError, match="^Bonsai intent request is invalid$"):
        execute(tampered, transport, ledger=ledger, reservation=reservation)

    assert transport.calls == []
    assert ledger.snapshot().reservations[0].status == "reserved"


def test_request_boundary_does_not_import_a_network_client() -> None:
    tree = ast.parse(inspect.getsource(bonsai_request))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_from = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    forbidden = {
        "http.client",
        "httpx",
        "requests",
        "socket",
        "src.clients.bonsai_client",
        "urllib.request",
    }

    assert imported_modules.isdisjoint(forbidden)
    assert imported_from.isdisjoint(forbidden)


def test_resorted_schema_with_rebound_digest_stops_before_transport() -> None:
    original = prepared_request()
    body = json.dumps(
        json.loads(original.body), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert body != original.body
    data = original.request.model_dump(mode="python")
    data["body_sha256"] = hashlib.sha256(body).hexdigest()
    tampered = PreparedBonsaiIntentRequest(
        request=BonsaiIntentRequest.model_validate(data),
        source_input=original.source_input,
        prompt=original.prompt,
        body=body,
    )
    ledger, reservation = reserved_usage(tampered)
    transport = RecordingTransport(http_response(valid_response_bytes()))
    with pytest.raises(BonsaiRequestError, match="^Bonsai intent request is invalid$"):
        execute(tampered, transport, ledger=ledger, reservation=reservation)
    assert transport.calls == []
    assert ledger.snapshot().reservations[0].status == "reserved"
