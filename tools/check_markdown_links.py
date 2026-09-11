from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Iterable
from urllib.parse import unquote


_EXTERNAL_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_ATX_HEADING = re.compile(r"^ {0,3}#{1,6}(?:[ \t]+|$)(.*)$")
_CLOSING_HASHES = re.compile(r"[ \t]+#+[ \t]*$")
_INLINE_IMAGE = re.compile(r"!\[([^]]*)\]\([^)]*\)")
_INLINE_LINK = re.compile(r"\[([^]]+)\]\([^)]*\)")
_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class MarkdownLinkReport:
    markdown_files: int
    local_links: int
    anchor_links: int
    headings: int
    fence_pairs: int


class MarkdownLinkCheckError(ValueError):
    def __init__(self, issues: Iterable[str]) -> None:
        self.issues = tuple(issues)
        if not self.issues:
            raise ValueError("markdown link errors must not be empty")
        super().__init__("\n".join(self.issues))


@dataclass(frozen=True, slots=True)
class _MarkdownDocument:
    path: Path
    content_lines: tuple[tuple[int, str], ...]
    anchors: frozenset[str]
    heading_count: int
    fence_pairs: int


def _display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _discover_markdown(root: Path) -> tuple[Path, ...]:
    candidates = [*root.glob("*.md")]
    docs = root / "docs"
    if docs.is_dir():
        candidates.extend(docs.glob("*.md"))
    return tuple(
        sorted((path for path in candidates if path.is_file()), key=lambda path: path.name)
    )


def _source_paths(root: Path, paths: Iterable[Path] | None) -> tuple[Path, ...]:
    if paths is None:
        sources = _discover_markdown(root)
    else:
        sources = tuple(paths)

    normalized: list[Path] = []
    issues: list[str] = []
    for source in sources:
        candidate = source if source.is_absolute() else root / source
        resolved = candidate.resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            issues.append(f"source escapes repository root: {source}")
            continue
        if not candidate.is_file():
            issues.append(f"missing Markdown source: {_display_path(root, candidate)}")
            continue
        if candidate.is_symlink():
            issues.append(
                f"Markdown source must not be a symlink: {_display_path(root, candidate)}"
            )
            continue
        normalized.append(resolved)

    if not normalized and not issues:
        issues.append("no current Markdown files found")
    if issues:
        raise MarkdownLinkCheckError(issues)
    return tuple(sorted(set(normalized), key=lambda path: _display_path(root, path)))


def _content_outside_fences(
    root: Path,
    path: Path,
) -> tuple[tuple[tuple[int, str], ...], int]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise MarkdownLinkCheckError(
            (f"{_display_path(root, path)}: cannot read UTF-8 Markdown: {type(exc).__name__}",)
        ) from exc

    content: list[tuple[int, str]] = []
    fence_character: str | None = None
    fence_length = 0
    fence_start = 0
    fence_pairs = 0
    for line_number, line in enumerate(lines, start=1):
        match = _FENCE.match(line)
        if match is not None:
            marker = match.group(1)
            remainder = match.group(2)
            if fence_character is None:
                fence_character = marker[0]
                fence_length = len(marker)
                fence_start = line_number
                continue
            if (
                marker[0] == fence_character
                and len(marker) >= fence_length
                and remainder.strip() == ""
            ):
                fence_character = None
                fence_length = 0
                fence_start = 0
                fence_pairs += 1
            continue
        if fence_character is None:
            content.append((line_number, line))

    if fence_character is not None:
        raise MarkdownLinkCheckError(
            (f"{_display_path(root, path)}:{fence_start}: unclosed fenced code block",)
        )
    return tuple(content), fence_pairs


def _heading_slug(raw_heading: str) -> str:
    value = _CLOSING_HASHES.sub("", raw_heading).strip()
    value = _INLINE_IMAGE.sub(r"\1", value)
    value = _INLINE_LINK.sub(r"\1", value)
    value = _HTML_TAG.sub("", value)
    value = value.replace("`", "").replace("*", "").replace("_", "")
    value = value.casefold()
    value = "".join(
        character
        for character in value
        if character.isalnum() or character.isspace() or character in "-_"
    )
    return _WHITESPACE.sub("-", value)


def _heading_anchors(content_lines: tuple[tuple[int, str], ...]) -> tuple[frozenset[str], int]:
    anchors: set[str] = set()
    occurrences: defaultdict[str, int] = defaultdict(int)
    heading_count = 0
    for _line_number, line in content_lines:
        match = _ATX_HEADING.match(line)
        if match is None:
            continue
        heading_count += 1
        base = _heading_slug(match.group(1))
        duplicate_index = occurrences[base]
        occurrences[base] += 1
        anchors.add(base if duplicate_index == 0 else f"{base}-{duplicate_index}")
    return frozenset(anchors), heading_count


def _load_document(root: Path, path: Path) -> _MarkdownDocument:
    content_lines, fence_pairs = _content_outside_fences(root, path)
    anchors, heading_count = _heading_anchors(content_lines)
    return _MarkdownDocument(
        path=path,
        content_lines=content_lines,
        anchors=anchors,
        heading_count=heading_count,
        fence_pairs=fence_pairs,
    )


