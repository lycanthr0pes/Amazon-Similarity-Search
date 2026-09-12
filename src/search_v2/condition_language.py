"""Local, source-bound condition modifiers; no model inference or provider calls."""

import hashlib
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.search_v2.tokenizer import _analyze_japanese_source
from src.search_v2.candidate_diagnostics import CandidatePreparationError

PROFILE = "condition-language-v1"
Strength = Literal["required", "preferred", "excluded", "neutral"]
_PREFERRED = r"できれば|出来れば|なるべく|可能なら|できるだけ|出来るだけ"
_REQUIRED = r"必ず|絶対に"
_PARTICLE = r"(?:には|については|は|が|を|に)?"
_NEUTRAL = re.compile(
    _PARTICLE
    + r"(?:なくても(?:よい|良い|いい|構わない|かまわない|構いません|かまいません)|こだわらない|こだわりません|拘らない|拘りません|問わない|どちらでも(?:よい|いい)|でも(?:構わない|かまわない|構いません|かまいません|よい|いい))(?:です)?$"
)
_EXCLUDED = re.compile(
    _PARTICLE
    + r"(?:避けたい|避けます|避けてほしい|除外(?:する|してほしい)?|不要|いらない|要らない|いりません|要りません|必要ない|必要ありません|なし|無し|以外|ではない)(?:です)?$"
)
_PREFERRED_END = re.compile(
    _PARTICLE
    + r"(?:希望(?:します|しています|している|する)?|望ましい|あると(?:よい|良い|いい|うれしい|嬉しい)|だと(?:うれしい|嬉しい|ありがたい)|なら(?:うれしい|嬉しい)|だとうれしい)(?:です)?$"
)
_REQUIRED_END = re.compile(_PARTICLE + r"(?:必須|必要|絶対条件)(?:です)?$")
_AMBIGUOUS = re.compile(
    r"避けたくない|(?:不要|必要ない|いらない|なし|必須|希望)(?:では|じゃ|とは)ない|ない(?:わけ|こと|とは).*ない|なくはない"
)


class ConditionExpression(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(repr=False)
    target: str = Field(repr=False)
    strength: Strength
    reason: str


class ConditionLanguageError(CandidatePreparationError):
    def __init__(self, issues):
        super().__init__("condition_strength")
        self.issues = tuple(issues)


def _issue(quote, start, code):
    return {"start": start, "end": start + len(quote), "code": code}


def interpret_clause(quote, *, start=0):
    value = quote.strip()
    if _AMBIGUOUS.search(value):
        raise ConditionLanguageError([_issue(quote, start, "ambiguous_negation")])
    preferred = required = False
    # Prefixes modify their own clause, never a following comma-separated clause.
    while True:
        match = re.match(r"^(?:" + _PREFERRED + "|" + _REQUIRED + r")\s*", value)
        if not match:
            break
        preferred |= bool(re.fullmatch(_PREFERRED, match.group().strip()))
        required |= bool(re.fullmatch(_REQUIRED, match.group().strip()))
        value = value[match.end() :]
    # Topic-marked modifiers: e.g. 容量はできれば300ml以上.
    value, count = re.subn(r"(?<=[はが])(?:" + _PREFERRED + r")\s*", "", value)
    preferred |= bool(count)
    value, count = re.subn(r"(?<=[はが])(?:" + _REQUIRED + r")\s*", "", value)
    required |= bool(count)
    strength, reason = "required", "explicit_condition"
    for pattern, selected, code in (
        (_NEUTRAL, "neutral", "permission"),
        (_EXCLUDED, "excluded", "avoidance"),
        (_PREFERRED_END, "preferred", "preference_suffix"),
        (_REQUIRED_END, "required", "requirement_suffix"),
    ):
        match = pattern.search(value)
        if match:
            value = value[: match.start()].strip()
            strength, reason = selected, code
            preferred |= selected == "preferred"
            required |= code == "requirement_suffix"
            break
    if preferred and required or required and strength in {"excluded", "neutral"}:
        raise ConditionLanguageError([_issue(quote, start, "conflicting_modifiers")])
    if reason == "explicit_condition":
        strength = "preferred" if preferred else "required"
        reason = "preference_prefix" if preferred else "requirement_prefix" if required else reason
    if not value or re.search(_PREFERRED + r"|こだわら|構わ|避けた|希望|必須", value):
        raise ConditionLanguageError([_issue(quote, start, "modifier_scope")])
    return ConditionExpression(
        start=start,
        end=start + len(quote),
        quote=quote,
        target=value,
        strength=strength,
        reason=reason,
    )


def clause_spans(source):
    start = 0
    for separator in re.finditer(r"[。\n、]|(?<=(?:以上|以下|以内))で|(?<=対応)の", source):
        text = source[start : separator.start()]
        if text.strip():
            yield start + len(text) - len(text.lstrip()), text.strip()
        start = separator.end()
    if source[start:].strip():
        text = source[start:]
        yield start + len(text) - len(text.lstrip()), text.strip()


def analyze_conditions(source, *, structure=None):
    text = _analyze_japanese_source(source).text
    if structure is None:
        spans = clause_spans(text)
    else:
        from src.search_v2.lexical_structure import validate_structure

        validate_structure(source, structure)
        spans = (
            (fragment.start + start, quote)
            for fragment in structure.fragments
            for start, quote in clause_spans(fragment.text(text))
        )
    rows = tuple(interpret_clause(quote, start=start) for start, quote in spans)
    if len(rows) > 24:
        raise ConditionLanguageError([_issue(rows[24].quote, rows[24].start, "condition_count")])
    grouped = {}
    for row in rows:
        key = re.sub(r"\s|(?:です)$", "", row.target).casefold()
        previous = grouped.get(key)
        if previous and previous.strength != row.strength:
            raise ConditionLanguageError(
                [_issue(r.quote, r.start, "conflicting_conditions") for r in (previous, row)]
            )
        grouped[key] = row
    return rows


def language_digest(source, *, structure=None):
    rows = analyze_conditions(source, structure=structure)
    payload = PROFILE + "\n" + "\n".join(r.model_dump_json() for r in rows)
    return hashlib.sha256(payload.encode()).hexdigest()


def original_range(source, start, end):
    """Map normalized offsets back to the exact submitted Unicode string."""
    from bisect import bisect_left, bisect_right

    lengths = [
        len(unicodedata.normalize("NFKC", source[:i]).casefold()) for i in range(len(source) + 1)
    ]
    left = max(0, bisect_right(lengths, start) - 1)
    right = min(
        len(source), bisect_right(lengths, end) - 1 if end in lengths else bisect_left(lengths, end)
    )
    return left, right


def display_conditions(source, quotes=(), *, structure=None):
    accepted = set(quotes)
    rows = []
    for expression in analyze_conditions(source, structure=structure):
        if (
            expression.quote not in accepted
            and expression.reason == "explicit_condition"
            and not re.search(r"[0-9].*円", expression.target)
        ):
            continue
        start, end = original_range(source, expression.start, expression.end)
        rows.append(
            {**expression.model_dump(), "start": start, "end": end, "quote": source[start:end]}
        )
    return rows


def display_issues(source, issues):
    result = []
    for issue in issues:
        start, end = original_range(source, issue["start"], issue["end"])
        result.append(
            {"start": start, "end": end, "quote": source[start:end], "code": issue["code"]}
        )
    return result
