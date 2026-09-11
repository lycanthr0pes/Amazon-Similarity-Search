# TASK-008: 次期検索フロー v2 バックエンド基盤

## メタデータ

- 状態: 完了（OpenAI商品検索接続案は後続決定で置換済み）
- 作成日: 2026-08-16
- 最終更新: 2026-08-19
- 関連要件: [SEARCH-FLOW.md](../../SEARCH-FLOW.md)、[REQUIREMENTS.md](../../REQUIREMENTS.md)
- 関連タスク: [TASK-008](../../TASKS.md#task-008-次期検索フロー-v2-の実装)
- 関連負債: [TECH-DEBT-TRACKER.md](../../TECH-DEBT-TRACKER.md)

## 目的

2026-08-16時点では、現行バックエンドの観察可能な挙動をcharacterization testで固定した上で、次期検索フローの最初の決定的な境界として、OpenAI Structured Outputsを受けるstrict intentモデル、入力正規化、最大2件の検索query planをTDDで実装することを目的とした。現行のBonsai・Outscraperパイプラインは変更せず、移行前後の契約を同時に検証できる状態にした。

## 後続決定（2026-08-19）

商品検索のLLM経路は、現行 `run_product_search()` が使うBonsaiを正本とする。OpenAI Responses API / Structured Outputsを商品検索へ接続する後続計画は置換済みであり、本Planに残るOpenAIの記述は2026-08-16時点の目的と判断の履歴である。

`src/search_v2/` のstrict model、normalizer、query plannerと対応テストは、外部providerへ接続していない決定的domain基盤として残る。ただし、これらの存在をOpenAIへの移行、または現行検索への接続済み証拠として扱わない。将来この基盤を現行検索へ接続する場合は、Bonsai応答を非信頼JSONとして受けるadapter、既存 `ProductAttributes` / cacheとの互換性、現行characterizationを先に固定する。

この決定は商品検索だけを対象とする。`tools/ai_review/` の独立reviewer / adversaryがOpenAIを使うAIレビューハーネスには適用しない。

## 対象範囲

- 対象:
  - 現行のquery選択、Pydantic互換入力、価格欠損、同点sortのcharacterization test
  - `SearchIntentDraft`、`NormalizedSearchIntent`、価格・曖昧性・provenanceのstrict model
  - Unicode NFKC、空白、空値、重複、明示brand/modelを扱う決定的正規化
  - 日本語1件、英語1件、合計最大2件の決定的query planner
  - 実装、テスト、仕様文書、作業記録の同期
- 対象外:
  - OpenAI、Cloudflare Workers AI、Outscraperの実通信
  - OpenAI Responses API client、承認state machine、画像生成、商品補完、ranking v2
  - 現行 `run_product_search` の切替とUI変更

## 着手時の状態

- `src/main/run.py` はBonsaiで属性を抽出し、`src/services/outscraper_search_select.py` で1件だけqueryを選ぶ。
- `src/schemas.py` の現行modelは入力coercionと未知fieldの無視を許す。
- `src/services/product_scoring.py` は価格欠損を0.0、価格条件なしの既知価格を0.5とし、総合score降順のstable sortを行う。
- [SEARCH-FLOW.md](../../SEARCH-FLOW.md) は次期境界をstrict model、決定的最大2queryとして確定していたが、対応するコードはなかった。

## 実行手順

1. 現行挙動だけを呼ぶcharacterization testを追加し、既存コードを変更せず成功させる。
2. 次期model・normalizer・query plannerの期待テストを先に追加し、対象module不在または契約不一致によるREDを記録する。
3. `src/search_v2/` に外部通信を持たないdomain実装を追加し、対象テストをGREENにする。
4. TASK-008とバックエンド資料を実装済み範囲へ同期し、offline全体gateを実行する。

## 進捗

- [x] 2026-08-16: 現行pipeline、schema、query選択、scoring、既存テストを確認した。
- [x] 2026-08-16: 現行挙動のcharacterization testを6件追加し、既存実装のまま成功した。
- [x] 2026-08-16: 次期backend境界のテストを先に追加し、対象package不在によるREDを記録した。
- [x] 2026-08-16: nested modelの事前構築による検証迂回を追加REDで再現し、全instance再検証で閉じた。
- [x] 2026-08-16: field上限内でもintent全体が過大になる入力を追加REDで再現し、UTF-8 byte上限で閉じた。
- [x] 2026-08-16: preconstructed top-level intentによるprovenance検証迂回を追加REDで再現し、公開関数入口で再検証した。
- [x] 2026-08-16: strict intent、normalizer、query plannerをGREENにした。
- [x] 2026-08-16: 文書同期とoffline全体gateを完了した。

## 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| 現行characterization | `uv run pytest -q tests/test_backend_characterization.py` | 全件成功 | 成功、6 passed |
| TDD RED | `uv run pytest -q tests/test_search_v2_intent.py tests/test_search_v2_query_planner.py` | 実装前に新契約が失敗 | exit 2、`ModuleNotFoundError: No module named 'src.search_v2'`。test SHA-256: intent `f7ccac923d3c241ec3a250fb42b325e2266bef76eb1b707ae894f746f9e0220c`、planner `3e5e66b8cac51be7ae19a75c3db7d4e0eca17221bc3f33fd0befd35738cfbebb` |
| TDD追加RED | 同上 | preconstructed nested modelを拒否する新契約が失敗 | exit 1、2 failed / 14 passed。`model_construct()` 済みambiguityとqueryが再検証されなかった。test SHA-256: intent `344b962138f588e49b1f1356aa570b84de26660ce4bf1448fd6d73e9960fad6f`、planner `55b0f686c6a4a0538bbd8ac5d12ca9993caa274f4da44240c9f97cb0463a43f0` |
| TDD byte上限RED | `uv run pytest -q tests/test_search_v2_intent.py` | field上限内でも過大なintent全体を拒否 | exit 1、1 failed / 9 passed。test SHA-256 `f2643f4f3fd91abd5abb9a0c083070879908e8ae5a87451144f544d708b80c9f` |
| TDD top-level RED | `uv run pytest -q tests/test_search_v2_query_planner.py` | forged top-level intentをquery planner入口で拒否 | exit 1、1 failed / 9 passed。test SHA-256 `96712ad1bc297c800f2360c5edb7449a905bfff112703afa48df5ee686514242` |
| TDD GREEN | `uv run pytest -q tests/test_search_v2_intent.py tests/test_search_v2_query_planner.py` | 全件成功 | 成功、20 passed。最終test SHA-256: intent `f2643f4f3fd91abd5abb9a0c083070879908e8ae5a87451144f544d708b80c9f`、planner `96712ad1bc297c800f2360c5edb7449a905bfff112703afa48df5ee686514242` |
| 対象全体 | `uv run pytest -q tests/test_backend_characterization.py tests/test_search_v2_intent.py tests/test_search_v2_query_planner.py` | 全件成功 | 成功、26 passed |
| offline全体 | `uv run pytest -m 'not live_api'` | 全件成功 | 成功、752 passed / 1 deselected |
| lint | `uv run ruff check .` | 違反0件 | 成功 |
| format | `uv run ruff format --check .` | 差分0件 | 成功、123 files already formatted |
| lock | `uv lock --check` | lock整合 | 成功、72 packages resolved |
| whitespace | `git diff --check` | 違反0件 | 成功 |
| 文書 | project Markdownのlocal link、anchor、fence、AGENTS索引、sh/bash構文 | 違反0件 | 成功、37 files / 78 shell fences |
| Python 3.10構文 | 新規 `src/search_v2/*.py` を `ast.parse(..., feature_version=(3, 10))` | 解析成功 | 成功。Python 3.10実interpreterでは未実行 |

外部API、credential、課金を使う検証はこのPlanでは実行しない。

## セキュリティ・データ・互換性

- 次期modelは `strict=True` と `extra="forbid"` で型coercionと未知fieldを拒否する。
- 自然文、query、各fieldに長さ・文字・件数上限を設ける。
- source/prompt/schema/responseは本文ではなくSHA-256だけをdomain modelへ結び付ける。
- 現行modelとpipelineは変更せず、新packageへ隔離するため既存cacheとCLIの互換性を維持する。
- 外部API clientを含めず、テストはnetworkなしで完結させる。

## 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-08-16 | 現行modelをstrict化せず `src/search_v2/` へ新契約を置く | 現行cacheとBonsai応答を暗黙に破壊せず移行差分を明示するため | 現行pipeline切替時にadapterとcache version更新を別マイルストーンで行う |
| 2026-08-16 | 第1マイルストーンは外部clientを含めない | normalizationとquery planを決定的・無課金で先に検証するため | OpenAI client実装時はrefusal/incompleteとusage ledgerのPlan項目を追加する |
| 2026-08-16 | intent全体を49,152 UTF-8 bytes以下にする | 各field上限だけでは多言語4-byte文字を全配列へ詰めた過大payloadを止められないため | provider schemaや正当fixtureが上限へ近づく場合は計測結果と費用上限を示して見直す |
| 2026-08-19 | 商品検索は現行Bonsai経路を正本とし、OpenAI商品検索client計画を置換する | 現行実装を基準に継続し、商品検索とAIレビューハーネスのOpenAI利用を混同しないため | provider変更は新たな明示決定、互換adapter、TDD、cache移行計画を伴う場合だけ再検討する |

## 発見事項

- 現行query選択は日本語配列の先頭1件だけを採用し、次期仕様の最大2件queryとは別契約である。
- 現行Pydantic modelは数値文字列を整数へcoerceし、未知fieldを無視する。次期strict modelは互換modelではなく新境界として扱う。

## ロールバック

`src/search_v2/`、対応する新規テスト、このPlanとTASK-008の進捗差分だけを取り除けば、現行pipelineへ影響せず元へ戻せる。外部状態とcache schemaは変更しない。

## 結果

最初のbackend縦切りを完了した。legacy挙動6件を固定し、strict intent、provenance、決定的normalizer、最大2件query planとdomain-separated digestを追加した。当時の結果ではOpenAI clientとrefusal/incompleteを後続作業としていたが、この商品検索client計画は2026-08-19の決定で置換した。Bonsai正本の互換境界、決定的tokenizer、承認state machine、Cloudflare、Outscraper複数query、ranking v2の扱いは、現行仕様と [TASK-008](../../TASKS.md#task-008-次期検索フロー-v2-の実装) に従う。