def _unescaped_index(value: str, needle: str, start: int) -> int:
    index = value.find(needle, start)
    while index >= 0:
        backslashes = 0
        cursor = index - 1
        while cursor >= 0 and value[cursor] == "\\":
            backslashes += 1
            cursor -= 1
        if backslashes % 2 == 0:
            return index
        index = value.find(needle, index + 1)
    return -1


def _inline_link_destinations(line: str) -> tuple[str, ...]:
    destinations: list[str] = []
    search_start = 0
    while True:
        separator = _unescaped_index(line, "](", search_start)
        if separator < 0:
            break
        opening = line.rfind("[", search_start, separator)
        if opening < 0:
            search_start = separator + 2
            continue

        depth = 1
        cursor = separator + 2
        escaped = False
        angle_destination = False
        while cursor < len(line):
            character = line[cursor]
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == "<" and cursor == separator + 2:
                angle_destination = True
            elif character == ">" and angle_destination:
                angle_destination = False
            elif not angle_destination and character == "(":
                depth += 1
            elif not angle_destination and character == ")":
                depth -= 1
                if depth == 0:
                    destinations.append(line[separator + 2 : cursor])
                    search_start = cursor + 1
                    break
            cursor += 1
        else:
            break
    return tuple(destinations)


def _destination(inside: str) -> str:
    value = inside.strip()
    if value.startswith("<"):
        closing = _unescaped_index(value, ">", 1)
        if closing >= 0:
            return value[1:closing]

    escaped = False
    for index, character in enumerate(value):
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character.isspace():
            return value[:index]
    return value


def _is_external(target: str) -> bool:
    return target.startswith("//") or _EXTERNAL_SCHEME.match(target) is not None


def _resolve_target(root: Path, source: Path, path_part: str) -> Path:
    decoded = unquote(path_part).replace("\\ ", " ")
    if decoded == "":
        return source
    if decoded.startswith("/"):
        raise ValueError("absolute local target is not allowed")
    destination = (source.parent / decoded).resolve()
    destination.relative_to(root)
    return destination


def check_markdown_links(
    root: Path,
    paths: Iterable[Path] | None = None,
) -> MarkdownLinkReport:
    repository_root = root.resolve()
    if not repository_root.is_dir():
        raise MarkdownLinkCheckError((f"repository root is not a directory: {root}",))
    sources = _source_paths(repository_root, paths)
    documents: dict[Path, _MarkdownDocument] = {}
    issues: list[str] = []
    for source in sources:
        try:
            documents[source] = _load_document(repository_root, source)
        except MarkdownLinkCheckError as exc:
            issues.extend(exc.issues)

    local_links = 0
    anchor_links = 0
    for source in sources:
        document = documents.get(source)
        if document is None:
            continue
        for line_number, line in document.content_lines:
            for inside in _inline_link_destinations(line):
                target = _destination(inside)
                if target == "" or _is_external(target):
                    continue
                local_links += 1
                path_part, separator, fragment = target.partition("#")
                if separator:
                    anchor_links += 1
                try:
                    destination = _resolve_target(repository_root, source, path_part)
                except ValueError:
                    issues.append(
                        f"{_display_path(repository_root, source)}:{line_number}: "
                        f"target escapes repository root: {target}"
                    )
                    continue
                if not destination.exists():
                    issues.append(
                        f"{_display_path(repository_root, source)}:{line_number}: "
                        f"missing target: {target}"
                    )
                    continue
                if fragment == "":
                    continue
                if not destination.is_file() or destination.suffix.casefold() != ".md":
                    issues.append(
                        f"{_display_path(repository_root, source)}:{line_number}: "
                        f"anchor target is not Markdown: {target}"
                    )
                    continue
                target_document = documents.get(destination)
                if target_document is None:
                    try:
                        target_document = _load_document(repository_root, destination)
                    except MarkdownLinkCheckError as exc:
                        issues.extend(exc.issues)
                        continue
                    documents[destination] = target_document
                wanted_anchor = unquote(fragment).casefold()
                if wanted_anchor not in target_document.anchors:
                    issues.append(
                        f"{_display_path(repository_root, source)}:{line_number}: "
                        f"missing anchor '{wanted_anchor}' in "
                        f"{_display_path(repository_root, destination)}"
                    )

    if issues:
        raise MarkdownLinkCheckError(issues)
    return MarkdownLinkReport(
        markdown_files=len(sources),
        local_links=local_links,
        anchor_links=anchor_links,
        headings=sum(
            document.heading_count for document in documents.values() if document.path in sources
        ),
        fence_pairs=sum(
            document.fence_pairs for document in documents.values() if document.path in sources
        ),
    )


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check local links and ATX heading anchors in current Markdown files.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root. Defaults to this script's repository.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Optional Markdown paths relative to --root.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _argument_parser().parse_args(argv)
    selected_paths = arguments.paths or None
    try:
        report = check_markdown_links(arguments.root, selected_paths)
    except MarkdownLinkCheckError as exc:
        for issue in exc.issues:
            print(issue, file=sys.stderr)
        return 1
    print(
        f"markdown_files={report.markdown_files} "
        f"local_links={report.local_links} "
        f"anchor_links={report.anchor_links} "
        f"headings={report.headings} "
        f"fence_pairs={report.fence_pairs}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
