# amazon-explorer

## 概要

日本語の自然文からAmazon.co.jpの商品候補を検索し、希望条件への近さで比較するアプリケーションです。

現在はCLIで実際の商品検索を利用できます。React + StyleXのフロントエンドはオフラインモックとして実装しており、入力から条件・画像の確認、商品調査、結果・検索履歴まで操作できます。モックの条件・画像・商品は固定の合成データで、実バックエンドや外部APIには未接続です。

## 技術スタック

CLIの既存検索と、`src/search_v2/` の画像比較・辞書を使う候補検索は別の経路です。React画面は固定データのオフラインモックで、以下の実検索バックエンドには未接続です。

| 分野 | 技術 | 用途・構成 |
|---|---|---|
| フロントエンド | React、TypeScript、StyleX | 条件入力、画像確認、結果・履歴の画面と共通コンポーネント |
| フロントエンド開発 | Node.js 22.12以上、npm、Vite | 依存管理、開発サーバー、TypeScriptとStyleXのビルド |
| バックエンド | Python 3.11以上、Pydantic | 検索パイプライン、要求・応答・商品データの型定義と検証 |
| 設定・HTTP | pydantic-settings、python-dotenv、Requests | 環境設定の読込とBonsai・商品検索APIへの通信 |
| ローカルAPI | Starlette、ASGI | 次期検索ジョブの投入・状態取得・取消・履歴取得。サーバー起動構成とReact接続は未実装 |
| 日本語の形態素解析 | SudachiPy、SudachiDict-core | 単語分割・正規化、原文中の条件や商品語の範囲確認 |
| 商品句の構文解析 | spaCy、GiNZA、ja-ginza | 主語・目的語・修飾関係から商品句を取り出す。任意の `lexical` 依存で有効化 |
| 検索語の辞書 | JMdict、Japanese WordNet 1.1、SQLite | 表記・語義・英訳、日本語定義・用例を保持し、商品名・言い換え・英訳の候補を作成 |
| 辞書の文脈照合 | ONNX Runtime、Hugging Face Tokenizers、`hotchpotch/japanese-reranker-xsmall-v2` | 原文と辞書の定義・用例の対応を評価する。旧経路は `intfloat/multilingual-e5-small` を使用 |
| ローカルLLM | Bonsai 8B、llama.cpp、GGUF | 既存CLIでは属性抽出。候補検索では視覚条件の提案と商品名候補の選択・補完に限定し、商品採点には使わない |
| 日本語から英語への翻訳 | OPUS-MT、CTranslate2、SentencePiece、sacremoses | 辞書に候補がない場合の商品句を翻訳する任意構成。INT8モデルを別Python環境のCPUで実行 |
| 商品候補の取得 | Outscraper Amazon Products API | Amazon.co.jpの商品候補取得と非同期タスクの完了待ち |
| 参考・比較画像の生成 | Cloudflare Workers AI | 利用者が確認する参考画像と条件別の比較画像を生成する候補検索側のAPI境界 |
| 商品画像の比較 | SigLIP 2、PyTorch、Transformers | 候補検索の既定方式。`google/siglip2-base-patch16-224` を別Python環境で実行し、参考・比較画像と商品画像の外観を比較 |
| 旧画像比較との互換 | CLIP、ONNX Runtime | 明示選択された旧CLIP方式と旧履歴を維持 |
| 画像・数値処理 | Pillow、NumPy、SciPy | 画像の検証・変換・前処理、ベクトル計算、任意の領域解析 |
| 順位付け | scikit-learn、TF-IDF、条件判定・単語一致 | 既存CLIはテキスト類似度・価格・除外条件で採点。候補検索は必須条件を優先し、タイトル一致と画像比較を組み合わせる |
| 保存 | JSON、SQLite、sessionStorage | 既存検索のキャッシュ、次期検索ジョブ・履歴、モックのタブ内履歴 |
| 開発・検証 | uv、Ruff、pytest、jsonschema、Prettier、Vitest、Playwright、GitHub Actions | Python・npm依存管理、静的検査、単体・スキーマ・ブラウザテスト、CI |

辞書とモデルは事前に取得し、資材のSHA-256を検証してローカルで読み込みます。辞書・構文解析の追加依存は `uv sync --locked --extra lexical` で準備します。辞書候補や補完された商品名は利用者が確認してから検索へ使います。[辞書資材の準備](docs/BACKEND.md#ローカル辞書資材の準備手順)と[バックエンド設計](docs/BACKEND.md)を参照してください。

React・StyleX等はMIT License、css-mediaqueryはBSD-3-Clause、Weather IconsはSIL Open Font License 1.1で提供されています。使用資材の著作権表示・ライセンス全文・変更通知は [THIRD-PARTY-NOTICES.txt](frontend/public/THIRD-PARTY-NOTICES.txt) に記載しています。

## 起動方法

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

Python 3.11以上、uv、llama.cppの `llama-server`、Bonsai 8BのGGUFモデル、Outscraper APIキーを用意します。リポジトリ直下で依存関係と設定ファイルを準備します。

```sh
uv sync --locked
test -e .env || cp .env.example .env
chmod 600 .env
```

`.env` の `OUTSCRAPER_API_KEY` を設定します。既存の `.env` は上書きせず、APIキーをGit管理ファイルへ書かないでください。

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
