"""Optional real CPU dictionaries/parser/encoder, with fixture-only providers."""

import json

import pytest

from src.search_v2.lexical_assets import load_lexical_services


@pytest.fixture(scope="module")
def lexical(request):
    path = request.config.getoption("--lexical-assets")
    if path is None:
        pytest.skip("requires prepared --lexical-assets; no automatic downloads")
    with load_lexical_services(path) as services:
        yield services


def test_real_lexical_components_connect_to_fixture_images_clip_and_history(
    lexical, tmp_path, monkeypatch
):
    import test_candidate_search_live_e2e as live

    module, config, services, events, clips = live.setup_run(tmp_path, monkeypatch)
    expander, parser = lexical
    reviews = []

    def choose(review):
        reviews.append(review)
        return next(i for i, q in enumerate(review["queries"]) if q["value"] == "mug")

    result = module.run_candidate_e2e(
        config,
        services,
        lexical_expander=expander,
        source_parser=parser,
        select_query=choose,
        image_score_mode="appearance",
    )
    assert result["status"] == "succeeded"
    assert result["bonsai_calls"] == 1
    assert result["outscraper_tasks"] == 1
    assert result["history_images_verified"] == 2
    assert events == [("reference", 1, 1), ("search", 2, 1)]
    assert clips == [2, 4]
    saved = json.loads((config.output_dir / "plan.json").read_bytes())
    assert saved["query_expansion"]["profile_id"] == "dictionary-query-terms-v1"
    assert saved["request"]["queries"][0]["value"] == "mug"
    assert saved["source_structure"]["parser_id"].startswith("ginza:")


def test_real_parser_keeps_compound_and_inline_price(lexical):
    from src.search_v2.candidate_queries import build_candidate_queries

    _, parser = lexical
    for source, product in (
        ("ランチボックスを探しています。", "ランチボックス"),
        ("3000円以下の名刺入れを探しています。", "名刺入れ"),
    ):
        structure = parser.analyze(source)
        query = build_candidate_queries(source, structure=structure)
        assert structure.product.text(structure.source) == product
        expected = "ランチ ボックス" if product == "ランチボックス" else product
        assert query.retrieval_intent.product_name_ja == expected
        if "3000" in source:
            assert query.retrieval_intent.price.max_jpy == 3000


def test_real_ambiguous_senses_and_unhandled_relations_abstain(lexical):
    from src.search_v2.candidate_queries import build_candidate_queries

    expander, parser = lexical
    for source in ("マウスを探しています。", "ドライバーを探しています。"):
        structure = parser.analyze(source)
        result = expander.propose(source, structure.product.text(structure.source))
        assert result.status == "unavailable"
        assert result.selected_sense_id is None
    for source in ("机に固定するライトが欲しい。", "赤か青のマグカップが欲しい。"):
        with pytest.raises(ValueError):
            build_candidate_queries(source, structure=parser.analyze(source))
