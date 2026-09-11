# 参考資料

## 目的

amazon-explorer の仕様確認、実装変更、障害調査で参照する一次資料をまとめる。アプリの現行挙動はコードとテスト、外部サービスやライブラリの現行仕様は対応する公式資料を正とする。

## 情報源の優先順位

対象ごとに情報源を使い分ける。

1. アプリが現在どう動くかは、現行コードとテストを確認する
2. 採用バージョン、Python要件、設定可能な名前は、`pyproject.toml`、`uv.lock`、`.env.example` を確認する
3. 外部サービスやライブラリが現在何を保証するかは、対象バージョンに対応する公式資料を確認する
4. 設計意図と運用手順は `docs/` の参照資料を確認し、上記の一次資料と矛盾する場合は文書を修正する
5. `docs/old/examples/` は経緯の確認だけに使い、現行仕様の根拠にはしない

公式仕様と現行コードが食い違う場合は、外部仕様に合わせて動くと推測せず、互換性の問題としてコード・テスト・文書を同時に確認する。

## リポジトリ内の一次資料

| 確認対象 | 一次資料 |
|---|---|
| 作業指示と開発規則 | [`AGENTS.md`](../AGENTS.md)、[`docs/DEVELOPMENT.md`](DEVELOPMENT.md) |
| ゴール、問題、開発履歴、統合済み変更 | [`docs/GOAL.md`](GOAL.md)、[`docs/ISSUES.md`](ISSUES.md)、[`docs/WORKLOG.md`](WORKLOG.md)、[`docs/CHANGELOG.md`](CHANGELOG.md) |
| 依存関係・Python要件 | [`pyproject.toml`](../pyproject.toml)、`uv.lock` |
| 設定名・既定値・制約 | [`src/config.py`](../src/config.py)、[`.env.example`](../.env.example) |
| データモデル | [`src/schemas.py`](../src/schemas.py) |
| 処理順序・キャッシュキー | [`src/main/run.py`](../src/main/run.py) |
| 商品検索providerの方針 | [`docs/DEVELOPMENT.md`](DEVELOPMENT.md#商品検索-provider)、[`docs/BACKEND.md`](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装) |
| 次期商品検索の利用フロー | [`SEARCH-FLOW.md`](../SEARCH-FLOW.md) |
| 次期検索の技術契約 | [`docs/BACKEND.md`](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装) |
| local job・履歴HTTP API | [`src/search_v2/production_api.py`](../src/search_v2/production_api.py)、[`tests/test_search_v2_production_api.py`](../tests/test_search_v2_production_api.py)、[EXEC-076](GOAL.md#exec-076-local検索job履歴http-api) |
| 次期検索の段階別offline orchestration | [`src/search_v2/orchestrator.py`](../src/search_v2/orchestrator.py)、[`tests/test_search_v2_orchestrator.py`](../tests/test_search_v2_orchestrator.py)、[EXEC-017](GOAL.md#exec-017-offline検索orchestration)、[EXEC-039](GOAL.md#exec-039-型付きranking-v4のoffline検索経路移行) |
| テスト方針と受入確認 | [`docs/DEVELOPMENT.md`](DEVELOPMENT.md#統合済みテスト方針) |
| Bonsai通信 | [`src/clients/bonsai_client.py`](../src/clients/bonsai_client.py) |
| Bonsai v2 network非依存応答境界 | [`src/search_v2/bonsai_adapter.py`](../src/search_v2/bonsai_adapter.py)、[EXEC-004](GOAL.md#exec-004-bonsai-v2-strict応答境界) |
| Bonsai v2要求・HTTP境界 | [`src/search_v2/bonsai_request.py`](../src/search_v2/bonsai_request.py)、[`src/search_v2/bonsai_http.py`](../src/search_v2/bonsai_http.py)、[`tests/test_search_v2_bonsai_http.py`](../tests/test_search_v2_bonsai_http.py)、[EXEC-013](GOAL.md#exec-013-bonsai-v2-http-transport) |
| 次期検索tokenizer・query plan | [`src/search_v2/tokenizer.py`](../src/search_v2/tokenizer.py)、[`src/search_v2/query_planner.py`](../src/search_v2/query_planner.py)、[EXEC-005](GOAL.md#exec-005-決定的検索tokenizer) |
| 次期検索の承認state・single-use token・利用量予約 | [`src/search_v2/approval.py`](../src/search_v2/approval.py)、[`src/search_v2/state_machine.py`](../src/search_v2/state_machine.py)、[`src/search_v2/usage_ledger.py`](../src/search_v2/usage_ledger.py)、[EXEC-006](GOAL.md#exec-006-2段階承認と費用予約境界) |
| Cloudflare v2要求・HTTP・応答・画像正規化・途中失敗回復境界 | [`src/search_v2/cloudflare_request.py`](../src/search_v2/cloudflare_request.py)、[`src/search_v2/cloudflare_http.py`](../src/search_v2/cloudflare_http.py)、[`src/search_v2/state_machine.py`](../src/search_v2/state_machine.py)、[`src/search_v2/orchestrator.py`](../src/search_v2/orchestrator.py)、[`tests/test_search_v2_cloudflare_http.py`](../tests/test_search_v2_cloudflare_http.py)、[`tests/test_search_v2_orchestrator.py`](../tests/test_search_v2_orchestrator.py)、[EXEC-016](GOAL.md#exec-016-cloudflare-http応答と画像正規化)、[EXEC-018](GOAL.md#exec-018-cloudflare画像生成失敗後の回復state)、[EXEC-070](GOAL.md#exec-070-cloudflare応答画像の安全な形式正規化) |
| LLM systemプロンプト | [`src/clients/bonsai_prompt.txt`](../src/clients/bonsai_prompt.txt) |
| Outscraper通信・再試行・URL検証 | [`src/clients/outscraper_client.py`](../src/clients/outscraper_client.py) |
| Outscraper v2要求・認可・HTTP・task・polling境界 | [`src/search_v2/outscraper_contract.py`](../src/search_v2/outscraper_contract.py)、[`src/search_v2/outscraper_request.py`](../src/search_v2/outscraper_request.py)、[`src/search_v2/outscraper_http.py`](../src/search_v2/outscraper_http.py)、[`tests/test_search_v2_outscraper_http.py`](../tests/test_search_v2_outscraper_http.py)、[EXEC-014](GOAL.md#exec-014-outscraper-v2-httptaskpolling境界)、[EXEC-039](GOAL.md#exec-039-型付きranking-v4のoffline検索経路移行) |
| 属性抽出 | [`src/services/user_attribute_extraction.py`](../src/services/user_attribute_extraction.py) |
| 商品正規化 | [`src/services/amazon_product_normalization.py`](../src/services/amazon_product_normalization.py) |
| 次期商品正規化 | [`src/search_v2/product_normalization.py`](../src/search_v2/product_normalization.py)、[`tests/test_search_v2_product_normalization.py`](../tests/test_search_v2_product_normalization.py)、[EXEC-009](GOAL.md#exec-009-決定的商品正規化と未知属性境界) |
| 次期画像proxy・類似度境界 | [`src/search_v2/image_proxy.py`](../src/search_v2/image_proxy.py)、[`src/search_v2/image_similarity.py`](../src/search_v2/image_similarity.py)、[`src/search_v2/image_similarity_onnx.py`](../src/search_v2/image_similarity_onnx.py)、[`tests/test_search_v2_image_proxy.py`](../tests/test_search_v2_image_proxy.py)、[`tests/test_search_v2_image_similarity.py`](../tests/test_search_v2_image_similarity.py)、[`tests/test_search_v2_image_similarity_quality.py`](../tests/test_search_v2_image_similarity_quality.py)、[`tests/test_search_v2_image_similarity_quality_case2.py`](../tests/test_search_v2_image_similarity_quality_case2.py)、[`tests/test_search_v2_image_similarity_quality_case3.py`](../tests/test_search_v2_image_similarity_quality_case3.py)、[EXEC-010](GOAL.md#exec-010-安全な画像取得phash固定clip境界)、[EXEC-026](GOAL.md#exec-026-単一条件の複数画像clip-characterization)、[EXEC-031](GOAL.md#exec-031-case2固定候補と自己参照除外clip診断)、[EXEC-032](GOAL.md#exec-032-全体保持clip前処理とcase3準備)、[EXEC-033](GOAL.md#exec-033-case3固定候補と自己参照除外clip診断) |
| 検索語選択 | [`src/services/outscraper_search_select.py`](../src/services/outscraper_search_select.py) |
| 分かち書き・文字列一致 | [`src/services/text_processing.py`](../src/services/text_processing.py) |
| 現行ランキング | [`src/services/product_scoring.py`](../src/services/product_scoring.py) |
| 次期ranking v3 | [`src/search_v2/ranking.py`](../src/search_v2/ranking.py)、[`tests/test_search_v2_ranking.py`](../tests/test_search_v2_ranking.py)、[EXEC-029](GOAL.md#exec-029-高評価レビュー件数を使うranking-v3)。v2導入履歴は[EXEC-011](GOAL.md#exec-011-決定的ランキングv2とスコア内訳) |
| 型付き条件・商品証拠・裁定 | [`src/search_v2/typed_requirements.py`](../src/search_v2/typed_requirements.py)、[`src/search_v2/typed_intent_adapter.py`](../src/search_v2/typed_intent_adapter.py)、[`src/search_v2/product_evidence.py`](../src/search_v2/product_evidence.py)、[`src/search_v2/requirement_evaluation.py`](../src/search_v2/requirement_evaluation.py)、[EXEC-035](GOAL.md#exec-035-型付き条件と証拠裁定の最小domain実装)、[EXEC-036](GOAL.md#exec-036-観測商品から型付き証拠へのadapter)、[EXEC-037](GOAL.md#exec-037-bonsai型付き条件候補adapter) |
| typed ranking v4 | [`src/search_v2/typed_ranking.py`](../src/search_v2/typed_ranking.py)、[`tests/test_search_v2_typed_ranking.py`](../tests/test_search_v2_typed_ranking.py)、[EXEC-038](GOAL.md#exec-038-型付き条件ranking-v4境界)、[EXEC-039](GOAL.md#exec-039-型付きranking-v4のoffline検索経路移行) |
| typed ranking v4のholdout評価契約 | [`src/search_v2/holdout_evaluation.py`](../src/search_v2/holdout_evaluation.py)、[`tests/test_search_v2_holdout_evaluation.py`](../tests/test_search_v2_holdout_evaluation.py)、[BACKEND.mdの評価契約](BACKEND.md#148-未使用holdoutの評価契約)、[EXEC-040](GOAL.md#exec-040-未使用holdoutの評価契約と集計境界) |
| holdout品質判定と最初の適用結果 | [`src/search_v2/holdout_acceptance.py`](../src/search_v2/holdout_acceptance.py)、[`tests/test_search_v2_holdout_acceptance.py`](../tests/test_search_v2_holdout_acceptance.py)、[BACKEND.mdの最初の評価](BACKEND.md#1410-最初の適格holdout評価)、[EXEC-041](GOAL.md#exec-041-holdout品質合格ポリシーの固定)、[EXEC-042](GOAL.md#exec-042-固定済み基準による未使用holdout評価) |
| 次期検索後半pipeline・完了state | [`src/search_v2/product_pipeline.py`](../src/search_v2/product_pipeline.py)、[`src/search_v2/state_machine.py`](../src/search_v2/state_machine.py)、[`tests/test_search_v2_product_pipeline.py`](../tests/test_search_v2_product_pipeline.py)、[EXEC-015](GOAL.md#exec-015-検索後半pipelineと完了state)、[EXEC-039](GOAL.md#exec-039-型付きranking-v4のoffline検索経路移行) |
| 次期検索のtyped表示履歴・SQLite v2 | [`src/search_v2/history_snapshot.py`](../src/search_v2/history_snapshot.py)、[`src/search_v2/history_repository.py`](../src/search_v2/history_repository.py)、[`tests/test_search_v2_history_snapshot.py`](../tests/test_search_v2_history_snapshot.py)、[`tests/test_search_v2_history_repository.py`](../tests/test_search_v2_history_repository.py)、[EXEC-039](GOAL.md#exec-039-型付きranking-v4のoffline検索経路移行) |
| JSONキャッシュ | [`src/repositories/cache_repository.py`](../src/repositories/cache_repository.py)、[`src/utilities/json_editor.py`](../src/utilities/json_editor.py) |
| Streamlit画面 | [`src/ui/streamlit_ui.py`](../src/ui/streamlit_ui.py)、[`app.py`](../app.py) |
| 回帰仕様 | [`tests/`](../tests/) |
| AIレビューの基本契約・policy・judge・CLI | [`tools/ai_review/models.py`](../tools/ai_review/models.py)、[`tools/ai_review/policy.py`](../tools/ai_review/policy.py)、[`tools/ai_review/judge.py`](../tools/ai_review/judge.py)、[`tools/ai_review/cli.py`](../tools/ai_review/cli.py) |
| trusted release・workflow初期化・import前preflight・deployment check | [`tools/ai_review/runtime_release.py`](../tools/ai_review/runtime_release.py)、[`tools/ai_review/workflow_init.py`](../tools/ai_review/workflow_init.py)、[`tools/ai_review/external_launcher.py`](../tools/ai_review/external_launcher.py)、[`tools/ai_review/preflight.py`](../tools/ai_review/preflight.py)、[`tools/ai_review/deployment_check.py`](../tools/ai_review/deployment_check.py) |
| sensitive path・snapshot・offline evidence | [`tools/ai_review/sensitive_paths.py`](../tools/ai_review/sensitive_paths.py)、[`tools/ai_review/snapshot.py`](../tools/ai_review/snapshot.py)、[`tools/ai_review/offline_runner.py`](../tools/ai_review/offline_runner.py) |
| offline prepare/outer/finalize | [`tools/ai_review/offline_phase_protocol.py`](../tools/ai_review/offline_phase_protocol.py)、[`tools/ai_review/offline_outer_executor.py`](../tools/ai_review/offline_outer_executor.py)、[`tools/ai_review/phase_execution_adapters.py`](../tools/ai_review/phase_execution_adapters.py) |
| bounded packet・broker・固定egress | [`tools/ai_review/review_packet.py`](../tools/ai_review/review_packet.py)、[`tools/ai_review/codex_adapter.py`](../tools/ai_review/codex_adapter.py)、[`tools/ai_review/broker_executor.py`](../tools/ai_review/broker_executor.py)、[`tools/ai_review/broker_egress_provisioner.py`](../tools/ai_review/broker_egress_provisioner.py) |
| broker prepare/outer/frozen ledger/finalize | [`tools/ai_review/broker_phase_protocol.py`](../tools/ai_review/broker_phase_protocol.py)、[`tools/ai_review/broker_outer_executor.py`](../tools/ai_review/broker_outer_executor.py)、[`tools/ai_review/phase_execution_adapters.py`](../tools/ai_review/phase_execution_adapters.py) |
| Ed25519・frozen input復元・nonce ledger・attested judge | [`tools/ai_review/attestation.py`](../tools/ai_review/attestation.py)、[`tools/ai_review/nonce_ledger.py`](../tools/ai_review/nonce_ledger.py)、[`tools/ai_review/coordinator_attestation_inputs.py`](../tools/ai_review/coordinator_attestation_inputs.py)、[`tools/ai_review/attested_judge.py`](../tools/ai_review/attested_judge.py) |
| 7-phase protocol・outer workflow | [`tools/ai_review/phase_protocol.py`](../tools/ai_review/phase_protocol.py)、[`tools/ai_review/outer_driver.py`](../tools/ai_review/outer_driver.py)、[`tools/ai_review/outer_workflow_state.py`](../tools/ai_review/outer_workflow_state.py)、[`tools/ai_review/outer_workflow_runtime.py`](../tools/ai_review/outer_workflow_runtime.py)、[`tools/ai_review/external_launcher.py`](../tools/ai_review/external_launcher.py)、[`tools/ai_review/production_cli.py`](../tools/ai_review/production_cli.py)、[`tools/ai_review/coordinator_workflow_ops.py`](../tools/ai_review/coordinator_workflow_ops.py)、[`tools/ai_review/coordinator_workflow_inputs.py`](../tools/ai_review/coordinator_workflow_inputs.py) |
| AIレビューのJSON Schema、task、policy | [`specs/`](../specs/) |
| 独立reviewer / adversary prompt | [`specs/prompts/`](../specs/prompts/) |
| テスト時ネットワーク方針 | [`tests/conftest.py`](../tests/conftest.py)、[`tests/test_network_policy.py`](../tests/test_network_policy.py) |
| 決定論的CIゲート | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) |

## 外部の公式資料

| 対象 | 公式資料 | このリポジトリでの用途 |
|---|---|---|
| uv | [uv documentation](https://docs.astral.sh/uv/) | 依存同期、コマンド実行、ロックファイル管理 |
| uv GitHub Actions | [Using uv in GitHub Actions](https://docs.astral.sh/uv/guides/integration/github/) | setup-uvの固定版、Python matrix、locked sync |
| Streamlit | [Streamlit documentation](https://docs.streamlit.io/) | ローカルWeb UI、session state、表示キャッシュ |
| Pydantic | [Pydantic documentation](https://docs.pydantic.dev/latest/) | 入出力モデル検証 |
| Starlette | [Applications](https://www.starlette.io/applications/)、[Routing](https://www.starlette.io/routing/)、[Requests](https://www.starlette.io/requests/)、[Responses](https://www.starlette.io/responses/) | local ASGI application factory、method/path routing、request header・client address、固定JSON response |
| Pydantic Settings | [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) | `.env` と環境変数の読込・検証 |
| Requests | [Requests documentation](https://requests.readthedocs.io/) | Bonsai・Outscraper HTTP通信 |
| scikit-learn | [scikit-learn documentation](https://scikit-learn.org/stable/) | TF-IDFとコサイン類似度 |
| SudachiPy | [WorksApplications/SudachiPy](https://github.com/WorksApplications/SudachiPy) | 日本語の正規化と分かち書き |
| llama.cpp server | [llama-server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) | Bonsai GGUFモデルのOpenAI互換API提供。2026-09-05のlocal version 9294では `server-common.cpp` と `chat-auto-parser-generator.cpp` も確認し、schemaなしの `json_object` が空schemaとなってJinja生成grammarを有効化しないこと、既定 `n_predict=-1`、上限停止が `length`、EOS・停止語が `stop` へ写像されることを記録した。`response_format.schema` に渡す非空の生成用schemaは同versionのC++ `json_schema_to_grammar()` と同梱Python converterでmodel・HTTPなしに変換確認した。2026-09-06には同versionのhelpでprompt KV再利用の `--cache-prompt` と、disk slot保存が別の `--slot-save-path` であることを確認し、本番起動例へ前者だけを明示した |
| Outscraper | [Amazon Products API](https://docs.outscraper.com/endpoints/amazon-products/)、[Request Results API](https://docs.outscraper.com/endpoints/requests-requestid/)、[OpenAPI JSON](https://docs.outscraper.com/api-docs-data.json)、[Amazon Products API pricing](https://outscraper.com/amazon-products-api/) | 2026-09-08確認。GET、反復 `query` によるbatch、query当たりの `limit` 既定24、`amazon.co.jp`、`ja`、required `async`、作成応答のrequest ID・`Pending`・結果URL、結果取得の `Pending`・`Success`・`Failure`、server URL。料金は月間先頭500商品が無料、501〜5,000商品が2 USD/1,000商品、5,000商品超が1 USD/1,000商品。実行直前に再確認し、将来料金として固定しない |
| pytest | [pytest documentation](https://docs.pytest.org/) | 回帰テスト |
| Ruff | [Ruff documentation](https://docs.astral.sh/ruff/) | lintとformat確認 |
| Codex CLI | [Non-interactive mode](https://developers.openai.com/codex/noninteractive/) | dry-run argvの `exec`、`--ephemeral`、`--sandbox`、`--ignore-user-config`、`--output-schema`。OS隔離やattestationの根拠にはしない |
| GPT-5.6移行・推論量 | [GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model) | role別reasoning effort、persisted reasoning、prompt cache、verbosityの選択 |
| GPT-5.6 Sol | [GPT-5.6 Sol model](https://developers.openai.com/api/docs/models/gpt-5.6-sol) | 1.05M context、128K max output、対応effort、default-tier単価、272K input超の料金境界の確認 |
| GPT-5.6 Luna | [GPT-5.6 Luna model](https://developers.openai.com/api/docs/models/gpt-5.6-luna) | 2026-08-16の置換済み商品検索案で行ったprovider比較の履歴確認。現行の商品検索正本では使用しない |
| OpenAI Structured Outputs | [Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | 2026-08-16の置換済み商品検索案とJSON Schema検討の履歴確認。現行Bonsai応答の保証として引用しない |
| Cloudflare Workers AI FLUX.2 klein 4B | [Model page](https://developers.cloudflare.com/workers-ai/models/flux-2-klein-4b/)、[launch and multi-reference guide](https://developers.cloudflare.com/changelog/post/2026-01-15-flux-2-klein-4b-workers-ai/)、[Execute AI model](https://developers.cloudflare.com/api/resources/ai/methods/run/)、[Errors](https://developers.cloudflare.com/workers-ai/platform/errors/) | 2026-09-07再確認。model ID、POST endpoint、Base64の `image` output、prompt-onlyを含むmultipart、固定4 steps、seed、256〜1920px寸法、最大4参照画像、exact `input_image_0`、参照画像が512×512未満という制約。出力schemaはraw画像形式をPNGへ限定していない。`{result:{image},success,errors,messages}` はmodel output objectとREST envelopeを組み合わせたfail-closed契約である |
| Cloudflare Workers AI pricing | [Pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/) | 2026-09-08確認。FLUX.2 klein 4Bは入力512×512 tile当たり0.000059 USD、出力512×512 tile当たり0.000287 USD。画像生成live実行前に単価・quotaを再確認し、文書化時点の値を将来料金として固定しない |
| OpenAI CLIP | [openai/CLIP](https://github.com/openai/CLIP)、[pinned ViT-B/32 assets](https://huggingface.co/openai/clip-vit-base-patch32/tree/12b36594d53414ecfba93c7200dbb7c7db3c900a)、[pinned ONNX model](https://huggingface.co/openai/clip-vit-base-patch32/blob/12b36594d53414ecfba93c7200dbb7c7db3c900a/onnx/model.onnx)、[pinned processor](https://huggingface.co/openai/clip-vit-base-patch32/blob/12b36594d53414ecfba93c7200dbb7c7db3c900a/onnx/preprocessor_config.json) | 2026-09-03確認。pHashと分離した画像embedding、固定revision・byte数・SHA-256、RGB・BICUBIC・rescale・mean・std、L2正規化、cosine類似度。upstream processorのcenter cropはasset provenanceとして固定し、application profileは縦横比維持・224×224内の全体保持・正規化後0のmean余白としてruntime digestへ別途結ぶ。PyTorch pickle weightは採用しない |
| ONNX Runtime | [ONNX Runtime 1.23.2 on PyPI](https://pypi.org/project/onnxruntime/1.23.2/)、[Python API summary](https://onnxruntime.ai/docs/api/python/api_summary.html) | 2026-09-03確認。Python 3.10〜3.13、Windows/Linux x86-64 wheel、CPU execution providerを明示するlocal inference。provider fallbackやruntime downloadは使わない |
| Pillow image security | [Pillow security handbook](https://pillow.readthedocs.io/en/stable/handbook/security.html)、[Image.open reference](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.open) | MIMEとmagicの独立確認、decoder format allowlist、decompression bomb warning、寸法上限、metadata除去、process isolationの境界 |
| Codex設定 | [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) | `model_reasoning_effort`、`model_reasoning_summary`、`model_verbosity` の固定 |
| Podman導入 | [Podman installation](https://podman.io/docs/installation) | Archを含む公式package導入先の確認。package変更は管理者承認後だけ行う |
| Podman rootless mode | [Podman manual](https://docs.podman.io/en/latest/markdown/podman.1.html) | `/etc/subuid` / `/etc/subgid`、user-specific image storage、rootless制約の確認 |
| Podman container実行 | [podman-run](https://docs.podman.io/en/latest/markdown/podman-run.1.html) | rootless `--userns=keep-id`、read-only、capability、security option、resource制限の運用確認。現行コードとhost probeを優先する |
| Git clone | [git-clone](https://git-scm.com/docs/git-clone) | linked worktreeを避け、`--no-local` / `--no-hardlinks` でstandalone candidateを用意する際の前提 |
| Python zipapp | [zipapp](https://docs.python.org/3/library/zipapp.html) | 決定論的archiveの形式。現行のarchive内部hashを外部trust anchorとは扱わない |
| Python hashlib | [hashlib](https://docs.python.org/3/library/hashlib.html) | Python 3.10でも利用できるchunk単位SHA-256実装の根拠 |

Outscraperの描画済み公式ページはrequest endpointを `api.outscraper.com` と記載する一方、同じページのcURL例とOpenAPIのserverは `api.outscraper.cloud` を使う。実行時の接続先は [`src/config.py`](../src/config.py) の `OUTSCRAPER_ENDPOINT` を正とし、v2 request digestへexact endpointを含める。変更時は公式仕様、結果URLのホスト制約、テストを同時に確認する。

## ローカル保存資料

`docs/API Docs _ Outscraper.html` は取得時点の外部HTMLであり、`.gitignore` 対象である。内容が古くなる可能性があるため、仕様変更の根拠には公式Web資料を使う。

`tests/img/case1/near/` 13枚と `tests/img/case1/far/` 18枚は、利用者が検索条件「黒い無線ゲーミングマウス」の近い／近くない例として分類したlocal品質fixtureである。現行の安定IDはnearがn1〜n13、farがf1〜f18で、各IDを固定SHA-256へ結び付ける。far 18枚の属性は利用者提示の正解として記録した。near 13枚の属性は2026-09-03にlocal画像を個別表示して得た目視観察であり、利用者指定または商品仕様の正解とは区別する。全13枚を黒いマウス、うち11枚をゲーミング用途、n5・n6を用途未知とした。接続方式は静止画像から確定できないため、2026-09-04の責務分離でnear 13枚を全て未知へ訂正した。画像配信元の許可候補として `m.media-amazon.com` が別途示されているが、31枚それぞれの個別URL、商品識別子、取得元、取得時刻の出所検証は行っておらず、利用・再配布条件も未確認である。31枚はGit未追跡のまま保持し、test内の相対path・label・SHA-256 manifestによるlocal再現にだけ使う。これらをcommit、push、配布、一般的なAmazon検索品質の根拠にする前に、権利とdataset設計を別途確認する。

`tests/img/case2/near/` 4枚と `tests/img/case2/far/` 7枚は、利用者が第2条件「筒状・長い・縦・金属製・収納、追加で四角い・黒い」の候補、画像で判定する特徴、商品名・説明で判定する `金属製`、期待順位、rating、review countとして提示したlocal品質fixtureである。各画像はtest内の相対path・label・SHA-256 manifestへ固定したが、候補とは独立した4方向参照は受領していない。全体保持profileによるnear自己参照除外cluster診断は正式なproduction scoreではなく、AUC 0.642857143と期待順位の順序一致27/53を画像ranking無効の根拠として使う。画像の個別URL、商品識別子、取得時刻、利用・再配布条件は未確認で、Git未追跡のまま扱う。元Excelには非空の作成者・最終更新者metadataがあるためfixture、artifact、commit、配布へ含めず、転記した非個人データだけをtestへ使う。

`tests/img/case3/near/` 8枚と `tests/img/case3/far/` 12枚は、利用者が第3条件「収納口2つ・小型（卓上）・縦・収納」の候補、視覚・構造化特徴、期待順位、rating、review countとして提示したlocal品質fixtureである。全20枚は固定SHA-256へ結び付け、単一frame PNG、source・pixel digest一意、pHash距離5以下の重複なしをtestで検査する。候補とは独立した4方向参照がないため、全体保持profileのAUC 0.468750000・期待順位一致80/173は自己参照除外cluster診断に限定し、production scoreまたは採用基準と扱わない。画像の出所・利用・再配布条件は未確認でGit未追跡のまま扱い、元Excelの作成者・更新者metadataは値を転記せず、testもworkbookをruntimeで読まない。

SHA-256 `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea` の2026-09-05 local CSVは、利用者が非機密かつcase1からcase3や既存調整に未使用のholdoutとして提示した。2 category・各2 case・各3商品・各1 exact条件と、category別のhard contradiction・uncertainty labelを持つことを本文非表示で確認し、EXEC-042の1回目の本評価へ使用した。個別URL、ASIN相当値、検索文、商品本文は標準文書・評価artifactへ転記していない。出所referenceとsplit dateはCSV内の非個人metadataから構造検査したが、利用・再配布条件は未確認であるためGit追跡・配布対象としない。このCSVは使用済みdevelopment dataへ降格した。利用者指定によりEXEC-043の回帰確認へrequest v3で再利用し、4件全てが旧300秒timeoutで `request_failed` となった。EXEC-045でも時間上限なしrequest v4で再利用し、4件全てがHTTP完了後に `content_not_json` となった。request v5のhealth-ready再実行では4件全てがstrict intentまで通過した後、評価用後処理で停止した。段階診断付き部分再計測では完了2件が `query_plan_invalid`、送信済み3件目が手動中断、4件目が未送信となり、部分実行から評価reportまたはassessmentは生成していない。EXEC-050では更新promptの先頭1件だけを合計1 callで再利用し、HTTP 200後の受理前に `intent_normalization_invalid` となった。EXEC-051でも先頭1件だけを合計1 callで再利用し、HTTP 200後の `draft_schema_invalid` で停止した。EXEC-052では生成schema整合後の先頭1件だけを合計1 callで再利用し、完全draft schemaと正規化を通過した後の `intent_searchability_invalid` で停止した。EXEC-053では商品種別またはblocking確認待ちを強制する生成schemaで先頭1件を合計1 callだけ再利用し、strict intentとtyped proposal生成まで成功して `blocking` で停止した。EXEC-055では同じ先頭1件を現行orchestratorへ合計1 callだけ通し、233.419秒・HTTP 200・2,508 bytesでquery plan・query digestなしの `BlockingIntentReview` へ到達した。各1件確認では2件目、再試行、dataset assessmentを実行せず、生responseと検索内容を保存していない。EXEC-053・EXEC-055では商品取得・rankingも実行していない。いずれの再評価も独立holdoutまたは未知データの最終採否として扱わない。

## 参照時の確認事項

- 外部APIの料金、上限、レスポンス形状は利用前に公式資料で再確認する。
- `specs/policies/openai-pricing-policy.json` はAIレビューハーネスについて2026-08-15時点の `service_tier=default` を固定したrelease契約であり、商品検索のprovider設定でも将来料金の保証でもない。変更時は公式model pageを再確認して新しいdigestを承認する。
- `tools/ai_review/outer_descriptor_executor.py` はbounded subprocessのtest primitiveであり、provisioned broker production経路の根拠には使わない。正規経路は上表のoffline/broker専用protocolを確認する。
- broker phase protocolはfrozen final ledgerからhost DBなしでtyped evidenceを再構築し、`reconstruct_attestation_inputs` はimmutable phase chainからsign/judge共通bundleを復元する。`build_frozen_bundle_expectations` / `judge_frozen_attestation_bundle` はcanonical prepared/raw evidenceとpinned policy bytesを再finalizeし、productionでhost broker DB/runtime再probeを権威入力にしない。
- outer `--workflow` entry、inner `prepare|finalize` surface、7/7 actual handler、verified snapshot専用mount、sign-only key mount、judge-only nonce mountは接続済みである。readiness gateは不完全なreleaseをcredential read・broker ledger作成前に拒否する。
- `runtime_release workflow-init` はexternal approved manifest SHA、TaskSpec v2/harness、exact task/public key、protected candidate、人手承認済みpatch SHAからinitial requestを作る。同じinstalled manifestからその場で計算したSHAをexternal approvalの代替にしない。
- launcher `--deployment-check` はrootless backendと4 digest-pinned imageのcredential-free local checkであり、成功status `nonlive_ready` でも `production_e2e_complete=false` である。live APIまたはfull workflow実績として引用しない。
- nonce contractは [`tools/ai_review/nonce_ledger.py`](../tools/ai_review/nonce_ledger.py) のSQL、application ID/user version、PRAGMA、index/table metadata、file identityを正とする。replay setは署名検証後に単一transactionで予約し、部分衝突も全件rollbackする。
- 設計候補を実装済み機能として扱わない。
- 商品検索のLLMは現行Bonsai経路を正本とする。OpenAI関連資料はAIレビューハーネスまたは置換済み案の履歴という用途を明記し、商品検索でOpenAIを使用中と解釈しない。
- 既定値を変更した場合は、コード、`.env.example`、関連文書、テストを同じ変更で更新する。
- 実API確認は、認証情報、課金、取得件数、待機時間を確認してから明示的に実施する。

関連資料: [AGENTS.md](../AGENTS.md)、[バックエンド設計](BACKEND.md)、[要件と制約](REQUIREMENTS.md)、[開発・トラブルシューティング](DEVELOPMENT.md)

## 統合元文書とアーカイブ

`agents-setup` テンプレートにない説明用Markdownは、次表の正本文書へ内容を統合し、元ファイルを `docs/old/` に保存する。アーカイブは作成当時の詳細と判断経緯を確認するためのもので、現行の要件、設計、手順、進行状態を上書きしない。

`docs/HARNESS-RUNBOOK.md` はユーザー指定により統合対象外とし、実行コマンド、期待結果、停止・再実行規則の正本として現位置に保持する。旧 `docs/SEARCH-FLOW.md` の技術内容は要件・バックエンド・セキュリティ文書へ、テスト内容は [DEVELOPMENT.mdの統合済みテスト方針](DEVELOPMENT.md#統合済みテスト方針) へ分け、ルートの [SEARCH-FLOW.md](../SEARCH-FLOW.md) は旧 `UI-FLOW.md` を基に利用者向け操作の正本とする。

| 統合元 | 統合先または現行正本 | アーカイブまたは扱い |
|---|---|---|
| `docs/QUICKSTART.md` | [README.md](../README.md#統合済みクイックスタート) | `docs/old/QUICKSTART.md` |
| `docs/CONSTRAINTS.md` | [REQUIREMENTS.md](REQUIREMENTS.md#統合済み制約) | `docs/old/CONSTRAINTS.md` |
| `docs/DESIGN.md` | [BACKEND.md](BACKEND.md#統合済み全体設計) | `docs/old/DESIGN.md` |
| `docs/UI.md` | [FRONTEND.md](FRONTEND.md#統合済みui設計) | `docs/old/UI.md` |
| `docs/AI_GUIDE.md` | [DEVELOPMENT.md](DEVELOPMENT.md#統合済みaiレビュー規約)、[SECURITY.md](SECURITY.md) | `docs/old/AI_GUIDE.md` |
| `docs/PLANS.md` | [DEVELOPMENT.md](DEVELOPMENT.md#統合済みexecution-plan規約) | `docs/old/PLANS.md` |
| `docs/TROUBLESHOOTING.md` | [DEVELOPMENT.md](DEVELOPMENT.md#統合済みトラブルシューティング) | `docs/old/TROUBLESHOOTING.md` |
| `docs/MEMORY.md` | [WORKLOG.md](WORKLOG.md#統合済みプロジェクトメモリ) | `docs/old/MEMORY.md` |
| `docs/TASKS.md` | [GOAL.md](GOAL.md#統合済み大規模タスク一覧) | `docs/old/TASKS.md` |
| `docs/TODO.md` | [GOAL.md](GOAL.md#統合済み小規模タスク一覧) | `docs/old/TODO.md` |
| `docs/TECH-DEBT-TRACKER.md` | [ISSUES.md](ISSUES.md#統合済み技術的負債トラッカー) | `docs/old/TECH-DEBT-TRACKER.md` |
| `docs/INDEX.md` | [AGENTS.md](../AGENTS.md)、[統合済み旧ドキュメント索引](#統合済み旧ドキュメント索引) | `docs/old/INDEX.md` |
| `docs/TESTING.md` | [DEVELOPMENT.md](DEVELOPMENT.md#統合済みテスト方針) | `docs/old/TESTING.md` |
| `docs/plans/EXEC-002-ATTESTED-AI-REVIEW-BOUNDARIES.md` | [GOAL.md](GOAL.md#exec-002-attested-ai-review境界の実装) | `docs/old/plans/EXEC-002-ATTESTED-AI-REVIEW-BOUNDARIES.md` |
| `docs/old/plans/EXEC-001-AI-REVIEW-TDD-HARNESS.md` | [WORKLOG.md](WORKLOG.md#統合済み履歴plan-exec-001) | 履歴原本を同じ場所に保持 |
| `docs/old/plans/EXEC-003-SEARCH-FLOW-V2-BACKEND.md` | [WORKLOG.md](WORKLOG.md#統合済み履歴plan-exec-003) | 履歴原本を同じ場所に保持 |
| 旧 `docs/SEARCH-FLOW.md` | [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[DEVELOPMENT.md](DEVELOPMENT.md#統合済みテスト方針) | `docs/old/SEARCH-FLOW.md` |
| 旧 `UI-FLOW.md` | [SEARCH-FLOW.md](../SEARCH-FLOW.md#ui操作フロー) | `docs/old/UI-FLOW.md` |
| `docs/HARNESS-RUNBOOK.md` | 同ファイル | 統合・移動対象外 |

2026-08-15に削除された次の旧設計文書は、削除直前版を保持する。内容は現在の [BACKEND.md](BACKEND.md)、[REQUIREMENTS.md](REQUIREMENTS.md)、[DB-SCHEMA.md](DB-SCHEMA.md)、[SECURITY.md](SECURITY.md)、[ISSUES.md](ISSUES.md) へ統合済みである。

| 旧設計文書 |
|---|
| `docs/old/CACHE_DESIGN.md` |
| `docs/old/DATA_MODEL_SPEC.md` |
| `docs/old/ENVIRONMENT_VARIABLES.md` |
| `docs/old/EXTERNAL_API_SPEC.md` |
| `docs/old/PRODUCTION_DESIGN_GUIDE.md` |
| `docs/old/README_dev.md` |

段階別検証資料の本文は [WORKLOG.mdの統合済み旧検証資料](WORKLOG.md#統合済み旧検証資料) へ履歴として統合した。現行コードと回帰テストの根拠にはせず、[BACKEND.md](BACKEND.md) に残した現行結論だけを通常の開発判断に使う。元Markdownはパス構造を保って `docs/old/examples/` に保存する。

| 旧検証資料 |
|---|
| `examples/README.md` |
| `examples/legacy-phases/phase1_bonsai_attribute_extraction/Add.md` |
| `examples/legacy-phases/phase1_bonsai_attribute_extraction/PREREQUISITES.md` |
| `examples/legacy-phases/phase1_bonsai_attribute_extraction/README.md` |
| `examples/legacy-phases/phase2_outscraper_amazon_products_request/README.md` |
| `examples/legacy-phases/phase3_outscraper_response_normalization/README.md` |
| `examples/legacy-phases/phase4_product_scoring/README.md` |

実行時に読み込むpromptは説明文書ではないため、内容を [BACKEND.md](BACKEND.md#統合済みbonsai-system-prompt) または [DEVELOPMENT.md](DEVELOPMENT.md#統合済みindependent-reviewer-prompt) に統合した上で、実行用ファイルをMarkdown以外へ分離する。元Markdownは `docs/old/runtime/` に保存する。

| 旧Markdown | 実行時の正本 |
|---|---|
| `src/clients/bonsai_prompt.md` | `src/clients/bonsai_prompt.txt` |
| `specs/prompts/reviewer.md` | `specs/prompts/reviewer.txt` |
| `specs/prompts/adversary.md` | `specs/prompts/adversary.txt` |

## 統合済み旧ドキュメント索引

> 統合元: `docs/INDEX.md`。以下は統合前の役割情報を保持し、リンクだけを現行正本へ更新した履歴である。現行の目次は `AGENTS.md`、統合先の対応はこの文書の「統合元文書とアーカイブ」を優先する。

### ドキュメント索引

#### 標準文書

このリポジトリの文書体系は `agents-setup` の標準構成を入口とし、既存文書を詳細仕様、運用手順、履歴として保持する。標準文書と詳細文書が競合する場合の優先順位は、ルートの [AGENTS.md](../AGENTS.md) と [DEVELOPMENT.md](DEVELOPMENT.md) に従う。

| 役割 | 正本 | 主な詳細資料 |
|---|---|---|
| 開発規約 | [DEVELOPMENT.md](DEVELOPMENT.md) | [PLANS.md](DEVELOPMENT.md#統合済みexecution-plan規約)、[AI_GUIDE.md](DEVELOPMENT.md#統合済みaiレビュー規約) |
| 要件 | [REQUIREMENTS.md](REQUIREMENTS.md) | [CONSTRAINTS.md](REQUIREMENTS.md#統合済み制約)、[SEARCH-FLOW.md](../SEARCH-FLOW.md) |
| フロントエンド | [FRONTEND.md](FRONTEND.md) | [UI.md](FRONTEND.md#統合済みui設計)、[UI-FLOW.md](../SEARCH-FLOW.md#ui操作フロー) |
| バックエンド | [BACKEND.md](BACKEND.md) | [DESIGN.md](BACKEND.md#統合済み全体設計)、[SEARCH-FLOW.md](../SEARCH-FLOW.md) |
| セキュリティ | [SECURITY.md](SECURITY.md) | [AI_GUIDE.md](DEVELOPMENT.md#統合済みaiレビュー規約)、[HARNESS-RUNBOOK.md](HARNESS-RUNBOOK.md) |
| データ保存 | [DB-SCHEMA.md](DB-SCHEMA.md) | [DESIGN.md](BACKEND.md#統合済み全体設計)、[TECH-DEBT-TRACKER.md](ISSUES.md#統合済み技術的負債トラッカー) |
| テスト | [DEVELOPMENT.md](DEVELOPMENT.md#統合済みテスト方針) | `tests/`、[HARNESS-RUNBOOK.md](HARNESS-RUNBOOK.md) |
| 参考資料 | [REFERENCES.md](REFERENCES.md) | この索引、外部公式資料、旧検証資料 |
| 問題・作業の入口 | [ISSUES.md](ISSUES.md) | [TASKS.md](GOAL.md#統合済み大規模タスク一覧)、[TODO.md](GOAL.md#統合済み小規模タスク一覧)、[TECH-DEBT-TRACKER.md](ISSUES.md#統合済み技術的負債トラッカー)、個別Plan |
| ゴールと進行状態 | [GOAL.md](GOAL.md) | [TASKS.md](GOAL.md#統合済み大規模タスク一覧)、`docs/GOAL.md` |
| 開発履歴 | [WORKLOG.md](WORKLOG.md) | [MEMORY.md](WORKLOG.md#統合済みプロジェクトメモリ)、個別Plan |
| 統合済み変更 | [CHANGELOG.md](CHANGELOG.md) | Git履歴、[WORKLOG.md](WORKLOG.md) |

既存文書は標準文書から参照し、役割の重複を避ける。特に `HARNESS-RUNBOOK.md` は実行コマンド、期待結果、停止・再実行規則を担い、現在状態と過去実績は `GOAL.md`、Execution Plan、`WORKLOG.md` に分ける。

#### 最初に読む

| 目的 | 文書 |
|---|---|
| 開発・レビュー・文書更新のルールを確認する | [DEVELOPMENT.md](DEVELOPMENT.md) |
| 最短でセットアップして起動する | [QUICKSTART.md](../README.md#統合済みクイックスタート) |
| 症状から解決方法を探す | [TROUBLESHOOTING.md](DEVELOPMENT.md#統合済みトラブルシューティング) |
| アプリが満たす要件を確認する | [REQUIREMENTS.md](REQUIREMENTS.md) |
| 現在できないこと・前提条件を確認する | [CONSTRAINTS.md](REQUIREMENTS.md#統合済み制約) |
| 全体構成とデータフローを理解する | [DESIGN.md](BACKEND.md#統合済み全体設計) |
| 次期商品検索の利用者向け操作を確認する | [SEARCH-FLOW.md](../SEARCH-FLOW.md) |
| 通常ゲート、受入確認、live試験の境界を確認する | [DEVELOPMENT.md](DEVELOPMENT.md#統合済みテスト方針) |
| AIレビュー・ハーネスの実行区分、コマンド、期待結果、停止条件を確認する | [HARNESS-RUNBOOK.md](HARNESS-RUNBOOK.md) |
| プロダクトの到達点と進行中の計画を確認する | [GOAL.md](GOAL.md) |
| 利用者・運用者に影響する統合済み変更を確認する | [CHANGELOG.md](CHANGELOG.md) |

#### 設計資料

| 文書 | 主題 |
|---|---|
| [DESIGN.md](BACKEND.md#統合済み全体設計) | システム全体、責務分割、データフロー、キャッシュ、ランキング方針 |
| [SEARCH-FLOW.md](../SEARCH-FLOW.md) | 条件整理、任意の4方向参考画像、最終確認、待機、結果、履歴を利用者の操作順で説明する次期フロー |
| [FRONTEND.md](FRONTEND.md) | Streamlitフロントエンドの構造、状態管理、バックエンド境界 |
| [BACKEND.md](BACKEND.md) | 実行パイプライン、外部API、設定、正規化、採点、例外 |
| [DEVELOPMENT.mdの統合済みテスト方針](DEVELOPMENT.md#統合済みテスト方針) | offline gate、現行・次期テスト範囲、画面の受入確認、live試験の個別承認境界 |
| [UI.md](FRONTEND.md#統合済みui設計) | 画面要素、操作、表示状態、エラー表示、改善基準 |
| [DB-SCHEMA.md](DB-SCHEMA.md) | RDB未採用の現状とJSONキャッシュの論理スキーマ |
| [SECURITY.md](SECURITY.md) | シークレット、外部通信、ログ、キャッシュ、信頼境界 |

#### 作業管理

| 文書 | 使う場面 |
|---|---|
| [GOAL.md](GOAL.md) | プロダクトの到達点、非目標、進行中の計画状態を確認するとき |
| [CHANGELOG.md](CHANGELOG.md) | 利用者・運用者に影響する統合済み変更を確認するとき |
| [PLANS.md](DEVELOPMENT.md#統合済みexecution-plan規約) | 長時間・複雑タスクのExecution Planを作成・更新するとき |
| [EXEC-002](GOAL.md#exec-002-attested-ai-review境界の実装) | attested境界、workflow初期化、credential-free deployment check、typed outer protocol、frozen sign/judge、7/7 readiness、nonce契約・配備条件を確認するとき |
| [TASKS.md](GOAL.md#統合済み大規模タスク一覧) | 複数工程を持つ大規模タスクを管理するとき |
| [TODO.md](GOAL.md#統合済み小規模タスク一覧) | 単独で完了できる小規模タスクを管理するとき |
| [TECH-DEBT-TRACKER.md](ISSUES.md#統合済み技術的負債トラッカー) | 実装済みだが将来の保守性や運用性に負債がある項目を追跡するとき |
| [ISSUES.md](ISSUES.md) | 再現済みの不具合、制限、調査中の問題を追跡するとき |
| [WORKLOG.md](WORKLOG.md) | 実施した変更と検証結果を時系列で残すとき |
| [MEMORY.md](WORKLOG.md#統合済みプロジェクトメモリ) | 頻繁には変わらない長期的な判断・知識を残すとき |

#### 補助資料

| 文書 | 内容 |
|---|---|
| [REFERENCES.md](REFERENCES.md) | リポジトリ内の一次資料と外部公式資料 |
| [AI_GUIDE.md](DEVELOPMENT.md#統合済みaiレビュー規約) | TaskSpec v2、external manifest/patch anchor、TDD、snapshot、raw evidence、2役broker/frozen ledger、frozen judge、nonce、署名、人間承認の強制規約 |
| [HARNESS-RUNBOOK.md](HARNESS-RUNBOOK.md) | offline検証、host診断、trusted release、workflow初期化、credential-free deployment check、live 7-phase実行、停止・再実行規則 |

#### 文書の役割分担

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

#### 旧文書アーカイブ

アーカイブ全体の出典と取扱規則は [old/README.md](old/README.md) を参照する。2026-08-15の再編で内容を分配統合した旧文書は、削除直前版を `docs/old/` に保存する。現行判断には右列の統合先を使う。

| 旧ファイル | 主な統合先 |
|---|---|
| [CACHE_DESIGN.md](old/CACHE_DESIGN.md) | [DESIGN.md](BACKEND.md#統合済み全体設計)、[DB-SCHEMA.md](DB-SCHEMA.md)、[SECURITY.md](SECURITY.md)、[TECH-DEBT-TRACKER.md](ISSUES.md#統合済み技術的負債トラッカー) |
| [DATA_MODEL_SPEC.md](old/DATA_MODEL_SPEC.md) | [BACKEND.md](BACKEND.md)、[DB-SCHEMA.md](DB-SCHEMA.md)、[REQUIREMENTS.md](REQUIREMENTS.md) |
| [ENVIRONMENT_VARIABLES.md](old/ENVIRONMENT_VARIABLES.md) | [BACKEND.md](BACKEND.md)、[QUICKSTART.md](../README.md#統合済みクイックスタート)、[CONSTRAINTS.md](REQUIREMENTS.md#統合済み制約)、[SECURITY.md](SECURITY.md) |
| [EXTERNAL_API_SPEC.md](old/EXTERNAL_API_SPEC.md) | [BACKEND.md](BACKEND.md)、[SECURITY.md](SECURITY.md)、[TROUBLESHOOTING.md](DEVELOPMENT.md#統合済みトラブルシューティング)、[REFERENCES.md](REFERENCES.md) |
| [PRODUCTION_DESIGN_GUIDE.md](old/PRODUCTION_DESIGN_GUIDE.md) | [DESIGN.md](BACKEND.md#統合済み全体設計)、[SECURITY.md](SECURITY.md)、[TECH-DEBT-TRACKER.md](ISSUES.md#統合済み技術的負債トラッカー)、[TASKS.md](GOAL.md#統合済み大規模タスク一覧) |
| [README_dev.md](old/README_dev.md) | [DESIGN.md](BACKEND.md#統合済み全体設計)、[BACKEND.md](BACKEND.md)、[FRONTEND.md](FRONTEND.md)、[QUICKSTART.md](../README.md#統合済みクイックスタート) |

完了済みPlanも、現行の進行状態と混同しないよう `docs/old/plans/` に保存する。

| 完了済みPlan | 位置付け | 現行の参照先 |
|---|---|---|
| [EXEC-001](old/plans/EXEC-001-AI-REVIEW-TDD-HARNESS.md) | TASK-006 bootstrapとTDDパイロットの履歴 | [EXEC-002](GOAL.md#exec-002-attested-ai-review境界の実装)、[HARNESS-RUNBOOK.md](HARNESS-RUNBOOK.md) |
| [EXEC-003](old/plans/EXEC-003-SEARCH-FLOW-V2-BACKEND.md) | TASK-008第1マイルストーンと置換済みprovider判断の履歴 | [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装)、[TASKS.md](GOAL.md#統合済み大規模タスク一覧) |

#### 変更時の更新先

| 変更内容 | 同時に確認する文書 |
|---|---|
| 開発規約・検証方法 | `DEVELOPMENT.md`、`AGENTS.md` |
| 環境変数・既定値 | `BACKEND.md`、`QUICKSTART.md`、`CONSTRAINTS.md`、`.env.example` |
| Pydanticモデル | `BACKEND.md`、`DB-SCHEMA.md`、`REQUIREMENTS.md` |
| UIの入力・表示・状態 | `FRONTEND.md`、`UI.md`、`QUICKSTART.md` |
| 商品検索フロー、Bonsai抽出、画像生成、承認状態、ranking profile | `SEARCH-FLOW.md`、`DEVELOPMENT.md`、`REQUIREMENTS.md`、`DESIGN.md`、`BACKEND.md`、`FRONTEND.md`、`UI.md`、`SECURITY.md`、`CONSTRAINTS.md` |
| 外部API・再試行・URL制約 | `BACKEND.md`、`SECURITY.md`、`TROUBLESHOOTING.md` |
| キャッシュキー・TTL・保存形式 | `DESIGN.md`、`DB-SCHEMA.md`、`SECURITY.md` |
| 既知の制限または不具合 | `CONSTRAINTS.md`、`ISSUES.md`、必要に応じて `TECH-DEBT-TRACKER.md` |
| 大規模な将来作業 | `TASKS.md`。着手時は `PLANS.md` に従ってExecution Planを作る |
| AIレビュー、TDD証拠、ハーネス契約 | `AI_GUIDE.md`、`HARNESS-RUNBOOK.md`、対応する `docs/GOAL.md`、`SECURITY.md` |
| ゴール・問題・履歴・統合済み変更 | 順に `GOAL.md`、`ISSUES.md`、`WORKLOG.md`、`CHANGELOG.md` |

#### 検証

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


## Bonsai生成設定の確認（2026-09-09）

- [Prism ML Bonsai-8B GGUF model card](https://huggingface.co/prism-ml/Bonsai-8B-gguf#best-practices): EXEC-093で配布元のtemperature0.5、top-k20、top-p0.9と実行要件を確認した。診断用seed0を併用した既知5例の比較では意味品質の改善を確認できなかったため、sampling変更は採用していない。


## RAG前提の仕様定義診断（2026-09-09）

[EXEC-095](GOAL.md#exec-095-仕様定義を与えたbonsaiの属性同定を検証する) の [評価用定義](../tools/bonsai_definition_cases.py) は、メーカーの公開用語説明・取扱説明書・仕様ページを確認して短く要約した。出典URLの一覧は同fileのREFERENCESに持ち、試験manifestにも凍結する。Bonsaiへは要約定義とopaqueな資料IDを渡し、期待属性key・正解ID・採点情報・出典URLは渡さない。実商品データやユーザー検索履歴を使ったcorpusではない。

- [Nikon 顕微鏡の光学系](https://www.microscopyu.com/microscopy-basics/components)、[開口数](https://www.microscopyu.com/microscopy-basics/numerical-aperture): 倍率とレンズ単体・開口数を区別する。
- [Epson 読取解像度](https://faq2.epson.jp/web/Detail.aspx?id=197&printMode=1)、[Iris 細断枚数](https://www.irisohyama.co.jp/products/manual/pdf/101111.pdf): 読取と出力、一度の最大投入と連続運用を区別する。
- [EIZO リフレッシュレート](https://www.eizo.co.jp/support/glossary/sa/suichoku_i/)、[Canon 撮影仕様](https://cam.start.canon/ja/C003/manual/html/UG-09_Reference_0100.html): 画面更新・静止画連写・動画の枚数/時間を区別する。
- [TP-Link 速度表示](https://www.tp-link.com/jp/support/faq/2866/)、[Yamaha スピーカーとケーブル](https://jp.yamaha.com/products/contents/proaudio/docs/better_sound/part2_03.html): 理論値/実測値・無線/有線、負荷/導線の抵抗を区別する。
- [Omron UPS選定](https://store.fa.omron.co.jp/special/ups/)、[Oriental Motor ファン仕様](https://www.orientalmotor.co.jp/ja/products/fan-motors/spec-guide): 出力容量の単位と、通風条件による風量の違いを区別する。


## LFM2.5-1.2B-JPの比較診断（2026-09-10）

- [Liquid AI公式モデルカード](https://huggingface.co/LiquidAI/LFM2.5-1.2B-JP): 指定された日本語版の用途とllama.cpp対応を確認した。
- [公式GGUFの固定revision](https://huggingface.co/LiquidAI/LFM2.5-1.2B-JP-GGUF/tree/170ae1cecf0e74b0b25bd704047160fba9f613c6): Q6_K、962,843,584 bytesを診断専用に取得し、LFS SHA-256と照合した。製品のBonsai設定は置換していない。配布物とLICENSEはrepository外に保持する。


## 検索語のローカル辞書と文脈モデル

2026-09-10にEXEC-103の資材として確認。モデル・辞書はrepository外で管理し、取得版とSHA-256を固定する。

- [JMdict公式説明](https://www.edrdg.org/wiki/JMdict-EDICT_Dictionary_Project.html)、[英語XML配布](https://www.edrdg.org/pub/Nihongo/JMdict_e.gz)、[EDRDGライセンス](https://www.edrdg.org/edrdg/licence.html): 語義別表記制限、英訳、CC BY-SA 4.0と帰属表示。
- [日本語WordNet配布](https://bond-lab.github.io/wnja/eng/downloads.html)、[日本語版ライセンス](https://bond-lab.github.io/wnja/license.txt)、[Princeton WordNetライセンス](https://wordnet.princeton.edu/license-and-commercial-use): 今回はSQLiteで配布された1.1を使用。最新の全資材を取り込んだとは扱わない。
- [GiNZA公式](https://megagonlabs.github.io/ginza/): ginza 5.2.1 / ja_ginza 5.2.0によるローカル構文解析。
- [multilingual-e5-small固定版](https://huggingface.co/intfloat/multilingual-e5-small/tree/614241f622f53c4eeff9890bdc4f31cfecc418b3): 量子化ONNX、tokenizer、query/passage prefixとmean pooling。検索用embeddingであり、日本語の商品語義選択の品質保証ではない。


- [日本語小型reranker固定版](https://huggingface.co/hotchpotch/japanese-reranker-xsmall-v2/tree/de99fd2f16c7b5df1df1bcc1d9ad2c16d88ce93a): 約36.8M parameters、MIT、CPU用量子化ONNX。語義候補の比較に限定して試す。検索ベンチマークを語義選択の精度として流用しない。
- [語義情報の拡充によるWSD改善](https://aclanthology.org/2021.findings-emnlp.365/): 同義語・用例・上位語の定義を使った英語での評価。日本語商品検索への改善を保証するものではない。


## OPUS-MT日英翻訳のローカル比較（2026-09-10）

- [Helsinki-NLP opus-mt-ja-enモデルカード](https://huggingface.co/Helsinki-NLP/opus-mt-ja-en): 日本語→英語、Marian transformer-align、normalization + SentencePieceと元配布リンクを確認。確認時のHugging Face revisionは0770961a39ba6bd66305b149c3f4110bcafca2e6。試験は同カードが示す[元配布opus-2019-12-18.zip](https://object.pouta.csc.fi/OPUS-MT-models/ja-en/opus-2019-12-18.zip)を使用した。カードのライセンス表示Apache-2.0と、取得ZIPのLICENSE表題Attribution 4.0 Internationalは区別して保存する。
- [CTranslate2 Marian変換](https://opennmt.net/CTranslate2/guides/marian.html): 元のMarian Transformer重みと語彙からの変換手順。
- [CTranslate2特殊トークン](https://opennmt.net/CTranslate2/guides/transformers.html#special-tokens-in-translation): Marian由来のモデルではsource EOSを暗黙に付加することを確認し、二重付加しない。
- [CTranslate2量子化](https://opennmt.net/CTranslate2/quantization.html): CPUのint8_float32対応。試験では4.8.2の実runtimeが要求通りのcompute typeを使用した。性能はWORKLOG168の実測範囲に限る。


2026-09-10のcandidate実E2E準備で、[Cloudflare 4B公式modelページ](https://developers.cloudflare.com/workers-ai/models/flux-2-klein-4b/)の入力512px tile当たり0.000059 USD・出力tile当たり0.000287 USDと、[Outscraper公式Amazon料金](https://outscraper.com/amazon-scraper/)の最初500商品無料・501〜5000商品2 USD/1000商品・以後1 USD/1000商品を再確認した。今回の2出力/1入力tileと最大24商品は有料枠換算0.048633 USD。実計上額や強制課金上限ではない。


## 対象部位の切り出し（2026-09-10）

- [CLIPSeg公式Transformers文書](https://huggingface.co/docs/transformers/model_doc/clipseg): 自由なtext/image promptによる二値領域抽出、localモデル利用の入口。
- [CIDAS/clipseg-rd64-refined](https://huggingface.co/CIDAS/clipseg-rd64-refined/tree/999e0328d9e10b484360c477313983f9afdd7050): 公開model cardはApache-2.0。revisionと各ファイルのSHA256をsrc/search_v2/clipseg_assets.jsonへ固定した。
- [CLIPSeg原論文](https://openaccess.thecvf.com/content/CVPR2022/html/Luddecke_Image_Segmentation_Using_Text_and_Image_Prompts_CVPR_2022_paper.html): 領域抽出の方式の根拠であり、本商品の切出し精度・CPU/iGPU速度の保証ではない。

- [MobileSAM公式実装](https://github.com/ChaoningZhang/MobileSAM/tree/f706ad9c4eb7f219c00d9050e46328518ffb65d2): 軽量encoder、point/box入力、automatic mask generatorを使用。Apache-2.0。sourceとcheckpointのSHA256をsrc/search_v2/mobile_sam_assets.jsonへ固定した。公式GPU値を本環境のCPU/iGPU性能へ換算しない。


### EXEC-110の画像生成診断の料金確認

2026-09-10に[Cloudflareのflux-2-klein-4b公式仕様](https://developers.cloudflare.com/workers-ai/models/flux-2-klein-4b/)を確認した。入力512px tileあたり0.000059 USD、出力tileあたり0.000287 USD。既存参考画像を入力する512pxの偽画像1枚の診断は1入力tile＋1出力tileで0.000346 USDを想定する。実課金額の証明や追加送信の承認ではない。


### SigLIP 2試用（2026-09-10、EXEC-114）

- [Google公式モデル資材の固定revision](https://huggingface.co/google/siglip2-base-patch16-224/tree/75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2): Apache-2.0。7資材を取得しSHA256固定。モデル重み1,500,800,904bytesの[配布元SHA256](https://huggingface.co/google/siglip2-base-patch16-224/blob/75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2/model.safetensors)と照合した。
- [公式前処理設定](https://huggingface.co/google/siglip2-base-patch16-224/blob/75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2/preprocessor_config.json): SiglipImageProcessorの224×224 resize、bilinear、mean/std0.5を試験に使用。既存CLIPのcontain/padと異なる点を比較制約へ記録した。
- [SigLIP 2論文](https://arxiv.org/abs/2502.14786): 意味理解・localization・dense featureの学習方針。一般ベンチマークを今回の商品画像精度やiGPU性能の代用にはしない。

2026-09-11、EXEC-115準備で[Outscraper Amazon Products Scraper公式料金](https://outscraper.com/amazon-scraper/)を再確認した。無料枠を見込まない2 USD/1000商品で24件0.048 USDと見積もる。実課金額や強制金額capではなく、実行は別途当該範囲の明示承認後。
