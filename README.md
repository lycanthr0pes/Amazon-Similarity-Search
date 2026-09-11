# amazon-explorer

> **次期フロントエンド（2026-09-11）:** [frontend/](frontend/) にReact + StyleXのデスクトップ画面と[オフラインモック](docs/FRONTEND.md#14-オフラインモック)を実装した。任意入力から条件・画像の確認、商品調査、固定結果と履歴まで操作できる。Figmaはレイアウトの参考、[画面設計](docs/FRONTEND.md#13-次期uiの視覚統一契約)は視覚仕様の正本とする。実バックエンド・APIには未接続で、検証結果は [EXEC-117](docs/GOAL.md#exec-117-react-stylexのオフライン画面) に記録する。

amazon-explorer は、日本語の自然文から Amazon.co.jp の商品候補を検索し、条件への近さで並べる Python アプリケーションである。ローカルの Bonsai 8B が入力を商品属性 JSON に変換し、Outscraper が商品候補を取得する。商品名・属性の TF-IDF 類似度、価格、除外条件を組み合わせて順位を決め、Streamlit または CLI で結果を確認できる。

## オフラインで画面を確認する

Node.js 22.12以上とnpmを用意し、リポジトリ直下から次を実行する。Python、Bonsai、APIキーは不要である。

```sh
cd frontend
npm ci
npm run dev
```

`http://127.0.0.1:5173` をデスクトップのブラウザで開く。`npm ci` は公開パッケージとNoto Sans JPを取得する環境準備で、実行時のフォント・画像はローカル配信だけを使う。入力はそのまま確認画面に残るが、条件・画像・12件の商品は固定の合成データであり、実際の理解・検索は行わない。

画像なし経路と、参考画像1枚の確認→了承→比較画像の確認を選べる。完了した結果は同じタブの`sessionStorage`へ最大30件・30日間保存し、再読込しても履歴を開ける。進行中の検索状態は再読込で初期化され、タブを閉じた後の永続履歴は提供しない。起動・検証コマンドと失敗表示の確認方法は [モックの実行手順](docs/FRONTEND.md#141-配置と実行手順) を参照する。

## 実装フロー

```text
自然文
  -> Bonsai OpenAI互換APIで属性抽出
  -> Outscraper向け検索語を選択
  -> Amazon商品を非同期取得・ポーリング
  -> 商品データを正規化
  -> SudachiPy + TF-IDF + 条件一致 + 価格で採点
  -> Streamlit / CLIへ返却し、cache/へJSON保存
```

主な実装:

- `src/main/run.py`: 4段階の検索処理を統合
- `src/clients/`: Bonsai、Outscraperとの通信
- `src/services/`: 属性抽出、検索語選択、正規化、テキスト処理、採点
- `src/repositories/`: TTL付きJSONキャッシュの読込・保存
- `src/schemas.py`: Pydanticデータモデル
- `src/search_v2/`: 次期検索のstrict境界、schema 3.0のtyped proposal付き承認・画像失敗回復state、参考画像1枚の了承後にCloudflareで条件別偽画像だけを生成するoffline境界、Outscraper完了結果から `typed-ranking-v4` までのoffline pipeline、5秒application deadline付きspawn子processへ隔離した画像DNS resolverとpinned-IP HTTPS transport、typed decisionからschema 2.0/3.0表示履歴への変換、owner分離した30日検索履歴、local job・暫定schema 5.0履歴用ASGI API factory
- `src/ui/streamlit_ui.py`: Streamlit UI
- `frontend/`: React + TypeScript + StyleXの画面、オフライン状態遷移、タブ内履歴、ローカル資材、ブラウザテスト
- `tests/`: 現行 `src` を直接検証する回帰テスト
- `docs/old/examples/`: 段階別に作成した旧検証コードの参照用スナップショット

## 必要なもの

- Python 3.10以上
- [uv](https://docs.astral.sh/uv/)
- OpenAI互換APIとして起動した Bonsai 8B
- Outscraper APIキー

## セットアップ

```sh
uv sync --locked
test -e .env || cp .env.example .env
chmod 600 .env
```

既存の `.env` は上書きしない。`.env` には最低限 `OUTSCRAPER_API_KEY` を設定する。Bonsai の接続先や Outscraper の取得条件を変更する場合は、[バックエンド設計](docs/BACKEND.md)を参照する。実値を `.env.example` や Git 管理ファイルへ書かないこと。

## Bonsai 8B

llama.cpp をビルドし、GGUFモデルを用意する。

```sh
git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp
cmake -B build
cmake --build build --config Release -j 2
```

モデルの配置先に合わせてサーバーを起動する。アプリの既定接続先は `http://127.0.0.1:8080/v1`、既定モデル名は `Bonsai-8B.gguf` である。

```sh
/path/to/llama.cpp/build/bin/llama-server \
  -m /path/to/Bonsai-8B.gguf \
  -c 8192 \
  -np 1 \
  --cache-prompt \
  --host 127.0.0.1 \
  --port 8080
```

本番では同じ固定system promptのKVを再利用するため `--cache-prompt` を明示する。`--slot-save-path` は設定せず、prompt cacheをdiskへ永続化しない。schema二重送信の除去後も、許容する最大2,000文字の入力には固定promptと合わせて4,096 tokensを超える例があるため、contextは `-c 8192`、同時slotは `-np 1` を維持する。

## Outscraper

`.env` に APIキーを設定する。

```dotenv
OUTSCRAPER_API_KEY=your_api_key
```

既定では `amazon.co.jp`、言語 `ja`、郵便番号 `100-0001`、最大100件を指定する。APIキーは `X-API-KEY` ヘッダーで送信される。

## 起動

Streamlit:

```sh
uv run streamlit run app.py
```

CLI:

```sh
uv run python -m src.main.run "静かで軽い日本語配列のワイヤレスキーボード"
```

CLI の表示件数は `--display-limit` で変更できる。

```sh
uv run python -m src.main.run "1万円以内の白いワイヤレスキーボード" --display-limit 5
```

既存キャッシュを読まずに外部処理からやり直す場合は `--no-cache` を付ける。この指定でも新しい結果はキャッシュへ保存される。

## local job・履歴API

`src/search_v2/production_api.py` は、承認済み検索jobの投入、状態取得、取消、暫定schema 5.0履歴詳細取得を提供するloopback限定のStarlette ASGI application factoryである。既存production service、履歴repository、同一processの15分以内submission storeを呼出側から注入する。認証済み公開APIではなく、server起動構成、最終承認controller、現行Streamlit、次期フロントエンドには未接続である。API契約は [バックエンド設計](docs/BACKEND.md#134-local-job履歴http-api) を参照する。

## 次期の画像生成フロー

参考画像を使う場合は、最初に1枚だけ生成して確認を待つ。利用者が了承すると、その画像を参照して見た目の条件を1つだけ変えた比較用の偽画像を生成する。先行1枚の作り直しには再確認を必要とし、商品検索は別の最終承認後に開始する。[利用フロー](SEARCH-FLOW.md#4-step-2-参考画像を確認する) と [Figma](https://www.figma.com/design/PEVM5G4854vaDqdWgSA3ui?node-id=59-22) を同じ順序へ更新した。実装・検証範囲は [EXEC-080](docs/GOAL.md#exec-080-4方向生成を製品フローから除去) を参照する。現行Streamlitと次期フロントエンドへの接続は含まない。

## テストと静的確認

通常の確認は外部APIを呼ばない。

```sh
uv lock --check --offline
uv run --frozen --offline --no-sync ruff check .
uv run --frozen --offline --no-sync ruff format --check .
uv run --frozen --offline --no-sync python tools/check_markdown_links.py
uv run --frozen --offline --no-sync pytest -m 'not live_api'
git diff --check
```

Markdown検査は外部URLへ接続せず、ルート直下と `docs/` 直下の現行Markdownにあるlocal pathと見出しanchorを確認する。`docs/old/` は検査元から除外する。

外部APIを使う検索はoffline testとは別である。live試験の承認条件と、各結果から主張できる範囲は [統合済みテスト方針](docs/DEVELOPMENT.md#統合済みテスト方針) を参照する。

### request v8とprompt cacheのlocalhost結合テスト

次のtestは通常CIから除外し、実行するたびに送信内容・回数・時間上限・保存範囲を
示して人間の明示承認を得る。承認後、未使用のloopback portと実在するabsolute pathを
指定して実行する。

```sh
uv run --frozen --offline --no-sync pytest -q -s \
  --run-live-api \
  --run-bonsai-e2e \
  --bonsai-server-bin /absolute/path/to/llama-server \
  --bonsai-model-path /absolute/path/to/Bonsai-8B.gguf \
  --bonsai-e2e-port 18080 \
  tests/test_bonsai_live_e2e.py::test_request_v8_reuses_prompt_cache_with_local_bonsai
```

testは `llama-server` を `127.0.0.1`、context 8,192、parallel 1、prompt cache有効、log無効で
起動する。非機密の固定合成入力2件をrequest v8のbounded compact wire形式からactual Requests transportとstrict
adapterへ通し、2件目の `cached_tokens` が正であることを確認する。各1 attempt、retry 0、
response上限1 MiBであり、applicationの生成token上限とHTTP timeoutは追加しない。test全体は
server ready後900秒でtest所有serverを停止する。応答本文・合成入力・cache内容・server logは
出力または保存せず、schema version、token件数、所要時間、server停止状態だけを出力する。
`--offline` はuvの依存取得を止める指定であり、このtest自体は明示承認したlocalhost HTTPを使う。

### 同一入力によるprompt・生成時間診断

異なる入力間のwall時間をcache速度差として比較せず、同じ固定合成入力のcold・warmを測る場合は、
別の実行承認後に診断modeだけを選択する。

```sh
uv run --frozen --offline --no-sync pytest -q -s \
  --run-live-api \
  --run-bonsai-e2e \
  --run-bonsai-latency-diagnostic \
  --bonsai-server-bin /absolute/path/to/llama-server \
  --bonsai-model-path /absolute/path/to/Bonsai-8B.gguf \
  --bonsai-e2e-port 18080 \
  tests/test_bonsai_live_e2e.py::test_same_request_separates_prompt_and_generation_time
```

診断modeは通常の異なる入力2件testを選択せず、同一request v8を同じserverへ2回だけ送る。
生responseと入力本文は出力せず、prompt・cached・completion token数、llama.cppの
`prompt_ms`・`predicted_ms`、finish reason、response byte数、wall時間だけを返す。
context、parallel、cache、deadline、retry、cleanup等の境界は上記結合testと同じである。
この診断も通常CIでは実行せず、Core Ultra性能またはproduction E2Eを示さない。

2026-09-06の明示承認済みCore i5-13600KF・CPU版診断は旧request v6で行い、同じbodyの2 callsが
いずれも487 completion tokens、full JSON・strict intent成功となった。coldはprompt 43.655秒、
generation 93.609秒、wall 137.311秒、warmは923 / 924 prompt tokensをcacheし、prompt 0.124秒、
generation 90.281秒、wall 90.440秒だった。prompt処理は353.47倍・99.72%短縮、wall全体は
1.52倍・34.13%短縮した。warm時は生成がwallの99.82%を占めるため、次の速度改善対象は
prompt cacheではなくcompletion生成である。request v7の応答は365.12秒で未完了のまま停止した。request v8は
別の承認済み2-call診断でcold 53.148秒、warm 17.625秒、追加の1-call development regressionで50.628秒を
観測した。後者の意味条件欠落と不正typed conditionを受けてpromptとschemaをoffline修正したが、承認済みの
修正後1 callも53.595秒でstrict intentまで到達した一方、価格・除外条件の欠落と入力にないtyped conditionにより
blockingとなった。Outscraperは呼び出していない。そこでrequestを増やさず、入力中の原語・trusted aliasで
裏付けられたtyped conditionだけを残し、明示JPY上下限と未知語を含む除外表現をローカルで復元するadapter境界を
追加した。日本語の根拠照合と除外対象の切り出しは、手書きの文字境界ではなくSudachiPy `SplitMode.C` の形態素、
品詞、NFKC/casefold済みsourceのoffsetを使うため、未知の複合語でも形態素境界を越えて単一漢字aliasを誤一致させない。価格の数値抽出は
有界なJPY表記だけを正規表現で扱い、価格関係語は同じ形態素spanから判定する。取得済み応答相当fixtureはquery planまで
offlineでreadyとなる。後続の承認済み1-call localhost再実行では、83.398秒、902 prompt tokens、
290 completion tokensでstrict intentへ到達し、未知語2種、価格範囲、除外対象、二重否定拒否、ready proposal、
query planの固定判定がすべて成功した。これは単一の固定合成入力によるlocal development regressionであり、Core Ultra、
未知入力全般、実商品検索、production E2Eへ外挿しない。

2026-09-06の別の明示承認済みOutscraper試験では、固定合成queryをtask作成1回・自動retry 0で送り、同一taskを9回pollして251.795秒で24候補を受信した。24件すべてが次期v2の応答契約と観測値だけの正規化契約を通過し、rejectは0件だった。生応答、商品本文、商品URL、ASIN、provider request ID、APIキーは出力・保存していない。これはOutscraper接続と正規化の単一試験であり、Bonsaiからの一続きのE2E、ranking品質、UI、production運用、実請求額は未確認である。

2026-09-07の一続きE2E第1段階では、承認済みのlocalhost Bonsai 1 callを44.762秒で完了したが、入力にない商品名を生成し、桁区切り付きの明示価格範囲と未知色を欠落させたまま `ready` となったため、Outscraper前に停止した。offline修正後は、商品名、brand、model number、自由語termをSudachiPyの完全なsource spanまたはASCII語境界へ照合し、根拠のない値をqueryへ渡さない。commaが正しい3桁区切りのJPYも既存の上下限・範囲復元で扱う。商品名field過剰制約とSudachiPy連続接頭辞欠落を修正した後の承認済み最終確認は60.366秒で `ready` となり、query `超低背 ワイヤレス キーボード`、5,000〜10,000円、必須語3件、除外語1件を保持した。別の明示承認後、このqueryをOutscraperへtask作成1回・retry 0で送り、同一taskを8回pollして221.458秒で24候補を受信した。24件すべてが次期v2の正規化・typed rankingを通過し、rejectは0件だった。providerが省略した全条件、個々の順位品質、browser・UI・production E2Eは未確認である。

## 現在の注意点

- 検索処理は同期実行であり、Outscraper の完了まで画面が待機する。
- 属性抽出キャッシュは既定24時間、Outscraper生レスポンスは既定1時間再利用する。正規化・採点結果は内容と設定を含むキーで再利用する。
- Streamlitはセッションごとにランダムなキャッシュscopeを持ち、セッション間でキーを分離する。CLIは `local-cli` scopeを継続利用する。
- 現行JSONキャッシュの書込はアトミックだが、プロセス間ロック、容量上限、自動削除、利用者別の保存領域は未実装である。次期履歴のSQLite境界とは別物である。
- Outscraper は一時的な通信失敗、HTTP 429、5xxを再試行する。Bonsaiの再試行は未実装である。
- 現行cacheのファイル配置は共通であり、次期履歴も同じOS userの単一fileを使う。認証ユーザー単位のOS永続領域、構造化メトリクス、分散トレース、認証、レート制限は未実装である。
- ComfyUI、実画像生成、画像rankingは現行実装に含まれない。[次期商品検索の利用フロー](SEARCH-FLOW.md) に対応する `src/search_v2/` には、Bonsai・Cloudflare・OutscraperのHTTP境界、最大2件query、参考画像1枚と条件別偽画像、画像proxy・有界DNS・pinned-IP TLS、固定ONNX CLIP、観測値だけの商品正規化を隔離実装した。現行Bonsai request v8は、検索可能応答を最大12種類の固定field、確認待ちを `ambiguities` 1 fieldへ分け、商品名等48文字、term 32文字、各term list・typed condition・set値4件、ambiguity 2件・各96文字へ構造的に制限する。categoryは商品名へ、colorとfeaturesはtermsまたはtyped conditionへ集約し、上限内で意味を保てない場合は切断せずblocking確認待ちを要求する。adapterは省略値を完全19-field draftへ復元し、入力中の原語・trusted aliasで裏付けられたtyped conditionだけを保持する。不正だが入力に根拠のある値は自由語termへ戻し、明示JPY上下限と「不要・除外・避ける・without」の対象を商品語彙に依存せず復元する。完全intent schemaは別digestとstrict最終検証に維持する。代表fixtureはlocal Bonsai tokenizerで104 tokens、同じ意味のminified完全形式181 tokensだった。承認済みv8診断ではstrict intentとcold 53.148秒・warm 17.625秒を確認した。短縮prompt後の承認済み1 callは53.595秒・248 completion tokensだったが、adapter修正前のためblockingで停止し、Outscraperは呼び出していない。取得済み応答相当fixtureはadapter修正後にreadyとなるが、再推論は未実施である。applicationの生成token上限とHTTP timeoutを公開契約に持たず、`Session.request()` にtimeoutを設定しない。response 1 MiB上限、1 call、retry・redirect禁止、本文を保持しない7段階diagnosticも維持する。request v5はlocal modelの実応答でstrict intentまで確認済みで、EXEC-055では使用済みCSVの先頭1件を現行orchestratorへ1回だけ通し、query plan・query digestなしの `BlockingIntentReview` へ到達した。旧request v6の初期prompt benchmarkはCore i5-13600KF・WSL2・CPU版の出力1 tokenで、変更前相当cache無効の有効2件は中央値142.56秒、変更後cache warmの3件は中央値1.236秒、約115倍・99.1%短縮だった。EXEC-058では、本番相当server引数、actual Requests transport、strict adapterを使う異なる合成入力2件のlocalhost結合testで、両方のfull JSON・strict intent成功と2件目891 / 925 cached tokensを確認した。EXEC-059では同じrequest v6・同じ487 completion tokensのcold・warmを分離し、prompt処理を43.655秒から0.124秒へ353.47倍・99.72%短縮、wall全体を137.311秒から90.440秒へ1.52倍・34.13%短縮した。warm wallの99.82%はcompletion生成である。Core Ultra性能とproduction E2Eは未確認である。EXEC-055の結果もdevelopment regressionであり、blocking判断、条件分解、商品順位、未知データの品質を示さない。schema 3.0のoffline orchestrationはtyped proposal付き第1確認から `typed-ranking-v4`、完了stateまでを接続し、typed decisionをschema 2.0の表示履歴へ変換してSQLite `user_version=2` へ冪等保存できる。holdout評価と固定policyは、条件、候補、裁定、安全状態、順位をcase・category・全体へ集計し、構成不足を `ineligible`、品質未達を `fail`、全基準達成を `pass` とする。最初の適格holdoutはBonsai strict応答失敗4件を除外せず `fail` と確定し、商品順位は未測定である。旧検索artifact、旧Bonsai request v2〜v7、ranking-v3 runtime、SQLite version 1は暗黙変換しない。運用allowlist、実画像host、Windows native、Cloudflare、画像ranking、legacy `run_product_search()`、認証、API、次期UIへは未接続・未確認である。CLIP modelと受領画像はlocal working treeへ配置しただけで、Git追跡・配布はしていない。詳細は [次期検索バックエンド v2](docs/BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[TASK-008](docs/GOAL.md#task-008-次期検索フロー-v2-の実装)、[EXEC-057](docs/GOAL.md#exec-057-bonsai本番prompt-cacheとrequest-context縮小)、[EXEC-058](docs/GOAL.md#exec-058-request-v6prompt-cache-localhost結合テスト)、[EXEC-059](docs/GOAL.md#exec-059-bonsai応答時間のprompt生成分離診断)、[EXEC-060](docs/GOAL.md#exec-060-bonsai-196-token目標のcompact-wire応答)、[EXEC-061](docs/GOAL.md#exec-061-bonsai-bounded-compact-schema)、[EXEC-062](docs/GOAL.md#exec-062-outscraper単一task実商品接続試験) を参照する。

- 画像scoreは、色、外観形状、商品種別など画像で確認できる特徴だけの補助評価として設計する。有線・無線は商品名と構造化された観測属性で判定し、画像から属性を補完しない。固定CLIP入力は縦横比を維持して画像全体を224×224内へ収め、正規化後0となるモデル平均余白を使う。前項に残るAUC 0.790123457は旧center-crop profileの履歴であり、現行profileではcase1のnear/far AUCが0.759259259、接続方式だけが異なる4枚を画像上の正例へ移した補助評価がAUC 0.928571429、case2の限定診断がAUC 0.642857143・期待順位一致27/53、case3の限定診断がAUC 0.468750000・期待順位一致80/173である。2026-09-07に画像評価を再開した。初回E2E診断は正例2・負例2で不適格だったが、後続のcategory-only条件「黒い本体の電気ケトル」は実商品候補10件を正例4・負例6へCLIP前に固定し、候補を入力しないテスト用gpt-image 4方向参照と固定ONNXで正例中央値0.924253657、負例中央値0.870871561、pairwise AUC 1.0、参照pHash最小距離12となり、単一条件の事前基準を満たした。カテゴリ横断またはtyped ranking全体の合格ではないため画像rankingは無効のままである。本番の4方向参照生成は当初の予定どおりCloudflareを正本とし、gpt-imageは画像評価テストだけに使う。詳細は [EXEC-064](docs/GOAL.md#exec-064-実ブラウザ候補とgpt-image独立参照のclip診断) を参照する。

## 参照資料

- [ドキュメント目次](AGENTS.md#markdown目次)
- [最短の利用開始手順](#統合済みクイックスタート)
- [設計方針](docs/BACKEND.md#統合済み全体設計)
- [次期商品検索の利用フロー](SEARCH-FLOW.md)
- [テスト方針](docs/DEVELOPMENT.md#統合済みテスト方針)
- [フロントエンド設計](docs/FRONTEND.md)
- [バックエンド設計](docs/BACKEND.md)
- [セキュリティ](docs/SECURITY.md)
- [トラブルシューティング](docs/DEVELOPMENT.md#統合済みトラブルシューティング)


## 統合済みクイックスタート

> 統合元: `docs/QUICKSTART.md`。統合前の文書は `docs/old/` に保存する。


> **標準文書との関係:** リポジトリ概要と基本セットアップは [README.md](#amazon-explorer) を入口とする。この文書はローカル起動と外部APIを使わない確認手順を詳細化する。

### 1. 最短構成

amazon-explorer を実検索まで動かすには、次が必要である。

- Python 3.10以上
- `uv`
- OpenAI互換APIとして起動したBonsai 8B
- 有効なOutscraper APIキー
- Bonsai接続先とOutscraperへ到達できるネットワーク

Outscraperの実検索は外部APIを利用し、契約に応じて料金が発生し得る。最初は `OUTSCRAPER_LIMIT` を小さくして確認することを推奨する。

### 2. インストール

リポジトリへ移動し、ロックファイルに従って依存関係を用意する。

```sh
cd /home/products/Git_Products/amazon-explorer
uv sync --locked
```

`uv.lock` を意図的に更新する場合を除き、通常の利用開始では `--locked` を付ける。

### 3. 環境変数

サンプルをコピーし、所有者だけが読めるようにする。

```sh
test -e .env || cp .env.example .env
chmod 600 .env
```

既存の `.env` は上書きしない。すでに存在する場合は必要な設定名だけを `.env.example` と照合する。

`.env` の次の行へ実値を設定する。

```dotenv
OUTSCRAPER_API_KEY=your_api_key
```

Cloudflare Workers AIの明示承認付きlive画像試験を行う場合だけ、`CLOUDFLARE_ACCOUNT_ID`と`CLOUDFLARE_API_TOKEN`も設定する。token値はチャット、実行引数、画面キャプチャへ記録しない。

設定していない任意項目はコメントのままにする。数値、真偽値、パスの項目を空文字で有効化すると、起動時の型変換に失敗する場合がある。

既定値のまま使う場合、主要な接続設定は次である。

| 項目 | 既定値 |
|---|---|
| Bonsai URL | `http://127.0.0.1:8080/v1` |
| Bonsaiモデル名 | `Bonsai-8B.gguf` |
| Amazonドメイン | `amazon.co.jp` |
| 言語 | `ja` |
| 郵便番号 | `100-0001` |
| Outscraper取得上限 | `100` |

すべての設定名・既定値は [BACKEND.md](docs/BACKEND.md) と `.env.example`、利用上の限界は [CONSTRAINTS.md](docs/REQUIREMENTS.md#統合済み制約) を参照する。APIキーをGit管理ファイル、チャット、画面キャプチャへ貼らない。

### 4. Bonsaiを起動する

llama.cpp の `llama-server` とBonsai 8BのGGUFモデルを用意し、モデルの実パスを指定して起動する。

```sh
/path/to/llama.cpp/build/bin/llama-server \
  -m /path/to/Bonsai-8B.gguf \
  -c 8192 \
  -np 1 \
  --cache-prompt \
  --host 127.0.0.1 \
  --port 8080
```

この起動例は本番向けにprompt cacheを明示し、diskへslotを保存しない。4,096 contextは最大入力契約を満たさないため採用しない。

別ターミナルからOpenAI互換APIの疎通を確認する。

```sh
curl --fail --silent http://127.0.0.1:8080/v1/models >/dev/null \
  && echo "Bonsai API: OK"
```

別のホスト、ポート、base pathを使う場合は `.env` の `BONSAI_BASE_URL` を変更する。モデル名がサーバーの公開名と異なる場合は `BONSAI_MODEL` も合わせる。

### 5. Streamlitで起動する

```sh
uv run streamlit run app.py
```

ブラウザで表示されたURLを開く。サイドバーで次を確認する。

- `Outscraper API key: existing`
- `Bonsai Server: running`

入力例:

```text
1万円以内で白く、静かな日本語配列のワイヤレスキーボード。
テンキー付きは避けたい。
```

「検索」を押すと、Bonsai属性抽出、Outscraper取得、正規化、採点を同期実行する。Outscraperが非同期タスクを処理している間は画面が待機する。

### 6. CLIで起動する

UIを使わず上位結果を標準出力する場合:

```sh
uv run python -m src.main.run \
  "1万円以内で白く、静かな日本語配列のワイヤレスキーボード"
```

上位5件だけ表示する場合:

```sh
uv run python -m src.main.run \
  "1万円以内で白く、静かな日本語配列のワイヤレスキーボード" \
  --display-limit 5
```

`--display-limit` は表示件数だけを変える。Outscraperへ要求する取得上限は `OUTSCRAPER_LIMIT` である。

既存キャッシュを読まず、BonsaiとOutscraperから再実行する場合:

```sh
uv run python -m src.main.run \
  "1万円以内で白く、静かな日本語配列のワイヤレスキーボード" \
  --no-cache
```

`--no-cache` はキャッシュ読込だけを無効にする。新しい結果は引き続き `cache/` へ保存され、外部APIの利用も発生する。

### 7. 正常動作の目印

CLIまたはStreamlitを起動したターミナルには、検索時に次の段階が表示される。

```text
Step 1/4: Bonsaiで商品属性を抽出します
Step 2/4: Outscraperへ渡す検索クエリを選択します
Step 3/4: OutscraperでAmazon商品候補を取得します
Step 4/4: 商品候補をスコアリングします
```

Outscraperの非同期タスクではrequest IDとポーリング回数・状態が表示される。標準の進捗出力はAPIキーを表示しない。成功後は各段階のJSONが `cache/` 配下へ保存される。

同じCLI入力と設定では `local-cli` scopeの有効なキャッシュを再利用する。Streamlitはセッションごとにランダムなscopeを作るため、別セッションの検索結果を通常操作で再利用しない。

### 8. 外部APIを使わない確認

コード変更後の基本確認は外部APIを呼ばない。

```sh
uv lock --check --offline
uv run --frozen --offline --no-sync ruff check .
uv run --frozen --offline --no-sync ruff format --check .
uv run --frozen --offline --no-sync pytest -m 'not live_api'
git diff --check
```

テストのモックと、実際のBonsai・Outscraperを使う結合確認は区別する。上記テストが成功しても、APIキー、モデル、ネットワーク、Outscraper契約が正しいことまでは保証しない。

### 9. 終了

StreamlitとBonsaiサーバーは、それぞれ起動したターミナルで `Ctrl+C` を押して終了する。

検索できない場合は [TROUBLESHOOTING.md](docs/DEVELOPMENT.md#統合済みトラブルシューティング) を参照する。画面操作は [UI.md](docs/FRONTEND.md#統合済みui設計)、保存データと秘密情報の注意点は [SECURITY.md](docs/SECURITY.md) を参照する。


## ローカル辞書による検索語候補

candidate専用backendでは、CLIP用Bonsaiを維持し、任意の辞書経路で言い換え語・英訳候補を用意できる。語義選択の精度は開発段階で、候補を確認して検索語を1本選ぶ。用途・取り付け先などの関係が未解決なら検索を保留する。

依存取得は通常のoffline検証と分けて行う。

```bash
uv sync --extra lexical --frozen
```

新しい資材directoryへ、公式 `intfloat/multilingual-e5-small` revision `614241f622f53c4eeff9890bdc4f31cfecc418b3` の `onnx/model_qint8_avx512_vnni.onnx` を `encoder.onnx` として置き、同revisionの `tokenizer.json` を用意する。JMdict_e XMLと日本語WordNet 1.1 SQLiteを別途展開し、配布元の出典・hash・ライセンス通知も保存する。JMdictはCC BY-SA 4.0、WordNetは日本語版とPrinceton版の両通知を保持する。資材はrepositoryへcommitしない。公式リンクは [REFERENCES](docs/REFERENCES.md#検索語のローカル辞書と文脈モデル) に記載する。

```bash
uv run --frozen --offline --no-sync python -m tools.prepare_lexical_assets --asset-root /path/to/lexical --jmdict-xml /path/to/JMdict_e --wordnet-db /path/to/wnjpn.db
uv run --frozen --offline --no-sync pytest -q -m 'not live_api' tests/test_lexical_local_integration.py --lexical-assets /path/to/lexical
```

prepareは既存の資材を上書きせず、辞書とruntime-manifestを作る。runtimeはmanifestのSHA-256を検証し、通信せずCPUでロードする。上記テストの構文解析・辞書・encoderは実物、Bonsai・商品検索・画像・CLIPはfixture、履歴は一時SQLiteであり、本番E2Eではない。

専用 `tools.candidate_search_live_e2e` へ `--lexical-assets /path/to/lexical` を付けるとこの経路を接続する。未指定時は元queryのみで、検索語生成のBonsai呼び出しは行わない。実API実行には従来の実行条件提示・人間承認が必要。


日本語定義と曖昧時のBonsai語義選択を使う場合は、新しいdirectoryに `hotchpotch/japanese-reranker-xsmall-v2` revision `de99fd2f16c7b5df1df1bcc1d9ad2c16d88ce93a` の `onnx/model_qint8_avx2.onnx` を `encoder.onnx` として置き、同revisionのtokenizer.json/config.json・出典・ライセンスを用意する。既存のE5資材を上書きしない。

```bash
uv run --frozen --offline --no-sync python -m tools.prepare_lexical_assets --contextual --asset-root /path/to/contextual-lexical --jmdict-xml /path/to/JMdict_e --wordnet-db /path/to/wnjpn.db
uv run --frozen --offline --no-sync pytest -q -m 'not live_api' tests/test_lexical_context_local.py --lexical-assets /path/to/contextual-lexical
```

この新directoryを専用CLIの `--lexical-assets` へ渡すと、CLIP用Bonsaiに加え、商品名候補の選択・必要時の未収録名提案を最大1回使う。辞書訳を優先し、未収録の名前・英訳は人間確認前の提案として区別する。上記pytestは実小型モデルの観測済み4例の順位確認で、実Bonsaiや本番E2Eを実行しない。


構文付きの候補準備は、商品名の原文範囲と検索用候補を分けて保持します。既存contextual資材を指定すると、条件検査より先に複合語辞書検索と必要時の商品名補完を行います。候補があっても未解釈条件が残る場合は停止し、例外のproduct_reviewから候補と原文を確認できます。固定合成診断runnerはこのreviewをprivateなproduct-review.jsonへ保存します。商品名補完は検索語の未確認提案で、ランキングや商品属性の推論には使いません。 辞書候補が0件なら、Bonsaiが原文と対象だけから名称・英訳を直接推論します。この経路は生成後に辞書へ再照会せず、商品名だけの入力も対象です。候補は人間確認後に使用し、辞書の障害は候補なしとして扱いません。

```sh
uv run --frozen --offline --no-sync pytest tests/test_product_phrase.py tests/test_product_phrase_bonsai.py tests/test_product_phrase_flow.py -q
uv run --frozen --offline --no-sync pytest tests/test_product_phrase_local.py --lexical-assets /home/products/models/search-lexical-context-v2 -q
```


対象部位の切出しには、任意設定のCLIPSeg＋MobileSAM実験経路を追加した。通常環境にはSciPyを明示依存として追加し、モデル用PyTorch等はrepository外の専用環境に分離する。設定・検証範囲は [領域抽出の検証](docs/DEVELOPMENT.md#exec-105のmobilesam検証) を参照。


### Candidate画像評価のSigLIP 2設定

候補検索backendの画像比較はSigLIP 2参考画像方式を既定にする。画像承認後、正画像・偽画像と商品画像を比較し、資格条件・タイトル一致と合わせて順位を決める。モデルの用意と利用手順は[BACKEND](docs/BACKEND.md#siglip-2による全体外観評価exec-116)を参照。これはbackendへの接続で、次期フロントエンドとの接続ではない。

`tools.candidate_search_live_e2e`には`--asset-root <固定SigLIP資材の絶対path>`と`--image-python <準備済みPythonの絶対path>`を指定する。既定は`--image-model siglip2`。旧CLIPを使う場合だけ`--image-model clip`と旧CLIPの資材を明示する。推論時にモデルを自動取得せず、別環境のCPUを使用する。iGPUでの加速は未実装。新しい外部API実行には実行条件への承認が必要。
