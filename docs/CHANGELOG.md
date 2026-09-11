# 変更履歴

## 1. 記録方針

この文書は、利用者・開発者から見て重要なマージ済み変更を、Keep a Changelog形式の区分で要約する。詳細な作業経緯と検証結果は [WORKLOG.md](WORKLOG.md)、個々の差分はGit履歴を正とする。

- `Unreleased` は現在の作業ツリーにある未コミット変更であり、マージ済みまたは配布済みを意味しない
- マージ済み節の日付と短縮SHAは `git log` で確認できるcommit dateとcommitを使う
- 現在のGit履歴にtagはないため、release versionを推測して付けない
- 外部API、credential、課金、ブラウザ、実hostの確認は、コミットまたは検証記録に根拠がある範囲だけを記載する
- 将来計画は変更履歴へ先取りせず、[GOAL.md](GOAL.md) と [Execution Plan規約](DEVELOPMENT.md#統合済みexecution-plan規約) で管理する

## [Unreleased]

> 状態: 現在の作業変更。未コミット・未マージであり、完了済みreleaseではない。

### Added

- フロントエンドの第三者ライセンス全文・著作権表示を配布物へ同梱し、READMEへ使用資材のライセンスを明記し、著作権表示・本文へリンクした。

- push・pull requestで独立実行するフロントエンドCIを追加。Node.js 22で型/整形・単体・build・Chromium画面テストを実行する。

### Removed

- Streamlitの起動口・画面・専用テスト・SHOW_DEBUG_INFOと依存を削除した。画面はReactオフラインモック、実検索はCLIを使う。既存のschemaテストが必要とするjsonschemaは開発依存として明示した。

### Changed

- 最低対応Pythonを3.10から3.11へ引き上げ、CIを3.11 / 3.13、Ruffをpy311へ更新した。Python 3.10環境は更新が必要。

### Fixed

- 権限境界テストの暗黙のroot依存を除去し、通常ユーザーとACL付きPython配置でも検証できるようにした。本体の安全性チェックと実所有者変更の専用テストは維持した。

- AIレビュー境界テストのSSLモックを標準SSLContextに合わせ、rootless実行時の環境変数をホストに依存せず検証するようにした。

- 履歴一覧のカードを4列・幅268pxへ縮小し、内側余白と項目間隔を詰めた。
- 履歴一覧・詳細の段階バー用空白を廃止し、一覧の商品名に背景 `#212121` を付けた。

- 履歴詳細の条件を背景付き2列にし、削除・履歴へ戻る操作を条件枠の最下部へ移した。

- 表示件数プルダウンの選択時の追加フォーカス枠を非表示にした。

- 結果画面の右下に白背景・黒い上矢印・全方向の影を持つ「トップに戻る」ボタンを追加した。

- 「新しく検索」を全画面のヘッダー右側操作の左に配置し、処理中のモックもリセットできるようにした。結果カードの詳細ボタンを削除し、商品名は実HTTPS URLを明示した場合だけ商品ページへのリンクにする。モックではリンクを無効に保つ。

- 順位ラベルの右上・左下を直角、左上・右下を15pxの角丸にした。検索条件はカードごとに開閉できる折りたたみ表示にした。

- 順位ラベルの上端も商品カードの上枠に揃えた。

- 結果画像を虫眼鏡表示・クリックで拡大できるようにし、未確認・不一致を条件名だけの表示へ変更した。詳細操作を中央に、順位をカード左枠に重なる青い `#n` ラベルに揃えた。履歴内の結果にも適用する。

- 商品調査の完了チェックマークを24px・太さ700に調整した。

- 履歴一覧・詳細で見出しとモック通知が110px上にずれる問題を修正し、検索画面と配置を揃えた。

- 最終確認の条件名を背景の外側へ移し、値だけに背景を付けるようにした。

- 最終確認の「入力した文章」の本文も、各条件と同じ背景・角丸・余白に揃えた。

- 最終確認の各条件を背景 `#212121` の角丸領域に表示するようにした。

- 条件確認の各入力欄で、選択時の追加フォーカス枠を非表示にした。

- 条件確認の「入力した文章」の背景に15pxの角丸と16pxの内側余白を付けた。

- 条件確認画面の「入力した文章」の本文背景を `#212121` に変更した。

- 条件確認の5つの入力欄の背景を、自然文入力欄と同じ `#212121` に統一した。

- 参考画像・比較画像の拡大を画像クリックへ変更し、ホバー・キーボードフォーカス時に虫眼鏡アイコンを表示するようにした。

- 共通見出し下の「希望を確かめながら、ひとつずつ。」を全画面から削除した。

- 画像生成中ポップを96×32pxへ縮小し、参考画像・比較画像の確認で「条件へ戻る」「作り直す」を横並びにした。

- 条件整理の入力欄を選択した際の追加フォーカス枠を非表示にした。

- 入力欄下の「日本語で、そのまま。」を削除した。

- 条件整理の入力欄の背景を `#212121` に変更した。

- 条件整理の不要なキャッチコピーと操作説明を削除し、モックの警告は保持した。入力例を薄い文字色 `#a0a0a0` にし、入力欄の上へ16pxの余白を追加した。

- トグルスイッチのOFF背景を `#424242` に変更した。

- 段階バーの現在の丸は44pxを保ち、完了・未到達の丸を28pxへ縮小した。丸の中心と接続バー、ラベルの位置を維持する。

- 角丸の白線に残る薄れを、同位置の1px輪郭を重ねて補正した。線の位置・寸法・色を維持し、曲線の濃度と輪郭外へのはみ出しを画素で検証する。

- 全体段階バーの完了した丸を青背景 `#3a83f7` にした。画面更新時の先頭へのスクロールを削除し、見出しへフォーカスを移す際もスクロール位置を保つ。

- Chromeの100%表示でも残った角の薄れに対応し、ボタン・ウィンドウ等の枠をぼかしなしの内側1px輪郭へ変更した。色・寸法・内容位置を保ち、角の濃度と直線1pxを画素で検査する。[EXEC-121](GOAL.md#exec-121-枠線の濃淡を画素で検証して改善) に比較を記録した。

- 細い外枠の描画を改善するため、ウィンドウ・ボタンのsquircleを標準の円弧へ変更した。補足の行高を24pxに揃え、枠位置への端数累積を抑える。外枠1px、角丸15px/100px、指定色とボタン寸法は維持する。

- 危険ボタンの文字色を外枠と同じ `#901010` に揃え、ホバー時も維持する。通常・小型を含む全実行・遷移ボタンの外枠は1pxと明記した。

- トグルの切替を滑らかにし、ウィンドウ・ボタンの角丸へ連続した曲線を適用した。検索履歴一覧の「削除」「開く」は96×36pxへ縮小し、削除を左、開くを右に配置する。すべての「削除」を共通の危険ボタンにし、危険操作の外枠を `#901010` へ変更した。開発版で確認ダイアログを閉じた後のフォーカス復帰も修正した。検証は [EXEC-119](GOAL.md#exec-119-トグルの動き角丸履歴操作の調整) を参照する。

- 開発画面で主要ボタンが白背景・白文字になるCSS優先順位を修正した。画像利用は指定色のトグルへ変更し、段階バーと商品調査の白い丸枠をSVGで滑らかに描画する。開発版とproductionの検証結果は [EXEC-118](GOAL.md#exec-118-主要ボタンとトグル丸枠の表示修正) を参照する。

### Added

- React + StyleXのデスクトップ用オフラインモックを `frontend/` に追加した。任意入力の保持、固定デモ条件の編集、段階的な画像確認、商品調査、結果・タブ内履歴と失敗回復を操作できる。Noto Sans JPと合成画像はローカル配信し、実バックエンド・外部APIは使わない。起動は `cd frontend && npm ci && npm run dev`。検証範囲は [EXEC-117](GOAL.md#exec-117-react-stylexのオフライン画面) を参照する。

- candidate画像評価の既定をSigLIP 2参考画像方式へ変更。固定ローカルencoder、旧CLIPと分離した採点/履歴profile、CLIの--image-model/--image-pythonを追加。画像承認・資格条件優先・タイトル80%/画像20%を維持し、旧履歴は再採点しない。

- 辞書候補が0件の場合、Bonsaiが原文から名称と英訳を直接提案する経路を追加した。商品名だけの入力にも対応し、辞書再照会・語尾一致の制約をこの経路から外す。未確認候補と原文条件を保持し、候補確認と検索前の条件検査を維持する。

- candidateの構文解析経路で、原文の対象と修飾を保持して商品名候補を条件検査より先に作成する。複合語の辞書照会と、曖昧/未収録時のBonsai提案を追加し、未確認名には辞書IDを付けない。未解釈条件が残る場合は候補付きで停止する。CLIP用Bonsaiと検索候補の人間確認を維持する。

- search_v2の検索語から日本語の接尾辞が欠落する不具合を修正した。名刺入れ・子供用等を保持し、接尾辞付きの活用語も元の表記で組み立てる。検索query・Bonsaiへの商品句・タイトル一致に共通して適用する。

- candidate経路へ、確認用の日本語言い換え語・英訳候補を作るBonsaiの用途を追加した。元語と最大3件の言い換えには英訳をそれぞれ1つ対応付け、未確定の訳は保留する。対応関係を確認して最大8本から1本を画像生成前に選択できる。失敗時は元queryを維持し、商品の条件判定・採点には候補を流用しない。Bonsaiは視覚条件提案と語句候補作成の最大2回だけである。

- candidate経路のBonsaiから商品採点を除去した。現在の用途はCLIP用の視覚条件提案と検索語候補作成に限定する。商品採点・商品本文の属性推論フックを除去し、既存の条件判定とタイトル単語一致、CLIPで順位を計算する。新採点profileはcandidate-lexical-clip-v2。旧表示履歴は点数を変えず読み込める。

- Bonsai商品評価の入出力を短い配列形式にし、商品順とfield序数から従来の点数・引用へ復元する診断経路を追加した。現在の商品検索フローからは切り離している。商品本文・候補数を削減せず、旧応答読込とranking/履歴形式を維持する。実runnerには本文を残さないwall時間・モデルtoken数/処理時間の記録を追加した。

- Bonsaiの商品評価で、引用先を実在する同一商品のfieldに限定する生成schemaを追加した。文字位置の上限を本文長へ束縛し、点数と引用、判断保留と空引用を対応させる。空本文の商品は保留のみとし、受信側の不正引用拒否と既存ranking/履歴形式は維持する。

- Candidateの商品評価失敗に固定code診断を追加した。意味評価応答の終了理由・件数・点数・引用束縛の拒否を区別し、rankingとcomplete境界を通じて実runnerのsummaryへ保持する。生応答や不正値は保存せず、判定・順位計算・履歴保存だけの再試行契約は維持する。

- CandidateSearchFlowを追加し、新candidateから参考画像承認・条件別偽画像・最終承認・CLIP評価・履歴DBまでoffline接続した。数値必須条件を優先し、現在は単語一致80%と画像20%を合成する。画像不明を保持し、新profileの品質未測定は履歴にnullとして保存する。履歴保存だけの冪等な再試行を追加した。

- candidate経路の任意Bonsai視覚抽出を、既存VisualConditionSetと取得前確認へ接続した。原文引用・強度・非視覚条件を検証し、検索語はSudachiPyで組み立てる。画像/CLIP未実行の視覚条件はrankingでpendingとして保持する。

- `candidate_queries.py` / `candidate_search.py` に、SudachiPyで検索query・参考画像promptを作り、取得商品の観測属性を確認してから単語一致点数と数値条件で評価する独立offline経路を追加した。一次資料集・カテゴリ別辞書は不要。実provider・画像承認・履歴・API・frontendは未接続で、既存liveフローは未切替。

- 4面の品質診断に、seedと参考画像を固定した取っ手の見え方の指定と、近似画像の検出を追加した。4B実画像でも右側面の品質は未達。9Bの右側面1枚では改善を確認し、汎用4方向指示による追加比較modeを準備した。4面全体の品質確認は未完了。

- Cloudflareの4方向生成に参照視点からのcamera移動と遮蔽を明記し、承認済み参考画像から追加4枚だけを生成する限定診断を追加した。offline確認と追加4-call診断を実施したが、4方向の視点品質は未達。

- 自然言語から参考画像1枚・了承後4方向と偽画像・本番検索job・ランキング・履歴再読込までを実行する専用backend E2Eを追加した。liveは別承認と途中の画像確認が必要。

- 次期画像生成に、参考画像1枚の確認後だけ新規4方向画像と条件別の比較用偽画像を生成する段階を追加した。古い確認、二重操作、期限切れ、画像OFFでは後続生成せず、参考画像の作り直しに新しい了承を必要とする。Figmaと利用フローを同期し、委託フロントエンドへの接続と新フローの実サービス検証は含めない

- `src/search_v2/production_api.py` に、最終承認controllerが同一processへ登録する最大15分のsubmission capabilityからjobを冪等投入し、状態取得、queued・running取消、schema 5.0履歴詳細取得を行うloopback限定のStarlette ASGI API factoryを追加した。ownerはserver-sideの `local-user` に固定し、応答から承認token、binding、内部failure code、profile、既知accuracy、digest、score、画像body、生例外を除外する。server起動構成、認証、委託フロントエンド、実provider E2Eは含まない
- `src/search_v2/production_search.py` に、最終承認済み検索と同じowner・session・元入力に結ばれた承認済みcounterfactual参照をlocal jobへ冪等投入し、Outscraper 1 task、商品画像、固定CLIP、暫定ranking v5、schema 5.0履歴locatorまでを実行するapplication serviceを追加した。job DBには検索文、token、商品、URL、provider本文、生例外を保存せず、重複投入と失敗後の自動retryを行わない
- `usage_ledger.py` に現行local production用のquota無効policyを追加した。per-user・session・day・cost累計を拒否条件にせずattemptと費用を記録し、既存のquota有効policyと操作単位の固定call数・候補・poll・byte・timeout・自動retryなしは維持する
- `tools/provisional_search_live_e2e.py` に、Cloudflare desired・counterfactual 2枚の生成後に同一processで人間確認を待ち、参照fileのidentity・digest、15分期限、single-use承認を再検証した後だけOutscraper 1 task、商品画像最大24 GET、固定CLIP最大7 batches、暫定ranking v5へ進む対話式live E2E境界を追加した。専用pytest opt-inと固定確認文を必要とする。二段階承認後の初回liveはCloudflare 2 callsとOutscraper 1 taskまで進み、retry 0のままranking段階で失敗したため、成功済みproduction E2Eとは扱わない
- 初回liveのranking失敗を次回に安全に診断できるよう、商品正規化、typed ranking、参照・候補CLIP、候補準備・score、較正、ranking v5、結果検証のclosed substageと到達済み件数を固定errorへ追加した。生例外、商品data、provider ID、URL、画像digest、score、embeddingは診断へ含めず、過去の失敗を新しいstageへ推測で割り当てない
- `src/search_v2/provisional_search_pipeline.py` に、成功済みOutscraper 1 task・日本語query 1件・最大24候補を、観測値だけの商品正規化、`typed-ranking-v4`、承認済みcounterfactual参照、各商品の先頭画像、production proxy、固定CLIP、batch較正、暫定ranking v5へ接続するoffline backendを追加した。安全な集計はtask・poll・候補・画像状態の件数だけを返し、保存済みPNGから承認receiptを再構成しない
- `src/search_v2/` に、strict intent、provenance、決定的正規化、最大2件の日英query planを現行pipelineから隔離して追加した
- `src/search_v2/bonsai_adapter.py` に、full raw response body、OpenAI互換envelope、content全体のstrict JSON、strict intent、provenanceを結ぶnetwork非依存境界を追加した。不一致時は固定messageのまま、本文を保持しない7段階diagnosticを返す。draft schema不一致は値やvalidation本文を持たない固定group、検索不能は正規化済み値を持たない `missing_terms`・`invalid_terms` の固定groupへさらに分類する
- 同adapterの商品名、brand、model number、自由語termをSudachiPyの完全なsource spanまたはASCII語境界へ照合し、無根拠値をqueryへ渡さないようにした。JPY価格は正しい3桁comma区切りを受理し、不正区切りへの部分一致を拒否する。修正後の承認済みlocalhost Bonsai 1 callでは価格範囲、必須語、除外語を保持した一方、商品名fieldが空という理由だけでblockingになる過剰制約を確認した。入力に根拠のある肯定検索語が残れば商品名なしでもqueryを作り、価格・除外語しか残らなければ `source_product_ungrounded` へ戻す汎用判定へ修正した。最終修正後の実modelと実商品E2Eは未確認である
- 上記汎用判定後の承認済みlocalhost Bonsai 1 callは41.148秒で `ready` となり、明示条件を保持して無根拠商品名を除去した。ただしSudachiPyで `超低背` の連続接頭辞が落ち、queryが `背 ワイヤレス キーボード` となったためOutscraper前で停止した。tokenizerで連続接頭辞を直後の内容語へ結合し、同じ応答相当fixtureのqueryを `超低背 ワイヤレス キーボード` へ修正した。これはqueryと類似語scoreに共通する変更であり、接頭辞修正後の実modelと実商品E2Eは未確認である
- 接頭辞修正後の承認済みlocalhost Bonsai 1 callは60.366秒で `ready` となり、query `超低背 ワイヤレス キーボード`、価格範囲、必須語3件、除外語1件を保持した。Outscraperは呼ばず、JSON境界で検証した一時継続stateを権限0700/0600で保持した。一続きの実商品E2Eは未確認である
- 別の明示承認後、保持したqueryでOutscraper taskを1回だけ作成し、自動retry 0、同一taskのpoll 8回、221.458秒で24候補を受信した。24件すべてが正規化・typed rankingを通過し、rejectは0件だった。生商品データとcredentialは保存せず、一時stateを削除した。browser・UI・production E2Eおよび個々の順位品質は未確認である
- `src/search_v2/bonsai_adapter.py` と `bonsai_request.py` に、既定値を省略するrequest schema 7.0のcompact wireと、従来の完全19-field draftへの決定的復元を追加した。値がないscalar、空list、価格なし、固定JPY、非該当価格値、null confidenceだけを省略し、unknown field、型coercion、不整合なsparse価格、無効なtyped condition・ambiguityは拒否する。ambiguity code pattern、同値のllama.cpp互換decimal pattern、価格mode・source別9 sparse variant、通常の商品種別または全blocking確認待ちを持つ非空生成schemaを `response_format.schema` へ1回だけ送る。完全schema本文はmodelへ二重送信せず、完全schemaと生成schemaの別digest、application側のstrict最終検証へ維持し、旧6.0、未知pattern、schema欠落、body・digest改ざんを送信前に拒否する。代表fixtureはlocal Bonsai tokenizerで126 tokensとなり、同じ意味のminified完全形式181 tokensより30.4%少なく196-token目標を満たした。`max_tokens=196` は設定せず、applicationの生成token上限・HTTP timeoutなし、1-call、retry 0、response 1 MiB上限、本文非保持diagnostic、完全schemaとquery plannerを最終権威とするstrict parserを維持する。v7の実model生成・速度・意味品質は未確認である
- 後続の明示承認済みlocalhost診断ではrequest v7を実modelへ送信したが、365.12秒で応答未完了のため手動停止した。停止直前はserver内の生成が進行中で、clientはsocket read待ちだった。停止後はprocessとportを回収したが、completion token数、strict結果、速度改善率、意味品質は得られていない
- 現行request schemaを8.0へ更新し、検索可能compact wireを最大12種類の固定field、確認待ちを `ambiguities` 1 fieldへ分離した。商品名・brand・modelは48文字、termは32文字、各term list・typed condition・set値は4件、ambiguityは2件・各96文字へ制限し、categoryはproduct nameへ、colorとfeaturesはtermsまたはtyped conditionへ集約する。上限を超えて意味を保てない場合は切断せずblocking確認待ちへ戻す。llama.cpp converterで有限反復と除外field不在を確認し、代表fixtureは104 tokens、完全19-field形式は181 tokensだった。明示承認後のCore i5-13600KF・CPU版localhost診断は同じ固定入力2 callsでともに254 completion tokens・strict intent成功となり、warm wall 17.625秒で旧v6記録の90.440秒から80.51%短縮した。旧v6とは別runの比較であり、意味品質とCore Ultra性能は未確認である
- `src/search_v2/bonsai_http.py` に、canonical bodyを変更せず1回だけPOSTするRequests transportを追加した。環境proxy・環境由来認証・既定metadataを使わず、TLS検証、redirect・retry禁止、application timeoutなし、streaming 1 MiB上限、確実なcloseをmockで確認する。localhost Bonsaiの4応答完了は確認したが、現行pipelineには接続しない
- `tools/bonsai_live_e2e.py` と `bonsai_e2e` pytest markerに、request v6と本番相当のprompt cacheを同じlocalhost `llama-server` で確認する明示opt-in結合testを追加した。serverはloopback、context 8,192、parallel 1、cache有効、log無効に固定し、異なる合成入力2 callsをactual Requests transportとstrict adapterへ通し、2件目のcached tokenを検査する。通常CIでは除外する。明示承認後のCore i5-13600KF・CPU版live testは2 callsともfull JSON・strict intentに成功し、2件目で891 cached tokensを確認した。終了後はserver processなし・port非listenを確認した
- 同runnerへ、同じ固定合成request v6を2回だけ送ってprompt処理とcompletion生成を分離する専用latency diagnostic selectorを追加した。通常のBonsai live testとは排他にし、duplicate key・非有限数・型・範囲・token整合を検査したうえで、prompt・cache・completion token数、`prompt_ms`、`predicted_ms`、finish reason、response byte数だけを本文非保持で投影する。明示承認後のCore i5-13600KF・CPU版実行は両方487 completion tokensでfull JSON・strict intentに成功し、2件目は923 / 924 prompt tokensをcacheした。prompt処理は353.47倍・99.72%短縮、wall全体は1.52倍・34.13%短縮し、warm wallの99.82%はcompletion生成だった。終了後はserver processなし・port非listenを確認した
- `src/search_v2/tokenizer.py` にSudachi内容語・英数字tokenizerを追加し、意味語句単位の200文字上限を維持してquery plannerへ接続した
- `src/search_v2/approval.py`、`state_machine.py`、`usage_ledger.py` に、承認から検索完了・固定失敗までのsnapshot、canonical plan、15分のsingle-use承認、同一process内のcall・token・整数micro-USD予約境界を追加した
- `src/search_v2/cloudflare_request.py` に、固定4方向、attempt別seed、prompt contract、最大511pxの共有参照PNGを持つcredential-free multipart request descriptorを追加した
- `src/search_v2/cloudflare_http.py` に、開始済み4-call予約と画像生成stateを再検証し、server-side credentialで固定順のmultipart POSTを行うRequests transportを追加した。厳密なHTTP・JSON envelope・Base64検証、2 MiB以下のJPEG・PNG・WebPからmetadataなし512px RGB PNGへの決定的正規化、511px派生参照、全成功時だけの利用量・`image_review` 確定をmock・合成画像で確認し、現行pipelineには接続しない
- Cloudflare Account IDとAPI tokenを型付き設定へ追加し、tokenをmaskしたまま固定合成条件の基準画像1枚だけを1 callで生成する明示opt-in runnerを追加した。承認済み初回live試行は固定エラーで失敗し、別承認の追加1 callはHTTP 200・成功JSON後の `image_content` で停止した。credential・provider本文なしのclosed stage診断を維持し、公式契約にないraw PNG限定をJPEG・PNG・WebPの安全な正規化へ修正した。修正後のlive再試行は行っていない
- `src/search_v2/outscraper_request.py` に、1回のGETへ最大2件のqueryを反復するcredential-free request descriptor、exact parameter digest、single-use承認後だけ返るexecution permitを追加した
- `src/search_v2/outscraper_http.py` に、承認permitと開始済み利用量予約を再検証し、APIキーを固定headerへだけ注入するRequests transportと、同一origin・同一request IDへ限定した非同期task・上限付きpolling境界を追加した。通信、応答、task失敗、待機超過は生provider文を含まない固定エラーへ変換し、実Outscraperと現行pipelineには接続しない
- `src/search_v2/product_normalization.py` に、検証済みOutscraper requestへ結ぶ観測値だけの商品正規化、未知属性、固定reject、入力上限、非LLM境界を追加した
- `src/search_v2/image_proxy.py` に、注入式resolver・transportへHTTPS allowlist、global DNS・peer IP一致、redirect・timeout・byte・MIME・format・寸法・decompression bomb制限を強制し、metadataを除いたRGB artifactを返すoffline境界を追加した
- `src/search_v2/image_proxy_dns.py` に、小文字ASCIIのcanonical hostを `getaddrinfo` 1回で解決し、TCP用IPv4・IPv6を最大8件へ限定して既存proxy coreへ渡すadapterを追加した。host・生resolver結果・OS例外を固定messageへ変換し、global判定と重複除去はcoreへ維持する。主な検証は注入fixtureで行い、実host通信は含めない
- `src/search_v2/image_proxy_dns_process.py` に、Windows 11 / WSL互換の `spawn` 子processへ上記resolverを要求ごとに隔離する境界を追加した。5秒のapplication deadline、結果待機4.5秒、terminate・kill後のjoin各最大0.25秒、最大512 bytesのASCII IPC、親側のcanonical IP再検証、固定errorをfake process・pipe・clockで確認した。WSL2の実 `spawn` は外部DNSへ進まない固定失敗経路だけを確認し、Windows native・実host通信は含めない
- `src/search_v2/image_proxy_http.py` に、検証済みの先頭numeric IPへIPv4・IPv6 socketで1回だけ接続し、元host名でTLS証明書を検証する画像HTTPS transportを追加した。HTTP/1.1、固定header、peer IP、framing、8 MiB上限、全経路closeをsocket・TLS・HTTP fixtureで確認し、実hostへは接続していない
- `src/search_v2/image_proxy_service.py` に、起動時の1〜32件allowlist、既定のprocess分離DNS resolver、pinned-IP HTTPS transport、proxy coreを固定して束ねるserviceを追加した。取得methodはURLだけを受け、設定不正と取得失敗を固定messageへ変換する。合成allowlistと注入fixtureでのみ確認し、運用allowlist・実host通信・APIには接続していない
- `src/search_v2/image_similarity.py` の固定CLIP manifestをrepository-local ONNX 3 fileへ移行し、symlink・hardlink、byte数、SHA-256、読込中のidentity変化を拒否する。64-bit pHash、512次元L2 embedding、4方向fixture scoreと画像ranking無効は維持する
- `src/search_v2/image_similarity_onnx.py` と `image_similarity_process.py` に、224px固定前処理、ONNX Runtime 1.23.2のCPU-only image encoder、最大4枚・30秒application deadline・byte戻り値だけを使うWindows/WSL互換 `spawn` process境界を追加した。固定ONNX modelはlocal working treeへ配置し、local-only経路の合成画像で実推論した。受領1組は正例自身を参照に3回比較してbit-identicalなembeddingと期待順序を確認したが、Git配布、検索文の意味一致、4方向参照・複数商品によるranking品質、画像ranking有効化は含めない
- `tests/test_search_v2_image_similarity_quality.py` に、利用者分類のnear 13枚・far 18枚を相対path・label・SHA-256へ固定するlocal quality dataset検査と、固定4参照から自己参照を除いた27候補のcharacterizationを追加した。near/far中央値は分離したが、pairwise AUC 0.790123457で事前基準0.80へ未達だった。再現可能なscoreは成功test、既知の基準未達はstrict xfailとして保持し、画像rankingは無効のままとした
- 同quality datasetを利用者が整理した `n1.png`〜`n13.png`、`f1.png`〜`f18.png` へ同一SHA-256で対応付け、far 18枚の色・接続方式・ゲーミング用途・対象種別を固定した。属性別characterizationでは、接続方式だけが異なる黒い有線ゲーミングマウス4枚の平均scoreが0.945551862となり、有線・無線を画像だけでhard filterできない境界を再現した
- near 13枚をlocal画像から個別に確認し、全て黒いマウス、11枚はゲーミング用途、n5・n6は用途未知として、利用者指定のfar属性と区別した目視manifestへ固定した。静止画像だけでは接続方式を確定できないため、near 13枚の接続方式は全て未知へ訂正した。用途未知候補の平均score 0.941389590が目視確認済み用途の0.932454373より高くても属性を補完せず、画像rankingは無効のまま維持した
- 固定済み画像scoreへ接続方式非依存の補助評価を追加した。接続方式だけが異なるf2・f4・f7・f10を画像上の正例へ再分類すると、正例13枚・負例14枚の全182組中175組が正順となり、AUC 0.961538462、正例中央値0.942146431、負例中央値0.843137443を再現する。元のAUC 0.790123457とstrict xfailは維持する
- `tests/test_search_v2_image_similarity_quality_case2.py` に、2例目のnear 4枚・far 7枚、視覚・構造化特徴、期待順位、rating、review count、画像hashを固定した。候補と独立した4方向参照がないため自己参照除外cluster診断に限定し、AUC 0.392857143、期待順位との順序一致21/53を再現した。画像componentは無効のままである
- `tests/test_search_v2_image_similarity_quality_case3.py` に、3例目のnear 8枚・far 12枚、視覚・構造化特徴、期待順位、rating、review count、画像hashを固定した。候補と独立した4方向参照がないため自己参照除外cluster診断に限定し、全体保持profileでAUC 0.468750000、期待順位との順序一致80/173を再現した。画像componentは無効のままである
- `src/search_v2/ranking.py` を `ranking-v3` へ更新し、平均4.0以上のratingと対数飽和したreview countによるreview quality componentを追加した。base weightはtitle 0.35、attributes 0.30、price 0.20、image 0.10、review quality 0.05とし、review qualityを唯一の最小値にした。片方の観測値が欠ける場合は既存の欠損weight再正規化を使い、画像componentは無効のままである
- `src/search_v2/product_pipeline.py` に、成功済みOutscraper executionとschema 3.0の承認・state・typed proposal・利用量・runtime bindingを再検証し、観測値だけの商品正規化、画像無効の `typed-ranking-v4`、結果あり・正常0件・工程別固定失敗のstateを結ぶoffline後半pipelineを追加した
- `src/search_v2/holdout_evaluation.py` に、development IDを除外した正解dataset、完全runtime artifactをdigest・状態・順位だけへ投影する予測set、条件・候補・裁定・hard contradiction・uncertainty・必須状態・strict pairwise・NDCGのcase/category/overall集計を追加した。最低構成への適格性は返すが品質合否は出さず、合成fixtureによるoffline契約確認に限定する
- `src/search_v2/holdout_acceptance.py` に、実holdout閲覧前に固定した安全重視policy、全体・全categoryのAND判定、category別安全label適格性、`pass`・`fail`・`ineligible` の独立assessment、policy・report・assessmentのdomain-separated digestを追加した。元の評価reportは `quality_decision=not_assessed` のまま維持し、合成fixtureによるoffline判定契約確認に限定する
- `src/search_v2/holdout_postprocess.py` に、strict intent後のtyped proposal、query plan、typed ranking、prediction projectionを本文非保持の固定4段階へ分けるoffline wrapperを追加した。失敗は列挙済みstageと固定messageだけへ変換し、元例外のcause・contextやruntime本文を保持しない
- `src/search_v2/orchestrator.py` に、Bonsaiからreadyまたはquery-less blockingを返すtyped proposal付き第1確認、blocking停止、画像OFF・ON・一括再生成・破棄、第2確認、single-use承認、Outscraper、正規化、typed ranking、完了までを利用者操作ごとに停止するschema 3.0のoffline backend orchestrationを追加した。`state_machine.py` にはtyped proposal digest・status、readyだけのquery digest必須、blockingでのquery digest禁止と、既発生の画像利用量を残して画像なしへ進む破棄遷移を追加した
- Cloudflareの4枚生成が途中失敗した場合を `image_generation_failed` と `ImageFailureReview` へ固定し、失敗利用量を保持したまま、最大2組の範囲で新しい4枚一括attemptを明示retryするか画像なしで続行できるoffline回復境界を追加した。自動retry、部分画像採用、失敗reservation再利用は行わない
- `src/search_v2/history_repository.py` に、schema 2.0のstrictなtyped表示snapshot、owner内の冪等保存と衝突拒否、未期限履歴の一覧・詳細・参考画像取得、owner確認付き個別削除、30日期限削除を行うローカルSQLite `user_version=2` repositoryを追加した。保存・削除は専有512px PNGと同じtransactionで扱い、旧version 1・未知schema、安全でない既存file mode、保存JSONとdigestの不一致を固定errorで拒否する
- `src/search_v2/history_snapshot.py` に、正常完了result、承認済みreview、元入力、typed proposal・batchの結合を再検証し、必須状態と条件decisionを一致・未確認・情報矛盾・不一致等の限定表示へ変換して、内部score・evidence・metadataを除いた結果と任意の4方向画像を履歴へ冪等保存するoffline境界を追加した。失敗resultとranked商品の差し替えを保存前に拒否し、保存再試行でprovider処理を再実行しない
- `src/search_v2/search_job.py` に、固定local owner、SQLite `user_version=1` の永続状態、同一approval bindingの冪等投入、worker 1本、FIFO実行、状態照会、queued取消、running協調取消、24時間の開始期限、再起動時の固定終端、終了後30日の明示purgeを持つlocal単一process job境界を追加した。検索payload、approval token、provider本文、callback、例外本文は保存せず、成功時も結果locatorだけを保持する。実検索、現行・次期UI、実providerには接続しない
- 利用者の再開判断と明示承認後、隔離ChromiumでAmazon.co.jp検索結果1ページを59要求・retry 0で表示し、DOM候補12件から4商品画像をlocal未追跡assetへ保存した。候補を入力しない組み込みgpt-image 4 callsで独立参照を作り、score確認前の目視labelと固定ONNX CLIPへ通した初回E2E診断は正例中央値0.900656571、負例中央値0.836320198、pairwise AUC 0.75だった。正例2・負例2で正式評価に不適格なため画像rankingは有効化していない
- 後続のcategory-only画像試験ではCDP送信前interceptionで外部到達100件、追加遮断70件、retry 0を守り、実商品候補10件を別固定条件「黒い本体」で正例4・負例6へCLIP前に固定した。候補を送らないgpt-image 4 callsの参照と固定ONNXで正例中央値0.924253657、負例中央値0.870871561、pairwise AUC 1.0、参照pHash最小距離12となり、単一条件の事前基準を満たした。カテゴリ横断評価と製品接続は未完のため画像rankingは有効化していない
- 次の未使用category-only画像試験ではオフィスチェア候補12件を黒いメッシュ背もたれ・ヘッドレスト付きの正例4・負例6・曖昧2へCLIP前に固定した。外部到達100件、追加遮断70件、候補を送らないテスト用gpt-image 4 calls、retry 0で、正例中央値0.900518905、負例中央値0.921669262、pairwise AUC 0.291666667、参照pHash最小距離6となった。AUCと中央値分離が不合格で単一条件passを再現できず、画像rankingは有効化していない
- `src/search_v2/typed_requirements.py` に、値型ごとのstrictな期待値・観測値、9 keyのrepository内registry、alias・unit正規化、registryと条件setの決定的digestを追加した。条件draftはevaluator、実行module、weight、priority、registry digestを指定できず、初期registryはexact属性へ `structured` と `title_exact` だけを許可する
- `src/search_v2/requirement_evaluation.py` に、registryへ結んだ証拠生成、source優先順位と同順位矛盾の裁定、`match`・`mismatch`・`unknown`・`conflict`、固定分母の一致率、必須状態、候補集合に依存しない順位keyを追加した。現行ranking-v3、pipeline、画像scoreには接続していない
- `src/search_v2/product_evidence.py` に、正規化済み商品、typed requirement、trusted registry、固定profileを再検証し、専用color、固定feature全体、有界な商品名表現から `structured`・`title_exact` 証拠を作るadapterを追加した。商品・条件set・registry・profile・source別入力artifactをdigestで結び、本文とdescriptionを結果へ保持せず、未観測・未対応・同source矛盾を安全側に残す
- `SearchIntentDraft` と固定Bonsai promptへ、attribute key、operator、JSON-nativeな期待値、strengthだけを持つ必須 `typed_conditions` を追加した。候補は最大64件、全field必須、extra禁止、値型ごとのstrict unionとし、evaluator、module、model path、URL、command、weight、priority、registry digestを受け取らない
- `src/search_v2/typed_intent_adapter.py` に、既存1回のBonsai strict応答に含まれる候補へローカルcondition IDを付け、trusted registryだけで型付き条件または固定blocking issueへ変換するadapterを追加した。unknown key、型・operator・unit・値不整合、semantic hard条件、正規化後の重複、上流ambiguityを暗黙fallbackせず、valid partialと別に保持する
- `src/search_v2/typed_ranking.py` に、readyなtyped proposalをintentと固定registryから再構築照合し、各商品の限定証拠・全条件decision・typed evaluationを一括生成する `typed-ranking-v4` を追加した。unknown・conflictを残す固定分母typed attributes、excludedの逆条件、必須状態先行sort、v3 source ranking digest、v3と分離したschema・profile・batch digestを固定し、blocking proposalは採点開始前に拒否する。v3のtitle・price・review quality・negative判定だけを再利用し、自由語attributesを持ち込まない。第1確認、承認、state、offline後半pipeline、typed表示履歴へ接続し、legacy現行検索、cache、API、UIには接続しない
- `src/search_v2/outscraper_contract.py` にcredential-free要求model・builder・digestを分離し、商品正規化が承認moduleを逆参照しない依存方向へ変更した。`outscraper_request.py` は既存公開名を維持して認可だけを担当する
- `tools/check_markdown_links.py` と回帰テストを追加し、ルート直下と `docs/` 直下の現行Markdownについて、local path、ATX見出しanchor、fenced code blockを外部通信なしで検査できるようにした。欠落path・anchorは失敗し、外部URLと `docs/old/` 内部は既定検査元から除外する
- 現行挙動を固定するcharacterization testと、strict intent・query planner・Bonsai v2 request・Requests HTTP transport・注入transport・応答境界・tokenizer・承認state・利用量ledger・Cloudflare request・HTTP応答・画像正規化・Outscraper request guard・Outscraper HTTP/task/polling・商品正規化・画像proxy core・有界DNS resolver・spawn process分離・pinned-IP HTTPS transport・server-side proxy service・画像類似度・ranking v3・検索後半pipeline・段階別orchestration・完了検索の履歴変換・検索履歴repository・型付き条件・証拠裁定・Bonsai条件候補adapter・商品証拠adapter・typed ranking v4境界の単体テストを追加した
- `agents-setup` 標準の文書役割として、開発目標をまとめる `GOAL.md` と本変更履歴を追加した

### Changed

- 2026-09-11: 次期UIの実装をReact + StyleXに決定し、Figmaをレイアウト参考として、指定配色・文字サイズ・ボタン配置・進行表示・アニメーションを文書の正本へ固定した。任意の自然言語入力から固定の合成結果まで操作するオフラインモック要件を追加した。UIとモックは未実装であり、今回の変更は文書のみ。

- 2026-09-11: 次期フロントエンドを自前開発する方針に変更し、外部納品を着手条件とする制約を解除した。作業規則、画面仕様、残作業を同期した。今回は文書更新のみで、画面実装・起動・API接続は含まない。

- CandidateRankingのJSON読込で数量・予算のDecimal条件を復元できるようにした。JSON境界だけで明示的に変換し、共通domainの厳密な型・範囲・精度検証、出力形式、digestは維持する。既知失敗だった復元2ケースを通常の成功テストへ戻した。

- 4方向画像生成を製品フローから除去した。参考画像1枚を確認し、了承後に条件別偽画像だけを生成する。通常2〜4 calls、作り直しを含む最大8 calls。backend、承認・利用量、履歴、E2E runner、利用フロー、Figmaを同期した。CLIP・ランキング式は維持し、実検索E2Eは停止中。旧4方向追加記録は変更前の履歴として残す。

- 実商品画像取得の承認済み診断で、`m.media-amazon.com` の正常な一意DNS結果9件を従来の8件上限がHTTP前に拒否していたことを確認した。DNS adapterは生結果を最大64件まで全件構造検証し、順序維持の重複排除後にtransport候補を最大8件へ制限するよう変更した。全商品画像が取得不能な場合は `image_unavailable` を返し、誤った `image_ready` による最終契約失敗を避ける。修正後の限定liveはOutscraper 1 taskから24商品を正規化し、Amazon画像24件の取得、固定CLIP 7 batches、暫定ranking v5を `image_ready` で完了した
- 本番の4方向参照画像は当初の予定どおりCloudflareを正本とし、gpt-imageは画像評価テストだけに使う。実装済みCloudflare境界を製品接続前のoffline実装として維持する
- EXEC-057でBonsai requestをschema 6.0へ更新し、完全schema本文のsystem messageへの二重送信を除去した。生成用schemaは `response_format.schema`、完全schemaは別digestとapplication側strict最終検証に維持する。合成fixtureのbodyは20,716 bytes、system messageは3,772 bytesとなり、model入力から完全schema 7,352 bytes・2,000 tokensを除去した。本番 `llama-server` 起動例は `--cache-prompt`、`-np 1`、`-c 8192` を明示する。固定prompt 883 tokensと有効な最大2,000 codepoint入力4,000 tokensだけで4,096を超えるためcontextは8,192を維持する。明示承認後のCore i5-13600KF・WSL2・CPU版・出力1 token benchmarkでは、変更前相当cache無効のwall中央値142.559秒に対しrequest v6のcache warm中央値は1.236秒で、約115.3倍・99.13%短縮した。このbenchmark単独ではfull JSON、strict intent、Core Ultra性能、production E2E、Vulkan buildを確認していない
- EXEC-043の承認済みdevelopment regressionでは、request v3で同じ4件をretryなしに再送したが、全件が旧300秒timeoutで `request_failed` となりresponse parserへ到達しなかった。EXEC-044でrequest schemaを4.0へ更新し、生成token上限とHTTP timeoutをdescriptor、builder、transport、orchestration configから削除した。response 1 MiB上限、strict parser、retry禁止は維持する
- EXEC-045の承認済みdevelopment regressionでは、request v4で同じ4件を時間上限なし・retryなしに再送した。全件のHTTP応答が完了したが、schemaなしの `json_object` 宣言は現行llama.cppのJinja生成grammarを有効化せず、4件とも `content_not_json` でranking前に失敗した。後続のEXEC-046で非空のllama.cpp互換生成schemaをrequest v5へ追加し、完全canonical schemaによるapplication側のstrict検証を維持した
- EXEC-047の承認済みrequest v5初回実行は、port listenだけを待ってmodel ready前に4要求を送ったため、全件0.006〜0.010秒の `request_failed` となり推論へ到達しなかった。検索文なしのhealth-only再現ではlisten直後503、2秒後200への遷移を確認した。次回は `/health=200` を送信前条件にするが、自動retryせず新しい明示承認を必要とする
- EXEC-047の新しい明示承認後、`/health=200` を待ってrequest v5を同じ4件へ逐次各1回送った。全件がHTTP 200、`finish_reason=stop` で完了し、strict intent検証を通過したため、request v4の `content_not_json` は解消した。その後は評価用一時runnerの後処理で4件とも失敗し、typed rankingは未完了である。合成ready経路はrankingまで通り、合成blocking ambiguity経路を一時runnerが個別分類できないことを確認したが、実4件の原因とは断定しない
- EXEC-048でholdout predictionのblocking形を拡張し、上流blocking ambiguityはquery plannerを呼ばずintent・proposal digestへ結んだquery-less blockingとして評価へ含めるようにした。rankedは従来どおりquery planとranked batchを必須とし、既存のquery付きblocking、ranked、artifact-free failed、評価profile、acceptance policy、元reportの `not_assessed` は変更していない
- EXEC-048後の段階診断付き再計測では、完了2件がstrict intent後の `query_plan_invalid` となった。利用者の意図が全体1件だったとの訂正を受け、送信済みの3件目を手動中断し、4件目は送信していない。部分実行のassessmentは作らず、訂正後の追加model callも行っていない。EXEC-049では同じstageを生む非blocking空検索fieldの契約欠落をofflineで再現し、Bonsai adapterの受理前query plan検査とpromptの検索語必須・URL禁止規則を追加した。blocking ambiguityのquery-less投影、request schema 5.0、生成token上限なし、HTTP timeoutなし、1 MiB response上限、retry禁止は維持する
- EXEC-050では、更新promptを使用済みCSVの先頭1件・合計1 callだけlocalhostで確認した。HTTP 200の応答後、adapterの受理前に `intent_normalization_invalid` で停止し、2件目、retry、dataset assessmentは実行していない。実行時のstageはnormalizer失敗と検索不能をまとめていたため、追加推論なしで後者を `intent_searchability_invalid` へ分離した。固定message、本文・field値・内部例外の非保持、blocking ambiguityのquery-less投影は維持する
- EXEC-051では、固定条件を再提示して承認を得た後、使用済みCSVの先頭1件を合計1 callだけlocalhostへ送った。HTTP 200後の `draft_schema_invalid` で停止し、2件目、retry、assessmentは実行していない。追加推論なしで、生成schemaへ同値のllama.cpp互換decimal regex、ambiguity code regex、価格mode・source別9 variantを追加した。draft不一致は本文や値を保持せず固定groupへ分類する。新schemaによる実model成功、typed ranking、独立holdoutは未確認である
- EXEC-052では、再提示した固定条件への承認後、EXEC-051の生成schemaを使用済みCSVの先頭1件・合計1 callだけlocalhostで確認した。HTTP 200後、完全draft schemaと正規化を通過して `intent_searchability_invalid` で停止した。2件目、retry、assessmentは実行していない。追加推論なしで、通常経路の商品種別または全blocking確認待ちを生成時に強制し、検索不能を本文や値なしの `missing_terms`・`invalid_terms` groupへ分けた。次schemaによる実model成功、typed ranking、独立holdoutは未確認である
- EXEC-053では、固定条件を再提示して承認を得た後、生成時検索可能性schemaを使用済みCSVの先頭1件・合計1 callだけlocalhostで確認した。HTTP 200後にstrict intentとtyped proposal生成まで成功し、proposalは `blocking` となった。2件目、retry、assessment、商品取得、rankingは実行していない。本文非保持のためblocking理由は断定せず、次はquery-less blockingを第1確認へ返して後続providerを止めるorchestrator境界を追加model callなしで扱う
- EXEC-054では追加model callを行わず、orchestratorをtyped proposal先行へ変更した。readyだけが従来のquery必須 `IntentReview` を使い、blockingはquery fieldを持たない専用 `BlockingIntentReview` とquery digestなしのsessionへ結ぶ。blocking確認から画像生成または画像なし続行へ進む操作は追加provider予約前に固定errorで拒否し、query付きblocking、queryなしready、binding改ざんも拒否する。legacy現行検索、API、UIには接続しない
- EXEC-055では、固定条件を再提示して承認を得た後、使用済みCSVの先頭1件を現行orchestratorへ合計1 callだけ通した。233.419秒・HTTP 200・2,508 bytesでstrict intentとtyped proposalを処理し、typed status `blocking`、query plan・query digestなしの `BlockingIntentReview` へ到達した。2件目、retry、assessment、Cloudflare・Outscraperの予約・call、商品取得、rankingは実行していない。本文非保持のためblocking理由と妥当性は断定せず、独立holdoutまたはproduction成功として扱わない
- 2026-09-05の利用者判断により、未知データによる独立評価は実施しない。既存の評価contractと固定policyは維持するが、`pass` を推定せず、typed ranking品質は未確認、画像rankingは無効のままとする。新しい評価data、追加model call、dataset assessmentは用意・実行せず、将来再開する場合は新しい明示判断と適格な未使用dataを必要とする
- 事前固定したholdout policyを最初の適格な2 category・4 caseへ適用した。localhost Bonsaiの4応答は全てstrict検証で失敗し、失敗caseを除外せずassessmentを `fail` と確定した。ranking前に停止したため商品順位は未測定である。利用者指定により同じCSVを再利用するが、結果確認後の修正へ使ったためdevelopment regressionとしてだけ扱い、独立holdout合格とはしない
- 商品検索の正本providerをBonsaiとし、OpenAI商品検索案を置換済みの履歴へ移した。AIレビュー用OpenAI経路は別系統として維持する
- `agents-setup` テンプレートにないMarkdownの内容を標準文書へ統合し、統合元を `docs/old/` へ移した
- 現行・次期検索の検証区分、offline gate、次期画面の受入確認、live試験の個別承認境界を [DEVELOPMENT.mdの統合済みテスト方針](DEVELOPMENT.md#統合済みテスト方針) へ統合し、元の `TESTING.md` を `docs/old/` へ移した
- ルート [SEARCH-FLOW.md](../SEARCH-FLOW.md) を、次期商品検索を利用する人の操作・確認・回復フローへ再編し、技術契約とテスト手順の重複を分離した
- 画像ランキングを色、外観形状、商品種別など画像で確認できる特徴だけの補助評価とし、有線・無線は商品名と構造化された観測属性で判定する設計へ固定した。画像scoreは構造化属性を推定、補完、上書きせず、画像componentは本品質評価まで無効のままとする
- case3で広い外観scoreがexact条件を分離できなかった結果を受け、自然文をnamespace付きkey・値型・演算子・重要度へ分ける型付き条件、trusted registry、条件ごとの `match`・`mismatch`・`unknown`・`conflict`、必須状態を総合scoreより先に扱うrankingを設計した。外部通信を持たない最小domain、Bonsai候補・商品証拠adapter、typed-ranking-v4を実装し、次期offline検索の第1確認から履歴までschema 3.0 / 2.0で接続した。生成4方向画像は外観参照だけに使い、候補集合内のcenter・z-scoreは採用せず、画像無効状態を維持する
- 初期registryの `mouse.connection` に固定alias `ワイヤレス` を追加し、商品証拠adapterが専用fieldとfeature全体をtitleより優先して裁定へ渡す境界を実装した。商品説明、一般数値、画像、LLMは証拠抽出に使わず、legacy現行ranking-v3を変更していない
- 固定CLIP入力をcenter cropから、縦横比を維持して画像全体を224×224内へ収め、残りを正規化後0となるモデル平均値で埋めるapplication profileへ変更した。profile IDをruntime digestへ含め、旧embeddingとの混在を拒否する。再計測ではcase1 AUC 0.759259259、接続方式を除く視覚評価AUC 0.928571429、case2限定診断AUC 0.642857143・期待順位一致27/53となった。追加したcase3限定診断はAUC 0.468750000・期待順位一致80/173であり、画像componentは無効のままである
- 利用者によるcase別整理に合わせ、既存のcase1画像品質testと実process smokeの参照先を `tests/img/case1/` へ移した。固定画像byteとSHA-256は変更していない
- 実行処理へ接続されていなかった `APP_ENV` と `LOG_LEVEL` を `Settings` と `.env.example` から削除した。旧環境値は未知項目として無視し、観測可能性の設定は実装時に処理と同時に追加する
- 実行時promptを `.txt` へ分離し、コードとテストの参照を更新した。元Markdownは `docs/old/runtime/` へ保存した
- `AGENTS.md` をテンプレートの必須構造とamazon-explorer固有の安全規則が両立する形へ更新した
- [HARNESS-RUNBOOK.md](HARNESS-RUNBOOK.md) を現行CLIと標準文書の役割分担に合わせ、実行コマンド、期待結果、停止・再実行規則へ再編した
- `HARNESS-RUNBOOK.md` はユーザー指定どおり独立した現行正本として統合・移動の対象外にした
- 統合元、旧設計、Execution Plan、旧検証資料を [旧文書アーカイブ](old/README.md) へ集約し、現行正本と履歴資料を分離した

### Verification boundary

- 2026-09-06のEXEC-057追加benchmarkでは、明示承認されたlocalhost最大8 attempts、出力1 token、retry 0、credential・外部network・費用なしの条件で、Core i5-13600KF・WSL2・CPU版を測定した。変更前相当cache無効の有効2計測はwall中央値142.559秒、request v6のcache warm 3計測は中央値1.236秒で、約115.3倍・99.13%短縮した。cold単一比較は144.863秒から40.715秒で約3.56倍だった。変更前の1 attemptはclient側から中断しretryせず、全8 attemptsを超えていない。server停止とport非listenを確認した。記録後の標準gateはlock 79 packages、Ruff 197 files、offline pytest 1,661 passed / 9 skipped / 1 deselected、Python 3.10 AST 197 files、Markdown・`git diff --check` 成功だった。この結果はprompt処理の限定比較であり、このbenchmark単独ではfull JSON、strict intent、実検索E2E、Core Ultra、Vulkan性能を示さない
- 2026-09-05のEXEC-056では、local job受入testをscaffoldへ当てたREDが13 failed、production実装後のfocusedが13 passed、全search_v2が924 passed / 9 skipped、標準gateがlock 79 packages、Ruff 197 files、offline pytest 1,661 passed / 9 skipped / 1 deselected、Python 3.10 AST 197 files、Markdown・`git diff --check` 成功となった。一時SQLiteと注入callbackだけを使用し、現行Streamlit、実検索callback、実provider、credential、外部通信、課金、browser、フロントエンドは実行・確認していない
- 2026-09-05のEXEC-055では、model・CSV・prompt・完全schema・生成schema・canonical body・request・orchestrator・一時runnerのdigest、request schema 5.0、`max_tokens`・HTTP timeout不在、port・process状態を照合し、`/health=200` 後に先頭1件を合計1 callだけ現行orchestratorへ通した。233.419秒、HTTP 200、2,508 bytes、transport call 1、Bonsai利用量 `succeeded`、typed status `blocking`、query plan・query digestなしの `BlockingIntentReview` だった。2件目、retry、assessment、商品取得、ranking、Cloudflare・Outscraperはない。server停止、port非listen、対象process・一時runner・一時directory不在を確認した。関連offline回帰は195 passed。標準gateはlock 79 packages、Ruff 195 files、Markdown 16 files・1,266 links・865 anchors・1,580 headings・199 fence pairs、offline pytest 1,648 passed / 9 skipped / 1 deselected、Python 3.10 AST 195 files、`git diff --check` 成功である。blocking理由・妥当性、条件分解・商品順位品質、独立holdout、production E2E、画像、Windows native、browser、フロントエンドは未確認である
- 2026-09-05のEXEC-054では、query-less blockingの受入REDが3 failed / 1 passedとなった後、production変更だけで新規4 passed、orchestrator・state全体39 passed、typed・query・approval・Cloudflare・Outscraper・product pipeline・history・holdout後処理の関連回帰235 passedとなった。標準gateはlock 79 packages、Ruff 195 files、Markdown 16 files・1,256 links・855 anchors・1,565 headings・199 fence pairs、offline pytest 1,648 passed / 9 skipped / 1 deselected、Python 3.10 AST 195 files、`git diff --check` 成功である。実Bonsaiの追加call、使用済みCSVの再評価、未知データ、実Cloudflare・Outscraper、credential、課金、画像、Windows native、browser、フロントエンド、AIレビューハーネスは実行・確認していない
- 2026-09-05のEXEC-053では、固定model・使用済みCSV・更新prompt・完全schema・16,663 bytesの生成schema・canonical body・request schema 5.0・`max_tokens` とtimeout不在を確認し、`/health=200` 後に先頭1件だけを送った。HTTP 200、`finish_reason=stop`、473 tokens、2,508 bytes、395.713秒でstrict intentとtyped proposal生成まで成功し、proposalは `blocking` となった。transport call 1、retry 0で、2件目・再試行・assessment・商品取得・rankingはない。server停止、port非listen、process終了、一時runner削除を確認した。focused 87 passed、関連回帰187 passed、標準gateはlock 79 packages、Ruff 195 files、Markdown 16 files・1,241 links・840 anchors・1,549 headings・199 fence pairs、offline pytest 1,644 passed / 9 skipped / 1 deselected、Python 3.10文法AST 195 files、`git diff --check` 成功である。blocking理由、typed条件の意味品質、商品順位、独立holdout、production E2E、実provider、画像、Windows native、browser、フロントエンドは未確認である
- 2026-09-05のEXEC-052では、固定model・使用済みCSV・更新prompt・完全schema・EXEC-051の生成schema・canonical body・request schema 5.0・`max_tokens` とtimeout不在を確認し、`/health=200` 後に先頭1件だけを送った。HTTP 200、`finish_reason=stop`、143 tokens、1,187 bytes、252.845秒で `intent_searchability_invalid` となった。EXEC-051の `draft_schema_invalid` はこのcaseで解消し、完全draft schemaと正規化まで通過した。transport call 1、retry 0で、2件目・再試行・assessmentはない。server停止、port非listen、process終了、一時runner削除を確認した。生成時検索可能性・診断のREDは11 failed / 76 passed、GREENは87 passed、関連回帰187 passedである。標準gateはlock 79 packages、Ruff 195 files、Markdown 16 files・1,231 links・830 anchors・1,536 headings・199 fence pairs、offline pytest 1,644 passed / 9 skipped / 1 deselected、Python 3.10 AST 195 files、`git diff --check` 成功である。次schemaによるlocal model成功、独立holdout、typed条件・商品順位、production E2E、実provider、画像、Windows native、browser、フロントエンドは未確認である
- 2026-09-05のEXEC-051では、固定model・使用済みCSV・更新prompt・旧生成schema・canonical body・request schema 5.0・`max_tokens` とtimeout不在を確認し、`/health=200` 後に先頭1件だけを送った。HTTP 200、`finish_reason=stop`、257 tokens、1,613 bytes、117.242秒で `draft_schema_invalid` となった。transport call 1、retry 0で、2件目・再試行・assessmentはない。server停止、port非listen、process終了、一時runner削除を確認した。旧記録由来の誤ったbody・request digestでは送信前に停止し、canonical値へ訂正した。生成schema・診断のREDは10 failed、GREENは85 passed、関連回帰185 passedである。標準gateはlock 79 packages、Ruff 195 files、Markdown 16 files・1,221 links・820 anchors・1,524 headings・199 fence pairs、offline pytest 1,642 passed / 9 skipped / 1 deselected、Python 3.10 AST 195 files、`git diff --check` 成功である。新生成schemaによるlocal model成功、独立holdout、typed条件・商品順位、production E2E、実provider、画像、Windows native、browser、フロントエンドは未確認である
- 2026-09-05のEXEC-050では、固定model・使用済みCSV・更新prompt・生成schema・request schema 5.0・1 body・`max_tokens` とtimeout不在を確認し、`/health=200` 後に先頭1件だけを送った。HTTP 200、`finish_reason=stop`、143 tokens、1,183 bytes、102.333秒で `intent_normalization_invalid` となった。transport call 1、retry 0で、2件目・再試行・assessmentはない。server停止、port非listen、process終了、一時runner削除を確認した。原因別diagnosticのREDは1 failed / 1 passed、GREENは4 passed、関連回帰150 passedである。標準gateはlock 79 packages、Ruff 195 files、Markdown 16 files・1,211 links・810 anchors・1,512 headings・199 fence pairs、offline pytest 1,638 passed / 9 skipped / 1 deselected、Python 3.10 AST 195 files、`git diff --check` 成功である。独立holdout、typed条件・商品順位、production E2E、実provider、画像、Windows native、browser、フロントエンドは未確認である
- 2026-09-05のEXEC-049では、段階診断付き部分再計測で完了2件が `query_plan_invalid`、送信済み3件目が手動中断、4件目が未送信となった。部分実行のassessmentは生成せず、訂正後の追加model callは0件である。実2件の直接原因は本文非保持により未確定のまま、同じstageを生む検索可能性contractを合成入力で再現した。REDは2 failed / 1 passed、GREENは3 passed、関連回帰172 passed、標準gateはlock 79 packages、Ruff 195 files、Markdown 16 files・1,201 links・800 anchors・1,499 headings・199 fence pairs、Markdown test 4 passed、offline pytest 1,638 passed / 9 skipped / 1 deselected、Python 3.10 AST 195 files、`git diff --check` 成功である。一時runner不在、port非listen、`llama-server` processなしを確認した。更新promptのlocal model確認、独立holdout、production E2E、実provider、画像、Windows native、browser、フロントエンドは未確認である
- 2026-09-05のEXEC-048では、追加model callなしのoffline TDDで、本文非保持の後処理4段階、ready経路、query-less blocking、query-less ranked拒否をfocused 23件、typed・holdout関連126件、全search v2 898件 / 9 skippedで確認した。標準gateはlock 79 packages、Ruff 195 files、Markdown 16 files・1,187 links・786 anchors・1,483 headings・199 fence pairs、offline pytest 1,635 passed / 9 skipped / 1 deselected、Python 3.10 AST 195 files、`git diff --check` 成功である。Bonsai再推論、実4件の段階再計測、独立holdout、実provider、画像、Windows native、browser、フロントエンドは未確認である
- 2026-09-05のEXEC-047 health-ready再実行では、固定model・CSV・生成schema・4 body・`max_tokens` とtimeout不在を確認し、`/health=200` 後にlocalhostへ4要求を逐次各1回、retry 0で送った。全件HTTP 200、`finish_reason=stop`、strict intent成功だったが、その後は `postprocess_failed` となった。failed 4を除外しない元reportは `not_assessed`、assessmentは53 checks中45件未達の `fail` であり、typed条件・商品順位の品質値ではない。追加model callなしの合成診断後、server停止、port非listen、process終了、一時runner削除を確認した。標準gateはlock 79 packages、Ruff 193 files、Markdown 16 files・1,174 links・773 anchors・1,467 headings・199 fence pairs、offline pytest 1,627 passed / 9 skipped / 1 deselected、`git diff --check` 成功である。独立holdout、production E2E、Cloudflare・Outscraper・画像・フロントエンドは未確認である
- 2026-09-05のEXEC-047初回実行では、固定model・CSV・生成schema digest、request schema 5.0、4 body、`max_tokens`・timeout不在を確認後、localhostへ4要求を逐次各1回送った。全件model ready前の `request_failed`、response 0 bytes、completion token不明で、coverage適格、failed 4、ranked 0、元report `not_assessed`、assessment 53 checks中45件未達の `fail` だった。health-only再現で `/health` の503から200への遷移を確認し、server停止、port非listen、process終了、一時runner削除まで完了した。標準gateはlock 79 packages、Ruff 193 files、offline pytest 1,627 passed / 9 skipped / 1 deselected、Markdown 16 files・1,172 links・771 anchors・1,464 headings・199 fence pairs、`git diff --check` 成功である。request v5の生成品質、strict条件抽出、ranking、独立holdout、production E2Eは未確認である
- 2026-09-05のEXEC-046では、request v5の生成schema・別digest・tamper拒否・完全schemaによる最終拒否をfocused 44件、関連114件、全v2 890件 / 9 skippedでoffline確認し、llama.cpp version 9294のC++・Python converterが生成schemaをgrammarへ変換できることをmodel・HTTPなしで確認した。標準gateはlock 79 packages、Ruff 193 files、offline pytest 1,627 passed / 9 skipped / 1 deselected、Markdown 16 files・1,161 links・760 anchors・1,452 headings・199 fence pairs、Markdown test 4 passed、`git diff --check` 成功である。request v5によるlocal model、strict条件抽出、ranking、独立holdout、production E2Eの成功はまだ示さない
- 2026-09-05のEXEC-045では、明示承認後にlocalhost限定の同じ4件をrequest v4、時間上限なし、retry 0で実行した。4件とも約313〜326秒でHTTP完了後に `content_not_json` となり、coverage適格、failed 4、ranked 0、元report `not_assessed`、assessment 53 checks中45件未達の `fail` だった。raw response・検索文・商品情報を保存せず、server停止、port非listen、process終了を確認した。最終gateはlock 79 packages、Ruff 193 files、offline pytest 1,625 passed / 9 skipped / 1 deselected、Markdown 16 files・1,148 links・747 anchors・1,436 headings・197 fence pairs、`git diff --check` 成功である。これはstrict条件抽出、ranking、独立holdout、production E2Eの成功を示さない
- 2026-09-05のEXEC-044では、Bonsai request v4から生成token上限とHTTP timeoutを削除する受入4件と、Bonsaiから履歴までの関連172件をofflineで確認した。lock 79 packages、Ruff 193 files、offline pytest 1625 passed / 9 skipped / 1 deselected、現行Markdown 16 files・local link 1132件・anchor 731件・heading 1422件・fence 197組、`git diff --check` も成功した。この時点では時間上限なしのlocalhost Bonsaiを実行しておらず、後続結果はEXEC-045へ分離した
- 2026-09-05のEXEC-043では、Bonsai request v3、JSON object宣言、application output-token上限なし、本文非保持の段階診断をoffline TDDした。新規受入10 passed、関連159 passed、全offline pytestは1628 passed / 9 skipped / 1 deselectedである。lock、Ruff、Markdown、差分検査も成功した。その後の承認済みlocalhost development regressionは4件全てが旧300秒timeoutで `request_failed` となり、server停止とport非listenを確認した。これは時間上限なしのrequest v4、実provider、browser、production E2Eの成功を示さない
- 2026-09-05のEXEC-042では、localhost限定のlocal Bonsaiへ明示承認済みの4 callsを行い、4件全てが `bonsai_response_invalid` となった。credential、外部network、retry、server log、prompt cache、画像、Cloudflare、Outscraperは使わず、serverを停止した。focused 44 passed、lock 79 packages、Ruff 193 files、offline pytest 1620 passed / 9 skipped / 1 deselected、Markdown test 4 passed、現行正本16 Markdownのlocal link 1107件（うち見出しanchor 706件）・heading 1394件・fence 197組、`git diff --check` を確認した。この `fail` は条件抽出のstrict出力を受理できなかった結果であり、条件分解の意味精度、商品順位、production E2Eを測定した結果ではない
- 2026-09-04の作業ツリーでlock 79 packages、Ruff・Python 3.10 AST 191 files、EXEC-040 focused 117 passed、Markdown検査focused 4 passed、全v2 854 passed / 9 skipped、offline pytest 1591 passed / 9 skipped / 1 deselected、現行正本16 Markdownのlocal link 1081件（うち見出しanchor 682件）・heading 1363件・fence 197組、`AGENTS.md` 目次15件、`git diff --check` を確認した。固定ONNXを読む明示opt-inはEXEC-040では再実行していない。直前の記録は15 passed / 1 xfailedで、xfailはcase1 AUC 0.759259259による既知の基準未達だけである。case2限定診断のAUC 0.642857143・期待順位一致27/53とcase3限定診断のAUC 0.468750000・期待順位一致80/173を変更せず、画像componentを無効のまま維持した
- offline pytestは外部APIをモック・遮断しており、Bonsai、Outscraper、OpenAI、Cloudflare、ブラウザ、live 7-phase workflowのE2E成功を意味しない
- この節の文書標準化は、コミット後にマージ済み節へ移すまで `Unreleased` のままとする

## 2026-08-16 — AIレビュー配備文書と初期化記録（`5080440`）

### Added

- AIレビューの開発規約、運用runbook、TASK-006とTASK-007のExecution Planを追加した
- 配備前提、初期request生成、未検証のlive境界を参照文書へ記録した

### Changed

- task、負債、制約、security、worklogをattested reviewの実装状態と残作業へ同期した

## 2026-08-16 — Attested AI review TDD harness（`ba18dd9`）

### Added

- strict task、policy、gate、review、TDD evidence、verdict、attestationのschemaと検証modelを追加した
- snapshot、offline runner、review packet、分離broker、fixed egress、署名、attested judge、7-phase protocolの実装を追加した
- coordinator、offline runner、broker、egress gatewayのdigest-pinned container定義を追加した
- Python 3.10 / 3.13のlock、Ruff、offline pytest、diff checkを定義するGitHub Actionsを追加した
- trust boundary、network policy、broker、attestation、workflowを対象とする回帰テスト群を追加した

### Security

- 通常pytestでIPv4、IPv6、主要DNS解決、Requests経路を遮断し、`live_api` markerと `--run-live-api` の二重opt-inを導入した
- candidate、credential、外部packet、runtime、nonce、費用予約を別境界へ分離し、fail-closedな検証を追加した

このコミットのコード・fixture・テスト追加は、OpenAI APIのlive成功、課金、release hostでのfull workflow完了を単独では証明しない。

## 2026-08-16 — 検索fallbackと診断表示の堅牢化（`f57db1e`）

### Fixed

- 日本語・英語queryがない場合の推定商品名fallbackも、空文字とURLを拒否する共通検証へ通した
- Streamlitのdebug表示へ色と特徴の条件語重みを追加した

### Added

- query fallback、APIキー欠落時の外部呼出し抑止、Streamlit表示用関数の回帰テストを追加した

## 2026-08-15 — リポジトリ文書の統合（`2fd9c5b`）

### Added

- backend、frontend、security、database境界、requirements、constraints、troubleshooting、task、plan、worklog等の目的別文書を追加した
- `AGENTS.md` をMarkdown文書の入口として再編した

### Changed

- 旧cache、data model、environment variable、external API、production design、developer READMEの内容を目的別文書へ統合した
- READMEを新しい文書構成へ同期した

### Removed

- 統合後に同じ情報を重複保持していた旧6文書を削除した

## 2026-08-14 — 商品検索の堅牢化とリポジトリ整理（`fb2115a`）

### Added

- `.env.example`、例外型、project-root path、JSON cache repository、現行 `src` を直接対象にするテストを追加した
- 旧段階別コードを `examples/legacy-phases/` へ参照用として分離した

### Changed

- Bonsai応答検証、Outscraper task状態分類、HTTPS・同一origin結果URL検証、redirect拒否、上限付き再試行を強化した
- 商品属性、Amazon商品、価格、真偽値の正規化とランキング境界を強化した
- 入力・設定・内容を含むcache key、TTL、Streamlit session scope、アトミックJSON書込を導入した
- Streamlitでは詳細例外をserver logへ残し、利用者には固定エラーを表示するよう変更した

## 2026-05-28 — 初期商品検索アプリ（`91d6b48`、`1c51cd0`、`a571d92`、`aa117a8`、`29746e3`）

### Added

- Streamlit入口、設定、Pydantic model、Bonsai・Outscraper client、商品正規化、SudachiPy・TF-IDF採点、JSON utilityを含む初期アプリを追加した
- `pyproject.toml` と `uv.lock` によるPython依存管理を追加した
- READMEとGit除外設定を追加した

### Fixed

- 初期追加後に、project設定とアプリ入口を小さく修正した

先頭コミットの件名は `v1.0.0` だが、Git tagは存在しないため、この文書ではrelease versionとして扱わない。

### Candidate実テストの停止診断（2026-09-10）

新candidate実テストの結果JSONに `failure_diagnostic` を追加した。視覚応答の構文/終了状態/要確認/条件検証とHTTP・query準備の停止境界を固定codeで識別できる。応答本文や機密値は含めず、既存の拒否・保留基準を維持する。実サービスでの再検証は未実施。

### 視覚条件の生成候補を制限（2026-09-10）

価格・数量・既知の非視覚条件と一意な商品名詞句を、Bonsaiへ渡す視覚候補から除外した。要求と受信側で同じ候補集合を検証し、検索queryと価格条件は保持する。商品句を一意に分離できない場合はproduct_scopeで確認待ちになる。実モデルによる再検証は未実施。


### Candidateの比較可能なスコアを保持（2026-09-10）

検索計画に保存された原語英訳をタイトル採点へ接続した。画像の相対順位は候補集合の校正成否に依存させず、1件・片側/同点分布・一部条件だけの比較でも利用できる点数を保持する。同じ画像を使う別商品にも埋込みを再利用する。画像不在・全条件の計算不能・不正データの拒否と明示必須条件の優先順序は維持。新candidate-lexical-clip-v3と旧履歴を識別し、既存結果を再採点しない。


### 2026-09-10: 属性別の形状比較を追加

Bonsaiの視覚提案に比較対象部位を追加し、確認済みのshape条件をローカル領域抽出・輪郭比較・candidate順位・履歴へ接続した。旧focusなし条件と旧履歴は維持。形状欠測を全体CLIPで埋めず、他の比較可能な条件を保持する。CLIPSeg資材は別途設定する実験経路であり、実商品の切出し品質は未達。


### 2026-09-10: 個体分離と部位輪郭の改善

任意設定のCLIPSeg＋MobileSAM抽出器をcandidateの画像評価へ追加した。複数商品を一つのmaskへ結合せず、個体選択と部位選択を分ける。背景への意味応答の混入、小さな高確信度断片への偏り、選択した個体外へのはみ出しを抑える。旧設定と履歴は保持し、固定した別CPU環境で検証する。未知カテゴリの品質とiGPU性能は未確認。


### 2026-09-10: 条件ごとの形状特徴を評価

確認済みの形状条件へ測定項目と希望方向を追加し、側面の膨らみ・滑らかさ・投影縦横比を個別比較できるようにした。参考/偽画像が対象特徴を区別できない場合や希望と逆方向の場合は、その条件だけ保留する。測定値を記録する新しいcandidate/履歴profileを追加し、旧条件・履歴は保持する。実商品の総合順位や実Bonsaiの測定種別判断は未検証。

### 2026-09-10: 膨らみの参照画像生成と事前検査を改善

確認済みの膨らみ条件から、両側面の張り出しと直線を明示する生成要求を作る。表面の角張りだけで偽画像を作らないよう指定した。candidateでは生成後に参照の輪郭変動への耐性を検査し、差不足/逆方向/抽出不能なら画像承認と検索を止める。生成済み利用量は保持し、自動再生成しない。side_bulgeを使う場合は参照用の領域抽出器が必要。新prompt契約はv2で、既存の完了履歴と商品採点式は維持する。


### 2026-09-10: 商品全体の外観類似度をcandidateの既定へ変更

未知カテゴリでも専用形状測定を要求せず、CLIPによる参考/偽画像との全体外観類似度で採点する方式を接続した。Bonsaiは視覚条件と対象句を提案し、膨らみ等の測定種別は選ばない。参考画像・偽画像の確認は維持する。画像点を部位一致や仕様充足の証拠にせず、全体外観と明示する新しい結果/履歴profileを追加した。旧方式は明示選択時だけ残し、既存履歴は変更しない。専用の参照輪郭検査は既定では実行しない。
