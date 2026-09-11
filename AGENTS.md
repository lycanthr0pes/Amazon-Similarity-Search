## Instruction Priority

このリポジトリでは、以下の順序で指示を適用する。

1. `AGENTS.md`
2. `docs/DEVELOPMENT.md`
3. その他のプロジェクト文書
4. 既存コードから推測される慣習

`AGENTS.md` と `docs/DEVELOPMENT.md` が競合する場合は、`AGENTS.md` を優先する。
`docs/DEVELOPMENT.md` とその他のプロジェクト文書が競合する場合は、`docs/DEVELOPMENT.md` を優先する。

実装、修正、リファクタリング、テスト、コードレビュー、コミットメッセージ作成を行う前に、`docs/DEVELOPMENT.md` を読み、そのルールに従う。
`docs/DEVELOPMENT.md` のルールを、既存コードの慣習だけを理由に無視してはならない。

## 認証情報とコマンド出力

- トークン、PAT、API キー、パスワード、秘密鍵などの機密値を、コマンドライン引数、ログ、標準出力、標準エラー、コミット、Pull Request、またはユーザーへの回答へ露出させない。
- `gh auth token` のように機密値そのものを取得・表示するコマンドは、その値が作業に不可欠でない限り実行しない。
- `--token="$(...)"` のように、機密値をコマンドライン引数へ展開して渡さない。実行ツール、パッケージマネージャー、ラッパー、またはプロセス一覧が引数を記録・表示する可能性がある。
- 認証済み CLI の資格情報ストアや CI の Secret 機構など、機密値をコマンドラインへ展開しない認証方法を優先する。利用するツールが機密値をログ出力しないことも事前に確認する。
- 機密情報を扱う処理では、`set -x`、verbose/debug ログ、dry-run、notice などがコマンドや環境変数を出力しないか、実行前に確認する。安全な受け渡し方法を確認できない場合は実行せず、ユーザーへ報告する。
- 機密値が出力された場合は再掲せず、当該認証情報を漏えい済みとして扱う。関連する外部書き込みを停止し、失効・ローテーションと影響確認をユーザーへ案内する。

## amazon-explorer 固有の安全境界

- `.env`、`.streamlit/secrets.toml`、live API の要求・応答、利用者の検索入力、生キャッシュに含まれる機密情報または利用者データを、ログ、文書、review packet、artifact、コミットへ含めない。`.env.example` には実値を入れず、プレースホルダーだけを管理する。
- 通常の検証は事前準備済み環境で `uv run --frozen --offline --no-sync pytest -m 'not live_api'` を使う。`uv sync` は依存取得の通信を行い得るため別の環境準備として扱う。`live_api` marker や `--run-live-api` は技術的な opt-in であり、credential 利用、外部送信、課金の承認ではない。各 live 実行の直前に、送信先、要求範囲、回数・上限、credential 利用の有無、想定費用を示し、人間の明示承認を得る。
- mock、fixture、静的解析、ローカル subprocess、offline test、`nonlive_ready` を、Bonsai、Outscraper、OpenAI、Cloudflare の実サービス成功または production E2E と表現しない。
- 商品検索 LLM は現行のローカル Bonsai 経路を正本とし、OpenAI へ自動 fallback しない。candidate 経路の Bonsai 用途は CLIP 用視覚条件と、文脈に基づく商品名候補の選択・補完に限定する。検索語は任意のローカル辞書・構文解析・語義選択を使う。辞書未設定/保留時は元 query を保持する。明示的に構成した商品名補完経路では、未収録の候補を未確認として返し、人間確認前に検索へ適用しない。`src/search_v2/` は strict intent、要求・応答、正規化、画像、ランキングを含むdomain基盤であり、内部のoffline orchestrationではtyped proposal付き第1確認から `typed-ranking-v4` と表示履歴までを接続している。ただしlegacy現行パイプライン、実provider、API、UIへは未接続である。provider 変更には明示決定、互換 adapter、回帰テスト、cache 移行方針を必要とする。
- 2026-09-10の決定以降、candidate経路のBonsaiはCLIP用の視覚条件提案と、商品名候補の辞書語義ID選択・未収録名の提案だけに使う。英訳・言い換えは辞書を優先し、未収録時はBonsaiの提案と出典を分け、人間が確認した候補だけ検索へ使う。 辞書照会が正常に候補0件を返した場合は、原文だけに基づくBonsaiの商品名・英訳推論へ分岐し、生成後に辞書へ再照会しない。辞書未設定・照会失敗はこの分岐に含めない。2026-09-10の接続指示により、OPUS-MT設定時はこの分岐のBonsaiを日本語名提案だけにし、原語と提案名の英訳各1件をローカルOPUS-MTで作る。同じ句は1回だけ翻訳し、翻訳失敗では英訳をnullにして日本語候補を保持する。未設定時の従来経路と登録済み辞書の英訳を維持する。商品採点・商品本文の属性追加推論には使わず、SudachiPyと既存規則、観測値の条件判定、タイトル単語一致とCLIPで順位を決める。旧意味評価の診断やlegacy実装を根拠に、この経路へ商品評価LLMを再接続しない。
- `src/search_v2/holdout_evaluation.py` の合成fixture成功は評価契約と計算の確認であり、実Bonsaiの条件分解、実商品の属性充足、未知データの順位品質を証明しない。case1からcase3をdevelopment setとして除外し、実holdoutを開く前に用途別の品質合格基準を固定する。予測artifactへ検索文、商品本文、ASIN、生provider応答、生例外を保存しない。
- 2026-09-11の利用者の明示決定により、次期フロントエンドはこのリポジトリで自前開発する。外部納品を着手条件とする制約を解除し、`SEARCH-FLOW.md` と `docs/FRONTEND.md` を自前開発の目標仕様とする。文書の正本化に続く利用者の実装指示により、`frontend/` に画面とオフラインモックを実装した。自前開発では納品完了の確認を必要としない。実装はReact + StyleX、Figmaはレイアウトの参考とし、色・文字・装飾・操作配置は `docs/FRONTEND.md` の次期UI視覚統一契約を正本とする。任意の自然言語入力から固定の合成結果まで操作できるオフラインモックを維持し、実バックエンド・Bonsai・外部API・credentialを使わず、実サービスへ自動接続しない。React画面・合成データ・ローカル資材とタブ内履歴を実装し、検証結果は `docs/GOAL.md` のEXEC-117へ記録する。実バックエンド/API接続と本番の永続履歴は別の後続作業とする。ローカル専用・単一host・単一process・worker 1本の検索実行構成と、実サービス利用・外部送信・credential・課金の承認規則は維持する。
- 2026-09-11の利用者指示によりStreamlitを削除した。画面はReact + StyleXのオフラインモック、実検索はCLIを入口とする。Reactと実バックエンド/APIの接続は未実装である。旧 `.streamlit/secrets.toml` の漏えい防止規則は維持する。
- AI レビューの attested `pass` も、commit、push、merge、外部送信、credential 利用、課金を許可しない。これらはそれぞれ人間の明示的な権限を必要とする。
- AI レビューハーネスを操作する前に [`docs/HARNESS-RUNBOOK.md`](docs/HARNESS-RUNBOOK.md) を読む。同ファイルを実行コマンド、期待結果、停止・再実行規則の正本とし、CLI、policy、信頼境界を変更したときは関連文書と同時に更新する。

