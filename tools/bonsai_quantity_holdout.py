"""Frozen unseen inputs for the EXEC-094 specification-name evaluation."""

from tools.bonsai_unseen_categories import Case, Expected


CASES = (
    Case(
        "power_station",
        "ポータブル電源",
        "ポータブル電源。500Wh以上。急速充電対応を希望。",
        (
            Expected(
                ("電池容量", "バッテリー容量", "蓄電容量", "容量", "定格容量", "電力量", "蓄電量"),
                "蓄えられる電気エネルギーを表す電池容量",
                r"容量|電力量|蓄電量",
                "500Wh以上",
                500,
                "Wh",
                "at_least",
            ),
            Expected(
                ("急速充電対応", "急速充電"),
                "急速充電に対応する機能",
                r"急速.*充電",
                "急速充電対応を希望",
                True,
                strength="preferred",
            ),
        ),
    ),
    Case(
        "dehumidifier",
        "除湿機",
        "除湿機。12L/日以上。連続排水対応。",
        (
            Expected(
                ("除湿能力", "除湿量", "定格除湿能力", "定格除湿量", "最大除湿量"),
                "一日あたりに取り除ける水分を表す除湿量",
                r"除湿",
                "12L/日以上",
                12,
                "L/日",
                "at_least",
            ),
            Expected(
                ("連続排水対応", "連続排水"),
                "水を連続して排水する機能",
                r"連続.*排水",
                "連続排水対応",
                True,
            ),
        ),
    ),
)
