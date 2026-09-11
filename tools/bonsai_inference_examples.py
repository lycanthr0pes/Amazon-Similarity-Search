"""Five fixed cross-category diagnostics, separate from the prompt's example."""

from dataclasses import dataclass
from decimal import Decimal
import json
import re
import unicodedata

from src.search_v2.bonsai_adapter import BonsaiCompactSearchIntentDraft
from src.search_v2.dynamic_attributes import _unit_key
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from tools.bonsai_attribute_inference import run_inference_probe


@dataclass(frozen=True)
class Condition:
    key: str
    value: str | bool | int
    label: str = ""
    meaning: str = ""
    quote: str = ""
    aliases: tuple[str, ...] = ()
    unit: str = ""
    strength: str = "required"

    def payload(self):
        numeric = type(self.value) is int
        boolean = type(self.value) is bool
        value = (
            {"value_type": "integer", "minimum": self.value, "unit": self.unit}
            if numeric
            else {"value_type": "boolean", "value": self.value}
            if boolean
            else {"value_type": "enum", "values": [self.value]}
        )
        result = {"attribute_key": self.key}
        if self.key == "custom":
            result["attribute_definition"] = {
                "label": self.label,
                "meaning": self.meaning,
                "source_quote": self.quote,
            }
        result.update(
            operator="at_least" if numeric else "equals",
            expected_value=value,
            strength=self.strength,
        )
        return result


@dataclass(frozen=True)
class Example:
    case_id: str
    source: str
    products: tuple[str, ...]
    conditions: tuple[Condition, ...]

    def payload(self):
        return {
            "product_name_ja": self.products[0],
            "typed_conditions": [c.payload() for c in self.conditions],
        }


EXAMPLES = (
    Example(
        "table",
        "丸い木製テーブル。",
        ("テーブル",),
        (
            Condition("form.shape", "round"),
            Condition("material.type", "wood"),
        ),
    ),
    Example(
        "backpack",
        "青いリュック。容量20L以上。撥水対応。",
        ("リュック", "リュックサック"),
        (
            Condition("appearance.color", "blue"),
            Condition(
                "custom",
                20,
                "容量",
                "荷物を収納できる容量",
                "容量20L以上",
                ("収納容量", "内容量", "容積"),
                "L",
            ),
            Condition(
                "custom",
                True,
                "撥水対応",
                "表面で水をはじく撥水機能",
                "撥水対応",
                ("撥水", "撥水性", "撥水機能"),
            ),
        ),
    ),
    Example(
        "headphones",
        "黒いヘッドホン。連続再生時間20時間以上。ノイズキャンセリング対応。",
        ("ヘッドホン",),
        (
            Condition("appearance.color", "black"),
            Condition(
                "custom",
                20,
                "連続再生時間",
                "連続して音楽を再生できる時間",
                "連続再生時間20時間以上",
                ("再生時間", "バッテリー持続時間"),
                "時間",
            ),
            Condition(
                "custom",
                True,
                "ノイズキャンセリング対応",
                "周囲の雑音を抑えるノイズキャンセリング機能",
                "ノイズキャンセリング対応",
                ("ノイズキャンセリング", "ノイズキャンセリング機能"),
            ),
        ),
    ),
    Example(
        "monitor",
        "白いモニター。画面サイズ27インチ以上。VESA対応。",
        ("モニター", "ディスプレイ"),
        (
            Condition("appearance.color", "white"),
            Condition(
                "custom",
                27,
                "画面サイズ",
                "画面の対角線の大きさ",
                "画面サイズ27インチ以上",
                ("画面のサイズ", "画面対角", "画面対角サイズ"),
                "インチ",
            ),
            Condition(
                "custom",
                True,
                "VESA対応",
                "VESA規格の取り付けへの対応",
                "VESA対応",
                ("VESA", "VESA規格対応", "VESAマウント対応"),
            ),
        ),
    ),
    Example(
        "keyboard",
        "黒いキーボード。バックライト対応を希望。Bluetooth対応は除外。",
        ("キーボード",),
        (
            Condition("appearance.color", "black"),
            Condition(
                "custom",
                True,
                "バックライト対応",
                "キーを照らすバックライトの有無",
                "バックライト対応を希望",
                ("バックライト", "バックライト機能"),
                strength="preferred",
            ),
            Condition(
                "custom",
                True,
                "Bluetooth対応",
                "Bluetooth接続への対応",
                "Bluetooth対応は除外",
                ("Bluetooth", "Bluetooth接続対応"),
                strength="excluded",
            ),
        ),
    ),
)

