# AI相互レビュー・ハーネス運用Runbook

## 1. 文書の役割

この文書は、amazon-explorer のAI相互レビュー・ハーネスを運用するための、実行コマンド、期待結果、停止条件、再実行規則の正本である。現在の進捗、過去のhost・release・digest、実装内部の詳細、モデル料金の固定値はここへ重複させない。

| 確認したいこと | 正本 |
|---|---|
| 作業規則、承認、検証方法 | [AGENTS.md](../AGENTS.md)、[DEVELOPMENT.md](DEVELOPMENT.md) |
| 現在の到達状態と未完了項目 | [GOAL.md](GOAL.md)、[EXEC-002](GOAL.md#exec-002-attested-ai-review境界の実装) |
| AIレビュー契約、TaskSpec、TDD証拠 | [統合済みAIレビュー規約](DEVELOPMENT.md#統合済みaiレビュー規約) |
| credential、mount、egress、nonceの信頼境界 | [SECURITY.md](SECURITY.md) |
| 過去のhost配備、release、digest、検証件数 | [WORKLOG.md](WORKLOG.md) |
| 現行CLI、schema、policy、テスト | `tools/ai_review/`、`specs/`、`tests/` |
| 外部公式資料 | [REFERENCES.md](REFERENCES.md) |

このRunbookと実装が食い違う場合は実行を止め、CLIの `--help`、実装、テストを確認してから文書を更新する。古いRunbookの値や [WORKLOG.md](WORKLOG.md) の過去実績を、現在の承認値として再利用しない。

商品検索の正本providerはBonsaiである。ここで扱うOpenAI経路はAIレビュー専用であり、商品検索からOpenAIへのfallbackではない。

## 2. 実行区分と証拠境界

| 区分 | 外部通信 | credential | host状態の変更 | 必要な権限・承認 | 成功が証明する範囲 |
|---|---:|---:|---:|---|---|
| local offline検証 | 禁止。`uv --offline` とPython guardを使うがOS-level遮断ではない | なし | checkout内の事前準備済み環境だけ | 通常のlocal検証権限 | lock、lint、format、offline test、diff |
| host情報診断 | 禁止。clean環境でlocal Podman情報だけを読む | なし | 意図的な変更なし | 対象hostの読取り権限 | user、path、rootless Podman前提の観測値 |
| release build・install | registry/package通信の場合あり | OpenAI credentialなし | image store、release、user、権限を変更 | 対象・通信先・rollbackの明示承認 | 承認済みassetを構築・配置できたこと |
| `--deployment-check` | external networkなし | なし | smoke containerを作成・削除 | 対象releaseとrootless storeの実行承認 | `nonlive_ready`。live APIやproduction E2Eではない |
| full `--workflow` | OpenAI APIあり | あり | container、network、ledger、artifactを作成 | 実行ごとの外部送信・credential・費用承認 | 7 phaseのlive実行とattested結果 |

証拠ラベルを混同しない。

- offline成功は、実サービス、実host隔離、外部API、課金を証明しない。
- `status="nonlive_ready"` は、credentialを読まず外部networkを作らない配備前検査の成功だけを表す。
- `status="complete"` は7 phaseを完了したことを表すが、結果の採用やGit操作を自動承認しない。
- attested `pass` でも `human_approval_required=true` である。commit、push、merge、追加の外部送信は別権限である。

## 3. 承認と停止の境界

localの読取り・offline検証を越える前に、該当する操作を人間が明示承認する。

1. package導入、image pull/build、user・subuid/subgid・権限・system pathの変更
2. 対象release、4つのimage digest、Python、TaskSpec、manifest、candidate patch
3. 外部送信先、送信するreview packetの範囲、model、service tier、最大attempt、timeout
4. reviewer/adversary credentialの利用、token上限、費用上限、保存・削除方針
5. signing key、broker ledger、nonce ledgerのcustody、backup、rotation、retention

次のいずれかなら即時停止する。

- 承認値が空、形式不正、別経路で照合できない、または現在のassetと不一致
- rootless Podman、user namespace、seccomp、coordinatorとcandidateの別UIDを確認できない
- trusted pathがsymlink、candidate所有、group/world writable、またはowner/mode不正
- Python、task、harness、schema、policy、公開鍵、image、phase chainのdigest不一致
- `.env*`、cache、credential、利用者入力、Git metadataなどの禁止対象がpacketやartifactへ入る
- candidate、private key、nonce ledgerを許可されていないphaseへmountしようとする
- reviewer/adversaryの独立したsession・network lifecycleを作れない
- gatewayの固定egress、credential不在、cleanupとabsenceを証明できない
- attempt、token、費用、時間、byte、processの承認上限へ達した
- 送信済み・課金済みかを証拠から判定できない。この場合は「不明」と記録する
- 対象、送信内容、削除範囲、費用の解釈が実行中に変わった

秘密値をargv、親processの環境、ログ、標準出力、artifact、文書へ置かない。credentialを扱うshellで `set -x` を使わない。

## 4. 正規workflowと必須入力

phase名と順序は固定である。

```text
snapshot
  -> red-snapshot
  -> offline
  -> review-packet
  -> broker
  -> sign
  -> attested-judge
  -> human approval
```

飛越し、並替え、同一phaseの再利用、途中再開を行わない。失敗または中断時は、新しい `workflow_id`、initial artifact root、workflow output root、broker ledgerで最初から実行する。永続nonce ledgerはreplay防止の記録であり、失敗回避のために削除・初期化しない。

実行前に、少なくとも次の入力を外部承認記録と照合する。

| 入力 | 契約 |
|---|---|
| `APPROVED_RELEASE_SOURCE` | 人手監査済みcommitのprotected clean checkout。現在のdirty worktreeを使わない |
| `RELEASE_ID` | 承認済みcommitの40桁lowercase hex |
| `APPROVED_PYTHON` | symlinkでないroot-owned executable。manifestとlauncherがinode/digestを再検証する |
| `APPROVED_UV` | symlinkでないroot-owned `uv` executable。release用Python環境の起動だけに使う |
| `APPROVED_UV_PROJECT_ENVIRONMENT` | checkout外に固定したroot-owned environment。candidateとrelease operatorから書換不能にする |
| `APPROVED_TASK` | 具体化・承認済みTaskSpec v2。placeholderやbootstrap v1を使わない |
| `APPROVED_MANIFEST_SHA256` | install先とは別経路の署名済みrelease記録から受け取る |
| `PROTECTED_CANDIDATE_REPO` | coordinator用のstandalone、clean、single-commit candidate |
| `CANDIDATE_UID` | coordinatorとは異なる正のUID |
| `HUMAN_APPROVED_PATCH_SHA256` | candidateのcanonical patchを人間が承認した64桁hex |
| 4 image | roleごとに異なる `name@sha256:...` とmanifest用 `sha256:...` |
| private path | artifact、key、broker ledger、nonce ledger。symlink-freeかつowner/modeを固定 |

現行repository内の `specs/tasks/TASK-006-ai-review-harness.task.json` は意図的なbootstrap v1、`specs/tasks/example.task.json` はゼロ埋めplaceholderを含む例である。どちらもproductionの `APPROVED_TASK` として使わない。

4 imageの変数対応は次に固定する。

| role | build tag | manifest入力 | launcher入力 |
|---|---|---|---|
| coordinator | `COORDINATOR_TAG` | `COORDINATOR_DIGEST` / `--coordinator-image-digest` | `COORDINATOR_IMAGE` / `--coordinator-image` |
| offline runner | `RUNNER_TAG` | `RUNNER_DIGEST` / `--offline-runner-image-digest` | `OFFLINE_IMAGE` / `--offline-image` |
| broker | `BROKER_TAG` | `BROKER_DIGEST` / `--broker-image-digest` | `BROKER_IMAGE` / `--broker-image` |
| gateway | `GATEWAY_TAG` | `GATEWAY_DIGEST` / `--broker-gateway-image-digest` | `BROKER_GATEWAY_IMAGE` / `--broker-gateway-image` |

`*_DIGEST` は `sha256:` 付きdigest、`*_IMAGE` は対応する `name@sha256:...` でなければならない。tagや同一digestの使い回しをmanifestへ入れない。

## 5. local offline検証

### 5.1 依存環境の準備

`uv sync` はcache不足時にpackage indexへ通信し得る。依存準備はoffline検証と分け、通信先と変更範囲を承認した環境で一度だけ行う。

```bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"
uv sync --locked
```

通信を許可していない場合は上記を実行しない。必要なpackageと既存 `.venv` が揃っていなければ、offline検証はfail closedで停止する。

### 5.2 通信を許可しない検証

準備済み環境で次を実行する。

```bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

uv lock --check --offline
uv run --frozen --offline --no-sync ruff check .
uv run --frozen --offline --no-sync ruff format --check .
uv run --frozen --offline --no-sync pytest -m 'not live_api'
git diff --check
```

ハーネス境界だけを確認する場合は、現行test名へ追随するglobを使う。

```bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

uv run --frozen --offline --no-sync pytest -q \
  tests/test_ai_review_*.py \
  tests/test_network_policy.py \
  -m 'not live_api'
```

権限関連の通常テストは、テスト用Pythonコピーと合成所有者情報を用い、rootを必要としない。実所有者変更を検証するroot専用テストは通常ユーザーでは明示的にskipする。通常テストのためにCI全体をsudoで実行したり、本体のACL拒否を無効化したりしない。

固定のテスト件数を成功条件にしない。pytestのnetwork guardはPython processの補助防御であり、subprocessやnative codeをOSレベルで遮断した証拠ではない。

## 6. production hostの情報診断

この節はpackage、user、権限、imageを変更しない。`podman info` はlauncherと同じ専用非rootuserの既存login sessionで実行する。Dockerやrootful Podmanへfallbackしない。

```bash
set -euo pipefail

: "${REVIEW_USER:?set the approved coordinator OS user}"
: "${CANDIDATE_USER:?set the approved candidate OS user}"
: "${TRUSTED_PREFIX:?set the approved trusted release prefix}"
: "${STATE_ROOT:?set the approved private state root}"

review_uid=$(id -u "$REVIEW_USER")
candidate_uid=$(id -u "$CANDIDATE_USER")
review_home=$(getent passwd "$REVIEW_USER" | awk -F: 'NR == 1 {print $6}')

test "$review_uid" -gt 0
test "$candidate_uid" -gt 0
test "$review_uid" -ne "$candidate_uid"
test -n "$review_home"
test "${review_home#/}" != "$review_home"

command -v podman
getent passwd "$REVIEW_USER" "$CANDIDATE_USER"
awk -F: -v user="$REVIEW_USER" \
  '$1 == user { print; found = 1 } END { exit found ? 0 : 1 }' \
  /etc/subuid
awk -F: -v user="$REVIEW_USER" \
  '$1 == user { print; found = 1 } END { exit found ? 0 : 1 }' \
  /etc/subgid

for path in "$review_home" "$TRUSTED_PREFIX" "$STATE_ROOT"; do
  if test -e "$path"; then
    stat -c '%U:%G %a %h %F %n' "$path"
  fi
done
```

次は `REVIEW_USER` として開始済みの非root login sessionで実行する。launcherが固定する7変数を明示するが、この手動観測だけをproduction証拠にはしない。

```bash
set -euo pipefail

: "${REVIEW_USER:?set the approved coordinator OS user}"
test "$(id -un)" = "$REVIEW_USER"
test "$(id -u)" -ne 0

review_uid=$(id -u)
review_home=$(getent passwd "$review_uid" | awk -F: 'NR == 1 {print $6}')
xdg_config_home="$review_home/.config"
xdg_data_home="$review_home/.local/share"
xdg_runtime_dir="/run/user/$review_uid"
storage_conf="$xdg_config_home/containers/storage.conf"

for path in \
  "$review_home" \
  "$xdg_config_home" \
  "$xdg_data_home" \
  "$xdg_runtime_dir"; do
  test -d "$path"
  test ! -L "$path"
  stat -c '%U:%G %a %h %F %n' "$path"
done

test -f "$storage_conf"
test ! -L "$storage_conf"
stat -c '%U:%G %a %h %F %n' "$storage_conf"

/usr/bin/env -i \
  CONTAINERS_STORAGE_CONF="$storage_conf" \
  HOME="$review_home" \
  LC_ALL=C \
  PATH=/bin:/usr/bin \
  XDG_CONFIG_HOME="$xdg_config_home" \
  XDG_DATA_HOME="$xdg_data_home" \
  XDG_RUNTIME_DIR="$xdg_runtime_dir" \
  podman info --format json

/usr/bin/env -i \
  CONTAINERS_STORAGE_CONF="$storage_conf" \
  HOME="$review_home" \
  LC_ALL=C \
  PATH=/bin:/usr/bin \
  XDG_CONFIG_HOME="$xdg_config_home" \
  XDG_DATA_HOME="$xdg_data_home" \
  XDG_RUNTIME_DIR="$xdg_runtime_dir" \
  podman unshare cat /proc/self/uid_map
```

次を確認する。

- rootless、user namespace、seccompが有効で、seccompが `unconfined` ではない
- `store.graphRoot`、`store.runRoot`、`store.configFile` が承認済みprivate path内にある
- active `storage.conf` に迂回用の `imagestore` / `additionalimagestores` がない
- HOME、XDG path、storage config、trusted release、private stateの祖先がsymlinkでなく、candidateから書換不能
- 4 imageを専用userのrootless storeからdigest付き参照で解決できる

不足を直すpackage導入、user追加、subuid/subgid割当、ACL・owner・mode変更、login/linger設定、directory作成、image pull/buildは別のsystem変更である。対象とrollbackを承認してから行い、この診断へ混ぜない。

## 7. trusted releaseの構築と配置

### 7.1 前提

releaseは `APPROVED_RELEASE_SOURCE` の人手監査済みclean commitから作る。sourceと、`APPROVED_UV` から `uv run --frozen --offline --no-sync --no-env-file` で起動できる `APPROVED_UV_PROJECT_ENVIRONMENT` を、candidateから書換不能な場所に用意する。environmentはcheckout外でroot-ownedに凍結し、release scriptを実行する非root `REVIEW_USER` からも書換不能にする。このsource/environmentの配置自体もrelease工程であり、存在しない場合は後続の `workflow-init` へ進まない。

sourceを読む各scriptは、Git検査の前後とsource command完了後にcheckout全体を再帰検査する。別device、symlink、特殊file、hardlinkされたregular file、candidateまたはoperator/root以外が所有するentry、group/world書込み可能entryを1件でも含むsourceは使わない。`.git` はcheckout直下のprotected directoryに固定し、外部gitdirを使わない。Gitのtracked stateに含まれないuntracked / ignored entryもclean扱いにしない。仮想環境やcacheは、権限を緩めずcheckout外のprotected environmentへ分離する。

`APPROVED_UV_PROJECT_ENVIRONMENT` はroot-ownedのdirectory / regular fileと、同environment内または別のroot-owned non-hardlinked regular fileへ解決されるsymlinkだけを許す。事前準備ではpackage取得とenvironment作成を明示承認し、copy modeで構築してroot所有へ凍結する。Runbookのrelease script内ではsyncや修復を行わない。`/usr/bin/env -i` のallowlist環境で `UV_PROJECT_ENVIRONMENT` と `--project` をexact pathへ固定し、`--no-env-file` と `--no-config` で親shellのPython / loader / uv設定を継承しない。

次を満たす具体的なTaskSpec v2を別途作成し、raw bytesを承認する。

- 実在するbase commit、candidate、test path、RED fingerprint
- 作成するharnessのSHA-256
- allowed/denied path、変更量、network policy
- reviewer/adversary prompt digest
- token、費用、attemptのrelease上限と整合する要求

4 imageのbase取得、package取得、build、registry利用はOpenAI APIとは別の外部通信である。承認済みbuild networkでだけ行い、OpenAI credentialを渡さない。

```bash
set -euo pipefail

: "${APPROVED_RELEASE_SOURCE:?}"
: "${RELEASE_ID:?}"
: "${CANDIDATE_UID:?}"
: "${COORDINATOR_TAG:?}"
: "${RUNNER_TAG:?}"
: "${BROKER_TAG:?}"
: "${GATEWAY_TAG:?}"

[[ "$RELEASE_ID" =~ ^[0-9a-f]{40}$ ]]
test "$CANDIDATE_UID" -gt 0
test "$(id -u)" -ne "$CANDIDATE_UID"

approved_source=$(/usr/bin/readlink -e -- "$APPROVED_RELEASE_SOURCE")
test "$approved_source" = "$APPROVED_RELEASE_SOURCE"
source_ancestor=$approved_source
while :; do
  source_owner=$(stat -c '%u' "$source_ancestor")
  source_mode=$(stat -c '%a' "$source_ancestor")
  test "$source_owner" -eq 0 || test "$source_owner" -eq "$(id -u)"
  (( (8#$source_mode & 0022) == 0 ))
  if test "$source_ancestor" = /; then
    break
  fi
  source_ancestor=$(dirname -- "$source_ancestor")
done

validate_release_source_tree() {
  local root=$1
  local root_device entry entry_device entry_owner entry_mode_hex entry_mode entry_type
  root_device=$(stat -c '%d' -- "$root")
  find -P "$root" -xdev -print0 |
    while IFS= read -r -d '' entry; do
      entry_device=$(stat -c '%d' -- "$entry")
      entry_owner=$(stat -c '%u' -- "$entry")
      entry_mode_hex=$(stat -c '%f' -- "$entry")
      entry_mode=$((16#$entry_mode_hex))
      entry_type=$((entry_mode & 0170000))

      test "$entry_device" = "$root_device"
      test "$entry_owner" -ne "$CANDIDATE_UID"
      test "$entry_owner" -eq 0 || test "$entry_owner" -eq "$(id -u)"
      (( (entry_mode & 0022) == 0 ))
      if (( entry_type == 0040000 )); then
        continue
      fi
      if (( entry_type == 0100000 )); then
        test "$(stat -c '%h' -- "$entry")" = 1
        continue
      fi
      printf '%s\n' 'release source contains a symlink or special file' >&2
      return 2
    done
}

validate_release_source_tree "$approved_source"
test -d "$approved_source/.git"
test ! -L "$approved_source/.git"
cd "$approved_source"
source_root=$(/usr/bin/readlink -e -- "$(git rev-parse --show-toplevel)")
test "$source_root" = "$approved_source"
git_dir=$(/usr/bin/readlink -e -- "$(git rev-parse --absolute-git-dir)")
test "$git_dir" = "$approved_source/.git"
test "$(git rev-parse HEAD)" = "$RELEASE_ID"
release_git_status=$(
  GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_OPTIONAL_LOCKS=0 \
    git -c core.fsmonitor=false -c core.untrackedCache=false \
    status --porcelain=v1 --untracked-files=all \
    --ignored=matching --ignore-submodules=none
)
test -z "$release_git_status"
validate_release_source_tree "$approved_source"

podman build --pull=never \
  -f containers/ai-review-coordinator/Dockerfile \
  -t "$COORDINATOR_TAG" .
podman build --pull=never \
  -f containers/ai-review-runner/Dockerfile \
  -t "$RUNNER_TAG" .
podman build --pull=never \
  -f containers/ai-review-broker/Dockerfile \
  -t "$BROKER_TAG" .
podman build --pull=never \
  -f containers/ai-review-egress/Dockerfile \
  -t "$GATEWAY_TAG" .

validate_release_source_tree "$approved_source"
test "$(git rev-parse HEAD)" = "$RELEASE_ID"
post_image_source_status=$(
  GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_OPTIONAL_LOCKS=0 \
    git -c core.fsmonitor=false -c core.untrackedCache=false \
    status --porcelain=v1 --untracked-files=all \
    --ignored=matching --ignore-submodules=none
)
test -z "$post_image_source_status"
```

`--pull=never` は暗黙pullを禁止するが、Dockerfile内のpackage取得までofflineにしない。release管理者は4 roleのimmutable digestを別々に確定し、前節の対応表どおり `*_DIGEST` と `*_IMAGE` を承認記録へ固定する。digest付き参照を作れないimageは使わない。

### 7.2 signing keyを新規provisionまたはrotationする

通常releaseは既存の承認済みkey pairを再利用し、この節を実行しない。初回provisionまたはrotationだけ、custody、旧署名の検証継続、backup、rollback、新しいkey pathを明示承認してから実行する。既存private keyを上書きしない。

次は専用 `REVIEW_USER` のprotected sessionで、新規key directoryへだけ書く。失敗時にできたdirectoryを再利用・自動削除しない。

```bash
set -euo pipefail
umask 077

: "${APPROVED_RELEASE_SOURCE:?}"
: "${RELEASE_ID:?}"
: "${REVIEW_USER:?}"
: "${CANDIDATE_UID:?}"
: "${APPROVED_UV:?}"
: "${APPROVED_UV_PROJECT_ENVIRONMENT:?}"
: "${NEW_KEY_DIRECTORY:?}"

[[ "$RELEASE_ID" =~ ^[0-9a-f]{40}$ ]]
test "$CANDIDATE_UID" -gt 0
[[ "$APPROVED_UV_PROJECT_ENVIRONMENT" = /* && \
  "$APPROVED_UV_PROJECT_ENVIRONMENT" != / ]]
[[ "$NEW_KEY_DIRECTORY" = /* && "$NEW_KEY_DIRECTORY" != / ]]
test "$(id -un)" = "$REVIEW_USER"
test "$(id -u)" -ne 0
test "$(id -u)" -ne "$CANDIDATE_UID"
test ! -e "$NEW_KEY_DIRECTORY"
test ! -L "$NEW_KEY_DIRECTORY"

require_protected_existing_path() {
  local path=$1
  local canonical current owner mode
  [[ "$path" = /* ]]
  canonical=$(/usr/bin/readlink -e -- "$path")
  test "$canonical" = "$path"
  current=$path
  while :; do
    owner=$(stat -c '%u' "$current")
    mode=$(stat -c '%a' "$current")
    if test "$owner" -ne 0 && test "$owner" -ne "$(id -u)"; then
      test -n "${review_uid:-}"
      test "$owner" -eq "$review_uid"
    fi
    (( (8#$mode & 0022) == 0 ))
    if test "$current" = /; then
      break
    fi
    current=$(dirname -- "$current")
  done
}

require_root_owned_existing_path() {
  local path=$1
  local canonical current mode
  [[ "$path" = /* ]]
  canonical=$(/usr/bin/readlink -e -- "$path")
  test "$canonical" = "$path"
  current=$path
  while :; do
    test "$(stat -c '%u:%g' "$current")" = 0:0
    mode=$(stat -c '%a' "$current")
    (( (8#$mode & 0022) == 0 ))
    if test "$current" = /; then
      break
    fi
    current=$(dirname -- "$current")
  done
}

validate_release_source_tree() {
  local root=$1
  local root_device entry entry_device entry_owner entry_mode_hex entry_mode entry_type
  root_device=$(stat -c '%d' -- "$root")
  find -P "$root" -xdev -print0 |
    while IFS= read -r -d '' entry; do
      entry_device=$(stat -c '%d' -- "$entry")
      entry_owner=$(stat -c '%u' -- "$entry")
      entry_mode_hex=$(stat -c '%f' -- "$entry")
      entry_mode=$((16#$entry_mode_hex))
      entry_type=$((entry_mode & 0170000))

      test "$entry_device" = "$root_device"
      test "$entry_owner" -ne "$CANDIDATE_UID"
      test "$entry_owner" -eq 0 || test "$entry_owner" -eq "$(id -u)"
      (( (entry_mode & 0022) == 0 ))
      if (( entry_type == 0040000 )); then
        continue
      fi
      if (( entry_type == 0100000 )); then
        test "$(stat -c '%h' -- "$entry")" = 1
        continue
      fi
      printf '%s\n' 'release source contains a symlink or special file' >&2
      return 2
    done
}

validate_root_owned_uv_environment() {
  local root=$1
  local root_device entry entry_device entry_owner entry_mode_hex entry_mode entry_type
  local resolved resolved_mode
  root_device=$(stat -c '%d' -- "$root")
  find -P "$root" -xdev -print0 |
    while IFS= read -r -d '' entry; do
      entry_owner=$(stat -c '%u' -- "$entry")
      entry_mode_hex=$(stat -c '%f' -- "$entry")
      entry_mode=$((16#$entry_mode_hex))
      entry_type=$((entry_mode & 0170000))
      test "$entry_owner" -eq 0

      if (( entry_type == 0120000 )); then
        resolved=$(/usr/bin/readlink -e -- "$entry")
        case "$resolved" in
          "$root"|"$root"/*) ;;
          *)
            require_root_owned_existing_path "$resolved"
            test -f "$resolved"
            test "$(stat -c '%h' -- "$resolved")" = 1
            resolved_mode=$(stat -c '%a' -- "$resolved")
            (( (8#$resolved_mode & 06000) == 0 ))
            ;;
        esac
        continue
      fi

      entry_device=$(stat -c '%d' -- "$entry")
      test "$entry_device" = "$root_device"
      (( (entry_mode & 06022) == 0 ))
      if (( entry_type == 0040000 )); then
        continue
      fi
      if (( entry_type == 0100000 )); then
        test "$(stat -c '%h' -- "$entry")" = 1
        continue
      fi
      printf '%s\n' 'approved uv environment contains an unsafe entry' >&2
      return 2
    done
}

key_parent=$(dirname -- "$NEW_KEY_DIRECTORY")
require_protected_existing_path "$key_parent"
test "$(stat -c '%a' "$key_parent")" = 700
test "$(stat -c '%u:%g' "$key_parent")" = "$(id -u):$(id -g)"
test "$(/usr/bin/readlink -m -- "$NEW_KEY_DIRECTORY")" = "$NEW_KEY_DIRECTORY"

approved_source=$(/usr/bin/readlink -e -- "$APPROVED_RELEASE_SOURCE")
test "$approved_source" = "$APPROVED_RELEASE_SOURCE"
require_protected_existing_path "$approved_source"
validate_release_source_tree "$approved_source"
test -d "$approved_source/.git"
test ! -L "$approved_source/.git"

require_root_owned_existing_path "$APPROVED_UV"
test -f "$APPROVED_UV"
test "$(stat -c '%h' "$APPROVED_UV")" = 1
test -x "$APPROVED_UV"
approved_uv_mode=$(stat -c '%a' "$APPROVED_UV")
(( (8#$approved_uv_mode & 06000) == 0 ))
approved_uv_environment=$(
  /usr/bin/readlink -e -- "$APPROVED_UV_PROJECT_ENVIRONMENT"
)
test "$approved_uv_environment" = "$APPROVED_UV_PROJECT_ENVIRONMENT"
require_root_owned_existing_path "$approved_uv_environment"
test -d "$approved_uv_environment"
validate_root_owned_uv_environment "$approved_uv_environment"

case "$approved_uv_environment/" in
  "$approved_source/"*)
    printf '%s\n' 'approved uv environment must be outside the release source' >&2
    exit 2
    ;;
esac
case "$approved_source/" in
  "$approved_uv_environment/"*)
    printf '%s\n' 'release source must be outside the approved uv environment' >&2
    exit 2
    ;;
esac

run_approved_uv() {
  /usr/bin/env -i \
    GIT_CONFIG_GLOBAL=/dev/null \
    GIT_CONFIG_NOSYSTEM=1 \
    GIT_OPTIONAL_LOCKS=0 \
    HOME=/nonexistent \
    LC_ALL=C \
    PATH=/bin:/usr/bin \
    PYTHONHASHSEED=0 \
    PYTHONNOUSERSITE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT="$approved_uv_environment" \
    "$APPROVED_UV" run --project "$approved_source" \
    --frozen --offline --no-sync --no-env-file --no-cache --no-config \
    "$@"
}

cd "$approved_source"
source_root=$(/usr/bin/readlink -e -- "$(git rev-parse --show-toplevel)")
test "$source_root" = "$approved_source"
git_dir=$(/usr/bin/readlink -e -- "$(git rev-parse --absolute-git-dir)")
test "$git_dir" = "$approved_source/.git"
test "$(git rev-parse HEAD)" = "$RELEASE_ID"
key_source_status=$(
  GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_OPTIONAL_LOCKS=0 \
    git -c core.fsmonitor=false -c core.untrackedCache=false \
    status --porcelain=v1 --untracked-files=all \
    --ignored=matching --ignore-submodules=none
)
test -z "$key_source_status"
validate_release_source_tree "$approved_source"

case "$NEW_KEY_DIRECTORY/" in
  "$source_root/"*)
    printf '%s\n' 'key directory must be outside the approved Git checkout' >&2
    exit 2
    ;;
esac

mkdir -m 0700 "$NEW_KEY_DIRECTORY"
run_approved_uv python \
  -m tools.ai_review.runtime_release keygen \
  --private-key "$NEW_KEY_DIRECTORY/coordinator-private.pem" \
  --public-key "$NEW_KEY_DIRECTORY/coordinator-public.pem"

validate_release_source_tree "$approved_source"
test "$(git rev-parse HEAD)" = "$RELEASE_ID"
post_key_source_status=$(
  GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_OPTIONAL_LOCKS=0 \
    git -c core.fsmonitor=false -c core.untrackedCache=false \
    status --porcelain=v1 --untracked-files=all \
    --ignored=matching --ignore-submodules=none
)
test -z "$post_key_source_status"
validate_root_owned_uv_environment "$approved_uv_environment"

chmod 0400 "$NEW_KEY_DIRECTORY/coordinator-private.pem"
chmod 0444 "$NEW_KEY_DIRECTORY/coordinator-public.pem"
sha256sum "$NEW_KEY_DIRECTORY/coordinator-public.pem"
```

公開鍵bytesとSHA-256、private key path、key IDを外部custody記録へ固定する。後続では、その記録から `APPROVED_COORDINATOR_PUBLIC_KEY` と `SIGNING_KEY` を受け取る。同一pairであることを別経路で確認できなければreleaseを作らない。

### 7.3 runtime asset、immutable release、manifestを作る

次は管理者が通信、system path、rollbackを承認した後、1つのfail-fast Bash scriptとして実行する。`TRUSTED_PREFIX` は既存のroot-owned release親、`APPROVED_STATE_ROOT` は既存の専用private stateである。`RELEASE_ROOT` は `TRUSTED_PREFIX/RELEASE_ID` からscript内で一意に導出し、既存pathを拒否する。

`PACKET_RESERVATION_LIMIT` と `PACKET_COST_LIMIT_MICROUSD` は、pinned policy、実装上限、実行承認を照合して決める。Runbookの過去値を流用しない。通常releaseはprivate keyを読み書きせず、外部custody記録で承認済みの公開鍵だけをroot-owned releaseへ複製する。

```bash
set -euo pipefail
umask 077

: "${APPROVED_RELEASE_SOURCE:?}"
: "${RELEASE_ID:?}"
: "${TRUSTED_PREFIX:?}"
: "${APPROVED_STATE_ROOT:?}"
: "${REVIEW_USER:?}"
: "${REVIEW_GROUP:?}"
: "${CANDIDATE_UID:?}"
: "${APPROVED_TASK:?}"
: "${APPROVED_COORDINATOR_PUBLIC_KEY:?}"
: "${SIGNING_KEY:?}"
: "${APPROVED_PYTHON:?}"
: "${APPROVED_UV:?}"
: "${APPROVED_UV_PROJECT_ENVIRONMENT:?}"
: "${COORDINATOR_DIGEST:?}"
: "${RUNNER_DIGEST:?}"
: "${BROKER_DIGEST:?}"
: "${GATEWAY_DIGEST:?}"
: "${PACKET_RESERVATION_LIMIT:?}"
: "${PACKET_COST_LIMIT_MICROUSD:?}"

[[ "$RELEASE_ID" =~ ^[0-9a-f]{40}$ ]]
[[ "$TRUSTED_PREFIX" = /* && "$TRUSTED_PREFIX" != / ]]
[[ "$APPROVED_STATE_ROOT" = /* && "$APPROVED_STATE_ROOT" != / ]]
[[ "$APPROVED_UV_PROJECT_ENVIRONMENT" = /* && \
  "$APPROVED_UV_PROJECT_ENVIRONMENT" != / ]]
test "$CANDIDATE_UID" -gt 0
test "$(id -u)" -ne "$CANDIDATE_UID"

RELEASE_ROOT="$TRUSTED_PREFIX/$RELEASE_ID"
STATE_ROOT="$APPROVED_STATE_ROOT"
test ! -e "$RELEASE_ROOT"
test ! -L "$RELEASE_ROOT"
test "$(/usr/bin/readlink -m -- "$RELEASE_ROOT")" = "$RELEASE_ROOT"

require_protected_existing_path() {
  local path=$1
  local canonical current owner mode
  [[ "$path" = /* ]]
  canonical=$(/usr/bin/readlink -e -- "$path")
  test "$canonical" = "$path"
  current=$path
  while :; do
    owner=$(stat -c '%u' "$current")
    mode=$(stat -c '%a' "$current")
    if test "$owner" -ne 0 && test "$owner" -ne "$(id -u)"; then
      test -n "${review_uid:-}"
      test "$owner" -eq "$review_uid"
    fi
    (( (8#$mode & 0022) == 0 ))
    if test "$current" = /; then
      break
    fi
    current=$(dirname -- "$current")
  done
}

validate_root_owned_uv_environment() {
  local root=$1
  local root_device entry entry_device entry_owner entry_mode_hex entry_mode entry_type
  local resolved resolved_mode
  root_device=$(stat -c '%d' -- "$root")
  find -P "$root" -xdev -print0 |
    while IFS= read -r -d '' entry; do
      entry_owner=$(stat -c '%u' -- "$entry")
      entry_mode_hex=$(stat -c '%f' -- "$entry")
      entry_mode=$((16#$entry_mode_hex))
      entry_type=$((entry_mode & 0170000))
      test "$entry_owner" -eq 0

      if (( entry_type == 0120000 )); then
        resolved=$(/usr/bin/readlink -e -- "$entry")
        case "$resolved" in
          "$root"|"$root"/*) ;;
          *)
            require_root_owned_existing_path "$resolved"
            test -f "$resolved"
            test "$(stat -c '%h' -- "$resolved")" = 1
            resolved_mode=$(stat -c '%a' -- "$resolved")
            (( (8#$resolved_mode & 06000) == 0 ))
            ;;
        esac
        continue
      fi

      entry_device=$(stat -c '%d' -- "$entry")
      test "$entry_device" = "$root_device"
      (( (entry_mode & 06022) == 0 ))
      if (( entry_type == 0040000 )); then
        continue
      fi
      if (( entry_type == 0100000 )); then
        test "$(stat -c '%h' -- "$entry")" = 1
        continue
      fi
      printf '%s\n' 'approved uv environment contains an unsafe entry' >&2
      return 2
    done
}

require_root_owned_existing_path() {
  local path=$1
  local canonical current mode
  [[ "$path" = /* ]]
  canonical=$(/usr/bin/readlink -e -- "$path")
  test "$canonical" = "$path"
  current=$path
  while :; do
    test "$(stat -c '%u:%g' "$current")" = 0:0
    mode=$(stat -c '%a' "$current")
    (( (8#$mode & 0022) == 0 ))
    if test "$current" = /; then
      break
    fi
    current=$(dirname -- "$current")
  done
}

validate_release_source_tree() {
  local root=$1
  local root_device entry entry_device entry_owner entry_mode_hex entry_mode entry_type
  root_device=$(stat -c '%d' -- "$root")
  find -P "$root" -xdev -print0 |
    while IFS= read -r -d '' entry; do
      entry_device=$(stat -c '%d' -- "$entry")
      entry_owner=$(stat -c '%u' -- "$entry")
      entry_mode_hex=$(stat -c '%f' -- "$entry")
      entry_mode=$((16#$entry_mode_hex))
      entry_type=$((entry_mode & 0170000))

      test "$entry_device" = "$root_device"
      test "$entry_owner" -ne "$CANDIDATE_UID"
      test "$entry_owner" -eq 0 || test "$entry_owner" -eq "$(id -u)"
      (( (entry_mode & 0022) == 0 ))
      if (( entry_type == 0040000 )); then
        continue
      fi
      if (( entry_type == 0100000 )); then
        test "$(stat -c '%h' -- "$entry")" = 1
        continue
      fi
      printf '%s\n' 'release source contains a symlink or special file' >&2
      return 2
    done
}

require_root_owned_existing_path "$TRUSTED_PREFIX"
test "$(stat -c '%u:%g' "$TRUSTED_PREFIX")" = 0:0
test "$(stat -c '%a' "$TRUSTED_PREFIX")" = 755

require_protected_existing_path "$STATE_ROOT"
test "$(stat -c '%u:%g' "$STATE_ROOT")" = 0:0
test "$(stat -c '%a' "$STATE_ROOT")" = 711

review_uid=$(id -u "$REVIEW_USER")
review_gid=$(getent group "$REVIEW_GROUP" | awk -F: 'NR == 1 {print $3}')
test "$review_uid" -gt 0
test "$review_uid" -ne "$CANDIDATE_UID"
test -n "$review_gid"
test "$(id -u)" -eq "$review_uid"
test "$(id -u)" -ne 0

ensure_private_state_directory() {
  local path=$1
  if test -e "$path"; then
    test -d "$path"
    test ! -L "$path"
    test "$(stat -c '%u:%g' "$path")" = "$review_uid:$review_gid"
    test "$(stat -c '%a' "$path")" = 700
  else
    test ! -L "$path"
    test "$(/usr/bin/readlink -m -- "$path")" = "$path"
    sudo mkdir -m 0700 -- "$path"
    sudo chown "$REVIEW_USER:$REVIEW_GROUP" "$path"
  fi
}

ensure_private_state_directory "$STATE_ROOT/artifacts"
ensure_private_state_directory "$STATE_ROOT/broker-ledger"
ensure_private_state_directory "$STATE_ROOT/nonce-ledger"
ensure_private_state_directory "$STATE_ROOT/keys"

test -f "$APPROVED_TASK"
test ! -L "$APPROVED_TASK"
require_protected_existing_path "$APPROVED_TASK"
test -f "$APPROVED_COORDINATOR_PUBLIC_KEY"
test ! -L "$APPROVED_COORDINATOR_PUBLIC_KEY"
require_protected_existing_path "$APPROVED_COORDINATOR_PUBLIC_KEY"
test "$(stat -c '%h' "$APPROVED_COORDINATOR_PUBLIC_KEY")" = 1
public_key_mode=$(stat -c '%a' "$APPROVED_COORDINATOR_PUBLIC_KEY")
(( (8#$public_key_mode & 0222) == 0 ))
test -f "$SIGNING_KEY"
test ! -L "$SIGNING_KEY"
require_protected_existing_path "$SIGNING_KEY"
test "$(stat -c '%a' "$SIGNING_KEY")" = 400
test "$(stat -c '%h' "$SIGNING_KEY")" = 1
test "$(stat -c '%u:%g' "$SIGNING_KEY")" = "$review_uid:$review_gid"

require_root_owned_existing_path "$APPROVED_PYTHON"
test -f "$APPROVED_PYTHON"
test "$(stat -c '%h' "$APPROVED_PYTHON")" = 1
test -x "$APPROVED_PYTHON"
approved_python_mode=$(stat -c '%a' "$APPROVED_PYTHON")
(( (8#$approved_python_mode & 06000) == 0 ))

require_root_owned_existing_path "$APPROVED_UV"
test -f "$APPROVED_UV"
test "$(stat -c '%h' "$APPROVED_UV")" = 1
test -x "$APPROVED_UV"
approved_uv_mode=$(stat -c '%a' "$APPROVED_UV")
(( (8#$approved_uv_mode & 06000) == 0 ))
approved_uv_environment=$(
  /usr/bin/readlink -e -- "$APPROVED_UV_PROJECT_ENVIRONMENT"
)
test "$approved_uv_environment" = "$APPROVED_UV_PROJECT_ENVIRONMENT"
require_root_owned_existing_path "$approved_uv_environment"
test -d "$approved_uv_environment"
validate_root_owned_uv_environment "$approved_uv_environment"

approved_source=$(/usr/bin/readlink -e -- "$APPROVED_RELEASE_SOURCE")
test "$approved_source" = "$APPROVED_RELEASE_SOURCE"
require_protected_existing_path "$approved_source"
validate_release_source_tree "$approved_source"
test -d "$approved_source/.git"
test ! -L "$approved_source/.git"

case "$approved_uv_environment/" in
  "$approved_source/"*)
    printf '%s\n' 'approved uv environment must be outside the release source' >&2
    exit 2
    ;;
esac
case "$approved_source/" in
  "$approved_uv_environment/"*)
    printf '%s\n' 'release source must be outside the approved uv environment' >&2
    exit 2
    ;;
esac

run_approved_uv() {
  /usr/bin/env -i \
    GIT_CONFIG_GLOBAL=/dev/null \
    GIT_CONFIG_NOSYSTEM=1 \
    GIT_OPTIONAL_LOCKS=0 \
    HOME=/nonexistent \
    LC_ALL=C \
    PATH=/bin:/usr/bin \
    PYTHONHASHSEED=0 \
    PYTHONNOUSERSITE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT="$approved_uv_environment" \
    "$APPROVED_UV" run --project "$approved_source" \
    --frozen --offline --no-sync --no-env-file --no-cache --no-config \
    "$@"
}

cd "$approved_source"
source_root=$(/usr/bin/readlink -e -- "$(git rev-parse --show-toplevel)")
test "$source_root" = "$approved_source"
git_dir=$(/usr/bin/readlink -e -- "$(git rev-parse --absolute-git-dir)")
test "$git_dir" = "$approved_source/.git"
test "$(git rev-parse HEAD)" = "$RELEASE_ID"
release_source_status=$(
  GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_OPTIONAL_LOCKS=0 \
    git -c core.fsmonitor=false -c core.untrackedCache=false \
    status --porcelain=v1 --untracked-files=all \
    --ignored=matching --ignore-submodules=none
)
test -z "$release_source_status"
validate_release_source_tree "$approved_source"

release_stage=$(mktemp -d)
chmod 700 "$release_stage"
cleanup_release_stage() {
  if [[ -n ${release_stage:-} && -d $release_stage && $release_stage != / ]]; then
    rm -rf -- "$release_stage"
  fi
}
trap cleanup_release_stage EXIT

run_approved_uv python \
  -m tools.ai_review.build_zipapp \
  --source-root . \
  --output "$release_stage/harness.pyz"

run_approved_uv python \
  -m tools.ai_review.runtime_release schema-bundle \
  --schema-dir specs/schemas \
  --output "$release_stage/schemas.json"

validate_release_source_tree "$approved_source"
test "$(git rev-parse HEAD)" = "$RELEASE_ID"
post_asset_source_status=$(
  GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_OPTIONAL_LOCKS=0 \
    git -c core.fsmonitor=false -c core.untrackedCache=false \
    status --porcelain=v1 --untracked-files=all \
    --ignored=matching --ignore-submodules=none
)
test -z "$post_asset_source_status"
validate_root_owned_uv_environment "$approved_uv_environment"

sudo mkdir -m 0755 -- "$RELEASE_ROOT"
require_root_owned_existing_path "$RELEASE_ROOT"
test "$(stat -c '%u:%g' "$RELEASE_ROOT")" = 0:0
test "$(stat -c '%a' "$RELEASE_ROOT")" = 755
sudo install -d -o root -g root -m 0755 "$RELEASE_ROOT/bin"
sudo install -d -o root -g root -m 0755 "$RELEASE_ROOT/runtime"

sudo install -o root -g root -m 0555 \
  tools/ai_review/external_launcher.py \
  "$RELEASE_ROOT/bin/external_launcher.py"
sudo install -o root -g root -m 0444 \
  tools/ai_review/preflight.py \
  "$RELEASE_ROOT/bin/preflight.py"
sudo install -o root -g root -m 0444 \
  "$release_stage/harness.pyz" \
  "$RELEASE_ROOT/runtime/harness.pyz"
sudo install -o root -g root -m 0444 \
  "$release_stage/schemas.json" \
  "$RELEASE_ROOT/runtime/schemas.json"
sudo install -o root -g root -m 0444 \
  "$APPROVED_COORDINATOR_PUBLIC_KEY" \
  "$RELEASE_ROOT/runtime/coordinator-public.pem"
sudo install -o root -g root -m 0444 \
  uv.lock \
  "$RELEASE_ROOT/runtime/uv.lock"
sudo install -o root -g root -m 0444 \
  "$APPROVED_TASK" \
  "$RELEASE_ROOT/runtime/task.json"
sudo install -o root -g root -m 0444 \
  specs/policies/broker-egress-policy.json \
  "$RELEASE_ROOT/runtime/broker-egress-policy.json"
sudo install -o root -g root -m 0444 \
  specs/policies/openai-pricing-policy.json \
  "$RELEASE_ROOT/runtime/openai-pricing-policy.json"

run_approved_uv python \
  -m tools.ai_review.runtime_release manifest \
  --output "$release_stage/runtime-manifest.json" \
  --python "$APPROVED_PYTHON" \
  --harness "$RELEASE_ROOT/runtime/harness.pyz" \
  --task "$RELEASE_ROOT/runtime/task.json" \
  --dependency-lock "$RELEASE_ROOT/runtime/uv.lock" \
  --schema-bundle "$RELEASE_ROOT/runtime/schemas.json" \
  --coordinator-public-key "$RELEASE_ROOT/runtime/coordinator-public.pem" \
  --broker-egress-policy "$RELEASE_ROOT/runtime/broker-egress-policy.json" \
  --openai-pricing-policy "$RELEASE_ROOT/runtime/openai-pricing-policy.json" \
  --coordinator-image-digest "$COORDINATOR_DIGEST" \
  --offline-runner-image-digest "$RUNNER_DIGEST" \
  --broker-image-digest "$BROKER_DIGEST" \
  --broker-gateway-image-digest "$GATEWAY_DIGEST" \
  --broker-packet-reservation-limit "$PACKET_RESERVATION_LIMIT" \
  --broker-packet-cost-limit-microusd "$PACKET_COST_LIMIT_MICROUSD"

validate_release_source_tree "$approved_source"
test "$(git rev-parse HEAD)" = "$RELEASE_ID"
post_manifest_source_status=$(
  GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_OPTIONAL_LOCKS=0 \
    git -c core.fsmonitor=false -c core.untrackedCache=false \
    status --porcelain=v1 --untracked-files=all \
    --ignored=matching --ignore-submodules=none
)
test -z "$post_manifest_source_status"
validate_root_owned_uv_environment "$approved_uv_environment"

test ! -e "$RELEASE_ROOT/runtime/runtime-manifest.json"
sudo install -o root -g root -m 0444 \
  "$release_stage/runtime-manifest.json" \
  "$RELEASE_ROOT/runtime/runtime-manifest.json"

sha256sum "$RELEASE_ROOT/runtime/runtime-manifest.json"

cleanup_release_stage
trap - EXIT
unset release_stage
```

表示したSHA-256はrelease署名・承認工程へ渡す候補であり、それだけで承認済みにはならない。承認者はmanifest、asset、image、TaskSpec、Python、公開鍵、signing keyのcustody、費用上限を別経路で監査・署名し、production実行者へ `APPROVED_MANIFEST_SHA256` を渡す。実行直前に同じinstall先から計算したSHAを自己承認anchorにしない。

途中失敗した `RELEASE_ROOT` は不完全releaseとして隔離し、上書き・再利用しない。削除が必要なら対象を人間が確認し、別途承認する。通常releaseは `SIGNING_KEY` を読取り検査するだけで、内容やmodeを変更しない。

model、service tier、料金、long-context条件は変化し得る。live承認前に [REFERENCES.md](REFERENCES.md) の公式資料とpinned pricing policyを照合する。差異があればpolicy、manifest、費用上限を新releaseとして作り直す。

## 8. workflowを初期化する

`workflow-init` はcredentialやnetworkを使わないが、protected sourceの事前準備済みPython環境とcandidateへaccessする。coordinator userで読めないsource/environmentしかない場合は、ownerを場当たり的に緩めずrelease工程へ戻る。

```bash
set -euo pipefail
umask 077

: "${APPROVED_RELEASE_SOURCE:?}"
: "${RELEASE_ID:?}"
: "${RELEASE_ROOT:?}"
: "${REVIEW_USER:?}"
: "${APPROVED_UV:?}"
: "${APPROVED_UV_PROJECT_ENVIRONMENT:?}"
: "${APPROVED_MANIFEST_SHA256:?}"
: "${PROTECTED_CANDIDATE_REPO:?}"
: "${CANDIDATE_UID:?}"
: "${HUMAN_APPROVED_PATCH_SHA256:?}"
: "${INITIAL_ARTIFACT_ROOT:?}"

[[ "$RELEASE_ID" =~ ^[0-9a-f]{40}$ ]]
[[ "$APPROVED_MANIFEST_SHA256" =~ ^[0-9a-f]{64}$ ]]
[[ "$HUMAN_APPROVED_PATCH_SHA256" =~ ^[0-9a-f]{64}$ ]]
[[ "$INITIAL_ARTIFACT_ROOT" = /* && "$INITIAL_ARTIFACT_ROOT" != / ]]
[[ "$APPROVED_UV_PROJECT_ENVIRONMENT" = /* && \
  "$APPROVED_UV_PROJECT_ENVIRONMENT" != / ]]
test "$CANDIDATE_UID" -gt 0
test "$(id -un)" = "$REVIEW_USER"
test "$(id -u)" -ne 0
test "$(id -u)" -ne "$CANDIDATE_UID"
test ! -e "$INITIAL_ARTIFACT_ROOT"
test ! -L "$INITIAL_ARTIFACT_ROOT"
test "$(/usr/bin/readlink -m -- "$INITIAL_ARTIFACT_ROOT")" = \
  "$INITIAL_ARTIFACT_ROOT"

approved_source=$(/usr/bin/readlink -e -- "$APPROVED_RELEASE_SOURCE")
test "$approved_source" = "$APPROVED_RELEASE_SOURCE"
source_ancestor=$approved_source
while :; do
  source_owner=$(stat -c '%u' "$source_ancestor")
  source_mode=$(stat -c '%a' "$source_ancestor")
  test "$source_owner" -eq 0 || test "$source_owner" -eq "$(id -u)"
  (( (8#$source_mode & 0022) == 0 ))
  if test "$source_ancestor" = /; then
    break
  fi
  source_ancestor=$(dirname -- "$source_ancestor")
done

validate_release_source_tree() {
  local root=$1
  local root_device entry entry_device entry_owner entry_mode_hex entry_mode entry_type
  root_device=$(stat -c '%d' -- "$root")
  find -P "$root" -xdev -print0 |
    while IFS= read -r -d '' entry; do
      entry_device=$(stat -c '%d' -- "$entry")
      entry_owner=$(stat -c '%u' -- "$entry")
      entry_mode_hex=$(stat -c '%f' -- "$entry")
      entry_mode=$((16#$entry_mode_hex))
      entry_type=$((entry_mode & 0170000))

      test "$entry_device" = "$root_device"
      test "$entry_owner" -ne "$CANDIDATE_UID"
      test "$entry_owner" -eq 0 || test "$entry_owner" -eq "$(id -u)"
      (( (entry_mode & 0022) == 0 ))
      if (( entry_type == 0040000 )); then
        continue
      fi
      if (( entry_type == 0100000 )); then
        test "$(stat -c '%h' -- "$entry")" = 1
        continue
      fi
      printf '%s\n' 'release source contains a symlink or special file' >&2
      return 2
  done
}

require_root_owned_existing_path() {
  local path=$1
  local canonical current mode
  [[ "$path" = /* ]]
  canonical=$(/usr/bin/readlink -e -- "$path")
  test "$canonical" = "$path"
  current=$path
  while :; do
    test "$(stat -c '%u:%g' "$current")" = 0:0
    mode=$(stat -c '%a' "$current")
    (( (8#$mode & 0022) == 0 ))
    if test "$current" = /; then
      break
    fi
    current=$(dirname -- "$current")
  done
}

validate_root_owned_uv_environment() {
  local root=$1
  local root_device entry entry_device entry_owner entry_mode_hex entry_mode entry_type
  local resolved resolved_mode
  root_device=$(stat -c '%d' -- "$root")
  find -P "$root" -xdev -print0 |
    while IFS= read -r -d '' entry; do
      entry_owner=$(stat -c '%u' -- "$entry")
      entry_mode_hex=$(stat -c '%f' -- "$entry")
      entry_mode=$((16#$entry_mode_hex))
      entry_type=$((entry_mode & 0170000))
      test "$entry_owner" -eq 0

      if (( entry_type == 0120000 )); then
        resolved=$(/usr/bin/readlink -e -- "$entry")
        case "$resolved" in
          "$root"|"$root"/*) ;;
          *)
            require_root_owned_existing_path "$resolved"
            test -f "$resolved"
            test "$(stat -c '%h' -- "$resolved")" = 1
            resolved_mode=$(stat -c '%a' -- "$resolved")
            (( (8#$resolved_mode & 06000) == 0 ))
            ;;
        esac
        continue
      fi

      entry_device=$(stat -c '%d' -- "$entry")
      test "$entry_device" = "$root_device"
      (( (entry_mode & 06022) == 0 ))
      if (( entry_type == 0040000 )); then
        continue
      fi
      if (( entry_type == 0100000 )); then
        test "$(stat -c '%h' -- "$entry")" = 1
        continue
      fi
      printf '%s\n' 'approved uv environment contains an unsafe entry' >&2
      return 2
    done
}

validate_release_source_tree "$approved_source"
test -d "$approved_source/.git"
test ! -L "$approved_source/.git"

require_root_owned_existing_path "$APPROVED_UV"
test -f "$APPROVED_UV"
test "$(stat -c '%h' "$APPROVED_UV")" = 1
test -x "$APPROVED_UV"
approved_uv_mode=$(stat -c '%a' "$APPROVED_UV")
(( (8#$approved_uv_mode & 06000) == 0 ))
approved_uv_environment=$(
  /usr/bin/readlink -e -- "$APPROVED_UV_PROJECT_ENVIRONMENT"
)
test "$approved_uv_environment" = "$APPROVED_UV_PROJECT_ENVIRONMENT"
require_root_owned_existing_path "$approved_uv_environment"
test -d "$approved_uv_environment"
validate_root_owned_uv_environment "$approved_uv_environment"

case "$approved_uv_environment/" in
  "$approved_source/"*)
    printf '%s\n' 'approved uv environment must be outside the release source' >&2
    exit 2
    ;;
esac
case "$approved_source/" in
  "$approved_uv_environment/"*)
    printf '%s\n' 'release source must be outside the approved uv environment' >&2
    exit 2
    ;;
esac

run_approved_uv() {
  /usr/bin/env -i \
    GIT_CONFIG_GLOBAL=/dev/null \
    GIT_CONFIG_NOSYSTEM=1 \
    GIT_OPTIONAL_LOCKS=0 \
    HOME=/nonexistent \
    LC_ALL=C \
    PATH=/bin:/usr/bin \
    PYTHONHASHSEED=0 \
    PYTHONNOUSERSITE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT="$approved_uv_environment" \
    "$APPROVED_UV" run --project "$approved_source" \
    --frozen --offline --no-sync --no-env-file --no-cache --no-config \
    "$@"
}

cd "$approved_source"
source_root=$(/usr/bin/readlink -e -- "$(git rev-parse --show-toplevel)")
test "$source_root" = "$approved_source"
git_dir=$(/usr/bin/readlink -e -- "$(git rev-parse --absolute-git-dir)")
test "$git_dir" = "$approved_source/.git"
test "$(git rev-parse HEAD)" = "$RELEASE_ID"
workflow_source_status=$(
  GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_OPTIONAL_LOCKS=0 \
    git -c core.fsmonitor=false -c core.untrackedCache=false \
    status --porcelain=v1 --untracked-files=all \
    --ignored=matching --ignore-submodules=none
)
test -z "$workflow_source_status"
validate_release_source_tree "$approved_source"

run_approved_uv python \
  -m tools.ai_review.runtime_release workflow-init \
  --task "$RELEASE_ROOT/runtime/task.json" \
  --runtime-manifest "$RELEASE_ROOT/runtime/runtime-manifest.json" \
  --expected-runtime-manifest-sha256 "$APPROVED_MANIFEST_SHA256" \
  --coordinator-public-key "$RELEASE_ROOT/runtime/coordinator-public.pem" \
  --candidate-repo "$PROTECTED_CANDIDATE_REPO" \
  --candidate-uid "$CANDIDATE_UID" \
  --expected-patch-sha256 "$HUMAN_APPROVED_PATCH_SHA256" \
  --output-dir "$INITIAL_ARTIFACT_ROOT"

validate_release_source_tree "$approved_source"
test "$(git rev-parse HEAD)" = "$RELEASE_ID"
post_workflow_init_source_status=$(
  GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_OPTIONAL_LOCKS=0 \
    git -c core.fsmonitor=false -c core.untrackedCache=false \
    status --porcelain=v1 --untracked-files=all \
    --ignored=matching --ignore-submodules=none
)
test -z "$post_workflow_init_source_status"
validate_root_owned_uv_environment "$approved_uv_environment"
```

成功時は、stdoutの非secret digestを外部承認記録と照合する。特に `phase_request_file_sha256` と `coordinator_key_id` を、live実行用の `EXPECTED_INITIAL_REQUEST_FILE_SHA256` と `EXPECTED_COORDINATOR_KEY_ID` として別経路へ固定する。新規directoryは0500、`phase-request.json` は0400で、requestは新しい `workflow_id`、`phase="snapshot"`、`sequence=1` を持つ。

失敗したoutput pathを削除して再利用しない。承認値、candidate ownership、standalone/clean/single-commit条件を直し、新しいpathへ初期化する。

## 9. credential-free deployment check

このmodeはcredential、artifact、candidate、signing key、ledgerを受け取らない。rootless Podman storeで4つのsmoke containerを作成・削除するため、純粋なread-only診断ではない。implicit pull、external network、API callは行わない。

```bash
set -euo pipefail

: "${APPROVED_PYTHON:?}"
: "${RELEASE_ROOT:?}"
: "${APPROVED_MANIFEST_SHA256:?}"
: "${CANDIDATE_UID:?}"
: "${COORDINATOR_IMAGE:?}"
: "${OFFLINE_IMAGE:?}"
: "${BROKER_IMAGE:?}"
: "${BROKER_GATEWAY_IMAGE:?}"

[[ "$APPROVED_MANIFEST_SHA256" =~ ^[0-9a-f]{64}$ ]]
test "$CANDIDATE_UID" -gt 0
test "$(id -u)" -ne "$CANDIDATE_UID"

require_root_owned_existing_path() {
  local path=$1
  local canonical current mode
  [[ "$path" = /* ]]
  canonical=$(/usr/bin/readlink -e -- "$path")
  test "$canonical" = "$path"
  current=$path
  while :; do
    test "$(stat -c '%u:%g' "$current")" = 0:0
    mode=$(stat -c '%a' "$current")
    (( (8#$mode & 0022) == 0 ))
    if test "$current" = /; then
      break
    fi
    current=$(dirname -- "$current")
  done
}

require_root_owned_existing_path "$APPROVED_PYTHON"
test -f "$APPROVED_PYTHON"
test "$(stat -c '%h' "$APPROVED_PYTHON")" = 1
test -x "$APPROVED_PYTHON"
approved_python_mode=$(stat -c '%a' "$APPROVED_PYTHON")
(( (8#$approved_python_mode & 06000) == 0 ))

require_root_owned_existing_path "$RELEASE_ROOT"
test -d "$RELEASE_ROOT"
test "$(stat -c '%a' "$RELEASE_ROOT")" = 755

"$APPROVED_PYTHON" -I -S \
  "$RELEASE_ROOT/bin/external_launcher.py" \
  --manifest "$RELEASE_ROOT/runtime/runtime-manifest.json" \
  --expected-manifest-sha256 "$APPROVED_MANIFEST_SHA256" \
  --candidate-uid "$CANDIDATE_UID" \
  --deployment-check \
  --coordinator-image "$COORDINATOR_IMAGE" \
  --offline-image "$OFFLINE_IMAGE" \
  --broker-image "$BROKER_IMAGE" \
  --broker-gateway-image "$BROKER_GATEWAY_IMAGE"
```

成功条件は終了0と、canonical stdoutの次の値である。

```json
{
  "credentials_read": false,
  "external_api_called": false,
  "external_network_created": false,
  "production_e2e_complete": false,
  "status": "nonlive_ready"
}
```

実際のstdoutには追加の非secret evidence digestが含まれ得る。上記5項目の意味を変えない。失敗時にimageをpull/buildしたり、Docker/rootfulへfallbackしたりしない。修正操作は別承認に戻す。

## 10. 明示承認後にfull 7-phase workflowを実行する

### 10.1 実行直前チェック

毎回、次を新しい承認記録へ固定する。

- TaskSpec、candidate head、canonical patch、initial request file、manifest、4 imageのdigest
- 実際に送信し得るpacket範囲と除外対象
- `api.openai.com:443`、model、service tier、reviewer/adversaryの役割
- roleごとのattempt、timeout、input/output token、packet token、費用の上限
- reviewer/adversary credential fileのcustodyと、異なる継承FDで渡すこと
- artifact、broker ledger、nonce ledgerの保存、backup、削除方針
- 現在の公式料金とpinned pricing policyが一致すること
- keygen時のcustody記録が `EXPECTED_COORDINATOR_KEY_ID`、公開鍵digest、`SIGNING_KEY` pathを同一pairとして結んでいること

launcherはprivate継承FDからcredentialを読み、隔離broker processへ固定環境変数としてだけ渡す。credentialをparent環境、argv、stdin、artifact、gatewayへ渡さない。

現行実装がprivate/public keyの暗号学的な一致を再確認するのは、broker送信後の `sign` phaseである。したがって、keygen時に作った外部custody記録で `SIGNING_KEY` と `EXPECTED_COORDINATOR_KEY_ID` の対応を確認できない場合は、費用発生前の保証がなく、live workflowを実行しない。shellでprivate keyを読み出して場当たり的にkey IDを再計算しない。

### 10.2 実行コマンド

次はBashで実行する。fail-fast、dynamic FD、EXIT trapを外さない。`WORKFLOW_OUTPUT_ROOT` と `BROKER_LEDGER` は新規、nonce rootは永続private rootである。

```bash
set -euo pipefail
umask 077

: "${APPROVED_PYTHON:?}"
: "${RELEASE_ROOT:?}"
: "${APPROVED_MANIFEST_SHA256:?}"
: "${CANDIDATE_UID:?}"
: "${COORDINATOR_IMAGE:?}"
: "${OFFLINE_IMAGE:?}"
: "${BROKER_IMAGE:?}"
: "${BROKER_GATEWAY_IMAGE:?}"
: "${INITIAL_ARTIFACT_ROOT:?}"
: "${WORKFLOW_OUTPUT_ROOT:?}"
: "${PROTECTED_CANDIDATE_REPO:?}"
: "${SIGNING_KEY:?}"
: "${BROKER_LEDGER:?}"
: "${ATTESTATION_NONCE_LEDGER_ROOT:?}"
: "${REVIEWER_CREDENTIAL_FILE:?}"
: "${ADVERSARY_CREDENTIAL_FILE:?}"
: "${TIMEOUT_SECONDS:?}"
: "${EXPECTED_INITIAL_REQUEST_FILE_SHA256:?}"
: "${EXPECTED_COORDINATOR_KEY_ID:?}"

[[ "$APPROVED_MANIFEST_SHA256" =~ ^[0-9a-f]{64}$ ]]
[[ "$EXPECTED_INITIAL_REQUEST_FILE_SHA256" =~ ^[0-9a-f]{64}$ ]]
[[ "$EXPECTED_COORDINATOR_KEY_ID" =~ ^[0-9a-f]{64}$ ]]
[[ "$WORKFLOW_OUTPUT_ROOT" = /* && "$WORKFLOW_OUTPUT_ROOT" != / ]]
[[ "$BROKER_LEDGER" = /* && "$BROKER_LEDGER" != / ]]
[[ "$ATTESTATION_NONCE_LEDGER_ROOT" = /* && "$ATTESTATION_NONCE_LEDGER_ROOT" != / ]]
test "$CANDIDATE_UID" -gt 0
test "$(id -u)" -ne "$CANDIDATE_UID"
test "$TIMEOUT_SECONDS" -ge 1
test "$TIMEOUT_SECONDS" -le 900

current_uid=$(id -u)
current_gid=$(id -g)

require_protected_existing_path() {
  local path=$1
  local canonical current owner mode
  [[ "$path" = /* ]]
  canonical=$(/usr/bin/readlink -e -- "$path")
  test "$canonical" = "$path"
  current=$path
  while :; do
    owner=$(stat -c '%u' "$current")
    mode=$(stat -c '%a' "$current")
    test "$owner" -eq 0 || test "$owner" -eq "$current_uid"
    (( (8#$mode & 0022) == 0 ))
    if test "$current" = /; then
      break
    fi
    current=$(dirname -- "$current")
  done
}

require_root_owned_existing_path() {
  local path=$1
  local canonical current mode
  [[ "$path" = /* ]]
  canonical=$(/usr/bin/readlink -e -- "$path")
  test "$canonical" = "$path"
  current=$path
  while :; do
    test "$(stat -c '%u:%g' "$current")" = 0:0
    mode=$(stat -c '%a' "$current")
    (( (8#$mode & 0022) == 0 ))
    if test "$current" = /; then
      break
    fi
    current=$(dirname -- "$current")
  done
}

require_private_directory() {
  local path=$1
  require_protected_existing_path "$path"
  test -d "$path"
  test "$(stat -c '%u:%g' "$path")" = "$current_uid:$current_gid"
  test "$(stat -c '%a' "$path")" = 700
}

require_new_private_child() {
  local path=$1
  local parent
  [[ "$path" = /* && "$path" != / ]]
  test ! -e "$path"
  test ! -L "$path"
  test "$(/usr/bin/readlink -m -- "$path")" = "$path"
  parent=$(dirname -- "$path")
  require_private_directory "$parent"
}

paths_overlap() {
  local left=$1
  local right=$2
  if test "$left" = "$right"; then
    return 0
  fi
  case "$left/" in
    "$right/"*) return 0 ;;
  esac
  case "$right/" in
    "$left/"*) return 0 ;;
  esac
  return 1
}

require_root_owned_existing_path "$APPROVED_PYTHON"
test -f "$APPROVED_PYTHON"
test "$(stat -c '%h' "$APPROVED_PYTHON")" = 1
test -x "$APPROVED_PYTHON"
approved_python_mode=$(stat -c '%a' "$APPROVED_PYTHON")
(( (8#$approved_python_mode & 06000) == 0 ))

require_root_owned_existing_path "$RELEASE_ROOT"
test -d "$RELEASE_ROOT"
test "$(stat -c '%u:%g' "$RELEASE_ROOT")" = 0:0
test "$(stat -c '%a' "$RELEASE_ROOT")" = 755

require_protected_existing_path "$INITIAL_ARTIFACT_ROOT"
test -d "$INITIAL_ARTIFACT_ROOT"
test "$(stat -c '%u:%g' "$INITIAL_ARTIFACT_ROOT")" = \
  "$current_uid:$current_gid"
test "$(stat -c '%a' "$INITIAL_ARTIFACT_ROOT")" = 500

initial_request="$INITIAL_ARTIFACT_ROOT/phase-request.json"
require_protected_existing_path "$initial_request"
test -f "$initial_request"
test "$(stat -c '%u:%g' "$initial_request")" = "$current_uid:$current_gid"
test "$(stat -c '%a' "$initial_request")" = 400
test "$(stat -c '%h' "$initial_request")" = 1

initial_request_file_sha256=$(sha256sum -- "$initial_request" | awk '{print $1}')
test "$initial_request_file_sha256" = "$EXPECTED_INITIAL_REQUEST_FILE_SHA256"

request_key_id=$(
  "$APPROVED_PYTHON" -I -S -c '
import json
import re
import sys

with open(sys.argv[1], "rb") as handle:
    request = json.load(handle)
key_id = request.get("coordinator_key_id") if isinstance(request, dict) else None
if not isinstance(key_id, str) or re.fullmatch(r"[0-9a-f]{64}", key_id) is None:
    raise SystemExit(2)
print(key_id)
' "$initial_request"
)
test "$request_key_id" = "$EXPECTED_COORDINATOR_KEY_ID"

require_protected_existing_path "$PROTECTED_CANDIDATE_REPO"

require_protected_existing_path "$SIGNING_KEY"
test -f "$SIGNING_KEY"
test "$(stat -c '%a' "$SIGNING_KEY")" = 400
test "$(stat -c '%h' "$SIGNING_KEY")" = 1
test "$(stat -c '%u:%g' "$SIGNING_KEY")" = "$current_uid:$current_gid"

require_protected_existing_path "$ATTESTATION_NONCE_LEDGER_ROOT"
test -d "$ATTESTATION_NONCE_LEDGER_ROOT"
test "$(stat -c '%a' "$ATTESTATION_NONCE_LEDGER_ROOT")" = 700
test "$(stat -c '%u:%g' "$ATTESTATION_NONCE_LEDGER_ROOT")" = \
  "$current_uid:$current_gid"
unexpected_nonce_entry=$(find "$ATTESTATION_NONCE_LEDGER_ROOT" \
  -mindepth 1 -maxdepth 1 ! -name nonces.sqlite3 -print -quit)
test -z "$unexpected_nonce_entry"

if test -e "$ATTESTATION_NONCE_LEDGER_ROOT/nonces.sqlite3"; then
  nonce_db="$ATTESTATION_NONCE_LEDGER_ROOT/nonces.sqlite3"
  require_protected_existing_path "$nonce_db"
  test -f "$nonce_db"
  test "$(stat -c '%a' "$nonce_db")" = 600
  test "$(stat -c '%h' "$nonce_db")" = 1
  test "$(stat -c '%u:%g' "$nonce_db")" = "$current_uid:$current_gid"
fi

for credential_file in \
  "$REVIEWER_CREDENTIAL_FILE" \
  "$ADVERSARY_CREDENTIAL_FILE"; do
  require_protected_existing_path "$credential_file"
  test -f "$credential_file"
  test "$(stat -c '%a' "$credential_file")" = 600
  test "$(stat -c '%h' "$credential_file")" = 1
  test "$(stat -c '%u:%g' "$credential_file")" = "$current_uid:$current_gid"
  credential_size=$(stat -c '%s' "$credential_file")
  test "$credential_size" -ge 1
  test "$credential_size" -le 16384
  require_private_directory "$(dirname -- "$credential_file")"
done

require_new_private_child "$WORKFLOW_OUTPUT_ROOT"
require_new_private_child "$BROKER_LEDGER"

regions=(
  "$INITIAL_ARTIFACT_ROOT"
  "$PROTECTED_CANDIDATE_REPO"
  "$RELEASE_ROOT"
  "$SIGNING_KEY"
  "$ATTESTATION_NONCE_LEDGER_ROOT"
  "$REVIEWER_CREDENTIAL_FILE"
  "$ADVERSARY_CREDENTIAL_FILE"
  "$WORKFLOW_OUTPUT_ROOT"
  "$BROKER_LEDGER"
)
for ((left_index = 0; left_index < ${#regions[@]}; left_index++)); do
  for ((right_index = left_index + 1; right_index < ${#regions[@]}; right_index++)); do
    if paths_overlap "${regions[$left_index]}" "${regions[$right_index]}"; then
      printf '%s\n' 'workflow security regions must be disjoint' >&2
      exit 2
    fi
  done
done

mkdir -m 0700 "$WORKFLOW_OUTPUT_ROOT"

file_identity() {
  stat -L -c '%d:%i:%u:%g:%a:%h:%s' -- "$1"
}

reviewer_path_identity=$(file_identity "$REVIEWER_CREDENTIAL_FILE")
adversary_path_identity=$(file_identity "$ADVERSARY_CREDENTIAL_FILE")

reviewer_fd=
adversary_fd=
close_credential_fds() {
  if [[ -n ${reviewer_fd:-} ]]; then
    exec {reviewer_fd}<&-
  fi
  if [[ -n ${adversary_fd:-} ]]; then
    exec {adversary_fd}<&-
  fi
}
trap close_credential_fds EXIT

exec {reviewer_fd}<"$REVIEWER_CREDENTIAL_FILE"
exec {adversary_fd}<"$ADVERSARY_CREDENTIAL_FILE"
test "$reviewer_fd" -ne "$adversary_fd"

test "$(file_identity "$REVIEWER_CREDENTIAL_FILE")" = "$reviewer_path_identity"
test "$(file_identity "/proc/$$/fd/$reviewer_fd")" = "$reviewer_path_identity"
test "$(file_identity "$ADVERSARY_CREDENTIAL_FILE")" = "$adversary_path_identity"
test "$(file_identity "/proc/$$/fd/$adversary_fd")" = "$adversary_path_identity"

workflow_status=0
"$APPROVED_PYTHON" -I -S \
  "$RELEASE_ROOT/bin/external_launcher.py" \
  --manifest "$RELEASE_ROOT/runtime/runtime-manifest.json" \
  --expected-manifest-sha256 "$APPROVED_MANIFEST_SHA256" \
  --candidate-uid "$CANDIDATE_UID" \
  --workflow \
  --coordinator-image "$COORDINATOR_IMAGE" \
  --offline-image "$OFFLINE_IMAGE" \
  --broker-image "$BROKER_IMAGE" \
  --broker-gateway-image "$BROKER_GATEWAY_IMAGE" \
  --artifact-root "$INITIAL_ARTIFACT_ROOT" \
  --phase-request "$INITIAL_ARTIFACT_ROOT/phase-request.json" \
  --phase-output-root "$WORKFLOW_OUTPUT_ROOT" \
  --candidate-repo "$PROTECTED_CANDIDATE_REPO" \
  --signing-key "$SIGNING_KEY" \
  --broker-ledger "$BROKER_LEDGER" \
  --attestation-nonce-ledger-root "$ATTESTATION_NONCE_LEDGER_ROOT" \
  --reviewer-credential-fd "$reviewer_fd" \
  --adversary-credential-fd "$adversary_fd" \
  --timeout-seconds "$TIMEOUT_SECONDS" || workflow_status=$?

close_credential_fds
trap - EXIT
reviewer_fd=
adversary_fd=
test "$workflow_status" -eq 0
```

成功時stdoutは、少なくとも次を含むcanonical JSONである。

```json
{
  "human_approval_required": true,
  "phase_count": 7,
  "status": "complete"
}
```

実際のstdoutには `final_phase_sha256` も含まれる。verdictが `pass` でも、commit、push、merge、再送信を自動実行しない。

## 11. 結果、終了コード、再実行

| 入口 | 終了0 | 終了2 | 終了1・signal・traceback |
|---|---|---|---|
| `runtime_release` / `build_zipapp` | asset生成成功 | 入力、policy、出力安全性、CLI使用法の失敗 | 未処理例外として失敗 |
| `--deployment-check` | `nonlive_ready` | manifest、backend、image、smoke、CLIのfail-closed停止 | 成功扱いせず停止 |
| `--workflow` | 7 phase完了 | readiness、trust、isolation、protocol、outer executionのfail-closed停止 | 成功扱いせず停止 |

失敗時は次を行う。

1. 最後に確定したphase、終了状態、非機密digest、観測した停止理由を記録する。
2. 外部送信・credential読取り・課金の状態を証拠で確認する。確認不能なら「不明」とする。
3. container、network、credential FDのcleanupを確認する。credential値やraw responseを表示しない。
4. 失敗artifactを削除・上書きせず隔離する。削除が必要なら対象を人間が確認して別途承認する。
5. 原因を修正・再承認し、新しいworkflow ID、initial artifact root、output root、broker ledgerで最初から実行する。
6. 永続nonce ledgerは維持する。replayを避ける目的でrollback、削除、別ledgerへの迂回をしない。

証拠の内容を一括 `cat` しない。owner、mode、size、SHA-256、canonical summaryなど、非機密の検証値だけを記録する。

## 12. 記録先

| 記録内容 | 更新先 |
|---|---|
| 現在の到達状態、未完了のlive境界 | [GOAL.md](GOAL.md)、[EXEC-002](GOAL.md#exec-002-attested-ai-review境界の実装) |
| 実行日、非機密digest、exit、検証範囲 | [WORKLOG.md](WORKLOG.md) |
| 利用者・運用者に影響する統合済み変更 | [CHANGELOG.md](CHANGELOG.md) |
| 契約・脅威・承認規則の変更 | [統合済みAIレビュー規約](DEVELOPMENT.md#統合済みaiレビュー規約)、[SECURITY.md](SECURITY.md) |
| CLI、schema、policy、テストの変更 | 実装、対応test、このRunbook |

credential、private key、生API response、利用者入力、生cache、review packet本文、providerのsecret-bearing診断を文書へ保存しない。liveを実行していない場合は、`nonlive_ready` やoffline testをlive成功と記録しない。

## 13. 関連資料

- [AIレビュー運用規約](DEVELOPMENT.md#統合済みaiレビュー規約)
- [セキュリティ](SECURITY.md)
- [現在の到達点](GOAL.md)
- [attested AIレビュー境界のExecution Plan](GOAL.md#exec-002-attested-ai-review境界の実装)
- [作業履歴](WORKLOG.md)
- [公式資料一覧](REFERENCES.md)
