from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
from typing import Literal
import unicodedata

from sudachipy import dictionary
from sudachipy import tokenizer as sudachi_tokenizer


_CONTENT_PARTS_OF_SPEECH = frozenset({"名詞", "動詞", "形容詞", "形状詞"})
_ENGLISH_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_JAPANESE_CHARACTER_PATTERN = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
_URL_PATTERN = re.compile(r"(?i)(?:[a-z][a-z0-9+.-]*://|www\.)")


@dataclass(frozen=True, slots=True)
class _MorphemeSpan:
    surface: str
    normalized: str
    dictionary_form: str
    part_of_speech: str
    begin: int
    end: int


@dataclass(frozen=True, slots=True)
class _AnalyzedSource:
    text: str
    morphemes: tuple[_MorphemeSpan, ...]


@lru_cache(maxsize=1)
def _sudachi() -> sudachi_tokenizer.Tokenizer:
    return dictionary.Dictionary().create()


def _normalized_input(value: str) -> str:
    if type(value) is not str:
        raise TypeError("tokenizer input must be a string")
    normalized = unicodedata.normalize("NFKC", value)
    if any(character in "\r\n" for character in normalized):
        raise ValueError("tokenizer input must not contain a newline")
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        raise ValueError("tokenizer input must not contain control characters")
    if _URL_PATTERN.search(normalized):
        raise ValueError("tokenizer input must not contain a URL")
    return normalized.casefold()


def _normalized_source(value: str) -> str:
    if type(value) is not str:
        raise TypeError("source input must be a string")
    normalized = unicodedata.normalize("NFKC", value)
    if any(
        unicodedata.category(character).startswith("C") and not character.isspace()
        for character in normalized
    ):
        raise ValueError("source input must not contain control characters")
    return normalized.casefold()


def _analyze_japanese_source(value: str) -> _AnalyzedSource:
    normalized = _normalized_source(value)
    morphemes = tuple(
        _MorphemeSpan(
            surface=normalized[morpheme.begin() : morpheme.end()],
            normalized=unicodedata.normalize("NFKC", morpheme.normalized_form()).casefold(),
            dictionary_form=unicodedata.normalize("NFKC", morpheme.dictionary_form()).casefold(),
            part_of_speech=morpheme.part_of_speech()[0],
            begin=morpheme.begin(),
            end=morpheme.end(),
        )
        for morpheme in _sudachi().tokenize(
            normalized,
            sudachi_tokenizer.Tokenizer.SplitMode.C,
        )
    )
    return _AnalyzedSource(text=normalized, morphemes=morphemes)


def _append_unique(tokens: list[str], seen: set[str], token: str) -> None:
    token = unicodedata.normalize("NFKC", token).casefold().strip()
    if not token:
        return
    identity = token.casefold()
    if identity in seen:
        return
    seen.add(identity)
    tokens.append(token)


def _tokenize_japanese(value: str) -> list[str]:
    tokens: list[str] = []
    pending_prefixes: list[str] = []
    previous_start: int | None = None
    previous_end: int | None = None
    for morpheme in _sudachi().tokenize(
        value,
        sudachi_tokenizer.Tokenizer.SplitMode.C,
    ):
        surface = unicodedata.normalize("NFKC", morpheme.surface()).casefold()
        normalized = unicodedata.normalize("NFKC", morpheme.normalized_form()).casefold()
        if normalized == "*":
            normalized = surface
        part_of_speech = morpheme.part_of_speech()[0]
        if part_of_speech == "接頭辞" and _JAPANESE_CHARACTER_PATTERN.search(surface):
            pending_prefixes.append(surface)
            continue
        if part_of_speech == "接尾辞" and _JAPANESE_CHARACTER_PATTERN.search(surface):
            # Keep the compound intact: splitting 名刺入れ changes 入れ to a verb
            # when the query planner tokenizes the product phrase again.
            if tokens and previous_start is not None and previous_end == morpheme.begin():
                # Dictionary forms such as 軽い must not produce 軽いさ.
                tokens[-1] = value[previous_start : morpheme.end()]
            else:
                tokens.append(surface)
                previous_start = morpheme.begin()
            previous_end = morpheme.end()
            pending_prefixes.clear()
            continue
        previous_count = len(tokens)
        if part_of_speech in _CONTENT_PARTS_OF_SPEECH:
            prefixed = "".join((*pending_prefixes, normalized))
            if _JAPANESE_CHARACTER_PATTERN.search(surface) and _JAPANESE_CHARACTER_PATTERN.search(
                prefixed
            ):
                tokens.append(prefixed)
        start = morpheme.begin() - sum(len(prefix) for prefix in pending_prefixes)
        pending_prefixes.clear()
        for token in _ENGLISH_TOKEN_PATTERN.findall(surface):
            tokens.append(token)
        previous_end = morpheme.end() if len(tokens) > previous_count else None
        previous_start = start if previous_end is not None else None
    # Deduplicate complete words so 名刺 and 名刺入れ remain distinct.
    result: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        _append_unique(result, seen, token)
    return result


def tokenize_search_text(
    value: str,
    *,
    language: Literal["ja", "en"],
) -> list[str]:
    """Split one untrusted semantic phrase with fixed language-specific rules."""
    if language not in ("ja", "en"):
        raise ValueError("unsupported tokenizer language")
    normalized = _normalized_input(value)
    if language == "en":
        tokens: list[str] = []
        seen: set[str] = set()
        for token in _ENGLISH_TOKEN_PATTERN.findall(normalized):
            _append_unique(tokens, seen, token)
        return tokens
    return _tokenize_japanese(normalized)
