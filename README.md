# amazon-explorer

## 概要

日本語の自然文からAmazon.co.jpの商品候補を検索し、希望条件への近さで比較するアプリケーションです。

現在はCLIで実際の商品検索を利用できます。React + StyleXの既定画面はオフラインモックです。別のローカル接続入口では、固定マグカップ入力の検索語・参考画像・比較画像を確認してcandidate検索へ進めます。接続はオフライン検証済みで、実サービスの試験は別途承認して実行します。

## 技術スタック

CLIの既存検索と、`src/search_v2/` の画像比較・辞書を使う候補検索は別の経路です。Reactの既定モックに加え、固定入力の接続試験画面を設けています。

| 分野 | 技術 | 用途・構成 |
|---|---|---|
| フロントエンド | React、TypeScript、StyleX | 条件入力、画像確認、結果・履歴の画面と共通コンポーネント |
| フロントエンド開発 | Node.js 22.12以上、npm、Vite | 依存管理、開発サーバー、TypeScriptとStyleXのビルド |
| バックエンド | Python 3.11以上、Pydantic | 検索パイプライン、要求・応答・商品データの型定義と検証 |
| 設定・HTTP | pydantic-settings、python-dotenv、Requests | 環境設定の読込とBonsai・画像生成APIへの通信 |
| ローカルAPI | Starlette、ASGI、Python HTTPServer | 既存job APIと、candidateの確認操作を受け付ける単一workerのローカル接続試験入口 |
| 日本語の形態素解析 | SudachiPy、SudachiDict-core | 単語分割・正規化、原文中の条件や商品語の範囲確認 |
| 商品句の構文解析 | spaCy、GiNZA、ja-ginza | 主語・目的語・修飾関係から商品句を取り出す。任意の `lexical` 依存で有効化 |
| 検索語の辞書 | JMdict、Japanese WordNet 1.1、SQLite | 表記・語義・英訳、日本語定義・用例を保持し、商品名・言い換え・英訳の候補を作成 |
| 対比画像の辞書 | Japanese WordNet 1.1、Princeton WordNet 3.0、JMdict | 既存語義の直接反対語と部品有無の英訳を参照し、文法による否定補助・Bonsai補完へ接続 |
| 辞書の文脈照合 | ONNX Runtime、Hugging Face Tokenizers、`hotchpotch/japanese-reranker-xsmall-v2` | 原文と辞書の定義・用例の対応を評価する。旧経路は `intfloat/multilingual-e5-small` を使用 |
| ローカルLLM | Bonsai 8B、llama.cpp、GGUF | 既存CLIでは属性抽出。候補検索では視覚条件の提案と商品名候補の選択・補完に限定し、商品採点には使わない |
| 日本語から英語への翻訳 | OPUS-MT、CTranslate2、SentencePiece、sacremoses | 辞書に候補がない場合の商品句を翻訳する任意構成。INT8モデルを別Python環境のCPUで実行 |
| 商品候補の取得 | Playwright、Chromium | Amazon.co.jpの検索結果と商品詳細を日本語設定の匿名ブラウザから取得 |
| 参考・比較画像の生成 | Cloudflare Workers AI | 利用者が確認する参考画像と条件別の比較画像を生成する候補検索側のAPI境界 |
| 商品画像の比較 | SigLIP 2、PyTorch、Transformers | 候補検索の既定方式。`google/siglip2-base-patch16-224` を別Python環境で実行し、参考・比較画像と商品画像の外観を比較 |
| 旧画像比較との互換 | CLIP、ONNX Runtime | 明示選択された旧CLIP方式と旧履歴を維持 |
| 画像・数値処理 | Pillow、NumPy、SciPy | 画像の検証・変換・前処理、ベクトル計算、任意の領域解析 |
| 順位付け | scikit-learn、TF-IDF、条件判定・単語一致 | 既存CLIはテキスト類似度・価格・除外条件で採点。候補検索は否定条件（負）、タイトル一致、優先条件、希望条件、画像評価、レビュースコアの順で比較する |
| 保存 | JSON、SQLite、sessionStorage | 既存検索のキャッシュ、次期検索ジョブ・履歴、モックのタブ内履歴 |
| 開発・検証 | uv、Ruff、pytest、jsonschema、Prettier、Vitest、Playwright、GitHub Actions | Python・npm依存管理、静的検査、単体・スキーマ・ブラウザテスト、CI |

