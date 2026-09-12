"""Source-owned title fields and bounded synonym assistance for candidate ranking."""

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.search_v2.bonsai_query_terms import TranslatedTerm
from src.search_v2.candidate_text import TEXT_PROFILE_ID, TEXT_PROFILE_SHA256
from src.search_v2.tokenizer import tokenize_search_text


SYNONYM_WEIGHT = 0.25
_METADATA = re.compile(
    r"(?:^|[。\n、])\s*(?P<label>ブランド|メーカー|型番|モデル番号|カテゴリ英語|カテゴリ|カテゴリー|brand|model|category_en|category)"
    r"\s*[:：]\s*(?P<value>[^。\n、]{1,100})(?=[。\n、]|$)",
    re.I,
)


class TitleComparison(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", revalidate_instances="always"
    )
    profile_id: Literal["candidate-text-v1"] = TEXT_PROFILE_ID
    profile_sha256: Literal[TEXT_PROFILE_SHA256] = TEXT_PROFILE_SHA256
    product_name_ja: str = Field(min_length=1, max_length=100)
    product_name_en: str | None = Field(default=None, max_length=100)
    category_ja: str | None = Field(default=None, max_length=100)
    category_en: str | None = Field(default=None, max_length=100)
    brand: str | None = Field(default=None, max_length=100)
    model_number: str | None = Field(default=None, max_length=100)
    synonyms: tuple[TranslatedTerm, ...] = Field(default=(), max_length=3)


def title_metadata(source):
    source = unicodedata.normalize("NFKC", source)
    values, quotes = {}, []
    for match in _METADATA.finditer(source):
        label, value = match["label"].casefold(), match["value"].strip()
        key = (
            "brand"
            if label in {"ブランド", "メーカー", "brand"}
            else "model_number"
            if label in {"型番", "モデル番号", "model"}
            else "category_en"
            if label in {"カテゴリ英語", "category_en"}
            else "category_ja"
        )
        if key in values and values[key] != value:
            raise ValueError("Conflicting title metadata")
        values[key] = value
        quotes.append(source[match.start("label") : match.end()])
    return values, tuple(quotes)


def build_title_comparison(source, intent, expansion):
    values, _ = title_metadata(source)
    original = intent.product_name_ja
    model = values.get("model_number")
    brand = values.get("brand")
    phrase = original
    for value in (brand, model):
        if value:
            phrase = re.sub(re.escape(value), " ", phrase, flags=re.I)
    tokens = tokenize_search_text(phrase, language="ja")
    category = values.get("category_ja") or (tokens[-1] if tokens else None)
    terms = expansion.terms if expansion is not None and expansion.status == "ready" else None
    english = terms.original_en if terms is not None else None
    # A lexical category is the head of the source product phrase, not a provider taxonomy.
    head = re.split(r"\b(?:with|for|in|of)\b", english or "", maxsplit=1, flags=re.I)[0]
    english_tokens = tokenize_search_text(head, language="en")
    return TitleComparison(
        product_name_ja=original,
        product_name_en=english,
        category_ja=category,
        category_en=values.get("category_en") or (english_tokens[-1] if english_tokens else None),
        brand=brand,
        model_number=model,
        synonyms=terms.synonyms if terms is not None else (),
    )


def _coverage(phrase, title, language):
    tokens = set(tokenize_search_text(phrase, language=language))
    observed = set(tokenize_search_text(title, language=language))
    return len(tokens & observed) / len(tokens) if tokens else 0.0


def _bilingual(japanese, english, title):
    return max(
        _coverage(japanese, title, "ja") if japanese else 0.0,
        _coverage(english, title, "en") if english else 0.0,
    )


def _exact_identity(value, title):
    value = unicodedata.normalize("NFKC", value).casefold()
    title = unicodedata.normalize("NFKC", title).casefold()
    return float(
        re.search(r"(?<![a-z0-9])" + re.escape(value) + r"(?![a-z0-9])", title) is not None
    )


def score_title(comparison, title):
    original = _bilingual(comparison.product_name_ja, comparison.product_name_en, title)
    category = _bilingual(comparison.category_ja, comparison.category_en, title)
    synonym = max((_bilingual(t.ja, t.en, title) for t in comparison.synonyms), default=0.0)
    # Categories are a separate comparison field. A synonym can fill missing lexical
    # coverage only up to 25%; repeating variants never accumulates extra points.
    components = [original + SYNONYM_WEIGHT * (1 - original) * synonym]
    if comparison.category_ja or comparison.category_en:
        components.append(category + SYNONYM_WEIGHT * (1 - category) * synonym)
    for identity in (comparison.brand, comparison.model_number):
        if identity:
            components.append(_exact_identity(identity, title))
    return sum(components) / len(components)
