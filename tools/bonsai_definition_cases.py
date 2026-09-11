"""Oracle-context evaluation fixtures, never imported by production code.

Definitions are short authored paraphrases of public manufacturer references.
Keys, expected answers and reference URLs belong to the evaluator, not the prompt.
"""

from dataclasses import dataclass


REFERENCES = {
    "optics": "https://www.microscopyu.com/microscopy-basics/components",
    "aperture": "https://www.microscopyu.com/microscopy-basics/numerical-aperture",
    "scan": "https://faq2.epson.jp/web/Detail.aspx?id=197&printMode=1",
    "dpi": "https://www2.epson.jp/support/manual/data/scanner/es10000g/NPD0596_00.PDF",
    "paper": "https://www.irisohyama.co.jp/products/manual/pdf/101111.pdf",
    "vacuum": "https://www.kaercher.com/jp/professional/vacuums/dry-vacuum-cleaners/electric-broom/lvs-1-1-bp-31374580.html",
    "battery": "https://www.ankerjapan.com/pages/powerhouse-longlife",
    "water": "https://www.mitsubishielectric.co.jp/home/jyoshitsuki/product/comparison/",
    "refresh": "https://www.eizo.co.jp/support/glossary/sa/suichoku_i/",
    "camera": "https://cam.start.canon/ja/C003/manual/html/UG-09_Reference_0100.html",
    "speaker": "https://jp.yamaha.com/products/contents/proaudio/docs/better_sound/part2_03.html",
    "router": "https://www.tp-link.com/jp/support/faq/2866/",
    "ups": "https://store.fa.omron.co.jp/special/ups/",
    "fan": "https://www.orientalmotor.co.jp/ja/products/fan-motors/spec-guide",
    "operating_fan": "https://www.orientalmotor.co.jp/ja/tech/calculation/select-fan01",
}


@dataclass(frozen=True)
class Definition:
    key: str
    name: str
    unit: str
    meaning: str
    reference: str


