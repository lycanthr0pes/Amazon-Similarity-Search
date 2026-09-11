# 旧Markdownアーカイブ

このディレクトリは、`agents-setup` テンプレートの正本文書へ統合したMarkdownと、完了済み・置換済みの履歴資料を保存する。ここにある本文は移動時点のスナップショットであり、現行の要件、設計、手順、タスク状態を上書きしない。

現行文書の入口は [AGENTS.mdのMarkdown目次](../../AGENTS.md#markdown目次) と [REFERENCES.mdの統合元一覧](../REFERENCES.md#統合元文書とアーカイブ) とする。商品検索の技術仕様とUI操作はルート [SEARCH-FLOW.md](../../SEARCH-FLOW.md)、AIレビューハーネスの操作は [HARNESS-RUNBOOK.md](../HARNESS-RUNBOOK.md)、進行中のTaskとPlanは [GOAL.md](../GOAL.md) を正本とする。

## 統合元文書

- セットアップ: [QUICKSTART.md](QUICKSTART.md)
- 要件・設計・UI: [CONSTRAINTS.md](CONSTRAINTS.md)、[DESIGN.md](DESIGN.md)、[UI.md](UI.md)
- 開発・運用: [AI_GUIDE.md](AI_GUIDE.md)、[PLANS.md](PLANS.md)、[TROUBLESHOOTING.md](TROUBLESHOOTING.md)、[TESTING.md](TESTING.md)
- 作業管理: [TASKS.md](TASKS.md)、[TODO.md](TODO.md)、[TECH-DEBT-TRACKER.md](TECH-DEBT-TRACKER.md)、[MEMORY.md](MEMORY.md)
- 旧索引: [INDEX.md](INDEX.md)
- 検索とUIフローの統合元: [SEARCH-FLOW.md](SEARCH-FLOW.md)、[UI-FLOW.md](UI-FLOW.md)

## Execution Plan

- [EXEC-001](plans/EXEC-001-AI-REVIEW-TDD-HARNESS.md): TASK-006 bootstrapとTDDパイロットの完了履歴
- [EXEC-002](plans/EXEC-002-ATTESTED-AI-REVIEW-BOUNDARIES.md): [GOAL.mdの進行中Plan](../GOAL.md#exec-002-attested-ai-review境界の実装) へ統合した原本
- [EXEC-003](plans/EXEC-003-SEARCH-FLOW-V2-BACKEND.md): TASK-008第1マイルストーンと置換済みprovider判断の完了履歴

## 旧設計・検証・実行時Markdown

- 2026-08-15以前の旧設計資料: [CACHE_DESIGN.md](CACHE_DESIGN.md)、[DATA_MODEL_SPEC.md](DATA_MODEL_SPEC.md)、[ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md)、[EXTERNAL_API_SPEC.md](EXTERNAL_API_SPEC.md)、[PRODUCTION_DESIGN_GUIDE.md](PRODUCTION_DESIGN_GUIDE.md)、[README_dev.md](README_dev.md)
- 段階別の旧検証資料: [examples/README.md](examples/README.md) 以下
- 実行用promptの旧Markdown: `runtime/` 以下。現行実行ファイルは `src/clients/bonsai_prompt.txt` と `specs/prompts/*.txt`

## 取扱規則

- 現行仕様や手順の根拠としてアーカイブだけを参照しない。
- アーカイブ本文内の相対リンクとパスは作成当時の配置を示す場合があり、移動後の現行リンクとして保証しない。
- 履歴本文は原則変更せず、統合先・現行パスは [REFERENCES.md](../REFERENCES.md#統合元文書とアーカイブ) で確認する。
- 新しい進行中Planは [DEVELOPMENT.mdのExecution Plan規約](../DEVELOPMENT.md#統合済みexecution-plan規約) に従って `GOAL.md` へ追記し、完了した履歴原本だけを `docs/old/plans/` に置く。
