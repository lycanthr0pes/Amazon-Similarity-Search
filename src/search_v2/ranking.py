from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Annotated
from typing import Literal
import unicodedata

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import ValidationError
from pydantic import field_validator
from pydantic import model_validator

from src.search_v2.intent import NormalizedSearchIntent
from src.search_v2.intent import search_intent_sha256
from src.search_v2.product_normalization import NormalizedProductBatch
from src.search_v2.product_normalization import NormalizedProductCandidate
from src.search_v2.product_normalization import normalized_product_batch_sha256
from src.search_v2.query_planner import SearchQueryPlan
from src.search_v2.query_planner import search_query_plan_sha256
from src.search_v2.tokenizer import tokenize_search_text


RANKING_PROFILE_DOMAIN = b"amazon-explorer-ranking-profile-v3\x00"
RANKED_PRODUCT_BATCH_DOMAIN = b"amazon-explorer-ranked-product-batch-v3\x00"
MAX_RANKED_PRODUCTS = 48
MAX_SCORE_TERMS = 128
SCORE_DECIMALS = 4
EFFECTIVE_WEIGHT_DECIMALS = 6

_INVALID_RANKING_MESSAGE = "Ranking inputs did not match the ranking contract"

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
ScoreValue = Annotated[float, Field(ge=0.0, le=1.0)]
ScoreTerm = Annotated[str, StringConstraints(min_length=1, max_length=200)]
ScoreTerms = Annotated[tuple[ScoreTerm, ...], Field(max_length=MAX_SCORE_TERMS)]
ComponentStatus = Literal["available", "missing", "disabled"]
ComponentReason = Literal[
    "scored",
    "no_intent_terms",
    "not_requested",
    "product_data_missing",
    "image_scoring_disabled",
]


class RankingError(ValueError):
    """A fixed-message rejection for invalid ranking boundary inputs."""


class StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


class RankingProfile(StrictFrozenContract):
    schema_version: Literal["3.0"]
    profile_id: Literal["ranking-v3"]
    title_weight: Literal[0.35]
    attributes_weight: Literal[0.3]
    price_weight: Literal[0.2]
    image_weight: Literal[0.1]
    review_quality_weight: Literal[0.05]
    required_term_weight: Literal[3]
    preferred_term_weight: Literal[2]
    attribute_term_weight: Literal[1]
    negative_match_penalty: Literal[0.2]
    max_negative_penalty: Literal[0.5]
    high_rating_threshold: Literal[4.0]
    maximum_rating: Literal[5.0]
    review_count_saturation: Literal[1000]
    image_scoring_enabled: Literal[False]
    score_decimals: Literal[4]

    @model_validator(mode="after")
    def validate_base_weights(self) -> RankingProfile:
        total = math.fsum(
            (
                self.title_weight,
                self.attributes_weight,
                self.price_weight,
                self.image_weight,
                self.review_quality_weight,
            )
        )
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("ranking base weights must total 1.0")
        if self.review_quality_weight >= min(
            self.title_weight,
            self.attributes_weight,
            self.price_weight,
            self.image_weight,
        ):
            raise ValueError("review quality weight must be the unique lowest weight")
        if self.high_rating_threshold >= self.maximum_rating:
            raise ValueError("high rating threshold must be below maximum rating")
        return self


RANKING_PROFILE_V3 = RankingProfile(
    schema_version="3.0",
    profile_id="ranking-v3",
    title_weight=0.35,
    attributes_weight=0.3,
    price_weight=0.2,
    image_weight=0.1,
    review_quality_weight=0.05,
    required_term_weight=3,
    preferred_term_weight=2,
    attribute_term_weight=1,
    negative_match_penalty=0.2,
    max_negative_penalty=0.5,
    high_rating_threshold=4.0,
    maximum_rating=5.0,
    review_count_saturation=1000,
    image_scoring_enabled=False,
    score_decimals=4,
)


