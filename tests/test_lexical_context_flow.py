"""Candidate entry preserves visual extraction and adds at most one sense call."""

from contextlib import nullcontext
from dataclasses import replace
import json

from src.search_v2.bonsai_request import BonsaiHttpResponse
from src.search_v2.lexical_context import BonsaiSenseSelector
from src.search_v2.lexical_expansion import ContextualQueryExpander
from src.search_v2.lexical_selection import LexicalSense
from test_lexical_context_expansion import Scorer
from test_lexical_context_selection import envelope
import test_candidate_search_live_e2e as live


def test_optional_sense_call_happens_before_images_and_selected_query_reaches_history(
    tmp_path, monkeypatch
):
    module, config, services, events, clips = live.setup_run(tmp_path, monkeypatch)
    visual_transport = services.bonsai_session().__enter__()
    bodies = []

    class Transport:
        def post_json(self, **kwargs):
            bodies.append(kwargs["body"])
            if len(bodies) == 1:
                return visual_transport.post_json(**kwargs)
            assert len(bodies) == 2
            body = envelope({"sense_id": "wn:mug", "evidence_index": 0})
            return BonsaiHttpResponse(200, "application/json", len(body), None, (body,))

    class Lexicon:
        sha256 = "d" * 64

        def lookup_contextual(self, _):
            return (
                LexicalSense("wn:mug", "wordnet", ("マグカップ",), ("mug",), "cup"),
                LexicalSense("wn:face", "wordnet", ("マグカップ",), ("face",), "face"),
            )

    def confirm(stage, review):
        assert len(bodies) == 2, "Both model calls must finish before image confirmation"
        return services.confirm(stage, review)

    expander = ContextualQueryExpander(Lexicon(), Scorer([0.6, 0.4]))
    result = module.run_candidate_e2e(
        config,
        replace(services, bonsai_session=lambda: nullcontext(Transport()), confirm=confirm),
        lexical_expander=expander,
        sense_resolver_factory=lambda evaluator: BonsaiSenseSelector(evaluator, "e" * 64),
        select_query=lambda review: next(
            i for i, q in enumerate(review["queries"]) if q["value"] == "mug"
        ),
        image_score_mode="appearance",
    )
    assert result["status"] == "succeeded"
    assert result["bonsai_calls"] == 2 and result["outscraper_tasks"] == 1
    assert result["history_images_verified"] == 2
    assert clips == [2, 4]
    saved = json.loads((config.output_dir / "plan.json").read_bytes())
    assert saved["query_expansion"]["resolution_method"] == "bonsai"
    assert saved["request"]["queries"][0]["value"] == "mug"
    assert not (config.output_dir / "bonsai-response-3.json").exists()