# Bounded, predeclared meaning checks; not an open-ended semantic judge.
MEANINGS = {
    "容量": r"容量|容積|収納.*量",
    "撥水対応": r"撥水|水.*はじ|水.*弾|水に濡れることを防ぐ",
    "連続再生時間": r"再生.*時間|バッテリー.*時間|連続.*時間",
    "ノイズキャンセリング対応": r"ノイズキャンセリング|雑音.*抑|騒音.*低減|(?:外部|周囲)の音をキャンセリングする",
    "画面サイズ": r"画面|対角|ディスプレイ.*サイズ",
    "VESA対応": r"vesa",
    "バックライト対応": r"バックライト|キー.*照",
    "Bluetooth対応": r"bluetooth",
}


def normalized(value):
    return unicodedata.normalize("NFKC", value).casefold().strip()


def matches(candidate, expected):
    if candidate.attribute_key != expected.key or candidate.strength != expected.strength:
        return False
    if expected.key == "custom":
        definition = candidate.attribute_definition
        if definition is None:
            return False
        if normalized(definition.label) not in {
            normalized(label) for label in (expected.label, *expected.aliases)
        }:
            return False
        if expected.label == "撥水対応" and re.search("防水|水中|浸水|水没", definition.meaning):
            return False
        if not re.search(MEANINGS[expected.label], normalized(definition.meaning)):
            return False
        if re.search("非対応|不可|できない|ではない|しない|しません", definition.meaning):
            return False
    value = candidate.expected_value
    if type(expected.value) is int:
        return (
            candidate.operator == "at_least"
            and value.value_type in {"integer", "decimal"}
            and value.minimum is not None
            and Decimal(str(value.minimum)) == expected.value
            and value.maximum is None
            and _unit_key(value.unit) == _unit_key(expected.unit)
        )
    if candidate.operator != "equals":
        return False
    if type(expected.value) is bool:
        return value.value_type == "boolean" and value.value is expected.value
    return value.value_type == "enum" and tuple(value.values) == (expected.value,)


def condition_checks(intent, example):
    return {
        "product_type": intent.product_name_ja in example.products,
        "exact_condition_count": len(intent.typed_conditions) == len(example.conditions),
        **{
            f"condition_{index + 1}": sum(matches(c, expected) for c in intent.typed_conditions)
            == 1
            for index, expected in enumerate(example.conditions)
        },
    }


def judge_example(intent, example):
    proposal = build_typed_requirement_proposal(intent)
    expected_custom = sum(c.key == "custom" for c in example.conditions)
    return {
        **condition_checks(intent, example),
        "proposal_ready": proposal.status == "ready",
        "exact_requirement_count": len(proposal.requirements) == len(example.conditions),
        "custom_attributes": sum(
            r.attribute_key.startswith("search.") for r in proposal.requirements
        )
        == expected_custom,
        "no_unrequested_fields": not (
            intent.price.mode != "none"
            or intent.brand
            or intent.model_number
            or any(
                normalized(term) not in normalized(example.source)
                for terms in (
                    intent.required_terms_ja,
                    intent.required_terms_en,
                    intent.preferred_terms_ja,
                    intent.preferred_terms_en,
                    intent.negative_terms_ja,
                    intent.negative_terms_en,
                )
                for term in terms
            )
        ),
    }


def project_example(body, example):
    result = {"stage": "draft_invalid"}
    try:
        data = json.loads(json.loads(body)["choices"][0]["message"]["content"])
        from src.search_v2.source_constraints import expand_source_names

        data = expand_source_names(example.source, data)
        draft = BonsaiCompactSearchIntentDraft.model_validate(data).to_search_intent_draft()
        result.update(
            stage="draft_valid",
            typed_count=len(draft.typed_conditions),
            custom_count=sum(c.attribute_key == "custom" for c in draft.typed_conditions),
            checks=condition_checks(draft, example),
        )
    except Exception:
        pass  # Full response is private; the projection has only fixed checks.
    return result


def run_example(config, *, log_dir, example):
    return run_inference_probe(
        config,
        log_dir=log_dir,
        source_input=example.source,
        judge=lambda intent: judge_example(intent, example),
        project=lambda body: project_example(body, example),
    )
