# テスト方針

## 1. 目的と範囲

この文書は、現行の商品検索と次期検索フロー v2について、何をどの検証で確認し、結果からどこまで言えるかを定義する。

この文書は `AGENTS.md` と [DEVELOPMENT.md](DEVELOPMENT.md) の詳細ガイドであり、競合する場合はそれらを優先する。

- 利用者が行う操作と期待結果: [SEARCH-FLOW.md](../SEARCH-FLOW.md)
- 現行・次期バックエンドの内部契約: [BACKEND.md](BACKEND.md)
- テスト対象の実装状況: [TASK-008](GOAL.md#task-008-次期検索フロー-v2-の実装)
- AIレビューハーネス固有の実行手順: [HARNESS-RUNBOOK.md](HARNESS-RUNBOOK.md)

現行動作はコードと `tests/`、計画中の受入条件は要件、設計、`SEARCH-FLOW.md` を正とする。テストファイルが存在することや過去に成功した件数だけで、現在の実装完了を判断しない。

## 2. 検証区分と主張できる範囲

| 区分 | 確認するもの | 確認できないもの |
|---|---|---|
| 静的確認 | lock整合、lint、format、構文、文書リンク、差分の空白エラー | 実行時の振る舞い、外部サービス接続 |
| fixture・mock・offline test | 決定的な変換、入力拒否、状態遷移、要求descriptor、例外、ローカルUI関数 | 実Bonsai、Cloudflare、Outscraper、ブラウザ、課金 |
| ローカル画面確認 | 起動、画面表示、操作に対するローカル状態変化 | 実サービス結合、別ブラウザ、複数利用者、本番環境 |
| ブラウザE2E | 実ブラウザでの画面遷移、二重送信防止、再読込、focus、履歴操作 | 実サービスをmockした場合のprovider動作や課金 |
| live結合試験 | 承認した1つの実サービス境界と限定した要求 | 他providerを含む全体フロー、本番E2E、継続運用 |
| production E2E | 承認した環境、認証、永続化、全providerを含む利用者フロー | 未実施の負荷、障害復旧、別構成 |

下位の検証成功を上位区分の成功として報告しない。特に `nonlive_ready`、credential-free request生成、fixture画像、mock応答はlive成功ではない。

## 3. 標準の外部通信なしゲート

依存関係を事前に準備した環境で、次を実行する。

```sh
uv lock --check --offline
uv run --frozen --offline --no-sync ruff check .
uv run --frozen --offline --no-sync ruff format --check .
uv run --frozen --offline --no-sync pytest -m 'not live_api'
git diff --check
```

`uv sync` は依存取得の通信を行う可能性があるため、通常の検証とは別の環境準備として扱う。固定のテスト件数を合格条件にせず、コマンドの終了状態と失敗内容を確認する。

`tests/conftest.py` は通常pytestでPythonのsocket・主要DNS経路を遮断する。これは補助防御であり、subprocess、native code、OS全体のネットワーク隔離を証明しない。

`live_api` markerと `--run-live-api` は誤実行を防ぐ技術的な二重opt-inである。これらを指定しても、credential利用、外部送信、課金に対する人間の承認にはならない。

## 4. 自動テストの対象

### 4.1 現行検索の回帰

現行の `run_product_search()` とStreamlit・CLIは、主に次のテストで確認する。

| 対象 | 主なテスト |
|---|---|
| Bonsai要求・応答・属性抽出 | `tests/test_bonsai_client.py`、`tests/test_user_attribute_extraction.py` |
| Outscraper要求・状態・再試行・URL検証 | `tests/test_outscraper_client.py`、`tests/test_outscraper_search_select.py` |
| 商品正規化と採点 | `tests/test_amazon_product_normalization.py`、`tests/test_product_scoring.py`、`tests/test_src_product_scoring.py` |
| キャッシュと全体パイプライン | `tests/test_cache_repository.py`、`tests/test_run_pipeline.py` |
| StreamlitとCLI | `tests/test_streamlit_ui.py`、`tests/test_cli.py` |
| 既存互換境界 | `tests/test_backend_characterization.py` |

これらは外部応答をmockまたはfixtureで置き換える。成功しても、実Bonsaiの意味品質、Outscraper認証、Amazonの商品取得、利用料金、ブラウザ操作を確認したことにはならない。

### 4.2 次期検索フロー v2 のoffline境界

`src/search_v2/` の独立した境界は、対応する `tests/test_search_v2_*.py` で確認する。

| 対象 | 確認事項 |
|---|---|
| strict intent | 全field必須、unknown field拒否、型coercion拒否、価格整合、入力上限、provenance |
| Bonsai response adapter | OpenAI互換envelope、content全体の単一JSON、duplicate key、非有限数、raw content非露出 |
| tokenizer・query plan | NFKC、日英token、URL・改行・制御文字拒否、最大2query、200文字上限、決定的digest |
| 承認plan・state machine | 2段階確認、計画変更時の失効、15分期限、owner・session、single-use、並行二重消費拒否 |
| 利用量ledger | 送信前予約、未開始予約だけの解放、失敗attempt計上、user・session・day上限、snapshot再検証 |
| Cloudflare request descriptor | 固定4方向、共有する基準画像、attempt、seed、prompt、PNG上限、credential非保持 |
| Outscraper request descriptor | 1要求の最大2query、許可parameter、最大候補数、request digest、明示承認guard、token非保持 |

これらはnetwork非依存のdomain testである。providerへ送信するHTTP、実画像、Amazon候補、次期画面、永続化、検索履歴まで接続したことは示さない。

### 4.3 後続実装で必要な自動テスト

次の項目は、対応機能を実装する変更で追加し、実装前の受入条件として扱う。

- Outscraper候補の決定的正規化、未知属性の維持、Outscraper後にLLMを呼ばないこと
- 日本語・英語TF-IDF、価格式、pHash重複検出、固定CLIP fixture embedding
- 欠損componentのweight再正規化、negative penalty、stable sort、score breakdown
- 画像proxyのHTTPS、許可host、redirect、DNS/IP、byte、dimension、timeout、decompression bomb境界
- 完了1件につき履歴1件、0件結果の保存、重複完了通知の冪等性
- 履歴の空状態、読込失敗、詳細not found、削除失敗、owner不一致
- 履歴一覧、詳細、再読込、削除、期限削除から外部処理を呼ばないこと
- 通常画面と履歴の表示モデルに、郵便番号、お届け先、内部metadata、料金情報を含めないこと
- 完了から30日未満の保持と、期限到達後の履歴・結果・専有生成画像の物理削除

## 5. 次期画面の受入確認

この節は [SEARCH-FLOW.md](../SEARCH-FLOW.md) の利用者向け動作を確認するためのチェックリストである。次期UIへ接続するまでは、ブラウザE2E成功として扱わない。

### 5.1 条件整理と参考画像

- [ ] 参考画像の初期状態がOFFである。
- [ ] `条件を整理する` 前に条件整理処理が始まらない。
- [ ] 2,000文字超過時に次へ進めず、問題の入力欄へ移動できる。
- [ ] 条件または価格の変更後は、`変更を反映` まで次へ進めない。
- [ ] `参考画像を作る` 前に画像作成が始まらない。
- [ ] 初回作成前は `参考画像を使う（残り2回）` と表示し、4枚1組を1回として扱う。
- [ ] 4枚のうち1枚でも失敗すると採用できない。
- [ ] 作り直すと4枚すべてが置き換わる。
- [ ] 初回作成後は `残り1回`、作り直し後は `残り0回` と表示する。
- [ ] 作り直しをキャンセルした場合は、画像と残り回数が変わらない。
- [ ] 外部要求を1件も開始できなかった場合は画像の残り回数を減らさない。
- [ ] 1件目の外部要求開始後に一部または全部が失敗した場合は、画像1組を1回として扱う。

### 5.2 最終確認と待機

- [ ] Step 3を表示しただけでは商品検索が始まらない。
- [ ] `この条件で商品を探す` 以外の操作では商品検索が始まらない。
- [ ] 検索ボタンを二重に操作しても、検索要求は1件だけである。
- [ ] 条件変更または期限切れ後は古い確認を利用できない。
- [ ] 追加確認が不要な場合は、外部処理を増やさない。
- [ ] Step 4の再読込で完了済み工程を再実行しない。
- [ ] 確定前の件数、進捗率、残り時間を表示しない。
- [ ] 現在の工程だけを `処理中` とし、完了済み工程を失敗へ戻さない。
- [ ] 外部処理を再実行する再試行だけ、範囲と回数の確認を表示する。

### 5.3 結果と履歴

- [ ] 結果を `条件に近い順` に表示する。
- [ ] 表示件数の変更だけでは商品検索や比較を再実行しない。
- [ ] 結果の再読込が商品検索や比較を再実行しない。
- [ ] 完了した検索を履歴へ1件だけ保存し、0件の正常完了も保存する。
- [ ] 履歴を開く、再読込する、表示件数を変える操作で外部処理を再実行しない。
- [ ] 保存済み結果から `新しい検索` を押しても、不要な確認を表示しない。
- [ ] 履歴削除をキャンセルすると何も削除しない。
- [ ] 履歴削除に失敗した場合も対象を一覧に残す。
- [ ] 履歴カードに30日の保存期限を表示し、期限後は一覧と詳細へ返さない。
- [ ] 期限切れ履歴を外部処理で再構築しない。

### 5.4 表示と操作性

- [ ] credential、外部response本文、stack traceを通常画面へ表示しない。
- [ ] 外部APIの単価、見積額、合計額、金額上限を通常画面へ表示または入力させない。
- [ ] 内部ID、サービス名、model名、hash、内部評価方式、内部weightを通常画面へ表示しない。
- [ ] 郵便番号、お届け先、内部metadataを現在結果と履歴のどちらにも表示しない。
- [ ] 現在Stepを紫、完了Stepを緑、未到達Stepを灰色で示し、文字でも状態を判別できる。
- [ ] 処理中の主要ボタンは状態を示す文言へ変わり、重ねて押せない。
- [ ] 条件変更後は後続Stepを未完了へ戻し、古い承認操作を無効にする。
- [ ] エラー時に最初の問題箇所へ移動できる。
- [ ] Step 4の更新でスクロール位置を不必要に先頭へ戻さない。
- [ ] 拡大表示または確認ダイアログを閉じると、開いた元の操作へ戻れる。
- [ ] `Esc`、閉じる、キャンセルでは処理を実行しない。

## 6. live結合試験

### 6.1 共通の承認条件

実サービスを利用する前に、その実行ごとに次を利用者へ示し、明示的な承認を得る。

- 接続先と実行する操作
- 外部へ送る内容。実利用者の検索入力は使わず、合成した最小入力を使う
- 件数、attempt、timeout、polling等の上限
- 利用するcredentialの種類。値そのものは表示しない
- 想定費用と上限。実行直前に公式料金を再確認する
- 保存する結果とログの範囲

承認前の接続確認、疎通目的の有料要求、事前通信、CIからのlive実行を行わない。失敗後に再試行する場合も、原因、送信範囲、追加費用を示して新しい承認を得る。

### 6.2 Bonsai

最初の結合試験は、合成した自然文1件の意図抽出1回だけとする。model、prompt digest、max tokens、timeout、保存するmetadataを事前に示す。

商品fixtureをBonsaiへ送り、Outscraper後の商品属性を補完する試験は設けない。Bonsaiの結合成功をCloudflare、Outscraper、全体フローの成功として扱わない。

### 6.3 Cloudflare Workers AI

最初の実画像試験は、基準画像1枚だけに限定する。promptの要約、model、寸法、seed、credential種別、timeout、見積費用を示して承認を得る。

4方向1組、4枚一括の作り直し、負荷試験はそれぞれ別の承認対象とする。1枚の成功を4方向set、再生成、画像比較の成功として扱わない。

### 6.4 Outscraper

実行前に、送信query、domain、language、postal code、1 query当たりのlimit、最大候補数、timeout、polling上限、見積費用を示して承認を得る。表示または記録には合成queryを使い、credential値と生responseを含めない。

承認前の事前通信、疎通目的の有料検索、CIからの実行を行わない。task作成の成功だけで、polling、商品取得、正規化、ランキングまで成功したとは扱わない。

## 7. 結果の記録

検証結果には、少なくとも次を記録する。

- 実行したコマンドまたは操作
- 成功、失敗、未実行
- 失敗理由または未実行理由
- 確認できた境界と、確認できなかった境界
- liveの場合は承認した接続先、要求回数、上限、費用結果。credential値は含めない

次を文書、artifact、review packet、issue、回答へ保存しない。

- API key、token、password、secret、Authorization header
- 実利用者の検索入力
- 実サービスの生response
- 生cache、生成済みの承認token
- credentialを含むURI、環境変数の実値

報告例:

```text
offline pytest: 成功。mockとfixtureで対象境界を確認した。
実Bonsai・Cloudflare・Outscraper: 未実行。credential・外部送信・課金は確認していない。
ブラウザE2E: 未実行。次期UIは未接続である。
```

## 8. 変更時の確認範囲

| 変更 | 最低限確認するもの |
|---|---|
| domain model、正規化、ranking | focused test、関連回帰、offline全体 |
| 外部API request・response | strict adapter、mock、secret非露出、別承認の最小live試験 |
| 承認、利用量、履歴 | 改ざん、期限、owner、single-use、並行処理、永続化失敗 |
| UI入力・表示・状態 | component test、ブラウザE2E、accessibility、二重操作、再読込 |
| 文書だけ | ローカルリンク、見出しanchor、fence、`git diff --check` |

AIレビューハーネスのCLI、期待結果、停止・再実行規則を変更する場合は、この文書へ手順を複製せず [HARNESS-RUNBOOK.md](HARNESS-RUNBOOK.md) を同じ変更で更新する。
