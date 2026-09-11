# ドキュメント索引

## 標準文書

このリポジトリの文書体系は `agents-setup` の標準構成を入口とし、既存文書を詳細仕様、運用手順、履歴として保持する。標準文書と詳細文書が競合する場合の優先順位は、ルートの [AGENTS.md](../AGENTS.md) と [DEVELOPMENT.md](DEVELOPMENT.md) に従う。

| 役割 | 正本 | 主な詳細資料 |
|---|---|---|
| 開発規約 | [DEVELOPMENT.md](DEVELOPMENT.md) | [PLANS.md](PLANS.md)、[AI_GUIDE.md](AI_GUIDE.md) |
| 要件 | [REQUIREMENTS.md](REQUIREMENTS.md) | [CONSTRAINTS.md](CONSTRAINTS.md)、[SEARCH-FLOW.md](SEARCH-FLOW.md) |
| フロントエンド | [FRONTEND.md](FRONTEND.md) | [UI.md](UI.md)、[UI-FLOW.md](../UI-FLOW.md) |
| バックエンド | [BACKEND.md](BACKEND.md) | [DESIGN.md](DESIGN.md)、[SEARCH-FLOW.md](SEARCH-FLOW.md) |
| セキュリティ | [SECURITY.md](SECURITY.md) | [AI_GUIDE.md](AI_GUIDE.md)、[HARNESS-RUNBOOK.md](HARNESS-RUNBOOK.md) |
| データ保存 | [DB-SCHEMA.md](DB-SCHEMA.md) | [DESIGN.md](DESIGN.md)、[TECH-DEBT-TRACKER.md](TECH-DEBT-TRACKER.md) |
| 参考資料 | [REFERENCES.md](REFERENCES.md) | この索引、外部公式資料、旧検証資料 |
| 問題・作業の入口 | [ISSUES.md](ISSUES.md) | [TASKS.md](TASKS.md)、[TODO.md](TODO.md)、[TECH-DEBT-TRACKER.md](TECH-DEBT-TRACKER.md)、個別Plan |
| ゴールと進行状態 | [GOAL.md](GOAL.md) | [TASKS.md](TASKS.md)、`docs/plans/` |
| 開発履歴 | [WORKLOG.md](WORKLOG.md) | [MEMORY.md](MEMORY.md)、個別Plan |
| 統合済み変更 | [CHANGELOG.md](CHANGELOG.md) | Git履歴、[WORKLOG.md](WORKLOG.md) |

既存文書は標準文書から参照し、役割の重複を避ける。特に `HARNESS-RUNBOOK.md` は実行コマンド、期待結果、停止・再実行規則を担い、現在状態と過去実績は `GOAL.md`、Execution Plan、`WORKLOG.md` に分ける。

## 最初に読む

| 目的 | 文書 |
|---|---|
| 開発・レビュー・文書更新のルールを確認する | [DEVELOPMENT.md](DEVELOPMENT.md) |
| 最短でセットアップして起動する | [QUICKSTART.md](QUICKSTART.md) |
| 症状から解決方法を探す | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |
| アプリが満たす要件を確認する | [REQUIREMENTS.md](REQUIREMENTS.md) |
| 現在できないこと・前提条件を確認する | [CONSTRAINTS.md](CONSTRAINTS.md) |
| 全体構成とデータフローを理解する | [DESIGN.md](DESIGN.md) |
| Bonsaiを正本とする確定検索フローを確認する | [SEARCH-FLOW.md](SEARCH-FLOW.md) |
| AIレビュー・ハーネスの実行区分、コマンド、期待結果、停止条件を確認する | [HARNESS-RUNBOOK.md](HARNESS-RUNBOOK.md) |
| プロダクトの到達点と進行中の計画を確認する | [GOAL.md](GOAL.md) |
| 利用者・運用者に影響する統合済み変更を確認する | [CHANGELOG.md](CHANGELOG.md) |

## 設計資料

| 文書 | 主題 |
|---|---|
| [DESIGN.md](DESIGN.md) | システム全体、責務分割、データフロー、キャッシュ、ランキング方針 |
| [SEARCH-FLOW.md](SEARCH-FLOW.md) | 現行Bonsai属性抽出を正本とし、Cloudflare 4方向画像、確認、Outscraper、ランキングを扱う検索フロー（domain基盤を一部実装） |
| [FRONTEND.md](FRONTEND.md) | Streamlitフロントエンドの構造、状態管理、バックエンド境界 |
| [BACKEND.md](BACKEND.md) | 実行パイプライン、外部API、設定、正規化、採点、例外 |
| [UI.md](UI.md) | 画面要素、操作、表示状態、エラー表示、改善基準 |
| [DB-SCHEMA.md](DB-SCHEMA.md) | RDB未採用の現状とJSONキャッシュの論理スキーマ |
| [SECURITY.md](SECURITY.md) | シークレット、外部通信、ログ、キャッシュ、信頼境界 |

