# 開発目標

## EXEC-167: 条件を入力順で重み付けする

状態: 実装・対象回帰完了。全体gateに既知失敗、一般ブラウザ回帰に未完を残す。作成/更新: 2026-09-14。

目的: 同じ分類の条件では原文で先に記した語句を重くし、条件の並べ替えを順位へ反映する。対象はcandidateの日本語/日英最大値採点、画像あり/なしの順位、保存・表示と回帰。否定、タイトル、優先、希望、文章対画像、画像対画像、レビューの分類順と各条件の一致点は維持する。画像自体の採点とproviderは変更しない。

判断: 分類内の入力位置順にN..1の重みを用いた正規化加重平均とする。同じ入力位置は同じ重みとし、欠損も分母へ含める。source-order-linear-v1を任意の集約profileとしてplan/履歴へ保存し、新digestで旧形式と分離する。旧planは従来平均を使い、旧履歴を補完・再採点しない。

手順: 入力順逆転と分類ごとのREDを記録し、位置の固定・採点・履歴・表示を実装する。同じtestのGREEN、日英/価格/外観混在、互換性、改変拒否、offline全体、Ruff/format/lock/Markdown/diff、frontend型/単体/build/fixtureを検証する。実検索、実推論、画像生成、外部送信、課金は実施しない。

互換性/復旧: schema5の任意fieldと省略serializerを使い、保存済みJSON/digestを保持する。今回の差分だけでrollbackし、作業開始時の未コミット変更を残す。結果、RED/GREENのhash、未検証範囲は完了時に記録する。


実装結果: condition_weighting.pyで入力開始位置を固定し、candidate_text/candidate_bilingualで分類内のN..1平均を計算する。日本語/日英それぞれの個別一致点は維持。新規plan/履歴の任意集約profileとweightをdigestへ含め、画像あり/なしの履歴保存・再読込で保持する。旧fieldなしのplanでは従来平均とJSONを保持し、保存planの位置改変と保存点のweight改変を拒否する。共通内訳の「重み」列は新規条件だけへ出し、既存の説明文非表示方針を維持した。

RED: `uv run --frozen --offline --no-sync pytest tests/test_condition_order.py -q --tb=short` はexit1・12 failed。一致点が2/3となる期待に対して既存平均の0.5だった。初回test SHA-256は375f492a5b691d1160c52c40e88f3403c4ba8af2c970457a54fd57df6df3e887。同一12例を変えず実装後は成功。追加境界テストを含む最終同コマンドはexit0・20 passed。最終hash=d3dfb0e651fdd18d967a9ab6df906294c1e897c9df47238406dcd69f87d5079a。追加例の初回失敗2件はfixtureのJPY currency不足と、既存の同位置からの構造/外観2条件を考慮しない期待値だったためfixtureを修正した。

画面RED: frontendの `npm test -- src/condition-weights.test.ts` は重み列なしでexit1・1 failed/1 passed、初回hash=bac5c2c16815a75e41e858c123c024a2d1c0c3ca8905de0801cb144fd8ba98f8。実装後exit0・2 passed。最終hash=8691b052ae780b4ca6a6d94911dc6fb7e8dae763ea1cbddf483281560d43bffb。重み・元の一致点・旧形式の列省略を検証する。途中の説明文の期待は、既存の説明非表示方針に合わせて除去した。

検証:

- `uv run --frozen --offline --no-sync pytest tests/test_condition_order.py tests/test_candidate_text_scoring.py tests/test_candidate_bilingual_scoring.py tests/test_candidate_text_boundaries.py tests/test_candidate_connected_flow.py tests/test_candidate_search_retry.py tests/test_image_free_browser.py tests/test_candidate_priority.py tests/test_candidate_exclusion_priority.py tests/test_visual_text_priority.py tests/test_siglip2.py -q --tb=short`: exit0、158 passed。最後に追加した保存plan位置改変1例は上記20件で別途成功。
- `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short`: exit1、3497 passed/22 skipped/30 deselected/1 failed（最終境界8例の追加前）。test_graph_root_evidence_tolerates_only_runtime_managed_leaf_ctime_driftがos.utime前後のctime不変で失敗。既知の無関係な環境依存失敗であり全体合格とはしない。
- frontendの `npm run check`、`npm test`（112 passed）、`npm run build`: exit0。途中にe2eの整形不一致があり、対象ファイルのPrettier後にcheckを再実行。
- `npm run test:e2e -- --config playwright.connected.config.ts connected.spec.ts -g 'source-order weights'`: exit0、1 passed。実candidateコードと一時SQLiteの合成fixtureで、日本語条件2倍/1倍、結果・履歴・再読込をキーボード操作で確認。
- `npm run test:e2e -- visual-scores.spec.ts`: exit0、1 passed。キーボード操作でモックの結果と履歴の重み列を確認。
- 一般のconnected-parityはクリック前のvisible/enabled/stable待ちで2件timeout、5 passed/1 interrupted/9未実行として停止。mock visual-scoresも同じ待ちと撮影の待ちで失敗したため、採点表示の対象testをキーボード操作とDOMの表示検査に限定し、撮影を除去。マウス操作一般とスクリーンショットの成功は主張しない。
- Ruff check/format425 files、offline lock、Markdown/diff: exit0。

境界: 実モデル推論、商品検索、画像生成、credential利用、課金、commit/push、稼働serverの再起動は未実行。稼働serverのGETではquery（確認待ち）を確認したため、その準備済み検索を保持して再起動していない。変更適用済みprocessで新しく準備する検索から有効。既存process/準備済みplan/保存履歴の点を切り替えない。全体ctime検査と一般ブラウザ回帰の残件はISSUESに引き継ぐ。

## EXEC-166: 空行による条件誤判定と修正位置を直す

状態: 修正・関連回帰・稼働serverへの反映完了。作成/更新: 2026-09-14。

目的: 条件整理で空行を曖昧な希望/否定と扱い、無関係な商品名を修正箇所に表示する問題を修正する。関連: [ISSUES.md](ISSUES.md)、[BACKEND.md](BACKEND.md)。

調査: 稼働APIの失敗コードmodifier_scopeを確認し、入力をログ/ファイルへ保存せずローカルGiNZAと視覚条件抽出まで再現した。末尾の空白だけのfragmentをinterpret_clauseが空条件として拒否し、start未指定でoffset=0になっていた。全文の希望/否定解析は正常で、利用者が指摘した商品名の解釈が失敗原因ではない。

範囲: parserの空白だけのfragment除外、視覚条件の空白防御と原文位置保持、合成回帰、文書、ローカル反映。実入力はテスト/文書へ複製せず、独立した合成文で検証する。モデル/分類規則/順位/旧履歴/追加provider実行は変更しない。

手順: 合成parser tokenと注入structureで空行・空白・誤ったエラー位置のRED。最小修正後に同じtestのGREEN、関連と全offlineを実行。稼働中のstateは保持し、処理が進行中でなければ同じ起動設定と入力をメモリ内だけで引き継いでserverへ反映する。自動の条件整理/モデル推論/画像生成/商品検索はしない。

境界/復旧: API GETでの確認とローカル構文解析だけを使い、provider/credential/課金なし。先行する修正を保持し今回の差分だけrollback可能にする。実際の入力全文・例外本文・モデル応答はログへ出さない。結果と残る制約を追記する。


実装: GiNZAの条件fragmentの両端から空白tokenを除き、空になったfragmentを返さない。視覚条件側でも空白だけのfragmentを防御的に除外する。断片内でConditionLanguageErrorが発生した場合はstart/endに原文内の開始位置を加え、実際の問題箇所を返す。

RED/GREEN: `uv run --frozen --offline --no-sync pytest -q tests/test_blank_condition_fragments.py --tb=short` は実装前9 failed（exit1、0.38秒）。空行/CRLF/空白/tabの誤解析と、局所offsetが商品名を指す問題を確認。初回SHA-256=e39b72f5e2bc59aaa912192116110cc75929fb531ccd615763a9f7376e028fa5。同一testの修正後は関連4suiteと合わせて100 passed。実GiNZAの合成文回帰1件と整形を追加した最終hash=0ca239ac524873848701acdbe0902b30d10e385a545ce5c9a5bd1324abbef910。

検証: `uv run --frozen --offline --no-sync pytest -q tests/test_blank_condition_fragments.py tests/test_lexical_runtime.py tests/test_condition_language.py tests/test_candidate_visual_conditions.py tests/test_image_free_browser.py --tb=short` は101 passed（exit0、3.70秒）。全offline `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は3484 passed/22 skipped/30 deselected/1 failed（exit1、98.16秒、最後のGiNZA回帰追加前の収集）。既知のtest_graph_root_evidence_tolerates_only_runtime_managed_leaf_ctime_driftがos.utime前後のctime不変で失敗したため全体合格とはしない。Ruff check/format423 files、offline lock、Markdown/diff成功。

稼働反映: 実入力をメモリ内だけでローカル構文解析し、空fragment0・視覚句抽出成功を確認。停止中のclarificationでinstance/revisionが不変なのを確認し、同じ起動設定と入力をstdin経由で引き継いでserverを再起動した。入力と履歴一覧の一致、新instanceのidleを確認。GETだけを許可したChromiumで入力一致・「条件を整理」有効・pageerror0を確認した。生入力を引数/ファイル/ログへ出していない。

制約: 実モデルの条件整理・画像生成・商品検索は再実行していない。今回の実入力検証は失敗したローカル解析境界までであり、実サービスE2Eの成功は主張しない。frontendは変更しておらず、先行する型/単体/配信検証を維持する。credential利用・課金・commit/pushなし。


## EXEC-165: 接続失敗の種類を記録して表示

状態: 実装・関連回帰・稼働serverの配信確認完了。作成/更新: 2026-09-14。

目的: 状態取得失敗の一律表示を改め、一時的に失敗して復帰した場合も通信・timeout・HTTP・JSON・状態検証のどこで失敗したか確認できるようにする。関連: [EXEC-164](#exec-164-条件整理の再起動後の停止を解消)、[ISSUES.md](ISSUES.md)。

範囲: frontendの状態GET/command POSTに固定コードの診断を追加し、現在のエラーと接続診断欄へ表示する。診断は同じタブのsessionStorageへ最大10件だけ保持し、回復・再読込後も参照可能にする。時刻・操作種別・所要時間・HTTP status・固定の検証理由だけを保存する。入力/URL/要求応答本文/例外原文/stack/credential/商品情報は保存しない。新規provider要求、検索再送、既存履歴DB、モデルや順位、サーバーの再起動は対象外。

手順: 注入fetchの異常種別と秘匿、ブラウザの一時障害→復帰→再読込保持→再送なしのREDを確認。typedな固定診断と安全な有界保存・表示を実装し同じtestでGREEN、型/整形/単体/buildと関連ブラウザ回帰を確認する。実障害を起こすために稼働server/推論を停止しない。

判断/復旧: 生例外を出さず、未知の失敗はunknownとして記録する。診断保存不能でも画面内では保持し、検索状態の取得を妨げない。前回の過去障害は記録がなく遡及特定できない。今回のfrontend差分だけでrollbackし、先行変更を保持する。結果・hash・未検証範囲を追記する。


実装: connected-apiの状態GET/command POSTを同じ診断付き要求処理へ集約し、ヘッダー待ちと本文読込のtimeout、通信中断、HTTP非成功、JSON構文、状態検証を区別した。schemaには20種類の固定検証項目を対応付け、生例外を引き継がない。ConnectedAppは現在のalertを具体的な原因へ変更し、直近10件の折り畳み「接続診断」を追加。sessionStorageからの読込・保存で許可fieldだけを再構築し、未知情報は保持しない。保存不能時も画面内の診断と検索状態取得を維持する。

RED/GREEN: `npm test -- src/connection-errors.test.ts` は実装前6 failed/1 passed（exit1）、エラーに種別のdiagnosticがないため失敗。初回SHA-256=1d9bee08cdadf11cd75755caf6384925623ba639bf77edd210359e8f26bd94dd。同一testの実装後は7 passed（exit0）。後から中断/本文転送失敗2件と整形を追加した最終hash=3a04ffe6f167c96820408891b7b97fb9fbde47021fa4389a8b057586f65153d0。保存/再読込・10件上限・未知field除去・不正保存値・保存不能・未分類秘匿の4件も追加し、同fileのhash=4cc9645b675f72e99c6aeb5c62c99a9dbc77a9348bc66c0a502b4b32ee58e342。

ブラウザRED: `npm run test:e2e -- --config playwright.connected.config.ts connected.spec.ts -g 'connection diagnosis'` はHTTP 503の具体表示期待に一律エラーで失敗（exit1、5.2秒）。初回test hash=ae29910a94ec756ff48202added8b5028847dc61b7eeeab967e94891a96b5905。テストの期待を維持した整形後に復旧・再読込保持・再送0のGREENを確認し、さらにnetwork/json/schemaの3件を追加。最終hash=2c093ed06c284459f5ff5a80527deaac3b9ef282740e15725bc8917a74e445a7。

検証: `npm run check`、`npm test`（110 passed）、`npm run build` はexit0。`npm run test:e2e -- --config playwright.connected.config.ts connected.spec.ts -g 'connection diagnosis|open browser recovers|expired server'` は6 passed（exit0、7.3秒）。合成APIの各失敗、復帰/再読込後の診断、再送なし、既存の再起動/期限表示を確認した。fixtureの短いテスト終了時に静的資材送信のBrokenPipeが出たが、診断本文や実利用者情報は含まない。Ruff/format422 files、offline lock、Markdown/diffもexit0。

稼働反映: serverの再起動なしでbuildを更新。8765番へ新しいChromiumからGETだけで接続し、新診断bundleの配信・「条件を確認」表示・pageerror0・server instance/revision不変を確認した。既存タブには再読込で適用する。状態/要求本文はログへ出していない。実障害を誘発するための停止、モデル起動/再推論、画像生成、検索、外部API、credential利用、課金、commit/pushなし。

制約: 導入前の一時エラーは遡及特定できない。networkはブラウザが隠す接続拒否/接続断等の内訳を断定せず、ブラウザから確定できる失敗境界を記録する。前段で確認済みのChromium描画フレーム停止が空HTMLでも続くため、クリックを含む全E2Eは未実施。新診断の操作はキーボードで確認した。Python実装は未変更で、Python全機能回帰は再実行していない。

## EXEC-164: 条件整理の再起動後の停止を解消

状態: 修正・合成回帰完了。実際の停止時のエラー照合は未確認。作成/更新: 2026-09-14。

目的: 同じ条件で再試行する際、作業先の残存や画面の古い更新番号によって条件整理が進まなくなる問題を修正する。関連: [ISSUES.md](ISSUES.md)、[BACKEND.md](BACKEND.md)、[FRONTEND.md](FRONTEND.md)。

調査: live_stepsは初回作業先をexist_ok=Falseで作成するため、同じoutput-dirで再起動すると既存directoryで失敗する。ConnectedAppはrevisionの小さい状態を無条件で捨てるため、server再起動後のrevision=0を表示できない。現在8765番のserverは稼働しておらず、利用者の失敗時の状態・エラー本文は未確認。モデル応答の揺らぎやGPU停止を今回の障害原因と断定しない。

範囲: 起動ごとのprivate作業先の分離、履歴保存先の保持、server instance識別と古い状態/commandの拒否、合成回帰と関連文書。モデル設定・プロンプト・日英採点・順位・旧履歴の再取得/再採点・自動推論retryは対象外。

手順: serverを同じ作業先で2回起動するfixtureと、ブラウザを開いたままserver識別子/更新番号が変わる回帰でREDを確認する。最小実装後に同じテストのGREEN、関連Python/UIと標準offline gateを確認する。実サービス・モデル推論・課金を追加しない。fixtureの結果は本番E2Eと区別する。

境界/復旧: 入力・provider応答・credentialをログへ出さず、既存のprivate modeとsymlink拒否、準備3回・worker1本・確認操作を維持する。履歴DBのschemaと保存点は変更しない。今回の差分だけを戻せるよう、先行する未コミット変更を保持する。RED/GREENのコマンド・hash・結果・残る制約を追記する。

実装結果: 起動ごとのsession-ID配下に準備を分離し、同じprivate output-dirで再起動しても前の作業先と衝突しない。履歴DBは元のrootに維持する。BrowserSearchはinstanceIdを状態へ付け、新UIから異なるinstanceIdのcommandを受けた場合はrevisionが一致しても拒否する。画面は同一instance内でのみrevisionを比較し、再起動後のidleを受理する。command開始前のpoll結果は破棄する。旧client/モックの省略形式を維持した。

RED/GREEN: `uv run --frozen --offline --no-sync pytest -q tests/test_browser_restart.py --tb=short` は初回3 failed（exit1、1.18秒）。既存rootで準備境界へ0回しか到達しないこと、instanceIdの欠落を確認した。REDのSHA-256はa8501f93c4771a530eea23283bc121ed097266fe7cfe4d362bfae5793f92c992。同一内容の実装後はtest_browser_runtime/test_browser_searchと合わせて43 passed/旧作業先を期待する既存fixture1 failed。新しいnamespaceへfixtureを同期後44 passed（1.46秒）。その後private root/symlink/上書き拒否4件を追加した最終test SHA-256はa4fd1938f087ac9ef0e6b5eca1ea4ccc7996ba346bd96de4ac0cb1b343287655。

UI RED/GREEN: `npm run build` 後、`npm run test:e2e -- --config playwright.connected.config.ts connected.spec.ts -g 'open browser recovers'` で「整理中」から復帰せず条件整理ボタンが出ないREDを確認（exit1、5.6秒、初回SHA-256=b95de24f1760780cb93c814e2ee34eddcb0064aaa6079a85c5acbee1c61d50a5）。修正後のクリック検証はChromium自体のrequestAnimationFrame停止に阻まれた。空のHTMLの単一ボタンでも再現し、GPU無効/SwiftShader/full Chromium/Xvfbでも解消しなかった。再起動の期待・自動再送0回・操作1回・新instanceId/revisionの照合を維持し、入力操作をEnterへ変更。旧revision比較に戻した状態で同じ復帰失敗のREDを再確認し、修正を戻して1 passed（exit0、1.6秒）。このRED/GREENで同一のtest SHA-256はbf3fdb00303a193404092b5bada3da838b7d58d0687cafee6e520f5383d4b33c。誤ったcwdでのnpm開始失敗はREDに数えない。

検証: 関連7suiteは96 passed（14.22秒）。起動別namespaceでも実compositionの履歴repositoryがroot直下に固定される回帰2件を追加後、同じ7suiteは98 passed（13.64秒）。全offline `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は3473 passed/22 skipped/30 deselected/1 failed（102.25秒）。未変更のtest_graph_root_evidence_tolerates_only_runtime_managed_leaf_ctime_driftでos.utime前後のctimeが同一になる既知失敗。全体合格とはしない。Ruff check/format（422 files）、offline lock、Markdown/diff、frontend型/Prettier、Vitest97件、build成功。既存の期限切れ表示ブラウザ回帰1件も成功。

制約: クリックを含む全ブラウザ回帰は上記のChromium描画停止のため未実施。実利用者の入力/停止状態は未取得であり、今回修正した再起動不具合と元の障害の一致、実モデルの同条件再推論は未確認。8765番は稼働しておらず再起動対象がなかったため、ソースとfrontend/distの更新まで実施した。追加の実サービス・モデル起動/推論・画像生成・検索・credential利用・課金・commit/pushなし。採点・旧履歴・モデルprofileを変更していない。

追加確認（2026-09-14）: 利用者から状態取得失敗の表示を受けて再調査。今度は8765番のserverが稼働し、GETでworkingからqueryへの遷移を確認した。返却stateは現行frontendのparseSearchViewを通過し、新しいChromiumでGETだけを許可して実画面を開くと「条件を確認」が表示され、接続エラーなし・pageerror0・状態HTTP200だった。この条件整理は利用者が開始したもので、調査からのPOST/再推論/画像生成/検索は行っていない。Host=localhost:8765は既存の厳密なorigin規則で403、127.0.0.1:8765は200となることも確認した。利用者が開いているURLは照会中であり、元の接続失敗がこのHost差によるものとは断定しない。先行する「server不在」は前の調査時点の状態で、現在の稼働状態とは異なる。

## EXEC-163: Bonsaiの残存と同時起動による競合を防ぐ

状態: 実装・ローカル反映完了。全体回帰には既存ctime依存の失敗1件が残る。作成/更新: 2026-09-13。

目的: アプリ再起動後にBonsaiが残って条件整理を妨げる問題を防ぎ、競合時は理由を表示する。Linux/WSLの起動元終了に連動する子process停止と、同一user/portの起動排他を共通launcherへ追加する。既存の通常終了・timeout回収を維持する。

範囲: Bonsai起動helper、共通runtime、ブラウザへの固定競合エラー、offline回帰とローカルアプリ反映。外部プロセスの無差別停止・接続流用、推論自動retry、モデル/プロンプト/順位/履歴の変更、実推論・画像生成・商品検索・外部API・課金・commit/pushは含めない。

手順: 合成listenerで親SIGTERM/SIGKILL/異常終了後のport解放と再起動、起動競合、外部listener保護、固定エラー表示のREDを作る。同じテストでGREENを確認し、関連/全体offline、Ruff、lock、Markdown/diffを実行する。実モデル品質や本番E2Eとは区別する。

境界: 生入力/応答/credentialを診断へ保存しない。PID探索による自動killを追加せず、起動時にOSへ登録した子だけを回収する。新しい排他はprocess寿命に従って解放し、残存PIDファイルを作らない。既存非Linux経路は維持し、Linux以外へ今回の保護を主張しない。

判断: 現行はstart_new_session=Trueとfinally回収のみで、親の強制終了ではfinallyが実行されない。親終了連動はthreaded親のpreexec_fnを使わず、別の短いPython起動helperで設定して同じPIDのままexecする。排他はLinux abstract Unix socketを同一user/port単位で保持する。

復旧: このPlanのlauncher/helper/固定エラー差分だけを戻す。先行する未commit変更、iGPU設定、検索入力と既存履歴を保持する。

実装結果: 共通launcherでGPU確認前に同一user/portのabstract socketを排他取得し、子へ継承する。Linux helperは親PIDを登録前後で検査してPR_SET_PDEATHSIG/SIGKILLを設定し、同じPIDでexecする。特権付きexecと登録失敗は拒否する。起動元終了時に子と排他が解放される。BonsaiPortBusyErrorをブラウザadapterで固定表示へ変換し、他processの停止・接続流用・推論retryは追加していない。

RED/GREEN: `uv run --frozen --offline --no-sync pytest -q tests/test_bonsai_lifecycle.py --tb=short` は修正前6 failed/1 passed（18.64秒、exit 1）。親SIGTERM/SIGKILL/os._exit後の子残存、待受前の二重起動、汎用エラーしか返らない状態を確認。RED時のtest SHA-256は05a7484d581310ea2c30fbc5b5b0375f5948151cc59e2c88daa2785720613d20、fixtureは1851fb310ed5e72e385e964589081667c048aa87d61f09995458b66691802d22。同一内容で修正後7 passed（5.19秒、exit 0）。最初のnetwork guardとPythonビルドのpidfd未提供による試験準備失敗はREDに数えず、標準guardを変更せずcredential-free subprocess内の合成loopback検証へ分離した。

追加回帰: exec失敗・spawn失敗後の排他解放、親終了の登録前後race、prctl失敗時の停止を追加。対象6 suiteは99 passed/2 skipped（8.38秒）。全offlineは3466 passed/22 skipped/30 deselected/1 failed（95.79秒）。失敗は未変更のtest_graph_root_evidence_tolerates_only_runtime_managed_leaf_ctime_driftで、os.utime前後にctimeが変わらない既知事象。全体合格とはしない。Ruff check/format（421 files）、offline lock、Markdown/diffは成功。

ローカル実行確認: 同じiGPU設定の既知の未使用processを一度回収し、更新launcherで実モデルを起動。health-ready後に起動元をSIGKILLし、モデル終了・18080番の解放・同じ排他の再取得を確認（12.35秒）。推論0回、画像生成・商品検索・外部API・credential利用0回。モデル品質と本番検索E2Eの証拠ではない。

反映: 8765番の接続serverを修正済みコードへ再起動し、API idle/HTTP200、元入力の一致、履歴一覧の一致を確認。入力をargv/file/logへ保存せずstdinで渡し、次のrun保存先を分離した。既存履歴を再採点していない。Frontend資材の変更がないためbuild/実ブラウザ操作は再実行していない。更新前または直接起動したBonsaiにはOS保護を後付けできず、自動kill対象にも含めない。非Linuxの保護と実条件整理の再推論は未検証。未commit/push。

## EXEC-162: 文章対画像と画像対画像の採点分離

状態: 実装・本番ローカル反映完了。全体回帰には既存ctime依存の失敗1件が残る。作成・更新: 2026-09-13。

目的: 視覚条件の文章と商品画像のSigLIP 2比較を独立追加し、既存の否定・タイトル・優先・希望の後で文章対画像、画像対画像、レビューの順に比較する。新しいprofileで旧順位と保存履歴を維持する。両経路の点数を共通結果/履歴UIへ表示し、モックと本番接続に反映する。

方式: 確認済み視覚条件のmatching記述（除外はopposite）を固定SigLIP 2 tokenizer/text encoderへ渡し、正規化した商品画像特徴とのcosineを0〜1へ写像する。条件別の最小値を文章対画像点とする。参考画像・対比画像はこの点の計算に使わない。既存の画像対画像点はそのまま保持し、重み付き合成で順位を決めない。欠損は未評価として扱い、旧履歴に点を補完しない。

手順: 優先順位逆転のRED、採点/有界worker/結合/保存互換/APIの実装、欠損・除外方向・改変拒否・旧profileの回帰、共通UIとfixture更新、Pythonゲートとfrontend型/単体/build/両ブラウザ経路を確認する。生入力・画像・応答をログへ記録せず、追加の本番商品検索/画像生成/外部APIは行わない。新しいローカル文章encoderは既存固定資材を使い追加量子化しない。

復旧: 新規profileと追加任意fieldを外す場合も旧履歴を破壊しない。先行するBonsaiビルド設定・未コミット差分を保持し、今回の範囲だけを戻せるようにする。結果と制約を完了時に追記する。


実装結果: 既定をsiglip2_text_imageへ変更し、文章用workerとVisualTextBatchを独立追加した。生成画像の区別が不能でも文章経路の点を計算できる。文章条件別最小点と既存画像点を別々に保存し、新profileで文章点を先に比較する。画像特徴は共用し、文章encodeは最大1 batch、条件は最大3件、600秒を上限とする。Bonsai/iGPU設定や既存の画像encoder/モデル資材は維持した。

RED/GREEN: tests/test_visual_text_priority.pyは文章点0.8対0.7・画像点0対1、および文章点0対欠損で希望順が逆になる2件のRED（exit 1）を確認。SHA-256=b1b3a6ab23279ddc4bd66eb400a20478ccc20d59c4b1ffb19632d98daeea56f8。同一内容で実装後22 passed、後からformatだけ適用。UIのvisual-scores.test.tsは独立点がなく不正な負値が受理される2件のRED（exit 1、SHA-256=39cead18a0680dad3eeb1cb9691a8fb068efb8072b8e9a86616df11a2eb452f1）、同一内容で2 passed。初回UIコマンドのcwd違いとtsx未収録はREDに数えない。追加の画像なしfield拒否は有効な対照入力を用いたRED（SHA-256=db4a0d9a8b9a067f144f80d73380e164192a88ab352e93ae47ead3f72fcd8554）から3 passed。いずれもテストの意味を保ったformatを後で適用した。

検証: 最終関連112 passed（4.89秒）。文章/画像の逆転・欠損・除外反転・複数条件最小値・不正embedding・生成画像が区別不能な場合の独立性・profile混在拒否・日英内訳・SQLite保存/再読込・旧方式を検証した。全offlineは3452 passed/22 skipped/30 deselected/1 failed（98.40秒）。失敗は未変更のtest_graph_root_evidence_tolerates_only_runtime_managed_leaf_ctime_driftで、os.utime前後にctimeが変わらない既知事象。全体合格とはしない。この後の追加2回帰を含む関連112件は成功し、Python実装変更はない。Ruff check/format（418 files）、offline lock、Markdown/diffは成功。

UI: 型/Prettier、Vitest97件、build成功。ビルド配信のモック41件（2.2分）と本番API経路の合成fixture26件（25.1秒）が成功。画像なしguard追加後は接続関連3件（6.8秒）、開発配信の新スコア・controls/motion/frame/navigation15件（20.2秒）も成功。共通の検索詳細で文章点を画像点より上に表示し、新profileの合成点は隠す。モック履歴の保存後にも独立点が残ることを確認し、スコアカードのスクリーンショットを目視確認した。

ローカル実モデル: 既存固定SigLIP 2の文章workerは2文/768次元/有限値で成功（6.742秒）。続けて合成単色画像1枚の実画像encodeと文章比較を実行し、1条件の比較点0.558239を得た（12.494秒）。これはローカル計算経路の確認であり、実商品の順位品質や属性充足精度の合格とはしない。外部商品画像取得・画像生成・商品検索・追加課金は行っていない。

本番反映: 8765番のブラウザserverを新コードへ再起動し、API idle/HTTP200、既存履歴1件と旧詳細HTTP200を確認。実Chromeでも新ラベルを含む本番bundle配信、保存結果の表示、pageerror0を確認して検索画面へ戻した。元履歴DBを保持し、今回の新規run先だけ分離した。新しい点は次の画像あり検索から適用し、保存済み商品を再採点していない。commit/pushは行っていない。

## EXEC-161: Bonsaiの3ビルド分離とiGPU既定化

状態: ビルド分離・設定・iGPUブラウザ試験は完了。精度同等性と連続実行の安定性は未確定。作成・更新: 2026-09-13。

目的: 元のCPU版、EXEC-160で試した最適化版、iGPU版を独立して保持し、設定ファイルの既定をiGPUにする。最適化版の名称は速度向上の保証を意味しない。ユーザーの今回の指示に従い、実推論の試験はiGPU版だけに限定する。

手順: GPUとQ1_0対応backendを調査し、同じllama.cpp sourceから別build directoryへ構築する。元の実行ファイルをhash付きで保持し、CPU/OpenBLAS/iGPUの設定を用意する。設定読込・起動引数・不正設定拒否のRED/GREENを確認し、ブラウザの所有processへ接続する。iGPUへの実際のoffloadと合成入力の応答検証を確認して、稼働アプリへ適用する。

境界: GGUF、プロンプト、条件分類、応答検証、採点、既存履歴を維持する。iGPU設定時にCPUへ暗黙fallbackしない。認証情報を子process環境へ渡さない。公開build依存の取得とローカル合成推論だけを行い、画像生成・商品検索・課金・commit/pushは行わない。

復旧: 設定のactive profileで明示的に元のCPU版へ戻せるようにする。3ビルドの資材と前回の履歴を上書きしない。GPUが利用不能の場合は専用の固定例外で停止し、iGPU実行成功と誤報しない。

進捗: WSLの/dev/dxgからMesa Dozen 26.2.2でIntel Arc 140V（vendor 0x8086、device 0x64a0、integrated GPU）を確認。SYCL backendはQ1_0未実装のためVulkanを選択。元のCPU版105ファイルをbuild-originalへhash付きで保存し、build-optimizedはRelease/native/OpenBLAS、build-igpuはRelease/native/Vulkanとして同一source f12cc6d0fa96d6a3c33952f06b7439ac43a3c3feから構築完了。

設定実装: bonsai-runtime.tomlのactive=igpuを既定にし、profileごとの実行ファイル・library pathを準備開始ごとに読み込む。iGPUはdevice名の照合、全層offload指定、fit off、FP16行列演算経路無効を適用。親のcredential環境は継承しない。CPUへの自動fallbackは追加しない。

TDD: 新しいtests/test_bonsai_profiles.pyはmodule未実装でRED（exit 2）。テストSHA-256=`531c72e181d9623e5828d97c3627425adc1f1bae7e2cb1bfc7b1ee17f11b5a62`。実装後、同ファイルとtest_bonsai_live_e2e/test_browser_runtimeで61 passed/2 skipped。テストの意味は維持し、未使用importと不要f-stringだけ整理した最終SHA-256=`6c6aba452439150bd56f06a48c07700dd2417649e528f575688817cb9f2b7fbd`。既存browser composition fixtureの設定注入先を新しいloaderへ更新した。

ビルドと回帰: build-originalは元の105実体ファイルのhash一致を確認。build-optimized/igpuはそれぞれserverと共有ライブラリ9実体ファイルをmanifest付きで保存。CPU2版の実推論は実行していない。loaderへ移した設定注入をimage-free/WordNetの既存fixtureでも更新し、関連117 passed/2 skipped。全offline再検査は3442 passed/22 skipped/30 deselected（125.45秒）。初回のfixture3件と既存Git metadata/ctimeの一時的な失敗は再検査で解消し、検証条件は弱めていない。

初期iGPU試験（非同期有効）: デバイス検出成功、37/37層のGPU配置とVulkan model buffer 932.68 MiBを確認。形状29.552秒、別起動の部品29.783秒、希望/除外17.337秒で応答検証/条件保持に合格。ただし最初の連続試験の部品条件で検証拒否が1回あったため、キャッシュ依存を追加検証する。CPUとの応答本文hashは一致せず、GPU/CPU出力の完全一致や未知入力の品質保証は主張しない。startup配置ログはllama.cppのtrace levelが必要だったため、試験側で取得levelを修正し、数値だけ記録した。

追加検証: cache無効でもcontrast_proposalで拒否されたため、cache無効化は採用しない。ブラウザの最初のiGPU試験はWSLのdxgvmb_send_sync_msg待ち・CPU進行0を観測し、約300秒で所有model processを停止して失敗を確認。履歴1件は保持。Vulkanの非同期backendを無効にする互換設定を追加した。環境検査テストは必要keyの欠落でRED（exit 1）、SHA-256=`de781d02b4c7e7f488c670ecc04b30c85c2abaced2d87c7c7d234654caf13f92`。同一テストのまま関連117 passed/2 skippedでGREEN。同期設定の最終結果は以下のとおり。


最終iGPU試験: 同期実行・FP16経路無効の設定で37/37層をIntel Arc 140Vへ配置し、Vulkan model buffer 932.68 MiB、起動7.798秒を確認。形状例は44.265秒で形式検証と条件保持に合格した。一方、続く部品例では外観条件が空となり、診断側のNone処理不足でAttributeErrorも生じた。この試験は不合格とし、条件欠落を成功へ読み替えない。モデル・プロンプト・既存検証の緩和や再量子化は行っていない。CPUとの本文hash不一致に加えて失敗例もあるため、精度同等性は未確認である。

ブラウザ実行: 同じ同期設定を8765番のアプリへ反映し、実Chromeから合成入力の画像あり条件整理を実行。87.083秒でquery段階へ到達し、形状・価格条件、検索語5件、画像生成ボタン有効を確認した。実行processはbuild-igpuのserver、GGML_VK_DISABLE_ASYNC=1を使用。既存履歴1件を保持し、アプリをこの構成で稼働継続する。画像生成・商品検索は押していない。成功1回を連続実行の安定性保証やCPU版との厳密な速度比較とはしない。数値・合否だけの記録はrepo外のbonsai-igpu-ui-check.jsonへ保存した。

最終回帰: 同期設定後の関連117 passed/2 skippedは成功。全offlineは3441 passed/22 skipped/30 deselected/1 failed（112.45秒、exit 1）。未変更のtest_graph_root_evidence_tolerates_only_runtime_managed_leaf_ctime_driftがos.utime前後でctime同一となり失敗し、全体合格とはしない。同期設定前の3442 passedとは区別する。Ruff check/format、lock整合、Markdownリンク、diffの静的検査を実施。CPU2版のモデル実行は今回行わず、3ビルドの実体とhash/依存分離を確認した。

## EXEC-160: Bonsaiの条件整理の遅延を精度を維持して調査

状態: 実行復旧を確認。恒久修正は未完了（原因未特定）。作成・更新: 2026-09-13。

目的: 画像ありの条件整理が5分以上完了しない現象を切り分け、モデル・原文条件・既存の確認操作を維持して改善する。対象はローカル実行環境と起動設定。モデルの小型化・追加量子化、プロンプトの省略、未完了応答の受理、採点/履歴の変更は行わない。

手順: 同じモデルで入力処理/生成を測定し、並列度・BLAS・待機方法を比較する。設定変更は回帰のRED/GREEN後に評価し、効果がなければ戻す。合成条件例の厳密な検証と同一要求の応答hash比較、ブラウザの条件整理まで確認する。外部画像生成・商品検索・credential利用を追加せず、raw要求/応答を診断ログへ残さない。commit/pushは行わない。

判断: 最初のbenchmarkは8スレッドで入力10.65/生成0.88 token/s、4スレッドで13.55/10.39 token/sだった。しかし再測定では4スレッド14.42/10.86、8スレッド19.04/12.13 token/sとなり優劣が逆転した。同一実要求も8スレッド77.188秒、4スレッド111.335秒だった。4スレッド固定で常に12倍改善するという結論は成り立たず、暫定変更を撤回した。CPU quotaのthrottling記録は0で、初回遅延の原因をCPU性能やスレッド数だけへ特定できていない。

環境比較: 同じllama.cpp sourceからのOpenBLAS版は4スレッドで入力7.54 token/sと遅く不採用。元の実行ファイル105件のhash一致を確認して復元し、追加BLAS共有ライブラリは実行先から退避した。poll=0の8スレッドは入力19.39/生成11.71 token/sで有意な改善なし。利用CPUを4個へ制限した競合条件でもpoll=50/0は入力14.59/14.47、生成7.92/7.83 token/sで改善せず、待機設定も変更しない。OpenBLAS packageは環境に残るが実行backendには使わない。

精度確認: 元の非BLAS版・4スレッドで形状111.335秒、部品112.101秒、希望/除外116.866秒。3件ともfinish_reason=stop、厳密なparse_visual_response成功、原文条件とstrength保持。同一形状要求の8スレッド実行は要求・応答本文・検証後結果のhashが4スレッドと完全一致。最初の部品/希望の試験文は既存構文解析が曖昧として拒否したため、対象商品を明示した合成文に直した。解析・応答検証は緩和していない。有限例の成功を未知入力全体の精度保証としない。

資材: Bonsai GGUF SHA-256=`284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54`。モデル、元の非BLAS実行ファイル、プロンプト、schema、context、生成上限、推論設定を最終的に変更していない。repo外のbonsai-comparison.jsonへhash・時間・合否だけを保存した。

暫定変更のTDD: `uv run --frozen --offline --no-sync pytest -q tests/test_bonsai_live_e2e.py -k command` はthreads指定の欠落でexit 1。テストSHA-256=`9cb8235799002b89b11ac4b5a2fb5a2f69c24ead5da688619b346ce03eb2bf81`を保持したGREENは `uv run --frozen --offline --no-sync pytest -q tests/test_bonsai_live_e2e.py tests/test_browser_runtime.py` で51 passed/2 skipped。設定に速度改善の根拠がなく、実装・テスト・起動手順の暫定変更をすべて元へ戻した。

回帰確認: lock、Ruff check/format（412 files）、Markdown 17文書、diff check成功。合成APIの接続Playwrightは26 passed（25.4秒）。全offline pytestは3431 passed/22 skipped/30 deselected/1 failed（102.90秒）。失敗は未変更の `test_graph_root_evidence_tolerates_only_runtime_managed_leaf_ctime_drift` でos.utime前後のctimeが同一になるもの。単独suiteも68 passed/1 failed、ext4 basetempでも再現。全体合格とはしない。

実画面: 元の推論構成でアプリを再起動し、合成入力の画像あり条件整理が116.165秒でquery段階へ到達。形状と価格条件、検索語候補5件、参考画像生成ボタンの有効化を確認。既存履歴1件を保持し、画像生成/商品検索は実行していない。アプリは127.0.0.1:8765の確認画面で稼働中。

結果と残課題: 再起動後の正常動作は確認したが、恒久的な遅延解消や初回の根本原因は確認できていない。再発時はホスト負荷と各推論の入力/生成時間を同時に測り、同条件で再現する原因を特定してから最小修正を行う。効果のない性能設定を修正済みとして残さない。最終差分はこの調査記録とWORKLOGだけで、モデル・コード・設定・履歴は維持する。

## EXEC-159: 不要資料をbinへ退避して追跡を解除

状態: 退避・追跡解除・検証完了（未コミット）。作成/更新: 2026-09-13。

目的: 利用者の指示に従い、現行実行・回帰に不要な資料をローカルの `bin/` へ集約する。対象は統合済み旧文書36件、呼出元のない旧段階サンプル6件、対象外となったresponsiveデザインPNG1件、直前の合成UI検証出力。現行ソース・旧履歴互換・テストfixture/画像・現行デザイン参照・モデル・環境・実履歴とcacheは維持する。

手順: Gitと参照関係の調査、移動元/先とSHA-256のローカルmanifest作成、上書きなしの移動、対象だけのindex削除、root限定ignore、現行文書リンクの統合先への更新、退避物なしの文書検査・offline回帰。未コミットの既存変更を保持し、commit/pushは行わない。コードの振る舞いを変更しないため新規TDDは不要。

復旧: `bin/cleanup-20260913.json` の対応とhashを確認して元の場所へ戻し、必要な対象だけGitへ再登録する。退避物は削除せず、過去commitも書き換えない。binはcloneに含めないため、現行文書・検証がbinへ依存しないことを確認する。

結果: 対象43件をGit indexから除去し、`/bin/` のignoreを登録した。旧文書36件・旧Pythonサンプル6件・旧responsive PNG1件と、前回の合成UI検証出力を合わせて133ファイル・17,537,187 bytesをローカル保存した。全移動先のSHA-256一致、ignore、index非登録、予定外のstaged削除なしを確認。/tmpからの単純renameは別filesystemのため失敗し、copy後のhash検証を経て移動を完了した。

検証: `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は3432 passed/22 skipped/30 deselected（83.46秒、exit 0）。Ruff check・format（412 files）、現行17文書のMarkdown検査、binを含まない非ignoreファイルの一時コピーでの文書検査、作業差分/staged差分のcheckは成功。前回の未追跡ソースを含む現行コード・fixtureと履歴互換を維持した。Frontendソース/buildには変更がないためブラウザとbuildは再実行していない。実サービス・実履歴への操作とGit履歴の書換えは行っていない。追跡解除43件と.gitignoreだけをstageし、既存変更を含む現行文書の更新は未stageで保持する。

## EXEC-158: モック共用画面の目視確認と表示修正

状態: 修正・目視確認完了（未コミット）。作成/更新: 2026-09-13。

目的: 目視確認の利用者指示に基づき、幅1440/1280のChromiumで合成入力の主要画面・ダイアログを撮影し、重複と崩れを確認する。履歴案内の重複/余白不足、比較画像ラベルの折返しによる位置ずれ、採点表見出しの途中改行を確認した。

範囲: 共用React表示部品と視覚回帰。API/モデル/実履歴/採点値は変更しない。手順: 合成スクリーンショット目視、再現RED、最小の余白/配置修正、型・build・関連ブラウザ、修正後の目視。既存未コミット変更を保持し、rollbackは今回の表示修正のみ。モバイルは現行desktop仕様の対象外。実データ・外部通信は使わない。

RED: `npm run test:e2e -- visual-layout.spec.ts --workers=1 --forbid-only` は3 failed（exit 1）。履歴案内2件、カード上端14px差、表見出し2行を再現した。RED test SHA-256=`65cb8f951908dbb90f25240261f9c54dd82fa1b5c27b5a64dac11f103f2baa11`。

結果: 履歴の保存案内を1つにまとめ、案内・内容間に24pxの余白を設けた。画像ギャラリーは同じ行のカードを同じ高さにし、ラベルの折返し分を吸収して画像の上端を揃える。採点表の列見出しだけ途中改行を防ぎ、条件名の折返しは維持する。

検証: frontendで型/整形 `npm run check`、Vitest `npm test` 94件、`npm run build` 成功。`npm run test:e2e -- visual-layout.spec.ts results.spec.ts navigation.spec.ts --workers=1 --forbid-only` は8件成功。同コマンドに `UI_TEST_MODE=development` を指定した開発版も8件成功。`npm run test:e2e -- --config playwright.connected.config.ts --workers=1 --forbid-only` は合成API26件成功。最終visual-layout test SHA-256=`3ce0d2b24ee8bb1078a119b2c31c97422cd645be4aa069ca4576d4f7e620b08b`。RED後のテスト変更は整形のみ。

目視: ローカルChromium、DPR1、幅1440/1280px・高さ1000pxで入力、条件確認、画像生成中/参考/比較/最終確認、調査/完了、結果、履歴一覧/詳細、画像拡大、中止/再生成/削除/破棄ダイアログ、画像なし、保存失敗を撮影した。修正後42枚は `bin/ui-visual-20260913/after/` にローカル保存（EXEC-159で/tmpから退避）。主要画面・修正箇所・ダイアログを目視し、確認範囲で重複・重なり・横のはみ出しを認めなかった。全42状態で文書の横幅、可視h1の単一性、画像欠損、pageerrorを検査し問題0件。外部要求/APIはrouteで拒否し、固定合成入力のみ使用。実サービス・実履歴・他ブラウザ・モバイルの確認ではない。対象文書のリンクと差分検査も成功。

## EXEC-157: オフラインモックを現行接続画面へ統一

状態: 実装・オフライン検証完了（未コミット）。作成・更新: 2026-09-13。

目的: オフラインでも接続画面と同じ条件編集、画像確認、最終確認、調査、結果、履歴を操作できるようにする。利用者の今回の実装指示を根拠とし、旧モック固有の画面を共用画面へ置き換える。

範囲: frontendの画面とデータ供給境界、タブ内合成履歴、シナリオ、関連テスト・文書。任意入力を保持し、固定合成条件・商品・ローカル画像を使用する。実API、モデル、画像生成、商品検索、credential、課金、実履歴DB、商品順位の計算は対象外。既存の未コミット変更を保持する。

手順: 接続画面とモックの差分を確認し、共通条件編集のブラウザREDを固定する。検索/履歴のデータ供給を注入可能にし、既定入口だけオフライン実装を渡す。画像選択の再整理、準備3回、画像2回、明示確認、保存再試行、中止、期限を模擬する。型/整形・Vitest・build・全モックブラウザ・接続fixture・開発版視覚回帰・Markdown/diffを検証する。

判断: 画面を二重に保守せずConnectedApp/ConnectedHistory/ConnectedProductsを共用する。通信を差し替えるグローバルfetch hookは使わず、明示したデータ供給境界でモックを閉じる。保存はsessionStorageの別versionとし旧データを破棄しない。rollbackは今回の共用化とモック変更だけを戻す。

結果: Appは共用画面へのオフラインclient注入だけを行う。条件グループ、画像プロンプト、調査工程、結果、履歴は接続画面と同じ実装。固定12商品の表示画像/英語タイトルの欠損例/日英採点内訳、画像なしの画像点未使用、属性選択シナリオ、準備3回/画像2セット、保存だけの再試行、中止、期限を再現した。旧v1モック履歴は読取/削除を維持し、v2は合成スナップショットを保存する。期限切れは閲覧対象から外し、60秒間隔と履歴表示時にタブ内削除を試み、失敗時は再試行を提示する。

RED: frontendで `npm run test:e2e -- offline-parity.spec.ts --workers=1` は1 failed（exit 1）。旧モックに「優先条件」欄がなく、画像使用への切替時にも再整理を要求しなかった。最初のrootでのnpm実行はpackage.json不在によりexit 254となり、frontendへ修正後に上記REDを得た。以後の同テストは整形のみで期待を維持した。最終テストSHA-256=`d21c492d8dee41e7d07757feb65b6e8f4748217ab3ab60b05670bc89311013a6`。

検証: 型/Prettier `npm run check`、Vitest `npm test` 94件、`npm run build` は成功。`npm run test:e2e -- --workers=1 --forbid-only` は全37件成功（2.1分）。最初の回帰実行は旧モックのボタン名・画像再整理不要の操作を期待して失敗し、接続画面の現行操作に同期した。`npm run test:e2e -- --config playwright.connected.config.ts --workers=1 --forbid-only` は合成API26件成功。`UI_TEST_MODE=development npm run test:e2e -- controls.spec.ts motion.spec.ts frame.spec.ts navigation.spec.ts --workers=1 --forbid-only` は14件成功。最終の期限削除・保存時刻固定後にも型/整形・Vitest94件・build、`npm run test:e2e -- recovery.spec.ts results.spec.ts offline-parity.spec.ts --workers=1 --forbid-only` 13件が成功（14.9秒、exit 0）。履歴カード・日英採点付き結果カードのスクリーンショットを目視確認。対象7文書のMarkdownリンク/anchor検査と `git diff --check` も成功。

影響と制約: backend、実SQLite、実検索、実モデル、credential、課金を変更/実行していないため実サービスE2E・実入力理解・順位品質は未検証。Python domainを変更していないため全体pytestは対象外。オフライン表示は固定合成条件・画像・商品であることを明記する。手元の実稼働serverは再起動せず、ビルド済みフロントエンドを更新した。ブラウザ再読込で新しい画面を読み込む。旧モック専用のmodel/historyは旧保存データ・既存単体回帰用に残す。

## EXEC-156: 辞書に対比候補がない条件のBonsai補完

状態: 実装・offline検証・server反映完了。作成・更新: 2026-09-13。

目的: 辞書に対比候補が0件の条件をBonsai推論へ明示的に振り分ける。既存の補完機構を維持し、未収録と語義選択を要求内で区別する。未知の外観はmatching/opposite、未知部品はpart_enを既存の視覚推論1回で補完する。辞書未収録だけを理由に条件を落としたり保留したりしない指示を追加する。

範囲: 視覚要求の候補分類・promptとfixtureテスト。受信の原文/否定/出典検証、画像なしの推論なし、商品名/採点/履歴は維持する。条件の意味自体が不明な場合や不正応答では文章修正を維持する。新要求hashは旧要求と区別され、既存計画/保存画像は再生成しない。

手順: 未収録外観・部品・既知/曖昧語義の振り分けRED、最小実装、専用/関連/全体offline、文書同期、待機中serverへの反映。実モデル/画像生成/検索/課金は行わない。入力/履歴を保持し、rollbackは今回の要求分類/promptだけを戻す。現状では補完受信は実装済みだが、辞書候補なしを要求で明示していない。

RED: `uv run --frozen --offline --no-sync pytest tests/test_wordnet_contrast.py -k 'missing_' -q --tb=short` は4 failed/1 passed/24 deselected（exit 1）。専用要求fieldが存在せず、candidate接続の合成Bonsaiでも同fieldを参照できなかった。RED SHA-256=`61b43f2609f27722a37795d2523ca929684ccfb6443d931629ac150104e14ed3`。

GREEN: `uv run --frozen --offline --no-sync pytest tests/test_wordnet_contrast.py tests/test_attachment_contrast.py tests/test_visual_contrast.py tests/test_image_free_browser.py -q --tb=short` は86 passed（exit 0）。未収録/既知/多義の分離、未知部品、1回の推論で画像指示まで到達、否定時の反転、辞書出典非偽装、画像なしの未推論を確認。最終test SHA-256=`5a884cfc80f7866124275ba175773bd24cdc230286d8b3dc141be34fbb94d075`。Ruff/format・offline lockは成功。全体offline `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は3386 passed/22 skipped/30 deselected（75.69秒、exit 0）。Markdown/diffも成功。8772を修正版へ再起動し、入力と履歴4件の保持、idle、API/画面のHTTP200、新規検索なしを確認した。UIコード/履歴schemaは変更していないためfrontend build/ブラウザfixtureの再実行は不要と判断した。実Bonsaiの補完品質は未検証。

## EXEC-155: 画像なしの条件整理から比較画像検証を分離

状態: 実装・offline検証・server反映完了。作成・更新: 2026-09-13。

目的: 参考画像を使わない選択でも比較画像用の推論・対比検証が実行され、文章修正へ戻される不具合を直す。UIのstart/reviseから任意imageModeをAPI・factoryへ渡し、offでは視覚Bonsaiと対比辞書を使わず既存のローカル条件整理・商品名展開を行う。画像使用へ切り替える場合は既存の再整理操作と3回上限で準備し直す。

範囲: 接続画面、コマンド検証、runtime構成、fixture回帰。旧APIは項目省略で従来動作を保持する。日英採点・履歴形式・画像生成の承認は変更せず、実検索/実モデル/課金は実行しない。利用者入力と履歴をログへ出さない。

手順: APIのmode伝達・視覚条件を含む画像なし実行・UI送信のREDを追加し、最小実装後に関連/全体offlineとfrontend/browserを検証する。稼働中serverが処理中でないことを確認して入力/履歴を保持した再起動で反映する。rollbackは今回のmode伝達とUI変更だけを戻し、既存データを保持する。現時点では準備時の画像選択がAPIへ送信されていないことを確認済み。

実装結果: 視覚推論を省くだけでは未登録の外観句がquery_buildで止まることも確認し、画像なし準備では共通ローカル解析の原文句をfocus/contrastなしで保持する構成にした。新しい任意image_preparation=text-only-v1をplan digestへ含め、画像生成・画像採点への転用と視覚推論hashの混入を拒否する。旧field省略のJSONと既存保存結果は保持する。

RED: `uv run --frozen --offline --no-sync pytest tests/test_browser_editing.py tests/test_image_free_browser.py -q --tb=short` は2 failed/35 passed（exit 1）。APIがimageModeを拒否し、runtimeが引数を受け取れなかった。初回SHA-256はediting=`1a64a7cd2a319123f659d7c381e824a4722d4a681507f85c06dbff8e00970736`、image-free=`9df05f4ce2d636afa513e23ca30945b1f9ebb2e6c55678e2dd1b4f4bb0a0f195`。追加の条件保持REDではquery_buildが失敗。frontendの `./node_modules/.bin/playwright test --config playwright.connected.config.ts -g 'image preference reaches'` は送信値offに対しundefinedで失敗（exit 1）。先行の実行は作業directoryを重ねたパス指定誤りによりテスト追記に失敗し、修正してからこのREDを確認した。

関連GREENは40件。required/preferred/excludedの各原文外観句を画像なしで日英最大値採点し、指定なしの除去、画像生成拒否、履歴保存まで検証した。frontend check/build・Vitest80件、接続ブラウザ23件成功。初回ブラウザ回帰は画像なしfixtureのfactoryが新しい任意引数を受け取れず1件失敗し、実runtimeと同じ引数を接続して成功した。off応答には既存受信契約どおりimages=[]を付与した。最終全体offlineは3382 passed/22 skipped/30 deselected（76.97秒、exit 0）。Ruff/format・offline lock・Markdown/diffも成功。8772へ再起動反映し、idle、API/画面のHTTP200、入力と履歴4件の保持、新規検索なしを確認した。モック全35件の初回は29成功/6失敗（2.9分、exit 1）。6件ともEXEC-150以前の履歴一覧の入力全文表示を期待していたため、商品名見出し1件/入力全文0件と削除後の見出し0件を検証するよう期待を同期した。今回の機能コードとは独立したテスト保守であり、一覧の実装は変更していない。変更した6件は同じコマンドに該当テスト名の-gを指定して6 passed（54.5秒、exit 0）。先に成功した29件と合わせて全35件を確認済み。反映後の8772をread-only Chromiumで確認し、画像オフ・入力保持・API状態不変、POST/外部要求/ページ例外0を確認した。

最終テストSHA-256: editing=`55b17e00d83956ef3c7f7ff46a232311c29efc16a7db23e4c3cc0e06dc6c37e3`、image-free=`fd4a4cd6531062be8693bba32a11bc9ee20c43a4995d137e92c8f554d3afd947`、connected browser=`1bc7fc73fb4a90de522e83d49f0b3e8ed86cc7cd03e704b575f752ade4fada6f`。追加の実モデル・商品検索・画像生成・課金は実行しない。

## EXEC-154: 部品付き条件の対比準備

状態: 実装・オフライン検証・サーバー反映完了。作成・更新: 2026-09-13。

目的: 「部品付きの製品」で部品有無の対比を組み立てられず条件整理が止まる経路を修正する。構文のproduct/fragments分離は維持し、接続方式を外観へ移さない。ユーザー入力とprovider応答は文書/fixture/logへ保存せず、別の合成部品条件で再現する。

対象: visual_contrastの有無文法、既存JMdictの英訳候補、Bonsaiの辞書ID/部品英名応答からコードで有無指示を構築、browser/CLI接続、旧profile互換。独自辞書、商品名の新しい複合語分解、商品採点LLM、追加の本番検索/画像生成/実Bonsaiは対象外。辞書にない部品名は同じ視覚Bonsai要求で短い英名だけを提案し、存在/不在の反転はコードが行う。

手順: 付き/付属/無し・原文範囲・除外反転・辞書選択・未知部品のREDを固定。文法と参照adapter/受信を実装し、候補→画像要求とブラウザのfixture回帰、全体offline・静的gateを行う。新profileで旧計画を読み替えず、履歴を再採点しない。検証後は前回の再起動指示に沿って入力/履歴を保持したサーバー再起動を行い、新検索は自動実行しない。rollbackは今回差分だけを戻し既存資材/履歴を維持する。

受入: 既存辞書の部品英訳を優先、候補IDだけの応答で有無を作成、unknown時の英名補完も1回の既存要求内。部品外の属性を変更しない。否定済み条件/指定なしを誤って再反転せず、曖昧な複合句を推測で取り込まない。最終結果と未検証境界を追記する。

実装結果: presence_conditionで単純な名詞句の部品有無を認識し、既存WordNet/JMdictの英訳候補からwith/withoutをコードで組み立てる。JMdictの語義IDのみを選ぶ応答と、未知部品のpart_enのみの応答を同じBonsai要求で検証する。文法条件以外への英名転用、否定を含む英名、未提示IDを拒否した。新規v3と旧v1/v2を区別し、既存商品名/分類/採点を保持する。

RED: `uv run --frozen --offline --no-sync pytest -q tests/test_attachment_contrast.py --tb=short` は8 failed/6 passed、exit 1。付き文法の欠落、lexicon引数未実装、ID/英名のみ応答の拒否を確認した。RED SHA-256: `75148898c2fb8cc842ff784463eac2ed4109237d9ff1283bba9e829213ce2c90`。受入期待を保ち、画像要求への接続と旧v2読取、接続方式を外観条件に含めない回帰を追加。専用17件、関連99件が成功した。関連チェックの一度目は存在しないtest filenameを指定してexit 4だったため、正しいファイル指定で再実行した。

検証進捗: 実行済みの入力はメモリ内だけでローカル解析し、構文のproduct/fragments分離は正常、部品句が既存有無規則に未対応、WordNetに部品語義なし、既存JMdictに2候補ありと確認した。新処理で2候補双方の合成ID応答から条件を構築できた。実Bonsaiの応答は再取得/記録しておらず、最終の実モデル動作や画像品質は未確認。初回全体は3368 passed/1 failedで、画像なし接続fixtureの新method未対応を修正し、画像なし14件と資材を明示mockした単独回帰1件が成功。新しい外部通信/課金は0。

最終検証: 全体 `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は3369 passed /22 skipped /30 deselected（74.19秒、exit 0）。Ruff check/format、offline lock、Markdownリンク、diff check成功。専用17件の最終SHA-256: `b6c9332a55a7a2bc157650118234562a4dc95987dd3b4d290dc0b6a99acafbdb`。8772のサーバーを修正版へ再起動し、API/画面200、idle、元入力と既存履歴4件の保持を確認した。新しい検索/モデル推論/画像生成は開始していない。未コミット。実Bonsaiでの新応答形式と画像品質の確認は後続の利用者操作で行う。

## EXEC-153: 既存WordNetと文法による対比指示

状態: 実装・オフライン検証完了。作成・更新: 2026-09-13。

目的: 独自の外観対比辞書を新規検索から外し、既存の日本語WordNetの語義とPrinceton WordNet 3.0の反対語をコードで参照する。明確な部品有無は文法で反転し、曖昧な否定はBonsaiの既存視覚要求の補助情報に留める。呼出し上限、原文分類、日英採点、画像確認は維持する。

対象: visual_contrast、WordNet読み取りadapter、Bonsai要求/検証、candidate/ブラウザ/CLI接続、関連fixture。対象外: 実Bonsai、画像生成、商品検索、課金、稼働server再起動、履歴再採点。検索用lexiconや既存DBは更新しない。既存wnjpn.dbのsynlinkに反対語がないため、公式WordNet 3.0のdata.adjを別資材として準備する。公開辞書取得のみで利用者データやcredentialは送信しない。

手順: 辞書関係/語義曖昧/文法/否定方向/旧profileのRED、read-only adapterと新profile実装、要求から画像指示までのfixture接続、関連と全体offline・静的gateを実施する。出典digestと語義を計画へ保持し、既存v1の読取は凍結した規則で維持、新規はv2で区別する。失敗/未知/曖昧を誤った反対語で埋めずBonsaiへ渡す。辞書データは別directoryに保存し自動downloadしない。rollbackは新resolver設定と今回差分のみを戻し、旧履歴・先行変更・辞書元資材を保つ。

受入: 手書き色/形対比が新規経路にない、単一語義の直接反対語が優先、複数語義/複合修飾は保留、部品有無と形容詞の否定を区別、除外の二重反転なし、追加Bonsai呼出しなし、旧JSON/digest互換。実資材の限定ローカルlookupとfixture品質を実画像品質と区別する。実Bonsaiの新要求処理と生成画像の品質は未検証。

実装結果: 独自対応表はv1読取専用へ限定。新ContrastResolverは単一語義の直接反対語、名詞語義の英訳と部品有無の文法、Bonsaiへの文法補助と辞書候補提示を使う。複数語義からの選択は同じ視覚要求のsense_idで検証し、モデルが任意の辞書出典を生成することを拒否する。日本語WordNetとdata.adjの組合せdigestをブラウザ構成に固定した。CLIは両資材pathを任意指定できる。検索用辞書や既存DBは更新していない。

検証進捗: REDは `uv run --frozen --offline --no-sync pytest -q tests/test_wordnet_contrast.py --tb=short` で新ContrastResolver未実装のImportErrorによりcollection停止。REDテストSHA-256は `a592033dfac4c96fae3c8ce570206ba761342731f3468c21727ace279745d3f3`。ログ末尾を表示したラッパーは表示コマンドの終了値を返したためpytest終了値を別保存していない。実装後の初期16件が成功し、同じ期待を保って追加の語義ID・画像接続・資材改変・版違い・ブラウザ構成を25件まで拡張した。関連77件、初回全体3347 passed /22 skipped /30 deselected（74.51秒、exit 0）。旧fixtureのnullは旧手書き確定を前提としていたため、新規経路では明示的な合成Bonsai案へ変更し、旧計画の検証はv1として保持した。

実資材: 公式WNdb-3.0.tar.gzからdata.adjとLICENSEを別directoryへ配置。既存日本語DBに反対語関係がないことを確認し、データ変換や独自辞書作成はせず原配布形式を参照した。合成6句のローカルlookupで自動2件、語義候補の取得を確認。1回測定はlookup約16.8ms、資材読込/SHA照合を含め約202msであり一般的な性能保証ではない。実Bonsai・画像生成・商品検索・課金・server再起動は未実施。



最終検証: `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は3352 passed /22 skipped /30 deselected（74.63秒、exit 0）。Ruff check/format、offline lock、Markdownリンク、diff check成功。専用25件の最終SHA-256は `ac32f416d3588bbf2590dd362153e1ccd74083807dbf75ff0f01722157c61f06`。既存対比回帰の最終SHA-256は `a03787e74d74efe9be81f7123a44e8c7e1e56d57559ace4aaf23c1baa5bc747f`。稼働中serverの再起動と実Bonsai/画像の効果確認は今回の実装検証に含めず、次回通常起動後の新規準備から適用する。未コミット。

## EXEC-152: 対比画像への具体的な変更指示

状態: 実装・オフライン検証完了。作成・更新: 2026-09-13。

ローカルの対比変換を優先し、未対応の外観条件だけ既存Bonsai視覚条件要求で対比案を補完する。追加LLM呼出しはせず、商品名用を含む準備あたり最大2回を維持する。原文条件・分類と照合用語は変更せず、画像用の一致側/不一致側の外観記述と出典を別fieldへ持つ。否定条件では参考側に不一致側、対比側に一致側を指定する。

新fieldを条件・計画・画像要求digestへ束縛し、未設定の旧JSONと旧画像要求は同じ形で読む。Bonsai応答は長さ・型・対象句・分類・対比の同一性を検証し、未対応条件の補完失敗は既存の文章修正へ戻す。ローカル対応条件をBonsaiが上書きすることは許さない。確認済み画像・既存履歴を更新しない。

検証はローカル対応/未対応、否定方向、複数条件、無効応答、旧digest互換、Bonsai要求から画像要求へのfixture接続を固定し、RED→実装→関連/全体offlineを行う。追加の実Bonsai・画像生成・検索・課金は含めない。稼働中の画像確認を保つためserverは再起動せず、新しい処理の適用は次回通常起動以降とする。生成画像の実品質保証や自動再生成は今回の範囲外。

結果: VisualContrastの任意fieldを新規candidateへ接続し、Bonsaiの既存視覚選択1回で未対応句だけmatching/oppositeを補完する。丸み/角形、胴体の膨らみ、光沢/マット、取っ手、赤/青/白/黒の明示表現をローカルで扱う。否定方向、他条件の保持、出典、元の検索語/価格の保持を検証した。未対応案の欠落・同一記述・URL/長さ/型違反、ローカル案の上書きは拒否し、ブラウザは既存の文章修正へ戻る。画像指示は新規contrast付きのみv3、未設定の旧条件はv2と従来JSONを保持する。

検証: `uv run --frozen --offline --no-sync pytest -q tests/test_visual_contrast.py --tb=short` の初回REDは11 failed/1 passed（新要求fieldとstrict受信引数が未実装、exit 1）。受入の期待は保持し、整形と追加の接続/修飾範囲テストを行った。最終専用22件、関連242件と追加の語彙接続回帰を確認。全体 `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は初回3325 passed/1 failedから、既存の「つやのない」をローカルのマット表現へ含めて3327 passed/22 skipped/30 deselected（74.75秒、exit 0）。旧fixtureの未対応条件には明示的な合成対比案を追加し、原文/否定/件数の期待を維持した。Ruff/format、Markdownリンク、diff check成功。

最終専用テストSHA-256: `227bf5490379f242bec4ec3f668b84df6609ef5a99ea7fbf28a29d7f593e6549`。追加の実Bonsai・Cloudflare・商品検索・課金は0。8772は再起動せず、既存画像2枚を保持している。確認時の状態はexpired/revision5であり、承認期限を延長していない。新指示は次回通常起動後に新しく準備する計画から有効。生成画像の実品質を今回のoffline結果から保証しない。

## EXEC-151: 履歴の再読み込みボタン削除

状態: 完了。作成・更新: 2026-09-13。

利用者指示に従い、接続画面とモックの履歴から再読み込みボタンを除去する。履歴の再表示、ブラウザ再読み込み、削除失敗の再試行と期限切れ削除後の内部更新は維持する。保存データと実検索処理は変更しない。

RED: frontendで `./node_modules/.bin/playwright test --config playwright.connected.config.ts -g 'history survives reload'` がexit 1。再読込ボタン0件の期待に対して1件存在した。テストSHA-256は `01bfd5a3b65db443f83e2585832bf9898e373ba4e16e97ac45dcfa2132c21541`。読込失敗の回帰は履歴詳細から一覧へ戻るGETで検証し、既存項目の保持とPOSTなしを引き続き確認する。

実装: 不要なボタンと空の操作領域を除去し、既存の履歴取得・削除処理は保持した。取り消す場合はボタンの表示だけを戻せる。

検証: frontend check/build、Vitest80件、接続ブラウザ21件、モック履歴1件がexit 0。最初の接続回帰は20件成功し、画像なしfixtureの初期入力反映とfillが競合して1件timeoutした。fixture初期値の待機を追加し、同じ期待のまま21件成功した。最終テストSHA-256は `b91e899e8efef9654aec05999831b6ee0a555362598e53777ec7f65a63e60bec`。再読込ボタン不在のテスト内容はRED/GREENで同一。文書リンクとdiff checkも成功。

稼働中8772/8771へ静的反映し、読取専用Chromiumで両画面の再読込ボタン0件・履歴4件を確認した。前後のAPI状態は同一、POST/外部要求/ページ例外0。serverの再起動や追加本番検索・推論・課金は行っていない。

## EXEC-150: 履歴一覧の商品名表示

状態: 完了。作成・更新: 2026-09-12。

目的: 履歴一覧と削除確認の見出しは検索した商品名にし、入力全文は詳細だけに残す。モック一覧の入力文も除去する。既存履歴を書き換えず、追加の検索/推論/課金は行わない。

RED: `uv run --frozen --offline --no-sync pytest tests/test_browser_history.py -k product_name -q --tb=short` はexit1、product_nameが未定義。test SHA-256 `5cc21b10a7b047ec3c64ee7c296546f43be14919e1380a9d27f722ee565673fa`。frontendの `./node_modules/.bin/playwright test --config playwright.connected.config.ts -g 'history headings use'` はexit1、商品名見出しなし。test SHA-256 `3a92648019c861dd0fce0bcbd4b0259494ab319e547bdd51552674fcf700723d`。

範囲と方針: 履歴metadataに任意の商品名を保存し、candidateの画像あり/なしで準備済みの商品名を渡す。旧JSONは未設定項目を省略してhash互換を保つ。新payloadの完了キーは商品名を含めて旧形式から区別し、DBスキーマと採点profileは変更しない。API一覧/詳細へ商品名を通し、旧API/旧履歴は先頭の商品句が単独で読める場合に表示、それ以外は商品名未保存とする。元のsummaryは詳細表示用に保持する。

手順: 保存/再読込/API/一覧表示のREDを追加、最小実装、Python関連回帰とfrontend check/test/build・履歴ブラウザで検証する。稼働中の準備済み検索は再起動せず、静的表示で旧APIにも対応する。個人入力/機密値をログやartifactへ保存しない。rollbackは新metadata投影と表示の差分を戻し、既存DB・先行変更を保持する。新形式の読取には対応版が必要。完了時に結果と制約を記録する。

結果: 履歴一覧と削除確認はproductNameを表示し、入力文は詳細だけに保持する。モックの一覧からも入力文を除去した。画像あり/なし双方の新履歴に、準備済みの商品名を任意metadataとして保存し、一覧/詳細APIへ投影する。旧JSONはproduct_name未設定を省略するため従来のhashと読取を維持する。新payloadの完了キーは商品名で区別し、採点profileとDB user_versionは変更していない。

検証: 関連Python49件、全体 `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` が3305 passed /22 skipped /30 deselected（91.87秒）。frontend check/test/build成功、Vitest80件、connected Playwright21件（22.5秒）、mock履歴回帰1件（2.5秒）。保存・再起動読取・原文保持・画像あり/なしの商品名を検証した。旧APIの先頭商品句、条件主体の旧要約、任意fieldの型/長さ/制御文字も検証した。Ruff/format、offline lock、Markdownリンク、diff check成功。

最終SHA-256: `tests/test_browser_history.py` = `029b02049a3ded765c208e09ccd69e778f37cbb415f0e3f4446804ae002ddf07`、`frontend/e2e/connected-parity.spec.ts` = `5c61f2588469baab9aa3b520711288931d42f256d7c21600875ef198cb77c8b4`。初回RED後は整形のみで新規テストの期待を維持した。既存の画像あり/なしの回帰へ商品名保存のassertを追加した。

稼働確認: 8772/8771を再起動せず静的配信を更新し、両画面で4履歴の商品名見出しを読取専用Chromiumで確認した。前後の4DB hashと主検索のAPI状態は不変、POST/外部要求/ページ例外0。既存の準備済み検索と履歴を保持し、追加検索・推論・課金・再採点・commit/pushなし。現在の旧serverは先頭商品句による表示を使い、保存/API側の新metadataは次回通常起動時に有効となる。名前を特定できない旧履歴は商品名未保存と表示し、再解析しない。


## EXEC-149: 参考画像あり/なし表示の削除

状態: 完了。作成・更新: 2026-09-12。小規模表示修正。

利用者指示により参考画像あり/なしの表示を、条件確認・最終確認・履歴と共通モックから除く。画像選択のトグル、生成/確認、画像なし検索は維持する。不要になった共通表示部品と専用styleを削除する。検索・採点・API・DBは変更しない。rollbackは今回の表示削除だけを戻す。

RED: frontendの `./node_modules/.bin/playwright test --config playwright.connected.config.ts -g 'condition groups stay editable'` はexit1。状態表示の期待0に実際1。test SHA-256 `9034cc038c95cc7d476dd9c6d30983c95d5f71f574bc604cbe6f070c71074a03`。同じ回帰でトグル操作を維持したまま表示が消えることを確認する。

結果: 接続画面、条件要約/履歴、モックからReferenceImageStatusと専用styleを除去した。画像選択のトグル・画像確認・画像なしで進む操作は維持。frontend check/buildと単体78件、connected Playwright20件（23.1秒）が成功。モックは `npm run test:e2e -- recovery.spec.ts -g 'failed first image|returning to edit conditions' --workers=1` が2 passed（16.9秒）。RED/GREENのテストhashは同一。Markdownリンクとgit diff check成功。

8772の読取専用Chromiumで状態表示の不在とトグルの表示を確認した。前後のAPI状態は不変、POST/外部要求/ページ例外0。静的配信へ反映済み。Python・実モデル・本番検索・課金・履歴再採点・commit/pushは実行していない。


## EXEC-148: 指定なし編集欄の削除

状態: 完了。作成・更新: 2026-09-12。単一表示部品の小規模修正。

「指定なし」の編集欄を除き、優先/希望/否定だけを編集可能にする。許容表現が原文にある場合だけ検索に使わない条件として文章で表示する。neutralの内部値と元の句を保持し、別の条件修正で否定へ変換したり原文から落としたりしない。検索処理・保存・履歴は変更しない。rollbackは条件表示の今回差分のみを戻す。

RED: frontendの `./node_modules/.bin/playwright test --config playwright.connected.config.ts -g 'neutral conditions have no editor'` はexit1、指定なしtextboxの期待0に実際1。テストSHA-256 `51d701eea1f23dccb5cc0b679c617b1b6109a91bc20270d3bd49546b59c546a7`。同じ回帰で、希望条件修正後も許容表現がreviseの文章に残ることを確認する。静的配信だけ更新し、実検索・課金・DB変更は行わない。

補足: 全connected回帰で既存履歴テストが初期入力の反映前にfillし、元文字列と追加入力が連結する失敗を1件検出した。テストの初期値を待ってから編集するようにし、履歴往復で入力を保持する期待は維持した。製品の入力処理は変更していない。

結果: 指定なしtextboxを削除し、許容表現がある場合だけ読み取り専用の説明を表示する。元のneutral値とquoteは保持した。frontend check/buildと単体78件、connected Playwright20件（22.5秒）が成功。最終ブラウザテストSHA-256は `8425312722380ae62801555c28aba40536fcced52851d8f166ea9c7e8bfb993a`（初回RED後は整形と旧期待の更新のみ、新受入の期待は維持）。8772の読取専用ブラウザでも編集欄の不在と他3分類の表示を確認し、状態不変、POST/外部要求/ページ例外0。静的配信へ反映済み。Python/採点/履歴は未変更のため再検証・再検索・課金なし。Markdownリンクとdiff check成功。commit/pushなし。


## EXEC-147: 分類ごとのカンマ区切り条件編集

状態: 完了。作成・更新: 2026-09-12。

目的: 商品名を条件より上へ移し、条件確認の個別カードを優先・希望・否定・指定なしの編集欄へまとめる。空の希望欄を含め4分類を常時表示し、条件を半角カンマで区切る記法を補足する。末尾の独立した条件textareaを除き、参考画像のあり/なしを#212121背景で表示する（利用者確認済み）。

対象: Reactの条件表示・編集、reviseへ渡す文章の構成、fixture/回帰と仕様。変更のない原文と既存条件の分類・ブランド/型番・否定属性値を保持し、新しい希望/否定/指定なし項目にはローカル解析が認識する自然文修飾を付ける。反映時の同義語・英訳再取得、入力/再整理回数上限、旧履歴非再採点を維持する。実API・Bonsai・本番検索・課金・DB変更は対象外。

手順: 画面配置/空の希望欄/カンマ編集のブラウザREDを作る。分類別入力と原文構成を実装し、frontend単体とPython分類fixtureで否定/許容/希望予算の意味を確認する。check/test/build、connectedブラウザ、必要なoffline回帰、文書リンクと差分を検査する。既存プロセスを再起動せず静的配信だけ更新する。

RED: frontendの `./node_modules/.bin/playwright test --config playwright.connected.config.ts -g 'condition groups stay editable'` はexit1、優先条件textboxが存在しない。test SHA-256 `9870fba110829b17d03abf6b8daeed4404849ebab362aed8709d83d87888c109`。実装前のこの失敗を基点に検証する。

進捗: カンマ区切りの新ブラウザ回帰は実装後GREEN。共有JSON fixtureをTypeScriptの文章構成とPythonの構文解析/候補計画の両側で検証し、希望予算・USB非対応・否定対象・指定なし・ブランド保持が成功した。新しい修飾表現が欄の分類を上書きする境界もVitestのRED（1失敗）を追加して、修正を求める入力検証でGREENとした。稼働8772の4分類編集、商品名の位置、末尾フォーム不在と背景色はread-only Chromiumで確認済み。合成画面だけ撮影して外観を確認し、利用者データは画像やartifactへ保存していない。

互換性と判断: 既存APIのconditionReviewを分類の正本にし、対象語と元の句を分離する。編集しない項目は元の句を使い、確認一覧にない明示属性も落とさない。曖昧な旧API入力は既存の文章全体修正を維持する。rollbackは今回の分類編集と配色だけを戻し、先行変更・準備中の検索・履歴を保つ。完了時に結果と制約を記録する。

結果: 商品名を条件欄の前へ配置し、優先/希望/否定/指定なしを空欄も含め各1入力欄へまとめた。半角カンマ記法の補足を追加し、独立した末尾の条件textareaを除去した。参考画像は「あり/なし」の値部分のみ#212121背景へ変更し、共通モック表示も同期した。新しい条件は分類に沿う自然文へ変換し、既存の句と明示属性、入力の未変更状態を保持する。希望・否定・許容と属性falseを区別し、翻訳・同義語再取得は既存reviseを一度だけ送る。

検証: frontendの `npm run check` / `npm test` / `npm run build` はexit0（Vitest78件）。`./node_modules/.bin/playwright test --config playwright.connected.config.ts` は19 passed（20.2秒）。修飾入力ガード追加後の同コマンド `-g 'condition groups stay editable|product and condition edits'` も2 passed（2.5秒）。`npm run test:e2e -- --workers=1` は35 passed（2.4分）。Pythonは `uv run --frozen --offline --no-sync pytest tests/test_condition_group_edit.py tests/test_browser_terms_edit.py tests/test_condition_language.py tests/test_browser_editing.py tests/test_candidate_bilingual_scoring.py -q --tb=short` が84 passed（2.67秒）。Pythonの実装は変更しておらず、全体pytestの再実行はしていない。Ruff/format、Markdownリンク、git diff checkも成功。

最終SHA-256: `frontend/src/condition-editor.test.ts` = `4ea9db38682bb4a76293c70622b6325e77625a7a9809592f590adcb442f086d7`、`frontend/e2e/connected-parity.spec.ts` = `912e5afed12c5092bdc393c977f3845141cd0466b1e073713ae2bff0384b39be`、`tests/test_condition_group_edit.py` = `637eb0dad9798eb33f2c787b7e60da99546dd42482a854fe90c3f973497ada7d`。初回RED後のブラウザテスト変更は整形とEXEC-146の旧フォーム期待を新しい分類欄へ合わせたもの。新規受入テストの期待は弱めていない。

稼働確認: 8772のquery/revision2を再起動せず静的配信を更新。読取専用Chromiumで4分類が編集可能、商品名が上、末尾フォームなし、状態背景rgb(33,33,33)を確認。POST0/外部要求0/ページ例外0。前後のAPI状態と4履歴DBのhashが一致した。実モデル/本番検索/課金/履歴再採点/commit/pushなし。利用者の実ブラウザは再読み込みで新画面になる。入力上限と初回を含む再整理3回の制約は維持する。


## EXEC-146: 商品名の直接編集と語彙の再取得

状態: 完了。作成・更新: 2026-09-12。

目的: 接続画面の不要な入力案内と条件確認内の入力文・検索語の折りたたみを除く。商品名と条件を直接編集し、「変更を反映」で新しい入力から同義語・英訳を再取得する。未反映のまま検索へ進めない。

対象: browser candidateの表示投影、Reactの条件確認、API検証、fixtureと回帰、FRONTEND/SEARCH-FLOW。既存の元文章修正経路と同じreviseで再準備し、商品名・条件の語彙、計画digest、画像承認を更新する。条件の分類・日英最大採点・履歴互換・再整理3回上限は維持する。外部検索・モデル実行・課金・旧履歴再採点は対象外。

現在: 文章修正はfresh factoryで商品名と条件のexpanderを再実行するが、商品名の直接編集欄はない。解析済み商品名と原文の条件句を表示に渡し、編集時だけ商品名と条件を文区切りで構成する。無編集時は元入力を保持する。解析できない文章は既存の文章修正で回復する。

手順: 最小のブラウザ回帰と再準備のfixtureを追加してREDを記録する。表示投影・入力欄・検証を接続してGREEN、frontend check/test/buildとconnected/mockブラウザ、offline Python、文書リンク・差分を検査する。稼働画面は状態確認後に静的資材を反映し、必要時のみ待機中サーバを入力保持で更新する。

RED: `uv run --frozen --offline --no-sync pytest tests/test_browser_terms_edit.py -q --tb=short` はexit1、productName欠落。test SHA-256 `b8cedbefc81babb9b36cd8eff30ae0d0cbaa03af977a3635c5415f94872e0572`。`frontend/` の `./node_modules/.bin/playwright test --config playwright.connected.config.ts -g 'product and condition edits'` はexit1、商品名入力欄なし。test SHA-256 `59cf43db258fe62b7f013204a45a597b29e0416414e358f2046141de899caf4e`。fixture設定不足を修正後の意図したREDを記録した。

発見/変更: 稼働中8772は利用者操作でquery/revision2へ進んでいたため再起動しない。旧APIでも「原文の最初の商品句が既存queryの先頭と一致し、確認条件の範囲と重ならない」場合だけ直接編集欄へ投影する。曖昧な文中商品名は旧文章修正を維持し、準備済み計画を失わない。追加のVitest回帰を実装前にexit1（直接編集項目なし）で確認した。起動中の処理を再実行せず静的資材だけ反映する。

セキュリティ/互換性: 新表示項目は任意項目として旧履歴を維持。利用者入力・実商品・機密値をartifactへ書かない。単一workerと既存上限を維持。rollbackは今回の表示投影と編集欄のみを戻し、先行差分・DBを保持する。未確認事項と結果は完了時に追記する。

結果: 商品名と条件の手入力を既存reviseへ接続し、未反映時の後続操作を停止する。再準備で商品名・条件のexpanderが再実行され、商品名英訳・条件英訳とsource digestが更新される。旧英訳の混入なし、指定なし・全角文字・文中商品名の原文範囲と明示ブランド/型番の保持をfixtureで確認した。最後にブランド/型番が条件欄から落ちる境界を追加RED（4件中1失敗）から修正し、関連46件でGREENを確認した。

検証: 全体offline `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は3302 passed /22 skipped /30 deselected（90.61秒）。その後のブランド/型番保持を含む `pytest tests/test_browser_terms_edit.py tests/test_browser_candidate.py tests/test_browser_editing.py tests/test_browser_parity.py tests/test_browser_runtime.py -q --tb=short` は46 passed（3.64秒）。frontendのcheck/build、Vitest73件、connected Playwright18件（22.2秒）、mock Playwright35件（2.5分）が成功。新API項目の境界と旧応答互換、未反映・空の商品名・変更取消・一度だけrevise送信を確認した。RED後のテスト変更は整形と境界assert追加であり、元の期待を弱めていない。

最終test SHA-256: `tests/test_browser_terms_edit.py` = `b03eacc2cd29f1f0decc8f2418804158ab760da5028c67b0805f910a420ecf5e`、`frontend/e2e/connected-parity.spec.ts` = `ff24554ff0b584b05ce80fae272bd4fd94a953e441bc499bd26be571ed09550f`、`frontend/src/connected-api.test.ts` = `d057a276cf9d07d5ab614161cf352e22d81f13e23f8e1cbf9044cae2a4c64ce6`。Ruff/format、offline lock、Markdownリンク、diff checkも成功。

稼働確認: localhost8772のquery/revision2を再起動せず、ビルド配信を更新した。読取専用Chromiumで商品名・条件欄と不要なsummaryの不在を確認し、POST0/外部要求0/ページ例外0。確認前後の状態と既存4DBのhashが一致。サーバ起動時以降に利用者が準備を進めていたため、今回の確認では入力の再整理・モデル・画像生成・本番検索・課金を実行していない。新しいAPIの完全な表示項目は次回通常起動時に有効となり、現在の準備済み計画は保守的な旧API互換で編集できる。旧APIの文中商品が一意でない場合は文章全体の修正欄を維持する。commit/pushなし。


## EXEC-145: オフラインモックと接続画面の全画面・操作を統一

状態: 完了。作成/更新: 2026-09-12。
目的: 入力・条件確認・画像作成/確認・最終確認・調査待機/完了・結果・履歴・失敗回復をモックと同じ共通部品/操作配置にする。
範囲: React共通画面部品、接続状態の表示投影、戻る/作り直し/保存再試行/新しい検索/安全な中止と残数の接続。自然文での条件修正と現行ランキング・入力/準備/画像の上限、旧履歴を維持する。モックの固定商品や仮の進捗を実画面へ流用しない。条件分類を直接変える操作、未実装の属性推論、追加本番検索/課金は対象外。
手順: 画面/操作一覧とREDを固定→共通部品で表示統一→serverの実状態に基づく操作→fixture/API/ブラウザ回帰→稼働画面へ反映。未対応操作を見かけだけ有効にせず、安全に使える状態をserverが示す。
互換性: 順位/保存内容の再計算やDB移行なし。新しい検索は旧承認を無効化し、worker1と新規作業先を維持。履歴閲覧中も実行状態を保持する。画像作り直しは既存2回上限、準備は1検索3回。検索中止は取得済み情報の後段処理を停止する協調中止とし、進行中通信の即時取消とは表示しない。
検証: 初期/整理中/確認/生成中/了承/最終/調査中/完了/結果/空結果/履歴一覧・詳細/削除・失敗/拡大とキーボード/戻る/二重送信をfixtureで確認する。既存のモック回帰と全体offlineを維持する。外部サービスは実行しない。
完了/戻し方: 各画面と共通操作を接続しfixture検証、既存履歴不変の確認後に完了とする。変更を戻す場合も新規履歴/旧履歴は保持し、新規UI操作の有効化だけ戻す。

RED: `uv run --frozen --offline --no-sync pytest -m 'not live_api' tests/test_browser_parity.py -q --tb=short` は2 failed/exit1（canReset/workingAction欠落）。test hash=58708bc10ff555f2d923ffe5848246473b02f6ad8202d6c2de07d7ea83a47bb1。`./node_modules/.bin/playwright test --config playwright.connected.config.ts connected-parity.spec.ts` は2 failed/exit1（新しく検索/表示件数なし）、hash=2a038e87a0c2fc9c37dacfe2c58418cea65cd3be42e49ef69cc0d34516b24464。実装後の既存assertionを保持し、拡大対象を合成商品1の完全一致にして厳格locator衝突を修正した。
既存回帰の変更: 画像後のrevise拒否は本依頼の「条件へ戻る」に合わせ、旧画像消去と古いrevision拒否の確認へ変更した。見出し/全文の常時表示はモックの配置へ移し、元入力保持はAPIで確認する。主操作は画像OFFが既定のため、画像ありtestでトグルONを明示した。旧runtimeのattempt範囲0〜2は維持し、別batchで新しい検索先を分けた。全体の同一overlay attestationは主張しない。

完了: 入力/整理/確認/生成/了承/最終/調査/属性確認/完了/結果/履歴/失敗回復を共通UI部品に揃えた。新規検索、戻って再整理、画像作り直し、協調中止、保存再試行を接続した。モックの固定データと条件欄を実データへ転用せず、接続画面は自然文修正を維持する。
検証: 全体 `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は3294 passed/22 skipped/30 deselected（91.89秒）。その後の準備失敗再試行と新batchのsymlink/重複先拒否を含む関連47 passed（1.62秒）。frontend check/71 tests/build、接続ブラウザ17 passed（20.6秒）、既存モック35件と重複選択された接続投影8件を合わせ43 passed（2.5分）。既定configは接続specを除外するよう修正し、以後はモック35件/接続17件に分離する。Python test最終hash=1be2d2595f62a656423ffac926c88269476906a946fd92754df26a2cfa130bd0、ブラウザtest hash=0bc8ed0b506dd0d438d6c8b57528dd6e767658db9e38066b320563f6dcd026da。Ruff/format409files/lock/文書/diff成功。
表示確認: 1440pxのモックと接続入力でヘッダーの寸法一致、入力/段階/操作位置と結果カードを画像で確認した。390pxでは既存の1184px最小幅による横スクロールを確認したが、正本のdesktop専用契約に従いresponsive変更は加えていない。
稼働反映: localhost8772/8771を更新し、入力待機・原入力・4DBを保持した。両画面で4履歴、初期10件/24件選択、保存参考画像の拡大と前後移動、再読込を確認した。POST0/外部通信0/pageerror0。旧6server状態hash/4DBhashは不変、主serverはcanResetだけを追加して旧入力を維持。実行先未作成、新規検索/推論/画像生成/課金なし。機能の外部実サービスE2E成功や未知商品の品質をこの結果から主張しない。

## EXEC-144: 元入力・条件名・商品画像の永続保存

状態: 完了。作成/更新: 2026-09-12。
目的: 接続画面の新しい検索で入力全文、確定した条件名/分類、取得済みの表示用商品画像を保存し、再起動後の履歴でも表示する。
範囲: candidate完了、private SQLite表示履歴、履歴API、React。既存の30日期限・所有者境界・削除連動を維持する。実検索、追加画像取得、旧履歴の補完/再採点は対象外。
手順: 保存欠落のRED→版付き任意snapshotと有界PNG保存→履歴表示→offline/フロントエンド/fixtureブラウザ→稼働画面更新。新検索を起動せず、既存DBの不変を確認する。
互換性: schema5内の任意content profileを追加し、旧JSONの省略/読み込みを維持する。新保存のcompletion keyを分離し、入力/ラベル/画像を同一transactionとpayload digestに含める。取消は新保存の有効化を戻すことで行い、保存済みJSONは読み替えない。
安全境界: 利用者が明示したprivateアプリ履歴への入力保存だけを許可する。診断ログ/文書/artifactへの利用者データ出力は禁止を維持する。画像は取得済み192px PNGの複製で外部呼出しを追加しない。画像なし検索は画像を保存しない。
受入: fresh repositoryで全文/条件名/画像一致、旧履歴互換、画像なし/欠損画像、改変拒否、再試行、削除/期限と共有寿命、UI表示をfixtureで確認する。
実装: 任意content snapshot、PNG検証/保存、API復元と新旧表示を接続。
RED: `uv run --frozen --offline --no-sync pytest -m 'not live_api' tests/test_history_content.py -q --tb=short` は2 failed/exit1、historyContentAvailableがないという欠落で失敗した。RED SHA256=ec8032d2e5ba821df3bb68891cbb4cd823d62a658581c23340b2d4205be5ce7b。同じassertionは実装後成功。長文/neutral/rollback/再試行/削除/期限/改変拒否を追加して10 passed。最終hashは検証完了時に記録する。

追加境界: flowの原入力と保存snapshotが異なる場合のtestは1 failed/exit1（例外なし）となり、照合を追加して解決した。追加RED hash=d7fffae4360bead394b9c53b81943ff49431eca5dac3dd0ba78a4b12824960b7。最終test hash=5cc684fad701bbb304e233c4c09c5dc8668a75565660ab4ec88dd3daad926521、関連49 passed（4.25秒）。整形/追加を含むため同一overlay attestationとは主張しない。
検証: 全体offline3288 passed/22 skipped/30 deselected（82.96秒）、その後の原入力照合追加は上記関連49件で検証。frontend check/70 tests/build、接続ブラウザ8 passed（18.2秒）、Ruff/format408 files/lock/Markdown/diff成功。ブラウザは実candidate+SQLiteの画像なし保存と、fixture画像の再読込・外部画像通信なしを検証した。全体モック `npm run test:e2e -- --workers=1` も35 passed（2.4分）。
稼働反映: localhost8772/8771を更新し、入力待機と原入力を保持した。両画面の既存4履歴/詳細24商品/再読込を確認し、POST0・外部通信0・pageerror0。全7server状態hashと4DBhash不変、新規run出力先未作成。新しい本番検索/モデル推論/画像生成/課金は行っていない。新保存の永続化はfixtureで検証し、実商品の新規保存成功とは区別する。

## EXEC-143: 履歴削除と期限切れデータ削除の接続

状態: 完了。作成/更新: 2026-09-12。
目的: 履歴一覧/保存結果から対象を確認して削除し、完了から30日を過ぎた履歴と専有画像をサーバーで定期削除する。
範囲: BrowserHistory、schema5 repositoryの既存削除/期限削除、loopback POST、React確認/失敗時再試行、稼働画面への反映。対象はserver設定済みDBとlocal-userのみ。HTTPからpath/owner/時刻を受け取らない。GETは読み取り専用、新規検索/provider/課金/キャッシュ掃除は対象外。実利用者履歴をテスト目的で削除しない。
手順/受入: API/SQLite cascade/所有者/期限境界/冪等/ロールバックのRED、既存DB限定の書込経路と定期cleanup、確認ダイアログと再試行の接続、fixtureブラウザ、全体offline/frontend/文書検査、接続server反映。期限切れは直ちに閲覧不可、server稼働中は開始後および60秒間隔で削除を試み、失敗は次回再試行する。
安全/互換: 起動指定最大32DB、新規run予定先を作成しない。schema5と保存点数は変更しない。履歴と画像はDB内の同一transactionで削除。複数DBはそれぞれtransactionで、部分失敗は成功とせず冪等再試行できる。無関係なowner/DB/生cacheを削除しない。完了済み検索と実行中検索は再実行しない。
Rollback: 更新前コードへ戻して削除入口/定期実行を止められる。削除済み項目は復元しない旨を画面で確認する。検証には使い捨てfixture DBだけを使用する。
進捗/証拠: 既存repositoryのdelete/purgeをowner限定・既存file限定writerで接続し、API/UI/60秒cleanupを実装。GETのread-onlyと旧schema拒否を維持した。
RED: `uv run --frozen --offline --no-sync pytest -m 'not live_api' tests/test_browser_history_delete.py -q --tb=short` は最初2 failed/exit1（履歴POSTが404、BrowserHistory.purge_expired未実装）。初期SHA256=36ff41d7bac80029dfc9239cbaa25ad022f94aa3c04fd1bc63a13f19b5ceae61。同じ2ケースは実装後成功。境界テスト追加/整形後は10 passed（0.47秒）、最終SHA256=1abbe60437155de81051c0e719feee27964b729ccd0ea87bf0a6c06e6b5a9457。1件削除と同一DBの他履歴保持、画像cascadeの失敗rollback、期限到達/未到達/他owner、未知locator再送、symlink/旧schema/未作成path拒否、失敗後の60秒再試行、空削除時のDB bytes不変を検証した。
frontend check/69 tests/build、接続ブラウザ7 passed（18.1秒）。実candidate/一時SQLite経路で削除キャンセル、503後の再試行、削除成功後の応答喪失と同locator再試行、最後の履歴削除/再読込を確認。検索commandはstart/without_images/searchのまま増えず、状態も不変。追加の利用者データ削除や本番検索は未実行。
最終検証: 全体offline3276 passed・22 skipped・30 deselected（92.70秒）、全体実行後に追加した2境界を含む対象10 passed。既存モック35 passed（2.5分）、Ruff/format406 files、uv lock --check --offline、Markdownリンク、git diff --check成功。
稼働反映: localhost8772の接続画面と8771の履歴専用画面を同じURLで更新。両server開始後の期限対象は0件、cleanupPendingなし。実データは4履歴96商品を保持し、4DBと7serverの状態hashは更新前後で不変。両画面の一覧/詳細の削除確認をキャンセル/Escで閉じ、再読込で4件維持、ブラウザPOST0/pageerror0を確認した。削除確認のない削除（confirmed=false、固定合成locator）のAPIは両方400を返し、実データには触れていない。入力/検索状態、新規run未作成を維持した。2つの既存HTTP入口のSQL操作は既存SQLite transactionで直列化され、追加の検索workerは作成していない。
結果/残る制約: 履歴の手動削除とserver稼働中の期限削除を接続完了。停止中の期限削除は次回起動後に行う。旧raw cacheや外部backupの削除、schema変更、既存結果の再採点、新規provider実行、commit/pushは含めない。



## EXEC-142: 画像なし検索を接続

状態: 完了。作成/更新: 2026-09-12。
目的: 接続画面で画像なしを選択し、検索語確認、Playwright商品取得、日英最大値採点、結果と永続履歴まで到達する。画像の生成・取得・評価・認証設定を呼ばない。
範囲: candidate flow、browser API/runtime、React確認と結果、SQLite JSON契約。否定条件(負)>タイトル>優先>希望>レビューを維持し、画像未使用を画像欠損と区別する。外観条件がない入力も扱う。旧画像経路と保存済み履歴は再採点・移行しない。
対象外: 追加の本番検索、課金処理、履歴削除。ローカル専用/worker1、入力/推論/候補数/操作回数の上限を維持する。
手順/受入: 既存入口へ画像なし操作を行うREDを固定し、状態遷移と独立したranking/history profile、lazy画像設定、UIを実装する。fixtureで検索前確認、画像呼出し0、日英採点、履歴再読込、重複操作と旧経路の回帰を検証。全体offline/frontend/ブラウザ/文書検査後、idle接続画面へ反映する。
互換性/判断: 新しい画像なしprofileに限り画像参照0件と画像hashなしを許す。旧profileの検証を緩めず、serializerは追加任意値を旧履歴へ書き足さない。
Rollback: 画像なし操作を無効化し従来画像経路を使用する。新旧履歴は保持する。既存作業treeと旧server/DBを変更しない。
進捗/証拠: 接続/状態遷移/画像依存の遅延化/日英採点/空結果/履歴/画面を実装。追加の実サービス成功は未検証。
TDD: `uv run --frozen --offline --no-sync pytest -m 'not live_api' tests/test_image_free_browser.py -q --tb=short` の初回は4 failed/exit1（画像なし操作が通常画像ステップへ進み、画像評価まで呼ばれる）。当初test SHA256=e7ef4fdbf0721d8141c0d27b24113d5c79970b297fac46080965b368dd913586。同じ4ケースは実装後成功。追加の画像失敗回復testは2 failed/exit1（例外でgenerator終了）、RED時hash=bb70e29f6c612d725029fc7bb3b8fbcd0496d21cb4298a0a47eef493f2461c97。空結果の保存testも最小長制約で1 failed/exit1を確認後、新profileに限定して解決した。追加/整形により最終test hashは別途記録し、同一overlay attestationとは主張しない。現在14 passed。
最終test SHA256=d7e50e07f0918f6c0482c13b8feadd795f0b971604fe85e482e82e169d1b5455。全体offlineは3267 passed・22 skipped・30 deselected（87.62秒）。その後、稼働画面がqueryへ進んだことを発見し、メモリ内入力をidleへ引き継ぐmain引数の回帰を追加した。未対応引数で1 failed/exit1を確認後、server/runtime13 passed（0.81秒）。server test最終SHA256=f111be3ae258d0da205d8a156e419c8dcecc25189ee65ccb7af236a4dbd4807f。
frontend check/67 tests/build成功。接続ブラウザ6 passed（18.0秒）では実candidateと一時SQLiteを使用し、画像なし最終確認→採点→保存→履歴再読込までPOSTがstart/without_images/searchの3回だけであることを確認した。既存画像ありfixtureも成功。Ruff/format405 files、uv lock --check --offline、Markdownリンク、git diff --check成功。
稼働反映: 8772がquery/revision1だったため、メモリ内の入力を引き継いで同じURLへ更新し、idle/revision0で待機させた。旧準備directoryを保持し、新実行先は/home/products/bonsai-test-logs/20260912-image-free-browser-live-01（未作成）。原入力は引数/ファイル/ログへ出していない。旧6server状態hashと4DBhash不変、入力hash一致、4履歴96商品、実ブラウザの4履歴再表示/再読込でPOST0・pageerror0を確認した。再開には画面の「条件を整理」を操作する。今回の作業による追加のBonsai/商品検索/画像課金なし。
完了検証: `npm run test:e2e -- --workers=1` は既存モック35 passed（2.5分）。画像なし/画像あり/失敗回復/旧履歴の回帰を維持した。新経路の実商品品質/実サービスE2E、履歴削除、全画面の目標仕様一致はこの接続完了の主張に含めない。



## EXEC-141: 新しい条件分類を稼働接続画面へ反映

状態: 完了（runtime修正、最新server起動、offline/接続ブラウザ/履歴読戻し）。作成・更新: 2026-09-12。

目的/範囲: 接続継続指示に従い、EXEC-140のコードを新しいloopback serverへ載せ、既存の4履歴へ接続する。初回clarification後に再整理の親directoryがない問題をREDから修正し、起動/確認/再入力/履歴のローカル経路を検証する。新規serverはidleで渡し、既存server/DB、単一process/worker1、呼出し上限を維持する。

境界/検証: 追加のBonsai/画像生成/Amazon検索/credential/課金/再採点を行わない。fixtureで実runtime組立の再整理を確認し、offline gateと接続ブラウザ、実起動のGET/DOM/履歴照合を行う。起動したserverだけを停止できる。commit/pushなし。

実装/RED: 初回入力のローカルclarificationではruntimeがまだ呼ばれず、親outputが未作成のため、revision-1作成時にfailedとなることを再現した。`uv run --frozen --offline --no-sync pytest tests/test_browser_runtime.py -k live_server_revision -q --tb=short` は1 failed・5 deselected（0.66秒）。test SHA256=4a99028ab4cdea17fb9225b324ed365819c1d85b9667d5a16a4c8f58ecc62b9c、RED log=/tmp/ae141-red.log。runtimeへrootとattemptを明示して渡し、再整理時だけ0700の親を必要に応じて作成する。同じtestを含む関連21件が成功した。既存revisionの上書き、symlink、公開権限の親、attempt上限違反を拒否する追加4件を含め、runtime全10件も成功（0.68秒）。最終test SHA256=673328b2fa675022f377c38f46e361f88c3838869b0e6383893ae414cd76abd5。実model/credentialより手前でfixtureに停止させるテストであり、実provider成功ではない。

稼働接続: `uv run --frozen --offline --no-sync python -m tools.browser_search_server --run-live-api --port 8772 --output-dir /home/products/bonsai-test-logs/20260912-condition-browser-live-01` に既存4 DBの `--history-db` を付けて起動した。DBは20260912-playwright-browser-live-01、同live-03、20260912-bilingual-browser-live-01、20260912-editable-browser-live-02の各history.sqlite3。保存先はまだ作成せず、検索待機stage=idle/revision=0/editable=trueのまま保持した。`http://127.0.0.1:8772/?mode=connected` で最新frontendとbackendを使える。既存8765/8767/8768/8769/8770/8771は保持した。

実ブラウザ読戻し: 新serverの入力画面、履歴4件、保存結果の詳細/再読込、検索へ戻る操作を確認した。POST0・外部request0・pageerror0。新serverの操作前後state一致、既存6serverのstate SHA256不変、4DBのfile SHA256不変、未実行outputの不存在を確認した。生の入力/商品本文は診断へ保存せず、件数とhashだけで照合した。接続ブラウザfixture5件も成功（11.7秒）。起動時の --run-live-api は実サービスの実行成功を示さず、この回は検索/画像生成/推論を開始していない。

完了検証: 全体 `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は3249 passed・22 skipped・30 deselected（78.27秒、/tmp/ae141-offline.log）。全体収集後に追加した出力境界4件はruntime10件として別途成功した。Ruff/format（402 files）、lock、Markdown/diff成功。接続fixture5件のログは/tmp/ae141-connected.log。稼働serverは8772・PID1384470、既存serverは停止していない。今回の実装/起動範囲に残作業なし。本番検索・課金・commit/pushなし。

## EXEC-140: 希望条件と否定条件の自然文指定を拡張

状態: 完了（実装、offline、frontend、fixtureブラウザ検証）。作成・更新: 2026-09-12。

目的: 承認済み計画どおり、文頭/文中/文末の希望・否定・許容表現を共通ローカル解析し、仕様/外観/価格・日英採点・確認画面へ接続する。希望と否定の重なりは否定優先、希望付き価格は希望、指定なしは採点/検索/画像対象から外して表示に残す。分類用LLMは追加しない。

範囲/互換: 原文範囲・照合対象・強さ・根拠を保持する新解析profileを計画digestへ結ぶ。旧計画/履歴は旧契約を保持する。現行順位、日英最大値、価格の観測、worker1本、文字/条件/モデル呼出上限を維持する。個別分類変更UI、画像なし接続、既存DB再採点、本番検索/外部通信/credential/課金/commit/pushは対象外。

手順/受入: 表現分類と既存入口のRED→共通解析/原文照合→条件/外観/価格/語句展開の接続→確認/曖昧箇所表示/文章修正→関連/全体offline、frontend/build/browser、文書同期。不要と許容、属性値の非対応と除外、複数条件の修飾範囲、二重否定/矛盾、旧profile復元を検証する。既知でない意味を推測して条件を捨てない。

境界/rollback: 元入力と商品情報をdiagnosticへ出さず、修正箇所はメモリ内の表示応答だけへ渡す。既存変更とserver/DBを保持し、今回差分のみ戻せる。実行証拠は合成fixture/ローカル資材と区別し、追加の本番テストは行わない。

実装: 共通解析はcondition-language-v1。正規化範囲/原文quote/照合target/strength/reasonを保持し、GiNZAの条件fragmentにも同じ分類を適用する。確認APIは原入力へ位置を戻し、clarificationから既存の文章修正へ接続する。希望価格・否定対象の分離・指定なし除去・日英最大値・旧計画のlegacy projectionとdigest省略互換を検証する。UIの分類切替操作やLLM分類は追加していない。

TDD/修正記録: 最初の表現testは26 failed。そのうち8件は既存入口の分類/除外不足、18件は新module未実装のimport失敗であり後者を有効なREDとして扱わない。初期SHA256はc7b2af3dd55b90af7ed2aa240b4e920d1c2bda8141d8314ee75b6d0837fd3574。既存のcasefold契約に合わせて大文字USBのquote/label期待値を修正したため、全体を同一test overlayのRED/GREEN証明とは主張しない。

追加の有効なRED/GREEN: `uv run --frozen --offline --no-sync pytest tests/test_condition_language.py -k 'known_shape or prepared_local_ginza' -q --tb=short` は2 failed（丸い形の「形」が未消費扱い）→2 passed・39 deselected（1.52秒）。同一test SHA256は54aeaaa0f60a10d0d1bdf526b3b008843f39e28f3cfa9a66927a3da7fecae4eb。`-k 'polite_forms or opposite_boolean'` は6 failed（丁寧形/文中必須/対立boolean未対応）→6 passed・41 deselected（0.20秒）。同一test SHA256は010d99369bdccb73024dcbf9ffefe5a8a1181d57c7382218cd582c595362c12d。保存先は/tmp/ae140-shape-red.log、/tmp/ae140-polite-red.log。形状の限定接尾辞を消費し、未解決の別属性/数量を捨てない回帰を維持した。

検証中の修正: 旧計画fixtureのlist/tupleとrequest digestの組み立て不備、価格fixtureのJPY欠落、確認API fixture時計と実時計のずれを修正した。初回全体runはfixture不備1 failed・3235 passed・22 skipped・30 deselected（84.31秒）であり、実装の成功結果として扱わない。準備済み実GiNZAでは4種類の修飾/文中予算を検証した。モデルはローカル既存資材のみで、Bonsai/OPUS-MT推論の本番品質検証は行っていない。

最終位置回帰: `uv run --frozen --offline --no-sync pytest tests/test_condition_language.py -k conflict_offsets -q --tb=short` は1 failed（構文fragment連結後の位置を原入力と誤認）→1 passed・48 deselected（0.18秒）。同一test SHA256は6d0481556e796149de35ee3b2332c16290f943bdeca88ab99cbea37d929b359a。fragment投影と同時に原文位置対応を作り、修正箇所の引用を元の範囲へ戻した。

検証コマンド/境界: Python全体は `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short`。Ruff check/formatは全402 files、lockは `uv lock --check --offline`。frontend/で `npm run check`、`npm test`（66 passed）、`npm run build`、`./node_modules/.bin/playwright test --config playwright.connected.config.ts`（5 passed、12.1秒）、`npm run test:e2e -- --workers=1`（既存モック35 passed、2.5分）を実施した。接続ブラウザはlocalhost8766のfixture APIで、修正要求→再入力→分類確認→画像確認→検索結果と再読込を確認した。生provider要求やcredentialを使わず、本文はテスト用合成データだけ。ブラウザとPythonの時計を合わせたfixtureでは解釈→API→修正→日英採点→SQLite履歴まで接続した。

最終test SHA256: tests/test_condition_language.py=03a6cc16e875872cc90358872cf5b058c8c0bc649dc66a70f78c67f85fae76f4、tests/test_browser_editing.py=6561c1893a0274bdb1c5d711b91dc72afc244b0ad7ffe83fb9afa1672bea7016、frontend/e2e/connected.spec.ts=7de58371a5ecfd8e9a864fafa2aaa6701d746fdf058e96de1f6cc8b40a9cf797、frontend/src/connected-api.test.ts=a00019f9e967f6975ab995e758100203af00554cc9725fafb422a2f037ff405d。初期からのtest増補/整形があるため、上記個別RED/GREENのhashとは区別する。AIレビューのattested passや外部本番成功は主張しない。

最終結果: 位置対応修正後の全体offlineは3248 passed・22 skipped・30 deselected（80.03秒）。Ruff/format/lock、frontend check/66 tests/build、接続ブラウザ5件とモック35件、Markdown全16 files/1793 local links/1355 anchors、git diff --checkが成功した。最終全体ログは/tmp/ae140-final-offline-2.log、ブラウザモックは/tmp/ae140-mock-browser.log、buildは/tmp/ae140-frontend-build.log。既存serverとDBは保持し、新しいbackend動作は次回起動から適用する。追加本番検索・外部provider・credential・課金・既存結果の再採点・commit/pushは行っていない。承認済み実装範囲に残作業なし。

## EXEC-139: 否定条件を先頭にしレビュー点を最終比較へ追加

状態: 完了（順位・保存/復元・表示とoffline/ブラウザ回帰）。作成・更新: 2026-09-12。

目的/範囲: 利用者指定の否定条件（負）＞タイトル＞優先条件＞希望条件＞画像＞レビュースコアを新規candidateの辞書式順位へ適用する。否定一致は低い方、他は高い方を先にし、全項目同点なら取得順。レビューは既存PlaywrightのAmazon星評価0〜5を使用し、未取得は取得済み0より後。画像未取得も同様。レビュー件数による補正や新たなLLM評価は追加しない。

手順/受入: 各隣接優先順・負方向・欠損・全同点・旧profile復元のRED→新sort profileと検証/保存/表示→関連/全体offlineとfrontend/build/browser→文書同期。旧タイトル/画像優先の保存結果は旧profileで検証し、既存DBを再採点しない。タイトル/条件の日英最大値、画像計算、参考50:50合成値は維持する。新しい総合加重和ではなく順位順序の変更である。

境界/rollback: 商品ページの取得済みratingだけを利用するので外部通信/credential/課金/再検索は不要。旧履歴はoptional field省略互換を維持し、SQLite schema移行なし。現行server/既存未コミット変更を保持し、新規起動から適用。rollbackは今回差分のみ。commit/pushなし。


実装: candidate_completionの新keyを `(E, -T, -R, -P, -I, -V, 取得順)` にした。Eは日英最大値を集計した否定一致、Vは正規化済みproduct.rating。負の否定点を高い順にすることと同じで、情報不足の判定自体は変えない。旧keyを_title_image_sort_keyとして残し、新profile/旧profile/fieldなしで順序検証を分岐する。レビューは既存ratingを履歴のreview_ratingへ投影するだけで、追加取得や推論はない。null fieldをJSONから省略して旧保存digestを保持し、旧profileの再保存にはratingを追加しない。

表示: APIのsortProfileに応じて順位説明を切り替え、新規結果の否定条件は日英・採用点を0〜−100で表示する。保存値と日英最大値検証は0〜1のまま。reviewRatingを5点満点で表示し、欠損は未取得とする。画像・レビュー欠損はその項目の比較時だけ−1として扱う。旧履歴の正の除外一致表示、旧優先順とschema5読戻しを維持する。合成fixtureでは旧画像優先のA/C/D/Bから、優先条件を先に満たすD/B/A/Cへ変わることと、各画像点/参考合成値が変わらないことを確認した。

TDD: `uv run --frozen --offline --no-sync pytest -m 'not live_api' tests/test_candidate_exclusion_priority.py -q --tb=short` の初回は6 failed・4 passed（0.97秒）/exit1。否定/条件/レビュー優先の未反映と旧profileが理由。RED hash=`bc5ad778cd99c98c9432314cdb438d400295ab907bf7dc45eac2638791a33e2a`。実装後、同fileとtest_candidate_priority.py/test_candidate_connected_flow.py/test_candidate_bilingual_scoring.py/test_browser_candidate.pyは75 passed（6.84秒）。旧priorityの境界testは旧keyへ接続して保持し、現行結合testの確定順/画像点順を新要件に更新した。その後、実際に非nullの合成ratingを保存し、順序改変を拒否する追加assertを加えた最終hash=`a4a35ce5383859c58d967078e6f34ccbaca6ed5a2387b42afe95caf963b45b9e`。元assertを弱めていない。

frontend REDは `npm test -- --run src/connected-api.test.ts` の1 failed・6 passed/exit1。不正reviewRatingを受理したことが理由で、RED hash=`8a29acae48180463c04cadd6d52f3a5d61a0065515c144b43eaafdf43f513b08`。実装/整形後の同file hash=`9343bb2ce81297b8dddc79b3b8b8e56ce45ceabb8583dc8b8ac152daa4714bc8`。npm run check・npm test（65 passed/5 files）・npm run buildと接続Playwright5 tests（11.9秒）が成功した。合成応答で新profileの負表示/星評価と旧profileの正表示/旧説明を確認した。e2e最終hash=`01123b8bfb5f22debbfc99f877c97efe1868b3ec67b6c4650942364fdebcc745`。attestedレビューではない。

全体/完了: `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は3196 passed・22 skipped・30 deselected（83.60秒）。Ruff check/format（400 files）・uv lock --check --offline・Markdownリンク・git diff --checkが成功した。既存の順位検証11件は旧仕様の固定期待値/新field未許容が原因だったため、新profileと厳密な期待順/field集合を更新し、旧順序は別の互換testとして保持した。実データの再検索/再採点、外部API、credential、課金は0。現在起動中のserverとDBは保持し、新規起動した検索から適用する。新順位の未知商品品質や本番再検索を今回のoffline成功とは扱わない。今回指定の順位変更に残作業なし。commit/pushなし。

## EXEC-138: 永続履歴の一覧と保存結果を画面へ接続

状態: 完了（永続履歴の一覧/詳細/検索へ戻る操作と既存実データの再起動復元）。作成・更新: 2026-09-12。

目的/関連: 接続継続指示とSEARCH-FLOW.mdの8節に従い、SQLiteに保存した結果を一覧から開き、検索へ戻れるようにする。EXEC-137の入力/結果画面を維持する。

範囲: browser履歴adapter、loopback GET API、明示指定した履歴DB（最大32個）と新規runの保存先、React一覧/詳細、再起動後の閲覧専用入口。表示は新しい順の最新30件。既存schema5・owner=local-user・30日失効を維持する。削除操作/期限切れの物理削除、画像なし、構造化条件編集、商品画像の永続化、全モック一致は後続。旧履歴にない原入力/条件ラベル/商品画像を生成や再取得で補わない。

手順/受入: SQLite再読込・owner/期限/破損/任意path拒否のRED→閲覧専用adapter/API→画面の履歴/戻る・エラー・再読込→offline全体/frontend/ブラウザ→既存本番DBの実読戻しをブラウザ確認→文書同期。検索処理中の履歴操作はprovider再実行も現在state変更もしない。初期状態では実履歴UI未接続。

境界/判断: DBパスは起動時のCLI指定だけで、HTTPではopaque locatorだけを受ける。既存DBはSQLite read-onlyで開き、複製/移行/削除しない。認証情報/外部通信/課金は0。生入力・商品名・本文・ASIN・URLを診断へ残さず、件数/成否/hashのみ。既存server/DBと未コミット変更を保持し、新規localhost8771を閲覧用に使う。既存保存fieldで表現できない項目は未保存と表示する。rollbackは新規server停止と今回差分のみ、commit/pushなし。


実装: BrowserHistoryは起動時指定の既存DB最大29個と、新規runの初回/修正2回の保存先を登録する。GET時に既存schema5をread-onlyで開き、owner・保存digest・期限・画像hashを検証する。未作成runのDBを作らず、破損を空一覧に読み替えない。GET /api/historyと/api/history/{id}は表示fieldだけを返し、DBパスを受け付けない。旧結果/現行結果の商品projectionを共通化した。新たな採点や商品画像永続化は行わない。

画面: ヘッダーから一覧/詳細へ移動し、検索state・未送信文章・結果表示を保持したまま検索へ戻る。詳細URL fragmentから再読込でき、旧結果の日本語/英語タイトル・価格・日本語リンク・保存されている日英点数と生成画像を復元する。履歴にない原入力全文/個別条件名/商品画像は未保存と表示する。欠損/期限切れと一時的な取得失敗を表示し、再読込に検索POSTを使わない。履歴だけのserverはBonsai等のruntime/検索workerを作らず、検索POSTを拒否する。

TDD: `uv run --frozen --offline --no-sync pytest -m 'not live_api' tests/test_browser_history.py -q --tb=short` の初回は5 failed/pytest exit1。既存serverのGET履歴が404（期待200）で機能不足を確認した。read_only未対応も失敗し、未作成moduleのimport失敗3件は有効な振る舞いREDとして数えない。初回test SHA256=`cd28bc66a3ad8fd6b442620ebb31ad6768ecffd4c6df8d0d2d66ad4c94cfcf81`。実装後の同file＋test_browser_candidate.py＋test_browser_server.pyは16 passed（2.72秒）。整形とfixture名との衝突回避だけを加えた最終test hash=`dc7c94f76e975cda8db007c7bde5a122ba71af53df0e40aac35fb48166fb566d`。assertionを弱めていない。

画面RED/GREEN: frontendから `npm run test:e2e -- --config playwright.connected.config.ts -g 'history survives'` のREDは「検索履歴」ボタン未実装で30秒timeout・1 failed/exit1。RED test hash=`97e83314fdbf59cff6274a5f30ed7394f53c53847c9471334f7dd7625df93401`。実装/整形後の最終e2e hash=`924387bfd21103ebf195037a7eccd80460438d59086ec6ad794a875cf9d79c89`。同じ操作/assertionが成功し、接続全4 testsが10.4秒で成功した。履歴API応答は合成route、既存検索操作はfixture HTTP serverで確認した。実データのHTTP/SQLite/browser結合は後記で別に確認した。hashの変更を完全に同一snapshotのattestationとは扱わない。

全体検証: `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は3186 passed・22 skipped・30 deselected（78.64秒）。Ruff check/format（399 files）・uv lock --check --offline、frontendのnpm run check・npm test（64 passed/5 files）・npm run buildが成功した。Markdownリンク検査とgit diff --checkを実施。frontendテスト追記の初回はworkdir内にfrontend/を重ねて指定しfile未作成/テスト未検出だったため、正しい相対pathでやり直した。整形の初回も誤ったroot作業directoryからnpm execを呼び、公開Prettier取得を試みて対象file未検出となった。その後はfrontendの既存node_modulesの実行fileを使用し、project依存/lockを変更しなかった。この環境準備の呼出しをoffline検証やアプリの外部通信0へ混同しない。

実保存結果の検証: 新規8771を--history-onlyで起動し、EXEC-127/130/135/137に対応する既存4 DBを明示指定した。新しい順の4履歴、各24商品・計96商品と生成画像計8枚を実HTTP/Chromiumで照合した。タイトル・英語併記・価格・リンク・保存済み点数・画像decode・各詳細のページ再読込が一致した。次に所有serverだけを正常停止し、同じ引数で再起動して同じ全履歴を再検証した。前後の一覧digestは一致、全4DBのfile SHA256も不変。旧8767/8768/8769/8770の表示stateは不変だった。両ブラウザ検証とも検索POST0・画面からの外部通信0・pageerror0。Bonsai・商品取得・画像生成は呼ばず、credential利用0・provider費用0。新規の商品検索E2Eや最新価格の再確認ではない。

証拠/結果: `/home/products/bonsai-test-logs/20260912-history-browser-01/` に件数・成否・hashだけを保存した。summary.json SHA256=`9883ade2ca057aa6c377f222e64867c1d3bafc8172bc548c8e3a2e6d3551b088`、readback-1.json/readback-2.jsonとも=`8525b8dc0d4be5c70ced768d498bda055243da04b1c827e349a788d2354f04d0`、readback.mjs=`37aa82e5e4186f123658ed6d161a3f0ada10fd17fbdb2e3c6f7ae6f5c2ca2b58`。生の履歴本文・ID・商品データ・画面画像は診断へ複製しない。再起動後の8771を閲覧用に保持した。scope内の一覧/詳細/再起動復元は完了。削除と期限切れ物理削除、原入力/条件名/商品画像の永続保存、画像なし、個別条件編集、全画面統一は残る。commit/pushなし。

## EXEC-137: 入力編集と画像・採点内訳の画面接続

状態: 完了（入力編集・画像あり経路・サムネイル/点数表の接続と固定入力の実ブラウザ検証）。作成・更新: 2026-09-12。

目的: 利用者の接続継続指示に従い、固定入力だけのReact実行を自然文入力へ接続し、画像生成前の文章修正・条件再整理と、商品サムネイル/日英採点内訳の表示まで通す。

範囲: browser controller/runtime/APIと接続画面、実candidateとの回帰、実ブラウザ確認。最大2000文字・商品24件・視覚条件1〜3件の画像あり経路を対象とする。画像生成前の再整理は最大2回（最初を含め準備3回）、各準備のBonsai上限2回・worker1本を維持する。画像なし経路、構造化条件カードの個別編集、永続履歴一覧、全モック画面の一致、GPU切替は後続として残す。

手順/受入: 入力引渡し・修正/重複/古い要求の拒否と画像再利用禁止、画像の再取得なし表示、採点表示契約のRED→実装→対象/全体offline・frontend build/ブラウザ→固定の既存入力1回の新規本番接続→文書同期。任意入力の意味品質とfixture成功を混同しない。入力そのものが現行parserで解釈できない場合は実行を止め、原文を保持する。

境界/互換: 旧固定要求と閲覧中のserver/履歴を維持する。入力はメモリとアプリ保存だけで扱い、diagnosticへ生入力/商品データ/credentialを出さない。画像は既存の検証済みproxy結果から縮小し、外部URLをブラウザへ渡さず追加取得も行わない。数値の新fieldは追加的に扱い、旧表示を維持する。実行は継続授権の範囲を事前通知し、新規private出力とlocalhostで実施する。rollbackは新規server停止と今回差分のみで、既存作業を戻さない。commit/pushなし。


実装: controllerはeditableなstart/reviseのsourceを受け、factoryから入力別generatorを作る。再整理時は旧generatorを閉じて旧候補を破棄し、画像生成後の修正と準備上限超過を拒否する。Reactは文章変更中の画像生成を無効にし、「変更を反映」で再準備する。視覚条件1〜3件に対応し、条件名を比較画像と点数表へ渡す。評価proxyを包んで検証済みRGBから最大192pxのPNGを作り、同じ取得結果を採点と表示へ再利用する。APIの画像URL/点数検証と旧field省略互換を維持し、SQLite schema/採点順序は変えない。

TDD/offline: 初回test_browser_editing.pyは3 failed・7 passed（factory/source/画像再利用未実装）、frontendのconnected-api.test.tsは1 failed・5 passed（不正thumbnail受理）。実装後、全体 `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は3181 passed・22 skipped・30 deselected（80.33秒）。Ruff check/format（397 files）、uv lock --check --offline、frontendのnpm run check・npm test（61 passed）・npm run buildが成功した。`npm run test:e2e -- --config playwright.connected.config.ts` は3 passed（10.0秒）。fixture HTTP serverへ別の合成入力と文章修正を送り、応答紛失時の重複排除、旧要求、再読込、サムネイル/点数表を確認した。実candidateの1/3視覚条件とSQLite保存もfixtureで確認した。テスト側のproxy.callsは整数であり、途中のlen誤用を修正した。任意入力や3視覚条件の実サービス品質をこの成功から主張しない。

最終test hash: tests/test_browser_editing.py=`2493b374641da14dc2a06af00b3e2160ed950511f35761f1e615e09cb8444a33`、tests/test_browser_candidate.py=`a95300ca2178096a515af91048ec33898ce7cce1406a52c68c651c7af81b9cd5`、frontend/src/connected-api.test.ts=`4c5c4728ab1b4c6892ed992acde33a9cbb0b6fa9e9a9cda145751d44bc69535a`、frontend/e2e/connected.spec.ts=`c9d4d3393815b4ef23b71345d6b4000b0ab4bc72e1e08189ce89618af9cf3943`。RED時点のhashは未採取であり、最終hashをRED attestationとは扱わない。

初回停止: privateな20260912-editable-browser-live-01はBonsai準備中に進行が止まり、ブラウザdriverが1116.242秒で通信失敗した。Bonsai要求2回中、応答完了は1回。Cloudflare/商品取得へ未到達で、失敗記録を保持した。ホストRAM使用7424MB/7774MB・利用可能350MB、swap2048MB全使用と強いI/O待ちを観測し、当該run所有のBonsai/serverを停止した。完了済み8767/8768/8769の表示stateをメモリ内の軽量read-only serverへ移し、各URLのstate hash一致と元SQLiteの保持を確認した。検索workerは追加せず、旧Python runtimeを解放した。8765も維持した。解放後の利用可能RAMは3163MB。再試行結果との速度差をコード最適化やGPU効果とは扱わない。

本番結果: 同じ固定入力・同じ上限で別directoryのlive-02を起動し、2026-09-12 16:09:55〜16:13:37 JSTに222.365秒で完走した。画面の入力がPOST/runtimeへ渡ることを確認し、5操作を各1回送信。準備のUI観測区間は39.337秒、商品検索開始から完了は151.078秒。実Bonsai2 calls（商品名/視覚条件）、商品名要求のenglish=null、条件OPUS-MT1 call/1句、Cloudflare画像2 calls、匿名Playwright検索1ページ/日本語詳細24/英語詳細24を実行した。資材要求は許可5858・遮断5615。再試行0、有料商品取得API0。画像生成2枚分は課金対象で実請求額は未確認。

取得/採点/画面: 日本語タイトル24件・英語タイトル22件・英語詳細24件、商品画像24要求/24成功・SigLIP2 batches。タイトル＞画像＞否定＞優先＞希望の順、日英最大値、50:50参考合成点、strict復元と保存/APIが一致した。予算内23件・超過1件を条件状態へ反映した。SQLite1履歴/画像2枚・integrity_check=ok・foreign key違反0・画像hash一致。DOMの24商品すべてで192px以内のサムネイルdecode、タイトル/条件の日英点、画像点、参考合成点、日本語リンクと英語タイトル表示を照合した。24点数表を開いて可視性も確認した。再読込の追加POST0・state不変・pageerror0・画面からの外部取得0。旧8769のstate不変、旧8767/8768の完了表示も維持した。初回DOM probeはナビゲーションのliを商品行へ混入させ2項目で偽の不一致を返したため、元記録を残し商品行限定の読戻しで確認した。再検索やproductionコード修正は行っていない。最終38チェック全件成功。

証拠/後始末: `/home/products/bonsai-test-logs/20260912-editable-browser-live-02/` に数値/件数/hashだけの診断と実行scriptを保存した。score-summary SHA256=`86bd0e3e695c3a37e28f81967c98b09a02aa80bdc15b6db8808ff7d8e9dc4e27`、ui-summary=`6e73878cf290eab32ade8493e890b86e809f602412673f1e314077086e6e3a7b`、history-summary=`bdab616650d2c3b27a46a31eab669311a2b8b1d92b2f95d6415360aa18a256a9`、dom-readback=`18194cc1100b096bbb3f91f7a50251e26de7c8483a561d64a853a7d1f04d8f57`、acceptance-summary=`80ac263bcc3d3a7c3e8e311b887c505252bc513ad652d64b963b9ad54bd3b536`。生入力/商品データはアプリ保存とIPC以外に複製していない。Bonsai listenerは解放され、商品/翻訳/画像workerは終了した。結果閲覧用8770と旧結果の軽量serverを保持する。商品サムネイルはprocess内のみで、server再起動後の履歴復元UIは未実装。Markdownリンク/diff検査を実施し、commit/pushなし。

残る範囲: 画像なし、構造化条件カードの個別編集、永続履歴一覧、モックとの全画面統一、未知入力/複数視覚条件の実品質、反復運用の安定性。今回の入力編集・サムネイル/点数表示の接続は完了したが、全画面・全運用機能の接続完了とはしない。

## EXEC-136: 検索準備の処理別時間を実測

状態: 完了（同一固定入力の準備区間1回の実測）。作成・更新: 2026-09-12。

目的/範囲: EXEC-135の準備214.396秒には個別時刻がないため、同じ固定入力とtools/browser_search_runtime.pyの準備経路を1回再実行し、資材初期化・辞書/構文処理・Bonsai起動/2推論/停止・ローカル条件翻訳を分けて計測する。今回の再計測を過去の時間の復元とは扱わない。性能変更・商品取得・画像生成・UI操作・commit/pushは対象外。

手順/受入: private診断wrapperで単調時計による入れ子区間を記録→既存資材と新規ローカルBonsaiで検索語確認まで実行→区間合計と総時間の一致、推論回数/語句数、モデル停止を確認→数値と制約を記録する。要求/応答/検索文/訳文は記録せず、件数・時間・固定code・source hashだけを保存する。

境界/互換: 継続授権と今回の測定指示に基づき、localhost18080へ最大2 calls・各900秒・retry0、OPUS-MTは既存2句/batch・各30秒上限を使用する。network namespace内のloopbackだけで実行し、credential設定を診断用placeholderへ差し替える。外部API呼出し0・API費用0。既存serverと履歴は保持し、新規private directoryを使う。rollbackは診断processの停止のみ。現行コードの動作は変更しない。

実測: private wrapperからlive_stepsの最初のquery表示までを呼び出し、210.633158秒で完了。資材整合性検証3.141540秒、辞書初期化0.055682秒、語義モデル初期化0.456860秒、構文モデル初期化1.652924秒、Bonsai起動/ready待ち5.838673秒、翻訳資材初期化0.183033秒、構文解析0.422053秒、商品名辞書照会0.940978秒、辞書語義採点0.059435秒、商品名Bonsai82.164005秒、視覚要求作成0.001385秒、外観条件Bonsai113.534098秒、視覚応答検証0.280689秒、検索語構築0.063347秒、条件辞書照会0.025316秒、条件翻訳0.942906秒、Bonsai停止0.164874秒、その他の準備0.705359秒。入れ子区間を控除した合計は総時間と一致する。

推論内訳: Bonsai応答の数値metadataでは、商品名は入力処理11.228672秒/生成70.815930秒（入力355、生成52 tokens）、外観条件は入力処理14.874673秒/生成98.567369秒（入力469、うちcache3、生成69 tokens）。通信等を含む呼出し全体は195.698103秒で準備の92.91%。出力生成だけで169.383299秒。条件英訳は実OPUS-MT1 call/1句、非空1件。単回の実測であり平均/P95や最適化効果ではない。前回214.396秒はUIの観測区間で、今回はbackend準備区間。過去の個別時間の復元や、差分全てを処理性能の変化とする比較はできない。

検証/証拠: network namespaceを分離しloopbackのみ有効化、環境変数を空にして既存uv環境から実行。検索語候補5件・視覚条件1件まで到達し、Bonsai2 calls、所有serverの停止と18080の解放、区間合計誤差0、対象source hashの一致を確認した。診断先は `/home/products/bonsai-test-logs/20260912-preparation-timing-01/` のsummary.json（SHA256=`74a646ea90a6e8289bc0aeb1aa24fb606fd116b4e2b8879ffc8e69826bfaf965`）、breakdown.json、probe.py（SHA256=`d3b1f8c52fb9bcb78036e98a0368ddb476d6d918fed529226a08bbf0f6c0fe89`）。実行はexit0。要求/応答/訳文は保存していない。通常pytestはproduction code/契約の変更がないため再実行せず、Markdownリンクとgit diff --checkを確認する。画像生成・商品取得・全体UIの新E2Eは実施していない。今回の範囲に残作業なし。

## EXEC-135: 更新した翻訳・日英採点を実接続で確認

状態: 完了（固定入力1回の本番接続と独立した名前専用要求の検証）。作成・更新: 2026-09-12。

目的: 利用者の次の接続指示に従い、EXEC-134の名前専用Bonsai要求と実OPUS-MT、EXEC-133の日英条件採点を実サービスで確認し、固定マグカップ入力のReact→検索→画像評価→SQLite→表示へ到達させる。

範囲: localhost18080で名前専用提案の独立確認1 callと、固定入力の本番フロー最大2 calls。Cloudflareは既存credentialで参考/比較画像各1枚、匿名Amazon検索最大3ページ・日英詳細各24ページ、商品画像最大24枚・SigLIP最大7 batches。worker1本、再試行0、全体15分制限なし。画像生成2枚分は課金範囲で実請求額は未確定。既存の追加承認不要という継続指示を適用し、操作/上限/課金を事前通知して実行する。

手順/受入: 現行資材/実入口と静的画面確認→実Bonsai名前専用提案1回とローカル翻訳→新規8769でReact確認操作→日英採点/最終順序/50:50合成/履歴とAPI内訳/日本語リンク/再読込を照合→provider worker回収と数値診断/文書記録。通常の辞書選択を強制的に未収録へ変えず、実際に通った分岐を記録する。独立した名前専用確認と全体フローの経路被覆を混同しない。

境界/互換: 生検索文・商品名/本文・ASIN・URL・credential・生例外は診断へ保存しない。アプリのSQLite結果とIPC以外の診断は件数/数値/固定code/hashだけ。既存8765/8767/8768とDBを保持し、新規private directory `/home/products/bonsai-test-logs/20260912-bilingual-browser-live-01` を使用する。失敗した範囲を成功扱いせず、原因確認なしに課金処理を繰り返さない。コード修正が必要ならRED/GREENを別途記録する。rollbackは新規server停止のみで旧結果を維持する。任意入力UI、未知条件の品質、commit/pushは対象外。

準備/独立確認: frontendでnpm run buildが成功した。名前専用の実Bonsai確認は1 call・18.139秒で日本語名を取得し、english=nullを確認した。提案名が元語と同一だったため、OPUS-MTは1句だけ翻訳し、元語/提案名の両方へ英訳を保持した。入力は合成の固定句、商品候補shortlistなしのsuggest_name単体経路であり、辞書ありからの未収録分岐全体の証明ではない。診断は `/home/products/bonsai-test-logs/20260912-name-only-bonsai-live-01/summary.json`。model serverの停止後、新規8769を起動し、2026-09-12 14:46:34 JSTにReact操作を開始した。取得/採点を変えない観測wrapperで呼出し数と数値内訳を収集する。

本番結果: 14:46:34〜14:53:20 JST、406.105秒でReactの5操作を各1回送信し、画像2枚生成→24商品取得→画像評価→日英採点→SQLite保存→表示/再読込を完走した。Bonsaiは商品名1回・視覚条件1回、商品名要求のenglish=nullを確認した。商品名は辞書で確定して英訳も辞書由来、productTranslationはnullだった。条件の英訳は実OPUS-MT1 call/1句/非空1件。独立確認と合わせ実Bonsaiは3 callsで、通常フローで未収録名のMT分岐を強制していない。

取得/費用: Cloudflareは既存credentialで参考/比較画像各1枚、計2 calls。匿名Playwrightは検索1ページ・日本語詳細24・英語詳細24、資材要求は許可5852・遮断5577。再試行0、有料商品取得APIは0。日本語タイトル24件、英語タイトル22件・未取得2件、英語詳細24件。画像proxyは24要求/24成功、SigLIP2 batchesで全件の画像点を取得した。価格取得24件、予算内23件・超過1件で確認状態も一致した。Cloudflare生成2枚分は課金対象で、実請求額は未確認。

採点/保存: candidate-confirmed-lexical-v5 / candidate-text-bilingual-v2 / candidate-siglip2-appearance-v1、sort_profile_id=title-image-conditions-v1、image_weight=0.5を確認した。日英最大値、タイトル＞画像＞否定＞優先＞希望の順、50:50合成点を別計算し、strict JSON復元も一致した。タイトル4件で英語点が高く、条件では英語点が高いものは0件（外観条件の日本語点あり7件・英語点あり0件）。これは観測結果であり、英訳/条件照合の一般的な品質合格とはしない。

SQLite/画面: 履歴1件・画像2枚、integrity_check=ok、foreign key違反0、画像hash一致。保存/読戻しとAPIで商品名・価格・日本語URL・英語field・日英点数内訳が一致した。DOMに24商品と英語タイトル22件を表示し、日本語リンク24件のASIN対応を確認した。再読込で追加POST0・state不変・24件再表示、pageerror0。旧8768のstate全体も不変だった。数値・保存・表示の32チェックは全件成功。商品サムネイルと点数内訳表のDOM表示は未実装のままで、APIに点数内訳を保持する。

証拠/後始末: 新規private directoryにscore-summary/ui-summary/history-summary/dom-readback/provider-metrics/acceptance-summaryと観測scriptを保存した。score-summary SHA256=`f2d83e95e7c11c3684320887c4be9ef2ce09a8412d7f4a8dce4a2e04002e5b62`、ui-summary=`828357d3f1f1c7e4f6c6a3216e68cefa19897e5fdaede1a2c478fdd398093d1f`、history-summary=`bdab616650d2c3b27a46a31eab669311a2b8b1d92b2f95d6415360aa18a256a9`、acceptance-summary=`6895afa54f21ec1ea2ed91cfee0d72c7fa54686c51f426b07206289b4a6038c8`。生の商品データはアプリSQLiteとIPCに限り、診断へ複製しなかった。Bonsaiの18080 listener、商品取得Chromium、翻訳・SigLIP workerは終了した。Pythonのresource trackerだけは親serverに付随して残る。8769を結果閲覧用に保持する。

検証範囲: productionコードの変更なし。直前EXEC-134の3167 passedを再実行せず、今回はfrontend build、実サービス/ブラウザ検証、Markdownリンクとgit diff --checkを実行した。新たなRED/GREENやattestedレビューではない。固定入力での接続成功であり、任意入力・語義/翻訳/未知商品の順位品質、長期運用、点数内訳表・サムネイルUIの完成を意味しない。既存8765/8767/8768とDBを保持し、commit/pushなし。

## EXEC-134: 商品名提案の英訳をローカル翻訳へ統一

状態: 完了（offline結合と実OPUS-MTへの受け渡し）。作成・更新: 2026-09-12。

目的: 利用者の「次の接続」指示に従い、OPUS-MT設定時は辞書候補ありからBonsaiが未収録名を提案する経路も、日本語名提案とローカル英訳に分ける。辞書の英訳は優先し、商品名推論後の英訳元を一貫させる。

対象: BonsaiProductSelectorの名前専用提案、product_phraseの翻訳接続、translation出典の保存契約と回帰・文書。視覚条件のBonsai、日英採点、商品取得、UI操作、既存履歴、commit/pushは対象外。現在は候補0件だけOPUS-MTに接続され、候補ありの未収録提案はBonsai英訳が残る。

手順/受入: 失敗する提案翻訳・名前専用schema回帰→最小接続→辞書優先/失敗/重複排除/旧JSONと未設定互換→関連・全体offline/静的検査→文書同期。設定時はBonsai要求schemaと応答検証の両方でenglish=nullとし、未収録提案では元語/提案語を重複なしで翻訳する。翻訳失敗でも日本語候補を保持し、Bonsai英訳へ戻さない。保留・辞書再照会・利用者の候補選択は維持する。

境界/互換: 固定fixtureと通信なしの標準pytestで接続を検証し、必要なら準備済みローカル翻訳だけを追加確認する。Amazon/Cloudflareへの送信・課金は不要。新構成の要求hashを分離し、旧保存JSONとOPUS-MT未設定の旧経路は保持する。rollbackは新しい名前専用提案と翻訳分岐に限定し、既存DB/資材を更新しない。実Bonsaiの生成品質はoffline成功から主張しない。

実装: BonsaiProductSelector.suggest_nameを追加し、既存suggestの日本語名専用要求へ分岐する。要求schemaのenglishをnullに固定し、非nullの応答も拒否する。product_phraseでOPUS-MT設定時にこのmethodを選び、辞書再照会で確定できないbonsai_proposalを既存の重複除去付き翻訳器へ渡す。translation出典をbonsai_inference/bonsai_proposalで保持し、unavailableに英訳が混在するJSONは引き続き拒否する。設定時の要求識別はproduct-phrase-local-mt-v3、未設定時は従来のproduct-phrase-direct-v2。新field、SQL移行、商品取得cache変更は不要だった。

TDD: `uv run --frozen --offline --no-sync pytest -m 'not live_api' tests/test_product_translation.py -q --tb=short` の初回は4 failed・13 passed/exit1（ローカル翻訳未呼出し3件とBonsai英訳受理1件）。RED test SHA256=`918660e75a58a914ead0ad9b925e8e3b9c4ca004004f25872afd0e229687e5c0`。実装後、同fileとtest_product_phrase_bonsai.py/test_product_phrase_flow.py/test_product_name_inference.py/test_bonsai_query_terms.pyの関連実行は66 passed（1.80秒）。さらに合成の検索語選択→画像完成→SQLite履歴保存と未設定旧JSON回帰を追加し、同fileは19 passed（0.90秒）。最終test SHA256=`46fc895c29ea0645b22cee04504950ee7a2068a56f00376573764bb71a6cba23`。既存のRED assertionは弱めていない。

全体: `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は3167 passed・22 skipped・30 deselected（78.08秒）。Ruff/check/format、uv lock --check --offline、Markdownリンク、git diff --checkが成功した。UI表示コードと静的資材を変更していないためfrontend build/browser試験は再実行していない。attestedレビューではない。

実MT確認: `unshare --net env PYTHONPATH=/home/products/Git_Products/amazon-explorer uv run --frozen --offline --no-sync python /tmp/amazon-product-proposal-mt-probe.py` がexit0。Bonsai/辞書応答は固定合成、翻訳のみ準備済みOPUS-MT資材と独立Python環境を使用した。異なる提案名と同一名の2ケースは実英訳を保持し、辞書再照会hitの1ケースは翻訳出典なしで辞書英訳を保持した。全3ケースで名前専用schemaとstrict JSON復元が一致した。OSのnetwork namespaceで通信を遮断し、実Bonsai/外部API呼出し0・credential利用なし・費用0。翻訳やモデル性能の新しい速度測定ではない。

証拠/残る範囲: 件数・成否・hashだけをprivateな `/home/products/bonsai-test-logs/20260912-product-proposal-mt-01/summary.json`（SHA256=`d84b4b7582b8b58703a39ac1a664c12ce8b85e8f89b5a6a053ed217571702b5f`）とprobe.pyへ保存した。実の訳文を診断へ残していない。probe SHA256=`97d5b8b659cf2d945d2fbeb83cc7466cbbc35e8dbe3570ed809d8d42a2c6cc7f`。新要求に対する実Bonsaiの応答/意味品質、本番再検索は未検証であり、今回のコード接続と実翻訳の確認を全体live E2Eとは扱わない。既存完了server/履歴を保持し、新規起動のcandidateから適用する。視覚条件のBonsaiは継続使用する。commit/pushなし。

## EXEC-133: 条件展開と日英別採点の最大値採用

状態: 完了（実商品取得・テキスト採点とoffline結合の検証）。作成・更新: 2026-09-12。

目的: 利用者の指示に従い、ローカル辞書・OPUS-MTで条件の同義語/英訳を準備し、英語の商品タイトルと詳細本文を日本語と同じ条件で採点する。タイトルおよび条件ごとにmax(日本語点,英語点)を採用する。否定条件の高い点は除外一致の強さであり、加点ではない。

範囲: 条件語句の固定/出典、英語詳細取得/正規化、タイトル・条件の言語別内訳、candidate最終順位/履歴の方式識別、実入口、回帰と仕様。タイトル＞画像＞否定＞優先＞希望の順、画像計算、主表示の日本語と旧履歴を維持する。LLMによる商品評価、英語の別商品検索、commit/pushは対象外。

方針: 同一ASINの既存英語詳細アクセスから本文/特徴も採り、追加ページは増やさない。欠損/切詰めを区別する。辞書は単一語義かローカル文脈評価で確定した候補だけを使い、未確定語義を混ぜない。OPUS-MTはラベル/条件原文/値/同義語の重複を除いて2句ずつ処理し、失敗を日本語の欠損にしない。語句bundleをplan digestに結び付け、検索語自体には追加しない。JP/EN各言語内の否定・数値/単位・構造化優先を維持した上で、言語間の高い点を採用する。商品仕様の確認状態とテキスト一致点は区別する。

手順: 失敗する日英最大値/否定/欠損回帰→語句と英語本文契約→採点・復元・履歴→実入口とcache分離→全体offline/静的・実ローカル資材と必要な匿名Amazon限定確認→文書同期。実行条件を事前通知し、継続授権を適用する。診断は数値/件数/固定コードのみで、生検索文/商品本文/ASIN/credentialを保存しない。

互換/受入: 旧fieldなしのJSONを旧点数のまま再出力し、新profile/digest/cache版へ分離する。片側の点数変更とmax結果、同じ条件の言語対応、除外、単位換算、否定、数値の誤対応、英語欠損、語義保留、翻訳失敗、保存後の改変拒否を確認する。旧閲覧serverと既存DBを保持し、rollbackは新field/新方式切替に限定する。品質全般・反復安定性の合格と単体成功を混同しない。

実装: condition_terms.pyで条件IDに対応する辞書/ローカル翻訳語句を固定し、candidate_bilingual.pyで日英のタイトル点と条件点を独立計算して最大値を採る。複合句の名詞同義語は句の中で置換し、修飾語を残す。英語詳細の説明・特徴・色・素材は既存の英語ページ取得から保持し、追加ページは増やさない。candidate-confirmed-lexical-v5 / candidate-text-bilingual-v2、新しい要求flagとplaywright-v3 cacheへ分離した。画像完成結果、SQLite履歴、接続APIも数値内訳を保持する。実ブラウザ入口とcandidate CLIのContextualQueryExpanderから自動接続し、旧plan/旧履歴とlegacy CLIの旧採点式は維持した。

TDD: 初回の `uv run --frozen --offline --no-sync pytest -m 'not live_api' tests/test_candidate_bilingual_scoring.py -q --tb=short` は5 failed（condition_terms未実装）。初回test SHA256=`36f73c12d21e03f0a4e6dcf5315b64e4e7e262f7b2ffd4f7871b5f8e3d9b1967`。実装後、同一保存先へ旧/新fixtureを二重作成するtest準備を修正した。全体の初回は3151 passed/4 failedで、4件は商品名の再照会禁止fixtureが独立した条件辞書照会も拒否したものだった。商品名の再照会禁止を保持し、条件照会と分けて検証した。英語の概数表現の追加testは1 failed/19 passedとなり、概数を確定値として採点しない修正後に20 passedとなった。

offline: 全体 `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は3157 passed・22 skipped・30 deselected（75.67秒）。以後productionコードを変更せず、英語説明の切り詰めとAPI数値投影の3 caseを追加した。最終対象2 fileの実行は22 passed（2.23秒）。NodeのDOM/英語取得testは6 passed、接続画面のfixture browser testは3 passed（8.9秒）。新profileで日英最大値・除外・単位換算・構造化優先・翻訳失敗・旧JSON・改変拒否・画像50:50と優先順・SQLite/API内訳を確認した。Ruff/check/format、uv lock --check --offline、Markdownリンク、git diff --checkが成功した。attestedレビューではない。

最終test SHA256: tests/test_candidate_bilingual_scoring.py=`a3ddc265edd9c6ce9f787a18ff36e06486a4d793c3d46a55f2be3f309be2c21b`、tests/test_product_phrase_flow.py=`477064b091e2e3267e9b4e7f897b9d98db392bc6c1b9a234ccadda7cbfc49b5d`、tests/test_browser_candidate.py=`f0a52c8daf4e5c26e86285258a700f1f47fc6eca8e48eff37081a40c4c4ada4f`、tests/playwright_english_titles.test.mjs=`6735167a09eac331af6310bb96b7141192c3c7861f4512ef32b879bc93b78fd7`。

実検証: 合成の固定条件を使い、準備済み辞書・語義モデル・OPUS-MTと本物のPlaywrightProducts/CandidateSearchを接続した。検証scriptの検索語が商品名だけになるという想定を、通信前に3回のscope assertionで停止して修正した。既存の検索語生成は元の優先条件も含めるため、条件付き1検索と範囲を再通知して実行した。source parserも実入口と同じローカル資材を使用した。追加の同義語/英訳による検索はなく、匿名Amazon検索1ページ・日本語詳細24・英語詳細24、再試行0、許可5831・遮断4892資材要求で完了した。credentialなし、有料API呼出し0。生の検索/商品データはメモリとIPCに限定し、診断へ保存しなかった。

結果: 商品24件の英語タイトル・詳細・説明・特徴が全件取得できた。2つの非価格条件で各1件の英語照合語を準備し、うち1条件は辞書語義1件を採用、もう1条件はローカル翻訳を使用した。価格は共通の観測値を比較するため翻訳対象外。この試験条件では追加の日本語同義語は0件で、同義語による点数変化はoffline回帰で確認した。タイトル2件・条件1件で英語点が高く、条件の内訳は日本語0→英語0.5→採用0.5だった。全24件のmax式と新profileのJSON復元を照合して一致した。準備3.639秒（資材初期化/商品句解析等を含む）、取得96.003秒、採点とstrict復元0.651秒、全体100.294秒。条件翻訳だけの追加時間や以前の別検索との速度差を示す計測ではない。

証拠/境界: 数値のみの `/home/products/bonsai-test-logs/20260912-bilingual-scoring-04/summary.json`（SHA256=`99ac1b84e66ee2794e5088d3550dfcb959abf1c17f1735480b99112afa4e381b`）とprivate検証scriptに記録した。今回は実取得＋ローカル条件展開＋テキスト採点であり、Bonsai/画像生成/SigLIP/SQLite/React全体の新live E2Eではない。画像完成・保存・API・画面はofflineで検証した。8765/8767/8768の既存完了結果は保持し、更新コードは新規起動の検索へ適用する。任意入力の翻訳/語義品質、反復運用、画面の点数内訳表は未検証/未実装。commit/pushは行っていない。

## EXEC-132: 条件の辞書・ローカル翻訳の単体速度検証

状態: 完了（ローカル実資材の単体計測）。作成・更新: 2026-09-12。

目的: 条件の同義語候補と英訳取得にかかる追加時間を、既存のSQLite辞書/OPUS-MT実資材で測る。条件1/5/10件を対象に、辞書の初期化と照会、現行の最大2句/別process翻訳、同一モデルを保持した場合の参考値を分ける。合成の公開試験入力を固定し、各方式3回以上、中央値/範囲と欠損件数を残す。

対象: 単体benchmark testと計測補助、結果記録のみ。productionの条件展開・検索・順位・翻訳器の常駐化は実装しない。既存辞書は商品名用に名詞だけを取り込んでいるため、候補0件も正しい観測として計上し、語義選択/同義性や翻訳品質の合格に読み替えない。既存の翻訳器は呼出しごとに資材検証とモデル起動を行うことを確認済み。

境界: 準備済み `/home/products/models/search-lexical-context-v2/lexicon.sqlite3`、`/home/products/models/opus-mt-ja-en-ct2-v1`、別Python `/home/products/model-envs/opus-mt-eval-02/bin/python` を使用する。network namespaceで外部/localhost通信を遮断し、credential不要・費用0。モデル取得、Bonsai、Amazon、Cloudflare、既存DB/キャッシュ変更は行わない。OSのfile cacheを強制削除せず、初回は新規processでの測定とする。

手順: 現行API/制約確認→固定入力と明示opt-in付き単体test→実資材で計測→関連offline testと静的検査→中央値/初期化/欠損/未接続範囲を記録。通常pytestでは重いbenchmarkをskipし、偽のモデル時間を報告しない。診断は件数・成否・数値・資材/sourceのhashのみとし、ユーザー検索文・生成訳をartifactへ含めない。runtime変更やモデル不一致は停止し、取得で補わない。

受入: 実辞書と実翻訳が1/5/10条件で完了し、失敗/欠損と時間の関係を区別して説明できる。モデルを保持する参考測定では実の同じ翻訳処理を使い、現行adapter出力との一致を検証する。変更は診断用file/文書だけに限定してrollback可能にする。commit/pushは対象外。


実行: `unshare --net env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/root AMAZON_EXPLORER_LOCAL_TERMS_BENCHMARK=1 AMAZON_EXPLORER_TERMS_OUTPUT=/home/products/bonsai-test-logs/20260912-condition-terms-unit-01 /root/.local/bin/uv run --frozen --offline --no-sync pytest -m 'not live_api' tests/test_condition_terms_benchmark.py -q -s --tb=short` は2 passed/exit0（13.06秒）。通信をOSで遮断し、固定資材で実翻訳を行った。試験入力は軽量、丸い、取っ手、陶器、保温、丈夫、滑り止め、電子レンジ対応、食洗機対応、3000円以下の合成10句とその先頭1/5句。利用者データを取得・転用していない。

環境: Intel Core i5-13600KF、CTranslate2 4.8.2/CPU2 threads/int8_float32、SentencePiece0.2.1、sacremoses0.1.1、numpy2.2.6、beam4/最大64 tokens。辞書manifestとSQLite hash、OPUS-MTの固定資材hashが一致した。初回は新規processで、OS file cacheは消去していない。計測中に関連offline test32件（0.87秒）も実行したため、完全な無負荷環境ではない。

| 条件数 | 辞書照会中央値（20回） | 現行翻訳中央値（3回） | 現行翻訳の範囲 | モデル保持時中央値（3回） |
|---|---:|---:|---:|---:|
| 1 | 0.0213 ms | 0.3766秒 | 0.3679〜0.6007秒 | 0.0597秒 |
| 5 | 0.1033 ms | 1.1021秒 | 1.0910〜1.1026秒 | 0.2192秒 |
| 10 | 0.1832 ms | 1.9394秒 | 1.8941〜1.9885秒 | 0.3695秒 |

初期化: 辞書のfile hash/読取専用接続0.0623秒、翻訳adapterの資材検証0.0960秒は表と別。現行の最初の1句要求は0.6007秒、以降も1/5/10条件につきworkerを1/3/5回起動しモデルを毎回読む。参考測定は同じproduction workerのtranslate関数へ実CTranslate2モデル1個を保持するfactoryを試験内だけで注入した。型を偽装した応答や翻訳cacheは使わず、全9回の出力が現行adapterと一致した。参考workerの最初の1句は0.2557秒（うちモデル構築0.0621秒）、native import0.0291秒は別で、表はその後の処理時間。tokenizer/正規化等は各batchで再生成する。

候補と限界: 辞書hitは1/1、4/5、6/10、現行MTの非空英訳は1/1、5/5、10/10。辞書は全語義のforms/glosses取得だけで、文脈に合った同義語の確定はしていない。形容詞や複合条件の未収録は速度と別の課題。翻訳対象は各条件原文だけで、取得した全同義語を追加翻訳する費用/時間は含まない。句の抽出・文脈語義選択・否定や数値条件の同値性検証・商品採点・本番E2Eの時間/品質は未検証。常駐モデルは試験用で本番未実装。

最終確認: 実資材測定の2 passedに加え、通常offlineは `uv run --frozen --offline --no-sync pytest -m 'not live_api' tests/test_condition_terms_benchmark.py tests/test_opus_mt.py tests/test_query_translation_pairs.py tests/test_product_translation.py tests/test_lexical_dictionary.py -q --tb=short` で32 passed・2 skipped（benchmark opt-inなし）。対象2 fileのRuff/check/format、Markdownリンク、git diff --checkが成功した。production変更がないため全体pytestとfrontend/E2Eは再実行していない。

成果物: tools/condition_mt_benchmark.pyとtests/test_condition_terms_benchmark.pyを追加し、通常pytestでは明示envなしでskipする。production file・既存履歴・稼働serverは変更していない。これは性能観測なので未実装機能のRED/GREENやattestedレビューではない。test/helper hashはtests/test_condition_terms_benchmark.py=`3d09f6f21fbf2e28b9dfbb7ef6b4628b883e29379998079c3d6123e1b96b5d16`、tools/condition_mt_benchmark.py=`5d0c998074e5e7a798efc43b89b484d17f0e1efaa1624e45a35419f48fbde886`。各反復の数値、初期化、資材/source hash、候補件数を上記private directoryのdictionary/current-adapter/retained-model/summary.jsonとtimings.csvへ記録した。生の翻訳出力はIPC比較に限り、保存していない。commit/pushなし。

## EXEC-131: 商品の日本語・英語タイトルを併せて取得

状態: 完了（実商品取得とoffline保存/画面の検証）。作成・更新: 2026-09-12。

目的: 利用者の確認に従い、検索語の英訳とは別に、同じ商品の日本語タイトルとAmazon英語表示のタイトルを取得・保存・表示する。

範囲: Playwright要求/worker、正規化、candidate履歴、接続API/React、互換性とcache、関連仕様。日本語を主タイトルとして保持し、英語が取得不能・未翻訳なら未取得を明示する。商品名の機械翻訳やランキング計算変更、旧結果の上書き、commit/pushは対象外。

現在: 日本語詳細のみを取得し、英語タイトルfieldはない。英語指定だけで英語本文になるか未確認。匿名の言語別contextで同一ASINを検証し、追加英語詳細は商品ごと1回、通常最大24件、ページ30秒、retryなし。CAPTCHAを回避せず、英語側challenge後は追加英語取得を停止して日本語結果を保持する。既存の全体期限なし/worker1本/通信allowlistを維持する。

手順: 既存商品の限定live観測（英語2ページ、credentialなし・API課金なし）→失敗する回帰→取得・保存・表示→offline全体/画面/実取得の限定検証→仕様と結果を同期。各liveの範囲を事前通知し、ユーザーの追加承認不要という継続指示を適用する。診断には件数・成否だけを残し、タイトル・ASIN・生応答は複製しない。

互換性: 新要求の英語取得fieldとcache namespaceで旧日本語cacheを分離する。旧fieldなしのJSON/履歴を同じ内容で読戻せるよう追加fieldは省略可能とし、既存SQLiteを移行・更新しない。既存閲覧server8765/8767/8768を保持する。rollbackは新fieldと取得切替に限定する。

受入: 同一ASINの英語観測のみを保存し、欠損時も日本語商品を維持する。旧JSON互換、追加ページ/IPC上限、英語失敗、API/UI表示を回帰で確認する。実取得の成功数と取得不能数を分け、合成検証を本番成功と扱わない。


結果: 同一ASINの英語詳細観測を主タイトルと別に保存する実装を追加した。要求flag/IPC上限、英語challenge後の停止、欠損保持、正規化の500文字上限と状態整合、SQLite読戻し、API投影、React併記、CLI normalized/scored保持とplaywright-v2 cacheを接続した。旧JSONは追加fieldを省略したまま再出力する。順位計算は主タイトルのままで変更していない。

テスト: 実装前の `uv run --frozen --offline --no-sync pytest -m 'not live_api' tests/test_product_english_titles.py -q --tb=short` は2 failed/exit1（要求english_titles未実装・API titleEn未実装）。同じ2件を保持して7件へ拡張し、最終は7 passed/exit0。初回追加patch本文から計算したRED test SHA256=`820bbfadcbd09df5f6fd2006e6fb0a52f1d62759979c8fdd391f904482825a5e`。Nodeの初回 `node --test tests/playwright_english_titles.test.mjs` はmodule未実装で1 failed/exit1、実装後は言語/ASIN/未翻訳/失敗/英語challenge後の停止/重複排除を確認し、既存DOM testと合わせ4 passed/exit0。最終testのSHA256はtests/test_product_english_titles.py=`52dac287f0e839b335663b4006831c702fb19f5ec84f7e9ae9d25f19ab86e00a`、tests/playwright_english_titles.test.mjs=`eb9ff531847b0605e56dd89d9aeaeb689d3694e03bbc7921f48998fe54f9bc84`、frontend/src/connected-api.test.ts=`00bea85e68d5f2c3d57f1ad6431df8223950ee1a1a9a2caa7ca07fb5a0531639`、frontend/e2e/connected.spec.ts=`d9d35ff9525ed3cd789ddb06b9f4ebcb39ac8cca5ece18d8c705b047da458db8`。attestedレビューの証拠ではない。

全体確認: `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は3141 passed・20 skipped・30 deselected（80.51秒）。frontendのnpm testは60 passed、buildとcheck成功。`npx --no-install playwright test --config playwright.connected.config.ts --workers=1 --forbid-only` は3 passedで、英語タイトルと日本語リンクの併記をfixture APIで確認した。uv lock --check --offline、Ruff/check/format、Markdownリンク、git diff --checkも成功した。画像生成・Bonsai・画像評価の実再実行は不要なため行っていない。

実取得: 最初の匿名英語2ページ観測は2件とも同一ASIN/英語lang/英語タイトルを確認（許可242・遮断171要求）。続く実workerの新規検索では100.860秒、検索1ページ・日本語詳細24・英語詳細24ページ、許可5847・遮断5496要求。日本語商品24件、英語取得22件・未取得2件を返し、CLI正規化でも24件/英語22件を保持した。未取得2件の個別理由は保存していない。credentialなし、有料APIなし、再試行0。probe起動時のPython import path不備は通信前に修正した。実行の診断は `/home/products/bonsai-test-logs/20260912-playwright-bilingual-01/summary.json` の数値だけに限定し、生商品値を保存していない。

残る境界: このliveは商品取得・CLI正規化の確認であり、新しい英語fieldを伴うBonsai/画像生成/順位/SQLite/React全体の実サービスE2Eではない。保存/API/画面は合成データで確認した。稼働中の8765/8767/8768の完了結果は更新せず、新規起動・検索から追加取得が適用される。未知商品の英語提供率、混在表記の自動言語判定、反復運用は保証しない。commit/pushは行っていない。

## EXEC-130: 新優先度で実検索とスコアを再計算

状態: 完了（初回停止後の再実行で固定入力1回を完走）。作成・更新: 2026-09-12。

目的: 利用者の再検索指示に従い、既存の固定入力を実Bonsai/Cloudflare/Playwright/SigLIPへ再投入し、EXEC-129の優先順でスコアを計算・保存・表示する。以前の8765/8767の結果は保持し、新規8768でReact操作から実行する。

範囲: Bonsai localhost18080最大2回、Cloudflare既存credentialで参考/比較画像2枚、匿名Amazon.co.jp検索最大3ページと詳細最大24件、商品画像最大24枚、SigLIP最大7 batches。retryなし、全体15分制限なし。Cloudflare画像生成分の課金があり、実請求額は未確定。ユーザーの継続指示と追加承認不要の指示に従う。

検証: 本番の返り値を変更しない観測wrapperで、provider呼出し数・各順位の数値だけを記録する。タイトル/画像/否定/優先/希望の順序、50:50合成点、SQLite読戻し、新方式fieldとdigest、UI表示/再読込を照合する。診断へ検索文・商品名・本文・ASIN・URL・credentialを保存しない。private出力は `/home/products/bonsai-test-logs/20260912-playwright-browser-live-02/`、旧DB/結果は上書きしない。途中停止は原因を調べ、必要な修正/限定再実行を行う。固定入力1回の結果で未知順位品質を保証しない。commit/pushは対象外。

途中経過: live-02は2026-09-12 12:58:07〜12:59:28 JST、81.352秒で画像2枚生成後の商品取得開始時にfailedとなり、スコア/履歴は未完了。ReactへのPOSTは5回、旧8767のstateは不変。取得例外は汎用エラーへ変換され、初回の具体的原因/HTTP件数は未収集。続く無課金の限定診断は同じ検索語で検索1ページ/詳細1ページ、許可145・遮断261要求、1商品取得に成功した。初回原因の特定や修正済みという証拠にはしない。

再実行: 固定の取得失敗コードとprovider回数を記録する観測wrapperへ変更し、live-03を同じ8768・同じ上限で開始した。Cloudflare2枚の追加課金範囲を事前通知した。旧8767と失敗診断を保持し、新規private出力を `/home/products/bonsai-test-logs/20260912-playwright-browser-live-03/` とする。本番driver・ランキング・通信制約は変更していない。

完了: live-03は2026-09-12 13:01:48〜13:04:55 JST、187.560秒で24商品の再取得・再採点・保存・画面表示まで完走した。実測Bonsai2 calls、Cloudflare2 calls、Playwright検索1ページ/詳細24ページ（許可2912・遮断2883要求）、商品画像24要求/24成功、SigLIP2 batches。初回live-02と合わせてCloudflare生成は4枚、別の限定診断は検索1/詳細1ページ。初回停止の原因と要求総数は未特定で、継続運用の安定性を保証しない。

スコア確認: 全24件のT/I/E/R/P/合成点を数値だけで観測し、新優先keyの昇順と50:50合成式を別計算で照合して一致した。sort_profile_id=title-image-conditions-v1、image_weight=0.5、candidate-text-v1、candidate-siglip2-appearance-v1、取得元playwrightを確認。タイトル点0〜1、画像点0.512468496〜0.949153071、合成点0.337202674〜0.974576535。価格条件の一致22件、不一致2件は新順位17/18位に並び、旧条件優先で末尾に固定されていない。否定/希望の指定を増やす新入力試験ではない。

保存/表示: SQLite1履歴・画像2枚、integrity_check=ok・foreign key違反0・画像hash一致。観測した点数とrepository読戻しが一致し、表示URLの日本語化後にAPI値と全24件一致。DOMの24タイトル/価格/外観評価と日本語リンク・ASIN対応を照合した。5操作を各1回送信し、再読込で追加POST0・state不変・24件再表示、pageerror0、旧8767のstate全体も不変。Bonsai/product workerは終了し、8768を結果閲覧用に保持した。初回失敗の履歴件数は0である。

証拠: live-03へ数値だけのscore-summary.jsonと順位別scores.csv、ui-summary/history-summary/dom-readback/provider-metrics、観測/操作scriptを0700 directory内の0600 fileとして保存した。score-summary SHA256=`fef66f83571e74d37ade2c4d241e9f2e1b31ed6c673c068fc546de1fbcbbca95`、ui-summary=`099dd906a69a1b1ddaa56fdd44f363d225b425559fe3e1040d30e94c404ca3e3`、history-summary=`495feba9011b0f274353092c5284b9ced289a537eb28afd414edb63c1b931c28`。商品本文/タイトル等はアプリの既存SQLite保存に限り、診断CSV/JSONへ複製していない。

残る境界: 商品サムネイルと点数内訳の画面表示は未接続で、今回の内訳はCSVで確認する。未知商品の順位品質・任意入力・反復運用・実請求額は未検証。製品コードは変更せず、Markdownリンク/diff検査で文書を確認した。新順位の固定入力live検証を完了し、commit/pushは行っていない。

## EXEC-129: ランキングをタイトル・画像優先へ変更

状態: 完了。作成・更新: 2026-09-12。

目的: 利用者の明示指示に従い、新規candidateの最終順位をタイトル一致度、画像評価、否定条件、優先条件、希望条件の順に比較する。優先条件は既存required、希望条件はpreferred、否定条件はexcludedへ対応する。同点時だけ次の項目を比較し、最後は取得順とする。画像欠損は同じタイトル点の評価済み商品より後ろ、否定条件への一致度は低い方、他の一致度は高い方を先にする。

対象: 最終順位key・結果/履歴の方式識別と回帰・仕様。採点値、画像モデル、取得処理、条件の観測判定を維持する。先行50:50の合成点は記録に残すが順位keyには使わない。条件不一致による最優先のグループ分けを解除するため、価格超過商品もタイトル/画像が高ければ上位になり得る。古い保存結果は旧順位のまま読み、新しいsort_profile_idとdigestで分離する。

手順: 各優先段階の競合と欠損/同点の失敗test→最終sortとstrict復元/保存→関連・全体offline検証→文書同期。既存8767の完了結果と先行未コミット差分を保持する。外部検索/課金・既存履歴の再採点・commit/pushは行わない。rollbackは新方式fieldと新規sort切替に限定する。

結果: 最終rankingのkeyを `(-T, -I, E, -R, -P, 取得順)` に変更し、画像欠損はI=-1として扱う。条件の状態・一致度・タイトル/画像の点数は従来の計算を維持する。新規result/historyにsort_profile_id=title-image-conditions-v1を記録し、profile digestへ結合した。新方式の復元時は順序とimage_weight=0.5を検証し、旧fieldなしの結果は旧keyで検証・再出力する。画像評価前の内部CandidateRankingは旧順序で保持し、最終keyへ条件のグループ分けを持ち込まない。

検証: 新規優先度testは実装前に9 failed（未実装）、実装後は各項目の競合、画像欠損、全同点、旧sourceの除外観測を確認した。新方式→SQLite読戻し、旧50:50順位とのdigest/保存分離、方式だけ削除する改変の拒否を追加して計10件。関連3 file初回の旧期待は5 failed・35 passedで、新順序A/C/D/Bと、画像同点時B/D/A/Cへ期待を更新した。次の1 failed・40 passedは改変testが新先頭の画像満点に当たり、旧係数でも点数が同じだったため、係数差で点数が変わる行に対象を修正した。拒否assertを保持し、最終全体 `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は3134 passed・20 skipped・30 deselected（78.11秒）。Ruff/format（390 files）、Markdownリンク、git diff --checkも成功した。

互換と証拠: 新規test SHA256=`59bc60d454c3aa059adeef60209cad3f4d50d38daedc1e93ac37f1c400f124e0`、更新equal-weight test=`c6e9967486dc009f00202ed52d98caf5f0d8139c2fc410dc27403d77306ee61c`、connected test=`2144e67e1c31232ef5a77ebb27c09921f4dd460a771d60585891c14468615cb4`。EXEC-127の実保存24件を新readerで読戻し、旧JSON全体一致・DB bytes不変を確認した。旧80:20/50:50のJSONと履歴を保持する。今回の実行はofflineと保存DB読取のみで、新順序の実サービス検索/未知順位品質は未検証。8767の既存表示は旧実行結果のままであり、新規起動後の検索から適用する。commit/pushは行っていない。

## EXEC-128: タイトルと画像の採点比率を等しくする

状態: 完了。作成・更新: 2026-09-12。

目的: 利用者の指示に従い、新規candidateの合成点をタイトル50%・画像50%へ変更する。条件優先の順位、画像欠損時のタイトル点、モデルと商品取得は維持する。

対象: candidateの合成・検証・履歴metadataと関連回帰/仕様。旧80:20の保存済みranking/SQLiteは旧点数で読込可能にし、新しい合成方式を明示fieldとdigestで分離する。既存8767の完了結果は実行当時の証拠として保持し、外部検索や課金処理を再実行しない。

手順: 等重みの失敗回帰→合成/旧JSON互換→新旧履歴読戻しと条件優先/欠損回帰→offline全体と静的検査→文書同期。既存未コミット変更を保持し、rollbackは今回の合成fieldと既定変更に限定する。commit/pushは対象外。

結果: 新規candidateの合成を `0.5*T+0.5*I` へ変更した。画像欠損時はT、条件優先のsort keyは従来通り。新しいrow/ranking/表示履歴にはimage_weight=0.5を記録し、親子の係数と合成点を検証する。旧fieldなしのJSONは80:20で検証し、再出力で新fieldを省略する。旧profile digestの値を保持し、新履歴digestへ係数を追加して分離した。SQLiteのtable変更や旧履歴更新はない。

検証: 期待値を50:50に変えたconnected回帰は修正前2 failed・27 passedで旧80:20を検出し、修正後29 passed。新規2件は画像寄与による優先逆転、画像欠損、旧JSON/新旧SQLiteの読戻し、digest分離、親子係数/点数の改変拒否を検証した。関連5 fileは64 passed。最終全体 `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は3124 passed・20 skipped・30 deselected（78.33秒）。Ruff/format（389 files）、Markdownリンク、git diff --checkも成功。新規test SHA256=`fed2fc038a8983ec958526f7af08564adfafb28a21f5638fbf4fc73de180a539`、更新したconnected test SHA256=`9da8f780215e85ce0c33ced79917f06b11664573acf9a07ed404faf57305928a`。

互換確認: EXEC-127の実履歴24件を新readerで読戻し、旧JSON全体一致・DB bytes不変を確認した。今回の検証は合成fixtureと保存済みDBのローカル読取で、実検索/生成/画像評価を再実行していない。新規起動後の検索から50:50を使い、8767の表示済み結果は80:20のまま保持する。未知商品の順位品質と新比率の実E2Eは未検証。

## EXEC-127: Playwright移行後の接続本番テスト

状態: 完了（固定入力1回の本番接続検証）。作成・更新: 2026-09-12。

目的: 利用者の本番テスト指示に従い、既存の固定入力でReact操作から実Bonsai、Cloudflare参考/比較画像、Playwright検索/詳細、実商品画像とSigLIP 2、SQLite保存、画面表示/再読込まで検証する。移行時の追加承認不要の指示を適用する。

範囲: localhost8767に新規serverを起動し、既存8765の完了結果を保持する。Bonsaiはlocalhost18080で最大2回、Cloudflareは既存credentialによる画像生成2枚、匿名Amazon.co.jp検索最大3ページ・詳細最大24件、商品画像最大24枚、SigLIP最大7 batches。retryなし、全体15分制限なし。画像生成分の課金があり実請求額は未確認。検索文・商品本文・ASIN・生応答・credentialは診断artifactへ保存しない。

手順: Reactの各確認ボタンを実操作し、stateとDOMの件数・日本語タイトル・リンク・画像評価・保存を照合する。再読込で再送信しないこと、SQLite読戻しと取得元、旧結果保持を確認し、件数と成否だけを新規private directory `/home/products/bonsai-test-logs/20260912-playwright-browser-live-01/` へ記録する。途中停止は工程と原因を調べ、必要な修正と限定再実行を行う。成功を固定入力1回の接続検証に限定し、未知商品の順位品質や継続運用の合格とは扱わない。commit/pushは対象外。

結果: 2026-09-12 12:29:12〜12:32:04 JST、172.081秒で完走した。Reactからstart/reference/comparison/final/searchの5 POSTを各1回送り、実Bonsaiで条件を整理、実Cloudflareで512×512画像2枚を生成、新Playwright providerで24商品を取得し、実商品画像とSigLIP 2の評価を全24件でavailableとして保存した。全24件のかなを含む日本語タイトル・円価格・日本語指定リンクとASIN対応を確認した。予算内22件はconfirmed、超過2件はcontradictedで末尾に並ぶ。価格超過商品を一覧から消す仕様ではない。

保存/画面: SQLite履歴1件・参考画像2枚、integrity_check=ok・foreign key違反0、画像hash一致。repositoryでstrict読戻しし、retrieval_provider=playwright、ranking_profile=candidate-siglip2-appearance-v1、text_profile=candidate-text-v1を確認した。日本語URLへの表示変換後、APIと履歴の24件が一致。実DOMで24タイトル/価格/外観評価と22一致・2不一致を照合した。再読込後も24件でstate不変、追加POST0、pageerror0。元8765のstate全体も不変。終了後のBonsai/product workerは0で、新しい結果server8767だけは閲覧用に保持する。

検査側の修正: 初回診断scriptは見出しをh3と仮定してDOM照合false、URLを表示変換前の履歴と直接比較してfalseになった。製品のh2と日本語URL変換を確認し、結果画面GETだけの追加検査でいずれも一致を確認した。実検索/課金処理は再実行していない。初回ui-summaryを保持し、最終判定をdom-readback/history-summaryへ分離した。

証拠: 上記private directoryにui-summary.json、history-summary.json、dom-readback.jsonと実行scriptを0600で保存した。ui-summary SHA256=`954f0f2c93b01d1a61e3a62596aa33e1e3b2555d93757de1016c30256f7e9b50`、history-summary SHA256=`cf29eebe3a938dc80f9810ae4da46600d5ea63cc27a2cf167d85fe1ea7174835`。raw商品値はアプリの既存SQLiteに限り、診断には含めない。本番コードは変更していない。

残る境界: 商品画像は取得/評価済みだが接続画面のサムネイルは未接続（DOM画像0）。任意入力、条件編集、モックとの全画面一致、永続履歴一覧、未知商品の順位品質、反復運用、複数検索ページの実遷移は未検証。この実行の個別HTTP要求数とモデル呼出し数は診断に露出しておらず、過去実行の回数を転用しない。実請求額は未確認。詳細と残作業は [WORKLOG253](WORKLOG.md#253-playwright移行後の本番接続フローを完走2026-09-12) と [NEXT-STEPS](../NEXT-STEPS.md) に同期する。

## EXEC-126: 商品取得をPlaywrightへ移行

状態: 完了。作成・更新: 2026-09-12。

目的: 利用者の明示指示に従い、現行Outscraperの検索・商品詳細取得を日本語設定のローカルPlaywrightへ置換する。今回の実装・検証には追加承認を求めない。ブラウザ接続、CLI、再実行と既存診断入口で有料OutscraperやAPI keyを要求しない。

対象: 取得driver、要求/応答の互換adapter、candidate接続、CLI/実行入口、cache分離、関連回帰と文書。Bonsai用途・SigLIP採点・Reactの通常確認操作・保存済み履歴を保持する。commit/pushや公開配置は対象外。

現状: EXEC-124の単独試験で検索1ページ48カード/先頭24件と既存24商品詳細の取得に成功した。本番経路はOutscraperの要求・task/poll・API keyに依存している。既存未コミット差分とEXEC-125の採点変更を保持する。

方針: Node側のPlaywright workerをPython adapterから起動し、匿名contextで検索と詳細を逐次取得する。通信はAmazon.co.jpと必要なAmazon資材に限定し、query/商品本文はstdin/stdoutのprocess間通信とアプリの既存保存だけで扱う。診断ログへraw値を出さない。新要求とcache namespace/digestを分離し、旧JSON/履歴は読込互換を維持する。CAPTCHA、別ASIN、未知redirect、取得失敗は固定エラーで終了し、有料providerへのfallbackはしない。期限はページ/処理別で設定し、検索全体15分制限を追加しない。配送先は匿名Amazonの既定で、旧postal codeの適用済みとは扱わない。

手順: (1) driver・要求・互換境界の失敗test、(2) 検索/詳細抽出とprocess回収、(3) 実行入口とcache移行、(4) offline全体・静的検査、(5) 同じ固定入力の実検索/詳細/正規化の検証、必要な既存画像採点/履歴/画面との接続検証、(6) 文書と結果の同期。実検証は最初に1検索/最大24詳細/再試行0とし、修正が必要な再実行は原因と範囲を通知して行う。有料APIの新規呼出しは必要としない。

rollback: 新規取得adapter/入口切替のみを戻せるよう既存の保存形式を破壊しない。旧cacheを新providerとして再利用せず、自動変換・削除しない。実行中の結果閲覧serverと元DBは保持する。受入条件は新規実行がPlaywrightに到達し、API key未設定で検索でき、日本語取得・件数上限・失敗境界・旧履歴互換の回帰を満たすこと。

- [x] 要求/driverと互換性の回帰。
- [x] 全実行入口とcache切替。
- [x] offline/静的検査と実検索、文書同期。

実装: 新規 `product_request.py`、`playwright_products.py`、`playwright_compat.py`、`playwright_client.py` とNode worker/DOM抽出器を追加した。candidate/browser/CLI/retryを切り替え、旧provisionalの既定transportもPlaywrightへ変更した。保存済みplanからの再実行は元planを検証して新要求へ移行し、履歴JSONへretrieval_providerを保存する。Outscraper API keyを実factoryから除き、frontendに既存のPlaywright1.63.0をruntime依存として明示した。npm lock更新はoffline・script/auditなしで実施し、新しい資材のdownloadは行っていない。

回帰: 新規Python13件が成功。新providerの既定、旧plan読込、新旧digest/cache分離、single-useと応答binding、credential/proxy/DEBUG非継承、不正応答拒否、旧task adapter、正規化→条件/画像採点→SQLite、API key loader未呼出し、旧planから新規検索への移行を含む。新規要求/driverの初回は未実装等で5 failed。履歴取得元の追加は欠落を1 failedで確認してから修正した。合成fixtureの組立ミス（属性未確認、fixture戻り値/定数参照）はtest側で修正し、productionのRED証拠と混同しない。最終Python test SHA256=`3c40b1b2f8ed06d094253e1df10cd6110d2b9c5dd7a13d1ef5fb638c36c68fd1`。Nodeの全通信遮断DOM検証1件も成功し、test SHA256=`4dcd06a3ee657330c0d5736aaa4dd684129ddbe015c9dcac14dad51bf18b5b93`。途中でtest追加/整形があるため、最初のREDと最終hashが同一bytesであるとは扱わない。

検証境界の修正: 初回全体testでは旧CLIのmock差し替え先が移行前のままで、実Node workerが1回起動して商品取得失敗となった。HTTP要求数は未収集で、これをoffline検証や成功に数えない。実行を中断し、CLI testの差し替え先とpytestの実worker拒否を追加した。その後の全体は3119 passed・20 skipped・30 deselected（78.79秒）。追加の履歴/入口/再実行回帰を含む最終全体結果は後記する。

実検証: 本番用 `PlaywrightProducts` →Node検索/詳細取得→既存正規化を1回実行。53.549秒、検索1ページ・詳細24ページ、許可要求2909件・遮断2818件、24商品・rejection0件。全24件でかなを含む日本語タイトル、円価格、description、features、画像URL、ASINと一致する商品リンクを確認した。provider=playwrightで、実行前後のAPI state全体が一致。Bonsai/Cloudflare/Outscraper呼出し、画像本体取得、元履歴書換えは0回。番号/件数だけのsummaryと実行scriptを `/home/products/bonsai-test-logs/20260912-playwright-production/` に0700/0600で保存した。summary SHA256=`12e1986e58fd5942dbe63c90993a3268fa589193f2e20e89ebd1841dd262234a`。

確認済みの静的/画面検証: Ruff、format（388 files）、offline uv lock、frontendの型/Prettier・単体59件・build、connectedブラウザ3件（8.7秒）、Markdownリンク・git diff --checkが成功。ブラウザ3件は合成API応答の操作回帰で、今回の実検索とは別の証拠である。未知カテゴリ、複数ページの実遷移、反復運用、Windowsでのbrowser process回収、今回取得した商品の実SigLIP再評価は未検証。現在表示中の完了結果serverは保持し、次の新規起動から新providerを使う。

最終結果: `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` はexit0、3122 passed・20 skipped・30 deselected（79.87秒）。新規13件、保存済みOutscraper要求からの新検索移行、履歴取得元の保存/読戻し、実入口でのcredential loader未呼出しを含む。`node --test tests/playwright_products.test.mjs` の全通信遮断DOM確認も最終整形後に再成功した。既存未コミット差分を維持し、commit/pushは行っていない。実行入口の置換と今回の検索/正規化の受入条件は達成し、継続運用等の検証境界は [NEXT-STEPS.md](../NEXT-STEPS.md) に引き継いだ。

## EXEC-125: 説明文の条件一致とタイトル比較の拡張

状態: 完了。作成・更新: 2026-09-12。

目的: 利用者の5点の修正指示に従い、説明文の部分一致を条件スコアへ使い、構造化された観測値を優先する。元の商品表現を優先して同義語をタイトル採点へ加え、日本語・英語カテゴリ、取得できたブランド・型番を専用の比較項目へ分離する。

対象: candidateの検索意図・テキスト採点・画像との合成・結果復元・履歴の契約、offline回帰、関連設計文書。既存のブラウザ接続作業の未コミット差分を保持する。LLMによる商品採点、追加provider通信、実モデル/ブラウザlive試験、commit/pushは対象外。

方針: 条件の明示証拠と説明文の部分一致を区別する。構造化情報の不一致・情報競合を説明文で上書きせず、否定記載は正の一致点にしない。数値は単位と境界を比較する。タイトルは元語の一致に同義語の補助点を加え、カテゴリは商品表現から得た名詞、ブランド・型番は原文に明示された値だけを使う。採点profileとdigestを更新し、旧保存結果を再採点しない。既存画像20%・画像欠損時のテキスト100%と承認境界を保持する。

手順: (1) 現行契約と変更前差分を確認、(2) 説明文・否定・構造化優先・同義語・専用fieldのRED、(3) 新profile実装と同一testのGREEN、(4) candidate/画像/JSON/SQLite回帰と全offline・Ruff・lock・Markdown・diff、(5) 設計・履歴と結果を同期する。RED/GREENのコマンド・exit・test SHA256を記録する。

現状: 説明文はラベル付き数値抽出だけで、非数値全文一致は未実装。同義語は取得query候補だけで、タイトルは元語とoriginal_enのみ。比較関数にカテゴリ/ブランド/型番fieldはあるがcandidateから未設定。

rollback: 今回追加するテキスト採点とprofile分岐だけを戻す。既存未コミット変更・保存済み履歴・モデル資材を変更しない。関連仕様は [BACKEND.md](BACKEND.md)、保存互換は [DB-SCHEMA.md](DB-SCHEMA.md)、検証規則は [DEVELOPMENT.md](DEVELOPMENT.md) を参照する。

- [x] 現行実装と既存差分を確認。
- [x] RED/GREENとprofile互換を実装・確認。
- [x] 全体offlineと静的検証、文書同期。

実装判断: `candidate_title.py` と `candidate_text.py` を追加し、candidateの新規planだけに接続した。旧のtyped証拠・確認状態を保持し、説明文coverageをrequired/preferredの順位比較へ反映する。除外は一致度Eを状態keyへ0.5Eだけ加え、confirmed/uncertain/contradictedの群を逆転せず、除外の記載がある商品を同群内で下げる。原語とカテゴリの欠けた一致分へ同義語最大一致の25%を補い、明示ブランド・型番は独立した完全表現一致とする。各タイトル項目は等重み。新text_profile_idと合成digestは画像結果とSQLiteへ引き継ぐ。

RED/GREEN: `uv run --frozen --offline --no-sync pytest tests/test_candidate_text_scoring.py -q --tb=short` は初回exit1・9失敗（説明文/同義語の順位未反映、構造化数値と説明文の競合、専用field未実装）。実装後exit0・9成功。RED時SHA256は `90fe591b0b8e13b58bd525820b5b4fed0fd1a69ca6e2dcc5ede89fb0c722a2d5`、整形後の最終SHA256は `b206c064fd94ec9349a54d86cdb7a38e338972a7b7a214a36d81820f3894c5e6`。

追加境界test: `tests/test_candidate_text_boundaries.py` 初回はexit1・5失敗/6成功（構造化不明・価格の本文救済、除外順位、英語カテゴリ、診断summaryのprofile）。同一内容の修正後は2 file合計20成功。初回SHA256は `ad72d847c52d04c31b6f1430c7f562f6723b32bb90dd491da0f1a3efa746850e`。さらに否定2表現と属性に隣接しない数値の混同をRED3件で確認し修正した。追加時SHA256は `2bcd8f4c3ea7200868b899dad54d1d5dba891fe18a69aba5bf80aa25c3b722ea`。assertを弱めず、整形後hashは `1088ce8518a9120b228f3e585e8d587a9dbc7e7b06194b8104e9a86770e6626d`。

追加確認: 構造化数値が不明でも説明文の厳密値でconfirmedになる経路をRED1件で確認し、最優先fieldが存在すれば下位sourceを使わないよう修正した。採点profile/digestが新規planへ固定されることもRED1件で確認して接続した。最終境界test SHA256は `df547cc9b39dde0ae2e35b7effe88f3fd9a918f6dc1a46646611eaea3b9ec029`。最終2 fileはexit0・26成功（1.36秒）。新しいモデル推論や外部通信はない。

関連回帰: candidate/ブラウザfixture/語句/画像/JSON/SQLiteの初回は489成功・7skip・1失敗（旧profile期待値）。全体初回は3100成功・20skip・30deselect・3失敗（同義語0点の旧期待2件、旧順位関数をpatchする画像テスト1件）。旧契約の期待を新profileと0.25補助点へ同期し、画像の優先関係のassertを維持してpatch対象を更新した。追加24件と語句・属性画像の計61件はexit0。これらは合成データ・ローカルSQLiteのoffline検証である。

最終検証: `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` はexit0、3109 passed・20 skipped・30 deselected（76.79秒）。新規2 fileは26件で、最終hashは上記のscoring/boundariesの値。`uv run --frozen --offline --no-sync ruff check .`、`ruff format --check .`（383 files）、`uv lock --check --offline`、`uv run --frozen --offline --no-sync python tools/check_markdown_links.py`、`git diff --check` もexit0。途中の3107/3108成功後に追加した構造化不明とplan profile固定の回帰を含む最終結果である。

結果と境界: 5点を新規candidateへ実装し、旧保存結果の点数とJSON互換を保持した。説明文の部分一致は仕様の充足確認とは別の順位点であり、文脈の任意の否定・言い換え・英訳を網羅するものではない。カテゴリは商品語句のhead抽出、ブランド/型番はラベル付き明示入力の範囲。実モデル・実provider・実ブラウザ再検索・未知商品の順位品質は今回未検証で、[NEXT-STEPS.md](../NEXT-STEPS.md) の個別承認後の品質検証へ引き継ぐ。既存の未コミット差分を保持し、commit/pushは行っていない。

## EXEC-124: フロントエンドと実検索の接続

状態: 完了（固定入力の接続試験）。作成・更新: 2026-09-12。

検索診断（2026-09-12、完了）: 利用者の「検索をPlaywrightで行えるか試せ」に従い、既存の選択済み検索語をlocalhost8765からメモリへ読み、日本語指定のAmazon.co.jp検索結果1ページへ匿名Chromiumでアクセスした。最大24件を抽出し、タイトル・価格・ASIN・リンク・画像URLの取得可否、広告表示、重複を検査した。検索navigation1回、retry0、30秒timeout、商品詳細/次ページへの遷移0回。必要なAmazon資材のGETだけを許可し、画像bytesを遮断した。有料API・認証情報・proxyを使わない。合成HTML確認後に実行し、raw検索語/商品値を保存せず件数と成否を記録した。終了時にbrowserを回収し、現在の結果/履歴を保持した。本番providerの置換やランキング変更は対象外。

検索の実測: 2026-09-12 12:02:37〜12:02:39 JST、1.361秒、HTTP200。検索欄と最終URLの検索語が要求と一致し、日本語html langを確認。商品カード48件・一意ASIN48件・不正/重複ASIN0件。先頭24件すべてで、かなを含むタイトル、円価格、ASINに一致するAmazon商品リンク、Amazon画像URLを抽出した。先頭24件中、既存結果とのASIN一致は18件、指定selector/文言でのスポンサーラベル検出は0件（広告の網羅的識別を保証しない）。次ページリンクは存在したが開いていない。CAPTCHA/robot check/主document遮断0件、Amazon資材等を含む許可要求25件・遮断145件。API state全体は前後で一致した。検索語だけを渡し、価格上限/形状条件の適用、画像bytes、詳細ページとの連続処理、複数ページ、反復運用は今回未検証。

検索診断証拠: `/home/products/bonsai-test-logs/20260912-playwright-search/` に実商品の値を含まないscriptと番号別metadata reportを0700/0600で保存。script SHA256=`bab964d78b670ff57161a9c5696625d5924661a0d907bbf3b8994dde73e870db`、report SHA256=`7573e2432fe5a7e3bae3dbd568a18d16a80e39498bbc774bafcb16142f1006c6`。`node /home/products/bonsai-test-logs/20260912-playwright-search/probe.mjs --fixture` は重複・不正ASIN・リンク不一致・主要field・CAPTCHAを確認してexit0。初回の合成タイトルは漢字のみで、かな検査の期待に合わずexit1だったため合成文言を修正した。実検索の通常起動は1回・exit0で完了。結果のread-back、Markdownリンク検査、git diff --checkが成功した。

追加診断（2026-09-12、完了）: 利用者の明示指示により、表示済み24商品の詳細ページをPlaywrightだけで各1回、逐次アクセスした。localhost8765の既存結果を読み、日本語指定・匿名ChromiumでAmazon.co.jpと必要なAmazon静的資材へGETした。API key・有料proxy・他providerを使わず、画像はURL抽出だけとした。各navigationは30秒、タイトル待ちは最大5秒、retry 0、全体15分制限なし。タイトル・価格・説明・仕様・画像URLと同一ASINをメモリ内で検査し、診断は番号別の取得可否・HTTP status・件数だけ保存した。CAPTCHAを回避せず、終了時にbrowserを回収した。結果/履歴の書換え、検索providerの置換は対象外。

Playwright実測: 2026-09-12 11:59:16〜12:00:11 JST、54.930秒、商品document24要求・retry 0。全24件がHTTP200で、かなを含むタイトル、日本語html lang、円価格、特徴箇条書き、商品説明、仕様領域、主画像URLを取得した。ページ内ASINと遷移後URLは全24件で元商品と一致、canonical linkのASIN一致は23件。canonicalの残り1件をURLだけで同一商品と判定せず、ページ内ASINで照合した。A+説明は22件。CAPTCHA/robot check/主document遮断/ASIN競合は0件。静的資材等を含む許可要求2899件、画像・font・media・対象外origin等の遮断2819件であり、外部HTTP要求総数を24件とは扱わない。実行前後のAPI state全体が一致した。

診断証拠: `/home/products/bonsai-test-logs/20260912-playwright-24/` に機密値・商品名・ASIN・URL・本文を含まない実行scriptと番号別metadata reportを0700/0600で保存。script SHA256=`81195ad72572f61103100f43a232fc7181faf30104d82ff343d7551da03373f0`、report SHA256=`32bb2e4e36c7fde068a946c676a4dbd56dee068b6a58b8be70b31eae1f9cc6c6`。`node /tmp/amazon-playwright-24-probe/probe.mjs --fixture` で合成HTMLの主要field・ASIN不一致・CAPTCHAを確認してexit0、通常起動の実24件もexit0。本番コードは変更せず、画像bytesの取得、仕様値の完全な正規化、検索一覧の収集、反復運用の安定性、Outscraper全面置換は未検証。今回の24件について日本語タイトルを直接取得できることを確認した。

目的: 利用者の接続・本番テスト指示に従い、Reactからcandidateの検索語確認、参考画像確認、比較画像確認、検索、保存済み結果表示まで操作する。最初の実検証は利用者指定の既存合成マグカップ入力。SEARCH-FLOW.mdとFRONTEND.mdの確認境界、SigLIP 2既定、Bonsai用途制限を維持する。

開始時: Reactはモックのみ。production_api.pyは別のtyped-ranking経路のjob受付であり、candidateの事前確認controllerではない。既存のdocs/FRONTEND.mdとfrontend/src/screens.tsxの未コミット変更を保持した。

手順: ローカルAPI/controllerと接続画面の契約を固定し、確認省略・重複実行・外部origin拒否のREDを作る。既存candidate/provider adapterを組み合わせ、単一process・検索worker1本で実装する。fixture結合、ブラウザ、全体offline、lint/format/lock/Markdown/diffを検証する。その後、接続先・送信内容・件数・credential種類・費用と保存範囲を示し、実実行の承認を受ける。

境界: 既定モックを維持し、明示起動したローカル接続だけを許す。初回接続は画像あり・1検索の試験入口とし、未接続の画像なしや条件編集を実行可能と表示しない。ブラウザへcredential/承認token/raw応答を渡さず、検索入力やprovider本文を診断ログへ出さない。実結果は既存のprivate SQLite履歴に保存し、旧profile/cacheを再採点しない。外部サービス・credential・費用の承認前にはfixtureだけで検証する。公開配置・認証基盤・複数worker・commit/pushは対象外。

受入条件: 各確認で停止し、再読込や重複POSTで生成/検索が増えない。失敗・期限切れは固定文で表示する。保存済み結果の表示でproviderを再実行しない。offline結果と実サービス結果を区別して記録する。rollbackは追加接続入口を停止して既定モックへ戻す。既存DB/資材/利用者差分を変更しない。

実装: `browser_search.py` がrevisionとoperationを保持して単一workerへ投入する。`browser_candidate.py` は既存CandidateSearchFlowを検索語選択、先行画像、比較画像、最終確認、検索/属性確認、完了へ接続する。`tools/browser_search_runtime.py` は既存の有界provider transport・固定SigLIP/辞書/OPUS-MT・private SQLiteを構成する。`tools/browser_search_server.py` は同じoriginのビルド済みReactとAPIを127.0.0.1だけで配信する。Reactは明示した接続modeだけでAPIを使い、provider応答を通常表示へ変換する。読み直しで検索を再実行しない。

RED: `uv run --frozen --offline --no-sync pytest tests/test_browser_search.py -q` とserver追加testは実装前にModuleNotFoundError・exit2。初回のfrontend単体testもadapter未実装でexit1。初期testは後でformatしたため同一byteのattested証拠とは扱わない。追加の必須表示field欠落testは、SHA-256 `a6434878781fe49ed9c71c7cbde29e862ff8f244e938f90192cba851b2564126`、`npm test -- --run src/connected-api.test.ts` で欠落を受理して1 failed/3 passed・exit1。同じtest bytesを保持した修正後は4 passed・exit0。

検証: 新規Python境界16件成功。既存candidate/runnerを含む関連51件成功。全体offline初回は3056 passed・20 skipped・30 deselected（81.02秒）。frontend単体55件、型/Prettier/build、従来モックの全体ブラウザ35件（44.7秒）、接続ブラウザ1件（6.9秒）成功。接続testはローカルAPIを実起動し、POST受付後の応答消失、段階途中/完了後の再読込、同期二重クリック、外部要求なしを確認した。PythonのHTTP境界testはsocketを使わないHTTP message fixtureで、candidate結合は実SQLiteとprovider fixtureを使う。実provider/modelを呼んだ結果ではない。

最終test hash: browser_search.py test=`f1a00d979b006834632fdb24890ee733e98c1050aaac1b05f096a01dd8c27f76`、server test=`f0ff826bad8f8cce51366ae643819287950a3ae872d276056b9214af02e00eb1`、candidate test=`9b2a710b93504091a628414d9009b35870daeb0f2457183541f3deb012089ef4`、runtime test=`91cf4ed1ecd2ab1aca13c360a1599a662f42cdcba0e1452dc1187d4c896877a0`、connected.spec.ts=`b45590fb15412e70c2fbaa9cfde35c7a23ee93f5b6a0e79d328cab0d964b30a0`。

準備確認: モデル/辞書/各別Pythonの存在とCloudflare/Outscraper設定の検証成功だけを確認し、値は出力していない。credential付きHTTP、Bonsai起動、実モデル推論は0回。localhost8765のfixture画面を目視した。実入力/画像/商品データの診断artifactは作っていない。

次の実行: ローカルBonsai最大2回、Cloudflare参考/比較画像各1枚、Outscraper原語1 query/最大24商品、最大50 polls、商品画像最大24件、SigLIP最大7 batches、自動retry0。900秒後の新規処理停止と各transport timeoutを維持する。Cloudflare/Outscraperの従量分は無料枠を見込まず約0.048633 USDで、回数上限からの見積り。実計上額/強制金額capではない。実行承認後も生成された画像の人間確認を省略しない。結果は新規private directoryのSQLiteへ保存し、provider生応答・例外本文・credentialのログを作らない。実サービス実行は未承認・未実施のためPlanは進行中。

最終検証: runtime上限testと応答の必須field検証を追加した最終treeの全体offlineは3061 passed・20 skipped・30 deselected（76.24秒、exit0）。接続ブラウザは再検証1 passed（6.9秒）、共通画像caption追加後の既定モック画像確認フローも1 passed（17.3秒）。frontend単体55件、型/Prettier/build、Ruff/format/lock/Markdown/diffが成功。SigLIP資材manifestの照合とGiNZA等の任意依存の存在も確認した。実サービス・画像生成・検索は実行していない。

実行承認（2026-09-12）: 利用者が直前提示の接続先・件数・credential利用・概算費用・保存範囲に「はい」と回答した。初回live出力先はrepository外の `/home/products/bonsai-test-logs/20260912-browser-live-01`。8765番を明示live modeで起動し、Reactの `条件を整理` から1回だけ開始した。生成画像ごとの人間確認を維持し、追加検索や自動再試行へ授権を広げない。

初回liveの中間結果: Reactから実Bonsaiによる条件整理が完了し、原語の検索語を選択してCloudflare参考画像1枚の生成が成功した。再読込したReactでも512px画像の描画と `了承して生成` の確認待ちを検証した。比較画像生成・Outscraper検索・商品画像取得・SigLIP評価はまだ実行していない。提示用の正規化済み画像だけをprivate一時ファイルに取り出し、生HTTP応答やcredentialは記録していない。参考画像について利用者の確認を待つ。

初回liveの停止と修正: 参考画像の確認に利用者が了承した時点で、planの期限2026-09-12 10:05:32 JSTを過ぎていた。10:21台の比較生成操作は、CandidateSearchFlow.approve_referenceの先頭の期限検査で拒否される状態だった。追加画像の要求前に停止することを同じ境界のoffline testで再現した。画面には期限と期限切れ状態がなく、押せるボタンから汎用失敗になっていた。live serverを停止し、8765/18080のlistener終了を確認した。比較画像・Outscraper検索・商品画像取得・SigLIP評価を成功扱いにしない。

修正はserver側の期限切れ表示と受付停止。開始から900秒とplan期限の早い方を表示へ渡し、期限切れ後はsnapshot/submitでexpiredへ変える。古い画面からのPOSTもworkerへ渡さない。Reactは具体的な確認期限と期限切れを表示し、画像を閲覧用に保持して実行ボタンを除く。期限を延長したり旧承認を復活させる変更ではない。

期限回帰のRED/GREEN: tests/test_browser_search.pyのSHA-256は `77465e7154c43dcf1823b5f77bf364dc19d0dab653960918a45430714c4dab01`。`uv run --frozen --offline --no-sync pytest tests/test_browser_search.py tests/test_browser_candidate.py -q` は実装前1 failed/10 passed（expired期待にreference、exit1）、同じtest bytesで実装後11 passed（exit0）。candidate testは `e586013a3ee1e436eb4d80639dbc0770ff22ab14540a918d2838092fb41cb0fc`。関連Python18件、frontend単体55件、型/Prettier/build、Ruff/format/lockが成功。接続ブラウザは期限切れでPOST0件・画像保持と既存の確認順序を含む2件成功（8.6秒）、test hashは `54a8502519fd3785ddb04358acbf0e5adfce01643be2b851fd94833e10cab205`。

追加決定（2026-09-12）: 利用者の「全体の15分制限を削除しろ」に従い、上記の全体900秒とplan期限をブラウザ実行から撤廃する。前段の期限表示修正は経緯として残す。現在のserverは `plan_lifetime=None` とし、開始時のcontroller/transport deadlineを持たない。Bonsaiの全体停止timerを各推論900秒へ置き換え、条件整理の完了時にモデルを回収してから確認待ちへ入る。個別のHTTP/subprocess timeout、回数上限、明示了承を維持する。比較画像生成後のsingle-use承認15分は全体制限と区別し、消費後の検索/属性確認へ引き継がない。旧診断CLIの既定期限や既存履歴形式は変更しない。

全体期限撤廃のRED: 検索語/参考画像の各確認待ちを1時間進めるtestは2 failed/10 passed。runtimeの推論別timeout testは2 failed/1 passed。修正後のcontroller/candidate/runtimeを含む関連82件は成功した。実時間を待つ代わりにclockを進めたoffline検証であり、実サービス再実行ではない。

撤廃後の最終検証: 全体offlineは3065 passed・20 skipped・30 deselected（79.54秒、exit0）。検索語確認待ち1時間、参考画像確認待ち1時間、商品取得中1時間をclockで進めても実candidateからfixture商品/SQLite履歴まで完了した。controllerは画像承認を消費した後の期限を除去する。Bonsaiは各呼出に独立した900秒timerを持ち、3回目を拒否し、準備成功/失敗とも所有modelを回収することを注入fixtureで確認した。frontend単体55件、接続ブラウザ2件（8.5秒）、型/Prettier/build、Ruff/format/lock、Markdown/diffが成功。追加の実provider呼出は0回。

撤廃後のtest SHA-256: browser_search=`c873ae71de3087ffc954c3d5d4a0de4d840df810ed2e35dc631ea10b9603ed1e`、browser_candidate=`15e0e0c43e8f0d02a7549c29632a1ebb8c3161010c1dddbd04637c502e47b12e`、browser_runtime=`b0034b22860d2f0ecef490ca043e059c7bf0b642aa1d1fa074fd79c048b45b04`。RED後に商品取得待ち・消費後の期限除去・process回収の検証を追加しているため、先行REDと同一bytesの証明には使わない。

再実行条件: 元のlive sessionは終了した。再開には新規sessionが必要で、Bonsai・参考画像からやり直す場合は既存の合計回数承認を超えるため、追加実行の範囲を提示して明示承認を受ける。元画像/DB/ログを上書きせず、新規private directoryを使う。画像確認時にも画面の期限を示す。

再実行承認（2026-09-12）: 全体15分制限の撤廃と既存入力/同条件/追加見積り約0.049 USDを提示後、利用者が「再実行せよ」と指示した。新規出力先 `/home/products/bonsai-test-logs/20260912-browser-live-02`、localhost8765のReactから `条件を整理` を1回送信し、HTTP202/workingを確認した。Bonsai最大2回、Cloudflare画像2枚、Outscraper1 task/最大24商品/50 polls、商品画像最大24件、SigLIP最大7 batches、retry0。既存Cloudflare/Outscraper認証情報を使い、画像ごとの確認を維持する。外部送信先はapi.cloudflare.com、api.outscraper.cloud/amazon-productsと同host結果URL、m.media-amazon.com。Bonsaiはlocalhost18080。全体期限はなく、個々の通信/推論timeoutを維持する。

再実行の中間結果: live-02は実Bonsaiの条件整理が完了し、Reactで承認済み原語を選択して参考画像生成を1回送信した。Cloudflare参考画像1枚の生成後、APIはreference/revision2/画像1枚/期限なしを返した。React再読込でも512×512の画像表示と了承ボタン、期限表示なしを確認した。条件整理後のBonsai port18080非LISTENも確認済み。比較画像・Outscraper・商品画像取得・SigLIP・履歴完了はまだ実行していない。serverは確認待ちで保持し、今回の参考画像を利用者へ提示する。

live-02の比較生成: 現在の条件に取っ手の有無を含めないことを確認した後、利用者が「では進んで下さい」と了承した。Reactの `了承して生成` を1回送信し、比較画像1枚が成功、計2枚となった。APIはcomparison/revision3と画像承認期限2026-09-12 10:53:46 JSTを返した。全体期限とは別のsingle-use画像承認期限である。2枚を利用者へ提示し、Reactで両画像512×512の表示と最終確認画面の検索ボタンを確認した。Outscraper開始前で停止し、今回の2枚と検索内容への最終確認を待つ。

live-02完走（2026-09-12）: 比較画像と検索内容への利用者の「はい」を受け、画像承認の有効性を確認してReactの検索ボタンを1回押した。HTTP202/working/revision5、画像承認consume1件を確認。2026-09-12 10:42:17 JSTにcomplete/saved=true/24商品となり、画像承認consumeから128.457秒で検索・評価・保存まで完了した。未確定条件0件で、追加の属性選択を必要としなかった。

実結果: APIとprivate SQLiteの24商品を内部で照合し、全件の取得価格が3000円以下、価格不明0件、必須判定confirmed24件、画像評価available24件、candidate-siglip2-appearance-v1を確認した。履歴1件・参照画像2枚、DB integrity_check=ok、保存JSON/画像のdigest一致、各画像512×512、directory0700/DB0600を確認。比較画像は人間確認用に生成して保存し、candidateの採点はSigLIP 2参考画像方式を使った。実課金額やOutscraperの実poll回数は収集していない。

React検証: 結果を見る操作で24カードを描画し、各タイトル/価格/必須状態をAPIと照合した。最後のカードまで表示でき、再読込後も同じ24商品・revision5だった。この結果表示検証中のPOST0件、pageerror0件、外部originへのbrowser要求0件。商品リンクは開いていない。新規の検索や画像生成を追加していない。server8765は結果閲覧用に保持し、Bonsai18080は非LISTEN。

到達範囲: 既存合成入力1件について、Reactから実Bonsai・実Cloudflare・実Outscraper・商品画像取得・固定SigLIP 2・SQLite保存・React結果表示まで完走した。未知入力の順位品質、任意入力/画像なし/条件編集/永続履歴一覧の実接続、公開配置、実課金明細の照合は検証範囲に含めない。今回の価格/必須判定の成功を丸み判定の未知精度保証へ一般化しない。先行のoffline/ブラウザ回帰結果は維持し、今回の実実行は別証拠として記録した。

商品リンクの日本語化（2026-09-12）: 利用者の指摘どおり、live-02の24 URLすべてに英語path `/-/en/` が残っていた。共通 `productLink` で英語pathを除去し、`language=ja_JP` を設定する。ConnectedAppとProductNameで共用し、商品path/他queryと既存URL安全性検査を維持する。provider取得、履歴内容、検索を変更せず、配信中のfrontendを再buildした。単体REDは2 failed/9 passed（英語URLがそのまま出力）、同一test SHA-256 `aa4c0f097eda770be49c1b2fa5b734e80451021034f2da371561f61853c62719` のGREENを含むfrontend全体59件と型/Prettier/buildが成功。実結果を返すlocalhost画面の24リンクを再読込し、全件で日本語指定/同じASIN・origin/revision5を照合した。POST0件、Amazon商品ページは開いていない。接続ブラウザ3件（9.5秒）、Markdown/diffも成功した。リンク先のAmazon側描画を実測したとは扱わない。

日本語リンクの再修正（2026-09-12）: 利用者がリンク先のAmazon本文が英語のままと報告した。前回は画面だけの変換で、APIの24 URLには英語localeが残り、画面URLにも英語の商品名slugが残っていた。API snapshotとfrontendで商品IDを標準 `/dp/ASIN` へ正規化し、`language=ja_JP` を指定する。元の履歴は変更しない。Python REDはAPI snapshotに英語URLが残って1 failed/11 passed、frontend REDはslugが残って1 failed/10 passed。修正後の関連Python16件、frontend59件と型/Prettier/buildが成功。

実確認: 認証情報を使わない英語localeの新規Chromiumから、修正URLの商品ページ1件のdocumentだけを取得した。HTTP200/主document要求1回/html lang=ja-jp/商品タイトル要素あり/日本語のカート操作文言あり/英語のAdd to Cartなし/challengeなしを確認した。利用者自身のログインsession設定は変更していない。商品ページの本文やURLをartifactへ保存していない。

配信反映: 完了済みのAPI状態を別processのメモリだけへ受け渡し、外部処理を持たない結果閲覧serverへ同じ8765番で切り替えた。24商品・2参照画像・revision5を保持し、検索/生成0回。実APIとDOMの24リンクすべてが同じASINの日本語指定標準URLとなり、両者の完全一致とPOST0件を確認した。以前のserverを単に再起動して結果を消したり、結果を作るために再検索したりしていない。

日本語リンク再修正の最終検証: 全体offline3072 passed・20 skipped・30 deselected（77.84秒）、frontend59件、接続ブラウザ3件（8.8秒）、型/Prettier/build、Ruff/format/Markdown/diffが成功した。test hashはbrowser_search=`8c3744fbb21ebca2fa6642b1c4864d55b21c7e83c66b2d60379af2b0ce216c19`、product-name=`551442dee8378b7d3fa3e261654b935873466f6d10859d7b576e69e99dc4ef39`。PythonはRED後に不正URL拒否の検証とformatを追加しており、先行REDと同一byteの証明には使わない。

日本語タイトル取得の試験（2026-09-12）: APIの日本語指定だけでは英語名が返っていたため、日本語指定のAmazon検索URLをOutscraperへ渡す要求schema 2.1を追加した。旧2.0とdigestを分離し、検索語確認と送信URLへの応答bindingを保つ。関連offline147件、全体offline3083件（20 skipped・30 deselected、75.99秒）、Ruff/format/Markdown/diffが成功。その後、利用者承認で1 task・5 poll・126.57秒、24件取得/正規化成功・reject 0件。ただし日本語文字を含むタイトルは2件で、目的は未達。前回の商品と同じASINは17件、そのうち日本語文字を含むタイトルは1件。ブラウザの既定からschema 2.1の有効化を外し、表示中結果と履歴は変更しない。正式な日本語タイトルを取得する方法は引き続き未解決。

## 次期フロントエンドの自前開発（2026-09-11）

利用者の明示決定により、次期画面はこのリポジトリで自前開発する。外部納品待ちを解除し、[SEARCH-FLOW.md](../SEARCH-FLOW.md) と [FRONTEND.md](FRONTEND.md#11-次期フロントエンドの自前開発方針) を目標仕様にする。React + StyleXのオフライン画面を[EXEC-117](#exec-117-react-stylexのオフライン画面)で実装した。実バックエンド/API接続は後続作業である。過去の個別EXECにある委託・納品待ちの記述は当時の判断と検証範囲として残し、現在の着手制約には使わない。

[TASK-008](#task-008-次期検索フロー-v2-の実装) と [TASK-001](#task-001-検索処理のジョブ化) の画面実装と後続作業:

1. `frontend/` にReact + StyleXの画面とモックを配置した。通常ボタンは176×48px、検索履歴一覧の「削除」「開く」は96×36px、開発起動は `npm run dev` とする。Figmaはレイアウトの参考とし、[視覚統一契約](FRONTEND.md#13-次期uiの視覚統一契約) を優先する。
2. [オフラインモック](FRONTEND.md#14-オフラインモック) を共通部品で実装した。任意入力・条件編集、画像あり/なし、段階的承認、商品調査、結果・履歴、失敗回復、期限切れと二重操作防止をChromiumで確認した。フォント・画像はローカル資材で、実バックエンド・Bonsai・外部API・credentialを使わない。
3. 最終承認controllerとserver起動構成を整備し、ローカルAPIへ接続する。candidateの現行契約と既存暫定APIの差分は接続前に確認する。
4. 実サービスを含む検証は、送信先・内容・回数・credential・費用を提示して明示承認を得た範囲で行う。

検索実行のローカル専用・単一host・単一process・worker 1本、SigLIP 2既定、Bonsai用途制限、検索語と画像の確認手順は維持する。自前開発への変更を既存画面やAPIの接続完了として扱わない。

2026-09-11追加決定: React + StyleX、Figmaはレイアウト参考、Noto Sans JP、6桁の色コード、白黒基調と指定された青・灰色、共通ボタンと進行アニメーションを文書の正本へ固定する。文書化に続く実装指示を受け、UI-017〜UI-020のモックを実装した。実サービス接続・品質検証は対象外。検証結果はEXEC-117へ記録する。

## 1. 文書の役割

この文書は、amazon-explorer が目指す利用者価値、現在確認できる到達点、未接続の計画境界、成功条件を一か所で示す。個々の作業状態や実行手順を置き換えるものではない。

- 現在の実装事実は `src/`、`frontend/`、`tools/`、`tests/`、`specs/`、`pyproject.toml` を正とする
- 商品検索の次期利用者フローは [SEARCH-FLOW.md](../SEARCH-FLOW.md)、技術契約は [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、テスト方針は [DEVELOPMENT.mdの統合済みテスト方針](DEVELOPMENT.md#統合済みテスト方針) を正とする
- 大規模タスクと小規模タスクはこの文書の [大規模タスク一覧](#統合済み大規模タスク一覧) と [小規模タスク一覧](#統合済み小規模タスク一覧)、構造的負債は [ISSUES.md](ISSUES.md#統合済み技術的負債トラッカー) で管理する
- 複雑な変更の実行方法は [Execution Plan規約](DEVELOPMENT.md#統合済みexecution-plan規約)、進行中のPlanはこの文書で管理する
- 完了済み・実施中の変更記録は [WORKLOG.md](WORKLOG.md)、マージ済み変更の要約は [CHANGELOG.md](CHANGELOG.md) を参照する

## 2. プロダクトゴール

日本語の自然文で表された購入条件から Amazon.co.jp の商品候補を取得し、商品名、属性、価格、避けたい条件を説明可能な形で比較して、利用者が候補を選びやすい検索体験を提供する。

次期検索フローでは、外部APIを呼ぶ前に利用者が検索意図と実行内容を確認できること、観測できない商品属性をLLMで補完しないこと、任意の画像生成を商品実在性の証拠として扱わないこと、検索結果と費用・データ境界を再現可能な状態として残すことを目標に加える。

AIレビューハーネスは商品検索機能とは独立した開発統制である。変更、テスト、レビュー、署名証拠を結び付けることが目的であり、ハーネスの存在を商品検索の品質、外部サービス接続、または本番配備の証明として扱わない。

## 3. 確認済みの現在地

2026-09-10の[EXEC-104](#exec-104-属性別の画像比較と対象領域の分離)で、属性別形状比較の実験経路をcandidate/履歴へ接続した。全体offline2980件成功。自動切出し・実順位品質は未達であり、iGPU性能は未検証。

### 3.1 現行商品検索

現行の利用者経路は、StreamlitまたはCLIから同期的に実行する次の4段階パイプラインである。

1. ローカルBonsaiのOpenAI互換APIから商品属性JSON文字列を得て、現行互換モデルへ正規化する
2. 日本語を優先して1件の検索語を選び、Outscraperの非同期タスクをポーリングする
3. Amazon商品データを決定的に正規化し、重複候補を除く
4. SudachiPy、TF-IDF、条件一致、価格、否定条件で採点し、総合スコア降順で表示する

次の境界まで実装されている。

| 領域 | 確認済みの実装 |
|---|---|
| 入出力 | Streamlitの入力・状態・結果表示と、上位結果を出すCLI |
| Bonsai | `/chat/completions`、`/models`、応答形状検査、属性JSON補正。商品検索でOpenAI APIへ自動fallbackしない |
| Outscraper | APIキー必須、HTTPS・同一origin検査、redirect拒否、Timeout・ConnectionError・429・5xxの上限付き再試行、完了までの上限付きpolling |
| 正規化 | タイトル、価格、通貨、評価、レビュー数、画像、URL等の型補正と重複除去 |
| ランキング | 商品名0.45、属性0.35、価格0.20の既定係数、条件語重み、最大0.5の否定条件減点 |
| 保存 | 入力・設定・内容に結び付くローカルJSONキャッシュ、TTL判定、同一ディレクトリ内のアトミック置換 |
| 品質境界 | 外部通信を通常テストから遮断するpytest guard、Ruff、uv lock、GitHub ActionsのPython 3.10 / 3.13定義 |

現行キャッシュはRDBではない。認証、認可、利用者別永続領域、レート制限、構造化メトリクス、配布・復旧方式も商品アプリには実装されていない。local job境界は独立実装済みだが、現行商品アプリの検索実行には未接続である。

### 3.2 次期検索domain基盤

`src/search_v2/` には、現行パイプラインから隔離した次の基盤がある。

画像生成の現在の公開入口は [EXEC-080](#exec-080-4方向生成を製品フローから除去) の参考画像1枚で停止し、明示了承後は条件別偽画像N枚だけを生成する。Nは1〜3、通常1+N calls、先行作成2回と両回の後続生成を合わせて最大8 calls。4方向adapterは互換・診断用だけに残す。ranking式は維持し、core新規履歴はschema 3.0で参考画像1枚、暫定schema 5.0履歴は参考画像＋偽画像を保存する。新フローは固定1条件のbackend実サービスE2Eを完走したが、順位監査で材質未判定・材料名の色誤抽出を確認した。EXEC-082で修正し、EXEC-083で検索専用属性を追加した。修正後の実サービス順位品質・追加属性の実モデル品質は未確認である。

- unknown fieldと型coercionを拒否するstrict intent
- full raw response body、OpenAI互換envelope、content全体のstrict JSON、strict intentを検証し、非blocking intentは検索queryを構築できる場合だけ受理するnetwork非依存Bonsai adapter
- 固定system promptだけをsystem messageへ置き、検索可能な最大12種類の固定fieldと確認待ち `ambiguities` を分け、文字列長・配列数を制限する非空のllama.cpp互換bounded compact生成schemaを `response_format.schema` へ含め、完全19-field schemaは別digestとstrict最終検証に維持するcanonical request、1-call利用量lifecycleと、no-proxy・no-redirect・no-retry・1 MiB上限を固定するrequest v8・Requests HTTP transport
- 価格mode、文字数、配列数、曖昧性の整合検査
- source input、prompt、schema、responseを結ぶprovenance digest
- NFKC正規化、重複排除、入力中に根拠がないbrand・model numberの除去
- SudachiPy `SplitMode.C`＋内容語filterと英数字 `[a-z0-9]+` の決定的tokenizer
- blocking ambiguityで停止する、最大2件・日英各1件の決定的query plan
- owner・session・intent・query・Outscraper request・任意画像・provider allowance・runtime digest・15分期限を固定するcanonical承認plan
- `draft` から商品受信・正規化・検索完了または固定失敗までのrevision付きstate machineと、raw tokenを保持しない同一process内のsingle-use claim
- Bonsai・Cloudflare・Outscraperのcall・token・整数micro-USDを送信前予約する同一process内の利用量ledger
- exact FLUX.2 klein 4B model、固定4方向、attempt別seed、prompt contract、共有参照PNGを固定するcredential-free Cloudflare multipart request descriptor
- 開始済み4-call予約と画像生成stateを再検証し、固定順のmultipart HTTP、厳密な応答、JPEG・PNG・WebPから512px PNGへの正規化、511px派生参照、全成功時だけの `image_review` 遷移を行うCloudflare mock実行境界
- 1回のGETへ日英最大2件のqueryを反復し、exact parameter digestと第2確認後のexecution permitを固定するcredential-free Outscraper request descriptor
- permitと開始済み利用量予約を再検証し、API keyを固定headerへだけ注入してtask作成・same-origin exact結果pathへの上限付きpollingを行うOutscraper Requests HTTP境界
- 検証済みOutscraper request、query provenance、provider request ID、換算profileへ結び、観測値だけをstrict candidateへ投影して未観測属性を未知のまま残すnetwork非依存の商品normalizer
- exact host allowlist、global DNS・peer IP一致、redirect・byte・pixel上限を注入resolver・transportへ強制するimage proxy core、1回の有界なTCP用IPv4・IPv6名前解決、検証済みIPへ直接接続して元host名をTLS検証へ使うHTTPS transport、64-bit pHash・固定ONNX CLIP asset・縦横比を維持した224×224内の全体保持とモデル平均余白・CPU encoder・30秒 `spawn` process・fixture embedding score境界
- 固定profile、日英title coverage、観測属性の重み付き一致、strict price mode、平均評価・レビュー件数の最小weight補助評価、欠損weight再正規化、negative cap、stable tie-break、score breakdownを持つ画像無効の決定的ranking v3
- 値型ごとのstrict条件、9 keyのtrusted registry、証拠優先順位、`match`・`mismatch`・`unknown`・`conflict`、必須状態を先に扱う順位keyを持つ、現行ranking未接続の型付き条件domain
- 既存1回のBonsai strict応答でJSON-nativeな型付き条件候補を受け、local IDとtrusted registryで条件または固定blocking issueへ変換するnetwork非依存adapter
- 正規化済み商品の専用color、固定feature全体、限定した商品名表現を、本文を保持せず `structured`・`title_exact` 証拠へ変換するnetwork非依存adapter
- readyな型付き条件proposalを再構築照合し、限定商品証拠、全条件裁定、必須状態、固定分母scoreを、v3とdomain separationした独立 `typed-ranking-v4` へ結ぶnetwork非依存ranking境界
- strict intent後の処理をtyped proposal、query plan、typed ranking、prediction projectionへ分け、本文や元例外を保持せず固定失敗段階だけを返すholdout後処理境界と、検索前のblocking ambiguityをquery planなしの正規なblocking予測へ投影する評価境界
- 成功済みOutscraper executionと承認・利用量・runtime bindingを再検証し、観測値だけの商品正規化、ranking、結果あり・正常0件・工程別固定失敗のstateを結ぶoffline後半pipeline
- Bonsaiから第1確認、任意の参考画像1枚の了承と偽画像確認、最終確認、single-use承認、Outscraper、正規化、ranking、完了stateまでを利用者操作ごとに停止して結ぶoffline orchestration
- strictな表示用snapshot、owner内の冪等保存、未期限の一覧・詳細・参考画像取得、個別削除、30日期限削除を行うローカルSQLite検索履歴repository

この基盤は実Bonsai、実Cloudflare、現行Bonsai client、実Outscraper、Streamlit、CLIへ接続されていない。in-memory ledgerとstate、ローカル単一fileの履歴repositoryは、複数process・host・再起動をまたぐ承認・利用量・保存の原子性を保証しない。Bonsai・Cloudflare・OutscraperのRequests transport、Cloudflareの画像応答、Bonsaiから検索完了までの段階別orchestrationと画像途中失敗後の回復はmock・fixture・合成JPEG・PNG・WebPで、商品画像DNS resolverは注入 `getaddrinfo` fixture、process分離はfake process・pipe・clock、HTTPS transportはsocket・TLS・HTTPResponse fixture、proxy serviceは合成allowlistと注入resolver・transportで、履歴変換・repositoryは一時SQLiteと合成表示データで検証した。WSL2では外部DNSへ進まない固定失敗経路の実 `spawn` とbyte IPCを1回、repository-local固定ONNX modelではlocal-only code pathの合成画像1枚をCPU子processへ通す明示opt-in smokeを1回確認した。受領31枚は固定4参照と自己参照を除いたnear 9枚・far 18枚に分け、各scoreの再現、near/far中央値の分離、pairwise AUC 0.790123457を確認した。事前基準0.80へ未達である。far 18枚には利用者指定の属性を固定し、黒・有線・ゲーミング・マウス4枚の平均score 0.945551862が、色だけ異なる無線ゲーミングマウス6枚の0.875869567と非マウス6枚の0.830395143より高いことを確認した。この4枚を画像上の正例へ移した接続方式非依存の固定score評価は、AUC 0.961538462、正例中央値0.942146431、負例中央値0.843137443となった。画像scoreは色、外観形状、商品種別など視覚的特徴だけの補助評価とし、有線・無線は商品名と構造化された観測属性で判定する。元のAUC未達は履歴baselineとして維持し、この再計算だけで画像rankingを有効化しない。near 13枚はlocal画像を個別に確認し、全て黒いマウス、うち11枚はゲーミング用途を外観から確認、n5・n6の2枚は用途未知として固定した。静止画像だけでは接続方式を確定できないため、near 13枚の接続方式は全て未知へ訂正した。用途未知の候補2枚の平均scoreは0.941389590で、用途を確認できた候補7枚の0.932454373より高いため、scoreから未知属性を補完しない。pytestのPython network guardはspawn子processとnative codeをOSレベルで隔離しない。運用allowlist値・実hostへのDNS/TLS/HTTP、Windows native、検索文の意味理解、検索文から得た4方向の実参照画像・複数queryによるCLIP ranking品質、画像ranking、認証、API・UI、現行pipelineへの接続は未実装・未確認である。offline orchestration、画像service・resolver・transport、合成画像と単一条件31枚のCLIP characterization、履歴変換・repositoryの成功も実画像生成、実Amazon候補、実host通信、一般的な生成・順位品質、認証済み利用者分離を証明しない。存在するmodel、adapter・request descriptor・HTTP transport・normalizer・ranking・orchestration・repository、単体テストだけで次期検索フローが利用可能になったとは扱わない。

上段は基盤実装時点の境界記録である。後続の [EXEC-062](#exec-062-outscraper単一task実商品接続試験) では、明示承認済みの実Outscraper task作成1回・poll 9回・24候補の応答検証と正規化に成功した。Bonsaiからrankingまでの一続きの実サービスE2E、現行pipeline、API、UIへの接続は引き続き未確認である。

上段のAUC 0.790123457・0.961538462と属性別平均は、比較可能性のため残すEXEC-031以前のcenter-crop履歴である。現行のapplication profileは `clip-rgb-bicubic-contain-mean-pad-224-v1` で、画像全体を縦横比どおり224×224内へ収め、正規化後0となるモデル平均余白へ中央配置する。現行固定値はcase1 AUC 0.759259259、接続方式を除く視覚評価AUC 0.928571429、case2限定診断AUC 0.642857143・期待順位一致27/53、case3限定診断AUC 0.468750000・期待順位一致80/173である。case2・case3には候補とは独立した4方向参照がなく、画像rankingは無効のままである。

### 3.3 AIレビューハーネス

`tools/ai_review/`、`specs/`、`containers/` には、strict artifact契約、read-only snapshot、networkなしoffline runner、review packet、分離broker、署名、attested judgeを固定順序で扱う基盤がある。実装・fixture・ローカルテストの成功と、承認済みcredential・送信内容・費用を使うlive 7-phase E2Eは別の証拠である。

### 3.4 現行作業ツリーのローカル確認

2026-09-06の現行作業ツリーで、次を確認した。

- `uv lock --check --offline`: 成功、79 packagesを解決
- `uv run --frozen --offline --no-sync ruff check .`: 成功
- `uv run --frozen --offline --no-sync ruff format --check .`: 成功、200ファイルが整形済み
- `uv run --frozen --offline --no-sync python tools/check_markdown_links.py`: 成功、現行Markdown 16件のlocal link 1306件（うち見出しanchor 905件）、見出し1672件、code fence 203組
- `uv run --frozen --offline --no-sync pytest -q tests/test_markdown_links.py`: 成功、4 passed
- bounded compact schemaのfocused・関連回帰: focused 17 passed、Bonsai関連185 passed・2 skipped、次期検索940 passed・9 skipped
- `uv run --frozen --offline --no-sync pytest -m 'not live_api'`: 成功、1710 passed、9 skipped、3 deselected
- Python 3.10 AST 200件とzero-width scan 270件: 成功
- 固定ONNXの明示runtime test: 本作業では未実行。標準offline suiteではopt-in test 9件をskipした
- `git diff --check`: 成功

pytestはBonsai、Outscraper、OpenAI、Cloudflareの実サービスを呼んでいない。次期フロントエンド、現行Streamlitの起動、ブラウザ操作、画面描画、検索完了までのE2Eはこの確認で実行していない。

## 4. 計画済みだが未接続の境界

| 領域 | 実装済み | 未実装・未検証 |
|---|---|---|
| Bonsai v2 | strict intent、正規化model、固定system prompt、完全schemaと `pattern` だけを除いた非空生成schemaを別digestへ結ぶrequest v5、canonical request、注入transportによる1回限りの実行・利用量記録、no-proxy・no-redirect・no-retryのbounded Requests HTTP transport、full raw response・envelope・content全体・非blocking検索可能性のfail-closed adapter、正規化失敗と検索不能を区別する本文非保持diagnostic、同じstrict応答のJSON-native型付き条件候補とlocal registry adapter、readyまたはquery-less blockingを返すtyped proposal付き第1確認のoffline orchestration接続、更新promptのlocalhost限定1 call | legacy現行pipeline接続、条件分解の意味品質評価 |
| 検索実行 | Sudachi/英数字tokenizer、最大2件の決定的query plan、schema 3.0のtyped proposal付き承認から完了・固定失敗までのstate、query-less blocking専用第1確認、single-use承認、同一process内の利用量予約、Outscraper複数query descriptor・承認permit、mock Requests HTTP・task・polling・利用量確定、明示承認済みの実Outscraper単一task・24候補正規化、商品正規化・typed-ranking-v4へのoffline後半pipeline、各確認で停止するBonsaiから完了までのoffline orchestration、Cloudflare途中失敗後の明示回復state | 確認画面、Bonsaiからrankingまでの実サービスE2E、legacy現行pipeline接続 |
| 画像 | 先行1枚の確認後に偽画像だけを生成する公開入口、single-use了承と失敗回復、暫定production job・既存履歴までのoffline接続。本番Cloudflare向けcredential-free 4方向multipart request descriptor、seed・prompt・参照PNG境界、mock HTTP・厳密な応答検証・JPEG・PNG・WebPから512px RGB PNGへの正規化・511px派生参照・4枚完了state、生成後の採用・破棄、先行1枚からの作り直しと再確認、途中失敗後の画像なし続行を含むoffline orchestration、server-side image proxy core、有界DNS resolver、Windows/WSL互換 `spawn` によるDNS process isolationと5秒application deadline、pinned-IP HTTPS transport、合成allowlistで各層を束ねるserver-side service、64-bit pHash重複判定、repository-local固定ONNX asset、CPU encoder、30秒CLIP process isolation、embedding score境界、case1からcase3のcharacterization、実ブラウザ候補とテスト用gpt-image独立4方向参照による初回E2E診断、適格なcategory-only 2条件の1 pass・1 fail | 修正後のCloudflare実生成・製品接続、運用allowlist値・実hostへのDNS/TLS/HTTP、Windows nativeでのprocess確認、複数カテゴリ・複数条件の正式CLIP評価、画像ranking有効化、model配布 |
| 商品処理 | 現行Outscraper正規化とranking、未知属性を維持するnetwork非依存v2正規化、post-Outscraper非LLM境界、型付き条件・証拠裁定domain、Bonsai候補・限定商品証拠adapter、必須状態を先に扱うtyped-ranking-v4、画像無効の固定ranking profile v3・stable tie-break・score breakdown、v4を第1確認・承認・state・完了state・schema 2.0表示履歴まで結ぶoffline後半pipeline、holdoutの正解・予測分離と条件・裁定・順位のoffline集計契約、安全重視の固定acceptance policy、最初の適格holdout assessment、Bonsai JSON object宣言と本文非保持diagnostic、時間上限なしdevelopment regression、非空のllama.cpp互換生成schema、request v5のstrict intent実行確認、本文非保持の後処理4段階とquery-less blocking投影、非blocking intentの検索可能性検査、更新promptのlocalhost限定1 call、query-less blockingの第1確認接続、初回画像E2E診断 | 未知商品に対するtyped rankingの独立評価、適格な実CLIP scoreの採否、legacy現行pipeline・API・UI接続 |
| UI | 現行Streamlit画面 | 次期フロントエンドは自前開発。typed API、確認画面、Lightbox、AlertDialog、承認済み条件要約、検索履歴画面の実装とバックエンド接続は後続作業 |
| 永続化 | ローカルJSONキャッシュ、typed decisionからschema 2.0表示用履歴への変換、owner分離した30日履歴のローカルSQLite `user_version=2` repository、冪等保存、個別・期限削除、旧version 1の非破壊拒否 | 認証、legacy現行pipeline・API・UI接続、複数worker向け保存方式、backup・明示migration・定期purge |
| 公開運用 | 開発用Streamlit・CLI | 認証、認可、利用上限、ジョブ化、観測可能性、SLO、配布、rollback |
| attested review | 実装・ローカル検証・credential-free配備確認 | 承認済みlive 7-phase E2E、nonce ledgerの保持・backup・容量・rotation方針 |

Cloudflare画像、複数query、検索履歴などは承認済み仕様である。承認state、段階別orchestration、商品画像HTTPS transport、完了resultからの履歴変換、ローカル検索履歴repositoryはoffline境界まで実装したが、実provider・実画像host・認証・現行pipeline・API・UIへの接続と検証が完了するまでは現行機能として表示しない。

次期フロントエンドはこのリポジトリで自前開発する。[SEARCH-FLOW.md](../SEARCH-FLOW.md) と [FRONTEND.md](FRONTEND.md) を目標仕様として、画面設計・実装・ローカルAPI接続を後続作業へ登録する。外部納品を着手条件にしない。

## 5. 目標とPlanの一覧

### 5.1 実行中

| 目標 | 状態と残り | 実行計画 |
|---|---|---|
| [TASK-001](#task-001-検索処理のジョブ化) | 最終承認済み検索をlocal jobへ投入し、状態取得・協調的取消・schema 5.0履歴取得を行うlocal ASGI API factoryまで実装済み。server起動構成、最終承認controller、次期フロントエンドには未接続 | [EXEC-056](#exec-056-ローカル単独利用向け検索ジョブ基盤)、[EXEC-075](#exec-075-暫定本番検索のjob履歴接続と無quota方針)、[EXEC-076](#exec-076-local検索job履歴http-api) |
| [TASK-007](#task-007-attested-ai-review境界の実装) | 7-phase境界とcredential-free配備確認まで実装済み。承認済みlive E2Eとnonce長期運用が残る | [EXEC-002](#exec-002-attested-ai-review境界の実装) |
| [TASK-008](#task-008-次期検索フロー-v2-の実装) | 暫定production profileは限定liveでOutscraper 1 task、24商品画像、CLIP 7 batches、ranking v5まで成功した。[EXEC-075](#exec-075-暫定本番検索のjob履歴接続と無quota方針) で最終承認済み検索からlocal job・schema 5.0履歴までをoffline接続し、本番quotaなしを明示した。品質の既知制約は維持し、API・UI・新serviceを含む実provider E2Eは未確認。次期フロントエンドの設計・実装・接続は自前開発の後続作業 | [EXEC-073](#exec-073-outscraper商品画像から暫定ranking-v5への統合境界)、[EXEC-074](#exec-074-人間確認で停止する商品画像ranking-live-runner)、[EXEC-075](#exec-075-暫定本番検索のjob履歴接続と無quota方針)、[SEARCH-FLOW.md](../SEARCH-FLOW.md) |
| [TASK-005](#task-005-ランキング品質評価の確立) | [EXEC-065](#exec-065-未知の視覚条件に対する条件別counterfactual画像評価)で、minimum-positive v4の条件別scoreを、条件名や正解labelを使わず候補batchの観測中点へ揃える較正を実装した。development相対合格後、未知のデスクライト・クランプ条件1 caseを固定した結果、順位分離AUCは1.0だったが共通閾値0のaccuracyは0.875で絶対基準0.90へ未達だった。このcaseを再調整へ使わず、最低2 category・各2 caseの残りを別の未使用条件で評価する。画像rankingは無効のままである | [EXEC-064](#exec-064-実ブラウザ候補とgpt-image独立参照のclip診断)、[EXEC-065](#exec-065-未知の視覚条件に対する条件別counterfactual画像評価)、[TD-008](ISSUES.md#td-008-為替とランキング品質の評価) |

[EXEC-003](WORKLOG.md#統合済み履歴plan-exec-003) は第1マイルストーンの完了記録であり、TASK-008全体の完了を意味しない。同Plan内のOpenAI商品検索案は後続判断で置換済みで、現在の商品検索providerはBonsaiである。

#### 再開位置

以下は判断が更新された順の記録であり、後の項目が前の停止判断を上書きする。現在はEXEC-080の4方向生成除去を完了し、E2E実検索は停止中である。以下の旧判断は履歴として保持する。

- 実行環境はWindows 11 / WSL、Intel Core Ultra 9 288Vと確認できた。[EXEC-024](#exec-024-windowswsl向け画像dns-process-isolation) から [EXEC-033](#exec-033-case3固定候補と自己参照除外clip診断) までで、固定ONNX、全体保持前処理、case1からcase3の診断を完了した。新profileのcase1 AUCは0.759259259、接続方式を除く視覚評価AUCは0.928571429、case2限定診断はAUC 0.642857143・期待順位一致27/53、case3限定診断はAUC 0.468750000・期待順位一致80/173である。[EXEC-034](#exec-034-型付き条件と証拠別ランキングの設計) から [EXEC-038](#exec-038-型付き条件ranking-v4境界) で型付き条件domain、両側adapter、typed-ranking-v4を実装し、[EXEC-039](#exec-039-型付きranking-v4のoffline検索経路移行) でv4を第1確認・承認・state・検索後半pipeline・schema 2.0履歴へ移行した。[EXEC-040](#exec-040-未使用holdoutの評価契約と集計境界) で未使用holdoutの入力・集計契約を実装し、[EXEC-041](#exec-041-holdout品質合格ポリシーの固定) で安全重視の全体・全category合格基準を実データ閲覧前に固定した。[EXEC-042](#exec-042-固定済み基準による未使用holdout評価) では適格な2 category・4 caseを評価したが、localhost Bonsaiの4応答が全てstrict検証を通らず、ranking前に停止してassessmentは `fail` となった。[EXEC-043](#exec-043-bonsai構造化出力と安全診断) でJSON object宣言、application `max_tokens` なし、本文非保持の6段階診断を実装し、使用済みCSVを再実行したが4件とも300秒で `request_failed` となった。[EXEC-044](#exec-044-bonsai-application-timeout撤廃) で公開契約からtoken上限とtimeoutの両項目を削除した。[EXEC-045](#exec-045-時間上限なしbonsai-development-regression) の承認済み再実行では4件全てのHTTP応答が完了したが、全件が `content_not_json` でranking前に停止した。[EXEC-046](#exec-046-llamacpp互換bonsai生成schema) で非空の互換schemaをrequest v5へ追加し、local converterとoffline回帰を完了した。[EXEC-047](#exec-047-request-v5-local-bonsai-development-regression) の初回4要求はmodel ready前に失敗したが、health-ready再実行では4件全てがstrict intentまで通過し、その後の評価用後処理で停止した。[EXEC-048](#exec-048-holdout後処理段階診断とquery-less-blocking投影) で本文非保持の4段階diagnosticとquery-less blocking投影を固定した。段階診断付き部分再計測では2件が `query_plan_invalid` となり、利用者が実行数を「全体で1件」と訂正した時点で送信済みの3件目を中断し、4件目は送信しなかった。部分実行のassessmentは生成していない。[EXEC-049](#exec-049-bonsai-intent検索可能性contract) で同じstageを生む非blocking intentの検索可能性contractをoffline修正した。[EXEC-050](#exec-050-bonsai検索可能性失敗段階の分離) では更新promptを先頭1 case・合計1 callだけ確認し、HTTP応答後の受理前に `intent_normalization_invalid` で停止した。正規化失敗と検索不能を区別するdiagnosticはoffline実装済みである。[EXEC-051](#exec-051-bonsai生成schema整合とdraft診断) から [EXEC-053](#exec-053-生成時検索可能性schemaのlocalhost-1件確認) で生成schema整合と先頭1件のblocking proposal確認まで進め、[EXEC-054](#exec-054-query-less-blockingの第1確認接続) でquery-less blockingを専用第1確認へ返して後続providerを予約前に止めるoffline境界を実装した。[EXEC-055](#exec-055-query-less-blocking第1確認のlocalhost-1件結合確認) で同じ使用済み先頭1件を現行orchestratorへ1回だけ通し、queryなしの `BlockingIntentReview` まで結合確認した。2026-09-05の利用者判断により未知データでの独立評価は実施しない。case2・case3の独立4方向参照も保留し、品質未確認の画像rankingは無効のままとする。Cloudflare・Outscraper用credentialはまだ不要であり、取得・共有しない。
- [EXEC-076](#exec-076-local検索job履歴http-api) で固定local ownerのjob投入・状態取得・取消・schema 5.0履歴詳細取得をlocal ASGI API factoryへ接続した。次の再開位置は、自前開発する次期画面に向けた最終承認controller・server起動構成・UI接続、または別承認による新serviceとHTTPを含む実provider E2Eである。
- 2026-09-07の利用者判断で画像の未知データ評価を再開し、[EXEC-064](#exec-064-実ブラウザ候補とgpt-image独立参照のclip診断) の初回E2E診断と2件の適格category-only試験を完了した。電気ケトル条件はpassしたが、未使用のオフィスチェア条件はpairwise AUC 0.291666667、中央値逆転でfailし、カテゴリ間の再現性を確認できなかった。画像rankingは無効のまま維持する。
- 固定済みオフィスチェアartifactのcrop、同一dataset負例によるcontrastive margin、leave-one-out centroidも全て不合格だった。[EXEC-065](#exec-065-未知の視覚条件に対する条件別counterfactual画像評価) では、未知語をSudachiPyで正規化済みsource spanへ結ぶ最大3条件、望ましい基準1枚と1条件だけ違反させた最大3枚のreference set、条件別marginをoffline実装した。承認済みdevelopment較正ではテスト用gpt-imageをexact 6 calls、retry 0で使い、ケトル黒色は通過したが椅子ヘッドレスト・適格条件pool・椅子集約が基準未達、色・メッシュが構成不適格だった。閾値を採用せず、独立holdoutと製品の4方向仕様変更へ進んでいない。次は追加生成ではなく、固定artifactによる原因診断と方式再設計である。
- 次期フロントエンドは自前開発へ移行した。今回の文書更新後の再開対象は画面設計・API契約・実装方式の整理であり、外部納品の確認は不要である。
- [TASK-007](#task-007-attested-ai-review境界の実装) はfull 7-phase OpenAI live E2Eとnonce ledger長期運用が残る。前者はcredential、外部送信、費用の明示承認を得た場合だけ、[EXEC-002](#exec-002-attested-ai-review境界の実装) の未完了項目から再開する。
- TASK-008の次マイルストーンへ着手するときは [Execution Plan規約](DEVELOPMENT.md#統合済みexecution-plan規約) に従う新しい `EXEC-*` 節をこの文書へ追加し、TaskとPlan inventoryからリンクする。

### 5.2 候補

候補は着手承認、優先順位、期限、実装方式が確定した状態ではない。

| 目標 | 主な根拠 |
|---|---|
| [TASK-002: キャッシュ基盤の運用対応](#task-002-キャッシュ基盤の運用対応) | [TD-002](ISSUES.md#td-002-ファイルキャッシュのライフサイクルと競合) |
| [TASK-003: 多利用者向けセキュリティ境界](#task-003-多利用者向けセキュリティ境界の構築) | [TD-003](ISSUES.md#td-003-アクセス制御と利用量制御) |
| [TASK-004: 観測可能性と配布](#task-004-観測可能性と配布パイプラインの整備) | [TD-004](ISSUES.md#td-004-観測可能性とログ管理)、[TD-006](ISSUES.md#td-006-ciと配布方式) |

### 5.3 小規模作業と継続負債

- 現在、[小規模タスク一覧](#統合済み小規模タスク一覧) に未完了項目はない
- P1/P2の横断課題と対応状況は [技術的負債トラッカー](ISSUES.md#統合済み技術的負債トラッカー) を参照する
- 再現済みの不具合と検証範囲は [ISSUES.md](ISSUES.md) を参照する

### 5.4 Execution Plan inventory

| 文書 | 状態 | 役割 |
|---|---|---|
| [EXEC-166](#exec-166-空行による条件誤判定と修正位置を直す) | 完了 | 空白fragment除外・エラー原文位置・稼働反映 |
| [EXEC-165](#exec-165-接続失敗の種類を記録して表示) | 完了 | 接続失敗の分類・固定診断と同一タブ内保持 |
| [EXEC-164](#exec-164-条件整理の再起動後の停止を解消) | 修正・合成回帰完了、実症状照合は未確認 | 起動別作業先・server識別子による再起動回復 |
| [EXEC-141](#exec-141-新しい条件分類を稼働接続画面へ反映) | 完了 | 最新画面/履歴の稼働接続と初回clarification後の再整理修正 |
| [EXEC-140](#exec-140-希望条件と否定条件の自然文指定を拡張) | 完了 | 共通条件分類・指定なし除去・文章修正・希望予算と日英照合 |
| [EXEC-126](#exec-126-商品取得をplaywrightへ移行) | 完了 | Playwright検索・詳細取得、互換adapterとcache移行 |
| [EXEC-125](#exec-125-説明文の条件一致とタイトル比較の拡張) | 完了 | 説明文の部分一致・同義語・タイトル専用field |
| [EXEC-123](#exec-123-角の輪郭濃度を補正) | 完了 | 添付画像で残る角の薄れを補正 |
| [EXEC-122](#exec-122-完了段階の配色とスクロール維持) | 完了 | 完了した丸の青背景と更新時のスクロール維持 |
| [EXEC-121](#exec-121-枠線の濃淡を画素で検証して改善) | 完了 | 100%表示の角の薄さを再現し、内側1px輪郭へ変更 |
| [EXEC-120](#exec-120-細い外枠の描画改善) | 完了 | 円弧の角丸と整数行高で1px枠の描画を整える |
| [EXEC-119](#exec-119-トグルの動き角丸履歴操作の調整) | 完了 | 滑らかな切替と角丸、履歴ボタンの縮小、危険色の統一 |
| [EXEC-118](#exec-118-主要ボタンとトグル丸枠の表示修正) | 完了 | dev/prodのボタン配色、スイッチと円形表示の修正 |
| [EXEC-117](#exec-117-react-stylexのオフライン画面) | 完了 | 自然文入力から結果・履歴までの自前UIとブラウザ検証 |
| [Execution Plan規約](DEVELOPMENT.md#統合済みexecution-plan規約) | 規約 | 複雑タスクの作成、進捗、検証、判断、rollbackの共通要件 |
| [EXEC-094](#exec-094-省略された仕様名の推論を改善する) | 進行中 | 省略された仕様名の実Bonsai診断と、本番要求の比較・修正 |
| [EXEC-095](#exec-095-仕様定義を与えたbonsaiの属性同定を検証する) | 完了 | 定義追加7/12→11/12、資料不足・曖昧16件の保留0件。RAG進行基準未達 |
| [EXEC-096](#exec-096-属性同定の保留をアプリケーションで強制する) | 完了 | 推論候補と確定条件を分離し、根拠未確認の数値属性を後続処理へ渡さない |
| [EXEC-097](#exec-097-商品候補から属性を発見して確認後に評価する) | 完了 | 資料事前準備なしの候補取得・観測属性・確認・評価のoffline backend |
| [EXEC-098](#exec-098-bonsaiの視覚条件抽出を候補経路へ接続する) | 完了 | 既存VisualConditionSetを使う抽出・確認計画・画像prompt |
| [EXEC-099](#exec-099-新旧検索フローのoffline連続検証) | 完了 | 新candidate経路と既存画像承認・CLIP・履歴経路の接続境界を検証 |
| [EXEC-100](#exec-100-candidate結果jsonのdecimal復元) | 完了 | JSON境界だけでDecimal条件を復元しstrict domainを維持 |
| [EXEC-101](#exec-101-candidate経路の画像承認clip履歴接続) | 完了 | candidateから段階的画像承認・CLIP・SQLite履歴まで接続 |
| [EXEC-102](#exec-102-candidate経路の実画像付き実行) | 進行中 | 新candidate経路の実画像・商品取得・CLIP・履歴検証 |
| [EXEC-103](#exec-103-辞書と文脈による検索語の自動選択) | 進行中 | ローカル辞書と構文/語義の選択、保留と候補確認 |
| [EXEC-001](WORKLOG.md#統合済み履歴plan-exec-001) | 完了 | TASK-006のbootstrapとTDDパイロットの履歴 |
| [EXEC-002](#exec-002-attested-ai-review境界の実装) | 進行中 | TASK-007のattested境界と残るlive・運用境界 |
| [EXEC-003](WORKLOG.md#統合済み履歴plan-exec-003) | 完了 | TASK-008第1マイルストーンのstrict domain基盤と置換済みprovider判断の履歴 |
| [EXEC-004](#exec-004-bonsai-v2-strict応答境界) | 完了 | TASK-008第2マイルストーンのBonsai envelope・content・strict intent境界 |
| [EXEC-005](#exec-005-決定的検索tokenizer) | 完了 | TASK-008第3マイルストーンのSudachi・英数字tokenizerとquery planner統合 |
| [EXEC-006](#exec-006-2段階承認と費用予約境界) | 完了 | TASK-008第4マイルストーンの2段階承認、single-use token、call・token・費用予約 |
| [EXEC-007](#exec-007-cloudflare-4方向request-builder) | 完了 | TASK-008第5マイルストーンの4方向multipart request契約、seed、参照PNG境界 |
| [EXEC-008](#exec-008-outscraper複数query-requestと明示承認guard) | 完了 | TASK-008第6マイルストーンの複数query、exact parameter digest、single-use承認guard |
| [EXEC-009](#exec-009-決定的商品正規化と未知属性境界) | 完了 | TASK-008第7マイルストーンの観測値だけを使う商品正規化、未知属性、非LLM境界 |
| [EXEC-010](#exec-010-安全な画像取得phash固定clip境界) | 完了 | TASK-008第8マイルストーンのserver-side image proxy、pHash重複判定、固定CLIP asset・embedding境界 |
| [EXEC-011](#exec-011-決定的ランキングv2とスコア内訳) | 完了 | TASK-008第9マイルストーンの固定profile、欠損weight再正規化、negative penalty、stable sort、score breakdown |
| [EXEC-012](#exec-012-bonsai-v2-requestと実行境界) | 完了 | TASK-008第10マイルストーンのBonsai v2 canonical request、注入transport、利用量lifecycle境界 |
| [EXEC-013](#exec-013-bonsai-v2-http-transport) | 完了 | TASK-008第11マイルストーンのRequests HTTP adapter、no-redirect・no-proxy・bounded response境界 |
| [EXEC-014](#exec-014-outscraper-v2-httptaskpolling境界) | 完了 | TASK-008第12マイルストーンのOutscraper HTTP・task・polling・利用量確定境界 |
| [EXEC-015](#exec-015-検索後半pipelineと完了state) | 完了 | TASK-008第13マイルストーンのOutscraper完了結果・正規化・ranking・完了stateの結合境界 |
| [EXEC-016](#exec-016-cloudflare-http応答と画像正規化) | 完了 | TASK-008第14マイルストーンのCloudflare multipart HTTP・応答検証・PNG正規化・4枚完了境界 |
| [EXEC-017](#exec-017-offline検索orchestration) | 完了 | TASK-008第15マイルストーンのBonsaiから検索完了までの明示確認付きoffline統合境界 |
| [EXEC-018](#exec-018-cloudflare画像生成失敗後の回復state) | 完了 | TASK-008第16マイルストーンの途中失敗記録、明示的一括再試行・画像なし続行境界 |
| [EXEC-019](#exec-019-owner分離した30日検索履歴repository) | 完了 | TASK-008第17マイルストーンの冪等保存、owner分離、一覧・詳細・個別削除・30日期限削除境界 |
| [EXEC-020](#exec-020-完了検索から表示用履歴への変換と保存) | 完了 | TASK-008第18マイルストーンの完了result・承認済み情報から表示用snapshotへの変換と冪等保存結合 |
| [EXEC-021](#exec-021-pinned-ip画像https-transport) | 完了 | TASK-008第19マイルストーンのDNS再解決を避ける商品画像HTTPS transport境界 |
| [EXEC-022](#exec-022-server-side画像dns-resolver) | 完了 | TASK-008第20マイルストーンの有界なTCP用IPv4・IPv6名前解決境界 |
| [EXEC-023](#exec-023-server-side画像proxy-service) | 完了 | TASK-008第21マイルストーンのserver-side allowlist・DNS・pinned-IP transport統合境界 |
| [EXEC-024](#exec-024-windowswsl向け画像dns-process-isolation) | 完了 | TASK-008第22マイルストーンのWindows 11 / WSL互換spawn、DNS application deadline、byte IPC、子process回収境界 |
| [EXEC-025](#exec-025-固定onnx-clip-cpu-runtimeと品質smoke) | 完了 | TASK-008第23マイルストーンのrepository-local固定ONNX asset、CPU encoder、process isolation、受領1組による識別smoke |
| [EXEC-026](#exec-026-単一条件の複数画像clip-characterization) | 完了 | TASK-005の単一検索条件・固定31画像による自己参照なしCLIP baseline。暫定AUC基準は未達 |
| [EXEC-027](#exec-027-far画像の属性別hard-negative-characterization) | 完了 | TASK-005のfar 18枚に対する利用者指定属性と、属性別CLIP score傾向の固定 |
| [EXEC-028](#exec-028-near画像の目視属性characterization) | 完了 | TASK-005のnear 13枚に対する目視属性と、目視で確定できない属性のunknown固定 |
| [EXEC-029](#exec-029-高評価レビュー件数を使うranking-v3) | 完了 | TASK-005の通常ランキングへ、平均評価とレビュー件数による最小weightの補助componentを追加 |
| [EXEC-030](#exec-030-画像ランキングの視覚的特徴限定) | 完了 | TASK-005の画像評価を視覚的特徴へ限定し、接続方式を構造化属性へ分離する契約と再計算baselineの固定 |
| [EXEC-031](#exec-031-case2固定候補と自己参照除外clip診断) | 完了 | TASK-005のcase2候補、期待順位、rating・review count、独立参照不足と自己参照除外診断の固定 |
| [EXEC-032](#exec-032-全体保持clip前処理とcase3準備) | 完了 | 全体保持・モデル平均余白への移行とcase1・case2再固定を完了。case3受領前時点の準備記録 |
| [EXEC-033](#exec-033-case3固定候補と自己参照除外clip診断) | 完了 | case3の20候補、期待順位、rating・review count、独立参照不足と自己参照除外診断を固定した |
| [EXEC-034](#exec-034-型付き条件と証拠別ランキングの設計) | 完了 | 型付き条件、trusted registry、証拠優先順位、生成画像と商品画像の比較、次期ranking順序を設計した |
| [EXEC-035](#exec-035-型付き条件と証拠裁定の最小domain実装) | 完了 | strictな型付き条件、repository内registry、証拠裁定、必須状態と安定順位keyをoffline TDDした |
| [EXEC-036](#exec-036-観測商品から型付き証拠へのadapter) | 完了 | 観測済み商品属性と限定した商品名表現を固定registryのtyped evidenceへ変換する |
| [EXEC-037](#exec-037-bonsai型付き条件候補adapter) | 完了 | Bonsai strict応答の候補をtrusted registryで型付き条件または確認待ちへ変換する |
| [EXEC-038](#exec-038-型付き条件ranking-v4境界) | 完了 | 型付き条件・商品証拠・裁定・必須状態を独立したranking v4 schemaへ接続した |
| [EXEC-039](#exec-039-型付きranking-v4のoffline検索経路移行) | 完了 | ranking v4を第1確認、承認、state、検索後半pipeline、表示用履歴へ明示的なschema更新で接続した |
| [EXEC-040](#exec-040-未使用holdoutの評価契約と集計境界) | 完了 | 未使用holdoutの正解・予測artifactを分離し、条件・裁定・順位を別指標で集計するoffline評価契約 |
| [EXEC-041](#exec-041-holdout品質合格ポリシーの固定) | 完了 | 実holdout閲覧前に安全重視の全体・全category合格基準と独立assessmentを固定した |
| [EXEC-042](#exec-042-固定済み基準による未使用holdout評価) | 完了 | 適格な2category・4caseへ固定policyを適用し、Bonsai strict応答失敗4件を除外せず `fail` と確定したlocalhost限定評価 |
| [EXEC-043](#exec-043-bonsai構造化出力と安全診断) | 完了 | 本文非保持の失敗段階、llama.cpp JSON object宣言、output-token上限なしを実装し、4件のdevelopment regressionが300秒で全て `request_failed` となることを確認した |
| [EXEC-044](#exec-044-bonsai-application-timeout撤廃) | 完了 | request schema 4.0で生成token上限とapplication timeoutを公開契約から削除した。時間上限なしの実model再実行は別工程 |
| [EXEC-045](#exec-045-時間上限なしbonsai-development-regression) | 完了 | 使用済みCSVの4件を時間上限なしで完走し、全件の `content_not_json` と空schemaでは生成grammarが有効にならない原因を確認した |
| [EXEC-046](#exec-046-llamacpp互換bonsai生成schema) | 完了 | 非空の生成用schemaをrequest v5へ結び、完全なapplication schemaによる最終検証を維持した |
| [EXEC-047](#exec-047-request-v5-local-bonsai-development-regression) | 完了（development regression） | 更新promptを先頭1件・合計1 callだけ確認し、安全な受理前拒否まで記録した |
| [EXEC-048](#exec-048-holdout後処理段階診断とquery-less-blocking投影) | 完了 | 本文非保持の後処理4段階とquery-less blocking予測をoffline TDDした |
| [EXEC-049](#exec-049-bonsai-intent検索可能性contract) | 完了 | `query_plan_invalid` の再発を防ぐ非blocking intentの検索可能性検証とprompt規則をoffline TDDした |
| [EXEC-050](#exec-050-bonsai検索可能性失敗段階の分離) | 完了（offline診断） | 承認済み1 callの安全拒否を記録し、正規化失敗と検索不能を本文なしで区別できるようにした |
| [EXEC-051](#exec-051-bonsai生成schema整合とdraft診断) | 完了（承認済み1 call・offline改善） | 次の1 callがdraft schemaで停止した事実を記録し、生成schemaの既知差分と安全なdraft違反groupを改善した |
| [EXEC-052](#exec-052-新生成schemaのlocalhost-1件確認) | 完了（承認済み1 call・offline改善） | 新生成schemaでdraft検証を通過して検索不能段階まで進み、次の生成時検索可能性制約と安全診断を追加した |
| [EXEC-053](#exec-053-生成時検索可能性schemaのlocalhost-1件確認) | 完了（承認済み1 call・blocking proposal確認） | 生成時検索可能性schemaでstrict intentとtyped proposal生成まで成功し、安全な確認待ちで停止した |
| [EXEC-054](#exec-054-query-less-blockingの第1確認接続) | 完了 | query-less blockingを専用第1確認へ返し、承認・画像・商品取得へ進ませないoffline orchestration境界 |
| [EXEC-055](#exec-055-query-less-blocking第1確認のlocalhost-1件結合確認) | 完了（承認済み1 call・query-less blocking結合確認） | 使用済みCSVの先頭1件を現行orchestratorへ1回だけ通し、query-less blockingの専用第1確認へ到達することをlocalhost限定で確認した |
| [EXEC-056](#exec-056-ローカル単独利用向け検索ジョブ基盤) | 完了 | 単一ホスト・単一processで検索をbackground実行するSQLite job状態とworker境界 |
| [EXEC-057](#exec-057-bonsai本番prompt-cacheとrequest-context縮小) | 完了 | request v6で完全schema本文の二重送信を除き、本番prompt cacheを明示する。4,096は最大入力契約に不足するため8,192を維持する |
| [EXEC-058](#exec-058-request-v6prompt-cache-localhost結合テスト) | 完了 | request v6のfull JSON・strict intentと2回目のKV cache hitを同じlocalhost `llama-server`で確認した明示opt-in結合テスト |
| [EXEC-059](#exec-059-bonsai応答時間のprompt生成分離診断) | 完了 | 同一request v6をcold・warmで実行し、prompt処理353.47倍・99.72%短縮、全体1.52倍・34.13%短縮を本文非保持のllama.cpp timingで確認した |
| [EXEC-060](#exec-060-bonsai-196-token目標のcompact-wire応答) | 完了 | 既定値を省略するrequest v7のcompact wire応答を従来の完全19-field strict intentへ復元し、代表fixtureを126 Bonsai tokensにした。実model・Core Ultraは未測定 |
| [EXEC-061](#exec-061-bonsai-bounded-compact-schema) | 完了 | request v8のcompact wireを生成grammarでも有効な固定field profile、文字列長、配列数へ制限し、超過時は切断せず確認待ちへ戻す |
| [EXEC-062](#exec-062-outscraper単一task実商品接続試験) | 完了 | 明示承認済みの固定合成queryをtask作成1回・retry 0で実Outscraperへ送り、poll 9回後の24候補を応答・正規化契約へ通した |
| [EXEC-063](#exec-063-bonsai自由語と商品名のsource-grounding) | 完了 | 一続きE2Eで検出した無根拠商品名の `ready` 通過と桁区切りJPY未対応を、SudachiPy source spanと有界価格parseでfail closedに修正した |
| [EXEC-064](#exec-064-実ブラウザ候補とgpt-image独立参照のclip診断) | 完了（適格2条件で1 pass・1 fail） | 隔離Chromiumの実商品画像、候補を入力しないgpt-image 4方向参照、事前目視label、固定ONNX CLIPを一続きで診断し、別カテゴリで単一条件passを再現できないことを確認した |
| [EXEC-065](#exec-065-未知の視覚条件に対する条件別counterfactual画像評価) | 進行中（development相対合格、未知条件1-case probeは不合格） | 未知の視覚条件をsource-groundedな原子条件へ分け、条件名やlabelに依存しない候補batch較正を最低2 category・各2 caseの独立holdoutで最終評価する |
| [EXEC-067](#exec-067-cloudflare基準画像1-call-live準備) | 完了（live 1試行失敗、再実行なし） | Cloudflare credentialを非表示で読み、固定合成条件の基準画像1枚だけを明示opt-in後に生成できるlive専用境界 |
| [EXEC-068](#exec-068-cloudflare-live失敗段階診断) | 完了 | 初回live失敗を再実行せず、credential・provider本文なしの固定段階へ分類できる診断境界 |
| [EXEC-069](#exec-069-cloudflare-live画像内容診断) | 完了（追加1 call・画像内容で拒否） | 別承認の追加1 callでHTTP 200・成功応答後のlocal画像検証失敗を特定し、provider形式をPNGに限定する契約不一致をoffline再現した |
| [EXEC-070](#exec-070-cloudflare応答画像の安全な形式正規化) | 完了（offline） | Base64画像をJPEG・PNG・WebPから安全に検証し、従来どおりmetadataなしRGB PNGへ正規化する |
| [EXEC-071](#exec-071-counterfactual-cloudflare最小live-runner) | 完了（最小live成功） | 本番用counterfactual参照2枚をCloudflareのexact 2 callsで生成・正規化保存した |
| [EXEC-072](#exec-072-実商品画像proxy固定clip最小live-runner) | 完了（限定live成功） | 運用候補hostの商品画像1枚をproduction proxyで取得し、固定CLIPへ接続した |
| [EXEC-073](#exec-073-outscraper商品画像から暫定ranking-v5への統合境界) | 完了（offline統合） | 承認済みOutscraper 1 taskの実行結果を正規化し、商品画像proxy・固定CLIP・暫定ranking v5へ接続する |
| [EXEC-074](#exec-074-人間確認で停止する商品画像ranking-live-runner) | 完了（修正後の限定live成功） | Cloudflare参照生成後に同一processで人間確認を待ち、承認後だけOutscraper・商品画像・暫定ranking v5へ進むlive専用runner |
| [EXEC-075](#exec-075-暫定本番検索のjob履歴接続と無quota方針) | 完了（offline統合） | 本番quotaを無効化し、最終承認済み検索をlocal job、Outscraper、商品画像、固定CLIP、ranking v5、schema 5.0履歴locatorへ接続する |
| [EXEC-076](#exec-076-local検索job履歴http-api) | 完了（offline API） | server-side固定local ownerでjob投入・状態取得・取消・schema 5.0履歴取得を行うASGI APIを追加した |
| [EXEC-077](#exec-077-参考画像1枚の確認後に4方向と偽画像を生成) | 完了（offline接続・Figma） | 先行1枚の確認で停止し、明示承認後だけ4方向と条件別偽画像を生成するbackend境界をjob・履歴へ接続し、利用フローとFigmaを同期した |
| [EXEC-078](#exec-078-自然言語から画像確認ランキング履歴までのbackend-live-e2e) | 限定live完了・停止中 | 旧6-callフローで23商品rankingと履歴再読込を確認。4方向品質は不合格のまま、EXEC-080で製品要件から除外 |
| [EXEC-079](#exec-079-4方向画像の視点指示修正と限定再生成) | 終了（要件撤回） | 視点品質は未解決。利用者指示により4方向生成をEXEC-080で除去し、追加診断と3D/API調査を停止 |
| [EXEC-080](#exec-080-4方向生成を製品フローから除去) | 完了（offline・Figma） | 参考画像1枚→了承→条件別偽画像のみへ変更し、backend・履歴・runner・Figma・仕様を同期 |
| [EXEC-087](#exec-087-属性推論の条件欠落検出と応答ログ) | 修正・準備完了（offline） | 条件欠落の確認待ちと全生成応答のprivateログを用意 |
| [EXEC-086](#exec-086-bonsai単体の検索専用属性推論) | 単体実行完了・不合格 | 共通色・容量下限・食洗機対応の実Bonsai単体推論を先行確認 |
| [EXEC-085](#exec-085-共通属性変更後の実検索と順位監査) | 保留（単体推論不合格） | 同一固定入力で本番backendフローを実行し、全候補の条件根拠と順位・履歴を照合する |
| [EXEC-084](#exec-084-共通属性だけをプリセットにする) | 完了（offline） | カテゴリ専用プリセットを検索専用の推論属性へ移す |
| [EXEC-083](#exec-083-入力に基づく検索専用属性の追加) | 完了（offline） | Bonsaiの不足属性提案を原文で検証し検索単位で承認・判定へ接続する |
| [EXEC-082](#exec-082-材質条件と材料名の色誤抽出を修正) | 完了（offline） | 材質をtyped必須判定へ接続し、赤土等の材料名を本体色から分離する |
| [EXEC-081](#exec-081-参考画像生成失敗の安全な診断) | 限定診断実行済み・HTTP 429確認 | Cloudflareが画像生成をHTTP 429で拒否。制限の内訳と初回失敗の原因は未確定 |

## 6. 成功条件

### 6.1 現行機能を維持する変更

1. StreamlitまたはCLIから現行4段階パイプラインを実行できる
2. 外部API失敗を正常な0件と混同せず、APIキーをURL、ログ、キャッシュキー、利用者向け例外へ露出しない
3. キャッシュ、正規化、ランキングの変更が入力・設定・versionを含むキーまたは明示した移行方針へ反映される
4. `uv lock --check --offline`、`uv run --frozen --offline --no-sync` でのRuffとoffline pytest、`git diff --check` が成功する
5. モック、fixture、server起動、実サービス、ブラウザ、実hostのどこまで確認したかを分けて報告する

### 6.2 TASK-008全体

1. Bonsai contentを単一JSON objectとしてfail-closedに検証し、strict intentとprovenanceへ接続する
2. blocking ambiguityを解消し、条件、先行参考画像、商品検索について実行対象に対応する明示確認を得るまで、その外部処理を開始しない
3. optional画像生成は既定OFFとし、生成物を実在商品の証拠にしない
4. Outscraper後の未観測属性を別LLMで推測補完せず、未知値として保持する
5. text、attributes、price、optional imageの各scoreと欠損時のweight再正規化を説明できる
6. 0件を含む完了結果をowner分離したsnapshotとして冪等保存し、閲覧・削除で外部処理を再実行しない
7. 外部通信、credential、call数、token、費用、失敗を検索単位で追跡し、上限を強制する
8. domain、adapter、API、UI、保存、削除の回帰テストに加え、必要な実サービス・ブラウザ・運用E2Eを別証拠として完了する

各Taskの最終受入条件は [大規模タスク一覧](#統合済み大規模タスク一覧) と対応Execution Planを優先する。

## 7. スコープ境界と正本

- 現行商品検索providerはBonsaiであり、OpenAI商品検索への自動fallbackは採用しない
- OpenAIを使うAIレビューハーネスは商品検索provider判断と別系統である
- Outscraper後の商品属性をBonsai、OpenAI、その他LLMで補完しない
- ComfyUIとSSH分散実行は現行または次期の採用済み経路ではない
- `docs/old/examples/` は過去の検証資料であり、現行仕様・実装・テストの根拠にしない
- Planや文書に記載された機能は、実行経路への接続と対応検証が確認できるまで実装済みと扱わない
- offlineテスト、schema検査、credential-free probeを、外部API、課金、ブラウザ、実hostのE2Eへ読み替えない
- AIレビューの実行コマンド、期待結果、停止・再実行規則は [HARNESS-RUNBOOK.md](HARNESS-RUNBOOK.md) を正本とし、現在状態、履歴、信頼境界、AI契約を各標準文書へ分ける

要件の実装状態と現在の制約は [REQUIREMENTS.md](REQUIREMENTS.md#統合済み制約)、設計上の責務分割は [BACKEND.md](BACKEND.md#統合済み全体設計) を参照する。


## 統合済み大規模タスク一覧

> 統合元: `docs/TASKS.md`。統合前の文書は `docs/old/` に保存する。


> **標準文書との関係:** 現在の到達点と進行中の計画は [GOAL.md](#開発目標)、問題と作業台帳の入口は [ISSUES.md](ISSUES.md) とする。この文書は大規模タスクのID、詳細、完了条件を保持する。

### 1. 役割

この文書は、複数の設計判断、複数モジュール、段階的な検証を要する成果単位を管理する。候補項目は現行実装で確認できる制約から導いたものであり、着手承認、担当者、期限、実装方式が決まったことを意味しない。`TASK-006` は安全側MVP、`TASK-007` はattested境界とproduction接続を扱う。

- 小規模な作業は [小規模タスク一覧](#統合済み小規模タスク一覧)
- 再現可能な不具合は [ISSUES.md](ISSUES.md)
- 構造上の改善理由は [技術的負債トラッカー](ISSUES.md#統合済み技術的負債トラッカー)
- 着手する大規模タスクの詳細計画は [Execution Plan規約](DEVELOPMENT.md#統合済みexecution-plan規約) に従い、この文書へ追記する

状態は `候補`、`未着手`、`計画中`、`実行中`、`ブロック`、`完了` を使う。

### 2. 一覧

| ID | 状態 | 成果 |
|---|---|---|
| TASK-001 | 実行中 | 検索処理のジョブ化 |
| TASK-002 | 候補 | キャッシュ基盤の運用対応 |
| TASK-003 | 候補 | 多利用者向けセキュリティ境界の構築 |
| TASK-004 | 候補 | 観測可能性と配布パイプラインの整備 |
| TASK-005 | 実行中 | ランキング品質評価の確立 |
| TASK-006 | 完了 | AI相互レビューとTDDハーネスの導入 |
| TASK-007 | 実行中 | attested AI review境界の実装 |
| TASK-008 | 実行中 | 次期検索フロー v2 の実装 |

現行方針はローカル単独利用である。将来、外部公開へ変更する場合は候補Taskの優先順位、認証、保存、複数process運用を改めて決める。

### TASK-001: 検索処理のジョブ化

- 状態: 完了
- 根拠: [TD-001](ISSUES.md#td-001-同期的な検索実行)
- 現行: Streamlit実行内でBonsai、Outscraperポーリング、正規化、採点を同期実行する
- 目標: 長時間検索をWeb画面の1回の実行から分離し、状態照会、期限、キャンセル、再実行を明確にする
- backend到達点: 固定local owner、SQLite状態、同一bindingの冪等投入、worker 1本、状態照会、取消、開始期限、再起動回復、30日保持に加え、最終承認済み検索からOutscraper、商品画像、固定CLIP、ranking v5、履歴locator、local ASGI API factoryまでをoffline実装済み。server起動構成、最終承認controller、現行・次期UIへは未接続

想定する成果物:

1. 検索ジョブと状態遷移のデータモデル
2. ジョブ投入・実行・状態取得の境界
3. ワーカーの同時実行1件とOutscraper task 1回の操作契約。本番の累積利用量quotaは設けない
4. UIの進捗、再読込、失敗、キャンセル表示
5. タイムアウト、再起動、重複投入のテスト

着手前に決めること:

- 2026-09-05の利用者判断によりローカル専用とし、単一ホスト・単一process・同時実行1件を対象にする
- job metadataは終了後30日保持し、検索結果本体は既存の30日履歴repositoryへ分離する
- 同じ承認済みbindingの重複投入は同じjobを返し、自動再実行しない。再実行には新しい承認bindingを要求する
- ownerはserver-sideの固定local ownerを使う。公開・複数利用者へ変更する場合はTASK-003を先行する

完了条件:

- UI要求を占有せずに検索を継続できる
- queued、running、succeeded、failed、timed_out等の状態を検証できる
- 利用者が別の利用者のジョブを参照できない
- 外部API上限とキャンセル時の扱いが文書・テストで一致する

着手時は個別Execution Planを作成する。

### TASK-002: キャッシュ基盤の運用対応

- 状態: 候補
- 根拠: [TD-002](ISSUES.md#td-002-ファイルキャッシュのライフサイクルと競合)
- 現行: 共通ルート下の段階別JSON、属性と生レスポンスのTTL、内容ベースキー、アトミック置換
- 目標: 利用規模に合った保存方式で、競合、保持期限、容量、削除、利用者分離を管理する

想定する成果物:

1. 実測したデータ量、同時実行数、保持要件
2. ファイル継続、DB、オブジェクトストレージの比較と決定
3. 共通エンベロープまたはDBスキーマと移行方針
4. 容量上限、期限、自動削除、破損隔離
5. 競合、障害復旧、削除のテストと運用手順

完了条件:

- 全namespaceの保持・削除ルールが実装されている
- 複数ワーカーを対象にする場合、同じキーの競合結果が定義されている
- 認証利用者単位の分離が要件なら、保存と読込の双方で強制される
- 旧JSONを保持、移行、削除する条件が記録されている

### TASK-003: 多利用者向けセキュリティ境界の構築

- 状態: 候補
- 根拠: [TD-003](ISSUES.md#td-003-アクセス制御と利用量制御) と [SECURITY.md](SECURITY.md)
- 現行: アプリ独自の認証、認可、レート制限、利用者別永続領域がない
- 目標: 公開範囲と利用者モデルを定義し、外部API費用と保存データを主体ごとに制御する

想定する成果物:

1. 利用者、管理者、サービスの権限モデル
2. 認証とセッション管理
3. ジョブ、キャッシュ、ログの所有者分離
4. レート制限、日次等の利用上限、課金アラート
5. データ保持・削除要求、シークレットローテーション、監査手順
6. 認可抜けと越境アクセスのセキュリティテスト

完了条件:

- 未認証利用と別利用者データ参照が拒否される
- Outscraper利用量に強制上限と観測手段がある
- シークレット、ログ、キャッシュの保持と削除が運用可能である
- 脅威モデルと残余リスクをレビューしている

外部公開しない判断をする場合も、その運用境界とアクセス制御を文書化する。

### TASK-004: 観測可能性と配布パイプラインの整備

- 状態: 候補
- 根拠: [TD-004](ISSUES.md#td-004-観測可能性とログ管理) と [TD-006](ISSUES.md#td-006-ciと配布方式)
- 現行: `print()` 中心の進捗で構造化メトリクスと配布方式はない。現行作業ツリーにはPython 3.10 / 3.13の決定論的CIがあるが、GitHub上の実行結果と必須チェック設定は未確認である
- 目標: 対応Python環境で変更を自動検証し、障害を検索単位で追跡できる配布・運用基盤を作る

想定する成果物:

1. ログ項目、禁止項目、相関ID、保持期間
2. 外部API時間、再試行、キャッシュヒット、失敗分類のメトリクス
3. アラートとトラブルシューティング手順
4. Pythonバージョンごとのlint・testを行うCI
5. 配布形態、シークレット注入、読み取り専用コード領域、書込可能キャッシュ領域
6. リリースとロールバック手順

完了条件:

- 1件の検索を段階横断で追跡できる
- シークレットと保護対象データがログへ出ないことを検証できる
- 対応Python版でlint・testが自動実行される
- 新しい環境への配布と以前の版への復旧を再現できる

### TASK-005: ランキング品質評価の確立

- 状態: 進行中（case1からcase3のcharacterization、typed-ranking-v4、holdout評価契約と固定policyは完了した。2026-09-07に画像の未知データ評価を再開し、[EXEC-064](#exec-064-実ブラウザ候補とgpt-image独立参照のclip診断) の適格category-only 2条件は1 pass・1 failだった。[EXEC-065](#exec-065-未知の視覚条件に対する条件別counterfactual画像評価) はminimum-positive v4へlabel-free batch較正を追加し、development相対合格後の未知条件1-case probeはAUC 1.0、accuracy 0.875で不合格だった。最終独立評価と画像ranking有効化は未完了である）
- 根拠: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)
- 現行: 固定CLIP入力は縦横比を維持して画像全体を224×224内へ収め、モデル平均値の余白を使う。case1 AUCは0.759259259、接続方式を除く視覚評価AUCは0.928571429、case2の自己参照除外cluster診断はAUC 0.642857143、case3はAUC 0.468750000である。typed-ranking-v4とholdout評価契約はoffline接続済みで、legacy現行検索、API、UIへは未接続である。画像componentはdisabledである
- 最新: EXEC-065で、minimum-positive v4の4〜32候補を条件別の観測中点・半幅へlabel-free較正し、十分な分布根拠がある条件だけ共通閾値0を使う境界を実装した。developmentではaccuracyとpairwise AUCが1.0になったが、未使用のデスクライト・クランプ条件1 caseではmatch 3/3、mismatch 4/5、accuracy 0.875、AUC 1.0となり、事前固定したaccuracy 0.90へ未達だった。このcaseを調整へ流用せず、最低2 category・各2 caseの残りを別条件で確認する。画像rankingまたは本番合格ではない
- 目標: 重み、正規化、検索語変更による品質差を、再現可能なデータと指標で判断する

想定する成果物:

1. 個人情報とシークレットを含まない代表クエリ
2. 固定した商品候補または安全なfixture
3. 関連度の期待値と評価指標
4. 係数変更前後の比較レポート
5. 為替レートの鮮度・再現性要件とテスト方法
6. 型付き条件、trusted registry、証拠裁定、必須状態を持つ決定的ranking境界
7. 開発に使ったcaseと未使用holdoutを分けた評価report

完了条件:

- 同じfixtureで決定的に評価を再実行できる
- 重み変更の改善・悪化を指標で説明できる
- exact条件の判定品質と外観scoreの品質を別の指標で説明できる
- 必須条件の明示的不一致が外観・価格・レビューで隠れず、unknownを不一致または一致と誤表示しない
- 実APIの変動とアルゴリズム変更を分けて評価できる
- 評価データの出所と利用条件が [REFERENCES.md](REFERENCES.md) に記録されている

### TASK-006: AI相互レビューとTDDハーネスの導入

- 状態: 完了
- 実行計画: [EXEC-001](WORKLOG.md#統合済み履歴plan-exec-001)
- 根拠: [TD-009](ISSUES.md#td-009-ai変更の役割分離と証拠契約)
- 成果: strict task/policy/gate/review/TDD/verdict契約、canonical single-commit policy、Git object再hash、standalone clone検査、deterministic judge、network guard、CI gate、TDDパイロットを導入した
- 境界: EXEC-001はbootstrap時点の履歴であり、その後のattested runtime、snapshot、runner、broker、署名はTASK-007で実装した

TASK-006自体では外部AI、Bonsai、Outscraper、Amazonの実通信、課金、commit、push、mergeを行っていない。ブックマーク表示数プルダウン、検索結果スライダーの用途変更、削除済みPDFの復元も対象外である。

### TASK-007: attested AI review境界の実装

- 状態: 実行中（7/7 actual handler、frozen sign/judge、workflow初期化、credential-free deployment check、独立security review、rootless Podman実配備、承認済みv2 canaryの `nonlive_ready`、UID 1100が読めるlive用initial requestは確認済み。live E2Eとnonce長期運用が残る）
- 実行計画: [EXEC-002](#exec-002-attested-ai-review境界の実装)
- 根拠: [TD-009](ISSUES.md#td-009-ai変更の役割分離と証拠契約)
- 現行: import前stdlib preflight、root-owned runtime契約、read-only snapshot/RED overlay、networkなしraw offline runner、bounded packet、固定egressのprovisioned broker、frozen final ledger、失敗attemptを含むtoken/cost契約、Ed25519、exact SQLite nonce ledger、frozen attested judge、7-phase digest protocol、stdlib固定state machine、outer `--workflow` entry、7/7 actual handler、external approved manifest SHAとhuman-approved patch SHAに結ぶ `workflow-init` を実装した。rootless Podman hostへtrusted releaseと4 imageを配備し、credential/APIなしの `nonlive_ready` まで確認した
- 目標: credential-free配備確認とlauncher user向けinitial requestを維持した上で、別途承認したlive 7-phase E2Eとnonce ledger長期運用を閉じる

対象外:

- 自動commit、push、merge
- 検索アプリのUI、ブックマーク表示数、検索結果件数の変更
- 削除済みPDFの復元または参照
- Bonsai、Outscraper、Amazonへの実通信
- 未コミットbootstrap変更自身を自己attest済みと扱うこと
- 人間のcredential、送信内容、費用opt-inなしにOpenAI APIを起動すること

完了条件:

- [x] preflightがmanifestのPython inode/digest、harness、task、lock、schema、policy、public keyをimport前に固定する
- [x] candidateを別UIDから変更不能なsnapshotとし、raw RED/GREEN/gateをnetworkなしrunnerで採取する
- [x] root `.env.example` は空値検査後にsnapshotから除外し、共通credential pathとsecret-like contentを拒否する
- [x] reviewer/adversaryをcandidateなし、toolなし、同じbounded packet、別fresh lifecycleで実行する契約を持つ
- [x] broker/gatewayのnetwork分離、fixed egress、credential不在、raw inspect、cleanup/absenceを証拠化する
- [x] `service_tier=default` の価格policy digest、544K/4.54 USD標準cap、1,088K/7.94 USD絶対cap、失敗attempt予約を固定する
- [x] raw offline、2つのprovisioned broker lifecycle、frozen final ledger、Ed25519署名をattested judgeが再構築する
- [x] `pass` を許しても `human_approval_required=true` を維持する
- [x] 7つのphase、digest chain、consume-before-execute SQLite ledger、phase別mount制約を実装する
- [x] external phaseのprepared payload/raw evidenceをexclusive保存し、brokerをhost SQLite削除後もfrozen ledgerから再構築できるようにする
- [x] request/action/output/result/next requestをstdlib固定7-phase state machineで再検証する
- [x] external launcherの `--workflow` をroot-owned outer 7-phase driverへ接続する
- [x] inner `prepare|finalize` CLIとoffline/broker actual typed handlerを接続し、caller supplied descriptor/argv/unknown fieldを拒否する
- [x] physical snapshotを一般artifactから分離した専用read-only mountへ渡し、semantic/physical SHA集合をexact照合する
- [x] snapshot、red-snapshot、review-packetのactual workflow handlerを接続する
- [x] broker committed evidenceからlive DBなしでsign/judge共通frozen input bundleを再構築する
- [x] readiness gateが7/7 handlerの完全一致をcredential readとbroker ledger作成前に検査する
- [x] `sign` actual workflow handlerをfrozen common bundleへ接続する
- [x] attested judgeをfrozen common bundleだけからverdictへ接続し、host ledger削除後のpassと改ざん拒否を検証する
- [x] exact nonce SQLite schema、file identity、sidecar拒否、atomic replay rollbackを回帰テストする
- [x] external approved manifest SHA、TaskSpec v2、protected candidate、人手承認済みpatch SHAからsequence 1 requestを作るcredential-free `workflow-init` を実装する
- [x] 4 digest-pinned imageをcredential/API/external networkなしで検査し、`production_e2e_complete=false` の `nonlive_ready` evidenceを出すdeployment checkを実装する
- [x] 管理者承認の上で専用非rootuser、subuid/subgid、rootless Podman、trusted `/opt`、private `/var/lib` を用意する
- [x] 人手監査済みclean commit、具体的TaskSpec v2 canary、外部承認済みmanifest SHA、4 image digestからroot-owned releaseを配備し、`--deployment-check` の `nonlive_ready` を実hostで確認する
- [x] external manifest/patch anchorを再承認し、`ai-review` 所有のprivate artifact rootへlive launcherが読めるinitial requestを新規生成する
- [ ] rootless Podman `keep-id` hostでtrusted releaseのfull 7-phase承認済みlive検証を行う
- [x] offline全体pytest、Ruff、lock、diff、schema、Markdown、独立security reviewを最終確認する

外部OpenAI APIのlive成功は、credentialと費用の人間承認がない限り完了条件にしない。その場合は未実行境界を明記し、コード/fixture検証と配備実績を区別する。

2026-08-16の実配備では `ai-review` UID 1100、`amazon-candidate` UID 1101、ai-review専用subuid/subgid、rootless Podman 6.1、user namespace、seccompを確認した。clean base `dd4b6bde2bd2d7f3ebc67c5190949c1cc97652ee`、canary head `c603ec833e13f13bdce5af4e0b36f5917e0d4f98`、manifest SHA-256 `703d2e183558afe6e52198247888675d7f0b526f5082051a9ae75d5ea3a402ae` を `/opt/amazon-explorer-ai-review/releases/dd4b6bde2bd2d7f3ebc67c5190949c1cc97652ee` とprivate `/var/lib/amazon-explorer-ai-review` へ分離し、4 imageのlocal inspect/networkなしsmokeが `nonlive_ready` で成功した。package導入、public base image pull、image内package取得、4 image buildは実施したが、OpenAI credential/API、external network、live workflow、課金は未実行である。

同じmanifest anchorとcanonical patch `a9d49bea2225a903fe693f913c1f8652cdea56d02b03355e17f472363ca3b715` を再照合し、local objectを共有しないUID 1100所有candidateから `/var/lib/amazon-explorer-ai-review/artifacts/TASK-CANARY-001-live-init-r2/phase-request.json` を生成した。directoryは0500、fileは0400、file SHA-256は `57266f318584f01dd0fc3cccf08a9e356db67371277e974393d7c8b91f42c706` であり、UID 1101からは読めない。これはcredential/APIを使わない初期化実績であり、live 7-phase成功ではない。

### TASK-008: 次期検索フロー v2 の実装

2026-09-12の稼働接続は [EXEC-141](#exec-141-新しい条件分類を稼働接続画面へ反映)、条件表現拡張は [EXEC-140](#exec-140-希望条件と否定条件の自然文指定を拡張) に記録する。希望/否定/指定なし/優先の共通解析と文章修正の接続範囲であり、画像なし経路と未知入力の本番品質合格は含まない。

- 現行テキスト採点: [EXEC-125](#exec-125-説明文の条件一致とタイトル比較の拡張) で説明文部分一致、同義語補助、日英カテゴリ・明示ブランド/型番を追加。

- 枠線の再改善: [EXEC-121](#exec-121-枠線の濃淡を画素で検証して改善) で100%表示の角の画素濃度を検証し、内側1px輪郭へ変更した。
- 枠の描画改善: [EXEC-120](#exec-120-細い外枠の描画改善) で角丸方式と行高を調整した。
- 表示調整: [EXEC-119](#exec-119-トグルの動き角丸履歴操作の調整) で滑らかな切替・角丸、履歴一覧の小型ボタン、危険外枠色を更新した。
- 表示修正: [EXEC-118](#exec-118-主要ボタンとトグル丸枠の表示修正) でボタン配色・トグル・円枠を更新。

- 現在の画面実装: [EXEC-117](#exec-117-react-stylexのオフライン画面)。2026-09-11の利用者指示により、文書のみの段階からReact + StyleXのオフライン実装へ進む。

- 状態: 進行中（暫定production profileは限定liveでCloudflare 2 calls、Outscraper 1 task、24商品画像、CLIP 7 batches、ranking v5まで成功した。最終承認からlocal job・schema 5.0履歴とlocal ASGI API factoryまでをoffline接続済み。本番quotaは設けない。server起動構成、最終承認controller、UIと新service込み実provider E2Eは未完了。gpt-imageはテスト専用で、次期フロントエンドのオフラインモックはEXEC-117で実装し、実API接続を後続に残す）
- 最新: [EXEC-080](#exec-080-4方向生成を製品フローから除去) で4方向生成を公開フローから外した。新providerとローカル3D生成を採用せず、E2E実検索の停止を維持する。
- 過去のlive: [EXEC-078](#exec-078-自然言語から画像確認ランキング履歴までのbackend-live-e2e) は旧6-callフローの23商品ranking・履歴再読込を確認した。4方向品質不合格の観測を残し、新フローの検証に読み替えない。
- 先行実装: EXEC-077の参考画像承認境界とEXEC-076のlocal job・履歴HTTP APIを維持し、EXEC-080で後続生成を偽画像だけに変更する。次期フロントエンドへの接続は自前開発の後続作業とする。
- 利用者フロー: [SEARCH-FLOW.md](../SEARCH-FLOW.md)
- 技術仕様: [BACKEND.mdの次期検索境界](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[型付き条件と証拠別ランキング](BACKEND.md#14-型付き条件と証拠別ランキング最小domainを一部実装)
- テスト方針: [DEVELOPMENT.md](DEVELOPMENT.md#統合済みテスト方針)
- 完了した第10マイルストーン: [EXEC-012](#exec-012-bonsai-v2-requestと実行境界)
- 完了した第11マイルストーン: [EXEC-013](#exec-013-bonsai-v2-http-transport)
- 完了した第12マイルストーン: [EXEC-014](#exec-014-outscraper-v2-httptaskpolling境界)
- 完了した第13マイルストーン: [EXEC-015](#exec-015-検索後半pipelineと完了state)
- 完了した第14マイルストーン: [EXEC-016](#exec-016-cloudflare-http応答と画像正規化)
- 完了した第15マイルストーン: [EXEC-017](#exec-017-offline検索orchestration)
- 完了した第16マイルストーン: [EXEC-018](#exec-018-cloudflare画像生成失敗後の回復state)
- 完了した第17マイルストーン: [EXEC-019](#exec-019-owner分離した30日検索履歴repository)
- 完了した第18マイルストーン: [EXEC-020](#exec-020-完了検索から表示用履歴への変換と保存)
- 完了した第19マイルストーン: [EXEC-021](#exec-021-pinned-ip画像https-transport)
- 完了した第20マイルストーン: [EXEC-022](#exec-022-server-side画像dns-resolver)
- 完了した第21マイルストーン: [EXEC-023](#exec-023-server-side画像proxy-service)
- 完了した第22マイルストーン: [EXEC-024](#exec-024-windowswsl向け画像dns-process-isolation)
- 完了した第23マイルストーン: [EXEC-025](#exec-025-固定onnx-clip-cpu-runtimeと品質smoke)
- 完了した第25マイルストーン: [EXEC-054](#exec-054-query-less-blockingの第1確認接続)
- 完了した第9マイルストーン: [EXEC-011](#exec-011-決定的ランキングv2とスコア内訳)
- 完了した第8マイルストーン: [EXEC-010](#exec-010-安全な画像取得phash固定clip境界)
- 完了した第7マイルストーン: [EXEC-009](#exec-009-決定的商品正規化と未知属性境界)
- 完了した第6マイルストーン: [EXEC-008](#exec-008-outscraper複数query-requestと明示承認guard)
- 完了した第5マイルストーン: [EXEC-007](#exec-007-cloudflare-4方向request-builder)
- 完了した第4マイルストーン: [EXEC-006](#exec-006-2段階承認と費用予約境界)
- 完了した第3マイルストーン: [EXEC-005](#exec-005-決定的検索tokenizer)
- 完了した第2マイルストーン: [EXEC-004](#exec-004-bonsai-v2-strict応答境界)
- 第1マイルストーン証拠: [EXEC-003](WORKLOG.md#統合済み履歴plan-exec-003)。同Planに残るOpenAI provider案は履歴であり、現行provider判断には [DEVELOPMENT.mdの商品検索 provider](DEVELOPMENT.md#商品検索-provider) と [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装) を使う
- 関連: [TASK-001](#task-001-検索処理のジョブ化)、[TASK-003](#task-003-多利用者向けセキュリティ境界の構築)、[TASK-005](#task-005-ランキング品質評価の確立)
- 現行: Bonsaiで属性を抽出し、1クエリのOutscraper検索、決定的正規化、テキスト・価格採点をStreamlit要求内で同期実行する
- 目標: Bonsai JSON textのfail-closed parseとstrict intent、決定的query plan、本番Cloudflareで先行1枚の明示確認後に4方向と条件別偽画像を生成するフロー、商品検索前の最終確認、複数query Outscraper、未知商品属性を推測で埋めない決定的正規化、説明可能なtext/price/image ranking、モーダル系UI境界、検索履歴を実装する。gpt-imageは画像評価テストだけに使う

確定した主要判断:

1. 画像生成トグルは既定OFF
2. ON時は本番Cloudflareで参考画像をまず1枚だけ生成し、利用者の明示確認で停止する。gpt-imageは画像評価テストだけに使う
3. 了承後に先行1枚を参照して別途4方向と条件別偽画像1〜3枚を生成する。先行1枚の作成は初回と作り直しを合わせて最大2回、後続生成は同じ承認につき1回だけとし、先行画像変更後は再確認する
4. pHash/Hamming距離は重複検出、固定CLIP embeddingは意味的画像scoreに使う
5. Outscraperはexact parameterを示す第2確認のsingle-use承認後だけ呼ぶ
6. component欠損時はweightを再正規化し、総合score降順にする
7. UI技術と検索domainを分離し、StreamlitからReact/Tailwindへ変更しても同じtyped APIを使う
8. 画像拡大、再生成確認、安全な中止、条件付き再試行を共通Lightbox、AlertDialogへ分離し、待機中の承認済み条件は読み取り専用の右側要約として常時表示する
9. 完了した検索は0件を含めて履歴へ1件だけ30日間保存し、履歴の閲覧・再読込・個別削除・期限削除で外部処理を再実行しない
10. 初回実装の共通ヘッダーは `検索履歴` だけを追加し、設定ボタン、設定画面、設定用routeは保留する
11. 条件は型・演算子・重要度を持たせ、evaluatorとweightはtrusted registryで固定する。生成画像は外観参照だけに使い、必須条件の明示的不一致を総合scoreで打ち消さない

想定する成果物:

1. Bonsai response envelope、content全体のfail-closed JSON parser、strict Pydantic domain model（第1マイルストーンでdomain model、第2マイルストーンでnetwork非依存応答境界、第10マイルストーンで固定system prompt・canonical request・注入transportによる実行と利用量記録、第11マイルストーンでRequests HTTP transport、第15マイルストーンで第1確認までのoffline接続を完了。実Bonsai・現行pipeline接続は未実装）
2. intent正規化、Sudachi/英数字tokenizer、最大2件のquery plan（第1マイルストーンでintent正規化とquery plan、第3マイルストーンでtokenizer統合を完了）
3. 2段階承認state machine、single-use digest、call/token/cost ledger（第4マイルストーンでoffline・同一process境界を完了。永続・API接続は未実装）
4. Cloudflare 4方向provider adapter、image set、全体再生成。request builder、mock HTTP、PNG正規化、4-call利用量・state・回復境界はoffline実装済みだが、Cloudflare実生成と製品接続は未確認
5. Outscraper複数queryと承認guard（第6マイルストーンでoffline descriptor、exact request digest、token claim前照合、credential-free permit、第12マイルストーンでmock Requests HTTP・task・polling・利用量確定、第13マイルストーンで正規化・ranking・完了stateへの後半pipeline、第15マイルストーンで最終確認・single-use承認から完了までのoffline接続を完了。実Outscraper・現行pipeline接続は未実装）
6. deterministic product normalization、未知属性の維持、post-Outscraper LLM非呼出しguard（第7マイルストーンでnetwork非依存境界、第13マイルストーンで成功済みHTTP完了結果とのoffline pipeline接続を完了。永続・API・UI接続は未実装）
7. image proxy、pHash dedupe、pinned CLIP runtime（第8マイルストーンでoffline proxy core、64-bit pHash、固定asset verifier、注入encoder・fixture score境界、第19マイルストーンでpinned-IP HTTPS transport、第20マイルストーンで有界DNS resolver、第21マイルストーンで合成allowlistのserver-side service、第22マイルストーンでWindows/WSL互換のDNS process isolation、第23マイルストーンでrepository-local固定ONNX asset、CPU encoder、CLIP process isolation、合成画像の実model smoke、受領1組の3回識別smokeを完了。TASK-005のEXEC-026で単一条件31枚の自己参照なしcharacterizationを完了したが事前AUC基準は未達。運用allowlist・実host通信、Windows native確認、複数queryのranking本評価、ranking有効化は未実装）
8. ranking profile v2、stable sort、score breakdown（第9マイルストーンで画像無効のoffline境界、第13マイルストーンでOutscraper完了結果からの後半pipeline、第15マイルストーンでBonsaiから完了までのoffline orchestrationを完了。[EXEC-034](#exec-034-型付き条件と証拠別ランキングの設計) から [EXEC-038](#exec-038-型付き条件ranking-v4境界) で次期typed requirement・証拠裁定・両側adapter・typed-ranking-v4を実装し、第24マイルストーンで第1確認・承認・state・後半pipeline・typed表示履歴へ接続した。実provider、legacy現行pipeline、API・UIは未接続）
9. 利用者操作ごとに停止するoffline backend orchestration（第15マイルストーンで画像OFF・ON・再生成・破棄、最終承認前0 call、single-use、成功・0件・固定失敗、第16マイルストーンでCloudflare生成途中失敗後の固定回復stage、明示retry、画像なし続行を完了）
10. 自前開発によるAPI-first UI contract、モーダル系共通component、実画面の実装・操作確認とローカルバックエンド接続
11. owner分離した検索履歴の保存、一覧、詳細、個別削除、30日の期限物理削除（第17マイルストーンでoffline SQLite repository、第18マイルストーンで完了resultからの表示用変換・冪等保存結合を完了。認証、現行pipeline、API・UIは未接続）
12. offline/security/ranking評価と承認済みの最小live試験

完了条件:

- [ ] Bonsaiの通信・envelope・JSON・strict schema不一致をfail closedにし、Markdown fenceやJSON断片抽出で救済しない
- [ ] 意図、推定価格、クエリを第1確認で編集できる
- [ ] Cloudflareで4方向setを生成・一括再生成できる（offline境界は実装済み。実生成と製品接続は未確認。gpt-imageの評価用4 callsは別に完了）
- [ ] 第2確認なしのOutscraper呼出しを全経路で拒否する
- [ ] Outscraper後にLLMを呼ばず、観測できない商品属性は未知のまま、決定的な値だけで続行する
- [x] 検証済みOutscraper完了結果を観測値だけの商品正規化・画像無効rankingへ渡し、結果あり・正常0件・工程別固定失敗をoffline stateで区別できる
- [x] Bonsaiから各確認、任意画像、single-use承認、Outscraper、正規化、ranking、完了までを段階別offline orchestrationで結び、確認前のprovider callを拒否できる
- [x] Cloudflare生成途中失敗をfailed予約と専用stateへ結び、自動retry・部分画像採用・予約再利用なしで、上限内の4枚一括retryまたは画像なし続行を明示選択できる
- [x] 検証済みglobal IPへ直接1回だけ接続し、元host名でTLS証明書を検証する画像HTTPS transportを、socket・TLS・HTTPResponse fixtureで再現できる
- [x] canonical hostをTCP用IPv4・IPv6へ1回だけ有界に名前解決し、構造不正を固定error、globalでない全結果を既存coreでtransport前に拒否できる
- [x] 起動時のallowlist、DNS resolver、pinned-IP HTTPS transport、proxy coreを固定serviceへ束ね、requestごとのpolicy上書きなしに合成fixtureで取得できる
- [x] 固定ONNX 3 file、224px前処理、CPU-only encoder、30秒 `spawn` process境界を実装し、`--offline --no-sync` かつ外部clientを持たないlocal-only経路の合成画像でrepository-local modelを推論できる
- [ ] pHashとCLIPの役割を分離し、固定fixtureで画像rankingの採否を決める
- [x] 型付き条件、trusted registry、証拠source allowlistと `match`・`mismatch`・`unknown`・`conflict` をoffline境界で再現する（現行pipeline・UI非接続）
- [x] 必須状態を総合scoreより先に比較し、unknown条件の候補別除外と候補集合依存の画像正規化を行わないtyped-ranking-v4を、第1確認からtyped表示履歴までのoffline経路で再現する（legacy現行pipeline・API・UIへの接続は未実装）
- [x] 欠損weight再正規化、negative penalty、stable descending sortを再現できる（offline ranking境界。現行pipeline・UIへの接続と品質評価は未完了）
- [x] 現行local productionはper-user・session・day・cost quotaを無効化し、開始済みattemptと費用だけを記録する。操作単位のcall数、候補・poll・byte・timeout上限、自動retryなしは維持する
- [ ] LightboxとAlertDialogの用途を分け、待機画面右側へ承認済み条件の読み取り専用要約を常時表示し、検索語編集と商品詳細をページ内に維持する
- [x] strictな表示用snapshotをowner内で冪等保存し、結果あり・正常0件、再起動読込、異なるpayloadの衝突、保存・削除失敗のrollbackをoffline SQLite repositoryで区別する
- [x] 履歴repositoryの一覧・詳細・画像取得・個別削除が外部処理を呼ばず、owner不一致と内部metadata表示を拒否する
- [x] 履歴と専有生成画像を完了日時から30日で期限物理削除し、期限後の一覧・詳細・画像取得から返さない
- [x] 完了result、承認済みreview、元入力を再検証して表示用履歴へ変換し、結果あり・正常0件を外部処理の再実行なしでSQLiteへ冪等保存する
- [ ] 履歴の空・読込失敗・削除失敗を含む認証済みAPI・UI状態を提供する
- [ ] 通常CIをnetworkなしで完了し、live試験の送信内容・承認・費用・結果を別記録にする
- [ ] [SEARCH-FLOW.md](../SEARCH-FLOW.md)、[統合済みテスト方針](DEVELOPMENT.md#統合済みテスト方針)、要件、設計、UI、security、cache schemaを実装と一致させる

live試験の送信内容、費用提示、個別承認、実施順序は [DEVELOPMENT.mdのlive結合試験](DEVELOPMENT.md#6-live結合試験) を正とする。次マイルストーンの着手時は [Execution Plan規約](DEVELOPMENT.md#統合済みexecution-plan規約) に従って、この文書へ新しいPlan節を作成する。

### 3. 更新規則

- 候補から計画中へ移すとき、目的、対象外、依存関係、受入条件を確認する
- 実行中にする前に個別Planへリンクする
- 完了は成果物と検証結果がそろった場合だけにする
- 一部だけを実施した場合は、達成済みと残りを分け、タスク全体を完了にしない
- 要求されなくなった項目は削除せず、判断理由と再検討条件を記録して終了状態にする


## 統合済み小規模タスク一覧

> 統合元: `docs/TODO.md`。統合前の文書は `docs/old/` に保存する。


> **標準文書との関係:** 問題と作業台帳の入口は [ISSUES.md](ISSUES.md)、現在の到達点は [GOAL.md](#開発目標) とする。この文書は単独で完了できる小規模作業のIDと状態を保持する。

### 1. 役割

この文書は、対象と完了条件が明確で、原則として1回の小さな変更で完結する作業を管理する。2026-08-16時点の現行コードとテストから確認できた項目だけを掲載する。AIハーネスの専用user/subuid/subgid/rootless Podman設定、clean release、具体的TaskSpec v2 canary、`nonlive_ready` 実host確認、launcher user向けinitial request生成は完了した。残るlive E2Eとnonce ledger長期運用は単発作業ではないため、[TASK-007](#task-007-attested-ai-review境界の実装) と [TD-009](ISSUES.md#td-009-ai変更の役割分離と証拠契約) で追跡する。credential-free配備確認をOpenAI APIのlive成功として扱わない。

- 再現可能な不具合は [ISSUES.md](ISSUES.md) に原因と影響を記録し、ここから対応作業をリンクする
- 複数段階または複数の設計判断を要する作業は [TASKS.md](#統合済み大規模タスク一覧) へ移す
- 構造上の継続課題は [TECH-DEBT-TRACKER.md](ISSUES.md) で追跡する
- 長時間の実行計画は [PLANS.md](DEVELOPMENT.md#統合済みexecution-plan規約) に従う

チェックを付けるのは、変更、対応する確認、文書同期が完了した場合だけである。

### 2. 未完了

- なし

### 3. 完了

#### TODO-005: 未参照設定の扱いを明記する

- 状態: 完了
- 完了日: 2026-09-04
- 関連負債: [TD-004](ISSUES.md#td-004-観測可能性とログ管理)
- 判断: 実行処理に接続されず、設定可能との誤解を招く `APP_ENV` と `LOG_LEVEL` を `Settings` と `.env.example` から削除した
- 互換性: `Settings` は未知項目を無視するため、旧 `.env` またはprocess環境に同名値が残っていても既知設定のロードを妨げない。同名値による環境切替・ログ制御は提供しない
- テスト: `tests/test_outscraper_client.py` で旧2変数を設定した状態でも既知のUI設定をロードし、削除済みfieldを公開しないことを確認する
- 再導入条件: [TD-004](ISSUES.md#td-004-観測可能性とログ管理) で用途、型、許容値、秘密情報を含まない出力契約を決め、実際のlogging・観測処理へ同時に接続する

#### TODO-001: Markdownリンク検査を定型化する

- 状態: 完了
- 完了日: 2026-09-04
- 変更: `tools/check_markdown_links.py` に、ルート直下と `docs/` 直下の現行Markdownを列挙し、local path、ATX見出しanchor、fenced code blockをnetworkなしで検査するCLIを追加した。`docs/old/` は検査元から除外し、現行文書から参照されたarchive pathは存在確認する
- テスト: `tests/test_markdown_links.py` で現行repository、正常な相対pathと重複見出しanchor、fenced code・外部URL・archive sourceの除外、欠落path、欠落anchorを確認する。現行repositoryの検査は通常offline pytestとCIに含まれる
- 実行: `uv run --frozen --offline --no-sync python tools/check_markdown_links.py`
- 境界: 外部URLの到達性、setext見出し、`docs/old/` 自体の内部参照は検査しない

#### TODO-002: デバッグ表示へ全条件語重みを表示する

- 状態: 完了
- 完了日: 2026-08-15
- 関連Issue: [ISS-001](ISSUES.md#iss-001-デバッグ表示に2つの条件語重みがない)
- 変更: `src/ui/streamlit_ui.py` の `SHOW_DEBUG_INFO=true` 時のJSONへ `color_term_weight` と `feature_term_weight` を追加した
- 証拠: `tests/test_streamlit_ui.py` は修正前1 failed, 2 passed、修正後3 passed。テストSHA-256は `042ad1b2cd8307afe40787bd53510d4cb55f66914548adf9ed76b57b8306ac4c`
- 残事項: なし

#### TODO-003: UIの表示用純粋関数をテストする

- 状態: 完了
- 完了日: 2026-08-15
- 変更: `tests/test_streamlit_ui.py` で `format_price()` と `format_rating()` の価格不明、桁区切り、評価なし、レビュー件数あり・なしを確認した
- 検証: UIデバッグ表示のGREENと合わせて3 passed。外部APIは呼び出していない
- 残事項: ブラウザ操作による一連のUI確認はこの単体テストの範囲外である

#### TODO-004: APIキー欠落時の外部通信抑止を直接テストする

- 状態: 完了
- 完了日: 2026-08-15
- 変更: `tests/test_outscraper_client.py` にAPIキー空の直接回帰テストを追加した
- 検証: 対象テストは1 passed。`RuntimeError` となり、`fetch_amazon_products` が呼び出されないことを確認した
- 残事項: 実サービス結合試験は実施しておらず、完了条件にも含めない

### 4. 完了済み項目の扱い

完了時は項目を削除せず、次を追記して「完了」節へ移す。

- 完了日
- 変更を特定できるコミットまたはファイル
- 実行した検証
- 別タスクへ残した事項

完了済み項目のテストを変更した場合は、旧証拠を現行テストの結果として流用せず、新しい検証結果を追記する。


## EXEC-004: Bonsai v2 strict応答境界

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-02
- 最終更新日: 2026-09-02
- 関連仕様: [次期検索バックエンド v2](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)
- 前提Plan: [EXEC-003](WORKLOG.md#統合済み履歴plan-exec-003)
- 関連要件: [REQUIREMENTS.md](REQUIREMENTS.md)
- 関連設計: [BACKEND.md](BACKEND.md)、[SECURITY.md](SECURITY.md)

### 目的

BonsaiのOpenAI互換response bodyを、救済的な文字列加工を行わず `choices[0].message.content` の単一JSON objectとして検証し、既存のstrict `SearchIntentDraft`、決定的正規化、provenanceへ接続する。利用者から見える結果は、不正なenvelope、Markdown fence、前後の説明文、unknown・missing field、型coercionを検索意図として採用せず、生responseを含まない固定エラーで停止できることである。

### 対象範囲

- 対象:
  - `src/search_v2/` のnetwork非依存Bonsai response adapter
  - strict intent JSON schemaの決定的byte表現
  - full raw response body、prompt、schema、source inputを結ぶprovenance
  - 正常系、envelope不正、JSON不正、schema不一致、上限、秘密情報非露出のoffline fixture test
  - 実装状態に関係する標準文書と作業記録
- 対象外:
  - `requests` によるBonsai通信、現行 `src/clients/bonsai_client.py` または現行pipelineへの接続
  - v2 system prompt、tokenizer、承認state machine、Outscraper、Cloudflare、ranking、UI、保存
  - credential、外部送信、課金、Bonsai実モデルの意味品質評価

### 現在の状態

- `src/search_v2/intent.py` はunknown fieldと型coercionを拒否するdraft、正規化済みintent、source・prompt・schema・response digestを実装済みである。
- `src/search_v2/query_planner.py` は正規化済みintentから最大2件の日英query planを作るが、現行pipelineへ未接続である。
- 現行 `src/clients/bonsai_client.py` はenvelopeから非空contentを返すだけで、後段のlegacy parserはMarkdown fence除去やJSON断片抽出を行う。この経路は互換維持のため変更しない。
- `src/search_v2/bonsai_adapter.py` とfixture testを本Planで追加した。adapterはnetwork非依存で、Bonsai実通信と現行pipeline接続は行わない。

### 実行手順

1. `tests/test_search_v2_bonsai_adapter.py` に期待契約を追加し、production module不在によるREDを記録する。
2. full raw response bytesをUTF-8かつ上限内で検査し、OpenAI互換envelopeから非空contentだけを取り出すpure adapterを実装する。
3. content全体をstrict JSONとして読み、duplicate key、非有限数、object以外、Markdown fence、前後の非JSON text、Pydantic schema不一致を固定エラーへ変換する。
4. `SearchIntentDraft` を正規化し、exact prompt、canonical schema、full raw response bodyのSHA-256を `NormalizedSearchIntent` へ結び付ける。
5. 関連文書を実装済み範囲へ同期し、focused test、Ruff、offline全体pytest、文書リンク、`git diff --check` を実行する。

### 進捗

- [x] 2026-09-02: 現行実装、TASK-008、SEARCH-FLOW、Execution Plan規約、未実行の外部境界を再確認した。
- [x] 2026-09-02: RED testを追加した。`tests/test_search_v2_bonsai_adapter.py` のSHA-256は `fe607bb84982d14b958d2e08b4dc2f681c1d23ca279d987118c24361e66ff04e`、実装前はmodule不在によりcollection errorとなった。
- [x] 2026-09-02: full raw response、OpenAI互換envelope、content全体のstrict JSON、strict draft、normalizer、provenanceを接続するadapterを実装した。
- [x] 2026-09-02: SEARCH-FLOW、要件、backend、security、schema、開発規約、参照、負債、README、履歴を実装済み・未接続境界へ同期した。
- [x] 2026-09-02: focused test、関連回帰、lock、Ruff、offline全体pytest、現行Markdown、Python 3.10構文、`git diff --check` を完了した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_bonsai_adapter.py` | 実装前に期待した理由で失敗 | 終了2。`ModuleNotFoundError: No module named 'src.search_v2.bonsai_adapter'` |
| focused GREEN | 同上 | 全件成功 | 26 passed。整形後test SHA-256は `caf8f60d2583cd5449cd3edb30d1aa2b77296dc3dcdfc1f07baba13d819c4610` |
| 関連回帰 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_bonsai_adapter.py tests/test_search_v2_intent.py tests/test_search_v2_query_planner.py tests/test_backend_characterization.py tests/test_bonsai_client.py` | 全件成功 | 62 passed |
| lock | `uv lock --check --offline` | 終了0 | 終了0、72 packagesを解決 |
| lint | `uv run --frozen --offline --no-sync ruff check .` | 違反0件 | 終了0、違反0件 |
| format | `uv run --frozen --offline --no-sync ruff format --check .` | 差分0件 | 終了0、125 files already formatted |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | liveを実行せず全件成功 | 778 passed / 1 deselected |
| 文書・差分 | local Markdown link/anchor検査、Python 3.10 AST、`git diff --check` | 欠落・構文・whitespace error 0件 | 現行Markdown 15件で欠落0、AST成功、diff成功 |

### セキュリティ・データ・互換性

- raw responseはparser入力とdigest計算だけに使い、例外、UI、ログ、fixture以外のartifactへ本文を保存しない。
- schema mismatchを固定 `BonsaiResponseError` へ変換し、Pydanticの入力値を含む詳細を利用者向け例外へ連鎖表示しない。
- envelopeの追加metadataはOpenAI互換性のため許容するが、意図contractの追加fieldは拒否する。
- provenanceの `response_sha256` は `message.content` の再serialize値ではなく、adapterへ渡されたfull raw response body bytesを結ぶ。
- 現行legacy Bonsai parser、設定、cache schema、外部API call数は変更しないため、データ移行と外部状態のrollbackは発生しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-02 | v2 adapterはfull raw response bytesを受けるpure functionとする | exact response digestとUTF-8・envelope検証を、HTTP clientや再serialize結果から独立して再現するため | 後続のHTTP接続は `response.content` 相当を渡し、bodyを例外やログへ出さない |
| 2026-09-02 | envelopeの追加metadataは許容し、contentのintent contractだけを `extra=forbid` にする | OpenAI互換serverのrequest ID、usage、finish reason等を壊さず、検索意図だけを閉じた契約にするため | envelope metadataを保存する場合は別のstrict server-side modelを設計する |
| 2026-09-02 | legacy parserを変更せずv2 packageへ隔離する | 現行Streamlit・CLIの互換性を維持し、未接続基盤のlocal milestoneとして検証するため | v2 pipeline移行Planで明示的に切り替える |

### 発見事項

- 現行 `src/clients/bonsai_prompt.txt` はlegacy属性contract用であり、`SearchIntentDraft` の全fieldと一致しない。v2 system promptとrequest builderは本Planへ混在させず、後続のpipeline接続前に別マイルストーンで作成する。

### ロールバック

`src/search_v2/` の新規adapter、対応test、EXEC-004と実装状態の文書差分だけを取り除けば、現行pipelineと外部状態へ影響せずPlan開始前へ戻せる。`src/clients/bonsai_client.py`、legacy prompt、cache、credential、外部serviceは変更しない。

### 結果

full raw Bonsai response bodyをOpenAI互換envelope、非空content、content全体のstrict JSON、strict `SearchIntentDraft`、決定的normalizerへ接続するnetwork非依存adapterを実装した。duplicate key、非有限数、Markdown fence、前後の説明文、JSON断片、unknown・missing field、型coercionを固定エラーで拒否し、exact source、prompt、schema、responseをprovenanceへ結んだ。TDD RED、focused 26件、関連62件、offline全体778件、Ruff、lock、文書・差分検査は成功した。

EXEC-004完了時点では現行pipeline、v2 request builder、system prompt、HTTP client、決定的tokenizerは未接続・未実装だった。tokenizerは後続の [EXEC-005](#exec-005-決定的検索tokenizer) で実装する。Bonsaiその他の外部API、credential、課金、実モデルの意味品質は実行・確認していない。


## EXEC-005: 決定的検索tokenizer

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-02
- 最終更新日: 2026-09-02
- 関連仕様: [次期検索バックエンド v2](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[テキスト処理とランキング](BACKEND.md#8-テキスト処理とランキング)
- 前提Plan: [EXEC-003](WORKLOG.md#統合済み履歴plan-exec-003)、[EXEC-004](#exec-004-bonsai-v2-strict応答境界)
- 関連要件: [FR-402](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連設計: [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)

### 目的

Bonsaiが返した意味語句を検索queryのtoken列として信用せず、固定したローカル規則で再分割して、既存の最大2件query planへ接続する。利用者から見える結果は、助詞・記号・大文字小文字・全角英数字等の表記差に左右されにくく、同じintentと依存版から常に同じ安全な検索queryを作れることである。

### 対象範囲

- 対象:
  - `src/search_v2/tokenizer.py` のnetwork非依存tokenizer
  - 日本語のSudachiPy `SplitMode.C`、名詞・動詞・形容詞・形状詞filter
  - NFKC/casefold後の英数字 `[a-z0-9]+` 抽出
  - product name、category、required・preferred termsの再分割と、query plannerへの接続
  - brand/model identifierの正規化済み原形維持、negative termsのquery除外、重複排除、200文字上限
  - tokenizerとplannerのoffline TDD、標準文書同期
- 対象外:
  - 現行 `src/services/text_processing.py` の変更、現行ranking・Streamlit・CLIへの接続
  - v2 request builder、system prompt、Bonsai HTTP、Outscraper、承認state、ranking v2
  - dependency更新、辞書取得、外部通信、credential、課金、意味品質評価

### 現在の状態

- `src/search_v2/query_planner.py` は正規化済みintentの意味語句を空白で連結するだけで、Sudachi/英数字へ再分割していない。
- `src/services/text_processing.py` には現行ranking用のSudachi/英数字処理があるが、legacy pipelineの互換境界であり、v2 packageからimportして責務を混在させない。
- lock済み実行環境はSudachiPy `0.6.11` と `sudachidict-core 20260428` を持つ。辞書変更時は固定fixtureの出力差分として検出する。
- query plannerはblocking ambiguity、最大2query、各200文字、URL・改行・制御文字、重複、plan digestを既に検証する。

### 実行手順

1. `tests/test_search_v2_tokenizer.py` とquery planner統合testを追加し、module不在または未token化出力によるREDを記録する。
2. NFKC、casefold、URL/control拒否、英数字抽出、Sudachi内容語抽出、順序維持・重複排除を行うpure tokenizerを実装する。
3. product name、category、required・preferred termsだけを言語別にtoken化し、brand/modelは識別子として原形を維持してquery plannerへ接続する。
4. URLを句読点除去で無害化したように見せず、token化前のraw意味語句でfail closedにする。negative termsは引き続きqueryへ含めない。
5. 標準文書と作業記録を同期し、focused test、Ruff、offline全体pytest、文書リンク、`git diff --check` を実行する。

### 進捗

- [x] 2026-09-02: SEARCH-FLOW、query planner、現行text processing、依存版、未接続境界を確認した。
- [x] 2026-09-02: RED testを追加した。tokenizer test SHA-256は `1f6c708f609bb900f08c4b0764c87e906c8addca20bc4611e80616b1bfb6c548`、planner test SHA-256は `37029e795362e1e2703ad8be7a60fb48220d449fcc50d0a65cf4112338d5954a`。module不在でcollection errorとなった。
- [x] 2026-09-02: Sudachi内容語・英数字tokenizerを実装し、識別子原形と意味語句group境界を維持してquery plannerへ接続した。
- [x] 2026-09-02: SEARCH-FLOW、要件、backend、security、schema、開発規約、参照、負債、README、履歴を実装済み・未接続境界へ同期した。
- [x] 2026-09-02: focused test、関連回帰、lock、Ruff、offline全体pytest、現行Markdown、Python 3.10構文、`git diff --check` を完了した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_tokenizer.py tests/test_search_v2_query_planner.py` | 実装前に期待した理由で失敗 | 終了2。`ModuleNotFoundError: No module named 'src.search_v2.tokenizer'` |
| focused GREEN | 同上 | 全件成功 | 23 passed。整形後SHA-256はtokenizer `8d4ed3a4642b0f0a3f49eeb98e5e1dc14534dd67f7f15ab1190558c6d60e1ddc`、planner `da031d71b1dc01a5400008f3d7499422f56198f4719600563a21c48efe935488` |
| 関連回帰 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_tokenizer.py tests/test_search_v2_query_planner.py tests/test_search_v2_intent.py tests/test_search_v2_bonsai_adapter.py tests/test_backend_characterization.py tests/test_bonsai_client.py` | 全件成功 | 75 passed |
| lock | `uv lock --check --offline` | 終了0 | 終了0、72 packagesを解決 |
| lint | `uv run --frozen --offline --no-sync ruff check .` | 違反0件 | 終了0、違反0件 |
| format | `uv run --frozen --offline --no-sync ruff format --check .` | 差分0件 | 終了0、127 files already formatted |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | liveを実行せず全件成功 | 791 passed / 1 deselected |
| 文書・差分 | local Markdown link/anchor、Python 3.10 AST、`git diff --check` | 欠落・構文・whitespace error 0件 | 現行Markdown 15件で欠落0、AST成功、diff成功 |

### セキュリティ・データ・互換性

- tokenizer入力はBonsai由来の非信頼文字列として扱い、NFKC後のURL、改行、control文字をtoken抽出前に拒否する。
- token化でURL記号を除去して通常語へ変換する救済は行わない。最終queryも既存 `SearchQuery` strict modelで再検証する。
- raw意味語句、利用者入力、token列を新しいcache、log、artifactへ保存しない。
- 現行ranking tokenizerとlegacy query選択は変更しないため、現行cache schema・外部call数・利用者フローに移行は発生しない。
- 辞書依存の出力はlock済みSudachiPy・sudachidict-core版と固定fixtureで検出し、dependency更新時に暗黙変更しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-02 | v2専用tokenizerを `src/search_v2/` に置く | legacy rankingの挙動と次期query contractを暗黙に結合せず、移行前後を別testで固定するため | ranking v2で共通化するときは同じfixtureとversion境界を維持する |
| 2026-09-02 | brand/modelは原形を維持し、他の意味語句だけをtoken化する | 商品識別子のハイフン・表記を壊さず、LLMの自然言語句だけを決定的に分割するため | provider fixtureで識別子分割が検索品質を改善すると確認した場合だけ見直す |
| 2026-09-02 | token順と最初の表記を維持してcasefold identityで重複排除する | query優先順位と再現性を保ち、同義な全角・大小文字重複を増やさないため | 多言語拡張時は言語別identity規則を別versionで定義する |

### 発見事項

- 現行 `split_words()` は英数字tokenを先にまとめてから日本語tokenを追加し、Sudachiのnormalized formによってLatin brandをカタカナ化する場合がある。v2 query tokenizerはmorphemeのsurface順を使い、日本語判定をsurfaceに対して行い、意図しない翻字tokenを追加しない。
- Sudachiは文中の `製` を接尾辞、連続した `あ` を感動詞として分類する。固定fixtureはこの内容語filterと長さ上限を別々に検証する。
- tokenを平坦化して200文字へ追加すると、1つの低優先意味語句の後半tokenだけが残り得た。query plannerは意味語句groupを原子的に採否する方式へ変更した。

### ロールバック

`src/search_v2/tokenizer.py`、対応test、query planner統合差分、EXEC-005と実装状態の文書差分だけを取り除けば、EXEC-004完了時点へ戻せる。現行pipeline、cache、credential、外部serviceにrollback操作はない。

### 結果

SudachiPy `SplitMode.C` の内容語とNFKC/casefold後の英数字をsurface順に抽出する決定的tokenizerを実装し、product name、category、required・preferred termsをquery plannerへ接続した。brand/modelの原形、negative term除外、意味語句group単位の200文字上限を維持し、URL・改行・control文字をtoken化前に拒否する。

TDD RED、focused 23件、関連75件、offline全体791件、Ruff、lock、文書・差分検査は成功した。現行pipeline、v2 request builder、system prompt、HTTP clientは未接続・未実装であり、外部API、credential、課金、実検索の意味品質は実行・確認していない。次の通常ローカル作業は、別Planを作成して2段階承認state machineと費用ledgerへ進む。


## EXEC-006: 2段階承認と費用予約境界

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-02
- 最終更新日: 2026-09-02
- 関連仕様: [利用者フロー](../SEARCH-FLOW.md#ui操作フロー)、[次期検索バックエンド v2](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[セキュリティ境界](SECURITY.md#13-bonsai正本の商品検索フローの安全境界基盤を一部実装)
- 前提Plan: [EXEC-003](WORKLOG.md#統合済み履歴plan-exec-003)、[EXEC-004](#exec-004-bonsai-v2-strict応答境界)、[EXEC-005](#exec-005-決定的検索tokenizer)
- 関連要件: [FR-403・FR-406](REQUIREMENTS.md#35-次期検索フロー-v2)、[DATA-011](REQUIREMENTS.md#5-データキャッシュ要件)、[SEC-011](REQUIREMENTS.md#6-セキュリティ要件)、[NFR-205・NFR-206](REQUIREMENTS.md#83-性能可用性)
- 関連設計: [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[SECURITY.md](SECURITY.md#13-bonsai正本の商品検索フローの安全境界基盤を一部実装)

### 目的

条件確認と商品検索確認を別の明示操作として扱い、画像生成またはOutscraperを、正しい状態、対象計画、利用者、session、期限、未使用token、利用上限が揃った場合だけ開始可能にする。利用者が条件を変更した場合は旧承認を失効させ、失敗attemptを含むcall・token・費用を送信前に予約する。

### 対象範囲

- 対象:
  - `src/search_v2/approval.py` のcanonical承認計画、domain-separated plan digest、15分期限、raw tokenを保存しないsingle-use承認
  - `src/search_v2/state_machine.py` のserializableな承認段階snapshot、revision、許可された遷移、第1確認、画像set確認、第2確認、計画変更時の失効
  - `src/search_v2/usage_ledger.py` のprovider別call・token・micro-USD上限、per-user-day・per-session・global-day予約、開始前解放、開始後の成功・失敗計上
  - 同一process内でのatomic予約、snapshotからの再開、並行予約の上限回避防止
  - strict model、改ざん・期限切れ・replay・stale revision・上限超過のoffline TDD
  - 標準文書と作業記録の同期
- 対象外:
  - Bonsai v2 request builder、system prompt、HTTP client、現行pipeline接続
  - Cloudflare request builder、画像生成、Outscraper複数query request、実外部送信
  - browser/API endpoint、認証・認可、UI実装
  - 複数process・複数host向け永続ledger、RDB、migration、運用pricing policyの確定
  - credential、実料金取得、課金、live API、実サービスE2E

### 現在の状態

- `NormalizedSearchIntent` と `SearchQueryPlan` に加え、承認対象全体をcanonicalに固定する `SearchApprovalPlan` が存在する。
- `src/search_v2/` に承認段階session state、許可遷移、raw tokenを保持しないapproval grant、usage reservationが存在する。現行Streamlitはこの次期境界を参照しない。
- 仕様は第1確認を画像生成前、第2確認をOutscraper前に要求し、承認tokenをowner・session・plan digest・15分期限へ結び付けてsingle-useにする。
- call・token・費用は外部要求前に予約し、開始前に安全に止めた予約だけ解放できる。1件でも開始した失敗attemptは利用量へ残す。
- provider単価は変動するため、本Planでは金額を整数micro-USDで受ける上限ledgerに限定し、単価計算と承認済みpricing bytesは後続release境界で固定する。

### 実行手順

1. 承認計画、state遷移、single-use token、費用予約の期待動作をテストへ追加し、module不在によるREDを記録する。
2. strictなusage policy、reservation、ledger snapshotを実装し、1つのledger instance内で予約と状態更新をlockする。未開始予約だけを解放可能にし、開始後の失敗を集計から除外しない。
3. normalized intent、query plan、Outscraper request digest、画像binding、usage allowance、runtime binding、作成・期限をcanonical planへ固定する。
4. 承認段階のsession snapshotとtransition関数を実装する。画像OFF経路と画像ON経路を分け、revision不一致、計画変更、期限切れ、token不一致、replayをfail closedにする。
5. focused・関連・全体回帰を実行し、要件、backend、security、schema、開発規約、README、履歴、次の再開位置を同期する。

### 進捗

- [x] 2026-09-02: SEARCH-FLOW、要件、security、schema、既存strict model、未接続境界を確認した。
- [x] 2026-09-02: 承認state・single-use token・usage ledgerのRED testを追加した。usage ledger test SHA-256は `fb935fae5fcd2966ecd38f1c90f59925d10e25213a250829174bea7a8c01a68e`、approval testは `0bf017297f164295716223cb4a6ed6166059a1b73a35a4742058954e472e6c7a`、state machine testは `d1b2f130a7984a22617e93387141bbfd3a5c96525f79f6ee26a6a4de352f40b6`。3つのmodule不在でcollection errorとなった。
- [x] 2026-09-02: network非依存domain実装を追加し、focused 26件をGREENにした。
- [x] 2026-09-02: 関連文書とTASK-008の状態・再開位置を同期した。
- [x] 2026-09-02: lock、Ruff、offline全体pytest、Markdown、Python 3.10構文、`git diff --check` を完了した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_usage_ledger.py tests/test_search_v2_approval.py tests/test_search_v2_state_machine.py` | 実装前に期待した理由で失敗 | 終了2。`src.search_v2.usage_ledger` と `approval` のmodule不在による3件のcollection error |
| 順序回帰RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_state_machine.py::test_outscraper_reservation_cannot_start_before_search_approval` | 承認前に開始した予約が通るため失敗 | 1 failed。test SHA-256 `1c09bffa9a46d6fd5166b4a160e3ed1f209a1e4addcd59f646d9fa1ca30db2a6` |
| focused GREEN | 最初のREDと同じ3 test file | 全件成功 | 26 passed |
| 関連回帰 | approval・ledger・stateと既存v2・characterization・legacy Bonsai test | 全件成功 | 101 passed |
| lock | `uv lock --check --offline` | 終了0 | 72 packages、終了0 |
| lint | `uv run --frozen --offline --no-sync ruff check .` | 違反0件 | 成功 |
| format | `uv run --frozen --offline --no-sync ruff format --check .` | 差分0件 | 133 files already formatted |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | liveを実行せず全件成功 | 817 passed、1 deselected |
| 文書・差分 | local Markdown link/anchor、Python 3.10 AST、`git diff --check` | 欠落・構文・whitespace error 0件 | 現行Markdown 15件・local link 573件・shell block 78件、Python 133件、template接頭辞、diff checkが成功 |

### セキュリティ・データ・互換性

- raw approval tokenは発行時に1回だけcallerへ返し、session snapshotにはdomain-separated SHA-256だけを保持する。token、owner、session、plan、期限を全て照合する。
- Outscraper予約の開始時刻が承認発行時刻より前なら拒否し、承認前に開始した外部attemptを後から正当化しない。
- browserからsession state、revision、承認済みflag、予約状態を任意指定させるAPIは本Planで作らない。将来のAPIはserver-side snapshotへcommandを適用する。
- 金額はfloatを使わず整数micro-USDとし、予約失敗では外部要求を開始しない。上限超過理由を通常画面へ金額付きで返さない。
- 同一processの予約はlockするが、複数process・hostのatomicityは保証しない。公開・複数worker接続前に永続repositoryとtransactionを別Planで実装する。
- 現行pipeline、cache、credential、外部API call数は変更しないため、既存データ移行と外部状態のrollbackは発生しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-02 | 費用を整数micro-USD、token・callと別dimensionで予約する | float丸めを避け、providerごとに不要なdimensionを0で表せるため | production pricing policy確定時も整数変換とdigestを維持する |
| 2026-09-02 | stateとledgerをserializable snapshotにし、同一processのmutationだけlockする | domain契約と再開可能性を先に固定し、未決定のRDBを暗黙採用しないため | 複数worker接続前にCASまたはtransactional repositoryへ置き換える |
| 2026-09-02 | Outscraper全parameterは後続request builderのcanonical digestへ結ぶ | 複数query request設計を本Planへ先取りせず、承認改ざんを防ぐbindingだけ先に固定するため | request builder実装時にexact bytesとdigestの一致を回帰テストする |

### 発見事項

- raw session snapshotだけに `consumed_at` を持たせると、同じ未消費snapshotの並行copyを二重消費できる。別の同一process内消費ledgerでtoken digestをatomic claimする境界を追加した。
- usage予約要求へcaller指定時刻を持たせると日次上限をbackdateできる。要求modelから時刻を除き、ledgerの `reserve(..., now=server_time)` だけが予約時刻を決める形にした。
- started Outscraper予約が承認発行前でもplan digestだけで通り得るREDを追加し、`started_at >= issued_at` を必須にした。

### ロールバック

`src/search_v2/` のapproval・state machine・usage ledger、対応test、EXEC-006と実装状態の文書差分だけを取り除けば、EXEC-005完了時点へ戻せる。現行pipeline、cache、credential、外部serviceにrollback操作はない。

### 結果

承認段階のstate machine、canonical plan、15分のsingle-use承認、同一process内のprovider別利用量予約をoffline実装した。計画変更、stale revision、policy・owner・session・digest不一致、上限超過、期限切れ、承認前開始、replay、並行二重消費をfail closedにする。

focused 26件、関連101件、offline全体817件、lock、Ruff、現行Markdown、Python 3.10 AST、template接頭辞、`git diff --check` は成功した。外部API、credential、課金、browser、永続・複数worker、後半state、現行pipeline接続は実行・実装していない。次の通常ローカル作業は、新しいExecution Planを作成してCloudflare 4方向request builderのoffline mock TDDへ進む。


## EXEC-007: Cloudflare 4方向request builder

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-02
- 最終更新日: 2026-09-02
- 関連仕様: [次期検索バックエンド v2](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[v2のofflineテスト](DEVELOPMENT.md#42-次期検索フロー-v2-のoffline境界)
- 前提Plan: [EXEC-006](#exec-006-2段階承認と費用予約境界)
- 関連要件: [FR-403・FR-404・FR-405](REQUIREMENTS.md#35-次期検索フロー-v2)、[SEC-010・SEC-011](REQUIREMENTS.md#6-セキュリティ要件)
- 関連設計: [BACKEND.md](BACKEND.md#14-承認済みの次期検索アーキテクチャ基盤を一部実装)、[SECURITY.md](SECURITY.md)
- 公式仕様: [FLUX.2 klein 4B model](https://developers.cloudflare.com/workers-ai/models/flux-2-klein-4b/)、[launch and multi-reference guide](https://developers.cloudflare.com/changelog/post/2026-01-15-flux-2-klein-4b-workers-ai/)

### 目的

正規化済み検索意図と承認前画像計画digestから、Cloudflare Workers AIのFLUX.2 klein 4Bへ送る4方向画像要求を決定的に構築する。利用者から見える将来の結果は、基準、左側面、右側面、背面斜めを固定順で作り、派生3方向が同じ基準画像だけを参照し、一括再生成ではattemptに応じて別seedへ切り替わることである。

### 対象範囲

- 対象:
  - `src/search_v2/cloudflare_request.py` のnetwork非依存request descriptor
  - exact model ID、512 × 512、prompt・width・height・seedだけのmultipart text field
  - 基準画像なしの `front_three_quarter` と、同じ `input_image_0` を持つ派生3方向
  - domain-separated seed、prompt contract digest、個別request・4件metadata digest
  - 参照PNGのbyte上限、chunk構造・CRC、縦横511px以下の検証
  - attempt 1・2、固定角度順、改ざん、秘密情報非保持のoffline fixture test
  - 標準文書と作業記録の同期
- 対象外:
  - multipart boundaryのserialize、Cloudflare endpoint、account ID、Authorization header、HTTP client
  - Cloudflare応答parse、Base64 decode、基準画像のPNG・sRGB正規化、画像保存
  - state machine・usage ledgerとの実行時接続、並列送信、retry、実画像品質判定
  - credential、実API、課金、画像本体生成、browser、現行pipeline接続

### 現在の状態

- 公式仕様ではmodel IDを `@cf/black-forest-labs/flux-2-klein-4b` とし、prompt-onlyでもmultipartを使う。`steps` は固定4で変更できず、派生入力は `input_image_0` から `input_image_3` のexact field名を使い、各入力画像は512 × 512未満でなければならない。
- [次期検索バックエンド v2](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装) は出力を512 × 512、参照前の基準画像を最大511px、同じ基準画像を使う派生3方向、1計画2attemptに固定している。
- `src/search_v2/` には承認state、Cloudflare call予約境界、credential-free request descriptorが存在するが、HTTP adapterと画像応答境界は存在しない。
- builderは将来のserializerがmultipart boundaryと認証を別に付与できるよう、credential-freeのtyped partsだけを返す。

### 実行手順

1. 4方向、multipart field、seed、参照PNG、strict contractの期待動作を `tests/test_search_v2_cloudflare_request.py` へ追加し、module不在によるREDを記録する。
2. 正規化済みintentの承認対象属性だけから固定promptを作り、brand、model number、source input、価格、credentialをpromptへ混入させない。
3. domain-separated SHA-256先頭32 bitからattempt・angle別seedを作り、固定model・寸法・prompt contractと合わせたrequest descriptorを実装する。
4. PNG chunk・CRC・寸法を検証した同じ基準画像を、派生3件のexact `input_image_0` partへ結ぶ。`steps` と `guidance` は要求へ持たせない。
5. focused・関連・全体回帰を実行し、要件、backend、security、references、履歴、次の再開位置を同期する。

### 進捗

- [x] 2026-09-02: 公式model page、launch guide、一般REST endpoint、SEARCH-FLOW、既存strict modelと未接続境界を確認した。
- [x] 2026-09-02: RED testを追加した。test SHA-256は `ee1fb8a819757aec6ec48bbf34cdd6ccbc3699c59842b0b33d82511ce4740d7e`、production module不在でcollection errorとなった。
- [x] 2026-09-02: network非依存request builderを実装し、focused 19件をGREENにした。
- [x] 2026-09-02: 標準文書とTASK-008の実装状態・再開位置を同期した。
- [x] 2026-09-02: lock、Ruff、offline全体pytest、Markdown、Python 3.10構文、`git diff --check` を完了した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_cloudflare_request.py` | 実装前に期待した理由で失敗 | 終了2。`ModuleNotFoundError: No module named 'src.search_v2.cloudflare_request'` |
| focused GREEN | 同上 | 全件成功 | 19 passed。整形後test SHA-256は `0785ece00d39fa2b520be850d601bece759af95764a91b0a5462cebd07814c17` |
| 関連回帰 | Cloudflare requestと既存v2・characterization・legacy Bonsai test | 全件成功 | 120 passed |
| lock | `uv lock --check --offline` | 終了0 | 72 packages、終了0 |
| lint | `uv run --frozen --offline --no-sync ruff check .` | 違反0件 | 成功 |
| format | `uv run --frozen --offline --no-sync ruff format --check .` | 差分0件 | 135 files already formatted |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | liveを実行せず全件成功 | 836 passed、1 deselected |
| 文書・差分 | local Markdown link/anchor、Python 3.10 AST、`git diff --check` | 欠落・構文・whitespace error 0件 | 現行Markdown 15件・local link 586件・shell block 78件、Python 135件、diff checkが成功 |

### セキュリティ・データ・互換性

- descriptorはaccount ID、API token、Authorization、endpointを受け取らず、将来のserver-side HTTP adapterへ認証責務を分離する。
- promptへfull source input、価格、brand、model number、negative term、provenance本文を入れず、正規化済みの商品種別・カテゴリ・色・必須条件・見た目の特徴だけを属性dataとして埋める。
- 参照画像byteはmultipart partの実行時bodyにだけ保持し、serializable metadataとdigestには長さ、寸法、SHA-256だけを含める。
- 現行pipeline、cache、credential、外部API call数を変更しないため、既存データ移行と外部状態のrollbackは発生しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-02 | HTTP requestではなくcredential-free multipart descriptorを先に実装する | field・順序・seed・画像bindingをofflineで固定し、認証、boundary、課金を暗黙に開始しないため | HTTP接続Planでserializerとexact outbound requestを別testする |
| 2026-09-02 | `steps` と `guidance` をmodelへ持たせずmultipart fieldから除外する | 公式仕様でstepsは固定4、SEARCH-FLOWでguidanceはprovider既定値と確定しているため | model変更または公式schema変更時だけ新contract versionで見直す |
| 2026-09-02 | 512pxの基準出力を派生入力前に最大511pxのPNGへ正規化する境界を別に保つ | 公式仕様が入力画像を512 × 512未満に制限し、request builderは画像変換責務を持たないため | 後続のimage normalization PlanでsRGB・metadata除去・decode上限を実装する |

### 発見事項

- model pageの描画済みparameter表は入力schemaを展開しないが、公式launch guideはrequired prompt、optional `input_image_0` から `_3`、guidance、width、height、seed、固定4 steps、入力画像512px未満を明記している。本Planはmodel固有のguideを一般Text-to-Image schemaより優先する。

### ロールバック

`src/search_v2/cloudflare_request.py`、対応test、EXEC-007と実装状態の文書差分だけを取り除けば、EXEC-006完了時点へ戻せる。現行pipeline、cache、credential、外部serviceにrollback操作はない。

### 結果

FLUX.2 klein 4Bの基準、左、右、背面を固定順で表すcredential-free multipart request descriptorを実装した。基準要求は参照なし、派生3要求は同じ最大511px PNGをexact `input_image_0` に持ち、text fieldをprompt・width・height・seedだけに限定する。attempt 1・2とangleをdomain-separated 32 bit seedへ結び、prompt contract、個別request、4件setのdigestを作る。PNGは8 MiB、chunk・CRC、寸法をfail closedに検証し、画像bodyをserializable metadataから除外する。

TDD RED、focused 19件、関連120件、offline全体836件、lock、Ruff、文書・差分検査は成功した。module SHA-256は `b3684f73828895727a17ed838c42b60136333cffa73af07d4cdb124e2368a6e4` である。Cloudflare HTTP・credential・応答・画像正規化・実生成、browser、現行pipelineは実行・実装していない。次の通常ローカル作業は、新しいExecution Planを作成してOutscraper複数query request境界と明示承認guardのoffline TDDへ進む。


## EXEC-008: Outscraper複数query requestと明示承認guard

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-02
- 最終更新日: 2026-09-02
- 関連仕様: [次期検索バックエンド v2](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[v2のofflineテスト](DEVELOPMENT.md#42-次期検索フロー-v2-のoffline境界)
- 前提Plan: [EXEC-007](#exec-007-cloudflare-4方向request-builder)
- 関連要件: [FR-406](REQUIREMENTS.md#35-次期検索フロー-v2)、[SEC-010・SEC-011](REQUIREMENTS.md#6-セキュリティ要件)
- 関連設計: [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[SECURITY.md](SECURITY.md)
- 公式仕様: [Amazon Products API](https://docs.outscraper.com/endpoints/amazon-products/)、[OpenAPI JSON](https://docs.outscraper.com/api-docs-data.json)

### 目的

`SearchQueryPlan` の日本語・英語最大2件を、1回のOutscraper Amazon Products非同期GET要求の反復 `query` parameterへ決定的に固定する。同時に、第2確認のexact request digest、single-use token、owner・session、1 callの開始済み利用量予約がすべて一致した場合だけ、後続HTTP adapterへ渡せる実行permitを生成する。

### 対象範囲

- 対象:
  - `src/search_v2/outscraper_request.py` のcredential-free request descriptorとdomain-separated SHA-256
  - 同一GET要求中の1または2件の反復 `query`、`amazon.co.jp`、`ja`、server-side postal code、1 query当たり24件、`async=true`
  - request endpoint、query plan、全送信parameter、最大候補数24または48件のexact binding
  - approval plan内request digest、query plan、single-use token、owner・session、開始済みOutscraper予約を結ぶ明示承認guard
  - request不一致時にtokenを消費しない失敗順序、改ざん、二重消費、credential非保持のoffline test
  - 標準文書と作業記録の同期
- 対象外:
  - API key読込み、`X-API-KEY`、HTTP serialize・送信、task作成、polling、retry、response parse
  - 現行 `src/clients/outscraper_client.py` の置換またはv2 pipelineへの接続
  - credential、live API、課金、Amazon候補取得、browser、UI確認画面
  - `scrape_submitted` 以降のstate、永続repository、複数processをまたぐtransaction
  - Outscraper応答の正規化、ASIN重複除去、ranking

### 現在の状態

- Outscraper公式OpenAPI 0.4.3は `GET /amazon-products` の `query` をarrayとし、`query=text1&query=text2` の1要求batchを明記する。`limit` は1 query当たりで既定24、`amazon.co.jp` と `ja` は許可値、`async` はrequiredでtrue推奨である。
- [次期検索バックエンド v2](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装) は日本語・英語最大2 query、1要求、各24件、最大48候補、exact parameterの第2確認を固定している。
- `src/search_v2/outscraper_request.py` はquery planからcredential-free request descriptorを構築し、実requestのquery batch・query plan digest・request digestをtoken消費前に承認planへ照合する。照合成功後だけ既存のowner・session・期限・single-use・開始済み1 call予約を検証し、execution permitを返す。
- 現行Outscraper clientは1 queryのHTTP・polling境界であり、本Planでは変更しない。

### 実行手順

1. 複数query、exact parameter、digest、approval guardの期待動作を `tests/test_search_v2_outscraper_request.py` へ追加し、production module不在のREDを記録する。
2. query planからcredential-freeのstrict request descriptorと固定順の反復query parameterを構築し、全承認対象をcanonical digestへ結ぶ。
3. requestとapproval planのquery・request digestをtoken消費前に比較し、既存state machineのsingle-use claimと予約検証の成功後だけ実行permitを返す。
4. mismatchではpermitを返さずtokenを消費しないこと、valid pathが1回だけ成功し、permitがraw token・credentialを持たないことを回帰テストする。
5. focused・関連・全体回帰を実行し、要件、backend、security、schema、references、履歴、次の再開位置を同期する。

### 進捗

- [x] 2026-09-02: 公式Amazon Products page、OpenAPI JSON、SEARCH-FLOW、現行1 query client、承認state・利用量予約境界を確認した。
- [x] 2026-09-02: RED testを追加した。test SHA-256は `0b97aa6d880b0e95bd398952e56629830d48453b6d61024a5e6fe420d65dc7cc`、production module不在でcollection errorとなった。
- [x] 2026-09-02: credential-free request descriptorと承認guardを実装し、query batch差替えを含むsupplemental REDを経てfocused GREENにした。
- [x] 2026-09-02: 標準文書とTASK-008の実装状態・再開位置を同期した。
- [x] 2026-09-02: lock、Ruff、offline全体pytest、Markdown、Python 3.10構文、`git diff --check` を完了した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_outscraper_request.py` | 実装前に期待した理由で失敗 | 終了2。`ModuleNotFoundError: No module named 'src.search_v2.outscraper_request'`。test SHA-256は `0b97aa6d880b0e95bd398952e56629830d48453b6d61024a5e6fe420d65dc7cc` |
| supplemental RED | 同上 | query plan digestとrequest digestだけを合わせても、承認外query batchを拒否するtestが失敗 | 1 failed / 19 passed。test SHA-256は `68cc8e5306f4fc8c328ca22b4c62c6ab20d4089e2526a276c8543e39f05eb79a` |
| focused GREEN | 同上 | 全件成功 | 20 passed。整形後test SHA-256は `d1ce25c108850db62dfc548c229a513036824fc4f9fdf515b29166803ed797b6` |
| 関連回帰 | Outscraper requestと既存v2・characterization・legacy Outscraper test | 全件成功 | 164 passed |
| lock | `uv lock --check --offline` | 終了0 | 成功、72 packages |
| lint | `uv run --frozen --offline --no-sync ruff check .` | 違反0件 | 成功 |
| format | `uv run --frozen --offline --no-sync ruff format --check .` | 差分0件 | 成功、137 files already formatted |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | liveを実行せず全件成功 | 856 passed、1 deselected |
| 文書・差分 | local Markdown link/anchor、Python 3.10 AST、`git diff --check` | 欠落・構文・whitespace error 0件 | 現行Markdown 15件・local link 635件・shell block 79件、Python 137件、template接頭辞、diff checkが成功 |

### セキュリティ・データ・互換性

- descriptorとpermitはAPI key、`X-API-KEY`、Authorization headerを入力またはfieldに持たない。queryとpostal codeは承認digestには含めるが、repr・log・利用者向け通常画面へ出さない。
- 許可parameterを `query`、`domain`、`language`、`postal_code`、`limit`、`async` だけに固定し、`apiKey`、`fields`、`ui`、`format`、`webhook` を受け取らない。
- guardはrequest mismatchをapproval ledger claimより先に拒否する。通過後のsingle-use性と予約上限は既存 `state_machine.py` と `usage_ledger.py` の同一process内lock境界を維持する。
- 現行client、cache、設定、外部状態を変更しないため、データ移行と外部状態のrollbackは発生しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-02 | 現行1 query HTTP clientを拡張せず、v2のcredential-free descriptorを分離する | legacy pipelineの挙動を変えず、承認対象と将来serializer入力をofflineで固定するため | HTTP接続Planでlegacy client置換とmigrationを別途判断する |
| 2026-09-02 | request mismatch検証後に既存 `consume_search_approval()` を呼ぶguardにする | 既存のowner・session・期限・single-use・予約検証を重複実装せず、request不一致でtokenを消費しないため | 永続repository化時はrequest照合とtoken claimを同一transactionにする |
| 2026-09-02 | endpointもrequest digestに含め、API keyは含めない | 公式page内で `.com` と `.cloud` の例が併記されるため、実行時設定のexact送信先を承認に結びつつcredentialをcanonical dataから分離する | endpoint変更時は承認planを再作成し、HTTP adapterでHTTPS・redirect・結果URL制約を再検証する |

### 発見事項

- 公式の描画pageはrequest endpointを `api.outscraper.com` と記載する一方、同pageのcURL例とOpenAPIの `servers` は `api.outscraper.cloud` を使う。現行設定の `.cloud` endpointを勝手に変更せず、descriptorのexact digestと後続HTTP安全検証で扱う。

### ロールバック

`src/search_v2/outscraper_request.py`、対応test、EXEC-008と実装状態の文書差分だけを取り除けば、EXEC-007完了時点へ戻せる。現行pipeline、cache、credential、外部serviceにrollback操作はない。

### 結果

1回のGETへ日本語・英語最大2件のqueryを固定順で反復し、endpoint、postal code、固定parameter、最大候補数をdomain-separated SHA-256へ結ぶstrict descriptorを実装した。guardは実query batch、query plan digest、request digestをtoken claim前に照合し、owner・session・期限・single-use承認と開始済みOutscraper 1 call予約がすべて一致した場合だけtoken・credentialを持たないpermitを返す。

初期REDとquery差替えを再現するsupplemental REDを経てfocused 20件、関連164件、offline全体856件、lock、Ruff、文書・差分検査が成功した。module SHA-256は `88ff8e1e8dd03753e4ed295782bc615f75589da5b1b0fb774a99df9ec387de61` である。API key、HTTP、polling、response parse、Amazon候補取得、課金、browser、現行pipelineは実行・実装していない。次の通常ローカル作業は新しい `EXEC-009` を作成し、決定的商品正規化、未知属性維持、post-Outscraper LLM非呼出しguardのoffline TDDから再開する。


## EXEC-009: 決定的商品正規化と未知属性境界

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-02
- 最終更新日: 2026-09-02
- 関連仕様: [次期検索バックエンド v2](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[v2のofflineテスト](DEVELOPMENT.md#42-次期検索フロー-v2-のoffline境界)
- 前提Plan: [EXEC-008](#exec-008-outscraper複数query-requestと明示承認guard)
- 関連要件: [FR-407](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連設計: [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[DB-SCHEMA.md](DB-SCHEMA.md)、[SECURITY.md](SECURITY.md)

### 目的

Outscraperの完了応答に含まれる商品候補を、検証済みrequest descriptorとquery provenanceへ結び付け、観測できた値だけをstrictなv2商品候補へ決定的に正規化する。利用者から見える将来の結果は、価格、ASIN、URL、rating等を推測値で置換せず、色、材質、機能等を確認できない場合は未知として後続の欠損規則へ渡し、商品文をBonsai、OpenAIその他のLLMへ送らないことである。

### 対象範囲

- 対象:
  - `src/search_v2/product_normalization.py` のnetwork非依存なraw candidate投影、strict normalized candidate、query・request provenance、reject結果、batch digest
  - `OutscraperAmazonProductsRequest` のquery順・最大候補数・request digestと、provider request IDを正規化結果へ結ぶ境界
  - NFKC・空白縮約・長さ上限を適用したtitle、brand、store、description、categories、color、material、features
  - 観測済みcurrencyと数値だけから作るJPY価格、rating、review count、Prime、availability
  - HTTPS Amazon商品URLのcanonical化、HTTPS画像URLの構文・長さ検証、ASINまたはcanonical商品URLによる順序維持の重複除去
  - 欠損属性の明示、破棄した任意field、候補reject理由、固定エラー、外部文を実行・補完しないtest
  - 商品正規化moduleがprovider clientやLLM SDKをimportせず、intent・prompt・enricherを入力に取らない非LLM境界
  - 標準文書と作業記録の同期
- 対象外:
  - Outscraper API key、HTTP送信、task作成、polling、retry、実response取得
  - 現行 `src/services/amazon_product_normalization.py`、`run_product_search()`、cache schemaの置換
  - Bonsai v2 request builder・system prompt・HTTP、商品候補を使うLLM処理
  - ranking profile v2、score breakdown、pHash、CLIP、画像proxy・画像取得
  - 永続repository、API、browser、UI、履歴保存
  - credential、live API、課金、実Amazon候補の意味品質確認

### 現在の状態

- 現行 `src/services/amazon_product_normalization.py` はOutscraperの可変表現を `NormalizedAmazonProduct` へ補正し、ASIN、短縮URL、商品URL、titleの順で重複を除く。Prime欠損をfalseにし、通貨不明の数値価格をJPY相当として扱うため、未知値を明示するv2契約ではない。
- `src/search_v2/outscraper_request.py` は承認済みの日英最大2 query、24件/query、最大48候補をcredential-free descriptorへ固定するが、responseの候補正規化は持たない。
- 現行v2 moduleは外部通信を持たず、現行pipelineから未参照である。本Planもこの隔離を維持する。

### 実行手順

1. strict candidate、未知属性、query provenance、重複・reject、非LLM import境界の期待動作を `tests/test_search_v2_product_normalization.py` へ追加し、production module不在のREDを記録する。
2. 検証済みOutscraper requestとprovider request IDへ結ぶraw candidate展開、値の正規化、strict model、batch digestを最小実装する。
3. 二重queryの出所不明、候補上限超過、空title、未承認query、非対応通貨、重複をfail closedまたは理由付きrejectにし、任意fieldの不正値は未知へ戻す。
4. 商品文に命令風文字列が含まれてもデータとして保持するだけで、Bonsai・OpenAI・provider clientを呼ばないことをruntime・source境界testで固定する。
5. focused・関連・全体回帰を実行し、要件、backend、security、schema、開発規約、履歴、次の再開位置を同期する。

### 進捗

- [x] 2026-09-02: TASK-008、EXEC-008、現行normalizer、v2 request descriptor、要件、security、test規約を確認した。
- [x] 2026-09-02: RED testを追加した。test SHA-256は `8625affa5c4952deca66eb8ef4e2860a9f614b7c991c7eda565c9e7dbd7b0661`、production module不在でcollection errorとなった。
- [x] 2026-09-02: v2商品正規化と非LLM境界を実装し、入力処理量・portable整数・metadata fieldの補足REDを経てfocused 35件をGREENにした。
- [x] 2026-09-02: 標準文書とTASK-008の実装状態・再開位置を同期した。
- [x] 2026-09-02: lock、Ruff、offline全体pytest、Markdown、Python構文、`git diff --check` を完了した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_product_normalization.py` | 実装前に期待した理由で失敗 | 終了2。`ModuleNotFoundError: No module named 'src.search_v2.product_normalization'`。test SHA-256は `8625affa5c4952deca66eb8ef4e2860a9f614b7c991c7eda565c9e7dbd7b0661` |
| 実装中GREEN監査 | 同上 | field境界の不足を再現し、修正後に進む | 初回は改行空白とtest assertionの問題で2 failed / 26 passed。修正後28 passed |
| supplemental RED | 同上 | URL・画像件数・切詰め記録の不足を期待した理由で再現 | 3 failed / 28 passed。test SHA-256は `adbd0a2326f0ae9cbe4a1f19ae1e7fef6b95731c5ce64857dfd6229e1289dc5e` |
| resource-bound RED | `pytest -q ... -k 'oversized_text_is_bounded or oversized_numeric_text'` | Unicode正規化・数値抽出前の入力上限不足を再現 | 2 failed / 31 deselected。当時のtest SHA-256は `d065380091a1a0e74d9c22710bd4b9c424075f439bf272ff188a67e57a741431` |
| strict-boundary RED | focused test全体 | 外側container、ASIN、review count、metadata field名の不足を再現 | 4 failed / 31 passed。最終test SHA-256は `2e155ed3a912a52d4e3ee5252e968dc08a81bb09e43257dc38cb3d4d903ff3d0` |
| focused GREEN | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_product_normalization.py` | 全件成功 | 35 passed |
| 関連回帰 | v2商品正規化、Outscraper request、既存v2・legacy正規化test | 全件成功 | 205 passed |
| lock・lint・format | 標準offline gate | 終了0 | lock 72 packages、Ruff check成功、139 files already formatted |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | liveを実行せず全件成功 | 891 passed、1 deselected |
| 文書・差分 | local Markdown link/anchor、Python 3.10 AST、`git diff --check` | 欠落・構文・whitespace error 0件 | 現行Markdown 15件・local link 650件・shell block 79件、Python 3.10 AST 139件、diff checkが成功 |

### セキュリティ・データ・互換性

- 商品title、description、category等は非信頼データとして文字列正規化と長さ上限だけを適用し、命令、prompt、tool入力として解釈しない。例外とreject結果へ生値を含めない。
- v2正規化関数はintent、prompt、client、callbackを入力に取らず、`src.clients`、OpenAI SDK、Bonsai adapterをimportしない。観測されない属性を利用者の検索意図から埋めない。
- query本文とprovider request IDはserver-side provenanceであり、通常画面用modelではない。credential、postal code、raw response、raw approval tokenは正規化batchへ保持しない。
- 現行normalizer、cache、設定、外部状態を変更しないため、データ移行と外部状態のrollbackは発生しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-02 | legacy normalizerを拡張せずv2 moduleを分離する | Prime欠損、通貨不明価格、URL・長さ制約等の現行互換挙動を変えず、未知値を明示するstrict契約を追加するため | 現行pipeline移行Planでcache・schema互換性を別途判断する |
| 2026-09-02 | USD換算率を暗黙のglobal設定から読まず、明示引数とprofile digestへ結ぶ | 同じresponseと同じpolicyから同じJPY値を再現し、設定差を結果digestへ反映するため | JPY以外を扱わない方針へ変える場合はprofile versionを更新する |
| 2026-09-02 | 商品属性はproviderの構造化fieldだけから作り、titleやdescriptionの意味推論を行わない | ローカルheuristicでも未観測属性を事実として作らず、後続rankingが未知を判別できるようにするため | 決定的な語句一致をscore evidenceとして追加する場合も観測値modelとは別層にする |
| 2026-09-02 | 本文系raw文字列32,768文字、数値文字列256文字、identifier 64文字、配列100要素を処理上限にする | 出力上限だけでなく、非信頼provider応答を正規化する前のCPU・memory使用量も有界にするため | 実provider fixtureで不足が判明した場合はschema versionと負荷testを伴って見直す |

### 発見事項

- 現行normalizerは欠損Primeをfalseへ変換するため、「観測できない」と「Primeではない」を区別できない。v2では `bool | None` を使う必要がある。
- 複数query応答でitemのqueryがなく、group位置にも結び付かないflat候補は出所を一意に決められないため、推測せずrejectする必要がある。
- request descriptorだけではsingle-use承認permitを証明できないため、normalizerは承認を主張せずrequest・query provenanceの照合だけを担当する。
- 画像URLはHTTPS・構文・長さまでしか検証しない。host allowlist、redirect、DNS/IP、content type・byte・dimension上限は後続image proxyの責務である。

### ロールバック

`src/search_v2/product_normalization.py`、対応test、EXEC-009と実装状態の文書差分だけを取り除けば、EXEC-008完了時点へ戻せる。現行pipeline、cache、credential、外部serviceにrollback操作はない。

### 結果

Outscraper応答を検証済みrequest、query順、provider request ID、明示的な換算profileへ結び、観測値だけからstrictな商品batchを決定的に作るnetwork非依存境界を実装した。未観測のbrand、categories、color、material、featuresとPrimeを未知のまま残し、ASINまたはcanonical Amazon商品URLだけで順序維持の重複除去を行う。商品文はデータとして保持するだけで、Bonsai、OpenAI、provider client、prompt、enricherへ接続しない。

初期・補足REDを経てfocused 35件、関連205件、offline全体891件、lock、Ruff、文書・差分検査が成功した。module SHA-256は `835e36b4b703f13bf5de849150b7f919da4c6c49b516d9890f4519d872aa89a6`、test SHA-256は `2e155ed3a912a52d4e3ee5252e968dc08a81bb09e43257dc38cb3d4d903ff3d0` である。Outscraper API、credential、課金、実Amazon候補、browser、現行pipeline、永続化は実行・接続していない。次の通常ローカル作業は新しい `EXEC-010` を作成し、image proxy、pHash dedupe、pinned CLIP runtimeのoffline・fixture-first設計から再開する。


## EXEC-010: 安全な画像取得・pHash・固定CLIP境界

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-02
- 最終更新日: 2026-09-02
- 関連仕様: [次期検索バックエンド v2](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[v2のofflineテスト](DEVELOPMENT.md#42-次期検索フロー-v2-のoffline境界)
- 前提Plan: [EXEC-009](#exec-009-決定的商品正規化と未知属性境界)
- 関連要件: [FR-408](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連設計: [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[SECURITY.md](SECURITY.md)、[REFERENCES.md](REFERENCES.md)

### 目的

外部の商品画像を将来のserver-side adapterが取得するとき、利用者やproviderから渡されたURLを直接browserまたは汎用HTTP clientへ渡さず、HTTPSの明示allowlist、redirect拒否、DNS解決結果と接続先IPの一致、転送量・時間・画像形式・寸法を固定境界で検証できるようにする。検証済み画像では64-bit pHashを重複検出だけに使い、意味的類似度は固定したCLIP model assetに結び付くL2正規化済みembeddingだけから評価する。

利用者から見える将来の結果は、同一または近似した商品画像を意味scoreとして誤用せず除外でき、4方向の参照画像と最大4枚の商品画像の類似度を固定式で再現できることである。本Planではoffline境界を作る。実HTTP、605 MBのmodel weight取得、実CLIP encoder、画像rankingの有効化、現行画面への表示は確認しない。

### 対象範囲

- 対象:
  - `src/search_v2/image_proxy.py` のURL・host・DNS/IP・redirect・timeout・content type・byte数・寸法・decompression bomb境界
  - server-side resolverと、解決済みIPへ接続して実peer IPを返すtransportを注入するnetwork adapter契約
  - JPEG、PNG、WebPだけをPillowで完全decodeし、metadataを引き継がないRGB artifactへ変換する処理
  - `src/search_v2/image_similarity.py` の32x32 grayscale DCTによる64-bit pHash、Hamming距離、閾値5以下の順序維持重複除去
  - `openai/clip-vit-base-patch32` revision `12b36594d53414ecfba93c7200dbb7c7db3c900a` のimage runtimeに必要なasset名、byte数、SHA-256、512次元を固定するmanifest
  - symlink、欠損、余分なfile、byte数・digest不一致をload前に拒否し、downloadを許さないlocal asset verifier
  - 検証済みasset rootと `local_files_only=True` を注入encoderへ渡し、出力件数・512次元・有限値を検証してL2正規化するruntime境界
  - 4参照画像それぞれについて最大4商品画像との最大cosineを取り、4値の平均を `clamp((mean + 1) / 2, 0, 1)` へ写像するfixture score
  - Pillowのdirect dependencyとlock、標準文書、作業記録の同期
- 対象外:
  - DNSまたはHTTPの実adapter、実画像URLへの接続、Amazon CDN host allowlistの運用値、proxy endpoint
  - model assetのdownload・repository格納、PyTorch・Transformers・ONNX runtime、GPU/CPU選定、実画像のCLIP推論
  - Cloudflare画像応答、画像生成state、Outscraper HTTP・polling、現行 `run_product_search()` への接続
  - ranking profile v2、画像weightの有効化、品質acceptance、cache・永続repository、API、browser、UI
  - credential、live API、課金、実Amazon候補または生成画像の品質確認

### 現在の状態

- `product_normalization.py` は画像URLのHTTPS・構文・長さを検証し、`image_proxy.py` はhost、DNS/IP、応答を注入resolver・transport境界で検証する。実resolver・transportとpipelineはまだ接続していない。
- `cloudflare_request.py` は参照PNGの構造・CRC・511px・8 MiB境界を持ち、`image_proxy.py` は外部商品画像のJPEG・PNG・WebP decode境界を持つ。Cloudflare応答の画像正規化とは未接続である。
- Pillow 12.2.0をdirect dependencyとしてlockした。NumPy、Torch、Transformers、ONNX Runtime、imagehashは追加していない。
- OpenAI CLIPの公開APIはimage featureを返す一方、model名指定のloadは必要に応じdownloadする。したがって本Planではmodel名loadを使わず、固定済みlocal assetとdownload禁止を境界にする。
- pinned Hugging Face revisionの `config.json` はprojection dimension 512を定義する。image runtime用の固定対象は `config.json` 4,186 bytes / SHA-256 `b575ef3c36f2a057fa19e221650105052d61cc9c1a972ec15019c6261ec98770`、`preprocessor_config.json` 316 bytes / SHA-256 `910e70b3956ac9879ebc90b22fb3bc8a75b6a0677814500101a4c072bd7857bd`、`pytorch_model.bin` 605,247,071 bytes / SHA-256 `a63082132ba4f97a80bea76823f544493bffa8082296d62d71581a4feff1576f` である。

### 実行手順

1. image proxy、pHash、asset verifier、runtime、fixture scoreの期待動作を `tests/test_search_v2_image_proxy.py` と `tests/test_search_v2_image_similarity.py` へ追加し、production module不在のREDとtest SHA-256を記録する。
2. network clientを内蔵しないimage proxy coreを実装し、explicit allowlist、HTTPS、最大8 DNS address、global IP、peer IP一致、redirect拒否、10秒、8 MiB、4096px、単一frame、JPEG/PNG/WebPをfail closedにする。
3. metadataを除いたRGB artifactから64-bit pHashを決定的に計算し、Hamming距離5以下だけを重複として安定除去する。距離を意味scoreへ渡すAPIを作らない。
4. 固定asset manifestとlocal verifierを実装する。検証済みrootだけをdownload禁止の注入encoderへ渡し、embeddingをruntime digestへ結び、固定fixture scoreを実装する。画像rankingは既定かつ固定で無効のままにする。
5. focused・関連・全体回帰を実行し、要件、backend、security、開発規約、reference、履歴、次の再開位置を現行実装へ同期する。

### 進捗

- [x] 2026-09-02: TASK-008、EXEC-009、画像URL境界、画像security要件、CLIP・Pillow公式資料、現行dependencyを確認した。
- [x] 2026-09-02: RED testを追加した。image proxy test SHA-256は `8dfaac0e6481bcf28604b76499d95d04cbc3bbe3d456ddae9a500cf51b5ae9fe`、image similarity test SHA-256は `8dd1ada6b25608b2e8397817473052a8eb2e01e80fd2e6372662d2425afe190d` で、production module不在による2件のcollection errorとなった。
- [x] 2026-09-02: image proxy、pHash、固定CLIP asset・embedding境界を実装し、runtime digestとpixel digestの補足REDを閉じてfocused 76件をGREENにした。
- [x] 2026-09-02: 標準文書とTASK-008の実装状態・再開位置を同期した。
- [x] 2026-09-02: lock、Ruff、offline全体pytest、Markdown、Python構文、`git diff --check` を完了した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_image_proxy.py tests/test_search_v2_image_similarity.py` | 実装前にproduction module不在で失敗 | 終了2。`src.search_v2.image_proxy` と `src.search_v2.image_similarity` のmodule不在による2件のcollection error。test SHA-256はそれぞれ `8dfaac0e6481bcf28604b76499d95d04cbc3bbe3d456ddae9a500cf51b5ae9fe`、`8dd1ada6b25608b2e8397817473052a8eb2e01e80fd2e6372662d2425afe190d` |
| runtime digest supplemental RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_image_similarity.py::test_clip_score_rejects_consistent_but_unapproved_runtime_digest` | 同じ未承認runtime digestを全embeddingへ付けてもscoreできる抜けを再現 | 1 failed。`DID NOT RAISE ClipRuntimeError`。当時のtest SHA-256は `26911ea91c8cceac3f9b3f13765e918c46cb9a6c19f95059c0019825bd9ba997` |
| pixel digest supplemental RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_image_proxy.py::test_canonical_pixel_digest_binds_dimensions` | 同一RGB byteでも寸法が異なるartifactを別digestへ結ぶ関数の不足を再現 | 1 failed。`AttributeError: module ... has no attribute 'proxy_image_pixel_sha256'`。当時のtest SHA-256は `462070c23984304e087c4faa9a9094a4f5433aa41ae13edd9a06a5f7ace4abf5` |
| focused GREEN | REDと同じ2 test file | 全件成功 | 76 passed。最終test SHA-256はimage proxy `e719cb0fe972b8996baf0fca9fe0f0fa9eae1902b4f4167148b54023af1ffbce`、image similarity `40469caaf3fd54757a52c572560bb501da1f774b46f0875d810c4f18a362e975` |
| 関連回帰 | `tests/test_search_v2_cloudflare_request.py`、`tests/test_search_v2_product_normalization.py` を含むv2画像・商品境界 | 全件成功 | 253 passed |
| lock・lint・format | 標準offline gate | 終了0 | lock 72 packages、Ruff check成功、143 files already formatted |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | liveを実行せず全件成功 | 967 passed、1 deselected |
| 文書・差分 | local Markdown link/anchor、Python 3.10 AST、`git diff --check` | 欠落・構文・whitespace error 0件 | 現行Markdown 15件・local link 668件・shell block 79件、Python 3.10 AST 143件、diff checkが成功 |
| live・実model | 実HTTP、実商品画像、実asset、実encoder、browser | 本Planでは実行しない | 未実行。外部送信・大容量asset・runtime dependency・品質承認が対象外のため |

### セキュリティ・データ・互換性

- URLのhost allowlistはserver-side設定だけから渡し、URL側のuserinfo、IP literal、非443 port、fragment、非HTTPSを拒否する。DNSが返す全addressをglobal IPに限定し、transportが報告するpeer IPを解決結果へ照合する。
- redirectは追跡せず拒否する。transportは解決済みaddress、10秒、redirect禁止、identity encoding、streaming上限を受ける契約とし、response bodyの8 MiB超過を宣言値と実読込値の両方で拒否する。
- Pillowへ渡す前にbyte数とcontent typeを限定し、decoder formatをJPEG・PNG・WebPへ絞る。decompression bomb warningをerrorとして扱い、縦横4096px・総pixel数4096²以下・単一frameを完全decode前後に検証する。raw画像、metadata、URL、DNS値をbrowser modelまたは例外へ残さない。
- model assetはsymlinkを許さないexact file setとしてbyte数とSHA-256を検証してからencoderへ渡す。検証済みdigestは供給元の信頼性そのものやpickle deserializationのsandboxを証明しないため、実encoder追加時に安全なloaderとprocess隔離を別途審査する。
- 現行pipeline、cache schema、設定、外部状態を変更しない。Pillowをdirect dependencyへ昇格する以外のruntime dependencyは追加しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-02 | redirectをfollowせず全て拒否する | redirect先ごとのallowlist・DNS・peer再検証漏れをなくし、現行security要件の厳しい側を実装するため | 実provider画像URLがredirect必須とfixtureで確認された場合だけ、hop数を固定した再検証設計を別Planで追加する |
| 2026-09-02 | HTTP client・DNS resolverを内蔵せず、解決済みIPへ接続するtransport契約を注入する | offline TDDを維持しつつ、通常のhostname再解決によるDNS rebindingをadapterへ隠さないため | 実adapter追加時はsocket接続とTLS SNI・certificate host検証を同時に証明する |
| 2026-09-02 | pHashは32x32 DCTの8x8低周波64 bit、Hamming閾値5とし、重複除去だけに使う | 意味類似度との役割混同をAPIレベルで防ぎ、固定fixtureで再現するため | 固定画像datasetでfalse positive・negativeが受入外ならalgorithm versionと閾値を更新する |
| 2026-09-02 | CLIPは3つのlocal assetをexact SHA-256へ固定し、encoderは注入境界に留める | 現行環境へ600 MB超のweightと未lockのML runtimeを暗黙取得せず、download禁止・出力検証を先に固定するため | 実encoder実装時はdependency lock、loader安全性、CPU/GPU再現性、asset配布を別途検証する |
| 2026-09-02 | 画像rankingを本Planで有効化しない | CLIPのimage-to-image品質は固定評価を通るまで未保証という要件を守るため | 次のranking Planが代表fixtureの受入基準を満たした場合だけweightを有効にする |

### 発見事項

- Pillowの公式security guidanceはMIMEとmagicの独立検証、format allowlist、decompression bomb warningのerror化、実用的な寸法上限、metadata除去、decoder isolationを推奨している。process sandboxは本Planのpure Python境界だけでは成立せず、実adapter配備時の未完了項目として残る。
- pinned Hugging Face revisionのPyTorch weightはpickle importを含むため、SHA-256一致だけで任意assetの安全なdeserializationを許可してはならない。本Planの注入encoderはまだ実weightをloadしない。
- OpenAI公式CLIPのmodel名loadは必要に応じてdownloadするため、offline runtimeではlocal path・固定manifest・download禁止を明示的に強制する必要がある。

### ロールバック

`src/search_v2/image_proxy.py`、`src/search_v2/image_similarity.py`、対応test、Pillow direct dependency、EXEC-010と実装状態の文書差分だけを取り除けば、EXEC-009完了時点へ戻せる。model asset、cache、credential、外部serviceを変更しないため、外部状態のrollbackはない。

### 結果

server-side exact host allowlist、global DNS addressと実peer IPの一致、redirect拒否、10秒、8 MiB、JPEG・PNG・WebP、4096px、decompression bombを固定した注入式image proxy coreを実装した。metadataを除いたRGB artifactは寸法とbyteをdomain-separated digestへ結ぶ。32x32 DCTの64-bit pHashとHamming閾値5は重複除去だけに使い、CLIP scoreから分離した。

CLIPはpinned revisionの3 assetをexact file名・byte数・SHA-256へ固定し、local-only注入encoderの出力を512次元・有限・L2正規化へ制限した。4方向ごとの最大cosine平均と固定写像をfixtureで再現し、現行runtime digest以外をscoreで拒否する。画像rankingはfalseのままである。

初期RED、runtime digest・pixel digestの補足REDを経てfocused 76件、関連253件、offline全体967件、lock、Ruff、文書・差分検査が成功した。module SHA-256はimage proxy `094723f4b7075509fc6ab668124b02afabefbaee59ce9f9758ed77c9f35e2d75`、image similarity `a035d748ed82049f181be31d3209b412019d72b0ec94618bec35aae0a11abe2f` である。実DNS・HTTP、実商品画像、605,247,071 bytesのweight、実encoder・推論、process isolation、ranking品質、browser、現行pipelineは実行・接続していない。次の通常ローカル作業は新しい `EXEC-011` を作成し、ranking profile v2、欠損weight再正規化、negative penalty、stable sort、score breakdownのoffline TDDから再開する。


## EXEC-011: 決定的ランキングv2とスコア内訳

### メタデータ

- 状態: 完了
- 作成日: 2026-09-03
- 最終更新: 2026-09-03
- 対応Task: [TASK-008](#task-008-次期検索フロー-v2-の実装) 第9マイルストーン
- 関連要件: [PRD-011、FR-409、FR-410](REQUIREMENTS.md#35-次期検索フロー-v2)、[DATA-012](REQUIREMENTS.md#5-データキャッシュ要件)
- 関連負債: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)
- 後続候補: [TASK-005](#task-005-ランキング品質評価の確立)

### 目的

正規化済みの検索意図と商品候補から、同じ入力なら同じ順位と内訳を返すnetwork非依存のranking v2境界を作る。利用者向け表示へ投影できるよう、一致した条件、不足した条件、確認できないcomponent、避けたい条件への一致を分離し、価格や商品属性が欠損した商品を0点として不当に減点せず、利用可能なcomponentだけでweightを再正規化する。

### 対象範囲

- 対象:
  - `src/search_v2/ranking.py` のstrict・frozenなranking profile、component、score breakdown、ranked batch model
  - title 0.40、attributes 0.30、price 0.20、image 0.10、negative 1件0.20・最大0.50を固定するprofileとdomain-separated SHA-256
  - intent、query plan、normalized product batchのdigest連鎖を検証してから採点するoffline関数
  - titleは商品名・カテゴリ・brand・model numberと商品titleの言語別token coverageを比較し、日本語・英語の高い方を採用する処理
  - attributesはrequired 3、preferred 2、カテゴリ・色・特徴・brand 1の固定weightで、providerが構造化fieldとして返した観測属性だけと照合する処理
  - strict price modeと観測済み価格によるprice score、観測済みtitle・description・属性だけに対するnegative match
  - 未指定または未観測componentを除外したeffective weight、score contribution、減点前・減点後の4桁score
  - 同点時にOutscraper response index昇順を使う固定tie-break、ranked batch digest
  - focused test、関連回帰、標準文書、履歴の同期
- 対象外:
  - 実CLIP推論、画像品質評価、image weightの有効化。image componentは固定で無効のままにする
  - TF-IDFやweightの品質最適化、代表検索dataset、検索品質の良否判定。これらはTASK-005で扱う
  - 現行 `src/services/product_scoring.py`、`run_product_search()`、cache、永続repository、APIへの接続
  - 外部委託中のフロントエンドの確認、テスト、変更、バックエンド接続
  - Bonsai、Cloudflare、Outscraper、OpenAIその他の外部通信、credential、課金、実商品確認

### 現在の状態

- `NormalizedSearchIntent` は正規化済みの日英条件とstrictな価格modeを持ち、`SearchQueryPlan` はintent digestへ結び付く。
- `NormalizedProductBatch` はquery planとOutscraper requestのdigest、最大48件の観測値だけの商品候補を持つ。未観測属性は `unknown` に残る。
- `image_similarity.py` は固定fixtureのCLIP score境界を持つが、実asset・実encoder・品質評価はなく、`CLIP_IMAGE_RANKING_ENABLED` はfalseである。
- Plan開始時、現行rankingはlegacy modelと設定を使い、価格欠損を0.0として固定weightへ含め、総合scoreだけでstable sortしており、v2 modelを受けるranking境界とscore breakdownは存在しなかった。本Planで独立した `ranking.py` を追加し、legacy経路は変更していない。

### 実行手順

1. profile digest、artifact binding、日英token coverage、観測属性だけの照合、価格mode、欠損weight再正規化、negative cap、stable tie-break、strict outputを `tests/test_search_v2_ranking.py` へ追加し、production module不在のREDとtest SHA-256を記録する。
2. strict profile・component・breakdown・ranked batch modelとcanonical digestを実装し、画像componentを `disabled` へ固定する。
3. intent・query・batch bindingをfail closedに検証し、title・attributes・price・negative scoreを計算して、利用可能なbase weightだけを1.0へ再正規化する。
4. 表示scoreを小数4桁へ固定し、同点をresponse index昇順で解決してrankを付ける。空batchも外部処理なしで決定的に返す。
5. focused、既存v2・legacy ranking関連、offline全体、Ruff、lock、Markdown・差分検査を実行し、要件、backend、schema、security、課題、履歴、次の再開位置を同期する。

### 進捗

- [x] 2026-09-03: TASK-008、EXEC-010、ranking要件、legacy score、strict intent・query・product・image modelを確認した。
- [x] 2026-09-03: 本Planを作成し、外部委託中のフロントエンド、外部API、現行pipelineを対象外に固定した。
- [x] 2026-09-03: RED testを追加した。test SHA-256は `cd511be128031b3fb9f465b0ba9459ca9dbff7fae68334003ee4619bac0cdf24` で、production module不在によりcollection errorとなった。
- [x] 2026-09-03: ranking v2 model、固定profile、title・attribute・price・negative計算、欠損weight再正規化、tie-break、digestを実装した。
- [x] 2026-09-03: focused 17件、関連266件、offline全体984件とlock・Ruff・文書・差分gateを完了した。
- [x] 2026-09-03: 標準文書、TASK-008、作業履歴、次の再開位置を同期した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_ranking.py` | production module不在または契約未実装により失敗 | 終了2。`ModuleNotFoundError: No module named 'src.search_v2.ranking'` によるcollection error。test SHA-256は `cd511be128031b3fb9f465b0ba9459ca9dbff7fae68334003ee4619bac0cdf24` |
| focused GREEN | REDと同じtest file | 全件成功 | 17 passed。整形後test SHA-256は `492b7b89e2af31005afdc91bd94e3c7877d379b7936cc6534ca1344ffd789e07` |
| 関連回帰 | v2全境界、legacy ranking、backend characterization | 全件成功 | 266 passed |
| lock・lint・format | 標準offline gate | 終了0 | lockは72 packages、Ruff check成功、145 files already formatted |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | liveを実行せず全件成功 | 984 passed / 1 deselected |
| 文書・差分 | local Markdown link・anchor・fence、Python 3.10 AST、`git diff --check` | 欠落・構文・whitespace error 0件 | 現行Markdown 16件、local link 688件、anchor 861件、fence 195件、Python 3.10 AST 145件、差分error 0件 |
| live・UI | 実provider、実画像、実model、browser、委託フロントエンド | 本Planでは実行しない | 対象外のため未実行 |

### セキュリティ・データ・互換性

- ranking入力は既存strict modelを再検証し、intent、query plan、product batchのdigest不一致を固定文言で拒否する。raw provider response、credential、query本文を新しい例外へ含めない。
- 商品属性scoreは `ObservedProductAttributes` の構造化された観測値だけを使う。titleまたはdescriptionからbrand、color、material、featureを推測しない。
- negative matchは観測済み文字列とのtoken一致だけであり、商品を自動除外しない。外部文字列をコード、prompt、URLとして実行または送信しない。
- outputは内部domain modelであり、そのまま通常画面へ返さない。内部weight、raw score、digest、provider metadataを表示用modelから除外する責務は後続API Planに残す。
- legacy model、現行ranking、cache version、設定、外部状態を変更しないため、現行StreamlitとCLIの互換性を維持する。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-03 | ranking v2をlegacy scorerから分離し、日英token coverageと観測属性のweighted matchを使う | 候補集合で値が変わるTF-IDFを初期profileへ持ち込まず、同じintentと商品から内訳を再現・説明するため | TASK-005の固定評価で品質が受入外なら、新しいprofile IDとdigestで方式を更新する |
| 2026-09-03 | priceは条件未指定または商品価格未観測ならmissingとする | 0点との違いを保持し、欠損商品を固定weightで不当に減点しないため | 表示要件または評価datasetが別の扱いを要求した場合にprofile versionを更新する |
| 2026-09-03 | image base weight 0.10をprofileへ残すが、componentはdisabledとする | 承認済み将来構成をdigestへ含めつつ、実推論と固定品質評価前の利用を防ぐため | 実CLIP推論、process isolation、TASK-005の品質基準が完了した別Planでのみ有効化する |
| 2026-09-03 | 同点は `response_index` 昇順で解決する | provider応答内の観測順を維持し、入力tupleの並替えに依存しない固定keyにするため | provider順を品質信号として使わない要件が確定した場合は新profileで見直す |

### 発見事項

- `NormalizedProductBatch` の `response_index` はqueryごとに戻らず、全候補を展開した順の一意な連番である。このため複数queryでも同点keyとして使用できる。
- base weightを利用可能componentだけへ再配分すると循環小数になるため、effective weightは6桁、scoreとcontributionは4桁へ固定し、model側でも合計と内訳を再検証する必要があった。
- RED後のRuff検査でtestの未使用type importを1件削除した。受入assertionは変更せず、最終test SHA-256をGREEN記録へ別掲した。

### ロールバック

`src/search_v2/ranking.py`、`tests/test_search_v2_ranking.py`、EXEC-011と実装状態を更新した標準文書だけを取り除けば、EXEC-010完了時点へ戻せる。現行pipeline、cache、credential、外部service、委託フロントエンドを変更しないため、データ移行や外部状態のrollbackはない。

### 結果

strict・frozenな固定ranking profile、4componentの状態と内訳、ranked batchを `src/search_v2/ranking.py` に実装した。intent・query plan・normalized product batch・profileのdigest連鎖をfail closedに確認し、titleの日英token coverage、観測属性だけの重み付き一致、strict price mode、negative penaltyを決定的に計算する。未指定・未観測componentは0点と区別してweightから除外し、画像はdisabled、同点はresponse index昇順とした。

module SHA-256は `be5d6d28e042a2144eaccb7d458f57dbd0e1a45fc8aa7afd1de26247dde35c50`、最終test SHA-256は `492b7b89e2af31005afdc91bd94e3c7877d379b7936cc6534ca1344ffd789e07` である。focused 17件、関連266件、offline全体984件、lock、Ruff、文書・差分検査が成功した。外部API、credential、課金、実商品、実画像、実CLIP asset・推論、ranking品質、現行pipeline、cache、API、browser、委託フロントエンドは実行・接続していない。

次の通常ローカル作業は新しい `EXEC-012` を作成し、Bonsai v2 request builder・HTTP adapterと次期実行境界を、注入transportまたはmockによるoffline TDDから再開する。実provider通信、credential、課金、フロントエンド確認・接続は引き続き対象外にする。


## EXEC-012: Bonsai v2 requestと実行境界

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-03
- 最終更新日: 2026-09-04
- 前提: [EXEC-004](#exec-004-bonsai-v2-strict応答境界)、[EXEC-006](#exec-006-2段階承認と費用予約境界)
- 関連要件: [次期検索フロー](../SEARCH-FLOW.md)、[次期検索バックエンド](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)
- 関連負債: [TD-003](ISSUES.md#td-003-アクセス制御と利用量制御)、[TD-005](ISSUES.md#td-005-bonsai通信の回復性)

### 目的

Bonsaiへ送るv2 intent要求を、利用者入力、固定system prompt、canonical strict schema、model、生成上限、接続先、timeoutへ決定的に結び付ける。利用量予約を送信前に開始し、注入transportによる1回の試行を成功または失敗として確定した後、既存strict response adapterから `NormalizedSearchIntent` を返す。

利用者が観察できる本Planの結果は、外部通信なしのテストでexact JSON body、redirect禁止、応答byte上限、固定エラー、raw input・response非保持、reservation lifecycleを確認できることである。これは実Bonsaiへの接続成功ではない。

### 対象範囲

- v2専用の固定Bonsai intent system prompt asset
- credentialを含まないcanonical `/v1/chat/completions` request descriptorとdomain-separated digest
- loopback HTTPまたはcanonical HTTPSだけを許すendpoint境界
- fixed headers、redirect禁止、timeout、identity encoding、応答byte上限を要求する注入transport protocol
- exact 1-callかつ十分なtoken上限を持つBonsai intent利用量予約の送信前照合
- reservationの `reserved -> started -> succeeded|failed` lifecycleとstrict response adapterの接続
- mock/fixtureだけを使うoffline TDD、標準文書と再開位置の同期

### 対象外

- `requests`、`httpx`、socket等を使う実HTTP transport実装と実Bonsai通信
- credential、外部送信、課金、live API、model品質評価
- 自動再試行、backoff、circuit breaker。1回の失敗後に再試行する場合は新しい予約を要求する
- 現行 `src/clients/bonsai_client.py`、`run_product_search()`、cache、Streamlit、CLIへの接続
- Cloudflare・OutscraperのHTTP adapter、後半state、永続repository、API
- 外部委託中の次期フロントエンドの確認、レビュー、起動、テスト、接続

### 現在の文脈

- `src/search_v2/bonsai_adapter.py` はexact prompt、canonical schema、full raw responseをprovenanceへ結び、OpenAI互換envelopeとcontent全体をfail closedにparseするが、requestを作らずHTTPも行わない。
- `src/search_v2/usage_ledger.py` はprovider別のcall・token・整数micro-USDを送信前に予約し、失敗attemptも上限へ算入できるが、Bonsai requestとの実行lifecycleは未接続である。
- `src/search_v2/state_machine.py` は `draft -> intent_processing` を表すが、Bonsai実行自体は未接続である。intentは第1確認より前に作るため、第2確認tokenではなく利用量予約で送信前上限を強制する。
- 現行Bonsai promptとclientはlegacy schema用であり、本Planでは変更せず、v2 assetと境界を独立させる。

### 実行手順

1. canonical request、prompt/schema/body digest、endpoint、非serializable raw field、transport引数、response上限、reservation lifecycle、固定エラー、network client非依存を `tests/test_search_v2_bonsai_request.py` に追加し、production module不在のREDとtest SHA-256を記録する。
2. 固定prompt asset、strict request descriptor、prepared request、HTTP response・transport protocol、request digestを実装する。
3. 送信前にprepared requestとreserved usageを再検証し、ledgerを開始してtransportを1回だけ呼び、strict response parse後に成功、例外時に失敗として確定する。
4. focused、Bonsai・intent・usage・state関連、offline全体、lock、Ruff、Markdown・差分検査を実行する。
5. 要件、backend、security、課題、履歴、利用者向け残作業、次の再開位置を同期する。

### 進捗

- [x] 2026-09-03: EXEC-011の再開位置、Bonsai adapter、legacy client、usage ledger、intent stateを確認した。
- [x] 2026-09-03: 本Planを作成し、実通信、自動再試行、現行pipeline、委託フロントエンドを対象外に固定した。
- [x] 2026-09-03: RED testを追加した。test SHA-256は `9ce96b2156a234820f7aad66ad9450c1ff56954325cbba7d9286f2587e063c97` で、production module不在によりcollection errorとなった。
- [x] 2026-09-03: 固定v2 prompt、canonical request descriptor、prepared body、注入transport protocol、応答上限を実装した。
- [x] 2026-09-03: request一致のreserved 1-call usageを開始し、transport・parseの成功または失敗をledgerへ確定する実行境界を実装した。
- [x] 2026-09-03: focused 44件、関連114件、offline全体1028件とlock・Ruffを完了した。
- [x] 2026-09-03: 標準文書と次の再開位置を同期した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_bonsai_request.py` | request境界未実装により失敗 | 終了2。`ModuleNotFoundError: No module named 'src.search_v2.bonsai_request'` によるcollection error。test SHA-256は `9ce96b2156a234820f7aad66ad9450c1ff56954325cbba7d9286f2587e063c97` |
| focused GREEN | REDと同じtest file | 全件成功 | 44 passed。整形後test SHA-256は `8f2aeccfb3bf2abda97cf5528dd342bfe47aaa442eac99d2bc22c50194026fe8` |
| 関連回帰 | Bonsai、intent、usage ledger、state machine関連test | 全件成功 | 114 passed |
| lock・lint・format | 標準offline gate | 終了0 | lockは72 packages、Ruff check成功、147 files already formatted |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | liveを実行せず全件成功 | 1028 passed / 1 deselected |
| 文書・差分 | local Markdown link・anchor・fence、Python 3.10 AST、`git diff --check` | 欠落・構文・whitespace error 0件 | 現行Markdown 16件、local link 695件、heading 942件、fence 195件、Python 3.10 AST 147件、差分error 0件 |
| live・UI | 実Bonsai、credential、外部通信、browser、委託フロントエンド | 本Planでは実行しない | 対象外 |

### セキュリティ・データ・互換性

- request descriptorと実行結果へ利用者入力、prompt本文、request body、raw responseをserializable fieldとして保持せず、SHA-256だけを残す。transportへ渡すexact bodyは短命なprepared request内だけに保持する。
- HTTPはloopback addressへの `http` またはcanonical `https` に限定し、userinfo、query、fragment、redirect、圧縮応答を拒否する。認証headerは本Planのprotocolへ含めない。
- response metadataとstreamed bodyを上限内で検証してから既存strict adapterへ渡す。provider本文やtransport例外の詳細を利用者向け例外へ含めない。
- 現行Bonsai client、設定、legacy prompt、pipelineを変更せず、v2 moduleは未接続のままにする。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-03 | 本Planでは実HTTP libraryを内蔵せず、keyword-onlyの注入transport protocolを定義する | 外部通信なしでexact egress契約を検証し、credentialや環境依存を持ち込まずに責務を分離するため | transport実装を着手する次PlanでDNS、TLS、proxy、loggingを別途設計する |
| 2026-09-03 | 1 executionを1 transport callと1 usage reservationへ固定し、自動再試行しない | 失敗attemptを隠さず利用上限へ算入し、同じ予約で複数回送信しないため | TD-005を解消する際はattemptごとの新予約と明示上限を設計する |
| 2026-09-03 | intent生成は第2確認tokenではなく送信前利用量予約でguardする | intentは利用者が第1確認する計画を作る前に必要であり、後段承認を循環依存させないため | intent生成前の別承認が製品要件になった場合にstateを更新する |

### 発見事項

- 現行 `SearchSessionSnapshot` はBonsai reservation IDを保持しない。今回はexecution関数がledger lifecycleを完結させ、sessionへ途中予約を保存する設計は後続の永続job境界へ残す。
- 利用量ledgerのtokenはprovider報告値を後から補正するmodelではないため、request bodyのUTF-8 byte数と最大出力tokenの和を保守的な送信前上限として要求する。

### ロールバック

追加するv2 request module、prompt asset、focused testと、本Planに伴う標準文書の追記だけを取り除けばEXEC-011完了時点へ戻せる。legacy client、現行pipeline、外部状態、credential、委託フロントエンドを変更しないため、データ移行や外部状態のrollbackはない。

### 結果

`src/search_v2/bonsai_request.py` と固定 `bonsai_intent_prompt.txt` に、OpenAI互換 `/v1/chat/completions` のcanonical body、strict・credential-free descriptor、domain-separated request digest、注入transport protocol、bounded HTTP response、利用量lifecycleを実装した。request descriptorと結果はraw利用者入力・prompt・body・responseを持たず、execution時にexact body・digest・reserved 1 call・保守的token上限を再検証する。transportまたはstrict parseが失敗してもattemptを `failed` として残し、自動再試行しない。

module SHA-256は `cbcf8bb4802c3cb16145dbbe579cbbb7ec03403accb678163b12f185526e2910`、prompt SHA-256は `9eed0e3a2361b8cfaf72b3165e149f774aa524b57493f7355513898b49612ee7`、最終test SHA-256は `8f2aeccfb3bf2abda97cf5528dd342bfe47aaa442eac99d2bc22c50194026fe8` である。focused 44件、関連114件、offline全体1028件、lock、Ruff、文書・差分検査が成功した。実HTTP transport、実Bonsai、credential、課金、現行pipeline、cache、API、browser、委託フロントエンドは実行・接続していない。

次の通常ローカル作業は新しい `EXEC-013` を作成し、`BonsaiRequestTransport` の実HTTP adapterをRequests通信のmockによるoffline TDDで実装する。実Bonsai通信、credential、課金、フロントエンド確認・接続は引き続き対象外にする。


## EXEC-013: Bonsai v2 HTTP transport

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-03
- 最終更新日: 2026-09-03
- 前提: [EXEC-012](#exec-012-bonsai-v2-requestと実行境界)
- 関連要件: [次期検索フロー](../SEARCH-FLOW.md)、[次期検索バックエンド](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)
- 関連負債: [TD-003](ISSUES.md#td-003-アクセス制御と利用量制御)、[TD-005](ISSUES.md#td-005-bonsai通信の回復性)

### 目的

EXEC-012の `BonsaiRequestTransport` を満たすRequests製HTTP adapterを追加し、canonical bodyを変更せず1回だけPOSTできる境界を作る。環境proxy・環境由来認証を使わず、TLS検証を有効にし、redirectと自動再試行を禁止し、応答を固定byte上限内でstream読込して必ず接続資源を閉じる。

利用者が観察できる本Planの結果は、Requestsの通信をmockした外部通信なしのテストで、接続先、header、body、timeout、TLS、redirect、proxy、retry、応答上限、close、固定エラーを確認できることである。これは実Bonsaiへの接続成功、model品質、現行検索への接続を意味しない。

### 対象範囲

- `src/search_v2/bonsai_http.py` の `RequestsBonsaiTransport`
- EXEC-012で検証済みのcanonical endpointとexact transport引数の再検証
- request bodyを再serializeしない `data=body` の1回POST
- 新規Requests Session、`trust_env=False`、既定header・cookie・proxyの除去、TLS検証有効
- HTTP/HTTPS adapterの自動retry 0、redirect禁止、streaming応答
- status・Content-Type・Content-Encoding・Content-Length metadataの投影
- 非200、非JSON、圧縮、宣言済み上限超過でresponse bodyを読まない境界
- 実読込byte数の上限、空chunk除外、response・sessionの確実なclose
- Requests SessionとResponseをmockしたoffline TDD、標準文書と再開位置の同期

### 対象外

- 実Bonsai、localhost、任意hostへの実HTTP・DNS・TLS通信
- credential、Authorization、環境proxy、custom CA、外部送信、課金、live API、model品質評価
- 自動再試行、backoff、circuit breaker。再試行はattemptごとの新しい利用量予約を設計する別Planへ残す
- 現行 `src/clients/bonsai_client.py`、設定、`run_product_search()`、cache、Streamlit、CLIへの接続
- Cloudflare・OutscraperのHTTP adapter、後半state、永続repository、API
- 外部委託中の次期フロントエンドの確認、レビュー、起動、テスト、接続

### 現在の文脈

- `src/search_v2/bonsai_request.py` はcanonical endpoint・body・header・timeout・redirect・response上限を検証し、keyword-only `BonsaiRequestTransport` を1回だけ呼ぶ。network clientは持たない。
- 同moduleの `BonsaiHttpResponse` はstatusと限定したmetadata、byte chunk列だけを上位のstrict response adapterへ渡す。
- Requestsは既存依存であり、新しいpackageやlock変更は不要である。新規Sessionの既定環境連携とheaderを明示的に無効化しなければ、request digestにないproxy・認証・headerが実送信へ混入し得る。
- 通常pytestはsocketと名前解決を遮断する。本PlanはさらにSessionとResponseをmockし、実接続が発生しないことを検証する。

### 実行手順

1. Planを登録し、Requestsの現行Session・Response契約とEXEC-012のtransport引数を確認する。
2. exact POST、環境分離、no-retry、no-redirect、TLS、metadata、body非読込、stream上限、close、固定エラーを `tests/test_search_v2_bonsai_http.py` に追加し、production module不在のREDとtest SHA-256を記録する。
3. 専用Requests transportを最小実装し、focused testをGREENにする。
4. EXEC-012のexecutionへ実adapterを注入した統合mock testと、Bonsai・usage関連回帰を確認する。
5. offline全体、lock、Ruff、Markdown・Python構文・差分検査を実行する。
6. 要件、backend、security、課題、参照、履歴、利用者向け残作業、次の再開位置を同期する。

### 進捗

- [x] 2026-09-03: agents-setup、`AGENTS.md`、`DEVELOPMENT.md`、EXEC-012、既存transport契約、Requests依存、pytestのnetwork guardを確認した。
- [x] 2026-09-03: 本Planを作成し、実通信、credential、自動再試行、現行pipeline、委託フロントエンドを対象外に固定した。
- [x] 2026-09-03: RED testを追加した。test SHA-256は `f42a5319ca6053eafac4a59d7cf186dbcc160bfd4dc254ec38c87f5c1126ba33` で、production module不在によりcollection errorとなった。
- [x] 2026-09-03: Requests HTTP transportを実装し、focused 32件をGREENにした。
- [x] 2026-09-03: 関連回帰146件、offline全体1060件、lock、Ruffを完了した。
- [x] 2026-09-03: 標準文書、Markdown・Python構文・agents-setup・差分検査を完了した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_bonsai_http.py` | HTTP transport未実装により要求した振る舞いで失敗 | 終了2。`ModuleNotFoundError: No module named 'src.search_v2.bonsai_http'` によるcollection error。test SHA-256は `f42a5319ca6053eafac4a59d7cf186dbcc160bfd4dc254ec38c87f5c1126ba33` |
| focused GREEN | REDと同じtest file | 全件成功 | 32 passed。Ruff整形後test SHA-256は `457768048d5c2b35f5d7131b2e65b4d163db577b29dd6dac46d8462e6d272236` |
| integration・関連回帰 | Bonsai request・adapter、intent、usage ledger、state、legacy Bonsai test | 全件成功 | 146 passed |
| lock・lint・format | 標準offline gate | 終了0 | lockは72 packages、Ruff check成功、149 files already formatted |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | liveを実行せず全件成功 | 1060 passed / 1 deselected |
| 文書・差分 | local Markdown link・anchor・fence、Python 3.10 AST、agents-setup、`git diff --check` | 欠落・構文・whitespace error 0件 | 現行Markdown 16件、local link 708件、heading 957件、fence 195件、Python 3.10 AST 149件、テンプレート接頭辞・目次・安全規則・差分error 0件 |
| live・UI | 実Bonsai、credential、外部通信、browser、委託フロントエンド | 本Planでは実行しない | 対象外 |

### セキュリティ・データ・互換性

- adapterはEXEC-012のcredential-free headerだけを受け付け、環境proxy、`.netrc`、環境CA、既定Session header・cookieを利用しない。bodyやresponseをlog、例外、永続modelへ含めない。
- HTTPはloopback address、HTTPSはcanonical hostという既存endpoint policyを再検証する。redirect先へbodyを再送せず、TLS検証を無効化しない。
- Content-Lengthとstream実測の両方で1 MiBを上限とし、不正metadataや上限超過をfail closedにする。responseとsessionは成功・失敗の両方で閉じる。
- 現行legacy clientとpipelineを変更しない。新adapterは注入可能な部品として未接続のまま追加するため、利用者画面、cache、保存形式の移行はない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-03 | 既存依存のRequestsを使い、呼出しごとに新規Sessionを作って閉じる | 現行依存でProtocolを満たし、cookie・connection・設定をattempt間で共有しないため | connection pool共有が必要になった場合はowner・lifecycle・並行安全性を別途設計する |
| 2026-09-03 | `trust_env=False`、既定header・cookie・proxy除去、TLS検証有効を固定する | request digest外のproxy、`.netrc`、CA、送信metadataを混入させないため | 認証または管理proxyが必要なら、credential受渡しと送信先を別の明示Planで設計する |
| 2026-09-03 | HTTP adapterのretryを0にし、redirectも追わない | EXEC-012の1予約・1 transport callを複数の隠れたHTTP attemptへ膨らませないため | TD-005を扱う際はattempt単位の予約・上限・再承認を設計する |
| 2026-09-03 | 応答は上限内で読んだbyte chunkだけを `BonsaiHttpResponse` へ投影し、Requests Response自体を返さない | 接続資源をtransport内で確実に閉じ、上位層へnetwork objectや生header全体を漏らさないため | 大きな応答を逐次parseする要件が生じた場合にownership契約を見直す |

### 発見事項

- 最初の実装後はfocused 30件中29件が成功し、統合fixtureだけが入力に存在しない `Sony` を期待して失敗した。既存normalizerは根拠のないbrandを意図どおり除去していたため、production codeや期待値を弱めず、fixtureのsource inputへbrand根拠を追加した。
- Requests 2.34.2の実PreparedRequestを外部送信前で捕捉し、既定User-Agent、cookie、Authorization、proxyがなく、固定3 headerと自動Content-Length、exact bodyだけになることを確認した。

### ロールバック

`src/search_v2/bonsai_http.py`、focused test、本Planに伴う標準文書の追記だけを取り除けばEXEC-012完了時点へ戻せる。現行client、pipeline、外部状態、credential、保存データ、委託フロントエンドを変更しないため、外部状態やデータ移行のrollbackはない。

### 結果

`src/search_v2/bonsai_http.py` に、EXEC-012のcanonical endpoint・header・body・timeout・encoding・response上限を再検証して1回だけPOSTする `RequestsBonsaiTransport` を実装した。新規Sessionの環境連携、既定metadata、cookie、proxy、authを除去し、TLS検証有効、HTTP/HTTPS retry 0、redirect禁止、connect/read timeout、streaming 1 MiB上限を固定した。応答は限定metadataと上限内のbyte列だけへ投影し、ResponseとSessionを全経路で閉じる。

module SHA-256は `725be374c34ddfbf5579d3fa2327468529450e398f79086ec1a8bab1465bbab0`、最終test SHA-256は `457768048d5c2b35f5d7131b2e65b4d163db577b29dd6dac46d8462e6d272236` である。focused 32件、関連146件、offline全体1060件、lock、Ruff、文書・構文・差分検査が成功した。Requests通信はすべてmockであり、実Bonsai、credential、課金、model品質、現行pipeline、cache、API、browser、委託フロントエンドは実行・接続していない。

次の通常ローカル作業は新しい `EXEC-015` を作成し、本Planの完了出力を `product_normalization.py` と `ranking.py` へ結ぶ後半pipelineと、成功・失敗・0件を表す検索stateをoffline TDDで実装する。実Outscraper通信、credential実値、課金、フロントエンド確認・接続は引き続き対象外にする。


## EXEC-014: Outscraper v2 HTTP・task・polling境界

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-03
- 最終更新日: 2026-09-03
- 前提: [EXEC-008](#exec-008-outscraper複数query-requestと明示承認guard)、[EXEC-013](#exec-013-bonsai-v2-http-transport)
- 関連要件: [FR-406・FR-407](REQUIREMENTS.md#35-次期検索フロー-v2)、[SEC-010・SEC-011](REQUIREMENTS.md#6-セキュリティ要件)
- 関連負債: [TD-001](ISSUES.md#td-001-同期的な検索実行)、[TD-003](ISSUES.md#td-003-アクセス制御と利用量制御)、[TD-004](ISSUES.md#td-004-観測可能性とログ管理)
- 公式仕様: [Amazon Products API](https://docs.outscraper.com/endpoints/amazon-products/)、[Request Results API](https://docs.outscraper.com/endpoints/requests-requestid/)

### 目的

第2確認でsingle-useに承認され、1 callのOutscraper利用量を開始済みにした `AuthorizedOutscraperRequest` だけを、実HTTP adapterが実行できる境界を作る。利用者が将来観察できる結果は、承認済み日英queryを1回の非同期GETでtask作成し、同じprovider request IDの安全な結果URLだけを上限回数までpollし、正常な0件を含む完了応答を後段の決定的normalizerへ渡せることである。

本PlanではRequests Sessionとsleepをmockし、外部通信なしでendpoint、反復query、server-side API key header、TLS、no-proxy、no-redirect、no-retry、timeout、poll上限、応答byte上限、strict JSON、利用量の成功・失敗確定を検証する。これは実Outscraper、Amazon商品取得、課金、現行pipeline、browserまたはproduction E2Eの成功を意味しない。

### 対象範囲

- `src/search_v2/outscraper_http.py` のHTTP response投影、Requests transport、task実行境界
- `AuthorizedOutscraperRequest`、開始済み1-call予約、同一process利用量ledgerの再検証
- 承認済みの反復 `query`、`domain`、`language`、`postal_code`、`limit`、`async` をそのまま1回のGETへ渡すserializer境界
- 呼出しごとの新規Session、`trust_env=False`、既定header・cookie・proxy・authの除去、TLS検証、HTTP/HTTPS retry 0、redirect禁止
- server-sideから渡されたAPI keyを `X-API-KEY` だけに注入し、queryまたは結果へ保持しない境界
- 固定30秒request timeout、固定30秒poll間隔、最大50 poll、自動HTTP retryなし、各1回のGETに固定8 MiB応答上限
- `Content-Type`、`Content-Encoding`、`Content-Length`、実読込みbyte数、UTF-8、duplicate JSON key、非有限数のfail-closed検証
- `Pending`、`Success`、`Failure`、正常0件、不明status、待機超過の分類
- `results_location` のcanonical HTTPS、承認endpointとの同一origin、exact `/requests/{provider_request_id}`、poll応答ID一致
- 通信・HTTP・セキュリティ・応答・task失敗・待機超過を生データのない固定エラーへ分離する境界
- Requestsとsleepをmockしたoffline TDD、既存request・approval・usage・normalizerとの関連回帰、標準文書の同期

### 対象外

- 実Outscraper、Amazon、localhost、任意hostへのDNS・TLS・HTTP通信
- 実API keyの読込み・表示・保存、外部送信、課金、live API、service品質の確認
- HTTP 429・5xx・transport失敗の自動再試行、`Retry-After`、backoff。task作成の再実行は新しい承認と利用量予約を必要とする別Planへ残す
- 現行 `src/clients/outscraper_client.py`、`src/config.py`、cache、`run_product_search()`、Streamlit、CLIの変更・置換
- v2商品normalizer・rankingとのproduction pipeline接続、`scrape_pending` 以降のstate、永続repository、API、履歴
- Cloudflare HTTP・画像応答、実画像proxy transport、実CLIP encoder・model asset
- 外部委託中の次期フロントエンドの内容確認、レビュー、起動、テスト、接続
- AIレビューハーネスのCLI、policy、Runbook、配備またはlive実行

### 現在の文脈

- `outscraper_request.py` は日英最大2 queryと固定parameterのcredential-free descriptorを作り、request・query plan・承認・owner・session・期限・single-use token・開始済み1 call予約を検証したpermitを返す。HTTPとAPI keyは持たない。
- `usage_ledger.py` は開始済みattemptを成功または失敗で必ず確定し、どちらも上限集計へ残す。permit発行時点で予約は開始済みである。
- `product_normalization.py` は `data` list、request descriptor、provider request IDを受け、最大48候補を観測値だけで正規化できる。HTTP実行とprovider responseの完了検証は行わない。
- Outscraper公式資料はAmazon Productsの `query` 反復batch、`async=true`、作成応答の `id`・`Pending`・`results_location`、Request Resultsの `Pending`・`Success`・`Failure`を示す。表示endpointの `.com` と例の `.cloud` に不一致があるため、現行の `.cloud` を維持し、permitに固定したexact endpointからoriginを決める。
- Requestsは既存依存であり、新しいpackageは追加しない。通常pytestはsocketと主要DNS経路を遮断し、本PlanはさらにSessionをmockする。

### 実行手順

1. Planを登録し、公式Amazon Products・Request Results、既存descriptor・permit・usage・normalizer・legacy clientの境界を確認する。
2. exact GET、API keyのheader限定、環境分離、no-retry・no-redirect、TLS、response cap、strict JSON、Session・Response closeのRED testを追加する。
3. immediate success、pendingからのpoll success、正常0件、task failure、unknown status、results URL・ID改ざん、poll超過、利用量確定のRED testを追加する。
4. テストfileのSHA-256を固定し、production module不在によるREDを期待した理由で確認する。
5. Requests transportとtask実行境界を最小実装し、focused testをGREENにする。
6. v2 request・approval・usage・normalizer、legacy Outscraper、characterizationの関連回帰を確認する。
7. offline全体、lock、Ruff、Markdown・Python 3.10構文・agents-setup・差分検査を実行する。
8. 要件、backend、security、課題、参照、履歴、利用者向け残作業、次の再開位置を同期する。

### 進捗

- [x] 2026-09-03: `AGENTS.md`、`DEVELOPMENT.md`、EXEC-008・013、既存Outscraper request・permit・usage・normalizer・legacy clientを確認した。
- [x] 2026-09-03: 公式Amazon Products・Request Resultsで反復query、非同期task、result status、request ID・URLの現行形状を確認した。実APIは呼び出していない。
- [x] 2026-09-03: 本Planを登録し、実通信、credential実値、自動再試行、現行pipeline、委託フロントエンドを対象外に固定した。
- [x] 2026-09-03: RED testを追加した。test SHA-256は `b343a82ae1166c9b125e3555b6d49609861da2cf8231085892e89f9857a5a664` で、production module不在によるcollection errorとなった。
- [x] 2026-09-03: Requestsのstreaming検査とduplicate JSON検査が別の失敗に吸収されないようRED testを補正した。補正後SHA-256は `846e4343cce32c7b25f5fc3b10c8a40ffb56f51b5e29166766d26f521631b04b` で、production module不在の同じcollection errorを再確認した。
- [x] 2026-09-03: `outscraper_http.py` にexact GET、隔離Session、bounded response、strict task・polling、利用量確定を実装し、focused test 50件をGREENにした。module SHA-256は `51d652b56d792143ee4a64b6385d88bf0a82ae2d5793a684338e82029683148e`、最終test SHA-256は `01f9fc8791b4003b0bc4dda490a6c4dea7520dbc3c88c7d16f9ee0302b6571b9` である。
- [x] 2026-09-03: request・approval・usage・normalizer・ranking、legacy Outscraper、characterizationの関連回帰201件と、offline全体1110件を完了した。
- [x] 2026-09-03: 標準文書と利用者向け残作業を同期し、次の再開位置をEXEC-015の後半pipeline・検索stateへ更新した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_outscraper_http.py` | 本Planの境界が未実装のため期待した理由で失敗 | 終了2。`ModuleNotFoundError: No module named 'src.search_v2.outscraper_http'` によるcollection error。初回test SHA-256は `b343a82ae1166c9b125e3555b6d49609861da2cf8231085892e89f9857a5a664`。stream・JSON検査の意図を補正したSHA-256 `846e4343cce32c7b25f5fc3b10c8a40ffb56f51b5e29166766d26f521631b04b` でも同じ期待理由を再確認 |
| focused GREEN | REDと同じtest file | 全件成功 | 50 passed |
| 関連回帰 | Outscraper request・approval・usage・normalizer・ranking、legacy client、characterization | 全件成功 | 201 passed |
| lock・lint・format | 標準offline gate | 終了0 | lock成功、Ruff check成功、151 files already formatted |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | liveを実行せず全件成功 | 1110 passed / 1 deselected |
| 文書・構文・差分 | local Markdown link・anchor・fence、Python 3.10 AST、agents-setup、`git diff --check` | 欠落・構文・whitespace error 0件 | 現行Markdown 16件、local link 727件、anchor 972件、fence 195件、Python 3.10 AST 151件、14,087-byte template接頭辞、目次、安全規則、diff check成功 |
| live・UI | 実Outscraper、credential、課金、browser、委託フロントエンド | 本Planでは実行しない | 対象外 |

### セキュリティ・データ・互換性

- API keyは実行時の非保存引数からfixed headerへだけ注入し、request model、permit、URL、query、戻り値、repr、log、例外、文書へ入れない。
- SessionはHTTP要求1件ごとに作って閉じ、cookie、proxy、`.netrc`、環境CA、既定header、connection stateをtask作成とpoll間で共有しない。TLS検証を無効化しない。
- 承認済みendpointと反復parameterを送信直前に再検証する。provider由来URLはcanonical HTTPS、same origin、exact request ID pathを満たすまでAPI keyを送らない。
- 外部応答は最大8 MiBをstream読込みし、不正header、圧縮、超過、非UTF-8、重複key、非有限数、不明statusをfail closedにする。生の失敗応答とURLを例外へ保持しない。
- permit発行時点の開始済み予約は、HTTP送信、response検証、task失敗、poll超過の成否にかかわらず `succeeded` または `failed` へ確定する。失敗予約も上限集計へ残す。
- 現行client・pipeline・cacheは変更せず、新境界は未接続の部品として追加する。データ移行は発生しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-03 | HTTP要求1件ごとに新規Requests Sessionを作成し、adapter内で必ず閉じる | providerがcookieやconnection状態を返しても次のpollへ非承認metadataを引き継がないため | connection pool共有が必要なら、cookie禁止・lifecycle・並行安全性を別Planで設計する |
| 2026-09-03 | v2のHTTP自動retryを0に固定し、通常pollだけを最大50回許可する | task作成GETを隠れて再実行すると、1回の承認・利用量予約と実provider attemptが一致しなくなるため | 再試行を導入する場合は新しい承認、予約、idempotency仕様と同時に設計する |
| 2026-09-03 | timeout 30秒、poll間隔30秒、最大50 poll、各応答8 MiBを実装定数にする | 現行の安全側既定値を維持し、permit digestに含まれない実行値をcallerが拡大できないようにするため | runtime policyを可変にするときはapproval planとpolicy digestへ結ぶ |
| 2026-09-03 | `results_location` をsame originだけでなくexact `/requests/{id}` へ限定する | provider由来URLを使ったAPI keyの同一host内の別endpointへの送信を防ぎ、poll応答を初回task IDへ結ぶため | 公式APIが結果pathを変更した場合は、公式仕様・許可path・テストを同時に更新する |
| 2026-09-03 | task失敗、不正response、timeoutの例外にprovider文、query、URL、API keyを含めない | 外部文と利用者入力をlogや通常画面へ流さないため | 診断metadataを追加する場合は別のallowlist型内部modelと保持方針を作る |

### 発見事項

- Outscraper公式Amazon Products pageは本文のendpointに `api.outscraper.com`、cURL例と非同期応答に `api.outscraper.cloud` を示す。既存の承認済み `.cloud` 既定値を変更せず、実行時もdescriptorのexact endpointを使う。
- 公式APIは最大1,000 queryのbatchを許容するが、本プロダクトの承認・費用・最大候補境界は日英最大2 query、24件/queryのまま維持する。

### ロールバック

`src/search_v2/outscraper_http.py`、対応focused test、本Planに伴う標準文書の追記だけを取り除けばEXEC-013完了時点へ戻せる。現行client、pipeline、cache、credential、外部service、委託フロントエンドを変更しないため、外部状態・保存データのrollbackはない。

### 結果

完了。承認済みpermitと開始済み1-call予約に結ばれたOutscraper task作成、same-origin・same-IDの結果polling、strict response、固定エラー、利用量成功・失敗確定をRequests通信mockで実装した。focused 50件、関連201件、offline全体1110件、lock、Ruff、文書・Python 3.10構文・agents-setup・差分検査が成功した。

実Outscraper、credential、課金、実Amazon候補、現行pipeline、cache、API、browser、委託フロントエンドは実行・接続していない。次は新しい `EXEC-015` で、本Planの完了結果を商品正規化・rankingへ渡す後半pipelineと、成功・失敗・0件を扱う検索stateをoffline TDDで実装する。


## EXEC-015: 検索後半pipelineと完了state

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-03
- 最終更新日: 2026-09-03
- 前提: [EXEC-009](#exec-009-決定的商品正規化と未知属性境界)、[EXEC-011](#exec-011-決定的ランキングv2とスコア内訳)、[EXEC-014](#exec-014-outscraper-v2-httptaskpolling境界)
- 関連要件: [FR-407・FR-409・FR-410](REQUIREMENTS.md#35-次期検索フロー-v2)、[NFR-004・NFR-205](REQUIREMENTS.md#8-非機能要件)
- 関連負債: [TD-001](ISSUES.md#td-001-同期的な検索実行)、[TD-004](ISSUES.md#td-004-観測可能性とログ管理)、[TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

承認済みOutscraper要求の検証済み完了結果を、観測値だけの商品正規化と固定ranking v2へ一続きに渡す。利用者が将来観察できる後半状態として、商品受信、正規化、結果ありの正常完了、正常0件、固定コードの失敗を明確に区別する。

本Planは完了済みexecution objectとfixtureだけを使うoffline domain実装である。実Outscraper、実Amazon商品、検索品質、永続化、API、browser、production E2Eの成功を意味しない。

### 対象範囲

- `src/search_v2/state_machine.py` の `scrape_submitted` 以降の受信・正規化・完了・失敗stateと、revision付き遷移
- 受信候補数、正規化・除外・ランキング件数、正規化・ranking batch digest、正常結果種別、失敗工程・固定コードの整合性検証
- `src/search_v2/product_pipeline.py` のexecution・承認plan・intent・query・利用量・runtime profileの結合再検証
- `normalize_outscraper_products()` と `rank_product_batch()` の順序付き実行、結果ありと0件の完了result
- provider実行失敗を生例外文なしの `product_search_failed` として記録する独立遷移
- focused・関連・offline全体テスト、標準文書と再開位置の同期

### 対象外

- 実Outscraper、Amazon、Bonsai、Cloudflare、localhostまたは任意hostへのDNS・TLS・HTTP通信
- API key、credential実値、実利用者入力、外部送信、課金、live APIの確認
- 現行 `run_product_search()`、cache、Streamlit、CLI、新規API、バックグラウンドjob、永続repository、履歴保存
- 実CLIP asset・encoder・推論、画像ranking weightの有効化、代表fixtureによるranking品質評価
- 外部委託中で未納品の次期フロントエンドの内容確認、レビュー、起動、テスト、バックエンド接続
- AIレビューハーネスの設定、CLI、policy、[HARNESS-RUNBOOK.md](HARNESS-RUNBOOK.md)、配備、live実行

### 着手時の文脈

- `outscraper_http.py` は承認permitと開始済み利用量を再検証し、正常完了時だけ `OutscraperProductExecution` を返す。その中のresponseは `data` だけに限定され、利用量は `succeeded` である。
- `product_normalization.py` はrequest・query・provider request ID・換算profileへ結び付いたstrict batchを返し、各入力候補を正規化済み商品または固定reject理由のどちらかに分類する。
- `ranking.py` はintent・query・normalized batch・固定profileを再検証し、画像成分無効のstable rankingとscore breakdownを返す。
- 着手時点の `SearchSessionSnapshot` は `scrape_submitted` で止まり、生response、normalized batch、ranked batch、正常完了、0件、失敗を保持しなかった。

### 実行手順

1. 本Planを登録し、EXEC-009・011・014、state machine、要件、検索フローの境界を確認する。
2. 結果あり、0件、全候補reject、不正結合、古いrevision、各失敗工程、生response非保持のRED testを追加する。
3. test fileのSHA-256を固定し、未実装moduleまたは未実装stateによる期待したREDを確認する。
4. stateと遷移を追加し、executionから正規化・rankingまでの最小pipelineを実装する。
5. focused testをGREENにし、state・Outscraper・normalizer・rankingの関連回帰を確認する。
6. lock、Ruff、offline全体、Markdown・Python 3.10構文、agents-setup、差分検査を実行する。
7. 要件、backend、schema、security、課題、履歴、利用者向け残作業、次の再開位置を同期する。

### 進捗

- [x] 2026-09-03: `AGENTS.md`、`DEVELOPMENT.md`、EXEC-009・011・014、現行state・execution・normalizer・ranking・要件・検索フローを確認した。
- [x] 2026-09-03: 本Planを登録し、実通信、credential、課金、永続化、現行UI、委託フロントエンド、HARNESS-RUNBOOKを対象外に固定した。
- [x] 2026-09-03: 受入testを追加し、test SHA-256 `1e5c72e52753a07be9f86ad8585c13d6773bafdc7353164c6248e5ec36f07a98` でproduction module不在による期待したTDD REDを確認した。
- [x] 2026-09-03: 後半stateとpipelineを実装し、focused 21件、関連203件、offline全体1123件をGREENにした。
- [x] 2026-09-03: 標準文書と再開位置を同期し、次をCloudflare HTTP・応答・画像正規化のoffline境界とした。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_product_pipeline.py` | 本Planの境界が未実装のため期待した理由で失敗 | 終了2。`ModuleNotFoundError: No module named 'src.search_v2.product_pipeline'` によるcollection error。test SHA-256は `1e5c72e52753a07be9f86ad8585c13d6773bafdc7353164c6248e5ec36f07a98` |
| focused GREEN | REDと同じtest fileと `tests/test_search_v2_state_machine.py` | 全件成功 | 21 passed |
| 関連回帰 | state、承認・利用量、Outscraper request・HTTP、product normalization、ranking、legacy client・pipeline、characterization | 全件成功 | 203 passed |
| lock・lint・format | 標準offline gate | 終了0 | lock成功、72 packages。Ruff check成功。format check成功、153 files already formatted |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | liveを実行せず全件成功 | 1123 passed、1 deselected |
| 文書・構文・差分 | local Markdown link・anchor・fence、Python 3.10 AST、agents-setup、`git diff --check` | 欠落・構文・whitespace error 0件 | Markdown 16件・link 743件・heading 988件・fence 195件、Python 3.10 AST 153件、14,087-byte template接頭辞、AGENTS安全見出し・目次、差分検査に成功 |
| live・UI | 実provider、credential、課金、browser、委託フロントエンド | 本Planでは実行しない | 対象外 |

### セキュリティ・データ・互換性

- pipelineは承認plan、session、intent、query plan、Outscraper request、成功済み利用量、normalization・ranking profileの結合を実行前に再検証し、差替えを固定エラーで拒否する。
- session stateには数、digest、結果種別、失敗工程・コードだけを持たせ、API key、query本文、postal code、provider response、商品本文、URL、生例外文を保持しない。
- 商品本文を持つnormalized・ranked batchはpipeline resultに分離し、reprに露出させない。永続化・保持期限・owner認可は後続Planで決定する。
- 既存snapshot constructorは後半fieldの安全な既定値で互換性を維持する。保存schemaと現行cacheは変更しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-03 | `SearchSessionSnapshot` に `products_received`、`products_normalized`、`search_completed`、`search_failed` と有界metadataを追加する | 既存の承認・revision・owner・sessionを維持しながら `scrape_submitted` 以降を再開可能な状態にするため | 永続jobに接続する場合はCAS、transaction、migrationを別Planで追加する |
| 2026-09-03 | provider実行失敗、正規化失敗、ranking失敗は工程と固定コードだけを記録する | 外部文、入力、stack trace、内部例外を利用者状態やlogへ流さないため | 診断情報が必要な場合はallowlist済み内部eventと保持方針を別途設計する |
| 2026-09-03 | pipeline resultは正常結果、0件、失敗を一つのstrict contractで区別する | 0件を例外へ変換せず、後続API・履歴境界が種別に応じて扱えるようにするため | 履歴保存は正常結果と0件だけを対象にし、失敗は保存しない |

### 発見事項

- なし。発見時に追記する。

### ロールバック

`src/search_v2/product_pipeline.py`、後半state field・遷移、対応focused test、本Planに伴う標準文書の追記だけを取り除けばEXEC-014完了時点へ戻せる。現行pipeline、cache、credential、外部service、委託フロントエンドを変更しないため、外部状態・保存データのrollbackはない。

### 結果

完了。`state_machine.py` を商品受信、正規化、検索完了、工程別固定失敗まで拡張し、`product_pipeline.py` で成功済みOutscraper executionから観測値だけの商品正規化、画像無効のranking、結果あり・正常0件までを結んだ。final SHA-256はstate machine `6dcaf952c40eff034e9c3b08e3dbd5c7449c9d3c6603adb2b6becd2e78a06a7a`、pipeline `5c21c12350d6fc15567cbf0cc02943cba4edd5323730cb311dd7005b61806e0a`、test `94236f38458831c52d86034e85556078b900f989c9a17d135c22e3bbf716e246` である。

実provider、credential、課金、実Amazon候補、ranking品質、Bonsaiから履歴までの全体orchestration、永続repository、API、browser、外部委託中のフロントエンドは実行・接続していない。次の通常ローカル作業は、新しい `EXEC-016` を登録し、Cloudflare 4方向request descriptorのHTTP応答検証と画像正規化を注入transport・fixtureでoffline TDDする。


## EXEC-016: Cloudflare HTTP応答と画像正規化

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-03
- 最終更新日: 2026-09-03
- 前提: [EXEC-006](#exec-006-2段階承認と費用予約境界)、[EXEC-007](#exec-007-cloudflare-4方向request-builder)
- 関連要件: [FR-403・FR-404・FR-405](REQUIREMENTS.md#35-次期検索フロー-v2)、[NFR-004・NFR-104・NFR-206](REQUIREMENTS.md#8-非機能要件)
- 関連負債: [TD-003](ISSUES.md#td-003-アクセス制御と利用量制御)、[TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

第1確認と開始済み4-call利用量予約に結び付いたCloudflare 4方向request descriptorを、server-side credential注入、multipart HTTP、厳密な応答検証、決定的PNG正規化、利用量確定、`image_review` stateまで一続きにする。基準画像の表示用512px PNGと、派生3要求だけが参照する511px PNGを分ける。

本Planは注入transport、Requests Session mock、合成PNG、fixture JSONだけを使うoffline実装である。実CloudflareのDNS、TLS、HTTP、credential、課金、生応答または生成品質を確認したことにはしない。

### 対象範囲

- `src/search_v2/cloudflare_http.py` のexact Workers AI endpoint、server-side account ID・API token検証、multipart POST transport
- 新規Requests Session、環境proxy・`.netrc`・既定header・cookieの除去、TLS検証、redirect・retry禁止、固定timeout、streaming応答上限
- HTTP 200、JSON content type、identity encoding、UTF-8、duplicate key・非有限数拒否、exact Cloudflare envelope、canonical Base64のfail-closed検証
- 単一frameの512×512 PNG decode、decompression bomb、宣言・実測byte、pixel、metadata除去、RGB PNG再encodeの正規化
- 基準画像から511×511の共有参照PNGを作り、基準、左、右、背面の固定順で4 callsだけを実行する境界
- 開始済み利用量予約の現行ledger内binding、intent・query・attempt・stateの再検証、全成功時だけの `succeeded` と `image_review` 遷移
- 途中失敗時の一部結果非返却、開始済み予約の `failed` 確定、credential・生応答・生provider文の非保持
- focused・関連・offline全体testと、標準文書・再開位置の同期

### 対象外

- 実Cloudflare APIへのDNS・TLS・HTTP通信、account resource取得、credential読取り、外部送信、課金、quota確認
- 実生成画像の同一性・仕様正確性・seed再現性・視覚品質の評価
- 部分成功画像の採用、1枚だけの再生成、自動retry、並列送信、バックグラウンドjob、永続repository、object storage
- 実CLIP asset・encoder・推論、画像ranking weightの有効化、代表fixtureによるranking品質評価
- 現行 `run_product_search()`、cache、Streamlit、CLI、新規APIへの接続
- 外部委託中で未納品の次期フロントエンドの内容確認、レビュー、起動、テスト、バックエンド接続
- AIレビューハーネスの設定、CLI、policy、[HARNESS-RUNBOOK.md](HARNESS-RUNBOOK.md)、配備、live実行

### 着手時の文脈

- `cloudflare_request.py` はexact model、固定512px出力、固定4方向順、attempt別seed、prompt contract、基準画像なしの先頭要求、最大511pxの共有PNGを `input_image_0` に持つ派生3要求を固定している。
- `state_machine.py` は開始済みCloudflare 4-call予約がなければ `image_generating` へ進まず、成功済みの同じ予約がなければ4枚setを `image_review` へ記録しない。
- 公式のmodel資料は `@cf/black-forest-labs/flux-2-klein-4b` の出力をBase64画像文字列とし、公式launch資料はpromptだけでもmultipartが必須、参照入力は512×512未満、最大4枚とする。
- 本Planのexact JSON contractは、公式model output objectとREST API envelopeから `{result:{image},success,errors,messages}` を採用するofflineのfail-closed境界である。実応答による適合は未確認のため、live結合時は実行前に現行公式schemaを再確認する。

### 実行手順

1. 本Planを登録し、EXEC-006・007、state machine、利用量、要件、セキュリティ、公式Cloudflare仕様を確認する。
2. exact multipart、4要求順、511px参照、成功state、HTTP・JSON・Base64・PNGの拒否、中間失敗、secret非露出のRED testを追加する。
3. test fileのSHA-256を固定し、production境界が未実装であることを要求assertionの期待したREDで確認する。
4. 厳密model、Requests transport、response parser、PNG normalizer、4-call orchestrator、ledger・state確定を最小実装する。
5. focused testをGREENにし、Cloudflare request、state、利用量、画像境界の関連回帰を確認する。
6. lock、Ruff、offline全体、Markdown・Python 3.10構文、agents-setup、差分検査を実行する。
7. 要件、backend、schema、security、参照、課題、履歴、利用者向け残作業、次の再開位置を同期する。

### 進捗

- [x] 2026-09-03: `AGENTS.md`、`DEVELOPMENT.md`、EXEC-006・007、現行request・state・利用量・画像境界、要件、検索フローを確認した。
- [x] 2026-09-03: Cloudflare公式のmodel、launch changelog、REST execute、error資料を確認し、実API・account resource・credentialにアクセスせず本Planを登録した。
- [x] 2026-09-03: 60ケースの受入testを追加し、test SHA-256 `3cd90b28fa287a84791a304a8bffee2d16fa6d2f27516c23ff87f7c05242a68d` で、未実装境界を示す期待したrequirement assertionのREDを確認した。
- [x] 2026-09-03: `cloudflare_http.py` にHTTP・応答・画像正規化・4-call実行境界を実装し、module SHA-256を `198b60e6dd835d43865e1f172565bb36960e5fdf3b6454139ded5127f3067e34` に固定した。
- [x] 2026-09-03: focused・関連・offline全体と標準文書同期を完了した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_cloudflare_http.py` | 本Planの振る舞い境界が未実装のため期待した要求assertionで失敗 | 終了1、60 errors。全ケースが `the Cloudflare HTTP response and image normalization boundary is required` の同じrequirement assertionでRED。test SHA-256は `3cd90b28fa287a84791a304a8bffee2d16fa6d2f27516c23ff87f7c05242a68d` |
| focused GREEN | REDと同じtest file | 全件成功 | 60 passed |
| 関連回帰 | Cloudflare request、state、承認・利用量、画像proxy・類似度、ranking | 全件成功 | 198 passed |
| lock・lint・format | 標準offline gate | 終了0 | lock成功、72 packages。Ruff check成功。format check成功、155 files already formatted |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | liveを実行せず全件成功 | 1183 passed、1 deselected |
| 文書・構文・差分 | local Markdown link・anchor・fence、Python 3.10 AST、agents-setup、`git diff --check` | 欠落・構文・whitespace error 0件 | 現行Markdown 16件、local link 755件、heading 1003件、fence 195件、Python 3.10 AST 155件、template接頭辞、AGENTS目次15件・安全規則、diff check成功 |
| live・UI | 実Cloudflare、credential、課金、browser、委託フロントエンド | 本Planでは実行しない | 対象外 |

### セキュリティ・データ・互換性

- account IDとAPI tokenは実行関数からtransportのexact endpoint・Authorization headerへだけ注入し、request、artifact、state、digest、repr、固定例外へ保持しない。
- promptだけの先頭要求もmultipartとし、`Content-Type` のboundaryはRequestsに生成させる。応答は4 MiB、decode後PNGは2 MiB、512×512×1 frameへ固定する。
- 4 callsは自動retryせず固定順に実行する。1件でも失敗した場合は一部artifactを返さず、開始済み予約を `failed` としてattemptを戻さない。
- 正規化後artifactは角度、attempt、request SHA-256、PNG SHA-256、byte数、寸法だけをserializeし、画像byteを除外する。永続保存とbrowser向け表示modelは後続Planで分離する。
- 既存のrequest・state・ledger schemaと現行cacheは変更しない。新しいexecution objectは同一process内の一時artifactである。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-03 | 先頭のprompt-only要求もRequestsのmultipart fieldで送る | 現行公式launch資料がmultipartを必須とするため | 任意のboundaryを手作業で付けず、Requests生成値を使う |
| 2026-09-03 | 表示用512px基準画像と派生入力用511px参照を分ける | 固定512px出力と、参照入力を512×512未満とする公式制約を同時に守るため | 参照変換はpinned Pillow runtimeで決定的に行い、request set digestへ結ぶ |
| 2026-09-03 | 4枚を逐次・全件成功の単位とし、自動retryしない | 基準画像が派生3枚の入力であり、provider call数と失敗attempt計上を曖昧にしないため | 並列化・部分成功・retryは新しい予約・state契約を設計した場合だけ見直す |
| 2026-09-03 | 公式output objectとREST envelopeを組み合わせたexact JSONだけをofflineで受理する | 生provider文や曖昧な代替shapeを後段へ流さず、未確認の部分を明示するため | 別承認のlive結合で公式schemaと異なることが確認されたら、fixtureとcontractを根拠付きで更新する |

### 発見事項

- 既存の利用量・state契約では、第1確認が開始済み予約を受け取った時点で1組目または2組目のattemptが開始する。実行境界は新しい予約を作成・開始せず、そのexact予約を成功または失敗へ確定する。

### ロールバック

`src/search_v2/cloudflare_http.py`、対応focused test、本Planに伴う標準文書の追記だけを取り除けばEXEC-015完了時点へ戻せる。現行pipeline、cache、credential、外部service、委託フロントエンドを変更しないため、外部状態・保存データのrollbackはない。

### 結果

完了。開始済み4-call予約と `image_generating` stateへ結び付くCloudflare Requests transport、厳密な応答・Base64・PNG検証、表示用512px画像と派生用511px参照、全件成功時だけの利用量・`image_review` 確定を実装した。final SHA-256はmodule `198b60e6dd835d43865e1f172565bb36960e5fdf3b6454139ded5127f3067e34`、test `3cd90b28fa287a84791a304a8bffee2d16fa6d2f27516c23ff87f7c05242a68d` である。

検証はmock transport、Requests Session mock、fixture JSON、合成PNGだけで行った。実Cloudflare、credential、課金、生応答、生成画像品質、実CLIP、永続repository、API、browser、外部委託中のフロントエンドは実行・接続していない。次の通常ローカル作業は `EXEC-017` を新規作成し、既存のBonsai、確認、任意画像、Outscraper、商品正規化、ranking、完了stateを一つのofflineバックエンドorchestrationへ接続する。


## EXEC-017: offline検索orchestration

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-03
- 最終更新日: 2026-09-03
- 前提: [EXEC-012](#exec-012-bonsai-v2-requestと実行境界)、[EXEC-014](#exec-014-outscraper-v2-httptaskpolling境界)、[EXEC-015](#exec-015-検索後半pipelineと完了state)、[EXEC-016](#exec-016-cloudflare-http応答と画像正規化)
- 関連要件: [FR-401からFR-410](REQUIREMENTS.md#35-次期検索フロー-v2)、[SEC-010・SEC-011](REQUIREMENTS.md#6-セキュリティ要件)、[NFR-004・NFR-206](REQUIREMENTS.md#8-非機能要件)
- 関連負債: [TD-001](ISSUES.md#td-001-同期的な検索実行)、[TD-003](ISSUES.md#td-003-アクセス制御と利用量制御)、[TD-004](ISSUES.md#td-004-観測可能性とログ管理)

### 目的

既存のBonsai意図抽出、決定的query plan、第1確認、任意のCloudflare 4方向画像、第2確認、single-use承認、Outscraper、商品正規化、ranking、完了stateを、一つの同一process用バックエンド境界へ接続する。利用者操作に対応する確認点では処理を明示的に停止し、画像OFFではCloudflareを、最終承認前はOutscraperを呼ばない。

利用者が将来観察できる結果は、条件整理後、画像確認後、検索内容確認後の各状態を別々に受け取り、最後の明示承認後だけ商品検索を開始できることである。本Planは注入transport、fixture応答、合成PNGだけを使うoffline実装であり、実サービス、credentialの有効性、課金、画面、永続化またはproduction E2Eを確認したことにはしない。

### 対象範囲

- `src/search_v2/orchestrator.py` のstrictなbackend policy、意図確認、画像確認、最終検索確認の一時stage
- Bonsai要求の構築、利用量予約、注入transportによる1回実行、query plan、`intent_review` stateまでの接続
- 第1確認で画像OFFを選んだ場合のCloudflare 0 callと、画像ONを選んだ場合の4-call予約・生成・`image_review` state
- 成功した4枚の一括再生成を最大2組へ制限する既存state・利用量境界の接続
- 生成済み画像を採用する経路と、生成後に画像を使わず進む経路
- exact Outscraper request、provider別allowance、runtime bindingを持つ15分の最終確認plan作成と、確認段階でOutscraperを呼ばない境界
- 最終承認tokenの非serialize・非repr保持、承認発行後のOutscraper 1-call予約、single-use claim、task実行、後半pipelineへの接続
- Outscraper実行失敗を生provider文なしの `product_search_failed` stateへ確定する処理
- 予約・stage・plan・owner・session・digest・revisionの再検証、mock・fixtureだけのTDD、関連回帰、標準文書の同期

### 対象外

- 実Bonsai、Cloudflare、Outscraper、Amazonまたは任意hostへのDNS・TLS・HTTP通信
- 実credentialの読込み、有効性確認、外部送信、課金、quota、live API、生成・検索・ranking品質評価
- 現行 `run_product_search()`、cache、Streamlit、CLI、新規HTTP API、background jobへの接続
- 複数process・host・再起動をまたぐ承認・利用量の原子性、永続repository、検索履歴、30日保持、認証・認可
- Cloudflare生成が途中失敗した後の再開state、自動retry、部分画像採用、1枚だけの再生成
- 実画像proxy transport、実CLIP asset・encoder・推論、画像ranking weightの有効化
- 外部委託中で未納品の次期フロントエンドの内容確認、レビュー、起動、テスト、変更、バックエンド接続
- AIレビューハーネスの設定、CLI、policy、[HARNESS-RUNBOOK.md](HARNESS-RUNBOOK.md)、配備、live実行

### 着手時の文脈

- 各providerのrequest・HTTP・response境界、承認state、利用量ledger、商品正規化・ranking・後半pipelineは個別に存在するが、Bonsaiから検索完了までを結ぶ呼出し元は存在しない。
- state machineは `intent_review`、`image_review`、`search_approval` で停止できる。Outscraper permitはexact requestをtoken claim前に検査し、開始済み予約が承認発行より後でなければ拒否する。
- `SearchApprovalPlan` はBonsai、Cloudflare、Outscraperのallowance、Bonsai・画像・ranking・実装・利用policyのdigestを保持する。画像OFF時はCloudflare allowanceとruntime bindingを0・なしにする。
- 現行の画像成功stateからは画像を採用して進める遷移だけがあり、`SEARCH-FLOW.md` が定める「参考画像を使わない」操作を表す遷移は不足している。
- 承認・利用量ledgerはin-memoryで同一processだけがatomicであり、browserから渡されたsnapshotを信用する公開APIにはできない。

### 実行手順

1. 本Planを登録し、既存request・state・承認・利用量・provider・後半pipelineの入出力と確認停止点を固定する。
2. 画像OFF・ON・一括再生成、生成後の画像破棄、最終承認前0 call、single-use、Outscraper失敗state、secret・生body非保持のRED testを追加する。
3. test fileのSHA-256を固定し、orchestration module不在による期待したREDを確認する。
4. 既存境界を順に呼ぶ最小orchestratorと、画像破棄のstate遷移を実装する。外部clientや再試行処理は追加しない。
5. focused testをGREENにし、承認・state・利用量・各provider・正規化・ranking・現行検索の関連回帰を確認する。
6. lock、Ruff、offline全体、Markdown・Python 3.10構文、agents-setup、差分検査を実行する。
7. 要件、backend、schema、security、課題、履歴、利用者向け残作業、次の再開位置を現行結果へ同期する。

### 進捗

- [x] 2026-09-03: `AGENTS.md`、`DEVELOPMENT.md`、EXEC-012・014・015・016、既存request・state・承認・利用量・provider・後半pipelineを確認した。
- [x] 2026-09-03: 本Planを登録し、確認の自動通過、実通信、credential、課金、永続化、API、委託フロントエンド、HARNESS-RUNBOOKを対象外に固定した。
- [x] 2026-09-03: 12ケースのoffline orchestration RED testを追加した。初回test SHA-256は `c1903e12b58bc0c5329e059a4a3579f2b33a9aae7b7b3a68abc8474e06c43051`。nested modelの改ざんfixtureとimport検査だけを補正し、受入assertionを維持したSHA-256 `fe27b855fdbabe5181297b7c407687a97647945b1f53f20e56cc3844dbaa7c79` でも、module不在を示す同じrequirement assertionによる12 errorsを再確認した。
- [x] 2026-09-03: `orchestrator.py` と画像破棄遷移を実装し、14件のfocused test、528件の関連回帰、1197件のoffline全体をGREENにした。
- [x] 2026-09-03: 標準文書、履歴、残作業、次の再開位置を同期し、次をCloudflare生成途中失敗後の回復stateとした。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_orchestrator.py` | orchestration境界が未実装のため期待した理由で失敗 | 終了1、12 errors。全ケースが `the offline search orchestration boundary is required` の同じrequirement assertionでRED。補正後test SHA-256は `fe27b855fdbabe5181297b7c407687a97647945b1f53f20e56cc3844dbaa7c79` |
| focused GREEN | REDと同じtest file、state machine | 全件成功 | 14 passed |
| 関連回帰 | 承認、利用量、Bonsai、Cloudflare、Outscraper、商品正規化、ranking、現行pipeline | 全件成功 | 528 passed |
| lock・lint・format | 標準offline gate | 終了0 | lock成功、Ruff check成功、Ruff format check成功（157 files already formatted） |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | liveを実行せず全件成功 | 1197 passed、1 deselected |
| 文書・構文・差分 | local Markdown link・anchor・fence、Python 3.10 AST、agents-setup、`git diff --check` | 欠落・構文・whitespace error 0件 | 現行Markdown 16件・link 774件・heading 1020件・fence 195件、Python 3.10 AST 157件、14,087-byte template接頭辞、AGENTS目次15件・安全規則、diff check成功 |
| live・UI | 実provider、credential、課金、browser、委託フロントエンド | 本Planでは実行しない | 対象外 |

### セキュリティ・データ・互換性

- stageは既存strict modelとdigestを再検証し、Bonsai source・prompt・request body・response、Cloudflare token・生応答、Outscraper API key・生失敗応答を保持しない。正規化PNG bodyは同一process内だけで使い、serialize・reprから除外する。
- provider credentialは各実行関数の非保存引数から注入transportへだけ渡す。検索承認tokenは専用の非repr objectで一時保持し、stage、plan、state、結果へ保存しない。
- CloudflareとOutscraperの利用量は外部transport呼出し前に予約・開始する。開始後の失敗は返却せず利用量へ残し、自動retryしない。
- 最終確認stageの作成と承認tokenの発行だけではOutscraperを呼ばない。承認発行後にplan digestへ結ぶ予約を開始し、exact request照合とsingle-use claim後だけtransportを呼ぶ。
- 生成後に画像を破棄しても、既に成功したCloudflare予約は利用量ledgerから消さない。最終planは画像OFFとして画像digestを持たない。
- 現行client・pipeline・cache・UIを変更せず、新境界は隔離した同一process用部品として追加する。保存形式の移行と外部状態の変更はない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-03 | orchestrationを一括実行関数にせず、利用者操作ごとのstage関数へ分ける | 第1確認、画像確認、第2確認を自動通過せず、各段階でprovider 0 callを検証できるようにするため | 信頼済みjob runnerへ接続するときも同じ承認境界を維持する |
| 2026-09-03 | provider接続は既存注入transportをそのまま使い、orchestratorへHTTP clientを内蔵しない | 個別のURL・redirect・byte上限・credential境界を重複実装せず、offlineで順序と結合だけを検証するため | 実service adapterは別のlive結合Planで既存Requests transportを注入する |
| 2026-09-03 | 画像を生成後に使わない場合、生成利用量はledgerへ残しつつ最終planを画像OFFにする | 既に始めた課金attemptを戻さず、採用していない画像をOutscraper承認へ結ばないため | 永続利用量repository追加時も破棄済みattemptを監査履歴から削除しない |

### 発見事項

- Cloudflare生成が1件以上始まって失敗した場合、利用量はfailedへ確定できるが、現行stateは `image_generating` から再試行または画像OFFへ進む遷移を持たない。この障害回復は本Planの成功経路から分離し、後続のstate・job recoveryで扱う。

### ロールバック

`src/search_v2/orchestrator.py`、対応focused test、画像破棄のstate遷移、EXEC-017と実装状態を更新した標準文書だけを取り除けばEXEC-016完了時点へ戻せる。現行pipeline、cache、credential、外部service、委託フロントエンドを変更しないため、外部状態・保存データのrollbackはない。

### 結果

完了。`src/search_v2/orchestrator.py` にstrictなpolicyと一時stageを追加し、Bonsaiの1回実行から第1確認、画像OFFまたはCloudflare 4方向生成、最大1回の一括再生成、画像採用・破棄、最終確認、single-use承認、Outscraper、商品正規化、画像無効ranking、結果あり・正常0件・固定失敗までを、確認点ごとに停止する同一process用offline境界へ接続した。`state_machine.py` には、成功済み画像setを使わずに続行しつつ、既に発生した利用量をledgerへ残す `discard_image_set()` を追加した。

RED補正後test SHA-256は `fe27b855fdbabe5181297b7c407687a97647945b1f53f20e56cc3844dbaa7c79`。追加受入条件を含む最終test SHA-256は `ec07fdd39f49315435095e852f5a58ec68491b0f37c7e359c9d63a4681cc86f6`、orchestrator SHA-256は `a69e126798bfb4805cd3f65d7a55b9bde9146d3d1da6c6216a8cf300fe24df1a`、state machine SHA-256は `bb76d3ba97562e6763bc7eb9a4a16c069869e9a638a415a29be6c837004158ae` である。focused 14件、関連528件、offline全体1197件、lock、Ruff、文書・Python 3.10構文・agents-setup・差分検査を確認した。

検証は注入transport、fixture JSON、合成PNGだけで行った。実Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、実Amazon候補、実画像、生成・ranking品質、現行pipeline、永続repository、API、browser、外部委託中のフロントエンドは実行・接続していない。次の通常ローカル作業は新しい `EXEC-018` を作成し、Cloudflare生成が途中失敗した後に、失敗attemptを利用量へ保持したまま4枚一括再試行または画像なし続行を明示選択できる回復stateをoffline TDDする。


## EXEC-018: Cloudflare画像生成失敗後の回復state

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-03
- 最終更新日: 2026-09-03
- 前提Plan: [EXEC-017](#exec-017-offline検索orchestration)
- 関連課題: [TD-010](ISSUES.md#td-010-cloudflare画像生成途中失敗後の回復state)

### 目的

Cloudflareの4方向画像生成が途中で失敗しても、同じ検索sessionを失わず、利用者が「新しい4枚一括attemptを再試行する」または「画像なしで最終確認へ進む」を明示的に選べるようにする。失敗済みattemptは利用量・監査証拠へ残し、選択前にproviderを再呼出ししない。

### 対象範囲

- `image_generating` と失敗済みCloudflare予約を結ぶstrictな回復state
- 初回または一括再生成の途中失敗を回復stageとして返すoffline orchestration
- 最大2組の既存上限内で、新しい4-call予約だけを使う明示的な再試行
- 失敗済みattemptをledgerへ残した画像なし続行
- stale revision、予約ID・owner・session・query・policy・status改ざん、attempt再利用の拒否
- 注入transport、fixture応答、合成PNGだけを使うRED→GREEN回帰

### 対象外

- 自動retry、部分成功した画像の採用、同じreservationの再利用、上限の緩和
- 実Cloudflare、credential、外部送信、課金、生成画像品質の確認
- 永続repository、複数worker、job、API、現行pipelineへの接続
- 外部委託中のフロントエンドの確認、レビュー、起動、テスト、バックエンド接続
- `docs/HARNESS-RUNBOOK.md` の変更とAIレビューハーネスの実行

### 現在の状態

`cloudflare_http.py` は途中失敗時に開始済み4-call予約を `failed` へ確定し、部分画像を返さない。`state_machine.py` はこの予約を `image_generation_failed` とfailed reservation IDへ結び、`orchestrator.py` は固定 `ImageFailureReview` を返す。利用者が別関数を呼ぶまで追加通信せず、最大2組の範囲の新規4-call予約または画像OFFへだけ進める。同一process・offline境界であり、永続化と実provider接続は未実装である。

### 受入条件

1. 途中失敗後はrevisionを進めた専用stateとなり、失敗したreservation IDと現在のledger上の `failed` 証拠が一致する。
2. 初回失敗と再生成失敗はいずれも、一部画像や生provider detailをstageへ残さず回復stageとして返る。
3. 回復stageを返しただけでは追加のCloudflare callを行わず、利用者が再試行関数を明示的に呼んだ場合だけ新しい4-call予約を開始する。
4. 再試行は画像set最大2組を超えず、失敗reservationを解放・再利用せず、成功後の最終plan利用量には失敗分と成功分を含める。
5. 画像なし続行は最終planを画像OFFにしつつ、失敗reservationをledgerから削除・解放しない。
6. stale revision、改ざんstate、別owner・session・query・policy・statusの予約をfail closedにし、失敗stateから画像承認やOutscraper実行へ直接進めない。
7. focused・関連・offline全体、lock、Ruff、文書構造、Python 3.10構文、差分検査が成功し、未実行境界を明記する。

### 実行順序と進捗

- [x] 2026-09-03: 現行state、Cloudflare実行、利用量ledger、orchestrator、既存回帰を読み、失敗後にsessionだけが `image_generating` へ残る原因を確認した。
- [x] 2026-09-03: `EXEC-018` とTD-010を着手状態へ登録し、テストをproduction codeより先に追加した。
- [x] 2026-09-03: 初回失敗、明示再試行、再試行上限、画像なし続行、改ざん・stale拒否、失敗利用量保持を表す9件のfocused testを追加し、production code未変更で9 failedのREDを確認した。state test SHA-256は `7a4cda1005cfa16ab7c192384ad40dd6031c12b512441d618e732aaf2061ef1c`、orchestrator test SHA-256は `de0e5cca3b8fa18ecb94547350a783b92059da6e955fa104401ad87207844d13`。
- [x] 2026-09-03: state machineへ失敗記録、明示再試行、画像なし続行の最小遷移を追加した。
- [x] 2026-09-03: orchestratorへstrictな回復stageと、失敗をstageへ投影する境界を追加した。
- [x] 2026-09-03: focused 11件、state・orchestrator 32件、全v2 475件、offline全体1207件と標準gateをGREENにした。
- [x] 2026-09-03: 要件、backend、security、schema、課題、履歴、残作業、次の再開位置を現行結果へ同期した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | 追加9 test node | 未実装の失敗回復契約により期待した理由で失敗 | 終了1、9 failed。回復遷移・stage・明示retryが未実装で、従来経路はCloudflare固定例外を送出 |
| focused GREEN | 新規test、state machine、orchestrator、Cloudflare HTTP | 全件成功 | 回復契約11 passed、state・orchestrator 32 passed |
| 関連回帰 | v2承認・利用量・provider・pipeline | 全件成功 | 全v2 475 passed |
| 標準gate | lock、Ruff check/format、offline全体、`git diff --check` | 終了0 | lock 72 packages、Ruff成功、1207 passed / 1 deselected、diff check成功 |
| 文書・構文 | 現行Markdown link・anchor・fence、Python 3.10 AST、agents-setup | 欠落・構文・構造error 0件 | Markdown 16件・link 785件・heading 1035件・fence 195組、Python 3.10 AST 157件、14,087-byte template接頭辞、AGENTS目次16件・安全規則 |
| live・UI | 実provider、credential、課金、browser、委託フロントエンド | 本Planでは実行しない | 対象外 |

### セキュリティ・データ・互換性

- 回復stageは固定失敗stateとreservation metadataだけを保持し、API token、生応答、部分画像、provider内部detailを保存・serializeしない。
- 失敗予約は課金済みの可能性があるattemptとしてledger上の集計対象に残す。画像OFFを選んでも巻き戻さない。
- 再試行は利用者の別操作とし、新規予約時に同じprovider上限、owner、session、query plan、pricing/usage policyを再検証する。
- 現行Streamlit、legacy pipeline、cache、保存形式、外部serviceを変更しないため、移行や外部状態のrollbackはない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-03 | 失敗を例外だけでなく専用のsession stateとstageへ投影する | revisionとfailed reservationを結び、再試行・画像OFF以外の遷移をfail closedにするため | 永続job repositoryを追加するときも同じ証拠を保存する |
| 2026-09-03 | 再試行は自動化せず、利用者が呼ぶ別stage関数にする | 外部call・費用を確認点の裏側で増やさないため | UI/API接続後も明示操作と新規予約を維持する |
| 2026-09-03 | 再試行成功時の承認planは失敗attemptもCloudflare利用量へ算入する | ledger上で発生した費用と承認表示の過少計上を防ぐため | providerが実測課金情報を返す場合は別Planでamount契約を拡張する |

### 発見事項

- 既存 `regenerate_images()` は2組目の成功後に再度呼ばれると、新しい予約を開始した後でstate上限を検査する順序だった。本Planで上限検査を予約・transportより前へ移し、2組目が成功・失敗のどちらでも3組目を作らない回帰を追加した。
- 初期GREENではattempt履歴の最終 `finished_at` とsession `updated_at` を完全一致させたが、既存state APIは完了後の時刻で記録することを許す。この既存契約を狭めないよう、ID・status・owner・session・query・policy・単調時系列を維持して `finished_at <= updated_at` に補正した。
- RED後のassertionを変更せず、orchestrator testをRuffで整形し、retry自体の失敗と2組成功後の上限拒否を追加したため、最終test digestはRED時と異なる。RED時と最終時の両digestを履歴へ残した。

### ロールバック

本Planで追加するstate field・遷移、回復stage・関数、focused test、実装状態を更新した標準文書だけを取り除けばEXEC-017完了時点へ戻せる。失敗予約を外部へ送信するlive処理や永続保存は行わないため、外部状態・保存データのrollbackはない。

### 結果

完了。`SearchSessionSnapshot` に `image_generation_failed` と `failed_image_reservation_id`、state machineに失敗記録・新規予約による明示retry・画像なし続行、orchestratorに固定 `ImageFailureReview` と `retry_failed_images()` を追加した。初回生成、成功setの一括再生成、失敗後の明示retryのいずれでも、途中失敗は部分画像と生provider detailを返さず、failed予約を利用量へ残す。retry成功後の最終planは失敗分と成功分の8 callsを含み、画像なしを選んだplanは画像OFFとする一方でledgerを巻き戻さない。

RED時のstate test SHA-256は `7a4cda1005cfa16ab7c192384ad40dd6031c12b512441d618e732aaf2061ef1c`、orchestrator test SHA-256は `de0e5cca3b8fa18ecb94547350a783b92059da6e955fa104401ad87207844d13`。最終state test SHA-256は同じ `7a4cda1005cfa16ab7c192384ad40dd6031c12b512441d618e732aaf2061ef1c`、orchestrator test SHA-256は `5b77e3377349d873fe83472e73ebb170b922284cb5ce19aeaece9f29f7f34e94`、state machine SHA-256は `2dbc54d347a269f36041375449b51b7bb6f7ae470c61584df9be1c3cbdc054af`、orchestrator SHA-256は `f35dfd74d55969aaa3260131023e02c3bf5e6dcca64788390c1ec32edcab9345` である。focused 11件、state・orchestrator 32件、全v2 475件、offline全体1207件、lock、Ruff、文書・Python 3.10構文・agents-setup・差分検査を確認した。

検証は注入transport、fixture JSON、合成PNGだけで行った。実Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、実Amazon候補、実画像、生成・ranking品質、現行pipeline、永続repository、API、browser、外部委託中のフロントエンドは実行・確認・接続していない。次の通常ローカル作業は新しい `EXEC-019` を作成し、owner分離した30日検索履歴repositoryをoffline TDDする。


## EXEC-019: owner分離した30日検索履歴repository

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-03
- 最終更新日: 2026-09-03
- 前提Plan: [EXEC-018](#exec-018-cloudflare画像生成失敗後の回復state)
- 関連要件: `DATA-013`、`DATA-014`、`SEC-015`（[REQUIREMENTS.md](REQUIREMENTS.md#5-データキャッシュ要件)）
- 関連負債: [TD-003](ISSUES.md#td-003-アクセス制御と利用量制御)

### 目的

正常完了した検索を0件結果も含めて一意な履歴へ自動保存できる。同じ利用者はローカルprocessの再起動後も30日未満の履歴を新しい順に一覧・詳細参照でき、個別削除または保存期限で結果と専有参考画像を一体として物理削除できる。履歴操作から外部providerは呼ばない。

### 対象範囲

- strictでimmutableな保存入力、一覧、詳細、参考画像のallowlist model
- Python標準のSQLiteを使うローカル単一file repositoryと再起動後の読込
- owner内の `completion_key` 一意性による冪等保存、同一payloadの再保存、異なるpayloadの衝突拒否
- ownerで必ず絞る新着順一覧、公開locatorによる詳細・参考画像取得
- owner確認付き個別削除と30日到達後の冪等な期限物理削除
- 履歴一覧・詳細・削除・再保存にprovider transportやcredentialを受け取らないoffline境界

### 対象外

- 認証・tenant解決、HTTP API、browser、外部委託中のフロントエンドの確認・起動・テスト・接続
- 複数worker、共有DB、backup、暗号化、運用中のschema migration、容量制限、scheduler
- 現行Streamlit・legacy cache・現行pipelineとの接続または旧cacheの移行
- 実Bonsai、Cloudflare、Outscraper、OpenAI、credential、外部送信、課金
- AIレビューハーネスの実行と `docs/HARNESS-RUNBOOK.md` の変更

### 現在の状態

着手前の `ProductSearchPipelineResult` は `results`、`empty`、`failed` と検索完了時刻を同一process内で保持したが、再起動後に読める検索履歴は存在しなかった。本Planで利用者向けスナップショット、owner内の冪等キー、30日期限、結果と専有生成画像の一体削除を新規SQLite fileのversion 1 schemaとして実装した。旧cacheは読み書きしていない。完了result・承認stageから保存入力への変換、認証、API・UI接続は後続に残る。

### 受入条件

1. strict inputはowner、completion key、UTC完了時刻、利用者向け条件、正常結果、0枚または固定4枚の参考画像だけを受け付け、provider・model・request ID・postal code・token・raw score・digestを表示modelへ含めない。
2. owner内で同じcompletion keyと同じpayloadを複数回保存しても1件と同じlocatorを返す。同じkeyで異なるpayloadは上書きせず拒否し、別ownerの同じkeyは独立させる。
3. 一覧は同じownerの未期限履歴だけを完了時刻の新しい順に返し、詳細・参考画像・個別削除はowner不一致をnot foundと同じ固定失敗にする。内部 `history_id` は返さない。
4. `expires_at` は `completed_at + 30 days` に固定し、期限到達後はcleanup未実行でも一覧・詳細・画像に返さない。期限削除は履歴・結果・専有画像を同じtransactionで物理削除し、再実行しても安全である。
5. 個別削除はownerを確認して履歴と専有画像を1 transactionで削除する。失敗はrollbackし、別ownerの履歴・画像を変更しない。
6. 新しいrepository instanceから同じSQLite fileを読んで保存済み履歴を取得でき、履歴操作は外部provider、credential、旧cache、検索・正規化・rankingを呼び出さない。
7. RED→GREEN、focused・全v2・offline全体、lock、Ruff、文書構造、Python 3.10構文、差分検査に成功し、未実行境界を記録する。

### 実行順序と進捗

- [x] 2026-09-03: 現行要件、論理schema、完了result、画像artifact、テスト境界を確認した。
- [x] 2026-09-03: `EXEC-019` を登録し、ローカル単一fileのSQLite repositoryとする判断を固定した。
- [x] 2026-09-03: 正常結果・0件、冪等保存、owner分離、新着順一覧、詳細、再起動読込を表すREDテストを追加した。
- [x] 2026-09-03: 個別削除、期限後の非表示、履歴・結果・専有画像の期限物理削除、保存・削除失敗のrollbackを表すREDテストを追加した。
- [x] 2026-09-03: API名だけのscaffold上で履歴test 13件を実行し、1 passed / 12 failedのREDを確認した。失敗理由は保存・一覧・詳細・画像取得・削除・期限削除が `NotImplementedError`、未知schema versionの拒否が未実装であること。test SHA-256は `9fbc8e60fca96f04cb46f43df9d9e883ec57ac612b314f3a5716ea6c0b8e22cf`。
- [x] 2026-09-03: `src/search_v2/history_repository.py` へstrict modelとSQLite transaction境界を実装した。
- [x] 2026-09-03: focused・全v2・offline全体と標準gateを実行した。
- [x] 2026-09-03: 要件、backend、security、schema、課題、履歴、残作業、次の再開位置を同期した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_history_repository.py` | 未実装の履歴操作により期待した理由で失敗 | 終了1、1 passed / 12 failed。repository操作とschema拒否が未実装 |
| focused GREEN | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_history_repository.py` | 全件成功 | 終了0、15 passed |
| 関連回帰 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_*.py` | 全件成功 | 終了0、490 passed |
| 標準gate | lock、Ruff check/format、offline全体、`git diff --check` | 終了0 | lock 72 packages、Ruff成功、1222 passed / 1 deselected、diff check成功 |
| live・UI | 実provider、credential、課金、browser、委託フロントエンド | 本Planでは実行しない | 対象外 |

### セキュリティ・データ・互換性

- repositoryはowner IDを呼出しごとに必要とし、locator、session ID、completion keyだけを認可根拠にしない。owner不一致と不在は同じ固定失敗にする。
- 利用者向けmodelはallowlistとし、credential、provider、model、prompt、request、token、digest、利用量、postal code、raw scoreを持たない。source textと商品情報は利用者データとしてローカルDBに保存されるため、Git、ログ、artifact、文書へ複製しない。
- SQLiteのforeign keyと単一transactionで専有画像を履歴と一体削除する。運用中のmigration、複数worker競合、backup、at-rest暗号化は本Planで保証しない。
- 旧cacheと新規履歴DBは別物であり、旧データの移行・変更・削除は行わない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-03 | Python標準SQLiteの新規単一fileに履歴と専有画像を保存する | 追加依存なしで再起動後の読込、owner内一意制約、原子的な保存・削除を同時に満たせるため | 複数worker、共有運用、backup・復旧要件が決まったら別Planで再評価する |
| 2026-09-03 | exact replayだけを冪等成功とし、同じcompletion keyの異なるpayloadは衝突にする | 完了通知の重複と不整合な上書きを区別するため | payload変更を許す要件が追加されたらversioned updateを別設計する |
| 2026-09-03 | 期限到達後はcleanupの成否と無関係に読取経路から隠す | 削除job遅延時に30日超のデータを返さないため | 法的holdや異なるretentionが必要な場合はschemaと要件を変更する |

### 発見事項

- 最初のRED実行は、期待するrepository未実装より前にscaffoldのUTC validatorの `NameError` で失敗したため証拠に採用しなかった。同じtest SHA-256のままvalidatorとimportだけを修正し、repositoryの `NotImplementedError` で失敗するREDを取り直した。
- 実装後の補足REDで、Pydanticとして有効な別JSONへの置換はmodel検証だけでは検知できないと確認した。保存時の `detail_sha256` と読込時のconstant-time比較を追加した。
- 既存DB fileを自動で0600へ変更すると、権限設定の誤りを呼出元に知らせず所有外fileへ作用する。既存POSIX fileにgroup・other権限があればmodeを変更せず固定errorで拒否する方針へ変更した。
- SQLite repositoryはownerを比較できるが、そのownerが認証済み主体かを判定しない。API公開前にserver-side認証からownerを解決する必要がある。

### ロールバック

新規履歴module、test、文書の実装状態更新を取り除けば、EXEC-018完了時点に戻る。旧cacheと現行pipelineは変更しない。本Planで作るSQLite fileはruntime dataでありGit管理しない。実データの削除は実行しない。

### 結果

完了。`history_repository.py` にstrictな保存入力・表示用model、SQLite version 1 schema、owner内の冪等保存、未期限の新着順一覧、owner確認付き詳細・画像取得・個別削除、30日期限削除を追加した。同じcompletion keyの異なるpayload、owner不一致、未知schema、安全でない既存file mode、保存JSONとdigestの不一致をfail closedにし、履歴と専有画像の保存・削除失敗をrollbackする。

初期REDは1 passed / 12 failed、補足REDでは有効JSON改ざんと安全でない既存file modeをそれぞれ検出した。最終module SHA-256は `4a10f542c0ca5e2e1fa14dd519543f7b66ad43122b10e97b4dab3248cb8ba8e9`、test SHA-256は `90237c8169040ad340df3cf0de4689b19c47c7be1e3270962fa3c06274cc8214`。focused 15件、全v2 490件、offline全体1222件、現行Markdown 16件のlocal link 795件・見出し1071件・fence 195組、Python 3.10 AST 159件、`agents-setup` のコミット済み14,087-byte template接頭辞、AGENTS目次15件、lock、Ruff、差分検査を確認した。

検証は一時SQLite、合成表示データ、合成PNGだけで行った。実利用者データ、実Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、実Amazon候補、実画像、現行pipeline、完了resultから履歴入力への変換、認証、API、browser、外部委託中のフロントエンドは実行・確認・接続していない。次の通常ローカル作業は `EXEC-020` を新規作成し、正常完了result・承認stage・元入力・任意画像を表示用履歴snapshotへ変換してrepositoryへ保存するoffline境界をTDDする。


## EXEC-020: 完了検索から表示用履歴への変換と保存

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-03
- 最終更新日: 2026-09-03
- 前提Plan: [EXEC-019](#exec-019-owner分離した30日検索履歴repository)
- 関連要件: `DATA-013`、`DATA-014`、`SEC-015`（[REQUIREMENTS.md](REQUIREMENTS.md#5-データキャッシュ要件)）
- 関連負債: [TD-003](ISSUES.md#td-003-アクセス制御と利用量制御)

### 目的

正常に完了した商品検索を、現在結果と同じ利用者向け情報だけを持つ検索履歴へ1回保存できるようにする。保存の再試行ではBonsai、Cloudflare、Outscraper、正規化、rankingを再実行せず、正常な0件は保存し、失敗した検索は保存しない。

### 対象範囲

- `SearchReview`、元の自然文、`ProductSearchPipelineResult` のowner、session、intent、query、承認plan、完了batch、完了時刻の再検証
- 元入力の完全一致SHA-256を、Bonsai requestとintent provenanceの両方へ再照合する境界
- 確定条件、価格、順位付け結果、採用済み4方向画像から `SearchHistoryWrite` を作る決定的なallowlist変換
- raw score・weight・採用言語・provider・model・request ID・郵便番号・token・digestを表示snapshotへ含めない平易な結果説明
- 正常な `results` と `empty` だけを既存 `SqliteSearchHistoryRepository` へ冪等保存するoffline application service

### 対象外

- 認証・tenant解決、HTTP API、browser、現行Streamlitとの接続
- 外部委託中のフロントエンドの確認、レビュー、起動、画面確認、テスト、バックエンド接続
- 実Bonsai、Cloudflare、Outscraper、OpenAI、credential、外部送信、課金
- provider処理、正規化、rankingの再実行、検索job・取消・再開、複数worker向けtransaction
- 履歴schema migration、backup、暗号化、scheduler、旧cacheの移行
- AIレビューハーネスの実行と `docs/HARNESS-RUNBOOK.md` の変更

### 現在の状態

`orchestrator.py` の `SearchReview` は承認前に固定したintent、query plan、Outscraper request、利用上限、任意の採用済みCloudflare画像を結ぶ。`product_pipeline.py` の `ProductSearchPipelineResult` は消費済み承認を持つ最終sessionと、正常時の正規化・順位付けbatchを結ぶ。`history_snapshot.py` はこれらと元入力を再検証して `SearchHistoryWrite` へ変換し、`history_repository.py` へ保存する。現行pipeline、認証、API・UIからの呼出しはまだない。

元の自然文そのものは `SearchReview` に保持せず、そのSHA-256だけをBonsai requestとintent provenanceへ残している。このため保存境界は自然文を明示引数で受け、両digestへ完全一致する場合だけ履歴へ複製する。raw approval token、provider credential、生provider responseは受け取らない。

### 受入条件

1. 正常完了した `results` と `empty` だけを変換でき、`failed`、未完了、owner・session・intent・query・batch・承認planの不一致を、保存前の固定errorで拒否する。
2. 元入力は型、長さ、制御文字を検証し、exact UTF-8 SHA-256がBonsai requestとintent provenanceの両方に一致する場合だけ採用する。照合後にNFKCと空白整理を行った表示用本文を保存し、正規化済みの別入力をdigest照合の代用にしない。
3. 条件snapshotは商品種別、重複のない確定条件、価格要約だけを持つ。結果snapshotはrank、title、画像URL、価格、説明、Amazon URL、一致・未確認・注意点、画像比較案内だけを持ち、推測値を追加しない。
4. raw score、component、weight、採用言語、provider/model/request ID、郵便番号、approval token、利用量、内部digestを表示modelへ含めない。画像比較は現行rankingで無効である事実を平易に示し、生成画像を商品証拠として扱わない。
5. 画像OFFまたは破棄済み画像は0枚、採用済み画像は承認plan・完了sessionと再照合した固定順4枚だけを履歴へ複製する。
6. completion keyは同じowner・session・完了結果・変換契約で決定的に同一となり、同じ保存要求の再試行は同じlocatorを返す。再試行時に外部処理、正規化、rankingを呼ばない。
7. repository保存失敗は完了結果を変更せず固定履歴errorとして返り、同じ検証済み入力で再保存できる。
8. RED→GREEN、focused・全v2・offline全体、lock、Ruff、文書構造、Python 3.10構文、差分検査に成功し、未実行境界を記録する。

### 実行順序と進捗

- [x] 2026-09-03: `SearchReview`、完了result、元入力digest、ranking内訳、画像artifact、履歴repositoryの結合条件を確認した。
- [x] 2026-09-03: `EXEC-020` を登録し、raw tokenを受け取らない独立した変換・保存境界とする判断を固定した。
- [x] 2026-09-03: 正常結果・0件・画像採用・画像OFFのallowlist変換を表すREDテストを追加した。
- [x] 2026-09-03: 元入力、owner、session、intent、query、承認plan、完了batchの改ざんと失敗結果の保存拒否を表すREDテストを追加した。
- [x] 2026-09-03: 冪等な再保存とrepository失敗後の再保存がprovider再実行を伴わないことを表すREDテストを追加した。
- [x] 2026-09-03: scaffold上でfocused test 8件を実行し、1 passed / 7 failedのREDを確認した。失敗理由は変換・保存関数の `NotImplementedError`。test SHA-256は `6fc501d445b2d410fa6c1dd216b1429a08cd22d68371cfbad098c62e58c253d3`。
- [x] 2026-09-03: `src/search_v2/history_snapshot.py` に変換・検証・保存境界を実装した。
- [x] 2026-09-03: focused 8件、全v2 498件、offline全体1230件と標準gateを実行した。
- [x] 2026-09-03: 要件、backend、security、schema、課題、履歴、残作業、次の再開位置を同期した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_history_snapshot.py` | 未実装の変換・保存境界により期待した理由で失敗 | 終了1、1 passed / 7 failed。変換・保存関数が `NotImplementedError` |
| focused GREEN | 同上 | 全件成功 | 終了0、8 passed |
| 関連回帰 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_*.py` | 全件成功 | 終了0、498 passed |
| 標準gate | lock、Ruff check/format、offline全体、`git diff --check` | 終了0 | lock 72 packages、Ruff 161 files、1230 passed / 1 deselected、diff check成功 |
| 文書・構文 | 現行Markdown link・anchor・fence、Python 3.10 AST、AGENTS目次 | 欠落・構文・構造error 0件 | Markdown 16件・link 802件・heading 1086件・fence 195組、Python 161件、AGENTS目次15件 |
| live・UI | 実provider、credential、課金、browser、委託フロントエンド | 本Planでは実行しない | 対象外 |

### セキュリティ・データ・互換性

- 元入力と商品情報は利用者データである。変換と保存にだけ使用し、ログ、例外、テスト証拠、文書、Gitへ実データを複製しない。
- 変換境界はcredential、raw approval token、生provider responseを引数・返却modelに持たない。履歴の表示allowlistから内部metadataを除外する。
- 完了resultと承認済みreviewの整合を保存前に再検証するが、ownerが認証済み主体であることは保証しない。認証・tenant解決はAPI公開前の別Planで行う。
- 新規変換moduleは現行Streamlit、legacy cache、provider経路を変更しない。保存は既存SQLite repositoryのtransactionと30日期限契約に従う。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-03 | 元入力を保存関数の明示引数とし、既存の2つのsource digestへ再照合する | reviewはprivacy境界として本文を保持しておらず、digestだけから本文を復元・推測できないため | job repositoryが検証済み本文を保持する設計へ変わった場合に入力元を再評価する |
| 2026-09-03 | `SearchReview` と完了resultを受け、raw approval tokenを受け取らない | 保存は完了後の表示snapshot作成であり、single-use tokenを再利用する必要がないため | durable job/result契約を導入した場合はtoken以外の固定識別子へ置換する |
| 2026-09-03 | 表示説明は既存の観測値とmatched/missing/negative termsだけから作る | raw scoreを漏らさず、未観測情報を推測しないため | UX文言または説明可能性contractを変更する場合はsnapshot versionを見直す |

### 発見事項

- `SearchReview` は採用画像だけを `image_review` に保持する。生成後に画像なしを選んだ経路は `image_review=None` となるため、破棄画像を履歴へ保存せずに済む。
- 現行ranking profileは画像採点を無効にしている。採用画像は検索条件の記録として保存できるが、商品との画像類似度を確認済みとは表示できない。
- 初期GREENで、テストfixtureは日本語項目だけから1 queryになると仮定していたが、ブランド名と型番から英語queryも構築され、承認済み候補上限は48件だった。変換は固定値を置かず、承認済みOutscraper requestの上限を保存する。

### ロールバック

本Planで追加する変換module、focused test、実装状態を更新した標準文書だけを取り除けばEXEC-019完了時点へ戻る。現行pipeline、legacy cache、履歴repository schemaは変更しない。テストでは一時SQLiteと合成データだけを使い、実利用者データを作成・削除しない。

### 結果

完了。`history_snapshot.py` に、正常完了result、承認済みreview、元入力から表示用履歴を作る決定的変換とSQLite保存呼出しを追加した。元入力のexact digest、owner、session、intent、query、承認plan、完了時刻、normalized・ranked batch、任意画像を再検証し、失敗result、別session、normalized batch外の商品差し替えを保存前に固定errorで拒否する。

表示snapshotは確定条件・価格と、rank、title、先頭画像、価格、説明、Amazon URL、一致・未確認・注意点、画像比較案内だけを持つ。raw score、component、weight、採用言語、provider、model、request ID、郵便番号、token、利用量、内部digestを表示商品へ複製しない。正常0件は保存し、採用済み画像だけを固定順4枚で保存する。exact replayと保存失敗後の再試行は同じcompletion keyを使い、provider、正規化、rankingを再実行しない。

RED test SHA-256は `6fc501d445b2d410fa6c1dd216b1429a08cd22d68371cfbad098c62e58c253d3`、最終module SHA-256は `396f28e28f8283dfffd4970ff484435cd5ce2c33c7e424366a096cac881ae071`、最終test SHA-256は `be38b6c4d6f0a869a06dc2aea5c8882fe5b7701dca5c8a814e9edda2cea6fa39`。focused 8件、全v2 498件、offline全体1230件、現行Markdown 16件のlocal link 802件・heading 1086件・fence 195組、Python 3.10 AST 161件、AGENTS目次15件、lock、Ruff、差分検査を確認した。

検証は注入transport、fixture JSON、合成PNG、一時SQLiteだけで行った。実利用者データ、実Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、実Amazon候補、実画像、生成・ranking品質、現行pipeline、認証、API、browser、外部委託中のフロントエンドは実行・確認・接続していない。次の通常ローカル作業は新しい `EXEC-021` を作成し、DNSで検証したIPへ接続先を固定しつつ元hostのTLS証明書を検証するserver-side image HTTPS transportをoffline TDDする。


## EXEC-065: 未知の視覚条件に対する条件別counterfactual画像評価

### メタデータ

- 状態: 進行中（batch較正付きminimum-positive v4をdevelopment相対合格。未知条件の独立1-case probeはaccuracy 0.875で不合格、最終holdoutとrankingは未完了）
- 作成日: 2026-09-07
- 最終更新: 2026-09-07
- 関連Task: [TASK-005](#task-005-ランキング品質評価の確立)、[TASK-008](#task-008-次期検索フロー-v2-の実装)
- 関連要件: [FR-408](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-415](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-417](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-419](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-420](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)、[TD-011](ISSUES.md#td-011-画像取得推論の実環境検証)
- 先行Plan: [EXEC-064](#exec-064-実ブラウザ候補とgpt-image独立参照のclip診断)

### 目的と利用者から見える結果

全体画像どうしの近さを1値へ平均する方式では、白背景、縦横比、商品全体の輪郭、生成画像の作風が、利用者の複数条件より強く作用した。固定オフィスチェアartifactではcrop、同一候補集合の負例、label centroidのいずれもAUC 0.80へ届かなかった。このPlanでは「黒い」「メッシュ背もたれ」「ヘッドレスト付き」のような視覚条件を個別に扱い、条件を満たす画像と、その条件だけを違反させた画像との差から候補を評価する。

利用者には、画像で比較する条件を最大3件まで確認してもらう。評価できない条件を勝手に一致へせず、商品情報で確認できる条件は従来どおり構造化情報と限定した商品名表現を優先する。品質が合格するまで画像rankingは無効のままである。

### 対象範囲と対象外

対象は、source-groundedな視覚条件model、最大4-callのcounterfactual reference set、固定CLIP embeddingから条件別marginを作る純粋計算、評価artifact、独立holdoutによる採否である。最初に外部通信なしのdomainとscore契約をTDDし、その後の明示承認が得られた場合だけ、候補画像を入力しないテスト用gpt-imageで参照を生成する。

本番Cloudflare接続、現行4方向の製品仕様変更、画像ranking有効化、候補画像の外部送信、Outscraper後のLLM補完、外部委託中フロントエンドの確認・変更、model download、commit、pushは対象外とする。本番生成providerはCloudflare、gpt-imageは評価テスト専用という境界を維持する。

### 用語と設計

- `VisualCondition`: NFKC/casefold済み元入力中のexact source span、正規化値、強さ、順序、digestだけを持つ。日本語は既存のSudachiPy `SplitMode.C`、英数字は既存tokenizerの語境界で確定する。固定の類似語辞書へ未知語を丸めない
- `desired anchor`: 利用者が選んだ最大3条件を全て満たす、候補商品とは独立した生成画像
- `counterfactual reference`: desired anchorと同じ商品種別、個体、構図、背景を保ち、対応する1条件だけを不成立にした生成画像。excluded条件では、desired anchorを除外条件なし、counterfactualを除外条件ありにする
- `condition margin`: 初回方式は候補embedding `c`、desired anchor `a`、条件iのcounterfactual `n_i` に対して `cos(c,a) - cos(c,n_i)` を `1 - cos(a,n_i)` で正規化する。再設計は `P_i = {a} ∪ {n_j | j ≠ i}` を条件iを満たす正例参照とし、`mean(cos(c,p), p∈P_i) - cos(c,n_i)` を `mean(1 - cos(p,n_i), p∈P_i)` で正規化する。条件1件では初回式と完全に一致し、条件名や類似語辞書へ依存しない
- `counterfactual reference set`: desired anchor 1枚と最大3枚のcounterfactualを固定順で持つ。1組は選択条件数を `N` としてexact `1 + N` calls、上限4 callsとし、条件が1件または2件でも空きcallを別用途へ自動転用しない

未知語への汎用性は、語彙表へ登録済みかではなく、入力中のspanが再現でき、利用者が画像で確認可能な外観条件として選べるかで決める。LLMはcondition ID、evaluator、model、path、URL、weight、閾値、反実仮想の実行方法を指定できない。source spanを復元できない語、数値寸法、個数、互換性、接続方式、容量、性能、材質など画像だけで確定できない条件はこのevaluatorへ入れず、既存の証拠裁定で `unknown` を維持する。

生成promptはrepository内の固定templateと、既存term上限内の確認済みsource phraseだけから作る。URL、改行、control文字を拒否し、phraseを命令文として展開しない。required・preferredには「この外観だけを取り除く」、excludedには「この外観だけを加える」という固定operationを使い、自由形式の反対語、追加指示、LLM生成promptを受け取らない。任意の未知語に唯一の論理的反対を仮定せず、生成後の人間確認で1条件だけが変わったことを必須にする。

視覚条件が4件以上ある場合、サーバーは上位3件を自動選択しない。画像生成前の確認で利用者が最大3件を選ぶか、画像評価を使わず続行する。未選択条件は消去せず、構造化・title証拠がなければ `unknown` とする。

### 処理順序と信頼境界

1. 既存Bonsai 1 callのstrict intent候補から視覚条件候補を受けるが、既存SudachiPy source groundingで元入力spanへ再照合できたものだけを表示候補にする。
2. trusted registryで画像評価不可の属性を除外し、利用者が最大3条件を明示選択する。選択だけではproviderを呼ばない。
3. image-set実行の明示承認後、desired anchorを1 callで生成する。成功したanchorだけを参照入力にし、各counterfactualを最大3 callsで生成する。実装時は派生要求の並列化可否を計測するが、exact `1 + N` calls・上限4 calls、retry 0、自動再実行なしを変えない。
4. 期待する `1 + N` 枚全ての画像、対応条件、`AI生成イメージ`、desired/counterfactualの区別を利用者が確認する。1枚でも欠損、重複、条件以外の大きな差、意味逆転があればset全体を不採用にする。
5. 商品候補画像は既存proxyでlocal取得し、候補画像も候補embeddingもCloudflare、gpt-image、Bonsai、その他のLLMへ送らない。固定ONNXのlocal CPU processで全embeddingを作る。
6. 条件ごとのmarginを独立に計算する。検証済み閾値がなければ表示・rankingへ使わず、画像欠損、参照分離不足、条件超過、評価不能は `unknown` または `missing` とする。
7. 専用画像evaluatorが品質gateを通った属性だけ、registryの低優先度 `visual_feature` 証拠候補にできる。構造化値と限定title parseを上書きせず、requiredの不一致を総合scoreで打ち消さない。open visual phraseは合格後も最初は補助scoreに限定し、exact `match`・`mismatch` へ昇格させない。

### 応答時間、回数、費用

実験profileは1組をexact `1 + N` calls、上限4 calls、1計画最大2組、失敗時の自動retry 0とする。実行前に選択条件数からexact call数を予約し、未使用slotを予約・消費しない。desired anchorの完了後、最大3つのcounterfactualを独立要求として同時開始できる実装案を採用候補とし、現行の逐次4 callsより長いcritical pathを作らない。ただし並列性はprovider上限、local worker境界、失敗時の利用量確定をoffline fixtureと実測で確認するまで保証しない。

本Plan作成時点では外部call 0、credential 0、費用0円だった。development較正では事前提示と明示承認に従い、テスト用gpt-imageを2組・合計6 calls、retry 0で実行した。内訳は電気ケトル2 calls、オフィスチェア4 callsで、候補商品画像・候補embedding・商品識別子・credentialは送信していない。人間承認が必要で自動再実行しない試験には費用上限を設けない既存判断を適用したが、exact call上限は固定した。追加のgpt-image試験またはCloudflare試験は、送信先、prompt概要、画像数、exact call数、retry、費用、保存範囲を改めて提示し、別の明示承認を得る。

### 実装マイルストーン

- [x] 2026-09-07: EXEC-064と固定 `image-holdout-005` の失敗、改善検証、現行4方向・Cloudflare・利用量・typed condition・SudachiPy境界を確認した。
- [x] 2026-09-07: source-grounded条件、最大4-call counterfactual set、条件別margin、最大3条件、fail-closedな証拠裁定、採否と製品仕様変更の境界を設計した。
- [x] 2026-09-07: `VisualCondition` とcounterfactual reference setのstrict model、digest、改ざん・上限・不適格属性拒否を外部通信なしでRED→GREENした。
- [x] 2026-09-07: 固定embedding fixtureでraw margin、正規化margin、参照分離不足、画像欠損、候補非依存性、条件ごとの `unknown` をRED→GREENした。閾値未較正のためranking適格にはしていない。
- [x] 2026-09-07: `image-holdout-004` と `image-holdout-005` をdevelopment setとして、候補画像をgeneratorへ送らず、テスト用counterfactual参照を2組・exact 6 calls・retry 0で生成した。利用者が各画像の条件差を確認し、pHash最小距離は20と6で重複閾値5を超えた。
- [x] 2026-09-07: scoreを見る前に固定したlabelで較正を実行した。電気ケトルの黒色はAUC 1.0で通過したが、椅子のヘッドレストはAUC 0.75、適格条件のpoolはAUC 0.78、椅子の条件集約は最小AUC 0.583333333・平均AUC 0.708333333で基準未達だった。椅子の色とメッシュは各class最低3件を満たさず不適格だったため、判定閾値と較正profileを採用しなかった。
- [x] 2026-09-07: 次回再設計後も絶対基準へ届かない場合、今回方式と再設計方式を同一development bindingで比較し、高精度な方をdevelopment相対合格にする利用者判断をstrict offline selectorへ実装した。相対合格は独立holdoutへ進む資格だけで、ranking適格ではない。
- [x] 2026-09-07: 固定artifactだけで、条件i以外のcounterfactualが条件iを満たすという構造を正例参照へ再利用するmean-positive方式を再設計した。追加生成、browser、外部callは行っていない。
- [x] 2026-09-07: 初回方式と同一dataset・label・評価契約・20判定で再計算した。両方式ともaccuracy 0.80で絶対基準未達だったが、再設計はpool AUC 0.84、worst-condition AUC 0.958333333で初回の0.78・0.75を上回ったため、pairwise AUCをtie-breakerとしてdevelopment相対合格とした。
- [x] 2026-09-07: 全ての適合参照への一致を要求するminimum-positive v4を設計・実装した。参照自己較正はhard clampでpool AUC 0.72、単調変換でも0.84・16/20となり改善しなかったため棄却した。
- [x] 2026-09-07: mean-positive v2と同一binding・20判定でv4を固定ONNX再計算した。accuracy 0.85、pool AUC 0.93、worst-condition AUC 1.0となり、v2の0.80・0.84・0.958333333を全て上回ったため、第1指標accuracyでv4をdevelopment相対合格とした。
- [x] 2026-09-07: 同じ検索の4〜32候補だけから条件別の観測中点と半幅を求め、正解labelや条件名を使わず共通閾値0へ写すbatch較正をoffline TDDした。ゼロ交差または同じ飽和端点2件以上の支持がなく片側に連続する条件は `insufficient_diversity` とし、較正値を返さない。
- [x] 2026-09-07: 同一bindingの固定ONNXでbatch較正付きv4を再計算した。ケトル黒色と椅子ヘッドレストを各10/10、適格20判定を20/20、pool AUC 1.0とし、未較正v4の17/20・0.93を上回ったためdevelopment相対合格を更新した。椅子メッシュは `insufficient_diversity`、色・メッシュはclass数不足、独立holdoutは未実施なので絶対判定 `fail` とranking無効を維持した。
- [x] 2026-09-07: 未使用のデスクライト・クランプ条件で独立1-case probeを実行した。隔離browser 1 navigation・外部要求100件で候補12枚、テスト用gpt-image exact 2 calls・retry 0でdesiredと自立台座counterfactualを作り、利用者確認後に固定ONNXを実行した。match 3、mismatch 5、ambiguous 4を事前固定し、全12候補でlabel-free較正した結果、pairwise AUC 1.0、共通閾値0のaccuracy 7/8 = 0.875で、絶対基準0.90へ未達だった。
- [ ] 今回caseを開発調整へ流用せず、過去の全画像条件とデスクライト・クランプ条件を除外した最低2 category・各2 caseの残り独立holdoutで、条件別と全体の固定gateを評価する。
- [ ] 品質合格後にだけ、現行4方向setをcounterfactual setへ置き換えるか、追加callで併用するかを、応答時間・call数・費用とともに利用者へ提示して決定する。決定前はFR-404、FR-405、SEARCH-FLOWを変更しない。
- [ ] 採用決定後は新しいPlanでCloudflare request、state、ledger、history、ranking profile、API/UI契約と旧artifact非互換を実装する。

### 検証と採用基準

通常gateは `uv lock --check --offline`、Ruff check、Ruff format check、Markdown link check、`pytest -m 'not live_api'`、`git diff --check` とする。振る舞いを追加するときは対象testのRED、GREEN、test file SHA-256を同じPlanへ記録する。

画像品質評価は、参照生成前に条件、候補取得方法、最低件数、label規則を固定し、scoreを見る前に各条件の `match`・`mismatch`・`ambiguous` を固定する。development setはcase1からcase3、過去のCSV、EXEC-064の全条件を含み、式・閾値選択にだけ使う。独立holdoutはこれらを一切含めない。

絶対合格には、各caseで条件別の正例・負例を各3件以上、各categoryにhard negativeとuncertaintyを各1件以上含め、全条件・全categoryでpairwise AUC 0.80以上かつ正例中央値が負例中央値を上回ること、通常decision accuracy 0.90以上、失敗・欠損を除外しないことをANDで要求する。counterfactual参照は候補と独立し、期待する `1 + N` 枚間のpHash重複拒否、1条件以外を変えていないという人間確認、固定した参照分離範囲も満たす必要がある。

次回再設計との比較に限り、両仕様が上記の絶対基準へ届かなかった場合は相対合格fallbackを適用する。比較対象は今回方式と次回再設計の2件だけとし、同じdevelopment dataset SHA-256、label SHA-256、評価contract SHA-256、評価件数を必須とする。失敗・欠損を正解件数から除外しないdecision accuracyを第1指標、pairwise AUCを第2指標、worst-condition AUCを第3指標として辞書順に比較する。全指標が同じ場合は変更を増やさない今回方式を選ぶ。選ばれた仕様はassessmentを `pass`、basisを `relative_development_accuracy` とするが、`qualified_for_ranking=false` を維持し、独立holdoutへ進む資格だけを与える。gpt-imageでの絶対・相対合格はCloudflare合格へ読み替えず、本番採用にはCloudflareで別の未使用holdoutを通す。

固定development比較では、再設計も絶対accuracy 0.90へ届かず、椅子の色とメッシュも最低class数不足のままだった。一方、ケトル黒色AUC 1.0を保持し、椅子ヘッドレストAUCを0.75から0.958333333、適格条件pool AUCを0.78から0.84へ改善した。双方のdecision accuracyが16/20で同値だったため、第2指標のpairwise AUCで `counterfactual-mean-positive-v2` をdevelopment相対合格とした。この結果は同じdevelopment setへの適合であり、未知データの精度またはranking品質の合格ではない。

後続v4比較では、各条件の正例参照cosineを平均せず最低値とし、同じ負例cosineとの差を正例・負例間の平均参照距離で正規化した。v4はケトル黒色と椅子ヘッドレストのAUCをともに1.0とし、適格条件pool AUC 0.93、decision accuracy 17/20を得た。mean-positive v2の0.84・16/20より高いため `counterfactual-minimum-positive-v4` をdevelopment相対合格へ更新した。絶対accuracy 0.90、構成不足、未知holdoutは未達であり、ranking適格ではない。

後続のbatch較正は、候補ごとのv4 scoreを変えず、同じcondition・reference・profile・runtimeへ結ばれた4〜32候補の観測範囲だけを使う。条件別の最小値と最大値の中点をcenter、半幅をscaleとし、`clamp((score - center) / scale, -1, 1)` で共通閾値0へ写す。正解label、条件名、category、固定閾値表は使わない。観測幅 `1e-6` 未満、ゼロを跨がず同一飽和端点の2候補以上の支持もない条件はcalibrated marginを返さない。同じ適格20判定はaccuracy・pool AUCとも1.0となり未較正v4を上回ったが、色・メッシュのclass不足、候補集合依存、outlier・単一class、独立holdoutは未確認なので絶対 `fail` とranking不適格を維持する。

最初の未知条件probeは、過去に使っていないデスクライトcategoryと「机の端を挟むクランプ式」を用いた。候補12枚全体の未較正v4範囲は `-1.0` から `0.4920875621654818`、label-free centerは `-0.2539562189172591` となった。固定label 8件ではmatch 3件を全て正しく判定し、mismatch 5件中4件を正しく判定した。pairwise AUC 1.0は順位分離を示す一方、共通閾値0のaccuracy 0.875は絶対基準0.90へ未達である。ambiguous 4件は較正batchへ含めたが正解率の分母から除外した。単一caseで最低2 category・各2 caseの構成を満たさないため、最終採否、ranking、本番Cloudflare合格には使わない。

### 失敗時の安全な状態とrollback

どの段階で失敗しても画像ranking flagをfalseに保ち、既存typed-ranking-v4、4方向Cloudflare descriptor、SEARCH-FLOW、履歴schemaを変更しない。相対合格でもこの安全状態は解除せず、独立holdoutまたは本番Cloudflareの合格として扱わない。途中生成画像はsetとして採用せず、開始済みcallをledgerへ残し、自動retryしない。実験codeを取り除く場合は、新規profile、model、pure score、相対選択module、専用testとPlan参照だけを削除できる構造にし、既存3-file CLIP asset、proxy、4方向生成、ranking-v4へ変更を残さない。

### 判断記録

| 日付 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-07 | 全体類似度のcrop・重み調整を続けず、条件別counterfactualを次の方式とする | 固定artifactで全crop、同一dataset contrastive、centroidが基準未達で、背景・構図・商品全体の近さを除去できなかった | counterfactual参照でも独立holdout基準へ届かなければ専用属性evaluatorまたは別の固定vision-language modelを新Planで比較する |
| 2026-09-07 | 未知語はSudachiPyで元入力spanへ結び、固定類似語辞書への登録を要件にしない | 未知の複合語を落とさず、LLMの創作語や部分一致を実行条件へ入れないため | span復元不能、視覚的に観測不能、4件以上はfail closedまたは利用者選択とする |
| 2026-09-07 | 実験setはdesired 1枚＋counterfactual `N` 枚のexact `1 + N` calls、上限4 callsとする | 条件差を直接作りつつ現行の1組4-call上限を増やさず、選択条件が少ないときに不要なcallを行わないため | 現行4方向を置換する製品変更ではない。品質合格後に応答時間・費用とともに別決定する |
| 2026-09-07 | open visual phraseは最初からexact属性証拠にしない | 画像marginだけで仕様上の一致・不一致を断定しないため | 属性別に独立評価を通しregistryへ固定した場合だけ `visual_feature` 証拠への昇格を審査する |
| 2026-09-07 | 最初の未知条件1-case probeのAUC 1.0を合格へ読み替えず、accuracy 0.875で不合格とする | 事前固定した絶対基準はAUC 0.80とaccuracy 0.90のANDであり、共通閾値0で偽陽性が1件残ったため | このcaseで閾値を調整せず、別の未使用category・条件で残りの独立holdoutを構成する |
| 2026-09-07 | development較正の失敗時に診断用閾値をproduction profileへ昇格しない | 適格条件pool、椅子のヘッドレスト、椅子の条件集約が事前基準へ未達で、色・メッシュも構成不適格だった | 固定artifactによる原因診断と新方式のdevelopment合格後にだけ、独立holdoutを新たに計画する |
| 2026-09-07 | 次回再設計後、両仕様が絶対基準未達なら高精度な方をdevelopment相対合格とする | 利用者が今回または再設計仕様のうち精度の高い方を合格にするよう決定した | 同一bindingでdecision accuracy、pairwise AUC、worst-condition AUCの順に比較する。完全同値は今回方式を選び、rankingは無効のまま独立holdoutへ進む |
| 2026-09-07 | 条件i以外のcounterfactualを条件iの正例参照へ含めるmean-positive方式を相対合格とする | accuracyは双方0.80だが、同一bindingでpool AUCが0.78から0.84、worst-condition AUCが0.75から0.958333333へ改善した | 独立holdoutへ進めるが、絶対合格、ranking適格、本番Cloudflare合格、4方向仕様変更とは扱わない |
| 2026-09-07 | mean-positiveをminimum-positive v4で置き換えてdevelopment相対合格とする | 同一bindingでaccuracy 0.80から0.85、pool AUC 0.84から0.93、worst-condition AUC 0.958333333から1.0へ改善した | 自己較正案は悪化したため棄却する。v4も独立holdout、ranking、本番Cloudflare、製品仕様の合格にはしない |
| 2026-09-07 | label-free batch較正付きminimum-positive v4へdevelopment相対合格を更新する | 同一bindingの適格20判定でaccuracyとpool AUCを未較正v4の0.85・0.93から1.0・1.0へ改善し、片側連続分布のメッシュは判定不能にできた | 候補集合依存、outlier・単一class、構成不足、独立holdoutを未確認のためranking、本番Cloudflare、製品仕様の合格にはしない |

### 発見事項

- 固定ONNXは画像入力だけでなく512次元text embedding出力も持つが、local assetにはtokenizer fileがなく、OpenAI CLIPの日本語・未知語品質も本repositoryで確認していない。tokenizer追加や英訳を前提にせず、最初の実験は既存image embeddingだけで完結させる。
- 4方向参照はオフィスチェアで相互cosineが高く、全方向のAUCも低かったため、平均方法だけが失敗原因ではない。
- source offsetは元の未正規化文字列ではなく、NFKC/casefold済みsourceに対する位置である。全角ASCIIなど正規化で文字表現が変わる入力も同じcanonical source digestへ結ぶ。
- desired/counterfactualの画像重複はpHash閾値では検出されなかったが、参照非重複だけでは属性分離を保証しない。椅子ではヘッドレスト条件のAUCが0.75、色とメッシュは負例不足となり、1条件差の生成だけで汎用的な条件判定器になるとは確認できなかった。

### 結果

設計成果物に加え、`src/search_v2/counterfactual_image.py` にstrictな条件・reference set・未較正score profileと純粋計算を実装した。REDは `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_counterfactual_image.py` を実行し、未実装moduleの `ModuleNotFoundError` でexit 2となった。RED時点のtest SHA-256は `f7827972a13f9bc2038e4efdb8f678c6afa6a8c923096d9a0ac02b35d1f63863` である。実装とtest拡張後は専用pytest 24 passed、画像類似度・typed requirements・tokenizerを含む関連pytest 89 passedとなった。最終module SHA-256は `8efa806764df9d40f4f6f728e9bfbe77713cb40992f2f163d07bf0f3977f537a`、test SHA-256は `c6e315d9de49fd96ee07a58e285049d6db331b5fc7c68bee02342eeb8d3c9312` である。

この実装は、最大3条件、正規化済みsource span、registryで画像評価不可の属性、URL・改行・control、重複条件、条件数と一致しないreference、pixel digest重複、pHash距離5以下、digest・runtime・画像bindingの不一致をfail closedにする。候補欠損は `missing`、数値的に分離しない参照は `unknown` とし、score出力は常に `qualified_for_ranking=false`、module定数も `COUNTERFACTUAL_RANKING_ENABLED=false` である。現行4方向生成、state、ledger、history、typed-ranking-v4は変更していない。

明示承認後、候補を入力しないテスト用gpt-imageで電気ケトル2枚とオフィスチェア4枚をexact 6 calls、retry 0で生成し、利用者が条件差を確認した。候補22枚と参照6枚はrepository-local固定ONNXで7 batchesとして処理した。電気ケトルの黒色は正例4・負例6、AUC 1.0、中央値 -0.382740777 対 -1.0、診断閾値 -0.7626390195、balanced accuracy 1.0で通過した。椅子の色は正例9・負例2・曖昧1、メッシュは正例11・負例0・曖昧1で構成不適格だった。椅子のヘッドレストは正例6・負例4・曖昧2、AUC 0.75、中央値0.8908343505対0.5442160635、診断閾値0.8289868135、balanced accuracy 0.833333で失敗した。適格な黒色とヘッドレストをpoolしたAUCは0.78、balanced accuracy 0.8、椅子集約の最小AUCは0.583333333、平均AUCは0.708333333で、いずれも採用基準へ未達だった。

したがって、診断閾値を較正済みprofileとして採用せず、`qualified_for_ranking=false` と `COUNTERFACTUAL_RANKING_ENABLED=false` を維持した。独立holdout、本番Cloudflare、製品4方向仕様、応答時間契約へ進んでいない。較正artifactは `tests/img/counterfactual-calibration-result.json`、manifestは各development directoryへ保存した。artifact追加のREDは結果file欠落で1 failed、RED test SHA-256は `9c8af5ffce49043e23b4263d459fca89fe703bea84034026308598e0014071a7`、最終test SHA-256は `e323df29fcbad7bb2065407a70274a096298abac647879f863e940270a8e9038`、両manifestは `d255f0a1fb9861688ebedd1f38819083b95ebfc809f724761c541950f2659f0e` と `f26f25f061e7f454dfb1329507b75b190bfc18028510009f3cbcdff6d8ca3b71`、結果artifactは `1545b389e4a576929603ec3802c8fffd66bc06e6ac00878064d38bb96c489b52` である。固定ONNXの明示runtime testは3 passed、通常testは2 passed・1 deselectedだった。記録同期後はlock 79 packages、Ruff 203 files、Markdown 16 files・1,346 links・944 anchors・1,712 headings・203 fence pairs、offline全体1,761 passed・10 skipped・3 deselected、`git diff --check` が成功した。

利用者の比較合格判断を `src/search_v2/counterfactual_selection.py` へstrict offline policyとして追加した。両入力は絶対判定 `fail`、異なる仕様ID、同一のdevelopment dataset・label・評価contract digest、同一評価件数を必須とする。正解数によるdecision accuracy、pairwise AUC、worst-condition AUCの順に比較し、完全同値なら今回方式を選ぶ。結果は `decision=pass`、`selection_basis=relative_development_accuracy`、`eligible_for_independent_holdout=true`、`qualified_for_ranking=false` を固定する。REDはmodule未実装の `ModuleNotFoundError` でexit 2、RED時点のtest SHA-256は `10fa69ad6555847f6f491ea653ea6f1fdec400d3fa6342cca8a9d89f86a070ed` だった。GREENはfocused 8 passed、既存counterfactual関連は26 passed・1 deselectedとなった。最終module SHA-256は `e716d1be1a740e51c90216e0a1800c31be9635fec1d2f9ea5f6d2384d00e6642`、test SHA-256は `28d71cd855dcbe44d5ee1408bfda1e6bcd80012e40c84a1b6e2996895a183cc5` である。記録同期前の標準gateはlock 79 packages、Ruff 205 files、Markdown 16 files・1,347 links・945 anchors・1,713 headings・203 fence pairs、offline全体1,769 passed・10 skipped・3 deselectedで成功した。次の作業は追加生成ではなく、固定artifactだけを使った失敗原因の診断と方式再設計である。

較正前のoffline domain実装直後のgateはlock 79 packages、Ruff check、Ruff format 202 files、Markdown 16文書・local link 1,346件・anchor 944件、offline pytest 1,759 passed・9 skipped・3 deselected、`git diff --check` が全て成功した。較正artifact追加後の最新結果は直前の段落を正とする。

## EXEC-066: counterfactual v4の暫定本番実装

### メタデータ

- 状態: 完了
- 作成日: 2026-09-07
- 最終更新: 2026-09-07
- 関連Task: [TASK-005](#task-005-ランキング品質評価の確立)、[TASK-008](#task-008-次期検索フロー-v2-の実装)
- 関連要件: [FR-404](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-405](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-417](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)、[TD-011](ISSUES.md#td-011-画像取得推論の実環境検証)
- 先行Plan: [EXEC-065](#exec-065-未知の視覚条件に対する条件別counterfactual画像評価)

### 目的

利用者判断により、未知のデスクライト・クランプ条件でaccuracy 0.875だったlabel-free batch較正付きminimum-positive v4を修正せず、既知制約を明示した暫定仕様として本番backendへ実装する。Cloudflareでdesired 1枚と選択条件ごとのcounterfactualをexact `1 + N` calls、最大4 callsで生成し、人間確認済みsetと実商品画像を固定local CLIPへ結び、条件別較正値を低weightの補助画像scoreとして順位へ反映する。

### 対象範囲と対象外

対象は、暫定採用profileとdigest、score・calibration binding、候補商品binding、Cloudflare counterfactual request・HTTP実行契約、可変2〜4 callの利用量予約、画像proxyと固定CLIPを束ねるserver-side evaluator、画像有効の新ranking schema、検索state・approval・historyのversion分離、offline mock・固定runtime検証、現行文書の同期である。

既存の4方向schema、`typed-ranking-v4`、履歴schema 2.0を新仕様として読み替えない。外部委託フロントエンドの確認・変更、実Cloudflare・実画像host・実Outscraper・実Bonsaiへの接続、credential利用、課金、deploy、commit、pushは対象外とする。これらのlive確認は送信内容・回数・費用を再提示した別の明示承認後に行う。

### 現在の状態

既存counterfactual実験domainの出力は引き続きranking不適格だが、利用者が既知accuracy 0.875を確認して暫定採用した別profileだけがrankingを許可する。旧4方向・typed-ranking-v4・history version 2はそのまま残し、新しいexact `1 + N` Cloudflare、永続single-use承認、ranking v5、history version 5をversion分離して接続した。offline mock・固定ONNXで検証済みだが、実provider、API、UI、deployには未接続である。

### 実行手順と進捗

- [x] M1: 既知holdout accuracy 0.875、AUC 1.0、共通閾値0、人間による暫定採用をversion付きprofileへ固定する。
  - production code変更前に `tests/test_search_v2_provisional_counterfactual.py` を追加した。`uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_provisional_counterfactual.py` は未実装moduleの `ModuleNotFoundError` でcollection error（exit 2）となり、REDを確認した。test SHA-256は `6e5331468e3c14250691733a76942e103cb538de539866533c42f658c1cc5ab5`。
- [x] M2: 元のv4 scoreとlabel-free較正を変更せず再検証し、全条件が較正できた候補だけを `minimum calibrated margin` から0〜1の補助画像scoreへ写す。欠損・参照分離不足・較正不能は利用可能scoreへ丸めない。
- [x] M3: desiredと最大3条件のcounterfactualをCloudflareのexact `1 + N` callsで生成するrequest・response・利用量契約を追加し、旧4方向schemaとdigestを分離する。
- [x] M4: 承認済みreference、商品ごとの先頭画像、固定allowlist proxy、固定CLIP processを束ねる。候補の一部欠損を保持し、4件未満ではbatch較正を開始しない。
- [x] M5: 画像scoreをbase weight 0.10の補助componentにする新ranking profileを追加する。既存のtyped必須状態を最優先に保ち、画像からexact属性を補完しない。
- [x] M6: state、2段階approval、利用量、検索後半、表示用historyを新schema・digestへ接続する。旧artifactと旧履歴は拒否し、migrationしない。
  - `provisional_approval_repository.py` の別SQLiteはraw token・画像bodyを保存せず、owner・session・condition・reference・request・usage bindingを15分の承認reviewへ固定し、再起動後の最初のconsumeだけを原子的に成功させる。
  - `provisional_orchestrator.py` は現行のreadyな `IntentReview` からschema 5.0へ分岐し、exact 2〜4 callsの予約・生成後に永続人間確認で停止する。single-use receiptだけがlocal参照変換へ進める。
  - `provisional_history_snapshot.py` と別SQLite `user_version=5` の `provisional_history_repository.py` は、profile ID、accuracy 0.875、condition/reference/runtime/ranking、source v4 batch、商品ごとの画像component状態を表示用履歴へ保存する。旧history `user_version=2` は変更せず、相互にreaderを拒否する。
- [x] M7: focused、関連回帰、固定CLIP runtime、標準offline gateを完了し、live未実施とaccuracy 0.875を文書へ残す。
  - 永続承認・履歴の初回REDは未実装module 2件の `ModuleNotFoundError` でexit 2、test SHA-256は順に `999812a0f5da8c799cf8f2e6b0ac5cbcf106692b157914b2014e7a2da6e6b5c0` と `dfa4b88c51b87f473eb019a7f335bff2aeee096af8e96d5a02cae1f09307457f`。orchestrator分岐と履歴snapshotのREDも未実装moduleでexit 2、test SHA-256は `a07cb5498b61bf441a0c58f777a47279c9a4c8d131f8d358ee27ace2cc9681a2` と `80d63680d149af5dc057d16e34c46b89b868d859dddd809b76a98b011aa18f7a` だった。消費済みreceipt必須化のREDは旧関数signatureによる2 failed、test SHA-256は `3f2c62eef25b9dfe823d1208f72a36545f5a41cc8be3fd935d6c238d3c67d6dc`。
  - GREENは新規・関連59 passed。固定CLIPの3 fileは固定サイズ・SHA-256に一致し、`pytest -q -m clip_runtime --run-clip-runtime` は12 passed・1 xfailed・1828 deselected。標準offline pytestは1826 passed・13 skipped・3 deselectedだった。

### 検証

production code変更前に、profileの既知制約、改ざん拒否、label非利用、共通閾値0、score変換、欠損・較正不能、商品binding、旧schema非互換をREDで固定する。Cloudflareは注入transportだけ、商品画像は注入proxyだけで確認し、通常testでnetworkを使わない。固定ONNXは `clip_runtime` opt-inで別に再計算する。最終gateはlock、Ruff check・format、Markdown link、`pytest -m 'not live_api'`、`git diff --check` とする。

### セキュリティ・データ・互換性

候補画像・embeddingをCloudflareへ送らず、Cloudflareへ送るのはsource-groundedな確認済み視覚条件と、派生counterfactual時のdesired画像だけとする。promptへURL、商品名、商品識別子、利用者入力全文を含めない。商品画像URLは既存server-side allowlist proxyだけが扱い、score・historyへ保存しない。画像bodyとembeddingはserializeしない。暫定profileは既知の偽陽性を説明可能なmetadataとして保持するが、商品名や候補別scoreを含めない。

### 判断記録

| 日付 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-07 | accuracy 0.875の現方式を修正せず暫定本番実装へ進める | 利用者が未知条件probeの不合格を確認したうえで明示決定した | profileへ既知精度と暫定採用根拠を固定し、合格済み・最終品質保証とは表示しない |
| 2026-09-07 | 旧4方向とtyped-ranking-v4をin-place変更せず新versionを追加する | 既存approval、利用量、history、fixtureを別意味へ読み替えないため | rollbackは新profileの入口を無効化し、旧schemaをそのまま維持する |

### 発見事項

- 単純なranking flag変更では、Cloudflare参照の意味、可変call数、商品画像取得、calibration batch、history bindingが存在せず本番経路にならない。
- 1条件のcounterfactual setは2 callsだが、現行利用量契約は4 calls固定である。実使用数を過大・過小記録しない新operation bindingが必要である。

### ロールバック

暫定profileの入口と新schemaを無効化し、旧4方向Cloudflare・typed-ranking-v4・history 2.0を残す。新schemaを旧schemaへ変換せず、新しい暫定履歴は新readerなしに表示しない。途中の外部attemptがある場合は失敗分もledgerへ残し、同じreservationを再利用しない。

### 結果

完了。暫定profile、Cloudflare exact `1 + N` request・HTTP transport、可変call ledger、永続single-use reference approval、現行 `IntentReview` からのversion分岐、先頭商品画像proxy・固定CLIP evaluator、typed-ranking v5、別schema 5.0表示履歴を接続した。旧v4、旧4方向Cloudflare、typed-ranking-v4、旧履歴version 2は変更・migrationしていない。新規・関連59件、固定CLIP runtime 12件が成功し、既知case1の事前AUC未達1件は従来どおりxfailである。標準offline gateは1826 passed・13 skipped・3 deselected、lock 79 packages、Ruff 230 filesも成功した。実Cloudflare、実商品画像host、credential、課金、API、frontend、deploy、commit、pushは実行していない。accuracy 0.875は既知holdoutの暫定採用metadataであり、品質基準を合格へ変更していない。

## EXEC-067: Cloudflare基準画像1-call live準備

### メタデータ

- 状態: 完了（live 1試行は固定エラーで失敗）
- 作成日: 2026-09-07
- 最終更新: 2026-09-07
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)
- 関連要件: [FR-404](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-405](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連課題: [TD-011](ISSUES.md#td-011-画像取得推論の実環境検証)
- 先行Plan: [EXEC-066](#exec-066-counterfactual-v4の暫定本番実装)

### 目的

Cloudflare Workers AIの実通信前に、リポジトリルートの `.env` からAccount IDとAPI tokenをlive専用の型付き設定で受け取り、値を出力・保存せず、別の明示opt-inが揃ったときだけ固定合成条件の基準画像1枚を1 callで生成するlive専用境界を用意する。通常アプリとoffline testのglobal設定はfieldに値を保持・公開しない。

### 対象範囲と対象外

対象は、`CLOUDFLARE_ACCOUNT_ID`・`CLOUDFLARE_API_TOKEN`の設定契約、tokenの非表示型、固定合成intentと既存prompt-only transportを使う1-call runner、二重opt-in、retry 0、120秒transport timeout、正規化済みPNGのexclusiveな0600保存、安全な集計だけの出力、mock・offline test、文書同期である。

対象外は、承認前の実Cloudflare通信、token検証API、counterfactualの2 calls、4方向生成、自動retry、商品画像送信、実Outscraper・Bonsai・商品host、API・UI・外部委託中frontend、deploy、commit、pushである。

### 現在の状態

`.env` は0600・Git除外で、2変数が非空であることだけを値非表示で確認した。現行 `Settings` はこれらを定義せず、Cloudflare実行関数はcredentialを非保存の引数で受ける。実Cloudflare、credentialの有効性、課金、生成品質は未確認である。

### 実行手順と進捗

- [x] M1: 既存実装、Secret保存状態、開発・live検証規約、Cloudflare公式APIの最小権限を再確認する。
- [x] M2: credential非表示、必須設定、1 call、retry 0、承認selector、exclusive保存を表すoffline testを先にREDにする。
  - `tests/test_cloudflare_live_e2e.py` を先に追加し、未実装 `tools.cloudflare_live_e2e` の `ModuleNotFoundError`、exit 2でREDを確認した。RED時のtest SHA-256は `e26aff77ab2fc561c31e7712810bbec704044712cc8588f4a3a3fc51a3b6cbe1`。Cloudflare通信は0回である。
- [x] M3: 型付き設定、live runner、pytestの専用opt-inを最小実装し、focusedと関連offline gateをGREENにする。
  - live開始時だけ生成する `CloudflareLiveSettings`の `SecretStr`、Account ID検証、固定合成intent、1-call Requests transport、生応答非保存、正規化PNGの0600 exclusive作成、固定例外、`--run-live-api`・`--run-cloudflare-e2e` selectorを実装した。通常のglobal `settings` はfieldにCloudflare tokenを保持・公開しない。focusedは18 passed・1 deselected、関連回帰は135 passed・1 deselectedである。最終test SHA-256は `066d2be3d2c989e83307d0788b4b1d7a0fb91d2edb83a2131e8d266d3411454e`、runner SHA-256は `06a0d19fd5deb82570fe2b117babdbcd2f4cf140f3e229f59c98a3759fdd6030` である。
- [x] M4: 設定・security・backend・live test文書を現行実装に同期する。
  - 標準offline gateはlock 79 packages、Ruff check、Ruff format 232 files、Markdown 16 files・local link 1,365件・anchor 963件、pytest 1,844 passed・13 skipped・4 deselected、`git diff --check` で成功した。Cloudflare live testは実行していない。
- [x] M5: 実行直前の公式料金、exact endpoint、prompt要約、model、寸法、seed、1 call、retry 0、timeout、credential種別、保存範囲を提示し、別の明示承認後だけliveを実行する。
  - `@cf/black-forest-labs/flux-2-klein-4b`、512×512、seed `3006064433`、固定合成intent、1 call、retry 0、120秒timeout、4 MiB応答上限、API token、0600新規PNGだけの保存、出力1 tileの見積 `$0.000287` を提示して承認を得た。live HTTP試行は12.43秒後に固定エラー `Cloudflare E2E request failed` で終了し、PNGは作成されなかった。自動・手動の再実行はしていない。

### 検証

TDDは設定契約とrunnerを追加する前にfocused testをREDにし、同じtestを最小実装でGREENにする。通常gateは `uv lock --check --offline`、Ruff check・format、Markdown link、`pytest -m 'not live_api'`、`git diff --check` とする。live testは通常gateでskipし、`--run-live-api`と専用opt-inの両方がある場合だけnetwork guardを解除する。

### セキュリティ・データ・互換性

tokenはPydanticの非表示型とし、argv、URL、prompt、result、例外、stdout、PNG、履歴、artifactへ含めない。Account IDはexact endpoint構築にだけ使う。送信内容は固定合成intentから決定的に作るprompt-only multipartで、利用者入力、商品データ、URL、ASIN、brand、modelを入れない。既存のCloudflare production transportとcounterfactual経路は変更しない。

### 判断記録

| 日付 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-07 | 最初のCloudflare liveは基準画像1枚の1 callに分離する | live検証規約が4方向、counterfactual、負荷を別承認としている | 1 callでtransport・実応答shape・PNG正規化だけを確認し、2 calls品質検証は次のPlanへ分ける |
| 2026-09-07 | 実値は `.env` のみに置き、設定名と空placeholderだけをGit管理する | 既存の単一ホスト開発運用とGit除外・0600規約を維持する | 本番配備時は配備環境のSecret managerへ置換する |

### ロールバック

新しい設定field、live runner、pytest option、marker、空placeholderをひとまとめに取り除す。現行Cloudflare transport、counterfactual production境界、旧検索経路、`.env` の実値は変更・削除しない。

### 結果

完了。offline準備後に実行条件を再提示して明示承認を得て、Cloudflareへのlive HTTP試行を1回だけ開始したが、12.43秒後に固定エラーで失敗した。retryは0で、出力PNGは存在しない。現行runnerはtransport、非200応答、応答契約、画像検証の失敗を同じ文言へ変換するため、Cloudflareへ要求が到達したか、認証、HTTP status、応答shape、課金、生成品質のどこで失敗したかはこの記録から確定できない。原因段階を機密本文なしで残す診断改善と、その後のlive再試行は別の作業・別の明示承認とする。

## EXEC-068: Cloudflare live失敗段階診断

### メタデータ

- 状態: 完了
- 作成日: 2026-09-07
- 最終更新: 2026-09-07
- 先行Plan: [EXEC-067](#exec-067-cloudflare基準画像1-call-live準備)

### 目的と境界

初回Cloudflare live試行の固定エラーを、再実行せずに改善する。live runnerの失敗を `configuration`、`output`、`transport`、`http_status`、`response_contract`、`image_content`、`unexpected` のclosedな段階へ分類し、HTTP statusは100〜599の整数だけを安全なmetadataへ含める。credential、Account ID、URL、prompt、任意header、provider本文、生例外、画像bodyは診断へ含めない。

対象は `tools/cloudflare_live_e2e.py`、専用offline test、live testの安全な失敗JSON、関連文書である。Cloudflareへの通信、credential検証、live再試行、model・prompt・request・production transportの変更、counterfactual生成、API・frontend、commit、pushは対象外とする。

### 実行手順と進捗

- [x] M1: 初回結果、既存typed例外、HTTP projection、live規約を確認する。
- [x] M2: 各固定段階、status投影、機密値非混入、request count、retry 0、出力非作成を先にREDにする。
  - production変更前にfocused testを実行し、診断API不在と設定例外漏れにより10 failed・18 passed・1 deselectedでREDを確認した。RED時のtest SHA-256は `031049c6875d23adac34f2245d3939fdfcbeee60beba93755b70354906f5221c` である。
- [x] M3: 最小実装でGREENにし、既存Cloudflare回帰と標準offline gateを確認する。
  - 固定messageを維持した `safe_metadata()`、typed例外分類、検証済み非200 status、送信後の出力失敗count、live testの安全な失敗JSONを実装した。focusedは31 passed・1 deselected、既存request・HTTP・counterfactual回帰を含む関連確認は124 passed・1 deselectedである。標準offline gateは1,857 passed・13 skipped・4 deselected、lock 79 packages、Ruff 232 files、Markdown 16 files・local link 1,367件・anchor 965件、`git diff --check` で成功した。
- [x] M4: security、development、backend、changelog、worklog、next stepsを結果へ同期する。

### 判断記録

| 日付 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-07 | provider本文ではなくclosed stageと検証済みstatusだけを残す | 認証・契約診断に必要な最小情報と機密非保持を両立するため | 詳細本文が必要な場合も自動保存せず、別の承認済み手順を設計する |
| 2026-09-07 | 診断実装ではliveを再実行しない | 初回承認は1 call・retry 0に限定されていたため | 新しいlive試行は条件と費用を再提示した別承認後だけ行う |

### 結果

完了。最終runner SHA-256は `69cbe04fec618501e2a0a27dda3ed41bd78195c0c446336d0b5c5716b5cb93be`、test SHA-256は `78d8681961759412fa19d9a4237be0fe3455f314a240423039533ec5cb3a6449` である。標準offline gateを含む全検証が成功した。初回liveの再実行は行っておらず、過去の固定エラーへ新しいstageを推測で割り当てていない。次のlive試行では安全なstageと、取得できた場合だけ検証済みHTTP statusを観測できるが、再実行には改めて条件・費用提示と明示承認を必要とする。

## EXEC-069: Cloudflare live画像内容診断

### メタデータ

- 状態: 完了（修正未実施）
- 作成日: 2026-09-07
- 最終更新: 2026-09-07
- 先行Plan: [EXEC-068](#exec-068-cloudflare-live失敗段階診断)

### 目的と境界

段階診断を使う追加1 callの条件、credential、費用見積を再提示し、別の明示承認後に通信を1回だけ行って初回固定エラーの原因段階を絞る。送信先はCloudflare Workers AIの `@cf/black-forest-labs/flux-2-klein-4b`、入力は固定合成条件「白い無地の陶器製マグカップ」、512×512、seed `3006064433`、retry 0、timeout 120秒、応答上限4 MiBである。商品、利用者入力、URL、識別子は送らず、生要求、生応答、画像body、credentialを保存・表示しない。成功時だけ新規0600 PNGを `/tmp` に保存する。

この項目は通信診断であり、provider応答の受理形式、production transport、counterfactual生成、API、frontendは修正しない。追加のlive試行と自動再実行も行わない。

### 実行結果

- 承認済みの専用live testを1回だけ実行した。28.246秒後に `failure_stage=image_content`、`request_count=1`、`retry_count=0` で失敗し、出力PNGは作成されなかった。
- このstageは、transportからtyped responseが戻り、HTTP status 200とexact success envelopeを通過した後、Base64文字列からlocal画像artifactを作る境界で発生した。安全なmetadataの `http_status_code=null` は非200 statusを記録するfieldが該当しないことを表し、status不明を意味しない。
- `image_content` は、Base64長・decode後byte長の2 MiB上限、raw PNG判定、512×512、単一frame、完全decode、metadataなしRGB PNGへの再encode後上限をまとめた段階である。生応答を保持していないため、実応答の画像形式、byte長、寸法のどの条件だったかは断定しない。
- Cloudflare公式の[モデル仕様](https://developers.cloudflare.com/workers-ai/models/flux-2-klein-4b/)は成功結果をBase64画像として定義するが、PNG形式は保証していない。[公開時の利用例](https://developers.cloudflare.com/changelog/post/2026-01-15-flux-2-klein-4b-workers-ai/)も寸法指定は示すが応答画像形式を固定していない。対してlocal実装はPillowを呼ぶ前にPNG signatureと寸法を要求し、`Image.open(..., formats=("PNG",))` へ限定しているため、provider契約より狭い。
- 外部通信なしで512×512のJPEGをexact success envelopeへ入れ、現行parserへ渡したところ、同じ `CloudflareImageError` になった。これはPNG限定が今回と同じstageを再現することを示すが、保持していない実応答がJPEGだったことの証明ではない。

### 判断

通信、認証、endpoint、HTTP成功応答、JSON成功契約までは動作した。直接の停止原因はlocal画像内容検証である。確認できた設計上の原因は、公式契約がBase64画像までしか保証しないのに、受信raw画像をPNGへ限定していることである。今回の実byteを保持していないため、個別の根本条件は「非PNGが最有力」であり、2 MiB超過、512×512以外、複数frame、破損も完全には除外できない。

修正する場合は、入力byte上限を維持してJPEG・PNG・WebPを非信頼入力として完全decodeし、単一frame・exact 512×512を検証してからmetadataなしRGB PNGへ正規化する。先に各形式、oversize、寸法違い、複数frame、decompression bomb、破損のoffline RED/GREENを行い、その後の実通信は条件と費用を再提示した別承認1 callにする。

## EXEC-094: 省略された仕様名の推論を改善する

- 状態: 進行中
- 作成・更新: 2026-09-09
- 関連: [EXEC-093](#exec-093-原文の事実と属性推論を分離する)、[検索専用属性の実データ品質](ISSUES.md#検索専用属性の実データ品質)

### 目的・範囲・現在地

利用者の修正続行指示を受け、数値仕様へ別条件の名前を割り当てる問題を解消する。対象はsource_constraints.py、Bonsaiの要求と応答adapter、固定prompt、対応する回帰と診断である。EXEC-093の原文事実保持は維持する。既知14例は開発例として扱い、期待名やカテゴリ別辞書を本番へ追加しない。未知カテゴリ全体の精度とrankingは未確認である。

### 手順・検証・判断

保存応答と実装を確認し、同じローカルmodelに単純な仕様質問を送る診断で、知識不足と要求形式の影響を切り分ける。比較する要求・採点基準・source/model hashを送信前に固定する。原因に対応する契約のREDを先に追加し、同一テストでGREENを確認する。既知の名前省略例を基準変更なしで実測し、改善を確認した設定を別の未使用入力で評価する。通常offline全体、Ruff、lock、Markdown、diff検査を実施する。診断用の異なるwireの成功を本番経路成功と扱わない。

### 授権・保存・互換性・rollback

既存の継続授権により、localhost:18080のBonsai-8B、各1 call・retry0・最大900秒、context8192・parallel1、応答1 MiB、無認証・API費用0で実測する。各実行直前に入力・回数・新規private保存先を通知し、成功・失敗の全応答を0700/0600で保存する。外部provider・画像・全検索・委託frontend・commit/pushは対象外。要求変更はdigest/preflightへ結び、古いprepared要求や既存履歴を書き換えない。変更前snapshotを保存し、rollbackは本作業の差分のみ戻す。

### 進捗と結果

EXEC-093の最終実装を確認した。前回の/tmpログは現環境に残っていないため、過去値を今回の再現結果として扱わない。新規snapshotと事前manifestを用意し、通常回答・JSON・対象条件分離・説明先行・英語経由・数量値除去の診断18 callsを実行した。既知の顕微鏡・スキャナー・掃除機3例はいずれの方式も日本語名の固定基準へ未達。英語だけの別基準の知識診断3 callsは1/3であり、本番の合格には数えない。すべて完全HTTP応答をprivate保存した。最初のmanifest比較はtuple/listの表現差で生成前に停止し、0 callsを別記録してJSON値の比較へ修正した。

同一model SHA-256で現在の本番経路7例を新規実測し、2/7が合格した。元の判定器・期待名は変えていない。共通の重量1例で「値」と「仕様表の項目名」の違いを示す候補promptを作り、関連offline105 passed・14 deselectedを確認した。同じ7例の再測定は3/7で、電動ドライバーの仕様名が改善した。カテゴリ固有の正解名は追加していない。実測合計時間は72.09秒から93.75秒へ増え、速度改善ではない。追加の仕様一覧生成診断3 callsも0/3で採用しなかった。


仕様名の展開境界へ、日本語文字の有無と原文boolean属性名の流用検出を追加した。新規testのREDは7 failed・5 passed、同じ内容を含むsource contractとのGREENは63 passedだった。Latin略語を含む日本語名と明示数量の別の上下限は許す。HTTP応答からusage失敗へ閉じる2回帰も追加した。RED時test SHA-256は7603a2a36b47685009ce0c6c7b1292d00f1665a46857c686497d5d423da621f8。

別の未使用2入力を実測した結果は0/2（56.71秒）。除湿機は仕様名が基準未達、ポータブル電源は「急速」が形状詞であるため既知の機能句を拒否し、名前推論に入らずblockingへ進んだ。これはmodelの名前推論とは別の解析不具合である。品詞単位で複合名詞を扱うため_name_is_explicitへ形状詞を加え、特定の単語は登録しなかった。「急速・簡易・柔軟」の再現3 failed・17 passedから同じ20件をGREENにし、未解決の文・否定作用域を拒否する境界を維持した。このRED時と最終testのSHA-256はff1df989f346da816e55cfdff9d0d4180f18a275a6b6131d03ab80768f0eef70。新しい評価fixtureの説明文2件は採点patternへ一致していなかったため、初回通信前に参照fixtureを訂正してからcriteriaを固定した。実応答を見て基準を変更していない。

修正後のポータブル電源1回は13.90秒で、商品・数値条件・急速充電の希望・2条件のreadyを保持できた。ただし仕様名は既存基準に合格せず、1 failedのまま記録した。観測済み入力の開発再試験であり未知評価ではない。最終backendへ同一request bodyの実応答9件をoffline再投入すると3/9で、日本語文字を含まない1件は拒否した。この再投入の生成callは0。

### 最終検証と残作業

- 全体offline: `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は2322 passed・13 skipped・30 deselected（50.66秒）。新規の名前検証・形状詞・holdout参照を含む73 focusedも成功した。
- TDD: `uv run --frozen --offline --no-sync pytest tests/test_bonsai_name_validation.py -q --tb=short` のRED exit1を確認。GREENは同じtestを含む `uv run --frozen --offline --no-sync pytest tests/test_bonsai_name_validation.py tests/test_bonsai_source_contract.py tests/test_bonsai_quantity_holdout.py -m 'not live_api' -q --tb=short` の73 passed・exit0で確認。名前検証7件と形状詞3件の失敗理由は上記。実Bonsaiの意味基準は不合格を残し、緩和・xfailへ変更しない。
- live: 診断24、変更前後比較14、初回2、開発再試験1の計41 calls、各retry0。全41応答HTTP200・完全受信、private権限0700/0600と最後のport18080非listenを確認した。全検索・画像・ranking・委託frontendは実行していない。
- 静的検証: lock79 packages、Ruff check・format281 files、Markdown16 files・1547 local links・1137 anchors・2010 headings・216 fence pairs、Python 3.10構文274 files、git diff --check成功。
- 保存: /home/products/bonsai-test-logs/20260909-exec094 に全応答・入力別manifest・判定・最終source・offline再投入結果を保存。/tmpに生成した38応答はhash一致を確認してコピーし、その後の3応答は直接永続保存した。過去EXEC-093の消失した/tmpログを復元したとは扱わない。
- 互換性: request 9.0とwireは維持。固定promptのdigest/body照合で旧準備要求を拒否する。既存cache・表示履歴・共有属性registryは変更しない。rollbackは開始時snapshotとの差分と追加3 test/tool filesのみを対象とする。
- 残作業: 倍率・枚数・解像度・吸引仕様・電源容量・除湿能力の命名と意味を安定させる品質は未達。この16入力は全てdevelopmentへ移す。型・品詞の修正や共通例1件による限定改善を根本的な意味理解の解決とは扱わず、Planは進行中のままとする。追加のカテゴリ別辞書や正解例の継ぎ足しは行わない。


### 継続検証（2026-09-09）

利用者の続行指示により、原文事実の保持を維持したまま、概念の推論と日本語の仕様名への整形を分けて検証する。既存16例の期待名・judgeは変更しない。保存済みモデル候補を見直す1 callの診断と、同じ応答内で仮名・確定名を順に出す診断を比較する。成功した診断を本番成功とは扱わず、本番要求・strict adapter・usage境界で再測定してから採用する。保存先は /home/products/bonsai-test-logs/20260909-exec094-continuation-01 の新規private子directoryとする。

Q1量子化dot productのSIMDとgeneric実装を合成200例で比較した。最初の単独FFI診断はCPU初期化を呼んでおらず、FP16 lookup tableが未初期化だった。実serverが使うggml_cpu_initを呼ぶ修正版では両実装とも明示計算との最大絶対誤差0であった。これはdot productの限定確認であり、全modelの数値精度や推論品質の保証ではない。runtimeやmodelは変更していない。


継続検証の結果:

- 保存済み候補の見直しと、仮名から確定名を出す診断は各3 calls、いずれも0/3。採用しない。元の入力・数量事実と保存済み候補だけを渡し、期待名は要求へ入れていない。
- 受信時に日本語文字を要求する一方、生成schemaが英字だけの名前を許す不整合を修正した。カテゴリ別辞書・追加正解例は使わず、最初の日本語文字の位置を分岐し、各分岐に100文字上限を持たせる。JSON境界文字と単位そのものを除外する。単位に含まれる単一文字のUnicode大小文字差も生成側で除外した。
- REDは言語契約の20 failed・28 passed。テストSHA256 adb8b9a04f9434a1695021b3b13e49140051ac9e7630c56503b7424f5dd65b1f のままfocused99 passed。追加のUnicode単位2例は2 failed・4 passedから修正し、最終focused101 passed（1.28秒）。最終テストSHA256 a14810081ce452cc5f6041e98388a4c03ac747e4d651f5989adab37697e6bdcf。
- 実llama.cpp converter/grammarは初回60/60、Unicode単位追加後84/84。正常名・略語入り日本語・100/101文字・単位・不正JSON文字を確認した。有限文字列補集合の10,300例は最初にUnicode単位の大小文字差1件を検出し、修正後0不一致。最初の失敗記録も残す。
- 最終生成契約による既存9例は3/9、119.41秒。各1 call・retry0で全HTTP200・完全受信。合格は投影機器・電動工具・圧縮機器の3例で、以前の最終9件再投入と同じ3/9。全9件readyだが、6件は意味品質不合格。スキャナーでは英字に別機能名を付け加えて文字制約だけを満たした。この修正は形式契約の整合であり、意味精度の改善や不適切な名前の完全排除ではない。最後のUnicode修正前後で9件のrequest metadata/bodyは全て一致した。
- この継続作業の生成は計15 calls（診断6、本番要求9）・各最大900秒・応答1 MiB・無認証・API費用0。全15応答を /home/products/bonsai-test-logs/20260909-exec094-continuation-01 へ保存。全file0600・directory0700、所有server停止・port18080非listenを確認した。manifest、全成功/失敗応答、native検査、最終source・要求一致・権限監査を含む。前回41 callsと混同しない。
- 最終offline2352 passed・13 skipped・30 deselected（49.24秒）、Ruff check・format281 files・lock79 packages成功。意味品質の根本解決は未達で、EXEC-094は進行中を維持する。既存16例は観測済みのままで、新規holdoutや全検索・ranking評価は実施していない。

## EXEC-093: 原文の事実と属性推論を分離する

- 状態: 構造修正・検証完了、未知仕様名の意味品質は未達
- 作成・更新: 2026-09-09
- 関連: [検索専用属性の実データ品質](ISSUES.md#検索専用属性の実データ品質)

### 目的・原因・対象

利用者の根本修正指示に従う。EXEC-092の誤りは、原文で確定した数値・単位・比較方法・希望/除外まで自由生成し、誤りを後処理で削除する構造から生じた。生成schemaは型の整合性だけを保証し、原文との不変条件を表していない。意味説明も原文の属性名とは別に自由作文させ、属性定義を変質させていた。

単一のBonsai呼出しの前に、Sudachiの原文境界を使うカテゴリ非依存の事実抽出と、入力に束縛した生成schemaを追加する。明確な数値条件と対応可否は、原文引用・値・単位・演算子・強さを固定する。明示属性名の定義は原文の属性名と型・単位から構成する。属性名が省略された場合はBonsaiが推論する。生成時の制約だけを信用せず受信後にも同じ原文契約を検証する。既存共通registryの語彙やカテゴリ別例を追加しない。provider・呼出し回数・画像・frontendは変えない。

### 実行・検証

原文から明確に確定できる条件と、OR・否定作用域などの曖昧な表現を分離し、曖昧な箇所の推測補完はしない。原文値の改変・機能除外の反転・希望の昇格・条件欠落・別原文からのschema流用を再現するREDから始める。実llama.cpp文法変換でも改変応答の拒否を確認する。EXEC-092の8例はdevelopment回帰として再使用し、成功判定を緩めない。別の未使用カテゴリを初回評価へ使う場合は、送信前に入力と基準を固定する。

### 授権・互換性・保存

継続授権によりlocalhost Bonsai-8B、各1 call・retry0・最大900秒、認証不要・費用0で実測する。全応答は新規private log（directory0700・file0600）へ保存し、各回の入力・件数・保存先を事前通知する。外部provider・全検索・ranking・委託frontend・commit/pushは対象外。request versionを更新して古いprepared requestの再利用を拒否し、既存履歴・商品cacheは書き換えない。変更前sourceのprivate snapshotを残す。rollbackは今回の差分だけを戻し、保存済み評価を保持する。

### 状態と制約

生成時の原文不変条件10件をREDから実装した。原文にない共通属性も拒否する追加RED、任意の数値・単位・強さ、受信時の契約違反・利用量失敗を含む26回帰が成功。実llama.cpp文法で正常応答accept・数値改変rejectを確認した。最初の文法用exportはJSONの辞書順ソートでfield順を変えていたため、実要求どおりの順序を保ったexportへ訂正した。本番では従来どおりproperties順を保持する。初回全体offlineは71 failed・2182 passedで、旧wireの条件省略fixture、旧version期待、不正条件を削除してreadyへ昇格する旧期待が新しい契約へ適合していなかった。fixtureを明示条件保持へ更新し、不正応答をprovider失敗へ閉じる期待に変更した。互換回帰162 passed、続く全体2265 passed・13 skipped・22 deselected（48.88秒）。

実装はsource_constraints.pyに置き、数量の以上/以下/以内、希望/除外、肯定・非対応、明確な接続助詞をSudachi境界で扱う。既存共通enumも原文aliasだけを許可し、生成arrayの全位置を固定する。明示ラベルのmeaningは原文ラベルと数量単位または可否から構成し、省略ラベルとそのmeaningだけをBonsaiに推論させる。OR、未解析の数量作用域、複数共通値の関係はblockingへ限定する。定数制約は原文から生成し、期待回答や採点器から生成しない。完全schemaのstrict parser後にも未加工の応答を原文契約へ照合し、欠落や値の改変を固定エラーで拒否する。

旧8例の入力・判定器はEXEC-092から変えず、新規developmentログへ再実行する。別のシュレッダー・プロジェクター・電動ドライバー・スキャナー各1件は全て数量の属性名を省略し、推論labelが要求bodyへ含まれないことを確認した。未使用4例の8事前fixtureも成功してから、全source/prompt・判定器・model・入力別request/schema digestを固定した。各8 callsと4 calls、retry0、ログ先は /tmp/amazon-explorer-bonsai-source-development-20260909-01 と /tmp/amazon-explorer-bonsai-source-holdout-20260909-01。

カテゴリに依存しない明示的な言語構文の範囲を固定し、対応しない表現を成功と主張しない。入力事実の保持と、省略された属性の意味推論の品質は分けて測る。標準offline gate・lock・Ruff・文書検証後に完了判断する。


最初のdevelopment 8例は7 passed・1 failed（412.60秒）、18/19条件。全HTTP 200・完全受信・各1 call・retry0・所有server停止、固定source/hashと判定器不変を確認した。明示値・単位・希望/除外の誤りは解消したが、顕微鏡の省略属性名を単位名の「倍」としたため既存基準へ未達だった。

この結果を受け、省略属性ではmeaningを先に生成してからlabelを選ばせ、labelを単位そのものと同一にできない一般的な制約を追加した。llama.cppが未対応のnotやlookaheadには依存せず、単位文字列の補集合を有界regexとして構成する。大文字小文字違いも拒否し、受信時はNFKC/casefoldで再検証する。単位名のRED1件と追加RED3件を確認し、整数wireの範囲を超える原文値を桁変換せずdecimal文字列で保持する修正も行った。対象26→30回帰とholdout fixture・関連request回帰の計132件が成功した。実文法でも妥当な属性名を受理し、単位名と大文字違いを拒否した。

末尾02の顕微鏡再測定は1 failed（47.69秒）。文字列patternをllama.cppがraw JSONへ変換する際、引用符を通して不正なfield構造を生成できた。実際の失敗応答を旧文法が受理することを再現し、全regex分岐で引用符・escape・制御文字を拒否して修正文法のrejectを確認した。追加RED4件を含む文字列境界回帰も成功した。末尾03は1 failed（46.15秒）で、構造は直ったが別条件の属性名を流用した。manifest準備時のfield参照誤りと、server起動前のpytest失敗も別記録し、この準備失敗の生成callは0である。

数量・単位・引用を先に出す順序へ変えた末尾04の顕微鏡は1 failed（47.11秒）。条件値を保持してreadyだが、属性名が既存基準へ未達だった。同設定の新規4例は1 passed・3 failed（185.81秒）、5/8条件で初回の意味推論基準へ不合格。全条件の値・単位・強さは保持された。シュレッダーは数量そのものへの誤解、スキャナーは上限名と希望を混ぜた説明があり、プロジェクターは英語のbrightness表現で日本語名の基準へ未達だった。未実行のholdout末尾01・02・03は送信0件を記録し、実測は末尾04だけである。

意味の自由作文と原文条件の保持を分離するため、数量の省略属性はwireでsource_quote・label_jaだけを生成し、compact adapterが仕様名・単位から完全なmeaningへ展開する構成にした。未解析の追加仕様を黙って削除できる回帰もREDからblockingへ修正した。名前だけへ制限し旧抽出promptを使った5例は0 passed・5 failed（226.06秒）で、名称に数値条件をそのまま入れる誤りが残った。

そこで省略仕様名のある入力だけを、固定のbonsai_attribute_name_prompt.txtによる商品知識の推論へ分ける。値と条件はcompilerが所有し、Bonsaiの担当は日本語の仕様名だけとする。選択された実promptをprompt/body digestと送信前検証へ結び付ける。元の7例は最終bodyが初回と一致する。既知5例を /tmp/amazon-explorer-bonsai-source-name-development-20260909-02 へ、新しいコンプレッサー・掃除機の2例を /tmp/amazon-explorer-bonsai-name-holdout-20260909-01 へ、同じ生成上限とprivate保存契約で事前固定した。元の8例・4例の採点器は変更していない。


専用promptで旧wireを使った末尾02は0/5（121.79秒）、名前を先に生成した末尾04も0/5（127.77秒）で、指示とfield順だけの変更では改善しなかった。途中の全体offlineは51 failed・2240 passedで、未解析句のblockingが既存の語句条件と後置商品名まで拒否していた。この範囲を修正し、数値仕様の後置商品名を回帰へ追加した結果、125 focused、全体2292 passed・13 skipped・28 deselected（47.22秒）となった。未送信の末尾03は送信0件を記録した。

最終設計では、Bonsaiから固定数値の再出力自体を除き、仕様名だけの応答を原文の事実と結合する。最小応答の初回顕微鏡1件は10.24秒で数値条件を名前にしたため拒否した。実modelのembedded chat templateとllama.cppのJinja既定を読み、明らかな不一致や環境overrideがないことを確認した。model/runtimeは変更していない。さらに推論対象をunnamed_quantitiesとして入力へ明示し、商品知識から仕様名を特定する固定promptへ分けた。Bonsai自身に「どの句を推論対象にするか」と「既知の値を転記すること」を重ねて要求しない。原文と数量句をJSON dataとして送り、完全応答のprovenanceは元HTTP bodyへ結ぶ。

model-projectionの表示だけを新wireの原文事実展開へ対応させた。元の8例・4例の入力・期待値・judge/checks・pytest合否基準は変更していない。原文事実・meaningの構成を、Bonsaiが生成した精度と混同しない。新しいコンプレッサー・掃除機は依然未観測のまま同一criteriaで再固定し、未実行の各ログrootに送信0件を記録する。


### 最終結果と残る課題

最小応答と推論対象の明示を使った末尾06の既知5例は1/5、6/10条件（顕微鏡9.38秒＋残り4件37.18秒）だった。名前の誤りは残り、数量・単位・演算子・強さをmodelに再生成させないことと、名前を正しく推論できることは別である。配布元の[生成設定](https://huggingface.co/prism-ml/Bonsai-8B-gguf#best-practices)に合わせたtemperature0.5・top-k20・top-p0.9と、この診断用seed0の比較も1/5（46.39秒）で改善を確認できなかったため採用せず、既存temperature引数とruntime既定を維持した。

最終的に、単位・数値・数値比較句・商品名自体を推論属性名として受理しない回帰を追加し、原文事実を持つ新wireだけを受け入れる。既知12例は同一request bodyの保存実応答を最終backendへoffline再投入し、8/12が既存基準に合格した。元の8例は2/8から7/8へ改善したが、この7件は初回development実応答の再利用であり、全件を最終コードで再生成したとは扱わない。顕微鏡・シュレッダーの名前は品質未達、電動ドライバー・スキャナーの不適切な名前は最終adapterで拒否した。新規model callは0である。

未使用のコンプレッサー・掃除機各1件は、最終source・prompt・入力別request・criteriaを固定した /tmp/amazon-explorer-bonsai-name-holdout-20260909-07 で初回実測した。1 passed・1 failed（19.36秒）、3/4条件。コンプレッサーは容量として合格し、掃除機は数値仕様に別の機能名を使ってregistryの整合性を満たさず確認待ちとなった。単一設定の2例であり、未知カテゴリ全体の精度や実商品rankingを保証しない。

この作業の生成は合計43 calls・各retry0。43応答全てHTTP200・完全受信で、各private directory0700・file0600を再確認した。失敗応答と準備時の送信0件も保存し、未使用ログを上書きしていない。最後のport18080非listenを独立確認した。最終offlineは2300 passed・13 skipped・28 deselected（47.49秒）、lock79 packages、Ruff check・format278 files成功。最終ソース不変と12例の再投入結果、全ログ権限の監査は /tmp/amazon-explorer-bonsai-source-final-20260909-01 に保存した。仕様名の品質不足は未解決のまま明記し、全検索・画像・外部provider・委託frontend・commit/pushは実行していない。 Markdown16 files・1542 local links・1132 anchors・2002 headings・216 fence pairs、Python 3.10構文272 files、git diff --checkも成功した。


## EXEC-092: 未使用4カテゴリの属性推論精度を測定

- 状態: 初回精度測定完了、事前品質基準に不合格（2026-09-09）
- 作成・更新: 2026-09-09
- 関連: [検索専用属性の実データ品質](ISSUES.md#検索専用属性の実データ品質)

### 目的と範囲

利用者の「未知カテゴリの精度を確認しろ」に従い、既知6入力とprompt例を除き、テント・ミシン・プリンター・顕微鏡を各2入力で初回評価する。現行のモデル・prompt・schema・adapterは変更しない。未知とは今回の開発評価で未使用という意味であり、モデルの学習データ未収録を意味しない。実商品rankingのholdout評価とは独立した属性推論診断である。

### 事前基準と実行順序

入力、期待属性・意味・値・単位・演算子・強さを新規診断moduleへ定義し、モデル応答を見る前に固定する。全条件一致・余計な条件なし・商品種別一致・ready proposal・共有registry不変を1入力の合格条件とする。合格基準は8/8完全成功かつ全条件成功とし、失敗・応答不能も分母から除外しない。カテゴリ別2件、入力別、条件別の結果を分けて集計する。意味のregex判定と内容確認が食い違う場合は補足を別保存し、自動判定を上書きしない。

テスト用の正常・改変fixtureを先に確認する。受入可能なfixtureを作るためにproduction側を修正しない。private parentへ基準・source/model/prompt等のdigestを保存してから、既存run_inference_probeを通じて各1回送る。測定途中でモデル・prompt・adapter・判定器を変えず、再送しない。全応答を記録した後、保存応答の限定投影から原因を分類し、全体offline gateと文書確認を行う。

### 授権・保存・制約

継続授権のあるlocalhost Bonsai-8B単体診断。127.0.0.1:18080、8 calls・各retry0・各最大900秒、1 MiB応答上限、認証不要・API費用0。実行前に入力・範囲・保存先を提示する。全生成応答を新規 `/tmp/amazon-explorer-bonsai-unseen-20260909-01` へ保存し、directory0700・file0600、旧ログ上書き禁止を維持する。外部provider・画像・全検索・委託frontend・commit・pushは対象外。既存履歴・registry・cacheの変更はない。

### 結果と再評価

実行前の評価器テストは44 passed・8 deselected。正常fixture、欠落・意味・真偽・強さ・数値上下限・単位・余計な語句を確認した。最初の8 failuresは正規化時に付加される原文由来termsも禁止していた評価器の不備で、原文にないtermsだけを拒否するよう事前に修正した。本番コードの変更はない。8入力・19条件のcriteriaと全search_v2 source・prompt・診断・modelのmanifestをprivate parentへ固定し、EXEC-091最終sourceとの一致を確認して実測を開始した。初回評価後はこの8例も使用済みとして扱う。追加修正に使う場合はdevelopment setへ移し、未知精度の再評価には別入力を必要とする。診断追加を取り除く場合もprivate結果は保持し、本番コードのrollbackは不要である。


実測は6 failed・2 passed、384.25秒。8要求全てHTTP 200・完全受信、各1 call・retry0・所有server停止。完全合格2/8（25%）、正規化後の条件合格11/19（57.9%）、モデル提案時も11/19。カテゴリ別はテント1/2・4/5条件、ミシン1/2・4/5条件、プリンター0/2・2/5条件、顕微鏡0/2・1/4条件。readyは4/8で、そのうち2件は意味定義の事前基準を満たさなかった。全件成功という基準は未達である。

テントの耐水圧とプリンターの給紙枚数・自動両面印刷は、属性名と値は正しい一方、meaningが測定単位の説明、給紙という対象の省略、自動という意味の省略となり不合格だった。これは固定語彙による意味判定を含み、独立した人間の意味評価ではない。ミシンは希望→required、プリンターは無線LANのtrue・excluded→false・excludedを生成。顕微鏡は倍率40倍を幅40mmへ置換し、入力にない形状・向き・styleを生成した。もう1件は重量2kg以下を2000kg以下へ誤り、入力にない色も追加した。後4件は不適切な条件が正規化で除外され、blockingとなった。

全生成応答に加え `assessment.json` と `content-review.json` をprivate parentへ新規保存した。source・prompt・判定器の固定hash不変、directory0700・file0600、全server停止・最終port18080非listenを確認した。測定中も測定後も本番コード・prompt・判定基準は変えず、再送は行っていない。未使用4カテゴリの限定初回結果であり、母集団全商品の精度ではない。今後この8例を修正へ使う場合は未知評価として再利用しない。


最終offlineは2239 passed・13 skipped・22 deselected、49.43秒。lock・Ruff check/format・Markdown・git diff --checkも成功した。測定という作業は完了したが、属性推論の品質改善は未解決としてISSUESへ引き継ぐ。


## EXEC-091: 5入力の失敗箇所を修正し再試験

- 状態: 既知5例と既存マグカップの改善後実試験に合格（2026-09-08）
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)

### 方針と授権

利用者の「試行と改善を繰り返せ」と既存のローカル属性推論の継続授権に従う。EXEC-090の5例はdevelopment setとして固定し、目標の意味・条件数・強さは変えない。各試験はBonsai-8B、loopback18080、各1 call・retry0・最大900秒、認証不要・費用0。全生成応答と判定を新規private logへ保存し、旧結果を上書きしない。外部provider・画像・全検索・ranking・委託frontendへ広げない。

### 初回修正

- 共通形状の丸形へ「丸い」を追加し、共通registryをv4へ更新した。カテゴリ固有プリセットは増やしていない。
- inch・inches・インチを同じ大きさの単位表記として原文照合・検索専用registry・商品仕様評価へ接続した。数値を変更する単位換算はせず、cm等の別単位へのすり替えは拒否する。未知の単位は従来の原文一致を維持する。
- ヘッドホン評価器で外部音のキャンセリングを同義として認め、否定の意味を拒否する回帰を追加。事前基準の意味を変えず、初回の自動0/5と内容確認1/5は元ログへ残す。
- 再現回帰は4 failed・19 passedから修正を開始した。丸い・同値インチ表記・同義意味の偽陰性と、否定意味の偽陽性を対象とした。単位aliasの追加中に℃の大文字小文字が重複した回帰を修正し、未知単位は従来のalias生成を維持した。
- モデルへの指示は材質・形状の欠落防止、商品名を単位にしないこと、対応可否を件数にしないこと、trueの対応をexcludedで除外することを明記した。診断5例と異なるカメラを使い、数値上限・希望・除外を示す4条件例へ変更した。既存要求17,000 bytes上限と生成schemaの型別operator制約を維持する。

共通registryと動的単位aliasの定義digestが変わるため、古い承認・prepared requestを再利用しない。既存保存履歴や商品cacheは書き換えず、新規の推論・proposal・承認から始める。成功した回だけを残して評価しない。

### 実試験

最初の修正後5例は `/tmp/amazon-explorer-bonsai-examples-20260908-02` へ事前基準・manifestと各caseの応答・処理前後・判定を保存して実行した。

02は2 passed・3 failed、328.25秒。テーブルとモニターは合格、リュックは3条件を保持したが撥水の説明に対する語彙判定、ヘッドホンは時間→hours表記の照合、キーボードは除外対象のfalseが不合格だった。全5例でHTTP 200・1 call・retry0・server停止を確認した。

次にhour・hours・時間の同値表記を追加し、数値換算をせず原文照合と商品仕様評価へ伝える。撥水の説明は表面が濡れることを防ぐという意味も認める一方、防水・浸水・水中保護との混同を拒否する回帰を追加した。これは定義の表現に対する評価器の修正で、対象属性・真偽値・数値・単位の大きさ・強さを緩和するものではない。追加3回帰のREDを確認した。

customの生成順序は属性キー・定義・strength・operator・値へ変更し、除外対象の値を生成する前にexcludedを確定させる。生成JSONに妥当なfalse・excludedを表せる能力は残し、特定入力の値を後処理で反転しない。文法順序の回帰6件でREDを確認し、同じ意味のfixtureを新しいwire順で生成できることと、実llama.cpp文法が新prompt例を受理することを確認した。生成schema SHA-256は `415728a8c74f59373994d18b8e16f65750c90d8a0c6f10c150630f77a89dc2e6`。

03はまずkeyboardを1回再試験し、1 passed・68.41秒、要求65.320秒、prompt1186・completion164 tokens、1,476 bytes。バックライトtrue・preferredとBluetooth対応true・excludedを保持し、3条件・custom2件・readyを含む全項目が合格した。同じ03 manifestの設定で残り4例も4 passed・312.54秒。最終設定の5例全てでモデル提案と正規化後の全条件が合格し、source/prompt/判定器の事前digest不変、HTTP 200・完全受信・各1 call・retry0・所有server停止、0700/0600を確認した。要求処理時間はtable53.125秒、backpack66.045秒、headphones69.573秒、monitor114.240秒。既知5例のdevelopment regressionであり、独立holdoutや実商品rankingの合格ではない。


同じ最終設定で元のマグカップ1件も既存9項目へ合格した（1 passed・72.05秒、要求68.387秒、prompt1182・completion169、HTTP 200・1,434 bytes、1 call・retry0）。全応答と診断を `/tmp/amazon-explorer-bonsai-attributes-20260908-06` に保存し、完全受信・0700/0600・全server停止・port18080非listenを確認した。この作業の実推論は途中5件＋最終5件＋既存1件の計11 calls。全応答を保存し、失敗結果を取り除いていない。


最終標準offlineは2195 passed・13 skipped・14 deselected、79.35秒。既知tableのxfailは解消した。lock79 packages、Ruff check・format270 files、Markdown検査、git diff --checkも成功した。


## EXEC-090: 別カテゴリ5入力の実Bonsai単体検証

- 状態: 5件の実試験完了。自動基準0/5、内容確認1/5（2026-09-08）
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)

### 対象と事前基準

利用者の「他の入力例でも成功するか試せ」に従い、EXEC-089で合格したprompt・model・生成schemaを固定して5件を各1回検証する。前の作業でのローカル属性推論テストの継続授権を適用し、追加承認質問はしない。モデル・promptの調整を測定途中に行わず、初回結果を記録する。これらは新規合成診断例であり、独立した実商品holdoutや統計的精度評価ではない。

| case | 合成入力 | 期待する条件 |
|---|---|---|
| table | 丸い木製テーブル。 | 丸形・木材をrequired、2条件、custom0件 |
| backpack | 青いリュック。容量20L以上。撥水対応。 | 青色・容量下限20L・撥水trueをrequired、3条件、custom2件 |
| headphones | 黒いヘッドホン。連続再生時間20時間以上。ノイズキャンセリング対応。 | 黒色・再生時間下限20時間・ノイズキャンセリングtrueをrequired、3条件、custom2件 |
| monitor | 白いモニター。画面サイズ27インチ以上。VESA対応。 | 白色・画面サイズ下限27インチ・VESA対応trueをrequired、3条件、custom2件 |
| keyboard | 黒いキーボード。バックライト対応を希望。Bluetooth対応は除外。 | 黒色required・バックライトtrue preferred・Bluetooth対応true excluded、3条件、custom2件 |

共通の合格条件は商品種別、全条件の型・値・単位・比較方法・強さ・custom定義の限定語彙による意味確認、条件数、検索専用属性数、ready proposal、共有registry不変、入力外のterms・価格・brand等がないことである。商品種別・属性名の許容同義語と意味判定regexは `tools/bonsai_inference_examples.py` へ実送信前に固定する。不合格を見て語彙や件数を緩和しない。

事前の合成応答検証で、tableはモデルがroundを正しく返しても「丸い」を原文照合できず落とす問題を確認した。fixture試験はstrict xfailとして既知の未解決を記録し、実試験の合格条件は丸形を保持するままとする。他4例の正常応答は原文照合・proposalまで合格し、欠落と値・単位・意味・強さの改変を拒否する。40 passed・6 deselected・1 xfailedの関連offline検査を確認した。

### 実行境界

Bonsai-8B、HTTP127.0.0.1:18080、各case独立server・1 call・retry0・最大900秒、全5 calls、認証不要・API費用0。生成応答は1 MiB上限で、全文とmetadata・モデル投影・正規化後・判定を `/tmp/amazon-explorer-bonsai-examples-20260908-01/<case>` へ0700/0600で保存する。parentに基準・source/prompt/schema/test等のdigestを保存する。各server停止を確認する。外部provider・画像・商品検索・ranking・委託frontendは実行しない。

### 初回の実測結果

同一prompt・モデル・schemaで全5件を各1回実行した。pytestは5 failed、318.56秒、exit1。全てHTTP 200・retry0・完全応答受信で、合計5 calls・API費用0。試験前manifestのsource/test/prompt SHA-256が終了後も一致した。

| case | モデル提案→正規化後（条件・custom） | 最終内容 | 失敗箇所・補足 |
|---|---|---|---|
| table | 1・0→0・0 | 不合格 | モデルが木材を欠落。丸形roundは正しく提案したが、adapterが「丸い」を根拠付けできず除外 |
| backpack | 3・2→1・0 | 不合格 | 容量20の単位を商品名へ誤り、撥水対応を入力にない防水対応へ置換 |
| headphones | 3・2→3・2 | 内容確認では合格 | 全条件を保持しready。ノイズキャンセリングの意味を外部音のキャンセリングとして表現し、事前regexの同義語不足で自動判定だけ不合格 |
| monitor | 3・2→2・1 | 不合格 | 27インチを27.000000 inchへ正規化し、原文引用は27インチ以上。意味上の単位は同じだが、原文照合がこの単位表記を受け付けず除外 |
| keyboard | 3・2→1・0 | 不合格 | 希望のバックライト対応を1件以上の数値へ変更。除外すべきBluetooth対応をfalseとし、期待するtrue・excludedと不一致 |

ヘッドホンの自動判定falseをそのままモデルの意味誤りとは扱わず、保存応答を内容確認した。黒色required、再生時間20時間以上required、ノイズキャンセリングtrue・equals・required、定義の意味、3条件・2独自属性・readyを満たしている。基準固定後にregexを広げたり試験結果を上書きしたりせず、`content-review.json` に応答digestと補足判定を別保存した。したがって初回自動結果は0/5、内容確認後の最終条件充足は1/5と区別する。

要求時間はtable50.408秒、backpack63.775秒、headphones64.556秒、monitor62.382秒、keyboard65.919秒。各5fileと親のcriteria・manifest・補足判定をprivate logへ保存し、directory0700・file0600を確認した。全5件server_stopped=true、最後の独立port18080確認も非listen。応答全文を文書へ転記していない。

最終offlineは2185 passed・13 skipped・14 deselected・1 xfailed、76.83秒。xfailは既知の「丸い」の照合欠落1件で、全合格とは扱わない。lock79 packages、Ruff check、format270 files、Markdown検査とgit diff --checkも成功した。

マグカップ1件の成功は汎用推論品質を証明しなかった。モデルの条件保持・属性定義・単位選択、adapterの同義語・単位表記対応、判定器の意味語彙という別々の課題を確認した。今回は測定中の改善・再送は行わず初回結果を保存した。新規5例は今後の開発診断例であり、これらへ調整した後の成功を独立holdout成功とは扱わない。

## EXEC-089: 独自属性の比較方法と条件の強さを修正

- 状態: 固定ケースの実Bonsai単体に合格（2026-09-08。2回の改善・再試験）
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)

### 授権と目的

利用者は「ユーザの承認無しに、改善とテストを繰り返せ」と明示した。この作業の属性推論修正とローカルBonsai単体再試験は追加の承認質問なしで継続する。固定入力・モデル・合格基準を維持し、各試験はloopback1 call・retry0・認証不要・費用0・最大900秒、応答上限1 MiB、新規private logへ応答全文を保存する。実行条件は事前に通知する。外部provider、画像、全検索、ranking、委託frontend、commit・pushへは広げない。

EXEC-088の実応答では食洗機対応の型・定義・値を提案できたが、booleanにcontains_allを指定し、requiredをpreferredへ弱めた。生成schemaがcustomの全型と全operatorを無関係に許していたため、domainで成立しない組み合わせを生成時に許す不整合を修正する。

### 変更と検証

- customをboolean・enum・numeric・text_setに分け、domainの型別operator集合と対応付けた。booleanはequalsだけ、semanticはcustomで生成できない。integerとdecimalのoperator集合は同一なので同じ分岐へまとめた。プリセット追加・期待値補完・モデル変更・合格基準緩和は行わない。
- propertiesの生成順序を維持し、参照されない共通integer targetを削除した。固定回帰の要求17,000 bytes上限は維持する。promptには希望表現がある場合だけpreferredとし、通常の明示条件をrequiredとする指示、booleanはequalsとする指示を追加した。preferred・excluded自体はschemaから削除せず、原文との照合で判定する。
- 生成時に型と不適合なoperatorを拒否する新規回帰は7 failed・3 passedから10 passedへ改善。関連回帰121 passed・1 deselected。llama.cppの実converterとgrammar matcherでも正常なprompt例・数値＋boolean fixtureを受理した。
- 生成schema SHA-256 `8a016c75aad9ad18f3911aa19a3c9d72af1ddf5cf613b919569fe9954d442b28`。単体入力の要求16,911 bytes。旧schema/requestはdigest再照合で失効し、新規作成する。完全application schema、既存cache、表示履歴は変更しない。

### 実試験

最初の試験はDEVELOPMENT 6.2の専用node、保存先 `/tmp/amazon-explorer-bonsai-attributes-20260908-04`。実応答の判定・原因を保存ログで確認し、同じ合格基準を満たさなければ修正後の新規ログ先で再試験する。

### 結果

| 試験 | 条件・独自属性（モデル提案→正規化後） | 判定 | 要求時間・token・応答 |
|---|---|---|---|
| 04: 型別operator＋強さの指示 | 2・1→1・0 | 不合格 | 39.544秒、prompt1176・completion107、1,161 bytes |
| 05: 3条件を分ける別カテゴリ例 | 3・2→3・2 | 全9項目合格 | 42.129秒、prompt1155・completion158、1,431 bytes |

04は容量と食洗機対応を1条件へ混ぜ、食洗機対応の定義に350ml以上を割り当てた。型別operator制約は満たしても意味が不適切なため原文照合で除外し、確認待ちとなった。05へ向け、診断入力とは別のライトを使い、青色・点灯時間8時間以上・防水対応を3条件へ独立分解するprompt例を追加した。冗長な文章を短縮して既存要求17,000 bytes上限を維持し、全仕様を別条件へ割り当てる指示を残した。

05は白色required、容量350ml以上required、食洗機対応boolean true・equals・required、商品種別、3条件、検索専用属性2件、ready proposal、余分なterms等の希望なし、共有registry不変の固定基準を全て満たした。属性・値・意味を後処理から補完せず、モデル提案時点でも容量と食洗機対応が合格した。専用testは1 passed、43.82秒、exit0。04は1 failed、41.49秒、exit1として保持する。

2回とも生成1 call・retry0、HTTP 200、API費用0。完全応答と診断5fileずつを末尾04・05へ保存し、各directory0700・file0600を確認した。04本文SHA-256 `f18d59e41b44b97ecb388c7aac363821b59e8a37f011aa4985f3f2063de29d45`、05本文SHA-256 `5627cef3aee07a679da7aea4ef7948f46c27c448e032ef55911779aadd8a94ca`。双方server_stopped=true、05後の独立port18080確認も非listen。

最終標準offlineは2167 passed・13 skipped・9 deselected、44.91秒。lock79 packages、Ruff check、format268 files、Markdownリンク・見出し・フェンス検査とgit diff --checkも成功した。初回全体検査で見つかった旧prompt表記のassertionだけを現行表記へ合わせ、実推論合格後のsourceとpromptは変更していない。

最終prompt SHA-256 `9485ced1dc91308e7ac158f231ae3622d322d3a2f78caa30c4b447ac93b1f49d`、adapter `03664ab925c99db04564a08c91ec4f7bc8377fe105e512ac1d75047686aef000`、新規test `fc9d1f59b7e14c0689013ffd1d460e0a6d4750453fb57bafe1a998f71400ec04`。単体要求16,891 bytes、固定回帰16,932 bytes。追加したprompt例自体も原文照合から3条件・2独自属性・readyになるoffline回帰を通過した。

これは既知の固定入力1件の修正後合格であり、未知カテゴリ・未知入力や実商品rankingの品質を保証しない。条件分解・型別operator・強さの修正と単体試験を完了し、全検索・画像・ランキングは実行していない。

## EXEC-088: 独自属性の生成順序を修正

- 状態: 実再試験で容量・独自属性提案は改善、食洗機条件の関係・強さが不合格（2026-09-08）
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)

### 原因と変更

EXEC-087の実Bonsai応答ではcustom0件となった。送信する生成schemaとHTTP bodyを再帰的に辞書順へ並べていたため、custom分岐のpropertiesだけはattribute_definitionがattribute_keyより先だった。ローカルllama.cppの `common/json-schema-to-grammar.cpp` はproperties順で必須fieldを生成文法へ固定する。attribute_keyから生成を始めるprompt例ではcustom分岐に入れず、既存属性だけを選べる。この文法上の不整合は確認したが、前回モデル出力の全誤りを説明する唯一の原因とは断定しない。

生成schemaと最終HTTP bodyの両方で構築時の順序を保持し、属性キー→独自属性定義→operator→値→strengthの順序を維持した。数値targetはvalue_type→上下限→unitに統一した。モデル・prompt・カテゴリプリセット・受入判定・応答ログ方針は変更しない。共有registryへ属性を追加せず、不足属性や値を後処理で補わない。

JSONの意味上のschemaとapplication完全schemaは同一。生成schemaのbyte列とbody digestは変わるため、旧prepared requestは本番実行前の再構築照合で拒否する。再ソートしたbodyのdigestだけを再計算してもtransport呼出前に拒否する回帰を追加した。既存の表示履歴・商品cacheは書き換えず、新規の推論要求を作り直す。戻す場合はこの順序修正差分だけを戻す。

### 検証

- 最初の生成順序回帰は4 failed、修正後4 passed。追加でcustomのboolean・enum・integer上限・decimal範囲・text_setと、再ソートの拒否を確認した。関連回帰は148 passed・1 deselected、追加の要求binding回帰を含む重点検査は56 passed。
- ローカルllama.cppの既存C++文法integration testを用いた一時probeで、モデルロード・server起動・通信なしに実converterとgrammar matcherを実行した。prompt例と正常な数値＋boolean属性fixtureは、変更前の送信schemaでは2件ともreject、変更後は2件ともacceptだった。これは文法の到達可能性の確認であり、実モデルが正しい属性を選ぶ証拠ではない。
- 一時probeと変更前後schemaは `/tmp/amazon-explorer-grammar-order-k5rtpnxn`。`probe before-schema.json prompt-example.json` と `probe before-schema.json numeric-boolean.json` はexit1、after-schema.jsonへの置換はexit0となる。fixtureは固定合成値のみで、実応答本文を転記していない。
- 生成schema SHA-256は `183a65bac158668f0a2d2738f6f5f5c152240dba6e99cd847334da2e50c4d256`。application schemaは `ef1d33c66f7dde41c98f82be8ab1090d17c3781c8d0b8ee0b25e9623f575c27e`、promptは `95f0cc8d551a4b37fb5963832bc0abfc12af74524260f060c878cc5d6ee8ff12` のまま。要求は固定回帰16,357 bytes、単体診断16,316 bytesで17,000上限内。
- 最終標準offlineは2156 passed・13 skipped・9 deselected、45.73秒。lock79 packages、Ruff check、format267 files、現行Markdownのlocal link・anchor・fenceとgit diff --checkも成功した。
- source SHA-256: adapter `61f2d58d95b0e35fa14026abf9885bbb4c9229f96b1fa08c486dfbd1b4d2565c`、request `790dfbada1bc2f39e4a0d3eb924748627201f7ca740d0ba7fd5c26b135c0f27a`。順序test `617d783a1caf81725f9a3ed95dae7fe09911c87d99318963738c2fd5d405ef02`、request test `605d7e6ff4aa5951ef74571e5ecc3a62baf71951499d23ec668d291021532d82`。

### 実推論の再試験境界

DEVELOPMENT 6.2の専用nodeで、同一固定入力・Bonsai-8B、HTTP127.0.0.1:18080、生成1回・retry0、認証不要・API費用0、全体900秒・応答1 MiB、private log `/tmp/amazon-explorer-bonsai-attributes-20260908-03` を使う準備をした。新規ログ先は未作成。変更後schemaによる実推論は別の明示承認後に実行し、意味品質を同じ基準で判定する。全検索・画像・ランキング・委託frontendは保留する。

### 承認済み実再試験の結果

利用者の「推論の改善を確認して下さい」を今回の提示済み1-call再試験の承認として実行した。直前に同一入力・Bonsai-8B・loopback・認証不要・費用0・retry0・900秒上限・新規ログ先を再掲し、model、adapter、request、prompt、完全schema、生成schema、runner、logger、単体testのSHA-256を照合した。専用nodeは1 failed、exit1、全体43.25秒、要求処理41.551秒。HTTP 200、prompt1123 tokens・completion164 tokens、応答1,449 bytes、1 call・retry0だった。

| 固定基準・件数 | 修正前（EXEC-087） | 今回 |
|---|---|---|
| 商品種別・白色required | 合格 | 合格 |
| 容量350ml以上required | 不合格 | 合格 |
| 食洗機対応true required | 不合格 | 不合格 |
| モデル提案のcustom件数 | 0 | 2 |
| 正規化後の条件数・custom件数 | 1・0 | 2・1 |
| 条件3件・検索専用属性2件 | 不合格 | 不合格 |
| proposal_ready | false | false |
| 余分な希望なし・共有registry不変 | 合格 | 合格 |

モデル提案は白色・容量・食洗機対応の3件で、容量の意味・350・ml・下限・requiredは固定基準を満たした。食洗機対応もラベル・意味・原文引用・boolean trueを提案したが、operator=contains_all、strength=preferredだった。必要なequals・requiredと異なるため、原文照合で除外され、custom_condition_unresolvedにより確認待ちとなった。なおno_extra_preferences判定はterms・価格・brand等を対象とし、却下されたtyped候補のpreferredを正しいと認定するものではない。

生成順序の修正後にcustom提案0→2件、容量不合格→合格の改善を同じ入力で観測した。ただし全体基準は未達で、条件の比較方法と強さを維持する課題が残る。同一入力各1回の比較であり、未知カテゴリの推論精度・実商品の順位品質を保証しない。追加推論・全検索・画像・ランキングは実行していない。

応答本文の完全受信と5診断file保存を `/tmp/amazon-explorer-bonsai-attributes-20260908-03` で確認した。directory0700・file0600、本文SHA-256 `7ef4720d2a5953b3c159e40f0d13bb548bc33618ff7d74aa88f3481b3a73edbc`。本文は標準出力・文書へ転記せず、固定項目への限定投影で診断した。server_stopped=trueと独立したport18080の非listenを確認した。

## EXEC-087: 属性推論の条件欠落検出と応答ログ

- 状態: 再試験完了・属性推論は不合格（2026-09-08。商品種別・白色と欠落検出は改善）
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)

### 目的・手順・検証境界

実Bonsai単体不合格を受け、利用者の「修正し、テストの準備」と「テストの応答を全てログに保存する」指示を実施する。過去raw応答は残っておらず、今回の修正を過去失敗の根本原因特定とは扱わない。合成入力で再現できる条件欠落のready受理を修正し、promptへ商品種別と仕様を分ける例を追加する。カテゴリ固有属性をプリセットへ戻さず、モデル提案・後処理・判定の段階別件数を確認できるようにする。

新規テストでREDを記録後、処理・ログを実装してGREENと全体offlineを確認する。生成要求の全HTTP応答本文（成功・非200・不正JSONを含む）を、新規0700 directoryの0600 fileへ保存する。応答1 MiB上限を維持し、上限超過・読込失敗は受信済みprefixと不完全の固定理由を保存する。生成要求なしの接続失敗は本文なしの固定metadataとし、応答のない成功ログを捏造しない。認証情報・request header・生例外を保存しない。固定合成入力の単体診断に限定し、外部サービス・本番ログの方針は変えない。

修正後の実Bonsai再実行は今回の準備に含めず、変更したprompt・ログ保存条件を提示して別承認後の1 callとする。所有server停止、retry0、費用0、モデルとschemaの固定を維持する。全検索・画像・ランキングは保留。

### 変更範囲とロールバック

Bonsai source grounding・prompt、単体runnerとテスト専用応答logger・pytest option、合成回帰、現行文書が対象。原文から比較可能条件が欠落した場合は確認待ちとし、期待値や属性をテスト側からモデルの代わりに追加しない。変更前の保留承認は再利用しない。戻す場合は今回の差分だけを戻す。

### 実装と検証

- 数値＋単位＋有界比較の条件が有効な数値属性へ分解されない場合と、商品種別への複数条件文の混入を確認待ちにした。容量以外の点灯時間、別単位へのすり替え、数値句をcustom enumへ押し込む迂回も合成回帰で確認した。promptには診断入力と異なるライトの出力例を追加した。共有registryのカテゴリ属性は増やしていない。
- 初期の欠落検出REDは6 failed・2 passed。追加のenum迂回・repository内ログ拒否も2 failed・16 passedを確認後に修正した。範囲指定回帰は既存のASCII単位境界が受理する空白付き入力へfixtureを訂正した上で、幅の有効な上下限を保持することを確認した。
- 最終 `tests/test_bonsai_inference_repair.py` と同じSHA-256 `6dd780051550c667420230e52274738d0173ab2f82e0c1ff80392f2cb800b139` を変更前source copyへ配置し、7 failed・3 passedを再現した。コマンドは準備済みvenvの `python -m pytest -q tests/test_bonsai_inference_repair.py --tb=short`。現行の同一testは10 passed。最初のcopyコマンドの相対path誤りによる収集不能はRED証拠へ数えず、絶対pathで再実行した。
- 応答loggerの初期REDは新規機能未実装により8 failed。現行は9 passedで、成功・500・不正JSON、接続失敗・読込中断・1 MiB超過、既存path・repository内保存・外部endpoint拒否、0600/0700、1 callを確認した。本文はHTTP metadata・JSON検証の前に保存し、本番のresponse projectionを保存済みbyteへ適用する。生例外やrequest headerはログに含めない。
- 単体runnerは同一要求の応答本文、モデル提案件数・固定判定、正規化済みintent、最終判定を別fileへ保存する。統合fixtureで、成功時の3条件・2追加属性と、不正JSONでも本文が残ることを確認した。追加requestは発生しない。test専用transportの選択を既存実行helperへ任意引数として渡し、他のBonsai診断は既定transportを維持する。
- 初回全体は1 failed・2140 passed。数値条件が欠落した旧fixtureのready期待をblockingへ変更し、partial candidate binding自体は維持した。最終 `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は2146 passed・13 skipped・9 deselected、44.53秒。loggerのO_NOFOLLOW互換化後も関連9件成功。lock79 packages、Ruff check/format266 files、Markdown links/anchors/fencesとdiff checkも成功した。
- prompt SHA-256 `95f0cc8d551a4b37fb5963832bc0abfc12af74524260f060c878cc5d6ee8ff12`。生成schemaは `8f8b3218b729b704994a0c235e91a700e9511e683ea39068d63131ff0bcbdb02` のまま。固定回帰入力は16,357 bytes（既存17,000上限内）、単体入力は16,316 bytes。生成token・HTTP timeoutの追加上限は設けない。
- runner SHA-256 `fc74a9f29bcd03eba595feeff6b9c9b816828c8ffba46505d411c6bf53fcb211`、logger SHA-256 `c6a6132c296546478b49598c8d3c2f6808808fd798e0636d2bd7ea5653e65f50`、単体test SHA-256 `a87a51afcc6edb54b456707fc596aad237a1fc9443917f58fa01fa0bbf3d30f7`、logger test SHA-256 `f3fe3ff4899c426c307d18a71256da4521163adce0040230e296d255e8dc2ce3`。

### 再試験の準備結果

DEVELOPMENT 6.2の専用nodeへ `--bonsai-response-log-dir /tmp/amazon-explorer-bonsai-attributes-20260908-02` を追加した。モデルと固定入力・生成1回・retry0・費用0・loopback・900秒は維持し、promptと保存範囲を変更した。利用者は今回「修正と準備」を指示しているため、実Bonsai・他providerへ再送していない。過去失敗の原因を特定した、または実推論品質を修正できたとは扱わない。未commit。


### 実Bonsai再試験の結果

利用者の「推論品質の改善を確認せよ」を受け、提示済みの固定入力・同一Bonsai-8B・loopback・生成1回・retry0・認証不要・費用0・900秒上限で専用nodeを実行した。実行直前に条件と保存先を再掲し、runner・logger・test・prompt・schemaのdigest一致を確認した。結果は1 failed、exit1、全体43.83秒、要求処理40.590秒、prompt1123 tokens・completion145 tokens、HTTP 200、応答1,373 bytesだった。

| 固定入力の判定 | EXEC-086 | 今回 |
|---|---|---|
| 商品種別・白色required | いずれもfalse | いずれもtrue |
| 容量350ml以上・食洗機対応 | いずれもfalse | いずれもfalse |
| 条件3件・検索専用属性2件 | いずれもfalse | いずれもfalse |
| proposal_ready | true | false（numeric_condition_unresolved） |
| 余分な希望なし・共有registry不変 | いずれもtrue | いずれもtrue |

今回の保存応答を固定語彙・数値の限定投影で調べたところ、モデル提案は共通属性4件・custom0件。白色に加え、容量を幅350mm以上へ誤対応し、入力にない円筒形・縦向きを提案した。正規化後は白色1件・custom0件で、数値条件不足により確認待ちとなった。妥当な検索専用属性がadapterで消えた事例ではなく、今回のモデル提案段階で不足・誤対応が発生している。前回のraw応答はなく、前回にも同じ誤りがあったとは断定しない。

商品種別・白色の固定判定と欠落時の停止は改善したが、核心の検索専用属性推論は未達。同一入力各1回の比較であり、未知入力への一般化や性能改善の証拠ではない。全検索・順位監査は保留し、追加推論・外部provider送信は実施していない。

応答全文・HTTP metadata・モデル提案投影・正規化intent・判定結果の5ファイルを `/tmp/amazon-explorer-bonsai-attributes-20260908-02` に保存した。directory0700・file0600、HTTP本文は完全受信。本文SHA-256は `64f45ef8e82a7dfff44573efe407d729a7848134e14890466c413de9f0a47ffc`。本文を文書や標準出力へ転記していない。server_stopped=trueと独立のport18080非listen確認により停止を確認した。

## EXEC-086: Bonsai単体の検索専用属性推論

- 状態: 単体実行完了・事前基準に不合格（2026-09-08）
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)

### 目的・手順・受入条件

EXEC-085の全検索より先に実Bonsai単体の推論を確認する。固定合成入力は「白いマグカップ。350ml以上で、食洗機対応。」の1件。共通の白色、原文に属性名がない容量下限、カテゴリ固有の食洗機対応を現行の1-call要求で提案し、strict adapterと検索専用registryへ通す。3条件がrequiredとして欠落・過剰なく保持され、容量は350 ml以上、食洗機は対応true、色はwhite、検索専用定義の名前・意味が対象仕様に対応し、共有registryを変更しないことを事前基準とする。

1. 合格fixtureと、容量・単位・比較・強さ・属性名の誤り、欠落を不合格とするoffline testを先にRED/GREENで確認する。
2. 単体専用live nodeは個別opt-inを要求し、Bonsai生成1 call・retry 0・loopback・context8192・起動含む900秒・response1 MiB・credential不要・API費用0、終了時server回収を固定する。
3. 実行直前にendpoint、固定入力、上限、保存範囲、digestを提示して明示承認を得る。実結果は件数・固定判定項目・時間・tokenだけを表示し、原文・raw応答・cache・server logを保存しない。
4. 単体結果を記録し、失敗を自動再推論で隠さない。Cloudflare、Outscraper、画像、ランキングは開始しない。汎用品質の合格とは扱わない。

### 変更範囲とロールバック

専用test runner・pytest opt-in・合成回帰・関連文書だけを変更する。Bonsai本体・prompt・属性adapterの意味挙動はこのテスト準備で変更しない。戻す場合は今回の差分だけを戻す。EXEC-085はこの確認後まで保留する。

### 準備と実行識別子

- 新規の `tools/bonsai_attribute_inference.py` と専用live node、個別opt-inを追加した。初期は未実装判定9件失敗。その後の空の受入判定stubに対するbehavior REDは9 failed・1 deselectedであり、収集・import失敗ではない。実装後は11 passed・1 deselected。追加2件は1 callと失敗時cleanupのfixture確認である。
- test SHA-256 `ce55d92a38184f253bc1a1e4c98fc037d2eeb8357a39e74d36ee8b787ac87065`、runner SHA-256 `050c8034d929c412c6887b2e310c19263310992b51d7cc4142a9c6c3c276192b`。
- model SHA-256 `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54`、prompt SHA-256 `db747c1eaf27a50c3de7df150cc4e57b59881d1b9783ba56886af10d8dd93f3e`、完全schema SHA-256 `ef1d33c66f7dde41c98f82be8ab1090d17c3781c8d0b8ee0b25e9623f575c27e`、生成schema SHA-256 `8f8b3218b729b704994a0c235e91a700e9511e683ea39068d63131ff0bcbdb02`。
- 実行先は `http://127.0.0.1:18080/v1/chat/completions`。固定入力1件、1 call、費用0、認証不要、raw応答非保存。実行コマンドはDEVELOPMENT 6.2に記録した。現在はoffline準備のみであり、実Bonsaiの属性推論成功とは扱わない。

- 最終offline全体: `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は2125 passed・13 skipped・9 deselected、46.49秒。lock 79 packages、Ruff check/format 263 files、Markdown links/anchors/fences、diff checkも成功した。テスト補助と文書だけを追加し、本番の属性抽出・商品判定の意味挙動は変更していない。

### 承認済み単体実行の結果

利用者の「実行しろ」を、直前に提示したloopback・固定入力1件・生成1回・retry0・API費用0・raw応答非保存の単体実行への明示承認として受けた。runner/test SHAが計画と一致することを実行前後に確認し、DEVELOPMENT 6.2の専用nodeだけを1回実行した。

結果は1 failed（exit1）、全体34.62秒、要求処理32,623 ms、prompt934 tokens、completion107 tokens、応答1,029 bytes。生成1 call・retry0。形式検証は通りproposal_ready=trueだが、product_type、exactly_three_conditions、white_required、capacity_minimum_350ml、dishwasher_required、two_search_local_attributesはすべてfalseとなった。no_extra_preferencesとshared_registry_unchangedはtrue。期待する3条件と検索専用属性2件を正しく保持する事前基準には不合格である。

この固定診断は複合条件の成否だけを出すため、falseを「属性が一切返らなかった」と読み替えない。raw応答・抽出内容を保持しておらず、モデル出力、adapterの正規化・除外、固定ケースの語彙判定のどこで期待から外れたかは未特定。JSON成功やreadyだけでは条件推論の妥当性を保証しないことが確認された。

server_stopped=true、実行後の独立した `ss -ltn '( sport = :18080 )'` でも非listenを確認した。Cloudflare・Outscraper・商品画像・CLIP・ランキングは未実行で、全検索EXEC-085は保留する。追加実推論は行わず、次に診断する場合は原文・raw応答を出さない固定件数・工程別理由を準備し、追加1 callの条件を別途提示する。

## EXEC-085: 共通属性変更後の実検索と順位監査

- 状態: 準備完了・今回の送信条件への承認待ち（2026-09-08）
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)

### 目的・範囲・判定基準

利用者の実フローテストと順位適正性の判断指示に従い、EXEC-084後の現行backendを、過去と同じ固定合成入力「白い陶器製マグカップ」で1回実行する。DEVELOPMENT 6.6の既存runnerを使い、参考画像への了承、偽画像とqueryへの最終承認で停止する。旧結果の再採点ではなく、新規の検索結果を対象とする。

受信後に全候補を監査し、色・材質の条件欠落と根拠のない一致、明示不一致商品の一致商品より上位への混入、画像scoreによる必須状態の逆転、rankingと再open履歴の相違を判定する。仕様不明は適合と断定せず、不明率と上位商品の確認可能性を報告する。取得情報が不足した商品は公開商品ページで必要な仕様を確認する場合もあり、最大24ページ、追加の有料検索taskは作らない。判定はこのqueryと候補集合に限り、カテゴリ固有属性全般・未使用holdoutの品質合格とは扱わない。

### 実行条件

- Bonsai: `http://127.0.0.1:18080/v1/chat/completions`、Bonsai-8B.gguf、上記原文、生成1 call・temperature 0・retry 0、context 8192、起動を含め900秒、health待ち最大180秒、認証不要。
- Cloudflare: `https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/black-forest-labs/flux-2-klein-4b`、参考1枚と了承後の偽画像1枚、512×512、偽画像の入力は先行画像511×511、各120秒・応答4 MiB・画像2 MiB・retry 0。既存tokenを使用。
- Outscraper: `https://api.outscraper.cloud/amazon-products`、Bonsaiから得た日本語queryを最終確認して1 task、Amazon.co.jp・100-0001、最大24商品、同一task最大50 polls・30秒間隔・各30秒、retry 0。最終確認後に既存API keyを読む。
- 商品画像: `m.media-amazon.com` 最大24 GET、各10秒・8 MiB、固定CLIP最大7 batches・各30秒。
- 最新公式単価を確認した概算はCloudflare 0.000633 USD、Outscraper有料換算0.048 USD、合計0.048633 USD。無料枠残数・実請求は未確認。過去に決めた金額上限なし・1 test 1 task・自動再実行なしを維持する。
- 新規 `/tmp/amazon-explorer-backend-e2e-ranking-audit-20260908-01` の0700 directory・0600 filesへquery・確認画像・表示ranking・表示履歴・実行用SQLite・安全な件数summaryを保存する。生provider応答・credential・承認token・embeddingを出力しない。既存履歴・画像、委託frontendは変更しない。

### 準備の確認

既存runnerと現行契約の接続を読み、Bonsai binary/model、固定CLIP asset、port 18080の空き、新規出力path、credential設定の妥当性をローカル確認した。値は表示していない。`uv run --frozen --offline --no-sync pytest -q -m 'not live_api' tests/test_backend_search_live_e2e.py tests/test_backend_search_live_entry.py tests/test_search_v2_common_presets.py tests/test_search_v2_material_ranking.py` は83 passed・1 deselected、4.20秒。実provider要求はまだ送っていない。

実行コマンドはDEVELOPMENT 6.6と同じ専用live nodeとし、output directoryだけ上記新規pathへ変更する。今回の送信条件への明示承認後に1回開始する。失敗時は固定診断で停止し、追加liveを自動実行しない。順位品質の結論は実行結果の確認後に記録する。

## EXEC-084: 共通属性だけをプリセットにする

- 状態: 完了（2026-09-08、offline。実Bonsai推論品質は未検証）
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)

### 目的と範囲

利用者判断に従い、組み込み属性を色・材質・形状・幅・向き・外観スタイルに限定する。対応モデル・接続方式・充電式・収納口数はBonsaiの検索専用属性へ移し、卓上型・携帯型のform.factorは共通形状のform.shapeへ置き換える。wire schema・prompt・registry・商品証拠と回帰fixture、現行文書を同期する。既存の未commit変更、保存済み履歴、委託frontend、実サービス呼出し、commit/pushは対象外。

### 手順と受入条件

1. プリセット限定とカテゴリ属性の推論→承認用proposal→商品判定を合成テストでREDにする。
2. カテゴリ専用keyと専用parserを削除し、汎用型・明示label付き仕様を使う。旧keyを暗黙復活させない。
3. 共通属性と汎用engineの回帰を保ち、旧プリセット前提のテストを新契約へ移行する。
4. 全体offline、lint、文書検査を通し、同一test SHAのRED/GREENと未検証境界を記録する。

### 判断・互換性・ロールバック

共通属性の幅・向き・外観スタイルも残すが、カテゴリ固有の機能・対応規格はcustomとして入力から提案させる。旧registry/要求schema/証拠profileのdigestで保留承認や再計算cacheを再利用しない。過去の表示履歴は変更不要。既存のBonsai 1 callと原文/SudachiPy照合を維持し、実推論品質はoffline成功で代替しない。戻す場合は今回の差分だけを戻す。

### 進捗・検証

- 共通6 keyのregistry v3とwire schema・promptを同期し、カテゴリ専用key・接続方式/充電式/収納口数の専用parserを削除した。商品証拠profile v4、structured parser v4、title parser v3へbindingを更新した。原文に属性名がなくても値や機能を根拠に名前を提案でき、形状の否定を肯定根拠から除外する。
- 初期12件のREDは11 failed・1 passed。属性名の推論と形状否定の追加4件も修正前に4 failed・12 passedを確認した。最終16件を変更前sourceの独立一時copyへ配置し、15 failed・1 passed（exit 1）を再現した。旧key受理、旧aliasとの衝突、形状未定義、原文label必須が原因であり、収集・import失敗ではない。
- RED/GREEN共通testは `tests/test_search_v2_common_presets.py`、SHA-256 `4dbf886c683431e395afd78c22ab0ba4a3134c6776db5c70b214f37f28377fa9`。REDは変更前copyを作業directoryとして `/home/products/Git_Products/amazon-explorer/.venv/bin/python -m pytest -q tests/test_search_v2_common_presets.py --tb=short`、GREENは現行の `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_common_presets.py tests/test_search_v2_product_evidence.py tests/test_search_v2_typed_requirements.py` に含む全63件成功（exit 0）。
- 初回全体は19 failed・2091 passed。旧カテゴリのfixtureを共通形状enumまたは検索専用定義へ移し、汎用boolean/integer/text_setの型判定を維持した。歴史的Bonsai応答の旧key拒否と現行の根拠照合を分け、schema digest期待値を更新した。既存の実holdoutや画像は変更していない。
- 最終 `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short`: 2114 passed、13 skipped、8 deselected、44.49秒、exit 0。後続のtest名・重複set要素の整理後も関連63件成功。`uv lock --check --offline` は79 packages、Ruff check成功、formatは261 files整合。Markdown links/anchors/fencesと `git diff --check` も成功。
- 固定入力の要求は16,320 bytesから15,485 bytesへ減少し、既存17,000 bytes上限を維持した。生成schema SHA-256は `8f8b3218b729b704994a0c235e91a700e9511e683ea39068d63131ff0bcbdb02`。通信・tokenizer・実生成時間の測定ではない。
- 合成応答で接続方式・充電式・収納数・対応モデル・設置方法の追加と必須状態先行ranking、属性名のない値からの提案を確認した。商品側はlabel全体一致の明示仕様だけを使い、観測できなければunknownとする。実Bonsaiの定義品質・条件網羅性と商品側の仕様取得率は未検証。

### 結果

共通属性だけを固定し、カテゴリ固有の仕様はBonsaiが検索ごとに提案する構成へ変更した。未commit。新規live通信、委託frontend、保存済み履歴の変更は行っていない。


## EXEC-083: 入力に基づく検索専用属性の追加

- 状態: 完了（2026-09-08、offline。実Bonsaiの定義品質は未検証）
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)

### 目的と範囲

自然言語の原文をBonsaiへ渡し、既存属性を再利用しつつ、不足属性の名前・意味・入力の根拠と型付き条件を提案させる。SudachiPyの単語位置を使って根拠を照合し、検索専用registryを第一確認、承認、商品判定、ランキング、表示履歴へ引き継ぐ。共有registryやコードをモデルに更新させない。対象はsearch_v2のbackendであり、委託frontend、モデル変更、実サービス呼出し、過去履歴の書換え、commit/pushを含めない。

### 実行手順と受入条件

1. 既存未対応の容量・対応可否・カテゴリを合成応答で再現し、実装前にREDを確認する。
2. strict応答契約、原文根拠、単位・比較・否定の検証と検索単位の属性定義を追加する。
3. registryを承認digestへ結び、明示的な商品仕様から判定し、欠落・曖昧はunknownとする。表示履歴まで合成結合テストする。
4. 不正定義、根拠なし、比較逆転、検索間混入・改ざん、既存属性の回帰を確認し、offline全体・lint・文書検査を通す。

### 判断・互換性・安全境界

既存provider・回数上限は維持し、追加の自動推論呼出しは行わない。モデルの提案は非信頼で、実行code、重み、evaluatorはbackendが固定する。属性の意味は条件確認で利用者へ示し、形態素解析だけで意味の正しさを保証したとは扱わない。新しいintent/proposalは定義込みdigestで旧承認と区別する。保存済み表示履歴は移行不要で変更しない。出力上限は現状を測ってから設計変更し、固定Bonsaiでの品質・速度はoffline成功から推測しない。

### 進捗と検証

- `dynamic_attributes.py`、`dynamic_product_evidence.py`、intent・Bonsai adapter/prompt・typed proposal・ranking・core履歴を実装した。商品側は既存の正規化済みfeature内の明示label付き仕様だけを使う。任意本文のLLM再抽出は追加していない。
- 新規testの初期REDは13 failed。商品fixtureのfieldをprovider契約のnameへ訂正し、追加の否定・OR・重複・改ざん・単位・旧profile回帰も、それぞれ変更前の失敗を確認した。最終32件と同一testを変更前sourceの独立一時copyへ適用し、32 failed（exit 1）。既存wireのcustom/definition拒否、旧profile受理が原因であり、import・依存・構文エラーではない。
- RED/GREEN共通test SHA-256: `3df1e71cf89ae4853a42e6d9814fe3badc77834ec7eb9afbba0cddcc3dca8eb8`。コマンドは `uv run --frozen --offline --no-sync pytest tests/test_search_v2_dynamic_attributes.py -m 'not live_api' -q --tb=short`。GREENは32件成功（全体gateにも含む）。REDでは同一testを配置した変更前copyをdirectoryに指定し、準備済みvenvを再利用した。
- 関連Bonsai・typed adapter回帰は134 passed。最終 `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は2098 passed、13 skipped、8 deselected、46.95秒、exit 0。
- `uv lock --check --offline` は79 packages、Ruff check成功、formatは259 files整合。Markdown local links/anchors/fencesと `git diff --check` も成功。
- 生成schema SHA-256は `7024677671c0f79d3e754da7e67e828a6f189d6e4cf9940a6960c6d8552365f7`。旧schema期待値、任意definition fieldを持たなかった候補shape期待値を更新した。
- 固定入力の要求は旧15,032 bytes以下から新16,320 bytesとなった。annotation削除・数値境界共用・prompt整理後の測定値に基づきfixture上限を17,000 bytesへ変更した。旧上限を満たしたとは扱わない。wireの条件数4件、provider call数は増やしていない。
- 原文送信→第一確認→検索承認→商品正規化・順位→core SQLite履歴再読込を注入transportで確認した。localhost Bonsai、Cloudflare、Outscraper、実画像host、委託frontendは実行していない。追加属性の未知入力品質・商品情報取得率は [実データ品質](ISSUES.md#検索専用属性の実データ品質) に残す。

### 結果

検索ごとの不足属性を提案・検証・承認へ束縛して共通判定するbackendが実装済みとなった。意味の妥当性は利用者確認を必要とし、語彙・関係を無制限に理解できるとは扱わない。未commit。既存の表示履歴・生成画像、共有registry、外部frontend、harnessは今回の変更対象外。

### ロールバック

今回のsource/test/doc差分だけを戻す。作業前から存在する未commit変更、秘密情報、既存検索履歴は変更しない。

## EXEC-082: 材質条件と材料名の色誤抽出を修正

- 状態: 完了（2026-09-08、offline。修正後liveは未実行）
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)

### 目的と境界

WORKLOG 115の完走後の監査で、素材が必須判定のregistryになく、材料名中の色語を商品色として抽出する経路を確認した。利用者の修正指示に基づき、Bonsaiのschema・grounding・prompt、商品証拠、typed/provisional rankingの接続を修正する。既存の画像生成フロー、ranking weight、provider、実行上限は変更しない。実商品本文・識別子・raw responseを回帰fixtureへ転記しない。

### 実装と判断

- `default-attribute-registry-v2` に `material.type` を追加する。enumはearthenware、porcelain、bone_china、stoneware、glass、plastic、stainless_steel、wood。陶器・磁器・ボーンチャイナ・炻器を区別し、ceramic / pottery / 陶磁器は狭義の陶器へ推測変換しない。
- Bonsaiのwire schemaへ材質を追加し、source-groundedな完全一致の材質termを元のrequired / preferred / excludedのままtyped条件へ補う。既存条件は重複させない。明示材質の欠落・広義語・補完後の4条件超過はblockingとする。promptもtyped条件優先へ整合し、既存の15,032 bytes以下のrequest回帰上限を維持する。
- 商品側は専用material fieldの完全一致を優先し、次にtitleの有界な明示材質を使う。description、features、生産地、CLIPから材質を補完しない。未取得・曖昧・複数材質はunknown / conflict。否定と材質風の表現を肯定根拠にしない。
- 英語の色語直後のsoil / clayを材料説明として色抽出から除く。実際の色語と複数色のconflictは保持する。新しい `bounded-product-evidence-v2` とstructured/title parser v2をdigestへ結び、旧profileの再利用を拒否する。保存済み表示履歴は移行・改変しない。

### 検証

- 初期REDは28 failed・4 passed。後段fixtureのfield参照誤りを訂正し、potteryを曖昧語へ訂正、否定・広義語・重複防止の回帰を追加した。
- 変更前のsourceを復元した独立一時directoryで最終39 casesを実行し、35 failed・4 passed。原因は材質key / wire未対応、材質脱落、材料色誤抽出、旧profile受理。最終testと同一SHA-256 `94b93a195024f18759df7b030330668dcc37f80b1962d960a9f74158cdb749df` で現行は39 passedとなった。fixture importは各版のprofile定数名へ対応するがassertionは同じである。
- 白い陶器・白い磁器・白いガラス・材質不明の合成4商品を、条件分解→正規化→証拠→typed ranking→provisional画像加点へ通す。陶器の画像scoreを不利にしても、confirmed→uncertain→contradictedの順で材質不一致を上位へ戻さないことを確認した。
- Bonsaiの生成schema digestは材質追加により `42a71cb4b56a7dec29ec698bbb30a6518a59d15892516042cb02ef8374ffb5a4` に更新した。最初の全体gateで検出した旧digestの2 assertionsとprompt記載漏れを整合し、Bonsai関連と新規回帰142 passed。
- 新しい実Bonsai・Cloudflare・Outscraper試行は行わない。今回の合成回帰と既存表示タイトルの局所再解析を、24商品の再ランキングや未知データ品質の成功とは扱わない。

### 最終結果

標準offline gateは2,066 passed・13 skipped・8 deselected（43.84秒）、終了0。Ruff check、format 256 files、lock 79 packages、Markdownリンクを含むtestとgit diff --checkも成功した。保存済み24位の表示titleだけを局所再解析し、色がwhiteだけになることを確認した。旧24商品の素材・採点根拠は再取得せず、旧ranking・履歴は変更していない。

最終registry digestは `e7c9f0d94a8562ffd687ba62eef223935678a3ac27053dc21184217bc1ea489e`、evidence profile digestは `75f2af8afa101c2d03985ef9e5609ce20d01770a398e31c7526d224699fd8c01`。修正後の実Bonsai条件分解・実商品の根拠取得と順位品質は別のlive確認が必要であり、offline成功で代替しない。

### ロールバックと互換性

この変更だけを戻す場合はregistry、Bonsai schema/prompt、evidence profileとその消費側・testを一緒に戻す。未コミットの他変更、保存済みPNG・履歴・rankingには触れない。新旧のregistry/profile digestを混在させず、再実行が必要な検索承認は取り直す。

## EXEC-081: 参考画像生成失敗の安全な診断

- 状態: 最新の4B単発生成はHTTP 200（過去429の内訳は未確定）
- 対象: WORKLOG 111の `reference_generation` 失敗。終了済みprocessには元例外が残っていないため、過去の直接原因を推測で確定しない。
- 方針: counterfactual HTTP境界の通信・HTTP status・応答契約・Base64・画像内容・artifact検証を固定コードで区別し、ReferenceReviewとbackend E2Eの安全な失敗出力まで保持する。本文、URL、credential、例外文字列を出力しない。
- [x] 合成失敗を注入し、現行runnerで診断が失われるREDを確認する。
- [x] 最小の診断伝播を実装し、同一testのGREENと関連・標準offline gateを確認する。
- [x] 原因確認用の新規実行条件を固定する。追加liveは別条件の明示承認後だけ行い、検索全体を自動再試行しない。

### 検証と原因の確定範囲

`tests/test_backend_search_live_e2e.py -k safe_substage` は、通信例外、HTTP 503、JSON不正、Base64不正、画像内容不正の5 casesで `cloudflare_failure` が失われるため5 failedとなった。RED SHA-256は `6e62c50ab3724ad603c635611de3920c7fdefae8f97fe40d142afa28de1d3b7e`。最小実装後に同一testで5 passed。整形後のtest SHA-256は `8b27af759bb4e068ba3b63a96c552a75f47da0d9bb75c5c986ae0eec4b917fa7`。実HTTP adapterの503・body非読込・close・1回限定と不正診断拒否を追加回帰で確認した。

関連53 passed、最終標準offlineは2,017 passed・13 skipped・8 deselected（43.59秒）。lock 79 packages、Ruff check、format 255 files、Markdown・diffも確認する。外部API・実CLIPは実行していない。診断情報を失う不具合は確定・修正したが、WORKLOG 111の実生成失敗を通信・HTTP・画像のいずれかに推測分類しない。

### 承認済み限定診断の実行条件

- 固定合成入力は前回同様の白い陶器製マグカップ。localhost `127.0.0.1:18080/v1` のBonsaiを1 call、起動込み上限900秒。
- Cloudflare `https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/black-forest-labs/flux-2-klein-4b` へ参考画像1 call。既存token、512×512、入力画像なし、HTTP上限120秒、response 4 MiB、画像2 MiB、retry 0。公式output tile単価による見積り0.000287 USD。金額上限は従来指定どおり設けない。
- 新規出力directoryは `/tmp/amazon-explorer-backend-e2e-reference-diagnostic-20260908-01`（0700、files 0600）。queryと成功した参考PNGのみ、固定失敗情報は端末へ出す。生応答・例外・credentialを保存しない。
- DEVELOPMENT 6.6のコマンドのoutput dirだけを上記へ変えて1回実行する。成功した場合も先行画像の対話確認で停止し、偽画像・Outscraper・商品画像・CLIP・ranking・履歴へ進めない。追加診断で成功した場合、過去失敗の原因が確定したとは扱わない。
- 新しい画像はBonsai結果や計画digestにより前回と完全に同じ要求・seedとは限らない。過去の元要求・生応答を保存していないため、bit単位の再現試験とは表現しない。

### 最終コードSHA-256

- counterfactual_cloudflare_http.py: `578d6181293de86e925943b8fedd559a3295df23efd597183505b464c8de79ba`
- orchestrator.py: `3b51dca8c4b785eb871b745dd5c4ccd0cd73163b6a4f6de0c2baa7027e25c6a3`
- backend_search_live_e2e.py: `ac2209767c979b9d8eba118adac06628683b548786d702cec4070befb18ad119`

### 限定liveの結果

利用者の「はい」による条件承認後、上記のBonsai 1 call＋Cloudflare参考画像1 callを1回実行した。指定pytest nodeは42.30秒で1 failedとなり、`failure_stage=reference_generation`、`cloudflare_failure.stage=http_status`、`http_status_code=429` を観測した。Bonsaiによるquery作成後、Cloudflareが非200を返し、応答bodyの読込み・画像decodeより前に停止した。Outscraper task/poll・商品画像・CLIPはすべて0、retry 0。port 18080にlistenが残らず、出力directory 0700とquery.json 0600のみを確認した。画像・ranking・履歴は未生成。

今回の直接停止原因はCloudflareのHTTP 429である。[公式Errors](https://developers.cloudflare.com/workers-ai/platform/errors/) は429に日次無料枠超過（3036）と処理容量不足（3040）を列挙し、[公式Limits](https://developers.cloudflare.com/workers-ai/platform/limits/) はtask/model別のrate limitも定義する。今回の診断は数値HTTP statusだけを保持し、body内の内部code、利用残量、請求状態は取得していないため、特定のquota・rate・capacityを断定しない。WORKLOG 111の初回にも同じ429が起きたかは、旧診断がないため未確定。既存承認を使った追加送信は行わず、制限解除も自動再試行もしていない。

### 429内訳の追加調査

利用者の調査指示により、既存tokenでGraphQL Analyticsへread-only照会を3回行った（最大4回、各30秒、応答2 MiBの提示範囲内）。公開schemaの2照会は成功し、当日集計1照会はpermission errorで利用量を取得できなかった。token、account ID、生応答は保存・表示せず、生成・設定変更・再試行は行わなかった。

当日の9B診断summary 3件から同モデルの1 + 4 + 4 = 9 calls・retry 0を再照合した。[公式料金](https://developers.cloudflare.com/workers-ai/platform/pricing/) の最初の1 MP単価1,363.64 neuronsを1出力へ適用した見積りは、出力だけで12,272.76 neuronsになる。日次無料枠10,000超過が有力だが、512px出力の実計上量と契約planは取得しておらず確定値ではない。無料枠は00:00 UTC（09:00 JST）に更新される。既知429 code 3036 / 3040を実HTTP境界から安全に保持する修正を追加した。詳細なRED・検証結果はWORKLOG 113に記録する。

2026-09-08 17:38 JST、利用者の現行疎通確認指示により4Bへの生成1 callを実行し、HTTP 200・13.341秒で512×512 PNGを取得した（WORKLOG 114）。retry 0。過去429の原因を確定する証拠ではなく、検索E2Eは再開していない。

利用者の再開始指示後、二段階の人間確認を経た新フローbackend E2Eは24商品ranking・履歴再読込まで完走した（WORKLOG 115）。Bonsai 1 call、Cloudflare 2 calls、Outscraper 1 task・6 polls、商品画像24件、CLIP 7 batches、retry 0。過去429の内訳は引き続き未確定。

## EXEC-080: 4方向生成を製品フローから除去

- 状態: 完了（2026-09-08、offline・Figma更新・固定1条件のbackend実サービスE2E）
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)

### 目的と範囲

利用者の明示指示により、参考画像1枚の生成・了承後は条件別偽画像だけを生成する。新フローは1+N calls、参考画像を1回作り直して両回の後続生成まで実行した上限は2(1+N) calls。core・暫定production・backend E2E runner・承認/usage・履歴・仕様・既存Figmaを同期する。現行の参考画像と偽画像を使うCLIP/ranking式は変更しない。旧4方向の低位adapter、診断再現、保存済み履歴は維持し、新フローへ流用しない。

### 実行計画

- [x] 公開フローの1+N calls、4方向要求なし、再承認/期限/作り直し、ranking・履歴への接続をREDで固定する。
- [x] 4方向executionを必須としない新review契約と状態遷移を実装する。新経路のusageは先行画像と偽画像だけを予約し、失敗・過去作り直し分も数える。
- [x] 旧history読込みを維持し、coreの新規履歴には参考1枚、暫定historyには既存の参考1枚＋偽画像を保存する。新承認に旧4方向metadataを転用しない。
- [x] runner・関連仕様・Figmaの4方向カード、説明、生成数を変更する。
- [x] focused回帰と標準offline gate、Markdown、Figma read-back/スクリーンショットを確認する。

E2E実検索は停止を維持する。新provider・外部画像生成・課金・commit/push・未納品フロントエンドの起動や接続は行わない。Figma編集は先の明示依頼を継続する。

### 検証記録

- 最初のREDは `tests/test_search_v2_reference_image_flow.py` の「承認後は計2 calls」で旧実装が6 callsとなり、1 failed・1 passed。RED test SHA-256は `b0d1bde8210b49ae3d3bfbfee478504c01632138b8c53d079ee294e50231dc4c`。同じtestは生成処理変更後に2 passedとなった。
- 承認・作り直しのREDは旧allowanceが2-call planを拒否して1 failed。`tests/test_search_v2_reference_image_approval.py` SHA-256 `be955631ab2ce894e9ee762533d89e1e7913451b5b3888b7e117d69d41a7776e` はGREENでも同一。新profileで通常2〜4、最大8 callsを検証する。
- 履歴の初回REDは旧fixtureの6-call期待で止まったため、それを2へ修正してから再実行した。正式REDは `execution=None` から旧4方向画像を読むAttributeErrorによる1 failed。`tests/test_search_v2_history_snapshot.py` SHA-256 `63da147ac22234ee9f3d36141d531302df3bb4bd725f5510b398136b117001c8` はGREENでも同一。新規1枚保存と旧4枚履歴の読込みを区別する。
- 関連11 filesのfocused回帰は118 passed・1 skipped。追加で条件数1・2・3と作り直し両回の呼び出し数、第三回拒否を検証し、reference flowは5 passed。これは追加回帰であり、追加3件を実装前REDとして数えない。
- 最終標準offline: `uv run --frozen --offline --no-sync pytest -m 'not live_api'` は2,006 passed・13 skipped・8 deselected（41.76秒）。lock 79 packages、Ruff check、format 255 files、Markdownリンク、`git diff --check` も成功した。実model opt-inとlive APIは実行していない。
- Figmaは先行画像・生成中・生成後・最終確認・待機・モーダル・参照シートを更新した。4方向カードを除去し、1条件例は参考1枚＋偽画像1枚とした。reference frames `59:22`・`169:71`・`169:172`、最終確認 `60:61`、modal `114:4`・`114:55`、参照シート `66:2` をscreenshotで確認した。最終確認に残った旧4枚サムネイルも2枚へ修正し、参照シートのPNGを更新した。テストは未納品UIの起動・接続を含まない。

### 最終コードSHA-256

| 対象 | SHA-256 |
|---|---|
| orchestrator.py | `8da158cab7022a5140796a4eae077ad9034ad36a82b2c7a09c5ef61c2d638196` |
| state_machine.py | `e2a8869ac1144d40294cf7389856f5712700d10d1f69e3101cc7e01b5058ff6e` |
| approval.py | `6bb578217ae847ec1a605820bb25ff7b3e71796e2fc7b4e8136eda0974830db3` |
| history_snapshot.py | `f6ec34f19676ee5c8bc61071692ed5560a822f261d01a282f3aa46442735595c` |
| history_repository.py | `ad60bc7dee03a13495be01eb3faeb9b5dcfbc9687dee8193345a2d08f2bb5216` |
| backend_search_live_e2e.py | `e8b5d69198fc1c423959ad19ed01097b6ef3b40d764a8440ea71bfe3856ac263` |
| test_search_v2_reference_image_flow.py（追加回帰込み） | `42f0187a2bc340087bb1761cef5457fcf0612cd94ab8500d1a8f5c3467bb8f27` |

### 結果と残る境界

4方向生成を公開フローから除去した。元の参考画像と偽画像を使うCLIP・ranking方式は維持し、精度改善や実画像品質の合格は主張しない。旧低位4方向adapterと診断記録は残す。モデル品質不合格は要件撤回による終了として記録し、修正成功に読み替えない。実検索E2Eの再開、外部画像生成、新provider、ローカル3D、未納品フロントエンド、commit/pushは行っていない。

## EXEC-079: 4方向画像の視点指示修正と限定再生成

### メタデータ

- 状態: 終了（EXEC-080で4方向要件を撤回。モデル品質は未解決のまま）
- 作成日・最終更新: 2026-09-08
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)
- 不具合: [ISS-002](ISSUES.md#iss-002-4方向指定の生成画像がほぼ同じ向きになる)

### 目的・範囲

利用者の再生成指示に従い、4方向のpromptに参照視点からのカメラ移動と遮蔽を明記する。先行画像の同一性と4方向の順序を維持し、prompt契約digestを更新する。原因はモデル内部まで確定しておらず、offlineの指示検証は生成品質の証明にしない。

同じ承認済み参考PNGを使う追加4-call診断を準備する。固定合成マグカップ属性を明示し、Bonsai由来intentや既存E2Eの継続結果とは扱わない。元の6枚・偽画像・検索job・履歴を置換せず、Bonsai・Outscraperを再実行しない。追加liveは具体的な条件・費用提示への承認後だけ実施する。

### 受入条件・進捗

- [x] カメラ移動・遮蔽指示のREDを確認し、prompt修正後に既存契約の回帰を確認する。
- [x] 保存済み参考画像のdigest検証、4 calls上限、失敗時停止、private別保存をofflineで確認する。
- [x] 別承認の限定liveで4方向を再生成し、画像の視点差を目視判定する。

### 停止・復元・検証境界

追加liveの拒否、参考画像の変更、provider失敗では停止し、自動再試行しない。品質が改善しない場合は未解決として結果を提示する。変更を戻す際は今回のprompt変更・診断runner・対応文書だけを対象とし、元の生成物と履歴を保持する。API・UI・委託frontend・commit/pushは対象外。

### 検証結果・再開手順

prompt検査は `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_cloudflare_request.py -k derived_views` で1 failed・19 deselected（移動角度の指示なし）を確認した。初回のtest挿入位置が既存testを分断していたため位置を訂正し、再度同じREDを確認してからproductionを変更した。訂正後test SHA-256 `b93eb8ee0f02568394a6315a6130ae57c950ad7bd93b4f4a6b96f224c9dcf29a` はGREENまで不変である。既存のmetadata検査がprompt内の英単語bodyにも反応したため、遮蔽対象の表現をproduct itselfへ直し、既存検査を維持した。

限定診断は `uv run --frozen --offline --no-sync pytest -q tests/test_view_regeneration_live.py` が公開scaffoldの未実装で5 failedとなり、同じtest SHA-256 `9ec9f70a806a34193f4ddc6091b5b3bdd08fe78e427a88b00c39275d34e7ceba` のままGREENとなった。関連5 filesは112 passed、標準offlineゲートは1,987 passed・13 skipped・8 deselected（54.52秒）。lock 79 packages、Ruff、format 253 files、Markdown・diff検査も成功した。attested reviewではない。

最終SHA-256はrequest builder `2055bde5462b0a57718e2dfe701ecabbf11e7c0a2468aa5b3de4ba43bf638978`、診断runner `b1f709ecb2e75f2149e06236de777e6a5cae1d7945bdd104d88027db4d64fd16`。保存済み参考画像のdigest・private属性・511px入力化、新規出力先が未存在であることをoffline確認した。追加のcredential利用・画像生成は未実行。

[DEVELOPMENT 6.7](DEVELOPMENT.md#67-同じ参考画像から4方向だけを再生成する限定診断) に実行コマンド・送信先・保存先を固定した。同日再確認した[公式料金](https://developers.cloudflare.com/workers-ai/models/flux-2-klein-4b/)では4入力tile＋4出力tileで約0.001384 USD、金額上限なし。具体的条件への追加承認後に1回実行し、4画像を目視してISS-002の継続または解決を判断する。再生成物は元E2Eの承認・ranking・履歴へ差し込まない。

2026-09-08 16:06 JST: 追加4枚の送信先・参考画像と属性・回数・token利用・見積り・保存範囲の提示に対して、利用者が「はい」と明示承認した。request builderと診断runnerのSHA-256一致を確認し、記載のコマンドを1回起動した。自動再試行なし。

2026-09-08 16:07 JST: 承認済み追加診断はexit 0、Cloudflare 4 calls・retry 0で完了した。4 PNGすべて512×512 RGB・0600・単一link、summary digestとの一致、0700 directory、元の参考画像が不変であることを独立検証した。元E2E・Bonsai・Outscraper・偽画像を再実行していない。費用は事前見積り0.001384 USDであり、実請求を取得した値ではない。

目視では左側面指定の画像だけ取っ手が見えず、正面斜め・右側面・背面斜めの3枚は取っ手が右に見えるほぼ同じ構図だった。左の差が正しい遮蔽か取っ手の消失かは単一出力から確定できない。camera移動を具体化したpromptでも4方向の描き分けは達成しておらず、ISS-002を未解決として維持する。4方向品質の受入は不合格。追加承認の4 callsを使い切ったので、この結果から自動再試行しない。次の修正方針・実生成は別途検討し、新しい実行条件への承認を得る。summaryのhuman_review_pendingは利用者による採用確認を意味し、agentの目視による不合格記録とは分ける。

### 追加方針: E2E検索停止と視点生成の原因切り分け

2026-09-08: 利用者がE2E検索フローを一度停止し、4面が想定どおりにならない問題の解決を指示した。対象E2E・再生成processの稼働がないことを確認した。Bonsai、Outscraper、ranking、履歴、Figma・frontendを再実行せず、画像生成だけに範囲を絞る。

- [x] 実multipartに方向別prompt・seed・同じ参考PNGが正しく載ることをofflineで確認する。
- [x] 既存8画像の視覚的類似度を同じ尺度で計測し、byteの相違を視点の相違と混同しない。
- [x] 抽象的camera移動から、最終画像で見える取っ手・面・遠近の指定へ変える固定マグカップ診断を準備する。既存失敗条件と同じseed・参考PNG・寸法で比較する。
- [x] 再生成前に視点差・同一形状・特徴保持の受入基準を固定する。画像類似度は疑わしい組の検出だけに使い、低類似度を正しい視点の証明にしない。
- [ ] 追加liveへの具体的条件承認後に実画像で改善を確認し、成功した方式だけを本番の汎用契約へ反映する。

この段階ではモデル内部の原因は未確定であり、未実証のpromptを汎用修正として採用しない。既存履歴・画像・承認記録を保持する。診断の失敗や上限到達では自動再試行せず、観測結果から次の修正を決める。

追加調査: 実transportのmultipart組立をfake Sessionで捕捉し、4つの異なるprompt、4つの異なるseed、同じ `input_image_0`、512pxを確認した。これはofflineのwire検査であり、過去liveのraw要求を保存・再取得したものではない。既存初回4面のpHash距離は6組すべて2、再生成4面では正面斜め・右側面・背面斜めの3組が4/4/2、左側面との3組が10だった。既存閾値5で両実行の近似組を検出できる。pHashは姿勢を認識せず、閾値だけで正しい4面を証明しない。

[Cloudflare公式](https://developers.cloudflare.com/changelog/post/2026-01-15-flux-2-klein-4b-workers-ai/)のinput field名・511px条件と実装は一致していた。[BFL公式推論実装](https://github.com/black-forest-labs/flux2/blob/main/src/flux2/util.py)ではklein-4bのguidance 1・steps 4がfixedであり、Cloudflareが公開するguidance fieldを増やせば解決するとは仮定しない。[BFL画像編集説明](https://docs.bfl.ai/flux_2/flux2_image_editing)は単一参照への変更指示を示すが、任意商品の正確な4面生成を保証していない。

追加した3挙動testは `uv run --frozen --offline --no-sync pytest -q tests/test_view_regeneration_live.py -k 'landmark or identical or unknown'` で3 failed・5 deselectedとなった。profile未実装のTypeErrorと比較出力なしのKeyErrorが失敗理由。RED時file SHA-256は `ff3fe67ea608845bc94fda871cce4d39479a219626dc76c3d25cf14d8929dbe5`、この3件の本文を変えずGREENにした。追加wire検査とformatにより最終file全体のSHAは変わっている。関連97 passed。本番のprompt/transport契約は変更せず、診断runnerだけに `landmark-v1` と近似画像検出を加えた。

候補runner SHA-256 `9622cf3a567308d7521a7a9a5d71c1795d6cd9de656c177c454574fe7d2c81dc`、test SHA-256 `31cfbe8a30e1fdb057965b1a22fc604b2dc59ceffad5ff9df733574439113de3`、候補4要求のdiagnostic契約SHA-256 `7538069793bc611d3b3349e9e360cf62d9ed7ef94034325953a455fad9c634b1`。前回のcontrol prompt契約一致、参考画像不変、新規保存先未存在をofflineで確認した。候補promptは532/532/572/542文字の固定英文。実行コマンド・採用前の視点と形状の合格条件は [DEVELOPMENT 6.7](DEVELOPMENT.md#67-同じ参考画像から4方向だけを再生成する限定診断) に記録した。追加liveは未実行であり、ISS-002は未解決。

最終標準offlineゲートは1,991 passed・13 skipped・8 deselected（51.51秒）。lock 79 packages、Ruff、format 253 filesも成功した。追加4 callsのlive比較は条件提示・承認待ちで、生成品質の改善はまだ確認していない。

2026-09-08 16:15 JST: landmark-v1の視点別受入基準、Cloudflareへの参考PNG・新指示送信、4 calls・各120秒・retry 0、既存token利用、0.001384 USD見積り・金額上限なし・別保存という条件に対して利用者が「はい」と承認した。候補runner・testのSHA一致を確認し、記載済みlandmark-v1のコマンドを1回起動した。E2E検索は停止を維持する。

2026-09-08 16:16 JST: landmark-v1はCloudflare 4 calls・retry 0でexit 0となり、4 PNGの512×512 RGB・0600・digestと診断契約一致を確認した。pHash距離は正面/左12、正面/右6、正面/背面24、左/右12、左/背面20、右/背面24で、閾値5以下の組はなかった。しかし目視では正面斜めと右側面がともに取っ手を右に広く見せる像で、右側面の中央edge-onという事前基準を満たさない。背面の取っ手は左へ移動したが、左奥に一部隠れる指定も満たしていない。近似検出を通過しても4方向品質は不合格であり、ISS-002は未解決。本番への採用とE2E検索の再開は行わない。

### 次の切り分け: 同一providerの9Bモデルで失敗視点1枚を比較

4Bで3方式（方向名、camera移動、見える特徴の指定）を試しても右側面を描けていない。文章の追加だけを繰り返さず、Cloudflare上の `@cf/black-forest-labs/flux-2-klein-9b` を限定診断として比較する準備を行う。これは本番provider/model変更の決定ではない。本番の4B Literal・endpoint allowlist・cacheを維持し、独立の診断HTTP adapterで実modelと要求を結び付ける。

- [x] 9B専用の固定endpoint、右側面1 call、同一参考PNG・prompt・seed・寸法、retry 0、private保存、credential非露出をofflineで確認する。
- [x] 9Bの送信先・model変更を含む診断範囲・1 call・費用と保存先を提示して明示承認を得る。
- [x] 9Bで右側面の中央edge-onと同一形状が成立するか目視する。1枚成功だけで4面を解決済みにしない。

9Bでも不適合なら、任意視点の精度が必要な3D/camera条件付き生成と、その実行環境・provider選択を改めて検討する。同じ4B promptの自動再試行や、未承認のmodel切替は行わない。

準備検証: `uv run --frozen --offline --no-sync pytest -q tests/test_view_model_probe.py` はscaffold未実装で4 failedとなった。最初のHTTP検査はrequests import未定義で失敗したためscaffoldのimportを補い、4件すべてNotImplementedErrorとなるREDを確認してから実装した。RED時test SHA-256は `74558be8eb4fd31fdafc3bde69c26f6419fc92a8714c76f28e929b383db3c6b9`。同じ4件がGREENとなり、その後HTTP上限検査を追加した。追加検査でfixtureの存在しないread_callsを参照した誤りをstream_callsへ訂正したため、この失敗はproductionの不具合とは扱わない。関連84 passed。本番request builderのSHAは `2055bde5462b0a57718e2dfe701ecabbf11e7c0a2468aa5b3de4ba43bf638978` のままである。

候補runner SHA-256 `cc4879532e015317c3ffac442fd67d9df0d284a370a491d064d19536219c6ae2`、test SHA-256 `2b9667940c0ea37d2ef585c0feed7aa99db21cafd8ad768729d4e8eeba609b6b`。送信契約・出力・費用・右側面の合格基準は [DEVELOPMENT 6.8](DEVELOPMENT.md#68-9bモデルによる右側面1枚の比較診断) に固定した。9Bへのcredential利用・送信は未実行で、追加承認待ち。

9B診断のoffline preflightで参考PNGの検証、新規出力先未存在、右側面1 callの選択を確認した。diagnostic契約SHA-256は `eea190561a6cac0d87571b7e6f3a9aebd42fc941475e3c5d44a1ac168ed10958`。最終標準offlineは1,998 passed・13 skipped・8 deselected（49.43秒）、lock 79 packages、Ruff、format 255 files、Markdownとdiffも成功した。9B liveは未実行であり、問題解決は継続中。

2026-09-08 16:22 JST: 9Bモデルの右側面1枚比較について、同一参考PNG・指示・seed、512px、既存Cloudflare token、120秒・retry 0、約0.017 USD見積り・金額上限なし・別保存の提示に対して利用者が「はい」と明示承認した。runner・test SHA一致を確認し、記載済みコマンドを1回起動した。E2E検索・本番model切替は行わない。

2026-09-08 16:22 JST: 9Bの右側面1 call・retry 0がexit 0で終了した。512×512 RGB PNG・0600、0700 directory、画像digest、実modelとdiagnostic契約の一致を確認した。目視では取っ手が手前中央に細い曲線として見え、白い円筒形・縁・全体比率を保った右側面となった。4Bで不適合だったこの視点は改善した。ただし正確な奥行き寸法や遮蔽内の形状は1枚から測定できず、4面全体の解決・汎用promptの品質は未検証である。費用は事前見積り0.017 USDで、実請求は取得していない。

### 次の検証: 本番の汎用4方向指示を9Bで実行

マグカップ専用landmark-v1を本番へ一般化する前に、現行 `build_cloudflare_request_set(..., derive_front=True)` が出力するcamera-v2の4要求をそのまま9Bへ送る診断を準備する。参考PNG、seed、寸法、4方向順、promptは4Bのcamera-v2対照と同じにする。変更する要因はmodelだけである。既存1-call modeを保ち、別の `generic-four` modeを追加し、modeごとの1/4回上限を検証する。

- [x] 汎用4要求のそのままの送信、1/4回の分離、未知modeの拒否、失敗時停止をofflineで確認する。
- [x] 9Bの汎用4枚について、送信条件・費用・保存先を提示して追加承認を得る。
- [ ] 4枚が異なる視点、同一の形状・材質・特徴を保つことを目視する。成功した場合だけ本番model変更の具体案と互換性・費用・cache方針へ進む。E2E検索は停止を維持する。

`generic-four` の4挙動は `uv run --frozen --offline --no-sync pytest -q tests/test_view_model_probe.py -k 'generic or unknown_probe'` でmode未実装のTypeErrorによる4 failed・7 deselectedからGREENにした。RED/GREENでtest SHA-256 `982208221f344859e402d91e8e38edc3dd3c4cd41dc778212d891f3df833d679` は同一である。関連20 passed。汎用modeでは本番builderの要求tupleそのものを送信し、実HTTP adapterが全4方向を固定9Bへ送ることをofflineで確認した。1-call modeのcontrol digestと出力契約は維持した。

候補runner SHA-256 `f5ec7f72d0570001e696d0c05476cdf4a7fe7ec7587a9053a73e342ccc8b6263`。追加4-call診断の条件・合格基準・コマンドは [DEVELOPMENT 6.8](DEVELOPMENT.md#68-9bモデルによる右側面1枚の比較診断) に固定した。追加live・本番model変更は未実施である。

汎用4枚のoffline preflightで参考PNG検証、4方向順、新規出力先未存在を確認した。diagnostic契約SHA-256は `5f5d258a32dd0905c482fa8978a0a80d7e0001aac6dc8a1c2ed6acfe5e3a874a`。最終標準offlineは2,002 passed・13 skipped・8 deselected（49.57秒）、lock 79 packages、Ruff、format 255 files、Markdown・diffに成功した。追加4枚への承認待ちであり、1枚の成功から4面品質の解決とは判断しない。

2026-09-08 16:26 JST: 9Bへ汎用camera-v2の4要求を送る追加検証について、同一参考PNG・seed・512px、4 calls・各120秒・retry 0、既存token・約0.068 USD見積り・金額上限なし・別保存の提示に対して利用者が「はい」と明示承認した。候補runner・test SHA一致を確認し、generic-fourを1回起動した。E2E検索は停止を維持する。

2026-09-08 16:27 JST: generic-fourは9B 4 calls・retry 0でexit 0となり、PNG・digest・実model・契約一致を確認した。4枚の構図に差は出たが、左側面は取っ手が左に開き、右側面は取っ手が右に開く像だった。参考camera基準の左右90度に必要な遮蔽・中央edge-onが満たされず、4方向セットは不合格。背面斜めでは取っ手が左手前に見えるが、全セットを同じ座標系で確認できないため解決済みにしない。E2E検索を再開せず、4Bから9Bへの本番切替もしない。

### 回転基準の修正

実装上の不整合を確認した。SEARCH-FLOWは正面・左右・背面を要求するが、現行camera-v2は参考画像のcameraを0度としつつ、左45度・左90度・右90度・右135度を指定し、さらにproductのfront/left/right/rearという未確定の絶対面名を重ねる。単一基準の四等分ではなく、参照からの相対回転とモデルが解釈する絶対面名が混在する。これが全失敗の唯一原因だとは断定しないが、直せる契約不整合である。

診断 `turntable-four` では、cameraを固定し、入力画像のobject姿勢を0度としてobjectだけを上から見て0度・反時計回り90度・時計回り90度・180度へ回す。front/left/right/rearの単語を生成promptから除き、既存angle IDは出力の対応付けだけに使う。正面斜め・背面斜めという既存IDを新規変更せず、汎用の同じ商品の参照相対回転として試験する。マグカップ専用の特徴指示を入れない。過去のcamera-v2診断は変更しない。

- [x] 四等分の回転、camera固定、入力姿勢との対応、既存mode維持をofflineで検証する。
- [x] 9Bの追加4 calls・新指示・費用・保存先の条件承認後に実画像で検証する。結果は不合格。
- [ ] 今回のマグカップでは0度は取っ手が右、反時計回り90度は取っ手が背後、時計回り90度は手前中央、180度は左となり、同一形状を保つことを検証する。1枚でも満たさなければ不合格とする。

`uv run --frozen --offline --no-sync pytest -q tests/test_view_model_probe.py -k turntable` で未対応modeによる1 failed・11 deselectedを確認した。RED時test SHA-256は `afa9d3fe38f0df3210177c657c4fd039d44d86c828cb0e333aedda07acaa3468`。実装後は同じtest内容で1 passed・11 deselected、その後Ruff整形だけを行い、model probeとview regenerationの関連21 passedとなった。liveは未実行で、追加4枚の条件・固定判定基準・コマンドをDEVELOPMENT 6.8に記載した。

turntable-fourのoffline preflightで同一参考PNG・4要求・新規保存先を確認した。diagnostic契約SHA-256は `b7d0cb360b9993ff3ec621d44035a6c35785e63d8b71736ffb8a7a4fb5ff7aa3`、runnerは `cab5eaaa04b88cd3ec987545cf2b2c9e5e01b0d589e1d1c2fb12dd78089ea9c3`、整形後testは `fe7a70611400fd8b8783f8a37ecb99201c147dd097e1f051924a50c3fab40e26`。本番request module SHAは前回と同一である。

最終標準offlineは2,003 passed・13 skipped・8 deselected（50.40秒）。lock 79 packages、Ruff check・format 255 files、Markdownとdiff検査に成功した。turntable-fourの追加liveは未実行で条件承認待ち。

2026-09-08 16:36 JST: turntable-fourの追加4枚について、同じ参考PNG・511px入力・512px出力、回転指示0/90/270/180度、9B endpoint・既存Cloudflare token、4 calls・retry 0・接続/読込各120秒・response 4 MiB・画像2 MiB、約0.068 USD見積り・金額上限なし・別保存の提示に対して利用者が「はい」と明示承認した。runner・test SHA一致を確認し、DEVELOPMENT 6.8のturntable-fourコマンドを1回開始する。E2E検索は停止したままである。

2026-09-08 16:37 JST: turntable-fourは9B 4 calls・retry 0でexit 0となった。実model、事前契約SHA-256 b7d0cb360b9993ff3ec621d44035a6c35785e63d8b71736ffb8a7a4fb5ff7aa3、全4 PNGの512×512 RGB・digest・0600、directory 0700を検証した。目視では0度でも取っ手が手前側へ回り、反時計回り90度はカップが倒れて複数の取っ手に見える形になり、時計回り90度も上面向きと複数の突起を生じ、180度では開口部が下へ向いた。camera固定・垂直軸回転・取っ手1個・形状維持の基準に不合格。指示の混在を除いても今回のmodelは追従せず、契約不整合が唯一の原因ではない。承認済み4 callsは完了し、追加prompt試行とE2E検索は停止する。実請求は取得せず、事前見積りは0.068 USD。

### 取り下げたローカル3D案と調査記録

2026-09-08: 利用者から「本番環境ではiGPUを使うため、3Dモデルのローカル生成は不可」と明示された。以下のローカル3D案は取り下げる。開発機のRTX 4070 Ti SUPERは本番の利用可能資源ではない。モデル取得・環境構築・推論は行っていない。以下は取り下げ前の検討記録である。

Cloudflareで4枚を個別に編集する追加prompt試行はここで止める。次の候補は、参考PNGからHunyuan3D-2系のshapeを1個生成し、参考画像に基づくtextureを付与し、同じmesh・materialを固定cameraの0/90/270/180度で512px描画する独立backend診断である。生成したmeshについてはrendererが角度と遮蔽を幾何的に制御できる。ただし参考画像にない面は推定となり、取っ手・縁・穴・色・比率が元画像に忠実かは別途検証する。meshを使うだけで本来の商品形状が保証されるとは扱わない。

[Hunyuan3D-2公式README](https://github.com/Tencent-Hunyuan/Hunyuan3D-2)で、image-to-shapeとtextureの分離、mini shape model、形状6 GB・形状とtexture計16 GBの目安を確認した。実機は `nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader` でRTX 4070 Ti SUPER・16,376 MiB、確認時空き13,079 MiB。これはGPU情報だけで、依存・CUDA互換性や実推論成功を示さない。現行pyproject/lockにTorch/Diffusersはなく、models内にはCLIPだけがある。数値camera経路を持つ[SV3D](https://huggingface.co/stabilityai/sv3d)も候補として確認したが、model cardは連絡先共有への同意が必要で、今回は取得していない。

方式変更後の作業は本番から分離した環境で依存・model revision・ライセンス・取得容量を固定し、読み込むPNG・推論回数・保存範囲を明示した比較診断を準備する。本番適用は今回の参考例の品質、実行資源、互換adapterと新しいprovider/model/mesh/camera digestを含むcache識別の検証後に判断する。旧4B要求と9B診断metadataを新画像へ流用せず、既存historyは維持する。先行参考画像・偽画像の生成方式も個別に扱い、E2E検索は停止を継続する。この代替方式は提案段階であり、model取得・環境構築・推論・本番切替は未実施である。

### iGPU本番環境に適合するAPI候補

本番の制約をREQUIREMENTS 7へ明記し、ローカル3D生成案を取り下げた。参考画像1枚の確認後、同じ参考PNGを外部の視点変換APIへ渡して4面を生成する構成を候補とする。先行画像・偽画像・ranking・historyの既存実装は維持し、4面生成のprovider adapterとその要求・cache識別を分離する。本番のprovider切替や外部送信はまだ実施しない。

候補は [fal.ai Qwen Image Edit 2511 Multiple Angles](https://fal.ai/models/fal-ai/qwen-image-edit-2511-multiple-angles/api)。公式APIには参考画像、水平角・仰角・距離、出力寸法、seedがあり、512pxと1画像/要求を指定できる。独立4要求で同じ参考画像を入力し、水平角を0/90/180/270度に分ける診断を検討する。APIの角度は内部で専用LoRA用promptへ変換されるため、数値fieldの存在を幾何的な角度保証とは解釈しない。元の取っ手1個・形状・上下・遮蔽を維持できるかは実画像での確認が必要。providerの左右定義と現行angle IDの対応も固定前に確認する。

新APIはCloudflareと異なる認証・費用・応答契約を持つ。採用判断には既存cacheと識別を混ぜない互換adapter、外部送信前の有界要求とresponse検証、画像品質診断を必要とする。現時点は公開仕様の確認のみで、認証情報の取得・使用、画像送信、課金API呼出し、環境への新依存導入はしていない。E2E検索は停止を継続する。

## EXEC-078: 自然言語から画像確認・ランキング・履歴までのbackend live E2E

### メタデータ

- 状態: 旧フローの限定E2E完了・停止中。4方向品質不合格のままEXEC-080で要件撤回
- 作成日・最終更新: 2026-09-08
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)
- 前提: [EXEC-077](#exec-077-参考画像1枚の確認後に4方向と偽画像を生成)

### 目的・範囲

利用者の指示に基づき、実Bonsaiの自然言語解釈とquery生成、先行参考画像1枚、明示了承後の新規4方向と偽画像、最終検索承認、production job、実Outscraper商品・Amazon画像proxy・固定CLIP・暫定ranking v5、SQLite履歴保存と再読込を一つの専用backend E2Eとして実行する。旧2-call診断はこの用途へ流用せず、現行の公開orchestrationとproduction serviceを使う。

固定合成入力は「白い陶器製マグカップ」、視覚条件は「白い」1件。Bonsaiは1 call、画像は先行1と後続5の計6 calls、OutscraperはBonsai由来query 1件・最大24商品・task 1回・poll最大50回、自動retry 0。queryを固定値で代替しない。参考画像と最終生成物の確認を省略しない。実行直前にendpoint、要求、上限、credential、費用見積り、private保存範囲を提示し、明示承認後だけliveを開始する。

対象外は委託frontendの確認・起動・接続、browser、公開API/server配備、別queryの追加実行、未知データの品質評価、commit/push。画像とランキング・履歴の利用者向け出力を新規0700 directoryの0600 filesへ限定し、生provider応答・credential・承認tokenを出力しない。

### 受入条件・進捗

- [x] 専用runnerの承認前停止・拒否・改ざん・1回実行・履歴再読込を、実通信なしのbehavioral REDからGREENで確認した。
- [x] 本番のBonsai・画像生成・production job経路を使う専用runnerと、三重opt-inのlive nodeを追加した。fixture実行とlive実行を分ける。
- [x] 実行環境、固定model、利用条件、最新の公式料金を確認し、具体的な実行内容を提示する準備を完了した。利用者が「開始せよ」と明示承認し、2026-09-08 15:49 JSTに専用nodeを1回開始した。
- [x] 明示承認後にlive専用nodeを1回実行し、途中の画像確認を実ユーザーへ求める。
- [x] ランキング出力と再openした履歴の一致を確認し、成功・失敗・未実施を各段階で記録する。

### 停止・再開・復元

入力がblocking、provider失敗、画像確認の拒否・期限切れ・改ざん、job失敗、履歴不一致では停止する。失敗時に同じ承認で再実行しない。利用量と失敗記録を保持し、rawデータから原因を推測しない。起動したBonsai serverだけを終了し、既存server、既存private出力、既存の未コミット変更を変更・削除しない。runner追加のrollbackは今回追加したfileと文書参照だけを対象とする。

### 検証結果

初回の公開scaffoldに対する7件は6 failed・1 passedで、先行停止・後続生成・履歴出力が未実装で失敗した。同じtest file SHA-256 `83fc1bf37747d74fb0e3a5330f2c1b7ceb5e1d44f97acb09317e632f0595d553` のまま7 passedとなった。追加の実HTTP dispatchと失敗件数は2 failed・2 passed・7 deselectedから実装した。dispatchの最終確認でangleの期待名が既存契約と異なったため、`front_three_quarter` 等の実際の4 enumへtestを訂正した。この訂正後のtestを初回と同一bytesとは扱わない。

Bonsai serverの起動失敗・呼出中例外cleanupと三重opt-inは、3 failed・7 passed・1 deselectedから実装した。RED時entry test SHA-256は `432ab307ee4c703a83bb02d262b949ba82199276f468b9046713e3b9d2498f46`。live test本体を後から追加したためfile全体は変更されるが、該当するoffline test本体は変更していない。新規focusedは21 passed・1 deselectedである。

関連回帰は94 passed・5 deselected、標準offlineゲートは1,981 passed・13 skipped・8 deselected、50.28秒で成功した。lock 79 packages、Ruff、format 251 files、現行Markdownと差分検査も成功した。最終SHA-256はrunner `934c6f5c52ad6a0ed676757847ae412d5bdea1582ba969db7098d2ecbe4c5da8`、flow test `40841dc71195b561bc137e53cab877e9240963003e13df0fe305253e87510cce`、entry test `19d09095d9e19bbb20fb85f8b675c29b19e0b34b161b989c2812854e88e3befc`。

2026-09-08の[Cloudflare公式単価](https://developers.cloudflare.com/workers-ai/models/flux-2-klein-4b/)は512×512入力tile 0.000059 USD、出力tile 0.000287 USDであり、今回の出力6枚と入力5枚は約0.002017 USD。[Outscraper公式単価](https://outscraper.com/amazon-scraper/)の無料枠外2 USD/1,000商品を最大24商品へ適用すると0.048 USD、合計見積りは約0.050017 USDである。基本契約や実請求を取得した値ではなく、金額上限も設けない。生成queryは実Bonsai応答後に提示し、最終確認で人間が了承するまでOutscraperへ送らない。

ローカルpreflightでは既存Bonsai server・GGUFのSHA-256と固定CLIP asset一式を確認した。指定output pathは未存在、port18080は非listenだった。Bonsai起動、credential利用、live通信、課金はまだ行っていない。実行手順と保存範囲は [DEVELOPMENT 6.6](DEVELOPMENT.md#66-自然言語からランキング履歴までの本番backend-e2e) を参照する。

2026-09-08 15:49 JST: 提示済み条件に対して利用者が「開始せよ」と承認した。runner・testの最終SHA一致、output未存在、port非listen、Cloudflare/Outscraperの型付きcredential設定、固定CLIP assetを確認し、専用live nodeを1回起動した。資格情報の値は出力せず、商品検索はrunner内の最終確認後にだけ開始する。実Bonsai 1 callでstrict intentとquery生成に成功し、Cloudflare 1 callで先行512×512 PNGを生成して参考画像への了承待ちで停止した。queryは固定値の代入ではなく実Bonsai由来である。画像は白い無地のマグカップとして目視確認した。Bonsai serverは終了し、後続5画像・Outscraper・商品画像・CLIP・ランキング・履歴はまだ実行していない。

2026-09-08 15:51 JST: 先行画像の提示後、利用者が「了承した」と明示した。同じ稼働中nodeの確認入力を1回だけ進め、先行画像を共通参照とした後続4方向と偽画像1枚を生成中。商品検索の最終確認は未承認であり、Outscraperはまだ開始しない。

後続5 callsも成功し、計6枚の512×512 RGB PNGを0600で保存して生成物とqueryの最終確認待ちに到達した。4方向指定の画像は全てほぼ同じ向きであり、視点の分離は確認できなかったため [ISS-002](ISSUES.md#iss-002-4方向指定の生成画像がほぼ同じ向きになる) として記録した。偽画像は青いマグカップで、色の反転は目視できた。Outscraper・商品画像・CLIP・ランキング・履歴は未実行である。

2026-09-08 15:55 JST: 4方向指定画像がほぼ同じ向きである点、青い偽画像、実生成queryを提示し、利用者が「はい」と最終承認した。同じnodeへ検索の固定確認文を1回だけ入力し、production jobの商品検索・ランキング・履歴へ進めた。ISS-002は承認によって解決扱いにしない。

2026-09-08: 同じlive nodeが667.58秒で1 passedとなった。Bonsai 1 call、Cloudflare 6 calls、Outscraper 1 task・8 polls、商品画像23 GETすべて成功、固定CLIP 7 batches、23商品ranking、履歴再openと参照画像2枚のpixel一致を確認した。独立read-backでもranking/historyの23商品一致と全出力0600を確認した。4方向品質はISS-002として未解決であり、要求全体の品質合格とは扱わない。利用者の再生成指示をEXEC-079で継続する。

## EXEC-077: 参考画像1枚の確認後に4方向と偽画像を生成

### メタデータ

- 状態: 完了（offline接続・Figma。実provider・委託UIは未検証）
- 作成日: 2026-09-08
- 最終更新: 2026-09-08
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)
- 関連要件: FR-403、FR-404、FR-405、FR-411、UI-009、UI-011
- 関連文書: [SEARCH-FLOW.md](../SEARCH-FLOW.md)、[BACKEND.md](BACKEND.md)、[FRONTEND.md](FRONTEND.md)、[SECURITY.md](SECURITY.md)、[DB-SCHEMA.md](DB-SCHEMA.md)

### 目的と範囲

参考画像フェーズでまず1枚だけ生成して利用者へ確認を求め、了承後だけ、その画像を参照した4方向の新規画像と条件別の偽画像を生成する。採用する画像全体の確認と商品検索の最終確認を引き続き分離する。既存Figmaのデスクトップ画面と関連componentを同じ操作順へ更新する。

対象はfrontendに依存しない画像生成・明示承認・後続生成のbackend境界、暫定production orchestrationの公開入口から既存SQLite参照承認への接続、回帰テスト、目標仕様とFigmaである。委託フロントエンドの確認・起動・テスト・API接続、実画像生成、商品検索、credential、課金、deploy、commit、pushは対象外である。Figmaの編集は今回の利用者指示に基づく。

### 着手時点と受入条件

着手時の利用者フローは4枚一括生成後の確認だけを定義し、暫定counterfactual backendもdesiredと条件別counterfactualをまとめて生成してから確認していた。新仕様では以下を満たす。

1. 参考画像ON時の初回操作で生成する画像は1枚だけとし、成功後は確認待ちで停止する。
2. 先行画像、条件、owner・sessionへ結び付いた明示承認がある場合だけ後続4方向と偽画像を生成する。未承認、古い確認、二重承認から生成しない。
3. 先行1枚の初回と作り直しは1計画最大2回。後続は同じ承認につき1回だけ実行し、自動retryまたは部分採用をしない。
4. 偽画像は最大3件の視覚条件に対して1枚ずつ生成し、変更した条件を明示する。実商品または商品仕様の証拠として扱わない。
5. 先行生成中、先行確認待ち、後続生成中、全体確認、失敗、作り直し、画像OFFの操作を文書とFigmaで一致させる。
6. offlineテストと静的確認で承認前の停止を検証し、実provider・委託UIの成功とは区別する。

### 実行順序と進捗

- [x] M1: 現行の文書、独立backend、Figma参照先を調査し、先行1枚と後続生成を別操作と決定する。
- [x] M2: 初回の公開API契約未実装と、TDD工程の逸脱を記録する。最初の2件は新しい `condition_set` 引数を受けない `TypeError` で失敗した。初回test SHA-256は `52f48080166a97b5733ad21cc78420bc6edce55e92e095a0c917eb6196accd4c`。これは未実装APIのREDであり、先行1枚停止・承認binding・後続生成の動作を実行して失敗した証拠ではない。
- [x] M3: coreのfocused 36件と、暫定production公開入口からjob・履歴までのfocused 46件をGREENにし、変更した契約をread-backした。
- [x] M4: 利用フロー、要件、backendの具体的な型・接続、保存・安全境界とFigmaの先行1枚・後続生成中・生成物確認を同期する。Figmaは対象3状態と関連4ページを更新し、スクリーンショットで確認した。
- [x] M5: 関連テストと標準offlineゲートで1960 passed・13 skipped・7 deselectedを確認した。lock 79 packages、Ruff、format 248 files、Markdownリンク、`git diff --check` は成功。実provider・委託UIは未実施。

### セキュリティ・データ・互換性

先行1枚の承認は後続生成にだけ使い、商品検索の最終承認を代替しない。条件または先行画像を変更したら旧承認と後続画像を失効させる。失敗利用量を削除せず、後続呼出しを先行生成の予約へ混在させない。承認tokenと画像bodyをログ、通常UI、serializable metadataへ露出させない。

既存4方向schemaと暫定counterfactual schema、保存済み履歴を新フローの承認済みデータと読み替えない。先行1枚は了承・生成binding用、後続4方向は既存image setへ採用、偽画像は生成物確認で利用し、履歴schemaと保存範囲は変更しない。画像生成の内容・同一性・未知条件品質はoffline成功だけで保証しない。

### 判断とロールバック

利用者の「了承後に4面」を先行1枚とは別の4方向新規生成として扱う。先行画像は方向生成と条件別偽画像の共通参照にする。偽画像枚数は既存視覚条件数1〜3を維持し、上限を自動で増やさない。先行画像の作り直し回数だけを利用者へ表示する。

旧provisional live runnerは、Bonsaiを呼ばず固定合成条件から低位の2-call adapterを直接診断する独立境界として互換性を維持する。このrunnerの過去または将来の成功を、新しい公開入口、先行画像確認、4方向と偽画像、UIを含むフローの検証へ読み替えない。

rollbackは今回追加した生成・承認境界と参照を一組として戻し、既存履歴・利用量・ユーザーの未コミット作業を削除しない。Figmaは既存component構造と編集前のnode構成を記録し、変更した画面とcomponentだけを復元する。

### 検証工程の逸脱

core実装では、初回のAPI未対応REDの後に `source_input` 照合などの境界を追加し、対応testも変更した。失敗回復、古い画像、利用量合算、並行了承などの追加境界testは修正後に追加してGREENを確認しており、修正前の同じtest bytesによる動作上のREDは実行していない。これは「振る舞いを変える前にREDを確認する」という開発規約からの工程逸脱であり、同一testのRED→GREENまたはattested TDD完了とは扱わない。

利用量欠落はreviewerがfixtureで再現したが、この再現も最終回帰testの修正前実行と同一の証拠ではない。追加回帰のGREENは修正後の境界を確認する証拠として残し、実行しなかったREDを補記しない。

暫定production側の後続修正では、古い生成物に対するSQLite承認が `DID NOT RAISE` となるREDと、新しい画像承認済みplanが従来の画像OFF限定validatorに拒否されるREDをそれぞれ確認してからGREENにした。この個別のRED→GREENを、coreの未実施工程と混同しない。最終reference test SHA-256は `c727aa32a70191e4e16a90ec14829896d8f0c49ea7519ac0912c7dd5125845d5`、production flow testは `44445d607b52fa91a7ef2b9303a26aec719c63c0b52fef2d525fdf4552cc0b75`。

stale承認のREDコマンドは `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_provisional_reference_flow.py::test_provisional_final_approval_rejects_images_after_reference_replacement` で、1 failed。production拒否のREDコマンドは `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_provisional_production_flow.py` で、1 failed・3 passedだった。

### 結果と残る境界

完了。coreと暫定productionの公開入口を実装し、全体offline gateを確認した。利用フローの先行1枚確認、了承後の4方向と条件別偽画像、全体確認、作り直しと失敗時の操作を更新した。Figmaは [先行1枚](https://www.figma.com/design/PEVM5G4854vaDqdWgSA3ui?node-id=59-22)、[後続生成中](https://www.figma.com/design/PEVM5G4854vaDqdWgSA3ui?node-id=169-71)、[生成物確認](https://www.figma.com/design/PEVM5G4854vaDqdWgSA3ui?node-id=169-172) と関連4ページを更新し、保存後の構造とスクリーンショットを確認した。先行カード1枚、後続4方向と偽画像1枚の例、Reference Sheetの3サムネイルを照合し、字体の不一致とvisible auto-layout overflowは0件だった。実providerと委託フロントエンドは実行していない。

coreのfocused確認は `uv run --frozen --offline --no-sync pytest -q -m 'not live_api' tests/test_search_v2_reference_image_approval.py tests/test_search_v2_reference_image_flow.py tests/test_search_v2_orchestrator.py` で36 passed。先行1枚停止、了承後の4方向と偽画像、失敗後の画像OFF・作り直し、古い画像と最終確認の拒否、過去後続利用の合算、並行single-use、期限、予約失敗回復を確認した。最終flow test SHA-256は `f679f88ec1098aa09f48474f96b9efd064f14094b3c913f779bb62dbecae9a01`、approval testは `94a5bfb84969a4f0036409d70384726b0da9910529380ed3ff3ecfb1e90e7d1d`。

暫定productionのoffline E2Eは、先行1枚→了承後4方向＋偽画像1枚→SQLite参照承認→検索の最終承認→production job→fixtureの商品取得・CLIP→SQLite履歴の再openを確認した。画像6 calls、二重job submitでも商品要求1回で、保存されたdesiredと偽画像2枚のpixelは生成物に一致する。全角文字を含むraw入力と視覚条件の正規化sourceを別照合し、正規化結果が同じでも異なるraw入力は拒否した。schema 5.0履歴の保存枚数・役割とranking方式は維持し、4方向の追加保存や新画像品質の合格とは扱わない。

暫定productionの関連確認は次で46 passed（8.90秒）。

```sh
uv run --frozen --offline --no-sync pytest -q \
  tests/test_search_v2_provisional_reference_flow.py \
  tests/test_search_v2_provisional_production_flow.py \
  tests/test_search_v2_production_search.py \
  tests/test_search_v2_provisional_approval_repository.py \
  tests/test_search_v2_counterfactual_reference_approval.py \
  tests/test_search_v2_counterfactual_derived_images.py \
  tests/test_search_v2_counterfactual_cloudflare_http.py \
  tests/test_search_v2_counterfactual_cloudflare_request.py
```

初回全体gateでは旧history fixtureの1呼出しが新しい `source_input`・`condition_set` を持たず失敗した。fixtureを先行1枚→了承→4方向と偽画像へ同期し、履歴4枚と並び順の既存検証を保持してfocused 9 passedを確認した。その後の `uv run --frozen --offline --no-sync pytest -m 'not live_api'` は1960 passed・13 skipped・7 deselected（43.71秒）で成功した。`uv lock --check --offline`、`uv run --frozen --offline --no-sync ruff check .`、`uv run --frozen --offline --no-sync ruff format --check .`、`uv run --frozen --offline --no-sync python tools/check_markdown_links.py`、`git diff --check` も成功した。

残る境界は [TASK-008](#task-008-次期検索フロー-v2-の実装) のHTTP controller・委託UI接続、process再起動後の先行確認復元、実providerを使う新フローと生成品質の確認である。今回の実装と検証は未コミットであり、commit・push・deployは行っていない。

## EXEC-076: local検索job・履歴HTTP API

### メタデータ

- 状態: 完了
- 作成日: 2026-09-08
- 最終更新: 2026-09-08
- 関連Task: [TASK-001](#task-001-検索処理のジョブ化)、[TASK-008](#task-008-次期検索フロー-v2-の実装)
- 前提Plan: [EXEC-056](#exec-056-ローカル単独利用向け検索ジョブ基盤)、[EXEC-075](#exec-075-暫定本番検索のjob履歴接続と無quota方針)

### 目的

最終承認済み検索をlocal background jobへ冪等投入し、job状態取得、協調的取消、成功履歴取得をHTTPから行えるようにする。利用者が将来観察するAPI結果には、検索状態、取消可否、成功時の履歴locator、表示用の検索結果だけを含め、owner、binding、provider、内部score・digestを含めない。

### 対象範囲

- 対象: Starlette ASGI application factory、server-side固定local owner、承認済みcommandを一時保持するin-memory submission capability、job投入・状態取得・取消・schema 5.0履歴詳細取得、固定JSON error、loopback client限定、offline HTTP test、標準文書の同期
- 対象外: 委託フロントエンドの内容確認・起動・テスト・接続、Bonsai・Cloudflare・Outscraper・Amazon実通信、credential読取り、課金、公開・多利用者向け認証、複数host・process・worker、履歴一覧・画像body・削除API、deploy、commit、push

### 現在の状態

着手時、`ProvisionalProductionSearchService` は最終承認済み検索をlocal jobへ投入し、Outscraperからschema 5.0履歴保存までをworker callbackへ接続していた。`LocalSearchJobExecutor` は状態取得と取消、`SqliteProvisionalHistoryRepository` はowner付き履歴詳細取得を提供していたが、HTTP transportは存在しなかった。production commandはraw single-use承認tokenを含む同一process内の一時値なので、JSON bodyへ直列化せず、将来の最終承認controllerが登録する短命なin-memory capabilityから解決する方針とした。

### 受入条件

1. `POST /api/v1/search-jobs` はserver-sideで登録された未期限のsubmission capabilityだけを受け、同じcapabilityの二重送信へ同じjob locatorを返す。owner、command、tokenをrequest bodyやURLへ含めない。
2. `GET /api/v1/search-jobs/{locator}` はjob状態、取消可否、時刻、成功時の履歴locatorだけを返し、owner、binding SHA、固定内部failure codeを返さない。
3. `POST /api/v1/search-jobs/{locator}/cancel` はqueued・runningだけを既存executorへ渡し、terminalまたは競合状態を固定409へ変換する。provider threadの強制停止や自動retryを追加しない。
4. `GET /api/v1/search-history/{locator}` は固定local ownerの未期限schema 5.0履歴を表示用schemaへ投影し、profile、holdout accuracy、digest、内部score、画像bodyを返さない。取得操作からproviderまたはrankingを呼ばない。
5. APIはloopback clientだけを受け、requestからownerを受け取らない。not found、期限切れ、別owner相当を同じ固定404へ変換し、例外本文、path、credential、外部responseをJSONへ含めない。
6. API追加は委託フロントエンドを確認・接続せず、実provider・credential・課金なしのASGI offline testと標準gateで検証する。

### 実行手順と進捗

- [x] 2026-09-08: governing文書、既存job・production service・schema 5.0履歴契約、dirty worktree、未納品frontend境界を確認した。
- [x] 2026-09-08: 新application service込みlive E2Eを行わず、HTTP API実装へ進む利用者判断を記録した。
- [x] 2026-09-08: API受入testを先に追加した。module不在のcollection error後、公開scaffoldに対する6 failedのbehavioral REDを確認した。
- [x] 2026-09-08: 最小ASGI実装、最大15分のsubmission capability、表示用projection、固定error mappingを追加し、期限切れ・取消競合・例外秘匿・405も含む11件をGREENにした。
- [x] 2026-09-08: 関連31件と標準offline gateを実行し、要件・設計・セキュリティ・進行文書を同期した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | focused API test | HTTP module未実装で失敗 | 初回はmodule不在でcollection error、scaffold後は未実装固定例外で6 failed。behavioral RED時test SHA-256は `a70947f8088bac2452d41c63059bc43005f513f15630eb05b1323d605c142a0f` |
| focused GREEN | focused API test | 4 endpoint、projection、error、loopback境界が成功 | 11 passed |
| 関連回帰 | production service、job、履歴、API test | 外部通信なしで成功 | 31 passed |
| 標準gate | lock、Ruff、format、Markdown、offline pytest、diff | 終了0 | lock 79 packages、Ruff成功、format 243 files、Markdown 16 files・local link 1,417件・anchor 1,013件・heading 1,852件・fence 207組、pytest 1,927 passed・13 skipped・7 deselected、diff成功 |
| live・UI | provider、credential、browser、委託frontend | 実行しない | 対象外 |

### セキュリティ・データ・互換性

submission capabilityは承認tokenそのものではなく、URL・bodyへ入れず専用headerで同一processの短命commandへ結ぶ。job投入後はstore内のcommand参照を破棄し、capability再送時は既存jobだけを返す。APIは現行local-only境界としてloopbackへ限定し、公開認証・tenant分離の代替とは扱わない。SQLite schema、provider adapter、操作単位のcall・poll・timeout・retry契約は変更しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-08 | 承認済みcommandをJSON化せず短命なin-memory capabilityで解決する | raw承認token、検索条件、参照画像を新しいHTTP payloadへ複製しないため | 最終承認stateをprocess間で永続化する場合は暗号化・失効・migrationを別Planで設計する |
| 2026-09-08 | ownerは `local-user` をserver-side固定しloopbackだけを許可する | 現行の単一host・単一process・1利用者境界を越えて認証を推測実装しないため | 外部公開または複数利用者化ではTASK-003を先行する |
| 2026-09-08 | 履歴詳細APIから内部scoreとprofile metadataを除外する | 通常画面へ内部評価値・方式を公開しない既存表示契約を守るため | 運用者向けdiagnostic APIは認証・監査付きの別契約にする |

### 発見事項

- Starletteはlock内に推移依存として存在したが、production APIが直接importするため `pyproject.toml` の直接依存へ追加し、現行pyproject全体に対してofflineでlockを同期した。
- Starletteのtest clientへ新しい依存を追加せず、ASGI scopeを直接呼ぶoffline testでclient address、header、status、body、response headerを確認できた。

### ロールバック

新しいHTTP module、focused test、Starlette direct dependency、本Planに対応する標準文書差分だけを戻す。既存job・history SQLite、production service、provider、frontend、外部状態は変更しない。

### 結果

完了。`production_api.py` に4 routeを持つlocal Starlette application factoryと、最大15分のin-memory submission capabilityを追加した。capabilityは専用headerだけで受け、最初の投入後にcommand参照を破棄し、期限内の再送では同じjobを返す。状態取得と取消は既存job service、履歴詳細取得は固定 `local-user` のschema 5.0 repositoryを呼び、HTTP responseからowner、binding、内部failure code、profile、known accuracy、digest、score、画像body、生例外を除外した。loopback以外、未知・期限切れ、terminal取消、storage失敗、method違反を固定JSONへ投影する。

focused 11件、関連31件、offline全体1,927件、lock、Ruff、format、Markdown、差分検査は全て成功した。最終SHA-256はmodule `5d64e222adcd67fabda3b50ed5bba910b9c554c4c47ad8d10d13d7d619a5183a`、test `0f1c62edfab7e794ac22a99710c13eb4bbaf48ee3b3f8fde49a1a9ff45625828` である。実Bonsai・Cloudflare・Outscraper・Amazon、credential、課金、browser、server起動、最終承認controller、外部委託中フロントエンド、deploy、commit、pushは実行・接続していない。これはoffline ASGI境界の実装完了であり、production E2E成功を意味しない。


## EXEC-075: 暫定本番検索のjob・履歴接続と無quota方針

### メタデータ

- 状態: 完了（offline統合）
- 作成日: 2026-09-08
- 最終更新: 2026-09-08
- 関連Task: [TASK-001](#task-001-検索処理のジョブ化)、[TASK-008](#task-008-次期検索フロー-v2-の実装)
- 先行Plan: [EXEC-056](#exec-056-ローカル単独利用向け検索ジョブ基盤)、[EXEC-066](#exec-066-counterfactual-v4の暫定本番実装)、[EXEC-073](#exec-073-outscraper商品画像から暫定ranking-v5への統合境界)、[EXEC-074](#exec-074-人間確認で停止する商品画像ranking-live-runner)

### 目的

人間が最終承認した暫定production検索を、固定local owner・単一process・worker 1本の検索jobへ冪等投入し、Outscraper 1 task、商品画像、固定CLIP、ranking v5、schema 5.0履歴保存までを一つのapplication serviceで接続する。本番ではper-user・session・day・costの利用量quotaを設けず、reservationは課金上限ではなく、開始済みattemptと承認bindingの記録に限定する。

### 対象範囲

- 対象: quota無効を明示するusage policy、既存のsingle-use最終承認、Outscraper task作成exact 1回・自動retry 0、最大24候補、商品画像GET最大24回、固定CLIP最大7 batches、暫定ranking v5、schema 5.0履歴、job成功時の履歴locator、同一bindingの二重投入防止、fixtureによるoffline E2E、標準文書の同期
- 対象外: 本Plan中のBonsai・Cloudflare・Outscraper・Amazon実通信、credential読取り、課金、browser、API、委託フロントエンドの確認・接続、複数host・process・worker、deploy、commit、push

### 受入条件

1. production用usage policyはquota無効を型として明示し、日次・session・費用累計を理由に予約を拒否しない。既存のquota有効policyと上限超過testは変更せず維持する。
2. 利用量無制限は、1回の利用者操作に対する処理契約を無制限にしない。Bonsai 1 call、Cloudflare exact `1 + N` calls、Outscraper task 1回、候補・画像・poll・byte・timeout上限、自動retry 0、明示承認、single-useを維持する。
3. application serviceは、固定local ownerの未消費search approval、同じintentに結ばれた承認済みcounterfactual参照、条件、元入力をjob bindingへ結び、置換・期限切れ・二重消費を外部通信前に拒否する。
4. workerは既存Outscraper認可・HTTP、暫定検索pipeline、履歴snapshot・repositoryを順に呼び、成功時だけ履歴locatorをjobへ保存する。生検索文、approval token、商品、URL、provider本文、生例外をjob DBへ保存しない。
5. 同一bindingを二重投入しても外部処理callbackと履歴は1回だけで、取消・失敗後の自動再実行を行わない。
6. offline fixture E2Eはprovider transport、画像proxy、CLIP encoderを注入し、外部通信なしで承認済み投入からjob完了・履歴再読込までを確認する。live、browser、production E2E成功とは表現しない。

### 実行手順と進捗

- [x] 現行の暫定参照承認、Outscraper認可、ranking v5、履歴、jobの契約とEXEC-074の限定live成功を確認した。
- [x] 本番quotaを設けず、操作単位の回数・候補・timeout・retry・承認契約は維持する判断を記録した。
- [x] quota無効policy、production application service、job・履歴接続のtestを先に追加し、production code未変更でimport errorのREDを確認した。
- [x] 最小実装でGREENにし、owner・session差し替え、重複投入、失敗、自動retryなし、job DBの本文非保持を関連回帰で確認した。
- [x] 標準offline gateを実行し、NEXT-STEPS、要件、設計、開発・試験文書を現行状態へ同期した。

### 検証

| 対象 | 結果 |
|---|---|
| RED | `build_no_quota_usage_policies` が存在しないimport errorで停止し、実装前に要求差分を確認した |
| focused | production service、usage ledger、orchestrator、参照承認、評価、履歴、jobの73件が成功した |
| 全v2 | `pytest -q tests/test_search_v2_*.py -m 'not live_api'` は1,082 passed・13 skipped |
| 標準offline gate | lock 79 packages、Ruff check、format 241 files、Python 3.10 AST 234 files、Markdown 16 files・local link 1,406件・anchor 1,004件・heading 1,835件・fence pair 207件、pytest 1,916 passed・13 skipped・7 deselectedが成功した |
| live・UI | 実provider、credential、課金、browser、委託フロントエンドは実行・確認していない |

最終SHA-256はapplication service `82b7cac447613d4e97e53b70f4a661b63674223a91fc550d4f2048c2339fe0bb`、usage ledger `48cb3035260e08afe4070f83b4666a6fe8f947db125bfc9abd4dd6e5ebe0f666`、service test `c3f9ea8ba26dc6e691f4de800efb98340a076962985e22e429cf4da6f145ce38`、ledger test `33503963d25109883a20103e551a0bd2ee92bab8e4d8a18b194dcac014791288` である。

### 結果

完了。quota有効policyを互換維持したまま、現行local production用の明示的なquota無効policyを追加した。production serviceはBonsai・Cloudflare・Outscraperのいずれかにquota有効policyが注入された場合も構築時に拒否する。最終承認済み検索と同じowner・session・元入力に結ばれた承認済み参照だけをlocal jobへ投入し、worker内でOutscraper 1 task、最大24商品画像、固定CLIP、暫定ranking v5、schema 5.0履歴保存を実行する。重複投入は既存jobを返し、失敗・取消後も自動再実行しない。fixture E2Eでは成功履歴の再読込まで確認したが、新serviceを含む実provider E2E、API、UI、deployは未実施である。

### 判断記録

| 日付 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-08 | 本番ではper-user・session・day・cost quotaを設けない | 利用者が本番方針として明示したため | 公開・複数利用者化、provider側契約変更、運用上の濫用対策が必要になった場合だけ別Planで再検討する |
| 2026-09-08 | exact call数等はquotaではなく操作契約として維持する | 二重送信、暗黙retry、無界poll・response・候補処理を防ぎ、承認した1操作の意味を固定するため | 検索品質またはprovider契約変更時は、回数変更を新しいschema・回帰testへ結ぶ |
| 2026-09-08 | 委託フロントエンドを待たずbackend job callbackを接続する | 利用者が段階5までのbackend実装を明示したため | UI/API接続は納品完了が明示された後の別作業とする |

### ロールバック

新しいquota無効mode、production application service、focused test、対応文書だけを一単位で戻す。既存quota有効policy、live runner、provider adapter、SQLite job・履歴data、credential、外部状態は変更しない。


## EXEC-070: Cloudflare応答画像の安全な形式正規化

### メタデータ

- 状態: 完了
- 作成日: 2026-09-07
- 最終更新: 2026-09-07
- 先行Plan: [EXEC-069](#exec-069-cloudflare-live画像内容診断)
- 関連課題: [TD-011](ISSUES.md#td-011-画像取得推論の実環境検証)

### 目的

Cloudflareが成功応答で返すBase64画像を、公式契約にないraw PNG限定で拒否しない。JPEG・PNG・WebPを非信頼入力として有界に検証し、単一frame・exact 512×512だけを従来と同じmetadataなしRGB PNG artifactへ正規化する。

### 対象範囲

- 対象: `src/search_v2/cloudflare_http.py` の画像decode・正規化、Cloudflare HTTPとlive runnerのoffline fixture test、関連するbackend・security・test・履歴文書
- 対象外: endpoint、model、prompt、request field、credential、timeout、retry、利用量、保存schema、画像ranking、実Cloudflare再試行、API、frontend、deploy、commit、push

### 現在の状態

Cloudflare公式モデル仕様は成功結果をBase64画像とするがraw形式を固定していない。修正前のparserはPillow decode前にPNG signatureを要求し、`formats=("PNG",)` へ限定するため、有効な512×512 JPEGでも `image_content` になっていた。外部通信済みの実応答byteは保持していないため、その形式は不明である。

### 実行手順と進捗

- [x] 公式モデル仕様、現行parser、追加live診断、外部実行境界を再確認した。
- [x] JPEG・WebPの成功正規化と、不正形式・寸法違い・複数frame・oversize・破損拒否を先にtestへ追加し、PNG限定による3 failed・10 passedのREDを確認した。
- [x] magicとPillow formatをJPEG・PNG・WebPへ限定し、完全decode・単一frame・exact寸法・metadata除去・正規化後上限を維持する最小修正で13 passedのGREENにした。
- [x] 関連Cloudflare回帰133 passed・1 skippedと標準offline gateを実行し、文書を現行動作へ同期した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| TDD RED/GREEN | Cloudflare HTTP・live runnerのfocused pytest | 修正前はJPEG/WebPが画像内容で失敗し、修正後は正規化PNGになる | 同一testでRED 3 failed・10 passed、GREEN 13 passed |
| 関連回帰 | Cloudflare request・HTTP・counterfactual・live offline tests | 外部通信なしで全件成功 | 133 passed・1 skipped |
| 標準gate | lock、Ruff、format、Markdown、`pytest -m 'not live_api'`、diff | 全て終了0 | lock 79 packages、Ruff 232 files、pytest 1,866 passed・13 skipped・4 deselected、Markdown 4 passed、diff成功 |

### セキュリティ・データ・互換性

応答上限4 MiB、Base64 decode画像2 MiB、exact 512×512、単一frame、完全decode、decompression bomb警告拒否、正規化後2 MiB、metadata除去、body非serializeを維持する。入力形式だけをJPEG・PNG・WebPへ広げ、公開artifactは従来どおりschema 2.0のRGB PNGなので保存・呼出側の移行は不要である。実装とoffline gateでは外部通信、credential利用、課金を行わなかった。後続のlive確認は条件と費用を再提示して別の明示承認を得た1 callに限定した。

### 判断記録

| 日付 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-07 | provider raw画像はJPEG・PNG・WebPだけ受理し、任意のPillow decoderへ広げない | 公式契約の形式不定へ対応しつつ、攻撃面とテスト範囲を明示的に限定するため | Cloudflareが別形式を公式に固定した場合は、fixtureと安全条件を追加した別変更で見直す |
| 2026-09-07 | artifact形式とschemaは変更しない | 呼出側、履歴、参照画像処理へ互換性変更を広げないため | 正規化PNGの契約自体を変える場合は新schemaと移行方針を必要とする |

### 発見事項

- 最初の標準gateはPlan内のTD-011リンク先見出しが誤っており、コード関連1,865件成功・Markdown 1件失敗だった。正確なanchorへ修正し、外部通信なしで全gateを再実行した。

### ロールバック

追加する形式fixtureと画像decode変更を一単位で戻せば、従来のraw PNG限定へ戻る。外部状態と保存済みartifactは変更しない。

### 結果

完了。provider raw画像はmagicとPillow formatの両方でJPEG・PNG・WebPだけに限定し、2 MiB以下、単一frame、exact 512×512、完全decode、decompression bomb警告拒否を通過した場合だけmetadataなしRGB PNGへ再encodeする。BMP、破損JPEG・WebP、寸法違い、animation、oversizeは固定画像エラーのままである。公開artifact、schema 2.0、保存処理、参照画像処理、retry・timeout・利用量契約は変更していない。

最終SHA-256はmodule `d1a0126bf308417e856bfbc7a6e3b323c92a699bbb54a4558805022d4f96e928`、HTTP test `7b26c07ba1aafe32ceb6b3b69e47f799091bc5f954f13b1f68bf32caa50833f3`、live runner test `4110ca4af4e6471f7a58bca76048e6e8a26077b171382d07963e9a172ffae19a` である。実装検証はfixture・mock・offlineで完了した。その後、条件・費用を再提示して別の明示承認を得た基準画像1 callは11.728秒、retry 0で成功し、175,824 bytesの512×512・単一frame・metadataなしRGB PNGを0600で保存した。credential値、生要求、生応答は表示・保存していない。これは固定合成条件1件の実Cloudflare結合成功であり、4方向set、counterfactual生成、画像品質、実請求額、production E2Eは未確認である。

## EXEC-074: 人間確認で停止する商品画像ranking live runner

### メタデータ

- 状態: 進行中（DNS上限と全missing outcomeをoffline修正、修正後live未実行）
- 作成日: 2026-09-08
- 最終更新: 2026-09-08
- 関連Task: [TASK-005](#task-005-ランキング品質評価の確立)、[TASK-008](#task-008-次期検索フロー-v2-の実装)
- 先行Plan: [EXEC-071](#exec-071-counterfactual-cloudflare最小live-runner)、[EXEC-073](#exec-073-outscraper商品画像から暫定ranking-v5への統合境界)
- 関連課題: [TD-011](ISSUES.md#td-011-画像取得推論の実環境検証)

### 目的

固定合成条件のCloudflare desired・counterfactual参照を生成した時点で必ず停止し、利用者が保存画像を確認して明示承認した同一processだけが、Outscraper 1 task、商品画像proxy、固定CLIP、暫定ranking v5へ進めるlive専用runnerを用意する。参照承認tokenと画像bodyをprocess外へ保存せず、承認前のOutscraper・Amazon通信を0件にする。

### 対象範囲

- 対象: 固定合成入力「白い陶器製マグカップ」、視覚条件「白い」1件、Cloudflare exact 2 calls・retry 0、参照2枚の新規0700/0600保存、15分以内の同一process人間確認、Outscraper日本語query 1件・task 1回・retry 0・最大24候補、商品画像GET最大24回、固定CLIP最大7 batch、EXEC-073統合backend、安全な段階別metadata、offline注入test、専用pytest opt-in
- 対象外: 本Plan実装中のlive通信、参照token・生response・商品本文・ASIN・商品URL・画像URL・embeddingの保存または出力、Cloudflare自動再生成、Outscraper自動再実行、Bonsai、実利用者入力、API、外部委託中frontend、deploy、commit、push

### 現在の状態

EXEC-071のlive runnerは参照PNGを保存するが、approval reviewとraw tokenをprocess外へ残さない。EXEC-073は正規の `ApprovedCounterfactualReferences` を受けた後のOutscraper完了結果からranking v5までを接続した。EXEC-074でCloudflare生成、参照保存、確認待ち、single-use consume、Outscraper以後を一つの長寿命process内で段階分離するrunnerと専用test nodeを実装した。2026-09-08の承認済みliveと後続診断で、Outscraper 1 taskから24商品を正規化した後、`m.media-amazon.com` が返した一意DNS結果9件を従来の最大8件契約が拒否し、Amazon HTTPへ到達しなかったことを確認した。全画像missingを `image_ready` とした集約不整合も再現した。resolverは生結果を最大64件まで全件構造検証し、重複排除後にtransport候補を最大8件へ制限するよう変更し、全画像missingは `image_unavailable` とするoffline修正を行った。修正後の別承認liveでは、Cloudflare 2 calls、Outscraper 1 task・poll 9回、24商品の正規化、Amazon画像24件の取得、固定CLIP 7 batches、暫定ranking v5、最終 `image_ready` まで357.95秒で完了した。

### 実行手順と進捗

- [x] 2026-09-08: 保存済みPNGだけを承認済み参照へ昇格できない理由と、同一processの二段階runnerが必要なことを確認した。
- [x] 2026-09-08: Cloudflare準備段階が参照2枚を保存してpending reviewを返し、Outscraper設定loaderと商品画像を呼ばないtestを追加した。
- [x] 2026-09-08: 明示確認がtrueで、保存画像が生成artifactと一致し、approvalが期限内・未使用の場合だけ参照をconsumeできるGREENを実装した。改ざん・期限切れではOutscraper設定loaderを0回にした。
- [x] 2026-09-08: 承認後段階をOutscraper single-use認可、actual transport、EXEC-073、production proxy、固定CLIPへ接続し、安全な集計だけを返すようにした。
- [x] 2026-09-08: 専用pytest opt-in、`SecretStr`設定、関連文書、focused・関連回帰・標準offline gateを完了した。
- [x] 2026-09-08: live条件と現行公式料金を提示し、二段階の明示承認後に専用nodeを1回実行した。Cloudflare 2 callsとOutscraper 1 taskの後、ranking段階で失敗し、retry 0のまま停止した。
- [x] 2026-09-08: 生商品データを残さず、商品正規化、typed ranking、画像入力検証、参照CLIP、候補準備、候補CLIP、候補score、較正、ranking v5、結果検証を区別できる安全な失敗substageと完了件数を実装・offline検証した。
- [x] 2026-09-08: 別承認の新規Outscraper 1 taskと単一DNS形状probeにより、運用hostの一意DNS結果9件を8件上限が拒否する下位原因を特定した。
- [x] 2026-09-08: DNS生結果の有界検証後に重複排除・transport候補制限を行い、全画像missingを `image_unavailable` とするoffline修正をTDDした。
- [x] 2026-09-08: 修正後live条件を提示し、二段階の明示承認後に新規taskとして1回実行した。24画像を全件取得し、固定CLIP 7 batchesと暫定ranking v5を `image_ready` で完了した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| TDD RED/GREEN | 新規二段階runnerのfocused pytest | 承認前0件、承認後だけOutscraperと画像評価へ進む | scaffold後の同一testは3 failed、実装後10 passed・1 live skipped |
| 関連回帰 | Cloudflare counterfactual、承認repository、Outscraper、proxy、CLIP、EXEC-073 | 外部通信なしで全件成功 | 196 passed・5 deselected |
| 標準gate | lock、Ruff、format、Markdown、`pytest -m 'not live_api'`、diff | 全て終了0 | lock 79、Ruff成功、239 files format済み、Markdown 16 files・1,400 links・1,824 headings、pytest 1,907 passed・13 skipped・7 deselected、diff成功 |
| live | 対話式専用test node | 別承認後だけ開始し、参照確認後の再承認時だけ1 taskへ進む | 利用者の二段階承認後に1回実行。Cloudflare 2 calls、Outscraper 1 task、retry 0の後、`failure_stage=ranking`、1 failed、358.22秒。再実行なし |
| live後offline診断 | 保存済み参照2枚の固定ONNX process隔離推論、kernel log確認 | 外部通信なしでCLIP基盤またはhost障害を分離する | 参照2枚は2 embeddings・2.997秒で成功。OOM・強制終了・segfaultなし。商品正規化以後の内訳は現行ログだけでは未特定 |
| 最大境界offline再現 | 入れ子24商品、24画像、実ONNX最大7 batches、較正、ranking v5 | liveと同じ件数・batch上限の一般的な統合不良を分離する | `image_ready`、received 24、image request 24、available 24、unknown 0、21.424秒で成功 |
| 安全なsubstage診断TDD | 画像評価、暫定backend、検索pipeline、live runnerの失敗伝搬 | closed stageと件数だけを保持し、生dataと例外文を破棄する | 初回focusedは3 failed、実装後24 passed・1 live skipped |
| 原因特定live診断 | 新規Outscraper 1 task・最大24画像段階probe、単一DNS形状probe | 商品画像失敗段階とDNS契約不一致を安全な件数だけで特定する | 24商品すべてDNS段階で停止しAmazon GET 0件。単一DNSは一意9件を返し旧8件上限で拒否された |
| DNS・全missing修正TDD | DNS重複・9件・raw上限・上限外項目検証、全画像取得失敗 | 全生結果を検証後に候補8件へ制限し、全missingを正常なoutcomeにする | 変更前3 failed、変更後focused 3 passed、関連241 passed・1 skipped |
| 修正後標準gate | lock、Ruff、format、Markdown、`pytest -m 'not live_api'`、diff | 全て終了0 | lock 79、Ruff成功、239 files format済み、Markdown 16 files・1,400 links・1,824 headings、pytest 1,911 passed・13 skipped・7 deselected、diff成功 |
| 修正後限定live | 対話式専用test node | 二段階承認後だけ1 taskを実行し、実商品画像から暫定rankingまで完了する | Cloudflare 2 calls、Outscraper 1 task・poll 9回、24候補、正規化24・reject 0、画像要求・取得各24、固定CLIP 7 batches、`image_ready`、1 passed・357.95秒、retry 0 |

### セキュリティ・データ・互換性

Cloudflare API tokenは準備段階、Outscraper API keyは人間確認後の実行段階でだけ読み、同じ設定objectへ同時保持しない。参照approval tokenと生成画像bodyはprocess memoryだけに保持し、SQLiteにはdomain-separated token digestとbindingだけを保存する。参照PNGは目視用の新規private directoryへ保存し、consume直前に生成artifactとのbyte digest・file identityを再検証する。承認前、拒否、期限切れ、改ざん、process終了時はOutscraperと商品画像を0件にする。

### 判断記録

| 日付 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-08 | Cloudflare生成とOutscraper実行を同一processの二段階にする | raw approval tokenと画像bodyを永続化せず、参照を見た後の明示確認をsingle-use receiptへ結ぶため | 永続暗号化sessionを別設計する場合だけprocess境界を見直す |
| 2026-09-08 | Outscraper credentialは参照承認後に初めて設定から読む | 承認前の誤送信と不要なcredential保持を避けるため | server-side secret brokerを導入した場合はread時点を再設計する |

### 発見事項

- 既存approval TTLは15分であり、目視確認と2回目の承認は生成完了後15分以内に必要である。
- `pytest -s` でも対話入力の実行環境差があるため、runner coreはprepareとapprove/runの2関数に分け、stdinはlive test wrapperだけで扱う。
- 最初のtest実行はmodule欠落によるcollection errorであり、有効なREDに数えなかった。最小scaffold後、準備段階が固定未実装例外になる同一testの3 failedをbehavioral REDとした。
- runnerの金額dimensionは実費0を意味せず、手動承認・自動再実行なしのtestに金額上限を設けないという利用者判断に従いcall数だけを強制する。実行直前の現行料金確認と見積り提示は引き続き必要である。
- 4画像の固定ONNX batchは3.323秒、参照1 batchと候補6 batchesに相当する連続7回は各2.761〜2.972秒・合計19.824秒で成功した。30秒timeoutと7 batch上限は一般的な失敗原因ではない。
- 入れ子24商品からranking v5までの実ONNX最大境界も成功したため、今回のlive失敗は実応答・実候補画像に固有の契約不一致または候補CLIP失敗である。ただし現行ログから両者を区別して断定しない。

### ロールバック

新規live runner・test・selector・live専用設定と対応文書だけを一単位で戻す。既存Cloudflare、Outscraper、approval repository、proxy、CLIP、EXEC-073、保存済み参照画像、外部状態は変更しない。

### 結果

offline runnerと安全なsubstage診断を実装した。liveは1回実行済みで、Cloudflare 2 callsとOutscraper 1 taskの後に旧 `failure_stage=ranking` で失敗した。retryは0で、再実行していない。保存済み参照、最大7 CLIP batches、入れ子24商品からranking v5までのoffline再現は成功した。後続実装はclosedなsubstageと到達済み件数だけを固定errorへ追加し、生例外と商品dataを保持しない。focused 24 passed・1 live skipped、関連166 passed・2 skipped・1 deselected、offline全体1,907 passed・13 skipped・7 deselectedである。これは過去の失敗原因を遡及確定しないため、原因特定には別条件提示・別承認後の新しいlive 1回が必要である。

## EXEC-073: Outscraper商品画像から暫定ranking v5への統合境界

### メタデータ

- 状態: 完了（offline統合）
- 作成日: 2026-09-08
- 最終更新: 2026-09-08
- 関連Task: [TASK-005](#task-005-ランキング品質評価の確立)、[TASK-008](#task-008-次期検索フロー-v2-の実装)
- 先行Plan: [EXEC-062](#exec-062-outscraper単一task実商品接続試験)、[EXEC-071](#exec-071-counterfactual-cloudflare最小live-runner)、[EXEC-072](#exec-072-実商品画像proxy固定clip最小live-runner)
- 関連課題: [TD-011](ISSUES.md#td-011-画像取得推論の実環境検証)

### 目的

Outscraperが返した実商品情報の `image_urls` を正本として、承認済み1 taskの完了結果を観測値だけの商品正規化、`typed-ranking-v4`、各商品の先頭画像だけを取得するproduction proxy、固定CLIP、label-free batch較正、暫定 `typed-ranking-v5-counterfactual-provisional` まで一続きに渡せるbackend境界を作る。

### 対象範囲

- 対象: 既存の認可・HTTP境界が返した `OutscraperProductExecution` と成功済み利用量予約、task 1回・retry 0という完了契約、完了結果の正規化、最大24商品、各商品の先頭画像だけ、画像GET最大24回、固定CLIP参照2枚と候補最大24枚、候補batch最大4、承認済みcounterfactual参照の必須化、安全な集計metadata、offline fixture test、関連文書
- 対象外: 本Plan実装中のlive通信、Cloudflare再生成、保存済みPNGからの承認receipt再構成、Bonsai、実利用者入力、商品本文・ASIN・URL・生provider応答・embeddingの保存または出力、legacy現行pipeline、API、外部委託中frontend、deploy、commit、push

### 現在の状態

Outscraperの単一task実通信と24候補の正規化、商品画像1枚のproduction proxy・固定CLIP、承認済みcounterfactual参照から複数商品の暫定ranking v5を作る各境界は個別に確認済みだった。本Planで成功済みOutscraper executionから画像付きrankingまでを結ぶ単一offline backend入口を追加した。EXEC-071の保存済みPNGには生request metadataと消費済み承認receiptを保存していないため、それだけをproduction承認済み参照へ昇格させない。

### 実行手順と進捗

- [x] 2026-09-08: 既存のOutscraper実行、商品正規化、typed-ranking-v4、承認済み参照、商品画像評価、暫定ranking v5の契約と上限を確認した。
- [x] 正常完了したOutscraper executionと正規の `ApprovedCounterfactualReferences` だけを受理し、最終rankingと安全な集計値を返すoffline backend testを先に追加してREDを確認した。
- [x] 最小の統合backendを実装し、fixtureでtask完了からv5までのGREEN、URL・本文を含まない集計、有効画像4件未満のfail-closedを確認した。
- [x] focused・関連回帰・標準offline gateを実行し、文書を現行動作へ同期した。
- [x] live実行を別工程へ分離した。参照生成後の人間確認を同一実行状態で維持する専用runnerを新しいPlanで設計し、送信先、固定合成query、task・poll・商品画像GET・CLIP上限、credential、費用見積り、保存範囲を再提示して新しい明示承認を得るまで実行しない。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| TDD RED/GREEN | 新規統合backendのfocused pytest | 未実装でRED、実装後は合成Outscraper完了結果からv5成功 | `ModuleNotFoundError`・exit 4のRED後、7 passed |
| 関連回帰 | Outscraper HTTP・正規化・typed ranking・画像評価・暫定backend tests | 外部通信なしで全件成功 | 144 passed |
| 標準gate | lock、Ruff、format、Markdown、`pytest -m 'not live_api'`、diff | 全て終了0 | lock 79 packages、Ruff成功、format 237 files、Markdown成功、1,890 passed・13 skipped・6 deselected、diff成功 |
| live | 専用test node | 別承認後だけ1 task・retry 0・有界poll・画像GET最大24・固定CLIPで集計結果を返す | 未実行。本Plan実装中は承認対象外 |

### セキュリティ・データ・互換性

Outscraper API keyは既存HTTP transportへ実行時だけ渡し、結果へ保持しない。backend結果は最終rankingに加えて件数・poll数・画像状態だけを集計し、生provider応答、provider request ID、商品名、ASIN、商品URL、画像URL、画像byte、embedding、生例外をログまたはartifactへ保存しない。画像は既存allowlist、DNS、pinned-IP HTTPS、10秒、8 MiB、redirect・retryなしを変更せず、1商品につき先頭URLだけを最大1回試す。参照画像は消費済みapproval receiptへ結ばれた `ApprovedCounterfactualReferences` だけを受理する。

### 判断記録

| 日付 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-08 | 商品画像URLはOutscraper正規化結果からだけ取得する | productionの商品情報取得元と画像取得元のprovenanceを一致させるため | provider変更時は別adapterと回帰testを必要とする |
| 2026-09-08 | 保存済み参照PNGだけから承認済み参照を再構成しない | Cloudflare request metadataと消費済みapproval receiptがなく、承認証跡を捏造することになるため | 明示的なimport承認schemaを別設計した場合だけ見直す |
| 2026-09-08 | live testはoffline実装完了後の別承認にする | task課金と最大24件の画像通信を実装検証から分離するため | live条件を提示し利用者が明示承認した場合に進める |

### 発見事項

- Outscraper task作成はexact 1回でも、非同期完了確認は初回応答後に最大50 pollを行い得る。live提示ではtask数とHTTP poll数を分ける。
- 固定CLIPは参照2枚を1 batch、候補最大24枚を4枚ずつ最大6 batchで処理するため、子process実行は最大7回である。

### ロールバック

新規統合backend・testと対応文書だけを一単位で戻す。既存Outscraper、正規化、proxy、CLIP、counterfactual承認、ranking profile、保存済み参照画像、外部状態は変更しない。

### 結果

完了。`provisional_search_pipeline.py` は成功済みOutscraper 1 task、日本語query 1件・最大24候補を再検証し、正規化、typed-ranking-v4、承認済み参照、各商品の先頭画像、production proxy、固定CLIP、batch較正、暫定ranking v5へ接続する。4件の固有画像は `image_ready`、同一重複画像だけの4件は有効候補4件未満の `image_unknown`、全商品画像の取得失敗は `image_unavailable`、失敗済みOutscraper予約は画像取得0件で固定拒否となる。安全な集計へprovider request ID、商品本文・識別子、商品・画像URL、画像byte、embedding、生例外を含めない。

focused 7件、関連144件、標準offline gate 1,890件が成功した。最終SHA-256はmodule `5cf1c1eab9c5af06780f2f07c5c23e6984326a0343a711aa75b43ea310929317`、test `d80bfc9af7ce37d1a99ce133b76043716f08d3c8b7f8ec429822b766a5926e32` である。実Outscraper、Amazon画像host、固定ONNX実推論、Cloudflare再生成、credential、課金、API、frontend、production E2Eは実行・確認していない。次は参照生成後の人間確認を同一実行状態で維持するlive専用runnerを別Planで設計する。

## EXEC-072: 実商品画像proxy・固定CLIP最小live runner

### メタデータ

- 状態: 完了（限定live成功）
- 作成日: 2026-09-08
- 最終更新: 2026-09-08
- 関連Task: [TASK-005](#task-005-ランキング品質評価の確立)、[TASK-008](#task-008-次期検索フロー-v2-の実装)
- 先行Plan: [EXEC-071](#exec-071-counterfactual-cloudflare最小live-runner)
- 関連課題: [TD-011](ISSUES.md#td-011-画像取得推論の実環境検証)

### 目的

運用候補host `m.media-amazon.com` の実商品画像1枚をproduction `ImageProxyService`で取得し、EXEC-071のdesired・counterfactual 2枚と同じ固定CLIP processへ渡せるかを、別承認の最小live試験で確認できる専用runnerを用意する。Outscraper再実行を同じ試験へ混ぜず、商品画像側のDNS・pinned IP・TLS・HTTP・decodeとlocal CLIPだけを切り分ける。

### 対象範囲

- 対象: exact許可host 1件、商品画像GET 1回、redirect・圧縮・retryなし、既存Cloudflare参照PNG 2枚の読戻し、固定CLIP 3画像1 batch、新規0600 PNG保存、URLを含まない固定診断、専用pytest opt-in、offline fixture test、関連文書
- 対象外: このPlan実装中のlive実行、商品画像URLの取得、Outscraper task、Bonsai、Cloudflare再生成、複数商品、batch較正、ranking合格判定、API、frontend、deploy、commit、push

### 現在の状態

Cloudflare desired・counterfactual最小setは実生成済みである。商品画像proxy、DNS process、pinned HTTPS transport、固定CLIP processは個別または合成fixtureで確認済みだが、運用候補hostから取得した実画像を同じprocessでencodeする結合は未確認である。過去のブラウザ候補では商品URLを保存しなかったため、live用URLは後続の別承認で取得し、値を表示せずtest専用環境設定へ渡す。

### 実行手順と進捗

- [x] Outscraperとの同時liveではなく、未確認の商品画像hostとCLIPだけを最小1 GETへ分離する。
- [x] 専用runnerのURL非露出、exact 1 GET、参照読戻し、CLIP実行、一括保存、固定失敗stageをoffline testへ追加してREDを確認する。
- [x] runner、専用selector、test用秘密設定、文書を実装し、focused・関連回帰・標準offline gateを通す。
- [x] URL取得方法、送信先、browser要求上限、credential、費用、保存範囲を別提示し、明示承認後に隔離browserでURL 1件だけを秘密設定へ保存する。
- [x] 商品画像GETの送信先、回数、timeout、byte上限、credential、費用、保存範囲を別提示し、明示承認後にproxy・CLIP live testを1回だけ実行する。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| TDD RED/GREEN | 新規runnerとselectorのfocused pytest | 未実装でRED、実装後にfixture成功 | ImportError・exit 2を確認後、12 passed・1 skipped |
| 関連回帰 | image proxy・DNS・HTTPS・CLIP process・counterfactual tests | 外部通信なしで全件成功 | 318 passed・4 skipped |
| 標準gate | lock、Ruff、format、Markdown、`pytest -m 'not live_api'`、diff | 全て終了0 | lock 79 packages、Ruff成功、format 236 files、Markdown成功、1,887 passed・13 skipped・6 deselected、diff成功 |
| URL取得 | 隔離Chromium・送信前interception | 1 navigation、外部要求100件以下、retry 0、URL 1件を秘密設定へ保存 | 1 navigation、送信100件、送信前遮断65件、retry 0、1件保存 |
| live | 専用test node | 別承認後だけ1 GET・retry 0・CLIP 3画像を確認 | 1 passed、1 GET、retry 0、CLIP 3画像、3.440秒、margin 0.570058732、PNG保存 |

### セキュリティ・データ・互換性

商品画像URLは `SecretStr` としてtest専用環境設定から読み、repr、JSON、pytest node ID、CLI引数、文書、artifactへ含めない。許可hostは `m.media-amazon.com` だけとし、DNSは最大8 address・5秒process deadline、HTTPSは検証済み先頭IPへ1回、元host名で証明書確認、10秒timeout、8 MiB、redirectなし、`Accept-Encoding: identity`を既存production契約のまま使う。成功時だけ正規化PNGを新規absolute pathへ0600で保存し、生response、header、URL、IP、embeddingを保存しない。

### 判断記録

| 日付 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-08 | Outscraper taskと商品画像GETを別live試験にする | Outscraperは既に単一task成功済みであり、同時実行すると失敗原因を分離できず追加課金も生じるため | full search E2Eは各最小境界の成功後に別Plan・別承認で扱う |
| 2026-09-08 | URLをCLI引数にせずtest専用環境設定から読む | process list、shell history、pytest出力への商品URL露出を避けるため | URLを取得する別工程でも値を表示・永続artifact化しない |

### ロールバック

新規runner・test・selector・test専用設定と対応文書だけを一単位で戻す。既存proxy、DNS、HTTPS、CLIP、Cloudflare参照PNG、外部状態は変更しない。

### 結果

完了。専用runner、三重opt-in、test専用SecretStr設定、参照読戻し、exact 1 GET、固定CLIP 3画像、成功後だけの0600保存、URLを含まない固定診断をoffline TDDで実装した。focusedは12 passed・1 skipped、関連回帰は318 passed・4 skipped、標準gateはlock 79 packages、Ruff・236 filesのformat、Markdown、1,887 passed・13 skipped・6 deselected、diffの全てに成功した。最終SHA-256はrunner `4851e57b934a0778e024e26601f101449056873f2dcb31f80f50877a6b1ff887`、test `a6761d71b9bb48552c023f8cc93b23250135602b1efafd3dde9706f9749af6ac` である。その後、別承認の隔離Chromiumで1 navigation、外部要求100件、送信前遮断65件、retry 0によりexact hostの商品画像URL 1件を `.env` へ値非表示で保存した。さらに、この試験がOutscraper本番統合ではなくproxy・CLIP限定smokeであることを利用者へ説明し、改めて明示承認を得て専用live testを1回だけ実行した。結果は1 passed、1 GET、retry 0、CLIP 3画像、3.440秒、normalized margin 0.570058732だった。候補は14,690 bytes・320×280・RGB・単一frame・metadataなしのPNGとして0600で保存し、白い無地のマグカップであることを目視した。Cloudflare、Outscraper、Bonsai、credential、provider課金は使っていない。この成功は実hostのproxy・local CLIP結合だけを示し、Outscraper由来画像の正規化、複数商品batch、ranking v5、本番E2Eを示さない。

## EXEC-071: counterfactual Cloudflare最小live runner

### メタデータ

- 状態: 完了（最小live成功）
- 作成日: 2026-09-07
- 最終更新: 2026-09-07
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)
- 先行Plan: [EXEC-070](#exec-070-cloudflare応答画像の安全な形式正規化)
- 関連課題: [TD-011](ISSUES.md#td-011-画像取得推論の実環境検証)

### 目的

暫定production正本のdesired 1枚と条件別counterfactualを作るexact `1 + N` Cloudflare経路について、最小の1条件・2 callsだけを別承認でlive確認できる専用runnerを用意する。既存の1-call基準画像成功を、counterfactualの参照画像入力・2-call利用量・一括artifact成功へ読み替えない。

### 対象範囲

- 対象: 固定合成条件1件、exact 2 calls、retry 0、専用pytest二重opt-in、safe failure metadata、新規directoryへの0600 PNG一括保存、offline fixture test、関連文書
- 対象外: このPlan実装中のlive実行、既存1-call出力の再利用、2条件以上、旧4方向set、CLIP評価、商品画像取得、API、frontend、deploy、commit、push

### 現在の状態

単一の固定合成基準画像は実Cloudflareで生成・正規化保存まで成功した。`execute_counterfactual_cloudflare_reference_set()` はdesiredの生成後、それを511×511の `input_image_0` として条件ごとのcounterfactualへ渡すexact `1 + N` production境界を持つ。専用runnerはこの経路だけを最小1条件で選択し、2枚が全て成功した場合だけ安全に保存する。

### 実行手順と進捗

- [x] 生成済み基準画像をローカルで目視し、固定条件と禁止要素を確認した。
- [x] 旧4方向ではなくcounterfactual `1 + N` が現行production正本であり、専用live runnerがないことを確認した。
- [x] 専用runnerの期待動作をoffline testへ追加し、未実装によるREDを確認する。
- [x] 最小runner、専用selector、safe output、固定診断を実装してfocused・関連回帰・標準offline gateを通す。
- [x] live実行前に公式料金とexact 2-call送信契約を再提示し、別の明示承認までlive実行しない境界を固定する。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| TDD RED/GREEN | 新規runnerとselectorのfocused pytest | 未実装でRED、最小実装後に全件成功 | `ModuleNotFoundError`・exit 2を確認後、9 passed・1 skipped |
| 関連回帰 | Cloudflare 1-call・counterfactual request・HTTP tests | 外部通信なしで全件成功 | 151 passed・2 skipped |
| 標準gate | lock、Ruff、format、Markdown、`pytest -m 'not live_api'`、diff | 全て終了0 | lock 79 packages、Ruff成功、format 234 files、Markdown成功、1,875 passed・13 skipped・5 deselected、diff成功 |
| live | 専用exact test node | 別承認後だけ2 calls・retry 0でdesiredとcounterfactualを保存 | 1 passed、2 calls、retry 0、18.388秒、PNG 2枚保存 |

### セキュリティ・データ・互換性

`.env` credentialは実行時だけ読み、repr・JSON・失敗出力へ含めない。実利用者入力、商品、URL、ASINを使わず、固定合成入力だけを送る。生要求、生応答、provider本文、Authorization headerを保存しない。成功時だけ新規absolute directoryへ正規化PNG 2枚を0600で保存し、既存pathを上書きしない。既存1-call runnerとproduction moduleの公開契約は変更しない。

### 判断記録

| 日付 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-07 | 次のlive候補を旧4方向ではなく最小counterfactual 2 callsとする | 暫定production正本がdesired＋条件別counterfactualへ移行済みであり、未確認境界を直接検証するため | 4方向互換経路の検証は別目的・別承認にする |
| 2026-09-07 | 既存の成功PNGを2 call目へ流用しない | production経路内でdesired生成、参照変換、counterfactual生成を一続きに確認するため | 接続費用は出力2 tilesと入力1 tileで別提示する |

### 発見事項

- 生成済みPNGは白色・無地・陶器・単一ハンドル・単品・中立背景・正面斜めを目視で満たし、文字、ロゴ、包装、余分な商品は見当たらなかった。この目視は単一画像の固定条件確認であり、画像品質の一般評価ではない。

### ロールバック

新規runner・test・selectorと対応文書だけを一単位で戻す。既存production counterfactual module、1-call runner、生成済みPNG、外部状態は変更しない。

### 結果

完了。専用runner、二重opt-in、exact 2-call予約、retry 0、安全な一括保存と固定診断をoffline TDDで実装した。最終SHA-256はrunner `7ac6c3c86038d5a2211ae4373cd6411b4bec782003ac69e52e243e56cba5fb5f`、test `abf33c53b2187b8b638e4c0178d654a014696f5b28cc3354aa0c7c41963196de`、selector `68038ce0b88f7a2e75dc643af16bacc3ff02d18a111ada3f85bfae7cf4923277`、pytest設定 `f403ec02d2709485ecdfa3ff42d4ce604707defe7c14e565d001c2796f196074` である。その後、条件と費用を再提示して利用者の明示承認を得た専用live testを1回だけ実行し、18.388秒、2 calls、retry 0で成功した。desiredは白い無地の陶器製マグ、counterfactualは同じ構図・形状・材質の青いマグであり、対象条件「白い」だけを反転する意図を定性的に満たした。これは固定合成条件1件の実Cloudflare結合成功であり、未知条件全般の精度、2条件以上、CLIP、商品検索、実請求額、production E2Eは確認していない。

## EXEC-064: 実ブラウザ候補とgpt-image独立参照のCLIP診断

### メタデータ

- 状態: 完了（適格なcategory-only 2条件で1 pass・1 fail）
- 作成日: 2026-09-07
- 最終更新: 2026-09-07
- 関連Task: [TASK-005](#task-005-ランキング品質評価の確立)、[TASK-008](#task-008-次期検索フロー-v2-の実装)
- 先行Plan: [EXEC-026](#exec-026-単一条件の複数画像clip-characterization)、[EXEC-030](#exec-030-画像ランキングの視覚的特徴限定)

### 目的と境界

2026-09-05の独立評価停止判断を利用者が撤回し、画像評価を再開した。初回は「白・円筒形・卓上加湿器」という未使用の視覚条件を固定し、ログイン情報を持たない隔離ChromiumでAmazon.co.jp検索結果1ページだけを表示する。候補商品画像はgpt-imageへ渡さず、gpt-imageで正面を生成して、その正面だけを参照に左・右・背面を生成する。候補と参照の独立性、目視labelのCLIP実行前固定、固定ONNXのproduction score経路を一続きで確認する。

外部実行は人間の明示承認後、ブラウザのトップレベル遷移1回、外部要求100件以下、保存12画像以下、gpt-image 4 calls、retry 0に限定した。商品詳細ページ、ログイン、既存Cookie、CAPTCHA回避、商品URL・ASIN・商品名・生DOM・Cookie・credentialの保存、Cloudflare・Outscraper・Bonsai、外部委託中フロントエンド、commit・pushは対象外とした。

### 結果

Chromium 151はトップレベル遷移1回、外部要求59件で上限へ達せず、DOM候補12件を確認した。ブラウザ応答本文から224px以上の単一frame画像として固定できた4枚をローカルPNGへ正規化した。追加navigation、商品詳細表示、retryは行っていない。候補01・04を3つの視覚条件に適合、候補02を非円筒、候補03を非白色として、画像scoreを見る前にmanifestへ固定した。

画像生成スキルの組み込みgpt-image経路を使い、repository credentialなしで正面・左・右・背面を各1回、合計4 callsで生成した。正規化前の生成物を候補作成へ使わず、4枚をproject-localの未追跡assetへコピーした。左・右参照のpHash距離は4で既定重複閾値5以内となり、対称な円筒形商品では4方向の情報量が不足することを確認した。

manifestのlabelと全8画像のSHA-256を固定してから、repository-localの固定ONNX、全体保持・モデル平均余白前処理、`spawn` process encoder、4-reference scoreを外部通信なしで実行した。候補01から04のimage scoreは順に0.956313209、0.865547134、0.807093262、0.844999933、正例中央値0.900656571、負例中央値0.836320198、pairwise AUC 0.75となった。候補04より候補02が高く、正例2・負例2で事前の最低3件ずつを満たさないため、これは取得・生成・推論のdevelopment E2E診断であり正式なacceptance assessmentではない。画像rankingは無効のままとする。

記録更新後、lock 79 packages、Ruff 200 files、現行Markdown 16件のlocal link 1,322件・anchor 921件、Markdown test 4件、offline pytest 1,735 passed・9 skipped・3 deselected、全8画像のmanifest SHA-256、`git diff --check` を確認した。これらの再検証では外部通信とprovider callを行っていない。

初回のlocal診断入口は標準入力から `spawn` できず、次の直接file実行はrepository rootをimport pathに持たず停止した。どちらも画像、label、外部状態を変更せず、外部通信・生成・browser navigationを再実行していない。同じ一時runnerをmoduleとして起動した実行だけが成功し、その後一時runnerを削除した。Chromium process、一時browser profile、誤作成した空directoryも残していない。

次は非対称な未使用商品条件について、ブラウザ表示から最低3正例・3負例を固定できる取得方法と、候補を入力しないテスト用gpt-image 4方向参照を別の明示承認後に実行する。本番の4方向参照生成は当初の予定どおりCloudflareを正本とし、既存のCloudflare境界を製品接続へ進める。gpt-imageは画像評価テストだけに使い、製品コードへ移行しない。

後続の明示承認では、非対称条件によるAmazon.co.jp検索結果へのトップレベル遷移を1回開始したが、Chromium performance logが外部要求をbatchで返し、100件到達時の停止前に111件を観測した。承認上限超過として候補0枚で失敗停止し、retry、gpt-image、CLIPを開始しなかった。URL、ASIN、商品名、生DOM、Cookie、credential、生provider応答は保存していない。外部通信なしのlocal模擬ページでは、CDP `Fetch.requestPaused` で送信前に各要求を判定し、上限5件だけをcontinue、残り17件をblockしてserver到達を5件へ固定できた。実Amazonへの再試行には、この方式と新しい明示承認を必要とする。

修正方式への別の明示承認後、同じ非対称条件でトップレベル遷移を1回実行した。CDP送信前interceptionは外部到達を100件へ固定し、追加64件を送信前に遮断した。DOM候補9件から7画像を保存したが、CLIP前の目視labelは正例0件・負例7件だった。赤い候補1件もハンドルが赤く、黒いハンドル条件を満たさなかった。最低3正例・3負例に達しないため正式評価には不適格として停止し、retry、gpt-image、CLIPを開始しなかった。次回は検索語を評価条件と同一にせず、同一商品カテゴリ内で正負を集めるcategory-only取得設計を事前固定する。

category-only設計への別の明示承認後、検索語を「電気ケトル」、評価条件を「黒い本体の電気ケトル」へ分離してトップレベル遷移を1回実行した。CDP送信前interceptionは外部到達を100件へ固定し、追加70件を送信前に遮断した。DOM候補12件のうち10画像を保存し、scoreを見る前に候補06〜09を正例4件、候補01〜05・10を非黒色の負例6件としてmanifestへ固定した。商品URL、ASIN、商品名、生DOM、Cookie、credential、生provider応答は保存していない。

最低構成を満たしたため、候補画像を入力せず、組み込みgpt-imageで無印の黒色電気ケトル正面を1 call、正面だけを参照した左・右・背面を各1 call、計4 calls・retry 0で生成した。固定ONNXのprocess隔離経路では正例中央値0.924253657、負例中央値0.870871561、pairwise AUC 1.0となった。4参照のpHash最小距離は12で重複閾値5を超え、AUC 0.80以上、中央値分離、参照非重複という事前基準を全て満たしたため、この単一条件のassessmentは `pass` とする。artifactは `tests/img/image-holdout-004/` に保存した。

この結果は、category-only取得と別固定条件が最低構成を作り、固定CLIPがこの1条件を分離できたことを示す。1カテゴリ・1条件だけであり、複数カテゴリ、exact条件、uncertainty、typed ranking全体、製品接続、Windows nativeを証明しない。画像rankingは無効のままとし、次回はこの条件もdevelopment dataから除外して別カテゴリ・別条件で再現性を評価する。本番の画像生成はCloudflare、gpt-imageは評価テスト専用とする。

再現性確認への明示承認後、未使用の検索語「オフィスチェア」と評価条件「黒いメッシュ背もたれ・ヘッドレスト付き」を分離した。CDP送信前interceptionは外部到達100件、追加70件を送信前遮断し、トップレベル遷移1回、retry 0、保存12件だった。score確認前に正例4・負例6・曖昧2へ固定し、候補を入力しないテスト用gpt-imageで正面・左・右・背面を計4 calls、retry 0で生成した。固定ONNXでは正例中央値0.900518905、負例中央値0.921669262、pairwise AUC 0.291666667、参照pHash最小距離6となった。最低構成と参照非重複は満たしたが、AUC 0.80以上と中央値分離に失敗したため `tests/img/image-holdout-005/` を `fail` とした。再取得・再生成は行わず、本番Cloudflareも呼んでいない。

適格な2条件で結果は1 pass・1 failとなり、カテゴリ横断の再現性を確認できない。画像rankingは無効のままとし、本番の生成providerはCloudflare、gpt-imageは画像評価テスト専用とする。

固定済み `image-holdout-005` だけを使う外部通信なしの改善検証では、中央正方形cropはAUC 0.375、参照比率2:3の中央cropは0.458333333、椅子上部60%・75%のcropはいずれも0.375で、全て正例中央値が負例中央値を下回った。同一datasetから1負例をfold外参照にするcontrastive marginはAUC 0.25〜0.55、ヘッドレストなしと非黒色の2負例をfold外参照にする8分割は0.125〜0.5625、leave-one-out label centroidは0.208333333だった。いずれも固定基準0.80と中央値分離を満たさず、同一datasetのlabelを使う方式は独立holdoutでもないため採用しない。結果は `tests/img/image-holdout-005/improvement-result.json` に固定し、production codeと現行assessmentを変更していない。


## EXEC-063: Bonsai自由語と商品名のsource grounding

### メタデータ

- 状態: 完了
- 作成日: 2026-09-07
- 最終更新: 2026-09-07
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)
- 関連要件: [FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)
- 先行Plan: [EXEC-061](#exec-061-bonsai-bounded-compact-schema)、[EXEC-062](#exec-062-outscraper単一task実商品接続試験)

### 目的と現在地

利用者承認済みの一続きE2E第1段階として、固定合成入力をrequest v8のlocalhost Bonsaiへ1回だけ送った。
HTTP、compact response、完全intent、typed proposal、query planの構文契約は通過したが、入力にない商品名を採用し、
明示した桁区切りJPY範囲と未知色を欠落させたまま `ready` となった。生成queryを確認した時点で停止し、
Outscraper、Cloudflare、credential、課金、retryは使っていない。一時継続stateはJSON境界を再検証して削除し、
server process停止とport非listenを確認した。

着手時の `_ground_source_conditions()` はtyped conditionの値、明示JPY、明示除外だけを入力へ照合していた。
商品名、brand、model number、自由語termはprovider値をそのまま残し、JPY正規表現は桁区切りcommaを受理しない。
この境界差により、strict JSON成功が意味的なsource grounding成功として扱われている。

### 対象範囲

- `src/search_v2/bonsai_adapter.py` で商品名、brand、model number、自由語termを同じSudachiPy
  `SplitMode.C` source spanまたはASCII語境界へ照合する。
- 入力に根拠がないprovider値を検索queryへ渡さない。商品名fieldだけを必須条件にせず、入力に根拠のある
  商品名・brand・model number・required term・preferred termが全て残らない場合だけ固定blocking ambiguityへ戻す。
- commaを3桁区切りとして検証したJPY表記を、既存の有界な上限・下限・範囲復元へ追加する。
- SudachiPyが連続する接頭辞と内容語へ分けた未知複合語を、queryとrankingの共通tokenizerで1 tokenへ結合する。
- 実modelで観測した意味差分を生responseなしの合成fixtureでREDに固定し、同じtest内容をGREENにする。
- 現行文書を実装結果と検証境界へ同期する。

### 対象外

- 新しいBonsai、Outscraper、Cloudflare、OpenAIの呼出、credential利用、課金、自動retry
- LLM prompt、request v8、生成schema、HTTP transport、response上限、server設定の変更
- ranking weight、商品正規化、画像、cache、履歴、job、legacy pipeline、API、UIの変更
- 外部委託中フロントエンドの確認、起動、テスト、接続
- providerが省略した全条件を自然文から完全復元できるという保証

### 受入条件

1. 入力に存在しない商品名を除去し、他の根拠ある肯定検索語もなければblocking確認へ戻す。
2. 日本語・英語の自由語とscalarは、入力中の連続した完全morpheme spanまたはASCII語境界だけを保持する。
3. 少なくとも1つの肯定検索語を根拠付けられる既存の日本語・英語fixtureは、商品名fieldの有無にかかわらず
   検索可能性を維持する。
4. `5,000円以上10,000円以下` を5,000〜10,000円の明示範囲として復元し、不正なcomma配置は価格として扱わない。
5. 実model由来の合成fixtureは無根拠の商品名をqueryへ含めず、根拠ある必須語から `IntentReview` へ到達する。
6. `超低背` のような連続接頭辞を持つ未知複合語は、接頭辞を失わない同一tokenとしてqueryとrankingへ渡す。
7. focused test、関連回帰、標準offline gate、Markdown、Python 3.10構文、`git diff --check` が成功する。

### 実行手順と進捗

- [x] 2026-09-07: 承認済みBonsai 1 callを44.762秒で完了し、意味不一致を確認してOutscraper前に手動停止した。
- [x] 2026-09-07: raw responseを保存せず、厳格intent、利用量state、server停止、一時state削除を確認した。
- [x] 2026-09-07: 現行adapter、SudachiPy span、価格parse、既存fixtureの責務を確認した。
- [x] 2026-09-07: 最小RED testで無根拠商品名、自由語、comma付きJPY範囲を固定した。
  focused 4件は3 failed / 1 passedで、失敗は期待した未実装理由に限定された。test SHA-256は
  `ee0df0e4ea7aca852623a8684f202f4e5efee7b89e830e7d1e21b484aed0da26`。
- [x] 2026-09-07: adapterのsource groundingを最小変更し、同じtestを4 passedへした。
- [x] 2026-09-07: 関連222件、全 `search_v2` 963件、標準offline gateを完了した。
- [x] 2026-09-07: 文書を結果へ同期し、追加live callを新しい明示承認の対象として分離した。
- [x] 2026-09-07: 新しい明示承認後、同じ固定入力をlocalhost Bonsaiへ1 call・retry 0で再確認し、
  43.282秒で `source_product_ungrounded` のblockingへ到達した。Outscraperは呼ばなかった。
- [x] 2026-09-07: 再確認結果から商品名field必須の過剰制約をRED 2 failed / 1 passedで固定し、
  根拠ある肯定検索語の有無による判定へ修正した。同じ3件をGREENにした。
- [x] 2026-09-07: 関連211件、全 `search_v2` 964件、標準offline gate 1,734件を完了した。
- [x] 2026-09-07: 別の明示承認後、同じ固定入力をlocalhost Bonsaiへ1 call・retry 0で再確認した。
  41.148秒で `ready` となったが、queryの接頭辞欠落を確認してOutscraper前で停止した。
- [x] 2026-09-07: 接頭辞欠落をRED 3 failedで固定し、SudachiPyの連続接頭辞を後続内容語へ結合した。
  同じ3件をGREENにし、旧queryを持つ一時stateを削除した。
- [x] 2026-09-07: 関連177件、全 `search_v2` 965件、標準offline gate 1,735件を完了した。
- [x] 2026-09-07: 新しい明示承認後、接頭辞修正済みの同じ固定入力をlocalhost Bonsaiへ
  1 call・retry 0で再確認し、60.366秒で期待queryを持つ `IntentReview` へ到達した。
- [x] 2026-09-07: 別の明示承認後、保持したqueryでOutscraper taskを1回だけ作成し、
  24候補の正規化・typed rankingまで完了した。自動retryは0だった。

### セキュリティ、互換性、判断

providerが生成した未根拠値を黙って検索へ昇格させないことを優先する。商品名fieldの有無から商品種別を推測せず、
入力に根拠のある肯定検索語が残るかを既存query構成要素単位で判定する。価格・除外語しか残らない場合は既存の
fail-closedなquery-less blocking契約を再利用する。公開request、response schema、保存schemaを変えない。
自由語のsource span照合は語彙listを追加せず、未知語にも同じ規則を適用する。
共通tokenizerはSudachiPyの品詞だけで連続接頭辞を検出し、個別語彙を列挙しない。接頭辞は後続内容語が
存在する場合だけ結合し、孤立接頭辞、助詞、句読点は検索tokenへ昇格させない。
検索可能性が下がる回帰が見つかった場合は、無根拠値を再び許すのではなく、具体的なsource span規則をREDで固定して見直す。

### 発見事項と逸脱

- 実行前には既存source groundingが今回の固定入力を安全に扱えると見込んだが、商品名と自由語は照合対象外だった。
- 継続stateをPython辞書からstrict modelへ復元する確認は日時とtupleの型で失敗した。JSON境界からの復元では成功した。
  外部呼出や保存内容には影響せず、stateは削除済みである。

### ロールバック

EXEC-063で追加するadapter分岐、focused test、同Planに対応する現行文書の記述だけを取り除けば、
EXEC-062完了時点へ戻る。request v8、既存SudachiPy tokenizer、provider credential、外部データは変更しない。

### 結果

完了。商品名、brand、model number、自由語termは語彙listではなく、SudachiPyの連続する完全形態素spanまたは
ASCII語境界へ一致する値だけを保持する。商品名fieldが空でも、入力に根拠のあるbrand、model number、required term、
preferred termが残ればquery planを作れる。肯定検索語が全てなく、価格・除外語しか残らない場合は
`source_product_ungrounded` のblocking確認へ戻り、Outscraperへ進まない。URLは削除で隠さず既存の固定searchability
errorへ渡す。正しい3桁comma付きJPYは上下限・範囲へ復元し、不正commaへ部分一致しない。

初回REDはtest SHA-256 `ee0df0e4ea7aca852623a8684f202f4e5efee7b89e830e7d1e21b484aed0da26` で
3 failed / 1 passed、GREENはfocused 4 passedだった。実model再確認後の追加REDはcompact test SHA-256
`351e44ecf17cc133d9258ebbf41a45f5d4cbca4296c9a18210bc577ca21d0fb6`、orchestrator test SHA-256
`ee6ed3ef21ca8f55400853ede1fcb98bb8aec28475a27441959d7fde6ed075cf` で2 failed / 1 passed、同じ3件を
GREENにした。最終adapter SHA-256は `f78b85c325e536aeb9dc69c4b35aca8207b048d94cf537ecc2044bb4f517ed7b`。
関連211 passed、全 `search_v2` 964 passed / 9 skipped、標準gateはlock 79 packages、Ruff 200 files、
pytest 1,734 passed / 9 skipped / 3 live deselectedに成功した。

初期source-grounding修正後の実Bonsaiは1 call・retry 0で再確認した。43.282秒、906 prompt tokens、268 completion tokens、
response 1,776 bytes、`finish_reason=stop` でstrict intentへ到達し、5,000〜10,000円の価格範囲、必須語3件、
除外語1件を保持した。入力に根拠のある商品名がなかったため、商品名をqueryへ昇格させず
`source_product_ungrounded` のblocking確認へ戻した。typed proposalもblockingであり、query plan、一時継続state、
Outscraper callは作らなかった。server停止、port非listenを確認した。

これは無根拠の商品名を外部検索へ渡さない境界の実model確認である。同時に、商品名field必須の初期修正が
入力中の根拠ある必須語まで利用不能にすることを検出した。最終offline修正では同じ応答相当fixtureが無根拠の
「マウス」を除去し、根拠ある「キーボード」を含む日本語queryとready proposalを作る。価格・除外語しかないfixtureは
引き続きblockingである。providerが省略した全条件の復元、最終修正後の実model、実商品候補、ranking品質、
production E2Eを合格扱いにしない。一続きの実商品E2Eを続ける場合は、同じ固定入力をBonsai段階から1回だけ再実行し、
生成queryを確認した後、Outscraper送信前に別の明示承認を得る。

その明示承認による次のBonsai 1 callは41.148秒、906 prompt tokens、268 completion tokens、response 1,775 bytes、
`finish_reason=stop` で完了した。価格範囲、必須語3件、除外語1件を保持し、無根拠商品名を除去したまま
typed proposalは `ready` になった。ただし生成queryが `背 ワイヤレス キーボード` となり、`超低背` の接頭辞を
失ったためOutscraper前で停止した。一時stateはJSON境界では有効だったが、この旧queryを後続へ渡さず削除した。
post-call harnessは一度Python辞書からstrict modelへ復元して日時・tuple型で失敗したが、追加model callなしで
JSON境界から再検証した。server停止、port非listen、自動retry 0を確認した。

接頭辞欠落のREDはtokenizer、compact adapter、orchestratorの3件が全て期待理由で失敗し、test SHA-256は順に
`ca9db4b08f87d4061da0cfdbb34e83bde1663ce963192681121722587abd2248`、
`b70e335cb4103e9c671491024bff179cf762569dd2e163d6b372642e46b75a6e`、
`7a4ad314ed66b69102015c338b436c812a95e2b5819211818602582eca4163b8` だった。SudachiPyの連続接頭辞を
後続内容語へ結合した最終tokenizer SHA-256は `5a5d9f20b4d86e560c7a427def5b39ecf9a434ca287cbca4f05e0890216aaddb`。
同じ3件はGREEN、関連177 passed、全 `search_v2` 965 passed / 9 skipped、標準offline gateはlock 79 packages、
Ruff 200 files、pytest 1,735 passed / 9 skipped / 3 live deselectedだった。同じ実測応答相当fixtureは
`超低背 ワイヤレス キーボード` を作る。接頭辞修正後の実modelとOutscraperは未実行である。

接頭辞修正後の承認済み最終確認は60.366秒、906 prompt tokens、268 completion tokens、response 1,777 bytes、
`finish_reason=stop` で完了した。typed proposalは `ready`、typed requirementとissueは0件、blocking ambiguityも0件。
無根拠の商品名を除去したまま、5,000〜10,000円、必須語3件、除外語1件と、query
`超低背 ワイヤレス キーボード` を保持した。Bonsai 1 call・自動retry 0であり、server停止とport非listenを確認した。
継続stateはJSON境界でIntentReview、policy、usage ledgerを再検証し、directory 0700・file 0600で保持している。
このBonsai段階ではOutscraper、Cloudflare、商品取得、ranking、credential、課金を開始していない。

別の明示承認後、同stateから画像なしの最終確認と単一使用approvalを作り、query
`超低背 ワイヤレス キーボード`、`amazon.co.jp`、日本語、郵便番号 `100-0001`、1 queryあたり24件、
`async=true` のOutscraper requestを実行した。task作成1回、自動retry 0、同一taskのpoll 8回で、221.458秒後に
24候補を受信した。24件すべてが観測値だけの正規化と `typed-ranking-v4` を通過し、reject 0件、ranked 24件、
利用量予約 `succeeded`、approval consumption 1件で完了した。生応答、商品本文、商品URL、ASIN、provider request ID、
API keyは出力・保存せず、消費済み一時stateを削除した。実請求額はproviderの課金記録を取得していないため未確認である。

この結果は、固定合成入力1件について、local Bonsai、承認境界、実Outscraper、正規化、typed rankingが段階的に
接続したbackend development E2Eである。個々の商品が条件を満たすこと、順位品質、未知入力全般、画像ranking、
browser、委託フロントエンド、production SLOを証明しない。


## EXEC-062: Outscraper単一task実商品接続試験

### メタデータ

- 状態: 完了
- 作成日: 2026-09-06
- 最終更新: 2026-09-06
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)
- 関連要件: [FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)
- 先行Plan: [EXEC-061](#exec-061-bonsai-bounded-compact-schema)

### 目的と境界

次期Outscraperのactual Requests transport、非同期task、同一task polling、完了応答検証、観測値だけの商品正規化が実サービス応答でつながるかを、明示承認済みの固定合成query 1件で確認する。task作成は1回、自動retryは0、候補上限は24、各HTTP timeoutは30秒、応答上限は8 MiB、pollは30秒間隔・最大50回とする。APIキーは設定から読み `X-API-KEY` だけへ渡し、生応答、商品本文、商品URL、ASIN、provider request ID、APIキーを出力・保存しない。

この試験はBonsai、Cloudflare、ranking、履歴、現行pipeline、API、UI、外部委託中フロントエンドを接続しない。人間承認済みかつ自動再実行しない試験として費用上限は設けず、task作成回数だけを1回へ固定する。実請求額はproviderの課金記録を取得していないため未確認とする。

### 実行結果

task作成1回・自動retry 0で開始し、同一taskを9回pollした。251.795秒で候補24件を受信し、v2応答契約を通過した。観測値だけの正規化は24件成功・reject 0件で、利用量予約は `succeeded` となった。生の商品データと内部識別子は出力・保存していない。

### 検証と結論

実行前にOutscraper request・HTTPのoffline回帰70件を確認した。実行後はlock 79 packages、Ruff check・format 200 files、Markdown 16 files・1,315 links・914 anchors・1,678 headings・203 fence pairs、pytest 1,728 passed・9 skipped・3 live deselected、`git diff --check`に成功した。この単一試験から確認できるのは、承認済み1 query・24件という条件での実Outscraper接続、非同期完了、現行response contract、現行normalizerとの互換性である。未知query全般、0件・失敗応答のlive挙動、属性充足率、条件一致、順位品質、Bonsaiからの一続きのE2E、production SLOは証明しない。

## EXEC-061: Bonsai bounded compact schema

### メタデータ

- 状態: 完了
- 作成日: 2026-09-06
- 最終更新: 2026-09-06
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)
- 関連要件: [FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)
- 先行Plan: [EXEC-060](#exec-060-bonsai-196-token目標のcompact-wire応答)

### 目的

request v7の承認済みlocalhost診断は、代表fixtureが126 tokensでも365.12秒で応答を完了しなかった。
196をhard capにせず、provider wireの自由度を文字列長、配列要素数、許可field profileで制限する。
省略値は従来どおり完全19-field application契約へ復元し、上限に収まらない入力を黙って欠落・切断せず、
blocking ambiguityとして利用者確認へ戻せるrequest v8を実装する。

### 現在の状態と発見事項

- v7はrootに19 field、各term list最大20、typed condition最大64、set値最大32、通常文字列最大100、
  商品名最大200、ambiguity message最大300を許す。代表fixtureの短さは任意のmodel出力を拘束しない。
- 現行llama.cppのJSON-schema converterは `maxLength` と `maxItems` をgrammarへ反映するが、
  `maxProperties` を処理しない。rootへ数値だけを加えても実生成のfield数制限にはならない。
- field数は、検索可能応答と確認待ち応答で異なる `properties` と `additionalProperties=false` を持つ
  固定branchを作り、converterが生成するobject grammar自体で制限する。

### 対象範囲

- 検索可能branchは `product_name_ja`、`product_name_en`、日英のrequired・preferred・negative terms、
  `brand`、`model_number`、`price`、`typed_conditions` の最大12 fieldだけを許す。
- 確認待ちbranchは全要素がblockingの `ambiguities` 1 fieldだけを許す。
- 商品名・brand・model numberは48文字、termは32文字、ambiguity messageは96文字までとする。
- 各term listとtyped conditionは最大4件、enum・text set値は最大4件、ambiguityは最大2件とする。
- categoryは商品名へ、colorとfeaturesはtermsまたはtyped conditionへ集約する。安全に表現できない、
  または上限を超える場合は省略・切断せずblocking ambiguityを返すようpromptへ明記する。
- compact wireだけを狭め、復元後の `SearchIntentDraft`、normalized intent、query planner、typed proposal、
  cache、履歴、DB schemaは変更しない。
- request schemaとdigest domainを8.0へ更新し、v7 descriptorを暗黙に受理しない。

### 対象外

- `max_tokens=196` その他の生成token hard cap、application HTTP timeout、response 1 MiB上限の変更
- 実Bonsai、localhost再測定、Core Ultra、Vulkan、OpenVINO、NPUでの実行
- legacy検索、Cloudflare、Outscraper、API、browser、外部委託中フロントエンドとの接続
- 完全19-field application schema、ranking、cache・履歴・DB migration、commit、push

### 受入条件

1. 文字列長と配列要素数がcompact Pydantic modelと生成schemaの両方で同じ値に制限される。
2. 検索可能branchのgrammarは最大12種類の許可field、確認待ちbranchは `ambiguities` だけを生成できる。
3. category、color、features、unknown field、profile混在、上限超過をadapterが本文非保持で拒否する。
4. 上限内の代表fixtureは完全19-fieldへ決定的に復元でき、query planとtyped proposalを構築できる。
5. promptは切断や条件欠落を指示せず、表現不能・上限超過をblocking確認へ写す。
6. request v8はprompt、compact生成schema、完全schema、bodyのdigestをbindし、生成token上限を持たない。
7. llama.cpp converterがschemaを終了0で処理し、生成grammarに除外fieldが現れず、各反復上限が現れる。
8. focused・関連回帰、標準offline gate、Python 3.10構文、Markdown、`git diff --check` が成功する。

### 実行手順と進捗

- [x] 2026-09-06: v7 schema、adapter、prompt、実行停止時の診断とconverterの対応keywordを確認した。
- [x] 2026-09-06: bounded compact model、固定field branch、request v8、prompt規則をRED testで固定した。
- [x] 2026-09-06: 最小実装でfocused testをGREENにした。
- [x] 2026-09-06: llama.cpp converterとtokenizerでschema・代表fixtureをoffline確認した。
- [x] 2026-09-06: Bonsai関連回帰と標準offline gateを実行した。
- [x] 2026-09-06: 現行文書を実装・検証結果へ同期した。
- [x] 2026-09-06: 後続の明示承認後、request v8の同一固定入力2 callsをlocalhostで完走した。
- [x] 2026-09-06: 別の承認済み固定入力1 callで意味欠落と不正typed conditionを確認し、追加callなしでpromptとschemaをoffline修正した。
- [x] 2026-09-06: 修正後の承認済み固定入力1 callを実行し、strict intent後に残る価格・除外条件欠落と無根拠typed conditionを確認した。Outscraper前のblockingで停止した。
- [x] 2026-09-06: requestを増やさず、typed candidateの入力根拠検査、明示JPY上下限、未知語を含む除外対象の決定的復元をoffline TDDした。
- [x] 2026-09-06: 日本語の根拠照合と否定対象抽出をSudachiPy `SplitMode.C` の形態素・品詞・正規化済みsource offsetへ置き換え、未知複合語、格助詞、二重否定の回帰をoffline TDDした。

### 検証

| 対象 | 期待結果 | 実結果 |
|---|---|---|
| bounded schema RED | 新しい文字列・配列・field profile・request v8の期待だけが失敗する | 7 failed / 5 passed。field profile、上限超過拒否、価格既定値省略、request v8の7期待だけが未実装理由で失敗。test SHA-256 `4b2b703c2e86e10ec5f32109f3a8f16bf4ba01cab59abf30416c4637bb55c61a` |
| focused GREEN | 上限内成功、上限超過・profile混在の本文非保持拒否 | 17 passed。test SHA-256 `9b192c605282acd375728e46811675d90ebe28fd1a31833c8d2e1f8bebfdd14c` |
| llama.cpp converter | schema変換成功、固定field branchと有限反復を確認 | 終了0。schema 9,820 bytesから48,260-byte・214-rule grammarを生成。商品名 `char{1,48}`、term `char{1,32}`、最大4件 `{0,3}`、ambiguity最大2件・message `char{1,96}` を確認し、除外root fieldは不在 |
| tokenizer | bounded代表fixtureのtoken数を測定するが、任意出力の196保証とは扱わない | bounded compact 104 tokens、完全19-field 181 tokens。77 tokens・42.5%削減 |
| offline gate | lock、Ruff、Markdown、pytest、Python 3.10構文、差分検査が成功 | lock 79 packages、Ruff 200 files、次期検索940 passed・9 skipped、全体1,710 passed・9 skipped・3 deselected、Python 3.10 AST 200 files、Markdown 16 files・1,306 links・905 anchors・1,672 headings・203 fence pairs、Markdown test 4 passed、zero-width scan 270 files、`git diff --check` 成功 |
| localhost v8診断 | 後続の明示承認後だけ、同一固定入力2 callsのwall・prompt・生成時間を本文非保持で測定 | 1 passed in 72.49s。2 callsとも1190 prompt・254 completion tokens・`finish_reason=stop`・strict intent成功。coldはprompt 35,594.167 ms・生成17,480.571 ms・wall 53,148 ms。warmは1189 cached / 1190 prompt、prompt 69.675 ms・生成17,529.892 ms・wall 17,625 ms。server停止・port非listenを確認 |
| 1-call意味回帰とoffline修正 | 別の固定入力で条件保持とtyped proposalを確認し、応答量を増やさず欠陥を修正 | 実modelは50.628秒・82 completion tokensでstrict intentまで成功したが、価格・色・除外条件を欠落し、不正typed conditionでblocking。追加callなしで語彙非依存の原子的条件分解と未知語原文保持を要求する3,600-byte promptへ短縮し、10,950-byte schemaを6 value-type branchへ分離。同一入力body 14,859 bytes、203-byte ready fixture、promptにない日英3組の語彙回帰、54,537-byte grammar変換に成功。修正後の実modelは未測定 |
| 修正後の承認済み1-call回帰 | 同じ固定合成入力でprompt・schema修正後の応答時間と意味条件を確認する | localhostへexact 1 call、retry 0。53.595秒、887 prompt・248 completion tokens、response 1,670 bytes、`finish_reason=stop`、strict intent成功。価格・除外条件を欠落し、入力にないtyped conditionを含めたためproposalはblocking。query plan・Outscraper callなし。server停止・port非listenを確認 | 接続・形式・約54秒の応答完了は確認できたが、promptだけでは意味保持を保証できない。後続provider前の停止境界は機能した |
| source-grounding adapterのRED・GREEN | 語彙を列挙せず、取得済み応答で明示条件を保持し無根拠条件を実行へ昇格させない | REDは価格未復元で1 failed。実装後は取得済み応答相当fixtureが価格上限10,000円、除外対象、白、ワイヤレスを保持し、無根拠style・orientationを除去してproposal・query planともready。明示JPY min・max・range、未知英語除外、単一漢字aliasの未知語内誤一致も固定。関連119 passed | request body・prompt・生成schemaを変えず、追加モデルcallと語彙whitelistなしで今回の欠落を境界処理できる。adapter修正後の実model成功や未知入力全般の分類精度は示さない |
| source-grounding後の標準offline gate | repository全体の静的・fixture・mock回帰と文書を確認する | lock 79 packages、Ruff 200 files、Markdown 16 files・1,306 links・905 anchors・1,672 headings・203 fence pairs、pytest 1,723 passed・9 skipped・3 live deselected、Python 3.10 AST 193 files、`git diff --check`成功 | 外部通信・model推論なしで変更が既存offline境界と共存する。adapter修正後の実model・実商品検索は示さない |
| SudachiPy span抽出のRED・GREEN | 手書きの日本語境界を既存SudachiPy解析へ置き換え、未知語と否定範囲を正規化済みsource spanで扱う | 最初のREDは格助詞より前の語を巻き込み1 failed・1 passed。実装後に二重否定のREDも1 failedで再現し、修正後はtokenizer・compact adapter 45 passed、関連146 passed。tokenizer SHA-256 `f5ba7ff5ab7910f1146096031cffbc072e28905d9bf947b390b1be3966fa17b5`、adapter `992f4939a0879bfe96fae6b0e8f2b7cdf7bbc7f7cc5bbba0d13178ce2782648f` | trusted aliasは連続する完全形態素spanだけへ一致し、未知複合語内の部分一致、格助詞より前の巻き込み、二重否定を拒否する。公開request・prompt・schemaは変更しない |
| SudachiPy span抽出後の標準offline gate | repository全体の静的・fixture・mock回帰を確認する | lock 79 packages、Ruff成功・200 files formatted、pytest 1,728 passed・9 skipped・3 live deselected、Markdown 16 files・1,306 links・905 anchors・1,672 headings・203 fence pairs、`git diff --check`成功 | 外部通信・model推論なしで形態素span方式が既存offline境界と共存する。adapter修正後の実model・実商品検索は示さない |
| local warm処理時間 | requestの応答時間へ影響するローカル後処理量を限定測定する | 初回形態素解析46.300 ms、warm形態素解析10,000回平均0.032384 ms、warm adapter全体1,000回平均2.043352 ms | 同一host・同一processの限定測定では約53秒の既存model応答に対して小さい。Core Ultra、production、任意長入力へ外挿しない |
| 承認済み1-call localhost再確認 | 固定合成入力1件で実Bonsai後のSudachiPy source groundingを確認する | localhostへ1 call、retry 0でstrict intent、typed proposal構築、query plan作成まで完了したが、集計コードが存在しないledger methodを呼んで出力前に失敗。server停止・port非listen。追加call、Outscraper、Cloudflare、credential、外部network、課金なし | strict受理とquery plan到達は確認できたが、実応答の意味条件・時間・token数は確定できない。自動再実行せず、集計修正のoffline確認と新しい明示承認を次回実行の条件にする |
| 別承認による1-call localhost再実行 | 集計を `snapshot().reservations` へ修正し、同じ固定合成入力の意味条件を再確認する | 1 call・retry 0、83.398秒、902 prompt・290 completion tokens、response 1,895 bytes、`finish_reason=stop`。未知語2種、価格範囲、除外対象、二重否定拒否、strict intent、ready proposal、query planの全判定成功。server停止・port非listen | SudachiPy adapter後の単一development regressionは成功した。未知入力全般、実商品、ranking、production E2Eの合格へ一般化しない |
| Core Ultra・UI | Core Ultra、browser、委託フロントエンド | 実行・接続していない |

### セキュリティ・互換性

超過値をtruncateせず、adapterの固定 `draft_schema_invalid` groupへ写す。検索可能応答へambiguityを混在させず、
確認待ちは他fieldを持たないため、部分抽出を承認済み検索として進めない。生response、検索文、field値、
validation detailを新しいdiagnosticへ追加しない。v7 request artifactはv8として再利用しない。

### ロールバック

bounded compact model、固定branch変換、v8 request、prompt、focused testを取り除き、request v7の19-field
compact modelとdigest domainへ戻す。application intent、cache、履歴、DBの移行は不要である。

### 結果

完了。検索可能compact wireを最大12種類の固定field、確認待ちを `ambiguities` だけへ分け、
商品名等48文字、term 32文字、各term list・typed condition・set値4件、ambiguity 2件・各96文字を
Pydantic modelとllama.cpp生成grammarへ反映した。categoryはproduct nameへ、colorとfeaturesはtermsまたは
typed conditionへ集約し、完全19-field application intentへ決定的に復元する。上限超過とbranch混在は
本文を保持せず拒否し、promptは切断・黙った欠落ではなくblocking確認待ちを要求する。

request schemaとdigest domainは8.0で、代表bodyは15,008 bytes、生成schemaは9,820 bytes、完全schemaは
7,352 bytes、promptは4,899 bytesである。代表fixtureは104 Bonsai tokensで、完全形式181 tokensより42.5%
少ない。applicationの `max_tokens` とHTTP timeoutは追加していない。

後続の承認済みlocalhost診断では、Core i5-13600KFのCPU版でrequest v8の同一入力2 callsが
ともに254 completion tokens、`finish_reason=stop`、strict intent成功となった。warm wallは
17.625秒で、旧v6の90.440秒より80.51%短縮・5.13倍だった。ただし、旧v6とは別runの
比較であり、実出力は196 tokensを超えた。credential、外部network、課金は使用していない。
Core Ultra、Vulkan、OpenVINO、NPU、未知入力のstrict成功率、意味品質は未確認である。

追加の承認済み固定入力1 callは50.628秒・82 completion tokensでstrict intentへ到達したが、価格、色、
除外条件を欠落し、入力にないstyleを不正なvalue typeで返したためblockingとなった。これを受け、入力言語、
原子的条件分解、未知語の原文保持、割当不能時のblockingを要求する3,600-byte promptへ短縮し、typed conditionを6 value-type branchへ
結ぶ10,950-byte生成schemaとadapter検証を追加した。同一入力のbodyは15,032 bytesから14,859 bytesへ減り、
203-byte ready fixtureとpromptにない日英3組の合成語彙はquery planまでofflineで成功した。

その後の明示承認済み1 callは53.595秒、887 prompt tokens、248 completion tokens、response 1,670 bytes、
`finish_reason=stop` でstrict intentへ到達した。ただし価格と除外条件を欠落し、入力にないtyped conditionも含めたため
proposalはblockingとなった。query plan、Outscraper、retryはなく、server停止とport非listenを確認した。

追加callなしで、providerのtyped candidateを入力中の原語・trusted registry aliasへ根拠付けし、根拠のない候補を
実行条件へ昇格しないadapter境界を追加した。不正candidateでも入力に現れる値は同じstrengthの自由語termへ戻す。
日本語の明示JPY上限・下限・範囲と、「不要・除外・避ける・without」に続く未知の除外語もsourceから決定的に
復元する。取得済み応答相当fixtureは価格上限10,000円、除外対象、白、ワイヤレスを保持し、無根拠条件を除去して
query planまでreadyとなった。request body、prompt、生成schemaは変えていないため、model生成時間を増やす変更ではない。
日本語の根拠照合と否定対象抽出は、その後さらにSudachiPy `SplitMode.C` の全形態素、品詞、正規化済みsource offsetへ置き換えた。
trusted aliasを完全な連続形態素spanにだけ一致させ、未知複合語内の単一漢字部分一致、格助詞より前の語の巻き込み、
二重否定を拒否する。既存tokenizerの公開出力、request body、prompt、schemaは変更していない。local warm adapter全体は
1,000回平均2.043352 msだったが、単一hostの限定測定でありproduction性能を保証しない。
後続の承認済み1-call localhost再実行は83.398秒、902 prompt tokens、290 completion tokens、response 1,895 bytesで
完了した。未知語2種、価格範囲、除外対象、二重否定拒否、strict intent、ready proposal、query planの全固定判定が
成功した。ただし単一の固定合成入力だけであり、未知入力全般、実商品、ranking、production E2Eの品質は未確認である。


## EXEC-060: Bonsai 196-token目標のcompact wire応答

### メタデータ

- 状態: 完了
- 作成日: 2026-09-06
- 最終更新: 2026-09-06
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)
- 関連要件: [FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)
- 先行Plan: [EXEC-059](#exec-059-bonsai応答時間のprompt生成分離診断)

### 目的

prompt cache後も約90秒を占めたBonsai completion生成を短くする。生成token数を196で強制切断せず、
意味のあるfield名と従来の19-field application契約を保ったまま、wire応答では `null`、空list、
価格の固定値・非該当fieldを省略する。受信側で省略値を決定的に復元し、代表fixtureの検索意図、
query plan、typed proposalを変えずにBonsai tokenizerで196 tokens以下となる形式を実装する。

196は代表fixtureの目標であり、任意の複雑な入力に対する固定長または生成上限ではない。

### 対象範囲

- `src/search_v2/bonsai_adapter.py` にprovider wire専用のstrict compact draftとcanonical復元を追加する
- 同じ意味のfield名を維持し、未指定のscalar・list・価格・typed condition・ambiguityだけを省略可能にする
- 価格ありでは `currency=JPY`、非該当価格値、null confidenceをwireから省き、復元後に既存 `PriceCondition` で再検証する
- 生成schemaとsystem promptをcompact・minified出力へ更新し、完全schemaはprovenanceと最終検証の正本として維持する
- request descriptorとdigest domainをv7へ更新し、旧v6 descriptorをfail-closedで拒否する
- adapter、request、localhost runnerのoffline testと関連文書を同期する

### 対象外

- `max_tokens=196` その他の生成token上限、application HTTP timeout、response byte上限の変更
- 実Bonsaiへの要求、localhost live再測定、実modelの意味品質・token数・速度の確定
- context 8,192、prompt cache、parallel 1、retry 0、server lifecycleの変更
- Core Ultra、Vulkan、OpenVINO、NPU、model・quantizationの変更
- legacy検索、Outscraper、Cloudflare、API、browser、外部委託中フロントエンドとの接続
- cache・履歴・DB schemaの移行、commit、push、merge

### 現在の状態

request v6は全19 fieldと価格7 fieldを常に生成し、同一入力のwarm callでも487 completion tokens、
generation 90,280.801 msだった。生成上限を196へ下げると `finish_reason=length` となる可能性があり、
既存adapterは安全に `output_truncated` として拒否する。生成なしのlocal tokenizer確認では、同じ
代表条件をminifiedな完全19-field JSONにすると181 tokensへ収まり、compact wireでは126 tokensへ
短縮できた。情報を削らずに既定表現だけを省略する形式目標は達成したが、実modelが新形式を
生成完了できることと実速度は未確認である。後続の承認済みlocalhost診断ではrequest v7を送信したが、
応答完了前の365.12秒で原因調査に十分なprocess状態を取得して手動停止した。

### 受入条件

1. compact wireは既存の意味あるfield名を使い、unknown field、型coercion、duplicate key、非有限数、
   不整合な価格、無効なtyped condition・ambiguityを従来どおりfail-closedで拒否する。
2. 省略したscalarは `null`、listは空list、価格全体は既存の `mode=none` 契約へ復元し、価格ありでは
   `currency=JPY`、非該当値、null confidenceを補完して完全な `SearchIntentDraft` を再検証する。
3. 代表fixtureのcompact応答と完全19-field応答は、provenanceだけを除いて同じnormalized intent、
   query plan、typed proposalを作る。
4. 代表compact JSONはrepositoryで使用したBonsai GGUFとlocal `llama-tokenize` により196 tokens以下と
   確認する。任意入力の固定196 tokens、実生成成功、品質、速度をoffline結果から主張しない。
5. request v7は新prompt、compact生成schema、完全schema、bodyの各digestをbindし、旧v6 descriptorを
   拒否する。bodyへ生成token上限を追加せず、response 1 MiB、retry 0を維持する。
6. 生成schemaは非blocking時の `product_name_ja` と、検索語なしblocking時のblocking ambiguityを
   生成時にも要求する。applicationの完全schema・正規化・検索可能性検証を置き換えない。
7. focused・関連回帰、標準offline gate、Python 3.10構文、Markdown、`git diff --check` が成功する。
8. live再測定はendpoint、exact入力、2 calls、retry、上限、credential、費用、保存範囲、実行機を
   改めて提示し、利用者の新しい明示承認後だけ実行する。

### 実行手順と進捗

- [x] 2026-09-06: request v6、生成schema、strict adapter、代表JSONのtoken削減余地を確認した。
- [x] 2026-09-06: compact復元、schema v7、意味同等性の期待契約をoffline RED testで固定した。
- [x] 2026-09-06: 最小実装でfocused testをGREENにし、Bonsai関連回帰175 passed・2 skippedを確認した。
- [x] 2026-09-06: 標準文書を現行挙動へ同期し、全offline gateを確認した。
- [x] 2026-09-06: 実装完了時点ではlive再測定を行わず、将来は条件再提示と新しい明示承認を必須とした。
- [x] 2026-09-06: 後続の明示承認後にlocalhost診断を開始し、原因調査に十分なprocess状態を取得したため、
  利用者指示どおり応答完了前に手動停止した。

### セキュリティ・データ・互換性

compact化はBonsai responseの一時的なwire表現だけを変える。復元後の `NormalizedSearchIntent`、
provenance、typed proposal、query、承認、cache、履歴のschemaは変更しない。省略を曖昧な推測に使わず、
既存の `null`、空list、価格なしだけへ写す。生成schemaは補助制約であり、受信後のstrict validation、
本文非露出の固定error、1 MiB上限を維持する。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_bonsai_compact.py` | compact復元・生成schema・request v7が未実装の理由で失敗 | 終了1、1 passed / 3 failed。test SHA-256 `38d7c8bb1083d7a7878d6a01ca4fa3618b101c2a49e82dda66ec38d0dc11169a` |
| prompt整合RED | compact schemaで許可しないnullをpromptが指示しないことをread-back後に固定 | 旧文言だけが失敗 | 6 passed・1 failed。`product_name_ja=null` の旧指示を検出 |
| focused GREEN | 同上 | 全件成功 | 7 passed。最終test SHA-256 `b96102f510b82ea25c045a97b389d71f9c57c6626f6781f54bd8ec5caaf9666e` |
| 関連回帰 | Bonsai adapter・request・HTTP・typed adapter・localhost runner | 全件成功 | 175 passed・2 skipped。live 2件はopt-inなしのためskip |
| tokenizer | 固定代表fixtureを現行GGUFでcompact・完全形式ともtokenize | compactが196以下 | compact 126、完全19-field minified形式181 tokens。55 tokens・30.4%削減 |
| schema・request artifact | llama.cpp converterとcanonical集計 | converter終了0、各digest固定、生成上限なし | converter終了0。body 18,163 bytes、compact生成schema 13,804 bytes、完全schema 7,352 bytes、prompt 4,074 bytes。bodyに `max_tokens` なし |
| 標準gate | lock、Ruff、Markdown、offline全体、Python 3.10 AST、`git diff --check` | 終了0 | lock 79 packages、Ruff 200 files、Markdown 16 files・1,299 links・898 anchors・1,658 headings・203 fence pairs、Markdown test 4 passed、次期検索963 passed・11 skipped、全体1,700 passed・9 skipped・3 deselected、Python 3.10 AST 200 files、zero-width scan、`git diff --check` 成功 |
| localhost v7診断 | 固定合成入力・同一bodyを最大2 calls、retry 0、prompt cache有効で送信 | 新しい明示承認後だけ実行し、本文を保存せず安全なtimingだけを得る | Core i5-13600KF・WSL2・CPU版で開始。body 18,172 bytes、SHA-256 `db1f302c51b61ae44f1ccde545e87708de82edb2a2e1bdff06643bc1fa9fa942`。365.12秒時点で応答未完了のため手動停止し、pytest testは未完了。1件または2件目のどちらを処理中だったか、完了call数、token数、strict結果、速度改善率は確定できない |
| Core Ultra・UI | Core Ultra、browser、委託フロントエンド | 本診断では実行しない | 実行・接続していない |

### 判断と見直し条件

- 196をhard capにせず代表fixtureの形式目標とする。実出力分布を測定せずにcapすると正常応答も
  truncationで失敗し、品質を維持できないためである。
- 短い不透明なaliasは使わない。token削減よりmodelのfield対応と保守性を優先し、既定値の省略と
  minified JSONだけをwire差分にする。
- v6 artifactを暗黙に再利用しないようrequest schemaとdigest domainをv7へ更新する。復元後の
  application intent schemaは意味を変えないためversion 2.0を維持する。
- 代表fixtureが196 tokensを超える、またはliveで意味欠落・strict拒否が増える場合は、hard capを
  追加せずprompt・wire schemaを見直す。
- localhost診断中はserverが約995% CPU、30 threads、RSS 2,527,844 KBで動作し、loopback接続は
  established、clientはsocket read待ちだった。request buildとcompact parseのoffline平均はそれぞれ
  4.466 msと2.574 msであり、停止時の主処理はapplication、接続、復元ではなくserver内の生成だった。
- compact生成schemaのgrammarは48,736 bytes、289行、833 alternationsで、任意field、長い文字列、
  多数要素の配列を許す。126 tokensは代表fixtureであって生成上限ではないため、長い生成が有力原因である。
  応答、completion token数、server timingを取得していないため断定はせず、grammar sampling overheadも
  未分離とする。

### ロールバック

compact wire model・復元、request v7、prompt、focused testと関連文書を取り除き、request v6の
生成schemaと全field必須promptへ戻せばよい。canonical intent、cache、履歴、DBの移行は不要である。

### 結果

完了。request v7のcompact wire、完全19-field復元、sparse価格schema、minified prompt、v7 digestを
実装した。代表fixtureは126 Bonsai tokensで196-token目標を満たし、完全形式とのnormalized intent、
query plan、typed proposalの同等性を確認した。196はhard capではなく、bodyへ生成token上限を
追加していない。後続の承認済みlocalhost診断は365.12秒で手動停止し、server内の生成が継続していた
ことまでは確認したが、応答、token数、strict結果、速度改善率は得ていない。credential、外部network、
課金は使わず、停止後はserver processなし・port非listenを確認した。Core Ultra、Vulkan、browser、
外部委託中のフロントエンドは実行・確認・接続していない。


## EXEC-059: Bonsai応答時間のprompt・生成分離診断

### メタデータ

- 状態: 完了
- 作成日: 2026-09-06
- 最終更新: 2026-09-06
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)
- 関連要件: [FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)
- 先行Plan: [EXEC-058](#exec-058-request-v6prompt-cache-localhost結合テスト)

### 目的

EXEC-058で1件目99.729秒、2件目579.494秒となった差を、異なる入力間の推測で説明せず、
同じ非機密入力をrequest v6で2回実行してcold・warmを比較する。llama.cpp応答から本文を
残さず、prompt処理時間、completion生成時間、生成token数を分離し、cacheが効いた区間と
総時間を支配した区間を確認できるようにする。

### 対象範囲

- 現行localhost runnerへ、boundedな `completion_tokens`、`prompt_n`、`prompt_ms`、
  `predicted_n`、`predicted_ms`、`finish_reason`、response byte数のstrict投影を追加する
- 同じ固定合成入力を、同じtest所有serverへtemperature 0で2回逐次送る専用live testを追加する
- 1件目cold、2件目cache hit、両方のfull JSON・strict intent成功を確認する
- 既存の異なる入力2件によるEXEC-058結合testと通常offline testを維持する
- README、DEVELOPMENT、BACKEND、SECURITY、REQUIREMENTS、NEXT-STEPS、WORKLOG、CHANGELOGを同期する

### 対象外

- 生request、生response、生成JSON、入力本文、cache内容、server logの保存・出力
- applicationの生成token上限またはHTTP timeoutの追加、response契約・prompt・schemaの変更
- cache無効との追加比較、3 calls以上、retry、負荷・並列・長時間安定性試験
- Core Ultra、Vulkan、OpenVINO、NPU、別model・quantizationの性能確認
- legacy検索、Outscraper、Cloudflare、ranking、API、browser、外部委託中フロントエンドとの接続
- commit、push、merge

### 現在の状態

EXEC-058は2件目で891 / 925 prompt tokensのcache hitを確認したが、入力と生成内容が異なり、
runnerはprompt token数とtotal wall時間だけを保存したため、479.765秒の差を分解できなかった。
EXEC-059で同一request v6を2回実行し、両方487 completion tokens・`finish_reason=stop`・full JSON・
strict intent成功となった。2件目は923 / 924 prompt tokensをcacheから再利用した。

### 受入条件

1. timing投影はduplicate key、非有限数、型coercion、負値、token数の不整合、過大値、未知の
   finish reasonを固定errorで拒否し、本文・入力・任意provider fieldをresultへ保持しない。
2. 診断testは既存の二重opt-inとabsolute regular server・model pathを必須にし、同じ固定合成入力を
   schema 6.0、temperature 0、同一server、2 calls、各1 attempt、retry 0で送る。
3. 両方がfull JSONとstrict intentを通過し、1件目cached 0、2件目cached正、prompt・生成の
   token数と時間がllama.cppの整合するbounded metadataとして得られる。
4. 出力するのはcall数、schema version、prompt・cache・completion・timing・response byte数、
   finish reason、server停止状態だけとし、合成入力と生成内容を含めない。
5. context 8,192、parallel 1、prompt cache有効、loopback、log無効、slot非保存、response 1 MiB、
   startup 180秒、ready後全体900秒、成功・失敗・deadline時cleanupを維持する。
6. focused・関連回帰、標準offline gate、Python 3.10構文、Markdown、`git diff --check` が成功する。
7. live実行前にendpoint、exact payload、2 calls、retry 0、上限、credential、費用、保存範囲、
   実行機を改めて提示し、新しい明示承認を得る。

### 実行手順と進捗

- [x] 2026-09-06: EXEC-058の安全な集計とrunner計測範囲、local llama.cppのcache・timing実装を確認した。
- [x] 2026-09-06: timing投影と同一入力2 callsの期待契約をoffline RED testで固定した。
- [x] 2026-09-06: 最小実装でGREENにし、既存結合testと標準offline gateを確認した。
- [x] 2026-09-06: 実行条件を再提示し、利用者の新しい明示承認後だけlocalhost実modelを実行した。
- [x] 2026-09-06: 安全な数値を記録し、原因を確認できる範囲と未確認範囲を同期した。

### セキュリティ・データ・互換性

raw responseは既存strict adapterと新しいmetadata投影の間だけmemoryに置き、直後に破棄する。
projectionはOpenAI互換usageとllama.cpp timingsの列挙済み数値・finish reasonだけを新しい非repr resultへ
写す。server子processへ親環境を継承せず、loopback以外へ接続せず、server logとslot保存を無効にする。

request v6、固定prompt、生成schema、完全schemaによるstrict最終検証、1 MiB response上限、retry 0、
application timeout・生成token上限なしを変更しない。live markerとCLI opt-inは人間承認を代替しない。

### 判断と見直し条件

- 同一入力・temperature 0でもhardwareや数値計算によりcompletion token数が一致するとは仮定せず、
  実測値が一致した場合だけwall・prompt・generation時間をcold・warm比較する。
- cache効果はtotal wallだけでなく `cached_tokens` と `prompt_ms` で判断する。
- `predicted_ms` が総時間を支配する場合はprompt cacheの失敗ではなくcompletion生成を次の改善対象とする。
- この診断はCore i5-13600KFのCPU版localhost単一境界であり、Core Ultraやproduction E2Eへ外挿しない。

### ロールバック

本Planで追加するbounded timing field、同一入力診断test、関連文書だけを取り除けば、EXEC-058の
request v6＋cache結合testと既存production request契約を変更せず元へ戻せる。

### 結果

完了。bounded timing投影、同一request v6の2 calls、通常live testとの排他selectorを実装し、focused 33 passed・2 deselected、関連回帰150 passed・2 deselected、通常収集33 passed・2 skippedを確認した。標準offline gateも1,694 passed・9 skipped・3 deselected、Ruff・Markdown・Python 3.10構文・lock・差分検査まで成功した。

新しい明示承認後、Core i5-13600KF・CPU版で専用localhost診断を実行し、231.24秒で1 passedとなった。両callは同じschema 6.0 body、924 prompt tokens、487 completion tokens、`finish_reason=stop` で、full JSONとstrict intentを通過した。coldはprompt 43,655.256 ms、generation 93,609.113 ms、wall 137,311 msだった。warmは923 tokensをcacheし、処理1 token、prompt 123.505 ms、generation 90,280.801 ms、wall 90,440 msだった。

prompt区間は43,531.751 ms短縮、353.47倍、99.72%減、wall全体は46,871 ms短縮、1.52倍、34.13%減だった。生成区間は同じ487 tokensで3,328.312 ms、3.56%の観測差に留まり、warm wallの99.82%を生成が占めた。したがってprompt cacheは正常かつ大幅に効く一方、full JSON応答ではcompletion生成が主な残存時間である。EXEC-058の旧579.494秒は当時のcompletion timingを保存していないため直接分解できないが、cache不発を原因とする根拠はなく、生成量または生成速度側が有力である。

credential、外部network、課金、retry、server log、slot保存、生要求・生応答の保存はなく、終了後はserver processなし・port 18080非listenを独立確認した。これは現行Core i5-13600KFの単一測定であり、Core Ultra、Vulkan、production E2E、検索全体の性能を示さない。


## EXEC-058: request v6＋prompt cache localhost結合テスト

### メタデータ

- 状態: 完了
- 作成日: 2026-09-06
- 最終更新: 2026-09-06
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)
- 関連要件: [FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)
- 先行Plan: [EXEC-057](#exec-057-bonsai本番prompt-cacheとrequest-context縮小)

### 目的

request v6と本番相当の `--cache-prompt -c 8192 -np 1` を同じlocalhost
`llama-server` で結び、2回目のBonsai要求が固定prefixのKV cacheを再利用したことと、
full JSON応答がapplication側のstrict intent検証まで到達することを、明示opt-inの
localhost結合テストで確認できるようにする。

### 対象範囲

- `pytest` へlocalhost Bonsai専用の明示opt-inとserver・model path引数を追加する
- testが専用 `llama-server` をloopbackだけへ起動し、正常・失敗の両方で停止する
- 非機密の合成入力2件をrequest v6 builder、Requests transport、strict response adapterへ通す
- 2件目の `usage.prompt_tokens_details.cached_tokens` が正であることを検証する
- server起動引数、response metadata投影、opt-in境界を外部通信なしのtestで固定する
- README、DEVELOPMENT、BACKEND、SECURITY、REQUIREMENTS、NEXT-STEPS、WORKLOG、CHANGELOGを同期する

### 対象外

- 外部委託中フロントエンドの確認、起動、テスト、接続
- legacy `run_product_search()`、API、Outscraper、Cloudflare、Amazon商品取得との接続
- credential、外部network、課金、browser、複数利用者、負荷・長時間安定性の検証
- Vulkan、SYCL、OpenVINO、NPU版build、driver、modelの変更
- commit、push、merge

### 現在の状態

request v6のcanonical body、actual Requests transport、strict adapter、prompt cache metadata、
test所有serverのlifecycleを専用runnerへ接続した。offline testは固定command、二重opt-in、
2 calls、deadlineを含むcleanupを確認した。明示承認後のlocalhost実model 2 callsも完了し、
両方がfull JSONとstrict intentを通過し、2件目で正のcached token数を確認した。
EXEC-057のlocalhost速度比較はv6とcacheを同時に使用したものの、`max_tokens=1` のprompt処理
benchmarkであり、今回のfull JSON所要時間と直接比較できる同一条件ではない。

### 受入条件

1. 通常pytestとCIではlive testを収集対象外またはskipにし、`--run-live-api`と
   Bonsai専用opt-inの両方なしに起動しない。
2. serverは利用者が明示したregular executableとregular modelだけを使い、
   `127.0.0.1`、context 8,192、parallel 1、prompt cache有効、server log無効で起動する。
   diskへslotを保存しない。
3. chat completionは非機密の合成入力2件、各1 attempt、retry 0に固定し、両方が
   request schema 6.0、full JSON、strict intentに成功する。application側に生成token上限と
   HTTP timeoutを追加しない。
4. 1件目はcold cache、2件目は正のcached token数を返し、異なるuser messageでも
   固定system prefixが再利用されたことを確認できる。
5. 要求・応答本文、検索文、cache内容、server logを保存・出力せず、安全な固定status、
   schema version、call数、cached token数、時間だけを報告する。
6. test所有serverは成功・例外・全体deadline到達の全経路で停止し、元々使用中のportや
   無関係processを操作しない。
7. focused test、関連回帰、標準offline gate、Markdown、Python 3.10構文、`git diff --check`
   が成功する。live実行は条件を実行直前に提示し、利用者の新しい明示承認後に行う。

### 実行手順と進捗

- [x] 2026-09-06: 現行test、CI、network guard、request v6、manual cache benchmarkの境界を確認した。
- [x] 2026-09-06: localhost結合runnerの期待契約をoffline RED testで固定した。
- [x] 2026-09-06: request v6、actual Requests transport、strict adapter、cache metadata、server lifecycleを接続した。
- [x] 2026-09-06: focused、関連、標準offline gateと文書整合を確認した。
- [x] 2026-09-06: 利用者へ実行条件を提示して新しい明示承認を得た後、localhost実modelの2 callsを実行した。

### セキュリティ・データ・互換性

live testはloopbackとlocal modelのみを使い、credential、外部network、課金を伴わない。
server起動前にport未使用、実行file、model file、opt-inを検査する。全体deadlineは
test harness所有serverを停止するための外側安全境界とし、production Requests transportの
HTTP timeoutは引き続き設けない。生responseはstrict adapterとcache metadata投影の間だけ
memoryに保持し、result、log、artifact、例外へ含めない。

`live_api` markerとCLI opt-inは誤実行防止であり、人間承認の代替にはならない。
request schema、OpenAI互換endpoint、完全schemaのstrict検証、retry 0を変更しない。

### 判断と見直し条件

- このtestはBonsai intent境界のlocalhost live結合であり、Outscraper、ranking、API、UIを含む
  production E2Eとは表現しない。
- cache hitは所要時間の比較ではなく、llama.cpp応答の正の `cached_tokens` で判定する。
- 実行時に対象Core Ultra機を使う場合も、CPU、Vulkan、OpenVINO、NPUを別構成として記録する。

### ロールバック

本Planで追加するlive test、localhost runner、pytest option・marker、関連文書だけを取り除けば、
request v6、本番server起動例、既存offline testに影響せずEXEC-057完了時点へ戻る。

### 結果

実装とoffline検証まで完了した。REDは新module不在によるcollection error、focused GREENは
16 passed・1 live deselected、Bonsai request・HTTP・adapterを含む関連回帰は133 passed・
1 live deselected、通常収集は16 passed・1 live skippedだった。標準offline gateはlock
79 packages、Ruff 199 files、offline pytest 1,677 passed・9 skipped・2 deselected、
Python 3.10 grammar AST 199 files、Markdown 16 files・1,285 links・884 anchors・
1,628 headings・201 fence pairs、`git diff --check` に成功した。

明示承認後、Core i5-13600KF・CPU版llama-server version 9294、context 8,192、parallel 1、
prompt cache有効、temperature 0でlocalhost実modelを実行した。request v6の2 callsはいずれも
full JSON生成とstrict intent検証に成功した。1件目はprompt 924・cached 0 tokens・99.729秒、
2件目はprompt 925・cached 891 tokens・579.494秒で、2件目のprompt cache率は約96.3%だった。
test全体は683.00秒で1 passedとなり、server停止とport 18080非listenを独立確認した。

2件は入力と生成内容が異なりcompletion token数も安全な集計へ保存していないため、99.729秒と
579.494秒の差をcacheによる速度差として扱わない。今回確認したのはrequest v6、full JSON、
strict intent、prompt cache hitのlocalhost単一境界である。Core Ultra性能、Outscraper、ranking、
API、UI、production E2Eは未確認である。


## EXEC-057: Bonsai本番prompt cacheとrequest context縮小

### メタデータ

- 状態: 完了
- 作成日: 2026-09-06
- 最終更新: 2026-09-06
- 関連Task: [TASK-008](#task-008-次期検索フロー-v2-の実装)
- 関連要件: [FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)

### 目的

Core Ultra 9 288Vでの本番運用に先立ち、同じ固定system promptを再利用するBonsai serverのprompt cacheを有効にし、完全schemaをsystem messageと `response_format` の両方へ重ねていたrequestを縮小する。縮小後のmodel入力を現行Bonsai tokenizerで確認し、server contextを8,192から4,096へ下げられるかを外部通信と生成なしで判断する。

### 対象範囲

- READMEの本番Bonsai起動例へ明示的なprompt cache、検証で決めたcontext、parallel 1を追加する
- `src/search_v2/bonsai_request.py` から完全schemaのsystem message埋込みだけを除去する
- 生成用schemaは `response_format.schema`、完全schemaはapplication側のstrict最終検証とdigest bindingに維持する
- request bodyとsystem messageの縮小、両schema digest、改ざん拒否をoffline testで固定する
- 現行Bonsai tokenizerを使い、最大2,000 codepointの合成入力を含むmodel入力が4,096 token未満であることを生成なしで確認する
- BACKEND、REQUIREMENTS、SECURITY、REFERENCES、NEXT-STEPS、WORKLOG、CHANGELOGを現行動作へ同期する

### 対象外

- Vulkan、SYCL、OpenVINO版llama.cppのbuild、install、driver変更
- 実Bonsaiへのchat/completions、Outscraper、Cloudflare、OpenAI、Amazon、credential、外部通信、課金
- Bonsai model、生成用schema、完全schema、response adapter、検索意味品質の変更
- 外部委託中フロントエンドの確認、起動、テスト、接続
- commit、push、merge

### 現在の状態

現行request schema 5.0は、完全schemaをsystem messageへ連結し、生成用schemaを `response_format.schema` にも含める。代表request bodyは約29 KB、system messageは約11 KBである。過去のdevelopment regressionは再現性と本文非保持を優先してserver prompt cacheを無効化し、context 8,192、parallel 1で実行した。本番起動例はcacheとcontextを明示していない。実Bonsai、Core Ultra 9 288V、Vulkanは本Planでは実行しない。

### 受入条件

1. system messageは固定promptだけを持ち、完全schema本文を含まない。
2. `response_format.schema` は現行の非空生成用schemaを維持する。
3. request descriptorは完全schemaと生成用schemaの両digestを維持し、実行直前の変更を拒否する。
4. READMEの本番起動例は `--cache-prompt`、検証で決めた `-c`、`-np 1` を明示し、過去のcache無効development regressionと区別する。
5. 最大2,000 codepointの合成入力を含むsystem・user messageを現行Bonsai tokenizerで生成なしに確認する。4,096へ収まらない有効入力がある場合は8,192を維持する。
6. focused、関連回帰、標準offline gate、Markdown、Python 3.10構文、`git diff --check` が成功する。

### 実行手順と進捗

- [x] 2026-09-06: 現行request、生成・完全schema、起動例、過去のcache無効実測条件を確認した。
- [x] 2026-09-06: 期待する縮小requestのtestを先に追加し、旧5.0と完全schema連結を対象理由とする2 failed・44 passedのREDを確認した。
- [x] 2026-09-06: 最小実装でschema二重送信を除去し、本番起動例を `--cache-prompt -c 8192 -np 1` へ更新した。
- [x] 2026-09-06: 最大長合成入力をtokenizeし、4,096 contextは現行入力契約に不適合、8,192維持と判定した。
- [x] 2026-09-06: 関連文書と履歴を同期し、focused・関連・全v2・標準offline gateを確認した。
- [x] 2026-09-06: 明示承認されたlocalhost 8 attempts以内で、変更前相当cache無効とrequest v6 cache有効の1-token prompt処理速度を比較し、server停止まで確認した。

### セキュリティ・データ・互換性

完全schemaはmodel入力から外してもapplication側のstrict検証とdigest bindingに残す。生成用schema、response 1 MiB上限、1 call予約、retry・redirect禁止、本文非保持を変更しない。prompt cacheは同一process内のKV再利用であり、diskへのslot保存を設定しない。実利用者入力、生response、cache内容を保存しない。

request body digestが変わるため旧request artifactと互換扱いにせず、schema versionを更新する。OpenAI互換endpointとBonsai provider判断は維持する。Vulkan buildは現行CPU版の完成後に別Planで扱う。

### 判断と見直し条件

- 本番serverではllama.cppのprompt cacheを明示的に有効化する。再現性優先の限定検証で無効化する場合は本番設定と区別する。
- context 4,096はbyte数ではなく現行model tokenizerの最大長合成入力で判断する。固定promptは883 tokensまで縮小できるが、有効な2,000 codepointの合成入力だけで4,000 tokensになる例を確認したため、入力上限を変更しない本Planでは8,192を維持する。
- schema縮小後にstrict JSON成功率または意味品質が低下する可能性はoffline testと1-token benchmarkだけでは否定できない。full JSONの実model確認は条件を再提示して別途明示承認を得る。

### ロールバック

request schema version、system message構築、対応test、本番起動例、本Planに伴う標準文書だけを戻せば、完全schemaをmodelにも送るschema 5.0とcontext 8,192の状態へ戻る。外部状態、model、runtime build、cache fileは変更しない。

### 結果

完了。request schemaを6.0へ更新し、system messageを固定promptだけにして、生成用schemaを `response_format.schema`、完全schemaを別digestとapplication側strict最終検証へ維持した。合成fixtureのbodyは20,716 bytes、system messageは3,772 bytesで、model入力から完全schema 7,352 bytes・2,000 tokensを除去した。生成なしのtokenizer確認では固定prompt 883 tokens、最大長の通常日本語例2,000 tokensに対し、現行検証を通る別Unicode例は4,000 tokensだった。後者とpromptだけで4,883 tokensとなるため、4,096 contextは全入力契約を満たさず8,192を維持する。

本番起動例へ `--cache-prompt -c 8192 -np 1` を明示し、diskへslotを保存する `--slot-save-path` は設定していない。REDは2 failed・44 passed、focused GREENは46 passed、関連141 passed、全v2は924 passed・9 skippedだった。標準offline gateはlock 79 packages、Ruff 197 files、offline pytest 1,661 passed・9 skipped・1 deselected、Python 3.10 AST 197 files、Markdown検査と `git diff --check` に成功した。

追加の明示承認後、Core i5-13600KF・WSL2・CPU版llama-server version 9294、context 8,192、parallel 1、temperature 0、出力1 token、非機密合成入力でlocalhost benchmarkを行った。変更前相当の完全schema二重送信・cache無効は有効2計測のwall中央値142.559秒、prompt処理中央値142.525秒、prompt token中央値2,925.5だった。request v6・cache有効はcold 40.715秒、cache warm後3計測のwall中央値1.236秒、prompt処理中央値1.208秒、処理18 tokens・cache 895 tokensだった。warm比較は約115.3倍・wall 99.13%短縮、prompt処理約118.0倍・99.15%短縮である。変更前4 attemptsのうち1件はbufferされた進捗の誤認でclient側から中断し、retryしていない。合計8 attemptsを超えず、credential、外部network、費用はなく、終了後にserver processとport 18080の不在を確認した。

このbenchmarkはprompt prefillとcache効果だけを測る。full JSON生成、strict intent成功率、実検索のend-to-end latency、Core Ultra、Vulkan、browser、production E2Eは実行・確認していない。

記録更新後も標準offline gateはlock 79 packages、Ruff 197 files、offline pytest 1,661 passed・9 skipped・1 deselected、Python 3.10 AST 197 files、Markdown 16 files・1,278 links・877 anchors・1,613 headings・199 fence pairs、`git diff --check` に成功し、server processなし・port 18080非listenを維持した。


## EXEC-056: ローカル単独利用向け検索ジョブ基盤

### メタデータ

- 状態: 完了
- 作成日: 2026-09-05
- 最終更新: 2026-09-05
- 関連Task: [TASK-001](#task-001-検索処理のジョブ化)
- 関連要件: [NFR-203・NFR-204](REQUIREMENTS.md#83-性能可用性)
- 関連課題: [TD-001](ISSUES.md#td-001-同期的な検索実行)

### 目的

ローカルで1人が使う検索処理を、将来の画面要求とは別のbackground workerで実行できるbackend境界へ分離する。利用者が将来観察できる結果は、同じ検索の二重投入を防ぎながら、queued、running、cancel requested、succeeded、failed、cancelled、queued timeoutの状態を後から照会できることである。

本Planはjob metadataと注入callbackを使うoffline backend実装である。現行Streamlit、外部委託中の次期フロントエンド、実Bonsai・Outscraper・Cloudflare、実商品検索へは接続しない。

### 対象範囲

- `src/search_v2/search_job.py` のstrict・frozen model、SQLite repository、単一worker executor
- server-side固定local owner、同時実行1件、同一bindingの冪等な投入
- 24時間以内に開始できなかったqueued jobの `timed_out` 化
- queuedの即時取消と、running callbackへ伝える協調的取消
- process再起動後にcallbackを復元できないactive jobの固定失敗または取消への回復
- 終了済みjob metadataの30日保持と明示purge
- 一時SQLiteと注入callbackだけを使うoffline test
- BACKEND、REQUIREMENTS、DB-SCHEMA、SECURITY、ISSUES、NEXT-STEPS、WORKLOG、CHANGELOGの同期

### 対象外

- 現行Streamlitまたは外部委託中フロントエンドの変更、確認、起動、テスト、API接続
- 実Bonsai、Outscraper、Cloudflare、Amazon、OpenAI、credential、外部通信、課金
- provider要求中のthread強制停止、local Bonsaiの生成token上限または実行timeout
- 自動retry、同じ承認bindingの再実行、approval token・検索文・商品・provider本文のjob DB保存
- 複数process、複数host、複数worker、公開利用、認証・認可
- job結果本体の保存形式変更。成功jobは既存検索履歴等の安全なlocatorだけを参照する

### 現在の状態

着手時、現行Streamlitは `run_product_search()` を同じ実行内で呼び、Outscraper polling中も画面要求を占有していた。次期検索orchestrator、利用量ledger、検索履歴repositoryはoffline実装済みだったが、job投入・状態保存・worker実行境界はなかった。本Planでそのlocal backend境界を追加したが、現行Streamlitと実検索へは接続していない。

利用者は2026-09-05に運用形態をローカル専用と決定した。公開・複数利用者向けのTASK-003は開始せず、single-host・single-processだけを今回の互換境界とする。

### 受入条件

1. job入力・snapshotはstrict・frozenで、owner、binding、時刻、状態の型違いと不整合を拒否する。
2. SQLiteは0600のregular file、固定schema、transactionを使い、同じowner・bindingの同時投入を1 jobへ収束させる。
3. executorはworker 1本だけを持ち、callbackの最大同時実行数を1に固定する。
4. queued jobはprovider callback開始前に取消でき、running jobは取消要求を保持してcallbackへ協調的に通知する。取消後の返却結果を成功として採用しない。
5. callback例外の本文を保存せず固定codeで `failed` にし、成功時もbounded locator以外の結果本文をjob DBへ保存しない。
6. worker開始前に24時間を超えたjobはcallbackを実行せず `timed_out` にする。開始済みcallbackにはruntime timeoutを追加しない。
7. process再起動時は復元不能なqueued・runningを固定失敗、cancel requestedをcancelledへ原子的に回復し、自動で外部処理を再実行しない。
8. 終了後30日を過ぎたjobだけを明示purgeでき、ownerの異なるlocatorを取得・取消できない。
9. REDからGREEN、focused・全v2・offline全体、lock、Ruff、Markdown、Python 3.10構文、`git diff --check` を確認し、live・browser未実行を記録する。

### 実行手順と進捗

- [x] 2026-09-05: `AGENTS.md`、`DEVELOPMENT.md`、TASK-001、TD-001、既存orchestrator・履歴SQLite境界を確認した。
- [x] 2026-09-05: ローカル専用、single-host、single-process、同時実行1件を利用者判断と実装方針へ固定した。
- [x] 2026-09-05: 受入testを先に追加し、公開APIだけのscaffoldで13件すべてが期待した `NotImplementedError` になるREDを確認した。test SHA-256は `e1cbf9138140d92051cb338fc23cddbd18c47ba405f40c6615b7a1b868ea60dc`。
- [x] 2026-09-05: strict model、SQLite repository、worker、取消・再起動・保持境界を実装し、focused 13件をGREENにした。
- [x] 2026-09-05: 全search_v2回帰と標準offline gateを実行した。
- [x] 2026-09-05: 標準文書を同期し、実検索・結果履歴・UI接続が納品後まで残ることと再開位置を記録した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_search_job.py` | scaffoldの未実装操作が `NotImplementedError` で失敗 | 終了1、13 failed。全件がscaffoldの `NotImplementedError` |
| focused GREEN | 同上 | 全件成功 | 13 passed |
| 関連回帰 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_*.py` | 全件成功 | 924 passed、9 skipped |
| 標準gate | lock、Ruff check/format、Markdown、offline pytest、Python 3.10 AST、`git diff --check` | 終了0 | lock 79 packages、Ruff 197 files、offline pytest 1,661 passed・9 skipped・1 deselected、Python 3.10 AST成功、Markdown・diff成功 |
| live・UI | 実provider、credential、browser、委託フロントエンド | 本Planでは実行しない | 対象外 |

### セキュリティ・データ・互換性

job DBには固定local owner、random locator、binding digest、状態、時刻、固定失敗code、成功結果のlocatorだけを保存する。検索文、商品情報、approval token、API key、provider URL・response、例外本文を保存しない。SHA-256は匿名化として扱わない。

同一bindingは二重callbackを起動せず、再実行は新しい明示承認から得る別bindingを必要とする。process再起動後もcallbackを推測復元せず安全に停止する。既存履歴schema、cache、provider、orchestratorの公開契約は変更しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-05 | ローカル専用、単一ホスト・単一process、worker 1本に固定する | 利用者の明示判断と、現行file cache・in-memory approval境界を越えないため | 公開、複数利用者、複数processが必要になったらTASK-003・TD-002を先行して再設計する |
| 2026-09-05 | job DBへ検索payloadを保存せず、callbackはprocess内だけで保持する | 検索文、token、provider情報を新しい永続領域へ複製しないため | 再起動後の自動再開は行わず、別の明示承認から新jobを作る |
| 2026-09-05 | timeoutはqueued開始待ちだけに適用し、実行中callbackへ設けない | local Bonsaiのapplication timeoutを撤廃した既存判断を維持するため | 分離processで安全に停止できる方式を別Planで採用した場合だけ再検討する |
| 2026-09-05 | 自動retryを実装しない | 外部API attemptと承認・利用量予約を暗黙に増やさないため | 新しい承認bindingと費用表示を伴う利用者操作として将来UI接続時に扱う |

### 発見事項

- 現行orchestratorの実行時callbackとraw approval tokenは永続化用modelではない。再起動後の自動復元対象にせず、active jobを固定終端へ移す必要がある。
- 終了jobの30日保持testで、30日後に未開始queued jobを残すfixtureは24時間の開始期限と矛盾した。保持対象を開始済みactive jobへ訂正し、期限削除が終了jobだけへ作用する受入意図を維持した。
- repositoryの件数照会もownerを必須にし、local-onlyであっても別ownerのaggregateを返さない契約へ揃えた。

### ロールバック

新規job module、focused test、本Planに伴う標準文書の追記だけを取り除けばEXEC-055完了時点へ戻る。実provider、現行pipeline、cache、履歴schema、フロントエンド、外部状態を変更しない。local job DBが作成された場合はアプリ停止後に利用者が対象pathを確認して削除する。

### 結果

local単独利用向けのjob metadata・repository・worker境界を実装した。production source SHA-256は `21ae58994002b8a31958848a3a3b4a56cc872afabc08efcba54ebeaf13b204ff`、最終test SHA-256は `572c49dd05b5f9871823cb6ff3c94037d73c47de74415721ca48094568a21e80` である。focused、全search_v2、標準offline gateは成功した。

このEXEC-056完了時点ではTASK-001全体は完了しておらず、実検索callback、成功結果の履歴locator、利用者向け状態表示・取消操作への接続を保留した。後続の [EXEC-075](#exec-075-暫定本番検索のjob履歴接続と無quota方針) でproduction callbackと履歴locatorのoffline接続を完了し、API・状態表示・取消操作は外部委託中フロントエンドの納品完了まで保留している。


## EXEC-055: query-less blocking第1確認のlocalhost 1件結合確認

### メタデータ

- 状態: 完了（承認済み1 callを消費済み）
- 作成日: 2026-09-05
- 最終更新: 2026-09-05
- 前提Plan: [EXEC-054](#exec-054-query-less-blockingの第1確認接続)
- 関連要件: [TASK-008](#task-008-次期検索フロー-v2-の実装)、[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

EXEC-054でoffline実装した第1確認結合を、local Bonsaiの実応答1件で確認する。使用済みCSVの先頭 `mouse-01` を現行 `start_intent_review()` へ通し、strict intentが受理された場合に、`ready` ならquery付き `IntentReview`、`blocking` ならqueryなし `BlockingIntentReview` として返ることを確認する。

### 対象範囲

- 対象: `http://127.0.0.1:18080/v1/chat/completions` のlocal Bonsai、使用済みCSVの先頭1 case、合計1 call、retry 0
- 対象: request schema 5.0、固定prompt、完全schema、生成schema、strict adapter、typed proposal、queryの有無を含む第1確認までの結合
- 対象: model・CSV・prompt・schema・body・request digest、token・timeout不在、health-ready、call数、利用量状態、server停止の確認
- 対象外: 2件目、同一case再試行、dataset report・assessment、商品取得・ranking、画像生成、画像ranking
- 対象外: Cloudflare、Outscraper、Amazon、OpenAI、credential、課金、外部network、browser、Windows native、外部委託中フロントエンド、AIレビューハーネス、commit、push

### 実行承認と固定条件

利用者へendpoint、固定model、固定prompt・両schema・検索文だけを含むpayload、先頭1件・合計1 call、retry 0、application生成token上限・HTTP timeoutなし、response 1 MiB、credential・費用・外部networkなし、本文非保持、商品取得・rankingを行わない条件を提示し、2026-09-05に明示承認を得た。結果にかかわらず2件目または同一caseを送らず、使用済みdataによるdevelopment regressionとしてだけ扱う。

### 受入条件

1. 送信前に固定artifactとcanonical requestが一致し、portが非listen、対象 `llama-server` processがない。
2. `/health=200` 後、先頭caseのcanonical requestだけを1回送り、自動retryしない。
3. strict intentを受理した場合、`ready` はquery planとquery digestを持ち、`blocking` は専用確認型でquery planとquery digestを持たない。
4. Cloudflare・Outscraperのreservationとtransport call、商品取得、ranking、dataset assessmentを開始しない。
5. 検索文、生response、正規化intent、typed condition、ambiguity message、商品情報を結果または文書へ保存しない。
6. 実行後にserverを停止し、port非listenとprocess終了を確認する。

### 進捗

- [x] 2026-09-05: 使用済みCSVを独立holdoutではなくdevelopment regressionとして再利用する利用者判断を確認した
- [x] 2026-09-05: endpoint、payload範囲、1 call、retry 0、token・timeout不在、保存範囲、費用・credential・外部通信なしを提示して明示承認を得た
- [x] 2026-09-05: 固定artifact、canonical request、call guard、port・process状態を送信前に検査した
- [x] 2026-09-05: `/health=200` 後に先頭1件を1回だけ現行orchestratorへ通した
- [x] 2026-09-05: server停止、port非listen、process終了、一時runner削除を確認した
- [x] 2026-09-05: focused・関連回帰、標準offline gate、正本文書同期を完了した

### 実行結果

- 最初のpreflightは一時runnerをfile pathで直接起動したためrepository rootがimport pathへ入らず、`ModuleNotFoundError: No module named 'src'` で送信前に停止した。server起動とmodel callは0件だった。`PYTHONPATH=.` を明示した再検査で解消した。
- server起動用の最初のshell commandは、後片付けを含む `rm -f` が実行環境の安全filterに拒否され、command自体が実行されなかった。削除操作を含まない起動へ分け、同じ固定条件を維持した。
- 送信前にCSV 12 rows・4 unique cases・先頭 `mouse-01`、model、server、prompt、完全schema、生成schema、canonical body、request、orchestrator、runnerのdigestを照合した。port `18080` は非listen、対象server processは不在、requestに `max_tokens` とHTTP timeoutはなかった。
- `/health=200` の後に現行 `start_intent_review()` を1回だけ実行した。233.419秒でHTTP 200、2,508 response bytes、transport call 1、Bonsai利用量 `succeeded` となり、sessionは `intent_review`、typed proposalは `blocking`、reviewは `BlockingIntentReview`、query planとquery digestはどちらも存在しなかった。
- 2件目、同一case retry、dataset report・assessment、Cloudflare・Outscraperの予約・call、商品取得、rankingは実行していない。server停止後にport非listen、対象process不在、一時runnerと一時directory不在を確認した。

この結果は、local modelの実応答がstrict intentとtyped proposalを通り、query-less blockingとしてproduction相当のoffline orchestration第1確認へ安全に到達したことを示す。検索文、生response、正規化intent、typed condition、ambiguity・issue本文を保持していないため、blockingの直接理由と判断の妥当性は示さない。検索成功、商品順位、独立holdout、production E2Eの証拠でもない。

### 固定artifact

| 対象 | SHA-256または値 |
|---|---|
| CSV | `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea` |
| Bonsai model | `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54` |
| llama-server binary | `71b0c2554c375071855547f5da7ef2fc5c34766f6fcd6fab194ce93a18a59e0a` |
| prompt | `459f4a7bc3ecbb93664b4973b00cec31de4665a5cd61762bf84c6ad51779859d` |
| 完全schema | `f6650c439794aface4d3b2b98227c32d8123ea9349db2ca3ad82dab7eedfb88c` |
| 生成schema | `2e5cfed749d4f71898c42226c58e3f838664cac0e66f1c3230e54daf384f004d` |
| canonical body | `5754a3b00ca2be0fe909a1d3fb9079ddbfa45729c9a3d692f44b172e7744a6b6` |
| request | `9701a1d930dfe6c7b5971fb03a76587dcb7fa57a293f47175cbb70438f237f1e` |
| orchestrator | `aedf45afe023502424ba84d635cf8e654480b83bf0b1b122fdd709c215f4bfe9` |
| 一時runner | `c9547f7c9f5b180d9bc396d501d7676dcffa52e11ec77d486c2f2a549a85c9a9`。実行後に削除済み |

### 検証

| 検証 | 期待 | 結果 |
|---|---|---|
| 関連offline回帰 | Bonsai adapter・request・HTTP、typed adapter、query planner、orchestrator、state、holdout後処理が成功する | 195 passed |
| 標準offline gate | lock、Ruff、Markdown、offline pytest、Python 3.10 AST、`git diff --check` が成功する | lock 79 packages、Ruff 195 files、Markdown 16 files・1,266 links・865 anchors・1,580 headings・199 fence pairs、pytest 1,648 passed・9 skipped・1 deselected、AST 195 files、diff成功 |

### セキュリティ・データ・互換性

一時runnerはcanonical request digestを送信直前に再検証し、transport callを1回に固定する。server log、prompt cache、UIを無効化し、loopbackだけへbindする。保存するのは固定artifactのdigest、経過時間、response byte数・token数、固定diagnostic、確認型、proposal status、query有無、利用量状態だけとし、検索文、生response、intent内容、typed condition、ambiguity messageを保存しない。SHA-256は匿名化として扱わない。

現行source、schema、prompt、CSV、modelは変更しない。結果は同一caseに対する結合回帰には使えるが、独立holdout、未知データへの一般化、条件分解・商品順位の品質、production E2Eを証明しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-05 | 未知データによる独立評価を実施しない | 利用者の明示判断 | 品質合格とは扱わず、ranking品質未確認と画像ranking無効を維持する。再開には利用者の新しい明示判断と、既存development dataを除外した固定policy適格dataが必要 |

### 停止・ロールバック

digest、request field、call guard、port・process状態が一致しなければ送信前に停止する。送信開始後はtimeoutや自動retryを設けず、応答、接続・OS失敗、server context境界、EOS、または人間の手動停止を結果とする。終了後は一時runnerとserver processを削除し、source codeと固定artifactを変更しない。

## EXEC-054: query-less blockingの第1確認接続

### メタデータ

- 状態: 完了
- 作成日: 2026-09-05
- 最終更新: 2026-09-05
- 前提Plan: [EXEC-053](#exec-053-生成時検索可能性schemaのlocalhost-1件確認)
- 関連要件: [TASK-008](#task-008-次期検索フロー-v2-の実装)、[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

Bonsaiのstrict intentからtyped proposalが `blocking` になった場合、検索queryを要求せずに利用者の第1確認へ返す。blocking確認中は画像生成、検索承認、Cloudflare、Outscraper、商品正規化、rankingへ進めず、利用者が条件を修正するまで安全に停止できるoffline backend境界を作る。

### 対象範囲

- 対象: `src/search_v2/orchestrator.py` のproposal・query構築順序と第1確認contract
- 対象: `src/search_v2/state_machine.py` のblocking sessionにおけるquery digest不在のcanonical契約
- 対象: ready proposalでは従来どおりquery planとdigestを必須にする相互制約
- 対象: blocking reviewから画像・検索承認へ進めないこと、追加provider予約・callが発生しないことのoffline test
- 対象: query付きblocking、queryなしready、digest改ざん、型違い、非canonical状態のfail-closed拒否
- 対象外: 追加Bonsai model call、使用済みCSVの再評価、独立holdout、Cloudflare・Outscraper実通信、商品取得・ranking品質、画像、Windows native、API・UI、外部委託中フロントエンド、AIレビューハーネス

### 現在の状態

EXEC-053の承認済み1 callは生成schema、完全draft schema、正規化、typed proposal生成まで成功し、proposal status `blocking` を返した。検索文、生response、正規化intent、proposal本文を保存していないためblocking理由は断定しない。

現行 `start_intent_review()` は `build_search_query_plan()` を `build_typed_requirement_proposal()` より先に呼ぶ。`SearchSessionSnapshot` はintent・query・proposal digestの同時存在を要求し、`IntentReview` も常に `SearchQueryPlan` を要求する。このため、商品種別を安全に確定できず全blocking ambiguityを返す正当なintentはquery plannerで停止し、第1確認へ到達できない。一方、state machineの承認処理はproposal statusが `ready` でなければ拒否するため、blockingから後段へ進ませないguard自体は存在する。

### 実装方針

1. 合成したquery-less blocking応答とsession相互制約をtestへ追加し、現行のquery先行処理またはquery必須契約が原因でREDになることを確認する。
2. typed proposalをquery planより先に構築する。`ready` の場合だけqueryを構築し、`blocking` はqueryを持たない専用の第1確認contractとして返す。
3. sessionではintent digest・proposal digest・proposal statusを常に結び、query digestは `ready` で必須、`blocking` で禁止する。query付きblockingとqueryなしreadyを拒否する。
4. 既存のready `IntentReview`、画像経路、検索承認、Outscraper、rankingのquery必須形を変更しない。blocking reviewを後段関数へ渡した場合は、provider予約またはtransport callより前に固定orchestration errorで拒否する。
5. focused test、state・typed・後段関連回帰、標準offline gateを実行し、要件、backend、security、testing、issue、残作業、履歴を同期する。

### 受入条件

1. query語を持たずblocking ambiguityを持つstrict intentが、Bonsai call 1回の後に第1確認として返る。
2. blocking確認はintent・proposal・Bonsai request・成功済み利用量へ結ばれ、query planとquery digestを持たない。
3. ready確認は従来どおりquery planとquery digestを必須とし、既存digestとschema 3.0のready payloadを維持する。
4. blocking確認から画像生成、画像なし続行、検索承認、Outscraperへ進めず、Cloudflare・Outscraperのreservationとtransport callが0件である。
5. query付きblocking、queryなしready、status・digest・artifact改ざん、型違い、非canonical順序を安全な固定errorで拒否する。
6. source input、生response、ambiguity message、商品情報、provider error本文を新しいsession bindingまたは固定errorへ複製しない。

### 進捗

- [x] 2026-09-05: 現行orchestrator、state、既存blocking testとEXEC-053結果を再確認した
- [x] 2026-09-05: 対象、対象外、canonicalなready・blocking形、TDD順序を固定した
- [x] 2026-09-05: 受入testを追加し、対象理由のREDとtest SHA-256を記録した
- [x] 2026-09-05: 最小実装でGREENにし、後段provider非呼出しと改ざん拒否を確認した
- [x] 2026-09-05: focused 39件と関連回帰235件を完了した
- [x] 2026-09-05: 正本文書、履歴、次の再開位置を同期し、標準offline gateを完了した

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | query-less blockingのorchestrator・state受入test | query先行またはquery必須という対象理由で失敗 | 3 failed・1 passed。orchestrator 2件は `build_search_query_plan()` のblocking拒否、state 1件は `SearchQueryPlan.model_validate(None)` による対象理由で失敗。test SHA-256はorchestrator `1280510f64e2412c299cf7a83547213c62b8fe4e408a357eb9bc467ff42684f2`、state `a62e710622c67a1f0c565dc2db433a9010171d891bae09bb0e0bdcc8be5c3947` |
| focused GREEN | `tests/test_search_v2_orchestrator.py`、`tests/test_search_v2_state_machine.py` | 全件成功 | 39 passed。新規受入4件だけでも4 passed |
| 関連回帰 | typed adapter、query planner、approval、Cloudflare・Outscraper request・HTTP、product pipeline、history、holdout後処理 | 全件成功 | 235 passed |
| 標準gate | lock、Ruff、Markdown、offline pytest、Python 3.10文法、差分形式 | 全件成功 | lock 79 packages、Ruff 195 files、Markdown 16 files・1,256 links・855 anchors・1,565 headings・199 fence pairs、pytest 1,648 passed・9 skipped・1 deselected、AST 195 files、diff成功 |

### セキュリティ・データ・互換性

新しい外部通信、credential、課金、file reader、callback、動的importは追加しない。testは合成strict response、注入transport、in-memory ledgerだけを使う。blockingではqueryを生成・保存せず、query digestも持たせない。readyのquery、approval plan、provider request、ranking、history bindingは従来の必須形を維持する。

ready用 `IntentReview` のfieldとschema 3.0 payloadは変更しない。blockingにはquery fieldを持たない専用contractを追加し、`start_intent_review()` の戻り値をその安全な確認variantへ広げる。`SearchSessionSnapshot.query_plan_sha256` は既存のnullable fieldを使うが、nullを許すのは `state=intent_review` かつproposal status `blocking` の組合せだけとする。queryを持つ従来のblocking形は未接続・未永続のoffline contractであり、新しいcanonical形へ暗黙変換せず拒否する。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-05 | blocking専用の第1確認contractを追加し、ready `IntentReview` はquery必須のまま維持する | Optional queryを全後段へ広げず、安全停止形と実行可能形を型で分けるため | API・UI接続時に共通表示modelが必要なら、秘密情報を除いた別の表示projectionを設計する |
| 2026-09-05 | proposalをqueryより先に確定する | blocking時にはqueryを作る必要がなく、query planner自体もblocking ambiguityを拒否するため | proposal生成が失敗する場合は従来どおり固定失敗とし、query fallbackを作らない |

### 発見事項

- 現行testには検索可能なfieldを持つunknown typed conditionのblocking確認はあるが、商品種別・検索語を持たないblocking responseを `start_intent_review()` へ通す回帰testはない。
- holdout後処理にはproposalを先に作り、blockingならquery作成を省略するoffline実装がある。orchestratorも同じ順序へ揃えたため、評価投影と本番相当offline確認stateでblockingのartifact形が一致した。

### ロールバック

本Planで追加するblocking確認contract、session相互制約、orchestrator分岐、受入test、同期文書だけを取り除けばEXEC-053完了時点へ戻る。外部状態、credential、database、cache、model、画像assetを作成・変更しないため、データrollbackは不要である。

### 結果

完了。`start_intent_review()` はBonsaiのstrict intentからtyped proposalを先に構築し、`ready` の場合だけ従来のquery planを作る。`blocking` はquery fieldを持たない専用 `BlockingIntentReview` と、intent・proposal digestおよび成功済みBonsai利用量だけへ結んだquery-less `intent_review` snapshotを返す。snapshotはquery付きblockingとqueryなしreadyを拒否し、ready用 `IntentReview`、approval、画像、Outscraper、rankingのquery必須形は変更していない。

blocking確認を `generate_images()` または `skip_images()` へ渡すと、Cloudflare・Outscraperの予約・transport callより前に固定 `SearchOrchestrationError` で停止する。これにより画像なし続行から検索承認へ到達する経路も作れず、blocking状態のまま利用者修正を待つ。source input、生response、ambiguity message、商品情報、provider error本文をsessionまたはerrorへ追加していない。

最終SHA-256は `src/search_v2/orchestrator.py` が `aedf45afe023502424ba84d635cf8e654480b83bf0b1b122fdd709c215f4bfe9`、`src/search_v2/state_machine.py` が `73a211cd4a9432b533f7e91fa766cfdfa28f069007d1e8352c14c73b78559e81`、RED兼最終testはorchestratorが `1280510f64e2412c299cf7a83547213c62b8fe4e408a357eb9bc467ff42684f2`、stateが `a62e710622c67a1f0c565dc2db433a9010171d891bae09bb0e0bdcc8be5c3947` である。新規受入4件、focused 39件、関連235件が成功した。標準gateはlock 79 packages、Ruff 195 files、Markdown 16 files・1,256 links・855 anchors・1,565 headings・199 fence pairs、offline pytest 1,648 passed・9 skipped・1 deselected、Python 3.10 AST 195 files、`git diff --check` 成功である。

実Bonsaiの追加call、使用済みCSVの再評価、未知データ、Cloudflare、Outscraper、Amazon、OpenAI、credential、課金、画像、Windows native、browser、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・変更していない。次の再開位置は、case1〜case3と使用済みCSVを除外した未知データで独立評価を行うかどうかの判断である。実施する場合だけ、固定済みpolicyを満たす新しい非機密dataを利用者側で用意する。

## EXEC-053: 生成時検索可能性schemaのlocalhost 1件確認

### メタデータ

- 状態: 完了（承認済み1 call・blocking proposal確認）
- 作成日: 2026-09-05
- 最終更新: 2026-09-05
- 前提Plan: [EXEC-052](#exec-052-新生成schemaのlocalhost-1件確認)
- 関連要件: [TASK-005](#task-005-ランキング品質評価の確立)、[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

EXEC-052後にoffline実装した、通常経路の商品種別または全blocking確認待ちを生成時に強制するschemaを、使用済みCSVの先頭1 case・合計1 callだけで確認する。これはdevelopment regressionであり、独立holdout、dataset assessment、typed ranking品質、production E2Eとして扱わない。

### 実行承認と固定範囲

利用者へ、`http://127.0.0.1:18080/v1/chat/completions`、固定Bonsai model、更新prompt、完全schema、未送信の生成時検索可能性schema、使用済みCSVの先頭1件だけを含むpayload、合計1 call、retry 0、application生成token上限・HTTP timeoutなし、response 1 MiB、credential・費用・外部networkなし、本文非保持を提示し、新しい明示承認を得た。

- 対象: `mouse-01` 1 case、localhost Bonsai 1 call、retry 0
- 対象: strict response、正規化、検索可能性、typed proposalへ到達する範囲の安全な段階診断
- 対象外: 2件目、同一case再試行、dataset report・assessment、商品取得・ranking、画像、実外部service、フロントエンド
- 保存しないもの: 検索文、生response、正規化intent、商品情報、URL、ASIN相当値、provider error、validation本文
- 結果にかかわらず2件目や同一caseを自動送信せず、追加model callには別の明示承認を必要とする

### 受入条件

1. model、CSV、prompt、完全schema、生成schema、canonical body・request digest、`max_tokens`・timeout不在、port非listenを送信前に固定する。
2. serverをloopbackだけへbindし、`/health=200` 後にexact requestを1回だけ送る。
3. 成否は固定stage・group、finish reason、completion token件数、response byte数、所要時間、transport call数だけで記録する。
4. 1件だけなのでdataset report・assessmentを作らず、失敗時もretryしない。
5. 終了後にserver、port、一時runnerを確実に片付ける。
6. 必要な修正は追加model callなしのoffline作業とし、同じ承認で再送しない。

### 進捗

- [x] 2026-09-05: 新しい明示承認を受領した
- [x] 2026-09-05: 固定artifact、canonical request、token・timeout不在、停止状態を本文非表示で再検証した
- [x] 2026-09-05: `/health=200` 後に先頭1件を1回だけ送った
- [x] 2026-09-05: 安全な結果を記録し、serverと一時runnerを削除した
- [x] 2026-09-05: focused・関連回帰を完了した
- [x] 2026-09-05: 標準文書同期後のoffline gateを完了した

### 送信前検査

| 対象 | 固定値・結果 |
|---|---|
| model | SHA-256 `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54` |
| CSV | SHA-256 `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea`、先頭case `mouse-01` |
| prompt | SHA-256 `459f4a7bc3ecbb93664b4973b00cec31de4665a5cd61762bf84c6ad51779859d` |
| 完全schema | 7,352 bytes、SHA-256 `f6650c439794aface4d3b2b98227c32d8123ea9349db2ca3ad82dab7eedfb88c` |
| 生成schema | 16,663 bytes、SHA-256 `2e5cfed749d4f71898c42226c58e3f838664cac0e66f1c3230e54daf384f004d` |
| canonical body | 29,320 bytes、SHA-256 `5754a3b00ca2be0fe909a1d3fb9079ddbfa45729c9a3d692f44b172e7744a6b6` |
| request | schema 5.0、SHA-256 `9701a1d930dfe6c7b5971fb03a76587dcb7fa57a293f47175cbb70438f237f1e` |
| runner | SHA-256 `196639692c05b0b6e80fd4126562af53e1041fd0d7564ee9d76b9ef020abbf57`、preflight transport call 0 |
| 制限・状態 | `max_tokens` なし、timeoutなし、port 18080非listen、`llama-server` processなし |

### 実行結果と検証

| 対象 | 方法 | 実結果 | 分かること |
|---|---|---|---|
| localhost 1 call | `/health=200` 後に固定requestを1回だけ送信 | HTTP 200、`finish_reason=stop`、473 completion tokens、2,508 response bytes、395.713秒、transport call 1、retry 0、usage `succeeded` | 生成schema、envelope、content JSON、完全draft schema、正規化、adapter受理を通過した |
| typed proposal | 受理済みintentを固定registryのadapterへ渡す | proposal status `blocking`、response stage・draft group・searchability groupは全て `not_applicable` | typed proposal自体は生成できたが、検索・rankingへ進めず利用者確認が必要な状態である。本文非保持のためblocking理由は断定しない |
| 実行数・後処理 | call guard、usage、assessment、server、socket、process、一時runnerを確認 | transport call 1、retry 0、assessmentなし、port 18080非listen、`llama-server` processなし、EXEC-053 runner・bytecodeなし | 承認済み1 call以外の送信はなく、local実行資源を残していない |
| focused regression | Bonsai adapter・request | 87 passed | 現行schema、strict受理、固定diagnostic契約を維持した |
| 関連回帰 | Bonsai HTTP、query planner、holdout postprocess、typed adapter、orchestrator、history | 187 passed | 実行後にcodeを変更せず、関連offline契約が成功した |
| 標準offline gate | lock、Ruff、Markdown、offline pytest、Python 3.10文法、差分形式 | lock 79 packages、Ruff 195 files、Markdown 16 files・1,241 links・840 anchors・1,549 headings・199 fence pairs、pytest 1,644 passed・9 skipped・1 deselected、AST 195 files、diff成功 | 追加model call・依存取得・外部通信なしで最終treeの整合を確認した |

### 判断と結果

目的とした未送信schemaの1件確認は完了した。今回の応答はschema・normalizer・adapterで拒否されず、typed proposalまで生成できたため、EXEC-052の `intent_searchability_invalid` はこの固定caseでは再現しなかった。一方、proposalは `blocking` であり、商品取得・rankingへ進める `ready` ではない。1件の使用済みdataであるため、条件分解の意味精度、blocking判断の妥当性、未知データへの一般化、商品順位の品質は評価しない。

検索文、生response、正規化intent、typed condition、ambiguity、issue本文を保存していないため、blockingが上流ambiguity、未知attribute、値・演算子不整合等のどれに由来したかは断定しない。追加model callで原因を探らない。EXEC-053時点の `start_intent_review()` はquery planをtyped proposalより先に要求し、query-less blockingを `IntentReview` として表現できないことをsourceで再確認した。この不足は後続のEXEC-054で、確認待ちを商品取得前の専用第1確認へ安全に返すoffline設計として解消した。

この実行ではsource code、prompt、schemaを変更していない。Cloudflare、Outscraper、Amazon、OpenAI、画像、credential、課金、外部network、browser、Windows native、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・変更していない。

### 停止・ロールバック

送信前のdigest、schema、port、process、call guardが一致しなければmodelを呼ばず停止する。送信開始後は自動retryせず、応答、接続・OS失敗、server context境界、EOS、または人間の手動停止を最終結果として記録する。作業後は一時runnerとserverを削除し、実装変更が不要ならEXEC-052後のcodeを維持する。

## EXEC-052: 新生成schemaのlocalhost 1件確認

### メタデータ

- 状態: 完了（承認済み1 call・offline改善）
- 作成日: 2026-09-05
- 最終更新: 2026-09-05
- 前提Plan: [EXEC-051](#exec-051-bonsai生成schema整合とdraft診断)
- 関連要件: [TASK-005](#task-005-ランキング品質評価の確立)、[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

EXEC-051で互換regex、価格mode・source別9 variant、本文非保持のdraft違反groupを追加した生成schemaを、使用済みCSVの先頭1 case・合計1 callだけで確認する。これはdevelopment regressionであり、独立holdout、dataset assessment、typed ranking品質、production E2Eとして扱わない。

### 実行承認と固定範囲

利用者へ、`http://127.0.0.1:18080/v1/chat/completions`、固定Bonsai model、更新prompt、完全schema、新生成schema、使用済みCSVの先頭1件だけを含むpayload、合計1 call、retry 0、application生成token上限・HTTP timeoutなし、response 1 MiB、credential・費用・外部networkなし、本文非保持を提示し、新しい明示承認を得た。

- 対象: `mouse-01` 1 case、localhost Bonsai 1 call、retry 0
- 対象: strict response、正規化、検索可能性、typed proposalへ到達する範囲の安全な段階診断
- 対象外: 2件目、同一case再試行、dataset report・assessment、商品取得・ranking、画像、実外部service、フロントエンド
- 保存しないもの: 検索文、生response、正規化intent、商品情報、URL、ASIN相当値、provider error、validation本文
- 結果にかかわらず2件目や同一caseを自動送信せず、追加model callには別の明示承認を必要とする

### 受入条件

1. model、CSV、prompt、完全schema、新生成schema、canonical body・request digest、`max_tokens`・timeout不在、port非listenを送信前に固定する。
2. serverをloopbackだけへbindし、`/health=200` 後にexact requestを1回だけ送る。
3. 成否は固定stage、固定draft group、finish reason、completion token件数、response byte数、所要時間、transport call数だけで記録する。
4. 1件だけなのでdataset report・assessmentを作らず、失敗時もretryしない。
5. 終了後にserver、port、一時runnerを確実に片付ける。
6. 必要な修正は追加model callなしのoffline TDDとし、同じ承認で再送しない。

### 送信前検査

| 対象 | 固定値・結果 |
|---|---|
| model | SHA-256 `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54` |
| CSV | SHA-256 `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea`、先頭case `mouse-01` |
| prompt | SHA-256 `9477fcc8c4a846a9c6f87ae8410371f8a57f68a7f6dc2599ef015d084561a150` |
| 完全schema | 7,352 bytes、SHA-256 `f6650c439794aface4d3b2b98227c32d8123ea9349db2ca3ad82dab7eedfb88c` |
| 新生成schema | 11,051 bytes、SHA-256 `c8537ff3ee378b0ef57d41889210e1a807962d2cbd1ab8772020706481a58ca6` |
| canonical body | 23,725 bytes、SHA-256 `4d2d6e5b3abc59f996a74d0b40f80c14e731a8e77acbaa8410323913cd20bc2b` |
| request | schema 5.0、SHA-256 `6bdaa64071b867d421a2c07830d1fb4c1c675e23ff7f4825a24fe7014edb29c8` |
| 制限・状態 | `max_tokens` なし、timeoutなし、port 18080非listen、`llama-server` processなし |

### 進捗

- [x] 2026-09-05: 新しい明示承認を受領した
- [x] 2026-09-05: 固定artifact、canonical request、token・timeout不在、停止状態を本文非表示で再検証した
- [x] 2026-09-05: `/health=200` 後に先頭1件を1回だけ送った
- [x] 2026-09-05: 安全な結果を記録し、serverと一時runnerを削除した
- [x] 2026-09-05: 生成時検索可能性制約と安全な検索可能性groupをREDからoffline実装した
- [x] 2026-09-05: focused・関連回帰とschema converter検査を完了した
- [x] 2026-09-05: 文書同期後の標準offline gateを完了した

### 実行結果と検証

| 対象 | 方法 | 実結果 | 分かること |
|---|---|---|---|
| runner preflight | SHA-256 `ec2c98747d7d117884d4a2488c861074a54769b291f709718ca5e3f067be4dab` の一時runnerを送信なしで検査 | 最初はrepository import path不足で停止。`PYTHONPATH` をrepository直下へ固定すると全digest一致、transport call 0 | 最初の停止はmodel・provider・schemaの失敗ではなく、requestは送っていない |
| localhost 1 call | `/health=200` 後に固定requestを1回だけ送信 | HTTP 200、`finish_reason=stop`、143 completion tokens、1,187 response bytes、252.845秒、transport call 1、retry 0、`intent_searchability_invalid` | 新生成schema、envelope、content JSON、完全draft schema、正規化を通過し、非blocking query構築で停止した。typed proposal・rankingには到達していない |
| 後処理 | server、socket、process、一時runnerを確認 | port 18080非listen、`llama-server` processなし、EXEC-052 runner・bytecodeなし、assessmentなし | 承認済みmodel callは合計1回で、追加送信やlocal実行資源は残っていない |
| offline RED | 生成時の安全な商品種別・blocking分岐と検索可能性groupを要求 | 11 failed、76 passed | schema分岐、prompt規則、diagnostic fieldが未実装という対象理由で失敗した |
| offline GREEN | Bonsai adapter・requestの全test | 87 passed | 通常商品、検索語なし拒否、blocking確認待ち、非blocking ambiguity拒否、固定groupを確認した |
| 関連回帰 | HTTP、query planner、holdout postprocess、typed adapter、orchestrator、history | 187 passed | strict受理と後段bindingの既存offline契約を維持した |
| schema互換 | llama.cpp同梱Python converterとDraft 2020-12 validator | 16,663 bytes、SHA-256 `2e5cfed749d4f71898c42226c58e3f838664cac0e66f1c3230e54daf384f004d`、converter終了0、schema valid | 次の生成schemaはconverterで表現できる。実model成功はまだ示さない |
| 標準offline gate | lock、Ruff、Markdown、offline pytest、Python 3.10構文、差分形式 | lock 79 packages、Ruff 195 files、Markdown 16 files・1,231 links・830 anchors・1,536 headings・199 fence pairs、pytest 1,644 passed・9 skipped・1 deselected、AST 195 files、diff成功 | 追加model call・依存取得・外部通信なしで最終treeの整合を確認した |

### 判断と結果

今回の `intent_searchability_invalid` は、完全draft schemaと正規化後の非blocking intentからqueryを作れなかったことを示す。生responseを保持していないため、検索fieldが全て空だったか、URL等の不正値があったかは断定しない。実行時点のdiagnosticにもその内訳はなかったため、過去responseを事後分類しない。

追加model callなしで、生成schemaを2分岐にした。通常経路は `product_name_ja` に日本語の商品種別を必須とし、商品種別を安全に確定できない経路は1件以上のambiguityを全てblockingにする。これにより商品カテゴリを限定せず、曖昧な商品種別を捏造して検索へ進めない。完全schemaとquery plannerは最終権威のまま維持する。検索可能性で失敗した場合は、正規化済み値を保持せず `missing_terms` または `invalid_terms` の固定groupだけを返す。

次schemaは16,663 bytes、SHA-256 `2e5cfed749d4f71898c42226c58e3f838664cac0e66f1c3230e54daf384f004d` である。更新promptはSHA-256 `459f4a7bc3ecbb93664b4973b00cec31de4665a5cd61762bf84c6ad51779859d`、同じ先頭caseの次canonical bodyは29,320 bytes・SHA-256 `5754a3b00ca2be0fe909a1d3fb9079ddbfa45729c9a3d692f44b172e7744a6b6`、requestはSHA-256 `9701a1d930dfe6c7b5971fb03a76587dcb7fa57a293f47175cbb70438f237f1e` となる。このEXEC-052完了時点では未送信であり、後続のEXEC-053で条件を再提示した別の明示承認後に1回だけ送信した。

最終SHA-256は `src/search_v2/bonsai_adapter.py` が `dccfed18908cda7fe0b839f9ae193431bad2ae20d27947163edce32cf29c6b57`、`src/search_v2/bonsai_request.py` が `4b88031a760b1d87efd2b851d249720c25d83c846ba468364621bf0a085d32ef`、RED兼最終 `tests/test_search_v2_bonsai_adapter.py` が `b9af88eeb92c888eb392c4afea7202a37bd819141ac100f219557ae09df30347`、最終 `tests/test_search_v2_bonsai_request.py` が `b212a9aea188b32f6ab4856a185789f0ea35b1a35feed74743a04f4d1cac7ecd` である。

検索文、生response、正規化intent、商品情報、URL、ASIN相当値、provider error、validation本文は保存・転記していない。Cloudflare、Outscraper、Amazon、OpenAI、画像、credential、課金、外部network、browser、Windows native、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・変更していない。

## EXEC-051: Bonsai生成schema整合とdraft診断

### メタデータ

- 状態: 完了（承認済み1 call・offline改善）
- 作成日: 2026-09-05
- 最終更新: 2026-09-05
- 前提Plan: [EXEC-050](#exec-050-bonsai検索可能性失敗段階の分離)
- 関連要件: [TASK-005](#task-005-ランキング品質評価の確立)、[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

EXEC-050で分離した原因別stageを、使用済みCSVの先頭1 case・合計1 callだけで確認する。より前のstrict draft schemaで停止した場合は追加推論をせず、生成用schemaと完全schemaの既知の差を閉じ、次回に本文や値を残さず違反領域を判別できるようにする。

### 対象範囲

- 対象: `mouse-01` 1 case、localhost Bonsai 1 call、retry 0
- 対象: 生成用schemaのregex互換化、価格field横断条件、本文非保持のdraft違反group
- 対象: 合成responseによるRED、llama.cpp同梱converter、focused・関連回帰、標準offline gate
- 対象外: 2件目、同一case再試行、dataset report・assessment、商品取得・ranking、実サービス、画像、フロントエンド
- 対象外: Cloudflare、Outscraper、Amazon、OpenAI、credential、課金、外部network、browser、Windows native、AIレビューハーネス、commit、push

### 実行承認と固定条件

利用者へ、`http://127.0.0.1:18080/v1/chat/completions`、固定model・使用済みCSV先頭1件、合計1 call、retry 0、application生成token上限・HTTP timeoutなし、response 1 MiB、credential・費用・外部networkなし、検索文・生response・正規化intent・商品情報を保存しない条件を再提示し、明示承認を得た。結果にかかわらず2件目または同一caseを送らず、1件だけなのでdataset assessmentを作らない条件も固定した。

### 実行順序と進捗

- [x] 2026-09-05: model、CSV、prompt、生成schema、body、request、token・timeout不在、port非listenを送信前に確認した
- [x] 2026-09-05: 手入力された旧body・request digest不一致でpreflightを停止し、transport call 0のままcanonical builderの値へ訂正した
- [x] 2026-09-05: `/health=200` 後、先頭 `mouse-01` だけを1回送った
- [x] 2026-09-05: HTTP 200の応答を受けたが、`draft_schema_invalid` で安全に拒否された
- [x] 2026-09-05: 2件目・再試行・assessmentを行わず、server停止、port非listen、process終了、一時runner削除を確認した
- [x] 2026-09-05: 既知の生成schema差分と安全なdraft違反groupをREDからoffline実装した
- [x] 2026-09-05: 同梱converter、JSON Schema、focused・関連回帰を実行した
- [x] 2026-09-05: 文書同期後の標準offline gateを実行した

### 検証

| 対象 | 方法 | 実結果 | 分かること |
|---|---|---|---|
| 送信前検査 | 固定artifactとrequestを本文非表示で再検証 | model `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54`、CSV `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea`、prompt `9477fcc8c4a846a9c6f87ae8410371f8a57f68a7f6dc2599ef015d084561a150`、旧生成schema `f557081591fa9d322364e8b65ac0583ee78a0359cd7e1721b659491e1e2fa865`、body 19,877 bytes、`max_tokens`・timeout不在 | 承認済みの固定条件と先頭caseを送信対象にした |
| preflight停止と訂正 | 手入力digestをcanonical builderへ照合 | 旧記録由来のbody・request digestが不一致で停止、transport call 0。正しいbodyは `eb44d062f665ffb37dbec1c8f5a2ecd41ee491557a156002fab75ab616639588`、requestは `be5bda07d09c87a371fc1cd77b0cb5680045a447c29e887a225fa77ce791e0aa` | model失敗ではなく送信前固定値の誤りであり、不一致requestは送っていない |
| localhost 1 call | `/health=200` 後に先頭caseだけを送信 | HTTP 200、`finish_reason=stop`、257 completion tokens、1,613 response bytes、117.242秒、transport call 1、`draft_schema_invalid` | envelopeとJSONまでは通ったが、完全なdraft schema検証で停止した。正規化・検索可能性・rankingには到達していない |
| RED | 生成schema整合とdraft違反groupを先に要求 | 10 failed | patternが除外され、価格field横断条件と違反groupが未実装という対象理由で失敗した |
| focused GREEN | Bonsai adapter・requestの全test | 85 passed | strict parserを緩めず、互換regex、9価格variant、安全な違反groupを固定した |
| 関連回帰 | HTTP、query planner、holdout postprocess、typed adapter、orchestrator、history | 185 passed | request・後段bindingとのoffline互換性を維持した |
| schema互換 | 同梱Python converterとDraft 2020-12 validator | converter終了0、正fixture 0 errors、価格矛盾・不正decimal・不正ambiguity codeは各1 error | 新生成schemaは既知のstrict差分を生成段階で拒否できる。実model成功はまだ示さない |
| 標準offline gate | lock、Ruff、Markdown、offline pytest、Python 3.10構文、差分形式 | lock 79 packages、Ruff 195 files、Markdown 16 files・1,221 links・820 anchors・1,524 headings・199 fence pairs、pytest 1,642 passed・9 skipped・1 deselected、AST 195 files、diff成功 | 追加model call・依存取得・外部通信なしで最終treeの整合を確認した |

### セキュリティ・データ境界

実行結果には検索文、生response、正規化intent、商品情報、URL、ASIN相当値、provider error、内部validation本文を残していない。追加した `draft_failure_group` は `document`、`fields`、`price`、`typed_conditions`、`ambiguities`、`multiple` と非draft用 `not_applicable` の固定値だけを持ち、field値やvalidation messageを保持しない。今回の実行はgroup追加前なので、保存済みstageから直接違反groupを復元・断定しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-05 | 実行は旧生成schemaの1 callで終了し、新schemaを同じ承認で再送しない | 利用者指定が合計1 callであり、結果にかかわらず再試行しない条件だったため | 新生成schemaの実model確認には同じcaseでも新しい明示承認が必要 |
| 2026-09-05 | 完全schemaのregexを捨てず、decimalだけ同値のconverter互換表現へ書き換える | ambiguity codeを含む既知patternを生成段階でも強制し、application受理条件との距離を縮めるため | schema変更時は未知patternを固定request errorとして見つける |
| 2026-09-05 | 価格をmode・source別の9 variantへする | Pydanticのfield横断validatorは通常のmodel schemaへ自動反映されず、生成schemaだけを満たす矛盾を許していたため | range大小関係と全体byte上限は完全schemaの最終検証を維持する |

### 結果

承認済みの先頭1件を合計1 callだけ実行した。応答は完了したが `draft_schema_invalid` で停止し、EXEC-050で分離した正規化・検索可能性stageには到達しなかった。生responseを保持しないため、今回の直接違反fieldは断定しない。

追加model callなしで生成schemaを11,051 bytes、SHA-256 `c8537ff3ee378b0ef57d41889210e1a807962d2cbd1ab8772020706481a58ca6` へ更新した。ambiguity codeのpatternを保持し、decimalは同じ受理言語を持つconverter互換regexへ置換し、価格はexact・range・min・maxのexplicit/inferredとnoneを9つの排他的variantへ固定した。完全schemaによる最終検証、request schema 5.0、application生成token上限なし、HTTP timeoutなし、response 1 MiB、1 call、retry 0は維持する。

最終SHA-256は `src/search_v2/bonsai_adapter.py` が `2a0284b6bb2f30c0c740aded2535008ec901472c8a9e0e75ce004da48768eff4`、`src/search_v2/bonsai_request.py` が `87244ec4c124a94e04051a322f299d9cc63e3eea32f98cc1eac0f731716c875b`、`tests/test_search_v2_bonsai_adapter.py` が `484e102949cc119cafb975d8572c0d7abd7a6d3d0c84b854dd798962f67856b0`、`tests/test_search_v2_bonsai_request.py` が `b6a68fbbde05327a4113cc39a678162eb73e548edba495db4ff118a9e2dc9e4c` である。

次は、新しい生成schemaで同じ先頭caseを1 callだけ確認する場合、endpoint、payload、回数、保存範囲を再提示して新しい明示承認を得る。新しいCSV、画像、APIキーは不要である。未知データの独立評価は別工程とする。


## EXEC-050: Bonsai検索可能性失敗段階の分離

### メタデータ

- 状態: 完了（承認済み1 call・offline診断）
- 作成日: 2026-09-05
- 最終更新: 2026-09-05
- 前提Plan: [EXEC-049](#exec-049-bonsai-intent検索可能性contract)
- 関連要件: [TASK-005](#task-005-ランキング品質評価の確立)、[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

EXEC-049の更新promptと検索可能性contractを、利用者が指定した全体1 case・1 callだけで確認する。安全なstageだけでは原因を分けられなかった場合は追加推論を行わず、正規化失敗と検索不能を本文非保持の別stageへ分離する。

### 対象範囲

- 対象: 使用済みCSVの先頭1 case、localhost Bonsai 1 call、retry 0
- 対象: `bonsai_adapter.py` の正規化失敗と検索可能性失敗の安全な分類
- 対象: 合成responseによるRED、focused・関連回帰、標準offline gate
- 対象外: 2件目、同一caseの再試行、dataset全体のreport・assessment、prompt・schema・model・ranking profile・labelの変更
- 対象外: Cloudflare、Outscraper、Amazon、OpenAI、画像、credential、課金、外部network、browser、Windows native、外部委託中フロントエンド、commit、push

### 実行承認と固定条件

利用者へ、`http://127.0.0.1:18080/v1/chat/completions`、固定model・使用済みCSV先頭1件、合計1 call、retry 0、application生成token上限・HTTP timeoutなし、response 1 MiB、credential・費用・外部networkなし、検索文・生response・正規化intent・商品情報を保存しない条件を提示し、明示承認を得た。結果にかかわらず2件目または同一caseを送らず、1件だけなのでdataset assessmentを作らない条件も固定した。

### 実行順序と進捗

- [x] 2026-09-05: model、CSV、prompt、完全schema、生成schema、body、request、token・timeout不在、port非listenを送信前に確認した
- [x] 2026-09-05: 一時runnerの最初のpreflightでrepository import path不足を検出し、model call前に停止した
- [x] 2026-09-05: import pathだけを修正したrunnerを再検証し、`/health=200` 後に先頭1件を1回だけ送った
- [x] 2026-09-05: HTTP 200の応答を受けたが、adapterの `intent_normalization_invalid` で安全に拒否された
- [x] 2026-09-05: 2件目・再試行・assessmentを実行せず、server停止、port非listen、process終了、一時runner削除を確認した
- [x] 2026-09-05: 正規化と検索可能性を分けるREDを固定し、`intent_searchability_invalid` をoffline実装した
- [x] 2026-09-05: focused・関連回帰を実行した
- [x] 2026-09-05: 文書同期後の標準offline gateを実行した

### 検証

| 対象 | 方法 | 実結果 | 分かること |
|---|---|---|---|
| 送信前検査 | 固定artifactとrequestを本文非表示で再検証 | model `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54`、CSV `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea`、prompt `9477fcc8c4a846a9c6f87ae8410371f8a57f68a7f6dc2599ef015d084561a150`、生成schema `f557081591fa9d322364e8b65ac0583ee78a0359cd7e1721b659491e1e2fa865`、body 19,877 bytes、`max_tokens`・timeout不在 | 承認済みの固定条件へ一致した |
| runner preflight | 実送信前に一時runnerを起動 | 初回はrepository import path不足で停止。transport call 0 | modelやproviderの失敗ではなく、送信前の実行用設定不備だった |
| localhost 1 call | `/health=200` 後に先頭caseだけを送信 | HTTP 200、`finish_reason=stop`、143 completion tokens、1,183 response bytes、102.333秒、transport call 1、`intent_normalization_invalid` | envelope、JSON、draft schema後の受理前段階で停止した。後段の `query_plan_invalid` へは進んでいない |
| RED | 正規化失敗と検索不能に別stageを要求 | 1 failed、1 passed | 実装前は検索不能も `intent_normalization_invalid` だった |
| focused GREEN | 正規化、検索不能、blocking、diagnosticを合成responseで確認 | 4 passed | 検索不能だけを `intent_searchability_invalid` に分け、blockingと正規化の既存契約を維持した |
| 関連回帰 | adapter、request、HTTP、query planner、holdout postprocess、typed adapter | 150 passed | request・strict parser・後処理境界との互換性を維持した |
| 標準offline gate | lock、Ruff、Markdown、offline pytest、Python 3.10 AST、diff | lock 79 packages、Ruff 195 files、Markdown 16 files・1,211 links・810 anchors・1,512 headings・199 fence pairs、pytest 1,638 passed・9 skipped・1 deselected、AST 195 files、diff成功 | model再推論・外部通信なしで最終treeの整合を確認した |

### セキュリティ・データ境界

一時runnerはrequest digestへ一致するtransportを1回だけ許可し、2回目を拒否する。実行結果へ検索文、生response、正規化intent、商品情報、URL、ASIN相当値、provider error、内部例外本文を残していない。追加したdiagnosticもstage、finish reason、completion token件数、response byte数だけを保持し、公開message、cause、contextを従来どおり固定する。SHA-256は匿名化として扱わない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-05 | 承認済み上限を先頭1件・合計1 callで消費し、同じ承認で再試行しない | 利用者が全体で1件だけと明示したため | 次のmodel callには、同じ1件でも新しい明示承認が必要 |
| 2026-09-05 | `intent_searchability_invalid` を追加する | 実行時の `intent_normalization_invalid` がnormalizerとquery plannerの両方を含み、本文なしでは次の修正対象を特定できなかったため | 次回1件でstageを区別できる。保存情報は増やさない |

### 結果

承認済みの先頭1件は1 callだけ実行し、HTTP応答は完了したが `intent_normalization_invalid` で拒否された。実行時点のadapterは正規化と検索可能性を同じstageへ写像していたため、保存済み情報だけから直接原因を断定できない。ただし、EXEC-049で修正対象にした失敗が後段の `query_plan_invalid` として漏れることはなく、受理前にfail closedとなった。

追加model callなしでadapterを分離し、正規化失敗は `intent_normalization_invalid`、非blocking intentからquery planを作れない場合は `intent_searchability_invalid` とした。どちらも固定messageと本文非保持を維持する。最終実装SHA-256は `src/search_v2/bonsai_adapter.py` が `d04e10319c36a649a82780e7e003aae3cf0069d7df584115b4b447e66c8d89e5`、RED兼最終testは `tests/test_search_v2_bonsai_adapter.py` が `d449e02fe563957adfdb67a9be8d9a0b4935269198325cd3b95c178344b88ded` である。

標準offline gateはlock 79 packages、Ruff 195 files、現行Markdown 16 files・1,211 links・810 anchors・1,512 headings・199 fence pairs、offline pytest 1,638 passed・9 skipped・1 deselected、Python 3.10 AST 195 files、`git diff --check` に成功した。一時runner不在、port 18080非listen、`llama-server` processなしも再確認した。

次は、必要なら同じ先頭caseを新しいdiagnosticで合計1 callだけ再確認し、`intent_normalization_invalid` ならnormalizer契約、`intent_searchability_invalid` ならmodelの検索field生成を個別に修正する。これは新しい明示承認なしには実行しない。独立holdout評価は別の未使用dataで行う。


## EXEC-049: Bonsai intent検索可能性contract

### メタデータ

- 状態: 完了（offline契約）
- 作成日: 2026-09-05
- 最終更新: 2026-09-05
- 前提Plan: [EXEC-048](#exec-048-holdout後処理段階診断とquery-less-blocking投影)
- 関連要件: [TASK-005](#task-005-ランキング品質評価の確立)、[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-419](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

Bonsaiのstrict responseとして受理した非blocking intentが、その直後のquery plannerで失敗しない契約を固定する。商品名・カテゴリ・検索語を作れない場合はstrict intent成功として後段へ渡さず、既存の本文非保持errorへ安全に写像する。modelには非blocking出力で検索可能な商品種別または検索語を必須とする規則を明示する。

### 対象範囲

- 対象: `src/search_v2/bonsai_adapter.py` の非blocking intent検索可能性検査
- 対象: `src/search_v2/bonsai_intent_prompt.txt` の検索語必須・URL禁止規則
- 対象: 空の検索fieldを持つ合成response、正常response、blocking ambiguity、本文非保持のoffline test
- 対象外: model再実行、使用済みCSVの追加case、generation schema、request schema、ranking profile、quality policy、labelの変更
- 対象外: Cloudflare、Outscraper、Amazon、OpenAI、画像、credential、課金、外部network、browser、Windows native、外部委託中フロントエンド、commit、push

### 現在の状態

- 利用者の承認を4件各1回と解釈して実行を開始したが、利用者の意図は全体で1件だけだった。訂正を受けた時点で2件が完了、3件目が送信済みだったため直ちに中断し、4件目は送信していない
- 完了した2件はHTTP 200、`finish_reason=stop`、strict intent成功後にともに `query_plan_invalid` となった。3件目は応答待ち中に手動中断したため評価へ投影していない
- 生responseと正規化intentを保存していないため、完了2件の具体的なfield値とquery planner内の直接原因は復元できない
- 合成した「typed conditionは有効だが、商品名・カテゴリ・required・preferred検索語が全て空」のintentでは、proposalが誤って `ready` になった後に同じ `query_plan_invalid` となる契約上の穴をofflineで再現した。ただし、これが実2件と同一原因だとは断定しない

### 受入条件

1. blocking ambiguityを持たないBonsai responseは、strict intentとして返す前に既存query plannerでquery planを構築できなければならない。
2. 非blockingで検索fieldが空、URLを含む、またはquery plannerが拒否するresponseは、後処理の `query_plan_invalid` へ進めず、既存の固定messageと本文非保持diagnosticで拒否する。
3. blocking ambiguityを持つintentはquery planなしで受理でき、EXEC-048のquery-less blocking投影を維持する。
4. promptは、非blocking出力で商品種別または検索語を少なくとも1つ設定し、query用fieldへURLを入れないことを明示する。
5. request schema 5.0、完全schema、生成schema、生成token上限なし、HTTP timeoutなし、1 MiB response上限、retry禁止は変更しない。prompt変更によりprompt・body・request digestが変わることは新しいrequestとして扱う。
6. RED、focused GREEN、Bonsai・query・postprocess関連回帰、標準offline gate、Markdown検査、`git diff --check` を記録する。
7. 修正後のlocal model確認は全体で1 case・1 call・retry 0に限定し、条件を再提示して利用者が明示承認するまで実行しない。

### 実行順序と進捗

- [x] 2026-09-05: 利用者の訂正後に実行を中断し、server停止とport非listenを確認した
- [x] 2026-09-05: 同じstageを起こす検索fieldなしの合成intentをofflineで再現した
- [x] 2026-09-05: 非blocking responseの検索可能性とprompt規則を先に要求するRED testを追加した
- [x] 2026-09-05: adapterとpromptを最小修正し、focused・関連回帰を実行した
- [x] 2026-09-05: 実行逸脱、確認できた原因範囲、未確認範囲を標準文書へ同期した
- [x] 2026-09-05: 標準offline gateを実行し、一時runner不在を再確認した
- [x] 2026-09-05: [EXEC-050](#exec-050-bonsai検索可能性失敗段階の分離) で更新promptの先頭1件・合計1 callを確認した

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| 合成再現 | 検索fieldなし・有効typed condition・ambiguityなしのintentをpostprocessへ入力 | 現行の契約上の穴を再現 | proposal `ready` の後に `query_plan_invalid` を再現 |
| RED | Bonsai adapterとpromptのfocused test | 修正前に期待した理由で失敗 | 2 failed、1 passed。非blocking空検索fieldの未拒否とprompt規則欠落で失敗 |
| focused GREEN | Bonsai adapter・request・query planner・postprocess test | 全件成功 | focused 3 passed、関連回帰172 passed |
| 標準gate | lock、Ruff、Markdown、offline pytest、diff | 全て終了0 | lock 79 packages、Ruff 195 files、Markdown 16 files・1,201 links・800 anchors・1,499 headings・199 fence pairs、Markdown test 4 passed、pytest 1,638 passed・9 skipped・1 deselected、diff成功 |

### セキュリティ・データ・互換性

検査には既存のstrict `NormalizedSearchIntent` とquery plannerだけを使い、生response、検索文、正規化field、商品情報をdiagnosticへ追加しない。失敗は既存の固定messageと件数だけを持つBonsai response diagnosticへ写像する。prompt変更後は旧request digestとの同一性を主張しない。使用済みCSVはdevelopment dataのままで、独立holdoutへ戻さない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-05 | model出力を推測補完せず、非blocking intentの受理条件にquery plan構築成功を追加する | 元入力やtyped keyから商品種別を捏造すると誤検索を開始し得るため | query-lessの人間確認stateをproduction orchestrationへ導入する場合にblocking表現を別Planで見直す |
| 2026-09-05 | local modelの次回確認は全体で1件だけにする | 利用者が「各case 1回」ではなく「1件だけ」と明示したため | 追加caseは各回の新しい明示承認がある場合だけ実行する |

### 発見事項

- 現行schemaは全fieldの存在と型を固定するが、非blocking出力に検索可能な商品種別または語が1つ以上あるというfield横断の意味条件までは表現していない。
- 生intentを保存しない境界は維持できた一方、過去の安全なstageだけから具体的な欠損fieldを後で復元することはできない。

### ロールバック

adapterの検索可能性検査、promptの2規則、対応testと本Planの実装結果だけを戻せばEXEC-048完了時点の契約へ戻る。model、CSV、評価dataset、ranking profile、既存reportは変更しない。

### 結果

offline実装は完了した。`bonsai_adapter.py` は非blocking intentを返す前に既存 `build_search_query_plan()` を実行し、検索queryを構築できない応答を既存の `intent_normalization_invalid` と固定messageへ写像する。blocking ambiguityはこの検査を迂回し、EXEC-048のquery-less blocking投影を維持する。promptは非blocking出力へ商品種別または検索語を最低1つ要求し、検索fieldへのURL出力を禁止する。

REDは非blocking空検索fieldの未拒否とprompt規則欠落を理由に2 failed・1 passed、GREENは同じ3件が3 passed、Bonsai adapter・request・HTTP、query planner、holdout後処理、typed adapter、orchestrationの関連回帰が172 passedだった。test SHA-256は `test_search_v2_bonsai_adapter.py` が `44290455602b612af096bdf7b01877ddf43c77457d52b90b94a5ecd2bc5b0137`、`test_search_v2_bonsai_request.py` が `90f63f94e2c6794c4ab66ff99b5d153feda4d9b494605163c5d1737d26359ac3`、最終 `bonsai_adapter.py` が `0a418495e27bbb5e1df395c2367fdcf0ddcd523147b43f05bc7f1b240fddec05`、promptが `9477fcc8c4a846a9c6f87ae8410371f8a57f68a7f6dc2599ef015d084561a150` である。標準gateの最終値は本節の検証表とWORKLOGへ記録する。

標準gateはlock 79 packages、Ruff 195 files、現行Markdown 16 files・1,201 links・800 anchors・1,499 headings・199 fence pairs、Markdown test 4 passed、offline pytest 1,638 passed・9 skipped・1 deselected、Python 3.10 AST 195 files、`git diff --check` に成功した。一時runner不在、port 18080非listen、`llama-server` processなしも確認した。

実2件の具体的な出力値を復元していないため、修正した契約欠落を直接原因とは断定しない。訂正後の追加model callは行っていない。更新promptのlocal model確認は、後続のEXEC-050で条件を再提示して明示承認を得たうえで、先頭1 case・合計1 call・retry 0だけを実行した。HTTP 200の応答後、受理前の `intent_normalization_invalid` で停止し、2件目・再試行・dataset assessmentは実行していない。実行時のstageはnormalizer失敗と検索不能を区別できなかったため、EXEC-050で本文非保持の `intent_searchability_invalid` を追加した。


## EXEC-048: holdout後処理段階診断とquery-less blocking投影

### メタデータ

- 状態: 完了
- 作成日: 2026-09-05
- 最終更新: 2026-09-05
- 前提Plan: [EXEC-047](#exec-047-request-v5-local-bonsai-development-regression)
- 関連要件: [TASK-005](#task-005-ランキング品質評価の確立)、[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-419](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

strict intent成功後の後処理を、typed proposal、query plan、typed ranking、prediction projectionの固定段階へ分け、失敗時に本文や内部例外を残さず安全な段階だけを取得できるようにする。上流blocking ambiguityをquery plan失敗またはartifact-free failureへ潰さず、query planを作らない正規の `blocking` predictionとして評価へ含める。

### 対象範囲

- 対象: `src/search_v2/holdout_postprocess.py` の固定段階diagnostic、typed proposal・query plan・ranking・prediction projection wrapper
- 対象: `src/search_v2/holdout_evaluation.py` のquery-less blocking prediction、既存prediction digest・集計との互換性
- 対象: 合成ready、上流blocking ambiguity、各段階失敗、tamper、本文非保持のoffline test
- 対象外: local Bonsai再推論、使用済みCSV再評価、実holdout、provider・prompt・schema・model・ranking profile・quality policyの変更
- 対象外: 商品取得、画像、Cloudflare、Outscraper、Amazon、OpenAI、credential、課金、外部network、browser、Windows native、外部委託中フロントエンド、AIレビューハーネス、commit、push

### 現在の状態

- EXEC-047のhealth-ready再実行では4件全てがstrict intentを通過した後、一時runnerの一括 `postprocess_failed` へ入り、個別段階を保持していなかった
- 追加model callなしの合成ready intentは同じ後処理からrankingまで通った
- 上流blocking ambiguityを持つ合成intentはtyped proposalが `blocking` になる一方、既存query plannerは検索前停止を意図してquery plan生成を拒否する
- 既存holdout predictionは `blocking` にもquery plan digestを必須としており、検索前停止した正規のblockingを直接投影できない

### 受入条件

1. diagnosticはfrozenで、`typed_proposal_invalid`、`query_plan_invalid`、`typed_ranking_invalid`、`prediction_projection_invalid` のいずれか1項目だけを保持する。
2. postprocess errorは固定messageとdiagnosticだけを公開し、検索文、商品情報、provider応答、ASIN、URL、元例外の本文・型を保持または連鎖しない。
3. 公開wrapperはtyped proposal、query plan、typed ranking、prediction projectionを固定段階へ写像し、network、file reader、callbackへ依存しない。
4. proposalが `blocking` の場合はquery plannerを呼ばず `None` を返し、holdout predictionはintent・proposal digestへ結んだ `blocking` としてquery planなしで正規に投影できる。
5. `ranked` predictionは従来どおりquery planとranked batchを必須とし、query-less ranked、blockingへのranked products混入、artifact改ざんを拒否する。
6. 既存のquery plan付きblocking、ranked、artifact-free failed predictionと既存digest・集計値を変更しない。評価reportは `not_assessed`、acceptance policyは未変更のまま維持する。
7. 実行は合成fixtureだけを使い、Bonsai、外部通信、credential、課金、画像、実商品を使わない。
8. RED、focused GREEN、holdout・typed関連回帰、標準offline gate、Markdown検査、`git diff --check` を記録する。

### 実行順序と進捗

- [x] 2026-09-05: EXEC-047の安全な実行記録、現行holdout projection、query planner、typed adapter、typed ranking、orchestration境界を確認した
- [x] 2026-09-05: 本Planを実model・CSV・外部serviceなしのoffline変更として登録した
- [x] 2026-09-05: 新しい公開moduleとquery-less blockingの期待をテストへ追加し、module不在による収集errorのREDを記録した
- [x] 2026-09-05: 段階別diagnosticとquery-less blocking投影を最小実装した
- [x] 2026-09-05: focused 23件、関連126件、全search v2 898件の回帰を実行した
- [x] 2026-09-05: 標準文書を結果へ同期した
- [x] 2026-09-05: 標準offline gateを実行し、最終件数を記録した

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_holdout_postprocess.py tests/test_search_v2_holdout_evaluation.py` | module不在または現行all-or-none制約で失敗 | exit 2。新規module不在の `ModuleNotFoundError` で収集停止 |
| focused GREEN | postprocess・holdout evaluation test | 全件成功 | 23 passed |
| 関連回帰 | typed adapter・query planner・typed ranking・orchestrator・acceptance test | 全件成功 | 126 passed |
| search v2全体 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_*.py` | 全件成功 | 898 passed、9 skipped |
| 標準gate | lock、Ruff check/format、Markdown、offline pytest、diff | 全て終了0 | lock 79 packages、Ruff 195 files、Markdown 16 files・1,187 links・786 anchors・1,483 headings・199 fence pairs、pytest 1,635 passed・9 skipped・1 deselected、diff成功 |

### セキュリティ・データ・互換性

diagnosticは固定stage以外を持たず、元例外はactiveな例外処理の外で固定errorへ置き換えてcontextを残さない。runtimeのintent、query plan、proposal、商品batchは既存処理へ渡すだけでdiagnosticへ複製しない。query-less blockingはprovider失敗ではなく、検索前に人間確認が必要という既存の安全状態を保持する。既存predictionのserialized bytesとdigestを変えず、新しく表現可能になるblocking形だけを追加する。

RED時のtest SHA-256は新規 `tests/test_search_v2_holdout_postprocess.py` が `66f1d813eae8d86b4a9ff6cc38a49b30502167aa94130ac96ff9d43e94a95474`、更新した `tests/test_search_v2_holdout_evaluation.py` が `14578bd0928233e79067a8351a1e5364f95b4c6f66d2cf5e669683c27e66658a` である。GREEN後は実装 `src/search_v2/holdout_postprocess.py` が `3d1928c6fdb3e38cda3eb3d7c0d1177daba8431c1ee9b563949f0bd9aca887a6`、`src/search_v2/holdout_evaluation.py` が `4bf54b15f541f06ad12c32e846eff55eaa0c20fe8a874ce4a230da2fffd7e460`、新規testが `db4485e28696d913dd952898a562c69776e3dd634fcd83757d4e9d5036a2585e`、更新testが `1b2c82cd0875e38684c2350b873f1c103dc89ce3ae4ec559da4da6e65f6330af` である。評価profile digest `8112ae763f24191cbcc4212cfda7fbdc8133a658ebf6f9f282d735d117237807` とacceptance policy digest `de4b17313dbcbe6bc7e032b36f8a00e59506f49a600e0e0138c748c734073db3` は変更していない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-05 | query plannerのblocking拒否を緩めず、評価projection側でquery planなしblockingを表現する | blocking ambiguityは検索を開始しない安全状態であり、評価のためだけに検索queryを生成すると本来の停止境界を崩すため | query plan以外の検索前artifactを導入する場合はprediction schema versionを見直す |
| 2026-09-05 | 一括catchではなく公開wrapperごとの固定stageへ変換する | raw本文を保存せず再実行時の失敗位置を判別するため | 段階が追加された場合はallowed stageと受入testを同時更新する |

### 発見事項

- `HoldoutCasePrediction.query_plan_sha256` は既にoptional型だが、validatorとbuilderのall-or-none規則がblockingでも値を要求していた。
- EXEC-048時点のorchestratorもquery planをtyped proposalより先に作るため、上流blocking ambiguityを `IntentReview` として返せなかった。このPlanでは評価後処理だけを修正し、orchestration schemaの変更は別範囲として課題へ残した。後続のEXEC-054で専用blocking確認へ接続済みである。

### ロールバック

新規postprocess moduleとtestを削除し、holdout predictionのblocking validationを元のall-or-noneへ戻せばEXEC-047完了時点へ戻る。既存dataset、prediction、report、policy、model、CSV、provider、cache、履歴は変更しない。

### 結果

完了。本文を保持しない4段階の後処理diagnosticを追加し、ready経路は従来のquery planとtyped rankingを通し、上流blocking ambiguityはquery plannerを呼ばずquery-less blocking predictionへ投影できるようにした。既存のquery付きblocking、ranked、artifact-free failed、評価profile、acceptance policy、元reportの `quality_decision=not_assessed` は変更していない。実4件の過去の失敗段階は復元していない。後続の部分再計測と検索可能性修正はEXEC-047・EXEC-049へ記録し、次のmodel確認は全体で1 case・1 callについて新しい明示承認が必要だった。EXEC-048時点で別課題へ残したorchestratorの上流blocking処理は、後続のEXEC-054で専用blocking確認へ接続済みである。


## EXEC-047: request v5 local Bonsai development regression

### メタデータ

- 状態: 完了（使用済みdataによるdevelopment regression）
- 作成日: 2026-09-05
- 最終更新: 2026-09-05
- 前提Plan: [EXEC-046](#exec-046-llamacpp互換bonsai生成schema)
- 関連要件: [TASK-005](#task-005-ランキング品質評価の確立)、[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-419](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

非空のllama.cpp互換生成schemaを含むrequest v5をlocal Bonsaiへ実際に送り、使用済みCSVの4 caseがstrict intent、typed proposal、固定候補rankingのどこまで進むかを確認する。結果確認後に修正へ使っている同じCSVを再利用するため、結果はdevelopment regressionであり、独立holdout、未知データへの一般化、production E2Eとして扱わない。

### 実行承認と固定条件

2026-09-05に利用者へ次の条件を提示し、「実行してよい」と明示承認を得た。

- 送信先は `http://127.0.0.1:18080/v1/chat/completions` だけとし、credential・外部network・費用を使わない
- SHA-256固定済みのlocal Bonsai modelと使用済みCSVを使い、4 caseを固定順に各1回、合計4 calls、逐次、retry 0で送る
- payloadは固定system prompt、完全schema、互換生成schema、検索文だけとし、商品名、商品情報、URL、ASIN相当値、画像をmodelへ送らない
- applicationの生成token上限とHTTP timeoutは設けない。responseは最大1 MiB、server context 8,192、parallel 1とし、応答、EOS、context境界、OS失敗、または人間の手動停止まで待ち得る
- server log、prompt cache、UIを無効にし、検索文と生responseを保存しない。digest、固定status、安全なdiagnostic、時間、token・byte件数、評価集計だけを残す

### 対象範囲

- 対象: request v5によるlocal Bonsai 4 calls、strict response adapter、typed proposal、CSV内の固定候補だけを使うoffline ranking、既存holdout evaluation・acceptance policy
- 対象: request bodyが非空の生成schemaを含み、`max_tokens` とtimeout fieldを持たないことの実行直前検査、call数とserver停止の実行後検査
- 対象外: prompt、schema、model、llama.cpp、label、ranking profile、quality policyの実行中変更、自動retry、追加call
- 対象外: Cloudflare、Outscraper、Amazon、OpenAI、実商品取得、画像、credential、課金、外部network、browser、Windows native、外部委託中フロントエンド、commit、push

### 受入条件

1. model・CSVのSHA-256、port非listen、request v5、生成schema digest、body、token・timeoutなしを送信前に確認する。
2. localhostだけへ4 caseを各1回逐次送信し、成功・失敗にかかわらず自動retryしない。
3. 各caseの到達段階を固定statusと本文非保持diagnosticで記録し、strict不一致を修復・除外しない。
4. strict intentが成功したcaseだけ既存adapter・rankingへ進め、failed・blocking caseも既存評価へ含める。
5. raw検索文、生response、商品本文、URL、ASIN相当値を結果artifact・標準文書・回答へ保存または転記しない。
6. 実行後はserverを停止し、port非listenとprocess終了を確認する。
7. 結果反映後に標準offline gate、Markdown検査、`git diff --check` を成功させる。

### 実行順序と進捗

- [x] 2026-09-05: endpoint、範囲、4 calls、上限なし、credential・費用・外部networkなし、保存・停止条件を提示し、利用者の明示承認を得た
- [x] 2026-09-05: model・CSV digest、実行file、port非listenを確認した
- [x] 2026-09-05: request v5と安全な一時評価runnerを送信前に検証した
- [x] 2026-09-05: llama-serverをloopback限定で起動して4要求を各1回送ったが、全件model ready前の `request_failed` となり推論へ到達しなかった
- [x] 2026-09-05: 失敗4件を既存評価・固定policyへ投影し、server停止、port非listen、process終了を確認した
- [x] 2026-09-05: 検索文を送らないhealth-only再現で、listen直後503、model ready後200への遷移を確認した
- [x] 2026-09-05: `/health=200` を必須の送信前条件にした同じ4 caseの再実行について、利用者から新しい明示承認を得た
- [x] 2026-09-05: `/health=200` を確認した後に4 caseを各1回だけ再実行し、全件でHTTP 200、`finish_reason=stop`、strict intent通過を確認した
- [x] 2026-09-05: 後処理4件の一括失敗を除外せず評価へ投影し、server停止、port非listen、process終了を確認した
- [x] 2026-09-05: modelを呼ばない合成入力で後処理を切り分け、通常のready経路はrankingまで通る一方、上流blocking ambiguity経路はquery plan生成で停止することを確認した
- [x] 2026-09-05: [EXEC-048](#exec-048-holdout後処理段階診断とquery-less-blocking投影) で本文を保持しない後処理段階診断とquery-less blocking投影を固定した
- [x] 2026-09-05: 段階診断付き再計測を開始し、2件の `query_plan_invalid` を確認した。利用者の「1件だけ」という訂正を受け、送信済みの3件目を手動中断し、4件目は送信しなかった
- [x] 2026-09-05: server停止、port非listen、process終了を確認し、一時runnerを削除した
- [x] 2026-09-05: [EXEC-049](#exec-049-bonsai-intent検索可能性contract) 後の全体1 case・1 call条件を再提示し、明示承認後に先頭1件だけ確認した
- [x] 2026-09-05: strict intent・後処理到達結果を標準文書へ反映し、標準offline gateを完了した

### 停止・再実行規則

今後の確認は全体で1 case・1 callだけとし、結果にかかわらず次caseや同一caseを自動実行しない。transportが応答しない場合はapplication timeoutがないため、人間の手動停止まで待ち得る。server起動失敗、`/health` が200でない状態、local以外の接続先、request v5不一致、bodyへの `max_tokens`・timeout混入、digest不一致、CSV・model差し替え、保存境界違反を検出した場合は送信前に停止する。port listenだけをmodel readyの根拠にしない。実行後の追加call、再試行、prompt・schema・model変更後の再実行は、原因と1 callの新しい条件を提示して別の明示承認を得るまで行わない。

### 結果

初回実行ではrequest schema 5.0、生成schema SHA-256 `f557081591fa9d322364e8b65ac0583ee78a0359cd7e1721b659491e1e2fa865`、model SHA-256 `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54`、CSV SHA-256 `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea`、4 body、`max_tokens`・timeout不在を再検証した。SHA-256 `f48c24958c3c5632d52ddf75eddf3e92091eff93b8b24690c9d071f7edff3069` の一時runnerから4要求を逐次各1回送ったが、所要時間は0.009秒、0.010秒、0.009秒、0.006秒で、全件 `request_failed`、response 0 bytes、completion token不明となった。推論、strict intent、typed proposal、rankingには到達していない。

失敗を除外しない投影はcoverage適格、failed 4、ranked 0、元report `quality_decision=not_assessed`、固定assessment `fail`、53 checks中45件未達である。安全なdigestはdataset `73951eb4bce8860e016b3a63388002e900802ba2fdeb75e55827cca65d31ba6d`、prediction set `3ccae7a2d52d65597caa9d2727ceec4916892626b00593008654c0b31569c156`、evaluation report `6db0adfcf671fa3834a3d646a531ecb4eea1a572f491da0ebe16fc00aaf378a8`、assessment `0db8e790ffa02ab89bbbcbb757f41d9d575af0acbc82ca79cbd3833bea81e2a3` である。この評価値はmodel出力品質ではなく、推論前の失敗を欠落させなかった結果である。

直接のapplication観測は非200系を本文なしの `request_failed` へ写像したことだけで、元4要求のHTTP statusは保存していない。一方、llama.cpp version 9294の `server.cpp` はHTTP serverをmodel loadより先に開始し、ready前の全endpointを `server-http.cpp` が503にする。検索文を送らない同一条件のhealth-only再現でもlisten直後の `/health` は503、2秒後に200となった。初回runnerはport listenだけで送信を開始したため、model ready前に4要求を送ったことが失敗原因である。初回serverと一時runnerは終了・削除済みで、portとprocessも残していない。この結果を受けたhealth-ready再実行は次のとおりである。

新しい明示承認後の再実行では、同じmodel・CSV・生成schema digestと4 bodyを再照合し、SHA-256 `27f5ecb63ab6ef351ef53647d6ef091c257a885e5e962ac2220c062a905cf06d` の一時runnerを使用した。`/health` が2秒後にHTTP 200となってから4要求を逐次各1回、retry 0で送った。4件は全てHTTP 200、`finish_reason=stop` で、所要時間は152.007秒、149.881秒、151.759秒、152.631秒、completionは146、144、144、143 tokens、responseは1,189、1,178、1,185、1,186 bytesだった。request digestは順に `9197c2886922ba2ba1154839cf6820a85ef7139ce8f28c0b267bb1d5cfb340a6`、`207f94bd6566a32eb0f6118ed0d111fa0bc04543b5569b5e85f55dc4801ae69f`、`72d31f9df8b8f4e18f1084efaeeccda482f8a4e724ad5d6519ae3ebfab377573`、`b38b9a28f1667dcee825098dba0cffb8bb222956f40a7a3bab06ae016286e823` である。

4件とも `execute_bonsai_intent_request()` が正常復帰したため、OpenAI互換envelope、content全体のJSON、完全schema、正規化を含むstrict intent検証には成功した。request v5の非空生成schemaは、request v4で全件発生した `content_not_json` をこの4件では解消した。一方、その後の一時runner内後処理が4件とも `postprocess_failed` となり、typed rankingは完了しなかった。失敗を除外しない投影はcoverage適格、failed 4、ranked 0、元report `quality_decision=not_assessed`、固定assessment `fail`、53 checks中45件未達で、全品質指標は0.000000だった。digestはdataset `6a0d32e52e9f0a971300bdfd2bdcdb223e7c70badbc6f021fb6e3638c258d8ca`、prediction set `9df834c89e3470f6aa8b98ff8834f109c25418b2de14397dd617f895cd5eb1f2`、evaluation report `43b011d8d9bb0e20612d85bfc2e73f27da2c23b9da8eb0a3b4dfb942527b1243`、assessment `d630babb70c0c8782e860406282deff8d509a1c063b684f8180e0aef6837af86` である。この `fail` は後処理失敗の投影であり、typed条件または商品順位の品質値ではない。

一時runnerは後処理例外を一括していたため、実4件の個別失敗箇所は本文を再取得せずには復元できない。追加model callを行わず合成入力で確認すると、正しくbindingしたready intentは同じ後処理からranking完了まで進んだ。上流にblocking ambiguityを持つ合成intentではtyped proposalが `blocking` となる一方、query plannerは仕様どおりblocking ambiguityを拒否した。この経路を一時runnerが個別分類できない観測上の欠陥は確認したが、実4件が同じ経路だったとは断定しない。serverを停止し、port非listen、`llama-server` processなし、一時runner削除を確認した。

EXEC-048完了後の段階診断付き再計測では、固定model・CSV・request v5・生成schema・4 bodyを再照合し、`/health=200` 後に送信を開始した。1件目はHTTP 200、`finish_reason=stop`、146 tokens、1,189 bytes、151.339秒でstrict intent通過後の `query_plan_invalid`、2件目もHTTP 200、`finish_reason=stop`、144 tokens、1,186 bytes、118.616秒で同じstageだった。利用者の承認を「4 caseを各1回」と解釈して続行したが、利用者の意図は「全体で1件だけ」だった。訂正時には3件目が送信済みだったため直ちに手動中断し、4件目は送信していない。3件目の応答・token・byte・評価値は確定せず、部分実行からdataset評価またはassessmentを生成していない。server停止、port非listen、process終了、一時runner削除を確認した。

完了2件の生responseと正規化intentは保存していないため、query planner内の直接原因は復元できない。一方、商品名・カテゴリ・required・preferred検索語が全て空で、typed conditionだけが有効な合成intentではproposalが `ready` になった後に同じ `query_plan_invalid` となる契約上の穴をofflineで再現した。実2件と同一原因とは断定せず、後続のEXEC-049で非blocking intentの検索可能性をstrict受理条件へ追加する。prompt変更後のmodel確認は全体で1 case・1 callだけとし、別の明示承認まで実行しない。

EXEC-049後は固定条件を再提示して明示承認を得てから、使用済みCSVの先頭1件だけを新promptで送った。HTTP 200、`finish_reason=stop`、143 tokens、1,183 bytes、102.333秒で応答したが、adapterの受理前に `intent_normalization_invalid` となった。transport callは合計1、retry 0で、2件目、同一case再試行、dataset report・assessmentは実行していない。実行時点ではnormalizer失敗と検索不能を同じstageへ写像していたため、保存済み情報から直接原因は断定できない。後続のEXEC-050で両者を安全な別stageへ分けたが、追加model callは行っていない。server停止、port非listen、process終了、一時runner削除も確認した。

health-ready再実行の記録後に標準offline gateを実行し、lock 79 packages、Ruff check成功・193 files format済み、Markdown 16 files・1,174 links・773 anchors・1,467 headings・199 fence pairs、offline pytest 1,627 passed / 9 skipped / 1 deselected、`git diff --check` 成功を確認した。

初回失敗の記録後に標準offline gateを実行し、lock 79 packages、Ruff check成功・193 files format済み、offline pytest 1,627 passed / 9 skipped / 1 deselected、Markdown 16 files・1,172 links・771 anchors・1,464 headings・199 fence pairs、`git diff --check` 成功を確認した。


## EXEC-046: llama.cpp互換Bonsai生成schema

### メタデータ

- 状態: 完了（offline契約・llama.cpp converter互換）
- 作成日: 2026-09-05
- 最終更新: 2026-09-05
- 前提Plan: [EXEC-045](#exec-045-時間上限なしbonsai-development-regression)
- 関連要件: [TASK-005](#task-005-ランキング品質評価の確立)、[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

`response_format` に非空のllama.cpp互換JSON schemaを含め、Bonsaiの生成をJSON objectへ制約する。生成時の互換schemaは形式逸脱を減らす補助境界とし、受理の最終権威は既存の完全な `SearchIntentDraft` schemaとstrict application parserに残す。

本番フロー上では、利用者が `条件を整理する` を押した直後から、整理済み条件を最初の確認画面へ渡す前までに相当する。通常は条件整理1回につきBonsai transportを1回だけ呼び、同じ整理済み条件の承認、商品取得、結果再表示、履歴閲覧では追加で呼ばない。条件を変更して再度整理する場合は別の条件整理として1回呼ぶ。自動retryは行わない。

```text
検索条件を入力
  -> 条件を整理する
  -> [本Plan: Bonsai 1 call -> JSON生成制約 -> strict intent検証]
  -> 整理済み条件の確認
  -> 商品取得
  -> 商品正規化・typed-ranking-v4
  -> 結果表示・履歴
```

### 対象範囲

- 対象: `src/search_v2/bonsai_adapter.py` の決定的な生成用schema、`src/search_v2/bonsai_request.py` のcanonical request body・descriptor・digest、直接関係するoffline testと標準文書
- 対象: 完全schemaからllama.cpp同梱converterが扱えない `pattern` だけを生成用schemaから除き、その他の構造、必須field、型、列挙値、配列上限を維持する
- 対象: request schema 5.0として、完全application schema digestと生成schema digestを別々に結び、旧request schema 4.0を暗黙受理しない
- 対象外: local Bonsai modelの起動・再推論、使用済みCSVの再評価、未知holdout、商品取得、ranking、画像、Cloudflare・Outscraper・Amazon、credential、課金、外部通信
- 対象外: legacy `run_product_search()`、API、認証、外部委託中フロントエンドの確認・接続、AIレビューハーネス

### 現在の状態

- EXEC-045までのrequest v4はsystem messageへ完全schemaを含めたが、`response_format={"type":"json_object"}` に非空schemaを含めなかった
- llama.cpp version 9294のJinja経路は空schemaでは生成grammarを有効化せず、EXEC-045の4件は全てHTTP完了後に `content_not_json` となった
- 完全schemaにあるdecimal文字列の正規表現はllama.cpp同梱Python converterで拒否された。完全schemaから `pattern` 3箇所だけを除いたschemaは、localのC++・Python converterでgrammarへ変換できる
- application parserはcontent全体の単一JSON object、duplicate key、非有限数、全field、strict型、正規化を既にfail closedで検証する。この検証は緩めない

### 受入条件

1. 生成用schemaは非空のcanonical JSON objectで、完全 `SearchIntentDraft` schemaとの差が全 `pattern` keywordの除去だけである。
2. canonical bodyは `response_format={"type":"json_object","schema":<生成用schema>}` を含み、system messageには完全schemaを引き続き含む。
3. request schema 5.0は完全schemaと生成schemaの別digest、body、source、prompt、model、endpoint、response上限をdomain-separated digestへ結ぶ。旧4.0、schema欠落、digestまたはbody改ざんを送信前に拒否する。
4. builder、descriptor、HTTP transportに生成token上限とapplication timeoutを追加しない。1条件整理につきtransport 1回、自動retry 0を維持する。
5. application側は既存の完全schemaで最終検証し、生成schemaだけを満たす不正値を後段へ渡さない。JSON断片抽出、Markdown除去、型coercionは追加しない。
6. schema生成はfile reader、network、callback、llama.cpp installationにruntime依存せず、同じsourceから同じbytesを返す。
7. focused test、関連v2回帰、標準offline gate、Markdown検査、`git diff --check` が成功する。local model・実provider・browserは未実行理由を記録する。

### 実行順序と進捗

- [x] 2026-09-05: 本番フロー上の位置とBonsai呼出回数を確認し、本Planへ固定した
- [x] 2026-09-05: 現行request、strict parser、Pydantic schema、llama.cpp version 9294のschema取込経路を確認した
- [x] 2026-09-05: 完全schemaはdecimal `pattern` でconverterが失敗し、全 `pattern` だけを除くとlocal converterが成功することを静的確認した
- [x] 2026-09-05: request v5の期待を表すテストを追加し、production code未実装による3 failed / 41 passedのREDとtest SHA-256を記録した
- [x] 2026-09-05: 生成用schema、request v5、別digest・tamper検証を最小実装し、focused 44件と関連114件をGREENにした
- [x] 2026-09-05: 関連文書を現行実装へ同期し、標準offline gateを完了した

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| 実装前schema調査 | 完全schemaと `pattern` 除去schemaをlocal llama.cpp converterへ入力 | 前者は既知regexで失敗、後者は終了0 | 確認済み。model推論・HTTPなし |
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_bonsai_request.py` | 新しい生成schema APIまたはrequest v5未実装により期待した理由で失敗 | exit 1、3 failed / 41 passed。生成schema API欠落と旧4.0受理による期待どおりのRED |
| focused GREEN | 同上 | 全件成功 | 44 passed |
| 関連回帰 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_bonsai_adapter.py tests/test_search_v2_bonsai_http.py tests/test_search_v2_typed_intent_adapter.py tests/test_search_v2_orchestrator.py tests/test_search_v2_history_snapshot.py` | 全件成功 | 114 passed |
| 標準gate | lock、Ruff check/format、offline pytest、Markdown、`git diff --check` | 全て終了0 | lock 79 packages、Ruff 193 files、offline pytest 1627 passed / 9 skipped / 1 deselected、Markdown・diff成功 |
| local model・UI | localhost Bonsai、使用済みCSV、実provider、browser、委託フロントエンド | 本Planでは実行しない | 明示承認または納品前のため対象外 |

### セキュリティ・データ・互換性

- 生成用schemaから除く正規表現制約はapplication側の完全schemaへ残る。生成時に広く許された値も、完全schemaに不一致なら本文非保持の固定errorで停止する
- request descriptorにはschema本文、検索文、prompt、request body、responseを保持せず、digestだけを追加する。生入力、商品情報、credential、provider responseを文書・test artifactへ保存しない
- token上限とHTTP timeoutは引き続き設けない。1 MiB response上限、1 transport call、retry・redirect禁止、利用量予約、手動停止境界を維持する
- request serializationをschema 5.0へ上げ、旧4.0 artifactを自動移行しない。intent provenanceの `schema_sha256` は完全application schemaを指し続ける
- `src/search_v2/` はlegacy現行検索、API、UIへ未接続である。offline test成功をproduction E2Eまたは実Bonsai成功と扱わない

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-05 | 完全schemaと生成用schemaを分離する | provider converter互換性のため生成制約を緩めても、applicationの受理条件を緩めないため | llama.cppが完全schemaを安定して受理し、回帰で意味品質も改善すると確認できた場合に統合を再検討する |
| 2026-09-05 | 生成用schemaは完全schemaから `pattern` だけを決定的に除く | 手書きの別schemaによるfield driftを避け、既知のconverter不一致だけを最小化するため | 新しい非互換keywordが確認された場合は、REDと理由を追加して除外範囲を明示更新する |
| 2026-09-05 | request schemaを5.0へ更新する | wire bodyとdescriptorへ生成schema・digestを追加するため | v4 artifactは診断履歴としてのみ保持し、混在させない |

### 発見事項

- 現行Pydantic schemaの `pattern` はdecimal最小・最大とambiguity codeの3箇所にある。生成用schemaで除いても、完全schemaによる最終検証では全て維持される
- llama.cppの `response_format.type=json_object` は `schema` fieldを直接受け、非空objectの場合にJinja response grammarへ組み込む

### ロールバック

request v5、生成用schema関数、focused test、本Planに伴う現行文書だけを戻せばrequest v4へ戻る。外部状態、database、cache、model、利用者データは変更しない。異なるrequest schemaとdigestを混在させない。

### 結果

完了。`search_intent_generation_schema_bytes()` は完全な7,352 bytesのschemaから全3箇所の `pattern` だけを除いた7,203 bytesのcanonical schemaを返す。生成schema SHA-256は `f557081591fa9d322364e8b65ac0583ee78a0359cd7e1721b659491e1e2fa865`、完全schema SHA-256は `f6650c439794aface4d3b2b98227c32d8123ea9349db2ca3ad82dab7eedfb88c` である。request v5は生成schemaを `response_format.schema` へ含め、両schemaのdigestとcanonical bodyを送信前に再検証する。

RED固定時のtest SHA-256は `6d70c936a650b95b56a0e112451b2d64a06bf98116e37b05f3d465e950fc8fa8` だった。GREEN後にRuffの機械整形だけを適用したため、最終test SHA-256は `8f3609951be147bac39c37e8f001f8ad18ab21114d44241082bfe117b047fdf7` である。最終module SHA-256は `bonsai_adapter.py` が `c177516cb182b76dd04dfbb946f369e6fae8cb1e8d3714785e22b8ae04d0bd6e`、`bonsai_request.py` が `ce7a07a2aa19ab94034d9669a418c8f736c234981bcf26701aa97a7efc49ef42` である。

生成schemaはllama.cpp version 9294の同梱Python converterと、local `libllama-common` の実 `json_schema_to_grammar(schema, true)` の両方で終了0となった。model、HTTP、外部networkは使っていない。focused 44件、関連114件、全v2 890件 / 9 skipped、標準offline pytest 1627件 / 9 skipped / 1 deselected、lock、Ruff、Markdown、差分検査が成功した。applicationの生成token上限とHTTP timeoutは追加せず、完全schemaによる最終検証と1 call・retry 0を維持した。request v5によるlocal Bonsai再実行は別の明示承認を得るまで行わない。


## EXEC-045: 時間上限なしBonsai development regression

### メタデータ

- 状態: 完了（4件とも `content_not_json`）
- 作成日: 2026-09-05
- 最終更新: 2026-09-05
- 前提Plan: [EXEC-044](#exec-044-bonsai-application-timeout撤廃)
- 関連要件: [TASK-005](#task-005-ランキング品質評価の確立)、[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-419](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

applicationの生成token上限とHTTP timeoutを除いたrequest v4をlocal Bonsaiへ実際に送り、使用済みCSV 4件が応答完了、strict条件抽出、または安全な失敗段階のどこまで進むかを確認する。結果はdevelopment regressionとして扱い、独立holdout合格や未知データへの一般化には使わない。

### 対象範囲

- 対象: `127.0.0.1:18080` のlocal Bonsai、固定prompt・canonical schema・検索文・`response_format=json_object` を含むrequest v4
- 対象: 同一CSVの4 caseを逐次各1回、retry 0、application timeoutなし、application生成token上限なしで実行する
- 対象: 本文を保持しないdiagnostic、holdout評価report、固定acceptance assessment、server停止確認
- 対象外: prompt・strict parser・ranking・label・policy・model・llama.cppの変更、再試行、画像、外部network、credential、課金、Cloudflare、Outscraper、Amazon、browser、Windows native、外部委託中フロントエンド

### 現在の状態

request bodyには `max_tokens` がなく、transportの `Session.request()` に `timeout` を渡さない。1 MiB response上限は生応答の無制限取得を防ぐbyte境界であり、model生成token上限ではない。使用済みCSVのSHA-256は `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea`、modelのSHA-256は `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54`、llama-serverはversion 9294（`0f3cb3fc8`）である。

### 実行手順と進捗

- [x] 2026-09-05: 接続先、payload範囲、4 calls、retry 0、無期限待機、1 MiB response上限、credentialなし、費用0円、外部networkなし、本文非保持、手動停止方法を提示して明示承認を得た
- [x] 2026-09-05: serverをloopback、context 8,192、parallel 1、CPU、offline、log・prompt cache・UIなしで起動した
- [x] 2026-09-05: request schema 4.0、`max_tokens`・旧fieldなしを実行時に検証し、同一4 caseを各1回だけ逐次実行した
- [x] 2026-09-05: raw responseを保存せず、安全な段階・token件数・response byte数・所要時間と評価digestだけを集計した
- [x] 2026-09-05: serverを停止し、port非listenと `llama-server` process終了を確認した

### 検証

| 対象 | 方法 | 期待結果 | 実結果 |
|---|---|---|---|
| request契約 | 実行時にschema、旧field、bodyを検証 | v4、`max_tokens`・token上限field・timeout fieldなし | 成功 |
| localhost 4 calls | 使用済みCSVを逐次各1回、retry 0で送信 | 応答完了または列挙済みの安全な失敗 | 4件ともHTTP完了後に `content_not_json` |
| 評価 | 同じ正解datasetと固定policyで集計 | 失敗を除外せず判定 | coverage適格、failed 4、ranked 0、`not_assessed` / `fail` |
| 後処理 | server停止後にsocket・processを確認 | 待受・processなし | 成功 |
| 標準offline gate | lock、Ruff、pytest、Markdown、差分形式を検査 | 全件成功 | lock 79 packages、Ruff 193 files、pytest 1,625 passed / 9 skipped / 1 deselected、Markdown 16 files・1,148 links・747 anchors・1,436 headings・197 fence pairs、diff成功 |

各caseの所要時間は313.169秒、316.069秒、325.651秒、318.563秒で、合計1,273.452秒、平均318.363秒だった。全件が `finish_reason=stop`、completion 2,000 tokensで、response byte数は9,186、9,188、9,194、9,193だった。`finish_reason=length` ではないため、2,000はapplicationまたはserverの上限停止を示す値ではなく、今回の実生成量である。

dataset digestは `cb12c4a9c608b400bdad6f8b3b1e6a8ac68907c0a152304b438e42199e872d5e`、prediction setは `4c5499b22e67ed61c40bdb59ef8c76a075d8a7dc3d4ba7579adae3ef2ab3ec91`、evaluation reportは `29960a1aa7faa7d2939bf0de3262a94ff1312cba283fdf8a17eac4378dd363aa`、assessmentは `920f39eb6362925877da0625905edc93e9553d252fc6ee63539e10597c03b5f8` である。assessmentは53 checks中45件未達で、全品質指標は0.000000だった。

### セキュリティ・データ・互換性

検索文は固定prompt・schemaとともにloopbackへだけ送り、商品名、商品属性、URL、ASIN相当値、画像はmodelへ送っていない。credentialと外部networkを使わず、server logとprompt cacheを無効にした。raw response、検索文、商品本文はartifact・文書へ保存せず、digest、固定status、安全なdiagnostic、件数、metricだけを残した。CSVは既に使用済みであり、この結果も独立holdoutとして扱わない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-05 | 4件を時間上限なしで完走する | 旧300秒timeoutがresponse parser到達前の唯一の観測失敗だったため | 無期限待機と手動停止を事前提示し、逐次4 calls・retry 0へ限定した |
| 2026-09-05 | strict parserを緩めず、生成grammarを次に直す | 4件ともtransportは完了し、失敗段階が `content_not_json` に揃ったため | 修正後も完全canonical schemaをapplication側の最終権威にする |

### 発見事項

- 現行llama.cppでは `response_format={"type":"json_object"}` にschemaがない場合、内部のJSON schemaは空objectになる。Jinja/autoparser経路は非空schemaだけをresponse formatとして扱うため、今回の空schemaでは生成grammarが有効にならない
- 完全なPydantic schemaは既知の未対応regexを含むため、そのままllama.cpp grammarへ渡せない。この役割分離は後続の [EXEC-046](#exec-046-llamacpp互換bonsai生成schema) で、非空の互換生成schemaとapplication側の完全strict schemaとして実装した
- raw contentを保持しない方針のため、非JSON本文の具体的な文字列、先頭文字、Markdown・説明文・反復の別は確定しない

### ロールバック

外部状態の変更はない。serverは停止済みで、保存したprovider responseもない。評価記録を取り消す場合も既存のEXEC-042・EXEC-043結果やCSV labelを変更せず、本節だけを履歴として残す。

### 結果

時間上限なしのrequest v4は4件全てでHTTP応答まで完了したが、全件が `content_not_json` となり、strict intent、typed proposal、商品rankingへ進まなかった。固定assessmentは `fail` のままである。非空のllama.cpp互換生成schemaは後続の [EXEC-046](#exec-046-llamacpp互換bonsai生成schema) でoffline実装した。次にlocal modelを使う直前には、別の明示承認を得る。


## EXEC-044: Bonsai application timeout撤廃

### メタデータ

- 状態: 完了（offline実装）
- 作成日: 2026-09-05
- 最終更新: 2026-09-05
- 前提Plan: [EXEC-043](#exec-043-bonsai構造化出力と安全診断)
- 関連要件: [TASK-005](#task-005-ランキング品質評価の確立)、[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

利用者決定に従い、local Bonsai requestからapplication側の生成token上限とHTTP timeoutの両方を除く。`None` の設定値として残さず、公開request descriptor、builder、transport protocol、orchestration configから両項目を削除し、旧schema 3.0と区別する。

### 直前の実測

EXEC-043のoffline修正後、明示承認された同一CSVの4件をrequest schema 3.0、`response_format=json_object`、`max_tokens`なし、各300秒、retry 0でlocalhostへ再送した。4件は300.101秒、300.104秒、300.105秒、300.066秒で全て `request_failed` となり、response parserへ到達しなかった。coverageは適格だがranked caseは0件で、独立assessmentは53 checks中45件未達の `fail` だった。server停止と `127.0.0.1:18080` の非listenを確認済みである。

### 対象範囲

- 対象: Bonsai requestをschema 4.0へ更新し、`max_output_tokens` と `timeout_seconds` をdescriptorとbuilder signatureから削除する
- 対象: Bonsai transport protocolとRequests実装から `timeout_seconds` を削除し、Requests送信へ `timeout` optionを渡さない
- 対象: `BonsaiIntentConfig` から両項目を削除し、旧configをstrictに拒否する
- 対象: request digest domain、mock HTTP、orchestration、履歴fixture、標準文書を新契約へ同期する
- 対象外: prompt、strict response parser、typed registry、ranking、acceptance policy、CSV label、response 1 MiB上限、retry禁止、localhost制約の変更
- 対象外: timeoutなしのlocal model再実行、外部provider、credential、課金、画像ranking、Windows native、browser、外部委託中フロントエンド

### 受入条件

- request bodyとdescriptorに `max_tokens`、`max_output_tokens`、`timeout_seconds` が存在しない
- builder、transport、orchestration configの公開signature/schemaにtoken上限とtimeout入力が存在しない
- applicationの `Session.request()` 呼出しに `timeout` 引数が存在せず、Requests内部の実効値が無期限を表す `None` である。redirect・retry・環境proxy・response 1 MiB上限は従来どおりである
- 旧schema 3.0 requestと旧configをschema 4.0として受理しない
- focused test、標準offline pytest、Ruff、Markdown link検査、`git diff --check` が成功する

### 実行順序と進捗

- [x] 2026-09-05: request・builder・transport・configから両制御が消える受入testを追加し、実装前RED 4件を期待理由で確認した
- [x] 2026-09-05: request schema 4.0とv4 digest domainを実装し、生成token上限とHTTP timeoutを公開契約・Requests高水準呼出しから削除した
- [x] 2026-09-05: 旧schema 3.0 requestと旧config fieldの拒否、response上限・retry禁止・本文非保持の維持を確認した
- [x] 2026-09-05: 受入4件とBonsaiから履歴までの関連172件をofflineでGREENにした
- [x] 2026-09-05: 標準offline gateと標準文書の最終read-backを完了した
- [x] 別作業: [EXEC-045](#exec-045-時間上限なしbonsai-development-regression) で条件提示と明示承認後に時間上限なしのlocal model再実行を完了した

### 検証記録

REDはrequest body・descriptor・builder signature、transport signature・送信option、orchestration configに旧制御が残ることを理由に4件失敗した。import、依存、fixture、構文の失敗ではない。RED固定時点のtest SHA-256は `test_search_v2_bonsai_request.py` が `05d8822dac95bda1e2b0179ebfdc06f3ed94a603a756628e613cadfc0d436152`、`test_search_v2_bonsai_http.py` が `c1fb0d2b3be05061934f67085c5116cb55bedbfc25f4d8e48ba1d3044b430e3d`、`test_search_v2_orchestrator.py` が `978f202c501eeec9a89ac6d25e308b4e3dfaecd112c1f986bd787325a40a568c`、`test_search_v2_history_snapshot.py` が `d3afedd7140e7eee862b648a8cf2045cfda5caa787cd89064a3c810de10306bf` である。GREENは同じ4 nodeで4 passed、Bonsai adapter・request・HTTP・typed adapter・orchestration・history snapshot・history repositoryの関連回帰で172 passedとなった。

最終module SHA-256は `bonsai_request.py` が `37105f67c951f7df7b9886c8287c65cc76e8458a13e5cf1390ce7458b545cd3b`、`bonsai_http.py` が `e50b9872fe7e4fa1abb9d04a1d65d50bcebb0670e3176a00c46199ad52a4fb65`、`orchestrator.py` が `d1054fc2f3c9ebfaf00736d90adc4f8ab75c0350923ea0f86660f447c6250276` である。最終test SHA-256は `test_search_v2_bonsai_request.py` が `2815fcdc927c7a5a8bffd74621dd45708b3f0f22e1470b226ec69f740b2bdc1c`、`test_search_v2_bonsai_http.py` が `c685b2b810e41c300d1367ea8c9cab8a73a2d3e69e5e3582ca1defcb28ffb8b7`、`test_search_v2_orchestrator.py` が `8681bc8cef80c6f3e1e5efa60d09dd6732befc62fbb2999376d4ad82e9864c38`、`test_search_v2_history_snapshot.py` が `d3afedd7140e7eee862b648a8cf2045cfda5caa787cd89064a3c810de10306bf` である。標準gateはlock 79 packages、Ruff check成功、Ruff format 193 files、offline pytest 1625 passed / 9 skipped / 1 deselected、現行Markdown 16 files・local link 1132件・anchor 731件・heading 1422件・fence 197組、`git diff --check` 成功である。

### セキュリティと停止条件

application timeout撤廃後のlocal実行は、応答、接続失敗、OS/network失敗、server context境界、EOS、または人間による手動停止まで待ち続け得る。自動再試行は追加しない。実行する場合は、時間上限なしと手動停止方法を含む条件を直前に提示し、別の明示承認を得る。生response、検索文、商品本文は保存しない。

### ロールバック

schema 4.0のrequest、transport、config、対応testと文書を一緒に戻し、schema 3.0の300秒契約へ戻す。異なるschemaやdigestを混在させない。

### 結果

offline実装は完了した。後続の [EXEC-045](#exec-045-時間上限なしbonsai-development-regression) では使用済みCSV 4件のHTTP応答が全て完了したが、全件 `content_not_json` でstrict条件抽出とrankingへ進まなかった。


## EXEC-043: Bonsai構造化出力と安全診断

### メタデータ

- 状態: 完了（development regressionは `request_failed`）
- 作成日: 2026-09-05
- 最終更新: 2026-09-05
- 前提Plan: [EXEC-042](#exec-042-固定済み基準による未使用holdout評価)
- 関連要件: [TASK-005](#task-005-ランキング品質評価の確立)、[FR-419](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

localhost Bonsaiの応答を後段で修復せず、生成時にJSON objectへ制約し、strict契約のどの段階で拒否したかを本文非保持の固定codeで判断できるようにする。local LLM requestからapplication側のoutput-token上限を外し、EOS、llama.cpp context、300秒timeout、1 MiB response上限、1-call承認境界は維持する。

### 対象範囲

- 対象: `bonsai_adapter.py` にresponse metadata、envelope JSON・shape、content JSON、draft schema、intent normalization、output truncationの安全な失敗段階を追加する
- 対象: 公開error本文を固定したまま、failure stage、正規化したfinish reason、completion token件数、response byte数だけを保持し、生response、検索文、field名・値、内部例外を保持しない
- 対象: `bonsai_request.py` のcanonical bodyへ `response_format={"type":"json_object"}` を固定し、現行Pydantic JSON Schemaを生成grammarへ直接渡さない
- 対象: local Bonsai requestから `max_tokens` を省略し、request model・digest・orchestration configを新schemaへ更新する。token課金上限の代わりにrequest・response byte上限からusage reservationを固定し、timeout、call数、response byte上限は残す
- 対象: strict Pydantic、重複key・非有限数拒否、extra禁止、型非coercionを維持する
- 対象: 利用者指定により2026-09-05のCSVを修正後の回帰確認へ再利用する
- 対象外: JSON断片抽出、Markdown fence除去、欠落field補完、型coercion、OpenAI fallback、画像component、Cloudflare、Outscraper、フロントエンド
- 対象外: 使用済みCSVの再評価を、未使用holdoutまたは独立した汎化性能の証拠として扱うこと

### 現在の状態

- schema 3.0のcanonical bodyはSchemaをsystem promptへ文字列で含め、llama.cppへ `response_format={"type":"json_object"}` を送る。`max_tokens` と生成grammar用schemaは送らない
- 使用中のllama.cpp version 9294は `response_format` の `json_object` とschema制約を実装している
- 現行Pydantic JSON Schemaは7,352 bytesで、同梱のoffline grammar変換scriptはdecimal pattern内のnon-capturing groupを未対応として拒否した。現行Schemaをそのまま生成grammarへ渡せるとは扱わない
- 4回の旧実行時間が約209秒から219秒で揃っており、旧1,000 token上限到達は有力な仮説だが、finish reasonを保持していなかったため未確認である。旧応答の段階は後から復元できない
- 新diagnosticはpublic messageを変えず、6種類の失敗段階、`stop`・`length`・`other`・`missing` へ正規化したfinish reason、妥当なcompletion token件数、response byte数だけを保持する
- request byte数と最大1 MiB responseをtoken数の保守的上界としてledgerへ予約するが、request bodyに生成token上限は含めない

### 実行順序と進捗

- [x] 2026-09-05: 現行request、adapter、tests、llama.cpp version 9294のsource・documentationを確認した
- [x] 2026-09-05: 現行Pydantic Schemaを同梱offline変換scriptへ渡し、decimal pattern未対応による変換失敗を確認した
- [x] 2026-09-05: 新しいrequest・diagnostic契約の受入testを追加し、実装前RED 10件を期待理由で確認した
- [x] 2026-09-05: 安全な失敗段階、`json_object` response format、application output-token上限なしのrequest schemaを最小実装した
- [x] 2026-09-05: 新規受入10件とBonsai request・adapter・HTTP・orchestration・履歴のfocused 159件をGREENにした
- [x] 2026-09-05: 標準offline gateとBACKEND・REQUIREMENTS・SECURITY・ISSUES・NEXT-STEPS・WORKLOG・CHANGELOG・README・REFERENCESを同期した
- [x] 2026-09-05: 送信先、4 calls、300秒・response上限、credential・費用・保存範囲を提示して明示承認を得た後、使用済みCSVをdevelopment regressionとして再実行した。4件全てが約300秒で `request_failed` となった

### 受入条件と検証

| 段階 | 確認 | 期待結果 |
|---|---|---|
| RED | request・diagnostic test | 現行bodyの `response_format` 不在、`max_tokens` 存在、安全なfailure stage不在を理由に失敗する |
| request | canonical JSON | `response_format` はexact `json_object`、`max_tokens` と生成用Schemaは不在、request digestへ新契約を結ぶ |
| response | strict parse | 正常応答は従来どおり受理し、不正応答は固定messageと安全なstageだけを返す。truncationを別stageにする |
| security | 本文非保持 | raw marker、検索文、field名・値、内部例外がexception、repr、serialized modelへ残らない |
| regression | focused・標準offline gate | request、adapter、HTTP、orchestration、全offline test、Ruff、Markdown、差分検査が成功する |
| local regression | 使用済みCSV 4 cases | 別途承認後にexact 4 calls、retry 0で実行し、独立holdoutではなくdevelopment regressionとして記録する |

REDは `uv run --frozen --offline --no-sync pytest -q` に、canonical request、安全なHTTP metadata分類、6種類のresponse診断に関する対象nodeを列挙して実行した。終了statusは1、10件失敗であった。request側はapplication token上限を省略した新しい呼出しを現行関数が受理せず、adapter側は `BonsaiResponseDiagnostic` と段階付きerrorが未実装であるため失敗した。import・依存・fixture・構文の失敗ではない。RED時点のtest SHA-256は `tests/test_search_v2_bonsai_request.py` が `f640535745a9f668fc5f64e0724b363a3034659ecf98d96524de46c85ec6ac72`、`tests/test_search_v2_bonsai_adapter.py` が `21c933f4c35601c9ed3d5e2d40416edded91117001734f702daca0d6e93da66a` である。

同じtest内容によるGREENは10 passed、Bonsai adapter・request・HTTP・typed adapter・orchestration・history snapshotのfocused回帰は159 passedである。最終標準gateはlock 79 packages、Ruff check成功、Ruff format 193 files、offline pytest 1628 passed / 9 skipped / 1 deselected、現行Markdown 16 files・local link 1119件・anchor 718件・heading 1409件・fence 197組、`git diff --check` 成功である。最終文書追記後にもMarkdownと差分検査を再実行する。

最終SHA-256は `bonsai_adapter.py` が `01ccf94168c9583ab6aa3f06d88e607d8fd1363b1622559ada14671c37843421`、`bonsai_request.py` が `b0a0f44ee8921d812cb0ede2753737cb5cdd9de27736dec3c96c110989586b16`、`orchestrator.py` が `dded3a5369a4111b342abd2468ffa5245d529453f78181bc6cc8e814df61afd1` である。受入testのSHA-256はREDから変更していない。

### セキュリティ、互換性、データ

public error本文とfail-closed parserを緩めない。diagnosticは列挙済みcode、正規化済みfinish reason、0以上の件数だけを持ち、raw responseやvalidation pathを保持しない。`max_tokens` を送らなくても、localhost限定、1-call予約、300秒timeout、1 MiB response上限、llama.cpp context windowとEOSによる停止は残る。request bodyとmodel schemaを更新するため旧request digestを新契約として受理せず、approval・runtime bindingも再計算する。

2026-09-05のCSVはEXEC-042で結果を確認済みであり、今回の修正判断にも使っている。利用者指定に従い再利用するが、未使用性を失っているため以後はdevelopment regression dataである。再評価値は同じcaseの改善確認には使えるが、未知dataへの一般化やproduction合格を証明しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-05 | parserを緩めず生成時JSON制約を追加する | 不正出力の修復は契約違反を正常扱いするため | strict Pydanticとfail-closedを維持する |
| 2026-09-05 | 最初は `json_object` を使い、現行Schemaを直接grammarへ渡さない | 同梱offline converterが現行decimal patternを処理できなかったため | llama.cpp互換の生成用Schemaは別検証後に追加する |
| 2026-09-05 | local requestからapplication `max_tokens` を外す | 利用者がlocal LLMにtoken制限不要と決定したため | timeout、response byte、context、call数の上限は維持する |
| 2026-09-05 | 同じCSVを再利用する | 利用者の明示指定 | 独立holdoutという名称・証拠能力を失い、development regressionと表示する |

### 発見事項

- llama.cpp sourceはOpenAI風 `response_format` を処理するが、同梱READMEのschema例とsourceが受けるwrapperには差がある。今回は両方が一致する `json_object` だけを使う
- output-token上限撤廃は無制限runtimeを意味しない。server context、EOS、timeout、response byte、call数が残る

### ロールバック

request schema、canonical body、orchestration config、diagnostic型と対応testを同時に戻し、EXEC-042時点のrequest digestへ戻す。旧requestと新requestを同じschema versionまたはdigestとして混在させない。local regression開始前なら外部状態はなく、server processも存在しない。

### 結果

完了。offline実装と標準gateは成功した。その後の承認済みdevelopment regressionは4件全てが300.101秒、300.104秒、300.105秒、300.066秒で `request_failed` となり、response parserへ到達しなかった。dataset digestは `cb12c4a9c608b400bdad6f8b3b1e6a8ac68907c0a152304b438e42199e872d5e`、prediction setは `1b0c2417d6be4bf9856b59c19b56b7b9890ff036821beb1ffd35c912a56e4ace`、evaluation reportは `665568a0a419e698870a686716c8c53f1eaca853dbcfc7cd7cdf527eb0525161`、assessmentは `ffe754d23fead22dee428fd15c1e33dd6a3d535e63bbb8f4a7ac83d6a4d61f57` である。coverageは適格、failed 4、ranked 0、元reportは `not_assessed`、assessmentは53 checks中45件未達の `fail` だった。server停止とport非listenを確認した。後続のEXEC-044でapplication timeoutも削除した。


## EXEC-042: 固定済み基準による未使用holdout評価

### メタデータ

- 状態: 完了（assessment `fail`）
- 作成日: 2026-09-05
- 最終更新: 2026-09-05
- 前提Plan: [EXEC-041](#exec-041-holdout品質合格ポリシーの固定)
- 関連要件: [TASK-005](#task-005-ランキング品質評価の確立)、[FR-419](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

結果を見る前に固定した `typed-ranking-holdout-acceptance-v1` を、case1からcase3および既存の実装・weight調整に使っていない非機密holdoutへ一度適用する。ローカルBonsaiによる条件抽出、固定済み商品証拠adapter、`typed-ranking-v4`、holdout集計、独立acceptance assessmentを順に実行し、条件抽出・必須条件判定・候補保持・順位品質を相殺なしで判定する。

### 対象範囲

- 対象: SHA-256 `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea` のrepository-local CSVを、2 category・各2 case・各3商品・各1 exact条件の固定入力として使う
- 対象: 登録済みの `form.orientation`、`mouse.connection`、`power.rechargeable`、`storage.compartment_count` を人間の正解条件としてcanonical化する
- 対象: `/home/llama.cpp/build/bin/llama-server` version 9294を `127.0.0.1` のみにbindし、SHA-256 `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54` のlocal Bonsai modelをCPUで使う
- 対象: 固定system prompt・strict schema・検索文だけを4回、temperature 0、各最大1,000 output token、各最大300秒、再試行なしでlocal Bonsaiへ渡す
- 対象: 商品名、観測feature、構造化値、価格、rating、review countを外部送信せずローカルで正規化し、元URL・ASIN・本文を評価reportとassessmentへ残さない
- 対象: `evaluate_holdout_predictions()` と `assess_holdout_quality()` を変更せず使用し、元reportの `quality_decision=not_assessed` と独立assessmentを両方確認する
- 対象外: acceptance policy、evaluation profile、attribute registry、Bonsai prompt、adapter、ranking weight、CSVの正解labelの変更
- 対象外: case1からcase3、画像component、CLIP、Cloudflare、Outscraper、OpenAI、Amazonへの通信、credential、課金、Windows native、browser、API、外部委託中フロントエンド

### 現在の状態

- 更新後CSVは12行、4 case、2 category、各case 3商品で、各categoryにhard contradictionとuncertainty labelを2件ずつ含む。登録済み条件、labelとrequired status、関連度grade、日付、未使用宣言の構造検査はエラー0件だった
- CSVには参照用のAmazon URLとASIN相当値が含まれるため、生値を標準出力、文書、評価artifactへ転記しない。SHA-256は匿名化として扱わない
- llama.cppとlocal modelの存在・digest、localhost healthを確認し、承認範囲どおり4件を各1回だけ実行した
- 2026-09-05に利用者から、localhost endpoint、4回・再試行なし、上限、credentialなし、費用0円、ログ・cache無効、終了時停止の条件で明示承認を得た
- 4件全てでHTTP応答は得たが、既存のstrict response境界が `bonsai_response_invalid` として拒否した。生responseを保持していないため、この評価だけから構文・schema・内容のどこが不一致だったかは確定しない
- coverageは適格であり、失敗を除外せず集計したassessmentは `fail` である。4件全てがranking前に停止したため、商品順位そのものの良否は測定できていない

### 失敗理由

| 区分 | 内容 |
|---|---|
| 確定した直接原因 | localhost Bonsaiから4件とも応答は返ったが、既存のstrict response契約が全件を `bonsai_response_invalid` として拒否した |
| strict契約の検査範囲 | HTTP status・`Content-Type`・encoding・length・body上限、UTF-8 JSONのOpenAI互換envelope、非空の `choices[0].message.content`、content全体が単一JSON objectであること、重複key・非有限数の禁止、`SearchIntentDraft` の必須field・型・extra禁止、intent正規化を順に検査する。どれか1つでも不一致なら受理しない |
| 未確定の根本原因 | どの検査で不一致になったかは確定していない。安全境界が詳細例外を同じ固定エラーへ変換し、生responseと内部例外を保存しない承認条件で実行したためである。JSON構文、前後の説明文、field不足・余分なfield、型違いなどを現時点で断定しない |
| `fail` になった経路 | 条件抽出が0件となり、4 case全てがranking前の `failed` になった。評価契約は失敗caseを除外しないため、条件・候補・判定・安全指標・順位の値が0.000000となり、固定policyの53 checks中45件が未達になった |
| 原因ではないと確認できたもの | CSVはcoverage適格でregistry keyも登録済みだったため `ineligible` ではない。ranking、画像、Cloudflare、Outscraperは開始しておらず、今回の失敗原因として評価していない。接続timeoutや再試行超過ではなく、応答受領後の契約不一致である |

### 実行順序と進捗

- [x] 更新後CSVをbyte固定し、件数、条件registry、label、required status、関連度、日付、未使用宣言を本文非表示で検証した
- [x] llama.cpp、Bonsai model、localhost bind、CPU実行、上限、保存範囲を確認し、人間の明示承認を得た
- [x] Bonsai serverをログ・prompt cache無効で起動し、4 caseを各1回だけstrict response境界へ通した。4件全てを固定失敗として記録した
- [x] CSVの商品観測値をローカルで正規化した。Bonsaiが確定した条件は0件で、4 case全てをranking開始前の `failed` 予測とした
- [x] 正解datasetと予測setを別digestへ固定し、評価reportとacceptance assessmentを生成した
- [x] 生入力を含まない結果を標準文書へ同期し、offline gateと差分検査を行った

### 受入条件と検証

| 段階 | 確認 | 期待結果 |
|---|---|---|
| source | CSV SHA-256と構成検査 | 固定digest一致、2 category・各2 case・各3商品、安全labelあり |
| Bonsai | localhostへのexact 4 calls | 各caseを1回だけ実行し、失敗やblockingも除外しない |
| evaluation | report再検証 | `quality_decision=not_assessed`、dataset・prediction・profile digest一致 |
| acceptance | 固定policy適用 | `pass`、`fail`、`ineligible` のいずれかを全checkとともに決定 |
| regression | 標準offline gate | lock、Ruff、pytest、Markdown link、差分検査が成功 |

### セキュリティとデータ

検索文は固定promptとschemaとともにlocalhostのBonsaiだけへ渡し、商品情報はLLMへ渡さない。serverは `127.0.0.1` のみにbindし、credential、外部network、retry、prompt cache、server logを使わない。実行中の生responseはメモリ内でstrict parseし、文書、test fixture、評価artifactへ保存しない。結果には固定ID、digest、status、rank、集計metric、checkだけを残す。serverは成功・失敗を問わず停止する。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-05 | 人間の正解条件をBonsai予測として流用しない | condition F1を人為的に1.0へせず、実モデルの抽出失敗を測定へ含めるため | local Bonsaiがstrict responseを返せない場合も失敗として固定する |
| 2026-09-05 | 結果を理由にpolicy、registry、prompt、weight、labelを変更しない | holdoutで調整して同じdataを再評価する漏えいを防ぐため | 改善作業へ使う場合、このdatasetをdevelopmentへ降格し、新しい未使用holdoutを必要とする |
| 2026-09-05 | 生CSVではなくdigestと集計結果だけを標準文書へ残す | URL、ASIN、検索文、商品本文を履歴へ複製しないため | 個別誤り分析は別の明示範囲でlocal-onlyに行う |

### 発見事項

- llama.cpp serverは4要求へ応答したが、全て既存のstrict Bonsai response契約で拒否された。transport到達と契約受理は別であり、localhost応答成功を条件抽出成功として扱えない
- 結果artifactを書き終えた後、一時実行runnerの表示用summaryが `blocking_case_count` の参照階層を誤って終了した。保存済みreport・assessmentを公開digest関数で再検証し、評価結果自体は確定できた。モデル呼出しは再実行していない
- 生responseを保存しない承認条件を維持したため、EXEC-042時点では今回のholdoutを再利用せず、別の合成検索文を用いたlocalhost 1-call診断を次工程とした。後続のEXEC-043で利用者が同じCSVの回帰利用を明示指定したため、この予定はdevelopment regression 4 callsへ置き換えた

### ロールバック

本評価はpolicy、registry、ranking、CSVを変更しない。途中停止時はBonsai serverを終了し、結果未確定として本Planの進捗だけを戻す。標準文書へ追加した評価記録を取り除けば、EXEC-041完了時点へ戻る。外部サービス、credential、cache、DB、画像、フロントエンドには状態を作らない。

### 結果

固定入力は2 category・4 case・12商品でcoverage適格だった。localhost Bonsaiへexact 4 callsを行い、再試行0、credential 0、外部network 0で終了し、serverも停止した。4件全てが `bonsai_response_invalid` となり、`failed_case_count=4`、`blocking_case_count=0`、`ranked_case_count=0` である。条件F1、候補precision・recall、decision accuracy、hard contradiction recall、uncertainty preservation、required status accuracy、pairwise accuracy、mean NDCGは全て0.000000となった。元reportの `quality_decision` は `not_assessed` のまま、固定assessmentは53 checks中45件未達で `fail` となった。

source SHA-256は `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea`、model SHA-256は `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54`、datasetは `76b808c0f144c9b59e5b0fc25e70a748a11829befbb41af249c60d5568d41ac7`、prediction setは `703ebd0fa15c64b2216276f0f4c078a3a193397c78615bea0cacf0ad4883bc01`、evaluation reportは `c7e6d4ce93eb29407fd1eadf559279e2c4bf373adfb61fadebf02303208f4202`、acceptance policyは `de4b17313dbcbe6bc7e032b36f8a00e59506f49a600e0e0138c748c734073db3`、assessmentは `88a4cbf234bb75e1b5c133617131b7ddb0aee6436fb424438127cf290ad13bec` である。reportとassessmentの再計算digestは一致し、一時結果JSONにURL・ASIN相当値を含まないことを確認した。必要なdigestと集計値を正本文書へ反映した後、一時JSONは削除した。

この `fail` は商品順位が悪かったことを示すのではなく、条件抽出のstrict出力を1件も受理できず、順位を測れなかったことを示す。今回のdatasetは使用済みとしてdevelopmentへ降格した。EXEC-042完了時点ではholdout外の合成入力と別の未使用holdoutを次工程としたが、後続の利用者指定によりEXEC-043では同じCSVをdevelopment regressionとして再利用する。再利用結果を独立holdout合格へ読み替えない。


## EXEC-041: holdout品質合格ポリシーの固定

### メタデータ

- 状態: 完了
- 作成日: 2026-09-05
- 最終更新: 2026-09-05
- 前提Plan: [EXEC-040](#exec-040-未使用holdoutの評価契約と集計境界)
- 関連要件: [TASK-005](#task-005-ランキング品質評価の確立)、[FR-419](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

未使用holdoutの内容や結果を見る前に、`typed-ranking-v4` の品質合否を決める固定基準を、既存評価reportとは独立したstrict・frozenなpolicyとdigestへ固定する。全体値と全categoryが安全重視の全基準を満たした場合だけ `pass` とし、評価dataの構成不足を品質不合格と混同せず `ineligible` として分離する。

### 対象範囲

- 対象: `src/search_v2/holdout_acceptance.py` に固定policy、check、assessment、domain-separated SHA-256、判定関数、固定errorを実装する
- 対象: policyを `typed-ranking-holdout-v1` のprofile digestと `typed-ranking-v4` のprofile digestへ固定する
- 対象: coverage適格性、各categoryのhard contradiction・uncertainty label最低1件、blocking・failed 0件を必須にする
- 対象: 条件F1、候補precision・recall、decision accuracy、hard contradiction recall、uncertainty preservation、required status accuracy、pairwise accuracy、NDCGを全体・全categoryでAND判定する
- 対象: report、policy、assessmentを別digestへ結び、固定順checkだけをserializableな判定artifactへ保持する
- 対象: 合成fixtureだけを使うRED→GREEN、境界値、category隠蔽、構成不足、改ざん、本文非保持、決定性、非network test
- 対象外: 既存 `HoldoutEvaluationReport.quality_decision` とschema 1.0の変更
- 対象外: case1からcase3、実holdoutの作成・閲覧・採点、画像component、CLIP、独立4方向参照、ranking weight、registryの変更
- 対象外: Bonsai、Cloudflare、Outscraper、OpenAI、Amazon画像host、credential、課金、network、Windows実機、browser、legacy現行検索、API、外部委託中フロントエンド、AIレビューハーネス、commit、push

### 現在の状態と未確認事項

- EXEC-040は正解・予測・reportを分離し、case・category・全体の品質指標とcoverage適格性を計算するが、品質合否は常に `not_assessed` である
- reportには判定に必要な件数、micro値、case macro値があり、各category summaryを直接判定すればreport schemaを変更せずcategory間の隠蔽を防げる
- case1からcase3は設計用development setであり、本Planのtestや品質判断へ流用しない
- 実holdoutが未受領なので、本Planで確認できるのは合成fixtureに対する判定契約・境界値・改ざん拒否だけである

### 受入条件

- [x] policy ID、schema、評価profile digest、ranking profile digest、metric桁数、全閾値、全category必須、category別安全label最低件数を固定し、変更をpolicy digestへ反映する
- [x] 既存reportをexact typeとして再検証し、report digest、dataset digest、prediction set digest、ranking profile digestをassessmentへ結ぶ
- [x] coverage不適格または各categoryのhard contradiction・uncertainty label不足を `ineligible` とする
- [x] 構成適格時は全体と各categoryへ同じ品質基準を適用し、1件でも未達なら `fail`、全件達成時だけ `pass` とする
- [x] blocking・failedは0件、hard contradiction・uncertainty・required statusは1.0を要求し、他の固定閾値をepsilonなしで比較する
- [x] checkは固定順のscope、category、metric、operator、観測値、基準値、成否だけを保持し、検索文、商品本文、ASIN、provider response、生errorを保持しない
- [x] 元のreportは `quality_decision=not_assessed` のまま変更せず、policy assessmentと混同しない
- [x] 非canonical順序、型coercion、未対応profile、digest差し替え、check・decision改ざんを再検証またはdigest差で検出する
- [x] provider client、file reader、network、画像runtime、動的import、callbackを追加しない
- [x] focused、全v2、offline全体、lock、Ruff、Python 3.10 AST、Markdown、差分検査が成功する

### 固定品質基準

全項目をANDで判定し、加重平均で未達を相殺しない。全体summaryと各category summaryについて、micro・case macroが存在する項目は両方を判定する。

| 項目 | 合格条件 |
|---|---:|
| blocking case | 0件 |
| failed case | 0件 |
| condition F1 | micro・case macroとも0.90以上 |
| candidate precision | 0.85以上 |
| candidate recall | micro・case macroとも0.90以上 |
| decision accuracy | micro・case macroとも0.90以上 |
| hard contradiction recall | 1.00 |
| uncertainty preservation | 1.00 |
| required status accuracy | micro・case macroとも1.00 |
| pairwise accuracy | micro・case macroとも0.85以上 |
| mean NDCG | 0.90以上 |

### 実行順序と進捗

- [x] 2026-09-05: EXEC-040、TASK-005、FR-419、TD-008、現行metric・digest・文書境界を確認した
- [x] 2026-09-05: 安全重視、全category必須、各categoryの安全label必須、通常decision accuracy 0.90を人間判断として固定した
- [x] 2026-09-05: 本Planを作成し、実holdout非閲覧、既存report不変、独立assessment、非network境界を固定した
- [x] 2026-09-05: 新moduleを参照するcontract・threshold・eligibility・tamper testを追加し、module未実装によるREDとtest SHA-256を記録した
- [x] 2026-09-05: strict policy、固定check、3状態assessment、canonical digestを最小実装した
- [x] 2026-09-05: 合成fixtureで境界値、全体値によるcategory隠蔽拒否、blocking・failed、安全label不足、本文非保持を監査した
- [x] 2026-09-05: focused、全v2、offline全体、lock、Ruff、Python 3.10 AST、Markdown、差分検査を実行した
- [x] 2026-09-05: 関連文書と再開位置を同期し、本Planを完了した

### 検証計画

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_holdout_acceptance.py` | moduleまたは公開契約不足を理由に失敗する | exit 2、`ModuleNotFoundError: No module named 'src.search_v2.holdout_acceptance'` |
| focused | holdout acceptance・evaluation test | 全件成功 | 44 passed |
| 全v2 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_*.py` | 全件成功 | 883 passed / 9 skipped |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | 全件成功 | 1620 passed / 9 skipped / 1 deselected |
| 静的 | lock、Ruff check・format、Python 3.10 AST | error 0件 | lock 79 packages、Ruff 193 files、AST 193 files、全て成功 |
| 文書・差分 | 現行Markdown検査、AGENTS目次、`git diff --check` | 欠落・差分error 0件 | Markdown 4 passed、16 files・local link 1091件・anchor 692件・heading 1379件・fence 197組、目次15件、diff成功 |

### セキュリティ・データ・互換性

assessmentは固定ID、digest、限定されたmetric名、件数、比率、比較結果だけを保持する。検索文、生provider response、商品名・説明・ASIN、画像byte・URL、credential、個人情報、元Excel metadataを保存しない。SHA-256は入力本文の匿名化を保証しないため、holdout自体は非機密の代表dataだけを使い、出所・分割日・利用条件・未使用宣言を人間が別途管理する。

既存evaluation report、ranking、proposal、registry、case1からcase3を変更せず、新moduleがread-onlyにreportを再検証する。policy assessmentの `pass` は固定合成またはholdout dataに対する基準達成だけを表し、実provider、production E2E、未知利用者query全般、画像rankingの品質を証明しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-05 | raw evaluation reportを変更せず、別assessmentで `pass`・`fail`・`ineligible` を返す | 計測結果と後付け可能な用途別判断を分離し、EXEC-040の `not_assessed` 契約を維持するため | evaluation schema自体を改版する場合だけ新profileで見直す |
| 2026-09-05 | 全体と全categoryの全基準をAND判定する | 件数の多いcategoryや高い別metricで弱いcategory・安全指標を隠さないため | category別SLOが必要になれば別policy IDで明示する |
| 2026-09-05 | 安全指標とrequired statusを1.0、condition・candidate recall・decision・NDCGを0.90、candidate precision・pairwiseを0.85とする | 人間が実結果を見る前に安全重視の許容失敗を選択したため | 実結果を理由に同じpolicyを書き換えず、変更時は新policy IDと別holdoutで評価する |
| 2026-09-05 | 各categoryにhard contradictionとuncertainty labelを最低1件ずつ要求する | category別安全性を該当labelなしで合格表示しないため | 該当概念を定義できないcategoryが判明した場合は、結果を見る前にcategory適用規則を新policyへ固定する |

### ロールバック

本Planで追加するacceptance module・testと、実装状態を更新する標準文書だけを取り除けばEXEC-040完了時点へ戻る。既存holdout evaluation、typed ranking、registry、case1からcase3、model、画像、cache、履歴、外部状態は変更しない。

### 結果

完了。`holdout_acceptance.py` に安全重視の固定policy、全体・全categoryの固定順check、`pass`・`fail`・`ineligible` の独立assessment、policy・assessmentのdomain-separated digestを追加した。元のevaluation reportと `quality_decision=not_assessed` は変更していない。

実装前RED test SHA-256は `1991103bca3de644a6b421b4340c7ab25839bd91d0f2271cbc891f2bd41994cc`、最終moduleは `2c023e746a4c0f79c501000c364efe4932fd422fd70f9bcfe18105275f5b9238`、最終testは `29c5ccfb32dab99afdde3ef4fd9f825992f36ea8219d396b64ce81ad642e8f9d`、両fileのmanifest hashは `1aec6558492367d589055a59b00635fe035e81ca5f99dd2046cb6758ed5c2426` である。

focused 44件、全v2 883件・9 skipped、offline全体1620件・9 skipped・1 deselected、lock 79 packages、Ruff・Python 3.10 AST 193件、現行Markdown 16件のlocal link 1091件・anchor 692件・heading 1379件・fence 197組、Markdown test 4件、AGENTS目次15件、差分検査が成功した。検証は合成metricだけで行った。実holdout、case1からcase3、固定ONNX、実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、Windows実機、browser、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・変更していない。この成果は判定契約の実装であり、実際の条件分解精度、未知categoryの順位品質、画像ranking採用、production E2Eを証明しない。次はcase1からcase3を除く未使用の複数category holdoutと出所・分割記録を用意し、固定済みpolicyで本評価する。


## EXEC-040: 未使用holdoutの評価契約と集計境界

### メタデータ

- 状態: 完了
- 作成日: 2026-09-04
- 最終更新: 2026-09-04
- 前提Plan: [EXEC-039](#exec-039-型付きranking-v4のoffline検索経路移行)
- 関連要件: [TASK-005](#task-005-ランキング品質評価の確立)、[FR-417](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-419](REQUIREMENTS.md#35-次期検索フロー-v2)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

case1からcase3を設計・調整に使ったdevelopment setとして固定したまま、未知データ用の正解artifactと予測artifactを分離し、型付き条件の抽出、商品ごとの裁定、安全側の必須状態、候補網羅、総合順位を別々に再現可能な指標へ集計する。実holdoutを受領する前に入力schema、digest、失敗の数え方、case・category集計を固定し、結果を見てから都合よく対象や計算方法を変えない境界を作る。

### 対象範囲

- 対象: `src/search_v2/holdout_evaluation.py` に、strict・extra-forbid・frozenな評価profile、正解dataset、予測set、case・category・全体reportを実装する
- 対象: 正解datasetはholdout宣言、非個人のprovenance reference ID、case ID、category、query language、source input digest、canonicalなexact条件、商品digest、期待decision、関連度gradeを持つ
- 対象: 予測setは `ranked`・`blocking`・`failed` を区別し、ready proposalと `TypedRankedProductBatch` を入口で再検証して、artifact digest、条件identity、商品digest、decision状態、必須状態、順位だけへ投影する
- 対象: 条件抽出precision・recall・F1、候補precision・recall、decision exact accuracy、hard contradiction recall、uncertainty preservation、required status accuracy、strict pairwise順位一致、full-list NDCGを固定式で計算する
- 対象: case別、category別、全caseのlabel microとcase macroを併記し、件数の多いcategoryだけで全体値を押し上げない
- 対象: blocked・failed・候補欠落を分母から除かず0点または不正解として数え、unexpected条件・商品もprecisionへ反映する
- 対象: 評価profileは最低2 category、各2 case、各3商品、各1 exact条件を本評価の構成要件とし、小さい合成fixtureはreport可能でも `coverage_eligible=false` とする
- 対象: dataset・prediction・report・profileをdomain-separated SHA-256へ結び、改ざん・順序差し替え・profile不一致を固定errorで拒否する
- 対象: 合成intent・商品・proposal・rankingだけを使うRED→GREEN、改ざん、失敗集計、決定性、非network test
- 対象外: case1からcase3のlabel・画像・score変更、実holdoutの作成・閲覧・採点、品質の合否判定、weightまたはregistry変更
- 対象外: 画像component、独立4方向参照、CLIP実行、為替鮮度の評価。これらは対応dataと事前基準を持つ別Planで扱う
- 対象外: Bonsai、Cloudflare、Outscraper、OpenAI、Amazon画像host、credential、課金、network、browser、legacy現行検索、API、外部委託中フロントエンド、AIレビューハーネス、commit、push

### 現在の状態と未確認事項

- `typed-ranking-v4` は条件proposal、全商品のdecision・required status、固定score、順位を持ち、offline検索と表示履歴へ接続済みである
- case1からcase3は設計判断後のdevelopment characterizationであり、未知categoryへの一般化を示さない
- repositoryにはholdout専用の正解・予測schema、条件identity、blocked・failedを含む集計、NDCG・category macro reportが存在しなかった
- 実データが未受領なので、本Planで確認できるのは合成fixtureに対する契約・計算・改ざん拒否だけである。holdout宣言が本当に未使用かはコードだけで証明できず、出所・分割・事前固定の人間記録を別途必要とする

### 受入条件

- [x] profileはmetric version、rounding、本評価の最低構成、固定 `typed-ranking-v4` digest、画像無効、予測投影versionを保持し、変更をdigestへ反映する
- [x] 正解datasetと予測setは別model・別digestで、case ID・source input・runtime artifact・ranking profileを再照合し、case1からcase3という既知development IDをholdoutとして受理しない
- [x] 正解条件は固定registryでcanonicalな非semantic条件だけを受理し、条件IDを除いたidentityで予測条件と比較する
- [x] 各正解商品は全正解条件のdecision labelをexactに1件ずつ持ち、商品digest・grade・case順序の重複・欠落を拒否する
- [x] ranked予測はready proposalとv4 batchを一致させ、blocking・failedはranked batchを持たず、生例外、検索文、商品本文をserializable予測へ保存しない
- [x] 条件、候補、decision、hard contradiction、uncertainty、required status、pairwise順位、NDCGを固定式でcase別に計算する
- [x] blocked・failed、条件・商品欠落、unexpected条件・商品が指標から消えず、都合のよい成功caseだけを集計できない
- [x] category別と全体のmicro・macroを決定的順序で返し、小規模fixtureを本評価合格と表示しない
- [x] case・条件・商品・categoryのcanonical順序を強制し、同じcanonical入力から同じdigest・reportを返し、label・予測・profile・report改ざんを再検証またはdigest差で検出する
- [x] provider client、file reader、network、画像runtime、動的import、callbackを追加せず、case1からcase3、ranking profile、registry、現行画面を変更しない
- [x] focused、全v2、offline全体、lock、Ruff、Python 3.10 AST、Markdown、差分検査が成功する

### 実行順序と進捗

- [x] 2026-09-04: TASK-005、TD-008、typed requirement・decision・ranking contract、既存case1からcase3の診断とExecution Plan規約を確認した
- [x] 2026-09-04: 本Planを作成し、正解・予測分離、失敗を除外しない集計、画像・実holdout非対象、合否未判定を固定した
- [x] 2026-09-04: 新moduleを参照するcontract・metric・tamper・failure testを追加し、module不在によるREDを記録した
- [x] 2026-09-04: strict model、canonical digest、生本文を除く予測投影、case metric、category・overall aggregationを最小実装した
- [x] 2026-09-04: 合成fixtureで完全一致、条件過不足、商品欠落、blocking・failed、同点grade、NDCG、coverage eligibility、予測JSONの本文非保持を監査した
- [x] 2026-09-04: focused、全v2、offline全体、lock、Ruff、Python 3.10 AST、Markdown、差分検査を実行した
- [x] 2026-09-04: 関連文書と再開位置を同期し、本Planを完了した

### 検証計画

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | 新規holdout evaluation test | module未実装または契約不足を原因に失敗する | `ModuleNotFoundError: No module named 'src.search_v2.holdout_evaluation'` |
| focused | holdout evaluation、typed ranking、typed requirements、requirement evaluation test | 全件成功 | 117 passed |
| 全v2 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_*.py` | 全件成功 | 854 passed / 9 skipped |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | 全件成功 | 1591 passed / 9 skipped / 1 deselected |
| 静的 | lock、Ruff check・format、Python 3.10 AST | error 0件 | lock 79 packages、Ruff 191 files、AST 191 files、全て成功 |
| 文書・差分 | 現行Markdown検査、AGENTS目次、`git diff --check` | 欠落・差分error 0件 | Markdown 4 passed、16 files・local link 1081件・anchor 682件・heading 1363件・fence 197組、目次15件、diff成功 |

### セキュリティ・データ・互換性

評価artifactへ保存する識別子はrepository用ID、canonical digest、限定された状態・件数・比率だけにする。予測builderへ渡したruntime artifactは再検証後にdigest・条件identity・商品digest・decision・必須状態・順位だけへ投影し、利用者の検索文、生provider response、商品名・説明・ASIN、画像byte、URL、郵便番号、credential、個人名、元Excel metadataを保持しない。正解商品はnormalized product digestで予測へ結び、reportには商品本文を複製しない。固定errorだけを公開し、validation exceptionや生入力をmessageへ連結しない。

既存ranking、proposal、商品、case1からcase3のfixtureを変更せず、評価moduleがread-onlyに再検証する。holdoutというroleとdevelopment ID拒否は誤混入を減らす契約であり、未知データだった事実を暗号学的に証明しない。実評価前にprovenance、利用条件、分割日、評価profile・合否基準を人間が事前固定する。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-04 | 正解datasetと予測setを別artifact・別digestにする | ranking入力へ正解gradeやdecisionを混ぜず、評価時の差し替えを検出しやすくするため | blind評価serverが必要になれば、label非公開・時刻証明を持つ別境界へ拡張する |
| 2026-09-04 | blocked・failedを除外せず、条件抽出以外の品質を0または不正解として数える | 成功caseだけの平均で全体品質を過大表示しないため | provider可用性とalgorithm品質を分ける場合も、両値を併記し全case値を残す |
| 2026-09-04 | 条件exact判定と総合順位を別指標にし、画像・semantic条件を本profileへ含めない | 現行画像componentは無効で、広い外観scoreからexact属性を補完しない責務分離を維持するため | 専用画像evaluatorと独立4方向参照を受領した時点で別profileを作る |
| 2026-09-04 | coverage適格性だけを判定し、品質のpass・fail閾値は実装しない | 実holdout結果を見る前に人間が用途と許容riskに応じて基準を固定すべきで、現時点の任意値を合格条件へしないため | 実データを開く前の別Planでacceptance policyとdigestを固定する |

### 発見事項

- 条件抽出の誤り自体をprecision・recallとして測る必要があるため、正解datasetは「期待するintent digest」へ予測を一致させない。代わりに同じ入力だったことをsource input digestで照合し、予測側のintent・query・proposal・rankingは相互のruntime digestで検証する。
- 初期実装では予測modelが完全なintent・proposal・商品batchを保持していた。評価artifactの保存境界を監査し、公開builder内だけで完全artifactを再検証した後、digest・状態・順位だけを持つ `digests-states-ranks-only-v1` へ投影する形に変更した。
- coverage適格性と品質合否は別である。最低2 category・各2 case等を満たしても `quality_decision` は `not_assessed` のままであり、任意の閾値をこのPlanで作っていない。

### ロールバック

本Planで追加するholdout evaluation module・testと、実装状態を更新する標準文書だけを取り除けばEXEC-039完了時点へ戻る。typed ranking、registry、case1からcase3、model、画像、cache、履歴、外部状態は変更しない。

### 結果

完了。`holdout_evaluation.py` にprofile、正解dataset、本文非保持の予測set、case・category・全体report、domain-separated digest、条件・候補・裁定・安全状態・順位の各指標を追加した。実装前RED testのSHA-256は `bb10e1de4b866442845e55fffd9d4effa3e98ea0f0f6cd18fc7abb839a5aec70`、最終moduleは `de45c86e092d2c4c164b0d13ad0288e3c8e355eb62ed9c3295490590777e0782`、最終testは `6fb8392efee52683aa1a6368f7255304ed664443d6ee9f48d1eee157bb85da31`、両fileのmanifest hashは `5f89fb8f3c605f4188c05656cb7aa8176dd7c224d3026ed28e121562498130bf` である。

focused 117件、全v2 854件・9 skipped、offline全体1591件・9 skipped・1 deselected、lock 79 packages、Ruff・Python 3.10 AST 191件、現行Markdown 16件のlocal link 1081件・anchor 682件・heading 1363件・fence 197組、Markdown test 4件、AGENTS目次15件、差分検査が成功した。検証は合成intent、合成Outscraper商品、合成正解labelだけで行った。実holdout、case1からcase3、固定ONNX、実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・変更していない。これは評価契約と計算の実装であり、実際の条件分解精度、商品属性充足率、未知categoryの順位品質、画像rankingの採用を証明しない。次は実holdoutを開く前に用途別の品質合格基準を別Planとdigestへ固定する。

## EXEC-039: 型付きranking v4のoffline検索経路移行

### メタデータ

- 状態: 完了
- 作成日: 2026-09-04
- 最終更新: 2026-09-04
- 前提Plan: [EXEC-038](#exec-038-型付き条件ranking-v4境界)
- 関連要件: [FR-409](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-410](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-413](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-415](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-417](REQUIREMENTS.md#35-次期検索フロー-v2)、[TASK-005](#task-005-ランキング品質評価の確立)、[TASK-008](#task-008-次期検索フロー-v2-の実装)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

独立実装した `typed-ranking-v4` を、Bonsai応答後の第1確認、最終承認、検索session、Outscraper後半pipeline、30日表示用履歴へ一続きで接続する。旧ranking-v3のartifactをv4として暗黙に読み替えず、typed proposal、registry、evidence profile、ranking profile、resultを承認前から保存入力までdigestで結ぶ。

### 対象範囲

- 対象: 第1確認resultへ、intentから固定registryで再構築した `TypedRequirementProposal` を追加し、readyとblockingを区別して表示層へ渡せること
- 対象: blocking proposalを画像生成、画像なし続行、最終承認、Outscraper実行の前に拒否し、valid partial条件だけで検索を続けないこと
- 対象: search sessionへtyped proposal digestとstatusを追加し、intent planの記録・置換、全遷移、承認planへ結ぶこと
- 対象: approval runtimeへtyped proposalと固定product evidence profileを結び、`typed-ranking-v4` profileを承認digestへ含めること
- 対象: 検索後半pipelineで正規化済み商品を `rank_typed_product_batch()` へ渡し、typed batch digestだけを完了stateへ記録すること
- 対象: 表示用履歴をtyped decisionから作り、必須状態、一致、未確認・矛盾、不一致、旧negative語句を安全な表示文へ変換すること
- 対象: orchestration・approval・state・pipelineをschema 3.0、表示用履歴とSQLite `user_version` を2へ更新し、旧schemaを固定errorで拒否すること
- 対象: 新しいoffline migration test、既存fixture移行、現行正本文書と再開位置の同期
- 対象外: standalone `ranking-v3` の削除・変更、legacy `run_product_search()`、JSON cache、現行Streamlit、CLI、API、認証への接続
- 対象外: 旧offline artifactまたはSQLite履歴v1の自動変換・削除。旧DBは変更せず初期化時に拒否し、将来必要なら別の明示migrationを作る
- 対象外: 専用画像evaluator、画像component有効化、case1からcase3の再採点、holdout本評価
- 対象外: 実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネス、commit、push

### 現在の状態と未確認事項

- `IntentReview`、画像確認・回復、`SearchReview` はschema 3.0で同じtyped proposalを保持し、stateはintent・queryと同時にproposal digest・readyまたはblocking statusを保持する。blocking条件は第1確認に残すが、画像・最終承認・検索へ進めない
- `SearchApprovalPlan` とruntime digestはready proposal、固定 `typed-ranking-v4` profile、product evidence profileへ結ばれ、旧2.0 planとranking-v3 runtimeを拒否する
- `product_pipeline.py` はschema 3.0で `rank_typed_product_batch()` を呼び、`ProductSearchPipelineResult` と完了stateへv4 batch digestを記録する
- `history_snapshot.py` はtyped decisionとrequired statusからschema 2.0の表示理由を作り、SQLite `user_version=2` へ保存する。旧version 1 DBは変更せず拒否する
- これらはlegacy現行Streamlitと実providerへ未接続のoffline domainである。合成E2E成功は実Bonsai条件分解、実Outscraper属性充足、case3またはproduction順位の改善を証明しない

### 受入条件

- [x] 第1確認resultはintentから再構築可能なtyped proposalを持ち、intent・candidate set・registry・adapter profile・requirement setの差し替えを再検証で拒否する
- [x] stateはtyped proposal digestとready・blocking statusをintent・query digestと同時に保持し、どれか一部だけのsnapshot、旧2.0 snapshot、blockingからの承認遷移を拒否する
- [x] 画像生成、画像なし続行、最終確認、承認token発行、Outscraper実行まで同じready proposalを伝搬し、途中での条件差し替えを固定errorにする
- [x] approval schema 3.0はready proposal digest、固定product evidence profile、typed-ranking-v4 profileをplan digestへ結び、旧2.0 planとranking-v3 runtimeを拒否する
- [x] 後半pipeline schema 3.0はproposalとtyped profileを再検証し、`TypedRankedProductBatch` だけを返してそのdigestを完了stateへ記録する
- [x] v3 batch、blocking proposal、intent・query・商品・proposal・profileのbinding不一致はtyped ranking前に拒否し、失敗時も生商品・候補本文をerrorへ出さない
- [x] 履歴schema 2.0はtyped required statusとdecisionから利用者向けmatching・unverified・cautionを作り、raw score、weight、evidence、registry、provider metadataを表示snapshotへ複製しない
- [x] SQLite `user_version=2` は新しい表示snapshotだけを保存・再読込し、旧version 1 DBを変更・削除せず固定storage errorで拒否する
- [x] 正常結果、正常0件、ranking固定失敗、保存冪等性、owner分離、30日期限を維持し、保存再試行でproviderまたはrankingを再実行しない
- [x] provider client、network、画像runtime、動的import、callbackを追加せず、legacy検索、cache、現行画面、外部委託中フロントエンドを変更しない
- [x] focused、全v2、offline全体、lock、Ruff、Python 3.10 AST、Markdown、差分検査が成功する

### 実行順序と進捗

- [x] 2026-09-04: `DEVELOPMENT.md`、approval、state machine、orchestrator、後半pipeline、履歴snapshot・repository、typed rankingと関連testを確認した
- [x] 2026-09-04: 本Planを作成し、schema 3.0・履歴2.0、blocking fail closed、旧artifact非互換、現行画面・実provider非接続を固定した
- [x] 2026-09-04: typed proposal伝搬、v4 pipeline、履歴理由、旧schema拒否の6件を先に追加し、実装前に6 failedのREDを確認した
- [x] 2026-09-04: approval・state・orchestration・pipeline・historyを最小変更で移行し、既存fixtureを新schemaへ更新した
- [x] 2026-09-04: 改ざん、blocking、v3混入、正常0件、失敗、冪等保存、非network境界を監査した
- [x] 2026-09-04: focused、全v2、offline全体、lock、Ruff、Python 3.10 AST、Markdown、差分検査を実行した
- [x] 2026-09-04: 関連文書を現行実装・残る未接続境界へ同期し、本Planを完了した

### 検証計画

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | typed offline pipeline migration test | proposal・schema・v4 pipeline・typed履歴が未接続のため失敗する | 実装前に6 failed。proposal未伝搬、旧schema、v3 pipeline、typed履歴未接続を原因として確認 |
| focused | approval、state、orchestrator、Outscraper要求、pipeline、history、typed ranking test | 全件成功 | 121 passed |
| 全v2 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_*.py` | 全件成功 | 839 passed / 9 skipped |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | 全件成功 | 1576 passed / 9 skipped / 1 deselected |
| 静的 | lock、Ruff check・format、Python 3.10 AST | error 0件 | lock 79 packages、Ruff 189 files、AST 189 files、全て成功 |
| 文書・差分 | 現行Markdown検査、AGENTS目次、`git diff --check` | 欠落・差分error 0件 | Markdown focused 4 passed、16 files・local link 1066件・anchor 669件・heading 1347件・fence 197組、目次15件、diff成功 |

### セキュリティ・データ・互換性

Bonsai候補、商品名、商品属性、商品説明は非信頼dataである。typed proposalはBonsaiが指定できないrepository内registryとadapterで再構築し、承認・state・rankingへ本文でなくdigestを伝搬する。商品証拠と裁定はOutscraper後にlocalで作り、別LLMまたはproviderへ再送しない。履歴には表示用に正規化した条件名・値・状態だけを置き、生証拠、score、weight、内部digest、provider request、郵便番号を保存表示しない。

schema 2.0のsession・approval・pipeline artifact、ranking-v3 batch、history schema 1.0、SQLite `user_version=1` を新契約として読み替えない。検索v2は現行経路へ未接続であり、実利用者履歴の自動破棄や変換は行わない。旧DBが存在してもbyteを変更せず固定errorで停止する。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-04 | 互換modeを追加せず、offline検索契約をschema 3.0へ明示更新する | v3・v4 unionやoptional proposalは、承認済み条件と実際のrankingがずれる経路を増やすため | 現行Streamlitへ接続する前にAPI schemaと移行手順を別Planで定める |
| 2026-09-04 | blocking proposalは第1確認resultとして保持するが、state machineとorchestratorの両方で後続遷移を拒否する | 問題箇所を確認可能にしつつ、valid partialだけで画像生成や課金検索へ進ませないため | UI接続時に固定issue codeの表示文と編集・再確認操作を実装する |
| 2026-09-04 | 旧SQLite v1は自動変換せず、v2 repositoryが読込前に拒否する | v1の自由語理由からtyped decisionを復元できず、見かけだけv4へ変換すると監査不能になるため | production接続前に保持すべき実データが発生した場合は、archival/exportを含む別migrationを設計する |
| 2026-09-04 | 履歴理由はtyped decisionから作るがraw score・evidenceは表示用snapshotへ保存しない | 利用者へ順位理由を示しつつ、内部評価値・証拠artifact・provider metadataを表示契約へ固定しないため | 説明文のUXは委託frontend納品後にAPI/UI契約として別途確認する |

### 発見事項

- `approval.py` からtyped profileを通常importすると、商品正規化が認可moduleを逆参照していたため循環した。credential-freeなOutscraper要求model・builder・digestを `outscraper_contract.py` へ分離し、認可と正規化の依存方向を一方向にした。局所import、動的import、callbackは追加していない。

### ロールバック

本Planで変更するapproval、state、orchestration、pipeline、history、test、標準文書をEXEC-038完了時点へ戻す。standalone ranking-v3・typed-ranking-v4、legacy検索、cache、model、画像、外部状態は変更しない。testは一時SQLiteと合成dataだけを使い、既存の履歴DBを更新・削除しない。

### 結果

完了。schema 3.0の第1確認、承認、state、orchestration、後半pipelineへ同じready proposalと固定profileを結び、blocking条件は画像・承認・検索より前に停止する。後半pipelineは `typed-ranking-v4` のbatchだけを返し、そのdigestを完了stateへ記録する。schema 2.0の表示履歴はtyped decisionと必須状態を限定文へ変換し、SQLite `user_version=2` へ保存する。旧v3 artifact、旧2.0検索artifact、SQLite version 1は暗黙変換せず、旧DBのbyteを変えない固定errorで拒否する。

商品正規化と認可の循環は、credential-freeなOutscraper要求model・builder・digestを `outscraper_contract.py` へ分離して解消した。局所import、動的import、callback、provider client、network、画像runtimeは追加していない。変更対象15ファイルのSHA-256 manifest hashは `f7766de87775c2fda0ac9c3fc2a3afc63ddce4011ea47090ae8d852d9d22fe38` である。

focused 121件、全v2 839件、offline全体1576件、lock 79 packages、Ruff・Python 3.10 AST 189件、現行Markdown 16件のlocal link 1066件・anchor 669件・heading 1347件・fence 197組、AGENTS目次15件、差分検査が成功した。検証は合成Bonsai応答、合成Outscraper商品、in-memory state・ledger、一時SQLiteだけで行った。実Amazon画像host、実商品、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・接続していない。これはoffline契約の接続であり、実Bonsaiの条件分解品質、実Outscraperの属性充足率、case3またはproduction順位の改善を証明しない。次の通常ローカル作業は、case1からcase3をdevelopment setとして固定したまま、未使用holdoutの評価契約と集計方法を新しいExecution Planでoffline TDDすることである。

## EXEC-038: 型付き条件ranking v4境界

### メタデータ

- 状態: 完了
- 作成日: 2026-09-04
- 最終更新: 2026-09-04
- 前提Plan: [EXEC-037](#exec-037-bonsai型付き条件候補adapter)
- 関連要件: [FR-409](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-410](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-412](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-413](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-415](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-417](REQUIREMENTS.md#35-次期検索フロー-v2)、[TASK-005](#task-005-ランキング品質評価の確立)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

readyな型付き条件proposal、正規化済み商品、限定商品証拠、条件裁定、必須状態を、現行 `ranking-v3` と混同しない独立した `typed-ranking-v4` schemaへ接続する。自由語attributes scoreを型付き条件の固定分母scoreへ置き換え、必須条件の状態、一致率、希望条件一致率を総合scoreより先に比較する。

### 対象範囲

- 対象: 固定 `typed-ranking-v4` profile、schema・profile・batch digest、現行v3 source ranking digest、intent・query・normalized batch・proposal・registry・requirement set・evidence profile binding
- 対象: ready proposalの再構築照合、商品ごとの `build_product_evidence()`、全条件の `adjudicate_requirement()`、`evaluate_typed_product()`、`typed_product_sort_key()` の一括接続
- 対象: required・preferredの `match` とexcludedの `mismatch` だけを加点し、unknown・conflictを0点のまま固定分母へ残すtyped attributes component
- 対象: v3のtitle、price、image-disabled、review quality、negative term判定を再利用し、自由語attributes componentのscore・language・matched/missing termをv4へ持ち込まないこと
- 対象: `confirmed`、`uncertain`、`contradicted`、required ratio、preferred ratio、v4 total、response indexの順による安定順位
- 対象: 新規独立moduleとoffline test、現行正本文書と再開位置の同期
- 対象外: ranking-v3の削除・変更、`product_pipeline.py`、orchestration、state、cache、SQLite履歴、API、UIへの接続またはmigration
- 対象外: 専用画像evaluator、画像component有効化、case1からcase3のlabel・weight調整、未使用holdout本評価
- 対象外: 実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネス、commit、push

### 現在の状態と未確認事項

- `ranking-v3` は自由語attributes componentを持ち、総合scoreとresponse indexだけで並べる。typed requirement、evidence、decision、required statusを参照しない
- `typed_product_sort_key()` は必須状態を先に比較できるが、既存scoreを引数に取る独立関数であり、ranking batch schemaへ未接続である
- Bonsai候補adapterと商品証拠adapterはoffline domainとして存在するが、blocking proposalをranking前に拒否する一括境界と、商品ごとの証拠生成・裁定・評価・順位付けを結ぶresultはない
- 本Planの合成商品成功は、実Bonsaiの条件分解品質、実Outscraperの属性充足率、case3またはproduction順位の改善を証明しない

### 受入条件

- [x] v4の公開入口はintent、query plan、normalized product batch、typed proposal、固定profileを再検証し、proposalをintentとregistryから再構築して完全一致しない入力を固定errorで拒否する
- [x] blocking proposalは商品証拠生成やrankingを開始せず拒否し、valid partial requirementだけで続行しない
- [x] 各商品について同じrequirement setから限定商品証拠、全条件decision、typed evaluationを決定的に作り、product・intent・query・batch・proposal・registry・profile digestへ結ぶ
- [x] typed attributes scoreは検索全体のregistry weightを固定分母とし、required・preferredのmatchとexcludedのmismatchだけを加点する。unknown・conflictを欠損componentとして除外しない
- [x] v4 totalはtitle、typed attributes、price、image、review qualityの固定weightを使い、imageを無効、review qualityを唯一の最小weightに維持する。自由語attributes scoreを使わない
- [x] 全候補を残したまま、必須状態、required ratio、preferred ratio、v4 total、response indexの順で並べ、低いprice・review・titleまたは高い旧attributes scoreが明示的な必須不一致を逆転させない
- [x] requirementなしではtyped attributesをnot requestedとして除外し、同じ他componentなら現行v3と同じ安定順を維持する
- [x] v4 schema、profile、batch digestはv3とdomain separationし、旧ranking batch、cache、履歴をv4として読み替えない
- [x] resultと固定errorのreprへ商品本文、Bonsai候補本文、上流ambiguity、URL、生証拠artifactを露出しない
- [x] provider client、LLM、network、画像runtime、動的import、callbackを追加せず、現行pipeline・state・cache・履歴・フロントエンドを変更しない
- [x] focused、全v2、offline全体、lock、Ruff、Python 3.10 AST、Markdown、差分検査が成功する

### 実行順序と進捗

- [x] 2026-09-04: `DEVELOPMENT.md`、ranking-v3、typed condition・evidence・decision・sort key、両adapter、現行pipelineと未接続境界を確認した
- [x] 2026-09-04: 本Planを作成し、v3維持、自由語attributes置換、固定分母、required status先行、pipeline・UI非接続を固定した
- [x] 2026-09-04: v4 profile・result・binding、blocking、score、stable order、非network境界のREDを追加した
- [x] 2026-09-04: 最小実装でGREENにし、改ざん・順序・欠損・excluded・空条件・旧schema拒否を監査した
- [x] 2026-09-04: focused、全v2、offline全体、lock、Ruff、Python 3.10 AST、Markdown、差分検査を実行した
- [x] 2026-09-04: 関連文書を現行実装・残る未接続境界へ同期し、本Planを完了した

### 検証計画

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | 新規typed ranking v4 test | module・schema・接続不足で失敗する | collectionで `ModuleNotFoundError: No module named 'src.search_v2.typed_ranking'`、終了2 |
| focused | 新規test、typed intent・requirements・product evidence・evaluation、ranking v3 test | 全件成功 | 140 passed |
| 全v2 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_*.py` | 全件成功 | 834 passed / 9 skipped |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | 全件成功 | 1571 passed / 9 skipped / 1 deselected |
| 静的 | lock、Ruff check・format、Python 3.10 AST | error 0件 | lock 79 packages、Ruff 188 files、AST 188 files、全て成功 |
| 文書・差分 | 現行Markdown検査、AGENTS目次、`git diff --check` | 欠落・差分error 0件 | Markdown focused 4 passed、16 files・local link 1043件・anchor 651件・heading 1333件・fence 197組、目次15件、diff成功 |

### セキュリティ・データ・互換性

商品本文とBonsai候補は非信頼dataであり、registry、evaluator、weight、module、URL、command、prompt、toolを選ばせない。v4はrepository内の固定registry、固定product evidence profile、固定v3 source profile、固定v4 profileだけを使い、商品情報をproviderまたはLLMへ再送しない。商品、証拠、条件、各profileはdigestで結び、本文・URL・生artifactを固定errorやreprへ複製しない。schema version、profile ID、hash domainをv3から変更し、現行cache・SQLiteへ保存しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-04 | ranking-v3を直接変更せず、独立 `typed-ranking-v4` を追加する | 現行offline pipeline、state、cache、履歴のv3 bindingを壊さず、新旧schemaを誤読しないため | v4をpipelineへ接続する後続Planでstate・history migrationを別途定義する |
| 2026-09-04 | v3からtitle・price・image-disabled・review quality・negativeだけを再利用し、自由語attributesを捨てる | exact条件の語句一致とtyped evidenceを二重加点せず、unknownを商品ごとの欠損再正規化で有利にしないため | holdoutでtyped coverageが不足する場合も自由語への暗黙fallbackはせずregistry・parserをversion付きで拡張する |
| 2026-09-04 | excluded条件は観測値が条件にmismatchした場合を満足として加点する | 「避けたい値ではない」ことをtyped componentへ反映しつつ、excludedのmatchを必須矛盾として最優先で下げるため | excluded unknown・conflictは加点せずuncertainに維持する |

### 発見事項

- v3は利用可能なcomponentだけへweightを再正規化するため、自由語attributesが欠損した商品でも他componentの比率が上がる。v4ではtyped attributesを検索条件全体の固定分母で採点し、候補ごとのunknown・conflictを分母から外さないことで、属性を観測できない商品が相対的に有利になる経路を閉じた。
- v3の総合scoreだけでは高いreview・price・title scoreが必須条件の不一致を上回り得る。合成商品ではv3の先頭が必須不一致となる配置を作り、v4が `confirmed`、`uncertain`、`contradicted` の順へ直すことを固定した。
- source v3 batchを全面的に信用せず、公開入口でintent、query、商品、proposal、profileを再検証し、proposalと全商品評価を再構築してからdigestを結ばないと、旧schemaや改ざん済み内訳をv4として誤読できる。result modelの再検証でも同じ再構築を行う。
- 合成fixtureの成功は型付き契約と順位規則の再現であり、実Bonsaiの条件分解、実Outscraper属性の充足、case3またはproduction順位の改善を示さない。

### ロールバック

新しいtyped ranking module・testと本Planで変更した文書だけを削除し、EXEC-037完了時点へ戻す。ranking-v3、pipeline、cache、SQLite、model、画像、外部状態は変更しないため、データ復旧や外部rollbackは不要である。

### 結果

完了。`typed_ranking.py` に固定 `typed-ranking-v4` profile、score breakdown、商品result、batch resultと公開ranking入口を追加した。ready proposalをintentと固定registryから再構築し、blockingまたは不一致ならsource ranking・証拠生成前に固定errorで停止する。各商品について限定証拠、全条件裁定、typed evaluationを作り、必須状態、required ratio、preferred ratio、v4 total、response indexで安定順位を決定する。

typed attributesはrequired・preferredのmatchとexcludedのmismatchだけを加点し、unknown・conflictも含めたregistry weightを固定分母とする。v3からはtitle、price、無効なimage、最小weightのreview quality、negative判定だけを再利用し、自由語attributesのscore・language・matched term・missing termをv4へ持ち込まない。schema version、profile ID、hash domain、batch digestはv3から分離し、result再検証で商品、証拠、評価、score、順位の差し替えを拒否する。

最終SHA-256は `typed_ranking.py` が `b81b9c25d5b4d0fbde44f87c356c021e90bbe19004be4d6e96b2a0d2ff82cf8b`、対応testが `65b154f14cb8adf41eecd44e7f3fb4d4ddf98bbde9cfac2cdc3e742366bdc896` である。focused 140件、全v2 834件、offline全体1571件、lock 79 packages、Ruff・Python 3.10 AST 188件を確認した。文書・差分検査の最終値は本節の検証表と [WORKLOG.md](WORKLOG.md) に記録する。

検証は合成intent、query、商品とlocal domainだけで行った。実Amazon画像host、実商品、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・接続していない。現行ranking-v3、`product_pipeline.py`、orchestration、state、cache、SQLite履歴、API、UIも変更していない。次の通常ローカル作業は、独立v4を第1確認・検索後半pipeline・state・履歴へschema migration付きで接続する境界を、新しいExecution Planでoffline TDDすることである。

## EXEC-037: Bonsai型付き条件候補adapter

### メタデータ

- 状態: 完了
- 作成日: 2026-09-04
- 最終更新: 2026-09-04
- 前提Plan: [EXEC-036](#exec-036-観測商品から型付き証拠へのadapter)
- 関連要件: [FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-413](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-414](REQUIREMENTS.md#35-次期検索フロー-v2)、[TASK-005](#task-005-ランキング品質評価の確立)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

既存の1回のBonsai strict intent応答へ、attribute key、operator、JSON-nativeなtyped expected value、strengthから成る条件候補を追加する。Bonsai出力をそのまま実行契約にせず、repository内のtrusted registryだけで `TypedRequirement` へ正規化し、未知key、registry不整合、semantic hard条件、重複等を暗黙に破棄・文字列化せず、固定codeを持つ確認待ちへ戻す。

### 対象範囲

- 対象: `SearchIntentDraft` の必須 `typed_conditions` field、JSON-nativeなstrict candidate union、Bonsai promptの候補出力規則、既存response schema digestへのbinding
- 対象: 固定adapter profile、intent・candidate set・registry・requirement set・profile digest、候補順から作るローカルrequirement ID、candidateごとのtrusted registry正規化、partial resultと固定blocking issue
- 対象: unknown attribute、known attributeに対する型・operator・unit・値不整合、semanticのrequired・excluded指定、正規化後の重複、上流blocking ambiguityを `blocking` statusへすること
- 対象: 新規adapter moduleとoffline test、既存のstrict response・request・intent fixture、prompt、現行正本文書と再開位置の同期
- 対象外: evaluator ID・実行module・weight・priorityのBonsai出力、候補からの動的registry作成、自由文字列fallback、追加のBonsai call、実model起動・意味品質評価
- 対象外: 第1確認state、ranking-v3・product pipeline・orchestration・cache・履歴・API・UIへの接続、専用画像evaluator、画像ranking有効化
- 対象外: 実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネス、commit、push

### 現在の状態と未確認事項

- 現行 `SearchIntentDraft` は色、feature、required・preferred・negative termを持つが、attribute key、value type、operator、strengthを1条件として結ぶfieldを持たない
- 現行Bonsai response adapterはcontent全体をstrict schemaへ検証し、schema digestをrequest・provenanceへ結ぶ。新fieldを同じschemaへ追加するとmock request digestとfixtureは変わるが、別call・別providerは不要である
- `TypedRequirementDraft` のDecimalはPython `Decimal` を要求するため、JSONから直接信頼modelへ入れない。Bonsai候補では有限桁のdecimal文字列だけを受け、ローカルadapterで `Decimal` へ変換してregistry正規化する
- このPlanの合成応答成功は、Bonsai-8Bが実際に条件を正しく分解すること、利用者の意図を網羅すること、case3またはproduction順位を改善することを証明しない

### 受入条件

- [x] Bonsai candidate schemaは全field必須・extra禁止・strictなdiscriminated unionであり、evaluator、module、model path、URL、command、weight、priority、registry digestを受け取らない
- [x] `typed_conditions` は既存の1回のstrict intent応答へ含まれ、prompt・schema・response digestでprovenanceへ結ばれる。欠落・unknown field・不正型は既存の固定response errorになる
- [x] local adapterはintent、registry、profileを公開入口で再検証し、候補順から決定的IDを付け、`normalize_typed_requirements()` だけでtrusted `TypedRequirement` を作る
- [x] unknown key、known keyに対する型・operator・unit・値不整合、semantic hard条件、正規化後の重複を固定blocking issueへし、候補を自由文字列やsoft条件へ暗黙変換しない
- [x] 上流intentにblocking ambiguityがあれば、候補が全て正規でも結果を `blocking` にする。blocking中のvalidなpartial requirementは保持するが、readyとして扱わない
- [x] resultはintent・candidate set・registry・requirement set・profile digestへ結び、candidate本文・上流ambiguity messageを固定error・reprへ露出しない
- [x] adapterはprovider client、LLM、network、画像、動的import、callbackを持たず、同じ入力から同じ順序・digestを返す
- [x] 現行ranking-v3、pipeline、cache、履歴、画像component、フロントエンドを変更せず、focused・全v2・offline全体・静的・文書・差分検査が成功する

### 実行順序と進捗

- [x] 2026-09-04: `DEVELOPMENT.md`、既存Bonsai strict response・request・prompt、intent、typed requirement domainを確認した
- [x] 2026-09-04: 本Planを作成し、既存1-call schemaへの候補追加、local registry最終決定、外部通信・ranking・UI非接続を固定した
- [x] 2026-09-04: candidate schema、strict response、normalization、blocking issue、digest、非LLM境界のREDを追加した
- [x] 2026-09-04: 既存fixtureを新しい必須fieldへ移行し、テストを弱めず最小adapter実装でGREENにした
- [x] 2026-09-04: focused、全v2、offline全体、lock、Ruff、Python 3.10 AST、Markdown、差分検査を実行した
- [x] 2026-09-04: 関連文書を現行実装・残る未接続境界へ同期し、本Planを完了した

### 検証計画

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | 新規typed intent adapter testと既存strict response test | schema・adapter未実装または契約不足で失敗する | stubに対して18 failed / 1 passed。RED test SHA-256 `3a79d5c4cba8597105829d4319593141914687b9e354364462c364bf7feea0e4` |
| prompt型整合の補足RED | registryとpromptのvalue typeが一致することを確認する | 不整合時に失敗し、修正後に成功 | `appearance.style` がsemanticでなくenumと読める説明に対して1 failed / 18 deselected、修正後1 passed / 18 deselected |
| focused | 新規test、typed requirement、intent、Bonsai response・request test | 全件成功 | 151 passed |
| 全v2 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_*.py` | 全件成功 | 814 passed / 9 skipped |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | 全件成功 | 1551 passed / 9 skipped / 1 deselected |
| 静的 | lock、Ruff check・format、Python 3.10 AST | error 0件 | lock 79 packages、Ruff 186 files、AST 186 files、全て成功 |
| 文書・差分 | 現行Markdown検査、AGENTS目次、`git diff --check` | 欠落・差分error 0件 | Markdown focused 4 passed、16 files・local link 1021件・anchor 636件・heading 1319件・fence 197組、目次15件、diff成功 |

### セキュリティ・データ・互換性

利用者入力とBonsai candidateは非信頼dataであり、registry、evaluator、module、URL、command、prompt、toolを選ばせない。候補を含むintentは既存response上限内で、公開resultは本文ではなくdigestと正規化済みrequirement、固定issue codeだけを持つ。`typed_conditions` 追加でSearchIntentDraftのstrict JSON Schemaとrequest digestは変わるため、既存合成fixtureを同時に移行するが、現行Streamlit・legacy Bonsai client・cache・SQLite schemaは変更しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-04 | 型付き条件候補を別のBonsai callではなく既存strict intent応答へ追加する | 同じ利用者入力を重複送信せず、既存の1-call利用量・schema・response provenance境界を再利用するため | 実modelの出力上限・品質が不足する場合も、追加callは費用・承認・migrationを別Planで審査する |
| 2026-09-04 | Bonsai candidateとtrusted `TypedRequirementDraft` を別modelにする | JSON decimalと非信頼keyを受けつつ、Python `Decimal` とregistry bindingを要求するtrusted domainを弱めないため | candidate schema変更時はintent schema digest、prompt、fixtureを同時更新する |
| 2026-09-04 | invalid candidateは全応答を修復せず、valid partialと固定blocking issueへ分ける | 1条件の不整合を黙って落とさず、他の確認可能な条件も失わずに利用者へ修正を求めるため | 第1確認へ接続するときにissue codeからallowlist済み表示文を定義する |

### 発見事項

- Bonsai用candidateとtrusted `TypedRequirementDraft` を分けることで、JSONのdecimal文字列や日本語aliasを受けても、registry正規化前の値をtrusted domainへ直接入れずに済む。
- 正規化後に同一となる候補を重複として止めないと、同じ条件が複数weightとして数えられる。2件目以降をfixed issueにし、最初のvalid requirementだけをpartial resultへ残した。
- 初期promptでは `appearance.style` のcanonical labelをenum値と同じ列へ記載しており、registryのsemantic型と読み分けにくかった。semantic、`similar_to`、preferredの組合せを独立した規則へ修正し、prompt回帰で固定した。
- 合成strict応答はschema、adapter、bindingを検証できるが、実Bonsaiが利用者の条件を漏れなく適切な重要度へ分ける意味品質は測れない。実model評価はranking接続とは別の承認済みfixture評価を必要とする。

### ロールバック

新しいcandidate field・adapter module・test・prompt規則を削除し、既存fixtureと本Planで変更した文書状態をEXEC-036完了時点へ戻す。現行pipeline、cache、SQLite、model、画像、外部状態は変更しないため、データ復旧や外部rollbackは不要である。

### 結果

完了。既存1回のBonsai strict intent応答へ最大64件のJSON-nativeな型付き条件候補を追加し、ローカルadapterが候補順のIDを付け、repository内registryだけでtrusted requirementまたは固定blocking issueへ変換する境界を実装した。unknown key、不正な型・operator・unit・値、semantic hard条件、正規化後の重複、上流ambiguityは暗黙fallbackせず、valid partialがあっても `blocking` のままにする。prompt、schema、intent、candidate set、registry、requirement set、adapter profileはdigestへ結んだ。

最終SHA-256は `intent.py` が `cdc5747b057cffa3ace119e228c4c7856f4700e63d437571d9935969286ff137`、`typed_intent_adapter.py` が `6f78e18359304efb97e212901f1d8882b058f16f013e5b1df1c5ef32f989d0bb`、`bonsai_intent_prompt.txt` が `7a16394361bca1bfddd5605c28d237a31cbd0ed519c25e50e9e7c3ef84601310`、対応testが `1b4f3640bd3cc7ee9cfd11b835b5e748400927091778c0cf8b61c00efa22b17a` である。

検証は合成Bonsai応答とlocal domainだけで行った。実Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、実Amazon候補、browser、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・接続していない。現行ranking-v3、pipeline、cache、履歴、画像componentも未接続であり、実modelの条件分解品質、case3またはproduction順位の改善を示さない。次の通常ローカル作業は、型付き条件、商品証拠、裁定、必須状態を新しいranking schemaへ接続する境界を、新しいExecution Planでoffline TDDすることである。

## EXEC-036: 観測商品から型付き証拠へのadapter

### メタデータ

- 状態: 完了
- 作成日: 2026-09-04
- 最終更新: 2026-09-04
- 前提Plan: [EXEC-035](#exec-035-型付き条件と証拠裁定の最小domain実装)
- 関連要件: [FR-407](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-415](REQUIREMENTS.md#35-次期検索フロー-v2)、[TASK-005](#task-005-ランキング品質評価の確立)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)

### 目的

検証済みOutscraper応答から作られた `NormalizedProductCandidate` について、明示的に観測された構造化属性と、商品名に現れる限定した完全表現だけを、EXEC-035の `EvidenceObservation` へ決定的に変換する。値がないこと、表現がないこと、parserが対応していないことを反対値へ変換せず、商品情報をLLMへ再送しない証拠抽出境界を作る。

### 対象範囲

- 対象: strictなadapter profileとdigest、正規化済み商品digest、requirement・registry・product・profileへ結んだ証拠tuple、構造化 `color`、固定feature語彙、商品名のbounded exact語彙、収納口数と幅の明示label付き数値表現
- 対象: 同じsource内の複数値を保持して後段の `conflict` 裁定へ渡すこと、source欠損・未検出・未対応をそれぞれ固定unknown reasonへ変換すること、説明文を解析しないこと
- 対象: 新規 `src/search_v2/product_evidence.py`、対応するoffline test、現行正本文書と再開位置の同期
- 対象外: Bonsaiから `TypedRequirementDraft` を作るadapter、曖昧条件の確認画面、専用画像evaluator、CLIP score、ranking-v3・product pipeline・orchestration・cache・履歴への接続、画像ranking有効化
- 対象外: 実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネス、commit、push

### 現在の状態と未確認事項

- `product_normalization.py` はproviderから明示されたbrand、categories、color、material、featuresを `ObservedProductAttributes` へ保持し、欠損を `unknown` にしている。titleとdescriptionは別fieldであり、属性を推測していない
- EXEC-035のdomainはtypedな条件と観測値を受け取れば裁定できるが、現行商品modelから `EvidenceObservation` を作るadapterを持たない
- 現行product modelには収納口数、向き、接続方式、幅の専用fieldがない。このPlanでは、専用color field、feature item全体の固定語彙一致、title内の固定語彙または属性labelに隣接する有界数値だけを許可し、descriptionや一般的な意味推論へ広げない
- adapter成功はOutscraperが実際に十分な属性を返すこと、商品名の表現が正しいこと、case3またはproduction順位が改善することを証明しない

### 受入条件

- [x] `NormalizedProductCandidate`、typed requirement tuple、trusted registry、固定adapter profileを公開入口で再検証し、結果をproduct・requirement・registry・profile digestへ結ぶ
- [x] `appearance.color` は専用の観測済みcolor fieldだけをstructured証拠とし、その他のenum・boolean・numericは固定されたfeature全体または明示label付き表現だけを読む
- [x] title parserは固定語彙の境界と最長一致を使い、英単語の部分一致、短い日本語色名の埋込み、否定表現内の肯定語を誤検出しない
- [x] 収納口数と幅は属性名に隣接するASCII decimalだけを有界に解釈し、一般の商品個数・寸法・価格を条件値へ流用しない
- [x] 同sourceで異なる明示値があれば両方を保持して `conflict` にでき、structured証拠がtitle証拠より優先される
- [x] 欠損・語句不在・未対応を `unknown` にし、単なるtitle語句不在、未登録値、description内の語句を `mismatch` または観測値へ変換しない
- [x] moduleはprovider client、LLM、network、画像をimportせず、商品本文または生値を固定error・reprへ露出しない
- [x] 現行intent、ranking-v3、pipeline、cache、履歴、画像componentを変更せず、focused・全v2・offline全体・静的・文書・差分検査が成功する

### 実行順序と進捗

- [x] 2026-09-04: `DEVELOPMENT.md`、EXEC-035、`product_normalization.py`、typed requirement・evidence domainと関連testを確認した
- [x] 2026-09-04: 本Planを作成し、商品証拠adapterだけ、外部通信なし、Bonsai・ranking・画像・フロントエンド非接続を固定した
- [x] 2026-09-04: 構造化属性、title exact、unknown、conflict、digest、非LLM境界のREDを追加した
- [x] 2026-09-04: テストを弱めず最小adapter実装でGREENにした
- [x] 2026-09-04: 数値単位、短い日本語alias、source上限、本文非露出の補足REDを追加し、誤検出とresource境界を修正した
- [x] 2026-09-04: focused、全v2、offline全体、lock、Ruff、Python 3.10 AST、Markdown、差分検査を実行した
- [x] 2026-09-04: 関連文書を現行実装・残る未接続境界へ同期し、本Planを完了した

### 検証計画

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | 新規product evidence focused test | adapter未実装または契約不足で失敗する | 初期stubに対して19 failed、終了1。RED test SHA-256 `e6c1ed9a3fda9e173cf03fcbb8870ee985d0ace32757ee55a7ba09798944b578` |
| 補足RED | 誤った数値単位、短い日本語alias、非正規順、未登録color、source上限、本文非露出 | 各欠陥を実装修正前に再現する | 最初に3 failed / 21 deselected、追加監査で1 failed / 4 passed / 22 deselectedを確認し、修正後は対象5 passed / 22 deselected |
| focused | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_product_evidence.py tests/test_search_v2_requirement_evaluation.py tests/test_search_v2_typed_requirements.py` | 全件成功 | 63 passed |
| 全v2 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_*.py` | 全件成功 | 795 passed / 9 skipped |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | 全件成功 | 1532 passed / 9 skipped / 1 deselected |
| 静的 | lock、Ruff check・format、Python 3.10 AST | error 0件 | lock 79 packages、Ruff 184 files、AST 184 files、全て成功 |
| 文書・差分 | 現行Markdown検査、AGENTS目次、`git diff --check` | 欠落・差分error 0件 | Markdown focused 4 passed、16 files・local link 1008件・anchor 623件・heading 1305件・fence 197組、目次15件、diff成功 |

### セキュリティ・データ・互換性

商品title、description、属性は非信頼dataとして扱い、実行module、registry、evaluator、正規表現、URL、command、prompt、toolを選ばせない。parser profileとsourceごとの処理はrepository sourceへ固定し、input artifactは本文ではなくSHA-256だけを証拠へ保持する。descriptionは解析対象にせず、商品候補をBonsai、OpenAI、Cloudflareへ送らない。adapterは新しい独立moduleであり、現行serialization、cache、SQLite schemaを変更しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-04 | color専用fieldとfeatures/titleを同じstructured sourceへ混ぜず、attributeごとに入力fieldを固定する | 例えばfeature中の `red` が本体色ではなくLED色を表す場合に、専用colorと同格の誤証拠を作らないため | 専用provider fieldを追加する場合はnormalizerとprofileを同時にversion更新する |
| 2026-09-04 | title語彙は最長の重なる表現だけを採用する | `desktop_small` と `desktop`、否定句と肯定句のような内包関係で偽のconflictを作らないため | 語彙・境界を変更するときはparser profile IDと回帰fixtureを更新する |
| 2026-09-04 | 対応できないattribute/sourceも値を推測せず `evaluator_unavailable` にする | registryで許可されることと、現行商品fieldから安全に抽出できることは別だから | 専用fieldまたは有界parserを追加したPlanでunknownからobservedへ変更する |

### 発見事項

- `mouse.connection` の固定registryは「無線」を持っていたが、正規化済みfeatureで現れ得る「ワイヤレス」をaliasに持っていなかった。provider値から動的に語彙を増やさず、repository内aliasとregistry digestを更新した。
- `収納口` の直後に数があるだけでは `20cm` や `1200円` を収納口数へ誤変換できた。`収納口` にはcount単位を必須にし、明示的な `収納口数` でも既知の寸法・重量・容量・通貨単位が続く値を拒否した。
- 1文字の日本語色aliasは、別scriptの単語に埋め込まれた場合も境界が必要である。`黒bird` をunknownへ維持し、区切られた `【黒】` だけを認識する回帰testを固定した。

### ロールバック

新規adapter moduleと対応testを削除し、本Planで変更した文書状態をEXEC-035完了時点へ戻す。現行pipeline、cache、SQLite、model、画像、外部状態は変更しないため、データ復旧や外部rollbackは不要である。

### 結果

完了。`product_evidence.py` に固定adapter profile、正規化済み商品digest、product・requirement set・registry・profileへ結んだ `ProductEvidenceSet`、専用color・固定feature全体・bounded title exactからの証拠生成を実装した。構造化値をtitleより優先し、同sourceの異なる値は最大8件まで保持して後段の `conflict` へ渡す。source欠損、語句不在、未対応、未登録値を固定unknown reasonへ分け、description、一般数値、画像、provider client、LLM、networkを使わない。

最終SHA-256は `product_evidence.py` が `74bb76a4883e2dcc1bb5d4066b2b85b16c3f30bd6d40daeb1d04f024fa6f2826`、registry alias更新後の `typed_requirements.py` が `45ec569a7a999323a15300255cb43eadee4658d887ea18c1d70d7698bd56fd61`、product evidence testが `061aa9052dff763cf6aa96385634fbc1efef0e477c038e6cf06580605b610d1b` である。focused 63件、全v2 795件、offline全体1532件、lock 79 packages、Ruff・Python 3.10 AST 184 filesに成功した。現行Markdownは16 files・local link 1008件・anchor 623件・heading 1305件・fence 197組、Markdown focusedは4件、AGENTS目次は15件で、差分検査にも成功した。

検証は合成 `NormalizedProductCandidate` と固定registryだけで行った。実Amazon画像host、実商品、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・接続していない。現行intent、ranking-v3、pipeline、cache、履歴、画像componentも変更・接続していないため、case3順位またはproduction検索の改善実績ではない。次の通常ローカル作業は、Bonsaiのstrict応答からtrusted registryが受理できる型付き条件候補だけを作り、未知key・曖昧値・semantic hard条件を確認待ちへ戻すadapterを、新しいExecution Planでoffline TDDすることである。

## EXEC-035: 型付き条件と証拠裁定の最小domain実装

### メタデータ

- 状態: 完了
- 作成日: 2026-09-04
- 最終更新: 2026-09-04
- 前提Plan: [EXEC-034](#exec-034-型付き条件と証拠別ランキングの設計)
- 関連要件: [FR-413からFR-418](REQUIREMENTS.md#35-次期検索フロー-v2)、[TASK-005](#task-005-ランキング品質評価の確立)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)、[TD-011](ISSUES.md#td-011-画像取得推論の実環境検証)

### 目的

利用者が確認した条件を型・演算子・重要度へ固定し、商品について得られた証拠を `match`・`mismatch`・`unknown`・`conflict` へ決定的に裁定できる、商品カテゴリ非依存の最小domain APIを追加する。必須条件の状態を既存総合scoreより先に比較できる安定した順位keyも提供し、情報不足や明示的不一致が画像・価格・レビューの得点で隠れない実装土台を作る。

### 対象範囲

- 対象: discriminated unionによる型付き期待値・観測値、repository内の固定attribute registryとdigest、条件正規化、sourceごとの固定evaluator metadata、証拠の生成・binding・優先順位・矛盾裁定、必須状態、固定分母の一致率、候補集合に依存しない順位key
- 対象: 新規 `src/search_v2/` domain module、対応するoffline test、現行要件・設計・schema・security・管理文書の実装状態同期
- 対象外: Bonsai prompt・intent schemaへの追加、Outscraper field parser、専用画像evaluator、CLIP score、ranking-v3・product pipeline・orchestration・cache・履歴への接続、画像ranking有効化、依存追加
- 対象外: 実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンドの確認・接続、AIレビューハーネス、commit、push

### 現在の状態と未確認事項

- [EXEC-034](#exec-034-型付き条件と証拠別ランキングの設計) で、typed requirement、trusted registry、証拠4状態、生成画像を外観参照だけへ使う境界、必須状態を総合scoreより先に扱う順序を設計済みである
- 現行 `NormalizedSearchIntent`、`ObservedProductAttributes`、`ranking-v3` は型付き条件を持たず、画像componentは無効である
- 今回は純粋なdomain入力だけを扱うため、実際のBonsai応答またはOutscraper商品から条件・証拠を抽出できること、case3順位が改善すること、未使用holdoutで一般化することは確認できない
- `semantic` 条件はtypedなpreferred条件として受理できるが、CLIP連続scoreは証拠modelへ入れない。今回の4状態裁定で使えるのはregistryが許可した分類済み観測だけとし、外観類似度との結合は後続Planへ残す

### 受入条件

- [x] 値型ごとの期待値と観測値がstrictなdiscriminated unionであり、型coercion、非有限数、不正単位を拒否する
- [x] 未知attribute key、不許可operator・strength・unit・enum値を拒否し、semanticな必須・除外条件を暗黙にsoft化しない
- [x] untrustedな条件draftがevaluator、実行module、weight、registry digestを指定できず、正規化後の条件が固定registry digestへ結ばれる
- [x] 証拠source、priority、evaluator ID・versionはregistryからだけ選ばれ、観測なしを値または不一致へ変換しない
- [x] 同じ最高優先度の観測が矛盾すれば `conflict`、有効な観測がなければ `unknown`、上位観測があれば低位観測で上書きしない
- [x] 条件演算子の一致・不一致を型別に決定し、titleへの語句不在やCLIP scoreをexact属性の証拠にしない
- [x] 必須状態、必須・希望一致率、coverageの分母が検索条件全体で固定され、総合scoreより先に比較する順位keyが候補集合へ依存しない
- [x] 現行intent、ranking-v3、画像component、pipeline、cache、履歴schemaを変更せず、focused・全v2・offline全体・静的・文書・差分検査が成功する

### 実行順序と進捗

- [x] 2026-09-04: `DEVELOPMENT.md`、EXEC-034、現行intent・商品正規化・rankingと関連testを確認した
- [x] 2026-09-04: 本Planを作成し、domain-only、外部通信なし、pipeline・画像・フロントエンド非接続を固定した
- [x] 2026-09-04: strict registry・typed requirementのREDを追加し、未実装stubのschema不足で失敗することを確認した
- [x] 2026-09-04: 証拠生成・裁定・必須状態・順位keyのREDを追加し、未実装stubのschema不足で失敗することを確認した
- [x] 2026-09-04: テストを弱めず最小domain実装でGREENにした
- [x] 2026-09-04: focused、全v2、offline全体、lock、Ruff、Python 3.10 AST、Markdown、差分検査を実行した
- [x] 2026-09-04: 関連文書を現行実装・残る未接続境界へ同期し、本Planを完了した

### 検証計画

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | 新規typed requirement・evidence focused test | 新moduleがないためcollection時import errorではなく、最小stub導入後に契約不足で失敗する | 25 failed / 6 passed、終了1。typed test SHA-256 `6f17e2604554aa1c6867ce7b41a1b0de806efa1ffa67a8819b1863fc681b2166`、evidence test SHA-256 `5118e8772ea7ca8568b4b3ca15850651665e35aada1cbc92b55e42da58f95bd7` |
| focused | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_typed_requirements.py tests/test_search_v2_requirement_evaluation.py` | 全件成功 | 36 passed |
| 全v2 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_*.py` | 全件成功 | 768 passed / 9 skipped |
| offline全体 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | 全件成功 | 1505 passed / 9 skipped / 1 deselected |
| 静的 | lock、Ruff check・format、Python 3.10 AST | error 0件 | lock 79 packages、Ruff 182 files、AST 182 files、全て成功 |
| 文書・差分 | 現行Markdown検査、AGENTS目次、`git diff --check` | 欠落・差分error 0件 | Markdown focused 4 passed、16 files・local link 998件・anchor 613件・heading 1291件・fence 197組、目次15件、diff成功 |

### セキュリティ・データ・互換性

registryはPython source内の固定dataから構築し、条件draftまたは商品dataからevaluator名、module path、weight、priorityを受け取らない。evaluator IDは比較・digest用の識別子であり、dynamic importやcommand dispatchへ使わない。入力文字列・tuple件数・証拠件数を有界にし、例外へ商品title、画像URL、生provider値を含めない。新modelは同一processの一時値だけで、現行cache、SQLite、API、履歴serializationを変更しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-04 | registry、条件正規化、証拠裁定を現行intent・rankingから分離する | 既存動作とcacheを変えずにdomain契約をRED/GREENで固定するため | adapter・ranking接続は別Planでschema migrationと回帰を定義する |
| 2026-09-04 | sourceごとにevaluator metadataとpriorityをregistryへ持たせる | 商品dataやmodel出力が実行方式・優先度を選ぶ経路を作らないため | 実evaluator追加時は固定ID・version・profile digestとholdoutを必要とする |
| 2026-09-04 | CLIPの連続scoreを4状態のexact証拠へ変換しない | 広い外観類似度から個数・接続方式等を補完しない設計を維持するため | semantic score統合は別profileとholdoutを伴う後続Planにする |

### 発見事項

- 最初のREDはparameterizeの引数をmodule読込時にmodel化し、collection中の `ValidationError` で停止したため、有効なREDとして採用しなかった。fixtureをテスト本体内で生成する形へ修正し、25件が未実装schema・functionを理由に失敗するREDを再取得した。production要件やassertionは弱めていない。
- 初期GREEN後、registry aliasがcanonical値を別値へ上書きできることと、正規化前の `TypedRequirement` を条件set digestへ渡せることを2 failed / 31 passedの補足REDで再現した。canonical値を優先し、digest入口でregistry正規化との完全一致を要求した。
- 証拠modelの `attribute_key` が単なる有界文字列だったため、名前空間なしkeyを1 failedの補足REDで再現し、共通の `AttributeKey` 型へ変更した。
- `Decimal("120.0")` と `Decimal("120.00")` が同値でも異なるdigestになり得ることと、過剰精度値を2 failedの補足REDで再現し、有限・精度制約とcanonical Decimal表現を固定した。

### ロールバック

新規domain moduleと対応testを削除し、本Planで変更した文書状態をEXEC-034完了時点へ戻す。現行pipeline、cache、SQLite、model、画像、外部状態は変更しないため、データ復旧や外部rollbackは不要である。

### 結果

完了。`typed_requirements.py` にstrictな型付き期待値・観測値、9 keyのrepository内registry、alias・unit正規化、registry・条件set digestを実装し、`requirement_evaluation.py` にregistryへ結んだ証拠生成、source優先順位、同順位矛盾、型別裁定、固定分母、必須状態、候補集合非依存の順位keyを実装した。最終SHA-256は順に `b760f149a91a04f73f566d42e36288487a454c23e4f0fb909eda9875c7524b76` と `8ebf4cbc533ee12eab13d099a2f26a7bfddcfe2b95b91d6bb6acca7fe07bb422`、対応testは `5a604b957b694b4b5f033754b751193c77b7c0e2d28790825eb2ce816f5940ad` と `62b0fdf7d526282e0274c92537d57ee4255adabb2b39521bce7b8cdf410297c2` である。

focused 36件、全v2 768件、offline全体1505件、lock、Ruff、Python 3.10 AST、Markdown、AGENTS目次、差分検査が成功した。実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・接続していない。現行intent、ranking-v3、pipeline、cache、履歴、画像componentも変更していないため、case3順位またはproduction検索の改善実績ではない。次の通常ローカル作業は、観測済み商品属性と限定した商品名表現を固定registryの証拠へ変換するadapterを、新しいExecution Planでoffline TDDすることである。

## EXEC-034: 型付き条件と証拠別ランキングの設計

### メタデータ

- 状態: 完了
- 作成日: 2026-09-04
- 最終更新: 2026-09-04
- 関連要件: [FR-408](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-409](REQUIREMENTS.md#35-次期検索フロー-v2)、[TASK-005](#task-005-ランキング品質評価の確立)
- 関連課題: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)、[TD-011](ISSUES.md#td-011-画像取得推論の実環境検証)

### 目的

自然文の条件を商品分野ごとの自由な文字列だけで採点せず、値の型、比較方法、重要度を持つ条件へ変換する。商品情報と商品画像から得た証拠を条件ごとに照合し、生成した4方向画像は外観の近さだけへ使う。これにより、case3で観測した「収納用品として外観が近いだけの商品が、収納口数や縦型という条件を欠いても上位になる」問題を、特定商品だけの例外規則を追加せずに扱える設計を確定する。

### 対象範囲

- 対象: 型付き条件model、商品カテゴリ別のtrusted schema registry、証拠modelと優先順位、`match`・`mismatch`・`unknown`・`conflict`、生成画像と商品画像のCLIP比較、必須条件を先に扱うranking順序、説明用の結果、段階実装・評価方法
- 対象: [BACKEND.md](BACKEND.md)、[REQUIREMENTS.md](REQUIREMENTS.md)、[DB-SCHEMA.md](DB-SCHEMA.md)、[SECURITY.md](SECURITY.md)、[DEVELOPMENT.md](DEVELOPMENT.md)、利用者向け表示と残作業の同期
- 対象外: production code、ranking profileの変更、画像rankingの有効化、学習済みfeature classifierの選定・取得、候補とは独立した4方向参照の検査、実Amazon画像host・Bonsai・Cloudflare・Outscraper、credential、課金、API、外部委託中フロントエンドの確認・接続

### 現在の状態と発見事項

- `NormalizedSearchIntent` は条件を商品名、カテゴリ、required・preferred・negative term、色、featureの文字列として保持し、属性の値型や比較演算子を持たない
- `ObservedProductAttributes` はproviderから観測したbrand、categories、color、material、featuresだけを保持し、個々の条件ごとの証拠、矛盾、確度を表せない
- 現行の固定CLIPは、4方向の各参照embeddingについて候補の最大cosineを選び、4値の平均を0〜1へ写像する。1枚の候補画像が複数方向の最大値に使われ得るため、方向別画像が揃ったことや個数・寸法・接続方式の一致は証明しない
- case3では広い外観scoreだけでnearとfarを分離できなかった。候補集合でscoreを中心化する診断は候補の追加・削除で同じ商品の点数が変わるため、production rankingには採用しない
- case3を見てから決めた条件weightや提出labelによる上限計算は、実際の商品情報・画像から属性を抽出できることや未知商品での改善を証明しない。case3は開発用とし、最終採否には未使用のholdoutを必要とする

### 受入条件

- [x] 型付き条件のfield、許可する値型・演算子、trusted registryとLLM出力の境界が定義されている
- [x] 構造化属性、商品名の限定parse、専用画像評価、CLIP外観scoreの役割と優先順位が定義されている
- [x] 証拠なしを不一致または一致へ変換せず、矛盾時の処理と説明方法が定義されている
- [x] 必須条件の明示的不一致を画像・価格・レビューの高得点で打ち消せないranking順序が定義されている
- [x] 生成画像と候補商品画像の具体的な比較式、digest binding、欠損時の扱いが定義されている
- [x] case3固有weightをproductionへ固定せず、開発用fixtureとholdout評価を分離している
- [x] 実装済み、設計済み、未実装、未検証が関連文書で区別されている
- [x] 現行Markdown検査と `git diff --check` が成功している

### 実行順序と進捗

- [x] 2026-09-04: 現行intent、商品正規化、CLIP比較、ranking v3、case3固定診断を確認した
- [x] 2026-09-04: 型付き条件と証拠別照合の内部契約を設計した
- [x] 2026-09-04: 要件、論理schema、security、利用者表示、テスト方針へ同期した
- [x] 2026-09-04: TASK-005、TD-008、TD-011、NEXT-STEPSを次の実装位置へ更新した
- [x] 2026-09-04: Markdown検査と差分検査を行い、結果と未実行境界を記録した

### 検証計画

| 対象 | 方法 | 結果 |
|---|---|---|
| 文書構造 | `uv run --frozen --offline --no-sync python tools/check_markdown_links.py` | 成功。現行16文書、local link 985件、anchor 600件、heading 1277件、fence 197組を確認した |
| 回帰test | `uv run --frozen --offline --no-sync pytest -q tests/test_markdown_links.py` | 成功。4 passed |
| 差分形式 | `git diff --check` | 成功。whitespace errorなし |
| 変更範囲 | 着手前の `git status --short` と本作業の編集記録を照合する | 既存の未コミット変更を保ち、本Planでは現行Markdown 12件だけを編集した |

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-04 | 生成画像を「正解画像」ではなく、利用者が承認した外観参照と呼ぶ | 生成物は実商品の仕様証拠ではなく、個数や接続方式を誤って描く可能性がある | 画像は広い外観scoreだけへ使い、型付き条件の真偽を上書きしない |
| 2026-09-04 | evaluatorとweightはLLM出力ではなくtrusted registryで決める | 商品文やmodel出力による任意実行・caseごとのweight調整を防ぐ | 新カテゴリはregistry entryと回帰testを追加して対応する |
| 2026-09-04 | 必須条件は3状態を含む階層で総合scoreより先に比較する | exact条件の不一致が外観、価格、レビューで隠れることを防ぐ | hard除外は行わず、利用者が全候補と不一致理由を確認できる形を初期方針とする |
| 2026-09-04 | 候補集合によるcenter・z-score正規化をproductionに使わない | 無関係な候補の追加・削除で同一商品の点数と順位理由が変わる | 固定した背景集合による校正が必要なら別Planとholdout評価を要求する |

### セキュリティ・データ・互換性

型付き条件と商品側証拠はstrict modelとprofile digestへ結び、商品title、description、画像を命令として扱わない。商品候補をBonsai、OpenAI、Cloudflareへ送り返さず、画像は既存server-side proxyと固定local runtimeを通す。現行intent、ranking v3、cache、履歴schemaは本Planで変更しない。後続実装は新schema versionと移行・rollbackを別Planで定義する。

### ロールバック

本Planは文書だけを変更する。関連文書のEXEC-034差分を取り消せば、production code、model、fixture、外部状態へ影響せず設計前の状態へ戻せる。

### 結果

完了。型付き条件、trusted registry、証拠別裁定、必須状態を先に比較するranking、生成画像を外観参照だけへ使う比較境界を現行文書へ同期した。production code、ranking-v3、画像componentの無効状態、model、fixture、依存関係は変更していない。検証は現行Markdown 16件の静的検査と4件の回帰test、差分形式検査に限定し、実provider、実画像host、browser、外部委託中フロントエンドは実行・確認・接続していない。

## EXEC-033: case3固定候補と自己参照除外CLIP診断

### メタデータ

- タスクID: `TASK-005`
- 状態: 完了
- 作成日: 2026-09-04
- 最終更新日: 2026-09-04
- 前提Plan: [EXEC-032](#exec-032-全体保持clip前処理とcase3準備)
- 関連要件: `FR-408`、`NFR-208`（[REQUIREMENTS.md](REQUIREMENTS.md)）
- 関連負債: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)、[TD-011](ISSUES.md#td-011-画像取得推論の実環境検証)
- 関連設計: [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)

### 目的

利用者が `tests/img/case3/` に提出した第3条件を、画像byte、画像で判定する特徴、商品名・説明で判定する特徴、期待順位、rating、review countへ再現可能に結び付ける。候補とは独立した4方向参照がないため、case2と同じ自己参照除外cluster診断に限定し、全体保持・モデル平均余白CLIP profileがcase3をどの程度分離するかを測定する。

### 対象範囲

- 必須条件を「収納口2つ、小型（卓上）、縦、収納」へ固定する
- `tests/img/case3/near/n1.png`〜`n8.png` と `far/f1.png`〜`f12.png` のpath、label、SHA-256、視覚・構造化特徴、期待順位、rating、review countを固定manifestへ転記する
- workbookの数式、macro、外部link、個人metadataの有無をread-only確認し、評価に必要な非個人データだけをtestへ転記する
- 20枚を目視し、収納用品、開口・仕切り、縦横形状という大分類が提出表と矛盾しないことを確認する。収納口の厳密な個数は利用者の提出labelを正本とし、画像から商品仕様を補完しない
- near候補は自分以外のnear 7枚、far候補はnear 8枚に対する平均CLIP scoreで限定診断し、near/far pairwise AUCと期待順位のpairwise concordanceを記録する
- 現行要件、設計、課題、次工程、作業・変更履歴を診断結果と同じ境界へ同期する

### 対象外

- near候補を正面・左・右・背面の独立参照画像として扱うこと
- 単一queryのcluster診断をproductionの4方向score、カテゴリ横断品質、総合商品順位または採用基準へ読み替えること
- `case3.xlsx` の作成者・更新者metadataをtest、文書、artifact、Gitまたは配布物へ転記すること
- 画像rankingの有効化、image weight、CLIP model、前処理profile、production rankingまたは現行pipelineの変更
- 画像から「小型（卓上）」その他の商品仕様を推定・補完すること
- 実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネス、commit、push

### 現在の状態と発見事項

- workbookは1 sheet・A1:G22、数式0件、macro・外部link・hyperlinkなしで、作成者・更新者metadataは存在する。testはworkbookをruntime fixtureとして読まない
- 提出値はnear 8枚・far 12枚、視覚特徴「収納口2つ、縦、収納」、構造化特徴「小型（卓上）」、期待順位1〜10、rating 0.0〜5.0、review count 0〜666である
- 20枚は単一frame PNGで、source SHA-256とpixel digestが全て異なり、pHash距離5以下の重複はない
- 目視では全20枚が収納用品であり、開口・仕切りと縦横形状の差を確認した。一部は2個を超える仕切りまたは開口に見えるため、「収納口2つ」は提出labelとして固定し、厳密な商品仕様の独立検証とは扱わない
- case3専用の独立4方向参照は0枚であり、productionと同じ4-reference scoreは構成できない
- 画像componentはdisabledである

### 受入条件

- [x] case3の20 path・label・SHA-256と提出属性を固定manifestで再現できる
- [x] 視覚特徴と構造化特徴を分離し、画像から未確認の商品仕様を補完しない
- [x] 候補と独立した4方向参照が0枚であることをtestへ固定する
- [x] source byte、pixel、pHash重複を検査できる
- [x] near自身を参照から除外した固定ONNX診断を再実行し、記録scoreと一致する
- [x] AUCと期待順位concordanceを成功testで再現し、品質合格として扱わない
- [x] case1・case2の固定値と画像ranking disabledを維持する
- [x] 標準offline gate、Markdown、Python 3.10 AST、AGENTS目次、差分形式を最終状態で確認する

### 実行順序と進捗

- [x] 2026-09-04: workbookの構造と20画像をread-only確認し、個人metadataを出力・転記しない境界を決めた。
- [x] 2026-09-04: 全画像を目視し、提出された視覚特徴を商品仕様の独立検証へ読み替えない方針を決めた。
- [x] 2026-09-04: case3固定manifest、属性、期待順位、独立参照不足を通常offline testへ固定した。
- [x] 2026-09-04: repository-local固定ONNXで自己参照除外scoreを初回測定し、回帰値へ固定した。
- [x] 2026-09-04: case1〜case3の通常testと明示CLIP runtimeを実行した。
- [x] 2026-09-04: 標準文書をcase3結果と次の入力要件へ同期した。
- [x] 2026-09-04: 最終の全offline gateを実行し、件数とhashを記録した。

### 検証計画

| 対象 | コマンドまたは方法 | 期待結果 |
|---|---|---|
| 入力契約 | case3通常quality test | 20候補、属性、期待順位、rating・review count、独立参照0枚をmodel読込なしで再現する |
| 初回characterization | case3 quality testへ `--run-clip-runtime` を明示 | 自己参照除外score、AUC、期待順位concordanceを採取する |
| 固定回帰 | 同じ明示runtime testを再実行 | 初回に記録した全scoreと指標へ絶対誤差1e-8以内で一致する |
| 既存case | case1・case2 quality test | 既存の固定値、既知のxfail、画像ranking disabledを維持する |
| 標準gate | lock、Ruff、全v2、offline全体、Markdown、AST、AGENTS目次、`git diff --check` | 全て終了0。実provider通信は行わない |

productionの振る舞いは変更せず、提出fixtureのcharacterization testだけを追加するため、production code変更に対するTDD RED/GREENは適用しない。初回の実ONNX観測値と、その値を固定した後の再実行を分けて記録する。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-04 | case3も自己参照除外cluster診断に限定する | 候補とは独立した4方向参照がなく、near自身とのcosineでscoreを水増ししないため | case3専用の独立4方向参照を受領したらproductionと同じscoreで再評価する |
| 2026-09-04 | workbookの特徴labelと期待順位を利用者提出値として固定する | 画像だけでは寸法や厳密な開口数などの商品仕様を確定できないため | 商品名・説明または仕様表を受領した場合に構造化属性として別途検証する |
| 2026-09-04 | rating 0・review count 0を欠損推定せず提出値のまま記録する | 0が未評価か欠損かをworkbookだけから判定できないため | source上の欠損表現が明示された場合にだけ `None` への変更を検討する |
| 2026-09-04 | AUC・concordanceの高低を成功testへ固定する | characterizationの役割は観測値の再現であり、独立参照なしの値を採用基準へ使わないため | 複数queryと独立参照の本評価で事前基準を定める |

### セキュリティ・データ・互換性

- Excelの個人metadata、画像の入手元情報、利用者データをtest出力や文書へ複製しない。原本は変更・削除せず、Git・配布可否もこのPlanでは判断しない。
- testはlocal PNGとrepository-local固定ONNXだけを使い、外部通信、DNS、credential、provider費用を必要としない。
- production code、ranking profile、runtime profile digest、model asset、現行pipelineを変更しない。
- 委託フロントエンドは未納品として、内容確認、起動、画面確認、test、backend接続を行わない。

### ロールバック

case3用testを取り除き、標準文書をEXEC-032完了時点へ戻せば実装差分を除去できる。ただし利用者が配置した `tests/img/case3/` と `case3.xlsx` は利用者資産なので削除・上書きしない。

### 結果

完了。`tests/test_search_v2_image_similarity_quality_case3.py` に20候補の相対path・SHA-256、提出属性、期待順位、rating、review count、独立参照0枚を固定した。固定ONNXによる自己参照除外診断はnear平均0.858911962、far平均0.858491016、near中央値0.861306486、far中央値0.863038093、near/far AUC 0.468750000（45/96組）、期待順位一致80/173となり、画像単独では分離できなかった。case3通常testは2 passed / 2 skipped、明示runtimeは4 passed、case1からcase3の通常testは9 passed / 7 skipped、明示runtimeは15 passed / 1 xfailedだった。xfailはcase1の既知のAUC 0.759259259だけである。

test SHA-256は `8cc5143e33bb00dd039e3513c1931ee9bcd6e0ba00e1c44dd67c397258f74c23`。全v2は732 passed / 9 skipped、offline全体は1469 passed / 9 skipped / 1 deselected、lockは79 packages、RuffとPython 3.10 ASTは178 files、現行Markdownは16 files・local link 969件・anchor 589件・heading 1254件・fence 195組、AGENTS目次15件、`git diff --check` は成功した。production code、ranking profile、model assetは変更せず、画像componentはdisabledのままである。次はcase2・case3の候補とは独立した正面・左・右・背面参照を受領後、複数queryの本評価基準を事前固定して進める。

## EXEC-032: 全体保持CLIP前処理とcase3準備

### メタデータ

- タスクID: `TASK-005`
- 状態: 完了
- 作成日: 2026-09-04
- 最終更新日: 2026-09-04
- 前提Plan: [EXEC-031](#exec-031-case2固定候補と自己参照除外clip診断)
- 関連要件: `FR-408`、`NFR-208`（[REQUIREMENTS.md](REQUIREMENTS.md)）
- 関連負債: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)、[TD-011](ISSUES.md#td-011-画像取得推論の実環境検証)
- 関連設計: [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)

### 目的

利用者の決定に従い、固定CLIPの224×224入力を、短辺拡大後の中央切り抜きから、縦横比を維持して画像全体を224×224内へ収める方式へ変更する。残り領域はCLIPの正規化平均値で埋め、余白そのものが強い特徴にならないようにする。前処理変更をruntime digestへ結び、case1・case2を新しいscoreへ再固定した後、未受領のcase3を安全に追加できる状態へ進める。

### 対象範囲

- landscapeは幅、portraitは高さを224pxへ合わせ、もう一辺を縦横比どおり縮小して中央配置する
- 余白はCLIP image meanを正規化前のfloat32 tensorへ入れ、正規化後に0となるよう固定する
- Bicubic、RGB、NCHW float32、最大4枚、CPU-only ONNX、process isolationは維持する
- application固有の前処理profile IDをruntime digestへ含め、旧center-crop embeddingとの混在を拒否する
- case1・case2を同じ固定ONNXで再計測し、score、AUC、期待順位concordance、既知の基準未達を更新する
- case3の配置有無を確認し、未受領なら必要入力と再開位置を標準文書へ明記する

### 対象外

- repository-localの固定ONNX 3 assetまたはupstream `preprocessor_config.json` のbyte変更
- 画像rankingの有効化、image weight、ranking profile、現行pipelineの変更
- object detection、背景除去、OCR、画像内容からの構造化属性推定
- case3の画像・属性・期待順位・独立4方向参照を推測または生成すること
- 実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、委託フロントエンド、AIレビューハーネス、commit、push

### 現在の状態

- current profileは縦横比を維持して画像全体を224×224内へ収め、残りをCLIP image meanで埋める。旧center-crop profileは後続embeddingへ混在できない
- offline比較ではモデル平均余白方式によりcase2 AUCが0.392857143から0.642857143、期待順位concordanceが21/53から27/53へ改善した
- 同じ比較でcase1の元AUCは0.790123457から0.759259259、接続方式を除く視覚評価AUCは0.961538462から0.928571429へ低下した。利用者はこのtrade-offを確認した上で全体保持方式を採用した
- case3 directoryはまだ存在せず、画像、視覚・構造化特徴、期待順位、rating、review count、候補とは独立した4方向参照は未受領である
- 画像componentはdisabledであり、前処理移行後も有効化しない

### 受入条件

- [x] landscape・portrait画像の全体が縦横比を維持して224×224内へ収まる
- [x] 余白が正規化後の全channelで0となり、画像は中央配置される
- [x] 同じ入力からbit-identicalなNCHW float32 tensorを再現できる
- [x] preprocessing profile IDを変更するとruntime digestも変わり、旧embeddingと混在しない
- [x] case1・case2の固定ONNX scoreと指標を新profileへ更新する
- [x] case1の既知の基準未達、case2の限定診断、画像ranking disabledを維持する
- [x] case3未受領を明示し、必要入力を `NEXT-STEPS.md` へ同期する
- [x] 標準offline gate、明示CLIP runtime、Markdown、AST、差分検査を通す

### 実行順序と進捗

- [x] 2026-09-04: center crop、全体保持、直接変形、2-view併用をcase1・case2でread-only比較した。
- [x] 2026-09-04: 利用者がモデル平均余白による全体保持方式を採用すると決定した。
- [x] 2026-09-04: 全体保持、中央配置、正規化後0余白、runtime digest更新のRED testを追加した。
- [x] 2026-09-04: 最小実装で前処理とprofile bindingを変更した。
- [x] 2026-09-04: case1・case2を固定ONNXで再計測し、固定値と回帰testを更新した。
- [x] 2026-09-04: case3受領要件と標準文書を同期した。
- [x] 2026-09-04: 全offline gateと明示CLIP runtimeを実行し、結果を記録した。

### 検証計画

| 対象 | コマンドまたは方法 | 期待結果 |
|---|---|---|
| TDD RED/GREEN | `pytest -q tests/test_search_v2_image_similarity.py tests/test_search_v2_image_similarity_onnx.py -k 'runtime_profile or preprocessor'` | 旧center crop実装に対して期待理由でREDとなり、実装後は全件成功する |
| case1・case2 | quality testを `--run-clip-runtime` 付きで実行 | 新しい固定score、AUC、concordanceへ一致し、既知のcase1基準未達だけをstrict xfailに保つ |
| process境界 | image similarity process testを明示runtime付きで実行 | 親側全体保持tensorと子process CPU encoderの契約が成功する |
| 標準gate | lock、Ruff、全v2、offline全体、Markdown、AST、AGENTS目次、`git diff --check` | 全て終了0。実provider通信は行わない |

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-04 | 224×224へ直接変形せず、縦横比を維持して全体を収める | 直接変形は形状を歪め、case2改善も小さかったため | 可変解像度modelへ移行する場合に再評価する |
| 2026-09-04 | 余白を白または画像端色でなくCLIP image meanにする | read-only比較でcase2 AUCが最も高く、正規化後0にできるため | 複数query評価で余白色への依存が見つかった場合に見直す |
| 2026-09-04 | upstream preprocessor assetを変更せずapplication profileをdigestへ追加する | 固定assetのprovenanceを保ちつつ、実際の前処理変更をembedding identityへ反映するため | model asset自体を更新するreleaseでbundle全体を再固定する |
| 2026-09-04 | case1悪化を隠さず利用者決定として採用し、画像rankingを無効のままにする | case2改善だけを全体品質の証明にせず、後続case3・複数query評価で判断するため | 独立参照付き評価が採用基準を満たした場合だけ有効化を検討する |

### セキュリティ・データ・互換性

- 前処理は親process内の有界RGB byteだけを使い、外部I/O、OCR、network、pickleを追加しない。
- 旧runtime digestのembeddingは新profileで拒否する。現在画像componentはdisabledで、永続embedding schemaまたはcache移行は発生しない。
- model asset、利用者画像、Excelを変更・削除・再配布しない。case3の不足情報を既存caseから推測しない。
- 委託フロントエンドは未納品として確認・起動・接続しない。

### ロールバック

前処理をcenter cropへ戻し、application preprocessing profile IDとcase1・case2の固定scoreをEXEC-031時点へ戻す。固定model asset、利用者画像、Excelには変更を加えない。

### 結果

完了。全体保持・モデル平均余白の `clip-rgb-bicubic-contain-mean-pad-224-v1` を実装し、runtime profile digestを `bf5e3355bf11e924fdff2f8703e7a5331d7fd94b06f8fcde32c6083b34bddd05` へ更新した。TDDは旧実装に対して3 failed / 4 passed / 47 deselectedでRED、実装後は7 passed / 47 deselectedでGREENとなった。固定ONNXの再計測ではcase1 AUC 0.759259259、接続方式を除く視覚評価AUC 0.928571429、case2 AUC 0.642857143・期待順位一致27/53となった。case1の事前基準未達とcase2の限定診断を維持し、画像componentはdisabledのままである。明示CLIP runtimeはcore 79 passed、case1・case2 11 passed / 1 xfailed、全v2は730 passed / 7 skipped、offline全体は1467 passed / 7 skipped / 1 deselectedとなり、lock、Ruff、Markdown、Python 3.10 AST、AGENTS目次、差分検査も成功した。case3は `tests/img/` に存在せず、画像・属性・期待順位・rating・review count・候補とは独立した4方向参照の受領待ちである。

## EXEC-031: case2固定候補と自己参照除外CLIP診断

### メタデータ

- タスクID: `TASK-005`
- 状態: 完了
- 作成日: 2026-09-04
- 最終更新日: 2026-09-04
- 前提Plan: [EXEC-029](#exec-029-高評価レビュー件数を使うranking-v3)、[EXEC-030](#exec-030-画像ランキングの視覚的特徴限定)
- 関連要件: `FR-408`、`NFR-208`（[REQUIREMENTS.md](REQUIREMENTS.md)）
- 関連負債: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)、[TD-011](ISSUES.md#td-011-画像取得推論の実環境検証)
- 関連設計: [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[SEARCH-FLOW.md](../SEARCH-FLOW.md)

### 目的

利用者が `tests/img/case2/` に追加した2例目を、画像byte、視覚的特徴、画像では確定しない構造化特徴、期待順位、rating、review countへ再現可能に結び付ける。候補と独立した4方向参照がないことを明示し、near画像自身を参照に含めてscoreを水増しせず、固定ONNXによる限定的な診断と通常rankingのレビュー品質tie-breakだけを確認する。

### 対象範囲

- 検索条件を必須特徴「筒状、長い、縦、金属製、収納」、追加特徴「四角い、黒い」へ固定する
- `tests/img/case2/near/n1.png`〜`n4.png` と `tests/img/case2/far/f1.png`〜`f7.png` のpath、label、SHA-256、視覚的特徴、構造化特徴、期待順位、rating、review countを固定manifestへ転記する
- `case1` への再配置に合わせ、既存画像品質testと実process smokeの参照先を `tests/img/case1/` へ更新する
- near候補は自分以外のnear 3枚、far候補はnear 4枚に対する平均CLIP scoreで限定診断し、near/far pairwise AUCと期待順位のpairwise concordanceを記録する
- 視覚・構造化特徴が同じ組について、ratingとreview countを最小weightで使うranking v3が利用者の期待順を支えることを固定する
- 現行要件、設計、課題、次工程、作業・変更履歴を診断結果と同じ境界へ同期する

### 対象外

- case2のnear候補を、正面・左・右・背面の独立参照画像として扱うこと
- 単一queryのcluster診断をproductionの4方向score、カテゴリ横断品質、総合商品順位または採用基準へ読み替えること
- `case2.xlsx` の作成者・更新者metadataをtest、文書、artifact、Gitまたは配布物へ転記すること
- 画像rankingの有効化、image weightの変更、CLIP modelまたはproduction ranking実装の変更
- 画像から「金属製」その他の商品仕様を推定・補完すること
- 実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネス、commit、push

### 現在の状態と前提

- `case2.xlsx` にはmacroと外部linkはなかったが、作成者・更新者metadataが残っている。入力値は個人metadataを除いてtestへ転記し、testはExcelをruntime fixtureとして読まない
- 11枚は単一frame PNGで、source SHA-256、pixel digest、pHashが重複しない
- near 4枚は期待上位の候補であり、独立した4方向参照ではない。したがってcase1と同じproduction score評価を構成できない
- 自己参照を除く限定診断ではpairwise AUC 0.392857143、期待順位との順序一致21/53となり、画像score単独の採用根拠にならない
- 同じ視覚・構造化特徴を持つ `n4` と `f4`、`f1` と `f2` の比較では、ranking v3のreview qualityが利用者の期待順を支える
- 画像componentは引き続きdisabledである

### 受入条件

- [x] case2の11 path・label・SHA-256と入力属性を固定manifestで再現できる
- [x] 「金属製」を構造化特徴とし、画像からの推定値と混同しない
- [x] 候補と独立した4方向参照が0枚であることをtestへ固定する
- [x] source byte、pixel、pHash重複を検査できる
- [x] near自身を参照から除外した固定ONNX診断を再実行し、記録scoreと一致する
- [x] AUC 0.392857143と期待順位concordance 21/53を成功testで再現し、品質合格として扱わない
- [x] 同一特徴2組のreview quality tie-breakが期待順と一致する
- [x] 標準offline gate、Markdown、Python 3.10 AST、AGENTS目次、差分形式を最終状態で確認する

### 実行順序と進捗

- [x] 2026-09-04: `case2.xlsx` の構造と画像11枚をofflineで確認し、個人metadataを出力・転記しない境界を決めた。
- [x] 2026-09-04: case2固定manifest、独立参照不足、診断値をmodel読込なしのtestへ固定した。
- [x] 2026-09-04: case1のpath移動を既存品質testとprocess smokeへ反映した。
- [x] 2026-09-04: repository-local固定ONNXで自己参照除外scoreを再計算した。
- [x] 2026-09-04: review qualityが同一特徴2組の期待順を支える回帰testを追加した。
- [x] 2026-09-04: 標準文書をcase2の結果と次の入力要件へ同期した。
- [x] 2026-09-04: 最終の全offline gateを実行し、件数とhashを記録した。

### 検証

| コマンドまたは方法 | 期待結果 | 状態・実測 |
|---|---|---|
| case1既存quality testをpath更新前に実行 | 利用者によるcase別再配置を再現する失敗 | 期待どおり1 failed / 7 deselected。旧loaderが `tests/img/` 直下に `near`・`far` だけを期待して失敗した |
| case1・case2の通常quality test | model読込なしでmanifest、診断値、disabled境界を固定 | 7 passed / 5 skipped |
| case1・case2の `--run-clip-runtime` | repository-local固定ONNXの実scoreが記録値へ一致 | 11 passed / 1 xfailed。xfailはcase1の既知のAUC 0.790123457だけ |
| case1実process smoke | path移動後も `spawn` process経路を維持 | 2 passed / 23 deselected |
| case2 review quality test | 同一特徴2組が期待順になる | 2 passed / 30 deselected |
| `pytest -q tests/test_search_v2_*.py` | 次期backend全体のoffline回帰が成功 | 729 passed / 7 skipped |
| `pytest -m 'not live_api'`、lock、Ruff、静的・文書・差分検査 | repository標準offline gateが成功 | 1466 passed / 7 skipped / 1 deselected、lock 79 packages、Ruff・AST 177 files、Markdown 16 files・local link 943件・anchor 567件・heading 1226件・fence 195組、AGENTS目次15件、差分検査成功 |

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-04 | near 4枚を候補と参照へ二重使用せず、各nearだけ自己参照から除外するcluster診断に限定する | 自分自身とのcosine類似度で正例scoreが不当に上がることを防ぎ、独立参照不足を隠さないため | case2専用の独立4方向参照を受領したらproductionと同じ4参照scoreで再評価する |
| 2026-09-04 | AUCと期待順位concordanceの低さを成功testへ固定する | testの役割は観測値の再現であり、基準未達を成功と偽装しないため | 複数queryの採用基準を測定前に決め、新しい独立datasetで合否を判定する |
| 2026-09-04 | `case2.xlsx` はtestの入力依存にせず、個人metadataを除く必要値だけを転記する | source workbookに作成者・更新者metadataが残り、実行再現に不要だから | 利用者が配布可能に処理した原本を明示的に提供した場合にだけfixture化を再検討する |
| 2026-09-04 | rating・review countは一致特徴候補の補助tie-breakとしてだけ確認する | review qualityは最小weightであり、視覚的・構造化適合を逆転させる主評価ではないため | 複数query総合評価で期待順位を悪化させる場合は新profile IDで重みを再評価する |

### セキュリティ・データ・互換性

- Excelの個人metadata、画像の入手元情報、利用者データをtest出力や文書へ複製しない。原本は変更・削除せず、Git・配布可否もこのPlanでは判断しない。
- testはlocal PNGとrepository-local固定ONNXだけを使い、外部通信、DNS、credential、provider費用を必要としない。
- production code、ranking profile、profile digest、model asset、現行pipelineを変更しない。追加testは画像componentがdisabledである既存契約を維持する。
- 委託フロントエンドは未納品として、内容確認、起動、画面確認、test、backend接続を行わない。

### ロールバック

`tests/test_search_v2_image_similarity_quality_case2.py` とcase2用ranking回帰を取り除き、case1 path更新を再配置前へ戻せば実装差分を除去できる。ただし利用者が配置した `tests/img/case1/`、`tests/img/case2/`、`case2.xlsx`、固定modelは利用者資産なので削除・上書きしない。文書はEXEC-030完了時点のcase1だけの状態へ戻す。

### 結果

case2の11候補を固定manifestへ結び、個人metadataを含むExcelをtest依存から外した。独立参照がないためproductionの4方向評価は実施せず、near自身を参照から除いた限定診断でAUC 0.392857143、期待順位との順序一致21/53を再現した。review qualityは同じ視覚・構造化特徴を持つ2組の期待順を支えたが、画像score単独は品質基準を満たす根拠にならず、画像componentはdisabledのままである。

case2 test SHA-256は `bf1894e9a30a46796dc8156838c1e7a899303c0cea2c38c53b4711e9734f0217`、case1 quality testは `e5deea9629a95fe7b2d037ef2206c5d84ddd73121f70a19b904c1a2bdb22c3fd`、process testは `a530c5a9502f0c106e9e37b027ce2bda0a0962ea5da87ff52a3455c52fd3f16d`、ranking testは `b8237d3a5b43b2516e0ef07e0fee1437058a2e0b2fa13cfa6c22aada20780690` である。全v2は729 passed / 7 skipped、offline全体は1466 passed / 7 skipped / 1 deselected、lockは79 packages、RuffとPython 3.10 ASTは177 files、現行Markdownは16 files・local link 943件・anchor 567件・heading 1226件・fence 195組、AGENTS目次15件、`git diff --check` は成功した。

次は別条件のcase3と、case2・case3それぞれについて候補とは別の正面・左・右・背面4方向参照を受領してから、画像ON/OFF、構造化属性、review qualityを含む複数queryの本評価を新しいPlanで行う。実provider用credentialと委託フロントエンドはまだ不要である。

## EXEC-030: 画像ランキングの視覚的特徴限定

### メタデータ

- タスクID: `TASK-005`
- 状態: 完了
- 作成日: 2026-09-04
- 最終更新日: 2026-09-04
- 前提Plan: [EXEC-026](#exec-026-単一条件の複数画像clip-characterization)、[EXEC-027](#exec-027-far画像の属性別hard-negative-characterization)、[EXEC-028](#exec-028-near画像の目視属性characterization)
- 関連要件: `FR-408`、`NFR-208`（[REQUIREMENTS.md](REQUIREMENTS.md)）
- 関連負債: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)、[TD-011](ISSUES.md#td-011-画像取得推論の実環境検証)
- 関連設計: [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[SEARCH-FLOW.md](../SEARCH-FLOW.md)

### 目的

画像ランキングを、色、外観形状、商品種別など画像で確認できる特徴だけを扱う補助評価として定義する。有線・無線は商品名とproviderから得た構造化された観測属性で判定し、画像scoreから属性を推定、補完、上書きしない。

### 対象範囲

- 画像scoreは視覚的な近さだけを表し、商品仕様の真偽または適合確率として扱わない
- 有線・無線など画像で確定できない属性はtitle・attributes componentへ残し、画像componentでhard filterしない
- near 13枚の目視manifestにあった接続方式の暫定推定を全て `None` へ訂正し、利用者指定のfar接続方式labelは構造化評価用の根拠として維持する
- 「黒い無線ゲーミングマウス」の固定scoreを、接続方式だけが異なるf2・f4・f7・f10も画像上の正例として扱う接続方式非依存の評価へ再分類する
- 元のnear 9枚・far 18枚によるAUC 0.790123457とstrict xfailは、事前条件を変えない履歴baselineとして維持する
- 要件、backend、testing、課題、次工程、作業・変更履歴を同じ責務分離へ同期する

### 対象外

- 画像rankingの有効化、ranking-v3、weight、profile digest、商品順位の変更
- 色、形状、商品種別についても画像scoreから構造化属性を新規作成すること
- 複数query、検索文から生成した実4方向参照、実Amazon候補による本受入評価
- 実画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、外部通信
- 現行Streamlit、CLI、API、外部委託中フロントエンドの確認・接続
- model・画像のGit追跡、commit、push、merge

### 現在の状態

固定4参照に対するnear候補9枚とfar 18枚の元評価は、全162組中128組が正順でAUC 0.790123457となり、事前基準0.80へ未達である。一方、farのうちf2・f4・f7・f10は色、ゲーミング用途、商品種別が対象条件と一致し、接続方式だけが有線である。接続方式を画像評価から外してこの4枚を画像上の正例へ移すと、正例13枚・負例14枚の全182組中175組が正順となり、AUCは0.961538462、正例中央値は0.942146431、負例中央値は0.843137443となる。

責務分離の数値は、まず固定済みscoreと利用者指定属性だけから再計算した。その後、同じlocal ONNX modelを明示opt-in testで再推論し、固定scoreと両評価が再現することも確認した。near側の接続方式は目視で確定できないため全13枚を未知へ訂正し、far側の接続方式は利用者指定labelとして画像観察と分離した。どちらも単一条件のlocal characterizationであり、複数条件または実商品順位の品質を示さない。

### 受入条件

1. 画像scoreの責務を視覚的特徴の補助評価へ限定し、接続方式をtitle・構造化属性で判定する契約が正本文書で一致する。
2. 画像scoreが構造化属性を推定、補完、上書きせず、接続方式をhard filterしないことを明記する。
3. near目視manifestの接続方式を全て未知とし、利用者指定のfar接続方式labelと根拠を混同しない。
4. 接続方式非依存の再分類集合がf2・f4・f7・f10だけで、AUC 0.961538462と両群の中央値を固定scoreから再現する。
5. 元のAUC 0.790123457、事前基準0.80、strict xfail、画像ranking無効を変更しない。
6. 複数query、実4方向参照、商品順位の本合格基準を、有効化前の残作業として維持する。
7. focused test、通常offline test、Ruff、現行Markdown、`git diff --check` を確認する。

### 実行順序と進捗

- [x] 2026-09-04: 利用者が、画像ランキングを視覚的特徴だけの補助評価とし、有線・無線を商品名・構造化属性で判定する方針を決定した。
- [x] 2026-09-04: 固定scoreから接続方式非依存の再分類を計算し、AUCと中央値を確認した。
- [x] 2026-09-04: 再分類集合、AUC、中央値、元baseline不変をquality testへ固定した。
- [x] 2026-09-04: near目視manifestの接続方式を全て未知へ訂正し、farの利用者指定labelと根拠を分離した。
- [x] 2026-09-04: 正本文書、課題、次の再開位置、履歴を同期した。
- [x] 2026-09-04: 回帰・静的・文書gateを実行し、結果を記録した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 現在の記録 |
|---|---|---|---|
| 再計算 | 固定済みnear・far scoreと属性manifestのpairwise比較 | 接続方式非依存AUC 0.961538462、正例中央値0.942146431、負例中央値0.843137443 | 通常focused testで再現 |
| near接続方式境界 | manifest修正前に接続方式未知を要求するfocused testを実行 | 以前の目視推定が残っているため失敗 | 1 failed / 4 passed / 3 deselected。`wireless` と `None` の不一致を確認 |
| focused | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_image_similarity_quality.py` | 通常test成功、CLIP runtimeだけskip | 5 passed / 3 skipped |
| 固定ONNX | 同quality testへ `--run-clip-runtime` を明示 | 記録score、元baseline、接続方式非依存評価を再現 | 7 passed / 1 xfailed。xfailは元AUC 0.790123457の既知未達 |
| v2回帰 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_*.py` | 既存のoffline v2境界を維持 | 725 passed / 5 skipped |
| 回帰 | `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | 外部通信なしで終了0 | 1457 passed / 5 skipped / 1 deselected |
| 静的・文書 | lock、Ruff、Python 3.10 AST、現行Markdown、`git diff --check` | error 0件 | lock 79、Ruff 174、AST 174、Markdown 16、local link 932、anchor 559、heading 1210、fence 195組、diff成功 |
| live・UI | provider API、実host、browser、委託フロントエンド | 本Planでは実行しない | 対象外 |

### 判断記録

| 日付 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-04 | 画像scoreを色、形状、商品種別など視覚的特徴だけの補助評価にする | 固定datasetでは接続方式だけが異なる4枚が高scoreで、画像から有線・無線を十分に分離できなかったため | 画像scoreから商品仕様を確定しない。構造化属性との総合順位は複数queryの本評価で別に確認する |
| 2026-09-04 | 有線・無線は商品名・構造化された観測属性で判定する | ケーブルが見えない画像だけでは無線仕様を証明できず、画像生成物も実商品仕様の証拠ではないため | providerが接続方式を返さない場合は未知を維持し、画像で補完しない |
| 2026-09-04 | near 13枚の接続方式を全て未知へ訂正し、far側のlabelは維持する | nearは画像からの暫定推定、farは利用者が提示した構造化labelであり、根拠が異なるため | 接続方式の品質評価では商品名または検証済み構造化属性を別途用意する |
| 2026-09-04 | 元のAUC未達を保持し、接続方式非依存AUCを別指標として追加する | 測定後に元のlabelを変更して事前基準へ合格したことにしないため | 次の本評価では評価責務とlabelを測定前に固定する |

### セキュリティ・データ・互換性

固定済みの数値と属性だけを文書へ記録し、画像byte、商品URL、商品ID、credential、外部responseを新たに保存・出力しない。現行ranking、profile digest、pipeline、履歴schema、UIに互換性変更はない。外部通信は行わず、model再推論はrepository-local固定ONNXを使う明示opt-in testだけに限定した。

### ロールバック

接続方式非依存のcharacterization testと、本Planに伴う標準文書差分だけを取り除けばEXEC-029完了時点へ戻る。元の画像、属性manifest、score、AUC、ranking profileは変更しない。

### 結果

完了。画像scoreを色、外観形状、商品種別など画像で確認できる特徴だけの補助評価へ限定し、有線・無線を商品名と構造化された観測属性へ分離した。scoreから構造化属性を推定、補完、上書きせず、画像componentで接続方式をhard filterしない。near 13枚の目視manifestにあった接続方式の暫定推定は全て `None` へ訂正し、far側は利用者指定labelとして根拠を分離した。

固定scoreでは、接続方式だけが異なるf2・f4・f7・f10を画像上の正例へ移し、正例13枚・負例14枚の全182組中175組が正順となった。AUC 0.961538462、正例中央値0.942146431、負例中央値0.843137443を通常offline testと固定ONNXの明示opt-in testで再現した。元のnear 9枚・far 18枚によるAUC 0.790123457、事前基準0.80、strict xfailは変更していない。

quality test SHA-256は `c44318873d3e6ffc36954fd9f74625d3c779e506ccf1917ade138f585a3881a8` である。focused 5件、固定ONNX明示実行7件、全v2 725件、offline全体1457件、lock、Ruff、Python 3.10 AST、現行Markdown、差分検査に成功した。固定ONNXでは元のAUC未達だけを1 xfailedとして維持した。

これは単一条件の責務別characterizationであり、複数query、検索文から得た4方向参照、総合商品順位、実provider、実host、Windows native、API、UIの品質を確認していない。ranking-v3と画像有効化flagは変更せず、画像rankingは無効のままである。


## EXEC-029: 高評価レビュー件数を使うranking-v3

### メタデータ

- タスクID: `TASK-005`
- 状態: 完了
- 作成日: 2026-09-04
- 最終更新日: 2026-09-04
- 前提Plan: [EXEC-011](#exec-011-決定的ランキングv2とスコア内訳)
- 関連要件: `FR-407`、`FR-409`、`FR-410`、`FR-412`（[REQUIREMENTS.md](REQUIREMENTS.md)）
- 関連負債: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)
- 関連設計: [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[DB-SCHEMA.md](DB-SCHEMA.md#48-次期ranking-batch未永続化)

### 目的

次期検索の通常ランキングへ、平均評価と総レビュー件数から作る補助componentを追加する。レビューは商品名、属性、価格、将来の画像評価より順位への影響を小さくし、欠損や低評価を高評価レビューとして扱わない決定的な `ranking-v3` 契約へ更新する。

### 対象範囲

- `NormalizedProductCandidate.rating` と `review_count` だけから、外部通信なしでレビュー補助scoreを計算する
- 平均4.0以上だけを高評価対象とし、評価値を5.0で正規化する
- 件数は `log1p(review_count) / log1p(1000)` とし、1,000件以上を上限1.0にする
- 両方の観測値がある場合だけcomponentをavailableとし、片方でも欠ける場合はmissingとして既存のweight再正規化へ委ねる
- base weightをtitle 0.35、attributes 0.30、price 0.20、image 0.10、review quality 0.05とし、合計1.0かつreview qualityを唯一の最小値にする
- component追加と重み変更を同一 `ranking-v2` と扱わず、profile、ranked product、ranked batch、domain separatorをv3へ更新する
- pipelineの既定profile、fixture、正本文書を新契約へ同期する

### 対象外

- 個別レビュー本文、星別件数、verified purchase、review sentimentの取得・推定
- レビューをhard filterまたはnegative penaltyとして使うこと
- 1,000件上限や重み0.05が実検索品質上の最適値であるとの主張
- 画像rankingの有効化、CLIP score・画像manifest・model assetの変更
- legacy `run_product_search()`、Streamlit、CLI、API、外部委託中フロントエンドへの接続
- 実Amazon、Bonsai、Cloudflare、Outscraper、credential、課金、browser、AIレビューハーネス
- commit、push、merge

### 現在の状態

`ranking-v2` はtitle 0.40、attributes 0.30、price 0.20、disabled image 0.10の4componentであり、正規化済み候補に保持しているratingとreview countを順位へ使用していない。内部ranked batchは現行検索と履歴保存形式へ未接続であり、表示用履歴はraw scoreとweightを保存しない。

### 受入条件

1. 固定profileはv3として識別され、5つのbase weightが合計1.0、review quality 0.05が唯一の最小値になる。
2. rating 4.0未満またはreview count 0件はreview quality score 0.0となり、4.0以上ではratingと件数の双方が増えるとscoreが低下しない。
3. review count 1,000件以上の件数効果は1.0で飽和し、scoreは0〜1・小数4桁に固定される。
4. ratingまたはreview countの片方が欠ける場合はcomponentをmissingとし、利用可能componentだけでeffective weightを1.0へ再正規化する。
5. 他componentが同点の候補ではレビュー補助scoreが順位へ反映され、同scoreではresponse indexによるstable sortを維持する。
6. v2のprofile IDまたはdigestをv3 batchとして受け入れず、profileとranked batchのdigestが新componentへ結合される。
7. focused、全v2、offline全体、lock、Ruff、Python 3.10 AST、現行Markdown、`git diff --check` を確認する。

### 実行順序と進捗

- [x] 2026-09-04: 現行ranking、正規化済みrating・review count、pipeline・履歴の結合点を確認した。
- [x] 2026-09-04: profile、式、欠損、飽和、順位、digestを固定するRED testを追加し、未実装symbolによる収集失敗を記録した。
- [x] 2026-09-04: ranking-v3とpipeline既定値を実装し、focused testをGREENにした。
- [x] 2026-09-04: 要件、backend、schema、負債、worklog、changelog、次の再開位置を同期した。
- [x] 2026-09-04: 回帰・静的・文書gateを実行し、結果とhashを記録した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_ranking.py` | 新しいv3 profileまたはreview componentが未実装のため失敗 | 収集時1 error。`RANKING_PROFILE_V3` が未実装。test SHA-256 `eb86c9bfe63c920b9d46ab5e97bad96e954bd019effd6ad8608b26008f9b2b38` |
| GREEN | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_ranking.py` | profile、式、欠損、飽和、順位、digestの全件成功 | 26 passed |
| 回帰 | 全v2、offline全体 | 既存のoffline境界を維持 | 全v2 724 passed / 5 skipped、offline全体1456 passed / 5 skipped / 1 deselected |
| 静的・文書 | lock、Ruff、Python 3.10 AST、現行Markdown、`git diff --check` | error 0件 | lock 79、Ruff 174、AST 174、Markdown 16、local link 913、anchor 542、heading 1196、fence 195組、diff成功 |
| live・UI | provider API、browser、委託フロントエンド | 本Planでは実行しない | 対象外 |

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-04 | 高評価レビュー件数そのものではなく、平均評価と総レビュー件数による代理指標を使う | 現行provider正規化で観測できるのはこの2値だけで、星別件数や本文を推測できないため | provider契約へ検証済みの星別件数が追加された場合に別profileで見直す |
| 2026-09-04 | base weightは0.05とし、titleから0.05を移す | reviewを唯一の最小weightにし、既存のattributes、price、将来imageのweightを維持するため | 固定評価datasetで悪化が確認された場合に新profileで比較する |
| 2026-09-04 | 平均4.0を閾値、1,000件を件数効果の飽和点とする | 低評価を件数だけで押し上げず、極端な件数が補助component内を独占しない固定式にするため | 代表queryの期待順位と実候補で別閾値の改善を再現できた場合に見直す |

### ロールバック

本Planのranking-v3、focused test、pipeline既定profile、実装状態を更新した標準文書だけを取り除き、ranking-v2の定数とdomain separatorへ戻す。正規化商品、画像model・fixture、legacy検索、履歴repository schema、外部サービスは変更しない。

### 結果

完了。strict・frozenなranking profile、ranked product、ranked batch、domain separatorをv3へ上げ、5componentの内訳へreview qualityを追加した。平均4.0以上のratingと対数飽和するreview countの積を小数4桁で採点し、ratingまたはreview countの欠損、0件、4.0未満、1,000件以上、順位差、v2契約拒否をfocused testで固定した。pipelineの既定profileと承認fixtureもv3へ同期した。

RED test SHA-256は `eb86c9bfe63c920b9d46ab5e97bad96e954bd019effd6ad8608b26008f9b2b38`、最終ranking module SHA-256は `c71bee9ea55e1357986a6e78aea81d04b0db3dc6d949ababbcbed00955c815cf`、pipeline module SHA-256は `6ec4cdc421b92fa63b64af8c15077d31e08a071980ac7ab6906648a1203412f0`、最終ranking test SHA-256は `fc4d745e2970a6503619960cdf21eb954ffd9dfcb580110f7d72ed96357403d0` である。focused 26件、主要結合107件、全v2 724件、offline全体1456件、lock、Ruff、Python 3.10 AST、現行Markdown、AGENTS目次、差分検査に成功した。

これは内部計算契約とfixture順位の確認であり、0.05、平均4.0閾値、1,000件飽和が実商品検索に最適であるとは確認していない。実Amazon、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、実商品候補、実ランキング品質、browser、委託フロントエンド、AIレビューハーネスは実行・確認・接続していない。画像componentは引き続き無効である。


## EXEC-028: near画像の目視属性characterization

### メタデータ

- タスクID: `TASK-005`
- 状態: 完了
- 作成日: 2026-09-03
- 最終更新日: 2026-09-03
- 前提Plan: [EXEC-027](#exec-027-far画像の属性別hard-negative-characterization)
- 関連要件: `FR-408`、`NFR-208`（[REQUIREMENTS.md](REQUIREMENTS.md)）
- 関連負債: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)、[TD-011](ISSUES.md#td-011-画像取得推論の実環境検証)
- 関連設計: [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[SECURITY.md](SECURITY.md)

### 目的

near 13枚をローカル画像から確認できる属性へ分類し、利用者が指定した「黒い無線ゲーミングマウス」とのうち画像で確認可能な一致内容を再現可能にする。接続方式を含め画像だけでは確定できない属性は未知として残し、CLIP scoreを属性確認の代用にしない。

### 対象範囲

- `tests/img/case1/near/n1.png` から `n13.png` までを個別に目視する
- 色、ゲーミング用途、対象種別を目視結果として固定し、接続方式は `None` にする
- 画像内の本体、ケーブルの有無、受信機・充電dock、ロゴ、ボタン、発光、形状を視覚的特徴として扱うが、ケーブル非接続や付属品の写り込みを接続方式の証拠にしない
- 目視でゲーミング用途を確定できない画像は `None` とし、商品名や外部仕様を推測で補完しない
- 固定4参照を除くn5〜n13について、用途が明確な集合と未知の集合の記録済みscore傾向をcharacterizationする
- 既存SHA-256、参照、score、AUCが変わらないことをlocal-only testで再確認する

### 対象外

- 商品ページ、画像検索、外部catalogによる型番・接続方式・用途の補完
- 見えない底面switch、付属品、製品仕様、販売者説明の推測
- 利用者指定のnear/far分類、既存score、参照、AUC基準、model、ranking profileの変更
- 複数query、検索文から生成した実4方向参照、実Amazon検索順位の品質判断
- 画像・modelのGit追跡、commit、push、再配布
- 実host通信、provider、credential、課金、API、UI、外部委託中フロントエンド、AIレビューハーネス

### 現在の状態

13枚をlocal viewerで個別に確認した。全て黒色系のマウス本体で、付属受信機・充電dock、ケーブル非接続の本体表示を含む。ただし、これらは無線という商品仕様を確定する証拠にはならないため、接続方式は全て未知へ訂正した。n1〜n4とn7〜n13はゲーミングlogo、発光、多ボタン、軽量穴あき形状、製品上の `SUPERLIGHT` 表示等を確認できた。n5とn6は黒いマウスであることは確認できるが、静止画像だけではゲーミング用途を確定できない。

### 受入条件

1. near目視属性manifestがn1〜n13を重複・欠落なく覆い、全て黒、接続方式未知、マウスとして記録される。
2. n1〜n4・n7〜n13の11枚はゲーミング、n5・n6の2枚は用途未知とし、scoreから未知を補完しない。
3. 固定参照n1〜n4と候補n5〜n13の区別を維持し、記録済みnear scoreとのpath対応を再現する。
4. 実ONNX再計算で既存27 scoreとpairwise AUC 0.790123457を維持する。
5. `CLIP_IMAGE_RANKING_ENABLED` は `False` のまま維持する。
6. focused、画像関連、全v2、offline全体、lock、Ruff、Python 3.10 AST、現行Markdown、`git diff --check` を確認する。

### 実行順序と進捗

- [x] 2026-09-03: n1〜n13をlocal viewerで個別に確認し、判断根拠と目視で確定できない箇所を分離した。
- [x] 2026-09-03: near目視属性manifest、path整合test、記録score characterizationを追加した。
- [x] 2026-09-03: 固定ONNX CPU runtimeでscoreとAUCが変わらないことを確認した。
- [x] 2026-09-03: 回帰・静的・文書gateを実行し、TASK-005と次の再開位置を同期した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| 目視 | n1〜n13をlocal viewerで原寸表示 | 色、対象種別、用途と、画像で確定できない接続方式を分ける | 全13枚を確認。接続方式を全て未知、n5・n6の用途を未知とした |
| path・属性固定 | quality testの通常offline部分 | near 13 path、属性件数、未知集合がexactに一致 | 4 passed / 3 deselected |
| score再現 | quality testを `--run-clip-runtime` で実行 | 既存27 scoreとAUCを維持 | 6 passed / 1 xfailed。AUC 0.790123457を維持 |
| CLIP focused | 4つの画像類似度test fileを `--run-clip-runtime` で実行 | 既存境界とnear・far属性baselineを維持 | 84 passed / 1 xfailed |
| 回帰 | 画像関連、全v2、offline全体 | 通常gateはlocal assetを読まず全件成功 | 画像関連293 passed / 5 skipped、全v2 715 passed / 5 skipped、offline 1447 passed / 5 skipped / 1 deselected |
| 静的・文書 | lock、Ruff、Python 3.10 AST、現行Markdown、`git diff --check` | error 0件 | lock 79、Ruff 174、AST 174、Markdown 16、local link 907、anchor 537、heading 1183、fence 195組、diff成功 |
| live・UI | 商品ページ、Amazon画像host、provider API、browser、委託フロントエンド | 本Planでは実行しない | 対象外 |

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-03 | near属性を利用者指定の正解ではなく目視観察として別manifestへ保存する | farは利用者提示、nearはAIの画像確認であり、根拠の強さを混同しないため | 利用者または検証済み商品仕様から訂正された場合はsourceとrevisionを分けて更新する |
| 2026-09-03 | n5・n6のゲーミング用途を未知にする | 黒いマウス本体は見えるが、用途は外観だけで確定できないため | 商品仕様の根拠を追加するか、利用者が正解を提示した場合にだけ真偽へ変更する |
| 2026-09-04 | 2026-09-03の「接続方式は無線」という暫定目視判断を撤回し、near 13枚を全て未知にする | ケーブル非接続、受信機、充電dockの写り込みだけでは接続方式を確定できず、[EXEC-030](#exec-030-画像ランキングの視覚的特徴限定) で商品名・構造化属性を正本にしたため | 利用者指定または検証済みの商品名・構造化属性が得られた場合だけ、画像manifestとは別の根拠で接続方式を記録する |

### セキュリティ・データ境界

画像はlocal viewerとlocal testでだけ読み、画像byte、商品URL、商品IDを文書や出力へ複製しない。外部商品ページ・画像検索を使わず、credential、課金、利用者データを扱わない。画像とmodelは未追跡のままとする。

### ロールバック

near目視属性manifest、そのtest、本Planに伴う標準文書差分だけを取り除けばEXEC-027完了時点へ戻る。`tests/img/` とrepository-local modelは削除・移動・改名しない。

### 結果

完了後の2026-09-04に責務境界を訂正した。n1〜n13を原寸で個別に確認した結果として、全13枚を黒いマウス、n1〜n4とn7〜n13の11枚をゲーミング用途、n5・n6を用途未知として目視属性manifestへ固定した。ケーブル非接続、受信機、充電dockの写り込みは接続方式の証拠にせず、全13枚の接続方式を `None` とした。

候補n5〜n13の記録scoreでは、用途未知のn5・n6が平均0.941389590、用途を目視確認できたn7〜n13が平均0.932454373だった。未知群のscoreが高くても用途の根拠にはならないため、CLIP scoreからゲーミング属性を補完しない。固定ONNX再計算では27 score、near/far分布、pairwise AUC 0.790123457が従来値と一致した。

EXEC-028完了時のquality test SHA-256は `2c7846a41376b42bcbb4f93940bd1ba28cad4673460868aec0a8228715cb741d` である。当時はCLIP focused 84件、画像関連293件、全v2 715件、offline全体1447件が成功し、既知のAUC未達だけをstrict xfailへ維持した。lock 79 packages、Ruff・Python 3.10 AST 174 files、現行Markdown 16件のlocal link 907件・anchor 537件・heading 1183件・fence 195組、`git diff --check` も成功した。接続方式の訂正後のtestと検証結果は [EXEC-030](#exec-030-画像ランキングの視覚的特徴限定) を正とする。画像rankingは無効のままである。複数query、実4方向参照、商品順位の本受入評価はTASK-005へ残す。

## EXEC-027: far画像の属性別hard negative characterization

### メタデータ

- タスクID: `TASK-005`
- 状態: 完了
- 作成日: 2026-09-03
- 最終更新日: 2026-09-03
- 前提Plan: [EXEC-026](#exec-026-単一条件の複数画像clip-characterization)
- 関連要件: `FR-408`、`NFR-208`（[REQUIREMENTS.md](REQUIREMENTS.md)）
- 関連負債: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)、[TD-011](ISSUES.md#td-011-画像取得推論の実環境検証)
- 関連設計: [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[SECURITY.md](SECURITY.md)

### 目的

「黒い無線ゲーミングマウス」に対するfar 18枚を、利用者が提示した色、接続方式、ゲーミング用途、対象種別へ結び付ける。既に記録したCLIP scoreを属性差ごとに分解し、無線、有線、色、商品種別のどこで画像embeddingが近くなるかを再現可能にする。

本Planは既存の単一条件characterizationを説明可能にする追加作業である。near側の属性を推測せず、複数query・実商品順位の本受入評価や画像rankingの有効化には進まない。

### 対象範囲

- 利用者が整理した `tests/img/case1/far/f1.png` から `f18.png` までを既存SHA-256へ再対応付けする
- far 18枚へ、色、接続方式、ゲーミング用途、マウス・マウスソール・マウスバンジーの対象種別を固定する
- 黒・無線・ゲーミング・マウスとの差が1属性だけの集合と、マウスではない集合を機械的に抽出する
- [EXEC-026](#exec-026-単一条件の複数画像clip-characterization) で記録済みのscoreを集合別に集計し、観測傾向を固定する
- 画像file名変更後も、同一byte、同一参照、同一候補、同一scoreになることをlocal-only testで再確認する

### 対象外

- near 13枚の属性推測。利用者から明示された場合だけ別の正解dataとして追加する
- farのnear/far分類変更、scoreを理由にしたlabel変更、画像の除外
- model、前処理、参照4枚、score式、事前AUC基準、ranking profileの変更
- 複数query、検索文から生成した実4方向参照、実Amazon検索順位の品質判断
- model・画像のGit追跡、commit、push、再配布
- 実host通信、provider、credential、課金、API、UI、外部委託中フロントエンド、AIレビューハーネス

### 現在の状態

far 18枚とnear 13枚は、byteを変えずにそれぞれ `f1.png`〜`f18.png`、`n1.png`〜`n13.png` へ整理されている。利用者からfar 18枚の属性を受領した。f11は提示内容に「ゲーミング」がないため、黒・無線・非ゲーミングのマウスとして記録する。マウスではない画像の色・接続方式・ゲーミング用途は該当なしとし、見た目から補完しない。

### 受入条件

1. `f1.png`〜`f18.png` と `n1.png`〜`n13.png` が既存の31 SHA-256へexactに一致し、参照は従来と同じbyteのn1〜n4を使う。
2. far属性manifestが全18 pathを重複・欠落なく覆い、マウス12枚、マウスソール5枚、マウスバンジー1枚になる。
3. 対象条件との差が接続方式だけ、ゲーミング用途だけ、色だけの集合と、マウスではない集合が利用者指定属性から決定的に得られる。
4. 記録済みscoreとの対応と属性集合別の平均を再現し、画像だけでは接続方式を分離できない現象を数値で記録する。
5. `CLIP_IMAGE_RANKING_ENABLED` は `False` のまま維持する。
6. focused、画像関連、全v2、offline全体、lock、Ruff、Python 3.10 AST、現行Markdown、`git diff --check` を確認する。実provider、credential、課金、browserは使わない。

### 実行順序と進捗

- [x] 2026-09-03: 整理後の31 pathとSHA-256を再照合し、byteが従来fixtureと一致することを確認した。
- [x] 2026-09-03: far属性manifest、path整合test、属性別score characterizationを追加した。
- [x] 2026-09-03: 固定ONNX CPU runtimeでscore、中央値、AUCが改名前と一致することを確認した。
- [x] 2026-09-03: 回帰・静的・文書gateを実行し、TASK-005と次の再開位置を同期した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| path・属性固定 | quality testの通常offline部分 | 31 path、far 18属性、件数、属性集合がexactに一致 | 2 passed / 3 deselected |
| score再現 | quality testを `--run-clip-runtime` で実行 | 既存27 scoreとAUCを維持 | 4 passed / 1 xfailed。AUC 0.790123457を維持 |
| CLIP focused | 4つの画像類似度test fileを `--run-clip-runtime` で実行 | 既存境界、改名後path、属性baselineを維持 | 82 passed / 1 xfailed |
| 回帰 | 画像関連、全v2、offline全体 | 通常gateはlocal assetを読まず全件成功 | 画像関連291 passed / 5 skipped、全v2 713 passed / 5 skipped、offline 1445 passed / 5 skipped / 1 deselected |
| 静的・文書 | lock、Ruff、Python 3.10 AST、現行Markdown、`git diff --check` | error 0件 | lock 79、Ruff 174、AST 174、Markdown 16、local link 890、anchor 522、heading 1169、fence 195組、diff成功 |
| live・UI | Amazon画像host、provider API、browser、委託フロントエンド | 本Planでは実行しない | 対象外 |

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-03 | f番号を利用者指定属性の安定IDとし、旧file名からbyte対応を変えない | 属性説明と画像を人間が照合しやすくし、過去scoreとの比較可能性を維持するため | 画像byteまたはlabelが訂正された場合は別revisionとして記録する |
| 2026-09-03 | f11を非ゲーミングとして扱う | 他のゲーミング画像と異なり、利用者の提示に「ゲーミング」が含まれないため | 利用者がゲーミングまたは不明へ訂正した場合に更新する |
| 2026-09-03 | 非マウス画像の色・接続方式・用途を該当なしにする | マウス属性を付与すると、商品種別差と属性差が混ざるため | accessory自体の属性評価を別途定義した場合に見直す |

### セキュリティ・データ境界

画像byteはlocal test入力としてだけ読み、文書、例外、標準出力へ複製しない。属性は利用者が提示した一般的な商品分類だけを保持し、source URL、商品ID、利用者情報、credentialを記録しない。画像とmodelは未追跡のままとする。

### ロールバック

quality testのpath・属性追加、process smokeのpath更新、本Planに伴う標準文書差分だけを取り除けばEXEC-026完了時点へ戻る。利用者が整理した `tests/img/` とrepository-local modelは削除・移動・改名しない。

### 結果

完了。画像byteを変えず、farを `f1.png`〜`f18.png`、nearを `n1.png`〜`n13.png` の安定IDへ対応付けた。従来と同じn1〜n4を固定参照に使う実ONNX再計算で、27 score、near/far分布、pairwise AUC 0.790123457が改名前と一致した。

利用者指定属性では、対象条件との差が接続方式だけの黒・有線・ゲーミング・マウス4枚が平均0.945551862、ゲーミング用途だけが異なる黒・無線マウス1枚が0.922820165、色だけが異なる無線ゲーミングマウス6枚が平均0.875869567、非マウス6枚が平均0.830395143だった。接続方式だけが異なる4枚はすべてfar全体の中央値0.876893229を上回った。これは画像embeddingが形状や色を強く反映し、有線・無線を十分に分離しないという単一条件の観測であり、一般品質を示さない。

quality test SHA-256は `2eec3a74453ae6edb5e0cace4cd00aedd07aa84f5bb0b3e7a53a6ad34f95ae5d`、改名後pathへ更新したprocess testは `2bb0c8e195b92b288619c889952247fb81753882afe41010665ffbf105c914b8` である。CLIP focused 82件、画像関連291件、全v2 713件、offline全体1445件が成功し、既知のAUC未達だけをstrict xfailへ維持した。lock 79 packages、Ruff・Python 3.10 AST 174 files、現行Markdown 16件のlocal link 890件・anchor 522件・heading 1169件・fence 195組、`git diff --check` も成功した。画像rankingは無効のままである。near側の目視属性は後続の [EXEC-028](#exec-028-near画像の目視属性characterization) で固定した。商品仕様による独立確認、複数query、実4方向参照、商品順位の本受入評価はTASK-005へ残す。

## EXEC-026: 単一条件の複数画像CLIP characterization

### メタデータ

- タスクID: `TASK-005`
- 状態: 完了
- 作成日: 2026-09-03
- 最終更新日: 2026-09-03
- 前提Plan: [EXEC-025](#exec-025-固定onnx-clip-cpu-runtimeと品質smoke)
- 関連要件: `FR-408`、`NFR-208`（[REQUIREMENTS.md](REQUIREMENTS.md)）
- 関連負債: [TD-008](ISSUES.md#td-008-為替とランキング品質の評価)、[TD-011](ISSUES.md#td-011-画像取得推論の実環境検証)
- 関連設計: [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[SECURITY.md](SECURITY.md)

### 目的

利用者が `tests/img/case1/near/` と `tests/img/case1/far/` に分類した「黒い無線ゲーミングマウス」の31枚を、固定byteのlocal quality datasetとして再現可能に評価する。正例自身を候補と参照へ同時に使った旧1組smokeを置き換え、固定した4枚だけを参照、残るnear 9枚とfar 18枚を候補にして、同じproduction score境界の分離傾向を測る。

本Planは単一検索条件のcharacterizationである。暫定基準を満たしても、検索文から生成した実際の4方向参照、複数query・カテゴリ、実Amazon結果の順位品質を確認したことにはせず、画像rankingを有効化しない。

### 対象範囲

- `tests/img/case1/near/` 13枚、`tests/img/case1/far/` 18枚の相対path・label・SHA-256をtest内の固定manifestへ記録する
- symlink・hardlink、PNG以外、複数frame、hash不一致、未登録・欠損file、同一source byte、pHash距離5以内の近似重複を拒否する
- 測定前に選んだ同一byteのnear 4枚を固定参照とし、参照自身を候補から除外する。現行の安定IDはn1〜n4である
- 残るnear 9枚とfar 18枚を各1枚の候補として、productionの `score_clip_image_similarity()` で採点する
- near/farの件数、平均、中央値、最小・最大、全162組のpairwise AUCを出す。tieは0.5として数える
- 暫定characterization基準を `AUC >= 0.80` かつ `near中央値 > far中央値` とし、測定後に同じPlan内で参照選択、label、基準を変更しない
- 既存の固定ONNX model、CPU-only `spawn` process encoder、224px前処理、runtime digestをそのまま使う

### 対象外

- 利用者が指定したnear/far labelの視覚判断による変更、都合のよい画像の除外、測定後の閾値変更
- 検索文を入力するtext encoder、実Cloudflareの4方向生成画像、実Amazon商品画像hostへの通信
- 複数query・カテゴリ、商品単位の複数画像、属性別正解、NDCG・precision/recallの本評価
- CLIP model、前処理、score式、ranking weight・profileの変更または画像componentの有効化
- model・画像のGit追跡、Git LFS、commit、push、再配布
- 現行pipeline、API、UI、外部委託中フロントエンド、AIレビューハーネス

### 受入条件

1. 固定manifestが、利用者の分類したnear 13枚・far 18枚とexactに一致し、全fileの通常file・link数・SHA-256・PNG・単一frame・固有byteを再検証する。
2. pHash距離5以内の近似重複をdataset内に含めず、参照4枚をnear/far候補から除外する。
3. 固定4参照に対するnear 9枚・far 18枚のscoreを同じruntimeで計算し、件数と分布、pairwise AUCを決定的に記録する。
4. 暫定基準は測定前に固定した `AUC >= 0.80` と `near中央値 > far中央値` の両方とする。不合格でもmodel・label・参照・基準を同じPlanで調整せず、観測結果として残す。
5. 結果にかかわらず `CLIP_IMAGE_RANKING_ENABLED` は `False` を維持し、単一queryの結果を一般的な意味理解またはproduction品質と表現しない。
6. focused、画像関連、全v2、offline全体、lock、Ruff、Python 3.10 AST、現行Markdown、`git diff --check` を確認する。実provider、credential、課金、browserは使わない。

### 実行順序と進捗

- [x] 2026-09-03: near 13枚・far 18枚、全31枚が単一frame RGBA PNG、source SHA-256重複なし、pHash距離10以内の組なしであることを確認した。
- [x] 2026-09-03: 固定4参照、near候補9枚、far候補18枚、AUCと中央値の暫定基準を実測前に決定した。
- [x] 2026-09-03: 固定dataset manifestと自己参照なしのruntime testを追加し、aggregateと個別scoreを記録した。暫定AUC基準のREDは期待どおり不合格だった。
- [x] 2026-09-03: 回帰・静的・文書gateを実行し、TASK-005、標準文書、次の再開位置を同期した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| dataset固定 | 31件のmanifest、file・link・PNG・frame・digest・pHash検査 | near 13、far 18、参照と候補の分離、重複0 | 1 passed。pHash距離10以内も0組 |
| 初回品質gate | 固定4参照、near 9、far 18をCPU processで採点 | AUC 0.80以上かつnear中央値がfar中央値を上回る | 1 failed。中央値条件は成功、AUC 0.790123457で未達 |
| 固定characterization | 記録scoreとの絶対誤差1e-8、既知の未達をstrict xfail | score再現成功、基準未達は成功と数えない | quality file 2 passed / 1 xfailed |
| CLIP focused | 4つの画像類似度test fileを `--run-clip-runtime` で実行 | 既存境界と新baselineを維持 | 80 passed / 1 xfailed |
| 回帰 | 画像関連、全v2、offline全体 | 通常gateはlocal assetを読まず全件成功 | 画像関連289 passed / 5 skipped、全v2 711 passed / 5 skipped、offline 1443 passed / 5 skipped / 1 deselected |
| 明示runtime | `pytest -m clip_runtime --run-clip-runtime` | 合成・旧1組・31枚を実行し、既知の基準未達だけxfail | 4 passed / 1 xfailed / 1444 deselected |
| 静的・文書 | lock、Ruff、Python 3.10 AST、現行Markdown、`git diff --check` | error 0件 | lock 79、Ruff 174、AST 174、Markdown 16、local link 874、anchor 508、heading 1155、fence 195組、diff成功 |
| live・UI | Amazon画像host、provider API、browser、委託フロントエンド | 本Planでは実行しない | 対象外 |

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-03 | `near/` と `far/` を利用者の正解labelとしてそのまま使う | product属性は画像だけでは確定できず、測定者による事後除外を防ぐため | label誤りを利用者が訂正した場合はdataset revisionを変えて別結果として再測定する |
| 2026-09-03 | score確認前に選んだnear 4枚を固定参照にする。現行IDはn1〜n4 | 機械的・再現可能に選び、自己参照と選択の恣意性を避けるため | 実Cloudflare 4方向画像を受領した場合は別dataset・別Planで置換する |
| 2026-09-03 | AUC 0.80と中央値分離を暫定基準にする | 単一閾値ではなく全near/far組の順序を測り、少数の境界例にも耐える最小baselineにするため | 複数query評価では事前にNDCG等を含む本受入基準を別途決める |

### セキュリティ・データ境界

画像byteはtest入力としてlocalでだけ読み、標準出力、文書、例外へ複製しない。source URL、商品識別子、利用者データ、credentialは記録しない。画像の権利・再配布条件は確認していないため、画像とmodelは未追跡のlocal assetのままとし、本Planはcommit・pushを許可しない。

### ロールバック

新しいquality testと本Planに伴う標準文書差分だけを取り除けば、EXEC-025完了時点へ戻る。利用者が配置した `tests/img/` とrepository-local modelは削除・移動・改名しない。

### 結果

固定4参照、near候補9枚、far候補18枚を同じCPU process encoderとproduction scoreへ通した。near平均0.934439977、far平均0.881724434、near中央値0.940632749、far中央値0.876893229で、中央値分離条件は成功した。near範囲0.909637856〜0.950941212とfar範囲0.808155344〜0.956266974は重なり、全162組のpairwise AUCは0.790123457だったため、測定前に固定した0.80以上の基準へ未達だった。

同じ測定を再実行して各scoreが記録値の絶対誤差1e-8以内で一致することをtestへ固定した。dataset・characterizationは成功test、事前品質基準の未達はstrict xfailとして分離した。farの上位にはnear参照と外形・色が近い黒い有線ゲーミングマウスが含まれ、画像embeddingだけでは「無線」という非視覚的属性を十分に分離できないことが観察された。model、label、参照、基準は変更せず、画像rankingは無効のままとした。far側属性は後続の [EXEC-027](#exec-027-far画像の属性別hard-negative-characterization)、near側目視属性は [EXEC-028](#exec-028-near画像の目視属性characterization) で固定した。商品仕様による独立確認、複数query、検索文から得た実4方向参照、商品順位の本受入基準はTASK-005へ残る。

## EXEC-025: 固定ONNX CLIP CPU runtimeと品質smoke

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-03
- 最終更新日: 2026-09-03
- 前提Plan: [EXEC-010](#exec-010-安全な画像取得phash固定clip境界)、[EXEC-024](#exec-024-windowswsl向け画像dns-process-isolation)
- 関連要件: `FR-408`、`NFR-207`、`NFR-208`、`SEC-012`（[REQUIREMENTS.md](REQUIREMENTS.md)）
- 関連負債: [TD-011](ISSUES.md#td-011-画像取得推論の実環境検証)
- 関連設計: [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[SECURITY.md](SECURITY.md)

### 目的

固定したCLIP modelを、model名による暗黙downloadやPython pickle weightの復元なしに、Windows 11 / WSLでCPU実行できるようにする。model assetは利用者指定どおりリポジトリ内の専用directoryへ配置し、通常runtimeはnetworkを使わない。画像前処理、ONNX session、embedding出力、子processのdeadline・回収を固定し、受領した「黒い無線ゲーミングマウス」の正例・負例を再現可能なlocal fileとして評価できる入口を作る。

利用者が将来観察できる結果は、画像rankingをまだ有効化しない状態で、固定runtimeが同じ画像から決定的な512次元embeddingを返し、代表例の近い／近くない順序をlocal quality smokeとして比較できることである。1組だけのsmokeを本番品質保証とは扱わず、採点有効化は別の十分なdatasetと受入基準を必要とする。

### 対象範囲

- `models/clip-vit-base-patch32-12b36594/` に置く、固定revisionの `config.json`、`preprocessor_config.json`、`model.onnx`
- `openai/clip-vit-base-patch32` revision `12b36594d53414ecfba93c7200dbb7c7db3c900a` のONNX asset名、byte数、SHA-256を固定するmanifestへの移行
- PyTorch・Transformersを使わず、CPU execution providerだけでONNX image embeddingを得るlocal encoder
- 224pxへの固定resize・center crop、RGB、rescale、固定mean・std、NCHW float32へ変換する前処理
- Windows/WSL互換の明示的な `spawn` 子process、固定deadline、byte IPC、terminate・kill、全endpoint回収
- model load・推論失敗、timeout、IPC不正、shape・dtype・有限値不正をpath・画像・生例外を含まない固定errorへ変換する境界
- fake session・process・pipe・clockによるoffline TDDと、明示opt-inのrepository-local実model smoke
- 受領済み条件「黒い無線ゲーミングマウス」、近い画像1枚、近くない画像1枚、exact許可host `m.media-amazon.com` の記録
- `NEXT-STEPS.md`、要件、backend、security、課題、worklog、changelogの同期

### 対象外

- `pytorch_model.bin`、pickle・PyTorch・Transformersによるmodel load
- model assetのGit commit・Git LFS・push・release artifact配布。明示指示がない限りlocal working treeへの配置だけとする
- 実Amazon画像URL、`m.media-amazon.com` へのDNS・TLS・HTTP、Outscraper、Cloudflare、Bonsai、OpenAIへの接続
- 受領画像のチャット表示からの推測保存、代替画像の生成、画像byteを含むlog・artifact
- GPU・NPU execution provider、自動provider fallback、量子化、batch最適化、常駐worker、複数worker運用
- 画像ranking weightの有効化、現行pipeline・API・UI・外部委託中フロントエンドへの接続
- 1組だけの例による一般的な画像検索品質、Amazon全カテゴリ、障害耐性、性能・SLOの保証
- AIレビューハーネス、`docs/HARNESS-RUNBOOK.md` の変更

### 現在の状態

実行環境はWindows 11 / WSL、Intel Core Ultra 9 288Vである。`/home/products/models/Bonsai-8B.gguf` は文章処理用として分離したまま、CLIPはrepository内の `models/clip-vit-base-patch32-12b36594/` へ配置した。directoryには読取専用の `config.json` 456 bytes、`model.onnx` 605,804,513 bytes、`preprocessor_config.json` 468 bytesだけがあり、SHA-256はmanifestと一致する。model directoryと3 fileはGit未追跡である。

依存にはNumPyとONNX Runtime 1.23.2を追加してlockした。PyTorch、Transformers、pickle weightは導入していない。固定graphのactive providerは `CPUExecutionProvider` だけで、`input_ids`、`pixel_values`、`attention_mask` から `image_embeds` `[image_batch_size, 512]` の `float32` を得られる。`--offline --no-sync` かつ外部clientを持たないlocal-only経路で、合成画像1枚を実 `spawn` 子processへ通す明示opt-in testは3.39秒で成功した。pytestのPython network guardはspawn子processやnative codeをOSレベルで遮断しないため、これはrepository-local modelのload・CPU推論・IPC疎通だけを示し、OS-level offline、Windows native、画像rankingを示さない。

正例・負例は `tests/img/` の固定PNGとして受領した。正例自身のembeddingを4方向の代用参照とし、正例・負例を同じ子process経路で3回比較した。3回のembeddingはbit-identicalで、画像scoreは正例1.000000000、負例0.940624123、差0.059375877となり、事前の最小条件である期待順序を満たした。これは自己参照を含む1組の識別smokeであり、検索文との意味一致、実際の4方向参照、複数商品・カテゴリでのranking品質を示さない。

### 受入条件

1. model directoryはリポジトリ内の固定相対pathとし、3つの通常fileだけを含む。symlink、hardlink、欠損、余分file、byte数・SHA-256不一致をload前とload後に拒否する。
2. asset取得は固定revisionのHTTPS URL 3件、合計610 MB未満、credentialなし、API課金なしに限定する。runtime、通常pytest、import、constructorはnetworkを開始しない。
3. manifestとruntime profileをONNX assetへ結び直し、`pytorch_model.bin`、pickle、PyTorch、Transformersをproduction import・dependency・assetから除外する。画像rankingは固定で無効のままにする。
4. 前処理は検証済み `ProxyImage` だけを受け、224px、BICUBIC resize、center crop、RGB、`1/255` rescale、固定mean・std、NCHW float32を決定的に作る。入力件数を1〜4、生成byte数を固定上限へ制限する。
5. ONNX RuntimeはCPU execution providerだけを明示し、固定session optionとoutput名を使う。入力・出力名、dtype、shape、512次元、件数、有限値を再検証し、L2正規化前の0 vectorを拒否する。
6. process encoderは明示的な `spawn` を使い、親で検証・縮小したbounded image dataだけを子へ渡す。子からは固定headerと最大4組のfloat32 embedding bytesまたは固定失敗tagだけを受け、pickle objectを戻さない。
7. process開始、model load、推論、応答、正常終了を1つの固定deadlineへ含める。timeoutまたは異常終了ではterminate、なお生存時はkillし、作成済みprocess・pipeを全経路で閉じる。Pythonからpreemptできない `Process.start()` は絶対上限の例外として明記する。
8. constructor、model path、provider、thread数、deadline、IPC上限を利用者入力やrequest単位で変更させず、生path、画像byte、ONNX errorを例外、log、履歴へ含めない。自動retryと別provider fallbackを行わない。
9. fake runtimeのfocused test、画像関連回帰、全v2、offline全体、lock、Ruff、Python 3.10 AST、Markdown、差分検査に成功する。通常gateは606 MB modelをloadせず、明示opt-in smokeだけが実assetを使う。
10. local画像fileが用意された後、同一runtime・同一前処理で3回再現し、正例が負例より高いことを記録する。この1組だけではranking weightを有効化せず、追加datasetと閾値は別Planへ残す。

### 実行順序と進捗

- [x] 2026-09-03: 実行環境、空き容量、`/home/products/models`、現行dependency、固定CLIP契約、受領例と許可hostを確認した。
- [x] 2026-09-03: 利用者指示によりmodelの配置先をリポジトリ内へ決定し、pickle weightではなく固定revisionのONNX assetを選択した。
- [x] 2026-09-03: 固定URLから3 assetを一時directoryへ取得し、通常file、件数、byte数、SHA-256を検証してから専用model directoryへ移した。
- [x] 2026-09-03: ONNX manifest、固定前処理、CPU session、shape・dtype・output検証のREDを追加し、旧manifestとmodule不在という期待理由で失敗することを確認した。
- [x] 2026-09-03: local ONNX encoderを実装し、fake sessionでGREENにした。CPU実modelを明示opt-inでloadして入出力契約を確認した。
- [x] 2026-09-03: `spawn` process lifecycle、deadline、byte IPC、cleanup、固定errorのREDを追加し、process encoderを実装した。
- [x] 2026-09-03: 同じ2枚をlocal PNGとして受領し、3回のbit-identicalなembeddingと正例・負例の期待順序を確認した。
- [x] 2026-09-03: focused、画像関連、全v2、offline全体、lock、Ruff、文書・構文・差分を検証し、標準文書を同期した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| asset取得 | 固定3 URL、取得上限、`stat`、SHA-256、directory entry検査 | 3通常fileだけ、合計610 MB未満、公開model digest一致 | 3読取専用file、合計605,805,437 bytes。3 digest一致 |
| encoder RED/GREEN | 新規focused test | 前処理・session・shape・error境界をRED後に全件成功 | 旧manifest mismatchとmodule不在でRED、encoderを含むfocused 51件成功 |
| process RED/GREEN | 新規focused test | spawn・deadline・IPC・cleanup境界をRED後に全件成功 | module不在でRED、23件成功・実model 1件は既定skip |
| 実model smoke | 明示opt-inのlocal-only testまたは専用command | CPU provider、512次元、有限・正規化済みembedding、外部通信なし | 合成画像1枚、WSL CPU `spawn`、1件成功、3.39秒 |
| 代表画像 | 受領した同一byteの正例・負例を3回評価 | 決定的な順序、正例scoreが負例scoreを上回る | 3回bit-identical。正例1.000000000、負例0.940624123、差0.059375877 |
| 回帰 | 画像関連、全v2、offline全体 | 全件成功、通常gateでは実modelをloadしない | 画像関連289 passed / 2 skipped、全v2 711 passed / 2 skipped、offline全体1443 passed / 2 skipped / 1 deselected |
| 静的・文書 | lock、Ruff、Python 3.10 AST、現行Markdown、`git diff --check` | error 0件 | lock 79、Ruff 173、Markdown 16、local link 858、anchor 495、heading 1142、fence 195組、AST 173、diff成功 |
| live・UI | Amazon画像host、provider API、browser、委託フロントエンド | 本Planでは実行しない | 対象外 |

### セキュリティ・データ・互換性

- ONNX採用はPython pickle復元を避けるためであり、model parser自体の無欠陥、供給元の永続的信頼性、sandboxを証明しない。固定commit URL、byte数、SHA-256、process回収を重ねる。
- model directoryを実行時に書換えず、load前後のfile identityとdigestを確認する。取得client、model名解決、cache探索、環境proxyをruntimeへ持ち込まない。
- process isolationは停止・crashの影響を親processから回収する境界であり、別OS user、filesystem sandbox、network namespaceではない。ranking有効化前に運用分離を再評価する。
- 受領画像は個人情報・機密情報なしの品質fixtureとしてだけ扱う。固定hashで同じbyteを検証し、画像byteを文書、例外、logへ複製しない。Git追跡・配布は別途権利と配布方針を確認する。
- model binaryはリポジトリ内へ置くが、commit・pushは別権限である。本Planでは `.gitignore`、Git LFS、remoteを変更しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-03 | modelを `models/clip-vit-base-patch32-12b36594/` へ置く | 利用者がrepository-local配置を指定し、現行source・cacheと分離できるため | 配布方法を決めるまではlocal assetであり、Git追跡を意味しない |
| 2026-09-03 | pinned PyTorch weightをONNXへ置換する | 既存 `.bin` はpickle importを含み、同revisionにpickleを使わないONNX artifactがあるため | ONNX graphが必要なimage embeddingを再現できない場合は実装を停止し、別のsafe artifactを再審査する |
| 2026-09-03 | CPU providerから開始する | Windows 11 / WSLと提供CPUで共通に確認でき、GPU・NPU固有runtimeを前提にしないため | 代表datasetで性能不足を実測した場合だけ別providerを新Planで検討する |
| 2026-09-03 | 1組の正例・負例はquality smokeに限定する | 自己一致や少数例だけではカテゴリ横断のranking品質を保証できないため | ranking有効化には独立した複数query・複数商品のdatasetと閾値を要求する |

### 発見事項

- 固定revisionのONNX graphは画像outputだけを要求しても3つのgraph inputを要求する。runtimeは画像に影響しない固定最小 `input_ids=[[0]]` と `attention_mask=[[1]]` を渡し、`image_embeds` だけを取得する。
- 現行環境でONNX Runtimeが列挙するproviderにはAzureも含まれるが、作成したsessionのactive providerは明示したCPUだけである。active providerが1件のCPU以外ならfail closedにする。
- 受領した2画像はいずれもRGBAの単一frame PNGであり、固定hash確認後にRGBへ変換した。同じ2画像を1つの子process callへ入れる実行を3回繰り返してもembedding bytesは変わらなかった。
- 正例自身を参照にすれば自己scoreは必ず最大になるため、今回確認できるのは固定runtimeの再現性と異なる画像に対する順序だけである。画像ranking有効化には、自己参照を避けた複数query・4方向参照・複数商品と事前合格基準が必要である。

### ロールバック

repository-local model directory、新規ONNX encoder・process module、新規test、dependency変更と本Planに伴う標準文書差分だけを取り除けばEXEC-024完了時点へ戻る。既存Bonsai GGUF、現行pipeline、cache、履歴DB、credential、外部service、委託フロントエンドは変更しない。取得途中の一時fileはfinal assetと区別し、検証不合格なら専用一時directoryだけを削除する。

### 結果

完了。repository-localの固定ONNX 3 asset、NumPy・ONNX Runtime 1.23.2、224px前処理、CPU-only encoder、30秒 `spawn` process・byte IPC、合成画像の実model smokeを実装した。受領1組は正例自身を参照として3回比較し、bit-identicalなembedding、正例1.000000000、負例0.940624123、差0.059375877で期待順序を満たした。明示opt-inのCLIP focusedは78件、画像関連289件、全v2 711件、offline全体1443件が成功した。通常gateでは実model 2件をskipし、明示opt-inでは2件とも成功した。更新後process test SHA-256は `1b4ac8498caaf292cac01b51311d7beacad1aef1268a26472c4a92393c077d17` である。画像rankingは本Plan完了後も既定無効とし、十分なdataset評価はTASK-005へ残す。


## EXEC-024: Windows/WSL向け画像DNS process isolation

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-03
- 最終更新日: 2026-09-03
- 前提Plan: [EXEC-023](#exec-023-server-side画像proxy-service)
- 関連要件: `SEC-012`、`NFR-104`（[REQUIREMENTS.md](REQUIREMENTS.md#6-セキュリティ要件)）
- 関連設計: [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[SECURITY.md](SECURITY.md)

### 目的

商品画像hostのOS名前解決が停止しても、画像proxyを動かす親processを無期限に待たせない。Windows 11とWSLの両方で利用できるPythonの `spawn` 方式に固定し、名前解決を1回限りの子processへ隔離する。親processは5秒のapplication deadline内だけ結果を待ち、timeout、子process異常終了、IPC不正を固定errorへ変換して、作成済みのprocessとpipeを回収する。Pythonから `Process.start()` 自体はpreemptできないため、5秒をOS process起動の絶対上限とは扱わない。

利用者が将来観察できる結果は、許可済み画像URLの名前解決がOS側で停止しても、`Process.start()` 復帰後は画像取得が名前解決段階でapplication deadlineにより失敗へ向かうことである。本Planではfake process・pipe・clockと子workerの直接fixtureによる外部通信なしの契約検証に加え、WSL2で外部DNSへ進まない固定失敗経路の実 `spawn` とbyte IPCを1回確認した。Windows 11 native、WSL上の実DNS、実画像hostでの時間・終了挙動は確認していない。

### 対象範囲

- `src/search_v2/image_proxy_dns_process.py` に実装する `ProcessIsolatedImageDnsResolver`
- Windows 11 / WSLで共通利用できる明示的な `multiprocessing.get_context("spawn")`
- 1回の名前解決ごとに1本の片方向pipeと1個のdaemon子processを作り、子process内だけで既存 `BoundedImageDnsResolver` を呼ぶ境界
- 親processで固定する5秒のapplication deadline、4.5秒以下の結果待機、terminate・kill後のjoinへ各0.25秒以下を確保する回収境界
- 子processから受ける最大512 bytesのASCII成功messageを、1〜8件のcanonical numeric IPv4・IPv6だけへ再検証するbyte IPC境界
- timeout、異常終了、EOF、malformed message、process・pipe操作失敗を固定 `image DNS process failed` へ変換する非露出境界
- `ImageProxyService` の既定resolverだけをprocess分離版へ置き換え、constructor注入による既存offline test境界を維持する変更
- fake process・pipe・clockと子worker直接fixtureによるRED→GREEN、関連回帰、標準文書の同期

### 対象外

- Windows 11 nativeでの実process、WSL上の実DNS、実画像hostのE2E、性能・負荷・長時間安定性
- 実Amazon CDN等の運用allowlist値、DNS cache、TTL、DNSSEC、DoH・DoT、custom resolver
- DNS成功後のTCP/TLS/HTTP全体deadline、別IP failover、retry、redirect、batch・並列取得
- CLIP model asset・encoder・GPU・NPU実行、CLIP process isolation、画像ranking有効化、品質評価
- endpoint、認証・認可、rate limit、cache、metrics、現行pipeline、API、UIへの接続
- 外部委託中のフロントエンドの確認、レビュー、起動、画面確認、テスト、バックエンド接続
- credential、外部送信、課金、AIレビューハーネスの実行、`docs/HARNESS-RUNBOOK.md` の変更

### 現在の状態

`ImageProxyService` の既定resolverを `ProcessIsolatedImageDnsResolver` へ変更した。serviceとresolverのconstructorはprocess、DNS、socketを開始せず、実際の名前解決要求ごとに明示的な `spawn` context、片方向pipe、daemon子processを1組だけ作る。子process内だけで既存 `BoundedImageDnsResolver` を呼び、親processへ最大512 bytesのASCIIだけを返す。

利用者から実行環境がWindows 11 / WSL、Intel Core Ultra 9 288Vであると確認できた。本PlanはCPUだけで成立する `spawn` を選び、Intel GPU・NPUの利用可否やメモリ量をDNS境界の前提にしない。現行作業環境はLinux/WSL側であり、Windows nativeでの実process検証は後続の運用確認へ残す。

### 受入条件

1. resolver constructorと `ImageProxyService` constructorはprocess、DNS、socketを開始しない。名前解決1回につき `get_context("spawn")`、片方向pipe、daemon子processを各1回だけ使い、processを再利用またはcacheしない。
2. 子workerだけが既存 `BoundedImageDnsResolver` を1回呼ぶ。hostをshell・command line・環境変数・logへ投影せず、IPC引数だけで渡す。子workerは成功結果または固定失敗tagだけを送ってpipeを閉じる。
3. 親processはprocess準備前から5秒のdeadlineを計測し、pipe待機、正常終了待機、terminate後とkill後のjoinへ残り時間だけを渡す。`Process.start()` 自体はPythonからpreemptできない制約を明記し、start復帰後は期限超過を成功扱いしない。
4. 成功messageは最大512 bytesのexactな組込み `bytes` とし、ASCIIの成功tag、1〜8件のcanonical numeric IPv4・IPv6だけを受ける。不正、空、過剰、非ASCII、非canonical、余分fieldを拒否し、既存coreの全address global判定は維持する。pickleによる任意object復元は行わない。
5. timeout、子processの固定失敗、異常終了、EOF、malformed message、pipe・process・clock操作失敗は、host、IP、raw message、OS例外を含めず `image DNS process failed` だけを返す。retry、別resolver、別processによる自動再試行を行わない。
6. 成功・失敗の全経路で親側pipe endpointを閉じる。deadline内に子processが終了しなければterminate、なお生存する場合はkillを各最大1回行い、待機時間をdeadlineの残りへ限定する。
7. `ImageProxyService` の既定compositionはprocess分離resolverを1回だけ構築する。constructor注入されたresolver・transport、公開 `fetch_image(url)`、固定service error、既存policy・transport・coreの契約を変更しない。
8. fake process・pipe・clockによるfocused test、service回帰、proxy関連、全v2、offline全体、lock、Ruff、文書構造、Python 3.10構文、差分検査に成功する。実network、credential、browser、外部委託中フロントエンドを使わない。

### 実行順序と進捗

- [x] 2026-09-03: `agents-setup`、`AGENTS.md`、`DEVELOPMENT.md`、現在のPlan・実装・テスト境界を確認した。
- [x] 2026-09-03: 実行環境をWindows 11 / WSL、Intel Core Ultra 9 288Vとして記録し、DNSはGPU・NPU非依存の `spawn` 子process方式と決定した。
- [x] process lifecycle、deadline、IPC検証、固定error、service既定compositionのREDテストを追加し、期待理由で失敗することを確認した。
- [x] `ProcessIsolatedImageDnsResolver` を実装し、既定serviceへ接続した。
- [x] focused、proxy関連、全v2、offline全体を検証した。lock、Ruff、文書・構文・差分の最終gateも完了時に確認した。
- [x] 要件、backend、security、課題、履歴、残作業と再開位置を同期した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_image_proxy_dns_process.py tests/test_search_v2_image_proxy_service.py` | 新module不在または要求した振る舞い不足で失敗 | module不在は終了2、scaffoldは37 failed / 33 passed。byte IPC、cleanup時間確保、interrupt伝播、正常message後のcleanup予約の補足REDも順に8 failed / 61 passed、3 failed / 66 passed、1 failed / 38 passed、1 failed / 69 passedを確認 |
| focused GREEN | 同上 | 全件成功 | 70 passed |
| proxy関連 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_image_proxy.py tests/test_search_v2_image_proxy_dns.py tests/test_search_v2_image_proxy_dns_process.py tests/test_search_v2_image_proxy_http.py tests/test_search_v2_image_proxy_service.py` | 全件成功 | 213 passed |
| 全v2 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_*.py` | 全件成功 | 665 passed |
| 標準gate | lock、Ruff check/format、offline全体、`git diff --check` | 終了0 | offline全体は1397 passed / 1 deselected。その他は最終gateで終了0 |
| 文書・構文 | 現行Markdown link・anchor・fence、Python 3.10 AST、AGENTS目次 | 欠落・構文・構造error 0件 | 最終gateでerror 0件 |
| WSL2 process smoke | 外部DNSへ進まない不正hostを子workerへ渡し、実 `spawn`・片方向pipe・byte IPC・終了を確認 | 固定 `error` messageを受けて子processが終了 | `Linux 6.18.33.2-microsoft-standard-WSL2 x86_64` で1回成功 |
| live・UI | Windows native、実DNS・実host・実画像、credential、browser、委託フロントエンド | 本Planでは実行しない | 対象外 |

### セキュリティ・データ・互換性

- 子processは1 hostの名前解決だけを行い、HTTP、credential、cache、利用者入力の保存、logを持たない。親子IPCは最大512 bytesのASCIIで、成功時のnumeric address列または固定失敗tagだけに限定する。
- 子processを信頼せず、親側でIPC shapeとnumeric addressを再検証し、その後も既存coreが全addressのglobal性と重複を検査する。
- process isolationはOS resolver停止時の親process保護であり、sandbox、権限分離、DNS応答の真正性、Windows native動作、実host到達性を証明しない。
- 現行Streamlit、legacy cache、provider、履歴schema、公開APIは変更しない。直接注入resolverを使う既存offline testは同じ振る舞いを維持する。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-03 | `fork` ではなく明示的な `spawn` を使う | Windows 11で `fork` は利用できず、WSLでも同じ起動方式を検証できるため | 配布方式がPython multiprocessingを安全に起動できない場合は、同じIPC・deadline契約を維持した専用subprocessへ見直す |
| 2026-09-03 | 1回の解決ごとに新しいdaemon子processを作る | 停止したOS resolverを要求単位でterminateでき、状態やDNS結果を要求間で共有しないため | 実測でspawn overheadが受入不能な場合は、上限付きworker poolと強制再生成を別Planで設計する |
| 2026-09-03 | DNS deadlineを5秒とし、CPUだけで成立させる | 現行画像HTTP timeout 10秒より短く停止し、提供されたCPU環境でGPU・NPU準備なしに適用できるため | Windows native実測または運用SLOから起動時間不足が確認された場合は、固定値と全体画像deadlineを同時に再評価する |

### 発見事項

- Pythonのmultiprocessing connectionでobjectを受けるとpickle復元を伴うため、初期案のobject IPCを採用せず、`send_bytes()` と上限付き `recv_bytes()` のASCII protocolへ変更した。
- 5秒すべてを結果待機へ使うと停止した子processを回収する時間が残らないため、結果待機を最大4.5秒、terminate・kill後のjoinを各最大0.25秒へ分けた。
- 初期GREENでは正常message受信後の終了待機だけが5秒deadlineの残りを使えていた。test SHA-256 `86a7d3630a1e1b7d55550a8332a80cff167c20c3fc2a2952b611a458ef31666e` の補足REDで1 failed / 69 passedを確認し、このjoinも4.5秒側の期限へ揃えた。
- 親processへ届く `KeyboardInterrupt` 等を固定domain errorへ誤変換しないよう、作成済みresourceを回収した後に再送出する契約を追加した。
- WSL2の実 `spawn` smokeでは、外部DNSへ進まない不正hostが固定 `error` bytesを返し、子processとpipeが正常に終了した。これはWindows nativeまたは実DNSの確認ではない。

### ロールバック

新規process resolver moduleとfocused testを取り除き、`ImageProxyService` の既定resolverを `BoundedImageDnsResolver` へ戻し、本Planと標準文書の実装状態をEXEC-023完了時点へ戻す。現行pipeline、runtime data、外部状態、履歴schemaは変更しない。

### 結果

完了。`ProcessIsolatedImageDnsResolver` を追加し、明示的な `spawn`、要求ごとの片方向pipeとdaemon子process、5秒application deadline、回収用の固定時間、最大512 bytesのASCII IPC、親側IP再検証、固定error、全経路cleanupを実装した。`ImageProxyService` の既定resolverはこのprocess分離版へ変更し、依存注入時の公開契約は維持した。

production module不在の初期RED test SHA-256は `e62cc8f8fdebb8a63eacf3b3e609c0ab7445d1a83c1127c777d7cd3c8616f8d9`、最終module SHA-256は `835bf099ab817c7fc44bd28271b219f6d0122f5f8eace75da5d34a97919122bd`、service module SHA-256は `48933eaeb776938987eec0c51f934e99930c143980d9819dea2d6d4cb66b1dbf`、最終process test SHA-256は `86a7d3630a1e1b7d55550a8332a80cff167c20c3fc2a2952b611a458ef31666e`、service test SHA-256は `4c7c2bf1ee263f92666316d4dea8be2e246c486d869be21e326349bb5a2660bf` である。focused 70件、proxy関連213件、全v2 665件、offline全体1397件を確認した。

検証の中心はfake process・pipe・clock、注入 `getaddrinfo`、socket・TLS・HTTP fixtureである。WSL2の実processは外部DNSへ進まない固定失敗経路1回だけを確認した。Windows native、実DNS、運用allowlist、実画像host、実CLIP model・encoder、画像ranking品質、credential、課金、現行pipeline、API、browser、外部委託中のフロントエンド、AIレビューハーネスは実行・確認・接続していない。5秒はapplication deadlineであり、Pythonからpreemptできない `Process.start()` のOS起動時間を絶対に制限しない。次の通常ローカル作業は [NEXT-STEPS.md](../NEXT-STEPS.md#後で必要になるもの) の5〜6を受け取ってから、新しいExecution PlanでCPU優先の実CLIP encoder process isolationと代表画像による品質評価を設計する。実provider用の1〜3はまだ不要である。


## EXEC-023: server-side画像proxy service

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-03
- 最終更新日: 2026-09-03
- 前提Plan: [EXEC-010](#exec-010-安全な画像取得phash固定clip境界)、[EXEC-021](#exec-021-pinned-ip画像https-transport)、[EXEC-022](#exec-022-server-side画像dns-resolver)
- 関連要件: `SEC-012`、`NFR-104`（[REQUIREMENTS.md](REQUIREMENTS.md#6-セキュリティ要件)）
- 関連設計: [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[SECURITY.md](SECURITY.md)

### 目的

商品画像を将来server-sideで取得するとき、運用者が起動時に固定するallowlist、1回だけの有界な名前解決、検証済みIPへ固定するHTTPS transport、画像検証coreを一つのserviceへ束ねる。画像URLを渡す呼出し側がrequestごとにpolicy、resolver、transportを差し替えられないAPIにし、設定不正と取得失敗をそれぞれ固定errorへ変換する。

利用者が将来観察できる結果は、許可した配信元の商品画像だけが同じserver-side security境界を通り、安全条件を満たさない画像は取得前または検証時に一貫して失敗することである。本Planでは合成host、注入resolver、注入transport、合成PNGによるoffline testまでを行う。実運用allowlist、実domain、実DNS・TCP・TLS・HTTP、実画像の取得成功は確認しない。

### 対象範囲

- `src/search_v2/image_proxy_service.py` に実装する `ImageProxyService` と固定messageの `ImageProxyServiceError`
- constructorでだけ受け取る1〜32件のexact tuple allowlistと、既存 `ImageProxyPolicy` によるcanonical host検証
- 省略時に `BoundedImageDnsResolver` と `PinnedHttpsImageTransport` を構築し、構築時には外部通信しないserver-side composition
- testと将来のserver bootstrapに限ってconstructorで注入できるresolver・transport境界
- URLだけを受け取る `fetch_image()` と、既存 `fetch_proxy_image()` への1回だけの委譲
- 設定不正を `image proxy configuration is invalid`、取得経路の全失敗を `image proxy request failed` へ変換する非露出境界
- 合成host・global documentation address・合成PNG fixtureによるfocused testと標準文書の同期

### 対象外

- 実Amazon CDN等の運用allowlist値、環境変数・設定file・secret manager・管理画面による設定投入
- 実domain、localhost、任意hostへのDNS、TCP、TLS、HTTP通信、実URL、実商品画像
- endpoint、web framework、認証・認可、tenant解決、rate limit、cache、監査log、metrics
- retry、別addressへのfailover、redirect、並列・batch取得、全体deadline、process isolation
- pHash・CLIP実行、画像ranking weightの有効化、画像品質評価
- 現行 `run_product_search()`、Streamlit、履歴、orchestratorへの接続
- 外部委託中のフロントエンドの確認、レビュー、起動、画面確認、テスト、バックエンド接続
- credential、外部送信、課金、AIレビューハーネスの実行、`docs/HARNESS-RUNBOOK.md` の変更

### 現在の状態

`image_proxy.py` はstrictな `ImageProxyPolicy` と、URL・allowlist・DNS全結果・transport応答・画像本体を検証する `fetch_proxy_image()` を持つ。`image_proxy_dns.py` は構造検証した最大8件のTCP用IPv4・IPv6を返し、`image_proxy_http.py` はその先頭IPへ直接1回だけ接続しながら元host名でTLS証明書を検証する。

`image_proxy_service.py` を追加し、server bootstrapで構築した後にURLだけを受ける `ImageProxyService` へ既存3 moduleを束ねた。serviceはfrozen・slots・repr非表示で、allowlist、resolver、transportをrequest単位で差し替えられない。HTTP client、socket、画像decoder、cache、credential、logは重複実装していない。各画像部品とserviceは現行pipelineから分離されたままである。

### 受入条件

1. constructorは組込みtupleのallowlistだけを受け、1〜32件、canonicalな小文字ASCII DNS host、重複なしという既存policy契約を維持する。設定値や低レベル例外を含めず、全設定不正を固定 `image proxy configuration is invalid` で拒否する。
2. resolver・transportを省略した場合、`BoundedImageDnsResolver` と `PinnedHttpsImageTransport` を各1回だけ構築する。constructorはDNS、socket、TLS、HTTPを開始しない。
3. resolver・transportはconstructorでだけ注入できる。publicな取得methodはURL以外のpolicy、allowlist、resolver、transport、timeout、上限を受け取らず、requestごとのsecurity policy上書きを許さない。
4. 有効なURLを既存policy・resolver・transportとともに `fetch_proxy_image()` へ1回だけ渡し、その `ProxyImage` を変更せず返す。service自身にretry、failover、redirect、cache、network client、画像再検証を追加しない。
5. 不許可・不正URLはresolver前、DNS例外・空・private混在はtransport前、transport・応答・画像不正はその後に既存coreで停止する。どの失敗でも自動再試行せず、service外へは固定 `image proxy request failed` だけを返す。
6. URL、host、allowlist、IP、raw response、低レベル例外をerror message、repr、log、返却modelへ新たに複製しない。credential、環境proxy、利用者データをserviceに保持しない。
7. 合成allowlistによる成功、default composition、設定不正、request単位の上書き不能、resolver・transportのexact 1-call、各段階の失敗順序、固定error非露出をRED→GREENで確認する。通常pytestのnetwork guardを解除しない。
8. focused・proxy関連・全v2・offline全体、lock、Ruff、文書構造、Python 3.10構文、差分検査に成功する。

### 実行順序と進捗

- [x] 2026-09-03: 既存proxy core、DNS resolver、pinned-IP HTTPS transport、通常pytestのnetwork guard、関連要件と未実装境界を確認した。
- [x] 2026-09-03: `EXEC-023` を登録し、allowlistをconstructorで固定し、request APIをURLだけに限定するservice責務を決定した。
- [x] 2026-09-03: 合成allowlist・注入fixtureによる成功、設定不正、呼出し順序、固定error、default compositionのREDテストを追加した。
- [x] 2026-09-03: production module不在の初期REDと、公開APIだけのscaffoldに対する29 failed / 2 passedの振る舞いREDを確認した。RED test SHA-256は `a2f44a4e9af8a8ac40bb2f2fc025f77242a176f117ce0103461c79df27931b93`。
- [x] 2026-09-03: `src/search_v2/image_proxy_service.py` を最小実装し、focused 31件をGREENにした。
- [x] 2026-09-03: proxy関連174件、全v2 626件、offline全体1358件とlock・Ruffを実行した。
- [x] 2026-09-03: 要件、backend、security、開発規約、課題、履歴、残作業、次の再開位置を同期した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_image_proxy_service.py` | production module不在または要求した振る舞い不足で失敗 | 初期は終了2のmodule不在。scaffold実行は終了1、29 failed / 2 passed、`NotImplementedError`。test SHA-256は `a2f44a4e9af8a8ac40bb2f2fc025f77242a176f117ce0103461c79df27931b93` |
| focused GREEN | 同上 | 全件成功 | 31 passed。最終module SHA-256は `0772279bc0c976846d18d41942ae4c20c568066fb2330b0f6251f4fa2effc593`、最終test SHA-256は `a2f44a4e9af8a8ac40bb2f2fc025f77242a176f117ce0103461c79df27931b93` |
| proxy関連 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_image_proxy.py tests/test_search_v2_image_proxy_http.py tests/test_search_v2_image_proxy_dns.py tests/test_search_v2_image_proxy_service.py` | 全件成功 | 174 passed |
| 全v2 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_*.py` | 全件成功 | 626 passed |
| 標準gate | lock、Ruff check/format、offline全体、`git diff --check` | 終了0 | lock 72 packages、Ruff check・format 167 files、offline 1358 passed / 1 deselected、差分検査成功 |
| 文書・構文 | 現行Markdown link・anchor・fence、Python 3.10 AST、AGENTS目次 | 欠落・構文・構造error 0件 | 現行Markdown 16件のlocal link 832件・heading 1131件・fence 195組、Python 3.10 AST 167件、AGENTS目次15件・安全規則を確認 |
| live・UI | 実DNS・実host・実画像・credential・browser・委託フロントエンド | 本Planでは実行しない | 対象外 |

### セキュリティ・データ・互換性

- allowlistと依存部品は信頼済みserver bootstrapが構築する設定であり、browser・利用者入力・provider応答から受け取らない。画像URLだけを非信頼入力として既存coreへ渡す。
- 注入resolver・transportはoffline testと将来のserver compositionのための境界であり、request APIには公開しない。実際のendpointを追加する場合は認証・tenant・rate limitを別Planで決定する。
- serviceは既存coreの8 MiB、10秒、no redirect、identity encoding、最大8 IP、global IP全件検証、先頭IPへの1回接続という制限を上書きしない。
- 新規moduleは現行Streamlit、legacy cache、provider経路、履歴schemaを変更しない。serviceの成功は現行検索・API・UIまたは実host E2Eの成功を意味しない。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-03 | allowlistはconstructorの必須tupleとし、取得methodはURLだけを受ける | 利用者入力や呼出し単位で配信元policyを緩める経路を作らないため | production設定の読込方式を決める別Planでも、service構築後の不変性を維持する |
| 2026-09-03 | resolver・transportは省略時にproduction adapterを構築し、注入はconstructorだけに限定する | 実行経路の既定値を明確にしつつ、network guardを解除しないoffline testを可能にするため | process isolationや別transportを導入する場合は新しいcomposition rootで再評価する |
| 2026-09-03 | serviceの外向きerrorを設定不正と取得失敗の2種類へ固定する | URL、host、IP、provider応答、低レベル例外を境界外へ漏らさないため | 運用観測性を導入する場合も利用者向けerrorと機密除去した内部eventを分離する |

### 発見事項

- 既存 `ImageProxyPolicy` はallowlistの件数、重複、canonical hostを検証するが、service constructorでも組込みtupleであることを先に固定した。list、generator、tuple subclassを暗黙変換して運用設定として受理しない。
- default resolverとtransportのconstructorは外部通信しない。通常pytestのnetwork guard下で実classを使うservice構築が成功し、取得を開始するまでDNS・socketを呼ばないことを確認した。

### ロールバック

新規service module、focused test、本Planと実装状態を更新した標準文書だけを取り除けばEXEC-022完了時点へ戻る。既存proxy core・DNS resolver・HTTPS transport、現行pipeline、runtime data、外部状態は変更しない。

### 結果

完了。`ImageProxyService` は組込みtupleの1〜32件allowlistを既存strict policyで検証し、既定の `BoundedImageDnsResolver`、`PinnedHttpsImageTransport`、`fetch_proxy_image()` を起動時に固定する。resolver・transportはconstructorでだけ注入でき、frozen serviceの公開取得methodはURLだけを受ける。設定不正と取得失敗を別の固定messageへ変換し、URL、host、IP、生例外を再掲しない。service自身にはnetwork client、retry、failover、redirect、cache、画像decode、credential、logを追加していない。

RED test SHA-256は `a2f44a4e9af8a8ac40bb2f2fc025f77242a176f117ce0103461c79df27931b93`、最終module SHA-256は `0772279bc0c976846d18d41942ae4c20c568066fb2330b0f6251f4fa2effc593`、最終test SHA-256は `a2f44a4e9af8a8ac40bb2f2fc025f77242a176f117ce0103461c79df27931b93`。focused 31件、proxy関連174件、全v2 626件、offline全体1358件、現行Markdown 16件のlocal link 832件・heading 1131件・fence 195組、Python 3.10 AST 167件、AGENTS目次15件、lock、Ruff、差分検査に成功した。

検証は合成allowlist、注入resolver・transport、合成PNGだけで行い、通常pytestのnetwork guardを解除していない。実domain、実URL、実画像、実DNS・TCP・TLS・HTTP、credential、課金、現行pipeline、API、browser、外部委託中のフロントエンド、AIレビューハーネスは実行・確認・接続していない。`docs/FRONTEND.md` と `docs/HARNESS-RUNBOOK.md` は本マイルストーンで変更していない。

次の画像工程ではDNSとCLIPの全体deadline・process isolation方式を実行環境へ合わせる。着手前に `NEXT-STEPS.md` の4、実画像取得と品質評価まで進める場合は5〜6が必要である。実Bonsai・Cloudflare・Outscraper用の1〜3はまだ不要である。


## EXEC-022: server-side画像DNS resolver

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-03
- 最終更新日: 2026-09-03
- 前提Plan: [EXEC-010](#exec-010-安全な画像取得phash固定clip境界)、[EXEC-021](#exec-021-pinned-ip画像https-transport)
- 関連要件: `SEC-012`、`NFR-104`（[REQUIREMENTS.md](REQUIREMENTS.md#6-セキュリティ要件)）
- 関連設計: [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[SECURITY.md](SECURITY.md)

### 目的

商品画像の許可済みhostを将来server-sideで取得するとき、OS resolverを1回だけ呼び、TCP接続に使えるIPv4・IPv6のnumeric addressだけを有界な結果としてimage proxy coreへ渡せるようにする。曖昧なhost、空・過剰・非TCP・family不一致・非canonicalな結果を固定errorで拒否し、DNS結果にprivate、loopback、link-local等が1件でも混じる場合は既存coreがtransport開始前に拒否する境界を維持する。

利用者が将来観察できる結果は、商品画像URLのhostを無制限または曖昧な名前解決結果のまま取得処理へ渡さず、安全条件を満たさない画像を取得前に停止できることである。本Planでは `socket.getaddrinfo` をfixtureへ置換した外部通信なしのadapter testまでを行い、実domainの名前解決成功や応答時間は確認しない。

### 対象範囲

- `src/search_v2/image_proxy_dns.py` に実装する `ResolveImageHost` 互換の `BoundedImageDnsResolver`
- canonicalな小文字ASCII DNS hostをresolver呼出し前に再検証する境界
- host、443番、`AF_UNSPEC`、`SOCK_STREAM`、`IPPROTO_TCP`、`AI_NUMERICSERV` を固定した `getaddrinfo` 1回だけの呼出し
- `getaddrinfo` のlistを1〜8件へ制限し、5要素tuple、IPv4・IPv6 family、TCP socket type・protocol、空のcanonical nameを検証する処理
- IPv4の2要素、IPv6の4要素socket address、443番、IPv6 flowinfo・scope ID 0、familyとIP versionの一致、canonicalなnumeric addressを検証する処理
- 結果順を維持したaddress tupleを既存 `fetch_proxy_image()` へ渡し、global IPの全件検証・重複除去を既存coreで行う統合test
- 注入 `getaddrinfo` fixtureによるfocused testと標準文書の同期

### 対象外

- 実domain、実Amazon CDN、localhostまたは任意hostへのDNS、TCP、TLS、HTTP通信
- DNS cache、TTL、DNSSEC、DoH・DoT、nameserver設定、search domain、resolv.conf、custom resolver
- OS resolver自体のdeadline・process isolation、非同期名前解決、別addressへのfailover・retry
- image proxy service・endpoint、運用allowlist、認証、API、cache、画像比較・ranking、CLIP asset・encoder
- 現行 `run_product_search()`、Streamlit、履歴、orchestratorへの接続
- 外部委託中のフロントエンドの確認、レビュー、起動、画面確認、テスト、バックエンド接続
- credential、外部送信、課金、AIレビューハーネスの実行、`docs/HARNESS-RUNBOOK.md` の変更

### 現在の状態

`image_proxy.py` は `ResolveImageHost = Callable[[str], Iterable[str]]` を注入し、結果を最大8件のglobal IPへ正規化して全件検証した後、`image_proxy_http.py` へ渡す。`image_proxy_dns.py` に、OS名前解決を限定引数で1回だけ行い、生結果を構造検証するproduction adapterを追加した。当初は結果順と重複を維持してglobal判定と重複除去をcoreへ委ねたが、運用hostの正常な一意9件を8件上限で拒否したため、生結果を最大64件まで全件構造検証し、順序維持の重複排除後にtransport候補を最大8件へ制限する方式へ修正した。

通常pytestは `socket.getaddrinfo` を含む主要な名前解決関数を遮断する。resolver constructorへ低レベルcallableを注入し、network guardを解除せずに引数、返却値、失敗経路を確認した。標準のresolverを使うtestもguardにより固定errorになることを確認した。

### 受入条件

1. hostが小文字ASCIIのcanonical DNS名でない、IP literal、単一label、末尾dot、空、253文字超過、制御文字を含む場合、`getaddrinfo` 呼出し前に固定errorで拒否する。
2. `getaddrinfo` をhostと443番、`AF_UNSPEC`、`SOCK_STREAM`、`IPPROTO_TCP`、`AI_NUMERICSERV` で1回だけ呼ぶ。例外時にretry、別resolver、hostname変換を行わない。
3. 戻り値は組込みlistかつ1〜8件だけを受け入れ、各項目を5要素tuple、IPv4またはIPv6、TCP socket type・protocol、空のcanonical nameへ限定する。
4. IPv4 socket addressはcanonical numeric addressと443番の2要素、IPv6はそれらに0のflowinfo・scope IDを加えた4要素へ限定する。familyとIP versionの不一致、zone ID、非canonical表記、型coercionを拒否する。
5. 有効なnumeric addressをresolver結果の順序どおりtupleで返す。重複除去と、private・loopback・link-local・reserved等を含む全addressのglobal判定は既存 `image_proxy.py` で行い、1件でも不許可ならtransportを呼ばない。
6. host、address、raw resolver tuple、OS例外を例外、repr、logへ含めず、入力不正と名前解決・結果不正を固定messageへ変換する。
7. IPv4・IPv6成功、exact call、入力不正、例外、空・9件、tuple・family・TCP・port・canonical address不正、core接続とprivate混在拒否をRED→GREENで確認する。
8. focused・proxy関連・全v2・offline全体、lock、Ruff、文書構造、Python 3.10構文、差分検査に成功する。

### 実行順序と進捗

- [x] 2026-09-03: `image_proxy.py`、`image_proxy_http.py`、通常pytestのnetwork guard、関連要件と未実装境界を確認した。
- [x] 2026-09-03: `EXEC-022` を登録し、名前解決結果の構造検証をadapter、global IP検証・重複除去を既存coreの責務に固定した。
- [x] 2026-09-03: `socket.getaddrinfo` fixtureによる成功、入力改ざん、例外、件数・構造・address不正、core統合のREDテストを追加した。
- [x] 2026-09-03: production module不在によるcollection errorの初期REDを確認した。network guard自己検査の誤判定を修正後、公開APIだけのscaffoldに対して54 failed / 2 passedの振る舞いREDを確認した。最終RED test SHA-256は `4c5048835b379e8bb2396a5a86d1d98a27820f3c175ff622b9e4cda7910a50be`。
- [x] 2026-09-03: `src/search_v2/image_proxy_dns.py` を実装した。追加の攻撃testで、注入された `ImageProxyDnsError` の任意messageを再掲する経路と、非hashableなfamily等で `TypeError` が漏れる経路をREDにし、どちらも固定errorへ修正した。
- [x] 2026-09-03: focused 60件、proxy関連143件、全v2 595件、offline全体1327件と標準gateを実行した。
- [x] 2026-09-03: 要件、backend、security、開発規約、課題、履歴、残作業、次の再開位置を同期した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_image_proxy_dns.py` | production module不在または要求した振る舞い不足で失敗 | 初期は終了2のmodule不在。自己検査修正後のscaffold実行は終了1、54 failed / 2 passed、`NotImplementedError`。最終RED test SHA-256は `4c5048835b379e8bb2396a5a86d1d98a27820f3c175ff622b9e4cda7910a50be` |
| focused GREEN | 同上 | 全件成功 | 60 passed。最終module SHA-256は `c5a9cfccc5b20208cdbf7321cd0ec64f515a2ff18ad0b585cf817957f917dbca`、最終test SHA-256は `94f9d43b04fb8035c43cc2b572da19e86e0a960af4df7f7a56ce1da450f4b1b0` |
| proxy関連 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_image_proxy.py tests/test_search_v2_image_proxy_http.py tests/test_search_v2_image_proxy_dns.py` | 全件成功 | 143 passed |
| 全v2 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_*.py` | 全件成功 | 595 passed |
| 標準gate | lock、Ruff check/format、offline全体、`git diff --check` | 終了0 | lock 72 packages、Ruff check・format 165 files、offline 1327 passed / 1 deselected、文書同期後の差分検査にも成功 |
| 文書・構文 | 現行Markdown link・anchor・fence、Python 3.10 AST、AGENTS目次 | 欠落・構文・構造error 0件 | 現行Markdown 16件のlocal link 820件・heading 1116件・fence 195組、Python 3.10 AST 165件、AGENTS目次15件を確認 |
| live・UI | 実DNS・実host・実画像・credential・browser・委託フロントエンド | 本Planでは実行しない | 対象外 |

### セキュリティ・データ・互換性

- hostとDNS結果は非信頼データとして扱い、固定error以外へ投影しない。resolverはcredential、環境proxy、HTTP client、cache、logを持たない。
- raw結果を8件で打ち切って受理せず、9件以上なら全体を拒否する。private等を除いて残りだけ使うこともせず、既存coreの全address global検証を維持する。
- `ResolveImageHost` callable契約と `fetch_proxy_image()` は変更しない。新adapterは注入可能な実装として追加し、現行pipelineと既存fixtureの挙動を変更しない。
- stdlib `getaddrinfo` はcall単位のdeadlineを受け取らない。本Planは応答時間を保証せず、production serviceへ接続する場合はprocess isolationと全体deadlineを別Planで決定する。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-03 | `getaddrinfo` callableをconstructorへ注入し、省略時だけcall時点の `socket.getaddrinfo` を使う | pytestのnetwork guardを解除せずexact callと結果検証を再現し、import時にguard前の関数を捕捉しないため | resolver backendを変更する場合は同じ引数・件数・固定error契約を維持する |
| 2026-09-03 | raw結果を1〜8件に限定し、先頭8件への切捨てをしない | 9件目以降に不許可addressがある状態を安全な部分結果へ見せないため | 実運用hostが8件を超える場合は、allowlistとattempt方針を含む別要件で上限を再評価する |
| 2026-09-03 | adapterはaddressの構造とcanonical表記を検証し、global判定・重複除去は既存coreへ残す | transport直前に全DNS addressを一括検証する既存security invariantを単一箇所へ維持するため | resolverをcore以外から公開利用する場合はpublic contractを別途設計する |
| 2026-09-08 | 生結果を最大64件まで全件構造検証し、順序維持の重複排除後にtransport候補を8件へ制限する | 運用hostの正常な一意9件を拒否せず、9件目以降の不正構造も見落とさないため | 実hostの生結果が64件を超える場合、または複数IPへの接続failoverを導入する場合に再評価する |

### 発見事項

- 初期testでは空hostの非露出確認に空文字を使い、どの例外文にも一致する自己矛盾があった。入力拒否とresolver未呼出しの検証は維持し、非空hostだけをmessage非露出の対象に修正した。
- 最初の実装は、注入されたcallableが `ImageProxyDnsError` を投げた場合に任意messageをそのまま通した。専用REDを追加し、低レベルcallableの全例外を固定 `image DNS resolution failed` へ再包囲するよう修正した。
- family・socket type・protocolを集合membershipだけで判定すると、list等の非hashable値が固定errorへ変換されず `TypeError` を漏らした。exact type検証をmembershipより先に置くRED→GREENで修正した。
- 実装中の型確認で、計画の対象外だった `socket.getaddrinfo("localhost", 443, ...)` を1回実行した。表示したのは返却値のPython型だけでaddressは表示していない。外部domain、HTTP、credential、課金は使っていないが、この確認は通常pytestのnetwork guard外だったため計画逸脱として記録する。

### ロールバック

新規resolver module、focused test、本Planと実装状態を更新した標準文書だけを取り除けばEXEC-021完了時点へ戻る。既存image proxy core・HTTPS transport、現行pipeline、runtime data、外部状態は変更しない。

### 結果

完了。`BoundedImageDnsResolver` はcanonicalな小文字ASCII DNS hostだけを受け、443番、`AF_UNSPEC`、`SOCK_STREAM`、`IPPROTO_TCP`、`AI_NUMERICSERV` を固定した `getaddrinfo` を1回呼ぶ。組込みlist 1〜8件、exact 5-tuple、IPv4・IPv6と対応sockaddr、空canonical name、443番、IPv6 flowinfo・scope ID 0、canonical numeric addressだけを結果順に返す。生入力・生結果・OS例外を固定errorへ変換し、global判定・重複除去・transport前の全件拒否は既存coreで維持した。

最終module SHA-256は `c5a9cfccc5b20208cdbf7321cd0ec64f515a2ff18ad0b585cf817957f917dbca`、最終test SHA-256は `94f9d43b04fb8035c43cc2b572da19e86e0a960af4df7f7a56ce1da450f4b1b0`。focused 60件、proxy関連143件、全v2 595件、offline全体1327件、現行Markdown 16件のlocal link 820件・heading 1116件・fence 195組、Python 3.10 AST 165件、AGENTS目次15件、lock、Ruff、差分検査に成功した。

主な検証は注入 `getaddrinfo`、transport、合成PNGによるoffline testで行った。上記の `localhost` 1回の型確認を除き、実domainの名前解決は行っていない。外部hostへのDNS、実TCP/TLS/HTTP、実URL、実画像、credential、課金、現行pipeline、API、browser、外部委託中のフロントエンド、AIレビューハーネスは実行・確認・接続していない。`docs/FRONTEND.md` と `docs/HARNESS-RUNBOOK.md` は本マイルストーンで変更していない。次の通常ローカル作業は新しい `EXEC-023` を作成し、`ImageProxyPolicy`、`BoundedImageDnsResolver`、`PinnedHttpsImageTransport`、`fetch_proxy_image()` を合成allowlistで束ねるimage proxy serviceをoffline TDDする。


## EXEC-021: pinned-IP画像HTTPS transport

### メタデータ

- タスクID: `TASK-008`
- 状態: 完了
- 作成日: 2026-09-03
- 最終更新日: 2026-09-03
- 前提Plan: [EXEC-010](#exec-010-安全な画像取得phash固定clip境界)、[EXEC-020](#exec-020-完了検索から表示用履歴への変換と保存)
- 関連要件: `SEC-012`、`NFR-104`（[REQUIREMENTS.md](REQUIREMENTS.md#6-セキュリティ要件)）
- 関連設計: [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[SECURITY.md](SECURITY.md)

### 目的

商品画像を将来server-sideで取得するとき、検証済みDNS結果のIP addressへ直接1回だけ接続しながら、TLSのSNIと証明書検証には元の許可host名を使えるようにする。通常のhost名接続による再DNS解決、環境proxy、redirect、自動retry、HTTP圧縮を使わず、応答を固定上限内で読み終えて全経路で通信資源を閉じる。

利用者が将来観察できる結果は、許可済みの商品画像だけをbrowserへ直接取得させず、server-sideの同じ安全境界へ通せることである。本Planではsocket、TLS、HTTP responseをfixtureへ置換した外部通信なしのadapter testまでを行う。実画像配信元への接続成功や画像品質は確認しない。

### 対象範囲

- `src/search_v2/image_proxy_http.py` に実装する `ImageProxyTransport` 互換adapter
- `image_proxy.py` から渡されたcanonical HTTPS URL、最大8件のglobal IP、10秒timeout、redirect禁止、identity encoding、8 MiB上限の再検証
- 検証済み一覧の先頭IPだけを使うIPv4・IPv6 socket接続と、追加addressへの自動failover・retry禁止
- 元host名を `server_hostname` にしたTLS handshake、hostname verification、証明書必須、TLS 1.2以上、TLS compression禁止
- origin-formのGET、固定Host・Accept・Accept-Encoding・Connection headerだけを送るHTTP/1.1要求
- 実peer IPと選択済みIPの一致、応答status・header framing、Content-Length・Transfer-Encoding、identity encoding、stream byte上限のfail-closed検証
- statusまたはmetadataが不適切な応答bodyを読まず、成功bodyだけを上限内のbytesへ投影し、response、TLS socket、raw socketを成功・失敗の全経路で閉じる処理
- socket・TLS context・HTTPResponseをfixtureへ置換するfocused testと標準文書の同期

### 対象外

- 実URL、実Amazon CDN、DNS、TCP、TLS、HTTP通信、実画像、配信元host allowlistの運用値
- DNS resolverの実装、proxy endpoint、認証、API、cache、画像比較・ranking、CLIP asset・encoder
- 接続失敗時の別IP failover、自動retry、redirect追従、HTTP content compression、cookie、proxy、custom CA
- 現行 `run_product_search()`、Streamlit、履歴、orchestratorへの接続
- 外部委託中のフロントエンドの確認、レビュー、起動、画面確認、テスト、バックエンド接続
- credential、外部送信、課金、AIレビューハーネスの実行、`docs/HARNESS-RUNBOOK.md` の変更

### 現在の状態

`image_proxy.py` はserver-side allowlist、URL、DNS結果、実peer IP、応答metadata、byte数、画像decoderを検証するnetwork非依存coreである。`image_proxy_http.py` は検証済み一覧の先頭IPへ直接接続し、元host名でTLSを検証する低レベルadapterとして追加済みである。DNS resolver、proxy endpoint、現行pipelineへの接続と実host通信は存在しない。

通常pytestはIPv4・IPv6 socketと主要な名前解決関数を遮断する。本Planのテストはmodule内のsocket factory、TLS context、HTTPResponse parserをfixtureへ置換し、ネットワークguardを解除しない。

### 受入条件

1. transport入力がcanonical HTTPS URL、canonicalで重複のない1〜8件のglobal IP、固定10秒、`allow_redirects=False`、`accept_encoding="identity"`、固定8 MiBに完全一致しない場合、socket作成前に固定errorで拒否する。
2. 選択した先頭IPのversionに応じたTCP socketを1個だけ作り、そのnumeric IPと443番へ直接接続する。接続失敗時に残りIPを試さず、DNS関数、proxy、Requestsを使わない。
3. default server-auth TLS contextをTLS 1.2以上、certificate required、hostname check有効、compression無効にし、URLの元host名をSNIと証明書検証へ渡す。不安全なcontextはHTTP送信前に拒否する。
4. TLS socketの実peer IPが選択済みIPと一致する場合だけ、pathとqueryから作るorigin-form GETを送る。Host、許可画像MIMEのAccept、`Accept-Encoding: identity`、`Connection: close` 以外の認証・cookie・referer・proxy用headerを送らない。
5. HTTP/1.0または1.1、100〜599のstatus、上限内のheaderだけを受け入れる。Content-Length、Content-Encoding、Transfer-Encodingの重複・競合・不正値を拒否し、chunkedは単独かつparserでdecode済みの場合だけ許可する。
6. redirect、非200、不許可content type、圧縮、宣言済み上限超過ではbodyを読まない。読込対象は8 MiBを1 byteでも超えた時点で固定errorにし、coreへは限定metadata、peer IP、上限内bodyだけを返す。
7. URL、path、host、IP、raw header・bodyを例外、repr、logへ含めない。response parse、read、send、TLS、TCPの成功・失敗を問わず、作成済みresponseとsocketを閉じる。
8. coreとadapterをfixtureで接続した成功、IPv4・IPv6、peer不一致、TLS不備、retryなし、request bytes、body非読込、上限、closeをRED→GREENで確認し、focused・全v2・offline全体、lock、Ruff、文書構造、Python 3.10構文、差分検査に成功する。

### 実行順序と進捗

- [x] 2026-09-03: `image_proxy.py`、通常pytestのnetwork guard、既存Bonsai・Outscraper HTTP adapter、関連要件と未実装境界を確認した。
- [x] 2026-09-03: `EXEC-021` を登録し、先頭の検証済みIPへ1回だけ接続するstdlib adapterとして責務を固定した。
- [x] 2026-09-03: socket・TLS・HTTP fixtureによる成功、入力改ざん、peer不一致、TLS不備、retryなし、response上限、全経路closeのREDテストを追加した。
- [x] 2026-09-03: production module不在によるcollection errorのREDを確認した。test SHA-256は `7639e1cadd52866f8de809111e5e61d2958bdd3cde92bfa5b6e56e1eae24e2aa`。
- [x] 2026-09-03: `src/search_v2/image_proxy_http.py` を実装し、曖昧なContent-Encoding拒否とHTTP/1.1 ALPN固定を補ってfocused 37件をGREENにした。
- [x] 2026-09-03: 関連83件、全v2 535件、offline全体1267件と標準gateを実行した。
- [x] 2026-09-03: 要件、backend、security、開発規約、課題、履歴、残作業、次の再開位置を同期した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| RED | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_image_proxy_http.py` | production module不在によりcollectionで失敗 | 終了2。`ModuleNotFoundError: No module named 'src.search_v2.image_proxy_http'`。test SHA-256は `7639e1cadd52866f8de809111e5e61d2958bdd3cde92bfa5b6e56e1eae24e2aa` |
| focused GREEN | 同上 | 全件成功 | 37 passed |
| 関連回帰 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_image_proxy.py tests/test_search_v2_image_proxy_http.py` | 全件成功 | 83 passed |
| 全v2 | `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_*.py` | 全件成功 | 535 passed |
| 標準gate | lock、Ruff check/format、offline全体、`git diff --check` | 終了0 | lock 72 packages、Ruff check・format 163 files、offline 1267 passed / 1 deselected、差分検査に成功 |
| 文書・構文 | 現行Markdown link・anchor・fence、Python 3.10 AST、AGENTS目次 | 欠落・構文・構造error 0件 | Markdown 16件、local link 811件、heading 1101件、fence 195組、Python 163件、目次15件に成功 |
| live・UI | 実host・実画像・credential・browser・委託フロントエンド | 本Planでは実行しない | 対象外 |

### セキュリティ・データ・互換性

- URLとqueryは利用者またはprovider由来の非信頼データである。検証後のHTTP requestにだけ使い、固定error、文書、テスト証拠へ実値を保存しない。
- transportはcredentialを引数・header・状態に持たず、新規socket 1個だけを所有する。環境proxy、`.netrc`、cookie、redirect、retry、名前解決を利用しない。
- `ImageProxyTransport` protocolは変更せず、新adapterを注入可能な実装として追加する。現行pipelineと既存のmock testの挙動は変更しない。
- custom CAと運用allowlistは追加しない。system trust store、許可host、TLS方針を変更する場合は送信先と証明書運用を別Planで再評価する。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-09-03 | Requests adapterを流用せず、stdlib socket・ssl・http.clientを使う | numeric IPへのTCP接続と元hostのSNI・証明書検証を同時に明示し、host名の暗黙な再解決を避けるため | 維持管理可能なpinned-IP adapter libraryを導入する場合は依存・TLS・proxy挙動を再評価する |
| 2026-09-03 | 検証済みaddressの先頭だけへ接続し、failoverしない | 1回の取得が複数TCP attemptへ暗黙に増えることを避け、retryなしの契約を保つため | 可用性要件とattempt上限を決めた場合は、各addressの再検証を伴う別Planで追加する |
| 2026-09-03 | response bodyをtransport内で上限付き読込してから返す | coreがmetadata拒否した時にもsocketを確実に閉じ、遅延iteratorによる資源リークを避けるため | streaming decoderへ変更する場合はclose所有権と上限をprotocol versionとして再設計する |

### 発見事項

- 初期実装はfocused 36 passed / 1 failedで、`Content-Encoding: identity, gzip` を「読まない応答」として投影し、曖昧なcodingをtransport errorへできていなかった。production側の単一token検証を厳格化し、既存テストを弱めず解消した。
- TLS contextへHTTP/1.1だけを提示するALPN固定が初期実装から欠落していた。補足RED test SHA-256 `99a8d3b7e35dbd43a27f50ad0cf0b5b18ce396f879bc72ed158becd5371d235d` で失敗を確認し、`set_alpn_protocols(["http/1.1"])` を追加してGREENにした。
- transportは意図どおり名前解決を行わず先頭IPだけを試すため、次の独立境界は件数とTCP address familyを限定するserver-side DNS resolverである。

### ロールバック

新規transport module、focused test、本Planと実装状態を更新した標準文書だけを取り除けばEXEC-020完了時点へ戻る。既存 `image_proxy.py`、現行pipeline、履歴schema、runtime data、外部状態は変更しない。

### 結果

完了。`PinnedHttpsImageTransport` を追加し、canonical HTTPS入力、1〜8件のglobal IP、固定timeout・上限、先頭numeric IPへの単一TCP接続、元host名によるTLS検証、HTTP/1.1 ALPN、peer一致、限定header・framing・body読込、全経路closeをfixtureで固定した。最終module SHA-256は `3538b1ab0172943987e553ab718f0207dfa1189dfa514fdda920a8ac82959744`、test SHA-256は `99a8d3b7e35dbd43a27f50ad0cf0b5b18ce396f879bc72ed158becd5371d235d` である。

検証はsocket、TLS context、HTTPResponseを置換したoffline testだけで行った。実DNS、実TCP/TLS/HTTP、実URL、実画像、credential、課金、現行pipeline、API、browser、外部委託中のフロントエンドを実行・確認・接続していない。`docs/FRONTEND.md` と `docs/HARNESS-RUNBOOK.md` も本マイルストーンでは変更していない。次の通常ローカル作業は新しい `EXEC-022` を作成し、server-side DNS resolverを外部通信なしでTDDする。


## EXEC-002: attested AI review境界の実装

> 統合元: `docs/plans/EXEC-002-ATTESTED-AI-REVIEW-BOUNDARIES.md`。統合前の文書は `docs/old/` に保存する。


### メタデータ

- タスクID: `TASK-007`
- 状態: 進行中（7/7 actual handler、frozen sign/judge、exact nonce contract、workflow初期化、credential-free deployment check、独立security review、rootless Podman実配備、具体的TaskSpec v2 canaryの `nonlive_ready`、live launcher用initial request準備は完了。別途承認するfull 7-phase OpenAI live E2Eとnonce ledger長期運用が残る）
- 作成日: 2026-08-15
- 最終更新日: 2026-09-02
- 前提タスク: [TASK-006](#task-006-ai相互レビューとtddハーネスの導入)
- 関連負債: [TD-009](ISSUES.md#td-009-ai変更の役割分離と証拠契約)
- 運用規約: [AI_GUIDE.md](DEVELOPMENT.md#統合済みaiレビュー規約)
- 実行手順: [HARNESS-RUNBOOK.md](HARNESS-RUNBOOK.md)

### 目的

candidateがruntime、snapshot、evidence、credential、network、judgeを改ざんできない境界でAI相互レビューを行えるようにする。利用者が観察できる完了状態は、root-owned trusted releaseとrootless Podman hostでclosed 7-phase workflowがfail closedに動き、raw offline evidence、reviewer/adversaryのdistinct provisioned broker lifecycle、Ed25519署名をattested judgeまで一貫して検証できることである。

`pass` でも人間承認を維持し、自動commit、push、mergeは行わない。

### 対象範囲

- root-owned stdlib external launcher/preflightとruntime manifest
- external approved manifest SHAとhuman-approved patch SHAに結ぶcredential-free workflow初期化
- standalone Git commitからのbase/candidate/RED read-only snapshot
- common sensitive path policyとroot `.env.example` の安全な除外
- rootless Podmanのnetworkなしoffline runnerとraw execution evidence
- bounded sanitized text-only review packet
- tool-free GPT-5.6 Sol requestとfixed model/effort/service tier
- broker/gatewayのnetwork分離、fixed egress、raw inspect、cleanup evidence
- 失敗attemptを含むtoken/cost SQLite ledger
- Ed25519 artifact、nonce/replay防止、attested judge
- 7-phase digest chain、durable phase ledger、phase別mount/output
- adversarial regression、schema、CI、runbook
- credential/API/external networkなしの4-image deployment preflight

### 対象外

- 自動commit、push、merge
- 検索アプリのUI、ブックマーク表示数、検索結果件数の変更
- 削除済みPDFの復元または参照
- Bonsai、Outscraper、Amazonの実通信
- 未コミットbootstrap変更自身を自己attest済みと宣言すること
- credential、送信内容、費用の人間承認なしにOpenAI APIを実行すること
- agentic modelへcandidate filesystem、shell、toolを与えること
- rootful Dockerに合わせてproduction境界を弱めること

### 現在の状態

#### 実装済みの境界

| 領域 | 主なpath | 現行結果 |
|---|---|---|
| release/preflight | `runtime_release.py`、`workflow_init.py`、`external_launcher.py`、`preflight.py`、`deployment_check.py` | external approved manifest SHA、manifest/asset/Python inode/digestを固定。TaskSpec v2とhuman-approved patchからinitial requestを凍結し、credential-free 4-image checkは `nonlive_ready` に限定 |
| coordinator | `coordinator_launcher.py`、coordinator image | nonroot rootless Podman `keep-id`、seccomp、networkなし、read-only、phase別mount |
| snapshot | `snapshot.py`、`sensitive_paths.py`、`outer_workflow_runtime.py`、`coordinator_launcher.py` | Git再hash、read-only snapshot、exact RED overlay、credential path拒否、root `.env.example` 空値検査後除外、専用physical store/RO mount |
| offline | `offline_runner.py`、`offline_phase_protocol.py`、`offline_outer_executor.py`、runner image | complete prepared batch、networkなしraw execution、coordinator再finalize |
| packet/request | `review_packet.py`、`codex_adapter.py` | bounded text-only packet、credential scanner、strict Responses schema、toolsなし |
| egress/broker | `broker_phase_protocol.py`、`broker_outer_executor.py`、`broker_egress_provisioner.py`、`broker_executor.py`、broker/gateway image | 2役prepared batch、role/attempt別network、credential-free fixed gateway、raw lifecycle、frozen final ledger、coordinator再finalize |
| token/cost | `pricing_policy.py`、`openai-pricing-policy.json` | `service_tier=default`、失敗attemptの事前予約、標準544K/4.54 USD、絶対1,088K/7.94 USD |
| attestation | `attestation.py`、`nonce_ledger.py`、`attested_judge.py`、`coordinator_attestation_inputs.py` | raw offline、2 provisioned lifecycle、frozen final ledger、Ed25519、exact SQLite nonce/replayを検証。host broker DBなしでsign/judgeへ接続 |
| phase protocol | `phase_protocol.py`、`phase_execution_adapters.py`、`outer_driver.py`、`outer_workflow_state.py`、`outer_workflow_runtime.py`、`external_launcher.py`、`production_cli.py`、`coordinator_workflow_ops.py` | closed order/digest/exclusive tree、outer entry、inner operation、7/7 actual handler、readiness gate |

phase順序は次である。

```text
snapshot -> red-snapshot -> offline -> review-packet -> broker -> sign -> attested-judge
```

`snapshot` workflow prepareだけがcandidateをmountし、`sign` workflow prepareだけがprivate keyをread-only mountする。`attested-judge` prepareだけがlauncher所有のprivate nonce ledger rootを専用read-write mountで受け取る。`offline` と `broker` だけがouter executorを使う。outer workflow runtimeは各phaseを `NN-phase/{prepare-input,prepare-output,finalize-input,finalize-output,committed}` へ分ける。`committed/` はrequest、prepared/finalized transition、payload、`coordinator-output.json`、`artifact-manifest.json`、`phase-result.json` を保存し、external phaseではexact `external-evidence.json` も保存する。初回はinitial inputs、それ以後は直前のimmutable committed treeを `prior-artifacts/` へcopyし、phase完了後はtree全体をread-only化する。

brokerのouter rawは両roleのprovisioned lifecycleに加え、失敗attemptを含むcanonical frozen `final_ledger` を持つ。host SQLiteのraw copyやpath/device/inodeのcopyを証拠にせず、prepared/raw pairを `external_execution_sha256` と `phase_sha256` へ結ぶ。同じallowlist/pricing policy bytesを使うと、host DB削除後でもtyped `ProvisionedBrokerExecutionEvidence` 2件を再構築できる。

さらに `reconstruct_attestation_inputs` がimmutable PhaseChain、dedicated snapshot、raw offline runs、broker prepared/raw/frozen ledgerから、host DBなしでsign/judge共通bundleと2つのtyped evidenceを復元する。`sign` はこのimmutable evidenceからrole別expectationを署名し、`attested-judge` は同じevidenceからexpectationを独立再構築する。canonical prepared/raw pairとpinned policy bytesを再finalizeするため、host broker ledger削除後もverdictへ到達できる。raw DB copy/bind mountとruntime再probeはproduction証拠にしない。

#### 現在の運用上の残り

- external launcherの `--workflow`、inner `prepare|finalize` CLI、7/7 actual handlerは接続済みである
- readiness gateはhandler tupleが7 phase全体と完全一致することを、credential FD読取り・broker ledger作成前に検査する
- `workflow-init` はexternal approved manifest SHAとhuman-approved patch SHAを必須にし、sequence 1 requestをcredential/networkなしで生成する
- `--deployment-check` はcredential/API/external networkなしでrootless backendと4 imageを確認し、`production_e2e_complete=false` の `nonlive_ready` だけを返す
- Arch WSL2の実hostへ専用UID/subuid/subgid、rootless Podman `keep-id`、trusted `/opt`、private `/var/lib`、現行4-role image、具体的TaskSpec v2 canaryを配備し、credential-free `nonlive_ready` を確認した
- external manifest/patch anchorを再照合し、UID 1100所有のstandalone candidateとprivate artifact rootからlive launcherが読めるinitial requestを生成した
- nonce ledgerの長期保持、backup、容量、rotation運用が未定義である
- external OpenAI APIはcredential/費用opt-inがなく未実行である

package/user/system変更、rootless Podman設定、image build/pull、release installは人間承認後に実施した。ただし、ここまでの結果はcredential-freeな非live配備準備・検証であり、`nonlive_ready` をlive/E2E完了とは扱わない。OpenAI credential、external API、broker external network、full 7-phase live workflow、課金は実行していない。個別APIを手作業でつないだlive実行も行わない。

### 実行手順と進捗

#### M1: import前trust anchor

- [x] stdlib-only launcherがharness import前にmanifestとraw assetを検証する
- [x] open FD、path component、symlink/hardlink、owner/mode、candidate UIDの書換権限を検査する
- [x] `-I -S`、root-owned Python prefix/sys.pathを要求する
- [x] 実行中 `sys.executable` をmanifest Pythonのpath/inode/SHA-256へ一致させる
- [x] coordinator imageをcandidate外のpinned digestへ固定する
- [x] external approved manifest SHA、TaskSpec v2、exact task/public key、protected clean candidate、human-approved patch SHAからinitial requestを作り0500/0400へ凍結する

#### M2: immutable snapshotとraw offline runner

- [x] standalone cloneのcommit/tree/blobとGit metadataを検証する
- [x] base/candidateをcontent-addressed read-only snapshotへ変換する
- [x] REDをbase + exact test overlayへ限定し、production差分混入を拒否する
- [x] common sensitive pathをpathで拒否する
- [x] root `.env.example` は64KiB以下のUTF-8、NUL/credential-like contentなし、全assignment空値を検証後、実行snapshotから除外する
- [x] networkなし、read-only、capabilityなし、resource制限付きrunnerからraw evidenceを得る

#### M3: bounded packet、broker、予算

- [x] trusted diffと限定contextだけからcanonical packetを作る
- [x] credential-like content、credential path、binary、byte/token上限を拒否する
- [x] canonical Responses request JSON全体を260K input上限/250K warningの予約対象にする
- [x] reviewer=`high`、adversary=`xhigh`、verbosity=`low`、toolsなし、`store=false`、`service_tier=default` を固定する
- [x] brokerとgatewayを別network権限へ分け、gatewayを `api.openai.com:443` へ固定する
- [x] raw inspect、post-inspect、cleanup、absenceをrole別provisioned evidenceへ結ぶ
- [x] root-owned stdlib outerがbroker ledgerをO_EXCL・0600・STRICT schemaで新規作成し、既存fileを拒否する
- [x] attemptを起動前にledgerへ予約し、失敗attemptもtoken/costへ算入する

#### M4: Ed25519とattested judge

- [x] private keyをsign workflow prepareだけへread-only mountする
- [x] private nonce ledger rootをattested-judge workflow prepareだけへ専用read-write mountする
- [x] task/policy/gate/TDD/reviewをruntime/snapshot/request/runner/log/nonceへ署名する
- [x] raw offline runから全acceptanceのgate/TDDを再構築する
- [x] reviewer/adversaryのdistinct provisioned lifecycleを各1件要求する
- [x] canonical prepared/raw evidenceとpinned policyを再finalizeし、final ledgerの失敗attempt、累積token/cost、pricing policy digestを再検証する
- [x] tamper、replay、別task/head/snapshot/runtime、重複session/lifecycleをfail closedにする
- [x] clean provenanceの `pass` でも `human_approval_required=true` を維持する

#### M5: closed phase protocol

- [x] 7つのphaseと実行domainをclosed tableへ固定する
- [x] request/action/result/artifactをcanonical digest chainへ結ぶ
- [x] SQLite ledgerをconsume-before-executeにし、同workflow/phase replayを拒否する
- [x] candidate/signing key/output mountをphaseごとに限定する
- [x] coordinator outputをtyped envelopeとして再検証し、durable historyと分けて保存する
- [x] offline/brokerをそれぞれtyped prepare→outer→finalizeへ接続し、generic outer descriptorをproduction brokerから除外する
- [x] external prepared/raw evidenceをexclusive保存し、`prior-artifacts/` へ累積する
- [x] broker frozen final ledgerをphase chainへ結び、host DB削除後の再finalizeとtamper拒否を確認する
- [x] stdlib固定state machineが7phaseのrequest/action/output/result/next requestをcanonical再検証する
- [x] external launcherの `--workflow` をstdlib outer runtimeへ接続し、phase別working treeをexclusive作成・read-only化する
- [x] inner `prepare|finalize` CLIを登録し、offline/brokerをactual typed handlerへ接続する
- [x] verified physical snapshotを一般artifactから分離した専用read-only mountへ渡し、semantic/physical集合をexact照合する
- [x] snapshot、red-snapshot、review-packetのactual typed handlerを接続する
- [x] frozen phase evidenceからlive broker DBなしでsign/judge共通input bundleを再構築する
- [x] readiness gateが7/7 handlerの完全一致をcredential read・broker ledger作成前に検査する

#### M6: production統合とhandoff

- [x] frozen common bundleを消費してcanonical署名artifactを作る `sign` actual handlerをouter `--workflow` entryへ接続する
- [x] frozen common bundleからverdictを出し、host ledger削除後のpassとtamperされたfrozen evidence拒否を確認する `attested-judge` actual handlerを接続する
- [x] nonce DBのexact schema・PRAGMA・index・file identity・sidecar不在を固定し、replay setを単一transactionで原子的に予約する
- [x] credential/API/external networkなしでrootless backendと4 imageをlocal inspect/smokeし、`nonlive_ready` evidenceだけを返すdeployment checkを追加する
- [ ] 失敗時に同workflowを再開せず、新しいworkflow IDでやり直す運用をE2Eで確認する
- [x] 管理者承認後に専用user/subuid/subgid/rootless Podman、trusted `/opt`、private `/var/lib` を用意する
- [x] 人手監査済みclean commit、具体的TaskSpec v2 canary、external approved manifest SHA、4 image digestからroot-owned releaseをinstallし、実hostで `--deployment-check` のcredential-free `nonlive_ready` を確認する
- [x] external manifest/patch anchorを再照合し、UID 1100所有のstandalone candidateとprivate artifact rootからlive launcherが読めるinitial requestを生成する
- [ ] 別途承認した送信内容、OpenAI credential、費用上限を使うfull 7-phase OpenAI live workflowをE2Eで確認する
- [ ] nonce ledgerの長期保持、backup、容量、rotation、古いattestation検証方針を定義する
- [x] schema生成・一致、full offline pytest、Ruff、lock、diff、Markdown link/anchorを最終確認する
- [x] 独立security reviewの未修正CRITICAL/HIGHを0にし、7-phase重点回帰とnonce再監査を完了する
- [x] TASKS、TECH-DEBT、WORKLOG、runbookを最終状態へ同期する

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 現在の記録 |
|---|---|---|---|
| lock | `uv lock --check` | 終了0 | 2026-08-16に終了0 |
| lint | `uv run ruff check .` | 終了0 | 2026-08-16に終了0 |
| format | `uv run ruff format --check .` | 終了0 | 2026-08-16に終了0 |
| offline全体 | `uv run pytest -m 'not live_api'` | liveを実行せず終了0 | 2026-08-16の現行gateは726 passed / 1 deselected |
| trust/phase | `uv run pytest -q tests/test_ai_review_runtime_release.py tests/test_ai_review_coordinator_launcher.py tests/test_ai_review_phase_protocol.py tests/test_ai_review_outer_driver.py tests/test_ai_review_outer_workflow_state.py` | adversarial caseを含め終了0 | 関連回帰は終了0 |
| outer protocol | `uv run pytest -q tests/test_ai_review_offline_phase_protocol.py tests/test_ai_review_broker_phase_protocol.py tests/test_ai_review_phase_execution_adapters.py` | prepare/raw/finalize、frozen ledger、tamper caseを含め終了0 | 関連回帰は終了0 |
| broker/judge | `uv run pytest -q tests/test_ai_review_broker_executor.py tests/test_ai_review_broker_egress_provisioner.py tests/test_ai_review_attested_judge.py` | lifecycle/ledger/tamper caseを含め終了0 | AI suiteの一部として終了0 |
| frozen sign/judge | `uv run pytest -q tests/test_ai_review_coordinator_attestation_inputs.py tests/test_ai_review_attestation.py tests/test_ai_review_attested_judge.py` | host DB/runtime probeなしでsign/judgeが同じimmutable evidenceからexpectationを再構築し、tamper/replayを拒否 | 対象testは終了0 |
| workflow init / deployment check | `uv run pytest -q tests/test_ai_review_workflow_init.py tests/test_ai_review_deployment_check.py` | external anchors、initial request freeze、credential/APIなし、4-image local smoke、`nonlive_ready` contractを検証 | full gateへ含めて終了0。実hostでも `nonlive_ready` とUID 1100所有initial requestを確認 |
| AI test suite | `uv run pytest -q tests/test_ai_review_*.py tests/test_network_policy.py -m 'not live_api'` | 終了0 | 2026-08-16の現行gateは650 passed / 1 deselected。生成asset同期検査も含む |
| patch | `git diff --check` | whitespace errorなし | docs対象は終了0 |
| docs | local Markdown link/anchor検査とshell構文検査 | missing・構文errorなし | 35 Markdown / 全78 sh/bash blockで終了0 |
| independent security review | 7-phase重点回帰、nonce再監査、finding集計 | 未修正CRITICAL/HIGH 0 | 重点回帰215 passed、nonce再監査完了 |
| production host | `id` / rootless Podman / subuid/subgid / trusted path / deployment check / workflow init / 7-phase E2E | fail-closed境界、`nonlive_ready`、artifact chain成立を段階別に確認 | 専用UID、rootless Podman、trusted release、4 image、`nonlive_ready`、UID 1100所有initial requestまで確認。live 7-phaseは未実行 |
| OpenAI live | 人間opt-in後の限定run | 送信・usage・費用・request IDを記録 | 未実行。credential/費用承認なし |

上の件数は2026-08-16の実行証拠であり、将来の固定期待値ではない。Python 3.10 local interpreterがないため、Python 3.10はCI上の将来検証境界として残る。

### セキュリティ・データ・互換性

- `.env`、Streamlit secrets、生cache、利用者検索入力、API response本文を読出し・copy・artifact化しない
- root `.env.example` はsize/UTF-8/NUL/credential-like content/空assignmentを検証し、snapshotから除外する
- OpenAI credentialはbroker processだけへ注入し、gateway、argv、stdin、artifactへ入れない
- private keyはcandidate外0400 fileとし、sign workflow prepare以外へ渡さない
- nonce ledger rootはlauncher/coordinator所有の0700 directoryとし、attested-judge prepare以外へ渡さない
- external AIを通常pytest、CI、release build、preflight診断から起動しない
- app本体、cache schema、ブックマークUI、削除済みPDFへ変更を広げない

### 判断記録

| 日付 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-08-15 | agentic Codexへcandidateをmountせずtext-only packetを使う | credentialとcandidate実行権を同じnamespaceへ置かないため | shell/tool reviewは別のoffline境界を設計するまで禁止 |
| 2026-08-15 | Ed25519に `cryptography` を使う | stdlibに署名実装がなく、openssl subprocess鍵処理を避けるため | dependency/runtime digestへ固定 |
| 2026-08-15 | bootstrap変更を自己attestしない | trust anchor導入前の変更を新anchor自身で証明できないため | 人手監査済みcommitから別trusted buildが必要 |
| 2026-08-16 | coordinator production backendをrootless Podman `keep-id` に限定する | host ownerとcontainer UIDのRW mount意味を一意に保つため | Docker/rootful hostはfail closed。正式な別mappingを設計した場合だけ見直す |
| 2026-08-16 | brokerとgatewayを分離し、gatewayをcredential-freeにする | credential保有主体へunrestricted egressを与えないため | policy digest、raw inspect、cleanup証拠が必須 |
| 2026-08-16 | 失敗attemptも予算へ算入する | paid request後のtimeout/errorで上限を回避させないため | 新packet/workflowでも旧ledgerを改ざんして戻さない |
| 2026-08-16 | clean attestationは `pass` を許すが人間承認を維持する | provenance検証と統合権限を分けるため | 自動commit/push/mergeは対象外 |
| 2026-08-16 | initial requestはexternal manifest anchorとhuman-approved patchから専用initializerで作る | 手書きworkflow ID、placeholder、検査対象manifestの自己承認を防ぐため | dirty checkoutや同じmanifestから都合よく作った期待SHAを権威入力にしない |
| 2026-08-16 | live前の配備確認をcredential-free `nonlive_ready` に限定する | host/image前提の検査と外部送信・課金を分離するため | full E2E、API、credential、external networkの成功とは別に記録する |

### 発見事項

- モデルcontextは1.05Mだが、272K超のinputには料金倍率がある。projectは1 call総予約272K、input 260K、output 12Kへ保守的に制限した
- packet本文だけを数えるとschema/envelope分を漏らすため、canonical request JSON全体のUTF-8 bytesを予約上界に変更した
- fixed gatewayの設計だけでは実配置を証明できないため、create/inspect/post-inspect/cleanup/absenceのraw lifecycleが必要になった
- successful broker evidenceだけでは失敗したpaid attemptを隠せるため、final SQLite ledger全体の検証が必要になった
- live SQLite identityはabsolute path/device/inodeへ結び付くため、raw DB copyやbind mountを後段証拠にできない。broker終了時のcanonical frozen ledgerをouter rawへ入れ、phase digestへ結ぶ方式へ変更した
- 開発途中はbroker phase finalizeのpath依存を除去してもjudgeが実行時状態を再計測していた。そのためcanonical frozen evidenceから再finalizeする専用APIと、sign/judge共通bundle adapterへ移行した
- 開発途中のsingle-phase限定は7/7 actual handlerの接続とreadiness gateにより解消した。不完全releaseは依然としてcredential読取り前にfail closedする
- hostのrootful Dockerはproduction要件を満たさない。境界を弱めずrootless Podman hostへ移す
- rootful Docker storeの古いimageはrootless Podman user storeから見えることも、現行manifestの4-role digestに一致することも証明しない。承認済みrelease digestで別途用意する
- fixed state machineとouter entryがあっても、全phaseのactual handlerと専用mountが閉じていなければ運用者の手作業でbindingを崩し得る
- outer/inner operationを追加しても、全7 phaseのactual handlerと専用mountが同じclosed contractへ接続されなければ実環境E2Eにはならない

### ロールバック

external brokerはdefault disabledとし、production entryが完成しない、host条件が不足する、検証が失敗する場合は外部AIを起動しない。既存アプリの検索経路はハーネスから独立しているため、検索UI、cache、Bonsai/Outscraper設定を削除・変更しない。

失敗したphase/workflow/attemptを巻き戻して再利用しない。artifactを監査用に保持する必要がなければ、人間が対象を確認してcandidate外一時rootを削除する。private key rotationは既存attestationの検証方針を決めた別releaseで行う。

### 結果

候補コードからruntime、snapshot/専用mount、offline network、broker egress、credential、frozen費用ledger、署名、judgeを分ける境界部品、typed external protocol、stdlib固定7-phase state machine、outer `--workflow` entry、7/7 actual handler、frozen sign/judge、exact nonce contract、readiness gate、external-anchor付きworkflow initializer、credential-free deployment check、敵対的回帰テストを実装した。最終gateと独立security reviewは完了し、未修正CRITICAL/HIGHは0である。rootless Podman host、clean release、具体的TaskSpec v2 canary、4 image、実host `nonlive_ready`、UID 1100所有のlive用initial requestまで確認した。残作業は別途人間承認するlive 7-phase E2Eとnonce ledgerの長期運用定義である。

外部OpenAI APIは実行しておらず、credential・送信内容・費用の人間承認もない。これをlive運用済み、課金確認済み、bootstrap自己attest済みとは表現しない。


## EXEC-095: 仕様定義を与えたBonsaiの属性同定を検証する

- 状態: 完了（検証完了、RAG試作への進行基準は未達）
- 作成・更新: 2026-09-09
- 関連: [検索専用属性の実データ品質](ISSUES.md#検索専用属性の実データ品質)、EXEC-094

### 目的と境界

正しい仕様定義を取得できたと仮定したときに、Bonsaiが原文の数量条件を該当属性へ対応付けられるかを測る。資料検索器を作る前のoracle-context診断であり、検索recall・本番intent経路・実商品補完・ranking・frontendは対象外。src、既存prompt、normalization、registry、cacheは変更しない。比較用の合成入力・事前に用意した定義・判定器と要求をtools/testsへ分離する。資料はメーカーの公開用語・仕様から短く要約し、出典と凍結時点を保存する。定義は正解資料として意図的にモデルへ渡すが、caseの期待IDや合否、採点用属性keyは渡さない。

### 事前固定の計画と基準

- 正例12件: 既存6カテゴリ（顕微鏡、スキャナー、シュレッダー、掃除機、ポータブル電源、除湿機）と新規6カテゴリ（モニター、カメラ、スピーカー、ルーター、UPS、冷却ファン）。既存カテゴリの入力と新規入力を分けて集計する。
- 各正例を3条件で比較: 候補名・単位のみ、候補名・単位・定義、名称・単位を隠した定義（候補の順序とopaque IDも変更）。同じ原文に対して同じ候補概念を与える。定義の有無以外が同じ最初の2条件で増分効果を測り、3条件目で意味と根拠による選択を調べる。候補名のみの成功を定義の増分効果へ数えない。
- 不足4件と曖昧4件は定義付き・名称非表示の2条件、計16 calls。根拠から一意に特定できない場合はunresolvedが正解である。
- 合計52 calls、temperature0、seed固定、各1 call・retry0、1 worker・context8192、各最大900秒・応答1 MiB。localhost 127.0.0.1:18080/v1/chat/completions、既存Bonsai-8B.ggufとllama-server、無認証・API費用0。継続授権と今回の実行指示の範囲で条件を通知して実行する。
- 応答は候補IDまたはunresolvedの1 field。schemaは全候補と未確定を許し、正解IDを強制しない。strict JSON・候補所属を検証し、誤ID・余計なfield・重複key・不正応答・通信失敗も分母から除かない。
- 次のRAG検索器試作へ進めるための限定基準: 定義付き12/12、名称非表示12/12、不足/曖昧16/16。これは本番適格性や全商品精度の保証ではない。合否にかかわらず全結果を報告し、同じbatch中にprompt・入力・定義・期待値・判定器を変更しない。

### 実装・検証・記録

要求生成とstrict採点、候補順/ID変更後の対応、gold非混入、欠落資料、失敗を合格にしないことをofflineで検証する。実行前に入力・定義・出典・judge/source/prompt/model/server・全要求byteのSHA256を新規private manifestへ固定する。ログ先は /home/products/bonsai-test-logs/20260909-exec095-definition-01。全要求・全生成応答・失敗・評価・runtime計測を0700/0600で保存し、各server停止と最終port停止、実行前後のhashを確認する。

診断toolの追加を停止すればrollbackでき、本番データ移行は不要。完了には実測、offline回帰、文書・権限・停止の確認と、意味品質の合否を含む報告を必要とする。RAG導入そのものと既存EXEC-094の根本品質問題は別の残作業として維持する。

EXEC-095準備時の補足: 顕微鏡は装置全体、シュレッダーは手差しで一度の投入という用途を明示し、複数の仕様に解釈できる入力を正例の一意な正解へ押し込まない。残る既存4入力は前回と同一。新規6入力もこの比較のために事前固定した合成入力である。前回の自由名称生成3/9とは入力・出力契約が違うため、直接の改善率にはしない。blindでは名称と独立したunit fieldを両方隠すが、定義文中の時間や数量の意味は保持する。


EXEC-095実行準備の結果:

- 新規diagnostic tool未作成時のREDは `pytest tests/test_bonsai_definition_probe.py -q --tb=short` がmodule未存在でcollection error（exit2）。既存production不具合の再現とは区別する。要求/採点契約の実装後41 passed、集計境界3件の追加後44件。既存response log回帰と合わせて53 passed（0.39秒）。最終テストSHA256 4f11873afeb5162c3dda8e0d89e62c93cf1a5ce9f812c745c385a53792a917eb。
- 通常offline全体2396 passed・13 skipped・30 deselected（49.80秒）。Ruff check・format284 files・lock79 packages成功。
- 全52要求とmanifest、対象sourceのtar snapshotをprivate rootへ保存した。最大要求2019 bytes。正解候補の位置は通常が先頭3・中央7・末尾2、blindが先頭7・中央2・末尾3で、常に同じ位置を選ぶだけでは限定合格基準を満たせない。blindのopaque IDは通常と非重複。
- model SHA256は284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54。server binaryと共有libraryもmanifestへ束縛した。実行前の全file0600・directory0700を確認済み。


### EXEC-095の実測結果

52 calls・retry0を608.444秒で完了した。全52応答がHTTP200・完全受信・strict JSON合格。model/server/shared library/sourceの実行前後hashは全て一致し、各所有server停止と最終port18080非listen、全file0600・directory0700を確認した。今回のsource62 filesはEXEC-094最終snapshotからも変更していない。

| 条件 | 既存6カテゴリ | 新規6カテゴリ | 合計 |
|---|---:|---:|---:|
| 候補名・単位のみ | 4/6 | 3/6 | 7/12 |
| 候補名・単位・定義 | 5/6 | 6/6 | 11/12 |
| 定義のみ、名称/単位なし・順序/ID変更 | 3/6 | 4/6 | 7/12 |

同じ候補名・単位・原文・schema・IDを保って定義だけを加える比較では4件改善・悪化0件、共通合格7件・共通不合格1件。改善は顕微鏡、モニター、カメラ、ルーター。不合格はシュレッダーの最大細断枚数を定格細断枚数へ取り違えるケースだった。初回の新規6カテゴリの成功は、この小さな固定比較の結果であり全商品の未知精度ではない。

| 未確定へ戻すべき条件 | 定義付き | 名称/単位非表示・順序/ID変更 |
|---|---:|---:|
| 正解資料なし（4入力） | 0/4 | 0/4 |
| 複数解釈が残る（4入力） | 0/4 | 0/4 |

全16件でunresolvedへ戻らず候補を選んだ。読取仕様がないときに印刷解像度、吸引仕様がないときにファンの静圧、蓄電仕様がないときに出力電力、除湿能力がないときにタンク容量を選ぶ誤りがあった。実llama.cpp converter/grammarで全52要求のunresolved受理と候補外ID拒否を確認し、104/104成功した。未確定を返せない生成文法の不具合ではない。

名称非表示条件は名称・unit field・順序・IDを同時に変えるため、7/12への低下をそのうち1要因だけの効果と断定しない。候補名だけの条件にも候補語彙は与えているため、無資料の自由生成baselineとは異なる。数値抽出・属性登録・検索器・retrieval recall・商品情報取得・ranking・iGPUでの性能は測っていない。

結論: 正しい候補と定義を供給することの限定改善は確認したが、資料不足時の保留と近い仕様の識別が不足し、事前の進行基準（12/12・12/12・16/16）を満たさない。RAG導入だけで根本解決したとは判断しない。検索器を実装済み・品質改善済みとして扱わず、定義を読む側の比較・追加学習などの検討と、資料不足/曖昧さの評価を [検索専用属性の実データ品質](ISSUES.md#検索専用属性の実データ品質) に残す。

再現資料は /home/products/bonsai-test-logs/20260909-exec095-definition-01 のmanifest.json、request-*.json、trial-*/response-001.body、assessment.json、summary.json、paired-analysis.json、report.md、native-abstention/results.json、log-audit.json。既存ログや判定基準は上書きしていない。検証中・結果確認後に本番promptやnormalizationを変更して合格へ誘導していない。

## EXEC-096: 属性同定の保留をアプリケーションで強制する

- 状態: 完了（数値属性の保留契約。意味推論・商品名品質は別課題）
- 作成・更新: 2026-09-09
- 関連: EXEC-095、[検索専用属性の実データ品質](ISSUES.md#検索専用属性の実データ品質)

### 目的・対象・判断

Bonsaiが常に候補を選んでも、根拠未確認の数値属性を確定条件として実行しない。数値・単位の一致と属性名の同定を別の契約にする。既存adapterの推論候補は確認用に保持するが、原文の引用に属性名と数量の対応が明記されていない場合はblockingとし、typed proposalとregistryの再構築でも同じ根拠を検査する。モデルのconfidence、自己申告のunresolved、候補順位、評価用の正解ラベルには依存しない。

対象はsearch_v2の数値属性同定・その確認/後続処理境界、定義選択の診断境界、回帰テスト。RAG検索器・商品属性の補完・本番サービス・外部委託frontend・Figma・モデル学習・commit/pushは対象外。仕様名を明記して再入力する既存の確認経路を用い、一般的な了承だけでは保留を解除しない。すべての自然言語の曖昧さを判定できるという意味の保証ではなく、未証明の数値属性同定を実行しない契約である。

### 順序と完了基準

1. 未記名数量をもっともらしい属性名で埋めた応答、モデルが保留を返さない応答、再構築/承認での迂回をREDにする。属性名が明記された正常対照も用意する。
2. 原文に基づく決定論的検査をadapter・typed proposal・registryへ実装し、定義選択は一意な明示対応がない限り未確定とする。promptやカテゴリー辞書は追加しない。
3. EXEC-095の保存済み52応答を新規private directoryへ再評価する。原実測の採点・正解・応答は変更しない。保留16件と正例36件の自動確定率を別々に報告する。再生を実Bonsaiの再実行と表現しない。
4. focused/offline全体、ruff、lock、Markdown link、diffを検証し、関連文書を更新する。必要な実Bonsai確認を行う場合は別の凍結batchと全応答ログを使い、条件を通知する。

既存のユーザー差分は保持する。rollbackは本計画の根拠検査変更に限定し、旧キャッシュ・古い確認artifactを新しい検査なしで再利用しない。保存形式は変更しない。旧候補の再構築でも未記名数量をblockingにする。

### 検証記録

実装前のRED/GREEN、テストSHA256、再評価の件数・停止境界、正常入力の進行可否を追記する。

EXEC-096の実装と検証経過:

- 最初のbehavior RED: `uv run --frozen --offline --no-sync pytest tests/test_bonsai_attribute_abstention.py -q --tb=short` は6 failed・4 passed、exit1。推論名がblockingにならず、ambiguitiesを除去した旧intentとname-only実行もreadyへ進んだ。テストSHA256 bd2a0b3bb2cde591218ebd5896ab769abd46a6b87f0081c6bf232561d8fd9222。同一テストで実装後10 passed・exit0（0.53秒）。
- 追加のquery迂回RED: 同コマンドで1 failed・11 passed、exit1。ambiguitiesを消したintentからqueryを生成できた。テストSHA256 f19c83276f1af7274b78c672a5896ad69be079cfae76eebfe9d24cc35c01ec0a。query plannerにも同じ根拠検査を入れ、definition契約と合わせ44 passed・exit0（0.64秒）。
- definition境界の初回RED: `pytest tests/test_definition_abstention.py -q --tb=no` は未実装moduleのため32 failed・exit1、SHA256 b680163754caebc3d5ad9072b5aefc9884476467ce3949c65938bbea95eb46d8。実装後は既存10件と合わせ42 passed。さらに4属性の明記/省略、strict JSON、打ち切りを加え、最終focused52 passed（0.64秒）。
- 初回offline全体は23 failed・2415 passed。旧テストが未記名属性をreadyとしていた14件と旧common presetの1件、数量引用を省いたengine fixture8件を検出した。旧semantic oracle・live judge・期待属性名は変更せず、候補内容の正否と保留によるproposalの不合格を分けてassertした。engine fixtureにはテスト対象の値に対応する明示的な数量引用を付けた。関連226 passed・22 deselected。
- `dynamic_attributes.py` の `numeric_identity_requires_review` は原文引用の名前と数量の対応を検査する。候補自体はadapterで保持してblockingにし、typed proposalでは未確認候補をrequirement/registryへ昇格させない。共通属性や確認済みの別候補の表示は維持する。既存registryの注入、ambiguity削除、query/画像/画像省略からの迂回を拒否する。profile IDをevidence-gated-v2へ更新した。
- 定義の判定はsrc/search_v2/attribute_resolution.py、再生はtools/bonsai_abstention_replay.pyへ分離した。responseの提案IDと実行IDは別で、候補の選択だけでは実行IDを返さない。gold/groupは判定関数へ渡さない。文書の名称/単位/定義が不足する場合、複数の対応、原文に名前がない場合は保留する。
- /home/products/bonsai-test-logs/20260909-exec096-replay-01 に旧52応答をprivate複製し、現行source hash・判定・集計を保存。保留必須16/16、正例の自動確定0/36、不正応答0、追加モデル要求0。正例も保留する制約を明示し、Bonsaiの意味品質向上とは扱わない。
- 実行条件を通知後、localhost Bonsaiへ4 calls・retry0・無認証・API費用0。省略2件はblocking、明記2件はreadyとなり、status4/4、source値4/4を確認した。事前固定した全項目では3/4合格。ポータブル電源の明記入力で商品名が「電源」に短縮され、期待名不一致のため1件不合格。基準を緩めず追加生成しない。合計114.399秒、全HTTP200・完全受信。source/model/server/library/request hash不変、各server停止を確認。全要求・応答・正規化intent・凍結probe.pyは /home/products/bonsai-test-logs/20260909-exec096-live-01 へ保存した。
- 発見事項: 保留を強制しても正しい属性の提案や商品名の抽出精度は上がらない。前者の自動同定と後者の商品名短縮はISSUES/EXEC-094へ残す。外部サービス・ランキング・frontend・モデル変更は行っていない。

最終検証: `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は2448 passed・13 skipped・30 deselected、exit0（48.94秒）。Ruff check/format288 files、lock79 packages、Markdown link、git diff --check成功。最終テストSHA256は test_bonsai_attribute_abstention.py=f19c83276f1af7274b78c672a5896ad69be079cfae76eebfe9d24cc35c01ec0a、test_definition_abstention.py=1042b04d898314d71e57b42017fb5ba205ac12301efae75df8a7c865a072a5dc。検証ログ・集約レポート・権限/hash監査は /home/products/bonsai-test-logs/20260909-exec096-validation-01。数値属性の未確認候補を保留する実装と検証は完了。意味からの自動同定と商品名短縮の問題はISSUESへ残す。


## EXEC-097: 商品候補から属性を発見して確認後に評価する

- 状態: 完了（独立backend実装・offline検証）
- 作成・更新: 2026-09-09
- 関連: EXEC-096、[検索専用属性の実データ品質](ISSUES.md#検索専用属性の実データ品質)

### 目的と対象

一次資料集・カテゴリー別プリセットの事前作成を行わず、原文の未記名数量を保持し、商品候補の観測フィールドから属性候補を得る。利用者が選んだ属性と数量を対応付けた後だけ適合評価する。既存の未確定intentを最終検索へ通す抜け道は作らない。候補取得は別目的の計画と確認に束縛し、元の取得query/product provenanceと後からの属性選択を分けて記録する。

対象はsearch_v2バックエンド、strict商品正規化、観測属性抽出、選択の確認契約、既存typed評価との結合とoffline test。実Bonsai/Outscraper/画像生成の呼び出し、依存取得、資料収集、外部委託frontendの確認・起動・接続、commit/pushは行わない。実providerは注入境界とし、fixtureとmockで全経路を検証する。

### 方針と順序

1. 自然言語をSudachiPyとsource compilerで解析して候補取得計画を作る。既存Bonsai intent reviewは原文digestを検証する互換入口としてだけ受け付ける。原文の数値・単位・比較・強度はsource compilerで固定し、推論された属性名を取得条件へ混ぜない。解析できない関係や欠落条件は取得許可へ読み替えない。
2. owner/session・計画digest・期限・一回性を確認して候補取得を一回行い、既存Outscraper request契約と商品正規化を使う。未確定条件で候補を除外せず、取得結果を適合順位として返さない。
3. 商品の仕様欄から属性名/数値/単位/引用位置を抽出する。Bonsaiによる本文抽出も原文の位置指定だけを受け、自由生成値を採用しない。欠落・切断・曖昧な値を補完しない。カテゴリ辞書や全商品の定義集を追加しない。
4. 名前が明記された原文と観測名が一意に一致する場合だけ自動対応する。未記名数量は一候補だけでも推定確定しない。owner・原文・商品batch・変更不能な提示候補digestに束縛した具体的な選択を受ける。重複/候補外/別単位/古い確認を拒否する。
5. 未確定条件が残る限り順位評価を停止する。確認後、既存型付き数値比較と不明/矛盾の規則を使い、元の取得provenanceを保持した別の評価結果を返す。単なる取得成功を全条件適合や検索完了履歴へ昇格させない。

### 検証と完了条件

TDDで実装前RED、同一テストのGREEN、SHA256を記録する。少なくともスキャナーの同単位・異属性、未知属性、複数条件、強度/上下限、単位不一致、資料不足、商品説明の偽造/切断/曖昧値、出現頻度による誤確定防止、owner/digest/revision/期限/二重取得、未確定の順位禁止、選択後のmatch/unknown/conflict/mismatchを検証する。自然文→SudachiPy query/prompt→取得(mock)→抽出→確認→Bonsai意味評価(mock)と数値評価のoffline統合を行う。旧Bonsai intent reviewからの互換入力も別に検証する。

全体offline、Ruff check/format、lock、Markdown、diffを実行し、関連仕様・現状・作業記録を更新する。raw fixture応答と実行ログはrepository外のprivate directoryに保存し、実利用者データやcredentialを含めない。新規候補経路を外すことでrollbackでき、既存final searchの保留契約・承認・DBは維持する。本番取得率・Bonsai意味品質・未知商品の順位品質は別評価と明記する。

### 実行記録

調査: 既存typed-ranking-v4はintent/query/product batchを同一digestへ束縛するため、後からの選択で取得時のintentや商品provenanceを上書きしない。新経路は取得batchと確認記録を別々に保持し、既存のtyped評価を再利用する。

EXEC-097作業中の利用者による方向修正: 「検索および画像生成クエリはsudachipyで組み立てて、ランキングにbonsaiを使う」案を取り込む。新規経路の検索前Bonsai呼び出しを不要にし、SudachiPy/source compilerと固定テンプレートで取得query/参考画像promptを組み立てる。Bonsaiは検索後の引用範囲提案と意味適合度の補助評価に限定する。必須条件・数値比較・不明/矛盾・最終整列はコードが所有する。日本語からの英訳や省略意味の補完をSudachiPyの能力として扱わない。旧Bonsai intent reviewからの移行入力も原文digestを検証する。


実装と検証経過:

- `src/search_v2/candidate_queries.py`、`candidate_search.py`、`observed_attributes.py`、`candidate_semantics.py` を追加。検索前はSudachiPyと原文compilerだけを使い、検索後の観測属性の確認、Bonsaiの引用付き意味点数、コードの数値・必須条件評価を分離した。原文明示の価格も必須評価する。
- 初回RED: `uv run --frozen --offline --no-sync pytest tests/test_candidate_search.py -q --tb=short` はexit 1、18 failed（新規module未実装）。同じテストファイルの実装後GREENはexit 0、18 passed。両時点のSHA256は `ea6394604f67fa9af408dd16c5c41a0fc1347a260ee941ecd5718375e1f7dbb7`。その後、方向修正に合わせて検索前Bonsaiなし・検索後意味点数と異常応答・未知属性・単位換算・強度・予算などへテストを拡張した。
- 拡張中、数値境界の片側欠落、数字だけの名称、数値範囲の誤読、既存名称aliasとの衝突、明示予算の評価漏れを検出して修正した。数値はDecimalへ統一し、同じ名称の原文定義と確認済み定義がglobal aliasを奪い合わないよう、確認記録から直接対応付ける。
- 最終focused: `uv run --frozen --offline --no-sync pytest tests/test_candidate_search.py tests/test_candidate_semantics.py -q --tb=short --basetemp /home/products/bonsai-test-logs/20260909-exec097-validation-01/fixtures` はexit 0、61 passed。SHA256は `tests/test_candidate_search.py` が `e210411043f40111e71f1f4cb85e3d2c496223c4e77d76702178432a222d883c`、`tests/test_candidate_semantics.py` が `7f12a9a8b517c8055bb01940eea3d736ae79796e88b4d52e88bf6088ec9ed9ac`。
- 標準全体テストの初回は2499 passed / 10 failed / 13 skipped / 30 deselected。ログrunnerが子pytestへumask 0077を引き継ぎ、権限検証fixtureの755/555 directoryを700/500として作成したための失敗。製品コードや既存テストは変更せず、ログfileだけ0600で開き、pytest子processは通常の0022で再実行する。
- 合成provider応答、Bonsai mock要求・応答全文、代表ranking、実行ログは `/home/products/bonsai-test-logs/20260909-exec097-validation-01/` に保存。focused fixtureのJSON 91 filesはすべて0600。実利用者入力、実provider応答、credentialは使用していない。

実装の適用範囲: `candidate-confirmed-observations-v1` は新規のoffline結果型であり、liveフローを置き換えるものではない。in-memory・一回性で、revision編集APIは持たず変更不能な計画/提示digestで確認を束縛する。実providerの承認/費用permit、画像生成・画像確認、API・frontend、履歴DBは別の接続作業となる。Bonsai引用の一致は意味品質の証明ではなく、正しい未知順位・取得率・画像品質は未検証。解析できない複合条件や一部の色表記は明確化待ちとなる。任意の資料を追加してこれらを自動確定する経路は作っていない。

最終全体GREEN: 通常umask 0022で `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` はexit 0、2509 passed / 13 skipped / 30 deselected（47.77秒）。Ruff check、Ruff format（294 files）、`uv lock --check --offline`、Markdown links、`git diff --check` もexit 0。新規backend実装とoffline検証の範囲を完了とする。外部呼び出し0、依存取得0、実provider・API・frontend接続0、commit/pushなし。


## EXEC-098: Bonsaiの視覚条件抽出を候補経路へ接続する

- 状態: 完了（独立backend接続・offline検証）
- 作成・更新: 2026-09-09
- 対象: EXEC-097のcandidate経路、既存VisualConditionDraft / VisualConditionSet、Bonsaiのstrict JSON解析、source compiler、offline回帰。
- 対象外: 実サービス、credential、課金、画像生成/CLIP推論の実行、frontend、履歴DB、commit/push。

利用者の「既存のコードを用いて、資格条件の抽出にも広げよv」は直前の文脈から視覚条件の抽出として実装する。検索語はSudachiPyとコードが組み立て、Bonsaiは原文から視覚条件を提案する役割も持つ。既存のCLIP用VisualConditionSetへ変換し、原文・強度・候補計画digestへ束縛する。モデル出力を数値条件の削除や条件の確定に流用しない。

実装順序: 合成Bonsai応答によるREDを保存→既存source grounding/最大3条件の契約を再利用するadapter→candidate計画の視覚条件と要求/応答digest→SudachiPy queryと画像promptへの接続→既存参考画像/偽画像request builderとのoffline互換→全体gate。一般的な了承で未知の数量名を決めず、候補取得計画の確認と検索後の属性選択を維持する。部分引用で否定や希望を落とさないため、新規の意味的外観句は完全な節で扱い、同定不能・過剰条件・不正応答は保留/拒否する。

完了条件: 原文にある未知外観句がVisualConditionSetとpromptへ渡ること、数量/性能条件が視覚条件へ誤移送されないこと、強度・引用・原文digest・確認計画が保持されること、取得前の確認なしに後続処理が進まないことをfixtureで検証する。全合成応答を新規private logに保存し、RED/GREEN・test SHA256、通常umaskでの全体offline、Ruff、lock、Markdown、diffを記録する。実Bonsaiの抽出精度と画像/CLIP品質は未検証として分離する。


### 実装と検証結果

- `bonsai_visual_conditions.py` を追加し、既存strict JSON parser、source compiler、VisualConditionDraft/Setを再利用した。candidate経路の任意 `visual_extractor` が1 callで提案し、計画へ条件と要求/応答digestを保持する。検索語と画像promptの組立は引き続きコードが担当する。
- 初回RED: `uv run --frozen --offline --no-sync pytest tests/test_candidate_visual_conditions.py -q --tb=short` はexit 1、14 failed（引数とadapter未実装）。同じtest SHA256 `22d5bebbc28ae22a9b89784eecf5275fc7da38059f33fa68fae0b433f534f6ef` で実装後14 passed、exit 0。初回GREENでは証拠保存のためprivate `--basetemp` を付加した。
- 追加のOR関係テストは1 failed / 20 passedでRED。視覚句のmaskによって未対応ORが消える問題を、既存 `_ALTERNATIVE` の再利用で拒否した。最終の新規テストは21件。最終SHA256は `22ac9c9e34e52a33eb5e5d5aa0d58db5f8f55de09e7b9197ef0e0bdfdbfa9c2f`。
- focused: 新規視覚条件21件、candidate検索/意味評価、既存counterfactual request・参考画像フローを合わせて94 passed、4.91秒、exit 0。条件2件を既存builderへ渡し、参考1枚+偽画像2枚のdescriptorになることを確認した。モデル応答/条件の捏造・部分引用・強度違い・性能条件・数値・重複・超過・異なる原文・保留・provider失敗・確認digestを検証した。
- 標準全体: `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` は2530 passed / 13 skipped / 30 deselected、84.24秒、exit 0。子processのumaskは通常0022とし、ログだけ0600で保存した。
- 結果に `visual_evaluation_status=pending/not_requested` を追加し、typed数値評価のconfirmedを視覚条件まで含む完了へ読み替えない。旧candidate結果にはこのfieldがないため新しいstrict結果型へ無検証で流用しない。保存済み実検索cache/履歴、既存liveフローは未変更で、移行対象の稼働DBはない。
- ログは `/home/products/bonsai-test-logs/20260909-exec098-validation-01/`。最終focusedの合成要求/応答・代表結果JSON 135 filesはすべて0600。RED/GREEN、最終test hash、実行command、全体ログを保持した。

完了範囲は既存契約を使った視覚条件抽出の接続とoffline検証。完全な非数値節だけを自動候補化する制限があり、混在文の分解・未知語の視覚/非視覚分類・抽出漏れ防止の意味品質は実modelで未検証である。実provider、画像生成、CLIP runtime、画像承認やranking画像点数、API、委託frontend、履歴DBへは接続していない。


## EXEC-099: 新旧検索フローのoffline連続検証

- 状態: 完了（検証。新経路全体の未接続・復元未対応を確認）
- 作成・更新: 2026-09-09
- 対象: EXEC-097/098のcandidate経路の自然文から視覚抽出・query/prompt・商品取得・属性確認・Bonsai意味評価・結果出力までと、既存画像承認/偽画像/CLIP/履歴のofflineフロー。
- 対象外: product codeの新規接続、実Bonsai/画像provider/CLIP runtime/Outscraper、frontend、credential、課金、依存取得、commit/push。

依頼は一連のフローのオフライン検証。調査により、新candidate経路は画像要求descriptorとtyped/Bonsai rankingまでで、画像承認・CLIP点数統合・履歴DBは既存の別経路にあることを確認した。二つの独立した経路の成功を一つの新フローの完走へ読み替えない。新経路は明示数量名/未記名数量の2シナリオを一続きで検証し、意味点数の逆転に対して数値/予算条件の優先と視覚pendingを確認する。既存経路は既存test関数を再利用して参考1枚→承認→偽画像→CLIP固定embedding→ranking→SQLite履歴再読込を別に検証する。

テストは現行実装のcharacterizationであり、振舞い変更のTDDではない。新規test hashと初回実行結果を保存し、必要な不具合修正が発生した場合はRED/GREENへ移行する。注入providerの合成要求・応答と結果を新規repository外private directoryに記録し、fixture credentialやheaderは保存しない。focused、全体offline、Ruff、lock、Markdown、diffを確認し、未接続区間を残作業に記録する。


### 実行結果と判定

`tests/test_candidate_offline_flow.py` を追加した。初回は新経路2ケースがJSONからのdomain復元で失敗し、既存フロー1ケースが成功した（2 failed / 1 passed、9.53秒、exit 1）。初回test SHA256は `e6974a367b041bb2c8015368eb9fad7ea3f5b8a300e768f1f6e8f5b51e72342d`。`DecimalTarget` は有限Decimal実体を要求するため、JSONに書き出した数量下限と予算上限の文字列を汎用model_validate_jsonで戻せなかった。

製品コードは変更せず、成功する出力/readbackと未対応のdomain復元を別テストに分けた。復元の期待は変更せず、2件をstrict xfail（ValidationErrorのみ）で保持する。解決後はxfailを解除する必要があり、現状の全体フロー合格を意味しない。最終test SHA256は `792b47f8c19bdaa537118eca79d7839e03a5ab5696cd51f48385e4694a8796c3`。

- 新規連続検証: 新candidateの2ケースと既存フロー1ケースが成功、candidate domain復元2ケースがxfail。
- 新candidate: 自然文→Bonsai視覚fixture→Sudachi query/prompt→参考/偽画像request descriptor→計画確認→商品fixture取得→具体的属性確認→Bonsai意味fixture/数値/予算ranking→JSON出力まで成功。未記名数量の未選択と未確認計画、二重取得/二重rankingを拒否。点数0.8と0.1の条件適合商品を、0.9の不明商品と1.0の不一致商品より優先した。
- 新candidateの画像はdescriptorのみ。CLIP未評価はpending。履歴DBの保存/再読込は未接続で、JSON出力を履歴成功として扱わない。
- 既存フロー: 既存のstaged-generation testを再利用し、Bonsai fixture1応答、参考/偽画像fixture2応答、商品fixture1応答、固定CLIP embedding2応答、SQLite履歴detail1応答と画像2応答を記録した。参考了承前に偽画像を出さない既存制御と、job完了・履歴再読込・画像一致を検証した。新candidateからこの経路への接続はない。
- focused command: `uv run --frozen --offline --no-sync pytest tests/test_candidate_offline_flow.py tests/test_candidate_visual_conditions.py tests/test_candidate_search.py tests/test_candidate_semantics.py tests/test_search_v2_reference_image_flow.py tests/test_search_v2_provisional_production_flow.py -q --tb=short -rx --basetemp /home/products/bonsai-test-logs/20260909-exec099-validation-01/fixtures`。94 passed / 2 xfailed、10.48秒、exit 0。
- 全体command: `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short`。2533 passed / 13 skipped / 30 deselected / 2 xfailed、78.44秒、exit 0。Ruff check/format（297 files）、lock、Markdown、diffも確認する。
- ログ: `/home/products/bonsai-test-logs/20260909-exec099-validation-01/`。初回失敗をinitial.txt/initial.jsonへ、最終の全要求・応答・結果をfixtures/へ保存。最終focusedのJSON 198 filesはすべて0600。header/credentialを記録しない。実外部provider/CLIP runtime呼出し0、frontend未使用。

判定: 接続済み区間のオフライン検証は成功したが、利用者が求める新経路全体の画像承認・CLIP・履歴までの完走は未達。[接続と復元の課題](ISSUES.md#candidate経路の画像履歴接続と結果復元) を次の実装対象とする。本Planの完了は検証作業の完了であり、新フローの完成ではない。


## EXEC-100: Candidate結果JSONのDecimal復元

- 状態: 完了（結果JSON復元・offline検証）
- 作成・更新: 2026-09-09
- 対象: CandidateRankingのJSON読込、EXEC-099の復元2ケース、数値表現/型/範囲の回帰。
- 対象外: 共通DecimalTarget/DecimalObservedValueの型制約緩和、画像/CLIP/履歴の接続、実サービス、credential、課金、frontend、commit/push。

`model_dump_json()` はDecimalを文字列へ書き出すが、共通domainはDecimal実体だけを受け付けるため復元できなかった。CandidateRankingのJSON入力境界に限り、requirementsのdecimal型targetのminimum/maximumを有限Decimalへ復元してから、既存DecimalTargetを厳密に検証する。Python入力と非decimal値の型制約は緩めない。requirementsとenum/text_setのJSON配列だけは通常のJSON読込と同じtupleへ戻し、その他のfieldには前処理を加えない。既存出力形式・profile・digestは維持し、新しい承認や実行stateの復元機能は加えない。

TDD: 既存のxfail2件を通常テストへ戻してREDを保存→JSON境界の実装→同じtest SHA256でGREEN→小数/指数/片側null/非数値型/非有限/範囲/精度超過の回帰→全体offlineとstatic gate。既存ログを上書きせず、新規private directoryへ合成応答とRED/GREEN・最終結果を保存する。履歴DB接続の未完了は復元問題と分けて残す。


### 実装と検証経過

`CandidateRanking.restore_json_targets` を追加。Pydanticの入力modeがjsonのときだけ、requirementsのdecimal targetの両境界を明示的に復元し、DecimalTarget.model_validateで共通制約を再検証する。前処理後はPython containerとして検証されるため、requirementsとenum/text_setのvaluesはtupleへ戻す。全モデルのstrict=False化や共通DecimalTargetの文字列許可は行っていない。

- RED: `uv run --frozen --offline --no-sync pytest tests/test_candidate_offline_flow.py -q --tb=short --basetemp /home/products/bonsai-test-logs/20260909-exec100-validation-01/red-fixtures` は2 failed / 3 passed、3.45秒、exit 1。xfail解除後の復元2ケースがDecimal文字列で失敗した。
- 中間実装: Decimalを復元した後のlistがPythonのstrict tuple検証で拒否された。tupleへ戻し、色などが混在するJSON配列も既存のtuple契約へ復元した。中間失敗ログも保存し、期待値は変更していない。
- GREEN: 同じテストとSHA256 `5a58c0ea1ec21f1ba4012eeb6a871c2d7080724c5390ef8d08a7486a4d1ea225` で5 passed、2.55秒、exit 0（保存先だけgreen-final-fixturesへ変更）。以前の復元xfail2件は通常の成功テストになった。
- `tests/test_candidate_result_json.py` に36件追加。str/bytes/bytearray、指数表記、小数点以下6桁、負数、片側null、空要求、enum/booleanとの混在、完全な結果と出力JSON/digest/pendingの保持、NaN/Infinity/空白/underscore/範囲/精度超過/誤型/未知fieldの拒否、Python入力と共通型の厳格性を検証した。SHA256は `b5a4029316f1ff91e927f47c4c7118f2331976353242d1981b90ee1d186ecc16`。
- focused: candidate結果JSON・連続フロー・検索・視覚抽出・意味評価・共通typed requirementsの6 filesを実行し、143 passed、4.20秒、exit 0。

出力形式とprofileは変更していないため、既存candidate JSONの数値文字列を読み直せる。結果型のJSON往復の修正であり、実行state/承認tokenの再生、画像/CLIP/履歴DB接続は追加していない。EXEC-099の失敗ログと過去の判断は履歴として維持する。

最終全体offlineは `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short` で2571 passed / 13 skipped / 30 deselected、80.17秒、exit 0。xfailは残っていない。RED・中間失敗・GREEN・合成要求/応答・結果は `/home/products/bonsai-test-logs/20260909-exec100-validation-01/` に保存した。外部呼出し・依存取得・frontend接続は行っていない。

最終static gate: Ruff check・format（298 files）、offline lock、Markdown links、git diff --checkはすべてexit 0。


## EXEC-101: Candidate経路の画像承認CLIP履歴接続

- 状態: 完了（画像付きcandidateのoffline接続）
- 作成・更新: 2026-09-10
- 目的: Sudachi query・Bonsai視覚提案から、参考1枚→了承→条件別偽画像→最終承認→候補取得→属性選択→Bonsai/数値/CLIP評価→履歴保存・再読込までを独立backendで実行する。
- 対象: candidate専用の状態管理、既存画像executor/利用量ledger/永続承認の再利用、CLIP evaluator接続、結果と履歴投影、offline回帰。
- 対象外: 実provider実行、実CLIP runtime、frontend/API、既存live入口の切替、commit/push。

既存IntentReviewやtyped-ranking-v4を捏造せず、CandidateSearchを所有する新しいflowで承認順序を管理する。原文・計画・owner・期限・画像digestを束縛し、初回1枚と了承後N枚の利用量を既存ledgerに記録する。画像再生成は取得前だけ、旧承認を失効させ、実行中や二重実行を拒否する。条件名未記載の数量は候補取得後の具体的属性選択まで保留する。

CLIPは既存counterfactual evaluatorを使い、CandidateRankingのtyped必須条件を最優先した上でBonsai意味点数80%・画像点数20%を新profileとして合成する。画像missing/unknown時は意味点数のみ、画像側状態を保持する。新結果を既存schema5履歴の表示型へ明示投影し、新ranking profileと品質未測定のnullを組として許可する。旧profileの0.875を新経路の実測精度として流用しない。SQLiteの表は変更せず、新経路は専用DB利用を推奨し、旧writer/readerへ新profileを無検証で戻さない。

実装順序: 新経路を通す正常/未承認/不一致/再生成/失敗/保留のテストを追加してRED保存→既存executorと承認repositoryの組立→数値と意味を保持した画像評価/履歴投影→同じテストでGREEN→境界回帰→標準全体offline・Ruff・lock・Markdown・diff。全合成応答とRED/GREEN、command、hashはrepository外private directoryへ保存する。

完了条件: 新経路そのものから明記属性/要選択の2入力が履歴と画像再読込まで到達し、画像点数が数値不適合を覆さず、拒否/期限/owner/digest/二重使用/失敗は保留または停止する。実品質の保証とは分けて記録する。rollbackは新flow利用を停止して従来のCandidateSearchへ戻す。既存データを移行・削除しない。


### 実装と検証結果

- `candidate_flow.py` と `candidate_completion.py` を追加。CandidateSearchを所有するflowで、画像段階の利用量・承認・再生成・一回性、候補取得/属性選択、CLIP evaluatorと専用ranking、履歴投影を接続した。既存CandidatePlan/Rankingを旧IntentReviewやTypedRankedProductBatchへ偽装せず、共通型を緩和していない。
- 画像付き結果はsourceの数値/意味評価を保持し、専用profileで画像評価を合成する。履歴schema5に新ranking profileと未測定nullの組を追加した。旧profileとの組合せ誤りを拒否し、旧SQLite table・digest形式・旧行の互換性を維持した。
- 初回RED: `uv run --frozen --offline --no-sync pytest tests/test_candidate_connected_flow.py -q --tb=short`（private basetemp付与）は13 failed、0.98秒。新moduleなし。test SHA256 `88303ef93be56256395b1fd6b290c971ade33c86f91bcc7e375a0aa7e1f61563`。
- 初回実装後は3 failed / 10 passed。ledger.snapshotの順序はreservation ID順であり、同時刻fixtureを実行順と誤って仮定していたため、各予約のoperation/calls/statusを全件比較するようテストを修正した。製品側のledger並びや予約を変更していない。
- 履歴一覧の未測定nullを含めたREDは4 failed / 13 passed、4.46秒。ProvisionalHistoryListItemがnullを拒否していた。実装を修正し、同じtest SHA256 `ae9b93506188616958a18d402dc667050482470d977b4ebcf23d9aeee743ce76` で17 passed、4.01秒となった。
- 最終新規28件。明記属性/要選択×CLIP同点/異なる点数の4ケースが、原文から画像承認・商品取得・属性選択・意味/数量/画像ranking・履歴詳細/一覧/画像の再読込まで成功。異なる点数では数値適合D/B→不明C→不一致Aを保持し、画像点数0.4/0/0.6/1を保存。同点時はunknown/nullを保持した。4ケースのDB integrity_check=ok、履歴各1件。
- 最大3条件の生成数1+N、未承認、owner/digest/期限、同時承認、再生成による失効と最大3attempt、未選択数量、生成/CLIP失敗、保存commit後の応答喪失と保存のみの再試行、品質profileの誤組合せ拒否を検証した。
- 関連7 filesは100 passed、19.04秒。標準全体offlineは2601 passed / 13 skipped / 30 deselected、96.27秒、exit 0。Ruff check/format（301 files）、offline lock、Markdown links、git diff --checkも成功。
- 証拠: `/home/products/bonsai-test-logs/20260910-exec101-validation-01/` にRED/中間/最終、全合成応答・ranking・履歴・SQLite、実行command、test hash、DB監査を保存。実provider/実CLIP/外部送信/依存取得0。commit/pushなし。

完了範囲は視覚条件1〜3件の新candidateから画像付き履歴までの独立backend接続とoffline検証。実Bonsai/画像/CLIP品質、既存live入口/API/委託frontendの切替、画像省略/視覚条件なしの履歴経路、process再起動後の途中状態復旧は未実装・未検証として残す。13 skipは実CLIP opt-inなし、30件はlive_api除外。

## EXEC-102: Candidate経路の実画像付き実行

- 状態: 進行中
- 作成・更新: 2026-09-10
- 目的: EXEC-101の新candidate経路で実Bonsai、参考画像1枚、参考了承後の偽画像1枚、商品取得、実CLIP、ランキング、SQLite履歴再読込を順に確認する。
- 対象: backend専用の実テスト入口とそのoffline接続確認。関連仕様は[BACKEND.md](BACKEND.md)、前提は[EXEC-101](#exec-101-candidate経路の画像承認clip履歴接続)。
- 対象外: 委託frontend、API公開、4視点生成、3D生成、provider変更、commit/push。

既存live入口は旧IntentReviewを使用するため流用して成功扱いにしない。CandidateSearchFlowを直接組み立て、既存HTTP transport・画像検証・process分離CLIP・SQLiteを使う専用runnerを作る。固定合成入力は「マグカップ。丸みのある形。3000円以下。」、視覚1条件・query1本・取得24件まで。条件数や要求が上限を超えたら生成前に停止する。Bonsai最大2推論、Cloudflare最大2要求、Outscraper task1回・poll50回、商品画像24枚、CLIP7batch、retry0。Bonsaiはloopback・1worker・900秒の所有process期限、flow自体も15分有効である。

実装順序はrunner境界のofflineテスト→専用入口実装→関連回帰・標準gate→具体的な送信先/内容/件数/credential/費用を示して実行承認→実行時の画像2段階確認→rankingと履歴/画像再読込の照合。生成画像、表示用結果、応答のstatus/長さ/hashなどの診断をrepository外の新private directoryに保存する。認証header・生例外・不要なprovider本文は保存しない。合成fixtureの応答はoffline試験ログに保存する。

完了条件は全実段階の成功と保存結果の再読込一致。失敗時は最後の成功段階と実呼出し数を記録し、追加外部呼出しを行わない。単一入力で順位品質全般を保証しない。rollbackは専用入口の利用停止だけで、既存flow・保存データを変更しない。

進捗: 修正後の再実行で視覚条件1件の抽出、参考画像・偽画像、人間確認、商品検索応答まで到達した。商品評価用BonsaiのHTTP 200後にranking_clip_historyで停止し、CLIP・ranking・履歴再読込は未完了。

### 実行準備と条件提示

新入口: `tools/candidate_search_live_e2e.py`。offlineテストは `tests/test_candidate_search_live_e2e.py`。既存Settingsが返すSecretStrは内部でのみ取り出し、HTTP transportへ渡す。確認後の画像差替えを拒否する既存保存file検証を両段階で再利用した。Bonsai/画像/Outscraper各HTTP応答はstatus・長さ・hashを記録し、Cloudflareの失敗は既存の限定されたdiagnosticのみ保存する。

ローカル準備確認: model SHA256 `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54`、server binary SHA256 `71b0c2554c375071855547f5da7ef2fc5c34766f6fcd6fab194ce93a18a59e0a`、固定CLIP assets検証成功、port18080 bind可能。実Bonsai推論や外部provider疎通の確認ではない。証拠は `/home/products/bonsai-test-logs/20260910-exec102-preparation/` に保存した。

実行承認時に示す内容:

- ローカルBonsai `http://127.0.0.1:18080/v1/chat/completions`、Bonsai-8B.gguf、合成入力からの視覚抽出1回＋取得した商品本文の意味評価1回。起動health確認は別。credentialなし・API費用0。
- Cloudflare `https://api.cloudflare.com/client/v4/accounts/<account-id>/ai/run/@cf/black-forest-labs/flux-2-klein-4b` に固定合成入力由来のpromptを送り512×512参考1枚、その了承後に参考画像を入力して偽画像1枚。既存Cloudflare API token使用。4視点/3Dは生成しない。
- Outscraper `https://api.outscraper.cloud/amazon-products` にマグカップのquery1本、amazon.co.jp/ja、固定合成郵便番号100-0001、limit24を送る。既存Outscraper API key使用。task1回と最大50poll、各HTTP30秒。画像セットの了承前には送信しない。
- 許可host `m.media-amazon.com` の商品画像を最大24 GET。既存proxyのDNS/TLS/画像検証を通し、固定ローカルCLIPを最大7batch実行する。credentialなし。全体900秒・retry0。
- 2026-09-10に確認した[Cloudflare料金](https://developers.cloudflare.com/workers-ai/models/flux-2-klein-4b/)は512tileにつき出力0.000287 USD、入力0.000059 USD。参考+偽画像は出力2tile・入力1tileとして0.000633 USD。[Outscraper料金](https://outscraper.com/amazon-scraper/)は500件超で1000件2 USD、24件で0.048 USD。無料枠を適用しない概算は合計0.048633 USD（税別）。金額の自動停止ではなく固定要求数で範囲を制限する。

承認済み実行コマンド:

```sh
uv run --frozen --offline --no-sync python -m tools.candidate_search_live_e2e --run-live-api --output-dir /home/products/bonsai-test-logs/20260910-exec102-live-01 --asset-root /home/products/Git_Products/amazon-explorer/models/clip-vit-base-patch32-12b36594 --server-bin /home/llama.cpp/build/bin/llama-server --model-path /home/products/models/Bonsai-8B.gguf
```

実行はPTYで行い、表示されたPNGを人間へ提示する。参考確認は「この参考画像を了承して偽画像を生成する」、最終画像/query確認は「生成画像と検索クエリを確認し商品検索を承認する」を、人間がその段階を了承した後にだけ入力する。過去の画像了承を今回の画像へ流用しない。15分の期限内に確認が得られなかった場合も自動再生成しない。

### 準備の検証結果と再開位置

- 新規7件成功。改変PNG検出は同一test SHAで2 failed / 5 passedから7 passed。HTTP応答metadata保存は1 failed / 6 passedから7 passed。最初のmodule不存在は入口未実装の確認であり、振る舞いのRED証拠とは区別した。
- 関連5 files: 113 passed / 1 deselected、9.97秒。標準全体offline: 2608 passed / 13 skipped / 30 deselected、84.85秒。13 skipは実CLIP opt-inなし、30件はlive_api除外。
- Ruff check/format（303 files）、offline lock、Markdown links、git diff --check成功。モデルとCLIP assetsのローカル検査成功。
- 全command・exit・test hash・RED/GREEN・preflightは上記private preparation directoryに保存した。実サービス呼出し0、実CLIP推論0。

準備完了時点では実行承認待ちだった。承認後の実測結果は以下に記録する。全実段階は未完了のため、EXEC-102全体を完了扱いにしない。

### 承認後の起動

利用者が提示条件に対して「開始せよ」と指示した。初回起動はBonsaiLiveE2EConfigの必須port引数欠落により入口でexit1となり、出力directory作成前・provider呼出し0で停止した。CLI経由のoffline回帰を追加し1 failed / 7 passedを確認、config.bonsai_portを明示して関連18 passed / 1 deselected、Ruff成功。同じ承認範囲で修正後の入口を起動した。外部要求の再試行は行っていない。今回の修正はCLI組立のみで、provider設定・件数・flow契約は変更していない。

### 実行結果: 視覚条件処理で停止

- 修正後runnerはexit1、failure_stage=`visual_conditions`。ローカルBonsaiへ1推論要求を送り、HTTP200・1101 bytesの応答を受信した。応答SHA256 `1ca9a4d26e31873616ab0268587008cbf522dccdbbf7c420f383f5947f93a3d7`。
- Cloudflare0 calls、Outscraper0 tasks/0 polls、商品画像0、CLIP0 batches、retry0。参考画像・ランキング・検索履歴は生成されていない。外部API課金を伴う要求0。
- 応答ログはstatus/byte数/hashのみ。生応答を保持していないため、JSON不備、要確認/空条件、原文照合、その他constructor検証のどの分岐で停止したかは今回の記録から断定できない。Bonsaiの意味的誤答を確認したとは表現しない。追加の実送信は行っていない。
- 履歴DB integrity_check=ok、provisional_history/画像tableは各0件。port18080のLISTENなし、所有llama-server processなしを確認。bind不可の一時状態だけをserver残存と解釈していない。
- 証拠: `/home/products/bonsai-test-logs/20260910-exec102-live-01/` のsummary.json、bonsai-response-1.json、audit.json、空の履歴DB。CLI修正のRED/GREENとhashはpreparation directory。

停止時点の残作業: 応答本文を記録しなくても拒否分岐を特定できる構造化diagnosticを用意し、offlineで確認する。その後、実行条件を提示して次の実検証へ進む。今回の承認はretry0であり、停止後の新たな推論や画像生成を自動再実行しない。画像生成・商品取得・CLIP・ranking・履歴までの実完走は未達。

### EXEC-102継続: 応答本文を残さない停止診断

2026-09-10、利用者の「診断を追加せよ」に基づき、Bonsai視覚応答の構文/外側構造/生成終了/要確認/条件数/条件型/原文・属性束縛/節の範囲/条件の強さ、空条件による画像経路の拒否を固定codeで識別する。CandidateSearchで例外が握り直されても型付きdiagnosticを保持し、実runnerのsummaryへ出力する。モデルの応答文字列・任意の例外文・入力・credentialを診断へ転記しない。未知例外は固定unexpected codeにする。成功/保留/拒否の判定、prompt、上限、providerは変えない。

実装前に各拒否分岐とログ非漏洩のoffline REDを保存→診断型/各境界/runnerへ最小接続→同じテストのGREEN→関連/標準gate。外部実行は対象外。過去の応答本文は保存されていないため、今回の変更で過去の拒否理由を復元したとは扱わない。rollbackは新diagnostic表示の利用停止であり、既存のstrict拒否を緩めない。完了条件は分岐がsummaryまで保持され、任意の応答/例外文字列がログへ出ず、正常ケースの後段接続が維持されること。

診断の実装は完了。strictなschema1.0/codeの診断型を追加し、parser→CandidateSearch→画像必須flow→実runnerのsummaryへ保持する。HTTP/request/query/runner上限と未知例外も固定codeに分類する。condition_bindingは共通builderの検証境界であり、内部の全拒否理由の分解や過去応答の復元までは行わない。テスト初回は50件中49 failed / 1 passed、空条件fixtureの修正と6ケース追加を経て関連151 passed。test hash変更の理由はWORKLOG145に記録し、同一hashの全件GREENやattestedなレビューとは主張しない。

最終検証: 新規56件を含む関連151 passed、7.58秒。標準全体offline2665 passed / 13 skipped / 30 deselected、89.17秒。Ruff check/format305 files、offline lock、Markdown links、git diff --check成功。実サービス0 calls。RED・最終command/exit・test hash・変更file hash・全体logは `/home/products/bonsai-test-logs/20260910-exec102-diagnostics/`。診断追加の完了条件を満たした。EXEC-102全体の残作業は診断付きの実再検証から画像/商品/CLIP/履歴までの完走であり、未完了のまま保持する。

### 診断付き実Bonsai再検証

2026-09-10、診断追加後の「テストを実行し、診断せよ」に基づき、前回と同じ合成入力をローカルBonsaiへ1回だけ送る。接続先127.0.0.1:18080/v1/chat/completions、Bonsai-8B.gguf、最大900秒・retry0、認証/外部課金なし。画像生成・Outscraperはこの原因診断では実行しない。現行のbuild_visual_request、HTTP transport、parse_visual_responseとCandidateSearchを用い、応答を一時メモリ上に保持して既存検証へ再投入する。追加モデル要求は行わない。保存物は固定diagnostic code、応答status/長さ/hash、原文/属性/型の照合結果のboolean・件数のみ。生応答・生例外・入力値・credentialは保存しない。

診断付き再検証の結果: 実Bonsai1 call、HTTP200、1097 bytes、19.965秒、retry0。新diagnosticはclause_scope。finish_reasonはstop、payloadはready、条件数3。各条件は原文内の完全な節で、draft・個別束縛・既存視覚属性登録の検証を通過した。parse_visual_responseは3件全体の一意性検証を通してからclause_scopeで停止している。入力は3節だけなので、商品種別「マグカップ」、外観「丸みのある形」、価格「3000円以下」をすべて視覚条件として選択したことが分かる。価格節の数字が非数量節の検証に違反する。

要求schemaをoffline確認すると、source_phraseのenumに全3節をそのまま渡しており、価格も生成可能な候補になっていた。指示文では商品種別だけの節・数量・価格を対象外としているが、モデルは守らなかった。通信/JSON構文/未登録属性/原文の捏造ではなく、非視覚条件の誤選択と生成側の候補制約不足である。後段の拒否は仕様どおり機能した。

追加model callなしの合成再生では、3節すべてを選ぶ応答は同じclause_scope、外観節だけを選ぶ応答は1条件として受理された。実応答本文の再生とは区別する。Cloudflare/Outscraper/CLIP実行0、port18080非LISTEN、API費用0。証拠は `/home/products/bonsai-test-logs/20260910-exec102-bonsai-diagnostic-01/` のsummary.json、diagnosis.json、HTTP metadata、実行用probeとmanifest。

今回の実テストと診断は完了。次の修正対象は、既存の数量/価格/商品種別の抽出と視覚候補の契約を接続し、非視覚条件を生成候補に入れない要求設計。今回の診断では本体コードやpromptを変更していない。実画像付き全フローの完走は引き続き未達。

### EXEC-102継続: 視覚候補の生成契約を修正

2026-09-10の「修正しろ」に基づく。対象はbonsai_visual_conditions.pyの生成候補と受信検証、および回帰テスト。既存のSudachi正規化・節分割・source facts・属性registry・名詞句判定を再利用し、数字を含む節、既知の非視覚条件、OR関係、商品名として確保する名詞句を視覚候補から除く。商品辞書やカテゴリ別プリセットは追加しない。商品名は既存の節形式入力から、条件として抽出されておらず希望/除外指定のない一意な名詞句を確保する。候補名詞句が複数ある場合はproduct_scopeとして保留し、先頭の句を商品と推測しない。名詞句の意味が常に商品であるという保証ではなく、残余の構文は既存query構築・人間確認で検証する。

同じ候補集合をJSON schemaのenum、Bonsaiへ示す選択肢、受信時の検証に使用する。候補がなければ空配列だけを許すschema、候補1件なら最大1件にする。原文・否定・希望/除外は保持し、価格は元のsourceから検索条件へ残す。旧価格条件混入の合成応答と正常外観応答、別カテゴリ/順序/全角数字/対応可否/候補なしをRED→GREENで検証し、関連・全体offline gateを行う。実API呼出し・画像生成・provider変更・commit/pushは対象外。完了条件は候補制約が生成と受信で一致し、商品queryと価格条件が保持されること。rollback時も受信側の非視覚条件拒否を緩めない。

生成契約の修正とoffline検証は完了。_visual_clausesをschema enum・提示選択肢・受信検証に共用し、今回の入力は外観1件だけを選べる。商品queryと価格3000円を保持する。商品名詞句の複数候補はproduct_scopeで保留するため、「机。木目調。」などの曖昧な短い名詞列も確認が必要になる。

新規18件は同一test hashで16 failed / 2 passedから18 passedへ改善。関連169 passed（5.39秒）、全体offline2683 passed / 13 skipped / 30 deselected（62.55秒）。Ruff306 files、offline lock、Markdown links、git diff --check成功。Python schema conversion＋C++ GBNF validatorのローカル10ケースでも期待どおり許可/拒否を確認。Python converterがenumをUnicodeエスケープ化する点を踏まえ、合成JSONを同表現で比較した。これは本番C++ converter/実モデル推論の測定ではない。

証拠は `/home/products/bonsai-test-logs/20260910-exec102-visual-scope-fix/`。修正前source、RED/GREENのcommand/exit/hash、最終file hash、schema・文法・合成応答・validator出力、全体gateログを保存した。実API/model call0。今回の修正は完了し、EXEC-102全体の残作業は新契約での実Bonsai再検証と画像/商品/CLIP/履歴までの実完走。

### EXEC-102継続: 修正後の全体実テスト再開

2026-09-10、利用者の「全体テストを再開しろ」により、上記と同じ入力・送信先・credential・費用見積り・呼出し上限で再開する。修正時に検証した4 fileのSHA256一致、port18080非LISTEN、新規出力先の未作成を確認した。出力先は `/home/products/bonsai-test-logs/20260910-exec102-live-02/`。参考画像と最終画像/queryの確認は今回生成した画像に対して実施し、過去の了承を流用しない。全体900秒、retry0を維持する。

途中結果: 実Bonsai 1 callはHTTP 200、816 bytes。視覚条件は「丸みのある形」の1件だけとなり、商品名・価格条件を選んで停止する問題は今回の実応答で再発しなかった。queryはマグカップ、pending条件0。Cloudflareで512×512の参考画像1枚を生成・検証し、人間の参考画像確認待ちへ到達した。偽画像・商品取得・CLIP・ranking・履歴照合は未実行。plan期限は2026-09-10 03:08:57 JST、全体実行期限も適用する。

参考画像への「はい」を受け、同じ実行を継続した。Cloudflare 2 call目はHTTP 200、512×512の偽画像を保存・検証した。目視では参考の滑らかな側面に対して偽画像は角のある側面となっている。現在は2枚とquery「マグカップ」の最終確認待ち。商品取得・CLIP・ranking・履歴照合はまだ実行していない。

最終画像/queryへの「はい」を受けて商品検索を継続した。Outscraper task1回・poll7回、最終HTTP 200・73,548 bytesを受信。商品評価用Bonsaiの2回目もHTTP 200・8,191 bytesを返したが、ranking_clip_history / unexpectedでexit1となった。商品画像要求0、CLIP0、ranking出力なし、履歴0件・履歴画像0件。retry0、全体期限前の2026-09-10 03:06:16 JSTに終了した。最後の商品応答からBonsai応答metadataまで451.389秒であり、純粋な推論時間とは区別する。

生応答は保存していない。CandidateSearchFlow.completeが内部例外を固定ValueErrorにまとめ、意味評価parserも詳細分岐を保持しないため、現存metadataだけでは意味評価応答の契約違反・後続検証のどちらかを特定できない。8,191 bytesという長さだけで打ち切りとも断定しない。次は商品評価段階の固定code診断を追加し、失敗分岐を保持する必要がある。

summary.json、HTTP metadata、生成PNG2枚、audit.jsonを上記live-02 directoryに保存。directory0700、全file0600、履歴DB integrity_check=ok、所有Bonsai process終了・port18080非LISTENを確認した。要求数は承認上限内、実課金額は未照会。追加live実行なし。文書リンク・anchor・fenceとgit diff --check成功。今回の作業は実テストと記録のみであり、既存の全体offline2683件の成功を今回の実完走として扱わない。

### EXEC-102継続: 商品評価の停止診断

2026-09-10「診断せよ」に基づく作業。状態: 進行中。保存済みmetadataと実行経路を調べ、意味評価parser、CandidateSearch.rank、CandidateSearchFlow.completeの3層で詳細を失うことを確認した。対象はこれらの固定code診断とsummaryへの伝播、合成応答による検証。順位計算・受理条件・prompt・provider・保存形式の変更、追加live送信は対象外。

実装前に終了理由、件数、商品ID、score、引用field/owner/範囲/重複の拒否分岐と、runnerまでの伝播をテストで固定する。RED→実装→GREEN→関連回帰・全体offline・標準gateの順に行う。生応答・例外文字列を保存せず、既存diagnosticのallowlistを拡張する。履歴保存の再試行状態も維持する。完了条件は拒否を緩和せずに固定codeを最終summaryへ記録できること。rollbackは診断変更の取り消しで、実テスト結果を上書きしない。前回の本文は未保存のため、診断改善が過去応答の原因特定を意味しない。

診断追加は完了。CandidateEvaluationErrorを追加し、parserの18種類の拒否、rankの条件準備/要求/評価/結果契約、completeの画像評価/履歴投影、履歴saveを区別した。rankとcompleteの両層で型付き診断を維持し、runner既存の保存直前再検証に接続した。非型付き例外は処理段階だけを記録する。既存の拒否・点数計算・failed/history_pendingの状態を維持する。

新規33件は32 failed / 1 passedから同じtest SHAで33 passed。REDのうち31件は期待した診断欠落で失敗、1件は新例外class未定義のimport失敗であり振る舞いのRED根拠に含めない。その後のRuff整形でtest SHAが変わったことも記録した。整形後を含む関連222 passed、全体offline2716 passed / 13 skipped / 30 deselected（63.47秒）。Ruff check/format307 files、offline lock、Markdown links、git diff --check成功。18種類の合成応答も全件を期待codeへ分類し、raw bytesと診断結果をprivate directoryへ保存した。

証拠: `/home/products/bonsai-test-logs/20260910-exec102-semantic-diagnostics/` にcommand/exit、RED/GREEN hash、最終source hash、全体log、18合成応答を保存。実API/model call0。live-02で起きた失敗の詳細分岐は依然未特定であり、再実行していない。EXEC-102全体は未完了のまま、次回は商品評価の詳細codeを記録できる。

### EXEC-102継続: 商品評価診断付きの実再開

2026-09-10、利用者の「テストを再開せよ」により、上記の同じ合成入力・接続先・既存credential・費用見積り・件数上限で実再開する。Bonsai最大2 calls、Cloudflare画像2枚、Outscraper task1回/poll50回、商品最大24件、CLIP7 batches、全体900秒、retry0。今回生成した画像への2段階確認を行う。全体offline2716件を検証した5 fileのSHA一致、port18080非LISTEN、新出力先の未作成を確認済み。新規出力先は `/home/products/bonsai-test-logs/20260910-exec102-live-03/`。前回と同じCLI引数でoutput-dirだけを変更する。

途中結果: 実Bonsai1回はHTTP200・819 bytes、視覚1条件として計画作成成功。Cloudflare1回もHTTP200で512×512参考画像を保存・検証した。今回の参考画像を提示して確認待ち。検索queryはマグカップ、商品上限24件。plan期限は2026-09-10 03:28:25 JST、全体900秒も適用する。偽画像・商品検索・CLIP・ランキング・履歴はまだ実行していない。

参考画像への「はい」で同じ実行を継続し、Cloudflare2回目はHTTP200で偽画像を生成・保存した。目視で滑らかな参考画像に対して偽画像は多面体の側面となっている。今回の2枚とquery「マグカップ」を提示して最終確認待ち。商品検索・CLIP・ランキング・履歴はまだ実行していない。

最終画像/queryへの「はい」後に商品検索を実行。Outscraper task1回・poll6回、最終HTTP200・74,445 bytesを受信した。商品評価用BonsaiはHTTP200・8,543 bytesで応答し、ranking_clip_history / semantic_field_bindingでexit1となった。外側/内側JSON、stop終了、assessments件数は通過し、引用field_idが文字列でないか、要求で渡したfield集合に存在しないため拒否された。保存codeはこの2条件を区別しない。今回はJSON復元やfinish_reason拒否ではない。live-02も同じ理由だったとは断定しない。

生成schemaはfield_idを単なるstringとしており、実在するfieldのID集合に制限していないことをコードで確認した。受信側の所属検証との契約差があり、次の修正候補は実在する同一商品のfieldへ引用生成を束縛すること。今回は診断付き実行だけで、生成schemaや判定は変更していない。

Bonsai計2 calls、Cloudflare2 calls、商品画像要求/CLIP0、retry0。ranking未出力、履歴/履歴画像0件。最終商品応答からBonsai応答metadataまで531.973秒で、純粋な推論時間とは区別する。全体期限前の2026-09-10 03:26:31 JSTに終了。履歴DB integrity_check=ok、directory0700/files0600、所有Bonsai終了・port18080非LISTENを確認した。summary.json、HTTP metadata、PNG2枚、audit.jsonをlive-03へ保存。実課金額未照会。文書リンク・anchor・fence、git diff --check成功。EXEC-102の全体実完走は未達。

### EXEC-102継続: 意味評価の引用生成を商品へ束縛

2026-09-10「修正しろ」に基づき進行中。目的はsemantic_field_bindingを生む任意ID生成を止めること。要求schemaを商品別の分岐にし、product_indexと同じ商品の実在field_idを対応させる。field別にUnicode位置の上限を付け、引用できる本文がない商品はscore=null/evidence=[]のみを生成する。受信側の所属・位置・重複検証、出力JSON形式、順位計算、Bonsai/providerは維持する。

schemaの正常/架空ID/他商品引用/空本文/Unicode位置と、schemaを無視する応答の拒否をREDで固定してから実装する。関連回帰・全体offline・標準gate・可能な範囲のローカル文法変換を検証し、合成応答と結果をprivate directoryに保存する。実provider再実行、4面生成、frontend、commit/pushは対象外。完了条件は生成schemaで不正IDと他商品引用を拒否し、既存受信契約・履歴互換が維持されること。rollbackは要求schema変更の取り消しで保存済み結果を変更しない。schema遵守や意味的品質の実モデル確認は別途必要で、今回のoffline成功で代替しない。

修正完了。商品index別・field別の固定値分岐で実在する同一商品への引用を束縛し、Unicode本文長で位置の上限を固定した。非null点数と1〜4件の引用、nullと空引用をそれぞれ一組の分岐にした。空/空白本文は保留のみ、商品0件は空assessmentsを生成する。受信parser・prompt・順位計算・結果JSON形式は変更していない。

新規18件は同じtest SHAで12 failed / 6 passedから18 passed。実在field2種類、架空/別商品/名称推測/null ID、文字数とbyte数の違い、引用なし/空白本文、空batch、任意IDと24商品、受信側の逆転位置/重複拒否を確認した。関連184 passed、全体offline2734 passed / 13 skipped / 30 deselected（65.56秒）。Ruff check/format308 files、offline lock、Markdown links、git diff --check成功。

Python schema converterとローカルC++ GBNF validatorでも14ケースすべてが期待した許可/拒否となった。これは実serverのC++ schema converterやモデル推論の測定ではない。raw合成応答、schema、文法、判定出力、RED/GREEN command・exit・hash、変更前source、最終source hash、全体logを `/home/products/bonsai-test-logs/20260910-exec102-semantic-schema-fix/` に保存。実API/model call0。次は新生成契約での実Bonsai再確認から全体フローを検証する。EXEC-102の実完走は引き続き未完了。

### EXEC-102継続: 引用生成修正後の実再検証

2026-09-10「実Bonsai・実検索の再検証」に基づき、上記の同じ合成入力・接続先・既存credential・費用見積りで実行する。Bonsai最大2 calls、Cloudflare2枚、Outscraper task1回/poll50回、商品最大24件、CLIP7 batches、全体900秒、retry0。今回生成する画像を2段階で確認する。修正時に全体offline2734件を検証したsource/testのSHA一致、port18080非LISTEN、新出力先未作成を確認済み。出力先は `/home/products/bonsai-test-logs/20260910-exec102-live-04/`。同じCLI引数でoutput-dirを変更する。

途中結果: 視覚抽出用Bonsai1回はHTTP200・818 bytes、視覚1条件で計画作成成功。Cloudflare1回はHTTP200で512×512参考画像を保存・検証した。今回の参考画像を提示して了承待ち。queryはマグカップ、商品上限24件。plan期限は2026-09-10 03:49:26 JST、全体900秒も適用する。偽画像・商品検索・商品評価用Bonsai・CLIP・ランキング・履歴は未実行。

参考画像への「はい」で同じ実行を継続。Cloudflare2回目はHTTP200、512×512の偽画像を保存・検証した。参考画像の丸い側面に対して偽画像は角張った側面となっている。今回の2枚とquery「マグカップ」を提示し、商品検索前の最終確認待ち。商品検索・商品評価用Bonsai・CLIP・ランキング・履歴は未実行。

最終画像/queryの「はい」後に商品検索を実行。Outscraper task1回・poll8回でHTTP200・74,080 bytesを受信した。商品評価用Bonsaiは応答完了前に全体900秒の実行期限となり、ranking_clip_history / transportでexit1。2回目のHTTP応答metadataは存在しない。Bonsaiのpost_json中に発生した期限例外を既存runnerがtransportへまとめるため、summary単独では期限を区別できない。停止時刻03:49:24 JSTは起動直後に設定した全体期限と一致し、起動後に作成されたplan期限03:49:26より約2秒早い。

最後の商品応答から停止まで510.381秒で、純粋な推論時間ではない。引用schema修正の成否・意味評価の品質は未確認。Bonsai呼出し開始2回（応答完了は視覚抽出1回のみ）、Cloudflare2回、商品画像/CLIP0、retry0。ranking未出力、履歴/履歴画像0件。DB integrity_check=ok、directory0700/files0600、所有Bonsai終了・port18080非LISTENを確認した。HTTP metadata、PNG2枚、summary.json、audit.jsonをlive-04に保存。実課金額未照会。文書リンク・anchor・fenceとgit diff --check成功。

今回の再検証は期限停止で未完了。既存15分には画像確認待ちと商品検索待ちも含まれ、今回の商品評価に残った時間では応答を得られなかった。次の実検証では段階別の所要時間と実行期限の設計を見直す必要がある。期限延長・新規再試行・引用の判定緩和は行っていない。

### EXEC-102継続: Bonsai商品評価の生成量削減と時間計測

2026-09-10「Bonsaiの実行時間が長過ぎる」に対応。状態: 進行中。現在の実測は商品応答後451〜532秒、live-04は510秒で応答未完了。入力処理と生成時間は未保存で原因の割合は不明。model/provider、数値優先・意味点数・引用検証を維持し、冗長なJSONの生成量を減らす。新wireは商品順の短い配列とfield序数を使い、元の商品index・field_id・引用位置へ受信側で復元する。既存object応答の読込互換を保持し、混在形式と不正な束縛を拒否する。schemaで各商品を順に1件ずつ生成させ、同じ商品indexの重複生成を避ける。

既存の安全なBonsai metrics projectorを実runnerへ接続し、wall時間・prompt/生成tokens・各処理時間を本文なしで保存する。metrics未提供は明示的に未取得とし、成功/拒否判定は変えない。テストを先に固定し、短いwireの復元・不正引用・旧JSON互換・本文非露出・失敗時の時間記録を検証する。合成24商品で生成量を比較し、関連/全体offlineとローカル文法検証を行う。外部API追加送信、GPU移行、商品削減、本文切捨て、期限延長は対象外。実速度の改善は未測定として記録し、今回のbyte削減を速度倍率と同一視しない。rollbackは旧wire生成へ戻し、新旧結果のdomain形式と履歴DBは維持する。

実装とoffline検証は完了。新wireはevaluationsの順序をschemaで商品順へ固定し、field序数と文字位置だけを引用として生成する。既存のSemanticAssessmentへ復元後に同じ検証を通す。旧object読込と比較用compact=Falseを維持し、実経路はcompactを既定とした。実runnerのwall/optional model metrics記録も追加済み。

新規15件は同一test SHAで5 failed / 10 passedから成功。関連255 passed、全体offline2749 passed / 13 skipped / 30 deselected（65.28秒）。Ruff check/format310 files、offline lock、Markdown links、git diff --check成功。既存合成Bonsai fixtureを新wireへ対応させ、元の順位・点数・履歴の検証を維持した。旧schemaテストはcompact=Falseを明記し互換契約として保持した。

24商品・各4引用の同一合成内容を、既存Bonsai GGUFのllama-tokenizeで比較した。入力user contentは4,703→2,593 tokens（44.86%減、14,006→7,959 bytes）、出力contentは2,260→908 tokens（59.82%減、5,775→1,159 bytes）。同じ点数/引用へ復元できる。chat template・system promptを含むサーバーの総prompt tokensではなく、モデル推論も実行していない。Python schema converter＋C++ GBNF validatorの7ケースで、24商品正常/保留の許可と、別商品/範囲外/bool序数、欠落、商品順入替の拒否を確認した。実速度倍率や品質向上は未測定。

証拠は `/home/products/bonsai-test-logs/20260910-exec102-semantic-compact/`。変更前source、RED/GREEN command/exit/hash、全体log、合成入出力・schema・文法・validator結果、GGUF token数を保存。今回の実API/model推論0。現環境のCMakeCacheはCUDA/Vulkan/OpenVINO/SYCLがOFF、CPUはCore i5-13600KFと確認し、実運用iGPUの速度には外挿しない。次は新wireと時間metricsで実Bonsaiを再計測する。EXEC-102全体の実完走は未完了。

### EXEC-102継続: 外部通信なしの実Bonsai時間比較

2026-09-10「実際の時間短縮を、オフラインテストで確認せよ」に基づき実施。対象は既存の合成24商品/96本文の旧要求とcompact要求。localhost127.0.0.1:18080/v1/chat/completions、既存Bonsai-8B GGUFとCPU server、context8192/parallel1、各形式1 call（計2）、各900秒、retry0、credentialなし/費用0。各回serverを起動し直し、cacheがcoldであることを取得metricsで確認する。Outscraper/Cloudflare/外部通信は行わない。

要求を実行前にhashで固定し、旧→compactの順で測定する。wall、prompt/生成tokens、各処理時間、終了理由、既存parserの成否、商品網羅数・非null評価数・引用件数を保存する。要求/応答は今回の合成データだけをrepository外private directoryに保存し、stdoutへ本文や生例外を出さない。出力先は `/home/products/bonsai-test-logs/20260910-exec102-local-timing-01/`。成功時は両形式の完了時間を比較するが、各1回で分散や未知商品の順位品質、iGPU速度は保証しない。片方が未完了/不正ならその制約を明示し、速度だけで改善成功としない。検証コードは専用private scriptで、製品コードは変更しない。

測定完了、品質を維持した高速化の判定は不合格。旧形式は804.309秒でHTTP200を返したが、prompt4,857＋completion3,335がcontext8,192へ達し、finish_reason=length / semantic_finish_reasonで拒否された。prompt163.678秒、生成640.607秒。JSONは未完で、有効な24商品評価は得られていない。

compactは205.518秒でHTTP200・stop終了。prompt2,800 tokens / 85.849秒、生成1,131 tokens / 119.652秒。24商品の非null評価と96引用を既存parserで復元できた。ただし全商品0点で、各商品とも本文先頭の1〜4文字を引用し、検索条件の形状を示す語は引用に含まれなかった。旧未完応答の部分観測ではscore0.95が21件あるが、受理済み評価として使わない。HTTP応答までの時間差は598.792秒であって、同等の正常結果同士の高速化倍率ではない。意味評価品質を保持した改善とは扱わない。

各serverはcold cache（cached_tokens=0）で、同じCPU/GGUF・商品本文を使用。script/source hash不変、所有process終了・port非LISTEN、private権限を確認。合成要求/全応答、parsed結果、時間metrics、manifest/provenance、audit、content-validationを上記directoryへ保存した。専用scriptのexit0は測定手順の完了であり品質合格ではない。モデル2 calls・retry0・外部API/credential/課金0。今回製品コードは変更せず、全体pytestは直前の2749件成功後に再実行していない。次はcompactで構造検証だけを通過する意味評価不良の原因を切り分ける。実商品ranking、全検索E2E、iGPU速度は未検証のまま。

### EXEC-102継続: Bonsaiを視覚条件の意味付けへ限定

2026-09-10の明示指示に基づく仕様変更。状態: 進行中。candidate経路のBonsaiを、入力からCLIP用の視覚条件・反対条件を作る処理だけに限定する。商品採点と商品本文の属性追加推論の注入入口を除去する。SudachiPyと既存規則による条件抽出、観測属性の確認、必須/希望条件の決定的判定は維持。Bonsaiの意味点数を既存のタイトル単語一致点数へ置換し、画像ありは単語一致80%＋CLIP20%、画像不明は単語一致のみとする。必須条件状態・必須充足率・希望充足率の優先順位は変えない。

REDで非視覚Bonsai入口の廃止、単語一致による同条件商品の順位、必須条件優先、fixture結合のBonsai1 callだけ、旧履歴読込と新profileを固定し、最小実装後に同じテストをGREENとする。関連回帰、全体offline、Ruff、lock、Markdown/diffを検証する。実Bonsai/外部API/画像生成/委託UIは今回実行しない。旧意味評価の単体診断は現行フローから切り離して残す。

結果契約はcandidate-confirmed-lexical-v2、最終採点はcandidate-lexical-clip-v2へ更新し、semantic_score/assessmentと非視覚Bonsai応答hashを新結果から除く。旧中間結果JSONを新規採点として再利用せず拒否し、再検索が必要。既存の表示履歴は旧profileの点数を保持して読込可能とし、書換えやDB移行をしない。cache/履歴の識別は新profileを含むdigestで分離する。rollbackは本変更のsourceと新テストを戻す単位で行い、旧履歴は削除しない。単語一致の未知同義語への限界、実商品順位品質、実時間改善は別評価とする。

本仕様変更の実装・offline検証は完了。新規12件は同一test SHAで10 failed / 2 passedから12 passed。関連309件、全体2755 passed / 13 skipped / 30 deselected（63.41秒）。最初の全体検証は、廃止したSemanticBonsai fixtureを参照する旧結合8件だけ失敗した。旧応答parserの18ケースは保持し、旧意味処理・商品属性推論を呼ぶと失敗する結合テストへ置換して、Bonsai視覚提案1回・画像承認・商品取得・CLIP fixture・履歴再読込までを確認した。新旧表示履歴のprofile/点数保持、画像不明時の単語一致採点、数値/予算/不明の優先順位、結果JSON復元も成功。

Ruff check/format311 files、offline lock、Markdown linksとgit diff --check成功。証拠は `/home/products/bonsai-test-logs/20260910-exec102-visual-only/`。変更前source、RED/GREEN command・exit・hash、初回/最終全体log、関連log、最終hashを保存。実model・外部API・credential・課金は0で、実検索E2Eは再開していない。Bonsaiの意味点数高速化という前案はこの仕様変更で終了し、次の確認対象は新採点方式の実商品順位品質と全体フロー。旧legacy検索・委託frontendは変更せず、実完走未達のEXEC-102全体は引き続き進行中。

### EXEC-102継続: Bonsaiの検索語候補作成を追加

2026-09-10の「CLIP用の視覚条件抽出 とこれにのみBonsaiを使う」に基づく仕様変更。状態: 進行中。Bonsaiの役割を視覚条件提案と商品句の言い換え語・英訳候補作成の2つへ限定する。商品採点・仕様補完は禁止したまま。検索語候補は各言語最大3件・各64文字、strict JSON・stop終了・長さ/文字種/URL/重複を検証し、検索原文と要求・応答digestへ結ぶ。意味上の同義性は自動検証済みとせず確認を必要とする。

原文とSudachi商品句から候補を作り、元のquery・条件・画像prompt・ランキング用intentを変更せず計画へ別保持する。候補作成は任意注入の1 callだけ。失敗/不正時は候補を不採用にして元queryを維持し、固定statusとdigestだけを残す。既存の視覚抽出失敗をこのfallbackへ巻き込まない。

画像生成/取得承認前だけ、利用者が元query・日本語別名・英訳から検索queryを1本選べるbackend操作を追加する。owner・計画digest・state・候補indexを検証し、更新後digestで再確認させる。日英同時実行は最大48件となりCLIP上限32件を超えるため、今回の経路は1 query/24件を維持する。候補を全部AND結合せず、選択した商品句を検索語とし、元の属性条件は商品取得後も維持する。未選択時は元queryだけで検索する。委託UIは対象外。

専用実runnerは視覚抽出＋候補生成の最大2 callsへ更新し、候補一覧と固定indexを画像生成前に確認できるようにする。検証はstrict応答・原文条件/順位非変更・選択の有界性・古い承認拒否・Bonsai2 callsが商品取得前だけであること、画像/CLIP/履歴fixtureまでの接続。RED/GREENを固定し全体offlineを実行する。実モデル/外部API/課金は行わず、実品質/時間を未検証と明示する。候補選択を含む計画digestで旧計画の流用を拒否し、表示履歴のDB移行は不要。rollbackは本追加のsourceと新規テストを戻す単位で行い、既存履歴を変更しない。

実装・offline検証は完了。利用者が「候補を確認して反映」を明示し、画像生成前に選択した1本だけを実要求へ反映する。実要求と選択queryからの再構成結果を照合し、保存計画の不整合も拒否する。新規24＋13＋2件のRED/GREEN、関連356件、最終全体2794 passed / 13 skipped / 30 deselected（62.48秒）。Ruff315 files・lock・文書・diffも成功。証拠は `/home/products/bonsai-test-logs/20260910-exec102-query-terms/`。実Bonsai・外部APIは未実行で、候補の意味品質と新方式の実検索E2Eは未検証のため、EXEC-102全体は進行中を維持する。


### EXEC-102継続: 実Bonsaiの視覚条件と検索語候補の品質確認

2026-09-10、利用者の「実Bonsaiの推論品質を確認せよ」に基づくローカル診断。状態: 準備済み。既存Bonsai-8Bと現行の2用途の要求を変更せず、今回用意した合成6入力（花瓶・工具箱・名刺入れ・じょうろ・ランチボックス・掛け時計）で必須・希望・除外・視覚条件なしを検証する。価格は全例に含め、視覚条件への混入を不合格とする。視覚節と強度の完全一致、属性keyの意味、全検索語の同一商品種別・属性非追加、各例で有用な英訳1件以上を採点する。日本語同義語の空配列は許可する。両用途6/6を今回の合格条件とし、構造検証と意味判定を分ける。

合成入力・基準・12要求・実装/モデル/server/library hashを `/home/products/bonsai-test-logs/20260910-query-visual-quality-01/` へ凍結。prepareで合成6応答とquery要求一致を確認した。実行前にSudachiが名刺入れを名刺へ変換する点を記録し、実Bonsaiへの入力不良をモデル誤りと混同しない。推論結果で製品queryを再構成できるかも別集計し、視覚処理失敗後に独立実行した語句診断をフロー成功に数えない。

実行条件は127.0.0.1:18080、既存GGUF/server、context8192・1 worker、各例でcold起動後に視覚→語句の最大2 calls、計12 calls・retry0・各例最大900秒。認証情報・外部API・課金0。各callの全合成応答と処理時間を0700/0600で保存し、所有serverの停止とhash不変を確認する。現在のローカル検証の継続指示と今回の明示依頼に基づき条件通知後に実行する。検索・画像生成・CLIP・履歴・委託UIは対象外。製品codeを変えず、観測後のケースを未知精度の再評価へ流用しない。完了時に実測と残る制約を記録する。


診断完了、品質は未達。全12応答がHTTP200/stopだが、視覚はparser受理3/6・意味合格2/6、語句は受理6/6・意味合格1/6、両用途合格0/6だった。希望/除外のrequired化と視覚条件なしの不要保留、形状の誤った属性key、上位カテゴリへの言い換え・英訳誤りを確認した。名刺入れ→名刺は推論前の処理不良として分離した。視覚拒否後の語句診断は実フロー成功に数えない。応答待ち時間は2用途合計17.156〜21.812秒/例（server起動を除く）。12全応答とsemantic-review.json/audit.jsonを同directoryへ保存し、hash不変・所有server停止・port非LISTENを確認した。

次は商品名の欠落を防ぐ前処理と、希望/除外・属性対応・同一商品種別を維持できる意味推論方式を改善する。現在の人間確認を維持し、今回の6例は観測済みdevelopmentとして扱う。製品codeは未変更で、実検索E2EとEXEC-102全体の完了は引き続き未達。


### EXEC-102継続: 原語と言い換えごとに英訳を1つ保持

2026-09-10の「英訳はオリジナルと言い換えに対してそれぞれ１つでよい」を実装する。元の商品句のoriginal_enと、最大3件のsynonyms（ja/enの対）へ変更し、各enは1文字列または明示保留のnullとする。対応がない独立英訳リストを廃止する。重複した同じ日本語へ異なる英訳を付けた応答は拒否する。英訳の候補列挙を1語句1訳へ絞るが、実意味品質の改善は未検証とする。

候補確認に対応関係を渡し、選択肢は元の日本語・日本語言い換え・各英訳を最大8本から1本選ぶ。検索上限24件、画像生成前の確認、原文条件と採点intentの保持は維持する。query expansion profileはv2として旧v1中間計画を拒否し、表示履歴DBは変更しない。RED/GREEN・関連・全体offlineを実行し、実Bonsai・外部APIは本変更では呼ばない。rollbackは本schema/adapter/確認処理とテストを戻す単位。既存の推論品質問題やSudachiの商品句欠落は今回の変更で解決したと扱わない。


実装・offline検証完了。原語original_enとsynonymsの各ja/en対を保持し、英訳配列・訳の欠落・同じ日本語に複数の訳を付ける応答を拒否する。未確定はnullとして明示。query expansion profileをv2へ更新し、候補対応の確認と最大8本からの1本選択を接続した。新規10件のRED/GREEN、関連69件、全体2804 passed / 13 skipped / 30 deselected（64.86秒）。Ruff316 files・lock・文書・diff成功。証拠は `/home/products/bonsai-test-logs/20260910-query-translation-pairs/`。実Bonsaiは再実行しておらず、意味品質の基準未達は未解決のまま。


### EXEC-102継続: 日本語接尾辞を検索語に保持

2026-09-10の「接尾辞を除外するな」に従い、tokenizerで接尾辞を保持する。文字位置が連続する直前の語へ接尾辞の表記を結合し、名刺入れ→名刺という欠落と、分割後の再解析による名刺 入れるへの変形を防ぐ。特定の商品語彙には依存しない。語の組立後に重複を除き、名刺と名刺入れを別々に保持する。Latin語の表記は維持し、接尾辞製はsony製として残す。助詞・句読点を除く既存規則、sourceの全形態素span解析、英語処理は維持する。

token・最終Outscraper query・Bonsai語句候補への入力・タイトル一致の回帰をRED/GREENで確認し、関連・全体offlineと静的gateを実行する。商品別辞書の追加、視覚条件推論やモデル変更、実Bonsai/外部API、委託UIは対象外。既存表示履歴を再採点せず、新計画は修正後の語句とqueryのdigestで承認する。rollbackはtokenizer・回帰テストの変更を戻す単位。検証結果と未測定の意味品質を記録する。


実装・offline検証完了。名刺入れを最終検索queryとBonsai商品句へ保持した。接尾辞は連続する語の元表記へ結合し、辞書形から軽いさ等を作る問題も追加7例で修正した。新規9件＋7件のRED/GREEN、最終関連145件、全体2820 passed / 13 skipped / 30 deselected（64.42秒）。Ruff318 files・lock・文書・diff成功。証拠は `/home/products/bonsai-test-logs/20260910-suffix-retention/`。実モデルの再評価は行っておらず、推論品質の課題とEXEC-102全体は未完了。


### EXEC-102継続: LFM2.5-1.2B-JPの限定比較

作成・更新2026-09-10、状態: 進行中。利用者の試用指示に基づき、公式LiquidAI/LFM2.5-1.2B-JP-GGUFのQ6_Kを診断専用に取得する。目的は現行の視覚条件抽出と1語句1英訳をBonsaiより少ない時間・メモリで処理できるか、品質と別々に確認すること。製品provider・prompt・parser・cache・履歴・委託frontendは変更しない。

配布revisionとLFS SHA-256を固定し、既存llama-serverを共用する。接尾辞修正後の観測済みdevelopment6例を両モデル各2用途、計24 calls・retry0・各例900秒まで実行する。温度0、context8192、1 worker、例ごとにcold起動し視覚→語句の順。要求の相違はmodel識別子だけとし、モデル固有のtokenizer/chat templateはGGUFのものを使う。視覚節・強度・属性keyの意味と、全語句の同一商品種別・各英訳を評価する。明示nullは保留として別計数し、各例で有用な原語英訳と全候補の妥当性を求める。両用途6/6を小標本の合格条件とし、未知精度へ一般化しない。

継続する試行指示に従い、接続先127.0.0.1:18080、合成入力・回数・上限・保存範囲・credential不要・API費用0を通知した。公開配布の取得以外に外部送信しない。全要求/応答・command・hash・時間・server RSSを新規private directoryへ保存する。手順は取得hash確認→合成preflight→24実推論→意味レビュー→所有server停止/hash不変確認。製品code変更がないためTDD/全体pytestは対象外、文書gateを実行する。rollbackは診断serverの停止で完了し、既存モデルや設定を置換しない。iGPU・電力・実検索/画像/CLIP/E2Eは未測定として残す。

初回比較24 callsを完了。LFMは12/12がHTTP200だがJSON以外の本文となり、全件parser拒否。既存llama.cppのcommon_chat_params_init_lfm2_5はtoolsだけでgrammarを構成し、inputs.json_schemaを反映していないことを確認した。モデル品質とruntime不整合を分離するため、同じschemaをtop-level json_schemaとしてserver-taskの直接変換へ渡す診断を追加する。source/messages/temperature/parserは変更せず、追加12 calls・同じ期限/retry0/保存条件を通知した。初回要求・応答は保持し、新規lfm-direct directoryへ固定要求と結果を保存する。

top-level json_schemaは全12要求がHTTP400で、通常transportは非200本文を破棄した。合成1要求だけエラー本文取得用transportで追加確認し、Failed to initialize samplersを記録。LFM specialized処理が返すgeneration promptをJSON grammarへprefillする経路との不整合が疑われる。次に同じ元要求とmodelを使い、診断serverへ--no-jinjaだけ追加した12 callsを実行する。legacy経路はschemaをgrammarへ変換し、specializedなgeneration promptを使わない。通信失敗で残りを止める。要求・評価基準・製品設定は維持し、2つの失敗試行と改善後を混ぜず保存する。

限定比較は完了。最終--no-jinja構成のLFMは12/12でJSON生成、視覚意味1/6・語句意味0/6。Bonsaiは視覚2/6・語句1/6で、両者とも事前基準未達。2用途中央値はLFM10.881秒/Bonsai23.260秒、ピークserver RSSは1.113/2.410GiBだが、等品質の速度比較ではない。診断用のruntime切替だけで、製品採用は行わない。全証拠とsemantic-review.jsonは `/home/products/bonsai-test-logs/20260910-lfm-jp-comparison-01/`。診断49 POST（正常36・HTTP400拒否13）、外部推論/認証/課金0。所有server停止・port非LISTEN・hash不変を確認した。詳細はWORKLOG161。EXEC-102全体の実検索完走と意味品質は未達で継続する。


## EXEC-103: 辞書と文脈による検索語の自動選択

作成・最終更新2026-09-10、状態: 進行中。利用者の進行指示に基づき、検索語側を辞書・構文解析・語義選択へ移し、CLIP用の視覚条件抽出はBonsaiを維持する。関連: EXEC-102の意味品質未達、検索候補の人間確認、接尾辞保持。商品採点・画像生成・履歴DB・委託frontendは対象外。

対象はローカルのJMdict/WordNet読取、語義候補と出典ID、GiNZAによる商品句/修飾の原文範囲、文脈と定義を比較する小型ONNX encoder、保留と候補確認への接続。元語と各言い換えに英訳1件、検索1 query/24件、元の条件と順位計算を維持する。辞書にない語を生成せず、未収録・語義不確実は追加候補なし、商品/条件関係が解釈不能なら検索前に保留する。否定・OR・部位修飾を捨てて続行しない。

手順: 公開資材取得とhash/ライセンス固定→原文範囲/辞書/選択/保留のRED→最小実装GREEN→実辞書・GiNZA・encoderのネットワーク不要診断→既存backendへのfixture接続→関連/全体offlineと文書gate。評価用合成入力は既知6例に加え、同綴り別語義・複合語・未知語・否定/OR/部位条件を事前固定する。構文/意味の受理精度と保留率、時間/RSSを分け、誤った自動採用を成功に数えない。閾値は開発用として明示し、未知商品の一般精度やproduction E2E成功を主張しない。

公開資材取得のみ外部通信し、認証・API課金・検索入力送信は0。通常runtimeはlocal_files_only相当、CPU1 worker、最大入力2000字・語義候補有界、DBはread-only、候補と辞書/model hashを結ぶ。公開辞書・モデルと合成応答ログはrepository外に置き、利用者データは保存しない。任意のlexical依存groupで既存環境の軽量構成を維持する。Bonsaiから辞書方式へprofileを分離し、旧履歴はそのまま表示、旧中間計画を新方式として流用しない。rollbackは本経路の注入を外す単位とし、Bonsaiの語句自由生成への自動fallbackは行わない。


実装とoffline接続を完了した。JMdict/WordNet importer、語義IDによる選択/保留、GiNZAの原文範囲、量子化E5とmanifest検証、候補確認への接続を追加した。検索語Bonsaiの実入口呼出しを除き、視覚用1回だけを維持する。初回のONNX token_type_ids欠落と、GiNZAがdep未確定とした連続名詞の欠落を修正した。ランチ ボックスという既存の検索用分割表記は両語を保持し、辞書検索では全商品句として照合する。

実ローカル資材＋fixture providerの接続3件が成功し、画像承認・query選択・CLIP・SQLite履歴の境界を確認した。合成17入力の実語義診断は8件選択/8件正答・9件保留。文脈付きマウス/ドライバー4例は全保留で、自動語義解決の品質は未達。現在のencoderは検索用embeddingであり、語義選択の学習/校正済みモデルではない。閾値は0.75/差0.04を変更せず、観測例を未知holdoutへ流用しない。構文受理16/17は商品句抽出の指標であり、条件関係の解釈成功率ではない。EXEC-103全体は品質課題のため進行中。

資材は `/home/products/models/search-lexical-v1/ready/`、応答・段階ログ・意味判定は `/home/products/bonsai-test-logs/20260910-lexical-rag-01/`。実検索、画像生成、実CLIP、Bonsai実推論、委託UIは今回未実行。公開資材取得だけ外部通信、認証/推論課金0。初期のテストimport/field参照誤りは製品不良と分けて保存し、初回全体のBonsai2回という旧期待値2件を1回へ更新した。詳細な最終gateはWORKLOG162へ記録する。


最終全体offline: 2851 passed / 16 skipped / 30 deselected、59.57秒。実ローカル資材の接続3 passed。Ruff/format/lock/文書/diff gate成功。意味品質の未達と実provider未検証は維持する。


### EXEC-103継続: 日本語定義と小型比較モデル、曖昧時だけBonsai

2026-09-10、利用者の提案採用指示に基づき開始。既存WordNetの日本語定義・用例を語義単位で保持し、英語定義の複数行欠落も修正する。日本語定義があるWordNet語義を優先する新辞書profileを追加し、JMdictと根拠なく語義を結合しない。既存v1資材と履歴は保持する。

公開japanese-reranker-xsmall-v2の固定revision/量子化ONNXを別directoryへ取得し、原文と語義定義の対をCPUで比較する。選択の暫定基準はsigmoid score 0.80以上、次点差0.20以上。未知語と文脈なし多義語はBonsaiを呼ばず保留し、小型モデルが曖昧とした文脈付き候補だけBonsaiに既存ID/nullの選択を1回求める。自己申告confidenceは使わず、候補IDとアプリが保持する原文への参照を検証する。どのモデルも語句・英訳・商品属性を自由生成しない。CLIP用Bonsaiと商品採点は維持する。

RED/GREENのargv/exit/test hashを固定し、最初の4文脈と無文脈・未知・否定例の診断、fixture接続、全体offlineを実行する。合成入力の全応答と処理時間をprivate directoryへ保存する。公開資材取得以外の外部API/credential/課金/実検索/画像/委託UIは対象外。実Bonsaiは準備済みlocalhostを限定診断し、実行条件と最大回数を事前提示する。品質未達なら誤選択と保留を別集計し、合格基準を下げて通過させない。cache/profileの変更は新規計画へ限定し、旧承認と混用しない。rollbackは新profileとBonsai語義選択の注入を外す単位。


初回小型モデルは元の4例すべてで正解語義を最上位としたが、絶対scoreは暫定基準未満。実Bonsaiの最初の診断は、診断transportの応答上限指定が既存契約と合わず送信前に拒否された（実POST 0）。指定を既存定数へ修正して8 POSTを完了し、元4例は2件採用・2件保留、否定2件は正答、無文脈/未知は呼出しなし。一方、小型/候補外の2入力に誤った語義を採用した。全応答を保存し、これを合格扱いにしない。

対処は商品名や語彙の例外追加ではなく、候補検索と確認の分離とした。Bonsaiには小型モデルの上位2候補だけを渡し、最上位と一致した場合のみ採用する。引用文の自由生成を廃止し、アプリが保持する原文の参照index/nullへ変更した。モデルが不一致なら保留。暫定score閾値は変更しない。追加の最大8 POST・同じlocalhost/900秒/認証不要/課金0を通知し、別directory confirm-v3で要求とhashを凍結した。同じ例はdevelopmentとして評価し、独立holdoutとは呼ばない。


最終8 POSTでは元4文脈が4/4正答、否定2例も正答した。development12例全体は正答7件・誤答1件・保留4件。小型モデルとBonsaiの一致は正しさの保証ではなく、候補外の1例を語義選択単体で誤って採用した。この例は実ローカル構文解析を含む候補準備で未解釈関係として停止し、語句選択が呼ばれないことをofflineで確認した。EXEC-103の品質課題は継続する。語義選択BonsaiのHTTP時間中央値8.835秒、最大12.740秒で、CLIP抽出とserver起動を含まない追加時間である。

保存済み実応答のoffline再生では12例の結果が完全一致し、8応答を使用、HTTPは0回。実ローカル資材テスト2件成功。固定revisionの37,367,189 bytes量子化ONNXと辞書は `/home/products/models/search-lexical-context-v2/`、全合成応答・要求・phase hash・結果は `/home/products/bonsai-test-logs/20260910-lexical-context-02/`。実Bonsaiは合計16 POST・retry0で所有server停止を確認した。外部推論・credential・課金・実検索・実画像・委託UIは未実行。


最終の通常offline検査は2872 passed / 18 skipped / 30 deselected（59.92秒）。`uv run --frozen --offline --no-sync pytest -m 'not live_api'` を実行した。Ruff check/format（339 files）、offline lock（114 packages）、Markdownリンク/anchor/fence、git diff --checkも成功。記録はfull-offline-standard.json/logと各gate log。


### EXEC-103追加検証: 別語の未使用入力

2026-09-10、利用者の「ドライバーやマウス以外の未知入力を試せ」に従い、ファン・クラブ・キャップ・ライト・ストック・ハブ等の新規合成19文を固定した。語義選択12件（肯定10・否定対比2）、保留対照7件（無文脈3・候補語義欠落2・未収録語2）。肯定には人・場所など商品以外の言語的対照3件を含み、商品検索適格性の成功とは数えない。正解IDは辞書定義を読んで事前固定し、期待値はモデル要求に入れない。既存lexical case setとの原文完全一致がないことを検査し、学習データ未知とは主張しない。

モデル・辞書・prompt・閾値を変えず、元19文の語義選択を評価する。localhost18080、実Bonsai最大16 calls・retry0・全体900秒・1 worker・無認証・課金0。現行runtimeの準備済み資材だけを使い、外部API・実検索・画像生成・UIは対象外。要求/全応答/時間/採点/凍結hashは `/home/products/bonsai-test-logs/20260910-lexical-unseen-01/`。語義選択の正答・保留・誤答を別集計し、保留すべき7例の誤採用0と正解あり12例の正答を基準とする。観測後はdevelopmentへ移し、今回は製品修正を混ぜない。


19例の実測完了。正解あり12例は11正答・1保留、保留対照7例は4保留・3誤採用で基準未達。文脈なしの「クラブが欲しいです。」「キャップを買いたいです。」をそれぞれゴルフ用・瓶のふたへ誤確定し、USB用ハブを車輪中心部へ誤確定した。前者2件は依頼表現の残りを文脈ありとしてBonsaiを呼び、両モデル一致で採用した。後者は辞書候補が1件なら文脈との適合を検査しない経路で採用した。スキー用ストックと未収録語2例は保留できた。

実Bonsaiは15 POST・retry0・HTTP時間中央値8.519秒/最大11.426秒、全19結果と15保存応答のoffline再生が一致し、再生HTTP0回。所有server停止・凍結hash不変を確認。原文からの候補準備は18/19が語義選択前に停止し、無文脈ファンの1件だけ元query保持で準備できた。正解あり12例も全停止しているため、これを誤採用問題の解決や検索全体の成功とは数えない。現在の語義単体の精度と構文/条件解釈の通過性を分けて改善する必要がある。今回は診断のみで、製品code・prompt・辞書・閾値を変更していない。


### EXEC-103継続: 商品句候補を条件検査より先に解決する

2026-09-10、利用者の方向採用指示。原文上の商品名と検索用候補を分け、依頼表現を形態素で識別し、係り受けから得た対象名と修飾情報で複合語辞書候補を検索する。候補未収録/文脈不一致の場合だけBonsaiに原文に沿う商品名候補を提案させ、辞書へ再照会する。既存語義選択と商品名補完は1回の候補用Bonsai枠で実行する。CLIP用Bonsai、単語一致/CLIP採点、元語/言い換え各1英訳、人間による検索候補確認を維持する。

辞書を引く前の条件解釈失敗を解消し、未解釈の条件が残る場合も商品名候補と原文の関係を検査可能なreviewとして返す。候補名の解決を仕様充足の証明とせず、未解釈条件がある実検索・画像生成は既存の停止を維持する。検索対象を収納対象などへ入れ替えない。既存候補に合わない場合、IDを捏造せず未確認の語句提案として扱う。保留時は元の入力を維持する。

変更対象はlexical構文/辞書検索/候補解決とcandidate準備・専用runner。外部API・実検索・画像・UIは対象外。新しいproposal profileをsource/dictionary/model/request/responseへ束縛し、旧profile・旧履歴を保持する。例外文言に原文やモデル本文を含めない。USB複合語、収納対象、依頼表現の活用、未知語、否定/除外、原文改ざん・条件保持をRED/GREENとoffline全体で検証する。全応答/phase argv/exit/hashは `/home/products/bonsai-test-logs/20260910-product-phrase-01/`。実モデルは別の限定条件を通知して測定し、固定例を未知holdoutと扱わない。rollbackは新prepare経路と新resolver注入を外す単位。


実ローカル資材で商品句・依頼活用形・複合語検索を確認し、候補確認からfixture画像/候補/CLIP/履歴の接続も成功した。初回実Bonsai4 POSTでは正しい辞書IDと同時に商品名・英訳を生成したため、排他的な受信契約に違反し4件とも保留した。受信側を緩めず、生成JSON Schemaを辞書選択/未収録名提案/保留のoneOfへ変更。混在応答を拒否するRED/GREENとllama.cpp文法変換を確認し、resolver hashをexclusive-v2へ更新した。

全体offlineは2892 passed / 20 skipped / 30 deselected（64.61秒）。追加の実Bonsaiは前回8例と未収録エアタグホルダー1例の9 development入力、最大8 POST・同じlocalhost18080/900秒/無認証/課金0/再試行なしを通知した。新しいprivate directory live-exclusive-nineへ入力・要求・source/model/hashを固定した。初回の失敗と修正前prepare記録を上書きせず保持する。


最終9例では実Bonsai5 POSTが全て排他的な形式で受理された。USB用途からUSBハブを選び、収納対象を含む文ではケースを対象に維持し、車輪用ハブも対応する語義を選んだ。依頼表現しかないクラブ/キャップは追加語義を保留し、明示USBハブは辞書だけで解決した。未収録エアタグホルダーは辞書IDなしの候補となったが、名称は原文の反復で英訳は保留した。未知名の補完・英訳品質全般が改善した証拠とはしない。

保存済み5応答のoffline再生で9例の商品名review/保留を完全再現した（HTTP0回）。原文からの候補準備は3件成功・6件停止。無文脈クラブ/キャップは元queryを保持し、明示USBハブは日英query候補を作成した。他の用途/取り付け/収納条件付き5件は商品名reviewを付けてquery_buildで停止し、除外1件はproduct_scopeで停止した。USB用途の検索全体が通るようになったとは扱わない。HTTP中央値11.963秒・最大14.469秒は候補用Bonsaiの追加時間であり、CLIPと起動は含まない。

本作業の実Bonsaiは初回4回と最終5回の合計9 POST、retry0。所有server停止と固定hash不変を確認。今回の構造変更と限定検証は完了し、未解釈条件と未知入力品質の課題はEXEC-103に残す。最終証拠は同private directoryのRESULT.md、audit.json、live-exclusive-nine/results.jsonとreplay-result.jsonに保存する。実検索・実画像生成・実CLIP・委託UI・外部APIは未実行。


### EXEC-103追加検証: 未収録の商品名補完と英訳

2026-09-10、利用者の品質確認指示に従い、未使用の合成12入力を実推論前に固定した。4商品の汎用名からの文脈補完4例と、辞書未収録の複合商品名を明記した英訳4例、判断保留対照4例を分ける。正答には商品対象と必要な用途概念を含む自然な名称・英訳を要求し、汎用名の反復や英訳nullは成功に数えない。8正例の全英訳・4補完の成功、根拠のない具体化0・対照4例の保留を基準とする。これはモデルの学習データ未知を保証する評価ではない。

準備済み辞書/構文解析/比較モデルと現行Bonsaiのみ。候補辞書IDがない複合名4件、構文解析受理12件、Bonsai予定8要求を送信前に確認した。送信先localhost18080、最大12 POST・retry0・全体900秒・1 worker・無認証・API費用0。全入力/全要求/全応答/時間/判定は /home/products/bonsai-test-logs/20260910-product-name-quality-01/ に保存する。原文候補準備と再生も別集計する。製品code・prompt・辞書・モデル・閾値は変更せず、初回結果を見て基準を緩めない。実検索・画像生成・CLIP・委託UI・外部API・新規資材取得は対象外。観測後はdevelopment例として扱う。


測定完了、品質は未達。実8 POSTは形式として全て受理されたが、汎用名からの補完0/4、未収録名明記時の英訳0/4、8正例全体の必要概念を満たす英訳0/8だった。文脈付き一般名は辞書語義を選ぶだけで、用途を含む商品名へ補完しなかった。スタンドを小さなテーブル、トレーを金属容器panとして選ぶ語義誤選択2件もあった。未収録名の4応答はモデルが全field nullを返しており、JSON復元や受信側が英訳を捨てた問題ではない。

対照4例はBonsai前の否定関係/無文脈判定で保留し、モデル自身の保留品質の証拠ではない。保存済み8応答で12例を完全再現（HTTP0）。候補準備は元queryを使う無文脈2件のみ成功し、正例を含む10件がquery_buildで停止した。HTTP中央値4.327秒・最大18.292秒、所有server停止・固定hash不変を確認。全結果と意味判定は同private directoryのRESULT.md、semantic-review.json、results.json、replay-result.jsonへ保存した。

今回の確認作業は完了。EXEC-103では未知名補完・英訳の品質未達を継続課題とする。辞書語義の選択と用途を保持した名称/英訳作成を分け、広い語義との一致を補完完了としない構成を次の改善候補とする。全保留を生むモデル内部の原因までは断定しない。今回、製品code・prompt・辞書・モデル・閾値は変更していない。


### EXEC-103継続: 辞書候補なしのBonsai直接推論

2026-09-10、利用者の実装指示。辞書lookup_productsが正常に空候補を返した場合だけ、辞書語義選択とは別のBonsai名称生成へ分岐する。原文と購入対象を渡して日本語名と英訳各1件を提案し、辞書候補や定義を渡さず、生成後も辞書へ再照会しない。文脈修飾のない未収録の商品名も対象。意味が不明な場合は保留する。辞書エラー・候補過多・モデル失敗を空候補と扱わない。

元語と同じ末尾を要求する制約はこの未確認の直接提案だけに適用しない。既存辞書選択/提案の制約と別のresolution_methodで識別し、元の対象・条件と候補の確認を保持する。意味の正しさを文字列検査で証明したとは扱わない。既存profile/履歴の読み込みは維持し、request/resolver hashの世代を更新して旧中間承認と混用しない。CLIP・ランキング・検索回数・委託UIは対象外。ネット検索やモデルprovider追加は行わない。

RED/GREENで空候補/非空候補/辞書失敗/文脈なし/語尾変更/不正JSON/出典/条件保持/人間確認を検証し、関連/全体offlineへ進む。記録は /home/products/bonsai-test-logs/20260910-dictionary-miss-inference-01/。実Bonsaiを再測定する場合は別途範囲通知・要求固定を行う。今回の実装成功と実推論品質は分ける。rollbackは直接推論への分岐を外す単位。


直接推論の実装を完了。最初のREDは8失敗/3成功、同一test hashのGREENで11成功。追加回帰とfixture接続を含む関連57件、全体offline 2906 passed / 20 skipped / 30 deselected（64.29秒）が成功した。既存の辞書ありfixtureはcross_encoderを使うため、新規assertのdictionaryという誤期待を修正した記録も残す。製品の辞書あり分岐は変更していない。

事前通知した既知6例の実Bonsaiで、辞書候補/IDを含まない要求6件を送信し、全件bonsai_inferenceとして名称と英訳を受理した。全て名称明記例なので日本語名は原文の反復であり、新しい名称の文脈補完精度の証拠ではない。英訳は必要概念を満たすもの3/6。ヘッドホンハンガーをbagへ変えた1件、モニターの上と机の下の意味が抜けた2件は未達。前回全保留だった明記4例のうち2例では必要概念の英訳を得たが、汎用品名からの補完4例は再測定していない。

今回の範囲は正常な辞書候補0件だけ。辞書に広い語義が存在する場合は従来経路を維持するため、先に確認した広い語義で補完が止まる問題全体を解決したとは扱わない。実検索・画像生成・CLIP実推論・委託UI・外部APIは未実行。名称の意味検証と英訳品質はEXEC-103に残す。


保存済み6応答によるoffline再生で6件の候補reviewが完全一致し、追加HTTP0回。文脈なし2例は候補準備成功、用途付き4例はreviewを保持してquery_buildで停止した。所有server停止・固定hash不変・private directory権限を確認。最終結果は同directoryのRESULT.mdとaudit.jsonに保存した。


### EXEC-103追加検証: OPUS-MT日英翻訳

2026-09-10、利用者の試験指示。今後の入力・説明ではヘッドフォン表記を使い、過去の実応答/固定入力ログは書き換えない。OPUS-MT ja-enを準備し、商品句全体を翻訳する。既知の商品句4件と追加8件を事前固定し、対象種別と用途/位置関係など必要概念を維持するかを判定する。12/12の概念充足と対象の取り違え0を目標とする。過去Bonsaiは原文全文を受け、この翻訳は商品句だけを受けるため、同一条件のmodel比較や未知精度の証拠ではない。

公開配布元からモデル/実行依存だけを取得し、認証・推論API料金・翻訳文の外部送信0。repositoryとは別の環境/資材directoryへ保存する。翻訳はCPU・1 worker・2 threads、beam4・最大64出力tokens、各1候補。元のfloat32とINT8版を同じ12例で比較し、最大24翻訳を記録する。全入力/出力/時間/資材hash/argv/exitは /home/products/bonsai-test-logs/20260910-opus-mt-ja-en-01/。製品のprovider、依存lock、Bonsai名称推論、CLIP、ランキング、履歴、委託UIは変更しない。品質不足でも基準を下げず、今回の試験結果と採用判断を分ける。


試験完了。通常精度/INT8とも概念充足6/12（既知4例3/4・追加8例3/8）で、品質基準未達。デスク下ヘッドフォンハンガーは両精度でHeadphone hanger under the deskとなった。一方、名刺入れはcardのみ、収納かご/フックの対象が欠落し、保護スリーブをstorage、コンセント用キャップをfilterへ変えた。モニター上の位置も欠落した。単語の表記訂正は今回以降に適用し、以前の固定入力/応答は保持する。

CPUの1件中央値はfloat32 0.133秒、INT8 0.046秒。peak RSSは518.6/153.9 MiB、model.binは305,346,797/80,485,157 bytes。各12件を一巡した値で、モデルロード・Bonsai/CLIPとの同時実行・本番iGPUの性能は含まない。元のMarian配布をCTranslate2 4.8.2へ変換し、同一のtokenizer/語彙を使用。全24出力EOS終了、入力unknown token0、固定hash不変。推論processはunshare --netによるnetwork namespace分離で外部通信を禁止した。

初回環境はPython 3.14によるNumPy source buildを停止し、既存Python 3.13の独立環境02でbinary wheelsだけを取得。診断のsocket差し替えによるssl import失敗は翻訳0件の時点で修正し、同じ入力/基準/modelのrun-02で測定した。初回ログを上書きしていない。全出力・意味判定・時間・hashは同private directoryのRESULT.md、audit.json、run-02/に保存。製品への翻訳provider接続は行わず、OPUS-MTの無条件採用は品質不足として保留する。試験依存は独立環境に置き、製品依存lockは変更していない。


### EXEC-103追加評価: 辞書未収録の商品句だけへ限定

2026-09-10、利用者の再評価指示。前回12商品句に対し、現行辞書の完全句lookup_contextualと実GiNZAで抽出した対象/修飾のlookup_productsを実行し、両方が正常に0件の場合だけ採用した。辞書エラー・構文失敗・未解釈の否定関係は未収録扱いにしない。前回のモデル出力/基準/採点のhashを固定し、モデル再実行や判定基準の変更をせず対象を再集計した。

評価完了。名刺入れ（JMdict1752260:1）とヘッドフォン（WordNet03261776-n）を登録済みとして除外し、残る10件は両照会とも0件。通常精度/INT8とも概念充足5/10（50%）。除外2件は正答1件と誤答1件だったため、元の6/12と割合は同じになった。名刺入れの誤訳は今回の不合格理由に含めない。

未収録の失敗は、モニター上の位置欠落、収納フック/収納かごの対象欠落、スリーブ→storage、コンセント用キャップ→filterの5件。自動翻訳の採用基準には未達。新規推論/外部通信/課金0、既知データの再集計であり独立holdoutではない。証拠は /home/products/bonsai-test-logs/20260910-opus-mt-unlisted-01/ のclassification.json、evaluation.json、RESULT.md。製品code/providerは変更していない。


### EXEC-103追加判断と実E2E準備（2026-09-10）

利用者が辞書未収録10商品句のOPUS-MT評価5/10（50%）を合格点として受け入れ、自然言語から画像生成を含む実E2Eを依頼した。観測値と過去の判定ログを変更せず、受入判断を更新する。精度の追加改善をE2E再開の前提にしない。OPUS-MTは単体試験環境にあり、現行candidate入口の翻訳providerには未接続である。今回の実行は既存の辞書/文脈選択とBonsai、Cloudflare、Outscraper、CLIP、SQLiteを用いるbackend E2Eとし、翻訳providerの置換を含めない。

状態は事前検査中。tools/candidate_search_live_e2e.pyの固定合成入力「マグカップ。丸みのある形。3000円以下。」を使う。辞書未収録経路の個別品質試験ではなく、現行入口の一連の接続試験である。検索候補提示・利用者選択、参考画像提示・了承、偽画像を含む最終画像/検索確認を維持する。4方向生成と未納品frontendは対象外。

実行範囲はlocalhost18080の既存Bonsai-8B最大2 POST・1 worker・認証なし、Cloudflare api.cloudflare.comのflux-2-klein-4bへ参考画像1枚と偽画像1枚（計2 POST・512px・参考入力511px）、Outscraper https://api.outscraper.cloud/amazon-productsへ1 query・1 task・Amazon.co.jp/ja/100-0001・最大24商品、同hostの結果取得最大50 polls・30秒間隔、m.media-amazon.comへ商品画像最大24 GET、ローカルCLIP最大7 batchesとする。Cloudflare各HTTP120秒、Outscraper各30秒、商品画像各10秒・8 MiB、CLIP各30秒、runner全体900秒（確認待ちを含む）、自動retry0。失敗・拒否・期限切れで停止し、所有Bonsai processを回収する。

公開公式料金を2026-09-10に再確認。Cloudflare入力tile0.000059 USD、出力tile0.000287 USDに基づき2出力+1入力で0.000633 USD。Outscraperは2 USD/1000商品で24件を見積もり0.048 USD、合計0.048633 USD。無料枠/実利用量は未照会、金額の強制上限はなく回数を制限する。既存のCloudflare API tokenとOutscraper API keyを用いるが、credential値を出力しない。今回の具体的な送信条件を提示した上で、AGENTS.mdの各live実行の承認規則に従う。

事前検査ログは /home/products/bonsai-test-logs/20260910-candidate-e2e-preflight-01/、実行先は未作成の /home/products/bonsai-test-logs/20260910-candidate-real-e2e-01/。private directory0700/files0600に生成PNG2枚・正規化plan/ranking/history・SQLite・応答件数/status/digestと時間を保存する。生の外部provider応答・credential・承認tokenをログへ出さない。既存DB/過去artifactを上書きしない。

受入は実providerで参考/偽画像生成、承認順序、候補取得、CLIP採点、ranking JSON復元、履歴一覧/詳細/参照画像画素の再読込一致、呼出し上限と所有process停止を確認する。画像内容と実順位の妥当性は実結果を目視/表示情報で別途判断する。事前のoffline成功を実E2E成功や未知商品全般の精度と扱わない。製品変更を予定しないためrollbackは不要で、試験失敗では今回の実行を停止し既存履歴を保持する。


事前検査完了。現行資材のhash/manifest、実GiNZA解析のローカル確認が成功し、関連offlineは89 passed（5.52秒）。診断scriptの初回はdataclassをPydantic形式で出力しようとして失敗し、asdictへ直して完了した。製品codeの不具合ではなくprovider call0。現在は今回の具体的送信条件の人間承認待ちで、実E2E未実行。実行コマンドを同private directoryのRUN.mdへ保存した。

### EXEC-103追加実装: OPUS-MT英訳の接続（2026-09-10）

状態: 実装中。利用者が未収録語5/10を合格とし、単体試験した変更の接続を指示した。正常な辞書候補0件からBonsaiが提案した日本語名について、原語と提案名をOPUS-MTで各1英訳にする。同じ句は1回だけ翻訳する。登録済み辞書の英訳とBonsai視覚抽出・単語一致/CLIP採点を維持する。英訳失敗時は日本語候補を保持し英訳をnullにし、別providerへfallbackしない。候補は人間確認後にだけ検索へ適用する。

既存のINT8資材と独立Python環境を指定する有界ローカルsubprocess adapterを追加し、candidate実CLIまで接続する。モデル/実行コード/要求/応答のdigestを分け、旧QueryExpansion JSONは追加metadataなしで読めるようにする。新構成は要求hashを変えるため旧候補cacheと共有しない。既存履歴・DBを移行/書換しない。外部取得・新たな翻訳API・委託UIは対象外。

実装前に未収録のみの翻訳、原語/言い換えの対応、失敗時の保持、辞書hit/エラー時の未呼出し、CLI接続と画像承認/CLIP/履歴までのfixture接続をREDにし、同じテストでGREENを確認する。関連回帰と全体offline、lint/format/文書検査を実行する。実OPUS-MTを既知の合成商品句でローカル検証し、品質の再採点とは分ける。ログは /home/products/bonsai-test-logs/20260910-opus-connection-01/。

先に提示した画像2 calls・検索1 taskの実E2Eは利用者の「はい」で承認済み。接続後に同じ固定合成入力と外部送信上限で再開し、検索語選択/画像承認では実結果を確認する。ローカル翻訳の追加は外部要求上限を増やさない。途中中断で実E2Eの出力先は未作成、Bonsai/pytest稼働processなしを確認した。取消時は翻訳CLI設定を外せば従来経路へ戻る。完了条件は接続と回帰成功、実E2Eの実到達段階を記録すること。


接続実装と検証完了。候補0件の場合に限りBonsaiの英訳をschemaでnullにし、日本語名と原語をOPUS-MTへ渡す。候補出典と翻訳出典を分け、原語と提案名の1訳対応、同一語の重複排除、翻訳失敗時の日本語維持、辞書hit/error/名称保留時の翻訳未呼出し、旧JSON読込、CLI設定と画像承認/CLIP/履歴のfixture接続を確認した。

関連90 passed、全体offline2928 passed / 20 skipped / 30 deselected（65.89秒）、Ruff check/format350 files・offline lock・文書リンク/diff成功。初回全体はテストへumask0077を継承し、権限fixtureのmkdir0755/0555を変えて10 failed / 2918 passedになった。ログは0077のまま、pytest subprocessだけ通常の0022に戻し、製品/既存テスト変更なしで全件成功した。

実OPUS-MTと実辞書/GiNZAはnetwork namespace分離で未収録3句を確認し、翻訳trace・英訳候補・JSON復元まで成功。Bonsaiはこのprobeでは名称fixtureであり、実Bonsaiや画像APIの成功とはしない。接続前の語句品質5/10という受入値を再採点していない。実E2Eは先の人間承認に基づき、翻訳設定付きの実CLIを開始した。検索語/画像の実確認を待って進める。


実E2Eは実Bonsai2 POST（語義選択と視覚条件）を終え、検索語選択待ちへ到達した。GiNZA 5.2.1/ja_ginza5.2.0とhotchpotch/japanese-reranker-xsmall-v2の量子化ONNXを現行資材から使用。マグカップは辞書語義wordnet:03797390-nをBonsaiが選び、辞書由来mugを含む候補を提示した。OPUS-MT/画像生成/Outscraperはこの段階で0 calls。人間の候補選択前に画像生成を進めていない。


利用者の再開指示後、同じ実行の元query「マグカップ」を保持して進行。追加の言い換え/英訳候補は適用しなかった。参考画像1枚がCloudflare HTTP200で生成でき、丸みのある胴体のマグカップを確認用に提示した。現在は参考画像の人間承認待ち。Bonsai累計2、Cloudflare累計1、Outscraper/OPUS-MT0、retry0。同じCLI processで確認待ちにしており、偽画像や実検索を先行実行していない。


参考画像への利用者の「はい」を受け、同じ実行で偽画像1枚を生成した。Cloudflare HTTP200、参考の丸い胴体に対して偽画像は角張った胴体となり、比較用の形状差を目視確認した。現在は2枚の画像と元query「マグカップ」の最終人間確認待ち。累計Bonsai2 POST、Cloudflare2 POST、Outscraper0、retry0。実検索・CLIPランキング・履歴再読込は承認後に進める。


最終画像/検索語への利用者の「はい」を受け、Outscraper1 taskを開始し8 pollsまで進行したが、候補取得中に停止した。確認待ちを含むrunner全体900秒上限と停止時刻が一致し、50 polls上限には達していない。summaryの固定codeはunexpectedで元例外型は保存されていないため、期限到達と整合する診断として記録する。画像2枚生成まで成功、商品画像/CLIP/ランキング/表示履歴は未実行。所有Bonsai/CLI停止、retry0、新規要求なし。OPUS-MT接続の実装とoffline検証は完了しているが、実E2E完走は未達。再検証には確認待ちと処理時間の上限設計の見直し、実行条件と追加費用の明示承認が必要。証拠は実行directoryのRESULT.md/summary.json/execution-audit.json。

### EXEC-103追加: 保存済み画像から検索だけ再実行（2026-09-10）

利用者が検索依頼段階からの再実行を明示した。終了済みprocessの状態を偽装せず、保存plan/実画像/消費済み画像承認を検証し、現在の再実行承認に基づく新しいcandidate検索を作る。画像の承認tokenを再消費せず、Bonsai/Cloudflare/OPUS-MT0回で新規Outscraper1 taskからCLIP/ランキング/新規SQLite履歴まで進む。検索開始から900秒、1 query/24商品/最大50 polls/30秒間隔、HTTP30秒、商品画像24 GET/10秒・8 MiB、CLIP最大7 batches/30秒、retry0。送信先api.outscraper.cloud/amazon-productsと同host結果URL、m.media-amazon.com。既存Outscraper API key、追加見積り0.048 USD・金額強制上限なし。再実行指示をこの範囲の承認として引き継ぎ、条件を通知してから実行する。

保存元のplan・2 PNG/metadata・承認DBをbounded readとdigestで固定し、owner/source/条件/reference digest/承認consumed時刻を照合する。保存planだけでは権限とせず、明示のhuman_confirmedと元plan digest/ownerを要求する再準備methodを作る。元の条件/query/推論出典は保ち、新しい15分の検索期限を付ける。旧DBはreadonly、新規出力先/履歴を使い、既存画像を再生成したとは記録しない。

実装前に再実行承認拒否・改変拒否・条件保持/期限更新・保存画像から検索/CLIP/履歴までのofflineテストを追加してRED/GREENを記録する。関連回帰、全体offline、lint/format/文書を検査後に実行。ログは /home/products/bonsai-test-logs/20260910-search-retry-prep-01/。元画像/承認は不変に保つ。外部API・キャッシュ形式・UIの変更はなく、追加入口を使わなければ従来動作へ戻る。完了条件は検索部分から実結果/履歴へ到達し、未到達なら失敗段階と回数を記録すること。

前回タスクは別途照会によりprovider Failureを確認。利用者が再度「検索の依頼から再実行せよ」と指示したため、保存一式のhashを固定し、新入口tools/candidate_search_retry.pyを実装した。元の7件のREDに対応するGREENに加え、現在の確認拒否・承認改変3件・provider失敗時のtask ID/status保持を検証した。全体offline2940 passed/20 skipped/30 deselected、73.35秒。lint/format/文書検査も成功。現在の検証・実行argv/時刻/終了状態の保存先は /home/products/bonsai-test-logs/20260910-search-retry-prep-02/。新規実検索の出力は /home/products/bonsai-test-logs/20260910-search-retry-live-01/。既存画像とplan・承認DBは変更せず、再実行の承認は今回の指示に基づく。

実検索再実行は完了。Outscraper1 task/12 pollsでSuccess、24商品/画像24枚、CLIP7 batches、ランキング/履歴保存と画像2枚の再読込まで391.621秒・exit0。Bonsai/Cloudflare0、追加retry0。画像スコアは全件unknown、単語一致を含む総合scoreは23件0であり、価格条件の並べ替えは確認できたが順位品質は未達。校正保留の詳細と英語商品名への語句一致が残る問題。実行完了を品質合格として扱わない。詳細はWORKLOG175。

画像unknownの原因診断は完了。同一Success応答のSHA256一致を確認した再評価でCLIP24件scored、全正のmargin分布を校正がinsufficient_diversityで拒否し全件unknownとなることを特定。数値入力のoffline再生でも一致した。製品規則は未変更。詳細はWORKLOG176、診断証拠は /home/products/bonsai-test-logs/20260910-image-unknown-diagnostic-01/。

### EXEC-103追加: 比較可能なスコアを保持する順位付け（2026-09-10）

利用者が総合score0の原因特定と、切り捨て基準を必要最小限にする修正を指示した。総合0は保存済み原語英訳がタイトル採点へ未接続であることと、校正保留による画像scoreの消失の組合せ。candidateのタイトル比較にはreadyな原語英訳だけを渡し、未承認の言い換えで検索を広げない。画像の相対順位は校正から切り離し、計算できる条件marginの最小値を0〜1に写す。候補1件・片側/同値の分布・比較できる条件が一部だけでも利用可能な値を保持する。数値が不正、画像不在、全条件が参照近接で比較不能の場合は保留を維持する。owner/承認/digest/URL/資源上限と、明示予算などの必須条件の優先順序は維持する。

新しいrelative画像contractとcandidate順位profileを追加し、旧校正評価/旧表示履歴の解釈を変えない。新順位には既存holdout accuracyを付けない。画像診断の数値入力・保存plan/titleだけでoffline再評価し、モデル/APIの追加呼出しなしで変更を検証する。RED→実装→GREEN→関連回帰/全体offline、lint/format/文書検査を行う。source/ログ/実行結果はrepository外のprivate directoryへ記録し、元E2E成果物は変更しない。完了条件は0点の原因を数値で再現し、実診断24件で画像score利用が回復すること、新旧履歴互換と不正入力拒否が保持されること。相対score改善を未知商品の品質合格とはしない。

完了。原語英訳のタイトル比較・relative画像順位・重複画素の埋込み再利用・新旧profile/履歴互換を実装した。全体offline2957件成功、lint/format/文書検査成功。元の表示履歴だけでは商品digestと保存marginの対応を復元できなかったため、条件を通知したうえで完了済み結果GET1回だけを追加し、元応答SHA256と商品digestを照合した。新規検索/画像取得/モデル推論0で24件を再計算し、画像available24件、総合0件数23→0を確認した。既存の必須条件順序・承認一式は不変。記録はWORKLOG177と /home/products/bonsai-test-logs/20260910-relative-ranking-01/。未知順位品質の合格とは別に扱う。


## EXEC-104: 属性別の画像比較と対象領域の分離

状態: 完了（実験経路の実装とoffline接続）。作成・更新: 2026-09-10。関連: EXEC-103、[BACKEND.md](BACKEND.md)、[DEVELOPMENT.md](DEVELOPMENT.md)。

目的は形状条件を色・背景・材質から分離し、輪郭比較をcandidateの承認済み画像評価から履歴まで接続すること。Bonsaiは視覚条件と比較部位の提案だけを行い、商品採点には使わない。3D生成・4視点生成・UI・新規実検索は対象外。

手順: (1) 条件に任意の比較対象を追加し旧JSON/hash互換を検証、(2) 対象領域抽出と縦横比を保持する輪郭比較を独立実装、(3) 新しい採点profileでcandidate/履歴へ接続、(4) 色・背景・位置・倍率への不変性と形状差への感度、失敗保留、旧履歴の回帰をofflineで検証。local領域抽出モデルの資材・環境はrepository外へ分離し、推論時のネット接続・自動ダウンロードを禁止する。モデルを使う場合はCPUを初期検証対象とし、iGPU性能は未測定として扱う。

受入条件: 同じ対象maskでは色や背景が変わっても形状score不変、縦横比を歪めず正規化、対象/参照領域が得られない条件だけ保留、他条件と価格優先順を維持、検索/画像承認・binding・旧履歴を迂回しない。合成maskの成功を自動切出し品質や実順位品質の証拠にしない。

検証はRED/GREENのコマンド・exit・test SHA256と全体offlineを保存する。ログはrepository外のprivate directoryへ保存し、商品本文・API生応答・credentialは含めない。旧profileは再採点しない。設定を外すとshape条件は保留になり、旧CLIPへ戻すには旧focusなし条件で新しいplan/画像確認を行う。既存の承認や履歴を変更してrollbackしない。

進捗: 対象部位の契約・確認への提示、別processの固定CLIPSeg、輪郭比較、candidate順位/SQLite履歴、失敗時の部分評価、旧JSON/hash互換を実装。検証結果はWORKLOG178とprivateログに記録する。実切出し品質・未知順位品質・iGPU性能の未達は[ISSUES.md](ISSUES.md#exec-104残課題-自動領域抽出の品質)へ残した。

発見事項: 最初のRED7件には未実装moduleのimport失敗6件が含まれ、順位品質の失敗再現とは扱わない。自然言語fixtureの不要な第二条件を除いて入力を修正し、接続入口未実装の4件と未観測形状が先に並ぶ1件もREDで確認した。後者は資格条件順を変えず、新profileだけ観測済み画像を先に並べることで修正した。全体CLIPは診断用に既存通り実行しており、形状だけの検索でその計算を省く最適化は未実施。

実モデル診断: 保存済み4画像/1対象のCPU切出しは5.762秒、起動wrapperを含め6.162秒、子process peak RSS927.3 MiB。実検索・画像生成・実Bonsai・iGPUは未実行。内部欠けと複数商品連結を目視したため、自動maskと実順位品質は未達。


## EXEC-105: MobileSAMによる個体分離と輪郭改善

状態: 完了（実験経路・固定画像比較・offline接続）。作成・更新: 2026-09-10。関連: EXEC-104、[切出し品質の課題](ISSUES.md#exec-104残課題-自動領域抽出の品質)。

目的はCLIPSegの意味領域とMobileSAMの輪郭候補を組み合わせ、内部欠けと複数商品の連結を減らすこと。実装・固定画像の比較・offline接続を対象とし、実Bonsai/商品検索/画像生成/委託UI/3Dは対象外。Bonsaiの商品採点は追加しない。

手順: (1) 公開MobileSAM資材/依存を別のlocal環境に固定、(2) 候補maskの選択・重複/連結の扱いを先にtest、(3) bounded workerと明示設定を既存領域抽出interfaceへ接続、(4) 以前の4画像について先に手動参考領域と合格基準を固定し旧CLIPSegと比較、(5) 全体offlineと静的gateを実行する。

受入条件は、一枚に複数商品があってもmaskをunionせず一つの対象として選ぶこと、対象部位が不明なら保留すること、参考領域に対するIoU/境界一致と混入を測り、平均IoU改善と各例の大きな劣化なしを確認すること。試験前に数値基準をprivate manifestへ固定する。手動参考領域は厳密な正解でなく評価者の近似であり、4例の改善を未知商品の合格としない。

資材取得だけネットを使い、推論はlocal-only/無credential/1 worker/CPU上限付き。画像・応答・数値と全検証logはrepository外private directoryへ記録し、生provider本文/秘密値は保存しない。runtime/profile hashを分け、既存履歴を再採点せず、設定を外せば旧CLIPSegへ戻る。iGPU性能は別途未検証として残す。

進捗: 任意抽出器とcandidate/履歴接続、17件の単体/接続test、固定4枚の実モデル比較まで完了。平均IoU0.7016→0.9467で事前基準を満たした。最終全体offline2997件成功、lint/format/lock/文書検査も成功。取っ手混入・順位品質・iGPUの未達はISSUESへ保持する。

## EXEC-106: 意味に対応した形状特徴の比較

状態: 完了（特徴比較・offline接続・開発評価）。作成: 2026-09-10。EXEC-105の切出し改善後も順位が逆転し、手動近似maskでも金属-0.2361、ガラス-0.4354で再現した。IoU全体の類似を特定の形状条件の充足へ読み替える問題を修正する。

対象は任意の測定種別を確認済みVisualFocusへ追加し、側面の膨らみ・滑らかさ・投影縦横比を個別採点する新profile、参考間の有効差の検証、数値証拠、candidate/履歴へのoffline接続。Bonsaiは測定種別の解釈提案だけで商品採点をしない。旧測定種別なしJSON/hash/profile/履歴は保持し、新条件は再確認を必要とする。表面の角張り・3D形状など輪郭で判定不能なものはunobservableとして当該条件だけ保留する。追加モデル/辞書依存・3D・実API・委託UIは対象外。

先に合成のdevelopment/未使用評価入力と順位基準を固定する。平行移動・倍率・色の影響、同じ対象で測定種別を替える場合、参照差不足、画像の欠測、改変と互換性をRED/GREENで確認する。最後に保存済み実モデルmaskと手動maskの診断、未使用の合成評価、全体offline・静的gateを実施する。合成成功を未知の実商品の合格にしない。記録はrepository外の20260910-shape-features-01へ全応答・argv・exit・hashを保存する。

結果: 新規14件、関連54件、全体offline3011 passed/20 skipped/30 deselected、71.69秒。合成48組は正順序48/48。保存済み2商品の側面の滑らかさ比較で逆転を解消し、差不足/逆方向の参照を保留した。実Bonsaiの測定種別判断・未知実商品の総合順位・実検索E2Eは未確認。詳細はWORKLOG180。

## EXEC-107: 保存済み24商品の総合順位を確認

状態: 完了（24商品の確認と診断）。作成: 2026-09-10。利用者の指示に基づき、同じ完了済みOutscraper結果1 GETと商品画像最大24 GETを行い、応答SHA256および24枚すべての画素SHA256が元データと一致することを確認した。新規検索・画像生成・Bonsaiは0回。既存キーを使った完了済み結果照会と公開画像取得の条件を実行前に通知し、同24商品の確認という今回の指示の範囲で実行した。

元の資格判定・タイトル単語点を保持し、側面の滑らかさ/higherを診断上で明示指定してローカルCLIPSeg＋MobileSAM/形状特徴を再計算する。元plan/承認/履歴は変更しない。価格適合19・未確定3・不適合2の順序を守り、候補確認済みの本番フローとは区別した診断結果を保存する。

新mask/scoreを見る前に、元画像だけから参考形への近さをアシスタントが3段階評価し固定した。独立専門家の正解ではない。品質基準は適合商品内の強い適合4件以上/非適合4件以上、上位5件中4件以上の強い適合、異なる目視grade間の正順序80%以上、画像採点75%以上。対象データが構成基準を満たさない場合はineligibleとし、指標の改善/悪化と合格資格を分ける。詳細ログ・全24順位・maskはrepository外の20260910-ranking24-01へ保存する。

結果: 応答/全24画像の一致、旧総合点/順位の再現、新形状評価/全24順位を確認した。目視順位一致43.2%→36.9%、nDCG@10 0.365→0.336で悪化。原因は直線も高くなる滑らかさ指標と、微小分離片による3件の形状保留。品質未達はISSUESに保持する。詳細はWORKLOG181。


## EXEC-108: 膨らみ測定の精度と追加時間をオフライン比較

状態: 完了（オフライン比較。既存採点経路の改善は未達）。作成・更新: 2026-09-10。目的は保存済み24商品の側面の膨らみを測り、EXEC-107の滑らかさによる順位から改善するかを検証すること。既知developmentデータであり、独立holdout合格とは扱わない。

対象はrepository外の数値実験と結果文書。固定maskの微小孤立片除去、中心軸補正、左右輪郭の基準線からの張り出しを計算する。production module、既存承認・履歴、provider、委託UIは変更しない。外部通信・credential・画像生成・モデル再推論は0回。戻す場合は実験を採用しないだけで旧経路を維持できる。

手順: (1) 既存mask/目視label/sourceのSHA256と評価式・改善基準を固定、(2) 合成形状で数値処理の特性を確認、(3) 同24商品を一度評価し、参照guardを保持した総合順位と測定値単体の識別力を区別、(4) 26maskの追加処理時間を21回測定し、全数値・順位・実行結果を記録する。参照差不足を回避するために評価式や判定方向を後から変更しない。

比較改善は順位一致率5ポイント以上、nDCG@10と上位5件の強適合数が低下しないこと、採点率75%以上。既存の正式合格基準は別途維持し、強適合3件しかない構成不足を許容品質に読み替えない。詳細と全出力は /home/products/bonsai-test-logs/20260910-bulge-eval-01/ に保存する。未確認は未知実商品・実Bonsaiの意味選択・参考画像再生成・本番iGPU性能。

結果: 新しい膨らみ量を使う診断では順位一致36.9%→85.6%、nDCG@10 0.336→0.933、明瞭な膨らみ3商品が上位3位となった。参考画像との膨らみ分布だけを比較する別診断でも84.2%、上位3件を確認した。一方、既存の参照差検査を保持すると差0.0123が0.02未満で24件すべて保留し、総合順位改善は未達。0.02は新指標の誤差から校正した値ではなく、今回その引下げはしない。新方式は実験用に留め、参照対の有効性・測定誤差と閾値の校正・独立評価をISSUESへ残す。

検証: 合成13件と既存関連54件の計67件成功。全4方式の24件性・元資格順序・総合点・順位一致率・固定hashを再検算。26maskの追加計算時間中央値0.149秒（21回）。production code不変の数値実験なので全体pytestは再実行せず、関連testと文書gateを実施した。詳細は[WORKLOG182](WORKLOG.md#182-膨らみ測定の識別力と追加時間をオフライン検証2026-09-10)。


## EXEC-109: 膨らみ参照差の閾値を検証

状態: 完了（閾値検証。productionへの引下げは不採用）。作成・更新: 2026-09-10。EXEC-108の実験用膨らみ測定器を固定し、既存0.02と測定揺れに基づく閾値候補を比較する。目的は閾値を下げてよい根拠の有無を明確にすることで、特定商品を上位にする値の探索は行わない。

対象はrepository外のoffline数値試験と文書。48合成形状を校正、別パラメータの48形状を検証とし、各20変形（傾き±3度、倍率0.9/1.1、境界±1/2px、最大2pxの平滑ノイズ）を固定seedで生成する。校正の絶対誤差99percentileの2倍を候補閾値とする。商品score/目視label/既存参照差は校正に使用しない。未知実商品や実モデル誤差の分布とは区別する。

手順: 入力/実装/policyをhash固定、校正値を別artifactへ固定、別seedの同形状と明瞭な膨らみ差で検証、現在の参考対と24商品の摂動感度/順位への影響を診断、全数値・argv/exit・検算結果を保存する。検証基準は測定取得95%以上、同形状の誤分離1%以下、既知差の正方向検出90%以上。参考対は名目差だけでなく変形後の最小交差差が閾値以上であるかも確認する。

外部通信/credential/モデル推論/画像生成/検索/委託UIは0回。production code・既存閾値・承認・履歴は変更しない。rollbackは実験を採用しないことで完了する。ログ先は /home/products/bonsai-test-logs/20260910-bulge-threshold-01/。残る未確認は実モデルの切出し誤差、意味の妥当性、未知商品とiGPU性能。

結果: 校正960観測の誤差99percentileは0.005318で、候補閾値0.010636を固定した。別パラメータ48形状で同形状誤分離1/9120組（0.011%）、既知差検出960/960、取得960/960となり、合成の事前基準は通過した。既存0.02も明瞭な差の検証基準を満たすため、一般に厳しすぎることを示す結果ではない。

現在の参考対は名目差0.012277で候補閾値を超えるが、20変形ずつの最小交差差は0.005680で不合格。大小方向は400/400で保持し、閾値通過は233/400。名目差だけなら24商品採点・順位一致67.6%だが、安定性を要求すると採点保留になるため、閾値だけを下げる変更は採用しない。人工変形の組合せを本番成功確率とは扱わない。

合成/関連74件成功、校正値・誤分離・参考400組・全24順位・総合点・hashを別scriptで検算した。production不変のため全体pytestは再実行せず、関連testと文書gateを確認。詳細は[WORKLOG183](WORKLOG.md#183-膨らみ参照差の閾値を校正検証2026-09-10)。参照対の改善と実切出し誤差による検証はISSUESへ残す。


## EXEC-110: 膨らみの参照画像生成と採用前検査を改善

状態: 実装・offline検証と承認済み偽画像1件の実生成・参照検査を完了。作成・更新: 2026-09-10。EXEC109で候補閾値の引下げだけでは参照差が安定しないことを確認した。原因は偽画像が表面を角張らせても胴体の膨らみを残すことである。確認済みside_bulgeの希望方向から、参考/偽画像の左右輪郭の膨らみと直線を指定し、別部位・表面の角張りによる代用を防ぐ。

対象は生成prompt、独立した膨らみ参照検査、candidateでの画像承認発行前の接続、offline回帰。測定器はEXEC108の双方向張り出しを基にするが、商品rankingのprofileは変更しない。既存閾値0.02を維持し、参考maskの小変動後の最小差でも希望方向を満たすか確認する。検査不能/差不足なら新しい画像承認を発行せず、生成済み利用量を成功として維持して再確認へ戻せる状態にする。

手順: 生成内容と不適切な参照の早期検出をREDで確認し、最小実装、関連test、保存済み参照/合成参照で比較、全体offlineと静的gate。新prompt契約をversion/digestで区別し、旧承認・履歴を新要求へ流用しない。現在の実画像の改善は再生成で別途確認が必要であり、合成参照の成功とは区別する。

ログは /home/products/bonsai-test-logs/20260910-reference-improvement-01/。credential/live送信・画像再生成の前には具体的な要求を完成させて範囲を提示する。委託UI、4方向/3D生成、商品LLM採点は対象外。rollbackは新実行を止め、保存済み履歴を保持する。

実装結果: prompt v2、参照用の双方向膨らみ測定器、各参照20変形の最小差0.02を確認する検査、candidateの最終承認発行前の停止、live runnerの安全な数値診断を接続した。既存のrank/history profileは変更せず、画像要求に新しいprompt/参照品質policyのbindingを含める。

検証結果: 新規10件、最終全体offline3021 passed/20 skipped/30 deselected、99.37秒。既存の不正参照の接続testは検索後の保留から検索前の停止へ期待を変更し、正常参照の順位/履歴を維持した。旧参照対の最小差0.005028は不合格、元の参考maskと合成の直線側面maskでは0.032108で通過した。これは理想的な輪郭の数値検証で、実画像の再生成成功ではない。

既存の承認済み参考画像から偽画像だけを1回生成する要求をprivate prepared-request.jsonへ完成させた。送信先はCloudflare flux-2-klein-4b、出力512px、既存APIキー、retry0、180秒上限、想定0.000346 USD、検索0回。実行条件を示して承認を求めた。承認後に固定CLIPSeg＋MobileSAMで参照2枚を切り出し、同じ判定器で検証した。元の承認・履歴を新生成の完了結果として書き換えない。

承認後の実行結果: Cloudflareへ偽画像1件を送信し、7.715秒で生成成功。再試行0・検索0。固定ローカルCLIPSeg＋MobileSAMによる2枚の切出しと検査は48.444秒、子process peak 1.329 GiB。名目差0.027957、各20変形と元maskを含む全441組の最小差0.024392で、既存0.02基準を通過した。旧対の最小差0.005028から改善した。目視でも側面の膨らみが減少し、取っ手を除いた本体maskを確認した。参考対1件の診断成功であり、全24商品の総合順位・実検索E2E・未知画像・iGPU性能は未検証。詳細は[WORKLOG185](WORKLOG.md#185-承認済み偽画像1枚を実生成し参照品質を検証2026-09-10)。

## EXEC-111: 新偽画像による全24商品のランキング改善を検証

状態: offline比較・検算完了。作成・更新: 2026-09-10。目的はEXEC110の参照差改善が商品順位改善につながるかを確認すること。保存済み24商品のmask・資格条件・単語点・EXEC107目視gradeを固定し、旧/新偽画像を現行side_bulge測定と実験用の双方向膨らみ測定で比較する。旧smoothness結果と新参照でのsmoothnessも診断する。測定種別は診断上の明示指定で、実Bonsaiの解釈確認とは扱わない。

閾値0.02、資格順序、単語80%・画像20%、保留時の単語点を維持し、点数を見て調整しない。比較基準は既存の順位一致5pt以上改善・nDCG非低下・top5明瞭適合数非低下・画像採点75%以上。正式基準は強適合4件以上を維持し、この集合の3件だけでは合格にしない。旧参照が採用前検査を通らない場合の順位は数値診断だけと明記する。

対象はrepository外のoffline数値再生・検算と文書。production code・既存承認・履歴は変更せず、追加API/画像生成/検索/モデル推論/credential/委託UIは0回。手順は入力とpolicyのSHA256固定、全件再計算、旧結果の再現、独立算術検算、関連test・文書gate、全24件のIDと数値の保存。失敗試行も保存する。ログは /home/products/bonsai-test-logs/20260910-new-reference-ranking-01/。rollbackは診断を採用しないことで完了する。未知商品とiGPUの評価は対象外。

結果: 現行side_bulgeは旧参照の全件保留から新参照で21/24件採点となり、順位一致47.3%→63.1%、nDCG0.290→0.582、top5強適合0→2。改良した双方向測定では24/24件採点、順位一致79.7%、nDCG0.859、強適合3件が上位3位となった。両方とも既存の比較改善基準を満たすが、滑らかさを維持するとnDCG0.336→0.242で不合格。正式判定は強適合3件で母数不足、改良測定の一致率も80%未満。商品rankingへの改良測定接続は行っていない。全6方式144件を別scriptで検算、関連53 test成功、追加API/モデル推論0回。詳細は[WORKLOG186](WORKLOG.md#186-新偽画像で全24商品の順位を比較2026-09-10)。

## EXEC-112: 未使用商品の膨らみ順位を固定基準で検証

状態: 承認済み取得・実ローカルモデル評価完了、正式評価は構成不適格。作成・更新: 2026-09-10。EXEC111の既知24件で見られた改善が、別の商品でも成立するか確認する。手元のcase1〜3、image-holdout001〜005と直近の24件は使用済みであり、新しいholdoutへ転用しない。新しい検索語「コーヒーカップ」で最大24件を1回取得し、価格3000円以下を既存規則で評価する。膨らみを取得queryへ含めず、旧24件と同一の商品ID・URL・画像および近似画像を除く。未知とはこの開発集合との非重複であり、基盤モデルの未学習を保証しない。

実行前に現行/改良膨らみ測定・新しい参照対・閾値0.02・単語80%/画像20%・資格順序・同点半点の比較基準をhash固定する。画像を見てgrade2=明瞭な両側膨らみ、1=弱い曲がり/テーパー、0=直線的、判定不能を採点前に固定する。形状に基づく追加選別や追加検索は行わず、強適合4件・非強適合4件未満は構成不適格として報告する。順位一致80%以上、上位5件中強適合4件以上、画像採点75%以上を維持し、取得/切出し失敗を隠さない。目視ラベルはassistantによるもので独立した人間の正解とは扱わない。

対象はrepository外の新規取得runner・固定評価・offline fixtureと文書。新規Outscraper1task・最大50polls・各30秒間隔・HTTP30秒、取得全体1800秒、m.media-amazon.com画像最大24GET・retry0。既存Outscraper API key利用、無料枠を適用しない見積り0.048 USD（公式2USD/1000商品、2026-09-10確認）。画像生成/Bonsai/追加モデル取得/委託UIは0回。画像と匿名ID・数値・digest・安全な状態だけ保存し、rawprovider応答・商品本文・URL・ASIN・credentialを保存しない。既存承認・履歴・production codeは変更しない。

手順は要求/基準固定、送信回数と重複除外のoffline test、具体的範囲への人間承認、1回取得、採点前の目視label固定、CPUの固定CLIPSeg＋MobileSAM、現行/改良測定の比較、独立算術検算、全件結果保存。取得失敗や母数不足でも自動再検索しない。rollbackは診断の採用を見送ること。ログ先 /home/products/bonsai-test-logs/20260910-unseen-ranking-01/。新規取得の承認前にcredentialを読まず外部要求を開始しない。

準備結果: prepared-request.jsonとpolicy.json、旧24商品のidentity digest24件・画素digest26件を固定した。単発取得・重複除外・再送拒否・安全な失敗・要求改変拒否のoffline3 testが1.10秒で成功。sourceと参照をSHA256固定し、credential利用前に照合する。開始marker未作成、実商品新規取得・credential・model推論0回。具体的な送信条件を利用者に示し、承認後に取得と目視label固定へ進む。未知商品精度はまだ測定していない。

承認後の結果: Outscraper1task・6pollsで24件を取得し、画像21GET。既存と同一の商品3件と目視近似重複1件を除き20件を採点前に固定した。目視gradeは強適合0・弱い曲がり/テーパー11・直線6・判断不能3で、強適合4件という構成基準を満たさない。現行/改良とも17/20件を採点できた。価格適合7件内の異grade6組は8.3%→66.7%、価格を問わない画像比較66組（欠測不正解）は37.1%→65.9%。強い膨らみの順位品質を確認した結果とはしない。

新しい失敗例として上面のコーヒー部分を本体と誤抽出し、楕円maskに画像点1.0を付けた。取っ手を含む直線本体は改良測定で減点できたが、部位の取り違えと分離片による保留が残る。単語一致点全件0、価格不明10件という別の制約もあり、未知商品での合格は未確認。取得191.699秒、20画像のローカル切出し・参照検査・採点290.221秒、子process peak約1.352GiB。全数値/順序/hashと取得上限を独立scriptで検算した。追加生成・再検索・再調整は行わず、データは今後developmentとして扱う。詳細は[WORKLOG188](WORKLOG.md#188-未使用20商品の実画像で膨らみ評価を検証2026-09-10)。


## EXEC-113: 汎用の外観類似度へ切り替え、保存済みカップ画像を再評価

状態: 実装・保存済み画像再評価・全gate完了。未知カテゴリと形状順位の品質合格は未確認。作成・更新: 2026-09-10。利用者の指示により、未知カテゴリでの処理範囲を優先し、専用形状測定を必須としない画像採点をcandidate既定へ接続する。画像点は全体の外観類似度で、部位・寸法・属性の充足確率ではない。

対象: 汎用画像profile、candidate完了/生成確認/履歴、Bonsai視覚条件prompt、offline回帰、既存実画像のローカルCLIP再推論。対象外: 外部検索/画像生成/credential/新モデル取得/委託UI/commit/push。検索語確認、参考画像確認、偽画像確認、価格条件、単語80%・画像20%と画像欠測時の単語点は維持する。

手順: 変更前snapshotを保存、カテゴリやmeasureに依存しない採点・承認・履歴のRED、新profileと明示的旧方式の互換実装、GREEN/全体offline/静的gate、保存済み直近20商品と旧24商品の再採点、数値検算、文書同期。専用測定と部位抽出は既定で呼ばず、旧方式の明示選択を残す。参照近接時は該当比較を保留し、商品を除外しない。全体画像の点を部位の一致と表現しない。

固定比較: EXEC110の参考/新偽画像、EXEC112の20件とEXEC107の24件をそれぞれ全件使用。既存grade・資格・単語点・対比較の同点半点を維持し、結果に基づく閾値/重み調整や再ラベルを行わない。採点率・形状gradeとの順位一致・nDCG・全件点数・CPU所要時間を報告する。既知development画像であり未知カテゴリ精度の合格とはしない。旧集合の強適合3件、新集合0件の構成不足を維持する。

保存先: /home/products/bonsai-test-logs/20260910-appearance-ranking-01/。入力とコードのSHA256、全数値応答、RED/GREEN、失敗試行、argv/exit、時間を保存し、生provider応答/商品本文/ASIN/URL/機密値は出力しない。新方式のprofile/hashで旧採点と区別し、既存履歴/承認を書き換えない。rollbackは明示的旧方式の選択または今回snapshotから対象差分だけ復元。未確認は未知カテゴリ精度、部位一致、iGPU性能、実サービスE2E。


EXEC-113の実装/検証結果: appearance-image-v1 / candidate-appearance-v1 / counterfactual-appearance-v1とwhole_image_similarityを接続した。既定はBonsai測定選択・参照輪郭検査・商品部位抽出を呼ばない。旧方式は明示選択へ移し、旧結果/履歴とJSONのbindingを保持する。新規7件、関連109件、全体3026件（追加2件導入前）と追加を含む関連24件が成功。全体初回は旧方式指定を欠いたMobileSAM接続1件が失敗し、明示選択へ修正して通過した。

実ローカルCLIP再評価: 直近20件は画像採点17→20、以前24件は21→24となった。画像点のみと既存形状gradeの順位一致は直近37.1%→56.1%（66対）、以前59.4%→30.4%（171対）。価格適合群では直近8.3%→91.7%（6対のみ）、以前63.1%→24.3%（111対）。以前の強膨らみ3件は9/14/15位へ下がり、微小な低下とはいえない。専用の改良両側測定との比較もprivate RESULT.mdへ全件記録した。

事前入力準備の初回はsets階層の誤りで0件だった。実推論0回の出力を保存し、件数assert追加後に44件を実行。以後の再調整/再ラベルなし。固定ONNX CPU1thread、20+2画像21.914秒、24+2画像23.599秒、合計13batch。画像点・総合点・資格順・全埋込み/参照差・入力/code/label hashを独立scriptで検算した。全体testと同時の計測で、単独速度ベンチマークではない。未知カテゴリや膨らみ品質は合格未確認。利用者指定の汎用採点仕様として実装し、専用形状の品質改善とは報告しない。

EXEC-113最終gate: Ruff check、全369 fileのformat check、offline lock、Markdown16文書/1655 local links、git diff --checkがすべて成功。実装と依頼された再採点を完了し、品質低下と未知カテゴリ評価は未解決事項として保持する。


## EXEC-114: SigLIP 2の実ローカル画像比較を試す

状態: 実モデル試験・独立検算・文書gate完了。画像参照方式は比較改善、正式品質は構成不適格。作成・更新: 2026-09-10。利用者の「SigLIP 2を試せ」に基づき、google/siglip2-base-patch16-224を固定revision 75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2で取得し、既存44商品に対するCLIP結果と比較する。これは試験でありcandidateの本番model/providerは変更しない。

対象はrepository外の公開model資材・ローカル推論runner・数値比較と文書。既存mobile-sam-eval-01のtorch2.6.0+cpu/transformers4.57.6環境を使い、依存の追加や既存環境の変更はしない。公開Hugging Face/配信CDNから約1.54GBを認証なしで取得する環境準備と、取得後の通信禁止推論を分けて記録する。商品画像/検索文/credentialを外部へ送らない。有料API/新規検索/画像生成/商品画像GET/委託UI/commit/pushは対象外。

比較はEXEC113の20/24商品、同じ参考/新偽画像、既存grade/資格/単語点を固定する。画像参照とのcosine差、肯定/対照の英語条件文とのcosine差の2方式を分ける。テキストは事前policyへ固定し、結果を見た調整や混合重み探索は行わない。領域切出しは加えず、まずmodelと比較基準の差を評価する。画像点は確率ではない。参照距離で差を正規化して[-1,1]へclampし[0,1]へ写す診断上の共通式を使う。

手順: 資材SHA256/入力/policy固定、数値fixtureで形状/正規化/欠測/改変を検証、CPU2threads・batch4・最大600秒で実モデルを1回評価、全埋込み/数値/時間/RSS/失敗試行を保存、独立検算、文書/関連gate。比較改善の基準は各集合の画像対比較+5pt以上、nDCG/上位5強例数非低下、採点75%以上。強例0/3件の構成不足を保持し未知カテゴリ合格とはしない。ローカルCPUの速度をiGPU値としない。

保存先は /home/products/bonsai-test-logs/20260910-siglip2-ranking-01/。製品コードと既存履歴/承認は不変、rollbackはこの試験を採用しないこと。未確認はモデル実行互換性、比較精度、iGPU資源、未知カテゴリ品質。公開資材取得は今回の明示的モデル試用に必要な環境準備として実施し、推論APIは呼ばない。


EXEC-114結果: 固定revisionの7資材1,539,453,393bytesを認証なしで取得し公式model SHA256と照合した。既存環境のGemmaTokenizerFast/SiglipImageProcessorで動作し、依存追加なし。46画像（44商品+参照2）/12batchと固定条件文2件を通信禁止で実推論した。production code/model/履歴の変更はない。

画像参照方式はCLIPに対し画像点の形状順位一致が直近56.1%→65.2%（66対）、以前30.4%→63.7%（171対）、各集合+5pt等の比較改善基準を通過。価格適合群は91.7%→91.7%（6対）と24.3%→57.2%（111対）、nDCGは0.993→1.000と0.151→0.718。以前の強膨らみ3例は1/4/9位。条件文方式は直近48.5%/以前68.4%の画像順位一致で、直近悪化のため両集合通過はしなかった。採点後の条件文/閾値/重みの修正なし。

CPU2threads/float32、読込2.506秒、画像14.842秒、文0.319秒、process全体25.410秒、peak1.419GiB。CLIPはCPU1thread/ONNX/別session・異なる前処理であり純粋なモデル速度比較としない。SigLIPは公式resize前処理なので、モデルと前処理のセットの比較である。7数値fixtureと23既存関連test成功、全88点の埋込み・参照差・順位・指標・hashを別scriptで検算した。対象は既知カップ類、強例0/3件で正式品質はineligible、未知カテゴリ/iGPU/production接続は未検証。詳細は[WORKLOG190](WORKLOG.md#190-siglip-2を保存済み44商品で実ローカル検証2026-09-10)。

EXEC-114最終gate: 数値fixture7件、既存関連23件、全88採点の独立検算、Markdown16文書/1657 local linksとgit diff --checkが成功。モデル試用と比較報告を完了し、production接続・未知カテゴリ/iGPU評価は未実施として残す。


## EXEC-115: SigLIP 2を未知商品で目視順位と比較する

状態: 完了（未知商品21件で75.8%、指定60%を達成）。作成・更新: 2026-09-11。利用者指定の成功基準は目視順位との一致度60%以上。関連: [EXEC-114](#exec-114-siglip-2の実ローカル画像比較を試す)、[ISSUES](ISSUES.md)。既存の44商品はdevelopmentとして除外し、まず同じカップ条件の未評価商品を対象とする。未知カテゴリやモデル学習データとの独立性は主張しない。

対象: repository外の20260911-siglip2-unseen-01で取得・重複除外・目視固定・実ローカルSigLIP 2・検算。本番code/model/履歴、委託UI、画像生成、Bonsai、commit/pushは対象外。既存承認済み正画像/偽画像、EXEC114の固定model/revision/公式前処理と採点式を維持する。

評価: モデル点数を開く前にassistantが胴体の外向き曲線の強さで順位と同順位群を固定する。色・材質・背景・取っ手を目視基準に含めない。人間の独立評価とは区別する。異なる目視順位の商品ペアを分母にし、画像点が同じ順序になった数を分子にする。モデル同点/欠測は不正解、目視同順位/判別不能は比較不能として件数を報告。60%以上でこの試験を成功とし、旧80%/強適合4件基準は流用しない。ただし目視可能12件/比較30対に満たない場合は資料不足で判定保留。raw差や総合順位を成功判定の救済へ使わない。

手順: 取得前にpolicy/model/参照/既知画像hash/取得codeを固定し、fake transportと数値試験を行う。外部取得の明示承認後、固定合成検索1件・24商品まで・最大50polls・画像GET24件・retry0・全体1800秒で取得する。既知商品hash/pixel/pHash距離5以下と目視同一商品を除き、新規同一商品は先着1件。形状/価格による選別や成功するまでの再検索をしない。目視labelsと画像をhash固定後、通信禁止CPU2threads/batch4/600秒以内のSigLIP 2を1回実行。全埋込み・匿名順位・時間・RSS・失敗を記録して別計算で検算する。

外部境界: https://api.outscraper.cloud/amazon-products と同providerのtask取得、Amazon画像host m.media-amazon.com。固定合成検索「マグカップ ガラス」、amazon.co.jp/ja/100-0001。既存Outscraper API keyを使用し値を表示しない。公式2 USD/1000商品を当日確認、24商品0.048 USD見積り、課金額の強制capなし。回数/件数上限で制限する。AGENTS/DEVELOPMENTの実行ごとの明示承認後だけ実行する。

保存: private directoryの画像、匿名hash、数値、評価者種別、policy/labels/script/model digest、実行ログ。商品本文/ASIN/URL/生provider応答/credentialは保存しない。前回snapshotを変更しない。rollbackは試験を採用しないこと。準備時点では新規商品未取得・精度未判定だった。取得承認後に固定manifest確認とacquire.py --execute-approvedを実行し、結果は下記へ記録した。

EXEC-115準備結果: private取得/重複除外/目視対比較/画像専用推論runnerを作成。取得fixture3件・一致度fixture8件の計11件が0.88秒で成功。155既知画像の比較基準と過去商品identity/pixel除外を固定した。構文確認成功。外部取得・実SigLIP推論は未実行。新たな外部取得は実行範囲への明示承認待ち。再開方法はprivate PREPARED.mdに記録。品質結果が出るまでこのPlanを完了扱いにしない。

EXEC-115完了結果（2026-09-11）: 利用者の当該取得承認後、1task/4pollsで24商品、既知重複2件を除いて22画像を取得した。目視同一画像1件を追加除外し21商品を評価。モデル点を見る前に6つの目視同順位群を固定し、全210組中、目視同点82組を除いた128組で比較した。97組一致、31組逆転、モデル同点/欠測0で75.8%。事前の60%と資料12商品/30組を満たし、この試験は成功。目視はassistant評価であり独立人間評価ではない。

初回workerは通信遮断のためsocketクラスを関数へ置換した結果、torch経由のssl importでTypeErrorになり、モデル読込・埋込み前に失敗。初回を保持し、別inference-02でconnect/connect_ex遮断へ修正した。import成功/3経路遮断を確認して同じ固定ラベル・参照・採点式で実行した。実モデル採点が完了した試行は1回、再検索/再ラベル/チューニングなし。23画像7.340秒、process15.399秒、CPU2threads、peak1.417GiB。取得125.361秒。

全21点・順位・128対・raw差と固定hashを別scriptで検算して一致。全応答・初回失敗・修正・画像/label/モデルdigestと全順位をprivate RESULT.mdへ保存。未確認事項は未知カテゴリ、独立人間評価、iGPU性能、本番総合順位。これらは[ISSUES](ISSUES.md)へ継続し、今回の未知商品試験自体は完了。本番code/model/履歴と委託UIは変更していない。


## EXEC-116: 候補検索の画像評価へSigLIP 2を組み込む

状態: 実装・接続回帰完了。作成・更新: 2026-09-11。利用者の本番組み込み指示に基づき、EXEC115で目視順位一致75.8%を確認したSigLIP 2参考画像方式をcandidate既定へ接続する。関連: [EXEC-115](#exec-115-siglip-2を未知商品で目視順位と比較する)、[BACKEND](BACKEND.md)、[DB-SCHEMA](DB-SCHEMA.md)。

対象: 固定資材manifest、768次元実ローカルencoder/別環境worker、承認参照との採点、candidate既定・CLI選択・新profile履歴、offline回帰と保存済み画像の実adapter検証。対象外: 委託UI、外部APIの新規実行、モデル/依存download、未知カテゴリ品質、iGPU性能、commit/push。実行環境は準備済みCPU2threadsの外部Python環境で、通常依存へtorchを追加しない。

仕様: siglip2_appearanceをcandidate既定にし、appearance/relativeのCLIPは明示選択時のみ保持する。失敗時にCLIPへ自動fallbackしない。正画像・偽画像の順と画像承認を保持し、条件ごとの差を正規化して最低点を採用する。単条件の式/前処理はEXEC115と一致。複数条件は既存のminimum-positiveによる条件集約契約を維持する。タイトル80%/画像20%、資格条件優先、欠測時の単語点を保持。

互換性: 新768次元/runtime/profileで512次元CLIPを拒否する。model/revision/資材/前処理/worker契約をruntime digestへ含め、旧cacheと共有しない。旧history/承認を上書きせず、新規modeが承認digestへ含まれる既存契約を使う。DB物理schema5を維持し、新ranking/profileの組を追加する。

手順: snapshot/RED、新adapterと境界/既定を実装、GREENと関連回帰、全体offline、Ruff/format/lock/Markdown/diff、保存済み画像の実adapter再現と履歴接続、文書更新。実検証は既知画像の接続回帰で、未知精度の再測定としない。private evidenceは20260911-siglip2-integration-01へ保存。外部応答/商品本文/ASIN/URL/credentialは複製しない。

rollback: 明示CLIP設定へ戻すか今回のbefore snapshotから対象差分だけ復元する。既存の大量の未commit差分を保持し、checkout全体をresetしない。未確認は実装互換性と回帰結果。完了時に確認結果と残る性能/品質境界を記録する。


EXEC-116結果: candidate既定をsiglip2_appearanceへ接続し、独立768次元adapter/runtime、新ranking/profile、画像承認、JSON復元とSQLite履歴を確認した。旧CLIPは明示設定で保持し、失敗時の自動fallbackはない。全体offlineは3045 passed/20 skipped/30 deselected（122.06秒）、最終関連26件成功。資材読取によるatime更新を改変と誤判定しない回帰を追加し、内容hashと変更検知を保持した。保存済み21商品を本番adapterで再採点し、全点の試験値との差0.0、順位完全一致。実推論31.127秒、子process peak803200KiB、CPU2threads、encoder呼出し2回。全体test同時の計測で単独速度比較ではない。新外部API実行0回、委託UI/iGPU/未知カテゴリは未検証。詳細は[WORKLOG193](WORKLOG.md#193-candidateの既定画像評価へsiglip-2を接続2026-09-11)。

## EXEC-117: React + StyleXのオフライン画面

状態: 完了。作成・更新: 2026-09-11。担当: Codex。期限: 未定。

目的: 任意の自然文入力から、固定デモ条件の確認、任意の参考画像・比較画像の確認、最終確認、5工程の商品調査、結果・履歴までをデスクトップで操作できるようにする。[TASK-008](#task-008-次期検索フロー-v2-の実装)、[視覚契約](FRONTEND.md#13-次期uiの視覚統一契約)、UI-017〜UI-020に対応する。

対象は新設する `frontend/` のReact + TypeScript + StyleX、ローカルの合成画像・Noto Sans JP、純粋な状態遷移と固定データ、ブラウザ内のモック履歴、関連文書。Figmaのnode 59:22を構成参考として確認し、今回の白黒・青・灰色の指定を優先する。Viteと公式StyleX unpluginを使い、共通ボタンは幅176px・高さ48pxとする。公開npm依存と必要なブラウザの取得は利用者承認済みの環境準備。実バックエンド・Bonsai・外部API・認証情報・実商品検索、commit/pushは対象外。

現状: フロントエンドのpackageとソースは存在しない。Python経路を変更せず独立して作成する。通常検索とモックで共有できる表示部品へ固定データを渡すが、本作業では実サービスadapterを設けない。

- [x] 規則、Figmaの構成、正本仕様、Node.js 22の環境を確認。
- [x] 意図した状態遷移のREDを確認し、同じテストをGREENにする。
- [x] 共通部品と全画面、ローカル資材、履歴と回復操作を実装。
- [x] TypeScript、単体テスト、production build、実Chromiumで両経路・操作・配色・外部通信遮断を検証。
- [x] Python既存offline gate、文書リンク、差分を確認し、実装事実と残作業を同期。

検証は `frontend/` で `npm test`、`npm run build`、`npm run test:e2e`、repository rootで標準offline gateと `git diff --check`。RED/GREENの理由・コマンド・test hashと最終件数は本節へ追記する。ブラウザには合成入力のみ使い、実利用者入力やcredentialをログへ残さない。

rollback: この作業で追加した `frontend/` と関連文書の差分だけを取り消す。既存Python実装・cache・モデル資材を変更しない。失敗時は同じ画面で回復でき、実サービスへfallbackしない。


EXEC-117検証記録（2026-09-11）:

- `cd frontend && npm run check`: 成功。strict TypeScript（未使用宣言も検査）とPrettier。
- `cd frontend && npm test`: 成功、40件（状態遷移20件、履歴20件）。
- `cd frontend && npm run build`: 成功。StyleXのCSS事前生成とローカルフォント・画像を含むproduction build。
- `cd frontend && npm run test:e2e`: 成功、18件、18.4秒。Chromiumで任意入力保持、画像なし、先行1枚で停止、了承後の比較画像、最終確認、5工程、結果・履歴、両承認15分期限、7種類の固定失敗/0件、戻る、再生成取消、中止取消、保存・削除再試行、未保存破棄取消、詳細のカード内展開を確認した。fetch/XHRと外部originを拒否し、ローカルの文書・JS/CSS・フォント・画像だけで動作した。
- 176×48px・角丸100pxのボタンと3種のホバー、本文/見出し/フォント/背景、現在工程の青い丸と1.5秒周期、生成波の1.5秒周期・停止、フォーカス復帰をブラウザで照合した。末尾の点は共通部品の0.5秒intervalで更新する。開発server `127.0.0.1:5173` でもStyleXが反映され、ブラウザ例外0件。入力・参考画像・結果のスクリーンショットを目視確認した。
- 最初のPython全体gateは3044 passed/20 skipped/30 deselectedに対しMarkdownリンクテスト1件失敗。新しいEXEC-117の見出しに含む `+` のanchor正規化を二重hyphenと誤記したためで、リンクを単一hyphenへ修正した。既存Pythonコードの変更はない。最終gate結果を後記する。

TDDの追跡:

| 対象 | REDとGREENのコマンド・結果 | 同一テストSHA-256 |
|---|---|---|
| 入力画面の参考画像ON/OFF | `cd frontend && npm test -- --run src/model.test.ts`: RED exit 1（true期待にfalse）、修正後19件GREEN exit 0 | `e2dc82bad8b912bb0fe6960d57e3529cf95a790738b3383d566a4a33adf124e0` |
| 固定商品の不一致・履歴の不正配列拒否 | `cd frontend && npm test -- src/model.test.ts src/history.test.ts`: RED exit 1（5 failed/35 passed）、GREEN exit 0（40 passed） | model: `00a24e0b1febeb5be5932b0a3c06c8fc4fbc0a6f8b519dc7b019afe60a8719db` / history: `62005c077e35ddf8dce1d7881eae1b774b714e071a1df27fbcc34128f0de73f9` |
| 比較生成中の参考画像保持・最終確認の画像・詳細履歴の削除後復帰 | `cd frontend && npm run test:e2e -- --grep 'reference and comparison|history deletion'`: RED exit 1（画像欠落・削除済み詳細の残存）、GREEN exit 0 | `7244fc9fd7b1160b2f7865c3b85fb674330fb32df720eab83381132f113a4ae2` |
| 商品詳細を開いて他カードを保持 | `cd frontend && npm run test:e2e -- e2e/interaction.spec.ts`: RED exit 1（結果10件が0件へ消失）、GREEN exit 0（4 passed） | `888951edebbc95f1f691715384f9a7b46019b0dc930a2a75bc86c9e9b8db7833` |

初回の状態遷移テストは未実装moduleの欠落でRED、履歴はstubで14件REDを確認してから実装した。初回整形でtest hashが変わったため、上表は書式を含め同一hashのままRED/GREENを確認できた回帰を記録する。後からテストを弱めて成功させていない。追加の回復試験 `recovery.spec.ts` は `6d0fe69987600ddc8ca032c3d61632b5a851a583db4dfed017deac05ffecaa3b`。

境界: 通常検索で共有する表示部品をモックデータへ接続した。日本語/英語検索語編集、実サービスadapter、最終承認controller・server・API接続は後続作業。固定データの一致/確認できない/合わない表示は検索品質の証明ではない。フォントはNoto Sans JP Variable（同書体）をローカルに同梱。公開npm依存とChromiumの取得、Figma node 59:22と公式StyleX資料の読取だけを外部準備として実施し、実商品検索・モデル推論・課金APIは実行していない。commit/pushは未実施。

最終gate: `uv lock --check --offline`、Ruff check、372ファイルのformat check、Python全体offline（3045 passed / 20 skipped / 30 deselected、74.35秒）が成功した。現行Markdownとfrontend/READMEのローカルリンク・見出し・コードフェンス検査、`git diff --check`も成功。実装とオフライン受入を完了し、実API接続を後続に残す。


## EXEC-118: 主要ボタンとトグル・丸枠の表示修正

状態: 完了。作成・更新: 2026-09-11。

目的: 利用者報告の白背景・白文字を直し、オン/オフを指定色のトグルへ変更し、白い円形外枠を滑らかに描画する。対象は `frontend/index.html`、共通表示部品、2か所の画像利用設定、関連ブラウザ回帰と仕様文書。実サービスと既存Pythonの処理は対象外。

原因: 開発配信ではStyleXの層より後にreset層が登録され、共通の `color: inherit` がprimaryの黒文字を上書きしていた。productionでは正常だったため、productionだけの既存検証では検出できなかった。headでresetを先に宣言するHTML差替え実験で、dev/prod両方の通常・無効・処理中・ホバーが正常になることを確認した。

手順: 修正前のブラウザ回帰REDを記録し、同じテストでdev/prodのGREENを確認する。トグルはnative checkboxを `role="switch"` として扱い、56×32pxの背景、24pxの白いつまみ、ON青/OFF濃灰色、Spaceとラベルクリック・disabledを共通化する。全体の44px円と調査工程の36px円はSVGの2px白線とし、図形の拡大で線幅が変わらないようにする。型・整形、unit、build、ブラウザ全体、文書リンク・差分を確認する。純粋な表示変更のためPython機能テストの再実行は対象外とし、関連するMarkdown検査を行う。

rollbackは今回の差分だけを戻し、EXEC-117から残る未コミット変更を保つ。実行結果とRED/GREENのtest hashは完了時に追記する。


EXEC-118結果: `index.html` のhead先頭でreset層を先に宣言し、開発時に後着する共通CSSがStyleXを上書きしないようにした。入力・条件確認の画像利用設定を同じToggle部品へ置換した。白い円枠は共通SVGへ分離し、全体44px/工程36px、2pxの白線、形状精度と拡大時の線幅を固定した。データ・状態遷移・既存Pythonは変更していない。

検証（すべて2026-09-11、frontendで実行）:

- `npm run check`: TypeScriptとPrettier成功。
- `npm test`: 40件成功。
- `npm run build`: 成功。
- `UI_TEST_MODE=development npm run test:e2e -- controls.spec.ts --workers=4`: 4件成功（5.4秒）。開発用5175番で通常・無効・ホバー・処理中文言の色、トグルのクリック/Space/disabled/状態保持、DPR 1/2の円を検証した。
- `npm run test:e2e -- --workers=4`: production配信4173番で22件成功（42.3秒）。既存18件を含む。
- 4枚のDPR別画像と利用者確認用5173番を目視・computed styleで確認した。白い円に欠け・楕円化はなく、白背景のボタンは黒文字、トグルONは青だった。5173番のブラウザ例外は0件。
- 現行Markdownリンク・見出し検査と `git diff --check`: 成功。純粋な表示修正なのでPython機能テストは再実行していない。

RED/GREEN記録: 変更前の `UI_TEST_MODE=development npm run test:e2e -- controls.spec.ts --workers=4` はexit 1、4件失敗（黒文字期待に白、switch未実装、SVG未実装2件）。同じ時点のproductionは3件失敗/色1件成功だった。test hashは `fd934dcbbd12b2bbbd4a6cea3662ed32f80ad7516e75cb339c8ada11bc2aaad0`。その後、SVGの白線検査を生のhex属性から共有tokenのcomputed strokeへ修正し、最終hashは `c703ddf8098ad2ef20def751a0c324e53f27dde3eb52e358264256ccb04ec107`。ボタン色のテスト内容は同じ。最終hashでswitch/SVGのRED（3件失敗）を確認し、実装後はdev4件・production22件がGREENとなった。最終REDのボタンだけは成功しており、初回の色REDと区別する。検査を弱めてボタンを成功させていない。

仕様の配色・サイズ・役割と開発版の検証コマンドをFRONTEND、REQUIREMENTS、SEARCH-FLOW、DEVELOPMENTへ同期した。追加のツール取得・外部サービス実行・commit/pushは行っていない。

## EXEC-119: トグルの動き・角丸・履歴操作の調整

状態: 完了。作成・更新: 2026-09-11。

目的: 利用者指定に合わせ、トグルの切替とウィンドウ・ボタンの角丸を滑らかにし、検索履歴一覧の「削除」「開く」を小さくする。すべての「削除」は危険ボタンとし、追加指定の外枠色 `#901010` を共通tokenへ適用する。背景・文字・ホバー色は従来仕様を維持する。

対象: `frontend/` の共通表示部品・StyleX・履歴一覧・ブラウザ回帰と関連仕様。トグルの移動と背景色は240ms、`cubic-bezier(0.22, 1, 0.36, 1)`。動きを減らす設定では即時に切り替える。ウィンドウ・カードの15px、ボタンの100pxを維持し、`corner-shape: squircle` で滑らかな曲線にする。未対応ブラウザは通常の角丸へ戻る。真円の進行アイコンとトグルは維持する。履歴一覧だけ96×36pxを採用し、削除を左、開くを右の同じ行へ離して配置する。通常操作と確認ダイアログは176×48pxとする。

手順: 変更前に専用ブラウザテストのREDを記録する。同じテストで連続切替・中間フレーム・動きの抑制・サイズ・削除配色・曲線のGREENを確認する。TypeScript/整形、unit、build、productionブラウザ全体と開発配信の表示回帰、スクリーンショット目視、Markdownリンク・差分を検証する。既存Pythonの処理に変更はないためPython機能テストの再実行は対象外。実サービス・credential・追加依存取得・commit/pushは対象外。

rollbackはこの表示差分だけを戻し、先行する未コミット実装と文書差分を保持する。結果とtest hashは完了時に追記する。


EXEC-119結果: 共通Toggleに移動・背景色の240ms補間と動きの抑制設定を追加した。ウィンドウ・カード・ボタンはStyleXのsquircleへ変更し、真円の部品は維持した。通常寸法に加えて96×36pxの小型寸法を共通tokenへ追加し、履歴一覧の2ボタンだけへ適用した。3か所の削除をDeleteButtonへまとめ、危険ボタンの外枠を共通の `#901010` にした。

専用テスト `frontend/e2e/motion.spec.ts` のSHA-256は `547625880f5438d220bcdfb34d43206e27211ced97b4ba93efaa8503342acf8e`。変更前の `UI_TEST_MODE=development npm run test:e2e -- motion.spec.ts --workers=4` はexit 1、4 failed / 1 passed（8.0秒）。アニメーションなし、旧176px幅、旧危険色、通常の角丸で失敗した。動きを減らす設定の即時切替は既存実装でも成功した。同じテスト内容を実装後も維持した。既存flow.spec.tsの危険外枠色の期待値だけは追加指定の色へ更新した。

初回GREEN確認は開発版8 passed / 1 failed。指定の表示は成功したが、削除確認取消後のフォーカス復帰が失敗した。既存DialogのcleanupがshowModalを閉じずにフォーカスを戻していたため、開発版StrictModeの再setupで起動元が正しく記録されなかった。cleanupで同じdialogをcloseしてから戻すように直し、同じテストで解消した。

検証（2026-09-11、frontendで実行）:

- `npm run check`: TypeScript・Prettier成功。
- `npm test`: unit40件成功。
- `npm run build`: 成功。
- `UI_TEST_MODE=development npm run test:e2e -- motion.spec.ts controls.spec.ts --workers=4`: 9件成功（5.6秒）。中間フレーム、連続切替、動きの抑制、サイズと左右配置、3か所の削除通常/ホバー色、曲線と半径、取消後フォーカス、既存ボタン配色と白円枠を確認した。
- `npm run test:e2e -- --workers=4`: production配信で27件成功（42.9秒）。画像あり/なし、履歴・失敗回復を含む。実バックエンド・外部APIへの接続は行っていない。
- 開発画面5173番でも入力・履歴・削除確認をDPR 2で目視し、ブラウザ例外0件、取消後の起動元フォーカス復帰を確認した。squircleの表示はChromiumで確認し、未対応ブラウザでの実表示は未検証。
- 現行Markdownのリンク・見出しと `git diff --check`: 成功。Python処理に変更はなく機能テストは再実行していない。

仕様・開発規則・要件・残作業・変更履歴を同期した。追加の依存取得、実サービス実行、commit/pushは行っていない。

## EXEC-120: 細い外枠の描画改善

状態: 完了。作成・更新: 2026-09-11。

目的: 実ブラウザでも外枠が掠れて見えるという報告に対し、原因候補を比較して1px・指定色を維持したまま描画を改善する。対象は共通部品・画面StyleX・既存表示テスト・現行仕様。実バックエンド、Python、外部サービス、ブラウザやOSの設定変更は対象外。

原因候補: 1px曲線のアンチエイリアス、squircleの狭い角の形状、行高の端数に由来する小数座標、表示倍率/DPRの画素補間。ローカルChromiumではopacity 1・filterなし・transformなしを確認したが、補足14pxの行高24.5px/25.2pxによりヘッダーボタンy=45.25px、入力panel y=536.6875pxとなっていた。利用者の実ブラウザやGPU固有の原因は未確定。DPR 1/1.25/2の現行画面と通常の円弧を比較した。

実装: squircle指定を除き、ウィンドウ等15px・ボタン100pxの標準border-radiusで円弧を描く。補足14pxの行高を24pxに揃え、端数の累積を減らす。線幅・色・ボタン寸法・SVGの進行丸とトグルは維持する。既存テストを円弧の契約へ更新し、代表枠の整数座標を検証してRED/GREENを記録する。開発/ビルド配信の表示回帰、DPR別の目視、型/整形/build、文書リンク・差分を検証する。変更のない状態モデルとPythonの機能テストは再実行しない。

rollbackは今回の角丸・行高差分だけを戻し、既存の未コミット変更を保持する。検証結果と制約は完了時に追記する。


EXEC-120結果: 共通表示と画面StyleXのsquircleを除去し、標準border-radiusの円弧へ変更した。補足・段階ラベル・説明・履歴の14px文字は行高24pxへ揃えた。幅1440pxの入力画面でheader高さ90px、headerボタンy=45px、panel y=534px、textarea y=643px、主要ボタンy=938pxとなり、代表枠の座標・寸法が整数になった。一般の任意viewport・DPRで物理画素が整数になるとは主張しない。

描画比較: Chromium 153、viewport1440×1100、DPR 1/1.25/2、ローカルフォント読込後の入力画面で比較した。DPR1.25のheaderボタン上辺をCSS x=1200pxで横切る画素列（画像x=1500、y=53〜60）は、変更前のRGB各成分が `[0,0,0,145,127,0,0,0]`、角丸だけ円弧へ変えた場合と最終実装が `[0,0,0,192,128,0,0,0]` だった。白線画素のピークは145→192/255、強度の和を255で割った値は1.067→1.255となり、同じCSS1px線でもsquircle経路で薄くなる差を再現した。DPR1の上辺は変更前後とも白255の1画素、DPR2は白255の2画素だった。この測定は代表位置のラスタライズ差であり、全GPUや利用者実機の不具合原因を断定するものではない。比較画像は一時領域 `/tmp/amazon-border-diagnostic/` に保存した。

RED/GREEN: 更新したmotion.spec.tsのSHA-256は `169f6840a5356f2d781af28f2168a8ba067d3c8768d539f460397c58fa13e3f2`。`UI_TEST_MODE=development npm run test:e2e -- motion.spec.ts -g 'integer frame'` は実装前exit1、1件失敗（squircleと小数座標を検出）。同じtest内容を維持し、実装後の `UI_TEST_MODE=development npm run test:e2e -- motion.spec.ts controls.spec.ts --workers=4` は9件成功（5.3秒）。`npm run test:e2e -- --workers=4` はビルド配信で27件成功（42.7秒）。主要ボタンと危険ボタンの配色・1px線・通常/小型寸法・トグルとSVG円・履歴操作・検索両経路と失敗回復を維持した。TypeScript/Prettier、build、Markdownリンク・見出し、git diff --checkも成功した。

残る境界: 125%等ではCSS1pxが物理画素の整数幅と一致しないためアンチエイリアス自体は残る。利用者のブラウザ/GPU/DPIそのものは未確認。線を太くする、指定色を明るくする、影を加える、ブラウザ設定を変更する対応は行っていない。状態モデル・Pythonの機能テストは再実行せず、実サービス・追加依存取得・commit/pushも行っていない。

## EXEC-121: 枠線の濃淡を画素で検証して改善

状態: 完了。作成・更新: 2026-09-11。

目的: EXEC-120後もChromeの100%表示でボタンとウィンドウの両方が掠れて見えるとの利用者報告に対応する。前回の角丸・行高だけでは解消できていない。CSS border、SVG stroke、SVG背景、outline、ぼかしなし内側輪郭を同一条件で比較し、表示スタイルだけでなく角の画素濃度を検査する。

調査: ChromiumのDPR1・100%でもCSS borderとSVG strokeは角の濃度が落ちた。半径24pxのボタンの左上角を10〜80度で法線方向に積分した濃度換算線幅は、CSS borderの最小0.569px・平均0.855pxに対し、内側輪郭は最小0.909px・平均1.047pxだった。半径15pxの枠では最小0.623→0.803px、平均0.850→0.938pxとなった。この値はアンチエイリアスの画素濃度を積分した比較量であり、CSSの幾何学的線幅そのものではない。画素密度1/1.25/1.5/2で描画比較し、SVG/outlineへの変更だけでは解消しないことを確認した。

実装方針: 指定の1px輪郭を `box-shadow: inset 0 0 0 1px <指定色>` で一度だけ描く。実borderを0にし、除去分を余白へ移して要素の外形と内容位置を維持する。白/危険色、通常/小型寸法、角丸15px/100px、フォーカス表示、トグル・進行円を維持する。外側の影、ぼかし、ハイライトは追加しない。対象は共通部品と画面StyleX、ブラウザ回帰、仕様文書。モデル・Python・外部サービスは対象外。

手順: 実装前に角の画素濃度を測るブラウザ回帰を作り、REDとhashを記録する。実装後も同じテストでGREENを確認し、既存検査をCSS border値から実際に表示する1px輪郭の色・幅へ更新する。開発/ビルド配信の回帰、型/整形/build、DPR別の画像比較、文書リンク・差分を確認する。ユーザーの実機で解消したと自己判定せず、手元の比較と区別する。

rollbackは今回の輪郭と余白の変更のみを戻す。先行する未コミット差分を保持し、追加依存取得・実サービス・commit/pushは行わない。


EXEC-121結果: 共通Button、画像カード、生成中ポップ、調査行、dialogと、画面のheader・panel・入力欄・結果/履歴カード等を内側1px輪郭へ変更した。余白の補正により、1440px viewportのheaderはx96/y24/1248×90、headerボタンはx1143/y45/176×48、panelはx160/y534/1120×485、textareaはx193/y643/718×168で、変更前の外形・配置を維持した。トグルと進行表示のSVGは変更していない。

RED/GREEN: 新規 `frontend/e2e/frame.spec.ts` のSHA-256は `b5e139b555ff2210a2a437f438c9ef6715e4b343d9a3d53b423d46056eeb3ece`。実装前の `UI_TEST_MODE=development npm run test:e2e -- frame.spec.ts` はexit1・1件失敗で、ボタン/ウィンドウの角の最小濃度と平均濃度の4検査が失敗した。実装後もtest内容/hashを保ち、角の最低濃度、平均濃度、過度に太くないこと、直線が白255の1画素で内側隣接画素は黒であることが成功した。既存の配色検査は描画方式に合わせてbox-shadowの1pxと色を検査するよう更新した。

検証: `npm run check`（TypeScript/Prettier）、`npm run build` はexit0。`UI_TEST_MODE=development npm run test:e2e -- frame.spec.ts controls.spec.ts motion.spec.ts --workers=4` はexit0・10件成功（5.4秒）。`npm run test:e2e -- --workers=4` はビルド配信でexit0・28件成功（42.6秒）。画像あり/なしの検索操作、履歴・回復、通常/危険/主要ボタン、トグル・進行丸、枠の画素検査を含む。5173番の開発画面もDPR1/1.25/1.5/2で描画・撮影し、例外0件と外形・配置の一致を確認した。比較画像は一時領域 `/tmp/amazon-stroke-diagnostic/` に保存した。

境界: ローカルChromium 153での濃淡改善であり、利用者のChrome/GPUそのものの解消確認ではない。非整数DPRでは画素補間が残る。DPR2の比較は従来も新方式も同程度であり、一律の改善とは扱わない。変更のない状態モデル・Pythonの機能テストは再実行していない。実サービス、追加依存取得、commit/pushは行っていない。現行仕様・開発規則・要件・変更履歴を同期した。`python tools/check_markdown_links.py` はexit0（16文書・1753リンク・1315アンカー・2243見出し）、`git diff --check` もexit0。


## EXEC-122: 完了段階の配色とスクロール維持

状態: 完了。作成・更新: 2026-09-11。

目的: 全体段階バーの完了した丸の背景を `#3a83f7` にし、画面更新で先頭へ戻さない。対象はStepper、Appの画面更新時フォーカス、ブラウザ回帰、関連仕様。調査内の工程アイコン、状態モデル、外部サービスは変更しない。現在は完了した丸が黒背景で、state.screen/view変更時に見出しfocusとscrollTo(0,0)が走る。

手順: 完了/現在/未到達と戻る操作の色、操作直後と非同期処理完了時のスクロール維持をブラウザテストでRED確認する。Stepperの塗り分けを変更し、見出しのfocusはpreventScrollを指定してscrollToを除く。画面が短くなった場合のブラウザによる末尾への位置制限は許容する。型/整形/build、開発・ビルド配信のブラウザ回帰、Markdownリンク・差分を検証する。データ/保存/認証境界への影響はない。rollbackは今回の配色とfocus差分だけを戻し、既存の未コミット変更を維持する。結果・RED/GREENのhashと未検証範囲を完了時に記録する。


EXEC-122実装: Stepperの現在以前の丸を青背景にし、未到達・戻った後の後続段階は黒背景へ戻す。白いSVG外枠と現在位置アイコンを維持した。Appの画面更新effectは見出しへ `focus({ preventScroll: true })` を行い、`window.scrollTo(0, 0)` を削除した。

RED/GREEN: `frontend/e2e/navigation.spec.ts` のSHA-256は `c5969c0a9715f381069992e6a5f05ef8ffc557e01413ebf07bbe9c6a5f1cedf8`。実装前の `UI_TEST_MODE=development npm run test:e2e -- navigation.spec.ts --workers=2` はexit1・2件失敗（完了した丸の青期待に黒、処理開始前のscrollY=480維持期待に0）。同一hashの実装後検証 `UI_TEST_MODE=development npm run test:e2e -- navigation.spec.ts controls.spec.ts motion.spec.ts frame.spec.ts --workers=4` はexit0・12件成功（6.1秒）。完了/現在/未到達の色と戻る操作、処理開始直後のスクロール、条件整理・画像生成完了後のscrollY=120維持、見出しフォーカスを確認した。`npm run check` と `npm run build` もexit0。


最終検証: `npm run test:e2e -- --workers=4` はビルド配信でexit0・30件成功（43.1秒）。検索の画像あり/なし、履歴・失敗回復、フォーカスと表示回帰を含む。`python tools/check_markdown_links.py` と `git diff --check` はexit0。現行仕様と要件・開発コマンド・変更履歴を同期した。状態モデルとPythonは未変更のため機能単体テストを再実行していない。ローカルChromium/合成データでの検証であり、実バックエンド・外部サービス・利用者実機の確認は行っていない。追加依存取得・commit/pushは行っていない。


## EXEC-123: 角の輪郭濃度を補正

状態: 完了。作成・更新: 2026-09-11。

目的: 添付された半径15pxの白枠の角に残る掠れを改善する。対象は共通の角丸枠と表示検証・仕様。1pxの線位置・指定色・寸法・内容・スクロール維持を保つ。前回の1回描画では曲線の部分画素が薄く、法線上の最低ピーク濃度が0.448だった。同位置へ同じ1px輪郭を2回合成すると0.680になり、直線部分と着色画素の範囲を広げず曲線の濃度が上がる。CSS border、SVG filter、重ね描画をローカルChromiumで比較した。

手順: frame.spec.tsに曲線ピーク濃度と輪郭の外への着色検査を追加してREDを確認する。従来のRGB値積分の上限1.2は幾何学的な線幅ではなく、濃度補正も太い線と判定するため、直線1pxに加え円弧の幾何学的範囲外の画素検査へ置き換える。最小濃度と平均濃度の既存下限は維持する。StyleXの同一1px内側輪郭を重ね、透明な部分画素だけの濃度を補う。文字や面へのfilterは使わない。開発/ビルドの表示回帰、DPR1/1.25/1.5/2の画像、型/整形/build、文書リンクを確認する。モデル・Python・実サービス・認証・データ構造は対象外。rollbackは今回の重ね描画だけを戻す。


EXEC-123実装: components.tsx/screens.tsxの同一1px内側輪郭を2回合成するよう変更した。白と危険色の両方に適用し、通常・ホバー時の指定色と従来の外形・余白・半径を保持する。陰影の移動やぼかし、文字や背景面へのfilterは追加していない。前回の「一度だけ描く」規則を今回の濃度補正へ更新した。

RED/GREEN: frame.spec.tsのSHA-256は `84ce5a3ba2bf490931378278cdfa6122b17536d9d89b4662edc816e7d4137bc6`。実装前 `UI_TEST_MODE=development npm run test:e2e -- frame.spec.ts` はexit1・1件失敗（ボタン0.492/ウィンドウ0.448のピーク濃度が0.65を下回る）。同一hashの実装後 `UI_TEST_MODE=development npm run test:e2e -- frame.spec.ts controls.spec.ts motion.spec.ts navigation.spec.ts --workers=4` はexit0・12件成功（4.5秒）。従来の最小/平均濃度下限と直線1pxを維持し、新規のピーク濃度と輪郭の幾何学的範囲外の非着色も成功した。既存のボタン配色検査は同位置の2個のbox-shadowへ同期した。

型/整形とbuildはexit0。5173番の現行画面をDPR1/1.25/1.5/2で撮影し、ブラウザ例外0件、textareaのx193/y643/718×168pxを維持した。各DPRで同一座標の角の変更前後も撮影した。一時比較画像は `/tmp/corner-before-*.png`、`/tmp/corner-after-*.png`、画面全体は `/tmp/corner-final-*.png`。ローカルChromiumの確認であり、利用者実機での解消確認ではない。


最終結果: `npm run test:e2e -- --workers=4` はビルド配信でexit0・30件成功（40.8秒）。画像あり/なしの検索、履歴・失敗回復、角の画素検査、完了した段階の青背景、画面更新時のスクロール維持を含む。`python tools/check_markdown_links.py` と `git diff --check` はexit0。変更のない状態モデル・Pythonの単体テスト、実サービス、追加依存取得、commit/pushは実行していない。
