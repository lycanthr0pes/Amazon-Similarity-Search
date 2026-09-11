"""Opt-in CPU pair-model regression on observed development contexts."""

from pathlib import Path
import json

import pytest

from src.search_v2.lexical_assets import load_lexical_services


def test_real_pair_model_ranks_the_four_dictionary_senses_first(request):
    root = request.config.getoption("--lexical-assets")
    if (
        root is None
        or json.loads((Path(root) / "runtime-manifest.json").read_bytes()).get("schema_version")
        != 2
    ):
        pytest.skip("requires --lexical-assets with a prepared contextual bundle")
    cases = [
        ("パソコンで使うマウスを探している。", "マウス", {"wordnet:03793489-n"}),
        (
            "実験動物として飼育するマウスが欲しい。",
            "マウス",
            {"wordnet:02330245-n", "wordnet:02331842-n"},
        ),
        ("ネジを締めるドライバーが欲しい。", "ドライバー", {"wordnet:04154565-n"}),
        ("ゴルフで使うドライバーが欲しい。", "ドライバー", {"wordnet:03244047-n"}),
    ]
    with load_lexical_services(Path(root)) as (expander, _):
        for source, product, expected in cases:
            senses = expander._lexicon.lookup_contextual(product)
            scores = expander._scorer.scores(source, senses)
            assert senses[max(range(len(scores)), key=scores.__getitem__)].sense_id in expected
            # Highest rank is not enough to authorize a confident automatic choice.
            assert expander.propose(source, product).status == "unavailable"


def test_uninterpreted_relation_stops_before_sense_selection(request):
    root = request.config.getoption("--lexical-assets")
    if (
        root is None
        or json.loads((Path(root) / "runtime-manifest.json").read_bytes()).get("schema_version")
        != 2
    ):
        pytest.skip("requires prepared contextual assets")
    from src.search_v2.candidate_search import prepare_candidate_search
    from src.search_v2.candidate_diagnostics import CandidatePreparationError
    from test_lexical_connection import NOW, PROFILE

    class Expander:
        def propose(self, *_):
            pytest.fail("Uninterpreted conditions must stop before sense expansion")

    with load_lexical_services(Path(root)) as (_, parser):
        with pytest.raises(CandidatePreparationError):
            prepare_candidate_search(
                "海底で育てるドライバーを探しています。",
                owner_id="owner",
                session_id="session",
                postal_code="100-0001",
                normalization_profile=PROFILE,
                now=NOW,
                source_parser=parser,
                lexical_expander=Expander(),
            )