## 作業管理

| 文書 | 使う場面 |
|---|---|
| [GOAL.md](GOAL.md) | プロダクトの到達点、非目標、進行中の計画状態を確認するとき |
| [CHANGELOG.md](CHANGELOG.md) | 利用者・運用者に影響する統合済み変更を確認するとき |
| [PLANS.md](PLANS.md) | 長時間・複雑タスクのExecution Planを作成・更新するとき |
| [EXEC-002](plans/EXEC-002-ATTESTED-AI-REVIEW-BOUNDARIES.md) | attested境界、workflow初期化、credential-free deployment check、typed outer protocol、frozen sign/judge、7/7 readiness、nonce契約・配備条件を確認するとき |
| [TASKS.md](TASKS.md) | 複数工程を持つ大規模タスクを管理するとき |
| [TODO.md](TODO.md) | 単独で完了できる小規模タスクを管理するとき |
| [TECH-DEBT-TRACKER.md](TECH-DEBT-TRACKER.md) | 実装済みだが将来の保守性や運用性に負債がある項目を追跡するとき |
| [ISSUES.md](ISSUES.md) | 再現済みの不具合、制限、調査中の問題を追跡するとき |
| [WORKLOG.md](WORKLOG.md) | 実施した変更と検証結果を時系列で残すとき |
| [MEMORY.md](MEMORY.md) | 頻繁には変わらない長期的な判断・知識を残すとき |

## 補助資料

| 文書 | 内容 |
|---|---|
| [REFERENCES.md](REFERENCES.md) | リポジトリ内の一次資料と外部公式資料 |
| [AI_GUIDE.md](AI_GUIDE.md) | TaskSpec v2、external manifest/patch anchor、TDD、snapshot、raw evidence、2役broker/frozen ledger、frozen judge、nonce、署名、人間承認の強制規約 |
| [HARNESS-RUNBOOK.md](HARNESS-RUNBOOK.md) | offline検証、host診断、trusted release、workflow初期化、credential-free deployment check、live 7-phase実行、停止・再実行規則 |

## 文書の役割分担

- `AGENTS.md` と `DEVELOPMENT.md` が作業ルールを定める。標準文書は判断の入口、既存の詳細文書は根拠・手順・履歴を保持する。
- 現在の実装事実は `src/`、`tools/`、`tests/`、`specs/`、`pyproject.toml`、`.env.example` を正とする。
- `REQUIREMENTS.md` は満たすべき振る舞い、`CONSTRAINTS.md` は前提と限界を記録する。
- `DESIGN.md` は採用した設計を記録し、計画中の候補は実装済みと混同しない。
- `ISSUES.md` は観測された問題、`TECH-DEBT-TRACKER.md` は既知の構造的負債を扱う。
- `TODO.md` は小規模作業、`TASKS.md` は複数工程の成果、`PLANS.md` は複雑タスクの遂行方法を扱う。
- `GOAL.md` はこれらの作業台帳を横断する到達点と現在状態をまとめる。
- `CHANGELOG.md` は統合済み変更を利用者・運用者向けにまとめ、詳細な検証履歴は `WORKLOG.md` に残す。
- `MEMORY.md` は安定した知識だけを残し、日々の進捗は `WORKLOG.md` へ記録する。
- `docs/old/` は統合済み旧資料と完了済みPlanの履歴アーカイブであり、現行の仕様、規約、手順、進行状態を上書きしない。

## 旧文書アーカイブ

アーカイブ全体の出典と取扱規則は [old/README.md](old/README.md) を参照する。2026-08-15の再編で内容を分配統合した旧文書は、削除直前版を `docs/old/` に保存する。現行判断には右列の統合先を使う。

