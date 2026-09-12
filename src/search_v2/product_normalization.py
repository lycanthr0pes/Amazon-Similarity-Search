from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from decimal import InvalidOperation
from decimal import ROUND_DOWN
import hashlib
import json
import math
import re
from typing import Annotated
from typing import Literal
import unicodedata
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import ValidationError
from pydantic import field_validator
from pydantic import model_validator
from pydantic import model_serializer

from src.search_v2.outscraper_contract import OutscraperAmazonProductsRequest
from src.search_v2.outscraper_contract import outscraper_request_sha256


MAX_PRODUCT_TITLE_CHARACTERS = 500
MAX_PRODUCT_DESCRIPTION_CHARACTERS = 4_000
MAX_PRODUCT_ATTRIBUTE_CHARACTERS = 200
MAX_PRODUCT_CATEGORIES = 20
MAX_PRODUCT_FEATURES = 20
MAX_PRODUCT_IMAGES = 20
MAX_PROVIDER_REQUEST_ID_CHARACTERS = 256
MAX_PRICE_JPY = 1_000_000_000
MAX_REVIEW_COUNT = 9_223_372_036_854_775_807
MAX_RAW_TEXT_INPUT_CHARACTERS = 32_768
MAX_RAW_NUMERIC_INPUT_CHARACTERS = 256
MAX_RAW_IDENTIFIER_INPUT_CHARACTERS = 64
MAX_RAW_COLLECTION_ITEMS = 100

_INVALID_RESPONSE_MESSAGE = "Outscraper response did not match the product normalization contract"
_ASIN_PATTERN = re.compile(r"^[A-Z0-9]{10}$")
_NUMBER_PATTERN = re.compile(r"[-+]?(?:\d[\d,]*(?:\.\d+)?|\.\d+)")
_PROVIDER_REQUEST_ID_PATTERN = re.compile(r"^[!-~]+$")

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
BoundedAttribute = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_PRODUCT_ATTRIBUTE_CHARACTERS),
]
BoundedUrl = Annotated[str, StringConstraints(min_length=1, max_length=2_048)]
ProviderRequestId = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_PROVIDER_REQUEST_ID_CHARACTERS),
]
PriceJpy = Annotated[int, Field(gt=0, le=MAX_PRICE_JPY)]
AttributeName = Literal["brand", "categories", "color", "material", "features"]
TruncatedFieldName = Literal[
    "description_en",
    "features_en",
    "color_en",
    "material_en",
    "title",
    "title_en",
    "brand",
    "store_name",
    "description",
    "categories",
    "color",
    "material",
    "features",
    "availability",
    "shipping",
]
DiscardedFieldName = Literal[
    "features_en",
    "asin",
    "brand",
    "store_name",
    "description",
    "categories",
    "color",
    "material",
    "features",
    "price",
    "list_price",
    "rating",
    "review_count",
    "prime",
    "availability",
    "shipping",
    "product_url",
    "image_urls",
]
RejectionReason = Literal[
    "not_an_object",
    "missing_title",
    "unsupported_currency",
    "unknown_query_provenance",
    "unapproved_query",
    "duplicate_asin",
    "duplicate_product_url",
]


class ProductNormalizationError(ValueError):
    """A fixed-message rejection for an invalid normalization boundary input."""


class StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        revalidate_instances="always",
        frozen=True,
    )


class ProductNormalizationProfile(StrictFrozenContract):
    schema_version: Literal["2.0"]
    profile_id: Literal["observed-only-v2"]
    usd_to_jpy_rate: Annotated[int, Field(gt=0, le=1_000_000)]


class ObservedProductAttributes(StrictFrozenContract):
    brand: BoundedAttribute | None
    categories: Annotated[
        tuple[BoundedAttribute, ...],
        Field(max_length=MAX_PRODUCT_CATEGORIES),
    ]
    color: BoundedAttribute | None
    material: BoundedAttribute | None
    features: Annotated[
        tuple[BoundedAttribute, ...],
        Field(max_length=MAX_PRODUCT_FEATURES),
    ]
    unknown: Annotated[tuple[AttributeName, ...], Field(max_length=5)]

    @model_validator(mode="after")
    def validate_unknown_attributes(self) -> ObservedProductAttributes:
        expected = tuple(
            name
            for name, value in (
                ("brand", self.brand),
                ("categories", self.categories),
                ("color", self.color),
                ("material", self.material),
                ("features", self.features),
            )
            if value is None or value == ()
        )
        if self.unknown != expected:
            raise ValueError("unknown attributes must match missing observed values")
        return self


