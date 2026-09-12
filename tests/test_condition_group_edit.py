"""The frontend fixture retains condition semantics at the local parser boundary."""

import json
from pathlib import Path
from types import SimpleNamespace
import unicodedata
from test_lexical_structure import structure

import test_candidate_search as fixtures
import test_candidate_visual_conditions as visual
from src.search_v2.candidate_search import CandidateSearch
from src.search_v2.condition_language import analyze_conditions
from src.search_v2.condition_terms import LocalConditionExpander


def test_grouped_edit_preserves_wish_budget_negation_and_neutral_conditions(tmp_path):
    data = json.loads((Path(__file__).parent / "fixtures/condition-group-edits.json").read_text())
    source = data["expectedSource"]
    rows = {row.target: row.strength for row in analyze_conditions(source)}
    assert rows["usb非対応"] == "required"
    assert rows["3000円以下"] == "preferred"
    assert rows["電子レンジ対応"] == "excluded"
    assert rows["光沢"] == "excluded"
    assert rows["取っ手"] == "neutral"
    normalized = unicodedata.normalize("NFKC", source).casefold()
    parsed = structure(normalized, "マグカップ", tuple(normalized.split("。")[1:-1]))
    service = CandidateSearch(
        source,
        owner_id="owner-1",
        session_id="group-edit",
        postal_code="100-0001",
        normalization_profile=fixtures.flow.backend_policy().normalization_profile,
        now=fixtures.flow.NOW,
        condition_expander=LocalConditionExpander(),
        source_parser=SimpleNamespace(analyze=lambda _: parsed),
        visual_extractor=visual.VisualBonsai(
            tmp_path, [visual.draft("光沢は避けたい", "excluded")]
        ),
    )
    plan = service.plan
    assert plan.title_comparison.brand == "合成"
    assert all("取っ手" not in query.value for query in plan.query_options)
    assert all("取っ手" not in row.source_ja for row in plan.condition_terms.conditions)
    assert (
        next(
            row for row in plan.condition_terms.conditions if row.condition_id == "condition-price"
        ).strength
        == "preferred"
    )