| 旧ファイル | 主な統合先 |
|---|---|
| [CACHE_DESIGN.md](old/CACHE_DESIGN.md) | [DESIGN.md](DESIGN.md)、[DB-SCHEMA.md](DB-SCHEMA.md)、[SECURITY.md](SECURITY.md)、[TECH-DEBT-TRACKER.md](TECH-DEBT-TRACKER.md) |
| [DATA_MODEL_SPEC.md](old/DATA_MODEL_SPEC.md) | [BACKEND.md](BACKEND.md)、[DB-SCHEMA.md](DB-SCHEMA.md)、[REQUIREMENTS.md](REQUIREMENTS.md) |
| [ENVIRONMENT_VARIABLES.md](old/ENVIRONMENT_VARIABLES.md) | [BACKEND.md](BACKEND.md)、[QUICKSTART.md](QUICKSTART.md)、[CONSTRAINTS.md](CONSTRAINTS.md)、[SECURITY.md](SECURITY.md) |
| [EXTERNAL_API_SPEC.md](old/EXTERNAL_API_SPEC.md) | [BACKEND.md](BACKEND.md)、[SECURITY.md](SECURITY.md)、[TROUBLESHOOTING.md](TROUBLESHOOTING.md)、[REFERENCES.md](REFERENCES.md) |
| [PRODUCTION_DESIGN_GUIDE.md](old/PRODUCTION_DESIGN_GUIDE.md) | [DESIGN.md](DESIGN.md)、[SECURITY.md](SECURITY.md)、[TECH-DEBT-TRACKER.md](TECH-DEBT-TRACKER.md)、[TASKS.md](TASKS.md) |
| [README_dev.md](old/README_dev.md) | [DESIGN.md](DESIGN.md)、[BACKEND.md](BACKEND.md)、[FRONTEND.md](FRONTEND.md)、[QUICKSTART.md](QUICKSTART.md) |

完了済みPlanも、現行の進行状態と混同しないよう `docs/old/plans/` に保存する。

| 完了済みPlan | 位置付け | 現行の参照先 |
|---|---|---|
| [EXEC-001](old/plans/EXEC-001-AI-REVIEW-TDD-HARNESS.md) | TASK-006 bootstrapとTDDパイロットの履歴 | [EXEC-002](plans/EXEC-002-ATTESTED-AI-REVIEW-BOUNDARIES.md)、[HARNESS-RUNBOOK.md](HARNESS-RUNBOOK.md) |
| [EXEC-003](old/plans/EXEC-003-SEARCH-FLOW-V2-BACKEND.md) | TASK-008第1マイルストーンと置換済みprovider判断の履歴 | [SEARCH-FLOW.md](SEARCH-FLOW.md)、[TASKS.md](TASKS.md) |

## 変更時の更新先

| 変更内容 | 同時に確認する文書 |
|---|---|
| 開発規約・検証方法 | `DEVELOPMENT.md`、`AGENTS.md` |
| 環境変数・既定値 | `BACKEND.md`、`QUICKSTART.md`、`CONSTRAINTS.md`、`.env.example` |
| Pydanticモデル | `BACKEND.md`、`DB-SCHEMA.md`、`REQUIREMENTS.md` |
| UIの入力・表示・状態 | `FRONTEND.md`、`UI.md`、`QUICKSTART.md` |
| 商品検索フロー、Bonsai抽出、画像生成、承認状態、ranking profile | `SEARCH-FLOW.md`、`REQUIREMENTS.md`、`DESIGN.md`、`BACKEND.md`、`FRONTEND.md`、`UI.md`、`SECURITY.md`、`CONSTRAINTS.md` |
| 外部API・再試行・URL制約 | `BACKEND.md`、`SECURITY.md`、`TROUBLESHOOTING.md` |
| キャッシュキー・TTL・保存形式 | `DESIGN.md`、`DB-SCHEMA.md`、`SECURITY.md` |
| 既知の制限または不具合 | `CONSTRAINTS.md`、`ISSUES.md`、必要に応じて `TECH-DEBT-TRACKER.md` |
| 大規模な将来作業 | `TASKS.md`。着手時は `PLANS.md` に従ってExecution Planを作る |
| AIレビュー、TDD証拠、ハーネス契約 | `AI_GUIDE.md`、`HARNESS-RUNBOOK.md`、対応する `docs/plans/`、`SECURITY.md` |
| ゴール・問題・履歴・統合済み変更 | 順に `GOAL.md`、`ISSUES.md`、`WORKLOG.md`、`CHANGELOG.md` |

## 検証

文書変更では少なくとも次を確認する。

```sh
git diff --check
```

コードの仕様を変更した場合は、文書確認に加えて次も実行する。

```sh
uv run --frozen --offline --no-sync ruff check .
uv run --frozen --offline --no-sync ruff format --check .
uv run --frozen --offline --no-sync pytest -m 'not live_api'
```
