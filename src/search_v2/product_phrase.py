"""Reviewable product naming before condition compilation; never remove source conditions."""

import hashlib
import re
from dataclasses import asdict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.search_v2.bonsai_query_terms import (
    QueryExpansion,
    QueryTerms,
    TranslatedTerm,
    TranslationTrace,
    _clean_term,
)
from src.search_v2.lexical_context import has_context
from src.search_v2.lexical_expansion import _hash
from src.search_v2.lexical_selection import lexical_key, select_sense, terms_from_sense
from src.search_v2.lexical_structure import ProductStructure, validate_structure
from src.search_v2.source_constraints import _source_facts
from src.search_v2.tokenizer import _analyze_japanese_source


class ProductPhraseReview(BaseModel):
    model_config = ConfigDict(
        frozen=True, strict=True, extra="forbid", revalidate_instances="always"
    )
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    structure: ProductStructure = Field(repr=False)
    product_name: str | None = Field(repr=False)
    expansion: QueryExpansion = Field(repr=False)

    @model_validator(mode="after")
    def validate_binding(self):
        source = self.structure.original_source
        if source is None or hashlib.sha256(source.encode()).hexdigest() != self.source_sha256:
            raise ValueError("Product review belongs to another source")
        validate_structure(source, self.structure)
        if (
            self.expansion.profile_id != "product-query-terms-v1"
            or self.expansion.source_sha256 != self.source_sha256
        ):
            raise ValueError("Product expansion belongs to another review")
        if (self.product_name is not None) != (self.expansion.status == "ready"):
            raise ValueError("Product proposal and expansion differ")
        if self.product_name is not None:
            target = self.structure.product.text(self.structure.source)
            inferred = self.expansion.resolution_method == "bonsai_inference"
            if _clean_term(self.product_name, "ja") != self.product_name or (
                not inferred and not keeps_target(self.product_name, target)
            ):
                raise ValueError("Product proposal changed the requested object")
            names = (target, *(t.ja for t in self.expansion.terms.synonyms))
            if lexical_key(self.product_name) not in {lexical_key(n) for n in names}:
                raise ValueError("Product name differs from query options")
        return self

    @property
    def context_quotes(self):
        return tuple(span.text(self.structure.source) for span in self.structure.fragments)


def keeps_target(name, target):
    # A new compound may qualify the object, but must not replace it with an accessory.
    return lexical_key(name).endswith(lexical_key(target))


def _product_name(sense, target):
    forms = [f for f in sense.forms if keeps_target(f, target)]
    if not forms:
        raise ValueError("Dictionary sense changed the target")
    return _clean_term(
        min(forms, key=lambda f: (lexical_key(f) != lexical_key(target), len(f))), "ja"
    )


def _meaning_context(context):
    facts, _ = _source_facts(context)
    for fact in facts:
        context = context.replace(fact.quote, " ")
    return re.sub(r"[0-9]+(?:\.[0-9]+)?\s*(?:万|千)?円(?:以上|以下|以内)?", " ", context)


def _uncertain_relation(context):
    # Negation/alternatives need their own relation interpretation; never erase them.
    words = {m.dictionary_form for m in _analyze_japanese_source(context).morphemes}
    return bool(
        words & {"ない", "ぬ", "ず", "以外", "除外", "除く", "または", "あるいは", "もしくは"}
    )


def _translate_product(translator, product, name):
    phrases = tuple(dict.fromkeys((product, name)))
    request_hash = _hash({"translator": translator.sha256, "phrases": phrases})
    response_hash, status = None, "unavailable"
    translations = dict.fromkeys(phrases)
    try:
        outputs = translator.translate(phrases)
        if type(outputs) is not tuple or len(outputs) != len(phrases):
            raise ValueError("Invalid translation count")
        response_hash = _hash(outputs)
        cleaned = {}
        for phrase, output in zip(phrases, outputs, strict=True):
            value = _clean_term(output, "en") if output is not None else None
            if value and not set(re.findall(r"\d+", value)).issubset(re.findall(r"\d+", phrase)):
                raise ValueError("Translation adds numbers")
            cleaned[phrase] = value
        translations = cleaned
        status = "ready" if any(v is not None for v in cleaned.values()) else "unavailable"
    except Exception:
        pass  # Optional English is unavailable; preserve the Japanese proposal.
    return (
        QueryTerms(
            original_en=translations[product],
            synonyms=(TranslatedTerm(ja=name, en=translations[name]),),
        ),
        TranslationTrace(
            model_sha256=translator.sha256,
            request_sha256=request_hash,
            response_sha256=response_hash,
            status=status,
        ),
    )


