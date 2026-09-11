"""First-exposure inputs with omitted property names, frozen before live measurement."""

from tools.bonsai_unseen_categories import Case, Expected


CASES = (
    Case(
        "shredder",
        "シュレッダー",
        "シュレッダー。8枚以上。自動停止対応。",
        (
            Expected(
                ("細断枚数", "同時細断枚数", "最大細断枚数", "裁断枚数"),
                "同時に細断できる紙の枚数",
                r"細断|裁断",
                "8枚以上",
                8,
                "枚",
                "at_least",
            ),
            Expected(
                ("自動停止対応", "自動停止", "自動停止機能"),
                "自動で動作を停止する機能",
                r"自動.*停止|停止.*自動",
                "自動停止対応",
                True,
            ),
        ),
    ),
    Case(
        "projector",
        "プロジェクター",
        "プロジェクター。3000lm以上。台形補正対応を希望。",
        (
            Expected(
                ("明るさ", "光束", "全光束", "投影光束"),
                "投影する光の明るさを表す光束",
                r"光束|明るさ",
                "3000lm以上",
                3000,
                "lm",
                "at_least",
            ),
            Expected(
                ("台形補正対応", "台形補正", "台形補正機能"),
                "投影画像の台形歪みを補正する機能",
                r"台形.*補正",
                "台形補正対応を希望",
                True,
                strength="preferred",
            ),
        ),
    ),
    Case(
        "driver",
        "電動ドライバー",
        "電動ドライバー。12V以上。逆回転対応。",
        (
            Expected(
                ("電圧", "定格電圧", "バッテリー電圧"),
                "電源またはバッテリーの電圧",
                r"電圧",
                "12V以上",
                12,
                "V",
                "at_least",
            ),
            Expected(
                ("逆回転対応", "逆回転", "逆回転機能"),
                "逆方向へ回転する機能",
                r"逆.*回転",
                "逆回転対応",
                True,
            ),
        ),
    ),
    Case(
        "scanner",
        "スキャナー",
        "スキャナー。600dpi以上。両面読取対応を希望。",
        (
            Expected(
                ("解像度", "光学解像度", "読取解像度", "読み取り解像度"),
                "画像を読み取る解像度",
                r"解像度",
                "600dpi以上",
                600,
                "dpi",
                "at_least",
            ),
            Expected(
                ("両面読取対応", "両面読取", "両面読み取り対応"),
                "紙の両面を読み取る機能",
                r"両面.*読",
                "両面読取対応を希望",
                True,
                strength="preferred",
            ),
        ),
    ),
)
