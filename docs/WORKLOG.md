# 作業履歴

## 1. 目的

この文書は、リポジトリで確認できる主要な変更を時系列で記録する。Git履歴を置き換えるものではなく、変更の目的と現在につながる判断を短く説明する。

進行予定は [GOAL.mdの大規模・小規模タスク一覧](GOAL.md#統合済み大規模タスク一覧)、現在の問題は [ISSUES.md](ISSUES.md) を参照する。未来の作業を「進行中」として先取りして記載しない。

## 2. Git履歴に基づく記録

### 2026-05-28: 初期実装（`91d6b48`, `v1.0.0`）

- Pythonアプリケーション本体、Streamlit入口、設定、スキーマ、Bonsai・Outscraperクライアント、正規化、採点、JSONユーティリティを追加した
- `pyproject.toml` と `uv.lock` により依存関係を管理する構成を追加した
- `.gitignore` を追加した

このコミットのファイル構成から確認できる事実であり、当時の実サービス結合試験結果はGit履歴だけからは確認できない。

### 2026-05-28: README追加（`1c51cd0`）

- ルート `README.md` を追加した

### 2026-05-28: プロジェクト設定修正（`a571d92`, `aa117a8`）

- `pyproject.toml` を各コミットで1行ずつ修正した
- コミットメッセージと差分から確認できる範囲を記録し、修正理由の詳細は推測しない

### 2026-05-28: アプリ入口修正（`29746e3`）

- `app.py` を1行修正した
- 修正内容の背景はコミット履歴に説明がないため、ここでは推測しない

### 2026-08-14: 堅牢化とリポジトリ整理（`fb2115a`）

- プロジェクト名と文書を `amazon-explorer` に整理した
- `.env.example`、開発文書、現行 `src` を直接検証するテストを追加した
- 開発段階の旧コードを現在の `docs/old/examples/` に参照用として分離した
- Bonsai応答検証、Outscraper状態分類・同一オリジンURL検証・リダイレクト拒否・再試行を追加した
- キャッシュrepository、プロジェクトルート基準パス、設定を含むキャッシュキー、Streamlitセッションscopeを追加した
- JSONのアトミック書込、商品データと価格・真偽値の正規化、採点境界を強化した
- UIでは詳細例外をサーバーログへ残し、固定の利用者向けエラーを表示する形へ変更した

この記録はコミット差分と現行コードで確認した。現行テストが保証する範囲は [ISSUES.md](ISSUES.md#4-検証範囲) を参照する。

## 3. 2026-08-15: 参照文書への再編

- 既存の開発概要、データモデル、環境変数、外部API、キャッシュ、本番設計の内容を現行コード・テストと照合し、20個の目的別文書へ統合した
- 統合後の重複を避けるため旧6文書を削除し、統合先を `INDEX.md` に記録した
- `AGENTS.md` を見出しとMarkdownリンクだけの全Markdown目次へ変更した
- Execution Plan、設計、フロントエンド、バックエンド、UI、セキュリティ、負債、索引、データ境界、起動手順、メモリ、TODO、作業履歴、要件、制約、トラブル解決、Issue、参考資料、Taskへ情報を分離する再編である
- `AI_GUIDE.md` は利用者から後続指示があるまで内容を記載しない方針で作成対象とした

この空ファイル方針は再編時点の履歴である。後述の明示指示を受けた変更では内容を追加しており、現在の状態を表す説明ではない。

この項目は同日の文書再編差分そのものに含まれるため、作成時点ではコミットIDが付与されていない。コミット前の作業をGitへ反映済みと扱わない。

同日の確認結果:

- `uv run ruff check .`: 成功
- `uv run ruff format --check .`: 成功、33ファイルが整形済み
- `uv run pytest`: 成功、68件
- `uv lock --check`: 成功
- プロジェクト内30個のMarkdownについて、コードブロック内を除くローカルリンク先と見出しアンカーの存在確認: 成功
- `docs/` の要求文書20個と `AI_GUIDE.md` の0バイトを確認: 成功
- `git diff --check`: 成功
- BonsaiとOutscraperの実サービス呼出し: 未実行。テストはモックを使用するため、課金を伴う結合動作はこの確認に含まれない

## 4. 2026-08-15: AI相互レビューとTDDハーネスの導入

この項目は記載時点の未コミット変更を記録する。コミットIDはまだ付与されておらず、Gitへ反映済みまたは外部AIレビューを運用開始済みとは扱わない。詳細は [EXEC-001](old/plans/EXEC-001-AI-REVIEW-TDD-HARNESS.md) を参照する。

### TDDパイロット

- `tests/test_streamlit_ui.py` を先に追加し、`color_term_weight` と `feature_term_weight` の不足により1 failed, 2 passedとなるREDを確認した
- テストファイルのSHA-256は `042ad1b2cd8307afe40787bd53510d4cb55f66914548adf9ed76b57b8306ac4c` である
- `src/ui/streamlit_ui.py` へ2項目を追加後、同じテストファイルで3 passedとなるGREENを確認した
- 同ファイルで `format_price()` と `format_rating()` の代表ケースも固定し、`TODO-002`、`TODO-003`、`ISS-001` を解決済みにした
- `tests/test_outscraper_search_select.py` を先に追加し、空文字とURLの推定商品名fallbackにより2 failed, 2 passedとなるREDを確認した
- fallbackテストのSHA-256は `c6c60c698d7cb3074721c07f04d853c5c742e6ab157fcf5697995ad5df889189` である
- `estimated_product_name_ja` も `validate_search_query()` を通す1行変更後、同じテストファイルで4 passedとなるGREENを確認した
- APIキー欠落時の既存安全性を直接固定するテストを追加し、1 passedと `fetch_amazon_products` 未呼出を確認して `TODO-004` を完了にした。この項目は修正前失敗を伴うRED→GREENではない

### ハーネスと安全境界

- `tools/ai_review/` にstrictなtask / policy / gate / review / TDD evidence / verdict契約、パス安全性、standalone clone向けcanonical single-commit policy、current repositoryを再検査するjudge、実行無効のCodex CLI dry-runを追加した
- `specs/schemas/` に上記6つのJSON Schema、`specs/prompts/` に独立reviewer / adversary prompt、`specs/tasks/` に例とPydantic検証済みの `TASK-006` 契約を追加した
- raw task SHA-256をpolicy / review / gate / TDD evidence / verdictへ、gateをhead / candidate digestへ結び付けた。test manifestはpolicyのtest content hashから再構築し、RED exit / fingerprintはtaskへ固定した
- policyはcontent/numstat後にHEAD、replace refs、index/worktreeを再検査するようにした。ただし同UIDのwritable candidateでは検査途中だけ差替えを戻す競合とreturn後のTOCTOUが残るため、別UID所有のread-only snapshotをattested実行の未完要件にした
- candidateは `git clone --no-local` または `--no-hardlinks` でlocal hardlink最適化を避けるstandalone cloneへ限定した。外部git-dir/common-dir、`commondir` / `worktrees`、attributes/alternates、Git metadata tree内のsymlink/hardlink/nested mount等を拒否するpolicyと回帰テストを追加した
- canonical candidate digest内のblob IDを内容へ束縛するため、SHA-1 repositoryだけを許可し、base/head commit、到達tree、変更前後blobをGit header込みで再hashするようにした。検査末尾にもcommit/treeを再検証し、loose blob/commit/tree改ざんの回帰テストを追加した
- pytestへtest collection前からPythonのIP socket I/O、主要な名前解決、Requests経路を遮断するguardを追加した
- `live_api` はmarkerだけでは通常収集時にskipし、`--run-live-api` も明示した場合だけguardを解除する二重opt-inにした
- 独立reviewerとadversaryがGit replace/external diff、任意gate、TDD再利用、型coercion、nested secret、output link、candidate AGENTS/Python/Git自己改ざん、linked worktree、network経路を攻撃的に再現した。各経路を回帰テスト化し、standalone isolated cloneとcandidate外artifact境界へ修正した
- GitHub ActionsへPython 3.10 / 3.13のlock、Ruff、offline pytest、diff checkを追加した。GitHub上でのworkflow実行結果はまだ確認していない
- Python 3.10にない `hashlib.file_digest()` を使わないchunk hashへ修正した。ただしローカルではPython 3.10 interpreterによる実行を確認していない
- `AI_GUIDE.md` を明示指示に基づいて初めて記載し、役割分離、RED→GREEN証拠、standalone clone、6 JSON契約、停止条件、人間承認を規約化した
- `HARNESS-RUNBOOK.md` に現在可能な非attested開発検証、残る信頼境界、将来の正規フロー、GPT-5.6 Solのrole別推論量、token最適化を集約した

この時点ではzipapp内部SHA-256をtrust anchorとせず、外部AI実行、自動 `pass`、provenance attestationを禁止した。その後に実装した外部preflight、snapshot、OS隔離、broker、attestationは次項へ分ける。

pytest monkeypatch guardはOSレベルの通信遮断ではないため、TASK-007でも開発checkoutの補助防御としてだけ扱う。

最終確認では固定件数を文書へ埋め込まず、共有ツリーに対するoffline pytest、ハーネス自己テスト、network policy自己テスト、Ruff、lock、diff check、Markdownリンク検証の終了状態をhandoffで報告する。GitHub ActionsのPython 3.10 / 3.13 job、外部Codex、Bonsai、Outscraper、実ネットワークはローカル確認に含めない。

## 5. 2026-08-16: attested AI review境界の実装

この項目も記載時点の未コミット変更である。境界コードと敵対的fixtureの実装記録であり、trusted releaseの配備、外部OpenAI APIのlive成功、課金、push/merge済みを意味しない。詳細は [EXEC-002](GOAL.md#exec-002-attested-ai-review境界の実装) を参照する。

### trust、snapshot、offline

- stdlib-only external launcher/preflightを追加し、root-owned path、`-I -S`、manifest raw SHA、open inode、現在のPython executable、harness/task/lock/schema/public key/policyをimport前に固定した
- standalone Git commitをcontent-addressed read-only base/candidate snapshotへ変換し、exact test overlayだけのRED snapshotを別digestへ結び付けた
- rootのtracked `.env.example` は全assignmentが空の安全なtemplateかを検証後、snapshot実行treeから除外するようにした
- `.env*`、`.cache` / `cache`、generic credentials/secrets、SSH/cloud/container/package-manager/provider credential pathを共通policyで拒否した
- pinned runner image、read-only rootfs/snapshot、networkなし、capabilityなし、`no_new_privileges`、resource上限からraw RED/GREEN/gate evidenceを採取・再検証する経路を追加した

### packet、broker、費用

- trusted diffと限定contextからcredential検査済みbounded packetを作り、candidate filesystemをbrokerへ渡さないtool-free Responses requestへ固定した
- canonical request JSON全体を保守的なinput予約に使い、1 call 260K input / 12K output / 250K warning、reviewer=`high`、adversary=`xhigh`、`service_tier=default` を固定した
- broker専用internal networkとcredential-free gateway専用external networkをrole/attemptごとに作り、raw inspect、固定 `api.openai.com:443`、post-inspect、cleanup、absenceをprovisioned lifecycleへ結び付けた
- SQLite ledgerへattemptを外部起動前に予約し、失敗attemptも標準544K / 4.54 USD、絶対1,088K / 7.94 USDへ累積するようにした
- broker outer rawへ全recordsと累積値を持つcanonical frozen final ledgerを加え、host SQLite削除後も同じallowlist/pricing policyからreviewer/adversaryのtyped provisioned evidenceを再構築できるようにした
- 料金値をcanonical `openai-pricing-policy.json` とruntime manifest digestへ固定した

### 署名、judge、phase protocol

- task、policy、raw offline由来gate/TDD、reviewをEd25519署名、runtime/snapshot/request/runner/log、nonce/replay ledgerへ結び付けた
- attested judgeがraw offline evidence、reviewer/adversary各1件のdistinct provisioned broker lifecycle、frozen final ledger、全署名を再構築するようにした
- 完全なclean provenanceでは `pass` を返し得るが、全verdictで `human_approval_required=true` を維持した
- `snapshot -> red-snapshot -> offline -> review-packet -> broker -> sign -> attested-judge` のclosed order、digest chain、SQLite consume-before-execute ledger、phase別mount、exclusive outputを実装した
- phaseごとにprepare/finalize input/output/committed directoryを分け、request、prepared/finalized transition、payload、`coordinator-output.json`、`artifact-manifest.json`、`phase-result.json`、external phaseの `external-evidence.json` を保存し、initial/直前committed treeを `prior-artifacts/` へcopyするcontractを追加した
- request/action/output/result/next requestをcanonical再検証し、descriptor以外をouterへdispatchしないstdlib `run_fixed_workflow` state machineを追加した
- external launcherの `--workflow` をroot-owned outer 7-phase runtimeへ接続し、phaseごとのprepare/finalize input/output/committed treeをexclusive作成してread-only化する経路を追加した
- inner `prepare|finalize` CLIを追加し、先行してsnapshotからbrokerまでをactual typed protocolへ接続した。caller supplied descriptor/argv/invocation/unknown fieldを拒否し、未完成phaseへはその時点でfail closedした
- physical snapshotをhost `snapshot-artifacts/` とcoordinator専用read-only `/snapshots` mountへ分離し、一般artifactのAGENTS拒否を維持したままsemantic/physical SHA集合をexact照合するようにした
- private key mountをsign workflow prepareだけに絞り、attested-judge prepareだけがprivate 0700 nonce ledger rootを専用RW `/nonce-ledger` mountとして受け取るようにした
- immutable phase chain、dedicated snapshot、raw offline runs、broker prepared/raw/frozen ledgerから、live broker DBなしでsign/judge共通 `CoordinatorAttestationInputs` を復元する `reconstruct_attestation_inputs` を追加した
- external launcherに7/7 handlerの完全一致を要求するreadiness gateを追加し、不完全な開発途中releaseはcredential FD読取り・broker ledger作成前にfull workflowをfail closedするようにした
- frozen bundleからrole別expectationを作ってEd25519署名する `sign` handlerと、同じimmutable evidenceからexpectationを独立再構築する `attested-judge` handlerを接続し、actual handlerを7/7とした
- production judgeをcanonical broker prepared/raw bytesとpinned policyから再finalizeするfrozen APIへ移行し、host broker SQLite削除後のpassとtamper/replay拒否を回帰テストした
- nonce ledgerをexact SQLite schema/PRAGMA/index/file identity、WAL/sidecar不在へ固定し、全nonceを単一 `BEGIN IMMEDIATE` transactionで予約するようにした。重複・既使用・部分衝突は全件rollbackする

### 残る運用作業と検証境界（配備前時点）

- 配備前時点のcode/testは7/7境界を接続済みであった。coordinatorはrootless Podman `keep-id` を必須とし、同時点のhostはArch WSL2 / UID 0 / Podmanなし / subuid・subgidなし / rootful Docker・usernsなしのためcredential FD読取り前のbackend検査でfail closedになった
- 最終AI suiteは568 passed / 1 skipped、secret-free temp copyのoffline suiteは644 passed / 1 deselectedで終了0を確認した。この件数は2026-08-16の証拠であり、運用文書の固定成功条件にしない
- 独立security reviewは7-phase重点回帰215 passedとnonce再監査を完了し、未修正CRITICAL/HIGHは0である
- lock、Ruff check/format、schema/hash、tracked+untracked whitespace、PDF不在を確認した。最新の文書同期後は25 Markdownのlocal link/anchor、全57 sh/bash block（Runbook 12 block）の構文、docs対象のdiff checkが終了0である。Python 3.10 local interpreterはなく、実行確認はCI境界として残る
- external OpenAI API、Bonsai、Outscraper、Amazonは実行していない。credential、送信内容、費用の人間opt-inも与えられていない

### 本番配備preflight境界の補完（配備前時点）

- `runtime_release workflow-init` を追加し、external approved manifest SHA、TaskSpec v2と現行harness digest、manifestに固定したexact task/public key、protected standalone clean candidate、人手承認済みpatch SHAを再検証してsequence 1 requestをexclusive作成・凍結する契約にした。credentialとnetworkは使わない
- external launcherの `--deployment-check` を追加し、workflow sensitive inputとcredentialを受け取らず、rootless backendとmanifest-pinned 4 imageのlocal inspect/networkなしsmokeだけを行い、`production_e2e_complete=false` の `nonlive_ready` evidenceへ限定した
- `tests/test_ai_review_workflow_init.py` と `tests/test_ai_review_deployment_check.py` の対象回帰は50 passedで終了0を確認した。この時点ではfake runtimeを使うcode contract検証だけであり、後続の実host `nonlive_ready` は次項へ記録する
- 配備前のread-only host probeではArch Linux on WSL2、UID 0、Podmanなし、subuid/subgidと専用userなし、user namespaceなしのrootful Docker、`/home/products` 0777、trusted `/opt`・private `/var/lib` 未作成、古く不完全なDocker imageを確認した。production検出はfail closedであり、この時点では配備可能と判定しなかった
- package/user/system変更、rootless Podman設定、承認済みclean commitと具体的TaskSpec v2 canaryからのrelease build/install、4 image build/pull、credential/API、full 7-phase live E2Eは実行していない。これらは人間承認後の別作業として残した

## 6. 2026-08-16: credential-free本番配備検証

前項のhost不足は配備前診断の履歴である。利用者の明示承認後、外部OpenAI APIを使わない範囲で本番配備前提を実hostへ構築し、`nonlive_ready` まで確認した。

### hostとtrust root

- Podman 6.1、crun、netavark、passt、fuse-overlayfs等のrootless実行stackを導入した
- coordinator専用 `ai-review`（UID/GID 1100）とcandidate identity `amazon-candidate`（UID/GID 1101）を分離し、ai-reviewだけへsubuid/subgid範囲を割り当てた
- passwd由来の `/var/lib/amazon-explorer-ai-review/home`、専用XDG config/data/runtime、active `containers/storage.conf`、rootless user storeを設定し、user namespaceとseccompを確認した
- root-owned trusted releaseを `/opt/amazon-explorer-ai-review/releases/dd4b6bde2bd2d7f3ebc67c5190949c1cc97652ee`、private artifact/key/ledger rootを `/var/lib/amazon-explorer-ai-review` に分離した

### clean releaseとcanary

- clean base commitを `dd4b6bde2bd2d7f3ebc67c5190949c1cc97652ee`、canary candidate commitを `c603ec833e13f13bdce5af4e0b36f5917e0d4f98` へ固定した
- harness SHA-256は `0d27b9c541b01b1fb6f02c270286965c1507748abe5f5667ac5a9e7250426278`、TaskSpec v2 raw SHA-256は `8507bc001dcf4d383ce43cb335e65851da740c10d6e3c4dd752c1f762b1b32fd`、canonical candidate patch SHA-256は `a9d49bea2225a903fe693f913c1f8652cdea56d02b03355e17f472363ca3b715` である
- runtime manifest SHA-256は `703d2e183558afe6e52198247888675d7f0b526f5082051a9ae75d5ea3a402ae` であり、`/usr/bin/python3.14`、release asset、4つの異なるimage digestを固定した
- `/var/lib/amazon-explorer-ai-review/candidates/TASK-CANARY-001-r2` のstandalone single-commit、決定論的RED exit 23 / GREEN exit 0、exact 2-path patchを確認し、credential-free `workflow-init` のsequence 1 requestを `/var/lib/amazon-explorer-ai-review/build/workflow-init-r2/initial` へ凍結した
- initializer出力はcanonical bindingを満たす一方、root所有0500/0400のbuild証拠であり `ai-review` UID 1100から直接読めない。deployment checkはworkflow inputを受け取らないため成功へ影響しないが、live前に再承認したanchorから `ai-review` 所有のprivate artifact rootへinitial requestを新規生成する必要がある
- 後続指示によりmanifest `703d2e183558afe6e52198247888675d7f0b526f5082051a9ae75d5ea3a402ae`、TaskSpec `8507bc001dcf4d383ce43cb335e65851da740c10d6e3c4dd752c1f762b1b32fd`、candidate head `c603ec833e13f13bdce5af4e0b36f5917e0d4f98`、canonical patch `a9d49bea2225a903fe693f913c1f8652cdea56d02b03355e17f472363ca3b715` を再照合した
- UID 1100でroot所有candidateを使った初回initializerは `candidate Git metadata must be owned by the coordinator user: refs` で安全側停止した。既存candidateを変更せず、local objectを共有しない `/var/lib/amazon-explorer-ai-review/live-candidates/TASK-CANARY-001-r2` をUID 1100で作り、書込み権を除去して再実行した
- `/var/lib/amazon-explorer-ai-review/artifacts/TASK-CANARY-001-live-init-r2/phase-request.json` をUID 1100所有0500/0400で生成した。file SHA-256は `57266f318584f01dd0fc3cccf08a9e356db67371277e974393d7c8b91f42c706`、request SHA-256は `3fce384684bbd5df6d87ddd52af8b6010f732fc5201ce9421e245fe5db0a1a82` で、UID 1101からの読取りを拒否した。Podman containerは残存せず、networkは既定 `podman` だけで、credential/API/課金は使用していない

### imageとdeployment check

- public registryからdigest固定のPython/uv base imageを取得し、coordinator、offline runner、broker、gatewayをrootless Podman storeへbuildした。coordinator/runner buildではimage内package取得を行った
- 4 image digestは順に `sha256:bd1e77e913eeecce78fe2ace2ac595a061d2c92ed4a335a137e9bf2b31d33d03`、`sha256:9ed1d64387776f3026efbcdf4957bfcd0b296493e784c6a775a17f1691f0b8b4`、`sha256:cec5e091d220e87bf0e1723ee59ea1062cf7bb5d6371cf2b55839754b470a1b1`、`sha256:36509c46496d5c3779e66185de9babf8d8ea34a1adf9fee297684c3e54cb11aa` である
- root-owned launcherの `--deployment-check` は実hostで終了0となり、`status="nonlive_ready"`、`credentials_read=false`、`external_api_called=false`、`external_network_created=false`、`production_e2e_complete=false` を確認した。独立した再実行でも同じbackend bindingとflagsを確認した。smoke用のランダム名を含むためrun全体のevidence SHAは実行ごとに異なる
- secret-free full suiteは726 passed / 1 deselected、Ruff check/formatは117 files、lock、diff、release/candidateのstrict Git fsckは終了0である
- 配備記録の同期後、project Markdown 35件のlocal link/anchorとfence balance、sh/bash block 78件の `bash -n`、repository全体の `git diff --check` は終了0である

package導入、public image pull、image内package取得とbuildには公開package/registry通信を使った。一方、OpenAI credentialは読まず、OpenAI API、review packetの外部送信、broker external network、full 7-phase live workflow、課金、provider request IDは発生していない。`nonlive_ready` をlive成功として扱わない。

## 7. 2026-08-16: 次期検索フロー v2 の仕様確定

- 現在はルートに統合された [SEARCH-FLOW.md](../SEARCH-FLOW.md) の旧技術仕様を正本として追加し、自然文からOpenAI strict intent、決定的query plan、2段階確認、Outscraper、商品補完、採点までの状態遷移を確定した
- 画像生成トグルは既定OFF、ON時はCloudflare Workers AIの `@cf/black-forest-labs/flux-2-klein-4b` で基準、左側面、右側面、背面斜めの4方向を生成する判断とした
- 派生3方向も同じCloudflare modelを使い、基準画像だけを参照し、再生成は4枚一括とした
- LLMの意味語句と決定的なSudachi/英数字tokenizationを分離し、pHash/Hamming重複検出と固定CLIP embeddingによる意味的画像scoreも分離した
- text 0.40、attributes 0.30、price 0.20、image 0.10を基準とし、欠損componentを除外して重みを再正規化し、stable keyで総合score降順にする仕様を確定した
- Outscraperの実テストは毎回送信内容を提示して明示承認を得ること、Cloudflareの最初の実試験は基準画像1枚に限定することを固定した
- 要件、設計、backend、frontend、UI、security、制約、Task、負債、索引、参考資料を同じ未実装境界へ同期した

この項目は仕様文書の確定記録であり、次期検索フローのコード実装、OpenAI・Cloudflare・Outscraperの実API、課金、ランキング品質確認は実施していない。実装は [TASK-008](GOAL.md#task-008-次期検索フロー-v2-の実装) で管理する。

この節の商品検索providerとしてOpenAIを採用する判断は、2026-08-19の後続決定で置換した。画像生成、確認、Outscraper、rankingに関する当時の判断まで取り消したことを意味しない。

## 8. 2026-08-16: 次期検索backendのcharacterizationと第1 TDDマイルストーン

- [EXEC-003](old/plans/EXEC-003-SEARCH-FLOW-V2-BACKEND.md) を作成し、現行pipelineを変更せず次期domain境界を分離する方針を固定した
- 現行backendについて、先頭1queryだけの選択、legacy Pydanticのcoercion/unknown field、価格欠損、同点stable order、TF-IDFの候補集合依存、`use_cache=False` の再計算を6件のcharacterization testで固定した
- `SearchIntentDraft`、`NormalizedSearchIntent`、`PriceCondition`、`IntentAmbiguity`、artifact provenanceをstrict/extra-forbid modelとして追加した
- 自然文2,000 code points、artifact 1 MiB、intent 49,152 UTF-8 bytes、field/配列/価格上限、NFKC、空白、空値、casefold重複、sourceにliteral根拠のないbrand/model除去を決定的normalizerへ実装した
- 日本語1件、英語1件、各200文字以下のquery plannerとintent/planのdomain-separated SHA-256を追加した。negative termはqueryへ含めない
- `model_construct()` 済みnested objectがfield validatorを迂回するREDを追加で再現し、`revalidate_instances="always"` で拒否した
- 公開関数へ `model_construct()` 済みtop-level intentを直接渡す迂回もREDで再現し、normalizer・digest・planner入口でmodel全体を再検証した
- 初回REDはpackage不在でcollection error、nested再検証REDは2 failed / 14 passed、byte上限REDとtop-level再検証REDは各1 failed / 9 passed、GREENは次期契約20 passed、characterization込み対象26 passedである。test hashとコマンドはEXEC-003へ記録した
- offline全体は752 passed / 1 deselected、Ruff、format、lock、diff checkは終了0である

OpenAI、Cloudflare Workers AI、Outscraperの実API、credential、外部送信、課金は行っていない。現行 `run_product_search()` とStreamlitも次期domainをまだ参照しない。

この節で後続作業として想定したOpenAI商品検索clientは、2026-08-19の決定で置換した。characterization testと外部通信を持たないdomain基盤の実装記録は、そのまま過去の検証事実として残す。

## 9. 2026-08-19: 商品検索LLMを現行Bonsai経路へ確定

- 利用者の明示決定により、商品検索のLLM経路は現行 `run_product_search()` が呼ぶBonsaiを正本とした
- 2026-08-16に記録したOpenAI Responses API / Structured Outputsの商品検索採用案は置換済みとし、履歴を消さず前節と [EXEC-003](old/plans/EXEC-003-SEARCH-FLOW-V2-BACKEND.md) に注記した
- `src/search_v2/` のstrict model、normalizer、query plannerは外部provider未接続のdomain基盤であり、OpenAI移行済みとも現行検索へ接続済みとも扱わない
- 商品検索からOpenAIへの自動fallbackを設けず、providerを将来変更する場合は別の明示決定、互換adapter、回帰テスト、cache移行計画を要求する方針とした
- AIレビューハーネスのreviewer / adversaryがOpenAIを利用する別経路は変更せず、商品検索の入力・credential・費用境界と分離した

この項目はprovider判断と文書同期の記録である。Bonsai、OpenAI、Cloudflare Workers AI、Outscraperのlive API呼出し、credential利用、課金は行っていない。

## 10. 2026-09-02: agents-setup 文書体系への統合

この項目は現行作業ツリーの未コミット変更を記録する。マージ済みまたは配布済みの変更ではない。

- `agents-setup` テンプレートを完全一致する接頭辞として `DEVELOPMENT.md` へ配置し、Python、Bonsai、文書同期、offline/live、TDD、Execution Plan、履歴の固有規則を追記した
- `AGENTS.md` を指示優先順位、認証情報とコマンド出力、amazon-explorer固有の安全境界、標準文書と詳細文書の目次へ書き換えた
- 標準文書として `GOAL.md` と `CHANGELOG.md` を追加し、`INDEX.md` と `ISSUES.md` を文書・作業台帳の統合入口へ更新した
- 既存の詳細文書、作業台帳、Execution Planは内容を削除せず、標準文書との関係を明記して保持した
- `EXEC-002` の古い進捗表示を、既に記録済みのrootless Podman配備、credential-free `nonlive_ready`、live用initial request準備と整合させた。full 7-phase OpenAI live E2Eとnonce長期運用は未完了のまま維持した
- `HARNESS-RUNBOOK.md` は統合対象外としてbyte単位で変更しなかった

検証結果:

- `DEVELOPMENT.md` のテンプレート接頭辞を `cmp` とSHA-256で照合: 一致
- `AGENTS.md` の機密値のコマンドライン展開禁止、露出時の停止・失効・ローテーション規則: 存在を確認
- リポジトリ内Markdown 41件のローカルリンク491件と見出しアンカー: 欠落0件
- `uv lock --check`: 成功、72 packagesを解決
- `uv run ruff check .`: 成功
- `uv run ruff format --check .`: 成功、123 files already formatted
- `uv run pytest -m 'not live_api'`: 成功、752 passed / 1 deselected
- `git diff --check`: 成功
- `HARNESS-RUNBOOK.md` のGit差分と統合前後のSHA-256: 差分なし、一致

外部Bonsai、Outscraper、OpenAI、Cloudflare、credential、課金、ブラウザE2E、full 7-phase live workflowは、この文書統合の検証で実行していない。

## 11. 2026-09-02: HARNESS-RUNBOOK の標準文書体系への統合

この項目は、同日の `agents-setup` 文書統合に対する後続依頼を、現行作業ツリーへ反映した未コミット記録である。前節の「当時Runbookを変更しなかった」という事実は保持し、その後に行った再編として記録する。

- `HARNESS-RUNBOOK.md` を、実行コマンド、期待結果、停止条件、再実行規則の正本へ再編した
- 現在状態と未完了項目は `GOAL.md` / `EXEC-002`、信頼境界は `SECURITY.md`、AI契約は `AI_GUIDE.md`、過去のhost・release・digestはこの `WORKLOG.md` へ委ねた
- 旧Runbookのhost固有UID・path・SHA、古い固定テスト件数、library関数一覧、nonce DBのDDL、モデル・料金の固定説明を運用手順から外した。過去実績は既存の第5・第6節から削除していない
- 依存取得を伴い得る `uv sync` を環境準備へ分離し、検証コマンドを `--frozen --offline --no-sync` と `uv lock --check --offline` へ更新した
- ハーネス対象pytestを `tests/test_ai_review_*.py tests/test_network_policy.py` へ更新し、現行test追加へ追随させた
- host診断からDocker fallbackを外し、launcherが固定する7つのPodman環境変数、rootless/user namespace/seccomp、trusted/private pathの診断へ更新した
- repository内にproduction-readyなTaskSpec v2がない現状を明記し、bootstrap v1とゼロ埋めexampleのproduction流用を禁止した
- releaseのimage変数対応、source command前後のcheckout全体再帰検査、checkout直下 `.git`、untracked / ignored entry拒否、root-owned external uv environmentとclean allowlist環境を伴うcanonical build source、root-owned Python / release root、manifestの外部承認anchor、workflow初期化、credential-free deployment checkを現行CLIへ合わせた
- key provision / rotationを既存key非上書きの新規protected directoryへ分離し、一時release stageへprivate keyを入れない手順へ更新した
- live例をBash fail-fast、initial request digest / key IDの外部照合、dynamic credential FDのpath / open FD同一性検査、相互に重ならないsecurity region、EXIT cleanup、新規output / broker ledger、永続nonce ledger、実行ごとの外部送信・credential・費用承認へ更新した
- `AGENTS.md`、`INDEX.md`、`GOAL.md`、`CHANGELOG.md` の「Runbookは変更対象外」という記述を、恒久的な役割分担へ同期した
- `AGENTS.md`、`DEVELOPMENT.md`、`INDEX.md`、`GOAL.md`、`BACKEND.md`、`FRONTEND.md`、`QUICKSTART.md`、`SECURITY.md`、`AI_GUIDE.md`、`PLANS.md`、`MEMORY.md`、`REQUIREMENTS.md`、`TROUBLESHOOTING.md`、`UI.md` の規範的なoffline検証例を `--offline --no-sync` へ同期した。過去の実行記録に含まれる当時のコマンドは履歴として保持した

検証結果:

- `build_zipapp`、`runtime_release schema-bundle`、`runtime_release keygen`、`runtime_release manifest`、`runtime_release workflow-init`、`external_launcher` の `--help` とRunbookの引数を照合: 一致
- Runbook内のBash block 11件と、リポジトリ内Markdownのshell block 78件を `bash -n` で検査: 成功
- dynamic credential FDのopen、別FD、cleanupをsecretなしの `/dev/null` で検査: 成功
- リポジトリ内Markdown 41件のローカルリンク506件と見出しアンカー: 欠落0件
- `uv lock --check --offline`: 成功、72 packagesを解決
- `uv run --frozen --offline --no-sync ruff check .`: 成功
- `uv run --frozen --offline --no-sync ruff format --check .`: 成功、123 files already formatted
- ハーネス対象offline pytest: 成功、650 passed / 1 deselected
- repository全体のoffline pytest: 成功、752 passed / 1 deselected
- `git diff --check`: 成功
- `HARNESS-RUNBOOK.md` のSHA-256: 再編前 `523ae0cf749fcd6afaa2e4a5880204499e6cbf7d4aa5fe715ec6c70ab8ad4d8f`、再編後 `175829ae938b43e8246cba4ca3de872e7c9d0a59677f7effe34a81c357b0b585`

外部Bonsai、Outscraper、OpenAI、Cloudflare、credential、課金、Podman host診断、image pull/build、`--deployment-check`、full 7-phase live workflowは実行していない。

## 12. 2026-09-02: 旧文書の `docs/old/` 集約

この項目は、標準文書への統合後も現行正本と履歴資料を混在させないために行った、未コミットの文書整理を記録する。

- 2026-08-15の文書統合commit `2fd9c5b1c12efbcf14172d62ad23341291292a3a` で削除された旧設計文書6件を、削除直前の親commit `fb2115aac26c1bcadc3c0a662f60cb7c4fdb43b6` から `docs/old/` へ復元した
- 復元した `CACHE_DESIGN.md`、`DATA_MODEL_SPEC.md`、`ENVIRONMENT_VARIABLES.md`、`EXTERNAL_API_SPEC.md`、`PRODUCTION_DESIGN_GUIDE.md`、`README_dev.md` は、6件とも復元元のGit blob IDと一致した
- 完了済みで履歴資料と明記された `EXEC-001` と、完了済みでprovider案が置換された `EXEC-003` を `docs/old/plans/` へ移した
- 進行中の `EXEC-002`、商品検索の正本 `SEARCH-FLOW.md`、実行手順の正本 `HARNESS-RUNBOOK.md`、未完了項目を含む各台帳は現行位置に残した
- `docs/old/README.md` に、アーカイブが現行要件・設計・手順・進行状態を上書きしないこと、復元元commit、現行統合先、完了済みPlanの参照先を記録した
- `AGENTS.md`、`DEVELOPMENT.md`、`INDEX.md`、`PLANS.md` と、旧Planを参照する現行文書のリンクを新しい位置へ同期した

検証結果:

- リポジトリ対象Markdown 48件、ローカルリンク566件、見出しアンカーを検査: 欠落0件
- shell block 86件を `bash -n` で検査: 成功。Runbook内のBash blockは11件のまま
- 旧設計文書6件を `git rev-parse <source>:<path>` と `git hash-object <restored-path>` で比較: 6件すべて一致
- `AGENTS.md` または `docs/INDEX.md` から到達できるdocs配下Markdownを検査: 35/35件
- `docs/DEVELOPMENT.md` のagents-setupテンプレート接頭辞14,087 bytes: 一致
- `git diff --check`: 成功

コード、外部API、credential、課金、Podman、deployment check、live workflowは、この文書移動の検証では実行していない。

## 13. 2026-09-02: 非テンプレートMarkdownの統合とアーカイブ

この項目は、`agents-setup` テンプレートにないプロジェクトMarkdownを標準文書へ統合し、統合元を `docs/old/` へ移した未コミット変更を記録する。

- テンプレート文書13件を現行正本とし、ユーザー指定の例外としてルート `SEARCH-FLOW.md` と `docs/HARNESS-RUNBOOK.md` だけを現行Markdownへ残した
- 旧 `docs/SEARCH-FLOW.md` の技術仕様とルート `UI-FLOW.md` の操作仕様を、ルート `SEARCH-FLOW.md` へ全文統合した
- `HARNESS-RUNBOOK.md` は統合・移動せず、独立した実行手順の正本として維持し、移動後の標準文書を指すリンクだけを同期した
- 要件、設計、UI、開発規約、トラブルシューティング、Task、TODO、負債、Memory、旧索引、3件のExecution Planを対応するテンプレート文書へ統合した
- 旧 `examples/` のMarkdown 7件を、この文書の [統合済み旧検証資料](#統合済み旧検証資料) へ全文統合した。旧索引の役割情報は [REFERENCES.md](REFERENCES.md#統合済み旧ドキュメント索引) へ統合した
- 実行時prompt 3件は内容を標準文書へ統合し、現行実行ファイルを `.txt` に変更した。元Markdownは `docs/old/runtime/` へ保存し、コード、テスト、TaskSpecの派生harness digestを同期した
- 統合元27件は元位置からなくなり、すべて `docs/old/` に存在する。既存の旧設計6件とアーカイブ索引を含め、`docs/old/` のMarkdownは34件である
- 継続地点は [GOAL.mdの再開位置](GOAL.md#再開位置) に集約した。通常のローカル実装はTASK-008のBonsai v2 response境界から、外部承認が必要な作業はTASK-007のlive E2Eから再開する

検証結果:

- `docs/DEVELOPMENT.md` の先頭14,087 bytesは `agents-setup` テンプレートと一致
- `AGENTS.md` のMarkdown目次14リンクは全件リポジトリ内の実在ファイルへ解決
- 現行Markdown 15件のローカルpath・見出しanchorは欠落0件
- 統合元27件について、元位置なし・アーカイブ先ありを確認
- 実行用 `.txt` 3件は対応するアーカイブ元MarkdownとSHA-256が一致
- 現行Markdownのfence不整合0件、sh/bash block 78件の `bash -n` は全件成功
- `uv lock --check --offline`: 成功、72 packagesを解決
- `uv run --frozen --offline --no-sync ruff check .`: 成功
- `uv run --frozen --offline --no-sync ruff format --check .`: 成功、123 files already formatted
- prompt参照とtrusted zipappを含む関連テスト: 114 passed
- `uv run --frozen --offline --no-sync pytest -m 'not live_api'`: 752 passed / 1 deselected
- `git diff --check`: 成功

この検証ではBonsai、Outscraper、OpenAI、Cloudflare、credential、課金、ブラウザ、Podman host、full 7-phase live workflowを実行していない。

## 14. 2026-09-02: Bonsai v2 strict応答境界

この項目は、TASK-008第2マイルストーンのうち、外部通信を伴わないBonsai response adapterを実装した未コミット変更を記録する。詳細は [EXEC-004](GOAL.md#exec-004-bonsai-v2-strict応答境界) を参照する。

- `src/search_v2/bonsai_adapter.py` を追加し、exact full raw response bytesからOpenAI互換envelopeと `choices[0].message.content` を取り出すpure adapterを実装した
- response bodyはUTF-8かつ1,048,576 bytes以下、contentは単一のstrict JSON objectに限定し、duplicate key、`NaN` 等の非有限数、Markdown fence、前後の説明文、JSON断片、unknown・missing field、型coercionを拒否した
- valid draftを既存normalizerへ渡し、source input、exact prompt、canonical `SearchIntentDraft` schema、full raw response bodyのSHA-256を `NormalizedSearchIntent` へ結び付けた
- response不一致は生contentやPydantic入力値を含まない固定 `BonsaiResponseError` へ変換した
- 現行 `src/clients/bonsai_client.py`、legacy prompt、`run_product_search()`、cache schemaは変更せず、v2 request・prompt・HTTP・pipeline接続を後続へ残した

TDD記録:

- RED test SHA-256: `fe607bb84982d14b958d2e08b4dc2f681c1d23ca279d987118c24361e66ff04e`
- RED: `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_bonsai_adapter.py` はmodule不在により終了2、collection error
- 整形後test SHA-256: `caf8f60d2583cd5449cd3edb30d1aa2b77296dc3dcdfc1f07baba13d819c4610`
- focused GREEN: 26 passed
- intent、query planner、characterization、legacy Bonsai clientを含む関連回帰: 62 passed
- `uv lock --check --offline`: 成功、72 packagesを解決
- `uv run --frozen --offline --no-sync ruff check .`: 成功
- `uv run --frozen --offline --no-sync ruff format --check .`: 成功、125 files already formatted
- `uv run --frozen --offline --no-sync pytest -m 'not live_api'`: 778 passed / 1 deselected
- 現行Markdown 15件のlocal path・見出しanchor・fence、Python 3.10 AST、`git diff --check`: 成功

このマイルストーンではBonsai、Outscraper、OpenAI、Cloudflareへの外部通信、credential、課金、実モデルの意味品質、現行検索へのv2接続を確認していない。次の通常ローカル作業は、別Execution Planを作成してTASK-008の決定的tokenizerへ進む。

## 15. 2026-09-02: 決定的検索tokenizer

この項目は、TASK-008第3マイルストーンとして、外部通信を伴わないSudachi/英数字tokenizerをquery plannerへ接続した未コミット変更を記録する。詳細は [EXEC-005](GOAL.md#exec-005-決定的検索tokenizer) を参照する。

- `src/search_v2/tokenizer.py` を追加し、日本語はSudachiPy `SplitMode.C` の名詞・動詞・形容詞・形状詞、英数字はNFKC/casefold後の `[a-z0-9]+` をsurface順に抽出した
- Latin surfaceをSudachi normalized form由来のカタカナtokenへ重複変換せず、token順と最初の表記を維持して重複を除いた
- NFKC後のURL、改行、control文字はtoken抽出前に拒否し、URLの句読点を除去して通常queryへ救済しない
- product name、category、required・preferred termsをtoken化し、brand/model identifierは原形を維持した。negative termsは引き続きqueryへ含めない
- 200文字上限は意味語句group単位で適用し、1つの低優先語句の一部tokenだけをqueryへ残さない
- 現行 `src/services/text_processing.py`、legacy query選択、ranking、cache、外部API経路は変更していない

TDD記録:

- RED tokenizer test SHA-256: `1f6c708f609bb900f08c4b0764c87e906c8addca20bc4611e80616b1bfb6c548`
- RED planner test SHA-256: `37029e795362e1e2703ad8be7a60fb48220d449fcc50d0a65cf4112338d5954a`
- RED: module不在により終了2、collection error
- 初回GREEN試行: 2 failed / 19 passed。Sudachiが文中の `製` を接尾辞、連続した `あ` を感動詞として分類したため、品詞filterと200文字fixtureの責務を分離した
- 次の試行: 1 failed / 20 passed。token列を平坦化すると低優先意味語句の一部だけが200文字内へ残ったため、意味語句groupを原子的に採否するよう修正した
- 整形後tokenizer test SHA-256: `8d4ed3a4642b0f0a3f49eeb98e5e1dc14534dd67f7f15ab1190558c6d60e1ddc`
- 整形後planner test SHA-256: `da031d71b1dc01a5400008f3d7499422f56198f4719600563a21c48efe935488`
- focused GREEN: 23 passed
- intent、Bonsai adapter、characterization、legacy Bonsai clientを含む関連回帰: 75 passed
- `uv lock --check --offline`: 成功、72 packagesを解決
- `uv run --frozen --offline --no-sync ruff check .`: 成功
- `uv run --frozen --offline --no-sync ruff format --check .`: 成功、127 files already formatted
- `uv run --frozen --offline --no-sync pytest -m 'not live_api'`: 791 passed / 1 deselected
- 現行Markdown 15件のlocal path・見出しanchor・fence、Python 3.10 AST、`git diff --check`: 成功

このマイルストーンではBonsai、Outscraper、OpenAI、Cloudflareへの外部通信、credential、課金、実モデル・実検索の意味品質、現行検索へのv2接続を確認していない。次の通常ローカル作業は、別Execution Planを作成してTASK-008の2段階承認state machineと費用ledgerへ進む。

## 16. 2026-09-02: 2段階承認と費用予約境界

この項目は、TASK-008第4マイルストーンとして、外部通信を伴わない承認段階state machineと利用量予約を実装した未コミット変更を記録する。詳細はEXEC-006を参照する。

- `src/search_v2/approval.py` に、owner・session、strict intent・query plan、Outscraper request、任意画像set、provider allowance、runtime digest、作成時刻・15分期限を結ぶcanonical承認planを追加した
- `src/search_v2/state_machine.py` に、`draft` から `scrape_submitted` までのrevision付きsnapshot、第1確認、画像set確認、第2確認、計画変更時の失効を追加した
- raw approval tokenは発行時に1回だけ返し、snapshotと同一process内の消費ledgerにはdomain-separated SHA-256だけを保持する。並行した同一token claimは1件だけ成功する
- `src/search_v2/usage_ledger.py` に、Bonsai・Cloudflare・Outscraperのcall・token・整数micro-USDをper-user-day・per-session・global-dayで送信前予約する同一process内ledgerを追加した
- callerは予約時刻を指定できず、未開始予約だけを解放できる。開始後の成功・失敗はどちらも利用量へ残し、pricing・利用policy digestの不一致とsnapshot集計上限超過を拒否する
- 画像ONは開始済み4-call予約と成功済み画像setを必要とし、最大2 setに制限した。画像OFFはCloudflare状態を持たない
- Outscraper予約はapproved plan、owner、session、pricing・利用policy、1 call、費用上限に加え、開始時刻が承認発行時刻以後であることを必要とする
- 現行 `run_product_search()`、cache、Streamlit、CLI、外部clientは変更せず、後半state、永続repository、API・UI、複数workerのtransactionを後続へ残した

TDD記録:

- 初回REDは3 test fileのmodule importで終了2、3件のcollection error。usage ledger test SHA-256は `fb935fae5fcd2966ecd38f1c90f59925d10e25213a250829174bea7a8c01a68e`、approval testは `0bf017297f164295716223cb4a6ed6166059a1b73a35a4742058954e472e6c7a`、state machine testは `d1b2f130a7984a22617e93387141bbfd3a5c96525f79f6ee26a6a4de352f40b6`
- security再確認で、承認発行前に開始したOutscraper予約が通るREDを `1 failed` で再現した。test SHA-256は `1c09bffa9a46d6fd5166b4a160e3ed1f209a1e4addcd59f646d9fa1ca30db2a6`
- 最終SHA-256は `approval.py` が `452dec2b6d96923abe00f187696acb7cacf8070f16ee880c32de0b9d9834537b`、`state_machine.py` が `de4b810b2af0acf46d6e681c210b0420fc82fa4cac6d48139bf1298e9b968111`、`usage_ledger.py` が `3070071039f55924492190b6bb20a4e3bd4be52dad871989bf099377f4a4dc8e`
- 最終test SHA-256はapprovalが `0fc20431c58e72cb2c699907e1a57cb3a4ab69b24d579da99f747d19b9c9af67`、state machineが `1c09bffa9a46d6fd5166b4a160e3ed1f209a1e4addcd59f646d9fa1ca30db2a6`、usage ledgerが `1aac865fcad24b7f9d55a869471f04bd47b4b342402dfd3d8e2c60275eb18e81`
- focused GREENは26 passed、既存v2・characterization・legacy Bonsaiを含む関連回帰は101 passed
- `uv lock --check --offline`: 成功、72 packages
- Ruff check: 成功。format check: 成功、133 files already formatted
- offline全体pytest: 817 passed / 1 deselected
- 現行Markdown 15件のlocal link・anchor・fenceとsh/bash block 78件、Python 3.10 AST 133件、`agents-setup` の `DEVELOPMENT.md` テンプレート接頭辞、`git diff --check`: 成功

外部Bonsai、Outscraper、OpenAI、Cloudflare、credential、課金、browser、実サービスE2Eは実行していない。同一process内のoffline modelとtestの成功を、永続・複数worker・現行アプリへの接続済み境界として扱わない。次の通常ローカル作業は、新しいExecution Planを作成してCloudflare 4方向request builderのmock TDDへ進む。

## 17. 2026-09-02: Cloudflare 4方向request builder

この項目は、TASK-008第5マイルストーンとして、外部通信を伴わないFLUX.2 klein 4B request descriptorを実装した未コミット変更を記録する。詳細は [EXEC-007](GOAL.md#exec-007-cloudflare-4方向request-builder) を参照する。

- `src/search_v2/cloudflare_request.py` に、exact model ID、基準・左・右・背面の固定順、512px出力、attempt 1・2、angle別seedを持つstrict request contractを追加した
- multipart text fieldは `prompt`、`width`、`height`、`seed` だけに固定し、公式仕様で4に固定された `steps` と、provider既定値を使う `guidance` を送らない
- 基準要求は画像を持たず、派生3要求は同じ `input_image_0`、PNG SHA-256、byte長、縦横、実行時bodyを持つ。`input_image_1` から `_3` は使わない
- 参照PNGは8 MiB以下、signature、IHDR・IDAT・IEND順、chunk長、CRC、縦横511px以下を検証し、bodyをserializable metadataから除外した
- promptは商品種別、カテゴリ、色、必須条件、見た目の特徴をJSON属性dataとして含め、source input全文、価格、negative・preferred term、brand、model number、credentialを含めない
- prompt contract、個別request、4件setにdomain-separated SHA-256を付け、参照画像byteの変更をmetadata digestで検出する
- endpoint、account ID、Authorization、multipart boundary、HTTP、応答parse、512px出力から511px PNGへのsRGB正規化、画像保存、state・ledger接続は後続へ残した

TDD記録:

- RED test SHA-256: `ee1fb8a819757aec6ec48bbf34cdd6ccbc3699c59842b0b33d82511ce4740d7e`
- RED: `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_cloudflare_request.py` はmodule不在により終了2、collection error
- 実装SHA-256: `b3684f73828895727a17ed838c42b60136333cffa73af07d4cdb124e2368a6e4`
- 整形後test SHA-256: `0785ece00d39fa2b520be850d601bece759af95764a91b0a5462cebd07814c17`
- focused GREEN: 19 passed
- 既存v2、characterization、legacy Bonsaiを含む関連回帰: 120 passed
- `uv lock --check --offline`: 成功、72 packages
- `uv run --frozen --offline --no-sync ruff check .`: 成功
- `uv run --frozen --offline --no-sync ruff format --check .`: 成功、135 files already formatted
- `uv run --frozen --offline --no-sync pytest -m 'not live_api'`: 836 passed / 1 deselected
- 現行Markdown 15件のlocal link 586件・anchor・fence、sh/bash block 78件、Python 3.10 AST 135件、`git diff --check`: 成功

公式Cloudflare model page、launch guide、一般REST endpointはpublic documentationとして参照したが、Cloudflare API、credential、課金、画像生成、画像品質、browser、現行検索への接続は実行・確認していない。次の通常ローカル作業は、新しいExecution Planを作成してOutscraper複数query request境界と明示承認guardのoffline TDDへ進む。

## 18. 2026-09-02: 検索フローとテスト方針の統合整理

この項目は、ルート `SEARCH-FLOW.md` の役割を次期画面の利用者向け操作へ限定し、テスト関連の内容をテンプレート正本 `docs/DEVELOPMENT.md` へ統合した未コミット変更を記録する。

- `SEARCH-FLOW.md` を、条件整理、任意の4方向参考画像、最終確認、5段階の待機、結果、30日間の履歴、確認の取消、エラー回復を利用者の操作順で読める構成へ変更した
- internal API、型、provider request、採点式、実装順序を利用者フローから除き、技術契約の参照先を `BACKEND.md`、`REQUIREMENTS.md`、`SECURITY.md` へ統一した
- `docs/DEVELOPMENT.md` の [統合済みテスト方針](DEVELOPMENT.md#統合済みテスト方針) に、検証区分、外部通信なしゲート、現行・次期検索の自動テスト範囲、次期画面の受入チェック、provider別live試験の個別承認条件、記録禁止情報をまとめた
- 統合元 `docs/TESTING.md` を `docs/old/TESTING.md` へ移し、現行目次と参照をテンプレート正本へ統一した
- `AGENTS.md`、`README.md`、関連する要件・設計・計画・参照文書の説明と見出しリンクを新しい役割分担へ更新した

検証結果:

- `uv lock --check --offline`: 成功、72 packages
- `uv run --frozen --offline --no-sync ruff check .`: 成功
- `uv run --frozen --offline --no-sync ruff format --check .`: 成功、137 files already formatted
- `uv run --frozen --offline --no-sync pytest -m 'not live_api'`: 856 passed / 1 deselected
- 現行正本15 Markdownのローカルpath、見出しanchor、fence: 欠落0件
- `git diff --check`: 成功

上記pytestは外部通信を除外したmock・fixture中心の確認である。Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、実画像生成、ブラウザ、production E2Eは実行していない。

## 19. 2026-09-02: Outscraper複数query request境界と明示承認guard

この項目は、TASK-008第6マイルストーンとして、外部通信を伴わないOutscraper Amazon Products request descriptorと明示承認guardを実装した未コミット変更を記録する。詳細は [EXEC-008](GOAL.md#exec-008-outscraper複数query-requestと明示承認guard) を参照する。

- `src/search_v2/outscraper_request.py` に、1回のGETへ日英最大2件のqueryを固定順で反復するstrict request contractを追加した
- 送信候補parameterを `query`、`domain=amazon.co.jp`、`language=ja`、server-side postal code、`limit=24`、`async=true` へ限定し、1 queryなら24件、2 queryなら最大48件へ固定した
- HTTPS endpointのcredential・query・fragment・非canonical hostを拒否し、endpoint、query plan、実query batch、postal code、固定parameter、最大候補数をdomain-separated SHA-256へ結んだ
- requestの実query batch、query plan digest、request digestをtoken消費前に承認planへ照合し、owner・session・期限・single-use token、承認後に開始したOutscraper 1 call予約が一致した場合だけexecution permitを返すguardを追加した
- request不一致時はtokenを消費せず、permitはraw token、API key、Authorization headerを保持しない
- 現行 `src/clients/outscraper_client.py` と現行pipelineは変更せず、HTTP、polling、response parse、候補正規化を後続境界へ残した

TDD記録:

- 初期RED test SHA-256: `0b97aa6d880b0e95bd398952e56629830d48453b6d61024a5e6fe420d65dc7cc`
- 初期RED: `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_outscraper_request.py` はmodule不在により終了2、collection error
- supplemental RED test SHA-256: `68cc8e5306f4fc8c328ca22b4c62c6ab20d4089e2526a276c8543e39f05eb79a`
- supplemental RED: query plan digestとrequest digestを整合させた承認外query差替えtestが1 failed / 19 passedとなり、実query batchのexact照合不足を再現した
- 実装SHA-256: `88ff8e1e8dd03753e4ed295782bc615f75589da5b1b0fb774a99df9ec387de61`
- 整形後test SHA-256: `d1ce25c108850db62dfc548c229a513036824fc4f9fdf515b29166803ed797b6`
- focused GREEN: 20 passed
- 既存v2、characterization、legacy Outscraperを含む関連回帰: 164 passed
- `uv lock --check --offline`: 成功、72 packages
- `uv run --frozen --offline --no-sync ruff check .`: 成功
- `uv run --frozen --offline --no-sync ruff format --check .`: 成功、137 files already formatted
- `uv run --frozen --offline --no-sync pytest -m 'not live_api'`: 856 passed / 1 deselected
- 現行Markdown 15件のlocal link 635件・anchor・fence、sh/bash block 79件、Python 3.10 AST 137件、`agents-setup` の `DEVELOPMENT.md` テンプレート接頭辞、`git diff --check`: 成功

公式Amazon Products pageとOpenAPI JSONを参照したが、Outscraper API、credential、課金、Amazon候補取得、browser、現行検索への接続は実行・確認していない。offline permitと `scrape_submitted` はHTTP送信済みの証拠ではない。次の通常ローカル作業は、新しい `EXEC-009` を作成して決定的商品正規化、未知属性維持、post-Outscraper LLM非呼出しguardのoffline TDDから再開する。

## 20. 2026-09-02: 決定的商品正規化と未知属性境界

この項目は、TASK-008第7マイルストーンとして、外部通信を伴わないOutscraper商品候補normalizerを実装した未コミット変更を記録する。詳細は [EXEC-009](GOAL.md#exec-009-決定的商品正規化と未知属性境界) を参照する。

- `src/search_v2/product_normalization.py` に、検証済みOutscraper request descriptor、query順、provider request ID、明示的なUSD/JPY換算profileへ結果を結ぶstrictな商品batchを追加した
- title、description、brand、categories、color、material、features、価格、通貨、rating、review count、Prime、在庫・配送、ASIN、商品・画像URLをproviderの観測値だけから正規化し、観測できない属性とPrimeを未知のまま残す
- query本文、postal code、credential、raw approval token、raw responseをbatchへ複製せず、request・query plan・profile・batchのdomain-separated digestと内部provenanceを保持する
- ASIN、次にcanonical Amazon商品URLで入力順を保って重複を除き、titleだけが同じ候補は除外しない。出所不明、承認外query、非対応通貨、空title等は固定理由でrejectし、生値をrejectや例外へ含めない
- 本文系raw文字列32,768文字、数値文字列256文字、identifier 64文字、配列100要素、候補24または48件で正規化前の処理量を有界化し、49件目は全候補を一時展開せず拒否する。review countはportableな符号付き64-bit範囲に限定する
- moduleはintent、prompt、client、callbackを受け取らず、Bonsai adapter、OpenAI SDK、`src.clients` をimportしない。命令風の商品文もデータとして保持するだけで属性推論や外部呼出しを行わない
- 現行 `amazon_product_normalization.py`、cache、`run_product_search()`、Outscraper HTTP・pollingを変更せず、承認permitとの実行時接続、画像proxy、ranking、永続化を後続へ残した

TDD記録:

- 初期RED test SHA-256: `8625affa5c4952deca66eb8ef4e2860a9f614b7c991c7eda565c9e7dbd7b0661`
- 初期RED: `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_product_normalization.py` はmodule不在により終了2、collection error
- 初回実装後は2 failed / 26 passedとなり、改行を空白へ畳む契約と空request IDのtest assertionを修正して28 passedにした
- URL上限、21件目画像の破棄記録、全fieldの切詰め記録を追加したsupplemental REDは3 failed / 28 passed。test SHA-256は `adbd0a2326f0ae9cbe4a1f19ae1e7fef6b95731c5ce64857dfd6229e1289dc5e`
- Unicode正規化と数値抽出前の処理量上限を追加したresource-bound REDは2 failed / 31 deselected。当時のtest SHA-256は `d065380091a1a0e74d9c22710bd4b9c424075f439bf272ff188a67e57a741431`
- 外側container、ASIN、review count、metadata field名を固定するstrict-boundary REDは4 failed / 31 passed。最終test SHA-256は `2e155ed3a912a52d4e3ee5252e968dc08a81bb09e43257dc38cb3d4d903ff3d0`
- 最終module SHA-256: `835e36b4b703f13bf5de849150b7f919da4c6c49b516d9890f4519d872aa89a6`
- focused GREEN: 35 passed。既存v2、characterization、legacy Outscraper・normalizerを含む関連回帰: 205 passed
- `uv lock --check --offline`: 成功、72 packages
- `uv run --frozen --offline --no-sync ruff check .`: 成功
- `uv run --frozen --offline --no-sync ruff format --check .`: 成功、139 files already formatted
- `uv run --frozen --offline --no-sync pytest -m 'not live_api'`: 891 passed / 1 deselected
- 現行Markdown 15件のlocal link 650件・anchor・fence、sh/bash block 79件、Python 3.10 AST 139件、`git diff --check`: 成功

このマイルストーンではOutscraper、Bonsai、OpenAI、Cloudflareへの外部通信、credential、課金、実Amazon候補、browser、現行pipeline、永続化を実行・接続していない。normalizerは検証済みrequestへ応答を結ぶが、single-use承認permit、HTTP送信、provider成功を単独では証明しない。次の通常ローカル作業は新しい `EXEC-010` を作成し、image proxy、pHash dedupe、pinned CLIP runtimeのoffline・fixture-first設計から再開する。

## 21. 2026-09-02: 安全な画像取得・pHash・固定CLIP境界

この項目は、TASK-008第8マイルストーンとして、外部clientを内蔵しない画像proxy core、pHash重複判定、固定CLIP asset・embedding score境界を実装した未コミット変更を記録する。詳細は [EXEC-010](GOAL.md#exec-010-安全な画像取得phash固定clip境界) を参照する。

- `src/search_v2/image_proxy.py` に、exact host allowlist、HTTPS、最大8件のglobal DNS address、実peer IP一致、redirect拒否、10秒、identity encoding、8 MiBを固定して注入resolver・transportへ渡す境界を追加した
- JPEG・PNG・WebPのMIMEとdecoder format、単一frame、縦横4096px・総pixel数4096²以下、Pillow decompression bomb warningを検証し、raw URL・metadataを残さないRGB artifactへ変換した。pixel digestには寸法とRGB byteをdomain-separated形式で結んだ
- `src/search_v2/image_similarity.py` に、32x32 grayscale DCTの8x8低周波から作る64-bit pHash、Hamming距離5以下だけを使う順序維持の重複判定を追加した。pHashと距離は意味score関数の入力にしない
- `openai/clip-vit-base-patch32` revision `12b36594d53414ecfba93c7200dbb7c7db3c900a` のconfig、preprocessor、weightをfile名、byte数、SHA-256へ固定した。local exact file setをload前に検証し、注入encoderへ検証済みrootと `local_files_only=True` を渡す境界を追加した
- encoder出力は件数、512次元、float、有限値を検証してL2正規化し、4参照方向それぞれの最大cosine平均を `clamp((mean + 1) / 2, 0, 1)` へ写像する。scoreは現行pinned runtime digestだけを受理し、画像ranking flagはfalseのままにした
- Pillow 12.2.0をdirect dependencyへ昇格し、既存lockをoffline更新した。Torch、Transformers、ONNX Runtime、imagehash、NumPyは追加していない
- 現行pipeline、cache、設定、外部provider、browserを変更せず、実DNS・pinned-IP TLS transport、proxy endpoint、model asset配布、実encoder、process isolation、ranking接続を後続へ残した

TDD記録:

- 初期RED: `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_image_proxy.py tests/test_search_v2_image_similarity.py` は2 module不在により終了2、collection error。test SHA-256はそれぞれ `8dfaac0e6481bcf28604b76499d95d04cbc3bbe3d456ddae9a500cf51b5ae9fe`、`8dd1ada6b25608b2e8397817473052a8eb2e01e80fd2e6372662d2425afe190d`
- 初回実装は73 passed / 1 failed。一様白画像の理論上0となるDCT係数へ浮動小数誤差が残ることを確認し、最大振幅に対する固定許容差以下を0へ正規化した。1px市松模様はpHashが捨てる高周波だけだったため、同じ「構造差は閾値外」というassertionを低周波の四分割fixtureで検証した
- runtime digest supplemental RED: 同じ未承認digestを全embeddingへ付けたscoreが拒否されず1 failed。当時のtest SHA-256は `26911ea91c8cceac3f9b3f13765e918c46cb9a6c19f95059c0019825bd9ba997`
- pixel digest supplemental RED: 寸法をdigestへ結ぶ関数がなく1 failed。当時のtest SHA-256は `462070c23984304e087c4faa9a9094a4f5433aa41ae13edd9a06a5f7ace4abf5`
- 最終module SHA-256: `image_proxy.py` は `094723f4b7075509fc6ab668124b02afabefbaee59ce9f9758ed77c9f35e2d75`、`image_similarity.py` は `a035d748ed82049f181be31d3209b412019d72b0ec94618bec35aae0a11abe2f`
- 最終test SHA-256: image proxyは `e719cb0fe972b8996baf0fca9fe0f0fa9eae1902b4f4167148b54023af1ffbce`、image similarityは `40469caaf3fd54757a52c572560bb501da1f774b46f0875d810c4f18a362e975`
- focused GREEN: 76 passed。既存v2、characterization、legacy normalizer・rankingを含む関連回帰: 253 passed
- `uv lock --check --offline`: 成功、72 packages
- `uv run --frozen --offline --no-sync ruff check .`: 成功
- `uv run --frozen --offline --no-sync ruff format --check .`: 成功、143 files already formatted
- `uv run --frozen --offline --no-sync pytest -m 'not live_api'`: 967 passed / 1 deselected
- 現行Markdown 15件のlocal link 668件・見出しanchor・fence、sh/bash block 79件、Python 3.10 AST 143件、`git diff --check`: 成功

Pillow公式security handbook、OpenAI公式CLIP repository、pinned Hugging Face model revisionを参照した。公開model metadata、4,186 bytesのconfig、316 bytesのpreprocessorを読んでdigestを照合し、weightはHEAD metadataの605,247,071 bytesとSHA-256だけを照合してdownloadしていない。Bonsai、Outscraper、OpenAI API、Cloudflare API、実商品画像、credential、課金、実CLIP asset・推論、browser、現行pipelineは実行・接続していない。fixture/mock成功を実TLS transport、model load、画像ranking品質として扱わない。次の通常ローカル作業は新しい `EXEC-011` を作成し、ranking profile v2、欠損weight再正規化、negative penalty、stable sort、score breakdownをoffline TDDで実装するところから再開する。

## 22. 2026-09-02: 次期フロントエンドの外部納品待ち境界

利用者の明示指示により、次期フロントエンドは外部委託中・未納品として扱うことを作業境界へ追加した。

- 納品完了が明示されるまで、委託成果物の内容確認、レビュー、起動、画面確認、テスト、バックエンド・API接続を行わない
- `SEARCH-FLOW.md` と `FRONTEND.md` は納品物の目標仕様として維持し、納品済み・確認済みとは扱わない
- ranking、provider境界、履歴保存など、フロントエンドへ依存しないバックエンド作業は継続できる
- `AGENTS.md`、`NEXT-STEPS.md`、`SEARCH-FLOW.md`、`FRONTEND.md`、`GOAL.md`、`REQUIREMENTS.md` へ同じ境界を反映した

この変更では委託成果物を取得、確認、起動、テストしておらず、バックエンド・APIへの接続も行っていない。Markdownのローカルリンクと `git diff --check` は成功した。コードを変更していないため、Pythonテストは実行していない。

## 23. 2026-09-03: 決定的ranking v2とscore breakdown

この項目は、TASK-008第9マイルストーンとして、現行pipelineから分離したnetwork非依存のranking v2を実装した未コミット変更を記録する。詳細は [EXEC-011](GOAL.md#exec-011-決定的ランキングv2とスコア内訳) を参照する。

- `src/search_v2/ranking.py` に、strict・frozenな固定profile、component、score breakdown、ranked batchとdomain-separated digestを追加した
- title 0.40、attributes 0.30、price 0.20、image 0.10をbase weightとし、画像はdisabledに固定した。未指定・未観測componentは0点と区別して除外し、利用可能なweightだけを1.0へ再正規化する
- titleは商品名・カテゴリ・brand・model numberの言語別token coverage、attributesはrequired 3、preferred 2、カテゴリ・色・特徴・brand 1と `ObservedProductAttributes` の構造化観測値だけの一致率を使う
- 価格はintentのexact・range・min・max modeに従い、negative termは観測済みtitle・store・description・属性への一致1件につき0.20、最大0.50を減点する。negative一致だけで商品を除外しない
- scoreとcontributionは4桁へ丸め、同点を全候補で一意なOutscraper response index昇順で解決する。intent・query plan・normalized product batch・固定profileのdigest連鎖を再検証する
- 現行legacy ranking、cache、設定、`run_product_search()`、Streamlit、CLIを変更せず、provider pipeline、API、履歴、外部委託中のフロントエンドへの接続を後続へ残した

TDD・検証記録:

- 初期RED test SHA-256: `cd511be128031b3fb9f465b0ba9459ca9dbff7fae68334003ee4619bac0cdf24`
- 初期RED: `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_ranking.py` はmodule不在により終了2、collection error
- Ruffで未使用type importを削除した後の最終test SHA-256: `492b7b89e2af31005afdc91bd94e3c7877d379b7936cc6534ca1344ffd789e07`。受入assertionは変更していない
- 最終module SHA-256: `be5d6d28e042a2144eaccb7d458f57dbd0e1a45fc8aa7afd1de26247dde35c50`
- focused GREEN: 17 passed。既存v2全境界、legacy ranking、backend characterizationを含む関連回帰: 266 passed
- `uv lock --check --offline`: 成功、72 packages
- `uv run --frozen --offline --no-sync ruff check .`: 成功
- `uv run --frozen --offline --no-sync ruff format --check .`: 成功、145 files already formatted
- `uv run --frozen --offline --no-sync pytest -m 'not live_api'`: 984 passed / 1 deselected
- 現行Markdown 16件のlocal link 688件・anchor 861件・fence 195件、Python 3.10 AST 145件、`git diff --check`: 成功

このマイルストーンではBonsai、Cloudflare、Outscraper、OpenAIへの外部通信、credential、課金、実商品、実画像、実CLIP asset・推論、ranking品質、browser、現行pipeline、cache、API、委託フロントエンドを実行・接続していない。次の通常ローカル作業は新しい `EXEC-012` を作成し、Bonsai v2 request builder・HTTP adapterと次期実行境界をoffline TDDから再開する。

## 24. 2026-09-03: Bonsai v2 canonical requestと利用量実行境界

この項目は、TASK-008第10マイルストーンとして、現行pipelineから分離したBonsai v2 request・注入transport実行境界を実装した未コミット変更を記録する。詳細は [EXEC-012](GOAL.md#exec-012-bonsai-v2-requestと実行境界) を参照する。

- `src/search_v2/bonsai_intent_prompt.txt` に、利用者入力を非信頼データとして扱い、説明やMarkdownなしのstrict JSON objectだけを返すv2専用system promptを追加した
- `src/search_v2/bonsai_request.py` に、固定prompt、canonical `SearchIntentDraft` schema、利用者入力を含むexact chat-completions JSON bodyと、raw本文を保持しないstrict request descriptorを追加した
- requestはloopback addressへのHTTPまたはcanonical HTTPS、exact `/v1/chat/completions`、固定JSON header、redirect禁止、identity encoding、最大300秒、1 MiB応答上限へ限定し、source・prompt・schema・bodyとrequest全体をSHA-256へ結んだ
- request digestへ一致するreserved Bonsai intent 1 callと、request UTF-8 byte数＋最大出力token以上の予約だけを開始し、注入transportを1回だけ呼ぶ。strict response parse成功を `succeeded`、通信・HTTP・応答失敗を `failed` としてledgerへ確定する
- responseはstatus、content type・encoding・length、streamed byte上限を検証し、生入力、prompt、request body、生response、transport例外をdescriptor・結果・固定例外へ残さない
- 現行legacy Bonsai client、設定、prompt、`run_product_search()`、cache、Streamlit、CLIを変更せず、実HTTP transport、自動再試行、pipeline、API、外部委託中のフロントエンドを後続へ残した

TDD・検証記録:

- 初期RED test SHA-256: `9ce96b2156a234820f7aad66ad9450c1ff56954325cbba7d9286f2587e063c97`
- 初期RED: `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_bonsai_request.py` はmodule不在により終了2、collection error
- 最終module SHA-256: `cbcf8bb4802c3cb16145dbbe579cbbb7ec03403accb678163b12f185526e2910`
- prompt SHA-256: `9eed0e3a2361b8cfaf72b3165e149f774aa524b57493f7355513898b49612ee7`
- Ruff整形後の最終test SHA-256: `8f2aeccfb3bf2abda97cf5528dd342bfe47aaa442eac99d2bc22c50194026fe8`
- focused GREEN: 44 passed。Bonsai adapter、intent、usage ledger、state machine、legacy Bonsai、backend characterizationを含む関連回帰: 114 passed
- `uv lock --check --offline`: 成功、72 packages
- `uv run --frozen --offline --no-sync ruff check .`: 成功
- `uv run --frozen --offline --no-sync ruff format --check .`: 成功、147 files already formatted
- `uv run --frozen --offline --no-sync pytest -m 'not live_api'`: 1028 passed / 1 deselected
- 現行Markdown 16件のlocal link 695件・heading 942件・fence 195件、Python 3.10 AST 147件、`agents-setup` の `DEVELOPMENT.md` テンプレート接頭辞14,087 bytes、`AGENTS.md` の安全規則・目次、`git diff --check`: 成功

このマイルストーンではBonsai、Cloudflare、Outscraper、OpenAIへの外部通信、credential、課金、実model品質、現行pipeline、cache、API、browser、委託フロントエンドを実行・接続していない。次の通常ローカル作業は新しい `EXEC-013` を作成し、実Bonsaiへ接続せずにRequests通信をmockしてBonsai v2実HTTP transportを実装する。

## 25. 2026-09-03: Bonsai v2 Requests HTTP transport

この項目は、TASK-008第11マイルストーンとして、現行pipelineから分離したBonsai v2 HTTP transportを実装した未コミット変更を記録する。詳細は [EXEC-013](GOAL.md#exec-013-bonsai-v2-http-transport) を参照する。

- `src/search_v2/bonsai_http.py` に、EXEC-012の `BonsaiRequestTransport` を満たすRequests製adapterを追加した
- canonical endpoint・header・body・timeout・redirect・encoding・1 MiB上限を送信前に再検証し、bodyを再serializeせず `data` へ渡して1回だけPOSTする
- 新規Sessionの `trust_env` を無効にし、既定header・cookie・proxy・authを除去する。TLS検証を有効にし、HTTP/HTTPS adapterのretryを0、redirectをfalse、connect/read timeoutを同じ上限へ固定する
- status、Content-Type、Content-Encoding、Content-Lengthだけを応答metadataへ投影する。非200、非JSON、圧縮、宣言済み上限超過のbodyを読まず、stream実測が1 MiBを超えた時点で停止する
- 成功・通信失敗・stream失敗・metadata不正の全経路でResponseとSessionを閉じ、生body、任意header、例外詳細を結果や固定エラーへ残さない
- 現行legacy Bonsai client、設定、`run_product_search()`、cache、Streamlit、CLIを変更せず、実Bonsai、pipeline、自動再試行、API、外部委託中のフロントエンドを後続へ残した

TDD・検証記録:

- 初期RED test SHA-256: `f42a5319ca6053eafac4a59d7cf186dbcc160bfd4dc254ec38c87f5c1126ba33`
- 初期RED: `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_bonsai_http.py` はmodule不在により終了2、collection error
- 最初の実装後は29件成功し、統合fixture 1件が入力に存在しないbrandを期待して失敗した。入力へ根拠語を追加し、normalizerの既存仕様を弱めずに修正した
- 最終module SHA-256: `725be374c34ddfbf5579d3fa2327468529450e398f79086ec1a8bab1465bbab0`
- Ruff整形後の最終test SHA-256: `457768048d5c2b35f5d7131b2e65b4d163db577b29dd6dac46d8462e6d272236`
- focused GREEN: 32 passed。Bonsai request・adapter、intent、usage ledger、state machine、legacy Bonsai、backend characterizationを含む関連回帰: 146 passed
- `uv lock --check --offline`: 成功、72 packages
- `uv run --frozen --offline --no-sync ruff check .`: 成功
- `uv run --frozen --offline --no-sync ruff format --check .`: 成功、149 files already formatted
- `uv run --frozen --offline --no-sync pytest -m 'not live_api'`: 1060 passed / 1 deselected
- 現行Markdown 16件のlocal link 708件・heading 957件・fence 195件、Python 3.10 AST 149件、`agents-setup` の `DEVELOPMENT.md` テンプレート接頭辞、`AGENTS.md` の安全規則・目次、`git diff --check`: 成功

このマイルストーンではRequests通信をすべてmockし、Bonsai、Cloudflare、Outscraper、OpenAIへの外部通信、credential、課金、実model品質、現行pipeline、cache、API、browser、委託フロントエンドを実行・接続していない。次の通常ローカル作業は新しい `EXEC-014` を作成し、実Outscraperへ接続せずにRequests通信をmockしてOutscraper v2 HTTP・task・polling adapterを実装する。

## 26. 2026-09-03: Outscraper v2 Requests HTTP・task・polling境界

この項目は、TASK-008第12マイルストーンとして、現行pipelineから分離したOutscraper v2 HTTP transportと非同期task・polling実行境界を実装した未コミット変更を記録する。詳細は [EXEC-014](GOAL.md#exec-014-outscraper-v2-httptaskpolling境界) を参照する。

- `src/search_v2/outscraper_http.py` に、`AuthorizedOutscraperRequest`、`scrape_submitted` snapshot、同じledgerの開始済み1-call予約を再検証する実行境界を追加した
- task作成時は承認済みの日英最大2 queryと固定parameterをexact順で1回のGETへ渡し、API keyはserver-side引数から `X-API-KEY` headerへだけ注入する
- HTTP要求ごとに新規Requests Sessionを作り、`trust_env=False`、既定header・cookie・proxy・auth除去、TLS検証、HTTP/HTTPS retry 0、redirect禁止、30秒timeout、identity encoding、streaming 8 MiB上限、Response・Session closeを固定した
- 初回の `Pending`・`Success`、結果取得の `Pending`・`Success`・`Failure`、正常0件、最大50 poll、最後のpoll後のno-sleepを区別した。結果URLは承認endpointと同一originかつ初回request IDのexact `/requests/{id}` に限定し、poll応答IDも一致させる
- Content-Type、Content-Encoding、Content-Lengthと実測byte、UTF-8、duplicate JSON key、非有限数、status、候補数をfail closedに検証し、query、URL、API key、生provider文を例外・戻り値のmetadataへ含めない
- 成功時は限定した `data` とprovider request IDを返して予約を `succeeded`、通信・HTTP・応答・危険URL・task失敗・待機超過では予約を `failed` へ確定する。失敗attemptも利用上限へ残る
- 公式Amazon Products APIとRequest Results APIで、反復query、非同期taskのrequest ID・結果URL、`Pending`・`Success`・`Failure` の現行形状を確認した。公式page内の `.com` / `.cloud` 不一致があるため、承認descriptorに固定した既存 `.cloud` endpointを変更していない
- REDはproduction module不在によるcollection errorを期待理由として確認した。初回test SHA-256は `b343a82ae1166c9b125e3555b6d49609861da2cf8231085892e89f9857a5a664`、stream・JSON検査を補正したSHA-256は `846e4343cce32c7b25f5fc3b10c8a40ffb56f51b5e29166766d26f521631b04b`
- 最終module SHA-256は `51d652b56d792143ee4a64b6385d88bf0a82ae2d5793a684338e82029683148e`、最終test SHA-256は `01f9fc8791b4003b0bc4dda490a6c4dea7520dbc3c88c7d16f9ee0302b6571b9`
- focused GREEN: 50 passed。Outscraper request・approval・usage・normalizer・ranking、legacy client、characterizationを含む関連回帰: 201 passed
- `uv lock --check --offline`: 成功、72 packages。Ruff check: 成功。Ruff format check: 成功、151 files already formatted
- `uv run --frozen --offline --no-sync pytest -m 'not live_api'`: 1110 passed / 1 deselected
- 現行Markdown 16件のlocal link 727件・heading 972件・fence 195件、Python 3.10 AST 151件、`agents-setup` の14,087-byte `DEVELOPMENT.md` template接頭辞、`AGENTS.md` の目次・安全規則、`git diff --check`: 成功

このマイルストーンではRequests通信をすべてmockし、Bonsai、Cloudflare、Outscraper、OpenAIへの外部通信、credential、課金、実Amazon候補、現行pipeline、cache、API、browser、委託フロントエンドを実行・接続していない。次の通常ローカル作業は新しい `EXEC-015` を作成し、本境界の完了結果を商品正規化・rankingへ渡す後半pipelineと、成功・失敗・0件を扱う検索stateをoffline TDDで実装する。

## 27. 2026-09-03: 検索後半pipelineと完了state

この項目は、TASK-008第13マイルストーンとして、成功済みOutscraper executionから商品正規化、ranking、検索完了までを結ぶoffline後半pipelineを実装した未コミット変更を記録する。詳細は [EXEC-015](GOAL.md#exec-015-検索後半pipelineと完了state) を参照する。

- `src/search_v2/state_machine.py` に `products_received`、`products_normalized`、`search_completed`、`search_failed` を追加し、候補・正規化・除外・ranking件数、batch digest、正常結果種別、失敗工程・固定コードの整合性をstrictに検証するようにした
- `src/search_v2/product_pipeline.py` に、execution、承認plan、session revision、intent、query plan、Outscraper request、成功済み利用量、normalization・ranking profileの結合を再検証する境界を追加した
- pipelineは検証済み `data` を観測値だけの商品normalizerから画像無効のrankingへ渡し、商品ありと正常0件を成功として区別する。provider実行、正規化、ranking失敗は工程別固定コードだけをstateへ残す
- stateには件数とdigestだけを投影し、API key、query、postal code、生provider応答、商品本文、URL、生例外文を保持しない。商品を持つnormalized・ranked batchはresultへ分離し、reprへ露出させない
- 初期RED test SHA-256は `1e5c72e52753a07be9f86ad8585c13d6773bafdc7353164c6248e5ec36f07a98`。production module不在による `ModuleNotFoundError` のcollection errorを期待理由として確認した
- 最終SHA-256はstate machine `6dcaf952c40eff034e9c3b08e3dbd5c7449c9d3c6603adb2b6becd2e78a06a7a`、pipeline `5c21c12350d6fc15567cbf0cc02943cba4edd5323730cb311dd7005b61806e0a`、test `94236f38458831c52d86034e85556078b900f989c9a17d135c22e3bbf716e246`
- focused GREEN: 21 passed。state、承認・利用量、Outscraper、normalizer、ranking、legacy client・pipeline、characterizationを含む関連回帰: 203 passed
- `uv lock --check --offline`: 成功、72 packages。Ruff check: 成功。Ruff format check: 成功、153 files already formatted
- `uv run --frozen --offline --no-sync pytest -m 'not live_api'`: 1123 passed / 1 deselected
- 現行Markdown 16件のlocal link 743件・heading 988件・fence 195件、Python 3.10 AST 153件、`agents-setup` の14,087-byte `DEVELOPMENT.md` template接頭辞、`AGENTS.md` の目次・安全規則、`git diff --check`: 成功

このマイルストーンではBonsai、Cloudflare、Outscraper、OpenAIへの外部通信、credential、課金、実Amazon候補、ranking品質、Bonsaiから履歴までの全体orchestration、現行pipeline、cache、API、browser、委託フロントエンドを実行・接続していない。次の通常ローカル作業は新しい `EXEC-016` を作成し、Cloudflare 4方向request descriptorのHTTP応答検証と画像正規化を注入transport・fixtureでoffline TDDする。

## 28. 2026-09-03: Cloudflare v2 Requests HTTP・応答・画像正規化境界

この項目は、TASK-008第14マイルストーンとして、開始済みCloudflare 4-call予約から固定順のmultipart HTTP、厳密な応答検証、決定的PNG正規化、`image_review` stateまでを結ぶoffline境界を実装した未コミット変更を記録する。詳細は [EXEC-016](GOAL.md#exec-016-cloudflare-http応答と画像正規化) を参照する。

- `src/search_v2/cloudflare_http.py` にexact Workers AI endpoint、server-side account ID・API token、prompt-onlyを含むmultipart POST、120秒timeout、4 MiB応答上限を持つRequests transportを追加した
- HTTP 200、JSON content type、identity encoding、UTF-8、duplicate key、非有限数、exact envelope、canonical Base64をfail closedに検証し、2 MiB以下・単一frame・512×512 PNGだけをmetadataなしRGB PNGへ決定的に再encodeする
- 基準画像は表示用512×512を保持し、派生3方向へだけ511×511の共有参照PNGを渡す。基準、左、右、背面の固定順で4 callsを逐次実行し、自動retryしない
- `image_generating` state、intent・query・owner・session・usage policy、開始済み4-call予約を送信前に再検証する。全件成功時だけ予約を `succeeded`、sessionを `image_review` にし、途中失敗では一部artifactを返さず予約を `failed` にする
- artifactの通常serializeとreprには角度、attempt、request・image digest、byte数、寸法だけを残し、account ID、API token、生応答、生provider文、画像bodyを含めない
- 公式model output objectとREST envelopeを組み合わせたexact JSON shapeはofflineのfail-closed契約である。実Cloudflare応答による適合は未確認のため、live実行前に現行公式schemaを再確認する

TDD・検証記録:

- 初期RED test SHA-256: `3cd90b28fa287a84791a304a8bffee2d16fa6d2f27516c23ff87f7c05242a68d`
- 初期RED: `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_cloudflare_http.py` は終了1、60 errors。全ケースが未実装境界を示す同じrequirement assertionで失敗した
- 最終module SHA-256: `198b60e6dd835d43865e1f172565bb36960e5fdf3b6454139ded5127f3067e34`。最終test SHA-256は初期REDから不変
- focused GREEN: 60 passed。Cloudflare request、state、承認・利用量、画像proxy・類似度、rankingを含む関連回帰: 198 passed
- `uv lock --check --offline`: 成功、72 packages。Ruff check: 成功。Ruff format check: 成功、155 files already formatted
- `uv run --frozen --offline --no-sync pytest -m 'not live_api'`: 1183 passed / 1 deselected
- 現行Markdown 16件のlocal link 755件・heading 1003件・fence 195件、Python 3.10 AST 155件、`agents-setup` の14,087-byte `DEVELOPMENT.md` template接頭辞、`AGENTS.md` の目次15件・安全規則、`git diff --check`: 成功

このマイルストーンでは通信をすべてmockし、入力画像には合成PNGだけを使った。Bonsai、Cloudflare、Outscraper、OpenAIへの外部通信、credential、課金、実生成画像、実Amazon候補、生成・ranking品質、Bonsaiから履歴までの全体orchestration、永続repository、API、browser、外部委託中のフロントエンドを実行・接続していない。次の通常ローカル作業は新しい `EXEC-017` を作成し、既存のBonsai、確認、任意画像、Outscraper、正規化、ranking、完了stateを一つのofflineバックエンドorchestrationへ接続する。

## 29. 2026-09-03: 段階別offline検索orchestration

この項目は、TASK-008第15マイルストーンとして、既存のBonsai、確認、任意画像、Outscraper、正規化、ranking、完了stateを、利用者操作ごとに停止する一つのoffline backend境界へ接続した未コミット変更を記録する。詳細は [EXEC-017](GOAL.md#exec-017-offline検索orchestration) を参照する。

- `src/search_v2/orchestrator.py` にstrictなprovider予算・Bonsai設定・backend policyと、`IntentReview`、`ImageReview`、`SearchReview`、非reprの `ApprovedSearch` を追加した
- Bonsaiのexact 1-call予約・実行後は `intent_review`、Cloudflareの4枚成功後は `image_review`、画像OFF・採用・破棄後は `search_approval` で返し、利用者確認を自動通過しない
- 画像OFFではCloudflare 0 call、最終確認と承認token発行だけではOutscraper 0 callとした。承認後に作成した開始済み予約、exact request、single-use tokenが一致する場合だけOutscraperと後半pipelineを実行する
- 画像ONでは4枚1組、最大2組の一括再生成を既存state・利用量境界へ接続した。`state_machine.py` に成功済み画像setを破棄して画像なしで続行する遷移を追加し、既発生のCloudflare利用量はledgerへ残す
- stageとplanはBonsai request・利用量、任意画像、Outscraper request、normalization・ranking profile、実装・利用policyのdigestを再検証する。credential、生provider応答、raw approval tokenを保存せず、Outscraper transport失敗は固定 `product_search_failed` resultへ変換する
- sequentialなtoken再利用は、新しいOutscraper reservationとtransport callより前に拒否する。商品あり、正常0件、provider固定失敗を区別する

TDD・検証記録:

- 初回RED test SHA-256: `c1903e12b58bc0c5329e059a4a3579f2b33a9aae7b7b3a68abc8474e06c43051`
- nested model改ざんfixtureとimport検査だけを補正したRED test SHA-256: `fe27b855fdbabe5181297b7c407687a97647945b1f53f20e56cc3844dbaa7c79`
- RED: `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_orchestrator.py` は終了1、12 errors。全ケースが未実装境界を示す同じrequirement assertionで失敗した
- 最終orchestrator SHA-256: `a69e126798bfb4805cd3f65d7a55b9bde9146d3d1da6c6216a8cf300fe24df1a`。最終state machine SHA-256: `bb76d3ba97562e6763bc7eb9a4a16c069869e9a638a415a29be6c837004158ae`。追加受入条件を含む最終test SHA-256: `ec07fdd39f49315435095e852f5a58ec68491b0f37c7e359c9d63a4681cc86f6`
- focused GREEN: 14 passed。全v2、legacy client・pipeline・ranking、backend characterizationを含む関連回帰: 528 passed
- `uv lock --check --offline`: 成功、72 packages。Ruff check: 成功。Ruff format check: 成功、157 files already formatted
- `uv run --frozen --offline --no-sync pytest -m 'not live_api'`: 1197 passed / 1 deselected
- 現行Markdown 16件のlocal link 774件・heading 1020件・fence 195件、Python 3.10 AST 157件、`agents-setup` の14,087-byte `DEVELOPMENT.md` template接頭辞、`AGENTS.md` の目次15件・安全規則、`git diff --check`: 成功

このマイルストーンでは注入transport、fixture JSON、合成PNGだけを使った。Bonsai、Cloudflare、Outscraper、OpenAIへの外部通信、credential、課金、実生成画像、実Amazon候補、生成・ranking品質、現行pipeline、永続repository、API、browser、外部委託中のフロントエンドを実行・接続していない。Cloudflare生成が途中失敗した場合は利用量をfailedへ確定できるが、現行sessionを再試行または画像なし続行へ進める遷移がない。次の通常ローカル作業は新しい `EXEC-018` を作成し、この回復stateをoffline TDDする。

## 30. 2026-09-03: Cloudflare画像生成途中失敗後の回復state

この項目は、TASK-008第16マイルストーンとして、4方向画像生成が途中失敗した同じsessionを、失敗利用量を保持したまま明示的一括retryまたは画像なし続行へ進めるoffline境界を追加した未コミット変更を記録する。詳細は [EXEC-018](GOAL.md#exec-018-cloudflare画像生成失敗後の回復state) を参照する。

- `SearchSessionSnapshot` に `image_generation_failed` と `failed_image_reservation_id` を追加し、active予約・完成画像bindingと同時に存在できないstrict stateとした
- `record_image_generation_failure()` は `image_generating` のactive予約と、owner・session・query・usage policy・4 callsが一致するfinished `failed` 予約だけを結び、revisionを進める
- `retry_failed_image_set()` は最大2組の既存上限内で、失敗IDと異なる新しいstarted予約だけを `image_generating` へ接続する。`discard_failed_image_attempt()` は利用量ledgerを変更せず画像OFFの `search_approval` へ進める
- `ImageFailureReview` は固定失敗code、session、Bonsai証拠、最大2件のCloudflare attempt履歴を結び、credential、生provider detail、部分画像を保持しない
- `generate_images()`、`regenerate_images()`、`retry_failed_images()` はCloudflare固定例外後のfailed予約を回復stageへ投影する。回復stageを返すだけでは再通信せず、明示retryだけが新しい4-call予約を作る
- retry成功後の `ImageReview` と最終planは、失敗・成功両方のattemptを保持してCloudflare 8 callsを算入する。画像なしを選んだ最終planは画像OFF・0 calls表示とするが、ledgerのfailed予約は削除・解放しない
- 2回目の成功・失敗後はいずれも、3組目の予約やtransport callより前に上限超過を拒否する

TDD・検証記録:

- production code変更前のstate test SHA-256は `7a4cda1005cfa16ab7c192384ad40dd6031c12b512441d618e732aaf2061ef1c`、orchestrator test SHA-256は `de0e5cca3b8fa18ecb94547350a783b92059da6e955fa104401ad87207844d13`
- REDは追加9 test nodeが終了1・9 failed。回復遷移・stage・明示retryが存在せず、従来経路がCloudflare固定例外で終了することを確認した
- 実装後にretry自体の失敗と2回成功後の3組目拒否を追加し、最終state test SHA-256は `7a4cda1005cfa16ab7c192384ad40dd6031c12b512441d618e732aaf2061ef1c`、orchestrator test SHA-256は `5b77e3377349d873fe83472e73ebb170b922284cb5ce19aeaece9f29f7f34e94`
- 最終state machine SHA-256は `2dbc54d347a269f36041375449b51b7bb6f7ae470c61584df9be1c3cbdc054af`、orchestrator SHA-256は `f35dfd74d55969aaa3260131023e02c3bf5e6dcca64788390c1ec32edcab9345`
- focused回復契約は11 passed、state・orchestrator全体は32 passed、全v2回帰は475 passed
- `uv lock --check --offline` は72 packages、Ruff check・formatは成功し、`uv run --frozen --offline --no-sync pytest -m 'not live_api'` は1207 passed / 1 deselected
- 現行Markdown 16件のlocal link 785件・heading 1035件・fence 195組、Python 3.10 AST 157件、`agents-setup` のコミット済み14,087-byte `DEVELOPMENT.md` template接頭辞、`AGENTS.md` 目次16件・安全規則、`git diff --check`: 成功

このマイルストーンでは注入transport、fixture JSON、合成PNGだけを使った。Bonsai、Cloudflare、Outscraper、OpenAIへの外部通信、credential、課金、実生成画像、実Amazon候補、生成・ranking品質、現行pipeline、永続repository、API、browser、外部委託中のフロントエンドを実行・確認・接続していない。`docs/FRONTEND.md` と `docs/HARNESS-RUNBOOK.md` も変更していない。次の通常ローカル作業は新しい `EXEC-019` を作成し、owner分離した30日検索履歴repositoryの冪等保存・一覧・詳細・個別削除・期限削除をoffline TDDする。

## 31. 2026-09-03: owner分離した30日検索履歴repository

この項目は、TASK-008第17マイルストーンとして、正常完了した検索の表示用snapshotをowner内で冪等保存し、再起動後の一覧・詳細、参考画像取得、個別削除、30日期限削除を行うローカルSQLite境界を追加した未コミット変更を記録する。詳細は [EXEC-019](GOAL.md#exec-019-owner分離した30日検索履歴repository) を参照する。

- `history_repository.py` に、strict・frozen・extra-forbidな保存入力、一覧、詳細、参考画像modelと、固定messageのinput・conflict・not-found・storage errorを追加した
- SQLite `user_version=1` に、owner内のcompletion key一意性と表示JSONのSHA-256を持つ `search_history`、固定順4方向の512×512 PNG BLOBを持つ `history_reference_images` を分離した。legacy JSON cacheは読み書き・移行・削除していない
- 同じowner・completion key・同じpayloadの再保存は同じ公開locatorを返し、異なるpayloadは上書きしない。別ownerの同じkeyは独立させ、owner不一致、不在、期限切れは同じ固定not-foundにする
- 一覧は未期限の同じownerだけを完了時刻の新しい順に返す。詳細と画像の表示modelから、内部ID、owner、completion key、provider、model、request、postal code、token、利用量、digest、raw scoreを除外した
- 完了時刻から30日到達後はpurge前でも一覧・詳細・画像から除外する。個別削除と期限削除はforeign key cascadeを使い、履歴と専有画像を同じtransactionで物理削除し、失敗時はrollbackする
- 新規POSIX DB fileは0600で作り、final-component symlink、非regular file、安全でない既存file mode、未知または占有済みversion 0 schema、必須table・columnの欠落、表示JSONとdigestの不一致を固定storage errorで拒否する

TDD・検証記録:

- API名だけのscaffoldを使った有効な初期RED test SHA-256は `9fbc8e60fca96f04cb46f43df9d9e883ec57ac612b314f3a5716ea6c0b8e22cf`。focusedは終了1、1 passed / 12 failedで、保存・読取・削除・期限削除と未知schema拒否が未実装のため失敗した
- それより前の実行はscaffold UTC validatorの `NameError` で全件失敗し、要求したrepository未実装を示さないためRED証拠へ採用していない
- 実装後、valid JSONを変更しても保存digestとの不一致を検出できない状態を追加RED 13 passed / 1 failed、test SHA-256 `407e8bc0a5811db0c6a94c24af2d2da7a74a9a92a369f924e66f54cd5d650caa` で確認し、表示JSONのSHA-256検証を追加した
- 安全でない既存DB modeを暗黙chmodする状態を追加RED 14 passed / 1 failedで確認し、modeを変更せずfail closedにした。最終test SHA-256は `90237c8169040ad340df3cf0de4689b19c47c7be1e3270962fa3c06274cc8214`
- 最終repository SHA-256は `4a10f542c0ca5e2e1fa14dd519543f7b66ad43122b10e97b4dab3248cb8ba8e9`
- focused履歴repositoryは15 passed、全v2回帰は490 passed
- `uv lock --check --offline` は72 packages、Ruff check・formatは成功し、`uv run --frozen --offline --no-sync pytest -m 'not live_api'` は1222 passed / 1 deselected、`git diff --check` は成功した
- 現行Markdown 16件のlocal link 795件・heading 1071件・fence 195組、Python 3.10 AST 159件、`agents-setup` のコミット済み14,087-byte `DEVELOPMENT.md` template接頭辞、`AGENTS.md` 目次15件を確認した

このマイルストーンでは一時SQLite、合成表示データ、合成PNGだけを使った。実利用者データ、実Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、実Amazon候補、実画像、現行pipeline、完了resultから履歴入力への変換、認証、API、browser、外部委託中のフロントエンドを実行・確認・接続していない。`docs/FRONTEND.md` と `docs/HARNESS-RUNBOOK.md` も本マイルストーンでは変更していない。次の通常ローカル作業は新しい `EXEC-020` を作成し、正常完了result・承認stage・元入力・任意画像から表示用履歴snapshotを作ってrepositoryへ冪等保存するoffline境界をTDDする。

## 32. 2026-09-03: 完了検索から表示用履歴への変換と保存

この項目は、TASK-008第18マイルストーンとして、正常完了した検索result、承認済みreview、元入力を表示用履歴へ変換し、既存SQLite repositoryへ冪等保存するoffline境界を追加した未コミット変更を記録する。詳細は [EXEC-020](GOAL.md#exec-020-完了検索から表示用履歴への変換と保存) を参照する。

- `history_snapshot.py` は元入力のexact SHA-256をBonsai requestとintent provenanceへ再照合し、owner、session、intent、query、承認plan、完了時刻、normalized・ranked batch、任意画像の結合を保存前に検証する
- 正常な `results` と `empty` だけを `SearchHistoryWrite` へ変換する。`failed`、別reviewとの混在、ranked batchへ差し替えられたnormalized batch外の商品を固定 `HistorySnapshotError` で拒否する
- 条件は商品種別、必須、希望、避けたい、色、特徴、ブランド、型番、明示または推定価格の表示値へ変換する。商品はrank、title、先頭画像URL、価格、説明、Amazon URL、一致・未確認・注意点、画像比較案内だけを持つ
- raw score、component、weight、採用言語、provider、model、request ID、郵便番号、raw approval token、利用量、内部digestを表示商品へ入れない。現行画像rankingは無効であるため、採用画像を保存しても順位付けには使っていないと明示する
- 画像OFFまたは破棄済み画像は0枚、採用済み画像は固定順4枚を履歴へ複製する。同じ完了resultは決定的なcompletion keyを使い、保存再試行でprovider、正規化、rankingを呼ばない
- repositoryのtransaction失敗後も完了resultを変更せず、同じ入力で再保存できることを一時SQLite triggerで確認した

TDD・検証記録:

- API名だけのscaffoldを使ったRED test SHA-256は `6fc501d445b2d410fa6c1dd216b1429a08cd22d68371cfbad098c62e58c253d3`。focusedは終了1、1 passed / 7 failedで、変換・保存関数の `NotImplementedError` により失敗した
- 初期GREENでfixtureの候補上限を24件と仮定した1 assertionが失敗した。ブランド名・型番から英語queryも構築されるため、承認済みOutscraper requestどおり48件へ期待値を修正した
- 最終module SHA-256は `396f28e28f8283dfffd4970ff484435cd5ce2c33c7e424366a096cac881ae071`、test SHA-256は `be38b6c4d6f0a869a06dc2aea5c8882fe5b7701dca5c8a814e9edda2cea6fa39`
- focused履歴変換は8 passed、全v2回帰は498 passed
- `uv lock --check --offline` は72 packages、Ruff check・formatは161 filesで成功し、`uv run --frozen --offline --no-sync pytest -m 'not live_api'` は1230 passed / 1 deselected、`git diff --check` は成功した
- 現行Markdown 16件のlocal link 802件・heading 1086件・fence 195組、Python 3.10 AST 161件、`AGENTS.md` 目次15件を確認した

このマイルストーンでは注入transport、fixture JSON、合成PNG、一時SQLiteだけを使った。実利用者データ、実Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、実Amazon候補、実画像、生成・ranking品質、現行pipeline、認証、API、browser、外部委託中のフロントエンドを実行・確認・接続していない。`docs/FRONTEND.md` と `docs/HARNESS-RUNBOOK.md` も本マイルストーンでは変更していない。次の通常ローカル作業は新しい `EXEC-021` を作成し、DNSで検証した接続先IPへ固定しつつ元hostのTLS検証を行うserver-side image HTTPS transportを、外部通信なしでTDDする。

## 33. 2026-09-03: pinned-IP画像HTTPS transport

この項目は、TASK-008第19マイルストーンとして、検証済みのnumeric IPへ1回だけ直接接続しながら元host名でTLS証明書を検証する商品画像HTTPS transportを追加した未コミット変更を記録する。詳細は [EXEC-021](GOAL.md#exec-021-pinned-ip画像https-transport) を参照する。

- `image_proxy_http.py` はcanonicalなHTTPS URL、1〜8件の重複しないglobal IP、10秒timeout、redirect禁止、identity encoding、8 MiB上限をsocket作成前に再検証する
- 検証済み一覧の先頭IPだけへIPv4またはIPv6 TCP socketで直接接続し、別IPへのfailover、retry、環境proxy、Requests、名前解決を行わない
- default server-auth TLS contextへcertificate required、hostname check、TLS 1.2以上、compression禁止、HTTP/1.1だけのALPNを固定し、元host名をSNI・証明書検証へ渡す。接続後のpeer IPが選択済みIPと一致するまでHTTP要求を送らない
- origin-form GETとHost、画像MIME Accept、`Accept-Encoding: identity`、`Connection: close` だけを送り、HTTP version・status・header件数とbyte数・framing・Content-Length・Content-Encoding・Transfer-Encodingをfail closedに検証する
- redirect、非200、不許可MIME、圧縮、宣言済み上限超過のbodyを読まず、成功bodyも8 MiBを1 byte超えた時点で固定errorにする。response、TLS socket、raw socketは成功・失敗・close失敗を問わず処理対象にする

TDD・検証記録:

- production module不在を使った初期RED test SHA-256は `7639e1cadd52866f8de809111e5e61d2958bdd3cde92bfa5b6e56e1eae24e2aa`。focusedは終了2で、`ModuleNotFoundError: No module named 'src.search_v2.image_proxy_http'` によりcollectionで失敗した
- 初期実装後は36 passed / 1 failedとなり、`Content-Encoding: identity, gzip` の曖昧な値をtransport errorへしていない不足を確認した。production側の単一token検証を修正し、テストを弱めず解消した
- HTTP/1.1 ALPN固定の補足RED test SHA-256は `99a8d3b7e35dbd43a27f50ad0cf0b5b18ce396f879bc72ed158becd5371d235d`。対象testの失敗を確認してから `set_alpn_protocols(["http/1.1"])` を実装した
- 最終module SHA-256は `3538b1ab0172943987e553ab718f0207dfa1189dfa514fdda920a8ac82959744`、test SHA-256は `99a8d3b7e35dbd43a27f50ad0cf0b5b18ce396f879bc72ed158becd5371d235d`
- focused transportは37 passed、proxy coreとの関連回帰は83 passed、全v2回帰は535 passed
- `uv lock --check --offline` は72 packages、Ruff check・formatは163 filesで成功し、`uv run --frozen --offline --no-sync pytest -m 'not live_api'` は1267 passed / 1 deselected、`git diff --check` は成功した
- 現行Markdown 16件のlocal link 811件・heading 1101件・fence 195組、Python 3.10 AST 163件、`AGENTS.md` 目次15件を確認した

このマイルストーンではsocket、TLS context、HTTPResponseをfixtureへ置換し、通常pytestのnetwork guardを解除していない。実DNS、実TCP/TLS/HTTP、実URL、実画像、実利用者データ、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、現行pipeline、認証、API、browser、外部委託中のフロントエンドを実行・確認・接続していない。`docs/FRONTEND.md` と `docs/HARNESS-RUNBOOK.md` も本マイルストーンでは変更していない。次の通常ローカル作業は新しい `EXEC-022` を作成し、TCP用IPv4・IPv6だけを有界に返すserver-side DNS resolverを外部通信なしでTDDする。

## 34. 2026-09-03: server-side画像DNS resolver

この項目は、TASK-008第20マイルストーンとして、canonicalな商品画像hostを1回だけ名前解決し、TCP接続用のIPv4・IPv6だけを最大8件の有界結果として既存image proxy coreへ渡すadapterを追加した未コミット変更を記録する。詳細は [EXEC-022](GOAL.md#exec-022-server-side画像dns-resolver) を参照する。

- `image_proxy_dns.py` に `BoundedImageDnsResolver` と固定messageの `ImageProxyDnsError` を追加した。小文字ASCIIで2 label以上のcanonical DNS hostだけを受け、IP literal、末尾dot、port・path付き、非ASCII、過長hostをresolver前に拒否する
- `getaddrinfo` はhost、443番、`AF_UNSPEC`、`SOCK_STREAM`、`IPPROTO_TCP`、`AI_NUMERICSERV` で1回だけ呼ぶ。retry、別resolver、HTTP client、cache、環境proxyを持たない
- 戻り値は組込みlist 1〜8件とexact 5-tupleに限定し、IPv4・IPv6 family、TCP socket type・protocol、空canonical name、familyごとのsockaddr長、443番、IPv6 flowinfo・scope ID 0、canonical numeric addressを検証する
- resolverは順序と重複を維持する。全addressのglobal判定、private等を1件でも含む場合の全体拒否、重複除去、transport呼出しは既存 `image_proxy.py` の責務として維持した
- host、address、raw resolver tuple、OS例外を固定例外文へ含めず、default resolverを呼ぶ時点で通常pytestのnetwork guardが有効であることも確認した

TDD・検証記録:

- production module不在の初期test SHA-256は `ecfc42ced2aabc889ed89ebcbe8bd07ddb13aee02d63b76da7a15a6ec582eda4`。focusedは終了2でcollection errorになった
- network guard自己検査に空文字の非露出を要求する自己矛盾があったため、そのtestだけを修正した。公開APIだけのscaffoldに対する振る舞いREDは54 failed / 2 passed、test SHA-256は `4c5048835b379e8bb2396a5a86d1d98a27820f3c175ff622b9e4cda7910a50be` だった
- 初期GREEN候補は55 passed / 1 failedで、残りは空文字を例外文に含めないというtest自身の誤りだった。非空hostだけの非露出確認へ修正し、受入条件は弱めていない
- 注入callableが任意messageの `ImageProxyDnsError` を投げる攻撃caseを追加し、1 failed / 56 passedのREDを確認した。低レベルcallableの全例外を固定resolution errorへ包み直した
- 非hashableなfamily・socket type・protocolで集合membershipが `TypeError` を漏らすcaseを追加し、1 failed / 59 passedのREDを確認した。exact type検証を先行させて固定errorへ修正した
- 最終module SHA-256は `c5a9cfccc5b20208cdbf7321cd0ec64f515a2ff18ad0b585cf817957f917dbca`、test SHA-256は `94f9d43b04fb8035c43cc2b572da19e86e0a960af4df7f7a56ce1da450f4b1b0`
- focused resolverは60 passed、proxy core・resolver・transportの関連回帰は143 passed、全v2回帰は595 passed
- `uv lock --check --offline` は72 packages、Ruff check・formatは165 filesで成功し、`uv run --frozen --offline --no-sync pytest -m 'not live_api'` は1327 passed / 1 deselected、実装後と文書同期後の `git diff --check` は成功した
- 現行Markdown 16件のlocal link 820件・heading 1116件・fence 195組、Python 3.10 AST 165件、`AGENTS.md` 目次15件・安全規則を確認した

検証の中心は注入 `getaddrinfo`、transport、合成PNGであり、通常pytestのnetwork guardを解除していない。ただし実装中の型確認で、計画の対象外だった `socket.getaddrinfo("localhost", 443, ...)` をpytest外から1回実行した。出力したのは返却値のPython型だけでaddressは表示していない。外部domain、HTTP、credential、課金は使っていないが、計画逸脱としてここへ残す。

上記以外の外部hostへのDNS、実TCP/TLS/HTTP、実URL、実画像、実利用者データ、Bonsai、Cloudflare、Outscraper、OpenAI、現行pipeline、認証、API、browser、外部委託中のフロントエンド、AIレビューハーネスを実行・確認・接続していない。`docs/FRONTEND.md` と `docs/HARNESS-RUNBOOK.md` も本マイルストーンでは変更していない。次の通常ローカル作業は新しい `EXEC-023` を作成し、既存policy、resolver、transport、proxy coreを合成allowlistで束ねるimage proxy serviceをoffline TDDする。

## 35. 2026-09-03: server-side画像proxy service

この項目は、TASK-008第21マイルストーンとして、起動時の画像host allowlist、既存の有界DNS resolver、pinned-IP HTTPS transport、画像検証coreを一つに固定するserver-side serviceを追加した未コミット変更を記録する。詳細は [EXEC-023](GOAL.md#exec-023-server-side画像proxy-service) を参照する。

- `image_proxy_service.py` に、frozen・slots・repr非表示の `ImageProxyService` と固定messageの `ImageProxyServiceError` を追加した
- constructorは組込みtupleのallowlistを必須にし、既存 `ImageProxyPolicy` で1〜32件、canonicalな小文字ASCII DNS host、重複なしを検証する。設定値と生例外を含めず、全設定不正を `image proxy configuration is invalid` へ変換する
- resolverとtransportを省略した場合は `BoundedImageDnsResolver` と `PinnedHttpsImageTransport` を各1回構築する。注入はconstructorだけに限定し、公開 `fetch_image()` はURL以外のpolicy、allowlist、依存部品、timeout、上限を受け取らない
- 取得は既存 `fetch_proxy_image()` へ1回だけ委譲し、service自身にnetwork client、retry、failover、redirect、cache、画像decoder、credential、logを追加していない。全取得失敗を `image proxy request failed` へ変換する
- 不正・不許可URLはresolver前、private等を含むDNS結果はtransport前、transport・応答・画像不正は既存coreの各検証位置で停止することを、合成allowlist・global IP・PNGと注入fixtureで確認した

TDD・検証記録:

- production module不在の初期RED test SHA-256は `a2f44a4e9af8a8ac40bb2f2fc025f77242a176f117ce0103461c79df27931b93`。focusedは終了2で `ModuleNotFoundError` によりcollectionで失敗した
- 公開APIだけのscaffoldに対する振る舞いREDは29 failed / 2 passedで、constructorの `NotImplementedError` により要求機能が未実装であることを確認した。同じtest SHA-256を維持した
- 最終module SHA-256は `0772279bc0c976846d18d41942ae4c20c568066fb2330b0f6251f4fa2effc593`、test SHA-256は `a2f44a4e9af8a8ac40bb2f2fc025f77242a176f117ce0103461c79df27931b93`
- focused serviceは31 passed、proxy core・resolver・transport・serviceの関連回帰は174 passed、全v2回帰は626 passed
- `uv lock --check --offline` は72 packages、Ruff check・formatは167 filesで成功し、`uv run --frozen --offline --no-sync pytest -m 'not live_api'` は1358 passed / 1 deselectedだった
- 現行Markdown 16件のlocal link 832件・heading 1131件・fence 195組、Python 3.10 AST 167件、`AGENTS.md` 目次15件・安全規則、`git diff --check` を確認した

通常pytestのnetwork guardを解除せず、実domain、実URL、実画像、実DNS・TCP・TLS・HTTP、実利用者データ、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、現行pipeline、認証、API、browser、外部委託中のフロントエンド、AIレビューハーネスを実行・確認・接続していない。`docs/FRONTEND.md` と `docs/HARNESS-RUNBOOK.md` も本マイルストーンでは変更していない。

次の画像工程ではDNSとCLIPの全体deadline・process isolation方式を実行環境へ合わせる必要があるため、[NEXT-STEPS.md](../NEXT-STEPS.md#後で必要になるもの) の4を確認してから新しいExecution Planを作る。実画像取得・品質評価には5〜6も必要である。実provider用の1〜3はまだ不要である。

## 36. 2026-09-03: Windows/WSL向け画像DNS process isolation

この項目は、TASK-008第22マイルストーンとして、商品画像の名前解決をWindows 11 / WSL互換の `spawn` 子processへ要求単位で隔離し、親process側でapplication deadlineと回収を強制する未コミット変更を記録する。詳細は [EXEC-024](GOAL.md#exec-024-windowswsl向け画像dns-process-isolation) を参照する。

利用者から実行環境がWindows 11 / WSL、Intel Core Ultra 9 288Vであると確認できた。DNS境界はGPU・NPUを使わないCPU処理とし、`image_proxy_dns_process.py` に `ProcessIsolatedImageDnsResolver` を追加した。

- constructorではprocess、DNS、socketを開始せず、解決要求ごとに明示的な `multiprocessing.get_context("spawn")`、片方向pipe、daemon子processを各1つだけ作る
- 子process内だけで既存 `BoundedImageDnsResolver` を呼び、親子間は `send_bytes()` と上限付き `recv_bytes()` による最大512 bytesのASCII protocolだけを使う。pickleで任意objectを復元しない
- 親processは準備前から5秒のapplication deadlineを計測し、結果待機へ最大4.5秒、terminate・kill後のjoinへ各最大0.25秒を確保する。`Process.start()` 自体はPythonからpreemptできないため、この5秒はOS起動の絶対上限ではない
- 親側で成功tag、1〜8件のcanonical numeric IPv4・IPv6を再検証し、その後も既存proxy coreで全addressのglobal性を検証する。timeout、異常終了、EOF、IPC不正、cleanup失敗はhost・IP・OS例外を含まない `image DNS process failed` へ変換する
- 親processへ届く `KeyboardInterrupt` 等はresource回収後に再送出し、自動retry、別resolver、別processへのfailover、DNS cacheは追加しない
- `ImageProxyService` の既定resolverをprocess分離版へ変更した。constructor注入、公開 `fetch_image(url)`、既存policy・transport・coreの契約は変更していない

TDD・検証記録:

- production module不在の初期REDは終了2の `ModuleNotFoundError` で、process test SHA-256は `e62cc8f8fdebb8a63eacf3b3e609c0ab7445d1a83c1127c777d7cd3c8616f8d9`、service test SHA-256は `4c7c2bf1ee263f92666316d4dea8be2e246c486d869be21e326349bb5a2660bf` だった
- 公開scaffoldの振る舞いREDは37 failed / 33 passedだった。その後、pickleを使わないbyte IPCは8 failed / 61 passed、cleanup時間確保は3 failed / 66 passed、interrupt伝播は1 failed / 38 passedの補足REDを順に確認した
- 初期GREENでは正常message後の終了待機がcleanup予約を侵食できたため、test SHA-256 `86a7d3630a1e1b7d55550a8332a80cff167c20c3fc2a2952b611a458ef31666e` で1 failed / 69 passedの補足REDを確認し、このjoinも4.5秒側の期限へ揃えた
- 最終module SHA-256は `835bf099ab817c7fc44bd28271b219f6d0122f5f8eace75da5d34a97919122bd`、service module SHA-256は `48933eaeb776938987eec0c51f934e99930c143980d9819dea2d6d4cb66b1dbf`、最終process test SHA-256は `86a7d3630a1e1b7d55550a8332a80cff167c20c3fc2a2952b611a458ef31666e` である
- focused process・serviceは70 passed、proxy関連は213 passed、全v2は665 passed、offline全体は1397 passed / 1 deselectedだった
- `uv lock --check --offline` は72 packages、Ruff checkと169 filesのformat check、現行Markdown 16件のlocal link 845件（うち見出しanchor 484件）・見出し1127件・fence 195組、Python 3.10 AST 169件、`AGENTS.md` 目次15件・安全規則を確認し、すべて終了0だった
- 現行WSL2 kernel `Linux 6.18.33.2-microsoft-standard-WSL2 x86_64` で、外部DNSへ進まない不正hostの子workerを実 `spawn` し、固定 `error` bytes受信と正常終了を1回確認した

主な検証はfake process・pipe・clock、注入 `getaddrinfo`、socket・TLS・HTTPResponse、合成allowlist・PNGによるoffline testである。実DNS、実TCP/TLS/HTTP、実画像host、運用allowlist、Windows native、実CLIP model・encoder、画像ranking品質、実利用者データ、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、現行pipeline、認証、API、browser、外部委託中のフロントエンド、AIレビューハーネスは実行・確認・接続していない。`docs/FRONTEND.md` と `docs/HARNESS-RUNBOOK.md` も本マイルストーンでは変更していない。

次の通常ローカル作業は [NEXT-STEPS.md](../NEXT-STEPS.md#後で必要になるもの) の5〜6を受け取ってから、新しいExecution PlanでCPU優先の実CLIP encoder process isolationと代表画像による品質評価を設計することである。実Bonsai・Cloudflare・Outscraper用の1〜3はまだ不要である。

## 37. 2026-09-03: 固定ONNX CLIP CPU runtimeとprocess isolation

この項目は、TASK-008第23マイルストーンのrepository-local固定ONNX asset、CPU image encoder、Windows 11 / WSL互換の推論process隔離、合成画像による実model疎通、受領1組の最小識別smokeを追加した未コミット変更を記録する。詳細は [EXEC-025](GOAL.md#exec-025-固定onnx-clip-cpu-runtimeと品質smoke) を参照する。

- 利用者指定に従い、固定modelを `models/clip-vit-base-patch32-12b36594/` へ配置した。固定revisionのHTTPS URL 3件だけから一時directoryへ取得し、3通常file、合計605,805,437 bytes、SHA-256を検証してから移した。directoryは0555、各fileは0444、hardlink数は1で、Git追跡・Git LFS・pushは行っていない
- `config.json` は456 bytes・SHA-256 `20a24818e6ce94b8393759112206420496d48c6dcadacd657db33839bdaf823f`、`model.onnx` は605,804,513 bytes・`57879bb1c23cdeb350d23569dd251ed4b740a96d747c529e94a2bb8040ac5d00`、`preprocessor_config.json` は468 bytes・`5df7e578c37e907a431daf47fd592fc49fa50d23ed4c41285a0a34a58a9d2e06` である
- direct dependencyへNumPyとONNX Runtime 1.23.2を追加した。`uv lock` と環境準備ではPyPIからCPU wheelと補助packageを取得したが、credential、API、課金は使っていない。lockは79 packagesで、Python 3.10〜3.13用wheelを持つversionへ固定した
- `image_similarity.py` のmanifestをONNX 3 fileへ移行し、exact entry、通常file、symlink・hardlink、byte数、SHA-256、読込前後のstat identityを検証する。PyTorch、Transformers、pickle weightはdependency・production import・assetへ追加していない
- `image_similarity_onnx.py` は検証済みRGBをBICUBICで短辺224pxへresizeし、224px center crop、`1/255` rescale、固定mean・std、NCHW `float32`へ変換する。最大4枚、中間resize辺4096px、生成tensor約2.4 MBを上限とする
- ONNX sessionはthread数各1、sequential execution、`CPUExecutionProvider` だけに固定した。実graphの3 inputと4 outputのname・type・shapeを照合し、`image_embeds` の件数、512次元、`float32`、有限、非0を検証する。assetはsession作成前と推論後に再hashし、identity差替えを拒否する
- `image_similarity_process.py` は親で前処理したbounded tensor bytesを `spawn` daemon子processへ渡し、子から固定header付きlittle-endian `float32` embeddingまたは固定失敗tagだけを受ける。戻りは最大8,201 bytes、application deadlineは30秒、cleanup予約は2秒、terminate後も生存時はkillする。process・pipeを全経路で閉じ、path、画像byte、生ONNX例外を公開errorへ含めない
- pytestへ `clip_runtime` markerと `--run-clip-runtime` を追加した。通常gateは606 MB modelをloadせずskipし、明示opt-inだけがrepository-local assetを使う。spawn子processとnative codeはpytestのPython network guardでOS-level隔離されないため、model名解決・download・外部clientを持たないlocal-only code pathであることと、OS network遮断の証拠を区別する
- 受領した正例・負例は固定hashの単一frame PNGとして読み、RGBへ変換した。正例自身のembeddingを4方向の代用参照として各候補を採点する明示opt-in testを追加した。これは検索文の意味一致や実際の4方向参照を評価するtestではない

TDD・検証記録:

- manifest移行のREDはtest SHA-256 `f4b30ffbeddcb3a9034a689046e1735a8bed91e200b7aafa566ec9e96dcf7cf4` で旧assetとの差により1 failed、ONNX encoderの初期REDは `d296a8dc58e63fb16fdadb3a69f03beba35b9426805cc2cfbbe43b0fec79d051` でmodule不在のcollection errorだった
- process encoderの初期REDはtest SHA-256 `1342999cf91b42be9b19537aa600d8b98c3d76a26690bd7be16d4fec805e0cda` でmodule不在のcollection errorだった。後続でhardlink、中間resize、asset identity、provider・graph drift、NaN・0 vector、timeout、terminate・kill、interrupt、malformed IPCを追加してGREENにした
- 最終module SHA-256は `image_similarity.py` が `c5215344d9acae377b79302ffc1f78f58058874b1ca65ae9fb395e5a375c1caf`、`image_similarity_onnx.py` が `b21bb891236782cfc7f4c1dfac4038929c3d8aa2689f5025ad13af41ec4548c1`、`image_similarity_process.py` が `8e3c190fc1605c37ea82fa7dc13325832ee6a0b9c565e1296ee9923b0a56a767` である
- 最終test SHA-256は順に `dac54d4952ca98c59d6713d8b9239eb332a2426e0f30a675c0743d5b73032a3d`、`dfe1880c076b376a602b690b842dea8df8a47fba4e12c31bc77bcbfa216899b5`、`1b4ac8498caaf292cac01b51311d7beacad1aef1268a26472c4a92393c077d17` である
- encoder・process focusedは明示opt-inで78 passed、画像関連は289 passed / 2 skipped、全v2は711 passed / 2 skipped、offline全体は1443 passed / 2 skipped / 1 deselectedだった。skipは明示opt-in実model 2件、deselectは `live_api` である
- `--run-clip-runtime` を明示した合成画像1枚のtestはWSL・CPU子processで1 passed、3.39秒だった。active provider、512次元、有限・L2正規化済みembeddingを確認したが、合成1枚の疎通を提示画像の意味品質、Windows native、性能保証として扱わない
- 受領1組を同じCPU子process経路で3回評価し、embeddingがbit-identicalであること、正例score 1.000000000、負例0.940624123、差0.059375877で期待順序になることを確認した。自己参照を含むため、1組の成功を一般的なranking品質として扱わない
- `uv lock --check --offline` は79 packages、Ruff checkと173 filesのformat check、現行Markdown 16件のlocal link 858件（うち見出しanchor 495件）・見出し1142件・fence 195組、Python 3.10 AST 173件、`AGENTS.md` 目次15件、`git diff --check` を確認し、終了0だった

外部接続は固定asset 3件とdependencyの取得時だけに限定した。実Amazon、`m.media-amazon.com`、DNS・TCP・TLS・HTTP、実Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、現行pipeline、認証、API、browser、外部委託中のフロントエンド、AIレビューハーネスは実行・確認・接続していない。`docs/FRONTEND.md` と `docs/HARNESS-RUNBOOK.md` も本マイルストーンでは変更していない。

EXEC-025は受領1組の最小識別smokeまで完了した。1組だけでは画像rankingを有効にせず、model assetと受領画像の配布可否、Windows native、複数query・4方向参照・複数商品を使う代表dataset、事前の採用閾値を後続判断に残す。

## 38. 2026-09-03: 単一検索条件31枚のCLIP characterization

この項目は、TASK-005の最初のlocal画像品質baselineとして、利用者が追加・分類したnear 13枚・far 18枚を自己参照なしで評価した未コミット変更を記録する。詳細は [EXEC-026](GOAL.md#exec-026-単一条件の複数画像clip-characterization) を参照する。

- `tests/img/case1/near/` と `tests/img/case1/far/` の全31枚を目視し、フォルダ分類を利用者の正解labelとして保持した。全fileはRGBA・単一frame PNG、source SHA-256とpixel digestは一意で、pHash距離10以内の組もなかった
- test内へ31件の相対path・label・SHA-256を固定し、未登録・欠損file、symlink・hardlink、形式・frame・寸法・hash不一致、source・pixel重複、pHash距離5以内の近似重複を明示opt-inで拒否する
- scoreを見る前に、当時の辞書順先頭のnear 4枚を固定参照、残るnear 9枚とfar 18枚を候補、pairwise AUC 0.80以上かつnear中央値がfar中央値を上回ることを暫定基準とした。測定後にlabel、参照、基準を変更しなかった。現行の参照IDは同じbyteのn1〜n4である
- 旧2枚は `near/` と `far/` へ移動したため、旧pathのquality testが期待どおり1 failedになるREDを確認してから参照pathを更新した
- 固定4参照と27候補を4枚以下のbatchで同じrepository-local ONNX CPU子processへ通し、productionの `score_clip_image_similarity()` で採点した。near平均0.934439977、far平均0.881724434、near中央値0.940632749、far中央値0.876893229、near範囲0.909637856〜0.950941212、far範囲0.808155344〜0.956266974だった
- 全162組のpairwise AUCは0.790123457で、中央値条件は成功したが事前AUC基準0.80へ未達だった。再実行でも各scoreは記録値の絶対誤差1e-8以内で一致した。固定baselineの再現は成功test、既知の基準未達はstrict xfailへ分離した
- far上位には固定参照と外形・色が近い黒い有線ゲーミングマウスが含まれた。画像embeddingだけで「無線」を十分に区別できないため、商品名・構造化された観測属性を正本にし、画像rankingは無効のままとした
- 新規quality test SHA-256は `8d1d53f375e7fce8d9d0a590bff932bd4ade29e0632e6d30d87eb096efe6af20`、移動後pathへ更新したprocess testは `e59fcde00ee2e2bcdb4df345c7f212d3b95b3caff6083171662f8cf0f2f6c04f` である
- CLIP focusedは80 passed / 1 xfailed、明示runtimeだけでは4 passed / 1 xfailed、画像関連は289 passed / 5 skipped、全v2は711 passed / 5 skipped、offline全体は1443 passed / 5 skipped / 1 deselectedだった。lock 79、Ruff 174 files、現行Markdown 16件のlocal link 874件・anchor 508件・heading 1155件・fence 195組、Python 3.10 AST 174件、AGENTS目次15件、`git diff --check` も成功した

31枚とmodelはlocal未追跡assetのままで、commit、push、再配布を行っていない。実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、委託フロントエンド、AIレビューハーネスは実行・確認・接続していない。far側属性は後続の [EXEC-027](GOAL.md#exec-027-far画像の属性別hard-negative-characterization)、near側目視属性は [EXEC-028](GOAL.md#exec-028-near画像の目視属性characterization) で固定した。商品仕様による独立確認、複数query、検索文から得た実4方向参照、商品順位の本受入基準はTASK-005へ残る。

## 39. 2026-09-03: far画像の属性別hard negative固定

この項目は、利用者が整理したf1〜f18と提示属性を、既存の単一条件CLIP characterizationへ結び付けた未コミット変更を記録する。詳細は [EXEC-027](GOAL.md#exec-027-far画像の属性別hard-negative-characterization) を参照する。

- `tests/img/case1/far/` と `tests/img/case1/near/` は、画像byteを変えずに `f1.png`〜`f18.png` と `n1.png`〜`n13.png` へ整理されていた。31件のSHA-256を旧manifestと照合し、従来のn1〜n4相当を参照、n5〜n13とf1〜f18を候補として維持した
- f1〜f18へ、利用者が提示した色、接続方式、ゲーミング用途、対象種別を固定した。内訳はマウス12枚、マウスソール5枚、マウスバンジー1枚である。f11は提示に「ゲーミング」がないため非ゲーミング、非マウス6枚のマウス向け属性は該当なしとした
- 対象条件との差が接続方式だけのf2・f4・f7・f10は平均0.945551862、ゲーミング用途だけのf11は0.922820165、色だけのf3・f5・f12・f14・f15・f16は平均0.875869567、非マウスのf6・f8・f9・f13・f17・f18は平均0.830395143だった
- 接続方式だけが異なる4枚は全てfar中央値0.876893229を上回った。これは固定CLIP画像embeddingが形状や色の近い有線・無線マウスを十分に分けないという単一条件の観測であり、商品名・構造化された観測属性を接続方式の正本にする。画像rankingは有効化していない
- quality test SHA-256は `2eec3a74453ae6edb5e0cace4cd00aedd07aa84f5bb0b3e7a53a6ad34f95ae5d`、改名後pathへ更新したprocess testは `2bb0c8e195b92b288619c889952247fb81753882afe41010665ffbf105c914b8` である

| コマンド | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| `pytest -q -s tests/test_search_v2_image_similarity_quality.py -m 'not clip_runtime'` | modelを読まない属性manifestと記録score集計を確認する | 2 passed / 3 deselected | far 18 path、属性件数、4つの比較集合と記録score傾向が固定された |
| `pytest -q -s tests/test_search_v2_image_similarity_quality.py --run-clip-runtime` | 改名後も実ONNX scoreが変わらないことを確認する | 4 passed / 1 xfailed | 27 scoreとAUC 0.790123457が一致し、xfailは既知の事前基準未達だけである |
| 4つの画像類似度test fileを `--run-clip-runtime` で実行 | CLIP境界全体を確認する | 82 passed / 1 xfailed | model、process、score、属性baselineを同時に維持した |
| `pytest -q tests/test_search_v2_image*.py` | 画像関連の通常回帰を確認する | 291 passed / 5 skipped | 通常gateはlocal modelを暗黙実行せず、画像関連境界が成功した |
| `pytest -q tests/test_search_v2_*.py` | 次期バックエンド全体への影響を確認する | 713 passed / 5 skipped | 属性fixture追加で他のv2境界を壊していない |
| `pytest -q -m 'not live_api'` | repository全体のoffline回帰を確認する | 1445 passed / 5 skipped / 1 deselected | 実providerを使わない標準testが成功した |
| `uv lock --check --offline`、Ruff check・format check | lockと静的品質を確認する | lock 79 packages、Ruff 174 files、全て成功 | dependency取得や外部通信なしで既存lockとPython形式を維持した |
| 現行Markdown・Python 3.10 AST・AGENTS目次・`git diff --check` | 文書参照、構文、差分形式を確認する | Markdown 16件、local link 890件、anchor 522件、heading 1169件、fence 195組、AST 174件、目次15件、diff成功 | 現行文書のlink・見出し参照とPython 3.10構文に欠落がない |

画像とmodelはlocal未追跡assetのままで、commit、push、再配布を行っていない。実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、委託フロントエンド、AIレビューハーネスは実行・確認・接続していない。同Planではnear側を推測せず、後続の [EXEC-028](GOAL.md#exec-028-near画像の目視属性characterization) で利用者の指示に基づく目視観察として別に固定した。

## 40. 2026-09-03: near画像の目視属性固定

この項目は、利用者の指示によりn1〜n13をlocal画像から確認し、farの利用者指定属性とは別の目視manifestへ固定した未コミット変更を記録する。詳細は [EXEC-028](GOAL.md#exec-028-near画像の目視属性characterization) を参照する。

| ID | 色 | 接続方式 | ゲーミング用途 | 対象種別 | 画像内の判断材料 |
|---|---|---|---|---|---|
| n1 | 黒 | 不明 | 確認 | マウス | 本体へ接続されたケーブルなし、Gロゴ、多ボタン形状 |
| n2 | 黒 | 不明 | 確認 | マウス | 本体へ接続されたケーブルなし、Razerロゴ、RGB発光 |
| n3 | 黒 | 不明 | 確認 | マウス | 本体へ接続されたケーブルなし、Gロゴ、発光部 |
| n4 | 黒 | 不明 | 確認 | マウス | USB受信機とadapter、多ボタン形状 |
| n5 | 黒 | 不明 | 不明 | マウス | 本体へ接続されたケーブルなし。用途を確定できる表示は見えない |
| n6 | 黒 | 不明 | 不明 | マウス | USB受信機とUSB-C adapter。用途を確定できる表示は見えない |
| n7 | 黒 | 不明 | 確認 | マウス | 本体へ接続されたケーブルなし、Gロゴ、状態灯 |
| n8 | 黒 | 不明 | 確認 | マウス | 充電dock、Razerロゴ、多ボタン形状 |
| n9 | 黒 | 不明 | 確認 | マウス | 本体へ接続されたケーブルなし、`SUPERLIGHT` 表示 |
| n10 | 黒 | 不明 | 確認 | マウス | 本体へ接続されたケーブルなし、Razerロゴ、多数の側面ボタン |
| n11 | 黒 | 不明 | 確認 | マウス | USB受信機とadapter、Razerロゴ |
| n12 | 黒 | 不明 | 確認 | マウス | 本体へ接続されたケーブルなし、RGB発光、軽量開口形状 |
| n13 | 黒 | 不明 | 確認 | マウス | 本体へ接続されたケーブルなし、RGB発光、蜂の巣状開口 |

n5・n6の用途は画像だけでは確定できないため、`is_gaming=None` とした。他11枚は目視できるロゴ、発光、多ボタン、製品表示、軽量開口形状を根拠に `True` とした。接続方式は、ケーブル非接続、受信機、充電dockの写り込みだけでは確定できないため、2026-09-04に全13枚を `connection=None` へ訂正した。この分類は外観の目視結果であり、商品ページ、型番、一次仕様による確認ではない。

候補n5〜n13の記録scoreでは、用途未知のn5・n6が平均0.941389590、用途を目視確認できたn7〜n13が平均0.932454373だった。scoreの高い未知画像をゲーミング用途へ補完せず、商品名・構造化された観測属性が得られるまで未知を維持する。画像rankingは有効化していない。

EXEC-028完了時のquality test SHA-256は `2c7846a41376b42bcbb4f93940bd1ba28cad4673460868aec0a8228715cb741d` である。接続方式訂正後のtest SHA-256はEXEC-030で記録する。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| local viewerでn1〜n13を原寸表示 | 画像から確認できる属性と未知を分ける | 13枚を個別確認 | 全て黒いマウスと判断した。接続方式は後続の責務分離で全て未知へ訂正し、n5・n6の用途も未知とした |
| `pytest -q -s tests/test_search_v2_image_similarity_quality.py -m 'not clip_runtime'` | modelを読まないnear・far属性manifestと記録score集計を確認する | 4 passed / 3 deselected | near 13 path、用途unknown 2枚、score集合が固定された |
| `pytest -q -s tests/test_search_v2_image_similarity_quality.py --run-clip-runtime` | 実ONNX scoreが変わらないことを確認する | 6 passed / 1 xfailed | 27 scoreとAUC 0.790123457が一致し、xfailは既知の事前基準未達だけである |
| 4つの画像類似度test fileを `--run-clip-runtime` で実行 | CLIP境界全体を確認する | 84 passed / 1 xfailed | model、process、score、near・far属性baselineを同時に維持した |
| `pytest -q tests/test_search_v2_image*.py` | 画像関連の通常回帰を確認する | 293 passed / 5 skipped | 通常gateはlocal modelを暗黙実行せず、画像関連境界が成功した |
| `pytest -q tests/test_search_v2_*.py` | 次期バックエンド全体への影響を確認する | 715 passed / 5 skipped | 目視manifest追加で他のv2境界を壊していない |
| `pytest -q -m 'not live_api'` | repository全体のoffline回帰を確認する | 1447 passed / 5 skipped / 1 deselected | 実providerを使わない標準testが成功した |
| `uv lock --check --offline`、Ruff check・format check | lockと静的品質を確認する | lock 79 packages、Ruff 174 files、全て成功 | dependency取得や外部通信なしで既存lockとPython形式を維持した |
| 現行Markdown・Python 3.10 AST・AGENTS目次・`git diff --check` | 文書参照、構文、差分形式を確認する | Markdown 16件、local link 907件、anchor 537件、heading 1183件、fence 195組、AST 174件、目次15件、diff成功 | 現行文書のlink・見出し参照とPython 3.10構文に欠落がない |

画像とmodelはlocal未追跡assetのままで、commit、push、再配布を行っていない。商品ページ、画像検索、実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、委託フロントエンド、AIレビューハーネスは実行・確認・接続していない。次のTASK-005作業は別条件の代表datasetと本合格基準を事前に固定してから行う。

## 41. 2026-09-04: 高評価レビュー件数を使うranking v3

この項目は、利用者の指示により次期検索の通常ランキングへreview qualityを追加した未コミット変更を記録する。詳細は [EXEC-029](GOAL.md#exec-029-高評価レビュー件数を使うranking-v3) を参照する。

- `RankingProfile`、`RankedProduct`、`RankedProductBatch` とdomain separatorをv3へ更新し、重み変更を旧v2の同一契約として扱わないようにした
- base weightをtitle 0.35、attributes 0.30、price 0.20、disabled image 0.10、review quality 0.05とし、review qualityを唯一の最小値にした
- 現行の正規化候補で観測できる平均ratingと総review countだけを使い、平均4.0以上では `(rating / 5.0) * min(1, log1p(count) / log1p(1000))`、4.0未満または0件では0.0とする決定的な補助scoreを追加した
- ratingまたはreview countの片方が未観測ならmissingとし、既存どおり利用可能なcomponentだけを1.0へ再正規化する。星別件数、レビュー本文、verified purchase、sentimentは取得・推測していない
- pipelineの既定profileとoffline fixtureをv3へ同期した。legacy `run_product_search()`、Streamlit、CLI、履歴表示schema、画像scoreは変更していない

RED test SHA-256は `eb86c9bfe63c920b9d46ab5e97bad96e954bd019effd6ad8608b26008f9b2b38` である。未実装の `RANKING_PROFILE_V3` importにより収集時1 errorを確認した。最終ranking module SHA-256は `c71bee9ea55e1357986a6e78aea81d04b0db3dc6d949ababbcbed00955c815cf`、pipeline module SHA-256は `6ec4cdc421b92fa63b64af8c15077d31e08a071980ac7ab6906648a1203412f0`、最終ranking test SHA-256は `fc4d745e2970a6503619960cdf21eb954ffd9dfcb580110f7d72ed96357403d0` である。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| ranking focused test | profile、式、欠損、飽和、順位、v2拒否、digestを確認する | 26 passed | rating・review countの決定的な補助評価とv3契約が成功した |
| 主要結合7 test file | pipeline、履歴変換、orchestration、承認、state、requestへの影響を確認する | 107 passed | v3 profile bindingを主要なoffline結合で維持した |
| `pytest -q tests/test_search_v2_*.py` | 次期バックエンド全体への影響を確認する | 724 passed / 5 skipped | 他のv2 package境界を壊していない。skipは明示opt-inのlocal CLIP runtimeである |
| `pytest -q -m 'not live_api'` | repository全体のoffline回帰を確認する | 1456 passed / 5 skipped / 1 deselected | 実providerを使わない標準testが成功した |
| `uv lock --check --offline`、Ruff check・format check | lockと静的品質を確認する | lock 79 packages、Ruff 174 files、全て成功 | dependency取得や外部通信なしで既存lockとPython形式を維持した |
| 現行Markdown・Python 3.10 AST・AGENTS目次・`git diff --check` | 文書参照、構文、差分形式を確認する | Markdown 16件、local link 913件、anchor 542件、heading 1196件、fence 195組、AST 174件、目次15件、diff成功 | 現行文書のlink・見出し参照とPython 3.10構文に欠落がない |

実Amazon、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、実商品候補、実ランキング品質、browser、委託フロントエンド、AIレビューハーネスは実行・確認・接続していない。0.05、平均4.0閾値、1,000件飽和は固定計算契約であり、代表queryの期待順位による最適化結果ではない。次のTASK-005作業はrating・review countの有無も含む複数条件の固定評価setを事前定義してから行う。

## 42. 2026-09-04: 画像ランキングの視覚的特徴限定

この項目は、利用者の指示により画像ランキングを視覚的特徴だけの補助評価へ限定し、有線・無線を商品名と構造化された観測属性へ分離した未コミット変更を記録する。詳細は [EXEC-030](GOAL.md#exec-030-画像ランキングの視覚的特徴限定) を参照する。

- 画像scoreは色、外観形状、商品種別など画像で確認できる近さだけを表し、構造化属性の推定、補完、上書きまたはhard filterへ使わない方針を固定した
- 有線・無線は商品名またはproviderから得た構造化された観測属性で判定する。観測できない場合は、画像が近くても未知のまま扱う
- near 13枚の接続方式を暫定目視値の無線から全て未知へ訂正した。far側の接続方式は利用者提示labelなので、画像観察とは分けて構造化評価にだけ使う
- 元のnear候補9枚・far 18枚によるAUC 0.790123457とstrict xfailは、事前評価の履歴として変更していない
- 接続方式だけが異なるf2・f4・f7・f10を画像上の正例へ再分類した。正例13枚・負例14枚の全182組中175組が正順で、AUC 0.961538462、正例中央値0.942146431、負例中央値0.843137443を固定scoreから再現した
- この再計算は単一条件の画像score責務を確認するcharacterizationであり、複数query、検索文から生成した4方向参照、総合商品順位の品質または画像ranking有効化を証明しない

quality test SHA-256は `c44318873d3e6ffc36954fd9f74625d3c779e506ccf1917ade138f585a3881a8` である。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| near接続方式を未知と要求するfocused testをmanifest修正前に実行 | 以前の目視推定が残ることを確認する | 1 failed / 4 passed / 3 deselected | `wireless` と期待する `None` の不一致だけで失敗し、訂正対象を特定した |
| `pytest -q tests/test_search_v2_image_similarity_quality.py` | 固定scoreの属性manifestと接続方式非依存評価をmodel読込なしで確認する | 5 passed / 3 skipped | 新しいAUC・中央値と元baseline不変を通常offline testで再現した |
| `pytest -q -s tests/test_search_v2_image_similarity_quality.py --run-clip-runtime` | 固定ONNX再推論でも記録scoreと両評価が一致することを確認する | 7 passed / 1 xfailed | 接続方式非依存AUC 0.961538462が成功し、xfailは元のAUC 0.790123457による既知の未達だけである |
| `pytest -m 'not live_api'` | repository全体のoffline回帰を確認する | 1457 passed / 5 skipped / 1 deselected | 実providerを使わない標準testが成功した |
| `uv lock --check --offline`、Ruff check・format check、`git diff --check` | lock、静的品質、差分形式を確認する | lock 79 packages、Ruff 174 files、差分検査を含め全て成功 | dependency取得や外部通信なしで既存境界を維持した |
| 現行Markdown・Python 3.10 AST・AGENTS目次 | 文書参照、見出し参照、構文、目次を確認する | Markdown 16件、local link 932件、anchor 559件、heading 1210件、fence 195組、AST 174件、目次15件、全て成功 | 現行正本の参照と構文に欠落がない |

画像rankingは無効のままで、ranking-v3、weight、profile digest、現行pipeline、Streamlit、CLI、APIを変更していない。実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネスは実行・確認・接続していない。

## 43. 2026-09-04: Markdownリンク検査の定型化

この項目は、TODO-001として残っていた一時的なMarkdown検査を、通常offline pytestからも実行される再利用可能なCLIへ置き換えた未コミット変更を記録する。

- `tools/check_markdown_links.py` を追加し、repository root直下の `*.md` と `docs/*.md` を決定的に列挙する
- local path、参照先MarkdownのATX見出しanchor、重複見出しsuffix、fenced code blockの開閉を標準libraryだけで確認する
- 外部schemeのURLへは接続せず、`docs/old/` は履歴のため検査元から除外する。現行文書からarchiveを参照する場合は、そのtarget pathを存在確認する
- sourceまたはtargetがrepository root外へ出るpath、欠落target、欠落anchor、非Markdownへのanchor、閉じていないfenceを終了1にする
- `tests/test_markdown_links.py` は現行repository自体の検査に加え、正常path、重複anchor、外部URL・code fence・archive sourceの除外、欠落path、欠落anchorを一時directoryで固定する

RED test SHA-256と最終test SHA-256は同じ `e3004dbffb90d2025068f325560c6c55c5b9902c864fbc97c9fc56bfe1cb7e7f`、最終tool SHA-256は `fa6a9475a2e1a261fd0aa9f2dc8e3538896e44a6eb0928c0f0e8cece78975b3f` である。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| `pytest -q tests/test_markdown_links.py`（実装前） | 期待する検査契約を先に固定する | collection 1 error | `tools.check_markdown_links` が存在しない期待理由でREDになった |
| `pytest -q tests/test_markdown_links.py`（実装後） | 同じtestを最小実装で満たす | 4 passed | 正常な相対linkとanchorは成功し、欠落targetとanchorは失敗する |
| `python tools/check_markdown_links.py` | 現行文書へCLIを適用する | Markdown 16件、local link 932件、anchor 559件、heading 1211件、fence 195組、終了0 | 外部通信なしで現行文書のpath・anchor・fence整合を再現できる |
| `pytest -m 'not live_api'` | repository全体のoffline回帰を確認する | 1461 passed / 5 skipped / 1 deselected | 新しいrepository自己検査を含む標準testが成功した |
| `uv lock --check --offline`、Ruff check・format check | lockと静的品質を確認する | lock 79 packages、Ruff 176 files、全て成功 | 新規toolとtestを既存依存だけで維持できる |

外部URL、実Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、委託フロントエンド、AIレビューハーネスは実行・確認・接続していない。GitHub Actions上の実行も確認していない。

## 44. 2026-09-04: 未参照設定placeholderの削除

この項目は、TODO-005として残っていた `APP_ENV` と `LOG_LEVEL` の扱いを確定し、設定契約、サンプル、制約文書を同期した未コミット変更を記録する。

- repository全体の参照を確認し、両項目が `Settings` と `.env.example` にだけ存在して実行処理へ接続されていないことを確認した。AIレビューハーネス内の同名でないdeployment結果fieldは別契約のため変更していない
- 動作のない設定を将来用placeholderとして維持せず、`src/config.py` と `.env.example` から削除した
- `Settings` の未知項目無視を互換境界とし、旧 `.env` またはprocess環境に両変数が残っていても、既知の `SEARCH_RESULT_DISPLAY_LIMIT` を含む設定ロードを妨げないことをtestへ固定した。同名値は環境切替やログレベル制御には使われない
- logging、相関ID、メトリクス、出力のマスキングは実装していない。必要な型付き設定は [TD-004](ISSUES.md#td-004-観測可能性とログ管理) の実装時に処理と同時に追加する

RED時と最終のtest SHA-256は同じ `3b69966f246b971bd86aa0e276e6ebf2580c711e7dcd21afbea49e92dd58df09`、最終 `src/config.py` SHA-256は `f08f7816bfe50e1eb89542416c5217f74233bab6cd8a3c8bc1615c9e1c82b7f1`、最終 `.env.example` SHA-256は `0d56b885465a76a96d3e484fcff1ef08a47efb86b09b6ad218849d20ae585078` である。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| 新しい設定load testを削除前に実行 | 採用した削除・互換契約を先に固定する | 1 failed / 30 deselected | `app_env` が公開fieldに残る期待理由だけでREDになった |
| `pytest -q tests/test_outscraper_client.py -k settings` | 削除後の旧環境値と既存設定のload・validationを確認する | 9 passed / 22 deselected | 旧2変数を無視しつつ既知UI設定を読み、既存の数値・weight制約も維持した |
| `pytest -m 'not live_api'` | repository全体のoffline回帰を確認する | 1462 passed / 5 skipped / 1 deselected | 実providerを使わない標準testが成功した |
| `uv lock --check --offline`、Ruff check・format check、Python 3.10 AST | lock、静的品質、対応構文を確認する | lock 79 packages、Ruff 176 files、AST 176 files、全て成功 | 依存取得や実service通信なしで設定契約を更新できた |
| 現行Markdown検査、`git diff --check` | 正本文書の参照と差分形式を確認する | Markdown 16件、local link 935件、anchor 562件、heading 1212件、fence 195組、diff成功 | コード、設定例、要件、設計、負債、作業状態を同じ判断へ同期した |

実Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、委託フロントエンド、AIレビューハーネスは実行・確認・接続していない。ログレベル切替や観測可能性が実装済みになったことも意味しない。

## 45. 2026-09-04: case2固定候補と自己参照除外CLIP診断

この項目は、利用者が `tests/img/case2/` に追加した2例目を固定候補へ転記し、独立参照がない境界を隠さずにCLIPとreview qualityを診断した未コミット変更を記録する。詳細は [EXEC-031](GOAL.md#exec-031-case2固定候補と自己参照除外clip診断) を参照する。

- 必須特徴「筒状、長い、縦、金属製、収納」、追加特徴「四角い、黒い」、near 4枚・far 7枚の視覚的特徴、構造化特徴、期待順位、rating、review countを固定manifestへ結び付けた
- `case2.xlsx` はmacro・外部linkを含まない一方で作成者・更新者metadataを持つため、個人metadataを出力・転記せず、必要値だけをtestへ固定した。testはExcelをruntime fixtureとして参照しない
- case2画像11枚は単一frame PNGで、source SHA-256、pixel digest、pHashが重複しないことを確認した
- near 4枚は候補であって独立した正面・左・右・背面参照ではない。near候補は自分以外のnear 3枚、far候補はnear 4枚との平均scoreだけを限定診断し、productionの4方向評価とは区別した
- repository-local固定ONNXによる診断はpairwise AUC 0.392857143、利用者の期待順位とのpairwise concordance 21/53だった。観測値を成功testへ固定したが、品質合格または画像ranking有効化とは扱わない
- 視覚・構造化特徴が同じ `n4` と `f4`、`f1` と `f2` では、最小weightのreview qualityが利用者の期待順を支えた
- 利用者によるdataset再配置に合わせ、case1既存testを `tests/img/case1/` へ更新した。画像byteと固定hashは変更していない

case2 test SHA-256は `bf1894e9a30a46796dc8156838c1e7a899303c0cea2c38c53b4711e9734f0217`、case1 quality testは `e5deea9629a95fe7b2d037ef2206c5d84ddd73121f70a19b904c1a2bdb22c3fd`、process testは `a530c5a9502f0c106e9e37b027ce2bda0a0962ea5da87ff52a3455c52fd3f16d`、ranking testは `b8237d3a5b43b2516e0ef07e0fee1437058a2e0b2fa13cfa6c22aada20780690` である。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| case1既存quality testをpath修正前に実行 | 利用者によるcase別再配置を再現する | 1 failed / 7 deselected | 旧loaderが `tests/img/` 直下に `near`・`far` だけを期待し、case1・case2 directoryを拒否する期待理由でREDになった |
| case1・case2の通常quality test | model読込なしでmanifest、固定診断値、disabled境界を確認する | 7 passed / 5 skipped | case2入力と限定診断を通常offline testで再現し、skipは明示opt-inの固定ONNX実行だけである |
| case1・case2の `--run-clip-runtime` | repository-local固定ONNXで記録scoreを再計算する | 11 passed / 1 xfailed | case2全scoreが一致し、xfailはcase1の既知のAUC 0.790123457だけである |
| case1実process smoke | path移動後もWindows/WSL互換 `spawn` 経路を確認する | 2 passed / 23 deselected | case1再配置後もlocal ONNX process境界を維持した |
| case2 review quality test | 同一特徴候補の補助tie-breakを確認する | 2 passed / 30 deselected | 2組とも期待順となり、画像や構造化適合が同じ場合の補助評価を再現した |
| globをliteral引数として渡した初回v2個別実行 | 次期backend全体の回帰を確認する | exit 4、file not found、test 0件 | 検証ラッパーの引用誤りであり、codeまたはtestの失敗ではない。globをshell展開する正規コマンドで再実行した |
| `pytest -q tests/test_search_v2_*.py` | 次期backend全体のoffline回帰を確認する | 729 passed / 7 skipped | 訂正したコマンドでは全v2境界が成功し、skipは明示opt-inの固定ONNX実行だけである |
| `pytest -q -m 'not live_api'` | repository全体のoffline回帰を確認する | 1466 passed / 7 skipped / 1 deselected | 実providerを使わない標準testが成功した |
| lock、Ruff check・format check、Python 3.10 AST | lockと静的品質を確認する | lock 79 packages、Ruff 177 files、AST 177 files、全て成功 | dependency取得や外部通信なしで既存lockと対応構文を維持した |
| 現行Markdown、AGENTS目次、`git diff --check` | 文書参照、構造、差分形式を確認する | Markdown focused 4 passed、16 files・local link 943件・anchor 567件・heading 1226件・fence 195組、目次15件、diff成功 | 現行正本の参照と差分形式に欠落がない |

画像ranking、production code、ranking profile、weight、model asset、現行pipelineは変更していない。実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・接続していない。次はcase3と、case2・case3の候補とは別の4方向参照を受領してから本評価を行う。

## 46. 2026-09-04: 全体保持・モデル平均余白CLIP前処理

この項目は、利用者が採用した「画像全体を余白付きで収める」方式を固定CLIP入力へ実装し、case1・case2を再characterizationしてcase3の受領待ちへ進めた未コミット変更を記録する。詳細は [EXEC-032](GOAL.md#exec-032-全体保持clip前処理とcase3準備) を参照する。

- center crop、全体保持＋モデル平均余白、全体保持＋白余白、全体保持＋画像端余白、224×224への直接変形、center/full score併用を同じcase1・case2でread-only比較した。モデル平均余白はcase2をAUC 0.392857143から0.642857143、期待順位一致を21/53から27/53へ改善した一方、case1 AUCを0.790123457から0.759259259、接続方式を除く視覚評価AUCを0.961538462から0.928571429へ低下させた。利用者はこのtrade-offを確認して全体保持方式を採用した
- `image_similarity_onnx.py` はRGB画像の縦横比を維持し、長辺を224pxへ合わせて全体を224×224内の中央へ配置する。残りはCLIP image meanで埋めるため、固定mean・stdによる正規化後の余白は全channelで0となる。BICUBIC、NCHW `float32`、最大4枚、CPU-only ONNX、30秒process isolationは維持した
- application前処理profileを `clip-rgb-bicubic-contain-mean-pad-224-v1` とし、固定asset manifestとともにruntime digest `bf5e3355bf11e924fdff2f8703e7a5331d7fd94b06f8fcde32c6083b34bddd05` へ結び付けた。旧center-crop embeddingとの混在を拒否し、固定ONNX 3 assetとupstream `preprocessor_config.json` のbyteは変更していない
- case1はnear/far AUC 0.759259259、接続方式を除く視覚評価は全182組中169組が正順でAUC 0.928571429、正例中央値0.941192911、負例中央値0.874694884となった。事前基準0.80未達はstrict xfailのままであり、属性をscoreから補完しない
- case2の自己参照除外cluster診断はAUC 0.642857143、期待順位一致27/53となった。候補とは独立した4方向参照がない限定診断であり、画像rankingの採用根拠にはしない
- `tests/img/` にはcase1・case2だけがあり、case3 directoryは存在しない。case3の画像、視覚・構造化特徴、期待順位、rating、review count、候補とは独立した正面・左・右・背面参照を既存caseから推測せず、受領待ちとした

RED時と最終の `tests/test_search_v2_image_similarity.py` SHA-256は同じ `2c76b064d9a23ea5d501f7b98a09396a779e1cdf7660d0aa5f95f48560ba7ada`、`tests/test_search_v2_image_similarity_onnx.py` は同じ `edf39b2545f93ceb1d07ded87550ac206ed1303ad2beda72736009b113a56d4a` である。最終 `image_similarity.py` は `aeb0fc7cb9a768dfdf699b9b89af74f102ab7312c6767fa8d9cabfb948f3358d`、`image_similarity_onnx.py` は `a5b71863ab5c89955af0f150737120591e0189148f00ec38ff49afe27bad78da`、case1 quality testは `f7bcfb984fd7fc402e22ec6ba6349b2f55356ee3502c1a738556f88322f6b756`、case2 quality testは `53792e2aa0e3db552a72547f04610527a3b71c6cb2648319f5b6a5d4309b14be` である。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| 前処理方式のread-only比較 | 実装前にcase1・case2のtrade-offを確認する | center cropはcase1 0.790123457・視覚評価0.961538462・case2 0.392857143・21/53、モデル平均余白は0.759259259・0.928571429・0.642857143・27/53 | 全体保持はcase2を改善するがcase1を低下させるため、単一指標による全面的改善ではない |
| focused test（実装前） | 全体保持、中央配置、0余白、profile bindingを先に固定する | 3 failed / 4 passed / 47 deselected | profile定数と全体保持size関数の不存在、極端な縦横比の旧拒否という期待理由だけでREDになった |
| focused test（実装後） | 同じ契約を最小実装で満たす | 7 passed / 47 deselected | landscape・portrait・極端な縦横比、0余白、runtime digest更新を再現できる |
| case1・case2の通常quality test | model読込なしでmanifest、固定score、disabled境界を確認する | 7 passed / 5 skipped | 新profileの固定指標を通常offline testで再現し、skipは明示opt-inの固定ONNX実行だけである |
| case1・case2の `--run-clip-runtime` | repository-local固定ONNXで記録scoreを再計算する | 11 passed / 1 xfailed | 両caseの全scoreと指標が一致し、xfailはcase1 AUC 0.759259259による既知の基準未達だけである |
| image similarity coreの `--run-clip-runtime` | 親前処理、CPU encoder、子process境界をまとめて確認する | 79 passed | 全体保持tensorと既存process isolation・runtime契約が両立する |
| `pytest -q tests/test_search_v2_*.py` | 次期backend全体のoffline回帰を確認する | 730 passed / 7 skipped | 全v2境界が成功し、skipは明示opt-inの固定ONNX実行だけである |
| `pytest -q -m 'not live_api'` | repository全体のoffline回帰を確認する | 1467 passed / 7 skipped / 1 deselected | 実providerを使わない標準testが成功した |
| lock、Ruff check・format check、Python 3.10 AST | lockと静的品質を確認する | lock 79 packages、Ruff 177 files、AST 177 files、全て成功 | dependency取得や外部通信なしで既存lockと対応構文を維持した |
| 現行Markdown、AGENTS目次、`git diff --check` | 文書参照、構造、差分形式を確認する | Markdown focused 4 passed、16 files・local link 955件・anchor 577件・heading 1240件・fence 195組、目次15件、diff成功 | 現行正本の参照と差分形式に欠落がない |

画像component、ranking profile、weight、model asset、現行pipelineは変更せず、画像rankingはdisabledのまま維持した。実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・接続していない。次はcase3と、case2・case3の候補とは独立した4方向参照を受領してから本評価を行う。

## 47. 2026-09-04: case3固定候補と自己参照除外CLIP診断

この項目は、利用者が `tests/img/case3/` に提出した第3条件を固定入力へ転記し、候補と独立した4方向参照がない境界を明示したうえでCLIPを診断した未コミット変更を記録する。詳細は [EXEC-033](GOAL.md#exec-033-case3固定候補と自己参照除外clip診断) を参照する。

- `case3.xlsx` はread-onlyで構造だけを確認した。1 sheet・A1:G22、数式0件、hyperlink 0件、結合cell 0件、macro・外部linkなしで、作成者・更新者metadataが存在した。値は出力・転記せず、testはworkbookをruntimeで読まない
- near 8枚・far 12枚を相対pathと固定SHA-256へ結び、利用者提出の視覚特徴「収納口2つ・縦・収納」、構造化特徴「小型（卓上）」、期待順位、rating、review countを固定した。rating 0・review count 0は欠損と推測せず提出値のまま保持した
- 20枚を個別表示し、全て収納用品で、開口・仕切りと縦横形状の大分類が提出表と矛盾しないことを確認した。一部は2個を超える仕切りまたは開口に見えるため、厳密な「収納口2つ」は利用者提出labelであり、画像による商品仕様の独立検証とは扱わない
- 全20枚は単一frame PNGで、source SHA-256とpixel digestが全て異なり、pHash距離5以下の重複はなかった。画像byteと元Excelは複製・変更していない
- case3専用の独立参照は0枚である。near候補は自分以外のnear 7枚、far候補はnear 8枚との平均cosineだけを使う自己参照除外cluster診断に限定し、productionの4-reference scoreと区別した
- 固定ONNX scoreはnear平均0.858911962、far平均0.858491016、near中央値0.861306486、far中央値0.863038093だった。near/far全96組中45組だけが正順で、tie 0、AUC 0.468750000となった。期待順位が異なる173組中80組が正順で、concordance 0.462427746だった
- farのf1・f2が全候補の上位2件となった。両画像はnear群と同じ収納箱・引き出し系の広い外観特徴を共有し、提出label上は「縦」だけを欠く。この観察は低い分離性能の説明候補であり、CLIP内部の因果や商品仕様を証明するものではない
- case3 quality test SHA-256は `8cc5143e33bb00dd039e3513c1931ee9bcd6e0ba00e1c44dd67c397258f74c23` である

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| workbook構造検査と20画像の個別表示 | 個人metadataを転記せず、入力構造・大分類・重複有無を確認する | 1 sheet・A1:G22、数式・hyperlink・macro・外部linkなし、20枚は単一frame PNG・source/pixel一意・pHash閾値内重複0件 | workbookをfixture化せず、提出値とlocal画像だけを固定できる。厳密な商品仕様や画像権利は確認できない |
| case3通常quality test | model読込なしでmanifest、属性、期待順位、固定診断値、画像ranking disabledを確認する | 2 passed / 2 skipped | skipは明示opt-inの固定ONNX実行だけで、通常gateでもcase3契約を再現できる |
| case3の `--run-clip-runtime` | repository-local固定ONNXで全20 scoreと指標を初回測定後に再現する | 4 passed | 全score、AUC 0.468750000、期待順位一致80/173が絶対誤差1e-8以内で一致した |
| case1からcase3の通常quality test | 3条件の固定入力と診断値を同時確認する | 9 passed / 7 skipped | case3追加後もcase1・case2の固定値とdisabled境界を維持した |
| case1からcase3の `--run-clip-runtime` | 3条件をrepository-local固定ONNXで再計測する | 15 passed / 1 xfailed | case1からcase3のscoreが一致し、xfailはcase1 AUC 0.759259259による既知の基準未達だけである |
| `pytest -q tests/test_search_v2_*.py` | 次期backend全体のoffline回帰を確認する | 732 passed / 9 skipped | 全v2境界が成功し、skipは明示opt-inの固定ONNX実行だけである |
| `pytest -q -m 'not live_api'` | repository全体のoffline回帰を確認する | 1469 passed / 9 skipped / 1 deselected | 実providerを使わない標準testが成功した |
| lock、Ruff check・format check | lockと静的品質を確認する | lock 79 packages、Ruff 178 files、全て成功 | dependency取得や外部通信なしで既存lockとPython形式を維持した |
| 現行Markdown、Python 3.10 AST、AGENTS目次、`git diff --check` | 文書参照、構文、構造、差分形式を確認する | Markdown focused 4 passed、16 files・local link 969件・anchor 589件・heading 1254件・fence 195組、AST 178 files、目次15件、diff成功 | 現行正本の参照、対応構文、目次、差分形式に欠落がない |

画像component、production code、ranking profile、weight、model asset、現行pipelineは変更せず、画像rankingはdisabledのまま維持した。実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・接続していない。次はcase2・case3それぞれについて、候補とは別の正面・左・右・背面参照を受領してから複数queryの本評価を行う。

## 48. 2026-09-04: 型付き条件と証拠別ランキングの設計

この項目は、case3で固定CLIPの広い外観scoreだけでは「収納口2つ」「縦」等を分離できなかった結果を受け、商品カテゴリをまたいで拡張できる型付き条件と、生成画像・商品情報・商品画像の責務を分けた次期rankingを文書設計した未コミット変更を記録する。詳細は [EXEC-034](GOAL.md#exec-034-型付き条件と証拠別ランキングの設計) と [BACKEND.md](BACKEND.md#14-型付き条件と証拠別ランキング最小domainを一部実装) を参照する。

- 条件はnamespace付きattribute key、`boolean`・`enum`・`integer`・`decimal`・`text_set`・`semantic` の値型、型が許可する演算子、typed expected value、`required`・`preferred`・`excluded` へ分ける
- attributeの型、単位、alias、証拠source、evaluator ID・version、既定weightはrepository内のtrusted registryで固定し、Bonsai応答や商品dataに実行module・weightを選ばせない
- 商品側の証拠は構造化field、限定したexact title parser、holdout検証済みの専用画像evaluator、固定CLIP外観scoreへ分け、条件ごとに `match`・`mismatch`・`unknown`・`conflict` を返す。語句不在を不一致にせず、画像scoreでexact属性を補完・上書きしない
- 生成した正面・左・右・背面画像は「正解画像」ではなく利用者承認済みの外観参照とする。候補は既存proxy、全体保持前処理、pHash重複除去、固定CLIPを通し、4参照それぞれと最も近い候補画像のcosineを平均する。候補画像欠損は `missing` とする
- 現行式では同じ候補画像が複数方向に使われ得るため、4方向掲載、向き、個数、寸法を証明しない。方向分類や1対1対応は、独立したholdoutで比較する別profile変更にする
- 必須条件は `confirmed`、`uncertain`、`contradicted` の順で総合scoreより先に比較し、明示的不一致を外観・価格・レビューで打ち消さない。unknown条件を商品ごとに分母から除いて有利にせず、初期段階では不一致候補も理由付きで残す
- 候補集合を使うcenter・z-scoreは、無関係な候補の追加・削除で同じ商品の値が変わるためproductionへ採用しない。case3を見て決めたweightや提出labelは開発用の上限確認に限り、最終採否には未使用の複数カテゴリholdoutを使う
- `BACKEND.md`、`REQUIREMENTS.md`、`DB-SCHEMA.md`、`SECURITY.md`、`DEVELOPMENT.md`、`SEARCH-FLOW.md`、`FRONTEND.md`、`GOAL.md`、`ISSUES.md`、`NEXT-STEPS.md`、`CHANGELOG.md` を実装済み・設計済み・未実装の区分と次の再開位置へ同期した

検証結果:

- `uv run --frozen --offline --no-sync python tools/check_markdown_links.py`: 成功。現行Markdown 16件、local link 985件、anchor 600件、heading 1277件、fence 197組
- `uv run --frozen --offline --no-sync pytest -q tests/test_markdown_links.py`: 成功、4 passed
- `git diff --check`: 成功、出力なし
- 着手前状態と編集記録の照合: 設計反映・管理同期の上記11文書と、この `WORKLOG.md` の現行Markdown計12件だけを編集した。着手前から存在する他の未コミット変更は保持した

production code、test、dependency、model、画像、外部状態は本作業で変更していない。実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネス、commit、pushも実行・確認・接続していない。この成功は文書構造と記録整合性だけを確認したものであり、型付き条件または次期rankingの実装・品質を証明しない。

## 49. 2026-09-04: 型付き条件と証拠裁定の最小domain実装

この項目は、[EXEC-035](GOAL.md#exec-035-型付き条件と証拠裁定の最小domain実装) に従い、型付き条件、repository内registry、証拠裁定、必須状態と安定順位keyを、現行検索へ接続しない独立domainとしてoffline TDDした未コミット変更を記録する。

- `typed_requirements.py` に、`boolean`・`enum`・`integer`・`decimal`・`text_set`・`semantic` のstrictな期待値・観測値、条件draft、正規化済み条件、registry model、canonical digestを追加した
- 初期registryは9つのnamespace付きattribute keyを固定し、alias、型別operator、単位、強さ、既定weight、source priority、evaluator ID・versionをrepository sourceだけから決める。条件draftはevaluator、module、weight、priority、registry digestを指定できない
- 初期registryのexact属性は `structured` と `title_exact` だけを許可し、`visual_feature` とCLIP類似度を証拠へ使わない。`semantic` はpreferredだけを許可する
- `requirement_evaluation.py` に、registryへ結んだ証拠、最高優先度の裁定、同順位矛盾、型別operator比較、固定分母の一致率、`confirmed`・`uncertain`・`contradicted`、候補集合へ依存しない順位keyを追加した
- aliasがcanonical値を上書きするregistry、正規化していない条件、名前空間なしの証拠key、数値として同値なのに異なるdigest、decimalの過剰精度を補足REDで再現し、入口の正規化・再検証で拒否または同一化した
- 現行 `NormalizedSearchIntent`、`ObservedProductAttributes`、ranking-v3、product pipeline、orchestration、cache、SQLite履歴、画像score、フロントエンドは変更・接続していない

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| 新規2 testの初期RED | 実装前に新契約が既存挙動で偶然通らないことを確認する | 最初の収集時評価は無効なREDとして破棄した。修正後は25 failed / 6 passed、終了1。typed test SHA-256 `6f17e2604554aa1c6867ce7b41a1b0de806efa1ffa67a8819b1863fc681b2166`、evidence test SHA-256 `5118e8772ea7ca8568b4b3ca15850651665e35aada1cbc92b55e42da58f95bd7` | schema・関数不足を原因とする有効なREDであり、assertionを弱めず実装へ進めた |
| alias・canonical condition・decimal・証拠keyの補足RED | 初期GREEN後に見つけたcanonical化とbindingの迂回を再現する | 2 failed / 31 passed、対象別に1 failed、2 failedを確認した後、修正した | registry alias、条件set digest、attribute key、Decimal表現を公開入口で再検証する必要がある |
| `pytest -q tests/test_search_v2_typed_requirements.py tests/test_search_v2_requirement_evaluation.py` | 新しいdomain契約を集中的に確認する | 36 passed | 型、registry、正規化、証拠4状態、必須状態、固定分母、順位keyの対象回帰が成功した |
| `pytest -q tests/test_search_v2_*.py` | 既存の次期検索domainへ回帰がないか確認する | 768 passed / 9 skipped | 全v2 offline境界が成功し、skipは明示opt-inの固定ONNX実行だけである |
| `pytest -m 'not live_api'` | repository全体の外部通信なし回帰を確認する | 1505 passed / 9 skipped / 1 deselected | 実providerを呼ばない標準testが成功した。live API成功は示さない |
| `uv lock --check --offline`、Ruff check・format check | dependency lockとPython静的品質を確認する | lock 79 packages、Ruff 182 files、全て成功 | dependency取得なしでlock整合と対象Python形式を維持した |
| 現行Markdown、Python 3.10 AST、AGENTS目次、`git diff --check` | 文書参照、対応構文、目次、差分形式を確認する | Markdown focused 4 passed、16 files・local link 998件・anchor 613件・heading 1291件・fence 197組、AST 182 files、目次15件、diff成功 | 現行正本の参照、Python 3.10構文、標準目次、差分形式に欠落がない |

最終SHA-256は `typed_requirements.py` が `b760f149a91a04f73f566d42e36288487a454c23e4f0fb909eda9875c7524b76`、`requirement_evaluation.py` が `8ebf4cbc533ee12eab13d099a2f26a7bfddcfe2b95b91d6bb6acca7fe07bb422`、対応testが順に `5a604b957b694b4b5f033754b751193c77b7c0e2d28790825eb2ce816f5940ad` と `62b0fdf7d526282e0274c92537d57ee4255adabb2b39521bce7b8cdf410297c2` である。

実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・接続していない。この成果は、既に型が付いた条件と証拠を安全に裁定できる土台であり、自然文または実商品から正しい条件・証拠を抽出できること、case3順位が改善すること、production検索が型付き順位を使うことを証明しない。次の通常ローカル作業は、観測済み商品属性と限定した商品名表現を固定registryの証拠へ変換するadapterを、新しいExecution Planでoffline TDDすることである。

## 50. 2026-09-04: 観測商品から型付き証拠へのadapter

この項目は、[EXEC-036](GOAL.md#exec-036-観測商品から型付き証拠へのadapter) に従い、正規化済み商品の専用color field、固定feature全体、限定した商品名表現から、registryが許可する型付き証拠を作るadapterを、現行検索へ接続しない独立domainとしてoffline TDDした未コミット変更を記録する。

- `product_evidence.py` に、固定adapter profile、正規化済み商品digest、product・requirement set・registry・profileへ結んだ証拠set、source別の入力artifact digestを追加した
- `appearance.color` のstructured証拠は専用colorだけを読み、form、connection、充電式、収納口数、幅は固定feature item全体だけを読む。titleはregistry語彙のbounded exact・最長一致と、収納口数・幅の明示label付きASCII数値だけを読む
- source欠損、語句不在、parser未対応、未登録の専用値を別のunknown reasonへし、title語句不在やdescription内の語句を不一致・観測値へ変換しない
- structuredをtitleより優先し、同sourceの異なる値は最大8件まで保持して `conflict` 裁定へ渡す。商品本文は証拠set、repr、固定errorへ複製しない
- `mouse.connection` の固定registryへ `ワイヤレス` aliasを追加した。商品dataから語彙を動的追加せず、registry digestを更新した
- 現行intent、ranking-v3、product pipeline、orchestration、cache、SQLite履歴、画像score、フロントエンドは変更・接続していない

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| 新規product evidence testの初期RED | 実装前に新契約が既存挙動で偶然通らないことを確認する | stubに対して19 failed、終了1。RED test SHA-256 `e6c1ed9a3fda9e173cf03fcbb8870ee985d0ace32757ee55a7ba09798944b578` | 未実装の公開入口とschema不足を原因とする有効なREDから実装を開始した |
| 数値単位、短い日本語alias、正規順、未登録color、source上限、本文非露出の補足RED | 初期GREEN後に見つけた誤検出・resource・binding境界を固定する | 最初に3 failed / 21 deselected、追加監査で1 failed / 4 passed / 22 deselectedを確認し、修正後は対象5 passed / 22 deselected | `収納口20cm`・`収納口数20cm`・`収納口1200円`、`黒bird` を観測値にせず、source上限と非露出を維持できる |
| `pytest -q tests/test_search_v2_product_evidence.py tests/test_search_v2_requirement_evaluation.py tests/test_search_v2_typed_requirements.py` | 新adapter、証拠裁定、registryの結合を集中的に確認する | 63 passed | structured優先、title exact、unknown、conflict、digest、型別裁定の対象回帰が成功した |
| `pytest -q tests/test_search_v2_*.py` | 既存の次期検索domainへ回帰がないか確認する | 795 passed / 9 skipped | 全v2 offline境界が成功し、skipは明示opt-inの固定ONNX実行だけである |
| `pytest -m 'not live_api'` | repository全体の外部通信なし回帰を確認する | 1532 passed / 9 skipped / 1 deselected | 実providerを呼ばない標準testが成功した。live APIまたはproduction成功は示さない |
| `uv lock --check --offline`、Ruff check・format check、Python 3.10 AST | lock、静的品質、対応構文を確認する | lock 79 packages、Ruff 184 files、AST 184 files、全て成功 | dependency取得や外部通信なしでlock整合とPython形式を維持した |
| 現行Markdown、AGENTS目次、`git diff --check` | 文書参照、構造、差分形式を確認する | Markdown focused 4 passed、16 files・local link 1008件・anchor 623件・heading 1305件・fence 197組、目次15件、diff成功 | 現行正本の参照、対応見出し、構造、差分形式に欠落がない |

最終SHA-256は `product_evidence.py` が `74bb76a4883e2dcc1bb5d4066b2b85b16c3f30bd6d40daeb1d04f024fa6f2826`、registry alias更新後の `typed_requirements.py` が `45ec569a7a999323a15300255cb43eadee4658d887ea18c1d70d7698bd56fd61`、product evidence testが `061aa9052dff763cf6aa96385634fbc1efef0e477c038e6cf06580605b610d1b` である。

実Amazon画像host、実商品、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・接続していない。この成果は、正規化済み商品から限定した証拠を安全に作れる土台であり、Bonsaiの自然文から正しい型付き条件を作れること、実Outscraper商品が必要属性を返すこと、case3順位が改善すること、production検索が型付き順位を使うことを証明しない。次の通常ローカル作業は、Bonsaiのstrict応答からtrusted registryが受理できる型付き条件候補だけを作るadapterを、新しいExecution Planでoffline TDDすることである。

## 51. 2026-09-04: Bonsai型付き条件候補adapter

この項目は、[EXEC-037](GOAL.md#exec-037-bonsai型付き条件候補adapter) に従い、既存1回のBonsai strict intent応答へ型付き条件候補を追加し、repository内のtrusted registryだけで型付き条件または確認待ちへ変換するadapterを、現行検索へ接続しない独立domainとしてoffline TDDした未コミット変更を記録する。

- `SearchIntentDraft` へ最大64件の必須 `typed_conditions` を追加した。各候補はattribute key、operator、JSON-nativeな期待値、strengthだけを持ち、全field必須、extra禁止、値型ごとのdiscriminated unionである
- integerはJSON整数、decimalは指数表記を許さない有限桁のASCII文字列として受け、ローカルadapterでPython `Decimal` へ変換してから既存の `normalize_typed_requirements()` へ渡す
- `typed_intent_adapter.py` に、固定profile、候補順から作る `condition-001` 形式のID、intent・candidate set・registry・requirement set・profile digest、valid partial requirement、固定blocking issueを追加した
- unknown key、known keyに対する値型・operator・unit・値不整合、semanticのrequired・excluded指定、正規化後の重複、上流blocking ambiguityを暗黙に破棄・文字列化・soft化せず、候補indexと固定codeへ変換する
- candidate本文と上流ambiguity messageはproposalのreprや固定errorへ複製せず、Bonsaiにcondition ID、evaluator、module、model path、URL、command、weight、priority、registry digestを指定させない
- 固定Bonsai promptを9 keyのregistry、canonical enum値、JSON値型、semantic制約、禁止metadataへ同期した。別のBonsai callやprovider fallbackは追加していない
- 既存のstrict intent fixtureを必須fieldへ移行した。現行Streamlit・legacy Bonsai client、ranking-v3、product pipeline、orchestration、cache、SQLite履歴、画像score、フロントエンドは変更・接続していない

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| 新規typed intent adapter testの初期RED | 実装前にcandidate schemaとadapter契約が既存挙動で偶然通らないことを確認する | stubに対して18 failed / 1 passed、終了1。RED test SHA-256 `3a79d5c4cba8597105829d4319593141914687b9e354364462c364bf7feea0e4` | strict候補、registry変換、blocking issue、digest、非LLM境界の不足を原因とする有効なREDから開始した |
| prompt型整合の補足RED | registryとpromptのvalue typeが一致することを確認する | `appearance.style` がsemanticでなくenumと読める説明に対して1 failed / 18 deselected、修正後1 passed / 18 deselected | semantic、`similar_to`、preferredの組合せを独立規則として固定した |
| `pytest -q tests/test_search_v2_typed_intent_adapter.py tests/test_search_v2_typed_requirements.py tests/test_search_v2_intent.py tests/test_search_v2_bonsai_adapter.py tests/test_search_v2_bonsai_request.py tests/test_search_v2_bonsai_http.py` | 新adapter、trusted domain、既存Bonsai strict境界を集中的に確認する | 151 passed | strict JSON候補、1-call schema binding、alias・Decimal正規化、local ID、partial result、固定issue、prompt、非network境界が成功した |
| `pytest -q tests/test_search_v2_*.py` | 既存の次期検索domainへ回帰がないか確認する | 814 passed / 9 skipped | 全v2 offline境界が成功し、skipは明示opt-inの固定ONNX実行だけである |
| `pytest -m 'not live_api'` | repository全体の外部通信なし回帰を確認する | 1551 passed / 9 skipped / 1 deselected | 実providerを呼ばない標準testが成功した。live APIまたはproduction成功は示さない |
| `uv lock --check --offline`、Ruff check・format check、Python 3.10 AST | lock、静的品質、対応構文を確認する | lock 79 packages、Ruff 186 files、AST 186 files、全て成功 | dependency取得や外部通信なしでlock整合とPython形式を維持した |
| 現行Markdown、AGENTS目次、`git diff --check` | 文書参照、構造、差分形式を確認する | Markdown focused 4 passed、16 files・local link 1021件・anchor 636件・heading 1319件・fence 197組、目次15件、diff成功 | 現行正本の参照、対応見出し、構造、差分形式に欠落がない |

最終SHA-256は `intent.py` が `cdc5747b057cffa3ace119e228c4c7856f4700e63d437571d9935969286ff137`、`typed_intent_adapter.py` が `6f78e18359304efb97e212901f1d8882b058f16f013e5b1df1c5ef32f989d0bb`、`bonsai_intent_prompt.txt` が `7a16394361bca1bfddd5605c28d237a31cbd0ed519c25e50e9e7c3ef84601310`、対応testが `1b4f3640bd3cc7ee9cfd11b835b5e748400927091778c0cf8b61c00efa22b17a` である。

実Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、実Amazon候補、browser、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・接続していない。この成果はBonsai候補を安全なlocal条件へ変換する契約であり、実Bonsaiが利用者条件を漏れなく正しく分解すること、case3順位が改善すること、production検索が型付き順位を使うことを証明しない。次の通常ローカル作業は、型付き条件、商品証拠、裁定、必須状態を新しいranking schemaへ接続する境界を、新しいExecution Planでoffline TDDすることである。

## 52. 2026-09-04: 型付き条件ranking v4境界

この項目は、[EXEC-038](GOAL.md#exec-038-型付き条件ranking-v4境界) に従い、型付き条件、限定商品証拠、条件裁定、必須状態を独立した `typed-ranking-v4` へ接続した未コミット変更を記録する。現行 `ranking-v3` と検索経路は変更せず、外部通信を持たない合成domainでTDDした。

- `typed_ranking.py` に、v3とdomain separationしたschema 4.0、固定profile、score breakdown、商品result、batch result、公開ranking入口を追加した
- 公開入口はintent、query plan、normalized product batch、typed proposal、固定profileを再検証し、proposalをintentと固定registryから再構築する。blockingまたは不一致はv3 source rankingと商品証拠を作る前に固定errorで拒否する
- 全商品について同じrequirement setから限定証拠、全条件decision、typed evaluationを構築し、product・intent・query・batch・proposal・registry・各profileのdigestへ結んだ
- typed attributesはrequired・preferredの `match` とexcludedの `mismatch` だけを加点し、`unknown`・`conflict` も含むregistry weightを固定分母にする。条件がない場合だけnot requestedとして除外する
- v3のtitle、price、無効なimage、最小weightのreview quality、negative判定だけを利用し、自由語attributesのscore・language・matched term・missing termはv4へ持ち込まない
- 必須状態、required ratio、preferred ratio、v4 total、response indexの順で全候補を安定sortし、必須不一致を総合scoreで逆転させない
- resultの再検証で証拠、裁定、評価、score、順位の差し替えを拒否し、v3 batchをv4として読み替えない
- provider client、LLM、network、画像runtime、動的import、callbackは追加せず、現行pipeline、state、cache、SQLite履歴、API、UI、外部委託中フロントエンドは変更・接続していない

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| 新規typed ranking v4 testの初期RED | 実装前に新module・schema・一括接続が既存挙動で偶然通らないことを確認する | collectionで `ModuleNotFoundError: No module named 'src.search_v2.typed_ranking'`、終了2 | 未実装moduleを原因とする有効なREDから開始した |
| `pytest -q tests/test_search_v2_typed_ranking.py tests/test_search_v2_ranking.py tests/test_search_v2_typed_requirements.py tests/test_search_v2_product_evidence.py tests/test_search_v2_requirement_evaluation.py tests/test_search_v2_typed_intent_adapter.py tests/test_search_v2_intent.py` | v4と再利用するv3 component、型付き条件、証拠、裁定、adapterを集中的に確認する | 140 passed | 必須状態先行、固定分母、excluded、改ざん拒否、空条件、旧schema拒否と関連回帰が成功した |
| `pytest -q tests/test_search_v2_*.py` | 既存の次期検索domainへ回帰がないか確認する | 834 passed / 9 skipped | 全v2 offline境界が成功し、skipは明示opt-inの固定ONNX実行だけである |
| `pytest -m 'not live_api'` | repository全体の外部通信なし回帰を確認する | 1571 passed / 9 skipped / 1 deselected | 実providerを呼ばない標準testが成功した。live APIまたはproduction成功は示さない |
| `uv lock --check --offline`、Ruff check・format check、Python 3.10 AST | lock、静的品質、対応構文を確認する | lock 79 packages、Ruff 188 files、AST 188 files、全て成功 | dependency取得や外部通信なしでlock整合、形式、Python 3.10構文を維持した |
| 現行Markdown、AGENTS目次、`git diff --check` | 文書参照、構造、差分形式を確認する | Markdown focused 4 passed、16 files・local link 1043件・anchor 651件・heading 1333件・fence 197組、目次15件、diff成功 | 現行正本の参照、対応見出し、構造、差分形式に欠落がない |

最終SHA-256は `typed_ranking.py` が `b81b9c25d5b4d0fbde44f87c356c021e90bbe19004be4d6e96b2a0d2ff82cf8b`、対応testが `65b154f14cb8adf41eecd44e7f3fb4d4ddf98bbde9cfac2cdc3e742366bdc896` である。

合成fixtureでは、v3の総合scoreで必須不一致の商品が先頭になる配置に対し、v4が `confirmed`、`uncertain`、`contradicted` の順へ直すことを固定した。これは型付き契約と順位規則の再現であり、実Bonsaiの条件分解品質、実Outscraperの属性充足率、case3またはproduction順位の改善を証明しない。

実Amazon画像host、実商品、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・接続していない。次の通常ローカル作業は、独立v4を第1確認・検索後半pipeline・state・履歴へschema migration付きで接続する境界を、新しいExecution Planでoffline TDDすることである。

## 53. 2026-09-04: 型付きranking v4のoffline検索経路移行

この項目は、[EXEC-039](GOAL.md#exec-039-型付きranking-v4のoffline検索経路移行) に従い、独立していた `typed-ranking-v4` を第1確認、承認、state、Outscraper後半pipeline、表示用履歴へ接続した未コミット変更を記録する。接続先は合成fixtureだけで検証する次期offline backendであり、legacy現行検索、実provider、API、外部委託中フロントエンドには接続していない。

- 第1確認へ、Bonsaiのstrict intent候補を固定registryで確定したtyped proposalを追加した。ready proposalだけが画像確認、最終確認、承認、検索へ進め、blocking proposalはvalid partial条件を持っていても後続処理を開始しない
- approval、state、orchestration、product pipelineをschema 3.0へ更新し、同じproposal digest、`typed-ranking-v4` profile、product evidence profileを承認前から完了stateまで再検証する
- 後半pipelineは自由語attributesを使うv3 batchでなく `TypedRankedProductBatch` だけを返し、必須状態を総合scoreより先に比較するv4 batch digestを完了stateへ記録する
- 表示用履歴をschema 2.0へ更新し、typed decisionを一致、非該当、未確認、情報が矛盾、不一致、該当へ限定して変換する。raw score、weight、内部evidence、provider metadataは表示snapshotへ複製しない
- SQLite repositoryを `user_version=2` へ更新した。旧version 1は自動変換・削除せず、file byteを変えない固定storage errorで拒否する
- 商品正規化が認可moduleを逆参照する循環を避けるため、credential-freeなOutscraper要求model・builder・digestを `outscraper_contract.py` へ分離し、`outscraper_request.py` は既存公開名を保ったまま認可だけを担当する
- provider client、network、画像runtime、動的import、callbackは追加していない。画像componentは無効のままで、旧ranking-v3 artifactと旧offline schemaは新契約として読み替えない

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| typed migration testの初期RED | proposal伝搬、schema更新、v4 pipeline、typed履歴が既存挙動で偶然通らないことを確認する | 実装前に6 failed | proposal未伝搬、旧schema、v3 pipeline、typed履歴未接続を原因とする有効なREDから開始した |
| `pytest -q` によるapproval・state・orchestrator・Outscraper要求・pipeline・history・typed rankingのfocused test | 今回変更した境界と直接関係する回帰を確認する | 121 passed | ready・blocking、digest結合、v4 batch、typed理由、v1非破壊拒否を含む対象境界が成功した |
| `pytest -q tests/test_search_v2_*.py` | 次期検索domain全体の回帰を確認する | 839 passed / 9 skipped | 全v2 offline境界が成功し、skipは明示opt-inの固定ONNX実行だけである |
| `pytest -m 'not live_api'` | repository全体の標準offline回帰を確認する | 1576 passed / 9 skipped / 1 deselected | 実providerを呼ばない標準testが成功した。live APIまたはproduction成功は示さない |
| `uv lock --check --offline`、Ruff check・format check、Python 3.10 AST | lock、静的品質、対応構文を確認する | lock 79 packages、Ruff 189 files、AST 189 files、全て成功 | dependency取得や外部通信なしでlock整合、形式、Python 3.10構文を維持した |
| 現行Markdown、AGENTS目次、`git diff --check` | 文書参照、構造、差分形式を確認する | Markdown focused 4 passed、16 files・local link 1066件・anchor 669件・heading 1347件・fence 197組、目次15件、diff成功 | 現行正本の参照、対応見出し、標準目次、差分形式に欠落がない |

変更対象15ファイルのSHA-256 manifest hashは `f7766de87775c2fda0ac9c3fc2a3afc63ddce4011ea47090ae8d852d9d22fe38` である。対象はapproval、state、orchestrator、product pipeline、history snapshot・repository、Outscraper要求分離・商品正規化と直接testであり、manifestは各fileの `sha256sum` 出力を同じ順序で再度SHA-256へ通した。

検証は合成Bonsai応答、合成Outscraper商品、in-memory state・ledger、一時SQLiteだけで行った。実Amazon画像host、実商品、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・接続していない。この成果はoffline契約の接続であり、実Bonsaiの条件分解品質、実Outscraperの属性充足率、case3またはproduction順位の改善を証明しない。次の通常ローカル作業は、case1からcase3をdevelopment setとして固定したまま、未使用holdoutの評価契約と集計方法を新しいExecution Planでoffline TDDすることである。

## 54. 2026-09-04: 未使用holdoutの評価契約と集計境界

この項目は、[EXEC-040](GOAL.md#exec-040-未使用holdoutの評価契約と集計境界) と [FR-419](REQUIREMENTS.md#35-次期検索フロー-v2) に基づく未コミット変更を記録する。case1からcase3を設計用development setとして固定し、実holdoutを受領する前に正解・予測の分離、入力拒否、指標、集計方法を合成fixtureで固定した。

`holdout_evaluation.py` に、固定 `typed-ranking-v4` と画像無効へ結ぶ評価profile、holdout roleを持つ正解dataset、`ranked`・`blocking`・`failed` を区別する予測set、case・category・全体reportを追加した。正解datasetはcanonicalな非semantic条件、商品digest、期待decision、関連度gradeを保持し、既知development IDを拒否する。条件precision・recall・F1、候補precision・recall、decision exact accuracy、hard contradiction recall、uncertainty preservation、required status accuracy、同点gradeを除くstrict pairwise accuracy、full-list NDCGを固定式で計算する。blocked・failed、条件・商品欠落、unexpected条件・商品を有利に除外しない。

予測builderは完全なintent、query plan、typed proposal、ranked batchを相互に再検証するが、serializableな `digests-states-ranks-only-v1` にはartifact digest、条件identity、商品digest、decision、必須状態、順位だけを残す。初期GREEN後の安全監査で完全runtime artifactを予測modelから除き、検索文、商品名・説明・ASIN、URL、生provider応答、生例外を保持しないことをtestへ固定した。最低2 category・各2 case・各3商品・各1条件と安全labelの構成適格性は判定するが、品質合否は常に `not_assessed` である。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| 新規holdout testの実装前RED | 新moduleなしで受入testが偶然成功しないことを確認する | `ModuleNotFoundError: No module named 'src.search_v2.holdout_evaluation'` | 実装前に有効なREDから開始した |
| holdout・typed ranking・typed requirements・裁定・商品証拠のfocused test | 新評価境界と直接依存する既存契約の回帰を確認する | 117 passed | 完全一致、条件・商品過不足、blocking・failed、同点、NDCG、改ざん、本文非保持を含む対象境界が成功した |
| `pytest -q tests/test_search_v2_*.py` | 次期検索domain全体の回帰を確認する | 854 passed / 9 skipped | 全v2 offline境界が成功し、skipは明示opt-inの固定ONNX実行だけである |
| `pytest -m 'not live_api' -q` | repository全体の標準offline回帰を確認する | 1591 passed / 9 skipped / 1 deselected | 実providerを呼ばない標準testが成功した。実holdout品質やproduction E2Eは示さない |
| `uv lock --check --offline`、Ruff check・format check、Python 3.10 AST | lock、静的品質、対応構文を確認する | lock 79 packages、Ruff 191 files、AST 191 files、全て成功 | dependency取得や外部通信なしでlock整合、形式、Python 3.10構文を維持した |
| 現行Markdown、AGENTS目次、`git diff --check` | 文書参照、構造、差分形式を確認する | Markdown focused 4 passed、16 files・local link 1081件・anchor 682件・heading 1363件・fence 197組、目次15件、diff成功 | 現行正本の参照、対応見出し、標準目次、差分形式に欠落がない |

実装前RED testのSHA-256は `bb10e1de4b866442845e55fffd9d4effa3e98ea0f0f6cd18fc7abb839a5aec70`、最終moduleは `de45c86e092d2c4c164b0d13ad0288e3c8e355eb62ed9c3295490590777e0782`、最終testは `6fb8392efee52683aa1a6368f7255304ed664443d6ee9f48d1eee157bb85da31`、両fileのSHA-256 manifest hashは `5f89fb8f3c605f4188c05656cb7aa8176dd7c224d3026ed28e121562498130bf` である。

検証は合成intent、合成Outscraper商品、合成正解labelだけで行った。実holdout、case1からcase3のlabel・画像・score、固定ONNX、実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、browser、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・変更していない。これは評価契約と計算の実装であり、実Bonsaiの条件分解精度、実商品の属性充足率、未知categoryの順位品質、画像rankingの採用を証明しない。次の通常作業は、実holdoutを開く前に用途別の品質合格基準を別Planとdigestへ固定することである。

## 55. 2026-09-05: holdout品質合格ポリシーの固定

この項目は、[EXEC-041](GOAL.md#exec-041-holdout品質合格ポリシーの固定) と [FR-419](REQUIREMENTS.md#35-次期検索フロー-v2) に基づく未コミット変更を記録する。実holdoutの内容・結果を見る前に、人間が選んだ安全重視の基準を固定policyとdigestへ記録し、EXEC-040の評価reportとは別のassessmentを実装した。

`holdout_acceptance.py` に、strict・frozenな `HoldoutAcceptancePolicy`、固定順の `HoldoutAcceptanceCheck`、`pass`・`fail`・`ineligible` を返す `HoldoutAcceptanceAssessment` を追加した。policyは `typed-ranking-holdout-v1` と `typed-ranking-v4` のprofile digest、metric小数6桁、全閾値、全category必須、category別安全label最低1件を保持する。policy、evaluation report、assessmentは別のdomain-separated SHA-256へ結ぶ。

coverage不適格、またはhard contradiction・uncertainty labelが0件のcategoryを `ineligible` とする。適格なreportでは、blocking・failed 0件、condition F1・candidate recall・decision accuracy・NDCG 0.90以上、candidate precision・pairwise accuracy 0.85以上、hard contradiction recall・uncertainty preservation・required status accuracy 1.0を、全体と全categoryへAND適用する。microとcase macroがある指標は両方を判定し、別metricや大きいcategoryの高得点で未達を相殺しない。元の `HoldoutEvaluationReport.quality_decision` は `not_assessed` のまま変更しない。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_holdout_acceptance.py` の実装前RED | 新しい判定契約が既存コードで偶然成立しないことを確認する | exit 2、`ModuleNotFoundError: No module named 'src.search_v2.holdout_acceptance'` | 実装前に新moduleが存在しないことを確認した |
| holdout acceptance・evaluation focused test | policy、境界値、全category判定、3状態、改ざん、既存report不変を確認する | 44 passed | 合成metricだけに対する判定・再検証契約が成功した |
| `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_*.py` | 次期検索domain全体の回帰を確認する | 883 passed / 9 skipped | 全v2 offline境界が成功し、skipは明示opt-inの固定ONNX実行だけである |
| `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q` | repository全体の標準offline回帰を確認する | 1620 passed / 9 skipped / 1 deselected | 実providerを呼ばない標準testが成功した。実holdout品質やproduction E2Eは示さない |
| `uv lock --check --offline`、Ruff check・format check、Python 3.10 AST | lock、静的品質、対応構文を確認する | lock 79 packages、Ruff 193 files、AST 193 files、全て成功 | dependency取得や外部通信なしでlock整合、形式、Python 3.10構文を維持した |
| 現行Markdown、AGENTS目次、`git diff --check` | 文書参照、構造、差分形式を確認する | Markdown focused 4 passed、16 files・local link 1091件・anchor 692件・heading 1379件・fence 197組、目次15件、diff成功 | 現行正本の参照、対応見出し、標準目次、差分形式に欠落がない |

実装前RED testのSHA-256は `1991103bca3de644a6b421b4340c7ab25839bd91d0f2271cbc891f2bd41994cc` である。formatと追加のmacro・check改ざん回帰後の最終module SHA-256は `2c023e746a4c0f79c501000c364efe4932fd422fd70f9bcfe18105275f5b9238`、最終test SHA-256は `29c5ccfb32dab99afdde3ef4fd9f825992f36ea8219d396b64ce81ad642e8f9d`、両fileのSHA-256 manifest hashは `1aec6558492367d589055a59b00635fe035e81ca5f99dd2046cb6758ed5c2426` である。RED後に受入条件を弱めておらず、formatとcategory case macro・check改ざん検査だけを追加した。

検証は合成されたcase・category・全体metricだけで行った。実holdout、case1からcase3、固定ONNX、実Amazon画像host、Bonsai、Cloudflare、Outscraper、OpenAI、credential、課金、Windows実機、browser、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・変更していない。`pass` は与えたreportが固定基準を満たすことだけを表し、実際の条件分解精度、未知categoryの順位品質、画像ranking採用、production E2Eを証明しない。次はcase1からcase3を除く未使用の複数category holdoutと出所・分割記録を用意し、固定済みpolicyで本評価する。

## 56. 2026-09-05: 固定済み基準による最初のholdout評価

この項目は、[EXEC-042](GOAL.md#exec-042-固定済み基準による未使用holdout評価) と [FR-419](REQUIREMENTS.md#35-次期検索フロー-v2) に基づく未コミット作業を記録する。事前固定した `typed-ranking-holdout-acceptance-v1` を、case1からcase3および既存の実装・weight調整に使っていない2 category・4 case・12商品のholdoutへ一度適用した。

更新後CSVはSHA-256 `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea` で固定した。各caseは登録済みexact条件1件と3商品を持ち、各categoryはhard contradictionとuncertainty labelを最低1件ずつ持つためcoverage適格だった。検索文、商品名、URL、ASIN相当値、構造化商品情報を標準出力、文書、評価artifactへ転記していない。

利用者の明示承認後、`/home/llama.cpp/build/bin/llama-server` version 9294を `127.0.0.1:18080` のみにbindし、SHA-256 `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54` のlocal Bonsai modelをCPUで実行した。固定prompt、schema、各caseの検索文だけをtemperature 0、各最大1,000 output token、各最大300秒、4 calls、retry 0で送った。credential、外部network、server log、prompt cache、画像、Cloudflare、Outscraperは使っていない。

4件ともmodel応答は返ったが、既存のstrict Bonsai response境界が `bonsai_response_invalid` として拒否した。各所要時間は218.837秒、212.436秒、209.006秒、214.882秒だった。条件候補0件、ranked case 0件、failed case 4件として除外せず評価した。元reportは `quality_decision=not_assessed`、固定assessmentは53 checks中45件未達の `fail` である。条件F1、候補precision・recall、decision accuracy、hard contradiction recall、uncertainty preservation、required status accuracy、pairwise accuracy、mean NDCGは全て0.000000となった。

失敗の直接原因は、4応答が既存のstrict response契約を通過しなかったことである。この契約はHTTP response metadata・body、OpenAI互換envelope、非空の `choices[0].message.content`、content全体の単一JSON object、重複key・非有限数、`SearchIntentDraft` の必須field・型・extra禁止、intent正規化を検査する。安全のため、いずれの不一致も同じ固定エラーへ変換し、生responseと内部例外を保持しない。そのため、どの検査項目が4件それぞれで失敗したかは未確定であり、特定のJSON構文またはfieldを原因として推測しない。

CSVのcoverageとregistry照合は成功しているため、データ構成不足による `ineligible` ではない。ranking、画像、Cloudflare、Outscraperは開始前であり、商品順位や画像品質が今回の直接原因でもない。条件抽出失敗を評価から除外しない設計により、4 caseが `failed`、ranked caseが0となり、後続metricが全て0.000000へ伝播してassessmentが `fail` となった。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| CSVの本文非表示preflightとregistry照合 | holdout構成、型、演算子、安全label、未使用宣言を送信前に確認する | 12行、4 case、2 category、登録済み4 key、構造error 0、coverage適格 | `ineligible` ではなく品質判定へ進める入力だった |
| localhost Bonsai 4 calls | 人間の正解条件を予測へ流用せず、実modelのstrict条件抽出を測る | 4件全て `bonsai_response_invalid`、retry 0、成功0 | transport到達は確認できたが、strict条件抽出は1件も受理できなかった |
| `evaluate_holdout_predictions()` と `assess_holdout_quality()` | 失敗caseを除外せず固定policyへ適用する | failed 4、ranked 0、report `not_assessed`、assessment `fail` | 今回の不合格はranking品質ではなく、ranking前の条件抽出契約が停止要因である |
| 公開digest関数によるread-back | reportとassessmentの改ざんや不完全保存を検出する | report・assessment digest一致、一時結果artifactにURL・ASIN相当値なし | 本文非保持結果から判定を再現できる |
| localhost port確認とserver停止 | 評価後にprocessとlistening socketを残さない | server停止、`127.0.0.1:18080` は非listen | 実行後にlocal service状態を残していない |
| holdout evaluation・acceptance focused test | 実行後も集計・固定policy契約が変わっていないことを確認する | 44 passed | 実結果に合わせて評価式や閾値を変更していない |
| `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q` | repository全体の標準offline回帰を確認する | 1620 passed / 9 skipped / 1 deselected | 外部providerを使わない既存機能の回帰は成功した |
| `uv lock --check --offline`、Ruff check・format check | lock整合、静的品質、形式を確認する | lock 79 packages、Ruff 193 files、全て成功 | dependency取得なしで標準Python gateを維持した |
| 現行Markdown検査、`git diff --check` | 文書参照と差分形式を確認する | 16 files、local link 1107件、anchor 706件、heading 1394件、fence 197組、Markdown test 4件、diff成功 | 現行正本の参照と差分形式に欠落がない |

dataset SHA-256は `76b808c0f144c9b59e5b0fc25e70a748a11829befbb41af249c60d5568d41ac7`、prediction setは `703ebd0fa15c64b2216276f0f4c078a3a193397c78615bea0cacf0ad4883bc01`、evaluation reportは `c7e6d4ce93eb29407fd1eadf559279e2c4bf373adfb61fadebf02303208f4202`、acceptance policyは `de4b17313dbcbe6bc7e032b36f8a00e59506f49a600e0e0138c748c734073db3`、assessmentは `88a4cbf234bb75e1b5c133617131b7ddb0aee6436fb424438127cf290ad13bec` である。

結果artifactを書き終えた後、一時runnerの表示用summaryがreport fieldの参照階層を誤って終了した。保存済みartifactを公開digest関数で再検証して結果を確定し、モデル呼出しは再実行しなかった。一時runnerは製品codeへ残さず、必要なdigestと集計値を正本文書へ反映した後に一時結果JSONも削除した。生responseを保存しない承認条件を維持したため、strict不適合の具体箇所は今回の評価だけでは確定しない。

このholdoutは使用済みとしてdevelopmentへ降格した。EXEC-042完了時点では同じCSVを再送せず、別の非機密な合成検索文1件を診断に使う予定だった。この予定は後続のEXEC-043で利用者指定により、同じCSVをdevelopment regressionとして再利用する方針へ変更した。画像rankingは無効のままで、Cloudflare、Outscraper、OpenAI、Amazon、browser、Windows native、外部委託中フロントエンド、AIレビューハーネス、commit、pushはEXEC-042で実行・確認・変更していない。

## 57. 2026-09-05: Bonsai構造化出力と安全診断

この項目は、[EXEC-043](GOAL.md#exec-043-bonsai構造化出力と安全診断) と [FR-401](REQUIREMENTS.md#35-次期検索フロー-v2) に基づく未コミット作業を記録する。EXEC-042の4件が同じ固定errorで停止し、不一致段階を特定できなかったため、strict parserを緩めず生成制約と本文非保持diagnosticを追加した。

`bonsai_request.py` のrequest descriptorをschema 3.0へ更新し、canonical bodyへ `response_format={"type":"json_object"}` を追加した。application `max_tokens` は送らない。現行Pydantic schemaはllama.cpp同梱converterがdecimal regexのnon-capturing groupを拒否したため、system promptとprovenanceには残すが生成grammarのschema引数へ直接渡さない。request byte数と最大1 MiB responseをtoken数の保守的上界としてledgerへ予約するが、これはmodelの生成上限ではない。1 call、300秒、1 MiB、llama.cpp context、EOSは維持する。

`bonsai_adapter.py` に `BonsaiResponseDiagnostic` と固定messageの `BonsaiResponseContractError` を追加した。失敗段階はresponse metadata、envelope、content JSON、draft schema、intent normalization、output truncationの6種類である。diagnosticは正規化済みfinish reason、妥当なcompletion token件数、response byte数だけを持ち、生response、検索文、provider固有理由、field名・値、内部validation例外を保持しない。duplicate key、非有限数、extra field、欠落field、型coercion、Markdown fence、JSON断片救済は引き続き拒否する。

利用者は同じCSVの再利用を指定した。EXEC-042で結果を確認済みのため、このCSVは以後development regression dataであり、再評価を独立holdout、未知データへの一般化、production合格として扱わない。localhost再実行は、endpoint、4 calls、retry 0、300秒・1 MiB、credential・費用・外部networkなし、保存範囲を実行直前に示して明示承認を得るまで行わない。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| 新request・diagnosticの対象nodeだけを列挙した実装前pytest | application token上限なし、JSON object制約、安全な失敗段階が現行実装で偶然成立しないことを確認する | exit 1、10 failed | 現行builderは `max_output_tokens` が必須で、diagnostic型と段階情報が存在しないため期待どおりREDになった |
| 同じ対象nodeのGREEN | REDのtest内容を弱めず最小実装を確認する | 10 passed | canonical body、6段階、truncation、unknown finish reason、本文非保持、frozen diagnosticが成立した |
| Bonsai adapter・request・HTTP・typed adapter・orchestration・history snapshot | request schema更新に関係する既存境界を回帰確認する | 159 passed | mock・fixture上でstrict responseから履歴結合まで互換箇所が成功した |
| `uv run --frozen --offline --no-sync pytest -m 'not live_api'` | repository全体の最終offline回帰を確認する | 1628 passed / 9 skipped / 1 deselected | 外部providerを呼ばない全testが成功した。修正後のlocal model成功は示さない |
| 対象8 fileのRuff check・format check | 実装とtestの静的品質・形式を確認する | 成功 | 対象fileにlint・format違反がない |
| lock、全Ruff、Markdown、`git diff --check` | lock整合、全Python形式、文書参照、差分形式を確認する | lock 79 packages、Ruff check成功、format 193 files、Markdown 16 files・1119 links・718 anchors、diff成功 | dependency取得や外部通信なしで標準gateが成功した |

RED時点とGREEN時点でtest内容は同一である。SHA-256は `tests/test_search_v2_bonsai_request.py` が `f640535745a9f668fc5f64e0724b363a3034659ecf98d96524de46c85ec6ac72`、`tests/test_search_v2_bonsai_adapter.py` が `21c933f4c35601c9ed3d5e2d40416edded91117001734f702daca0d6e93da66a` である。最終module SHA-256は `bonsai_adapter.py` が `01ccf94168c9583ab6aa3f06d88e607d8fd1363b1622559ada14671c37843421`、`bonsai_request.py` が `b0a0f44ee8921d812cb0ede2753737cb5cdd9de27736dec3c96c110989586b16`、`orchestrator.py` が `dded3a5369a4111b342abd2468ffa5245d529453f78181bc6cc8e814df61afd1` である。

その後、利用者へendpoint、payload、4 calls、retry 0、各300秒、1 MiB response、credentialなし、費用0円、外部networkなし、本文非保持を提示して明示承認を得た。同じCSVをdevelopment regressionとしてrequest schema 3.0で再利用した。4件は300.101秒、300.104秒、300.105秒、300.066秒で全て `request_failed` となり、安全なresponse bytes、completion token、finish reasonは得られずresponse parserへ到達しなかった。coverageは適格、failed 4、ranked 0、元reportは `not_assessed`、assessmentは53 checks中45件未達の `fail` である。server停止後、`127.0.0.1:18080` が非listenであることを確認した。

安全なdigestはdataset `cb12c4a9c608b400bdad6f8b3b1e6a8ac68907c0a152304b438e42199e872d5e`、prediction set `1b0c2417d6be4bf9856b59c19b56b7b9890ff036821beb1ffd35c912a56e4ace`、evaluation report `665568a0a419e698870a686716c8c53f1eaca853dbcfc7cd7cdf527eb0525161`、assessment `ffe754d23fead22dee428fd15c1e33dd6a3d535e63bbb8f4a7ac83d6a4d61f57` である。検索文、商品名、商品情報、URL、ASIN相当値、生provider応答、内部例外本文は保存・転記していない。

## 58. 2026-09-05: Bonsai生成token上限・HTTP timeout撤廃

この項目は、[EXEC-044](GOAL.md#exec-044-bonsai-application-timeout撤廃) と [FR-401](REQUIREMENTS.md#35-次期検索フロー-v2) に基づく未コミット作業を記録する。EXEC-043の4件が全て旧300秒timeoutで停止したため、利用者決定に従い最適化を後続へ分離し、次期Bonsai経路のapplication生成token上限とHTTP timeoutを両方削除した。

`BonsaiIntentRequest` とbuilderから `max_output_tokens`・`timeout_seconds` を削除し、canonical bodyには引き続き `max_tokens` を含めない。request schemaとdomain-separated digestを4.0へ更新した。transport protocol、Requests実装、`BonsaiIntentConfig` からtimeout入力を削除し、Requests高水準呼出しへ `timeout` optionを渡さない。旧schema 3.0 requestと旧fieldを持つconfigはstrictに拒否する。

response 1 MiB上限、1 call予約、retry 0、redirect禁止、環境proxy・認証情報の不使用、TLS検証、本文非保持の6段階diagnostic、strict parserは変更していない。`maximum_usage_tokens` はrequest byte数と最大response byte数を保守的にledgerへ予約する単位であり、modelへ送る生成token上限ではない。application timeoutがないため、今後のlocal実行は応答、接続・OS失敗、server context境界、EOS、または人間の手動停止まで無期限に待ち得る。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| 対象4 nodeの実装前pytest | token・timeout制御が公開request、transport、configから消える契約を先に固定する | exit 1、4 failed | 旧required引数・field・signatureが残るため期待どおりREDで、importやfixtureの失敗ではなかった |
| 同じ対象4 nodeのGREEN | 最小実装で受入契約を満たすことを確認する | 4 passed | request body・descriptor・公開signature・configに両制御がなく、旧schemaを拒否する |
| Bonsai adapter・request・HTTP・typed adapter・orchestration・history snapshot・history repository | downstream bindingと履歴までの関連回帰を確認する | 172 passed | mock・fixture上でschema 4.0へ同期した経路が成功した |
| 対象PythonのRuff check・format check | 実装とtestの静的品質・形式を確認する | check成功、全193 files format済み | test 1 fileを機械formatし、意味を変更していない |
| 標準offline gate | repository全体のlock、Ruff、pytest、Markdown、差分形式を確認する | lock 79 packages、Ruff成功、offline pytest 1625 passed / 9 skipped / 1 deselected、Markdown 16 files・1132 links・731 anchors・1422 headings・197 fence pairs、diff成功 | dependency取得・実model・外部通信なしでrepository全体の回帰が成功した |

RED固定時点のtest SHA-256は `test_search_v2_bonsai_request.py` が `05d8822dac95bda1e2b0179ebfdc06f3ed94a603a756628e613cadfc0d436152`、`test_search_v2_bonsai_http.py` が `c1fb0d2b3be05061934f67085c5116cb55bedbfc25f4d8e48ba1d3044b430e3d`、`test_search_v2_orchestrator.py` が `978f202c501eeec9a89ac6d25e308b4e3dfaecd112c1f986bd787325a40a568c`、`test_search_v2_history_snapshot.py` が `d3afedd7140e7eee862b648a8cf2045cfda5caa787cd89064a3c810de10306bf` である。

最終module SHA-256は `bonsai_request.py` が `37105f67c951f7df7b9886c8287c65cc76e8458a13e5cf1390ce7458b545cd3b`、`bonsai_http.py` が `e50b9872fe7e4fa1abb9d04a1d65d50bcebb0670e3176a00c46199ad52a4fb65`、`orchestrator.py` が `d1054fc2f3c9ebfaf00736d90adc4f8ab75c0350923ea0f86660f447c6250276` である。最終test SHA-256は `test_search_v2_bonsai_request.py` が `2815fcdc927c7a5a8bffd74621dd45708b3f0f22e1470b226ec69f740b2bdc1c`、`test_search_v2_bonsai_http.py` が `c685b2b810e41c300d1367ea8c9cab8a73a2d3e69e5e3582ca1defcb28ffb8b7`、`test_search_v2_orchestrator.py` が `8681bc8cef80c6f3e1e5efa60d09dd6732befc62fbb2999376d4ad82e9864c38`、`test_search_v2_history_snapshot.py` が `d3afedd7140e7eee862b648a8cf2045cfda5caa787cd89064a3c810de10306bf` である。

この節のoffline実装完了時点では、時間上限なしのlocalhost Bonsaiを実行していなかった。後続の [EXEC-045](GOAL.md#exec-045-時間上限なしbonsai-development-regression) で別の明示承認を得て再実行した結果を次節へ記録する。

## 59. 2026-09-05: 時間上限なしBonsai development regression

この項目は、[EXEC-045](GOAL.md#exec-045-時間上限なしbonsai-development-regression) と [FR-401](REQUIREMENTS.md#35-次期検索フロー-v2) に基づく未コミット作業を記録する。利用者へ接続先、固定prompt・canonical schema・検索文だけを含むpayload、逐次4 calls、retry 0、application timeout・生成token上限なし、1 MiB response上限、credentialなし、費用0円、外部networkなし、本文非保持、`Ctrl+C` による手動停止を示し、明示承認を得た。

SHA-256 `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54` のBonsai-8Bをllama-server version 9294（`0f3cb3fc8`）で `127.0.0.1:18080` のみにbindし、CPU、context 8,192、parallel 1、offline、server log・prompt cache・UIなしで起動した。SHA-256 `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea` の使用済みCSVをdevelopment regressionとして再利用した。request schema 4.0、旧token・timeout fieldなし、bodyに `max_tokens` なし、`response_format={"type":"json_object"}` を実行時に再検証した。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| localhost Bonsai 4 calls | 旧300秒timeoutを外したrequest v4がどの段階まで進むか確認する | 4件ともHTTP完了後に `content_not_json`、retry 0 | timeout問題は解消したが、strict条件抽出は1件も成功していない |
| 固定holdout評価・assessment | 失敗caseを除外せず既存基準で集計する | coverage適格、failed 4、ranked 0、元report `not_assessed`、assessment `fail` | 商品rankingは開始されず、品質合格を示さない |
| request・llama.cpp静的確認 | token上限とJSON生成制約の実効性を区別する | requestに `max_tokens` なし、server既定 `n_predict=-1`、空schemaではJinja grammarなし | completion 2,000は設定上限ではなく、JSON宣言は生成grammarとして有効でなかった |
| server停止後のsocket・process確認 | local serviceを残さない | port closed、`llama-server` stopped | localhost待受とmodel processは終了した |
| 標準offline gate | live実行記録を反映した共有treeの回帰と文書整合を確認する | lock 79 packages、Ruff check成功・193 files format済み、pytest 1,625 passed / 9 skipped / 1 deselected、Markdown 16 files・1,148 links・747 anchors・1,436 headings・197 fence pairs、diff成功 | dependency取得と追加networkなしで現行treeの標準検査が成功した |

各caseの所要時間は313.169秒、316.069秒、325.651秒、318.563秒で、合計1,273.452秒、平均318.363秒だった。全件の `finish_reason` は `stop`、completionは2,000 tokens、response byte数は9,186、9,188、9,194、9,193だった。llama.cppは上限停止を `length`、EOSまたは停止語を `stop` へ写像するため、2,000はapplicationまたはserverで設定した生成上限ではない。

安全なdigestはdataset `cb12c4a9c608b400bdad6f8b3b1e6a8ac68907c0a152304b438e42199e872d5e`、prediction set `4c5499b22e67ed61c40bdb59ef8c76a075d8a7dc3d4ba7579adae3ef2ab3ec91`、evaluation report `29960a1aa7faa7d2939bf0de3262a94ff1312cba283fdf8a17eac4378dd363aa`、assessment `920f39eb6362925877da0625905edc93e9553d252fc6ee63539e10597c03b5f8` である。assessmentは53 checks中45件未達で、条件、候補、decision、安全状態、required status、pairwise、NDCGの全指標は0.000000だった。

現行llama.cppの `server-common.cpp` はschemaなしの `json_object` を空schemaへ変換し、Jinjaの `chat-auto-parser-generator.cpp` は非空schemaだけをresponse formatとしてgrammarへ組み込む。完全Pydantic schemaは既知の未対応decimal regexを含み、そのまま生成grammarへ渡していない。この組合せにより生成時のJSON制約が実質無効で、strict parserが4件を `content_not_json` として拒否した。生contentは保持していないため、非JSON文字列の具体形は確定しない。この課題は後続の [EXEC-046](GOAL.md#exec-046-llamacpp互換bonsai生成schema) で非空の互換生成schemaを別契約として追加し、application側の完全canonical schemaによる最終検証を維持する形で対応した。

検索文、商品名、商品情報、URL、ASIN相当値、生provider応答、内部例外本文は保存・転記していない。商品データ、画像、Cloudflare、Outscraper、OpenAI、Amazon、credential、課金、外部network、browser、Windows native、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・変更していない。

## 60. 2026-09-05: llama.cpp互換Bonsai生成schema

この項目は、[EXEC-046](GOAL.md#exec-046-llamacpp互換bonsai生成schema) と [FR-401](REQUIREMENTS.md#35-次期検索フロー-v2) に基づく未コミット作業を記録する。EXEC-045でschemaなしの `json_object` が生成grammarを有効化せず4件全てが `content_not_json` となったため、strictなapplication受理条件を緩めず、llama.cppが生成制約へ使える非空schemaを追加した。

`bonsai_adapter.py` に、完全な `SearchIntentDraft` schemaから全ての `pattern` keywordだけを再帰的に除き、canonical JSON bytesへする `search_intent_generation_schema_bytes()` を追加した。完全schemaは7,352 bytes、SHA-256 `f6650c439794aface4d3b2b98227c32d8123ea9349db2ca3ad82dab7eedfb88c`、生成schemaは7,203 bytes、SHA-256 `f557081591fa9d322364e8b65ac0583ee78a0359cd7e1721b659491e1e2fa865` である。除いた3箇所のregexは完全schemaへ残り、生成schemaだけを満たす不正値もapplication parserが拒否する。

`bonsai_request.py` はrequest schema 5.0として非空objectを `response_format.schema` へ含め、完全schemaと生成schemaのdigestを別fieldへ固定する。body・digest・schema欠落や旧4.0を送信前に拒否し、system messageには完全schemaを残す。applicationの生成token上限とHTTP timeoutは追加せず、1 transport call、retry 0、response 1 MiB上限、本文非保持diagnosticを維持した。本番フロー上では「条件を整理する」操作から最初の条件確認までに当たり、1回の整理操作につきBonsaiを1回呼ぶ。同じ条件の承認、商品取得、再表示、履歴閲覧では呼ばず、条件を編集して再整理した場合だけ新しい1回となる。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| 実装前に完全schemaと `pattern` 除去schemaをllama.cpp同梱Python converterへ入力 | 既知の非互換箇所と最小除外範囲を確認する | 完全schemaはdecimal regexで失敗、`pattern` 除去schemaは終了0 | 手書きschemaを作らず、既知の3 keywordだけを除けば現行converterへ渡せる |
| `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_bonsai_request.py` のRED | request v5、生成schema、別digest、完全schemaでの最終拒否を実装前に固定する | exit 1、3 failed / 41 passed | 生成schema APIがなく旧4.0が残るため、期待したproduction未実装理由で失敗した |
| 同じfocused testのGREEN | REDを弱めず最小実装を確認する | 44 passed | schema差分、固定digest、v5 body、tamper拒否、token・timeoutなし、1 call、strictな最終拒否が成立した |
| Bonsai adapter・HTTP・typed adapter・orchestration・historyの関連回帰 | downstream bindingを確認する | 114 passed | request schema更新後もmock・fixtureの関連境界が成功した |
| `uv run --frozen --offline --no-sync pytest -q tests/test_search_v2_*.py` | 次期検索domain全体を確認する | 890 passed / 9 skipped | 外部providerを使わないv2回帰が成功した |
| 生成schemaをllama.cpp version 9294のPython converterと実C++ `json_schema_to_grammar(schema, true)` へ入力 | production serverと同系統のgrammar変換可否をmodelなしで確認する | 両方とも終了0 | 非空schemaはlocal converterへ入力可能である。ただしmodel出力品質は示さない |
| 標準offline gate | repository全体のlock、Ruff、pytest、Markdown、差分形式を確認する | lock 79 packages、Ruff 193 files、pytest 1627 passed / 9 skipped / 1 deselected、Markdown 16 files・1161 links・760 anchors・1452 headings・199 fence pairs、Markdown test 4 passed、diff成功 | dependency取得・model・外部通信なしで共有treeの回帰が成功した |

RED固定時のtest SHA-256は `6d70c936a650b95b56a0e112451b2d64a06bf98116e37b05f3d465e950fc8fa8` である。GREEN後にRuffの機械整形だけを適用したため、最終test SHA-256は `8f3609951be147bac39c37e8f001f8ad18ab21114d44241082bfe117b047fdf7` となった。最終module SHA-256は `bonsai_adapter.py` が `c177516cb182b76dd04dfbb946f369e6fae8cb1e8d3714785e22b8ae04d0bd6e`、`bonsai_request.py` が `ce7a07a2aa19ab94034d9669a418c8f736c234981bcf26701aa97a7efc49ef42` である。

converter検査用の一時fileとC++ helperは終了後に削除した。local Bonsai、使用済みCSV、実provider、商品data、画像、credential、課金、外部network、browser、Windows native、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・変更していない。request v5の実推論結果は未確認であり、再実行には新しい明示承認が必要である。

## 61. 2026-09-05: request v5初回実行とmodel readiness診断

この項目は、[EXEC-047](GOAL.md#exec-047-request-v5-local-bonsai-development-regression) と [FR-401](REQUIREMENTS.md#35-次期検索フロー-v2) に基づく未コミット作業を記録する。利用者へendpoint、固定prompt・完全schema・互換生成schema・検索文だけを含むpayload、逐次4 calls、retry 0、application timeout・生成token上限なし、1 MiB response上限、credentialなし、費用0円、外部networkなし、本文非保持、手動停止を提示し、「実行してよい」と明示承認を得た。

model SHA-256 `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54`、CSV SHA-256 `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea`、生成schema SHA-256 `f557081591fa9d322364e8b65ac0583ee78a0359cd7e1721b659491e1e2fa865` を再照合した。request schema 5.0、4件のbody、非空 `response_format.schema`、`max_tokens` とtimeout不在も送信前に検証した。安全な一時runnerのSHA-256は `f48c24958c3c5632d52ddf75eddf3e92091eff93b8b24690c9d071f7edff3069` である。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| request v5送信前検査 | 固定input、生成schema、body、token・timeout不在を確認する | 4件全て成功。bodyは19,478、19,463、19,467、19,466 bytes | 承認したrequest v5だけを送信対象にした |
| localhost Bonsai 4 requests | 非空生成schemaがstrict intentとrankingまで進めるか確認する | 各0.009、0.010、0.009、0.006秒で `request_failed`。response 0 bytes、completion token不明、retry 0 | 推論、strict intent、typed proposal、rankingへ到達せず、生成schemaの効果は測定できなかった |
| 固定評価・assessment | 推論前の失敗も除外せず集計する | coverage適格、failed 4、ranked 0、元report `not_assessed`、assessment `fail`、53 checks中45件未達 | 評価値0はranking品質ではなく、4件全てが開始前に失敗した結果である |
| llama.cpp source確認 | port listenとmodel readyの順序を確認する | HTTP serverをmodel loadより先に開始し、ready前のendpointを503にする実装を確認 | port listenだけでは送信可能と判断できない |
| 検索文なしのhealth-only再現 | 元4要求を再送せずreadiness原因を確認する | listen直後 `/health` は503、2秒後に200。推論callは0件 | 次回は `/health=200` をchat completions送信前条件にする必要がある |
| server・一時file後処理 | local serviceと生データを残さない | port非listen、`llama-server` processなし、一時runner削除 | 実行用processと一時コードは残っていない |
| 標準offline gate | 実行記録後の共有treeを回帰確認する | lock 79 packages、Ruff check成功・193 files format済み、pytest 1,627 passed / 9 skipped / 1 deselected、Markdown 16 files・1,172 links・771 anchors・1,464 headings・199 fence pairs、diff成功 | dependency取得と追加model推論なしでコード・文書の整合を維持した |

元4要求のHTTP statusとerror本文は保存していないため、個別statusを後から断定しない。applicationで確認できた直接状態は非200系を本文なしの `request_failed` へ変換したことだけである。ただし、合計0.034秒、response・token不在、source上の起動順序、同一条件のhealth再現から、port listenだけをready判定にしたことが失敗原因と判断できる。

安全なdigestはdataset `73951eb4bce8860e016b3a63388002e900802ba2fdeb75e55827cca65d31ba6d`、prediction set `3ccae7a2d52d65597caa9d2727ceec4916892626b00593008654c0b31569c156`、evaluation report `6db0adfcf671fa3834a3d646a531ecb4eea1a572f491da0ebe16fc00aaf378a8`、assessment `0db8e790ffa02ab89bbbcbb757f41d9d575af0acbc82ca79cbd3833bea81e2a3` である。検索文、商品名、商品情報、URL、ASIN相当値、生response、provider error本文は保存・転記していない。Cloudflare、Outscraper、OpenAI、Amazon、画像、credential、課金、外部network、browser、Windows native、外部委託中フロントエンド、AIレビューハーネス、commit、pushも実行していない。

初回4要求は承認済み上限を消費したため、自動再試行しない。次回は `/health=200` を確認してから同じ4件を各1回送る条件を提示し、新しい明示承認を得た場合だけ再開する。

## 62. 2026-09-05: request v5 health-ready再実行と後処理診断

この項目は、[EXEC-047](GOAL.md#exec-047-request-v5-local-bonsai-development-regression) と [FR-401](REQUIREMENTS.md#35-次期検索フロー-v2) に基づく未コミット作業を記録する。初回4要求がmodel ready前に失敗した後、利用者へ同じendpoint、model、CSV、payload、逐次4 calls、retry 0、application timeout・生成token上限なし、credential・費用・外部networkなし、本文非保持、`/health=200` の送信前条件を再提示し、新しい明示承認を得た。

model SHA-256 `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54`、CSV SHA-256 `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea`、生成schema SHA-256 `f557081591fa9d322364e8b65ac0583ee78a0359cd7e1721b659491e1e2fa865` を再照合した。request schema 5.0、4 body、非空 `response_format.schema`、`max_tokens` とtimeout不在を確認した。bodyは19,478、19,463、19,467、19,466 bytes、一時runnerのSHA-256は `27f5ecb63ab6ef351ef53647d6ef091c257a885e5e962ac2220c062a905cf06d` だった。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| request v5送信前検査 | 固定input、生成schema、body、token・timeout不在を再確認する | 4件全て成功 | 承認したrequestだけを対象にした |
| loopback限定llama-serverを起動し `/health` を確認 | model ready前送信を防ぐ | 起動2秒後にHTTP 200 | port listenだけでなくmodel readyを確認してから送信した |
| localhost Bonsai 4 requests | request v5がstrict intentとrankingのどこまで進むか確認する | 全件HTTP 200、`finish_reason=stop`、strict intent成功、retry 0。その後4件とも `postprocess_failed` | 非空生成schemaは旧 `content_not_json` を解消したが、typed rankingは完了していない |
| 固定評価・assessment | 後処理失敗を除外せず集計する | coverage適格、failed 4、ranked 0、元report `not_assessed`、assessment `fail`、53 checks中45件未達 | この `fail` は後処理失敗の投影で、typed条件・商品順位の品質値ではない |
| binding済み合成ready intentによる後処理確認 | modelを再度呼ばず、通常後処理自体が成立するか確認する | proposal、query plan、候補、正解、ranking、予測投影まで成功 | 一時runnerのready経路は決定的fixtureで完走する |
| 合成blocking ambiguity intentによる境界確認 | 一括 `postprocess_failed` になり得る既知経路を確認する | proposalは `blocking`、query plannerは `ValueError` で拒否 | 一時runnerにはこの経路を個別分類できない観測上の欠陥がある。実4件の原因と同一とは断定できない |
| server・一時file後処理 | local serviceと実行用コードを残さない | port非listen、`llama-server` processなし、一時runner削除 | localhost serviceと一時コードは残っていない |
| 標準offline gate | 実行記録後の共有treeを回帰確認する | lock 79 packages、Ruff check成功・193 files format済み、Markdown 16 files・1,174 links・773 anchors・1,467 headings・199 fence pairs、pytest 1,627 passed / 9 skipped / 1 deselected、diff成功 | dependency取得と追加model推論なしでコード・文書の整合を維持した |

4件の所要時間は152.007秒、149.881秒、151.759秒、152.631秒、合計606.278秒だった。completionは146、144、144、143 tokensで合計577、responseは1,189、1,178、1,185、1,186 bytesで合計4,738だった。request digestは順に `9197c2886922ba2ba1154839cf6820a85ef7139ce8f28c0b267bb1d5cfb340a6`、`207f94bd6566a32eb0f6118ed0d111fa0bc04543b5569b5e85f55dc4801ae69f`、`72d31f9df8b8f4e18f1084efaeeccda482f8a4e724ad5d6519ae3ebfab377573`、`b38b9a28f1667dcee825098dba0cffb8bb222956f40a7a3bab06ae016286e823` である。

安全なdigestはdataset `6a0d32e52e9f0a971300bdfd2bdcdb223e7c70badbc6f021fb6e3638c258d8ca`、prediction set `9df834c89e3470f6aa8b98ff8834f109c25418b2de14397dd617f895cd5eb1f2`、evaluation report `43b011d8d9bb0e20612d85bfc2e73f27da2c23b9da8eb0a3b4dfb942527b1243`、assessment `d630babb70c0c8782e860406282deff8d509a1c063b684f8180e0aef6837af86` である。全品質指標は0.000000だが、ranked caseがないため商品順位の良否を表さない。

一時runnerは後処理全体を1つの例外区分へ写像していた。検索文、生response、正規化intent、商品名、商品情報、URL、ASIN相当値、provider error、内部例外本文を保持していないため、実4件の個別失敗段階を後から復元できない。追加model callは行っていない。再推論前に本文非保持の後処理段階診断とblocking投影をofflineで固定し、新しい4 callsが必要なら条件を提示して別の明示承認を得る。Cloudflare、Outscraper、OpenAI、Amazon、画像、credential、課金、外部network、browser、Windows native、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行していない。

## 63. 2026-09-05: holdout後処理段階診断とquery-less blocking投影

この項目は、[EXEC-048](GOAL.md#exec-048-holdout後処理段階診断とquery-less-blocking投影)、[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)、[FR-419](REQUIREMENTS.md#35-次期検索フロー-v2)、[TD-008](ISSUES.md#td-008-為替とランキング品質の評価) に基づく未コミット作業を記録する。EXEC-047で保存しなかった実4件の本文や失敗段階は復元せず、追加model call、CSV再評価、外部通信を行わないoffline TDDとして実施した。

`src/search_v2/holdout_postprocess.py` を追加し、strict intent後の処理をtyped proposal、query plan、typed ranking、prediction projectionへ分けた。失敗時に保持するのは `typed_proposal_invalid`、`query_plan_invalid`、`typed_ranking_invalid`、`prediction_projection_invalid` の固定stageだけである。公開errorは固定messageを使い、検索文、商品情報、provider応答、URL、ASIN相当値、元例外の本文・型・cause・contextを残さない。

`src/search_v2/holdout_evaluation.py` は、上流blocking ambiguityから作られたblocking proposalに限り、query planなしでもintent・proposal digestへ結んだ `blocking` predictionを受理する。ready経路と `ranked` predictionは引き続きquery planを必須とし、既存のquery plan付きblocking、ranked、artifact-free failed prediction、評価report schema 1.0、評価profile、acceptance policy、`quality_decision=not_assessed` は変更していない。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| focused testのRED | 新moduleとquery-less blockingを実装前に要求する | exit 2、`ModuleNotFoundError` で収集停止 | 新しい境界が実装前には存在しないことを確認した |
| focused GREEN | postprocessとholdout projectionを直接検証する | 23 passed | 固定4段階、本文・例外非保持、ready経路、query-less blocking、query-less ranked拒否が成立する |
| typed・holdout関連回帰 | acceptance、adapter、query planner、ranking、orchestratorとの互換性を確認する | 126 passed | 評価・rankingの既存契約を壊していない |
| search v2全体 | 全ての次期検索offline testを確認する | 898 passed、9 skipped | 新しい評価境界を含むv2回帰が成功した。skipは既定で実行しない明示opt-inである |
| 標準offline gate | lock、Ruff、Markdown、offline pytest、diffを確認する | lock 79 packages、Ruff 195 files、Markdown 16 files・1,187 links・786 anchors・1,483 headings・199 fence pairs、pytest 1,635 passed・9 skipped・1 deselected、diff成功 | model推論・外部通信なしで共有tree全体の整合を維持した |
| Python 3.10 AST | 対応構文を新規module・testを含めて確認する | 195 files成功 | Python 3.10実interpreter実行ではないが、対象構文で解析できる |

RED時のtest SHA-256は `tests/test_search_v2_holdout_postprocess.py` が `66f1d813eae8d86b4a9ff6cc38a49b30502167aa94130ac96ff9d43e94a95474`、`tests/test_search_v2_holdout_evaluation.py` が `14578bd0928233e79067a8351a1e5364f95b4c6f66d2cf5e669683c27e66658a` だった。GREEN後は実装 `src/search_v2/holdout_postprocess.py` が `3d1928c6fdb3e38cda3eb3d7c0d1177daba8431c1ee9b563949f0bd9aca887a6`、`src/search_v2/holdout_evaluation.py` が `4bf54b15f541f06ad12c32e846eff55eaa0c20fe8a874ce4a230da2fffd7e460`、新規testが `db4485e28696d913dd952898a562c69776e3dd634fcd83757d4e9d5036a2585e`、更新testが `1b2c82cd0875e38684c2350b873f1c103dc89ce3ae4ec559da4da6e65f6330af` である。評価profile digest `8112ae763f24191cbcc4212cfda7fbdc8133a658ebf6f9f282d735d117237807` とacceptance policy digest `de4b17313dbcbe6bc7e032b36f8a00e59506f49a600e0e0138c748c734073db3` は既存記録と一致した。

この実装で今後の後処理失敗は安全な段階まで分類できるが、この節の時点ではEXEC-047の実4件を再計測していなかった。後続の部分再計測、利用者による実行数訂正、offline修正は次節へ記録する。現行orchestratorもquery planをproposalより先に作るため、上流blocking ambiguityを本番相当の `IntentReview` として返す処理は別のbackend課題として残る。外部委託中フロントエンド、Cloudflare、Outscraper、OpenAI、Amazon、credential、課金、外部network、browser、Windows native、AIレビューハーネス、commit、pushは実行・確認・変更していない。

## 64. 2026-09-05: 段階診断付き部分再計測とBonsai intent検索可能性contract

この項目は、[EXEC-047](GOAL.md#exec-047-request-v5-local-bonsai-development-regression)、[EXEC-049](GOAL.md#exec-049-bonsai-intent検索可能性contract)、[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)、[TD-008](ISSUES.md#td-008-為替とランキング品質の評価) に基づく未コミット作業を記録する。

段階診断付き再計測を開始した際、利用者の承認を「4 caseを各1回」と解釈したが、利用者の意図は「全体で1件だけ」だった。訂正時には2件が完了し、3件目が送信済みだったため直ちに手動中断し、4件目は送信しなかった。訂正後の追加model callは0件である。部分実行からdataset評価またはacceptance assessmentは生成していない。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| request v5送信前検査 | 固定model・CSV・生成schema、body、token・timeout不在、model readinessを確認する | model SHA-256 `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54`、CSV `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea`、生成schema `f557081591fa9d322364e8b65ac0583ee78a0359cd7e1721b659491e1e2fa865`、request schema 5.0、4 body、`max_tokens`・timeout不在、`/health=200` を確認 | 過去と同じmodel・使用済みdata・生成schemaで送信を開始した |
| localhost Bonsaiの部分実行 | 本文非保持diagnosticで後処理の停止段階を確認する | 1件目はHTTP 200、`finish_reason=stop`、146 tokens、1,189 bytes、151.339秒、2件目はHTTP 200、`finish_reason=stop`、144 tokens、1,186 bytes、118.616秒。両方ともstrict intent後の `query_plan_invalid` | JSON・完全schema・正規化までは通過し、query plan段階で止まった。ただし保存していないfield値から直接原因は特定できない |
| 手動中断と後処理 | 利用者が指定した全体1件という境界へ即時に合わせる | 送信済み3件目を応答待ち中に中断し、4件目は未送信。server停止、port 18080非listen、`llama-server` processなし、一時runner削除を確認 | 3件目の応答・token・byte・評価値は確定せず、後続要求は送っていない |
| 検索fieldなしの合成intentをpostprocessへ入力 | 追加model callなしで同じstageを生む契約欠落を切り分ける | 有効typed conditionと非blocking状態でもproposalが `ready` になり、その後 `query_plan_invalid` を再現 | strict schemaは非blocking intentの検索可能性というfield横断条件を保証していなかった。実2件と同一原因とは断定しない |
| Bonsai adapter・prompt focused RED | 非blockingの検索可能性とprompt規則を実装前に固定する | 2 failed、1 passed。空検索fieldが拒否されないこととprompt規則欠落で失敗 | importやfixtureではなく、対象contractが未実装である理由でREDになった |
| 同じfocused GREEN | REDを弱めず最小修正を確認する | 3 passed | 非blockingはquery plan構築成功を必須とし、blocking ambiguityはquery-lessのまま維持できる |
| Bonsai・query・postprocess関連回帰 | downstream互換性と固定失敗境界を確認する | 172 passed | request schema、token・timeout・response上限、query-less blocking、orchestrationの既存契約を壊していない |
| 標準offline gate | repository全体のlock、Ruff、pytest、Markdown、差分形式を確認する | lock 79 packages、Ruff 195 files、pytest 1,638 passed / 9 skipped / 1 deselected、Markdown 16 files・1,201 links・800 anchors・1,499 headings・199 fence pairs、Markdown test 4 passed、diff成功 | dependency取得・外部通信・追加model推論なしで共有treeの回帰が成功した |
| Python 3.10 ASTと実行資源再確認 | 対応構文と一時実行物の不在を確認する | AST 195 files成功。一時runner不在、port非listen、`llama-server` processなし | Python 3.10実interpreter試験ではないが対象構文で解析でき、local実行資源は残っていない |

`bonsai_adapter.py` は非blocking intentを返す前に既存query plannerを呼び、検索不能なresponseを既存の `intent_normalization_invalid` と固定messageへ写像する。promptには、非blocking出力で商品種別または検索語を最低1つ入れ、検索用fieldへURLを入れない規則を追加した。request schema 5.0、完全schema、生成schema、application生成token上限なし、HTTP timeoutなし、response 1 MiB、retry 0は変更していない。promptが変わったためbody・request digestは過去実行と同一ではない。

最終SHA-256は `src/search_v2/bonsai_adapter.py` が `0a418495e27bbb5e1df395c2367fdcf0ddcd523147b43f05bc7f1b240fddec05`、`src/search_v2/bonsai_intent_prompt.txt` が `9477fcc8c4a846a9c6f87ae8410371f8a57f68a7f6dc2599ef015d084561a150`、`tests/test_search_v2_bonsai_adapter.py` が `44290455602b612af096bdf7b01877ddf43c77457d52b90b94a5ecd2bc5b0137`、`tests/test_search_v2_bonsai_request.py` が `90f63f94e2c6794c4ab66ff99b5d153feda4d9b494605163c5d1737d26359ac3` である。

検索文、生response、正規化intent、商品名、商品情報、URL、ASIN相当値、provider error、内部例外本文は保存・転記していない。Cloudflare、Outscraper、OpenAI、Amazon、画像、credential、課金、外部network、browser、Windows native、外部委託中フロントエンド、AIレビューハーネス、commit、pushも実行していない。更新promptをlocal modelで確認する場合は、条件を再提示して新しい明示承認を得た後、使用済みCSVの先頭1 case・合計1 call・retry 0だけを実行し、結果にかかわらず次caseや同一caseを自動実行しない。

## 65. 2026-09-05: 更新promptの1件確認と検索可能性失敗段階の分離

この項目は、[EXEC-050](GOAL.md#exec-050-bonsai検索可能性失敗段階の分離)、[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)、[TD-008](ISSUES.md#td-008-為替とランキング品質の評価) に基づく未コミット作業を記録する。利用者へlocalhost endpoint、payload、全体1 case・1 call、retry 0、application生成token上限・HTTP timeoutなし、response 1 MiB、credential・費用・外部networkなし、本文非保持を提示し、明示承認を得て実施した。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| model・CSV・requestの送信前検査 | 承認済みの固定artifactと1-call条件へ一致することを確認する | model `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54`、CSV `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea`、prompt `9477fcc8c4a846a9c6f87ae8410371f8a57f68a7f6dc2599ef015d084561a150`、生成schema `f557081591fa9d322364e8b65ac0583ee78a0359cd7e1721b659491e1e2fa865`、request schema 5.0、body 19,877 bytes、`max_tokens`・timeout不在を確認 | 固定model、使用済みdata、更新promptの1件だけを送る準備だった |
| 一時runner preflight | model callより前に実行用コードとcall guardを確認する | 初回はrepository import path不足の `ModuleNotFoundError` で停止し、transport call 0 | providerやmodelの失敗ではない送信前設定不備だった。import pathだけを修正して再検証した |
| localhost Bonsai 1件実行 | 更新promptと受理前検索可能性contractを実modelで確認する | `/health=200` 後にHTTP 200、`finish_reason=stop`、143 completion tokens、1,183 response bytes、102.333秒、transport call 1、`intent_normalization_invalid` | envelope、JSON、draft schema後の受理前段階で停止し、後段の `query_plan_invalid` へは進まなかった。実行時のstageだけではnormalizerと検索不能を区別できない |
| 実行数・資源の後処理 | 利用者指定の全体1件を超えずlocal資源を残さない | 2件目・同一case retry・dataset assessmentなし。server停止、port 18080非listen、`llama-server` processなし、一時runner・生成bytecode削除 | 承認済みmodel callは合計1回だけで、追加送信や実行資源は残っていない |
| 原因別diagnostic RED | 正規化失敗と検索不能を本文なしで区別する | 1 failed、1 passed。検索不能が旧 `intent_normalization_invalid` のままで失敗 | 既存stageの粒度不足だけを再現した |
| focused GREEN | 正規化、検索不能、blocking、diagnosticの安全境界を確認する | 4 passed | 検索不能だけを `intent_searchability_invalid` へ分け、固定messageと例外非保持を維持した |
| Bonsai・query・postprocess関連回帰 | request、HTTP、query planner、holdout postprocess、typed adapterとの互換性を確認する | 150 passed | 新stage追加が周辺offline契約を壊していない |
| 標準offline gate | lock、Ruff、Markdown、offline pytest、差分形式を確認する | lock 79 packages、Ruff 195 files、Markdown 16 files・1,211 links・810 anchors・1,512 headings・199 fence pairs、pytest 1,638 passed・9 skipped・1 deselected、Python 3.10 AST 195 files、diff成功 | model再推論と外部通信なしで最終treeの整合を確認した |

1件のcanonical body SHA-256は `eb44d062f665ffb37dbec1c8f5a2ecd41ee491557a156002fab75ab616639588`、request SHA-256は `be5bda07d09c87a371fc1cd77b0cb5680045a447c29e887a225fa77ce791e0aa`、一時runner SHA-256は `aceacb72c982e53c599538b7ddbcc11ee9257d8c5c703c10eb235c7ae76bb61f` だった。一時runnerは削除済みである。旧記録に手入力していたbody `0f9fa3000632cfa7b0a664e2f84f42a3303f09768445d9e5f34b50d2d8f226dc` とrequest `e70570f4cb5690eecf8c4c4dbb578a6ac55210d245e20fd4dee6ec30fe8cbca1` は、固定model・CSV・prompt・生成schemaとcanonical builderから再現できず、EXEC-051の送信前検査で誤記と確認したため訂正した。検索文、生response、正規化intent、商品名、商品情報、URL、ASIN相当値、provider error、内部例外本文は保存・転記していない。

実行時点の `intent_normalization_invalid` はprovenance・normalizerとquery plannerによる検索可能性検査をまとめていたため、直接原因は保存済み情報から断定できない。追加model callなしで `bonsai_adapter.py` を変更し、normalizer側は既存stage、検索不能だけは `intent_searchability_invalid` とした。元例外のcause・contextを残さない既存契約も維持した。RED兼最終test SHA-256は `d449e02fe563957adfdb67a9be8d9a0b4935269198325cd3b95c178344b88ded`、最終moduleは `d04e10319c36a649a82780e7e003aae3cf0069d7df584115b4b447e66c8d89e5` である。

承認済みの1 callは消費済みであり、同じ先頭caseでも再実行には条件の再提示と新しい明示承認が必要である。次回 `intent_normalization_invalid` ならnormalizer契約、`intent_searchability_invalid` ならmodelの検索field生成を修正対象として分ける。これは使用済みdataによるdevelopment regressionであり、独立holdout、typed条件・商品順位の品質、production E2Eを示さない。Cloudflare、Outscraper、Amazon、OpenAI、画像、credential、課金、外部network、browser、Windows native、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・変更していない。

## 66. 2026-09-05: Bonsai生成schema整合とdraft診断

この項目は、[EXEC-051](GOAL.md#exec-051-bonsai生成schema整合とdraft診断)、[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)、[TD-008](ISSUES.md#td-008-為替とランキング品質の評価) に基づく未コミット作業を記録する。利用者へlocalhost endpoint、使用済みCSVの先頭1 case・合計1 call、retry 0、application生成token上限・HTTP timeoutなし、response 1 MiB、credential・費用・外部networkなし、本文非保持を再提示し、明示承認を得て実施した。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| model・CSV・requestの送信前検査 | 承認済みartifactと1-call条件へ一致することを確認する | model `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54`、CSV `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea`、prompt `9477fcc8c4a846a9c6f87ae8410371f8a57f68a7f6dc2599ef015d084561a150`、旧生成schema `f557081591fa9d322364e8b65ac0583ee78a0359cd7e1721b659491e1e2fa865`、body 19,877 bytes、`max_tokens`・timeout不在を確認 | 固定model、使用済みdata、更新promptの先頭1件だけを送る条件だった |
| digest preflight | 手入力固定値をcanonical builderへ照合する | 旧記録由来のbody・request digestが一致せず、transport call 0で停止。canonical bodyは `eb44d062f665ffb37dbec1c8f5a2ecd41ee491557a156002fab75ab616639588`、requestは `be5bda07d09c87a371fc1cd77b0cb5680045a447c29e887a225fa77ce791e0aa` | modelやproviderではなく記録値の誤りだった。不一致requestは送信していない |
| localhost Bonsai 1件実行 | EXEC-050後の失敗段階を固定条件で確認する | `/health=200` 後にHTTP 200、`finish_reason=stop`、257 completion tokens、1,613 response bytes、117.242秒、transport call 1、`draft_schema_invalid` | envelopeとcontent JSONまでは通ったが、完全draft schemaで停止した。正規化・検索可能性・typed proposal・rankingには到達していない |
| 実行数・資源の後処理 | 全体1件を超えずlocal資源を残さない | 2件目・同一case retry・dataset assessmentなし。server停止、port 18080非listen、`llama-server` processなし、一時runner・生成bytecode削除 | 承認済みmodel callは合計1回だけで、追加送信や実行資源は残っていない |
| 生成schema・診断RED | 既知のschema差分と本文非保持groupを実装前に固定する | 10 failed | regex除外、価格field横断条件の欠落、draft違反group未実装という対象理由で失敗した |
| focused GREEN | Bonsai adapter・requestの全testを実行する | 85 passed | strict parserを緩めず、互換regex、価格9 variant、固定違反groupを実装できた |
| Bonsai・後段関連回帰 | HTTP、query planner、holdout postprocess、typed adapter、orchestrator、historyとの互換性を確認する | 185 passed | requestと後段bindingの既存offline契約を維持した |
| schema互換検査 | 新生成schemaをllama.cpp同梱Python converterとDraft 2020-12 validatorへ入力する | converter終了0、正fixture 0 errors、価格矛盾・不正decimal・不正ambiguity codeは各1 error | 既知の生成時制約を表現できる。local modelが新schemaで成功することはまだ示さない |
| 標準offline gate | lock、Ruff、Markdown、offline pytest、Python 3.10構文、差分形式を確認する | lock 79 packages、Ruff 195 files、Markdown 16 files・1,221 links・820 anchors・1,524 headings・199 fence pairs、pytest 1,642 passed・9 skipped・1 deselected、AST 195 files、diff成功 | 追加model call・依存取得・外部通信なしで最終treeの整合を確認した |

実modelの直接違反fieldは断定しない。生responseを保持しておらず、実行時点には `draft_failure_group` も存在しなかったためである。追加推論なしで、ambiguity codeのregexを保持し、decimal regexだけを同値のllama.cpp互換表現へ置換した。価格はexact・range・min・maxのexplicit/inferredとnoneを9つの排他的variantへした。生成schemaは11,051 bytes、SHA-256 `c8537ff3ee378b0ef57d41889210e1a807962d2cbd1ab8772020706481a58ca6` である。完全schemaの最終検証、request schema 5.0、application生成token上限なし、HTTP timeoutなし、response 1 MiB、1 call、retry 0は維持する。

最終SHA-256は `src/search_v2/bonsai_adapter.py` が `2a0284b6bb2f30c0c740aded2535008ec901472c8a9e0e75ce004da48768eff4`、`src/search_v2/bonsai_request.py` が `87244ec4c124a94e04051a322f299d9cc63e3eea32f98cc1eac0f731716c875b`、`tests/test_search_v2_bonsai_adapter.py` が `484e102949cc119cafb975d8572c0d7abd7a6d3d0c84b854dd798962f67856b0`、`tests/test_search_v2_bonsai_request.py` が `b6a68fbbde05327a4113cc39a678162eb73e548edba495db4ff118a9e2dc9e4c` である。

`draft_schema_invalid` のdiagnosticには、Pydantic error locationから導く `document`、`fields`、`price`、`typed_conditions`、`ambiguities`、`multiple` の固定groupだけを追加した。field値、検索文、validation message、error input・context、provider本文は保持しない。実行済みresponseを新groupへ事後分類しておらず、新生成schemaでのmodel確認も行っていない。

次に新生成schemaで同じ先頭caseを1 callだけ確認する場合も、endpoint、payload、回数、credential、費用、保存範囲を再提示して新しい明示承認を得る。新しいCSV、画像、APIキーは不要である。この使用済みdataはdevelopment regression専用で、未知データの独立holdout評価とは分ける。Cloudflare、Outscraper、Amazon、OpenAI、画像、credential、課金、外部network、browser、Windows native、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・変更していない。

## 67. 2026-09-05: 新生成schemaの1件確認と生成時検索可能性制約

この項目は、[EXEC-052](GOAL.md#exec-052-新生成schemaのlocalhost-1件確認)、[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)、[TD-008](ISSUES.md#td-008-為替とランキング品質の評価) に基づく未コミット作業を記録する。利用者へlocalhost endpoint、固定model、更新prompt、完全schema、EXEC-051の生成schema、使用済みCSVの先頭1 case、合計1 call、retry 0、application生成token上限・HTTP timeoutなし、response 1 MiB、credential・費用・外部networkなし、本文非保持を再提示し、明示承認を得て実施した。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| model・CSV・requestの送信前検査 | 承認済みartifactと1-call条件へ一致することを確認する | model `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54`、CSV `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea`、prompt `9477fcc8c4a846a9c6f87ae8410371f8a57f68a7f6dc2599ef015d084561a150`、完全schema 7,352 bytes・`f6650c439794aface4d3b2b98227c32d8123ea9349db2ca3ad82dab7eedfb88c`、生成schema 11,051 bytes・`c8537ff3ee378b0ef57d41889210e1a807962d2cbd1ab8772020706481a58ca6`、body 23,725 bytes・`4d2d6e5b3abc59f996a74d0b40f80c14e731a8e77acbaa8410323913cd20bc2b`、request `6bdaa64071b867d421a2c07830d1fb4c1c675e23ff7f4825a24fe7014edb29c8`、`max_tokens`・timeout不在を確認 | 固定modelと使用済みdataの先頭1件だけを送る条件だった |
| 一時runner preflight | model callより前に実行用コード、digest、call guardを確認する | runner SHA-256 `ec2c98747d7d117884d4a2488c861074a54769b291f709718ca5e3f067be4dab`。初回はrepository import path不足の `ModuleNotFoundError` で停止し、transport call 0。`PYTHONPATH` をrepository直下へ固定すると全検査成功 | 初回停止はmodel・provider・schemaではなく送信前設定の不備で、不一致requestを送っていない |
| localhost Bonsai 1件実行 | EXEC-051の生成schemaが実応答を完全schemaと正規化へ通せるか確認する | `/health=200` 後にHTTP 200、`finish_reason=stop`、143 completion tokens、1,187 response bytes、252.845秒、transport call 1、retry 0、`intent_searchability_invalid` | EXEC-051の `draft_schema_invalid` はこのcaseで解消し、生成schema、envelope、content JSON、完全draft schema、正規化を通過した。非blocking query構築で停止し、typed proposal・rankingへは到達していない |
| 実行数・資源の後処理 | 全体1件を超えずlocal資源を残さない | 2件目・同一case retry・dataset assessmentなし。server停止、port 18080非listen、`llama-server` processなし、一時runner・生成bytecode削除 | 承認済みmodel callは合計1回だけで、追加送信や実行資源は残っていない |
| 生成時検索可能性・診断RED | 通常の商品種別またはblocking確認待ちと安全な検索可能性groupを実装前に固定する | test SHA-256はadapter `b9af88eeb92c888eb392c4afea7202a37bd819141ac100f219557ae09df30347`、request `b9c40d8577832dc2b269589a4177c95f16c551b094b2eba16edcea4f5393cb68`。11 failed、76 passed | schema分岐、prompt規則、diagnostic fieldが未実装という対象理由でREDになった |
| focused GREEN | Bonsai adapter・requestの全testを実行する | 87 passed | 通常商品、検索語なし拒否、blocking確認待ち、非blocking ambiguity拒否、固定groupを確認した |
| Bonsai・後段関連回帰 | HTTP、query planner、holdout postprocess、typed adapter、orchestrator、historyとの互換性を確認する | 187 passed | strict受理と後段bindingの既存offline契約を維持した |
| schema互換検査 | 次schemaをllama.cpp同梱Python converterとDraft 2020-12 validatorへ入力する | 16,663 bytes、SHA-256 `2e5cfed749d4f71898c42226c58e3f838664cac0e66f1c3230e54daf384f004d`、converter終了0、schema valid | 通常の商品種別または全blocking確認待ちをconverterで表現できる。実model成功はまだ示さない |
| 標準offline gate | lock、Ruff、Markdown、offline pytest、Python 3.10構文、差分形式を確認する | lock 79 packages、Ruff 195 files、Markdown 16 files・1,231 links・830 anchors・1,536 headings・199 fence pairs、pytest 1,644 passed・9 skipped・1 deselected、AST 195 files、diff成功 | 追加model call・依存取得・外部通信なしで最終treeの整合を確認した |

生responseと正規化fieldを保持していないため、検索fieldが全て空だったか、URL等の不正値があったかは断定しない。実行時点のdiagnosticにも内訳groupがなかったため、過去responseを事後分類していない。

追加model callなしで、生成schemaを完全objectの2分岐へ更新した。通常分岐は `product_name_ja` に日本語の商品種別を必須とし、商品種別を安全に確定できない分岐は1件以上のambiguityを全てblockingにする。検索不能時のdiagnosticは、正規化済み値を保持せず `missing_terms` または `invalid_terms` の固定groupだけを持つ。完全schemaとquery plannerによる最終検証、blocking ambiguityのquery-less投影、request schema 5.0、application生成token上限なし、HTTP timeoutなし、response 1 MiB、1 call、retry 0は維持する。

最終SHA-256は `src/search_v2/bonsai_adapter.py` が `dccfed18908cda7fe0b839f9ae193431bad2ae20d27947163edce32cf29c6b57`、`src/search_v2/bonsai_request.py` が `4b88031a760b1d87efd2b851d249720c25d83c846ba468364621bf0a085d32ef`、`src/search_v2/bonsai_intent_prompt.txt` が `459f4a7bc3ecbb93664b4973b00cec31de4665a5cd61762bf84c6ad51779859d`、RED兼最終 `tests/test_search_v2_bonsai_adapter.py` が `b9af88eeb92c888eb392c4afea7202a37bd819141ac100f219557ae09df30347`、最終 `tests/test_search_v2_bonsai_request.py` が `b212a9aea188b32f6ab4856a185789f0ea35b1a35feed74743a04f4d1cac7ecd` である。次のcanonical bodyは29,320 bytes・SHA-256 `5754a3b00ca2be0fe909a1d3fb9079ddbfa45729c9a3d692f44b172e7744a6b6`、requestはSHA-256 `9701a1d930dfe6c7b5971fb03a76587dcb7fa57a293f47175cbb70438f237f1e` だが、どちらも未送信である。

検索文、生response、正規化intent、商品情報、URL、ASIN相当値、provider error、validation本文は保存・転記していない。Cloudflare、Outscraper、Amazon、OpenAI、画像、credential、課金、外部network、browser、Windows native、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・変更していない。次schemaを同じ先頭caseで確認する場合も、endpoint、payload、回数、credential、費用、保存範囲を再提示して新しい明示承認を得る。新しいCSV、画像、APIキーは不要である。

## 68. 2026-09-05: 生成時検索可能性schemaの1件確認

この項目は、[EXEC-053](GOAL.md#exec-053-生成時検索可能性schemaのlocalhost-1件確認)、[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)、[TD-008](ISSUES.md#td-008-為替とランキング品質の評価) に基づく未コミット作業を記録する。利用者へlocalhost endpoint、固定model、更新prompt、完全schema、16,663 bytesの生成schema、使用済みCSVの先頭1 case、合計1 call、retry 0、application生成token上限・HTTP timeoutなし、response 1 MiB、credential・費用・外部networkなし、本文非保持を再提示し、明示承認を得て実施した。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| model・CSV・requestの送信前検査 | 承認済みartifactと1-call条件へ一致することを確認する | model `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54`、CSV `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea`、prompt `459f4a7bc3ecbb93664b4973b00cec31de4665a5cd61762bf84c6ad51779859d`、完全schema 7,352 bytes・`f6650c439794aface4d3b2b98227c32d8123ea9349db2ca3ad82dab7eedfb88c`、生成schema 16,663 bytes・`2e5cfed749d4f71898c42226c58e3f838664cac0e66f1c3230e54daf384f004d`、body 29,320 bytes・`5754a3b00ca2be0fe909a1d3fb9079ddbfa45729c9a3d692f44b172e7744a6b6`、request `9701a1d930dfe6c7b5971fb03a76587dcb7fa57a293f47175cbb70438f237f1e`、`max_tokens`・timeout不在を確認 | 固定modelと使用済みdataの先頭1件だけを送る条件だった |
| 一時runner preflight | model callより前に実行用コード、digest、call guardを確認する | runner SHA-256 `196639692c05b0b6e80fd4126562af53e1041fd0d7564ee9d76b9ef020abbf57`、transport call 0で全検査成功 | modelへ送る前に固定条件と本文非表示の出力境界を確認できた |
| localhost Bonsai 1件実行 | 生成時検索可能性schemaが実応答をstrict intentとtyped proposalへ通せるか確認する | `/health=200` 後にHTTP 200、`finish_reason=stop`、473 completion tokens、2,508 response bytes、395.713秒、transport call 1、retry 0、usage `succeeded` | 生成schema、envelope、content JSON、完全draft schema、正規化、adapter受理を通過した |
| typed proposal生成 | 受理済みintentを固定registryのadapterへ渡す | proposal status `blocking`、response stage・draft failure group・searchability failure groupは全て `not_applicable` | typed proposalは生成できたが、商品取得・rankingへ進まず利用者確認が必要な状態だった。本文非保持のため理由は断定しない |
| 実行数・資源の後処理 | 全体1件を超えずlocal資源を残さない | 2件目・同一case retry・dataset assessment・商品取得・rankingなし。server停止、port 18080非listen、`llama-server` processなし、一時runner・生成bytecode削除 | 承認済みmodel callは合計1回だけで、追加送信や実行資源は残っていない |
| focused regression | Bonsai adapter・requestの全testを実行する | 87 passed | 現行schema、strict受理、固定diagnostic契約を維持した |
| Bonsai・後段関連回帰 | HTTP、query planner、holdout postprocess、typed adapter、orchestrator、historyとの互換性を確認する | 187 passed | 実行後にsourceを変更せず、関連offline契約が成功した |
| orchestrator source確認 | blocking proposalを本番相当の第1確認へ返せるか確認する | `start_intent_review()` はquery planをtyped proposalより先に作り、`IntentReview` はquery planとready proposalを必須にする | 今回のquery-less blockingを第1確認へ返し、後続providerを止める接続が次のoffline backend作業である |
| 標準offline gate | lock、Ruff、Markdown、offline pytest、Python 3.10文法、差分形式を確認する | lock 79 packages、Ruff 195 files、Markdown 16 files・1,241 links・840 anchors・1,549 headings・199 fence pairs、pytest 1,644 passed・9 skipped・1 deselected、AST 195 files、diff成功 | 追加model call・依存取得・外部通信なしで最終treeの整合を確認した |

検索文、生response、正規化intent、typed condition、ambiguity、issue本文を保存していないため、blockingが上流ambiguity、未知attribute、値・演算子不整合等のどれに由来したかは断定しない。追加model callで原因を探らず、次はquery-less blockingの確認state、承認禁止、Cloudflare・Outscraper非呼出しを別Planでoffline TDDする。新しいCSV、画像、APIキー、model call承認は不要である。

Cloudflare、Outscraper、Amazon、OpenAI、画像、credential、課金、外部network、browser、Windows native、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・変更していない。

## 69. 2026-09-05: query-less blockingの第1確認接続

この項目は、[EXEC-054](GOAL.md#exec-054-query-less-blockingの第1確認接続)、[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)、[TD-008](ISSUES.md#td-008-為替とランキング品質の評価) に基づく未コミット作業を記録する。EXEC-053で得たblocking proposalを追加model callなしで扱い、queryを要求せず利用者の第1確認へ返して後続providerを予約前に止めるoffline backend境界をTDDした。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| query-less blocking受入RED | 実装前に、商品種別・検索語を持たないblocking intent、query digest相互制約、後続provider guardを固定する | 新規4件は3 failed・1 passed。orchestrator 2件はblockingをquery plannerが拒否し、state 1件はqueryなしをmodel validationが拒否した。test SHA-256はorchestrator `1280510f64e2412c299cf7a83547213c62b8fe4e408a357eb9bc467ff42684f2`、state `a62e710622c67a1f0c565dc2db433a9010171d891bae09bb0e0bdcc8be5c3947` | 現行のquery先行順序とquery必須snapshotが対象理由だった。readyのqueryなし拒否1件は実装前から成功した |
| focused GREEN | 専用blocking確認、canonical state、ready互換、後続provider非呼出しを確認する | 新規4 passed、orchestrator・state全体39 passed | blockingはquery plan・query digestなしで第1確認へ到達し、画像生成と画像なし続行は追加予約・transport前に拒否される。readyはquery必須のままである |
| 関連回帰 | typed adapter、query planner、approval、Cloudflare・Outscraper request・HTTP、product pipeline、history、holdout後処理との互換性を確認する | 235 passed | query必須の実行可能経路とquery-less blocking評価投影を維持した |
| source・test digest | 最終artifactを識別する | orchestrator `aedf45afe023502424ba84d635cf8e654480b83bf0b1b122fdd709c215f4bfe9`、state machine `73a211cd4a9432b533f7e91fa766cfdfa28f069007d1e8352c14c73b78559e81`。test digestはREDから不変 | production変更だけでREDをGREENにし、受入test自体を弱めていない |
| 標準offline gate | lock、Ruff、Markdown、offline pytest、Python 3.10文法、差分形式を確認する | lock 79 packages、Ruff 195 files、Markdown 16 files・1,256 links・855 anchors・1,565 headings・199 fence pairs、pytest 1,648 passed・9 skipped・1 deselected、AST 195 files、diff成功 | 追加model call・依存取得・外部通信なしで、文書を含む最終treeの整合を確認した |

`start_intent_review()` はtyped proposalをqueryより先に作る。`ready` の場合だけ既存query plannerを呼び、従来の `IntentReview` を返す。`blocking` はquery fieldを持たないstrict・frozenな `BlockingIntentReview` と、intent・proposal digest、status、成功済みBonsai利用量だけへ結んだquery-less snapshotを返す。query付きblocking、queryなしready、status・digest・artifact改ざん、非canonical stateは拒否する。

blocking確認を `generate_images()` または `skip_images()` へ渡した場合、Cloudflare・Outscraperの利用量予約とtransport callより前に固定errorで停止する。画像なし続行が作れないため、検索承認・商品取得・rankingにも到達しない。確認contractは第1確認に必要な既存intent・proposalを保持するが、source input、生response、商品情報、provider error本文を追加していない。sessionと固定errorにはambiguity messageを含む本文を複製していない。

実Bonsaiの追加call、使用済みCSVの再評価、未知データ、Cloudflare、Outscraper、Amazon、OpenAI、credential、課金、画像、Windows native、browser、外部委託中フロントエンド、AIレビューハーネス、commit、pushは実行・確認・変更していない。次は既存development dataを除外した未知データで独立評価を行うか判断し、実施する場合だけ固定policyを満たす新しい非機密dataを用意する。

## 70. 2026-09-05: query-less blocking第1確認のlocalhost 1件結合確認

この項目は、[EXEC-055](GOAL.md#exec-055-query-less-blocking第1確認のlocalhost-1件結合確認)、[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2)、[TD-008](ISSUES.md#td-008-為替とランキング品質の評価) に基づく未コミット作業を記録する。利用者へlocalhost endpoint、固定model、prompt・両schema・検索文だけを含むpayload、使用済みCSVの先頭1件・合計1 call、retry 0、application生成token上限・HTTP timeoutなし、response 1 MiB、credential・費用・外部networkなし、本文非保持、商品取得・rankingなしを再提示し、明示承認を得て実施した。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| 一時runnerの初回preflight | model call前に固定artifact、request、call guard、port・process状態を検査する | file pathで直接起動したため `ModuleNotFoundError: No module named 'src'` で停止。server起動・model callは0件 | repository rootをimport pathへ明示する必要があり、失敗は外部処理開始前だった |
| `PYTHONPATH=.` を付けたpreflight | import条件を修正し、同じ固定条件を再検査する | CSV 12 rows・4 unique cases・先頭 `mouse-01`、全digest、request schema 5.0、`max_tokens`・timeout不在、response 1 MiB、call guard、port非listen、対象process不在を確認 | 送信対象と回数を変更せず、安全な送信前条件を満たした |
| 最初のserver起動command | loopback限定serverを起動する | command内の `rm -f` を実行環境の安全filterが拒否し、command自体は未実行 | server・model callは開始しておらず、削除操作を含まない起動へ分離できる |
| 削除操作なしの `llama-server` 起動と `/health` 検査 | modelが要求受付可能になってからexact 1 callを許可する | `127.0.0.1:18080`、context 8192、parallel 1、CPU、offline、log・prompt cache・UI無効で起動し、最初のhealth検査でHTTP 200 | port listenだけでなくmodel readyを送信前条件にできた |
| `PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 uv run --frozen --offline --no-sync python tools/.exec055_runner.py run` | 使用済みCSVの先頭1件を現行 `start_intent_review()` へ1回だけ通す | 233.419秒、HTTP 200、2,508 bytes、transport call 1、Bonsai利用量 `succeeded`。session `intent_review`、typed status `blocking`、review `BlockingIntentReview`、query plan・query digestなし | local model実応答がstrict intent・typed proposalを通り、query-less blocking専用第1確認へ到達した。商品検索・順位品質の成功は示さない |
| 実行数と資源の後処理 | 承認範囲を超えずlocal資源を残さない | 2件目・同一case retry・assessment・Cloudflare・Outscraper予約・call・商品取得・rankingなし。server停止、port非listen、対象process、一時runner、一時directory不在 | 承認済みmodel callは1回だけで、後続providerと実行資源は残っていない |
| 関連offline回帰 | 実行した結合経路と既存契約を確認する | Bonsai adapter・request・HTTP、typed adapter、query planner、orchestrator、state、holdout後処理が195 passed | sourceを変更せず、query-less blockingと周辺のoffline契約を維持した |
| 標準offline gate | lock、Ruff、Markdown、offline pytest、Python 3.10文法、差分形式を確認する | lock 79 packages、Ruff 195 files、Markdown 16 files・1,266 links・865 anchors・1,580 headings・199 fence pairs、pytest 1,648 passed・9 skipped・1 deselected、AST 195 files、diff成功 | 文書同期後のtreeを追加model call・依存取得・外部通信なしで確認した |

送信時の一時runner SHA-256は `c9547f7c9f5b180d9bc396d501d7676dcffa52e11ec77d486c2f2a549a85c9a9` である。CSVは `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea`、modelは `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54`、server binaryは `71b0c2554c375071855547f5da7ef2fc5c34766f6fcd6fab194ce93a18a59e0a`、promptは `459f4a7bc3ecbb93664b4973b00cec31de4665a5cd61762bf84c6ad51779859d`、完全schemaは `f6650c439794aface4d3b2b98227c32d8123ea9349db2ca3ad82dab7eedfb88c`、生成schemaは `2e5cfed749d4f71898c42226c58e3f838664cac0e66f1c3230e54daf384f004d`、bodyは `5754a3b00ca2be0fe909a1d3fb9079ddbfa45729c9a3d692f44b172e7744a6b6`、requestは `9701a1d930dfe6c7b5971fb03a76587dcb7fa57a293f47175cbb70438f237f1e`、orchestratorは `aedf45afe023502424ba84d635cf8e654480b83bf0b1b122fdd709c215f4bfe9` だった。一時runnerは実行後に削除した。

検索文、生response、正規化intent、typed condition、ambiguity・issue本文、商品情報は保存していないため、blockingの直接理由と妥当性は断定しない。これは同じ使用済みdataによるdevelopment regressionであり、独立holdout、未知データへの一般化、条件分解・商品順位品質、production E2Eとして扱わない。

## 71. 2026-09-05: 未知データによる独立評価を実施しない判断

この項目は、[TASK-005](GOAL.md#task-005-ランキング品質評価の確立)、[EXEC-055](GOAL.md#exec-055-query-less-blocking第1確認のlocalhost-1件結合確認)、[TD-008](ISSUES.md#td-008-為替とランキング品質の評価) に関する利用者判断を記録する。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| 利用者判断の確認 | EXEC-055後に提示した未知データによる独立評価を実施するか確定する | 利用者が「実施しない」と明示した | 新しい評価data、追加model call、dataset assessmentは用意・実行しない |
| 正本文書の更新 | 未完の判断待ちを残さず、品質主張と再開条件を揃える | GOAL、BACKEND、REQUIREMENTS、ISSUES、NEXT-STEPS、WORKLOG、CHANGELOGへ反映 | fixed policyの `pass` は未確認、typed ranking品質は未確認、画像rankingは無効のままである |
| 文書検査 | 現行Markdownのlocal link、anchor、fence、差分形式を確認する | Markdown 16 files・1,270 links・869 anchors・1,582 headings・199 fence pairs、Markdown test 4 passed、`git diff --check` 成功 | 外部通信、model call、依存取得を伴わず判断記録の整合を確認した |

この判断は既存の評価contract、固定policy、development dataを削除または変更しない。将来再開する場合は、利用者の新しい明示判断と、case1〜case3および使用済みCSVを除外した固定policy適格dataを必要とする。品質未確認の状態を `pass` またはproduction利用可能へ読み替えない。

## 72. 2026-09-05: ローカル単独利用向け検索job基盤

この項目は、[TASK-001](GOAL.md#task-001-検索処理のジョブ化)、[EXEC-056](GOAL.md#exec-056-ローカル単独利用向け検索ジョブ基盤)、[TD-001](ISSUES.md#td-001-同期的な検索実行) に基づく未コミット作業を記録する。利用者の「ローカル専用」という判断に従い、単一host・単一process・worker 1本のbackend job境界だけを実装した。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| 公開APIだけのscaffoldに対する `pytest -q tests/test_search_v2_search_job.py` | 実装前にjob状態、重複投入、同時実行、取消、開始期限、再起動、保持、安全な保存境界を固定する | 終了1、13 failed。全件が期待した `NotImplementedError`。受入test SHA-256は `e1cbf9138140d92051cb338fc23cddbd18c47ba405f40c6615b7a1b868ea60dc` | 新moduleの実装なしでは受入条件を満たさない有効なREDを確認した |
| focused GREEN | strict・frozen model、SQLite repository、単一worker executorを実装して同じ受入境界を確認する | 13 passed。production SHA-256は `21ae58994002b8a31958848a3a3b4a56cc872afabc08efcba54ebeaf13b204ff`、最終test SHA-256は `572c49dd05b5f9871823cb6ff3c94037d73c47de74415721ca48094568a21e80` | 固定local owner、owner・binding冪等性、FIFO同時実行1件、状態照会、queued取消、running協調取消、取消後結果破棄、24時間の開始期限、再起動時の固定終端、30日purge、固定error、本文非保持をofflineで再現できる |
| `pytest -q tests/test_search_v2_*.py` | 既存の次期検索domainとの回帰を確認する | 924 passed、9 skipped | job moduleの追加後も既存v2境界は維持された |
| 標準offline gate | lock、Ruff check/format、Markdown、offline pytest、Python 3.10構文、差分形式を確認する | lock 79 packages、Ruff 197 files、offline pytest 1,661 passed・9 skipped・1 deselected、Python 3.10 AST 197 files、Markdownと `git diff --check` 成功 | 依存取得と外部通信なしで、コードと現行文書の整合を確認した |

job DBには固定 `local-user`、random locator、approval runtime binding digest、状態、時刻、固定失敗code、成功結果のlocatorだけを保存する。検索文、商品、画像、approval token、API key、provider URL・要求・応答、callback、例外本文は保存しない。同じbindingを再投入しても別callbackを起動せず、自動retryもしない。開始済みcallbackへruntime timeoutは追加せず、取消は協調方式とする。

30日保持testの初期fixtureは30日後までqueued jobを残しており、24時間の開始期限と矛盾した。対象を開始済みactive jobへ訂正し、期限削除が終了jobだけへ作用する受入意図を維持した。件数照会もowner必須へ揃えた。

現行Streamlit、外部委託中フロントエンド、実検索callback、実Bonsai・Cloudflare・Outscraper・Amazon・OpenAI、credential、外部通信、課金、browser、commit、pushは実行・確認・変更していない。TASK-001には実検索・履歴locator・利用者向け状態表示と取消操作への接続が残り、フロントエンド納品完了が明示されるまで保留する。

## 73. 2026-09-06: Bonsai本番prompt cacheとrequest context縮小

この項目は、[EXEC-057](GOAL.md#exec-057-bonsai本番prompt-cacheとrequest-context縮小) と [FR-401](REQUIREMENTS.md#35-次期検索フロー-v2) に基づく未コミット作業を記録する。利用者指定に従い、本番Bonsai起動例のprompt cache明示、request schema二重送信の除去、4,096 contextの適合性確認を行った。Vulkan版buildは現行build完成後の別工程とし、実model生成、外部API、credential、課金、browser、外部委託中フロントエンドは実行・確認していない。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| 変更後の期待を固定した `pytest -q tests/test_search_v2_bonsai_request.py` | system messageをpromptだけにし、request schemaを6.0へ更新する受入条件を実装前に固定する | 終了1、2 failed・44 passed。受入test SHA-256は `6bac4ef9005918a61da20ce4ce76eb4fe54813aacc32e04dfbf9006862fc1b48` | 旧5.0と完全schema連結が対象理由で失敗する有効なREDだった |
| request v6のfocused GREEN | 完全schema本文のsystem message連結だけを除去し、生成schema、両schema digest、strict最終検証を維持する | 46 passed | system messageは固定promptだけ、`response_format.schema` は非空、旧5.0は拒否され、body・digest改ざん防止を維持した |
| local `llama-tokenize` version 9294による生成なしの集計 | 4,096 contextが現行の最大2,000 codepoint入力契約を満たすか確認する | 固定prompt 883 tokens、通常日本語2,000 tokens、validationを通る最大長合成入力4,000 tokens。後者とpromptだけで4,883 tokens | chat template overheadと生成領域の前から4,096を超えるため、入力契約を変えずにcontextを4,096へ下げられない |
| canonical requestのoffline集計 | schema二重送信除去後のrequest構造と縮小量を確認する | schema 6.0、合成fixture body 20,716 bytes、system message 3,772 bytes、完全schema 7,352 bytes、生成schema 16,663 bytes。model入力から完全schema 2,000 tokensを除去 | 生成schemaは `response_format` に維持しつつ、完全schema本文の重複だけをmodel入力から除けた |
| README本番起動例の更新 | prompt cache、context、parallel数、disk保存境界を運用値として明示する | `--cache-prompt -c 8192 -np 1` を両起動例へ追加し、`--slot-save-path` は設定しない | 同一processの固定prefixを再利用し、slotをdiskへ永続化しない本番起動条件を再現できる |
| Bonsai関連回帰と次期検索全体 | request、HTTP、adapter、orchestratorと全v2境界を確認する | 関連141 passed。全v2は924 passed・9 skipped | request v6変更後も既存の送信・strict応答・offline orchestration境界を維持した |
| 標準offline gate | lock、Ruff check/format、Markdown、offline pytest、Python 3.10構文、差分形式を確認する | lock 79 packages、Ruff 197 files、Markdown 16 files・1,278 links・877 anchors・1,612 headings・199 fence pairs、offline pytest 1,661 passed・9 skipped・1 deselected、Python 3.10 AST 197 files、`git diff --check` 成功 | 依存取得と外部通信なしでコード・test・現行文書の整合を確認した |

完全schemaはmodel inputから外したが、`schema_sha256`、request digest、adapterのstrict Pydantic検証からは外していない。旧request schema 5.0は現行6.0へ暗黙変換せず拒否する。本番prompt cacheはmemory上に入力由来状態を残し得るため、loopback bind、単一slot、同一OS userの信頼境界を維持し、server process終了を破棄境界にする。

この時点ではrequest v6の実Bonsai成功、Core Ultra実機の応答時間、prompt cache hit率、4,096での実生成、Vulkan版buildを確認していなかった。後続の限定速度比較は次節へ記録する。Vulkan対応は現行build版の完成後に、backend・quantization互換性と同一入力の速度・品質を別Planで比較する。

## 74. 2026-09-06: request v6とprompt cacheのlocalhost速度比較

利用者へ送信先、payload、回数・上限、credential、費用、保存範囲を提示し、「実行してよい」と明示承認を得た。対象は `http://127.0.0.1:18080/v1/chat/completions`、local Bonsai model、非機密の合成検索文4件、変更前相当と変更後を各warm-up 1回＋計測3回の合計最大8 attempts、各出力1 token、300秒/call、retry 0、response 1 MiBである。credential、外部network、費用はなく、応答本文を保存せずtimingとtoken集計だけを記録する。Vulkan buildは対象外とした。

実行環境はWindows上のWSL2、13th Gen Intel Core i5-13600KF、20 logical CPUs、CPU版 `llama-server` version 9294（`0f3cb3fc8`）である。server binary SHA-256は `71b0c2554c375071855547f5da7ef2fc5c34766f6fcd6fab194ce93a18a59e0a`、Bonsai model SHA-256は `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54` だった。両条件ともcontext 8,192、parallel 1、GPU layer 0、offline、loopback bind、Web UI・log無効、temperature 0、`max_tokens=1` を固定した。

| 条件 | 完了した計測 | wall time | prompt処理 | prompt/cache tokens | request bytes |
|---|---:|---:|---:|---:|---:|
| 変更前相当: 固定prompt＋完全schema、生成schema、`--no-cache-prompt` | warm-up 1＋有効2 | warm-up 144.863秒、有効2件139.854・145.264秒、中央値142.559秒 | 中央値142.525秒 | prompt中央値2,925.5、cache 0 | 中央値29,341 |
| 変更後: request v6 prompt-only、生成schema、`--cache-prompt` | warm-up 1＋有効3 | cold 40.715秒、warm 0.818・1.236・1.369秒、中央値1.236秒 | warm中央値1.208秒 | 処理中央値18、cache中央値895 | 中央値20,706 |

warm状態の合成比較ではwall timeが約115.3倍、99.13%短縮し、prompt処理は約118.0倍、99.15%短縮した。変更後warm requestはprompt全体の中央値約98.03%をcacheから再利用した。cacheが空の単一比較でも144.863秒から40.715秒へ約3.56倍、71.89%短縮し、schema除去後のprompt tokenは2,928から913へ68.82%減った。request byte中央値は29,341から20,706へ29.43%減った。

変更前の3件目はPython出力がbufferされていたため進捗を誤認し、client側から手動中断した。server側の処理終了を待ち、同一callをretryせず、承認された変更前4 attemptsの最後の1件だけを実行した。このため変更前の有効計測は2件であり、中央値の確度は変更後3件より低い。変更後はunbuffered集計で4件全て完了した。全体で8 attemptsを超えていない。

この比較は1-token出力によりprompt prefillとcache再利用を主に測る。production requestはapplication側の `max_tokens` を持たず、full JSONのdecode時間は別に加算されるため、実検索全体が115倍になるとは結論しない。strict intent成功、条件分解・ranking品質、Core Ultra 9 288V、長いcompletion、production E2Eは未確認である。実行後は両serverを停止し、`llama-server` processなし、port 18080非listenを確認した。raw response、合成入力本文、cache内容、一時runnerは保存していない。

記録更新後の標準offline gateはlock 79 packages、Ruff 197 files、Markdown 16 files・1,278 links・877 anchors・1,613 headings・199 fence pairs、offline pytest 1,661 passed・9 skipped・1 deselected、Python 3.10 AST 197 files、`git diff --check` に成功した。server processなしとport 18080非listenも同時に再確認した。

## 75. 2026-09-06: request v6＋prompt cacheのlocalhost結合test接続

この項目は、[EXEC-058](GOAL.md#exec-058-request-v6prompt-cache-localhost結合テスト) と
[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2) に基づく未コミット作業を記録する。
利用者の「接続しろ」に従い、request v6、本番相当 `llama-server` prompt cache、
actual Requests transport、full JSON strict adapterを同じ明示opt-in localhost結合testへ接続した。
外部委託中フロントエンド、legacy検索、API、Outscraper、Cloudflare、Vulkan buildは変更していない。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| 現行test・CI・network guardの静的確認 | request v6とprompt cacheが現在の自動testで同時に検証されるか確認する | request v6 bodyはmock test対象、`--cache-prompt` はREADME起動例と手動benchmarkだけで、通常CIは `not live_api` | v6は自動検証済みだが、cache hitとfull JSONは自動E2E未接続だった |
| `pytest -q -m 'not live_api' tests/test_bonsai_live_e2e.py` | localhost runnerの期待契約を実装前に固定する | 終了2、`ModuleNotFoundError: tools.bonsai_live_e2e`。test SHA-256は `8e96d8b032c73f52a7b84f6861d9a15de3a596d34feb0c574b2e9a551a380548` | 新runner不在を対象理由とするREDだった |
| runner・marker・optionの最小実装 | server起動引数、固定2 calls、v6、strict adapter、cache metadata、cleanupを接続する | `tools/bonsai_live_e2e.py`、`tests/test_bonsai_live_e2e.py`、`tests/conftest.py`、pytest markerを追加 | 二重opt-inとabsolute regular fileなしにserverを起動せず、合成2 requestをv6からactual transportとstrict adapterへ通して2件目の正のcached tokenを要求できる |
| 新runnerとBonsai関連のoffline GREEN | 外部通信なしでcommand、config、metadata投影、2 calls、例外・deadline cleanup、既存v6 request・HTTP・adapter境界を確認する | focusedは16 passed・1 deselected、関連回帰は133 passed・1 deselected | 実modelなしでrunner契約と既存request・HTTP・adapter回帰が成功した |
| `pytest -q tests/test_bonsai_live_e2e.py` | 二重opt-inのない通常収集でserverが起動しないことを確認する | 16 passed、1 skipped | live testは通常pytestでskipされる |
| 現行 `llama-server --help` の局所確認 | runnerが指定するserver optionの存在をmodel起動なしで確認する | `-c`、`-np`、`--cache-prompt`、`--log-disable`、無効の `--slot-save-path` がhelpに存在 | 現行CPU版binaryがrunnerの固定引数を受理できる |
| 標準offline gate | 通常回帰、構文、文書、差分の整合性を確認する | lock 79 packages、Ruff 199 files、pytest 1,677 passed・9 skipped・2 deselected、Python 3.10 grammar AST 199 files、Markdown 16 files・1,285 links・884 anchors・1,628 headings・201 fence pairs、`git diff --check` 成功 | localhost liveを実行せず、repository標準のoffline検証が全て成功した |
| 二重opt-inのlocalhost Bonsai live test | 提示したendpoint、2 calls、deadline、credential・費用・保存範囲への利用者承認後に、request v6、full JSON、strict intent、prompt cache hitを実modelで確認する | 683.00秒で1 passed。1件目はprompt 924・cached 0 tokens・99.729秒、2件目はprompt 925・cached 891 tokens・579.494秒 | 2件ともschema 6.0のfull JSONとstrict intentを通過し、2件目はpromptの約96.3%をcacheから再利用した。入力とcompletionが異なるためwall時間差はcache速度比較ではない |
| live test終了後のprocess・port確認 | test所有serverが回収され、loopback endpointが残っていないことを独立確認する | `llama-server` processなし、port 18080非listen | server停止とmemory上のprompt cache破棄境界まで完了した |

runnerは未使用portを事前検査し、`127.0.0.1`、context 8,192、parallel 1、
`--cache-prompt`、`--log-disable` でtest所有serverを起動する。`--slot-save-path` は使わず、
親processのcredentialを含み得る環境も引き継がない。非機密合成入力2件、各1 attempt、retry 0、
response 1 MiB、server ready後900秒全体deadlineに固定する。production requestのHTTP timeoutと
生成token上限は追加しない。応答本文、合成入力、cache内容、server logは保存・出力しない。

live実行はCore i5-13600KFのCPU版で行った。2件ともfull JSON・strict intentに成功し、
2件目の正のcache hitを確認したが、異なる入力・生成内容のwall時間をcacheの速度効果へ換算しない。
Core Ultra、Vulkan、Outscraper、ranking、API、UI、production E2Eは実行・確認していない。

## 76. 2026-09-06: Bonsai応答時間のprompt・生成分離診断

この項目は、[EXEC-059](GOAL.md#exec-059-bonsai応答時間のprompt生成分離診断) と
[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2) に基づく未コミット作業を記録する。
EXEC-058の1件目99.729秒、2件目579.494秒は入力と生成内容が異なり、保存したprompt・cache token数と
wall時間だけでは差の原因を確定できなかったため、同じ入力でprompt処理とcompletion生成を分ける
専用診断をoffline TDDした。offline実装と標準gateの段階ではBonsai serverとmodelを起動せず、
その後、条件を再提示した新しい明示承認に基づくlocalhost 2 callsだけを実行した。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| EXEC-058 runnerとlocal llama.cpp sourceの静的確認 | 既存記録だけで時間差を説明できるか、追加で安全に取得できる数値を確認する | cacheは共通prompt prefixを再利用し、応答にはcompletion token数と `prompt_n`・`prompt_ms`・`predicted_n`・`predicted_ms` がある。既存runnerはこれらを保存していなかった | 既存の99.729秒対579.494秒から原因は確定できず、prompt処理と生成の分離計測が必要だった |
| timing投影と同一入力2 callsのRED test | 本文非保持、型・範囲・整合性、同一body、cleanupの期待契約を実装前に固定する | test SHA-256 `526168216c2a33df45edddc6e81bee024b0bac8ea314cb4579949691aaf1d735` で11 failed・15 passed・2 deselected。未実装のprojector・runnerと旧result形だけが失敗した | 追加対象を安全なmetadata投影と専用runnerに限定できた |
| live mode排他selectorのRED test | 診断selector時に既存の異なる入力2 callsを同時実行しない契約を固定する | test SHA-256 `5802924b6eadab9667a279206cd7d4e12a1307354054d0deddb65fd578c5d3a2` で6 failed・1 passed。未実装selectorだけが失敗した | 1回の診断実行を同一入力2 callsだけに制限する失敗条件を再現した |
| `tools/bonsai_live_e2e.py`、test、pytest option・markerの最小実装 | 同じrequest v6を2回送り、安全なprompt・生成timingだけを返す | runner SHA-256 `1c4f3bdde065d015547340991703580238352eff9dc01c76762d549552a3ab7c`、test `67040de62d0ee934f5716fb2c10aa594038b52df300151f4b086c530feb58a14`、conftest `d5fe294062635523296a739de62bb0fef9d49327effff5cc243a72cfeb4986c7`、pyproject `b6f1137a0fa2482f0a63d49b48a56db718245798834f4c6acb5e9ff0ecc5908a` | 通常live testと排他で、同じsource・body digestのschema 6.0を2 callsに固定し、raw本文をresultへ保持しない経路を実装した |
| `pytest -q -m 'not live_api' tests/test_bonsai_live_e2e.py` | projector、同一入力、排他selector、cleanupをmodelなしで確認する | 33 passed・2 deselected | 新規診断を含むrunner契約がofflineで成功した。実model・HTTP成功は示さない |
| Bonsai関連4 test fileのoffline回帰 | request v6、HTTP、strict adapterと新runnerの整合を確認する | 150 passed・2 deselected | 既存Bonsai offline境界を壊さず診断を追加できた |
| `pytest -q tests/test_bonsai_live_e2e.py` | opt-inなしでlive testが起動しないことを確認する | 33 passed・2 skipped | 通常pytestでは既存live testと新診断の両方がskipされる |
| 標準offline gate | repository全体の回帰、構文、文書、差分を確認する | lock 79 packages、Ruff 199 files、pytest 1,694 passed・9 skipped・3 deselected、Python 3.10 grammar AST 199 files、Markdown 16 files・1,292 links・891 anchors・1,643 headings・203 fence pairs、Markdown test 4 passed、zero-width scan、`git diff --check` 成功 | model・live通信なしで標準検証が全て成功した |
| binary・model・実行機・portのread-only再照合 | live条件のdriftと既存serverの上書きを送信前に防ぐ | server version 9294（`0f3cb3fc8`）、server SHA-256 `71b0c2554c375071855547f5da7ef2fc5c34766f6fcd6fab194ce93a18a59e0a`、model SHA-256 `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54`、Core i5-13600KF、`llama-server` processなし、port 18080非listen | 今回の候補はCore Ultraではなく既存CPU版で、専用serverを安全に起動できる事前状態だった。model推論はまだ行っていない |
| 同一診断requestのoffline canonical化 | exact payloadを本文表示なしで直前承認へ固定する | schema 6.0、temperature 0、20,728 bytes、body SHA-256 `b89200bad91a83de5e078cdc6782c64066ed91d6abc5348f707c84e3ad9da464`、source input SHA-256 `46fcb503864a60192e3f5d4262b3fa5a8389ac7df7f28526bfb45c70d3023f7b`、`max_tokens` なし。同じbodyを2回使う | 2 callsのpayload identityを送信前に再現でき、schema二重送信を戻していない。HTTP送信とmodel実行は示さない |
| 承認済みlocalhost同一入力診断 | prompt cache効果とcompletion生成時間を同じ入力・同じ生成token数で分離する | 利用者へendpoint、exact入力、同一body 2 calls、retry 0、上限、credentialなし、費用0円、保存範囲を再提示し、「実行せよ」の新しい承認後に実行した。231.24秒で1 passed。両方924 prompt・487 completion tokens、`finish_reason=stop`、full JSON・strict intent成功。coldはprompt 43,655.256 ms、generation 93,609.113 ms、wall 137,311 ms。warmはcached 923、processed 1、prompt 123.505 ms、generation 90,280.801 ms、wall 90,440 ms | prompt区間は353.47倍・99.72%短縮、wall全体は1.52倍・34.13%短縮した。warm wallの99.82%をcompletion生成が占め、cacheではなく生成が次の主な改善対象である |
| live test終了後のprocess・port確認 | test所有serverとmemory上のcacheが回収されたことを独立確認する | `llama-server` processなし、port 18080非listen | server停止とprompt cache破棄境界まで完了した |

診断は `127.0.0.1`、context 8,192、parallel 1、prompt cache有効、server log無効、slot非保存、
temperature 0、response 1 MiB、startup 180秒、ready後全体900秒、retry 0を維持する。
applicationの生成token上限とHTTP timeoutは追加しない。出力対象はprompt・cache・completion token数、
prompt・generation時間、finish reason、response byte数、wall時間、schema version、server停止状態だけである。
入力、request body、生成JSON、cache内容、任意provider field、server logは保存・出力しない。

実行結果では、coldからwarmへprompt時間を43,531.751 ms削減し、wall時間を46,871 ms削減した。
同じ487 completion tokensの生成時間差は3,328.312 ms・3.56%であり、cacheによるprompt削減と
生成速度の観測差を分けて扱う。EXEC-058の旧579.494秒は当時のcompletion token数とtimingを
保存していないため直接分解できない。ただし2件目で891 cached tokensを確認済みで、今回も
cache hit時のprompt処理が0.124秒だったため、cache不発よりcompletion生成側が有力である。

実行対象は現行Core i5-13600KFのCPU版であり、Core Ultra、Vulkan、OpenVINO、NPU、別model、
Outscraper、Cloudflare、ranking、API、browser、production E2E、外部委託中フロントエンドは
実行・確認しない。Vulkan版buildは現行build完成後の別工程という境界を変更しない。

## 77. 2026-09-06: Bonsai 196-token目標のcompact wire応答

この項目は、[EXEC-060](GOAL.md#exec-060-bonsai-196-token目標のcompact-wire応答) と
[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2) に基づく未コミット作業を記録する。
EXEC-059ではprompt cache後のwarm wallの99.82%をcompletion生成が占めたため、token数を196で
強制切断せず、意味を持たない既定表現だけをwireから省くrequest v7をoffline TDDした。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| `tests/test_search_v2_bonsai_compact.py` のRED | compact復元、完全形式との意味同等性、compact生成schema、request v7、生成上限不在を実装前に固定する | test SHA-256 `38d7c8bb1083d7a7878d6a01ca4fa3618b101c2a49e82dda66ec38d0dc11169a` で1 passed・3 failed。compact parse、compact schema、v7だけが未実装理由で失敗した | 変更対象をprovider wire、adapter復元、生成schema、request digestへ限定できた |
| compact wire model、復元、生成schema、prompt、request v7の最小実装 | null、空list、価格既定値を省略し、従来の完全19-field draftへ戻してstrict検証する | adapter SHA-256 `5d9d1e20e6824b5a8a0b8e04e0df81e38e49d66350cca412b19b92a2e981e942`、request `310b105a299d2d4e5c6d1d28e1a210acde92932e815232795aaa904b584b67b3`、prompt `9827506f57f32e7f1080f34b33cfa55427b1ec5492a076d4c439c1ea0dbeb6bc`。schema version 7.0 | 同じ意味のfield名とapplication契約を維持し、旧v6 descriptorとdigest domainを混在させない実装になった |
| prompt整合の追加REDと修正 | compact schemaがnullを許可しないfieldについて、旧promptがnullを指示しないことを固定する | test SHA-256 `b96102f510b82ea25c045a97b389d71f9c57c6626f6781f54bd8ec5caaf9666e` で6 passed・1 failedとなり、`product_name_ja=null` の旧指示を検出した。指示を「省略」へ直して7 passed | promptとcompact schemaのblocking分岐が一致し、modelへschema違反を要求しない |
| focused GREENとBonsai関連回帰 | 省略既定値、意味同等性、sparse価格、unknown field、request・HTTP・typed adapter・live runnerのoffline契約を確認する | 最終test SHA-256 `b96102f510b82ea25c045a97b389d71f9c57c6626f6781f54bd8ec5caaf9666e`。focused file 7 passed、関連6 files 175 passed・2 skipped | compactと完全形式は同じnormalized intent、query plan、typed proposalを作り、不正値は本文を露出せず拒否する。skipされたlive testの実model・HTTP成功は示さない |
| local `llama-tokenize --stdin --show-count` | 代表compact JSONが固定GGUFの196-token目標を満たすか、同じ意味の完全形式と比較する | compact 126 tokens、完全19-field minified形式181 tokens。modelは1,158,654,496 bytes、SHA-256 `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54`。tokenizer SHA-256 `ac97a885327a072036dde5b0d92e90f75236df1e764e635a8f57c73153356f9f` | 代表形式は196以下で、完全形式より55 tokens・30.4%少ない。tokenizerだけの結果であり、実modelの生成量、品質、速度を示さない |
| request artifact集計とllama.cpp JSON-schema converter | v7がcompact schema、完全schema、prompt、bodyを個別digestへ結び、現行converterで扱えるか確認する | body 18,163 bytes・SHA-256 `a4ae57f0c552c7548e26df280792ef5cb9405c420f683ad2006e89ae008059fc`、compact生成schema 13,804 bytes・`263a23a00c874cdff97604c2ea008e493c53a02daf1ea988dcaa5d825354909f`、完全schema 7,352 bytes・`f6650c439794aface4d3b2b98227c32d8123ea9349db2ca3ad82dab7eedfb88c`、prompt 4,074 bytes。converter終了0 | `response_format.schema` はllama.cpp互換で、完全schemaはmodelへ二重送信せずapplication側の最終権威として残る。bodyに `max_tokens` はない |
| 次期検索関連と標準offline gate | repository全体の回帰、構文、文書、差分を確認する | lock 79 packages、Ruff 200 files、次期検索963 passed・11 skipped、全体1,700 passed・9 skipped・3 deselected、Python 3.10 grammar AST 200 files、Markdown 16 files・1,299 links・898 anchors・1,658 headings・203 fence pairs、Markdown test 4 passed、zero-width scan、`git diff --check` 成功 | model推論・live通信なしでrequest v7と既存offline境界が共存し、標準検証が成功した |
| 承認済みrequest v7 localhost latency diagnostic | 固定合成入力の同一bodyを最大2 callsだけ送り、compact生成のcold・warm時間を本文非保持で測る | `127.0.0.1:18080`、context 8,192、parallel 1、prompt cache有効、retry 0、response最大1 MiB、ready後900秒、credential・外部network・費用なしで開始した。bodyは18,172 bytes、SHA-256 `db1f302c51b61ae44f1ccde545e87708de82edb2a2e1bdff06643bc1fa9fa942`。365.12秒時点で応答未完了のため、原因を調べられる状態なら打ち切るという利用者指示に従いSIGINTで停止した。pytest testは完了せず、`no tests ran` となった | request v7は実modelへ送信されたが、完了応答、strict intent、completion token数、速度改善率は得られなかった。runnerは両call完了後に結果を出すため、1件目と2件目のどちらを処理中だったか、完了call数が0か1かは確定できない |
| `ps`・thread CPU・`ss` による停止前snapshot | 応答待ちがdeadlock、接続失敗、idle、model計算のどれかを区別してから停止する | `llama-server` はrunning、約995% CPU、30 threads、RSS 2,527,844 KBで、主threadと9 workerがほぼ各1 coreを使用した。localhost TCPはestablishedでqueue 0、pytestはCPU 0%でsocket read待ちだった | client側のrequest構築、TCP接続、idle待ちではなく、server内の生成処理が進行中だった。応答本文とserver logを保存していないため、生成済みtoken数と終了見込みは確定できない |
| request build・compact parseのoffline反復と生成schema grammar集計 | application側処理とschema制約の規模を長時間処理から分離する | 100回平均はrequest build 4.466 ms、compact parse 2.574 ms。生成grammarは48,736 bytes、289行、833 alternationsで、任意field、長い文字列、多数要素の配列を許す。bodyに生成token上限はない | application側処理は365秒の支配要因ではない。126 tokensは代表fixtureの長さであって実生成を196以下へ拘束しないため、長い生成が有力原因である。grammar sampling overheadは分離できず、応答未完了なので断定はしない |
| SIGINT後のprocess・port確認 | 手動停止でtest所有serverとmemory上のprompt cacheが残らないことを確認する | pytest、uv、`llama-server` processなし、port 18080非listen、TCP接続なし | 追加requestを送らず停止・回収できた。生response、cache、server logは保存していない |

196は代表fixtureの形式目標であり、applicationへ `max_tokens=196` を追加していない。長い正当な
応答を切断せず、`finish_reason=length` は従来どおり `output_truncated` として拒否する。
旧request v6の487 completion tokensとの単純比ではcompact fixtureは74.1%少ないが、同じv7実生成を
比較した値ではないため応答時間の改善率へ換算しない。

request v7のlocalhost HTTPは承認後に開始したが応答完了前に手動停止し、成功・品質・速度は確認できて
いない。credential、外部network、課金は使用していない。Core Ultra、Vulkan、OpenVINO、NPU、
Outscraper、Cloudflare、ranking、API、browser、production E2E、外部委託中フロントエンドは
実行・確認・接続していない。追加live診断は実行条件を再提示し、新しい明示承認を得てから行う。
Vulkan版buildは現行build完成後の別工程という境界を維持する。

## 78. 2026-09-06: Bonsai bounded compact schema

この項目は、[EXEC-061](GOAL.md#exec-061-bonsai-bounded-compact-schema) と
[FR-401](REQUIREMENTS.md#35-次期検索フロー-v2) に基づく未コミット作業を記録する。
request v7の実応答が365.12秒で未完了となった後、196-token hard capは追加せず、compact schema自体の
文字列長、配列要素数、root field profileを制限するrequest v8をoffline TDDした。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| bounded schemaのRED | 固定field branch、文字列・配列上限、価格省略、request v8を実装前に固定する | test SHA-256 `4b2b703c2e86e10ec5f32109f3a8f16bf4ba01cab59abf30416c4637bb55c61a` で7 failed・5 passed。新しい7期待だけが未実装理由で失敗した | 変更対象をcompact wire、生成schema、prompt、request digestへ限定できた |
| bounded compact model、固定branch、prompt、request v8の最小実装 | 検索可能応答と確認待ちを分離し、上限超過を切断せず拒否する | adapter SHA-256 `8607121b2391d1594a0d47273a5497cae5f8cc5b0e75fcd3db68633ce89bed93`、request `4c12ba9abdf47e3e184de67d154eaf141eac94626ef6a5336c1519c3470ae1fb`、prompt `4da84bc5e28e64560ba14d13790d805ff7ae3d8c5ed837a14b29ca8d5ba11d38`、focused test `9b192c605282acd375728e46811675d90ebe28fd1a31833c8d2e1f8bebfdd14c`。schema version 8.0 | 検索branchは最大12種類、blocking branchは `ambiguities` だけとなり、旧v7 descriptorとdigest domainを混在させない |
| focused GREENとBonsai関連回帰 | 上限内の復元、各上限超過、profile混在、HTTP、request、typed adapter、live runnerのoffline契約を確認する | focused 17 passed。関連6 filesは185 passed・2 skipped | 文字列・配列上限と本文非保持拒否がapplication境界でも機能する。skipされたlive testの実model成功は示さない |
| llama.cpp JSON-schema converter | schema制限が実際の生成grammarへ反映されるか確認する | schema 9,820 bytes・SHA-256 `d4e2ba9d8674f530bc520212649354d696c07056b8ec201b36959736b0af6ade` からgrammar 48,260 bytes・214 rules・SHA-256 `0d9ea13ccf6bde3e4ce151c60936981fb62e2b8c045097aa157cf6810be305cf` を終了0で生成。stderr 0 bytes | 商品名 `char{1,48}`、term `char{1,32}`、最大4件の追加反復 `{0,3}`、ambiguity最大2件・message `char{1,96}` がgrammarへ現れ、`category_ja`、`color_ja`、`features_ja` のroot ruleはない |
| local `llama-tokenize --stdin --show-count` | 同じ意味の代表fixtureを固定GGUF tokenizerで比較する | bounded compact 432 bytes・104 tokens、完全19-field 702 bytes・181 tokens。両方終了0、stderr 0 bytes | 代表fixtureは77 tokens・42.5%少ない。任意の実生成token数、速度、意味品質を保証しない |
| request artifact集計 | v8 bodyがprompt、生成schema、完全schemaを個別にbindすることを確認する | 代表body 15,008 bytes・SHA-256 `ccc2cc6ef9d37bd51d8cb0c01d217dc0b9c3d253a304cc19d32582ff3933d040`、生成schema 9,820 bytes、完全schema 7,352 bytes、prompt 4,899 bytes。bodyに `max_tokens` なし | schema二重送信を戻さず、完全schemaをapplication側の最終権威として維持した |
| 次期検索全体回帰 | 共有fixtureをv8 wireへ移行し、orchestrator・履歴を含む回帰を確認する | 初回は旧19-field共有fixtureを原因として30 failed・910 passed・9 skipped。fixture移行後は940 passed・9 skipped | 失敗は2つの旧provider fixtureからの連鎖で、v8へ移行後は次期検索全体が成功した |
| 標準offline gate | repository全体の回帰、構文、文書、不可視文字、差分形式を確認する | lock 79 packages、Ruff 200 files、全体1,710 passed・9 skipped・3 deselected、Python 3.10 AST 200 files、Markdown 16 files・1,306 links・905 anchors・1,672 headings・203 fence pairs、Markdown test 4 passed、zero-width scan 270 files、`git diff --check` 成功 | 依存取得、model推論、live通信なしでrequest v8と既存offline境界が共存する |
| 承認済みrequest v8 localhost latency diagnostic | bounded compact後の実model生成量、prompt cache、応答時間を同じ固定入力2 callsで測る | Core i5-13600KF・CPU版、`127.0.0.1:18080`、context 8,192、parallel 1、cache有効、retry 0、response最大1 MiB、ready後900秒で実行。1 passed in 72.49s。2 callsとも1190 prompt・254 completion tokens・`finish_reason=stop`・strict intent成功。coldはprompt 35,594.167 ms・生成17,480.571 ms・wall 53,148 ms。warmは1189 cached、prompt 69.675 ms・生成17,529.892 ms・wall 17,625 ms | v8内でcacheはpromptを99.80%短縮し、wallを66.84%短縮した。旧v6記録比でcompletionは47.84%減、warm生成は80.58%減、warm wallは80.51%減・5.13倍だった。別run比較のためschema変更だけへ因果を限定しない |
| 終了後のprocess・port確認 | test所有serverとmemory上のcacheが残らないことを確認する | `llama-server` processなし、port 18080非listen | 追加requestなしで停止・回収できた。生response、入力、cache、server logは保存していない |
| 承認済みrequest v8 1-call意味回帰 | 別の固定合成入力で条件保持と後続query生成を確認する | localhostへ1 call、retry 0。50.628秒、1192 prompt・82 completion tokens、`finish_reason=stop`、strict intent成功。価格・色・除外条件を欠落し、入力にないstyleをtext setとして返したためtyped proposalは`invalid_condition`のblocking。query plan、Outscraper callなし | 接続と形式成功だけでは意味品質を示さない。追加providerへ進む前に停止できた |
| 語彙非依存promptとtyped value-type schema | 条件欠落とattribute・value type不整合を、特定の商品語彙やrequest量増加へ依存せず修正する | prompt 4,899から3,600 bytes、生成schema 9,820から10,950 bytes、同一入力body 15,032から14,859 bytes。adapter SHA-256 `5d7983b08634f4b536f39d33e1e83297350fa161f1866241e60f13f3d5b800a9`、prompt SHA-256 `fb324ab54bf2f59990df4b2f5efc35f086d694c98a9f2ffc90473de40c156e14`、schema SHA-256 `b0976b7d99a8564ab4022931857d36f9b9b718dfdf23058eb20dd8ab3be3ac9a` | 入力を原子的条件へ分け、未知語を原文termsへ保持し、割当不能をblockingへ戻す。typed conditionを6 value-type branchへ結んでもrequest bodyは173 bytes小さい |
| ready compact回帰とfocused test | 既知の失敗入力とpromptにない未知語を保持し、既存Bonsai・orchestrator契約と共存するか確認する | 203-byte fixtureで元の欠落条件を保持してtyped proposal `ready` と日本語query planを生成。さらに藍鼠色・超低背、雲母調・真空対応、hyperspectral・field-calibrated等、promptにない3組の日英語彙をtermsへ保持した。関連6 filesは183 passed | adapterとquery plannerは検索語whitelistへ依存せず未知語を保持できる。実modelが未知語を正しく分類する証拠ではない |
| llama.cpp JSON-schema converter | value-type branchを現行converterが処理できるかnetworkなしで確認する | schema 10,950 bytesからgrammar 54,537 bytes・254 rules、SHA-256 `80bd8cd5c584eaaa9e883b72cd16bd774a92cddf2d737bead314636a03d7d4ac` を終了0で生成 | `appearance.style`とtext setのようなvalue-type不整合を生成grammarで許可しないschemaを実行環境へ渡せる |
| 修正後の標準offline gate | repository全体の静的・fixture・mock回帰を確認する | lock 79 packages、Ruff check成功・200 files formatted、Markdown 16 files・1,306 links・905 anchors・1,672 headings・203 fence pairs、pytest 1,717 passed・9 skipped・3 live deselected、`git diff --check`成功 | 外部通信とmodel推論なしで、修正が既存offline境界と共存する。修正後の実model速度・意味品質は示さない |
| 修正後の承認済みrequest v8 1-call回帰 | 語彙非依存prompt・value-type schema後の同じ固定合成入力について、応答時間と後続へ渡せる意味条件を確認する | `127.0.0.1:18080` へexact 1 call、retry 0。53.595秒、887 prompt・248 completion tokens、response 1,670 bytes、`finish_reason=stop`、strict intent成功。価格・除外条件を欠落し、入力にないtyped conditionを含めたためproposalはblocking。query plan、Outscraper callなし。server停止・port非listen。生要求・生応答・server logは保存していない | promptとschema修正後もmodel単独では明示条件を保持できない。後続provider前の停止とcleanupは機能した |
| source-grounding回帰のRED | 取得済み実応答の意味形をfixture化し、語彙固有patchではなく境界修正が必要なことを確認する | 価格上限が復元されず1 failed。実応答本文は保存・再利用せず、正規化済み意味形だけを合成fixtureとして記述した | strict JSON成功だけでは足りず、sourceに基づくローカル補完・根拠検査が必要である |
| typed根拠検査と明示条件の決定的復元 | request量とmodel callを増やさず、無根拠typed候補を実行条件へ昇格させず、価格・除外を復元する | adapter SHA-256 `ef74ddc622dfdd6c3bf8cb16f2050e81e957716a859c24b8362b064d67083fd1`。入力中の原語・trusted aliasでtyped candidateを照合し、不正candidateの入力根拠値は自由語termへ戻す。日本語JPY min・max・range、「不要・除外・避ける・without」、単一漢字aliasの未知語内境界を実装。関連4 files 119 passed | 商品名や未知語の固定listを追加せず、取得済み応答相当fixtureは価格上限10,000円、除外対象、白、ワイヤレスを保持してreadyとなる。adapter修正後の実再推論は示さない |
| source-grounding後の標準offline gate | repository全体の回帰、構文、文書、差分形式を最終確認する | lock 79 packages、Ruff check成功・200 files formatted、Markdown 16 files・1,306 links・905 anchors・1,672 headings・203 fence pairs、pytest 1,723 passed・9 skipped・3 live deselected、Python 3.10 AST 193 files、`git diff --check`成功 | 外部通信・model推論なしで新しいadapter境界が既存offline契約と共存する。adapter修正後の実model成功、実商品検索、未知入力全般の品質は示さない |
| SudachiPy span方式のRED | 手書き文字境界による日本語照合を形態素spanへ置き換える前に、未知複合語と否定対象の期待を固定する | 2件中「静音キーボードでテンキーは不要」が `静音キーボードでテンキー` を抽出して1 failed、未知複合語内の単一漢字alias拒否は1 passed。二重否定も別REDで `テンキーは不要で` を抽出して1 failedとなった | 単純な直前切出しでは格助詞境界と二重否定を安全に扱えず、助詞・助動詞を含む正規化済みsource offset解析が必要である |
| SudachiPy `SplitMode.C` span実装 | sourceを1回解析し、全形態素のsurface・正規化形・辞書形・品詞・開始終了offsetで根拠照合、価格関係、否定範囲を扱う | tokenizer SHA-256 `f5ba7ff5ab7910f1146096031cffbc072e28905d9bf947b390b1be3966fa17b5`、adapter `992f4939a0879bfe96fae6b0e8f2b7cdf7bbc7f7cc5bbba0d13178ce2782648f`。tokenizer・compact adapter 45 passed、関連146 passed | trusted aliasは連続する完全形態素spanだけへ一致する。未知複合語内の部分一致、格助詞より前の巻き込み、二重否定を拒否し、未知の対象語は正規化済みsource spanのまま保持できる |
| local warm benchmark | requestを増やさず、形態素解析とadapter後処理のlocal overheadを確認する | 初回形態素解析46.300 ms、warm解析10,000回平均0.032384 ms、warm adapter全体1,000回平均2.043352 ms | 同一host・同一processの限定値では既存の約53秒model応答に対して小さい。Core Ultra、production、任意長入力の保証ではない |
| SudachiPy span方式後の標準offline gate | repository全体の回帰、構文、文書、差分形式を確認する | lock 79 packages、Ruff check成功・200 files formatted、Markdown 16 files・1,306 links・905 anchors・1,672 headings・203 fence pairs、pytest 1,728 passed・9 skipped・3 live deselected、`git diff --check`成功 | 外部通信・model推論なしで置換が既存offline契約と共存する。adapter修正後の実model成功、実商品検索、未知入力全般の品質は示さない |
| 承認済みSudachiPy source-grounding 1-call localhost試験 | 固定合成入力1件で、実Bonsai応答後の価格・未知語・否定範囲・二重否定とquery planを再確認する | `127.0.0.1:18080`へ1 call、retry 0でstrict intent、typed proposal構築、query plan作成まで完了した後、集計コードが存在しない `InMemoryUsageLedger.reservations()` を呼んで失敗した。`finally`でserver停止、port非listenを確認した。追加call、Outscraper、Cloudflare、credential、外部network、課金はない | strict受理とquery plan到達は確認できたが、集計値を出力する前のtest harness失敗なので意味条件・応答時間・token数の合否は確定できない。自動再実行せず、次回は `snapshot().reservations` を使う修正版をoffline確認し、新しい明示承認後にだけ再実行する |
| 別承認によるSudachiPy source-grounding 1-call再実行 | 集計を `snapshot().reservations` へ修正し、同じ固定合成入力の意味条件を再確認する | `127.0.0.1:18080`へ1 call・retry 0。83.398秒、902 prompt tokens、290 completion tokens、response 1,895 bytes、`finish_reason=stop`。未知語2種、5,000〜10,000円、除外対象、二重否定拒否、strict intent、ready proposal、query planの全判定が成功。server停止・port非listen | SudachiPy adapter後の単一development regressionは成功した。Outscraper、Cloudflare、credential、外部network、課金はなく、未知入力全般、実商品候補、ranking、production E2Eの合格を示さない |

上限内で意味を保てない場合はblocking確認待ちを返すようpromptで要求する。ただしschemaだけではmodelが入力条件を
黙って欠落したか検出できないため、意味品質は別評価が必要である。今回の実Bonsai診断はstrict形式と応答時間だけを確認した。
credential、外部network、課金は使用していない。Core Ultra、Vulkan、OpenVINO、NPU、Cloudflare、API、browser、
外部委託中フロントエンドは実行・確認・接続していない。Outscraperは後述の別承認・別試験で初めて接続した。Vulkan版buildは現行build完成後の別工程という境界を維持する。

## 79. 2026-09-06: Outscraper単一task実商品接続試験

この項目は、[EXEC-062](GOAL.md#exec-062-outscraper単一task実商品接続試験) に基づく未コミット作業を記録する。利用者へendpoint、固定合成query、1 query・24候補、task作成1回、自動retry 0、poll上限、timeout、応答上限、credential利用、費用見積り、保存しないデータを提示し、明示承認後に実行した。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| request descriptorとOutscraper HTTPのoffline回帰 | 外部送信前にquery数、候補数、async、timeout、poll、retry、応答上限を再確認する | descriptorは1 query・最大24候補・async、関連70 tests passed | 実送信前の契約が承認範囲と一致し、通常回帰は外部通信なしで成功した |
| 明示承認済みOutscraper単一task試験 | actual Requests transportからtask作成、同一task polling、応答検証、正規化までを実サービスで確認する | task作成1回、自動retry 0、poll 9回、251.795秒。候補24件を受信し、response contract成功、normalized 24件、rejected 0件、normalization contract成功、usage `succeeded` | 承認済み固定合成queryの単一試験では実Outscraperと現行normalizerが互換だった。失敗経路、未知query全般、属性充足率、ranking、production E2Eは示さない |
| 機密・商品データ非保持確認 | 試験証拠が利用者データやprovider内部識別子を残さないようにする | APIキー、生応答、商品本文、商品URL、ASIN、provider request IDを標準出力・文書・artifactへ保存しなかった | 接続結果を集計値だけで記録できた。provider側の課金記録は取得していないため実請求額は未確認 |
| 実行後の標準offline gate | live結果の記録後も通常の非live回帰と文書整合を維持できるか確認する | lock 79 packages、Ruff check・format 200 files、Markdown 16 files・1,315 links・914 anchors・1,678 headings・203 fence pairs、pytest 1,728 passed・9 skipped・3 live deselected、`git diff --check`成功 | taskを追加作成せず、既存のoffline境界と記録が共存する |

Bonsai、Cloudflare、ranking、履歴、現行pipeline、API、browser、外部委託中フロントエンドは接続していない。task作成の追加実行も行っていない。

## 80. 2026-09-07: 一続きE2E第1段階とsource grounding修正

この項目は、[EXEC-063](GOAL.md#exec-063-bonsai自由語と商品名のsource-grounding) に基づく未コミット作業を記録する。固定合成入力、localhost Bonsai 1 call、retry 0、外部通信・credential・費用なしを提示して明示承認を得た後、一続きE2Eの第1確認までを実行した。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| 承認済みBonsai 1 call | request v8から実model、strict intent、typed proposal、query planまでを一続きE2Eの第1段階として確認する | 44.762秒、906 prompt tokens、268 completion tokens、response 1,778 bytes、`finish_reason=stop`。入力にない商品名を生成し、桁区切りJPY範囲と未知色を欠落させても `ready` となった | HTTPと構文契約の成功だけでは意味的source groundingを保証しない。query確認時に停止し、Outscraper、Cloudflare、retry、credential、課金は使っていない |
| cleanupと継続state確認 | 失敗した第1確認を後続providerへ渡さず、local runtimeと一時データを回収する | intentとledgerはJSON境界で再検証できた。server processなし、port 18080非listen、一時state削除を確認した | 生response、server log、商品データを保存せず、追加callなしで安全に停止できた |
| source-grounding RED | 無根拠商品名・自由語・scalar、comma付きJPY範囲、不正commaの期待をproduction変更前に固定する | test SHA-256 `ee0df0e4ea7aca852623a8684f202f4e5efee7b89e830e7d1e21b484aed0da26`。focused 4件は3 failed / 1 passedで、未実装のsource grounding 3件だけが失敗した | typed condition以外のprovider値が未照合であり、価格regexが正しいcomma表記を扱わない欠陥を再現した |
| adapter最小実装とfocused GREEN | 同じSudachiPy spanを商品名・自由語・scalarへ広げ、JPY parserを補正する | adapter SHA-256 `2e48b78d6eec4dc3c4223bfb383ddc76e8bb57258451ac94d76d9d5f57caddad`、compact test `368faca40ad1060e883ff0812ada89f5984b39bd4713d5b7e84274980036e047`、orchestrator test `ddfb6dca25fcac8d07bc176e6bfc0d6914cea21654eef794bbd6947b02b35893`。focused 4 passed、compact 37 passed | 根拠のない商品名をblockingへ戻し、自由語・brand・modelをqueryから除き、正しいcomma付き範囲を復元できる。URL値は既存の固定searchability errorへ維持した |
| Bonsai関連・次期検索全体回帰 | request、HTTP、query、typed adapter、orchestrator、検索後半への副作用を確認する | 関連222 passed。全 `search_v2` は963 passed・9 skipped | 変更はoffline fixture上で既存v2境界と共存する。skipされたlive testと修正後の実model成功は示さない |
| 標準offline gate | repository全体の回帰、構文、文書、不可視文字、差分形式を確認する | lock 79 packages、Ruff 200 files、pytest 1,733 passed・9 skipped・3 live deselected、Python 3.10 AST 200 files、Markdown 16 files・1,324 links・923 anchors・1,690 headings・203 fence pairs、zero-width scan、`git diff --check` 成功 | 外部通信と追加model callなしで、修正と現行のoffline境界が共存する |
| 修正後の承認済みBonsai 1 call | 同じ固定入力が無根拠の商品名をqueryへ渡さず、明示条件を保持して停止するか実modelで再確認する | 43.282秒、906 prompt tokens、268 completion tokens、response 1,776 bytes、`finish_reason=stop`。価格範囲、必須語3件、除外語1件を保持し、商品名なし、typed proposal `blocking`、`source_product_ungrounded` で停止した | source grounding修正は実model応答に対してfail-closedに働いた。query plan、一時継続state、Outscraper callは作らず、自動retry 0、server停止、port 18080非listenを確認した |
| 商品名field過剰制約のRED・GREEN | 無根拠商品名を除去しても根拠ある必須語が残る実測応答を利用可能にし、肯定検索語のない入力は停止する | REDは2 failed / 1 passed。compact test SHA-256 `351e44ecf17cc133d9258ebbf41a45f5d4cbca4296c9a18210bc577ca21d0fb6`、orchestrator test `ee6ed3ef21ca8f55400853ede1fcb98bb8aec28475a27441959d7fde6ed075cf`。判定を商品名fieldの有無から、根拠ある肯定scalar・required・preferred termの有無へ変更し、同じ3件がGREEN。最終adapter SHA-256 `f78b85c325e536aeb9dc69c4b35aca8207b048d94cf537ecc2044bb4f517ed7b` | 語彙listや商品category推定を追加せず、未知語を含む根拠あるqueryを作れる。価格・除外語しか残らないfixtureはqueryなしのblockingを維持する |
| 最終offline回帰 | 商品名なしのquery許可がBonsai、typed proposal、orchestrator、次期検索全体へ回帰を生まないか確認する | 関連211 passed、全 `search_v2` 964 passed・9 skipped。lock 79 packages、Ruff 200 files、標準offline pytest 1,734 passed・9 skipped・3 live deselected | 最終修正はoffline契約と共存する。最終修正後の実modelとOutscraperは実行していない |
| 汎用判定後の承認済みBonsai 1 call | 同じ固定入力が実modelでもready queryを作れるか、Outscraper前の第1確認まで再確認する | 41.148秒、906 prompt tokens、268 completion tokens、response 1,775 bytes、`finish_reason=stop`。価格範囲、必須語3件、除外語1件を保持し、無根拠商品名なし、typed proposal `ready`。queryは `背 ワイヤレス キーボード` | source groundingと商品名なしの汎用判定は実model応答で機能したが、`超低背` の接頭辞欠落が残ったためOutscraper前で停止した。自動retry 0、server停止、port非listenを確認した |
| post-call state再検証と削除 | 後続providerへ渡すstateがstrict JSON境界を通り、修正前queryを残さないことを確認する | Python辞書からのstrict復元は日時・tuple型で失敗した。追加callなしでJSON境界から再検証し、directory 0700・file 0600を確認した。その後、旧queryを持つ専用stateを削除した | Bonsai本体のready結果と一時harness失敗を分離できた。Outscraper、Cloudflare、credential、課金、商品取得は開始していない |
| SudachiPy連続接頭辞のRED・GREEN | queryと類似語scoreの共通tokenizerが未知複合語の接頭辞を捨てないようにする | tokenizer・compact adapter・orchestratorのRED 3 failed。test SHA-256は `ca9db4b08f87d4061da0cfdbb34e83bde1663ce963192681121722587abd2248`、`b70e335cb4103e9c671491024bff179cf762569dd2e163d6b372642e46b75a6e`、`7a4ad314ed66b69102015c338b436c812a95e2b5819211818602582eca4163b8`。連続接頭辞を後続内容語へ結合し、同じ3件がGREEN。最終tokenizer SHA-256 `5a5d9f20b4d86e560c7a427def5b39ecf9a434ca287cbca4f05e0890216aaddb` | 個別語彙listなしで `超低背` を1 tokenとしてqueryとrankingへ渡し、同じ実測応答相当fixtureは `超低背 ワイヤレス キーボード` を作る。価格・除外語だけのblockingは維持する |
| 接頭辞修正後の最終offline回帰 | tokenizer共有先とrepository全体への副作用を確認する | 関連177 passed、全 `search_v2` 965 passed・9 skipped。lock 79 packages、Ruff 200 files、標準offline pytest 1,735 passed・9 skipped・3 live deselected | 最終修正はoffline契約と共存する。接頭辞修正後の実modelとOutscraperは実行していない |
| 接頭辞修正後の承認済みBonsai 1 call | 同じ固定入力が実modelでも未知複合語を保持したready queryを作るか確認する | 60.366秒、906 prompt tokens、268 completion tokens、response 1,777 bytes、`finish_reason=stop`。typed proposal `ready`、blocking・issue 0件。価格5,000〜10,000円、必須語3件、除外語1件、query `超低背 ワイヤレス キーボード` | source grounding、商品名なしの汎用判定、SudachiPy連続接頭辞の保持が同じ実model応答で接続した。Bonsai 1 call・自動retry 0で、Outscraperは呼んでいない |
| 継続stateと終了確認 | 正しいqueryを後続の別承認へ安全に引き継げるか確認する | IntentReview、policy、usage ledgerをJSON境界で再検証した。directory 0700・file 0600。server停止、port 18080非listen、`llama-server` processなし | 生responseやcredentialを保存せず、承認済みqueryとdigestだけをOutscraper前で保持できる |
| 承認済みOutscraper一続きE2E | 保持したBonsai reviewから画像を使わず、単一使用approval、実Outscraper、正規化、typed rankingまで接続する | query `超低背 ワイヤレス キーボード`、amazon.co.jp、日本語、郵便番号100-0001、最大24件、async。task作成1回、自動retry 0、同一taskのpoll 8回、221.458秒。24候補を受信し、normalized 24件、reject 0件、ranked 24件、outcome `results`、usage `succeeded`、approval consumption 1件 | 固定合成入力1件のbackend development E2Eは実サービスまで接続した。個々の条件一致、順位品質、未知入力全般、browser・UI・production E2Eは示さない |
| live商品データ非保持と終了確認 | credential、商品本文、provider識別子、消費済みstateを残さない | API key、生応答、商品本文、URL、ASIN、provider request IDを出力・保存しなかった。消費済み一時stateを削除し、専用一時directory、Bonsai process、port 18080の不在を確認した | 集計値だけで接続結果を記録し、同じapprovalまたはstateを再利用できない。provider側の実請求額は未確認 |

providerが省略した全条件をsourceだけから完全復元する変更ではない。接頭辞修正後の実Bonsaiが条件を保持し、無根拠商品名を除去して期待queryを作ることと、同じqueryによる実Outscraper・正規化・rankingの完了を確認した。結果本文を保持していないため、個々の商品が条件を満たすことや順位品質は未確認である。

## 81. 2026-09-07: 実ブラウザ候補とgpt-image独立参照のCLIP診断

この項目は、利用者の再開判断と明示承認に基づく [EXEC-064](GOAL.md#exec-064-実ブラウザ候補とgpt-image独立参照のclip診断) を記録する。

- 隔離Chromium 151でAmazon.co.jp検索結果をトップレベル遷移1回、外部要求59件、retry 0で表示した。DOM候補12件から224px以上の4商品画像をローカルPNGとして保存した
- 商品詳細ページ、ログイン、既存Cookie、CAPTCHA回避は使わず、商品URL、ASIN、商品名、生DOM、Cookie、credentialを保存しなかった
- 候補を入力せず、組み込みgpt-imageで正面を1回生成し、その正面だけを参照に左・右・背面を各1回生成した。4 calls、retry 0で、生成4枚をproject-localの未追跡assetへコピーした
- 「白・円筒形・卓上加湿器」を視覚条件とし、候補01・04を適合、02を形状不一致、03を色不一致としてCLIP実行前にmanifestへ固定した
- 固定ONNXの全体保持profileで候補scoreは0.956313209、0.865547134、0.807093262、0.844999933、正例中央値0.900656571、負例中央値0.836320198、pairwise AUC 0.75となった
- 左・右参照はpHash距離4で重複閾値5以内だった。正例2・負例2しかなく最低構成を満たさないため正式評価には使わず、画像rankingを無効のまま維持した
- 標準入力と直接file実行によるlocal runnerの2回の起動失敗は、それぞれ `spawn` のmain path不足とrepository import path不足だった。外部通信、browser、画像生成は再実行せず、module起動へ直して同じ固定artifactを診断した。一時runner、browser profile、Chromium processは回収した
- 記録更新後、lock 79 packages、Ruff 200 files、現行Markdown 16件のlocal link 1,322件・anchor 921件、Markdown test 4件、offline pytest 1,735 passed・9 skipped・3 deselected、全8画像のmanifest SHA-256、`git diff --check` を確認した。検証中の外部通信とprovider callは0件だった

画像とmanifest・結果は `tests/img/image-holdout-001/` にlocal未追跡assetとして置いた。Cloudflare、Outscraper、Bonsai、外部委託中フロントエンド、commit、pushは実行していない。本番の画像生成は実装済みCloudflare provider境界を正本とし、gpt-imageは評価テスト専用として製品adapterへ移行しない。

後続の明示承認による非対称条件のbrowser試験は、トップレベル遷移1回のperformance logで外部要求111件を観測し、上限100件超過として候補0枚で停止した。batch取得では上限到達前に停止できなかった。retry、gpt-image、CLIPは0回で、商品識別情報、生DOM、Cookie、credential、生provider応答を保存していない。外部通信を行わないlocal模擬ページでCDPの送信前interceptionへ切り替え、22要求中5件だけをcontinueした結果、server到達も5件となることを確認した。実Amazonへの再試行は別の明示承認まで行わない。

修正方式への別承認後の再試験では、CDP送信前interceptionで外部到達100件、送信前遮断64件、トップレベル遷移1回、retry 0を確認した。DOM候補9件から7画像を保存し、CLIP前の目視で正例0件・負例7件へ固定した。赤い候補もハンドルが赤く、評価条件を満たさない。最低構成不足のためgpt-imageとCLIPを開始せず、候補と集計だけを `tests/img/image-holdout-003/` に保存した。

category-only方式への別承認後、検索語「電気ケトル」と別評価条件「黒い本体」を固定した。CDP送信前interceptionで外部到達100件、送信前遮断70件、トップレベル遷移1回、retry 0を確認し、DOM候補12件から10画像を保存した。CLIP前の目視で候補06〜09を正例4件、候補01〜05・10を非黒色の負例6件としてmanifestへ固定した。

最低構成を満たしたため、候補を入力しない組み込みgpt-imageで正面・左・右・背面を4 calls・retry 0で生成した。固定ONNXのprocess隔離経路によるscoreは正例中央値0.924253657、負例中央値0.870871561、pairwise AUC 1.0、参照pHash最小距離12だった。事前基準のAUC 0.80以上、中央値分離、参照非重複を満たし、単一条件のassessmentを `pass` として `tests/img/image-holdout-004/` に固定した。商品URL、ASIN、商品名、生DOM、Cookie、credential、生provider応答は保存せず、一時runner、browser profile、Chromium processは残していない。この単一条件だけではカテゴリ横断性能またはtyped ranking全体を証明しないため、画像rankingは無効のままとした。

利用者判断を再確認し、本番の画像生成providerは当初の予定どおりCloudflare、gpt-imageは画像評価テスト専用と確定した。gpt-image製品adapterへの移行記述を要件・設計・計画から除き、既存Cloudflare境界をlegacyではなく本番接続前のoffline実装として位置付け直した。

別カテゴリでの再現性確認への明示承認後、検索語「オフィスチェア」と評価条件「黒いメッシュ背もたれ・ヘッドレスト付き」を分離したcategory-only試験を1回実施した。CDP送信前interceptionは外部到達100件、追加70件を送信前遮断し、トップレベル遷移1回、retry 0でDOM候補12件を保存した。CLIP前の目視で正例4件、負例6件、曖昧2件へ固定した。商品URL、ASIN、商品名、生DOM、Cookie、credential、生provider応答は保存していない。

最低構成を満たしたため、候補を入力しないテスト用gpt-imageで同一の黒いメッシュ背もたれ・ヘッドレスト付き椅子を正面・左・右・背面の4 calls、retry 0で生成した。固定ONNXのprocess隔離経路は正例中央値0.900518905、負例中央値0.921669262、pairwise AUC 0.291666667、参照pHash最小距離6だった。参照重複閾値5は超えたが、AUC 0.80以上と中央値分離を満たさず `tests/img/image-holdout-005/` のassessmentを `fail` とした。再取得・再生成は行わず、一時runner、browser profile、Chromium processを残していない。本番Cloudflareは呼ばず、画像rankingは無効のままとした。

記録更新後、全16画像のmanifest SHA-256、JSON構文、lock 79 packages、Ruff 200 files、現行Markdown 16件のlocal link 1,322件・anchor 921件、offline pytest 1,735 passed・9 skipped・3 deselected、`git diff --check` を確認した。この再検証で外部通信とprovider callは行っていない。

固定済み16画像だけを使い、production codeを変えずに改善候補を外部通信なしで比較した。中央正方形cropはAUC 0.375、参照比率2:3の中央cropは0.458333333、椅子上部60%・75%のcropはいずれも0.375で、全方式の正例中央値が負例中央値を下回った。同一datasetの負例を参照foldから除外して使うcontrastive marginは、1負例方式がAUC 0.25〜0.55、ヘッドレストなし・非黒色の2負例方式が0.125〜0.5625、leave-one-out label centroidが0.208333333だった。固定基準0.80と中央値分離を満たす方式はなく、labelを使った探索値を独立holdoutまたは採用証拠へ読み替えない。`tests/img/image-holdout-005/improvement-result.json` に集計だけを保存し、一時runnerとbytecodeを削除した。記録後のlock、Ruff、Markdown、offline pytest 1,735 passed・9 skipped・3 deselected、`git diff --check` も成功し、外部通信とprovider callは0件だった。


## 82. 2026-09-07: 未知の視覚条件に対する条件別counterfactual評価設計とoffline実装

固定オフィスチェアartifactの改善検証が全て不合格だったため、[EXEC-065](GOAL.md#exec-065-未知の視覚条件に対する条件別counterfactual画像評価) として次の実装前設計を固定した。

- 未知の視覚語句を固定類似語辞書へ丸めず、既存SudachiPy `SplitMode.C` と英数字tokenizerで元入力のexact spanへ結ぶ
- 利用者が最大3件の視覚条件を選び、候補とは独立したdesired anchor 1枚と、1条件だけを違反させたcounterfactual `N` 枚をexact `1 + N` calls、上限4 callsで作る。4件以上をサーバーが自動選択しない
- 候補とanchor、各counterfactualの固定CLIP embeddingから条件別marginを作り、参照差による正規化、clamp、参照分離、判定閾値をdevelopment setだけで決めて独立holdout前に固定する
- 画像で確定できない属性を対象外にし、open visual phraseは合格後も最初は補助scoreに限定する。構造化・限定title証拠を上書きせず、評価不能を `unknown` または `missing` とする
- 商品候補画像とembeddingを外部generatorまたはLLMへ送らない。本番providerはCloudflare、gpt-imageは評価テスト専用を維持する
- 現行の4方向Cloudflare descriptor、SEARCH-FLOW、state、ledger、history、ranking profileは変更しない。counterfactual方式が独立holdoutとCloudflareで合格した後、応答時間・call数・費用を提示して製品仕様変更を別途判断する

設計後、`src/search_v2/counterfactual_image.py` と専用testをTDDした。REDは未実装moduleの `ModuleNotFoundError` でexit 2、RED時点のtest SHA-256は `f7827972a13f9bc2038e4efdb8f678c6afa6a8c923096d9a0ac02b35d1f63863` だった。実装後は専用test 24 passed、既存の画像類似度・typed requirements・tokenizerを含む関連test 89 passedとなった。最終module SHA-256は `8efa806764df9d40f4f6f728e9bfbe77713cb40992f2f163d07bf0f3977f537a`、test SHA-256は `c6e315d9de49fd96ee07a58e285049d6db331b5fc7c68bee02342eeb8d3c9312` である。

実装は最大3件の条件をNFKC/casefold済み元入力spanへSudachiPyまたはASCII語境界で結び、source・registry・reference set・score profile・固定CLIP runtimeをdigestで再検証する。desired anchorと条件数どおりのcounterfactualについてpixel digest重複とpHash距離5以下を拒否し、raw marginと参照差で正規化した `[-1, 1]` のmarginを候補非依存で計算する。候補欠損は `missing`、数値的な参照分離不足は `unknown` とする。判定閾値は未較正で、scoreは常にranking不適格、画像ranking flagはfalseである。moduleは外部network、provider、ML runtimeをimportしない。

このoffline実装では画像、model、credential、browser、Bonsai、Cloudflare、Outscraper、gpt-image、外部委託中フロントエンド、commit、pushを変更・実行していない。外部callは0、費用0円である。現行4方向仕様、state、ledger、history、typed-ranking-v4も変更していない。通常gateはlock 79 packages、Ruff check、Ruff format 202 files、Markdown 16文書・local link 1,346件・anchor 944件、offline pytest 1,759 passed・9 skipped・3 deselected、`git diff --check` が全て成功した。

## 83. 2026-09-07: Counterfactual development較正と不合格判定

[EXEC-065](GOAL.md#exec-065-未知の視覚条件に対する条件別counterfactual画像評価) のdevelopment較正について、実行前にテスト用gpt-image、電気ケトル2 calls、オフィスチェア4 calls、合計6 calls、retry 0、自動再実行なし、候補画像を送らないこと、project内へ参照だけを保存すること、費用上限を設けないことを提示し、利用者の明示承認後に実行した。desired anchorと各counterfactualの合計6画像は全件生成でき、追加callはなかった。商品候補画像、候補embedding、商品URL、商品識別子、credentialは送信せず、生provider応答とraw promptを保存していない。

利用者が、電気ケトルは黒いanchorと白いcounterfactual、オフィスチェアは黒いメッシュ背もたれ・ヘッドレスト付きanchorと、非黒色・非メッシュ・ヘッドレストなしの各counterfactualについて条件差を確認した。score前に候補labelをmanifestへ固定した。参照pHashの組内最小距離は電気ケトル20、オフィスチェア6で、重複拒否閾値5を超えた。候補22枚と参照6枚をrepository-local固定ONNXへ4枚ずつ7 batchesで通し、外部通信は行っていない。

較正結果は次のとおりである。

- 電気ケトルの黒色: 正例4、負例6、AUC 1.0、正例中央値 -0.382740777、負例中央値 -1.0、診断閾値 -0.7626390195、balanced accuracy 1.0で条件基準を通過
- オフィスチェアの色: 正例9、負例2、曖昧1。AUC 1.0だが各class最低3件を満たさず不適格
- オフィスチェアのメッシュ: 正例11、負例0、曖昧1で不適格
- オフィスチェアのヘッドレスト: 正例6、負例4、曖昧2、AUC 0.75、正例中央値0.8908343505、負例中央値0.5442160635、診断閾値0.8289868135、balanced accuracy 0.833333で不合格
- 適格なケトル黒色と椅子ヘッドレストのpool: 正例10、負例10、AUC 0.78、正例中央値0.3478864165、負例中央値 -1.0、診断閾値 -0.7626390195、balanced accuracy 0.8、sensitivity 1.0、specificity 0.6で不合格
- オフィスチェアの条件集約: 最小AUC 0.583333333、平均AUC 0.708333333で不合格

この結果から診断閾値を較正済みproduction profileへ昇格せず、`qualified_for_ranking=false` と `COUNTERFACTUAL_RANKING_ENABLED=false` を維持した。独立holdout、本番Cloudflare、製品4方向仕様、state、ledger、history、typed-ranking-v4を変更・実行していない。次の作業は追加生成ではなく、固定artifactによるreference分離と構成不足の診断、および専用属性evaluatorを含む方式再設計である。

artifact存在と失敗判定を要求するREDは結果JSON欠落により1 failedとなり、RED時点のtest SHA-256は `9c8af5ffce49043e23b4263d459fca89fe703bea84034026308598e0014071a7` だった。最終test SHA-256は `e323df29fcbad7bb2065407a70274a096298abac647879f863e940270a8e9038`、manifest SHA-256は `d255f0a1fb9861688ebedd1f38819083b95ebfc809f724761c541950f2659f0e` と `f26f25f061e7f454dfb1329507b75b190bfc18028510009f3cbcdff6d8ca3b71`、結果JSONは `1545b389e4a576929603ec3802c8fffd66bc06e6ac00878064d38bb96c489b52` である。通常testは2 passed・1 deselected、固定ONNXの明示runtime testは3 passedだった。記録同期後はlock 79 packages、Ruff 203 files、Markdown 16 files・1,346 links・944 anchors・1,712 headings・203 fence pairs、offline全体1,761 passed・10 skipped・3 deselected、`git diff --check` が成功した。

## 84. 2026-09-07: 次回再設計の相対合格fallback

利用者判断に従い、次回のcounterfactual再設計後も絶対基準へ届かなかった場合、今回方式と再設計方式のうち精度が高い方をdevelopment `pass` とするfallbackを [EXEC-065](GOAL.md#exec-065-未知の視覚条件に対する条件別counterfactual画像評価) へ追加した。比較対象やlabelを変えて見かけの精度を上げないよう、同一development dataset SHA-256、label SHA-256、評価contract SHA-256、評価件数を必須とした。失敗・欠損を正解へ数えないdecision accuracyを第1指標、pairwise AUCを第2指標、worst-condition AUCを第3指標として辞書順に比較し、完全同値なら変更を増やさない今回方式を選ぶ。

`src/search_v2/counterfactual_selection.py` にstrict frozen metricsと選択結果、純粋なselectorを実装した。両仕様の絶対判定が `fail` の場合だけfallbackを受理し、異なる仕様IDと同一bindingを検証する。選ばれた仕様は `decision=pass`、`selection_basis=relative_development_accuracy`、`eligible_for_independent_holdout=true` になるが、`qualified_for_ranking=false` を固定する。したがって、この相対合格は独立holdoutへ進む資格だけであり、本番Cloudflare、画像ranking、4方向仕様変更の合格ではない。

REDは新module未実装の `ModuleNotFoundError` でexit 2となり、RED時点のtest SHA-256は `10fa69ad6555847f6f491ea653ea6f1fdec400d3fa6342cca8a9d89f86a070ed` だった。実装後はfocused 8 passed、既存counterfactual関連26 passed・1 deselected、Ruff check・format checkが成功した。最終module SHA-256は `e716d1be1a740e51c90216e0a1800c31be9635fec1d2f9ea5f6d2384d00e6642`、test SHA-256は `28d71cd855dcbe44d5ee1408bfda1e6bcd80012e40c84a1b6e2996895a183cc5` である。記録同期前の標準gateはlock 79 packages、Ruff 205 files、Markdown 16 files・1,347 links・945 anchors・1,713 headings・203 fence pairs、offline全体1,769 passed・10 skipped・3 deselectedで成功した。外部call、画像生成、browser、credential、課金は0で、現在の較正result JSONは `fail` の履歴として変更していない。

## 85. 2026-09-07: 複数適合参照によるcounterfactual再設計と相対合格

[EXEC-065](GOAL.md#exec-065-未知の視覚条件に対する条件別counterfactual画像評価) の初回方式が、条件ごとにdesired anchor 1枚だけを正例参照としていた点を診断した。条件iだけを不成立にしたcounterfactual `n_i` に対し、別条件jのcounterfactual `n_j` は条件iを維持するという既存の人間確認済みreference契約を使い、`P_i = {anchor} ∪ {n_j | j ≠ i}` を正例集合とした。新しいraw marginは `mean(cos(candidate,p), p∈P_i) - cos(candidate,n_i)`、参照距離は `mean(1 - cos(p,n_i), p∈P_i)` とし、距離で正規化して `[-1, 1]` へclampする。条件が1件なら初回方式と完全に一致し、条件名、category、固定類似語、他候補score、labelへ依存しない。

`src/search_v2/counterfactual_redesign.py` にstrict score profileと純粋scoreを追加した。condition/reference binding、参照順、pixel digest、固定CLIP runtime、候補と参照の非同一性を再検証し、画像欠損は `missing`、数値的に分離しない参照は `unknown` とする。全結果の `qualified_for_ranking` とmodule定数はfalseである。REDはmodule未実装の `ModuleNotFoundError` でexit 2となり、RED時点のtest SHA-256は `8b5d3f4de3416cc3f2620422a604305b5f347d9e5c77a4f80a0cbd0763f83019` だった。最終module SHA-256は `bb14c482bb488115ce14adf2f7d8dafec132e2f035cd50b445d949f6f72f28c2`、unit test SHA-256は `ef5e28cea638cfd6bad244817fc5c43d41db8d3c197a31206e33bebb86b7b038` である。

結果artifact欠落を検出する2回目のREDは1 failedだった。同じdevelopment画像、事前固定label、評価contract、20判定を固定ONNXで再計算し、`tests/img/counterfactual-redesign-result.json` へbindingと集計値を保存した。初回方式と再設計のdiagnostic decision accuracyはいずれも16/20、再設計はケトル黒色AUC 1.0を保持し、椅子ヘッドレストAUCを0.75から0.958333333、適格条件pool AUCを0.78から0.84、worst-condition AUCを0.75から0.958333333へ改善した。絶対accuracy 0.90未達と椅子の色・メッシュのclass数不足を残すため、両方式の絶対判定は `fail` とした。同一bindingのselectorは第1指標のaccuracy同値後、第2指標のpairwise AUCで `counterfactual-mean-positive-v2` をdevelopment相対 `pass` とした。これは独立holdoutへの進行資格だけであり、ranking適格ではない。

固定ONNXの対象runtime testは1 passed、counterfactualの非runtime focused testは16 passed・2 deselectedだった。quality test SHA-256は `fd34048450faeb035b47bca4afa6dd1390eaf1c96b68bfa0d13e9370906c046c`、結果JSON SHA-256は `7cfe9c832978608846ee89bce25d19cdafd4003a427b1963977698720118bde0` である。最終標準gateはlock 79 packages、Ruff check・format check 207 files、Markdown focused 4 passed、offline全体1,775 passed・11 skipped・3 deselected、`git diff --check` に成功した。診断用の一時scriptは正式scoreとruntime testへ置き換えて削除した。本作業の追加外部call、browser、画像生成、credential利用、課金は0であり、既存の初回較正artifact、製品Cloudflare 4方向仕様、state、ledger、history、typed-ranking-v4は変更していない。

## 86. 2026-09-07: minimum-positive v4の実装とdevelopment比較

利用者指示に従い、[EXEC-065](GOAL.md#exec-065-未知の視覚条件に対する条件別counterfactual画像評価) の次方式を固定済みdevelopment画像だけでテストした。最初に設計した参照自己較正は、複数条件で `positive_floor > 0` を同時要求できないため、数値guardをcalibration spanへ限定して実装した。しかし固定ONNXではhard clampにより椅子ヘッドレストAUCが0.5、適格条件pool AUCが0.72へ悪化した。hard clampを単調な非有界変換、tanh、rational変換へ置き換える診断でもpool AUC 0.84、accuracy 16/20でmean-positive v2を上回らなかったため、参照自己較正を棄却した。

改善していた最小正例marginだけをv4として固定した。条件iの正例集合をdesired anchorと条件i以外のcounterfactualとし、候補とのcosine最低値から条件iの負例cosineを引く。分母は全正例と負例の平均参照距離、clampは `[-1, 1]`、数値guardは `1e-6` とする。条件1件では初回式と完全に一致し、条件名、類似語、category、label、他候補scoreへ依存しない。既存embeddingから最低値を選ぶだけで、画像、provider call、CLIP推論を追加しない。

`src/search_v2/counterfactual_v4.py` にstrict profile digestと純粋scoreを実装した。condition/reference binding、参照pixel digestと順序、固定CLIP runtime、候補と参照の非同一性を再検証し、画像欠損を `missing`、参照分離不足を `unknown` とする。全出力とmodule定数はranking不適格を維持する。最初のREDはmodule未実装の `ModuleNotFoundError` でexit 2となり、RED時点のtest SHA-256は `0abc01ad22f01f38f42afe1b7d705ce06c7dcdfc68385a632e05a934d88fd25d` だった。自己較正棄却後のtest変更も旧exportに対するImportErrorを確認してから最小正例実装へ進んだ。最終module SHA-256は `4f6edd37f58f89c81b033ca779ec8a633054974b06d4943c767bd21620e49663`、unit test SHA-256は `38fafd5ca47cd80f370f0b44c0c3285ec77c11dcddbcff281b7f95a0cc8ab563` である。

結果artifact欠落のREDは1 failedだった。`tests/img/counterfactual-v4-result.json` は前回と同じdevelopment dataset・label・評価contract digest、20判定、外部call 0へv2とv4を結ぶ。固定ONNX再計算でv4はケトル黒色と椅子ヘッドレストがともにAUC 1.0、適格条件pool AUC 0.93、accuracy 17/20、balanced accuracy 0.85、sensitivity 0.9、specificity 0.8となった。mean-positive v2のpool AUC 0.84、accuracy 16/20、worst-condition AUC 0.958333333に対し、v4は0.93、17/20、1.0で全比較指標を改善したため、第1指標accuracyでdevelopment相対 `pass` とした。

v4も絶対accuracy 0.90へ届かず、椅子の色は負例2件、メッシュは負例0件で構成不適格のままである。`qualified_for_ranking=false` とし、独立holdout、本番Cloudflare、製品4方向仕様、state、ledger、history、typed-ranking-v4へ接続していない。unit・binding・selector focusedは14 passed、固定ONNXの正式runtime testは1 passedだった。quality test SHA-256は `f7d00e4c5d714f010f1e5ff89278e40d793c47edc993544f30f19b6dc86f68e3`、結果JSON SHA-256は `bf380619f0792c53ee1539d99330535c4054283998d2e9ca60df1de4fd9db3ce` である。最終標準gateはlock 79 packages、Ruff check・format check 209 files、offline全体1,781 passed・12 skipped・3 deselected、`git diff --check` に成功した。診断用一時scriptは正式実装・testへ置き換えて削除した。追加外部call、browser、画像生成、credential利用、課金は0だった。

## 87. 2026-09-07: minimum-positive v4のlabel-free batch較正

共通診断閾値 `-0.47284997230807874` で誤った3件を固定ONNXで再抽出した。ケトル黒色の正例1件が偽陰性、椅子ヘッドレストなしの負例2件が偽陽性だった。一方、条件別では両方ともAUCとbalanced accuracyが1.0で、最適閾値がケトル `-0.7626390193398531`、ヘッドレスト `-0.08483346029019756` と離れていた。このため順位分離ではなく条件間のscore位置差を原因とした。

条件別の固定閾値表や正解labelを使わず未知条件にも同じ処理を適用するため、`counterfactual_calibration.py` を追加した。同じcondition・reference・minimum-positive profile・固定runtimeへ結ばれた完全な4〜32候補だけを受け、候補digestの一意性も検証する。各条件の観測最小値・最大値の中点をcenter、半幅をscaleとして `clamp((score - center) / scale, -1, 1)` へ写し、全条件の共通decision thresholdを0とする。観測幅 `1e-6` 未満、または元scoreが0を跨がず同じ飽和端点の2候補以上の支持もない片側連続分布は較正せず、`insufficient_span` または `insufficient_diversity` を返す。全出力はranking不適格のままである。

最初のREDは新module欠落によるcollection errorでexit 2、RED test SHA-256は `74acaa8e84661f04039ea87a5a1ac6968e9c86eae38a349d95503ab6befcbcfa` だった。実装後のfocused testは6 passed、counterfactual関連の通常testは24 passed・3 deselectedとなった。最終コードの固定ONNX明示runtime testは1 passed、36.36秒で、較正に正解labelを入力せずケトル黒色と椅子ヘッドレストを各10/10、適格条件全体を20/20、pool AUC 1.0として再現した。単一classの椅子メッシュは `insufficient_diversity`、色・メッシュの品質評価はclass数不足で不適格のままである。

最終module SHA-256は `01e7dc1284187ab3f01d4548c7364e090c2c5eb42e394703f9881076e027d873`、test SHA-256は `8bc8c44a290dbb0d1a1dc619fedf0a98718dbc212ff9958546cdbe8134d4fe8f`、結果artifact SHA-256は `0756f9eb2c20e9b4721b8a6b6253c18629443e69d1ad6e9bbcd345882127afc7` である。標準gateはlock 79 packages、Ruff check、Ruff format 211 files、offline全体1,788 passed・12 skipped・3 deselected、Markdown test 4件、`git diff --check` が成功した。外部通信、browser、Bonsai、Outscraper、Cloudflare、gpt-image、credential、課金、追加生成は実行していない。

これは同じdevelopment setへ適合した相対改善である。候補集合の最小・最大に依存するため、outlier、単一class、候補構成変化、未知category・条件への一般化は証明していない。色・メッシュのclass不足と独立holdout未実施により絶対判定は `fail`、画像ranking、本番Cloudflare、4方向製品仕様は変更しない。次は使用済み条件を除外し、単一classとoutlierも含めた独立holdoutを取得・生成前に固定する。

## 88. 2026-09-07: 未知のデスクライト・クランプ条件による独立1-case probe

[EXEC-065](GOAL.md#exec-065-未知の視覚条件に対する条件別counterfactual画像評価) のdevelopment相対合格後、過去に使っていないデスクライトcategoryと「机の端を挟むクランプ式」を独立1-case probeとして固定した。利用者の明示承認後、fresh profileの隔離Chromiumでtop-level navigation 1回、送信前上限100件、retry 0のcategory検索を実行した。外部要求100件を送信し、追加40件は送信前に遮断した。商品detail、login、既存Cookieは使わず、URL、商品名、商品識別子、raw DOM、Cookie、生responseを保存しなかった。候補12枚を512×512 PNGへ正規化し、match 3、mismatch 5、ambiguous 4をCLIP実行前に固定した。

候補画像を入力せず、テスト専用gpt-imageをexact 2 calls・retry 0で利用した。desiredはdesk edgeを上下から挟むscrew clamp、counterfactualは同じlampのclampだけをfreestanding weighted baseへ置換した画像である。利用者が条件差を確認し、pHash距離14で重複閾値5を超えることを確認した。本番Cloudflare、repository credential、候補画像・embeddingの外部送信は行っていない。

固定ONNX、minimum-positive v4、既存label-free batch較正、共通閾値0を変更せず、参照2枚と候補12枚へ適用した。較正はlabelを使わず全12候補を対象とし、observed range `-1.0` から `0.4920875621654818`、center `-0.2539562189172591`、half span `0.7460437810827409` で成立した。固定label 8件ではmatch 3/3、mismatch 4/5、accuracy 7/8 = 0.875、pairwise AUC 1.0だった。順位は完全分離したが共通閾値0でmismatch 1件を偽陽性にしたため、AUC 0.80とaccuracy 0.90のAND基準へ届かず `fail` とした。ambiguous 4件は較正分布へ含め、正解率の分母から除外した。

| コマンドまたは方法 | 実行理由 | 実行結果 | 実行結果から分かること |
|---|---|---|---|
| 隔離Chromium CDP collector | 送信前要求上限を強制し、未知categoryの候補画像を実browserから得る | navigation 1、送信100、送信前遮断40、候補12、retry 0 | 既存Cookieや商品detailを使わず、承認済み上限内で候補を取得できた |
| テスト専用gpt-image 2 calls | 候補と独立したdesired・counterfactual pairを作る | 2/2成功、retry 0、人間確認済み、pHash距離14 | 条件差がclampとfreestanding baseとして目視可能で、候補画像はgeneratorへ送られていない |
| 一時local evaluator | 固定runtimeでscoreと較正を初回計算する | 最初のfile起動はmodel読込前のimport error、module起動は終了0 | 外部再試行なしで集計値を取得でき、起動失敗は評価結果へ影響していない |
| `pytest -q tests/test_search_v2_counterfactual_quality.py -m 'not clip_runtime'` | manifest・固定label・集計・安全境界をmodelなしで確認する | 6 passed / 4 deselected | 保存artifactと不合格判定が固定された |
| `pytest -q tests/test_search_v2_counterfactual_quality.py::test_unknown_condition_holdout_matches_fixed_clip_runtime -m clip_runtime --run-clip-runtime` | 同じ画像から集計値を再計算する | 1 passed / 20.59s | 手動集計と固定runtime回帰が一致した |

quality test SHA-256は `f723154295c1c00f32e9c8b0ab833cebd1e2f03942fe8bf2558378f9f65d4db9`、collectionは `af1f880c0625fc8fc6fe497461efb357b6291fc11c4f0eb801a4e1bdd42613cb`、labelsは `a72d26c4ac571e2d0176a49f70efef6e4f18a919f62f7710a5376b6a1a12890e`、referencesは `430e063cd49c55b89730f62f07e7afa9d45b62b102225e888fb0ead67d523a3e`、aggregate resultは `20273de56fd73de6e68a1a18065d5fb4b360ac03bc2197eb756fe28c98b7a24f` である。最終gateはlock 79 packages、Ruff check、Ruff format 211 files、Markdown link test 4 passed、offline全体1,789 passed・13 skipped・3 deselected、`git diff --check` が成功した。一時collector・evaluatorと生成したbytecodeは削除した。結果artifactには候補別score、URL、商品名、商品識別子、生provider情報を保存していない。これは最低2 category・各2 caseの最終holdoutではなく、画像ranking、本番Cloudflare、4方向製品仕様は無効・未変更のままである。

## 89. 記録規則

- 日付、コミットID、変更ファイル、実行結果のいずれかで確認できる事実を書く
- コミットメッセージにない動機を推測しない
- 外部APIを実行していない場合、実サービスで確認済みと書かない
- シークレット、利用者入力、商品結果、キャッシュ内容を記録しない
- 予定、優先度、担当は履歴に混ぜず、対応する管理文書へ置く
- 未コミット変更はその旨を明記し、コミット後にIDを追記できる
- 巻き戻しや置換があった場合も、履歴を消さず後続項目で説明する


## 統合済みプロジェクトメモリ

> 統合元: `docs/MEMORY.md`。統合前の文書は `docs/old/` に保存する。


> **標準文書との関係:** この文書は安定した補助知識であり、作業指示ではない。開発規則は [DEVELOPMENT.md](DEVELOPMENT.md)、現在のゴールは [GOAL.md](GOAL.md)、履歴は [WORKLOG.md](WORKLOG.md) を正本とする。

### 1. 目的

この文書は、amazon-explorer を長期的に保守するために維持すべき、変化しにくい知識だけを記録する。日々の進捗は [WORKLOG.md](WORKLOG.md)、未完了作業は [TODO.md](GOAL.md#統合済み小規模タスク一覧) と [TASKS.md](GOAL.md#統合済み大規模タスク一覧)、問題は [ISSUES.md](ISSUES.md) を使う。

一時的な調査結果、個人環境の絶対パス、シークレット、利用者入力、実キャッシュ、期限付きの担当者情報はここへ保存しない。

### 2. プロダクトの目的と範囲

amazon-explorer は、日本語の自然文から Amazon.co.jp の商品候補を取得し、条件への近さで順位付けするPythonアプリケーションである。

現行の中核機能:

1. ローカルBonsai OpenAI互換APIによる商品属性抽出
2. Outscraper Amazon Products APIによる候補取得
3. 外部レスポンスの内部モデルへの正規化
4. SudachiPyとTF-IDF、条件一致、価格、否定条件による採点
5. Streamlit UIとCLIからの実行
6. 段階ごとのローカルJSONキャッシュ

画像生成、画像類似度、ComfyUI、SSH連携、アプリ独自の認証、バックグラウンドジョブは現行機能ではない。次期商品検索の利用者向け操作は [SEARCH-FLOW.md](../SEARCH-FLOW.md)、技術契約は [BACKEND.md](BACKEND.md#13-次期検索バックエンド-v2基盤を一部実装) と [REQUIREMENTS.md](REQUIREMENTS.md#35-次期検索フロー-v2) で管理する。現行Bonsai属性抽出を正本とし、provider未接続の基盤実装が存在しても、現行検索、外部API、永続repository、画面、画像、ranking v3まで接続済みとは説明しない。

### 3. 権威ある情報源

変更時は、説明文より次の実装を優先して確認する。

| 知識 | 正とする場所 |
|---|---|
| 依存関係とPython要件 | `pyproject.toml` と `uv.lock` |
| 設定名、既定値、値制約 | `src/config.py` |
| 内部データモデル | `src/schemas.py` |
| パイプライン順序とキャッシュキー | `src/main/run.py` |
| Bonsai通信 | `src/clients/bonsai_client.py` |
| Outscraper通信とURL検証 | `src/clients/outscraper_client.py` |
| キャッシュのパス検証とTTL | `src/repositories/cache_repository.py` |
| UI表示とセッション状態 | `src/ui/streamlit_ui.py` |
| 現行動作の回帰保証 | `tests/` |
| 次期商品検索の利用者フロー | ルート `SEARCH-FLOW.md` |
| 次期商品検索の技術契約 | `docs/BACKEND.md`、`docs/REQUIREMENTS.md`、`docs/SECURITY.md` |
| テスト方針と受入確認 | `docs/DEVELOPMENT.md` の「統合済みテスト方針」 |

文書と実装が違う場合は、コードとテストで現状を確認し、同じ変更で文書を更新する。

### 4. アーキテクチャ上の境界

- `src/clients/`: 外部HTTPサービスとの通信とレスポンス形状の一次検証
- `src/services/`: 属性補正、検索語選択、商品正規化、テキスト処理、採点
- `src/repositories/`: キャッシュの保存先、TTL、読込失敗の扱い
- `src/main/run.py`: 4段階の検索を統合する唯一の共通入口
- `src/ui/`: Streamlit固有の状態と表示
- `src/schemas.py`: サービス間で渡すPydanticモデル
- `src/config.py`: 環境依存設定と値制約
- `src/paths.py`: リポジトリルートを基準にしたパス

StreamlitとCLIは同じ `run_product_search()` を呼ぶ。外部レスポンスをUIや採点へ直接渡さず、正規化したモデルを境界にする。

### 5. データフローの不変条件

```text
user_input: str
  -> Bonsai content: str
  -> ProductAttributes
  -> Outscraper query: str
  -> Outscraper response: dict
  -> list[NormalizedAmazonProduct]
  -> list[ProductScore]
```

- 空の利用者入力は外部通信前に拒否する
- Bonsaiの生応答を解析できないとき、生の内容を利用者向け例外へ含めない
- Outscraperの `data=[]` は正常な0件である
- 正規化ではタイトルのない商品と、明示通貨がJPY・USD以外の商品を除く
- USD価格は設定された固定 `USD_TO_JPY_RATE` で円換算する
- 採点結果は総合スコアの降順で返す

フィールドの完全な定義は [DB-SCHEMA.md](DB-SCHEMA.md)、計算方針は [BACKEND.md](BACKEND.md) を参照する。

#### 商品検索LLMのprovider決定

- 商品検索の正本は、現行 `run_product_search()` が使うローカルBonsai OpenAI互換APIである
- 2026-08-16に検討したOpenAI Responses API / Structured Outputsの商品検索採用案は、2026-08-19の明示決定で置換済みである
- `src/search_v2/` の存在をOpenAI移行済みの根拠にしない。`intent.py` と `query_planner.py` はprovider非依存、`bonsai_adapter.py` はnetwork非依存のBonsai応答境界であり、いずれも現行pipelineへ未接続として扱う
- 商品検索失敗時にOpenAIへ自動fallbackしない。provider変更は明示決定、互換adapter、回帰テスト、cache移行を伴う別変更にする
- AIレビューハーネスのOpenAI利用は別システム境界であり、この商品検索provider決定では変更しない

### 6. キャッシュの基本知識

キャッシュは `CACHE_DIR`（既定 `cache/`）の下に段階別JSONとして保存する。

```text
product_attributes/
outscraper/raw/
outscraper/normalized/
outscraper/scored/
```

- 属性抽出には既定24時間、Outscraper生レスポンスには既定1時間のTTLがある
- 正規化と採点は内容および設定を含むキーで再利用し、読込TTLはない
- Streamlitはセッションごとのランダムscope、CLIは `local-cli` scopeをキーへ含める
- scopeは認証や認可ではない
- `--no-cache` と `use_cache=False` は読込だけを止め、新規結果は保存する
- JSON書込は一時ファイル、flush、`fsync`、置換の順で行う
- キャッシュキーは結果に影響する入力を含むが、APIキーは含めない

キャッシュの削除は利用者データの削除になり得る。対象を確認せず一括削除しない。

### 7. セキュリティ上の不変条件

- `.env`、`.streamlit/secrets.toml`、`cache/` はGitへ追加しない
- APIキーをURL、キャッシュキー、payload、画面、文書、テストデータへ入れない
- Outscraper endpointと結果URLはHTTPSを必須とする
- `results_location` はendpointと同じホスト・実効ポートだけを許可する
- APIキー付きリクエストのリダイレクトを許可しない
- UIは詳細例外をサーバーログへ残し、利用者には固定メッセージを表示する
- Streamlitセッションscopeをアクセス制御として扱わない

詳細と公開前の条件は [SECURITY.md](SECURITY.md) を参照する。

### 8. 開発と検証

依存関係は `uv` で管理する。`uv sync --locked` は環境準備として分け、その後の標準検証は外部通信を許可せずに実行する。

```sh
uv sync --locked
uv lock --check --offline
uv run --frozen --offline --no-sync ruff check .
uv run --frozen --offline --no-sync ruff format --check .
uv run --frozen --offline --no-sync pytest -m 'not live_api'
git diff --check
```

Pythonコードの変更では関連する単体テストを追加・更新する。外部APIを使う結合確認は、モックによるテストと区別し、Bonsai起動状態、Outscraper APIキー、課金、待ち時間を確認してから行う。

`tests/` は現行 `src/` を直接検証する。`docs/old/examples/` は開発段階の旧コードを保存した参照資料であり、現行仕様や回帰テストの対象ではない。

### 9. 変更時に同時更新するもの

| 変更 | 同時に確認するもの |
|---|---|
| 設定の追加・既定値変更 | `src/config.py`、`.env.example`、[CONSTRAINTS.md](REQUIREMENTS.md#統合済み制約)、テスト |
| モデル変更 | `src/schemas.py`、[DB-SCHEMA.md](DB-SCHEMA.md)、キャッシュ互換性、テスト |
| 外部API変更 | client、[BACKEND.md](BACKEND.md)、[SECURITY.md](SECURITY.md)、モックテスト |
| UI変更 | `src/ui/streamlit_ui.py`、[FRONTEND.md](FRONTEND.md)、[UI.md](FRONTEND.md#統合済みui設計)、テスト |
| キャッシュキー変更 | `src/main/run.py` のキャッシュ版、保存互換性、テスト |
| 運用上の制約変更 | [CONSTRAINTS.md](REQUIREMENTS.md#統合済み制約)、[TROUBLESHOOTING.md](DEVELOPMENT.md#統合済みトラブルシューティング) |

### 10. この文書の更新基準

長期間維持する設計判断または安全上の不変条件が変わった場合だけ更新する。次はこの文書へ入れない。

- 今日だけ必要なコマンド出力
- 未検証の推測
- 一時的な障害や個別Issueの経過
- 進行中タスクのチェックリスト
- APIキー、検索語、商品結果、個人環境の絶対パス

履歴的事実は [WORKLOG.md](WORKLOG.md)、参照元は [REFERENCES.md](REFERENCES.md) へ分離する。


## 統合済み履歴Plan EXEC-001

> 統合元: `docs/old/plans/EXEC-001-AI-REVIEW-TDD-HARNESS.md`。統合前の文書は `docs/old/` に保存する。


> **履歴資料:** このPlanは2026-08-15のTASK-006 bootstrap時点を記録する。本文の「未実装」「禁止」「保留」は当時の状態であり、現行要件ではない。現在のattested境界と残作業は [EXEC-002](GOAL.md#exec-002-attested-ai-review境界の実装)、実行可否と手順は [HARNESS-RUNBOOK.md](HARNESS-RUNBOOK.md) を正とする。

### メタデータ

- タスクID: `TASK-006`
- 状態: 完了（TASK-006時点の履歴。attested境界は当時未完・保留）
- 作成日: 2026-08-15
- 最終更新日: 2026-08-16（history-only notice追加）
- 基準commit: `2fd9c5b1c12efbcf14172d62ad23341291292a3a`
- 関連規約: [PLANS.md](DEVELOPMENT.md#統合済みexecution-plan規約)、[AI_GUIDE.md](DEVELOPMENT.md#統合済みaiレビュー規約)
- 関連負債: [TD-009](ISSUES.md#td-009-ai変更の役割分離と証拠契約)
- 解決対象: [ISS-001](ISSUES.md#iss-001-デバッグ表示に2つの条件語重みがない)、`TODO-002`、`TODO-003`、`TODO-004`

### 目的

以下の目的と境界はTASK-006実施時点のものである。

AIを利用する変更で実装者の自己評価だけに依存せず、次を再現可能な証拠へ結び付ける安全側MVPを導入する。

1. 変更前にraw task、要求、許可範囲を固定する。
2. REDからGREENまでを同じcandidateとテスト内容へ固定する。
3. 安価で決定論的なゲートをAIの意味レビューより先に通す。
4. reviewerとadversaryを分け、同じcommit差分をstructured JSONで評価する。
5. provenanceがattestされない間は自動 `pass` を禁止し、人間承認へ戻す。

このPlanの「安全側MVP完了」は、fail-closedな契約、policy、judge、dry-run、オフラインテストを整えたことを指す。外部AIを安全に起動できるという意味ではない。2026-08-15の完了時点では、import前の外部trust anchor、別UID所有のread-only snapshot/clone、コンテナによるOS read/network隔離、coordinator attestationは未実装であり、attested自動実行を保留した。

### 対象範囲

- `tools/ai_review/` のPydantic契約、パス安全性、差分policy、決定論的judge、zipapp builder、実行無効のCodexアダプター、CLI
- `specs/schemas/` のtask、policy、gate、review、TDD evidence、verdictの6 JSON Schema
- `specs/prompts/` の独立reviewer / adversary prompt
- `specs/tasks/` のtask例と `TASK-006` 契約
- 通常pytestのPython network monkeypatch guardと `live_api` の二重opt-in
- GitHub Actionsのlock、Ruff、offline pytest、diff check
- Streamlitデバッグ表示、表示整形、検索語fallback、APIキー欠落経路の回帰テスト
- [AI_GUIDE.md](DEVELOPMENT.md#統合済みaiレビュー規約) と関連管理文書

### 対象外

- ブックマーク表示数を変更するプルダウンの追加
- 既存の検索結果表示件数スライダーの用途変更
- 削除済みPDFの復元または参照
- Codexその他の外部AIサービスの実行
- Bonsai、Outscraper、Amazonへの実通信
- standalone isolated clone、2つのAIレビュー、RED/GREEN証拠runnerの自動起動
- AI判定によるcommit、push、merge
- 別UID/read-only external preflight、コンテナ、network namespace、firewall、coordinator署名

対象外を変更する場合は、このPlan、task JSON、セキュリティ条件を人間が承認した別のExecution Planで扱う。

### TASK-006完了時点の状態

基準commitにはAIレビュー契約、実行コード、CI、network guardが存在しなかった。TASK-006当時の作業ツリーでは次を実装した。

- 6つのstructured JSON契約は未知fieldと型coercionを拒否する。
- raw task SHA-256をpolicy、review、gate、TDD evidence、verdictへ結び付ける。
- gateをcandidateのheadとcanonical diff SHA-256へ結び付ける。
- test manifestをpolicy内のtest file content SHA-256からjudgeが再構築する。
- test受入ごとにREDの許容終了コードとfailure fingerprint SHA-256をtaskへ固定する。
- candidateをlinked worktreeではなく、`git clone --no-local` または `--no-hardlinks` でlocal hardlink最適化を避けたstandalone isolated cloneに限定する。
- policyはgit-dir/common-dirが独立した `.git` directoryへ一致することを要求し、`commondir`、`worktrees`、attributes、alternates/http-alternates、metadata tree内のsymlink/hardlink/nested mount/特殊file/所有権・書込権限をfail closedで検査する。
- policyはSHA-1 repositoryだけを許可し、base/head commit、到達tree、変更前後blobをGit header込みで再hashしてobject IDとの一致を要求する。
- policyはbase直系の単一canonical commit、Git設定、metadata、scope、保護path、file type、byte/line/file上限をfail closedで検査する。
- policyはcontent/numstat処理後にもHEAD、replace refs、index/worktree、base/head commit、到達treeを再検査する。ただし同UIDのwritable candidateでは、検査中に一時差替えを戻す競合とreturn後のTOCTOUが残る。
- exact blob copyは拒否する。内容を変更したcopyはsimilarity推測を使わずnew addとして扱う。
- `.env.example` を含む `.env*`、Streamlit secrets、`.git`、`cache` の変更を保護する。
- judge CLIは保存済みpolicyを信用せず、現在のcandidate repositoryへpolicyを再実行して完全一致を要求する。
- provenanceが自己申告である間は自動 `pass` を返さない。
- Codexアダプターはdry-run専用で `--execute` を拒否する。
- pytestはcollection前から通常のPython socket、名前解決、Requests経路をmonkeypatchする。

zipapp内部のSHA-256検査は候補内/source-treeからの誤起動を検出する補助である。ハーネスmodule import後に検査するためtrust anchorではなく、attestationとして扱わない。候補内Python、候補内 `.venv`、source-treeの `python -m tools.ai_review`、直接 `PYTHONPATH` を設定する起動は正規運用にしない。

pytest guardもOSレベルの遮断ではない。subprocess、raw file descriptor、native code、plugin早期import、候補差分によるguard改変を完全には止めない。`network_policy=deny` は契約であってnetwork namespaceではない。

### 実行内容

#### 1. taskと証拠binding

- raw task bytesのSHA-256を実装前に候補外で固定する。
- `base_sha`、要求ID、review prompt digest、candidate commit metadata、受入、allowed / denied path、変更上限、RED終了コード/fingerprint、対象外をtaskへ固定する。
- review、gate、TDD evidence、verdictへ同じraw task SHA-256を必須にする。
- reviewerとadversaryへ同じbase/head/canonical diffを要求する。
- gateへhead/candidate digest、TDDへcontent由来test manifestと同一test patchを要求する。

#### 2. candidate policyとjudge

- `--no-local` または `--no-hardlinks` で作ったstandalone isolated cloneのcleanなHEADだけを評価する。
- 外部git-dir/common-dir、共有metadata、attributes/alternatesとmetadata tree内link/mountを拒否する。
- commit/tree/blobをGit header込みで再hashし、canonical candidate digest内のobject IDと実内容を束縛する。
- base直系1件のcanonical squash commitとtask固定metadataを要求する。
- 保護対象を検出したらblob本文を読まず、canonical diffを生成せず停止する。
- exact blobのrename/copy、delete、mode/type変更、binary、symlink、gitlinkを拒否する。
- judge時にcandidateのcurrent HEADをpolicyで再検査し、保存済みpolicyとの完全一致を要求する。
- policy末尾でHEAD、replace refs、index/worktree、commit/treeを再検査するが、attested運用では別UIDのread-only snapshot/cloneを追加条件にする。
- critical/high、accept以外、契約不一致、役割不備はfailとし、それ以外もattestation実装まではhuman reviewとする。

#### 3. TDDパイロット

- UIデバッグ表示の不足をテストでREDにし、同じテストでGREENにした。
- 検索語fallbackの検証迂回をテストでREDにし、共通validatorへ集約してGREENにした。
- APIキー欠落がHTTP要求前に停止する既存安全性をcharacterization testで固定した。

#### 4. networkとCI

- 通常pytestでは `live_api` を除外し、Python通常経路の通信をmonkeypatchで失敗させる。
- live testはmarkerと `--run-live-api` の二重opt-inにする。
- CIはPython 3.10 / 3.13 matrix、locked sync、Ruff、offline pytest、diff checkを定義する。
- hash処理はPython 3.10にない `hashlib.file_digest()` を使わずchunk読込にした。ただし今回のローカル環境ではPython 3.10 interpreterによる実行は未確認である。

### 進捗

以下の未チェック項目はTASK-006当時の移管項目であり、現在の未実装一覧ではない。後続の達成状況と残作業は [EXEC-002](GOAL.md#exec-002-attested-ai-review境界の実装) を参照する。

- [x] task、policy、gate、review、TDD evidence、verdictのモデルと6 schemaを追加した。
- [x] raw task、candidate、gate、TDD、reviewのbindingを強化した。
- [x] standalone clone、外部/共有Git metadataとmetadata link/mountの拒否、Git object再hash、current policy再検査、exact copy、保護pathのfail-closed testを追加した。
- [x] Codex実行と自動 `pass` を禁止し、zipapp内部検査の限界を明確化した。
- [x] network monkeypatch guard、live二重opt-in、CI定義を追加した。
- [x] TDDパイロットと関連文書を追加した。
- [ ] import前に別UID/read-onlyでarchiveとPythonを検証する外部preflightを実装する。
- [ ] policy return後もcandidateを書換不能にする、別UID所有のread-only snapshot/cloneを実装する。
- [ ] 候補から解除できないcontainer read/network isolationを実装する。
- [ ] reviewer / adversaryの起動、RED/GREEN/gate採取、署名付きprovenanceをcoordinatorでattestする。
- [ ] attestedな自動実行の設計を独立監査し、人間が再承認する。

### TDD証拠

| 対象 | テストSHA-256 | RED | GREEN / 固定結果 |
|---|---|---|---|
| Streamlitの全採点重みと表示整形 | `042ad1b2cd8307afe40787bd53510d4cb55f66914548adf9ed76b57b8306ac4c` | `tests/test_streamlit_ui.py` で色・特徴語重みの不足を再現 | 2項目追加後に同じtest contentで成功 |
| Outscraper検索語fallback | `c6c60c698d7cb3074721c07f04d853c5c742e6ab157fcf5697995ad5df889189` | 空文字・URL fallbackの検証迂回を再現 | fallbackも `validate_search_query()` を通して成功 |
| APIキー欠落時の通信抑止 | 現行test content | 新規不具合修正ではないためREDなし | `RuntimeError` と取得関数未呼出を確認 |

RED/GREENの全文ログはGit管理対象へ含めない。上表は実施時の要約であり、test content hashやcandidate digestが変わった将来変更へ証拠を流用しない。

### 検証方針

最終テスト件数は固定値として文書へ埋め込まない。共有ツリーの最終状態に対して次を再実行し、0終了と未実行境界をhandoffで報告する。

```sh
uv run pytest tests/test_ai_review_harness.py tests/test_network_policy.py -m 'not live_api'
uv run pytest -m 'not live_api'
uv run ruff check .
uv run ruff format --check .
uv lock --check
git diff --check
```

GitHub ActionsのPython 3.10 / 3.13 job、外部Codex、Bonsai、Outscraper、実networkはローカル確認に含めない。Python 3.10互換のhash APIへ修正済みだが、3.10実行結果はGitHub Actionsまたは別の3.10環境で確認する。

### セキュリティ判断

次表はTASK-006当時の判断と見直し条件である。見直し後の現行判断は [EXEC-002の判断記録](GOAL.md#判断記録) を正とする。

| 判断 | 理由 | 見直し条件 |
|---|---|---|
| candidateは `--no-local` または `--no-hardlinks` のstandalone isolated cloneに限定する | linked worktree、external common-dir、local clone hardlinkはGit metadata/objectを共有する | 独立性を同等以上に証明する別方式を敵対的テストで確認した場合 |
| zipapp内部hashをtrust anchorにしない | 検査より前にarchive codeがimportされる | import前の候補外preflightが実装・監査された場合 |
| Codex実行、自動 `pass`、attestationを禁止する | 別UID/read-only preflight、return後も不変なsnapshot、container隔離、署名付きprovenanceがない | 4条件を実装し独立監査と人間承認を終えた場合 |
| exact blob copyだけをcopyとして拒否する | Git similarity heuristicを証拠契約に使わない | copy定義と検出方法をtask/schema/testへ固定できた場合 |
| network monkeypatchを補助とする | Python通常経路の外をOSで遮断しない | container/network namespace等を候補から解除不能にした場合 |
| 全verdictで人間承認を必須にする | 機械規則とAIレビューは目的・有用性・残余リスクの責任を代替しない | 現行では見直さない |

### 発見事項

以下はTASK-006 bootstrap時点の発見事項である。

- TASK-006のbaseにはtrusted harnessがなく、このbootstrap変更自身にattestedなcandidate policy / verdictを生成できない。
- zipappの自己検査は誤起動には有効だが、外部trust anchorという以前の想定を満たさない。
- 保存済みpolicyだけをjudgeへ渡すとcandidate差替えを検出できないため、current repositoryの再検査が必要だった。
- policy末尾のHEAD / replace refs / index / worktree再検査でも、同UIDで検査中だけcandidateを差し替えて戻すraceとreturn後のraceは残る。attestationには別UIDのread-only snapshotが必要である。
- standalone cloneでもlocal cloneのhardlink最適化やGit metadata内の外部参照を許すと、候補外の変更が検査対象へ影響するため、`--no-local` / `--no-hardlinks` とmetadata tree検査が必要だった。
- canonical digestがblob IDだけを含む場合、object file名と内容が一致することが前提になる。SHA-1 object header込み再hashとloose blob/commit/tree改ざんの回帰テストでこの前提を検査する必要があった。
- test path名だけのmanifestでは内容差替えを検出できないため、policyのcontent SHA-256から再構築する必要があった。
- REDの任意失敗を証拠にできないよう、許容終了コードとfailure fingerprintをtaskへ固定する必要があった。
- `.env.example` はアプリ利用者向けの空templateであっても、AI coordinatorでは環境file名として保護する必要がある。

### ロールバック

このPlanの変更はアプリの永続データ移行を伴わない。取り消す場合は対象commitを通常のGit手順でrevertし、次を確認する。

1. 利用者の未コミット差分を巻き込まない。
2. `.env`、`.env.example`、`cache/` の内容を表示・削除しない。
3. 追加テストを単に消して安全性を見かけ上回復させない。
4. CI、network guard、ハーネス、6 schema、task、文書を同じ変更で整合させる。
5. offline gateと文書リンクを再検証する。

### 結果

2026-08-15時点で安全側MVPを完了した。strictな6 JSON契約、raw task / candidate / gate / TDD binding、standalone clone policy、current repository再検査を行うjudge、実行無効のCodex dry-run、補助的network guard、CI定義、TDDパイロット、運用文書をそろえた。

同日の完了時点ではattested自動実行を未完・保留とし、外部Codex、Bonsai、Outscraper、実networkを実行しなかった。そこで移管したpreflight、snapshot、OS隔離、broker、署名、attested judgeの現行実装と、supported production一括運用・配備の残りは [EXEC-002](GOAL.md#exec-002-attested-ai-review境界の実装) に記録する。


## 統合済み履歴Plan EXEC-003

> 統合元: `docs/old/plans/EXEC-003-SEARCH-FLOW-V2-BACKEND.md`。統合前の文書は `docs/old/` に保存する。


### メタデータ

- 状態: 完了（OpenAI商品検索接続案は後続決定で置換済み）
- 作成日: 2026-08-16
- 最終更新: 2026-08-19
- 関連要件: [SEARCH-FLOW.md](../SEARCH-FLOW.md)、[REQUIREMENTS.md](REQUIREMENTS.md)
- 関連タスク: [TASK-008](GOAL.md#task-008-次期検索フロー-v2-の実装)
- 関連負債: [TECH-DEBT-TRACKER.md](ISSUES.md#統合済み技術的負債トラッカー)

### 目的

2026-08-16時点では、現行バックエンドの観察可能な挙動をcharacterization testで固定した上で、次期検索フローの最初の決定的な境界として、OpenAI Structured Outputsを受けるstrict intentモデル、入力正規化、最大2件の検索query planをTDDで実装することを目的とした。現行のBonsai・Outscraperパイプラインは変更せず、移行前後の契約を同時に検証できる状態にした。

### 後続決定（2026-08-19）

商品検索のLLM経路は、現行 `run_product_search()` が使うBonsaiを正本とする。OpenAI Responses API / Structured Outputsを商品検索へ接続する後続計画は置換済みであり、本Planに残るOpenAIの記述は2026-08-16時点の目的と判断の履歴である。

`src/search_v2/` のstrict model、normalizer、query plannerと対応テストは、外部providerへ接続していない決定的domain基盤として残る。ただし、これらの存在をOpenAIへの移行、または現行検索への接続済み証拠として扱わない。将来この基盤を現行検索へ接続する場合は、Bonsai応答を非信頼JSONとして受けるadapter、既存 `ProductAttributes` / cacheとの互換性、現行characterizationを先に固定する。

この決定は商品検索だけを対象とする。`tools/ai_review/` の独立reviewer / adversaryがOpenAIを使うAIレビューハーネスには適用しない。

### 対象範囲

- 対象:
  - 現行のquery選択、Pydantic互換入力、価格欠損、同点sortのcharacterization test
  - `SearchIntentDraft`、`NormalizedSearchIntent`、価格・曖昧性・provenanceのstrict model
  - Unicode NFKC、空白、空値、重複、明示brand/modelを扱う決定的正規化
  - 日本語1件、英語1件、合計最大2件の決定的query planner
  - 実装、テスト、仕様文書、作業記録の同期
- 対象外:
  - OpenAI、Cloudflare Workers AI、Outscraperの実通信
  - OpenAI Responses API client、承認state machine、画像生成、商品補完、ranking v2
  - 現行 `run_product_search` の切替とUI変更

### 着手時の状態

- `src/main/run.py` はBonsaiで属性を抽出し、`src/services/outscraper_search_select.py` で1件だけqueryを選ぶ。
- `src/schemas.py` の現行modelは入力coercionと未知fieldの無視を許す。
- `src/services/product_scoring.py` は価格欠損を0.0、価格条件なしの既知価格を0.5とし、総合score降順のstable sortを行う。
- [SEARCH-FLOW.md](../SEARCH-FLOW.md) は次期境界をstrict model、決定的最大2queryとして確定していたが、対応するコードはなかった。

### 実行手順

1. 現行挙動だけを呼ぶcharacterization testを追加し、既存コードを変更せず成功させる。
2. 次期model・normalizer・query plannerの期待テストを先に追加し、対象module不在または契約不一致によるREDを記録する。
3. `src/search_v2/` に外部通信を持たないdomain実装を追加し、対象テストをGREENにする。
4. TASK-008とバックエンド資料を実装済み範囲へ同期し、offline全体gateを実行する。

### 進捗

- [x] 2026-08-16: 現行pipeline、schema、query選択、scoring、既存テストを確認した。
- [x] 2026-08-16: 現行挙動のcharacterization testを6件追加し、既存実装のまま成功した。
- [x] 2026-08-16: 次期backend境界のテストを先に追加し、対象package不在によるREDを記録した。
- [x] 2026-08-16: nested modelの事前構築による検証迂回を追加REDで再現し、全instance再検証で閉じた。
- [x] 2026-08-16: field上限内でもintent全体が過大になる入力を追加REDで再現し、UTF-8 byte上限で閉じた。
- [x] 2026-08-16: preconstructed top-level intentによるprovenance検証迂回を追加REDで再現し、公開関数入口で再検証した。
- [x] 2026-08-16: strict intent、normalizer、query plannerをGREENにした。
- [x] 2026-08-16: 文書同期とoffline全体gateを完了した。

### 検証

| 対象 | コマンドまたは方法 | 期待結果 | 実結果 |
|---|---|---|---|
| 現行characterization | `uv run pytest -q tests/test_backend_characterization.py` | 全件成功 | 成功、6 passed |
| TDD RED | `uv run pytest -q tests/test_search_v2_intent.py tests/test_search_v2_query_planner.py` | 実装前に新契約が失敗 | exit 2、`ModuleNotFoundError: No module named 'src.search_v2'`。test SHA-256: intent `f7ccac923d3c241ec3a250fb42b325e2266bef76eb1b707ae894f746f9e0220c`、planner `3e5e66b8cac51be7ae19a75c3db7d4e0eca17221bc3f33fd0befd35738cfbebb` |
| TDD追加RED | 同上 | preconstructed nested modelを拒否する新契約が失敗 | exit 1、2 failed / 14 passed。`model_construct()` 済みambiguityとqueryが再検証されなかった。test SHA-256: intent `344b962138f588e49b1f1356aa570b84de26660ce4bf1448fd6d73e9960fad6f`、planner `55b0f686c6a4a0538bbd8ac5d12ca9993caa274f4da44240c9f97cb0463a43f0` |
| TDD byte上限RED | `uv run pytest -q tests/test_search_v2_intent.py` | field上限内でも過大なintent全体を拒否 | exit 1、1 failed / 9 passed。test SHA-256 `f2643f4f3fd91abd5abb9a0c083070879908e8ae5a87451144f544d708b80c9f` |
| TDD top-level RED | `uv run pytest -q tests/test_search_v2_query_planner.py` | forged top-level intentをquery planner入口で拒否 | exit 1、1 failed / 9 passed。test SHA-256 `96712ad1bc297c800f2360c5edb7449a905bfff112703afa48df5ee686514242` |
| TDD GREEN | `uv run pytest -q tests/test_search_v2_intent.py tests/test_search_v2_query_planner.py` | 全件成功 | 成功、20 passed。最終test SHA-256: intent `f2643f4f3fd91abd5abb9a0c083070879908e8ae5a87451144f544d708b80c9f`、planner `96712ad1bc297c800f2360c5edb7449a905bfff112703afa48df5ee686514242` |
| 対象全体 | `uv run pytest -q tests/test_backend_characterization.py tests/test_search_v2_intent.py tests/test_search_v2_query_planner.py` | 全件成功 | 成功、26 passed |
| offline全体 | `uv run pytest -m 'not live_api'` | 全件成功 | 成功、752 passed / 1 deselected |
| lint | `uv run ruff check .` | 違反0件 | 成功 |
| format | `uv run ruff format --check .` | 差分0件 | 成功、123 files already formatted |
| lock | `uv lock --check` | lock整合 | 成功、72 packages resolved |
| whitespace | `git diff --check` | 違反0件 | 成功 |
| 文書 | project Markdownのlocal link、anchor、fence、AGENTS索引、sh/bash構文 | 違反0件 | 成功、37 files / 78 shell fences |
| Python 3.10構文 | 新規 `src/search_v2/*.py` を `ast.parse(..., feature_version=(3, 10))` | 解析成功 | 成功。Python 3.10実interpreterでは未実行 |

外部API、credential、課金を使う検証はこのPlanでは実行しない。

### セキュリティ・データ・互換性

- 次期modelは `strict=True` と `extra="forbid"` で型coercionと未知fieldを拒否する。
- 自然文、query、各fieldに長さ・文字・件数上限を設ける。
- source/prompt/schema/responseは本文ではなくSHA-256だけをdomain modelへ結び付ける。
- 現行modelとpipelineは変更せず、新packageへ隔離するため既存cacheとCLIの互換性を維持する。
- 外部API clientを含めず、テストはnetworkなしで完結させる。

### 判断記録

| 日時 | 判断 | 理由 | 影響・見直し条件 |
|---|---|---|---|
| 2026-08-16 | 現行modelをstrict化せず `src/search_v2/` へ新契約を置く | 現行cacheとBonsai応答を暗黙に破壊せず移行差分を明示するため | 現行pipeline切替時にadapterとcache version更新を別マイルストーンで行う |
| 2026-08-16 | 第1マイルストーンは外部clientを含めない | normalizationとquery planを決定的・無課金で先に検証するため | OpenAI client実装時はrefusal/incompleteとusage ledgerのPlan項目を追加する |
| 2026-08-16 | intent全体を49,152 UTF-8 bytes以下にする | 各field上限だけでは多言語4-byte文字を全配列へ詰めた過大payloadを止められないため | provider schemaや正当fixtureが上限へ近づく場合は計測結果と費用上限を示して見直す |
| 2026-08-19 | 商品検索は現行Bonsai経路を正本とし、OpenAI商品検索client計画を置換する | 現行実装を基準に継続し、商品検索とAIレビューハーネスのOpenAI利用を混同しないため | provider変更は新たな明示決定、互換adapter、TDD、cache移行計画を伴う場合だけ再検討する |

### 発見事項

- 現行query選択は日本語配列の先頭1件だけを採用し、次期仕様の最大2件queryとは別契約である。
- 現行Pydantic modelは数値文字列を整数へcoerceし、未知fieldを無視する。次期strict modelは互換modelではなく新境界として扱う。

### ロールバック

`src/search_v2/`、対応する新規テスト、このPlanとTASK-008の進捗差分だけを取り除けば、現行pipelineへ影響せず元へ戻せる。外部状態とcache schemaは変更しない。

### 結果

最初のbackend縦切りを完了した。legacy挙動6件を固定し、strict intent、provenance、決定的normalizer、最大2件query planとdomain-separated digestを追加した。当時の結果ではOpenAI clientとrefusal/incompleteを後続作業としていたが、この商品検索client計画は2026-08-19の決定で置換した。Bonsai正本の互換境界、決定的tokenizer、承認state machine、Cloudflare、Outscraper複数query、ranking v2の扱いは、現行仕様と [TASK-008](GOAL.md#task-008-次期検索フロー-v2-の実装) に従う。

## 統合済み旧検証資料

> 統合元: 旧 `examples/` 配下のMarkdown 7件。以下は段階別検証の経緯を保持する履歴であり、現行実装の正本ではない。元ファイルはパス構造を保って `docs/old/examples/` に保存する。

### examples/README.md

> 統合元: `examples/README.md`。旧検証時点の本文を保持する。現行仕様・回帰テストの根拠にはしない。

#### 段階別の検証用サンプル

`legacy-phases/`には、現在の`src/`実装へ統合する前に各処理段階を確認するために作成した独立スクリプトと説明を保存している。

これらは回帰テストではない。現在のアプリケーションを検証するときは、リポジトリルートで次を実行する。

```sh
uv run pytest
```

実装の起動方法と構成は、ルートの`README.md`を参照する。

### examples/legacy-phases/phase1_bonsai_attribute_extraction/Add.md

> 統合元: `examples/legacy-phases/phase1_bonsai_attribute_extraction/Add.md`。旧検証時点の本文を保持する。現行仕様・回帰テストの根拠にはしない。

llama.cpp を導入する必要があります。Ubuntu/Linux なら典型的にはこうです。
/home/llama.cpp/build/bin/llama-server
'''
cd /home/
git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp
cmake -B build
cmake --build build --config Release -j 2
'''
Bonsai 8B DL
'''
wget -O Bonsai-8B.gguf \
  https://huggingface.co/prism-ml/Bonsai-8B-gguf/resolve/main/Bonsai-8B.gguf
'''
起動
'''
/home/llama.cpp/build/bin/llama-server \
  -m /home/products/models/Bonsai-8B.gguf \
  --host 127.0.0.1 \
  --port 8080
'''

### examples/legacy-phases/phase1_bonsai_attribute_extraction/PREREQUISITES.md

> 統合元: `examples/legacy-phases/phase1_bonsai_attribute_extraction/PREREQUISITES.md`。旧検証時点の本文を保持する。現行仕様・回帰テストの根拠にはしない。

#### 第一段階：自然言語入力から商品属性抽出

##### 1. 目的

第一段階では、Amazon検索、ランキング、Streamlit UI、ComfyUI連携は実装対象外とする。

対象範囲は以下に限定する。

```text
自然言語入力
  ↓
Bonsai 8B local server
  ↓
商品属性JSON
```

この段階の目的は、ユーザーの曖昧な商品イメージを、後続のAmazon検索で利用できる構造化データへ変換できることを確認することである。

##### 2. 前提条件

ラップトップ側で以下を満たすこと。

- Python 3.10以上を利用できる
- `uv` を利用できる
- Bonsai 8B GGUFファイルをローカルに配置済みである
- `llama-server` またはOpenAI互換APIを提供できるLLMサーバを利用できる
- BonsaiのAPIは外部公開せず、`127.0.0.1` に限定して起動する
- 第一段階ではOutscraper APIキー、ComfyUI、SSH接続は不要とする

最小依存パッケージは以下とする。

```text
requests
pydantic
python-dotenv
```

開発用に `ruff` と `pytest` を追加してもよいが、第一段階の疎通確認だけであれば必須ではない。

##### 3. 環境変数

`.env` またはシェル環境変数で以下を設定する。

```env
BONSAI_BASE_URL=http://127.0.0.1:8080/v1
BONSAI_MODEL=Bonsai-8B
```

未設定の場合、サンプルコードは上記の値をデフォルトとして使う。

##### 4. Bonsai起動

BonsaiをOpenAI互換サーバとして起動する。

```bash
llama-server \
  -m /path/to/Bonsai-8B.gguf \
  --host 127.0.0.1 \
  --port 8080
```

疎通確認は以下で行う。

```bash
curl http://127.0.0.1:8080/v1/models
```

##### 5. 商品属性スキーマ

第一段階の出力は以下のスキーマに固定する。

```python
from pydantic import BaseModel, Field


class ProductAttributes(BaseModel):
    estimated_product_name_ja: str = Field(description="UI表示に使う日本語の推定商品名")
    estimated_product_name_en: str | None = Field(default=None, description="Outscraper検索と英語商品名照合に使う英語の推定商品名")
    category_ja: str | None = Field(default=None, description="UI表示に使う日本語の商品カテゴリ")
    category_en: str | None = Field(default=None, description="英語商品名照合に使う英語の商品カテゴリ")
    color_ja: str | None = Field(default=None, description="UI表示に使う日本語の主要な色")
    color_en: str | None = Field(default=None, description="英語商品名照合に使う英語の主要な色")
    features_ja: list[str] = Field(default_factory=list, description="UI表示に使う日本語の商品特徴")
    features_en: list[str] = Field(default_factory=list, description="Outscraper検索と英語商品名照合に使う英語の商品特徴")
    negative_conditions_ja: list[str] = Field(default_factory=list, description="UI表示に使う日本語の除外条件")
    negative_conditions_en: list[str] = Field(default_factory=list, description="英語商品名照合に使う英語の除外条件")
    search_queries_ja: list[str] = Field(default_factory=list, description="日本語Amazon検索クエリ候補")
    search_queries_en: list[str] = Field(default_factory=list, description="Outscraper検索に優先して使う英語Amazon検索クエリ候補")
    image_prompt: str | None = Field(default=None, description="画像生成用英語プロンプト")
    price_preference: str | None = Field(default=None, description="cheap / premium / none")
    max_price_jpy: int | None = Field(default=None, description="上限価格")
```

`search_queries_en` はOutscraper検索に優先して使う。`search_queries_ja` が空の場合、サンプルコードではユーザー入力をそのまま日本語検索語として使う。

##### 6. プロンプト方針

Bonsaiには、説明文やMarkdownを返させず、JSONのみを返させる。

```text
あなたはEC商品検索用の商品属性抽出器です。
ユーザーの自然言語入力から、Amazon検索に使う商品属性を抽出してください。

制約:
- 出力はJSONのみ
- Markdownや説明文は禁止
- 不明な項目は null または [] を使う
- *_ja フィールドは日本語で出力する
- *_en フィールドは自然な英語で出力する
- search_queries_ja は日本語で1から3件
- search_queries_en はOutscraper検索に使える英語で1から3件
- image_prompt は英語の商品写真プロンプト
- price_preference は cheap / premium / none のいずれか

JSONキー:
estimated_product_name_ja, estimated_product_name_en,
category_ja, category_en, color_ja, color_en,
features_ja, features_en, negative_conditions_ja, negative_conditions_en,
search_queries_ja, search_queries_en, image_prompt, price_preference, max_price_jpy
```

##### 7. 実行方法

依存パッケージを入れる。

```bash
uv sync
```

Bonsaiを起動した状態で、サンプルコードを実行する。

```bash
uv run python phase1_bonsai_attribute_extraction/extract_product_attributes.py
```

##### 8. 期待出力例

```json
{
  "estimated_product_name_ja": "ノイズキャンセリング 小型ワイヤレスイヤホン ブラック",
  "estimated_product_name_en": "compact black noise cancelling wireless earbuds",
  "category_ja": "ワイヤレスイヤホン",
  "category_en": "wireless earbuds",
  "color_ja": "ブラック",
  "color_en": "black",
  "features_ja": ["ノイズキャンセリング", "小型", "丸型ケース"],
  "features_en": ["noise cancelling", "compact", "small round case"],
  "negative_conditions_ja": [],
  "negative_conditions_en": [],
  "search_queries_ja": [
    "ノイズキャンセリング 小型 ワイヤレスイヤホン ブラック"
  ],
  "search_queries_en": [
    "compact black noise cancelling wireless earbuds"
  ],
  "image_prompt": "black compact wireless earbuds with noise cancelling, small rounded charging case, product photo, white background",
  "price_preference": "cheap",
  "max_price_jpy": null
}
```

##### 9. 完了条件

- Bonsai local serverへHTTP接続できる
- 自然言語入力からJSONのみを取得できる
- Pydanticで商品属性スキーマを検証できる
- `search_queries_ja` が1件以上になる
- `search_queries_en` または `estimated_product_name_en` が1件以上になる
- JSONが壊れた場合に失敗理由を明示できる

### examples/legacy-phases/phase1_bonsai_attribute_extraction/README.md

> 統合元: `examples/legacy-phases/phase1_bonsai_attribute_extraction/README.md`。旧検証時点の本文を保持する。現行仕様・回帰テストの根拠にはしない。

#### 第一段階：自然言語入力から商品属性抽出

##### 1. 目的

第一段階では、ユーザーの自然言語入力をBonsaiなどのOpenAI互換ローカルLLMへ渡し、Amazon検索や後続ランキングで使う商品属性JSONへ変換する。

この段階では、Outscraper APIへのリクエスト、商品候補正規化、ランキング、UI、ComfyUI連携は実装対象外とする。

対象範囲は以下に限定する。

```text
自然言語入力
  ↓
Bonsai OpenAI互換API
  ↓
商品属性JSON
  ↓
Outscraper検索用パラメータ候補
```

Bonsaiや `llama-server` の導入手順は `PREREQUISITES.md` を参照する。

##### 2. 実行方法

依存パッケージを入れる。

```sh
uv sync
```

BonsaiのOpenAI互換サーバを起動した状態で実行する。

```sh
uv run python phase1_bonsai_attribute_extraction/extract_product_attributes.py
```

利用する環境変数は以下とする。

```env
BONSAI_BASE_URL=http://127.0.0.1:8080/v1
BONSAI_MODEL=Bonsai-8B.gguf
```

未設定の場合は、サンプルコード内の標準値を使う。

##### 3. 出力モデル

`ProductAttributes` は、LLMから受け取った商品属性を検証するPydanticモデルである。

主な項目は以下とする。

| 項目 | 内容 |
|---|---|
| `estimated_product_name_ja` | 日本語の推定商品名。必須 |
| `estimated_product_name_en` | 英語の推定商品名 |
| `category_ja` / `category_en` | 商品カテゴリ |
| `color_ja` / `color_en` | 主要な色 |
| `features_ja` / `features_en` | 商品特徴 |
| `negative_conditions_ja` / `negative_conditions_en` | 除外したい条件 |
| `search_queries_ja` / `search_queries_en` | Amazon検索クエリ候補 |
| `required_terms_ja` / `required_terms_en` | ランキングで強く重視する語 |
| `preferred_terms_ja` / `preferred_terms_en` | ランキングで中程度に重視する語 |
| `related_terms_ja` / `related_terms_en` | ランキングで補助的に使う語 |
| `image_prompt` | 画像生成用の英語プロンプト |
| `price_preference` | `cheap`、`premium`、`none` の価格嗜好 |
| `max_price_jpy` | 上限価格 |

##### 4. 関数詳細

###### `string_list()`

Pydanticモデルでリスト型フィールドのデフォルト値を作るための補助関数。`Field(default_factory=list)` を返し、複数インスタンス間で同じリストを共有しないようにする。

###### `call_bonsai(user_input)`

`.env` を読み込み、`BONSAI_BASE_URL` の `/chat/completions` にHTTP POSTする。`build_bonsai_payload()` で作ったOpenAI互換リクエストを送り、レスポンスの `choices[0].message.content` を文字列として返す。

HTTPエラーは `raise_for_status()` で例外にする。戻り値はまだ検証前のLLM生レスポンスであり、JSONとして正しいとは限らない。

###### `build_bonsai_payload(user_input)`

Bonsaiへ送るリクエスト本文を作る。モデル名、system prompt、ユーザー入力、temperature、max_tokens を含む辞書を返す。

モデル名は `BONSAI_MODEL` があればそれを使い、未設定の場合は `Bonsai-8B.gguf` を使う。

###### `normalize_bonsai_json(data)`

LLMのJSON出力をPydantic検証前に補正する。リストであるべき項目が `null` の場合は `[]` にし、文字列の場合は1要素のリストに変換する。

`max_price_jpy` が文字列で返った場合、数字だけなら `int` に変換し、数値化できない場合は `None` にする。

###### `has_japanese_category_evidence(category, evidence_parts)`

日本語カテゴリが、推定商品名や特徴などの根拠テキストに含まれているかを確認する。LLMが根拠の薄いカテゴリを推測した場合に除外するために使う。

###### `english_words(text)`

英語テキストを小文字化し、ハイフンを空白扱いにして単語集合へ変換する。3文字以下の語は照合ノイズになりやすいため除外する。

###### `has_english_category_evidence(category, evidence_parts)`

英語カテゴリの単語が、推定商品名や特徴などの根拠テキストにすべて含まれているかを確認する。日本語カテゴリと同じく、根拠の薄いカテゴリを除外するために使う。

###### `clean_categories(attrs)`

`category_ja` と `category_en` を検証し、商品名や特徴から根拠を確認できないカテゴリを `None` にする。`ProductAttributes` をその場で更新する。

###### `unique_non_empty(values)`

空文字、`None`、大文字小文字違いの重複を除き、入力順を保った文字列リストを返す。検索クエリを作るときに同じ語が繰り返されないように使う。

###### `contains_japanese(text)`

ひらがな、カタカナ、漢字が含まれているかを判定する。日本語検索クエリに英語だけの語を混ぜすぎないための補助関数。

###### `japanese_query_part(value)`

値が空でなく、日本語文字を含む場合だけその値を返す。条件に合わない場合は `None` を返す。

###### `improve_search_queries(attrs)`

推定商品名、色、特徴、カテゴリを使って検索クエリを再構築する。日本語要素があれば `search_queries_ja` を1件の検索語に置き換え、英語要素があれば `search_queries_en` を小文字の1件に置き換える。

###### `select_outscraper_query(attrs)`

Outscraperへ渡す検索語を選ぶ。優先順位は `search_queries_ja` の先頭、`search_queries_en` の先頭、`estimated_product_name_ja` の順とする。

###### `build_outscraper_amazon_params(attrs, limit)`

第一段階の属性からOutscraper Amazon Products Scraper向けのクエリパラメータを作る。`query`、`domain`、`language`、`limit`、`async` を含む辞書を返す。

###### `build_outscraper_amazon_url(attrs, endpoint, limit)`

`build_outscraper_amazon_params()` の結果をURLエンコードし、Outscraper APIの確認用URLを組み立てる。実際のAPIキーは含めない。

###### `parse_attributes(raw_text, fallback_query)`

Bonsaiの生レスポンスをJSONとして読み込み、`normalize_bonsai_json()` で補正し、`ProductAttributes` として検証する。JSONが壊れている場合やスキーマに合わない場合は、元レスポンスを含む `ValueError` を送出する。

検索語が空の場合は `fallback_query` や `estimated_product_name_en` を使って最低限の検索語を補う。その後、カテゴリ検証と検索クエリ改善を実行する。

###### `extract_product_attributes(user_input)`

第一段階のメイン処理。自然言語入力を `call_bonsai()` に渡し、返ってきたテキストを `parse_attributes()` で検証済みの `ProductAttributes` に変換する。

##### 5. 完了条件

- Bonsai local serverへHTTP接続できる
- 自然言語入力からJSONのみを取得できる
- Pydanticで商品属性スキーマを検証できる
- 後続のOutscraper検索に使う検索語を1件以上作れる
- JSONが壊れた場合に失敗理由を明示できる

### examples/legacy-phases/phase2_outscraper_amazon_products_request/README.md

> 統合元: `examples/legacy-phases/phase2_outscraper_amazon_products_request/README.md`。旧検証時点の本文を保持する。現行仕様・回帰テストの根拠にはしない。

#### 第二段階：Outscraper Amazon Products Scraper疎通確認

##### 1. 目的

第二段階では、第一段階で生成するAmazon検索語を、Outscraper Amazon Products Scraperへ渡し、レスポンスJSONを受け取れることを確認する。

この段階では、商品候補正規化、ランキング、Streamlit UI、ComfyUI連携は実装対象外とする。

対象範囲は以下に限定する。

```text
Amazon検索語
  ↓
Outscraper Amazon Products Scraper
  ↓
非同期ジョブ作成
  ↓
results_locationをポーリング
  ↓
レスポンスJSON
```

##### 2. 前提条件

- Python 3.10以上を利用できる
- `uv` を利用できる
- Outscraper APIキーを保持している
- `OUTSCRAPER_API_KEY` を `.env` またはシェル環境変数で設定している

```env
OUTSCRAPER_API_KEY=xxxxxxxx
```

APIキーは `X-API-KEY` ヘッダーで送る。検索語やURLクエリにはAPIキーを含めない。

このサンプルでは、入力値をAmazon URLではなく検索語に限定する。`http://` または `https://` で始まる値を渡した場合はエラーにする。

##### 3. 実行方法

依存パッケージを入れる。

```sh
uv sync
```

サンプル検索語で実行する。

```sh
uv run python phase2_outscraper_amazon_products_request/fetch_amazon_products.py \
  --limit 10
```

サンプル検索語は以下とする。

```text
ノイズキャンセリング 小型 ワイヤレスイヤホン ブラック
```

検索語を指定して実行することもできる。

```sh
uv run python phase2_outscraper_amazon_products_request/fetch_amazon_products.py \
  "wireless earbuds noise cancelling black" \
  --limit 10
```

レスポンスJSONをファイルに保存する場合は `--output` を指定する。

```sh
uv run python phase2_outscraper_amazon_products_request/fetch_amazon_products.py \
  "wireless earbuds noise cancelling black" \
  --limit 10 \
  --output cache/outscraper/amazon_wireless_earbuds_sample.json
```

ジョブが長く待機する場合は、ポーリング間隔と確認回数を調整する。

```sh
uv run python phase2_outscraper_amazon_products_request/fetch_amazon_products.py \
  --limit 1 \
  --poll-interval 30 \
  --max-polls 50
```

Outscraper Amazon Products Scraperのレスポンスは、7分から25分程度かかる場合がある。標準設定では、30秒間隔で50回確認し、最大約25分待機する。

指定した回数内に完了しない場合は、例外で終了せず、`status: Pending` と `results_location` を含むJSONを返す。

##### 4. パラメータ

標準値は以下とする。

| 項目 | 値 |
|---|---|
| endpoint | `https://api.outscraper.cloud/amazon-products` |
| domain | `amazon.co.jp` |
| language | `ja` |
| limit | `10` |
| async | `true` |
| poll interval | `30` 秒 |
| max polls | `50` 回 |

endpointを変更する場合は、環境変数または `--endpoint` で指定する。

```env
OUTSCRAPER_AMAZON_PRODUCTS_ENDPOINT=https://api.outscraper.cloud/amazon-products
```

##### 5. 完了条件

- `Request URL:` としてOutscraperへ送る検索語入りURLを確認できる
- `Request ID:` と `Results location:` を確認できる
- `OUTSCRAPER_API_KEY` をコードに直書きせずに送信できる
- OutscraperからJSONレスポンスを受け取れる
- 必要に応じてレスポンスJSONをファイルへ保存できる

##### 6. 関数詳細

###### `validate_search_query(query)`

検索語の前後空白を取り除き、空文字でないことを確認する。`http://` または `https://` で始まる値はAmazon URLとみなし、検索語ではないため `ValueError` にする。

戻り値は正規化済みの検索語であり、以降のリクエスト生成ではこの値を使う。

###### `build_amazon_products_params(query, domain, language, limit, async_request)`

Outscraper Amazon Products Scraperへ渡すURLクエリパラメータを作る。`query` は `validate_search_query()` で検証する。

返す辞書には以下を含める。

| キー | 内容 |
|---|---|
| `query` | Amazon検索語 |
| `domain` | 対象Amazonドメイン |
| `language` | 表示言語 |
| `limit` | 取得件数の上限 |
| `async` | 非同期リクエストにするかどうか |

`async` はOutscraper APIへ渡しやすいように、Pythonの真偽値ではなく `"true"` または `"false"` の文字列に変換する。

###### `build_amazon_products_request_url(query, endpoint, domain, language, limit, async_request)`

確認用のリクエストURLを作る。`build_amazon_products_params()` の結果を `urlencode()` でエンコードし、endpointの後ろに付与する。

このURLにはAPIキーを含めない。APIキーは実リクエスト時に `X-API-KEY` ヘッダーで送る。

###### `submit_amazon_products_request(query, api_key, endpoint, domain, language, limit, timeout)`

Outscraper Amazon Products Scraperへ非同期リクエストを送信する。内部では `async_request=True` のパラメータを作り、`requests.get()` で送信する。

HTTPステータスがエラーの場合は `raise_for_status()` で例外にする。成功時はJSONレスポンスを辞書として返す。

レスポンスに `results_location` が含まれる場合、後続のポーリング対象になる。

###### `fetch_request_result(results_location, api_key, timeout)`

`submit_amazon_products_request()` で得た `results_location` にGETリクエストを送り、現在のジョブ結果を取得する。APIキーはここでも `X-API-KEY` ヘッダーで送る。

成功時はJSONレスポンスを辞書として返す。

###### `is_pending_result(data)`

Outscraperのレスポンスがまだ処理中かを判定する。`status` を小文字化し、`pending`、`in progress`、`in_progress`、`processing` のいずれかであれば `True` を返す。

この関数により、Outscraper側の表記ゆれを吸収する。

###### `fetch_amazon_products(query, api_key, endpoint, domain, language, limit, request_timeout, poll_interval, max_polls)`

第二段階の中心処理。まず `submit_amazon_products_request()` でジョブを作成し、`results_location` が返った場合は `fetch_request_result()` を繰り返して完了を待つ。

処理の流れは以下とする。

```text
検索語を送信
  ↓
results_locationを取得
  ↓
指定間隔でポーリング
  ↓
pendingでなくなったら結果を返す
```

`results_location` がない場合は、送信時レスポンスをそのまま返す。最大ポーリング回数を超えても処理中の場合は例外にせず、最後のレスポンスに `results_location` と説明文を追加して返す。

###### `write_json(path, data)`

レスポンスJSONをファイルへ保存する。親ディレクトリが存在しない場合は作成し、UTF-8、インデント付き、非ASCII文字をそのまま読める形式で出力する。

###### `parse_args()`

CLI引数を定義する。検索語、取得件数、Amazonドメイン、表示言語、endpoint、出力先、ポーリング間隔、最大ポーリング回数、リクエストタイムアウトを受け取る。

###### `main()`

CLI実行時の入口。`.env` を読み込み、引数を解析し、`OUTSCRAPER_API_KEY` を取得する。APIキーが未設定の場合は `RuntimeError` にする。

その後、確認用の `Request URL:` を表示し、`fetch_amazon_products()` でレスポンスを取得する。`--output` が指定されていればファイルへ保存し、未指定なら標準出力へJSONを表示する。

### examples/legacy-phases/phase3_outscraper_response_normalization/README.md

> 統合元: `examples/legacy-phases/phase3_outscraper_response_normalization/README.md`。旧検証時点の本文を保持する。現行仕様・回帰テストの根拠にはしない。

#### 第三段階：Outscraperレスポンスの商品候補正規化

##### 1. 目的

第三段階では、Outscraper Amazon Products ScraperのレスポンスJSONを解析し、ランキングやUI表示で扱いやすい商品候補リストへ正規化する。

この段階では、Outscraper APIへのリクエスト、商品ランキング、Streamlit UI、ComfyUI連携は実装対象外とする。

対象範囲は以下に限定する。

```text
OutscraperレスポンスJSON
  ↓
商品配列の取り出し
  ↓
価格、画像URL、レビュー、カテゴリなどの正規化
  ↓
正規化済み商品候補JSON
```

##### 2. サンプルレスポンス

実際のOutscraperレスポンスをもとに、サンプル用のダミーレスポンスを以下に用意している。

```text
cache/outscraper/amazon_products_dummy_response.json
```

実APIのレスポンスには商品URL、画像URL、商品名、価格などが含まれるため、サンプルでは値をダミー化している。JSON構造は、第二段階で取得したレスポンスと同じく `data` の中に商品配列が入る形式を想定する。

##### 3. 実行方法

依存パッケージを入れる。

```sh
uv sync
```

サンプルレスポンスを正規化する。

```sh
uv run python phase3_outscraper_response_normalization/normalize_amazon_products.py
```

第二段階で保存したレスポンスJSONを指定して実行することもできる。

```sh
uv run python phase3_outscraper_response_normalization/normalize_amazon_products.py \
  --input cache/outscraper/amazon_sample_response.json
```

正規化結果をファイルに保存する場合は `--output` を指定する。

```sh
uv run python phase3_outscraper_response_normalization/normalize_amazon_products.py \
  --output cache/outscraper/amazon_products_normalized_sample.json
```

##### 4. 正規化する項目

主な出力項目は以下とする。

| 項目 | 内容 |
|---|---|
| `asin` | Amazonの商品ID |
| `title` | 商品名 |
| `brand_or_store` | ストア名またはブランド名として扱う値 |
| `price_jpy` | 現在価格。数値化できない場合は `null` |
| `list_price_jpy` | 旧価格または取り消し線価格。数値化できない場合は `null` |
| `rating` | レビュー評価 |
| `review_count` | レビュー件数 |
| `categories` | カテゴリ階層 |
| `image_url` | 代表画像URL |
| `image_urls` | 商品画像URL一覧 |
| `product_url` | 商品ページURL |
| `short_url` | 短縮商品URL |
| `is_prime` | Prime対象かどうか |
| `availability` | 在庫状態 |
| `shipping` | 配送情報 |
| `source_query` | Outscraperへ渡した検索語 |
| `position` | 検索結果上の順位 |
| `description` | 商品説明 |

##### 5. 完了条件

- ダミーレスポンスJSONを参照して正規化処理を実行できる
- `data` 配下の商品配列を取り出せる
- 価格、評価、レビュー件数を数値として扱える
- `high_res_images` と `image_1` 以降から画像URL一覧を作れる
- `asin` などを使って重複商品を除外できる

##### 6. 関数詳細

###### `string_list()`

Pydanticモデルでリスト型フィールドのデフォルト値を作るための補助関数。`Field(default_factory=list)` を返し、商品ごとに独立したリストを持てるようにする。

###### `NormalizedAmazonProduct`

Outscraperの商品1件を、後続処理で扱いやすい形式へそろえるPydanticモデル。商品名、価格、レビュー、画像URL、商品URL、カテゴリ、在庫、配送情報などを保持する。

`title` は必須であり、商品名が取れない商品は `normalize_product()` で除外する。

###### `read_json(path)`

指定したJSONファイルをUTF-8で読み込み、辞書として返す。第三段階では、OutscraperレスポンスJSONの読み込みに使う。

###### `write_json(path, data)`

正規化済み商品候補をJSONファイルへ保存する。親ディレクトリがない場合は作成し、UTF-8、インデント付き、非ASCII文字を読める形式で出力する。

###### `as_int(value)`

価格、レビュー件数、検索順位などを整数へ変換する。`int` はそのまま返し、`float` は小数部分を切り捨てる。文字列の場合は数字だけを抽出して整数化する。

`bool` と `None` は数値として扱わず `None` を返す。変換できない値も `None` にする。

###### `as_float(value)`

レビュー評価などを浮動小数点数へ変換する。`bool` と `None` は `None` を返す。文字列、整数、小数はいったん `float()` に渡し、変換できない場合は `None` にする。

###### `as_non_empty_string(value)`

値が文字列であれば前後空白を取り除き、空でなければ返す。文字列でない値や空文字は `None` にする。

###### `as_string_list(value)`

Outscraperレスポンス内のカテゴリなどを文字列リストへ変換する。入力がリストでない場合は空リストを返す。リスト内では、文字列かつ空でない値だけを残す。

###### `unique_strings(values)`

文字列リストから `None` と重複を除き、入力順を保って返す。画像URL一覧の重複除去に使う。

###### `collect_image_urls(item)`

Outscraperの商品データから画像URL一覧を作る。まず `high_res_images` のURLを集め、続けて `image_1` から `image_10` までを確認する。

空値や重複は除外する。戻り値の先頭は代表画像 `image_url` として使われる。

###### `iter_product_items(response)`

Outscraperレスポンスの `data` から商品辞書だけを取り出す。`data` の中に商品辞書が直接入っている場合と、商品辞書リストが入っている場合の両方に対応する。

`data` がリストでない場合は空リストを返す。

###### `normalize_product(item)`

Outscraperの商品1件を `NormalizedAmazonProduct` へ変換する。商品名、ASIN、ストア名、価格、旧価格、通貨、評価、レビュー件数、カテゴリ、画像URL、商品URL、Prime対象、在庫、配送情報、検索語、順位、説明を正規化する。

商品名 `name` が空の場合は、後続で扱う最低限の情報がないため `None` を返す。

###### `normalize_amazon_products_response(response)`

Outscraperレスポンス全体を正規化済み商品候補リストへ変換する。`iter_product_items()` で商品候補を取り出し、`normalize_product()` で1件ずつ正規化する。

重複判定には `asin`、`short_url`、`product_url`、`title` の順で利用する。すでに見たキーの商品は追加しない。

###### `parse_args()`

CLI引数を定義する。入力JSONファイルと出力JSONファイルを受け取る。入力未指定時はダミーレスポンスを使い、出力未指定時は標準出力へ表示する。

###### `main()`

CLI実行時の入口。入力JSONを読み込み、`normalize_amazon_products_response()` で正規化し、Pydanticモデルを辞書へ変換する。

`--output` が指定されていればファイルへ保存し、未指定なら標準出力へJSONを表示する。

### examples/legacy-phases/phase4_product_scoring/README.md

> 統合元: `examples/legacy-phases/phase4_product_scoring/README.md`。旧検証時点の本文を保持する。現行仕様・回帰テストの根拠にはしない。

#### 第四段階：商品名類似度、属性類似度、価格スコア計算

##### 1. 目的

第四段階では、第三段階で正規化したAmazon商品候補に対して、第一段階で抽出した商品属性との一致度を計算し、ランキング用の総合スコアを付与する。

この段階では、Outscraper APIへのリクエスト、Streamlit UI、ComfyUI連携、embeddingによる高精度な類似度計算は実装対象外とする。

対象範囲は以下に限定する。

```text
商品属性JSON
  ↓
正規化済み商品候補JSON
  ↓
SudachiPy単語分割
  ↓
TF-IDFによる商品名類似度 + 属性類似度 + 価格スコア
  ↓
スコア付き商品候補JSON
```

##### 2. サンプルデータ

第三段階の正規化済みデータをもとに、サンプル用のダミー商品候補を以下に用意している。

```text
cache/outscraper/amazon_products_normalized_dummy.json
```

第一段階の商品属性抽出結果を想定したダミー属性は以下に用意している。

```text
cache/product_attributes/product_attributes_dummy.json
```

##### 3. 実行方法

依存パッケージを入れる。

```sh
uv sync
```

サンプルデータでスコアを計算する。

```sh
uv run python phase4_product_scoring/score_products.py
```

入力ファイルを指定して実行することもできる。

```sh
uv run python phase4_product_scoring/score_products.py \
  --attributes cache/product_attributes/product_attributes_dummy.json \
  --products cache/outscraper/amazon_products_normalized_dummy.json
```

スコア結果をファイルに保存する場合は `--output` を指定する。

```sh
uv run python phase4_product_scoring/score_products.py \
  --output cache/outscraper/amazon_products_scored_sample.json
```

##### 4. スコア設計

標準の重みは以下とする。

| 項目 | 重み | 内容 |
|---|---:|---|
| 商品名類似度 | `0.45` | 推定商品名、カテゴリ、ランキング語と商品名のTF-IDF類似度 |
| 属性類似度 | `0.35` | 色、カテゴリ、特徴、ランキング語と商品テキストのTF-IDF類似度 |
| 価格スコア | `0.20` | 上限価格または価格嗜好に合うか |

第一段階の商品属性JSONに以下のランキング語が含まれる場合は、TF-IDFクエリ内で重み付けする。

| 項目 | 繰り返し回数 | 内容 |
|---|---:|---|
| `required_terms_ja` / `required_terms_en` | `3` | 商品種別など必須に近い語 |
| `preferred_terms_ja` / `preferred_terms_en` | `2` | 色、形状、機能など重視したい語 |
| `related_terms_ja` / `related_terms_en` | `1` | 略語や言い換えなど補助的な語 |

除外条件に一致する語がある場合は、総合スコアから減点する。

```text
total_score =
  title_similarity * 0.45
  + attribute_similarity * 0.35
  + price_score * 0.20
  - negative_penalty
```

##### 5. 完了条件

- 正規化済み商品候補JSONを読み込める
- 商品属性JSONを読み込める
- 商品名類似度、属性類似度、価格スコアを計算できる
- 除外条件に一致する商品を減点できる
- 総合スコア順に商品候補を並べ替えられる

##### 6. 関数詳細

###### モデルと入出力

###### `string_list()`

Pydanticモデルでリスト型フィールドのデフォルト値を作る補助関数。`Field(default_factory=list)` を返し、属性やスコア結果ごとに独立したリストを持てるようにする。

###### `SearchAttributes`

第一段階の商品属性JSONを受け取るPydanticモデル。推定商品名、カテゴリ、色、特徴、除外条件、検索クエリ、ランキング用語、価格嗜好、上限価格を保持する。

第四段階では、商品名類似度、属性類似度、価格スコア、除外条件の計算に使う。

###### `ProductScore`

商品1件のスコア結果を表すPydanticモデル。商品識別情報に加えて、商品名類似度、属性類似度、価格スコア、除外ペナルティ、総合スコア、マッチした語、欠落した語、除外条件に一致した語を保持する。

###### `read_json(path)`

指定したJSONファイルをUTF-8で読み込み、Pythonオブジェクトとして返す。属性JSONと正規化済み商品候補JSONの読み込みに使う。

###### `write_json(path, data)`

スコア付き商品候補をJSONファイルへ保存する。親ディレクトリがない場合は作成し、UTF-8、インデント付き、非ASCII文字を読める形式で出力する。

###### テキスト正規化と単語分割

###### `normalize_text(text)`

文字列を `casefold()` で小文字化する。英語の大文字小文字差を吸収し、日本語や記号を含む文字列でも比較しやすくする。

###### `normalized_morpheme_text(morpheme)`

SudachiPyの形態素から正規化済みの表記を取り出す。`normalized_form()` が `*` の場合は `surface()` を使い、最後に `normalize_text()` と `strip()` を適用する。

###### `is_content_japanese_token(token, morpheme)`

形態素がランキングに使う日本語トークンかを判定する。空文字を除外し、品詞が名詞、動詞、形容詞、形状詞のいずれかで、ひらがな、カタカナ、漢字を含む場合に `True` を返す。

###### `split_japanese_words(text)`

SudachiPyで日本語を分割し、`is_content_japanese_token()` を通った語だけを返す。助詞や記号など、ランキングに使いにくい語はここで落とす。

###### `split_words(text, dedupe)`

英数字トークンと日本語トークンをまとめて取り出す。英語は正規表現、日本語は `split_japanese_words()` を使う。

`dedupe=True` の場合は `unique_non_empty()` で重複を除き、`dedupe=False` の場合はランキング語の重み付けのために重複を残す。

###### `term_matches_text(term, text)`

検索語や除外語が商品テキストに含まれるかを判定する。まず正規化文字列として部分一致を確認し、部分一致しない場合は単語分割して、語をすべて含むかを確認する。

例として、`wireless earbuds` は `Black wireless compact earbuds` に一致する。

###### `unique_non_empty(values)`

空値と大文字小文字違いの重複を除き、入力順を保った文字列リストを返す。クエリ語、属性語、除外語などの整理に使う。

###### クエリ語と商品テキストの構築

###### `build_title_query_terms(attrs)`

商品名類似度に使う基本語を作る。英語推定商品名、日本語推定商品名、英語カテゴリ、日本語カテゴリを重複除去して返す。

###### `build_attribute_terms(attrs)`

属性一致の確認に使う語を作る。色、カテゴリ、英語特徴、日本語特徴を重複除去して返す。

###### `repeat_terms(terms, weight)`

語句を指定回数だけ繰り返す。TF-IDFクエリ内で重要語の影響を強めるために使う。

###### `build_weighted_ranking_terms(attrs)`

第一段階で抽出したランキング用語を重み付きで展開する。`required_terms` は3回、`preferred_terms` は2回、`related_terms` は1回繰り返す。

###### `build_negative_terms(attrs)`

除外条件の英語語句と日本語語句をまとめ、重複を除いて返す。`calculate_negative_penalty()` で使う。

###### `product_text_parts(product)`

商品辞書から、タイトル、ストア名、カテゴリ、説明文を取り出す。カテゴリがリストの場合は空白区切りの文字列にする。

###### `combined_product_text(product)`

`product_text_parts()` の結果から空文字を除き、1つの商品テキストに結合する。属性類似度や除外条件判定に使う。

###### `build_tfidf_text(values, dedupe)`

複数の文字列を結合し、`split_words()` でTF-IDFに渡すための空白区切りトークン列へ変換する。

`dedupe=False` の場合は重み付きランキング語の繰り返しを残す。

###### `build_title_query_text(attrs)`

商品名類似度用のTF-IDFクエリ文字列を作る。基本の商品名・カテゴリ語に、重み付きランキング語を加える。

###### `build_attribute_query_text(attrs)`

属性類似度用のTF-IDFクエリ文字列を作る。色、カテゴリ、特徴に、重み付きランキング語を加える。

###### `build_product_tfidf_text(product)`

商品全体テキストをTF-IDF用のトークン列へ変換する。属性類似度の文書側テキストとして使う。

###### `build_product_title_tfidf_text(product)`

商品タイトルだけをTF-IDF用のトークン列へ変換する。商品名類似度の文書側テキストとして使う。

###### スコア計算

###### `calculate_tfidf_similarities(query_text, document_texts)`

クエリ文字列と複数の商品文書文字列のTF-IDFコサイン類似度を計算する。クエリまたは文書が空の場合は0点を返す。

`TfidfVectorizer` は、すでに分割済みの空白区切りトークン列を使うため、`token_pattern` を広めに設定し、`lowercase=False` にしている。

###### `calculate_term_match_score(terms, text)`

指定した語句リストのうち、商品テキストに一致した語と一致しなかった語を求める。戻り値は、マッチ率、マッチした語、欠落した語のタプルとする。

###### `calculate_title_similarity(attrs, product)`

商品名類似度を1商品分だけ計算する。`build_title_query_text()` と `build_product_title_tfidf_text()` を使い、TF-IDF類似度を1つ返す。

###### `calculate_attribute_similarity(attrs, product)`

属性類似度を1商品分だけ計算する。商品全体テキストに対して、属性語のマッチ状況とTF-IDF類似度を求める。

戻り値は、属性類似度、マッチした属性語、欠落した属性語のタプルとする。

###### `calculate_price_score(attrs, product)`

価格スコアを計算する。価格がない場合や0以下の場合は0点とする。

`max_price_jpy` がある場合、上限価格以下なら1点、上限超過なら超過率に応じて減点する。上限価格がない場合は、`price_preference` が `cheap` なら安いほど高く、`premium` なら高価格寄りほど高く、指定なしなら0.5点にする。

###### `calculate_negative_penalty(attrs, product)`

除外条件に一致した語を探し、総合スコアから引くペナルティを計算する。1語一致ごとに0.2点、最大0.5点まで減点する。

戻り値は、ペナルティ値と一致した除外語のタプルとする。

###### `score_product(attrs, product, title_similarity, attribute_similarity, title_weight, attribute_weight, price_weight)`

商品1件に対して最終的な `ProductScore` を作る。商品名類似度、属性類似度、価格スコア、除外ペナルティを組み合わせ、0から1の範囲に丸めた `total_score` を計算する。

`title_similarity` と `attribute_similarity` が渡された場合はそれを再利用し、未指定の場合はこの関数内で計算する。

###### `score_products(attrs, products)`

複数の商品候補をまとめてスコアリングする。商品名類似度と属性類似度は、商品ごとに個別計算せず、`calculate_tfidf_similarities()` でまとめて計算する。

各商品を `score_product()` で `ProductScore` に変換し、`total_score` の降順で返す。

###### CLI

###### `parse_args()`

CLI引数を定義する。第一段階の商品属性JSON、第三段階の正規化済み商品候補JSON、出力先JSONを受け取る。

###### `main()`

CLI実行時の入口。属性JSONを `SearchAttributes` として検証し、商品候補JSONがリストであることを確認する。その後 `score_products()` でスコアリングし、`--output` があればファイルへ保存し、なければ標準出力へ表示する。

## 90. 2026-09-07: counterfactual v4の暫定production backend

- 利用者は、未知のデスクライト・クランプ条件で共通閾値0のaccuracyが0.875だった方式を修正せず、暫定仕様として本番実装へ進めると決定した。これは事前品質基準の合格への変更ではない
- production code変更前にprofile・較正・商品binding、Cloudflare exact `1 + N`、server-side evaluator、ranking v5、明示reference approval、backend compositionのREDをそれぞれ未実装moduleによるcollection errorで確認した
- 元のminimum-positive v4とlabel-free batch較正は変更せず、既知accuracy 0.875、AUC 1.0、共通閾値0、人間暫定採用を別profileへ固定した。最低のcalibrated condition marginを `(margin + 1) / 2` で補助scoreへ写し、欠損・較正不能を0点にしない
- Cloudflareはdesired 1 callと条件別counterfactual各1 call、exact 2〜4 calls、attempt 1、自動retryなしの新schemaへ分離した。可変call数どおりの `counterfactual_reference_set` reservationだけを受理し、途中失敗もfailedへ確定するproduction transportを追加した
- 明示人間確認済みのCloudflare artifactだけをpHash検査付きlocal参照へ変換し、商品の先頭画像だけを既存allowlist proxyで取得する。固定CLIPは参照・候補とも最大4枚ずつ処理し、取得失敗・重複をmissing、利用可能候補4件未満をunknownにする
- `typed-ranking-v5-counterfactual-provisional` は旧v4をsourceとして画像weight 0.10を有効化するが、typed required statusを総合点より先に保ち、画像からexact属性を補完しない。承認済み参照から商品評価・v5順位までを `provisional_backend.py` で接続した
- 新規focused・usage ledgerと既存Cloudflare・state・orchestrator・typed ranking・product pipeline回帰192件を確認し、標準offline gateは1819 passed、13 skipped、3 deselectedだった。lock 79 packages、Ruff 224 files、Markdown 16 files・local link 1,359件・anchor 957件、`git diff --check` も成功した。実Cloudflare、実商品画像host、credential、課金、gpt-image、Bonsai、Outscraper、API、frontend、deploy、commit、pushは実行していない
- 永続single-use reference approvalは別SQLiteへraw token・画像bodyを保存せず、15分期限、owner・session、condition/reference/request/usage bindingを保持する。再起動後の最初のconsumeだけを成功させ、二重consumeを拒否する
- 現行のreadyな `IntentReview` からschema 5.0へ分岐し、exact 2〜4 callsの予約・counterfactual生成後に永続人間確認で停止するorchestratorを追加した。旧4方向orchestratorは変更していない
- 別SQLite `user_version=5` の表示用履歴は、暫定profile、既知accuracy 0.875、condition/reference/runtime/ranking、source typed-ranking-v4 batch、商品ごとの画像component状態を30日保持する。商品画像URLとembeddingは保存せず、旧history version 2からmigrationしない
- TDDのREDは承認・履歴・orchestrator・snapshotの未実装moduleと旧approval signatureで確認し、GREENは新規・関連59 passedだった。固定CLIP 3 fileのサイズ・SHA-256を再照合し、runtime opt-inは12 passed・1 xfailed、標準offline gateは1826 passed・13 skipped・3 deselectedだった。xfailは既知case1の事前AUC未達を成功へ読み替えていない
- 実Cloudflare、実商品画像host、credential、課金、Bonsai、Outscraper、API、frontend、deploy、commit、pushは実行していない

## 91. 2026-09-07: Cloudflare基準画像1-call live準備

- `.env` のCloudflare Account IDとAPI tokenは、値を表示せずに非空・0600・Git除外だけを確認した。設定済みであることをcredential利用や送信承認とは扱っていない
- production codeより先に `tests/test_cloudflare_live_e2e.py` を追加し、未実装moduleの `ModuleNotFoundError`、exit 2でREDを確認した。RED時のtest SHA-256は `e26aff77ab2fc561c31e7712810bbec704044712cc8588f4a3a3fc51a3b6cbe1`
- live開始時だけ生成する `CloudflareLiveSettings` に、32文字小文16進のAccount IDと `SecretStr` tokenを追加した。`.env.example` は空assignmentだけとし、tokenのreprとJSON表示に実値が出ないこと、通常のglobal `settings` がCloudflare tokenをfieldに保持・公開しないことをofflineで確認した
- `tools/cloudflare_live_e2e.py` は「白い無地の陶器製マグカップ」の固定合成intentから基準画像を1 call、retry 0で生成する。商品候補、URL、ASIN、brand、model、実利用者入力は送らず、生応答は保存しない。strict正規化後の512×512 RGB PNGだけを新規absolute pathへ0600・overwriteなしで保存する
- `--run-live-api`と`--run-cloudflare-e2e`の二重opt-inを追加し、focusedは18 passed・1 deselected、既存Cloudflare request・HTTP・counterfactual HTTP・設定回帰を含む関連確認は135 passed・1 deselectedで成功した。最終test SHA-256は `066d2be3d2c989e83307d0788b4b1d7a0fb91d2edb83a2131e8d266d3411454e`、runner SHA-256は `06a0d19fd5deb82570fe2b117babdbcd2f4cf140f3e229f59c98a3759fdd6030` である
- 標準offline gateはlock 79 packages、Ruff check、Ruff format 232 files、Markdown 16 files・local link 1,365件・anchor 963件、pytest 1,844 passed・13 skipped・4 deselected、`git diff --check` で成功した
- offline gate完了時点では実Cloudflare通信、token有効性、課金、生成品質は未確認だったため、実行直前に公式料金とexact送信契約を提示し、別の明示承認を得る境界を維持した
- Cloudflare公式の現行モデル一覧と料金を再確認し、`@cf/black-forest-labs/flux-2-klein-4b`、512×512、seed `3006064433`、固定合成intent、1 call、retry 0、120秒timeout、4 MiB応答上限、API token、出力1 tileの見積 `$0.000287`、新規0600 PNGだけの保存を提示して利用者の明示承認を得た
- 専用live testを1回だけ実行した。12.43秒後に `Cloudflare E2E request failed` で終了し、retryは0、出力PNGは作成されなかった。credential値、生要求、生応答、provider本文は表示・保存していない
- 現行runnerはtransport、HTTP status、応答契約、画像検証の例外を同じ固定文言へ変換するため、この結果だけでは要求到達、認証、HTTP status、応答shape、課金、生成品質の失敗段階を確定できない。再実行せず、機密本文を保存しない段階別diagnosticを別作業にする

## 92. 2026-09-07: Cloudflare live失敗段階diagnostic

- 初回liveの固定エラーを再実行なしで改善するため、credential、Account ID、URL、prompt、任意header、provider本文、生例外、画像bodyを持たないclosed stage診断を先にtestへ追加した
- production変更前のfocused testは、診断API不在と設定例外漏れにより10 failed・18 passed・1 deselectedでREDになった。RED時のtest SHA-256は `031049c6875d23adac34f2245d3939fdfcbeee60beba93755b70354906f5221c` である
- `CloudflareLiveE2EError.safe_metadata()` は `configuration`、`output`、`transport`、`http_status`、`response_contract`、`image_content`、`unexpected` のstage、100〜599へ検証したHTTP statusまたはnull、request count、retry count、wall millisecondsだけを返す
- typed transport・response・image例外をprovider原文なしで分類し、非200応答は本文を読まずstatusだけを投影する。送信成功後のlocal保存失敗はrequest count 1を維持し、live pytestは失敗時も安全なJSONだけを出して固定messageで停止する
- focusedは31 passed・1 deselected、既存Cloudflare request・HTTP・counterfactual回帰を含む関連確認は124 passed・1 deselectedで成功した。初回liveは再実行せず、過去の固定エラーstageは未確定のまま維持した
- 標準offline gateは1,857 passed・13 skipped・4 deselected、lock 79 packages、Ruff 232 files、Markdown 16 files・local link 1,367件・anchor 965件、`git diff --check` で成功した。最終runner SHA-256は `69cbe04fec618501e2a0a27dda3ed41bd78195c0c446336d0b5c5716b5cb93be`、test SHA-256は `78d8681961759412fa19d9a4237be0fe3455f314a240423039533ec5cb3a6449` である

## 93. 2026-09-07: Cloudflare live画像内容診断

- endpoint、固定合成入力、512×512、seed、1 call、retry 0、120秒timeout、4 MiB応答上限、`.env` credential、出力範囲、1 tile `$0.000287`見積を再提示し、別の明示承認を得た。累積の実課金はprovider側で確認していない
- 専用live testを追加で1回だけ実行し、28.246秒後に `failure_stage=image_content`、`request_count=1`、`retry_count=0` で停止した。出力PNG、credential値、生要求、生応答、provider本文、画像bodyは保存・表示していない。自動または手動の再実行は行っていない
- typed transport、HTTP 200、exact success JSON envelopeは通過し、local画像artifact検証で失敗した。`image_content` はBase64長、decode後2 MiB、raw PNG、512×512、単一frame、完全decode、正規化後2 MiBをまとめるため、保持していない実byteの個別条件は確定できない
- 公式モデル契約はBase64画像を返すがPNG形式を保証しない一方、現行parserはPillow decode前からraw PNGを要求する。外部通信なしの512×512 JPEG success envelopeも同じ `CloudflareImageError` を再現した。したがって通信・認証問題ではなくlocal受理契約の不一致が確認されたが、実応答がJPEGだったとは断定しない
- production codeは変更していない。次はJPEG・PNG・WebPを有界に完全decodeし、exact 512×512・単一frameを確認してmetadataなしRGB PNGへ正規化するTDDである。修正後のlive確認は別の条件提示と明示承認まで行わない

## 94. 2026-09-07: Cloudflare応答画像の安全な形式正規化

- 公式モデル仕様が成功結果をBase64画像とする一方、raw形式をPNGへ固定しないことを再確認した。外部通信、credential、課金を使わず、前回診断で特定したlocal受理契約だけを修正対象にした
- production変更前にJPEG・WebPの成功正規化とlive runner保存経路、BMP・破損・寸法違い・animation・oversize・decompression bomb拒否をtestへ追加した。同一test contentのREDは3 failed・10 passedで、JPEG・WebPが従来のPNG限定により `CloudflareImageError` になる期待理由だった。RED時test SHA-256はHTTP `7b26c07ba1aafe32ceb6b3b69e47f799091bc5f954f13b1f68bf32caa50833f3`、live runner `4110ca4af4e6471f7a58bca76048e6e8a26077b171382d07963e9a172ffae19a`
- provider raw画像をmagicとPillow formatの両方でJPEG・PNG・WebPへ限定し、2 MiB以下、完全decode、単一frame、exact 512×512、decompression bomb警告拒否を通した後だけ、metadataなしRGB PNGへ再encodeするよう変更した。同じfocused testは13 passed、関連Cloudflare回帰は133 passed・1 skippedになった
- 最初の標準gateではPlanのTD-011リンクanchor誤りによりMarkdown 1件だけ失敗し、コード関連は1,865 passedだった。anchorを修正し、最終gateはlock 79 packages、Ruff check・format 232 files、Markdown test 4 passed、offline pytest 1,866 passed・13 skipped・4 deselected、`git diff --check` に成功した
- 最終module SHA-256は `d1a0126bf308417e856bfbc7a6e3b323c92a699bbb54a4558805022d4f96e928` である。公開artifactは従来と同じschema 2.0・512×512 RGB PNGで、endpoint、model、prompt、request、credential、retry、timeout、利用量、保存処理は変更していない。修正後の実Cloudflare、実応答形式、画像品質、課金は未確認であり、live再試行は別の条件提示と明示承認まで行わない

## 95. 2026-09-07: Cloudflare画像正規化の1-call live確認

- `@cf/black-forest-labs/flux-2-klein-4b`、固定合成入力、512×512、seed `3006064433`、1 call、retry 0、120秒timeout、4 MiB応答上限、`.env` credential、出力1 tile `$0.000287`見積、成功PNGだけの保存を再提示し、利用者の別の明示承認を得た
- 専用live testを1回だけ実行し、11.728秒で成功した。pytestは1 passed、request count 1、retry count 0だった。追加のAPI送信は行っていない
- 生成artifactは175,824 bytes、SHA-256 `2fdac61f4a2af8cefdbcb971298a1d7414502947ea9a740b27b21929dce6d3cd`、512×512、RGB、単一frame、metadataなしのPNGで、`/tmp/amazon-explorer-cloudflare-reference.png`へ0600で保存した。credential値、生要求、生応答、provider本文は表示・保存していない
- これにより固定合成条件の基準画像1枚について、実Cloudflare通信、認証、成功envelope、画像decode・正規化、local保存までを結合確認した。4方向set、counterfactual生成、画像の意味品質、実請求額、production E2Eは確認していない

## 96. 2026-09-07: counterfactual Cloudflare最小live runner

- 成功した基準画像をローカルで目視し、白色・無地・陶器・単一ハンドル・単品・中立背景・正面斜めを満たし、文字、ロゴ、包装、余分な商品が見当たらないことを確認した。単一画像の固定条件確認であり、一般的な生成品質評価ではない
- 現行production正本は旧4方向ではなくdesired 1枚＋条件別counterfactualのexact `1 + N`であるが、この経路専用のlive runnerがないことを確認し、EXEC-071を開始した
- production変更前に、固定1条件・exact 2 calls・retry 0、JPEG・WebPから正規化した2枚の0600保存、既存path拒否、途中失敗時の部分出力なし、専用二重opt-inをtestへ固定した。最初のREDは専用module不在の `ModuleNotFoundError`、exit 2で、test SHA-256は `935127a0e25ba71a5f850189b26e0177bc4b47156c8da9211aa7a68f30d82b77` だった
- 最小runnerは「白い陶器製マグカップ」とsource-groundedな「白い」1条件だけを使い、desired生成後にその511×511参照を `input_image_0` とするcounterfactualを1回生成する。2 calls分633 micro-USDをlocal ledgerへ送信前予約し、開始済み失敗も利用量へ残す。credential、生要求、生応答、provider本文、画像bodyを診断へ含めない
- 保存失敗時のwall milliseconds欠落は追加testで1 failedのREDを確認し、2 calls消費、retry 0、経過時間を固定metadataへ残して作成済みdirectoryを除去するよう修正した。最終focusedは9 passed・1 skipped、既存1-call・counterfactual request/HTTP・共有正規化・利用量ledgerを含む関連回帰は151 passed・2 skippedだった
- 標準offline gateはlock 79 packages、Ruff check、format 234 files、Markdown 16 files・1,379 links・977 anchors・1,785 headings・205 fence pairs、pytest 1,875 passed・13 skipped・5 deselected、`git diff --check`の全てに成功した。最終SHA-256はrunner `7ac6c3c86038d5a2211ae4373cd6411b4bec782003ac69e52e243e56cba5fb5f`、test `abf33c53b2187b8b638e4c0178d654a014696f5b28cc3354aa0c7c41963196de`、selector `68038ce0b88f7a2e75dc643af16bacc3ff02d18a111ada3f85bfae7cf4923277`、pytest設定 `f403ec02d2709485ecdfa3ff42d4ce604707defe7c14e565d001c2796f196074` である
- 公式単価が入力512×512 tile `$0.000059`、出力512×512 tile `$0.000287`のままであることを直前確認し、入力1 tile＋出力2 tilesの見積額を`$0.000633`として、exact prompt・seed、2 calls、retry 0、各120秒timeout、各4 MiB応答上限、各2 MiB画像上限、credential、保存範囲を再提示した。利用者の明示承認後、専用test nodeを1回だけ実行し、1 passed、2 calls、retry 0、18.388秒で成功した。自動再実行と追加API送信は行っていない
- `desired.png`は142,018 bytes、SHA-256 `68ce57f009d990d899b715b20f6028722016bea5735f4a08b2da1153fbb59166`、`counterfactual-visual-condition-001.png`は194,184 bytes、SHA-256 `92677368bea8338ded0a36ceefa873e1a2d085e1fce7a03fbfbf438b6a68e24f`、reference set SHA-256は`a2480332862c1993af14ef30c832bb4647277692725ccb6c4c95d6ae32c8adac`だった。両方とも512×512、RGB、単一frame、metadataなしのPNGで、directory 0700・files 0600を読み戻した
- 目視ではdesiredが白い無地の陶器製マグ、counterfactualが同じ構図・形状・材質を保った青いマグであり、対象条件「白い」だけを反転する狙いを満たした。これは固定合成1条件・1組の定性的確認であり、未知条件全般の画像意味品質、2条件以上、4方向、CLIP、実商品、ranking、実請求額、production E2Eの成功を示さない

## 97. 2026-09-08: 実商品画像proxy・固定CLIP最小live runner

- 成功済みOutscraper taskを再実行せず、商品画像host側の失敗を分離するEXEC-072を開始した。商品画像URLの取得とlive GETは対象外とし、外部通信、credential利用、課金を行っていない
- production実装前に、exact `m.media-amazon.com`、GET 1回、retry 0、既存Cloudflare参照2枚との固定CLIP 3画像batch、成功後だけの0600 PNG保存、URL非露出、固定失敗stage、三重opt-inをtestへ追加した。最初のfocused pytestは未実装設定のImportError、exit 2でREDになった
- `ProductImageProxyLiveSettings`、専用pytest selector、`tools/product_image_proxy_live_e2e.py` を実装した。参照directory 0700・files 0600・所有者・単一link・exact 2 file・読込中identity、512×512 metadataなしRGB PNGを検証し、production proxyとprocess分離CLIPの上限を変更できないようにした
- focusedは12 passed・1 skipped、image proxy・DNS・HTTPS・CLIP process・counterfactualを含む関連回帰は318 passed・4 skippedだった。skipは明示opt-inが必要なliveまたはruntime nodeで、実host成功を示さない
- 文書同期後の標準offline gateはlock 79 packages、Ruff check、format 236 files、Markdown 16 files・local link 1,385件・anchor 983件・heading 1,798件・fence pair 206件、pytest 1,887 passed・13 skipped・6 deselected、`git diff --check`の全てに成功した。最終SHA-256はrunner `4851e57b934a0778e024e26601f101449056873f2dcb31f80f50877a6b1ff887`、test `a6761d71b9bb48552c023f8cc93b23250135602b1efafd3dde9706f9749af6ac` である
- URL取得条件として、Amazon.co.jpの「白い 陶器 マグカップ」検索、fresh browser profile、top-level navigation 1、送信前の外部要求上限100、retry 0、詳細ページ・login・既存Cookieなし、exact `m.media-amazon.com` URL 1件だけの秘密保存、credential・provider費用なしを提示し、利用者の明示承認を得た
- 隔離Chromiumを1回実行し、navigation 1、外部要求100件をcontinue、追加65件を送信前遮断、retry 0でURL 1件を `.env` の専用項目へ値非表示で保存した。`.env` は0600・所有者一致・通常file・Git除外、専用SecretStr設定でexact hostを読めることを確認した
- 商品画像、商品URL、生DOM、商品名、ASIN、Cookie、生responseを表示・artifact化せず、browser profileと一時runner・bytecodeを削除した。商品画像GET、CLIP live、Cloudflare、Outscraper、Bonsaiは0 callである。既存参照2枚、固定CLIP asset、新規output pathのlocal preflightは成功した
- 本番設計はOutscraper taskの商品情報を正規化し、各商品の先頭 `image_urls[0]` をproxyへ渡すことをコードで再確認した。ブラウザURLによる試験はこの出所・複数商品batch・ranking v5を確認しない限定smokeであると利用者へ説明し、理解後の明示承認を得た
- 専用live nodeを1回だけ実行し、1 passed、production proxyのGET 1、retry 0、固定CLIP 3画像、3.440秒、normalized margin 0.570058732で成功した。失敗再実行、Outscraper、Cloudflare、Bonsai、credential、provider課金はなかった
- 出力は14,690 bytes、320×280、RGB、単一frame、metadataなし、通常file・単一link・0600のPNGとして読み戻した。目視では白い無地のマグカップだった。URL、生response、header、IP、embeddingは表示・保存していない。この結果をOutscraper本番統合またはranking品質へ読み替えない

## 98. 2026-09-08: Outscraper商品画像から暫定ranking v5へのoffline統合

- 実装前にEXEC-073を作成し、実Outscraper・Amazon画像host・Cloudflare・Bonsai・credential・課金・API・frontendを対象外にした。保存済みCloudflare PNGだけではrequest metadataと消費済みapproval receiptがないため、production承認済み参照へ昇格させないと決定した
- 新しい統合testはmodule不在の `ModuleNotFoundError`、exit 4でREDとなった。RED時のtest SHA-256は `0d173265417e181a560557814672fe75411e892a0c2d28d580895cb6f272505b` である
- `provisional_search_pipeline.py` は、成功済みOutscraper利用予約、日本語query 1件・最大24候補、task 1回・retry 0を再検証し、観測値だけの商品正規化、typed-ranking-v4、承認済みcounterfactual参照、各商品の先頭画像、production proxy、固定CLIP、label-free batch較正、暫定ranking v5を一つのbackend入口へ接続する
- 結果はtask・poll・正規化・reject・画像要求・available・missing・unknownの件数だけを `safe_metadata()` へ投影する。provider request ID、商品名、ASIN、商品・画像URL、画像byte、embedding、生例外を含めない
- fixtureの4商品・4固有画像は `image_ready`、4商品・同一重複画像は有効候補4件未満の `image_unknown` となった。失敗済みOutscraper利用予約は画像取得0件のまま固定エラーで拒否した。focused 7 passed、Outscraper・正規化・typed ranking・counterfactual・承認の関連回帰144 passedを外部通信なしで確認した
- 標準offline gateはlock 79 packages、Ruff check、format 237 files、Markdown 16 files・local link 1,394件・anchor 992件・heading 1,811件・fence pair 206件、pytest 1,890 passed・13 skipped・6 deselected、`git diff --check`の全てに成功した。最終SHA-256はmodule `5cf1c1eab9c5af06780f2f07c5c23e6984326a0343a711aa75b43ea310929317`、test `d80bfc9af7ce37d1a99ce133b76043716f08d3c8b7f8ec429822b766a5926e32` である
- 実Outscraper task、Amazon画像GET、固定ONNX実推論、Cloudflare再生成、credential利用、課金は実行していない。実統合には、参照生成後の人間確認を同一実行状態で維持する専用runnerと、実行直前の別の明示承認が必要である

## 99. 2026-09-08: 人間確認で停止する暫定ranking live runner

- EXEC-074を作成し、Cloudflare desired・counterfactual生成、参照保存、人間確認、single-use consume、Outscraper 1 task、商品画像proxy、固定CLIP、EXEC-073を同一processの二段階へ接続した。固定合成入力は「白い陶器製マグカップ」、固定日本語queryは `白い 陶器製 マグカップ`、Cloudflareは2 calls、Outscraperは1 task、retryは全て0、候補と商品画像GETは最大24、CLIPは最大7 batchesである
- 準備段階は新規0700 directoryへ0600・単一linkの参照PNG 2枚を保存し、安全なpending metadataを返して停止する。承認後段階はdirectory・fileのdevice、inode、mode、link数、長さ、mtime・ctime、SHA-256、byte内容を同じfile descriptorで前後確認し、15分以内のSQLite single-use承認をconsumeした後だけ `OutscraperLiveSettings` loaderを呼ぶ。改ざんと期限切れのfixtureではloader 0回だった
- 最初のfocused実行はmodule欠落のcollection error、exit 2だったため有効なREDに数えなかった。公開契約だけのscaffold後、同一testは未実装固定例外により3 failed、exit 1となった。このbehavioral RED時のtest SHA-256は `ae1cd591b4d03a32208244c5eb162a42ef765fd4d38d21cef98de2f99841ded5` である。実装後は10 passed・1 live skipped、関連回帰は196 passed・5 deselectedで成功した
- 3つのpytest opt-in、absolute review directory、approval SQLite、固定CLIP asset root、TTY上の固定確認文を要求する専用live nodeを追加した。安全なmetadataには段階、call・task・poll・候補・画像・CLIP batch件数、参照digestだけを含め、Cloudflare token、Outscraper key、生response、provider request ID、商品本文・ASIN・URL、画像body、embedding、生例外を含めない。金額上限は設けずcall数だけを強制するが、実行直前の最新料金確認と見積り提示は必須のままである
- 標準offline gateはlock 79 packages、Ruff、239 filesのformat、Markdown 16 files・local link 1,400件・anchor 998件・heading 1,823件・fence pair 207件、pytest 1,900 passed・13 skipped・7 deselected、`git diff --check`で成功した。最終SHA-256はrunner `5cd2173ed5ea32eaea19317ad170e35c13bb5c043d9b601cfff468e3dec10feb`、test `699d491e9ae5cf1da52994e824a5ebe4b8948457e0e27305c0b99e3436b1333f` である
- offline実装完了時点では実Cloudflare、Outscraper、Amazon画像、固定ONNX、credential利用、課金を行っていなかった。次工程を、送信先、固定payload、全上限、credential種別、最新料金見積り、保存範囲の提示と、新しい明示承認後の専用live node 1回に限定した
- 2026-09-08に公式料金を再確認し、Cloudflare 2 callsの見積り0.000633 USD、Outscraper最大24商品の無料枠外見積り最大0.048 USD、金額上限なし、retry 0を提示して利用者の実通信承認を得た。新規private出力pathと固定CLIP assetをpreflightし、対話式専用nodeを1回だけ起動した
- Cloudflare exact 2 callsは成功し、desired 167,125 bytesとcounterfactual 161,829 bytesを0600 PNGとして保存した。目視ではdesiredが白い無地の陶器製マグ、counterfactualが濃い灰色の同種マグで、視覚条件「白い」の反転を確認した。2回目の固定文による承認までOutscraperは0 taskだった
- 2回目の承認後、Outscraperはexact 1 taskへ進んだが、専用nodeは `failure_stage=ranking`、`task_count=1`、`retry_count=0`、358.22秒、1 failedで停止した。自動・手動の再実行は行っていない。生response、provider request ID、商品本文、ASIN、URL、画像body、embedding、生例外は出力・保存していない
- 外部通信なしの診断でrepository固定ONNX runtime testは1 passed・3.22秒、保存済み参照2枚の同一process隔離CLIPは2 embeddings・2.997秒で成功した。kernel logにOOM、強制終了、segfaultはなく、確認時点で4.6 GiBのavailable memoryがあった。標準入力から起動した最初のprobeはPython `multiprocessing spawn`が `<stdin>` を再読込できず失敗したためCLIP診断証拠には採用せず、実file起動で再確認した
- 現行runnerは商品正規化、商品画像proxy、候補CLIP、較正、最終ranking契約の例外を一律 `failure_stage=ranking` へ縮約する。秘密・商品データを残さず安全なsubstageと完了件数を記録する診断境界を追加しない限り、今回の保存物と公開出力だけから失敗点をこれ以上特定できない
- 追加通信なしで、保存済み参照を使う4画像の実ONNX batchを実行し、4 embeddings・3.323秒で成功した。参照2枚1 batchと候補4枚6 batchesに相当する連続7回も、各2.761〜2.972秒、合計19.824秒で全て成功した。30秒timeout、4画像batch、7 batch上限、process繰返し起動を一般的な失敗原因から除外した
- 実Outscraperの単一queryで取り得る入れ子 `data` 形状、最大24商品、24画像、実ONNX 7 batches、label-free較正、ranking v5を合成・非機密入力で一続きに再現した。結果は `image_ready`、received 24、image request 24、available 24、unknown 0、21.424秒で成功した。別のfake embedding再現も入れ子24商品とbatch列 `[2, 4, 4, 4, 4, 4, 4]` を終了0で通過した
- 以上により、入れ子応答、24件上限、最大7 CLIP batches、固定ONNX、較正、ranking v5の一般的な統合不良は今回の原因ではない。実商品固有の正規化・typed ranking契約不一致、または実候補画像固有のCLIP・較正契約不一致が残るが、live時に生応答を保存せず安全なsubstageも未実装だったため、どちらかは断定できない
- 利用者指示により、再liveを行わず安全なsubstage診断を実装した。最初に参照CLIP、候補CLIP、較正失敗の期待を追加した同一focused testは3 failed・7 deselectedとなり、参照・候補の生 `RuntimeError` が境界外へ出ることと、固定評価errorにsubstageがないことをREDとして確認した
- `counterfactual_product_evaluator.py` は入力検証、参照CLIP、候補準備、候補CLIP、候補score、較正をclosed substageへ分け、画像要求・取得成功・参照／候補CLIP batch件数だけを固定errorへ持たせる。`provisional_backend.py` はbackend入力とranking v5を加え、`provisional_search_pipeline.py` はexecution、商品正規化、typed ranking、結果検証と正規化済み件数を加える。live runnerは同じmetadataだけを最外層へ伝搬する
- 未到達件数は0と推測せず `null` にし、生例外class・本文、Outscraper応答、provider request ID、商品本文・ASIN、商品・画像URL、画像digest、score、embeddingを診断へ含めない。fixtureの秘密文字列・URL・task IDがJSONへ現れないことをtestで確認した。focusedは24 passed・1 live skipped、Ruffは変更6 fileで成功した
- 関連回帰は166 passed・2 skipped・1 deselectedだった。標準gateはlock 79 packages、Ruff、239 files format済み、Markdown 16 files・local link 1,400件・anchor 998件・heading 1,824件・fence pair 207件、pytest 1,907 passed・13 skipped・7 deselected、`git diff --check`で成功した
- 標準gateの最初の並列pytest呼出しはmarker式 `not live_api` の引用符を引数組立てで失い、`live_api` をfile名として解釈して0件収集・exit 4になった。コードまたはtest failureではなく有効な検証に数えず、正しい固定コマンド `pytest -m 'not live_api'` を再実行して上記の全件成功を確認した
- substage診断実装後の新規liveについて、Cloudflare 2 calls、Outscraper 1 taskと最大50 poll、商品画像最大24 GET、retry 0、固定payload、credential、保存範囲、Cloudflare `$0.000633`、Outscraper最大24商品の無料枠外見積り最大 `$0.048`、金額上限なしを再提示し、利用者の明示承認を得た。新規pathと固定CLIP assetをpreflightして、同じ専用nodeを追加で1回だけ起動した
- Cloudflare exact 2 callsは成功し、desired 161,147 bytesとcounterfactual 177,948 bytesを新規0700 directory内の0600 PNGへ保存した。目視ではdesiredが白い無地の陶器製マグ、counterfactualが青い同種マグであり、固定文による参照承認までOutscraperは0 taskだった
- 参照承認後、Outscraper exact 1 taskは24候補を返し、24件を正規化、reject 0、画像URLあり24件、商品画像要求24件まで到達した。専用nodeは `failure_stage=ranking`、`failure_substage=result_validation`、retry 0、284.32秒、1 failedで停止し、自動・手動の再実行は行っていない
- `result_validation` は商品正規化、typed-ranking-v4、counterfactual商品評価、ranking v5が返った後、最終 `ProvisionalSearchResult` 契約の構築で失敗したことを示す。現行の安全な診断ではこの分岐の画像取得成功・参照／候補CLIP batch件数を保持しないため、これらは `null` であり、未実行または0件を意味しない。生response、provider request ID、商品本文・ASIN・URL、画像body、embedding、生例外は出力・保存していない
- 外部通信なしの決定的再現で、全商品画像取得を失敗させるとbackendは全候補を `missing` として正常完了する一方、集約側が `unknown` statusの不在だけで `outcome=image_ready` を選び、available 0件のため `ready image result is inconsistent` となることを確認した。4件取得成功の `image_ready` と、重複により有効1件の `image_unknown` を含む既存隣接test 3件は成功した。したがって今回の直接原因はall-missing時のoutcome導出と最終契約の不一致である。24件それぞれが利用不能になった下位のtransport理由は例外を意図的に破棄し、生URL・応答も保存していないため、今回のartifactからは遡及特定できない。production codeはまだ修正していない
- 画像取得失敗の下位原因調査として、Outscraper公式例の `image_1` がexact `m.media-amazon.com` であることを現行公式API文書で再確認した。同じ公開例URLは外部接続なしで現行正規化後も不変でallowlistを通過し、商品正規化・proxy・DNS・process隔離・HTTPS・serviceのoffline回帰248件も成功した。過去の同host実画像1 GET成功と合わせ、公式例形状のhost・構文拒否や恒常的なproxy不良は再現しなかった
- 完了結果の公式4時間保持期間内に、最新完了履歴最大1 GET、結合成功時だけ結果最大1 GETと商品画像最大1 GET、retry 0、credential、timeout、費用見積り、非保存範囲を提示して利用者の明示承認を得た。最初のCLI起動はmodule path解決前に終了し、credential読込・外部要求0件だった。root module起動へ訂正した診断はOutscraper履歴GET 1回後、最新項目がusage 24・単一項目・有効IDという保守的結合を満たさず `task_binding` で安全停止した。結果GETとAmazon GETは0回で、残り枠を別用途へ流用せず、一時ラッパーと生成bytecodeを削除した
- したがって、今回24件が利用不能になった直接の下位境界は各商品の `proxy_service.fetch_image()` だが、actual URLのallowlist拒否、DNS、pinned-IP接続、TLS、HTTP status、応答metadata、body、decodeのどこかはまだ確定していない。同じtaskを安全に再取得するには、複数履歴を読んでusage 24の一意な候補へ結合するか、利用者がprovider画面で直前request IDを秘密設定へ保存する必要があり、どちらも新しい外部送信条件と承認が必要である
- usage値への依存を除いた訂正版について、最新完了履歴最大1 GET、履歴が単一項目と有効IDを満たした場合だけ結果最大1 GET・商品画像最大1 GET、retry 0という条件を再提示し、利用者の明示承認を得た。実行はOutscraper履歴GET 1回後に再び `task_binding` で安全停止し、結果GETとAmazon GETは0回だった。この承認枠での自動・手動再実行は行わず、一時診断コードと生成bytecodeを削除した
- Outscraper公式Python SDKの現行実装も、`GET /requests` の成功JSONを加工せずlistとして返し、各項目の `id` を `GET /requests/{request_id}` に渡す契約である。したがって2回目の失敗はusage条件ではなく、今回の履歴応答が「1要素のlist、その要素がobject、有効な文字列id」という結合条件のいずれかを満たさなかったことを示す。ただし保守的probeは応答形状を保存・出力しなかったため、空list、要素数、top-level型、id欠落・形式のどれかは遡及確定できない。画像下位原因の特定には、安全な形状分類を含む新しい承認済み履歴取得が必要である
- 履歴結合を経由せず下位原因を直接調べるため、同じ固定query・amazon.co.jp・日本語・固定郵便番号・最大24商品について、新規Outscraper task exact 1、poll最大50、各商品画像最大1 GET、retry 0、credential、timeout、非保存範囲、無料枠外最大 `$0.048`、金額上限なしを提示し、利用者の明示承認を得た。段階別件数だけを出す一時probeを外部通信なしでRuff・compile・URL拒否例により確認してから1回起動した
- 新規taskはpoll 9回で24候補を返し、24件すべて正規化、reject 0、画像URLあり24件だった。24件すべてURL allowlist検証を通過した後、process隔離DNS段階で失敗したため、Amazon HTTP GETは0回、HTTP status・metadata・body・decode到達も0件だった。task 1、retry 0、269.869秒で完了し、商品名、ASIN、URL、画像、provider ID、生応答、生例外は保存・表示していない。したがって24画像が `missing` になった今回の下位原因は `m.media-amazon.com` に対する現行DNS resolver境界である
- 現行DNS resolverは1回の `getaddrinfo` 結果を重複排除する前に最大8件へ制限し、9件以上、空、非list、canonical name・family・socket type・protocol・address tupleの契約不一致を一律失敗にする。process側も5秒timeoutと同じ8件上限で固定errorへ縮約する。offline DNS回帰99件は成功し、9件を返すfixtureが拒否されることを確認した。ただしlive probeは安全のため生DNS結果・件数を保持しなかったので、今回が「9件以上」か別のresolver契約不一致かは、追加の単一DNS形状probeなしには断定しない
- 最終特定のため、`m.media-amazon.com` に対するsystem resolverの `getaddrinfo` exact 1 call、10秒外側timeout、retry 0、HTTP・credential・課金なし、件数と契約適否だけを出力する条件を提示し、利用者の明示承認を得た。結果はraw 9件、IPv4 1件、IPv6 8件、unique 9件、canonical name空9件で、現行bounded DNS契約は拒否した。したがって原因は、正常な9件のDNS応答を重複排除前・後とも8件上限超過として拒否する固定上限であり、URL、TCP、TLS、Amazon HTTP応答ではない。一時probeとbytecodeは削除し、生IP、canonical name、生応答、生例外は保存・表示していない
- 利用者指示により、DNS上限適用順序と全画像missing時のoutcome修正へ進んだ。production変更前に、重複DNS結果の除去、一意9件の受理とtransport候補8件への制限、全画像missingの `image_unavailable` を要求するfocused testを追加し、現行実装が重複を保持、一意9件を拒否、全missingを `result_validation` で拒否する3 failedをREDとして確認した
- DNS adapterは生 `getaddrinfo` 結果を最大64件まで受理して上限内の全項目を構造検証し、結果順を保って重複除去した後に既存transport・process IPC上限の8件へ制限するよう変更した。64件の重複を1件へ縮約でき、transport上限外の9件目が不正なら全体を拒否し、65件は拒否する回帰を追加した。検索pipelineは有効4件以上を `image_ready`、較正不能を含む0件を `image_unknown`、全件missingを `image_unavailable` として区別する
- 同一focused RED 3件は実装後3 passed、DNS・process・proxy・HTTPS・画像評価・live runnerの関連回帰は241 passed・1 skippedとなった。標準offline gateはlock 79 packages、Ruff、239 files format済み、Markdown 16 files・local link 1,400件・anchor 998件・heading 1,824件・fence pair 207件、pytest 1,911 passed・13 skipped・7 deselected、`git diff --check`で成功した。最終SHA-256はDNS module `e4d3336a304b19907a0acde67b68ca44b2b8d17a20ab1f41a8395d974c185204`、pipeline `22f68ab661f04b907890ed3edd71c1b7fb089a24329b40eaa604bfea08490eb2`、DNS test `7c433451d5c8426c2bb754127f413cd1c5d520bd783794e9ba109078ee732956`、pipeline test `b73d441d515bf1a10324d3ee55cedb60d5d4b3f5533608a4eecd39a4ffd4fdc5` である。修正後の実DNS・Amazon GET・CLIP・ranking liveは実行していない
- 修正後の再検証では、Cloudflare `$0.000633`、Outscraper無料枠外最大 `$0.048`、金額上限なし、retry 0を再提示し、利用者の二段階承認後に対話式専用nodeを1回だけ実行した。Cloudflare exact 2 callsでdesired 180,600 bytesとcounterfactual 181,540 bytesを新規0700 directory内の0600 PNGへ保存し、目視確認後にOutscraper exact 1 taskへ進んだ。poll 9回で24候補を受信し、24件を正規化、reject 0、画像URLあり24件、Amazon画像要求24件・取得成功24件、missing 0、unknown 0、固定CLIP 7 batchesを経て `outcome=image_ready`、`stage=completed` となった。pytestは1 passed・357.95秒で、task追加、retry、自動再実行はなかった。credential、生provider応答、商品本文・ASIN・URL、画像body、embedding、生例外は出力・保存していない。これは固定1条件・最大24候補の限定live成功であり、未知条件全般、複数query、4方向参照、個々の順位品質、Windows native、API・browser・外部委託中frontend、production E2Eを示さない

## 100. 2026-09-08: 暫定本番検索のjob・履歴接続と無quota方針

- 利用者判断により、現行local productionではper-user・session・day・cost quotaを一切設けない。既存quota有効policyは互換維持し、production policyだけを明示的な無quota modeにしてattemptと費用を拒否判定なしで記録する。Bonsai 1 call、Cloudflare exact `1 + N`、Outscraper task 1回、候補・画像・poll・byte・timeout上限、自動retryなし、明示承認は操作契約として維持した
- `production_search.py` は最終承認済み検索、同じowner・session・元入力に結ばれた承認済みcounterfactual参照、条件をdomain-separated job bindingへ固定する。worker内でだけOutscraper credential loaderを呼び、既存認可・1 task、暫定pipeline、schema 5.0履歴保存を順に実行し、成功時は履歴locatorだけをjobへ返す
- production実装前のtestは無quota policy helperのimport errorでREDとなった。production serviceがquota有効ledgerを受理する補足RED 1 failedも確認した。実装後はfocused 73 passed、全v2 1,082 passed・13 skipped、標準offline gate 1,916 passed・13 skipped・7 deselected、lock 79 packages、Ruff 241 files、Python 3.10 AST 234 files、Markdown 16 files・local link 1,406件・anchor 1,004件・heading 1,835件・fence pair 207件で成功した
- fixture E2Eは承認済み投入、Outscraper相当1 task、4商品画像、固定CLIP fixture、ranking v5、job成功、履歴再読込を一続きで確認した。同一bindingの重複投入でもtask相当は1回で、transport失敗時は失敗jobだけを残して履歴と自動retryを作らない。job DBに検索文が含まれないことも確認した
- 実Bonsai・Cloudflare・Outscraper・Amazon、credential、課金、browser、API、外部委託中フロントエンド、deploy、commit、pushは実行・変更していない。この成功はoffline production backend接続であり、実サービスproduction E2Eではない

## 101. 2026-09-08: local検索job・履歴HTTP API

- 利用者判断により、新application serviceを含む再live testは不要とし、job投入・状態取得・取消・履歴取得APIの実装へ進んだ。委託フロントエンドの内容確認・起動・テスト・接続、provider通信、credential読取り、課金は対象外とした
- `tests/test_search_v2_production_api.py` を先に追加した。初回はmodule不在のcollection errorでexit 2となったためbehavioral REDに数えず、公開scaffold後に未実装固定例外による6 failed・exit 1を確認した。behavioral RED時のtest SHA-256は `a70947f8088bac2452d41c63059bc43005f513f15630eb05b1323d605c142a0f` である
- `src/search_v2/production_api.py` にStarlette ASGI application factoryを追加した。`POST /api/v1/search-jobs`、`GET /api/v1/search-jobs/{locator}`、`POST /api/v1/search-jobs/{locator}/cancel`、`GET /api/v1/search-history/{locator}` の4 routeを持ち、server自体は起動しない
- 最終承認controllerが検証済み `ProductionSearchCommand` を同一processへ登録するin-memory submission storeを追加した。capabilityは43文字のrandom値、最大15分、専用headerだけで受ける。初回投入後はcommand参照を破棄し、期限内の同一capability再送は既存jobを返すためproviderを再実行しない
- APIはASGI client addressのIPv4・IPv6 loopbackだけを受け、ownerをrequestから受け取らず固定 `local-user` を使う。job応答からowner・binding・内部failure codeを、schema 5.0履歴応答からprofile・known accuracy・digest・score・画像bodyを除外した。期限切れ、未知locator、terminal取消、競合、storage失敗、想定外例外、method違反を本文非保持の固定JSONへ投影し、全応答へno-storeとnosniffを付ける
- 期限切れ、15分超過拒否、重複投入、状態取得、queued取消、terminal取消、取消race、履歴projection、未知resource、loopback拒否、想定外例外秘匿、405をfocused 11件で確認した。production service・job・履歴を含む関連回帰は31 passedだった
- 標準offline gateはlock 79 packages、Ruff成功、243 files format済み、Markdown 16 files・local link 1,417件・anchor 1,013件・heading 1,852件・fence pair 207件、pytest 1,927 passed・13 skipped・7 deselected、`git diff --check`で成功した。最終SHA-256はmodule `5d64e222adcd67fabda3b50ed5bba910b9c554c4c47ad8d10d13d7d619a5183a`、test `0f1c62edfab7e794ac22a99710c13eb4bbaf48ee3b3f8fde49a1a9ff45625828` である
- Starletteは既存lock内の推移依存だったが、production codeの直接importに合わせて `pyproject.toml` の直接依存へ追加し、現行pyproject全体をofflineでlock同期した。SQLite schemaとmigrationは変更していない
- 実装済みなのは依存注入型のlocal ASGI factoryである。server起動構成、最終承認controller、認証、履歴一覧・画像body・削除API、legacy Streamlit、外部委託中フロントエンド、browser、実provider E2E、deploy、commit、pushは実行・接続していない

## 102. 2026-09-08: 参考画像1枚の了承後に4方向と偽画像を生成

- 利用者指示に基づき、先行1枚の確認で停止し、明示了承後にその画像を参照して別の4方向画像と条件別の偽画像を生成する方式へ変更した。先行1枚の初回と作り直しは最大2回、後続生成は同じ了承につき1回とし、商品検索の最終承認を分離した。詳細は [EXEC-077](GOAL.md#exec-077-参考画像1枚の確認後に4方向と偽画像を生成) を参照する
- `orchestrator.py` にprocess内の15分参考画像確認と、了承・作り直し・破棄・後続生成の制御を追加した。確認は同じowner・session・条件・画像へ結び付け、古い確認、二重・並行実行、期限切れ、画像OFFから後続生成しない。4方向の全要求に同じ了承済み画像を渡し、偽画像はdesiredの再生成なしに選択した視覚条件数だけ生成する
- 先行生成、4方向、偽画像の利用量を別々に予約し、作り直し前の後続成功・失敗分も保持する。review中に新しい2種類の利用量を削除したledgerから最終検索へ進める問題をfixtureで再現し、全画像利用量の照合へ修正した。偽画像失敗後の画像OFF、再生成後の旧4方向採用・最終承認の拒否も確認した
- 基本フローの初回テスト2件は新引数未対応の `TypeError` で失敗したもので、画像生成本体のbehavioral REDとは分ける。その後の境界テストは修正後に追加しており、TDDの「振る舞いを示す同一テストでREDからGREEN」の工程を守れていない。工程逸脱として記録し、後からコードを壊してREDを作成せず、attested TDDと表現しない。初回と最終のテストSHAはEXEC-077へ記録した
- `uv run --frozen --offline --no-sync pytest -q -m 'not live_api' tests/test_search_v2_reference_image_approval.py tests/test_search_v2_reference_image_flow.py tests/test_search_v2_orchestrator.py` は36 passed。先行画像・偽画像HTTPの追加11件と既存関連14件は25 passedで、対象Ruff・formatも成功した
- Figmaの [先行1枚確認](https://www.figma.com/design/PEVM5G4854vaDqdWgSA3ui?node-id=59-22)、[了承後の生成中](https://www.figma.com/design/PEVM5G4854vaDqdWgSA3ui?node-id=169-71)、[4方向と偽画像の確認](https://www.figma.com/design/PEVM5G4854vaDqdWgSA3ui?node-id=169-172) を更新し、条件整理、最終確認、拡大・作り直しダイアログ、画面一覧も同期した。先行カード1件、後続4方向と偽画像1条件の表示例をread-backし、3主要画面でNoto Sans JP以外の文字と可視auto-layout要素のはみ出しはいずれも0件だった。スクリーンショットと保存後の3サムネイルを確認し、先行了承から生成中・完成へのFigma内プロトタイプ遷移を接続した
- 旧2枚生成の専用live runnerは独立した限定診断として維持し、新製品フローを検証しないことをmoduleとDEVELOPMENTへ明記した。先行画像の確認状態は再起動で失効し、履歴schemaは変更しない。新フローの実画像生成、商品検索provider、credential利用、課金、browser、委託フロントエンドの確認・接続、deploy、commit、pushは行っていない
- 暫定productionの公開入口も先行1枚で停止する方式へ接続し、SQLite参照承認、検索の最終承認、production job、fixtureの商品取得・CLIP、SQLite履歴の再openまでを確認した。focused回帰は46 passed。画像6 calls、二重job submitでも商品要求1回で、schema 5.0に保存したdesiredと偽画像のpixelは生成物と一致した。raw入力と視覚条件の正規化sourceは別々に照合し、既存の履歴schemaと保存枚数は維持した
- 暫定production側では、古い生成物のSQLite承認が拒否されないREDと、新しい画像承認済みplanが画像OFF限定validatorに拒否されるREDをそれぞれ確認して修正した。この個別のRED→GREENは、前述のcore実装のTDD工程逸脱を解消した証拠とは扱わない
- 標準offlineゲートの初回は1 failed・1,959 passed・13 skipped・7 deselectedだった。原因は履歴test fixtureが旧 `generate_images()` の引数と操作順を使っていたことで、先行1枚→明示了承→4方向と偽画像→採用へ更新し、既存の保存4枚と固定順序の検証を維持した。同fileの9 passedとRuff・format成功後、全体を再実行して1,960 passed・13 skipped・7 deselected、43.71秒で成功した
- lock 79 packages、Ruff check、format 248 files、現行Markdown 16 filesのリンク・見出し参照・コードフェンス、`git diff --check`も成功した。skipとdeselectionを含む通常offlineゲートであり、新フローの実provider生成、実画像品質、ブラウザと委託フロントエンドの動作確認ではない


## 103. 2026-09-08: 自然言語からランキング・履歴までのbackend E2E準備

- 利用者から実本番backend E2Eの指示を受け、[EXEC-078](GOAL.md#exec-078-自然言語から画像確認ランキング履歴までのbackend-live-e2e) を開始した。既存2-call診断はBonsaiと履歴を通らないため、新しい専用runnerとlive nodeを追加した
- 合成自然言語から本番Bonsai request v8とstrict intent・query生成、先行1枚、15分以内の人間了承、4方向と偽画像1枚、生成物とqueryの最終確認、production job、Outscraperと商品画像proxy・固定CLIP・ranking v5、SQLite履歴の再openを同じ実行へ接続する。queryを固定値へ代替せず、Bonsai serverは画像生成前に停止する
- 最初の公開scaffoldに対する6 failed・1 passedから同じtest bytesで7 passedへ進めた。後続の実HTTP dispatchと失敗件数は2 failedから実装し、既存4方向enumと異なる期待名を訂正した。Bonsai cleanupと三重opt-inは3 failedから実装した。初回と最終SHA、工程ごとの証拠はEXEC-078へ記録した
- focusedは21 passed・1 deselected、関連回帰は94 passed・5 deselected。標準offlineは1,981 passed・13 skipped・8 deselected、50.28秒で成功した。lock 79 packages、Ruff、format 251 files、現行Markdownと `git diff --check` も成功した。実providerまたは実CLIP成功の証拠ではない
- 新規0700出力directoryと0600 PNG 6枚、生成query、ランキング・履歴の表示用JSON、実行用SQLite DBを対象とする。参照fileは承認後にidentity・mode・内容を再照合し、履歴の表示内容と保存画像2枚のpixelを再open後に照合する。失敗時は固定stageと実開始件数だけを表示し、生provider応答・秘密値・承認token・embeddingを保存しない
- 固定Bonsai binary・GGUFのdigest、固定CLIP assets、port18080非listen、出力path未存在をread-onlyで確認した。公式料金を再確認し、画像6 calls約0.002017 USD、商品最大24件は無料枠外単価で0.048 USD、合計約0.050017 USD・金額上限なしの実行条件を用意した。AGENTS.mdの実行直前の明示承認を待っており、Bonsai起動、実画像生成、Outscraper、商品画像GET、credential利用、課金はまだ行っていない

- 2026-09-08 15:49 JST、提示済みの自然言語・Bonsai 1 call・Cloudflare計6 calls・Outscraper 1 taskと上限・概算費用・保存範囲に対して「開始せよ」の明示承認を得た。型付きcredential設定と固定asset、空きport・新規path、承認対象SHAを再照合し、専用live nodeを1回開始した。preflightは秘密値を表示せず設定型を確認しただけで、Outscraper要求は最終確認後まで行わない。

- 同じlive実行は、実Bonsaiのstrict intent・日本語query生成とCloudflare先行1 callで512×512のPNG保存まで成功し、参考画像への了承待ちで停止した。白い無地のマグカップを目視し、0700 directory・0600通常file・単一linkを確認した。後続4方向と偽画像、Outscraper、商品画像、CLIP、ランキング、履歴は未実行。Bonsai serverは既に終了した。

- 2026-09-08 15:51 JST、先行画像の提示に対して「了承した」の明示了承を得た。15分の有効期間内に同じ稼働中nodeへ固定確認文を1回入力し、後続4方向と偽画像1枚の生成へ進めた。新規E2Eの再起動やBonsaiの再推論は行わず、商品検索の最終確認はまだ行っていない。

- 同じnodeで後続4方向と偽画像1枚の計5 callsが完了し、先行分を含む6 PNGを確認した。4方向指定画像は取っ手が右に見えるほぼ同じ構図で、4方向の表現成功とは扱わず [ISS-002](ISSUES.md#iss-002-4方向指定の生成画像がほぼ同じ向きになる) を登録した。偽画像は青色だった。現在は生成物とqueryの最終確認待ちで、商品検索・ランキング・履歴は未実行である。system Pythonでの最初のPNG probeはPillow未導入で停止したが、準備済みuv環境で512×512 RGB・0600・単一linkを再確認した。追加の外部要求は行っていない。

- 2026-09-08 15:55 JST、生成物の視点不足と偽画像、実Bonsai由来queryを提示した上で「はい」の最終承認を得た。同じnodeでSQLite参照承認と検索承認を消費し、production jobへ進めた。追加の画像生成、Bonsai再推論、E2E再起動は行わず、ISS-002は未解決として維持する。

- 同じlive nodeは667.58秒で1 passed。Bonsai 1 call、Cloudflare 6 calls、Outscraper 1 task・8 polls、商品画像23/23、CLIP 7 batches、23商品rankingと履歴再読込、参照画像2枚のpixel一致に成功した。別read-backでもranking/historyの商品一致と全file0600を確認した。元画像の4方向品質は未合格のままで、利用者の再生成指示を [EXEC-079](GOAL.md#exec-079-4方向画像の視点指示修正と限定再生成) で継続する。


## 104. 4方向画像の視点指示修正と限定再生成の準備（2026-09-08）

- 利用者が「4面が同じ画像であるため、再生成せよ」と指示した。画像bytesは別だが、取っ手が右にあるほぼ同じ向きだった。現行promptは方向名だけを指定しており、camera移動と遮蔽を明記するv2へ修正した。モデル内部の原因と実画像改善は未確定。
- [EXEC-079](GOAL.md#exec-079-4方向画像の視点指示修正と限定再生成) と [DEVELOPMENT 6.7](DEVELOPMENT.md#67-同じ参考画像から4方向だけを再生成する限定診断) に、同じ参考PNGから4 callsだけを行う診断・再開手順を記録した。元E2Eは23商品ranking・履歴再読込まで完了した。追加診断は固定合成属性を使用し、元Bonsai応答の復元やproduction jobの再開とは扱わない。
- prompt検査1 failed、診断scaffold5 failedから実装し、関連112 passed。標準offlineは1,987 passed・13 skipped・8 deselected、54.52秒、lock・Ruff・format・Markdown・diffも成功した。RED/GREENのtest digestと訂正経緯はPlanに記録した。
- 参考画像のdigest・mode・511px入力化、新規保存先をofflineで検証した。Cloudflare公式の追加4枚見積りは0.001384 USD、金額上限なし。追加liveへの条件提示・承認待ちであり、視点品質が直ったとは報告しない。

- 2026-09-08 16:06 JST、追加4枚の具体的条件に対する「はい」の明示承認を得た。提示済みrequest builder・runnerのSHA一致を確認し、追加診断を1回開始した。

- 2026-09-08 16:07 JST、追加4 calls・retry 0がexit 0で終了した。4 PNGの512×512 RGB、0600、単一link、digest、0700 directory、元参考画像の不変を独立read-backで確認した。左側面指定では取っ手が見えなくなったが、残る3枚は取っ手が右に見えるほぼ同じ向きだった。正しい遮蔽と特徴消失は判別できず、4方向品質は不合格。ISS-002を未解決として維持し、自動再試行しない。実請求は未取得で、費用は承認時見積り0.001384 USDのみである。


## 105. E2E検索停止と4方向生成の比較実験準備（2026-09-08）

- 利用者指示でE2E検索を停止したままISS-002の修正に集中する。対象E2E・画像再生成processが稼働していないことを確認し、Bonsai・Outscraper・ranking・履歴は再実行していない。
- 実transportのmultipartをofflineで捕捉し、方向別promptとseedが異なり、参考PNGが同一であることを確認した。既存8画像のpHashを計算し、目視でほぼ同じ構図の組が既存閾値5以下で検出されることを確認した。モデル内部の原因は未確定。
- 本番promptを再変更する前に、参考PNG・seed・寸法を固定してpromptだけを変える `landmark-v1` 診断を追加した。取っ手の最終位置・見える面・遮蔽を具体化し、生成物の6組のpHash比較をsummaryへ記録する。近似検出やoffline成功を正しい4面の証明にしない。
- profile選択・近似検出・未知profile拒否の3 failedから実装した。wire検査を含む関連97 passed。RED/GREEN digestと公式調査、具体的コマンド・受入条件は [EXEC-079](GOAL.md#exec-079-4方向画像の視点指示修正と限定再生成) と [DEVELOPMENT 6.7](DEVELOPMENT.md#67-同じ参考画像から4方向だけを再生成する限定診断) に記録した。
- Cloudflareへの追加送信・credential利用は未実行。事前見積りは同一modelの入力4 tile＋出力4 tileで0.001384 USD、金額上限なし。追加実画像の比較検証への条件提示・承認が次の段階である。

- 標準offlineゲートは1,991 passed・13 skipped・8 deselected（51.51秒）、lock 79 packages、Ruff、format 253 filesに成功した。追加実生成は未実行である。

- 2026-09-08 16:15 JST、landmark-v1の提示済み条件に対する「はい」の明示承認を得た。runner・test SHA一致を確認し、画像生成だけの4-call比較診断を1回開始した。E2E検索は停止したままである。

- 2026-09-08 16:16 JST: landmark-v1はCloudflare 4 calls・retry 0でexit 0となり、4 PNGの512×512 RGB・0600・digestと診断契約一致を確認した。pHash距離は正面/左12、正面/右6、正面/背面24、左/右12、左/背面20、右/背面24で、閾値5以下の組はなかった。しかし目視では正面斜めと右側面がともに取っ手を右に広く見せる像で、右側面の中央edge-onという事前基準を満たさない。背面の取っ手は左へ移動したが、左奥に一部隠れる指定も満たしていない。近似検出を通過しても4方向品質は不合格であり、ISS-002は未解決。本番への採用とE2E検索の再開は行わない。


## 106. 9Bモデルの失敗視点1枚比較を準備（2026-09-08）

- 4Bのlandmark-v1でも右側面の取っ手が中央edge-onにならなかったため、本番の4B契約を変更せず、Cloudflare 9Bを同じ参考画像・prompt・seedで1回比較する独立診断を準備した。これはmodel採用の決定ではない。
- `tools/view_model_probe.py` は固定9B endpoint、1 call・retry 0、有界response・PNG正規化、実modelを含むdigest、private PNG 1枚＋summaryだけを扱う。4Bのproduction artifact識別子を9B生成物へ流用しない。
- scaffoldの4 failedから実装し、関連84 passed。追加HTTP検査ではfixture field名の誤りを訂正した。RED/GREENの詳細・SHA・実行手順は [EXEC-079](GOAL.md#exec-079-4方向画像の視点指示修正と限定再生成) と [DEVELOPMENT 6.8](DEVELOPMENT.md#68-9bモデルによる右側面1枚の比較診断) に記録した。
- 9Bへの送信・credential利用は未実行。見積りは入力を1 MP分とした約0.017 USD、金額上限なし。E2E検索は停止を維持する。

- 最終標準offlineは1,998 passed・13 skipped・8 deselected（49.43秒）、lock 79 packages、Ruff、format 255 files、Markdown・diffも成功した。9B診断の参考PNG、右側面1 call、新規保存先、契約digestをofflineで確認した。追加liveは未実行。

- 2026-09-08 16:22 JST、9Bモデル右側面1枚の提示済み条件に対する「はい」の明示承認を得た。候補runner・test SHA一致を確認し、9B診断を1回開始した。E2E検索は停止したままである。

- 2026-09-08 16:22 JST、9Bの1 call・retry 0がexit 0で完了した。PNG・private属性・digest・実model・契約一致を検証した。取っ手が中央手前に細く見える右側面となり、4Bで失敗していた視点が改善した。4面全体・汎用promptは未検証なので、E2E検索と本番model切替は行わない。


## 107. 9Bで汎用4方向promptを検証する準備（2026-09-08）

- 9Bでlandmark-v1の右側面が改善したことを受け、既存の汎用camera-v2 promptをそのまま9Bへ送る `generic-four` modeを独立診断runnerへ追加した。既定1-call modeを維持し、追加modeは最大4 calls・retry 0に固定した。本番model・endpoint allowlistは変更していない。
- 汎用要求tupleの一致、1/4回の分離、未知mode拒否、失敗時停止、実HTTP adapterの4方向送信を4 failedからGREENにした。RED/GREEN同一test SHAはPlanに記録した。関連20 passed。汎用4方向の追加liveは未実行。
- 追加条件と合格基準、4 calls・0.068 USD見積り・金額上限なし・別保存のコマンドを [DEVELOPMENT 6.8](DEVELOPMENT.md#68-9bモデルによる右側面1枚の比較診断) に固定した。実行には新しい条件への明示承認を要し、E2E検索は停止したままである。

- 最終標準offlineは2,002 passed・13 skipped・8 deselected（49.57秒）、lock 79 packages、Ruff、format 255 files、Markdown・diffも成功した。汎用4枚の追加liveは条件承認待ち。

- 2026-09-08 16:26 JST、9B汎用4方向検証の提示済み条件に対して「はい」の明示承認を得た。runner・test SHA一致を確認し、generic-fourを1回開始した。E2E検索は停止したまま。

- 2026-09-08 16:27 JST、9B generic-fourは4 calls・retry 0で完了し、PNG・digest・契約一致を確認した。左右で取っ手が左右に開く像となり、参照cameraから90度回った像としては不合格。相対角度と絶対面名の混在、および四等分でない角度指定をsourceで確認した。camera固定・objectの参照相対回転に統一した診断を準備する。


## 108. 参照姿勢から四等分する回転診断を準備（2026-09-08）

- `turntable-four` を独立診断に追加した。cameraを固定し、objectを参考画像から0/90/270/180度へ回し、生成promptから未定義の絶対面名を除く。既存angle IDは出力の対応付けに維持する。
- 新mode拒否のRED 1 failedから同一testのGREEN 1 passedを確認し、整形後に関連21 passedとなった。RED SHAとコマンドはEXEC-079に記録した。本番prompt・modelは変更していない。
- 実画像の合格基準を固定し、追加9B 4 calls・見積り0.068 USD・retry 0の条件と再現コマンドをDEVELOPMENT 6.8に記載した。追加liveは未実行、E2E検索は停止中。

- 最終標準offlineは2,003 passed・13 skipped・8 deselected（50.40秒）。lock 79 packages、Ruff check・format 255 files、Markdownとdiff検査に成功した。turntable-fourの追加liveは未実行で条件承認待ち。

- 2026-09-08 16:36 JST: turntable-fourの追加4枚について、同じ参考PNG・511px入力・512px出力、回転指示0/90/270/180度、9B endpoint・既存Cloudflare token、4 calls・retry 0・接続/読込各120秒・response 4 MiB・画像2 MiB、約0.068 USD見積り・金額上限なし・別保存の提示に対して利用者が「はい」と明示承認した。runner・test SHA一致を確認し、DEVELOPMENT 6.8のturntable-fourコマンドを1回開始する。E2E検索は停止したままである。

- 2026-09-08 16:37 JST: turntable-fourは9B 4 calls・retry 0でexit 0となった。実model、事前契約SHA-256 b7d0cb360b9993ff3ec621d44035a6c35785e63d8b71736ffb8a7a4fb5ff7aa3、全4 PNGの512×512 RGB・digest・0600、directory 0700を検証した。目視では0度でも取っ手が手前側へ回り、反時計回り90度はカップが倒れて複数の取っ手に見える形になり、時計回り90度も上面向きと複数の突起を生じ、180度では開口部が下へ向いた。camera固定・垂直軸回転・取っ手1個・形状維持の基準に不合格。指示の混在を除いても今回のmodelは追従せず、契約不整合が唯一の原因ではない。承認済み4 callsは完了し、追加prompt試行とE2E検索は停止する。実請求は取得せず、事前見積りは0.068 USD。
- 検証補助の初回コマンドはsystem PythonにPillowがなく失敗した。uvの準備済み環境でread-backを実行し直して成功した。追加生成は行っていない。

- 実GPUはRTX 4070 Ti SUPER・16,376 MiB、確認時空き13,079 MiB。公式資料に基づき、単一3D meshから固定角度で描画する代替方式と互換・cache・品質の未検証境界をEXEC-079へ記載した。model取得・依存導入・推論・本番切替は未実施。


## 109. 本番iGPU制約によりローカル3D生成案を撤回（2026-09-08）

- 利用者が本番iGPU・ローカル3D生成不可を明示した。開発機の専用GPUを本番の判断材料とした案を取り下げ、REQUIREMENTS・BACKEND・EXEC-079・NEXT-STEPSへ制約を反映した。モデル取得・環境構築・推論は実施していない。
- 外部API候補としてfal.ai Qwen Image Edit 2511 Multiple Anglesの公式仕様を確認した。角度指定は内部で専用LoRA用promptへ変換されるため、数値fieldだけで角度・形状の正確さを保証しない。候補と未検証境界をEXEC-079へ記録した。
- 公開資料の閲覧と文書更新だけを行い、画像送信・credential使用・課金API実行はしていない。4面問題は未解決、E2E検索は停止中。


## 110. 4方向画像生成を製品フローから除去（2026-09-08）

- 利用者指示に従い、参考画像1枚→明示了承→条件別偽画像のみ→生成物確認→商品検索最終承認→既存ranking・履歴へ変更した。生成回数は通常1+N（N=1〜3）、参考画像作り直し1回と両回の後続生成を合わせて最大8 calls。4方向の要求と利用予約を公開経路で作らない。
- `ImageReview` schema 4.0と専用成功遷移、承認profileを追加し、旧4方向executionを新フローへ流用しない。core新規履歴schema 3.0は参考1枚、暫定schema 5.0は既存参考1枚＋偽画像。旧4枚履歴の読み出しと低位adapterを維持した。CLIP・ranking式は変更していない。
- 1条件のE2E runnerを6 calls・PNG6枚から2 calls・PNG2枚へ変更した。途中の画像了承・最終検索承認は残し、実検索は再開していない。実provider送信、credential使用、課金、ローカル3D、新provider、未納品UIの起動・接続は行っていない。
- 生成数・承認allowance・履歴変換のREDからGREENを確認した。履歴の最初の失敗は旧fixture期待だったため、修正後のAttributeErrorを正式REDとして記録した。SHAとコマンドは [EXEC-080](GOAL.md#exec-080-4方向生成を製品フローから除去) に保持する。
- 関連回帰は118 passed・1 skipped。条件数1〜3の作り直し上限と第三回拒否を追加で確認した。最終標準offlineは2,006 passed・13 skipped・8 deselected（41.76秒）。lock 79 packages、Ruff check、format 255 files、Markdown・diff検査も成功した。
- Figmaの参考画像確認・偽画像生成中・生成後・最終確認・待機・モーダルを更新し、4視点カードと説明を除いた。最終確認で残存していた4枚サムネイルを参考画像と偽画像へ変更し、参照シートも更新した。該当screenのscreenshotとnode read-backを確認した。
- ISS-002とEXEC-079は要件撤回による終了とした。生成モデルの視点品質が改善したとは扱わず、過去の不合格診断を残す。commit/pushはしていない。


## 111. 4方向を除いた実検索backend E2Eを再開（2026-09-08）

- 2026-09-08 17:09 JST: 利用者の「改めて、実検索E2Eを開始しろ」に従い、DEVELOPMENT 6.6の現行runnerを1回開始する。固定合成入力、Bonsai 1 call、Cloudflare先行1＋了承後偽画像1、生成物・query確認後のOutscraper 1 task・最大24商品・50 polls、商品画像24 GET、CLIP 7 batches、自動retryなし、既存credential、別保存、金額上限なしを実行前に提示した。
- Cloudflare公式単価による画像合計見積りは0.000633 USD、Outscraper公式通常単価2 USD/1000 productsでは最大0.048 USD（無料枠残数・実請求は未確認）。新規出力は `/tmp/amazon-explorer-backend-e2e-reference-only-20260908-01`。先行画像の了承と商品検索の最終承認は対話待ちで停止する。

- 実行結果: 指定live nodeは43.91秒で1 failed。Bonsai 1 callからqueryを作成・保存した後、Cloudflare 1 callの `reference_generation` で停止した。Outscraper task・poll、商品画像GET、CLIPはすべて0。自動再試行は実行していない。
- 保存済み出力は `query.json` 1件（0600）、directoryは0700。preview・偽画像・ranking・履歴は未生成。生成query本文と生provider応答・例外は文書へ転記していない。
- 原因の確定範囲: 現行orchestratorは先行生成時の例外を固定失敗stageへ変換するため、今回の安全な出力ではHTTP・応答decode・画像内容検証のどこで失敗したかを分離できない。4方向除去が原因とは断定しない。Bonsaiの18080 listenが残っていないことをssで確認した（単純なbind確認では使用不可だったが、待受processの残存を示すものではない）。


## 112. 参考画像失敗の原因段階を保持する診断を追加（2026-09-08）

- 利用者の原因特定指示を受け、保存済み出力と実装を確認した。先行生成は例外を一律に握りつぶし、元のHTTP・応答・画像失敗を保持していなかった。終了済み試行の元例外は復元できず、過去の直接原因は未確定である。
- HTTP adapter / artifact / ReferenceReview / E2Eへ固定diagnosticを伝えるよう修正した。通信・HTTP status・応答契約・Base64・画像内容・artifact・予期しない失敗を区別する。診断には本文・例外文字列・credential・URLを含めず、HTTPエラーではbodyを読まずcloseする。
- 診断が失われる5 casesのRED 5 failedから同一testのGREEN 5 passedを確認した。関連53 passed、最終標準offlineは2,017 passed・13 skipped・8 deselected（43.59秒）。lock 79 packages、Ruff check・format 255 filesも成功。SHAと範囲は [EXEC-081](GOAL.md#exec-081-参考画像生成失敗の安全な診断) に記録した。
- 追加liveは未実行。Bonsai 1 call＋Cloudflare参考画像1 callだけの限定診断を準備した。失敗原因の確定には観測が必要であり、再現しなければ未確定のまま残す。AGENTS.mdの実行ごとの条件承認を求め、偽画像・商品検索・CLIPへ自動継続しない。

- 2026-09-08 17:22 JST: 利用者が提示済みの限定診断に「はい」と明示承認した。コード3 filesのSHA一致、portの非listen、新規output pathを確認し、Bonsai 1 call＋参考画像1 callだけの診断を1回開始する。偽画像・商品検索へ進まない。

- 承認済み限定liveの結果: 42.30秒で1 failed。Bonsai 1 call・Cloudflare 1 call、`cloudflare_failure={stage:http_status,http_status_code:429}` を観測した。画像bodyを読む前にCloudflareの非200応答で停止した。Outscraper task/poll、商品画像、CLIPはすべて0、retry 0。
- query.json（0600）だけが新規directory（0700）に保存され、preview・偽画像・ranking・履歴は未生成。ssでBonsai port 18080の非listenを確認した。
- 今回の直接原因はHTTP 429。Cloudflare公式資料は429に日次無料枠超過と処理容量不足を挙げているが、今回の内部code・quota残量は取得しておらず内訳は未確定。初回失敗も同原因だったとは断定しない。追加送信・制限解除・自動再試行は行っていない。

## 113. HTTP 429の利用量調査と内部code診断（2026-09-08）

- 既存credentialを用い、`api.cloudflare.com/client/v4/graphql` へ最大4回・各30秒・応答2 MiBのread-only調査を提示して実施した。schema確認2回は成功、当日Workers AI利用量・error code・時間別集計1回はHTTP 200内のGraphQL permission errorとなった。実使用量・契約planは取得できず、生成APIは呼び出していない。
- 当日の9B診断summary 3件で同モデルの1、4、4 callsとretry 0を再確認した。公式の最初の1 MP単価による出力9枚の見積り12,272.76 neuronsは、日次無料枠10,000を超える。無料枠超過が有力だが、512px出力の実計上量とaccount planを取得しておらず推定である。429は容量不足でも生じるため断定しない。
- 前の診断はHTTP statusだけで内部codeを失っていた。今回、HTTP 429のJSONを最大8 KiB（上限判定の追加読込は最大1 KiB）だけ検査し、公式に文書化された単一errorの整数code 3036 / 3040を保持する。重複key、未知code、不正JSON、複数error、上限超過ではcodeをnullとし、本文を保存・表示せずHTTP statusを維持する。provider codeはReferenceReviewからE2E出力へ伝える。
- 実装前に `uv run --frozen --offline --no-sync pytest tests/test_search_v2_counterfactual_cloudflare_http.py -k retains_only_known_error_code -q` で8 failed・終了1。原因は全casesでdiagnosticにprovider_error_codeがないことだった。RED test SHA-256は `2d6cfabde75c37ea9fd655996d1de67134231d69a4bb29ddb85b4db69f177f69`。同じ8 casesを弱めずGREENを確認し、既存期待値の新規null field対応とE2E伝播2 casesを加えた関連検証は39 passed・終了0。
- 最終test SHA-256はHTTP `dad96c803eaffde68fdf4c28f21b20edf54b79354bcd663d2dc63678f55196f2`、E2E `003777c57bf7e36bcf520dce136c18ba1842ee52753d52633de93f1632b4cfd0`、実装 `01da6e72f9fefe85e6c9f4e96c4a7c8749c55588ce7422e1f5314ca06006d897`。生成・Bonsai・商品検索・CLIP・frontend・commit・pushは未実行。
- 参照: [Cloudflare Errors](https://developers.cloudflare.com/workers-ai/platform/errors/)、[Cloudflare Pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)。新診断で3036 / 3040を実観測したという意味ではない。

- 最終標準offline gateは2,027 passed・13 skipped・8 deselected（43.19秒）、終了0。lock 79 packages、Ruff check、format 255 files、Markdownリンクを含むテスト、git diff --checkも成功した。実サービスの制限解除や新診断codeの実観測を示す検証ではない。

## 114. 現行4Bモデルの画像生成疎通を再確認（2026-09-08）

- 利用者の「現在、画像生成のリクエストが通るか確かめろ」を受け、現行4B endpoint、固定合成条件、512×512、既存Cloudflare token、1 call・retry 0、接続/読込各120秒、応答4 MiB、見積り0.000287 USD、成功PNGのみprivate一時保存の条件を提示して実行した。
- 17:38:51 JST開始。現行counterfactual desired requestとRequests transportを使う生成1 callは13.341秒でHTTP 200となり、512×512・163,572 bytesの正規化PNGを保存できた。保存内容のdigest一致と0600を再照合した。生要求・生応答・tokenは表示・保存していない。
- 現時点の4B画像生成リクエストが通ることを確認した。過去429の内部codeは復元できず、無料枠超過の推測を確定へ変更しない。Bonsai・偽画像・Outscraper・CLIP・ranking・履歴は実行せず、検索E2E全体の成功とは扱わない。

## 115. 4方向を除いた実検索backend E2Eの再試行（2026-09-08）

- 2026-09-08 17:40 JST: 利用者の再開始指示を受け、DEVELOPMENT 6.6の専用live nodeを新規output directoryで1回起動した。固定合成入力、Bonsai 1 call、Cloudflare 4Bの先行1枚＋了承後の偽画像1枚、最終確認後のOutscraper 1 task・最大24商品・50 polls、商品画像24 GET、CLIP 7 batches、自動retry 0、既存credential、private保存範囲、最新単価による見積りCloudflare 0.000633 USD・Outscraper有料換算0.048 USD、金額上限なしを再提示した。
- 実行前にBonsai server/modelと固定CLIP asset directoryの存在、18080の非listen、新規output pathを確認した。参考画像と生成画像・queryの二段階確認を省略せず、完了した段階だけを報告する。

- Bonsai 1 callによるquery作成とCloudflare 1 callの先行参考画像生成に成功し、reference confirmationで待機している。Bonsai port 18080は非listen。偽画像・Outscraper・CLIP・ranking・履歴は未実行。確認用PNGを利用者へ提示し、同じprocessで了承を待つ。

- 参考画像提示後の利用者の「はい」を受け、同じ実行processへ参考画像承認文を入力した。Cloudflareの追加1 callで偽画像1枚を生成し、search confirmationへ到達した。生成計2 calls・retry 0。参考画像・偽画像とBonsai由来queryの最終確認を待ち、Outscraperは未実行。

- 画像2枚とqueryの提示後、利用者の「はい」を受け、同じprocessへ商品検索承認文を入力した。17:46:32 JSTにproduction search jobがrunningへ遷移したことをread-only SQLite照会で確認した。新しいE2Eや別taskを作らず、同じ実行の完了を待つ。

- 専用live nodeは1 passed・終了0、548.83秒（画像確認の待ち時間を含む）で完了した。実Bonsai 1 call、実Cloudflare 2 calls、Outscraper 1 task・6 polls、商品画像24 requests / 24 successes、固定CLIP 7 batches、ranking 24商品、retry 0。SQLite履歴を再openし、参考画像と偽画像の計2枚を生成画素と照合した。
- 実行後に別のread-only確認でsummaryの上記件数、ranking.jsonとhistory.jsonの商品表示24件の完全一致、履歴schema 5.0・参照2枚、DBの単一job succeededを検査した。出力directory 0700・全9 files 0600、Bonsai port 18080の非listen、pytest processの終了0を確認した。
- 固定合成入力の自然言語→参考画像→人間了承→偽画像→画像/query最終了承→実商品検索→CLIP/ranking→履歴保存・再読込を一続きのbackend実サービスE2Eとして完走した。個別の順位品質、未知条件、Windows/iGPU、HTTP API、未納品frontend、実請求額は検証していない。追加task・自動retry・commit/pushは行わなかった。

## 116. 材質条件と材料名の色誤抽出を修正（2026-09-08）

- 利用者の修正指示に基づき、registry v2にmaterial.typeを追加し、Bonsaiのwire schema・prompt・source grounding、商品証拠profile v2、typed rankingの消費側を整合した。材質の完全一致termを元の強さでtypedへ補い、明示材質の欠落や曖昧な広義語はblockingとする。商品側の専用materialをtitleより優先し、欠落・曖昧・矛盾を保持する。色語直後のsoil/clay、材質の否定・材質風表現を肯定根拠から除いた。
- 初期REDは28 failed・4 passed。後段fixtureのfield参照誤りとpotteryの広義語扱いを訂正し、追加安全回帰も含む最終testを変更前sourceの独立一時copyで再実行した。35 failed・4 passedとなり、同一test SHA-256 `94b93a195024f18759df7b030330668dcc37f80b1962d960a9f74158cdb749df` の現行実装は39 passed。否定表現の追加2件も修正前にmatch/conflictの誤判定を確認してから修正した。詳細は [EXEC-082](GOAL.md#exec-082-材質条件と材料名の色誤抽出を修正) に記録する。
- 合成4商品による条件分解→正規化→typed判定→provisionalランキングで、白い陶器をconfirmed、材質不明をuncertain、磁器・ガラスをcontradictedとし、逆向きに与えた画像スコアで材質不一致が上位へ戻らないことを確認した。保存済み24位の表示titleの局所解析でも色値はwhiteだけとなった。旧24商品の再計算や実画像・素材品質の再評価ではない。
- 最初の全体gateは3 failed・2,063 passed。材質追加による生成schemaの新digestとpromptの属性名記載を整合し、既存15,032 bytes以下のrequest上限を変更せずに関連142 passed、最終全体2,066 passed・13 skipped・8 deselected（43.84秒）を確認した。Ruff・format 256 files・lock 79 packages・Markdown・diff checkも成功した。
- 最終SHA-256: typed_requirements `9e2b1428f52694dad7bad8cf7d6fe40446c0da0d17fa9b1098bdd08ab635e2f2`、product_evidence `f9c0dd910e58220499fba106fb5fe9672d1bd03de60077e9bb6fdab125fad82f`、bonsai_adapter `509a2bce4eacc9b77dddda1d44b51b87f098f2cc2a8e15d289409d3f32c195ad`、prompt `c3054785032141ce6c3fa4fcbff9d7dcb0ca9f5bc2d5ca511b4833a245558820`、typed_ranking `46a83d093591380b9a7b778272e08962b08b01e9a3f508d76e2b821cee176560`。
- 実Bonsai・Cloudflare・Outscraper・CLIP、API・未納品frontend、commit・pushは実行せず、既存のPNG・ランキング・履歴は変更していない。修正後の実検索と未知条件の順位品質は未確認である。


## 117. Bonsai提案から検索専用属性を追加するbackend（2026-09-08）

- 未commit。 [EXEC-083](GOAL.md#exec-083-入力に基づく検索専用属性の追加) に従い、原文を保持したBonsai要求へ不足属性のlabel・meaning・source_quoteを追加し、SudachiPyの位置情報と限定比較規則で根拠を検証する。共有registryは変更せず、検索専用registryをproposal・承認・商品証拠・rankingへ引き継ぐ。
- 商品側は正規化済みfeatures内のlabel付き仕様を共通の数値・真偽・カテゴリ・文字列集合として判定する。単位不整合・欠落はunknown、複数根拠はconflict。core表示履歴の追加属性名・条件・判定説明をSQLite再読込まで確認した。商品証拠profileはv3、既存title parserはv2を維持する。
- 最終新規testと同じSHA-256 `3df1e71cf89ae4853a42e6d9814fe3badc77834ec7eb9afbba0cddcc3dca8eb8` を変更前sourceへ適用し32 failed、現行32 passed。初期のprovider fixture field名をnameへ訂正した上でREDを取り直した。追加の否定切落し、OR/AND混同、定義改ざん、重複、単位、旧profile受理も修正前の失敗を確認した。
- `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short`: 2098 passed、13 skipped、8 deselected、46.95秒。lock check、Ruff check/format、Markdown検査、diff whitespace検査も成功。外部サービス、実Bonsai推論、委託frontendは未実行。
- 固定入力の要求は16,320 bytes、回帰上限は17,000 bytes。旧15,032 bytes以下から増加し、schema annotation削除・数値境界共用で抑制した。schema SHA-256は `7024677671c0f79d3e754da7e67e828a6f189d6e4cf9940a6960c6d8552365f7`。条件数・call数は従来どおり。通信量のfixture測定を実モデルの速度・品質成功とは扱わない。


## 118. 共通属性だけをプリセットとして残す（2026-09-08）

- 未commit。[EXEC-084](GOAL.md#exec-084-共通属性だけをプリセットにする) に従い、色・材質・形状・幅・向き・外観スタイルの6 keyへ限定した。対応モデル・接続方式・充電式・収納口数の固定登録とカテゴリ専用parserを除去し、卓上型・携帯型のform.factorを幾何形状のform.shapeへ置き換えた。
- カテゴリ固有属性はBonsaiのcustom提案で名前・意味・型・単位を検索ごとに定める。原文に属性名がなくても値や機能からの提案を受け、SudachiPy位置・値・単位・条件関係を照合する。商品は明示label付き仕様だけで判定し、不足を推測で埋めない。共通registry v3、商品証拠profile v4へ版を更新し、旧保留承認・再計算cacheを再利用しない。
- 最終16 testを変更前sourceへ適用して15 failed・1 passed、同じtestの現行実装は全件成功。test SHA-256 `4dbf886c683431e395afd78c22ab0ba4a3134c6776db5c70b214f37f28377fa9`。接続方式・充電式・収納数・対応モデル・設置方法の合成提案からrankingまでと、原文にない属性名の提案、旧key拒否、幾何形状の否定を確認した。
- `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short`: 2114 passed、13 skipped、8 deselected、44.49秒。後続のtest整理後も関連63 passed。lock 79 packages、Ruff check/format 261 files、Markdown links/anchors/fences、diff checkも成功した。
- 固定入力の要求は15,485 bytes、回帰上限17,000 bytesを維持した。生成schema SHA-256 `8f8b3218b729b704994a0c235e91a700e9511e683ea39068d63131ff0bcbdb02`。実Bonsaiの推論品質・実商品での仕様取得率は未検証であり、既存表示履歴と実画像、委託frontendは変更していない。


## 119. 共通属性変更後の実フローと順位監査の準備（2026-09-08）

- 利用者の実フローテスト指示を受け、[EXEC-085](GOAL.md#exec-085-共通属性変更後の実検索と順位監査) に固定入力、1 test 1 task、送信先・回数・最新見積り・保存範囲、全候補の条件根拠と順位を監査する基準を記録した。
- ローカル事前確認と関連offline 83 passed・1 deselectedを完了した。今回の実provider要求は未送信。実行条件の提示・承認後に既存対話runnerを1回開始し、画像確認で利用者を待つ。現時点で修正後の実順位品質を判定したとは扱わない。


## 120. 実Bonsai属性推論の単体テストを準備（2026-09-08）

- 利用者の「その前にBonsai単体」指示に従い、全検索EXEC-085を保留し、[EXEC-086](GOAL.md#exec-086-bonsai単体の検索専用属性推論) を先行した。固定合成入力1件で白色・容量下限・食洗機対応の提案を確認する専用runnerと個別opt-inを追加した。
- 受入判定の空stubは9 failed・1 deselected。実装後のoffline単体は11 passed・1 deselected。数値・単位・演算子・強さ・属性名・意味・対応真偽・欠落を検出し、1 callとcleanupもfixtureで確認した。語彙による意味確認は固定ケース用であり、一般的な意味理解の保証ではない。
- 最終offline全体は2125 passed・13 skipped・9 deselected、46.49秒。lock、Ruff check/format、Markdown、diff checkも成功した。model・prompt・完全schema・生成schemaと新規test/runnerのSHA-256を計画に記録した。
- 本番属性adapter・promptは変更せず、実Bonsaiは未送信。loopback1 call、認証不要・API費用0、raw応答非保存の条件を提示し、今回の単体実行の明示承認を待つ。Cloudflare・Outscraper・画像・rankingは実行していない。


## 121. 実Bonsai属性推論の単体試験は不合格（2026-09-08）

- 利用者の「実行しろ」を受け、提示済み条件の [EXEC-086](GOAL.md#exec-086-bonsai単体の検索専用属性推論) 専用nodeを1回実行した。runner/test SHAは事前記録と一致した。生成1 call・retry0、API費用0、credential不要、生応答・server log非保存。
- 1 failed、exit1、全体34.62秒。要求処理32.623秒、prompt934 tokens、completion107 tokens、応答1,029 bytes。proposal_ready=true、no_extra_preferences=true、shared_registry_unchanged=true。商品種別・条件数3件・白色・容量350ml以上・食洗機対応・検索専用属性2件の各固定判定はfalseとなり、事前の単体受入基準に不合格だった。
- 形式上readyは意味品質の合格を示さない。複合判定のfalseだけから属性未抽出と断定せず、実出力・adapter処理・判定語彙のどこで期待から外れたかは未特定とする。現在の診断はraw応答と抽出内容を保持しないため、同一応答で詳細を後追いできない。
- server_stopped=true、独立のport18080照会も非listen。追加推論、Cloudflare、Outscraper、画像、CLIP、ランキングは行わず、全検索EXEC-085を保留した。計画・開発手順・残作業・品質issueを結果に合わせて更新した。


## 122. 条件欠落の確認待ちと全生成応答ログを準備（2026-09-08）

- 利用者の修正・テスト準備と応答全件保存の指示に従い、[EXEC-087](GOAL.md#exec-087-属性推論の条件欠落検出と応答ログ) を実施した。数値仕様を属性へ分解しない応答と、商品種別へ複数条件文を混ぜた応答を確認待ちにし、promptへ別カテゴリの出力例を追加した。期待する属性・値をテスト側で補完せず、カテゴリ固有プリセットも追加しない。
- 単体診断の生成応答本文は成功・HTTPエラー・不正JSONを含めてrepository外の新規0700 directoryへ0600で保存する。HTTP状態・完全性、モデル提案件数、正規化後条件、最終判定も記録する。上限1 MiB超過・読込中断は受信prefixと不完全理由を残す。raw応答をstdout・文書・commitへ出さず、request header・credential・生例外は保存しない。
- 最終欠落検出testを変更前sourceへ適用して7 failed・3 passed、現行10 passed。logger9件と、成功・不正JSONの単体結合fixtureも成功した。最終offline全体は2146 passed・13 skipped・9 deselected、44.53秒。lock、Ruff、format、Markdown、diff checkも成功。
- 固定回帰入力の要求は16,357 bytesで17,000上限内、単体入力は16,316 bytes。prompt・test・runner・loggerのSHA-256と実行コマンドを計画・開発手順へ記録した。今回の実Bonsai再実行は未実施であり、過去の単体不合格の原因特定や実推論品質改善を確認したとは扱わない。全検索・ランキングは保留する。


## 123. 修正後の実Bonsai推論は部分改善・単体不合格（2026-09-08）

- 利用者の「推論品質の改善を確認せよ」に従い、[EXEC-087](GOAL.md#exec-087-属性推論の条件欠落検出と応答ログ) の準備済み単体nodeを1回実行した。同一モデル・固定入力・基準、loopback、認証不要・費用0、retry0・900秒上限を維持し、直前に条件を再掲した。runner・logger・test・prompt・schemaのdigestも一致した。
- 1 failed、exit1、全体43.83秒。要求処理40.590秒、prompt1123・completion145 tokens、HTTP 200、応答1,373 bytes。商品種別と白色requiredは前回falseからtrueへ改善した。容量・食洗機対応・条件3件・検索専用属性2件はfalseのまま。proposal_ready=falseとなり、numeric_condition_unresolvedによる条件欠落時の停止は機能した。
- 保存応答の限定投影から、モデル提案4件・custom0件、正規化後1件・custom0件を確認した。容量の幅350mm以上への誤対応と、入力にない円筒形・縦向きを後処理が除外した。独自属性が妥当に提案された後に消失した事例ではない。前回はraw非保持のため前回の出力原因との比較はできない。
- 応答全文とHTTP metadata、モデル投影、正規化intent、最終判定の5ファイルを `/tmp/amazon-explorer-bonsai-attributes-20260908-02` へ保存。directory0700・各file0600、本文完全受信。本文SHA-256は `64f45ef8e82a7dfff44573efe407d729a7848134e14890466c413de9f0a47ffc`。生応答を文書や標準出力へ転記せず、追加送信なしで原因を確認した。
- server_stopped=true、port18080の独立確認も非listen。今回は検証と結果記録のみでsource変更なし。全検索・ランキング・外部provider送信は保留。同一入力各1回の部分改善を、汎用属性推論の改善や未知商品の順位品質とは扱わない。


## 124. 独自属性を選べなくする生成順序の不整合を修正（2026-09-08）

- 利用者の修正指示に従い、[EXEC-088](GOAL.md#exec-088-独自属性の生成順序を修正) を実施した。生成schemaと要求bodyの再帰ソートにより、customだけattribute_definitionがattribute_keyより先に固定され、prompt例の属性キーから始める順序ではcustom分岐へ入れなかった。
- 生成schemaから最終bodyまで構築時の順序を保持し、数値targetも型・上下限・単位の順へ揃えた。モデル・prompt・受入判定・共有registry・応答ログ方針は変更していない。JSON Schemaとしての意味は変更前後で同じで、application schemaも同じ。生成schemaとbody digestの変更により旧prepared requestは再作成を必要とする。
- 新規順序回帰4 failedから修正後4 passed。llama.cppの実C++ converterとgrammar matcherでも、prompt例と正常な数値・boolean属性fixtureが変更前2件reject、変更後2件accept。モデルロード・server起動・通信のない文法検証であり、実推論成功ではない。
- custom全5型の順序と、再ソートしてbody digestを再計算してもtransport前に拒否する回帰を追加した。最終標準offlineは2156 passed・13 skipped・9 deselected、45.73秒。lock79 packages、Ruff check、format267 files、Markdown検査、git diff --checkも成功した。
- 次回の固定入力1件・Bonsai-8B・loopback1 call・retry0・費用0・最大900秒の再試験を、未使用の `/tmp/amazon-explorer-bonsai-attributes-20260908-03` に応答全文を保存するコマンドとして準備した。今回の実Bonsai再送・全検索・画像・ランキングは未実施。カテゴリ固有推論の意味品質は未確認のまま。


## 125. 実推論で容量・独自属性提案の改善を確認（2026-09-08）

- 利用者の「推論の改善を確認して下さい」を受け、[EXEC-088](GOAL.md#exec-088-独自属性の生成順序を修正) の提示済み単体試験を1回実行した。モデル・入力・prompt・固定受入基準を維持し、修正後の生成schemaを使用。直前に条件を再掲し、model・source・prompt・schema・runner・logger・testのdigest一致を確認した。
- 結果は1 failed、exit1、全体43.25秒。要求処理41.551秒、prompt1123・completion164 tokens、HTTP 200、応答1,449 bytes、1 call・retry0・費用0。商品種別・白色は合格を維持し、容量350ml以上も合格へ改善。モデル提案のcustomは前回0件から2件になった。
- 食洗機対応の定義・原文引用・boolean trueは提案されたが、operator=contains_all・strength=preferredで、equals・requiredを満たさなかった。原文照合で除外され、正規化後は白色・容量の2条件、custom1件。custom_condition_unresolvedによって確認待ちとなり、全体基準は不合格。no_extra_preferences=trueはterms等の固定判定であり、不適切なtyped候補の希望扱いが合格したという意味ではない。
- 完全な応答本文とHTTP metadata、モデル投影、正規化intent、最終判定を `/tmp/amazon-explorer-bonsai-attributes-20260908-03` の5fileへ保存。directory0700・file0600、本文SHA-256 `7ef4720d2a5953b3c159e40f0d13bb548bc33618ff7d74aa88f3481b3a73edbc`。生応答を標準出力・文書へ出さず、保存応答の限定投影で失敗箇所を確認した。
- server_stopped=true、独立照会でport18080非listenも確認。同一入力各1回の部分改善を汎用推論品質・商品rankingの証拠とはしない。今回は実試験と記録のみでsource変更・追加再送・外部provider・画像・全検索・rankingは未実施。結果記録後のMarkdownリンク・見出し・コードフェンス検査とgit diff --checkも成功した。


## 126. 継続授権の下で属性推論を改善し実単体に合格（2026-09-08）

- 利用者の「ユーザの承認無しに、改善とテストを繰り返せ」を受け、[EXEC-089](GOAL.md#exec-089-独自属性の比較方法と条件の強さを修正) を実施。ローカル属性推論の改善・単体試験は追加確認なしで継続し、各回のloopback・モデル・固定入力・1 call・retry0・費用0・900秒上限・privateログ先を事前に通知した。
- custom全型に全operatorを許す生成schemaを型別の制約へ修正した。新規不正組合せ回帰は7 failed・3 passedから10 passed。元のproperties順を維持し、不要な共通integer定義を除去、numericの共通operator分岐を共有して要求17,000 bytes上限を維持した。希望の明示がない条件をrequiredとするprompt指示も追加した。
- 最初の試験04は1 failed、41.49秒、要求39.544秒、prompt1176・completion107、HTTP 200・1,161 bytes。食洗機対応の定義へ容量350ml以上を混ぜたため、原文照合で除外。モデル提案2条件・custom1件から、正規化後1条件・custom0件となった。
- 別カテゴリのライトを使い、青色・点灯時間8時間以上・防水対応を独立した3条件にする例へ変更。prompt例の原文照合・typed proposal回帰でも3条件・custom2件・readyを確認した。条件を補完する処理や診断入力固有のカテゴリプリセットは追加していない。
- 次の試験05は1 passed、43.82秒、要求42.129秒、prompt1155・completion158、HTTP 200・1,431 bytes。モデル提案と正規化後の双方で3条件・custom2件となり、白色required、容量350ml以上required、食洗機対応true・equals・requiredを含む既存9判定が全てtrueだった。受入基準は変更していない。
- 失敗04・成功05それぞれの応答全文と診断5fileを `/tmp/amazon-explorer-bonsai-attributes-20260908-04`・末尾05へ保存し、完全受信・0700/0600を確認した。各1 call・retry0、合計2 calls・費用0。双方server_stopped=true、最終port18080非listenも独立確認した。
- 最初の全体offlineは1 failed・2166 passed。短縮後promptに残る共有辞書不変・value_type順守を、古い英語句で検査していたため、同じ制約の現行表記へassertionを更新した。実推論の成功後にprompt/sourceや意味品質の9判定を変更していない。
- 実llama.cpp文法でも不正boolean operatorの拒否と最終3条件例の受理を確認した。固定ケースの修正後合格であり、未知カテゴリ・実商品の属性充足・ranking品質は未検証。全検索・画像・外部provider・委託frontend・commit・pushは実行していない。
- 最終標準offlineは2167 passed・13 skipped・9 deselected、44.91秒。lock79 packages、Ruff check、format268 files、現行Markdownリンク・見出し・フェンスとgit diff --checkも成功した。


## 127. 別カテゴリ5入力は内容確認で1件成功（2026-09-08）

- 利用者の「他の入力例でも成功するか試せ」に従い、[EXEC-090](GOAL.md#exec-090-別カテゴリ5入力の実bonsai単体検証) を実施。テーブル・リュック・ヘッドホン・モニター・希望と除外付きキーボードの入力と期待条件・意味判定語彙を実送信前に固定した。ローカルテストの継続授権を適用し、全5 calls・費用0・各retry0・900秒上限と保存先を通知した。
- 既存単体runnerへ入力・判定・モデル投影の任意引数を追加し、既定のマグカップ判定を維持した。各例の正常fixture、欠落・値・単位・意味・強さの改変をofflineで確認。tableは丸形を正しく提案しても原文照合で失う既存不具合があり、strict xfailとして残した。合格条件を緩めたり例を除外したりしていない。
- model・prompt・生成schemaを固定した初回実行は5 failed、318.56秒。全HTTP 200・完全受信、各1 call・retry0、合計5 calls・API費用0。モデル提案と正規化後の条件数・custom件数はtable1/0→0/0、backpack3/2→1/0、headphones3/2→3/2、monitor3/2→2/1、keyboard3/2→1/0だった。
- tableはモデルが材質を欠落し、正しいroundもadapterで除外された。backpackは容量の単位を商品名へ誤り、撥水を防水へ置換。monitorは27インチを27.000000 inchへ正規化し、同じ意味の単位表記を原文照合できなかった。keyboardは希望の対応可否を1件以上へ数値化し、除外対象のBluetooth対応をfalseへ反転した。
- headphonesは3条件・custom2件・readyを保持し、応答内容は期待を満たした。ノイズキャンセリングを外部音のキャンセリングと定義した表現が固定regexに含まれず、評価器の偽陰性だった。自動0/5を上書きせず、内容確認1/5と区別して `content-review.json` に追記保存した。測定後に合格語彙を広げてpytestを通したものではない。
- `/tmp/amazon-explorer-bonsai-examples-20260908-01` に基準・manifest・補足判定と、各caseの応答全文・metadata・処理前後の診断5fileを保存。source/test/promptの事前digestが終了後も一致し、各directory0700・file0600を確認。全server停止と最終port18080非listenも確認した。
- 汎用推論品質は未達。モデル・原文照合・評価器それぞれの問題を分離し、新規5例は以後development用として扱う。今回は初回比較だけで追加実推論・prompt修正・外部provider・画像・全検索・ranking・委託frontendは実行していない。
- 最終offlineは2185 passed・13 skipped・14 deselected・1 xfailed、76.83秒。xfailはtableの既知照合不具合。lock79 packages、Ruff check、format270 files、Markdownリンク・見出し・フェンスとgit diff --checkも成功した。


## 128. 別カテゴリ5入力の改善を繰り返し実単体へ合格（2026-09-08）

- 利用者の「試行と改善を繰り返せ」とローカル属性推論の継続授権に従い、[EXEC-091](GOAL.md#exec-091-5入力の失敗箇所を修正し再試験) を実施した。既知5例の条件・値・強さを固定し、各試行前にloopback18080・Bonsai-8B・各1 call・retry0・最大900秒・認証不要・費用0・新規privateログ先を通知した。
- 最初の再現回帰4 failedから、共通形状の「丸い」→round、同値のinch/inches/インチ、意味判定の同義表現と否定拒否を修正した。共通registryはv4とし、カテゴリ専用プリセットは増やしていない。単位alias実装中の℃重複も既存回帰で検出し、未知単位は従来のalias生成へ戻した。モデルへの指示は明示条件の独立抽出と欠落防止を補い、診断5例とは別のカメラの4条件例へ更新した。
- 修正後02は2 passed・3 failed、328.25秒。テーブルとモニターは合格。リュックは全条件を保持したが定義説明の語彙判定、ヘッドホンは時間→hoursの原文照合、キーボードはBluetooth対応false・excludedが不合格。全5例はHTTP 200、各1 call・retry0・server停止だった。失敗を含む応答全文と診断を `/tmp/amazon-explorer-bonsai-examples-20260908-02` へ保存した。
- 追加3回帰のREDからhour/hours/時間の同値照合、撥水の表面湿潤防止という同義説明の受理、水中保護等の誤った意味の拒否を修正した。評価語彙の修正前後を区別し、初回の自動0/5・内容確認1/5と02の2/5を上書きしていない。別の大きさの単位への置換・換算は行わない。
- custom生成のproperties順を属性キー・定義・strength・operator・expected_valueへ変更した。除外指定を値の生成より先に確定させ、型別operator制約を維持した。順序回帰6件のREDから修正し、実llama.cpp converterとmatcherでも最終prompt例を受理した。妥当なfalseやexcludedの表現能力は残し、特定入力の値を後処理で反転しない。17,000 bytes要求上限も維持した。
- 最終設定03は先にキーボード1件が1 passed・68.41秒、続いて残り4件が4 passed・312.54秒。同じ設定で5/5が合格し、モデル提案と正規化後の両方で全条件を保持した。要求処理時間はテーブル53.125秒、リュック66.045秒、ヘッドホン69.573秒、モニター114.240秒、キーボード65.320秒。共通2条件または共通1＋custom2条件、ready・共有registry不変を確認した。
- 全5件の応答全文・metadata・処理前後の診断を `/tmp/amazon-explorer-bonsai-examples-20260908-03` へ保存。事前manifestのsource/prompt/評価器digestが最後まで一致し、全HTTP 200・完全受信・各1 call・retry0・所有server停止、directory0700・file0600を確認した。生成schema SHA-256は `415728a8c74f59373994d18b8e16f65750c90d8a0c6f10c150630f77a89dc2e6`。
- 最終設定を変えず、元のマグカップを既存受入基準で再実行した。1 passed・72.05秒、要求68.387秒、prompt1182・completion169、HTTP 200・1,434 bytes、3条件・custom2件・既存9判定全てtrue。応答全文と診断は `/tmp/amazon-explorer-bonsai-attributes-20260908-06` へ保存し、完全受信・0700/0600とserver停止・port18080非listenを独立確認した。
- この作業では計11 calls・retry0・API費用0。生成応答以外ではモニター実行中にlocalhostのslot稼働状態を1回照会し、処理中であることだけを確認した。失敗を含む全生成応答を保存した。最終設定の既知6例成功であり、独立holdout・未知カテゴリへの精度・実商品rankingの合格ではない。画像・外部provider・全検索・委託frontend・commit・pushは実行していない。
- 最終標準offlineは2195 passed・13 skipped・14 deselected、79.35秒。tableの既知xfailは解消した。lock79 packages、Ruff check、format270 files、現行Markdownリンク・見出し・フェンスとgit diff --checkも成功した。


## 129. 未使用4カテゴリの属性推論は完全合格2件で品質未達（2026-09-09）

- 利用者の「未知カテゴリの精度を確認しろ」に従い、[EXEC-092](GOAL.md#exec-092-未使用4カテゴリの属性推論精度を測定) を実施。既知6入力とprompt例を除き、テント・ミシン・プリンター・顕微鏡を各2件、計8入力・19条件として初回応答を見る前に固定した。検索した既存のコード・テスト・診断にこの4カテゴリは見つからなかったが、モデル学習データへの未収録を意味しない。
- 未commitの新規 `tools/bonsai_unseen_categories.py` と `tests/test_bonsai_unseen_categories.py` に評価基準と既存runnerのlive入口を追加。意味のregex・同義属性名・型・値・単位・上下限・強さ・全条件数・商品種別・readyを固定し、全8入力・19条件の成功を合格基準とした。モデルに採点用の定義・正解を送らず、本番model・prompt・schema・adapterは変更していない。
- 事前の合成評価器テストは初回8 failed・35 passed。正規化で追加される原文由来termsまで禁止していた新規評価器を、原文にないtermsだけの拒否へ修正した。さらに余計な語句の負例を、adapterで除去される前の値ではなく正規化intentへ直接設定するfixtureへ訂正した。最終44 passed・8 deselectedを確認してから基準・判定器を凍結し、実モデルを起動した。
- 継続授権のあるlocalhost Bonsai-8Bへ8 calls・各retry0・各最大900秒、1 MiB応答上限、認証不要・費用0で順次送信した。実行前に対象入力・送信先・制限・保存先を通知した。実測は6 failed・2 passed、384.25秒。全HTTP 200・完全受信、全server停止、最終port18080非listenを確認した。
- 完全合格2/8（25%）、意味判定を含む条件合格11/19（57.9%）、モデル提案段階も11/19。カテゴリ別はテント1/2・4/5条件、ミシン1/2・4/5条件、プリンター0/2・2/5条件、顕微鏡0/2・1/4条件。ready4/8のうち2件は属性の意味定義が不合格だった。通信・形式・readyの成功は意味品質の成功を保証しない。
- テント耐水圧、プリンター給紙枚数・自動両面印刷は属性名・型・値を保持したが、意味定義が測定単位の説明、給紙対象の省略、自動の意味の省略となり事前基準未達。固定regexを含む自動評価であり、独立した人間の採点とは区別する。自動結果を上書きせず補足内容確認を別保存した。
- ミシンは希望条件をrequiredへ、プリンターは除外対象の機能をfalse・excludedへ誤った。顕微鏡1は倍率40倍を幅40mmへ置換し、透過照明を欠落させ、入力にない形状・向き・styleを生成。顕微鏡2は重量2kg以下を2000kg以下とし、入力にない色も追加した。不適切な条件が正規化で除外された後4件はblockingとなった。
- `/tmp/amazon-explorer-bonsai-unseen-20260909-01` に固定criteria・model/source/prompt/評価器manifest、各caseの全応答と診断5file、`assessment.json`、`content-review.json` を新規保存。旧ログを上書きせず、directory0700・file0600、全source/prompt/評価器hashの実行前後不変、EXEC-091最終設定との一致を確認した。
- 結論は、今回未使用だった4カテゴリの8入力では事前品質基準未達。母集団全商品の推定精度や実商品rankingの評価とは扱わない。測定中・測定後の本番修正や再送は行わず、この8例は以後使用済みとして扱う。画像・外部provider・全検索・委託frontend・commit・pushは未実施。
- 最終標準offlineは2239 passed・13 skipped・22 deselected、49.43秒。lock79 packages、Ruff check、format272 files、現行Markdownリンク・見出し・フェンス、git diff --checkも成功した。これらは診断と既存コードの回帰確認であり、実Bonsaiの品質不合格を取り消さない。


## 130. 原文の事実と仕様名推論を分離し未知品質の未達を確認（2026-09-09）

- 利用者の根本修正指示に従い、[EXEC-093](GOAL.md#exec-093-原文の事実と属性推論を分離する) を実施。原文の確定事実を再生成させる責務をbackendへ移し、カテゴリ別の属性辞書は追加していない。Bonsai・1 call・retry0・iGPU境界を維持した。
- source_constraints.pyがSudachi境界から数値・単位・上下限・希望/除外・対応可否と既存共通enumを確定する。明示名だけの場合は固定schema、省略名がある場合は原文とunnamed_quantitiesを渡し、product_name_ja・attribute_names_jaだけを生成する。原文事実との結合・定義構成後にstrict検証を行い、元のHTTP応答provenanceを保持する。request version/digest domainは9.0/v9。
- 原文値の変更・条件欠落・余計な共通属性・不適切な名前・未解析仕様・利用量失敗などを回帰へ追加した。実llama.cpp converterの文字列patternがJSON境界を逃がす不具合も再現し、全分岐で引用符・escape・制御文字を排除した。変換器の正常acceptと不正rejectを確認した。
- 初回の既知8例は7/8。省略仕様名では、指示・field順・名前だけのwire・samplingの変更を比較しても誤りが残った。途中の新規4例の初回は1/4、最終の明示推論対象を使った既知5例も1/5だった。配布元の生成設定による比較も1/5だったため採用しない。各設定と全失敗結果はGOALとprivateログへ残した。
- 最終backendへ同一request bodyの実応答12件をoffline再投入した結果は8/12（元の8件7/8）。この再投入で新しいmodel callはない。不適切な商品名・単位と比較語を仕様名とする応答を最終adapterが拒否する。入力・期待値・judge/checksは変更せず、新wireの診断projectionだけを原文事実の展開へ対応させた。
- 最終設定の未使用2例はコンプレッサー合格、掃除機不合格、1 passed・1 failed、3/4条件、19.36秒。掃除機は数値仕様へ別の機能名を使い確認待ちとなった。ログは /tmp/amazon-explorer-bonsai-name-holdout-20260909-07、再投入・最終source・ログ権限の監査は /tmp/amazon-explorer-bonsai-source-final-20260909-01。未使用2例での成功は1件にとどまり、未知仕様名の品質は未解決。
- 本作業の全生成43 calls・各retry0・credential不要・API費用0、全43応答HTTP200・完全受信を確認。全ログdirectory0700・file0600、旧記録上書きなし。準備失敗・未使用rootは送信0件を記録した。各runのcleanupと最終port18080非listenを確認した。外部provider・画像・全検索・ranking再評価・委託frontend・commit/pushは実施していない。
- 途中のoffline失敗は旧wire fixtureと、広すぎた未解析句拒否の互換問題を修正した。最終offlineは2300 passed・13 skipped・28 deselected、47.49秒。lock79 packages、Ruff check、format278 files成功。Markdown16 files・1542 local links・1132 anchors・2002 headings・216 fence pairs、Python 3.10構文272 files、git diff --checkも成功した。


## 131. 属性名検証と形状詞解析を修正し実推論を再評価（2026-09-09）

- 未commitのEXEC-094。source_constraints.pyの原文名詞句判定へ形状詞を加え、「急速充電」のような属性が拒否される原因を修正した。機能名を数値属性名に流用する応答と、日本語文字を含まない推論名も拒否する。カテゴリ別辞書は追加していない。
- 固定promptへ共通の重量1例だけを追加した。本番経路の既知7例は変更前2/7、変更後3/7。電動ドライバーが改善したが、意味品質は未達。実測合計時間は72.09→93.75秒で速度向上はない。通常回答・JSON・説明・言語・単位・仕様一覧による24診断も別記録し、本番の合格へ混ぜていない。
- 初回の未使用2例は0/2（56.71秒）。ポータブル電源の停止原因を品詞解析へ特定し、修正後は値・単位・希望・2条件を保持した。ただし名前の基準は未達で、開発再試験1 failed（13.90秒）。除湿機も仕様名が基準未達である。評価基準を変更して合格にしていない。
- 新規名前検証7件と形状詞3件のRED/GREENを確認。全体offline2322 passed・13 skipped・30 deselected（50.66秒）。最終実装への同一要求の保存応答9件のoffline再投入は3/9、1件拒否、生成callは0。Ruff check・format281 files、lock79 packages、git diff --check成功。
- localhost Bonsai-8Bの生成は今回計41 calls・各retry0・無認証・API費用0。全41応答HTTP200・完全受信、所有server停止・port18080非listen、0700/0600を確認した。最初のmanifest準備失敗は送信0件として別記録した。
- 保存先は /home/products/bonsai-test-logs/20260909-exec094。/tmpの今回38応答をhash照合してコピーし、残る3応答を直接永続保存した。EXEC-093の/tmpログは現在の環境にはなく、復元・再検証したとは扱わない。新規入力2例も今後はdevelopment扱い。外部provider・画像・全検索・ranking・委託frontend・commit/pushは実施していない。
- 最終文書検査: Markdown16 files・1547 local links・1137 anchors・2010 headings・216 fence pairs、Python 3.10構文274 files成功。最終source hashは最後のliveとoffline再投入時から不変。


## 132. 生成と受信の名称制約を整合し実推論の未達を確認（2026-09-09）

- EXEC-094の継続修正。日本語文字・100文字上限・単位名除外を生成patternにも持たせ、単一文字のUnicode大小文字差を含めて受信側と整合した。カテゴリ別辞書や追加正解例は導入していない。名称を文法へ制約しても意味が正しくなる保証はない。
- 言語制約の20件とUnicode単位の2件のREDを確認し、最終focused101 passed。実llama.cpp grammar84/84、文字列補集合10,300例0不一致。初回の60文法例とUnicode差1件の失敗記録も保持した。
- 概念候補の見直し・仮名からの確定名生成の2方式を各3例で診断し、各0/3のため採用しない。生成契約修正後の本番要求9例は3/9（119.41秒）。最後のUnicode修正前後で9件のrequest metadata/bodyは一致し、追加生成はしていない。全9件readyだが意味は6件不合格。文字制約だけを満たす別機能名の付加もあり、意味品質の改善とは扱わない。
- Q1 dot productのSIMD/genericを合成200例で検査した。初回FFIはCPU初期化不足で無効。初期化後は双方の最大絶対誤差0。model全体の数値精度・推論性能の保証ではなく、runtime/modelは変更していない。
- 継続分15生成応答（診断6・本番要求9）は全HTTP200・完全受信、各1 call・retry0・無認証・API費用0。repository外の /home/products/bonsai-test-logs/20260909-exec094-continuation-01 に全応答・失敗診断・manifest・最終sourceと監査を保存し、全file0600・directory0700、所有server停止とport18080非listenを確認した。
- 最終offline2352 passed・13 skipped・30 deselected（49.24秒）、Ruff check・format281 files・lock79 packages成功。意味品質は未解決で、独立holdout・全検索・ranking監査は未実施。EXEC-094は進行中のままとする。


## 133. 正しい仕様定義を与えたBonsaiの属性選択を検証（2026-09-09）

- [EXEC-095](GOAL.md#exec-095-仕様定義を与えたbonsaiの属性同定を検証する) の検証完了。メーカー資料の要約定義と20合成入力を固定した。正例12件は候補名/単位のみ・定義追加・名称/単位非表示と順序/ID変更の3条件、資料不足4件と曖昧4件は後2条件で測定した。正解ID・採点用keyを要求へ含めず、同じsystem promptと全候補＋unresolvedを許すschemaを使う。
- 通常条件の正例は7/12→11/12、4件改善・悪化0件。既存6カテゴリ4/6→5/6、新規6カテゴリ3/6→6/6。名称/単位非表示と順序/ID変更では7/12。シュレッダーの最大細断枚数と定格細断枚数の取り違えが残った。顕微鏡/シュレッダー2入力は範囲を明確化しており、以前の自由名称生成3/9との直接比較ではない。
- 正解資料なし・複数解釈の計16件は全て誤選択し、未確定へ戻る基準は0/16。全52要求の実llama.cpp grammarでunresolved受理と候補外ID拒否を確認し、104/104成功。通信・schema成功から意味の正しさや保留能力を推定していない。
- 継続授権と今回の実行指示の範囲で、条件を通知してlocalhost Bonsai-8Bへ52 calls、各retry0・最大900秒・応答1 MiB・無認証・API費用0で実行。608.444秒、全52応答HTTP200・完全受信・strict JSON成功。source/model/server/shared libraryのhash不変、所有process停止・最終port18080非listen、全file0600・directory0700を確認した。
- 全要求・応答・失敗・fixture/判定器manifest・source snapshot・対比較と権限監査は /home/products/bonsai-test-logs/20260909-exec095-definition-01 に保存。過去ログを上書きせず、今回の定義をproduction registry/promptへ追加していない。
- 新規tool未実装時のcollection REDを記録し、要求/採点の44テストを追加。既存log回帰込み53 passed。全体offline2396 passed・13 skipped・30 deselected（49.80秒）、Ruff check・format284 files・lock79 packages成功。
- 定義の供給による限定改善は確認したが、RAG試作へ進む事前基準は未達。検索器・source数値抽出・属性登録・商品補完・全検索・ranking・frontend・iGPU実機性能は検証していない。意味品質と保留能力の課題はISSUESとEXEC-094へ残す。

## 134. 未確認の数値属性をアプリケーションで保留（2026-09-09）

- [EXEC-096](GOAL.md#exec-096-属性同定の保留をアプリケーションで強制する) で数量根拠と属性名同定を分離。未記名数量からの推論候補は確認用に残し、blockingとしてquery/画像生成/商品検索へ渡さない。typed proposalとregistryでも再検査し、旧ambiguityの削除や既存registryの注入で解除できない。属性名を明記した再入力は進行できる。profile IDをevidence-gated-v2へ変更した。
- 定義選択でも提案IDと実行IDを分け、原文に明記された属性名・単位が資料へ一意に対応するときだけresolvedにする。意味の言い換え・不足・競合はunresolved、不正応答はinvalid。RAG検索器とfrontendは接続していない。
- behavior RED6件とquery迂回RED1件を再現して修正。新規focused52 passed。旧意味判定のgold/judgeは保持し、保留された正しい候補も従来の実行品質判定では不合格のままとした。
- 保存済み実応答52件をoffline再生し、保留必須16/16、不正応答0。正例36件も保留して自動確定0/36であり、意味推論の改善とは扱わない。source/全要求/全応答/結果を /home/products/bonsai-test-logs/20260909-exec096-replay-01 へprivate保存した。
- 既存Bonsai-8Bの実4要求で、省略2件blocking・明記2件readyを確認。source値も4/4保持。全項目の事前基準は3/4合格で、ポータブル電源の商品名が「電源」になった1件を失敗として保持した。localhost18080、retry0、各最大900秒・1 MiB、無認証・API費用0、114.399秒、全HTTP200/完全受信。source/model/server/library/request hash不変と所有server停止を確認。全応答と凍結probeは /home/products/bonsai-test-logs/20260909-exec096-live-01 に保存した。
- 最終offline2448 passed・13 skipped・30 deselected（48.94秒）。Ruff check/format288 files・lock79 packages・Markdown link・diff check成功。検証結果と監査を /home/products/bonsai-test-logs/20260909-exec096-validation-01 へ保存した。保留契約の変更は完了し、意味推論の自動化と商品名抽出の問題は別課題として残す。


## 135. SudachiPyによる候補検索とBonsai意味評価を分離（2026-09-09）

一次資料集を準備しない方針を受け、[EXEC-097](GOAL.md#exec-097-商品候補から属性を発見して確認後に評価する) の独立したoffline backendを追加した。作業中の利用者提案に合わせ、検索前はSudachiPyと原文compilerで検索query・日本語参考画像promptを作り、検索後に商品フィールドの観測属性とBonsai意味評価を使う。未記名数量は候補が一つでも利用者の具体的選択を必要とし、数値・予算・必須条件はコードが評価する。

新規focused 61 testsが成功。同じ合成商品群で、条件を満たす商品（Bonsai点数0.1）→不明の商品（0.9）→不一致の商品（1.0）の順になり、意味点数が必須条件を覆さないことを確認した。未知の名称/単位、上下限、希望/除外、矛盾、切断本文、別商品引用、欠落/不正応答、未確定での順位禁止、owner/digest/期限/二重実行を検証した。

ログ保存先は `/home/products/bonsai-test-logs/20260909-exec097-validation-01/`。合成要求・応答全文と代表結果をprivateに保持する。全体テスト初回の権限fixture 10 failuresはログrunnerのumask継承によるもので、子pytestだけ通常の0022へ戻して再実行する。既存テストの期待値は変更していない。

検証はfixture/mockとローカルbackendの処理契約に限定される。実Bonsai、Outscraper、画像生成は呼んでおらず、実サービスの順位品質や画像品質を確認したものではない。既存liveフロー、画像承認、履歴DB、API、未納品frontendには未接続。

通常umaskでの全体再実行は2509 passed / 13 skipped / 30 deselected、47.77秒、exit 0。Ruff check/format（294 files）、lock、Markdown、diffも成功した。初回の失敗ログと再実行ログを両方保持した。実装・offline検証の範囲を完了し、実model/画像/取得率の品質評価とlive接続は残作業として区別した。


## 136. 既存CLIP契約へBonsai視覚条件抽出を接続（2026-09-09）

[EXEC-098](GOAL.md#exec-098-bonsaiの視覚条件抽出を候補経路へ接続する) により、candidate経路のBonsaiの役割を意味評価に加えて視覚条件の提案へ広げた。既存VisualConditionDraft/Setと原文照合・最大3条件を再利用し、SudachiPyで組み立てる検索語、原文の数値条件、共通属性のtyped評価を保持した。視覚句と強度を確認計画・画像promptへ含める。

新規21件を含むfocused 94件が成功し、全体offlineは2530 passed / 13 skipped / 30 deselected（84.24秒、exit 0）。合成応答から得た条件2件が既存参考画像1枚・偽画像2枚のrequest descriptorへ渡ること、数量/性能条件・部分引用・捏造・強度改変・OR関係を拒否することを確認した。CLIP未評価は結果にpendingとして残す。

全合成Bonsai要求・応答と代表結果を `/home/products/bonsai-test-logs/20260909-exec098-validation-01/` にprivate保存した。最終focusedのJSONは135 files、すべて0600。実Bonsai/画像生成/CLIPは実行しておらず、抽出の意味精度と画像順位品質は未検証。既存liveフロー、API、未納品frontend、履歴DBには未接続である。


## 137. 新旧検索フローの連続offline検証で未完了区間を確認（2026-09-09）

[EXEC-099](GOAL.md#exec-099-新旧検索フローのoffline連続検証) と `tests/test_candidate_offline_flow.py` を追加し、現行実装を変更せずに検証した。新candidateの明示属性名/未記名数量2ケースは、視覚抽出・Sudachi query・画像要求descriptor・商品取得・属性確認・Bonsai意味/数値ranking・JSON出力まで成功した。視覚評価はpendingで、画像承認/CLIP点数統合/履歴は未接続だった。

JSONからdomain結果への復元はDecimal条件で2件失敗した。初回の2 failed / 1 passedを保存し、出力/readbackと復元を分離した後も、未達の復元2件をstrict xfailとして保持する。既存の別フローは参考1枚→承認→偽画像→固定CLIP embedding→ranking→SQLite履歴と画像の再読込まで成功したが、新candidateの完走には数えない。

focusedは94 passed / 2 xfailed（10.48秒）。全体offlineは2533 passed / 13 skipped / 30 deselected / 2 xfailed（78.44秒）。合成要求・応答・結果のJSON 198 filesを0600で `/home/products/bonsai-test-logs/20260909-exec099-validation-01/` に保存した。外部サービス・実model・CLIP runtime・frontendを使っていない。[接続と復元の未完了箇所](ISSUES.md#candidate経路の画像履歴接続と結果復元) を記録した。


## 138. Candidate結果JSONのDecimal復元を修正（2026-09-09）

[EXEC-100](GOAL.md#exec-100-candidate結果jsonのdecimal復元) でCandidateRankingのJSON入力境界に復元処理を追加した。数量・予算の文字列をDecimalへ戻して共通型の有限値・範囲・精度を検証する。JSON配列のtuple復元も保持し、Python入力の厳格性と既存JSON形式・profile・digestを変更していない。

既存の復元2件のxfailを解除し、RED 2 failed / 3 passedから、同じテストSHA256でGREEN 5 passed（2.55秒）を確認。中間のtuple復元失敗も保存した。数値表記・型・混在条件・不正値など36件を追加し、focusedは143 passed（4.20秒）。全体offlineは2571 passed / 13 skipped / 30 deselected（80.17秒、exit 0）で、xfailは残っていない。

全合成要求・応答・結果、RED/GREEN、実行commandとtest SHA256を `/home/products/bonsai-test-logs/20260909-exec100-validation-01/` に保存した。実provider・実Bonsaiは呼んでいない。結果JSONの往復に限定した修正であり、新candidate経路の画像承認・CLIP・履歴DBの接続は引き続き未完了である。

最終static gate: Ruff check・format（298 files）、offline lock、Markdown links、git diff --checkはすべてexit 0。


## 139. JSON復元修正後の全体offline再検証（2026-09-09）

利用者の再実行指示により、製品コード・テストを変更せず `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short -ra` を再実行した。最終結果は2571 passed / 13 skipped / 30 deselected（59.04秒、exit 0）。新旧フローの5件とJSON復元回帰36件も成功し、対象source/testのSHA256不変を確認した。13件は明示opt-inが必要なCLIP runtimeテスト、30件はlive_api除外である。

初回は証拠保存用に指定したbasetempの親ディレクトリがfixtureのcandidate UIDから置換可能と判定され、ハーネス151件が失敗した（2420 passed）。保存先の権限や安全検査を変更せず、basetemp指定だけを外した標準設定で全体を再実行して成功した。初回のフロー5件・JSON回帰36件も成功していた。

両実行のcommand・結果・JUnit・合成fixtureを `/home/products/bonsai-test-logs/20260909-exec100-retest-115339/` に保存した。Ruff check/formatとoffline lockも成功。実Bonsai・画像生成・実CLIP・外部サービス・委託frontendは未実行で、画像承認・CLIP・履歴DBの新candidateへの接続完了を示すものではない。今回の変更は未commitの検証記録だけである。


## 140. 画像承認・CLIP・履歴DBのoffline接続検証（2026-09-09）

利用者の指示により、新旧candidate連続フロー、段階的画像生成、参考画像承認、永続承認、商品CLIP評価、typed ranking、履歴DB、production searchの既存9テストファイルを実行した。初回53 passed（10.23秒）。既存の通しfixtureでは全商品に同一CLIP embeddingを設定していたため、履歴の画像点数はunknown/nullだった。これを点数保存成功と誤認せず、較正のinsufficient_spanによる正常な保留として確認した。

`tests/test_search_v2_provisional_production_flow.py` と `tests/test_candidate_offline_flow.py` に異なるembeddingのケースを追加し、既存同点ケースも保持した。参考画像1枚で停止→了承後に偽画像→永続single-use承認→商品取得→CLIP固定embedding→ranking→SQLite履歴保存→再オープンを通し、異なる4商品で画像点数1.0 / 0.6 / 0.4 / 0.0の順位と商品ごとの対応が維持されることを独立した期待値で検証した。同点ケースはunknown/nullを保持する。両ケースで参考画像2枚の画素一致と読み取り専用SQLite integrity_check=okを確認した。

関連9 filesの拡張後は55 passed（11.62秒）。承認拒否・期限切れ・差替え・二重使用・owner、CLIP失敗、画像欠落、必須条件優先、履歴削除も含む。標準全体 `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q --tb=short -ra` は2573 passed / 13 skipped / 30 deselected（55.09秒、exit 0）。Ruff check/formatとoffline lockも成功した。

新candidate経路は現在もvisual_evaluation_status=pendingで、画像承認・CLIP点数・履歴DBへ未接続。今回の成功をこの経路全体の完走とは判定しない。CLIPは固定embedding、providerはmock、DBは一時ローカルSQLiteを使用した。実model・外部サービス・委託frontendは未実行。代表通しケースは各Bonsai1・画像2・商品1・CLIP2 batches・履歴detail1・履歴画像2の合成応答を保存した。初回・拡張後・全体のcommand、JUnit、test SHA256、応答、SQLite、監査は `/home/products/bonsai-test-logs/20260909-image-clip-history-115653/`。製品コードは変更せず、テストと検証記録のみ未commitで更新した。


## 141. 新candidate出力の画像・CLIP・履歴接続条件を直接検証（2026-09-09）

利用者が新経路の接続テストを指定したため、旧経路の成功を再利用せず、`run_candidate_flow` で新candidateを原文から実行した。数量属性の明記あり/選択が必要な2入力で、候補取得・属性確認・Bonsai mock/数値rankingの既存assertionは成功した。その出力を後続の既存入口へ直接渡すprivate診断6件はすべて失敗（0.60秒、exit 1）。

画像はCandidatePlanを `generate_provisional_reference_review` に渡した時点でIntentReview契約の不一致となり、mock画像呼出し0。CLIPは `complete_provisional_product_ranking` の最初の検査と同じTypedRankedProductBatch入力契約にCandidateRankingが適合せず失敗した。承認済み画像を捏造して先へ進めず、CLIP評価関数本体・runtimeは未実行。履歴はCandidateRankingを一時SqliteProvisionalHistoryRepository.saveへ渡すとProvisionalHistoryWrite契約の不一致で拒否され、2つのDBとも履歴0件・integrity_check=okだった。

これは未接続区間の入力互換性診断であり、存在しないadapterを経由したE2Eではない。正しい既存APIの拒否動作を製品不具合とは扱わず、新candidate専用の画像承認状態、CLIP評価への変換、履歴投影が必要であることを確認した。全体完走は未達のまま。xfail化や型検証の緩和は行っていない。

診断test・全合成フロー応答・結果・JUnit・command・SHA256・一時DBは `/home/products/bonsai-test-logs/20260909-candidate-connection-120356/` に保存した。初回は診断ログの同名exclusive書込が元の例外を覆ったため、開始/失敗を別名で保存するv2へ修正し、初回ログとsourceも保持した。最終pytest-final.txtとfinal-result.jsonを判定正本とする。repositoryの製品コードとテストは変更しておらず、今回の未commit変更は検証記録だけ。実provider・実CLIP・frontendは未実行で、全体テストの再実行は行っていない。


## 142. 新candidateから画像承認・CLIP・履歴を接続（2026-09-10）

[EXEC-101](GOAL.md#exec-101-candidate経路の画像承認clip履歴接続) でCandidateSearchFlowと専用の画像付き結果/履歴投影を追加した。原文→Bonsai視覚提案/Sudachi query→参考1枚→了承→条件別偽画像→永続single-use承認→商品取得→属性選択→数値/Bonsai/CLIP ranking→SQLite履歴の詳細・一覧・画像再読込を接続した。旧typed型へのキャストや承認結果の捏造は行わない。

数値必須条件の優先を維持し、同じ充足区分内でBonsai意味80%・画像20%を合成する。画像不明なら意味点数のみ。candidate-semantic-clip-v1の履歴品質は未測定nullとし、旧profileの0.875との不正な組合せを拒否する。既存schema5のtable・digestは変更せず、専用DB利用を推奨する。保存だけの失敗は同じpayloadで再試行でき、commit後の応答喪失でも生成/検索/CLIPを繰り返さない。

初回module未実装RED13件、途中のledger順序を仮定したテスト誤り、履歴一覧のnull拒否RED4件を記録。履歴一覧の修正は同じtest hashで17 passedとなり、その後28件へ拡張した。関連100 passed（19.04秒）、全体2601 passed / 13 skipped / 30 deselected（96.27秒）、Ruff check/format・offline lock・Markdown・diff成功。4つの新経路通しケースで履歴各1件・DB integrity_check=ok、参照画像2枚一致、数値優先と画像点数保持を確認した。生成2〜3条件、期限/owner/digest/拒否/同時実行/二重使用/再生成上限/失敗/未選択も検証した。

ログは `/home/products/bonsai-test-logs/20260910-exec101-validation-01/`。全合成応答・結果・履歴画像・一時DB・RED/GREEN/hash/commandを保存した。実provider・実CLIPは未実行、既存live入口・API・委託frontendは未切替。視覚条件なし/画像省略の新履歴接続、途中状態の再起動復旧は今回の範囲外。今回のコード・文書は未commitであり配布済みではない。

## 143. 新candidateの実画像付きテスト入口を準備（2026-09-10）

実画像を含む検証要求に対して、既存live入口が旧IntentReviewを通ることを確認し、CandidateSearchFlow専用の対話runnerを追加した。参考1枚で停止→人間了承後に偽1枚→画像/query了承→商品取得→Bonsai/CLIP→履歴照合の順で、既存HTTP・画像検証・固定CLIP・SQLiteを再利用する。固定合成入力1件、最大2推論/画像2 calls/query1本・24件/poll50回/商品画像24枚/CLIP7batch、retry0、全体900秒。

準備中にSecretStrの境界と確認PNGの改変検出を調整した。改変確認のREDは2 failed / 5 passed、同じtest SHAでGREENは7 passed。HTTP応答のstatus/byte数/hash記録を追加し、認証headerと生本文・生例外を保存しない。実行結果はrepository外private directoryに保存する。現時点では実provider未送信。関連回帰と標準gateの結果・実行承認/実測結果は [EXEC-102](GOAL.md#exec-102-candidate経路の実画像付き実行) に追記する。

準備の最終検証は関連113 passed / 1 deselected、全体offline2608 passed / 13 skipped / 30 deselected。Ruff303 files・lock・Markdown・diffも成功した。実行条件を提示して承認待ちであり、実画像生成や実Bonsai/CLIP/Outscraper成功はまだ確認していない。検証ログは `/home/products/bonsai-test-logs/20260910-exec102-preparation/`。

## 144. 新candidate実テストは視覚条件処理で停止（2026-09-10）

提示条件に対する「開始せよ」の承認後、専用CLIを起動した。初回はBonsai runtime configのport引数欠落でprovider送信前に停止。CLI回帰を追加して修正し、18 passed / 1 deselectedとRuffを確認して同じ承認範囲で続行した。修正後は実Bonsai 1 callがHTTP200・1101 bytesを返したが、visual_conditions段階でexit1となった。Cloudflare/Outscraper/商品画像/CLIPは全て0回、retry0、履歴0件。

保存診断はHTTP status・byte数・hashと停止段階で、生応答は保存していない。このため拒否の詳細分岐は特定できず、モデルの意味的誤りとも断定していない。所有Bonsai process終了とport18080非LISTEN、空の履歴DB integrity_check=okを確認した。証拠は `/home/products/bonsai-test-logs/20260910-exec102-live-01/`。実画像付き完走は未達。次は生本文を残さずに停止分岐を識別できる診断を整備する。[EXEC-102](GOAL.md#exec-102-candidate経路の実画像付き実行)を継続する。

## 145. Candidate準備失敗の固定code診断を追加（2026-09-10）

前回の実テストはBonsai応答後のvisual_conditions停止までしか識別できなかった。固定codeだけを持つstrictなdiagnosticを追加し、外側/内側JSON、終了理由、要確認、条件型・件数、原文/属性束縛、節の範囲、条件の強さ、空条件、HTTP境界、query構築、runner上限を区別してsummary.jsonへ保存するようにした。CandidateSearchによる例外の握り直しでも型付き診断を維持する。成功/保留/拒否判定やpromptは緩和していない。

初回50件のREDは49 failed / 1 passed。実装後は空条件fixtureの原文自体がquery構築不可だったため1件失敗した。画像必須flowのempty_conditionsを検証するfixtureを検索可能な原文へ修正し、要求/query/runner上限と偽装diagnosticの6件を追加した。初回REDと最終test hashが異なる点を記録し、同一hashで全件GREENまたはattestedと表現しない。既存の固定例外文を期待する回帰1件も維持するよう修正し、最終新規56件を含む関連151件が成功した。

応答/例外の任意文字列がdiagnosticに入らず、型付き例外に後から不正なdiagnosticを設定してもunexpectedになることを確認した。実サービス呼出しは0。過去のHTTP200応答本文は未保存のため、前回の詳細な拒否理由を復元したものではない。全体gateの結果は [EXEC-102](GOAL.md#exec-102-candidate経路の実画像付き実行) に追記する。

最終gateは全体offline2665 passed / 13 skipped / 30 deselected（89.17秒）、Ruff305 files、lock、Markdown、diffすべて成功。検証ログは `/home/products/bonsai-test-logs/20260910-exec102-diagnostics/`。診断追加を完了し、実再検証は未実施として残す。

## 146. 実Bonsaiの視覚条件誤選択を診断（2026-09-10）

利用者の「テストを実行し、診断せよ」に基づき、同じ合成入力をローカルBonsaiへ1回送った。HTTP200・1097 bytes、19.965秒、retry0で応答し、新diagnosticはclause_scopeだった。応答はstop/ready、3条件すべてが原文の完全な節で、既存視覚属性とdraft・束縛の検証を通過。全体の一意性検証も通った後の停止であり、入力の3節（商品種別・外観・価格）をすべて視覚条件に選んだことが確認できる。「3000円以下」が数量節除外の検証に違反した。

現行要求schemaのenumは全3節を許可しており、指示文で除外している価格も生成可能だった。追加送信なしの合成再生は、3節選択でclause_scopeを再現し、外観1節のみなら受理。実応答本文の再生ではない。Cloudflare/Outscraper/CLIPは0回、Bonsai終了・port非LISTEN確認済み。根拠は `/home/products/bonsai-test-logs/20260910-exec102-bonsai-diagnostic-01/`。修正対象は非視覚条件を候補へ含める生成側の契約であり、このターンでは本体コード/判定/promptを変更していない。

## 147. 非視覚条件を生成候補から除外（2026-09-10）

実Bonsaiが価格を含む全3節を選んだ問題に対して、既存source facts・Sudachi・registryで生成前の候補集合を作り、schema enumとモデル選択肢、受信検証を同じ集合へ接続した。価格/数量/既知の非視覚条件/OR節を除き、一意な商品名詞句を検索用に確保する。名詞句が複数なら語順から推測せずproduct_scopeで保留する。候補なしは空配列のみ、1件なら最大1件の生成契約とした。元の検索query・価格上限・否定/希望/除外は保持する。

新規18件のREDは16 failed / 2 passed。修正後は同じテストを含む関連169件が成功。別カテゴリ、全角数字、順序、対応可否、候補なし、schemaを無視した旧商品/価格提案、直接条件set経由の迂回拒否、曖昧な名詞句の保留を検証した。

ローカルのllama.cpp Python schema converterとC++ GBNF validatorでも10ケースを確認し、外観1件/空配列の許可、商品/価格/旧3節選択の拒否を確認した。validatorは不適合でもexit0なので出力の判定文を照合した。最初は不適合出力がUTF-8文字の途中で切れたため診断scriptのdecodeが失敗し、bytesのまま保存・ASCII判定文比較へ修正した。またPython converterのenum文法がUnicodeエスケープ表現を要求するため、合成JSONも同じ表現に合わせた。日本語の意味や本体parserは変更していない。本番C++ schema converterやモデル推論・HTTP接続の成功を示す検証ではない。全体gate結果は [EXEC-102](GOAL.md#exec-102-candidate経路の実画像付き実行) に追記する。

最終gate: 全体offline2683 passed / 13 skipped / 30 deselected、62.55秒。Ruff306 files・lock・Markdown・diff成功。REDとGREENの新規test SHA一致を確認した。証拠は `/home/products/bonsai-test-logs/20260910-exec102-visual-scope-fix/`。実API/モデル呼出しは0で、修正後の実推論品質と実画像付きフローは未検証。

## 148. 新candidate実テストは商品評価まで進行（2026-09-10）

利用者の「全体テストを再開しろ」に基づき、EXEC-102と同じ入力・接続先・credential・費用見積り・呼出し上限で専用runnerを再実行した。実Bonsaiは外観1件だけを選択し、従来の価格節誤選択は今回再発しなかった。Cloudflareで参考画像1枚を生成し、利用者の「はい」後に角のある形状の偽画像1枚を生成。両画像/queryの最終了承後にOutscraperへ進み、task1回・poll7回でHTTP 200の73,548 bytesを受信した。

商品評価用BonsaiもHTTP 200・8,191 bytesを返したが、ranking_clip_history / unexpectedで停止した。Bonsai合計2 calls、Cloudflare2 calls、商品画像/CLIP0、retry0。ranking未出力、履歴/履歴画像は0件。意味評価parserとcomplete境界が詳細を固定例外へまとめるため、保存metadataから拒否の正確な分岐は特定できない。応答長だけで打ち切りを推定しない。最後の商品応答からBonsai応答まで451.389秒、全体期限前に終了した。

証拠は `/home/products/bonsai-test-logs/20260910-exec102-live-02/`。生成PNG、HTTP metadata、summary、auditを保存し、生provider本文・credentialは記録していない。履歴DB integrity_check=ok、directory0700・files0600、Bonsai終了とport18080非LISTENを確認。文書リンク・anchor・fence、git diff --check成功。実課金額未照会。全体実完走は未達で、次は商品評価の失敗分岐を保持する診断が必要。実モデルの追加呼出しや再試行は行っていない。

## 149. 商品評価の診断情報が失われる3層を修正（2026-09-10）

「診断せよ」を受けて保存metadataとコードを調べた。意味評価parser、CandidateSearch.rank、CandidateSearchFlow.completeが詳細を固定ValueErrorへ置き換えるため、異なる拒否がsummaryではunexpectedになる。終了理由、商品件数/index、点数、引用field/同一商品/位置/重複/空白を固定codeへ分け、rank・completeを通して保存境界まで保持するよう修正した。画像評価、履歴投影、DB保存の未分類例外も区別する。元の受理条件、順位計算、履歴保存だけの再試行は変更していない。

新規33件は32 failed / 1 passedから同一hashで33 passed。31件が診断欠落のRED、1件のclass import失敗は振る舞いの根拠から除外。後のRuff整形でtest hashが変わっている。関連222件成功、全体offline2716 passed / 13 skipped / 30 deselected（63.47秒）。Ruff307 files・lock・Markdown・diff成功。合成18応答を全件正しく分類し、生の合成応答と検証ログを `/home/products/bonsai-test-logs/20260910-exec102-semantic-diagnostics/` に保存した。

今回は実provider・モデル呼出し0。前回live-02の応答本文は保存されておらず、診断改善によって過去の失敗理由を復元できたわけではない。8,191 bytesを打ち切りと断定せず、実停止の詳細は次回の診断付き実行で確認する必要がある。

## 150. 実商品評価の引用field束縛失敗を特定（2026-09-10）

利用者の「テストを再開せよ」によりEXEC-102と同じ条件でlive-03を実行し、参考画像と偽画像をそれぞれ提示・了承後に商品検索へ進んだ。Bonsai視覚抽出と画像2枚生成は成功、Outscraper task1回・poll6回でHTTP200・74,445 bytesを受信。商品評価用BonsaiはHTTP200・8,543 bytesで応答したが、追加した診断がsemantic_field_bindingを特定した。

意味評価parserの外側/内側JSON、stop終了、商品評価件数の検証を通過後、引用field_idの型または既存fieldへの所属で拒否された。保存診断は非文字列と存在しないIDを区別しない。生成schemaがfield_idを任意のstringとして許しており、受信契約の実在ID集合へ束縛していないことも確認した。次は引用を実在する同一商品のfieldへ制約する修正が必要。前回live-02の原因まで同じだったとは推定しない。

Bonsai計2 calls、Cloudflare2 calls、商品画像/CLIP0、retry0。ranking未出力、履歴/履歴画像0件。最後の商品応答からBonsai応答まで531.973秒、全体期限前に終了。証拠は `/home/products/bonsai-test-logs/20260910-exec102-live-03/`。DB integrity_check=ok、private権限、Bonsai終了・port18080非LISTENを確認し、文書リンク・anchor・fenceとgit diff --checkも成功した。実課金額は未照会。今回はコードを変更せず、追加live再試行も行っていない。

## 151. 引用の生成候補を同一商品の本文へ限定（2026-09-10）

live-03のsemantic_field_bindingに対し、意味評価要求のschemaを商品index別の分岐へ修正した。引用field_idは同じ商品の実在IDだけを固定値として生成でき、start/endの上限はfieldのUnicode文字数に束縛する。点数を返す分岐は引用1〜4件、保留の分岐はnullと空引用とし、空/空白本文しかない商品は保留のみ。prompt、受信parser、順位計算、結果JSONと履歴形式は維持した。

新規18件は同一test SHAで12 failed / 6 passedから18 passed。関連184件、全体offline2734 passed / 13 skipped / 30 deselected（65.56秒）。Ruff308 files、offline lock、Markdown、diff成功。Python schema converter＋C++ GBNF validatorの14ケースも全件期待どおりで、正常引用、架空/他商品/null ID、文字位置、点数と引用の対応、空batch/空本文を確認した。これは実serverのschema変換や実モデル生成の測定ではない。

証拠は `/home/products/bonsai-test-logs/20260910-exec102-semantic-schema-fix/`。合成応答・schema・文法・判定出力、変更前source、RED/GREENのcommand/exit/hash、最終hashと全体logを保存した。実API/model call0。商品網羅の一意性、引用のstart<endと重複は既存parserで検証し、意味的な引用品質はschemaだけでは保証しない。修正後の実検索E2Eは未実施。

## 152. 引用生成修正後の実再検証は全体期限で停止（2026-09-10）

「実Bonsai・実検索の再検証」に基づき、同じ入力・接続先・credential・費用見積り・件数上限でlive-04を開始した。実Bonsai視覚抽出と参考画像生成に成功し、参考了承後に偽画像を生成。最終画像/queryの了承後、Outscraper task1回・poll8回でHTTP200・74,080 bytesを受信した。

商品評価用Bonsaiは応答完了前に全体900秒の期限となり、ranking_clip_history / transportで停止した。2回目のHTTP応答metadataはなく、引用生成修正の成否は未確認。post_json中の期限例外がtransportへ集約されるため、summaryだけでは期限を識別できない。停止時刻03:49:24 JSTと起動直後の期限設定を照合した。最後の商品応答から停止までは510.381秒で、純粋な推論時間ではない。

Bonsai呼出し開始2回（応答完了1回）、Cloudflare2回、商品画像/CLIP0、retry0。ranking未出力、履歴/履歴画像0件。DB integrity_check=ok、private権限、Bonsai終了・port18080非LISTENを確認。証拠は `/home/products/bonsai-test-logs/20260910-exec102-live-04/`。文書リンク・anchor・fence、git diff --check成功。実課金額未照会。画像確認と商品検索の待ち時間も全体期限へ算入されるため、次は段階別時間と実行期限の設計を見直す必要がある。今回は期限延長や再試行を行っていない。

## 153. Bonsai商品評価の入出力を圧縮し時間計測を追加（2026-09-10）

実行時間への指摘に対応し、商品順・field序数を使うcompact wireを生成既定にした。繰り返すJSON keyやID文字列を省き、本文と条件は保持する。受信側で元の商品index・field_idへ復元し、既存の点数/引用/位置検証を行う。schemaは商品順に1件ずつ生成させる。旧応答読込、ranking/履歴形式、Bonsai/provider、実行期限は維持した。

24商品・各4引用の合成例を既存GGUF tokenizerで比較し、入力user contentは4,703→2,593 tokens、出力contentは2,260→908 tokens。同じ結果へ復元でき、本文や商品数は減らしていない。system/chat template込みの総prompt量や実生成時間を測ったものではない。実runnerには各callのwall時間と、取得・検証できたprompt/生成tokensと処理時間を保存する機能を追加した。未取得metricsはnull、本文/例外文字列は非保存。

新規15件は5 failed / 10 passedから同一hashで成功。関連255件、全体offline2749 passed / 13 skipped / 30 deselected（65.28秒）。Ruff310 files、lock、Markdown、diff成功。ローカルPython converter＋C++ GBNF validatorの7ケースも成功。証拠は `/home/products/bonsai-test-logs/20260910-exec102-semantic-compact/`。実API/モデル推論0で、実時間短縮とiGPU性能は未確認。次は新wireの実Bonsai計測で効果を確認する。

## 154. 実Bonsaiの時間比較でcompactの意味評価不良を確認（2026-09-10）

外部APIを使わず、同じ合成24商品・96本文をlocalhost Bonsaiへ旧形式→compactの順に各1回送信した。各回serverを再起動し、CPU/Core i5-13600KF、同じGGUF、context8192、parallel1、各900秒、retry0で測定。両回cached_tokens=0だった。実行コマンドは `uv run --frozen --offline --no-sync python /home/products/bonsai-test-logs/20260910-exec102-local-timing-01/benchmark.py`。

| 測定項目 | 旧形式 | compact |
|---|---:|---:|
| HTTP要求から応答完了 | 804.309秒 | 205.518秒 |
| prompt処理 | 163.678秒 / 4,857 tokens | 85.849秒 / 2,800 tokens |
| 生成処理 | 640.607秒 / 3,335 tokens | 119.652秒 / 1,131 tokens |
| 終了理由 | length | stop |
| 既存parser | semantic_finish_reasonで拒否 | 24商品・96引用を復元 |

旧形式は総8,192 tokensでcontext上限へ達し、JSONが途中で切れた。compactは応答が598.792秒早く、構造検証を通過したが、24商品すべて0点だった。各商品で同じ1本文の先頭1〜4文字を4件引用し、形状条件の根拠を含んでいない。引用96件に対し参照本文は24件。旧未完応答にある0.95の21件は部分観測に過ぎず、受理済み評価ではない。比較は正常完了同士ではなく、意味評価品質を維持した高速化は確認できていない。

上記directoryへ凍結要求、全合成応答、復元結果、metrics、script/source/model hash、auditとcontent-validationを保存。測定scriptのexit0と意味品質の不合格を分けて記録した。外部API、credential、課金は0。製品コード変更なし、所有Bonsai終了・port18080非LISTEN、directory0700/files0600、script/source hash不変を確認した。各形式1回の合成例であり、実商品ranking・全検索E2E・iGPU速度は未確認。全体pytestは製品コードが変わっていないため再実行していない。文書リンク・anchor・fenceとgit diff --checkは成功した。文書更新は未commit。

## 155. BonsaiをCLIP用の視覚条件提案だけへ限定（2026-09-10）

利用者の明示指示でcandidate経路の商品採点Bonsaiと商品本文の追加属性推論フックを削除した。Bonsaiを呼ぶのは検索開始時の視覚条件提案だけ。商品条件はSudachiPy・既存抽出規則とtyped evaluatorで判定し、既存ranking._title_scoreのタイトル単語一致率を採点へ接続した。画像ありは単語一致80%＋CLIP20%、画像不明は単語一致のみ。必須状態、必須充足率、希望充足率を総合点より優先する。

candidate_search、candidate_flow、candidate_completion、実runnerを変更。実runnerのBonsai上限も2から1 callへ変更し、商品評価用の要求・応答を生成しなくした。新結果はcandidate-confirmed-lexical-v2、最終採点はcandidate-lexical-clip-v2。旧中間JSONを新方式の結果として受理せず、表示履歴は旧profile/点数のまま読める。schema5 SQLiteのtable移行・旧履歴の再採点は行っていない。旧意味評価の単体診断コードは検索フローから切り離して残した。

新規12件は10 failed / 2 passedから同一test SHAで12 passed。関連309件、最終全体offlineは2755 passed / 13 skipped / 30 deselected（63.41秒）。初回全体の旧結合8件の失敗は、廃止した商品採点fixtureの参照が原因。旧応答parserの18ケースを保持し、旧意味処理・属性推論を呼ばずにCLIP fixture・履歴へ到達する結合テストへ置換した。Ruff check/format311 files、offline lock、文書リンク・anchor・fence、git diff --check成功。

証拠は `/home/products/bonsai-test-logs/20260910-exec102-visual-only/`。変更前source、RED/GREEN/関連/初回全体/最終全体logとcommand・exit・hashを保存。実Bonsai/外部API/credential/課金0。新方式の実商品順位品質と実フロー所要時間は未検証。AGENTS、設計・要件・DB・目標フロー・開発規約を同期した。旧legacy検索と委託frontendは変更しておらず、今回の変更は未commit。

## 156. 確認した検索語候補だけを検索へ反映（2026-09-10）

利用者の「候補を確認して反映」に合わせ、Bonsaiの用途をCLIP用の視覚条件提案と検索語の言い換え・英訳候補作成に限定した。商品本文の属性推論・採点には使わない。候補要求は原文とSudachiの商品句を受け、各言語最大3件・各64文字のstrict応答を検証する。失敗時は元queryを維持し、再試行しない。実runnerは画像生成前に最大2 callsを使い、元query・候補から利用者が選んだ1 queryだけを検索へ渡す。取得上限24件を維持する。

元の条件、画像prompt、採点用intentは保持する。owner・状態・計画digestを確認して選択を受け、画像生成後の変更を拒否する。保存計画のquery plan digestを保持したまま実要求の語句・言語だけが異なる2ケースも再現し、選択queryから再構成したOutscraper要求との完全一致検証で修正した。旧表示履歴のDB移行や再採点は不要。

新規テストは24件が24 failedから成功、13件が12 failed / 1 passedから成功、要求一致の2件が2 failedから成功し、それぞれRED/GREENのtest hashを保持した。関連356件成功。初回全体2792件成功後に要求一致の2件を追加し、最終の `uv run --frozen --offline --no-sync pytest -m 'not live_api'` は2794 passed / 13 skipped / 30 deselected（62.48秒）。候補選択から画像承認・検索・CLIP・履歴再読込までをfixtureで確認した。Ruff check/format315 files、offline lock、Markdown links・anchor・fence、git diff --checkも成功。

証拠は `/home/products/bonsai-test-logs/20260910-exec102-query-terms/`。合成要求・応答、変更前source、RED/GREEN・関連・全体ログ、command・exit・hashを保存した。実Bonsai/外部API/credential/課金0で、候補の同義性・英訳品質、実商品順位品質、実時間は未検証。旧legacy検索と委託frontendは変更せず、変更は未commit。

## 157. 確認付き検索語候補フローをオフラインで再検証（2026-09-10）

利用者の指示で全体offlineテストを再実行した。最終結果は2794 passed / 13 skipped / 30 deselected（63.01秒）。検索語候補24件、候補選択13件、要求との整合性2件、単語一致採点12件、画像承認・CLIP・履歴接続29件を含む。原語・日本語候補・英訳の各選択が1 query/24件の要求へ反映されること、元条件と採点用intentの保持、Bonsai呼出しが画像生成前の2用途だけであること、不正選択と古い承認の拒否をfixtureで確認した。

初回はテスト一時directoryをログ保管先の配下へ配置したため、既存の保護パス検証などで151件失敗した。一時directoryの親をcandidate UIDから置換可能として拒否していた。製品コード・テストを変えず、配置を `/tmp` 配下へ戻すと全件成功した。初回失敗ログも保持し、両実行でPython source/test/toolのhash不変を確認した。

実行は `uv run --frozen --offline --no-sync pytest -m 'not live_api' -vv -rA` に新規basetempとJUnit出力先を指定したもの。完全なargv、初回/最終ログ、JUnit、hash、検索語候補の合成要求・応答を `/home/products/bonsai-test-logs/offline-query-validation-20260910-050346/` に保存した。実Bonsai、外部API、実画像生成は実行していない。実CLIP runtimeのopt-inテストもskipしており、今回の接続成功はfixtureによる処理確認である。実モデルの候補品質・実順位品質・実フロー所要時間は未検証。文書更新は未commit。


## 158. 実Bonsaiの2用途の推論品質は基準未達（2026-09-10）

利用者の実品質確認指示を受け、現行prompt/parserを変更せず合成6入力を各2用途へ送信した。127.0.0.1:18080、既存Bonsai-8B/GGUFとllama-server、context8192、1 worker、各例cold起動後に視覚→語句、最大12 calls・各例900秒・retry0。継続指示に基づき、接続先・入力種別・上限・保存・認証不要・費用0を通知して実行した。検索・画像生成・CLIP・履歴は実行していない。

6入力・意味判定基準・12要求・source/server/model/libraryのhashを事前固定し、合成6応答による採点・query要求一致のpreflightを実施した。実応答は12/12がHTTP200・stop。視覚parser受理3/6、視覚意味合格2/6、語句parser受理6/6、語句意味合格1/6、両用途合格0/6で、事前の各6/6基準は未達だった。

| 商品 | 視覚意味 | 語句意味 | 主な問題 |
|---|---|---|---|
| 花瓶 | 合格 | 不合格 | 正しいvaseにpot/bowl等の別種・上位概念が混在 |
| 工具箱 | 不合格 | 不合格 | 形状をappearance.styleへ対応付け、検索語は箱/box等へ一般化 |
| 名刺入れ | 不合格 | 不合格 | 希望をrequiredへ変更し拒否。名刺を刺す/Punching a name tagは商品名でない |
| じょうろ | 合格 | 不合格 | きょうろ/Jouloは正しい同義語・英訳でない |
| ランチボックス | 不合格 | 合格 | 除外をrequiredへ変更し拒否。Lunch boxは妥当、重複は既存parserが除去 |
| 掛け時計 | 不合格 | 不合格 | 視覚条件なしでもneeds_clarification。時計/Clockは商品種別が広い |

名刺入れは推論前のSudachi処理で名刺へ変わることをpreflightで記録しており、語句失敗をモデル単独の問題とは断定しない。希望・除外の誤りはcondition_strengthで停止できた一方、誤った語句候補と工具箱の属性対応は構造検証を通過した。視覚拒否後の3例の語句呼出しは独立診断であり、現行フローが続行できたという意味ではない。語句候補は確認前に自動採用されない設計を維持している。

各HTTP応答までの時間は視覚8.943〜11.810秒（中央値10.127秒）、語句8.213〜10.002秒（中央値8.652秒）。2用途合計は各17.156〜21.812秒、12 calls合計115.096秒。server起動時間を含まず、旧商品採点とは入力・役割が異なるため同等品質の高速化比較とはしない。iGPU性能・未知商品一般の精度を示す測定でもない。

証拠は `/home/products/bonsai-test-logs/20260910-query-visual-quality-01/`。実行は `uv run --frozen --offline --no-sync python /home/products/bonsai-test-logs/20260910-query-visual-quality-01/probe.py run`。全合成要求・応答・復元結果・metrics・意味判定・凍結hashを保存した。script exit0は測定完了であり品質合格ではない。所有serverの停止、port18080非LISTEN、hash不変、0700/0600を確認。製品code・prompt/parser・テストは変更せず、全体pytestの再実行は行っていない。実外部API・credential・課金0。文書更新は未commit。


## 159. 元語・言い換えごとに英訳を1つ対応付け（2026-09-10）

利用者の指示に従い、語句候補を独立した日本語/英語の2配列から、original_enと最大3件のsynonyms（ja/enの対）へ変更した。各英訳は1文字列または明示保留のnull。同じ日本語へ異なる英訳を付ける応答を拒否し、同じ対だけを重複除去する。元語・各言い換えの対応関係を専用runnerのquery_terms確認情報へ渡す。日本語最大4本＋英訳最大4本から、重複を除いて1本だけ選択する。最大8本の最後のindex7も選択でき、検索上限24件を維持する。

query expansionはbonsai-query-terms-v2として旧v1中間計画を拒否する。検索候補の失敗時は元queryを維持し、原文条件・画像prompt・ランキング用intentへ候補を流用しない。表示履歴DBは変更しない。元の検索語の抽出・視覚条件抽出は変更しておらず、前回測定の意味品質不良や商品名欠落を解決したという主張ではない。

新規10件は5 failed / 5 passedから同一test hashで成功した。旧リスト拒否、1語句1訳、対応保持、null保留、8本目の選択と確認情報を検証。関連69件成功、全体offlineは2804 passed / 13 skipped / 30 deselected（64.86秒）。Ruff check/format316 files、offline lock、Markdown links・anchor・fence、git diff --checkも成功。全体コマンドは `uv run --frozen --offline --no-sync pytest -m 'not live_api'`。

証拠は `/home/products/bonsai-test-logs/20260910-query-translation-pairs/`。変更前source、新規テストのRED/GREEN・関連・全体log、command/exit/hash、合成要求・応答を保存した。実Bonsai・外部API・課金0。新形式での実推論品質・時間は未測定。委託frontendは変更せず、変更は未commit。


## 160. 日本語接尾辞の欠落と語形の変形を修正（2026-09-10）

利用者の「接尾辞を除外するな」に従い、search_v2の共通tokenizerで接尾辞を保持した。直前の語と文字位置が連続する場合は元の表記で結合し、語を組み立てた後で重複を除く。名刺入れの最終Outscraper queryとBonsaiへ渡すproduct_phraseはともに名刺入れとなる。子供用、sony製、さん等にも共通規則として適用する。空白・助詞・句読点を越えて結合せず、結合対象がない接尾辞自体も残す。

最初の実装では辞書形に接尾辞を付けたため、軽さ→軽いさ、使いやすさ→使うやすさ等の変形を追加診断で発見した。7例のREDを固定し、接尾辞が付く語はsource上の連続spanから組み立てるよう修正した。接尾辞のない内容語の正規化、英語tokenizer、全形態素のsource解析は維持した。旧Sony製fixtureは接尾辞の保持という仕様変更に合わせ、sony製を期待するよう更新した。

新規9件は9 failedから成功、追加7件は7 failedから成功し、それぞれtest hash不変を確認。初回関連138件・全体2813件成功後、追加修正を含む関連145件が成功。最終の `uv run --frozen --offline --no-sync pytest -m 'not live_api'` は2820 passed / 13 skipped / 30 deselected（64.42秒）。Ruff check/format318 files、offline lock、Markdown links・anchor・fence、git diff --checkも成功した。

証拠は `/home/products/bonsai-test-logs/20260910-suffix-retention/`。変更前source、両RED/GREEN・全体log、command/exit/test hash、最終hash、query投影と合成要求・応答を保存した。既存表示履歴を再採点せず、旧legacy実装・委託frontendは変更していない。実Bonsai・外部API・課金0。商品句の欠落は修正したが、Bonsaiの視覚条件/英訳の意味品質改善は未測定。変更は未commit。


## 161. LFM2.5-1.2B-JPを実測し速度と品質を比較（2026-09-10）

利用者の試用指示で公式LiquidAI/LFM2.5-1.2B-JP-GGUFのQ6_Kを取得した。revision170ae1cecf0e74b0b25bd704047160fba9f613c6、962,843,584 bytes、LFS SHA-256との一致を確認。既存Bonsai-8Bは1,158,654,496 bytes。製品のprovider・prompt・parser・設定を変えず、接尾辞修正と1語句1英訳を反映した観測済み6例を使った。

初回24 callsはmodel識別子以外の要求を一致させた。Bonsaiは12/12がJSONだが、LFMは全12応答が自然文でparser拒否。既存llama.cppのLFM2.5 specialized経路ではjson_schemaが生成制約に反映されないことを確認した。top-level json_schemaへの変更は12要求すべてHTTP400で、既存transportはエラー本文を破棄した。別の合成1要求でエラー本文を取得し、sampler初期化失敗と特定した。最後に--no-jinjaを指定すると、初回LFMとbyte一致する12要求でJSON生成が成功した。所有serverは全て停止し、port18080非LISTENとsource/model/server/library/request hash不変を確認した。

| 構成 | 視覚parser受理 / 意味合格 | 語句parser受理 / 意味合格 | 2用途合計中央値 | ピークserver RSS |
|---|---|---|---|---|
| Bonsai-8B・既存設定 | 3/6 / 2/6 | 6/6 / 1/6 | 23.260秒 | 2.410GiB |
| LFM JP Q6_K・--no-jinja | 1/6 / 1/6 | 0/6 / 0/6 | 10.881秒 | 1.113GiB |

両用途合格は双方0/6。LFMの最終12応答はJSON構文上は全て正常だが、不要保留、希望/除外のrequired化、属性keyの誤対応が残った。語句では原語英訳へ価格・外観を混入し、名刺入れをNameplate、じょうろをJarへ変え、jaへ英語を返した。Bonsaiでも名刺入れは欠落せず入力されるがNameplate insertとなった。nullでの英訳保留は双方0件。既存の意味検証・人間確認を緩めず、今回のLFMを製品へ採用していない。

環境はWSL2/Core i5-13600KF/CPU、context8192、1 worker、温度0、各例cold起動後に視覚→語句。file cacheはflushしていない。Bonsaiの2用途合計20.759〜27.071秒、LFM7.647〜11.581秒。HTTP待ち時間でserver起動は除外し、VmHWMはserver自身を停止直前に読む。出力長と品質が違うため、同等品質の高速化とは扱わない。iGPU、電力、未知入力一般、実検索・画像生成・CLIP・履歴・委託UIは未検証。

証拠は `/home/products/bonsai-test-logs/20260910-lfm-jp-comparison-01/`。probe.py/probe-direct.py/probe-legacy.pyのprepare/runをuv run --frozen --offline --no-sync pythonで実行し、全argv・exit・hashを保存。診断合計49 POST、HTTP200の実推論36応答とHTTP400の拒否13件。HTTP200本文は全保存した。直接Schema指定の12件は本文破棄という記録上の制約があり、追加1件のみエラー本文を保存した。認証・外部推論・API課金0、公開モデルとLICENSEだけを外部取得。初回合成preflightはready+空配列を返すparserのNoneを診断側が誤判定して失敗し、probeだけ修正して再固定した。製品code変更がないため全体pytestは再実行せず、Markdown検査16 filesとgit diff --checkは成功。文書・診断は未commit。


## 162. 辞書による候補選択と構文解析を実装し保留を検証（2026-09-10）

利用者の「曖昧な語義の選択や複雑な文の解釈を自動化したい」「CLIP用の視覚条件抽出はbonsaiのまま」「進めろ」に従い、EXEC-103を追加した。検索用語句生成を専用runnerのBonsaiから外し、任意のJMdict/WordNet・GiNZA・multilingual-e5-small ONNX経路を接続した。元語/言い換え各1英訳、候補確認、1 query/24件、原文条件、単語一致/CLIPの採点を維持する。旧Bonsai語句adapterは互換診断用で、自動fallbackしない。

語義表記制限、読みと別名の区別、未知/曖昧な語義の保留、範囲の原文binding、未消費条件の保留、資材hash変更拒否を検証した。ONNXのtoken_type_ids入力欠落、GiNZAの未確定depによる連続名詞の欠落、提案変換失敗後に選択IDが残る問題を修正した。初期fixtureの誤ったfield参照と、旧Bonsai2 calls期待による全体2失敗は、製品の意味品質問題と分けてログへ保存した。

実CPU資材＋fixture providerの接続は3 passed。実辞書/構文解析/encoder→模擬Bonsai視覚条件→模擬参考/偽画像の確認→辞書英訳mug選択→模擬候補取得/CLIP→一時SQLite履歴・画像再読込が成功した。実APIや実画像のE2Eではない。

事前固定17合成入力の語義診断は8件選択/8件正答、9件保留。名刺入れ・花瓶・工具箱・じょうろ・ランチボックス・掛け時計の候補は妥当だったが、マウス/ドライバーの4文脈は全て保留し、意味解決の品質合格は未達。構文の商品句受理16/17は、複雑な修飾関係の理解を保証しない。ORや取り付け先の未解決内容はquery作成で止める。暫定cosine0.75/次点差0.04を下げて通過させていない。

診断processの初期ロード1.922秒、17例中央値0.024秒、peak RSS926.1MiB。例ごとの時間は構文/投影/直接scoreと提案scoreを含む診断値であり、Bonsaiとの同等品質比較やiGPU性能ではない。既知例はdevelopmentとして保持し、EXEC-103の残作業は語義モデル/定義表現の品質向上と独立評価。

公開配布の取得以外の外部通信、credential、推論API料金0。資材とライセンスは `/home/products/models/search-lexical-v1/ready/`、全合成応答・失敗/成功log・semantic-review.json・auditは `/home/products/bonsai-test-logs/20260910-lexical-rag-01/`。通常runtimeは資材を取得せず、署名ではなく運用者が準備したmanifestとのhash一致を確認する。旧履歴DB、ランキング、委託frontendは変更していない。


最終全体offlineは2851 passed / 16 skipped / 30 deselected（59.57秒）。追加の実ローカル資材テストは3 passed（3.09秒）。Ruff check/format（332 files）、offline lock（114 packages）、Markdownリンク、git diff --checkも成功。全体ログはfull-offline-03.log、資材接続ログはlocal-integration-final.log。初期RED/GREENはログを保持したが一部の事前test hashは未固定であり、最終hashを過去のphase証拠として扱わない。optional-failure-red/green.jsonの対では同一test hashとargv/exitを固定した。AI attestation・commit・pushは実施していない。


## 163. 日本語定義と小型モデル、Bonsaiの語義確認を接続（2026-09-10）

利用者の提案採用指示に従い、WordNetの日本語定義・用例とjapanese-reranker-xsmall-v2を接続した。辞書取り込みで複数行の英語定義が最後の行だけになる問題も修正した。新しい辞書DB v2とmanifest v2を追加し、旧資材・履歴は保持する。モデルは公式固定revision de99fd2f16c7b5df1df1bcc1d9ad2c16d88ce93aの量子化ONNX、37,367,189 bytes、SHA-256は34d4657df53c875f970dbf87e584a21d59e6cfcd9368f9828d69a09ed152168f。通常runtimeでは資材を取得しない。

小型モデルで原文と定義を比較し、score0.80・次点差0.20の暫定基準で選択する。文脈のない多義語と未知語は保留し、曖昧な文脈付き語義だけBonsaiへ上位2候補の既存ID/nullを選ばせる。小型モデル最上位と不一致なら保留する。Bonsaiは英訳・言い換えを自由生成せず、確定語義の辞書表記を使う。CLIP抽出Bonsaiを維持し、専用runnerは語義確認を含め最大2 calls。元語/言い換え各1英訳、候補の人間確認、1 query/24件、条件・順位計算を維持した。

実小型モデルは元のマウス/ドライバー4文脈すべてで正解語義を最上位にしたが、絶対scoreが基準未満のため全件Bonsaiの確認を必要とした。実Bonsaiの最初の8 POSTでは2件採用・2件保留で、曖昧/候補外の2例に誤った採用があった。自由引用を原文の参照indexへ変更し、上位2候補との一致確認を加えた最終8 POSTでは元4例と否定2例が全て正答した。原文参照は入力との対応を保証するだけで、意味の正しさは保証しない。

最終development12例は正答7件・誤答1件・保留4件。「小型のドライバー」は不一致で保留したが、「海底で育てるドライバー」は語義選択単体ではゴルフ用と誤判定した。この例は実ローカル構文解析を含む候補準備では未解釈の条件関係として停止し、語句選択を呼ばないことを確認した。未知入力全般の品質は未達としてEXEC-103を継続する。観測後の例を独立holdoutと扱わず、閾値を下げて通過させていない。

語義確認BonsaiのHTTP時間中央値8.835秒・最大12.740秒。CLIP抽出とserver起動を除く追加時間であり、検索全体の高速化やiGPU性能の証拠ではない。実ローカル資材テストは2 passed（3.00秒）。保存済み8応答を使うoffline再生で12例の最終結果を完全再現し、HTTP呼出しは0回だった。fixture接続では視覚/語義の各1回、画像承認・検索候補選択・CLIP・SQLite履歴を確認した。実検索・画像生成・委託frontendは未実行。

全合成要求/応答、RED/GREENのargv・exit・事前test hash、source/model hash、再生と品質判定は `/home/products/bonsai-test-logs/20260910-lexical-context-02/` に保存した。初期dictionary GREENの旧fixture列不足、診断transport引数不一致による送信前拒否（実POST0）、初回全体検査の151失敗も保持する。初回全体失敗は指定basetempの祖先pathが既存の権限検査に抵触したためだった。標準保存先への再実行でも、ログ保存用のumask077をpytestへ継承したため、mode0755/0555を前提とする既存fixture10件が失敗した。ログは0600のまま、pytest子processだけ標準umask022・標準保存先で再実行した。製品code・権限検査・既存directoryの権限は変更していない。

実Bonsaiはlocalhost18080、合計16 POST・retry0・各実行最大900秒、認証不要・課金0。所有serverの停止とhash不変を確認。公開モデル取得以外の外部送信・推論API・credential利用はない。AI attestation・commit・pushは行っていない。


最終の通常offline検査は2872 passed / 18 skipped / 30 deselected（59.92秒）。`uv run --frozen --offline --no-sync pytest -m 'not live_api'` を実行した。Ruff check/format（339 files）、offline lock（114 packages）、Markdownリンク/anchor/fence、git diff --checkも成功。記録はfull-offline-standard.json/logと各gate log。


## 164. 別語の未使用19入力で語義選択と保留を検証（2026-09-10）

利用者の指示に従い、ドライバー/マウスを除き、ファン・クラブ・キャップ・ライト・ストック・ハブ等の合成19文を事前固定した。正解語義が辞書にある12例（肯定10・否定対比2）、保留すべき7例（無文脈3・語義欠落2・未収録語2）。正解IDは辞書定義を参照して実推論前に固定し、要求へ期待値を含めていない。前回lexicalケース集合との原文完全一致は0件。学習データ未知・全商品を代表する無作為標本とは主張しない。肯定10例には商品以外の言語的対照3件を含む。

| 評価群 | 正答/正しい保留 | 保留不足・過剰 |
|---|---|---|
| 正解あり12例 | 11正答 | 歌手を応援するファン1件を保留 |
| 保留が必要な7例 | 4保留 | 3件を誤採用 |

誤採用は「クラブが欲しいです。」→ゴルフ用、「キャップを買いたいです。」→瓶のふた、「ノートパソコンのUSB端子を増やすハブを探しています。」→車輪の中心部。前者2例は依頼表現の残りを文脈と誤認し、Bonsaiと比較モデルの一致で採用した。USB用ハブは辞書候補が1件だけなので文脈との適合を確認せず採用した。スキー用ストックは候補語義が欠けるが保留でき、未知の合成語2例も保留した。複数モデル一致と単義辞書候補は意味の正しさを保証しない。正答11件だけで未知入力の品質合格とはしない。

実CPU資材・実Bonsaiで15 POST・retry0、無認証・課金0、localhost18080のみ。HTTP中央値8.519秒/最大11.426秒。所有server停止と凍結source/model/request hash不変を確認した。保存済み15応答を使ったoffline再生で19結果を完全再現し、追加HTTP0回。原文からのGiNZAを含む候補準備は18/19が語義選択前に停止し、ファンの無文脈1例だけ元query保持で準備できた。正解あり12例も停止しているため、語義選択の成功を検索フローの成功と扱わない。

証拠は `/home/products/bonsai-test-logs/20260910-lexical-unseen-01/`。probe.py prepare/runとreview.pyをuv run --frozen --offline --no-sync pythonで実行した。prepare/run/reviewはexit0（診断完了）で、意味品質判定は不合格。19入力、基準、全要求/全応答、時間、再生結果、候補準備の診断をprivateログへ保存した。製品code・prompt・辞書・閾値の変更はないため全体pytestは再実行していない。外部API・実検索・画像生成・CLIP実推論・委託UIは未実行。文書と診断は未commitで、独立holdoutとして使えるのは観測前までである。


## 165. 原文を保持した商品名候補の解決を条件検査へ先行（2026-09-10）

利用者の方向採用指示に従い、原文上の対象と検索用の商品名候補を分離した。依頼表現の活用をSudachiで認識し、GiNZAの粗い品詞でCCONJになるusbも細分類の名詞情報から複合語へ保持する。原文の名詞と対象語を使って既存辞書の複合語を取得し、一意の候補でも文脈がある場合は適合を比較する。弱い候補や未収録語にはBonsaiで1回だけ語義選択/商品名提案を行い、生成名は辞書へ再照会する。CLIP用Bonsaiと商品採点は維持した。

新しいproduct-query-terms-v1とProductPhraseReviewを原文・構造・辞書/model・要求/応答hashへ束縛した。未収録名には辞書IDを付けず、未確認の候補として扱う。条件検査や視覚抽出で止まっても原文の修飾と候補を返す。未解釈条件を捨てて検索する変更ではない。候補選択には既存の人間確認を使い、旧表示履歴を維持する。新profileの中間計画は旧承認と混用しない。

初回実Bonsai4 POSTは正しい辞書IDと商品名/英訳が混在し、受信契約違反で全保留した。受信検査を緩めず、生成JSON Schemaを辞書選択/語句提案/保留の排他的oneOfへ修正した。最終9 development例では5 POSTを受理し、USB用途→USBハブ、収納対象付き→ケース、車輪用途→車輪のハブを確認した。無文脈クラブ/キャップは追加語義を保留した。未収録エアタグホルダーは辞書IDなし・英訳なしで原文名を返したため、新しい名称や英訳の生成品質は未証明である。

保存済み5応答で9例のreview/保留が完全再現し、追加HTTP0回。原文からの候補準備は3成功・6停止で、用途などの未解釈条件付き5件は商品名reviewを保持してquery_buildで停止し、除外1件はproduct_scopeで停止した。クラブ/キャップの元queryと明示USBハブだけ準備可能だった。商品名候補の改善と検索全体の通過性は分けて評価する。

全体offlineは2892 passed / 20 skipped / 30 deselected（64.61秒）。標準のuv run --frozen --offline --no-sync pytest -m 'not live_api'を実行した。実ローカル辞書/構文解析2件、fixtureによる候補確認・画像承認・CLIP・SQLite履歴の接続1件も成功した。RED/GREEN、全応答、argv・exit・事前test hashは /home/products/bonsai-test-logs/20260910-product-phrase-01/ に保存した。一部のRED/GREEN間にはfixture修正またはformatによるtest hash差があり、同一snapshotのattestationとは扱わない。最終静的gateとhashはaudit.jsonとfinal-gates.jsonへ記録する。

実Bonsaiは合計9 POST・retry0、localhost18080・1 worker・各実行900秒以内・無認証・API費用0。最終HTTP中央値11.963秒・最大14.469秒は候補用追加時間だけで、起動とCLIPを含まない。所有server停止と固定hash不変を確認した。モデル/辞書の新規取得、外部API、実検索、実画像生成、実CLIP、委託UIは未実行。AI attestation・commit・pushは行っていない。


## 166. 未収録の商品名補完・英訳を実Bonsaiで検証（2026-09-10）

利用者の品質確認指示に従い、12合成入力を事前固定した。文脈からの商品名補完4例、未収録名を明記した英訳4例、保留対照4例。対象の複合名4件は現行辞書候補に存在せず、過去4診断directoryのcases.jsonから得た47原文と完全一致0件。学習データ未知とは主張しない。必要概念を保持する補完4/4・英訳8/8、根拠のない具体化0、対照4/4を固定し、同義表現を許容して判定した。

実Bonsai8 POSTは形式を受理したが、補完0/4、名称明記時の英訳0/4、8正例全体の英訳0/8で品質未達。一般名入力はスタンド/ホルダー/ハンガー/トレーの辞書語義選択だけで終了した。スタンドに小さなテーブル、トレーに金属容器panを選ぶ誤り2件を確認した。広い辞書語義への一致だけで、具体的な商品名の補完完了とはできない。未収録名明記4件は生応答が全nullであり、受信契約やJSON復元による英訳欠落ではない。モデル内部の保留理由は未特定。

対照4例はモデル呼出し前に保留したため、Bonsaiの保留精度として数えない。保存済み8応答のoffline再生で12結果が完全一致し、追加HTTP0。原文からの候補準備は文脈なしの2件が元queryで成功、残り10件はquery_buildで停止した。正例の語句品質を、条件解釈や実検索成功と混同しない。

実行先localhost18080、既存Bonsai-8B・1 worker、実8 POST・retry0・上限12 POST/900秒・無認証・API費用0。HTTP中央値4.327秒/最大18.292秒は候補用だけで、早い保留を含むため品質を維持した高速化とはしない。所有server停止と凍結source/model/request hash不変を確認した。

全入力/全応答/基準/時間/意味判定は /home/products/bonsai-test-logs/20260910-product-name-quality-01/ に保存。prepare/run/replayのargvと実exitは各JSONにあり、全exit0は診断完了を意味する。意味品質判定は不合格。製品code・prompt・辞書・モデル・閾値を変更していないため全体pytestは再実行していない。文書リンクとdiffを検査し、結果はdoc-gates.jsonへ記録する。外部API・実検索・画像・実CLIP・委託UI・新規資材取得・AI attestation・commit・pushは未実行。未知名補完と英訳の課題はEXEC-103へ継続記録した。


## 167. 辞書候補0件をBonsaiだけの名称推論へ分岐（2026-09-10）

利用者の実装指示に従い、正常な辞書照会で候補が0件の場合だけ、BonsaiProductSelector.generateから新しいproduct_name_inferenceへ分岐するようにした。原文と対象だけを要求へ渡し、辞書定義・候補ID・生成後の辞書再照会を使わない。文脈修飾なしの未収録名にも呼び出し、名称/英訳各1件を提案させる。辞書あり・辞書エラー・未解釈条件の扱い、CLIPと採点を維持した。

直接生成はbonsai_inference、辞書IDなしで記録する。語尾一致をこの経路だけから外し、原文の対象・条件を保持して未確認の自然な言い換えを許容した。商品名と検索候補の対応、source/model/request/response provenanceは検証するが、意味の正しさを文字列検査で保証したとはしない。原語と同一名の場合の英訳はoriginal_enにも対応付ける。既存profileの読込を維持し、resolver/request hashの世代を更新した。

初期REDは8 failed / 3 passed、同一test hashのGREENで11 passed。追加回帰を含む関連57 passed。fixtureで候補確認・画像承認・CLIP・SQLite履歴までを確認した。既存の辞書ありfixtureのresolution_methodに新規assertでdictionaryを期待した1失敗は、元からのcross_encoder動作に期待を修正して解消した。最終の全体offlineは2906 passed / 20 skipped / 30 deselected（64.29秒）、標準のuv run --frozen --offline --no-sync pytest -m 'not live_api'を実行した。Ruff check/format（346 files）とoffline lockも成功した。

追加の実Bonsaiは前回の既知6例、localhost18080、1 worker、6 POST・retry0・900秒上限・無認証・API費用0で実行。全件が新経路で名称/英訳を返したが、日本語名はいずれも明記された原語であり、未知名の新規補完精度は未測定。意味を満たす英訳3/6、ハンガーをbagにする誤り1件と位置関係の欠落2件が残った。前回の文脈付き明記4例だけなら全保留から2/4の概念充足へ変わったが、独立holdoutではない。最終品質合格とは扱わない。

全要求/全応答、RED/GREEN argv・exit・test hash、失敗/成功ログ、source/model固定、意味判定は /home/products/bonsai-test-logs/20260910-dictionary-miss-inference-01/ に保存する。初期phaseの同一hash確認と、その後のテスト追加/formatを区別する。既知語義が存在する一般名の補完問題は今回の候補0件分岐の対象外。ネット検索、外部API、新規モデル取得、実検索・実画像・実CLIP・委託UI、AI attestation、commit、pushは行っていない。


保存済み6応答によるoffline再生で6件の候補reviewが完全一致し、追加HTTP0回。文脈なし2例は候補準備成功、用途付き4例はreviewを保持してquery_buildで停止した。所有server停止・固定hash不変・private directory権限を確認。最終結果は同directoryのRESULT.mdとaudit.jsonに保存した。


## 168. ヘッドフォン表記でOPUS-MT日英翻訳を比較（2026-09-10）

利用者の試験指示に従い、OPUS-MT ja-enをCPUで検証した。ヘッドフォン表記を今回の入力/説明へ反映し、過去の固定ログは変更していない。日本語の商品句全体12件と必要概念を事前固定し、通常精度/INT8で各1回・計24翻訳を行った。既知の商品句4件と追加8件で、元語と訳語の一致だけでなく対象・用途・設置位置を確認した。過去Bonsaiは文脈全文を受けていたため、同一条件のmodel比較ではない。

公式カードが示す元配布opus-2019-12-18.zip（280,569,863 bytes、SHA-256 64cba8697989961ff02bda5834b978345f72635b172f03b55eb4b9464004ced9）を取得し、CTranslate2 4.8.2でfloat32/int8_float32へ変換した。Python 3.13.13、SentencePiece 0.2.1、NumPy 2.2.6、sacremoses 0.1.1をrepository外の独立環境に準備。元のSentencePiece・共有語彙と句読点等の前処理を使用し、入力unknown tokenは全て0。CPU1 worker/2 threads、beam4、最大64出力tokens、全出力EOS終了だった。

両精度で必要概念の充足6/12、既知4件3/4、追加8件3/8。デスク下ヘッドフォンハンガーはHeadphone hanger under the deskと訳せた。名刺入れ→A card.、収納かご/フックの欠落、保護スリーブ→storage、コンセント用キャップ→filter、モニター上の位置欠落が残るため品質合格ではない。正答判定には自然な同義語を許容し、英語の流暢さ満点を意味しない。

1件中央値float32 0.133秒/INT8 0.046秒、最大0.271/0.091秒、ロード0.305/0.091秒、process peak RSS518.6/153.9 MiB。model.binは305,346,797/80,485,157 bytes。各精度を別processで一巡した値で、Bonsai/CLIPの同時常駐や本番iGPUの計測ではない。INT8で軽量に動いたが、商品名英訳の無条件な置き換えとして採用しない。

モデル・packageの公開取得以外の外部通信0、推論時はunshare --netによるnetwork namespace分離、認証不要・推論API費用0。初回Python 3.14のNumPy source buildを停止してbinary wheels対応Python 3.13へ移した経緯と、診断socket差し替えでssl importが壊れた翻訳前失敗を保存した。後者は翻訳0件で、同じ入力/基準/モデルのrun-02へ修正して全24翻訳を実行。入力・モデル・コードhash不変とprivateログ権限を確認した。

資材は /home/products/models/opus-mt-ja-en-ct2-v1/、環境は /home/products/model-envs/opus-mt-eval-02/、全入力/出力/時間/採点/argv/exit/hashは /home/products/bonsai-test-logs/20260910-opus-mt-ja-en-01/。run-02のprepare/float32/int8_float32は全exit0で、意味品質判定は不合格。製品code・依存lockを変更していないため全体pytestは再実行せず、文書リンクとdiffを検査する。Bonsai名称推論/CLIP/採点、翻訳provider接続、実検索・画像生成・委託UI、外部翻訳API、commit/pushは変更・実行していない。


## 169. 辞書にない商品句だけでOPUS-MTを再評価（2026-09-10）

利用者の指示に従い、前回12商品句を現行のJMdict/WordNetへ実照会した。完全句のlookup_contextualと、GiNZA解析後の対象/修飾によるlookup_productsが両方0件の例だけを対象にした。全12件の照会は正常に完了。辞書登録済みの名刺入れ（jmdict:1752260:1、(business) card case）とヘッドフォン（wordnet:03261776-n）を除外し、10商品句を未収録として評価した。

前回実行済みのfloat32/INT8出力と事前基準・意味判定をhash確認して再集計し、モデル再実行・閾値・同義語判定の変更は行っていない。通常精度/INT8とも概念充足5/10（50%）。元の成功6件からヘッドフォン1件、失敗6件から名刺入れ1件を除外した結果で、名刺入れの誤訳を未収録語の不合格理由にしていない。

残る失敗5件はモニター上の位置欠落、収納フック/収納かごという対象の欠落、保護スリーブ→storage、コンセント用キャップ→filter。通常精度でも同じ5件が未達で、量子化だけの問題とは扱えない。過去の観測済み10件であり、独立holdoutやBonsaiが生成する全名称、検索フロー全体の精度を示さない。

新規推論、外部通信、認証、課金0。全照会/出力参照/hash/判定は /home/products/bonsai-test-logs/20260910-opus-mt-unlisted-01/ に保存し、元のログを保持した。分類実行exit0、意味品質判定は不合格。製品code・依存・provider・CLIP・ランキング・UIは変更していないため全体pytestを再実行せず、文書リンクとgit diff --checkを検査する。OPUS-MTの自動採用は引き続き保留。commit/pushは実施していない。


## 170. 未収録語の精度受入と実E2Eの事前検査（2026-09-10）

利用者がOPUS-MTの未収録10商品句の5/10（50%）を合格点として受け入れたため、GOAL/NEXT-STEPSへ判断を追記した。過去の測定値・判定ログを保持し、精度改善を実E2E再開の前提としない。現行candidate実入口はOPUS-MT未接続であり、今回の検証対象は辞書/文脈解析・Bonsai・参考画像1枚/偽画像1枚・実検索・CLIP/単語一致採点・SQLite履歴である。

実行資材の存在とmanifest/hash、固定合成入力のGiNZA解析をローカル確認した。初回の診断結果出力でProductStructureをmodel_dumpしようとしてAttributeErrorになり、dataclassのasdictへ修正後に完了。製品codeを変更していない。事前検査に使用したBonsaiモデル/実行ファイル、CLIP、辞書は既存資材で、追加取得やprovider疎通はしていない。

uv run --frozen --offline --no-sync pytest -m 'not live_api' -q によりcandidate live入口・画像承認/CLIP/履歴のfixture接続・商品句/辞書フロー・結果JSON・query選択の関連6ファイルを実行し89 passed（5.52秒）。全体pytestは製品変更がないため再実行していない。argv/実exit/log/hashと具体的な実行コマンドは /home/products/bonsai-test-logs/20260910-candidate-e2e-preflight-01/ へ保存した。

Cloudflare/Outscraperの公開料金だけを再確認し、参考1枚+偽画像1枚+最大24商品で有料枠換算0.048633 USDと見積もった。credential読込0・推論/検索/画像API call0、実E2Eは今回の具体的送信条件に対する人間承認待ち。委託UI/既存DB/製品providerを変更せず、commit/pushも行っていない。文書リンク/anchor/fenceとgit diff --checkの結果はdoc-gates.jsonへ保存する。


## 171. OPUS-MTを未収録商品句と実E2E入口へ接続（2026-09-10）

利用者の接続指示を受け、任意のOpusMtTranslatorをContextualQueryExpanderとcandidate実CLIに接続した。正常な辞書候補0件だけが対象で、Bonsaiは日本語名を提案し英訳欄はnullに固定する。原語/提案名を重複除去して各1英訳を作り、人間確認前の候補へ反映する。翻訳失敗時は日本語候補を保持し、英訳をnullにする。登録済み辞書・視覚Bonsai・単語一致/CLIP採点・既存DBは維持した。

ローカルadapterは既存のINT8モデル/語彙/tokenizerを固定hashで検証し、別Python環境へstdin JSONで最大2句を送る。CPU1 worker/2 threads・beam4・64 tokens・30秒・retry0。credential環境変数を渡さず、固定エラーを使う。翻訳traceを辞書/Bonsaiと分け、translator identityを要求hashへ含める。旧JSONは追加項目を省略可能で、既存候補cache/承認の新構成への流用を防ぐ。主環境の依存lockは変更していない。

初回REDはtranslator引数未実装で7 failed。実装後に新規fixtureのfragments引数不足を修正したため、最初のRED/GREEN全体を同一test hashの証拠とは扱わない。adapter未実装、CLI未接続、名称専用schema未実装のREDをそれぞれ保存。関連90 passed。初回の全体はumask0077が既存権限fixtureへ影響し10 failed / 2918 passed、pytestだけ0022へ戻して全体2928 passed / 20 skipped / 30 deselected（65.89秒）。Ruff check/format350 files・offline lock・文書リンク/diffも成功。AI attestationではない。

実OPUS-MT・実辞書・実GiNZAを用い、縦置きノートパソコンスタンド、マグネットケーブルホルダー、デスク下ヘッドフォンハンガーの3句で未収録分岐→翻訳→候補JSON復元を確認した。推論processはnetwork namespace分離、外部通信0。Bonsaiだけは名称fixtureで、画像/検索/CLIP/履歴の実サービス試験ではない。候補選択と画像承認を経てCLIP/履歴まで進む確認は別のoffline fixture testで行った。

全ログ/argv/exit/hash/ローカル出力は /home/products/bonsai-test-logs/20260910-opus-connection-01/。既存の語句品質評価は変更せず、接続した実E2Eの全体品質を証明したとは扱わない。未commitで、委託UIの確認/起動/接続とcommit/pushは行っていない。先の利用者承認済み範囲で、翻訳設定を有効にした固定マグカップの実E2Eを開始した。


実E2Eの今回の到達点は検索語選択待ち。実Bonsaiの語義選択/視覚提案は2 POST、各12.672秒/11.070秒で完了した。GiNZAとjapanese-reranker-xsmall-v2を含む文脈辞書経路を使い、マグカップの辞書語義から元語・言い換え・mugを提示した。OPUS-MTは辞書hitのため0回。画像生成と実検索はこの時点で未実行。実行記録は /home/products/bonsai-test-logs/20260910-candidate-real-e2e-01/、継続状態は接続ログのlive-progress.json。


## 172. 接続後の実E2Eを参考画像確認まで再開（2026-09-10）

利用者の再開指示を受け、待機中の同じcandidate実行を継続した。承認済み合成入力の元query「マグカップ」を保持し、候補の言い換え/英訳は適用していない。実Bonsaiの視覚条件「丸みのある形」に基づき参考画像1枚を生成し、Cloudflare HTTP200を確認した。表示画像では丸みのある胴体のマグカップを確認した。画像の最終採否は人間確認待ちである。

この段階の累計はBonsai2 POST、Cloudflare1 POST、Outscraper0、OPUS-MT0、retry0。新しい実行やBonsaiの再推論はしていない。生成画像は /home/products/bonsai-test-logs/20260910-candidate-real-e2e-01/image-1.png、応答status/byte数/digestはimage-http-1.json、候補/条件はplan.jsonへ保存した。偽画像生成・候補取得・CLIPランキング・履歴再読込は未実行で、参考画像承認後に同じ実行を継続する。


参考画像への人間了承後、同じCLI実行で偽画像1枚もCloudflare HTTP200で生成した。丸い胴体から角張った胴体への差を目視確認し、比較画像と元query「マグカップ」を最終確認用に提示した。生成物は同実行directoryのimage-2.png、応答metadataはimage-http-2.json。累計Bonsai2/Cloudflare2/Outscraper0、retry0で、検索前の最終承認待ち。


## 173. 実検索へ進行し候補取得中の停止を確認（2026-09-10）

利用者が最終画像と検索語を了承し、待機中の同じCLIから実Outscraper検索を開始した。初回HTTP202、同一taskの結果確認8回で候補取得は完了しなかった。runnerはcandidates段階でfailed、診断codeはunexpected、実exit1。累計Bonsai2 POST・Cloudflare2 POST・Outscraper1 task/8 polls・商品画像0・CLIP0・retry0だった。

結果metadataの時刻とCLIのsignal.alarm(900)を照合し、人間確認待ちを含む15分の全体上限と停止時刻が一致した。Outscraperの50 polls上限ではない。元例外型はsummaryに残っておらず、期限到達に整合する診断として扱う。Outscraper完了や商品取得、ランキング品質の成功を推測しない。実請求額は照会していない。

参考/偽画像2枚・plan・応答status/byte数/digestを保持し、ランキングJSON/表示履歴JSONは未生成を確認。所有BonsaiサーバーとCLIの停止を確認した。失敗後の新規provider要求や自動retryはしていない。追加照合はローカルのみ。最終結果は /home/products/bonsai-test-logs/20260910-candidate-real-e2e-01/RESULT.md、summary.json、execution-audit.jsonへ保存し、接続ログのlive-progress/RESULTも更新した。

製品code変更がないためpytestは再実行せず、Markdownリンクとgit diff --checkを検査する。接続後のoffline2928件成功、実OPUS-MT/辞書/GiNZA3句接続と、この実E2E未完了を分けて記録する。commit/pushは未実行。

## 174. 前回のOutscraperタスクの最終状態を照会（2026-09-10）

利用者が新規検索より先に前回結果の確認を指示したため、再実行準備を中断して既存タスクを照会した。既存credentialを用い、api.outscraper.cloudの履歴GETを3回、特定したタスクの結果GETを1回実行した。履歴の実応答が公式例と異なり、完了履歴の抽出をやり直したため履歴照会が1回増えた。生応答・credentialは保存せず、抽出した識別情報と状態・byte数・digestのみrepository外のprivate directoryへ記録した。

完了履歴のIDから構成した初回応答のSHA256が、元実行で保存した応答SHA256と完全一致した1件を照会対象とした。18:21 JSTの結果照会はHTTP200、provider statusはFailureだった。HTTP成功は検索成功を意味せず、前回検索は処理中ではなく失敗終了していた。失敗原因の詳細は今回の診断では確認していない。新規検索task・画像生成・Bonsai実行は0回、ランキング/履歴も未生成。追加検索の課金を伴う発注は行わず、実請求額は未照会。

証拠は /home/products/bonsai-test-logs/20260910-prior-search-status-01/result-status.json。今回の状態照会のための製品code変更はなく、再実行用codeとテストの作業は途中のままで、完了またはテスト成功として扱わない。

## 175. 保存画像から実検索を再実行しランキング・履歴へ到達（2026-09-10）

利用者の再実行指示に基づき、検索語と画像2枚を保持したまま新規Outscraper1 taskを発注した。保存plan/画像/消費済み承認を読み取り、今回の承認に基づく検索期限を付けるCandidateSearch.from_approved_planと診断入口tools/candidate_search_retry.pyを追加。元承認tokenは再消費せず、元出力も変更していない。新規provider要求はapi.outscraper.cloudの1 query/24商品・最大50 polls、商品画像はm.media-amazon.comの最大24件に限定。既存API keyを利用し、検索費用見積り0.048 USD・金額強制上限なしを通知した。実請求額は未照会。

初回HTTP202から12 pollsでSuccessへ到達し、24商品/商品画像24枚を取得。ローカルCLIP7 batchesを経てランキングJSONとSQLite表示履歴を保存し、履歴一覧/詳細・JSON復元・参考画像2枚の画素一致を検証した。実行exit0、391.621秒。Bonsai/Cloudflare/OPUS-MTの再実行は0、追加retry0。元画像を今回生成したとは扱わない。保存元一式のdigestが実行前後で不変であることを確認した。

接続完了と順位品質は分ける。画像スコアは24件すべてunknown、23件は単語一致を含む総合score0だった。商品名の多くが英語で、日本語検索語との単語一致が働いていない。3000円以下と確認できる19件、価格不明3件、予算超過2件の順序は正しいが、条件を満たす商品の間で丸みを評価できていないため順位品質は合格としない。unknownの詳細な校正理由は表示履歴に保存されておらず、原因を断定しない。追加の画像取得や再検索は行っていない。

元のRED7件に対応するGREENに加え、承認拒否・改変・provider失敗時の識別情報保持を検証。全体offlineは2940 passed/20 skipped/30 deselected、73.35秒。Ruff lint/format、Markdown検査、git diff --checkも成功。検証ログ・argv・source hashは /home/products/bonsai-test-logs/20260910-search-retry-prep-02/、実結果は /home/products/bonsai-test-logs/20260910-search-retry-live-01/。task-statusには検証済みtask ID/statusを保存し、生provider応答・生例外・credentialは保存しない。委託UIの確認/起動/接続とcommit/pushは行っていない。

## 176. 実画像評価unknownの原因を校正規則に特定（2026-09-10）

利用者の原因特定指示に基づき、完了済みタスクの結果GET1回と商品画像GET24回で同じ検索結果を再評価した。接続先api.outscraper.cloudとm.media-amazon.com、既存Outscraper API key、既存HTTP/応答サイズ上限、全体600秒・retry0、新規検索/画像生成0、API追加料金の見込なしを通知して実行。請求額は未照会。結果本文のSHA256が元実行のSuccess応答と完全一致したことを確認した。画像は同じURLから再取得しており、元実行の商品画像pixel digestは保存されていないため、その時点の全画素一致までは証明しない。

現行の画像評価関数を実行し、校正関数への入力を変更せず診断用に取り出した。取得画像24枚・CLIP7 batches、49.905秒で全件unknownを再現。校正前は24件すべてscored。参考/偽画像間距離は0.02605174630600715で、近接保留の1e-6を超えていた。正規化marginは最小0.32639215238262115、最大0.8605415864517687、幅0.5341494340691475、正24件/負0件、±1飽和0件だった。

counterfactual_calibration.pyのゼロ交差または同じ飽和端点2件以上を要求する規則が、この片側分布をinsufficient_diversityとして拒否した。provisional_counterfactual.pyは校正保留時に全候補の画像componentをunknownへ変換し、image_scoreをNoneにする。CLIP推論や画像取得の失敗ではなく、比較値が計算できていても検索結果の分布によって全件の画像順位を無効化する設計が直接原因。値が正であることはCLIP上で参考画像の方に近いことを示すだけで、実商品の条件充足を証明しない。

数値とdigestのみの保存入力をofflineで再生し、同じ24件unknownを再確認した。原因を切り分ける合成対照では1値だけ負へ変えると校正可能になり、該当分岐による保留であることを確認。この改変値は実商品の評価や改善結果には使っていない。既存の校正/暫定評価テスト12件も成功。製品code・閾値・順位規則は変更せず、全体pytestは繰り返していない。

private診断は /home/products/bonsai-test-logs/20260910-image-unknown-diagnostic-01/。probe.py、summary.json、score-inputs.json、calibration.json、image-batch.json、offline-replay.json、pytest.logを保存し、生provider本文・商品本文・credentialは記録していない。校正保留の理由が元の表示履歴ではunknownへ集約されて失われていた点も確認した。

## 177. 総合0の原因を修正し相対順位の保留基準を縮小（2026-09-10）

利用者が総合score0の原因特定と、必要最小限の保留基準への変更を指示した。元planには原語英訳があるが、CandidateSearch.rankは日本語中心のretrieval_intentだけを_title_scoreへ渡していた。これにより英語商品名23件が単語一致0となり、画像scoreの校正保留と合わさって総合0が23件発生した。readyな原語英訳をタイトル比較だけに接続し、検索request/元条件/未確認言い換えの扱いは維持した。

candidate画像順位をrelative-image-v1へ変更。計算可能な条件の最小marginを(m+1)/2へ写し、候補4件以上・分布幅・正負混在・飽和件数を不要にした。候補1件や同点でも比較値を保持し、一部条件が参照近接の場合は残りの条件を使ってpartial_conditionsを記録する。同じ画素の別商品は埋込みを再利用して各商品にscoreを返す。画像不在・全条件の参照近接・不正入力は保留/拒否を維持し、必須条件の確認済み/不明/不一致の優先順序と資源/承認/URL/digest境界を変更していない。

新しい中間candidate-confirmed-lexical-v3と最終candidate-lexical-clip-v3、履歴のcounterfactual-relative-v1を識別する。旧profileのJSON/SQLite履歴を維持し、新旧方式の型/profile混在は拒否する。旧calibrated modeの評価契約/テストは変更せず、candidateだけrelative modeを指定する。実runnerには数値・状態・digestだけのimage-scores.json保存を追加した。旧画像schemaへ未校正marginを格納せず、新schemaには計算元marginとpartial/保留理由を保持する。

新規テスト14件のRED後に実装してGREEN、さらに同じ画像を持つ2商品の評価欠落をRED再現して修正した。既存接続テストの新profile/同点でもscore利用可能という期待を更新し、旧履歴読込テストは維持した。全体offline2957 passed/20 skipped/30 deselected、67.86秒。Ruff lint/format、Markdown検査、git diff --checkも成功。新規16件に加えて既存履歴互換のv3 caseを1件増やした。

前回の完了済み検索結果だけをapi.outscraper.cloudへGET1回し、元Success応答のSHA256一致と、保存済みCLIP診断数値の商品digest一致を確認して再計算した。既存API key利用、HTTP30秒/8 MiB、追加検索料金見込なし、新規検索・商品画像取得・モデル推論0という条件を通知して実行。取得後の順位/表示履歴はofflineで計算した。画像availableは0→24、単語一致0は23→1、総合0は23→0。画像score範囲0.663196〜0.930271、総合score範囲0.151401〜0.986054。最低点を付けて0を隠す処理は追加していない。

価格3000円以下19件→価格不明3件→超過2件の順序と、その中でのscore降順を確認。新規履歴の一覧/詳細/JSON・元参照画像2枚の画素再読込も成功し、元承認一式のdigestは不変だった。この比較は計算可能な点数が失われなくなった証拠であり、未知商品の順位品質合格や新規実E2E成功とは扱わない。実請求額は未照会。ログ/RED/GREEN/hash/比較結果は /home/products/bonsai-test-logs/20260910-relative-ranking-01/、比較後の表示JSONとSQLiteは同directoryのreplay/。生provider応答/credentialは保存していない。委託UIとcommit/pushは対象外。


## 178. 対象部位と形状専用比較をcandidateへ接続（2026-09-10）

利用者が、対象部位の切出しと属性ごとの特徴分離を実装するよう指示した。既存CLIPの正例/偽画像差を再提案せず、shape条件を独立した2D輪郭比較へ接続した。Bonsaiの既存視覚提案1回でfocus(kind、英語の対象部位target、scope)を作り、query選択・参考画像/検索確認へ提示する。focusをplan/画像承認のdigestに含め、形状を変える偽画像promptでは対象以外の色・材質・背景・撮影条件の維持を指示する。focusなし旧条件のJSONとhashは維持した。

shape_similarity.pyは対象maskだけを使い、位置/倍率を正規化し縦横比を保持した96px輪郭で最小正例IoU−負例IoUを計算する。新しいattribute-image-v1をcandidate-attribute-image-v1と表示履歴counterfactual-attribute-v1へ接続。形状は全体CLIPで埋め戻さず、色/材質/外観や旧条件は既存CLIP経路を保持する。欠測は条件単位で保留し、他の計算可能な条件を保持する。新profileでは資格条件の充足順の後、画像が観測できた候補を未観測より先に並べる。旧profile/SQLite保存値を再採点しない。画像診断JSONには数値・状態・digestだけを保存する。

LocalClipSegRegionsは固定CIDAS/clipseg-rd64-refined revisionのsafetensorsを検証し、別のCPU Python processで最大36画像×3対象・240秒・retry0・2threadsを使う。推論はlocal_files_only、offline環境、credential非継承とし、一時画像/maskを処理後に削除する。公開package/重みの取得は環境準備として実施し、通常のpyproject/uv.lockにtorchを追加していない。CLIには--region-python/--region-assetsの対を追加。未設定のshapeはextractor_unconfiguredで保留する。

検証はtests/test_attribute_image_ranking.pyの13件とtest_attribute_image_boundaries.pyの10件が成功。固定maskによるRGB非依存、形状差、位置/倍率・縦横比、同輪郭参照、部分条件、欠測時の順序、JSON/hash/領域binding、subprocessの出力形状・数値・timeout・credential非継承、自然言語fixtureから画像確認/候補/順位/SQLite履歴までを確認した。全体offlineは2980 passed/20 skipped/30 deselected、71.08秒。Ruff全体check/format、lock整合、Markdownリンク、git diff --checkも成功。TDDの初回REDには未実装moduleのimport失敗が含まれるため、意味品質の失敗再現やattested evidenceとは扱わない。接続入口欠落4件と未観測形状の優先問題1件は別のREDで記録した。

保存済み参考/偽画像と、前回確認済みメーカー写真2枚を用いて実ローカルCLIPSegを確認。最初の4画像×2対象8推論は10.818秒。固定実装の4画像×本体1対象4推論は5.762秒、外側の起動込み6.162秒、child peak RSS949568 KiB（927.3 MiB）。本体指定時の形状marginは直線的な製品−0.223667、丸い製品+0.214382になったが、maskに内部欠けと2商品の連結が見つかった。数値の順位変更だけを品質改善の証明にせず、自動領域抽出と実順位品質は未達と判定した。撮影方向差、未知カテゴリ、iGPU性能は未検証。実Bonsai・新規検索・画像取得/生成・ブラウザE2Eは実行していない。

実装/検証記録は /home/products/bonsai-test-logs/20260910-attribute-image-01/。verification.json、static-verification.json、focused-final.log、offline-final.log、REDログ、test SHA256、final-local/local-model-summary.json、resources.json、mask-body.pngを保存。生provider応答やcredentialを記録せず、元E2E成果物を変更していない。/usr/bin/timeが未導入だったため、最終計測には標準resource.getrusageを使用した。残課題は[自動領域抽出の品質](ISSUES.md#exec-104残課題-自動領域抽出の品質)。


## 179. MobileSAMで個体分離と部位輪郭を改善（2026-09-10）

利用者の「その方向で進めて下さい」に基づき、CLIPSegとMobileSAMを組み合わせる任意のbackend抽出器を実装した。固定されたMobileSAM source/checkpointと独立CPU環境を準備し、既存のRegionMaskからcandidate属性別順位/SQLite履歴まで接続した。実検索・実Bonsai・画像生成・委託UI・3Dは実行していない。通常環境の追加依存は既に間接利用していたSciPyの明示宣言だけで、PyTorch等は別環境に置く。

初回の実モデル出力は金属製品の本体でなく蓋を選んだ。正しい本体輪郭はMobileSAM候補に存在しており、選択式が小さな高確信度領域を優先していた。個体階層の解決だけでは直らず、候補間の最終選択に意味的被覆を含むsoft Diceを用いた。さらに背景候補の除外、部位maskの個体内制限、局所の部位一致と個体間の被覆評価の分離を追加した。画像参照の希望形状を候補選択に使わず、カテゴリ固有のpromptや輪郭ルールも追加しない。

実モデルの出力を見る前に手動近似maskと採点基準を固定し、以前の4枚だけで比較した。平均IoU改善0.05以上、各例の低下0.05以内、平均境界F低下0.01以内、別個体混入0.05以内、4件ともmask取得を要求し、最終結果は全基準を満たした。境界の許容距離は3pxである。

| development画像 | CLIPSeg IoU | CLIPSeg＋MobileSAM IoU |
|---|---:|---:|
| 丸い参考本体 | 0.9108 | 0.9703 |
| 角張った偽画像本体 | 0.9118 | 0.9460 |
| 金属製品本体 | 0.5913 | 0.9623 |
| ガラス製品1個体 | 0.3928 | 0.9083 |
| 平均 | 0.7016 | 0.9467 |

平均境界Fは0.3494→0.7845、ガラス画像の別個体への混入率は0.9930→0。金属本体内部の大きな欠けを解消し、ガラス2個の結合を防いだ。ただしガラスの取っ手が一部混ざる。固定4例・近似maskによるdevelopment評価であり、未知商品に対する品質合格ではない。

CPU2threads・4画像1対象の独立実行は、CLIPSeg5.924秒/子process peak RSS949256 KiB、追加方式58.146秒/1416332 KiB（約1.35 GiB）。新worker内部は53.990秒で、全体値には資材照合と起動も含む。最初の旧/新同時実行は速度比較に用いず、並行処理を外した測定を採用した。iGPU速度・最大入力の所要時間・実検索E2Eは未確認。

切出し改善と順位品質は別に判定した。同じ既存の輪郭IoU採点では金属製品のnormalized margin0.2619、ガラス製品-0.1161となり、丸みの意味に沿う順位を保証できない。取っ手の混入、姿勢・縦横比と局所形状の区別が残るため、自動順位の品質合格とはしない。

単体/接続testは17件。初期module/constructor未実装、個体階層、被覆、背景/個体外混入、部位選択それぞれのREDを保存し、実装後のGREENを確認した。過程の全体offline2996件は後続修正前の結果として保持し、最終sourceでは全体offline2997 passed/20 skipped/30 deselected、70.19秒、exit0。Ruff check/format、uv lock --check --offline、Markdown links、git diff --checkも成功した。モデルの全出力mask、数値診断、手動mask/基準、失敗試行、source/test SHA256、実行argv/exitはrepository外の /home/products/bonsai-test-logs/20260910-mobile-sam-01/ に保存した。最終比較はcomparison-final.png、判定はacceptance-final.json、モデル測定はmobile-parts/summary.json、旧方式はbaseline-isolated/summary.json。


## 180. 意味に対応した形状特徴を実装・比較（2026-09-10）

利用者が「適切に評価するにはどうすればよいか」への提案を受けて「進めろ」と指示した。まず手動近似本体maskだけで旧IoUを再評価し、金属-0.2361、ガラス-0.4354となる逆転を再現した。自動切出しだけでなく、輪郭全体の一致を特定の意味条件へ代用することが問題である。

側面の膨らみ・側面の曲がりの滑らかさ・画像上の縦横比を個別に測定するshape_features.pyを追加した。測定種別と値の希望方向をBonsai提案/確認条件/画像生成要求へ含め、数値計算・candidate-attribute-image-v2・counterfactual-attribute-v2の履歴まで接続した。商品本文の推論やLLM採点は追加していない。旧measureなしのJSON/hash、旧v1採点、保存履歴を維持した。

| 本体maskによる側面の滑らかさ比較 | 旧IoUの金属/ガラス | 新特徴の金属/ガラス |
|---|---|---|
| 手動近似mask | -0.2361 / -0.4354 | -1.0000 / 0.0352 |
| 保存済みMobileSAM mask | 0.2619 / -0.1161 | -0.6457 / -0.0540 |

今回の2商品ではガラスが上になる方向へ改善した。ただし、側面の滑らかさを選んだ場合の相対比較であり、ガラスが強い適合判定になったわけではない。測定項目の選択は診断上の明示指定で、実Bonsaiによる曖昧な「丸み」の解釈成功を示さない。旧24商品全体の総合順位も再実行していない。

手動maskの膨らみは参考0.0755/偽画像0.0767と差がほぼなかった。この条件はfeature_reference_too_closeで保留する。自動maskでは0.0816/0.1074と方向まで逆転したため、参照差だけの初版は不適切な点数を出した。希望方向higher/lowerを必須とする修正を追加し、逆方向はreference_direction_mismatchで保留する。旧全体CLIPやIoUへfallbackせず、他の評価可能な条件は保持する。表面や3D形状を輪郭から判定できない場合はunobservableとする。

パラメータと採点基準を固定した合成16組×3特徴の評価は、膨らみ16/16、滑らかさ16/16、縦横比16/16で正順序となり、保留/同点0。各90%以上・全件採点の事前条件を満たした。生成形状族はdevelopmentと共通で、未使用パラメータによる合成検証に限る。未知実商品・独立カテゴリの品質証拠ではない。特徴の測定/比較には新しいモデル依存を追加していない。

新規14件と既存関連を含む54件が成功。初回REDは未実装module/新focus拒否/接続未実装を含み、採点品質の失敗とは区別した。方向必須、feature証拠の改変、非観測条件の抽出未呼出しのRED/GREENも保存した。参照差不足の接続試験では同じ参照を作るfixture分岐が欠けていたため、期待値を変えずfixtureを修正した。最終全体offlineは3011 passed/20 skipped/30 deselected、71.69秒、exit0。Ruff check/formatとuv lock --check --offlineも成功。文書リンクとgit diff --checkも成功した。

証拠は /home/products/bonsai-test-logs/20260910-shape-features-01/。manual-baseline.json、development-first.json/development-final.json、synthetic-holdout-manifest.json、evaluation-policy.json、synthetic-evaluation.json、評価script/hash、RED/GREENログ、全体ログを保持した。実検索・画像生成・実Bonsai・CLIP/領域モデル再推論・委託UIは0回。


## 181. 全24商品の形状特徴付き総合順位を再評価（2026-09-10）

利用者の「全24商品の総合順位を確認せよ」に基づき、保存済み旧順位/画像score/資格判定を確認した。全画像とURLは保存されていなかったため、必要な完了済み結果GET1回・Amazon商品画像最大24 GET・既存Outscraperキー・retry0・新規検索/画像生成0・追加費用想定0の条件を通知し、今回の確認指示の範囲で実行した。完了済み応答SHA256と24画像すべての画素SHA256が元データに一致した。invoiceの実課金額は未確認。取得23.707秒。

元の資格判定とタイトル単語点を復元し、旧総合点と順位を24件すべて現在の計算コードで再現した。新方式はside_smoothness/higherを診断で明示し、既存の価格等条件・単語点と組み合わせて再計算した。元plan/画像承認/履歴は変更せず、新しい本番承認を受けた完了結果とは扱わない。評価対象画像は参考/偽画像2枚を含む26枚。ローカルCPU2threadsのCLIPSeg＋MobileSAMと数値計算は275.830秒、子process peak RSS1444216 KiB（約1.38 GiB）。実Bonsai/CLIP/新規検索/画像生成は0回。

新mask/scoreを見る前に、元画像の本体が参考画像のように膨らんでいるかをアシスタントが0/1/2で評価し固定した。最初の文章定義で円筒形と直線的側面が重複したため、元画像閲覧後・新点数閲覧前に0=概ね平行な直線側面、1=弱い曲がり/テーパー、2=明瞭な膨らみへ明確化した。独立専門家の正解ではなく、この既知24商品の開発診断である。

| 指標（資格条件適合19件内） | 旧方式 | 新方式 |
|---|---:|---:|
| 目視gradeが違う111組の順位一致率 | 43.2% | 36.9% |
| nDCG@10 | 0.3650 | 0.3362 |
| 上位5件中の明瞭な膨らみ | 1件 | 1件 |

全体として改善せず、今回の目視基準では悪化した。明瞭な膨らみの3商品は旧5→新4位、17→10位、15→14位と改善したが、他商品の順序まで含めると品質は下がった。強い適合が3件しかないため、事前の正式判定の構成条件（4件以上）も満たさずineligible。構成不足と比較指標の悪化は区別する。

新1位は直線的な白いマグで、側面特徴値0.7861が参考値を上回り画像点1.0となった。完全な長方形でもside_smoothness=1.0、side_bulge=0.0を再現した。側面の滑らかさは直線も高く評価するので、丸い膨らみの意味の代用にはならない。2商品の比較成功を全体の品質改善へ拡大できなかった。

画像採点21/24、3件は保留。maskが空/境界接触なのではなく、微小な分離片のため外接範囲内に空行が2/5/19行でき、測定器の連続行検査が拒否した。最大連結成分は各99.97%以上だった。これら3件は適合商品内の17〜19位となり、資格条件の適合19件→未確定3件→不適合2件の優先順序は維持された。総合点だけの全行降順とは異なる。

記録は /home/products/bonsai-test-logs/20260910-ranking24-01/。全24件の順位/旧順位/価格/資格状態/単語点/画像点/総合点/目視gradeはRANKING.md、全maskはranked-masks.png、数値はquality-summary.json/diagnosis.json。要求上限、全取得画像、モデルmask/診断、source hash、argv/exitも保存した。production codeは変更していない。診断の初回検算はsystem Pythonにpydanticがなく失敗したが、準備済みuv offline環境で24件すべてを検算できた。通常test全体の再実行は行わず、元総合点/順序の再現と新順位の全件性・資格順序・source不変を検証した。

## 182. 膨らみ測定の識別力と追加時間をオフライン検証（2026-09-10）

利用者の精度検証指示に基づき、EXEC-107の26mask（参考2・商品24）、資格判定、単語点、固定済みのアシスタント目視gradeを再利用した。計算式と比較基準を今回の新score取得前にSHA256で固定し、結果を見て調整せず一度評価した。既知development集合であり、未知商品や独立専門家による正解ではない。

repository外の実験用bulge_probe.pyで、99.5%以上の最大連結成分だけを保持し、行中心の直線から20度以内の傾きを補正する。上下15%を除き、左右の輪郭と端点帯の基準線との外向き距離を幅で正規化する。左右の小さい張り出しを採ることで片側突出を抑える。膨らみ量・位置・範囲・64点分布を保存した。既存domain/profile/承認/履歴へは接続していない。非対称な膨らみ一般への妥当性は未検証。

| 方法（資格適合19件内、grade差がある111組） | 順位一致率 | nDCG@10 | 上位5件の明瞭な膨らみ | 画像採点 |
|---|---:|---:|---:|---:|
| 前回の滑らかさ | 36.9% | 0.336 | 1 | 21/24 |
| 新しい膨らみと既存の参照差検査 | 47.3% | 0.290 | 0 | 0/24 |
| 従来の膨らみ値を使う診断 | 61.3% | 0.735 | 2 | 21/24 |
| 新しい膨らみ値を使う診断 | 85.6% | 0.933 | 3 | 24/24 |
| 参考画像との膨らみ分布だけを比較する診断 | 84.2% | 0.933 | 3 | 24/24 |

新しい測定値での診断では明瞭に膨らんだ3商品が1〜3位となり、前回1位の直線形状を上位から分離した。微小孤立片による測定保留3件も解消し、24件すべてで値を得た。ただし新指標の参考値0.034905、偽画像0.022628、差0.012277は既存の0.02未満であり、参照差検査を保持した採点では全件feature_reference_too_closeとなった。この経路の総合順位は改善していない。

0.02は新指標の測定誤差から校正した閾値ではない。今回、閾値を下げたり偽画像を替えたりして通過させていない。測定値による診断は膨らみの識別、参考画像だけの診断は分布の類似性を調べるものとして区別し、元の採点契約を満たす本番結果とは扱わない。全方式で元の資格順序と単語80%・画像20%を保ち、参考差保留では単語点を維持した。正式合格に必要な強適合4件に対して3件しかなく、ineligibleも維持する。

準備済みuv offline環境で合成13件成功、既存形状/領域/属性関連54件を併せた67件成功（3.05秒）。直線/台形、強弱、微小片、穴、複数物体、傾き、位置/倍率、片側突出、過大な膨らみとの非一致、空/切れたmaskを確認した。実験用の数値検証であり、production変更のRED/GREENやattested reviewとは表現しない。4方式すべての24件性・資格順序・総合点・順位一致率を別scriptで検算し、入力・label・実験source・使用するproduction sourceのhash不変を確認した。

26maskを読込済みの状態で21回計算し、従来の滑らかさ中央値0.0442秒、新方式0.1934秒、差0.1493秒。新方式p95は0.1990秒。import・画像読込・モデル推論・画像生成は含まず、本番iGPUや全E2Eの時間ではない。モデル再推論/外部通信/credential利用/検索/画像生成/委託UIは0回。

記録は /home/products/bonsai-test-logs/20260910-bulge-eval-01/。RESULT.mdに全24件の比較、quality-summary.jsonに全指標、measurements.jsonに全測定値と分布、timing.jsonに21回の時間、各script・test・argv/exit・固定hash・検算結果を保存した。production codeと依存を変更していないため全体pytestを再実行せず、関連testと文書リンク/差分検査を実施した。未commitの実験・文書更新であり、本番へ統合済みではない。

## 183. 膨らみ参照差の閾値を校正・検証（2026-09-10）

利用者の閾値検証指示に基づき、EXEC-108の実験用測定器を変更せず、48合成形状×20変形で測定値の揺れを校正した。変形は回転±3度、倍率0.9/1.1、境界±1/2px、最大変位2pxの平滑ノイズ12種。商品label/順位/現在の参照差は校正に使用せず、計算式・seed・合格基準・source hashを事前固定した。合成の誤差であり、実切出しモデルの誤差分布とは扱わない。

960観測の絶対誤差99percentile0.005318の2倍という事前規則から、候補閾値0.010636を校正artifactに固定した。別seed・別パラメータの48形状で同形状の誤分離は1/9120組（0.011%）、膨らみ振幅0対32pxの明瞭な差の正方向検出は960/960、測定取得960/960となり、誤分離1%以下/検出90%以上/取得95%以上の基準を満たした。既存0.02も誤分離0・差検出100%で同基準を満たす。同じ形状族を使い、9120組は48形状の20変形間で相関する比較であるため、独立9120商品や99%信頼区間と表現しない。

保存済み参考対の名目差は0.012277で候補値を超えるが、各20変形の全400組の最小差は0.005680。閾値を満たすのは233/400（58.25%）で、最小差が閾値以上という事前の安定性基準に不合格だった。膨らみの大小方向は400/400で保持しており、逆転が起きたわけではない。人工変形の通過割合を本番成功率には読み替えない。参考40/40の測定を取得した。

商品側は480変形中440で測定を取得し、元24枚はすべて測定できた。変形時の未取得40件中、21件は1.1倍拡大、12件は回転で発生した。切出し済みcanvasの端への接触等を含むストレス試験であり、本番欠測率を測ったものではない。境界変更/ノイズでも保留が残る。

既存の参照距離による点数式と資格順序・単語80%/画像20%を保持し、同24商品への影響を診断した。候補閾値を名目差だけへ適用すると24件採点、目視順位一致67.6%、nDCG@10 0.852、強適合3商品が上位3件となる。既存0.02または候補閾値と安定性基準を組み合わせる場合は全件画像採点保留で、順位一致47.3%、nDCG@10 0.290。閾値を通過させることを品質合格とせず、productionの閾値は変更していない。EXEC108の膨らみ量だけの診断85.6%とは式が異なり、今回の参照式では飽和・同点も生じる。

実験用7件と既存測定/領域/属性関連67件の計74件成功（3.07秒）。quantile境界、閾値同値/不足、逆方向/同値参照/欠測、組数、変形の再現性を確認した。別scriptで校正quantile・誤分離数・参照全組合せ・全24順位・資格順序・総合点・固定hashを検算した。production/依存不変のため全体pytestは再実行せず、関連testと文書検査を実施した。未commitの実験と文書更新であり、統合済み変更ではない。

全数値応答・校正/検証/stress・順位3方式・argv/exit・固定source/入力hash・検算・RESULT.mdを /home/products/bonsai-test-logs/20260910-bulge-threshold-01/ に保存した。外部通信・credential・検索・画像生成・モデル推論・委託UIは0回。参照画像対の改善、実切出し誤差の検証、未知商品の品質、本番iGPU性能は未確認である。

## 184. 膨らみの生成指示と参照採用前検査を改善（2026-09-10）

利用者の改善指示に基づき、偽画像の表面が角張っても胴体の膨らみが残る問題に対処した。counterfactual_cloudflare_request.pyのprompt契約をv2にし、確認済みside_bulge/directionから左右輪郭のoutward_bulge/straight_sidesを指定する。対象条件の偽画像だけ反転し、他条件の偽画像では元の膨らみを維持する。高さ・上下端幅・別部位・接続位置を保ち、模様/面取りだけで否定しない指示を追加した。

bulge_measurement.pyにEXEC108の測定器を参照検査用として移し、bulge_reference_quality.pyで各参照20変形・19/20以上の取得・全組合せ最小差0.02以上を検査する。candidate_flow.pyは派生画像生成後・最終画像承認発行前に検査し、不合格ならreference_quality診断で停止する。抽出器未設定・失敗・binding不一致も安全な数値診断にする。生成済み利用量は成功のまま保持し、自動再生成しない。既存の明示再生成で新しい確認へ戻れる。

live runnerは既存の領域抽出器を参照検査へ渡し、reference-quality.jsonを保存する。商品採点の測定器・閾値・ranking/history profileは変更せず、旧履歴を再採点しない。新しいpromptと参照品質policyのdigestを画像要求bindingに含める。旧prompt要求をそのまま再開しない。参照切出しのモデル処理は商品評価と未共有であり、追加呼出しになる。

最初のREDは生成要求の輪郭指定不足2件と未実装module3件。後者は挙動の失敗再現とは扱わない。参照測定器なしでも最終承認を発行してしまう挙動を追加REDで再現し、同じ6件がGREENとなった。追加4件で名目差だけ十分な不安定参照、抽出binding/例外を検証した。関連試験では旧不正参照2例が早期停止する仕様差を確認し、検索0・CLIP0・履歴なし・固定診断を検証する期待へ変更した。正常参照/非観測条件の経路を維持した。

全体初回は3 failed/3018 passed。旧live runnerのprompt v1固定と、準備失敗fixtureに参照品質propertyがない場合の診断出力を修正し、最終全体offline3021 passed/20 skipped/30 deselected、99.37秒。RED/GREENと全試行・argv/exitを保持した。未commitの実装であり、attested reviewや実サービス成功とは表現しない。

保存済みの元参照対を新検査で評価すると、変形後の最小差0.005028で不合格。元の参考maskに対して左右側面を直線にした合成maskを比較すると最小差0.032108となり、同じ0.02基準を通過した。2組の数値検査は1.512秒で、画像生成/モデル切出しの時間を含まない。合成maskは理想化した対照であり、Cloudflareがその輪郭を生成した証拠ではない。

実生成用に既存の承認済み参考画像と新しい偽画像要求1件をprivate領域へ準備した。初回準備では512pxの参照を直接渡して上限511pxの既存入力検査に拒否されたため、実経路と同じ_desired_reference_pngによる正規化を利用した。外部送信は0回。既存の入力上限は変更していない。fixtureで一度だけの送信・正規化artifact・利用量記録・再送拒否を確認した。Cloudflare公式料金は入力1tile 0.000059 USD＋出力1tile 0.000287 USDで、今回の1件は0.000346 USDを想定する。

記録は /home/products/bonsai-test-logs/20260910-reference-improvement-01/。実装/source/test hash、全体ログ、reference-comparison.json、prepared-request.json、prepared-scope.jsonと専用診断scriptを保存した。実生成は条件を提示して承認待ちであり、現時点の新画像生成・credential利用・商品検索・モデル再推論は0回。実画像品質の改善、未知商品、iGPU性能は未確認。

## 185. 承認済み偽画像1枚を実生成し参照品質を検証（2026-09-10）

利用者の明示承認後、準備済み要求とproduction/test 9ファイルのSHA256、既存参考画像のSHA256、未送信状態を確認し、Cloudflare flux-2-klein-4bへ偽画像1件を送信した。既存APIキーを利用し、retry0・180秒上限・検索0の承認範囲を維持した。生成は7.715秒で成功し、正規化PNGと秘密値を含まない数値結果を保存した。利用量予約は1件・1call・succeeded。想定0.000346 USDは料金見積りであり、ledgerのcost_microusd 0を無料または実請求額の証拠にしない。

既存の参考画像と新偽画像を固定ローカルCLIPSeg＋MobileSAMで切り出した。runtime SHA256は従来と一致し、双方の本体maskを取得した。切出しと参照品質検査は48.444秒、worker内診断39.710秒、子process peak 1393564 KiB（約1.329 GiB）。生成と検査の計測区間の和は56.159秒で、ユーザー確認・起動・記録を含む実検索フロー全体の所要時間ではない。

参考の名目膨らみ0.034905に対し新偽画像は0.006948、名目差0.027957。各20変形と元maskを含む21×21の441組すべてが0.02以上で、最小差0.024392、判定passedだった。同じ判定器による旧対の最小差0.005028から改善した。別の算術検算で全42測定値、全441差、閾値判定、元参考の測定値との完全一致、source不変、生成1回の利用量を確認した。人工変形の全組通過を未知画像での成功率と解釈しない。

assistantの目視では新画像の胴体側面がほぼ直線となり、旧偽画像のような表面の角張りだけの変更ではなく、外周の膨らみが減っている。白い外観・右側の取っ手・灰色の背景は概ね保たれるが、他条件の厳密な一致や人間による画像採用の承認とは扱わない。両maskは取っ手を除いた本体を抽出し、参考mask上端には小さな内部欠けが残る。

保存先は /home/products/bonsai-test-logs/20260910-reference-improvement-01/。counterfactual-new.png、generated-reference-mask-0.png/1.png、generated-reference-quality.json、live-summary.json、live-usage.json、live-validation.json、各実行log/argv/exitを保存した。生provider応答・認証情報は保存しない。既存承認・履歴は維持し、画像採用や検索開始は行っていない。production codeは前回全体offline3021件成功時と同じSHA256のため全体testを反復せず、文書とdiffのgateを再確認する。全24商品へのランキング改善、未知カテゴリ、実Bonsaiの測定種別選択、iGPU性能は引き続き未確認。

## 186. 新偽画像で全24商品の順位を比較（2026-09-10）

EXEC111として保存済み24商品のmask、資格条件、単語点、EXEC107のassistant目視gradeを固定し、旧/新偽画像×現行滑らかさ/現行膨らみ/改良双方向膨らみの6方式をoffline再計算した。source・入力・policyのSHA256を実行前に固定し、閾値0.02、資格順序、単語80%・画像20%、保留時単語点、同点処理を変更していない。測定種別は診断上の明示指定であり、実Bonsaiの解釈や既存画像の採用承認を変更していない。

品質指標は資格適合19件中、異なるgradeの111組を比較し、同点は0.5で数えた。現行膨らみは旧参照の全件保留（順位一致47.3%、nDCG0.290、top5強適合0）から、新参照で21/24件採点、63.1%、0.582、強適合2へ改善。改良双方向膨らみは新参照で24/24件採点、79.7%、0.859、強適合3となり、item-12/item-13/item-23が上位3位となった。新参照の最小差0.024392も前回の結果と一致した。旧参照は採用前検査に不合格のため、旧参照の順位は新フローが返す結果ではなく保留時の配点を比較する診断である。

滑らかさのままでは新参照で順位一致36.9%→43.7%となる一方、nDCG0.336→0.242、top5強適合1→0で、固定した比較改善基準を満たさない。新偽画像だけを替えれば必ず良くなるわけではなく、評価する意味を膨らみに合わせる必要がある。改良測定は参照検査にのみ接続済みで、商品rankingには未接続。今回production codeの変更は0件。

現行膨らみでは資格適合の画像採点7商品が満点で同点となり、grade0も上位に残る。微小な分離片による3件の測定失敗も維持される。改良測定では全件を測定できるが、負例以下の画像点を最低点へ丸める式により資格適合12件が総合0.8で同点になる。以前の単純な膨らみ量順85.6%と今回の79.7%は別方式なので、同じ方式の改善とは表現しない。独立した正解ラベルではなく既知developmentデータで、正式基準の強適合4件以上に対して3件しかなくineligible。79.7%も80%基準には未達。

全6方式144件の数値と順位を保存し、別scriptで参照差・配点・資格順序・111組・nDCGを検算した。旧滑らかさ全順位/点数、旧双方向膨らみの一致率、前回参照品質、全入力/source hashが再現した。関連53 testが6.80秒で成功。数値再計算3.058秒で、model推論・画像生成を含まない。production不変のため全体pytestは反復せず、関連testと文書/diff gateを確認した。ログ・argv/exit、summary.json、ranking-*.json、audit.json、全24件を載せたRESULT.mdは /home/products/bonsai-test-logs/20260910-new-reference-ranking-01/ に保存。追加の外部通信・credential・画像生成・検索・Bonsai/CLIP/領域モデル推論・委託UI操作は0回。既存承認・履歴を変更していない。

## 187. 未使用商品テストの取得要求と基準を固定（2026-09-10）

利用者の未知商品テスト指示を受け、手元の候補assetの用途を確認した。case1〜3、image-holdout001〜005と直近の24件は使用済みdevelopmentで、新しい独立holdoutとは扱えない。EXEC112で「コーヒーカップ」最大24件を1task取得する要求、旧24件との同一商品/画像除外、採点前の目視grade固定、現行/改良膨らみの比較を準備した。参照対・閾値0.02・配点・固定基準は維持し、母数不足でも追加検索はしない。

repository外のacquire.pyは準備modeでcredential/通信なしに既存CandidateSearchの要求を作り、実行modeではsource・要求・参照のSHA256を照合して開始markerを作る。既存の有界Outscraper transportとImageProxyServiceを使い、1task/50poll/24画像/1800秒/retry0に制限する。生応答はメモリ内だけで正規化・単語点・資格条件を求め、保存は匿名ID・identity/画素digest・数値・状態と正規化画像だけ。同一商品を画像取得前、同一画素を保存前に除外し、近似画像と目視gradeの確認は採点前に別工程とする。

offline fixture3件が1.10秒で成功。単発取得、商品/画像重複、開始済み再送拒否、provider例外の無再試行とraw例外非保存、固定要求変更時のcredential読込前拒否を確認した。実行要求・固定基準・除外digest・source hash・log/argv/exit・RESULT.mdは /home/products/bonsai-test-logs/20260910-unseen-ranking-01/ に保存。実API、credential、新しい商品画像、領域モデル推論は0回。公式公開料金ページだけを確認し、Outscraper2USD/1000商品から24件0.048USDを見積もった。AGENTS.mdの各live実行前の明示承認規則に従い、具体的な要求を提示する。現時点では未知商品の精度を評価した結果はない。production code、既存承認・履歴、委託UIは変更していない。

## 188. 未使用20商品の実画像で膨らみ評価を検証（2026-09-10）

利用者の明示承認後、EXEC112の固定hashと未開始状態を確認してprepared requestを1回実行した。Outscraper1task・6pollsで24商品を取得し、同一商品3件を除いて21画像をm.media-amazon.comから取得した。再試行0、取得191.699秒で承認範囲内。既存134画像とのpHash比較では距離5以下の追加重複はなく、目視で旧item-00と同様の黒い蓋付きマグunseen-04を保守的に近似重複として除いた。異なる画像/商品識別子でも見た目が同じ場合の完全なSKU同一性は保証しない。

残る20件の目視labelをモデル推論前にhash固定した。明瞭な胴体両側の膨らみ0件、弱い曲がり/テーパー11件、直線的6件、判断不能3件。底へ向かう丸みや単純テーパーはgrade1、両側の胴体の張り出しをgrade2とし、箱・遮蔽・collageの不確実性を保持した。基準を満たす正例がないため正式評価はineligibleで、追加検索やlabel変更で正例を補っていない。assistant目視であり独立した人間の正解ではない。

既存参照maskを固定し、20枚を既存runtime SHA256のCLIPSeg＋MobileSAMへ1回通した。切出し289.139秒、参照検査と採点を含め290.221秒、子process peak1417604KiB（約1.352GiB）。各方式の画像採点は17/20件。新参照品質は引き続きpassedだが、これは商品側の対象部位の正しさを保証しない。取得と評価の計測区間の和481.920秒は約8分で、目視・準備・監査を含む全体待ち時間ではない。

価格条件はconfirmed7件・uncertain10件・contradicted3件。単語一致点は全20件で0だった。現行/改良の総合順位一致はconfirmed7件中の異grade6組で8.3%→66.7%、nDCG@10は0.798→0.984。全目視可能17画像の異grade66組の補足画像比較では、両者採点可能54組、欠測12組を不正解として37.1%→65.9%となった。これは弱い曲がり/テーパーと直線の区別であり、強適合商品の検索品質や前回24件の79.7%との同一母集団比較ではない。正式基準の80%と強適合4件を満たしたとは扱わない。

unseen-21は本体でなく上面のコーヒーだけを218×45pxの楕円として切り出し、両測定器が画像点1.0を付けた。overlay-21.pngで取り違えを目視確認した。unseen-15は直線的本体に取っ手を含むmaskとなり、現行は満点で1位、改良は画像点0で5位だった。unseen-12は取っ手などの分離成分が約3.03%を占め、改良の主成分99.5%基準により保留となった。unseen-06も主成分99.15%で保留。箱だけのunseen-22は空maskとなり両者保留である。未知商品では測定器だけでなく対象部位の同定・可視性の検証が必要と確認した。

単語一致0の原因を実商品名なしで断定しない。商品本文は保存していないため、合成の「コーヒーカップ」等では固定token化が動くことだけを別診断へ保存した。old contact作成の初回はsystem PythonにPILがなく失敗し、準備済みuv環境で回復した。これは外部取得/モデル推論の再試行ではない。

全40行の数値/配点/順序、6組の順位一致、nDCG、coverage、評価不適格、source/画像/label hash不変とAPI回数上限を別scriptで検算した。production code不変のため全体testは再実行せず、数値検算と文書/diff gateを実施。実行script、全数値、mask、目視固定、overlay、取得/評価/検算のlogとargv/exitは /home/products/bonsai-test-logs/20260910-unseen-ranking-01/ に保存した。生provider応答・商品本文・商品URL・ASIN・credentialは保存していない。画像生成、Bonsai、CLIP埋込み、委託UI、既存承認・履歴の変更は0回。今後この20件を独立holdoutとして再利用しない。


## 189. 汎用外観採点へ変更し保存済み44商品の実CLIP再評価（2026-09-10）

利用者の未知カテゴリ優先の指示に基づき、candidateの既定を全体外観類似度へ変更した。変更は未commit。relative_image_rankingにappearance-image-v1/whole_image_similarityを追加し、candidate_completion/flow、表示履歴、実runnerへcandidate-appearance-v1を接続した。Bonsai要求はmeasure/direction=nullとし、原文の視覚条件・対象句を保持する。部位抽出・専用測定・参照輪郭検査は明示的旧modeでだけ使う。参考画像と偽画像の人間確認、資格条件順、単語80%/画像20%、欠測時の単語点、旧履歴を保持した。

新規5件のREDは領域処理の必須呼出し、新batch未実装、測定選択schemaで失敗した。実装後の関連109件成功。全体初回は3025 passed/1 failed/20 skipped/30 deselectedで、旧MobileSAM接続testが旧方式を暗黙に期待していた。image_score_mode="relative"を明示して旧動作を検証し、全体3026 passed/20 skipped/30 deselected（105.59秒）。後から追加した画像欠測/参照近接2件を含む関連24件も2.53秒で成功。新方式の新旧profile混在拒否・JSON復元・画像確認・SQLite履歴再読込を確認した。新規testは計7件。

固定した保存済み44商品と同じ参考/新偽画像を実ローカルONNX CLIPで再採点した。初回の実画像runnerは入力階層準備ミスで対象0件となり、推論0回の試行を保存。20/24件の事前assertと入力階層を修正して実44件を完了した。採点後の重み/閾値調整、再ラベル、再検索はなし。

直近20商品は17→20件採点。画像点のみと既存形状gradeの対比較66組は37.1%→56.1%、価格適合7商品内の6組は8.3%→91.7%、nDCG0.798→0.993。強膨らみ0件であり、6対の改善を全体の精度改善とは扱わない。以前24商品は21→24件採点だが、画像点の171対は59.4%→30.4%、価格適合19商品内111対は63.1%→24.3%、nDCG0.582→0.151。改良両側測定の上位3件だった明瞭な膨らみは9/14/15位になった。全体の類似度への変更で採点範囲は広がったが、膨らみの識別品質は大きく低下した。

unseen-21は旧切出しでコーヒー表面へ画像1.0、新方式は全体外観0.3481。これは部位誤認の修正ではなく部位測定を使用しない結果である。箱だけのunseen-22も0.3482となり、対象不在の自動検知は未達。画像点は部位/仕様の一致を証明しない。旧labelはassistantの形状gradeで外観類似の独立正解ではなく、強例数も正式構成基準未達。未知カテゴリ精度の検証は未実施。

実行範囲: CPU1threadの固定CLIP ViT-B/32、20+2画像21.914秒、24+2画像23.599秒、延べ48画像/13batch。通常test同時実行の計測でiGPU/単独latencyとは区別する。ネット接続を禁止し、外部API/検索/画像GET/画像生成/Bonsai/CLIPSeg/MobileSAMは0回。実データの資格/単語点は数値だけ再利用し、商品本文/ASIN/URL/生応答を複製せず匿名の商品contractで画像評価器を通した。実サービスE2Eや元履歴更新は行っていない。

保存はrepository外の20260910-appearance-ranking-01。RESULT.mdに全44件の点/順位/元画像リンク、各encoder応答、image-batch、summary、初回失敗、RED/GREEN/全体ログ、argv/exit、入力/code/label hashを記録。別scriptで全点・順位・指標・埋込みcosine・参照差を検算して一致した。汎用点を品質合格とはせず、カテゴリ横断評価と形状精度の低下をISSUESへ残す。

EXEC-113最終静的検証はRuff/format/lock/Markdown/diffすべて成功。委託フロントエンド、commit/push、実サービスの新規実行は対象外のまま完了した。


## 190. SigLIP 2を保存済み44商品で実ローカル検証（2026-09-10）

利用者の試用指示によりgoogle/siglip2-base-patch16-224を、revision 75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2へ固定して試験した。7つの公開資材1,539,453,393bytesをHugging Face/配信CDNから認証なしで26.979秒で取得し、model.safetensorsの公式SHA256と照合した。通常repo依存や既存環境は変更せず、準備済みmobile-sam-eval-01のtorch2.6.0+cpu/transformers4.57.6を使用。GemmaTokenizerFastを使い、sentencepiece/protobufの追加は不要だった。

EXEC113の同じ20/24商品と参考/新偽画像、既存形状grade・資格・単語点を再利用。肯定/対照の英語条件文1組と計算式を推論前に固定した。画像参照方式と条件文方式を分け、重み混合・文言調整・再ラベルはしない。SigLIP公式224×224 bilinear resize/mean/std0.5前処理を使用し、CLIPの縦横比維持+余白前処理と異なることを記録した。モデル単体の因果比較ではない。

画像参照方式は全44件採点。画像点と既存形状gradeの順位一致は直近56.1%→65.2%（66対）、以前30.4%→63.7%（171対）。事前に固定した両集合各+5pt、nDCG/上位5強例数非低下、採点75%以上を満たした。価格適合群の総合順位一致は直近91.7%のまま（6対）、以前24.3%→57.2%（111対）。nDCG0.993→1.000、0.151→0.718。以前の強膨らみitem-23/12/13は9/14/15位から1/4/9位へ改善した。過去の専用両側測定の画像一致86.0%を上回ったわけではない。

条件文方式も全44件採点したが、画像順位一致は直近48.5%、以前68.4%。以前の強例は上位5件に3件入るが直近集合では悪化し、両集合での比較基準は未達。固定した1組の条件文の結果であり、文言全般の優劣やBonsaiの条件生成品質は評価していない。raw差も保存し、画像参照方式の直近ではclamp前63.6%/後65.2%となった。0点同点化による半点を新たな識別力とみなさない。

推論は通信禁止process、CPU2threads、float32で1回。model読込2.506秒、46画像（商品44+参照2、12batch）14.842秒、条件文2件0.319秒。hash確認/importを含むprocess全体25.410秒、peak RSS1.419GiB。model全体375,187,970params、vision側92,884,224params。CLIPとはruntime/threads/session再利用/処理枚数が異なるため速度倍率は主張しない。iGPU性能は未測定。

数値fixture7件、既存candidate画像関連23件が成功。全88採点のcosine/正規化/総合点/資格順/順位/指標を独立scriptで再計算し、入力・モデル・code・label SHA256一致を確認した。試験runnerと資材はrepository外20260910-siglip2-ranking-01へ保存し、RESULT.mdに全44商品の2方式の点数と順位、全埋込み応答、policy、runtime、audit、取得/推論/testログとargv/exitを残した。productionコード不変をhashで確認し、全体pytestは繰り返していない。torch_dtypeの非推奨警告は記録したが実行失敗はなし。

公開モデル取得と資料閲覧だけが外部通信で、画像/検索文/credentialの送信、推論API、商品検索/画像GET/画像生成/Bonsai/委託UIは0回。モデル試験は成功したが本番接続は行っていない。形状gradeは過去のassistantラベル、強例0/3件の構成不足を維持し、正式品質はineligible。未知カテゴリ品質を確認したとは扱わない。

EXEC-114の最終Markdown検査は16文書/1657 local links/1243 anchor linksで成功し、git diff --checkも成功。文書変更は未commit。


## 191. SigLIP 2の未知商品評価を準備（2026-09-11）

利用者指定の目視順位一致60%以上をEXEC115へ固定した。既存44商品の再使用を避け、同じカップ条件で新しい商品を取得する準備を行った。モデル点を見ないassistant目視の順位群と厳密なペア一致を使い、モデル同点/欠測は不正解、目視同点/判別不能は別報告とする。独立した人間評価や未知カテゴリ評価とは区別する。

repository外20260911-siglip2-unseen-01へ既存取得runnerを再利用し、既知identity/pixel・155画像のpHash比較基準、固定model/参照、policy/source hashを準備。取得fixture3件と60%境界・同点/欠測/不正入力/資料不足のfixture8件、計11件が0.88秒で成功した。推論runnerは構文確認のみで未実行。新規商品の取得はAGENTSが求める当該外部実行への明示承認待ち。productionコードと過去結果は不変。文書変更は未commit。


## 192. SigLIP 2の未知商品21件で目視順位一致75.8%（2026-09-11）

利用者が承認した新規取得を1task/4polls/24商品まで実行。過去identity重複2件を除いて画像22件取得、125.361秒。目視で同一の単品/3個組画像1件を追加除外し、21商品を固定した。155既知画像のpHash比較と過去44商品の目視比較を実施し、形状による選別や追加検索はしなかった。

SigLIP点を見る前にassistantが胴体の膨らみで同順位群を固定した。21商品210組中、目視同点82組を除いた128組について、97一致/31逆転、モデル同点/欠測0。75.8%で利用者指定60%以上と資料12商品/30組を通過。モデル全21件採点、raw差の一致率も75.8%。目視最良はモデルも1位だが、目視3–4位の1件がモデル9位、目視5位が16位になる誤順序も残った。

初回workerはsocket.socketを関数へ置換したため、torchからsslをimportした段階でTypeError。モデル読込/埋込み出力前の失敗を保存した。別inference-02でsocketクラスを保持したconnect/connect_ex遮断へ修正し、import正常と3接続経路遮断を検証してから再開。ラベル/画像/モデル/採点式は変更せず、採点完了した実モデル試行は1回。

固定SigLIP 2 Base/公式224resize、CPU2threads/FP32、21+2画像6batchの前処理/推論/応答保存7.340秒、モデル読込0.105秒、process15.399秒、peak1.417GiB。実iGPUは未検証。画像生成/Bonsai/CLIP/外部推論APIは0回。全21点と順位、128対、モデル資材/参照/label/production hashを独立scriptで検算し一致した。

証拠はrepository外20260911-siglip2-unseen-01/RESULT.md、labels、inference-02の全埋込み/ランキング/summary/audit。初回失敗、回復診断、取得と推論の全ログ/argv/exitを保持。準備11fixtureは既報、production不変なので全体pytestは反復せず、今回の実評価/検算/文書gateを実施。これは同じカップ条件の未知商品に対するassistant目視順位評価であり、独立人間評価、未知カテゴリ品質、本番総合順位、production E2Eの合格ではない。code/model/既存履歴/委託UIに変更なし、文書は未commit。


## 193. Candidateの既定画像評価へSigLIP 2を接続（2026-09-11）

利用者の「本番へ組み込め」に基づき、EXEC115で指定60%を通過した参考画像方式をcandidate backendの既定へ接続した。SigLIP 2 Baseの固定revision・7資材hash・別Python環境の固定versionを使用し、通常依存へtorchを追加していない。画像生成方式やBonsai用途は変更せず、正画像と偽画像の承認後に768次元の全体外観比較へ進む。資格条件順、タイトル80%/画像20%、欠測時の単語点を維持した。

新adapter/runtime、siglip2-appearance-image-v1、candidate-siglip2-appearance-v1、counterfactual-siglip2-appearance-v1を追加。旧512次元CLIPと混ぜず、JSONとSQLite schema5履歴へ保存する。旧履歴は読めるまま保持し、明示CLIP選択も可能。保存済み旧承認を使うcandidate_search_retryはCLIPのままとする。CLI既定はsiglip2で、準備済みモデル資材と独立Pythonを明示指定する。workerは通信を遮断し、credential環境変数を継承せず、600秒上限・再試行なし。失敗時にCLIPへ自動fallbackしない。

新testのREDから実装し、関連初回の旧CLI引数不足2件とretry呼出しの構文誤り7件を修正して92件成功。全体初回3044件成功後、資材読み取りのatime変化を改変と誤判定する可能性に対しRED回帰を追加。内容hashとinode/size/mtime/ctime等の検査を保ち、atimeだけを除外した。最終関連26件成功、最終全体3045 passed/20 skipped/30 deselected、122.06秒。次元/runtime混在拒否、複数条件のminimum-positive、欠測/近接参照、不正応答/timeout、既定選択、画像承認→ランキング→JSON→SQLite履歴をofflineで確認した。

保存済み21商品と既存正/偽画像を本番用LocalSiglip2ImageEncoderと商品評価器へ通し、試験runnerの全21点との差が0.0、順位完全一致となった。最終実行は31.127秒、子process peak803200KiB、CPU2threads/FP32、参照と商品でworker2回（内部batch4）。全体回帰と同時実行の計測で、単独性能やiGPU性能を示さない。全埋込み応答、入力hash、型付き画像batch、全点比較、時間、argv/exitをprivate 20260911-siglip2-integration-01/final-realへ保存した。これは保存済み画像の接続回帰であり、新holdoutや実provider E2Eではない。

変更差分・初回失敗を含むtestログ・最終gate・RESULT.mdは同private directoryへ保存。外部API、検索、画像生成、モデル/依存downloadは0回。委託UIには接続せず、既存未commit差分を維持した。未知カテゴリ、独立人間評価、iGPU性能、本番総合順位の追加検証は残る。commit/pushは未実施。


## 194. 次期フロントエンドを自前開発へ変更（2026-09-11）

利用者の「納品待ちではなく、こちらでフロントを作成したいので、まず文書を書き換えて下さい」に基づき、次期画面をこのリポジトリで自前開発する方針へ変更した。2026-09-02の外部納品待ち境界を解除し、AGENTS.md、DEVELOPMENT.md、README.md、SEARCH-FLOW.md、FRONTEND.md、BACKEND.md、REQUIREMENTS.md、NEXT-STEPS.md、GOAL.md、ISSUES.md、CHANGELOG.mdを同期した。既存の未コミット差分を保持し、この作業も未コミットである。

納品確認を着手条件にする記述と納品一式の準備要求を更新し、画面設計・状態/API契約・実装方式の整理、合成データでの実装と操作確認、ローカルAPI接続を後続作業として登録した。過去の個別EXECと作業記録は当時の判断・検証範囲として保持する。検索実行のローカル専用・単一host・単一process・worker 1本、SigLIP 2既定、Bonsai用途制限と実サービス利用の承認規則を維持した。

検証: `uv run --frozen --offline --no-sync python tools/check_markdown_links.py` と `git diff --check` は成功。現行文書の納品待ち記述と作業開始時点からの文書差分を確認した。変更は文書のみのためPythonの機能テストとRuff/lock検査は未実行。フロントエンドの実装・起動・画面確認・API接続、実サービス検証、依存取得、外部送信、commit/pushは行っていない。


## 195. React + StyleXのUI仕様とオフラインモック要件を正本化（2026-09-11）

利用者が承認した文書更新計画に基づき、次期UIの実装をReact + StyleX、Figmaをレイアウトの参考とし、FRONTEND.mdへ視覚統一契約とオフラインモック要件を記載した。Noto Sans JP、本文・補足・h1〜h4のサイズ、6桁表記の配色、ウィンドウ角丸15px、ボタン角丸100px・全種別同寸法・中央揃え・短い文言・主要操作と危険操作の配置、ホバー色を固定した。全ボタン共通の幅・高さの数値は利用者の選択どおり後続設計へ残した。

上部中央の段階バーと上半身の現在位置アイコン、商品調査内の完了チェックと現在工程の丸を分けた。画像生成の右上から左下への光の波は1.5秒間隔、処理中の丸は1.5秒周期、生成中・処理中の末尾の点は0.5秒間隔とした。SEARCH-FLOW.mdの長いボタン文言と紫・緑・赤・黄色の状態表示を同期し、FRONTEND.mdの次期画面一覧に残っていた4方向画像の表示も現行の参考1枚と条件別偽画像へ合わせた。

任意入力を確認画面に保持し、固定の合成条件・商品・画像で結果表示まで操作するモックを実装予定として定義した。画像なし、戻る、二重操作防止、生成・調査中表示、共通React部品・StyleX、ローカルのフォント・画像、実バックエンド・Bonsai・外部API・credentialへの非依存と自動接続なしを明記した。REQUIREMENTS.mdに残っていた納品待ち制約を訂正し、UI-017〜UI-020を未実装として追加した。AGENTS.md、README.md、NEXT-STEPS.md、GOAL.md、DEVELOPMENT.md、BACKEND.md、CHANGELOG.mdも同期した。

検証: 指定値・色の網羅性、6桁表記、旧文言の除去、要件ID、過去の個別計画・作業記録・マージ済み変更履歴の保持を確認した。`uv run --frozen --offline --no-sync python tools/check_markdown_links.py` と `git diff --check` は成功。文書だけの変更のため、Python機能テスト・Ruff・lock検査・ブラウザ検証は未実行。UI・モックの実装、起動、API接続、Figma編集、外部通信、依存取得は行っていない。既存の未コミット差分を保持し、今回もcommit/pushは未実施。


## 2026-09-11: 既存変更の段階的なGit反映

利用者のcommit・push指示に基づき、既存差分を文書・runtime設定、次期検索基盤、診断runner、画像評価fixtureの4段階へ分割した。文書・runtime設定は `c447bac`、次期検索基盤は `20b218f`、診断runnerは `cbc0799` でmainへ反映した。

準備済み環境で `uv run --frozen --offline --no-sync pytest -m 'not live_api' -q` を実行し、3,045 passed・20 skipped・30 deselectedを確認した。lock整合、Ruff、format、Markdownリンク、diff検査も成功した。実provider、モデル推論、画面起動、外部API検証は実行していない。

固定CLIPモデル3ファイルと、検索文・商品情報を含む原本CSVおよびcase2・case3のExcelはローカルに保持し、`.gitignore` へ登録した。画像評価用の固定画像・manifest・数値結果は回帰テストと併せて管理する。過去の各作業にある「未コミット」は当時の状態として保持する。

Git管理ファイルだけの別チェックアウトでも、同じオフラインテストが3,045 passed・20 skipped・30 deselectedで成功した。lock整合、Ruff、format、Markdownリンク、全コミット差分の空白検査も成功し、ローカルに除外したモデル・CSV・Excelへ通常gateが依存しないことを確認した。


## 196. React + StyleXの画面とオフラインモックを実装（2026-09-11）

文書化に続く利用者の実装指示により、[EXEC-117](GOAL.md#exec-117-react-stylexのオフライン画面) で `frontend/` を新設した。React 19・TypeScript・Vite 8・公式StyleX unpluginとローカルNoto Sans JP、合成SVGを使う。Figma node 59:22の構成を参照し、配色・文字・角丸・176×48pxの共通ボタン・進行表示・生成/調査アニメーションはFRONTEND.mdの指定を適用した。

任意入力の保持と固定条件の区別、条件編集と反映、参考画像1枚での停止、明示了承後の比較画像、最終確認、5工程の商品調査、固定商品12件と0件結果、1〜30件の表示切替を実装した。商品情報の一致・確認できない・合わないを合成データとして表示し、詳細はカード内で開く。戻る・二重操作防止・15分の承認期限・生成上限・中止確認・画像拡大・モーダルのフォーカス復帰を含む。

履歴はタブ内sessionStorageへ最大30件・30日間保持し、保存失敗時は結果を残して保存だけ再試行する。削除失敗・取消では履歴を残し、保存できていない結果の破棄には確認を挟む。再読込は検索を再実行せず入力画面へ戻り、保存済み履歴を開ける。7種類の固定失敗/0件シナリオをqueryで指定できる。実バックエンド・Bonsai・外部API・credentialと自動fallbackを設けない。

検証: strict TypeScript/Prettier、40単体テスト、production build、Chromium18件成功（18.4秒）。ブラウザ試験では外部originとfetch/XHRを遮断し、ローカル配信だけで両経路と回復操作を確認した。入力・参考画像・結果の画面を目視し、開発serverでもStyleX反映と例外0件を確認した。レビュー指摘から入力画像toggle、生成中参考画像の保持、最終確認の画像表示、削除後復帰、商品詳細の展開を修正し、同一テストのRED/GREENをEXEC-117へ記録した。

初回Python全体gateは新規EXECリンクのanchor誤記で1件失敗（他3044件成功）し、修正した。最終gate結果は下記へ追記する。依存・Chromiumのインストールは利用者承認済みの準備として行い、Figmaと公式StyleX資料を読んだ。実provider E2E・検索品質・API接続は未検証。既存Python・モデル・cacheへ変更を加えず、commit/pushはしていない。

最終gate: lock整合、Ruff check、372ファイルのformat、Python3045 passed / 20 skipped / 30 deselected（74.35秒）、現行文書とfrontend/READMEのリンク・見出し検査、`git diff --check`が成功。UI40件・ブラウザ18件と合わせ、オフラインモックの実装・受入を完了した。


## 197. 主要ボタンの文字色・トグル・白い円枠を修正（2026-09-11）

利用者報告に基づき[EXEC-118](GOAL.md#exec-118-主要ボタンとトグル丸枠の表示修正)を実施した。開発配信だけでreset層の `color: inherit` が主要ボタンの黒文字を上書きしていたため、HTMLで先にreset層を登録した。通常・無効・処理中は白背景/黒文字、ホバーは反転となる。画像利用のチェックボックスを共有トグルへ変更し、ON青・OFF濃灰色・白いつまみ、ラベルとSpaceでの操作、操作中の無効状態を維持した。全体と商品調査の白円枠を2pxのSVG輪郭で描画する。

型・整形、unit40件、build、開発版4件（5.4秒）、productionブラウザ22件（42.3秒）、文書リンク・差分検査が成功。DPR 1/2の円とトグル画像を目視した。再現・修正前後のtest hashと結果はEXEC-118に記録し、以前のproductionのみの18件成功を開発版での成功と混同しない。状態遷移とPython処理の変更はなく、Python機能テストは再実行していない。実サービス、追加インストール、commit/pushは行っていない。


## 198. トグルの動き・角丸・履歴ボタンと危険色を調整（2026-09-11）

利用者指定に基づき[EXEC-119](GOAL.md#exec-119-トグルの動き角丸履歴操作の調整)を実施した。トグルの移動・背景色を240msで補間し、動きを減らす設定では即時に切り替える。角丸半径15px/100pxを維持してsquircleを適用し、進行表示とトグルの丸は維持した。履歴一覧の「削除」「開く」だけ96×36pxとし、同じ行の左と右に離して置いた。3か所の削除は共通部品で危険variantへ固定し、追加指定により危険外枠を `#901010` へ変更した。仕様・要件・開発規則・残作業・変更履歴も同期した。

専用ブラウザテストは変更前4件失敗・1件成功を記録し、同一hashのままGREENを確認した。途中で開発版の削除取消後にフォーカスが戻らない既存不具合を検出した。Dialogのcleanupでcloseしてから起動元へ戻すようにし、StrictModeでのsetup/cleanupを対称にした。

型・整形、unit40件、build、開発ブラウザ9件（5.6秒）、productionブラウザ27件（42.9秒）、Markdownリンク・見出し、差分検査が成功した。開発画面5173番で入力・履歴・削除確認を目視し、例外0件とフォーカス復帰も確認した。未対応ブラウザでのsquircle fallback実表示、実サービスは未検証。Pythonの機能テストは再実行せず、追加の依存取得・commit/pushも行っていない。詳細なRED/GREENとtest hashはEXEC-119に記録した。

## 199. 危険ボタンの文字色とボタン枠の仕様を統一（2026-09-11）

利用者指定により、共通Buttonの危険variantで文字色にも外枠と同じ `#901010` を適用した。通常・ホバー時とも色を維持する。全実行・遷移ボタンの外枠は既存の共通 `borderWidth: 1` を維持し、通常寸法と履歴一覧の小型寸法で1pxを確認した。FRONTEND・REQUIREMENTS・DEVELOPMENT・SEARCH-FLOWとCHANGELOGを同期した。進行アイコンの2px strokeとトグルは変更していない。

既存の表示テストを新仕様へ更新し、実装前の `UI_TEST_MODE=development npm run test:e2e -- motion.spec.ts -g 'every delete action'` はexit 1、1件失敗（赤い文字の期待に白文字）となった。同一test内容の実装後検証は `UI_TEST_MODE=development npm run test:e2e -- motion.spec.ts controls.spec.ts --workers=4` で9件成功（4.8秒）、`npm run test:e2e -- motion.spec.ts controls.spec.ts --workers=4` でビルド版9件成功（3.5秒）。3か所の削除の通常/ホバー色、共通ボタンと小型ボタンの1px枠、主要ボタンの文字色、トグル・円枠・角丸の既存表示を確認した。motion.spec.tsのSHA-256は `73652ad6dcade9e2ad117cfd7e57b886e0e0d23455650689f6e4472ee3807f6a`、controls.spec.tsは `9d854caba2417c3bc17e5e5a4d86edd9606356abadc7e72d8a597b672eb3536a`。

TypeScript・整形、build、現行Markdownリンク・見出し、`git diff --check` が成功した。変更は共通表示1定義と仕様・既存テストの更新であり、状態遷移の単体テストとPython機能テストは再実行していない。実サービス実行、追加依存取得、commit/pushは行っていない。


## 200. 細い外枠の掠れを描画比較して改善（2026-09-11）

利用者の実ブラウザでの報告を受け、[EXEC-120](GOAL.md#exec-120-細い外枠の描画改善)でsquircle、1px線の画素補間、行高から累積する小数座標を調査した。ぼかし・半透明指定はなく、補足の行高24.5px/25.2pxによりボタンやpanelが小数位置へ配置されていた。Chromium 153・DPR1.25で同一ボタン上辺の白線画素ピークがsquircleの145から標準円弧の192へ変わる差を再現した。CSS1pxと色を維持して標準border-radiusへ切り替え、補足14pxの行高を24pxへ揃えた。代表枠の座標・寸法は整数になった。

既存テストを新しい円弧・整数座標契約へ更新し、変更前の1件REDと同一test内容のGREENを確認した。型/整形、build、開発ブラウザ9件（5.3秒）、ビルド版27件（42.7秒）、Markdownリンク・見出し、差分検査が成功。DPR1/1.25/2を比較し、1と2では上辺の白255・1/2物理画素を維持した。仕様・開発規則・要件・変更履歴も更新した。

利用者実機のGPU/ブラウザ固有原因は未確定であり、非整数DPRのアンチエイリアスが消えるとは扱わない。状態モデルとPythonの機能テスト、実サービス、追加依存取得、commit/pushは実行していない。詳細測定とRED/GREENのtest hashはEXEC-120に記録した。


## 201. Chromeの100%表示で残る枠の濃淡を改善（2026-09-11）

利用者からボタンとウィンドウの両方で掠れが残ると回答があり、[EXEC-121](GOAL.md#exec-121-枠線の濃淡を画素で検証して改善)で描画方法を再比較した。DPR1でもCSS borderの角の濃度が薄くなる差を再現した。SVG strokeやoutlineだけでは解消せず、ぼかし0の内側1px輪郭が濃淡の差を減らしたため、共通部品と画面の枠へ適用した。borderを0にした分だけ余白を補正し、色・寸法・内容位置を保持した。

角を法線方向に積分した濃度換算値は、ボタンの最小0.569→0.909px・平均0.855→1.047px、半径15pxの枠の最小0.623→0.803px・平均0.850→0.938pxだった。これは画素濃度の比較量であり幾何学的線幅ではない。新規frame.spec.tsは実装前に1件RED（4濃度検査の失敗）となり、同じhashのまま実装後GREENとなった。直線1px・角の過度な太さも検査する。

型/整形・build、開発ブラウザ10件（5.4秒）、ビルド版28件（42.6秒）が成功した。DPR1/1.25/1.5/2の開発画面を撮影し、例外0件、代表枠の配置・寸法維持も確認した。利用者の実機での解消は未確認。状態モデルとPythonの機能テスト、実サービス、追加依存取得、commit/pushは実行していない。Markdownリンク・見出しと `git diff --check` も成功した。詳細な比較とRED/GREENのhashはEXEC-121に記録した。


## 202. 完了した段階の青背景と更新時のスクロール維持（2026-09-11）

[EXEC-122](GOAL.md#exec-122-完了段階の配色とスクロール維持)で全体段階バーの完了した丸を `#3a83f7` にした。未到達の丸は黒、白外枠と現在位置アイコンを維持する。Appの画面更新時の `scrollTo(0, 0)` を削除し、見出しへのfocusにpreventScrollを指定した。画面更新で先頭へ戻さず、表示可能な範囲でスクロール位置を保つ。

新規ブラウザ回帰は変更前2件RED（丸が黒、scrollY480が0へ移動）、同一hashで変更後GREENとなった。開発版12件（6.1秒）、ビルド版30件（43.1秒）、型/整形/build、Markdownリンク・見出し、差分検査が成功した。処理開始・条件整理完了・画像生成完了の位置維持と見出しフォーカス、戻った際の段階色も確認した。仕様と要件・開発コマンド・変更履歴を同期した。状態モデル/Python単体テストは未変更のため再実行せず、実サービス・追加依存取得・commit/pushは行っていない。


## 203. 添付画像で指摘された角の薄れを補正（2026-09-11）

[EXEC-123](GOAL.md#exec-123-角の輪郭濃度を補正)で、従来の1回の内側輪郭描画に残った部分画素の濃度低下を比較した。同位置の1px輪郭を2回重ね、着色範囲を広げずに角の濃度を補正した。半径15pxの角の法線上の最低ピーク濃度は0.448から0.680になった。寸法・色・内容・スクロールの処理は維持し、同じ指定色で描く基本・危険ボタンと共通の枠へ適用した。

画素テストは従来のRGB積分上限を幾何学的なはみ出し検査へ置き換え、薄れを検出するピーク濃度を追加した。実装前1件RED（ボタンとウィンドウの2検査が失敗）、同じhashでGREENを確認した。開発版12件（4.5秒）、ビルド版30件（40.8秒）、型/整形/build、Markdownリンク・見出し、差分検査が成功。DPR1/1.25/1.5/2の現行画面と同位置の角の変更前後を撮影し、寸法維持と例外0件を確認した。利用者実機での解消は未確認。状態モデル/Python単体テストは未変更のため再実行せず、実サービス・追加依存取得・commit/pushは行っていない。


## 204. 現在以外の段階マーカーを縮小（2026-09-11）

利用者指定により、Stepperの現在の丸は44×44pxを維持し、完了・未到達の丸を28×28pxへ縮小した。44×44pxの配置枠は保ち、SVGを中央へ配置して接続バー・文字・各丸の中心位置を維持する。完了した丸の青背景、現在位置の人アイコン、商品調査の36pxアイコンは維持した。FRONTEND・SEARCH-FLOW・REQUIREMENTS・DEVELOPMENT・CHANGELOGを同期した。

navigation.spec.tsへ初期状態・進行後・戻った後の寸法と中心位置の検査を追加した。SHA-256は `ab2371c974582b8c720bf831d91270790430aff16a91a2b9166d4f83eac83a17`。実装前 `UI_TEST_MODE=development npm run test:e2e -- navigation.spec.ts -g 'completed stage'` はexit1・1件失敗（28px期待に44px）。同一hashの実装後 `UI_TEST_MODE=development npm run test:e2e -- navigation.spec.ts controls.spec.ts --workers=4` はexit0・6件成功（3.8秒）、`npm run test:e2e -- navigation.spec.ts controls.spec.ts --workers=4` はビルド配信でexit0・6件成功（3.3秒）。DPR1/2のSVG外枠、配色・トグル・スクロール維持も確認した。

型/整形・build、Markdownリンク・見出し、git diff --checkが成功し、5173番の段階バーを目視した。小規模な表示変更であり、未変更の状態モデル・Pythonの機能テストや全操作回帰は再実行していない。実サービス・追加依存取得・commit/pushは行っていない。


## 205. トグルのOFF背景を変更（2026-09-11）

利用者指定により共通ToggleのOFF背景を `#424242` に変更し、仕様・要件・開発規則・変更履歴を同期した。ON背景、白いつまみ、240msの切替を維持した。

controls.spec.tsの既存OFF配色期待を更新し、実装前 `UI_TEST_MODE=development npm run test:e2e -- controls.spec.ts -g 'reference-image switch'` はexit1・1件失敗（66期待に33のRGB成分）。同一test hash `4f3abfa632bf22f2229ab62e68afbb6551943410d6f13f962f87b1f44f4bbf51` で実装後GREENを確認した。motion.spec.tsのOFF色も同期し、`UI_TEST_MODE=development npm run test:e2e -- controls.spec.ts motion.spec.ts -g 'switch|toggle|reduced motion' --workers=3` はexit0・3件成功（3.5秒）、同じ引数のビルド版はexit0・3件成功（3.8秒）。型/整形・build、Markdownリンク・見出し、差分検査も成功した。未変更のモデル/Python・全操作回帰・実サービスは再実行せず、追加依存取得・commit/pushは行っていない。


## 206. 条件整理の説明と入力欄の表示を整理（2026-09-11）

利用者指定により、条件整理の見出し下の「希望を確かめながら、ひとつずつ。」と、入力欄右の「希望から、比較へ。」および3項目の操作説明を削除した。共通のモック警告と固定デモ条件の注意書き・入力欄との関連付けを保った。入力例を `#a0a0a0` とし、入力文字は白を維持した。説明ラベルと入力欄の間に16pxを追加した。FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。

既存controls.spec.tsへ不要文言の非表示、注意書き保持、placeholder色、入力文字色、16px間隔を追加した。SHA-256は `66853d111c4975a4c9af82645bb74ac21cbc12bf4026ac9fc97b6719a22343fd`。実装前 `UI_TEST_MODE=development npm run test:e2e -- controls.spec.ts -g 'primary button'` はexit1・1件失敗（不要な3文言が存在、placeholder白、余白0px）。同一hashの実装後 `UI_TEST_MODE=development npm run test:e2e -- controls.spec.ts navigation.spec.ts motion.spec.ts frame.spec.ts --workers=4` はexit0・12件成功（6.0秒）、同じ引数のビルド版はexit0・12件成功（5.1秒）。型/整形・build、Markdownリンク・見出し、差分検査が成功し、5173番の入力画面も目視した。状態モデル/Python・全操作回帰・実サービスは未変更のため再実行せず、追加依存取得・commit/pushは行っていない。


## 207. 条件整理の入力欄の背景を変更（2026-09-11）

利用者指定により、自然文入力欄の背景を `#212121` に変更し、FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。既存controls.spec.tsに背景色検査を追加し、実装前 `UI_TEST_MODE=development npm run test:e2e -- controls.spec.ts -g 'primary button'` はexit1・1件失敗（期待RGB33に対し0）。SHA-256 `339d6d282021ff1c145427ba1507256b9741b5d7181c47700110b8bf5ebb9214` を保った実装後検証は、同じ開発版コマンドでexit0・1件成功（2.2秒）、ビルド版の同じ引数でexit0・1件成功（1.9秒）。型/整形・build、Markdownリンク・見出し、差分検査も成功。背景以外の入力文字・入力例・枠・余白・操作を維持した。未変更のモデル/Python・全操作回帰・実サービスは再実行せず、追加依存取得・commit/pushは行っていない。


## 208. 入力欄下の補助文を削除（2026-09-11）

利用者指定により「日本語で、そのまま。」だけを削除し、文字数の右寄せ表示と2,000文字超過時のエラーを保持した。FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。文言削除のため新しいテストは追加せず、型/整形・buildと既存 `npm run test:e2e -- flow.spec.ts -g 'input limits'` を実行し、ビルド配信でexit0・1件成功（1.8秒）。Markdownリンク・見出しと差分検査も成功した。実サービス・追加依存取得・commit/pushは行っていない。


## 209. 入力欄選択時の追加枠を非表示（2026-09-11）

利用者指定により条件整理のtextareaだけoutlineStyleをnoneにした。通常の1px外枠と背景 `#212121` は保持し、仕様のフォーカス枠規則へこの例外を反映した。ローカル開発画面でクリック、TabからShift+Tabでの復帰の双方についてfocus=true、outline=none、背景・通常枠の保持を確認した。小規模な表示変更として新しいテストは追加せず、型/整形・buildと既存 `npm run test:e2e -- controls.spec.ts -g 'primary button'` を実行し、ビルド配信でexit0・1件成功（1.9秒）。Markdownリンク・見出しと差分検査も成功。実サービス・追加依存取得・commit/pushは行っていない。


## 210. Figmaで指定されたWiStars素材を追加（2026-09-11）

利用者の指示で `frontend/public/icons/wi-stars.svg` を追加した。正本FigmaのIntent Reviewページに `96:467` / `react-icons/WiStars`（12×12px）が見つかったが、子レイヤー0・非表示fillのみでSVG exportは失敗した。直接書き出した成果物とは扱わず、名前に対応するWeather Iconsの `wi-stars.svg` を公開上流commit `bb80982bf1f43f2d57f9dd753e7413bf88beb9ed` から取得した。元のpathとviewBoxを維持し、白 `#ffffff` と明示寸法30×30を設定した。Figma側とReact表示コードは変更していない。

出典・変更点・Figmaとの対応を同じフォルダのREADMEへ記録し、SIL OFL 1.1の本文を同梱した。SVGのSHA-256は `2a7b20cf75a66725258c5510bcd01dfebb3ae84dae81a0ca4cb2d01e42f573d8`。XML構造とpath一致、ローカル配信HTTP200、同一originでのimg decode 30×30、黒背景での白い4つの星の描画を確認した。最初の確認スクリプトはSVG文書へのsetContentとabout:blankからの読み込みで失敗し、同一originのHTML文書でやり直して成功した。素材追加のみのため機能テスト・buildは再実行せず、Markdownリンク・差分を検証した。公開素材の取得以外の実検索サービス・追加依存取得・commit/pushは行っていない。


## 211. 参考画像の生成中ポップと操作配置を調整（2026-09-11）

利用者指定により共通の生成中ポップを126×46pxから96×32pxへ縮小した。文字14px・行高20px、上下余白6px・左右12pxで中央に置き、既存の背景・枠・点のアニメーションを維持する。参考画像と比較画像の確認画面では、下部左に「条件へ戻る」「作り直す」を32px間隔で横並びにした。右側の画像なし続行・主要操作は維持する。共通actionGroupの既存12px間隔は変更せず、この2操作だけ既存の32px横並びスタイルを使う。既存の星アイコン指定も保持し、同ファイルのimgとlabelWithIconの整形のみ行った。

既存flow.spec.tsにポップ寸法と両確認画面のボタン同一行・間隔検査を追加した。SHA-256は `e53c89366b7793a04624fb99ab5c666555945ed7e9a7da802925bb74b5a626d0`。実装前 `npm run test:e2e -- flow.spec.ts -g 'reference and comparison'` はexit1・1件失敗（ポップ126×46、ボタンが別行）。途中の12px間隔で2検査が失敗したため、対象の2操作に32pxを適用した。同一hashの最終検証はexit0・1件成功（17.1秒）。先行画像と比較画像の了承、作り直し確認の取消、検索・履歴までの既存操作も確認した。

開発画面でも96×32pxとボタン同一行・32px間隔を確認し、生成中と確認画面を撮影・目視した。型/整形・build、Markdownリンク・見出し、差分検査が成功。FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。未変更のモデル/Python・全操作回帰・実サービスは再実行せず、追加依存取得・commit/pushは行っていない。


## 212. 共通見出し下の補助文を削除（2026-09-11）

利用者指定によりApp.tsxの共通見出し下から「希望を確かめながら、ひとつずつ。」を削除し、条件整理以外の全画面でも表示しないようにした。FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。文言削除のみのため新規テストは追加せず、表示ソースの残存検査と `npm --prefix frontend run check` が成功した。ブラウザ操作・build・実サービスは再実行していない。未コミットの変更である。


## 213. 画像クリックで拡大表示（2026-09-11）

利用者指定により共通ImageCardの独立した「拡大」ボタンを除去し、画像自体をライトボックスを開くボタンにした。ホバーとキーボードフォーカス時に中央の虫眼鏡アイコンを表示し、カーソルをzoom-inにする。白いSVGアイコンを黒い44px円形背景に置き、画像全体への追加ハイライトは付けない。Enter・Spaceでの開閉操作と既存の閉じる際のフォーカス復帰を保持した。FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。

既存flow.spec.tsへ画像が拡大操作の対象であること、通常時/ホバー/キーボードフォーカス時のアイコン、画像クリックとEnterによる拡大を追加した。SHA-256は `48990a1df498fcb52d6ae7d7ef053ac66a84d475403aef3a35b0ff844db34d54`。実装前 `npm --prefix frontend run test:e2e -- flow.spec.ts -g 'reference and comparison'` はexit1・1件失敗（拡大ボタン内に画像がない）。同一テストの実装後はexit0・1件成功（17.3秒）。画像了承・比較画像・検索・履歴までの既存フローも通過した。

初回buildはdefineMarkerがnamed exportを要求して失敗したため、公開APIを増やさずdefaultMarkerへ変更した。整形修正後の型/整形とbuildは成功した。ローカル開発画面でもホバーアイコンを撮影・目視し、クリック・Escape・Spaceを確認した。Markdownリンク・差分検査を実施した。実バックエンド・外部API・追加依存取得・commit/pushは行っていない。全テストと実サービスの成功とは扱わない。


## 214. 条件確認の入力欄の背景を統一（2026-09-11）

利用者指定によりscreens.tsxの共通input背景をtheme.note（#212121）に変更した。条件確認の商品の種類・必ずほしい・できればほしい・避けたい・予算へ適用し、既存の自然文入力欄と統一した。FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。小規模な色変更のため新規テストは追加せず、型/整形検査とローカル開発画面で自然文入力欄および5項目の背景色、白文字、予算編集・反映から最終確認への値の保持を検証して成功した。Markdownリンク・差分検査を実施した。build・全テスト・実サービスは再実行していない。未コミットの変更である。


## 215. 条件確認の入力文背景を変更（2026-09-11）

利用者指定により条件確認画面の「入力した文章」の本文へ背景#212121を適用した。共通の折り返し規則は変更せず、当該本文だけ専用StyleXスタイルを追加した。FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。小規模な色変更のため新規テストは追加せず、型/整形検査とローカル開発画面で背景色・白文字・pre-wrapの保持を確認し成功した。Markdownリンク・差分検査を実施した。build・全テスト・実サービスは再実行していない。未コミットの変更である。


## 216. 入力文の背景を角丸に変更（2026-09-11）

利用者指定により条件確認の入力文背景へ共通の15px角丸を適用し、文字が角へ接しないよう16pxの内側余白を付けた。背景#212121と本文の折り返しを保持し、FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。小規模な表示変更のため新規テストは追加せず、型/整形検査とローカル開発画面の角丸15px・余白16px・背景色を確認して成功した。Markdownリンク・差分検査を実施した。build・全テスト・実サービスは再実行していない。未コミットの変更である。


## 217. 条件入力欄の追加フォーカス枠を非表示（2026-09-11）

利用者指定により共通inputスタイルのoutlineStyleをnoneにし、条件確認の5項目にも自然文入力欄と同じ選択時の表示を適用した。通常の1px外枠と背景#212121を保持し、FRONTENDのフォーカス規則・SEARCH-FLOW・CHANGELOGを同期した。小規模な表示変更のため新規テストは追加せず、型/整形検査とローカル開発画面の5項目について、クリックおよびTab/Shift+Tab時のフォーカス・outline非表示・背景・通常枠の保持を確認して成功した。Markdownリンク・差分検査を実施した。build・全テスト・実サービスは再実行していない。未コミットの変更である。


## 218. 最終確認の条件背景を変更（2026-09-11）

利用者指定により最終確認の5条件のラベルと値へ背景#212121・角丸15px・内側余白16pxを適用した。ConditionSummaryに表示variantを追加し、最終確認でだけ既存の背景スタイルを使用する。FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。小規模な表示変更のため新規テストは追加せず、型/整形検査とローカル開発画面で5条件の背景・角丸・余白・ラベルと値の表示、検索ボタンが有効であることを確認して成功した。Markdownリンク・差分検査を実施した。build・全テスト・実サービスは再実行していない。未コミットの変更である。


## 219. 最終確認の入力文背景を統一（2026-09-11）

利用者指定により最終確認の「入力した文章」を開いた本文にも、背景#212121・角丸15px・内側余白16pxを適用した。既存cards variantでのみ有効にし、折り返しを保持した。FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。小規模な表示変更のため新規テストは追加せず、型/整形検査とローカル開発画面で本文の開閉操作のうち展開、背景・角丸・余白・pre-wrapを確認して成功した。Markdownリンク・差分検査を実施した。build・全テスト・実サービスは再実行していない。未コミットの変更である。


## 220. 最終確認の条件名を背景外へ移動（2026-09-11）

利用者指定により最終確認の背景スタイルを条件の親領域から値（dd）へ移し、項目名（dt）を背景外の上に配置した。値の背景#212121・角丸15px・内側余白16pxを保持し、FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。小規模な表示変更のため新規テストは追加せず、型/整形検査とローカル開発画面で全5項目の親領域・項目名の透明背景、値の背景・角丸・余白、項目名が値の領域の上にあることを確認して成功した。Markdownリンク・差分検査を実施した。build・全テスト・実サービスは再実行していない。未コミットの変更である。


## 221. 履歴画面の見出し位置を統一（2026-09-11）

履歴専用の空要素と余白が検索画面のStepper領域より110px短く、1440px幅で見出しがy198、モック通知がy288となっていた（検索画面はy308/y398）。App.tsxで共通Stepper領域を維持し、履歴一覧・詳細ではopacity:0・pointer-events:none・aria-hiddenで表示と操作・読み上げから除外した。固定の余白によるhistoryIntroを除去し、本文幅1120pxと見出し・通知の開始位置を揃えた。途中のvisibility:hiddenではローカルChromiumの撮影時に他領域も描画されない現象があり、opacityへ変更後はヘッダー・内容の描画を撮影・目視で確認した。

navigation.spec.tsに空履歴・保存済み履歴・詳細・一覧復帰の見出し/通知の位置と幅、段階バーが読み上げ対象にないこと、検索復帰時の段階バー表示を追加した。SHA-256は `c42a97f8835b71b01f8545e4b4eb261e133219a50c5d3e4e464fe88e548f5dec`。実装前 `UI_TEST_MODE=development npm --prefix frontend run test:e2e -- navigation.spec.ts -g 'history list and details'` はexit1・1件失敗（y座標が110px不一致）。同一テストを保った最終実装で、開発版navigation.spec.ts全3件はexit0（3.1秒）。ビルド版 `npm --prefix frontend run test:e2e -- navigation.spec.ts flow.spec.ts interaction.spec.ts -g 'history list and details|history deletion is separated|opening history during research'` はexit0・3件成功（8.9秒）。履歴削除の確認、検索中の履歴表示・検索継続・1回だけの保存も通過した。

型/整形・build、Markdownリンク・差分検査が成功した。FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。未変更の全モデル/Python試験・全ブラウザ試験・実サービスは再実行せず、追加依存取得・commit/pushは行っていない。


## 222. 商品調査のチェックマークを拡大（2026-09-11）

利用者指定により商品調査の完了チェックを28px・太さ700・行高28pxへ変更した。36pxの白い丸と黒いチェックの配色、現在工程・待機工程の表示は保持した。FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。小規模な表示変更のため新規テストは追加せず、型/整形検査とローカル開発画面の全5工程完了時の文字サイズ・太さ・黒色を確認し、完了行を撮影・目視した。Markdownリンク・差分検査を実施した。build・全テスト・実サービスは再実行していない。未コミットの変更である。


## 223. 完了チェックの大きさを微調整（2026-09-11）

利用者指定により商品調査の完了チェックを28pxから24pxへ縮小し、行高も24pxに揃えた。太さ700と36pxの白い丸を保持し、FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。小規模な文字サイズ変更のため新規テストは追加せず、型/整形検査が成功した。Markdownリンク・差分検査を実施した。ブラウザ操作・build・全テスト・実サービスは再実行していない。未コミットの変更である。


## 224. 結果カードの画像拡大と表示整理（2026-09-11）

利用者指定により参考画像の画像クリック部を共通ImageZoomへ抽出し、結果と履歴内の商品画像でもホバー時の虫眼鏡・クリック/キーボードによる拡大を使えるようにした。拡大は共通Dialogで対象画像だけを表示し、閉じた後は起動元へフォーカスを戻す。商品詳細の説明はカード内に保持する。

条件状態を「一致」「未確認」「不一致」に揃え、固定データの未確認文言2種類と不一致の表現2種類を表示層で条件名へ変換した。保存済み履歴とmodelのデータは変更しない。詳細/閉じるを中央配置し、順位は「n位」、青背景#3a83f7・白い1px外枠・角丸15pxにした。カード余白25pxと同じ値の負の左余白で順位ラベルを左外枠に重ねる。FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。

実装前 `UI_TEST_MODE=development npm --prefix frontend run test:e2e -- results.spec.ts` はexit1・1件失敗（旧状態文言と説明文が残存、新順位ラベルなし）。RED時のtest SHA-256は `2b1beb2cbeda7a7cc57123192fe09ca2e4c7c5763ff8f95183d6e2dc52ebcb90`。後続の型検査でsrc属性のstring/null型エラーが見つかり、期待画像srcの非null assertionだけを追加した。検査内容は変更していない。最終hashは `85de6c9fa11a275f6e532a2c6f1dd3848a2f54798caad3c1e15fd81ff673ea33`。開発版同コマンドはexit0・1件成功（3.1秒）。順位1/12のラベル色・角丸・左枠一致、詳細ボタン中心、全条件文言、画像クリック・Enter・閉じる/Esc・フォーカス復帰、詳細展開と履歴内拡大を確認した。結果カードを撮影・目視した。

既存interaction.spec.tsの状態名を新仕様へ同期した。型/整形・build成功。ビルド版 `npm --prefix frontend run test:e2e -- results.spec.ts flow.spec.ts interaction.spec.ts -g 'result cards show|result details expand|reference and comparison|history deletion is separated'` はexit0・4件成功（17.6秒）。参考/比較画像の既存確認フローと履歴削除も通過した。Markdownリンク・差分検査が成功した。未変更のモデル/Python・全ブラウザ試験・実サービスは再実行せず、追加依存取得・commit/pushは行っていない。


## 225. 順位ラベルを#形式に変更（2026-09-11）

利用者指定により結果・履歴内の順位表記を「n位」から「#n」へ変更した。既存results.spec.tsの期待ラベルとFRONTEND・SEARCH-FLOW・CHANGELOGを同期した。新規テストは追加せず、型/整形検査と `UI_TEST_MODE=development npm --prefix frontend run test:e2e -- results.spec.ts` が成功（exit0・1件、3.0秒）。順位ラベル配置・画像拡大・条件表示・詳細と履歴操作を確認した。Markdownリンク・差分検査を実施した。build・全テスト・実サービスは再実行していない。未コミットの変更である。


## 226. 順位ラベルの上端をカード枠に統一（2026-09-11）

利用者指定により順位ラベルを相対位置で上へ25px移し、左端に加えて上端もカードの外枠へ揃えた。画像や本文の配置は保持し、FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。既存results.spec.tsに上端一致の検査を加え、型/整形検査と `UI_TEST_MODE=development npm --prefix frontend run test:e2e -- results.spec.ts` が成功（exit0・1件、3.0秒）。順位1/12の左右・上端配置と既存操作を確認し、結果カードを撮影・目視した。Markdownリンク・差分検査を実施した。build・全テスト・実サービスは再実行していない。未コミットの変更である。


## 227. 順位枠の角と一致情報の開閉を変更（2026-09-11）

利用者指定により順位ラベルの左上・右上・左下を直角、右下のみ15px角丸にした。既存の左/上端のカード枠への位置合わせを保持した。一致・未確認・不一致は既定で閉じたdetails/summary「一致情報」にまとめ、クリック・Enter・Spaceでカードごとに独立して開閉する。詳細ボタンによる説明と画像拡大は保持した。FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。

results.spec.tsへ開閉前後の内容表示、クリック/Enter/Space操作、別カードの閉状態保持と4隅の半径を追加した。同一SHA-256 `5c9dca72da372956c5fa38db57517bac5d577b613c604f3f0ca9d7e684c4512d` で、実装前 `UI_TEST_MODE=development npm --prefix frontend run test:e2e -- results.spec.ts` はexit1・1件失敗（一致情報の開閉要素なし）、実装後はexit0・1件成功（2.9秒）。型/整形・buildが成功し、ビルド版 `npm --prefix frontend run test:e2e -- results.spec.ts interaction.spec.ts -g 'result cards show|result details expand'` はexit0・2件成功（9.2秒）。結果カードを撮影・目視し、Markdownリンク・差分検査が成功した。未変更の全モデル/Python試験・全ブラウザ試験・実サービスは再実行せず、追加依存取得・commit/pushは行っていない。


## 228. 順位ラベルの左上を角丸へ変更（2026-09-11）

利用者指定により順位ラベルの左上を15px角丸に戻した。右下15px・右上/左下直角を保持し、既存results.spec.tsの期待値とFRONTEND・SEARCH-FLOW・CHANGELOGを同期した。型/整形検査と `UI_TEST_MODE=development npm --prefix frontend run test:e2e -- results.spec.ts` が成功（exit0・1件、3.1秒）。4隅・位置合わせ・一致情報開閉・画像拡大を確認した。Markdownリンク・差分検査を実施した。build・全テスト・実サービスは再実行していない。未コミットの変更である。


## 229. 結果カードの開閉見出しを変更（2026-09-11）

利用者指定により結果カードの「一致情報」を「検索条件」に変更し、既存results.spec.tsとFRONTEND・SEARCH-FLOW・CHANGELOGを同期した。型/整形検査と `UI_TEST_MODE=development npm --prefix frontend run test:e2e -- results.spec.ts` が成功（exit0・1件、3.2秒）。開閉と既存結果操作を確認した。Markdownリンク・差分検査を実施した。build・全テスト・実サービスは再実行していない。未コミットの変更である。


## 230. 新規検索の共通配置と商品名リンク（2026-09-11）

利用者指定により「新しく検索」を全画面のヘッダー右側操作の左へ移し、結果下部の重複ボタンを除去した。履歴表示時は既存の「検索へ戻る」の左に同じ位置で表示する。未保存結果の破棄確認は保持した。処理中のRESETを許可し、旧revisionの完了を無視して空の入力画面へ戻る。結果カードの詳細ボタン・展開説明・専用状態/スタイルを除去し、検索条件の折りたたみと画像拡大を保持した。

商品名表示をProductNameへ分離した。ResultsのproductUrl callbackで実商品のHTTPS URLを明示的に渡す場合だけ、noopener/noreferrer付き新規タブリンクを作る。現行モックAppではcallbackを渡さず、商品名は通常テキストとなる。保存形式や実providerは変更せず、実URLの供給は未接続。空・不正・非HTTPS・ユーザー情報付きURLはリンクにしない。リンクHTMLの生成は通信しないSSRテストで検証し、外部ページのクリックや実商品サービス成功は主張しない。FRONTEND・SEARCH-FLOW・REQUIREMENTS・CHANGELOGを同期し、現行Streamlitの旧リンク仕様は保持した。

実装前 `UI_TEST_MODE=development npm --prefix frontend run test:e2e -- navigation.spec.ts results.spec.ts -g 'new search stays|result cards show'` はexit1・2件失敗（ヘッダーに新規検索なし、詳細ボタン残存）。部分実装で処理中RESET拒否を検出した。追加の `npm --prefix frontend test -- -t 'new search resets'` はexit1・4件失敗後、RESET許可によって同じテストが成功した。新規検索・旧処理の非適用を検証するmodel.test.ts SHA-256は `1143ffe3f7d0d50b8f51a9d98f1ce6432320e5a05559543c299b88b5cad764c4`。navigation.spec.tsは `68dff631ec07c5f03bf5f37ad127dcccf59d553128e9288f84a3f785e27b3181`、results.spec.tsは `9e81dc7f1182b1e0f9f24c78458f4a42e5453575edd5fb69fb3f570d7bb2b342` を保ってGREENにした。

最終の型/整形・build・Vitest全51件が成功。開発版navigation/resultsは5件成功（4.1秒）、ビルド版 `npm --prefix frontend run test:e2e -- navigation.spec.ts results.spec.ts interaction.spec.ts` はexit0・9件成功（10.3秒）。常時配置・処理中リセット・履歴復帰・未保存結果の破棄キャンセル/保存再試行・モック非リンク・詳細ボタン不在・検索条件開閉・画像拡大を確認し、結果カードを撮影・目視した。Markdownリンク・差分検査が成功。未変更のPython・全ブラウザ試験・実サービスは再実行せず、追加依存取得・commit/pushは行っていない。


## 231. 結果画面に先頭へ戻るボタンを追加（2026-09-11）

利用者指定により結果と履歴内の結果の右下へ「トップに戻る」を固定表示した。右24px・下32px、56pxの円形、白い1px枠・白背景・黒い上矢印とし、影はオフセット0・ぼかし20px・広がり4px・白35%で全方向へ広げた。クリック/キーボードの明示操作で先頭へ滑らかに移動し、prefers-reduced-motionでは即時移動する。検索状態・件数は変更しない。FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。

back-to-top.spec.tsの同一SHA-256 `1e8a85892ff82cebe0318462858b6792665d375f5a305f6b6442e0ad45e4651a` で、実装前 `UI_TEST_MODE=development npm --prefix frontend run test:e2e -- back-to-top.spec.ts` はexit1・2件失敗（ボタンなし）。実装後はexit0・2件成功（4.4秒）。通常/動きを減らす設定の双方で、検索前の非表示、結果での配色・影・固定位置、クリック/Enter後のscrollY=0と件数保持を確認した。型/整形・build成功。ビルド版 `npm --prefix frontend run test:e2e -- back-to-top.spec.ts results.spec.ts navigation.spec.ts` はexit0・7件成功（4.7秒）。開発画面のボタンと影を撮影・目視し、Markdownリンク・差分検査が成功した。未変更のモデル/Python・全ブラウザ試験・実サービスは再実行せず、追加依存取得・commit/pushは行っていない。


## 232. 表示件数の追加フォーカス枠を非表示（2026-09-11）

利用者指定により表示件数selectのoutlineStyleをnoneにし、通常の1px外枠を保持した。FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。小規模な表示変更のため新規テストは追加せず、型/整形検査とローカル開発画面のクリック/キーボード選択で追加枠がないこと、3件への表示件数変更が成功することを確認した。Markdownリンク・差分検査を実施した。build・全テスト・実サービスは再実行していない。未コミットの変更である。


## 233. 履歴詳細の条件と操作配置を統一（2026-09-11）

利用者指定により履歴詳細のConditionSummaryを等幅2列・列間32pxにし、最終確認と同じcards表示を適用した。項目名は背景外、値と入力した文章は背景#212121・角丸15px・内側余白16pxとする。「削除」「履歴へ戻る」を条件枠の最下部へ移し、左に危険操作、右に戻る操作を置いた。結果カードとの間隔も共通stackで確保した。FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。

navigation.spec.tsへ2列の位置、全5条件の背景・角丸・項目名の背景、同じ枠の最終行に両操作があること、削除確認キャンセルとフォーカス復帰を追加した。実装前 `UI_TEST_MODE=development npm --prefix frontend run test:e2e -- navigation.spec.ts -g 'history list and details'` はexit1・1件失敗（先頭2項目が異なる行）。期待条件を維持して整形後、同じコマンドはexit0・1件成功（2.9秒）。最終SHA-256は `e96d8dc7233ebe002c29a733a76886f040c4497074608ecc644ff80c1a30c0bc`。型/整形・buildが成功し、ビルド版 `npm --prefix frontend run test:e2e -- navigation.spec.ts results.spec.ts flow.spec.ts -g 'history list and details|result cards show|history deletion is separated'` はexit0・3件成功（9.5秒）。履歴の条件枠を撮影・目視し、Markdownリンク・差分検査が成功した。未変更のモデル/Python・全ブラウザ試験・実サービスは再実行せず、追加依存取得・commit/pushは行っていない。


## 234. 履歴の段階バー用空白を削除（2026-09-11）

利用者指定により、履歴一覧・詳細では段階バー自体とその予約領域を描画せず、ヘッダー下の通常余白36pxから見出しを表示するようにした。一覧と詳細の本文幅・見出し位置は揃えた。履歴一覧の商品名は白文字を保ち、背景#212121・角丸15px・内側余白16pxを付けた。FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。

navigation.spec.tsを更新し、実装前の対象テストは段階バー用空白が残るため1件失敗した。実装後の開発版navigationは4件成功（3.0秒）。履歴の見出しが検索画面より上に移ること、非表示の段階バーも存在しないこと、一覧・詳細・戻る操作での位置統一、商品名の背景・文字色を確認した。最終SHA-256は `ef0591309887b8667401a72ee93140a538ef75aa918eae0c38e5be721b0cad6c`。型/整形・buildが成功し、ビルド版 `npm --prefix frontend run test:e2e -- navigation.spec.ts flow.spec.ts -g 'history list and details|history deletion is separated'` の最終結果ファイルもpassed・失敗なしを確認した。未変更のモデル/Python・全ブラウザ試験・実サービスは再実行せず、追加依存取得・commit/pushは行っていない。


## 235. 履歴一覧カードを小型化（2026-09-11）

利用者指定により、履歴一覧を3列・カード幅352pxから4列・268pxへ変更した。カード間隔は32pxから16px、内側余白は25pxから17px、項目間隔は16pxから8pxに縮小した。履歴専用StyleX規則を重ね、商品結果カードと履歴詳細の寸法、商品名背景、文字サイズ、96×36pxの操作ボタンを保持した。FRONTEND・SEARCH-FLOW・CHANGELOGを同期した。

小規模な表示変更のため新規テストは追加していない。型/整形・buildが成功し、開発版の既存navigation履歴テストは1件成功（1.9秒）。外部/API要求を遮断したローカルChromiumで合成検索を4件保存し、カード幅268px・高さ304px、同じ行の4列配置、横方向のはみ出しなしを確認した。撮影画像で文字とボタンの配置を目視した。Markdownリンク・差分検査を実施した。全テスト・実サービスは再実行せず、追加依存取得・commit/pushは行っていない。


## 236. フロントエンドのコミット前検証（2026-09-11）

利用者のcommit・push指示に基づき、React + StyleXのオフライン画面、ローカル資材、テストと関連文書をまとめて確認した。node_modules・dist・ブラウザ試験結果はgitignoreにより対象外。型/整形チェック、build、Vitest全51件、ビルド版Playwright全35件（20.7秒）、Markdownリンク検査、git diff --checkが成功した。ブラウザ検証は固定合成データを用いるローカル画面のみで、実バックエンド・実サービスは実行していない。fetch後のmainはorigin/mainと一致しており、公開対象にバックエンド実装の変更はない。


## 237. 最低対応Pythonを3.11へ更新（2026-09-11）

利用者のバージョン更新指示により、pyproject.tomlのrequires-pythonを>=3.11、Ruffをpy311、GitHub Actionsのマトリクスを3.11 / 3.13へ変更した。README・REQUIREMENTS・DEVELOPMENTの現行要件とCHANGELOGを同期し、過去の3.10検証記録は保存した。アプリケーションとテストのロジック、安全性チェックは変更していない。

uv lock --offlineはキャッシュ不足で失敗したため、環境準備として公開パッケージ情報を取得してuv lockを再生成した。107 packagesとなり、3.10専用の依存分岐・wheelを除去した。追加されたパッケージ名/バージョンの組は0で、残るバージョンは維持した。uv python install 3.11で3.11.15を準備し、UV_PROJECT_ENVIRONMENT=/tmp/amazon-explorer-python311-20260911-01 uv sync --locked --python 3.11で独立した検証環境を作った。既存.venvの3.13.13と別モデル環境は変更していない。

両環境で `uv run --frozen --offline --no-sync pytest -m 'not live_api' tests/test_lexical_assets.py tests/test_lexical_context_dictionary.py tests/test_lexical_dictionary.py tests/test_product_phrase.py tests/test_candidate_search_retry.py -q` を実行し、各31件成功（3.11は3.54秒、3.13は2.90秒）。3.11側は上記UV_PROJECT_ENVIRONMENTを指定した。file_digestとZ末尾日時解析を含む既存テストを使い、今回の設定変更に新規テストは追加していない。

3.11の全体 `uv run --frozen --offline --no-sync pytest -m 'not live_api'` はexit1・3044 passed / 1 failed / 20 skipped / 30 deselected（88.33秒）。残る失敗はtest_broker_tls_targets_openai_while_tcp_connects_only_to_the_internal_gatewayで、FakeContext.verify_mode不足によるAttributeError。既存CIで確認済みの別不具合として保持した。ローカルroot環境の結果であり、GitHub runnerでの権限・ACL・環境変数の失敗解消を証明しない。

uv lock --check --offline、Ruff check、Ruff format --check（372 files）、Python対応範囲/lock/Ruff/CI設定の照合、Markdownリンク、git diff --checkが成功した。Python 3.10が対応範囲外、3.11と3.13が範囲内であることも確認した。変更後のGitHub CI・実サービス・UI検証は未実行。commit/pushは行っていない。


## 238. SSLモックとoffline環境の期待値を修正（2026-09-11）

利用者指定によりCIで失敗していたSSLモックと環境変数の期待値を現行仕様へ合わせた。test_ai_review_broker_entryの独自FakeContextを標準SSLContextへ替え、wrap_socketとTCP接続だけをモックした。固定gatewayへのTCP接続、API_HOSTへのSNI、同じsocketの引渡し、CERT_REQUIREDとcheck_hostnameを確認する。TLSや外部通信そのものは実行しない。

test_ai_review_trust_boundaryはgate/red/greenそれぞれでruntime directoryの有無を模擬する。offline_runner内だけのos参照へ固定UIDを与え、対象/run/user/65532だけのPath判定を模擬し、実ホストのUID・directory・権限は変更しない。固定PATH/LC_ALLと条件付きXDG_RUNTIME_DIRを値まで厳密照合し、親環境の任意XDG_RUNTIME_DIR/DOCKER_HOSTが混入しないことを検証する。src・tools・specsの実装や安全性チェックは変更していない。DEVELOPMENT・REQUIREMENTS・CHANGELOGを同期した。

RED: 3.11環境で `uv run --frozen --offline --no-sync pytest -m 'not live_api' tests/test_ai_review_broker_entry.py -k test_broker_tls_targets_openai --tb=short -q` はexit1・1 failed（FakeContext.verify_mode不足）。変更前ファイルSHA-256は `0a9a84d8461ed5d9a55746100ab5a6a325e09995cb95654c3b7ff88621fe0865`。環境の有無を模擬して旧期待値を残した段階の `uv run --frozen --offline --no-sync pytest -q tests/test_ai_review_trust_boundary.py -k test_execute_offline_returns_bounded_digest_bound_evidence -m 'not live_api' --tb=short` はexit1・3 failed / 3 passed。XDG_RUNTIME_DIRが加わる3 phaseだけが失敗し、GitHubと同じ期待値不整合を再現した。今回はテスト自体の修正であり、同一テストhashのproduction RED/GREENやattestationとは扱わない。

GREEN: `uv run --frozen --offline --no-sync pytest -q tests/test_ai_review_broker_entry.py tests/test_ai_review_trust_boundary.py -m 'not live_api'` は3.11.15で99 passed（2.54秒）、既存3.13.13で99 passed（2.67秒）。最終SHA-256はbroker_entryのtestが `177142580e30417c9ece0d15b2257da8bc8cb8340fc23f68a8456b400a340b82`、trust_boundaryのtestが `0fd211299d8a2798b15c82eb3c583f204db6a383e4ebaecbb9fcf95d02b3f280`。

3.11側は事前準備済みのUV_PROJECT_ENVIRONMENT=/tmp/amazon-explorer-python311-20260911-01を指定し、全体 `uv run --frozen --offline --no-sync pytest -m 'not live_api'` がexit0・3048 passed / 20 skipped / 30 deselected（82.17秒）。lock・Ruff check/format（372 files）・Markdownリンク・git diff --checkも成功。ローカルroot環境でのoffline検証であり、GitHub runner固有の所有者変更・実行権限・ACLの既知失敗は別途対応が必要。実サービス、host配備、GitHub CI、commit/pushは実行していない。


## 239. フロントエンドCIを追加（2026-09-11）

利用者指定により.github/workflows/ci.ymlへPythonから独立したfrontendジョブを追加した。push/pull_request、ubuntu-latest、Node.js 22、20分上限、frontend作業ディレクトリで実行する。checkoutは既存のv7.0.1 SHAを再利用し、setup-node v7.0.0は公式tagから確認した820762786026740c76f36085b0efc47a31fe5020へ固定した。npm cacheはfrontend/package-lock.jsonをキーにする。既存のcontents: readとpersist-credentials: falseを維持する。

手順はnpm ci --no-audit --no-fund、npm run check、npm test、npm run build、npx --no-install playwright install --with-deps chromium、ビルド版全Playwright、開発版controls/motion/frame/navigation。ブラウザは--workers=1 --forbid-only、再試行なし。サービスcredentialや実バックエンドを使わず、画面は固定合成データとloopback配信だけを検証する。依存取得は公開配布先への通信を伴うため、既存のCI全体がegressなしというコメントも修正した。frontend README・FRONTEND・DEVELOPMENT・REQUIREMENTS・CHANGELOG・REFERENCESを同期した。

新規テストコードは追加せず、workflow構文と実行対象を検証した。actionlint v1.7.12の公式配布archiveを公開checksumと照合して/tmpへ展開し、ci.ymlの検査がexit0。起動中の開発環境を維持するためfrontendを/tmp/amazon-frontend-ci-20260911-01へコピーし、node_modules・dist・テスト出力を除外してnpm ciを実行した（105 packages、2秒）。Node.js 22.23.2/npm 12.0.2で型/整形・Vitest 51件・buildが成功した。

同じコピー内でCI=trueを指定した `npm run test:e2e -- --workers=1 --forbid-only` はexit0・35 passed（2.5分）。続くCI=true UI_TEST_MODE=developmentで `npm run test:e2e -- controls.spec.ts motion.spec.ts frame.spec.ts navigation.spec.ts --workers=1 --forbid-only` はexit0・14 passed（15.2秒）。Chromium資材はnpx --no-install playwright install chromiumで準備し、ローカルOSはPlaywrightの公式対応外なので既存のUbuntu向けfallback資材と準備済みsystem librariesを利用した。GitHub Ubuntu上の--with-depsによるOS依存導入、setup-node/cacheの実行、追加後のGitHub CIは未検証。ローカル成功をGitHub成功や実サービス成功とは扱わない。

Markdownリンクとgit diff --checkが成功。Python 3.11対応とSSL/環境モックの既存未コミット変更を維持し、無関係なPython/実サービス検証、commit/pushは実行していない。


## 240. 権限境界テストのroot依存を除去（2026-09-11）

利用者指定により、通常の権限境界テストから別UIDへのchown、read-only資材作成後の無許可書込み、実行ホストがrootという暗黙の前提を除去した。brokerの仮実行ファイルを上書きするときは所有者として書込可能にしてから再固定し、candidate/snapshotは内容を作成した後にread-onlyにする。coordinatorのUID模擬は対象モジュールだけに限定し、root拒否のテストではroot条件を明示する。

deployment_checkの所有者判定は、一時領域のlstat結果のUIDだけを合成値へ置き換えるfixtureへ変更した。mode・ACL・symlink・inode・内容・時刻のチェックは残し、所有者だけを変更した不正ケースも維持した。実OSの所有者変更を検証する既存のtest_ai_review_attestationのroot専用テストとskip条件は変更していない。src・tools・specsへの変更は0で、本体のACL拒否や権限検査を緩めていない。

ホストのPython配置を保護資材として直接参照する代わりに、session単位のtrusted_python fixtureへ実行ファイル・標準ライブラリ・必要なlibpythonをコピーする。実行ファイルには元のACLをコピーせず、read-onlyに固定する。/proc/self/fdからの実execは維持し、sys.executableの標準ライブラリへの依存だけを残すpyvenv.cfg方式ではexec時にencodingsを見つけられなかったため、最終実装では通常のbin/lib配置を用いる。これはテスト資材でありproduction releaseの検証済みruntimeではない。

通常ユーザーでの再現用に、/tmp/amazon-permission-check-20260911-01へ独立checkout、準備済みPython 3.13.13のコピー、uv、依存環境を用意した。元PythonコピーのruntimeディレクトリにACLを付け、GitHubの配置に依存する失敗も再現した。所有者変更とACL追加はこの新規一時領域の準備だけに限定し、既存host/runtime/repositoryの権限は変更していない。テストprocessはsetprivでUID/GID 65534、補助groupなし、capability bounding setなし、no-new-privsへ落とし、env -iからPATH・作業用HOME/cache/environmentだけを与えた。通常のCIでこの準備用の管理者操作を必要とする設計にはしていない。

REDはこの通常ユーザー環境の `uv run --frozen --offline --no-sync pytest -q -m 'not live_api'` にbroker_executor・deployment_check・coordinator_launcher・runtime_release・workflow_init・trust_boundaryの6ファイルを指定し、38 failed / 157 passed（6.27秒）。修正中は20 failed / 175 passed、次に3 failed / 192 passedとなり、read-only directoryやUID模擬の追加依存も解消した。テスト自体の修正であり、同一テストhashでのproduction RED/GREENやattestationではない。

最終の同じ6ファイルは通常ユーザー3.13で195 passed（7.92秒）、既存の独立3.11.15環境で195 passed（7.76秒）。通常ユーザー3.13の全体 `uv run --frozen --offline --no-sync pytest -m 'not live_api'` はexit0・3047 passed / 21 skipped / 30 deselected（82.84秒）。root固有の1件は既存条件によりskipされており、新たな一括除外はない。uv lock --check --offline、Ruff check/format（372 files）、Markdownリンク、git diff --checkも成功した。

最終SHA-256: conftest.pyはda6614d9e7b52d1cb3ed719d3a0680ee3f91ba363bc199a460da1878fc974690、broker_executorのtestは4204eeee652141ca55a950392ce9d1827ffb9c028ceb290ba55b7d8dfbf535a2、deployment_checkのtestは52845e4b19790c14eaefb78af7996d051c3c0f4aeb29c00a5fbef7d1112455bb、coordinator_launcherのtestは3e9d6338be281b42688eba94aa1e344ac3748ca94fa230dedd1ebc46e0928f8d、runtime_releaseのtestは60804588076c92561966bd5572425c842b0560fc2c538518d12e2da60fc9d703、workflow_initのtestはdde0a616313d7d7ebadf29d00b4a64d3a091dc201d50996b198773db11048839、trust_boundaryのtestは9ee54864dfdd3b5029bf0760cf8616394e923d41e848f3a586221cedb6f8d62e。

DEVELOPMENT・REQUIREMENTS・HARNESS-RUNBOOK・CHANGELOGを同期した。既存のPython 3.11対応、SSL/環境モック、frontend CIの未コミット変更を維持した。変更後のGitHub CI、実サービス、実host配備、commit/pushは未実行であり、ローカル非root回帰の成功をこれらの成功へ読み替えない。


## 241. READMEを概要・技術スタック・起動方法へ整理（2026-09-11）

利用者指定によりREADMEの主見出しを3項目へ整理した。オフラインモックのdev/previewと実検索のBonsai・Streamlit・CLIの起動手順を残し、開発経緯・検証記録・詳細仕様を除いた。参照されていたローカル辞書の資材準備手順はBACKENDへ移し、NEXT-STEPS・DEVELOPMENT・REFERENCESのREADME見出しリンクを更新した。

文書変更のみ。Markdownのローカルリンク・見出し・コードフェンス検査とgit diff --checkが成功した。起動コマンドはpackage.json・既存手順と照合し、アプリや外部サービスは起動していない。この変更は未コミット。


## 242. 第三者ライセンス通知を配布物へ追加（2026-09-11）

利用者指定により、公式MIT/OFL本文、Weather Icons採用revision、StyleX 0.19.0の上流LICENSE、ローカルの固定npm依存を確認した。Noto Sans JPのOFLと通常依存・推移依存10パッケージの著作権表示・ライセンス全文、星アイコンの作者・出典・変更点・OFL本文をfrontend/public/THIRD-PARTY-NOTICES.txtへまとめた。StyleXのnpm配布物はLICENSEを含まないため、同版の上流本文を用いた。

READMEは概要・技術スタック・起動方法の3項目を維持し、技術スタックからdocs/LICENSES.mdへリンクした。frontend/README・REFERENCES・CHANGELOGを同期した。本体のライセンスを新規に選択していない。case1〜case3の商品画像は現在Git追跡済みだが、既存資料の利用・再配布条件は未確認であり、通知追加では解消しない点も明記した。画像は変更していない。

最初のnpm run buildはリポジトリ直下で実行したためpackage.jsonがなく失敗し、frontendから再実行して成功した。固定版10件と通知の版一致、手元LICENSE全文の包含、アイコン帰属、publicとdistの通知・OFL本文のbyte一致、READMEの主見出し3件を確認した。Markdownのリンク・見出し・コードフェンス検査とgit diff --checkも成功した。外部サービスやUI操作の検証は行っておらず、Python環境全体・別途モデル・評価画像の配布許諾を網羅的に確認した結果ではない。前のREADME整理を保持し、今回の変更は未コミット。


## 243. Streamlitを削除（2026-09-11）

利用者指示によりapp.py、src/ui/streamlit_ui.py、専用のtests/test_streamlit_ui.py（3件）、SHOW_DEBUG_INFO設定と.env.exampleの項目、Streamlit依存を削除した。CLIの検索パイプライン、React + StyleXのオフラインモック、既存の機密パス除外は維持した。旧画面仕様はdocs/old/STREAMLIT.mdへ移し、現在のREADME・設計・要件・開発手順・課題・参照をCLIとReactへ同期した。

uv lock --offlineでStreamlitと専用依存を除去し、通常依存だけの環境へ同期したところ、既存テストがStreamlitの推移依存jsonschemaを暗黙に使っており、収集時に18 errorsとなった。jsonschemaを開発用依存として明示し、テスト内容を弱めずに再実行した。最終lockは107から85パッケージへ減り、残存パッケージのバージョン変更はない。通常依存のみの検証後、事前に存在していたlexicalオプション依存をoffline同期で復元し、Streamlitが未インストールのままであることを確認した。

Python 3.13.13でuv run --frozen --offline --no-sync pytest -m 'not live_api'は3045 passed / 20 skipped / 30 deselected（74.01秒）。CLI --help、Streamlitのruntime不在、lock検査、Ruff check/format（369 files）、現行Markdownと移動した旧画面資料のリンク・見出し・コードフェンス、git diff --checkが成功した。実検索・外部API・Bonsaiは実行していない。既存のREADME整理・第三者通知の未コミット変更を保持した。今回のcommit/pushと変更後GitHub CIは未実行。


## 244. 確認報告を第三者ライセンス表記へ変更（2026-09-11）

利用者の訂正に従い、確認結果を説明する未コミットのdocs/LICENSES.mdを削除した。READMEの技術スタック内に使用資材のライセンス名を明記し、著作権表示・許諾文・免責文・変更通知を含むTHIRD-PARTY-NOTICES.txtへ直接リンクした。通知冒頭の調査・更新手順の説明を除き、ライセンス全文と帰属表記は維持した。REFERENCES・CHANGELOGの参照も更新した。Markdownリンクとgit diff --checkが成功。変更は未コミット。


## 245. READMEの技術スタックを詳細化（2026-09-11）

利用者指定により技術スタックを技術名・用途・構成の表へ拡張し、JMdict・Japanese WordNet・GiNZA・文脈照合用ONNXモデル・OPUS-MT翻訳・SigLIP 2と旧CLIP互換・画像生成・保存・検証を記載した。既存CLI、候補検索、Reactオフラインモックの接続範囲を区別し、辞書の任意依存と資材準備へのリンクを追加した。技術スタックからフォント名を除き、配布用の第三者ライセンス本文は維持した。

記載はpyproject.toml、現行バックエンド設計、辞書・翻訳workerの実装と照合した。READMEの主見出し3項目、Markdownリンクとgit diff --checkが成功。文書のみの変更で、実サービスやモデルの実行は行っていない。変更は未コミット。