class ProductCandidateProvenance(StrictFrozenContract):
    provider: Literal["outscraper", "playwright"] = "outscraper"

    @model_serializer(mode="wrap")
    def serialize_compatible(self, handler):
        data = handler(self)
        if self.provider == "outscraper":
            data.pop("provider", None)
        return data

    outscraper_request_sha256: Digest
    query_plan_sha256: Digest
    provider_request_id: ProviderRequestId = Field(repr=False)
    query_index: Annotated[int, Field(ge=0, le=1)]
    query_language: Literal["ja", "en"]
    response_index: Annotated[int, Field(ge=0, lt=48)]

    @field_validator("provider_request_id")
    @classmethod
    def validate_provider_request_id(cls, value: str) -> str:
        if value != value.strip() or _PROVIDER_REQUEST_ID_PATTERN.fullmatch(value) is None:
            raise ValueError("provider request id is invalid")
        return value


class EnglishProductDetails(StrictFrozenContract):
    description: Annotated[str, StringConstraints(min_length=1, max_length=4000)] | None = Field(
        default=None, repr=False
    )
    features: tuple[BoundedAttribute, ...] = Field(default=(), max_length=20, repr=False)
    color: BoundedAttribute | None = Field(default=None, repr=False)
    material: BoundedAttribute | None = Field(default=None, repr=False)


class NormalizedProductCandidate(StrictFrozenContract):
    schema_version: Literal["2.0"]
    source: Literal["amazon"]
    asin: Annotated[str, StringConstraints(pattern=r"^[A-Z0-9]{10}$")] | None
    title: Annotated[
        str,
        StringConstraints(min_length=1, max_length=MAX_PRODUCT_TITLE_CHARACTERS),
    ] = Field(repr=False)
    store_name: BoundedAttribute | None = Field(repr=False)
    title_en: Annotated[str, StringConstraints(min_length=1, max_length=500)] | None = Field(
        default=None, repr=False
    )
    title_en_status: Literal["available", "unavailable"] | None = None
    details_en: EnglishProductDetails | None = Field(default=None, repr=False)
    details_en_status: Literal["available", "unavailable"] | None = None
    description: (
        Annotated[
            str,
            StringConstraints(min_length=1, max_length=MAX_PRODUCT_DESCRIPTION_CHARACTERS),
        ]
        | None
    ) = Field(repr=False)
    attributes: ObservedProductAttributes
    price_jpy: PriceJpy | None
    list_price_jpy: PriceJpy | None
    source_currency: Literal["JPY", "USD"] | None
    rating: Annotated[float, Field(ge=0.0, le=5.0)] | None
    review_count: Annotated[int, Field(ge=0, le=MAX_REVIEW_COUNT)] | None
    is_prime: bool | None
    availability: BoundedAttribute | None = Field(repr=False)
    shipping: BoundedAttribute | None = Field(repr=False)
    product_url: BoundedUrl | None = Field(repr=False)
    image_urls: Annotated[tuple[BoundedUrl, ...], Field(max_length=MAX_PRODUCT_IMAGES)] = Field(
        repr=False
    )
    truncated_fields: Annotated[tuple[TruncatedFieldName, ...], Field(max_length=20)]
    discarded_fields: Annotated[tuple[DiscardedFieldName, ...], Field(max_length=20)]
    provenance: ProductCandidateProvenance

    @model_serializer(mode="wrap")
    def serialize_compatible(self, handler):
        data = handler(self)
        if self.title_en_status is None:
            data.pop("title_en", None)
            data.pop("title_en_status", None)
        if self.details_en_status is None:
            data.pop("details_en", None)
            data.pop("details_en_status", None)
        return data

    @model_validator(mode="after")
    def validate_observed_values(self) -> NormalizedProductCandidate:
        if (self.details_en_status == "available") != (self.details_en is not None):
            raise ValueError("English details status is inconsistent")
        if (self.title_en_status == "available") != (self.title_en is not None):
            raise ValueError("English title status is inconsistent")
        if self.source_currency is None and (
            self.price_jpy is not None or self.list_price_jpy is not None
        ):
            raise ValueError("JPY prices require an observed source currency")
        if len(self.image_urls) != len(set(self.image_urls)):
            raise ValueError("image URLs must be unique")
        if len(self.truncated_fields) != len(set(self.truncated_fields)):
            raise ValueError("truncated fields must be unique")
        if len(self.discarded_fields) != len(set(self.discarded_fields)):
            raise ValueError("discarded fields must be unique")
        return self


