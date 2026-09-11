"""Bonsai confirms a short list; disagreement cannot override the pair model."""

from src.search_v2.lexical_context import BonsaiSenseSelector
from src.search_v2.lexical_expansion import ContextualQueryExpander
from test_lexical_context_expansion import Lexicon, Scorer
from test_lexical_context_selection import Bonsai, senses
import json


def test_evidence_is_an_input_reference_not_generated_text():
    bonsai = Bonsai({"sense_id": "wn:tool", "evidence_index": 0})
    selected = BonsaiSenseSelector(bonsai, "a" * 64).select(
        "ネジを締めるドライバーが欲しい。", "ドライバー", senses()
    )
    assert selected.sense == senses()[0]
    schema = json.loads(bonsai.calls[0])["response_format"]["schema"]
    assert schema["properties"]["evidence_index"]["enum"] == [None, 0]
    assert "evidence" not in schema["properties"]


def test_bonsai_disagreement_preserves_abstention():
    bonsai = Bonsai({"sense_id": "wn:club", "evidence_index": 0})
    e = ContextualQueryExpander(
        Lexicon(), Scorer([0.6, 0.5]), resolver=BonsaiSenseSelector(bonsai, "a" * 64)
    )
    result = e.propose("ネジを締めるドライバーが欲しい。", "ドライバー")
    assert result.status == "unavailable"
    assert result.selected_sense_id is None


def test_fallback_receives_only_the_top_two_senses():
    from src.search_v2.lexical_context import SenseResolution
    from src.search_v2.lexical_selection import LexicalSense

    values = (
        *senses(),
        LexicalSense("wn:person", "wordnet", ("ドライバー",), ("motorist",), "person"),
    )

    class Dictionary(Lexicon):
        def lookup_contextual(self, _):
            return values

    class Resolver:
        sha256 = "c" * 64

        def select(self, source, product, candidates):
            assert candidates == (values[1], values[0])
            return SenseResolution(None, "d" * 64, "e" * 64)

    result = ContextualQueryExpander(
        Dictionary(), Scorer([0.4, 0.5, 0.1]), resolver=Resolver()
    ).propose("ゴルフで使うドライバー", "ドライバー")
    assert result.status == "unavailable"
    assert result.resolver_request_sha256 == "d" * 64