DEFINITIONS = {
    d.key: d
    for d in (
        Definition(
            "magnification",
            "倍率",
            "倍",
            "顕微鏡の光学系全体を通して対象を観察する際の、像の大きさの比率。",
            "optics",
        ),
        Definition(
            "aperture",
            "開口数",
            "無次元",
            "対物レンズが取り込める光の角度と、対象とレンズの間の媒質の屈折率から決まる値。",
            "aperture",
        ),
        Definition(
            "eyepiece",
            "接眼レンズ倍率",
            "倍",
            "顕微鏡の目を当てる側にあるレンズ単体の拡大の比率。装置全体の拡大率とは異なる。",
            "optics",
        ),
        Definition(
            "scan_resolution",
            "読取解像度",
            "dpi",
            "スキャナーが紙の原稿を画像データにする際の、原稿上の一定の長さに対応する画素の数。",
            "scan",
        ),
        Definition(
            "print_resolution",
            "印刷解像度",
            "dpi",
            "プリンターが紙へ出力する際に、一定の長さの中に配置する印刷の点の数。",
            "dpi",
        ),
        Definition(
            "max_sheets",
            "最大細断枚数",
            "枚",
            "シュレッダーへ一度に重ねて手差しし、裁断できる紙の枚数の上限。",
            "paper",
        ),
        Definition(
            "rated_sheets",
            "定格細断枚数",
            "枚",
            "シュレッダーへ繰り返し連続して投入して裁断するときの、一度の投入に適した紙の枚数。",
            "paper",
        ),
        Definition(
            "vacuum_pressure",
            "吸引圧力",
            "Pa",
            "掃除機が吸い込む側に作る、周囲より低い空気圧の差の大きさ。",
            "vacuum",
        ),
        Definition(
            "vacuum_airflow",
            "吸引風量",
            "L/s",
            "掃除機が単位時間に吸い込む空気の体積。圧力差そのものではない。",
            "vacuum",
        ),
        Definition(
            "consumption_power",
            "消費電力",
            "W",
            "機器を動かすために単位時間あたりに消費する電気エネルギー。",
            "water",
        ),
        Definition(
            "battery_energy",
            "蓄電容量",
            "Wh",
            "ポータブル電源の内蔵電池に蓄えられる電気エネルギーの量。",
            "battery",
        ),
        Definition(
            "output_power",
            "定格出力",
            "W",
            "電源が接続した機器へ継続して供給できる電力の上限。蓄えられるエネルギーの量とは異なる。",
            "battery",
        ),
        Definition(
            "water_removal",
            "除湿能力",
            "L/日",
            "除湿機が指定の試験条件で一日あたりに空気から取り除く水分の体積。",
            "water",
        ),
        Definition(
            "water_tank",
            "排水タンク容量",
            "L",
            "除湿機で回収した水を一度にためておける容器の体積。時間あたりに除去できる水量ではない。",
            "water",
        ),
        Definition(
            "refresh",
            "リフレッシュレート",
            "Hz",
            "モニターの画面全体が一秒間に更新される回数。",
            "refresh",
        ),
        Definition(
            "still_rate",
            "連続撮影速度",
            "コマ/秒",
            "カメラが連写するときに、一秒あたりに撮影できる静止画の枚数。",
            "camera",
        ),
        Definition(
            "video_rate",
            "動画フレームレート",
            "fps",
            "動画を記録するときの、一秒あたりの画像のコマ数。",
            "camera",
        ),
        Definition(
            "burst_count",
            "連続撮影可能枚数",
            "枚",
            "カメラが一回の連写で、バッファ等の制約に達するまでに続けて撮れる静止画の総枚数。",
            "camera",
        ),
        Definition(
            "speaker_impedance",
            "スピーカーインピーダンス",
            "Ω",
            "アンプから見たスピーカーの、交流信号の電流の流れにくさを表す負荷。",
            "speaker",
        ),
        Definition(
            "cable_resistance",
            "ケーブル抵抗",
            "Ω",
            "アンプとスピーカーをつなぐ導線が持つ電気抵抗。スピーカー自体の負荷とは区別する。",
            "speaker",
        ),
        Definition(
            "wireless_rate",
            "無線リンク速度",
            "Mbps",
            "ルーターと無線端末の接続について、無線規格上の物理的な通信レート。実際に転送できたデータの速度ではない。",
            "router",
        ),
        Definition(
            "ethernet_rate",
            "有線ポート速度",
            "Mbps",
            "ルーターのケーブルを挿す端子で使える、有線ネットワーク接続の通信レート。",
            "router",
        ),
        Definition(
            "throughput",
            "実効スループット",
            "Mbps",
            "実際の転送で単位時間に送受信できたデータの量。規格上の理論速度より損失や混雑などの影響を受ける。",
            "router",
        ),
        Definition(
            "ups_apparent",
            "出力容量（皮相電力）",
            "VA",
            "UPSが負荷へ供給できる容量を、交流の電圧と電流の実効値の積で示したもの。",
            "ups",
        ),
        Definition(
            "ups_active",
            "出力容量（有効電力）",
            "W",
            "UPSが負荷へ供給できる容量を、実際に仕事として消費される電力で示したもの。",
            "ups",
        ),
        Definition(
            "fan_free",
            "最大風量",
            "m³/min",
            "冷却ファンの通風経路に圧力損失がなく、静圧がゼロのときに送れる空気の体積の時間あたりの上限。",
            "fan",
        ),
        Definition(
            "fan_operating",
            "動作点風量",
            "m³/min",
            "冷却ファンを機器へ取り付けた状態で、その通風経路の圧力損失とファンの特性が釣り合うときに流れる空気の体積の時間あたりの値。",
            "operating_fan",
        ),
        Definition(
            "fan_pressure",
            "最大静圧",
            "Pa",
            "ファンの空気の流れがなくなったときに生じる、送り出し側と周囲との静的な圧力差の上限。",
            "fan",
        ),
    )
}


@dataclass(frozen=True)
class Case:
    case_id: str
    group: str
    source: str
    target_quote: str
    candidates: tuple[str, ...]
    expected: str | None


