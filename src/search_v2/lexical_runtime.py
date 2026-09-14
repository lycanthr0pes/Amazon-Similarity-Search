"""Optional CPU runtimes. Constructors load local files only."""

import hashlib
from importlib.metadata import version
from pathlib import Path
import re

import numpy as np

from src.search_v2.lexical_selection import MAX_SENSES
from src.search_v2.lexical_structure import ProductStructure, TextSpan, validate_structure
from src.search_v2.source_constraints import _clauses, _name_is_explicit, _source_facts
from src.search_v2.tokenizer import _analyze_japanese_source


def product_span(doc, target):
    """Keep contiguous noun tokens, including unlabeled dependency fragments."""
    first = target.i
    while first:
        previous = doc[first - 1]
        current = doc[first]
        if previous.idx + len(previous.text) != current.idx:
            break
        lexical_noun = getattr(previous, "tag_", "").startswith(("名詞-", "接尾辞-"))
        if previous.pos_ not in {"NOUN", "PROPN"} and not lexical_noun:
            break
        # Fine-grained Sudachi tags preserve adjacent noun compounds even when
        # the dependency model mislabels an unfamiliar abbreviation as a conjunction.
        if (
            not lexical_noun
            and previous.dep_ != "dep"
            and not (previous.dep_ == "compound" and first <= previous.head.i <= target.i)
        ):
            break
        first -= 1
    return TextSpan(doc[first].idx, target.idx + len(target.text))


class GinzaProductParser:
    def __init__(self):
        import spacy

        self._nlp = spacy.load("ja_ginza", disable=["ner"])
        self.parser_id = (
            f"condition-language-v1/ginza:{version('ginza')}/ja_ginza:{version('ja-ginza')}"
        )

    def analyze(self, source):
        if type(source) is not str or not 0 < len(source) <= 2000:
            raise ValueError("Invalid syntax input")
        from src.search_v2.condition_language import analyze_conditions, interpret_clause

        analyze_conditions(source)
        original_source = source
        source = _analyze_japanese_source(source).text
        doc = self._nlp(source)
        if any(t.text in {"か", "または", "あるいは", "もしくは", "又は"} for t in doc):
            raise ValueError("Coordinated source requires clarification")
        roots = [
            t
            for t in doc
            if t.dep_ == "ROOT" and t.lemma_ in {"探す", "欲しい", "ほしい", "買う", "購入する"}
        ]
        ignored = []
        targets = []
        for root in roots:
            targets.extend(
                t
                for t in root.children
                if t.dep_ in {"obj", "nsubj"} and t.pos_ in {"NOUN", "PROPN"}
            )
            ending = [root]
            for token in doc[root.i + 1 :]:
                if token.pos_ == "PUNCT":
                    break
                ending.append(token)
            ignored.append(TextSpan(root.idx, ending[-1].idx + len(ending[-1])))
        if roots:
            if len(targets) != 1:
                raise ValueError("Search target is ambiguous")
            target = targets[0]
            product = product_span(doc, target)
        else:
            facts, uncertain = _source_facts(source, natural=True)
            if uncertain:
                raise ValueError("Unresolved source relation")
            candidates = [
                TextSpan(start + len(text) - len(text.lstrip()), start + len(text.rstrip()))
                for start, text in _clauses(source)
                if _name_is_explicit(text.strip())
                and interpret_clause(text.strip()).reason == "explicit_condition"
                and not any(f.quote in text for f in facts)
                and not re.search(r"[0-9]", text)
            ]
            if len(candidates) != 1:
                # An adjectivally modified noun can itself be the sentence root.
                noun_roots = [t for t in doc if t.dep_ == "ROOT" and t.pos_ in {"NOUN", "PROPN"}]
                if len(noun_roots) != 1 or len(list(doc.sents)) != 1:
                    raise ValueError("Search target is ambiguous")
                target = noun_roots[0]
                product = product_span(doc, target)
            else:
                product = candidates[0]
        blocked = (product, *ignored)
        groups, group = [], []
        for token in doc:
            covered = any(s.start <= token.idx < s.end for s in blocked)
            if covered or token.pos_ == "PUNCT":
                if group:
                    groups.append(group)
                    group = []
            else:
                group.append(token)
        if group:
            groups.append(group)
        fragments = []
        for group in groups:
            while group and (group[0].pos_ in {"ADP", "SCONJ"} or group[0].text.isspace()):
                group.pop(0)
            while group and (group[-1].pos_ in {"ADP", "SCONJ"} or group[-1].text.isspace()):
                group.pop()
            if group:
                fragments.append(TextSpan(group[0].idx, group[-1].idx + len(group[-1])))
        return validate_structure(
            original_source,
            ProductStructure(source, product, tuple(fragments), tuple(ignored), self.parser_id),
        )


class OnnxGlossScorer:
    def __init__(self, model_path, tokenizer_path):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        paths = [Path(model_path), Path(tokenizer_path)]
        digests = []
        for path in paths:
            if not path.is_file():
                raise ValueError("Local lexical model is missing")
            with path.open("rb") as stream:
                digests.append(hashlib.file_digest(stream, "sha256").hexdigest())
        self.sha256 = hashlib.sha256("".join(digests).encode()).hexdigest()
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self._session = ort.InferenceSession(
            str(paths[0]), sess_options=options, providers=["CPUExecutionProvider"]
        )
        self._tokenizer = Tokenizer.from_file(str(paths[1]))
        self._tokenizer.no_truncation()
        self._tokenizer.enable_padding(pad_id=1, pad_token="<pad>")

    def scores(self, context, senses):
        if (
            type(context) is not str
            or not 0 < len(context) <= 2000
            or not 0 < len(senses) <= MAX_SENSES
        ):
            raise ValueError("Invalid gloss scoring input")
        texts = ["query: " + context, *("passage: " + s.definition for s in senses)]
        encoded = self._tokenizer.encode_batch(texts)
        if max(len(e.ids) for e in encoded) > 512:
            raise ValueError("Lexical context exceeds model capacity")
        inputs = {
            "input_ids": np.array([e.ids for e in encoded], dtype=np.int64),
            "attention_mask": np.array([e.attention_mask for e in encoded], dtype=np.int64),
        }
        if any(value.name == "token_type_ids" for value in self._session.get_inputs()):
            inputs["token_type_ids"] = np.array([e.type_ids for e in encoded], dtype=np.int64)
        hidden = self._session.run(None, inputs)[0]
        mask = inputs["attention_mask"][..., None]
        pooled = (hidden * mask).sum(axis=1) / mask.sum(axis=1)
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        if not np.isfinite(pooled).all() or (norms <= 0).any():
            raise ValueError("Invalid lexical embeddings")
        vectors = pooled / norms
        return [float(np.clip(vectors[0] @ v, -1, 1)) for v in vectors[1:]]
