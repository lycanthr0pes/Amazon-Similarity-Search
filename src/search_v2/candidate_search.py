"""Local candidate discovery: retrieval approval, observed attributes, confirmation, evaluation.

Injected providers are the only execution boundary. Candidate retrieval is not a
final-search approval, and later selections never rewrite retrieval provenance.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from threading import RLock
from typing import Literal, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
    model_serializer,
)

from src.search_v2.lexical_structure import ProductStructure, validate_structure
from src.search_v2.product_phrase import ProductPhraseReview
from src.search_v2.condition_language import (
    PROFILE as LANGUAGE_PROFILE,
    analyze_conditions,
    language_digest,
)
from src.search_v2.candidate_queries import build_candidate_queries, candidate_source_sha256
from src.search_v2.candidate_diagnostics import CandidateEvaluationError, CandidatePreparationError
from src.search_v2.bonsai_visual_conditions import build_visual_request, parse_visual_response
from src.search_v2.bonsai_query_terms import (
    MAX_QUERY_OPTIONS,
    QueryExpansion,
    propose_query_terms,
    query_options,
)
from src.search_v2.counterfactual_image import VisualConditionSet
from src.search_v2.dynamic_attributes import _identity, _unit_key, _unit_spellings
from src.search_v2.dynamic_product_evidence import _UNITS
from src.search_v2.observed_attributes import (
    ObservedSpecification,
    discover_specifications,
    observed_option_id,
    product_fields,
)
from src.search_v2.outscraper_contract import (
    build_outscraper_request,
)
from src.search_v2.product_request import (
    ProductSearchRequest,
    build_product_request,
    rebuild_product_request,
    product_request_sha256,
)
from src.search_v2.product_evidence import (
    build_product_evidence,
    normalized_product_candidate_sha256,
)
from src.search_v2.product_normalization import (
    NormalizedProductBatch,
    NormalizedProductCandidate,
    ProductNormalizationProfile,
    normalize_outscraper_products,
    normalized_product_batch_sha256,
)
from src.search_v2.query_planner import SearchQuery, SearchQueryPlan
from src.search_v2.ranking import _title_score
from src.search_v2.candidate_title import TitleComparison, build_title_comparison, score_title
from src.search_v2.condition_terms import ConditionTermBundle
from src.search_v2.condition_weighting import ConditionWeighting, build_condition_weighting
from src.search_v2.candidate_bilingual import (
    BilingualTextScore,
    BilingualTitleScore,
    score_bilingual,
    title_scores,
)
from src.search_v2.candidate_text import CandidateTextScore, score_conditions, candidate_sort_key
from src.search_v2.requirement_evaluation import (
    TypedProductEvaluation,
    adjudicate_requirement,
    build_evidence_observation,
    evaluate_typed_product,
)
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from src.search_v2.typed_requirements import (
    AttributeDefinition,
    AttributeRegistry,
    DecimalObservedValue,
    DecimalTarget,
    EvidenceRule,
    TypedRequirement,
    TypedRequirementDraft,
    normalize_typed_requirements,
)


_PROFILE = hashlib.sha256(b"candidate-observed-evaluation-v1").hexdigest()


def _digest(value):
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _time(value):
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("Candidate operations require UTC timestamps")
    return value


def _factor(source, target):
    if set(_unit_spellings(source)) & set(_unit_spellings(target)):
        return Decimal(1)
    if source in _UNITS and target in _UNITS and _UNITS[source][0] == _UNITS[target][0]:
        return _UNITS[source][1] / _UNITS[target][1]
    return None


class _Frozen(BaseModel):
    model_config = ConfigDict(
        frozen=True, strict=True, extra="forbid", revalidate_instances="always"
    )


class CandidatePlan(_Frozen):
    purpose: Literal["candidate_retrieval_only"] = "candidate_retrieval_only"
    owner_id: str
    session_id: str
    source_sha256: str
    query_plan: SearchQueryPlan = Field(repr=False)
    request: ProductSearchRequest = Field(repr=False)
    pending_quotes: tuple[str, ...] = Field(repr=False)
    image_prompt: str = Field(repr=False)
    visual_conditions: VisualConditionSet | None = Field(default=None, repr=False)
    source_structure: ProductStructure | None = Field(default=None, repr=False)
    product_review: ProductPhraseReview | None = Field(default=None, repr=False)
    image_preparation: Literal["text-only-v1"] | None = None
    visual_request_sha256: str | None = None
    visual_response_sha256: str | None = None
    query_expansion: QueryExpansion | None = Field(default=None, repr=False)
    query_options: tuple[SearchQuery, ...] = Field(
        default=(), repr=False, max_length=MAX_QUERY_OPTIONS
    )
    selected_query_index: int = Field(default=0, ge=0, le=MAX_QUERY_OPTIONS - 1)
    title_comparison: TitleComparison | None = Field(default=None, repr=False)
    condition_terms: ConditionTermBundle | None = Field(default=None, repr=False)
    condition_weighting: ConditionWeighting | None = None
    condition_language_profile: Literal["condition-language-v1"] | None = None
    condition_language_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    normalization_profile_sha256: str
    created_at: datetime
    expires_at: datetime | None

    @model_serializer(mode="wrap")
    def serialize_compatible(self, handler):
        data = handler(self)
        if self.condition_weighting is None:
            data.pop("condition_weighting", None)
        if self.image_preparation is None:
            data.pop("image_preparation", None)
        if self.condition_language_profile is None:
            data.pop("condition_language_profile", None)
            data.pop("condition_language_sha256", None)
        if self.title_comparison is None:
            data.pop("title_comparison", None)
        if self.condition_terms is None:
            data.pop("condition_terms", None)
        return data

    @model_validator(mode="after")
    def validate_query_selection(self):
        if self.image_preparation == "text-only-v1" and (
            self.visual_request_sha256 is not None
            or self.visual_response_sha256 is not None
            or (
                self.visual_conditions is not None
                and any(
                    c.contrast is not None or c.focus is not None
                    for c in self.visual_conditions.conditions
                )
            )
        ):
            raise ValueError("Text-only preparation contains image inference")
        if (self.condition_language_profile is None) != (self.condition_language_sha256 is None):
            raise ValueError("Condition language binding is incomplete")
        if self.condition_terms is not None and (
            self.title_comparison is None
            or self.condition_terms.source_sha256 != self.source_sha256
        ):
            raise ValueError("Condition terms belong to another source")
        if (
            self.query_expansion is not None
            and self.query_expansion.profile_id == "product-query-terms-v1"
            and self.product_review is None
        ):
            raise ValueError("Product suggestions require their source review")
        if self.product_review is not None and (
            self.product_review.source_sha256 != self.source_sha256
            or self.product_review.structure != self.source_structure
            or self.product_review.expansion != self.query_expansion
        ):
            raise ValueError("Product review belongs to another candidate plan")
        if self.source_structure is not None:
            original = self.source_structure.original_source
            if original is None or candidate_source_sha256(original) != self.source_sha256:
                raise ValueError("Syntax structure belongs to another original source")
            validate_structure(original, self.source_structure)
        if (
            self.query_expansion is not None
            and self.query_expansion.source_sha256 != self.source_sha256
        ):
            raise ValueError("Query suggestions belong to another source")
        if (
            not self.query_options
            or self.selected_query_index >= len(self.query_options)
            or self.query_options != query_options(self.query_options[0], self.query_expansion)
            or self.query_plan.queries != [self.query_options[self.selected_query_index]]
            or self.request != rebuild_product_request(self.request, self.query_plan)
        ):
            raise ValueError("Query selection and request are inconsistent")
        return self


@dataclass(frozen=True, repr=False)
class FetchedCandidates:
    request_sha256: str
    provider_request_id: str
    response: object


class CandidateTransport(Protocol):
    def fetch(self, request: ProductSearchRequest) -> FetchedCandidates: ...


class BonsaiEvaluator(Protocol):
    def evaluate(self, request: bytes) -> bytes: ...


class AttributeOption(_Frozen):
    option_id: str
    label: str
    unit: str
    condition_ids: tuple[str, ...]
    evidence: tuple[ObservedSpecification, ...] = Field(repr=False)


class CandidateReview(_Frozen):
    sha256: str
    product_batch_sha256: str
    options: tuple[AttributeOption, ...]
    unresolved: tuple[str, ...]
    conditions: tuple[dict, ...] = Field(repr=False)
    automatic: tuple[tuple[str, str], ...]


class CandidateRankedProduct(_Frozen):
    product: NormalizedProductCandidate = Field(repr=False)
    evaluation: TypedProductEvaluation
    lexical_score: float = Field(ge=0.0, le=1.0)
    text_score: BilingualTextScore | CandidateTextScore | None = None
    title_scores: BilingualTitleScore | None = None

    @model_serializer(mode="wrap")
    def serialize_compatible(self, handler):
        data = handler(self)
        if self.text_score is None:
            data.pop("text_score", None)
        if self.title_scores is None:
            data.pop("title_scores", None)
        return data


class CandidateRanking(_Frozen):
    profile_id: Literal[
        "candidate-confirmed-lexical-v2",
        "candidate-confirmed-lexical-v3",
        "candidate-confirmed-lexical-v4",
        "candidate-confirmed-lexical-v5",
    ] = "candidate-confirmed-lexical-v3"
    retrieval_plan_sha256: str
    review_sha256: str
    confirmation_sha256: str
    retrieval_plan: CandidatePlan = Field(repr=False)
    attribute_review: CandidateReview = Field(repr=False)
    confirmed_selections: tuple[tuple[str, str], ...]
    requirements: tuple[TypedRequirement, ...] = Field(repr=False)
    registry: AttributeRegistry = Field(repr=False)
    product_batch: NormalizedProductBatch = Field(repr=False)
    products: tuple[CandidateRankedProduct, ...]
    visual_evaluation_status: Literal["not_requested", "pending"]

    @model_validator(mode="after")
    def validate_text_scoring(self):
        weighting = self.retrieval_plan.condition_weighting
        if weighting is not None:
            ids = {c["condition_id"] for c in self.attribute_review.conditions}
            if self.retrieval_plan.visual_conditions:
                ids.update(c.condition_id for c in self.retrieval_plan.visual_conditions.conditions)
            if set(dict(weighting.positions)) != ids or self.retrieval_plan_sha256 != _digest(
                self.retrieval_plan
            ):
                raise ValueError("Candidate condition positions do not match its plan")
        comparison = self.retrieval_plan.title_comparison
        if (
            self.profile_id in {"candidate-confirmed-lexical-v4", "candidate-confirmed-lexical-v5"}
        ) != (comparison is not None):
            raise ValueError("Candidate text profile does not match its plan")
        bundle = self.retrieval_plan.condition_terms
        if (self.profile_id == "candidate-confirmed-lexical-v5") != (bundle is not None):
            raise ValueError("Bilingual profile does not match its terms")
        if bundle:
            bound = {
                c["condition_id"]: (c["source_quote"], c["strength"], False)
                for c in self.attribute_review.conditions
            }
            if self.retrieval_plan.visual_conditions:
                bound.update(
                    {
                        v.condition_id: (v.source_phrase, v.strength, True)
                        for v in self.retrieval_plan.visual_conditions.conditions
                    }
                )
            actual = {
                c.condition_id: (c.source_ja, c.strength, c.visual) for c in bundle.conditions
            }
            if actual != bound:
                raise ValueError("Condition terms do not match source conditions")
        labels = {c["condition_id"]: c["label"] for c in self.attribute_review.conditions}
        options = {o.option_id: o.label for o in self.attribute_review.options}
        labels.update({cid: options[oid] for cid, oid in self.confirmed_selections})
        for row in self.products:
            if comparison is None:
                if row.text_score is not None:
                    raise ValueError("Legacy candidate cannot contain new text scores")
                continue
            expected = (
                score_bilingual(
                    row.product,
                    self.requirements,
                    self.registry,
                    row.evaluation,
                    labels,
                    bundle,
                    weighting=self.retrieval_plan.condition_weighting,
                )
                if bundle
                else score_conditions(
                    row.product,
                    self.requirements,
                    self.registry,
                    row.evaluation,
                    labels,
                    weighting=self.retrieval_plan.condition_weighting,
                )
            )
            title = title_scores(comparison, row.product) if bundle else None
            if (
                row.title_scores != title
                or row.text_score != expected
                or row.lexical_score
                != (title.score if title else score_title(comparison, row.product.title))
            ):
                raise ValueError("Candidate text score does not match its evidence")
        if comparison is not None and list(self.products) != sorted(
            self.products, key=lambda row: candidate_sort_key(row, row.lexical_score)
        ):
            raise ValueError("Candidate text order is invalid")
        return self

    @field_validator("requirements", mode="before")
    @classmethod
    def restore_json_targets(cls, value: object, info: ValidationInfo) -> object:
        """Decode serialized Decimal targets only at this result's JSON boundary.

        Python callers still need actual Decimal values. JSON arrays in this
        field become domain tuples; element types and all other rules stay strict.
        """
        if info.mode != "json" or type(value) is not list:
            return value
        restored = []
        for requirement in value:
            target = requirement.get("expected_value") if type(requirement) is dict else None
            if type(target) is dict and target.get("value_type") == "decimal":
                target = target.copy()
                for bound in ("minimum", "maximum"):
                    if bound not in target or target[bound] is None:
                        continue
                    raw = target[bound]
                    if (
                        type(raw) is not str
                        or len(raw) > 64
                        or re.fullmatch(
                            r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]{1,3})?", raw
                        )
                        is None
                    ):
                        raise ValueError("Invalid serialized candidate decimal target")
                    try:
                        target[bound] = Decimal(raw)
                    except InvalidOperation:
                        raise ValueError("Invalid serialized candidate decimal target") from None
                # Retain the shared finite/range/precision/unit/extra-field rules.
                requirement = {
                    **requirement,
                    "expected_value": DecimalTarget.model_validate(target),
                }
            elif (
                type(target) is dict
                and target.get("value_type") in ("enum", "text_set")
                and type(target.get("values")) is list
            ):
                # A before-validator returns Python containers to pydantic;
                # preserve the JSON array -> tuple behavior for mixed targets.
                requirement = {
                    **requirement,
                    "expected_value": {**target, "values": tuple(target["values"])},
                }
            restored.append(requirement)
        return tuple(restored)


def _conditions(facts):
    return tuple(
        {
            "condition_id": f"condition-{i + 1:03}",
            "source_quote": f.quote,
            "label": f.label,
            "target": f.target.copy(),
            "operator": f.operator,
            "strength": f.strength,
            "attribute_key": f.key,
        }
        for i, f in enumerate(facts)
    )


class CandidateSearch:
    """One owner/session, one retrieval, one complete selection, no automatic retries."""

    def __init__(
        self,
        source,
        *,
        owner_id,
        session_id,
        postal_code,
        normalization_profile,
        now,
        visual_extractor: BonsaiEvaluator | None = None,
        query_expander: BonsaiEvaluator | None = None,
        lexical_expander=None,
        condition_expander=None,
        contrast_resolver=None,
        source_parser=None,
        plan_lifetime=timedelta(minutes=15),
        japanese_search_urls=False,
        allow_empty_visual=False,
        image_mode="on",
    ):
        if plan_lifetime is not None and (
            type(plan_lifetime) is not timedelta or plan_lifetime <= timedelta(0)
        ):
            raise ValueError("Invalid candidate plan lifetime")
        for value in (owner_id, session_id):
            if type(value) is not str or not 0 < len(value) <= 128 or value.strip() != value:
                raise ValueError("Invalid candidate owner or session")
        self._normalization = ProductNormalizationProfile.model_validate(normalization_profile)
        _time(now)
        if query_expander is not None and lexical_expander is not None:
            raise ValueError("Choose one query suggestion provider")
        analyze_conditions(source)
        structure = None
        if source_parser is not None:
            try:
                structure = validate_structure(source, source_parser.analyze(source))
            except CandidatePreparationError:
                raise
            except Exception:
                raise CandidatePreparationError("product_scope") from None
        product_review = None
        if structure is not None and callable(getattr(lexical_expander, "prepare", None)):
            product_review = ProductPhraseReview.model_validate(
                lexical_expander.prepare(source, structure)
            )
        conditions, request_hash, response_hash = None, None, None
        if image_mode not in {"on", "off"}:
            raise ValueError("Invalid preparation image mode")
        if image_mode == "off":
            from src.search_v2.bonsai_visual_conditions import _visual_clauses
            from src.search_v2.condition_language import interpret_clause
            from src.search_v2.counterfactual_image import (
                VisualConditionDraft,
                build_visual_condition_set,
            )

            # Retain source-owned appearance phrases for text scoring without generating contrasts.
            clauses = _visual_clauses(source, structure)
            if clauses:
                conditions = build_visual_condition_set(
                    source_input=source,
                    drafts=tuple(
                        VisualConditionDraft(
                            source_phrase=phrase, strength=interpret_clause(phrase).strength
                        )
                        for phrase in clauses
                    ),
                )
            visual_extractor = None
        if visual_extractor is not None and allow_empty_visual:
            from src.search_v2.bonsai_visual_conditions import _visual_clauses

            if not _visual_clauses(source, structure):
                visual_extractor = None
        if visual_extractor is not None:
            try:
                request = build_visual_request(
                    source, structure=structure, contrast_resolver=contrast_resolver
                )
                if any(e.strength == "neutral" for e in analyze_conditions(source)):
                    import json

                    if not json.loads(json.loads(request)["messages"][1]["content"])["clauses"]:
                        raise CandidatePreparationError("empty_conditions")
            except CandidatePreparationError as error:
                error.product_review = product_review
                raise
            except Exception:
                raise CandidatePreparationError(
                    "request_build", product_review=product_review
                ) from None
            try:
                response = visual_extractor.evaluate(request)
                conditions = parse_visual_response(
                    source,
                    response,
                    structure=structure,
                    require_contrast=True,
                    contrast_resolver=contrast_resolver,
                )
            except CandidatePreparationError as error:
                error.product_review = product_review
                raise
            except Exception:
                raise CandidatePreparationError(
                    "unexpected", visual_extraction=True, product_review=product_review
                ) from None
            request_hash = hashlib.sha256(request).hexdigest()
            response_hash = hashlib.sha256(response).hexdigest()
        try:
            self._queries = build_candidate_queries(
                source, visual_conditions=conditions, structure=structure
            )
        except CandidatePreparationError as error:
            error.product_review = product_review
            raise
        except Exception:
            raise CandidatePreparationError("query_build", product_review=product_review) from None
        self._source = source
        expansion = (
            propose_query_terms(
                source, self._queries.retrieval_intent.product_name_ja, query_expander
            )
            if query_expander is not None
            else None
        )
        if lexical_expander is not None:
            expansion = (
                product_review.expansion
                if product_review is not None
                else lexical_expander.propose(
                    source, self._queries.retrieval_intent.product_name_ja
                )
            )
            if expansion.profile_id not in {
                "dictionary-query-terms-v1",
                "dictionary-query-terms-v2",
                "product-query-terms-v1",
            }:
                raise ValueError("Unexpected lexical suggestion profile")
        self._plan = CandidatePlan(
            owner_id=owner_id,
            session_id=session_id,
            source_sha256=candidate_source_sha256(source),
            condition_language_profile=LANGUAGE_PROFILE,
            condition_language_sha256=language_digest(source, structure=structure),
            query_plan=self._queries.query_plan,
            request=(
                build_outscraper_request(
                    self._queries.query_plan, postal_code=postal_code, japanese_search_urls=True
                )
                if japanese_search_urls
                else build_product_request(self._queries.query_plan, postal_code=postal_code)
            ),
            pending_quotes=tuple(
                f.quote for f in self._queries.facts if f.key == "custom" and f.label is None
            ),
            image_prompt=self._queries.image_prompt,
            visual_conditions=conditions,
            image_preparation="text-only-v1" if image_mode == "off" else None,
            source_structure=structure,
            product_review=product_review,
            visual_request_sha256=request_hash,
            visual_response_sha256=response_hash,
            query_expansion=expansion,
            query_options=query_options(self._queries.query_plan.queries[0], expansion),
            title_comparison=build_title_comparison(
                source, self._queries.retrieval_intent, expansion
            ),
            normalization_profile_sha256=_digest(self._normalization),
            created_at=_time(now),
            expires_at=None if plan_lifetime is None else now + plan_lifetime,
        )
        self._initialize_evaluation()
        self._plan = CandidatePlan.model_validate(
            self._plan.model_copy(
                update={
                    "condition_weighting": build_condition_weighting(
                        source, self._conditions, conditions
                    ),
                }
            )
        )
        expand_conditions = (
            condition_expander.prepare
            if condition_expander is not None
            else getattr(lexical_expander, "prepare_conditions", None)
        )
        if callable(expand_conditions):
            bundle = ConditionTermBundle.model_validate(
                expand_conditions(source, self._conditions, conditions)
            )
            self._plan = CandidatePlan.model_validate(
                self._plan.model_copy(update={"condition_terms": bundle})
            )

    @classmethod
    def from_approved_plan(
        cls,
        plan,
        *,
        source,
        owner_id,
        plan_sha256,
        human_confirmed,
        normalization_profile,
        now,
        use_playwright=False,
    ):
        """Prepare a new authorized retrieval, retaining saved inference provenance."""
        plan = CandidatePlan.model_validate(plan)
        profile = ProductNormalizationProfile.model_validate(normalization_profile)
        now = _time(now)
        if (
            human_confirmed is not True
            or owner_id != plan.owner_id
            or plan_sha256 != _digest(plan)
            or candidate_source_sha256(source) != plan.source_sha256
            or _digest(profile) != plan.normalization_profile_sha256
            or now < plan.created_at
        ):
            raise ValueError("Saved search requires a new bound human authorization")
        queries = build_candidate_queries(
            source,
            visual_conditions=plan.visual_conditions,
            structure=plan.source_structure,
            language_profile=plan.condition_language_profile,
        )
        if (
            plan.condition_language_profile
            and language_digest(source, structure=plan.source_structure)
            != plan.condition_language_sha256
        ):
            raise ValueError("Saved condition language changed")
        pending = tuple(f.quote for f in queries.facts if f.key == "custom" and f.label is None)
        if (
            queries.query_plan.intent_sha256 != plan.query_plan.intent_sha256
            or queries.query_plan.queries[0] != plan.query_options[0]
            or queries.image_prompt != plan.image_prompt
            or pending != plan.pending_quotes
            or (
                plan.title_comparison is not None
                and plan.title_comparison
                != build_title_comparison(source, queries.retrieval_intent, plan.query_expansion)
            )
        ):
            raise ValueError("Saved search no longer matches its original conditions")
        instance = cls.__new__(cls)
        instance._normalization, instance._source, instance._queries = profile, source, queries
        instance._plan = CandidatePlan.model_validate(
            plan.model_copy(
                update={
                    "created_at": now,
                    "expires_at": None if use_playwright else now + timedelta(minutes=15),
                    "request": build_product_request(
                        plan.query_plan, postal_code=plan.request.postal_code
                    )
                    if use_playwright
                    else plan.request,
                }
            )
        )
        instance._initialize_evaluation()
        if (
            plan.condition_weighting is not None
            and plan.condition_weighting
            != build_condition_weighting(source, instance._conditions, plan.visual_conditions)
        ):
            raise ValueError("Saved condition positions changed")
        return instance

    def _initialize_evaluation(self):
        self._conditions = _conditions(self._queries.facts)
        price = self._queries.retrieval_intent.price
        if price.source == "explicit" and price.mode != "none":
            minimum = price.target_jpy if price.mode == "exact" else price.min_jpy
            maximum = price.target_jpy if price.mode == "exact" else price.max_jpy
            self._conditions += (
                {
                    "condition_id": "condition-price",
                    "source_quote": self._queries.price_quote or self._source,
                    "label": "価格",
                    "target": {
                        "value_type": "decimal",
                        "unit": "jpy",
                        "minimum": minimum,
                        "maximum": maximum,
                    },
                    "operator": "between"
                    if minimum is not None and maximum is not None
                    else "at_least"
                    if minimum is not None
                    else "at_most",
                    "strength": self._queries.price_strength,
                    "attribute_key": "custom",
                },
            )
        self._state = "retrieval_review"
        self._lock = RLock()
        self._batch = self._review = self._confirmation = None
        self._selected = {}
        self._fields = self._specifications = ()

    @property
    def plan(self):
        return self._plan.model_copy(deep=True)

    @property
    def plan_sha256(self):
        return _digest(self._plan)

    def _check(self, owner_id, now, expected_state):
        if (
            owner_id != self._plan.owner_id
            or _time(now) < self._plan.created_at
            or (self._plan.expires_at is not None and now >= self._plan.expires_at)
            or self._state != expected_state
        ):
            raise ValueError("Candidate operation does not match owner, lifetime, or state")

    def select_search_query(self, *, owner_id, plan_sha256, index, now):
        with self._lock:
            self._check(owner_id, now, "retrieval_review")
            if (
                plan_sha256 != self.plan_sha256
                or type(index) is not int
                or not 0 <= index < len(self._plan.query_options)
            ):
                raise ValueError("Query selection does not match the current plan")
            query_plan = SearchQueryPlan(
                schema_version="2.0",
                intent_sha256=self._queries.query_plan.intent_sha256,
                queries=[self._plan.query_options[index].model_copy(deep=True)],
            )
            self._plan = CandidatePlan.model_validate(
                self._plan.model_copy(
                    update={
                        "query_plan": query_plan,
                        "selected_query_index": index,
                        "request": rebuild_product_request(self._plan.request, query_plan),
                    }
                )
            )
            return self.plan

    def approve_and_fetch(
        self,
        *,
        owner_id,
        plan_sha256,
        transport: CandidateTransport,
        now,
    ):
        with self._lock:
            self._check(owner_id, now, "retrieval_review")
            if plan_sha256 != self.plan_sha256:
                raise ValueError("Candidate retrieval plan changed")
            self._state = (
                "fetching"  # Claim before calling injected code, including re-entrant calls.
            )
        try:
            result = transport.fetch(self._plan.request.model_copy(deep=True))
            if type(
                result
            ) is not FetchedCandidates or result.request_sha256 != product_request_sha256(
                self._plan.request
            ):
                raise ValueError("Candidate response belongs to another request")
            self._batch = normalize_outscraper_products(
                result.response,
                request=self._plan.request,
                provider_request_id=result.provider_request_id,
                profile=self._normalization,
            )
            self._fields = product_fields(self._batch)
            self._specifications = discover_specifications(self._fields)
            self._review = self._build_review()
            self._state = "attribute_review"
            return self._review.model_copy(deep=True)
        except Exception:
            self._state = "failed"
            raise ValueError("Candidate retrieval or extraction failed") from None

    def _build_review(self):
        grouped = {}
        for spec in self._specifications:
            grouped.setdefault((spec.label, spec.unit), []).append(spec)
        options, automatic = [], []
        numeric = [
            c
            for c in self._conditions
            if c["attribute_key"] == "custom"
            and "unit" in c["target"]
            and c["condition_id"] != "condition-price"
        ]
        for (label, unit), evidence in sorted(grouped.items()):
            applicable = tuple(
                c["condition_id"] for c in numeric if _factor(unit, c["target"]["unit"]) is not None
            )
            if applicable:
                options.append(
                    AttributeOption(
                        option_id=observed_option_id(label, unit),
                        label=label,
                        unit=unit,
                        condition_ids=applicable,
                        evidence=tuple(evidence),
                    )
                )
        for condition in numeric:
            matching = [
                o
                for o in options
                if condition["condition_id"] in o.condition_ids and condition["label"] == o.label
            ]
            if condition["label"] is not None and len(matching) == 1:
                automatic.append((condition["condition_id"], matching[0].option_id))
        unresolved = tuple(c["condition_id"] for c in numeric if c["label"] is None)
        # Explicitly named conditions with no observed value remain valid requirements;
        # their product evidence is unknown. Unnamed conditions always need selection.
        data = dict(
            product_batch_sha256=normalized_product_batch_sha256(self._batch),
            options=tuple(options),
            unresolved=unresolved,
            conditions=self._conditions,
            automatic=tuple(automatic),
        )
        wire = {
            **data,
            "options": [o.model_dump(mode="json") for o in options],
            "plan": self.plan_sha256,
        }
        return CandidateReview(sha256=_digest(wire), **data)

    def confirm(self, *, owner_id, review_sha256, selections: dict[str, str], now):
        with self._lock:
            self._check(owner_id, now, "attribute_review")
            if (
                review_sha256 != self._review.sha256
                or type(selections) is not dict
                or set(selections) != set(self._review.unresolved)
            ):
                raise ValueError("Every unresolved condition needs a current explicit selection")
            by_id = {o.option_id: o for o in self._review.options}
            for condition_id, option_id in selections.items():
                if (
                    type(option_id) is not str
                    or option_id not in by_id
                    or condition_id not in by_id[option_id].condition_ids
                ):
                    raise ValueError("Selected attribute does not belong to this condition")
            self._selected = {**dict(self._review.automatic), **selections}
            self._confirmation = _digest(
                {
                    "owner": owner_id,
                    "session": self._plan.session_id,
                    "review": review_sha256,
                    "selections": self._selected,
                }
            )
            self._state = "confirmed"
            return self._confirmation

    def _requirements(self):
        base = build_typed_requirement_proposal(self._queries.retrieval_intent)
        if base.status != "ready":
            raise ValueError("Confirmed source conditions are invalid")
        definitions = {d.attribute_key: d for d in base.registry.definitions}
        by_id = {o.option_id: o for o in self._review.options}
        drafts, numeric_labels = [], {}
        for condition in self._conditions:
            cid, target = condition["condition_id"], condition["target"].copy()
            if condition["attribute_key"] == "custom" and "unit" in target:
                label = (
                    by_id[self._selected[cid]].label
                    if cid in self._selected
                    else condition["label"]
                )
                if label is None:
                    raise ValueError("Unresolved numeric condition cannot be evaluated")
                raw_unit = target["unit"]
                target["unit"] = _unit_key(raw_unit)
                # Quantities use Decimal even when the requested bound is integral:
                # a product's fractional measurement must not disappear as unknown.
                target["value_type"] = "decimal"
                key = "search.observed_" + _digest([label, raw_unit, target["value_type"]])[:24]
                definitions[key] = AttributeDefinition(
                    # Selection binds the name explicitly; global alias lookup must
                    # not collide with source or common definitions for that name.
                    category="search",
                    attribute_key=key,
                    aliases=(),
                    value_type=target["value_type"],
                    allowed_operators=("equals", "at_least", "at_most", "between"),
                    allowed_strengths=("required", "preferred", "excluded"),
                    allowed_units=(target["unit"],),
                    unit_aliases=(),
                    allowed_values=(),
                    value_aliases=(),
                    evidence_rules=(
                        EvidenceRule(
                            source="structured",
                            priority=1,
                            evaluator_id="candidate-observed-spec",
                            evaluator_version="1.0",
                        ),
                    ),
                    default_weight=1,
                    visual_prompt_allowed=False,
                )
                numeric_labels[cid] = (label, raw_unit)
            elif condition["attribute_key"] == "custom":
                from src.search_v2.dynamic_attributes import search_attribute_key

                candidate = next(
                    c
                    for c in self._queries.retrieval_intent.typed_conditions
                    if c.attribute_definition is not None
                    and c.attribute_definition.source_quote == condition["source_quote"]
                )
                key = search_attribute_key(candidate)
            else:
                key = condition["attribute_key"]
            if target["value_type"] == "decimal":
                for bound in ("minimum", "maximum"):
                    if target.get(bound) is not None:
                        target[bound] = Decimal(target[bound])
            if target["value_type"] in ("integer", "decimal"):
                target.setdefault("minimum", None)
                target.setdefault("maximum", None)
            if "values" in target:
                target["values"] = tuple(target["values"])
            drafts.append(
                TypedRequirementDraft(
                    requirement_id=cid,
                    attribute_key=key,
                    operator=condition["operator"],
                    expected_value=target,
                    strength=condition["strength"],
                )
            )
        registry = AttributeRegistry(
            schema_version="1.0",
            registry_id="candidate-" + self._confirmation[:24],
            definitions=tuple(sorted(definitions.values(), key=lambda d: d.attribute_key)),
        )
        return (
            normalize_typed_requirements(tuple(drafts), registry=registry),
            registry,
            numeric_labels,
        )

    def _evaluate(self, product, requirements, registry, numeric_labels):
        product_digest = normalized_product_candidate_sha256(product)
        common = tuple(r for r in requirements if r.requirement_id not in numeric_labels)
        evidence = build_product_evidence(product, common, registry=registry)
        observations = list(evidence.observations)
        for requirement in requirements:
            cid = requirement.requirement_id
            if cid not in numeric_labels:
                continue
            label, unit = numeric_labels[cid]
            specs = [
                s
                for s in self._specifications
                if s.product_index == product.provenance.response_index
                and s.label == label
                and _factor(s.unit, unit) is not None
            ]
            if self._plan.title_comparison is not None:
                kinds = {field.field_id: field.kind for field in self._fields}

                def priority(spec):
                    kind = kinds[spec.field_id]
                    return 0 if kind.startswith("features-") else 1 if kind == "title" else 2

                structured = any(
                    _identity(feature).partition(":")[0].strip() == _identity(label)
                    for feature in product.attributes.features
                )
                preferred = 0 if structured else min((priority(spec) for spec in specs), default=0)
                specs = [spec for spec in specs if priority(spec) == preferred]
            values = []
            for spec in specs:
                number = spec.number * _factor(spec.unit, unit)
                value = DecimalObservedValue(
                    value_type="decimal", value=number, unit=_unit_key(unit)
                )
                if value not in values:
                    values.append(value)
            if cid == "condition-price":
                specs = []
                values = (
                    []
                    if product.price_jpy is None
                    else [
                        DecimalObservedValue(
                            value_type="decimal",
                            value=Decimal(product.price_jpy),
                            unit="jpy",
                        )
                    ]
                )
            for value in values or [None]:
                observations.append(
                    build_evidence_observation(
                        requirement,
                        product_sha256=product_digest,
                        source="structured",
                        observed_value=value,
                        unknown_reason="not_observed" if value is None else None,
                        evaluator_profile_sha256=_PROFILE,
                        input_artifact_sha256=product_digest
                        if cid == "condition-price"
                        else _digest([s.model_dump(mode="json") for s in specs]),
                        registry=registry,
                    )
                )
        decisions = tuple(
            adjudicate_requirement(
                r,
                product_sha256=product_digest,
                observations=tuple(o for o in observations if o.requirement_id == r.requirement_id),
                registry=registry,
            )
            for r in requirements
        )
        return evaluate_typed_product(
            requirements, decisions, product_sha256=product_digest, registry=registry
        )

    def rank(self, *, owner_id, now):
        with self._lock:
            self._check(owner_id, now, "confirmed")
            self._state = "evaluating"
        stage = "ranking_requirements"
        try:
            requirements, registry, labels = self._requirements()
            stage = "ranking_product_evaluation"
            scoring_intent = self._queries.retrieval_intent
            expansion = self._plan.query_expansion
            if (
                expansion is not None
                and expansion.status == "ready"
                and expansion.terms is not None
            ):
                # Compare the original concept in both languages without expanding retrieval.
                scoring_intent = scoring_intent.model_copy(
                    update={
                        "product_name_en": expansion.terms.original_en,
                    }
                )
            products = []
            comparison = self._plan.title_comparison
            condition_labels = {c["condition_id"]: c["label"] for c in self._conditions}
            condition_labels.update({cid: label for cid, (label, _) in labels.items()})
            bundle = self._plan.condition_terms
            for p in self._batch.products:
                bilingual_title = title_scores(comparison, p) if bundle else None
                evaluation = self._evaluate(p, requirements, registry, labels)
                products.append(
                    CandidateRankedProduct(
                        product=p,
                        evaluation=evaluation,
                        title_scores=bilingual_title,
                        lexical_score=bilingual_title.score
                        if bilingual_title
                        else score_title(comparison, p.title)
                        if comparison
                        else _title_score(scoring_intent, p)[0].score or 0.0,
                        text_score=score_bilingual(
                            p,
                            requirements,
                            registry,
                            evaluation,
                            condition_labels,
                            bundle,
                            weighting=self._plan.condition_weighting,
                        )
                        if bundle
                        else score_conditions(
                            p,
                            requirements,
                            registry,
                            evaluation,
                            condition_labels,
                            weighting=self._plan.condition_weighting,
                        )
                        if comparison
                        else None,
                    )
                )
            products.sort(key=lambda p: candidate_sort_key(p, p.lexical_score))
            stage = "ranking_contract"
            result = CandidateRanking(
                profile_id="candidate-confirmed-lexical-v5"
                if bundle
                else "candidate-confirmed-lexical-v4"
                if comparison
                else "candidate-confirmed-lexical-v3",
                retrieval_plan_sha256=self.plan_sha256,
                review_sha256=self._review.sha256,
                confirmation_sha256=self._confirmation,
                retrieval_plan=self.plan,
                attribute_review=self._review.model_copy(deep=True),
                confirmed_selections=tuple(sorted(self._selected.items())),
                requirements=requirements,
                registry=registry,
                product_batch=self._batch,
                products=tuple(products),
                visual_evaluation_status="pending"
                if self._plan.visual_conditions is not None
                else "not_requested",
            )
            self._state = "completed"
            return result
        except (CandidateEvaluationError, CandidatePreparationError):
            self._state = "failed"
            raise
        except Exception:
            self._state = "failed"
            raise CandidateEvaluationError(stage) from None


def prepare_candidate_search(
    source_input,
    review=None,
    *,
    owner_id=None,
    session_id=None,
    postal_code,
    normalization_profile,
    now,
    visual_extractor: BonsaiEvaluator | None = None,
    query_expander: BonsaiEvaluator | None = None,
    lexical_expander=None,
    condition_expander=None,
    contrast_resolver=None,
    source_parser=None,
    plan_lifetime=timedelta(minutes=15),
    japanese_search_urls=False,
    allow_empty_visual=False,
    image_mode="on",
):
    if review is not None:
        from src.search_v2.orchestrator import BlockingIntentReview, IntentReview

        if type(review) not in (BlockingIntentReview, IntentReview):
            raise ValueError("Invalid source intent review")
        validated = type(review).model_validate(review)
        if candidate_source_sha256(source_input) != validated.intent.provenance.source_input_sha256:
            raise ValueError("Candidate source does not match its original review")
        if owner_id not in (None, validated.session.owner_id) or session_id not in (
            None,
            validated.session.session_id,
        ):
            raise ValueError("Candidate owner or session changed")
        owner_id, session_id = validated.session.owner_id, validated.session.session_id
    return CandidateSearch(
        source_input,
        owner_id=owner_id,
        session_id=session_id,
        postal_code=postal_code,
        normalization_profile=normalization_profile,
        now=now,
        visual_extractor=visual_extractor,
        query_expander=query_expander,
        lexical_expander=lexical_expander,
        condition_expander=condition_expander,
        contrast_resolver=contrast_resolver,
        source_parser=source_parser,
        plan_lifetime=plan_lifetime,
        japanese_search_urls=japanese_search_urls,
        allow_empty_visual=allow_empty_visual,
        image_mode=image_mode,
    )
