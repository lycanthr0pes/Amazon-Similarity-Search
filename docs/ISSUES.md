# 問題一覧

2026-09-13: 目視で見つかった履歴案内の重複/余白不足、比較画像の位置ずれ、採点表見出しの改行を [EXEC-158](GOAL.md#exec-158-モック共用画面の目視確認と表示修正) で修正した。Chromiumの幅1440/1280pxで再確認済み。

2026-09-13: オフラインモックと接続画面の条件編集・回復操作・結果表示の差分を [EXEC-157](GOAL.md#exec-157-オフラインモックを現行接続画面へ統一) で共用化。検証結果と境界は同Planへ記録する。

2026-09-12: 条件の同義語/英訳と英語本文がcandidate採点へ未接続だった点を [EXEC-133](GOAL.md#exec-133-条件展開と日英別採点の最大値採用) で実装した。日英の高い一致点を使うため、言語間で記載が矛盾しても採点は高い方となる。観測による仕様確認状態は別に保持する。翻訳・未知商品の順位品質全般を保証する変更ではない。

2026-09-12: 説明文の条件一致と同義語の採点漏れ、タイトル専用fieldの未設定を [EXEC-125](GOAL.md#exec-125-説明文の条件一致とタイトル比較の拡張) で修正した。全体offline3109件成功。検証の正本は同Planとし、未知商品の順位品質はoffline回帰から保証しない。

## 1. 役割

この文書は、現行実装で再現またはコード上確認できる不具合、利用者影響のある仕様不一致、障害を管理する。推測だけの問題は断定せず、「要確認」として再現条件を記載する。

関連文書との区別:

- 修正作業が小さい場合は [GOAL.mdの小規模タスク一覧](GOAL.md#統合済み小規模タスク一覧) に作業項目を作る
- 複数段階の修正は [GOAL.mdの大規模タスク一覧](GOAL.md#統合済み大規模タスク一覧) と同文書の個別Planで扱う
- 正常に動作しているが将来の保守・運用に不利な構造は [技術的負債トラッカー](#統合済み技術的負債トラッカー) で扱う
- 実装されていない将来機能は、不具合として要求済みでない限りIssueにしない

状態は `オープン`、`要確認`、`対応中`、`解決済み`、`再現せず` を使う。テストまたは観察可能な結果を確認する前に `解決済み` としない。

### 作業台帳の統合入口

`agents-setup` の標準文書では、この文書を問題と作業管理の入口とする。詳細なID、証拠、履歴は既存台帳に保持し、ここへ重複転記しない。

| 確認する内容 | 台帳 |
|---|---|
| 現在の到達点、進行中の計画、非目標 | [GOAL.md](GOAL.md) |
| 再現済みの不具合、仕様不一致、障害 | この文書 |
| 複数工程を持つ成果単位 | [GOAL.mdの大規模タスク一覧](GOAL.md#統合済み大規模タスク一覧) |
| 単独で完了できる小規模作業 | [GOAL.mdの小規模タスク一覧](GOAL.md#統合済み小規模タスク一覧) |
| 正常動作しているが改善が必要な構造 | [技術的負債トラッカー](#統合済み技術的負債トラッカー) |
| 実行中または履歴として保持する詳細計画 | [GOAL.md](GOAL.md#54-execution-plan-inventory) と [Execution Plan規約](DEVELOPMENT.md#統合済みexecution-plan規約) |

同じ事象を複数台帳で管理する場合は、各IDを相互リンクし、状態の正本を1つに定める。未実装、未検証、live未実行は、それ自体が観測済み不具合でない限りIssueへ変換しない。

次期フロントエンドのオフライン画面、ブラウザ受入確認、実APIへの未接続範囲は [EXEC-117](GOAL.md#exec-117-react-stylexのオフライン画面) で管理する。タブ内モック履歴と本番の永続履歴、日本語/英語検索語編集の未実装を区別し、固定合成データの操作成功を実商品検索の解決記録へ転記しない。

## 2. オープン

2026-09-10の候補検索の語義・商品句品質は [EXEC-103](GOAL.md#exec-103継続-商品句候補を条件検査より先に解決する) で対応中。商品名候補の生成は改善したが、用途/収納/取り付けの未解釈条件で検索準備が停止する状態と、未知名・英訳の品質未達を継続管理する。未収録名の追加検証では補完0/4・名称明記時の英訳0/4、辞書語義の誤選択2件を確認した。 その後、辞書候補0件だけをBonsai直接推論へ変更した。既知6例で経路は動作し英訳の概念充足3/6、名称は原語の反復であり、一般名からの補完問題と英訳誤りは残る。

2026-08-16時点で、現行作業ツリーにオープンとして記録する確認済みIssueはない。これは不具合が存在しないことを保証するものではない。AIハーネスの7/7 code境界、`workflow-init`、専用userとrootless Podman、root-owned release、4 image、承認済みTaskSpec v2 canary、credential-free `nonlive_ready`、launcher userが読めるlive用initial requestは実hostで確認済みである。OpenAI APIを使うlive E2Eとnonce ledger長期運用が未実行・未定義であることは不具合ではなく、[TASK-007](GOAL.md#task-007-attested-ai-review境界の実装) と [TD-009](#td-009-ai変更の役割分離と証拠契約) の運用境界として追跡する。

### ISS-002: 4方向指定の生成画像がほぼ同じ向きになる

- 状態: 解決済み（製品要件の撤回による。視点生成品質の改善ではない）
- 重要度: 中
- 確認日: 2026-09-08
- 対象: 先行参考画像を共通入力としたCloudflare 4方向生成
- 関連Plan: [EXEC-078](GOAL.md#exec-078-自然言語から画像確認ランキング履歴までのbackend-live-e2e)
- 再現: 承認済みの固定合成「白い陶器製マグカップ」で、先行1枚の了承後に正面斜め・左側面・右側面・背面斜めの4要求を1回ずつ実行した。
- 観測: 4枚とも取っ手が右に見えるほぼ同じ構図で、方向の分離を目視確認できなかった。4 PNGの生成・保存成功を4方向の表現成功とは扱わない。比較用偽画像は青いマグカップで、色の反転は確認した。
- 原因: 未確定。promptの指示、参照画像の影響、modelの追従性のどこに起因するかは、この1試行だけでは断定しない。
- 影響: 4面を見比べる目標仕様を今回の生成物は満たしていない。暫定rankingは先行desiredと偽画像を使う既存方式であり、4面の品質とは検証を分ける。
- 解決条件: 既存生成物・要求契約のoffline分析後、必要な修正と回帰確認を行い、別承認の限定liveで方向の違いを確認する。現在のE2E内で自動再生成しない。

2026-09-08: 利用者から再生成指示。 [EXEC-079](GOAL.md#exec-079-4方向画像の視点指示修正と限定再生成) でcamera移動と遮蔽の指示を修正し、同じ参考画像から追加4枚だけを生成する診断を準備する。元E2Eの23商品ranking・履歴再読込は成功したが、視点品質の改善は追加liveで確認するまで未解決。

2026-09-08 16:07 JST: 別承認の追加4 callsが成功し、保存・digestを確認した。左側面指定だけ取っ手が見えず、正面斜め・右側面・背面斜めは取っ手が右にあるほぼ同じ向きだった。具体的camera移動の指示だけでは4方向品質を達成できなかった。取っ手が見えない理由も正しい遮蔽か特徴消失か未確定で、ISS-002はオープンのまま。承認された4 callsを使い切り、追加の自動試行は行わない。

追加調査: E2E検索は利用者指示で停止中。offlineの実multipart検査で4 prompt・4 seed・同一参考PNGを確認し、要求の取り違えは再現しなかった。初回4枚のpHash距離は全組2、再生成後の同じ向きの3枚は2〜4で既存重複閾値5以下だった。取っ手の最終位置・遮蔽を指定するマグカップ限定 `landmark-v1` を診断に追加した。類似度だけでは視点・特徴の正しさを判定できず、実画像の事前固定基準による検証が残る。追加liveは未実行で、本番の汎用問題は未解決。

2026-09-08 16:16 JST: landmark-v1はCloudflare 4 calls・retry 0でexit 0となり、4 PNGの512×512 RGB・0600・digestと診断契約一致を確認した。pHash距離は正面/左12、正面/右6、正面/背面24、左/右12、左/背面20、右/背面24で、閾値5以下の組はなかった。しかし目視では正面斜めと右側面がともに取っ手を右に広く見せる像で、右側面の中央edge-onという事前基準を満たさない。背面の取っ手は左へ移動したが、左奥に一部隠れる指定も満たしていない。近似検出を通過しても4方向品質は不合格であり、ISS-002は未解決。本番への採用とE2E検索の再開は行わない。

2026-09-08 16:22 JST: 9Bによる同一landmark-v1右側面の1-call比較では、取っ手が手前中央に細く見える形となり、4Bで失敗していた視点が改善した。元の白い円筒形と縁・比率も目視で維持されている。4面全体・汎用promptは未検証のためISS-002は未解決。本番camera-v2の4要求をそのまま9Bへ送るgeneric-four診断を準備し、追加条件への承認待ちである。

2026-09-08 16:27 JST: 9Bの汎用camera-v2でも4枚の構図差は出たが、左右90度に必要な取っ手の遮蔽・中央edge-onを満たさず不合格。sourceには参照cameraからの相対角度と未定義の絶対面名が混在し、仕様の正面・左右・背面に対して四等分になっていなかった。次はcamera固定・objectの参照姿勢を0度とした0/90/270/180度の回転だけを指定する診断で検証する。唯一の失敗原因の確定ではなく、観測された契約不整合の修正である。

2026-09-08 16:37 JST: turntable-fourは9B 4 calls・retry 0でexit 0となった。実model、事前契約SHA-256 b7d0cb360b9993ff3ec621d44035a6c35785e63d8b71736ffb8a7a4fb5ff7aa3、全4 PNGの512×512 RGB・digest・0600、directory 0700を検証した。目視では0度でも取っ手が手前側へ回り、反時計回り90度はカップが倒れて複数の取っ手に見える形になり、時計回り90度も上面向きと複数の突起を生じ、180度では開口部が下へ向いた。camera固定・垂直軸回転・取っ手1個・形状維持の基準に不合格。指示の混在を除いても今回のmodelは追従せず、契約不整合が唯一の原因ではない。承認済み4 callsは完了し、追加prompt試行とE2E検索は停止する。実請求は取得せず、事前見積りは0.068 USD。

2026-09-08: 利用者の明示指示で [EXEC-080](GOAL.md#exec-080-4方向生成を製品フローから除去) により4方向生成を公開フローから除去した。生成モデルの問題を解決したとは扱わず、上記の失敗実績と低位診断を保持する。追加診断・ローカル3D・視点変換API調査を終了し、E2E実検索の停止を維持する。

## 3. 解決済みの履歴

### ISS-001: デバッグ表示に2つの条件語重みがない

- 状態: 解決済み
- 重要度: 低
- 確認日: 2026-08-15
- 解決日: 2026-08-15
- 対象: `src/ui/streamlit_ui.py` の `render_status_panel()`
- 前提: `SHOW_DEBUG_INFO=true`
- 原因: 採点に使う `color_term_weight` と `feature_term_weight` がデバッグJSONの構築対象に含まれていなかった
- 解決: 2項目を追加し、総合係数3項目と条件語重み5項目を表示対象にした
- 回帰証拠: `tests/test_streamlit_ui.py` は修正前1 failed, 2 passed、修正後3 passed。テストSHA-256は `042ad1b2cd8307afe40787bd53510d4cb55f66914548adf9ed76b57b8306ac4c`
- 対応作業: [TODO-002](GOAL.md#todo-002-デバッグ表示へ全条件語重みを表示する)

APIキーの値は表示対象にしていない。検索結果表示件数スライダーにも変更はなく、ブックマーク表示数プルダウンは追加していない。

次はコミット `fb2115a`（2026-08-14）後のコードと回帰テストで解決状態を確認できる。

| ID | 解決内容 | 根拠 |
|---|---|---|
| ISS-HIST-001 | Outscraper結果URLをHTTPSかつendpointと同一ホスト・ポートへ限定し、APIキー付きリダイレクトを拒否した | `validate_results_location()` と `tests/test_outscraper_client.py` |
| ISS-HIST-002 | Outscraperの正常0件、失敗、不明状態、待機超過を区別した | `task_state()`、専用例外、状態テスト |
| ISS-HIST-003 | 装飾されたJPY・USD価格と文字列Prime値を正規化した | `amazon_product_normalization.py` と正規化テスト |
| ISS-HIST-004 | Bonsaiの不正なレスポンス構造を検証し、生応答を属性変換エラーへ露出しないようにした | `bonsai_client.py`、`user_attribute_extraction.py` と関連テスト |
| ISS-HIST-005 | キャッシュキーへ入力・設定・scopeを含め、Streamlitセッション間の再利用を分離した | `src/main/run.py`、`streamlit_ui.py`、パイプラインテスト |

履歴は現在の回帰理由を残すためのものであり、旧コードで同じ問題が再現することを意味しない。

## 4. 検証範囲

現行テストは外部HTTP通信をモックし、属性抽出、Outscraper状態・再試行・URL検証、正規化、採点、キャッシュ、CLI補助処理、検索パイプラインを確認する。

次は自動テストだけでは確認済みにならない。

- 実際のBonsaiモデルによる抽出品質
- 実Outscraper契約・課金環境での結合動作
- Streamlitをブラウザ操作した一連のUI動作
- 複数プロセスから同じキャッシュへ書く競合
- root-owned releaseをrootless Podman `keep-id` hostへ配備したAIハーネスのlive 7-phase E2E
- 外部OpenAI APIのcredential・送信内容・費用承認を伴うlive実行

これらが未確認であること自体を不具合とは断定しない。障害が観測された場合は、入力やシークレットを伏せた再現情報とともに新しいIDを作る。

## 5. Issueテンプレート

```markdown
### ISS-NNN: 題名

- 状態: オープン
- 重要度: 高 / 中 / 低
- 確認日: YYYY-MM-DD
- 対象: リポジトリ相対パスまたは機能
- 関連要件:

#### 再現手順

1. シークレットと利用者データを含めずに記載する。

#### 期待する状態

#### 実際の状態

#### 影響

#### 証拠

テスト、最小ログ、スクリーンショット等。APIキーと生キャッシュは添付しない。

#### 解決条件

修正と回帰テストを記載する。
```


## 統合済み技術的負債トラッカー

> 統合元: `docs/TECH-DEBT-TRACKER.md`。統合前の文書は `bin/docs/old/` に保存する。


> **標準文書との関係:** 問題と作業台帳の入口は [ISSUES.md](ISSUES.md)、到達点と優先境界は [GOAL.md](GOAL.md) とする。この文書は正常動作しているが改善を要する構造上の負債をID付きで保持する。

### 1. 役割

この文書は、現行構造に意図的または歴史的に残っている横断的な改善課題を追跡する。記載内容は2026-08-16時点のコードとテストで確認した。

他の管理文書との区別:

- [ISSUES.md](ISSUES.md): 再現可能な不具合、障害、仕様との不一致
- [小規模タスク一覧](GOAL.md#統合済み小規模タスク一覧): 1回の小さな変更で完了できる作業
- [大規模タスク一覧](GOAL.md#統合済み大規模タスク一覧): 複数段階に分かれる大規模な成果単位
- 本文書: 放置すると保守性、信頼性、運用性、安全性を下げる構造上の負債

負債の解消には複数の変更が必要な場合がある。その場合は [GOAL.md](GOAL.md#統合済み大規模タスク一覧) に成果単位を作り、実行開始時に [Execution Plan規約](DEVELOPMENT.md#統合済みexecution-plan規約) に従って同文書へPlanを追記する。

### 2. 状態と優先度

状態は `未着手`、`対応中`、`ブロック`、`解消`、`受容` を使う。実装、検証、文書更新まで確認できる前に `解消` としない。`受容` には、受容理由と再検討条件が必要である。

| 優先度 | 意味 |
|---|---|
| P0 | シークレット漏えい、データ破壊等につながり、通常利用を止めて対処すべきもの |
| P1 | 多利用者運用または本番公開前に解消・受容判断が必要なもの |
| P2 | ローカル利用は継続できるが、信頼性や保守性を上げるために扱うもの |

現時点でP0として確認済みの項目はない。これは脆弱性が存在しないことを保証するものではない。

### 3. 一覧

| ID | 優先度 | 状態 | 概要 |
|---|---|---|---|
| TD-001 | P1 | 対応中 | 次期production callbackとlocal ASGI API factoryはoffline接続済みだが、server起動構成・最終承認controller・現行または次期UIは未接続でlegacy検索は同期実行のままである |
| TD-002 | P1 | 未着手 | ファイルキャッシュに競合・容量・全体保持期限の管理がない |
| TD-003 | P1 | 未着手 | 認証、認可、利用量制限、利用者別永続分離がない |
| TD-004 | P1 | 未着手 | 構造化ログ、相関ID、メトリクス、監査経路がない |
| TD-005 | P2 | 未着手 | Bonsai要求に上限付き再試行がない |
| TD-006 | P2 | 対応中 | 決定論的CIは追加中だが配布方式が定義されていない |
| TD-007 | P2 | 未着手 | 内部モデルの一部制約が正規化サービスに依存する |
| TD-008 | P1 | 対応中 | EXEC-065の未知条件1 caseはAUC 1.0、accuracy 0.875で絶対基準未達だった。利用者判断で既知制約を固定した暫定production profileだけ画像rankingを有効化したが、最終品質合格ではない |
| TD-009 | P2 | 対応中 | credential-free配備前提は実host確認済みだが、live E2Eとnonce長期運用が未完である |
| TD-010 | P1 | 解消 | Cloudflare画像生成の途中失敗後に再試行または画像なし続行へ進めない |
| TD-011 | P1 | 対応中 | Outscraper由来24商品画像のproxy・固定CLIP・ranking v5は限定live成功したが、未知条件・複数query・4方向参照の順位品質、Windows native、永続承認state・履歴が未確認である。最初の未知条件1 caseはaccuracy 0.875だった |

### 4. 詳細

#### TD-001: 同期的な検索実行

- 状態: 対応中
- 根拠: CLIが `run_product_search()` を直接呼び、`src/clients/outscraper_client.py` がポーリング間隔ごとに `time.sleep()` する
- 実装済みの緩和: `src/search_v2/search_job.py` に固定local owner、SQLite状態、同時実行1件、同一bindingの重複防止、状態照会、queued取消、running協調取消、24時間の開始期限、再起動時の安全な終端、終了後30日の明示purgeを持つbackend境界を追加した。`production_search.py` は最終承認済み検索をOutscraper、商品画像、固定CLIP、ranking v5、履歴locatorへ接続する。`production_api.py` はjob投入・状態取得・取消・schema 5.0履歴詳細取得をlocal ASGI APIへ投影する
- 現在の影響: CLIは検索完了または待機上限まで同じprocessで待つ。次期production callbackとAPI factoryはoffline確認済みだが、server起動構成、最終承認controller、現行検索、UIへは接続していない
- ローカル利用上の扱い: CLIでは同期完了を待ち、Reactモックは固定の処理中表示を使う。job部品を接続済みの利用者機能として案内しない
- 解消条件: 自前開発する次期フロントエンドに向けて最終承認controllerとserver起動構成を追加し、結果locator、状態表示・取消操作をUIへ接続して一連の状態遷移を検証できる
- 関連大規模タスク: [TASK-001](GOAL.md#task-001-検索処理のジョブ化)

#### TD-002: ファイルキャッシュのライフサイクルと競合

- 状態: 未着手
- 根拠: `JsonCacheRepository` はアトミック置換を行うが、プロセス間ロック、容量上限、削除処理を持たない。正規化・採点キャッシュは読込TTLを持たない
- 現在の影響: 長期利用でファイルが増え続け得る。同じキーへの複数プロセス書込を調停せず、認証利用者単位の保存領域もない
- 実装済みの緩和: namespaceとキー検証、アトミック書込、属性と生レスポンスのTTL、破損時の再計算、呼出元指定のcache scope
- 解消条件: 保存方式を決定し、容量・保持期限・削除・競合・利用者分離の方針を実装して負荷・競合テストを通す
- 関連大規模タスク: [TASK-002](GOAL.md#task-002-キャッシュ基盤の運用対応)

#### TD-003: アクセス制御と利用量制御

- 状態: 未着手
- 根拠: 現行CLIとローカルAPI境界 にアプリ独自の認証、認可、監査がない。キャッシュscopeは認証主体ではない。本番quotaを設けないことは現行local productionの明示方針であり、公開時の濫用対策を代替しない
- 現在の影響: アクセス制御なしで公開すると、第三者がOutscraper利用とローカル計算を発生させ得る。利用者別の保存・削除要求にも対応できない
- 実装済みの緩和: 次期v2の同一process ledgerはquota有効policyではowner・session・dayごとの上限を送信前に強制できる。現行production policyはquotaを明示的に無効化し、Bonsai・Cloudflare・Outscraperの開始済みattemptと費用を拒否判定なしで記録する。どちらも明示承認、single-use token、操作単位の固定call数、自動retryなしを維持する。暫定counterfactual分岐は専用SQLiteでraw tokenを保存せず15分のreference approvalを永続化し、再起動後も最初のconsumeだけを原子的に許可する。完了resultは表示用履歴へ変換でき、旧version 2と暫定version 5の別SQLite repositoryは全操作でownerを必須にし、owner不一致を不在と同じ固定失敗にし、owner内の冪等保存と30日期限削除を行う。ただしownerを認証済み主体から解決せず、同じOS userのfileを共有する。利用量ledgerの永続化、複数worker全体の原子性、認証・認可、API接続は未実装である
- 解消条件: 公開へ変更する場合は想定利用者と公開範囲を要件化し、認証、認可、濫用対策、永続データ分離、監査を一体で検証する。quotaを追加する場合は現行の無quota方針を別Planで変更する
- 関連大規模タスク: [TASK-003](GOAL.md#task-003-多利用者向けセキュリティ境界の構築)

#### TD-004: 観測可能性とログ管理

- 状態: 未着手
- 根拠: パイプラインは主に `print()` を使い、UI例外だけが `LOGGER.exception()` を使う。loggingの全体設定、環境切替、構造化メトリクス、トレースはない
- 現在の影響: 1検索の段階を横断する相関ID、レイテンシ、再試行、キャッシュヒット率、外部API失敗率を一貫して集計できない
- 実装済みの緩和: 実行処理へ接続されていなかった `APP_ENV` と `LOG_LEVEL` のplaceholderは設定契約から削除し、設定できるとの誤解を避けた。旧環境値は無視される
- セキュリティ上の注意: 現行legacy Outscraper失敗例外は外部レスポンス由来の説明を含み得るため、外部転送前にマスキング方針が必要である。未接続のv2 HTTP境界は生provider文を固定例外へ含めない
- 解消条件: ログ項目と禁止項目、相関ID、メトリクス、保持期間、アラートを定義し、値がシークレットや利用者入力を漏らさないテストを持つ
- 関連大規模タスク: [TASK-004](GOAL.md#task-004-観測可能性と配布パイプラインの整備)

#### TD-005: Bonsai通信の回復性

- 状態: 未着手
- 根拠: `call_bonsai()` は60秒のタイムアウトと専用例外を持つが、通信失敗または一時的HTTP失敗を再試行しない
- 現在の影響: 一時的なローカルサーバー障害でも検索全体が失敗する
- 実装済みの緩和: 次期v2 execution境界は1予約をexact 1 callへ固定し、transportまたは応答失敗も同一process ledgerの失敗attemptとして確定する。Requests HTTP transportもHTTP/HTTPS adapterのretryを0にして隠れた追加attemptを防ぎ、redirectを追わない。自動再試行、実Bonsai結合、現行pipeline接続は未実装である
- 制約: 生成要求の再送は計算時間を増やし、応答の再現性にも影響し得る。v2で再送する場合もattemptごとの新予約が必要である
- 解消条件: 再試行対象、最大回数、バックオフ、重複要求の扱いを決め、通信モックによる回帰テストを追加する

#### TD-006: CIと配布方式

- 状態: 対応中
- 根拠: 現行作業ツリーの `.github/workflows/ci.yml` はPython 3.10 / 3.13でlock、Ruff、offline pytest、diff checkを行う。一方、配布方式、必須チェック設定、リリース、ロールバックは未定義である
- 実装中の緩和: 最小権限の読取permission、永続credentialなしのcheckout、固定SHAのAction、20分timeout、`live_api` 除外を設定した
- 現在の影響: 決定論的な品質ゲートは追加中だが、ホスティング環境での実行確認、配布再現、シークレット注入、復旧は保証しない
- 解消条件: CIを実際のGitHub実行で確認し、必須チェック、配布先、シークレット注入、書込領域、リリース、ロールバックを決定して自動検証する
- 関連大規模タスク: [TASK-004](GOAL.md#task-004-観測可能性と配布パイプラインの整備)

#### TD-007: モデル境界の制約不足

- 状態: 未着手
- 根拠: `ProductAttributes.price_preference` の列挙値とリスト件数、商品URLのスキーム・ホスト、評価範囲、文字列長はPydanticモデル自体で制約していない。価格の正数化や範囲入替は属性抽出サービスで行う
- 現在の影響: 現行サービスを通らずモデルを直接構築した場合、同じ保証を得られない。外部URLはモデル検証だけでは表示可否を判断できない
- 実装済みの緩和: 次期 `src/search_v2/` はlegacy modelと分離し、strict/extra-forbid、nested instance再検証、文字数・配列数・価格mode、query URL/control/重複をmodel境界で強制する。Bonsai v2 requestは固定prompt・canonical schema・exact body・model・endpoint・response上限をdigestへ結び、1-call予約と注入transportのlifecycleをfail closedにする。request v5はapplicationの生成token上限とHTTP timeoutを公開契約に持たず、完全schemaから `pattern` だけを除いた非空の生成用schemaをbodyへ含め、両schemaのdigestを別々に固定し、旧schema・旧fieldをstrictに拒否する。network非依存Bonsai adapterはfull raw response body、envelope、content全体のstrict JSON、単一object、完全schemaによるstrict intentを検証し、救済parseを行わない。決定的tokenizerは意味語句をSudachi内容語と英数字へ再分割し、URLをtoken化前に拒否する。承認段階snapshot、canonical plan、single-use token、provider別利用量予約はstrict modelとdigestへ結び、同一process内の並行予約・二重消費をlockする。CloudflareとOutscraperのcredential-free request descriptorは送信fieldとdigestを固定し、Outscraper guardはactual query batch・request digestをtoken claim前に照合する。v2 Cloudflare HTTP境界はstate・4-call予約・exact endpoint・multipart field、応答サイズ・JSON envelope・Base64・PNGを再検証し、metadataなしの512px RGB PNG、固定エラー、利用量・state確定へ投影する。v2 Outscraper HTTP境界はpermit・予約・送信parameter、task ID・status・same-origin exact結果path、応答サイズ・JSONを再検証し、固定エラーと利用量確定へ投影する。v2商品normalizerはraw文字列・数値・配列と出力件数を有界化し、ASIN・URL・価格等をstrict modelへ投影する一方、未観測属性とPrimeを未知のまま残し、商品文をprovider clientやLLMへ接続しない。段階別orchestrationはこれらのstrict modelとdigestを各確認点で再検証し、Bonsaiから完了までをmock・fixtureだけで接続する。画像境界はallowlist、全DNS addressのglobal判定、peer一致、応答・画像上限を持つcore、canonical hostを1回だけ解決してTCP用IPv4・IPv6を最大8件返すresolver、検証済み先頭IPへ直接接続して元host名をTLS検証へ使うtransportへ分離した。現行 `src/schemas.py` とlegacy pipelineの互換境界は変更しておらず、v2 HTTPと画像境界はmock・`getaddrinfo`・socket/TLS/HTTP fixtureで主に確認し、proxy serviceは起動時の合成allowlistと既存3層を束ねるoffline境界まで追加した。運用allowlist値・実host通信、live provider、現行pipeline、認証・API、複数worker境界へは未接続である
- [EXEC-070](GOAL.md#exec-070-cloudflare応答画像の安全な形式正規化) で、Cloudflare成功応答のraw画像をPNGだけに限定せず、2 MiB以下のJPEG・PNG・WebPをmagicとPillow formatの両方で検証し、完全decode・単一frame・512×512を通過した場合だけmetadataなしRGB PNGへ正規化するよう修正した。別承認の基準画像1 callはretry 0で成功し、正規化PNGの保存まで実Cloudflareと結合確認した。4方向set、counterfactual生成、画像品質、実請求額、production E2Eは未確認である
- 解消条件: 受け入れる値と互換性を要件化し、モデルまたは明示的な境界サービスで一貫して検証する

#### TD-008: 為替とランキング品質の評価

- 状態: 対応中（利用者判断により独立評価を保留）
- 根拠: USD価格は `USD_TO_JPY_RATE` の固定整数で換算する。総合係数と条件語重みは手動決定値である。[次期検索バックエンド v2](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装) のranking v3はtitle 0.35、attributes 0.30、price 0.20、image 0.10、review quality 0.05と固定CLIP image embedding境界を採用する。前処理は縦横比維持・全体保持・モデル平均余白profileへ移行した。case1のlocal画像dataset、case2・case3の期待順位付き候補は追加したが、case2・case3に候補と独立した4方向参照がなく、複数query総合評価setはまだない
- 実装済みの緩和: 次期ranking v3は固定profileとdigest、日英token coverage、観測属性だけの重み付き一致、strict price mode、平均4.0以上のratingと対数飽和したreview countによる最小weightの補助評価、欠損weight再正規化、negative cap、response indexによるstable tie-break、score breakdownをofflineテストで固定した。星別件数やレビュー本文は推測しない。Cloudflare mock応答はmetadataを除いた512px RGB PNGへ正規化するが、生成品質は評価していない。[EXEC-026](GOAL.md#exec-026-単一条件の複数画像clip-characterization) から [EXEC-030](GOAL.md#exec-030-画像ランキングの視覚的特徴限定) でcase1の固定manifest、自己参照なしscore、属性別責務を再現可能にし、[EXEC-031](GOAL.md#exec-031-case2固定候補と自己参照除外clip診断) でcase2の特徴・期待順位・reviewを固定した。[EXEC-032](GOAL.md#exec-032-全体保持clip前処理とcase3準備) では画像全体をモデル平均余白内へ収めるprofileとruntime digestを固定し、case1・case2を再characterizationした。[EXEC-033](GOAL.md#exec-033-case3固定候補と自己参照除外clip診断) でcase3の20候補、期待順位、review、独立参照不足と診断値を固定した。画像componentはdisabledであり、基準未達のCLIP scoreを順位へ使わない
- 実装済みの緩和: [EXEC-034](GOAL.md#exec-034-型付き条件と証拠別ランキングの設計) で、条件をnamespace付きkey・値型・演算子・重要度へ分け、evaluatorとweightをtrusted registryで固定し、証拠を `match`・`mismatch`・`unknown`・`conflict` へ裁定する方針を定めた。[EXEC-035](GOAL.md#exec-035-型付き条件と証拠裁定の最小domain実装) では、strictな期待値・観測値、9 keyの固定registryとdigest、source metadata binding、証拠裁定、固定分母の一致率、必須状態、候補集合非依存の順位keyを外部通信なしの独立domainへ実装した。[EXEC-036](GOAL.md#exec-036-観測商品から型付き証拠へのadapter) では、正規化済み商品の専用color、固定feature全体、有界な商品名表現から、product・requirement・registry・profileへ結んだ `structured`・`title_exact` 証拠を作るadapterを実装した。[EXEC-037](GOAL.md#exec-037-bonsai型付き条件候補adapter) では、既存1回のBonsai strict応答へJSON-nativeな条件候補を追加し、trusted registryで確定または固定blocking issueへ分けるadapterを実装した。[EXEC-038](GOAL.md#exec-038-型付き条件ranking-v4境界) では、ready proposalだけを受けて全商品の限定証拠・裁定・評価を作り、自由語attributesをunknownも残す固定分母typed scoreへ置き換え、必須状態を総合scoreより先に扱う独立v4を実装した。[EXEC-039](GOAL.md#exec-039-型付きranking-v4のoffline検索経路移行) では、同じproposal digestをschema 3.0の第1確認・承認・state・後半pipelineへ伝搬し、schema 2.0の表示履歴へ必須状態と限定理由を保存する経路へ移行した。旧v3 artifactとSQLite version 1は暗黙変換せず、画像を無効のまま維持する
- 実装済みの緩和: [EXEC-040](GOAL.md#exec-040-未使用holdoutの評価契約と集計境界) で、development IDを拒否する正解datasetと、runtime artifactからdigest・状態・順位だけへ投影する予測setを分離した。条件precision・recall・F1、候補precision・recall、decision accuracy、hard contradiction recall、uncertainty preservation、required status accuracy、strict pairwise accuracy、NDCGを、blocked・failed・欠落を除外せずcase・category・全体へ集計する。最低構成への適格性だけを返し、実データを見ていない段階で品質pass・failを捏造しない
- 実装済みの緩和: [EXEC-041](GOAL.md#exec-041-holdout品質合格ポリシーの固定) で、実holdout閲覧前に安全重視の基準をpolicyとdigestへ固定した。coverage不適格またはcategory別安全label不足を `ineligible` とし、適格なreportではblocking・failed 0件、安全指標・required status 1.0、条件・候補・decision・順位の固定閾値を全体と全categoryへAND適用する。raw evaluation reportの `quality_decision=not_assessed` は変更しない
- 実装済みの緩和: [EXEC-042](GOAL.md#exec-042-固定済み基準による未使用holdout評価) で、適格な2 category・4 caseをlocalhost Bonsaiへ各1回だけ通した。4件全てのstrict応答失敗を除外せず、元reportを `not_assessed` のまま保ち、固定assessmentを `fail` と確定した
- 実装済みの緩和: [EXEC-043](GOAL.md#exec-043-bonsai構造化出力と安全診断) で、生成時の `json_object` 制約、application `max_tokens` を送らないrequest v3、本文非保持の6段階diagnosticをoffline TDDした。現行Pydantic schemaはllama.cpp converterが未対応regexを拒否するため、生成grammarへ直接渡さずstrict parserを最終権威として維持する
- 実装済みの緩和: EXEC-043の承認済みdevelopment regressionは4件全てが旧300秒timeoutで `request_failed` となった。[EXEC-044](GOAL.md#exec-044-bonsai-application-timeout撤廃) でrequest schemaを4.0へ更新し、applicationの生成token上限とHTTP timeoutをrequest・transport・configから削除した。1 MiB response上限、retry禁止、strict parserは維持する。[EXEC-045](GOAL.md#exec-045-時間上限なしbonsai-development-regression) では別の明示承認後に同じ4件を完走し、全件の失敗段階を `content_not_json` まで限定した
- 実装済みの緩和: [EXEC-046](GOAL.md#exec-046-llamacpp互換bonsai生成schema) で、完全schemaから `pattern` だけを除く非空の生成用schemaをrequest schema 5.0へ追加した。完全schemaと生成schemaの別digest、canonical body、request全体を再検証し、application側の完全strict検証、token・timeout制御なし、1 call・retry 0を維持する。現行llama.cppのC++ converterでgrammar変換できることはmodel・HTTPなしで確認した
- 実行時の発見: [EXEC-047](GOAL.md#exec-047-request-v5-local-bonsai-development-regression) の初回4要求はport listenだけを起動条件にしたためmodel ready前に失敗した。新しい明示承認後、`/health=200` を待って同じ4件を各1回送ると、全件がHTTP 200、`finish_reason=stop` で完了し、strict intent検証を通過した。非空生成schemaはrequest v4の `content_not_json` をこの4件では解消した。その後は評価用一時runnerの後処理が4件とも一括 `postprocess_failed` となった。合成ready intentはrankingまで通り、合成blocking ambiguity intentはproposal後のquery plan生成で停止することを確認したが、実4件の個別失敗段階は本文を保持していないため復元できない
- 実装済みの緩和: [EXEC-048](GOAL.md#exec-048-holdout後処理段階診断とquery-less-blocking投影) で、typed proposal、query plan、typed ranking、prediction projectionを本文非保持の固定4段階へ分けた。上流blocking ambiguityはquery plannerを呼ばず、intent・proposal digestへ結んだquery-less blocking predictionとして評価へ含める。rankedはquery planとbatchを引き続き必須とし、既存評価profile、acceptance policy、元reportの `not_assessed` は変更していない
- 実装済みの緩和: 段階診断付き部分再計測では2件がstrict intent後の `query_plan_invalid` となった。利用者の実行数訂正を受け、送信済みの3件目を中断し、4件目は送信していない。部分実行のassessmentは作らず、実2件の本文非保持により直接原因は断定していない。[EXEC-049](GOAL.md#exec-049-bonsai-intent検索可能性contract) で、同じstageを生む非blocking空検索fieldの契約欠落を合成入力で再現し、strict intent受理前のquery plan構築検査とpromptの検索語必須・URL禁止規則をoffline TDDした。blocking ambiguityのquery-less投影は維持する
- 実装済みの緩和: [EXEC-050](GOAL.md#exec-050-bonsai検索可能性失敗段階の分離) では、条件を再提示して明示承認を得た後、更新promptの先頭1 case・合計1 callだけを実行した。HTTP 200後にadapterの `intent_normalization_invalid` で停止し、2件目、retry、dataset assessmentは実行していない。実行時点ではnormalizer失敗と検索不能が同じstageだったため、追加推論なしで後者を `intent_searchability_invalid` へ分離した。固定messageと本文非保持は維持する
- 実装済みの緩和: [EXEC-051](GOAL.md#exec-051-bonsai生成schema整合とdraft診断) では、次の明示承認後も先頭1 case・合計1 callだけを実行し、HTTP 200後の `draft_schema_invalid` を確認した。2件目、retry、dataset assessmentは実行していない。直接違反fieldは断定せず、生成schemaへ互換regexと価格mode・source別9 variantを追加し、次回は本文や値なしの固定draft違反groupも得られるようにした。完全schema、token・timeoutなし、1 MiB response、retry禁止は維持する
- 実装済みの緩和: [EXEC-052](GOAL.md#exec-052-新生成schemaのlocalhost-1件確認) では、再提示した固定条件への明示承認後、先頭1 case・合計1 callだけを実行した。HTTP 200後、生成schema、完全draft schema、正規化を通過して `intent_searchability_invalid` で停止した。2件目、retry、dataset assessmentは実行していない。追加推論なしで通常経路の商品種別または全blocking確認待ちを生成時に強制し、検索不能を本文や値なしの `missing_terms`・`invalid_terms` groupへ分ける次schemaをoffline実装した
- 実装済みの緩和: [EXEC-053](GOAL.md#exec-053-生成時検索可能性schemaのlocalhost-1件確認) では、再提示した固定条件への明示承認後、そのschemaを先頭1 case・合計1 callだけで確認した。HTTP 200後にstrict intentとtyped proposal生成まで成功し、proposalは `blocking` となった。2件目、retry、dataset assessment、商品取得、rankingは実行していない。本文非保持のためblocking理由は断定しない
- 実装済みの緩和: [EXEC-054](GOAL.md#exec-054-query-less-blockingの第1確認接続) でtyped proposalをqueryより先に確定し、blockingをquery plan・query digestなしの専用第1確認へ返すoffline境界を実装した。query付きblockingとqueryなしreadyを拒否し、blocking確認から画像生成または画像なし続行へ進む操作はCloudflare・Outscraperの予約・callより前に停止する
- 実行済みの結合確認: [EXEC-055](GOAL.md#exec-055-query-less-blocking第1確認のlocalhost-1件結合確認) で、使用済みCSVの先頭1件を現行orchestratorへ合計1 callだけ通した。HTTP 200後にtyped status `blocking`、query plan・query digestなしの `BlockingIntentReview` へ到達し、Cloudflare・Outscraperの予約・call、商品取得、ranking、assessmentを開始しなかった。本文非保持のためblocking理由と妥当性は断定しない
- 実装済みの緩和: [EXEC-063](GOAL.md#exec-063-bonsai自由語と商品名のsource-grounding) で、一続きE2E第1段階における無根拠商品名と条件欠落を検出した。商品名、brand、model number、自由語termをSudachiPyの完全source spanまたはASCII語境界へ照合し、正しい3桁comma区切りのJPYは復元し、不正区切りへ部分一致しない。商品名fieldが空でも入力に根拠のある肯定検索語が残ればqueryを作る。SudachiPyの連続接頭辞を後続内容語へ結合し、queryと類似語scoreで同じ未知複合語を保持する。接頭辞修正後の実model 1 callは期待queryを作り、別承認のOutscraper 1 taskは24候補の正規化・typed rankingまで完了した。providerが省略した全条件の復元、個々の順位品質、browser・UI・production E2Eは未確認である
- 実装済みの緩和: [EXEC-065](GOAL.md#exec-065-未知の視覚条件に対する条件別counterfactual画像評価) で、最大3件の未知視覚語句をNFKC/casefold済みsourceへSudachiPyまたはASCII語境界で再照合し、条件・registry・reference画像・固定CLIP runtimeをdigestへ結ぶstrict domainを実装した。desired anchorと条件数どおりのcounterfactualをpHash非重複で固定し、候補非依存のraw marginと参照差正規化を計算する。候補欠損は `missing`、数値的な参照分離不足は `unknown` とする。承認済みのテスト用gpt-image 6 calls、retry 0と利用者確認済み参照で初回development較正した後、追加外部callなしでminimum-positive v4とlabel-free batch較正を実装した。較正は条件名や正解labelを使わず、同じbindingの4〜32候補の観測中点を共通閾値0へ写し、片側連続分布を `insufficient_diversity` にする。同一bindingの適格20判定でaccuracyとpool AUCは未較正v4の0.85・0.93から1.0・1.0へ改善した。続く未知のデスクライト・クランプ条件1 caseはAUC 1.0、accuracy 0.875で絶対基準未達だった。[EXEC-066](GOAL.md#exec-066-counterfactual-v4の暫定本番実装) ではこの数値を隠さず、人間暫定採用の別profile、Cloudflare exact `1 + N`、明示参照確認、商品画像proxy・固定CLIP、画像有効ranking v5を旧schemaと分離して実装した
- 現在の影響: 暫定profileは未知1 caseのaccuracy 0.875を受容した運用判断であり、画像品質の最終合格ではない。既存 `typed-ranking-v4` と旧orchestrator経路の順位は変わらず、現行 `IntentReview` から明示的に新versionへ分岐した場合だけ画像componentが有効になる。永続single-use approval stateとschema 5.0履歴はoffline実装済みだが、実Cloudflare・運用画像host・API・UIは未接続である。case1からcase3、電気ケトル、オフィスチェアの旧診断値も置換しない。現行商品adapterに専用parserがないattribute、実商品で欠ける属性も `unknown` のままであり、実勢為替との差、weight・tokenizer・正規化変更、Cloudflare生成品質、複数queryの実検索品質は引き続き自動検出できない
- 解消条件: 未知データへの一般化を判定する場合はcase1からcase3、今回のCSV、EXEC-064で使用した条件を除外した新しい未使用の複数category dataへ固定policyを適用する。外観componentには候補とは独立した4方向参照を使い、画像ON/OFF、日英query、rating・review countを含む欠損componentと為替鮮度も固定データで評価し、CLIP画像weightは採用基準を満たすまで有効化しない
- 次の確認: 最初の未知条件1 caseを閾値調整へ流用せず、case1からcase3、今回のCSV、EXEC-064・EXEC-065とデスクライト・クランプ条件を除外する残り独立holdoutを、画像取得・生成前に固定する。最低2 category・各2 caseの構成、label規則、hard contradiction・uncertainty、単一class、outlier、失敗・欠損を含む絶対gateを事前にdigestへ結ぶ。新しい外部呼出しは送信内容・回数・費用を再提示して別の明示承認を得るまで行わない
- 関連大規模タスク: [TASK-005](GOAL.md#task-005-ランキング品質評価の確立)
- 次期実装: [TASK-008](GOAL.md#task-008-次期検索フロー-v2-の実装)

#### TD-009: AI変更の役割分離と証拠契約

- 状態: 対応中
- 根拠: AI実装者の変更を、独立したreviewer / adversary、固定commit差分、RED→GREEN証拠、機械検証可能な結果へ一貫して結び付ける仕組みがなかった
- 実装済みの緩和: TaskSpec v2とstrict artifact契約、canonical Git policy、root `.env.example` の空値検査後除外、共通credential path/secret scanner、content-addressed candidate/RED snapshot、networkなしraw offline runner、bounded packet、root-owned stdlib preflight、pinned coordinator/runner/broker/gateway image、fixed egressのprovisioned lifecycle、失敗attemptを含むfrozen final ledger、Ed25519、exact SQLite nonce ledger、frozen attested judge、7-phase digest/replay protocol、stdlib固定state machineを追加した。external phaseはprepared payloadとexact raw evidenceをphase digestへ結び、brokerはhost SQLite削除後も再finalizeできる。7/7 actual handlerは、同じimmutable evidenceからexpectationを再構築するsign/judgeまで接続済みである。さらにexternal approved manifest SHAとhuman-approved patch SHAを必須にするcredential-free `workflow-init`、4つのmanifest-pinned imageをnetworkなしで検査して `nonlive_ready` だけを返すdeployment checkを追加した。TaskSpecはruntime release builderのPydantic full validation、manifestのraw task/harness binding、launcher import前のv2/harness narrow checkへ責務分離した。deployment checkはpasswd HOME由来の明示HOME/XDG、candidate-inaccessibleなconfig/storage path、Podman infoのgraph root/run root/active config/seccomp stable subsetを前後で結び、別image store指定を拒否する
- 現在の影響: コードと回帰テスト上の7/7境界、初期request生成、credential-free deployment preflightは閉じ、独立security reviewの未修正CRITICAL/HIGHも0である。2026-08-16に専用user/subuid/subgid、private passwd HOME/XDG、approved storage config、rootless Podman 6.1、root-owned release、具体的TaskSpec v2 canary、4つの異なるimage digestを配備し、実host `nonlive_ready` を確認した。external manifest/patch anchorを再照合し、`ai-review` 所有のstandalone candidateからUID 1100所有0500/0400のlive用initial requestも生成した。残る未検証境界はlive 7-phase E2E、GitHub Actions、Python 3.10 local実行である。nonce ledgerはreplay防止のため単調増加し、保持・backup・容量・rotation方針は未定義である
- セキュリティ制約: source-tree launcher、candidate内Python/task、root実行、Docker/rootful Podman、user namespace/seccompなし、caller任意のHOME/XDG、candidate-writable config/store、alternate image storeへfallbackしない。external AIにはpacketだけを渡し、candidate filesystemとcredentialを同じ主体へ持たせない。完全なattested verdictでも人間承認を維持する
- 解消条件: 別途承認した送信内容、credential、費用上限でlive 7-phase E2Eを確認する。nonce ledgerの保持・backup・容量・rotationと古いattestationの検証方針を定義する。live API未実行の間はその境界を明記し、credential-free `nonlive_ready` やinitial request生成をlive成功へ読み替えない
- 関連大規模タスク: [TASK-007](GOAL.md#task-007-attested-ai-review境界の実装)
- 実行計画: [EXEC-002](GOAL.md#exec-002-attested-ai-review境界の実装)

#### TD-010: Cloudflare画像生成途中失敗後の回復state

以下の4枚一括再試行はEXEC-018での初回解消記録である。現在の公開入口は [EXEC-080](GOAL.md#exec-080-4方向生成を製品フローから除去) で先行1枚の確認後に偽画像だけを生成する方式へ更新した。失敗後は先行1枚の残数内で作り直して再確認するか、画像なしで続行する。過去後続の成功・失敗利用量、古い確認の失効、並行single-useをofflineで確認しており、今回残る再現済み不具合はない。先行確認のprocess再起動後復元と実provider・UI検証はTASK-008の未対応境界として維持する。

- 状態: 解消（2026-09-03、offline境界）
- 対応前の根拠: `cloudflare_http.py` は4件のうち1件でも失敗すると利用量reservationを `failed` にできたが、`SearchSessionSnapshot` は `image_generating` のまま残り、同じ検索を新しい4枚一括attemptまたは画像OFFの最終確認へ進める遷移を持たなかった
- 現在の影響: 同じsessionを安全に回復できない問題は同一processのoffline orchestrationで解消した。永続化、複数worker、実Cloudflare、API・UI接続では未検証である
- セキュリティ・費用境界: 自動retry、失敗reservationの解放、成功した一部画像の採用、同じattempt IDの再利用を許可しない。再試行は新しい4-call予約として上限を再検証し、画像なし続行でも失敗attemptを監査・利用量から削除しない
- 解消条件: `image_generating` の失敗を明示したstrict stateとrevisionを追加し、利用者が4枚一括再試行または画像なし続行を選ぶまでproviderを呼ばないこと、stale・改ざんstateを拒否することをoffline回帰で確認する
- 対応: `SearchSessionSnapshot` に `image_generation_failed` と `failed_image_reservation_id` を追加し、`ImageFailureReview` が現在のledger上のfailed予約、owner、session、query、policy、attempt履歴へ結ぶ。`retry_failed_images()` は最大2組の範囲で新しい4-call予約だけを開始し、`skip_images()` は失敗利用量を残したまま画像OFFの最終確認へ進む。再試行成功後の承認planは失敗分と成功分の8 callsを含む
- 検証: 追加回復契約11件、state・orchestrator 32件、全v2 475件、offline全体1207件が成功。実Cloudflare、credential、課金、永続化、API・UIは未確認
- 関連大規模タスク: [TASK-008](GOAL.md#task-008-次期検索フロー-v2-の実装)
- 実行計画: [EXEC-018](GOAL.md#exec-018-cloudflare画像生成失敗後の回復state)

#### TD-011: 画像取得・推論の実環境検証

- 状態: 対応中
- 根拠: `image_proxy_dns_process.py` はWindows 11 / WSL互換の `spawn`、5秒application deadline、最大512 bytesのbyte IPC、terminate・killを実装したが、主な検証はfake process・pipe・clockである。WSL2の実process確認も外部DNSへ進まない固定失敗経路1回だけであり、Windows native、運用allowlist、実hostへのDNS/TLS/HTTPは未確認である。固定CLIPはrepository-local ONNX 3 file、ONNX Runtime 1.23.2、CPU encoder、縦横比維持・全体保持・モデル平均余白の224×224前処理、30秒 `spawn` process isolationまで実装し、local-only経路の合成画像とcase1からcase3で実model推論に成功した。case1は固定4参照と自己参照を除く27候補、case2は独立参照なしの11候補、case3は独立参照なしの20候補である
- 実装済みの緩和: 基礎resolverがhostとDNS構造を有界化し、process resolverが要求ごとのdaemon子processと親側deadlineへ隔離する。親子の戻り値にはpickleを使わず、ASCIIの成功結果を親側でcanonical numeric IPv4・IPv6へ再検証する。画像scoreは視覚的特徴だけの補助評価へ限定し、有線・無線を商品名と構造化された観測属性へ分離する。画像rankingは品質評価が終わるまでdisabledを維持する
- 実装済みの緩和: [EXEC-034](GOAL.md#exec-034-型付き条件と証拠別ランキングの設計) は、生成画像を外観参照に限定し、候補画像との4方向CLIP最大cosine平均をexact属性の証拠にしない。[EXEC-035](GOAL.md#exec-035-型付き条件と証拠裁定の最小domain実装) の初期registryは、個数、向き、接続方式等のexact属性に `structured` と `title_exact` だけを許可し、`visual_feature` とCLIP類似度を証拠裁定へ入れない。型付き条件domainは独立4方向参照の受領なしで実装した
- 実装済みの緩和: 固定合成基準画像1枚は別承認の実Cloudflare 1 callで生成・正規化保存まで成功した。[EXEC-071](GOAL.md#exec-071-counterfactual-cloudflare最小live-runner) では、暫定production正本の最小1条件をdesired＋counterfactualのexact 2 calls・retry 0で選択し、全成功時だけ新規directoryへ0600 PNG 2枚を保存する専用live runnerを追加した。別承認の実Cloudflare testも1回だけ実行し、2 calls、retry 0、18.388秒で成功し、白いマグと同じ構図・形状・材質の青いcounterfactualを定性的に確認した。未知条件全般、CLIP、実商品、ranking、production E2Eは未確認である
- 実装済みの緩和: [EXEC-072](GOAL.md#exec-072-実商品画像proxy固定clip最小live-runner) では、Outscraper再実行を避け、test専用SecretStrのexact `m.media-amazon.com` URLをproduction proxyで1 GETし、既存参照2枚と同じ固定CLIP batchへ渡す専用runnerをoffline TDDで追加した。URL非露出、retry 0、参照file・出力権限、固定失敗stageを確認した。別承認の隔離browserで1 navigation・外部要求100件・送信前遮断65件・retry 0によりURL 1件を秘密設定へ保存し、限定liveは1 GET・retry 0・CLIP 3画像・3.440秒・margin 0.570058732で成功した。Outscraper由来画像と複数商品rankingは未確認である
- 実装済みの緩和: EXEC-074の承認済み再診断ではOutscraper 1 taskから24商品を正規化したが、運用hostが返した一意DNS結果9件を従来の最大8件契約が全件拒否し、Amazon HTTPへ0件しか到達しなかった。生結果を最大64件まで全件構造検証し、重複排除後にtransport候補を最大8件へ制限するようresolverを修正した。全画像missing時は `image_unavailable` を返す。修正後の別承認liveはCloudflare 2 calls、Outscraper 1 task・poll 9回、24商品の正規化、Amazon画像要求・取得各24件、固定CLIP 7 batches、暫定ranking v5を `image_ready` で完了した
- 現在の影響: OS名前解決とCLIP推論のapplication側終了契約はoffline fixtureで確認できるが、Pythonの `Process.start()` 自体はpreemptできず、Windows nativeの起動・終了時間、実DNS・TLS・HTTP、実商品でのCLIP順位品質を保証できない。case1からcase3に加え、2026-09-07の初回実商品E2Eは候補不足で不適格だった。category-onlyの電気ケトル条件は正例4・負例6、pairwise AUC 1.0で通過したが、次の未使用オフィスチェア条件は正例4・負例6、pairwise AUC 0.291666667、中央値逆転で失敗した。counterfactual developmentではlabel-free batch較正付きminimum-positive v4が適格2条件AUC・pool AUC・accuracyを全て1.0へ改善して相対合格したが、同じ使用済みデータでの結果である。続く未知のデスクライト・クランプ条件1 caseはAUC 1.0でもaccuracy 0.875で不合格だった。最低2 category・各2 case、候補集合依存、outlier・単一classが未完了のため、十分な商品順位や未知条件への一般化、長時間安定性を証明しない。process isolationはsandboxやDNS真正性も提供しない
- 解消条件: repository-localの固定model assetと実encoderのprocess隔離、全体保持profile、case1からcase3のcharacterization、far側の属性別hard negative、near側の目視属性固定、画像と構造化属性の責務分離、Bonsai条件adapter、限定商品証拠adapter、独立typed-ranking-v4、適格category-only 2条件の1 pass・1 fail、EXEC-065のstrict domain、development較正fail、batch較正付きminimum-positive v4のdevelopment相対合格までは完了済みである。次に未知category・条件と単一class・outlierを含む独立holdout、本番Cloudflare用の別holdoutを順に確認する。残るWindows 11 nativeとWSLの対象起動方式でprocess lifecycleを確認し、運用allowlistと実host試験は送信先・回数・保存範囲の明示承認後に限定して行う。本番Cloudflare実生成・製品接続と複数カテゴリでの本合格基準達成後にだけ画像rankingの有効化を判断する
- 関連大規模タスク: [TASK-008](GOAL.md#task-008-次期検索フロー-v2-の実装)、[TASK-005](GOAL.md#task-005-ランキング品質評価の確立)
- 実行計画: DNSのoffline境界は [EXEC-024](GOAL.md#exec-024-windowswsl向け画像dns-process-isolation)、固定ONNX CPU runtimeと受領1組のsmokeは [EXEC-025](GOAL.md#exec-025-固定onnx-clip-cpu-runtimeと品質smoke)、case1の評価は [EXEC-026](GOAL.md#exec-026-単一条件の複数画像clip-characterization) から [EXEC-030](GOAL.md#exec-030-画像ランキングの視覚的特徴限定)、case2診断は [EXEC-031](GOAL.md#exec-031-case2固定候補と自己参照除外clip診断)、全体保持profileへの移行は [EXEC-032](GOAL.md#exec-032-全体保持clip前処理とcase3準備)、case3診断は [EXEC-033](GOAL.md#exec-033-case3固定候補と自己参照除外clip診断)、型付き条件設計は [EXEC-034](GOAL.md#exec-034-型付き条件と証拠別ランキングの設計)、最小domain・商品・Bonsai adapterと独立rankingは [EXEC-035](GOAL.md#exec-035-型付き条件と証拠裁定の最小domain実装) から [EXEC-038](GOAL.md#exec-038-型付き条件ranking-v4境界)、最小counterfactual live runnerは [EXEC-071](GOAL.md#exec-071-counterfactual-cloudflare最小live-runner)、実商品画像proxy・固定CLIP runnerは [EXEC-072](GOAL.md#exec-072-実商品画像proxy固定clip最小live-runner) で扱う。pipeline接続と独立参照を持つ複数queryの本評価は [TASK-005](GOAL.md#task-005-ランキング品質評価の確立) の後続Plan、実host通信は別の明示承認後に扱う

### 5. 更新規則

- 新規項目にはコード、テスト、実行結果のいずれかの根拠を付ける
- 推測だけのリスクは負債として断定せず、調査タスクまたはPlanの発見事項にする
- 対応中にした場合は、実行中のTaskまたはPlanへリンクする
- 解消時はコミットまたは変更箇所、検証結果、解消日を追記する
- 別の仕組みに置き換えた場合も、移行と旧データの扱いを確認するまで解消にしない
- 優先度は利用形態が変わったときに見直す。特に外部公開や多利用者化はP1項目の前提を変える


## 検索専用属性の実データ品質

- 関連: [EXEC-094](GOAL.md#exec-094-省略された仕様名の推論を改善する)、[EXEC-083](GOAL.md#exec-083-入力に基づく検索専用属性の追加)、[EXEC-093](GOAL.md#exec-093-原文の事実と属性推論を分離する)
- 状態: 原文保持の構造修正に加え、形状詞を含む属性名の誤拒否と、不正な推論名の受理を修正した。EXEC-094の既知7例は本番要求の比較で2/7→3/7。未使用2例の初回は0/2、解析修正後の開発再試験1例も名前の基準は不合格。未知仕様名の意味品質は未解決である。
- EXEC-093時点の確認: 原文の数値・単位・比較・強さを生成前に確定し、省略名は推論対象の数量一覧だけから提案する。完全schemaと原文契約を検証し、不適切な名前や未解析仕様を黙って削除してreadyへ進めない。新wireの数値・定義文はbackendによる構成であり、Bonsaiの意味理解を証明しない。offline2300件成功、全43生成応答の保存とprivate権限・port停止を確認した。
- 次の確認: 商品の数量と性能値の混同、別の機能名や商品名を仕様名にする誤り、仕様名と実商品属性の照合を改善する。追加2例を含む16例は全て使用済みデータとして扱い、独立評価は別の未使用入力で行う。原文保持の成功を未知意味推論や実rankingの合格へ読み替えない。ローカル改善・テストは継続授権の範囲、外部provider・全検索・委託frontendは未実施である。

- EXEC-094の最新検証: offline2322 passed・13 skipped・30 deselected。最終実装への同一要求の保存応答9件のoffline再投入は3/9（生成0 calls）。今回41実応答をrepository外の永続private logへ保存し、権限とport停止を確認した。仕様名の固定基準と品詞解析の成否を分けている。

- EXEC-094継続: 生成・受信の日本語文字/長さ/単位名制約を整合した。offline2352 passed、実grammar84/84。一方、本番要求9例の意味合格は3/9で改善なし。9件readyのうち6件は意味不合格であり、形式制約は意味的な誤受理の防止を保証しない。候補見直し・仮名生成診断も各0/3。追加15応答を永続保存し、根本的な意味推論の課題は未解決とする。


- [EXEC-095](GOAL.md#exec-095-仕様定義を与えたbonsaiの属性同定を検証する) の定義参照診断は完了。正例の候補名/単位のみ7/12に対し定義追加11/12、新規6カテゴリは6/6。名称/単位非表示・順序/ID変更では7/12、正解資料なし/曖昧な16件では全て誤選択した。全52応答は形式上成功し、native grammarでもunresolvedが許されることを確認済み。正しい資料を手動供給した条件での限定改善であり、RAGの検索品質や本番品質は未評価。定義を読む側の近い仕様の区別と、情報不足時の保留能力が未解決である。

EXEC-096で未確認の数値属性を実行させない境界を追加した。Bonsaiの保留出力には依存せず、原文に属性名が明記されない数量はblockingとし、typed proposal/registry/query/確認でも同じ制約を適用する。EXEC-095の保存済み52応答のoffline再生で保留必須16/16を確認したが、正例も36/36保留となる。これは未確定を止める改善であり、未知カテゴリの意味同定品質は未解決。名称の明記で再入力する正常経路を維持しつつ、RAGの取得・意味照合の独立した根拠設計は残作業とする。

EXEC-096の追加live4件では、省略2件blocking/明記2件readyと原文の数値保持は4/4だったが、ポータブル電源の明記入力で商品名が「電源」となり、全項目の事前基準は3/4に留まった。属性同定の保留とは別の商品名抽出の問題として残し、今回のscopeで再生成・prompt補正はしない。


## Candidate経路の画像・履歴接続と結果復元

[EXEC-099](GOAL.md#exec-099-新旧検索フローのoffline連続検証) のoffline連続検証で、EXEC-097/098の新candidate経路は自然文→視覚抽出→検索/画像要求descriptor→商品取得→属性確認→Bonsai/数値rankingの出力までであり、既存画像承認・CLIP点数統合・履歴DBへの接続がないことを確認した。画像要求の作成やJSON書出しを、画像生成や履歴保存として扱わない。既存の別経路は合成provider/CLIP embeddingで画像承認からSQLite履歴再読込まで動くが、新経路への接続の証明ではない。

追加で、`CandidateRanking.model_dump_json()` の出力を `CandidateRanking.model_validate_json()` へ戻すと、数量条件と予算条件のDecimalがJSON文字列であるため `DecimalTarget` のstrict検証で失敗した。共通domain契約は有限Decimal実体を要求する意図的な境界であり、その制約を緩める変更はしていない。EXEC-099時点ではcandidate結果用のJSON復元処理が未実装だった。復元2ケースをstrict xfailとして記録し、初回2 failedの証拠を保持した。

[EXEC-100](GOAL.md#exec-100-candidate結果jsonのdecimal復元) でCandidateRankingのJSON入力に限定したDecimal復元を追加し、復元2ケースを通常の成功テストへ戻した。共通domainの型制約と既存JSON出力形式は維持する。この時点では画像/CLIP接続、承認/費用境界、履歴DBへの投影と保存が未実装だった。後続EXEC-101で画像を持つ新flowのoffline接続を実装した。

2026-09-09の新candidate直接接続診断では、属性明記あり/選択が必要な2入力×3境界が6件とも不適合だった。CandidatePlanは画像生成前のIntentReview検査で拒否され、CandidateRankingはCLIP backendのTypedRankedProductBatch入力とDBのProvisionalHistoryWrite入力へ直接渡せない。mock画像呼出し0、CLIP実行0、DB履歴0件。[WORKLOG 141](WORKLOG.md#141-新candidate出力の画像clip履歴接続条件を直接検証2026-09-09) に根拠を記録した。入力型を緩めて接続済みとせず、承認状態とdigestを保持する接続実装が必要。

2026-09-10の[EXEC-101](GOAL.md#exec-101-candidate経路の画像承認clip履歴接続)でCandidateSearchFlowを追加し、新candidateから段階的画像承認・既存CLIP evaluator・schema5履歴の保存/詳細/一覧/画像再読込までoffline接続した。旧入口へ異なる型を直接渡す互換性は追加せず、新flowが状態と承認を保持し、専用結果型から履歴へ投影する。残課題は実provider/実CLIPの意味・画像順位品質、live/APIの組立、視覚条件なし/画像省略の新履歴経路、途中状態の永続復旧である。


## EXEC-104残課題: 自動領域抽出の品質

状態: 未解決（2026-09-10）。形状専用比較とcandidate/履歴接続は実装したが、CLIPSegの実画像4枚診断では金属製品の対象maskに内部の欠けがあり、ガラス製品2個が連結した領域として抽出された。画像全体のCLIPと違う順位が出ても、正しい本体輪郭による改善とは断定できない。

次に確認するのは対象部位/物体単位の領域分離と輪郭の正確さ。カテゴリ固有の形状ルールや当該2製品だけへのprompt調整で合格にしない。輪郭比較の合成テストと、自動mask・姿勢差・透明物・複数物体・未知カテゴリの精度を別集計する。採点基準を事前固定した独立データの実順位評価、iGPU性能測定、新構成の実検索E2Eは未実施。詳細は[EXEC-104](GOAL.md#exec-104-属性別の画像比較と対象領域の分離)。


EXEC-105でCLIPSeg＋MobileSAMを実装し、既知4枚の近似maskに対する平均IoU0.7016→0.9467と別個体混入0を確認した。金属本体の内部欠けとガラス2個の結合は改善したが、一部の取っ手混入と、輪郭IoUが意図した丸みを十分分離できない問題は残る。CPU4枚58.146秒・peak約1.35 GiBと処理負荷も増えた。未知カテゴリ/姿勢/透明物の独立評価、局所形状を区別する採点、iGPUでの実行資源の確認が次の課題。今回の成功は切出しのdevelopment基準だけで、商品順位の合格ではない。[WORKLOG179](WORKLOG.md#179-mobilesamで個体分離と部位輪郭を改善2026-09-10)を参照。


EXEC-106で測定項目/希望方向を持つ新しい特徴比較を追加し、保存済み2商品の側面の滑らかさではガラスが金属より上となった。手動/自動maskの双方で確認したが、測定項目は診断上の指定である。膨らみの参照差不足と逆方向も検出し、誤った採点を保留する。実Bonsaiが原文から適切な測定種別・方向を選べるか、未知の実商品で意図した順序になるかは未確認。特に姿勢、細い部分、取っ手混入、曲率に対する画素ノイズ、表面の角張りと外周の違いが残る。合成48組成功だけで本番順位を合格にしない。[WORKLOG180](WORKLOG.md#180-意味に対応した形状特徴を実装比較2026-09-10)を参照。


EXEC-107の全24商品再評価では、新方式の目視順位一致率43.2%→36.9%、nDCG@10 0.365→0.336で悪化した。直線的な白いマグが画像点1.0で1位となり、side_smoothnessが直線を高くするため「膨らみ」の代用にならないことを確認した。さらに最大連結成分99.97%以上のmask3件が、微小分離片による空行で保留された。次の修正対象は測定する意味の選択・参照画像の有効性と、対象本体から離れた微小片の扱い。今回の確認ではproduction codeを変更していない。[WORKLOG181](WORKLOG.md#181-全24商品の形状特徴付き総合順位を再評価2026-09-10)を参照。

EXEC-108の実験用測定器では、微小片除去・傾き補正・左右共通の張り出しを測ることで、同24商品の診断順位一致85.6%、明瞭な膨らみ3商品が上位3位となった。ただし参考/偽画像の新指標差0.0123は既存0.02未満で、参照差検査を保持すると全24件の画像採点が保留される。productionへは未統合。次は参照対が要求する膨らみを区別できるかを確認し、新指標の測定誤差と閾値を評価用商品を見る前に校正する。偽画像を省く別診断の成功で既存契約の通過を代替しない。非対称形状・未知商品・実Bonsaiの項目選択・iGPU性能は未確認。[WORKLOG182](WORKLOG.md#182-膨らみ測定の識別力と追加時間をオフライン検証2026-09-10)を参照。

EXEC-109で合成測定誤差から候補閾値0.010636を校正し、別パラメータの誤分離0.011%・明瞭な差検出100%を確認した。ただし現参考対は変形後の最小差0.005680、閾値通過233/400組で安定性基準に不合格。方向逆転は0/400。閾値だけの引下げは不採用とし、参照対の改善と実モデルの切出し誤差に基づく検証を残す。既存0.02も合成の明瞭な差の基準は満たしており、全般的に厳しすぎるとは断定しない。[WORKLOG183](WORKLOG.md#183-膨らみ参照差の閾値を校正検証2026-09-10)を参照。

EXEC-110で両側面の輪郭を明示するprompt v2と、生成後・画像承認前の参照品質検査を接続した。全体offline3021件成功。元参照対は不合格、理想的な直線側面の合成maskでは最小差0.0321で通過した。実際の生成品質は未確認で、偽画像1件の要求を準備して承認待ち。参照の領域抽出は商品評価と未共有のため追加時間がかかる。[WORKLOG184](WORKLOG.md#184-膨らみの生成指示と参照採用前検査を改善2026-09-10)を参照。

EXEC-110の承認済み実生成1件は成功し、新偽画像の側面直線化と参照検査通過を確認した。変形後の最小差0.005028→0.024392で、既存0.02を維持した。生成7.715秒、2枚のローカル切出し・検査48.444秒。参考対1件の改善であり、商品rankingは再評価していない。次は新しい参照を用いる採点の整合性と全24商品のoffline診断、その後の独立商品評価。旧承認・履歴は流用しない。[WORKLOG185](WORKLOG.md#185-承認済み偽画像1枚を実生成し参照品質を検証2026-09-10)を参照。

EXEC111で新偽画像の全24件診断を完了。現行膨らみ測定で順位一致63.1%、改良双方向測定で79.7%となり、後者は強適合3商品が上位3位。滑らかさでは上位品質が悪化するため、測定種別の選択が必要。改良測定は商品rankingへ未接続で、負例以下の点数が同じになる中下位の識別不足も残る。母数不足かつ80%未達なので正式合格とはしない。次は参照検査と商品採点の測定を整合させる実装、その回帰と独立商品での評価。[WORKLOG186](WORKLOG.md#186-新偽画像で全24商品の順位を比較2026-09-10)を参照。

EXEC112で新規取得後の20商品を実ローカルモデルで検証した。改良測定は弱い曲がり/直線の補足画像比較で37.1%→65.9%へ改善したが、明瞭な膨らみ0件で正式評価は構成不適格。コーヒー上面を本体と誤認して満点にする例、取っ手混入、主成分基準に合わない2件と箱だけの空mask1件の保留を確認した。単語点全件0・価格不明10件も診断上の制約。次は対象部位の同定と可視性の検証、単語採点の安全な診断、強適合を含む別の商品群での評価。この20件は使用済みとし再調整後の独立合格には使わない。[WORKLOG188](WORKLOG.md#188-未使用20商品の実画像で膨らみ評価を検証2026-09-10)を参照。


EXEC-113（2026-09-10）: 未知カテゴリで専用形状測定を必須にしない仕様へ変更し、candidate既定は全体外観CLIPになった。以前の部位誤抽出/参照輪郭検査は明示的旧方式の課題として残る。新方式は保存済み44件を採点できたが、以前24件の形状一致は画像171対59.4%→30.4%、価格適合111対63.1%→24.3%に低下。汎用点だけでは膨らみの識別精度を保てない。直近20件の採点率向上や6対の総合順位改善で、この低下を隠さない。箱のみの画像にも全体類似点が付く。対象不在・部位一致の保証、カテゴリを跨ぐ外観評価、画像点の限界を表示するUIは未確認/未接続。保存済み集合を独立holdoutへ再利用せず、カテゴリ専用修正や試験後の重み調整を行わない。詳細は[WORKLOG189](WORKLOG.md#189-汎用外観採点へ変更し保存済み44商品の実clip再評価2026-09-10)。


EXEC-114（2026-09-10）: SigLIP 2 Baseの画像参照比較は現行CLIPに対し既知20/24商品の形状順位一致を65.2%/63.7%へ改善し、事前の比較改善基準を通過した。条件文比較は48.5%/68.4%で直近集合に悪化があり不採用。画像参照方式は本番接続候補だが、未知カテゴリ品質・対象不在・部位一致・iGPU資源を未確認のまま有効化しない。現行CLIPの固定runtimeへSigLIP値を混ぜず、接続時には独立profile/adapterと回帰を必要とする。詳細は[WORKLOG190](WORKLOG.md#190-siglip-2を保存済み44商品で実ローカル検証2026-09-10)。

EXEC-115（2026-09-11）: SigLIP 2画像参照方式は新規カップ21商品でassistant目視順位との一致75.8%（97/128対）、利用者指定60%以上を達成した。目視同点82対は除外して報告し、モデル同点/欠測は不正解扱い。この試験時点では本番統合を行っていなかった。未知カテゴリ、独立人間評価、iGPU性能、総合順位は未検証。印刷のある直線的商品が上位へ来る等の31逆転は残る。今回21商品は以後developmentへ移す。


EXEC-116（2026-09-11）: その後の利用者指示により、独立SigLIP 2 adapter/runtime/profileをcandidate既定へ接続した。画像承認・新旧profileの分離・ランキング・履歴の回帰と全体3045件が成功し、保存済み21商品の本番adapter出力は試験時の点数/順位と一致した。EXEC114の接続候補という状態は更新するが、未知カテゴリ/対象不在/部位一致/独立人間評価/iGPU性能の課題は解消していない。実サービスの再実行と委託UI接続は未実施。[WORKLOG193](WORKLOG.md#193-candidateの既定画像評価へsiglip-2を接続2026-09-11)を参照。
