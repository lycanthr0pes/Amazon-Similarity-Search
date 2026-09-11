from pathlib import Path

import pytest

from tools.check_markdown_links import MarkdownLinkCheckError
from tools.check_markdown_links import check_markdown_links


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_current_repository_markdown_links_are_valid() -> None:
    report = check_markdown_links(REPOSITORY_ROOT)

    assert report.markdown_files >= 1
    assert report.local_links >= 1


def test_valid_relative_path_anchor_and_duplicate_heading_are_accepted(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "README.md").write_text(
        "# Home\n\n[Guide](docs/GUIDE.md#section-1)\n"
        "[External](https://example.com/missing)\n\n"
        "```text\n[Code example](missing.md)\n```\n",
        encoding="utf-8",
    )
    (docs / "GUIDE.md").write_text(
        "# Guide\n\n## Section\n\n## Section\n",
        encoding="utf-8",
    )
    old = docs / "old"
    old.mkdir()
    (old / "BROKEN.md").write_text("[Archived](missing.md)\n", encoding="utf-8")

    report = check_markdown_links(tmp_path)

    assert report.markdown_files == 2
    assert report.local_links == 1
    assert report.anchor_links == 1
    assert report.headings == 4
    assert report.fence_pairs == 1


def test_missing_relative_target_is_rejected(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# Home\n\n[Missing](docs/MISSING.md)\n", encoding="utf-8")

    with pytest.raises(MarkdownLinkCheckError, match=r"README\.md:3: missing target"):
        check_markdown_links(tmp_path)


def test_missing_heading_anchor_is_rejected(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "README.md").write_text(
        "# Home\n\n[Guide](docs/GUIDE.md#missing)\n",
        encoding="utf-8",
    )
    (docs / "GUIDE.md").write_text("# Guide\n\n## Present\n", encoding="utf-8")

    with pytest.raises(MarkdownLinkCheckError, match=r"README\.md:3: missing anchor"):
        check_markdown_links(tmp_path)