def prepare_product_phrase(source, structure, lexicon, scorer, resolver=None, translator=None):
    structure = validate_structure(source, structure)
    product = structure.product.text(structure.source)
    context = "。".join(s.text(structure.source) for s in structure.fragments)
    meaning = _meaning_context(context)
    resolver_hash = resolver.sha256 if resolver is not None else None
    request_hash = _hash(
        {
            "profile": "product-phrase-direct-v2",
            "source": source,
            "structure": asdict(structure),
            "dictionary": lexicon.sha256,
            "scorer": scorer.sha256,
            "resolver": resolver_hash,
            **({"translator": translator.sha256} if translator is not None else {}),
        }
    )
    senses, scores, selected, resolution, name, terms = (), [], None, None, None, None
    method = "abstained"
    translation = None
    try:
        if _uncertain_relation(context):
            raise ValueError("Unresolved product relation")
        senses = lexicon.lookup_products(product, meaning)
        contextual = has_context(product + "。" + meaning, product)
        if len(senses) == 1 and not contextual:
            selected, method = senses[0], "dictionary"
        elif senses and contextual:
            scores = scorer.scores(source, senses)
            selected = select_sense(senses, scores, minimum=0.80, margin=0.20).sense
            if selected is not None:
                method = "cross_encoder"
        if not senses and resolver is not None and hasattr(resolver, "generate"):
            resolution = (
                resolver.generate_name(source, product)
                if translator is not None and hasattr(resolver, "generate_name")
                else resolver.generate(source, product)
            )
            if resolution.sense is not None:
                raise ValueError("Direct inference cannot claim a dictionary sense")
            if resolution.product_name is not None:
                name = resolution.product_name
                terms = QueryTerms(
                    original_en=resolution.english
                    if lexical_key(name) == lexical_key(product)
                    else None,
                    synonyms=(TranslatedTerm(ja=name, en=resolution.english),),
                )
                method = "bonsai_inference"
                if translator is not None:
                    terms, translation = _translate_product(translator, product, name)
        elif senses and selected is None and contextual and resolver is not None:
            shortlist = tuple(
                senses[i]
                for i in sorted(range(len(scores)), key=scores.__getitem__, reverse=True)[:3]
            )
            if hasattr(resolver, "suggest"):
                resolution = resolver.suggest(source, product, shortlist)
            elif shortlist:
                resolution = resolver.select(source, product, shortlist)
            if resolution is not None and resolution.sense is not None:
                if resolution.sense not in shortlist:
                    raise ValueError("Unknown product sense")
                selected, method = resolution.sense, "bonsai"
            elif resolution is not None and getattr(resolution, "product_name", None):
                name = resolution.product_name
                if not keeps_target(name, product):
                    raise ValueError("Generated product changed the target")
                found = lexicon.lookup_contextual(name)
                # Re-query exact compound names; do not collapse multiple senses.
                if len(found) == 1:
                    selected, method = found[0], "bonsai"
                else:
                    terms = QueryTerms(
                        original_en=None, synonyms=(TranslatedTerm(ja=name, en=resolution.english),)
                    )
                    method = "bonsai_proposal"
        if selected is not None:
            name = _product_name(selected, product)
            terms = terms_from_sense(product, selected)
        response_hash = _hash(
            {
                "senses": [asdict(s) for s in senses],
                "scores": scores,
                "selected": asdict(selected) if selected else None,
                "resolution": asdict(resolution) if resolution else None,
                "name": name,
                **(
                    {"translation": translation.model_dump(), "terms": terms.model_dump()}
                    if translation is not None
                    else {}
                ),
            }
        )
    except Exception:
        selected, name, terms, method = None, None, None, "abstained"
        translation = None
        response_hash = _hash({"status": "unavailable"})
    expansion = QueryExpansion(
        profile_id="product-query-terms-v1",
        source_sha256=hashlib.sha256(source.encode()).hexdigest(),
        request_sha256=request_hash,
        response_sha256=response_hash,
        status="ready" if terms else "unavailable",
        terms=terms,
        dictionary_sha256=lexicon.sha256,
        sense_model_sha256=scorer.sha256,
        selected_sense_id=selected.sense_id if selected else None,
        resolution_method=method,
        resolver_sha256=resolver_hash,
        resolver_request_sha256=resolution.request_sha256 if resolution else None,
        resolver_response_sha256=resolution.response_sha256 if resolution else None,
        translation=translation,
    )
    return ProductPhraseReview(
        source_sha256=expansion.source_sha256,
        structure=structure,
        product_name=name,
        expansion=expansion,
    )