# Scope is explicit where a bare quantity would admit multiple specifications.
# These are evaluation inputs, not examples added to the system prompt.
POSITIVE_CASES = (
    Case(
        "microscope",
        "development",
        "顕微鏡。装置全体で対象を40倍以上に拡大して観察したい。",
        "装置全体で対象を40倍以上に拡大して観察したい",
        ("magnification", "aperture", "eyepiece"),
        "magnification",
    ),
    Case(
        "scanner",
        "development",
        "スキャナー。600dpi以上。両面読取対応を希望。",
        "600dpi以上",
        ("print_resolution", "scan_resolution", "max_sheets"),
        "scan_resolution",
    ),
    Case(
        "shredder",
        "development",
        "シュレッダー。手差しで一度に8枚以上の紙を細断したい。自動停止対応。",
        "手差しで一度に8枚以上の紙を細断したい",
        ("rated_sheets", "consumption_power", "max_sheets"),
        "max_sheets",
    ),
    Case(
        "vacuum",
        "development",
        "掃除機。20000Pa以上。水洗い対応を希望。",
        "20000Pa以上",
        ("vacuum_airflow", "vacuum_pressure", "consumption_power"),
        "vacuum_pressure",
    ),
    Case(
        "power_station",
        "development",
        "ポータブル電源。500Wh以上。急速充電対応を希望。",
        "500Wh以上",
        ("battery_energy", "output_power", "consumption_power"),
        "battery_energy",
    ),
    Case(
        "dehumidifier",
        "development",
        "除湿機。12L/日以上。連続排水対応。",
        "12L/日以上",
        ("water_tank", "consumption_power", "water_removal"),
        "water_removal",
    ),
    Case(
        "monitor",
        "new_category",
        "モニター。画面全体を毎秒144回以上書き換えたい。",
        "画面全体を毎秒144回以上書き換えたい",
        ("video_rate", "refresh", "still_rate"),
        "refresh",
    ),
    Case(
        "camera",
        "new_category",
        "カメラ。静止画を1秒に30枚以上続けて撮影したい。",
        "静止画を1秒に30枚以上続けて撮影したい",
        ("video_rate", "burst_count", "still_rate"),
        "still_rate",
    ),
    Case(
        "speaker",
        "new_category",
        "スピーカー。アンプから見た本体の交流の負荷が8Ωのもの。",
        "アンプから見た本体の交流の負荷が8Ω",
        ("speaker_impedance", "cable_resistance", "output_power"),
        "speaker_impedance",
    ),
    Case(
        "router",
        "new_category",
        "Wi-Fiルーター。無線の規格上の通信速度が2402Mbps以上。",
        "無線の規格上の通信速度が2402Mbps以上",
        ("ethernet_rate", "throughput", "wireless_rate"),
        "wireless_rate",
    ),
    Case(
        "ups",
        "new_category",
        "UPS。接続機器へ供給できる容量が800VA以上。",
        "接続機器へ供給できる容量が800VA以上",
        ("ups_active", "ups_apparent", "battery_energy"),
        "ups_apparent",
    ),
    Case(
        "fan",
        "new_category",
        "冷却ファン。通風の抵抗がない状態で、1分間に3m³以上の空気を送れるもの。",
        "通風の抵抗がない状態で、1分間に3m³以上の空気を送れる",
        ("fan_free", "fan_pressure", "fan_operating"),
        "fan_free",
    ),
)


NEGATIVE_CASES = (
    Case(
        "missing_scanner",
        "missing",
        POSITIVE_CASES[1].source,
        POSITIVE_CASES[1].target_quote,
        ("print_resolution", "max_sheets", "refresh"),
        None,
    ),
    Case(
        "missing_vacuum",
        "missing",
        POSITIVE_CASES[3].source,
        POSITIVE_CASES[3].target_quote,
        ("fan_pressure", "vacuum_airflow", "consumption_power"),
        None,
    ),
    Case(
        "missing_power",
        "missing",
        POSITIVE_CASES[4].source,
        POSITIVE_CASES[4].target_quote,
        ("output_power", "consumption_power", "ups_apparent"),
        None,
    ),
    Case(
        "missing_water",
        "missing",
        POSITIVE_CASES[5].source,
        POSITIVE_CASES[5].target_quote,
        ("water_tank", "consumption_power", "fan_free"),
        None,
    ),
    Case(
        "ambiguous_camera",
        "ambiguous",
        "カメラ。1秒に30コマ以上。静止画か動画かは未定。",
        "1秒に30コマ以上",
        ("still_rate", "video_rate", "burst_count"),
        None,
    ),
    Case(
        "ambiguous_router",
        "ambiguous",
        "ルーター。1000Mbps以上。有線か無線か、理論値か実測値かは未定。",
        "1000Mbps以上",
        ("wireless_rate", "ethernet_rate", "throughput"),
        None,
    ),
    Case(
        "ambiguous_optics",
        "ambiguous",
        "顕微鏡。40倍以上。装置全体の値か、接眼レンズ単体の値かは未定。",
        "40倍以上",
        ("magnification", "eyepiece", "aperture"),
        None,
    ),
    Case(
        "ambiguous_fan",
        "ambiguous",
        "冷却ファン。1分間に3m³以上。抵抗のない状態か、機器へ組み込んだ状態かは未定。",
        "1分間に3m³以上",
        ("fan_free", "fan_operating", "fan_pressure"),
        None,
    ),
)
