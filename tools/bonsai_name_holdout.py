"""Unobserved categories for the name-only source contract, declared before generation."""

from tools.bonsai_unseen_categories import Case, Expected


CASES = (
    Case(
        "compressor",
        "エアコンプレッサー",
        "エアコンプレッサー。30L以上。オイルレス対応。",
        (
            Expected(
                ("タンク容量", "空気タンク容量", "容量", "タンク容積"),
                "空気を蓄えるタンクの容量",
                r"容量|容積",
                "30L以上",
                30,
                "L",
                "at_least",
            ),
            Expected(
                ("オイルレス対応", "オイルレス"),
                "潤滑油なしで動作する方式",
                r"オイルレス|潤滑油",
                "オイルレス対応",
                True,
            ),
        ),
    ),
    Case(
        "vacuum",
        "掃除機",
        "掃除機。20000Pa以上。水洗い対応を希望。",
        (
            Expected(
                ("吸引力", "吸引圧", "吸引圧力", "吸込圧", "吸込圧力", "最大吸引力"),
                "ごみを吸い込む圧力",
                r"吸引|吸込|吸い込",
                "20000Pa以上",
                20000,
                "Pa",
                "at_least",
            ),
            Expected(
                ("水洗い対応", "水洗い"),
                "水で洗える仕様",
                r"水洗い|水.*洗",
                "水洗い対応を希望",
                True,
                strength="preferred",
            ),
        ),
    ),
)
