# 要件

EXEC-167: 新規検索の条件は同じ分類内で先に入力した語句を重くする。異なる開始位置N件へN..1の重みを付けた平均を用い、否定条件では先の条件への一致ほど強く減点側へ働く。分類間優先順と日英最大値・画像点を維持し、結果/履歴の内訳へ重みを表示する。旧履歴は補完・再採点しない。

条件整理中の通信timeoutは主画面のエラー表示を出さず、状態再取得と接続診断への記録を続ける（2026-09-14利用者指示）。

一時的な接続障害でも状態取得/操作受付の失敗種別、発生時刻、所要時間、HTTP statusまたは固定の検証理由を確認でき、回復・同じタブの再読込後に直近10件が残ること。利用者入力・生応答・生例外を保存せず、検索を自動再送しない（EXEC-165）。


接続画面はサーバー再起動後の更新番号を受理し、同じprivate出力先でも起動別の準備先で条件整理を開始できること。履歴保存先を維持し、再起動前のinstanceId付き確認操作を新起動へ適用しない（EXEC-164）。


最終確認の「今回の検索」では、商品名の表示枠の直上に「商品名」ラベルを置く。本番接続画面とオフラインモックで同じ配置を使う。

## オフラインと接続画面のUI共用（EXEC-157）

既定モックは現行接続画面のReactコンポーネントとフローを共用する。商品名・優先/希望/否定条件の編集、画像選択の再整理、準備3回/画像2セット、段階ごとの確認、日英採点内訳、履歴、期限・保存再試行・中止を合成応答で再現する。画像なしでもローカルの商品画像を表示する。モックは固定データであることを明記し、API/モデル/実履歴DB/credentialを使わない。旧モック履歴の閲覧と削除は維持する。詳細は [FRONTEND](FRONTEND.md#14-オフラインモック)。

履歴の保存案内を重複表示せず、内容との余白を保つ。画像ラベルが折り返しても同じ行のカード・画像上端を揃え、採点表の列見出しは途中改行しない（EXEC-158）。

## 画像なしの条件整理（EXEC-155）

画像不使用の選択は準備開始時から有効とし、比較画像用Bonsai推論・対比確定・対比辞書を要求しない。原文の照合条件と分類はローカル解析で保持し、日英採点と履歴保存を行う。画像使用への変更は既存の回数上限内で再整理し、画像の生成確認と検索の最終確認を維持する。


## モックと接続画面の共通表示・操作（EXEC-145）

入力から確認/待機/結果/履歴まで、desktop UIの共通ヘッダー・カード・画像拡大・表示件数・段階/工程・ダイアログを使う。実行可否/残数/進捗はserver状態を使う。自然文での条件修正、準備3回/参考画像2回、worker1、現行順位/旧履歴の互換性を維持する。新規検索は前回の作業先を再利用せず、未保存結果の破棄は確認する。取得中の中止は次の処理境界で比較/保存を止め、保存再試行では商品を再取得しない。

## 新しい接続履歴の保存範囲（EXEC-144）

接続画面の新規完了結果は、元入力全文（2000文字以内）、条件名/分類/指定なし、取得済み商品画像の表示用PNGを再起動後も復元する。既存30日の保持/削除、日英最大値と採点profileは維持する。画像なし検索は画像を追加取得しない。旧履歴の未保存内容は補完せず、入力内容を再解釈/再採点しない。

EXEC-143で履歴一覧/詳細の対象確認付き削除と、server稼働中60秒間隔の30日期限削除を接続した。履歴/専有生成画像は同一transactionで削除し、失敗・応答不明時は同じ対象で再試行できる。GETは期限後の結果を返さず、未指定DB/別owner/生cacheを削除しない。検索状態や保存点数を再計算しない。

EXEC-142で、明示的な画像なし検索を接続画面から商品取得・日英採点・永続履歴まで通す。画像用credential・生成・取得・SigLIPを呼ばず、画像未使用として表示/保存する。外観0件、画像準備失敗、画像承認期限切れも扱い、商品取得の最終確認・重複送信防止・worker1を維持する。検証境界は[EXEC-142](GOAL.md#exec-142-画像なし検索を接続)を参照。

EXEC-140では希望・否定・指定なし・優先の自然文分類を、追加LLMなしの共通ローカル解析へ統一する。希望と否定は否定優先、希望付き予算は希望、指定なしは表示に残して検索/採点/画像から除外する。矛盾や曖昧な範囲は文章修正を求め、旧計画/履歴は読み替えない。表現と検証境界は [BACKEND.md](BACKEND.md#条件表現の共通解析exec-140) に定義する。

EXEC-133の新規candidateは、ローカル辞書/翻訳で条件の同義語・英訳を準備し、日英の商品名と詳細を独立採点して、タイトル・条件ごとの高い点を採用する。否定条件の高い一致点は除外側に働く。タイトルと画像の評価は分け、順位の優先順を維持する。英語取得不能時は日本語点を使う。日本語の主表示・商品リンクと旧履歴を維持する。詳細は [BACKEND](BACKEND.md#条件の同義語英訳と日英最大値採点exec-133) を参照。

## candidateの順位優先度（2026-09-12）

EXEC-162以降、新規SigLIP 2 candidateの最終順位は否定条件（負）、タイトル一致、優先条件required、希望条件preferred、視覚条件の文章対画像、画像対画像、レビュースコアの順。明示した旧画像modeはEXEC-139の画像評価1項目を維持する。同点時だけ次を比較し、全同点なら取得順。否定条件は一致度が低い方、他は高い方を先にする。レビューは取得済み星評価0〜5、画像/レビュー欠損は比較時に評価済み0より後にする。50:50合成値は旧方式の参考値として保持し、新規SigLIP 2 UIでは2つの独立点を表示する。旧履歴を新方式で並べ替えない。詳細は [BACKEND.md](BACKEND.md#否定条件優先とレビューの最終比較exec-139) に定義する。

## 商品取得providerの移行（2026-09-12）

[EXEC-126](GOAL.md#exec-126-商品取得をplaywrightへ移行) により、現行商品検索・詳細取得はAPI key不要のローカルPlaywrightへ移行する。検索語/画像の既存確認操作、条件評価、SigLIP、旧履歴の読込を維持する。商品本文は日本語設定のAmazon.co.jpから観測し、翻訳や推論で補わない。旧Outscraperの課金・polling・API key要件は新規実行に適用しない。必要資材・通信上限・配送先/欠損の扱いは [BACKEND.md](BACKEND.md#playwrightの商品検索詳細取得exec-126) を正本とする。

## candidateのテキスト評価拡張（2026-09-12）

利用者の修正指示により、新規candidateは条件を取得済み説明文から部分一致で探し、一致度を順位へ反映する。構造化観測を優先し、不一致・競合や取得済みの不明値を説明文で上書きしない。否定と数値/単位を区別し、記載の一致度から仕様確認済みの状態を推論しない。

同義語は元の商品表現を優先する補助点としてタイトル採点へ接続する。タイトル比較に日本語・英語カテゴリと、取得できたブランド・型番の専用fieldを持つ。カテゴリは商品表現の語句から、ブランド・型番は明示入力から取得し、不明なものを推測で埋めない。詳細な係数・分母・優先順は [BACKEND.md](BACKEND.md#candidateの説明文タイトル採点exec-125)、保存互換とoffline検証は [EXEC-125](GOAL.md#exec-125-説明文の条件一致とタイトル比較の拡張) を正本とする。LLMによる商品本文の推論・追加サービス呼出しは追加しない。

2026-09-12の[EXEC-124](GOAL.md#exec-124-フロントエンドと実検索の接続)は、固定マグカップ入力・画像あり・最大24商品・1検索のReact接続試験を対象とする。各人間確認で停止し、同一処理の重複実行を防ぎ、serverに保存した結果を表示する。通常モックの任意入力・条件編集・画像なし・履歴一覧の仕様は維持するが、それらの実接続の完成とは扱わない。実サービス成功は別途承認して実測する。

次期フロントエンドは2026-09-11の決定により自前開発する。[SEARCH-FLOW.md](../SEARCH-FLOW.md) と [FRONTEND.md](FRONTEND.md#11-次期フロントエンドの自前開発方針) を実装・受入の目標仕様とし、外部納品を前提条件にしない。[frontend/](../frontend/) にオフライン画面を実装し、Chromiumでのオフライン受入確認済みである。検証結果と未接続範囲は [EXEC-117](GOAL.md#exec-117-react-stylexのオフライン画面) に記録する。

## 1. 文書の目的

この文書は、amazon-explorer の現行実装が満たすべき要件と、将来本番化する場合に追加で満たすべき要件を分けて記録する。承認済みで基盤を一部実装した次期検索の利用者フローは [SEARCH-FLOW.md](../SEARCH-FLOW.md)、技術契約は [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、制約は [統合済み制約](#統合済み制約)を参照する。

状態の意味:

| 状態 | 意味 |
|---|---|
| 実装済み | 現行 `src/` または `frontend/` に実装があり、対応する確認手段がある |
| モック実装済み | `frontend/` の固定合成データで操作できる。実データ・実API・本番運用を満たすことは示さない |
| 一部実装 | 基本動作はあるが、運用要件の一部を満たさない |
| 未実装 | 将来候補であり、現行機能として扱わない |

次期フロントエンドはReact + StyleXで自前開発し、外部納品を着手条件にしない。Figmaはレイアウトの参考、色・文字・装飾・操作配置は [FRONTEND.mdの視覚統一契約](FRONTEND.md#13-次期uiの視覚統一契約) を正本とする。local HTTP API factoryは実装済みだが、次期画面、最終承認controller、server起動構成とは未接続である。次期UIの実装範囲は固定合成データによる画面操作である。server側の承認、実データの表示、認証済み利用者ごとの永続履歴は接続時の要件として残す。

## 2. プロダクト要件

| ID | 状態 | 要件 |
|---|---|---|
| PRD-001 | 実装済み | 利用者は日本語の自然文で欲しい商品の条件を入力できること |
| PRD-002 | 実装済み | 入力から商品名、カテゴリ、色、特徴、除外条件、検索語、価格条件を抽出できること |
| PRD-003 | 実装済み | Amazon.co.jpの商品候補を取得できること |
| PRD-004 | 実装済み | 商品名、属性、価格、否定条件を組み合わせて候補を順位付けできること |
| PRD-005 | 廃止（2026-09-11） | 旧Streamlitの実検索画面。現行ReactモックはUI-010以降で定義する |
| PRD-006 | 実装済み | CLIから同じ検索パイプラインを実行できること |
| PRD-007 | 実装済み | 同じscope・入力・設定に対する外部処理と計算をローカルキャッシュから再利用できること |
| PRD-008 | 一部実装 | 現行と同じBonsaiで検索意図をJSON textへ構造化し、fail-closed parseとstrict Pydantic検証・正規化を通したうえで、利用者が属性・推定価格・検索クエリを確認・修正できること |
| PRD-009 | 一部実装（Cloudflare offline境界） | 画像生成を任意で有効化し、本番Cloudflareで参考画像1枚を生成・確認し、了承後に条件別偽画像だけを生成できること。gpt-imageは画像評価テストだけに使う |
| PRD-010 | 未実装 | Outscraperへ送信するクエリ、画像、取得上限、この承認で商品検索を1回実行することを事前表示し、利用者の明示承認後だけ商品取得を開始すること |
| PRD-011 | 一部実装（offline ranking境界） | 日本語・英語テキスト、価格、任意の意味的画像類似度を説明可能な内訳で統合し、総合スコア降順に表示すること |

主対象はローカルまたは単一ホストでアプリを起動し、BonsaiとOutscraperを利用できる開発者・検証者である。認証済み多数利用者を持つ公開Webサービスは現行対象ではない。

## 3. 機能要件

### 3.1 入力と属性抽出

| ID | 状態 | 要件 |
|---|---|---|
| FR-001 | 実装済み | 前後空白を除いた検索入力が空の場合、外部APIを呼ばず入力エラーにすること |
| FR-002 | 実装済み | Bonsaiへ商品属性抽出プロンプトと利用者入力を送ること |
| FR-003 | 実装済み | BonsaiのOpenAI互換レスポンス形状を検証すること |
| FR-004 | 実装済み | コードフェンスを含む応答からJSON object候補を取り出せること |
| FR-005 | 実装済み | リスト項目、価格、価格範囲、カテゴリ、検索語を後段で扱える形へ補正すること |
| FR-006 | 実装済み | 属性変換に失敗した場合、生のLLM応答を例外メッセージへ含めないこと |
| FR-007 | 実装済み | 日本語検索語、英語検索語、推定日本語商品名の優先順で検索語を決めること |

### 3.2 商品取得

| ID | 状態 | 要件 |
|---|---|---|
| FR-101 | 実装済み | Outscraperへ `async=true` のAmazon Products要求を送ること |
| FR-102 | 実装済み | domain、language、postal code、limitを設定可能にすること |
| FR-103 | 実装済み | APIキーがない場合はHTTP要求前に停止すること |
| FR-104 | 実装済み | 非同期タスクを設定済みの間隔と回数上限でポーリングすること |
| FR-105 | 実装済み | 処理中、成功、失敗、不明、待機超過を区別すること |
| FR-106 | 実装済み | `data=[]` をエラーではなく正常な0件として扱うこと |
| FR-107 | 実装済み | 一時的な通信エラー、HTTP 429、HTTP 5xxだけを上限付きで再試行すること |
| FR-108 | 実装済み | その他の4xxを再試行せず失敗として返すこと |

### 3.3 正規化

| ID | 状態 | 要件 |
|---|---|---|
| FR-201 | 実装済み | Outscraperレスポンスから辞書形式の商品を取り出すこと |
| FR-202 | 実装済み | タイトルがない商品を除外すること |
| FR-203 | 実装済み | JPYとUSDを扱い、USDを設定済み固定レートでJPYへ換算すること |
| FR-204 | 実装済み | その他の明示通貨の商品を除外すること |
| FR-205 | 実装済み | 価格、評価、レビュー数、Prime値、画像配列、文字列を内部形式へ補正すること |
| FR-206 | 実装済み | ASIN、短縮URL、商品URL、タイトルを使って重複商品を除くこと |
| FR-207 | 実装済み | 正規化結果を `NormalizedAmazonProduct` として検証すること |

### 3.4 ランキング

| ID | 状態 | 要件 |
|---|---|---|
| FR-301 | 実装済み | SudachiPyで日本語を、正規表現で英数字をトークン化すること |
| FR-302 | 実装済み | 商品名と属性についてTF-IDFコサイン類似度を計算すること |
| FR-303 | 実装済み | 必須語、色、特徴、優先語、関連語を設定済み重みで評価すること |
| FR-304 | 実装済み | 日本語と英語を別に評価し、より高い方を採用すること |
| FR-305 | 実装済み | 同点時に条件のある言語を選んで不足条件が消えないようにすること |
| FR-306 | 実装済み | 明示価格、価格帯、上下限、安価・高級志向を価格スコアへ反映すること |
| FR-307 | 実装済み | 除外語一致を1件0.2、最大0.5の減点にすること |
| FR-308 | 実装済み | 総合値を0.0から1.0へ制限し、小数4桁で降順に返すこと |

### 3.5 次期検索フロー v2

2026-09-08の画像生成フロー変更は [EXEC-080](GOAL.md#exec-080-4方向生成を製品フローから除去) と [SEARCH-FLOW.md](../SEARCH-FLOW.md) を正とする。先行1枚の了承後に条件別偽画像だけを生成する要件であり、下記の旧4方向・実験用counterfactualの検証記録は新フローの成功を証明しない。

次の要件は、この節と [BACKEND.mdの次期検索境界](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[型付き条件と証拠別ランキング](BACKEND.md#14-型付き条件と証拠別ランキング最小domainを一部実装) で技術契約を、[SEARCH-FLOW.md](../SEARCH-FLOW.md) で利用者向けの操作を定義する。`src/search_v2/` には互換regex、価格mode・source別variant、通常の商品種別またはblocking確認待ちを強制する2分岐を持つ非空のllama.cpp生成schema、完全strict schema、本文非保持の段階・draft・検索可能性group診断、非blocking intentの検索可能性検査、最大2件query、schema 3.0のtyped proposal付き承認・state・段階別orchestration、query-less blocking専用第1確認、Cloudflare参考画像1枚と条件別偽画像、Outscraper task・polling、観測値だけの商品正規化、固定registry・限定商品証拠・条件裁定、必須状態を総合scoreより先に扱う `typed-ranking-v4`、typed decisionからschema 2.0表示履歴を作るSQLite `user_version=2` repository、正解・予測を分離して条件・裁定・順位を集計するholdout評価契約、実データ閲覧前に固定した独立acceptance policy、本文非保持の後処理4段階とquery-less blocking投影を、外部通信に依存しない境界として接続した。要求model・HTTP認可・商品正規化の依存を分けるため、credential-freeなOutscraper要求model・builder・digestは `outscraper_contract.py` に置き、認可を `outscraper_request.py` が担当する。画像取得はexact allowlist、有界DNS、Windows/WSL互換のprocess隔離、pinned-IP・元host TLS検証、固定ONNX CLIP CPU runtimeを持つが、画像scoreは色・形状・商品種別など視覚的特徴だけの補助評価とし、採点を無効のまま維持する。case1はAUC 0.759259259、接続方式を除く責務別評価は0.928571429、独立参照を持たないcase2・case3の限定診断はそれぞれAUC 0.642857143・0.468750000である。health-readyなrequest v5は使用済み4件でstrict intentまで成功したが、typed rankingは未測定である。その後の段階診断付き部分再計測は2件完了後に停止した。更新promptの先頭1 case・合計1 callは `intent_normalization_invalid`、次の承認済み先頭1 case・合計1 callは `draft_schema_invalid` で停止した。生成schema整合後のEXEC-052の先頭1 case・合計1 callは、完全draft schemaと正規化を通過して `intent_searchability_invalid` で停止した。EXEC-053では生成時検索可能性schemaの先頭1 case・合計1 callがstrict intentとtyped proposal生成まで成功し、proposalは `blocking` となった。本文非保持のためblocking理由は断定しない。EXEC-054で、proposalをqueryより先に確定し、blockingをquery plan・query digestなしの専用第1確認へ返して後続providerを予約前に止めるoffline経路を追加した。これらのoffline・mock・fixture成功は実Cloudflare・Outscraper、実画像host、Windows native、未知データの順位品質を示さず、legacy現行検索、認証、API、次期UIへは未接続である。

EXEC-055では、使用済みCSVの先頭1件を明示承認された合計1 callだけ現行orchestratorへ通し、HTTP 200後にtyped status `blocking`、query plan・query digestなしの `BlockingIntentReview` へ到達した。2件目、retry、assessment、商品取得、ranking、Cloudflare・Outscraperは開始していない。この結合確認はFR-401のquery-less blocking停止形を1件で裏付けるが、blocking判断の妥当性、条件分解・商品順位品質、未知データへの一般化、production E2Eを裏付けない。

| ID | 状態 | 要件 |
|---|---|---|
| FR-401 | 一部実装（schema 8.0・prompt-only system message・bounded compact wire復元・互換regex、sparse価格variant、固定検索field branchまたはblocking確認待ちbranch・検索可能性検査・安全診断・mock HTTP・typed候補応答境界。EXEC-055でrequest v5のlocal実応答1件をquery-less blocking専用第1確認まで結合確認済み。EXEC-058でrequest v6の実model 2 calls、full JSON・strict intent・2件目のcache hitを結合確認済み。EXEC-059で同一入力のprompt・生成timing診断を実行し、prompt処理353.47倍・wall全体1.52倍を確認済み。request v8はoffline representative 104 tokensで、承認済みlocalhost 2 callsもstrict intentに成功し、warm wall 17.625秒を確認済み） | 固定promptだけをsystem messageへ入れ、非空のcompact生成schemaを `response_format.schema` へ含め、applicationの生成token上限とHTTP timeoutを持たないBonsai OpenAI互換requestを決定的に作り、1回の開始済み利用量予約へ結ぶこと。完全canonical schema本文はmodelへ重ねて送らず、別digestとapplication側のstrict最終検証に維持すること。llama.cppで有効な生成用JSON schemaを適用し、response envelope、空content、content全体のJSON構文、単一object、unknown field、strict型をfail closedで検証すること。wireで省略できるのはcanonicalで `null`、空list、価格なし、または固定・非該当となる列挙済みfieldだけとし、受信側で完全19-field draftへ決定的に復元して再検証すること。検索可能branchは最大12種類の固定field、確認待ちbranchは `ambiguities` 1 fieldだけを許可し、商品名等48文字、term 32文字、各term list・typed condition・set値4件、ambiguity 2件・各96文字をschemaとadapterで強制すること。生成schemaは完全schemaの既知regex、価格field横断条件、非blockingの商品種別またはblocking確認待ちを可能な範囲で生成時にも強制し、完全schemaとquery plannerを最終権威とすること。非blocking intentは既存query plannerで検索queryを構築できる場合だけ後段へ渡し、blocking ambiguityはqueryなしの専用第1確認を許可して後続providerを予約前に止めること。不一致時は生本文やvalidation値を保持せず、正規化失敗・検索不能・固定draft違反group・固定検索可能性groupを含む列挙済み診断だけを返すこと |
| FR-402 | 一部実装（offline token/query・orchestration境界） | LLMの意味語句をSudachiPyと決定的な英数字tokenizerで再分割し、日本語・英語の検索クエリを最大2件組み立てること |
| FR-403 | 一部実装（offline先行確認、UI未接続） | 画像生成前に意図・クエリと `参考画像を使う（残り2回）` を確認し、まず参考画像1枚を生成して明示了承を待つこと。先行1枚の作成を1回、1計画最大2回として残数を更新し、トグルの既定値をOFFにすること |
| FR-404 | 一部実装（offline分割生成、live未確認） | 先行1枚の明示了承後だけ、本番Cloudflareで別途正面、左側面、右側面、背面の4画像と、選択した視覚条件1〜3件に対応する偽画像を生成すること。了承前の後続生成を拒否すること |
| FR-405 | 一部実装（offline参照binding・single-use） | 後続の偽画像は了承済み先行画像を参照入力とし、同じ了承につき1回だけ生成すること。偽画像は対象視覚条件1件だけを変え、条件変更または先行画像の作り直しで旧了承と後続画像を失効させること |
| FR-406 | 一部実装（mock HTTP・exact request・single-use orchestration） | Outscraperの実行ごとに送信内容を表示し、専用の明示承認なしではAPIを呼ばないこと |
| FR-407 | 一部実装（offline orchestration・後半pipeline・商品証拠adapter） | Outscraper商品を決定的に正規化し、採点に必要な属性を観測できない場合は未知のまま保持すること。Outscraper後の商品候補をBonsai、OpenAIその他のLLMで補完しないこと |
| FR-408 | 一部実装（固定ONNX・CPU process・単一条件31枚characterization） | pHash/Hamming距離を重複検出だけに使い、意味的画像類似度には固定digestのCLIP image embeddingを使うこと。画像scoreは色、外観形状、商品種別など画像で確認できる特徴だけの補助評価とし、構造化属性を推定、補完、上書きしないこと。有線・無線は商品名と構造化された観測属性で判定し、画像scoreでhard filterしないこと |
| FR-409 | 一部実装（typed-ranking-v4 offline pipeline） | 欠損componentを総合重みから除き、利用可能なweightを1.0へ再正規化すること |
| FR-410 | 一部実装（typed-ranking-v4 offline pipeline） | 同点規則を含むstable keyで総合スコアを降順に返すこと |
| FR-411 | 一部実装（offline失敗回復・過去利用保持） | 先行1枚または後続の偽画像が失敗した場合、部分画像を採用せず失敗利用量を残し、自動retryせず、利用者が残数内で先行1枚を作り直して再確認するか、画像なし続行を明示選択できること |
| FR-412 | 一部実装（offline ranking-v3・後半pipeline接続） | 観測済みの平均評価と総レビュー件数から高評価レビューの多さを補助採点し、そのbase weightを全component中で最小にすること。星別件数やレビュー本文を観測していない場合は推測しないこと |
| FR-413 | 一部実装（offline Bonsai候補・local typed adapter・第1確認接続） | 自然文の条件をnamespace付きattribute key、値型、許可された演算子、期待値、`required`・`preferred`・`excluded` の強さへ正規化し、未知key・不正な型・単位・演算子を文字列条件へ暗黙fallbackしないこと |
| FR-414 | 一部実装（固定9-key registry・条件/商品adapter・独立ranking-v4） | attribute keyごとの型、単位、alias、証拠source、evaluator ID・version、既定weightをtrusted registryで固定し、LLM応答や商品データにevaluator、実行module、weightを選ばせないこと |
| FR-415 | 一部実装（offline証拠裁定・限定商品証拠adapter、画像evaluator未実装） | 商品ごとの条件判定を `match`、`mismatch`、`unknown`、`conflict` に分け、単なる語句不在を不一致にせず、構造化値、限定したtitle parse、検証済み専用画像evaluator、外観類似度の許可と優先順位をattributeごとに固定すること |
| FR-416 | 設計済み・未実装 | 了承済み参考画像と偽画像を利用者承認済みの外観参照としてだけ使い、候補画像との固定CLIP scoreから個数、寸法、材質、接続方式、互換性その他のexact属性を推定、補完、上書きしないこと。候補画像欠損時は画像評価を `missing` とすること |
| FR-417 | 一部実装（typed-ranking-v4 offline pipeline・履歴表示） | 必須条件が全て一致した候補、未確認または矛盾が残る候補、明示的不一致がある候補の順を総合scoreより先に固定し、未知条件を商品ごとに分母から除いて有利にしないこと。画像・価格・レビューの高得点で必須条件の明示的不一致を打ち消さないこと |
| FR-418 | 一部実装（候補非依存score・typed履歴理由、画像角度理由未実装） | 同一のreference setとruntimeに対する商品画像scoreを他候補に依存せず計算し、候補集合内のcenter・z-score正規化をproduction rankingに使わないこと。条件判定と画像の角度別scoreを、利用者向けの一致・未確認・不一致理由へ安全に変換できること |
| FR-419 | 一部実装（最初の適格holdoutは `fail`。使用済みCSVの部分再計測は未完走のため新しいassessmentなし） | development setと未使用holdoutを分離し、正解と予測を別digestへ結ぶこと。条件抽出、候補、exact decision、hard contradiction、uncertainty、必須状態、strict pairwise順位、NDCGをcase・category・全体へ集計し、失敗や欠落を除外しないこと。予測artifactへ検索文・商品本文を保存せず、実データを見る前に固定した安全重視の基準を全体・全categoryへAND適用し、構成不足を `ineligible`、品質未達を `fail`、全基準達成を `pass` とすること |
| FR-420 | 一部実装（batch較正付きminimum-positive v4をdevelopment相対合格） | 未知の視覚語句を固定類似語辞書へ丸めず、SudachiPyと英数字tokenizerでNFKC/casefold済み元入力のexact spanへ結んだ最大3条件として扱うこと。実験用referenceは候補と独立したdesired anchor 1枚と、1条件だけを違反させたcounterfactual `N` 枚のexact `1 + N` calls、上限4 callsとする旧実験契約であり、先行1枚の了承後に偽画像だけを作る製品フローはFR-403〜FR-405に従うこと。候補画像をgeneratorまたはLLMへ送らないこと。条件別margin、参照分離、較正、失敗時の `unknown`・`missing` を固定profileへ結び、open visual phraseをexact属性の一致・不一致へ変換しないこと。条件iのv4 scoreはanchorと条件i以外のcounterfactualを正例参照、条件iのcounterfactualを負例参照とし、全正例参照cosineの最低値と負例cosineのmarginを平均参照距離で正規化すること。同じbindingの4〜32候補だけをlabel-freeで条件別観測範囲へ写し、十分な幅とゼロ交差または複数の飽和端点支持がある条件だけ、観測中点をcenter、半幅をscaleとして共通decision threshold 0へ較正すること。条件名、category、正解label、固定類似語へ依存せず、候補不足、binding混在、片側連続分布はfail closedにすること。同一dataset・label・評価contract・20判定では未較正v4のaccuracy 0.85、pairwise AUC 0.93を、batch較正後に1.0、1.0へ改善したためdevelopment相対合格とすること。相対合格は独立holdoutへ進む資格だけとし、色・メッシュのclass不足、候補集合依存、outlier耐性、独立holdoutと本番Cloudflareの未確認を残すこと。相対合格だけで生成方式またはranking採用を変更せず、利用者が明示決定した現在の生成順はFR-403〜FR-405、暫定rankingはBACKEND 13.3節に従うこと |
| FR-421 | 一部実装（local ASGI API） | server-sideで登録した15分以内のsubmission capabilityだけから承認済み検索jobを冪等投入し、固定local ownerで状態取得・queuedまたはrunningの取消・未期限のschema 5.0履歴詳細取得を提供すること。HTTP応答へowner、承認token、binding、内部failure code、profile、既知accuracy、digest、score、画像body、生例外を含めず、loopback以外を拒否すること。server起動構成、最終承認controller、次期UI、認証、多利用者・複数process運用は別工程とする |

## 4. UI・CLI要件

2026-09-11にStreamlitを削除した。UI-001〜UI-007は旧画面の廃止済み要件で、Reactの要件へ流用しない。Reactはオフラインモック、実検索はCLIを入口とする。

| ID | 状態 | 要件 |
|---|---|---|
| UI-001 | 廃止（旧Streamlit） | Streamlitで検索条件を複数行入力できること |
| UI-002 | 廃止（旧Streamlit） | 1件から30件の範囲で表示件数を選べること |
| UI-003 | 廃止（旧Streamlit） | Bonsai疎通とOutscraper APIキー有無をサイドバーで確認できること |
| UI-004 | 廃止（旧Streamlit） | 総合、商品名、属性、価格の各スコアを表示すること |
| UI-005 | 廃止（旧Streamlit） | 価格、評価、画像、Amazonリンク、一致・不足・除外条件を表示すること |
| UI-006 | 廃止（旧Streamlit） | 詳細例外を画面へ出さず、固定の失敗メッセージを表示すること |
| UI-007 | 廃止（旧Streamlit） | 検索結果を現在のStreamlitセッションに保持すること |
| UI-008 | 一部実装（固定5項目の編集、日本語/英語検索語は未実装） | 意図、明示・推定価格、日本語・英語クエリを編集可能な第1確認画面を提供すること |
| UI-009 | 一部実装（固定画像モック、実画像生成は未接続） | 画像生成ON/OFFを既定OFFのトグルスイッチで切り替えること。背景はON `#3a83f7`・OFF `#424242`、つまみは `#ffffff` とし、共通の背景56×32px・つまみ直径24pxを使うこと。背景色とつまみの移動を240msの `cubic-bezier(0.22, 1, 0.36, 1)` で補間し、途中の再操作にも滑らかに追従すること。`prefers-reduced-motion: reduce` では即時に切り替えること。ラベル付きのネイティブcheckboxとswitchの役割、Space操作、無効状態を保つこと。先行1枚の確認・了承・作り直しと、了承後の条件別偽画像の生成・全体確認を区別すること。参考画像は了承済み表示、偽画像は変更条件を別枠に表示し、全画像にAI生成表示を付けること |
| UI-010 | 一部実装（モック最終確認、実検索は未接続） | 検索先、最大候補数、比較項目、この承認で商品検索を1回実行することを示す第2確認画面を提供し、送信parameterと外部APIの料金情報は通常画面へ表示しないこと |
| UI-011 | 一部実装（モックの失効・二重操作防止、server承認は未接続） | 変更、再生成、期限切れで旧承認を無効にし、明示承認なしの外部検索を拒否すること |
| UI-012 | 一部実装（固定商品の表示、実評価は未接続） | 条件との近さ、希望に合う点、確認できない点、避けたい条件への該当、参考画像利用の有無を表示し、raw score、component、weight、採用言語、内部画像scoreは通常画面へ表示しないこと |
| UI-013 | モック実装済み | ランキング結果を固定3件に切り捨てず、初期10件、1〜30件の範囲で表示件数を変更できること。表示件数変更で外部検索・正規化・採点を再実行しないこと |
| UI-014 | 一部実装（モックの確認・回復操作、実APIは未接続） | 画像拡大、先行1枚の作り直しと後続画像の失効・残り回数の確認、安全な検索中止、復元不能時の新規検索、サーバーが返せる場合だけ残り回数を示す外部処理の再試行を、用途に応じたLightbox、AlertDialogへ分離すること。待機画面には承認済みの条件、価格、検索先、比較候補の上限、参考画像利用の有無を読み取り専用の右側要約として常時表示し、郵便番号、お届け先、検索語、内部情報を含めないこと。検索語編集と商品カードの検索条件はページ内折り畳みを維持すること。商品名は実URLがある場合だけ商品ページへのリンクにし、モックではリンクにしないこと |
| UI-015 | 一部実装（タブ内履歴、server永続履歴は未接続） | 完了した検索を0件も含めて履歴へ保存し、空・読込・失敗・1件削除の各状態と保存済み結果を後から表示できること。履歴一覧の `削除`・`開く` は96×36pxに揃え、同じ行の左に `削除`、右に `開く` を離して配置すること。詳細と確認ダイアログは通常の176×48pxを保つこと。履歴操作で外部検索・画像生成・商品属性整理・採点を再実行しないこと |
| UI-016 | モック実装済み | 共通ヘッダー右側には検索履歴画面へ移動する `検索履歴` だけを追加し、設定ボタン、設定画面、設定用routeは初回実装の対象外とすること |
| UI-017 | モック実装済み | 次期UIをReact + StyleXで実装し、Figmaはレイアウトの参考とすること。色・文字・装飾・操作配置は [FRONTEND.mdの視覚統一契約](FRONTEND.md#13-次期uiの視覚統一契約) を優先すること |
| UI-018 | モック実装済み | Noto Sans JP、本文16px・補足14px・h1 40px・h2 32px・h3 24px・h4 20px、背景 `#000000`、指定のない文字・外枠 `#ffffff`、補足背景 `#212121`、指定のないハイライトなし、ウィンドウ角丸15pxを守ること。主要操作は右、危険操作は左に離し、実行・遷移ボタンの中央揃え・角丸100px・短い文言と種別ごとのホバー規則を満たすこと。ウィンドウ・カードとボタンは標準 `border-radius` の円弧とし、`corner-shape: squircle` は使わないこと。補足14pxの行高は24pxに揃え、枠位置への端数累積を抑えること。100%・DPR1のボタンとウィンドウで、角の輪郭の濃淡と直線1pxを画素で検証すること。トグルのつまみと進行表示の丸は真円を保つこと。通常の実行・遷移ボタンは幅176px・高さ48px、履歴一覧の `削除`・`開く` だけは96×36pxに揃え、トグルは別寸法とすること。基本・危険・進む/決定/保存のすべてで、通常寸法・小型寸法とも外枠の線幅を1pxにすること。すべての `削除` を危険ボタンとし、危険ボタンは外枠・文字 `#901010`・背景 `#000000`、ホバー背景 `#424242` とし、通常・ホバー・無効時とも文字と外枠の色を保つこと。進む・決定・保存は通常・無効・処理中も白背景・黒文字、操作可能なホバー時は黒背景・白文字とし、開発サーバーとビルド済み画面の両方で維持すること |
| UI-019 | モック実装済み | 中央上部の全体段階バーと商品調査内の工程表示を分け、完了した段階の丸は背景 `#3a83f7`・外枠 `#ffffff` とし、正本の白・青の配色、上半身の現在位置アイコン、完了チェック、現在工程の丸を表示すること。段階マーカーは現在44×44px・完了/未到達28×28pxで中心を揃え、商品調査アイコン36×36pxを保ち、白い丸枠を2pxのSVG strokeで描いて円周の欠けや線幅の不均一を抑えること。画像生成の光は右上から左下へ1.5秒間隔、調査中の丸は1.5秒周期、生成中・処理中の末尾の点は0.5秒間隔で循環し、完了・失敗時に止めること |
| UI-020 | モック実装済み | [オフラインモック](FRONTEND.md#14-オフラインモック) で任意の自然言語入力を保持し、固定の合成条件・商品・画像を使って条件確認、任意画像の生成・確認、最終確認、商品調査、結果表示まで操作できること。画像なし・戻る・二重操作防止を含め、共通のReact画面・StyleXを使うこと。画面更新・処理完了・段階遷移で先頭へ戻さず、見出しのフォーカス移動でも表示可能な範囲でスクロール位置を維持すること。ローカルのフォント・画像だけで動作し、実バックエンド・Bonsai・外部API・credentialを使わず、自動接続しないこと。モック利用中であることと実推論・実検索でないことを明示すること |
| CLI-001 | 実装済み | 自然文を位置引数として受け取ること |
| CLI-002 | 実装済み | 正の表示件数を指定できること |
| CLI-003 | 実装済み | 既存キャッシュを読まない実行を選べること |

## 5. データ・キャッシュ要件

| ID | 状態 | 要件 |
|---|---|---|
| DATA-001 | 実装済み | 内部データ境界をPydanticモデルで表すこと |
| DATA-002 | 実装済み | 属性、生レスポンス、正規化、採点を別namespaceへ保存すること |
| DATA-003 | 実装済み | 結果に影響する入力、設定、処理版をキャッシュキーへ含めること |
| DATA-004 | 実装済み | APIキーをキャッシュキーとpayloadへ含めないこと |
| DATA-005 | 実装済み | JSONを同一ディレクトリの一時ファイルから原子的に置換すること |
| DATA-006 | 実装済み | 属性と生レスポンスのTTLを設定できること |
| DATA-007 | 実装済み | 期限切れ、破損、モデル不一致をキャッシュミスとして再計算すること |
| DATA-008 | 廃止（旧Streamlit） | Streamlitのセッションごとのキャッシュキー分離。Python呼出元指定のscopeは維持する |
| DATA-009 | 一部実装 | 利用者間の保存データを分離すること。セッションscopeによるキー分離だけで、保存ルートとOSアクセス権は共通 |
| DATA-010 | 一部実装（strict domain・後半pipeline） | 次期フローのintent、query plan、image set、approval、raw product、normalized product、scoreを版付きstrict modelで分離すること |
| DATA-011 | 一部実装（未永続化） | 承認済み計画をcanonical SHA-256、利用者、session、15分期限、single-use tokenへ結び付けること |
| DATA-012 | 一部実装（offline orchestrationでruntime・provider・rankingをdigestへ結合、cache未接続） | prompt、schema、model、provider parameter、画像、ranking profileのdigestを結果とcache keyへ含めること |
| DATA-013 | 一部実装（offline変換・SQLite repository） | 完了した検索1回をimmutableな表示用履歴スナップショット1件として冪等に30日間保存し、再計算cacheのTTLから分離すること |
| DATA-014 | 一部実装（offline SQLite repository） | owner確認後の個別削除または30日の期限到達で、履歴項目、結果スナップショット、専有生成画像を一つの操作単位で物理削除し、部分削除を成功にしないこと |
| DATA-015 | 一部実装（local job SQLite） | 検索jobのbinding、状態、時刻、固定失敗code、結果locatorだけを30日間保存し、検索文、商品、approval token、provider本文、例外本文をjob DBへ保存しないこと |

論理スキーマは [DB-SCHEMA.md](DB-SCHEMA.md)を参照する。

## 6. セキュリティ要件

| ID | 状態 | 要件 |
|---|---|---|
| SEC-001 | 実装済み | `.env` とキャッシュをGit管理対象にしないこと |
| SEC-002 | 実装済み | Outscraper APIキーを `X-API-KEY` ヘッダーで送ること |
| SEC-003 | 実装済み | APIキー付きURLをHTTPSに限定すること |
| SEC-004 | 実装済み | 結果URLを設定endpointと同じホスト・実効ポートに限定すること |
| SEC-005 | 実装済み | APIキー付き要求でHTTPリダイレクトを拒否すること |
| SEC-006 | 実装済み | URL内のusernameとpasswordを拒否すること |
| SEC-007 | 実装済み | 検索語、要求URL、結果URL、APIキーを標準出力へ出さないこと |
| SEC-008 | 未実装 | 認証と認可により利用者ごとの検索・キャッシュアクセスを制御すること |
| SEC-009 | 方針確定（現行local productionでは設けない） | 現行のローカル単独利用ではper-user・session・day・costのquotaとレート制限を設けないこと。公開・複数利用者化する場合は認証・濫用対策とともに別要件として再検討すること |
| SEC-010 | 一部実装（mock server-side credential注入） | Bonsai接続設定をserver-sideに限定し、CloudflareとOutscraperのcredentialを分離してbrowser、Bonsai、生成promptへ渡さないこと |
| SEC-011 | 実装済み（同一process ledger・production無quota mode） | Bonsaiのcallとrequest・最大response byteに基づく保守的利用量、Cloudflare・Outscraperのcall・金額を送信前に記録し、失敗attemptも利用量へ含めること。本番では累計値による拒否を行わず、local Bonsaiへapplication output-token上限とHTTP timeoutを設定しないこと |
| SEC-012 | 一部実装（offline proxy service・spawn分離DNS・pinned-IP HTTPS transport） | 商品画像をHTTPS allowlist、redirect拒否、DNS/IP再検証、byte・pixel・timeout上限付きproxyで取得すること |
| SEC-013 | 未実装 | 外部商品文をuntrusted dataとして扱い、Bonsaiその他のLLMへ渡さないこと |
| SEC-014 | 未実装 | Outscraper live試験ごとに送信内容と費用を提示して人間承認を得ること |
| SEC-015 | 一部実装（offline repositoryのowner境界） | 検索履歴の一覧・詳細・削除でownerを検証し、session IDや公開用locatorを認可境界に使わないこと |

運用時の詳細は [SECURITY.md](SECURITY.md)を参照する。

## 7. 実行環境要件

- 本番環境はiGPUを使用する。4面画像生成のためのローカル3Dモデル生成は採用しない。開発機の専用GPUを本番の実行資源として扱わず、画像生成・視点変換は本番で実行可能な外部API方式で検討する。

- Python 3.11以上
- `uv` による依存関係管理
- 次期画像処理の対象運用環境はWindows 11 / WSL、Intel Core Ultra 9 288V。DNS process境界はGPU・NPUを使わず、`spawn` で共通化する。WSL2の固定失敗smokeは確認済みだが、Windows nativeでの実process・実DNSは未確認
- OpenAI互換APIとして起動したBonsai 8B
- 検索実行時のOutscraper APIキー
- キャッシュディレクトリへの書込権限
- OutscraperへのHTTPS通信

主要依存:

- Pydantic / pydantic-settings
- NumPy / ONNX Runtime 1.23.2（固定CLIPのCPU実行）
- Pillow
- requests
- scikit-learn / SciPy（領域maskの連結成分・距離変換）
- SudachiPy / sudachidict-core

開発確認にはpytest、Ruff、JSON Schema検証用のjsonschemaを使う。

属性別形状比較の任意CLIPSeg/MobileSAM抽出器は、後述のONNX CLIPとは別の実験環境を使用する。この抽出器に限り、repository外の固定PyTorch/Transformersと検証済みcheckpointを使用する。iGPUでの実行可否・速度は未確認。通常環境へモデル依存を追加せず、明示設定なしに起動しない。

次期検索フロー v2 はBonsaiを継続利用し、本番の参考画像・条件別偽画像生成にはCloudflare、画像類似度には固定したCLIP model assetsを使う。gpt-imageは画像評価テストだけに使い、製品adapter、credential、承認・利用量・state・cacheへ接続しない。PillowとNumPyは固定画像前処理、ONNX Runtime 1.23.2はCPU推論のdirect dependencyとしてlock済みである。CLIPの605,804,513 bytesの `model.onnx`、456 bytesの設定、468 bytesのupstream前処理設定はrepository内の専用directoryへlocal assetとして配置し、3 fileのbyte数とSHA-256をload前後に検証する。applicationは縦横比を維持して画像全体を224×224内へ収め、正規化後0となるモデル平均余白を使う固有profileをruntime digestへ結ぶ。upstream assetのbyteは変更しない。PyTorch・Transformers・pickle weightは導入しない。合成画像、受領1組、case1からcase3、EXEC-064の実商品候補によるWSL CPU推論は確認済みで、適格なcategory-only 2条件は1 pass・1 failだった。assetのGit配布、Windows native、複数カテゴリ・複数条件のranking本評価、Cloudflare実生成は未確認で、画像rankingは無効である。

## 8. 非機能要件

### 8.1 信頼性

| ID | 状態 | 要件 |
|---|---|---|
| NFR-001 | 実装済み | 外部API要求にタイムアウトを設けること |
| NFR-002 | 実装済み | Outscraperの一時障害を上限付き指数バックオフで再試行すること |
| NFR-003 | 実装済み | JSON書込中に完成ファイルを部分状態へしないこと |
| NFR-004 | 実装済み | 外部APIの失敗と正常な0件を区別すること |
| NFR-005 | 未実装 | 複数プロセスで同一キーへ安全に同時書込できること |

### 8.2 保守性

| ID | 状態 | 要件 |
|---|---|---|
| NFR-101 | 実装済み | UI、統合処理、外部通信、変換、保存、モデルをモジュール分割すること |
| NFR-102 | 実装済み | リポジトリルート基準でファイルパスを解決すること |
| NFR-103 | 実装済み | 現行 `src` を直接importする回帰テストを持つこと |
| NFR-104 | 実装済み | 外部通信を行わず単体テストを実行できること |
| NFR-105 | 実装済み | 現行処理が参照する設定可能な運用値を `Settings` へ集約すること |

### 8.3 性能・可用性

| ID | 状態 | 要件 |
|---|---|---|
| NFR-201 | 実装済み | 同一条件の高コスト処理をキャッシュで省略できること |
| NFR-202 | 一部実装 | 外部処理に上限を設けること。要求タイムアウトとポーリング上限はあるが、処理は画面要求内で同期実行 |
| NFR-203 | 一部実装（local HTTP API） | ローカル単独利用では承認済み暫定検索をbackground workerへ冪等投入し、local ASGI APIから状態照会、協調的取消、成功履歴locatorと表示用履歴詳細を提供すること。server起動構成、最終承認controller、UI接続は別工程とする |
| NFR-204 | 一部実装（local worker 1件） | ローカル単独利用の同時実行上限を1件に固定すること。公開・複数process運用のSLOと可用性目標は別途定義する |
| NFR-205 | 一部実装（承認・後半snapshot） | 次期検索フローの条件確認、先行参考画像の了承、後続生成物の確認、商品検索の最終承認、外部API状態、再生成、取消、期限切れを再開可能なstate machineとして提供すること |
| NFR-206 | 実装済み（quota有効・無効を型で分離） | Bonsaiの呼出し数・request byteと最大response byteに基づく保守的予約量、Cloudflare・Outscraperの呼出し数・費用・失敗を検索単位で追跡すること。本番policyはquotaを無効にして累計値による拒否を行わず、操作単位のcall・候補・poll・byte・timeout・retry契約およびBonsaiのmodel生成token境界とは分けること |
| NFR-207 | 一部実装（offline spawn process境界） | 商品画像のOS名前解決を親processから終了できる子processへ隔離し、application deadlineと回収上限を設けること |
| NFR-208 | 一部実装（全体保持profile・WSL CPU実model・case1本評価・case2診断） | 固定CLIP推論を最大4枚の有界入力とbyte戻り値だけを使う `spawn` 子processへ隔離し、application deadline、CPU provider、terminate・killを固定すること |

### 8.4 観測可能性

| ID | 状態 | 要件 |
|---|---|---|
| NFR-301 | 一部実装（v2 mock HTTP・後半state） | 処理段階、request ID、ポーリング状態を診断できること |
| NFR-302 | 未実装 | 構造化ログ、相関ID、メトリクス、トレースを提供すること |
| NFR-303 | 未実装 | API利用量、待機超過、キャッシュ破損を監視・通知すること |

## 9. 設定検証要件

起動時に次を満たさない設定を拒否する。

- タイムアウト、取得件数、最大試行、最大ポーリング、TTL、表示件数が正数
- retry backoffが0以上
- Bonsai temperatureが0以上2以下
- 商品名、属性、価格の総合係数がそれぞれ0以上1以下で合計1.0
- 条件語重みが0以上で、少なくとも1つが正

Outscraper endpointのHTTPS・ホスト・URL内認証情報は検索実行時、APIキー送信前に検証する。

## 10. 受入確認

依存環境を `uv sync --locked` で準備した後、外部通信を許可しない基本確認:

```sh
uv lock --check --offline
uv run --frozen --offline --no-sync ruff check .
uv run --frozen --offline --no-sync ruff format --check .
uv run --frozen --offline --no-sync pytest -m 'not live_api'
git diff --check
```

手動確認:

- Reactオフラインモックが起動し、入力から固定結果・履歴まで操作できる
- CLIの `--help` がリポジトリ外のカレントディレクトリからも動く
- 実Bonsaiを使う場合は `/models` と属性抽出が成功する
- request v8とprompt cacheを確認する場合は、別承認のlocalhost結合testで異なる合成入力2件を各1回だけ送り、両方のbounded compact応答から完全strict intentへの復元成功と2件目の正の `cached_tokens` を確認する
- 応答時間を診断する場合は通常のBonsai live testと排他の別承認testで、同じ固定合成request v8を2回だけ送り、boundedなprompt・cache・completion token数とllama.cppのprompt・generation時間を本文非保持で分離する
- 実Outscraperを使う場合はキー、利用料金、取得件数、タイムアウトを事前確認する

単体テスト成功を実外部サービスとの結合確認として報告してはならない。

## 11. 現行スコープ外

次は要求が明示され、設計・実装・テストが追加されるまでプロダクト要件に含めない。

- ComfyUI連携
- SSHによる別ホスト実行
- 独自REST / GraphQL API
- アカウント、認証、認可、課金
- RDB、検索エンジン、オブジェクトストレージ
- 公開・複数利用者・複数process向けの分散ジョブ実行
- Docker、systemd、クラウド配布、自動デプロイ（CD）

Cloudflareによる参考画像・偽画像生成と画像特徴を含む次期検索フローは明示要求済みであり、現行スコープ外候補ではない。既存のCloudflare向けmock HTTPとJPEG・PNG・WebPからRGB PNGへの合成画像正規化境界は本番providerのoffline実装だが、修正後のCloudflare実生成、画像品質合格、現行機能への接続を意味しない。gpt-imageは画像評価テスト専用である。利用者向けの操作は [SEARCH-FLOW.md](../SEARCH-FLOW.md) を参照し、全体実装完了までは現行機能として表示しない。

大規模・小規模な作業と進行中Planは [GOAL.md](GOAL.md#統合済み大規模タスク一覧)、Plan規約は [DEVELOPMENT.md](DEVELOPMENT.md#統合済みexecution-plan規約) で管理する。

## 12. 本番移行時の追加要件（未実装）

公開・複数利用者運用へ進む場合は、最低限次を実装・検証する。

1. 認証、認可、利用者またはテナント単位のデータ分離
2. 同時実行数、Outscraper利用量・費用の観測と異常通知。本番の利用量・費用quotaは設けず、必要になった場合だけ別要件で再検討する
3. Web要求を長時間占有しないジョブ実行方式
4. キャッシュの容量上限、保持・削除方針、破損時の運用
5. シークレット、ログ、キャッシュの保存・アクセス方針
6. 構造化ログ、相関ID、メトリクス、アラート
7. サポートPython版のCI成功と必須チェックの設定（ジョブ定義は追加済み）
8. 代表検索と期待順位を固定したランキング評価
9. 障害復旧、バックアップ、配布、ロールバック手順

これらは完了するまで「本番対応済み」と表現しない。


## 統合済み制約

> 統合元: `docs/CONSTRAINTS.md`。統合前の文書は `bin/docs/old/` に保存する。


> **標準文書との関係:** 満たすべき要件と受入条件は [REQUIREMENTS.md](REQUIREMENTS.md) を入口とする。この文書は実行環境、外部サービス、同期処理、運用上の限界を詳細化する。

### 1. 文書の目的

この文書は、amazon-explorer の現行実装を利用・変更するときに前提とする技術的、運用上、データ上の制約をまとめる。制約を解消する提案は現行機能ではなく、[TECH-DEBT-TRACKER.md](ISSUES.md#統合済み技術的負債トラッカー)、[ISSUES.md](ISSUES.md)、[TASKS.md](GOAL.md#統合済み大規模タスク一覧)で管理する。承認済みで基盤を一部実装した次期検索制約は [SEARCH-FLOW.md](../SEARCH-FLOW.md) も参照する。

### 2. 実行環境

- Python 3.11以上を対象とする。
- 依存関係は `uv` と `uv.lock` で管理する。
- `pyproject.toml` は `package = false` であり、現行用途はリポジトリからの直接実行である。
- 次期画像処理の対象運用環境としてWindows 11 / WSL、Intel Core Ultra 9 288Vを確認した。DNS境界はCPUだけで動く明示的な `spawn` を使い、親processのapplication deadlineを5秒とする。現在のWSL2では外部DNSを呼ばない固定失敗smokeまで確認した。Pythonの `Process.start()` 自体をpreemptできないためWindows nativeの起動時間・終了動作は未確認であり、実運用前に別途確認する。
- CLIを動かすホストから、BonsaiとOutscraperへ接続できなければならない。
- キャッシュを使うかどうかにかかわらず、新しい結果を保存するため `CACHE_DIR` への書込権限が必要である。
- 現行作業ツリーの決定論的GitHub Actions CIはPython 3.11 / 3.13を対象とする。変更後のGitHub実行は未確認であり、変更前のCIで検出した権限・ACLへのテスト依存は修正し、通常ユーザーとACL付き元Pythonのローカル環境で対象195件が成功した。SSLモックと環境変数の期待値はローカルで修正・検証済みである。コンテナ、systemd、クラウド配布の定義はない。

### 3. 外部サービス

#### 3.1 Bonsai

- OpenAI互換の `/v1/chat/completions` と `/v1/models` を提供するBonsaiサーバーを別途起動する必要がある。
- 既定URLはローカルの `http://127.0.0.1:8080/v1` であり、TLSを前提にしない。
- 属性抽出POSTには60秒の既定タイムアウトがあるが、再試行はない。
- 疎通確認は3秒で、検索要求の成否を保証しない。
- LLM出力は非決定的になり得る。temperature、モデル、プロンプトをキーに含めても、外部モデル実装自体の変更は自動検出できない。

#### 3.2 Outscraper

- 検索実行には有効なAPIキーと外部HTTPS通信が必要であり、利用量に応じた料金が発生し得る。
- APIの仕様、状態文字列、レスポンス項目は外部サービスの変更影響を受ける。
- 1要求のタイムアウトは検索全体の上限ではない。各ポーリングで最大試行回数分の通信時間があり、その間にポーリング待機も入る。
- `OUTSCRAPER_LIMIT` はアプリから送る上限であり、実際の取得件数や品質を保証しない。
- HTTP 429、5xx、Timeout、ConnectionErrorだけを再試行する。`Retry-After`、ジッター、回路遮断はない。
- endpointと結果URLはHTTPS・同一originへ制限されるため、異なるホストへ結果を配布する互換APIはそのまま利用できない。

#### 3.3 為替

- USDからJPYへの換算は既定160円の固定値である。
- 実勢レートを取得せず、取得時刻やレート出典も保存しない。
- `price_jpy` が円換算済みでも `currency` は元の検出通貨 `USD` のままになり得る。

#### 3.4 次期検索フローの外部サービス（一部実装）

strict intent、固定Bonsai v2 prompt・schema 8.0 canonical request・非空のbounded compact生成schema・本文非保持で正規化と検索不能を区別する段階診断・1-call execution、Cloudflare・Outscraperのbounded Requests transport、4方向画像、Outscraper task・polling、観測値だけの商品正規化、型付き条件・証拠裁定、固定ONNX CLIP、schema 3.0の第1確認・承認・state・`typed-ranking-v4` 後半pipeline、schema 2.0のtyped表示履歴・SQLite `user_version=2` repository、本文非保持のholdout評価契約、安全重視の固定acceptance policy、4段階のholdout後処理diagnosticとquery-less blocking投影、非blocking intentの検索可能性検査は、相互のdigestを再検証するoffline境界として存在する。Bonsai requestは固定promptだけをsystem messageへ置き、検索可能な最大12種類の固定fieldと確認待ち `ambiguities` を別branchにし、文字列・配列上限を持つcompact生成schemaを `response_format.schema` へ含める。完全schemaはmodelへ重ねず別digestとstrict最終検証に維持し、wireで省略したnull、空list、価格既定値は完全19-field draftへ決定的に復元する。applicationの生成token上限とHTTP timeoutを持たず、1 MiB response上限とretry禁止を維持する。blocking proposal、旧2.0検索artifact、旧Bonsai request v2〜v7、ranking-v3 runtime、旧SQLite version 1は新契約へ暗黙変換しない。case1からcase3は設計用development setであり、case1の事前AUC基準は未達、case2・case3には候補と独立した4方向参照がない。localhost Bonsaiを使った最初の適格holdoutは4件全てがstrict応答検証に失敗し、失敗を除外しない固定assessmentで `fail` となったため、条件分解の意味品質と商品順位は未測定である。同じCSVをrequest v3で再利用したdevelopment regressionも4件全てが旧300秒timeoutで失敗した。時間上限なしのrequest v4は4件全てでHTTP応答まで完了したが、schemaなしの `json_object` 宣言がllama.cppのJinja生成grammarを有効化せず、全件 `content_not_json` で失敗した。EXEC-046では完全schemaから `pattern` だけを除いた非空schemaを生成制約へ追加し、完全schemaのstrict検証を維持した。EXEC-047の初回request v5実行はport listenだけを起動条件にしてmodel ready前に失敗したが、新しい明示承認後のhealth-ready再実行では4件全てがHTTP 200かつstrict intent検証を通過し、request v4の `content_not_json` は解消した。その後は評価用一時runnerの後処理で4件とも失敗し、typed proposalの最終状態と商品ranking品質は未測定である。後処理失敗を除外しないassessmentは `fail` だが、独立holdoutや未知データの合格証拠ではない。EXEC-048では再推論前に、typed proposal、query plan、typed ranking、prediction projectionの本文非保持diagnosticを固定し、上流blocking ambiguityをquery planなしのblocking予測へ投影できるようにした。段階診断付き部分再計測では完了2件が `query_plan_invalid`、3件目が中断、4件目が未送信となり、dataset assessmentは生成していない。実2件の直接原因は復元せず、EXEC-049で同じstageを生む非blocking intentの検索可能性contractをoffline修正した。EXEC-050では更新promptの先頭1件・合計1 callだけを明示承認後に実行し、HTTP 200後の受理前に `intent_normalization_invalid` で停止した。実行時のstageでは直接原因を区別できなかったため、追加推論なしで検索不能を `intent_searchability_invalid` へ分離した。2件目、再試行、dataset assessmentは実行していない。現行orchestratorの上流blocking処理も未接続である。EXEC-057のrequest v6は、Core i5-13600KF・WSL2・CPU版で出力1 tokenのprompt処理benchmarkを行い、変更前相当cache無効中央値142.56秒に対してcache warm中央値1.236秒を確認した。ただしfull JSON生成、strict intent成功、Core Ultra性能、production E2Eは未確認である。Cloudflare・Outscraper、運用allowlist・実画像host、Windows native、画像ranking、legacy現行検索からの履歴保存、認証、API・UIは未実装・未確認である。

EXEC-058では、request v6のfull JSON 2 callsをactual Requests transportとstrict adapterへ通し、2件目のprompt cache hitを検査する二重opt-in localhost runnerを実装した。明示承認後のCore i5-13600KF・CPU版実行では2件ともfull JSON・strict intentに成功し、2件目は925 prompt tokens中891 tokens、約96.3%をcacheから再利用した。入力とcompletionが異なるためwall時間差はcacheの速度差を示さず、Core Ultra性能も未確認である。

EXEC-059では、同じ固定合成request v6を2回だけ送る専用selectorと、llama.cpp応答からprompt処理・completion生成のtoken数と時間をstrictに投影する本文非保持境界を追加した。通常のBonsai live testとは排他で、2 callsを超えない。新しい明示承認後のCore i5-13600KF・CPU版実行では、両方487 completion tokensでfull JSON・strict intentに成功した。2件目は923 / 924 prompt tokensをcacheし、prompt時間を43.655秒から0.124秒へ353.47倍・99.72%短縮、wall時間を137.311秒から90.440秒へ1.52倍・34.13%短縮した。warm wallの99.82%はcompletion生成であり、Core Ultra性能は未確認である。

EXEC-060では、request v7のprovider wireだけをcompact化した。既定のnull、空list、価格なし、固定JPYと非該当価格fieldを省略し、受信側で完全19-field draftへ復元して既存のstrict validationを行う。代表fixtureはlocal Bonsai tokenizerで126 tokensとなり196-token目標を満たしたが、`max_tokens=196` は設定していない。後続の明示承認済みlocalhost診断ではv7を実modelへ送信したが、365.12秒で応答未完了のため手動停止した。server内の生成継続までは確認したが、completion token数、strict結果、意味品質、応答時間の改善率、Core Ultra性能は未確認である。追加live実行には新しい条件提示と明示承認が必要である。

EXEC-061では現行requestをv8へ更新し、検索可能応答を最大12種類の固定field、確認待ち応答を
`ambiguities` 1 fieldへ分けた。商品名等48文字、term 32文字、各term list・typed condition・set値4件、
ambiguity 2件・各96文字をcompact modelと生成schemaの両方で強制する。llama.cpp converterはこれらを
有限反復へ変換し、除外fieldをroot grammarへ含めない。代表fixtureは104 tokensである。後続の明示承認済み
localhost診断では同一固定入力2 callsがともに254 completion tokens・strict intent成功となり、Core
i5-13600KF CPU版のcold wallは53.148秒、warm wallは17.625秒だった。意味品質、未知入力のstrict成功率、
Core Ultra性能は未確認である。

別の承認済み固定合成入力1 callでは50.628秒・82 completion tokensでstrict intentまで成功したが、価格、色、
除外条件を欠落し、入力にないstyleを不正なvalue typeで生成したためtyped proposalはblockingとなった。後続の
offline修正では、入力を語彙非依存の原子的条件へ分け、未知語を原文termsへ保持し、割当不能時はblockingへ戻すよう固定promptへ要求し、typed
attributeを6 value type branchへ生成時に結び、adapterでも同じprofileを再検証する。同一入力のrequest bodyは
15,032 bytesから14,859 bytesへ減り、203-byteのready compact fixtureとpromptに存在しない日英3組の合成語彙はquery planまで通過した。修正後の
承認済み1 callは53.595秒・248 completion tokensでstrict intentへ到達したが、価格・除外条件欠落と入力にない
typed conditionによりblockingで停止し、Outscraperは呼び出していない。追加callなしで、入力中の原語・trusted
aliasに根拠を持つtyped candidateだけを実行条件へ残し、不正candidateのうち入力に現れる値を自由語termへ戻す
adapter境界を追加した。明示JPY上下限と「不要・除外・避ける・without」の対象も商品語彙に依存せずsourceから
復元する。取得済み応答相当fixtureはquery planまでreadyとなる。後続の承認済み1-call localhost再実行では、固定合成入力の
未知語2種、5,000〜10,000円、除外対象、二重否定拒否、strict intent、ready proposal、query planの全判定が成功した。
83.398秒、902 prompt tokens、290 completion tokens、response 1,895 bytesで、retryと後続provider callはない。
これは単一development regressionであり、未知入力全般または実商品検索の合格証拠ではない。

その後の別の明示承認により、固定合成queryを次期Outscraper HTTP境界へ1回だけ送った。task作成1回・自動retry 0、同一taskのpoll 9回、251.795秒で候補24件を受信し、24件すべてが応答契約と観測値だけの正規化契約を通過した。生応答、商品本文、商品URL、ASIN、provider request ID、APIキーは保存・出力していない。この結果は実Outscraper接続と正規化の単一互換確認であり、Bonsaiからの一続きのE2E、条件充足、順位品質、UI、production運用、実請求額を合格扱いにしない。
後続の一続きE2E第1段階では、承認済みlocalhost Bonsai 1 callがstrict intentへ到達したものの、無根拠の商品名と明示条件欠落を検出したため、Outscraperを呼ばずに停止した。adapterは商品名、brand、model number、自由語termをSudachiPyの完全なsource spanまたはASCII語境界へ照合し、根拠のない値をqueryへ渡してはならない。商品名が残らなくても、入力に根拠のあるbrand、model number、required term、preferred termのいずれかが残ればquery planを作ってよい。肯定検索語が1つも残らず、価格・除外語しかない場合はblocking確認へ戻さなければならない。JPYの数値抽出は正しい3桁comma区切りを許可し、不正な区切りへ部分一致してはならない。この境界はproviderが省略した全条件の復元を保証しない。

SudachiPyが日本語検索語を連続する接頭辞と内容語へ分ける場合、queryとrankingの共通tokenizerは接頭辞を捨てず、直後の内容語へ結合しなければならない。接尾辞も除外せず、文字位置が連続する直前の語と元の表記で結合して保持しなければならない。商品名が検索queryやBonsai入力へ渡る際に接尾辞を欠落させず、再解析でも保持する。助詞・句読点は従来どおり検索tokenへ含めない。
日本語のsource groundingと否定対象はSudachiPy `SplitMode.C` の全形態素、品詞、NFKC/casefold済みsource offsetを用いて抽出し、
trusted aliasを連続する完全な形態素spanにだけ一致させる。未知複合語内の部分一致、格助詞より前の語の巻き込み、
「不要ではない」の二重否定を拒否する。JPY数値だけは有界な正規表現を併用し、関係語は形態素spanから判定する。

EXEC-051の承認済み先頭1件は旧生成schemaで `draft_schema_invalid` となり、正規化・検索可能性・rankingへ到達しなかった。追加推論なしで、ambiguity code pattern、同値のconverter互換decimal pattern、価格mode・source別9 variantを生成schemaへ固定し、本文非保持のdraft違反groupを追加した。EXEC-052ではその生成schemaを同じ先頭1件・合計1 callで確認し、完全draft schemaと正規化を通過した後の `intent_searchability_invalid` で停止した。追加推論なしで通常経路の商品種別または全blocking確認待ちを生成時に強制し、検索不能を `missing_terms`・`invalid_terms` の固定groupへ分ける次schemaを実装した。この次schemaの実model確認は未実施であり、同じcaseでも新しい明示承認を必要とする。

EXEC-053ではその次schemaを新しい明示承認後に同じ先頭1件・合計1 callだけで確認し、strict intentとtyped proposal生成まで成功した。proposalは `blocking` であり、2件目、retry、assessment、商品取得、rankingは実行していない。本文非保持のためblocking理由は断定しない。この時点で次の作業になったquery-less blockingのorchestrator接続は、後続のEXEC-054で実装した。

上段に残るorchestrator未接続の記述は各development regression実施時点の履歴である。EXEC-054で、typed proposalをqueryより先に確定し、blockingはquery planとquery digestを持たない専用第1確認へ返すoffline境界を実装した。blocking確認から画像生成または画像なし続行へ進む操作は追加provider予約前に拒否し、ready確認のquery必須契約は維持する。

EXEC-055ではその経路をlocal Bonsaiの実応答1件へ結合し、HTTP 200、transport call 1、`BlockingIntentReview`、query plan・query digestなし、後続provider予約なしを確認した。使用済みdataによる単一case確認のため、品質採否には使わない。

2026-09-07に利用者が2026-09-05の停止判断を撤回し、画像の未知データ評価を再開した。EXEC-064の初回は候補不足で不適格だったが、後続category-onlyの単一条件はfixed基準を `pass` した。typed rankingの意味品質とカテゴリ横断再現性を合格扱いにせず、画像rankingを有効化しない。次回も別の明示承認と未使用の適格dataを必要とする。

- Bonsaiは現行と同じローカルLLM境界として維持し、本番Cloudflare、テスト用gpt-image、Outscraperをそれぞれ別credential、別利用上限、別障害境界として扱う。gpt-imageを製品経路へ接続しない。
- gpt-imageの4方向画像は同一性、仕様の正確性、seedによるbyte再現を保証しない。
- 現行フローは先行1枚が1 call、了承後の偽画像がexact N calls（視覚条件Nは1〜3）である。通常2〜4 calls、先行画像の作り直し1回と両回の後続生成を合わせて最大8 calls。同じ了承から後続生成を再実行しない。旧4方向adapterは互換・診断用だけに残す。
- 画像生成は商品検索ではなく利用者の意図確認を補助する。生成画像を実在商品の証拠にしない。
- CLIP image-to-image類似度は本用途で品質保証されていないため、固定評価を通すまでranking weightを有効にしない。
- BonsaiのJSON textをstrict検証しても、意味上の誤推論やモデル更新による変化は排除できない。固定fixtureで品質を評価する必要がある。
- request v8は固定promptだけをsystem messageへ置き、検索可能な最大12種類の固定fieldと確認待ちの `ambiguities` だけを別branchにしたbounded compact wire、文字列・配列上限、ambiguity code pattern、同値のconverter互換decimal pattern、価格をmode・source別8 sparse variantへした非空の生成schemaでllama.cppの生成grammarを有効化する。完全schema本文はmodelへ重ねないが、content全体のJSON parse、完全schema digest、完全19-fieldへの復元とstrict Pydantic検証はapplication境界で引き続き強制し、生成用schemaだけを満たす値を受理しない。
- localhost Bonsaiへ送信する前に、process生存とloopback listenだけでなく、検索文を含まない `/health` がHTTP 200であることを確認する。llama.cppはmodel loadより先にlistenを開始し、ready前は503を返すため、port listenだけを送信可能の根拠にしない。
- gpt-imageとOutscraperの料金、quota、model availabilityは変更され得るため、live実行前に公式資料と承認済みpricing policyを再確認する。

### 4. 同期実行と可用性

- `run_product_search()` は同期関数である。
- CLIはOutscraperのポーリング完了まで同じprocess内で待つ。
- `src/search_v2/search_job.py` には、固定local owner、SQLite状態、同時実行1件、重複投入防止、状態照会、協調的取消を持つ単一process用job境界がある。`production_search.py` は承認済み暫定検索をOutscraper、商品画像、固定CLIP、ranking v5、schema 5.0履歴へ接続し、成功履歴locatorだけをjobへ保存する。これはoffline fixtureで確認したbackend接続であり、現行CLI、API、Reactフロントエンドへは未接続である。
- process再起動後は復元できないactive jobを固定終端へ移し、暗黙に再実行しない。実行中callbackの強制停止、詳細進捗API、自動再開は提供しない。
- ローカルjobのworker数と同時実行上限は1件である。複数利用者、複数process・host、サービスレベル目標は定義していない。
- Reactモックの進行中状態は再読込で初期化され、タブ内履歴はタブを閉じると失われる。

### 5. キャッシュと永続化

- 現行の再計算cacheはローカルJSONだけを使う。次期検索履歴には別fileのローカルSQLite version 2 repositoryがあり、次期offline検索結果からの保存境界へ接続済みだが、legacy現行pipelineへは未接続である。旧version 1 DBは自動変換せず変更前に拒否する。
- legacy JSON書込は原子的置換だが、複数プロセス間のロックはない。検索履歴repositoryも複数worker・共有DB運用を保証しない。
- 同じキーへ同時に書いた場合の勝者決定、競合検知、トランザクションはない。
- 属性と生レスポンスのTTLはファイルmtimeで判断する。
- 期限切れファイルを自動削除しない。
- 正規化・採点キャッシュは時間ベースのTTLを持たず、キーが一致する限り再利用する。
- 容量上限、LRU、定期掃除、破損隔離、バックアップ、復元手順がない。
- legacy cacheには共通のschema version、作成時刻、期限、整合性チェックサムを持つエンベロープがない。検索履歴repositoryはDB `user_version=2`、UTC完了・期限、typed ranking profile、商品ごとの必須状態、表示JSONのSHA-256を別に持つ。
- キャッシュを無効にしても読込だけが止まり、新しいファイルは保存される。

詳細は [DB-SCHEMA.md](DB-SCHEMA.md)を参照する。

### 6. 利用者分離とプライバシー

- 認証と認可はない。
- Python呼出元指定のcache scopeはキー分離であり、アクセス制御ではない。
- すべてのlegacy cache scopeが同じ `CACHE_DIR` とOSユーザー権限を共有する。検索履歴repositoryは論理ownerで全操作を絞るが、認証主体の解決やownerごとのOS領域を提供せず、同じ実行userのDB fileを共有する。
- CLIは常に既定scope `local-cli` を使うため、同じ入力・設定を別実行でも再利用する。
- キャッシュには利用者条件、商品情報、URL、条件一致が平文JSONで保存される。
- legacy cacheの保持期間、削除要求、利用者同意、監査方針は定義していない。検索履歴だけは完了から30日で非表示・物理削除するoffline境界を持つが、schedulerと運用監査は未実装である。
- ファイル暗号化はない。共有ホストではOS権限で保護する必要がある。

### 7. データモデル

- `ProductAttributes.price_preference` はモデル上の列挙型ではなく、任意文字列を受け付ける。
- 属性の各語句リストはモデル上の件数上限を持たない。プロンプト上の件数指示だけでは保証にならない。
- `ProductAttributes` を属性抽出サービス以外から直接作ると、価格の正数化、上下限入替、カテゴリ根拠確認を経由しない。
- `NormalizedAmazonProduct` はURLスキーム、URLホスト、文字列長、評価範囲、件数の非負性をモデル制約にしていない。
- 商品価格0は正規化モデルへ入り得るが、ランキング時には無効価格として扱われる。
- Outscraperの `data` が想定外の入れ子構造の場合、1段を超えて展開しない。
- 重複判定はASIN、短縮URL、商品URL、タイトルのいずれか1つであり、同一商品の表記ゆれを完全には統合できない。

### 8. 属性抽出

- JSON object候補は最初の `{` から最後の `}` までを単純に切り出す。複数objectや前後に波括弧を含む説明がある応答には弱い。
- カテゴリの根拠確認は、日本語では部分文字列、英語では3文字以上の単語集合包含というヒューリスティックである。
- 日本語検索語は日本語文字を含む商品名、色、特徴、カテゴリを結合して再構成する。
- プロンプトが求める `cheap` / `premium` / `none` をコード側のモデルで強制しない。
- LLMの推定価格帯は事実データではなく、価格スコアの参考値である。

### 9. 正規化

- 数値文字列は最初に現れる数値だけを採用する。範囲表現や複数価格を意味どおりには解釈しない。
- JPYの小数部分とUSD換算後の小数部分は整数化時に切り捨てる。
- 通貨が空で価格文字列にも通貨表現がなければ、数値をJPY相当として扱う。
- `data` がリストでなければ正規化関数単体は0件を返す。通常パイプラインではOutscraperクライアントが完了レスポンスのリスト形状を先に検証する。
- 画像URLと商品URLは外部レスポンスの値を表示モデルへ移すだけで、スキームや送信先を検証しない。

### 10. ランキング

- TF-IDFは固定学習済みモデルではなく、毎回クエリと取得候補集合から語彙とIDFを作る。同じ商品でも候補集合が変わればスコアが変わり得る。
- 日本語はSudachiPy SplitMode Cで名詞、動詞、形容詞、形状詞を使う。この形態素解析と辞書版に結果が依存する。
- 語句一致は部分文字列または分割語の包含であり、意味理解、否定文脈、語順を扱わない。
- 属性スコアはTF-IDFと条件一致率の最大値であり、統計的に校正された確率ではない。
- 総合重みと否定ペナルティは手動設定値であり、代表検索データによる評価・最適化は未実施である。
- `required_terms` は名前に反して候補を除外するハード条件ではなく、ランキング上の高い重みである。
- 価格が不明なら価格スコアは0、価格指定がなければ既定0.5であるため、価格欠損の影響が残る。
- 評価・レビュー件数・Prime・配送・元検索順位はCLIには表示しない。これらはlegacy現行経路の総合スコアには使わない。

次期ranking v3は現行rankingと分離されている。候補集合に依存するTF-IDFを使わず、日英token coverage、providerが構造化fieldとして返した観測属性、strict price modeを固定profileで採点する。さらに平均4.0以上のratingだけを高評価として `rating / 5.0` へ正規化し、総review countを `min(1, log1p(count) / log1p(1000))` へ写像して積をreview quality scoreとする。base weightはtitle 0.35、attributes 0.30、price 0.20、disabled image 0.10、review quality 0.05であり、review qualityを唯一の最小値にする。ratingまたはreview countが未観測なら0点とせずcomponentをweightから除外し、同点をOutscraper response indexで固定する。画像componentは無効である。画像scoreは色、外観形状、商品種別など画像で確認できる特徴だけの補助評価とし、商品仕様を表す構造化属性を推定、補完、上書きしない。有線・無線は商品名と構造化された観測属性で判定する。全体保持profileによる単一条件31枚のcharacterizationはpairwise AUC 0.759259259で事前基準0.80へ未達だった。接続方式だけが異なるf2・f4・f7・f10を画像上の正例へ再分類した視覚的特徴限定の評価は、正例13枚・負例14枚の全182組中169組が正順で、AUC 0.928571429、正例中央値0.941192911、負例中央値0.874694884となった。これは固定scoreの責務別characterizationであり、未達baselineを置換せず、画像rankingの有効化を意味しない。near 13枚の目視では全て黒いマウスと判断し、11枚はゲーミング用途、n5・n6は用途未知として固定した。静止画像だけでは接続方式を確定できないため、near 13枚の接続方式は全て未知とする。全体保持profileで用途未知候補の平均scoreは0.940557105であるため、scoreから属性を補完しない。複数queryの代表dataset、near属性の商品仕様による独立検証、検索文から得た4方向参照、現行pipeline・UIへの接続は未実施である。

`typed-ranking-v4` は、同じ固定weightのattributes 0.30だけを、trusted registryの条件weightを固定分母にしたtyped attributesへ置き換える。required・preferredの `match` とexcludedの `mismatch` だけを加点し、`unknown`・`conflict` を分母から外さない。必須状態、required一致率、preferred一致率、v4総合score、response indexの順で全候補を並べるため、明示的な必須不一致をtitle・価格・レビューで逆転させない。title、price、review quality、negative matchはv3の決定的計算を再利用するが、v3の自由語attributes score・言語・一致語・不足語は持ち込まない。schema、profile、batch digestはv3と分離し、blocking proposalは商品証拠またはsource rankingを始める前に拒否する。schema 3.0の第1確認、承認、state、`product_pipeline.py`、orchestrationへ同じproposalを結び、schema 2.0のSQLite表示履歴へ必須状態と限定した判定理由を保存する。legacy現行検索、cache、API、UIへは未接続であり、合成fixtureによる契約確認は実Bonsaiやproduction順位の品質を示さない。

case2では「筒状・長い・縦・金属製・収納、追加で四角い・黒い」の11候補について、視覚特徴と構造化特徴、期待順位、rating、review countを固定した。独立した4方向参照がないためproduction scoreではなく、nearだけ自己参照を除外するcluster診断を行った。全体保持profileではAUC 0.642857143、期待順位との順序一致27/53であり、center-crop profileの0.392857143・21/53から改善した。同じ一致特徴を持つn4・f4とf1・f2の期待順はreview quality componentと一致したが、これは画像componentの採用条件を満たさない。

case3では「収納口2つ・小型（卓上）・縦・収納」の20候補について、画像で判定する「収納口2つ・縦・収納」と、構造化情報で判定する「小型（卓上）」を分離し、期待順位、rating、review countを固定した。独立した4方向参照がない自己参照除外cluster診断ではAUC 0.468750000、期待順位との順序一致80/173だった。nearとfarの平均scoreはほぼ同値で、far中央値がnear中央値を上回るため、この条件でも画像componentの採用条件を満たさない。

2026-09-07に画像評価を再開し、未使用の視覚条件について隔離Chromiumで実商品画像4枚を取得し、候補を入力しないテスト用gpt-image 4方向参照、score確認前の目視label、固定ONNX 4-reference scoreを一続きで診断した。正例中央値0.900656571、負例中央値0.836320198、pairwise AUC 0.75だったが、正例2・負例2で最低構成を満たさず正式評価に不適格である。左・右参照もpHash距離4で重複閾値5以内だった。本番の4方向参照生成はCloudflareを正本とし、gpt-imageは画像評価テストだけに使う。画像componentは無効のままである。

同日の後続category-only試験では「電気ケトル」候補10件を別固定条件「黒い本体」で正例4・負例6へCLIP前に固定した。外部到達100件、送信前遮断70件、gpt-image 4 calls、retry 0で、正例中央値0.924253657、負例中央値0.870871561、pairwise AUC 1.0、参照pHash最小距離12となり、単一条件の事前基準を満たした。これは複数カテゴリの本評価またはproduction接続の成功ではない。

同日の次の未使用category-only試験では「オフィスチェア」候補12件を「黒いメッシュ背もたれ・ヘッドレスト付き」で正例4・負例6・曖昧2へCLIP前に固定した。外部到達100件、送信前遮断70件、候補を送らないテスト用gpt-image 4 calls、retry 0で、正例中央値0.900518905、負例中央値0.921669262、pairwise AUC 0.291666667、参照pHash最小距離6となった。最低構成と参照非重複は満たしたがAUCと中央値分離は不合格であり、前の単一条件passをカテゴリ横断で再現できていない。

### 11. UIとCLI

- React画面は固定合成データのオフラインモックで、実検索・APIとの接続は未実装である。
- CLIは上位商品のスコア、価格、タイトル、URLを表示する。表示件数は `--display-limit` で指定する。
- CLIは例外を捕捉して整形せず、失敗時はトレースバックを出し得る。
- 旧Streamlitのサイドバー、実商品画像の表示、セッション状態は削除した。

### 12. 設定

- `Settings` はモジュールimport時に1回生成される。プロセス実行中の環境変数変更は自動反映されない。
- `.env` はリポジトリルート固定で読み込む。
- 未参照だった `APP_ENV` と `LOG_LEVEL` は設定契約から削除済みである。旧 `.env` やprocess環境に残る同名値は未知項目として無視され、環境切替やログ制御を行わない。
- Streamlit専用の `SHOW_DEBUG_INFO` は削除した。旧環境に残る値は未知項目として無視する。
- `.env.example` の数値・bool・Path項目を空代入として有効にすると、Pydanticの型変換に失敗し得る。
- スコア総合係数は浮動小数点誤差 `1e-9` の範囲で合計1.0を要求する。

### 13. ログと観測可能性

- Python loggingの全体設定と、環境変数によるログレベル切替はない。
- 標準出力は処理段階、request ID、ポーリング状態、キャッシュヒット、保存先パスを出す。
- 検索語、要求URL、結果URL、APIキーは現行コードで標準出力しない。
- 保存先の絶対パスは環境構成を開示し得る。
- 構造化ログ、相関ID、メトリクス、分散トレース、監査ログ、アラートはない。

### 14. テストと品質保証

- 単体・パイプラインテストは外部APIをモックする。
- 実Bonsaiモデルの品質、実Outscraperレスポンスとの継続互換性、現行・次期ランキング精度は通常のpytestでは確認しない。ranking v3・typed-ranking-v4、holdout評価、acceptance policyのofflineテストは、合成fixtureに対する計算・判定契約、集計、改ざん拒否、決定性だけを確認する。
- ReactモックにはPlaywrightの画面テストがある。実検索UIのE2Eを示すものではない。
- 現行作業ツリーのCIはPython 3.11 / 3.13のマトリクスを定義する。変更前のGitHub実行ではPython 3.10で54件失敗・8件エラー、3.13で41件失敗を確認した。最低バージョン更新に加え、SSLモックと環境変数の期待値を修正し、3.11 / 3.13で関連99件が成功した。権限・ACLへのテスト依存も修正し、通常ユーザーで対象195件が成功した。本体の保護チェックは維持している。変更後のGitHub実行と必須チェック設定は未確認である。
- フロントエンドCIは独立したNode.js 22ジョブで、ロック済み依存、型/整形、Vitest、build、Chromiumによるビルド版全テストと開発版の操作部品テストを実行する。1ワーカー・再試行なし・test.only禁止。追加後のGitHub実行は未確認で、実サービスのE2Eを含めない。
- 実API結合試験は料金と外部状態へ影響するため、自動受入条件に含めない。
- 通常pytestのnetwork guardはPythonのsocket、DNS、Requests経路を遮断するが、subprocess、native code、候補差分によるfixture改変をOSレベルで止めない。
- repository-localの606 MB CLIP modelを読むtestは `clip_runtime` markerと `--run-clip-runtime` の二重opt-inにし、通常pytestではskipする。このopt-inは外部通信を許可せず、画像品質やWindows native動作の確認も代替しない。
- `live_api` はmarkerと `--run-live-api` の二重opt-inであるが、外部通信、シークレット、課金の承認を代替しない。
- 旧段階コードは `bin/examples/legacy-phases/` に保存されているが、現行仕様やテスト根拠として扱わない。

### 15. 配布と運用

- 開発サーバーを公開本番サーバーとして扱わない。
- シークレット管理サービスとの統合はない。
- 読み取り専用アプリ領域と書込可能キャッシュ領域の分離設定はない。
- バックアップ、災害復旧、ロールバック、ゼロダウンタイム更新の手順はない。
- API利用量、ストレージ容量、応答時間、エラー率の運用目標はない。

### 16. 現行スコープ外

次は設計メモに由来する候補であって、現行実装の制約内では利用できない。

- ComfyUI連携
- SSH連携による分散実行
- アプリ独自のHTTP API
- RDBやオブジェクトストレージ
- ジョブキューと複数ワーカー

これらを追加する場合は、[PLANS.md](DEVELOPMENT.md#統合済みexecution-plan規約) の規約に従って現行制約への影響、データ移行、失敗時の戻し方、検証方法を明示する。

Cloudflareによる先行1枚の確認後の条件別偽画像生成、pHash重複検出、固定CLIP embedding、段階ごとの明示確認、モーダル系UI境界、認証主体別の検索履歴は候補ではなく本書と [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装) で要件を確定している。gpt-imageは画像評価テスト専用である。利用者向けの操作は [SEARCH-FLOW.md](../SEARCH-FLOW.md) を参照する。ただし [TASK-008](GOAL.md#task-008-次期検索フロー-v2-の実装) が完了するまでは現行実装の制約内で利用できない。


### candidate経路のBonsai利用範囲

2026-09-10の利用者決定により、candidate経路ではBonsaiをCLIP画像比較のための視覚条件の意味付けと、文脈に基づく商品名候補の選択・補完に使う。検索用の言い換え語・英訳候補はローカル辞書と文脈による語義選択で作る。商品に適合点数を付ける処理と、商品本文から属性を追加推論する処理には使わない。入力の分解・検索queryはSudachiPy、任意のGiNZA構文解析と既存規則、仕様判定は商品記載に基づく決定的処理、同条件での採点はタイトル単語一致とCLIPとする。未確認の仕様を推論で合格にしない。旧legacy経路の記述は移行前の実装説明であり、この要件を上書きしない。


検索語候補は利用者が確認してから1本を選択する。元の検索語を先頭候補として保持し、候補を未選択または生成できない場合は元queryで進める。選択は画像生成と商品取得の承認前に行い、後から検索条件や採点基準を変更しない。商品採点や仕様補完にBonsaiを再使用しない。

元の商品句と言い換え語には、それぞれ英訳を1つだけ対応付ける。言い換えは最大3件、英訳は各1文字列とし、不確かな英訳は明示的に未確定とする。確認時に対応関係を示し、翻訳の候補リストを自動的に検索へ展開しない。


検索用の辞書経路はJMdictの名詞語義と、未収録時の日本語WordNet名詞synsetを使う。旧dictionary-query-terms profileではモデルは既存語義IDを選ぶ。新しいproduct-query-terms-v1では未収録の商品名と英訳の提案も許容するが、属性や仕様の充足は生成しない。未収録・信頼度不足は追加候補なし、商品句または条件の関係が未解決なら検索前に保留する。修飾・否定・選択関係を落として検索を続けてはならない。CLIP用Bonsai、元の価格/仕様、ランキングの重みは維持する。辞書/モデル資材の取得は別の環境準備とし、通常runtimeは通信も自動取得もしない。小型encoderの語義選択精度は開発段階であり、あらゆる入力の自動解釈を保証しない。


旧dictionary-query-terms-v2の文脈選択profileではWordNetの日本語定義・用例を語義ごとに保持し、小型モデルが原文と候補定義を対で比較する。日本語定義が利用できる場合はWordNetの語義集合を使い、JMdictとの意味対応を推測して統合しない。未収録または文脈のない多義語はBonsaiへ送らず保留する。文脈付きで小型モデルが保留した場合のみBonsaiへ1回送り、上位2候補から既存ID/nullと原文参照番号を受ける。引用文は生成させない。小型モデルの最上位と一致した場合だけ採用し、不一致なら保留する。モデル同士の一致は意味の正しさを保証しないため、候補確認と品質評価を維持する。CLIP用途と合わせて最大2 calls、商品採点には追加しない。


商品句の現行prepare経路は、原文の対象と修飾句を保持し、商品名候補の解決を条件query検証より先に行う。隣接名詞はSudachiの細分類も使い、未知略語の係り受け誤判定で分断しない。文脈中の名詞を手掛かりに対象名で終わる辞書見出しを検索する。単義でも意味を限定する文脈があれば適合を比較し、価格等だけの場合と区別する。Bonsaiは辞書候補の選択、未収録名と英訳1件の提案、保留を最大1 callで返す。辞書候補がある場合の生成名は辞書へ再照会し、ヒットした場合は辞書訳を使う。正常な辞書照会が候補0件の場合は、原文と対象だけを使う専用のBonsai直接推論に分岐し、辞書の再照会なしで名称と英訳各1件を未確認候補として返す。追加文脈のない未収録名も推論対象とし、自然な言い換えを許容する。辞書失敗は候補0件と扱わず保留する。直接推論と未収録提案には辞書IDを付けない。

ProductPhraseReviewは元の原文・対象span・修飾句と候補を保持し、成功planまたは準備失敗の明示reviewとして返す。未解釈の用途・仕様を候補名へ吸収して捨てず、現行で条件化できない場合は実検索/画像を停止する。否定・選択関係の未解決部分を含む商品候補は保留する。候補が選べたことは条件解釈や商品充足の合格ではない。CLIP用Bonsaiは従来の1 callを維持し、合計最大2 callsとする。


OPUS-MT接続は任意のローカル実行環境で、主環境の依存を追加しない。検証済みOPUS-MT ja-en INT8資材と、CTranslate2 4.8.2 / SentencePiece 0.2.1 / sacremoses 0.1.1 / NumPy 2.2.6を含む独立Pythonを指定する。既存検証環境はPython 3.13.13/Linux CPU。Windows nativeと本番iGPUでの今回の接続動作は未検証である。翻訳にGPU/外部APIを必要とせず、モデルの自動取得はしない。


### 未知カテゴリを扱う画像評価（2026-09-10、EXEC-113）

candidateの画像点は全体外観の類似度を基本とし、カテゴリ専用の形状測定や部位切出しを実行の必須条件にしない。任意の商品/部位の原文条件をBonsaiで整理し、参考画像の確認後に条件別偽画像を生成・確認する。部位の測定・仕様一致と外観類似を区別し、画像が不足/比較不能でも商品を除外しない。価格等の事実判定は画像点に置き換えず、Bonsaiの商品採点も追加しない。幅広い商品で計算可能であることと未知カテゴリでの順位品質は別に検証する。


EXEC-116以降、candidate画像比較の既定はSigLIP 2 Baseの準備済みローカル実行環境と固定資材を必要とする。通常Python依存は維持し、PyTorch等は別環境へ固定する。CPU2threads、モデル資材約1.54GB、試験時のピークメモリ約1.42GiBを目安とし、実iGPU加速や全カテゴリ精度は保証しない。3Dモデル/4視点生成は不要。採用根拠は利用者指定の未知カップ21商品の目視順位一致60%以上を満たした75.8%と、その後の明示組み込み指示。
