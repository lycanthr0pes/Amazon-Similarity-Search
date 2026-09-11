"""Offline runtime contracts; no optional model assets or providers."""

from types import SimpleNamespace

import numpy as np

from src.search_v2.lexical_runtime import OnnxGlossScorer
from src.search_v2.lexical_selection import LexicalSense


def test_exported_encoder_receives_token_type_ids():
    class Tokenizer:
        def encode_batch(self, texts):
            return [
                SimpleNamespace(ids=[1, 2], attention_mask=[1, 1], type_ids=[0, 0]) for _ in texts
            ]

    class Session:
        def get_inputs(self):
            return [
                SimpleNamespace(name=name)
                for name in ("input_ids", "attention_mask", "token_type_ids")
            ]

        def run(self, _, inputs):
            assert set(inputs) == {"input_ids", "attention_mask", "token_type_ids"}
            assert np.array_equal(inputs["token_type_ids"], np.zeros((2, 2), dtype=np.int64))
            return [np.ones((2, 2, 3), dtype=np.float32)]

    scorer = OnnxGlossScorer.__new__(OnnxGlossScorer)
    scorer._tokenizer = Tokenizer()
    scorer._session = Session()
    sense = LexicalSense("fixture:mouse", "fixture", ("マウス",), ("mouse",), "computer mouse")
    assert scorer.scores("パソコンのマウス", (sense,))[0] > 0.999


def test_adjacent_noun_tokens_are_retained_when_parser_leaves_dependency_unlabeled():
    from src.search_v2.lexical_runtime import product_span
    from src.search_v2.lexical_structure import TextSpan

    tokens = [
        SimpleNamespace(i=0, idx=0, text="ランチ", pos_="NOUN", dep_="dep"),
        SimpleNamespace(i=1, idx=3, text="ボックス", pos_="NOUN", dep_="obj"),
    ]
    tokens[0].head = SimpleNamespace(i=3)
    assert product_span(tokens, tokens[1]) == TextSpan(0, 7)


def test_product_compound_does_not_absorb_modifier_across_particle():
    from src.search_v2.lexical_runtime import product_span
    from src.search_v2.lexical_structure import TextSpan

    tokens = [
        SimpleNamespace(i=0, idx=0, text="革", pos_="NOUN", dep_="nmod"),
        SimpleNamespace(i=1, idx=1, text="の", pos_="ADP", dep_="case"),
        SimpleNamespace(
            i=2, idx=2, text="名刺", pos_="NOUN", dep_="compound", head=SimpleNamespace(i=3)
        ),
        SimpleNamespace(i=3, idx=4, text="入れ", pos_="NOUN", dep_="obj"),
    ]
    assert product_span(tokens, tokens[3]) == TextSpan(2, 6)