class ProductCandidateRejection(StrictFrozenContract):
    schema_version: Literal["2.0"]
    response_index: Annotated[int, Field(ge=0, lt=48)]
    reason: RejectionReason
    duplicate_of_response_index: Annotated[int, Field(ge=0, lt=48)] | None

    @model_validator(mode="after")
    def validate_duplicate_reference(self) -> ProductCandidateRejection:
        is_duplicate = self.reason in {"duplicate_asin", "duplicate_product_url"}
        if is_duplicate != (self.duplicate_of_response_index is not None):
            raise ValueError("duplicate rejection must identify the retained candidate")
        return self


class NormalizedProductBatch(StrictFrozenContract):
    provider: Literal["outscraper", "playwright"] = "outscraper"

    @model_serializer(mode="wrap")
    def serialize_compatible(self, handler):
        data = handler(self)
        if self.provider == "outscraper":
            data.pop("provider", None)
        return data

    schema_version: Literal["2.0"]
    normalization_mode: Literal["observed_only_no_llm"]
    outscraper_request_sha256: Digest
    query_plan_sha256: Digest
    provider_request_id: ProviderRequestId = Field(repr=False)
    normalization_profile_sha256: Digest
    maximum_candidates: Literal[24, 48]
    products: Annotated[tuple[NormalizedProductCandidate, ...], Field(max_length=48)]
    rejections: Annotated[tuple[ProductCandidateRejection, ...], Field(max_length=48)]

    @field_validator("provider_request_id")
    @classmethod
    def validate_provider_request_id(cls, value: str) -> str:
        if value != value.strip() or _PROVIDER_REQUEST_ID_PATTERN.fullmatch(value) is None:
            raise ValueError("provider request id is invalid")
        return value

    @model_validator(mode="after")
    def validate_batch_bindings(self) -> NormalizedProductBatch:
        if len(self.products) + len(self.rejections) > self.maximum_candidates:
            raise ValueError("normalized batch exceeds the approved candidate limit")
        response_indexes = [item.provenance.response_index for item in self.products]
        response_indexes.extend(item.response_index for item in self.rejections)
        if len(response_indexes) != len(set(response_indexes)):
            raise ValueError("normalized batch contains duplicate response indexes")
        for product in self.products:
            provenance = product.provenance
            if (
                provenance.provider != self.provider
                or provenance.outscraper_request_sha256 != self.outscraper_request_sha256
                or provenance.query_plan_sha256 != self.query_plan_sha256
                or provenance.provider_request_id != self.provider_request_id
            ):
                raise ValueError("product provenance does not match the normalized batch")
        return self


@dataclass(frozen=True, slots=True, repr=False)
class _RawProductCandidate:
    response_index: int
    suggested_query_index: int | None
    value: object


def _raise_invalid_response() -> None:
    raise ProductNormalizationError(_INVALID_RESPONSE_MESSAGE) from None