# Markdown目次

## 入口

- [`README.md`](README.md)
    - リポジトリの概要、インストール方法、使い方を説明する。
- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)
    - リポジトリの開発ルールを決定づける。

## 参照

- [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md)
    - プロダクト、実行環境、依存関係、受入条件を定義する。
- [`docs/FRONTEND.md`](docs/FRONTEND.md)
    - フロントエンド設計を定義する。
- [`docs/BACKEND.md`](docs/BACKEND.md)
    - バックエンド設計を定義する。
- [`docs/SECURITY.md`](docs/SECURITY.md)
    - セキュリティ設計を定義する。
- [`docs/DB-SCHEMA.md`](docs/DB-SCHEMA.md)
    - データ保存と論理スキーマを定義する。
- [`docs/REFERENCES.md`](docs/REFERENCES.md)
    - 開発時に参照した資料を管理する。

## 作業管理

- [`NEXT-STEPS.md`](NEXT-STEPS.md)
    - 残作業と、利用者側で用意するものを簡潔に示す。
- [`docs/ISSUES.md`](docs/ISSUES.md)
    - 問題と作業台帳への入口を管理する。
- [`docs/GOAL.md`](docs/GOAL.md)
    - プロダクトのゴールと進行中の計画を定める。
- [`docs/WORKLOG.md`](docs/WORKLOG.md)
    - 検証境界を含む開発履歴を記録する。
- [`docs/CHANGELOG.md`](docs/CHANGELOG.md)
    - 利用者・運用者に影響する統合済み変更を記録する。

## プロジェクト固有の正本

- [`SEARCH-FLOW.md`](SEARCH-FLOW.md)
    - 次期商品検索を利用する人の画面操作と確認・回復フローを定義する。
- [`docs/HARNESS-RUNBOOK.md`](docs/HARNESS-RUNBOOK.md)
    - AIレビューハーネスの実行コマンド、期待結果、停止・再実行規則を定義する。

統合前の文書は `docs/old/` に保存する。アーカイブは現行の要件、設計、手順、進行状態を上書きしない。


2026-09-11 EXEC-116の明示決定以降、candidateの画像比較既定はSigLIP 2参考画像方式（siglip2_appearance）。Bonsaiの用途制限は維持し、商品順位用LLMを追加しない。旧CLIPは明示選択と旧履歴互換に限る。SigLIP資材/別Python環境を事前準備し、新profile/runtimeで旧cacheと分離する。フロントエンドは上記の自前開発方針に従い、外部実行の境界は維持する。
