"""Optional local parser/dictionary checks; no network or model downloads."""

from pathlib import Path
import json

import pytest

from src.search_v2.lexical_assets import load_lexical_services
from src.search_v2.lexical_context import has_context


@pytest.fixture(scope="module")
def services(request):
    root = request.config.getoption("--lexical-assets")
    if (
        root is None
        or json.loads((Path(root) / "runtime-manifest.json").read_bytes()).get("schema_version")
        != 2
    ):
        pytest.skip("requires prepared contextual lexical assets")
    with load_lexical_services(root) as value:
        yield value


def test_real_parser_preserves_targets_across_request_inflections(services):
    _, parser = services
    for source, product in [
        ("USB端子を増やすハブを探しています。", "ハブ"),
        ("USBハブを入れるケースが欲しいです。", "ケース"),
        ("自転車の車輪に使うハブが欲しい。", "ハブ"),
        ("クラブが欲しいです。", "クラブ"),
        ("キャップを買いたいです。", "キャップ"),
        ("名刺入れを探していました。", "名刺入れ"),
    ]:
        parsed = parser.analyze(source)
        assert parsed.product.text(parsed.source) == product
        assert parsed.original_source == source
    assert not has_context("クラブが欲しいです。", "クラブ")
    with pytest.raises(ValueError):
        parser.analyze("USBハブ以外で端子を増やしたい。")


def test_real_compound_lookup_and_explicit_usb_plan(services):
    expander, parser = services
    senses = expander._lexicon.lookup_products("ハブ", "usb端子を増やす")
    assert any(s.sense_id == "jmdict:2273980:1" for s in senses)
    assert not any(
        s.sense_id == "jmdict:2273980:1"
        for s in expander._lexicon.lookup_products("ケース", "usbハブを入れる")
    )
    source = "USBハブを探しています。"
    review = expander.prepare(source, parser.analyze(source))
    assert review.product_name == "usbハブ"
    assert review.expansion.terms.original_en == "usb hub"