def _canonical_json_sha256(domain: bytes, value: BaseModel) -> str:
    canonical = json.dumps(
        value.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(domain + b"\n" + canonical).hexdigest()


def product_normalization_profile_sha256(profile: ProductNormalizationProfile) -> str:
    validated = ProductNormalizationProfile.model_validate(profile)
    return _canonical_json_sha256(b"amazon-explorer-product-normalization-profile-v2", validated)


def normalized_product_batch_sha256(batch: NormalizedProductBatch) -> str:
    validated = NormalizedProductBatch.model_validate(batch)
    return _canonical_json_sha256(b"amazon-explorer-normalized-product-batch-v2", validated)


def _append_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _normalize_text(
    value: object,
    *,
    maximum: int,
    field_name: str,
    truncated_fields: list[str],
) -> str | None:
    if type(value) is not str:
        return None
    if len(value) > MAX_RAW_TEXT_INPUT_CHARACTERS:
        value = value[:MAX_RAW_TEXT_INPUT_CHARACTERS]
        _append_once(truncated_fields, field_name)
    normalized = unicodedata.normalize("NFKC", value)
    sanitized_characters: list[str] = []
    for character in normalized:
        if character.isspace():
            sanitized_characters.append(" ")
        elif not unicodedata.category(character).startswith("C"):
            sanitized_characters.append(character)
    sanitized = "".join(sanitized_characters)
    collapsed = " ".join(sanitized.split())
    if not collapsed:
        return None
    if len(collapsed) > maximum:
        collapsed = collapsed[:maximum]
        _append_once(truncated_fields, field_name)
    return collapsed


def _normalize_string_collection(
    value: object,
    *,
    maximum_items: int,
    field_name: str,
    truncated_fields: list[str],
    discarded_fields: list[str],
) -> tuple[str, ...]:
    if value is None:
        return ()
    if type(value) is not list:
        _append_once(discarded_fields, field_name)
        return ()

    result: list[str] = []
    seen: set[str] = set()
    if len(value) > MAX_RAW_COLLECTION_ITEMS:
        _append_once(truncated_fields, field_name)
    for raw in value[:MAX_RAW_COLLECTION_ITEMS]:
        normalized = _normalize_text(
            raw,
            maximum=MAX_PRODUCT_ATTRIBUTE_CHARACTERS,
            field_name=field_name,
            truncated_fields=truncated_fields,
        )
        if normalized is None:
            if raw is not None:
                _append_once(discarded_fields, field_name)
            continue
        identity = normalized.casefold()
        if identity in seen:
            continue
        if len(result) == maximum_items:
            _append_once(truncated_fields, field_name)
            break
        seen.add(identity)
        result.append(normalized)
    return tuple(result)


def _as_decimal(value: object) -> Decimal | None:
    if value is None or type(value) is bool:
        return None
    if type(value) is int:
        if value.bit_length() > 256:
            return None
        number = Decimal(value)
    elif type(value) is float:
        if not math.isfinite(value):
            return None
        number = Decimal(str(value))
    elif type(value) is str:
        if len(value) > MAX_RAW_NUMERIC_INPUT_CHARACTERS:
            return None
        match = _NUMBER_PATTERN.search(value)
        if match is None:
            return None
        try:
            number = Decimal(match.group().replace(",", ""))
        except InvalidOperation:
            return None
    else:
        return None
    return number if number.is_finite() else None


def _detect_currency(item: dict[str, object]) -> tuple[Literal["JPY", "USD"] | None, bool]:
    raw_currency = item.get("currency")
    if raw_currency is not None:
        if type(raw_currency) is not str or len(raw_currency) > MAX_RAW_NUMERIC_INPUT_CHARACTERS:
            return None, True
        currency = unicodedata.normalize("NFKC", raw_currency).strip().upper()
        if currency in {"JPY", "USD"}:
            return currency, False
        return None, True

    currency_markers: set[str] = set()
    for field_name in (
        "price",
        "old_price",
        "strike_price",
        "delivery_price",
    ):
        value = item.get(field_name)
        if type(value) is not str or len(value) > MAX_RAW_NUMERIC_INPUT_CHARACTERS:
            continue
        normalized = unicodedata.normalize("NFKC", value).upper()
        if "USD" in normalized or "$" in normalized:
            currency_markers.add("USD")
        if "JPY" in normalized or "¥" in normalized or "円" in normalized:
            currency_markers.add("JPY")
    if len(currency_markers) == 1:
        return next(iter(currency_markers)), False
    return None, False


def _first_present(item: dict[str, object], field_names: tuple[str, ...]) -> object:
    for field_name in field_names:
        value = item.get(field_name)
        if value is not None:
            return value
    return None


def _price_to_jpy(
    value: object,
    *,
    currency: Literal["JPY", "USD"] | None,
    usd_to_jpy_rate: int,
) -> int | None:
    if currency is None:
        return None
    number = _as_decimal(value)
    if number is None or number <= 0:
        return None
    if currency == "USD":
        number *= usd_to_jpy_rate
    converted = int(number.to_integral_value(rounding=ROUND_DOWN))
    if not 0 < converted <= MAX_PRICE_JPY:
        return None
    return converted


def _bounded_float(value: object, *, minimum: float, maximum: float) -> float | None:
    number = _as_decimal(value)
    if number is None:
        return None
    converted = float(number)
    return converted if minimum <= converted <= maximum else None


def _non_negative_integer(value: object) -> int | None:
    number = _as_decimal(value)
    if (
        number is None
        or number < 0
        or number > MAX_REVIEW_COUNT
        or number != number.to_integral_value()
    ):
        return None
    return int(number)


def _optional_bool(value: object) -> bool | None:
    if type(value) is bool:
        return value
    if type(value) in {int, float} and value in {0, 1}:
        return bool(value)
    if type(value) is str:
        if len(value) > MAX_RAW_NUMERIC_INPUT_CHARACTERS:
            return None
        normalized = value.strip().casefold()
        if normalized in {"1", "true", "yes", "y"}:
            return True
        if normalized in {"0", "false", "no", "n"}:
            return False
    return None


def _normalize_https_url(value: object, *, amazon_product: bool) -> str | None:
    if (
        type(value) is not str
        or len(value) > 2_048
        or value != value.strip()
        or any(unicodedata.category(character).startswith("C") for character in value)
    ):
        return None
    try:
        value.encode("ascii")
        parsed = urlsplit(value)
        port = parsed.port
    except (UnicodeEncodeError, ValueError):
        return None

    hostname = parsed.hostname
    if (
        parsed.scheme.casefold() != "https"
        or hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
    ):
        return None
    hostname = hostname.casefold()
    if hostname.endswith(".") or any(not label for label in hostname.split(".")):
        return None
    if amazon_product and not (hostname == "amazon.co.jp" or hostname.endswith(".amazon.co.jp")):
        return None

    path = parsed.path or "/"
    query = "" if amazon_product else parsed.query
    return urlunsplit(("https", hostname, path, query, ""))


def _normalize_asin(value: object) -> str | None:
    if type(value) is not str or len(value) > MAX_RAW_IDENTIFIER_INPUT_CHARACTERS:
        return None
    normalized = unicodedata.normalize("NFKC", value).strip().upper()
    return normalized if _ASIN_PATTERN.fullmatch(normalized) is not None else None


def _product_url(item: dict[str, object], discarded_fields: list[str]) -> str | None:
    saw_value = False
    for field_name in ("url", "short_url"):
        value = item.get(field_name)
        if value is None:
            continue
        saw_value = True
        normalized = _normalize_https_url(value, amazon_product=True)
        if normalized is not None:
            return normalized
    if saw_value:
        _append_once(discarded_fields, "product_url")
    return None


def _image_urls(item: dict[str, object], discarded_fields: list[str]) -> tuple[str, ...]:
    raw_values: list[object] = []
    high_res_images = item.get("high_res_images")
    if high_res_images is not None:
        if type(high_res_images) is list:
            raw_values.extend(high_res_images[:MAX_RAW_COLLECTION_ITEMS])
            if len(high_res_images) > MAX_RAW_COLLECTION_ITEMS:
                _append_once(discarded_fields, "image_urls")
        else:
            _append_once(discarded_fields, "image_urls")
    for index in range(1, 11):
        value = item.get(f"image_{index}")
        if value is not None:
            raw_values.append(value)

    result: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        normalized = _normalize_https_url(raw, amazon_product=False)
        if normalized is None:
            _append_once(discarded_fields, "image_urls")
            continue
        if normalized in seen:
            continue
        if len(result) == MAX_PRODUCT_IMAGES:
            _append_once(discarded_fields, "image_urls")
            break
        seen.add(normalized)
        result.append(normalized)
    return tuple(result)


def _raw_candidates(
    data: list[object], *, maximum_candidates: Literal[24, 48]
) -> list[_RawProductCandidate]:
    result: list[_RawProductCandidate] = []
    response_index = 0
    for group_index, group in enumerate(data):
        if type(group) is list:
            for value in group:
                if response_index >= maximum_candidates:
                    _raise_invalid_response()
                result.append(
                    _RawProductCandidate(
                        response_index=response_index,
                        suggested_query_index=group_index,
                        value=value,
                    )
                )
                response_index += 1
        else:
            if response_index >= maximum_candidates:
                _raise_invalid_response()
            result.append(
                _RawProductCandidate(
                    response_index=response_index,
                    suggested_query_index=None,
                    value=group,
                )
            )
            response_index += 1
    return result


def _query_index(
    raw: _RawProductCandidate,
    item: dict[str, object],
    request: OutscraperAmazonProductsRequest,
) -> tuple[int | None, RejectionReason | None]:
    raw_query = item.get("query")
    if raw_query is not None:
        if type(raw_query) is not str:
            return None, "unapproved_query"
        matching = [
            index for index, query in enumerate(request.provider_queries()) if query == raw_query
        ]
        if len(matching) != 1:
            return None, "unapproved_query"
        query_index = matching[0]
        if raw.suggested_query_index is not None and raw.suggested_query_index != query_index:
            return None, "unapproved_query"
        return query_index, None

    if raw.suggested_query_index is not None:
        if raw.suggested_query_index >= len(request.queries):
            return None, "unapproved_query"
        return raw.suggested_query_index, None
    if len(request.queries) == 1:
        return 0, None
    return None, "unknown_query_provenance"


def _rejection(
    raw: _RawProductCandidate,
    reason: RejectionReason,
    *,
    duplicate_of_response_index: int | None = None,
) -> ProductCandidateRejection:
    return ProductCandidateRejection(
        schema_version="2.0",
        response_index=raw.response_index,
        reason=reason,
        duplicate_of_response_index=duplicate_of_response_index,
    )


def _normalize_candidate(
    raw: _RawProductCandidate,
    *,
    request: OutscraperAmazonProductsRequest,
    request_sha256: str,
    provider_request_id: str,
    profile: ProductNormalizationProfile,
) -> tuple[NormalizedProductCandidate | None, ProductCandidateRejection | None]:
    if type(raw.value) is not dict:
        return None, _rejection(raw, "not_an_object")
    item: dict[str, object] = raw.value
    query_index, query_error = _query_index(raw, item, request)
    if query_error is not None:
        return None, _rejection(raw, query_error)
    if query_index is None:
        raise AssertionError("accepted query provenance did not identify a query")

    truncated_fields: list[str] = []
    discarded_fields: list[str] = []
    title = _normalize_text(
        item.get("name"),
        maximum=MAX_PRODUCT_TITLE_CHARACTERS,
        field_name="title",
        truncated_fields=truncated_fields,
    )
    if title is None:
        return None, _rejection(raw, "missing_title")

    title_en = None
    title_en_status = None
    if item.get("title_en_status") in ("available", "unavailable"):
        if item["title_en_status"] == "available":
            title_en = _normalize_text(
                item.get("name_en"),
                maximum=MAX_PRODUCT_TITLE_CHARACTERS,
                field_name="title_en",
                truncated_fields=truncated_fields,
            )
        title_en_status = "available" if title_en else "unavailable"

    asin = _normalize_asin(item.get("asin"))
    if item.get("asin") is not None and asin is None:
        _append_once(discarded_fields, "asin")

    details_en_status = item.get("details_en_status")
    if details_en_status not in ("available", "unavailable"):
        details_en_status = None
    details_en = None
    if details_en_status == "available":
        values = {
            key: _normalize_text(
                item.get(key + "_en"),
                maximum=4000 if key == "description" else 200,
                field_name=key + "_en",
                truncated_fields=truncated_fields,
            )
            for key in ("description", "color", "material")
        }
        details_en = EnglishProductDetails(
            **values,
            features=_normalize_string_collection(
                item.get("features_en"),
                maximum_items=20,
                field_name="features_en",
                truncated_fields=truncated_fields,
                discarded_fields=discarded_fields,
            ),
        )

    brand = _normalize_text(
        item.get("brand"),
        maximum=MAX_PRODUCT_ATTRIBUTE_CHARACTERS,
        field_name="brand",
        truncated_fields=truncated_fields,
    )
    if item.get("brand") is not None and brand is None:
        _append_once(discarded_fields, "brand")
    store_name = _normalize_text(
        item.get("store_title"),
        maximum=MAX_PRODUCT_ATTRIBUTE_CHARACTERS,
        field_name="store_name",
        truncated_fields=truncated_fields,
    )
    if item.get("store_title") is not None and store_name is None:
        _append_once(discarded_fields, "store_name")
    description = _normalize_text(
        item.get("description"),
        maximum=MAX_PRODUCT_DESCRIPTION_CHARACTERS,
        field_name="description",
        truncated_fields=truncated_fields,
    )
    if item.get("description") is not None and description is None:
        _append_once(discarded_fields, "description")
    color = _normalize_text(
        item.get("color"),
        maximum=MAX_PRODUCT_ATTRIBUTE_CHARACTERS,
        field_name="color",
        truncated_fields=truncated_fields,
    )
    if item.get("color") is not None and color is None:
        _append_once(discarded_fields, "color")
    material = _normalize_text(
        item.get("material"),
        maximum=MAX_PRODUCT_ATTRIBUTE_CHARACTERS,
        field_name="material",
        truncated_fields=truncated_fields,
    )
    if item.get("material") is not None and material is None:
        _append_once(discarded_fields, "material")
    categories = _normalize_string_collection(
        item.get("categories"),
        maximum_items=MAX_PRODUCT_CATEGORIES,
        field_name="categories",
        truncated_fields=truncated_fields,
        discarded_fields=discarded_fields,
    )
    features = _normalize_string_collection(
        item.get("features"),
        maximum_items=MAX_PRODUCT_FEATURES,
        field_name="features",
        truncated_fields=truncated_fields,
        discarded_fields=discarded_fields,
    )

    source_currency, unsupported_currency = _detect_currency(item)
    if unsupported_currency:
        return None, _rejection(raw, "unsupported_currency")
    price_value = _first_present(item, ("price_parsed", "price"))
    list_price_value = _first_present(
        item,
        ("old_price_parsed", "strike_price_parsed", "old_price", "strike_price"),
    )
    price_jpy = _price_to_jpy(
        price_value,
        currency=source_currency,
        usd_to_jpy_rate=profile.usd_to_jpy_rate,
    )
    list_price_jpy = _price_to_jpy(
        list_price_value,
        currency=source_currency,
        usd_to_jpy_rate=profile.usd_to_jpy_rate,
    )
    if price_value is not None and price_jpy is None:
        _append_once(discarded_fields, "price")
    if list_price_value is not None and list_price_jpy is None:
        _append_once(discarded_fields, "list_price")

    rating = _bounded_float(item.get("rating"), minimum=0.0, maximum=5.0)
    if item.get("rating") is not None and rating is None:
        _append_once(discarded_fields, "rating")
    review_count = _non_negative_integer(item.get("reviews"))
    if item.get("reviews") is not None and review_count is None:
        _append_once(discarded_fields, "review_count")
    is_prime = _optional_bool(item.get("prime"))
    if item.get("prime") is not None and is_prime is None:
        _append_once(discarded_fields, "prime")

    availability = _normalize_text(
        item.get("availability"),
        maximum=MAX_PRODUCT_ATTRIBUTE_CHARACTERS,
        field_name="availability",
        truncated_fields=truncated_fields,
    )
    if item.get("availability") is not None and availability is None:
        _append_once(discarded_fields, "availability")
    shipping = _normalize_text(
        item.get("shipping"),
        maximum=MAX_PRODUCT_ATTRIBUTE_CHARACTERS,
        field_name="shipping",
        truncated_fields=truncated_fields,
    )
    if item.get("shipping") is not None and shipping is None:
        _append_once(discarded_fields, "shipping")

    attributes = ObservedProductAttributes(
        brand=brand,
        categories=categories,
        color=color,
        material=material,
        features=features,
        unknown=tuple(
            name
            for name, value in (
                ("brand", brand),
                ("categories", categories),
                ("color", color),
                ("material", material),
                ("features", features),
            )
            if value is None or value == ()
        ),
    )
    query = request.queries[query_index]
    return (
        NormalizedProductCandidate(
            schema_version="2.0",
            source="amazon",
            asin=asin,
            title=title,
            title_en=title_en,
            title_en_status=title_en_status,
            details_en=details_en,
            details_en_status=details_en_status,
            store_name=store_name,
            description=description,
            attributes=attributes,
            price_jpy=price_jpy,
            list_price_jpy=list_price_jpy,
            source_currency=source_currency,
            rating=rating,
            review_count=review_count,
            is_prime=is_prime,
            availability=availability,
            shipping=shipping,
            product_url=_product_url(item, discarded_fields),
            image_urls=_image_urls(item, discarded_fields),
            truncated_fields=tuple(truncated_fields),
            discarded_fields=tuple(discarded_fields),
            provenance=ProductCandidateProvenance(
                provider="playwright"
                if request.provider == "playwright" or provider_request_id.startswith("playwright-")
                else "outscraper",
                outscraper_request_sha256=request_sha256,
                query_plan_sha256=request.query_plan_sha256,
                provider_request_id=provider_request_id,
                query_index=query_index,
                query_language=query.language,
                response_index=raw.response_index,
            ),
        ),
        None,
    )


def normalize_outscraper_products(
    response: object,
    *,
    request: OutscraperAmazonProductsRequest,
    provider_request_id: str,
    profile: ProductNormalizationProfile,
) -> NormalizedProductBatch:
    try:
        from src.search_v2.product_request import PlaywrightSearchRequest

        request_type = (
            PlaywrightSearchRequest
            if isinstance(request, PlaywrightSearchRequest)
            else OutscraperAmazonProductsRequest
        )
        validated_request = request_type.model_validate(request)
        validated_profile = ProductNormalizationProfile.model_validate(profile)
        if (
            type(provider_request_id) is not str
            or len(provider_request_id) > MAX_PROVIDER_REQUEST_ID_CHARACTERS
            or provider_request_id != provider_request_id.strip()
            or _PROVIDER_REQUEST_ID_PATTERN.fullmatch(provider_request_id) is None
        ):
            _raise_invalid_response()
    except (TypeError, ValidationError, ValueError):
        _raise_invalid_response()

    if type(response) is not dict or type(response.get("data")) is not list:
        _raise_invalid_response()
    if len(response["data"]) > validated_request.maximum_candidates:
        _raise_invalid_response()
    raw_candidates = _raw_candidates(
        response["data"], maximum_candidates=validated_request.maximum_candidates
    )

    request_digest = outscraper_request_sha256(validated_request)
    products: list[NormalizedProductCandidate] = []
    rejections: list[ProductCandidateRejection] = []
    seen_asins: dict[str, int] = {}
    seen_urls: dict[str, int] = {}

    for raw in raw_candidates:
        product, rejection = _normalize_candidate(
            raw,
            request=validated_request,
            request_sha256=request_digest,
            provider_request_id=provider_request_id,
            profile=validated_profile,
        )
        if rejection is not None:
            rejections.append(rejection)
            continue
        if product is None:
            raise AssertionError("candidate normalization returned no result")

        if product.asin is not None and product.asin in seen_asins:
            rejections.append(
                _rejection(
                    raw,
                    "duplicate_asin",
                    duplicate_of_response_index=seen_asins[product.asin],
                )
            )
            continue
        if product.asin is None and product.product_url is not None:
            duplicate_index = seen_urls.get(product.product_url)
            if duplicate_index is not None:
                rejections.append(
                    _rejection(
                        raw,
                        "duplicate_product_url",
                        duplicate_of_response_index=duplicate_index,
                    )
                )
                continue

        products.append(product)
        if product.asin is not None:
            seen_asins[product.asin] = raw.response_index
        if product.product_url is not None:
            seen_urls.setdefault(product.product_url, raw.response_index)

    try:
        return NormalizedProductBatch(
            provider="playwright"
            if validated_request.provider == "playwright"
            or provider_request_id.startswith("playwright-")
            else "outscraper",
            schema_version="2.0",
            normalization_mode="observed_only_no_llm",
            outscraper_request_sha256=request_digest,
            query_plan_sha256=validated_request.query_plan_sha256,
            provider_request_id=provider_request_id,
            normalization_profile_sha256=product_normalization_profile_sha256(validated_profile),
            maximum_candidates=validated_request.maximum_candidates,
            products=tuple(products),
            rejections=tuple(rejections),
        )
    except (TypeError, ValidationError, ValueError):
        _raise_invalid_response()
