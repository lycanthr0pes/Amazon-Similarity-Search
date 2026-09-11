"""Predeclared first-exposure inference evaluation; never included in model prompts."""

from dataclasses import dataclass
from decimal import Decimal
import json
import re

from src.search_v2.bonsai_adapter import BonsaiCompactSearchIntentDraft
from src.search_v2.dynamic_attributes import _unit_key
from src.search_v2.typed_intent_adapter import build_typed_requirement_proposal
from tools.bonsai_attribute_inference import run_inference_probe
from tools.bonsai_inference_examples import normalized


@dataclass(frozen=True)
class Expected:
    labels: tuple[str, ...]
    meaning: str
    pattern: str
    quote: str
    value: int | bool | str
    unit: str = ""
    operator: str = "equals"
    strength: str = "required"
    key: str = "custom"

    def payload(self):
        if type(self.value) is int:
            bound = "minimum" if self.operator == "at_least" else "maximum"
            value = {"value_type": "integer", bound: self.value, "unit": self.unit}
        elif type(self.value) is bool:
            value = {"value_type": "boolean", "value": self.value}
        else:
            value = {"value_type": "enum", "values": [self.value]}
        condition = {"attribute_key": self.key}
        if self.key == "custom":
            condition["attribute_definition"] = {
                "label": self.labels[0],
                "meaning": self.meaning,
                "source_quote": self.quote,
            }
        condition.update(strength=self.strength, operator=self.operator, expected_value=value)
        return condition


@dataclass(frozen=True)
class Case:
    case_id: str
    category: str
    source: str
    expected: tuple[Expected, ...]

    def payload(self):
        return {
            "product_name_ja": self.category,
            "typed_conditions": [condition.payload() for condition in self.expected],
        }


CASES = (
    Case(
        "tent_1",
        "テント",
        "青いテント。耐水圧2000mm以上。自立式対応。",
        (
            Expected((), "", "", "", "blue", key="appearance.color"),
            Expected(
                ("耐水圧",),
                "水の圧力に耐える性能",
                r"耐水圧|水.*圧",
                "耐水圧2000mm以上",
                2000,
                "mm",
                "at_least",
            ),
            Expected(
                ("自立式対応", "自立式", "自立対応"),
                "テントが自立する機能",
                r"自立",
                "自立式対応",
                True,
            ),
        ),
    ),
    Case(
        "tent_2",
        "テント",
        "テント。重量3kg以下。スカート対応を希望。",
        (
            Expected(
                ("重量", "重さ", "本体重量"),
                "商品の重量",
                r"重量|重さ|質量",
                "重量3kg以下",
                3,
                "kg",
                "at_most",
            ),
            Expected(
                ("スカート対応", "スカート", "スカート付き"),
                "裾からの風の侵入を防ぐスカート",
                r"スカート|裾.*風",
                "スカート対応を希望",
                True,
                strength="preferred",
            ),
        ),
    ),
    Case(
        "sewing_1",
        "ミシン",
        "白いミシン。縫い速度700針/分以上。自動糸通し対応。",
        (
            Expected((), "", "", "", "white", key="appearance.color"),
            Expected(
                ("縫い速度", "縫製速度", "縫製スピード"),
                "一分間に縫える針数",
                r"縫.*速|針.*分|分.*針",
                "縫い速度700針/分以上",
                700,
                "針/分",
                "at_least",
            ),
            Expected(
                ("自動糸通し対応", "自動糸通し", "自動糸通し機能"),
                "自動的に針へ糸を通す機能",
                r"自動.*糸|糸.*自動",
                "自動糸通し対応",
                True,
            ),
        ),
    ),
    Case(
        "sewing_2",
        "ミシン",
        "ミシン。フットコントローラー対応を希望。刺繍対応は除外。",
        (
            Expected(
                ("フットコントローラー対応", "フットコントローラー", "フットコントローラ対応"),
                "足で縫製を操作する機能",
                r"フットコントローラ|足.*操作|足.*制御",
                "フットコントローラー対応を希望",
                True,
                strength="preferred",
            ),
            Expected(
                ("刺繍対応", "刺繍", "刺繍機能"),
                "刺繍を縫う機能",
                r"刺繍|ししゅう",
                "刺繍対応は除外",
                True,
                strength="excluded",
            ),
        ),
    ),
    Case(
        "printer_1",
        "プリンター",
        "黒いプリンター。給紙枚数100枚以上。自動両面印刷対応。",
        (
            Expected((), "", "", "", "black", key="appearance.color"),
            Expected(
                ("給紙枚数", "給紙容量", "用紙容量"),
                "給紙できる用紙の枚数",
                r"給紙|用紙.*枚数|紙.*容量",
                "給紙枚数100枚以上",
                100,
                "枚",
                "at_least",
            ),
            Expected(
                ("自動両面印刷対応", "自動両面印刷", "自動両面印刷機能"),
                "紙の両面へ自動で印刷する機能",
                r"自動.*両面|両面.*自動",
                "自動両面印刷対応",
                True,
            ),
        ),
    ),
    Case(
        "printer_2",
        "プリンター",
        "プリンター。無線LAN対応は除外。顔料インク対応を希望。",
        (
            Expected(
                ("無線LAN対応", "無線LAN", "Wi-Fi対応"),
                "無線LANで通信する機能",
                r"無線.*lan|wi.?fi",
                "無線LAN対応は除外",
                True,
                strength="excluded",
            ),
            Expected(
                ("顔料インク対応", "顔料インク"),
                "顔料インクを使えるか",
                r"顔料",
                "顔料インク対応を希望",
                True,
                strength="preferred",
            ),
        ),
    ),
    Case(
        "microscope_1",
        "顕微鏡",
        "顕微鏡。40倍以上。透過照明対応。",
        (
            Expected(
                ("倍率", "拡大倍率", "光学倍率", "総合倍率"),
                "対象を拡大して観察する倍率",
                r"倍率|拡大.*倍",
                "40倍以上",
                40,
                "倍",
                "at_least",
            ),
            Expected(
                ("透過照明対応", "透過照明", "透過照明機能"),
                "試料を透過する光による照明",
                r"透過.*照明|照明.*透過|透過.*光|光.*透過",
                "透過照明対応",
                True,
            ),
        ),
    ),
    Case(
        "microscope_2",
        "顕微鏡",
        "顕微鏡。重量2kg以下。USB接続対応を希望。",
        (
            Expected(
                ("重量", "重さ", "本体重量"),
                "商品の重量",
                r"重量|重さ|質量",
                "重量2kg以下",
                2,
                "kg",
                "at_most",
            ),
            Expected(
                ("USB接続対応", "USB接続", "USB対応"),
                "USBで接続できる機能",
                r"usb",
                "USB接続対応を希望",
                True,
                strength="preferred",
            ),
        ),
    ),
)