def _identity(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _unique_terms(values: tuple[str, ...]) -> bool:
    identities = tuple(_identity(value) for value in values)
    return len(identities) == len(set(identities))


class ScoreComponent(StrictFrozenContract):
    status: ComponentStatus
    reason: ComponentReason
    score: ScoreValue | None
    base_weight: Annotated[float, Field(gt=0.0, le=1.0)]
    effective_weight: ScoreValue
    contribution: ScoreValue

    @field_validator(
        "score",
        "base_weight",
        "effective_weight",
        "contribution",
        mode="before",
    )
    @classmethod
    def validate_float_types(cls, value: object) -> object:
        if value is not None and type(value) is not float:
            raise ValueError("score component numeric values must be floats")
        if type(value) is float and not math.isfinite(value):
            raise ValueError("score component numeric values must be finite")
        return value

    @model_validator(mode="after")
    def validate_status_contract(self) -> ScoreComponent:
        if self.status == "available":
            if self.reason != "scored" or self.score is None or self.effective_weight <= 0.0:
                raise ValueError("available score component is inconsistent")
            expected = round(self.score * self.effective_weight, SCORE_DECIMALS)
            if not math.isclose(self.contribution, expected, rel_tol=0.0, abs_tol=1e-12):
                raise ValueError("score component contribution is inconsistent")
            return self

        if self.score is not None or self.effective_weight != 0.0 or self.contribution != 0.0:
            raise ValueError("unavailable score component must not contribute")
        if self.status == "disabled" and self.reason != "image_scoring_disabled":
            raise ValueError("disabled score component reason is inconsistent")
        if self.status == "missing" and self.reason in {"scored", "image_scoring_disabled"}:
            raise ValueError("missing score component reason is inconsistent")
        return self


class ScoreBreakdown(StrictFrozenContract):
    title: ScoreComponent
    attributes: ScoreComponent
    price: ScoreComponent
    image: ScoreComponent
    review_quality: ScoreComponent
    available_base_weight: ScoreValue
    pre_penalty_score: ScoreValue
    negative_penalty: ScoreValue
    total_score: ScoreValue
    title_language: Literal["ja", "en"] | None
    attribute_language: Literal["ja", "en"] | None
    matched_terms: ScoreTerms
    missing_terms: ScoreTerms
    negative_matches: ScoreTerms

    @field_validator(
        "available_base_weight",
        "pre_penalty_score",
        "negative_penalty",
        "total_score",
        mode="before",
    )
    @classmethod
    def validate_float_types(cls, value: object) -> object:
        if type(value) is not float or not math.isfinite(value):
            raise ValueError("score breakdown numeric values must be finite floats")
        return value

    @model_validator(mode="after")
    def validate_breakdown(self) -> ScoreBreakdown:
        components = (
            self.title,
            self.attributes,
            self.price,
            self.image,
            self.review_quality,
        )
        expected_weights = (
            RANKING_PROFILE_V3.title_weight,
            RANKING_PROFILE_V3.attributes_weight,
            RANKING_PROFILE_V3.price_weight,
            RANKING_PROFILE_V3.image_weight,
            RANKING_PROFILE_V3.review_quality_weight,
        )
        if tuple(component.base_weight for component in components) != expected_weights:
            raise ValueError("score breakdown base weights do not match ranking profile")
        if self.image.status != "disabled":
            raise ValueError("image ranking must remain disabled")
        if self.review_quality.status == "disabled":
            raise ValueError("review quality ranking must not be disabled")

        available = tuple(component for component in components if component.status == "available")
        expected_available_weight = round(
            math.fsum(component.base_weight for component in available),
            SCORE_DECIMALS,
        )
        if self.available_base_weight != expected_available_weight:
            raise ValueError("available score weight is inconsistent")
        effective_total = math.fsum(component.effective_weight for component in available)
        expected_effective_total = 1.0 if available else 0.0
        if not math.isclose(
            effective_total,
            expected_effective_total,
            rel_tol=0.0,
            abs_tol=2e-6,
        ):
            raise ValueError("effective score weights are not normalized")

        expected_pre_penalty = round(
            math.fsum(component.contribution for component in components),
            SCORE_DECIMALS,
        )
        if self.pre_penalty_score != expected_pre_penalty:
            raise ValueError("pre-penalty score is inconsistent")
        expected_penalty = round(
            min(
                RANKING_PROFILE_V3.max_negative_penalty,
                len(self.negative_matches) * RANKING_PROFILE_V3.negative_match_penalty,
            ),
            SCORE_DECIMALS,
        )
        if self.negative_penalty != expected_penalty:
            raise ValueError("negative penalty is inconsistent")
        expected_total = round(
            max(0.0, min(1.0, self.pre_penalty_score - self.negative_penalty)),
            SCORE_DECIMALS,
        )
        if self.total_score != expected_total:
            raise ValueError("total score is inconsistent")

        if self.title.status == "available" and self.title_language is None:
            raise ValueError("available title score requires a language")
        if self.title.status != "available" and self.title_language is not None:
            raise ValueError("unavailable title score must not select a language")
        if self.attributes.reason == "no_intent_terms" and self.attribute_language is not None:
            raise ValueError("missing attribute intent must not select a language")
        if self.attributes.status == "available" and self.attribute_language is None:
            raise ValueError("available attribute score requires a language")

        if not _unique_terms(self.matched_terms):
            raise ValueError("matched terms must be unique")
        if not _unique_terms(self.missing_terms):
            raise ValueError("missing terms must be unique")
        if not _unique_terms(self.negative_matches):
            raise ValueError("negative matches must be unique")
        matched_identities = {_identity(term) for term in self.matched_terms}
        if matched_identities.intersection(_identity(term) for term in self.missing_terms):
            raise ValueError("matched and missing terms must not overlap")
        return self


class RankedProduct(StrictFrozenContract):
    schema_version: Literal["3.0"]
    rank: Annotated[int, Field(ge=1, le=MAX_RANKED_PRODUCTS)]
    product: NormalizedProductCandidate = Field(repr=False)
    breakdown: ScoreBreakdown


class RankedProductBatch(StrictFrozenContract):
    schema_version: Literal["3.0"]
    ranking_profile_id: Literal["ranking-v3"]
    ranking_profile_sha256: Digest
    intent_sha256: Digest
    query_plan_sha256: Digest
    normalized_product_batch_sha256: Digest
    products: Annotated[tuple[RankedProduct, ...], Field(max_length=MAX_RANKED_PRODUCTS)]

    @model_validator(mode="after")
    def validate_ranked_products(self) -> RankedProductBatch:
        if self.ranking_profile_sha256 != ranking_profile_sha256():
            raise ValueError("ranked batch uses an unsupported ranking profile")
        if tuple(item.rank for item in self.products) != tuple(range(1, len(self.products) + 1)):
            raise ValueError("ranked products must have contiguous ranks")
        response_indexes = tuple(item.product.provenance.response_index for item in self.products)
        if len(response_indexes) != len(set(response_indexes)):
            raise ValueError("ranked products must have unique response indexes")
        if any(
            item.product.provenance.query_plan_sha256 != self.query_plan_sha256
            for item in self.products
        ):
            raise ValueError("ranked product query binding is inconsistent")
        sort_keys = tuple(
            (-item.breakdown.total_score, item.product.provenance.response_index)
            for item in self.products
        )
        if sort_keys != tuple(sorted(sort_keys)):
            raise ValueError("ranked products are not in stable score order")
        return self


@dataclass(frozen=True, slots=True)
class _RawComponent:
    status: ComponentStatus
    reason: ComponentReason
    score: float | None


@dataclass(frozen=True, slots=True)
class _WeightedTerm:
    value: str
    tokens: frozenset[str]
    weight: int


@dataclass(frozen=True, slots=True)
class _LanguageScore:
    language: Literal["ja", "en"]
    score: float
    total_weight: int
    matched_terms: tuple[str, ...]
    missing_terms: tuple[str, ...]


def _canonical_model_sha256(domain: bytes, value: BaseModel) -> str:
    canonical = json.dumps(
        value.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(domain + canonical).hexdigest()


def ranking_profile_sha256(profile: RankingProfile = RANKING_PROFILE_V3) -> str:
    validated = RankingProfile.model_validate(profile)
    return _canonical_model_sha256(RANKING_PROFILE_DOMAIN, validated)


def ranked_product_batch_sha256(batch: RankedProductBatch) -> str:
    validated = RankedProductBatch.model_validate(batch)
    return _canonical_model_sha256(RANKED_PRODUCT_BATCH_DOMAIN, validated)


def _safe_tokens(value: str, *, language: Literal["ja", "en"]) -> tuple[str, ...]:
    try:
        return tuple(tokenize_search_text(value, language=language))
    except (TypeError, ValueError):
        return ()


def _tokens_for_values(
    values: tuple[str, ...],
    *,
    language: Literal["ja", "en"],
) -> frozenset[str]:
    tokens: set[str] = set()
    for value in values:
        tokens.update(_safe_tokens(value, language=language))
    return frozenset(tokens)


def _optional_values(*values: str | None) -> tuple[str, ...]:
    return tuple(value for value in values if value is not None)


def _title_targets(
    intent: NormalizedSearchIntent,
    *,
    language: Literal["ja", "en"],
) -> frozenset[str]:
    if language == "ja":
        values = _optional_values(
            intent.product_name_ja,
            intent.category_ja,
            intent.brand,
            intent.model_number,
        )
    else:
        values = _optional_values(
            intent.product_name_en,
            intent.category_en,
            intent.brand,
            intent.model_number,
        )
    return _tokens_for_values(values, language=language)


def _title_score(
    intent: NormalizedSearchIntent,
    product: NormalizedProductCandidate,
) -> tuple[_RawComponent, Literal["ja", "en"] | None]:
    language_scores: list[tuple[Literal["ja", "en"], float]] = []
    for language in ("ja", "en"):
        targets = _title_targets(intent, language=language)
        if not targets:
            continue
        product_tokens = _tokens_for_values((product.title,), language=language)
        score = len(targets.intersection(product_tokens)) / len(targets)
        language_scores.append((language, score))

    if not language_scores:
        return _RawComponent("missing", "no_intent_terms", None), None
    selected_language, selected_score = language_scores[0]
    for language, score in language_scores[1:]:
        if score > selected_score:
            selected_language = language
            selected_score = score
    return _RawComponent("available", "scored", selected_score), selected_language


def _append_weighted_terms(
    result: list[_WeightedTerm],
    seen: set[str],
    values: tuple[str, ...],
    *,
    language: Literal["ja", "en"],
    weight: int,
) -> None:
    for value in values:
        identity = _identity(value)
        if identity in seen:
            continue
        tokens = frozenset(_safe_tokens(value, language=language))
        if not tokens:
            continue
        seen.add(identity)
        result.append(_WeightedTerm(value=value, tokens=tokens, weight=weight))


def _attribute_terms(
    intent: NormalizedSearchIntent,
    profile: RankingProfile,
    *,
    language: Literal["ja", "en"],
) -> tuple[_WeightedTerm, ...]:
    if language == "ja":
        required = tuple(intent.required_terms_ja)
        preferred = tuple(intent.preferred_terms_ja)
        descriptive = _optional_values(intent.category_ja, intent.color_ja)
        descriptive = (*descriptive, *intent.features_ja)
    else:
        required = tuple(intent.required_terms_en)
        preferred = tuple(intent.preferred_terms_en)
        descriptive = _optional_values(intent.category_en, intent.color_en)
        descriptive = (*descriptive, *intent.features_en)

    result: list[_WeightedTerm] = []
    seen: set[str] = set()
    _append_weighted_terms(
        result,
        seen,
        required,
        language=language,
        weight=profile.required_term_weight,
    )
    _append_weighted_terms(
        result,
        seen,
        preferred,
        language=language,
        weight=profile.preferred_term_weight,
    )
    _append_weighted_terms(
        result,
        seen,
        descriptive,
        language=language,
        weight=profile.attribute_term_weight,
    )
    if intent.brand is not None:
        _append_weighted_terms(
            result,
            seen,
            (intent.brand,),
            language=language,
            weight=profile.attribute_term_weight,
        )
    return tuple(result)


def _observed_attribute_values(product: NormalizedProductCandidate) -> tuple[str, ...]:
    attributes = product.attributes
    return (
        *_optional_values(attributes.brand, attributes.color, attributes.material),
        *attributes.categories,
        *attributes.features,
    )


def _language_attribute_score(
    terms: tuple[_WeightedTerm, ...],
    product_tokens: frozenset[str],
    *,
    language: Literal["ja", "en"],
) -> _LanguageScore:
    matched: list[str] = []
    missing: list[str] = []
    matched_weight = 0
    total_weight = 0
    for term in terms:
        total_weight += term.weight
        if term.tokens.issubset(product_tokens):
            matched.append(term.value)
            matched_weight += term.weight
        else:
            missing.append(term.value)
    score = matched_weight / total_weight if total_weight else 0.0
    return _LanguageScore(
        language=language,
        score=score,
        total_weight=total_weight,
        matched_terms=tuple(matched),
        missing_terms=tuple(missing),
    )


def _selected_attribute_language_score(
    candidates: tuple[_LanguageScore, ...],
) -> _LanguageScore:
    selected = candidates[0]
    for candidate in candidates[1:]:
        if candidate.score > selected.score:
            selected = candidate
    return selected


def _attribute_score(
    intent: NormalizedSearchIntent,
    product: NormalizedProductCandidate,
    profile: RankingProfile,
) -> tuple[
    _RawComponent,
    Literal["ja", "en"] | None,
    tuple[str, ...],
    tuple[str, ...],
]:
    terms_by_language = {
        language: _attribute_terms(intent, profile, language=language) for language in ("ja", "en")
    }
    candidates = tuple(
        _language_attribute_score(
            terms,
            frozenset(),
            language=language,
        )
        for language, terms in terms_by_language.items()
        if terms
    )
    if not candidates:
        return _RawComponent("missing", "no_intent_terms", None), None, (), ()

    observed_values = _observed_attribute_values(product)
    if not observed_values:
        selected = _selected_attribute_language_score(candidates)
        return (
            _RawComponent("missing", "product_data_missing", None),
            selected.language,
            (),
            selected.missing_terms,
        )

    scored_candidates = tuple(
        _language_attribute_score(
            terms,
            _tokens_for_values(observed_values, language=language),
            language=language,
        )
        for language, terms in terms_by_language.items()
        if terms
    )
    selected = _selected_attribute_language_score(scored_candidates)
    return (
        _RawComponent("available", "scored", selected.score),
        selected.language,
        selected.matched_terms,
        selected.missing_terms,
    )


def _price_score(
    intent: NormalizedSearchIntent,
    product: NormalizedProductCandidate,
) -> _RawComponent:
    condition = intent.price
    if condition.mode == "none":
        return _RawComponent("missing", "not_requested", None)
    if product.price_jpy is None:
        return _RawComponent("missing", "product_data_missing", None)

    price = product.price_jpy
    if condition.mode == "exact":
        target = condition.target_jpy
        if target is None:
            raise AssertionError("validated exact price is missing target_jpy")
        score = min(price, target) / max(price, target)
    elif condition.mode == "range":
        minimum = condition.min_jpy
        maximum = condition.max_jpy
        if minimum is None or maximum is None:
            raise AssertionError("validated price range is incomplete")
        if minimum <= price <= maximum:
            score = 1.0
        elif price < minimum:
            score = price / minimum
        else:
            score = maximum / price
    elif condition.mode == "min":
        minimum = condition.min_jpy
        if minimum is None:
            raise AssertionError("validated minimum price is missing min_jpy")
        score = min(1.0, price / minimum)
    else:
        maximum = condition.max_jpy
        if maximum is None:
            raise AssertionError("validated maximum price is missing max_jpy")
        score = min(1.0, maximum / price)
    return _RawComponent("available", "scored", score)


def _review_quality_score(
    product: NormalizedProductCandidate,
    profile: RankingProfile,
) -> _RawComponent:
    rating = product.rating
    review_count = product.review_count
    if rating is None or review_count is None:
        return _RawComponent("missing", "product_data_missing", None)
    if rating < profile.high_rating_threshold or review_count == 0:
        return _RawComponent("available", "scored", 0.0)

    rating_quality = rating / profile.maximum_rating
    review_volume = min(
        1.0,
        math.log1p(review_count) / math.log1p(profile.review_count_saturation),
    )
    return _RawComponent("available", "scored", rating_quality * review_volume)


def _negative_matches(
    intent: NormalizedSearchIntent,
    product: NormalizedProductCandidate,
) -> tuple[str, ...]:
    evidence = (
        product.title,
        *_optional_values(product.store_name, product.description),
        *_observed_attribute_values(product),
    )
    matched: list[str] = []
    seen: set[str] = set()
    for language, terms in (
        ("ja", intent.negative_terms_ja),
        ("en", intent.negative_terms_en),
    ):
        evidence_tokens = _tokens_for_values(evidence, language=language)
        for term in terms:
            identity = _identity(term)
            if identity in seen:
                continue
            term_tokens = frozenset(_safe_tokens(term, language=language))
            if term_tokens and term_tokens.issubset(evidence_tokens):
                seen.add(identity)
                matched.append(term)
    return tuple(matched)


def _component(
    raw: _RawComponent,
    *,
    base_weight: float,
    available_base_weight: float,
) -> ScoreComponent:
    if raw.status != "available":
        return ScoreComponent(
            status=raw.status,
            reason=raw.reason,
            score=None,
            base_weight=float(base_weight),
            effective_weight=0.0,
            contribution=0.0,
        )
    if raw.score is None:
        raise AssertionError("available component is missing its score")
    score = round(max(0.0, min(1.0, raw.score)), SCORE_DECIMALS)
    effective_weight = round(
        base_weight / available_base_weight,
        EFFECTIVE_WEIGHT_DECIMALS,
    )
    return ScoreComponent(
        status="available",
        reason="scored",
        score=float(score),
        base_weight=float(base_weight),
        effective_weight=float(effective_weight),
        contribution=float(round(score * effective_weight, SCORE_DECIMALS)),
    )


def _score_product(
    intent: NormalizedSearchIntent,
    product: NormalizedProductCandidate,
    profile: RankingProfile,
) -> ScoreBreakdown:
    raw_title, title_language = _title_score(intent, product)
    raw_attributes, attribute_language, matched_terms, missing_terms = _attribute_score(
        intent,
        product,
        profile,
    )
    raw_price = _price_score(intent, product)
    raw_image = _RawComponent("disabled", "image_scoring_disabled", None)
    raw_review_quality = _review_quality_score(product, profile)
    raw_components = (
        raw_title,
        raw_attributes,
        raw_price,
        raw_image,
        raw_review_quality,
    )
    base_weights = (
        profile.title_weight,
        profile.attributes_weight,
        profile.price_weight,
        profile.image_weight,
        profile.review_quality_weight,
    )
    available_base_weight = math.fsum(
        weight
        for raw, weight in zip(raw_components, base_weights, strict=True)
        if raw.status == "available"
    )
    components = tuple(
        _component(
            raw,
            base_weight=weight,
            available_base_weight=available_base_weight,
        )
        for raw, weight in zip(raw_components, base_weights, strict=True)
    )
    negative_matches = _negative_matches(intent, product)
    negative_penalty = round(
        min(
            profile.max_negative_penalty,
            len(negative_matches) * profile.negative_match_penalty,
        ),
        SCORE_DECIMALS,
    )
    pre_penalty_score = round(
        math.fsum(component.contribution for component in components),
        SCORE_DECIMALS,
    )
    total_score = round(
        max(0.0, min(1.0, pre_penalty_score - negative_penalty)),
        SCORE_DECIMALS,
    )
    return ScoreBreakdown(
        title=components[0],
        attributes=components[1],
        price=components[2],
        image=components[3],
        review_quality=components[4],
        available_base_weight=float(round(available_base_weight, SCORE_DECIMALS)),
        pre_penalty_score=float(pre_penalty_score),
        negative_penalty=float(negative_penalty),
        total_score=float(total_score),
        title_language=title_language,
        attribute_language=attribute_language,
        matched_terms=matched_terms,
        missing_terms=missing_terms,
        negative_matches=negative_matches,
    )


def _raise_invalid_ranking() -> None:
    raise RankingError(_INVALID_RANKING_MESSAGE) from None


def rank_product_batch(
    intent: NormalizedSearchIntent,
    query_plan: SearchQueryPlan,
    product_batch: NormalizedProductBatch,
    *,
    profile: RankingProfile = RANKING_PROFILE_V3,
) -> RankedProductBatch:
    try:
        validated_intent = NormalizedSearchIntent.model_validate(intent)
        validated_query_plan = SearchQueryPlan.model_validate(query_plan)
        validated_product_batch = NormalizedProductBatch.model_validate(product_batch)
        validated_profile = RankingProfile.model_validate(profile)
        intent_digest = search_intent_sha256(validated_intent)
        query_plan_digest = search_query_plan_sha256(validated_query_plan)
        if (
            validated_query_plan.intent_sha256 != intent_digest
            or validated_product_batch.query_plan_sha256 != query_plan_digest
            or validated_profile.profile_id != RANKING_PROFILE_V3.profile_id
            or ranking_profile_sha256(validated_profile) != ranking_profile_sha256()
        ):
            _raise_invalid_ranking()

        scored = tuple(
            (product, _score_product(validated_intent, product, validated_profile))
            for product in validated_product_batch.products
        )
        ordered = sorted(
            scored,
            key=lambda item: (
                -item[1].total_score,
                item[0].provenance.response_index,
            ),
        )
        ranked_products = tuple(
            RankedProduct(
                schema_version="3.0",
                rank=rank,
                product=product,
                breakdown=breakdown,
            )
            for rank, (product, breakdown) in enumerate(ordered, start=1)
        )
        return RankedProductBatch(
            schema_version="3.0",
            ranking_profile_id=validated_profile.profile_id,
            ranking_profile_sha256=ranking_profile_sha256(validated_profile),
            intent_sha256=intent_digest,
            query_plan_sha256=query_plan_digest,
            normalized_product_batch_sha256=normalized_product_batch_sha256(
                validated_product_batch
            ),
            products=ranked_products,
        )
    except RankingError:
        raise
    except (AssertionError, TypeError, ValidationError, ValueError):
        _raise_invalid_ranking()