辞書とモデルは事前に取得し、資材のSHA-256を検証してローカルで読み込みます。辞書・構文解析の追加依存は `uv sync --locked --extra lexical` で準備します。辞書候補や補完された商品名は利用者が確認してから検索へ使います。[辞書資材の準備](docs/BACKEND.md#ローカル辞書資材の準備手順)と[バックエンド設計](docs/BACKEND.md)を参照してください。

React・StyleX等はMIT License、css-mediaqueryはBSD-3-Clause、Weather IconsはSIL Open Font License 1.1で提供されています。使用資材の著作権表示・ライセンス全文・変更通知は [THIRD-PARTY-NOTICES.txt](frontend/public/THIRD-PARTY-NOTICES.txt) に記載しています。

## 画像の採点

新規SigLIP 2検索では、視覚条件の文章と商品画像の比較、参考/対比画像と商品画像の比較を別々に採点します。否定・タイトル・優先・希望条件を比較した後、文章と画像の点数を優先し、同点なら画像同士の点数、レビューの順で並べます。モックと本番の検索詳細・履歴に2つの点数を表示します。旧履歴の順位は維持します。[採点方式](docs/BACKEND.md#視覚条件の文章対画像を優先する2経路exec-162)を参照してください。

## 起動方法

### フロントエンドの接続試験

準備済み環境で `frontend/` の `npm run build` を実行し、リポジトリ直下で起動します。

```sh
uv run --frozen --offline --no-sync python -m tools.browser_search_server --offline-fixture
```

`http://127.0.0.1:8765/?mode=connected` でローカルAPIとの接続を確認できます。上の起動は合成応答のみです。実モデル・APIを使う起動条件と上限は [接続試験の仕様](docs/BACKEND.md#ブラウザからの接続試験exec-124) を参照してください。任意入力・画像なし・条件編集・履歴一覧の実接続は後続です。

### Bonsaiビルドの切り替え

接続画面は条件整理の間だけBonsaiを自動起動・終了します。別ターミナルで18080番へBonsaiを起動する必要はありません。Linux/WSLではアプリ終了時の子process回収と起動排他を行います。使用中の表示が出た場合は、別のBonsai処理を終了してから再整理してください。詳細は [プロセス管理](docs/BACKEND.md#bonsaiのプロセス所有と起動競合exec-163) を参照してください。

実モデルを使う接続画面は、[bonsai-runtime.toml](bonsai-runtime.toml) の `active` を読みます。既定は `"igpu"` です。変更は次の条件整理から反映されます。

| active | 実行ファイル | 内容 |
|---|---|---|
| `original` | `/home/llama.cpp/build-original/bin/llama-server` | 元のCPUビルドを保持 |
| `optimized` | `/home/llama.cpp/build-optimized/bin/llama-server` | 前回試したOpenBLAS有効版。速度向上の保証ではありません |
| `igpu` | `/home/llama.cpp/build-igpu/bin/llama-server` | Intel Arc 140Vを指定したVulkan版 |

3ビルドは同じBonsaiモデルを使います。iGPU版は設定したGPUを起動前に照合し、GPUが使えなければ停止します。詳細は [実行設定](docs/BACKEND.md#bonsaiビルドの選択exec-161) を参照してください。上のオフラインモックはモデルを起動しません。

### オフラインモック

Node.js 22.12以上とnpmを用意し、リポジトリ直下から実行します。Python、Bonsai、APIキーは不要です。

```sh
cd frontend
npm ci
npm run dev
```

ブラウザで `http://127.0.0.1:5173/` を開きます。`npm ci` は依存パッケージを取得するため通信します。準備後の画面はフォント・画像を含めてローカル配信で動作します。

ビルドした画面を確認する場合は、`frontend/` で次を実行します。

```sh
npm run build
npm run preview
```

確認先は `http://127.0.0.1:4173/` です。`dev` は変更を即時反映する開発用、`preview` はビルド済み画面の確認用です。

### 実商品検索（CLI）

Python 3.11以上、uv、llama.cppの `llama-server`、Bonsai 8BのGGUFモデル、Node.js 22.12以上、Playwright用Chromiumを用意します。リポジトリ直下で依存関係と設定ファイルを準備します。

```sh
uv sync --locked
test -e .env || cp .env.example .env
chmod 600 .env
```

商品検索にAPIキーは不要です。既存の `.env` は上書きしません。`frontend/` で次を実行して、固定依存とChromiumを準備します（初回は配布元への通信があります）。

```sh
npm ci
npx playwright install chromium
```

検索はローカルNode workerで逐次実行し、検索語あたり最大3ページと上限件数の商品詳細を取得します。CLIの上限は `PLAYWRIGHT_LIMIT`（既定100、最大100）、candidateは24件です。CAPTCHAやページ取得失敗では停止し、有料APIへ自動切替しません。配送先は匿名Amazonの既定です。旧キャッシュを保持し、新規取得は `playwright-v3/` へ分離します。日本語詳細に加えて同じ商品の英語詳細を取得し、英語タイトル・説明・特徴を別fieldで保持します。英語のみ取得不能なら日本語商品を残し、英語側CAPTCHA後は追加英語取得を止めます。

ローカル辞書・OPUS-MTを設定したcandidate経路では、条件の同義語・英訳を準備し、日英の商品名と詳細を独立採点します。タイトルと条件ごとに高い点を採用し、否定条件の高い一致点は除外側に働きます。画像点と順位の優先順は維持します。詳細は [採点仕様](docs/BACKEND.md#条件の同義語英訳と日英最大値採点exec-133) を参照してください。

Bonsaiを別ターミナルで起動します。実行ファイルとモデルのパスは配置先に置き換えます。

```sh
/path/to/llama.cpp/build/bin/llama-server \
  -m /path/to/Bonsai-8B.gguf \
  -c 8192 \
  -np 1 \
  --cache-prompt \
  --host 127.0.0.1 \
  --port 8080
```

既定の接続先は `http://127.0.0.1:8080/v1` です。変更する場合は `.env` の `BONSAI_BASE_URL` と `BONSAI_MODEL` を合わせます。設定の詳細は [バックエンド設計](docs/BACKEND.md) を参照してください。

CLIで検索を実行します。

```sh
uv run python -m src.main.run "1万円以内の白いワイヤレスキーボード" --display-limit 5
```

実商品検索はBonsaiとOutscraperを利用し、外部APIの利用料金が発生する場合があります。起動したサーバーは各ターミナルで `Ctrl+C` を押して終了します。