def matches(candidate, expected):
    if (candidate.attribute_key, candidate.operator, candidate.strength) != (
        expected.key,
        expected.operator,
        expected.strength,
    ):
        return False
    if expected.key == "custom":
        definition = candidate.attribute_definition
        if definition is None or normalized(definition.label) not in {
            normalized(label) for label in expected.labels
        }:
            return False
        if not re.search(expected.pattern, normalized(definition.meaning)):
            return False
        if re.search("非対応|不可|できない|ではない|しない|しません", definition.meaning):
            return False
    value = candidate.expected_value
    if type(expected.value) is int:
        bound, other = (
            (value.minimum, value.maximum)
            if expected.operator == "at_least"
            else (value.maximum, value.minimum)
        )
        return (
            value.value_type in {"integer", "decimal"}
            and bound is not None
            and other is None
            and Decimal(str(bound)) == expected.value
            and _unit_key(value.unit) == _unit_key(expected.unit)
        )
    if type(expected.value) is bool:
        return value.value_type == "boolean" and value.value is expected.value
    return value.value_type == "enum" and tuple(value.values) == (expected.value,)


def checks(intent, case):
    return {
        "product_type": intent.product_name_ja == case.category,
        "exact_condition_count": len(intent.typed_conditions) == len(case.expected),
        **{
            f"condition_{i + 1}": sum(matches(c, e) for c in intent.typed_conditions) == 1
            for i, e in enumerate(case.expected)
        },
    }


def judge(intent, case):
    proposal = build_typed_requirement_proposal(intent)
    return {
        **checks(intent, case),
        "proposal_ready": proposal.status == "ready",
        "exact_requirement_count": len(proposal.requirements) == len(case.expected),
        "custom_attributes": sum(
            r.attribute_key.startswith("search.") for r in proposal.requirements
        )
        == sum(e.key == "custom" for e in case.expected),
        "no_unrequested_fields": not (
            intent.price.mode != "none"
            or intent.brand
            or intent.model_number
            or any(
                normalized(term) not in normalized(case.source)
                for strength in ("required", "preferred", "negative")
                for lang in ("ja", "en")
                for term in getattr(intent, f"{strength}_terms_{lang}")
            )
        ),
    }


def project(body, case):
    try:
        payload = json.loads(json.loads(body)["choices"][0]["message"]["content"])
        from src.search_v2.source_constraints import expand_source_names

        payload = expand_source_names(case.source, payload)
        draft = BonsaiCompactSearchIntentDraft.model_validate(payload).to_search_intent_draft()
        return {
            "stage": "draft_valid",
            "checks": checks(draft, case),
            "typed_count": len(draft.typed_conditions),
            "custom_count": sum(c.attribute_key == "custom" for c in draft.typed_conditions),
        }
    except Exception:
        # Raw response remains private; fixed stage is safe even for malformed provider data.
        return {"stage": "draft_invalid"}


def run_case(config, *, log_dir, case):
    return run_inference_probe(
        config,
        log_dir=log_dir,
        source_input=case.source,
        judge=lambda intent: judge(intent, case),
        project=lambda body: project(body, case),
    )
