"""Dictionary suggestions and source-bound preparation with an optional name resolver."""

from dataclasses import asdict
import hashlib
import json

from src.search_v2.bonsai_query_terms import QueryExpansion
from src.search_v2.lexical_selection import select_sense, terms_from_sense


def _hash(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


class DictionaryQueryExpander:
    def __init__(self, lexicon, scorer):
        self._lexicon = lexicon
        self._scorer = scorer

    def propose(self, source, product_phrase):
        request_hash = _hash(
            {
                "source": source,
                "product": product_phrase,
                "dictionary": self._lexicon.sha256,
                "model": self._scorer.sha256,
                "selection": "gloss-cosine-min075-margin004-v1",
            }
        )
        terms, selection, response_hash = None, None, None
        try:
            senses = self._lexicon.lookup(product_phrase)
            if len(senses) == 1:
                # A unique exact dictionary sense needs no contextual inference.
                scores = [1.0]
            else:
                scores = self._scorer.scores(source, senses) if senses else []
            selection = select_sense(senses, scores)
            response_hash = _hash(
                {
                    "senses": [asdict(s) for s in senses],
                    "scores": scores,
                    "selection": asdict(selection),
                }
            )
            if selection.sense is not None:
                terms = terms_from_sense(product_phrase, selection.sense)
        except Exception:
            # Optional suggestions abstain; source parsing never uses this fallback.
            selection = None
            terms = None
        return QueryExpansion(
            profile_id="dictionary-query-terms-v1",
            source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            request_sha256=request_hash,
            response_sha256=response_hash,
            status="ready" if terms is not None else "unavailable",
            terms=terms,
            dictionary_sha256=self._lexicon.sha256,
            sense_model_sha256=self._scorer.sha256,
            selected_sense_id=selection.sense.sense_id if selection and selection.sense else None,
        )


class ContextualQueryExpander:
    def __init__(self, lexicon, scorer, *, resolver=None, translator=None):
        self._lexicon, self._scorer, self._resolver = lexicon, scorer, resolver
        self._translator = translator

    def with_resolver(self, resolver):
        return ContextualQueryExpander(
            self._lexicon, self._scorer, resolver=resolver, translator=self._translator
        )

    def with_translator(self, translator):
        return ContextualQueryExpander(
            self._lexicon, self._scorer, resolver=self._resolver, translator=translator
        )

    def prepare(self, source, structure):
        from src.search_v2.product_phrase import prepare_product_phrase

        return prepare_product_phrase(
            source, structure, self._lexicon, self._scorer, self._resolver, self._translator
        )

    def propose(self, source, product_phrase):
        from src.search_v2.lexical_context import CONTEXT_PROFILE, has_context

        resolver_hash = self._resolver.sha256 if self._resolver else None
        request_hash = _hash(
            {
                "source": source,
                "product": product_phrase,
                "dictionary": self._lexicon.sha256,
                "model": self._scorer.sha256,
                "resolver": resolver_hash,
                "selection": CONTEXT_PROFILE,
            }
        )
        selected, terms, resolution = None, None, None
        method = "abstained"
        scores = []
        response_hash = None
        try:
            senses = self._lexicon.lookup_contextual(product_phrase)
            if len(senses) == 1:
                selected, method = senses[0], "dictionary"
            elif senses and has_context(source, product_phrase):
                scores = self._scorer.scores(source, senses)
                selected = select_sense(senses, scores, minimum=0.80, margin=0.20).sense
                if selected is not None:
                    method = "cross_encoder"
                elif self._resolver is not None:
                    shortlist = tuple(
                        senses[i]
                        for i in sorted(range(len(scores)), key=scores.__getitem__, reverse=True)[
                            :2
                        ]
                    )
                    resolution = self._resolver.select(source, product_phrase, shortlist)
                    # Different models must agree; the resolver cannot overrule the comparator.
                    selected = resolution.sense if resolution.sense == shortlist[0] else None
                    if selected is not None:
                        if selected not in senses:
                            raise ValueError("Resolver selected an unknown sense")
                        method = "bonsai"
            if selected is not None:
                terms = terms_from_sense(product_phrase, selected)
            response_hash = _hash(
                {
                    "senses": [asdict(s) for s in senses],
                    "scores": scores,
                    "selected": selected.sense_id if selected else None,
                    "resolution": asdict(resolution) if resolution else None,
                }
            )
        except Exception:
            selected, terms, method = None, None, "abstained"
        return QueryExpansion(
            profile_id="dictionary-query-terms-v2",
            source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            request_sha256=request_hash,
            response_sha256=response_hash,
            status="ready" if terms is not None else "unavailable",
            terms=terms,
            dictionary_sha256=self._lexicon.sha256,
            sense_model_sha256=self._scorer.sha256,
            selected_sense_id=selected.sense_id if selected else None,
            resolution_method=method,
            resolver_sha256=resolver_hash,
            resolver_request_sha256=resolution.request_sha256 if resolution else None,
            resolver_response_sha256=resolution.response_sha256 if resolution else None,
        )
